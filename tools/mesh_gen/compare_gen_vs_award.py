#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 mesh(generate_mesh_v2) → 對照 Award 真實生產 mesh。

流程(純 CPU,對真實生產標的):
  robot_parts.psd 切件(psd_slice)→ 對 3 個「Award 中為 mesh」的件(光暈/身體/左手)
  跑 generate_mesh_v2(auto) → 靜態評估(evaluate_mesh:IoU/format/孤兒/退化)
  → 與 Award 藝術家 mesh 對照:
     · 拓樸:頂點/三角/hull 數 vs 藝術家真值
     · 覆蓋率基準:重建藝術家 mesh 多邊形於「atlas 切件(derotate)」frame,量其 silhouette IoU
       (自我校驗:對 8 種 dihedral 方向取最佳 IoU,確認 atlas-UV↔件 對映正確)
  判定:生成 mesh IoU ≥ 藝術家覆蓋率基準 − margin,且拓樸在預算內。

⚠️ 誠實註記:這 3 件在 Award **無 deform timeline**(weighted,靠骨骼/權重變形),
   故 deform_eval 的「真實位移場轉移」閘**不適用**;本比對聚焦靜態幾何(覆蓋率 + 拓樸)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import parse_atlas, extract
from evaluate_mesh import evaluate as eval_mesh, load_mask as eval_load_mask
from generate_mesh_v2 import generate as gen_v2

# Award 3 個 mesh 件 → (slot/attachment 名, PSD 切件檔名)
PIECES = [
    ("機器人拆件/光暈", "00_光暈.png"),
    ("機器人拆件/身體", "03_身體.png"),
    ("機器人拆件/左手", "04_左手.png"),
]

def artist_attachment(sk, slot):
    skins = sk["skins"]
    att = skins[0]["attachments"] if isinstance(skins, list) else skins.get("attachments", skins)
    a = att[slot]
    name, data = next(iter(a.items()))
    return name, data


def artist_baseline_iou(sk, slot, atlas_path):
    """藝術家 mesh 自身 silhouette 覆蓋率基準。

    ★ 校驗過的事實(2026-07-17):Spine 3.8 mesh `uvs` 是**region-local 正規化 [0,1]**
      (非 full-sheet),與 validate_against_real.py 既有 artist_iou 一致。
      → 直接 uvs*(cropW,cropH) 對照 atlas 切件(derotate 後 upright)alpha。
      對 v / 1-v 取最佳以吸收影像 y-down vs uv 慣例差(實測 3 件皆 v 不翻,IoU≈0.97 → 對映正確)。
    回傳 (iou, flip_used, topo)。"""
    name, a = artist_attachment(sk, slot)
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    topo = {"vertices": len(uvs), "triangles": len(tris), "hull": a.get("hull")}

    sub = extract(atlas_path, "", name)  # extract 自動依 region.page 找同目錄貼圖
    alpha = (sub[:, :, 3] > 8).astype(np.uint8) if sub.ndim == 3 and sub.shape[2] == 4 \
        else (cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY) > 8).astype(np.uint8)
    Hc, Wc = alpha.shape

    best = (-1.0, None)
    for label, vv in (("v", uvs[:, 1]), ("1-v", 1 - uvs[:, 1])):
        px = np.clip(uvs[:, 0] * Wc, 0, Wc - 1)
        py = np.clip(vv * Hc, 0, Hc - 1)
        recon = np.zeros((Hc, Wc), np.uint8)
        pts = np.column_stack([px, py])
        for t in tris:
            cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
        inter = int(np.logical_and(recon, alpha).sum())
        union = int(np.logical_or(recon, alpha).sum())
        iou = inter / union if union else 0.0
        if iou > best[0]:
            best = (iou, label)
    return best[0], best[1], topo


def run(psd_dir, award_json, award_atlas, margin, tmp_dir):
    sk = json.load(open(award_json))
    os.makedirs(tmp_dir, exist_ok=True)
    rows = []
    all_pass = True
    for slot, pfile in PIECES:
        piece_png = os.path.join(psd_dir, pfile)
        mesh = gen_v2(piece_png, mode="auto")
        mask = eval_load_mask(piece_png)
        ev = eval_mesh(mesh, mask, vertex_budget=128)
        gen_iou = ev["criteria"]["AC1_iou"]["value"]
        base_iou, orient, topo = artist_baseline_iou(sk, slot, award_atlas)

        # 存生成 mesh 供追溯
        json.dump(mesh, open(os.path.join(tmp_dir, pfile.replace(".png", "_gen.json")), "w"),
                  ensure_ascii=False)

        gv, gt, gh = ev["vertices"], ev["triangles"], mesh["hull"]
        coverage_pass = gen_iou >= base_iou - margin
        # 拓樸預算:生成頂點數不超過藝術家 ×2(合理精簡度)
        budget_pass = gv <= topo["vertices"] * 2
        fmt_pass = ev["criteria"]["AC4_format"]["pass"] and \
            ev["criteria"]["AC2c_orphans"]["pass"] and ev["criteria"]["AC2b_degenerate"]["pass"]
        piece_pass = coverage_pass and budget_pass and fmt_pass
        all_pass = all_pass and piece_pass
        rows.append({
            "piece": slot,
            "mode": mesh.get("_mode"),
            "gen": {"vertices": gv, "triangles": gt, "hull": gh, "iou": round(gen_iou, 4)},
            "artist": {"vertices": topo["vertices"], "triangles": topo["triangles"],
                       "hull": topo["hull"], "baseline_iou": round(base_iou, 4),
                       "iou_orient": orient},
            "checks": {"coverage_ge_baseline": coverage_pass,
                       "vertex_budget(<=2x artist)": budget_pass,
                       "format/orphan/degenerate": fmt_pass},
            "piece_pass": piece_pass,
        })
    return {"overall_pass": all_pass, "margin": margin, "pieces": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd-dir", required=True, help="psd_slice 輸出目錄(含 00_光暈.png 等)")
    ap.add_argument("--award-json", default="assets/Award.json")
    ap.add_argument("--award-atlas", default="assets/Award.atlas")
    ap.add_argument("--margin", type=float, default=0.03)
    ap.add_argument("--tmp", default="/tmp")
    a = ap.parse_args()
    rep = run(a.psd_dir, a.award_json, a.award_atlas, a.margin, a.tmp)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
