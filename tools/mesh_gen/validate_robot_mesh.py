#!/usr/bin/env python3
"""端到端驗收:PSD件/atlas件 → S3 生成 mesh → 對照 Award 真實藝術家 mesh。

與 validate_against_real.py 的差異:
- Award 的 3 個機器人 mesh 件(光暈/身體/左手)**無 deform timeline**(靠骨骼權重變形,
  非逐頂點 deform),故不能用該資產自身的 real_deform_field 當變形閘。
- 本工具改為:① 靜態 IoU 覆蓋率 vs **藝術家自身 mesh 基準**(同一 mask);
  ② 拓樸統計對照(頂點/hull/三角);③ 以 main_draw 窗簾的**真實位移場**做「跨資產變形壓力」
  (通用耐變形檢查,非本件的真值 — 明確標示)。

可信度前置:先量藝術家 mesh 自身的靜態 IoU(自一致性)與負對照,確認評估器在此新資產可信。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import cv2
from atlas_crop import extract
from evaluate_mesh import evaluate, load_mask
from generate_mesh_v2 import generate as gen_v2
import deform_eval as de

ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]


def artist_mesh(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)[slot][name]


def iou_from_uvs(uvs, tris, mask):
    """把 region-local uvs(0..1)映到 mask 並填三角,回傳 vs mask 的 IoU。"""
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0


def run(skeleton_path, atlas_path, png_path, tmp_dir):
    sk = json.load(open(skeleton_path))
    # 跨資產變形場(main_draw 窗簾真實 deform,通用耐變形壓力來源)
    md = json.load(open(os.path.join(os.path.dirname(skeleton_path), "main_draw.json")))
    uvs_src, field, sframe = de.real_deform_field(md, "image/curtain_left", "image/curtain_left")

    out = {"source_deform_field": {"from": "main_draw curtain_left", "frame": sframe,
                                   "max_disp": round(float(np.abs(field).max()), 1)},
           "pieces": []}
    for slot in ROBOT_MESHES:
        name = slot
        a = artist_mesh(sk, slot, name)
        auv = np.array(a["uvs"]).reshape(-1, 2)
        atri = np.array(a["triangles"]).reshape(-1, 3)

        sub = extract(atlas_path, png_path, name)
        crop = os.path.join(tmp_dir, "_robot_region.png")
        cv2.imwrite(crop, sub)
        mask = load_mask(crop)
        Hh, Ww = mask.shape

        # 藝術家 mesh 自一致性(基準)+ 負對照(打亂 uv → IoU 應崩)
        artist_baseline = iou_from_uvs(auv, atri, mask)
        rng = np.random.default_rng(0)
        neg = iou_from_uvs(rng.permutation(auv), atri, mask)

        # 生成 mesh(auto:方形件走 v1 Delaunay)
        mesh = gen_v2(crop, mode="auto")
        nv = len(mesh["uvs"]) // 2
        gen_iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]

        # 跨資產變形壓力
        dres = de.transfer_deform_check(mesh, uvs_src, field)

        out["pieces"].append({
            "slot": slot, "region_px": [int(Ww), int(Hh)],
            "artist": {"vertices": len(auv), "hull": int(a.get("hull", 0)),
                       "triangles": len(atri), "self_iou": round(artist_baseline, 4),
                       "neg_control_iou": round(neg, 4)},
            "generated": {"mode": mesh.get("_mode"), "vertices": nv, "hull": mesh["hull"],
                          "triangles": len(mesh["triangles"]) // 3, "iou": round(gen_iou, 4)},
            "iou_vs_artist": {"gen": round(gen_iou, 4), "artist": round(artist_baseline, 4),
                              "pass": gen_iou >= artist_baseline - 0.03},
            "cross_asset_deform_stress": {
                "area_ratio": dres["area_ratio"], "self_intersections": dres["self_intersections"],
                "triangle_flips": dres["triangle_flips"], "clean": dres["clean"]},
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    rep = run(a.skeleton, a.atlas, a.png, a.tmp)
    print(json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
