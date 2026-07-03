#!/usr/bin/env python3
"""W1 切圖評分器 — 候選分件 PSD vs 美術真值 PSD 的量化評分(0~100)。

依 knowledge/s4-slicing-gap-analysis.md 的五個差距維度計分:
  1. **召回**(30):真值件被匹配的比例(一對一 Hungarian,IoU≥0.3 才算配對)。
     粒度不足(臉部套件沒切)直接反映在此。
  2. **對應品質 IoU**(25):配對件的平均 IoU(邊線/範圍準不準)。
  3. **邊界 chamfer**(15):配對件的平均對稱邊界距離(px),20px 以上得 0。
  4. **完整性**(15):配對件的 min(1, 候選面積/真值面積) 平均 — 抓「互斥掏空」
     (AI v4 的頭 0.57)。過大不罰(過大由 IoU 罰)。
  5. **重疊冗餘**(10):候選冗餘度(Σ件/聯集)與真值(1.408)的接近度 —
     抓「件=完整物件、被蓋處畫全」的架構差距。
  6. **過切懲罰**(5):候選件配不到真值的比例(美術不切髮/轉盤 → AI 多切要罰)。

AC(--selftest):真值自比對 = 100;AI v4 = 低分(已知壞例=負對照);
擾動負對照(刪件→召回降、平移件→IoU/chamfer 降)可被抓到。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
import numpy as np
import cv2
from psd_tools import PSDImage
from scipy.optimize import linear_sum_assignment

MATCH_IOU = 0.3


def leaf_alphas(path):
    """可見 leaf 圖層 → {name: bool alpha(canvas)},名稱含群組路徑;回傳 (dict, 由下而上序, size)。"""
    psd = PSDImage.open(path)
    W, H = psd.width, psd.height
    out, order = {}, []

    def walk(layers, prefix):
        for l in layers:
            if not l.is_visible():
                continue
            if l.is_group():
                walk(l, prefix + l.name + "/")
                continue
            im = l.topil()
            if im is None:
                continue
            if im.mode != "RGBA":
                im = im.convert("RGBA")
            a = np.zeros((H, W), bool)
            lft, top = int(l.left), int(l.top)
            x0, y0 = max(lft, 0), max(top, 0)
            x1, y1 = min(lft + im.width, W), min(top + im.height, H)
            if x1 > x0 and y1 > y0:
                a[y0:y1, x0:x1] = np.array(im)[y0 - top:y1 - top, x0 - lft:x1 - lft, 3] > 8
            key = prefix + l.name
            i = 2
            while key in out:
                key = f"{prefix}{l.name}#{i}"; i += 1
            out[key] = a
            order.append(key)
    walk(psd, "")
    return out, order, (W, H)


def _chamfer(a, b):
    ea = cv2.morphologyEx(a.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    eb = cv2.morphologyEx(b.astype(np.uint8), cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)) > 0
    if not ea.any() or not eb.any():
        return 999.0
    da = cv2.distanceTransform((~ea).astype(np.uint8), cv2.DIST_L2, 3)
    db = cv2.distanceTransform((~eb).astype(np.uint8), cv2.DIST_L2, 3)
    return float((db[ea].mean() + da[eb].mean()) / 2)


def _redundancy(d, size):
    stack = np.zeros(size[::-1], np.int32)
    for a in d.values():
        stack += a
    u = (stack > 0).sum()
    return float(stack.sum() / max(u, 1))


def evaluate(cand_psd, gt_psd):
    cand, _, size = leaf_alphas(cand_psd)
    gt, _, size2 = leaf_alphas(gt_psd)
    assert size == size2, f"畫布不一致 {size} vs {size2}"
    cn, gn = list(cand), list(gt)

    # IoU 矩陣 + Hungarian(最大化 IoU)
    M = np.zeros((len(cn), len(gn)))
    for i, c in enumerate(cn):
        ca = cand[c]
        if not ca.any():
            continue
        for j, g in enumerate(gn):
            inter = (ca & gt[g]).sum()
            if inter:
                M[i, j] = inter / np.logical_or(ca, gt[g]).sum()
    ri, cj = linear_sum_assignment(-M)
    pairs = [(cn[i], gn[j], M[i, j]) for i, j in zip(ri, cj) if M[i, j] >= MATCH_IOU]

    matched_gt = {g for _, g, _ in pairs}
    matched_cand = {c for c, _, _ in pairs}
    recall = len(matched_gt) / len(gn)
    precision = len(matched_cand) / max(len(cn), 1)

    per = []
    for c, g, iou in pairs:
        ch = _chamfer(cand[c], gt[g])
        comp = min(1.0, cand[c].sum() / max(gt[g].sum(), 1))
        per.append({"cand": c, "gt": g, "iou": round(float(iou), 3),
                    "chamfer_px": round(ch, 1), "completeness": round(float(comp), 3)})
    mean_iou = float(np.mean([p["iou"] for p in per])) if per else 0.0
    mean_ch = float(np.mean([p["chamfer_px"] for p in per])) if per else 999.0
    mean_comp = float(np.mean([p["completeness"] for p in per])) if per else 0.0
    red_c = _redundancy(cand, size)
    red_g = _redundancy(gt, size)

    s_recall = recall * 30
    s_iou = mean_iou * 25
    s_ch = max(0.0, 1 - mean_ch / 20) * 15
    s_comp = mean_comp * 15
    s_red = max(0.0, 1 - abs(red_c - red_g) / 0.5) * 10
    s_prec = precision * 5
    score = s_recall + s_iou + s_ch + s_comp + s_red + s_prec

    unmatched_gt = [g for g in gn if g not in matched_gt]
    overcut = [c for c in cn if c not in matched_cand]
    return {
        "score": round(score, 1),
        "breakdown": {"recall": round(s_recall, 1), "iou": round(s_iou, 1),
                      "chamfer": round(s_ch, 1), "completeness": round(s_comp, 1),
                      "redundancy": round(s_red, 1), "precision": round(s_prec, 1)},
        "metrics": {"gt_pieces": len(gn), "cand_pieces": len(cn), "matched": len(pairs),
                    "recall": round(recall, 3), "precision": round(precision, 3),
                    "mean_iou": round(mean_iou, 3), "mean_chamfer_px": round(mean_ch, 1),
                    "mean_completeness": round(mean_comp, 3),
                    "redundancy_cand": round(red_c, 3), "redundancy_gt": round(red_g, 3)},
        "pairs": per,
        "unmatched_gt": unmatched_gt,
        "overcut_cand": overcut,
    }


# ---------- selftest:正對照 + 擾動負對照 ----------
def _perturb(gt_psd, mode, tmp):
    """產生擾動版 GT PSD:drop(刪最大件)/ shift(平移一件 12px)。"""
    from PIL import Image
    psd = PSDImage.open(gt_psd)
    W, H = psd.width, psd.height
    new = PSDImage.new("RGBA", (W, H))
    new._background_color = None
    leaves = [l for l in psd.descendants() if not l.is_group() and l.is_visible()]
    areas = []
    for l in leaves:
        im = l.topil().convert("RGBA")
        areas.append((np.array(im)[..., 3] > 8).sum())
    big = int(np.argmax(areas))
    for i, l in enumerate(leaves):
        if mode == "drop" and i == big:
            continue
        dx = 12 if mode == "shift" else 0        # shift = 全件平移(全域錯位;單移大件會被 40 對平均稀釋)
        im = l.topil().convert("RGBA")
        lyr = new.create_pixel_layer(im, name="tmp", top=int(l.top), left=int(l.left) + dx)
        lyr.name = l.name
    new.save(tmp)
    return tmp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cand", default="acceptance/dj_cat_ai_sliced.psd")
    ap.add_argument("--gt", default="assets/dj_cat_artist.psd")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if not a.selftest:
        rep = evaluate(a.cand, a.gt)
        print(json.dumps(rep, ensure_ascii=False, indent=1))
        return
    ok = True
    full = evaluate(a.gt, a.gt)
    print(f"正對照 GT vs GT: score={full['score']}(期望 100)")
    ok &= full["score"] >= 99.9
    ai = evaluate(a.cand, a.gt)
    print(f"AI v4 vs GT:   score={ai['score']} breakdown={ai['breakdown']}")
    ok &= ai["score"] < 70
    for mode, dims in [("drop", "recall"), ("shift", "iou/chamfer")]:
        t = _perturb(a.gt, mode, f"/tmp/_gt_{mode}.psd")
        r = evaluate(t, a.gt)
        caught = r["score"] < full["score"] - 1
        print(f"負對照 {mode}(動 {dims}): score={r['score']} caught={caught}")
        ok &= caught
    print("SELFTEST", "PASS" if ok else "FAIL")
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
