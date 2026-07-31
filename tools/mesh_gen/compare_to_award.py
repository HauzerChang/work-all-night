#!/usr/bin/env python3
"""端到端驗收:PSD 切件 → S3 generate_mesh_v2 → 對照 Award 真實生產 mesh。

這是「PSD→件→mesh」對真實生產標的的整合 AC(見 STATE.md 最高優先 chunk)。
真值來源:機器人拆件的 3 個 mesh 件(光暈/身體/左手),在生產 spine `Award` 中
由美術手做 mesh。我們用 `robot_parts.psd` 切出同一件的 alpha,跑 S3 生成器,
與 Award 藝術家 mesh 在**同一件 alpha 幀**上比覆蓋率(IoU)。

座標系:兩邊 mesh 的 uvs 皆為 region-local [0,1](已驗:main_draw / Award 皆然),
直接 uvs*(W,H) 疊到切件像素幀 → 免處理 atlas 旋轉(旋轉是 atlas 打包細節,
JSON uvs 存邏輯正立座標)。此假設由「藝術家 mesh IoU 應 ≈ 其自身輪廓」實測驗證。

⚠️ 這 3 件在 Award **無 deform timeline**(骨骼/權重驅動,非逐頂點 deform),
故此處不套 deform 閘(無真實位移場可轉移;RULES 禁用未校準 stress)。
deform 耐受性已於 main_draw 4 mesh 另行建立。此 chunk 專驗**靜態覆蓋保真 vs 藝術家**。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from generate_mesh_v2 import generate as gen_v2
from evaluate_mesh import evaluate as eval_mesh


def load_alpha(path):
    img = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if img.ndim == 3 and img.shape[2] == 4:
        return (img[:, :, 3] > 8).astype(np.uint8)
    g = img if img.ndim == 2 else cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    return (g > 8).astype(np.uint8)


def raster_uv_mesh(uvs, tris, H, W):
    """把 region-local uv mesh 填成 (H,W) 二值 mask。"""
    rp = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
    return recon, rp


def iou(a, b):
    u = int(np.logical_or(a, b).sum())
    return (int(np.logical_and(a, b).sum()) / u) if u else 0.0


def get_award_mesh(sk, slot):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    att = skin.get("attachments", skin)
    a = att[slot][slot]
    return (np.array(a["uvs"]).reshape(-1, 2),
            np.array(a["triangles"]).reshape(-1, 3),
            a["hull"], a["width"], a["height"])


def raster_gen_mesh(mesh, H, W):
    """generate_mesh_v2 輸出:uvs 已是 [0,1] over 件本身 → 直接 uvs*(W,H)。"""
    uvs = np.array(mesh["uvs"]).reshape(-1, 2)
    tris = np.array(mesh["triangles"]).reshape(-1, 3)
    return raster_uv_mesh(uvs, tris, H, W)


def compare_one(part_png, sk, slot, iou_margin, viz_path=None):
    alpha = load_alpha(part_png)
    H, W = alpha.shape

    # 藝術家 mesh(真值)
    a_uvs, a_tris, a_hull, aw, ah = get_award_mesh(sk, slot)
    a_mask, a_rp = raster_uv_mesh(a_uvs, a_tris, H, W)
    a_iou = iou(a_mask, alpha)

    # 我的 mesh
    mesh = gen_v2(part_png, mode="auto")
    m_report = eval_mesh(mesh, alpha)
    m_iou = m_report["criteria"]["AC1_iou"]["value"]
    m_mask, m_rp = raster_gen_mesh(mesh, H, W)

    if viz_path:
        _render_viz(alpha, a_rp, a_tris, m_rp,
                    np.array(mesh["triangles"]).reshape(-1, 3), viz_path,
                    slot, a_iou, m_iou)

    return {
        "slot": slot,
        "part_png_size": [W, H],
        "artist": {"vertices": len(a_uvs), "hull": int(a_hull),
                   "triangles": len(a_tris), "logical_size": [aw, ah],
                   "coverage_iou": round(a_iou, 4)},
        "generated": {"vertices": len(mesh["uvs"]) // 2, "hull": mesh["hull"],
                      "triangles": len(mesh["triangles"]) // 3, "mode": mesh.get("_mode"),
                      "coverage_iou": round(m_iou, 4),
                      "format_ok": m_report["criteria"]["AC4_format"]["pass"],
                      "no_orphan": m_report["criteria"]["AC2c_orphans"]["pass"]},
        "AC_match_artist": {
            "pass": bool(m_iou >= a_iou - iou_margin),
            "gen_iou": round(m_iou, 4), "artist_baseline": round(a_iou, 4),
            "margin": iou_margin, "delta": round(m_iou - a_iou, 4)},
    }


def _render_viz(alpha, a_rp, a_tris, m_rp, m_tris, path, slot, a_iou, m_iou):
    H, W = alpha.shape
    base = np.dstack([alpha * 60] * 3).astype(np.uint8)
    art = base.copy(); gen = base.copy()
    for t in a_tris:
        cv2.polylines(art, [np.round(a_rp[t]).astype(np.int32)], True, (0, 200, 255), 1)
    for t in m_tris:
        cv2.polylines(gen, [np.round(m_rp[t]).astype(np.int32)], True, (0, 255, 120), 1)
    pad = np.full((H, 8, 3), 40, np.uint8)
    cv2.imwrite(path, np.hstack([art, pad, gen]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--parts_dir", default="/tmp/robot_parts")
    ap.add_argument("--iou_margin", type=float, default=0.03)
    ap.add_argument("--viz_dir", default=None)
    a = ap.parse_args()
    sk = json.load(open(a.award))
    # PSD 切件檔名 ↔ Award slot(見 knowledge/s4-psd-to-spine-real.md 對應表)
    pairs = [("00_光暈.png", "機器人拆件/光暈"),
             ("03_身體.png", "機器人拆件/身體"),
             ("04_左手.png", "機器人拆件/左手")]
    reports = []
    if a.viz_dir:
        os.makedirs(a.viz_dir, exist_ok=True)
    for fn, slot in pairs:
        pp = os.path.join(a.parts_dir, fn)
        viz = os.path.join(a.viz_dir, f"{slot.replace('/', '_')}.png") if a.viz_dir else None
        reports.append(compare_one(pp, sk, slot, a.iou_margin, viz))
    overall = all(r["AC_match_artist"]["pass"] and r["generated"]["format_ok"]
                  and r["generated"]["no_orphan"] for r in reports)
    out = {"overall_pass": overall, "parts": reports}
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
