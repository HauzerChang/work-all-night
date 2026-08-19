#!/usr/bin/env python3
"""端到端 AC:PSD 件 → S3 generate_mesh_v2 → 對照 Award 真實(藝術家)mesh。

背景(STATE.md 最高優先 chunk):robot_parts.psd 的 3 個件(光暈/身體/左手)在生產
spine `Award` 中為 mesh。本工具把「PSD 切件 alpha」餵給 S3 生成器,與 Award 藝術家
mesh 做**靜態覆蓋率 + 拓樸 + 頂點預算**對照 —— 對真實生產標的的端到端驗收。

⚠️ 這 5 件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform,見
knowledge/s4-psd-to-spine-real.md)。故 deform 閘 N/A;本 chunk 收斂在靜態 AC。

評估器可信度自檢(RULES「每能力必配評估器 + 評估器要先校準」):
  先量藝術家 mesh 對自身件 alpha 的 IoU。若高 → UV frame / 對齊正確,baseline 可信;
  否則標記為評估器問題,不誤判生成器。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask


# robot_parts.psd 件 → Award slot(皆 mesh)。件 PNG 由 psd_slice 切出。
PARTS = [
    {"key": "光暈", "png": "00_光暈.png",  "slot": "機器人拆件/光暈"},
    {"key": "身體", "png": "03_身體.png",  "slot": "機器人拆件/身體"},
    {"key": "左手", "png": "04_左手.png",  "slot": "機器人拆件/左手"},
]


def artist_attachment(sk, slot):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)[slot]
    return list(att.values())[0]


def fill_iou(pts_xy, tris, mask):
    """把三角形填滿成 recon,對 mask 算 IoU。pts_xy 為像素座標(y-down)。"""
    H, W = mask.shape
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        poly = np.round(pts_xy[t]).astype(np.int32)
        cv2.fillConvexPoly(recon, poly, 1)
    m = (mask > 0).astype(np.uint8)
    inter = int(np.logical_and(recon, m).sum())
    union = int(np.logical_or(recon, m).sum())
    return inter / union if union else 0.0


def artist_iou_variants(att, mask):
    """兩種 UV frame 詮釋各算一次,回傳 {frame: iou}。
    - region_local: uvs 直接 * (W,H)(main_draw 曲簾驗證過的詮釋)
    - minmax_norm : uvs 先各軸 min-max 正規化再 * (W,H)(對 bbox 未貼齊 region 的件)
    """
    H, W = mask.shape
    uv = np.array(att["uvs"]).reshape(-1, 2)
    tris = np.array(att["triangles"]).reshape(-1, 3)
    out = {}
    # region_local
    rl = np.column_stack([uv[:, 0] * W, uv[:, 1] * H])
    out["region_local"] = fill_iou(rl, tris, mask)
    # min-max normalized
    u0, u1 = uv[:, 0].min(), uv[:, 0].max()
    v0, v1 = uv[:, 1].min(), uv[:, 1].max()
    nn = np.column_stack([(uv[:, 0] - u0) / (u1 - u0) * W,
                          (uv[:, 1] - v0) / (v1 - v0) * H])
    out["minmax_norm"] = fill_iou(nn, tris, mask)
    return out, len(uv), len(tris), att.get("hull")


def run(parts_dir, award_path, budget=64, iou_margin=0.02, credibility_thresh=0.85):
    sk = json.load(open(award_path))
    rows = []
    for p in PARTS:
        png = os.path.join(parts_dir, p["png"])
        mask = load_mask(png)

        # --- S3 生成 ---
        mesh = gen_v2(png, mode="auto")
        nv = len(mesh["uvs"]) // 2
        ev = evaluate(mesh, mask, vertex_budget=budget)
        gen_iou = ev["criteria"]["AC1_iou"]["value"]
        fmt_ok = ev["criteria"]["AC4_format"]["pass"]
        degen = ev["criteria"]["AC2b_degenerate"]["value"]
        orphan = ev["criteria"]["AC2c_orphans"]["value"]

        # --- 藝術家 baseline + 評估器可信度自檢 ---
        att = artist_attachment(sk, p["slot"])
        variants, a_nv, a_tris, a_hull = artist_iou_variants(att, mask)
        best_frame = max(variants, key=variants.get)
        base = variants[best_frame]
        credible = base >= credibility_thresh

        cov_pass = gen_iou >= base - iou_margin
        topo_pass = fmt_ok and degen == 0 and orphan == 0
        budget_pass = nv <= budget
        overall = credible and cov_pass and topo_pass and budget_pass

        rows.append({
            "part": p["key"], "slot": p["slot"], "mask_wh": [int(mask.shape[1]), int(mask.shape[0])],
            "generated": {"mode": mesh.get("_mode"), "verts": nv, "tris": len(mesh["triangles"]) // 3,
                          "hull": mesh["hull"], "iou": round(gen_iou, 4),
                          "degenerate": degen, "orphans": orphan, "format_ok": fmt_ok},
            "artist": {"verts": a_nv, "tris": a_tris, "hull": a_hull,
                       "iou_variants": {k: round(v, 4) for k, v in variants.items()},
                       "baseline_frame": best_frame, "baseline_iou": round(base, 4)},
            "evaluator_credible": credible,
            "verts_ratio_gen_over_artist": round(nv / a_nv, 3),
            "AC_coverage": {"pass": cov_pass, "margin": iou_margin},
            "AC_topology": {"pass": topo_pass},
            "AC_budget": {"pass": budget_pass, "budget": budget},
            "overall_pass": overall,
        })
    return {"all_pass": all(r["overall_pass"] for r in rows),
            "deform_gate": "N/A — Award 這 5 件無 deform timeline(骨骼/權重變形)",
            "parts": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts-dir", default="/tmp/robot_parts")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--budget", type=int, default=64)
    a = ap.parse_args()
    rep = run(a.parts_dir, a.award, budget=a.budget)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["all_pass"] else 1)


if __name__ == "__main__":
    main()
