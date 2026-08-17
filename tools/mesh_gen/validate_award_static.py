#!/usr/bin/env python3
"""S3 對第二個真實資產(Award 機器人拆件)做**靜態**驗收。

與 main_draw(4 個 unweighted strip mesh + deform timeline)不同,Award 的機器人 mesh 是
**weighted(靠骨骼權重動,無 deform timeline)且形狀為 blob**。因此:
  - deform 閘不適用(無 deform timeline)→ 改做靜態幾何對照。
  - blob 形狀 → generate_mesh_v2 auto 模式會回退 v1(Delaunay);這是 v1 首次對「真實生產
    mesh 之 blob」驗收(main_draw 全是 strip 走 v2)。

對每個 mesh 件:
  1. 從 Award atlas 裁出 region(藝術家 mesh 的精確來源貼圖)→ alpha mask。
  2. generate_mesh_v2 → 生成 mesh。
  3. 覆蓋率 IoU:生成 mesh vs mask,對照「藝術家 mesh 自身覆蓋率」(artist baseline)。
  4. 頂點/三角/hull 預算:生成 vs 藝術家。
  5. hull 輪廓貼合度:生成 hull polygon vs 藝術家 hull polygon 的 IoU(兩者都是外周多邊形)。

判準(靜態):覆蓋率 IoU >= 藝術家 baseline - margin;頂點預算 <= 藝術家 × 1.5(精簡度)。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from evaluate_mesh import evaluate, load_mask
from atlas_crop import extract
from generate_mesh_v2 import generate as gen_v2


def _skin_att(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)[slot][name]


def artist_coverage_iou(a, mask):
    """藝術家 mesh 的三角面覆蓋率(填三角形 vs alpha)。適用 weighted(只用 uvs/triangles)。"""
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0


def hull_polygon_iou(a_uvs, a_hull, m_uvs, m_hull, mask_shape):
    """兩個 hull 外周多邊形填滿後的 IoU(輪廓貼合度)。"""
    H, W = mask_shape

    def fill(uvs, nh):
        uvs = np.array(uvs).reshape(-1, 2)[:nh]
        poly = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
        img = np.zeros((H, W), np.uint8)
        cv2.fillPoly(img, [np.round(poly).astype(np.int32)], 1)
        return img
    ai = fill(a_uvs, a_hull)
    mi = fill(m_uvs, m_hull)
    inter = np.logical_and(ai, mi).sum()
    union = np.logical_or(ai, mi).sum()
    return float(inter / union) if union else 0.0


def validate_part(sk, atlas, png, slot, name, tmp_dir, iou_margin=0.03, budget_mult=1.5):
    sub = extract(atlas, png, name)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    mesh = gen_v2(crop, mode="auto")
    my_nv = len(mesh["uvs"]) // 2
    my_iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]

    a = _skin_att(sk, slot, name)
    art_nv = len(a["uvs"]) // 2
    art_tris = len(a["triangles"]) // 3
    art_hull = a["hull"]
    base_iou = artist_coverage_iou(a, mask)
    h_iou = hull_polygon_iou(a["uvs"], art_hull, mesh["uvs"], mesh["hull"], mask.shape)

    iou_pass = my_iou >= base_iou - iou_margin
    budget_pass = my_nv <= art_nv * budget_mult
    return {
        "part": name,
        "region": {"w": int(mask.shape[1]), "h": int(mask.shape[0]),
                   "aspect": round(mask.shape[0] / mask.shape[1], 2)},
        "generated": {"mode": mesh.get("_mode"), "vertices": my_nv,
                      "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3},
        "artist": {"vertices": art_nv, "hull": art_hull, "triangles": art_tris,
                   "weighted": len(a["vertices"]) != len(a["uvs"])},
        "AC_coverage_iou": {"generated": round(my_iou, 4),
                            "artist_baseline": round(base_iou, 4),
                            "margin": iou_margin, "pass": bool(iou_pass)},
        "AC_vertex_budget": {"generated": my_nv, "artist": art_nv,
                             "limit": round(art_nv * budget_mult, 1), "pass": bool(budget_pass)},
        "hull_polygon_iou": round(h_iou, 4),
        "overall_pass": bool(iou_pass and budget_pass),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")  # multipage: extract auto-resolves page
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    parts = [("機器人拆件/光暈", "機器人拆件/光暈"),
             ("機器人拆件/身體", "機器人拆件/身體"),
             ("機器人拆件/左手", "機器人拆件/左手")]
    reps = []
    for slot, name in parts:
        reps.append(validate_part(sk, a.atlas, a.png, slot, name, a.tmp))
    allpass = all(r["overall_pass"] for r in reps)
    print(json.dumps({"parts": reps, "all_pass": allpass}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
