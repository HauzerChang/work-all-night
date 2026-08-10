#!/usr/bin/env python3
"""端到端 PSD件→S3 mesh→對照 Award 真實 mesh 的靜態覆蓋率 IoU 驗收。

- 來源:robot_parts.psd 切件(PSD piece alpha),而非 atlas → 走完整 PSD 契約路徑。
- 對照:Award.json 中對應 slot 的真實(藝術家)mesh 覆蓋率。
- AC:生成 mesh 覆蓋率 IoU >= 藝術家 mesh 覆蓋率 IoU - margin(用同一 alpha mask 量)。
- deform 閘:Award 這些件無 deform timeline(骨/權重驅動),故 per-vertex deform 閘 N/A;
  改報 mesh 格式有效性 + v2 auto 選到的拓樸模式。
"""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import cv2
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_mesh
from psd_slice import slice_psd

AWARD = json.load(open("assets/Award.json"))
PARTS_DIR = "/tmp/robot_parts"
# 若切件不存在,自動從 PSD 切(端到端:PSD→件→mesh 一鍵可重現)。
if not os.path.exists(os.path.join(PARTS_DIR, "00_光暈.png")):
    slice_psd("assets/robot_parts.psd", PARTS_DIR)

# PSD 圖層 → (PSD piece file, Award slot, Award attachment name)
MAP = {
    "光暈": ("00_光暈.png", "機器人拆件/光暈", "機器人拆件/光暈"),
    "身體": ("03_身體.png", "機器人拆件/身體", "機器人拆件/身體"),
    "左手": ("04_左手.png", "機器人拆件/左手", "機器人拆件/左手"),
}


def mask_from_png(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    return (img[:, :, 3] > 8).astype(np.uint8)


def coverage_iou_from_uvs(uvs, tris, mask):
    """把 (region-local uvs, tris) 填成多邊形,與 mask 求 IoU。"""
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0


def artist_mesh(slot, name):
    skins = AWARD["skins"]; skin = skins[0] if isinstance(skins, list) else skins
    a = skin.get("attachments", skin)[slot][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    return uvs, tris, a.get("hull"), len(uvs)


report = {}
for layer, (fn, slot, name) in MAP.items():
    path = os.path.join(PARTS_DIR, fn)
    mask = mask_from_png(path)

    mesh = gen_v2(path, mode="auto")
    nv = len(mesh["uvs"]) // 2
    gen_uvs = np.array(mesh["uvs"]).reshape(-1, 2)
    gen_tris = np.array(mesh["triangles"]).reshape(-1, 3)
    gen_iou = coverage_iou_from_uvs(gen_uvs, gen_tris, mask)

    # 生成 mesh 的格式與退化/孤兒閘
    ev = eval_mesh(mesh, mask, vertex_budget=128)

    a_uvs, a_tris, a_hull, a_nv = artist_mesh(slot, name)
    base_iou = coverage_iou_from_uvs(a_uvs, a_tris, mask)

    margin = 0.02
    report[layer] = {
        "psd_piece": fn, "mask_size": [int(mask.shape[1]), int(mask.shape[0])],
        "gen": {"mode": mesh.get("_mode"), "vertices": nv, "hull": mesh["hull"],
                "triangles": len(gen_tris), "coverage_iou": round(gen_iou, 4),
                "format_pass": ev["criteria"]["AC4_format"]["pass"],
                "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                "orphans": ev["criteria"]["AC2c_orphans"]["value"]},
        "artist_award": {"vertices": a_nv, "hull": a_hull, "triangles": len(a_tris),
                         "coverage_iou": round(base_iou, 4)},
        "AC_iou_pass": bool(gen_iou >= base_iou - margin),
        "iou_delta": round(gen_iou - base_iou, 4),
    }

print(json.dumps(report, ensure_ascii=False, indent=2))
allpass = all(r["AC_iou_pass"] and r["gen"]["format_pass"] and r["gen"]["degenerate"] == 0
              and r["gen"]["orphans"] == 0 for r in report.values())
print("\nOVERALL_PASS =", allpass)
sys.exit(0 if allpass else 1)
