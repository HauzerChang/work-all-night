#!/usr/bin/env python3
"""端到端 AC:PSD 件 → S3 mesh 生成器 → 對照 Award 真實藝術家 mesh。

這是 S3+S4 的端到端整合驗收(STATE 候選 #1,對真實生產標的、純 CPU 可自驅):
  robot_parts.psd 的 3 個 mesh 件(光暈/左手/身體,在生產 spine `Award` 中為 mesh)
  → psd_slice 取全解析度 alpha
  → generate_mesh_v2 生成 mesh
  → ① IoU vs 件 alpha  ② 拓樸閘(orphan/退化/hull/預算)  ③ 對照 Award 藝術家 mesh 覆蓋率基準

驗收邏輯(對齊 validate_against_real 的「對齊藝術家」哲學):
  生成 mesh 的 IoU 應 ≥ 藝術家 mesh 對同一件 alpha 的 IoU 基準(margin 容差)。
  藝術家 mesh 為 ground truth 品質標竿,不用武斷的絕對閾值。

⚠️ deform 閘 N/A:這 3 件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform),
  故此處只做靜態幾何/覆蓋率對照。deform 穩健性已於 main_draw 4 mesh(有 deform)驗證。

Award mesh uvs 為 region-local(0..1),已實測:對 PSD 件 alpha 直接 uv×(W,H) 得高 IoU
  (光暈 0.949 / 左手 0.977 / 身體 0.948),故沿用 region-local 解讀。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from evaluate_mesh import evaluate
import generate_mesh_v2 as g2

# PSD 圖層名 → Award slot(ground truth 對應,見 knowledge/s4-psd-to-spine-real.md)
MESH_PIECES = ["光暈", "左手", "身體"]
SLOT_FMT = "機器人拆件/{}"


def artist_iou(a, mask):
    """Award 藝術家 mesh(region-local uvs)對件 alpha 的覆蓋率 IoU。"""
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    return float(np.logical_and(recon, m).sum() / np.logical_or(recon, m).sum())


def artist_stats(a):
    nv = len(a["uvs"]) // 2
    return {"vertices": nv, "hull": int(a["hull"]),
            "triangles": len(a["triangles"]) // 3,
            "weighted": len(a["vertices"]) != len(a["uvs"])}


def validate(psd_path, award_path, tmp_dir, iou_margin=0.02, vertex_budget=96):
    psd, manifest, parts = slice_psd(psd_path)
    by_name = {e["name"]: (e, im) for e, im in parts}
    sk = json.load(open(award_path))
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    os.makedirs(tmp_dir, exist_ok=True)

    pieces = []
    for layer in MESH_PIECES:
        e, im = by_name[layer]
        arr = np.array(im.convert("RGBA"))
        crop = os.path.join(tmp_dir, f"_piece_{e['z']:02d}.png")
        cv2.imwrite(crop, cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA))
        mask = (arr[:, :, 3] > 8).astype(np.uint8)

        mesh = g2.generate(crop, mode="auto")
        ev = evaluate(mesh, mask, vertex_budget=vertex_budget)
        gen_iou = ev["criteria"]["AC1_iou"]["value"]

        a = atts[SLOT_FMT.format(layer)][SLOT_FMT.format(layer)]
        base = artist_iou(a, mask)
        art = artist_stats(a)

        topo_ok = (ev["criteria"]["AC2b_degenerate"]["pass"]
                   and ev["criteria"]["AC2c_orphans"]["pass"]
                   and ev["criteria"]["AC4_format"]["pass"]
                   and ev["criteria"]["AC3_vertex_budget"]["pass"])
        cov_ok = gen_iou >= base - iou_margin

        pieces.append({
            "piece": layer, "slot": SLOT_FMT.format(layer),
            "gen": {"mode": mesh.get("_mode"), "vertices": ev["vertices"],
                    "hull": ev["hull"], "triangles": ev["triangles"], "iou": gen_iou},
            "artist": {**art, "iou": round(base, 4)},
            "AC_a_coverage_parity": {"gen_iou": gen_iou, "artist_baseline": round(base, 4),
                                     "margin": iou_margin, "pass": cov_ok},
            "AC_b_topology": {"pass": topo_ok,
                              "degenerate": ev["criteria"]["AC2b_degenerate"]["value"],
                              "orphans": ev["criteria"]["AC2c_orphans"]["value"],
                              "vertex_budget": ev["criteria"]["AC3_vertex_budget"]},
            "AC_deform": "N/A (no deform timeline in Award; bone/weight driven)",
            "piece_pass": cov_ok and topo_ok,
        })

    overall = all(p["piece_pass"] for p in pieces)
    return {"source_psd": os.path.basename(psd_path),
            "award": os.path.basename(award_path),
            "pieces": pieces, "overall_pass": overall}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--tmp", default="/tmp/psd2award")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    rep = validate(a.psd, a.award, a.tmp, iou_margin=a.margin)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
