#!/usr/bin/env python3
"""端到端驗證:真實 PSD 件 → S3 v2 mesh → 對照 Award 真實生產 mesh。

背景(見 knowledge/s4-psd-to-spine-real.md):`robot_parts.psd` 的 5 件與生產 spine
`Award.json` 的 slot `機器人拆件/<圖層名>` 逐件吻合。其中 3 件(光暈/身體/左手)在 Award
是 **weighted mesh**(骨骼權重變形,**無 deform timeline**);另 2 件(右手/頭)是旋轉 region。

本工具對 3 個 mesh 件:
  psd_slice 切件 alpha → generate_mesh_v2 → ① 生成 mesh 對件 alpha 的覆蓋 IoU
  ② Award 藝術家 mesh 對同一 alpha 的覆蓋 IoU(baseline)③ 頂點/拓樸對照。

AC(可自評):生成 mesh 覆蓋 IoU >= 藝術家 baseline - margin。
→ 端到端「PSD → 件 → S3 mesh」對真實生產標的的覆蓋率驗收。

注意:這 3 件在 Award 無 deform timeline(bone-weighted),故**不套 deform 閘**
(deform 閘需真實逐頂點位移場;此處相關的品質閘是靜態覆蓋率)。y 軸取向自動對齊
(Award mesh uvs 為 region-local 0..1;PSD 件 alpha 為影像座標 y-down,兩者可能差一個
上下翻轉,本工具兩種取向都算,取較高者並記錄)。
"""
import argparse, json, sys, os
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2


def mesh_iou(uvs, tris, mask, flip_y=False):
    """把 mesh(region-local uvs 0..1)貼回件 alpha mask,算覆蓋 IoU。"""
    H, W = mask.shape
    u = uvs.copy()
    if flip_y:
        u = u.copy(); u[:, 1] = 1.0 - u[:, 1]
    rp = np.column_stack([u[:, 0] * W, u[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0


def load_piece_mask(png_path):
    img = cv2.imread(png_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"讀不到 {png_path}")
    alpha = img[:, :, 3] if (img.ndim == 3 and img.shape[2] == 4) else \
        (cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) > 0).astype(np.uint8) * 255
    return (alpha > 8).astype(np.uint8)


def award_mesh(award_json, slot, name):
    sk = json.load(open(award_json))
    skins = sk["skins"]; skin = skins[0] if isinstance(skins, list) else skins
    a = skin.get("attachments", skin)[slot][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    weighted = len(a["vertices"]) != len(a["uvs"])
    return uvs, tris, {"vertices": len(uvs), "triangles": len(tris),
                       "hull": a.get("hull"), "weighted": weighted,
                       "w": a.get("width"), "h": a.get("height")}


def best_iou(uvs, tris, mask):
    """兩種 y 取向都算,取較高者(對齊 region↔件 的上下慣例)。"""
    i0 = mesh_iou(uvs, tris, mask, flip_y=False)
    i1 = mesh_iou(uvs, tris, mask, flip_y=True)
    return (i0, "as-is") if i0 >= i1 else (i1, "flip_y")


def validate_piece(png_path, award_json, slot, name, iou_margin=0.02):
    mask = load_piece_mask(png_path)
    # 生成 mesh(v2 auto)
    gm = gen_v2(png_path, mode="auto")
    guvs = np.array(gm["uvs"]).reshape(-1, 2)
    gtris = np.array(gm["triangles"]).reshape(-1, 3)
    gen_iou, gen_orient = best_iou(guvs, gtris, mask)
    # Award 藝術家 mesh baseline
    auvs, atris, ainfo = award_mesh(award_json, slot, name)
    art_iou, art_orient = best_iou(auvs, atris, mask)
    return {
        "piece": os.path.basename(png_path),
        "mask_size": [int(mask.shape[1]), int(mask.shape[0])],
        "generated": {"mode": gm.get("_mode"), "vertices": len(guvs),
                      "triangles": len(gtris), "hull": gm["hull"],
                      "iou": round(gen_iou, 4), "orient": gen_orient},
        "award_artist": {"vertices": ainfo["vertices"], "triangles": ainfo["triangles"],
                         "hull": ainfo["hull"], "weighted": ainfo["weighted"],
                         "iou": round(art_iou, 4), "orient": art_orient,
                         "region_wh": [ainfo["w"], ainfo["h"]]},
        "AC_coverage": {"gen_iou": round(gen_iou, 4),
                        "artist_baseline": round(art_iou, 4),
                        "margin": iou_margin,
                        "pass": gen_iou >= art_iou - iou_margin},
        "overall_pass": gen_iou >= art_iou - iou_margin,
    }


# robot_parts.psd 的 3 個 mesh 件 → Award slot 對映
MESH_PIECES = [
    ("00_光暈.png", "機器人拆件/光暈", "機器人拆件/光暈"),
    ("03_身體.png", "機器人拆件/身體", "機器人拆件/身體"),
    ("04_左手.png", "機器人拆件/左手", "機器人拆件/左手"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts-dir", default="/tmp/robot_parts")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    reports = []
    for fn, slot, name in MESH_PIECES:
        p = os.path.join(a.parts_dir, fn)
        reports.append(validate_piece(p, a.award, slot, name, a.margin))
    out = {"pieces": reports,
           "overall_pass": all(r["overall_pass"] for r in reports)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["overall_pass"] else 1)


if __name__ == "__main__":
    main()
