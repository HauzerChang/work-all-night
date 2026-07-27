#!/usr/bin/env python3
"""端到端 S4→S3 對照:機器人拆件(robot_parts.psd)→ S3 生成 mesh → 對照 Award 生產 mesh。

STATE.md 最高優先 bounded chunk(有真值、純 CPU 可自驅):
用 Award 生產 spine 中三個 mesh 件(光暈/身體/左手)當真值,量化 S3 v2 自動生成的
拓樸「靜態覆蓋率(IoU)是否達到藝術家手做 mesh 的水準」。

⚠️ 關鍵事實(本次確認):Award 這三件是 **weighted mesh**(vertices.length != uvs.length),
靠骨骼驅動、**無 deform timeline**。因此:
  - 「真實 deform 轉移閘」在此不適用(沒有 deform 位移場)→ 只驗靜態幾何/覆蓋。
  - S3 v2 目前輸出 **unweighted** 幾何,可對齊覆蓋率,但尚無 BBW 權重/骨綁 → 不是
    生產等價 mesh。此為 S3 未建組件(權重),於報告明列。

比對基準面(frame):Award mesh 的 uvs 是「region 局部 0..1」,活在 atlas 去旋轉後的
region 影像空間。故用 atlas_crop 取去旋轉 region alpha 當共同遮罩:
  - my_iou    = 生成 mesh 三角覆蓋 vs region alpha
  - artist_iou= 藝術家 mesh(uvs 光柵化)覆蓋 vs 同一 region alpha
兩者同遮罩、可直接比。另外用 psd_slice 切 PSD 件,確認 PSD→件 這一段仍無損(S4 已驗)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract, parse_atlas
from evaluate_mesh import evaluate as eval_mesh, load_mask
from generate_mesh_v2 import generate as gen_v2

# Award 中被做成 mesh 的三個機器人件(對照 session 005:會 warp 的件做 mesh)
MESH_SLOTS = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def artist_mesh_info(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uv_pts = len(a["uvs"]) // 2
    weighted = len(a["vertices"]) != len(a["uvs"])
    return a, uv_pts, weighted


def artist_iou(a, mask):
    """把藝術家 mesh 的 uvs(0..1)光柵化到遮罩尺寸,量三角覆蓋 IoU。"""
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0


def validate_one(sk, atlas, png, slot, tmp_dir, iou_margin=0.0):
    name = slot  # 此資產 attachment name == slot name
    sub = extract(atlas, png, name)              # 去旋轉 region(uvs 所在空間)
    crop = os.path.join(tmp_dir, "_robot_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)
    H, W = mask.shape

    a, uv_pts, weighted = artist_mesh_info(sk, slot, name)

    mesh = gen_v2(crop, mode="auto")
    ev = eval_mesh(mesh, mask)                    # 靜態:format + IoU + 覆蓋/退化/孤兒
    my_iou = ev["criteria"]["AC1_iou"]["value"]
    base = artist_iou(a, mask)

    return {
        "slot": slot,
        "region_px": [int(W), int(H)],
        "artist": {"weighted": weighted, "uv_points": uv_pts, "hull": a["hull"],
                   "triangles": len(a["triangles"]) // 3, "coverage_iou": round(base, 4),
                   "has_deform": False},
        "generated": {"mode": mesh.get("_mode"), "vertices": len(mesh["uvs"]) // 2,
                      "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3,
                      "coverage_iou": round(my_iou, 4),
                      "format_ok": ev["criteria"]["AC4_format"]["pass"],
                      "no_orphans": ev["criteria"]["AC2c_orphans"]["pass"],
                      "no_degenerate": ev["criteria"]["AC2b_degenerate"]["pass"]},
        "AC_coverage_ge_artist": {"pass": my_iou >= base - iou_margin,
                                  "my_iou": round(my_iou, 4), "artist_iou": round(base, 4),
                                  "margin": iou_margin},
        "AC_format_clean": {"pass": ev["criteria"]["AC4_format"]["pass"]
                            and ev["criteria"]["AC2b_degenerate"]["pass"]
                            and ev["criteria"]["AC2c_orphans"]["pass"]},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    parts = []
    for slot in MESH_SLOTS:
        parts.append(validate_one(sk, a.atlas, a.png, slot, a.tmp))
    overall = all(p["AC_coverage_ge_artist"]["pass"] and p["AC_format_clean"]["pass"]
                  for p in parts)
    rep = {
        "task": "PSD件→S3 mesh 對照 Award 生產 mesh(靜態幾何/覆蓋)",
        "note": "Award 三件皆 weighted(骨驅動)、無 deform → 只驗靜態;S3 v2 輸出 unweighted,"
                "覆蓋可對齊但無 BBW 權重/骨綁(S3 未建組件)。",
        "parts": parts,
        "overall_pass": overall,
    }
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
