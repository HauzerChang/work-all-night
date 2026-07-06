#!/usr/bin/env python3
"""端到端「PSD→件→mesh」對真實生產標的(Award)驗收 — S3+S4 串接。

對 Award 中「機器人拆件」的 3 個 mesh 件(光暈/身體/左手),從 atlas 切出真實貼圖 alpha,
跑 S3 生成器 → 與 Award 的**藝術家真實 mesh** 在同一張 alpha 上比對:

  AC-cover : 生成 mesh 覆蓋率 IoU ≥ 藝術家 mesh 自身 IoU(真實生產基準,AC.md AC1)
  AC-econ  : 生成頂點數 ≤ 藝術家頂點數(同等或更精簡)
  AC-topo  : 生成 mesh 過拓樸閘(0 退化 / 0 孤兒 / 重心≥99% / 格式合法)
  AC-deform: N/A —— 這 3 件在 Award 無 deform timeline(靠骨骼權重變形),
             我方 unweighted 生成器不產權重 → 誠實排除,不做假性 deform 判定。

真值來源:Award.json 藝術家 mesh(uvs 為 region-local 正規化)。alpha 來源:atlas 切件
(0.70 縮放,但 IoU 正規化 scale-invariant;藝術家與生成用同一張 mask,比對公平)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate
import generate_mesh_v2 as g2
from auto_tune import generate_auto


MESH_PARTS = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def alpha_mask(sub):
    """atlas 切件 BGRA → 二值 alpha mask(與 evaluate/generate 的 >8 一致)。"""
    if sub.ndim == 3 and sub.shape[2] == 4:
        a = sub[:, :, 3]
    else:
        g = sub if sub.ndim == 2 else cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
        a = (g > 0).astype(np.uint8) * 255
    return (a > 8).astype(np.uint8)


def artist_mesh(skeleton, slot, name):
    skin = skeleton["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)[slot][name]


def fill_iou_from_uvs(att, mask):
    """把藝術家 mesh 的 uvs(region-local 正規化)映到 mask 尺寸,填三角求 IoU。"""
    uvs = np.array(att["uvs"]).reshape(-1, 2)
    tris = np.array(att["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    return (inter / union) if union else 0.0


def compare_one(sk, atlas, png, slot, name, tmp_dir, gen="auto"):
    sub = extract(atlas, png, name)
    mask = alpha_mask(sub)
    crop = os.path.join(tmp_dir, "_award_region.png")
    cv2.imwrite(crop, sub)

    att = artist_mesh(sk, slot, name)
    artist_v = len(att["uvs"]) // 2
    artist_iou = fill_iou_from_uvs(att, mask)

    if gen == "auto":
        # evaluator-driven:掃 epsilon 收斂到藝術家 IoU,預算=藝術家頂點數
        mesh, _ = generate_auto(crop, target_iou=artist_iou, budget=artist_v)
    else:
        mesh = g2.generate(crop, mode="auto")
        if isinstance(mesh, tuple):
            mesh = mesh[0]
    # budget = 藝術家頂點數(這批件比 main_draw 密,固定 64 不適用 → 以真值為預算)
    ev = evaluate(mesh, mask, vertex_budget=artist_v, iou_thresh=artist_iou)
    gen_v = ev["vertices"]
    gen_iou = ev["criteria"]["AC1_iou"]["value"]

    topo_pass = all(ev["criteria"][k]["pass"] for k in
                    ("AC2a_centroid_in_mask", "AC2b_degenerate", "AC2c_orphans", "AC4_format"))
    cover_pass = gen_iou >= artist_iou
    econ_pass = gen_v <= artist_v

    return {
        "part": name,
        "mask_shape": [int(mask.shape[1]), int(mask.shape[0])],
        "mode": mesh.get("_mode", "auto-v1"),
        "tune": mesh.get("_tune"),
        "artist": {"vertices": artist_v, "hull": att.get("hull"),
                   "triangles": len(att["triangles"]) // 3,
                   "iou": round(artist_iou, 4)},
        "generated": {"vertices": gen_v, "hull": mesh["hull"],
                      "triangles": ev["triangles"], "iou": round(gen_iou, 4)},
        "AC_cover": {"gen_iou": round(gen_iou, 4), "artist_iou": round(artist_iou, 4),
                     "pass": bool(cover_pass)},
        "AC_econ": {"gen_v": gen_v, "artist_v": artist_v, "pass": bool(econ_pass)},
        "AC_topo": {"pass": bool(topo_pass),
                    "detail": {k: ev["criteria"][k].get("value", ev["criteria"][k]["pass"])
                               for k in ("AC2a_centroid_in_mask", "AC2b_degenerate",
                                         "AC2c_orphans")}},
        "AC_deform": "N/A (無 deform timeline;靠骨骼權重,unweighted 生成器不比對)",
        "overall_pass": bool(cover_pass and econ_pass and topo_pass),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")  # 多頁時 atlas_crop 自動選 page
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--gen", choices=["auto", "v2"], default="auto")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reports = []
    for name in MESH_PARTS:
        slot = name  # Award 中 slot 名 == attachment 名
        reports.append(compare_one(sk, a.atlas, a.png, slot, name, a.tmp, a.gen))
    out = {"parts": reports,
           "all_pass": all(r["overall_pass"] for r in reports)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["all_pass"] else 1)


if __name__ == "__main__":
    main()
