#!/usr/bin/env python3
"""S4 補圖閘(inpainting evaluator)—— 補圖能力的自我品質閘(樞紐)。

對應 PLAN S4 完成條件:「補圖極端姿態幀 0 破洞 / 0 明顯接縫」。機讀判準:
  ① 破洞(hole_fill):要補的區域補完後不透明比例(=1 → 0 破洞)。            [免真值,可部署]
  ② 接縫(seam_ratio):補區邊界的影像梯度 ÷ 已知區自然紋理梯度中位數。       [免真值,可部署]
     補圖若順著周邊延伸 → ~1;硬填(flat/noise)→ 邊界跳變 → >>1。
  ③ 保真(fidelity,PSNR/MAE):僅『合成遮擋+已知真值』校準時可算(部署時被遮區本就沒真值)。
     用途:證明免真值的 ①②真的能追蹤品質(校準/負對照)。

⚠️ RULES:評估器要先校準 + 負對照才可信(本專案評估器已 3 次 miscalibration)。
   `--calibrate <layer.png>`:對一張完整層合成遮擋,跑 telea/ns vs 負對照(noop/flat/noise),
   印出鑑別表 —— 好補圖過、三個對照各自在對的軸上 fail,才證明閘可信。

門檻(校準得出,見 knowledge/s4-inpaint-evaluator.md):hole_fill≥0.999、seam_ratio≤3.0。
真實補圖 seam 1.8~1.9、硬填 10~12,>5× 分離 → 3.0 有充裕邊際。
"""
import argparse, json, os, sys
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(__file__))
from inpaint import complete_layer

HOLE_FILL_MIN = 0.999
SEAM_RATIO_MAX = 1.5      # 校準:好補圖 0.64~0.68、硬填 2.2~6.4(flat/textured 兩層皆然)→ 1.5 乾淨分開
JND_FLOOR = 40.0         # 平坦區的自然梯度下限(Sobel-mag 尺度),避免除以≈0 爆炸
PSNR_MIN = 11.0          # 校準用:區分好補圖 vs 對照


def _sobel_mag(gray):
    gx = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
    return np.sqrt(gx * gx + gy * gy)


def seam_ratio(result_rgb, fill_mask, known_mask):
    """補區邊界梯度 ÷ 洞周邊『已知窄環(3~15px)』的自然紋理梯度(以 JND_FLOOR 設下限)。
    known_mask=補前已畫(不含 fill)。用『局部』紋理當分母(非全域)→ 洞落在平坦區時
    才不會被層內他處強邊界灌水;JND_FLOOR 讓純平坦區的硬填仍會 fail。"""
    k = np.ones((3, 3), np.uint8)
    fm = (fill_mask > 0).astype(np.uint8)
    ring = (cv2.dilate(fm, k) - cv2.erode(fm, k)).astype(bool)
    ann = ((cv2.dilate(fm, k, iterations=15) - cv2.dilate(fm, k, iterations=3)) > 0) & (known_mask > 0)
    g = _sobel_mag(cv2.cvtColor(result_rgb, cv2.COLOR_RGB2GRAY).astype(np.float32))
    if not ring.any() or not ann.any():
        return float("nan")
    local = float(g[ann].mean())
    return float(g[ring].mean() / max(local, JND_FLOOR))


