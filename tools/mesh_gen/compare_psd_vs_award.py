#!/usr/bin/env python3
"""端到端閘:PSD 件 → S3 mesh → 對照 Award 真實(藝術家)mesh。

STATE.md 最高優先 bounded chunk:用 robot_parts.psd 的三個 mesh 件(光暈/身體/左手,
在生產 spine Award 中為 mesh)跑 generate_mesh_v2,與 Award 藝術家 mesh 做同基準比較,
完成「PSD→件→mesh」對真實生產標的的端到端驗收。純 CPU、可自驅。

★ 關鍵座標發現(2026-08-11 本次)
  Award.json 的 mesh `uvs` 是 **region-local 正規化**(0..1 覆蓋該件),非 atlas-page 正規化,
  y 與影像同向(top-down,不需翻轉)。→ 藝術家 mesh 可**直接**用 PSD 切件 alpha 當共同基準:
    px = (u*partW, v*partH) → 填三角 → 對 part alpha 取 coverage-IoU。
  這讓「藝術家 mesh」與「生成 mesh」在**同一份 alpha、同一種 IoU 定義**下比較(真 apples-to-apples)。
  經驗證(flip=False):光暈 0.949 / 左手 0.977 / 身體 0.948;flip=True 皆 <0.61(方向確認)。

★ deform 閘不適用
  這 3 件在 Award **無 deform timeline**,且為 **weighted mesh**(骨骼/權重變形,非逐頂點 deform),
  故 `real_deform_field` 無真實位移場可轉移 → 本閘只做靜態覆蓋保真 + 網格有效性,不下 deform 判定。
  (對照:main_draw 4 件為 unweighted + 有 deform,由 validate_against_real 跑真實 deform 閘。)

AC(逐件):
  AC_valid   evaluate_mesh 格式(AC4)+ 0 退化(AC2b)+ 0 孤兒(AC2c)全過
  AC_iou     gen_IoU >= artist_IoU - margin(生成 mesh 覆蓋保真不輸藝術家)
  AC_budget  生成頂點數 <= 頂點預算(預設 64;並報告 vs 藝術家頂點數)
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from evaluate_mesh import evaluate as eval_mesh, load_mask as load_alpha
from generate_mesh_v2 import generate as gen_v2

# robot_parts.psd 三個 mesh 件 → Award slot/attachment 名(見 knowledge/s4-psd-to-spine-real.md)
DEFAULT_PARTS = [
    {"file": "00_光暈.png", "award": "機器人拆件/光暈"},
    {"file": "03_身體.png", "award": "機器人拆件/身體"},
    {"file": "04_左手.png", "award": "機器人拆件/左手"},
]


def award_attachments(award_json):
    sk = json.load(open(award_json))
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)


def coverage_iou_from_uvs(uvs, tris, alpha):
    """region-local uvs(0..1)→ part 像素座標 → 填三角 → 對 part alpha 取 IoU。"""
    H, W = alpha.shape
    px = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(px[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, alpha).sum())
    union = int(np.logical_or(recon, alpha).sum())
    return (inter / union) if union else 0.0


def artist_stats(att, name, alpha):
    a = att[name][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    weighted = len(a["vertices"]) != len(a["uvs"])  # weighted:vertices 為變長 bind 格式
    return {
        "vertices": len(uvs), "triangles": len(tris), "hull": a.get("hull"),
        "weighted": weighted, "wh": [a.get("width"), a.get("height")],
        "iou": round(coverage_iou_from_uvs(uvs, tris, alpha), 4),
    }


def compare_one(part_png, att, award_name, budget, margin):
    alpha = load_alpha(part_png)          # (H,W) 0/1
    art = artist_stats(att, award_name, alpha)

    mesh = gen_v2(part_png, mode="auto")
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    ev = eval_mesh(mesh, alpha, vertex_budget=budget)
    nv = ev["vertices"]
    gen_iou = ev["criteria"]["AC1_iou"]["value"]

    valid = (ev["criteria"]["AC4_format"]["pass"]
             and ev["criteria"]["AC2b_degenerate"]["pass"]
             and ev["criteria"]["AC2c_orphans"]["pass"])
    iou_pass = gen_iou >= art["iou"] - margin
    budget_pass = nv <= budget

    return {
        "part": os.path.basename(part_png), "award": award_name,
        "generated": {"vertices": nv, "triangles": ev["triangles"], "hull": mesh["hull"],
                      "mode": mesh.get("_mode"), "iou": gen_iou},
        "artist": art,
        "AC_valid": {"pass": valid,
                     "format": ev["criteria"]["AC4_format"]["pass"],
                     "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                     "orphans": ev["criteria"]["AC2c_orphans"]["value"]},
        "AC_iou": {"pass": iou_pass, "gen": gen_iou, "artist_baseline": art["iou"],
                   "margin": margin, "delta": round(gen_iou - art["iou"], 4)},
        "AC_budget": {"pass": budget_pass, "gen_verts": nv, "budget": budget,
                      "artist_verts": art["vertices"]},
        "overall_pass": valid and iou_pass and budget_pass,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts-dir", default="/tmp/robot_parts")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--budget", type=int, default=64)
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    att = award_attachments(a.award)
    reports = [compare_one(os.path.join(a.parts_dir, p["file"]), att, p["award"],
                           a.budget, a.margin) for p in DEFAULT_PARTS]
    overall = all(r["overall_pass"] for r in reports)
    print(json.dumps({"overall_pass": overall, "parts": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
