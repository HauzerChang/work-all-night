#!/usr/bin/env python3
"""S3 端到端驗收:PSD 件 → generate_mesh_v2 → 對照 Award 真實藝術家 mesh。

背景(knowledge/s4-psd-to-spine-real.md):robot_parts.psd 的 光暈/身體/左手 三件在生產
spine `Award.json` 中是**藝術家手做的 weighted mesh**(靠骨骼權重變形,無 deform timeline)。
本工具把「S3 自動生成的 mesh」拿去對照「藝術家真值 mesh」,回答:
  S3 能否在真實生產件上,做出**輪廓覆蓋 ≥ 藝術家、頂點預算 ≤ 藝術家、拓樸乾淨**的 mesh?

三個量化指標(都可機讀 pass/fail):
  A. 形狀吻合(mesh↔mesh):藝術家 hull 多邊形 vs S3 hull 多邊形,各自正規化到單位方形後
     取 8 種二面體對稱(4 旋轉×2 翻轉)下的最佳 IoU。**用藝術家 mesh 當真值**。
     — 旋轉/翻轉不變是刻意的:atlas region 有 rotate 旗標(且曾出 CCW/CW bug),此處只問
       「形狀是否相同」,方向不列入,順帶避開 atlas 旋轉方向雷點。
  B. 輪廓覆蓋(S3 self vs 真實 alpha):evaluate_mesh 的 IoU,對 PSD 切件 alpha。真值=PSD alpha。
  C. 頂點預算:S3 頂點數 vs 藝術家頂點數(要求 ≤ 藝術家,證明不比人做的更囉嗦)。
  D. 拓樸:退化三角=0、孤兒頂點=0、重心落在 alpha 內。

負對照:跨件 hull 形狀 IoU(光暈 vs 身體…)應顯著低於同件,確認指標 A 有鑑別力。
"""
import argparse, json, sys, os
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_mesh_v2 as g2
import evaluate_mesh as em

# PSD 件檔名(psd_slice 輸出) 對應 Award slot/attachment 名
PIECES = {
    "光暈": {"png": "00_光暈.png", "slot": "機器人拆件/光暈"},
    "身體": {"png": "03_身體.png", "slot": "機器人拆件/身體"},
    "左手": {"png": "04_左手.png", "slot": "機器人拆件/左手"},
}


def load_award_meshes(award_json):
    d = json.load(open(award_json))
    skins = d["skins"]
    out = {}

    def walk(atts_by_slot):
        for slot, atts in atts_by_slot.items():
            for name, a in atts.items():
                if a.get("type") == "mesh":
                    out[slot] = a
    if isinstance(skins, list):
        for s in skins:
            walk(s.get("attachments", {}))
    else:
        for s in skins.values():
            walk(s)
    return out


def hull_polygon_uv(mesh):
    """取 mesh 前 hull 個頂點的 uv,回傳 (N,2) 多邊形(atlas UV 空間)。"""
    n = mesh["hull"]
    uv = mesh["uvs"]
    return np.array([[uv[2 * i], uv[2 * i + 1]] for i in range(n)], dtype=np.float64)


def norm_unit(poly):
    """把多邊形正規化到單位方形(bbox → [0,1]²,拉伸;兩件同 aspect 故公平)。"""
    mn = poly.min(axis=0)
    mx = poly.max(axis=0)
    span = np.maximum(mx - mn, 1e-9)
    return (poly - mn) / span


def raster(poly01, S=400):
    """把 [0,1]² 多邊形填成 S×S 遮罩。"""
    img = np.zeros((S, S), np.uint8)
    pts = np.round(poly01 * (S - 1)).astype(np.int32)
    cv2.fillPoly(img, [pts], 1)
    return img


DIHEDRAL = []  # 8 個二面體變換(對正規化座標)


def _build_dihedral():
    def rot(p, k):
        # k×90° 對 [0,1]² 中心旋轉
        x, y = p[:, 0], p[:, 1]
        for _ in range(k):
            x, y = y, 1.0 - x
        return np.stack([x, y], axis=1)

    def flip(p):
        return np.stack([1.0 - p[:, 0], p[:, 1]], axis=1)
    for k in range(4):
        DIHEDRAL.append(lambda p, k=k: rot(p, k))
        DIHEDRAL.append(lambda p, k=k: rot(flip(p), k))


