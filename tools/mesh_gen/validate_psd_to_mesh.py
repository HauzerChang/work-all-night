#!/usr/bin/env python3
"""端到端整合 AC:PSD 件 → S3 生成 mesh → 對照真實生產 spine 的藝術家 mesh。

串起 S4(PSD 切圖)與 S3(mesh 生成),對**真實生產標的**(Award「機器人拆件」)驗收:
  PSD leaf 圖層 → 緊湊件 PNG(psd_slice)→ generate_mesh_v2(auto) → 覆蓋率 IoU
  ↔ Award 對應 slot 的藝術家 mesh 覆蓋率(ground truth)+ 格式/品質閘。

⚠️ 變形機制差異(重要,見 knowledge/s5? / s3-psd-to-award.md):
  main_draw 窗簾 = **unweighted + deform timeline**(逐頂點 deform)→ 用真實位移場轉移閘。
  Award 機器人件 = **weighted(骨綁)+ 無 deform timeline** → 靠骨骼/權重變形。
  ⇒ 本標的**無 deform 場可轉移**,變形閘 N/A;可對比的真值是「靜態覆蓋率 + 拓樸品質」。
    (weighted 變形穩健度需 BBW 權重,屬 S3 後續子能力,不在本閘。)

自我修正(AC-first,RULES 5 輪預算內):generate_mesh_v2 auto 對非長條件回退 v1(Delaunay)。
v1 預設 epsilon_frac=0.008 為 main_draw 簡單外形調的;器官狀外形(光暈)邊界需更細取樣。
若覆蓋率 < 藝術家基準,依序收斂 epsilon(0.008→0.004→0.002→0.001)取第一個達標且在頂點預算內者。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from psd_slice import slice_psd
from generate_mesh_v2 import generate as gen_v2
from generate_mesh import generate as gen_v1
from evaluate_mesh import evaluate, load_mask
from validate_against_real import artist_iou

EPS_LADDER = [0.008, 0.004, 0.002, 0.001]  # 覆蓋率不足時的細化階梯(<=4 輪,符合 5 輪預算)


def award_mesh(skeleton, slot, name):
    skins = skeleton["skins"]
    att = skins[0]["attachments"] if isinstance(skins, list) else skins.get("attachments", skins)
    a = att[slot][name]
    nv = len(a["uvs"]) // 2
    weighted = len(a["vertices"]) != len(a["uvs"])
    return {"nv": nv, "hull": a["hull"], "tris": len(a["triangles"]) // 3, "weighted": weighted}


def has_deform(skeleton, slot):
    for _, data in skeleton.get("animations", {}).items():
        for _, slots in data.get("deform", {}).items():
            if slot in slots:
                return True
    return False


def gen_with_refine(png, mask, target_iou, margin, budget):
    """v2 auto;若回退 v1 且覆蓋率不足,收斂 epsilon 直到達標且在頂點預算內。"""
    mesh = gen_v2(png, mode="auto")
    iou = evaluate(mesh, mask, vertex_budget=budget)["criteria"]["AC1_iou"]["value"]
    trail = [{"mode": mesh.get("_mode"), "eps": None, "nv": len(mesh["uvs"]) // 2, "iou": iou}]
    if mesh.get("_mode") == "strip" or iou >= target_iou - margin:
        return mesh, iou, trail
    # v1 回退路徑:細化 epsilon
    for eps in EPS_LADDER:
        m, _ = gen_v1(png, max_interior=80, epsilon_frac=eps)
        nv = len(m["uvs"]) // 2
        i = evaluate(m, mask, vertex_budget=budget)["criteria"]["AC1_iou"]["value"]
        trail.append({"mode": "delaunay-v1", "eps": eps, "nv": nv, "iou": i})
        if i >= target_iou - margin and nv <= budget:
            m["_mode"] = f"delaunay-v1(eps={eps})"
            return m, i, trail
    # 未達標 → 回傳目前最佳(覆蓋率最高且在預算內者)
    best = max((t for t in trail if t["nv"] <= budget), key=lambda t: t["iou"], default=trail[0])
    m, _ = gen_v1(png, max_interior=80, epsilon_frac=best["eps"] or 0.008)
    m["_mode"] = f"delaunay-v1(eps={best['eps']},best)"
    return m, best["iou"], trail


def validate(psd_path, skeleton_path, parts, slot_prefix, margin, budget, tmp_dir):
    sk = json.load(open(skeleton_path))
    _, _, sliced = slice_psd(psd_path, tmp_dir)
    by_name = {e["name"]: (e, im) for e, im in sliced}
    reports = []
    for part in parts:
        if part not in by_name:
            reports.append({"part": part, "error": "PSD 無此圖層"}); continue
        entry, im = by_name[part]
        png = os.path.join(tmp_dir, entry["file"])
        mask = load_mask(png)
        slot = f"{slot_prefix}{part}"
        art = award_mesh(sk, slot, slot)
        art_iou = artist_iou(sk, slot, slot, mask)
        mesh, iou, trail = gen_with_refine(png, mask, art_iou, margin, budget)
        ev = evaluate(mesh, mask, vertex_budget=budget)
        cov_pass = iou >= art_iou - margin
        fmt_pass = ev["criteria"]["AC4_format"]["pass"]
        orphan_pass = ev["criteria"]["AC2c_orphans"]["pass"]
        degen_pass = ev["criteria"]["AC2b_degenerate"]["pass"]
        budget_pass = ev["criteria"]["AC3_vertex_budget"]["pass"]
        overall = cov_pass and fmt_pass and orphan_pass and degen_pass and budget_pass
        reports.append({
            "part": part, "slot": slot,
            "gen": {"nv": len(mesh["uvs"]) // 2, "hull": mesh["hull"],
                    "tris": len(mesh["triangles"]) // 3, "mode": mesh.get("_mode")},
            "artist": art,
            "AC_coverage": {"gen_iou": round(iou, 4), "artist_iou": round(art_iou, 4),
                            "margin": margin, "pass": cov_pass},
            "AC_format": {"pass": fmt_pass, "orphans": ev["criteria"]["AC2c_orphans"]["value"],
                          "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                          "budget_pass": budget_pass, "nv": len(mesh["uvs"]) // 2, "budget": budget},
            "AC_deform": {"applicable": has_deform(sk, slot),
                          "note": "weighted+no deform timeline → 變形靠骨/權重,無位移場可轉移(N/A)"},
            "refine_trail": trail,
            "overall_pass": overall,
        })
    return {"source": os.path.basename(psd_path), "target": os.path.basename(skeleton_path),
            "overall_pass": all(r.get("overall_pass") for r in reports), "parts": reports}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--parts", nargs="+", default=["光暈", "身體", "左手"])
    ap.add_argument("--slot-prefix", default="機器人拆件/")
    ap.add_argument("--margin", type=float, default=0.01)
    ap.add_argument("--budget", type=int, default=128)
    ap.add_argument("--tmp", default="/tmp/robot_parts")
    a = ap.parse_args()
    rep = validate(a.psd, a.skeleton, a.parts, a.slot_prefix, a.margin, a.budget, a.tmp)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
