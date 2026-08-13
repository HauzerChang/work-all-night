#!/usr/bin/env python3
"""端到端「件→S3 mesh」對照真實生產 mesh(Award)驗收。

背景(knowledge/s4-psd-to-spine-real.md):機器人拆件的 5 件中,光暈/身體/左手 3 件
在生產 spine `Award` 裡是 **mesh**(藝術家手做),右手/頭是 region。這 3 件給了我們
「藝術家真值 mesh」可對照 S3 生成器的輸出 —— 這是目前唯一有真實生產 mesh 真值的標的。

流程(純 CPU,不需額外 PNG,Award.png/Award2.png 已在 assets/):
  atlas 切件 alpha(atlas_crop.extract,多頁 + CW derotate)
  → generate_mesh_v2(auto)  ← 這幾件非高瘦 strip,auto 會回退 v1 Delaunay
  → 對照:① 覆蓋率 IoU(生成 vs 藝術家真值 mesh 基準)
          ② 頂點預算(生成 vs 藝術家)
          ③ 靜置拓樸乾淨(self-intersection / degenerate = 0)

⚠️ 這 3 件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform),
   故不套 transfer_deform_check(沒有真實位移場可轉移);deform 穩健性交由 rows/strip
   結論(見 s3-four-mesh-generalization.md)。此處的真值價值在「覆蓋率 + 拓樸」對照。

評估器可信度先驗:同時把**藝術家自己的 mesh** 餵進同一組閘(靜置拓樸 / IoU),
   確認閘對真值不誤殺,再信對生成 mesh 的判定。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask, mesh_pixel_coords
import deform_eval as de


# 機器人拆件在 Award 為 mesh 的 3 件(slot==name)
MESH_PIECES = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def artist_mesh(skeleton, slot, name):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)[slot][name]


def artist_iou(att, mask):
    """藝術家 mesh(uvs 為 region-local 0..1)填三角 vs 件 alpha 的 IoU。"""
    uvs = np.array(att["uvs"]).reshape(-1, 2)
    tris = np.array(att["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return float(np.logical_and(recon, mask).sum() / np.logical_or(recon, mask).sum())


def rest_topology(pts, tris):
    """靜置姿勢的拓樸乾淨度(self-intersection / degenerate;無 setup 比較故不判 flip)。"""
    r = de.check(pts, tris, None)
    return {"self_intersections": r["self_intersections"], "degenerate": r["degenerate"]}


def artist_pixel_coords(att, W, H):
    uvs = np.array(att["uvs"]).reshape(-1, 2)
    return np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])


# delaunay 覆蓋率自動收斂:對軟邊/圓潤大 blob,hull 點密度(epsilon_frac)決定覆蓋率
# (與 strip 的 rows 同理)。預設 0.008 對大軟 blob 欠取樣 → 由粗到細降 epsilon,
# 取「第一個過覆蓋率門檻且仍在頂點預算內」者。純確定性掃描,無隨機 / 無學習。
EPS_LADDER = [0.008, 0.006, 0.004, 0.003, 0.002]


def gen_with_coverage(crop, mask, target, margin, budget):
    """回傳 (mesh, tuned_epsilon|None, iterations)。auto 選 strip 時直接回,不掃 epsilon。"""
    from generate_mesh_v2 import generate as gen
    from generate_mesh import generate as g1
    base = gen(crop, mode="auto")
    if base.get("_mode") != "delaunay-v1":
        return base, None, 1                       # strip 由 rows 決定覆蓋,不在此掃
    best = None
    for it, eps in enumerate(EPS_LADDER, 1):
        m, _ = g1(crop, max_interior=40, epsilon_frac=eps)
        m["_mode"] = "delaunay-v1"
        m["_epsilon"] = eps
        iou = evaluate(m, mask, vertex_budget=10**6)["criteria"]["AC1_iou"]["value"]
        nv = len(m["uvs"]) // 2
        best = (m, eps, it)                          # 記最後一個(密度最高)當保底
        if iou >= target - margin and nv <= budget:
            return m, eps, it
    return best[0], best[1], best[2]                 # 都沒過:回最密的一版


def compare_one(sk, atlas, png, piece, tmp_dir, iou_margin=0.03, budget=64):
    att = artist_mesh(sk, piece, piece)
    sub = extract(atlas, png, piece)
    crop = os.path.join(tmp_dir, "_award_piece.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)          # (alpha>8) 0/1
    H, W = mask.shape

    a_iou_pre = artist_iou(att, mask)
    mesh, tuned_eps, iters = gen_with_coverage(crop, mask, a_iou_pre, iou_margin, budget)

    ev = evaluate(mesh, mask, vertex_budget=budget)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]
    gen_nv = ev["vertices"]
    gen_tris = ev["triangles"]

    # 生成 mesh 靜置拓樸
    gpts, _, _ = mesh_pixel_coords(mesh)
    gtris = np.array(mesh["triangles"], np.int32).reshape(-1, 3)
    gen_topo = rest_topology(gpts, gtris)

    # 藝術家真值:IoU + 靜置拓樸(先驗閘可信度)
    a_iou = artist_iou(att, mask)
    a_nv = len(att["uvs"]) // 2
    a_tris = len(att["triangles"]) // 3
    apts = artist_pixel_coords(att, W, H)
    atris = np.array(att["triangles"], np.int32).reshape(-1, 3)
    a_topo = rest_topology(apts, atris)

    iou_pass = gen_iou >= a_iou - iou_margin
    topo_pass = gen_topo["self_intersections"] == 0 and gen_topo["degenerate"] == 0
    budget_pass = gen_nv <= budget

    return {
        "piece": piece,
        "region_alpha_px": f"{W}x{H}",
        "generated": {"mode": mesh.get("_mode"), "vertices": gen_nv, "triangles": gen_tris,
                      "hull": mesh["hull"], "iou": round(gen_iou, 4),
                      "tuned_epsilon": mesh.get("_epsilon"), "coverage_iters": iters,
                      "rest_topology": gen_topo},
        "artist_truth": {"vertices": a_nv, "triangles": a_tris, "hull": att["hull"],
                         "iou": round(a_iou, 4), "rest_topology": a_topo},
        "AC_coverage_iou": {"gen": round(gen_iou, 4), "artist_baseline": round(a_iou, 4),
                            "margin": iou_margin, "pass": bool(iou_pass)},
        "AC_vertex_budget": {"gen": gen_nv, "artist": a_nv, "budget": budget, "pass": bool(budget_pass)},
        "AC_rest_clean": {"gen": gen_topo, "pass": bool(topo_pass)},
        "overall_pass": bool(iou_pass and topo_pass and budget_pass),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")   # 多頁時 extract 依 region.page 自選
    ap.add_argument("--pieces", nargs="*", default=MESH_PIECES)
    ap.add_argument("--iou-margin", type=float, default=0.03)
    ap.add_argument("--budget", type=int, default=64)
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reps = []
    for p in a.pieces:
        reps.append(compare_one(sk, a.atlas, a.png, p, a.tmp, a.iou_margin, a.budget))
    out = {"pieces": reps,
           "all_pass": all(r["overall_pass"] for r in reps),
           "artist_topology_all_clean": all(
               r["artist_truth"]["rest_topology"]["self_intersections"] == 0 for r in reps)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["all_pass"] else 1)


if __name__ == "__main__":
    main()
