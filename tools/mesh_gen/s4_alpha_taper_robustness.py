#!/usr/bin/env python3
"""S4 補圖候選 13 — `estimate_alpha_taper` 小樣本 bug 觸發頻率量化(見 STATE_S4.md 候選 13)。

背景(候選 10 意外發現,`knowledge/s4-inpaint-1a-shape-boundary.md`):特定橢圓 interior 洞下,
`ell`(局部漸縮寬度估計)被 15px 環內樣本數過少(n=7)污染,alpha 估計從真值 255 崩塌到 60,
但 RGB 本身補對。既有測試案例(圓形 interior/edge 洞、8 組真實遮擋洞)皆未觸發,回歸零反向。

本檔:在**修法之前先量化「多常發生」**(候選 13 建議的第一步,避免只憑一次意外案例重寫核心
估計邏輯)。做法:
1. 跨更多材質(robot_parts 5 層全部、Symbol_Ww 6 個形狀/尺寸各異的層)、更廣的洞形狀
   (circle 多種 frac、ellipse 多種 aspect×frac×angle)大量取樣,record 每次呼叫
   `estimate_alpha_taper` 的 `ring_count`(15px 環內已知 AA 邊緣樣本數)與實際 alpha_mae
   (洞區域 alpha 估計 vs 真值的平均絕對誤差)。
2. 用這批資料檢驗「ring_count 小 → alpha_mae 大」的假設,並找出一個能可靠避開污染的
   `min_ring` 門檻(現有硬編碼門檻是 5,候選 10 的意外案例 n=7 已經超過這個門檻卻仍失準,
   代表 5 太低)。
3. 用同一批資料驗證候選門檻(把 `min_ring` 從 5 提高到候選值)确实能把高 alpha_mae 案例
   壓下來,而不會誤傷原本表現良好的案例(fallback 用全域 fringe 對這些案例不會更差)。
"""
import argparse, json, os, sys
import numpy as np
from psd_tools import PSDImage

sys.path.insert(0, os.path.dirname(__file__))
from psd_slice import leaf_layers
from inpaint_eval import punch_hole, estimate_alpha_taper
from real_occlusion_eval import layer_full_canvas

ROBOT_MATERIALS = ["光暈", "右手", "頭", "身體", "左手"]
SYMBOL_MATERIALS = ["底", "頭", "身體", "框", "臉部陰影", "wild", "墨鏡"]

CIRCLE_FRACS = [0.06, 0.08, 0.10, 0.12, 0.15, 0.20]
ELLIPSE_ASPECTS = [1.5, 2.0, 2.5, 3.0]
ELLIPSE_FRACS = [0.06, 0.10, 0.15]
ELLIPSE_ANGLES = [0.0, np.pi / 4, np.pi / 2]


def load_materials():
    out = {}
    robot = PSDImage.open("assets/robot_parts.psd")
    for l in leaf_layers(robot):
        if l.name in ROBOT_MATERIALS:
            out[f"robot::{l.name}"] = layer_full_canvas(robot, l)
    symbol = PSDImage.open("assets/Symbol_Ww.psd")
    for l in leaf_layers(symbol):
        if l.name in SYMBOL_MATERIALS:
            out[f"symbol::{l.name}"] = layer_full_canvas(symbol, l)
    return out


def alpha_mae_in_mask(alpha_est, gt_alpha, mask):
    return float(np.mean(np.abs(alpha_est[mask] - gt_alpha[mask])))


def run_case(gt, mode, shape, seed, frac, aspect=1.0, angle=None):
    try:
        holed, mask = punch_hole(gt, mode=mode, frac=frac, seed=seed, shape=shape, aspect=aspect, angle=angle)
    except ValueError as e:
        return {"skipped": True, "reason": str(e)}
    debug = {}
    alpha_est = estimate_alpha_taper(holed[..., 3], mask, debug=debug)
    mae = alpha_mae_in_mask(alpha_est, gt[..., 3], mask)
    return {"skipped": False, "hole_px": int(mask.sum()), "mae": round(mae, 3), **debug}


