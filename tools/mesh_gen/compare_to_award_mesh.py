#!/usr/bin/env python3
"""端到端「PSD件 → S3 生成 mesh → 對照 Award 真實生產 mesh」驗收(有真值)。

背景(knowledge/s4-psd-to-spine-real.md):Award 的機器人 3 件(光暈/身體/左手)是真實
生產 mesh(**weighted**,靠骨骼權重變形,無逐頂點 deform timeline)。本工具用 PSD 切件
的 alpha 當來源,跑 S3 generate_mesh,與 Award 藝術家 mesh 做:
  ① 覆蓋率 IoU 對照(生成 vs 藝術家,對同一件 alpha)
  ② 拓樸統計(頂點/三角/hull 預算對照)
  ③ 靜態幾何品質閘(evaluate_mesh:重心在內/無退化/無孤兒/spine 格式)

⚠️ 為何不用逐頂點 deform 閘:這 3 件在 Award **無 deform timeline**(weighted,骨骼變形),
   real_deform_field 會回傳零場 → deform 閘 N/A。此處以「覆蓋率對照藝術家真值」為主軸。

座標對映(評估器可信度關鍵,2026-07-16 校正):Award 的 mesh uvs 是 **piece-local 正規化**
(0..1 直接對應該 attachment 的 width×height,已含 alpha 內的透明留白),**不是** atlas-page
座標,也**不可**依 mesh bbox 再正規化。驗證:身體 uv-x span=0.759 ≈ alpha_bbox_w/piece_w
=286/379=0.755、uv-y span=0.940 ≈ 403/425=0.948 → uvs 就是 piece-local。故直接 uv×(W,H)。
   踩過的坑:先前「依 mesh bbox 正規化」對 uv 未填滿件的身體施加各向異性拉伸 → 自覆蓋率
   假性掉到 0.64;「當 atlas-page 座標」則身體落在別處 IoU=0。改直接映射後 3 件自覆蓋率
   0.948/0.948/0.977(全 ≥0.85 可信)。

自校驗:此映射下藝術家 mesh 覆蓋自己的 alpha 應 ≥ ~0.85(covers own artwork),否則映射有誤。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from evaluate_mesh import evaluate, load_mask
import deform_eval as de


def raster_mesh(uvs, tris, W, H):
    """把 (uvs Nx2 in [0,1]-local, tris) 填三角成 mask。"""
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return recon


def iou(a, b):
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def artist_mesh_local(skeleton, slot, name):
    """回傳藝術家 mesh 的 (uvs Nx2 piece-local[0,1], tris, stats)。uvs 直接對應 attachment WH,不再正規化。"""
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uvs = np.array(a["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(a["triangles"], dtype=np.int32).reshape(-1, 3)
    nv = len(uvs)
    weighted = len(a["vertices"]) != 2 * nv
    return uvs, tris, {"vertices": nv, "triangles": len(tris), "hull": a["hull"],
                       "weighted": weighted, "wh": [a.get("width"), a.get("height")]}


def compare(skeleton_path, piece_png, slot, name, gen_fn, iou_margin=0.02):
    sk = json.load(open(skeleton_path))
    mask = load_mask(piece_png)
    H, W = mask.shape

    # ① 藝術家 mesh 覆蓋率(自校驗:應 ≥ ~0.9)
    a_uv, a_tris, a_stats = artist_mesh_local(sk, slot, name)
    artist_recon = raster_mesh(a_uv, a_tris, W, H)
    artist_iou = iou(artist_recon, mask)

    # ② 生成 mesh
    mesh = gen_fn(piece_png)
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    g_uv = np.array(mesh["uvs"], dtype=np.float64).reshape(-1, 2)
    g_tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    gen_recon = raster_mesh(g_uv, g_tris, W, H)
    gen_iou = iou(gen_recon, mask)

    # ③ 靜態幾何品質閘 —— 只取「幾何有效性」條目為 pass/fail。
    # 排除 evaluate() 內建的絕對 AC1_iou(門檻 0.95)因為:(a) 覆蓋率已由 AC_coverage_parity
    # 對「藝術家真值」判定(比武斷的 0.95 更對);(b) 0.95 對軟邊件(光暈,藝術家自身僅 0.949)
    # miscalibrated,會假性失敗。幾何有效性條目才是靜態閘該把關的。
    ev = evaluate(mesh, mask)
    geom_keys = ["AC4_format", "AC2a_centroid_in_mask", "AC2b_degenerate",
                 "AC2c_orphans", "AC3_vertex_budget"]
    static_pass = all(ev["criteria"][k]["pass"] for k in geom_keys)

    # deform:這些件無真實 deform timeline → 報告為 N/A(不當 pass/fail)
    _, field, frame = de.real_deform_field(sk, slot, name)
    has_real_deform = frame is not None

    coverage_pass = gen_iou >= artist_iou - iou_margin
    mapping_trustworthy = artist_iou >= 0.85

    return {
        "piece": name,
        "artist": {**a_stats, "self_coverage_iou": round(artist_iou, 4),
                   "mapping_trustworthy": mapping_trustworthy},
        "generated": {"mode": mesh.get("_mode"), "vertices": len(g_uv),
                      "triangles": len(g_tris), "hull": mesh["hull"],
                      "coverage_iou": round(gen_iou, 4)},
        "AC_coverage_parity": {"gen_iou": round(gen_iou, 4),
                               "artist_baseline": round(artist_iou, 4),
                               "margin": iou_margin, "pass": coverage_pass},
        "AC_static_quality": {"pass": static_pass,
                              "detail": {k: v["value"] if "value" in v else v.get("pass")
                                         for k, v in ev["criteria"].items()}},
        "AC_deform": {"applicable": has_real_deform,
                      "note": "Award 此件無 deform timeline(weighted 骨骼變形)→ 逐頂點 deform 閘 N/A"},
        "overall_pass": bool(mapping_trustworthy and coverage_pass and static_pass),
    }


PIECES = [
    ("機器人拆件/光暈", "00_光暈.png"),
    ("機器人拆件/身體", "03_身體.png"),
    ("機器人拆件/左手", "04_左手.png"),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--parts-dir", default="/tmp/robot_parts")
    ap.add_argument("--gen", choices=["v1", "v2"], default="v1")
    a = ap.parse_args()
    if a.gen == "v1":
        from generate_mesh import generate as g
        gen = lambda p: g(p)
    else:
        from generate_mesh_v2 import generate as g
        gen = lambda p: g(p, mode="auto")

    results = []
    for slot, fn in PIECES:
        png = os.path.join(a.parts_dir, fn)
        results.append(compare(a.skeleton, png, slot, slot, gen))
    overall = all(r["overall_pass"] for r in results)
    print(json.dumps({"gen": a.gen, "overall_pass": overall, "pieces": results},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
