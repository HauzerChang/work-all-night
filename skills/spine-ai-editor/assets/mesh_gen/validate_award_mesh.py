#!/usr/bin/env python3
"""端到端「PSD→件→S3 mesh」對真實生產標的(Award spine)驗收 — 靜態幾何閘。

背景(2026-08-10 發現):`機器人拆件/{光暈,身體,左手}` 在 Award 是 **weighted mesh**
且**全無 deform timeline**(靠骨骼權重變形,非逐頂點 deform)。故:
  - 無真實逐頂點位移場可轉移 → 不做 deform 轉移閘(那是 unweighted+deform 資產才有的真值)。
  - 這裡做「靜態幾何」對照:我的 S3 生成 mesh 之輪廓覆蓋(IoU vs 真實 alpha)是否 ≥ 藝術家同件 mesh
    的自身覆蓋(artist baseline);拓樸乾淨(0 退化/0 孤兒/重心在內);頂點數在預算內。

真值來源:Award atlas 切出的真實貼圖 alpha(多頁 + CW derotate,已校準);
藝術家 mesh 的 uvs+triangles(weighted 與否不影響 uvs/triangles 讀取)。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from generate_mesh import generate as gen_v1

ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def artist_mesh_iou(skeleton, name, mask):
    """藝術家 mesh(uvs+triangles)填滿 vs 真實 alpha 的 IoU + 頂點/hull 數。"""
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    a = att[name][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    iou = float(np.logical_and(recon, m).sum() / max(1, np.logical_or(recon, m).sum()))
    return {"iou": round(iou, 4), "vertices": len(uvs),
            "triangles": len(tris), "hull": a.get("hull"),
            "weighted": len(a["vertices"]) != len(a["uvs"])}


def validate_one(sk, atlas, png, name, tmp):
    sub = extract(atlas, png, name)          # 真實貼圖(RGBA,已 derotate)
    crop = os.path.join(tmp, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)

    artist = artist_mesh_iou(sk, name, mask)

    # 對齊藝術家頂點經濟:用其頂點數當預算,自適應 epsilon 反推輪廓解析度。
    mesh, _ = gen_v1(crop, target_verts=artist["vertices"])
    ev = evaluate(mesh, mask, vertex_budget=artist["vertices"] + 1, iou_thresh=0.0)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]

    topo_ok = (ev["criteria"]["AC2a_centroid_in_mask"]["pass"] and
               ev["criteria"]["AC2b_degenerate"]["pass"] and
               ev["criteria"]["AC2c_orphans"]["pass"] and
               ev["criteria"]["AC4_format"]["pass"])
    iou_ok = gen_iou >= artist["iou"]
    budget_ok = ev["vertices"] <= artist["vertices"]   # 不超過藝術家的頂點成本

    return {
        "name": name,
        "artist": artist,
        "generated": {"vertices": ev["vertices"], "triangles": ev["triangles"],
                      "hull": mesh["hull"], "iou": gen_iou},
        "AC_iou_ge_artist": {"gen": gen_iou, "artist": artist["iou"], "pass": bool(iou_ok)},
        "AC_topology_clean": {"pass": bool(topo_ok),
                              "centroid": ev["criteria"]["AC2a_centroid_in_mask"]["value"],
                              "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                              "orphans": ev["criteria"]["AC2c_orphans"]["value"]},
        "AC_vertex_economy": {"pass": bool(budget_ok), "gen": ev["vertices"],
                              "artist": artist["vertices"]},
        "overall_pass": bool(iou_ok and topo_ok and budget_ok),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reports = [validate_one(sk, a.atlas, a.png, n, a.tmp) for n in ROBOT_MESHES]
    allpass = all(r["overall_pass"] for r in reports)
    print(json.dumps({"reports": reports, "all_pass": allpass},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
