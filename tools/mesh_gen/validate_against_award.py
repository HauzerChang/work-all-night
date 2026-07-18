#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 generate_mesh_v2 → 對照 Award 生產 spine 的真實 mesh。

與 validate_against_real(main_draw 窗簾/陰影)的差異:
  - main_draw 的 4 mesh 是 **unweighted + 有 deform timeline**(逐頂點變形)→ 用真實位移場閘。
  - Award 機器人拆件的 3 個 mesh(光暈/身體/左手)是 **weighted + 無 deform timeline**
    (靠骨骼/權重變形)→ **deform 位移場閘 N/A**(已確認這些 slot 無 deform)。
    且形狀為團塊(aspect<1.2)→ v2 auto 回退 v1 Delaunay。
  → 這裡的可驗收指標是 **靜態覆蓋保真**:同一張 alpha 上,生成 mesh 的覆蓋 IoU
    是否 ≥ 藝術家 mesh 的覆蓋 IoU(-margin);外加格式合法 + 頂點預算 + 0 退化/孤兒。

輸入來源 = PSD 切件(端到端從 PSD 出發),對照真值 = Award.json 的 mesh attachment。
兩者疊在同一張「PSD 件 alpha」的像素框比較,隔離「拓樸覆蓋品質」這一維(材質同源已於
knowledge/s4-psd-to-spine-real.md 用 alpha-IoU 0.92~0.99 確認)。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask
from psd_slice import slice_psd

# PSD 圖層名 → Award slot(ground truth,見 knowledge/s4-psd-to-spine-real.md)
ROBOT_MESH_SLOTS = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def award_mesh(sk, slot):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)[slot]
    name = list(att)[0]
    a = att[name]
    return name, a


def coverage_iou(uvs, tris, mask):
    """把 mesh 三角形依 uvs 填進 mask 像素框,算與 alpha 的覆蓋 IoU。"""
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    union = int(np.logical_or(recon, m).sum())
    return float(np.logical_and(recon, m).sum() / union) if union else 0.0


def validate_part(part_png, sk, slot, budget=128, iou_margin=0.02):
    mask = load_mask(part_png)
    gen = gen_v2(part_png, mode="auto")
    if isinstance(gen, tuple):
        gen = gen[0]
    ev = evaluate(gen, mask, vertex_budget=budget)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]

    aname, am = award_mesh(sk, slot)
    a_uvs = np.array(am["uvs"]).reshape(-1, 2)
    a_tris = np.array(am["triangles"]).reshape(-1, 3)
    art_iou = coverage_iou(a_uvs, a_tris, mask)

    fmt_ok = (ev["criteria"]["AC4_format"]["pass"]
              and ev["criteria"]["AC2b_degenerate"]["pass"]
              and ev["criteria"]["AC2c_orphans"]["pass"]
              and ev["criteria"]["AC3_vertex_budget"]["pass"])
    iou_ok = gen_iou >= art_iou - iou_margin
    return {
        "slot": slot,
        "gen": {"mode": gen.get("_mode"), "vertices": len(gen["uvs"]) // 2,
                "hull": gen["hull"], "triangles": len(gen["triangles"]) // 3,
                "coverage_iou": round(gen_iou, 4)},
        "artist": {"vertices": len(a_uvs), "hull": am.get("hull"),
                   "triangles": len(a_tris), "coverage_iou": round(art_iou, 4)},
        "AC_coverage": {"pass": iou_ok, "gen": round(gen_iou, 4),
                        "artist_baseline": round(art_iou, 4), "margin": iou_margin},
        "AC_format": {"pass": fmt_ok, "detail": {
            "format": ev["criteria"]["AC4_format"]["pass"],
            "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
            "orphans": ev["criteria"]["AC2c_orphans"]["value"],
            "vertex_budget": ev["criteria"]["AC3_vertex_budget"]["value"]}},
        "overall_pass": iou_ok and fmt_ok,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--parts_dir", default="/tmp/robot_parts")
    ap.add_argument("--budget", type=int, default=128)
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()

    _, manifest, _ = slice_psd(a.psd, a.parts_dir)
    by_name = {p["name"]: p for p in manifest["parts"]}
    sk = json.load(open(a.skeleton))

    reports = []
    for slot in ROBOT_MESH_SLOTS:
        layer = slot.split("/")[-1]
        if layer not in by_name:
            reports.append({"slot": slot, "error": f"PSD 無圖層 {layer}"}); continue
        part_png = os.path.join(a.parts_dir, by_name[layer]["file"])
        reports.append(validate_part(part_png, sk, slot, a.budget, a.margin))

    overall = all(r.get("overall_pass") for r in reports)
    print(json.dumps({"overall_pass": overall, "parts": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
