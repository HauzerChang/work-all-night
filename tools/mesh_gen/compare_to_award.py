#!/usr/bin/env python3
"""S3 端到端驗收:PSD件/atlas件 → S3 mesh → 對照 Award 真實(藝術家)mesh。

目的(見 STATE 下一步候選 #1):把 S3 生成器對「真實生產標的」驗收 —— 拿 Award spine 裡
機器人的 3 個 **mesh** attachment(光暈 / 左手 / 身體;右手、頭為 region 不比)當藝術家真值,
與 S3 自動生成的 mesh 在**同一張素材、同一像素空間**下做覆蓋率 / 拓樸精簡度 / 足跡一致性比對。

共同座標框(關鍵):用 atlas_crop 把該 slot 的 region 去旋轉裁成「上正」的素材圖(0.70 縮放版,
但兩邊都用同一張 → IoU 尺度無關)。
  - 藝術家 mesh:JSON 存的 `uvs` 為 region-local 正規化 [0,1] → uv*(regW,regH) 映進 region 像素。
  - S3 mesh:直接對這張 region alpha 跑 generate_mesh_v2(auto) 生成 → 座標本就在 region 像素。
兩者都對「同一張 region alpha」量覆蓋率 → 公平比對。

註:這些 slot 在 9(12)支動畫**無 deform timeline**(藝術家 mesh 為 weighted 供自由變形/綁骨,
非時間軸驅動)→ 本比對聚焦**靜態覆蓋率 + 拓樸**;deform 穩健度另由 deform_eval 對 S3 mesh 單獨驗。

AC(可機讀):
  A. 藝術家 mesh 覆蓋率 IoU(vs region alpha)≥ 0.90  —— 同時驗證 uv→pixel 映射正確。
  B. S3 mesh 覆蓋率 IoU ≥ 0.90 且 ≥ 藝術家 IoU − 0.05   —— S3 覆蓋不遜於藝術家。
  C. S3 頂點數 ≤ max(藝術家頂點數 × 1.6, 藝術家 + 20)      —— 精簡度可比(不爆量)。
  D. 足跡一致性:S3 覆蓋遮罩 ∩ 藝術家覆蓋遮罩 IoU ≥ 0.85   —— 兩三角化足跡一致。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from atlas_crop import extract
import generate_mesh_v2 as g2
import evaluate_mesh as em

MESH_SLOTS = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def region_alpha(bgra):
    if bgra.ndim == 3 and bgra.shape[2] == 4:
        return (bgra[:, :, 3] > 8).astype(np.uint8)
    g = bgra if bgra.ndim == 2 else cv2.cvtColor(bgra, cv2.COLOR_BGR2GRAY)
    return (g > 8).astype(np.uint8)


def raster_uv_mesh(uvs, tris, W, H):
    """把藝術家 mesh(uvs 為 region-local 0..1,triangles)填成覆蓋遮罩(region 像素)。"""
    pts = np.array([[uvs[2 * i] * W, uvs[2 * i + 1] * H] for i in range(len(uvs) // 2)], np.float64)
    m = np.zeros((H, W), np.uint8)
    for t in np.array(tris, np.int32).reshape(-1, 3):
        cv2.fillConvexPoly(m, np.round(pts[t]).astype(np.int32), 1)
    return m, pts


def raster_pixel_mesh(mesh):
    """把 S3 mesh(vertices y-up 置中)還原成 region 像素覆蓋遮罩。"""
    pts, W, H = em.mesh_pixel_coords(mesh)
    m = np.zeros((H, W), np.uint8)
    for t in np.array(mesh["triangles"], np.int32).reshape(-1, 3):
        cv2.fillConvexPoly(m, np.round(pts[t]).astype(np.int32), 1)
    return m


def iou(a, b):
    inter = int(np.logical_and(a, b).sum())
    union = int(np.logical_or(a, b).sum())
    return inter / union if union else 0.0


def compare_one(slot, art_att, atlas, sheet, tmpdir):
    reg = extract(atlas, sheet, slot)
    alpha = region_alpha(reg)
    H, W = alpha.shape

    # 藝術家 mesh 覆蓋率
    art_mask, _ = raster_uv_mesh(art_att["uvs"], art_att["triangles"], W, H)
    art_iou = iou(art_mask, alpha)
    art_nv = len(art_att["uvs"]) // 2

    # S3:對同一張 region alpha 生成 mesh
    piece_png = os.path.join(tmpdir, slot.replace("/", "_") + ".png")
    cv2.imwrite(piece_png, reg)
    s3 = g2.generate(piece_png)  # auto mode
    s3_mask = raster_pixel_mesh(s3)
    s3_iou = iou(s3_mask, alpha)
    s3_nv = len(s3["uvs"]) // 2

    foot_iou = iou(s3_mask, art_mask)

    ac = {
        "A_art_covers": {"pass": art_iou >= 0.90, "art_iou": round(art_iou, 4)},
        "B_s3_covers": {"pass": s3_iou >= 0.90 and s3_iou >= art_iou - 0.05,
                        "s3_iou": round(s3_iou, 4)},
        "C_parsimony": {"pass": s3_nv <= max(int(art_nv * 1.6), art_nv + 20),
                        "s3_nv": s3_nv, "art_nv": art_nv},
        "D_footprint": {"pass": foot_iou >= 0.85, "footprint_iou": round(foot_iou, 4)},
    }
    return {
        "slot": slot, "region_px": f"{W}x{H}", "mode": s3.get("_mode"),
        "art": {"nv": art_nv, "tris": len(art_att["triangles"]) // 3, "hull": art_att.get("hull")},
        "s3": {"nv": s3_nv, "tris": len(s3["triangles"]) // 3, "hull": s3["hull"]},
        "criteria": ac,
        "pass": all(c["pass"] for c in ac.values()),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award-json", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--sheet", default="assets/Award.png")
    ap.add_argument("--tmp", default="/tmp/claude-0/-home-user-work-all-night/db6ac5fd-d95b-57ea-9f84-2877e54a42c1/scratchpad")
    a = ap.parse_args()
    os.makedirs(a.tmp, exist_ok=True)

    aw = json.load(open(a.award_json))
    skin = [s for s in aw["skins"] if s["name"] == "default"][0]
    reports = []
    for slot in MESH_SLOTS:
        att = skin["attachments"][slot][slot]
        assert att["type"] == "mesh", f"{slot} 非 mesh"
        reports.append(compare_one(slot, att, a.atlas, a.sheet, a.tmp))

    overall = all(r["pass"] for r in reports)
    print(json.dumps({"overall_pass": overall, "pieces": reports}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
