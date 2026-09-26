#!/usr/bin/env python3
"""candidate (G-4'''''-c) 自我驗收閘 — squash 擠壓**段數**隨檔位遞增(count-aware,純 CPU)。

candidate (G-4''''')(`validate_squash_tier.py`)讓 squash 的 shear 峰**幅度**與非均勻 scale 擠壓**幅度**
隨檔位遞增(愈高檔位擠壓愈強),而體積守恆 scaleX·scaleY≡1 在任一檔位保持;但各檔位仍是**同樣 4 段**
阻尼擠壓 —— 有「擠得多深」沒「擠幾下」。本次 (G-4'''''-c) 補上 squash 的擠壓**段數** nosc **隨檔位嚴格遞增**
(Super 4 → Mega 5 → Omg 6 → Legend 7)。

**關鍵:幅度增益加不出擠壓段數** —— 段數是關鍵幀**拓樸**(繞 0 交替的 shear 極值個數 = 耦合 squash 極值個數),
必須在 `gen_squash` 生成當下決定;事後 `amplify_bone_tl` 只能同比放大既有極值、無法多長一段。故不走 amplify,
而是對 squash 檔位變體以該檔位 nosc **重生成**整個 beat,再疊 (G-4''''') 的**耦合**幅度增益 g。此模式同
(G-4''')對 wobble、(J-2)對 combo 所做,惟段數階梯各類別獨立(squash→TIER_SQUASH_CYCLES,build_animations 依 cat 路由)。

**squash 獨有的 crux(與 wobble count 的差異)**:squash∈COUPLED_SCALE_CATS —— 段數重生成後仍走耦合 amplify,
故段數×幅度×**體積守恆**三效必須**同時**成立:每個檔位、每個(新增的)擠壓極值都要 |scaleX·scaleY−1|≤TOL_VOL。
段數增多會多長出低幅擠壓極值(q_i=Q·rⁱ 隨 i 遞減),閘須證這些新極值也守恆(不只是原 4 段)。

真值界定同 (E/H/I/J/J-2/G-4'/G-4''/G-4''''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章**非美感;
「愈高檔位擠愈多段且每段仍體積守恆」是可量化的檔位簽章,用負對照證鑑別力(閘可信)。從**先驗庫** →
**真實 build_spine robot 骨架** → `build_animations(..., tier_gains, tier_squash_cycles)` 端到端量,與 (J)/(G-4''''') 同一 fixture。

AC(客觀、可量測):
  SC1 present + backward-compat : 每檔位 `squash__{tier}` 皆產出、finite、有 bone、≥1 bone **同時**帶 shear+scale;
                                 **base squash 恆 4 段不變**(逐位元同無 count);且**不帶** `tier_squash_cycles`
                                 (=None)時 squash 變體逐位元同 (G-4''''') 幅度-only 輸出(加性 opt-in 零回歸)。
  SC2 crux — count↑ ∧ 守恆      : (a) 各檔位 squash 的擠壓**段數**(繞 0 交替 shear 極值個數)== 宣告 [4,5,6,7]
                                 且 Super<Mega<Omg<Legend **嚴格遞增**、Super 段數 == base 段數(向後相容);
                                 (b) **每個檔位、每個內部 scale 極值** |scaleX·scaleY−1|≤TOL_VOL —— 段數增多
                                 (多長低幅擠壓極值)仍不破體積守恆(段數×幅度×守恆三效正交可疊,squash count 獨有 crux)。
  SC3 signature preserved       : **每檔位** squash 仍 (a)首尾 shearX==0;(b)繞 0 變號 ≥3;(c)相繼 shear 極值幅度
                                 嚴格遞減(阻尼)。**且**峰 |shearX| 與峰非均勻 |scaleX−scaleY| 仍隨檔位嚴格遞增
                                 (段數軸不破幅度/擠壓軸)—— 段數增多不得破壞阻尼簽章、亦不得抵消幅度階梯。
  SC4 orthogonality             : (a) 段數 + **平增益**(全 g=1.0)→ 段數仍遞增(結構獨立於幅度)、峰非均勻**不**遞增,
                                 **且體積守恆仍保持**(段數單獨作用亦不破守恆);
                                 (b) 增益 + **無段數**(tsc=None)→ 段數恆 4、峰非均勻遞增(兩軸可獨立開關)。
  SC5 neg-control               : (a) **平段數**(全 4)→ 段數單調性 FALSE(證閘測遞增非恆真);
                                 (b) 無宣告的 genre(slot_reveal)→ `squash_cycles_for` 回 None 且無檔位增益 → 不產 squash 段數變體;
                                 (c) 段數**只作用 squash**:非-squash 主秀 beat 的 shear 段數在各檔位恆定(不外洩;wobble 仍 4 段)。

用法:
  python3 validate_squash_count.py            # 摘要
  python3 validate_squash_count.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
# 復用 G-4' 的 shear 讀取與阻尼簽章判準(與 shear-gen / wobble-count / squash-tier 閘完全一致)
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
# 復用 G-4'''' 的 scale 讀取 / 內部極值(與 squash-gen / squash-tier 閘完全一致)
from validate_squash_gen import _scale_xy, _interior_scale

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
DEAD = 1e-6
TOL_VOL = 2e-4      # 體積守恆 |scaleX·scaleY−1| 上限(同 squash-tier;耦合 amplify 主誤差為倒數 4 位捨入)


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/squash_count_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _squash_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "squash"]


def _main_beats(anims):
    # G-4''''''-vol:twist_vol(體積守恆扭轉)為 base-only 主秀節拍(未接 tier/count 差異化,無 {nm}__{tier} 變體)
    # → 排除,避免下方隔離檢查索引其不存在的檔位變體(KeyError);它本非 tier 差異化 beat。
    return {nm: G.beat_category(nm) for nm in anims
            if "__" not in nm and "vol" not in nm.lower() and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


def _nosc(anim):
    """該 anim 的 squash 擠壓段數 = 任一帶 shear bone 的**繞 0 交替 shear 極值個數**(= 非零 shearX 關鍵幀數)。

    squash shear 包絡 [0, e1, …, e_nosc, 0] 與 wobble 同形 → 非零內部關鍵幀數即段數;各 bone 同形
    (僅 role 峰值 / side 反相不同)→ 取任一有 shear 的 bone。scale 擠壓極值與 shear 極值同時刻(耦合)→ 段數一致。"""
    for ch in anim.get("bones", {}).values():
        sx = _shear_x(ch)
        if sx:
            return len([v for v in sx if abs(v) > DEAD])
    return 0


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _aniso_peak(anim):
    """該 anim 全 bone 的峰非均勻 |scaleX−scaleY|(無 scale 回 0)。"""
    vals = []
    for ch in anim.get("bones", {}).values():
        xy = _scale_xy(ch)
        if xy:
            vals.append(max(abs(sx - sy) for (sx, sy) in xy))
    return max(vals, default=0.0)


def _max_vol_err(anim):
    """該 anim 全 bone 每內部 scale 極值 max |scaleX·scaleY−1|(無 scale 回 0)。"""
    errs = []
    for ch in anim.get("bones", {}).values():
        for (sx, sy) in _interior_scale(ch):
            errs.append(abs(sx * sy - 1.0))
    return max(errs, default=0.0)


def _dual_bones(anim):
    """≥1 bone 同時帶 shear 與 scale 通道 → dict {bone: chans}。"""
    return {bn: ch for bn, ch in anim.get("bones", {}).items() if _shear_x(ch) and _scale_xy(ch)}


def _is_strict_inc(xs):
    return len(xs) >= 2 and all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    cyc = TV.squash_cycles_for(GENRE)

    base = G.build_animations(skel, sb)                                              # 無檔位
    amp_only = G.build_animations(skel, sb, tier_gains=gains)                        # (G-4''''') 幅度-only(耦合)
    full = G.build_animations(skel, sb, tier_gains=gains, tier_squash_cycles=cyc)    # (G-4'''''-c) 幅度+段數
    squash_beats = _squash_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- SC1 present + backward-compat ----
    sc1 = {"squash_beats": squash_beats, "missing": [], "not_finite": [], "no_bones": [],
           "variant_no_dual": [], "base_changed": [], "amp_only_regressed": []}
    for qb in squash_beats:
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = full.get(vk)
            if an is None:
                sc1["missing"].append(vk); continue
            if not SA.all_finite(an):
                sc1["not_finite"].append(vk)
            if not an.get("bones"):
                sc1["no_bones"].append(vk)
            if not _dual_bones(an):
                sc1["variant_no_dual"].append(vk)
        # base squash 恆 4 段且逐位元同無檔位
        if _nosc(full[qb]) != 4 or json.dumps(base[qb], sort_keys=True) != json.dumps(full[qb], sort_keys=True):
            sc1["base_changed"].append(qb)
    # tier_squash_cycles=None 時,squash 變體逐位元同 (G-4''''') 幅度-only(加性 opt-in)
    none_run = G.build_animations(skel, sb, tier_gains=gains, tier_squash_cycles=None)
    for qb in squash_beats:
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            if json.dumps(none_run.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                sc1["amp_only_regressed"].append(vk)
    sc1_pass = bool(squash_beats) and not any(sc1[k] for k in
               ["missing", "not_finite", "no_bones", "variant_no_dual", "base_changed", "amp_only_regressed"])
    R["SC1_present_backward_compat"] = {**sc1, "pass": sc1_pass}

    # ---- SC2 crux: count monotone AND volume conserved per extremum at every tier ----
    sc2 = {"beats": {}, "fail_count": [], "bad_volume": []}
    expected = [cyc[t] for t in TIERS]
    for qb in squash_beats:
        counts = [_nosc(full["{}__{}".format(qb, t)]) for t in TIERS]
        base_count = _nosc(base[qb])
        mono = _is_strict_inc(counts)
        matches = (counts == expected)
        super_eq_base = (counts[0] == base_count)
        # 每檔位每 bone 每內部 scale 極值 volume ok(段數增多的低幅極值也要守恆)
        vol_errs = {}
        for t in TIERS:
            an = full["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior or not _shear_x(ch):
                    continue
                err = max(abs(sx * sy - 1.0) for (sx, sy) in interior)
                vol_errs["{}__{}::{}".format(qb, t, bn)] = round(err, 6)
                if err > TOL_VOL:
                    sc2["bad_volume"].append("{}__{}::{}".format(qb, t, bn))
        sc2["beats"][qb] = {"counts": counts, "expected": expected, "base_count": base_count,
                            "monotone": mono, "matches_declared": matches, "super_eq_base": super_eq_base,
                            "max_vol_err": round(max(vol_errs.values(), default=0.0), 6)}
        if not (mono and matches and super_eq_base):
            sc2["fail_count"].append(qb)
    sc2_pass = bool(squash_beats) and not sc2["fail_count"] and not sc2["bad_volume"]
    R["SC2_count_monotone_volume_conserved"] = {"tiers": TIERS, **sc2, "pass": sc2_pass}

    # ---- SC3 damped signature preserved per tier + amplitude (shear + aniso) still monotone ----
    sc3 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [],
           "shear_not_mono": [], "aniso_not_mono": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = full["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                ends_ok = abs(sx[0]) < DEAD and abs(sx[-1]) < DEAD
                nsc = _sign_changes_zero(sx)
                damp = _extrema_mags_decreasing(sx)
                sc3["detail"][key] = {"n_sign_changes": nsc, "damped": damp}
                if not ends_ok:
                    sc3["bad_endpoints"].append(key)
                if nsc < 3:
                    sc3["few_sign_changes"].append(key)
                if not damp:
                    sc3["not_damped"].append(key)
        # 峰 |shearX| 與峰非均勻皆仍隨檔位嚴格遞增(段數軸不抵消幅度/擠壓軸)
        shear_peaks = [_shear_peak(full["{}__{}".format(qb, t)]) for t in TIERS]
        aniso_peaks = [_aniso_peak(full["{}__{}".format(qb, t)]) for t in TIERS]
        if not _is_strict_inc(shear_peaks):
            sc3["shear_not_mono"].append((qb, [round(p, 3) for p in shear_peaks]))
        if not _is_strict_inc(aniso_peaks):
            sc3["aniso_not_mono"].append((qb, [round(p, 4) for p in aniso_peaks]))
    sc3_pass = (bool(sc3["detail"]) and not any(sc3[k] for k in
                ["bad_endpoints", "few_sign_changes", "not_damped", "shear_not_mono", "aniso_not_mono"]))
    R["SC3_signature_preserved"] = {**sc3, "pass": sc3_pass}

    # ---- SC4 orthogonality ----
    flat_gain = {t: 1.0 for t in TIERS}
    ca = G.build_animations(skel, sb, tier_gains=flat_gain, tier_squash_cycles=cyc)
    counts_flatgain = {qb: [_nosc(ca["{}__{}".format(qb, t)]) for t in TIERS] for qb in squash_beats}
    aniso_flatgain = {qb: [round(_aniso_peak(ca["{}__{}".format(qb, t)]), 4) for t in TIERS] for qb in squash_beats}
    vol_flatgain = {qb: max(_max_vol_err(ca["{}__{}".format(qb, t)]) for t in TIERS) for qb in squash_beats}
    # (a) 段數 + 平增益 → 段數仍遞增、峰非均勻不遞增、且體積守恆仍保持
    a_ok = (bool(squash_beats)
            and all(_is_strict_inc(v) for v in counts_flatgain.values())
            and all(not _is_strict_inc(v) for v in aniso_flatgain.values())
            and all(v <= TOL_VOL for v in vol_flatgain.values()))
    # (b) 增益 + 無段數 → 段數恆 4、峰非均勻遞增
    counts_gainonly = {qb: [_nosc(amp_only["{}__{}".format(qb, t)]) for t in TIERS] for qb in squash_beats}
    aniso_gainonly = {qb: [round(_aniso_peak(amp_only["{}__{}".format(qb, t)]), 4) for t in TIERS] for qb in squash_beats}
    b_ok = (bool(squash_beats) and all(v == [4, 4, 4, 4] for v in counts_gainonly.values())
            and all(_is_strict_inc(v) for v in aniso_gainonly.values()))
    R["SC4_orthogonality"] = {
        "a_counts_with_flat_gain": counts_flatgain, "a_aniso_with_flat_gain": aniso_flatgain,
        "a_max_vol_err_flat_gain": {k: round(v, 6) for k, v in vol_flatgain.items()}, "a_pass": a_ok,
        "b_gain_only_counts_fixed4": counts_gainonly, "b_gain_only_aniso": aniso_gainonly, "b_pass": b_ok,
        "pass": a_ok and b_ok}

    # ---- SC5 negative controls ----
    sc5 = {}
    # (a) 平段數(全 4)→ 段數單調性 FALSE
    flat_cyc = {t: 4 for t in TIERS}
    fc = G.build_animations(skel, sb, tier_gains=gains, tier_squash_cycles=flat_cyc)
    any_mono_flat = any(_is_strict_inc([_nosc(fc["{}__{}".format(qb, t)]) for t in TIERS]) for qb in squash_beats)
    sc5["a_flat_cycles_guard"] = {"any_count_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) 無宣告段數的 genre → squash_cycles_for None + gains_for None → 不產 squash 段數變體
    rv_cyc = TV.squash_cycles_for("slot_reveal")
    rv_gains = TV.gains_for("slot_reveal")
    rv_sb = _storyboard("slot_reveal")
    rv_full = G.build_animations(skel, rv_sb, tier_gains=rv_gains, tier_squash_cycles=rv_cyc)
    rv_squash_variants = [k for k in rv_full if "__" in k and G.beat_category(k) == "squash"]
    sc5["b_no_cycle_genre"] = {"squash_cycles_for_slot_reveal": rv_cyc, "gains_for_slot_reveal": rv_gains,
                               "squash_variants": rv_squash_variants,
                               "pass": rv_cyc is None and not rv_squash_variants}
    # (c) 段數只作用於 squash:非-squash 主秀 beat 的 shear 段數在各檔位恆定(不外洩;wobble 仍 4 段)
    leak = []
    for beat, cat in main_beats.items():
        if cat == "squash":
            continue
        counts = [_nosc(full["{}__{}".format(beat, t)]) for t in TIERS]
        if len(set(counts)) != 1:      # 段數外洩 → 各檔位不同
            leak.append((beat, cat, counts))
    sc5["c_cycles_isolated_to_squash"] = {"leaked": leak, "pass": not leak}
    R["SC5_neg_control"] = {**sc5, "pass": all(v["pass"] for v in sc5.values())}

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
        for k in ["SC1_present_backward_compat", "SC2_count_monotone_volume_conserved",
                  "SC3_signature_preserved", "SC4_orthogonality", "SC5_neg_control"]:
            print("{:36s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("SC2 squash-segment counts per tier {} (+ max |scaleX*scaleY-1|):".format(TIERS))
        for qb, d in R["SC2_count_monotone_volume_conserved"]["beats"].items():
            print("  {:10s} {}  (base {})  max_vol_err {}".format(
                qb, d["counts"], d["base_count"], d["max_vol_err"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
