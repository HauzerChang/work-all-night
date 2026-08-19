#!/usr/bin/env python3
"""平圖(未分層)自動拆件 baseline — 純 CPU(cv2 + scipy),無網路/GPU。

情境:拿不到分層 PSD,只有一張壓平的目標圖。目標:盡量反推候選可動件,餵給 analyze_target。
⚠️ 這是 baseline,不是萬靈丹:同材質角色(整片同色)靠顏色分不出語意件 —— 量化這個落差,
   正是「為何要催分層 PSD」的證據(見 validate_flat_recall.py)。

流程:
  1. 前景遮罩:有 alpha → alpha>閾;否則邊界主色 flood-fill 去背。
  2. 顏色量化(Lab k-means)+ 每色連通元件 → 候選區。
  3. 小區併入相鄰 / 丟棄 < min_area。
  4. decomposability 分數:預測平圖自動拆件是否可行(低分 → 應改要 PSD / 人工)。
"""
import argparse, json, os, sys
import numpy as np
import cv2
from scipy import ndimage


def foreground_mask(img):
    """回傳 (mask uint8{0,1}, rgb)。有 alpha 用 alpha;否則邊界主色 flood 去背。"""
    if img.ndim == 3 and img.shape[2] == 4:
        a = img[:, :, 3]
        rgb = cv2.cvtColor(img[:, :, :3], cv2.COLOR_BGRA2BGR) if img.shape[2] == 4 else img[:, :, :3]
        if (a > 8).mean() < 0.999:                     # alpha 真的有透明 → 直接用
            return (a > 8).astype(np.uint8), rgb
    else:
        rgb = img if img.ndim == 3 else cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    # 無 alpha:以四邊主色 flood(容差)去背
    h, w = rgb.shape[:2]
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]]).reshape(-1, 3)
    bg = np.median(border, axis=0)
    dist = np.linalg.norm(rgb.astype(np.int32) - bg, axis=2)
    fg = (dist > 30).astype(np.uint8)
    fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
    fg = ndimage.binary_fill_holes(fg).astype(np.uint8)
    return fg, rgb


def color_quantize(rgb, mask, k):
    lab = cv2.cvtColor(rgb, cv2.COLOR_BGR2LAB)
    ys, xs = np.where(mask > 0)
    if len(xs) < k:
        return None
    samp = lab[ys, xs].astype(np.float32)
    crit = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0)
    _, labels, _ = cv2.kmeans(samp, k, None, crit, 3, cv2.KMEANS_PP_CENTERS)
    lab_img = -np.ones(mask.shape, np.int32)
    lab_img[ys, xs] = labels.flatten()
    return lab_img


def propose_parts(img, k=6, min_area_frac=0.01):
    mask, rgb = foreground_mask(img)
    H, W = mask.shape
    fg_area = int(mask.sum())
    n_cc_fg, _ = cv2.connectedComponents(mask)          # 前景連通塊數(語意分不分得開的先兆)
    lab_img = color_quantize(rgb, mask, k)
    min_area = max(50, int(min_area_frac * fg_area))
    parts = []
    if lab_img is not None:
        for c in range(k):
            cm = (lab_img == c).astype(np.uint8)
            n, cc = cv2.connectedComponents(cm)
            for i in range(1, n):
                comp = (cc == i)
                a = int(comp.sum())
                if a < min_area:
                    continue
                ys, xs = np.where(comp)
                parts.append({"mask": comp, "area": a,
                              "bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())],
                              "color_cluster": c})
    parts.sort(key=lambda p: -p["area"])
    largest_frac = parts[0]["area"] / max(fg_area, 1) if parts else 1.0
    n_parts = len(parts)
    n_fg = int(n_cc_fg - 1)
    # decomposability(經 validate_flat_recall 校準):**唯一可靠**的自動拆件 = 前景的
    # 「不相連塊」——各自是獨立件。相連的同材質件(單一 blob)靠幾何/顏色分不出語意界線
    # (實測 robot 0/5、Symbol 0/18 召回)。故分數主要由 fg_components 決定:
    #   1 塊 → 0.2(單一 blob,語意拆件欠定,顏色分群僅過度分割,供人工起手)
    #   >=2 塊 → 0.5 起,每多一塊 +0.1(上限 +0.3);但顏色分群本身不保證語意召回。
    if n_fg <= 1:
        score = 0.2
    else:
        score = round(min(0.5 + 0.1 * (n_fg - 1), 0.8), 3)
    reliable_parts = n_fg if n_fg >= 2 else 0            # 可靠件 = 不相連塊
    verdict = ("平圖可嘗試自動拆件(存在不相連塊)" if score >= 0.6 else
               "平圖自動拆件不可靠:單一相連前景 → 顏色分群僅過度分割(非語意件)。"
               "建議索取分層 PSD / 人工拆件 /(未來)GPU 語意分層(SAM、See-Through)")
    return {"canvas": [W, H], "fg_area": fg_area, "fg_components": n_fg,
            "reliable_parts": reliable_parts,
            "n_color_candidates": n_parts, "largest_frac": round(largest_frac, 3),
            "decomposability": score, "verdict": verdict,
            "caveat": "顏色分群候選為『過度分割提案』,非語意可動件;需人工歸併或分層來源"}, parts, mask


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("-k", type=int, default=6)
    ap.add_argument("--out", default=None, help="輸出候選件遮罩 PNG 的目錄")
    a = ap.parse_args()
    img = cv2.imread(a.image, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise SystemExit(f"無法讀取: {a.image}")
    summary, parts, mask = propose_parts(img, a.k)
    if a.out:
        os.makedirs(a.out, exist_ok=True)
        for i, p in enumerate(parts):
            cv2.imwrite(os.path.join(a.out, f"cand_{i:02d}.png"), p["mask"].astype(np.uint8) * 255)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
