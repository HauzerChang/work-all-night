#!/usr/bin/env python3
"""端到端「PSD 件 → S3 生成 mesh → 對照 Award 真實生產 mesh」驗收工具。

背景(2026-08-15 這次執行揭示的結構事實):
  - Award 機器人 3 個 mesh 件(光暈/身體/左手)在生產 spine 是 **weighted mesh**
    (vertices.length != uvs.length,每頂點綁 1~2 骨),**且無 deform timeline** —— 形變靠
    骨骼權重驅動,不是靠 deform。這與 main_draw 的 4 個 **unweighted + deform 驅動** mesh
    是不同機制。
  - 因此 S3 的「deform 穩健度閘」(transfer_deform_check,為 deform 驅動 mesh 而建)對這類
    件**不適用**;此處可自動驗的只有「靜態輪廓保真(IoU)」。要真正逼近 Award 這類件,S3 還缺
    **BBW 權重生成**(把幾何綁到骨)—— 屬 S3 路線圖已列、尚未實作的部分。

驗收(可自動、純 CPU、有真值):
  用 psd_slice 切出的件 alpha 當來源 → generate_mesh_v2(auto)產幾何 → 兩項比對:
    ① 靜態 IoU(生成 mesh vs 件 alpha) ≥ 藝術家 mesh 對同一 alpha 的 IoU 基準(margin 內)。
    ② evaluate_mesh 靜態 AC(格式/重心在內/無退化三角/無孤兒/頂點預算)全過。
  藝術家 mesh 的 uvs 為 **region 局部正規化 0..1**(本次驗證:三件 uv 皆近 [0,1]),可直接
  以 uvs*W,uvs*H 填入件遮罩比對(不需再做 atlas→局部轉換;更正 session006 的假設)。

用法:
  python3 tools/mesh_gen/validate_psd_to_award.py \
    --award assets/Award.json --psd assets/robot_parts.psd --parts-dir /tmp/robot_parts
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as ev_static


# PSD 圖層名 → 切件檔名(psd_slice 以 z 序命名),與 Award slot 對應
PIECE_FILES = {"光暈": "00_光暈.png", "身體": "03_身體.png", "左手": "04_左手.png"}


def piece_mask(png):
    img = cv2.imread(png, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"讀不到件: {png}")
    if img.ndim == 3 and img.shape[2] == 4:
        return (img[:, :, 3] > 8).astype(np.uint8)
    g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return (g > 8).astype(np.uint8)


def artist_iou_local(attach, mask):
    """藝術家 mesh(region 局部 uv)填入件遮罩算 IoU。回傳 (iou, nverts, ntris, weighted)。"""
    uvs = np.array(attach["uvs"]).reshape(-1, 2)
    tris = np.array(attach["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    weighted = len(attach["vertices"]) != len(attach["uvs"])
    return (inter / union if union else 0.0), len(uvs), len(tris), weighted


def has_deform(award, slot):
    for an, body in award.get("animations", {}).items():
        for _, slotmap in body.get("deform", {}).items():
            if slot in slotmap:
                return True
    return False


def validate(award_path, parts_dir, iou_margin=0.0, budget=128):
    award = json.load(open(award_path))
    att = award["skins"][0]["attachments"]
    out = {"pieces": [], "overall_pass": True}
    for pname, fn in PIECE_FILES.items():
        slot = f"機器人拆件/{pname}"
        a = att[slot][slot]
        mask = piece_mask(os.path.join(parts_dir, fn))
        H, W = mask.shape
        m = gen_v2(os.path.join(parts_dir, fn), mode="auto")
        rep = ev_static(m, mask, vertex_budget=budget)
        gi = rep["criteria"]["AC1_iou"]["value"]
        ai, av, at, weighted = artist_iou_local(a, mask)
        iou_pass = gi >= ai - iou_margin
        static_pass = rep["overall_pass"]
        piece_pass = iou_pass and static_pass
        out["overall_pass"] = out["overall_pass"] and piece_pass
        out["pieces"].append({
            "piece": pname, "size": [W, H], "aspect": round(H / W, 3),
            "generated": {"mode": m.get("_mode"), "vertices": rep["vertices"],
                          "triangles": rep["triangles"], "hull": rep["hull"],
                          "iou": round(gi, 4), "static_ac_pass": static_pass,
                          "static_fails": [k for k, v in rep["criteria"].items() if not v["pass"]]},
            "artist": {"vertices": av, "triangles": at, "iou": round(ai, 4),
                       "weighted": weighted, "has_deform": has_deform(award, slot)},
            "iou_margin": round(gi - ai, 4),
            "iou_pass": iou_pass, "piece_pass": piece_pass,
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--parts-dir", default="/tmp/robot_parts",
                    help="psd_slice 切出的件目錄(需含 00_光暈.png/03_身體.png/04_左手.png)")
    ap.add_argument("--margin", type=float, default=0.0)
    ap.add_argument("--budget", type=int, default=128)
    a = ap.parse_args()
    rep = validate(a.award, a.parts_dir, a.margin, a.budget)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
