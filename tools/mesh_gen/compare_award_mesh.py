#!/usr/bin/env python3
"""S3×S4 端到端驗收 — PSD 切件 → generate_mesh_v2 → 對照 Award 真實生產 mesh。

目的:先前 S3 只對 main_draw 的 4 個 unweighted 窗簾/陰影 mesh 驗過。本工具把
S4(PSD 切件)與 S3(mesh 生成器)串起來,並用**真實生產標的**(機器人 big win
的 Award spine 中三個 weighted mesh:光暈/身體/左手)當外部真值,回答:

  「我們自動生成的 mesh,對真實不規則生產件的輪廓覆蓋,是否 ≥ 藝術家手做 mesh?
    頂點數是否更精簡?拓樸是否合理(strip vs delaunay auto 分流)?」

共同座標系 = **PSD 切件像素框**(全解析度,避開 atlas 0.70 縮小與旋轉):
  - 參考輪廓 = PSD 切件 alpha(已驗證與 spine 貼圖同素材,alpha-IoU 0.92~0.99)。
  - 藝術家 mesh 覆蓋 = 用 Award mesh 的 uvs(region-local [0,1])映到切件框 → 三角覆蓋。
  - 生成 mesh 覆蓋 = generate_mesh_v2(切件 alpha) 的三角覆蓋。
  - 兩者都對同一張切件 alpha 算 silhouette IoU → apples-to-apples。

自我校驗:藝術家 mesh 對切件 alpha 的 IoU 若高(>0.9),證明 uvs↔切件框對齊、
座標系一致、比較可信(否則報告 frame mismatch,不下判定)。

⚠️ 這三件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform),
故本輪只做**靜態輪廓保真 + 精簡度**;deform 閘(真實位移場轉移)對它們不適用。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2


def load_alpha(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"讀不到 {path}")
    if img.ndim == 3 and img.shape[2] == 4:
        a = img[:, :, 3]
    else:
        g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        a = (g > 0).astype(np.uint8) * 255
    return (a > 8).astype(np.uint8)


def raster_from_uv(uvs, tris, W, H):
    """uvs (region-local [0,1], shape (n,2)) + 三角索引 → 覆蓋遮罩 (H,W)。"""
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    cov = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(cov, np.round(pts[t]).astype(np.int32), 1)
    return cov


def iou(a, b):
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter / union) if union else 0.0


def artist_mesh(skel_path, slot):
    sk = json.load(open(skel_path))
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    a = att[slot][slot]  # attachment 名 == slot 名(機器人拆件/<圖層>)
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    return uvs, tris, a.get("hull"), a.get("width"), a.get("height")


def compare_one(piece_png, skel_path, slot, iou_margin=0.02):
    alpha = load_alpha(piece_png)
    H, W = alpha.shape

    # --- 藝術家真實 mesh ---
    a_uvs, a_tris, a_hull, a_W, a_H = artist_mesh(skel_path, slot)
    a_cov = raster_from_uv(a_uvs, a_tris, W, H)
    a_iou = iou(a_cov, alpha)
    a_nv = len(a_uvs)

    # --- 我們的生成 mesh(在切件框) ---
    g = gen_v2(piece_png)  # 預設 rows=10 cols=3 mode=auto
    g_uvs = np.array(g["uvs"]).reshape(-1, 2)  # 已 normalize 到切件 W,H
    g_tris = np.array(g["triangles"], dtype=np.int32).reshape(-1, 3)
    g_cov = raster_from_uv(g_uvs, g_tris, W, H)
    g_iou = iou(g_cov, alpha)
    g_nv = len(g_uvs)

    frame_ok = a_iou > 0.90  # 藝術家自身覆蓋要夠高才代表座標系對齊
    coverage_pass = g_iou >= (a_iou - iou_margin)

    return {
        "slot": slot,
        "piece_size": [int(W), int(H)],
        "artist": {"nv": a_nv, "hull": a_hull, "tris": len(a_tris), "iou": round(a_iou, 4)},
        "generated": {"nv": g_nv, "hull": g["hull"], "tris": len(g_tris),
                      "iou": round(g_iou, 4), "mode": g.get("_mode")},
        "frame_aligned(artist_iou>0.90)": frame_ok,
        "coverage_parity(gen>=artist-%.2f)" % iou_margin: coverage_pass,
        "vertex_frugal(gen<=artist)": g_nv <= a_nv,
    }


PIECES = {
    "光暈": "00_光暈.png",
    "身體": "03_身體.png",
    "左手": "04_左手.png",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pieces-dir", default="/tmp/robot_parts")
    ap.add_argument("--skel", default="assets/Award.json")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    results = []
    for cn, fn in PIECES.items():
        r = compare_one(os.path.join(a.pieces_dir, fn), a.skel,
                        "機器人拆件/" + cn, a.margin)
        results.append(r)
    print(json.dumps(results, ensure_ascii=False, indent=2))
    all_frame = all(r["frame_aligned(artist_iou>0.90)"] for r in results)
    all_cov = all(list(r.values())[5] for r in results)  # coverage_parity
    print("\n=== SUMMARY ===")
    for r in results:
        cov = list(r.values())[5]
        print(f"{r['slot']:16s} artist IoU {r['artist']['iou']:.3f} "
              f"({r['artist']['nv']}v) | gen[{r['generated']['mode']:>9s}] "
              f"IoU {r['generated']['iou']:.3f} ({r['generated']['nv']}v) | "
              f"frame_ok={r['frame_aligned(artist_iou>0.90)']} parity={cov}")
    print(f"\nframe_aligned(all)={all_frame}  coverage_parity(all)={all_cov}")


if __name__ == "__main__":
    main()
