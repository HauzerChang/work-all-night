#!/usr/bin/env python3
"""端到端「PSD件 → S3 mesh」對照 Award 真實藝術家 mesh(靜態覆蓋 + 拓樸)。

背景(見 knowledge/s4-psd-to-spine-real.md):robot_parts.psd 的 5 個圖層對應到
Award spine 的 slot `機器人拆件/<圖層名>`;其中 光暈/身體/左手 是 mesh(其餘為 region)。
這 3 個 Award mesh 是 **weighted(骨骼驅動)、無 deform timeline** → 本比對只做
**setup-pose 靜態覆蓋 IoU + 拓樸**,不做 deform(那需要 real_deform_field,這些件沒有)。

關鍵前提(本 session 校正 STATE 的過時假設):
  Spine JSON 的 mesh `uvs` 是 **region 局部 0..1**(runtime 才映射到 atlas page),
  main_draw 與 Award 皆然 → **不需 atlas UV 轉換**。artist_iou 直接 uv*(W,H) 即可。

alpha 來源:PSD 切件 PNG(邏輯原始解析度,與 attachment 邏輯尺寸差 +2px padding,
~0.3% 可忽略),對應「PSD→件→mesh」端到端故事。

AC:
  - 生成 mesh 的靜態 IoU ≥ 藝術家同件 mesh 的 IoU(以其自身 uvs 對同一 alpha 量)。
  - 生成 mesh 無退化/孤兒(evaluate_mesh 靜態閘)。
  - 頂點數在預算內(≤64,理想接近或優於藝術家精簡度作參考)。
"""
import json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from evaluate_mesh import evaluate
from generate_mesh_v2 import generate as gen_v2, load_mask  # 這版回傳 (mask{0,1}, W, H)


def artist_mesh(sk, slot):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)[slot]
    a = list(att.values())[0]
    return a


def mesh_iou_from_uvs(uvs, tris, mask):
    """以 region 局部 uvs(0..1)在 mask 尺寸上重建 mesh 覆蓋,回傳 IoU。"""
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0


def compare(part_png, sk, slot):
    mask01, W, H = load_mask(part_png)          # load_mask 回傳 (mask{0,1}, W, H)
    mask = mask01.astype(bool)

    # 生成 mesh(v2 auto)
    gm = gen_v2(part_png, mode="auto")
    guv = np.array(gm["uvs"]).reshape(-1, 2)
    gtri = np.array(gm["triangles"]).reshape(-1, 3)
    gen_iou = mesh_iou_from_uvs(guv, gtri, mask)
    gen_static = evaluate(gm, mask01)

    # 藝術家 mesh
    am = artist_mesh(sk, slot)
    auv = np.array(am["uvs"]).reshape(-1, 2)
    atri = np.array(am["triangles"]).reshape(-1, 3)
    art_iou = mesh_iou_from_uvs(auv, atri, mask)

    ac_static = gen_static["criteria"]
    return {
        "slot": slot,
        "alpha_source": os.path.basename(part_png),
        "alpha_size": [W, H],
        "generated": {
            "mode": gm.get("_mode"),
            "vertices": len(guv), "hull": gm["hull"], "triangles": len(gtri),
            "iou": round(gen_iou, 4),
        },
        "artist": {
            "weighted": len(am["vertices"]) != len(am["uvs"]),
            "vertices": len(auv), "hull": am["hull"], "triangles": len(atri),
            "iou": round(art_iou, 4),
        },
        "AC_coverage": {
            "gen_iou": round(gen_iou, 4), "artist_baseline": round(art_iou, 4),
            "pass": gen_iou >= art_iou,
        },
        "AC_static_clean": {
            "degenerate_tris": ac_static["AC2b_degenerate"]["value"],
            "orphan_verts": ac_static["AC2c_orphans"]["value"],
            "centroid_inside": round(ac_static["AC2a_centroid_in_mask"]["value"], 4),
            "pass": ac_static["AC2b_degenerate"]["pass"] and ac_static["AC2c_orphans"]["pass"]
                    and ac_static["AC2a_centroid_in_mask"]["pass"],
        },
        "AC_vertex_budget": {
            "gen": len(guv), "artist": len(auv), "budget": 64,
            "pass": len(guv) <= 64,
        },
    }


def main():
    sk = json.load(open("assets/Award.json"))
    jobs = [
        ("psd_parts/00_光暈.png", "機器人拆件/光暈"),
        ("psd_parts/03_身體.png", "機器人拆件/身體"),
        ("psd_parts/04_左手.png", "機器人拆件/左手"),
    ]
    # psd_parts/ 是 gitignore 的衍生物;缺就先切(fresh container 可自足)
    if not all(os.path.exists(p) for p, _ in jobs):
        import subprocess
        subprocess.run([sys.executable, os.path.join(os.path.dirname(__file__), "psd_slice.py"),
                        "assets/robot_parts.psd"], check=True, stdout=subprocess.DEVNULL)
    reps = []
    for png, slot in jobs:
        reps.append(compare(png, sk, slot))
    overall = all(r["AC_coverage"]["pass"] and r["AC_static_clean"]["pass"]
                  and r["AC_vertex_budget"]["pass"] for r in reps)
    out = {"overall_pass": overall, "parts": reps}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
