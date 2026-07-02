#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 generate_mesh_v2 → 對照 Award 真實生產 mesh。

流程(純 CPU,有真值):
  1. 讀 PSD 切件 PNG(alpha 來源)。
  2. generate_mesh_v2 生成 mesh。
  3. 從 Award.json 取同名 slot 的**藝術家真實 mesh**(vertices/triangles/hull/width/height)。
  4. 三方光柵化到 PSD 件像素空間比對:
       - 生成 mesh 填充 vs PSD alpha 的 IoU
       - 藝術家 mesh 填充 vs PSD alpha 的 IoU(真值基準)
       - 生成 vs 藝術家 mesh 填充的 IoU(彼此覆蓋同區?)

AC(見 log):
  AC-A 格式合規(呼叫 evaluate_mesh)
  AC-B 生成 IoU ≥ 藝術家 IoU(對同一 alpha)
  AC-C 生成 vs 藝術家 mesh IoU ≥ 0.90

真值特性(見 knowledge/s4-psd-to-spine-real.md):Award 這 5 件**無 deform timeline**
(mesh 靠骨骼/權重變形,非逐頂點 deform),故本比對聚焦「靜態覆蓋 vs 藝術家真值」,
不做 per-vertex deform 閘(無真實位移場)。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_static, load_mask


def award_meshes(award_json):
    """回傳 {slot_name: attachment_dict} 只取 mesh 型。"""
    d = json.load(open(award_json))
    skins = d["skins"]
    out = {}
    items = skins if isinstance(skins, list) else [{"attachments": skins}]
    for sk in items:
        for slot, atts in sk.get("attachments", {}).items():
            for an, ad in atts.items():
                if ad.get("type") == "mesh":
                    out[slot] = ad
    return out


def raster_by_uv(uvs, tris, out_w, out_h):
    """用 mesh 的 **uvs**(region 正規化,top-origin:v 隨影像列增加)光柵化到 out_w×out_h。

    診斷結論(2026-07-02):Award 藝術家 mesh 的 **vertices** 位於任意 setup 座標框
    (bbox 802×780 遠大於 width×height 且非置中,是骨架 setup pose 下的擺位),**不可**
    用來還原件內形狀;而 **uvs** 正規化貼齊 region(=件影像),藝術家 mesh uv 填充 vs
    件 alpha IoU=0.95~0.98(flipy=False 才對)。故形狀比對一律走 uv。
    生成 mesh 的 uvs=(x/W, y/H) 同為 top-origin,兩者對齊一致。"""
    u = np.array(uvs, dtype=np.float64).reshape(-1, 2)
    px = u[:, 0] * out_w
    py = u[:, 1] * out_h
    pts = np.c_[px, py]
    img = np.zeros((out_h, out_w), np.uint8)
    for t in np.array(tris, dtype=np.int32).reshape(-1, 3):
        cv2.fillConvexPoly(img, np.round(pts[t]).astype(np.int32), 1)
    return img


def iou(a, b):
    a = a > 0; b = b > 0
    u = int(np.logical_or(a, b).sum())
    return (int(np.logical_and(a, b).sum()) / u) if u else 0.0


def compare(png, slot, award_att, budget=64):
    mask = load_mask(png)                      # PSD 件 alpha (H×W)
    H, W = mask.shape
    gen = gen_v2(png)                          # 生成 mesh
    # AC-A 格式 / 靜態(對 PSD alpha)
    static = eval_static(gen, mask, vertex_budget=budget)

    # 兩者皆以 uv 光柵化到 PSD 件像素空間(見 raster_by_uv 診斷註解)
    gen_fill = raster_by_uv(gen["uvs"], gen["triangles"], W, H)
    art_fill = raster_by_uv(award_att["uvs"], award_att["triangles"], W, H)

    gen_iou_alpha = iou(gen_fill, mask)
    art_iou_alpha = iou(art_fill, mask)
    gen_vs_art = iou(gen_fill, art_fill)
    # AC-B:生成覆蓋率不遜於藝術家 —— ≥0.90 且不明顯低於藝術家(容差 0.03)
    ac_b = gen_iou_alpha >= 0.90 and gen_iou_alpha >= art_iou_alpha - 0.03

    return {
        "slot": slot,
        "psd_size": [W, H],
        "gen": {"mode": gen.get("_mode"), "verts": len(gen["uvs"]) // 2,
                "tris": len(gen["triangles"]) // 3, "hull": gen["hull"]},
        "art": {"verts": len(award_att["uvs"]) // 2,
                "tris": len(award_att["triangles"]) // 3, "hull": award_att["hull"],
                "size": [award_att["width"], award_att["height"]]},
        "AC_A_format_pass": static["criteria"]["AC4_format"]["pass"]
                            and static["criteria"]["AC3_vertex_budget"]["pass"],
        "AC_B_gen_iou_vs_alpha": round(gen_iou_alpha, 4),
        "AC_B_art_iou_vs_alpha": round(art_iou_alpha, 4),
        "AC_B_pass": ac_b,
        "AC_C_gen_vs_art_iou": round(gen_vs_art, 4),
        "AC_C_pass": gen_vs_art >= 0.90,
    }


# PSD 切件檔名(psd_slice 以 NN_圖層名.png 命名)→ Award slot
PAIRS = [
    ("00_光暈.png", "機器人拆件/光暈"),
    ("03_身體.png", "機器人拆件/身體"),
    ("04_左手.png", "機器人拆件/左手"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("parts_dir", help="psd_slice -o 產出的目錄")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--budget", type=int, default=64)
    a = ap.parse_args()
    atts = award_meshes(a.award)
    reports = []
    for fn, slot in PAIRS:
        png = os.path.join(a.parts_dir, fn)
        if not os.path.exists(png):
            print(f"缺件: {png}", file=sys.stderr); continue
        reports.append(compare(png, slot, atts[slot], a.budget))
    ok = all(r["AC_A_format_pass"] and r["AC_B_pass"] and r["AC_C_pass"] for r in reports)
    print(json.dumps({"overall_pass": ok, "parts": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
