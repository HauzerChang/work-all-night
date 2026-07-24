#!/usr/bin/env python3
"""端到端閘:PSD 切件 → S3 mesh → 對照 Award 真實生產 mesh。

驗收「PSD→件→mesh」對真實標的(Award big win 機器人拆件)的靜態保真與頂點經濟:
  ① 靜態輪廓 IoU ≥ Award 藝術家同件 mesh 對相同 alpha 的覆蓋 IoU(基準)。
  ② 頂點/三角/hull 與藝術家比(經濟性)。
  ③ auto-refine:自動下修 Douglas-Peucker epsilon,直到 IoU ≥ 藝術家基準(在 vert 上限內)。

限制(誠實紀錄):Award 這 5 件是 **weighted mesh 且無 deform timeline**(靠骨骼權重變形,
非逐頂點 deform),故真實位移場轉移閘(deform_eval.transfer_deform_check)不適用 —— 本閘
只做「靜態輪廓 + 頂點經濟 + 拓樸」比對。變形穩健見 main_draw 4 unweighted mesh 的 v2 strip 結論。

用法:
  python3 tools/mesh_gen/compare_to_award.py            # 跑 3 個 mesh 件(需先 psd_slice)
  python3 tools/mesh_gen/compare_to_award.py --refine    # 對每件 auto-refine epsilon
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh import generate as gen_v1
from evaluate_mesh import evaluate, load_mask

# 機器人拆件的 3 個 mesh 件(PSD 圖層名 → psd_slice 切出的 PNG)。
DEFAULT_PARTS = {
    "光暈": "00_光暈.png",
    "身體": "03_身體.png",
    "左手": "04_左手.png",
}


def artist_coverage_iou(skeleton, slot, name, mask):
    """把 Award 藝術家 mesh 的 region-local uvs 渲染到件 mask 框,量它對相同 alpha 的覆蓋 IoU。"""
    sk0 = skeleton["skins"]
    sk0 = sk0[0] if isinstance(sk0, list) else sk0
    a = sk0.get("attachments", sk0)[slot][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    hull = a.get("hull")
    return (float(inter / union) if union else 0.0,
            {"verts": len(uvs), "hull": hull, "tris": len(tris), "weighted": True})


def gen_iou(path, mask, eps, max_interior=40):
    m, _ = gen_v1(path, max_interior=max_interior, epsilon_frac=eps)
    iou = evaluate(m, mask)["criteria"]["AC1_iou"]["value"]
    return m, iou


def refine_epsilon(path, mask, target, vert_cap=96,
                   ladder=(0.008, 0.006, 0.004, 0.003, 0.002, 0.0015, 0.001)):
    """由粗到細下修 epsilon,回傳第一個達到 target 且頂點在 cap 內的 mesh。"""
    best = None
    for eps in ladder:
        m, iou = gen_iou(path, mask, eps)
        nv = len(m["uvs"]) // 2
        if best is None or iou > best[2]:
            best = (m, eps, iou, nv)
        if iou >= target and nv <= vert_cap:
            return m, eps, iou, nv, True
    # 沒達標:回傳 IoU 最高者
    m, eps, iou, nv = best
    return m, eps, iou, nv, False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--parts-dir", default="/tmp/robot_parts")
    ap.add_argument("--slot-prefix", default="機器人拆件/")
    ap.add_argument("--eps", type=float, default=0.008, help="固定 epsilon(不 refine 時用)")
    ap.add_argument("--refine", action="store_true", help="auto-refine epsilon 到藝術家基準")
    ap.add_argument("--vert-cap", type=int, default=96)
    a = ap.parse_args()

    sk = json.load(open(a.skeleton))
    report, all_pass = {}, True
    for layer, fn in DEFAULT_PARTS.items():
        path = os.path.join(a.parts_dir, fn)
        if not os.path.exists(path):
            report[layer] = {"error": f"缺件 {path}(先跑 psd_slice)"}
            all_pass = False
            continue
        mask = load_mask(path)
        H, W = mask.shape
        slot = name = a.slot_prefix + layer
        art_iou, art = artist_coverage_iou(sk, slot, name, mask)

        if a.refine:
            m, eps, iou, nv, ok = refine_epsilon(path, mask, art_iou, a.vert_cap)
        else:
            m, iou = gen_iou(path, mask, a.eps)
            eps, nv, ok = a.eps, len(m["uvs"]) // 2, iou >= art_iou

        entry = {
            "mask_wh": [W, H],
            "generated": {"verts": nv, "hull": m["hull"],
                          "tris": len(m["triangles"]) // 3,
                          "epsilon": eps, "static_iou": round(iou, 4)},
            "artist": {**art, "coverage_iou": round(art_iou, 4)},
            "iou_pass_vs_artist": bool(iou >= art_iou),
            "verts_vs_artist": f"{nv} vs {art['verts']}",
        }
        report[layer] = entry
        all_pass = all_pass and entry["iou_pass_vs_artist"]

    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
