#!/usr/bin/env python3
"""端到端閘:PSD 件 → S3 生成 mesh → 對照 Award 真實生產 mesh(有真值)。

背景(knowledge/s4-psd-to-spine-real.md):`robot_parts.psd`(機器人拆件)的
光暈 / 身體 / 左手 三件,在真實生產 spine `Award.json` 裡是 mesh attachment。
本工具把「PSD 切件 alpha」餵給 S3 生成器,產出 mesh,再與 Award 藝術家 mesh 做量化對照:

  ① 覆蓋率(coverage):alpha 內容有多少落在 mesh 三角內(藝術家 = 真值基準)。
  ② IoU:三角填充 vs alpha(同時懲罰過度外擴)。
  ③ 頂點預算:生成頂點數 vs 藝術家頂點數(精簡度)。
  ④ 拓樸格式:hull/索引/退化/孤兒(復用 evaluate_mesh)。
  ⑤ 三角品質:最小內角分佈 / sliver 比例(靜態網格健康度代理)。

★ 這 3 件在 Award **無 deform timeline**(weighted mesh,靠骨骼/權重變形,見對應 knowledge),
  故「真實位移場轉移」deform 閘對它們 **N/A**;本閘做的是「靜態覆蓋 + 拓樸 + 三角品質」對真值對照。
  這與 curtain/shadow(有 deform)的 `validate_against_real` 互補。

Award mesh `uvs` 為 0..1 相對「該件原圖」(已驗:直接映到 PSD 切件 alpha,IoU 0.95~0.98),
故藝術家基準可直接在切件像素座標算,免處理 atlas 縮放 / weighted bind 座標。

可重現:
  python3 tools/mesh_gen/compare_award_mesh.py            # 3 件全跑
  python3 tools/mesh_gen/compare_award_mesh.py --piece 身體
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from evaluate_mesh import evaluate as eval_mesh
import generate_mesh_v2 as g2
import psd_slice

# 機器人拆件裡「在 Award 為 mesh」的三件 → PSD 圖層名
MESH_PIECES = ["光暈", "身體", "左手"]
SLOT_PREFIX = "機器人拆件/"


def award_attachments(award_json):
    sk = json.load(open(award_json))
    skins = sk["skins"]
    skin = skins[0] if isinstance(skins, list) else skins
    return skin["attachments"] if "attachments" in skin else skin


def fill_tris(pts, tris, H, W):
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    return recon


def coverage_iou(recon, mask):
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    tot = int(mask.sum())
    iou = inter / union if union else 0.0
    cov = inter / tot if tot else 0.0
    return round(iou, 4), round(cov, 4)


def tri_quality(pts, tris):
    """三角形最小內角統計 + sliver(<15°)比例 — 靜態網格健康度代理。"""
    mins = []
    for t in tris:
        a, b, c = pts[t[0]], pts[t[1]], pts[t[2]]
        angs = []
        for p, q, r in ((a, b, c), (b, c, a), (c, a, b)):
            u = q - p; v = r - p
            nu = np.linalg.norm(u); nv = np.linalg.norm(v)
            if nu < 1e-9 or nv < 1e-9:
                angs.append(0.0); continue
            cosang = np.clip(np.dot(u, v) / (nu * nv), -1, 1)
            angs.append(np.degrees(np.arccos(cosang)))
        mins.append(min(angs))
    mins = np.array(mins) if len(mins) else np.array([0.0])
    slivers = int((mins < 15).sum())
    return {"min_angle": round(float(mins.min()), 2),
            "median_min_angle": round(float(np.median(mins)), 2),
            "sliver_frac": round(slivers / len(mins), 4), "n_tris": len(mins)}


def artist_metrics(att, slot, mask):
    a = att[slot][slot]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    iou, cov = coverage_iou(fill_tris(pts, tris, H, W), mask)
    q = tri_quality(pts, tris)
    return {"vertices": len(uvs), "triangles": len(tris), "hull": a["hull"],
            "weighted": len(a["vertices"]) != len(a["uvs"]),
            "iou": iou, "coverage": cov, "tri_quality": q}


def gen_metrics(mesh, mask):
    W, H = mesh["width"], mesh["height"]
    v = np.array(mesh["vertices"]).reshape(-1, 2)
    pts = np.column_stack([v[:, 0] + W / 2.0, H / 2.0 - v[:, 1]])
    tris = np.array(mesh["triangles"]).reshape(-1, 3)
    iou, cov = coverage_iou(fill_tris(pts, tris, mask.shape[0], mask.shape[1]), mask)
    topo = eval_mesh(mesh, mask, vertex_budget=256)  # 拓樸格式用大 budget(預算另判)
    fmt_ok = all(topo["criteria"][k]["pass"] for k in
                 ("AC4_format", "AC2b_degenerate", "AC2c_orphans"))
    return {"vertices": len(pts), "triangles": len(tris), "hull": mesh["hull"],
            "mode": mesh.get("_mode"), "iou": iou, "coverage": cov,
            "tri_quality": tri_quality(pts, tris), "topology_ok": fmt_ok,
            "topology_detail": {k: topo["criteria"][k] for k in
                                ("AC4_format", "AC2b_degenerate", "AC2c_orphans")}}


def compare_piece(att, layer, png, cov_margin, iou_margin, budget_factor, sliver_thresh):
    im = cv2.imread(png, cv2.IMREAD_UNCHANGED)
    mask = (im[:, :, 3] > 8).astype(np.uint8)
    slot = SLOT_PREFIX + layer
    art = artist_metrics(att, slot, mask)
    mesh = g2.generate(png, mode="auto")
    gen = gen_metrics(mesh, mask)

    cov_pass = gen["coverage"] >= art["coverage"] - cov_margin
    iou_pass = gen["iou"] >= art["iou"] - iou_margin
    budget_pass = gen["vertices"] <= art["vertices"] * budget_factor
    quality_pass = gen["tri_quality"]["sliver_frac"] <= sliver_thresh
    overall = cov_pass and iou_pass and budget_pass and gen["topology_ok"] and quality_pass
    return {
        "piece": layer, "slot": slot, "mask_wh": [int(mask.shape[1]), int(mask.shape[0])],
        "artist": art, "generated": gen,
        "gates": {
            "coverage": {"pass": bool(cov_pass), "gen": gen["coverage"],
                         "artist_baseline": art["coverage"], "margin": cov_margin},
            "iou": {"pass": bool(iou_pass), "gen": gen["iou"],
                    "artist_baseline": art["iou"], "margin": iou_margin},
            "vertex_budget": {"pass": bool(budget_pass), "gen": gen["vertices"],
                              "artist": art["vertices"], "factor": budget_factor},
            "topology": {"pass": bool(gen["topology_ok"])},
            "tri_quality": {"pass": bool(quality_pass),
                            "sliver_frac": gen["tri_quality"]["sliver_frac"],
                            "thresh": sliver_thresh},
        },
        "deform_gate": "N/A — Award 此件為 weighted mesh 且無 deform timeline(骨骼/權重變形)",
        "overall_pass": bool(overall),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--piece", default=None, help="只跑單件(如 身體);預設全跑")
    ap.add_argument("--out", default="/tmp/robot_parts")
    ap.add_argument("--cov-margin", type=float, default=0.02)
    ap.add_argument("--iou-margin", type=float, default=0.03)
    ap.add_argument("--budget-factor", type=float, default=2.0)
    ap.add_argument("--sliver-thresh", type=float, default=0.35)
    a = ap.parse_args()

    _, manifest, _ = psd_slice.slice_psd(a.psd, a.out)
    name2file = {p["name"]: os.path.join(a.out, p["file"]) for p in manifest["parts"]}
    att = award_attachments(a.award)

    targets = [a.piece] if a.piece else MESH_PIECES
    reports = []
    for layer in targets:
        if layer not in name2file:
            print(f"⚠️ PSD 無此圖層: {layer}", file=sys.stderr); continue
        reports.append(compare_piece(att, layer, name2file[layer],
                                     a.cov_margin, a.iou_margin,
                                     a.budget_factor, a.sliver_thresh))
    out = {"source": os.path.basename(a.psd), "award": os.path.basename(a.award),
           "pieces": reports,
           "overall_pass": all(r["overall_pass"] for r in reports) if reports else False}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["overall_pass"] else 1)


if __name__ == "__main__":
    main()
