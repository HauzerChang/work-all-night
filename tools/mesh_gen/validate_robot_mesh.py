#!/usr/bin/env python3
"""端到端「PSD件 → S3 mesh → 對照真實生產 mesh」驗收(機器人拆件 / Award spine)。

背景與 main_draw 的差異(重要):
  - main_draw 的 4 個 mesh 是 **unweighted + 有 deform timeline** → 用 `validate_against_real.py`
    的真實位移場轉移閘驗變形穩健。
  - Award「機器人拆件」的 3 個 mesh(光暈/身體/左手)是 **weighted(骨骼驅動)、無 deform timeline**
    → 逐頂點 deform 閘不適用。這裡改做 **靜態覆蓋率對照**:在同一張真實貼圖上,
    比較「我生成的 mesh」與「藝術家真實 mesh」的三角覆蓋 IoU + 頂點預算。

流程(每件):
  atlas 切真實貼圖(extract,已含 CW derotate + 多頁)→ alpha mask
   → ① 生成 mesh(generate_mesh_v2)→ 生成 IoU(evaluate_mesh)
   → ② 藝術家真實 mesh 覆蓋 IoU(artist_iou,uvs 為 region-local[0,1])
   → ③ 判定:生成 IoU ≥ 藝術家 baseline − margin,且頂點數在 budget 內。

真值來源 = Award.json 的生產 mesh(77 bones/47 slots 的真實 spine)。這是「對真實標的」驗收,
非合成 fixture。
"""
import argparse, json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from evaluate_mesh import evaluate, load_mask
from validate_against_real import artist_iou
from atlas_crop import extract

# 機器人拆件在 Award 中為 mesh 的 3 件(右手/頭為 region,不列入)
ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def artist_vertex_count(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    return len(a["uvs"]) // 2


def validate_one(sk, atlas, png, slot, name, gen_fn, tmp_dir,
                 iou_margin=0.03, vertex_budget=64, adaptive=False):
    sub = extract(atlas, png, name)
    crop = os.path.join(tmp_dir, "_robot_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    art_nv = artist_vertex_count(sk, slot, name)
    if adaptive:
        # 公平預算:生成頂點數不得超過藝術家自己用的數量(+小額 slack)
        vertex_budget = art_nv + 4
        from generate_mesh import generate_adaptive
        mesh, _, chosen_eps, _ = generate_adaptive(crop, vertex_cap=vertex_budget)
    else:
        chosen_eps = None
        mesh = gen_fn(crop)
        if isinstance(mesh, tuple):
            mesh = mesh[0]
    nv = len(mesh["uvs"]) // 2

    gen_iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
    base = artist_iou(sk, slot, name, mask)

    iou_pass = gen_iou >= base - iou_margin
    budget_pass = nv <= vertex_budget
    return {
        "slot": slot,
        "mesh": {"mode": mesh.get("_mode"), "gen_vertices": nv, "gen_triangles": len(mesh["triangles"]) // 3,
                 "gen_hull": mesh["hull"], "artist_vertices": art_nv,
                 "chosen_epsilon": chosen_eps},
        "AC_iou": {"gen": round(gen_iou, 4), "artist_baseline": round(base, 4),
                   "margin": iou_margin, "pass": bool(iou_pass)},
        "AC_vertex_budget": {"value": nv, "budget": vertex_budget, "pass": bool(budget_pass)},
        "overall_pass": bool(iou_pass and budget_pass),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--gen", choices=["v1", "v2"], default="v2")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--slots", nargs="*", default=ROBOT_MESHES)
    ap.add_argument("--adaptive", action="store_true",
                    help="用自適應 hull 密度(per-shape 預算=藝術家頂點數),對 soft/round 件更準")
    a = ap.parse_args()

    if a.gen == "v1":
        from generate_mesh import generate as g
        gen = lambda p: g(p)
    else:
        from generate_mesh_v2 import generate as g
        gen = lambda p: g(p, mode="auto")

    sk = json.load(open(a.skeleton))
    reports = [validate_one(sk, a.atlas, a.png, s, s, gen, a.tmp, adaptive=a.adaptive)
               for s in a.slots]
    overall = all(r["overall_pass"] for r in reports)
    out = {"gen": a.gen, "adaptive": a.adaptive, "n": len(reports),
           "all_pass": overall, "results": reports}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
