#!/usr/bin/env python3
"""端到端 S4→S3 對真實生產標的驗收:PSD 件 → generate_mesh_v2 → 對照 Award 真實藝術家 mesh。

背景(見 knowledge/s4-psd-to-spine-real.md):`robot_parts.psd` 的 5 個圖層在生產 spine
`Award` 中對應 slot `機器人拆件/<圖層名>`;其中 **光暈 / 身體 / 左手 3 件是 mesh**
(且為 weighted — 靠骨骼權重變形,**無 deform timeline**),右手 / 頭是 region。

本閘做「覆蓋率」對照(deform 閘不適用,因這些件無逐頂點 deform):
  PSD 切件 alpha(native,乾淨) → generate_mesh_v2 → 生成 mesh 填滿 IoU
  vs Award 藝術家 mesh 在同一遮罩上的覆蓋 IoU。
  PASS ⇔ 生成 IoU ≥ 藝術家基準 − margin(對齊 AC.md AC1:對齊藝術家而非武斷 0.95),
        且 evaluate_mesh 靜態有效性(無退化/孤兒/重心在內/Spine 格式)全過。

⚠️ 遮罩用 PSD 切件(native 上直、無 atlas 0.70 縮放與旋轉還原插值);
   Award 藝術家 uvs 為 region-local 0..1(已驗:光暈 0.01–0.99 等),width/height 為原始邏輯尺寸,
   與 PSD 上直件同向 → uvs×(W,H) 直接落在 PSD 遮罩上(以 artist_iou 對齊度自證)。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from evaluate_mesh import evaluate, load_mask
from psd_slice import slice_psd


# robot_parts.psd 圖層 → Award slot/attachment(見 knowledge 表);只取 mesh 件
MESH_PIECES = {
    "光暈": "機器人拆件/光暈",
    "身體": "機器人拆件/身體",
    "左手": "機器人拆件/左手",
}


def artist_mesh(skeleton, slot):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)[slot]
    name = list(att.keys())[0]
    return att[name]


def mesh_iou(uvs, tris, mask):
    """任意 mesh(藝術家或生成)在遮罩上的填滿 IoU;uvs=region-local 0..1。"""
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0


def validate(psd_path, skeleton_path, tmp_dir, iou_margin=0.02, vertex_budget=110):
    from generate_mesh_v2 import generate as gen
    sk = json.load(open(skeleton_path))
    _, _, parts = slice_psd(psd_path)
    by_name = {e["name"]: im for e, im in parts}
    os.makedirs(tmp_dir, exist_ok=True)

    out = {"pieces": {}, "overall_pass": True}
    for layer, slot in MESH_PIECES.items():
        im = by_name[layer]
        crop = os.path.join(tmp_dir, f"_piece_{layer}.png")
        im.save(crop)
        mask = load_mask(crop)  # evaluate_mesh.load_mask → boolean mask (H,W)

        # 藝術家 mesh
        a = artist_mesh(sk, slot)
        a_uvs = np.array(a["uvs"]).reshape(-1, 2)
        a_tris = np.array(a["triangles"]).reshape(-1, 3)
        a_iou = mesh_iou(a_uvs, a_tris, mask)
        a_nv = len(a_uvs)

        # 生成 mesh
        m = gen(crop, mode="auto")
        if isinstance(m, tuple):
            m = m[0]
        g_nv = len(m["uvs"]) // 2
        ev = evaluate(m, mask, vertex_budget=vertex_budget)
        g_iou = ev["criteria"]["AC1_iou"]["value"]

        # 有效性(排除 AC1 的武斷門檻,改用對齊藝術家判定)
        valid_keys = ["AC2a_centroid_in_mask", "AC2b_degenerate",
                      "AC2c_orphans", "AC4_format"]
        validity = {k: ev["criteria"][k]["pass"] for k in valid_keys if k in ev["criteria"]}
        valid_ok = all(validity.values())

        iou_ok = g_iou >= a_iou - iou_margin
        budget_ok = g_nv <= vertex_budget
        piece_pass = iou_ok and valid_ok and budget_ok
        out["overall_pass"] = out["overall_pass"] and piece_pass

        out["pieces"][layer] = {
            "slot": slot,
            "mask_size": [int(mask.shape[1]), int(mask.shape[0])],
            "gen_mode": m.get("_mode"),
            "gen_vertices": g_nv, "gen_hull": m["hull"],
            "gen_triangles": len(m["triangles"]) // 3,
            "artist_vertices": a_nv, "artist_weighted": len(a["vertices"]) != len(a["uvs"]),
            "artist_hull": a.get("hull"),
            "gen_iou": round(g_iou, 4), "artist_iou": round(a_iou, 4),
            "iou_delta": round(g_iou - a_iou, 4),
            "iou_pass": iou_ok, "validity": validity, "valid_pass": valid_ok,
            "budget_pass": budget_ok, "piece_pass": piece_pass,
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--tmp", default="/tmp/award_val")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    rep = validate(a.psd, a.skeleton, a.tmp, iou_margin=a.margin)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
