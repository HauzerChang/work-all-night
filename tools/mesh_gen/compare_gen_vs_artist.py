#!/usr/bin/env python3
"""端到端「PSD/atlas 件 → S3 生成 mesh → 對照 Award 真實藝術家 mesh」幾何驗收。

背景(knowledge/s4-psd-to-spine-real.md):Award 生產 spine 有 3 個機器人 mesh 件
(光暈/身體/左手)。本工具對這 3 件的真實 atlas 貼圖跑 S3 `generate_mesh_v2`,
在**同一個 raw packed atlas-region 幀**裡把生成 mesh 與藝術家 mesh 的覆蓋率(coverage IoU)
與拓樸(頂點/三角/hull 數)做並排比對。

關鍵(2026-08-03 實測校正):Spine JSON 的 mesh `uvs` 是**該件來源圖的局部 [0,1]**
座標(runtime `AtlasAttachmentLoader.updateUVs` 載入時才 remap 進 atlas region),**不是**
atlas page 座標。故藝術家與生成 mesh 同處一個局部 [0,1] 幀:兩者都用 `atlas_crop.extract`
的**去旋轉 upright 件圖**,以 `(u*W, v*H)` 映射,coverage IoU 直接可比。
藝術家 mesh 對自身 alpha 的覆蓋率(baseline)同時是 **mapping 正確性的自我檢查**:
映射/翻轉錯 → baseline 會崩到極低(初版誤把 uvs 當 page-space,baseline 崩到 0.0~0.54 被抓到)。

⚠️ 限界(誠實記錄):這 3 件在 Award 是 **weighted mesh 且無 deform timeline**
(靠骨骼權重變形,非逐頂點 deform)。S3 生成器產出的是 **unweighted、deform 導向** 的 mesh。
故:(a) 真實 deform 閘 N/A(無真實位移場,拒絕用未校準合成場);(b) 本次只驗**幾何層**
(covering + 拓樸精簡度),weighting(BBW)是下一個明確缺口。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from generate_mesh_v2 import generate as gen_v2


def rasterize_coverage(px, tris, W, H, alpha):
    """把 (px Nx2 像素座標, tris Mx3) 三角化填滿 → 與 alpha(bool)算 IoU。"""
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        poly = np.round(px[t]).astype(np.int32)
        cv2.fillConvexPoly(recon, poly, 1)
    inter = np.logical_and(recon, alpha).sum()
    union = np.logical_or(recon, alpha).sum()
    return float(inter / union) if union else 0.0


def artist_mesh(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    return uvs, tris, int(a.get("hull", 0))


def compare(skeleton_path, atlas_path, png_path, slot, name, tmp_dir):
    sk = json.load(open(skeleton_path))

    # 去旋轉 upright 件圖(atlas_crop.extract 已用 PSD 外部真值校 CW 方向)
    crop = extract(atlas_path, png_path, name)
    H, W = crop.shape[:2]
    alpha = (crop[:, :, 3] > 8) if crop.ndim == 3 and crop.shape[2] == 4 \
        else (cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) > 0)

    # 藝術家 mesh:uvs 為來源圖局部 [0,1] → (u*W, v*H)
    a_uv, a_tri, a_hull = artist_mesh(sk, slot, name)
    a_px = np.column_stack([a_uv[:, 0] * W, a_uv[:, 1] * H])
    artist_iou = rasterize_coverage(a_px, a_tri, W, H, alpha)

    # 生成 mesh(從同一去旋轉件圖)
    crop_png = os.path.join(tmp_dir, "_crop.png")
    cv2.imwrite(crop_png, crop)
    gen = gen_v2(crop_png, mode="auto")
    g_uv = np.array(gen["uvs"]).reshape(-1, 2)
    g_px = np.column_stack([g_uv[:, 0] * W, g_uv[:, 1] * H])
    g_tri = np.array(gen["triangles"]).reshape(-1, 3)
    gen_iou = rasterize_coverage(g_px, g_tri, W, H, alpha)

    return {
        "piece": name,
        "crop_wh": [W, H],
        "aspect": round(H / W, 3),
        "artist": {"vertices": len(a_uv), "triangles": len(a_tri), "hull": a_hull,
                   "coverage_iou": round(artist_iou, 4)},
        "generated": {"mode": gen.get("_mode"), "vertices": len(g_uv),
                      "triangles": len(g_tri), "hull": gen["hull"],
                      "coverage_iou": round(gen_iou, 4)},
        "mapping_ok": artist_iou >= 0.80,          # 自我檢查:映射正確藝術家應高覆蓋
        "cover_pass": gen_iou >= artist_iou - 0.03,  # 生成覆蓋 ≥ 藝術家(容差 3%)
        "deform_gate": "N/A (weighted mesh, no deform timeline in Award)",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png",
                    help="fallback page;extract 會依 region 的 page 屬性自動選頁")
    ap.add_argument("--slot", default=None, help="單件;省略則跑全部 3 mesh 件")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    pieces = [a.slot] if a.slot else [
        "機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]
    reps = [compare(a.skeleton, a.atlas, a.png, p, p, a.tmp) for p in pieces]
    ok = all(r["mapping_ok"] and r["cover_pass"] for r in reps)
    print(json.dumps({"pieces": reps,
                      "all_mapping_ok": all(r["mapping_ok"] for r in reps),
                      "all_cover_pass": all(r["cover_pass"] for r in reps),
                      "overall_pass": ok}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
