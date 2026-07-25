#!/usr/bin/env python3
"""端到端驗收:真實生產 PSD 件 → S3 generate_mesh_v2 → 對照 Award 真實藝術家 mesh。

這是「PSD→件→mesh」對**真實生產標的**的整合 AC(有藝術家真值可比,純 CPU 可自驅)。
流程:psd_slice 切件 → 對 mesh 件跑 generate_mesh_v2(auto) → 量靜態覆蓋率 IoU,
與 Award 對應 slot 的藝術家 mesh 覆蓋率並列比較。

⚠️ 座標校驗(2026-07-25,已對件 alpha 真值校準):
  - Award mesh `uvs` 為 **region-local 0..1、v top-down**(非 atlas-page 正規化)。
    校驗:vtop IoU 0.95~0.98 >> vflip 0.43~0.60 → 確認朝向。
    (修正 sess006 open note「需先轉 region 局部」— 實測本就是 region-local。)
  - generate_mesh_v2 產出的 uvs 同樣 region-local 0..1、v top-down → 直接同框比較。

⚠️ deform 真值缺口(honest):Award 機器人 mesh 為 **weighted(骨骼驅動)、無 deform timeline**,
   本生成器產 **unweighted** mesh。故此處只做**靜態覆蓋率**對照;變形對照需先做 BBW 骨權重
   (S3 roadmap)才能對等比較。詳見 knowledge/s3-psd-to-award-mesh.md。
"""
import argparse, json, os, sys, tempfile
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import cv2
from generate_mesh_v2 import generate as gen_v2
from psd_slice import slice_psd

# PSD 圖層名 → Award slot(=attachment);只列 Award 中為 mesh 的件
DEFAULT_MAP = {"光暈": "機器人拆件/光暈", "身體": "機器人拆件/身體", "左手": "機器人拆件/左手"}


def _iou(a, b):
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def _fill(pix, tris, H, W):
    m = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(m, np.round(pix[t]).astype(np.int32), 1)
    return m


def _coverage(uvs, tris, mask):
    """mesh 三角形對 mask 的覆蓋率 IoU。uvs=region-local 0..1、v top-down。"""
    H, W = mask.shape
    pix = np.column_stack([uvs[:, 0] * (W - 1), uvs[:, 1] * (H - 1)])
    return _iou(_fill(pix, tris.reshape(-1, 3), H, W), mask)


def compare(psd_path, award_json, mapping=DEFAULT_MAP, iou_margin=0.03):
    sk = json.load(open(award_json))
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)

    with tempfile.TemporaryDirectory() as td:
        _, manifest, parts = slice_psd(psd_path, td)
        by_name = {e["name"]: (e, im) for e, im in parts}
        rep = {"psd": os.path.basename(psd_path), "pieces": []}
        for layer, slot in mapping.items():
            if layer not in by_name:
                rep["pieces"].append({"layer": layer, "error": "PSD 無此圖層"}); continue
            _, im = by_name[layer]
            mask = (np.array(im.split()[-1]) > 8).astype(np.uint8)
            H, W = mask.shape
            fn = os.path.join(td, "_p.png"); im.save(fn)

            a = att[slot][slot]
            a_uv = np.array(a["uvs"]).reshape(-1, 2); a_tri = np.array(a["triangles"])
            a_iou = _coverage(a_uv, a_tri, mask)

            m = gen_v2(fn, mode="auto")
            g_uv = np.array(m["uvs"]).reshape(-1, 2); g_tri = np.array(m["triangles"])
            g_iou = _coverage(g_uv, g_tri, mask)

            rep["pieces"].append({
                "layer": layer, "slot": slot, "piece_wh": [W, H],
                "artist": {"iou": round(a_iou, 4), "verts": len(a_uv),
                           "hull": int(a.get("hull", 0)), "tris": len(a_tri) // 3},
                "gen_v2": {"iou": round(g_iou, 4), "mode": m.get("_mode"),
                           "verts": len(g_uv), "hull": m["hull"], "tris": len(g_tri) // 3},
                "gen_minus_artist": round(g_iou - a_iou, 4),
                "pass": g_iou >= a_iou - iou_margin,
            })
    rep["iou_margin"] = iou_margin
    rep["overall_pass"] = all(p.get("pass") for p in rep["pieces"])
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--margin", type=float, default=0.03)
    a = ap.parse_args()
    rep = compare(a.psd, a.award, iou_margin=a.margin)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