def evaluate(result_rgba, fill_mask, known_alpha, gt_rgb=None):
    """result_rgba: 補完的 RGBA;fill_mask: 要補區;known_alpha: 補前該層 alpha。
    gt_rgb: 有真值時(校準)才傳 → 額外算 fidelity。"""
    fm = (fill_mask > 0)
    res_rgb = result_rgba[..., :3]
    res_a = result_rgba[..., 3]
    hole_fill = float((res_a[fm] > 8).mean()) if fm.any() else 1.0
    sr = seam_ratio(res_rgb, fill_mask, known_alpha) if hole_fill > 0 else float("inf")

    crit = {
        "AC1_no_hole": {"pass": hole_fill >= HOLE_FILL_MIN,
                        "hole_fill": round(hole_fill, 4), "thresh": HOLE_FILL_MIN},
        "AC2_no_seam": {"pass": (sr <= SEAM_RATIO_MAX),
                        "seam_ratio": (round(sr, 3) if np.isfinite(sr) else None),
                        "thresh": SEAM_RATIO_MAX},
    }
    if gt_rgb is not None and fm.any():
        diff = res_rgb[fm].astype(np.float32) - gt_rgb[fm].astype(np.float32)
        mae = float(np.abs(diff).mean())
        psnr = float(10 * np.log10(255 ** 2 / (float((diff ** 2).mean()) + 1e-9)))
        crit["AC3_fidelity"] = {"pass": psnr >= PSNR_MIN, "psnr": round(psnr, 2),
                                "mae": round(mae, 2), "thresh_psnr": PSNR_MIN}
    overall = all(c["pass"] for c in crit.values())
    return {"overall_pass": overall, "criteria": crit}


# ---- 校準:合成遮擋 + 負對照 ----
def _load_rgba(path):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im.ndim == 3 and im.shape[2] == 4:
        return cv2.cvtColor(im, cv2.COLOR_BGRA2RGBA)
    return cv2.cvtColor(im, cv2.COLOR_BGR2RGBA)


def calibrate(layer_png, radius_frac=0.11):
    rgba = _load_rgba(layer_png)
    rgb, alpha = rgba[..., :3], rgba[..., 3]
    opaque = (alpha > 8).astype(np.uint8)
    ys, xs = np.where(opaque > 0)
    cy, cx = int(ys.mean()), int(xs.mean())
    R = int(radius_frac * np.sqrt(opaque.sum()))
    hole = np.zeros(alpha.shape, np.uint8)
    cv2.circle(hole, (cx, cy), R, 1, -1)
    hole = (hole & opaque).astype(np.uint8)     # 洞在內部,四周有真值

    occ = rgba.copy()
    occ[..., :3][hole > 0] = 0
    occ[..., 3][hole > 0] = 0
    known_alpha = occ[..., 3]

    def run(method):
        if method == "noop":
            return occ.copy()
        if method == "flat":
            r = occ.copy(); r[..., :3][hole > 0] = 128; r[..., 3][hole > 0] = 255; return r
        if method == "noise":
            r = occ.copy()
            n = (np.arange(int(hole.sum()) * 3) * 2654435761 % 256).astype(np.uint8).reshape(-1, 3)
            r[..., :3][hole > 0] = n; r[..., 3][hole > 0] = 255; return r
        return complete_layer(occ, hole, method)

    report = {"layer": os.path.basename(layer_png), "hole_px": int(hole.sum()), "methods": {}}
    good, bad_caught = [], []
    for m in ("telea", "ns", "extend", "noop", "flat", "noise"):
        res = run(m)
        rep = evaluate(res, hole, known_alpha, gt_rgb=rgb)
        report["methods"][m] = rep
        is_real = m in ("telea", "ns", "extend")
        if is_real and rep["overall_pass"]:
            good.append(m)
        if (not is_real) and (not rep["overall_pass"]):
            bad_caught.append(m)
    report["discriminates"] = (len(good) >= 1 and bad_caught == ["noop", "flat", "noise"])
    return report


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd")
    apc = ap.add_argument_group()
    ap.add_argument("--calibrate", metavar="LAYER_PNG", default=None,
                    help="對完整層合成遮擋做校準 + 負對照(印鑑別表)")
    a = ap.parse_args()
    if a.calibrate:
        rep = calibrate(a.calibrate)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        raise SystemExit(0 if rep["discriminates"] else 1)
    ap.error("用 --calibrate <layer.png>;部署時請 import evaluate()")


if __name__ == "__main__":
    main()
