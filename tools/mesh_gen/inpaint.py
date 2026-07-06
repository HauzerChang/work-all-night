#!/usr/bin/env python3
"""S4 補圖(occlusion inpainting)—— 純 CPU 基線。

工作流(使用者定義):切圖定出區塊後,被上層遮住的下層(如 dj_cat「身體」被「耳機右罩」蓋住)
在被遮區缺像素;動起來上層一移就露破洞 → 需補圖把下層被遮區「畫全」。

本工具:給一張下層件 RGBA + 一個「要補的區域(fill mask)」→ 用周邊已知像素把該區補上、
alpha 設為不透明。方法為 CPU 基線(對應 Spine能力鍛鍊計畫 S4 降階梯的第 2 階);
降階梯:① 邊緣外擴(extend)② cv2.inpaint(telea/ns,本檔)③ LaMa ④ GPU/人工。

⚠️ 補圖品質一律交給 `inpaint_eval.py`(補圖閘)量化把關,不靠肉眼。
"""
import argparse, os
import numpy as np
import cv2

METHODS = ("telea", "ns", "extend")


def complete_layer(rgba, fill_mask, method="telea", radius=3):
    """把 fill_mask 標示的區域用周邊已知像素補起來。
    rgba: HxWx4 uint8;fill_mask: HxW {0,1}(要補的像素)。回傳補好的 rgba。"""
    rgb = rgba[..., :3].copy()
    alpha = rgba[..., 3].copy()
    m = (fill_mask > 0).astype(np.uint8)
    if m.sum() == 0:
        return rgba.copy()

    if method == "extend":
        # 邊緣外擴:distance-transform 取最近『已知』像素的顏色(最便宜的降階第①階)
        known = (m == 0).astype(np.uint8)
        # 每個未知像素 → 最近已知像素索引
        _, labels = cv2.distanceTransformWithLabels(
            1 - known, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
        ys, xs = np.where(known > 0)
        lut = np.zeros(labels.max() + 1, dtype=np.int64)
        lut[labels[known > 0]] = ys * rgb.shape[1] + xs
        flat = rgb.reshape(-1, 3)
        filled = flat[lut[labels].reshape(-1)].reshape(rgb.shape)
        rgb = np.where(m[..., None] > 0, filled, rgb)
    else:
        flag = cv2.INPAINT_NS if method == "ns" else cv2.INPAINT_TELEA
        rgb = cv2.inpaint(rgb, m, radius, flag)

    alpha = np.where(m > 0, 255, alpha).astype(np.uint8)
    return np.dstack([rgb, alpha])


def occlusion_mask(lower_alpha, upper_alpha, grow=12):
    """啟發式『真實破洞』:被上層遮住、下層目前透明、但下層內容合理會延伸到的區域。
      = 上層不透明 ∩ 下層透明 ∩ 膨脹(下層不透明, grow px)
    只標『缺的』像素(不含下層已畫好的區,避免覆寫好內容)。
    ⚠️ 『延伸多遠(grow)』是美術決定(無唯一解)—— grow 給保守起點;
    端到端需以真實重疊檔(dj_cat)校準,見 knowledge/s4-inpaint-evaluator.md。"""
    lo = (lower_alpha > 8).astype(np.uint8)
    up = (upper_alpha > 8).astype(np.uint8)
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * grow + 1, 2 * grow + 1))
    near = cv2.dilate(lo, k)
    return ((up > 0) & (lo == 0) & (near > 0)).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("layer_png", help="下層件 RGBA PNG")
    ap.add_argument("fill_mask_png", help="要補區域的遮罩 PNG(非零=補)")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--method", choices=METHODS, default="telea")
    ap.add_argument("--radius", type=int, default=3)
    a = ap.parse_args()
    rgba = cv2.cvtColor(cv2.imread(a.layer_png, cv2.IMREAD_UNCHANGED), cv2.COLOR_BGRA2RGBA)
    fm = cv2.imread(a.fill_mask_png, cv2.IMREAD_GRAYSCALE)
    res = complete_layer(rgba, fm, a.method, a.radius)
    out = a.out or (os.path.splitext(a.layer_png)[0] + f"_filled_{a.method}.png")
    cv2.imwrite(out, cv2.cvtColor(res, cv2.COLOR_RGBA2BGRA))
    print(f"[{a.method}] {out}: 補 {int((fm>0).sum())} px")


if __name__ == "__main__":
    main()
