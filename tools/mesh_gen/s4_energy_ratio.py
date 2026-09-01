#!/usr/bin/env python3
"""S4 候選 16(a)(chunk 22):1b 補圖閘「局部高頻能量/方差比」候選第 4 指標,一次性實測腳本。

背景(見 knowledge/s4-inpaint-1b-lenient-gate.md 候選 16/18):chunk 18 用 vision 發現機械紋理
材質(身體/左手)的 CPU baseline 補丁雖然既有 1b 三指標(alpha_gap/seam_ratio/tone_gap)全 pass,
近看卻丟失周圍鋸齒面板的高頻細節,呈現「奶油糊」。chunk 21 試過「邊界證據延續性」(候選 18)
路線,結論:該路線的預測基準本身是「局部線性外推」,構造上偏向獎勵平滑,方向跟設計意圖相反、
不可用,並指出候選 16 原構想 (a)「洞內外高頻能量/局部方差比」在方向上更有機會成立——它問的是
「補丁的局部紋理能量夠不夠像周圍材質」,不是「補丁像不像一個平滑外推預測值」,不會因為獎勵
平滑而倒錯方向。

本腳本把 (a) 做成可量化候選指標 `energy_ratio`(**只測 interior 模式**,理由與範圍限制同既有
1b:edge 模式的洞邊界貼真實輪廓,套用 score_1b 的 local_ring 基準前需要先排除輪廓段落,超出
本次探測範圍,若 interior 校準通過再決定是否延伸):
  1. 局部高頻能量 = 局部方差(premultiplied 灰階,uniform_filter box 近似,手法同
     `inpaint_eval.ssim_region` 內部的 mu/var 計算慣例,不是新發明的統計量)。
  2. 洞側取 hole core(mask 內縮,避開邊界漸層帶——邊界附近 nearest/cv2 補丁天生會貼近真實
     邊緣像素,深入洞中段才是真正被抹平的區域;深度不夠時退回整個 mask)。
  3. 參照側複製 `score_1b` 的 `local_ring` 基準(mask 外環,寬度/半徑與既有 1b 完全一致,
     不重新發明基準幾何,以便跟既有已校準的 tone_gap/seam_ratio 同源可比)。
  4. energy_ratio = hole 能量 / ref 能量(ref 太小時用 eps 防除以零)。

**這是探測腳本,不動 `inpaint_eval.py` production 代碼**(候選 8/18 教訓:新指標要先校準過
才能信,不能先斬後奏塞進 `score_1b`/`THRESH_1B`)。用法見 `main()`。
"""
import argparse, json, os, sys

import numpy as np
from scipy import ndimage

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inpaint_eval import load_rgba, punch_hole, METHODS, score, score_1b, passes, passes_1b, _premult  # noqa: E402


def _local_variance(gray, win=5):
    mu = ndimage.uniform_filter(gray, win)
    sq = ndimage.uniform_filter(gray * gray, win)
    return np.clip(sq - mu * mu, 0, None)


def _local_ring(content, mask, width=3):
    """複製 `score_1b` 內 `local_ring` 的定義(見 inpaint_eval.py score_1b docstring 的
    baseline_grad 段落),不重新發明基準幾何——同一個環,才能跟既有 tone_gap/seam_ratio
    的已校準結論互相印證。"""
    ring = content & ~ndimage.binary_dilation(mask, iterations=width) \
        & ndimage.binary_dilation(mask, iterations=width + 12)
    if ring.sum() < 200:
        ring = content & ~ndimage.binary_dilation(mask, iterations=width)
    return ring


def energy_ratio(recon, mask, content, core_depth=3, win=5, width=3):
    """回傳 {"energy_ratio","hole_energy","ref_energy","hole_px","ref_px"}。見檔頭說明。"""
    if mask.sum() == 0:
        return {"energy_ratio": 1.0, "hole_energy": 0.0, "ref_energy": 0.0, "hole_px": 0, "ref_px": 0}
    gray = _premult(recon).mean(axis=2)
    var_map = _local_variance(gray, win)

    core = mask & (ndimage.distance_transform_edt(mask) > core_depth)
    if core.sum() < 20:
        core = mask
    ring = _local_ring(content, mask, width)

    hole_e = float(var_map[core].mean()) if core.sum() else 0.0
    ref_e = float(var_map[ring].mean()) if ring.sum() else 1e-6
    ratio = hole_e / max(ref_e, 1e-6)
    return {"energy_ratio": round(ratio, 4), "hole_energy": round(hole_e, 3),
            "ref_energy": round(ref_e, 3), "hole_px": int(core.sum()), "ref_px": int(ring.sum())}


def run(path, mode, seed):
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
        er = energy_ratio(recon, mask, content)
        s1a = score(recon, gt, mask)
        s1b = score_1b(recon, mask, content, mode=mode)
        out[name] = {
            "energy_ratio": er["energy_ratio"],
            "hole_energy": er["hole_energy"],
            "ref_energy": er["ref_energy"],
            "hole_px": er["hole_px"],
            "ref_px": er["ref_px"],
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
    a = ap.parse_args()

    report = {}
    for path in a.images:
        for mode in a.modes:
            key = f"{os.path.basename(path)}::{mode}"
            report[key] = run(path, mode, a.seed)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
