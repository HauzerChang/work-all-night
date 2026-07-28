#!/usr/bin/env python3
"""端到端驗收:PSD 切件 → S3 生成 mesh → 對照 Award 真實(藝術家)mesh。

這是 S3+S4 串接的整合閘:對「真實生產標的」(Award 機器人拆件的 3 個 mesh 件)
驗證我們的 mesh 生成器產出的輪廓覆蓋率是否 ≥ 藝術家手做基準。

流程(全 CPU,不需 Award.png):
  1. 從 robot_parts.psd 切出件的緊湊 alpha(piece-local 像素框)。
  2. 讀 Award.json 對應 slot 的藝術家 mesh(weighted);其 uvs 為 **region-local [0,1]**
     (Spine JSON 慣例:uvs 是相對 region 的區域座標,runtime 才映射到 atlas page),
     故 piece_pixel = (u*W, v*H),與 PSD 件同框,無需處理 atlas 旋轉/縮放。
  3. 光柵化藝術家三角 → 對 piece alpha 算 IoU = artist_baseline。
  4. generate_mesh_v2 對 piece alpha 生成 → evaluate_mesh 算 IoU + 格式/退化/孤兒 AC。
  5. 判定:生成 IoU ≥ artist_baseline − margin,且生成 mesh 自身 AC 全過。

⚠️ 映射自驗(evaluator-of-evaluator):藝術家 mesh 對自己的件 alpha 理應高度吻合。
   若 artist_baseline < MAP_SANITY 代表 uv→像素映射錯(例如 v 軸方向),閘會標記
   mapping_ok=False 並拒絕採信該件結果(避免又一次 miscalibration,見 knowledge)。

⚠️ deform 閘不適用:這 3 件在 Award **無 deform timeline**(靠骨骼/權重變形),
   故此閘只驗「靜態輪廓對藝術家真值」;逐頂點 deform 穩健性不在本閘範圍。
"""
import argparse, json, os, sys
import numpy as np
import cv2

sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_mesh

# 對應表:PSD 圖層名 → Award slot(= attachment name)
ROBOT_MESH_MAP = {
    "光暈": "機器人拆件/光暈",
    "身體": "機器人拆件/身體",
    "左手": "機器人拆件/左手",
}
MAP_SANITY = 0.80   # 藝術家 mesh 對自己件的 IoU 下限(低於此 → uv 映射有誤)
IOU_MARGIN = 0.03   # 生成 IoU 容許低於藝術家基準的幅度


def load_award_mesh(award_json, slot):
    sk = json.load(open(award_json))
    skin = sk["skins"][0] if isinstance(sk["skins"], list) else sk["skins"]
    att = skin.get("attachments", skin)
    name = list(att[slot])[0]
    return att[slot][name]


def raster_uv_mesh(uvs, tris, W, H, flip_v=False):
    """用 region-local uvs([0,1])光柵化三角填充,回傳 (H,W) 0/1 覆蓋圖。"""
    uv = np.array(uvs, np.float64).reshape(-1, 2)
    px = uv[:, 0] * W
    py = (1.0 - uv[:, 1]) * H if flip_v else uv[:, 1] * H
    pts = np.column_stack([px, py])
    canvas = np.zeros((H, W), np.uint8)
    T = np.array(tris, np.int32).reshape(-1, 3)
    for t in T:
        cv2.fillConvexPoly(canvas, np.round(pts[t]).astype(np.int32), 1)
    return canvas


def iou(a, b):
    inter = int(np.logical_and(a, b).sum())
    union = int(np.logical_or(a, b).sum())
    return inter / union if union else 0.0


def piece_masks(psd_path):
    """回傳 {圖層名: (alpha_mask uint8 0/1, W, H, rgba_png_path)}。"""
    _, manifest, parts = slice_psd(psd_path)
    out = {}
    for entry, im in parts:
        arr = np.array(im)  # RGBA
        alpha = (arr[..., 3] > 8).astype(np.uint8)
        out[entry["name"]] = (alpha, im.width, im.height, im)
    return out


def compare_piece(psd_layer, slot, mask, W, H, im, award_json, tmp_dir):
    # 藝術家 mesh(region-local uvs)
    art = load_award_mesh(award_json, slot)
    art_uvs, art_tris = art["uvs"], art["triangles"]
    # 映射自驗:試 v 不翻/翻,取吻合較高者;要求 ≥ MAP_SANITY
    art_no = raster_uv_mesh(art_uvs, art_tris, W, H, flip_v=False)
    art_fl = raster_uv_mesh(art_uvs, art_tris, W, H, flip_v=True)
    iou_no, iou_fl = iou(art_no, mask), iou(art_fl, mask)
    flip_v = iou_fl > iou_no
    art_iou = max(iou_no, iou_fl)
    mapping_ok = art_iou >= MAP_SANITY

    # 生成 mesh(存 piece PNG 給 generate 讀 alpha)
    crop = os.path.join(tmp_dir, f"_{psd_layer}.png")
    im.save(crop)
    gmesh = gen_v2(crop, mode="auto")
    # AC1 的 IoU 門檻對齊「藝術家基準 − margin」,不用武斷的 0.95
    # (與 validate_against_real.py 的校正一致:軟邊件連藝術家都 < 0.95)。
    art_bar = max(0.0, art_iou - IOU_MARGIN)
    gen_rep = eval_mesh(gmesh, mask, vertex_budget=128, iou_thresh=art_bar)
    gen_iou = gen_rep["criteria"]["AC1_iou"]["value"]

    passed = mapping_ok and gen_rep["overall_pass"]
    return {
        "piece": psd_layer, "slot": slot, "size": [W, H],
        "artist_mesh": {"vertices": len(art_uvs) // 2, "hull": art.get("hull"),
                        "triangles": len(art_tris) // 3, "weighted": True,
                        "iou_vs_piece": round(art_iou, 4), "v_flipped": bool(flip_v)},
        "mapping_ok": mapping_ok, "mapping_sanity_thresh": MAP_SANITY,
        "generated_mesh": {"mode": gmesh.get("_mode"), "vertices": gen_rep["vertices"],
                           "hull": gmesh["hull"], "triangles": gen_rep["triangles"],
                           "iou_vs_piece": round(gen_iou, 4),
                           "iou_bar_artist_rel": round(art_bar, 4),
                           "self_AC_pass": gen_rep["overall_pass"],
                           "self_AC": {k: v["pass"] for k, v in gen_rep["criteria"].items()}},
        "iou_margin": IOU_MARGIN,
        "iou_gap_vs_artist": round(gen_iou - art_iou, 4),
        "piece_pass": passed,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    masks = piece_masks(a.psd)
    reports = []
    for layer, slot in ROBOT_MESH_MAP.items():
        if layer not in masks:
            reports.append({"piece": layer, "error": "PSD 無此圖層"}); continue
        mask, W, H, im = masks[layer]
        reports.append(compare_piece(layer, slot, mask, W, H, im, a.award, a.tmp))
    overall = all(r.get("piece_pass") for r in reports)
    print(json.dumps({"overall_pass": overall, "pieces": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
