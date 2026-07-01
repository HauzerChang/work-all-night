#!/usr/bin/env python3
"""S2 補圖閘(自我品質閘) — 量化「遮擋補圖」的完整度與接縫,補齊 S2 評估器套件最後一塊。

S4 補圖分級降階(PLAN:邊緣外擴→cv2→LaMa→GPU/人工)需要一個機讀閘來判「補得夠不夠好、要不要升級」。
本閘純 CPU、兩種模式:

  盲測(production,無真值):
    - unfilled_ratio  : 補完後 hole 區仍透明(alpha≤8)的比例 → 應為 0(補圖必須把洞填滿)。
    - seam_score      : hole 邊界環帶的梯度均值 / 內部基準梯度 → 偵測明顯接縫(越低越好)。
  對照(self-test,有真值):
    - gt_premult_mae  : 對原圖(真值)在 hole 區的 premultiplied-RGB MAE。

附 cv2 baseline 補圖(Telea)以驗證閘;真實 pipeline 可換更強的補圖器,閘不變。
"""
import argparse, os, sys, json
import numpy as np
import cv2


def synth_occlusion(img, rect):
    """在 RGBA 圖挖一個矩形洞(alpha=0,rgb=0),回傳 (occluded, hole_mask)。rect=(x,y,w,h)。"""
    occ = img.copy()
    x, y, w, h = rect
    hole = np.zeros(img.shape[:2], np.uint8)
    hole[y:y + h, x:x + w] = 1
    occ[y:y + h, x:x + w, :] = 0
    return occ, hole


def inpaint_cv2(occ, hole_mask, radius=3):
    """cv2 Telea 補 RGB;hole 區 alpha 補回不透明(以原件輪廓為界)。"""
    rgb = occ[:, :, :3].astype(np.uint8)
    filled = cv2.inpaint(rgb, (hole_mask * 255).astype(np.uint8), radius, cv2.INPAINT_TELEA)
    out = occ.copy()
    out[:, :, :3] = filled
    out[hole_mask > 0, 3] = 255
    return out


def _grad_mag(rgb):
    g = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_BGR2GRAY)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0); gy = cv2.Sobel(g, cv2.CV_32F, 0, 1)
    return np.hypot(gx, gy)


def evaluate_inpaint(result, hole_mask, original=None,
                     unfilled_thresh=0.0, seam_thresh=3.0, mae_thresh=25.0):
    a = result[:, :, 3]
    hole = hole_mask > 0
    # 1) 完整度:hole 區仍透明的比例
    unfilled = float(np.logical_and(hole, a <= 8).sum() / max(int(hole.sum()), 1))

    # 2) 接縫:hole 邊界環帶梯度 vs 內部基準
    ring = cv2.dilate(hole_mask, np.ones((5, 5), np.uint8)) - cv2.erode(hole_mask, np.ones((5, 5), np.uint8))
    gm = _grad_mag(result[:, :, :3])
    content = a > 8
    interior = np.logical_and(content, hole_mask == 0)
    ring_g = float(gm[ring > 0].mean()) if (ring > 0).any() else 0.0
    base_g = float(gm[interior].mean()) if interior.any() else 1.0
    seam = ring_g / max(base_g, 1e-6)

    res = {
        "AC1_filled": {"pass": unfilled <= unfilled_thresh, "unfilled_ratio": round(unfilled, 5)},
        "AC2_seam": {"pass": seam <= seam_thresh, "seam_score": round(seam, 3), "thresh": seam_thresh},
    }
    if original is not None:
        oa = original[:, :, :3].astype(np.float64) * (original[:, :, 3:4] / 255.0)
        ra = result[:, :, :3].astype(np.float64) * (result[:, :, 3:4] / 255.0)
        mae = float(np.abs(oa - ra)[hole].mean())
        res["AC3_gt_mae"] = {"pass": mae <= mae_thresh, "premult_mae": round(mae, 3), "thresh": mae_thresh}
    return {"overall_pass": all(v["pass"] for v in res.values()), "criteria": res}


def _hole_rect(W, H, frac):
    hw, hh = int(W * frac), int(H * frac)
    return (W // 2 - hw // 2, H // 2 - hh // 2, hw, hh)


def _fill_gt(occ, hole, original, sigma=5.0):
    """以真值+微噪補洞 — 模擬「強補圖器(LaMa/人工)重建良好」,供驗證閘接受好補圖。
    (確定性:噪聲用固定 seed 網格擾動,不用 RNG。)"""
    out = occ.copy()
    ys, xs = np.where(hole > 0)
    noise = (np.sin(xs * 0.7) + np.cos(ys * 0.7)) * sigma  # 確定性擾動
    for c in range(3):
        vals = original[ys, xs, c].astype(np.float64) + noise
        out[ys, xs, c] = np.clip(vals, 0, 255).astype(np.uint8)
    out[hole > 0, 3] = 255
    return out


def _demo(part_png):
    """驗證閘鑑別力:沿補圖能力梯(強補圖→過 / cv2 紋理區→升級 / 不補→缺)三態應可分。"""
    img = cv2.imread(part_png, cv2.IMREAD_UNCHANGED)
    if img.shape[2] == 3:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2BGRA)
    H, W = img.shape[:2]

    def run(label, frac, filler):
        occ, hole = synth_occlusion(img, _hole_rect(W, H, frac))
        result = filler(occ, hole) if filler else occ
        rep = evaluate_inpaint(result, hole, original=img)
        c = rep["criteria"]
        print(f"{label:30} overall={rep['overall_pass']!s:5} | "
              f"filled={c['AC1_filled']['pass']!s:5}(unfilled {c['AC1_filled']['unfilled_ratio']}) | "
              f"seam={c['AC2_seam']['seam_score']} | mae={c['AC3_gt_mae']['premult_mae']}")
        return rep

    print("補圖能力梯(閘鑑別力驗證):")
    a = run("強補圖(GT+微噪,擬 LaMa)", 0.15, lambda o, h: _fill_gt(o, h, img))  # 期望 PASS
    b = run("cv2 Telea(紋理區)", 0.15, inpaint_cv2)                              # 期望 升級(MAE 高)
    c = run("不補圖(留洞)", 0.15, None)                                          # 期望 缺(AC1 FAIL)
    ok = (a["overall_pass"] and (not b["criteria"]["AC3_gt_mae"]["pass"])
          and (not c["criteria"]["AC1_filled"]["pass"]))
    print(f"\n閘鑑別力(強補圖過 / cv2 紋理升級 / 留洞缺,三態可分): {ok}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("part_png", help="一張 RGBA 件(demo:沿補圖降階梯驗證閘鑑別力)")
    a = ap.parse_args()
    ok = _demo(a.part_png)
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
