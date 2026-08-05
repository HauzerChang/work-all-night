#!/usr/bin/env python3
"""端到端「PSD件 → S3 生成 mesh → 對照 Award 真實生產 mesh」整合驗收。

背景(STATE.md 最高優先 bounded chunk):`robot_parts.psd` 的光暈/身體/左手 3 件在
生產 spine `Award` 中是 **mesh**(其餘右手/頭是 region)。這 3 件在 Award 無 deform
timeline(靠骨骼/權重變形,非逐頂點 deform)→ 故本閘不跑「真實 deform 轉移」,
改做**靜態覆蓋率 + 頂點預算 + 拓樸有效性**對照真實 mesh。

真值來源:Award atlas 切出的真實貼圖件(atlas_crop,已用 PSD 外部真值校過 CW 方向)。
uvs 對映驗證:對 3 件測 8 種方位,identity 全勝(0.97+)→ 與 validate_against_real
相同的 `uvs*(W,H)` 疊圖成立(de-rotate 後與 JSON uvs 同向)。

判準(每件):
  AC_iou     : 生成 mesh 覆蓋率 >= 藝術家 mesh 覆蓋率 - margin(生成不遜於真實件)。
  AC_budget  : 生成頂點數 <= 藝術家頂點數(精簡度不遜於真實件)。
  AC_valid   : 0 退化三角 / 0 孤兒頂點 / 格式合法(evaluate_mesh)。
  cross_iou  : 生成覆蓋遮罩 vs 藝術家覆蓋遮罩的 IoU(兩 mesh 外形相似度,參考量)。
"""
import argparse, json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask, mesh_pixel_coords
from generate_mesh_v2 import generate as gen_v2

MESH_PIECES = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def coverage_mask(pts, tris, H, W):
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    return recon


def artist_mesh(skeleton, slot, mask):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)[slot]
    a = list(att.values())[0]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    cov = coverage_mask(rp, tris, H, W)
    iou = float(np.logical_and(cov, mask).sum() / np.logical_or(cov, mask).sum())
    return {"verts": len(uvs), "hull": a.get("hull"),
            "tris": len(tris)}, cov, iou


def compare_piece(sk, atlas, png, slot, tmp, iou_margin=0.02):
    sub = extract(atlas, png, slot)
    crop = os.path.join(tmp, "_award_region.png")
    cv2.imwrite(crop, sub)
    mask = load_mask(crop)
    H, W = mask.shape

    mesh = gen_v2(crop, mode="auto")
    ev = evaluate(mesh, mask, vertex_budget=256)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]
    nv = ev["vertices"]

    art, art_cov, art_iou = artist_mesh(sk, slot, mask)

    gpts, _, _ = mesh_pixel_coords(mesh)
    gtris = np.array(mesh["triangles"]).reshape(-1, 3)
    gen_cov = coverage_mask(gpts, gtris, H, W)
    cross = float(np.logical_and(gen_cov, art_cov).sum() /
                  np.logical_or(gen_cov, art_cov).sum())

    valid = (ev["criteria"]["AC4_format"]["pass"] and
             ev["criteria"]["AC2b_degenerate"]["pass"] and
             ev["criteria"]["AC2c_orphans"]["pass"])
    iou_pass = gen_iou >= art_iou - iou_margin
    budget_pass = nv <= art["verts"]

    return {
        "piece": slot,
        "region_px": f"{W}x{H}",
        "generated": {"mode": mesh.get("_mode"), "verts": nv, "hull": mesh["hull"],
                      "tris": len(gtris), "iou": round(gen_iou, 4)},
        "artist": {"verts": art["verts"], "hull": art["hull"], "tris": art["tris"],
                   "iou": round(art_iou, 4)},
        "cross_iou": round(cross, 4),
        "AC_iou": {"gen": round(gen_iou, 4), "artist": round(art_iou, 4),
                   "margin": iou_margin, "pass": iou_pass},
        "AC_budget": {"gen_verts": nv, "artist_verts": art["verts"], "pass": budget_pass},
        "AC_valid": {"pass": valid,
                     "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                     "orphans": ev["criteria"]["AC2c_orphans"]["value"]},
        "overall_pass": iou_pass and budget_pass and valid,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reports = [compare_piece(sk, a.atlas, a.png, slot, a.tmp, a.margin)
               for slot in MESH_PIECES]
    out = {"pieces": reports,
           "all_pass": all(r["overall_pass"] for r in reports)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["all_pass"] else 1)


if __name__ == "__main__":
    main()
