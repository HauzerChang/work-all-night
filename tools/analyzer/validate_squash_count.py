#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash 擠壓**段數**隨檔位遞增(count-aware,純 CPU)。

candidate (G-4'''') 讓 `gen_squash`(斜拉果凍擠壓)成為**第一個同時產 shear + 非均勻 scale**(體積守恆)
的生成器,但所有檔位仍是**同樣 4 段**擠壓 —— 有「擠多深」沒「擠幾下」。且 squash **不在** MAIN_SHOW_CATS
(其 scaleY<1 樓地板會被 (J) 的 `_amp_scale` 保留、scaleX>1 被放大 → 破壞 scaleX·scaleY==1 體積守恆),
故 (J) 的幅度差異化對 squash 為 honest boundary(需**耦合 amplify**,後續)。

本次 (G-4''''') 補上 squash 的擠壓**段數** nosc **隨檔位嚴格遞增**(Super 4 → Mega 5 → Omg 6 → Legend 7),
**繞開幅度軸**:段數是關鍵幀**拓樸**(繞 0 交替的極值個數),必須在 `gen_squash` 生成當下決定;事後 amplify
只能同比放大既有極值、加不出一段(同 (J-2) combo / (G-4''') wobble)。**關鍵:段數軸不需碰幅度**——對 squash
以該檔位 nosc **重生成**整支 beat 而**不套幅度增益**(g≡1.0)→ 擠壓段數隨檔位遞增,而每幀仍**嚴格體積守恆**
(scaleX·scaleY≡1、非均勻);首極值幅度(shear 峰 / 擠壓峰)各檔位恆定。此為「結構軸可獨立於未接的幅度軸
推進」——squash 的檔位差異化先拿下**能不破壞守恆就拿下**的那一半。

真值界定同 (G-4'/G-4''/G-4'''/G-4''''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**
(阻尼振盪 + 體積守恆耦合 + 段數遞增),負對照證鑑別力(閘可信)。從**先驗庫**(slot_bigwin)→ **真實
build_spine robot 骨架** → `build_animations(..., tier_squash_cycles)` 端到端量,與 (G-4'''') 同一 fixture。

AC(客觀、可量測):
  V1 present + backward-compat : 每檔位 `squash__{tier}` 皆產出、finite、有 bone、**同時**帶 shear+scale
                                雙通道;**base squash 恆 4 段不變**(逐位元同無檔位);且**不帶**
                                `tier_squash_cycles`(=None)時**完全不產** squash 變體(加性 opt-in 零回歸),
                                連帶 tier_gains 單開也不產 squash 變體(squash 不在 MAIN_SHOW_CATS)。
  V2 crux — count monotone    : 各檔位 squash 的擠壓**段數**由 **shear 與 scale 兩通道各自**量得,皆
                                == 宣告 [4,5,6,7]、皆 Super<Mega<Omg<Legend **嚴格遞增**、**兩通道段數相等**
                                (同 nosc 耦合驅動);Super 段數 == base 段數(向後相容)。
  V3 signature preserved       : **每檔位** squash 仍 (a)shearX 首尾 0 + 繞 0 變號 ≥3 + 相繼極值嚴格遞減(阻尼);
                                (b)**體積守恆耦合(crux)**:每個 scale 極值幀 scaleX·scaleY≈1、至少一極值非均勻
                                |scaleX−scaleY|≥MIN_ANISO、擠壓幅度隨極值嚴格遞減 —— 段數增多**不得破壞守恆**。
  V4 no-amplitude(honest)     : squash 變體**只走段數軸、不套幅度增益**:各檔位 (a)shear 峰恆定、(b)非均勻峰
                                恆定(皆 == base,**不**隨檔位遞增)——證段數軸與未接的幅度軸互不干涉(對照
                                wobble/combo 段數變體會再疊 (J) 幅度增益,squash 刻意不疊以守恆);
                                (c)tier_gains 單開(twc/tsc 皆不影響)→ 仍**零** squash 變體(不在 MAIN_SHOW)。
  V5 neg-control               : (a) **平段數**(全 4)→ 段數單調性 FALSE(證閘測遞增非恆真);
                                (b) 無宣告的 genre(slot_reveal)→ `squash_cycles_for` 回 None → 不產段數變體;
                                (c) 段數**只作用 squash**:非-squash 主秀 beat 各檔位段數/存在性不受 tsc 影響(不外洩)。

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
# 復用 G-4' 的 shear 讀取與阻尼簽章判準、G-4'''' 的 scale 讀取與體積守恆判準 → 與 shear-gen/squash-gen 閘一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import _scale_xy, _interior_scale, _sq3_eval, MIN_ANISO

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
DEAD = 1e-6


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
    return {nm: G.beat_category(nm) for nm in anims
            if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


def _nosc_shear(anim):
    """squash 段數(shear 通道)= 任一 shear bone 的繞 0 交替極值個數(=非零 shearX 內部關鍵幀數)。"""
    for ch in anim.get("bones", {}).values():
        sx = _shear_x(ch)
        if sx:
            return len([v for v in sx if abs(v) > DEAD])
    return 0


def _nosc_scale(anim):
    """squash 段數(scale 通道)= 任一 scale bone 的**內部**極值個數(去掉首尾 (1,1) identity 端點)。

    squash 每個 shear 極值時刻施一次 squash → 內部 scale 極值數 == 擠壓段數(與 shear 段數耦合相等)。"""
    for ch in anim.get("bones", {}).values():
        if _scale_xy(ch):
            return len(_interior_scale(ch))
    return 0


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _aniso_peak(anim):
    """該 anim 全 bone 的峰非均勻 |scaleX−scaleY|(無 scale 回 0)。"""
    peaks = [max(abs(sx - sy) for (sx, sy) in _scale_xy(ch))
             for ch in anim.get("bones", {}).values() if _scale_xy(ch)]
    return max(peaks, default=0.0)


def _is_strict_inc(xs):
    return len(xs) >= 2 and all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def _all_equal(xs, tol=1e-6):
    return len(xs) >= 2 and all(abs(xs[i] - xs[0]) <= tol for i in range(len(xs)))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    cyc = TV.squash_cycles_for(GENRE)

    base = G.build_animations(skel, sb)                                              # 無檔位
    full = G.build_animations(skel, sb, tier_squash_cycles=cyc)                      # (G-4''''') 段數變體
    gain_only = G.build_animations(skel, sb, tier_gains=gains)                       # 幅度-only(squash 不受影響)

    squash_beats = _squash_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- V1 present + backward-compat + additive opt-in ----
    v1 = {"squash_beats": squash_beats, "missing": [], "not_finite": [], "no_bones": [],
          "not_dual_channel": [], "base_changed": [], "none_produced_variants": [],
          "gain_only_produced_variants": []}
    for qb in squash_beats:
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = full.get(vk)
            if an is None:
                v1["missing"].append(vk); continue
            if not SA.all_finite(an):
                v1["not_finite"].append(vk)
            if not an.get("bones"):
                v1["no_bones"].append(vk)
            if not any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values()):
                v1["not_dual_channel"].append(vk)
        # base squash 恆 4 段且逐位元同無檔位
        if _nosc_shear(full[qb]) != 4 or json.dumps(base[qb], sort_keys=True) != json.dumps(full[qb], sort_keys=True):
            v1["base_changed"].append(qb)
    # tier_squash_cycles=None(且無 tier_gains)→ 完全不產 squash 變體
    none_run = G.build_animations(skel, sb, tier_squash_cycles=None)
    v1["none_produced_variants"] = [k for k in none_run if "__" in k and G.beat_category(k) == "squash"]
    # tier_gains 單開 → squash 不在 MAIN_SHOW_CATS → 仍不產 squash 變體
    v1["gain_only_produced_variants"] = [k for k in gain_only if "__" in k and G.beat_category(k) == "squash"]
    v1_pass = bool(squash_beats) and not any(v1[k] for k in
              ["missing", "not_finite", "no_bones", "not_dual_channel", "base_changed",
               "none_produced_variants", "gain_only_produced_variants"])
    R["V1_present_backward_compat"] = {**v1, "pass": v1_pass}

    # ---- V2 crux: squash-segment count monotone (both channels, coupled-equal) ----
    v2 = {"beats": {}, "fail": []}
    expected = [cyc[t] for t in TIERS]
    for qb in squash_beats:
        sh_counts = [_nosc_shear(full["{}__{}".format(qb, t)]) for t in TIERS]
        sc_counts = [_nosc_scale(full["{}__{}".format(qb, t)]) for t in TIERS]
        base_sh = _nosc_shear(base[qb])
        base_sc = _nosc_scale(base[qb])
        mono = _is_strict_inc(sh_counts) and _is_strict_inc(sc_counts)
        matches = (sh_counts == expected and sc_counts == expected)
        channels_agree = (sh_counts == sc_counts)
        super_eq_base = (sh_counts[0] == base_sh and sc_counts[0] == base_sc)
        v2["beats"][qb] = {"shear_counts": sh_counts, "scale_counts": sc_counts, "expected": expected,
                           "base_shear": base_sh, "base_scale": base_sc, "monotone": mono,
                           "matches_declared": matches, "channels_agree": channels_agree,
                           "super_eq_base": super_eq_base}
        if not (mono and matches and channels_agree and super_eq_base):
            v2["fail"].append(qb)
    v2_pass = bool(squash_beats) and not v2["fail"]
    R["V2_count_monotone"] = {"tiers": TIERS, **v2, "pass": v2_pass}

    # ---- V3 signature preserved per tier: damped shear + volume-preserving coupling ----
    v3 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped_shear": [],
          "bad_volume": [], "no_aniso": [], "not_damped_squash": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = full["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                # (a) damped shear oscillation
                ends_ok = abs(sx[0]) < DEAD and abs(sx[-1]) < DEAD
                nsc = _sign_changes_zero(sx)
                damp_sh = _extrema_mags_decreasing(sx)
                # (b) volume-preserving squash coupling (SQ3 判準,復用 squash-gen 閘)
                vol_ok, aniso_ok, damp_sq, sq_detail = _sq3_eval(_interior_scale(ch))
                v3["detail"][key] = {"n_sign_changes": nsc, "damped_shear": damp_sh,
                                     "volume_ok": vol_ok, "aniso_ok": aniso_ok, "damped_squash": damp_sq,
                                     **sq_detail}
                if not ends_ok:
                    v3["bad_endpoints"].append(key)
                if nsc < 3:
                    v3["few_sign_changes"].append(key)
                if not damp_sh:
                    v3["not_damped_shear"].append(key)
                if not vol_ok:
                    v3["bad_volume"].append(key)
                if not aniso_ok:
                    v3["no_aniso"].append(key)
                if not damp_sq:
                    v3["not_damped_squash"].append(key)
    v3_pass = (bool(v3["detail"]) and not v3["bad_endpoints"] and not v3["few_sign_changes"]
               and not v3["not_damped_shear"] and not v3["bad_volume"] and not v3["no_aniso"]
               and not v3["not_damped_squash"])
    R["V3_signature_preserved"] = {**v3, "pass": v3_pass}

    # ---- V4 no-amplitude (honest boundary): count axis carries NO amplitude gain ----
    v4 = {"shear_peaks": {}, "aniso_peaks": {}, "shear_not_flat": [], "aniso_not_flat": [],
          "shear_ne_base": [], "aniso_ne_base": []}
    for qb in squash_beats:
        sh_peaks = [round(_shear_peak(full["{}__{}".format(qb, t)]), 4) for t in TIERS]
        an_peaks = [round(_aniso_peak(full["{}__{}".format(qb, t)]), 4) for t in TIERS]
        base_sh = round(_shear_peak(base[qb]), 4)
        base_an = round(_aniso_peak(base[qb]), 4)
        v4["shear_peaks"][qb] = {"tiers": sh_peaks, "base": base_sh}
        v4["aniso_peaks"][qb] = {"tiers": an_peaks, "base": base_an}
        # (a)(b) 各檔位峰恆定(不隨檔位遞增)且 == base
        if not _all_equal(sh_peaks):
            v4["shear_not_flat"].append((qb, sh_peaks))
        if not _all_equal(an_peaks):
            v4["aniso_not_flat"].append((qb, an_peaks))
        if abs(sh_peaks[0] - base_sh) > 1e-6:
            v4["shear_ne_base"].append((qb, sh_peaks[0], base_sh))
        if abs(an_peaks[0] - base_an) > 1e-6:
            v4["aniso_ne_base"].append((qb, an_peaks[0], base_an))
    # (c) tier_gains 單開 → squash 仍零變體(復用 V1 的量測)
    c_ok = not v1["gain_only_produced_variants"]
    v4_pass = (bool(squash_beats) and not v4["shear_not_flat"] and not v4["aniso_not_flat"]
               and not v4["shear_ne_base"] and not v4["aniso_ne_base"] and c_ok)
    R["V4_no_amplitude"] = {**v4, "c_gain_only_zero_squash_variants": c_ok, "pass": v4_pass}

    # ---- V5 negative controls ----
    v5 = {}
    # (a) 平段數(全 4)→ 段數單調性 FALSE
    flat_cyc = {t: 4 for t in TIERS}
    fc = G.build_animations(skel, sb, tier_squash_cycles=flat_cyc)
    any_mono_flat = any(_is_strict_inc([_nosc_shear(fc["{}__{}".format(qb, t)]) for t in TIERS])
                        for qb in squash_beats)
    v5["a_flat_cycles_guard"] = {"any_count_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) 無宣告段數的 genre → squash_cycles_for None → 不產段數變體
    rv_cyc = TV.squash_cycles_for("slot_reveal")
    rv_sb = _storyboard("slot_reveal")
    rv_full = G.build_animations(skel, rv_sb, tier_squash_cycles=rv_cyc)
    rv_squash_variants = [k for k in rv_full if "__" in k and G.beat_category(k) == "squash"]
    v5["b_no_cycle_genre"] = {"squash_cycles_for_slot_reveal": rv_cyc,
                              "squash_variants": rv_squash_variants,
                              "pass": rv_cyc is None and not rv_squash_variants}
    # (c) 段數只作用 squash:非-squash 主秀 beat 不因 tsc 產生額外變體/段數擾動
    #     (full 只給 tsc → 非-squash 主秀 beat 不應有任何 __tier 變體)
    leak = [k for k in full if "__" in k and G.beat_category(k) != "squash"]
    v5["c_cycles_isolated_to_squash"] = {"leaked_variants": leak, "pass": not leak}
    R["V5_neg_control"] = {**v5, "pass": all(v["pass"] for v in v5.values())}

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
        for k in ["V1_present_backward_compat", "V2_count_monotone", "V3_signature_preserved",
                  "V4_no_amplitude", "V5_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V2 squash-segment counts per tier {} (shear / scale):".format(TIERS))
        for qb, d in R["V2_count_monotone"]["beats"].items():
            print("  {:12s} shear {}  scale {}  (base {})".format(
                qb, d["shear_counts"], d["scale_counts"], d["base_shear"]))
        print("V4 peaks flat across tiers (shear° / aniso):")
        for qb in R["V4_no_amplitude"]["shear_peaks"]:
            print("  {:12s} shear {}  aniso {}".format(
                qb, R["V4_no_amplitude"]["shear_peaks"][qb]["tiers"],
                R["V4_no_amplitude"]["aniso_peaks"][qb]["tiers"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
