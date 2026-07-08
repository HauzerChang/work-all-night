#!/usr/bin/env python3
"""端到端驗收:PSD件 → S3 mesh → 對照 Award 真實生產 mesh(機器人拆件)。

背景(見 knowledge/s4-psd-to-spine-real.md、STATE.md 下一步 #1):
Award(big win spine)有 3 個 mesh 件對應機器人拆件 PSD 圖層 —— 光暈/身體/左手。
本工具把這 3 件的真實 alpha(從 Award atlas 切出,已 CW derotate + 0.70 縮放)
餵給 S3 `generate_mesh_v2`,再與 **Award 藝術家真實 mesh** 逐項對照:

  ① 覆蓋率 IoU：生成 mesh 對件 alpha 的 IoU ≥ 藝術家 mesh 對同一 alpha 的 IoU − margin。
  ② 拓樸有效:evaluate_mesh 全過(format/centroid/退化/孤兒/頂點預算)。
  ③ 精簡度:生成頂點數與藝術家同量級(≤ 藝術家 nv 或 ≤ 預算)。

⚠️ **deform 閘 N/A**:這 3 件在 Award 是 **weighted mesh(靠骨骼權重變形)且無 deform timeline**
   (len(vertices)!=len(uvs);見 s4-psd-to-spine-real.md)。S3 目前只產 unweighted 幾何、
   BBW 權重尚未實作,且無逐頂點位移場可轉移 → 誠實標記 N/A,不套未校準的合成壓力
   (RULES:別用未校準 stress_field)。本 chunk 只驗「靜態幾何/覆蓋率/精簡度」對真實標的的對齊。

對照 main_draw(4 個 unweighted + 有 deform 的 mesh,由 validate_against_real.py 負責變形閘),
本工具補上「跨資產、weighted、無 deform」情境的靜態端到端驗收。
"""
import argparse, json, os, sys, tempfile
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate as eval_mesh
import generate_mesh_v2 as gv2

# 機器人拆件在 Award 的 3 個 mesh 件(slot==attachment name)
ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]


def crop_mask(atlas, png, name):
    sub = extract(atlas, png, name)
    if sub.ndim == 3 and sub.shape[2] == 4:
        alpha = sub[:, :, 3]
    else:
        g = sub if sub.ndim == 2 else cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
        alpha = (g > 0).astype(np.uint8) * 255
    return (alpha > 8).astype(np.uint8), sub


def poly_iou(uvs, tris, mask):
    """把 mesh(region-local uv 0..1)填成覆蓋圖,與件 alpha 算 IoU。"""
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = int(np.logical_and(recon, mask).sum())
    union = int(np.logical_or(recon, mask).sum())
    return (inter / union) if union else 0.0


def artist_mesh(sk, slot):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    a = att[slot][slot]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    nv = len(uvs)
    weighted = len(a["vertices"]) != len(a["uvs"])
    return uvs, tris, nv, int(a.get("hull", 0)), weighted


def gen_pixel_uv(mesh):
    """generate_mesh 的 uvs 已是件內 0..1(以 crop W,H 正規化),直接可用。"""
    return np.array(mesh["uvs"]).reshape(-1, 2), np.array(mesh["triangles"]).reshape(-1, 3)


def validate_one(sk, atlas, png, slot, iou_margin=0.03):
    mask, sub = crop_mask(atlas, png, slot)
    H, W = mask.shape
    fd, tmp = tempfile.mkstemp(suffix="_award_region.png"); os.close(fd)
    cv2.imwrite(tmp, sub)

    a_uvs, a_tris, a_nv, a_hull, weighted = artist_mesh(sk, slot)
    base_iou = poly_iou(a_uvs, a_tris, mask)

    mesh = gv2.generate(tmp, mode="auto")
    os.unlink(tmp)
    g_uvs, g_tris = gen_pixel_uv(mesh)
    g_nv = len(g_uvs)
    gen_iou = poly_iou(g_uvs, g_tris, mask)

    # 頂點預算對齊「藝術家為同尺寸件實際使用的量級」(這 3 件藝術家用 78~98,
    # 遠高於小窗簾用的固定 64;對大件沿用 64 會錯判精簡度)。
    budget = max(a_nv, 64)
    em = eval_mesh(mesh, mask, vertex_budget=budget)

    ac_iou = gen_iou >= base_iou - iou_margin
    ac_topo = em["overall_pass"]
    ac_budget = g_nv <= budget

    return {
        "slot": slot, "crop": [W, H],
        "artist": {"vertices": a_nv, "hull": a_hull, "triangles": len(a_tris),
                   "weighted": weighted, "self_iou": round(base_iou, 4)},
        "generated": {"mode": mesh.get("_mode"), "vertices": g_nv, "hull": mesh["hull"],
                      "triangles": len(g_tris), "iou": round(gen_iou, 4)},
        "AC_coverage": {"pass": bool(ac_iou), "gen_iou": round(gen_iou, 4),
                        "artist_baseline": round(base_iou, 4), "margin": iou_margin},
        "AC_topology": {"pass": bool(ac_topo),
                        "criteria": {k: v["pass"] for k, v in em["criteria"].items()}},
        "AC_budget": {"pass": bool(ac_budget), "gen_nv": g_nv, "artist_nv": a_nv, "budget": budget},
        "deform_gate": "N/A (weighted mesh + no deform timeline in Award; BBW weights not yet in S3)",
        "overall_pass": bool(ac_iou and ac_topo and ac_budget),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--margin", type=float, default=0.03)
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reports = [validate_one(sk, a.atlas, a.png, slot, a.margin) for slot in ROBOT_MESHES]
    allpass = all(r["overall_pass"] for r in reports)
    print(json.dumps({"overall_pass": allpass, "meshes": reports},
                     ensure_ascii=False, indent=2))
    raise SystemExit(0 if allpass else 1)


if __name__ == "__main__":
    main()
