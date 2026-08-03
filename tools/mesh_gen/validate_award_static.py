#!/usr/bin/env python3
"""S3 整合 AC(靜態 IoU 軸)對真實生產 weighted mesh 的驗收 —— Award 機器人拆件。

背景:S3 的 4-mesh 校準(curtain/shadow)全是簡單 unweighted 直條輪廓;本閘把 S3 推廣到
真實生產 spine「Award」裡 3 個 **weighted** mesh(光暈/左手/身體,藝術家手做,78~98 頂點)。

真值:同一 atlas region 的 alpha(atlas_crop 切自 Award.png/Award2.png)+ 藝術家 mesh 自身的
IoU baseline(artist_iou:用藝術家 uvs/triangles 對 alpha 的覆蓋率)。生成 mesh 需 IoU ≥ baseline。

結論(見 knowledge/s3-award-weighted-static.md):預設 ~30v 預算(為簡單 mesh 校準)對複雜
機器人輪廓不足;把頂點預算拉到 ≈ 藝術家水準,3 件全部達標 → S3 靜態軸可推廣,覆蓋率隨頂點數上升。

⚠️ 僅靜態軸。weighted mesh 的 deform 閘(real_deform_field 目前只支援 unweighted)為下一塊工作。
"""
import sys, os, json, argparse
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
import generate_mesh_v2 as g2
from validate_against_real import artist_iou

PIECES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]

# (max_interior, epsilon_frac, min_dist):default = v1 預設;matched ≈ 藝術家頂點量
BUDGETS = {
    "default": None,
    "matched": (120, 0.002, 7),
}


def run(skeleton_path, atlas_path, png_path, pieces, budget_key, tmp_dir):
    sk = json.load(open(skeleton_path))
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    density = BUDGETS[budget_key]
    out = {}
    all_pass = True
    for slot in pieces:
        sub = extract(atlas_path, png_path, slot)
        crop = os.path.join(tmp_dir, "_award_region.png")
        cv2.imwrite(crop, sub)
        mask = load_mask(crop)
        a = att[slot][slot]
        base = artist_iou(sk, slot, slot, mask)
        art_v = len(a["uvs"]) // 2
        mesh = g2.generate(crop, density=density)
        if isinstance(mesh, tuple):
            mesh = mesh[0]
        iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
        gv = len(mesh["uvs"]) // 2
        ok = iou >= base
        all_pass = all_pass and ok
        out[slot] = {
            "alpha_wh": [int(mask.shape[1]), int(mask.shape[0])],
            "artist": {"verts": art_v, "iou_self": round(base, 4)},
            "gen": {"verts": gv, "mode": mesh.get("_mode"), "iou": round(iou, 4)},
            "pass": ok,
        }
    return {"budget": budget_key, "overall_pass": all_pass, "pieces": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--budget", choices=list(BUDGETS), default="matched")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    rep = run(a.skeleton, a.atlas, a.png, PIECES, a.budget, a.tmp)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    sys.exit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
