#!/usr/bin/env python3
"""S4 候選 18(chunk 21):1b 補圖閘「邊界證據延續性」候選第 4 指標,一次性實測腳本。

背景(見 knowledge/s4-inpaint-1b-lenient-gate.md 候選 7、knowledge/s4-gptfill-plugin-knowledge.md §5):
chunk 18 用 Claude vision 發現機械紋理材質(身體/左手)的 CPU baseline 補丁雖然 1b(alpha_gap/
seam_ratio/tone_gap)全 pass,近看卻是一坨丟失高頻細節的「奶油糊」;chunk 19 讀到使用者的
Photoshop GPT Fill 插件 prompt 獨立佐證同一個失真維度,並給出更可操作的指標方向:不是籠統的
「細節保留度」,而是「洞內的亮度/梯度場有沒有延續邊界暗邊所暗示的走向」(SHADOW REASONING)。

本腳本把這個方向做成可量化的候選指標 `grad_continuity_gap`,**只用洞外已知像素**當預測依據
(延續 1b 自我參照精神,不看 gt、不看洞內填了什麼):
  1. 洞外已知亮度場算 Sobel 梯度(洞內先最近鄰暫填避免假邊緣,手法同 `estimate_alpha_taper`)。
  2. 洞內每個像素,用「最近的洞外已知像素」的亮度 + 該點局部梯度,做一階線性外推,當作
     「邊界證據暗示這裡應該長怎樣」的預測值。
  3. 只在貼近邊界的淺層(`probe_depth`,預設 6px)跟 recon 實際亮度比 MAE——線性外推對真實
     結構本來就只在幾 px 內可信,不奢求它能预测深處的真實細節。

**這是探測腳本,不動 `inpaint_eval.py` production 代碼**(候選 8 教訓:新指標要先校準過
才能信,不能先斬後奏塞進 `score_1b`/`THRESH_1B`)。用法見 `main()`。
"""
import argparse, json, os, sys

import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inpaint_eval import load_rgba, punch_hole, METHODS, score, score_1b, passes, passes_1b, _premult  # noqa: E402


def _luminance(rgba):
    return _premult(rgba).mean(axis=2)


def boundary_evidence_continuity(recon, mask, probe_depth=6):
    """回傳 {"grad_continuity_gap": float, "probe_px": int}。見檔頭說明。"""
    known = ~mask
    if mask.sum() == 0 or known.sum() == 0:
        return {"grad_continuity_gap": 0.0, "probe_px": 0}

    L = _luminance(recon)
    # 暫填洞內只為算梯度時邊界不要因洞內恆值產生假邊緣(手法同 estimate_alpha_taper)。
    _, ind_fill = ndimage.distance_transform_edt(~known, return_distances=True, return_indices=True)
    L_fill = L.copy()
    L_fill[mask] = L[tuple(ind_fill)][mask]

    gy = ndimage.sobel(L_fill, axis=0) / 8.0
    gx = ndimage.sobel(L_fill, axis=1) / 8.0

    probe = mask & (ndimage.distance_transform_edt(mask) <= probe_depth)
    if probe.sum() == 0:
        return {"grad_continuity_gap": 0.0, "probe_px": 0}

    # 每個洞內像素找最近的洞外已知像素 p,線性外推 L(p) + grad(p)·(q-p)。
    dist, ind = ndimage.distance_transform_edt(~known, return_distances=True, return_indices=True)
    yy, xx = np.mgrid[0:mask.shape[0], 0:mask.shape[1]]
    py, px = ind[0], ind[1]
    dy = (yy - py).astype(np.float64)
    dx = (xx - px).astype(np.float64)
    pred = L[py, px] + gy[py, px] * dy + gx[py, px] * dx

    gap = float(np.abs(pred - L)[probe].mean())
    return {"grad_continuity_gap": round(gap, 3), "probe_px": int(probe.sum())}


def run(path, mode, seed, probe_depth):
    gt = load_rgba(path)
    try:
        _, mask = punch_hole(gt, mode=mode, frac=0.12, seed=seed)
    except ValueError as e:
        return {"skipped": True, "reason": str(e)}
    holed = gt.copy()
    holed[mask] = 0
    content = gt[..., 3] > 8
    out = {}
    for name, fn in METHODS.items():
        recon = fn(holed, gt, mask)
        bec = boundary_evidence_continuity(recon, mask, probe_depth)
        s1a = score(recon, gt, mask)
        s1b = score_1b(recon, mask, content, mode=mode)
        out[name] = {
            "grad_continuity_gap": bec["grad_continuity_gap"],
            "probe_px": bec["probe_px"],
            "ssim": s1a["ssim"],
            "1a_pass": passes(s1a),
            "1b_pass": (passes_1b(s1b, mode) if s1b["applicable"] else None),
        }
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("images", nargs="+", help="RGBA PNG 件(如切件輸出)")
    ap.add_argument("--modes", nargs="+", default=["interior"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--probe-depth", type=int, default=6)
    a = ap.parse_args()

    report = {}
    for path in a.images:
        for mode in a.modes:
            key = f"{os.path.basename(path)}::{mode}"
            report[key] = run(path, mode, a.seed, a.probe_depth)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
