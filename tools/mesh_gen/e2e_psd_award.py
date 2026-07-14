#!/usr/bin/env python3
"""端到端驗證:分層 PSD 件 → S3 generate_mesh_v2 → 對照 Award 真實藝術家 mesh(靜態輪廓)。

背景(STATE.md 最高優先 chunk):`robot_parts.psd` 的三個 mesh 件(光暈/身體/左手)在生產
spine `Award` 中就是藝術家手做的 weighted mesh。這給了「S3 生成的 mesh」一個**真實生產真值**
可對照,把 S4(PSD 切件)+ S3(mesh 生成)串成端到端並用外部真值驗收。

方法(純 CPU,不需 Award.png;alpha 來源 = PSD 切件本身):
  1. psd_slice 切出每件緊湊 RGBA → alpha mask(件影像座標系,imgW×imgH)。
  2. 藝術家 mesh:Award.json 的 uvs 為「region 局部 0..1」,乘以件影像 W/H 落回件座標系
     → 光柵化三角覆蓋 → 與件 alpha 的 IoU = 藝術家 mesh 對藝術的包覆基準。
  3. 生成 mesh:generate_mesh_v2.generate(件PNG) → evaluate IoU(vs alpha)+ 覆蓋光柵。
  4. 指標:
     - AC1 生成 IoU(vs alpha) >= 藝術家 IoU(vs alpha) - margin(生成至少和藝術家一樣包覆藝術)。
     - AC2 生成↔藝術家覆蓋 IoU(兩 mesh 是否覆蓋同一 footprint)。
     - AC3 頂點預算:生成頂點數 vs 藝術家頂點數(報告,不硬性 fail)。

⚠️ 限制:Award 三件皆 **weighted**(骨驅動,無 deform timeline),故本 chunk 只做**靜態輪廓**
對照;weighted deform 對照留待後續 chunk(需重現 bone-skinning,非 deform 轉移)。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from psd_slice import slice_psd
from evaluate_mesh import evaluate, load_mask
from generate_mesh_v2 import generate as gen_v2

ROBOT_MESHES = ["光暈", "身體", "左手"]  # Award 中為 mesh 的機器人件


def award_attachment(sk, layer_name):
    slot = f"機器人拆件/{layer_name}"
    skins = sk["skins"]
    slots = skins["default"] if isinstance(skins, dict) else \
        next(s["attachments"] for s in skins if s["name"] == "default")
    return slot, slots[slot][slot]


def raster_mesh(uvs, tris, W, H, flip_y=False):
    """把 uvs(0..1)乘件影像尺寸,光柵化三角 → 覆蓋 mask。"""
    u = np.array(uvs).reshape(-1, 2).astype(np.float64)
    px = u[:, 0] * W
    py = (1.0 - u[:, 1]) * H if flip_y else u[:, 1] * H
    rp = np.column_stack([px, py])
    t = np.array(tris).reshape(-1, 3)
    m = np.zeros((H, W), np.uint8)
    for tri in t:
        cv2.fillConvexPoly(m, np.round(rp[tri]).astype(np.int32), 1)
    return m


def iou(a, b):
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter / union) if union else 0.0


def run(psd_path, award_path, tmp_dir, iou_margin=0.02):
    os.makedirs(tmp_dir, exist_ok=True)
    _, manifest, parts = slice_psd(psd_path, tmp_dir)
    sk = json.load(open(award_path))
    by_name = {e["name"]: (e, im) for e, im in parts}

    reports = []
    for layer in ROBOT_MESHES:
        entry, im = by_name[layer]
        W, H = im.width, im.height
        alpha = (np.array(im)[:, :, 3] > 8).astype(np.uint8)

        # 藝術家 mesh(真值)
        slot, att = award_attachment(sk, layer)
        a_uvs, a_tris = att["uvs"], att["triangles"]
        a_nv = len(a_uvs) // 2
        # 方向:試直/翻 y,取與件 alpha IoU 較高者(件座標系原點慣例校驗)
        cand = {fy: raster_mesh(a_uvs, a_tris, W, H, fy) for fy in (False, True)}
        flip = max(cand, key=lambda fy: iou(cand[fy], alpha))
        artist_cover = cand[flip]
        artist_iou = iou(artist_cover, alpha)

        # 生成 mesh
        crop = os.path.join(tmp_dir, entry["file"])
        mesh = gen_v2(crop, mode="auto")
        g_nv = len(mesh["uvs"]) // 2
        mask = load_mask(crop)
        gen_iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
        gen_cover = raster_mesh(mesh["uvs"], mesh["triangles"], W, H, flip_y=False)

        rep = {
            "piece": layer, "slot": slot, "img_wh": [W, H],
            "artist": {"vertices": a_nv, "triangles": len(a_tris) // 3,
                       "hull": att.get("hull"), "weighted": len(att["vertices"]) != len(a_uvs),
                       "iou_vs_alpha": round(artist_iou, 4), "uv_flip_y": flip},
            "generated": {"vertices": g_nv, "triangles": len(mesh["triangles"]) // 3,
                          "hull": mesh["hull"], "mode": mesh.get("_mode"),
                          "iou_vs_alpha": round(gen_iou, 4)},
            "gen_vs_artist_cover_iou": round(iou(gen_cover, artist_cover), 4),
            "AC1_silhouette": {"pass": gen_iou >= artist_iou - iou_margin,
                               "detail": f"gen {gen_iou:.4f} >= artist {artist_iou:.4f} - {iou_margin}"},
        }
        rep["overall_pass"] = rep["AC1_silhouette"]["pass"]
        reports.append(rep)
    return reports


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--tmp", default="/tmp/e2e_psd_award")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    reps = run(a.psd, a.award, a.tmp, a.margin)
    print(json.dumps(reps, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all(r["overall_pass"] for r in reps) else 1)


if __name__ == "__main__":
    main()
