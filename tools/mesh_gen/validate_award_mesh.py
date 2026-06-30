#!/usr/bin/env python3
"""對 Award(機器人拆件)真實生產 mesh 驗證生成的 mesh — 端到端「PSD→件→S3 mesh→對照真值」。

與 validate_against_real.py 的差別:
  - main_draw 的 4 mesh 靠**動畫 deform timeline** 逐頂點變形 → 可用真實位移場轉移做變形閘。
  - Award 機器人 mesh 件(光暈/身體/左手)在 spine 中**無 deform timeline**,
    靠**骨骼權重(weighted)**變形 → 沒有可轉移的真實位移場。
    因此本檔只做**靜態覆蓋率 IoU** 對照藝術家 mesh(weighted),不做 deform 閘。
    (bone-weighted 變形需重現整段骨骼動畫,屬 S5 範圍,本階段不測。)

真值來源:Award.json 的 weighted mesh attachment(uvs 為 region-local;與 atlas_crop 的 CW
derotate 上正 crop 對齊 → artist_iou 直接用 uvs×(cropW,cropH))。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from validate_against_real import artist_iou

# Award 中為 mesh 的機器人件(slot==attachment 同名)
ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def validate(skeleton_path, atlas_path, png_path, slot, name, gen_fn, tmp_dir, iou_margin=0.0):
    sk = json.load(open(skeleton_path))
    sub = extract(atlas_path, png_path, name)          # 多頁 + CW derotate 上正
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    mesh = gen_fn(crop)
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    nv = len(mesh["uvs"]) // 2

    iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
    amask = (sub[:, :, 3] > 8).astype(np.uint8) if sub.ndim == 3 and sub.shape[2] == 4 \
        else (cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY) > 0).astype(np.uint8)
    base = artist_iou(sk, slot, name, amask)

    skin = sk["skins"]; skin = skin[0]["attachments"] if isinstance(skin, list) else skin.get("attachments", skin)
    a = skin[slot][name]
    art_nv = len(a["uvs"]) // 2

    return {
        "slot": slot,
        "mesh": {"vertices": nv, "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3,
                 "mode": mesh.get("_mode")},
        "artist": {"vertices": art_nv, "hull": a.get("hull"), "triangles": len(a["triangles"]) // 3,
                   "weighted": True},
        "AC_iou": {"value": round(iou, 4), "artist_baseline": round(base, 4),
                   "within_vertex_budget": nv <= art_nv,
                   "pass": iou >= base - iou_margin},
        "overall_pass": (iou >= base - iou_margin),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--slot", default=None, help="單一 slot;省略則跑全部 3 個機器人 mesh 件")
    ap.add_argument("--gen", choices=["v1", "v2"], default="v2")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    if a.gen == "v1":
        from generate_mesh import generate as g
        gen = lambda p: g(p)
    else:
        from generate_mesh_v2 import generate as g
        gen = lambda p: g(p, mode="auto")

    slots = [a.slot] if a.slot else ROBOT_MESHES
    reps = [validate(a.skeleton, a.atlas, a.png, s, s, gen, a.tmp) for s in slots]
    print(json.dumps(reps, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all(r["overall_pass"] for r in reps) else 1)


if __name__ == "__main__":
    main()
