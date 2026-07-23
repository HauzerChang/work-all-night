#!/usr/bin/env python3
"""端到端 AC:PSD 件 → S3 mesh 生成 → 對照 Award 真實生產 mesh。

背景(2026-07-23 發現):Award 機器人 3 件(光暈/身體/左手)在生產 spine 都是
**weighted mesh**,且**沒有任何 deform timeline** 引用它們 —— 它們靠骨骼加權蒙皮
(bone-driven skinning)變形,而非 deform 位移場。因此:

  * 靜態輪廓/覆蓋率(IoU)可直接對照 → 本工具做此比對。
  * deform 閘(transfer_deform_check)**不適用** —— 那是給「deform-driven」mesh
    (如 main_draw 窗簾)的閘;bone-weighted 件的耐變形屬 S3 加權(BBW)課題,尚未建。

素材等價性:log 006 已用 alpha-IoU 0.92~0.99 確認「PSD 切件 == atlas 生產貼圖」(同素材,
0.70 縮放)。故本工具直接用 Award atlas region alpha 當來源(與藝術家 mesh 同一 crop 座標系,
IoU 可直接對照),等價於 PSD→件→(等同)→region alpha→mesh。

AC:
  AC1 覆蓋率:生成 mesh IoU ≥ 藝術家 mesh 對自身 alpha 的 IoU − margin。
  AC2 預算  :生成頂點/三角數在合理預算內(不遠超藝術家;藝術家 weighted 頂點數為 uvs//2)。
  AC3 靜態拓樸:生成 mesh setup pose 0 自交 / 0 退化。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from validate_against_real import artist_iou
import deform_eval as de

ROBOT_PIECES = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def artist_budget(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    nv = len(a["uvs"]) // 2
    ntri = len(a["triangles"]) // 3
    weighted = len(a["vertices"]) != nv * 2
    return nv, ntri, weighted


def static_topology(mesh):
    v = mesh["vertices"]
    s = np.column_stack([v[0::2], v[1::2]])
    t = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    signs = [de.signed_area(s, x) > 0 for x in t]
    r = de.check(s, t, signs)
    return {"self_intersections": r["self_intersections"], "degenerate": r["degenerate"]}


def compare_one(sk, atlas, png, slot, name, tmp_dir, iou_margin=0.02):
    sub = extract(atlas, png, name)
    crop = os.path.join(tmp_dir, "_awd_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)
    H, W = mask.shape

    base = artist_iou(sk, slot, name, mask)
    a_nv, a_tri, weighted = artist_budget(sk, slot, name)

    from generate_mesh_v2 import generate as gen
    # 自主收斂:對照藝術家基準覆蓋率,頂點預算對齊藝術家(允許少量餘裕)
    mesh = gen(crop, mode="auto", target_coverage=base - iou_margin,
               vertex_budget=int(a_nv * 1.5))

    gen_iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
    g_nv = len(mesh["uvs"]) // 2
    g_tri = len(mesh["triangles"]) // 3
    topo = static_topology(mesh)

    ac1 = gen_iou >= base - iou_margin
    # 預算:生成頂點數不超過藝術家 1.5×(自動化允許略多,仍需在預算內)
    ac2 = g_nv <= max(a_nv * 1.5, a_nv + 20)
    ac3 = topo["self_intersections"] == 0 and topo["degenerate"] == 0
    return {
        "piece": name,
        "region": f"{W}x{H}",
        "artist": {"nv": a_nv, "tris": a_tri, "weighted": weighted, "iou": round(base, 4)},
        "generated": {"nv": g_nv, "tris": g_tri, "mode": mesh.get("_mode"), "iou": round(gen_iou, 4)},
        "AC1_coverage": {"gen": round(gen_iou, 4), "baseline": round(base, 4),
                         "margin": iou_margin, "pass": bool(ac1)},
        "AC2_budget": {"gen_nv": g_nv, "artist_nv": a_nv, "pass": bool(ac2)},
        "AC3_static_topology": {**topo, "pass": bool(ac3)},
        "overall_pass": bool(ac1 and ac2 and ac3),
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
    reps = []
    for name in ROBOT_PIECES:
        reps.append(compare_one(sk, a.atlas, a.png, name, name, a.tmp, a.margin))
    out = {"pieces": reps, "all_pass": all(r["overall_pass"] for r in reps),
           "note": "deform 閘不適用:robot 件為 bone-weighted、無 deform timeline"}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["all_pass"] else 1)


if __name__ == "__main__":
    main()
