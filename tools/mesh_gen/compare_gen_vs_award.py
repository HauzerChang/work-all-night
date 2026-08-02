#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 generate_mesh_v2 → 對照 Award 真實 mesh。

背景(見 knowledge/s4-psd-to-spine-real.md):robot_parts.psd 的 光暈/身體/左手 三件
在生產 spine `Award` 中是 **mesh**(weighted、無 deform timeline,靠骨骼/權重變形)。
本工具把「我們生成的 mesh」與「藝術家手做 mesh」放在同一個真值(PSD 切件 alpha)上比覆蓋率,
做端到端「PSD→件→mesh」對真實生產標的的靜態驗收。

真值來源:PSD 切件 alpha(texture-IoU 0.92~0.99 已確認 = spine 生產貼圖素材,同一份)。

對照方式(避開 atlas 旋轉/縮放糾纏):
  - 生成 mesh:evaluate() 在切件像素框內算 IoU_gen(座標框一致)。
  - 藝術家 mesh:uvs 為 region-local 正規化 [0,1](與 main_draw 同慣例,已驗),
    直接 uvs*(maskW,maskH) 光柵化三角面 → IoU_artist(同一張切件 alpha)。
  兩者都是「對同一件形狀的覆蓋率」→ 可比。pass 準則:IoU_gen >= IoU_artist - margin。

deform 閘:此 3 件在 Award **無 deform timeline**(bone-weighted),故不套真實位移場轉移閘;
  改記錄頂點預算對照 + 生成 mesh setup 拓樸乾淨(0 自交)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from evaluate_mesh import evaluate, load_mask, mesh_pixel_coords
from generate_mesh_v2 import generate as gen_v2


def skin_att(sk):
    s = sk["skins"]
    s = s[0] if isinstance(s, list) else s
    return s.get("attachments", s)


def artist_mesh(sk, slot):
    att = skin_att(sk)[slot]
    name, a = next(iter(att.items()))
    return name, a


def rasterize_uv(uvs, tris, W, H):
    """用 region-local uvs*(W,H) 光柵化三角面成二值遮罩。"""
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    return recon


def iou(a, b):
    a = a > 0; b = b > 0
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def self_intersections(pts, tris):
    """setup pose 下三角面兩兩相交計數(退化/翻面偵測用簡易版:面積<=0 計為壞面)。"""
    bad = 0
    for t in tris:
        p = pts[t]
        area = 0.5 * ((p[1, 0] - p[0, 0]) * (p[2, 1] - p[0, 1]) -
                      (p[2, 0] - p[0, 0]) * (p[1, 1] - p[0, 1]))
        if area <= 0:
            bad += 1
    return bad


def compare_one(sk, slot, piece_png, margin):
    mask = load_mask(piece_png)
    H, W = mask.shape

    # 生成 mesh
    g = gen_v2(piece_png, mode="auto")
    g = g[0] if isinstance(g, tuple) else g
    ev = evaluate(g, mask)
    iou_gen = ev["criteria"]["AC1_iou"]["value"]
    gpts, gW, gH = mesh_pixel_coords(g)
    gtris = np.array(g["triangles"]).reshape(-1, 3)
    gbad = self_intersections(gpts, gtris)

    # 藝術家 mesh:uvs region-local → 切件框光柵化
    aname, a = artist_mesh(sk, slot)
    auvs = np.array(a["uvs"]).reshape(-1, 2)
    atris = np.array(a["triangles"]).reshape(-1, 3)
    recon_a = rasterize_uv(auvs, atris, W, H)
    iou_artist = iou(recon_a, mask)
    # 方向自檢:若過低,試 v 翻轉(atlas v 慣例不同)
    flip = None
    if iou_artist < 0.7:
        auvs_f = auvs.copy(); auvs_f[:, 1] = 1.0 - auvs_f[:, 1]
        recon_f = rasterize_uv(auvs_f, atris, W, H)
        io_f = iou(recon_f, mask)
        if io_f > iou_artist:
            iou_artist, flip = io_f, "v"

    nv_gen = len(g["uvs"]) // 2
    nv_art = len(a["uvs"]) // 2
    passed = iou_gen >= iou_artist - margin
    return {
        "slot": slot, "artist_attachment": aname,
        "piece": os.path.basename(piece_png), "piece_wh": [W, H],
        "generated": {"vertices": nv_gen, "hull": g["hull"],
                      "triangles": len(gtris), "mode": g.get("_mode"),
                      "iou_vs_piece": round(iou_gen, 4),
                      "setup_bad_triangles": gbad},
        "artist": {"vertices": nv_art, "hull": a.get("hull"),
                   "triangles": len(atris), "weighted": len(a["vertices"]) != len(a["uvs"]),
                   "iou_vs_piece": round(iou_artist, 4),
                   "uv_flip_applied": flip},
        "AC_coverage": {"margin": margin,
                        "gen_ge_artist_minus_margin": passed,
                        "delta": round(iou_gen - iou_artist, 4)},
        "AC_setup_clean": {"pass": gbad == 0, "bad_triangles": gbad},
        "vertex_budget": {"gen": nv_gen, "artist": nv_art,
                          "gen_within_artist": nv_gen <= nv_art},
        "overall_pass": bool(passed and gbad == 0),
    }


DEFAULT_MAP = {
    "機器人拆件/光暈": "00_光暈.png",
    "機器人拆件/身體": "03_身體.png",
    "機器人拆件/左手": "04_左手.png",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--slices", default="/tmp/robot_slices")
    ap.add_argument("--margin", type=float, default=0.03)
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reports = []
    for slot, fn in DEFAULT_MAP.items():
        piece = os.path.join(a.slices, fn)
        reports.append(compare_one(sk, slot, piece, a.margin))
    allpass = all(r["overall_pass"] for r in reports)
    out = {"reports": reports, "all_pass": allpass,
           "n_pass": sum(r["overall_pass"] for r in reports), "n": len(reports)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
