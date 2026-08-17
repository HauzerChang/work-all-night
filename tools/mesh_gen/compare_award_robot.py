#!/usr/bin/env python3
"""S3+S4 端到端:對第二份生產資產 Award 的機器人 mesh 件驗證 v2 生成器泛化性。

背景(STATE.md 最高優先 chunk):main_draw 的 4 個 mesh 全是 **unweighted**;Award 的機器人
三件(光暈/左手/身體)是 **weighted** mesh(vertices 為 [骨數,骨idx,bindX,bindY,權重,...]
攤平變長格式,雷點 #6)。本工具在「atlas region 像素框」中做靜態覆蓋率對照:

  atlas 切件(真值素材)→ 生成 v2 mesh → ① 生成 mesh IoU(vs 件 alpha)
                                        ② 藝術家 mesh 覆蓋率(uvs×region 幾何,weighted 也適用)
  判定:生成 IoU >= 藝術家覆蓋率 − margin(對齊藝術家而非武斷 0.95,同 validate_against_real)。

⚠️ deform 閘不含在此:deform_eval.load_mesh/real_deform_field 把 vertices reshape 成 (nv,2),
   對 weighted mesh 會壞(格式不同)。weighted-aware deform 轉移是後續 chunk(見 STATE 未解)。
   artist_iou 只用 uvs+triangles → weighted/unweighted 皆可,故靜態對照可靠。

同時做 PSD 端點健全性:對 robot_parts.psd 切出的對應件也跑一次 v2,確認生成器對「PSD 來源」
(不同解析度/padding)同樣產出乾淨 mesh(端到端 PSD→件→mesh 不只限 atlas 來源)。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from generate_mesh_v2 import generate as gen_v2


# 機器人三件:mesh slot/attachment 名 == atlas region 名
ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def artist_coverage(skeleton, slot, name, H, W):
    """藝術家 mesh 在 region 像素框的覆蓋 mask(uvs×尺寸,三角填充)。weighted 亦適用。"""
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uvs = np.array(a["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return recon, uvs.shape[0], tris.shape[0], int(a["hull"])


def cov_iou(cov, mask):
    return float(np.logical_and(cov, mask).sum() / max(np.logical_or(cov, mask).sum(), 1))


def run_atlas(skeleton_path, atlas_path, png_path, tmp_dir, margin=0.0):
    sk = json.load(open(skeleton_path))
    os.makedirs(tmp_dir, exist_ok=True)
    out = {}
    for name in ROBOT_MESHES:
        sub = extract(atlas_path, png_path, name)
        crop = os.path.join(tmp_dir, "_" + name.split("/")[-1] + ".png")
        cv2.imwrite(crop, sub)
        mask = load_mask(crop)                      # bool HxW
        H, W = mask.shape

        mesh = gen_v2(crop, mode="auto")
        gen_iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]

        cov, a_nv, a_tris, a_hull = artist_coverage(sk, name, name, H, W)
        artist_base = cov_iou(cov, mask)            # 藝術家對自身 alpha 的覆蓋率(基準)

        out[name] = {
            "region_px": [W, H],
            "gen": {"mode": mesh.get("_mode"), "vertices": len(mesh["uvs"]) // 2,
                    "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3,
                    "iou": round(gen_iou, 4)},
            "artist": {"vertices": a_nv, "hull": a_hull, "triangles": a_tris,
                       "coverage": round(artist_base, 4), "weighted": True},
            "pass": gen_iou >= artist_base - margin,
        }
    return out


def run_psd_source(psd_path, tmp_dir):
    """PSD 端點健全性:對 robot_parts.psd 各件跑 v2,回報 mode/頂點/自身 IoU(生成器對 PSD 來源可用)。"""
    from psd_slice import slice_psd
    _, manifest, parts = slice_psd(psd_path, os.path.join(tmp_dir, "psd_parts"))
    res = {}
    for entry, im in parts:
        fn = os.path.join(tmp_dir, "psd_parts", entry["file"])
        mask = load_mask(fn)
        mesh = gen_v2(fn, mode="auto")
        gen_iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
        res[entry["name"]] = {"px": entry["size"], "mode": mesh.get("_mode"),
                              "vertices": len(mesh["uvs"]) // 2, "hull": mesh["hull"],
                              "iou": round(gen_iou, 4)}
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")   # 多頁:extract 依 region.page 自動選頁
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--tmp", default="/tmp/award_robot")
    ap.add_argument("--margin", type=float, default=0.0)
    a = ap.parse_args()

    atlas = run_atlas(a.skeleton, a.atlas, a.png, a.tmp, a.margin)
    rep = {"atlas_frame_vs_artist": atlas,
           "overall_pass": all(v["pass"] for v in atlas.values())}
    if os.path.exists(a.psd):
        rep["psd_source_sanity"] = run_psd_source(a.psd, a.tmp)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
