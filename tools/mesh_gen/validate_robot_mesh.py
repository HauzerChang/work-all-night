#!/usr/bin/env python3
"""在「真實生產 weighted mesh」上驗證 S3 生成器 —— 端到端 PSD→件→mesh 的收尾對照。

背景(見 STATE.md 下一步候選 #1):先前 S3 v1/v2 只在 main_draw 的 4 個 **unweighted**、
簡單拓樸(hull 12–16)mesh 上驗過。這裡把它推到真實生產標的:Award(機器人 big win)裡
3 個 **weighted** mesh —— `機器人拆件/光暈`(hull 78)、`左手`(hull 42)、`身體`(hull 40),
遠比窗簾複雜。有藝術家真值可比,是端到端能力的關鍵一步。

⚠️ 與 main_draw 的差異(決定本閘只做「靜態 + 自身穩健」,不做 deform 轉移):
  1. 這 3 個 mesh 是 **weighted**(vertices.len != uvs.len),deform_eval 目前只支援 unweighted。
  2. Award 裡這 3 個 mesh **沒有 deform timeline**(靠骨骼 skinning 變形,非 deform)。
  → 「真實位移場轉移」閘不適用。改用:① 靜態 IoU vs 藝術家覆蓋率基準
     ② evaluate_mesh 的結構健全度(重心在內/退化/孤兒/頂點預算)。

真值來源:Award.atlas + Award.png/Award2.png(atlas_crop 處理多頁 + rotate)。
"""
import argparse, json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from validate_against_real import artist_iou

ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def artist_topology(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    nv = len(a["uvs"]) // 2
    return {"vertices": nv, "hull": a["hull"], "triangles": len(a["triangles"]) // 3,
            "weighted": len(a["vertices"]) != len(a["uvs"])}


def validate_one(sk, atlas, png_hint, slot, name, gen_fn, tmp_dir):
    sub = extract(atlas, png_hint, name)
    crop = os.path.join(tmp_dir, "_robot_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    mesh = gen_fn(crop)
    if isinstance(mesh, tuple):
        mesh = mesh[0]

    # 頂點預算用「藝術家真值 + 餘裕」而非 main_draw 簡單 mesh 的 64
    # (這 3 個真實生產 mesh 藝術家自身就用了 78~98 頂點)。
    art_nv = artist_topology(sk, slot, name)["vertices"]
    ev = evaluate(mesh, mask, vertex_budget=max(110, art_nv + 12))
    iou = ev["criteria"]["AC1_iou"]["value"]
    base = artist_iou(sk, slot, name, mask)
    art = artist_topology(sk, slot, name)
    gen_nv = len(mesh["uvs"]) // 2

    # 結構健全度(不含 AC1 IoU 的絕對門檻 0.9,改用藝術家基準判 IoU)
    struct_ok = (ev["criteria"]["AC2a_centroid_in_mask"]["pass"]
                 and ev["criteria"]["AC2b_degenerate"]["pass"]
                 and ev["criteria"]["AC2c_orphans"]["pass"]
                 and ev["criteria"]["AC3_vertex_budget"]["pass"])

    return {
        "slot": slot,
        "region_hw": [int(mask.shape[1]), int(mask.shape[0])],
        "gen": {"mode": mesh.get("_mode"), "vertices": gen_nv, "hull": mesh["hull"],
                "triangles": len(mesh["triangles"]) // 3},
        "artist": art,
        "AC_iou": {"value": round(iou, 4), "artist_baseline": round(base, 4),
                   "pass": iou >= base - 0.0},
        "AC_struct": {"pass": bool(struct_ok),
                      "centroid_in_mask": ev["criteria"]["AC2a_centroid_in_mask"]["value"],
                      "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                      "orphans": ev["criteria"]["AC2c_orphans"]["value"],
                      "vertex_budget": ev["criteria"]["AC3_vertex_budget"]["pass"]},
        "overall_pass": bool(iou >= base and struct_ok),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--gen", choices=["v1", "v2"], default="v2")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    if a.gen == "v1":
        from generate_mesh import generate as g
        gen = lambda p: g(p)
    else:
        from generate_mesh_v2 import generate as g
        gen = lambda p: g(p, mode="auto")

    reports = []
    for name in ROBOT_MESHES:
        reports.append(validate_one(sk, a.atlas, a.png, name, name, gen, a.tmp))
    allpass = all(r["overall_pass"] for r in reports)
    print(json.dumps({"gen": a.gen, "results": reports, "all_pass": allpass},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
