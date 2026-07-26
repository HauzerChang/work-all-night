#!/usr/bin/env python3
"""端到端「PSD 件 → S3 生成 mesh → 對照 Award 真實 mesh」對照器。

背景(knowledge/s4-psd-to-spine-real.md):robot_parts.psd 的 光暈/身體/左手 3 件在生產 spine
`Award` 中為 mesh(其餘 右手/頭 為 region)。這 3 件在 Award **無 deform timeline → weighted
(骨骼/權重驅動)**,故 deform-transfer 閘(deform timeline)不適用;本器做**靜態 IoU + 拓樸對照**:

  ① 生成器對『件的 alpha』的覆蓋率 IoU(recon vs mask)
  ② Award 藝術家 mesh 對同一 alpha 的覆蓋率 IoU(真值基準)
  ③ 拓樸對照:頂點/hull/三角 數;生成 vs 藝術家。

判定:生成 IoU >= 藝術家基準 - margin(對齊藝術家覆蓋率,非武斷 0.95;沿用 validate_against_real 精神)。
註:Award region 有 +2px atlas padding、uvs 為 region 內 0..1,映射到件 alpha(小 2px)誤差 ~0.3%,可忽略。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from evaluate_mesh import evaluate, load_mask
from generate_mesh_v2 import generate as gen_v2


def artist_mesh(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[slot][name]


def poly_iou(uvs, tris, mask):
    """把 uv-space 三角形填滿(uvs*[W,H])與 alpha mask 求 IoU。"""
    H, W = mask.shape
    uvs = np.array(uvs).reshape(-1, 2)
    tris = np.array(tris).reshape(-1, 3)
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    return (inter / union) if union else 0.0


def compare(piece_png, sk, slot, name, mode="auto", margin=0.0, budget=128):
    mask = load_mask(piece_png)
    # ① 生成器
    mesh = gen_v2(piece_png, mode=mode)
    gen_iou = evaluate(mesh, mask, vertex_budget=budget)["criteria"]["AC1_iou"]["value"]
    # ② 藝術家真值 mesh
    a = artist_mesh(sk, slot, name)
    art_iou = poly_iou(a["uvs"], a["triangles"], mask)
    art_nv = len(a["uvs"]) // 2
    return {
        "slot": slot,
        "piece_size": [int(mask.shape[1]), int(mask.shape[0])],
        "generated": {"mode": mesh.get("_mode"), "vertices": len(mesh["uvs"]) // 2,
                      "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3,
                      "iou": round(gen_iou, 4)},
        "artist": {"vertices": art_nv, "hull": a.get("hull"),
                   "triangles": len(a["triangles"]) // 3, "iou": round(art_iou, 4)},
        "pass": gen_iou >= art_iou - margin,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--parts-dir", default="/tmp/robot_parts")
    ap.add_argument("--mode", choices=["auto", "strip", "delaunay"], default="auto")
    ap.add_argument("--margin", type=float, default=0.0)
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    # (piece 檔, slot/name) — 3 個 mesh 件
    targets = [
        ("00_光暈.png", "機器人拆件/光暈"),
        ("03_身體.png", "機器人拆件/身體"),
        ("04_左手.png", "機器人拆件/左手"),
    ]
    reports = []
    for fn, slot in targets:
        png = os.path.join(a.parts_dir, fn)
        reports.append(compare(png, sk, slot, slot, mode=a.mode, margin=a.margin))
    overall = all(r["pass"] for r in reports)
    print(json.dumps({"mode": a.mode, "overall_pass": overall, "results": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
