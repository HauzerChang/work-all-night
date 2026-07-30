#!/usr/bin/env python3
"""端到端『真實生產標的』靜態對照 — 生成 mesh vs Award 藝術家 mesh。

背景(2026-07-30):Award(機器人 big win)的 3 個 mesh 件(光暈/左手/身體)是
**weighted mesh,由骨頭 skinning 驅動、無 deform timeline**,與 main_draw 的
「unweighted + deform timeline」機制不同。因此:
  - 靜態覆蓋率(輪廓/coverage)仍可直接對照 → 本工具。
  - 變形穩健度需先做 BBW 權重 + 骨頭模擬(S3 尚缺)→ 列為下一步,不在此閘。

流程:atlas 切件 → generate_mesh_v2 → ① 生成 mesh IoU(vs 切件 alpha)
② 藝術家 mesh 覆蓋率基準(同一 alpha frame)③ 頂點/三角/hull 預算對照。
判定:生成 mesh IoU >= 藝術家基準 - margin(對齊藝術家自身覆蓋率,不用武斷 0.95)。
"""
import argparse, json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from evaluate_mesh import evaluate, load_mask
from atlas_crop import extract
from validate_against_real import artist_iou
from generate_mesh_v2 import generate as gen_v2


def artist_mesh_info(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    nv = len(a["uvs"]) // 2
    weighted = len(a["vertices"]) != len(a["uvs"])
    return {"vertices": nv, "triangles": len(a["triangles"]) // 3,
            "hull": a.get("hull"), "weighted": weighted}


def validate_one(sk, atlas_path, png_path, slot, name, tmp_dir, iou_margin=0.02):
    sub = extract(atlas_path, png_path, name)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    mesh = gen_v2(crop, mode="auto")
    nv = len(mesh["uvs"]) // 2
    iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
    base = artist_iou(sk, slot, name, mask)
    art = artist_mesh_info(sk, slot, name)
    passed = iou >= base - iou_margin
    return {
        "slot": slot,
        "region_px": [int(sub.shape[1]), int(sub.shape[0])],
        "generated": {"vertices": nv, "hull": mesh["hull"],
                      "triangles": len(mesh["triangles"]) // 3, "mode": mesh.get("_mode")},
        "artist": art,
        "AC_iou": {"generated": round(iou, 4), "artist_baseline": round(base, 4),
                   "margin": iou_margin, "pass": bool(passed)},
        "pass": bool(passed),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    parts = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]
    reports = []
    for p in parts:
        try:
            reports.append(validate_one(sk, a.atlas, a.png, p, p, a.tmp, a.margin))
        except Exception as e:
            reports.append({"slot": p, "error": repr(e), "pass": False})
    overall = all(r.get("pass") for r in reports)
    print(json.dumps({"parts": reports, "overall_pass": overall},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
