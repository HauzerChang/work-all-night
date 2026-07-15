#!/usr/bin/env python3
"""S3 端到端驗收:真實生產件(Award 機器人拆件)自動 mesh vs 藝術家真實 mesh。

情境(見 knowledge/s4-psd-to-spine-real.md):Award「機器人拆件」有 5 件,其中
**光暈 / 身體 / 左手 為 mesh**(右手 / 頭為 region)。這 3 個 mesh 是 **weighted**
且 **無 deform timeline** —— 它們靠骨骼權重變形,不是逐頂點 deform。

因此對這批件,有意義的 AC 是「**靜態覆蓋率**」而非 deform 耐受:
  我自動生成的 mesh,對這件貼圖的覆蓋(IoU),是否 ≥ 藝術家手做 mesh 的覆蓋(基準)?
外加「生成 mesh 自身合法性」(格式/預算/0 退化/0 孤兒/重心在 mask 內)。

⚠️ 為什麼不做 deform 閘:這 3 件在 Award 12 支動畫全無 deform timeline(已查證),
   變形由 weighted bone 驅動;我目前的生成器不產權重,故 deform 耐受無真值可比。
   權重生成(BBW)是 S3 後續課題,屆時才有意義做 weighted deform 對照。

流程:atlas 切真實貼圖(多頁 + CW derotate)→ 生成 mesh(v2 auto)→
  ① 靜態 IoU / 合法性(evaluate_mesh)② 藝術家 mesh 覆蓋率基準(artist_iou)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from validate_against_real import artist_iou

# Award「機器人拆件」中為 mesh 的 3 件(slot == attachment name)
ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def validate_piece(skeleton, atlas_path, png_path, name, gen_fn, tmp_dir,
                   iou_margin=0.02, budget_cap=128):
    sub = extract(atlas_path, png_path, name)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)          # evaluate_mesh.load_mask → 二值 alpha
    H, W = mask.shape

    # 藝術家真實 mesh 拓樸(真值,供對照 + 定 budget)
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[name][name]
    art_nv = len(a["uvs"]) // 2
    art_nt = len(a["triangles"]) // 3

    # AC3(leanness):auto mesh 頂點數 ≤ 藝術家同件(不比手做的多),而非武斷常數 64。
    # 64 是對 main_draw 小 mesh(窗簾 21v/陰影 12v)校準的;真實大件藝術家自身即用 78~98v。
    # 以 art_nv 為 budget = 與 IoU 一樣「以藝術家為基準」的方法論一致做法。加一 budget_cap 防跑飛。
    budget = min(art_nv, budget_cap)

    mesh = gen_fn(crop)
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    ev = evaluate(mesh, mask, vertex_budget=budget)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]

    base = artist_iou(skeleton, name, name, mask)

    coverage_pass = gen_iou >= base - iou_margin
    validity_pass = ev["overall_pass"]
    return {
        "piece": name,
        "region_px": [W, H],
        "generated": {"vertices": ev["vertices"], "triangles": ev["triangles"],
                      "hull": ev["hull"], "mode": mesh.get("_mode")},
        "artist": {"vertices": art_nv, "triangles": art_nt,
                   "hull": a.get("hull"), "weighted": len(a["vertices"]) != len(a["uvs"])},
        "AC_coverage": {"gen_iou": round(gen_iou, 4),
                        "artist_baseline": round(base, 4),
                        "margin": iou_margin, "pass": bool(coverage_pass)},
        "AC_validity": {"pass": bool(validity_pass), "vertex_budget": budget,
                        "criteria": {k: v["pass"] for k, v in ev["criteria"].items()}},
        "overall_pass": bool(coverage_pass and validity_pass),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--gen", choices=["v1", "v2"], default="v2")
    ap.add_argument("--margin", type=float, default=0.02)
    ap.add_argument("--budget-cap", type=int, default=128,
                    help="安全上限;每件實際 budget = min(藝術家頂點數, budget-cap)")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--pieces", nargs="*", default=ROBOT_MESHES)
    a = ap.parse_args()

    if a.gen == "v1":
        from generate_mesh import generate as g
        gen = lambda p: g(p)
    else:
        from generate_mesh_v2 import generate as g
        gen = lambda p: g(p, mode="auto")

    sk = json.load(open(a.skeleton))
    reports = [validate_piece(sk, a.atlas, a.png, name, gen, a.tmp,
                              iou_margin=a.margin, budget_cap=a.budget_cap)
               for name in a.pieces]
    overall = all(r["overall_pass"] for r in reports)
    out = {"gen": a.gen, "overall_pass": overall, "pieces": reports}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
