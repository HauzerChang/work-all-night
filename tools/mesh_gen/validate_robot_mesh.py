#!/usr/bin/env python3
"""S3+S4 端到端:PSD 切件 → S3 生成 mesh → 對照 Award 真實 mesh(ground truth)。

STATE.md 最高優先 chunk:用 robot_parts.psd 的 mesh 件(光暈/身體/左手,在 Award 中為 mesh)
跑 generate_mesh_v2,與 Award 真實 mesh 做 IoU 對照 → 對真實生產標的驗收「PSD→件→mesh」。

與 validate_against_real.py 的差異:
  - 資產來源是 **PSD 切件**(logical 尺寸、乾淨 alpha),不是 atlas 切件。
  - ground truth 是 **Award 的 weighted mesh**(uvs 為 region-local 0..1),
    對照 baseline = artist mesh 三角覆蓋率(uvs×件尺寸 光柵化 vs 件 alpha)。
  - **無 deform timeline**:Award 這 5 件靠骨骼/權重變形,非逐頂點 deform
    → 真實位移場不存在,故本閘只做靜態 IoU 對照(誠實標註 deform 不可測)。

用法:python3 tools/mesh_gen/validate_robot_mesh.py
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from evaluate_mesh import evaluate, load_mask
from generate_mesh_v2 import generate as gen_v2


# Award 中為 mesh 的 3 件 ⇄ robot_parts.psd 切件檔名
MESH_PIECES = [
    ("機器人拆件/光暈", "00_光暈.png"),
    ("機器人拆件/身體", "03_身體.png"),
    ("機器人拆件/左手", "04_左手.png"),
]


def award_mesh(sk, slot):
    skins = sk["skins"]
    skin = skins[0] if isinstance(skins, list) else skins
    att = skin.get("attachments", skin)
    return att[slot][slot]


def artist_iou_from_uvs(uvs_flat, tris_flat, mask):
    """artist mesh 三角覆蓋率:region-local uvs×(件W,H) 光柵化 vs 件 alpha。"""
    uvs = np.array(uvs_flat).reshape(-1, 2)
    tris = np.array(tris_flat).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0


def run(psd_parts_dir, award_path, iou_margin=0.02):
    sk = json.load(open(award_path))
    rows = []
    for slot, fn in MESH_PIECES:
        piece = os.path.join(psd_parts_dir, fn)
        mask = load_mask(piece)  # 件 alpha (H,W) uint8 0/1

        mesh = gen_v2(piece, mode="auto")
        nv = len(mesh["uvs"]) // 2
        our_iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]

        a = award_mesh(sk, slot)
        base = artist_iou_from_uvs(a["uvs"], a["triangles"], mask)
        a_nv = len(a["uvs"]) // 2

        rows.append({
            "slot": slot,
            "piece_size": [int(mask.shape[1]), int(mask.shape[0])],
            "award_logical": [a["width"], a["height"]],
            "our_mesh": {"verts": nv, "hull": mesh["hull"],
                         "tris": len(mesh["triangles"]) // 3, "mode": mesh.get("_mode")},
            "artist_mesh": {"verts": a_nv, "hull": a["hull"],
                            "tris": len(a["triangles"]) // 3, "weighted": True},
            "our_iou": round(our_iou, 4),
            "artist_iou": round(base, 4),
            "iou_pass": our_iou >= base - iou_margin,
        })
    overall = all(r["iou_pass"] for r in rows)
    return {"overall_pass": overall, "iou_margin": iou_margin,
            "deform_gate": "N/A (Award 這些件無 deform timeline;靠骨骼權重變形)",
            "pieces": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts", default="/tmp/robot_parts")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    rep = run(a.parts, a.award, a.margin)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
