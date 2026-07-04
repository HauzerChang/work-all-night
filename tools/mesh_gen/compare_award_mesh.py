#!/usr/bin/env python3
"""端到端「PSD→件→S3 mesh」對真實生產標的(Award 藝術家 mesh)驗收。

背景(見 knowledge/s4-psd-to-spine-real.md):機器人拆件 3 個 mesh 件
  光暈(78v/hull78)、左手(80v/hull42)、身體(98v/hull40)在 Award spine 為 weighted mesh,
  且**無 deform timeline**(靠骨骼權重變形,非逐頂點 deform)→ 對照聚焦
  「靜態輪廓覆蓋 + 頂點預算 + 拓樸乾淨」,不是 deform 轉移。

方法(方向穩健):
  1. alpha = atlas_crop.extract → 邏輯朝向去旋轉切件(工具已修 CW)。
  2. 藝術家 mesh 覆蓋:atlas uvs → atlas 像素 → 裁到 mesh bbox → 若 region rotate=true 旋 90°
     對齊邏輯朝向 → resize 到 256² → 與 SIL 比 IoU(自動挑兩方向較佳者並記錄)。
  3. 我方 mesh:generate_mesh_v2 對 alpha 切件 → uv 三角填充 → resize 256² → 與 SIL 比 IoU。
  4. AC:our_iou ≥ artist_iou−margin(覆蓋不輸藝術家);our_verts ≤ artist_verts(更精簡);
     evaluate_mesh 拓樸 0 自交。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from atlas_crop import extract, parse_atlas
import generate_mesh_v2 as g2
from evaluate_mesh import evaluate, load_mask as ev_load_mask

CANVAS = 256


def content_bbox(alpha):
    ys, xs = np.where(alpha > 8)
    return xs.min(), ys.min(), xs.max() + 1, ys.max() + 1


def sil_canvas(alpha):
    x0, y0, x1, y1 = content_bbox(alpha)
    crop = (alpha[y0:y1, x0:x1] > 8).astype(np.uint8)
    return cv2.resize(crop, (CANVAS, CANVAS), interpolation=cv2.INTER_NEAREST)


def fill_mesh(uvs, tris, W, H):
    """uvs 正規化 [0,1] → 在 W×H 畫布填三角。"""
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    m = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(m, np.round(pts[t]).astype(np.int32), 1)
    return m


def iou(a, b):
    inter = np.logical_and(a, b).sum()
    union = np.logical_or(a, b).sum()
    return float(inter / union) if union else 0.0


def artist_mesh(skeleton, slot, name):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    a = skin.get("attachments", skin)[slot][name]
    uvs = np.array(a["uvs"]).reshape(-1, 2)
    tris = np.array(a["triangles"]).reshape(-1, 3)
    return uvs, tris, a.get("hull", 0)


def artist_cov_canvas(uvs, tris):
    """藝術家 mesh 的 uvs 為 region-local(~0-1)。填入 256² 方形,回傳全部 8 個
    二面體(dihedral)朝向候選;呼叫端挑與 SIL(同樣 logical→方形)IoU 最佳者。
    這樣對「rotate 打包 / v 軸翻轉」等朝向歧義一律穩健,不需猜方向。"""
    u0, v0 = uvs.min(0); u1, v1 = uvs.max(0)
    nu = (uvs - [u0, v0]) / [max(u1 - u0, 1e-9), max(v1 - v0, 1e-9)]
    base = fill_mesh(nu, tris, CANVAS, CANVAS)
    cands = {}
    for k in range(4):
        r = np.rot90(base, k)
        cands[f"r{k*90}"] = r
        cands[f"r{k*90}_flip"] = r[:, ::-1]
    return cands


def run(skeleton_path, atlas_path, png_dir, pieces, tmp_dir, margin):
    sk = json.load(open(skeleton_path))
    regs = parse_atlas(atlas_path)
    os.makedirs(tmp_dir, exist_ok=True)
    results = []
    for slot, name in pieces:
        reg = regs[name]
        page = os.path.join(png_dir, reg["page"])
        rotate = reg.get("rotate", "false") == "true"
        # 1) 去旋轉切件 alpha
        sub = extract(atlas_path, page, name)
        crop_path = os.path.join(tmp_dir, "_" + name.replace("/", "_") + ".png")
        cv2.imwrite(crop_path, sub)
        alpha = sub[:, :, 3] if sub.ndim == 3 and sub.shape[2] == 4 else \
            cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY)
        SIL = sil_canvas(alpha)

        # 2) 藝術家 mesh 覆蓋(region-local uvs → 8 朝向候選挑最佳)
        a_uvs, a_tris, a_hull = artist_mesh(sk, slot, name)
        a_verts = len(a_uvs)
        cands = artist_cov_canvas(a_uvs, a_tris)
        a_best_dir, artist_iou = None, -1.0
        for d, cov in cands.items():
            v = iou(cov, SIL)
            if v > artist_iou:
                artist_iou, a_best_dir = v, d

        # 3) 我方 mesh
        mesh = g2.generate(crop_path)
        our_verts = len(mesh["uvs"]) // 2
        mask = ev_load_mask(crop_path)
        ev = evaluate(mesh, mask)
        our_iou_raw = ev["criteria"]["AC1_iou"]["value"]
        orphans = ev["criteria"].get("AC2c_orphans", {}).get("value")
        degen = ev["criteria"].get("AC2b_degenerate", {}).get("value")
        # 也在同一 256² 正規化畫布量,與藝術家可比
        m_uvs = np.array(mesh["uvs"]).reshape(-1, 2)
        m_tris = np.array(mesh["triangles"]).reshape(-1, 3)
        u0, v0 = m_uvs.min(0); u1, v1 = m_uvs.max(0)
        nu = (m_uvs - [u0, v0]) / [max(u1 - u0, 1e-9), max(v1 - v0, 1e-9)]
        OURS = fill_mesh(nu, m_tris, CANVAS, CANVAS)
        our_iou = iou(OURS, SIL)

        ac_cover = our_iou >= artist_iou - margin
        ac_budget = our_verts <= a_verts
        # 拓樸閘:排除 AC1_iou(武斷 0.95,已由 artist-baseline 覆蓋取代);
        # 保留真實幾何閘(質心在遮罩內 / 無退化 / 無孤兒 / 格式合法)。
        ac_topo = all(ev["criteria"][k]["pass"] for k in
                      ("AC4_format", "AC2a_centroid_in_mask", "AC2b_degenerate",
                       "AC2c_orphans") if k in ev["criteria"])
        results.append({
            "piece": name, "mode": mesh.get("_mode"), "rotate": rotate,
            "artist_verts": a_verts, "artist_hull": a_hull, "artist_iou": round(artist_iou, 4),
            "artist_align": a_best_dir,
            "our_verts": our_verts, "our_hull": mesh["hull"],
            "our_iou": round(our_iou, 4), "our_iou_selfeval": round(our_iou_raw, 4),
            "orphans": orphans, "degenerate": degen, "topo_pass": bool(ac_topo),
            "AC_cover(≥artist-m)": bool(ac_cover),
            "AC_budget(≤artist)": bool(ac_budget),
            "piece_pass": bool(ac_cover and ac_budget and ac_topo),
        })
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default="assets/Award.json")
    ap.add_argument("--atlas", default="assets/Award.atlas")
    ap.add_argument("--png-dir", default="assets")
    ap.add_argument("--margin", type=float, default=0.03)
    ap.add_argument("--tmp", default="/tmp/award_mesh_cmp")
    a = ap.parse_args()
    pieces = [
        ("機器人拆件/光暈", "機器人拆件/光暈"),
        ("機器人拆件/左手", "機器人拆件/左手"),
        ("機器人拆件/身體", "機器人拆件/身體"),
    ]
    res = run(a.skeleton, a.atlas, a.png_dir, pieces, a.tmp, a.margin)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    overall = all(r["piece_pass"] for r in res)
    print("\nOVERALL:", "PASS" if overall else "FAIL")
    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
