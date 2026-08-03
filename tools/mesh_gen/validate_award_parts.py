#!/usr/bin/env python3
"""端到端驗收:機器人生產件(Award mesh)→ S3 生成 mesh → 對照真實藝術家 mesh。

STATE.md 下一步候選 #1(最高優先,有真值可比)。用 `robot_parts.psd` 對應的三個
Award mesh 件(光暈 / 左手 / 身體;皆 weighted mesh、無 deform timeline),從 atlas
切出真實 alpha → `generate_auto`(自調 epsilon 到 IoU target)→ 與藝術家 mesh 的
輪廓覆蓋率(artist_iou)及頂點預算對照。

★ 這是**靜態幾何/拓樸維度**的端到端驗收。這三件在 Award 為 **weighted**(靠骨骼權重
變形,無逐頂點 deform timeline),而 S3 目前只產 **unweighted** mesh,故:
  - 「輪廓覆蓋 + 頂點預算」可對真值驗收(本工具);
  - 「權重綁定(BBW)」尚未實作(S3 roadmap),不在此比對。
  - deform 閘對這三件為 N/A(無 deform timeline;真實件靠 rig 變形)。

用法:
  python3 tools/mesh_gen/validate_award_parts.py            # 三件全跑,全過 exit 0
  python3 tools/mesh_gen/validate_award_parts.py --iou 0.98 # 自訂輪廓 IoU target
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from generate_mesh import generate_auto

# 三個 weighted mesh 件(slot == attachment name)
PARTS = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def artist_mesh_iou(skeleton, name, mask):
    """藝術家 mesh 對同一張 mask 的輪廓覆蓋率(用 uvs,適用 weighted/unweighted)。"""
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[name][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    iou = float(np.logical_and(recon, mask).sum() / np.logical_or(recon, mask).sum())
    weighted = len(a["vertices"]) != len(a["uvs"])
    return iou, len(uvs), weighted


def validate_one(sk, name, iou_target, tmp_dir):
    sub = extract("assets/Award.atlas", "assets/Award.png", name)
    crop = os.path.join(tmp_dir, "_award_part.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    base_iou, av, weighted = artist_mesh_iou(sk, name, mask)
    # 頂點預算 = 藝術家頂點數(要求生成不比藝術家更「重」)
    mesh, _ = generate_auto(crop, iou_target=iou_target, vertex_budget=av)
    gv = len(mesh["uvs"]) // 2
    gi = mesh["_iou"]

    iou_pass = gi >= base_iou            # 覆蓋率 >= 藝術家
    budget_pass = gv <= av               # 頂點不超過藝術家
    return {
        "part": name,
        "mask": [int(mask.shape[1]), int(mask.shape[0])],
        "artist": {"verts": av, "iou": round(base_iou, 4), "weighted": weighted},
        "generated": {"verts": gv, "hull": mesh["hull"], "iou": gi,
                      "eps": mesh["_eps"], "iters": mesh["_iter"] + 1},
        "iou_vs_artist_pass": iou_pass,
        "vertex_budget_pass": budget_pass,
        "deform_gate": "N/A (weighted rig, no deform timeline)",
        "pass": iou_pass and budget_pass,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--iou", type=float, default=0.98, help="自調 epsilon 的絕對 IoU target")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open("assets/Award.json"))
    reps = [validate_one(sk, name, a.iou, a.tmp) for name in PARTS]
    allpass = all(r["pass"] for r in reps)
    print(json.dumps({"iou_target": a.iou, "parts": reps, "all_pass": allpass},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
