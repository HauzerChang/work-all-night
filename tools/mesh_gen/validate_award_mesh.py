#!/usr/bin/env python3
"""S3×S4 端到端整合 AC — 對「真實生產 mesh」(Award 機器人拆件)驗證生成器。

與 validate_against_real.py 的差別(不同 regime):
  - main_draw 4 mesh = **unweighted + 有 deform timeline**(窗簾/陰影)→ 閘是「真實位移場
    轉移後 0 自交/0 翻面」;拓樸用 strip(deform-robust)。
  - Award 機器人 3 mesh(光暈/左手/身體)= **weighted + 無 deform timeline**
    (靠骨骼/權重變形,非逐頂點 deform,見 knowledge/s4-psd-to-spine-real.md)。
    這裡沒有 per-vertex deform 可轉移 → **deform 閘 N/A**;真正的品質標的是
    「**覆蓋率保真** + 拓樸有效」,以藝術家真實 mesh 為 ground truth。

流程(每件):
  1. atlas 切真實貼圖 region 當 canvas(uvs 的原生 0..1 空間,免配準猜測)。
  2. 藝術家 mesh:覆蓋率 IoU(baseline)+ UV-space 拓樸(自交/翻面/退化)。
     ── 評估器自我校驗:藝術家真值必須拓樸乾淨,否則不信其判定(RULES「先驗評估器」)。
  3. 生成器(v1 Delaunay,非 strip:這些是 blob/身體形,長寬比 <1.2):
     **AC 驅動的 auto-epsilon 搜尋**(≤5 輪,對應 RULES 迭代預算):由粗到細掃 epsilon,
     取**第一個**同時滿足「覆蓋率 ≥ baseline−margin、nv ≤ 藝術家 nv、拓樸乾淨」的最省頂點解。
  4. 判定:覆蓋率達標 + 拓樸乾淨 + 頂點預算 ≤ 藝術家。

weighted mesh 只需 uvs+triangles 即可做覆蓋率與 UV 拓樸(與權重無關)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
import deform_eval as de
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from generate_mesh import generate as gen_v1, EPS_SCHEDULE   # 排程單一真相來源(generate_mesh)

ROBOT_MESH_SLOTS = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def _uvs_tris(a):
    return (np.array(a["uvs"], dtype=np.float64).reshape(-1, 2),
            np.array(a["triangles"], dtype=np.int32).reshape(-1, 3))


def uv_topology(uvs, tris):
    """在 UV(= 貼圖版面)空間檢查三角網:自交/翻面/退化。
    對『無 deform』的靜態 mesh,UV 平面有效性就是拓樸正確性的不變量。"""
    signs = [de.signed_area(uvs, t) > 0 for t in tris]
    return de.check(uvs, tris, signs)


def coverage_iou(uvs, tris, mask):
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    u = np.logical_or(recon, m).sum()
    return float(np.logical_and(recon, m).sum() / u) if u else 0.0


def gen_mesh_topology(mesh):
    uvs = np.array(mesh["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    return uv_topology(uvs, tris)


def validate_slot(sk_atts, slot, atlas_path, png_path, tmp_dir, margin):
    a = sk_atts[slot][slot]
    uvs_a, tris_a = _uvs_tris(a)
    artist_nv = len(uvs_a)

    sub = extract(atlas_path, png_path, slot)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    art_topo = uv_topology(uvs_a, tris_a)
    art_iou = coverage_iou(uvs_a, tris_a, mask)
    art_clean = (art_topo["self_intersections"] == 0 and art_topo["triangle_flips"] == 0
                 and art_topo["degenerate"] == 0)

    target = art_iou - margin
    rounds = []
    chosen = None
    for eps in EPS_SCHEDULE:
        mesh, _ = gen_v1(crop, epsilon_frac=eps)
        gnv = len(mesh["uvs"]) // 2
        giou = evaluate(mesh, mask, vertex_budget=artist_nv)["criteria"]["AC1_iou"]["value"]
        gtopo = gen_mesh_topology(mesh)
        gclean = (gtopo["self_intersections"] == 0 and gtopo["triangle_flips"] == 0
                  and gtopo["degenerate"] == 0)
        ok = (giou >= target) and (gnv <= artist_nv) and gclean
        rounds.append({"epsilon": eps, "nv": gnv, "hull": mesh["hull"],
                       "iou": round(giou, 4), "clean": gclean, "pass": ok})
        if ok:
            chosen = {"epsilon": eps, "nv": gnv, "hull": mesh["hull"], "tris": len(mesh["triangles"]) // 3,
                      "iou": round(giou, 4), "self_intersections": gtopo["self_intersections"],
                      "triangle_flips": gtopo["triangle_flips"], "degenerate": gtopo["degenerate"]}
            break

    return {
        "slot": slot,
        "canvas": f'{sub.shape[1]}x{sub.shape[0]} (atlas ~0.70 scale)',
        "artist": {"nv": artist_nv, "hull": int(a["hull"]), "tris": len(tris_a),
                   "coverage_iou": round(art_iou, 4), "uv_topo_clean": art_clean,
                   "weighted": len(a["vertices"]) != artist_nv * 2, "has_deform": False},
        "evaluator_self_check": {"artist_topo_clean": art_clean,
                                 "note": "藝術家真值須拓樸乾淨才信閘判定"},
        "generated": chosen,
        "search_rounds": rounds,
        "target_iou": round(target, 4),
        "pass": (chosen is not None) and art_clean,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--margin", type=float, default=0.005,
                    help="覆蓋率容差:生成 IoU ≥ 藝術家 baseline − margin 即算達標")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--slots", nargs="*", default=ROBOT_MESH_SLOTS)
    a = ap.parse_args()

    sk = json.load(open(a.skeleton))
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)

    reports = [validate_slot(atts, s, a.atlas, a.png, a.tmp, a.margin) for s in a.slots]
    overall = all(r["pass"] for r in reports)
    out = {"assets": os.path.basename(a.skeleton), "margin": a.margin,
           "results": reports, "overall_pass": overall}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
