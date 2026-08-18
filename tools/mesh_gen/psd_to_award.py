#!/usr/bin/env python3
"""端到端閘:PSD 切件 → S3 mesh v2 → 對照真實生產 Spine(Award)的 mesh。

驗收「PSD→件→mesh」這條下游 pipeline 對**真實生產標的**是否夠好:
  1) 從 `robot_parts.psd` 切出目標圖層(tight-crop,原圖解析度、原始朝向)。
  2) `generate_mesh_v2` 生成拓樸 → 覆蓋率 IoU(vs 該件 alpha)。
  3) 對照 Award 中對應 slot 的**藝術家真實 mesh**(名稱慣例 `機器人拆件/<圖層名>`):
     - 覆蓋率基準:artist_iou 對**同一份 PSD mask**(原圖朝向,與 spine uvs 同框;
       經 §驗證:光暈/身體(atlas 內 rotate)與左手(不 rotate)artist_iou 皆 0.95+)。
     - 頂點預算 / hull / 三角數 對照。
  overall_pass:生成 IoU >= 藝術家覆蓋率基準 - margin。

⚠️ 重要發現(2026-08-18):Award 的 3 個機器人 mesh 皆為 **weighted 且靠 bone 驅動,
   無 deform timeline**。故 deform-transfer 閘(real_deform_field/transfer_deform_check,
   針對 per-vertex deform)對它們 **N/A**;骨驅變形的耐受度需 BBW 權重(S3 未建)+ bone
   動畫取樣 才能量化,列為後續。本閘只做「靜態覆蓋 + 拓樸預算」對照。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from PIL import Image
from psd_slice import slice_psd
from evaluate_mesh import evaluate, load_mask
from generate_mesh_v2 import generate as gen_v2
from validate_against_real import artist_iou


def artist_mesh_stats(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    nv = len(a["uvs"]) // 2
    weighted = len(a["vertices"]) != len(a["uvs"])
    return {"vertices": nv, "hull": a["hull"], "triangles": len(a["triangles"]) // 3,
            "weighted": weighted}


def find_layer_png(psd_path, layer_name, out_png):
    _, _, parts = slice_psd(psd_path)
    for entry, im in parts:
        if entry["name"] == layer_name:
            im.save(out_png)          # RGBA,已 tight-crop 到該層 bbox
            return entry
    raise KeyError(f"layer {layer_name!r} not found in {psd_path}")


def validate(psd_path, layer_name, skeleton_path, slot, name, tmp_dir, iou_margin=0.02):
    os.makedirs(tmp_dir, exist_ok=True)
    png = os.path.join(tmp_dir, "_psd_piece.png")
    entry = find_layer_png(psd_path, layer_name, png)
    mask = load_mask(png)

    mesh = gen_v2(png, mode="auto")
    if isinstance(mesh, tuple):
        mesh = mesh[0]

    gen_iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]
    sk = json.load(open(skeleton_path))
    base = artist_iou(sk, slot, name, mask)
    astat = artist_mesh_stats(sk, slot, name)

    gen_nv = len(mesh["uvs"]) // 2
    return {
        "layer": layer_name, "psd": os.path.basename(psd_path),
        "target_slot": slot, "target_attachment": name, "psd_piece_size": entry["size"],
        "generated_mesh": {"vertices": gen_nv, "hull": mesh["hull"],
                           "triangles": len(mesh["triangles"]) // 3, "mode": mesh.get("_mode")},
        "artist_mesh": astat,
        "AC_coverage": {"generated_iou": round(gen_iou, 4),
                        "artist_baseline": round(base, 4),
                        "pass": gen_iou >= base - iou_margin},
        "overall_pass": gen_iou >= base - iou_margin,
    }


# PSD 圖層名 → (slot, attachment) 慣例:機器人拆件/<圖層名>
ROBOT_MESHES = ["光暈", "左手", "身體"]  # Award 中為 mesh 的 3 件(右手/頭為 region)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--layers", nargs="*", default=ROBOT_MESHES,
                    help="PSD 圖層名(對應 slot 機器人拆件/<名>)")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()

    reports = []
    for ly in a.layers:
        slot = name = f"機器人拆件/{ly}"
        rep = validate(a.psd, ly, a.skeleton, slot, name, a.tmp)
        reports.append(rep)
    summary = {"reports": reports,
               "all_pass": all(r["overall_pass"] for r in reports)}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(0 if summary["all_pass"] else 1)


if __name__ == "__main__":
    main()
