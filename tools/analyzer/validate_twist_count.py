#!/usr/bin/env python3
"""candidate (G-4''''''-count) 自我驗收閘 — twist 扭轉**段數**隨檔位遞增(count-aware,純 CPU)。

candidate (G-4''''''-tier)(`validate_twist_tier.py`)讓 twist 的**兩條** shear 軸峰**幅度**隨檔位遞增
(愈高檔位擰愈狠),兩軸同一 g 同比放大 → shearY/shearX ≡ −TWIST_PHI 逐檔不變;但各檔位仍是**同樣 4 段**
反相雙軸阻尼擺 —— 有「擰多狠」沒「擰幾下」。本次 (G-4''''''-count) 補上 twist 的扭轉**段數** nosc **隨檔位嚴格
遞增**(Super 4 → Mega 5 → Omg 6 → Legend 7)。

**關鍵:幅度增益加不出扭轉段數** —— 段數是關鍵幀**拓樸**(繞 0 交替的 shearX 極值個數 = 反相 shearY 極值個數),
必須在 `gen_twist` 生成當下決定;事後 `amplify_bone_tl` 只能同比放大既有極值、無法多長一段。故不走 amplify,
而是對 twist 檔位變體以該檔位 nosc **重生成**整個 beat,再疊 (G-4''''''-tier) 的**單一-g** 幅度增益。此模式同
(G-4''')對 wobble、(J-2)對 combo、(G-4'''''-c)對 squash 所做,惟段數階梯各類別獨立
(twist→TIER_TWIST_CYCLES,build_animations 依 cat 路由)。

**twist 獨有的 crux(與 wobble count 的差異)**:twist 有**兩條** shear 軸(反相雙軸)。段數重生成後兩軸各多長
nosc 個阻尼極值,而每個新極值仍由 `_twist_env` 建構 shearY=−TWIST_PHI·shearX → **φ 比值由建構保證、與段數無關**;
故段數×幅度×φ 保形三效必須**同時**成立:每個檔位不論扭幾段,(a)段數 == 宣告且遞增;(b)兩軸峰比值 ≈ TWIST_PHI
(φ 逐檔不變);(c)每內部極值仍反相(shearX·shearY<0)。段數增多會多長出低幅極值(A·rⁱ 隨 i 遞減),閘須證這些
新極值也保 φ 與反相(不只原 4 段)—— 比照 squash count 的「新擠壓極值也體積守恆」。

真值界定同 (E/H/I/J/J-2/G-4'/G-4''/G-4''''/G-4''''''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構
簽章**非美感;「愈高檔位擰愈多段且每段仍反相雙軸保 φ」是可量化的檔位簽章,用負對照證鑑別力(閘可信)。從
**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(..., tier_gains, tier_twist_cycles)` 端到端量,
與 (J)/(G-4''''''-tier) 同一 fixture。

AC(客觀、可量測):
  TC1 present + backward-compat : 每檔位 `twist__{tier}` 皆產出、finite、有 bone、≥1 bone 帶**雙軸** shear
                                 (shearX、shearY 皆非零);**base twist 恆 4 段不變**(逐位元同無 count);且**不帶**
                                 `tier_twist_cycles`(=None)時 twist 變體逐位元同 (G-4''''''-tier) 幅度-only(加性 opt-in 零回歸)。
  TC2 crux — count↑ ∧ φ 不變     : (a) 各檔位 twist 的扭轉**段數**(繞 0 交替 shearX 極值個數)== 宣告 [4,5,6,7]
                                 且 Super<Mega<Omg<Legend **嚴格遞增**、Super 段數 == base 段數(向後相容);
                                 (b) **每個檔位、每個 twist bone** shearY 峰 / shearX 峰 ≈ TWIST_PHI(|誤差|≤PHI_TOL)——
                                 段數增多(多長低幅反相極值)仍不破 φ 比值(段數×幅度×φ 保形三效正交,twist count 獨有 crux)。
  TC3 signature preserved(兩軸) : **每檔位**每 twist bone 的 shearX **與** shearY 各自:(a)首尾 0;(b)繞 0 變號 ≥3;
                                 (c)相繼極值幅度嚴格遞減(阻尼)。**且**峰 |shearX| 與峰 |shearY| 仍隨檔位嚴格遞增
                                 (段數軸不抵消幅度軸)、每內部極值仍反相 shearX·shearY<0(段數軸不破反相)。
  TC4 orthogonality             : (a) 段數 + **平增益**(全 g=1.0)→ 段數仍遞增(結構獨立於幅度)、兩軸峰**不**遞增,
                                 **且 φ 比值仍逐檔 ≈TWIST_PHI**(段數單獨作用亦不破 φ);
                                 (b) 增益 + **無段數**(ttc=None)→ 段數恆 4、兩軸峰遞增(兩軸可獨立開關)。
  TC5 neg-control               : (a) **平段數**(全 4)→ 段數單調性 FALSE(證閘測遞增非恆真);
                                 (b) 無宣告的 genre(slot_reveal)→ `twist_cycles_for` 回 None 且無檔位增益 → 不產 twist 段數變體;
                                 (c) 段數**只作用 twist**:非-twist 主秀 beat 的 shear 段數在各檔位恆定(不外洩;wobble/squash 仍 4 段)。

用法:
  python3 validate_twist_count.py            # 摘要
  python3 validate_twist_count.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from beat_templates import TWIST_PHI
from analyze_target import analyze
# 復用 G-4' 的阻尼簽章判準 + G-4'''''' 的雙軸讀取/反相判準(與 twist-gen / twist-tier 閘完全一致)
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_twist_gen import _shear_y, _shear_xy, _interior_shear, _tw3_eval, _has_shear_y

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
DEAD = 1e-6
PHI_TOL = 2e-3     # shearY峰/shearX峰 對 TWIST_PHI 的容差(g*v 4 位捨入下的餘裕;同 twist-tier)


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/twist_count_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _twist_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "twist"]


def _main_beats(anims):
    return {nm: G.beat_category(nm) for nm in anims
            if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


def _nosc(anim):
    """該 anim 的 twist 扭轉段數 = 任一帶 shear bone 的**繞 0 交替 shearX 極值個數**(= 非零 shearX 關鍵幀數)。

    twist shear 包絡 [0, e1, …, e_nosc, 0] 與 wobble 同形 → 非零內部關鍵幀數即段數;各 bone 同形
    (僅 role 峰值 / side 反相不同)→ 取任一有 shear 的 bone。shearY 與 shearX 極值同時刻(反相耦合)→ 段數一致。"""
    for ch in anim.get("bones", {}).values():
        sx = _shear_x(ch)
        if sx:
            return len([v for v in sx if abs(v) > DEAD])
    return 0


def _peak_x(anim):
    ps = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(ps, default=0.0)


def _peak_y(anim):
    ps = [max(abs(v) for v in _shear_y(ch)) for ch in anim.get("bones", {}).values() if _shear_y(ch)]
    return max(ps, default=0.0)


def _phi_ratios(anim):
    """該 anim 每個帶雙軸 shear 的 bone 的 shearY峰/shearX峰 → dict {bone: ratio}(shearX 峰 ~0 的略過)。"""
    out = {}
    for bn, ch in anim.get("bones", {}).items():
        sx, sy = _shear_x(ch), _shear_y(ch)
        if not sx or not sy:
            continue
        pkx = max(abs(v) for v in sx)
        pky = max(abs(v) for v in sy)
        if pkx <= 1e-9:
            continue
        out[bn] = pky / pkx
    return out


def _max_phi_err(anim):
    """該 anim 全 bone 的峰 |φ_ratio − TWIST_PHI|(無 dual-axis 回 0)。"""
    rs = _phi_ratios(anim)
    return max((abs(r - TWIST_PHI) for r in rs.values()), default=0.0)


def _dual_bones(anim):
    """≥1 bone 同時帶非零 shearX 與非零 shearY → dict {bone: chans}。"""
    return {bn: ch for bn, ch in anim.get("bones", {}).items()
            if _shear_x(ch) and _has_shear_y(ch)}


def _is_strict_inc(xs):
    return len(xs) >= 2 and all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    cyc = TV.twist_cycles_for(GENRE)

    base = G.build_animations(skel, sb)                                            # 無檔位
    amp_only = G.build_animations(skel, sb, tier_gains=gains)                      # (G-4''''''-tier) 幅度-only
    full = G.build_animations(skel, sb, tier_gains=gains, tier_twist_cycles=cyc)   # (G-4''''''-count) 幅度+段數
    twist_beats = _twist_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- TC1 present + backward-compat ----
    tc1 = {"twist_beats": twist_beats, "missing": [], "not_finite": [], "no_bones": [],
           "variant_no_dual": [], "base_changed": [], "amp_only_regressed": []}
    for tb in twist_beats:
        for t in TIERS:
            vk = "{}__{}".format(tb, t)
            an = full.get(vk)
            if an is None:
                tc1["missing"].append(vk); continue
            if not SA.all_finite(an):
                tc1["not_finite"].append(vk)
            if not an.get("bones"):
                tc1["no_bones"].append(vk)
            if not _dual_bones(an):
                tc1["variant_no_dual"].append(vk)
        # base twist 恆 4 段且逐位元同無檔位
        if _nosc(full[tb]) != 4 or json.dumps(base[tb], sort_keys=True) != json.dumps(full[tb], sort_keys=True):
            tc1["base_changed"].append(tb)
    # tier_twist_cycles=None 時,twist 變體逐位元同 (G-4''''''-tier) 幅度-only(加性 opt-in)
    none_run = G.build_animations(skel, sb, tier_gains=gains, tier_twist_cycles=None)
    for tb in twist_beats:
        for t in TIERS:
            vk = "{}__{}".format(tb, t)
            if json.dumps(none_run.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                tc1["amp_only_regressed"].append(vk)
    tc1_pass = bool(twist_beats) and not any(tc1[k] for k in
               ["missing", "not_finite", "no_bones", "variant_no_dual", "base_changed", "amp_only_regressed"])
    R["TC1_present_backward_compat"] = {**tc1, "pass": tc1_pass}

    # ---- TC2 crux: count monotone AND phi ratio invariant per tier/bone ----
    tc2 = {"beats": {}, "fail_count": [], "bad_phi": []}
    expected = [cyc[t] for t in TIERS]
    for tb in twist_beats:
        counts = [_nosc(full["{}__{}".format(tb, t)]) for t in TIERS]
        base_count = _nosc(base[tb])
        mono = _is_strict_inc(counts)
        matches = (counts == expected)
        super_eq_base = (counts[0] == base_count)
        # 每檔位每 bone 的 φ 比值 ≈ TWIST_PHI(段數增多的低幅極值也保 φ)
        phi_errs = {}
        for t in TIERS:
            an = full["{}__{}".format(tb, t)]
            for bn, r in _phi_ratios(an).items():
                key = "{}__{}::{}".format(tb, t, bn)
                phi_errs[key] = round(r, 5)
                if abs(r - TWIST_PHI) > PHI_TOL:
                    tc2["bad_phi"].append((key, round(r, 5)))
        tc2["beats"][tb] = {"counts": counts, "expected": expected, "base_count": base_count,
                            "monotone": mono, "matches_declared": matches, "super_eq_base": super_eq_base,
                            "max_phi_err": round(max((abs(v - TWIST_PHI) for v in phi_errs.values()),
                                                     default=0.0), 6)}
        if not (mono and matches and super_eq_base):
            tc2["fail_count"].append(tb)
    tc2_pass = bool(twist_beats) and not tc2["fail_count"] and not tc2["bad_phi"]
    R["TC2_count_monotone_phi_invariant"] = {"tiers": TIERS, "phi": TWIST_PHI, **tc2, "pass": tc2_pass}

    # ---- TC3 both-axes damped signature preserved per tier + peaks monotone + counterphase ----
    tc3 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [],
           "peak_x_not_mono": [], "peak_y_not_mono": [], "not_counterphase": [], "detail": {}}
    for tb in twist_beats:
        for t in TIERS:
            an = full["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                for axis, vals in (("x", _shear_x(ch)), ("y", _shear_y(ch))):
                    if not vals:
                        continue
                    key = "{}__{}::{}::{}".format(tb, t, bn, axis)
                    ends_ok = abs(vals[0]) < DEAD and abs(vals[-1]) < DEAD
                    nsc = _sign_changes_zero(vals)
                    damp = _extrema_mags_decreasing(vals)
                    tc3["detail"][key] = {"n_sign_changes": nsc, "damped": damp}
                    if not ends_ok:
                        tc3["bad_endpoints"].append(key)
                    if nsc < 3:
                        tc3["few_sign_changes"].append(key)
                    if not damp:
                        tc3["not_damped"].append(key)
                # 每內部極值反相(段數軸不破反相)
                interior = _interior_shear(ch)
                if interior and _has_shear_y(ch):
                    cp_ok, _dev_ok, _det = _tw3_eval(interior)
                    if not cp_ok:
                        tc3["not_counterphase"].append("{}__{}::{}".format(tb, t, bn))
        # 峰 |shearX| 與峰 |shearY| 皆仍隨檔位嚴格遞增(段數軸不抵消幅度軸)
        px = [_peak_x(full["{}__{}".format(tb, t)]) for t in TIERS]
        py = [_peak_y(full["{}__{}".format(tb, t)]) for t in TIERS]
        if not _is_strict_inc(px):
            tc3["peak_x_not_mono"].append((tb, [round(p, 3) for p in px]))
        if not _is_strict_inc(py):
            tc3["peak_y_not_mono"].append((tb, [round(p, 3) for p in py]))
    tc3_pass = (bool(tc3["detail"]) and not any(tc3[k] for k in
                ["bad_endpoints", "few_sign_changes", "not_damped",
                 "peak_x_not_mono", "peak_y_not_mono", "not_counterphase"]))
    R["TC3_signature_preserved"] = {**tc3, "pass": tc3_pass}

    # ---- TC4 orthogonality ----
    flat_gain = {t: 1.0 for t in TIERS}
    ca = G.build_animations(skel, sb, tier_gains=flat_gain, tier_twist_cycles=cyc)
    counts_flatgain = {tb: [_nosc(ca["{}__{}".format(tb, t)]) for t in TIERS] for tb in twist_beats}
    px_flatgain = {tb: [round(_peak_x(ca["{}__{}".format(tb, t)]), 3) for t in TIERS] for tb in twist_beats}
    py_flatgain = {tb: [round(_peak_y(ca["{}__{}".format(tb, t)]), 3) for t in TIERS] for tb in twist_beats}
    phi_flatgain = {tb: max(_max_phi_err(ca["{}__{}".format(tb, t)]) for t in TIERS) for tb in twist_beats}
    # (a) 段數 + 平增益 → 段數仍遞增、兩軸峰不遞增、且 φ 比值仍逐檔 ≈TWIST_PHI
    a_ok = (bool(twist_beats)
            and all(_is_strict_inc(v) for v in counts_flatgain.values())
            and all(not _is_strict_inc(v) for v in px_flatgain.values())
            and all(not _is_strict_inc(v) for v in py_flatgain.values())
            and all(v <= PHI_TOL for v in phi_flatgain.values()))
    # (b) 增益 + 無段數 → 段數恆 4、兩軸峰遞增
    counts_gainonly = {tb: [_nosc(amp_only["{}__{}".format(tb, t)]) for t in TIERS] for tb in twist_beats}
    px_gainonly = {tb: [round(_peak_x(amp_only["{}__{}".format(tb, t)]), 3) for t in TIERS] for tb in twist_beats}
    py_gainonly = {tb: [round(_peak_y(amp_only["{}__{}".format(tb, t)]), 3) for t in TIERS] for tb in twist_beats}
    b_ok = (bool(twist_beats) and all(v == [4, 4, 4, 4] for v in counts_gainonly.values())
            and all(_is_strict_inc(v) for v in px_gainonly.values())
            and all(_is_strict_inc(v) for v in py_gainonly.values()))
    R["TC4_orthogonality"] = {
        "a_counts_with_flat_gain": counts_flatgain, "a_peak_x_flat_gain": px_flatgain,
        "a_peak_y_flat_gain": py_flatgain,
        "a_max_phi_err_flat_gain": {k: round(v, 6) for k, v in phi_flatgain.items()}, "a_pass": a_ok,
        "b_gain_only_counts_fixed4": counts_gainonly, "b_gain_only_peak_x": px_gainonly,
        "b_gain_only_peak_y": py_gainonly, "b_pass": b_ok,
        "pass": a_ok and b_ok}

    # ---- TC5 negative controls ----
    tc5 = {}
    # (a) 平段數(全 4)→ 段數單調性 FALSE
    flat_cyc = {t: 4 for t in TIERS}
    fc = G.build_animations(skel, sb, tier_gains=gains, tier_twist_cycles=flat_cyc)
    any_mono_flat = any(_is_strict_inc([_nosc(fc["{}__{}".format(tb, t)]) for t in TIERS]) for tb in twist_beats)
    tc5["a_flat_cycles_guard"] = {"any_count_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) 無宣告段數的 genre → twist_cycles_for None + gains_for None → 不產 twist 段數變體
    rv_cyc = TV.twist_cycles_for("slot_reveal")
    rv_gains = TV.gains_for("slot_reveal")
    rv_sb = _storyboard("slot_reveal")
    rv_full = G.build_animations(skel, rv_sb, tier_gains=rv_gains, tier_twist_cycles=rv_cyc)
    rv_twist_variants = [k for k in rv_full if "__" in k and G.beat_category(k) == "twist"]
    tc5["b_no_cycle_genre"] = {"twist_cycles_for_slot_reveal": rv_cyc, "gains_for_slot_reveal": rv_gains,
                               "twist_variants": rv_twist_variants,
                               "pass": rv_cyc is None and not rv_twist_variants}
    # (c) 段數只作用於 twist:非-twist 主秀 beat 的 shear 段數在各檔位恆定(不外洩;wobble/squash 仍 4 段)
    leak = []
    for beat, cat in main_beats.items():
        if cat == "twist":
            continue
        counts = [_nosc(full["{}__{}".format(beat, t)]) for t in TIERS]
        if len(set(counts)) != 1:      # 段數外洩 → 各檔位不同
            leak.append((beat, cat, counts))
    tc5["c_cycles_isolated_to_twist"] = {"leaked": leak, "pass": not leak}
    R["TC5_neg_control"] = {**tc5, "pass": all(v["pass"] for v in tc5.values())}

    R["OVERALL_PASS"] = all(R[k]["pass"] for k in R)
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    R = run()
    if a.json:
        print(json.dumps(R, ensure_ascii=False, indent=2))
    else:
        for k in ["TC1_present_backward_compat", "TC2_count_monotone_phi_invariant",
                  "TC3_signature_preserved", "TC4_orthogonality", "TC5_neg_control"]:
            print("{:38s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("TC2 twist-segment counts per tier {} (+ max |phi_ratio-PHI|):".format(TIERS))
        for tb, d in R["TC2_count_monotone_phi_invariant"]["beats"].items():
            print("  {:10s} {}  (base {})  max_phi_err {}".format(
                tb, d["counts"], d["base_count"], d["max_phi_err"]))
        print("TC4(a) counts / peak_x with flat gain (count-axis isolated):")
        for tb in R["TC4_orthogonality"]["a_counts_with_flat_gain"]:
            print("  {:10s} counts {}  peak_x {}".format(
                tb, R["TC4_orthogonality"]["a_counts_with_flat_gain"][tb],
                R["TC4_orthogonality"]["a_peak_x_flat_gain"][tb]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
