#!/usr/bin/env python3
"""S3 端到端驗收:PSD件/生產貼圖 → S3 generate_mesh → 對照真實 spine(Award)的美術 mesh。

背景(見 knowledge/s4-psd-to-spine-real.md):Award「機器人拆件」有 3 個 mesh 件
(光暈/左手/身體,皆 weighted)。前一 session 已用 texture alpha-IoU 0.92~0.99 確認
「PSD 切件 = spine 生產貼圖素材(同一份)」。本工具在**同一個 region 影像框**裡把
S3 生成 mesh 與 Award 美術 mesh 做量化對照,完成「件 → mesh」對真實生產標的的端到端閘。

關鍵發現(本 session):
  1. **Spine JSON mesh 的 `uvs` 是 region-local [0,1](非 atlas-page 分數)**。
     故美術 mesh 覆蓋率 = uvs×(regionW,regionH) 直接光柵化,vflip=False。
     (經 4 種 v/derotate 組合實測:vflip=False 對 3 件皆 IoU 0.97~0.98,其餘 <0.61。)
  2. 這 3 件在 Award **無 deform timeline**(weighted、靠骨骼變形)→ 真實逐頂點 deform
     轉移閘不適用;此處驗收 = 靜態覆蓋率 IoU + 拓樸合法性 + 頂點經濟度。

共同框:用 `atlas_crop.extract` 取 Award region(已 derotate+0.70 縮放)的 alpha 當
來源+真值,S3 生成也吃同一張 → 零跨檔套準誤差(PSD↔atlas 等價性已於 session 006 確立)。

AC:gen_iou >= artist_iou - margin(預設 margin=0.03);拓樸 overall_pass;報告頂點經濟度。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from atlas_crop import parse_atlas, extract
from evaluate_mesh import evaluate
from generate_mesh_v2 import generate as gen_v2

ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def award_attachment(sk, slot):
    skin = sk["skins"]
    skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    return atts[slot][slot]


def rasterize(pts, tris, W, H):
    m = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(m, np.round(pts[t]).astype(np.int32), 1)
    return m


def iou(a, b):
    return float(np.logical_and(a, b).sum() / max(np.logical_or(a, b).sum(), 1))


def artist_coverage(att, mask):
    """美術 mesh 在 region 框的覆蓋率(uvs 為 region-local [0,1], vflip=False)。"""
    uvs = np.array(att["uvs"]).reshape(-1, 2)
    tris = np.array(att["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    return iou(rasterize(pts, tris, W, H), mask), len(uvs), len(tris), att["hull"]


def has_deform(sk, slot, name):
    """Award 是否對此 slot/attachment 有 deform timeline。"""
    for anim in sk.get("animations", {}).values():
        d = anim.get("deform", {})
        for skin_name, slots in d.items():
            if slot in slots and name in slots[slot]:
                return True
    return False


def compare_one(sk, atlas, png, slot, tmp_dir, margin):
    sub = extract(atlas, png, slot)                 # derotate + 0.70 縮放後的 region
    alpha = sub[:, :, 3] if (sub.ndim == 3 and sub.shape[2] == 4) else \
        (cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY) > 0).astype(np.uint8) * 255
    mask = (alpha > 8).astype(np.uint8)
    crop = os.path.join(tmp_dir, "_robot_region.png")
    cv2.imwrite(crop, sub)

    mesh = gen_v2(crop, mode="auto")
    ev = evaluate(mesh, mask, vertex_budget=128, iou_thresh=0.0)   # IoU 門檻改用藝術家基準
    gen_iou = ev["criteria"]["AC1_iou"]["value"]
    gen_nv = ev["vertices"]

    att = award_attachment(sk, slot)
    art_iou, art_nv, art_tris, art_hull = artist_coverage(att, mask)
    deform = has_deform(sk, slot, slot)

    topo_ok = (ev["criteria"]["AC2b_degenerate"]["pass"] and
               ev["criteria"]["AC2c_orphans"]["pass"] and
               ev["criteria"]["AC4_format"]["pass"])
    iou_ok = gen_iou >= art_iou - margin
    return {
        "slot": slot,
        "region_wh": [mask.shape[1], mask.shape[0]],
        "gen": {"mode": mesh.get("_mode"), "vertices": gen_nv,
                "triangles": ev["triangles"], "hull": mesh["hull"], "iou": round(gen_iou, 4)},
        "artist": {"vertices": art_nv, "triangles": art_tris, "hull": art_hull,
                   "coverage_iou": round(art_iou, 4), "weighted": len(att["vertices"]) != len(att["uvs"]),
                   "has_deform_timeline": deform},
        "AC_iou": {"gen": round(gen_iou, 4), "artist_baseline": round(art_iou, 4),
                   "margin": margin, "pass": iou_ok},
        "AC_topology": {"pass": topo_ok,
                        "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                        "orphans": ev["criteria"]["AC2c_orphans"]["value"]},
        "overall_pass": iou_ok and topo_ok,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--margin", type=float, default=0.03)
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reports = [compare_one(sk, a.atlas, a.png, s, a.tmp, a.margin) for s in ROBOT_MESHES]
    allpass = all(r["overall_pass"] for r in reports)
    print(json.dumps({"overall_pass": allpass, "pieces": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
