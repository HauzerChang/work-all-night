#!/usr/bin/env python3
"""端到端驗證:PSD 件 → S3 mesh → 對照 Award 真實生產 mesh(weighted регime)。

背景與 validate_against_real.py 的差異
--------------------------------------
`validate_against_real.py` 針對 main_draw 的 4 個 **unweighted + deform-timeline** mesh
(窗簾/陰影),用「真實位移場轉移」當變形閘。但 Award(big win 機器人)的 mesh 屬**另一種
regime**:`機器人拆件/{光暈,身體,左手}` 全為 **weighted mesh(骨骼權重驅動)、無 deform
timeline**(見 knowledge/s4-psd-to-spine-real.md)。這類 mesh:
  - deform 靠骨骼+權重,不是逐頂點 deform → 「真實位移場轉移」閘不適用(N/A)。
  - S3 目前只產 **unweighted topology**(BBW 權重尚未實作)→ 能公平比對的維度是
    **靜態覆蓋 + 拓樸經濟性**,不是變形。

因此本工具的 AC(對每件):
  1. 端到端來源真值 = **PSD 切件的 alpha**(art source;非 atlas 縮小/derotate 版)。
     驗證前先確認「藝術家 uvs 疊在 PSD 件上覆蓋率高」→ 座標框一致性 sanity check
     (Spine mesh uvs 存於邏輯 upright 空間,與 upright PSD 件對齊,與 atlas rotate 無關)。
  2. 生成 mesh 靜態覆蓋 IoU ≥ 藝術家同件 mesh 的覆蓋 IoU(margin 可調)。
  3. 頂點經濟性:生成頂點數 ≤ 藝術家頂點數(「用更少頂點達到同等覆蓋」)。
  4. 靜態幾何:0 退化 / 0 孤兒 / 重心在內 / Spine 格式正確(evaluate_mesh)。
  5. 變形閘:**N/A**(weighted、無 deform timeline)→ 端到端 parity 的缺口 = BBW 權重(下一能力)。

自主收斂(L2,預算 5 輪):若預設 eps 覆蓋率未達藝術家基準,沿
epsilon_frac 0.008→0.004→0.002→0.001 收斂(hull 貼更緊),在「頂點數 ≤ 藝術家」的天花板內
取第一個達標點。這重現了 S3 的核心 tradeoff:**覆蓋率由邊界取樣密度(eps/rows)決定**。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from generate_mesh import generate as gen_v1
from evaluate_mesh import evaluate, load_mask
from psd_slice import slice_psd

# Award 中屬 mesh 的機器人件 → 對應 PSD 圖層名
ROBOT_MESH_PIECES = ["光暈", "身體", "左手"]
EPS_LADDER = [0.008, 0.004, 0.002, 0.001]  # 由粗到細(自主收斂階梯,≤5 輪)


def award_attachment(sk, piece):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    slot = "機器人拆件/" + piece
    return atts[slot][slot]  # attachment key == slot 全名


def artist_iou_on(mask, att):
    """把藝術家 mesh(uvs,邏輯 upright 0..1)疊到 PSD 件 alpha 上算覆蓋 IoU。"""
    uvs = np.array(att["uvs"], dtype=np.float64).reshape(-1, 2)
    tris = np.array(att["triangles"], dtype=np.int32).reshape(-1, 3)
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    m = mask > 0
    inter = int(np.logical_and(recon, m).sum())
    union = int(np.logical_or(recon, m).sum())
    return (inter / union if union else 0.0), len(uvs)


def psd_piece_masks(psd_path):
    """切 PSD → {圖層名: (alpha_mask, tmp_png_path)}(只留機器人 mesh 件)。"""
    _, _, parts = slice_psd(psd_path, out_dir=None)
    out = {}
    tmp = "/tmp/_award_pieces"; os.makedirs(tmp, exist_ok=True)
    for entry, im in parts:
        if entry["name"] in ROBOT_MESH_PIECES:
            p = os.path.join(tmp, f"{entry['name']}.png")
            im.save(p)
            out[entry["name"]] = p
    return out


def validate_piece(piece, png_path, att, iou_margin=0.0, sanity_min=0.85):
    mask = load_mask(png_path)
    base_iou, art_nv = artist_iou_on(mask, att)
    # 座標框一致性 sanity:藝術家 mesh 疊 PSD 件應高覆蓋,否則框沒對齊
    frame_ok = base_iou >= sanity_min

    target = base_iou - iou_margin
    chosen = None
    trail = []
    for eps in EPS_LADDER:
        m, _ = gen_v1(png_path, epsilon_frac=eps)
        rep = evaluate(m, mask, vertex_budget=10**9)  # 頂點上限改用藝術家數,budget 不擋
        c = rep["criteria"]
        iou = c["AC1_iou"]["value"]; nv = rep["vertices"]
        geom_ok = (c["AC2a_centroid_in_mask"]["pass"] and c["AC2b_degenerate"]["pass"]
                   and c["AC2c_orphans"]["pass"] and c["AC4_format"]["pass"])
        rec = {"eps": eps, "nv": nv, "hull": m["hull"], "tris": rep["triangles"],
               "iou": iou, "geom_ok": geom_ok}
        trail.append(rec)
        # 達標條件:覆蓋 ≥ 藝術家(margin) 且 頂點 ≤ 藝術家(更經濟) 且 幾何乾淨
        if iou >= target and nv <= art_nv and geom_ok:
            chosen = rec
            break
    if chosen is None:  # 沒有點同時達 IoU 與經濟性 → 取覆蓋最高者報告
        chosen = max(trail, key=lambda r: r["iou"])

    passed = (frame_ok and chosen["iou"] >= target
              and chosen["nv"] <= art_nv and chosen["geom_ok"])
    return {
        "piece": piece,
        "psd_alpha_size": [mask.shape[1], mask.shape[0]],
        "frame_sanity": {"artist_iou_on_psd": round(base_iou, 4), "ok": frame_ok,
                         "min": sanity_min},
        "artist": {"nv": art_nv, "hull": att["hull"], "weighted": True,
                   "note": "bone-driven weighted mesh, no deform timeline"},
        "generated": {"eps": chosen["eps"], "nv": chosen["nv"], "hull": chosen["hull"],
                      "tris": chosen["tris"], "iou": round(chosen["iou"], 4),
                      "geom_clean": chosen["geom_ok"]},
        "AC_coverage": {"gen_iou": round(chosen["iou"], 4),
                        "artist_baseline": round(base_iou, 4),
                        "margin": iou_margin,
                        "pass": chosen["iou"] >= target},
        "AC_economy": {"gen_nv": chosen["nv"], "artist_nv": art_nv,
                       "pass": chosen["nv"] <= art_nv},
        "AC_deform": {"applicable": False,
                      "reason": "weighted/bone-driven mesh, no per-vertex deform timeline; "
                                "S3 emits unweighted topology only (BBW weights = next capability)"},
        "iteration_trail": trail,
        "overall_pass": bool(passed),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--margin", type=float, default=0.0)
    a = ap.parse_args()
    sk = json.load(open(a.award))
    masks = psd_piece_masks(a.psd)
    reports = []
    for piece in ROBOT_MESH_PIECES:
        att = award_attachment(sk, piece)
        reports.append(validate_piece(piece, masks[piece], att, iou_margin=a.margin))
    summary = {"pieces": reports,
               "all_pass": all(r["overall_pass"] for r in reports),
               "deform_note": "全 3 件為 weighted/bone-driven,靜態拓樸維度已對齊生產;"
                              "變形 parity 待 S3 BBW 權重(下一能力)。"}
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(0 if summary["all_pass"] else 1)


if __name__ == "__main__":
    main()
