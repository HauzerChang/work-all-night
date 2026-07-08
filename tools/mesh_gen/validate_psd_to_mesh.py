#!/usr/bin/env python3
"""端到端「PSD 件 → S3 生成 mesh → 對照真實生產 mesh(Award)」靜態驗收。

背景(knowledge/s4-psd-to-spine-real.md):robot_parts.psd 的 3 件(光暈/身體/左手)在生產
spine `Award` 裡是 **weighted / 骨骼驅動 mesh,且 0 deform timeline**(靠骨骼+權重變形,
非逐頂點 deform)。因此驗收方式與 4 個窗簾/陰影 deform-mesh 不同:

  - **不套 deform 閘**(無 deform 場可轉移;骨骼/權重變形不在本工具範疇)。
  - 改做**靜態覆蓋率**對照真實生產 mesh(ground truth):
      ① 生成 mesh 對「PSD 件 alpha」的覆蓋 IoU  vs  ② 藝術家 mesh 對同 alpha 的覆蓋 IoU。
      ③ 生成 mesh 與藝術家 mesh 的直接覆蓋 IoU(拓樸是否落在同一區域)。
      ④ 格式合法(0 孤兒 / 0 退化 / 索引合法)。
      ⑤ 頂點效率:生成頂點數 ≤ 藝術家頂點數。

AC(可機讀):生成覆蓋 IoU ≥ 藝術家基準 − margin,且格式合法,且頂點數不超過藝術家。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from evaluate_mesh import evaluate, load_mask, mesh_pixel_coords
from generate_mesh_v2 import generate as gen_v2


def get_artist_mesh(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[slot][name]


def raster_from_uvs(uvs_flat, tris_flat, H, W):
    """把 mesh 的 uvs(region 內 0..1)三角形填滿成遮罩,用於覆蓋率比對。"""
    uvs = np.array(uvs_flat).reshape(-1, 2)
    tris = np.array(tris_flat).reshape(-1, 3)
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return recon


def raster_from_verts(mesh, H, W):
    """生成 mesh 用像素座標(逆轉 y 翻轉+置中);對齊到 (H,W)。"""
    pts, mW, mH = mesh_pixel_coords(mesh)
    sx, sy = W / mW, H / mH
    pts = pts * np.array([sx, sy])
    tris = np.array(mesh["triangles"]).reshape(-1, 3)
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    return recon


def iou(a, b):
    a = (a > 0); b = (b > 0)
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def validate(part_png, skeleton_path, slot, name, iou_margin=0.02):
    sk = json.load(open(skeleton_path))
    mask = load_mask(part_png)
    H, W = mask.shape

    mesh = gen_v2(part_png, mode="auto")
    nv = len(mesh["uvs"]) // 2

    art = get_artist_mesh(sk, slot, name)
    art_nv = len(art["uvs"]) // 2

    # 覆蓋率遮罩
    gen_recon = raster_from_verts(mesh, H, W)
    art_recon = raster_from_uvs(art["uvs"], art["triangles"], H, W)

    gen_iou = iou(gen_recon, mask)
    art_iou = iou(art_recon, mask)
    gen_vs_art = iou(gen_recon, art_recon)

    # 格式合法(用寬鬆 budget,只看 orphan/degenerate/索引;頂點效率另判)
    ev = evaluate(mesh, mask, vertex_budget=max(nv, art_nv) + 1)
    fmt_ok = (ev["criteria"]["AC4_format"]["pass"]
              and ev["criteria"]["AC2b_degenerate"]["pass"]
              and ev["criteria"]["AC2c_orphans"]["pass"])

    iou_pass = gen_iou >= art_iou - iou_margin
    vbudget_pass = nv <= art_nv

    return {
        "part": name, "slot": slot,
        "mode": mesh.get("_mode"),
        "mask_wh": [W, H],
        "gen_mesh": {"vertices": nv, "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3},
        "artist_mesh": {"vertices": art_nv, "hull": art["hull"], "triangles": len(art["triangles"]) // 3,
                        "weighted": len(art["vertices"]) != len(art["uvs"])},
        "AC_coverage_iou": {"gen": round(gen_iou, 4), "artist_baseline": round(art_iou, 4),
                            "margin": iou_margin, "pass": iou_pass},
        "AC_gen_vs_artist_iou": round(gen_vs_art, 4),
        "AC_format_valid": {"pass": fmt_ok,
                            "orphans": ev["criteria"]["AC2c_orphans"]["value"],
                            "degenerate": ev["criteria"]["AC2b_degenerate"]["value"]},
        "AC_vertex_budget": {"gen": nv, "artist": art_nv, "pass": vbudget_pass},
        "overall_pass": iou_pass and fmt_ok and vbudget_pass,
    }


PARTS = [
    ("psd_parts/00_光暈.png", "機器人拆件/光暈", "機器人拆件/光暈"),
    ("psd_parts/03_身體.png", "機器人拆件/身體", "機器人拆件/身體"),
    ("psd_parts/04_左手.png", "機器人拆件/左手", "機器人拆件/左手"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--part", default=None, help="只跑單一件(png path)")
    ap.add_argument("--slot", default=None)
    ap.add_argument("--name", default=None)
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    if a.part:
        jobs = [(a.part, a.slot, a.name)]
    else:
        jobs = PARTS
    reps = [validate(p, a.skeleton, s, n, a.margin) for (p, s, n) in jobs]
    print(json.dumps(reps, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all(r["overall_pass"] for r in reps) else 1)


if __name__ == "__main__":
    main()
