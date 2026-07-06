#!/usr/bin/env python3
"""S3+S4 端到端 AC — 從「真實生產 PSD 件」生成 mesh,對照「真實生產 spine mesh」。

動機(STATE 下一步 #1,最高優先:有真值可比):
  之前 S3 的 mesh 品質都對 main_draw 的 4 個窗簾/陰影 mesh 驗;那些是 unweighted、
  有 deform timeline。這裡改用**另一條真實 pipeline**:機器人拆件 PSD(robot_parts.psd)
  → S4 切件 → S3 generate_mesh_v2 → 對照 Award.json 裡對應的生產 mesh(weighted、無 deform)。
  這把 S4(PSD 切圖)與 S3(mesh 生成)串成端到端,並用**第二組獨立真實真值**檢驗 S3。

方法論重點(避免評估器 miscalibration,前有三次教訓):
  * 「mesh 覆蓋率」一律定義為 **mesh 三角形填充區 IoU 它所依據的真實 alpha 輪廓**。
  * 生成 mesh:在「PSD 切件的直立局部像素座標」量(mesh uvs↔切件像素,無旋轉歧義)。
  * 藝術家 mesh:**完全在 atlas 頁像素空間量**(uv×pageWH → 頁像素;輪廓取同頁 alpha)。
    兩者同處 atlas 頁座標系,含 rotate:true 也自洽,**不需任何 derotate/對齊**,消除旋轉誤差。
  * 兩個數字都是「mesh 蓋住自己真實輪廓的緊密度」,可公平對比:AC = 生成 ≥ 藝術家 − margin。

deform 閘:機器人這 5 件在 Award **無 deform timeline**(靠骨骼權重變形),故無逐頂點位移場
  可轉移 → 本 AC 只做靜態幾何(覆蓋/拓樸/預算)。這點已記於 knowledge/s4-psd-to-spine-real.md。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_mesh
from atlas_crop import parse_atlas, crop_region


def artist_mesh_coverage(atlas_path, region, attach):
    """藝術家 mesh 覆蓋其真實 alpha 輪廓的 IoU,完全自洽、免旋轉猜測。

    關鍵(2026-07-06 實測):Award 的 mesh uvs 是**region-local [0,1]**(非 atlas 頁 uv),
    且對應**直立(de-rotated)**方向。故:輪廓取 atlas_crop.crop_region(已 CW derotate,
    經 PSD 真值校正),mesh 用 uv×(cropW,cropH) 直接光柵化 —— 兩者同處直立 region 局部座標系,
    含 rotate:true 也 IoU 0.98(免翻轉/derotate 對齊)。此即「藝術家 mesh 蓋住自己輪廓的緊密度」。"""
    page = region["page"]
    sheet = cv2.imread(os.path.join(os.path.dirname(atlas_path), page), cv2.IMREAD_UNCHANGED)
    crop = crop_region(sheet, region)          # 直立 de-rotated region(CW)
    H, W = crop.shape[:2]
    alpha = (crop[:, :, 3] > 8).astype(np.uint8)
    uv = np.array(attach["uvs"]).reshape(-1, 2)
    px = np.column_stack([uv[:, 0] * (W - 1), uv[:, 1] * (H - 1)])
    raster = np.zeros((H, W), np.uint8)
    for t in np.array(attach["triangles"]).reshape(-1, 3):
        cv2.fillConvexPoly(raster, np.round(px[t]).astype(np.int32), 1)
    inter = int(np.logical_and(raster, alpha).sum())
    union = int(np.logical_or(raster, alpha).sum())
    return {
        "iou": round(inter / union, 4) if union else 0.0,
        "vertices": len(uv), "hull": attach["hull"],
        "triangles": len(attach["triangles"]) // 3,
        "weighted": len(attach["vertices"]) != len(attach["uvs"]),
    }


def validate_piece(psd_parts, atlas_path, skeleton, slot, layer_name, tmp_dir, iou_margin=0.03):
    # 1) 取 PSD 切件(依圖層名)
    entry_im = None
    for entry, im in psd_parts:
        if entry["name"] == layer_name:
            entry_im = (entry, im); break
    if entry_im is None:
        raise SystemExit(f"PSD 無此圖層: {layer_name}")
    entry, im = entry_im
    crop = os.path.join(tmp_dir, f"_piece_{entry['z']:02d}.png")
    im.save(crop)

    # 2) 生成 mesh(v2 auto)+ 靜態評估(對切件 alpha)
    mesh = gen_v2(crop, mode="auto")
    a = np.array(im.split()[-1] if hasattr(im, "split") else None)
    mask = (np.array(im)[:, :, 3] > 8).astype(np.uint8)
    ev = eval_mesh(mesh, mask)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]

    # 3) 藝術家真值 mesh 覆蓋率(atlas 頁空間,自洽)
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)[slot]
    aname = list(att.keys())[0]
    regions = parse_atlas(atlas_path)
    art = artist_mesh_coverage(atlas_path, regions[slot], att[aname])

    passed = gen_iou >= art["iou"] - iou_margin
    return {
        "layer": layer_name, "slot": slot,
        "generated": {"mode": mesh.get("_mode"), "vertices": len(mesh["uvs"]) // 2,
                       "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3,
                       "iou_vs_piece": gen_iou,
                       "static_pass": ev["overall_pass"]},
        "artist": {"vertices": art["vertices"], "hull": art["hull"],
                   "triangles": art["triangles"], "weighted": art["weighted"],
                   "iou_vs_silhouette": art["iou"]},
        "AC_coverage": {"pass": bool(passed), "margin": iou_margin,
                        "generated": gen_iou, "artist_baseline": art["iou"]},
    }


# 機器人拆件:PSD 圖層名 → Award slot,只取 mesh 型的三件(見 s4-psd-to-spine-real.md)
MESH_PIECES = [("光暈", "機器人拆件/光暈"),
               ("身體", "機器人拆件/身體"),
               ("左手", "機器人拆件/左手")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--margin", type=float, default=0.03)
    a = ap.parse_args()

    _, _, parts = slice_psd(a.psd)
    sk = json.load(open(a.skeleton))
    reports = []
    for layer, slot in MESH_PIECES:
        reports.append(validate_piece(parts, a.atlas, sk, slot, layer, a.tmp, a.margin))
    overall = all(r["AC_coverage"]["pass"] and r["generated"]["static_pass"] for r in reports)
    out = {"overall_pass": overall, "pieces": reports}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
