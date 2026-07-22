#!/usr/bin/env python3
"""S3+S4 端到端驗收 — PSD 件 → generate_mesh → 對照 Award 真實生產 mesh。

這是「PSD→件→mesh」對**真實生產標的**的整合 AC(STATE.md 候選 #1,有真值)。
與 validate_against_real.py 的差別:那支比對 main_draw 的 atlas 切件 + 真實 deform 場;
本支比對 robot_parts.psd 的切件 + Award spine 裡藝術家手做的真實 mesh(ground truth)。

流程(每個 mesh 件):
  1. 從 robot_parts.psd 切出該圖層的緊湊 PNG(psd_slice,已驗證無損)。
  2. generate_mesh_v2(auto) 生成 mesh。
  3. AC_iou     : 生成 mesh 覆蓋率 vs 件 alpha(evaluate_mesh)。
  4. artist_base: 藝術家真實 mesh 覆蓋率 vs 件 alpha(用 Award mesh 的 **region-local
                  uvs** 光柵化;⚠️不可用 vertices — 見 rasterize_uv_mesh 說明)。
  5. pass ⇔ AC_iou >= artist_base - margin(對齊藝術家覆蓋率,不用武斷閾值,與既有 AC 一致)。

⚠️ deform 閘:這 5 件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform),
   故沒有可轉移的真實位移場 → 本支**不下 deform pass/fail**(避免用未校準壓力場,見 RULES)。
   僅回報生成 mesh 在 setup 的拓樸健全(0 退化/0 孤兒)作為結構 sanity。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import slice_psd
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate


# robot_parts.psd 圖層 → Award slot/attachment(ground truth,見 s4-psd-to-spine-real.md)
MESH_MAP = [
    ("光暈", "機器人拆件/光暈", "機器人拆件/光暈"),
    ("身體", "機器人拆件/身體", "機器人拆件/身體"),
    ("左手", "機器人拆件/左手", "機器人拆件/左手"),
]


def award_attachment(sk, slot, name):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    return att[slot][name]


def rasterize_uv_mesh(mesh_or_att, W, H):
    """用 **region-local uvs**(0..1)光柵化 mesh 覆蓋到 (H,W)。

    ⚠️ 關鍵:藝術家 Award mesh 的覆蓋要用 `uvs`(貼圖座標),**不是** `vertices`。
    vertices 在 bone-local/旋轉框(span 與中心都不對齊 W/H,會嚴重低估覆蓋率);
    uvs 才是「貼圖上哪塊被這 mesh 蓋到」。經驗證:uvs 已是 region-local upright
    (與 atlas_crop CW 還原對齊),對 atlas region alpha IoU 0.97~0.98,對 PSD 件 0.95~0.98。
    我方生成 mesh 的 uvs = x/W,y/H(影像座標正規化),同一慣例,可同框比對。
    """
    uv = np.asarray(mesh_or_att["uvs"], dtype=np.float64).reshape(-1, 2)
    pts = np.column_stack([uv[:, 0] * W, uv[:, 1] * H])
    tris = np.asarray(mesh_or_att["triangles"], dtype=np.int32).reshape(-1, 3)
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    return recon


def iou(a, b):
    a = a > 0; b = b > 0
    u = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / u) if u else 0.0


def piece_alpha(im):
    arr = np.asarray(im.convert("RGBA"))
    return (arr[:, :, 3] > 8).astype(np.uint8)


def compare(psd_path, award_path, tmp_dir, iou_margin=0.02, fig_dir=None):
    _, _, parts = slice_psd(psd_path)          # [(entry, PIL im), ...]
    by_name = {e["name"]: im for e, im in parts}
    sk = json.load(open(award_path))
    os.makedirs(tmp_dir, exist_ok=True)
    if fig_dir:
        os.makedirs(fig_dir, exist_ok=True)

    rows = []
    for layer, slot, name in MESH_MAP:
        im = by_name[layer]
        mask = piece_alpha(im)                 # (H,W) 件 alpha,原始尺寸
        Hp, Wp = mask.shape
        crop = os.path.join(tmp_dir, f"_{layer}.png")
        im.convert("RGBA").save(crop)

        mesh = gen_v2(crop, mode="auto")
        nv = len(mesh["uvs"]) // 2
        ev = evaluate(mesh, mask, vertex_budget=64)
        my_iou = ev["criteria"]["AC1_iou"]["value"]
        # 兩 mesh 都用 region-local uvs 光柵化到同一件像素框(PSD 件為共同貼圖)
        my_cov = rasterize_uv_mesh(mesh, Wp, Hp)

        a = award_attachment(sk, slot, name)
        art_cov = rasterize_uv_mesh(a, Wp, Hp)
        art_iou = iou(art_cov, mask)
        # 生成 vs 藝術家覆蓋一致性(兩 mesh 彼此的 IoU,同框)
        gen_vs_art = iou(my_cov, art_cov)

        crit = ev["criteria"]
        topo_ok = (crit["AC2b_degenerate"]["pass"] and crit["AC2c_orphans"]["pass"]
                   and crit["AC4_format"]["pass"])
        passed = (my_iou >= art_iou - iou_margin) and topo_ok

        rows.append({
            "piece": layer, "slot": slot,
            "generated": {"vertices": nv, "hull": mesh["hull"],
                          "triangles": len(mesh["triangles"]) // 3,
                          "mode": mesh.get("_mode")},
            "artist": {"vertices": len(a["uvs"]) // 2, "hull": a["hull"],
                       "triangles": len(a["triangles"]) // 3},
            "AC_iou": {"generated_vs_alpha": round(my_iou, 4),
                       "artist_vs_alpha": round(art_iou, 4),
                       "margin": iou_margin,
                       "pass": my_iou >= art_iou - iou_margin},
            "gen_vs_artist_iou": round(gen_vs_art, 4),
            "topology_sane": topo_ok,
            "overall_pass": passed,
        })

        if fig_dir:
            canvas = np.zeros((Hp, Wp, 3), np.uint8)
            canvas[mask > 0] = (60, 60, 60)
            # 生成綠、藝術家紅、重疊黃
            g = my_cov > 0; r = art_cov > 0
            canvas[g] = (0, 180, 0)
            canvas[r] = (0, 0, 180)
            canvas[np.logical_and(g, r)] = (0, 180, 180)
            cv2.imwrite(os.path.join(fig_dir, f"cover_{layer}.png"), canvas)

    overall = all(r["overall_pass"] for r in rows)
    return {"overall_pass": overall, "pieces": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--tmp", default="/tmp/award_cmp")
    ap.add_argument("--figs", default=None, help="輸出覆蓋疊圖目錄")
    ap.add_argument("--margin", type=float, default=0.02)
    a = ap.parse_args()
    rep = compare(a.psd, a.award, a.tmp, a.margin, a.figs)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
