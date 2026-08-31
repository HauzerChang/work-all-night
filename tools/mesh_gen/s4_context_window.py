#!/usr/bin/env python3
"""S4 候選 19:上下文假設重測 — CPU baseline 加大輸入上下文是否能改變 1a 判定。

背景(見 STATE_S4.md 候選 19 / `knowledge/s4-gptfill-plugin-knowledge.md`):使用者自製
Photoshop GPT-Fill 插件給生成模型的重建上下文下限是 **512px**,而 `inpaint_eval.py`
從頭到尾只吃 `psd_slice.py` 切出的、緊裁到單一圖層 bbox 的孤立 PNG——零周圍上下文。
「機械紋理材質(身體/左手)1a 全 fail」這個貫穿 S4 的核心結論,是在這個「只看單層」
條件下量出來的,尚未驗證過是不是「裁太緊」的人工產物。

本檔直接測:把同一個洞嵌進「該層 + 周圍 PSD composite(其他圖層/畫布範圍)當背景」的
更大畫布(比照插件 512px 下限),重跑既有三個 CPU baseline(`nearest`/`cv2_telea`/`cv2_ns`),
與孤立裁切版本做**同一顆隨機洞**的配對比較,量化洞區分數是否改變。

方法論的關鍵前提(先驗證,見 `calibration` 區塊,不能先信任結果):
  1. 該層在「context canvas」中的實際像素,必須與獨立切出的 gt 像素一致(否則「加上下文」
     這個操作本身就把 gt 換了,比較不公平)。
  2. 洞的 mask 用同一個 `punch_hole(seed=...)` 呼叫產生一次,分別套進「孤立裁切」與「大
     畫布視窗」兩種輸入,確保兩邊是同一顆洞、唯一變因是周圍上下文的有無。

⚠️ **踩到兩層坑(先跑過才發現,兩輪修正,細節見 `load_layer_and_context()` docstring 與
`knowledge/s4-inpaint-context-window.md`)**:(1)第一版直接用 `psd.composite()` 當上下文
畫布——錯的,composite 是全部圖層依 z-order 疊完的最終結果,目標層若被後畫(z 更高)的
圖層局部蓋住,composite 顯示的是蓋在上面那層的顏色,`calibration` 直接炸開(`光暈`
premult_mae 87.7)。(2)改成「只疊 z 序在目標層之前的圖層 + `alpha_composite` 貼回目標層」
仍不完全過(`身體`/`左手` fringe alpha_mae 117~123,集中在抗鋸齒半透明邊緣,因為疊圖公式
本身就會在半透明像素疊到不透明背景時把 alpha 推高,這是場景合成的正確結果但語意上不等於
「圖層自身 alpha」)。**最終做法**:bbox 內部直接硬覆蓋成 gt(不經 alpha 混合),bbox 以外
才用「較底層圖層疊成的背景」——兩者語意各自正確,6 案例 calibration 逐位元通過。

跑法:`python3 s4_context_window.py assets/robot_parts.psd 身體 左手 光暈 --modes interior edge`
(光暈已知 1a pass,當回歸檢查:上下文不該讓已經 pass 的案例變差)。
"""
import argparse, json, os, sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from inpaint_eval import punch_hole, METHODS, score, CANDIDATE_METHODS  # noqa: E402
from psd_slice import slice_psd, reassemble  # noqa: E402


def load_layer_and_context(psd_path, name):
    """回傳 (gt, (left,top), context_canvas, (W,H))。

    `context_canvas`:只由 z 序排在目標層**之前**(較底層)的圖層 alpha-over 疊成的背景,
    再把目標層自己的 bbox 範圍**硬覆蓋**(直接複製像素值,不做 alpha 混合)成它自己的真實
    gt(見下方踩坑說明)——保證目標層自己的內容跟孤立裁切版 gt 逐位元一致,視窗裡 bbox 以外
    的部分才是它真實、未受汙染的周圍場景上下文。

    ⚠️ **第二個坑**:一開始改用 `Image.alpha_composite(below_canvas, target)` 把目標層貼回去
    (物理正確的疊圖方式),結果 calibration 在 `身體`/`左手` 仍不過(fringe alpha_mae 117~123)
    ——診斷發現誤差 100% 集中在目標層自身抗鋸齒的半透明邊緣像素(<1.6% 面積),原因是
    alpha_composite 在半透明像素疊到不透明背景上時,**輸出 alpha 會被推高**(`a_out = a1 +
    a2*(1-a1)`,背景不透明時 a_out→255)——這是「場景最終呈現」的正確物理結果,但語意上
    不等於「這個圖層自己的 alpha」,兩者本來就不該逐位元相等。既然這裡只是要給孤立裁切
    版本一個忠實的『周圍』背景,bbox 內部根本不需要疊圖運算——改成直接像素覆蓋(hard
    overwrite,如同直接貼上原始圖層資料,不經過任何 alpha 混合公式),bbox 內外語意各自
    正確且逐位元對得上。"""
    psd, manifest, parts = slice_psd(psd_path)
    W, H = psd.width, psd.height
    names = [e["name"] for e, _ in parts]
    if name not in names:
        raise KeyError(f"layer {name!r} not found (available: {names})")
    z = names.index(name)
    entry, im = parts[z]
    if im.mode != "RGBA":
        im = im.convert("RGBA")
    gt = np.array(im).astype(np.float64)  # channel order R,G,B,A(與 inpaint_eval.load_rgba 一致)
    left, top = entry["offset"]
    h, w = gt.shape[:2]

    below_canvas, _ = reassemble(parts[:z], W, H)  # 只疊 z 序在目標層之前(較底層)的圖層
    context_arr = np.array(below_canvas.convert("RGBA")).astype(np.float64)
    context_arr[top:top + h, left:left + w] = gt  # 硬覆蓋,不經過 alpha 混合
    return gt, (left, top), context_arr, (W, H)


