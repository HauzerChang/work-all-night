#!/usr/bin/env python3
"""端到端驗收:PSD 切件 → S3 generate_mesh_v2 → 對照 Award 真實生產 mesh。

背景(knowledge/s4-psd-to-spine-real.md):Award 的機器人拆件中,光暈/身體/左手 為 mesh。
這 3 件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform),故真實位移場閘
(transfer_deform_check)不適用 —— 這裡的 AC 是「靜態覆蓋率對齊藝術家 + mesh 良構」。

流程(每件):
  1. 讀 PSD 切件 PNG → 區域局部、正立、原始解析度 alpha mask。
  2. generate_mesh_v2(auto)→ 生成 mesh(auto 依長寬比/row-convex 決定 strip / v1)。
  3. evaluate → 生成 mesh 對 mask 的 IoU + 良構(退化/孤兒/格式)。
  4. artist_iou → 把 Award 真實 mesh 的 uvs(區域局部 0..1)描到同一張 mask 算覆蓋率(基準)。
  5. rest-pose self-intersection/flip 檢查(deform_eval.check),確認生成 mesh 本身不自交。
  6. 判定:生成 IoU >= 藝術家基準 - margin,且生成 mesh 良構且 0 自交。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask
import deform_eval as de


def artist_iou(award_mesh, mask):
    uvs = np.array(award_mesh["uvs"]).reshape(-1, 2)
    tris = np.array(award_mesh["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0


def rest_self_int(mesh):
    """rest-pose(setup 座標)自交/翻面/退化(生成 mesh 本身良構性)。"""
    verts = np.array(mesh["vertices"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(mesh["triangles"]).reshape(-1, 3)
    # check() 以布林(area>0)比對;seed 用同一組頂點 → 良構時 flips 必為 0,
    # 真正有意義的是 self_intersections(非相鄰邊交叉)。
    setup_signs = [de.signed_area(verts, t) > 0 for t in tris]
    return de.check(verts, tris, setup_signs)


def get_award_mesh(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[slot][name]


def compare(png_path, award_json, slot, name, iou_margin=0.03):
    mask = load_mask(png_path)
    mesh = gen_v2(png_path, mode="auto")
    ev = evaluate(mesh, mask)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]

    sk = json.load(open(award_json))
    am = get_award_mesh(sk, slot, name)
    base = artist_iou(am, mask)

    rs = rest_self_int(mesh)
    wellformed = (ev["criteria"]["AC2b_degenerate"]["pass"]
                  and ev["criteria"]["AC2c_orphans"]["pass"]
                  and ev["criteria"]["AC4_format"]["pass"])
    clean_rest = (rs["self_intersections"] == 0 and rs["triangle_flips"] == 0
                  and rs["degenerate"] == 0)

    iou_pass = gen_iou >= base - iou_margin
    return {
        "piece": name,
        "gen": {"mode": mesh.get("_mode"), "vertices": len(mesh["uvs"]) // 2,
                "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3},
        "award_real": {"vertices": len(am["uvs"]) // 2, "hull": am["hull"],
                       "triangles": len(am["triangles"]) // 3},
        "AC_iou": {"gen": round(gen_iou, 4), "artist_baseline": round(base, 4),
                   "margin": iou_margin, "pass": iou_pass},
        "AC_wellformed": {"pass": wellformed,
                          "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                          "orphans": ev["criteria"]["AC2c_orphans"]["value"]},
        "AC_rest_clean": {"pass": clean_rest,
                          "self_intersections": rs["self_intersections"],
                          "triangle_flips": rs["triangle_flips"]},
        "overall_pass": iou_pass and wellformed and clean_rest,
    }


PIECES = [
    ("00_光暈.png", "機器人拆件/光暈", "機器人拆件/光暈"),
    ("03_身體.png", "機器人拆件/身體", "機器人拆件/身體"),
    ("04_左手.png", "機器人拆件/左手", "機器人拆件/左手"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts-dir", required=True, help="psd_slice 輸出目錄")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--margin", type=float, default=0.03)
    a = ap.parse_args()
    reps = []
    for fn, slot, name in PIECES:
        p = os.path.join(a.parts_dir, fn)
        reps.append(compare(p, a.award, slot, name, a.margin))
    out = {"pieces": reps, "all_pass": all(r["overall_pass"] for r in reps)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["all_pass"] else 1)


if __name__ == "__main__":
    main()
