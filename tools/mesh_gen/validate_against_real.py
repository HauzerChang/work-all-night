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
    uvs_src, field, frame = de.real_deform_field(sk, slot, name)

    iou_pass = iou >= base - iou_margin
    if frame is None:
        # 該 mesh 無 deform timeline(bone-driven,如機器人光暈/身體/左手):
        # 拓樸不受 deform 位移場拉扯,deform 閘不適用 → 標 N/A,overall 只看靜態 IoU。
        deform = {"frame": None, "status": "N/A (bone-driven; no deform timeline)", "pass": True}
        deform_pass = True
    else:
        dres = de.transfer_deform_check(mesh, uvs_src, field)
        deform = {"frame": frame, "area_ratio": dres["area_ratio"],
                  "self_intersections": dres["self_intersections"],
                  "triangle_flips": dres["triangle_flips"], "pass": dres["clean"]}
        deform_pass = dres["clean"]

    return {
        "mesh": {"vertices": nv, "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3,
                 "mode": mesh.get("_mode")},
        "AC_iou": {"value": round(iou, 4), "artist_baseline": round(base, 4),
                   "artist_vertices": len(np.array(
                       (sk["skins"][0] if isinstance(sk["skins"], list) else sk["skins"])
                       .get("attachments", sk["skins"])[slot][name]["uvs"])) // 2,
                   "pass": iou_pass},
        "AC_real_deform": deform,
        "overall_pass": iou_pass and deform_pass,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/main_draw.json")
    ap.add_argument("--atlas", default="assets/main_draw.atlas")
    ap.add_argument("--png", default="assets/main_draw.png")
    ap.add_argument("--slot", default="image/curtain_left")
    ap.add_argument("--name", default="image/curtain_left")
    ap.add_argument("--gen", choices=["v1", "v2"], default="v1")
    ap.add_argument("--epsilon", type=float, default=0.002,
                    help="Delaunay 邊界簡化比例(靜態件輪廓 IoU 操作點,見 award-mesh knowledge)")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    if a.gen == "v1":
        from generate_mesh import generate as g
        gen = lambda p: g(p, epsilon_frac=a.epsilon)
    else:
        from generate_mesh_v2 import generate as g
        gen = lambda p: g(p, mode="auto", epsilon=a.epsilon)
    rep = validate(a.skeleton, a.atlas, a.png, a.slot, a.name, gen, a.tmp)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
