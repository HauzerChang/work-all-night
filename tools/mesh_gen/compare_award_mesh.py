#!/usr/bin/env python3
"""端到端整合 AC:真實件 → S3 mesh → 對照 Award 生產 mesh(真值)。

背景(STATE 候選 #1,最高優先):Award(big win spine)裡機器人拆件的
光暈/身體/左手三件是**美術手做的生產 mesh**,可當 S3 生成器的外部真值。
本工具把「切件(atlas 生產貼圖,derotate 回邏輯朝向)→ generate_mesh_v2 → 量化」
與該件的**藝術家 mesh** 逐條對照,回報 pass/fail + 差距。

⚠️ 兩個已校準的事實(見 knowledge/s3-award-real-mesh.md):
1. Spine JSON 的 mesh `uvs` 是 **region 局部 0..1**(runtime 才透過 atlas region 貼回、
   含 rotate),不是整頁 atlas UV。故藝術家 uvs 直接 ×(W,H) 即像素座標
   (對 derotate 後的邏輯朝向切件,3 件 artist_iou 0.968~0.980 已驗證此慣例)。
2. 這 5 件在 Award **無 deform timeline**(靠骨骼權重變形,非逐頂點 deform)→
   本比對**不跑 deform 閘**(沒有真實位移場可轉移;絕不用未校準的合成壓力充數)。
   靜態輪廓保真(IoU)是這裡可信的量化軸。

判準:generated IoU(vs 生產貼圖 alpha)≥ artist mesh 自身 IoU(baseline) − margin,
且格式/退化/孤兒/頂點預算(evaluate_mesh)全過。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate as ev_mesh, load_mask
from validate_against_real import artist_iou
from generate_mesh_v2 import generate as gen_v2

# Award 中確認是 mesh 的機器人件(見 knowledge/s4-psd-to-spine-real.md)
ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def artist_stats(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    return {"vertices": len(a["uvs"]) // 2, "hull": a.get("hull"),
            "triangles": len(a["triangles"]) // 3,
            "weighted": len(a["vertices"]) != len(a["uvs"])}


def compare_one(sk, atlas, png, slot, name, tmp_dir, eps, budget, margin):
    sub = extract(atlas, png, name)                 # derotate 回邏輯朝向
    crop = os.path.join(tmp_dir, f"_{name.split('/')[-1]}.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    art = artist_stats(sk, slot, name)
    base = artist_iou(sk, slot, name, mask)

    mesh = gen_v2(crop, mode="auto", eps=eps, max_interior=80, min_dist=8)
    ev = ev_mesh(mesh, mask, vertex_budget=budget)
    giou = ev["criteria"]["AC1_iou"]["value"]

    iou_pass = giou >= base - margin
    fmt_pass = all(ev["criteria"][k]["pass"] for k in
                   ("AC4_format", "AC2b_degenerate", "AC2c_orphans", "AC3_vertex_budget"))
    return {
        "piece": name, "mode": mesh.get("_mode"),
        "artist": art,
        "generated": {"vertices": ev["vertices"], "hull": ev["hull"],
                      "triangles": ev["triangles"],
                      "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                      "orphans": ev["criteria"]["AC2c_orphans"]["value"]},
        "AC_iou": {"generated": round(giou, 4), "artist_baseline": round(base, 4),
                   "gap": round(giou - base, 4), "margin": margin, "pass": iou_pass},
        "AC_mesh_quality": {"pass": fmt_pass},
        "overall_pass": iou_pass and fmt_pass,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")  # 多頁:atlas_crop 依 region page 自動選
    ap.add_argument("--eps", type=float, default=0.002,
                    help="Douglas-Peucker 邊界簡化比例;細緻生產件用 0.002(見 knowledge)")
    ap.add_argument("--budget", type=int, default=140)
    ap.add_argument("--margin", type=float, default=0.0, help="容許低於藝術家基準的 IoU 邊際")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--pieces", nargs="*", default=ROBOT_MESHES)
    a = ap.parse_args()

    sk = json.load(open(a.skeleton))
    reports = [compare_one(sk, a.atlas, a.png, s, s, a.tmp, a.eps, a.budget, a.margin)
               for s in a.pieces]
    overall = all(r["overall_pass"] for r in reports)
    print(json.dumps({"overall_pass": overall, "eps": a.eps, "pieces": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
