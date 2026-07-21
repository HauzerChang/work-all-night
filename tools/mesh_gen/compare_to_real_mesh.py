#!/usr/bin/env python3
"""端到端對照:件 PNG → S3 生成 mesh → 對照生產 spine 的真實 mesh(靜態公平閘)。

用於「PSD→件→mesh」對真實生產標的的驗收。與 validate_against_real.py 不同處:
- validate_against_real 針對 **unweighted + 有 deform timeline** 的件(main_draw 窗簾/陰影),
  用真實位移場轉移做 deform 閘。
- 本工具針對 **可能為 weighted / 骨骼驅動、無 deform timeline** 的件(Award 機器人拆件)。
  對這類件,curtain 位移場轉移是**跨域不適用**(連 weighted 藝術家 mesh 都無法套用該閘,
  且把窗簾垂直大拉伸套到手部並不代表其生產變形)。故公平閘 = 靜態覆蓋率 IoU + 頂點預算 + 拓樸有效。

自動判定真實 mesh 是否 weighted(vertices 長度 != 2*頂點數)與是否有 deform timeline,
據此標示 deform 閘是否適用,避免再犯「跨域評估器」誤判(第 4 次評估器校準教訓)。
"""
import argparse, json, sys, os
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from evaluate_mesh import evaluate, load_mask


def get_attachment(skeleton, slot, name=None):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    d = skin.get("attachments", skin)[slot]
    if name and name in d:
        return name, d[name]
    k = next(iter(d))
    return k, d[k]


def is_weighted(att):
    return len(att["vertices"]) != 2 * (len(att["uvs"]) // 2)


def has_deform_timeline(skeleton, slot):
    for _, ad in skeleton.get("animations", {}).items():
        for _, slots in ad.get("deform", {}).items():
            if slot in slots:
                return True
    return False


def coverage_iou(uvs, triangles, mask):
    """以 uvs*W,H 填三角形算對遮罩的 IoU(適用 weighted / unweighted)。"""
    uvs = np.array(uvs).reshape(-1, 2)
    tris = np.array(triangles).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0


def compare(skeleton_path, piece_png, slot, name, gen="v2", iou_margin=0.01):
    sk = json.load(open(skeleton_path))
    rn, ra = get_attachment(sk, slot, name)
    mask = load_mask(piece_png)

    if gen == "v1":
        from generate_mesh import generate as g
        mesh = g(piece_png)
        mesh = mesh[0] if isinstance(mesh, tuple) else mesh
    else:
        from generate_mesh_v2 import generate as g
        mesh = g(piece_png, mode="auto")

    real_nv = len(ra["uvs"]) // 2
    ev = evaluate(mesh, mask, vertex_budget=real_nv)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]
    base_iou = coverage_iou(ra["uvs"], ra["triangles"], mask)
    gen_nv = len(mesh["uvs"]) // 2

    weighted = is_weighted(ra)
    deform = has_deform_timeline(sk, slot)
    deform_gate_applies = (not weighted) and deform

    iou_pass = gen_iou >= base_iou - iou_margin
    budget_pass = gen_nv <= real_nv
    fmt_pass = ev["criteria"]["AC4_format"]["pass"]
    return {
        "slot": slot, "real_attachment": rn,
        "real": {"verts": real_nv, "tris": len(ra["triangles"]) // 3, "hull": ra.get("hull"),
                 "weighted": weighted, "has_deform_timeline": deform,
                 "iou_baseline": round(base_iou, 4)},
        "gen": {"mode": mesh.get("_mode"), "verts": gen_nv, "tris": len(mesh["triangles"]) // 3,
                "hull": mesh["hull"], "iou": round(gen_iou, 4)},
        "deform_gate_applies": deform_gate_applies,
        "gate": {"iou_pass": iou_pass, "budget_pass": budget_pass, "format_pass": fmt_pass},
        "static_pass": iou_pass and budget_pass and fmt_pass,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--piece", required=True, help="切件 PNG(含 alpha)")
    ap.add_argument("--slot", required=True)
    ap.add_argument("--name", default=None)
    ap.add_argument("--gen", choices=["v1", "v2"], default="v2")
    a = ap.parse_args()
    rep = compare(a.skeleton, a.piece, a.slot, a.name, a.gen)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["static_pass"] else 1)


if __name__ == "__main__":
    main()
