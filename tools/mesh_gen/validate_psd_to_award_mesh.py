#!/usr/bin/env python3
"""端到端 AC:PSD 件 → S3 mesh v2 → 對照 Award 真實藝術家 mesh(靜態覆蓋率真值)。

背景:先前 S3 v2 只在 main_draw 的 4 個 *unweighted* mesh(窗簾/陰影)上驗過。
Award 的機器人 3 件(光暈/左手/身體)在生產 spine 是 *weighted* mesh,形狀也和窗簾
截然不同(blobby,非高瘦條狀)→ 是 S3 「泛化到真實生產標的」的硬考。

本檔驗兩條互補路徑,對每個部位:
  (P) PSD 路徑:從 robot_parts.psd 圖層取 alpha → generate_mesh_v2 → evaluate_mesh
      (格式閘 + 覆蓋率 IoU)。證明「PSD→件→mesh」端到端純 CPU 可跑、產物合法。
  (A) 真值對照:同一部位在 Award atlas 的 region alpha 上,
      generate_mesh_v2 的覆蓋率 IoU  vs  藝術家 mesh 的覆蓋率 IoU(artist_iou,同一 mask,
      apples-to-apples)。過關 = 生成 mesh 覆蓋 ≥ 藝術家覆蓋 − margin。

⚠️ deform 閘在此**刻意不做**:Award mesh 為 weighted,deform timeline 的 vertices 是
   逐權重項偏移(非逐頂點),現行 deform_eval 的 real_deform_field 假設 unweighted,
   無法在不重建 skinning 的前提下取真實位移場。列為 open item(見輸出 note)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate
from atlas_crop import extract
from validate_against_real import artist_iou

# (PSD 圖層名, Award slot, Award attachment 名, atlas region 名)
PARTS = [
    ("光暈", "機器人拆件/光暈", "機器人拆件/光暈", "機器人拆件/光暈"),
    ("左手", "機器人拆件/左手", "機器人拆件/左手", "機器人拆件/左手"),
    ("身體", "機器人拆件/身體", "機器人拆件/身體", "機器人拆件/身體"),
]


def psd_layer_alpha(psd_path, layer_name):
    from psd_tools import PSDImage
    psd = PSDImage.open(psd_path)
    for l in psd.descendants():
        if l.is_group() or not l.is_visible():
            continue
        if l.name == layer_name:
            img = l.composite()  # 緊湊 bbox 的 PIL 影像
            arr = np.array(img)
            if arr.ndim == 3 and arr.shape[2] == 4:
                bgra = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA)
            else:
                g = arr if arr.ndim == 2 else cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
                a = (g > 0).astype(np.uint8) * 255
                bgra = cv2.merge([g, g, g, a]) if arr.ndim == 2 else \
                    np.dstack([cv2.cvtColor(arr, cv2.COLOR_RGB2BGR), a])
            return bgra
    raise SystemExit(f"PSD 找不到圖層: {layer_name}")


def coverage_iou(mesh, mask):
    """把 mesh 三角形填滿,對 alpha mask 算 IoU(evaluate_mesh 的 AC1)。"""
    return evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")  # 多頁時 atlas_crop 自動選 page
    ap.add_argument("--tmp", default="/tmp/claude-0/-home-user-work-all-night/"
                                     "d08475f8-c4b0-5752-9778-129e019274cc/scratchpad")
    ap.add_argument("--iou_margin", type=float, default=0.03)
    a = ap.parse_args()
    os.makedirs(a.tmp, exist_ok=True)
    sk = json.load(open(a.skeleton))

    report = {"parts": {}, "note_deform_gate":
              "Award mesh 為 weighted;現行 deform_eval 假設 unweighted 逐頂點 offset,"
              "無法取真實位移場 → deform 閘刻意跳過(open item)。此檔僅靜態覆蓋率。"}
    all_pass = True

    for psd_layer, slot, name, region in PARTS:
        entry = {}

        # ---- (P) PSD 路徑 ----
        bgra = psd_layer_alpha(a.psd, psd_layer)
        p_crop = os.path.join(a.tmp, f"_psd_{psd_layer}.png")
        cv2.imwrite(p_crop, bgra)
        psd_mask = (bgra[:, :, 3] > 8).astype(np.uint8)
        mesh_psd = gen_v2(p_crop, mode="auto")
        ev_psd = evaluate(mesh_psd, psd_mask)
        entry["psd_path"] = {
            "src_size": [int(bgra.shape[1]), int(bgra.shape[0])],
            "mode": mesh_psd.get("_mode"),
            "vertices": ev_psd["vertices"], "triangles": ev_psd["triangles"],
            "hull": ev_psd["hull"],
            "format_pass": ev_psd["criteria"]["AC4_format"]["pass"],
            "no_orphans": ev_psd["criteria"]["AC2c_orphans"]["pass"],
            "no_degenerate": ev_psd["criteria"]["AC2b_degenerate"]["pass"],
            "iou": ev_psd["criteria"]["AC1_iou"]["value"],
        }
        psd_valid = (ev_psd["criteria"]["AC4_format"]["pass"]
                     and ev_psd["criteria"]["AC2c_orphans"]["pass"]
                     and ev_psd["criteria"]["AC2b_degenerate"]["pass"])

        # ---- (A) 真值對照(同一 atlas region mask,apples-to-apples)----
        sub = extract(a.atlas, a.png, region)   # BGRA
        r_crop = os.path.join(a.tmp, f"_region_{psd_layer}.png")
        cv2.imwrite(r_crop, sub)
        reg_mask = (sub[:, :, 3] > 8).astype(np.uint8) if sub.shape[2] == 4 \
            else (cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY) > 8).astype(np.uint8)
        mesh_reg = gen_v2(r_crop, mode="auto")
        gen_iou = coverage_iou(mesh_reg, reg_mask)
        art_iou = artist_iou(sk, slot, name, reg_mask)
        beats = gen_iou >= art_iou - a.iou_margin
        entry["ground_truth"] = {
            "region_size": [int(sub.shape[1]), int(sub.shape[0])],
            "gen_mode": mesh_reg.get("_mode"),
            "gen_vertices": len(mesh_reg["uvs"]) // 2,
            "gen_iou": round(gen_iou, 4),
            "artist_iou": round(art_iou, 4),
            "artist_vertices": len(sk_uv(sk, slot, name)) // 2,
            "gen_ge_artist_minus_margin": beats,
            "margin": a.iou_margin,
        }

        entry["part_pass"] = psd_valid and beats
        all_pass = all_pass and entry["part_pass"]
        report["parts"][psd_layer] = entry

    report["overall_pass"] = all_pass
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if all_pass else 1)


def sk_uv(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)[slot][name]["uvs"]


if __name__ == "__main__":
    main()
