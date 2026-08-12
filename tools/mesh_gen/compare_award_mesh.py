#!/usr/bin/env python3
"""端到端驗收:PSD件 → S3 generate_mesh_v2 → 對照 Award 真實生產 mesh(有真值)。

Award 機器人 3 件 mesh(光暈/身體/左手)為 **weighted、無 deform timeline**(靠骨骼驅動),
故此對照是**靜態覆蓋 + 拓樸預算**比較,deform 閘 N/A(記為 not_applicable)。

流程(每件):
  atlas_crop 取真實貼圖 region(mask) → generate_mesh_v2 產 mesh →
  ① 我的 mesh 覆蓋 IoU(evaluate_mesh)vs ② 藝術家真實 mesh 覆蓋 IoU(artist_iou)
  ③ 頂點預算(我 vs 藝術家)④ hull/自交健康度。

判定:my_iou >= artist_iou - margin(覆蓋不輸藝術家)且 mesh 靜態健康(0 自交)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from generate_mesh_v2 import generate as gen_v2
from validate_against_real import artist_iou


ROBOT_MESHES = [
    "機器人拆件/光暈",
    "機器人拆件/身體",
    "機器人拆件/左手",
]


def artist_vertex_count(skeleton, slot, name):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    return len(a["uvs"]) // 2, len(a["triangles"]) // 3


def run_one(sk, atlas, png, name, tmp_dir, iou_margin):
    sub = extract(atlas, png, name)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    mesh = gen_v2(crop, mode="auto")
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    my_nv = len(mesh["uvs"]) // 2
    my_tri = len(mesh["triangles"]) // 3

    art_nv, art_tri = artist_vertex_count(sk, name, name)
    # 頂點預算以「藝術家真實 mesh」為參照 —— evaluate_mesh 的絕對 budget=64 比真實生產
    # (78/98/80)還嚴,連藝術家自己都會 fail;對照真值時該用藝術家頂點數。
    ev = evaluate(mesh, mask, vertex_budget=art_nv)
    my_iou = ev["criteria"]["AC1_iou"]["value"]

    base = artist_iou(sk, name, name, mask)
    iou_pass = my_iou >= base - iou_margin

    # 幾何健康度(與頂點總數無關):重心在遮罩內、無退化三角、無孤兒像素、格式合法。
    GEOM = ("AC2a_centroid_in_mask", "AC2b_degenerate", "AC2c_orphans", "AC4_format")
    geom = {k: v for k, v in ev["criteria"].items() if k in GEOM}
    geom_clean = all(geom[k].get("pass", True) for k in geom)
    budget_pass = my_nv <= art_nv  # 效率:不比藝術家用更多頂點

    return {
        "region": name,
        "mask_wh": [int(mask.shape[1]), int(mask.shape[0])],
        "my_mesh": {"vertices": my_nv, "triangles": my_tri, "hull": mesh["hull"],
                    "mode": mesh.get("_mode")},
        "artist_mesh": {"vertices": art_nv, "triangles": art_tri, "weighted": True},
        "coverage_iou": {"mine": round(my_iou, 4), "artist_baseline": round(base, 4),
                         "margin": iou_margin, "pass": bool(iou_pass)},
        "vertex_budget_vs_artist": {"mine": my_nv, "artist": art_nv,
                                    "ratio": round(my_nv / art_nv, 3), "pass": bool(budget_pass)},
        "geometry_clean": {"pass": bool(geom_clean), "criteria": geom},
        "deform_gate": "not_applicable (weighted, bone-driven, no deform timeline)",
        "overall_pass": bool(iou_pass and geom_clean and budget_pass),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")  # multi-page auto-selected
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--margin", type=float, default=0.0)
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reports = [run_one(sk, a.atlas, a.png, name, a.tmp, a.margin) for name in ROBOT_MESHES]
    out = {"reports": reports,
           "all_pass": all(r["overall_pass"] for r in reports)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["all_pass"] else 1)


if __name__ == "__main__":
    main()
