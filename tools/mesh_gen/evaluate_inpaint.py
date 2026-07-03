#!/usr/bin/env python3
"""S2 補圖閘(inpainting evaluator)— 對「補繪被遮擋區」的候選結果 pass/fail + 量化。

對應 PLAN S4 完成條件「補圖極端姿態幀 0 破洞 / 0 明顯接縫」的靜態可機讀版。
補圖在 pipeline 的角色:PSD 契約下美術畫全 → 通常不需要;fallback(平面圖切件)時
被遮區要補繪 → 本閘把關「補得夠不夠好」,無它則補圖無法自主收斂(S2 樞紐)。

輸入:candidate RGBA(補繪後的件)+ hole mask(被遮/缺失區)+ 可選 GT RGBA(真值,校準用)。

GT-free 準則(生產時無真值可用)—— 2026-07-03 以真實遮擋 benchmark 校準後定版:
  AC1_hole   :洞區內的「內部破洞」比率 ≈ 0。內部破洞 = closure(alpha) 內卻 alpha=0 的像素
               (被內容包圍的透明洞;不罰洞區中本來就在件輪廓外的部分)。→ 抓「沒補」。
  AC2_seam   :**局部化接縫比** = 洞邊界線(±1px)平均梯度 / 緊鄰兩側(2~4px)平均梯度 ≤ 閾值。
               GT 的邊界只是內容中任意一條線 → ≈1;顏色/筆觸不接 → 邊界出現梯度脊 → 高。
               ⚠️ 初版用「遠處參考帶」不穩(洞恰在細節區時 GT 自己會高);局部化後才把
               平色填充(2.3~3.8)與 GT(≤1.87)分開。→ 抓「接縫」(含平色填充)。
  AC3_texture:洞內 **Laplacian** 能量 / 參考帶 ≤ 上限(僅上限)。自然筆觸是線狀、iid 噪聲是
               斑點,Laplacian 對噪聲遠更敏感(噪聲 ≥1.70 vs GT ≤0.93,Sobel 分不開)。
               不設下限:平滑內容(光暈漸層)洞內梯度天生低,下限會誤殺 GT。→ 抓「亂填」。

GT 模式(benchmark/校準時):
  AC4_fidelity:洞區 premultiplied MAE vs 真值(沿用 psd_slice 的 premult 比對教訓)。
               fid_tol=12 的含意:cv2 級補繪只在平滑件(光暈 10.0)達標,細節件(右手 31/頭 24/
               身體 20)不達 → 正確編碼降階鏈「cv2 只夠平滑區,細節大洞要升級(LaMa/GPU/人工)」。

梯度一律算在 premultiplied RGB 上(透明區不產生假梯度)。
閾值以真實 benchmark 校準(robot_parts 真實圖層互遮 + 美術畫全圖層當 GT,見 --bench)。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2


def _premult(img):
    f = img.astype(np.float64)
    return f[..., :3] * f[..., 3:4] / 255.0


def _grad_mag(pm):
    g = pm.mean(axis=2).astype(np.float32)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    return np.sqrt(gx * gx + gy * gy)


def _lap_mag(pm):
    g = pm.mean(axis=2).astype(np.float32)
    return np.abs(cv2.Laplacian(g, cv2.CV_32F, ksize=3))


def _mean_on(x, m):
    return float(x[m].mean()) if m.any() else 0.0


def evaluate(cand, hole, gt=None, hole_tol=0.02, seam_tol=2.0, tex_hi=1.3, fid_tol=12.0):
    """cand/gt: RGBA uint8;hole: bool。回傳逐條 AC 報告。閾值來源見檔頭(benchmark 校準)。"""
    hole = hole.astype(bool)
    alpha = cand[..., 3] > 8
    k = np.ones((3, 3), np.uint8)
    closure = cv2.morphologyEx(alpha.astype(np.uint8), cv2.MORPH_CLOSE,
                               np.ones((15, 15), np.uint8)).astype(bool)

    # AC1 內部破洞
    interior_holes = closure & ~alpha & hole
    denom = int((closure & hole).sum())
    hole_ratio = interior_holes.sum() / denom if denom else 0.0

    # AC2 局部化接縫:邊界線(±1px)vs 緊鄰兩側(2~4px)
    hu = hole.astype(np.uint8)
    B1 = (cv2.dilate(hu, k) > 0) & ~(cv2.erode(hu, k) > 0)
    d4 = cv2.dilate(hu, k, iterations=4) > 0
    e4 = cv2.erode(hu, k, iterations=4) > 0
    B2 = (d4 & ~e4) & ~B1
    pm = _premult(cand)
    gm = _grad_mag(pm)
    g_line = _mean_on(gm, B1 & alpha)
    g_near = _mean_on(gm, B2 & alpha)
    seam_ratio = g_line / g_near if g_near > 1e-6 else 0.0

    # AC3 洞內 Laplacian 能量 vs 遠處參考帶(僅上限;平滑內容天生低,不設下限)
    lm = _lap_mag(pm)
    ref = (cv2.dilate(hu, k, iterations=12) > 0) & ~d4 & alpha & ~hole
    l_in = _mean_on(lm, hole & alpha)
    l_ref = _mean_on(lm, ref)
    tex_ratio = l_in / l_ref if l_ref > 1e-6 else 0.0

    res = {
        "AC1_hole": {"pass": hole_ratio <= hole_tol, "interior_hole_ratio": round(float(hole_ratio), 5),
                     "thresh": hole_tol},
        "AC2_seam": {"pass": seam_ratio <= seam_tol, "seam_local_ratio": round(seam_ratio, 3),
                     "line_grad": round(g_line, 2), "near_grad": round(g_near, 2),
                     "thresh": seam_tol},
        "AC3_texture": {"pass": tex_ratio <= tex_hi, "lap_ratio": round(tex_ratio, 3),
                        "thresh_hi": tex_hi},
    }
    if gt is not None:
        content = (gt[..., 3] > 8) | alpha
        m = hole & content
        mae = float(np.abs(_premult(cand)[m] - _premult(gt)[m]).mean()) if m.any() else 0.0
        res["AC4_fidelity"] = {"pass": mae <= fid_tol, "premult_mae_in_hole": round(mae, 3),
                               "thresh": fid_tol}
    overall = all(v["pass"] for v in res.values())
    return {"overall_pass": overall, "hole_px": int(hole.sum()), "criteria": res}


# ---------- 補繪器(benchmark 用;cv2 級 = 降階鏈的 CPU fallback) ----------
def make_occluded(gt, hole):
    out = gt.copy()
    out[hole] = 0
    return out


def inpaint_cv2(occluded, hole, method=cv2.INPAINT_TELEA, radius=5):
    """premult RGB + alpha 各自 inpaint 再解回 straight RGBA。"""
    m = hole.astype(np.uint8) * 255
    pm = np.clip(_premult(occluded), 0, 255).astype(np.uint8)
    rgb = cv2.inpaint(pm, m, radius, method)
    a = cv2.inpaint(occluded[..., 3], m, radius, method)
    out = np.zeros_like(occluded)
    af = np.maximum(a.astype(np.float64), 1e-6)
    out[..., :3] = np.clip(rgb.astype(np.float64) * 255.0 / af[..., None], 0, 255).astype(np.uint8)
    out[..., 3] = a
    out[a == 0] = 0
    return out


def fill_flat(occluded, hole, color=None):
    out = occluded.copy()
    if color is None:  # 周圍平均色(「偷懶補圖」)
        ring = cv2.dilate(hole.astype(np.uint8), np.ones((9, 9), np.uint8)).astype(bool) & ~hole
        ring &= occluded[..., 3] > 8
        color = occluded[ring][:, :3].mean(axis=0) if ring.any() else np.array([128, 128, 128])
    out[hole, :3] = color.astype(np.uint8)
    out[hole, 3] = 255
    return out


def fill_noise(occluded, hole, rng):
    out = occluded.copy()
    n = int(hole.sum())
    out[hole, :3] = rng.integers(0, 256, (n, 3), dtype=np.uint8)
    out[hole, 3] = 255
    return out


def fill_black_hole(occluded, hole):
    """啥都不補(alpha 留 0)= 破洞負對照。"""
    return occluded.copy()


# ---------- 真實 benchmark:robot_parts 圖層互遮 ----------
def load_bench_pieces(manifest_path, pieces_dir, min_occ_px=500):
    """回傳 [(name, gt RGBA, hole bool)]:hole = 上層圖層真實蓋住本件的區域(裁到件 bbox)。"""
    man = json.load(open(manifest_path))
    W, H = man["size"]
    full = {}
    for e in man["parts"]:
        im = cv2.imread(os.path.join(pieces_dir, e["file"]), cv2.IMREAD_UNCHANGED)
        full[e["name"]] = (e, im)
    out = []
    for e, im in full.values():
        l, t = e["offset"]; w, h = e["size"]
        occ = np.zeros((h, w), bool)
        for e2, im2 in full.values():
            if e2["z"] <= e["z"]:
                continue
            l2, t2 = e2["offset"]; w2, h2 = e2["size"]
            a2 = np.zeros((H, W), bool)
            a2[t2:t2 + h2, l2:l2 + w2] = im2[..., 3] > 8
            occ |= a2[t:t + h, l:l + w]
        hole = occ & (im[..., 3] > 8)
        if hole.sum() >= min_occ_px:
            out.append((e["name"], im, hole))
    return out


def bench(manifest_path, pieces_dir, seed=7):
    rng = np.random.default_rng(seed)
    rows = []
    for name, gt, hole in load_bench_pieces(manifest_path, pieces_dir):
        occ = make_occluded(gt, hole)
        cands = {
            "GT(正對照)": gt,
            "cv2_telea": inpaint_cv2(occ, hole, cv2.INPAINT_TELEA),
            "cv2_ns": inpaint_cv2(occ, hole, cv2.INPAINT_NS),
            "黑洞(不補)": fill_black_hole(occ, hole),
            "平色填充": fill_flat(occ, hole),
            "噪聲填充": fill_noise(occ, hole, rng),
        }
        for label, cand in cands.items():
            r = evaluate(cand, hole, gt=gt)
            c = r["criteria"]
            rows.append({"piece": name, "cand": label, "overall": r["overall_pass"],
                         "gtfree_pass": all(c[k]["pass"] for k in ("AC1_hole", "AC2_seam", "AC3_texture")),
                         "hole": c["AC1_hole"]["interior_hole_ratio"],
                         "seam": c["AC2_seam"]["seam_local_ratio"],
                         "tex": c["AC3_texture"]["lap_ratio"],
                         "mae": c["AC4_fidelity"]["premult_mae_in_hole"]})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", help="候選補繪 RGBA PNG")
    ap.add_argument("--hole", help="洞 mask PNG(>0 為洞)")
    ap.add_argument("--gt", default=None)
    ap.add_argument("--bench", action="store_true", help="跑真實遮擋 benchmark(robot_parts)")
    ap.add_argument("--manifest", default="/tmp/robot_parts/manifest.json")
    ap.add_argument("--pieces", default="/tmp/robot_parts")
    a = ap.parse_args()
    if a.bench:
        rows = bench(a.manifest, a.pieces)
        print(json.dumps(rows, ensure_ascii=False, indent=1))
        return
    cand = cv2.imread(a.cand, cv2.IMREAD_UNCHANGED)
    hole = cv2.imread(a.hole, cv2.IMREAD_UNCHANGED)
    hole = (hole if hole.ndim == 2 else hole[..., -1]) > 0
    gt = cv2.imread(a.gt, cv2.IMREAD_UNCHANGED) if a.gt else None
    rep = evaluate(cand, hole, gt)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
