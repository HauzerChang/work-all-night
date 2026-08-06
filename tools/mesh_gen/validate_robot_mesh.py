#!/usr/bin/env python3
"""端到端驗證:atlas 件 → S3 generate_mesh_v2 → 對照 Award 真實生產藝術家 mesh。

與 validate_against_real.py 的差異:
  - main_draw 的 4 mesh 是 **unweighted + 有 deform timeline**,可用真實位移場驗變形。
  - Award 機器人 3 件(光暈/身體/左手)是 **weighted(骨骼蒙皮)、無 deform timeline**,
    所以這裡只做**靜態 IoU 對照**(變形需先做權重轉移,屬 S3 後續能力)。

真值來源:Award 藝術家 mesh 本身。發現(2026-06-26,見 knowledge/s3-robot-mesh-vs-award.md):
  - Award mesh uvs 是 **region-local 0..1**(不是整頁 UV);(u*cropW, v*cropH) 直接命中
    derotate 後的 crop(藝術家 mesh 對自身 alpha IoU 0.967~0.972 → 映射確認)。
  - v2 auto 對非直條件正確走 delaunay;預設 eps 收緊到 0.003 後 3 件靜態 IoU 全高於藝術家。

用法:python validate_robot_mesh.py [--eps 0.003]
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
import generate_mesh_v2 as g2

ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def rasterize_iou(uvs, tris, H, W, alpha):
    """把 (region-local uv, triangles) 光柵化,對 alpha 算 IoU。"""
    px = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(px[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, alpha).sum()
    union = np.logical_or(recon, alpha).sum()
    return float(inter / union) if union else 0.0


def artist_mesh(skeleton, name):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[name][name]
    return (np.array(a["uvs"]).reshape(-1, 2),
            np.array(a["triangles"]).reshape(-1, 3),
            a.get("hull"))


def validate_one(sk, atlas, png, name, eps, tmp):
    sub = extract(atlas, png, name)
    H, W = sub.shape[:2]
    alpha = (sub[..., 3] > 10).astype(np.uint8)
    crop = os.path.join(tmp, "_robot_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    # 藝術家真值(自身 alpha IoU 為映射正確性自檢)
    a_uv, a_tris, a_hull = artist_mesh(sk, name)
    a_iou = rasterize_iou(a_uv, a_tris, H, W, alpha)

    # 生成 mesh
    m = g2.generate(crop, eps=eps)
    m = m[0] if isinstance(m, tuple) else m
    g_iou = evaluate(m, mask)["criteria"]["AC1_iou"]["value"]
    g_v = len(m["uvs"]) // 2

    return {
        "name": name, "crop": [W, H],
        "artist": {"iou": round(a_iou, 4), "verts": len(a_uv), "hull": a_hull},
        "gen": {"iou": round(g_iou, 4), "verts": g_v, "hull": m["hull"], "mode": m.get("_mode")},
        "mapping_ok": a_iou >= 0.90,           # 藝術家 mesh 應緊貼自身 alpha
        "beats_artist": g_iou >= a_iou,
        "verts_saved": len(a_uv) - g_v,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--eps", type=float, default=0.003)
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reps = [validate_one(sk, a.atlas, a.png, n, a.eps, a.tmp) for n in ROBOT_MESHES]
    overall = all(r["mapping_ok"] and r["beats_artist"] for r in reps)
    print(json.dumps({"eps": a.eps, "results": reps, "overall_pass": overall},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
