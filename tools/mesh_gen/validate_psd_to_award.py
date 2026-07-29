#!/usr/bin/env python3
"""端到端「PSD 件 → S3 生成 mesh → 對照 Award 真實 mesh」整合 AC。

情境(見 knowledge/s4-psd-to-spine-real.md):`robot_parts.psd` 的 3 個件
(光暈 / 身體 / 左手)在生產 spine `Award` 中是 mesh。本工具把「切件 alpha」
餵進 S3 生成器,並拿 Award 藝術家 mesh 當**外部真值**做靜態覆蓋率對照。

⚠️ 與 main_draw 4 mesh 的關鍵差異:
- Award 這 3 件是 **weighted mesh**(靠骨骼權重變形)且 **無 deform timeline**
  → 逐頂點 deform 轉移閘 N/A(沒有真實位移場可轉移)。本閘只驗**靜態覆蓋率 + 拓樸格式**。
- Award mesh uvs 經實測為 **region-local 0..1**(非 atlas-global);與 main_draw 同慣例
  (推翻 s4 筆記中「需轉 region 局部」的過度保守假設)。

比對空間:一律在「PSD 切件 alpha 遮罩」的像素空間內光柵化。
- 生成 mesh:用 evaluate_mesh(其 mesh_pixel_coords 還原到遮罩空間)。
- 藝術家 mesh:uvs × (遮罩 W,H) 直接光柵化(沿用 validate_against_real.artist_iou 慣例,y 不翻)。
兩者對同一遮罩算 IoU → 尺度(atlas 0.70 縮放)自動抵消。

判準:
  AC_format   生成 mesh 格式/預算/無孤兒/無退化(evaluate_mesh)
  AC_iou      生成覆蓋率 ≥ 藝術家自身覆蓋率基準 − margin(對齊藝術家,非武斷 0.95)
  AC_agree    生成 mesh 覆蓋 vs 藝術家 mesh 覆蓋 的 IoU(mesh↔mesh 一致性,診斷用)
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from evaluate_mesh import evaluate, load_mask


def award_mesh(skeleton, slot, name=None):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    d = atts[slot]
    name = name or next(iter(d))
    return d[name], name


def raster_uvs(uvs, tris, W, H):
    """uvs(region-local 0..1) × 遮罩尺寸 → 填三角形得覆蓋率點陣。"""
    u = np.asarray(uvs, np.float64).reshape(-1, 2)
    pts = np.column_stack([u[:, 0] * W, u[:, 1] * H])
    t = np.asarray(tris, np.int32).reshape(-1, 3)
    recon = np.zeros((H, W), np.uint8)
    for tri in t:
        cv2.fillConvexPoly(recon, np.round(pts[tri]).astype(np.int32), 1)
    return recon


def gen_coverage(mesh, W, H):
    """把生成 mesh 光柵化到遮罩空間(用其 uvs,與 award 同法,確保同空間)。"""
    return raster_uvs(mesh["uvs"], mesh["triangles"], W, H)


def validate(piece_png, skeleton_path, slot, gen_fn, iou_margin=0.02):
    mask = load_mask(piece_png)          # (H,W) 0/1
    H, W = mask.shape
    m = (mask > 0).astype(np.uint8)

    mesh = gen_fn(piece_png)
    if isinstance(mesh, tuple):
        mesh = mesh[0]

    fmt = evaluate(mesh, m)
    gen_iou = fmt["criteria"]["AC1_iou"]["value"]

    sk = json.load(open(skeleton_path))
    art, aname = award_mesh(sk, slot)
    art_recon = raster_uvs(art["uvs"], art["triangles"], W, H)
    a_inter = int(np.logical_and(art_recon, m).sum())
    a_union = int(np.logical_or(art_recon, m).sum())
    art_iou = a_inter / a_union if a_union else 0.0

    # mesh↔mesh 覆蓋一致性(診斷)
    gen_recon = gen_coverage(mesh, W, H)
    g_inter = int(np.logical_and(gen_recon, art_recon).sum())
    g_union = int(np.logical_or(gen_recon, art_recon).sum())
    agree = g_inter / g_union if g_union else 0.0

    return {
        "piece": os.path.basename(piece_png), "slot": slot,
        "gen_mesh": {"vertices": fmt["vertices"], "triangles": fmt["triangles"],
                     "hull": fmt["hull"], "mode": mesh.get("_mode")},
        "artist_mesh": {"vertices": len(art["uvs"]) // 2,
                        "triangles": len(art["triangles"]) // 3,
                        "hull": art.get("hull"), "weighted": len(art["vertices"]) != len(art["uvs"])},
        "AC_format": {"pass": fmt["criteria"]["AC4_format"]["pass"]
                      and fmt["criteria"]["AC2b_degenerate"]["pass"]
                      and fmt["criteria"]["AC2c_orphans"]["pass"]
                      and fmt["criteria"]["AC3_vertex_budget"]["pass"],
                      "detail": {k: fmt["criteria"][k] for k in
                                 ("AC4_format", "AC2b_degenerate", "AC2c_orphans", "AC3_vertex_budget")}},
        "AC_iou": {"gen": round(gen_iou, 4), "artist_baseline": round(art_iou, 4),
                   "margin": iou_margin, "pass": gen_iou >= art_iou - iou_margin},
        "AC_agree": {"gen_vs_artist_iou": round(agree, 4)},
        "deform_gate": "N/A (weighted mesh, no deform timeline in Award)",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("piece_png")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--slot", required=True)
    ap.add_argument("--gen", choices=["v1", "v2"], default="v2")
    a = ap.parse_args()
    if a.gen == "v1":
        from generate_mesh import generate as g
        gen = lambda p: g(p)
    else:
        from generate_mesh_v2 import generate as g
        gen = lambda p: g(p, mode="auto")
    rep = validate(a.piece_png, a.skeleton, a.slot, gen)
    ok = rep["AC_format"]["pass"] and rep["AC_iou"]["pass"]
    rep["overall_pass"] = ok
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
