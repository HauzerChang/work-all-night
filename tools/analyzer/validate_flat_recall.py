#!/usr/bin/env python3
"""平圖拆件 baseline 對真值校驗 — 把分層 PSD 壓平成單張平圖,自動拆件,
再拿『已知的 PSD 圖層』當真值量召回/精度/破碎度。

這直接量化「沒有分層、只有平圖」時自動拆件差多少 —— S1 件召回率的最難情境。
真值 = PSD 各 leaf 圖層在畫布座標的 alpha 遮罩。
匹配:每個真值件 → 取與它 IoU 最高的候選件;IoU>=recover_thresh 視為『成功召回』。
"""
import argparse, json, os, sys
import numpy as np
import cv2
from PIL import Image
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
from psd_slice import slice_psd
from segment_flat import propose_parts


def true_masks(psd_path):
    psd, manifest, parts = slice_psd(psd_path)
    W, H = psd.width, psd.height
    out = []
    for e, im in parts:
        a = np.array(im.split()[-1]) > 8
        m = np.zeros((H, W), bool)
        l, t = e["offset"]; hh, ww = a.shape
        m[t:t + hh, l:l + ww] = a
        out.append((e["name"], m))
    return psd, out, W, H


def flatten_rgba(psd_path):
    psd, _, _ = slice_psd(psd_path)
    comp = psd.composite().convert("RGBA")
    arr = np.array(comp)                                  # RGBA
    bgr = cv2.cvtColor(arr, cv2.COLOR_RGBA2BGRA)
    return bgr


def iou(a, b):
    return float(np.logical_and(a, b).sum() / max(np.logical_or(a, b).sum(), 1))


def validate(psd_path, k, recover_thresh):
    psd, tmasks, W, H = true_masks(psd_path)
    flat = flatten_rgba(psd_path)
    summary, cands, fgmask = propose_parts(flat, k=k)
    cand_masks = [c["mask"] for c in cands]

    per_true = []
    recovered = 0
    used = set()
    for name, tm in tmasks:
        best_iou, best_j = 0.0, -1
        for j, cm in enumerate(cand_masks):
            v = iou(tm, cm)
            if v > best_iou:
                best_iou, best_j = v, j
        ok = best_iou >= recover_thresh
        recovered += int(ok)
        if best_j >= 0:
            used.add(best_j)
        per_true.append({"true_part": name, "best_iou": round(best_iou, 3),
                         "recovered": ok})
    recall = recovered / max(len(tmasks), 1)
    precision = len(used) / max(len(cand_masks), 1)       # 候選中對到真值件的比例
    frag = len(cand_masks) / max(len(tmasks), 1)
    rep = {
        "source": os.path.basename(psd_path),
        "n_true_parts": len(tmasks), "n_candidates": len(cand_masks),
        "seg_summary": summary,
        "recall@%.2f" % recover_thresh: round(recall, 3),
        "precision": round(precision, 3),
        "fragmentation(cand/true)": round(frag, 2),
        "per_true_part": per_true,
        "finding": ("平圖自動拆件可用" if recall >= 0.8 else
                    f"平圖自動拆件僅召回 {recovered}/{len(tmasks)} 語意件(IoU>={recover_thresh}) "
                    f"→ 同材質/重疊件靠顏色分不出;佐證需分層 PSD 或人工拆件"),
    }
    # 交叉檢查:decomposability 分數是否正確預測(低召回應對低分)
    rep["decomposability_predicts_failure"] = (
        (recall < 0.8) == (summary["decomposability"] < 0.6))
    return rep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("-k", type=int, default=6)
    ap.add_argument("--recover-thresh", type=float, default=0.5)
    a = ap.parse_args()
    rep = validate(a.psd, a.k, a.recover_thresh)
    print(json.dumps(rep, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