_build_dihedral()


def best_dihedral_iou(polyA01, polyB01, S=400):
    """A 固定,B 取 8 種二面體變換,回最佳 IoU 與變換 index。"""
    ra = raster(polyA01, S)
    best = (-1.0, -1)
    for idx, tf in enumerate(DIHEDRAL):
        rb = raster(norm_unit(tf(polyB01)), S)
        inter = int(np.logical_and(ra, rb).sum())
        union = int(np.logical_or(ra, rb).sum())
        iou = inter / union if union else 0.0
        if iou > best[0]:
            best = (iou, idx)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pieces-dir", default="/tmp/claude-0/-home-user-work-all-night/882595c6-f532-595d-9baf-3db2c6de50ef/scratchpad/robot")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--shape-thresh", type=float, default=0.85)
    args = ap.parse_args()

    award = load_award_meshes(args.award)
    report = {}
    artist_hulls = {}  # for negative control
    s3_hulls = {}

    for pname, info in PIECES.items():
        png = os.path.join(args.pieces_dir, info["png"])
        art = award[info["slot"]]
        art_nv = len(art["uvs"]) // 2

        # --- S3 生成 ---
        s3 = g2.generate(png, mode="auto")
        s3_nv = len(s3["uvs"]) // 2

        # --- B/D: 覆蓋 + 拓樸(對 PSD alpha,以藝術家頂點數為預算) ---
        mask = em.load_mask(png)
        ev = em.evaluate(s3, mask, vertex_budget=art_nv, iou_thresh=0.90)

        # --- A: 形狀吻合(藝術家 hull vs S3 hull) ---
        art_hull = norm_unit(hull_polygon_uv(art))
        s3_hull = norm_unit(hull_polygon_uv(s3))
        artist_hulls[pname] = art_hull
        s3_hulls[pname] = s3_hull
        shape_iou, tf_idx = best_dihedral_iou(art_hull, s3_hull)

        report[pname] = {
            "s3_mode": s3.get("_mode"),
            "A_shape_iou": round(shape_iou, 4),
            "A_pass": shape_iou >= args.shape_thresh,
            "A_best_dihedral": tf_idx,
            "B_coverage_iou": ev["criteria"]["AC1_iou"]["value"],
            "B_pass": ev["criteria"]["AC1_iou"]["pass"],
            "C_verts_s3": s3_nv, "C_verts_artist": art_nv,
            "C_pass": s3_nv <= art_nv,
            "D_degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
            "D_orphans": ev["criteria"]["AC2c_orphans"]["value"],
            "D_centroid_in": ev["criteria"]["AC2a_centroid_in_mask"]["value"],
            "D_pass": ev["criteria"]["AC2b_degenerate"]["pass"]
                       and ev["criteria"]["AC2c_orphans"]["pass"]
                       and ev["criteria"]["AC2a_centroid_in_mask"]["pass"],
        }
        report[pname]["piece_pass"] = all(
            report[pname][k] for k in ("A_pass", "B_pass", "C_pass", "D_pass"))

    # --- 負對照:跨件 hull 形狀 IoU(應顯著 < 同件) ---
    names = list(PIECES.keys())
    neg = {}
    for i in range(len(names)):
        for j in range(len(names)):
            if i == j:
                continue
            iou, _ = best_dihedral_iou(artist_hulls[names[i]], s3_hulls[names[j]])
            neg[f"{names[i]}(art) vs {names[j]}(s3)"] = round(iou, 4)

    same = {n: report[n]["A_shape_iou"] for n in names}
    cross_max = max(neg.values())
    same_min = min(same.values())
    discriminative = same_min > cross_max

    out = {
        "pieces": report,
        "negative_control": {
            "same_piece_shape_iou": same,
            "cross_piece_shape_iou": neg,
            "same_min": round(same_min, 4),
            "cross_max": round(cross_max, 4),
            "discriminative": discriminative,
        },
        "overall_pass": all(report[n]["piece_pass"] for n in names) and discriminative,
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["overall_pass"] else 1)


if __name__ == "__main__":
    main()
