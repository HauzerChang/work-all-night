#!/usr/bin/env python3
"""端到端驗收:件 → S3 generate_mesh_v2 → 對照 Award 真實(生產)mesh 的靜態覆蓋率。

與 validate_against_real.py 的差異(為何需要獨立腳本):
  - main_draw 4 mesh 是 unweighted,且 attachment==region。
  - Award 機器人 3 件(光暈/身體/左手)是 weighted mesh;件在 atlas 中可能 rotate 打包、
    貼圖被 ~0.70 縮小;無 deform timeline(靠骨骼 warp)。故不套用 main_draw 的「真實位移場
    轉移」閘,本腳本專注**靜態覆蓋率**對真實生產 mesh 的驗收。

UV 慣例校準(2026-08-13,以藝術家自 IoU 實測 8 種翻轉/旋轉組合):
  Award mesh 的 uvs 是 region-local 0..1、且已對應「去旋轉後的直立影像」
  (session-006 log 記為 atlas-UV 有誤)。最單純的 `u*Wc, v*Hc`(無翻轉/無旋轉)填三角形時,
  三件藝術家自 IoU = 0.97~0.98(全 8 組合最高;其餘 ≤0.70)。這同時**獨立佐證 session-006 的
  CW 去旋轉修正**(生產 spine 的 uvs 恰落在 CW 去旋轉的 crop 上 → 0.98)。
  藝術家自 IoU 當**校準閘**:<0.85 視為評估器不可信(拒絕給判定)。

流程:atlas 取件直立 crop(alpha=共同畫布) → ① 藝術家 uvs 直接 raster 得覆蓋遮罩(自 IoU 校準)
  → ② generate_mesh_v2 生成 → evaluate() 得 gen_IoU → 判定 gen_IoU >= artist_iou - margin。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import parse_atlas, extract
from evaluate_mesh import evaluate
from generate_mesh_v2 import generate as gen_v2

CALIB_MIN = 0.85   # 藝術家自 IoU 低於此 → 評估器不可信


def _att(sk, slot, name):
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)[slot][name]


def iou(a, b):
    a = a > 0; b = b > 0
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def artist_mask(sk, slot, name, Wc, Hc):
    """直接把 region-local uvs raster 成覆蓋遮罩(校準過的直立對齊)。"""
    a = _att(sk, slot, name)
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    m = np.zeros((Hc, Wc), np.uint8)
    pts = np.column_stack([uvs[:, 0] * Wc, uvs[:, 1] * Hc])
    for t in tris:
        cv2.fillConvexPoly(m, np.round(pts[t]).astype(np.int32), 1)
    return m, len(uvs), len(tris)


def piece_alpha(sub):
    if sub.ndim == 3 and sub.shape[2] == 4:
        return (sub[:, :, 3] > 8).astype(np.uint8)
    g = sub if sub.ndim == 2 else cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    return (g > 8).astype(np.uint8)


def compare(sk, atlas_path, png_path, slot, name, tmp_dir,
            rows=10, cols=3, iou_margin=0.0, gen_kwargs=None):
    regions = parse_atlas(atlas_path)
    region = regions[name]
    sub = extract(atlas_path, png_path, name)           # 直立、去旋轉的真實貼圖 crop
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    Wc, Hc = sub.shape[1], sub.shape[0]
    alpha = piece_alpha(sub)

    art, a_nv, a_tris = artist_mask(sk, slot, name, Wc, Hc)
    art_iou = iou(art, alpha)

    gk = dict(rows=rows, cols=cols, mode="auto")
    if gen_kwargs:
        gk.update(gen_kwargs)
    mesh = gen_v2(crop, **gk)
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    nv = len(mesh["uvs"]) // 2
    ev = evaluate(mesh, alpha)
    node = ev.get("criteria", ev)
    gen_iou = node["AC1_iou"]["value"]

    calibrated = art_iou >= CALIB_MIN
    return {
        "piece": name,
        "region": {k: region.get(k) for k in ("page", "size", "rotate")},
        "crop_px": [int(Wc), int(Hc)],
        "artist_mesh": {"vertices": a_nv, "triangles": a_tris, "weighted": True},
        "gen_mesh": {"vertices": nv, "hull": mesh["hull"],
                     "triangles": len(mesh["triangles"]) // 3, "mode": mesh.get("_mode")},
        "artist_baseline_iou": round(art_iou, 4),
        "calibrated": calibrated,
        "gen_iou": round(gen_iou, 4),
        "gap": round(gen_iou - art_iou, 4),
        "pass": bool(calibrated and gen_iou >= art_iou - iou_margin),
    }


PIECES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")  # extract 依 region.page 自動選頁
    ap.add_argument("--piece", default=None, help="單一件名;預設跑全部 3 件")
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--cols", type=int, default=3)
    ap.add_argument("--margin", type=float, default=0.0)
    ap.add_argument("--max-interior", type=int, default=None)
    ap.add_argument("--epsilon", type=float, default=None)
    ap.add_argument("--min-dist", type=float, default=None)
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    gk = {}
    if a.max_interior is not None:
        gk["max_interior"] = a.max_interior
    if a.epsilon is not None:
        gk["epsilon_frac"] = a.epsilon
    if a.min_dist is not None:
        gk["min_dist"] = a.min_dist
    pieces = [a.piece] if a.piece else PIECES
    reports = [compare(sk, a.atlas, a.png, p, p, a.tmp, rows=a.rows, cols=a.cols,
                       iou_margin=a.margin, gen_kwargs=gk or None) for p in pieces]
    out = {"pieces": reports,
           "all_calibrated": all(r["calibrated"] for r in reports),
           "overall_pass": all(r["pass"] for r in reports)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["overall_pass"] else 1)


if __name__ == "__main__":
    main()
