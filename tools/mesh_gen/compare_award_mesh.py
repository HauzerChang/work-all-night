#!/usr/bin/env python3
"""端到端「PSD件 → S3 mesh → 對照 Award 真實 mesh」— 對真實生產標的驗收。

背景(STATE.md 最高優先塊):`robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手)在生產 spine
`Award` 中為 **weighted mesh**(靠骨骼權重變形,無 deform timeline)。因此:
  - **不能**套用 deform 閘(real_deform_field 需 unweighted vertices;且這些件無 deform 動畫)。
  - 有真值可比的是 **靜態輪廓覆蓋率(IoU)** 與 **頂點預算 / 拓樸有效性(setup pose)**。

驗收目標(AC):
  AC1 覆蓋率:生成 mesh 的 IoU >= 藝術家 mesh 的 IoU 基準 - margin(生成至少和藝術家一樣貼合輪廓)。
  AC2 拓樸有效(setup pose,靜態):生成 mesh 0 自交 / 0 退化三角。
  AC3 精簡度:生成 mesh 頂點數 <= 藝術家頂點數(不比藝術家更浪費)。

alpha 來源:用 atlas 切出的 region(與藝術家 uvs 同座標系,IoU 自一致)。
weighted mesh 判定:vertices.length != uvs.length。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
import deform_eval as de
from evaluate_mesh import evaluate, load_mask, mesh_pixel_coords
from atlas_crop import extract
from generate_mesh_v2 import generate as gen_v2


def artist_mesh(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)[slot][name]


def artist_iou(att, mask):
    """藝術家 mesh 三角填滿 vs alpha 的 IoU(uvs 對 weighted/unweighted 皆為標準 u,v 序列)。"""
    uvs = np.array(att["uvs"]).reshape(-1, 2)
    tris = np.array(att["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    return float(np.logical_and(recon, m).sum() / max(np.logical_or(recon, m).sum(), 1))


def static_topology(mesh):
    """生成 mesh 在 setup pose 的靜態拓樸有效性(自交 / 退化 / 翻面 vs 自身)。"""
    pts, W, H = mesh_pixel_coords(mesh)
    tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    setup_signs = [de.signed_area(pts, t) > 0 for t in tris]
    r = de.check(pts, tris, setup_signs)
    r["clean"] = (r["self_intersections"] == 0 and r["degenerate"] == 0)
    return r


def compare_one(sk, atlas, png, slot, name, tmp_dir, iou_margin=0.02):
    att = artist_mesh(sk, slot, name)
    a_uvs = np.array(att["uvs"]).reshape(-1, 2)
    a_verts = att["vertices"]
    a_nv = len(att["uvs"]) // 2
    weighted = len(a_verts) != len(att["uvs"])

    sub = extract(atlas, png, name)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)  # uint8 0/1

    mesh = gen_v2(crop, mode="auto")
    g_nv = len(mesh["uvs"]) // 2

    g_iou = evaluate(mesh, mask, vertex_budget=max(a_nv, 64))["criteria"]["AC1_iou"]["value"]
    a_iou = artist_iou(att, mask)
    topo = static_topology(mesh)

    ac1 = g_iou >= a_iou - iou_margin
    ac2 = topo["clean"]
    ac3 = g_nv <= a_nv
    return {
        "slot": slot,
        "artist": {"vertices": a_nv, "hull": att.get("hull"),
                   "triangles": len(att["triangles"]) // 3, "weighted": weighted},
        "generated": {"vertices": g_nv, "hull": mesh["hull"],
                      "triangles": len(mesh["triangles"]) // 3, "mode": mesh.get("_mode")},
        "AC1_coverage": {"gen_iou": round(g_iou, 4), "artist_iou": round(a_iou, 4),
                         "margin": iou_margin, "pass": bool(ac1)},
        "AC2_topology_setup": {**topo, "pass": bool(ac2)},
        "AC3_compactness": {"gen_nv": g_nv, "artist_nv": a_nv, "pass": bool(ac3)},
        "overall_pass": bool(ac1 and ac2 and ac3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    slots = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]
    reports = [compare_one(sk, a.atlas, a.png, s, s, a.tmp) for s in slots]
    allpass = all(r["overall_pass"] for r in reports)
    print(json.dumps({"reports": reports, "all_pass": allpass}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
