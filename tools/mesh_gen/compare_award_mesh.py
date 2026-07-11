#!/usr/bin/env python3
"""端到端 S3+S4:PSD 件 → generate_mesh_v2 → 對照 Award 真實生產 mesh。

背景(見 knowledge/s4-psd-to-spine-real.md):Award 中 3 個機器人件是 mesh —
光暈(78v/hull78)、身體(98v/154t/hull40)、左手(80v/116t/hull42),皆 **weighted 且無
deform timeline**(靠骨骼/權重變形,非逐頂點 deform)。因此本比對不做 deform 轉移閘(不適用),
改做「拓樸 + 輪廓覆蓋率」對照:

  ① 從 robot_parts.psd 切出各件緊湊 RGBA(psd_slice,已驗 = spine 生產素材)。
  ② generate_mesh_v2(mode=auto)生成 mesh + evaluate_mesh 量化(IoU/退化/孤兒/預算)。
  ③ 從 Award 真實 mesh 的 uvs+triangles 算「藝術家覆蓋率」(同一 mask,同 uv→pixel 映射)。
  ④ AC:生成 mesh 有效(0 退化/0 孤兒/hull 閉合)且覆蓋率 IoU ≥ 藝術家自身覆蓋率 - margin。

Award mesh uvs 已是 region-local(~0..1,見腳本量測),故直接 uv*(W,H) 落回件像素空間比對。
"""
import argparse, json, os, sys
import numpy as np
import cv2
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate

# PSD 件檔名 → Award slot（同一素材）
PIECES = [
    ("00_光暈.png", "機器人拆件/光暈"),
    ("03_身體.png", "機器人拆件/身體"),
    ("04_左手.png", "機器人拆件/左手"),
]


def piece_mask(png_path):
    im = np.array(Image.open(png_path).convert("RGBA"))
    return (im[:, :, 3] > 8).astype(np.uint8)


def award_attachment(sk, slot):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)[slot]
    return list(att.values())[0]


def coverage_iou(uvs, tris, mask):
    """把 (uv*W, uv*H) 三角形填滿 vs alpha mask,算 IoU 覆蓋率。"""
    H, W = mask.shape
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    return inter / union if union else 0.0


def compare(pieces_dir, award_path, iou_margin=0.02, tmp_dir="/tmp"):
    sk = json.load(open(award_path))
    rows = []
    for fname, slot in PIECES:
        png = os.path.join(pieces_dir, fname)
        mask = piece_mask(png)
        H, W = mask.shape

        # ① 生成 mesh(對件緊湊 PNG)
        mesh = gen_v2(png, mode="auto")
        ev = evaluate(mesh, mask, vertex_budget=64)
        gen_iou = ev["criteria"]["AC1_iou"]["value"]

        # ② 藝術家真實 mesh 覆蓋率(同 mask)
        a = award_attachment(sk, slot)
        auv = np.array(a["uvs"]).reshape(-1, 2)
        atris = np.array(a["triangles"]).reshape(-1, 3)
        art_iou = round(coverage_iou(auv, atris, mask), 4)
        art_nv = len(a["uvs"]) // 2

        valid = (ev["criteria"]["AC2b_degenerate"]["pass"] and
                 ev["criteria"]["AC2c_orphans"]["pass"] and
                 ev["criteria"]["AC4_format"]["pass"] and
                 ev["criteria"]["AC3_vertex_budget"]["pass"])
        iou_ok = gen_iou >= art_iou - iou_margin
        rows.append({
            "slot": slot, "piece_px": [W, H],
            "gen": {"mode": mesh.get("_mode"), "vertices": ev["vertices"],
                    "triangles": ev["triangles"], "hull": ev["hull"], "iou": gen_iou},
            "artist": {"vertices": art_nv, "triangles": len(atris), "hull": a.get("hull"),
                       "coverage_iou": art_iou},
            "mesh_valid": bool(valid),
            "iou_vs_artist_pass": bool(iou_ok),
            "overall_pass": bool(valid and iou_ok),
            "_eval_detail": {k: v for k, v in ev["criteria"].items()},
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pieces", default="/tmp/robot_pieces")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--iou-margin", type=float, default=0.02)
    a = ap.parse_args()
    rep = compare(a.pieces, a.award, a.iou_margin)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all(r["overall_pass"] for r in rep) else 1)


if __name__ == "__main__":
    main()
