#!/usr/bin/env python3
"""端到端「PSD→件→S3 mesh」對照真實生產標的 (Award 機器人拆件)。

與 validate_against_real.py 的差異(關鍵發現,2026-07-20):
  Award 的 3 個機器人 mesh 件(光暈/身體/左手)是 **weighted mesh + 純骨骼驅動**,
  **沒有任何 deform timeline**(main_draw 窗簾則是 unweighted + deform)。
  → S3 的 deform-transfer 閘(讀 deform 位移場)對這些件**不適用**;
    這裡只做「靜態輪廓/覆蓋率」軸的對照(generated vs 真實 alpha vs 藝術家 mesh 覆蓋)。
  weighted 件的「耐變形」正確性屬 S3 尚未建的 **BBW 權重生成** 範疇(見結論)。

流程:atlas 切真實貼圖(region-local)→ 生成 mesh(v2 auto)→
  ① IoU(generated vs 真實 alpha)② artist IoU(藝術家 mesh 覆蓋 vs 真實 alpha)
  ③ 藝術家 mesh 統計(頂點/三角/hull/weighted)供對照。
"""
import argparse, json, sys, os
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from evaluate_mesh import evaluate, load_mask
from atlas_crop import extract


def artist_iou(skeleton, slot, name, mask):
    """藝術家 mesh 的 region-local uvs 映到裁出的 mask,量覆蓋 IoU。"""
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    a = att[slot][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    iou = float(np.logical_and(recon, mask).sum() / max(np.logical_or(recon, mask).sum(), 1))
    weighted = len(a["vertices"]) != len(a["uvs"])
    return iou, {"vertices": len(uvs), "triangles": len(tris),
                 "hull": a["hull"], "weighted": weighted}


def validate(skeleton_path, atlas_path, png_path, slot, name, tmp_dir):
    from generate_mesh_v2 import generate as g
    sk = json.load(open(skeleton_path))
    sub = extract(atlas_path, png_path, name)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    mesh = g(crop, mode="auto")
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    nv = len(mesh["uvs"]) // 2

    gen_iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
    a_iou, a_stat = artist_iou(sk, slot, name, mask)

    return {
        "slot": slot,
        "region_px": {"w": int(sub.shape[1]), "h": int(sub.shape[0])},
        "generated": {"vertices": nv, "hull": mesh["hull"],
                      "triangles": len(mesh["triangles"]) // 3,
                      "mode": mesh.get("_mode")},
        "artist": a_stat,
        "AC_static_iou": {
            "generated_vs_alpha": round(gen_iou, 4),
            "artist_vs_alpha": round(a_iou, 4),
            "pass": gen_iou >= a_iou - 0.02,   # 對齊藝術家覆蓋率(容差 2pt)
        },
        "deform_gate": "N/A — weighted, bone-driven, no deform timeline",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--slots", nargs="*",
                    default=["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"])
    a = ap.parse_args()
    reports = []
    for slot in a.slots:
        rep = validate(a.skeleton, a.atlas, a.png, slot, slot, a.tmp)
        reports.append(rep)
    out = {"reports": reports,
           "all_static_pass": all(r["AC_static_iou"]["pass"] for r in reports)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["all_static_pass"] else 1)


if __name__ == "__main__":
    main()
