#!/usr/bin/env python3
"""端到端「PSD 件 → S3 生成 mesh → 對照 Award 真實生產 mesh」驗收(靜態/輪廓級)。

動機(STATE.md 最高優先 chunk):前面 S3 只對 main_draw 的 4 個窗簾/陰影 mesh 驗過,
那些是 deform-timeline mesh。Award(機器人拆件 big win)有 3 個 **weighted/blob mesh**
(光暈/身體/左手),是另一種真實生產標的 —— 用骨骼權重變形、無 deform timeline。
本工具把 `psd_slice` 切出的 PSD 件餵進 `generate_mesh_v2`(blob 件 aspect<1.2 → auto 回退
v1 Delaunay),與 Award 真實 mesh 做**靜態輪廓覆蓋(IoU)+ 拓樸預算**對照。

⚠️ 為何只做靜態:這 3 件在 Award **無 deform timeline**(s4-psd-to-spine-real.md),
靠骨骼/權重變形,沒有真實位移場可轉移 → 不用未校準合成場硬套(RULES 禁)。故此處
驗收 = 輪廓吻合 + 頂點預算,不含 deform 閘。deform 穩健已由 main_draw 4 mesh 驗過。

UV 空間先驗:Award mesh `uvs` 為 region-local 0..1(JSON 慣例;經 atlas rotate/scale
無關),故 `uvs×(W,H)` 直接落在 PSD 件(原始解析度、未旋轉)的輪廓上。artist_iou
高即證實此假設(若 uvs 為 atlas-page 空間會極低)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask


# Award 機器人拆件:3 個 mesh 件 → 對應 PSD 切件檔(psd_slice -o 產出)
ROBOT_MESH_PARTS = [
    {"layer": "光暈", "psd_file": "00_光暈.png", "slot": "機器人拆件/光暈", "name": "機器人拆件/光暈"},
    {"layer": "身體", "psd_file": "03_身體.png", "slot": "機器人拆件/身體", "name": "機器人拆件/身體"},
    {"layer": "左手", "psd_file": "04_左手.png", "slot": "機器人拆件/左手", "name": "機器人拆件/左手"},
]


def artist_mesh(skeleton, slot, name):
    skins = skeleton["skins"]
    skin = skins[0] if isinstance(skins, list) else skins
    att = skin.get("attachments", skin)
    return att[slot][name]


def iou_from_uvs(uvs, tris, mask):
    """artist uvs(region-local 0..1)× mask 尺寸 → 填三角 → IoU vs mask。"""
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    return (inter / union if union else 0.0), recon


def overlay_fig(mask, gen_mesh, artist_recon, gen_recon, out_path):
    """三聯圖:來源 alpha / 生成 mesh 覆蓋 / 藝術家 mesh 覆蓋(疊輪廓)。"""
    H, W = mask.shape
    def panel(cov):
        img = np.zeros((H, W, 3), np.uint8)
        img[mask > 0] = (60, 60, 60)
        img[np.logical_and(cov > 0, mask > 0)] = (0, 160, 0)      # 命中
        img[np.logical_and(cov > 0, mask == 0)] = (0, 0, 200)     # 溢出
        img[np.logical_and(cov == 0, mask > 0)] = (0, 120, 200)   # 漏覆蓋
        return img
    src = np.dstack([mask * 255] * 3)
    strip = np.hstack([src, panel(gen_recon), panel(artist_recon)])
    cv2.imwrite(out_path, strip)


def compare_one(skeleton, parts_dir, part, fig_dir=None, iou_margin=0.03):
    psd_path = os.path.join(parts_dir, part["psd_file"])
    mask = load_mask(psd_path)

    gen = gen_v2(psd_path, mode="auto")
    rep = evaluate(gen, mask)
    gen_iou = rep["criteria"]["AC1_iou"]["value"]
    gen_nv = rep["vertices"]

    # 生成 mesh 的覆蓋圖(像素座標)
    from evaluate_mesh import mesh_pixel_coords
    gpts, _, _ = mesh_pixel_coords(gen)
    gtris = np.array(gen["triangles"]).reshape(-1, 3)
    gen_recon = np.zeros_like(mask)
    for t in gtris:
        cv2.fillConvexPoly(gen_recon, np.round(gpts[t]).astype(np.int32), 1)

    am = artist_mesh(skeleton, part["slot"], part["name"])
    a_uvs = np.array(am["uvs"]).reshape(-1, 2)
    a_tris = np.array(am["triangles"]).reshape(-1, 3)
    a_iou, a_recon = iou_from_uvs(a_uvs, a_tris, mask)
    a_nv = len(a_uvs)
    a_weighted = (len(am.get("vertices", [])) != 2 * a_nv)

    if fig_dir:
        os.makedirs(fig_dir, exist_ok=True)
        overlay_fig(mask, gen, a_recon, gen_recon,
                    os.path.join(fig_dir, f"award_{part['layer']}.png"))

    iou_pass = gen_iou >= a_iou - iou_margin
    fmt_pass = rep["criteria"]["AC4_format"]["pass"]
    budget_pass = gen_nv <= a_nv  # 生成不得比藝術家更冗(頂點預算)
    return {
        "layer": part["layer"], "slot": part["slot"],
        "psd_size": [int(mask.shape[1]), int(mask.shape[0])],
        "generated": {"mode": gen.get("_mode"), "vertices": gen_nv,
                      "hull": gen["hull"], "triangles": rep["triangles"],
                      "iou": round(gen_iou, 4)},
        "artist": {"vertices": a_nv, "hull": int(am["hull"]),
                   "triangles": len(a_tris), "weighted": bool(a_weighted),
                   "iou": round(a_iou, 4)},
        "AC_iou_vs_artist": {"pass": bool(iou_pass), "gen": round(gen_iou, 4),
                             "artist": round(a_iou, 4), "margin": iou_margin},
        "AC_format": {"pass": bool(fmt_pass)},
        "AC_vertex_budget": {"pass": bool(budget_pass), "gen": gen_nv, "artist": a_nv},
        "overall_pass": bool(iou_pass and fmt_pass and budget_pass),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--parts", default="/tmp/robot_parts", help="psd_slice -o 輸出目錄")
    ap.add_argument("--figs", default=None, help="輸出對照三聯圖目錄")
    ap.add_argument("--margin", type=float, default=0.03)
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reports = [compare_one(sk, a.parts, p, a.figs, a.margin) for p in ROBOT_MESH_PARTS]
    out = {"overall_pass": all(r["overall_pass"] for r in reports), "parts": reports}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["overall_pass"] else 1)


if __name__ == "__main__":
    main()