def window_bounds(left, top, w, h, W, H, pad_to=512):
    """以圖層 bbox 中心為準,視窗每邊至少擴到 pad_to,裁到畫布範圍內。"""
    cx, cy = left + w / 2.0, top + h / 2.0
    half_w, half_h = max(w, pad_to) / 2.0, max(h, pad_to) / 2.0
    wl = int(max(0, round(cx - half_w)))
    wt = int(max(0, round(cy - half_h)))
    wr = int(min(W, round(cx + half_w)))
    wb = int(min(H, round(cy + half_h)))
    return wl, wt, wr, wb


def check_composite_matches_layer(gt, comp_arr, left, top):
    """校準:composite 在該層自己的內容範圍內,像素應與獨立切出的 gt 一致(允許合成捨入誤差)。
    不一致代表這層底下/上面有其他東西蓋住它,把它抽出來單獨測的「context」實驗前提就不成立。"""
    h, w = gt.shape[:2]
    comp_crop = comp_arr[top:top + h, left:left + w]
    content = gt[..., 3] > 8
    if content.sum() == 0:
        return {"ok": True, "premult_mae": 0.0, "alpha_mae": 0.0, "note": "empty content"}
    a_p = gt[..., :3] * gt[..., 3:4] / 255.0
    b_p = comp_crop[..., :3] * comp_crop[..., 3:4] / 255.0
    premult_mae = float(np.abs(a_p - b_p)[content].mean())
    alpha_mae = float(np.abs(gt[..., 3] - comp_crop[..., 3])[content].mean())
    ok = premult_mae < 2.0 and alpha_mae < 2.0  # 沿用 psd_slice.py 重組無損閘同款門檻
    return {"ok": ok, "premult_mae": round(premult_mae, 4), "alpha_mae": round(alpha_mae, 4)}


def run_case(psd_path, name, mode, seed=0, frac=0.12, pad_to=512):
    gt, (left, top), comp_arr, (W, H) = load_layer_and_context(psd_path, name)
    h, w = gt.shape[:2]

    calib = check_composite_matches_layer(gt, comp_arr, left, top)

    try:
        _, mask = punch_hole(gt, mode=mode, frac=frac, seed=seed)
    except ValueError as e:
        return {"skipped": True, "reason": str(e), "calibration": calib}

    # --- 條件 A:孤立裁切(既有 inpaint_eval.py 的做法,零上下文) ---
    holed_isolated = gt.copy()
    holed_isolated[mask] = 0
    isolated_scores = {}
    for m in CANDIDATE_METHODS:
        recon = METHODS[m](holed_isolated, gt, mask)
        isolated_scores[m] = score(recon, gt, mask)

    # --- 條件 B:大畫布視窗(composite 當周圍上下文,比照插件 512px 下限) ---
    wl, wt, wr, wb = window_bounds(left, top, w, h, W, H, pad_to)
    window = comp_arr[wt:wb, wl:wr].copy()
    ry0, rx0 = top - wt, left - wl
    if ry0 < 0 or rx0 < 0 or ry0 + h > window.shape[0] or rx0 + w > window.shape[1]:
        return {"skipped": True, "reason": "layer bbox not fully inside computed window "
                                            "(hit canvas edge) — pad_to too small or layer "
                                            "touches canvas border", "calibration": calib}
    mask_win = np.zeros(window.shape[:2], dtype=bool)
    mask_win[ry0:ry0 + h, rx0:rx0 + w] = mask
    holed_window = window.copy()
    holed_window[mask_win] = 0
    windowed_scores = {}
    for m in CANDIDATE_METHODS:
        recon_win = METHODS[m](holed_window, window, mask_win)
        recon_crop = recon_win[ry0:ry0 + h, rx0:rx0 + w]
        windowed_scores[m] = score(recon_crop, gt, mask)

    delta = {}
    for m in CANDIDATE_METHODS:
        delta[m] = {k: round(windowed_scores[m][k] - isolated_scores[m][k], 4)
                    for k in ("premult_mae", "alpha_mae", "seam_grad_diff", "ssim")}

    return {
        "calibration": calib,
        "hole_px": int(mask.sum()), "content_px": int((gt[..., 3] > 8).sum()),
        "layer_bbox": [w, h], "window_bbox": [wr - wl, wb - wt],
        "isolated": isolated_scores, "windowed": windowed_scores, "delta": delta,
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                  formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("psd")
    ap.add_argument("layers", nargs="+", help="圖層名稱(如 身體 左手 光暈)")
    ap.add_argument("--modes", nargs="+", default=["interior", "edge"])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--pad-to", type=int, default=512, help="視窗每邊最小尺寸(比照插件下限)")
    a = ap.parse_args()

    report = {}
    for name in a.layers:
        for mode in a.modes:
            key = f"{name}::{mode}"
            report[key] = run_case(a.psd, name, mode, seed=a.seed, pad_to=a.pad_to)

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
