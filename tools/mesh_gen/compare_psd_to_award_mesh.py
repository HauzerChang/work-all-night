#!/usr/bin/env python3
"""端到端 S3+S4 對照:PSD 件 → generate_mesh_v2 → 對照 Award 真實生產 mesh。

背景(STATE / log 2026-06-26-005,006):robot_parts.psd 的 5 圖層 ⇄ Award spine
slot `機器人拆件/<圖層名>` 一對一;其中 光暈/身體/左手 在 Award 中為 **weighted mesh**
(藝術家手做)。本工具把「PSD 切件 → 我方 S3 生成 mesh」與「藝術家真實 mesh」放在
**同一張 PSD 件 alpha 剪影**上量化對照:

  · gen_iou     = 我方生成 mesh 三角形填充 vs 件 alpha 的 IoU
  · artist_iou  = 藝術家 mesh(setup uvs+triangles)填充 vs 同一件 alpha 的 IoU
                  (= 可信度校準:藝術家 mesh 對自己的剪影應該高覆蓋;若偏低代表
                   PSD 件 frame 與 Award region-local uv frame 有旋轉/翻面錯位,
                   此時對照不可信,須改用 atlas 抽取的 region 當遮罩)

AC(對真實生產標的):
  1. 校準:artist_iou ≥ ART_MIN(否則 frame 錯位,判定 UNTRUSTED 而非 pass/fail)
  2. 覆蓋率:gen_iou ≥ artist_iou − MARGIN(我方 mesh 覆蓋不遜於藝術家)
  3. 靜態幾何乾淨:evaluate() 的 AC2/AC4(無退化三角/孤兒/格式正確)
  4. 頂點預算:生成頂點數 ≤ 藝術家頂點數(精簡度不超過真值,寬鬆上限用 evaluate 的 budget)

deform 閘不適用:此 5 件在 Award 無 deform timeline(靠骨骼動,log 005),
故只驗靜態剪影覆蓋 + 幾何乾淨。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from evaluate_mesh import evaluate
from generate_mesh_v2 import generate as gen_v2

ART_MIN = 0.80   # 藝術家 mesh 對自身剪影的最低合理覆蓋(低於此 => frame 錯位)
MARGIN = 0.03    # 覆蓋率容差


def load_alpha(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"讀不到: {path}")
    if img.ndim == 3 and img.shape[2] == 4:
        a = img[:, :, 3]
    else:
        g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        a = g
    return (a > 8).astype(np.uint8)


def award_mesh(skeleton, slot, name):
    sk = skeleton["skins"]; sk = sk[0] if isinstance(sk, list) else sk
    return sk.get("attachments", sk)[slot][name]


def rasterize_uv_mesh(uvs, tris, H, W):
    """把 (region-local 0..1 uvs, triangles) 填成 HxW 剪影。"""
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return recon


def iou(a, b):
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def compare_one(piece_png, skeleton, slot, name):
    mask = load_alpha(piece_png)
    H, W = mask.shape

    # 藝術家真實 mesh(校準基準)
    a = award_mesh(skeleton, slot, name)
    a_uv = np.array(a["uvs"]).reshape(-1, 2)
    a_tri = np.array(a["triangles"]).reshape(-1, 3)
    a_nv = len(a_uv)
    a_recon = rasterize_uv_mesh(a_uv, a_tri, H, W)
    artist_iou = iou(a_recon, mask)

    # 我方生成 mesh(S3 v2)
    gen = gen_v2(piece_png, mode="auto")
    if isinstance(gen, tuple):
        gen = gen[0]
    ev = evaluate(gen, mask)
    gen_iou = ev["criteria"]["AC1_iou"]["value"]
    gen_nv = ev["vertices"]

    trusted = artist_iou >= ART_MIN
    geom_clean = all(ev["criteria"][k]["pass"]
                     for k in ("AC2a_centroid_in_mask", "AC2b_degenerate",
                               "AC2c_orphans", "AC4_format"))
    coverage_ok = gen_iou >= artist_iou - MARGIN
    budget_ok = gen_nv <= a_nv  # 生成不超過藝術家頂點數(精簡)

    return {
        "piece": os.path.basename(piece_png),
        "slot": slot,
        "artist": {"vertices": a_nv, "triangles": len(a_tri),
                   "hull": a.get("hull"), "weighted": len(a["vertices"]) != len(a["uvs"]),
                   "self_iou": round(artist_iou, 4)},
        "generated": {"vertices": gen_nv, "triangles": ev["triangles"],
                      "hull": gen["hull"], "mode": gen.get("_mode"),
                      "iou": round(gen_iou, 4)},
        "AC1_calibration_trusted": {"pass": trusted, "artist_self_iou": round(artist_iou, 4),
                                    "min": ART_MIN},
        "AC2_coverage": {"pass": coverage_ok, "gen_iou": round(gen_iou, 4),
                         "artist_iou": round(artist_iou, 4), "margin": MARGIN},
        "AC3_geometry_clean": {"pass": geom_clean,
                               "detail": {k: ev["criteria"][k]["pass"] for k in
                                          ("AC2a_centroid_in_mask", "AC2b_degenerate",
                                           "AC2c_orphans", "AC4_format")}},
        "AC4_vertex_budget": {"pass": budget_ok, "gen": gen_nv, "artist": a_nv},
        "overall_pass": trusted and coverage_ok and geom_clean and budget_ok,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--parts_dir", required=True, help="psd_slice 輸出目錄")
    ap.add_argument("--skeleton", default="assets/Award.json")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    manifest = json.load(open(os.path.join(a.parts_dir, "manifest.json")))
    # PSD 圖層名 -> Award mesh slot(僅 mesh 件)
    mesh_slots = {}
    skins = sk["skins"]; skins = skins[0] if isinstance(skins, list) else skins
    for slot, atts in skins.get("attachments", skins).items():
        for an, ad in atts.items():
            if ad.get("type") == "mesh":
                mesh_slots[an] = slot

    reports = []
    for p in manifest["parts"]:
        slot_name = f"機器人拆件/{p['name']}"
        if slot_name in mesh_slots:
            png = os.path.join(a.parts_dir, p["file"])
            reports.append(compare_one(png, sk, slot_name, slot_name))

    overall = all(r["overall_pass"] for r in reports) and len(reports) > 0
    out = {"overall_pass": overall, "n_mesh_pieces": len(reports), "reports": reports}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
