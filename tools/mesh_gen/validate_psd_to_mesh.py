#!/usr/bin/env python3
"""端到端 S4→S3 對真實生產標的驗收:PSD 件 → generate_mesh_v2 → 對照 Award 真實 mesh。

情境(見 knowledge/s4-psd-to-spine-real.md):機器人 big win 的生產 spine `Award` 有 5 個
`機器人拆件/<圖層名>` slot,一對一對應 `robot_parts.psd` 的 5 圖層。其中 3 件是 **mesh**
(光暈/身體/左手),另 2 件 region(右手/頭)。本工具對 3 個 mesh 件跑「PSD 切件 → S3 生成 mesh」,
與 Award 藝術家 mesh 做**靜態幾何**對照,取得端到端保真度量。

⚠️ 與 main_draw 的差異(誠實記錄):
  - Award 的機器人 mesh 是 **weighted(骨骼驅動)、無 deform timeline**。
    → 因此**不能**跑 `deform_eval.transfer_deform_check`(沒有真實位移場可轉移)。
      骨骼旋轉下的耐受度是另一個 regime,不在本 chunk 範圍。
  - 本 chunk 的 AC 只涵蓋**靜態**:覆蓋率 IoU、頂點預算、setup 自交/退化/format。

AC(可機讀、對藝術家真值):
  AC1 覆蓋率 IoU:生成 mesh 在 PSD 件 alpha 上的 IoU >= 藝術家 mesh 基準 - margin。
      (藝術家基準同時在 PSD alpha 與 atlas region alpha 兩個 frame 上量,透明呈現)
  AC2 頂點預算:生成頂點數 <= 藝術家頂點數(效率不劣於藝術家)。
  AC3 setup 幾何:生成 mesh 在 setup pose 下 0 自交 / 0 翻面 / 0 退化。
  AC4 format:unweighted 格式合法(hull-first、索引合法),見 evaluate_mesh AC4。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_mesh
import deform_eval as de
from atlas_crop import extract as atlas_extract

# PSD 圖層名 → Award slot(= attachment name)
PART_MAP = {
    "光暈": "機器人拆件/光暈",
    "身體": "機器人拆件/身體",
    "左手": "機器人拆件/左手",
}


def artist_mesh(skeleton, slot):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][slot]
    return a


def coverage_iou(uvs, tris, mask):
    """把 mesh(uvs 正規化 [0,1] + triangles)填到 mask 尺寸,回傳與 mask 的 IoU。"""
    H, W = mask.shape
    uvs = np.asarray(uvs).reshape(-1, 2)
    tris = np.asarray(tris).reshape(-1, 3)
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    inter = int(np.logical_and(recon, m).sum())
    union = int(np.logical_or(recon, m).sum())
    return inter / union if union else 0.0


def alpha_of(im_rgba):
    a = np.asarray(im_rgba)
    if a.ndim == 3 and a.shape[2] == 4:
        return (a[:, :, 3] > 8).astype(np.uint8)
    g = a if a.ndim == 2 else cv2.cvtColor(a, cv2.COLOR_RGB2GRAY)
    return (g > 8).astype(np.uint8)


def validate_part(psd_parts, layer_name, skeleton, atlas_path, png_path,
                  tmp_dir, iou_margin=0.02, budget=96):
    slot = PART_MAP[layer_name]
    # --- PSD 件 alpha + 存暫存 PNG 供生成器讀 ---
    entry_im = next(((e, im) for e, im in psd_parts if e["name"] == layer_name), None)
    if entry_im is None:
        raise SystemExit(f"PSD 找不到圖層: {layer_name}")
    entry, im = entry_im
    part_png = os.path.join(tmp_dir, f"_psd_{layer_name}.png")
    im.save(part_png)
    psd_mask = alpha_of(im)

    # --- 生成 mesh(v2 auto) ---
    mesh = gen_v2(part_png, mode="auto")
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    nv = len(mesh["uvs"]) // 2

    # --- AC1 覆蓋率 IoU ---
    gen_iou = eval_mesh(mesh, psd_mask, vertex_budget=budget)["criteria"]["AC1_iou"]["value"]
    art = artist_mesh(skeleton, slot)
    art_nv = len(art["uvs"]) // 2
    art_iou_on_psd = coverage_iou(art["uvs"], art["triangles"], psd_mask)
    # 藝術家在自身 atlas region frame 的 IoU(原生基準)
    sub = atlas_extract(atlas_path, png_path, slot)
    atlas_mask = alpha_of(cv2.cvtColor(sub, cv2.COLOR_BGRA2RGBA) if sub.ndim == 3 and sub.shape[2] == 4 else sub)
    art_iou_on_atlas = coverage_iou(art["uvs"], art["triangles"], atlas_mask)

    baseline = art_iou_on_psd  # 同 frame 直接可比
    ac1 = gen_iou >= baseline - iou_margin

    # --- AC3 setup 幾何(生成 mesh 在 rest 下自交/翻面/退化) ---
    v = mesh["vertices"]
    s = np.column_stack([v[0::2], v[1::2]])
    tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    signs = [de.signed_area(s, t) > 0 for t in tris]
    chk = de.check(s, tris, signs)
    ac3 = chk["self_intersections"] == 0 and chk["triangle_flips"] == 0 and chk["degenerate"] == 0

    # --- AC4 format ---
    fmt = eval_mesh(mesh, psd_mask, vertex_budget=budget)["criteria"]["AC4_format"]["pass"]

    ac2 = nv <= art_nv
    return {
        "layer": layer_name, "slot": slot, "gen_mode": mesh.get("_mode"),
        "AC1_iou": {"gen_iou_on_psd": round(gen_iou, 4),
                    "artist_iou_on_psd": round(art_iou_on_psd, 4),
                    "artist_iou_on_atlas": round(art_iou_on_atlas, 4),
                    "margin": iou_margin, "pass": bool(ac1)},
        "AC2_vertex_budget": {"gen_nv": nv, "artist_nv": art_nv, "pass": bool(ac2)},
        "AC3_setup_geom": {**chk, "pass": bool(ac3)},
        "AC4_format": {"pass": bool(fmt)},
        "overall_pass": bool(ac1 and ac2 and ac3 and fmt),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--layers", nargs="*", default=list(PART_MAP))
    a = ap.parse_args()
    _, _, parts = slice_psd(a.psd)
    sk = json.load(open(a.skeleton))
    reps = [validate_part(parts, ly, sk, a.atlas, a.png, a.tmp) for ly in a.layers]
    overall = all(r["overall_pass"] for r in reps)
    out = {"target": os.path.basename(a.psd), "vs": os.path.basename(a.skeleton),
           "overall_pass": overall, "parts": reps}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
