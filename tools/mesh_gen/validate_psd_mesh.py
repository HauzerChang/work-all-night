#!/usr/bin/env python3
"""端到端「PSD 件 → S3 mesh」對真實生產 spine mesh 驗收。

背景:`robot_parts.psd` 的 3 個件(光暈/身體/左手)在真實 spine(Award.json)中是 **weighted mesh**
(骨骼驅動、無 deform timeline),不同於 main_draw 的 unweighted + deform-timeline mesh。
故此處的**可信閘 = 靜態覆蓋率(IoU)對照藝術家真實 mesh**,而非 deform 轉移。

流程(每件):
  psd_slice 產出的件 PNG(region-local、正立、邏輯解析度)
    → generate_mesh_v2 生成 mesh(unweighted)
    → ① 生成 mesh 對件 alpha mask 的 IoU
    → ② 藝術家真實 mesh(Award 同 slot,uvs 已證實為 region-local)對同一 mask 的 IoU(baseline)
    → pass = 生成 IoU >= 藝術家 baseline - margin;另報頂點數對照。

驗證前提(本工具建立時已量化確認):
  - Award mesh uvs 為 **region-local [0,1]**(光暈 u 跨 0.012–0.99;若為 atlas-global 僅 ~0.24)。
  - PSD 件 mask 與 Award mesh uv 同框、**無 v 翻轉**(flipv=False 時 artist IoU 0.95/0.95/0.98,翻轉則掉到 0.4–0.6)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from evaluate_mesh import evaluate, load_mask


def artist_mesh(skeleton, slot, name=None):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    name = name or slot
    a = att[slot][name]
    return np.array(a["uvs"]).reshape(-1, 2), np.array(a["triangles"]).reshape(-1, 3), a


def poly_iou(uvs, tris, mask):
    """uvs 為 region-local [0,1];填三角形重建 mask 後對真值 alpha mask 算 IoU。"""
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0


def validate_piece(piece_png, skeleton, slot, gen_fn, margin=0.02):
    mask = load_mask(piece_png)
    H, W = mask.shape

    mesh = gen_fn(piece_png)
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    guv = np.array(mesh["uvs"]).reshape(-1, 2)
    gtris = np.array(mesh["triangles"]).reshape(-1, 3)
    gen_iou = poly_iou(guv, gtris, mask)

    auv, atris, a = artist_mesh(skeleton, slot)
    base_iou = poly_iou(auv, atris, mask)

    ev = evaluate(mesh, mask)["criteria"]
    clean = (ev["AC2b_degenerate"]["value"] == 0 and ev["AC2c_orphans"]["value"] == 0
             and ev["AC2a_centroid_in_mask"]["pass"])

    return {
        "slot": slot,
        "mask_size": [W, H],
        "generated": {"vertices": len(guv), "hull": mesh["hull"],
                      "triangles": len(gtris), "mode": mesh.get("_mode"),
                      "iou": round(gen_iou, 4), "clean": clean},
        "artist_truth": {"vertices": len(auv), "hull": int(a.get("hull", 0)),
                         "triangles": len(atris), "weighted": len(a["vertices"]) != len(a["uvs"]),
                         "iou": round(base_iou, 4)},
        "iou_gap": round(gen_iou - base_iou, 4),
        "pass": gen_iou >= base_iou - margin and clean,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--pieces_dir", default="/tmp/robot_pieces")
    ap.add_argument("--gen", choices=["v1", "v2"], default="v2")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()

    if a.gen == "v1":
        from generate_mesh import generate as g
        gen = lambda p: g(p)
    else:
        from generate_mesh_v2 import generate as g
        gen = lambda p: g(p, mode="auto")

    sk = json.load(open(a.skeleton))
    # (件檔名, Award slot)
    pieces = [
        ("00_光暈.png", "機器人拆件/光暈"),
        ("03_身體.png", "機器人拆件/身體"),
        ("04_左手.png", "機器人拆件/左手"),
    ]
    reports = []
    for fn, slot in pieces:
        p = os.path.join(a.pieces_dir, fn)
        if not os.path.exists(p):
            print(f"skip {p} (missing)", file=sys.stderr)
            continue
        reports.append(validate_piece(p, sk, slot, gen, a.margin))

    overall = all(r["pass"] for r in reports) and len(reports) == 3
    print(json.dumps({"pieces": reports, "overall_pass": overall,
                      "margin": a.margin, "gen": a.gen}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
