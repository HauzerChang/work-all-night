#!/usr/bin/env python3
"""端到端「PSD→件→S3 mesh」對真實生產標的(Award 機器人拆件)驗收 — 靜態 IoU 版。

背景(見 knowledge/s4-psd-to-spine-real.md):Award 的機器人 3 個 mesh 件
(光暈 / 身體 / 左手)皆為 **weighted mesh 且無 deform timeline**(靠骨骼/權重變形,
非逐頂點 deform)。因此:
  - deform-transfer 閘(需 deform timeline + unweighted vertices)**不適用**,
    直接呼叫 `deform_eval.real_deform_field` 會因 weighted vertices 無法 reshape 而崩。
  - 有意義的閘是 **靜態覆蓋 IoU**:生成 mesh 對「真實貼圖 alpha」的覆蓋率,
    與「藝術家手做 mesh 對同一 alpha 的覆蓋率」(ground-truth baseline)比較。

frame 對齊(已驗):Award mesh `uvs` 是 **region-local 正規化**(每件 uvs 幾乎撐滿 [0,1]),
非 atlas-page UV;atlas_crop.extract(多頁 + CW derotate)切出的 upright region mask 與之同框,
故 artist mesh 對自身 alpha 的 IoU 達 0.97~0.98(高 → 對齊正確)。

流程:atlas 切真實貼圖 → 生成 mesh(v1/v2)→ IoU(vs 真實 alpha)vs 藝術家 baseline。
deform 閘標記為 N/A 並附原因(誠實,不用未校準的 stress 場冒充)。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from evaluate_mesh import evaluate, load_mask
from atlas_crop import extract
from validate_against_real import artist_iou

ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def is_weighted(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    return len(a["vertices"]) != len(a["uvs"]), len(a.get("uvs", [])) // 2, a.get("hull")


def has_deform(skeleton, slot, name):
    for _an, body in skeleton.get("animations", {}).items():
        for _skinname, slots in body.get("deform", {}).items():
            if slot in slots and name in slots[slot]:
                return True
    return False


def validate_one(skeleton, atlas, png, slot, name, gen_fn, tmp_dir, iou_margin=0.0):
    sub = extract(atlas, png, name)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    mesh = gen_fn(crop)
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    nv = len(mesh["uvs"]) // 2

    ev = evaluate(mesh, mask)
    iou = ev["criteria"]["AC1_iou"]["value"]
    base = artist_iou(skeleton, slot, name, mask)
    weighted, artist_nv, artist_hull = is_weighted(skeleton, slot, name)
    deform = has_deform(skeleton, slot, name)

    return {
        "slot": slot,
        "mask_px": [int(mask.shape[1]), int(mask.shape[0])],
        "gen_mesh": {"vertices": nv, "hull": mesh["hull"],
                     "triangles": len(mesh["triangles"]) // 3, "mode": mesh.get("_mode")},
        "artist_mesh": {"vertices": artist_nv, "hull": artist_hull, "weighted": weighted},
        "AC_iou": {"value": round(iou, 4), "artist_baseline": round(base, 4),
                   "pass": iou >= base - iou_margin,
                   "gap": round(iou - base, 4)},
        "AC_real_deform": {"applicable": False,
                           "reason": "weighted mesh, no deform timeline (bone/weight driven)"},
        "overall_pass": bool(iou >= base - iou_margin),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--gen", choices=["v1", "v2", "adaptive", "both"], default="both")
    ap.add_argument("--slots", nargs="*", default=ROBOT_MESHES)
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))

    def make_gen(kind):
        if kind == "v1":
            from generate_mesh import generate as g
            return lambda p: g(p)
        if kind == "adaptive":
            from generate_mesh import generate_adaptive as g
            return lambda p: g(p)  # returns (mesh, mask, meta) → validate_one takes mesh[0]
        from generate_mesh_v2 import generate as g
        return lambda p: g(p, mode="auto")

    kinds = ["v1", "v2"] if a.gen == "both" else [a.gen]
    report = {}
    all_pass = True
    for kind in kinds:
        gen = make_gen(kind)
        rows = []
        for slot in a.slots:
            r = validate_one(sk, a.atlas, a.png, slot, slot, gen, a.tmp)
            rows.append(r)
            all_pass = all_pass and r["overall_pass"]
        report[kind] = rows
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
