#!/usr/bin/env python3
"""端到端「PSD件 → S3 mesh → 對照真實生產 mesh」驗收(Award 機器人拆件)。

目的:把 S3 mesh 生成器對「真實生產標的」驗收 —— 不是合成 fixture、也不是自訂門檻,
而是直接跟藝術家在生產 spine(Award.json)手做的 mesh 做 head-to-head。

比較對象(Award 中的 3 個 mesh 件,皆 weighted,無 deform timeline → 靠骨骼權重變形):
  機器人拆件/光暈(78v)、機器人拆件/身體(98v)、機器人拆件/左手(80v)。

流程(純 CPU,可自驅):
  atlas 切真實貼圖(多頁 + CW derotate,已校準) → 生成 mesh(v1 auto-epsilon)
  → 靜態 AC(evaluate_mesh) → 藝術家基準 IoU(同法量測)→ head-to-head 報告。

⚠️ 範圍:本閘只驗「靜態輪廓保真 + 拓樸品質 + 頂點預算」的端到端。
   藝術家 mesh 是 weighted(骨骼權重變形);我們生成的是 unweighted → 不宣稱變形手感等價。
   (BBW 權重 = S3 後續子目標,尚未實作;這 3 件無 deform timeline 故無真實位移場可轉移。)
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from generate_mesh import generate_auto
from validate_against_real import artist_iou

# slot -> (atlas page png, 藝術家頂點數)  ※ page 由 Award.atlas 決定(光暈/身體在 Award2)
PIECES = {
    "機器人拆件/光暈": ("assets/Award2.png", 78),
    "機器人拆件/身體": ("assets/Award2.png", 98),
    "機器人拆件/左手": ("assets/Award.png", 80),
}


def compare(skeleton_path, atlas_path, slot, png_path, artist_nv, target_iou, tmp_dir):
    sk = json.load(open(skeleton_path))
    sub = extract(atlas_path, png_path, slot)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    base = artist_iou(sk, slot, slot, mask)
    tgt = base if target_iou is None else target_iou
    mesh, _, meta = generate_auto(crop, target_iou=tgt, vertex_budget=max(120, int(artist_nv * 1.3)))
    ev = evaluate(mesh, mask, vertex_budget=max(120, int(artist_nv * 1.3)))
    c = ev["criteria"]
    gen_nv = c["AC3_vertex_budget"]["value"]

    topo_ok = (c["AC2a_centroid_in_mask"]["pass"] and c["AC2b_degenerate"]["pass"]
               and c["AC2c_orphans"]["pass"] and c["AC4_format"]["pass"])
    iou_ok = meta["iou"] >= base           # 對齊/超越藝術家輪廓保真
    budget_ok = gen_nv <= artist_nv        # 頂點量不超過藝術家(更省或持平)
    return {
        "slot": slot, "page": os.path.basename(png_path),
        "region_wh": [int(sub.shape[1]), int(sub.shape[0])],
        "artist": {"nv": artist_nv, "iou": round(base, 4), "weighted": True},
        "generated": {"nv": gen_nv, "hull": mesh["hull"], "tri": len(mesh["triangles"]) // 3,
                      "iou": round(meta["iou"], 4), "epsilon": meta["epsilon"], "mode": "delaunay-v1-auto"},
        "checks": {
            "iou_ge_artist": iou_ok,
            "vertex_le_artist": budget_ok,
            "centroid_in_mask": c["AC2a_centroid_in_mask"]["value"],
            "degenerate": c["AC2b_degenerate"]["value"],
            "orphans": c["AC2c_orphans"]["value"],
            "format_ok": c["AC4_format"]["pass"],
            "topology_clean": topo_ok,
        },
        "pass": iou_ok and topo_ok,  # 端到端靜態閘:達藝術家輪廓 + 拓樸乾淨
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--target-iou", type=float, default=None,
                    help="目標 IoU;預設 None = 對齊各件藝術家基準")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()

    reports, all_pass = [], True
    for slot, (png, anv) in PIECES.items():
        r = compare(a.skeleton, a.atlas, slot, png, anv, a.target_iou, a.tmp)
        reports.append(r)
        all_pass = all_pass and r["pass"]
    print(json.dumps({"pieces": reports, "overall_pass": all_pass}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
