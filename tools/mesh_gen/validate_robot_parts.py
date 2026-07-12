#!/usr/bin/env python3
"""端到端 S3 驗收:PSD→件→mesh 對照 Award 真實生產 mesh(機器人拆件)。

背景(knowledge/s4-psd-to-spine-real.md):機器人 big win 主角在生產 spine `Award` 中,
會 warp 的件做成 mesh(光暈/身體/左手),剛體件用 region(右手/頭)。這給了 S3 生成器
一組**有真值可比**的真實標的。

與 main_draw 4 mesh 的關鍵差異:**這 3 個 mesh 件在 12 支動畫中皆無 deform timeline**
(靠骨骼驅動,不逐頂點變形)。因此:
  - 真實位移場閘(transfer_deform_check)對它們**不適用(N/A)** —— 沒有位移場可轉移。
  - 改用「靜態拓樸有效性」閘(setup pose 下 0 自交 / 0 翻面 / 0 退化)+ 覆蓋率 IoU。

流程:每件 → atlas 切真實貼圖(0.70 縮小頁,經 CW derotate 校正)→ generate_mesh_v2(auto)
     → ① 覆蓋率 IoU(vs 該件真實 alpha),與藝術家 mesh 自身覆蓋率比較
       ② 生成 mesh 在 setup pose 的靜態拓樸有效性
       ③ 頂點預算 / 格式。

註:atlas 區塊為 0.70 縮小版;藝術家 uvs 為 region-local [0,1](offset=0、orig==size,
    無 trim,已驗),與生成 mesh 同處 atlas-region 像素空間 → 可直接對照。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
import deform_eval as de
from evaluate_mesh import evaluate, load_mask
from atlas_crop import extract
from generate_mesh_v2 import generate as gen_v2

# Award 中做 mesh 的 3 個機器人件(slot == attachment name)
ROBOT_MESH_PARTS = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def artist_iou(skeleton, slot, name, mask):
    """藝術家 mesh 對其來源 alpha 的覆蓋率(uvs region-local)。"""
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0, len(uvs), len(tris)


def static_topology(mesh):
    """setup pose 下生成 mesh 的拓樸有效性(0 自交 / 0 翻面 / 0 退化)。"""
    v = mesh["vertices"]
    s = np.column_stack([v[0::2], v[1::2]])
    t = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    signs = [de.signed_area(s, x) > 0 for x in t]
    r = de.check(s, t, signs)
    r["clean"] = (r["self_intersections"] == 0 and r["triangle_flips"] == 0 and r["degenerate"] == 0)
    return r


def validate_part(sk, atlas, part, tmp_dir, iou_margin, budget):
    sub = extract(atlas, None, part)          # 多頁自動選 page;None → 用 region.page
    crop = os.path.join(tmp_dir, "_robot_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    mesh = gen_v2(crop, mode="auto", adaptive=True, budget=budget)
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    nv = len(mesh["uvs"]) // 2

    gen_iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
    base_iou, art_nv, art_tris = artist_iou(sk, part, part, mask)
    topo = static_topology(mesh)

    iou_pass = gen_iou >= base_iou - iou_margin
    budget_pass = nv <= budget
    part_pass = iou_pass and topo["clean"] and budget_pass
    return {
        "part": part,
        "region_wh": [int(mask.shape[1]), int(mask.shape[0])],
        "gen_mesh": {"mode": mesh.get("_mode"), "eps": mesh.get("_eps"), "vertices": nv,
                     "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3},
        "artist_mesh": {"vertices": art_nv, "triangles": art_tris},
        "AC_coverage_iou": {"gen": round(gen_iou, 4), "artist_baseline": round(base_iou, 4),
                            "margin": iou_margin, "pass": bool(iou_pass)},
        "AC_static_topology": {"self_intersections": topo["self_intersections"],
                               "triangle_flips": topo["triangle_flips"],
                               "degenerate": topo["degenerate"], "pass": bool(topo["clean"])},
        "AC_vertex_budget": {"value": nv, "budget": budget, "pass": bool(budget_pass)},
        "note_deform": "N/A — 此件無 deform timeline(骨骼驅動),不做真實位移場閘",
        "part_pass": bool(part_pass),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--iou-margin", type=float, default=0.03)
    ap.add_argument("--budget", type=int, default=64)
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reports = [validate_part(sk, a.atlas, p, a.tmp, a.iou_margin, a.budget) for p in ROBOT_MESH_PARTS]
    overall = all(r["part_pass"] for r in reports)
    out = {"parts": reports, "overall_pass": overall}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
