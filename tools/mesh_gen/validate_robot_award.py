#!/usr/bin/env python3
"""端到端驗證:PSD 機器人件 → S3 生成 mesh → 對照 Award 真實「藝術家 weighted mesh」。

背景(2026-07-28):main_draw 的 4 mesh 全 **unweighted**、靠 deform timeline 變形;
但真實生產檔 Award 的 3 個機器人 mesh(左手/光暈/身體)全 **weighted、bone-driven、
無 deform timeline**。這是 S3 第一次面對「真實生產標的」的外部真值。

本腳本只做**靜態輪廓覆蓋**對照(在 atlas region 自身像素空間,與藝術家 uvs 同座標系):
  extract(Award.atlas, Award.png/Award2.png, region) → alpha mask
  → 藝術家 mesh 覆蓋 IoU(uvs→region 像素 + triangles fillConvexPoly)= baseline
  → S3 生成 mesh 覆蓋 IoU,比較是否達 baseline、頂點數是否可比。

⚠️ **不做 deform 閘**:這些 mesh 是 bone-driven weighted,沒有 per-vertex 位移場可轉移
(transfer_deform_check 不適用)。bone-affine-blend 變形閘 + BBW 權重綁定 是尚未建的能力
(見 knowledge/s3-award-weighted-real.md 的「gap / 下一步」)。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from validate_against_real import artist_iou

ROBOT_MESHES = ["機器人拆件/左手", "機器人拆件/光暈", "機器人拆件/身體"]


def run(skeleton_path, atlas_path, png_path, names, tmp_dir, gen_kind, gen_kwargs):
    sk = json.load(open(skeleton_path))
    if gen_kind == "v1":
        from generate_mesh import generate as g
        gen = lambda p: g(p, **gen_kwargs)[0]
    else:
        from generate_mesh_v2 import generate as g
        gen = lambda p: (lambda m: m[0] if isinstance(m, tuple) else m)(g(p, **gen_kwargs))
    rows = []
    for name in names:
        sub = extract(atlas_path, png_path, name)
        crop = os.path.join(tmp_dir, "_" + name.split("/")[-1] + ".png")
        cv2.imwrite(crop, sub)
        mask = load_mask(crop)
        att = sk["skins"][0]["attachments"][name][name]
        nv_art = len(att["uvs"]) // 2
        weighted = len(att["vertices"]) != len(att["uvs"])
        base = artist_iou(sk, name, name, mask)
        mesh = gen(crop)
        nv = len(mesh["uvs"]) // 2
        iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
        rows.append({
            "name": name, "region": [int(mask.shape[1]), int(mask.shape[0])],
            "artist": {"nv": nv_art, "weighted": weighted, "iou": round(base, 4)},
            "gen": {"mode": mesh.get("_mode"), "nv": nv, "hull": mesh["hull"], "iou": round(iou, 4)},
            "meets_artist": iou >= base,
        })
    return {"gen_kind": gen_kind, "gen_kwargs": gen_kwargs, "pieces": rows,
            "all_meet_artist": all(r["meets_artist"] for r in rows)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")  # 多頁:extract 自動切 Award2.png
    ap.add_argument("--gen", choices=["v1", "v2"], default="v1")
    ap.add_argument("--epsilon", type=float, default=0.002)
    ap.add_argument("--max-interior", type=int, default=60)
    ap.add_argument("--min-dist", type=int, default=8)
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    if a.gen == "v1":
        kw = {"epsilon_frac": a.epsilon, "max_interior": a.max_interior, "min_dist": a.min_dist}
    else:
        kw = {"rows": a.rows, "cols": a.cols, "mode": "auto"}
    rep = run(a.skeleton, a.atlas, a.png, ROBOT_MESHES, a.tmp, a.gen, kw)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["all_meet_artist"] else 1)


if __name__ == "__main__":
    main()
