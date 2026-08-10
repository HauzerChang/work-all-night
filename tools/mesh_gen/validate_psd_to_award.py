#!/usr/bin/env python3
"""端到端驗證:PSD 切件 → S3 generate_mesh_v2 → 對照 Award 真實生產 mesh。

這是「PSD→件→mesh」pipeline 對**真實生產標的**的驗收(有藝術家 ground truth)。
標的:robot_parts.psd 的 3 個在 Award spine 中為 mesh 的件(光暈/身體/左手)。

⚠️ 這 3 件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform),
   故**無真實位移場**可轉移。依 RULES「不要用未校準的 stress_field」,本驗收
   **不捏造變形場**,只做靜態拓樸品質對照:
     ① IoU 覆蓋率  vs 藝術家 mesh(同一 alpha 上量,artist 為 baseline)
     ② 頂點預算    vs 藝術家(生成不應遠多於藝術家)
     ③ 靜態 self-intersection / degenerate == 0(合法三角化)
   變形穩健度已在 main_draw 4 mesh(有真實 deform 場)證明,見 s3-four-mesh-generalization.md。

UV 對映(已校驗):Award mesh uvs 為 region-relative [0,1],直接 uv*W, uv*H(**不 flip v**)
   對齊 PSD 切件像素空間 → 藝術家 mesh 覆蓋自身 alpha IoU 0.945/0.948/0.977(見輸出)。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from evaluate_mesh import evaluate, load_mask
from generate_mesh_v2 import generate as gen_v2
import deform_eval as de

# PSD 圖層名 → (Award slot/attachment, 切件檔名)
MESH_PIECES = {
    "光暈": "00_光暈.png",
    "身體": "03_身體.png",
    "左手": "04_左手.png",
}


def raster_mesh(uvs, tris, W, H):
    """把 region-relative uv mesh 填成 piece 像素空間的遮罩(不 flip v)。"""
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    r = np.zeros((H, W), np.uint8)
    for t in tris.reshape(-1, 3):
        cv2.fillConvexPoly(r, np.round(rp[t]).astype(np.int32), 1)
    return r


def iou(a, b):
    return float(np.logical_and(a, b).sum() / max(1, np.logical_or(a, b).sum()))


def artist_mesh(skeleton, slot):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[slot][slot]


def validate_piece(pname, piece_png, award, iou_margin=0.03, vertex_slack=1.30):
    img = cv2.imread(piece_png, cv2.IMREAD_UNCHANGED)
    alpha = (img[:, :, 3] > 10).astype(np.uint8)
    H, W = alpha.shape

    # --- 藝術家 baseline ---
    slot = "機器人拆件/" + pname
    a = artist_mesh(award, slot)
    a_uvs = np.array(a["uvs"]).reshape(-1, 2)
    a_tris = np.array(a["triangles"])
    a_raster = raster_mesh(a_uvs, a_tris, W, H)
    a_iou = iou(a_raster, alpha)
    a_verts = len(a["uvs"]) // 2

    # --- S3 生成 ---
    mesh = gen_v2(piece_png, mode="auto")
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    g_verts = len(mesh["uvs"]) // 2
    g_iou = evaluate(mesh, alpha)["criteria"]["AC1_iou"]["value"]

    # 靜態合法性(setup 頂點,無翻面基準 → 只看自交/退化)
    verts = np.array(mesh["vertices"]).reshape(-1, 2).astype(np.float64)
    tris = np.array(mesh["triangles"]).reshape(-1, 3)
    chk = de.check(verts, tris, None)

    iou_pass = g_iou >= a_iou - iou_margin
    budget_pass = g_verts <= a_verts * vertex_slack
    legal_pass = chk["self_intersections"] == 0 and chk["degenerate"] == 0

    return {
        "piece": pname,
        "piece_px": [int(W), int(H)],
        "artist": {"verts": a_verts, "tris": len(a["triangles"]) // 3,
                   "hull": a["hull"], "iou_vs_alpha": round(a_iou, 4)},
        "generated": {"verts": g_verts, "tris": len(mesh["triangles"]) // 3,
                      "hull": mesh["hull"], "mode": mesh.get("_mode"),
                      "iou_vs_alpha": round(g_iou, 4)},
        "AC_iou_vs_artist": {"gen": round(g_iou, 4), "artist_baseline": round(a_iou, 4),
                             "margin": iou_margin, "pass": bool(iou_pass)},
        "AC_vertex_budget": {"gen": g_verts, "artist": a_verts,
                             "slack_x": vertex_slack, "pass": bool(budget_pass)},
        "AC_static_legal": {"self_intersections": chk["self_intersections"],
                            "degenerate": chk["degenerate"], "pass": bool(legal_pass)},
        "overall_pass": bool(iou_pass and budget_pass and legal_pass),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--pieces", default="/tmp/robot_pieces",
                    help="psd_slice.py 對 robot_parts.psd 的輸出目錄")
    a = ap.parse_args()
    award = json.load(open(a.award))
    reports = []
    for pname, fn in MESH_PIECES.items():
        reports.append(validate_piece(pname, os.path.join(a.pieces, fn), award))
    out = {"reports": reports,
           "all_pass": all(r["overall_pass"] for r in reports)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["all_pass"] else 1)


if __name__ == "__main__":
    main()
