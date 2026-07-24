#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 mesh → 對照 Award 真實生產 mesh(有真值)。

背景(見 knowledge/s4-psd-to-spine-real.md):robot_parts.psd 的 5 圖層一對一對應
Award spine 的 slot `機器人拆件/<圖層名>`。其中 3 件在 Award 是 **weighted mesh**
(光暈 78v/身體 98v/左手 80v);另 2 件(右手/頭)是 region,略過。

這 3 個 mesh 在 Award **沒有 deform timeline**(靠骨骼擺放,非 deform warp)——
所以「真實位移場轉移」閘不適用;本閘以 **靜態輪廓覆蓋 IoU** 為主,真值 = 藝術家 mesh。

兩種比對(都自我驗證、純 CPU):
  A) 同幀嚴謹比對:生成 mesh 與藝術家 mesh **在同一張影像**(atlas region)上覆蓋 IoU
     直接對打 → 消除尺度歧義。AC:gen_IoU_atlas >= artist_baseline - margin。
  B) 端到端來源比對:對 **PSD 切件** 本身生成 mesh,量其 IoU → 證明「PSD 來源」
     產出的 mesh 與 atlas 來源同等保真(PSD↔atlas 同素材前置已於 s4 驗:alpha-IoU 0.92~0.99)。

另報告頂點效率:生成頂點數 vs 藝術家頂點數(生成器目標是精簡且達標)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract
from evaluate_mesh import evaluate as eval_mesh, load_mask as load_mask_bin
from generate_mesh_v2 import generate as gen_v2

PARTS = [
    # (slot/attachment name, PSD 切件檔)
    ("機器人拆件/光暈", "00_光暈.png"),
    ("機器人拆件/身體", "03_身體.png"),
    ("機器人拆件/左手", "04_左手.png"),
]


def artist_coverage(skeleton, name, mask):
    """藝術家 mesh 對其自身 alpha mask 的覆蓋 IoU(真值基準)。weighted 也適用(用 uvs)。"""
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    a = att[name][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    inter = int(np.logical_and(recon, m).sum())
    union = int(np.logical_or(recon, m).sum())
    return (inter / union) if union else 0.0, len(uvs)


def gen_iou(mesh, mask):
    return eval_mesh(mesh, mask)["criteria"]["AC1_iou"]["value"]


def run(skeleton_path, atlas_path, png_dir, psd_parts_dir, tmp_dir, margin):
    sk = json.load(open(skeleton_path))
    os.makedirs(tmp_dir, exist_ok=True)
    rows = []
    for name, psd_file in PARTS:
        # --- A) atlas region(藝術家 mesh 定義所在的同一張影像) ---
        sub = extract(atlas_path, None, name)          # 自動選 page
        atlas_crop = os.path.join(tmp_dir, "_atlas.png")
        cv2.imwrite(atlas_crop, sub)
        atlas_mask = load_mask_bin(atlas_crop)
        base_iou, artist_nv = artist_coverage(sk, name, atlas_mask)
        mesh_atlas = gen_v2(atlas_crop, mode="auto")
        iou_atlas = gen_iou(mesh_atlas, atlas_mask)
        ev_atlas = eval_mesh(mesh_atlas, atlas_mask, iou_thresh=base_iou - margin)

        # --- B) PSD 切件(端到端來源) ---
        psd_path = os.path.join(psd_parts_dir, psd_file)
        psd_mask = load_mask_bin(psd_path)
        mesh_psd = gen_v2(psd_path, mode="auto")
        iou_psd = gen_iou(mesh_psd, psd_mask)

        gen_nv = len(mesh_atlas["uvs"]) // 2
        rows.append({
            "part": name,
            "artist": {"vertices": artist_nv, "coverage_iou": round(base_iou, 4)},
            "A_atlas_source": {
                "gen_mode": mesh_atlas.get("_mode"), "gen_vertices": gen_nv,
                "gen_iou": round(iou_atlas, 4),
                "pass_vs_artist": iou_atlas >= base_iou - margin,
                "format_ok": ev_atlas["criteria"]["AC4_format"]["pass"],
                "degenerate": ev_atlas["criteria"]["AC2b_degenerate"]["value"],
                "orphans": ev_atlas["criteria"]["AC2c_orphans"]["value"],
            },
            "B_psd_source": {
                "gen_mode": mesh_psd.get("_mode"),
                "gen_vertices": len(mesh_psd["uvs"]) // 2,
                "gen_iou": round(iou_psd, 4),
                # PSD 來源自我保真:與 atlas 來源同等(不落後藝術家基準)
                "pass_self": iou_psd >= base_iou - margin,
            },
            "vertex_efficiency": round(gen_nv / artist_nv, 3),
        })
    overall = all(r["A_atlas_source"]["pass_vs_artist"]
                  and r["A_atlas_source"]["format_ok"]
                  and r["B_psd_source"]["pass_self"] for r in rows)
    return {"overall_pass": overall, "margin": margin,
            "note": "3 件在 Award 皆 weighted mesh 且無 deform timeline → 靜態 IoU 閘;deform 閘 N/A",
            "parts": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--psd_parts", default="scratch_robot_parts")
    ap.add_argument("--tmp", default="/tmp/psd2mesh")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    rep = run(a.skeleton, a.atlas, None, a.psd_parts, a.tmp, a.margin)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
