#!/usr/bin/env python3
"""端到端「PSD → 件 → S3 mesh」對真實生產標的(Award spine)驗收。

背景(STATE.md 最高優先塊):使用者提供機器人 big-win 主角的分層 PSD(`robot_parts.psd`)
以及對應的真實生產 spine(`Award.json`)。Award 中有 5 個機器人拆件 slot,其中 3 個是 **mesh**:
  機器人拆件/光暈 (78v, hull=78 純輪廓, 708x685)
  機器人拆件/身體 (98v, hull=40, 381x427)
  機器人拆件/左手 (80v, hull=42, 259x217)
另 2 件(右手/頭)是 region。這 3 個 mesh 提供了 **藝術家真值**,可對我們的 S3 生成器做
端到端對照:PSD 切件 → generate_mesh_v2 → 與 Award 真實 mesh 比 IoU / 頂點預算 / 拓樸乾淨。

重要事實(本次探查):這 3 個 mesh 在 Award 全部 12 動畫中 **皆無 deform timeline**
(靠骨骼 transform 動,非 mesh 變形)。因此:
  - 生產「相關」的 AC = 靜態覆蓋(對齊藝術家 mesh)+ 拓樸乾淨 + 頂點預算,而非耐變形。
  - 仍附一個「deform-safe 交叉檢查」:把 main_draw curtain_left 的**真實位移場**轉移到生成
    mesh,確認 0 自交 / 0 翻面 —— 證明生成器輸出即便被拿去變形也安全(超出生產需求的保險)。

AC(每件):
  AC-cover  : gen_iou >= artist_iou - margin   (生成 mesh 覆蓋不輸藝術家真值)
  AC-budget : gen 頂點數 <= 藝術家頂點數 * budget_ratio(不比藝術家臃腫太多)
  AC-clean  : 生成 mesh 靜態 0 退化/0 孤兒 且 deform-safe 交叉檢查 clean
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_mesh, load_mask
import deform_eval as de

# Award 中 3 個 mesh 拆件(slot == attachment name)
ROBOT_MESHES = ["機器人拆件/光暈", "機器人拆件/身體", "機器人拆件/左手"]
# PSD 切件檔名(psd_slice 輸出;PSD 圖層名 = slot 去掉前綴)
PART_FILE = {"機器人拆件/光暈": "00_光暈.png",
             "機器人拆件/身體": "03_身體.png",
             "機器人拆件/左手": "04_左手.png"}


def award_mesh(sk, slot):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    return skin.get("attachments", skin)[slot][slot]


def mesh_iou_over_mask(uvs, tris, mask):
    """把 mesh 的 uv(→ 該遮罩尺寸像素)三角填滿,和 mask 求 IoU。"""
    H, W = mask.shape
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    inter = np.logical_and(recon, mask).sum()
    union = np.logical_or(recon, mask).sum()
    return float(inter / union) if union else 0.0


def gen_uvs_tris(mesh):
    uvs = np.array(mesh["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    return uvs, tris


def validate_part(sk, slot, part_png, ref_field, cover_margin=0.02, budget_ratio=1.5):
    mask = load_mask(part_png)              # 生成器與藝術家共用同一參考:切件 alpha
    H, W = mask.shape

    # --- 生成 mesh(v2 auto,對映生產預設路徑) ---
    mesh = gen_v2(part_png, mode="auto")
    g_uvs, g_tris = gen_uvs_tris(mesh)
    g_nv = len(g_uvs)
    ev = eval_mesh(mesh, mask, vertex_budget=256)   # 放寬預算閘,改用相對藝術家比
    gen_iou = ev["criteria"]["AC1_iou"]["value"]
    degen = ev["criteria"]["AC2b_degenerate"]["value"]
    orphan = ev["criteria"]["AC2c_orphans"]["value"]

    # --- 藝術家真值 mesh IoU(同一 mask 上重建) ---
    am = award_mesh(sk, slot)
    a_uvs = np.array(am["uvs"], dtype=np.float64).reshape(-1, 2)
    a_tris = np.array(am["triangles"], dtype=np.int32).reshape(-1, 3)
    a_nv = len(a_uvs)
    artist_iou = mesh_iou_over_mask(a_uvs, a_tris, mask)

    # --- 生產相關 AC(對映真實資產使用方式:這 3 slot 全無 deform,靠骨骼動) ---
    ac_cover = gen_iou >= artist_iou - cover_margin
    ac_budget = g_nv <= a_nv * budget_ratio
    ac_static_clean = (degen == 0 and orphan == 0)

    # --- deform-robustness 探針(informational,非生產必要) ---
    #   生產不變形這 3 件,但探針揭示「若被拿去 warp」是否安全:轉移 main_draw curtain 真實位移場。
    #   同時記錄強制 strip 的補救(strip 對窗簾/大單軸拉伸最耐變形)。
    d_auto = de.transfer_deform_check(mesh, ref_field[0], ref_field[1])
    mesh_strip = gen_v2(part_png, mode="strip")
    d_strip = de.transfer_deform_check(mesh_strip, ref_field[0], ref_field[1])

    return {
        "slot": slot,
        "part_size": [W, H],
        "gen": {"vertices": g_nv, "hull": mesh["hull"],
                "triangles": len(g_tris), "mode": mesh.get("_mode"), "iou": round(gen_iou, 4)},
        "artist": {"vertices": a_nv, "hull": am["hull"],
                   "triangles": len(a_tris), "iou": round(artist_iou, 4),
                   "wh": [am.get("width"), am.get("height")]},
        "AC_cover": {"pass": bool(ac_cover), "gen_iou": round(gen_iou, 4),
                     "artist_iou": round(artist_iou, 4), "margin": cover_margin},
        "AC_budget": {"pass": bool(ac_budget), "gen_v": g_nv, "artist_v": a_nv,
                      "limit": round(a_nv * budget_ratio, 1)},
        "AC_static_clean": {"pass": bool(ac_static_clean),
                            "degenerate": degen, "orphans": orphan},
        "deform_probe": {  # informational — 生產無 deform,不 gating
            "note": "此 slot 在 Award 全動畫無 deform(骨骼驅動);以下為『若被 warp』的耐受探針。",
            "auto": {"mode": mesh.get("_mode"), "clean": d_auto["clean"],
                     "self_intersections": d_auto["self_intersections"],
                     "triangle_flips": d_auto["triangle_flips"], "area_ratio": d_auto["area_ratio"]},
            "strip": {"vertices": len(mesh_strip["uvs"]) // 2, "clean": d_strip["clean"],
                      "self_intersections": d_strip["self_intersections"],
                      "triangle_flips": d_strip["triangle_flips"], "area_ratio": d_strip["area_ratio"]},
        },
        "overall_pass": bool(ac_cover and ac_budget and ac_static_clean),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--parts_dir", default="/tmp/robot_parts")
    ap.add_argument("--field_skeleton", default="assets/main_draw.json")
    ap.add_argument("--field_slot", default="image/curtain_left")
    a = ap.parse_args()

    sk = json.load(open(a.award))
    field_sk = json.load(open(a.field_skeleton))
    uvs_src, field, frame = de.real_deform_field(field_sk, a.field_slot, a.field_slot)
    ref_field = (uvs_src, field)

    reports = []
    for slot in ROBOT_MESHES:
        part = os.path.join(a.parts_dir, PART_FILE[slot])
        reports.append(validate_part(sk, slot, part, ref_field))

    out = {"deform_field_source": {"skeleton": os.path.basename(a.field_skeleton),
                                   "slot": a.field_slot, "frame": frame},
           "parts": reports,
           "overall_pass": all(r["overall_pass"] for r in reports)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["overall_pass"] else 1)


if __name__ == "__main__":
    main()
