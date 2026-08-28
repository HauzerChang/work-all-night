#!/usr/bin/env python3
"""S2 骨架閘 + S5 pivot baseline 的整合驗收(對 Award 真 rig)。

三道校驗(對齊 repo 其他評估器「正/負對照 + baseline 分級」慣例):

  ①自洽(正對照)  : 餵真 pivot → 0 誤差、100% pass。確認閘沒有系統性偏差。
  ②鑑別力(負對照): 對真 pivot 加逐級高斯噪音(σ = 0.1/0.3/1.0 · 骨長)→ 誤差與
                     fail 率**單調上升**。確認閘真的能分辨「準 vs 亂放」而非永遠說 pass。
  ③baseline 分級  : parent_tip / parent_origin 兩啟發式 → 回報 pass 率、serial vs branch
                     分項。預期 parent_tip 在 serial 明顯優於 branch;parent_origin 全面差。

OVERALL PASS 條件:①誤差 <1e-6 且 100% pass;②σ 單調且 σ=1.0 幾乎全 fail;
③parent_tip 的 serial pass 率 > branch pass 率(啟發式行為符合幾何預期)、
且 parent_tip 明顯優於 parent_origin(閘能分好壞啟發式)。
"""
import sys
import os
import math
import random

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
from weighted_deform_eval import load_skeleton
from pivot_eval import eval_pivots, true_world_pivots, evaluable_bones, print_report
from infer_pivots import infer_parent_tip, infer_parent_origin


def perturb(true_pivots, byname, eval_names, sigma_frac, seed=0):
    """對每根被評骨的真 pivot 加 σ = sigma_frac·骨長 的高斯噪音(各向獨立)。"""
    rng = random.Random(seed)
    out = dict(true_pivots)
    for n in eval_names:
        L = byname[n].get("length") or 1.0
        s = sigma_frac * L
        tx, ty = true_pivots[n]
        out[n] = (tx + rng.gauss(0, s), ty + rng.gauss(0, s))
    return out


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    sk, bones, byname, order = load_skeleton(path)
    tp, _, _, _ = true_world_pivots(sk)
    eval_names = evaluable_bones(byname, order)

    print(f"### validate_pivots — {path}  ({len(eval_names)} 限肢節段被評)\n")

    checks = []

    # ---- ① 自洽(正對照) ----
    res0 = eval_pivots(sk, tp)
    print_report(res0, "① self-consistency (truth)")
    c1 = res0["summary"]["max_norm_len"] < 1e-6 and res0["summary"]["pass_rate"] == 1.0
    checks.append(("① 自洽 truth→0 誤差/100%pass", c1))
    print(f"   -> {'PASS' if c1 else 'FAIL'}\n")

    # ---- ② 鑑別力(負對照) ----
    print("② discrimination (truth + Gaussian noise σ·len):")
    prev_mean = -1.0
    prev_pass = 2.0
    mono = True
    rows = []
    for sig in (0.0, 0.1, 0.3, 1.0):
        r = eval_pivots(sk, perturb(tp, byname, eval_names, sig, seed=42))
        s = r["summary"]
        rows.append((sig, s["mean_norm_len"], s["pass_rate"]))
        print(f"   σ={sig:>4}·len  mean err/len={s['mean_norm_len']:.3f}  "
              f"pass={s['pass_rate']*100:3.0f}%")
        if sig > 0:
            if s["mean_norm_len"] <= prev_mean or s["pass_rate"] > prev_pass + 1e-9:
                mono = False
        prev_mean = s["mean_norm_len"]
        prev_pass = s["pass_rate"]
    sig1_pass = rows[-1][2]
    c2 = mono and sig1_pass <= 0.15  # σ=1.0·len 幾乎全 fail
    checks.append(("② 誤差/fail 隨噪音單調上升 且 σ=1.0 幾近全 fail", c2))
    print(f"   monotonic={mono}  σ=1.0 pass={sig1_pass*100:.0f}%  "
          f"-> {'PASS' if c2 else 'FAIL'}\n")

    # ---- ③ baseline 分級 ----
    rt = eval_pivots(sk, infer_parent_tip(sk))
    ro = eval_pivots(sk, infer_parent_origin(sk))
    print_report(rt, "③a baseline parent_tip")
    print()
    print_report(ro, "③b baseline parent_origin (弱對照)")
    st = rt["summary"]["by_class"]
    serial_pr = st.get("serial", {}).get("pass_rate", 0.0)
    branch_pr = st.get("branch", {}).get("pass_rate", 0.0)
    tip_pr = rt["summary"]["pass_rate"]
    ori_pr = ro["summary"]["pass_rate"]
    c3 = (serial_pr > branch_pr) and (tip_pr > ori_pr + 1e-9)
    checks.append(("③ parent_tip: serial>branch 且 tip 優於 origin(閘分得出好壞啟發式)", c3))
    print(f"\n   parent_tip: serial pass={serial_pr*100:.0f}% > branch pass={branch_pr*100:.0f}% ?  "
          f"tip {tip_pr*100:.0f}% > origin {ori_pr*100:.0f}% ?  -> {'PASS' if c3 else 'FAIL'}")

    # ---- 匯總 ----
    print("\n=== SUMMARY ===")
    for name, ok in checks:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}")
    overall = all(ok for _, ok in checks)
    print(f"\nOVERALL: {'PASS' if overall else 'FAIL'}")
    return 0 if overall else 1


if __name__ == "__main__":
    sys.exit(main())
