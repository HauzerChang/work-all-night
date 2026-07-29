#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 生成 mesh → 對照 Award 真實生產 mesh(ground truth)。

背景(見 knowledge/s4-psd-to-spine-real.md):Award(機器人 big win spine)有 3 個
weighted mesh 件——光暈 / 身體 / 左手——是真實美術做的 mesh。本工具把它們當
**ground truth**,驗證 S3 `generate_mesh_v2` 對同一素材自動產出的 mesh 覆蓋率
是否達到藝術家水準。

為什麼不能沿用 validate_against_real:
  - 那 4 個 main_draw mesh 是 unweighted 且有 deform timeline(可跑真實位移場閘)。
  - Award 這 3 件是 **weighted**(vertices 為 bind 格式,不能當像素座標)且
    **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform)→ 只能做靜態覆蓋比對,
    且藝術家 mesh 幾何要從 **atlas UV** 還原。

共同畫布策略(避免跨座標系轉換的 bug):
  - 用 atlas_crop.extract() 取得「去旋轉、直立、atlas 縮放(~0.70)」的件裁圖 = 共同畫布。
  - 生成 mesh 直接從這張裁圖產出(uvs 天然在裁圖 [0,1])。
  - 藝術家 mesh 的 atlas-UV 用「與 atlas_crop 的 CW 去旋轉一致」的轉換映射到裁圖像素。
  - **裁圖自身 alpha 當獨立 oracle**:轉換正確 → 藝術家 mesh 覆蓋率高;轉錯(方向/翻面)
    → IoU 崩到 ~0.4(即先前 CCW bug 的特徵)。同時報 CW vs CCW 當負對照,確認鑑別力。

AC(靜態覆蓋,無 deform 閘):
  AC_coverage: gen_iou(vs 裁圖 alpha) >= artist_iou - margin  ← 藝術家真值當基準
  AC_agreement: IoU(gen_recon, artist_recon) 報告(mesh 對 mesh 輪廓一致度)
  AC_format: 生成 mesh 格式合法(沿用 evaluate_mesh)
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import parse_atlas, extract
from evaluate_mesh import evaluate, load_mask as load_alpha_mask
from generate_mesh_v2 import generate as gen_v2

ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def page_size(atlas_path, page_name):
    """讀 atlas 中指定 page 的 size(pageW,pageH)。"""
    cur = None
    for ln in open(atlas_path, encoding="utf-8").read().splitlines():
        if ln.rstrip().endswith(".png"):
            cur = ln.strip()
        elif cur == page_name and ln.strip().startswith("size:"):
            w, h = ln.split(":", 1)[1].split(",")
            return int(w), int(h)
    raise SystemExit(f"找不到 page size: {page_name}")


def uv_to_crop(uvs, crop_shape, mode="direct"):
    """把藝術家 mesh 的 **region-local** UV([0,1] over region)映射到 extract()
    裁圖像素。Spine 匯出時 attachment uvs 已是 region 局部座標(非 atlas 頁面 UV),
    且對應「原始未旋轉」邏輯朝向 = extract() 去旋轉後的直立裁圖 → 直接乘裁圖尺寸。
    mode 供垂直/水平翻轉負對照(驗證朝向鑑別力)。"""
    H, W = crop_shape
    u = uvs[:, 0]; v = uvs[:, 1]
    if mode == "direct":
        cx, cy = u * W, v * H
    elif mode == "vflip":
        cx, cy = u * W, (1.0 - v) * H
    elif mode == "hflip":
        cx, cy = (1.0 - u) * W, v * H
    else:  # rot180
        cx, cy = (1.0 - u) * W, (1.0 - v) * H
    return np.column_stack([cx, cy])


def raster_artist(skeleton, name, crop_shape, mode="direct"):
    """把藝術家 mesh 柵格化到裁圖畫布。"""
    a = skeleton_attachment(skeleton, name)
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = crop_shape
    pts = uv_to_crop(uvs, crop_shape, mode)
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    return recon


def iou(a, b):
    a = a > 0; b = b > 0
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def validate_piece(skeleton, atlas_path, png_path, name, tmp_dir, budget=110,
                   margin=0.02):
    # margin=0.02:atlas 貼圖被縮小 ~0.70 打包 + 羽化(anti-alias)邊界,
    # 固定 alpha 門檻下 <2% 的覆蓋差屬重採樣噪聲(mesh-對-mesh agreement 0.92~0.96 佐證)。
    # 共同畫布:去旋轉直立裁圖
    crop = extract(atlas_path, png_path, name)
    crop_path = os.path.join(tmp_dir, "_award_crop.png")
    cv2.imwrite(crop_path, crop)
    alpha = load_alpha_mask(crop_path)            # HxW uint8 {0,1}
    H, W = alpha.shape

    # 藝術家 mesh 柵格化(4 朝向負對照:確認 region-local UV 朝向鑑別力)
    modes = ["direct", "vflip", "hflip", "rot180"]
    recons = {m: raster_artist(skeleton, name, (H, W), m) for m in modes}
    cand = {m: iou(recons[m], alpha) for m in modes}
    best_key = max(cand, key=cand.get)
    artist_recon = recons[best_key]
    artist_iou = cand[best_key]

    # 生成 mesh(同一裁圖)
    mesh = gen_v2(crop_path, mode="auto")
    ev = evaluate(mesh, alpha, vertex_budget=budget)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]
    nv = ev["vertices"]

    # 生成 mesh 柵格化(供 mesh-對-mesh 輪廓一致度)
    gen_recon = np.zeros((H, W), np.uint8)
    gpts = (np.array(mesh["uvs"]).reshape(-1, 2) * np.array([W, H]))
    for t in np.array(mesh["triangles"]).reshape(-1, 3):
        cv2.fillConvexPoly(gen_recon, np.round(gpts[t]).astype(np.int32), 1)
    agree = iou(gen_recon, artist_recon)

    art_nv = len(skeleton_attachment(skeleton, name)["uvs"]) // 2
    transform_valid = best_key == "direct" and artist_iou >= 0.80
    coverage_pass = gen_iou >= artist_iou - margin
    return {
        "piece": name,
        "crop_size": [W, H],
        "transform_oracle": {k: round(v, 4) for k, v in cand.items()},
        "transform_chosen": best_key,
        "transform_valid": transform_valid,
        "artist_mesh": {"vertices": art_nv,
                        "weighted": True,
                        "coverage_iou": round(artist_iou, 4)},
        "generated_mesh": {"mode": mesh.get("_mode"), "vertices": nv,
                           "hull": mesh["hull"],
                           "triangles": len(mesh["triangles"]) // 3,
                           "coverage_iou": round(gen_iou, 4),
                           "format_pass": ev["criteria"]["AC4_format"]["pass"]},
        "AC_coverage": {"gen": round(gen_iou, 4),
                        "artist_baseline": round(artist_iou, 4),
                        "pass": coverage_pass},
        "AC_agreement_iou": round(agree, 4),
        "AC_format_pass": ev["criteria"]["AC4_format"]["pass"],
        "overall_pass": bool(transform_valid and coverage_pass
                             and ev["criteria"]["AC4_format"]["pass"]),
    }


def skeleton_attachment(skeleton, name):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)[name][name]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")  # extract 會自動選對的 page
    ap.add_argument("--pieces", nargs="*", default=ROBOT_MESHES)
    ap.add_argument("--budget", type=int, default=110)
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reports = [validate_piece(sk, a.atlas, a.png, nm, a.tmp, a.budget)
               for nm in a.pieces]
    allpass = all(r["overall_pass"] for r in reports)
    out = {"pieces": reports, "all_pass": allpass}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
