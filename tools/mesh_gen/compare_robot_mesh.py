#!/usr/bin/env python3
"""端到端驗收:atlas 件 → S3 generate_mesh_v2 → 對照 Award 真實藝術家 mesh。

首次以**真實生產藝術家 mesh** 當 ground truth 比對(先前只有 main_draw 窗簾)。
對 3 個機器人 mesh 件(光暈/身體/左手,Award 中為 weighted mesh)量化:
  - 輪廓 IoU(mesh 三角填滿 vs 件 alpha):生成 vs 藝術家
  - 頂點經濟度:生成 nv vs 藝術家 nv
  - 靜態幾何合法性(setup pose):self-intersections / degenerate(生成 vs 藝術家)
  - AC2/3/4 拓樸與格式(evaluate_mesh)

⚠️ Award 機器人 mesh **無 deform timeline**(靠骨骼/權重變形)→ 無真實位移場可轉移,
   故不含 AC5 真實 deform 轉移(誠實標註 N/A)。

跑法(於 repo 根目錄):python3 tools/mesh_gen/compare_robot_mesh.py
"""
import json, sys, os
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from atlas_crop import extract
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask as ev_load_mask
import deform_eval as de

PARTS = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SK = json.load(open(os.path.join(ROOT, "assets/Award.json")))
SKIN = SK["skins"][0]["attachments"]
TMP = os.path.join(ROOT, "scratchpad", "robot_crops")
os.makedirs(TMP, exist_ok=True)


def recon_from_uv(uvs, tris, H, W):
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return recon


def iou(a, b):
    return float(np.logical_and(a, b).sum() / max(1, np.logical_or(a, b).sum()))


def static_check(pts, tris):
    """setup pose 幾何合法性:signs 取自自身 → flips 恆 0,專測 self-intersections / degenerate。"""
    tris = np.asarray(tris).reshape(-1, 3)
    signs = [de.signed_area(pts, t) > 0 for t in tris]
    return de.check(pts, tris, signs)


def run():
    results = []
    for name in PARTS:
        sub = extract(os.path.join(ROOT, "assets/Award.atlas"),
                      os.path.join(ROOT, "assets/Award.png"), name)
        crop = os.path.join(TMP, name.split("/")[-1] + ".png")
        cv2.imwrite(crop, sub)
        mask = ev_load_mask(crop)
        H, W = mask.shape

        a = SKIN[name][name]
        a_uvs = np.array(a["uvs"]).reshape(-1, 2)
        a_tris = np.array(a["triangles"]).reshape(-1, 3)
        a_iou = iou(recon_from_uv(a_uvs, a_tris, H, W), mask)
        a_pts = np.column_stack([a_uvs[:, 0] * W, a_uvs[:, 1] * H])
        a_static = static_check(a_pts, a_tris)

        m = gen_v2(crop, mode="auto")
        ev = evaluate(m, mask)
        g_iou = ev["criteria"]["AC1_iou"]["value"]
        v = m["vertices"]
        g_pts = np.array([(v[i] + W / 2.0, H / 2.0 - v[i + 1]) for i in range(0, len(v), 2)])
        g_static = static_check(g_pts, np.array(m["triangles"]).reshape(-1, 3))
        g_nv = len(m["uvs"]) // 2

        results.append({
            "part": name, "crop": [W, H],
            "artist": {"nv": len(a_uvs), "tris": len(a_tris), "hull": a.get("hull"),
                       "iou": round(a_iou, 4), "self_intersections": a_static["self_intersections"],
                       "degenerate": a_static["degenerate"],
                       "weighted": len(a["vertices"]) != len(a["uvs"])},
            "generated": {"mode": m.get("_mode"), "nv": g_nv, "tris": len(m["triangles"]) // 3,
                          "hull": m["hull"], "iou": g_iou,
                          "self_intersections": g_static["self_intersections"],
                          "degenerate": g_static["degenerate"]},
            "delta": {"iou_gen_minus_artist": round(g_iou - a_iou, 4),
                      "nv_gen_minus_artist": g_nv - len(a_uvs)},
            "AC_all_pass": all(ev["criteria"][k]["pass"] for k in
                               ["AC2a_centroid_in_mask", "AC2b_degenerate", "AC2c_orphans",
                                "AC3_vertex_budget", "AC4_format"]),
        })
    return results


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
