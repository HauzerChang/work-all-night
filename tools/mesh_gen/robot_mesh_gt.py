#!/usr/bin/env python3
"""端到端 S3 對真實生產標的驗收:PSD 機器人件 → generate_mesh_v2 → 對照 Award 真實 mesh。

背景(log 005/006):robot_parts.psd 5 件 ⇄ Award spine slot `機器人拆件/<圖層名>`。
其中 3 件是 **weighted mesh(綁骨、無 deform timeline)**:光暈 / 左手 / 身體。
本工具把「Award 真實藝術家 mesh」當作 ground truth,對照我方 generator 的拓樸/覆蓋率。

實測校正(本 session):Award mesh 的 uvs 是 **region 局部 0..1**(u,v 各滿佈 0..1,非整頁 uv;
推翻 log 006「atlas 頁 uv」的推測),且 v 為 top-down(對齊影像座標)。因此映射就是
col=u*cropW, row=v*cropH,對照 atlas_crop 的 derotate 後切件即可。
自我品質閘:artist mesh 映射後應高覆蓋(≥0.90);負對照 = v-flip(應明顯崩壞),
確認映射(含 atlas_crop CW derotate)正確,再信 generator 對照結果。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atlas_crop import parse_atlas, extract
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate

PARTS = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def artist_region_pixels(uvs, cropW, cropH, flip_v=False):
    """region 局部 uv(0..1)→ derotate 後切件像素 (col, row)。
    flip_v=True 為負對照(v 反轉,應明顯崩壞)。"""
    v = (1 - uvs[:, 1]) if flip_v else uvs[:, 1]
    return np.column_stack([uvs[:, 0] * cropW, v * cropH])


def render_iou(pix, tris, mask):
    H, W = mask.shape
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        poly = np.round(pix[t]).astype(np.int32)
        cv2.fillConvexPoly(recon, poly, 1)
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    return inter / union if union else 0.0


def run(skeleton, atlas, sheet_hint, tmp, iou_margin=0.03):
    sk = json.load(open(skeleton))
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    regions = parse_atlas(atlas)
    os.makedirs(tmp, exist_ok=True)
    out = {"parts": [], "harness_ok": True, "gen_pass": True}

    for nm in PARTS:
        a = att[nm][nm]
        uvs = np.array(a["uvs"]).reshape(-1, 2)
        tris = np.array(a["triangles"]).reshape(-1, 3)
        reg = regions[nm]
        rot = reg.get("rotate", "false") in ("true", "90")

        crop = extract(atlas, sheet_hint, nm)          # derotate 後的 region 切件
        cpath = os.path.join(tmp, "_rp.png"); cv2.imwrite(cpath, crop)
        mask = (crop[:, :, 3] > 8).astype(np.uint8) if crop.ndim == 3 and crop.shape[2] == 4 \
            else (cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) > 8).astype(np.uint8)
        H, W = mask.shape

        # 藝術家 mesh 映射(region-local uv;負對照 = v-flip)
        iou_art = render_iou(artist_region_pixels(uvs, W, H, False), tris, mask)
        iou_flip = render_iou(artist_region_pixels(uvs, W, H, True), tris, mask)
        # 正對照高覆蓋 + 負對照明顯崩壞 → 映射(含 CW derotate)可信
        harness_part_ok = iou_art >= 0.90 and iou_art >= iou_flip + 0.15
        out["harness_ok"] &= harness_part_ok

        # generator 對照(同一 region alpha)
        m = gen_v2(cpath, mode="auto")
        ev = evaluate(m, mask, vertex_budget=64)
        gen_iou = ev["criteria"]["AC1_iou"]["value"]
        fmt_ok = ev["criteria"]["AC4_format"]["pass"]
        orph = ev["criteria"]["AC2c_orphans"]["value"]
        degen = ev["criteria"]["AC2b_degenerate"]["value"]
        nv = ev["vertices"]
        gen_part_pass = (gen_iou >= iou_art - iou_margin) and fmt_ok and orph == 0 and degen == 0 and nv <= 64
        out["gen_pass"] &= gen_part_pass

        out["parts"].append({
            "part": nm, "rotate": rot,
            "region_crop": [int(W), int(H)],
            "artist": {"weighted": len(a["vertices"]) != len(a["uvs"]),
                       "nv": len(uvs), "tris": len(tris), "hull": a.get("hull"),
                       "iou": round(iou_art, 4), "iou_vflip_negctrl": round(iou_flip, 4)},
            "generated": {"mode": m.get("_mode"), "nv": nv, "tris": ev["triangles"],
                          "hull": m["hull"], "iou": round(gen_iou, 4),
                          "orphans": orph, "degenerate": degen, "format_ok": fmt_ok},
            "artist_baseline_iou": round(iou_art, 4),
            "gen_vs_artist_margin": round(gen_iou - iou_art, 4),
            "vertex_efficiency_vs_artist": round(nv / max(len(uvs), 1), 3),
            "harness_self_check_pass": bool(harness_part_ok),
            "generation_pass": bool(gen_part_pass),
        })

    out["overall_pass"] = bool(out["harness_ok"] and out["gen_pass"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--sheet", default="assets/Award.png")
    ap.add_argument("--tmp", default="/tmp/robot_gt")
    a = ap.parse_args()
    rep = run(a.skeleton, a.atlas, a.sheet, a.tmp)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
