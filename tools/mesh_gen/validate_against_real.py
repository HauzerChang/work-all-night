#!/usr/bin/env python3
"""對「真實資產」驗證生成的 mesh — 正式整合 AC(校正後)。

校正(2026-06-24):
  - IoU 目標改為「對齊藝術家 mesh 的覆蓋率」(curtain_left 藝術家自身僅 0.918),
    不再用武斷的 0.95。
  - deform 閘改用 transfer_deform_check()(真實位移場轉移),取代 stress_field
    (合成場 mag=315 面積比 2.0 >> 真實 1.13,會造成假性失敗)。

流程:atlas 切真實貼圖 → 生成 mesh → ① IoU(vs 真實 alpha)② 真實 deform 轉移後 0 自交/0 翻面。
"""
import argparse, json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
import deform_eval as de
from evaluate_mesh import evaluate, load_mask
from atlas_crop import extract


def artist_iou(skeleton, slot, name, mask):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return float(np.logical_and(recon, mask).sum() / np.logical_or(recon, mask).sum())


def validate(skeleton_path, atlas_path, png_path, slot, name, gen_fn, tmp_dir,
             iou_margin=0.0):
    sk = json.load(open(skeleton_path))
    sub = extract(atlas_path, png_path, name)
    crop = os.path.join(tmp_dir, "_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    mesh = gen_fn(crop)
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    nv = len(mesh["uvs"]) // 2

    iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
    base = artist_iou(sk, slot, name, mask)
    iou_pass = iou >= base - iou_margin

    # 藝術家該件是否 weighted(vertices 長度 != uvs×2)?
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    weighted = len(a["vertices"]) != len(a["uvs"])

    uvs_src, field, frame = de.real_deform_field(sk, slot, name)
    if field is None:
        # 該件無 deform timeline(骨骼驅動,如 Award 機器人拆件)→ 位移場轉移不適用。
        deform_ac = {"applicable": False,
                     "note": "no deform timeline (bone-driven); deform-transfer N/A",
                     "pass": None}
        overall = iou_pass
    else:
        dres = de.transfer_deform_check(mesh, uvs_src, field)
        deform_ac = {"applicable": True, "frame": frame, "area_ratio": dres["area_ratio"],
                     "self_intersections": dres["self_intersections"],
                     "triangle_flips": dres["triangle_flips"], "pass": dres["clean"]}
        overall = iou_pass and dres["clean"]

    return {
        "mesh": {"vertices": nv, "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3,
                 "mode": mesh.get("_mode")},
        "artist_mesh": {"vertices": len(a["uvs"]) // 2, "hull": a.get("hull"),
                        "triangles": len(a["triangles"]) // 3, "weighted": weighted},
        "AC_iou": {"value": round(iou, 4), "artist_baseline": round(base, 4), "pass": iou_pass},
        "AC_real_deform": deform_ac,
        "overall_pass": overall,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/main_draw.json")
    ap.add_argument("--atlas", default="assets/main_draw.atlas")
    ap.add_argument("--png", default="assets/main_draw.png")
    ap.add_argument("--slot", default="image/curtain_left")
    ap.add_argument("--name", default="image/curtain_left")
    ap.add_argument("--gen", choices=["v1", "v2"], default="v1")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    if a.gen == "v1":
        from generate_mesh import generate as g
        gen = lambda p: g(p)
    else:
        from generate_mesh_v2 import generate as g
        gen = lambda p: g(p, mode="auto")
    rep = validate(a.skeleton, a.atlas, a.png, a.slot, a.name, gen, a.tmp)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
