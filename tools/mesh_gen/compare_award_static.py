#!/usr/bin/env python3
"""端到端靜態驗收:atlas 切件 → S3 generate_mesh_v2 → 對照 Award 真實(weighted)mesh。

背景(2026-07-11 發現):Award 生產 mesh 全為 **weighted**(vertices 為
`[boneCount, boneIdx,bindX,bindY,weight, ...]` 變長格式,len != 2*nv),
與 main_draw 的 4 個 unweighted mesh 不同。因此 deform_eval 的 real_deform_field /
transfer_deform_check(假設 unweighted vertices)在 Award 上會 crash。

但**靜態覆蓋率比對只用 `uvs`+`triangles`,與加權無關**,故仍可做:
  ① 藝術家 mesh 覆蓋率(uvs 光柵化 vs 切件 alpha) — 建立可信真值 / 對齊確認。
  ② 生成 mesh 覆蓋率(generate_mesh_v2 vs 切件 alpha)。
  ③ 生成是否達到藝術家基準(iou_gen >= iou_artist - margin)。

deform 比對(weighted)需 setup-pose 骨架世界變換求解器,列為後續 chunk。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate
from generate_mesh_v2 import generate as gen_v2


def is_weighted(att):
    return len(att["vertices"]) != len(att["uvs"])


def artist_coverage(att, mask):
    """用 uvs+triangles 光柵化藝術家 mesh(與加權無關),回傳 (iou, recon)。"""
    uvs = np.array(att["uvs"]).reshape(-1, 2)
    tris = np.array(att["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return (float(inter / union) if union else 0.0), recon


def run(skeleton_path, atlas_path, png_path, slot, name, tmp_dir, iou_margin=0.0):
    sk = json.load(open(skeleton_path))
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)[slot][name]

    sub = extract(atlas_path, png_path, name)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = (cv2.imread(crop, cv2.IMREAD_UNCHANGED)[:, :, 3] > 8).astype(np.uint8)

    iou_artist, _ = artist_coverage(att, mask)

    mesh = gen_v2(crop, mode="auto")
    ev = evaluate(mesh, mask, vertex_budget=64)
    iou_gen = ev["criteria"]["AC1_iou"]["value"]

    return {
        "part": name,
        "weighted": is_weighted(att),
        "artist_mesh": {"vertices": len(att["uvs"]) // 2, "hull": att["hull"],
                        "triangles": len(att["triangles"]) // 3},
        "gen_mesh": {"vertices": mesh["vertices"] and len(mesh["uvs"]) // 2,
                     "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3,
                     "mode": mesh.get("_mode")},
        "iou_artist_baseline": round(iou_artist, 4),
        "iou_generated": round(iou_gen, 4),
        "coverage_pass": iou_gen >= iou_artist - iou_margin,
        "gen_geometry_ok": ev["criteria"]["AC2b_degenerate"]["pass"] and
                           ev["criteria"]["AC2c_orphans"]["pass"] and
                           ev["criteria"]["AC4_format"]["pass"],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--parts", nargs="+",
                    default=["機器人拆件/身體", "機器人拆件/左手", "機器人拆件/光暈"])
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    reps = []
    for p in a.parts:
        reps.append(run(a.skeleton, a.atlas, a.png, p, p, a.tmp, a.margin))
    allpass = all(r["coverage_pass"] and r["gen_geometry_ok"] for r in reps)
    print(json.dumps({"parts": reps, "all_pass": allpass}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
