#!/usr/bin/env python3
"""端到端「PSD→件→mesh」對真實生產 mesh(Award)驗收 —— 有 ground truth 的整合 AC。

背景:S3 之前只對 main_draw 的 4 個 **unweighted strip mesh**(窗簾/陰影)驗過。Award 的
機器人拆件提供另一類真值:**weighted、blobby(近方形)的生產 mesh**(光暈/身體/左手)。
本工具把這三件當 ground truth,量化我們生成器與藝術家的差距。

對齊基礎(已驗,2026-06-27):
  - Award mesh uvs 為 **region-local [0,1]**(相對原始未旋轉件),非 atlas page 全域。
  - `atlas_crop.extract`(CW derotate)還原上正件;藝術家 mesh 以 uvs×(W,H) 填回該件,
    對三件 alpha-IoU 0.968~0.980 → 確認比對座標系一致、extract 方向正確。

比對(同一張 atlas crop alpha,同座標系):
  - 藝術家 mesh 覆蓋 IoU = AC1 的門檻(bar)。
  - 生成 mesh(generate_mesh_v2.generate,auto 模式)→ evaluate_mesh.evaluate。
  - 因三件在 Award 為剛體(無 deform timeline,靠骨骼),**無真實位移場** → 變形閘不適用,
    僅報靜態 AC(依 AC.md:不要用未校準的 stress_field 當 pass/fail)。

注意:這三件為 weighted mesh;本比對只比 **幾何/拓樸/覆蓋**(權重屬 S5 骨架,未做)。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from atlas_crop import extract
from evaluate_mesh import evaluate
from generate_mesh_v2 import generate as gen_v2

# Award 的 3 個 mesh 件 → 所在 atlas page(雙頁)。attachment 名 == slot 名。
PARTS = {
    "機器人拆件/光暈": "Award2.png",
    "機器人拆件/身體": "Award2.png",
    "機器人拆件/左手": "Award.png",
}


def skin_atts(d):
    sk = d["skins"]
    sk = sk[0] if isinstance(sk, list) else sk
    return sk.get("attachments", sk)


def fill_mesh(uvs, tris, W, H):
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return recon


def iou(a, b):
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def compare(skeleton_path, atlas_path, asset_dir, tmp_dir, vertex_budget=64):
    sk = json.load(open(skeleton_path))
    atts = skin_atts(sk)
    os.makedirs(tmp_dir, exist_ok=True)
    rows = []
    for slot, page in PARTS.items():
        av = atts[slot][slot]
        sub = extract(atlas_path, os.path.join(asset_dir, page), slot)
        H, W = sub.shape[:2]
        alpha = (sub[:, :, 3] > 8).astype(np.uint8) if sub.shape[2] == 4 \
            else (cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY) > 8).astype(np.uint8)
        crop = os.path.join(tmp_dir, "_" + slot.split("/")[-1] + ".png")
        cv2.imwrite(crop, sub)

        # 藝術家 mesh 覆蓋 IoU = bar
        a_uvs = np.array(av["uvs"]).reshape(-1, 2)
        a_tris = np.array(av["triangles"]).reshape(-1, 3)
        artist_recon = fill_mesh(a_uvs, a_tris, W, H)
        artist_iou = iou(artist_recon, alpha)
        artist_nv = len(av["uvs"]) // 2
        artist_weighted = len(av["vertices"]) != len(av["uvs"])

        # ① 預設(非自適應)生成
        m_def = gen_v2(crop)
        rep_def = evaluate(m_def, alpha, vertex_budget=vertex_budget, iou_thresh=artist_iou)
        # ② 自適應覆蓋:以藝術家 IoU 為目標,預算內加密輪廓
        m_ada = gen_v2(crop, target_iou=artist_iou, vertex_budget=vertex_budget)
        rep_ada = evaluate(m_ada, alpha, vertex_budget=vertex_budget, iou_thresh=artist_iou)
        rows.append({
            "part": slot, "crop": [W, H],
            "artist": {"verts": artist_nv, "hull": av["hull"],
                       "weighted": artist_weighted, "iou": round(artist_iou, 4)},
            "gen_default": {"mode": m_def.get("_mode"), "verts": rep_def["vertices"],
                            "hull": m_def["hull"], "iou": rep_def["criteria"]["AC1_iou"]["value"],
                            "meets_artist": rep_def["criteria"]["AC1_iou"]["pass"]},
            "gen_adaptive": {"verts": rep_ada["vertices"], "hull": m_ada["hull"],
                             "iou": rep_ada["criteria"]["AC1_iou"]["value"],
                             "eps": m_ada.get("_eps"), "budget_capped": m_ada.get("_budget_capped", False),
                             "meets_artist": rep_ada["criteria"]["AC1_iou"]["pass"],
                             "static_overall": rep_ada["overall_pass"]},
            "iou_meets_artist": rep_ada["criteria"]["AC1_iou"]["pass"],
            "static_overall": rep_ada["overall_pass"],
        })
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--assets", default="assets")
    ap.add_argument("--tmp", default="/tmp/award_cmp")
    ap.add_argument("--budget", type=int, default=64)
    a = ap.parse_args()
    rows = compare(a.skeleton, a.atlas, a.assets, a.tmp, a.budget)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    n_iou = sum(r["iou_meets_artist"] for r in rows)
    print(f"\n== {n_iou}/{len(rows)} 件覆蓋 IoU 達藝術家門檻;"
          f"預算 {a.budget} 下 static_overall {sum(r['static_overall'] for r in rows)}/{len(rows)} ==")
    raise SystemExit(0 if n_iou == len(rows) else 1)


if __name__ == "__main__":
    main()
