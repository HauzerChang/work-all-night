#!/usr/bin/env python3
"""S3 對真實生產 spine(Award)靜態驗收 — 機器人拆件 mesh 件。

背景:Award(big win)裡「機器人拆件/光暈|身體|左手」是**weighted mesh 且無 deform
timeline**(靠骨骼權重變形,非逐頂點 deform)。故不能用 validate_against_real 的真實
位移場 deform 閘(那需要 deform timeline)。這裡做**靜態幾何**驗收,對照藝術家真值:

  ① 校準(評估器可信度先驗):把藝術家自己的 mesh 用 uvs*(W,H) 光柵化,量對 atlas 切件
     alpha 的自身 IoU。高(~0.97~0.98)才證明「atlas 切件 ↔ 藝術家 uvs」座標映射正確
     (含 rotate=true 件由 atlas_crop derotate 對齊)。
  ② 生成:對同一張 atlas 切件跑 generate_mesh_v2 → 得生成 mesh。
  ③ 判定:生成 IoU ≥ 藝術家自身 IoU(以藝術家覆蓋率為基準,非武斷閾值)
     + 靜態品質閘(0 退化 / 0 孤兒 / 重心全在 mask 內 / 合法 Spine 格式)。

發現(見 knowledge/s3-award-mesh-static.md):dense/複雜輪廓件用預設 epsilon_frac=0.008
太粗(hull 14~21,IoU 差 0.05);**epsilon_frac=0.002**(hull 37~43)對 3 件全過藝術家
IoU,且頂點數 97~103 落在藝術家 78~98 鄰域。

⚠️ 限制:deform 穩健性未在此驗(這些件無真實位移場;未用未校準的合成壓力,避免假性結論)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import load_mask, evaluate
from generate_mesh_v2 import generate as genv2

PIECES = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def artist_mesh(skeleton, name):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[name][name]
    return (np.array(a["uvs"]).reshape(-1, 2),
            np.array(a["triangles"]).reshape(-1, 3), a.get("hull"))


def raster(uvs, tris, W, H):
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return recon


def validate_piece(sk, atlas, png, name, epsilon, tmp_dir):
    sub = extract(atlas, png, name)
    crop = os.path.join(tmp_dir, "_award_piece.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)
    H, W = mask.shape

    a_uv, a_tri, a_hull = artist_mesh(sk, name)
    a_recon = raster(a_uv, a_tri, W, H)
    base = float(np.logical_and(a_recon, mask).sum() / np.logical_or(a_recon, mask).sum())

    m = genv2(crop, mode="auto", epsilon_frac=epsilon)
    ev = evaluate(m, mask)["criteria"]
    gi = ev["AC1_iou"]["value"]
    gv = len(m["uvs"]) // 2
    quality_ok = (ev["AC2a_centroid_in_mask"]["pass"] and ev["AC2b_degenerate"]["pass"]
                  and ev["AC2c_orphans"]["pass"] and ev["AC4_format"]["pass"])

    return {
        "piece": name,
        "calib_artist_self_iou": round(base, 4),
        "artist": {"vertices": len(a_uv), "hull": a_hull, "triangles": len(a_tri)},
        "generated": {"mode": m.get("_mode"), "vertices": gv, "hull": m["hull"],
                      "triangles": len(m["triangles"]) // 3, "iou": round(gi, 4)},
        "quality": {"degenerate": ev["AC2b_degenerate"]["value"],
                    "orphans": ev["AC2c_orphans"]["value"],
                    "centroid_in_mask": ev["AC2a_centroid_in_mask"]["value"],
                    "format_ok": ev["AC4_format"]["pass"]},
        "iou_pass": gi >= base,
        "quality_pass": quality_ok,
        "overall_pass": (gi >= base) and quality_ok,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--epsilon", type=float, default=0.002)
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reps = [validate_piece(sk, a.atlas, a.png, name, a.epsilon, a.tmp) for name in PIECES]
    allpass = all(r["overall_pass"] for r in reps)
    print(json.dumps({"epsilon_frac": a.epsilon, "pieces": reps, "all_pass": allpass},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
