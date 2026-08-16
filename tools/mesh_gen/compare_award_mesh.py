#!/usr/bin/env python3
"""端到端(靜態):Award 真實貼圖件 → S3 generate_mesh_v2 → 對照 Award 藝術家 mesh。

背景(2026-08-16 發現):Award 機器人拆件的 mesh(光暈/左手/身體)是 **bone-weighted rig**,
**沒有 deform timeline**(靠骨頭仿射動,不靠 mesh 逐頂點變形)。因此 run.md 要求的
「真實位移場轉移 deform 閘」對這些件 **N/A**(沒有真實位移場可轉移)。
→ 對這些件,S3 的正確性等於「靜態輪廓覆蓋 + 拓樸乾淨 + 頂點預算」對照藝術家 mesh。
(對照:main_draw 窗簾是 deform 驅動,deform 閘才適用且已驗。)

流程(每件):atlas 切件(CW derotate,已校正)→ 生成 mesh(v2 auto)
  → ① 覆蓋 IoU vs 真實 alpha,對照藝術家 mesh 自身覆蓋(baseline)
  → ② 生成 mesh setup pose 靜態幾何(0 自交/0 翻面/0 退化)
  → ③ 頂點預算 vs 藝術家。
並回報藝術家 mesh 是否有 deform timeline(有 → 提醒改跑 deform 閘)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from validate_against_real import artist_iou
import deform_eval as de
from generate_mesh_v2 import generate as gen_v2


def artist_mesh(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    nv = len(a["uvs"]) // 2
    weighted = len(a["vertices"]) != len(a["uvs"])
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    return {"nv": nv, "hull": a["hull"], "tris": len(tris), "weighted": weighted}


def has_deform(sk, slot, name):
    for anim in sk.get("animations", {}):
        if de.deform_frames(sk, anim, slot, name):
            return True
    return False


def static_geom(mesh):
    """生成 mesh 在 setup pose 的靜態幾何品質(不施加任何 deform)。"""
    v = np.array(mesh["vertices"], dtype=np.float64).reshape(-1, 2)
    t = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    signs = [de.signed_area(v, x) > 0 for x in t]
    r = de.check(v, t, signs)
    r["clean"] = (r["self_intersections"] == 0 and r["triangle_flips"] == 0
                  and r["degenerate"] == 0)
    return r


def compare_one(sk, atlas, png, slot, name, tmp, iou_margin=0.0):
    sub = extract(atlas, png, name)
    crop = os.path.join(tmp, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    mesh = gen_v2(crop, mode="auto")
    gnv = len(mesh["uvs"]) // 2

    iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
    base = artist_iou(sk, slot, name, mask)
    art = artist_mesh(sk, slot, name)
    geom = static_geom(mesh)
    deform = has_deform(sk, slot, name)

    iou_pass = iou >= base - iou_margin
    budget_pass = gnv <= art["nv"]
    return {
        "piece": name,
        "crop_size": [int(sub.shape[1]), int(sub.shape[0])],
        "generated": {"mode": mesh.get("_mode"), "vertices": gnv,
                      "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3},
        "artist": art,
        "AC1_coverage_iou": {"generated": round(iou, 4),
                             "artist_baseline": round(base, 4), "pass": iou_pass},
        "AC2_static_geom": {**geom, "pass": geom["clean"]},
        "AC3_vertex_budget": {"generated": gnv, "artist": art["nv"], "pass": budget_pass},
        "deform_gate": ("N/A (no deform timeline; bone-weighted rig)"
                        if not deform else "APPLICABLE — run deform_eval real-field gate"),
        "overall_pass": iou_pass and geom["clean"] and budget_pass,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--pieces", nargs="+",
                    default=["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"])
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reports = [compare_one(sk, a.atlas, a.png, p, p, a.tmp) for p in a.pieces]
    out = {"pieces": reports,
           "all_pass": all(r["overall_pass"] for r in reports)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["all_pass"] else 1)


if __name__ == "__main__":
    main()
