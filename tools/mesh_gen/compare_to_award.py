#!/usr/bin/env python3
"""端到端「件 → S3 生成 mesh」對照真實生產 spine(Award)的 mesh 真值。

背景(見 knowledge/s4-psd-to-spine-real.md):機器人拆件 5 件中,光暈/身體/左手在 Award
是 mesh。這三件的真實 alpha(atlas region,已 CW derotate、~0.70 縮小)可當「同一素材」的
真值來源;它們的 Spine mesh attachment 提供**藝術家手做拓樸**作為 IoU 真值基準。

⚠️ 校驗發現(2026-07-30):Award mesh 的 uvs 是**region-local 正規化 [0,1]**(非 atlas-page UV,
   先前 s4 筆記的謹慎假設有誤);且 v 軸**不需翻轉**即可與 extract() 的 de-rotate region alpha 對齊
   (flip_v=False artist IoU 0.97~0.98,flip_v=True 掉到 0.44~0.61 → 確認慣例)。

⚠️ 這三件在 Award **無 deform timeline**(靠骨骼/權重變形),故此對照只做**靜態拓樸/IoU/頂點預算**;
   deform 耐受度另在 main_draw 窗簾(有 deform)由 validate_against_real 驗證,不在此重複。

流程:extract() 取真值 region alpha → ① 藝術家 mesh IoU(真值基準)
      → ② generate_mesh_v2 對同一 region alpha 生成 → evaluate_mesh 全條 + IoU
      → ③ 對照:生成 IoU ≥ 藝術家基準 − margin、頂點數 ≤ 藝術家(精簡度)、格式全過。
"""
import argparse, json, sys, os
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate
from generate_mesh_v2 import generate as gen_v2
from generate_mesh import generate_adaptive


def region_alpha(atlas, png, name):
    sub = extract(atlas, png, name)
    if sub.ndim == 3 and sub.shape[2] == 4:
        return (sub[:, :, 3] > 8).astype(np.uint8)
    g = sub if sub.ndim == 2 else cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    return (g > 8).astype(np.uint8)


def artist_mesh(skeleton, name):
    skins = skeleton["skins"]
    skin = skins[0] if isinstance(skins, list) else skins
    atts = skin.get("attachments", skin)
    return atts[name][name]


def artist_iou(att, alpha, flip_v=False):
    uvs = np.array(att["uvs"]).reshape(-1, 2).copy()
    if flip_v:
        uvs[:, 1] = 1.0 - uvs[:, 1]
    tris = np.array(att["triangles"]).reshape(-1, 3)
    H, W = alpha.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, alpha).sum())
    union = int(np.logical_or(recon, alpha).sum())
    return (inter / union) if union else 0.0


def compare(skeleton_path, atlas_path, png_path, name, tmp_dir, iou_margin=0.02,
            vertex_budget=64, iou_target=0.96, generator="adaptive"):
    sk = json.load(open(skeleton_path))
    alpha = region_alpha(atlas_path, png_path, name)
    H, W = alpha.shape

    # ① 藝術家真值 mesh
    att = artist_mesh(sk, name)
    a_nv = len(att["uvs"]) // 2
    a_tris = len(att["triangles"]) // 3
    a_iou = artist_iou(att, alpha)

    # ② 生成 mesh(對同一 region alpha)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, (alpha * 255).astype(np.uint8))
    if generator == "adaptive":
        mesh, _ = generate_adaptive(crop, iou_target=iou_target,
                                    vertex_budget=vertex_budget)
    else:
        mesh = gen_v2(crop, mode="auto")
        if isinstance(mesh, tuple):
            mesh = mesh[0]
    g_nv = len(mesh["uvs"]) // 2
    ev = evaluate(mesh, alpha, vertex_budget=vertex_budget, iou_thresh=0.0)
    g_iou = ev["criteria"]["AC1_iou"]["value"]

    iou_pass = g_iou >= a_iou - iou_margin
    budget_pass = g_nv <= min(vertex_budget, a_nv)
    fmt_pass = (ev["criteria"]["AC4_format"]["pass"]
                and ev["criteria"]["AC2b_degenerate"]["pass"]
                and ev["criteria"]["AC2c_orphans"]["pass"])
    centroid_pass = ev["criteria"]["AC2a_centroid_in_mask"]["pass"]

    return {
        "part": name, "region_px": [W, H],
        "artist": {"vertices": a_nv, "triangles": a_tris, "hull": att.get("hull"),
                   "iou": round(a_iou, 4)},
        "generated": {"vertices": g_nv, "triangles": len(mesh["triangles"]) // 3,
                      "hull": mesh["hull"],
                      "mode": mesh.get("_mode", mesh.get("_adaptive")),
                      "iou": round(g_iou, 4), "adaptive": mesh.get("_adaptive")},
        "AC_iou_vs_artist": {"pass": bool(iou_pass), "gen": round(g_iou, 4),
                             "artist_baseline": round(a_iou, 4), "margin": iou_margin},
        "AC_vertex_budget": {"pass": bool(budget_pass), "gen": g_nv,
                             "artist": a_nv, "budget": vertex_budget},
        "AC_format": {"pass": bool(fmt_pass),
                      "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                      "orphans": ev["criteria"]["AC2c_orphans"]["value"]},
        "AC_centroid_in_mask": {"pass": bool(centroid_pass),
                                "value": ev["criteria"]["AC2a_centroid_in_mask"]["value"]},
        "overall_pass": bool(iou_pass and budget_pass and fmt_pass and centroid_pass),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--parts", nargs="+",
                    default=["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"])
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--budget", type=int, default=64)
    ap.add_argument("--margin", type=float, default=0.02)
    ap.add_argument("--target", type=float, default=0.96)
    ap.add_argument("--generator", choices=["adaptive", "v2"], default="adaptive")
    a = ap.parse_args()
    reports = []
    for name in a.parts:
        reports.append(compare(a.skeleton, a.atlas, a.png, name, a.tmp,
                               iou_margin=a.margin, vertex_budget=a.budget,
                               iou_target=a.target, generator=a.generator))
    allpass = all(r["overall_pass"] for r in reports)
    print(json.dumps({"overall_pass": allpass, "parts": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
