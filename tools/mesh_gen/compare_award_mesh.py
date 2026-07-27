#!/usr/bin/env python3
"""端到端『PSD件/atlas件 → S3 generate_mesh_v2 → 對照 Award 真實生產 mesh』(靜態 AC)。

背景(見 STATE.md 最高優先 chunk):Award(機器人 big win 生產 spine)有 3 個 weighted mesh
部位 —— `機器人拆件/{光暈,身體,左手}`。這是首次把 S3 生成器對照「真實藝術家手做的生產 mesh」
(先前只對照 main_draw 窗簾這種簡單直條)。

⚠️ 這 3 件**無 deform timeline**(靠骨骼 weighted 驅動,非 mesh deform)→ 真實位移場轉移閘
   (transfer_deform_check)對它們 N/A。本工具因此聚焦**靜態幾何 AC**:
   ① 生成 mesh 的覆蓋率 IoU ≥ 藝術家真實 mesh 的覆蓋率 IoU(對齊藝術家基準,同 validate_against_real 精神);
   ② 生成 mesh 通過 evaluate_mesh 全部靜態格式/退化/預算 AC;
   ③ 附上藝術家 vs 生成的拓樸統計(verts/hull/tris)供對照。
   weighted deform 對照需 BBW 權重(S3 未來組件),超出本 chunk。

來源 alpha:直接用 Award atlas 該 region 的 alpha(藝術家 mesh uv 就定義在此 region 座標系,
可公平同框對照)。『PSD→件』段先前已驗(log 005:PSD切件↔atlas切件 alpha-IoU 0.92~0.99),
故在 atlas region 生成 ≈ 在 PSD 件生成,且保持與藝術家同座標。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from validate_against_real import artist_iou
from generate_mesh_v2 import generate as gen_v2


def artist_stats(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uvs = a["uvs"]; tris = a["triangles"]; verts = a.get("vertices", [])
    nv = len(uvs) // 2
    weighted = len(verts) != len(uvs)
    return {"vertices": nv, "hull": a["hull"], "triangles": len(tris) // 3,
            "weighted": weighted}


def compare_one(sk, atlas, png, slot, name, tmp_dir, iou_margin=0.02):
    sub = extract(atlas, png, name)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    a_iou = artist_iou(sk, slot, name, mask)
    a_stat = artist_stats(sk, slot, name)

    mesh = gen_v2(crop, mode="auto")
    ev = evaluate(mesh, mask)
    g_iou = ev["criteria"]["AC1_iou"]["value"]
    nv = len(mesh["uvs"]) // 2

    iou_pass = g_iou >= a_iou - iou_margin
    return {
        "slot": slot,
        "artist": {**a_stat, "coverage_iou": round(a_iou, 4)},
        "generated": {"vertices": nv, "hull": mesh["hull"],
                      "triangles": len(mesh["triangles"]) // 3,
                      "mode": mesh.get("_mode"), "coverage_iou": round(g_iou, 4)},
        "AC_iou_vs_artist": {"pass": bool(iou_pass), "margin": iou_margin,
                             "gen_minus_artist": round(g_iou - a_iou, 4)},
        "AC_static_mesh": {"pass": bool(ev["overall_pass"]),
                           "criteria": {k: v["pass"] for k, v in ev["criteria"].items()}},
        "overall_pass": bool(iou_pass and ev["overall_pass"]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")  # extract 會自動選 region 所屬 page
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--slots", nargs="*",
                    default=["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"])
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reports = []
    for slot in a.slots:
        reports.append(compare_one(sk, a.atlas, a.png, slot, slot, a.tmp))
    out = {"target": "Award (機器人 big win 生產 spine)",
           "note": "weighted/bone-driven, 無 deform timeline → 真實位移場閘 N/A;本表為靜態幾何對照",
           "results": reports,
           "overall_pass": all(r["overall_pass"] for r in reports)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["overall_pass"] else 1)


if __name__ == "__main__":
    main()
