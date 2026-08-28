#!/usr/bin/env python3
"""S2 骨架閘 / S5 前置 —— bone pivot(關節樞紐)放置品質評估器(純 CPU)。

S5(骨架半自動)在路線圖是「唯一真正卡死處」:每個關節的 pivot(骨的原點)放對,
限肢旋轉才會繞對的軸擺動;放錯 → 動作歪、末梢甩不到位。要自主收斂就得先有能
「量化某組 pivot 對不對」的閘 —— 這正是 S2 尚缺的骨架閘。本檔即該閘。

## 量什麼(以及為什麼這個量就夠)

一根骨帶著它的 attachment 是**剛體**:骨繞 pivot 轉 θ 時,整片圖跟著繞同一 pivot。
若真 pivot=c_true、提案 pivot=c_prop、Δ=c_true−c_prop,則骨上任一點 p 在轉 θ 後
兩種 pivot 造成的世界位移差為

    P_true − P_prop = (I − Rot(θ))·Δ ,   ‖(I−Rot(θ))·Δ‖ = 2·sin(θ/2)·‖Δ‖

—— 與 p 無關(tip 消掉)、且各方向等向(沿骨軸 / 垂直分量貢獻相同)。

結論:**pivot 的歐氏誤差 ‖Δ‖ 就是充分且正確的量**;不必另設「功能性擺動」指標,
因為擺動後整片圖的位移恰為 ‖Δ‖ 的固定倍數。但 ‖Δ‖ 本身對人不直觀,所以本閘同時
回報它的物理後果 **swing@θ = 2·sin(θ/2)·‖Δ‖**(「限肢擺 θ 時每個像素偏離應到位置多少 px」),
並以骨長 normalize(`/length`)得到跨骨可比、跨資產可比的尺度。

## 真值來源

Award.json 的骨階層本身就是美術定好的真 rig:每根骨的 world 原點 = 真 pivot。
本閘用 `weighted_deform_eval` 既有的 Spine 3.8 FK 算真值,再對任意「提案 pivot 組」評分。

## 誰被評

只評**帶 length 且有 parent 的骨**(真正的限肢節段;pivot 放置對它們才有意義)。
root / 無 length 的容器骨(光效群組等)pivot 語意不同,不列入 pass/fail。
"""
import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
from weighted_deform_eval import (
    load_skeleton,
    bone_world_transforms,
    transform_point,
)

# 預設判準:pivot 誤差 / 骨長。0.15 = pivot 落在骨長 15% 內算過關
# (擺 30° 時像素偏移 ≈ 0.518·誤差 ≈ 8% 骨長,肉眼幾乎看不出擺錯軸)。
DEFAULT_TOL_NORM_LEN = 0.15
DEFAULT_TEST_ANGLE = 30.0


def swing_disp(pivot_err, angle_deg):
    """pivot 誤差 → 骨擺 angle_deg 時整片圖的世界位移(px)。"""
    return 2.0 * math.sin(math.radians(angle_deg) / 2.0) * pivot_err


def true_world_pivots(sk):
    """回傳 {bone_name: (wx, wy)} —— 真 rig 每根骨的 world 原點(= 真 pivot)。"""
    _, bones, byname, order = (sk, sk["bones"], {b["name"]: b for b in sk["bones"]},
                               [b["name"] for b in sk["bones"]])
    world = bone_world_transforms(bones, byname, order, {})
    return {n: (world[n][4], world[n][5]) for n in order}, world, byname, order


def evaluable_bones(byname, order):
    """帶 length(>0)且有 parent 的骨 = 真限肢節段,pivot 放置有意義。"""
    out = []
    for n in order:
        b = byname[n]
        L = b.get("length") or 0.0
        if b.get("parent") and L > 0:
            out.append(n)
    return out


def skeleton_diag(true_pivots):
    xs = [p[0] for p in true_pivots.values()]
    ys = [p[1] for p in true_pivots.values()]
    if not xs:
        return 1.0
    dx = max(xs) - min(xs)
    dy = max(ys) - min(ys)
    return math.hypot(dx, dy) or 1.0


def classify_serial(byname, order, eval_names):
    """把每根被評骨標成 'serial'(其 parent 只有 1 個限肢子)或 'branch'(≥2 個)。
    parent-tip 這類「關節端對端相接」的啟發式只在 serial 節段成立;branch 節段
    的岔出子骨不在 parent 軸尖端,是啟發式必然失手處 —— 分類後可分別回報。"""
    eval_set = set(eval_names)
    limb_children = {}
    for n in order:
        b = byname[n]
        p = b.get("parent")
        if n in eval_set and p:
            limb_children.setdefault(p, []).append(n)
    cls = {}
    for n in eval_names:
        p = byname[n].get("parent")
        sib = limb_children.get(p, [])
        cls[n] = "serial" if len(sib) <= 1 else "branch"
    return cls


