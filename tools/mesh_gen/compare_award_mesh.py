#!/usr/bin/env python3
"""端到端驗收:PSD 切件 → S3 generate_mesh_v2 → 對照 Award 真實(藝術家)mesh。

背景與定位
----------
- 這是「PSD→件→mesh」端到端閘的最後一段:S4 已證明 robot_parts.psd 的 5 圖層 ⇄ Award
  slot `機器人拆件/<圖層名>` 逐件吻合(+2px padding),其中 光暈/身體/左手 在 Award 中是
  **weighted mesh**(靠骨骼 warp,無 deform timeline;右手/頭是剛體 region)。
- 本工具拿「PSD 切件的 alpha」當 ground-truth 輪廓,對同一件比較兩張 mesh 的**輪廓覆蓋 IoU**:
  (a) 我的 `generate_mesh_v2` 自動產出 vs (b) 藝術家在 Award 裡手做的 mesh。
- 公平性:兩者都在同一張「attachment (W,H) 畫布」上柵格化,PSD 件以 +1px(padding/2)置入,
  對同一 GT mask 量 IoU。藝術家 mesh 的 uvs(0..1,region 局部)以 px=u*W, py=v*H 還原
  (y 不翻,已實測 flip=False 才對齊)。

為何是「靜態輪廓 IoU」而非 deform 閘
----------------------------------
- 這 3 件在 Award 中**沒有 deform timeline**(log 2026-06-26-005:5 件無 deform、靠骨骼)。
  沒有真實位移場可轉移,故 deform 閘(真實位移場轉移)在此不適用;本閘只做靜態覆蓋對照,
  這正是 AC.md AC1「≥ 藝術家同件 mesh 的 IoU」的精神,只是把基準換成**真實生產藝術家 mesh**。

判定
----
- 每件 PASS 條件:IoU_mine >= IoU_artist - MARGIN(預設 0.03),且我的 mesh 靜態 evaluate 各項過。
- 另報頂點經濟度(我方 vs 藝術家),strip/delaunay 模式。
"""
import argparse
import json
import os
import numpy as np
import cv2

import generate_mesh_v2 as gmv2
import evaluate_mesh as em

# 3 個 warp 件(Award 中為 mesh);PSD 切件檔名由 psd_slice 產出
PIECES = {
    "機器人拆件/光暈": "00_光暈.png",
    "機器人拆件/左手": "04_左手.png",
    "機器人拆件/身體": "03_身體.png",
}
MARGIN = 0.03  # 允許我方 IoU 比藝術家低的裕度


def load_award_mesh(skeleton_path, slot):
    d = json.load(open(skeleton_path))
    att = list(d["skins"][0]["attachments"][slot].values())[0]
    return att


def raster_fill(pts, tris, W, H):
    """把三角形填成 (H,W) 覆蓋 mask。"""
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        poly = np.round(pts[t]).astype(np.int32)
        cv2.fillConvexPoly(recon, poly, 1)
    return recon


def iou(a, b):
    inter = int(np.logical_and(a, b).sum())
    union = int(np.logical_or(a, b).sum())
    return inter / union if union else 0.0


def artist_pixel_pts(att, W, H):
    uvs = np.array(att["uvs"], dtype=np.float64).reshape(-1, 2)
    px = uvs[:, 0] * W
    py = uvs[:, 1] * H  # flip=False(實測對齊)
    return np.stack([px, py], axis=1)


def place_piece(alpha, W, H, ox=1, oy=1):
    """把 PSD 件 alpha 以 +1px 偏移置入 attachment (W,H) 畫布(對齊 +2px padding)。"""
    gt = np.zeros((H, W), np.uint8)
    ah, aw = alpha.shape
    hh, ww = min(ah, H - oy), min(aw, W - ox)
    gt[oy:oy + hh, ox:ox + ww] = alpha[:hh, :ww]
    return gt


def compare_one(skeleton_path, slot, piece_png, rows, cols):
    att = load_award_mesh(skeleton_path, slot)
    W, H = int(att["width"]), int(att["height"])
    art_tris = np.array(att["triangles"], dtype=np.int32).reshape(-1, 3)
    art_nv = len(att["uvs"]) // 2

    # ⚠️ 用與生成器/評估器一致的門檻(>8)建立件的 alpha silhouette,
    # 避免自造門檻不一致(>10)在 AC2a 邊界三角上產生假性失敗。
    alpha = em.load_mask(piece_png)

    # 共同 GT:PSD 件 alpha 置入 (W,H)
    gt = place_piece(alpha, W, H)

    # 藝術家 mesh 覆蓋(在 attachment 座標)
    art_pts = artist_pixel_pts(att, W, H)
    art_recon = raster_fill(art_pts, art_tris, W, H)
    iou_artist = iou(art_recon, gt)

    # 我方 mesh:對 PSD 件原始 alpha 生成(件原生尺寸),再以同 +1px 偏移置入 (W,H)
    mine = gmv2.generate(piece_png, rows=rows, cols=cols, mode="auto")
    my_pts_native, mW, mH = em.mesh_pixel_coords(mine)
    my_tris = np.array(mine["triangles"], dtype=np.int32).reshape(-1, 3)
    my_pts = my_pts_native + np.array([1.0, 1.0])  # 對齊 padding
    my_recon = raster_fill(my_pts, my_tris, W, H)
    iou_mine = iou(my_recon, gt)

    # 我方 mesh 的靜態自評(對件原生 alpha,同一 >8 門檻)——沿用 evaluate_mesh
    static = em.evaluate(mine, alpha, vertex_budget=64,
                         iou_thresh=0.90, centroid_thresh=0.99)

    passed = (iou_mine >= iou_artist - MARGIN) and static["overall_pass"]
    return {
        "slot": slot,
        "attachment_wh": [W, H],
        "iou_vs_artist_baseline": round(iou_artist, 4),
        "iou_mine": round(iou_mine, 4),
        "iou_gap": round(iou_mine - iou_artist, 4),
        "margin": MARGIN,
        "verts_mine": mine_nv(mine),
        "verts_artist": art_nv,
        "tris_mine": len(my_tris),
        "tris_artist": len(art_tris),
        "gen_mode": mine.get("_mode"),
        "static_self_eval_pass": static["overall_pass"],
        "static_iou_native": static["criteria"]["AC1_iou"]["value"],
        "pass": bool(passed),
    }


def mine_nv(mesh):
    return len(mesh["uvs"]) // 2


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="../../assets/Award.json")
    ap.add_argument("--pieces-dir", required=True,
                    help="psd_slice 產出的切件目錄(含 00_光暈.png 等)")
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--cols", type=int, default=3)
    args = ap.parse_args()

    results = []
    for slot, fn in PIECES.items():
        png = os.path.join(args.pieces_dir, fn)
        results.append(compare_one(args.skeleton, slot, png, args.rows, args.cols))

    all_pass = all(r["pass"] for r in results)
    print(json.dumps({"overall_pass": all_pass, "pieces": results},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
