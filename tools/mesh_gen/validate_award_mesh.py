#!/usr/bin/env python3
"""端到端「PSD/atlas 件 → S3 generate_mesh → 對照 Award 真實生產 mesh」驗收。

與 validate_against_real.py(main_draw)的差異:
- main_draw 的 4 個 mesh 是 **unweighted 且有 deform timeline** → 用真實位移場轉移驗變形。
- Award 機器人件(光暈/身體/左手)是 **weighted 且無 deform timeline**(靠骨骼權重 warp,
  非逐頂點 deform)→ **沒有 deform 位移場真值可轉移**。故本驗收只做「靜態覆蓋 IoU +
  拓樸/格式 AC」對照藝術家真值,不跑 deform 閘(避免用未校準合成場產生假判定,見 STATE)。

真值來源:直接從 Award atlas 切出 region alpha(與藝術家 mesh 的 uvs 同一貼圖幀),
藝術家 mesh 的 region-local uvs 直接落在此 alpha 上 → 生成 mesh 與藝術家 mesh 對同一 alpha
比覆蓋率,scale 一致、可直接比較。

判準(對齊 validate_against_real 精神):生成 mesh IoU ≥ 藝術家自身覆蓋率(baseline)- margin
且格式/預算/無孤兒/無退化三角全過 → overall_pass。
"""
import argparse, json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from evaluate_mesh import evaluate
from validate_against_real import artist_iou
from atlas_crop import extract

# Award 中 type=mesh 的機器人件(右手/頭是 region,不在此列)
MESH_PIECES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def artist_topology(sk, slot, name):
    skin = sk["skins"]
    att = (skin[0]["attachments"] if isinstance(skin, list) else skin["attachments"])
    a = att[slot][name]
    nv = len(a["uvs"]) // 2
    weighted = len(a["vertices"]) != len(a["uvs"])
    return {"vertices": nv, "triangles": len(a["triangles"]) // 3,
            "hull": a["hull"], "weighted": weighted}


def validate_piece(sk, atlas, png, name, gen_fn, tmp_dir, iou_margin=0.0, budget=100):
    sub = extract(atlas, png, name)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = (sub[:, :, 3] > 8).astype(np.uint8) if (sub.ndim == 3 and sub.shape[2] == 4) \
        else (cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY) > 8).astype(np.uint8)

    mesh = gen_fn(crop)
    if isinstance(mesh, tuple):
        mesh = mesh[0]

    rep = evaluate(mesh, mask, vertex_budget=budget)   # 生成 mesh 全 AC
    gen_iou = rep["criteria"]["AC1_iou"]["value"]
    base = round(artist_iou(sk, name, name, mask), 4)
    art = artist_topology(sk, name, name)

    fmt_ok = all(rep["criteria"][k]["pass"] for k in
                 ("AC4_format", "AC2b_degenerate", "AC2c_orphans", "AC3_vertex_budget"))
    iou_ok = gen_iou >= base - iou_margin

    return {
        "piece": name,
        "generated": {"vertices": rep["vertices"], "triangles": rep["triangles"],
                      "hull": rep["hull"], "mode": mesh.get("_mode")},
        "artist": art,
        "coverage_iou": {"generated": gen_iou, "artist_baseline": base,
                         "pass": bool(iou_ok)},
        "topology_ac_pass": bool(fmt_ok),
        "ac_detail": {k: rep["criteria"][k] for k in
                      ("AC4_format", "AC2b_degenerate", "AC2c_orphans", "AC3_vertex_budget")},
        "overall_pass": bool(iou_ok and fmt_ok),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--gen", choices=["v1", "v2"], default="v1")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--pieces", nargs="*", default=MESH_PIECES)
    # 對這批「不規則團塊件」(aspect<1.2,auto 一律回退 v1 Delaunay),
    # eps=0.002 使輪廓保真度貼齊藝術家 mesh(見 knowledge/s3-award-mesh-match.md)。
    ap.add_argument("--epsilon", type=float, default=0.002)
    ap.add_argument("--budget", type=int, default=100)  # 藝術家件本身 78~98v,64 太緊
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    if a.gen == "v1":
        from generate_mesh import generate as g
        gen = lambda p: g(p, epsilon_frac=a.epsilon)
    else:
        from generate_mesh_v2 import generate as g
        gen = lambda p: g(p, mode="auto")

    reports = [validate_piece(sk, a.atlas, a.png, name, gen, a.tmp, budget=a.budget)
               for name in a.pieces]
    allpass = all(r["overall_pass"] for r in reports)
    print(json.dumps({"gen": a.gen, "overall_pass": allpass, "pieces": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
