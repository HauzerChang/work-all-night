#!/usr/bin/env python3
"""端到端「PSD 件 → S3 mesh → 對照 Award 真實生產 mesh」驗收(S3+S4 串接里程碑)。

流程(純 CPU,不需 GPU):
  robot_parts.psd --psd_slice--> 各件緊湊 PNG(含 alpha)
  --generate_mesh_v2--> 生成 mesh(這 3 件皆 aspect<1.2 → v1 Delaunay 回退)
  對照 Award.json 中對應 slot 的**真實生產 mesh**(weighted,骨骼驅動,無 deform timeline)。

比對度量(皆在「PSD 件像素框」下,兩者用同一張 alpha 遮罩):
  - 生成 mesh 覆蓋率 IoU(填三角 vs alpha)
  - 藝術家 mesh 覆蓋率 IoU(uv×件W,H 還原到件框;為 baseline)
  - mesh↔mesh 覆蓋區 IoU(生成填充 vs 藝術家填充,拓樸相似度)
  - 頂點數 / hull / 三角數 對照
  - 格式 + 退化/孤兒 + setup-pose 靜態自交(生成 mesh)

AC(對齊 validate_against_real 哲學):生成覆蓋率 >= 藝術家 baseline - margin,
且格式合法、0 退化/孤兒、靜態 0 自交。

⚠️ Award 這 3 件是 **weighted mesh(vertices.len != uvs.len)**、靠骨骼權重變形、
   **無 deform timeline** → 無真實位移場可轉移,故本閘**不跑 deform 轉移**(依 RULES
   不用未校準 stress_field)。strip/Delaunay 的耐變形已在 main_draw 窗簾另行驗證。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_mesh, mesh_pixel_coords


def load_alpha(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"讀不到: {path}")
    if img.ndim == 3 and img.shape[2] == 4:
        a = img[:, :, 3]
    else:
        g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        a = g
    return (a > 8).astype(np.uint8)


def fill_mesh(pts_px, tris, H, W):
    """把三角形填成 0/1 覆蓋圖(pts_px = Nx2 像素座標)。"""
    canvas = np.zeros((H, W), np.uint8)
    for t in tris:
        poly = np.round(pts_px[t]).astype(np.int32)
        cv2.fillConvexPoly(canvas, poly, 1)
    return canvas


def iou(a, b):
    u = int(np.logical_or(a, b).sum())
    return int(np.logical_and(a, b).sum()) / u if u else 0.0


def artist_mesh_px(award_att, W, H):
    """Award 真實 mesh 的 uv → 件像素框(uv 已驗為 region-local 0..1)。"""
    uvs = np.array(award_att["uvs"]).reshape(-1, 2)
    tris = np.array(award_att["triangles"], dtype=np.int32).reshape(-1, 3)
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    return pts, tris


def seg_intersect(p1, p2, p3, p4):
    """兩線段是否『真正交叉』(不含共端點)。"""
    def ccw(a, b, c):
        return (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
    d1, d2 = ccw(p3, p4, p1), ccw(p3, p4, p2)
    d3, d4 = ccw(p1, p2, p3), ccw(p1, p2, p4)
    return (d1*d2 < 0) and (d3*d4 < 0)


def static_self_intersections(pts, tris):
    """setup pose 下,計數彼此不共頂點的三角形『邊-邊』真交叉對(近似自交偵測)。"""
    edges = set()
    for t in tris:
        for a, b in ((t[0], t[1]), (t[1], t[2]), (t[2], t[0])):
            edges.add((min(a, b), max(a, b)))
    edges = list(edges)
    n = 0
    for i in range(len(edges)):
        a, b = edges[i]
        for j in range(i + 1, len(edges)):
            c, d = edges[j]
            if len({a, b, c, d}) < 4:      # 共端點跳過
                continue
            if seg_intersect(pts[a], pts[b], pts[c], pts[d]):
                n += 1
    return n


def validate_piece(piece_png, award_att, iou_margin=0.02, budget=80):
    mask = load_alpha(piece_png)
    H, W = mask.shape

    mesh = gen_v2(piece_png, mode="auto")
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    gen_pts, _, _ = mesh_pixel_coords(mesh)
    gen_tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    nv = len(mesh["uvs"]) // 2

    # 覆蓋圖
    gen_fill = fill_mesh(gen_pts, gen_tris, H, W)
    art_pts, art_tris = artist_mesh_px(award_att, W, H)
    art_fill = fill_mesh(art_pts, art_tris, H, W)

    gen_iou_alpha = iou(gen_fill, mask)
    art_iou_alpha = iou(art_fill, mask)          # 藝術家 baseline
    mesh_mesh_iou = iou(gen_fill, art_fill)       # 拓樸相似度

    fmt = eval_mesh(mesh, mask, vertex_budget=budget)
    degen = fmt["criteria"]["AC2b_degenerate"]["value"]
    orphan = fmt["criteria"]["AC2c_orphans"]["value"]
    si = static_self_intersections(gen_pts, gen_tris)

    art_nv = len(award_att["uvs"]) // 2
    art_weighted = len(award_att["vertices"]) != len(award_att["uvs"])

    cover_pass = gen_iou_alpha >= art_iou_alpha - iou_margin
    overall = (cover_pass and fmt["criteria"]["AC4_format"]["pass"]
               and degen == 0 and orphan == 0 and si == 0
               and nv <= budget)
    return {
        "generated": {"vertices": nv, "hull": mesh["hull"],
                      "triangles": len(gen_tris), "mode": mesh.get("_mode")},
        "artist_real": {"vertices": art_nv, "hull": award_att["hull"],
                        "triangles": len(award_att["triangles"]) // 3,
                        "weighted": art_weighted,
                        "note": "bone-driven, no deform timeline"},
        "AC_coverage_iou": {"generated": round(gen_iou_alpha, 4),
                            "artist_baseline": round(art_iou_alpha, 4),
                            "margin": iou_margin, "pass": bool(cover_pass)},
        "AC_mesh_to_mesh_iou": round(mesh_mesh_iou, 4),
        "AC_format": {"pass": fmt["criteria"]["AC4_format"]["pass"],
                      "degenerate": int(degen), "orphans": int(orphan)},
        "AC_static_self_intersections": {"value": int(si), "pass": si == 0},
        "AC_vertex_budget": {"value": nv, "budget": budget, "pass": nv <= budget},
        "overall_pass": bool(overall),
    }


# PSD 件檔名(psd_slice z 序) → Award slot(皆 mesh)
MESH_PIECES = {
    "00_光暈.png": "機器人拆件/光暈",
    "03_身體.png": "機器人拆件/身體",
    "04_左手.png": "機器人拆件/左手",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts-dir", default="/tmp/robot_parts")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    aw = json.load(open(a.award))
    skin = aw["skins"][0]["attachments"]
    out = {}
    all_pass = True
    for fn, slot in MESH_PIECES.items():
        att = skin[slot][slot]
        rep = validate_piece(os.path.join(a.parts_dir, fn), att, a.margin)
        out[slot] = rep
        all_pass = all_pass and rep["overall_pass"]
    out["_overall_pass"] = all_pass
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
