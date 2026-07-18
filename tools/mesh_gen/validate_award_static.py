#!/usr/bin/env python3
"""端到端「PSD→件→S3 mesh」對第二個生產骨架(Award)的『真實 weighted mesh』做靜態驗收。

背景 / 為何只做靜態(2026-07-18):
  main_draw 的 4 個 mesh 全 unweighted;Award 機器人拆件的 3 個 mesh(光暈/左手/身體)
  全 **weighted**(vertices 為 [boneCount,boneIdx,bindX,bindY,weight,...] 攤平格式)。
  `deform_eval` 目前假設 unweighted(reshape(-1,2)),對 weighted 的 deform 位移場**尚不可信**,
  因此本次先做「靜態輪廓覆蓋率」對照(只用 uvs+triangles,與權重無關 → 真值可信),
  weighted-aware deform 閘列為下一個 bounded chunk。

真值:Award 藝術家手做的 weighted mesh 覆蓋率(artist_iou,只吃 uvs/triangles)。
AC:
  AC1 覆蓋率  gen_IoU >= artist_IoU - margin(0.02)     # 自動 mesh 覆蓋 >= 藝術家
  AC2 頂點預算 gen_nv <= artist_nv                        # 自動 mesh 更精簡
  AC3 靜態拓樸 0 退化三角 / 0 孤兒頂點(evaluate AC2b/AC2c)
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract, parse_atlas
from evaluate_mesh import evaluate, load_mask
from generate_mesh_v2 import generate as gen_v2
from validate_against_real import artist_iou


PARTS = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def artist_mesh_stats(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    nv = len(a["uvs"]) // 2
    ntri = len(a["triangles"]) // 3
    weighted = len(a["vertices"]) != len(a["uvs"])
    return nv, ntri, a["hull"], weighted


def overlay(mask, mesh, artist_uv, out_path):
    """存一張對照圖:alpha 底 + 生成 mesh 線框(綠)+ 藝術家 hull 點(紅)。"""
    H, W = mask.shape
    img = np.zeros((H, W, 3), np.uint8)
    img[mask > 0] = (60, 60, 60)
    # 生成 mesh
    v = mesh["vertices"]
    pts = []
    for i in range(0, len(v), 2):
        pts.append((v[i] + W / 2.0, H / 2.0 - v[i + 1]))
    pts = np.array(pts)
    tris = np.array(mesh["triangles"]).reshape(-1, 3)
    for t in tris:
        p = np.round(pts[t]).astype(np.int32)
        cv2.polylines(img, [p], True, (80, 220, 80), 1, cv2.LINE_AA)
    for p in pts:
        cv2.circle(img, (int(round(p[0])), int(round(p[1]))), 2, (80, 255, 80), -1)
    # 藝術家 uv 點(紅)
    for (u, vv) in artist_uv:
        cv2.circle(img, (int(round(u * W)), int(round(vv * H))), 2, (60, 60, 230), -1)
    cv2.imwrite(out_path, img)


def run(skeleton, atlas, png, tmp, fig_dir, margin=0.02):
    sk = json.load(open(skeleton))
    os.makedirs(fig_dir, exist_ok=True)
    regions = parse_atlas(atlas)
    report = {}
    all_pass = True
    for part in PARTS:
        sub = extract(atlas, png, part)
        crop = os.path.join(tmp, "_award_region.png")
        cv2.imwrite(crop, sub)
        mask = load_mask(crop)

        mesh = gen_v2(crop, mode="auto")
        ev = evaluate(mesh, mask, vertex_budget=999)  # 預算另行比對藝術家
        gen_iou = ev["criteria"]["AC1_iou"]["value"]
        base = artist_iou(sk, part, part, mask)
        a_nv, a_tri, a_hull, weighted = artist_mesh_stats(sk, part, part)
        g_nv = ev["vertices"]

        ac1 = gen_iou >= base - margin
        ac2 = g_nv <= a_nv
        ac3 = ev["criteria"]["AC2b_degenerate"]["pass"] and ev["criteria"]["AC2c_orphans"]["pass"]
        part_pass = ac1 and ac2 and ac3
        all_pass = all_pass and part_pass

        # figure
        skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
        auv = np.array(skin.get("attachments", skin)[part][part]["uvs"]).reshape(-1, 2)
        fig = os.path.join(fig_dir, part.split("/")[-1] + "_static.png")
        overlay(mask, mesh, auv, fig)

        report[part] = {
            "region_px": [int(sub.shape[1]), int(sub.shape[0])],
            "rotate": regions[part].get("rotate", "false"),
            "mode": mesh.get("_mode"),
            "artist": {"nv": a_nv, "tris": a_tri, "hull": a_hull, "weighted": weighted},
            "generated": {"nv": g_nv, "tris": ev["triangles"], "hull": mesh["hull"]},
            "AC1_coverage": {"gen_iou": round(gen_iou, 4), "artist_iou": round(base, 4),
                             "margin": margin, "pass": ac1},
            "AC2_budget": {"gen_nv": g_nv, "artist_nv": a_nv, "pass": ac2},
            "AC3_static_topology": {"degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                                    "orphans": ev["criteria"]["AC2c_orphans"]["value"], "pass": ac3},
            "part_pass": part_pass,
            "figure": fig,
        }
    report["_overall_pass"] = all_pass
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")  # extract 會依 region page 自動切頁
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--figdir", default="knowledge/figures/award_static")
    a = ap.parse_args()
    rep = run(a.skeleton, a.atlas, a.png, a.tmp, a.figdir)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["_overall_pass"] else 1)


if __name__ == "__main__":
    main()
