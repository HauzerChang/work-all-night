#!/usr/bin/env python3
"""端到端 S4→S3 對真實生產標的驗收:PSD 分層件 → 生成 mesh → 對照真實 spine artist mesh。

流程(純 CPU,無需 atlas 貼圖):
  robot_parts.psd 的可動件(光暈/左手/身體 在 Award 中是 mesh)
  → psd_slice 切成緊湊 PNG(alpha 即遮罩)
  → generate_mesh_v2 產生 mesh
  → 對照 Award.json 的 artist mesh:
       ① 靜態 IoU(生成 vs 件 alpha) >= artist 自身覆蓋率 baseline
       ② 頂點預算 / 拓樸模式
       ③ deform 閘:僅對「unweighted + 有 deform timeline」的件適用;
          weighted(骨綁)mesh 由骨權變形,本閘 N/A(需 S3 BBW 權重生成器,尚未建)。

真值來源:Award.json 的 artist mesh(uvs/triangles)。此為 S4(切件)+ S3(生成 mesh)
端到端對「真實生產 mesh」的對照,不再只用合成 fixture。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from evaluate_mesh import evaluate, load_mask
from generate_mesh_v2 import generate as gen_v2
import deform_eval as de


def award_mesh(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    weighted = len(a["vertices"]) != len(a["uvs"])
    return a, weighted


def raster_iou(uvs, tris, mask):
    """把一組 uvs(0..1)+triangles rasterize 到 mask 尺寸,回 IoU vs mask。"""
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return float(np.logical_and(recon, mask).sum() / max(np.logical_or(recon, mask).sum(), 1))


def validate_piece(sk, slot, name, piece_png, tmp_dir):
    mask = load_mask(piece_png)
    a, weighted = award_mesh(sk, slot, name)

    # artist baseline 覆蓋率
    art_uvs = np.array(a["uvs"]).reshape(-1, 2)
    art_tris = np.array(a["triangles"]).reshape(-1, 3)
    art_iou = raster_iou(art_uvs, art_tris, mask)

    # 生成 mesh
    mesh = gen_v2(piece_png, mode="auto")
    nv = len(mesh["uvs"]) // 2
    gen_iou = evaluate(mesh, mask)["criteria"]["AC1_iou"]["value"]

    # deform 閘:只有 unweighted + 有 deform timeline 才適用
    _, field, frame = de.real_deform_field(sk, slot, name)
    has_deform = frame is not None and float(np.abs(field).sum()) > 0
    deform_res = None
    if has_deform and not weighted:
        uvs_src, fld, fr = de.real_deform_field(sk, slot, name)
        d = de.transfer_deform_check(mesh, uvs_src, fld)
        deform_res = {"frame": fr, "self_intersections": d["self_intersections"],
                      "triangle_flips": d["triangle_flips"], "pass": d["clean"]}

    return {
        "slot": slot,
        "artist": {"nv": len(art_uvs), "tris": len(art_tris), "hull": a["hull"],
                   "weighted": weighted, "iou_baseline": round(art_iou, 4)},
        "generated": {"nv": nv, "tris": len(mesh["triangles"]) // 3, "hull": mesh["hull"],
                      "mode": mesh.get("_mode"), "iou": round(gen_iou, 4)},
        "AC_iou": {"pass": gen_iou >= art_iou, "gen": round(gen_iou, 4),
                   "baseline": round(art_iou, 4)},
        "deform_gate": deform_res if deform_res else
            ("N/A (weighted mesh — 需 BBW 權重生成器)" if weighted else "N/A (無 deform timeline)"),
    }


PIECES = [  # PSD layer name -> Award slot/name(皆同名)
    ("光暈", "機器人拆件/光暈"),
    ("左手", "機器人拆件/左手"),
    ("身體", "機器人拆件/身體"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--out", default="/tmp/robot_pieces")
    a = ap.parse_args()

    sk = json.load(open(a.skeleton))
    _, manifest, parts = slice_psd(a.psd, a.out)
    by_name = {}
    for entry, _ in parts:
        by_name[entry["name"]] = os.path.join(a.out, entry["file"])

    reports = []
    for layer, slot in PIECES:
        png = by_name.get(layer)
        if png is None:
            reports.append({"slot": slot, "error": f"PSD 無圖層 {layer}"})
            continue
        reports.append(validate_piece(sk, slot, slot, png, a.out))

    overall = all(r.get("AC_iou", {}).get("pass") for r in reports if "AC_iou" in r)
    out = {"overall_iou_pass": overall, "pieces": reports}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
