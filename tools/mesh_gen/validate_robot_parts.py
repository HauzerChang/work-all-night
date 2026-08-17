#!/usr/bin/env python3
"""端到端驗證:PSD 件 → S3 generate_mesh_v2 → 對照 Award 真實生產 mesh。

背景(STATE 下一步 #1):`robot_parts.psd` 的光暈/身體/左手 3 件在真實 spine `Award` 中
是 mesh。本驅動用 Award atlas 的真實貼圖切件(alpha 來源),跑 v2 生成 mesh,與 Award
藝術家 mesh 做「靜態覆蓋率(IoU)」與頂點預算對照 —— 對真實生產標的的自主驗收。

⚠️ deform 閘 N/A(誠實標註):Award 這 3 件**沒有 deform timeline**(靠加權骨骼驅動,
   見 log/2026-06-26-005.md),因此 `real_deform_field` 無真實位移場可轉移。硬跑會拿到
   零位移的**假性乾淨**,故本驅動明確標 N/A 而非讓它 vacuous pass。加權骨骼驅動的耐變形
   驗收需 bone transform,屬後續課題。

AC(每件):
  ① IoU_gen ≥ IoU_artist(覆蓋率不低於藝術家自身 mesh)。
  ② 頂點數 ≤ 藝術家頂點數 ×1.1(精簡度相當,不靠灌頂點取巧)。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from validate_against_real import artist_iou
from generate_mesh_v2 import generate as gen_v2

ROBOT_MESH_SLOTS = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def artist_vertex_count(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    return len(a["uvs"]) // 2


def validate(skeleton_path, atlas_path, png_path, slots, tmp_dir, budget_margin=1.1):
    sk = json.load(open(skeleton_path))
    os.makedirs(tmp_dir, exist_ok=True)
    reports = []
    for slot in slots:
        name = slot  # Award 慣例 attachment 名 == slot 名
        sub = extract(atlas_path, png_path, name)
        crop = os.path.join(tmp_dir, os.path.basename(name) + ".png")
        cv2.imwrite(crop, sub)
        mask = load_mask(crop)

        mesh = gen_v2(crop, mode="auto")
        if isinstance(mesh, tuple):
            mesh = mesh[0]
        nv = len(mesh["uvs"]) // 2

        iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
        base = artist_iou(sk, slot, name, mask)
        av = artist_vertex_count(sk, slot, name)
        iou_pass = iou >= base
        budget_pass = nv <= av * budget_margin
        reports.append({
            "slot": slot,
            "region": [int(sub.shape[1]), int(sub.shape[0])],
            "mode": mesh.get("_mode"),
            "AC_iou": {"gen": round(iou, 4), "artist": round(base, 4), "pass": iou_pass},
            "AC_vertex_budget": {"gen": nv, "artist": av, "pass": budget_pass},
            "AC_real_deform": {"status": "N/A", "reason": "Award 此件無 deform timeline(骨骼驅動)"},
            "overall_pass": iou_pass and budget_pass,
        })
    return {
        "target": "Award 機器人拆件 真實 mesh",
        "parts": reports,
        "overall_pass": all(r["overall_pass"] for r in reports),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--tmp", default="/tmp/robot")
    a = ap.parse_args()
    rep = validate(a.skeleton, a.atlas, a.png, ROBOT_MESH_SLOTS, a.tmp)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
