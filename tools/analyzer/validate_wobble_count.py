#!/usr/bin/env python3
"""candidate (G-4''') 自我驗收閘 — wobble 振盪**段數**隨檔位遞增(count-aware,純 CPU)。

candidate (G-4'') 讓 wobble 的 shearX 峰**幅度**隨檔位遞增(愈高檔位愈斜),但各檔位仍是**同樣 4 段**
阻尼振盪 —— 有「多斜」沒「晃幾下」。本次 (G-4''') 補上 wobble 的振盪**段數** nosc **隨檔位嚴格遞增**
(Super 4 → Mega 5 → Omg 6 → Legend 7)。

**關鍵:幅度增益加不出振盪段數** —— 段數是關鍵幀**拓樸**(繞 0 交替的極值個數),必須在 `gen_wobble`
生成當下決定;事後 `amplify_bone_tl` 只能同比放大既有極值、無法多長一段。故不走 amplify,而是對 wobble
檔位變體以該檔位 nosc **重生成**整個 beat,再疊 (G-4'') 幅度增益 g → 與幅度軸**正交可疊**
(段數 [4,5,6,7] × 峰幅 [16,21.6,27.2,33.6]° 皆遞增)。此模式同 (J-2) 對 combo 連擊數所做,
惟段數階梯各類別獨立(combo→TIER_COMBO_HITS、wobble→TIER_WOBBLE_CYCLES,build_animations 依 cat 路由)。

真值界定同 (E/H/I/J/J-2/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位晃愈多段」是可量化的檔位簽章,用負對照證鑑別力(閘可信)。從**先驗庫** → **真實
build_spine robot 骨架** → `build_animations(..., tier_gains, tier_wobble_cycles)` 端到端量,與 (J)/(G-4'') 同一 fixture。

AC(客觀、可量測):
  U1 present + backward-compat : 每檔位 `wobble__{tier}` 皆產出、finite、有 bone、帶 shear 通道;
                                **base wobble 恆 4 段不變**(逐位元同無檔位);且**不帶** `tier_wobble_cycles`
                                (=None)時 wobble 變體逐位元同 (G-4'') 幅度-only 輸出(加性 opt-in 零回歸)。
  U2 crux — count monotone    : 各檔位 wobble 的振盪**段數**(繞 0 交替極值個數)== 宣告 [4,5,6,7] 且
                                Super<Mega<Omg<Legend **嚴格遞增**;Super 段數 == base 段數(向後相容)。
  U3 signature preserved       : **每檔位** wobble 仍 (a)首尾 shearX==0;(b)繞 0 變號 ≥3;(c)相繼極值幅度
                                嚴格遞減(阻尼)。**且**峰 |shearX| 仍隨檔位嚴格遞增(段數軸不破幅度軸,
                                兩效可疊)—— 段數增多不得破壞阻尼振盪簽章,亦不得抵消幅度階梯。
  U4 orthogonality             : (a) 段數 + **平增益**(全 g=1.0)→ 段數仍遞增(結構獨立於幅度)、峰幅**不**遞增;
                                (b) 增益 + **無段數**(twc=None)→ 段數恆 4、峰幅遞增(兩軸可獨立開關)。
  U5 neg-control               : (a) **平段數**(全 4)→ 段數單調性 FALSE(證閘測遞增非恆真);
                                (b) 無宣告的 genre(slot_reveal)→ `wobble_cycles_for` 回 None → 不亂加段數變體;
                                (c) 段數**只作用 wobble**:非-wobble 主秀 beat 的 shear 段數在各檔位恆定(不外洩)。

用法:
  python3 validate_wobble_count.py            # 摘要
  python3 validate_wobble_count.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
# 復用 G-4' 的 shear 讀取與阻尼簽章判準,確保與 shear-gen / wobble-tier 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
DEAD = 1e-6


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/wobble_count_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _wobble_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "wobble"]


def _main_beats(anims):
    return {nm: G.beat_category(nm) for nm in anims
            if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


def _nosc(anim):
    """該 anim 的 wobble 振盪段數 = 任一 shear bone 的**繞 0 交替極值個數**(=非零 shearX 關鍵幀數)。

    包絡 [0, e1, e2, …, e_nosc, 0] 每個內部極值皆交替變號 → 非零內部關鍵幀數即段數;
    各 bone 同形(僅 role 峰值 / side 反相不同)→ 取任一有 shear 的 bone。"""
    for ch in anim.get("bones", {}).values():
        sx = _shear_x(ch)
        if sx:
            return len([v for v in sx if abs(v) > DEAD])
    return 0


def _shear_peak(anim):
    """該 anim 全 bone 的峰 |shearX|(無 shear 回 0)。"""
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _is_strict_inc(xs):
    return len(xs) >= 2 and all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    cyc = TV.wobble_cycles_for(GENRE)

    base = G.build_animations(skel, sb)                                              # 無檔位
    amp_only = G.build_animations(skel, sb, tier_gains=gains)                        # (G-4'') 幅度-only
    full = G.build_animations(skel, sb, tier_gains=gains, tier_wobble_cycles=cyc)    # (G-4''') 幅度+段數

    wobble_beats = _wobble_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- U1 present + backward-compat ----
    u1 = {"wobble_beats": wobble_beats, "missing": [], "not_finite": [], "no_bones": [],
          "variant_no_shear": [], "base_changed": [], "amp_only_regressed": []}
    for wb in wobble_beats:
        for t in TIERS:
            vk = "{}__{}".format(wb, t)
            an = full.get(vk)
            if an is None:
                u1["missing"].append(vk); continue
            if not SA.all_finite(an):
                u1["not_finite"].append(vk)
            if not an.get("bones"):
                u1["no_bones"].append(vk)
            if not any(_shear_x(ch) for ch in an.get("bones", {}).values()):
                u1["variant_no_shear"].append(vk)
        # base wobble 恆 4 段且逐位元同無檔位
        if _nosc(full[wb]) != 4 or json.dumps(base[wb], sort_keys=True) != json.dumps(full[wb], sort_keys=True):
            u1["base_changed"].append(wb)
    # tier_wobble_cycles=None 時,wobble 變體逐位元同 (G-4'') 幅度-only(加性 opt-in)
    none_run = G.build_animations(skel, sb, tier_gains=gains, tier_wobble_cycles=None)
    for wb in wobble_beats:
        for t in TIERS:
            vk = "{}__{}".format(wb, t)
            if json.dumps(none_run.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                u1["amp_only_regressed"].append(vk)
    u1_pass = bool(wobble_beats) and not any(u1[k] for k in
              ["missing", "not_finite", "no_bones", "variant_no_shear", "base_changed", "amp_only_regressed"])
    R["U1_present_backward_compat"] = {**u1, "pass": u1_pass}

    # ---- U2 crux: oscillation-segment count monotone ----
    u2 = {"beats": {}, "fail": []}
    expected = [cyc[t] for t in TIERS]
    for wb in wobble_beats:
        counts = [_nosc(full["{}__{}".format(wb, t)]) for t in TIERS]
        base_count = _nosc(base[wb])
        mono = _is_strict_inc(counts)
        matches = (counts == expected)
        super_eq_base = (counts[0] == base_count)
        u2["beats"][wb] = {"counts": counts, "expected": expected, "base_count": base_count,
                           "monotone": mono, "matches_declared": matches, "super_eq_base": super_eq_base}
        if not (mono and matches and super_eq_base):
            u2["fail"].append(wb)
    u2_pass = bool(wobble_beats) and not u2["fail"]
    R["U2_count_monotone"] = {"tiers": TIERS, **u2, "pass": u2_pass}

    # ---- U3 damped signature preserved per tier + amplitude still monotone ----
    u3 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "amp_not_mono": [], "detail": {}}
    for wb in wobble_beats:
        for t in TIERS:
            an = full["{}__{}".format(wb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(wb, t, bn)
                ends_ok = abs(sx[0]) < DEAD and abs(sx[-1]) < DEAD
                nsc = _sign_changes_zero(sx)
                damp = _extrema_mags_decreasing(sx)
                u3["detail"][key] = {"n_sign_changes": nsc, "damped": damp}
                if not ends_ok:
                    u3["bad_endpoints"].append(key)
                if nsc < 3:
                    u3["few_sign_changes"].append(key)
                if not damp:
                    u3["not_damped"].append(key)
        # 峰幅仍隨檔位嚴格遞增(段數軸不抵消幅度軸)
        peaks = [_shear_peak(full["{}__{}".format(wb, t)]) for t in TIERS]
        if not _is_strict_inc(peaks):
            u3["amp_not_mono"].append((wb, [round(p, 3) for p in peaks]))
    u3_pass = (bool(u3["detail"]) and not u3["bad_endpoints"] and not u3["few_sign_changes"]
               and not u3["not_damped"] and not u3["amp_not_mono"])
    R["U3_signature_preserved"] = {**u3, "pass": u3_pass}

    # ---- U4 orthogonality ----
    # (a) 段數 + 平增益 → 段數仍遞增、峰幅不遞增(結構獨立於幅度)
    flat_gain = {t: 1.0 for t in TIERS}
    ca = G.build_animations(skel, sb, tier_gains=flat_gain, tier_wobble_cycles=cyc)
    counts_flatgain = {wb: [_nosc(ca["{}__{}".format(wb, t)]) for t in TIERS] for wb in wobble_beats}
    peaks_flatgain = {wb: [round(_shear_peak(ca["{}__{}".format(wb, t)]), 3) for t in TIERS] for wb in wobble_beats}
    a_ok = (bool(wobble_beats) and all(_is_strict_inc(v) for v in counts_flatgain.values())
            and all(not _is_strict_inc(v) for v in peaks_flatgain.values()))
    # (b) 增益 + 無段數 → 段數恆 4、峰幅遞增
    counts_gainonly = {wb: [_nosc(amp_only["{}__{}".format(wb, t)]) for t in TIERS] for wb in wobble_beats}
    peaks_gainonly = {wb: [round(_shear_peak(amp_only["{}__{}".format(wb, t)]), 3) for t in TIERS] for wb in wobble_beats}
    b_ok = (bool(wobble_beats) and all(v == [4, 4, 4, 4] for v in counts_gainonly.values())
            and all(_is_strict_inc(v) for v in peaks_gainonly.values()))
    R["U4_orthogonality"] = {
        "a_counts_with_flat_gain": counts_flatgain, "a_peaks_with_flat_gain": peaks_flatgain, "a_pass": a_ok,
        "b_gain_only_counts_fixed4": counts_gainonly, "b_gain_only_peaks": peaks_gainonly, "b_pass": b_ok,
        "pass": a_ok and b_ok}

    # ---- U5 negative controls ----
    u5 = {}
    # (a) 平段數(全 4)→ 段數單調性 FALSE
    flat_cyc = {t: 4 for t in TIERS}
    fc = G.build_animations(skel, sb, tier_gains=gains, tier_wobble_cycles=flat_cyc)
    any_mono_flat = any(_is_strict_inc([_nosc(fc["{}__{}".format(wb, t)]) for t in TIERS]) for wb in wobble_beats)
    u5["a_flat_cycles_guard"] = {"any_count_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) 無宣告段數的 genre → wobble_cycles_for None → 不產段數變體(此 fixture 借 slot_bigwin 骨架 + slot_reveal 分鏡)
    rv_cyc = TV.wobble_cycles_for("slot_reveal")
    rv_sb = _storyboard("slot_reveal")
    rv_gains = TV.gains_for("slot_reveal")
    rv_full = G.build_animations(skel, rv_sb, tier_gains=rv_gains, tier_wobble_cycles=rv_cyc)
    rv_wobble_variants = [k for k in rv_full if "__" in k and G.beat_category(k) == "wobble"]
    u5["b_no_cycle_genre"] = {"wobble_cycles_for_slot_reveal": rv_cyc,
                              "wobble_variants": rv_wobble_variants,
                              "pass": rv_cyc is None and not rv_wobble_variants}
    # (c) 段數只作用於 wobble:非-wobble 主秀 beat 的 shear 段數在各檔位恆定(不外洩)
    leak = []
    for beat, cat in main_beats.items():
        if cat == "wobble":
            continue
        counts = [_nosc(full["{}__{}".format(beat, t)]) for t in TIERS]
        if len(set(counts)) != 1:      # 段數外洩 → 各檔位不同
            leak.append((beat, cat, counts))
    u5["c_cycles_isolated_to_wobble"] = {"leaked": leak, "pass": not leak}
    R["U5_neg_control"] = {**u5, "pass": all(v["pass"] for v in u5.values())}

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
        for k in ["U1_present_backward_compat", "U2_count_monotone",
                  "U3_signature_preserved", "U4_orthogonality", "U5_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("U2 osc-segment counts per tier {}:".format(TIERS))
        for wb, d in R["U2_count_monotone"]["beats"].items():
            print("  {:10s} {}  (base {})".format(wb, d["counts"], d["base_count"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
