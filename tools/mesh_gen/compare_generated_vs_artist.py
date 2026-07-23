#!/usr/bin/env python3
"""端到端驗收:PSD 切件 → S3 generate_mesh_v2 → 對照「真實生產 spine」的藝術家 mesh。

背景(見 knowledge/s4-psd-to-spine-real.md):機器人拆件 PSD 的 3 個 mesh 件(光暈/身體/左手)
在生產 spine `Award` 裡是**加權(weighted)mesh、無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform)。
因此此處的可檢查真相是**靜態覆蓋 IoU 與藝術家 mesh 的對等性** + setup 拓樸乾淨度,
而**不是** deform 穩健度(無 ground-truth deform 場可轉移,不硬套 → 保持誠實)。

流程:
  對每個 mesh 件:
    ① 用 psd_slice 切出該件緊湊 PNG(alpha mask 來源)。
    ② generate_mesh_v2(auto) 生成 mesh → evaluate_mesh 量化(IoU/format/degenerate/orphan)。
    ③ 從 Award.json 讀藝術家 mesh 的 region-local uvs+triangles,柵格化進同一件框架
       (自動判 y 翻轉:取兩方向中 IoU 較高者為藝術家基準)。
    ④ 判定:my_iou >= artist_iou - margin(覆蓋率對等)且 my mesh 拓樸乾淨。
       另報頂點經濟性(my_v vs artist_v)供參考。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2, load_mask
from evaluate_mesh import evaluate as eval_mesh
from psd_slice import slice_psd


def _iou(a, b):
    inter = int(np.logical_and(a, b).sum())
    union = int(np.logical_or(a, b).sum())
    return inter / union if union else 0.0


def artist_mesh(award, slot):
    skins = award["skins"]
    if isinstance(skins, list):
        att = skins[0]["attachments"]
    else:
        att = skins.get("attachments", skins)
    a = att[slot]
    name = list(a.keys())[0]
    m = a[name]
    uvs = np.array(m["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(m["triangles"], dtype=np.int32).reshape(-1, 3)
    return uvs, tris, {"vertices": len(uvs), "triangles": len(tris),
                       "hull": m["hull"], "weighted": len(m["vertices"]) != len(m["uvs"])}


def rasterize_uv(uvs, tris, W, H, flip_y):
    rp = np.column_stack([uvs[:, 0] * W, (1.0 - uvs[:, 1]) * H if flip_y else uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return recon


def mesh_recon(mesh, W, H):
    """generate 輸出的 vertices(y 上翻+置中)→ 像素座標柵格化。"""
    v = mesh["vertices"]
    pts = np.array([(v[i] + W / 2.0, H / 2.0 - v[i + 1]) for i in range(0, len(v), 2)])
    tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    return recon


def compare_piece(piece_png, award, slot, margin, budget):
    mask, W, H = load_mask(piece_png)

    mesh = gen_v2(piece_png, mode="auto")
    ev = eval_mesh(mesh, mask, vertex_budget=budget)
    my_recon = mesh_recon(mesh, W, H)
    my_iou = _iou(my_recon, mask)

    uvs, tris, ainfo = artist_mesh(award, slot)
    a_no = rasterize_uv(uvs, tris, W, H, flip_y=False)
    a_fl = rasterize_uv(uvs, tris, W, H, flip_y=True)
    iou_no, iou_fl = _iou(a_no, mask), _iou(a_fl, mask)
    flip = iou_fl > iou_no
    artist_iou = max(iou_no, iou_fl)

    topo_clean = (ev["criteria"]["AC4_format"]["pass"]
                  and ev["criteria"]["AC2b_degenerate"]["pass"]
                  and ev["criteria"]["AC2c_orphans"]["pass"])
    cover_ok = my_iou >= artist_iou - margin

    return {
        "slot": slot, "piece_size": [W, H],
        "generated": {"mode": mesh.get("_mode"), "vertices": ev["vertices"],
                      "triangles": ev["triangles"], "hull": mesh["hull"],
                      "iou_vs_alpha": round(my_iou, 4), "topo_clean": topo_clean,
                      "format_pass": ev["criteria"]["AC4_format"]["pass"],
                      "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                      "orphans": ev["criteria"]["AC2c_orphans"]["value"]},
        "artist": {**ainfo, "iou_vs_alpha": round(artist_iou, 4), "uv_flip_y": flip},
        "AC_coverage_parity": {"my_iou": round(my_iou, 4),
                               "artist_baseline": round(artist_iou, 4),
                               "margin": margin, "pass": cover_ok},
        "vertex_economy": {"generated": ev["vertices"], "artist": ainfo["vertices"],
                           "ratio": round(ev["vertices"] / ainfo["vertices"], 3)},
        "piece_pass": bool(cover_ok and topo_clean),
    }


PIECES = [("光暈", "機器人拆件/光暈"), ("身體", "機器人拆件/身體"), ("左手", "機器人拆件/左手")]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--tmp", default="/tmp/robot_pieces")
    ap.add_argument("--margin", type=float, default=0.03,
                    help="覆蓋率對等容差(my_iou 允許低於藝術家基準的量)")
    ap.add_argument("--budget", type=int, default=128,
                    help="頂點預算(藝術家 mesh 最高 98v,故放寬 > 主 draw 的 64)")
    a = ap.parse_args()

    award = json.load(open(a.award))
    os.makedirs(a.tmp, exist_ok=True)
    _, _, parts = slice_psd(a.psd, a.tmp)
    layer_to_file = {}
    for entry, _ in parts:
        layer_to_file[entry["name"]] = os.path.join(a.tmp, entry["file"])

    reports = []
    for layer, slot in PIECES:
        png = layer_to_file[layer]
        reports.append(compare_piece(png, award, slot, a.margin, a.budget))

    overall = all(r["piece_pass"] for r in reports)
    print(json.dumps({"overall_pass": overall, "pieces": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
