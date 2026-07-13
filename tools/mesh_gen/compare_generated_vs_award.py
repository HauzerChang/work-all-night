#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 generate_mesh_v2 → 對照 Award 真實生產 mesh。

三件機器人 mesh(光暈/左手/身體)在 Award 中是藝術家手做的 weighted mesh(生產真值)。
把「生成 mesh 的覆蓋率」拿去跟「藝術家 mesh 的覆蓋率」比,同一張真實 alpha 為基準:

  ① 用 atlas_crop.extract 取 region 去旋轉後的真實貼圖(atlas 解析度,~0.70 縮小)。
  ② 藝術家 mesh 的 uvs 為 **region 局部 0..1、y 向下**(2026-07-13 校正:先前 log 006
     誤以為是 atlas UV;實測 u,v 幾乎鋪滿 [0,1] 且不落在 region 的 atlas box 內 →
     確認為局部 UV。直接 px=u*W, py=v*H、不翻 y 時藝術家對自身貼圖 IoU≈0.97–0.98)。
  ③ generate_mesh_v2 在同一張 crop 上生成 → 同法光柵化 → IoU(vs 同一 alpha)。
  ④ 報告:兩者 IoU、頂點/hull/三角數、生成⇄藝術家形狀 IoU;
     pass = 生成 IoU >= 藝術家 IoU - margin(藝術家自身覆蓋率為基準,非武斷 0.95)。

校驗:藝術家 mesh 對自身貼圖 IoU 必須高(~0.97),否則表示 UV 解讀錯 → 拒絕出報告。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import parse_atlas, extract
from generate_mesh_v2 import generate as gen_v2

ART_IOU_SANITY = 0.90   # 藝術家 mesh 對自身貼圖 IoU 低於此 → UV 解讀可疑,視為錯誤


def load_alpha(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"讀不到: {path}")
    if img.ndim == 3 and img.shape[2] == 4:
        a = img[:, :, 3]
    else:
        a = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return (a > 8).astype(np.uint8), img.shape[1], img.shape[0]


def raster(uvs, tris, W, H):
    px = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(px[t]).astype(np.int32), 1)
    return recon


def iou(a, b):
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def artist_attachment(sk, slot, name):
    skins = sk["skins"]
    att = {}
    if isinstance(skins, list):
        for s in skins:
            att.update(s.get("attachments", {}))
    else:
        att = skins.get("attachments", skins)
    a = att[slot][name]
    return (np.array(a["uvs"], float).reshape(-1, 2),
            np.array(a["triangles"], int).reshape(-1, 3),
            a.get("width"), a.get("height"))


def run_one(sk, atlas_path, name, tmp_dir, margin):
    reg = parse_atlas(atlas_path)[name]
    page = reg["page"]
    sub = extract(atlas_path, os.path.join(os.path.dirname(atlas_path), page), name)
    crop = os.path.join(tmp_dir, "_cmp_region.png")
    cv2.imwrite(crop, sub)
    mask, W, H = load_alpha(crop)

    a_uv, a_tri, aw, ah = artist_attachment(sk, name, name)
    art_recon = raster(a_uv, a_tri, W, H)
    art_iou = iou(art_recon, mask)
    if art_iou < ART_IOU_SANITY:
        raise SystemExit(f"[{name}] 藝術家 IoU={art_iou:.3f} < {ART_IOU_SANITY}"
                         f" — UV 解讀可疑,不出報告")

    m = gen_v2(crop, mode="auto")
    g_uv = np.array(m["uvs"], float).reshape(-1, 2)
    g_tri = np.array(m["triangles"], int).reshape(-1, 3)
    gen_recon = raster(g_uv, g_tri, W, H)
    gen_iou = iou(gen_recon, mask)

    return {
        "piece": name,
        "region": {"page": page, "rotate": reg.get("rotate"),
                   "atlas_size": reg["size"], "crop_wh": [W, H]},
        "artist_mesh": {"vertices": len(a_uv), "triangles": len(a_tri),
                        "logical_wh": [aw, ah], "iou_vs_alpha": round(art_iou, 4)},
        "generated_mesh": {"mode": m.get("_mode"), "vertices": len(m["uvs"]) // 2,
                           "hull": m["hull"], "triangles": len(m["triangles"]) // 3,
                           "iou_vs_alpha": round(gen_iou, 4)},
        "gen_vs_artist_shape_iou": round(iou(gen_recon, art_recon), 4),
        "iou_gap": round(gen_iou - art_iou, 4),
        "pass": gen_iou >= art_iou - margin,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--margin", type=float, default=0.03)
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    pieces = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]
    reports = [run_one(sk, a.atlas, p, a.tmp, a.margin) for p in pieces]
    overall = all(r["pass"] for r in reports)
    print(json.dumps({"reports": reports, "overall_pass": overall,
                      "margin": a.margin}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
