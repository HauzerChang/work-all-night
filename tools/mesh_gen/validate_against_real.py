#!/usr/bin/env python3
"""對「真實資產」驗證生成的 mesh — 正式整合 AC。

校正(2026-06-24):
  - IoU 目標 = 對齊藝術家 mesh 覆蓋率(非武斷 0.95)。
  - deform 閘用 transfer_deform_check()(真實位移場轉移)。

優化(2026-06-26,review a):
  - **軟邊件(feathered)用 alpha 加權 IoU**:硬 alpha>8 遮罩對軟陰影失真(藝術家基準僅 0.473、
    一沾就過,意義有限)。soft_fraction>0.5 時改以 alpha 加權 IoU 對齊藝術家加權基準。
  - **v2 自適應 rows**:以藝術家硬覆蓋率為目標挑最少 rows(省頂點;strip 拓樸對 rows 一律 deform-clean)。

流程:atlas 切真實貼圖 → 生成 mesh → ① 覆蓋率(硬或軟,vs 藝術家基準)② 真實 deform 轉移 0 自交/翻面。
"""
import argparse, json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
import deform_eval as de
from atlas_crop import extract


def _recon(uvs, tris, H, W):
    rp = np.column_stack([np.array(uvs).reshape(-1, 2)[:, 0] * W,
                          np.array(uvs).reshape(-1, 2)[:, 1] * H])
    tris = np.array(tris).reshape(-1, 3)
    m = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(m, np.round(rp[t]).astype(np.int32), 1)
    return m.astype(bool)


def hard_iou(recon, mask):
    return float(np.logical_and(recon, mask).sum() / max(int(np.logical_or(recon, mask).sum()), 1))


def soft_iou(recon, alpha01):
    """alpha 加權 IoU:像素以 alpha 計重,羽化邊不再被當作硬邊界。"""
    a = recon.astype(np.float64)
    inter = np.minimum(a, alpha01).sum()
    union = np.maximum(a, alpha01).sum()
    return float(inter / max(union, 1e-9))


def artist_attachment(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)[slot][name]


def validate(skeleton_path, atlas_path, png_path, slot, name, gen_fn, tmp_dir, iou_margin=0.0):
    sk = json.load(open(skeleton_path))
    sub = extract(atlas_path, png_path, name)        # BGRA
    H, W = sub.shape[:2]
    alpha = sub[:, :, 3] if sub.ndim == 3 and sub.shape[2] == 4 else np.full((H, W), 255, np.uint8)
    mask = (alpha > 8)
    alpha01 = alpha.astype(np.float64) / 255.0
    crop = os.path.join(tmp_dir, "_region.png")
    cv2.imwrite(crop, sub)

    content = mask.sum()
    soft_fraction = float(((alpha > 8) & (alpha < 248)).sum() / max(int(content), 1))
    is_soft = soft_fraction > 0.5

    # 藝術家基準覆蓋率(硬 + 軟)
    a = artist_attachment(sk, slot, name)
    art_recon = _recon(a["uvs"], a["triangles"], H, W)
    base_hard = hard_iou(art_recon, mask)
    base_soft = soft_iou(art_recon, alpha01)

    # 生成 mesh(v2 auto 以硬基準為 target 挑最少 rows)
    mesh = gen_fn(crop, base_hard)
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    nv = len(mesh["uvs"]) // 2
    g_recon = _recon(mesh["uvs"], mesh["triangles"], H, W)
    iou_hard = hard_iou(g_recon, mask)
    iou_soft = soft_iou(g_recon, alpha01)

    # 軟件用加權指標,硬件用硬指標
    if is_soft:
        metric, val, base = "alpha_weighted_iou", iou_soft, base_soft
    else:
        metric, val, base = "hard_iou", iou_hard, base_hard
    iou_pass = val >= base - iou_margin

    uvs_src, field, frame = de.real_deform_field(sk, slot, name)
    dres = de.transfer_deform_check(mesh, uvs_src, field)

    return {
        "mesh": {"vertices": nv, "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3,
                 "mode": mesh.get("_mode"), "rows": mesh.get("_rows")},
        "soft_piece": is_soft, "soft_fraction": round(soft_fraction, 3),
        "AC_iou": {"metric": metric, "value": round(val, 4), "artist_baseline": round(base, 4),
                   "pass": iou_pass,
                   "hard_iou": round(iou_hard, 4), "alpha_weighted_iou": round(iou_soft, 4),
                   "base_hard": round(base_hard, 4), "base_soft": round(base_soft, 4)},
        "AC_real_deform": {"frame": frame, "area_ratio": dres["area_ratio"],
                           "self_intersections": dres["self_intersections"],
                           "triangle_flips": dres["triangle_flips"], "pass": dres["clean"]},
        "overall_pass": iou_pass and dres["clean"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/main_draw.json")
    ap.add_argument("--atlas", default="assets/main_draw.atlas")
    ap.add_argument("--png", default="assets/main_draw.png")
    ap.add_argument("--slot", default="image/curtain_left")
    ap.add_argument("--name", default="image/curtain_left")
    ap.add_argument("--gen", choices=["v1", "v2"], default="v2")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    if a.gen == "v1":
        from generate_mesh import generate as g
        gen = lambda p, target=None: g(p)
    else:
        from generate_mesh_v2 import generate as g
        gen = lambda p, target=None: g(p, rows="auto", mode="auto", target_iou=target)
    rep = validate(a.skeleton, a.atlas, a.png, a.slot, a.name, gen, a.tmp)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
