#!/usr/bin/env python3
"""端到端驗證:PSD 拆件 → S3 generate_mesh → 對照 Award 真實生產 mesh(held-out 標的)。

背景(見 STATE.md 候選 #1):main_draw 是 S3 的調校標的;Award 機器人是**未參與調校的
held-out 生產標的**,拿來測 S3 泛化。Award 中為 mesh 的 3 件:光暈 / 左手 / 身體。

重要差異(本次發現):
  - main_draw 4 mesh = **unweighted + deform-timeline** 驅動變形。
  - Award 機器人 3 mesh = **weighted(骨骼蒙皮)+ 無 deform timeline**。
    → AC5(真實位移場轉移閘)基於 deform timeline,對這些件 **N/A**;
      weighted 蒙皮是另一種變形模式(deform_eval 不覆蓋)。誠實標記,不假裝通過。

因此本閘做**靜態對照**(apples-to-apples,同一張 atlas-crop alpha):
  gen mesh(generate_mesh_v2 auto)的覆蓋 IoU  vs  藝術家真實 mesh 的覆蓋 IoU
  + evaluate_mesh 的結構 AC(無退化/孤兒、頂點預算、hull 排最前、格式)。

用 atlas-crop 當來源 alpha 而非 PSD:藝術家 mesh 的 uvs 對映 atlas 貼圖,artist_iou 在
atlas 像素空間量;gen mesh 也用同一張 crop → 兩者對同一 silhouette 比,scale/來源一致。
(PSD↔atlas 已於 session 006 確認同素材 alpha-IoU 0.92~0.99。)
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from validate_against_real import artist_iou
from generate_mesh_v2 import generate as gen_v2

PIECES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def artist_mesh_stats(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    nv = len(a["uvs"]) // 2
    weighted = len(a["vertices"]) != len(a["uvs"])
    return {"vertices": nv, "triangles": len(a["triangles"]) // 3,
            "hull": a.get("hull"), "weighted": weighted}


def run_piece(sk, atlas, png, slot, name, tmp_dir, iou_margin=0.0):
    sub = extract(atlas, png, name)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    mesh = gen_v2(crop, mode="auto")
    ev = evaluate(mesh, mask)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]
    base = artist_iou(sk, slot, name, mask)
    am = artist_mesh_stats(sk, slot, name)

    # 結構 AC:排除 AC1(門檻改用 artist IoU baseline)與 AC3(絕對 64 預算);
    # AC3 改用「相對經濟」——生成頂點數 ≤ 藝術家同件頂點數(64 是窗簾件校準,對有機件過嚴)。
    gen_nv = len(mesh["uvs"]) // 2
    struct_keys = [k for k in ev["criteria"] if k not in ("AC1_iou", "AC3_vertex_budget")]
    struct_pass = all(ev["criteria"][k]["pass"] for k in struct_keys)
    econ_pass = gen_nv <= am["vertices"]

    return {
        "piece": name,
        "region_px": [int(sub.shape[1]), int(sub.shape[0])],
        "artist_mesh": am,
        "gen_mesh": {"vertices": gen_nv, "triangles": len(mesh["triangles"]) // 3,
                     "hull": mesh["hull"], "mode": mesh.get("_mode"),
                     "density": mesh.get("_density")},
        "AC_iou": {"gen": round(gen_iou, 4), "artist_baseline": round(base, 4),
                   "pass": gen_iou >= base - iou_margin},
        "AC_struct": {k: ev["criteria"][k] for k in struct_keys},
        "AC_struct_pass": struct_pass,
        "AC_econ_vs_artist": {"gen_verts": gen_nv, "artist_verts": am["vertices"],
                              "pass": econ_pass},
        "AC_real_deform": "N/A(weighted 蒙皮,無 deform timeline)",
        "overall_pass": bool(gen_iou >= base - iou_margin and struct_pass and econ_pass),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reports = [run_piece(sk, a.atlas, a.png, p, p, a.tmp) for p in PIECES]
    allpass = all(r["overall_pass"] for r in reports)
    print(json.dumps({"pieces": reports, "all_pass": allpass},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
