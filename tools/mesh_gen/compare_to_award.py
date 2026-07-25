#!/usr/bin/env python3
"""端到端驗收:PSD 件 → S3 generate_mesh_v2 → 對照 Award 真實(藝術家)mesh。

這是第一個「對真實生產標的、有藝術家真值可比」的 S3 整合閘。
與 validate_against_real.py 的差異:
  - 輸入源是**分層 PSD 切件**(robot_parts.psd),不是 atlas region → 走完整 PSD→件→mesh 路徑。
  - 目標 mesh 是 Award 生產檔的**加權(weighted)** mesh(靠骨骼 skinning 變形,無 deform timeline)。
    因此本閘只做**靜態**對照(IoU / 頂點預算 / 覆蓋率 / 格式);加權 mesh 的變形閘(骨骼位移場)
    是另一個 bounded chunk,見 STATE.md。

流程(每個件):
  1. PSD 切件 alpha(全解析度)→ generate_mesh_v2(auto) → 生成 mesh。
  2. atlas 切件 alpha(uvs 真值所在座標系)→ 量 PSD↔atlas 幀一致性(alpha-IoU),
     證明 PSD 件與 Award 貼圖為同素材、可共用同一評估幀。
  3. 在 PSD 幀評估:生成 mesh IoU + AC2/3/4;藝術家 mesh 在同幀重建的 IoU 當基準。
  4. pass = 生成 IoU ≥ 藝術家 IoU − margin 且 AC2/3/4 全過。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from evaluate_mesh import evaluate, load_mask
from atlas_crop import extract
from generate_mesh_v2 import generate as gen_v2


def award_mesh(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    return atts[slot][name]


def reconstruct_iou(uvs, tris, mask):
    """把 mesh 的 uvs(region-local 0..1)在 mask 幀重建填滿,回 IoU。"""
    H, W = mask.shape
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    m = (mask > 0).astype(np.uint8)
    inter = int(np.logical_and(recon, m).sum())
    union = int(np.logical_or(recon, m).sum())
    return (inter / union if union else 0.0), recon


def frame_agreement(psd_alpha, atlas_alpha):
    """PSD 件 alpha 與 atlas 件 alpha 的 alpha-IoU(把 atlas 縮放到 PSD 幀)。"""
    Hp, Wp = psd_alpha.shape
    a = cv2.resize(atlas_alpha, (Wp, Hp), interpolation=cv2.INTER_NEAREST)
    p = (psd_alpha > 0).astype(np.uint8); a = (a > 0).astype(np.uint8)
    inter = int(np.logical_and(p, a).sum()); union = int(np.logical_or(p, a).sum())
    return inter / union if union else 0.0


def compare_piece(sk, atlas_path, png_path, slot, name, psd_png, tmp_dir, margin):
    # 1) PSD 件 alpha(生成輸入,全解析度)
    psd_mask = load_mask(psd_png)                       # uint8 0/1, shape (H,W)
    Hp, Wp = psd_mask.shape

    # 2) atlas 件 alpha(真值幀)+ 幀一致性
    sub = extract(atlas_path, png_path, name)
    atlas_alpha = sub[:, :, 3] if sub.ndim == 3 and sub.shape[2] == 4 else \
        cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
    fa = frame_agreement(psd_mask, atlas_alpha)

    # 3) 生成 mesh(從 PSD 件)
    crop = os.path.join(tmp_dir, "_psd_piece.png")
    cv2.imwrite(crop, cv2.imread(psd_png, cv2.IMREAD_UNCHANGED))
    mesh = gen_v2(crop, mode="auto")
    if isinstance(mesh, tuple):
        mesh = mesh[0]
    ev = evaluate(mesh, psd_mask, iou_thresh=0.0)      # 用藝術家基準當門檻,故 AC1 閾值放寬
    gen_iou = ev["criteria"]["AC1_iou"]["value"]
    gen_nv = ev["vertices"]; gen_tri = ev["triangles"]

    # 4) 藝術家 mesh 在 PSD 幀重建的 IoU(真值基準)
    am = award_mesh(sk, slot, name)
    a_uvs = np.array(am["uvs"]).reshape(-1, 2)
    a_tris = np.array(am["triangles"]).reshape(-1, 3)
    art_iou, _ = reconstruct_iou(a_uvs, a_tris, psd_mask)
    art_nv = len(a_uvs); art_tri = len(a_tris)
    a_weighted = len(am["vertices"]) != len(am["uvs"])

    static_ok = all(ev["criteria"][k]["pass"] for k in
                    ["AC2a_centroid_in_mask", "AC2b_degenerate", "AC2c_orphans",
                     "AC3_vertex_budget", "AC4_format"])
    iou_ok = gen_iou >= art_iou - margin
    return {
        "slot": slot,
        "mode": mesh.get("_mode"),
        "psd_frame": [Wp, Hp],
        "frame_agreement_alpha_iou": round(fa, 4),
        "gen": {"vertices": gen_nv, "triangles": gen_tri, "hull": mesh["hull"], "iou": round(gen_iou, 4)},
        "artist": {"vertices": art_nv, "triangles": art_tri, "hull": am["hull"],
                   "weighted": a_weighted, "iou": round(art_iou, 4)},
        "AC_iou": {"pass": iou_ok, "gen": round(gen_iou, 4),
                   "artist_baseline": round(art_iou, 4), "margin": margin},
        "AC_static": {"pass": static_ok,
                      "detail": {k: ev["criteria"][k]["value"] if "value" in ev["criteria"][k]
                                 else ev["criteria"][k]["pass"]
                                 for k in ["AC2a_centroid_in_mask", "AC2b_degenerate",
                                           "AC2c_orphans", "AC3_vertex_budget", "AC4_format"]}},
        "overall_pass": iou_ok and static_ok,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png", default="assets/Award.png")
    ap.add_argument("--png2", default="assets/Award2.png",
                    help="第二頁 atlas(某些件在 Award2.png)")
    ap.add_argument("--psd-dir", default="/tmp/robot_parts")
    ap.add_argument("--tmp", default="/tmp")
    ap.add_argument("--margin", type=float, default=0.03)
    a = ap.parse_args()
    sk = json.load(open(a.skeleton))
    # 若切件不存在(/tmp 為排程臨時目錄),自動從 PSD 切一次 → 完全可自驅重現
    if not os.path.exists(os.path.join(a.psd_dir, "00_光暈.png")):
        from psd_slice import slice_psd
        slice_psd("assets/robot_parts.psd", a.psd_dir)
    # slot(Award) → PSD 切件檔
    pieces = [
        ("機器人拆件/光暈", "00_光暈.png", a.png2),
        ("機器人拆件/身體", "03_身體.png", a.png2),
        ("機器人拆件/左手", "04_左手.png", a.png),
    ]
    reports = []
    for slot, psd_file, page in pieces:
        rep = compare_piece(sk, a.atlas, page, slot, slot,
                            os.path.join(a.psd_dir, psd_file), a.tmp, a.margin)
        reports.append(rep)
    out = {"pieces": reports,
           "all_pass": all(r["overall_pass"] for r in reports)}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if out["all_pass"] else 1)


if __name__ == "__main__":
    main()
