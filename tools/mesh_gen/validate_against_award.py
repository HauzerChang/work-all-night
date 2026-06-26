#!/usr/bin/env python3
"""端到端「件 → S3 mesh → 對照真實生產 mesh」驗收(對 Award 機器人拆件)。

STATE 下一步候選 #1:用機器人 mesh 件(光暈/身體/左手)跑 S3 generate_mesh_v2,
與 Award 真實 mesh 做 IoU 對照 —— 對真實生產標的做端到端驗收。

關鍵發現(2026-06-26,本工具建立時校正):
  Award 的 mesh attachment `uvs` 是 **region-local [0,1]、v-down**(非 page-relative
  atlas UV)。把 artist uvs 直接 (u*W, v*H) 疊到 atlas_crop 切出的 region 遮罩上,
  三件 artist IoU = 0.968/0.979/0.976 → 證實 (a) uvs 為 region-local、v-down,
  (b) atlas_crop 的 CW 去旋轉對 rotate=true 件(光暈/身體)正確對齊。
  這也讓 artist mesh 與 generate_mesh_v2 輸出落在同一座標系,IoU 可直接比。

AC(per piece):
  - AC_iou:generated mesh 覆蓋率 >= artist 覆蓋率 - margin(對齊藝術家基準,非武斷 0.95)。
  - AC_topology:generated 為合法 mesh(格式/0 退化/0 孤兒,由 evaluate_mesh 把關)。
  - 頂點預算:generated nv <= budget。
  ⚠️ deform 閘不適用:這 5 件在 Award **無 deform timeline**(靠骨骼/權重變形),
     沒有真實逐頂點位移場可轉移;依 RULES 不用未校準的合成 stress_field。

apples-to-apples 保證:generated 與 artist 都在「atlas region 去旋轉後的局部像素框」評分。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import parse_atlas, extract
from evaluate_mesh import evaluate
from generate_mesh_v2 import generate as gen_v2

MESH_SLOTS = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def region_mask(sub):
    if sub.ndim == 3 and sub.shape[2] == 4:
        a = sub[:, :, 3]
    else:
        a = sub if sub.ndim == 2 else cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    return (a > 8).astype(np.uint8)


def artist_iou(att, slot, mask):
    """artist mesh(region-local uvs, v-down)對 region 遮罩的覆蓋率。"""
    a = att[slot][slot]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0, len(uvs), len(tris), int(a["hull"])


def validate_slot(skeleton, atlas, png, att, slot, tmp_dir, budget, margin):
    sub = extract(atlas, png, slot)
    mask = region_mask(sub)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)

    mesh = gen_v2(crop, mode="auto")
    ev = evaluate(mesh, mask, vertex_budget=budget)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]
    gnv = ev["vertices"]

    a_iou, anv, antri, ahull = artist_iou(att, slot, mask)

    iou_pass = gen_iou >= a_iou - margin
    # 拓樸合法性:沿用 evaluate_mesh 的格式/退化/孤兒(不含其武斷的 0.95 IoU 與 centroid)
    topo = (ev["criteria"]["AC4_format"]["pass"]
            and ev["criteria"]["AC2b_degenerate"]["pass"]
            and ev["criteria"]["AC2c_orphans"]["pass"])
    budget_pass = ev["criteria"]["AC3_vertex_budget"]["pass"]

    return {
        "slot": slot,
        "region_wh": [mask.shape[1], mask.shape[0]],
        "generated": {"mode": mesh.get("_mode"), "vertices": gnv,
                      "triangles": ev["triangles"], "hull": mesh["hull"]},
        "artist": {"vertices": anv, "triangles": antri, "hull": ahull},
        "AC_iou": {"generated": round(gen_iou, 4), "artist_baseline": round(a_iou, 4),
                   "margin": margin, "pass": iou_pass},
        "AC_topology": {"pass": bool(topo),
                        "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                        "orphans": ev["criteria"]["AC2c_orphans"]["value"]},
        "AC_budget": {"pass": bool(budget_pass), "value": gnv, "budget": budget},
        "overall_pass": bool(iou_pass and topo and budget_pass),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")  # 多頁:atlas_crop 自動依 region.page 取 Award/Award2
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--budget", type=int, default=120)
    ap.add_argument("--margin", type=float, default=0.03)
    a = ap.parse_args()

    sk = json.load(open(a.skeleton))
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)

    reports = [validate_slot(sk, a.atlas, a.png, att, s, a.tmp, a.budget, a.margin)
               for s in MESH_SLOTS]
    overall = all(r["overall_pass"] for r in reports)
    print(json.dumps({"overall_pass": overall, "pieces": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
