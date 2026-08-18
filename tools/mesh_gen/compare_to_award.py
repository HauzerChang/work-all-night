#!/usr/bin/env python3
"""端到端 AC:PSD 件 → S3 生成 mesh → 對照 Award「真實生產 mesh」。

背景(見 knowledge/s4-psd-to-spine-real.md):`robot_parts.psd` 5 圖層對應到真實 spine
`Award` 的 slot `機器人拆件/<圖層名>`;其中 光暈 / 身體 / 左手 三件在 Award 是 **mesh**
(右手/頭是 region)。這三件是「有藝術家真值 mesh 可比」的端到端驗收標的。

真值來源與 AC:
  1) 切件 alpha:由 `psd_slice.py` 從真實 PSD 切出的部位 PNG(alpha 即部位輪廓)。
  2) 藝術家 baseline:Award mesh 的 **region-local uvs**(本檔實測 Award mesh uvs 為
     region-local 0..1,非 atlas UV)還原多邊形對 alpha 的覆蓋 IoU。
  3) 生成 mesh:`generate_mesh_v2`(auto)對切件 alpha 生成;近方形件會自動回退 v1 Delaunay。
  AC 通過 = 生成 mesh 覆蓋 IoU ≥ 藝術家 baseline − margin,且 mesh 格式/自洽閘全過。

★ deform 閘:這三件在 Award **無 deform timeline**(靠 weighted bone 變形,非逐頂點 deform),
  故不套用 real_deform_field 轉移閘;此處只驗靜態覆蓋與拓樸格式(誠實標註)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate, load_mask

MESH_PARTS = {  # PSD 圖層名 -> psd_slice 輸出檔
    "光暈": "00_光暈.png",
    "身體": "03_身體.png",
    "左手": "04_左手.png",
}


def award_mesh(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[slot][name]


def artist_iou_regionlocal(a, alpha):
    """Award mesh 的 region-local uvs 還原到切件像素座標,量對 alpha 的覆蓋 IoU。"""
    H, W = alpha.shape
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, alpha).sum()
    union = np.logical_or(recon, alpha).sum()
    return float(inter / union) if union else 0.0


def compare_one(sk, slot, name, part_png, tmp_dir, iou_margin=0.02):
    img = cv2.imread(part_png, cv2.IMREAD_UNCHANGED)
    alpha = (img[:, :, 3] > 8).astype(np.uint8)

    mesh = gen_v2(part_png, mode="auto")
    ev = evaluate(mesh, alpha)              # 靜態覆蓋 + 格式/自洽閘
    my_iou = ev["criteria"]["AC1_iou"]["value"]

    a = award_mesh(sk, slot, name)
    base = artist_iou_regionlocal(a, alpha)
    aw_v = len(a["uvs"]) // 2

    fmt_ok = all(ev["criteria"][k]["pass"] for k in
                 ("AC4_format", "AC2b_degenerate", "AC2c_orphans", "AC3_vertex_budget"))
    iou_ok = my_iou >= base - iou_margin
    return {
        "part": name,
        "psd_alpha_px": [int(alpha.shape[1]), int(alpha.shape[0])],
        "generated": {"mode": mesh.get("_mode"), "vertices": len(mesh["uvs"]) // 2,
                      "hull": mesh["hull"], "triangles": len(mesh["triangles"]) // 3,
                      "iou_vs_alpha": round(my_iou, 4)},
        "award_artist": {"vertices": aw_v, "hull": a["hull"],
                         "triangles": len(a["triangles"]) // 3, "weighted": len(a["vertices"]) != len(a["uvs"]),
                         "iou_vs_alpha": round(base, 4)},
        "AC_coverage": {"pass": bool(iou_ok), "my": round(my_iou, 4),
                        "artist_baseline": round(base, 4), "margin": iou_margin},
        "AC_format": {"pass": bool(fmt_ok)},
        "overall_pass": bool(iou_ok and fmt_ok),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--parts_dir", default="/tmp/robot_parts")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    reps = []
    for zh, f in MESH_PARTS.items():
        slot = name = f"機器人拆件/{zh}"
        reps.append(compare_one(sk, slot, name, os.path.join(a.parts_dir, f), a.tmp, a.margin))
    out = {"parts": reps, "overall_pass": all(r["overall_pass"] for r in reps)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["overall_pass"] else 1)


if __name__ == "__main__":
    main()