def sweep(materials, n_seeds=3):
    rows = []
    for mat_name, gt in materials.items():
        for mode in ("interior", "edge"):
            for frac in CIRCLE_FRACS:
                for seed in range(n_seeds):
                    r = run_case(gt, mode, "circle", seed, frac)
                    if not r["skipped"]:
                        rows.append({"material": mat_name, "mode": mode, "shape": "circle",
                                     "frac": frac, "aspect": 1.0, "angle": None, "seed": seed, **r})
        # ellipse 只支援 interior(見 punch_hole)
        for aspect in ELLIPSE_ASPECTS:
            for frac in ELLIPSE_FRACS:
                for angle in ELLIPSE_ANGLES:
                    for seed in range(n_seeds):
                        r = run_case(gt, "interior", "ellipse", seed, frac, aspect=aspect, angle=angle)
                        if not r["skipped"]:
                            rows.append({"material": mat_name, "mode": "interior", "shape": "ellipse",
                                         "frac": frac, "aspect": aspect, "angle": round(angle, 3),
                                         "seed": seed, **r})
    return rows


def bucket_report(rows):
    buckets = [(0, 5), (5, 10), (10, 20), (20, 30), (30, 50), (50, 10**9)]
    report = []
    for lo, hi in buckets:
        sel = [r for r in rows if lo <= r["ring_count"] < hi]
        if not sel:
            continue
        maes = [r["mae"] for r in sel]
        report.append({
            "ring_count_range": f"[{lo},{hi})",
            "n": len(sel),
            "mae_mean": round(float(np.mean(maes)), 3),
            "mae_max": round(float(np.max(maes)), 3),
            "n_mae_gt_20": sum(1 for m in maes if m > 20),
        })
    return report


def evaluate_min_ring(materials, rows, candidate_min_rings):
    """對每個候選 min_ring 門檻,重算「原本因 ring_count 落在 [candidate, 5) 或 [5, candidate)
    之間會改變路徑」的案例,量測 fallback(全域 fringe)是否真的降低 mae,而不是猜測就改。
    只需重跑 ring_count < candidate 的既有案例(路徑會從 local 或 already-fallback 變成
    fallback),用同一個 (material, mode, shape, frac, aspect, angle, seed) 反查回 mask 重算。"""
    out = {}
    for cand in candidate_min_rings:
        changed = [r for r in rows if r["ring_count"] < cand and not r["used_fallback"]]
        deltas = []
        for r in changed:
            gt = materials[r["material"]]
            holed, mask = punch_hole(gt, mode=r["mode"], frac=r["frac"], seed=r["seed"],
                                      shape=r["shape"], aspect=r["aspect"],
                                      angle=r["angle"] if r["angle"] is not None else None)
            debug2 = {}
            alpha_est2 = estimate_alpha_taper(holed[..., 3], mask, min_ring=cand, debug=debug2)
            mae2 = alpha_mae_in_mask(alpha_est2, gt[..., 3], mask)
            deltas.append({"material": r["material"], "mode": r["mode"], "shape": r["shape"],
                            "frac": r["frac"], "aspect": r["aspect"], "angle": r["angle"],
                            "seed": r["seed"], "ring_count": r["ring_count"],
                            "mae_before": r["mae"], "mae_after": round(mae2, 3)})
        out[cand] = {
            "n_cases_switched_to_fallback": len(changed),
            "n_improved": sum(1 for d in deltas if d["mae_after"] < d["mae_before"] - 0.5),
            "n_worsened": sum(1 for d in deltas if d["mae_after"] > d["mae_before"] + 0.5),
            "n_unchanged": sum(1 for d in deltas if abs(d["mae_after"] - d["mae_before"]) <= 0.5),
            "worst_before_after": sorted(deltas, key=lambda d: -d["mae_before"])[:5],
        }
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    materials = load_materials()
    print(f"materials: {list(materials.keys())}")
    rows = sweep(materials, n_seeds=args.seeds)
    print(f"total runs: {len(rows)}")

    buckets = bucket_report(rows)
    print("\n=== ring_count bucket -> alpha_mae ===")
    for b in buckets:
        print(b)

    high_mae = [r for r in rows if r["mae"] > 20]
    print(f"\nn cases with mae > 20: {len(high_mae)} / {len(rows)}")
    for r in sorted(high_mae, key=lambda r: -r["mae"])[:15]:
        print({k: r[k] for k in ("material", "mode", "shape", "frac", "aspect", "angle",
                                  "seed", "ring_count", "mae", "used_fallback")})

    candidates = [10, 15, 20, 30, 50]
    print(f"\n=== candidate min_ring evaluation (existing threshold=5) ===")
    ev = evaluate_min_ring(materials, rows, candidates)
    for cand, res in ev.items():
        print(cand, {k: v for k, v in res.items() if k != "worst_before_after"})
        for d in res["worst_before_after"]:
            print("   ", d)

    if args.out:
        with open(args.out, "w") as f:
            json.dump({"rows": rows, "buckets": buckets, "min_ring_eval": ev}, f, indent=2)
        print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
