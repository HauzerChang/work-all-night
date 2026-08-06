#!/usr/bin/env python3
"""S3+S4 端到端(對真實生產標的):PSD 件 / atlas 件 → generate_mesh_v2 →
與 Award 真實『藝術家 mesh』做覆蓋率(coverage IoU)對照。

為什麼是這個對照(有真值、純 CPU、可自驅):
  Award.json 的機器人 3 件(光暈/身體/左手)在生產 spine 中是**手做 weighted mesh**。
  我們用 S3 自動從同一素材產 mesh,問:**自動 mesh 覆蓋輪廓的能力 ≥ 出貨的藝術家 mesh?**
  這是公平的相對閘(不是武斷 0.95),沿用 validate_against_real 的 artist baseline 邏輯。

三條腿:
  A. atlas 件 → v2 mesh:coverage IoU vs 真實 alpha,且 ≥ 藝術家 mesh 自身覆蓋率(相對閘)。
     附頂點預算對照(nv/hull/tris vs 藝術家)。
  B. PSD 件 ↔ atlas 件:silhouette IoU(證實同素材,PSD→atlas 幾何一致)。
  C. PSD 件 → v2 mesh:與 atlas 件 mesh 在各自 alpha-bbox 正規化後 hull 覆蓋 IoU(證 PSD→mesh ≡ atlas→mesh)。

⚠️ 不含 weighted-mesh 真實 deform 轉移閘:Award 3 件是 weighted mesh,其 `vertices` 為
   變長綁定格式(非 2*nv),real_deform_field 目前只支援 unweighted。weighted deform 重現
   列為下一個 bounded chunk。此處僅驗證『靜態覆蓋 + 生成 mesh 內在拓樸乾淨』。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from generate_mesh_v2 import generate as gen_v2
from deform_eval import signed_area
from validate_against_real import artist_iou


# 機器人 3 件:PSD 圖層名 → (Award slot/att 名, atlas region 名)
PIECES = [
    ("光暈", "機器人拆件/光暈"),
    ("身體", "機器人拆件/身體"),
    ("左手", "機器人拆件/左手"),
]


def psd_piece_mask(psd_path, layer_name):
    """從 PSD 取指定圖層,裁到自身 alpha bbox,回傳 (mask uint8 HxW)。"""
    from psd_tools import PSDImage
    psd = PSDImage.open(psd_path)
    for l in psd:
        if l.name == layer_name:
            arr = np.asarray(l.composite(force=True))  # RGBA of layer bbox
            if arr.ndim == 3 and arr.shape[2] == 4:
                a = arr[:, :, 3]
            else:
                a = (arr.sum(axis=2) > 0).astype(np.uint8) * 255 if arr.ndim == 3 else arr
            m = (a > 8).astype(np.uint8)
            ys, xs = np.where(m)
            if len(xs) == 0:
                return m
            return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    raise SystemExit(f"PSD 無此圖層: {layer_name}")


def trim(mask):
    """裁到 alpha bbox(去除周邊透明 padding),讓不同來源件可公平配準。"""
    ys, xs = np.where(mask)
    if len(xs) == 0:
        return mask
    return mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]


def mask_iou_resized(a, b):
    """兩個(可能不同尺寸)二值 mask,各自裁到 alpha bbox 後 resize 對齊算 IoU。"""
    a = trim(a); b = trim(b)
    H, W = a.shape
    b2 = cv2.resize(b, (W, H), interpolation=cv2.INTER_NEAREST)
    inter = np.logical_and(a, b2).sum()
    union = np.logical_or(a, b2).sum()
    return float(inter / union) if union else 0.0


def mesh_hull_mask(mesh, W, H):
    """把 mesh 的三角形填成 mask(mesh.uvs 為 [0,1] 正規化)。"""
    uvs = np.array(mesh["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    m = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(m, np.round(rp[t]).astype(np.int32), 1)
    return m


def intrinsic_clean(mesh):
    """setup pose 下生成 mesh 是否無退化三角(內在拓樸健康度)。"""
    v = np.array(mesh["vertices"], dtype=np.float64)
    s = np.column_stack([v[0::2], v[1::2]])
    t = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    degen = sum(1 for x in t if abs(signed_area(s, x)) < 1e-6)
    return {"degenerate": degen, "clean": degen == 0}


def artist_stats(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    return {"vertices": len(a["uvs"]) // 2, "hull": a["hull"],
            "triangles": len(a["triangles"]) // 3,
            "weighted": len(a["vertices"]) != len(a["uvs"])}


def run(skeleton, atlas, png, psd, tmp, iou_margin, eps):
    sk = json.load(open(skeleton))
    os.makedirs(tmp, exist_ok=True)
    report = {"_eps": eps}
    all_pass = True
    for psd_layer, region in PIECES:
        # --- atlas 件 ---
        sub = extract(atlas, png, region)
        crop = os.path.join(tmp, f"_atlas_{psd_layer}.png")
        cv2.imwrite(crop, sub)
        mask_atlas = load_mask(crop)
        Ha, Wa = mask_atlas.shape

        mesh_a = gen_v2(crop, mode="auto", eps=eps)
        gen_iou = evaluate(mesh_a, mask_atlas)["criteria"]["AC1_iou"]["value"]
        base = round(artist_iou(sk, region, region, mask_atlas), 4)
        astat = artist_stats(sk, region, region)
        leg_a_pass = gen_iou >= base - iou_margin

        # --- PSD 件 ---
        mask_psd = psd_piece_mask(psd, psd_layer)
        sil_iou = round(mask_iou_resized(mask_atlas, mask_psd), 4)
        crop_psd = os.path.join(tmp, f"_psd_{psd_layer}.png")
        cv2.imwrite(crop_psd, (mask_psd * 255).astype(np.uint8))
        mesh_p = gen_v2(crop_psd, mode="auto", eps=eps)

        # C: 兩來源 mesh 在共同正規化網格上的 hull 覆蓋一致性
        N = 256
        hm_a = mesh_hull_mask(mesh_a, N, N)
        hm_p = mesh_hull_mask(mesh_p, N, N)
        mesh_consistency = round(mask_iou_resized(hm_a, hm_p), 4)

        report[region] = {
            "A_atlas_gen_vs_artist": {
                "gen_coverage_iou": gen_iou,
                "artist_baseline_iou": base,
                "pass": leg_a_pass,
                "gen_mode": mesh_a.get("_mode"),
                "budget": {"gen": {"vertices": len(mesh_a["uvs"]) // 2, "hull": mesh_a["hull"],
                                   "triangles": len(mesh_a["triangles"]) // 3},
                           "artist": astat},
                "gen_intrinsic": intrinsic_clean(mesh_a),
            },
            "B_psd_vs_atlas_silhouette_iou": sil_iou,
            "C_psd_mesh_vs_atlas_mesh_iou": mesh_consistency,
        }
        all_pass = all_pass and leg_a_pass and intrinsic_clean(mesh_a)["clean"]
    report["_overall_pass"] = all_pass
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--iou-margin", type=float, default=0.0)
    ap.add_argument("--eps", type=float, default=0.002,
                    help="v1 hull Douglas-Peucker 容差;有機生產件建議 0.002(見 knowledge)")
    a = ap.parse_args()
    rep = run(a.skeleton, a.atlas, a.png, a.psd, a.tmp, a.iou_margin, a.eps)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["_overall_pass"] else 1)


if __name__ == "__main__":
    main()
