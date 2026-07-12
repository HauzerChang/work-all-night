#!/usr/bin/env python3
"""端到端「PSD 件 → S3 mesh → 對照 Award 真實 mesh」驗收(有 ground truth 的整合 AC)。

背景:`Award.json`(機器人 big win 生產 spine)裡 3 件是 **weighted mesh**
(光暈 78v / 身體 98v / 左手 80v),由骨骼權重變形、**無 deform timeline**
→ 不能跑 `deform_eval` 的真實位移場閘。改用**靜態覆蓋率對照藝術家真值**:
用同一件的 alpha,量「生成 mesh 覆蓋率(IoU)」vs「藝術家 mesh 覆蓋率」,
在頂點預算 ≤ 藝術家 的前提下,IoU 需 ≥ 藝術家基準(margin 內)且 setup pose 幾何乾淨。

關鍵發現(2026-07-12):v1 預設 `epsilon_frac=0.008` 是**周長比例**,對大件(光暈周長
~1900px)邊界過度簡化 → 覆蓋率掉到 0.929(藝術家 0.980)。改成**固定絕對像素容差**
(`eps_px≈3px` → `eps_frac = eps_px / perimeter`)後,3 件全在 ≤ 藝術家頂點數下
IoU ≥ 藝術家。此規則對 main_draw 窗簾(小件)幾乎不變(0.008×小周長 ≈ 3px)。

來源 alpha 兩條路都驗:
  - `--src psd` :從 `robot_parts.psd` 切件(端到端 PSD→件→mesh,預設)。
  - `--src atlas`:從 `Award` atlas 切件(與 validate_against_real 同機制,交叉檢查)。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from generate_mesh import generate as gen_v1
from evaluate_mesh import evaluate, load_mask
from atlas_crop import extract as atlas_extract
from psd_slice import slice_psd

MESH_SLOTS = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def perimeter(mask):
    cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    c = max(cnts, key=cv2.contourArea)
    return cv2.arcLength(c, True)


def artist_mesh(sk, slot):
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[slot][slot]


def artist_iou(a, mask):
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


def psd_piece_alpha(psd_dir_cache):
    """回傳 {圖層名: alpha PNG 路徑}(從 robot_parts.psd 切件)。"""
    _, manifest, parts = slice_psd("assets/robot_parts.psd", psd_dir_cache)
    out = {}
    for e in manifest["parts"]:
        # slice_psd 已把各件寫成 NN_<name>.png
        for f in os.listdir(psd_dir_cache):
            if f.endswith(f"_{e['name']}.png"):
                out[e["name"]] = os.path.join(psd_dir_cache, f)
    return out


def validate_one(sk, slot, crop_path, eps_px, iou_margin):
    mask = load_mask(crop_path)
    mesh, _ = gen_v1(crop_path, eps_px=eps_px)  # 固定絕對像素邊界容差
    nv = len(mesh["uvs"]) // 2

    crit = evaluate(mesh, mask)["criteria"]
    gi = crit["AC1_iou"]["value"]
    clean = crit["AC2b_degenerate"]["pass"] and crit["AC2c_orphans"]["pass"] \
        and crit["AC2a_centroid_in_mask"]["pass"]

    a = artist_mesh(sk, slot)
    a_nv = len(a["uvs"]) // 2
    ai = artist_iou(a, mask)

    iou_pass = gi >= ai - iou_margin
    budget_pass = nv <= a_nv
    return {
        "slot": slot,
        "gen": {"vertices": nv, "iou": round(gi, 4), "eps_px": eps_px,
                "geom_clean": bool(clean)},
        "artist": {"vertices": a_nv, "iou": round(ai, 4)},
        "iou_pass": bool(iou_pass),
        "vertex_budget_pass": bool(budget_pass),
        "pass": bool(iou_pass and budget_pass and clean),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--src", choices=["psd", "atlas"], default="atlas",
                    help="atlas=權威(藝術家 mesh 在 atlas footprint 上作圖);"
                         "psd=端到端 PSD→件→mesh 交叉檢查(藝術家基準因 frame 錯位偏低)")
    ap.add_argument("--eps-px", type=float, default=3.5)
    ap.add_argument("--iou-margin", type=float, default=0.0)
    ap.add_argument("--tmp", default="/tmp/award_mesh")
    a = ap.parse_args()
    os.makedirs(a.tmp, exist_ok=True)
    sk = json.load(open(a.award))

    psd_map = psd_piece_alpha(os.path.join(a.tmp, "psd")) if a.src == "psd" else None

    reports = []
    for slot in MESH_SLOTS:
        leaf = slot.split("/")[-1]
        crop = os.path.join(a.tmp, f"{leaf}.png")
        if a.src == "psd":
            src = psd_map.get(leaf)
            if src is None:
                raise SystemExit(f"PSD 找不到件: {leaf}")
            img = cv2.imread(src, cv2.IMREAD_UNCHANGED)
            cv2.imwrite(crop, img)
        else:
            sub = atlas_extract(a.atlas, a.png, slot)
            cv2.imwrite(crop, sub)
        reports.append(validate_one(sk, slot, crop, a.eps_px, a.iou_margin))

    overall = all(r["pass"] for r in reports)
    print(json.dumps({"src": a.src, "eps_px": a.eps_px,
                      "results": reports, "overall_pass": overall},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
