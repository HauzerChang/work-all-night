#!/usr/bin/env python3
"""端到端 PSD→件→S3 mesh 對照 Award 真實 mesh(ground truth)。

對 Award 的 3 個 mesh 件(光暈/身體/左手):
  1. 從切出的 PSD 件 alpha 跑 generate_mesh_v2(S3);
  2. 從 Award.json 的 UV+triangles 還原「藝術家 mesh」到件-局部像素空間;
  3. 量化:各自對 alpha 的覆蓋 IoU、兩者互相 IoU、頂點經濟度。
評估器可信度:藝術家 mesh 對 alpha 的覆蓋 IoU 應該高(生產真值),當基準線。
"""
import sys, json, os
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/tools/mesh_gen")
sys.path.insert(0, "/home/user/work-all-night/tools/mesh_gen")
from generate_mesh_v2 import generate as gen_v2

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
AWARD = os.path.join(ROOT, "assets/Award.json")
PIECES = {  # slot -> sliced piece png
    "機器人拆件/光暈": "/tmp/robot_pieces/00_光暈.png",
    "機器人拆件/身體": "/tmp/robot_pieces/03_身體.png",
    "機器人拆件/左手": "/tmp/robot_pieces/04_左手.png",
}


def load_alpha(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    a = img[:, :, 3] if (img.ndim == 3 and img.shape[2] == 4) else \
        (cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if img.ndim == 3 else img)
    return (a > 8).astype(np.uint8), img.shape[1], img.shape[0]


def raster_tris(pts, tris, W, H):
    canvas = np.zeros((H, W), np.uint8)
    for t in tris:
        poly = np.round(pts[t]).astype(np.int32)
        cv2.fillConvexPoly(canvas, poly, 1)
    return canvas


def iou(a, b):
    inter = int(np.logical_and(a, b).sum())
    union = int(np.logical_or(a, b).sum())
    return inter / union if union else 0.0


def gen_pixel_coords(mesh):
    W, H = mesh["width"], mesh["height"]
    v = mesh["vertices"]
    return np.array([[v[i] + W / 2.0, H / 2.0 - v[i + 1]] for i in range(0, len(v), 2)]), W, H


def artist_pixel_coords(att, W, H, flip_y):
    uv = np.array(att["uvs"]).reshape(-1, 2)
    px = uv[:, 0] * W
    py = (1.0 - uv[:, 1]) * H if flip_y else uv[:, 1] * H
    return np.stack([px, py], axis=1)


award = {sk["name"]: sk for sk in json.load(open(AWARD))["skins"]}["default"]["attachments"]
report = {}
for slot, png in PIECES.items():
    mask, W, H = load_alpha(png)
    att = award[slot][slot]
    tris = np.array(att["triangles"], dtype=np.int32).reshape(-1, 3)

    # artist mesh: try both y orientations, correct one covers alpha well
    art = {}
    for flip in (False, True):
        pts = artist_pixel_coords(att, W, H, flip)
        recon = raster_tris(pts, tris, W, H)
        art[flip] = (pts, recon, iou(recon, mask))
    flip = max(art, key=lambda f: art[f][2])
    art_pts, art_recon, art_iou = art[flip]

    # generated mesh (S3 v2)
    mesh = gen_v2(png)
    gp, gW, gH = gen_pixel_coords(mesh)
    gen_recon = raster_tris(gp, np.array(mesh["triangles"]).reshape(-1, 3), gW, gH)
    gen_iou = iou(gen_recon, mask)

    report[slot] = {
        "piece_px": [W, H],
        "artist": {"verts": len(art_pts), "tris": len(tris), "hull": att["hull"],
                   "cover_iou_vs_alpha": round(art_iou, 4), "uv_flip_y": flip},
        "generated_v2": {"verts": len(gp), "tris": len(mesh["triangles"]) // 3,
                         "hull": mesh["hull"], "mode": mesh.get("_mode"),
                         "cover_iou_vs_alpha": round(gen_iou, 4)},
        "mutual_iou_gen_vs_artist": round(iou(gen_recon, art_recon), 4),
        "vertex_ratio_gen_over_artist": round(len(gp) / len(art_pts), 3),
    }

print(json.dumps(report, ensure_ascii=False, indent=2))
