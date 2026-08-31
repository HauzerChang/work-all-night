#!/usr/bin/env python3
"""S4 候選 7(1b 閾值反向校準)—— 用 Claude 自身 vision 當「有沒有穿幫」人工標註的代理。

背景:`knowledge/s4-inpaint-1b-lenient-gate.md` 誠實界定過,1b 三指標
(alpha_gap/seam_ratio/tone_gap)的閾值是靠正負對照的數值分野訂定,不是靠人工「這樣補
看起來有沒有穿幫」的標註反過來校準——這一步一直沒有真人標註資料來源可用。RULES.md 明訂
「客觀項(角度/pose/輪廓/破圖)用 vision 自評」,「有沒有看得出破綻」屬於此類客觀視覺缺陷,
故用 Claude 自己讀圖判斷來代理缺失的人工標註,而非再猜一個門檻。

用法:先用 `inpaint_eval.py --modes interior -o <dir>` 對材質跑出
`{base}_interior_{method}.png` 全套(gt/none/random/nearest/cv2_telea/cv2_ns),
再用本檔把每個材質的洞附近裁切、疊棋盤格透明底、放大,橫向拼成一張比較圖,方便人眼/vision
直接盯著看,而非只看數字。

⚠️ 誠實限制(見 knowledge/s4-inpaint-1b-lenient-gate.md「候選 7」章節):這是「靜態、
獨立單一圖層、人工放大裁切、疊棋盤格」的觀察條件,不是 1b 真正要問的「動態動畫、真實
canvas 尺度、遮擋件移動瞬間」的觀察條件——只能當作比「單看數字」更強、但仍弱於真人在
真實動畫上標註的代理指標。不要拿這個腳本的輸出直接當作足以動閾值的證據;若某材質的
數字判定與這個代理判定明顯衝突,先懷疑是這個代理本身的限制(見上),再考慮改閾值。
"""
import argparse, os
import cv2
import numpy as np

METHODS_ORDER = ("gt", "none", "random", "nearest", "cv2_telea", "cv2_ns")


def load_rgba(path):
    im = cv2.imread(path, cv2.IMREAD_UNCHANGED)
    if im is None:
        raise FileNotFoundError(path)
    if im.shape[2] == 3:
        im = cv2.cvtColor(im, cv2.COLOR_BGR2BGRA)
    return im


def checkerboard(h, w, size=8):
    yy, xx = np.mgrid[0:h, 0:w]
    c = ((yy // size) + (xx // size)) % 2
    v = np.where(c == 0, 200, 230).astype(np.uint8)
    return np.repeat(v[..., None], 3, axis=2)


def composite_on_checker(rgba):
    bg = checkerboard(*rgba.shape[:2])
    a = rgba[..., 3:4].astype(np.float64) / 255.0
    rgb = rgba[..., :3].astype(np.float64)
    return (rgb * a + bg.astype(np.float64) * (1 - a)).astype(np.uint8)


def hole_bbox(orig, holed, pad, shape):
    mask = (orig[..., 3] > 8) & (holed[..., 3] <= 8)
    ys, xs = np.where(mask)
    if len(ys) == 0:
        raise ValueError("no hole detected between original/holed (mismatched inputs?)")
    y0, y1 = max(0, ys.min() - pad), min(shape[0], ys.max() + pad + 1)
    x0, x1 = max(0, xs.min() - pad), min(shape[1], xs.max() + pad + 1)
    return y0, y1, x0, x1


def build_compare_strip(indir, base, target_h=400, pad=15):
    """`indir` = inpaint_eval.py 的 -o 輸出目錄,`base` = '<檔名>_<mode>'(不含 _方法.png)。"""
    orig = load_rgba(os.path.join(indir, f"{base}_original.png"))
    holed = load_rgba(os.path.join(indir, f"{base}_holed.png"))
    y0, y1, x0, x1 = hole_bbox(orig, holed, pad, orig.shape[:2])
    factor = max(1, min(6, target_h // max(y1 - y0, 1)))

    panels, labels = [], []
    for m in METHODS_ORDER:
        p = os.path.join(indir, f"{base}_{m}.png")
        if not os.path.exists(p):
            continue
        crop = load_rgba(p)[y0:y1, x0:x1]
        comp = composite_on_checker(crop)
        comp = cv2.resize(comp, None, fx=factor, fy=factor, interpolation=cv2.INTER_NEAREST)
        panels.append(comp)
        labels.append(m)

    maxh = max(p.shape[0] for p in panels)
    strips = []
    for lab, p in zip(labels, panels):
        ph, pw = p.shape[:2]
        canvas = np.full((maxh + 30, pw, 3), 255, dtype=np.uint8)
        canvas[30:30 + ph, :] = p
        cv2.putText(canvas, lab, (4, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        strips.append(canvas)
        strips.append(np.full((maxh + 30, 4, 3), 128, dtype=np.uint8))
    return np.concatenate(strips, axis=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("indir", help="inpaint_eval.py -o 輸出目錄")
    ap.add_argument("base", help="檔名前綴,如 '03_身體_interior'")
    ap.add_argument("-o", "--out", required=True, help="輸出比較圖 PNG 路徑")
    a = ap.parse_args()
    strip = build_compare_strip(a.indir, a.base)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    cv2.imwrite(a.out, strip)
    print(a.out, strip.shape)


if __name__ == "__main__":
    main()
