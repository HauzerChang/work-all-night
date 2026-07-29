#!/usr/bin/env python3
"""端到端 S3 驗收:件 alpha → 生成 mesh → 對照「真實生產 spine 的 mesh」(有真值)。

用途(2026-07-29 里程碑):把 S4(切件)與 S3(生成 mesh)串成端到端,並用真實生產資產
(機器人拆件 → Award spine 的 mesh)當 ground truth,量化「生成 mesh 是否達到藝術家品質」。

與 validate_against_real.py 的差別:
  - validate_against_real 針對 main_draw 的 **unweighted + 有 deform timeline** mesh,用真實逐頂點
    位移場轉移當變形閘。
  - 本工具針對 Award 的 **weighted + 無 deform timeline** mesh(靠骨骼權重變形,非逐頂點 deform)。
    真實位移場不存在 → 改用「相對耐變形」:對 gen 與 artist 兩套拓樸施加**同一** synthetic
    stress 場(deform_eval.stress_field,僅供相對比較,非絕對閘),比誰先自交/翻面。

量化條目(逐件):
  - AC_coverage : 生成 mesh 對件 alpha 的 IoU ≥ 藝術家真實 mesh 的 IoU − margin
  - AC_topology : 生成 mesh 在 setup 下 0 自交 / 0 翻面 / 0 退化 / 0 孤兒
  - AC_budget   : 生成頂點數 ≤ 藝術家頂點數 × budget_ratio
  - REL_robust  : 同一 stress 下 gen 自交數 ≤ artist 自交數(相對,不作 pass/fail 硬閘)

真值座標系:Spine mesh uvs 為 **region 局部正規化**(0..1,已由 main_draw 驗證),故
artist 像素座標 = uvs × [W,H](W,H = atlas 切件尺寸)。切件由 atlas_crop 取(多頁 + CW derotate)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
import deform_eval as de
from evaluate_mesh import evaluate, load_mask
from atlas_crop import extract
from generate_mesh_v2 import generate as genv2


def artist_mesh(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uvs = np.array(a["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    return uvs, tris, a["hull"]


def poly_iou(pts, tris, mask):
    H, W = mask.shape
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    return float(np.logical_and(recon, m).sum() / max(1, np.logical_or(recon, m).sum()))


def stress_topology(pts, tris, mag):
    """對一套 (pts像素, tris) 施加同一 synthetic stress 場,回傳自交/翻面數(相對比較用)。"""
    setup = pts.astype(np.float64)
    signs = [de.signed_area(setup, t) > 0 for t in tris]
    area = sum(abs(de.signed_area(setup, t)) for t in tris)
    deformed = de.stress_field(setup, mag)
    r = de.eval_pose(deformed, tris, signs, area)
    return r["self_intersections"], r["triangle_flips"]


def validate(skeleton_path, atlas_path, png_path, slot, name, tmp_dir,
             epsilon=0.002, margin=0.02, budget_ratio=1.5, stress_frac=0.35):
    sk = json.load(open(skeleton_path))
    sub = extract(atlas_path, png_path, name)
    crop = os.path.join(tmp_dir, "_region_ptm.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)
    H, W = mask.shape

    # 生成 mesh(v2 auto;非 strip 件會走 Delaunay 回退,epsilon 控制 hull 密度)
    mesh = genv2(crop, mode="auto", epsilon=epsilon)
    gpts, _, _ = _mesh_pixels(mesh, W, H)
    gtris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    gnv = len(mesh["uvs"]) // 2

    # 藝術家真值
    a_uvs, a_tris, a_hull = artist_mesh(sk, slot, name)
    apts = np.column_stack([a_uvs[:, 0] * W, a_uvs[:, 1] * H])
    anv = len(a_uvs)

    iou_gen = evaluate(mesh, mask, vertex_budget=10 ** 6)["criteria"]["AC1_iou"]["value"]
    iou_art = round(poly_iou(apts, a_tris, mask), 4)

    ev = evaluate(mesh, mask, vertex_budget=10 ** 6)["criteria"]
    setup_clean = (ev["AC2b_degenerate"]["value"] == 0 and ev["AC2c_orphans"]["value"] == 0)
    # setup 自交/翻面(用 stress mag=0)
    gsi0, gf0 = stress_topology(gpts, gtris, 0.0)
    setup_clean = setup_clean and gsi0 == 0 and gf0 == 0

    # 相對耐變形:同一 stress(以件短邊比例校準幅度)
    mag = stress_frac * min(W, H)
    gsi, gfl = stress_topology(gpts, gtris, mag)
    asi, afl = stress_topology(apts, a_tris, mag)

    cov_pass = iou_gen >= iou_art - margin
    budget_pass = gnv <= anv * budget_ratio
    return {
        "slot": slot,
        "gen": {"nv": gnv, "hull": mesh["hull"], "tris": len(gtris), "mode": mesh.get("_mode")},
        "artist": {"nv": anv, "hull": a_hull, "tris": len(a_tris)},
        "AC_coverage": {"iou_gen": iou_gen, "iou_artist": iou_art, "margin": margin, "pass": cov_pass},
        "AC_topology_setup": {"pass": bool(setup_clean)},
        "AC_budget": {"gen_nv": gnv, "artist_nv": anv, "ratio_limit": budget_ratio, "pass": budget_pass},
        "REL_robust": {"stress_mag": round(mag, 1),
                       "gen_self_int": gsi, "artist_self_int": asi,
                       "gen_flips": gfl, "artist_flips": afl,
                       "gen_no_worse": gsi <= asi and gfl <= afl},
        "overall_pass": bool(cov_pass and setup_clean and budget_pass),
    }


def _mesh_pixels(mesh, W, H):
    v = mesh["vertices"]
    pts = np.array([[v[i] + W / 2.0, H / 2.0 - v[i + 1]] for i in range(0, len(v), 2)], dtype=np.float64)
    return pts, W, H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--slots", nargs="+",
                    default=["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"])
    ap.add_argument("--epsilon", type=float, default=0.002)
    ap.add_argument("--margin", type=float, default=0.02)
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    reps = []
    for s in a.slots:
        reps.append(validate(a.skeleton, a.atlas, a.png, s, s, a.tmp,
                             epsilon=a.epsilon, margin=a.margin))
    allpass = all(r["overall_pass"] for r in reps)
    print(json.dumps({"epsilon": a.epsilon, "results": reps, "all_pass": allpass},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
