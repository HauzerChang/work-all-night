#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 generate_mesh_v2 → 對照 Award 真實生產 mesh。

這是 S3(mesh 生成器)+ S4(PSD 切圖)串起來、對「真實生產標的」的整合 AC。
真值 = big win spine `Award.json` 裡機器人拆件的**藝術家手做 mesh**(光暈/左手/身體)。

關鍵發現(2026-07-15,本工具建立時實測):
  Spine JSON 的 mesh `uvs` 是 **region-local 0..1、logical(未旋轉)方位**。
  把 uv × PSD 件尺寸,藝術家 mesh footprint 疊回 PSD 件 alpha 的 IoU = 0.95~0.98,
  證明 PSD 件與 spine 貼圖同一素材(見 log/session 006 texture 驗證),
  且**兩邊都能在同一個 PSD 件像素空間比較**(atlas 0.70 縮放在覆蓋率正規化下抵銷)。

比較法(蘋果對蘋果,皆在 PSD 件像素空間、對同一 alpha 剪影):
  - gen_iou    = IoU(生成 mesh 三角填滿, 件 alpha)      —— 生成 mesh 的剪影覆蓋率
  - artist_iou = IoU(Award 真實 mesh 三角填滿, 件 alpha) —— 藝術家 mesh 覆蓋率(基準真值)
  - AC 覆蓋率:gen_iou >= artist_iou - margin(達到或超過藝術家)
  - AC 頂點預算:生成頂點數在藝術家頂點數的合理倍數內
  - AC 格式/退化/孤兒:沿用 evaluate_mesh(unweighted 合法性)

⚠️ 不含 deform 閘:Award mesh 為 **weighted**,其變形需重現 Award 12 支動畫的
   weighted deform,屬另一個 bounded chunk(見 STATE 下一步)。本工具只做幾何/覆蓋對照。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask

# PSD 件檔名 ← → Award slot/attachment(同名)。三件皆為 Award 中的 mesh。
PART_MAP = [
    ("光暈", "機器人拆件/光暈", "00_光暈.png"),
    ("左手", "機器人拆件/左手", "04_左手.png"),
    ("身體", "機器人拆件/身體", "03_身體.png"),
]


def award_mesh(skeleton, slot_name):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[slot_name][slot_name]


def coverage_iou(uvs, tris, alpha):
    """uvs(region-local 0..1)× 件尺寸 填三角 → 對 alpha 剪影的 IoU。"""
    H, W = alpha.shape
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, alpha).sum())
    union = int(np.logical_or(recon, alpha).sum())
    return (inter / union) if union else 0.0


def compare_one(skeleton, slot_name, part_png, iou_margin, budget_factor):
    alpha = load_mask(part_png)  # PSD 件 alpha 剪影(件像素空間)

    # 藝術家真值 mesh
    a = award_mesh(skeleton, slot_name)
    a_uvs = np.array(a["uvs"]).reshape(-1, 2)
    a_tris = np.array(a["triangles"]).reshape(-1, 3)
    a_nv = len(a_uvs)
    artist_iou = coverage_iou(a_uvs, a_tris, alpha)

    # S3 生成 mesh(unweighted)
    mesh = gen_v2(part_png, mode="auto")
    g_nv = len(mesh["uvs"]) // 2
    g_uvs = np.array(mesh["uvs"]).reshape(-1, 2)
    g_tris = np.array(mesh["triangles"]).reshape(-1, 3)
    gen_iou = coverage_iou(g_uvs, g_tris, alpha)

    # 沿用 evaluate_mesh 檢查生成 mesh 的 unweighted 合法性(格式/退化/孤兒/重心)
    ev = evaluate(mesh, alpha, vertex_budget=max(64, int(a_nv * budget_factor) + 1),
                  iou_thresh=0.0)  # IoU 這裡不設絕對門檻,改用藝術家基準比較
    fmt_ok = all(ev["criteria"][k]["pass"] for k in
                 ["AC4_format", "AC2a_centroid_in_mask", "AC2b_degenerate", "AC2c_orphans"])

    cover_pass = gen_iou >= artist_iou - iou_margin
    budget_pass = g_nv <= a_nv * budget_factor

    return {
        "slot": slot_name,
        "part_png": os.path.basename(part_png),
        "part_size": [int(alpha.shape[1]), int(alpha.shape[0])],
        "artist": {"vertices": a_nv, "triangles": len(a_tris),
                   "weighted": len(a["vertices"]) != len(a["uvs"]), "coverage_iou": round(artist_iou, 4)},
        "generated": {"vertices": g_nv, "triangles": len(g_tris), "hull": mesh["hull"],
                      "mode": mesh.get("_mode"), "coverage_iou": round(gen_iou, 4)},
        "AC_coverage": {"pass": bool(cover_pass), "gen": round(gen_iou, 4),
                        "artist_baseline": round(artist_iou, 4),
                        "delta": round(gen_iou - artist_iou, 4), "margin": iou_margin},
        "AC_vertex_budget": {"pass": bool(budget_pass), "gen_verts": g_nv,
                             "artist_verts": a_nv, "factor_limit": budget_factor,
                             "ratio": round(g_nv / a_nv, 3)},
        "AC_format_legal": {"pass": bool(fmt_ok)},
        "overall_pass": bool(cover_pass and budget_pass and fmt_ok),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--parts-dir", default="/tmp/robot_parts",
                    help="psd_slice 切出 robot_parts.psd 的目錄")
    ap.add_argument("--iou-margin", type=float, default=0.03,
                    help="覆蓋率容差(gen 與 artist 皆在件空間量,留一點 raster 誤差)")
    ap.add_argument("--budget-factor", type=float, default=1.5,
                    help="生成頂點數上限 = 藝術家頂點數 × 此係數")
    a = ap.parse_args()

    sk = json.load(open(a.skeleton))
    reports = []
    for _pname, slot, fn in PART_MAP:
        png = os.path.join(a.parts_dir, fn)
        reports.append(compare_one(sk, slot, png, a.iou_margin, a.budget_factor))

    overall = all(r["overall_pass"] for r in reports)
    out = {"tool": "compare_award_mesh", "overall_pass": overall, "parts": reports}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
