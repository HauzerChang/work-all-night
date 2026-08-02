#!/usr/bin/env python3
"""S3×S4 端到端閘 — 「PSD 件 → 生成 mesh」對照 Award 真實藝術家 mesh。

背景(見 knowledge/s4-psd-to-spine-real.md):robot_parts.psd 的 3 件(光暈/身體/左手)
在生產 spine `Award` 中是 **weighted mesh**。本閘把「切件 alpha」當覆蓋真值,
把「藝術家 mesh」當拓樸/精簡度真值,量化我方生成 mesh 是否達到藝術家水準:

  切件 PNG(alpha) ──generate_mesh_v2──▶ 我方 mesh ──光柵化──▶ 我方覆蓋
                    └─ Award.json uvs ─▶ 藝術家 mesh(region 局部像素)─▶ 藝術家覆蓋

量化指標(對每件):
  - iou_alpha:mesh 覆蓋 vs 切件 alpha(藝術家 / 我方各一,越高越貼合美術)。
  - iou_cross:我方覆蓋 vs 藝術家覆蓋(是否覆蓋同一塊 footprint)。
  - 頂點/三角數:我方 vs 藝術家(精簡度對照)。

⚠️ Award mesh `uvs` 是 **region 局部正規化**(0..1 在該 attachment 自身 region 內),
   px = u*W, py = v*H 即可還原到切件像素座標。v 的朝向(上/下原點)以「哪個朝向對 alpha
   IoU 較高」自動選定(藝術家 mesh 必然貼合自己的素材)。

AC(端到端驗收):
  AC1 我方 iou_alpha ≥ 藝術家 iou_alpha − TOL(覆蓋美術不遜於藝術家)。
  AC2 iou_cross ≥ CROSS_THRESH(與藝術家覆蓋同一 footprint)。
  AC3 我方頂點數 ≤ 藝術家頂點數 × BUDGET_FACTOR(精簡度可比)。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_mesh_v2 as gmv2

TOL = 0.02            # AC1 覆蓋容差
CROSS_THRESH = 0.90   # AC2 footprint 一致
BUDGET_FACTOR = 1.10  # AC3 精簡度(允許 +10%)


def rasterize(pts, tris, W, H):
    """把三角形填滿成覆蓋遮罩(pts 為像素座標 Nx2, tris 為 Mx3 索引)。"""
    canvas = np.zeros((H, W), np.uint8)
    for t in tris:
        poly = np.round(pts[t]).astype(np.int32)
        cv2.fillConvexPoly(canvas, poly, 1)
    return canvas


def iou(a, b):
    inter = int(np.logical_and(a, b).sum())
    union = int(np.logical_or(a, b).sum())
    return inter / union if union else 0.0


def my_mesh_pixels(mesh):
    """generate_mesh_v2 輸出:vertices 為置中+上翻,還原回像素座標。"""
    W, H = mesh["width"], mesh["height"]
    v = mesh["vertices"]
    pts = np.array([(v[i] + W / 2.0, H / 2.0 - v[i + 1]) for i in range(0, len(v), 2)],
                   dtype=np.float64)
    return pts, np.array(mesh["triangles"], np.int32).reshape(-1, 3), W, H


def artist_mesh_pixels(att, W, H, alpha):
    """從 Award weighted mesh 的 region 局部 uvs 還原像素座標。
    v 朝向未知 → 兩種都試,取對 alpha IoU 較高者(藝術家 mesh 必貼合自身素材)。"""
    uvs = att["uvs"]
    tris = np.array(att["triangles"], np.int32).reshape(-1, 3)
    n = len(uvs) // 2
    u = np.array(uvs[0::2]); vv = np.array(uvs[1::2])
    best = None
    for flip in (False, True):
        py = (1.0 - vv) * H if flip else vv * H
        pts = np.column_stack([u * W, py])
        cov = rasterize(pts, tris, W, H)
        sc = iou(cov > 0, alpha > 0)
        if best is None or sc > best[0]:
            best = (sc, pts, tris, cov, flip)
    return best  # (iou_alpha, pts, tris, cov, flip)


def load_alpha(png):
    img = cv2.imread(png, cv2.IMREAD_UNCHANGED)
    if img.ndim == 3 and img.shape[2] == 4:
        return (img[:, :, 3] > 8).astype(np.uint8)
    g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return (g > 8).astype(np.uint8)


def load_award_mesh(award_json, slot_name):
    d = json.load(open(award_json))
    for skin in d["skins"]:
        atts = skin.get("attachments", {})
        if slot_name in atts:
            for _, a in atts[slot_name].items():
                if a.get("type") == "mesh":
                    return a
    return None


# 對應:切件檔名 → Award slot
TARGETS = [
    ("00_光暈.png", "機器人拆件/光暈"),
    ("03_身體.png", "機器人拆件/身體"),
    ("04_左手.png", "機器人拆件/左手"),
]


def evaluate_piece(png, slot, award_json):
    alpha = load_alpha(png)
    H, W = alpha.shape
    # 我方生成
    my = gmv2.generate(png)
    mpts, mtris, mW, mH = my_mesh_pixels(my)
    my_cov = rasterize(mpts, mtris, mW, mH)
    my_iou = iou(my_cov > 0, alpha > 0)
    my_nv = len(my["uvs"]) // 2
    my_nt = len(my["triangles"]) // 3
    # 藝術家(region 局部 uvs → 用「我方切件」的 W,H 對齊,因 att.width≈W+2)
    att = load_award_mesh(award_json, slot)
    a_iou, apts, atris, a_cov, flip = artist_mesh_pixels(att, W, H, alpha)
    a_nv = len(att["uvs"]) // 2
    a_nt = len(att["triangles"]) // 3
    cross = iou(my_cov > 0, a_cov > 0)
    ac1 = my_iou >= a_iou - TOL
    ac2 = cross >= CROSS_THRESH
    ac3 = my_nv <= a_nv * BUDGET_FACTOR
    return {
        "piece": os.path.basename(png), "slot": slot,
        "mode": my.get("_mode"), "size": [W, H], "v_flip_artist": flip,
        "my":     {"iou_alpha": round(my_iou, 4), "nv": my_nv, "nt": my_nt},
        "artist": {"iou_alpha": round(a_iou, 4), "nv": a_nv, "nt": a_nt},
        "iou_cross": round(cross, 4),
        "AC1_cover_ge_artist": {"pass": bool(ac1), "my": round(my_iou, 4),
                                "artist": round(a_iou, 4), "tol": TOL},
        "AC2_footprint_match": {"pass": bool(ac2), "value": round(cross, 4), "thresh": CROSS_THRESH},
        "AC3_parsimony": {"pass": bool(ac3), "my_nv": my_nv, "artist_nv": a_nv,
                          "factor": BUDGET_FACTOR},
        "overall_pass": bool(ac1 and ac2 and ac3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="/tmp/robot_parts")
    ap.add_argument("--award", default="assets/Award.json")
    a = ap.parse_args()
    reports = []
    for fn, slot in TARGETS:
        png = os.path.join(a.parts, fn)
        reports.append(evaluate_piece(png, slot, a.award))
    overall = all(r["overall_pass"] for r in reports)
    print(json.dumps({"overall_pass": overall, "pieces": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
