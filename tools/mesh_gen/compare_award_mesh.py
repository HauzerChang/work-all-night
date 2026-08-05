#!/usr/bin/env python3
"""端到端「PSD件/atlas件 → S3 generate_mesh_v2 → 對照 Award 真實 mesh」靜態比對閘。

背景(knowledge/s4-psd-to-spine-real.md):機器人 3 個 mesh 件(光暈/身體/左手)在 Award
皆為 **weighted mesh 且無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform)。
故此比對用「靜態拓樸/覆蓋率」對照藝術家真值,而非 deform 轉移閘(後者需 deform timeline)。

真相來源與對齊:
  - 用 atlas_crop 從 Award atlas 取「藝術家方向」region alpha(已以 PSD 外部真值校正 derotate=CW)。
  - Award mesh uvs 為 0..1 over region(main_draw 已證此慣例:artist_iou 自洽)。
    先做「藝術家自我 IoU」自一致性檢查(uvs 重建自身 alpha 應 ~0.9);過關才信對齊正確。
  - 對同一 region alpha 跑 generate_mesh_v2,量測生成 mesh 的覆蓋 IoU。

判準(L2 客觀項):
  - alignment_ok:artist_iou >= 0.80(對齊/UV 慣例自洽,evaluator 可信)。
  - coverage_pass:gen_iou >= artist_iou - margin(生成覆蓋率不輸藝術家)。
  - structure_pass:evaluate_mesh 的格式/退化/孤兒/預算全過。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from atlas_crop import extract
from evaluate_mesh import evaluate as eval_mesh, load_mask
from generate_mesh_v2 import generate as gen_v2


ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def artist_mesh(sk, name):
    skins = sk["skins"]
    skin = skins[0] if isinstance(skins, list) else skins
    att = skin.get("attachments", skin)
    # slot == name for these robot pieces
    a = att[name][name]
    return a


def artist_iou(a, mask):
    """藝術家 mesh uvs(0..1 over region) 重建 vs region alpha 的 IoU。"""
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    return inter / union if union else 0.0


def compare_one(sk, atlas, png, name, tmp_dir, margin=0.03):
    sub = extract(atlas, png, name)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)
    Hn, Wn = mask.shape

    a = artist_mesh(sk, name)
    a_iou = artist_iou(a, mask)
    a_nv = len(a["uvs"]) // 2
    a_hull = a.get("hull")
    a_ntri = len(a["triangles"]) // 3
    a_weighted = len(a["vertices"]) != len(a["uvs"])

    mesh = gen_v2(crop, mode="auto")
    g_rep = eval_mesh(mesh, mask)
    g_iou = g_rep["criteria"]["AC1_iou"]["value"]
    g_nv = len(mesh["uvs"]) // 2

    alignment_ok = a_iou >= 0.80
    coverage_pass = g_iou >= a_iou - margin
    structure_pass = all(
        g_rep["criteria"][k]["pass"]
        for k in ("AC4_format", "AC2b_degenerate", "AC2c_orphans", "AC3_vertex_budget")
    )
    return {
        "name": name,
        "region_px": [Wn, Hn],
        "artist": {"vertices": a_nv, "hull": a_hull, "triangles": a_ntri,
                   "weighted": a_weighted, "self_iou": round(a_iou, 4)},
        "generated": {"vertices": g_nv, "hull": mesh["hull"],
                      "triangles": len(mesh["triangles"]) // 3,
                      "mode": mesh.get("_mode"), "iou": round(g_iou, 4)},
        "alignment_ok": alignment_ok,
        "coverage_pass": coverage_pass,
        "structure_pass": structure_pass,
        "overall_pass": alignment_ok and coverage_pass and structure_pass,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")  # multipage auto-resolved by atlas_crop
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--margin", type=float, default=0.03)
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reports = [compare_one(sk, a.atlas, a.png, nm, a.tmp, a.margin) for nm in ROBOT_MESHES]
    overall = all(r["overall_pass"] for r in reports)
    print(json.dumps({"overall_pass": overall, "meshes": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
