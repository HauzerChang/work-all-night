#!/usr/bin/env python3
"""S3 端到端泛化驗證 — 對 Award「機器人拆件」真實 weighted mesh 做靜態覆蓋率對照。

目的(STATE 下一步 #1):把 generate_mesh_v2 從 main_draw 4 個 unweighted mesh
推廣到**另一份生產資產**(Award 機器人拆件)的真實 mesh,建立「不同美術、不同拓樸」
的外部真值對照 → 驗證 S3 生成器不是只在 main_draw 過擬合。

⚠️ Award 機器人 mesh 全為 **weighted**(vertices 為變長 bind 格式),
   `deform_eval` 的真實位移場閘(reshape(-1,2))對 weighted **不適用** → 本回合只做
   **靜態覆蓋率**(uvs 有效,weighted/unweighted 皆可)。weighted deform 閘列為後續 chunk。

比對法(apples-to-apples,同一 atlas region 為單一來源):
  atlas region(derotate)→ alpha mask
    ├─ 生成:generate_mesh_v2 → IoU_gen(mesh 三角填滿 ∩ mask)
    └─ 真值:artist uvs → IoU_artist(同法)
  pass ⇔ IoU_gen >= IoU_artist - margin(對齊藝術家覆蓋率,非武斷 0.95)。

rotate region 的 uv-frame 對齊亦在此回合驗證(見輸出 artist_iou;過低代表 uv 未隨 derotate)。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from evaluate_mesh import evaluate, load_mask
from atlas_crop import extract, parse_atlas
from generate_mesh_v2 import generate as gen_v2


def artist_uvs_tris(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uvs = np.array(a["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    weighted = len(a["vertices"]) != len(a["uvs"])
    return uvs, tris, weighted


def raster_iou(uvs, tris, mask, flip_y=False, swap_xy=False):
    """uvs(region-local [0,1])光柵化 vs mask,回傳 IoU。可選 y 翻轉 / xy 互換以測 rotate 對齊。"""
    H, W = mask.shape
    u = uvs.copy()
    if swap_xy:
        u = u[:, ::-1]
    x = u[:, 0] * W
    y = (1.0 - u[:, 1]) * H if flip_y else u[:, 1] * H
    rp = np.column_stack([x, y])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    return (inter / union if union else 0.0), recon


def best_artist_iou(uvs, tris, mask):
    """在 4 種 uv 取向(直/翻y × 直/swap)中取最高 IoU,回報是哪一種對齊。
    用於自動偵測 rotate region 的 uv frame,避免 90° 錯位假性低分。"""
    best = None
    for flip_y in (False, True):
        for swap in (False, True):
            iou, recon = raster_iou(uvs, tris, mask, flip_y, swap)
            tag = f"{'flipY' if flip_y else 'y'}/{'swapXY' if swap else 'xy'}"
            if best is None or iou > best[0]:
                best = (iou, tag, recon)
    return best


def validate(skeleton_path, atlas_path, png_path, slot, name, tmp_dir, iou_margin=0.03):
    sk = json.load(open(skeleton_path))
    sub = extract(atlas_path, png_path, name)
    crop = os.path.join(tmp_dir, "_robot_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    uvs, tris, weighted = artist_uvs_tris(sk, slot, name)
    art_iou, art_tag, _ = best_artist_iou(uvs, tris, mask)

    mesh = gen_v2(crop, mode="auto")
    nv = len(mesh["uvs"]) // 2
    gen_iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]

    return {
        "slot": slot,
        "source": {"region_px": [int(mask.shape[1]), int(mask.shape[0])],
                   "alpha_px": int(mask.sum())},
        "artist_mesh": {"weighted": weighted, "vertices": len(uvs),
                        "triangles": len(tris), "iou": round(art_iou, 4),
                        "uv_frame": art_tag},
        "generated_mesh": {"mode": mesh.get("_mode"), "vertices": nv,
                           "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3,
                           "iou": round(gen_iou, 4)},
        "AC_coverage": {"pass": gen_iou >= art_iou - iou_margin,
                        "margin": iou_margin,
                        "gap": round(gen_iou - art_iou, 4)},
    }


ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--slots", nargs="*", default=ROBOT_MESHES)
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    reports = []
    for s in a.slots:
        reports.append(validate(a.skeleton, a.atlas, a.png, s, s, a.tmp))
    overall = all(r["AC_coverage"]["pass"] for r in reports)
    out = {"overall_pass": overall, "n": len(reports), "meshes": reports}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