def eval_pivots(sk, proposed, tol_norm_len=DEFAULT_TOL_NORM_LEN,
                test_angle=DEFAULT_TEST_ANGLE, bones_subset=None):
    """評估一組提案 pivot。

    proposed : {bone_name: (world_x, world_y)}
    回傳 dict:
      per_bone : [{name, length, pivot_err, err_norm_len, err_norm_diag,
                   swing_disp, swing_norm_len, cls, passed}]
      summary  : {n, n_pass, pass_rate, mean_norm_len, median_norm_len,
                  p90_norm_len, max_norm_len, by_class:{...}, worst:[...]}
    """
    true_pivots, world, byname, order = true_world_pivots(sk)
    names = bones_subset if bones_subset is not None else evaluable_bones(byname, order)
    diag = skeleton_diag(true_pivots)
    cls = classify_serial(byname, order, names)

    per = []
    for n in names:
        if n not in proposed:
            continue
        L = byname[n].get("length") or 0.0
        tx, ty = true_pivots[n]
        px, py = proposed[n]
        err = math.hypot(px - tx, py - ty)
        norm_len = err / L if L > 0 else float("inf")
        sd = swing_disp(err, test_angle)
        per.append({
            "name": n,
            "length": L,
            "pivot_err": err,
            "err_norm_len": norm_len,
            "err_norm_diag": err / diag,
            "swing_disp": sd,
            "swing_norm_len": sd / L if L > 0 else float("inf"),
            "cls": cls.get(n, "serial"),
            "passed": norm_len <= tol_norm_len,
        })

    per.sort(key=lambda r: r["err_norm_len"], reverse=True)
    vals = [r["err_norm_len"] for r in per] or [0.0]
    vals_sorted = sorted(vals)

    def pct(p):
        if not vals_sorted:
            return 0.0
        i = min(len(vals_sorted) - 1, int(round(p * (len(vals_sorted) - 1))))
        return vals_sorted[i]

    n_pass = sum(1 for r in per if r["passed"])
    by_class = {}
    for c in ("serial", "branch"):
        sub = [r for r in per if r["cls"] == c]
        if sub:
            by_class[c] = {
                "n": len(sub),
                "n_pass": sum(1 for r in sub if r["passed"]),
                "pass_rate": sum(1 for r in sub if r["passed"]) / len(sub),
                "mean_norm_len": sum(r["err_norm_len"] for r in sub) / len(sub),
            }

    summary = {
        "n": len(per),
        "n_pass": n_pass,
        "pass_rate": n_pass / len(per) if per else 0.0,
        "mean_norm_len": sum(vals) / len(vals),
        "median_norm_len": pct(0.5),
        "p90_norm_len": pct(0.9),
        "max_norm_len": max(vals),
        "skeleton_diag": diag,
        "test_angle": test_angle,
        "tol_norm_len": tol_norm_len,
        "by_class": by_class,
        "worst": [(r["name"], round(r["err_norm_len"], 3), r["cls"]) for r in per[:6]],
    }
    return {"per_bone": per, "summary": summary}


def print_report(res, title="pivot eval"):
    s = res["summary"]
    print(f"== {title} ==")
    print(f"  bones evaluated : {s['n']}   pass {s['n_pass']}/{s['n']} "
          f"({s['pass_rate']*100:.0f}%)  tol={s['tol_norm_len']}·len")
    print(f"  err/len  mean={s['mean_norm_len']:.3f} "
          f"median={s['median_norm_len']:.3f} p90={s['p90_norm_len']:.3f} "
          f"max={s['max_norm_len']:.3f}")
    for c, d in s["by_class"].items():
        print(f"  [{c:6}] n={d['n']:2d} pass={d['n_pass']:2d}/{d['n']:2d} "
              f"({d['pass_rate']*100:3.0f}%)  mean err/len={d['mean_norm_len']:.3f}")
    if s["worst"]:
        print("  worst:", ", ".join(f"{n}={e}({c})" for n, e, c in s["worst"]))


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    sk, bones, byname, order = load_skeleton(path)
    tp, _, _, _ = true_world_pivots(sk)
    # 自我測試:餵真值應 0 誤差、100% pass
    res = eval_pivots(sk, tp)
    print_report(res, f"self-consistency (truth vs truth) — {path}")
    assert res["summary"]["max_norm_len"] < 1e-9, "評估器對真值不應有誤差!"
    print("  OK: 餵真值 → 0 誤差、100% pass(評估器自洽)")
