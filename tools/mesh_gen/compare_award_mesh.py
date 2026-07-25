#!/usr/bin/env python3
"""S3×S4 端到端閘 — PSD 件 → 生成 mesh → 對照 Award 真實(藝術家)mesh。

目標:機器人 3 個 mesh 件(光暈/身體/左手,Award 中為 mesh)做「生成 mesh」與
「藝術家 mesh」的 **同一輪廓覆蓋率(IoU)** 對照,回答「S3 能否以精簡頂點達到藝術家覆蓋率」。

共同空間 = **Award atlas region 的 alpha 輪廓**(用 atlas_crop 正確 un-rotate 抽出)。
兩邊 mesh 的 uvs 皆為 region-local 0..1(經校驗:藝術家 mesh 正映射 IoU 0.97~0.98、
v-flip 只 0.44~0.61 → 有鑑別力、方向正確)。normalized 座標對尺度不變,故 PSD 件(原尺寸)
與 atlas region(0.70 縮小)可同框比較。

兩條生成路徑都報:
  - gen_from_region:直接用 atlas region alpha 生成 → 隔離 S3 mesh 品質(同源、apples-to-apples)。
  - gen_from_psd   :用 PSD 切件 alpha 生成 → 真實端到端(含 PSD↔atlas ~0.70 縮放的微差)。

⚠️ Award 這 5 件在 spine **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform),
   故此處**不套用** real_deform_field 閘(那需要 deform timeline)。AC = 靜態輪廓覆蓋率對照。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from generate_mesh_v2 import generate as gen_v2


def region_alpha(atlas, sheet, slot):
    reg = extract(atlas, sheet, slot)
    if reg.ndim == 3 and reg.shape[2] == 4:
        a = (reg[:, :, 3] > 8).astype(np.uint8)
    else:
        g = reg if reg.ndim == 2 else cv2.cvtColor(reg, cv2.COLOR_BGR2GRAY)
        a = (g > 8).astype(np.uint8)
    return a


def raster_uv(uvs, tris, W, H):
    uv = np.array(uvs, float).reshape(-1, 2)
    pts = np.column_stack([uv[:, 0] * W, uv[:, 1] * H])
    canvas = np.zeros((H, W), np.uint8)
    for t in np.array(tris).reshape(-1, 3):
        cv2.fillConvexPoly(canvas, np.round(pts[t]).astype(np.int32), 1)
    return canvas


def iou(a, b):
    return float(np.logical_and(a, b).sum() / max(np.logical_or(a, b).sum(), 1))


def artist_att(sk, slot):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    return atts[slot][slot]


def compare_piece(sk, atlas, sheet, slot, psd_png, rows, cols, v1_kw):
    ra = region_alpha(atlas, sheet, slot)          # 共同輪廓(atlas region)
    H, W = ra.shape

    a = artist_att(sk, slot)
    art_mask = raster_uv(a["uvs"], a["triangles"], W, H)
    art_iou = iou(art_mask, ra)

    # gen from region alpha (同源)
    tmp_r = os.path.join(os.path.dirname(psd_png) or ".", "_reg_tmp.png")
    cv2.imwrite(tmp_r, (ra * 255).astype(np.uint8))
    gr = gen_v2(tmp_r, rows=rows, cols=cols, mode="auto", v1_kw=v1_kw)
    gr_mask = raster_uv(gr["uvs"], gr["triangles"], W, H)
    gr_iou = iou(gr_mask, ra)

    # gen from PSD piece(真實端到端)
    # ⚠️ 正確 AC = 各 mesh 對「自己來源輪廓」的覆蓋率:gen_from_psd 用 PSD 件本身 alpha 評。
    #    另報 iou_vs_region(對 atlas region)作跨源診斷 —— 它被 PSD↔atlas ~0.70 縮放/對位差
    #    封頂(~0.95),非 mesh 品質,不作為 pass 依據。
    gp = gen_v2(psd_png, rows=rows, cols=cols, mode="auto", v1_kw=v1_kw)
    psd_img = cv2.imread(psd_png, cv2.IMREAD_UNCHANGED)
    psd_alpha = (psd_img[:, :, 3] > 8).astype(np.uint8)
    ph, pw = psd_alpha.shape
    gp_own = iou(raster_uv(gp["uvs"], gp["triangles"], pw, ph), psd_alpha)   # 自源(pass 依據)
    gp_reg = iou(raster_uv(gp["uvs"], gp["triangles"], W, H), ra)            # 跨源(診斷)

    return {
        "region_size": [W, H],
        "artist": {"verts": len(a["uvs"]) // 2, "hull": a["hull"],
                    "tris": len(a["triangles"]) // 3, "iou_vs_own": round(art_iou, 4)},
        "gen_from_region": {"mode": gr.get("_mode"), "verts": len(gr["uvs"]) // 2,
                             "hull": gr["hull"], "tris": len(gr["triangles"]) // 3,
                             "iou_vs_own": round(gr_iou, 4),
                             "pass": gr_iou >= art_iou - 0.0},
        "gen_from_psd": {"mode": gp.get("_mode"), "verts": len(gp["uvs"]) // 2,
                         "hull": gp["hull"], "tris": len(gp["triangles"]) // 3,
                         "iou_vs_own": round(gp_own, 4),
                         "iou_vs_region_xsrc": round(gp_reg, 4),
                         "pass": gp_own >= art_iou - 0.0},
    }


PIECES = {          # slot 中文 -> PSD 切件檔名(psd_slice 產出 z 序)
    "光暈": "00_光暈.png",
    "身體": "03_身體.png",
    "左手": "04_左手.png",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--sheet", default="assets/Award.png")
    ap.add_argument("--slices", default="/tmp/robot_slices")
    ap.add_argument("--rows", type=int, default=10)
    ap.add_argument("--cols", type=int, default=3)
    # blob 件 v1 調校(對照 Award 藝術家 mesh 得出的 parity 參數)
    ap.add_argument("--eps", type=float, default=0.002)
    ap.add_argument("--max-interior", type=int, default=60)
    ap.add_argument("--min-dist", type=float, default=10)
    a = ap.parse_args()
    v1_kw = {"epsilon_frac": a.eps, "max_interior": a.max_interior, "min_dist": a.min_dist}
    sk = json.load(open(a.skeleton))
    out = {"_params": {"eps": a.eps, "max_interior": a.max_interior, "min_dist": a.min_dist}}
    all_pass = True
    for zh, fn in PIECES.items():
        slot = f"機器人拆件/{zh}"
        psd_png = os.path.join(a.slices, fn)
        rep = compare_piece(sk, a.atlas, a.sheet, slot, psd_png, a.rows, a.cols, v1_kw)
        out[zh] = rep
        all_pass &= rep["gen_from_region"]["pass"] and rep["gen_from_psd"]["pass"]
    out["_overall_pass"] = all_pass
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all_pass else 1)


if __name__ == "__main__":
    main()
