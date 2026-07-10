#!/usr/bin/env python3
"""端到端「真實生產件 → S3 mesh → 對照 Award 藝術家真實 mesh」驗收(IoU 覆蓋率)。

背景(STATE.md 最高優先 bounded chunk):
  Award(機器人 big win spine)裡 3 個件是 **mesh**:光暈 / 身體 / 左手。
  這些是 **weighted mesh(骨骼權重蒙皮)**,**無逐頂點 deform timeline**
  → 變形靠 bone 權重,不是 DeformTimeline。因此本驗收的 AC 是
  **靜態 IoU 覆蓋率 vs 藝術家真實 mesh**(幾何端到端對真實生產標的驗收);
  deform-transfer 閘對這些件 **N/A**(無位移場可轉移,不做未校準的合成壓力,避免假性失敗)。

流程(每件):
  atlas 切真實貼圖(多頁 + CW derotate,已校正)→ generate_mesh_v2(auto)
  → ① 生成 mesh IoU(vs 真實 alpha)② 藝術家 mesh IoU(同 mask,baseline)
  → pass = gen_iou >= artist_iou - margin。
  另存 overlay PNG(藝術家 vs 生成三角網 疊 alpha)供視覺存證。

用法:
  python3 tools/mesh_gen/validate_award_mesh.py            # 跑 3 件,印 JSON 報告
  python3 tools/mesh_gen/validate_award_mesh.py --figs DIR # 另存 overlay 圖
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from generate_mesh_v2 import generate as gen_v2

PIECES = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def artist_mesh(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)[slot][name]


def mesh_iou(uvs, tris, mask):
    """把 (region-local 正規化 uvs, 三角) 光柵化到 mask 尺寸,回傳與 mask 的 IoU。"""
    H, W = mask.shape
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0, recon


def draw_overlay(mask, uvs, tris, color):
    H, W = mask.shape
    img = np.zeros((H, W, 3), np.uint8)
    img[mask > 0] = (60, 60, 60)
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H]).astype(np.int32)
    for t in tris:
        cv2.polylines(img, [pts[t]], True, color, 1, cv2.LINE_AA)
    return img


def validate_piece(sk, atlas, png, slot, margin, figs_dir):
    name = slot  # Award: slot == attachment name
    sub = extract(atlas, png, name)
    tmp = "/tmp/_award_region.png"  # 暫存切件供 load_mask/generate 讀取(不污染 repo)
    cv2.imwrite(tmp, sub)
    mask = load_mask(tmp)

    # 生成 mesh
    gm = gen_v2(tmp, mode="auto")
    g_uvs = np.array(gm["uvs"]).reshape(-1, 2)
    g_tris = np.array(gm["triangles"]).reshape(-1, 3)
    g_iou, g_recon = mesh_iou(g_uvs, g_tris, mask)

    # 藝術家 mesh
    a = artist_mesh(sk, slot, name)
    a_uvs = np.array(a["uvs"]).reshape(-1, 2)
    a_tris = np.array(a["triangles"]).reshape(-1, 3)
    a_iou, _ = mesh_iou(a_uvs, a_tris, mask)

    if figs_dir:
        os.makedirs(figs_dir, exist_ok=True)
        tag = slot.split("/")[-1]
        cv2.imwrite(os.path.join(figs_dir, f"award_{tag}_artist.png"),
                    draw_overlay(mask, a_uvs, a_tris, (80, 200, 255)))
        cv2.imwrite(os.path.join(figs_dir, f"award_{tag}_gen.png"),
                    draw_overlay(mask, g_uvs, g_tris, (120, 255, 120)))

    return {
        "piece": slot,
        "region": {"w": mask.shape[1], "h": mask.shape[0]},
        "generated": {"mode": gm.get("_mode"), "vertices": len(g_uvs),
                      "hull": gm["hull"], "triangles": len(g_tris), "iou": round(g_iou, 4)},
        "artist": {"vertices": len(a_uvs), "hull": a.get("hull"),
                   "triangles": len(a_tris), "iou": round(a_iou, 4), "weighted": True},
        "iou_gap": round(g_iou - a_iou, 4),
        "deform_gate": "N/A (weighted mesh, no per-vertex deform timeline)",
        "pass": g_iou >= a_iou - margin,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--margin", type=float, default=0.02)
    ap.add_argument("--figs", default=None)
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reps = [validate_piece(sk, a.atlas, a.png, p, a.margin, a.figs) for p in PIECES]
    overall = all(r["pass"] for r in reps)
    print(json.dumps({"pieces": reps, "overall_pass": overall}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
