#!/usr/bin/env python3
"""端到端 AC:PSD 件 → S3 mesh → 對照 Award 真實生產 mesh。

這是「PSD→件→mesh」對真實標的(不是合成 fixture、不是自家生成的真值)的驗收。
機器人拆件 PSD 的三件在生產 spine `Award` 中被美術做成 mesh(光暈/身體/左手),
是難得的**外部藝術家真值**。本工具:

  robot_parts.psd → psd_slice 切件(全解析度、原始朝向) → generate_mesh_v2(auto)
    → ① 靜態覆蓋 IoU / 格式 / 拓樸 / 頂點預算(evaluate_mesh)
    → ② 對照 Award 同件真實 mesh 的覆蓋率(artist baseline)與複雜度(頂點數)

座標系對齊(2026-07-23 校驗):Award 這三件的 mesh `uvs` **是 region 局部 0..1、v 由頂部量**
(先前 log 假設「uvs 為 atlas 頁 UV」有誤)。渲染 artist mesh 到 PSD 件 alpha:
v-top IoU 0.95~0.98、v-flip 0.43~0.60 → 確認 v-top region-local,與生成器 uv 慣例一致。

deform 閘不適用:這五件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform),
故不跑 transfer_deform_check;變形穩健性在 main_draw 四窗簾/陰影 mesh 已另行驗過。

AC:
  - COVERAGE:gen_iou >= artist_iou - margin(預設 margin=0.03)。
  - PARSIMONY:gen 頂點數 <= artist 頂點數(不比藝術家更複雜就達到同覆蓋)。
  - TOPOLOGY:format 合法 / 0 孤兒 / 0 退化 / 重心 100% 在 mask。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask

# Award「機器人拆件」中被做成 mesh 的三件 → robot_parts.psd 切件檔名
MESH_PIECES = {
    "光暈": "00_光暈.png",
    "身體": "03_身體.png",
    "左手": "04_左手.png",
}


def load_skin_attachments(skeleton_path):
    sk = json.load(open(skeleton_path))
    skins = sk["skins"]
    skin = skins[0] if isinstance(skins, list) else skins
    return skin.get("attachments", skin)


def artist_mesh(att, name):
    """Award 真實 mesh attachment(slot==name=='機器人拆件/<件>')。"""
    full = "機器人拆件/" + name
    return att[full][full]


def artist_coverage(a, mask):
    """把 Award 真實 mesh 三角形填到 PSD 件 alpha 上算覆蓋 IoU(region-local, v-top)。"""
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    iou = float(np.logical_and(recon, m).sum() / max(int(np.logical_or(recon, m).sum()), 1))
    return iou, len(uvs), len(tris), int(a["hull"])


def compare_piece(name, piece_png, att, margin, budget):
    mask = load_mask(piece_png)
    mesh = gen_v2(piece_png, mode="auto")
    ev = evaluate(mesh, mask, vertex_budget=budget)
    c = ev["criteria"]
    gen_iou = c["AC1_iou"]["value"]

    a = artist_mesh(att, name)
    a_iou, a_v, a_t, a_hull = artist_coverage(a, mask)

    cover_pass = gen_iou >= a_iou - margin
    pars_pass = ev["vertices"] <= a_v
    topo_pass = (c["AC4_format"]["pass"] and c["AC2c_orphans"]["pass"]
                 and c["AC2b_degenerate"]["pass"] and c["AC2a_centroid_in_mask"]["pass"])
    return {
        "piece": name,
        "generated": {"mode": mesh.get("_mode"), "vertices": ev["vertices"],
                      "triangles": ev["triangles"], "hull": ev["hull"],
                      "coverage_iou": gen_iou},
        "artist": {"vertices": a_v, "triangles": a_t, "hull": a_hull,
                   "coverage_iou": round(a_iou, 4)},
        "AC_coverage": {"pass": cover_pass, "gap": round(gen_iou - a_iou, 4),
                        "margin": margin},
        "AC_parsimony": {"pass": pars_pass, "gen_v": ev["vertices"], "artist_v": a_v},
        "AC_topology": {"pass": topo_pass,
                        "centroid_in_mask": c["AC2a_centroid_in_mask"]["value"],
                        "orphans": c["AC2c_orphans"]["value"],
                        "degenerate": c["AC2b_degenerate"]["value"],
                        "format": c["AC4_format"]["pass"]},
        "overall_pass": cover_pass and pars_pass and topo_pass,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd_parts", default="/tmp/robot_parts",
                    help="psd_slice 切出的件目錄(需先 psd_slice robot_parts.psd -o 此目錄)")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--margin", type=float, default=0.03)
    ap.add_argument("--budget", type=int, default=120)
    a = ap.parse_args()

    att = load_skin_attachments(a.skeleton)
    reps = []
    for name, fn in MESH_PIECES.items():
        p = os.path.join(a.psd_parts, fn)
        if not os.path.exists(p):
            raise SystemExit(f"缺件: {p};先跑 psd_slice.py assets/robot_parts.psd -o {a.psd_parts}")
        reps.append(compare_piece(name, p, att, a.margin, a.budget))

    out = {"pieces": reps, "all_pass": all(r["overall_pass"] for r in reps)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["all_pass"] else 1)


if __name__ == "__main__":
    main()
