#!/usr/bin/env python3
"""端到端 AC:PSD 件 → S3 mesh → 對照真實生產 spine(Award)的藝術家 mesh。

情境(見 knowledge/s4-psd-to-spine-real.md):機器人拆件 big win 的 3 個件在 Award 中是 mesh
(光暈 78v / 身體 98v / 左手 80v,皆 **weighted**、**無 deform timeline** → 靠骨骼權重變形,
非逐頂點 deform)。因此本 AC 的真值是「藝術家手做 mesh 的輪廓覆蓋率(IoU)與精簡度」,
而非 deform 耐受(那對這些件不適用,已於報告標明)。

流程:
  psd_slice 切件 → 各件 alpha → generate_mesh_v2(auto) → 三項量化 AC:
    AC1 coverage:生成 mesh IoU(vs 件 alpha)>= 藝術家 Award mesh IoU − margin
    AC2 topology:0 退化 / 0 孤兒 / 三角重心全在 mask(evaluate_mesh)
    AC3 budget  :生成頂點數 <= 藝術家頂點數(不比藝術家更費)

UV 對齊已驗證:Award mesh uvs 為 region-local,"as-is" 直接對 PSD 件 alpha IoU 0.95~0.98
(4 種翻轉變體中唯一高者)→ 座標系一致,無需翻轉。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_mesh, load_mask as eval_load_mask


ROBOT_MESHES = {  # PSD 圖層名 -> (Award slot, part png 檔名)
    "光暈": ("機器人拆件/光暈", "00_光暈.png"),
    "身體": ("機器人拆件/身體", "03_身體.png"),
    "左手": ("機器人拆件/左手", "04_左手.png"),
}


def award_attachment(sk, slot):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    return atts[slot][slot]


def iou_uvs_mask(uvs, tris, mask):
    """把 (region-local uvs, triangles) 填成 raster 與 alpha mask 比 IoU。"""
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    return float(np.logical_and(recon, m).sum() / max(int(np.logical_or(recon, m).sum()), 1))


def has_deform(sk, slot, name):
    for anim in sk.get("animations", {}).values():
        for _, slots in (anim.get("deform") or {}).items():
            if slot in slots and name in slots[slot]:
                return True
    return False


def validate_one(sk, part_png, slot, name, iou_margin=0.02):
    a = award_attachment(sk, slot)
    art_uvs = np.array(a["uvs"]).reshape(-1, 2)
    art_tris = np.array(a["triangles"]).reshape(-1, 3)
    art_nv = len(art_uvs)

    mask_full = cv2.imread(part_png, cv2.IMREAD_UNCHANGED)
    mask = (mask_full[:, :, 3] > 8).astype(np.uint8)

    art_iou = iou_uvs_mask(art_uvs, art_tris, mask)

    mesh = gen_v2(part_png, mode="auto")
    ev = eval_mesh(mesh, eval_load_mask(part_png), vertex_budget=art_nv)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]
    gen_nv = ev["vertices"]

    ac1 = gen_iou >= art_iou - iou_margin
    ac2 = (ev["criteria"]["AC2b_degenerate"]["pass"]
           and ev["criteria"]["AC2c_orphans"]["pass"]
           and ev["criteria"]["AC2a_centroid_in_mask"]["pass"])
    ac3 = gen_nv <= art_nv
    return {
        "part": name, "slot": slot, "mode": mesh.get("_mode"),
        "has_deform_timeline": has_deform(sk, slot, name),
        "AC1_coverage": {"gen_iou": round(gen_iou, 4), "artist_iou": round(art_iou, 4),
                         "margin": iou_margin, "pass": bool(ac1)},
        "AC2_topology": {"degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                         "orphans": ev["criteria"]["AC2c_orphans"]["value"],
                         "centroid_in_mask": ev["criteria"]["AC2a_centroid_in_mask"]["value"],
                         "pass": bool(ac2)},
        "AC3_budget": {"gen_vertices": gen_nv, "artist_vertices": art_nv,
                       "gen_triangles": ev["triangles"], "artist_triangles": len(art_tris),
                       "pass": bool(ac3)},
        "overall_pass": bool(ac1 and ac2 and ac3),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--parts-dir", default="/tmp/robot_parts")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    sk = json.load(open(a.award))
    reports = []
    for name, (slot, png) in ROBOT_MESHES.items():
        reports.append(validate_one(sk, os.path.join(a.parts_dir, png), slot, name, a.margin))
    out = {"reports": reports, "all_pass": all(r["overall_pass"] for r in reports)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["all_pass"] else 1)


if __name__ == "__main__":
    main()
