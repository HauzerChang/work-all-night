#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

補上 (G-4'''') 留的 honest boundary:「squash 未接 tier 幅度差異化」。當時 squash **刻意排除**於
`MAIN_SHOW_CATS`,因為天真的 `_amp_scale`(只放大 identity 上方 overshoot、下方 squash/collapse 樓地板
不動)套到 squash 會**放大 scaleX>1 卻凍結 scaleY<1** → 破壞體積守恆(scaleX·scaleY≠1)。本次(G-4''''')
把 squash 併入 `MAIN_SHOW_CATS`,並讓 build_animations 對 squash 走 `_amp_scale_coupled`(**體積守恆耦合
放大**:拉長軸線性放大、壓縮軸取倒數 → 積恆 1),使 squash 的**斜拉擠壓強度隨檔位嚴格遞增**(shear 峰
與 scale 非均勻同增),同時**體積守恆 + 阻尼簽章在每個檔位保持**(強度變、結構/守恆不變)。

真值界定同 (J/G-4''/G-4'''/G-4''''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章
(阻尼振盪 + 體積守恆耦合)+ 檔位單調遞增**,非美感;負對照證鑑別力(閘可信)。從**先驗庫** →
**真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  ST1 present + backward-compat  : squash base beat 帶 dual(shear+scale);每檔位 `squash__{tier}` 皆產出、
                                   finite、有 bone、≥1 bone 同時帶 shear+scale、名經 `beat_category` 仍路由回
                                   squash;**base 逐位元不變**(帶/不帶 tier_gains 的 base + In/Loop/Out 相同)。
  ST2 crux — dual-peak monotone  : 各檔位 squash 的 **scale 非均勻峰 |scaleX−scaleY|** 與 **shear 峰 |shearX|**
                                   皆 Super<Mega<Omg<Legend **嚴格遞增**(端到端經 build_animations 量),
                                   且首檔(Super,g=1)兩峰 == base(向後相容)。
  ST3 crux — volume kept per tier: **每個檔位**的 squash bone:(a)**每個** scale 極值幀 scaleX·scaleY≈1
                                   (|積−1|≤TOL_VOL,體積守恆 —— 這正是天真 `_amp_scale` 會破壞、耦合放大修好的);
                                   (b)squash 幅度 |scaleX−1| 隨極值嚴格遞減(阻尼耦合);(c)shear 阻尼振盪
                                   (首尾 0、繞 0 變號≥3、相繼極值遞減)—— 復用 G-4' 判準。
  ST4 identity interface per tier: **每個檔位**——shear 首尾 0 + scale 首尾 (1,1)，且 sample(0)/sample(dur)
                                   各 bone identity → 皆可插 Loop 間(檔位無關的介面契約)。
  ST5 neg-control                : (a)**平增益守衛**:增益全 1.0 → ST2 遞增 FALSE 且各檔位逐位元 == base;
                                   (b)**crux — 耦合必要性守衛**:對同一 base squash bone 套**天真非耦合**
                                   `amplify_bone_tl(coupled=False)` @Legend → 體積守恆 FALSE(積偏離 > TOL_VOL);
                                   對照 `coupled=True` 積≈1(≤TOL_VOL)→ 證「耦合放大是**必要**、非裝飾」;
                                   (c)**耦合隔離**:全 storyboard(含所有檔位變體)中,只有 squash 及其 `__tier`
                                   變體同時帶 shear 且非均勻 scale;非-squash 主秀變體皆非此耦合(零外洩)。

用法:
  python3 validate_squash_tier.py            # 摘要
  python3 validate_squash_tier.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
# 復用 G-4' 阻尼簽章判準 + G-4'''' 的 squash 度量(volume/aniso/damped),確保與既有閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import (_squash_beats, _scale_xy, _interior_scale, _sq3_eval,
                                 _has_aniso_scale, _is_ident, MIN_SHEAR, MIN_ANISO, TOL_VOL)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/squash_tier_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _aniso_peak(anim):
    """該 anim 全 bone 的峰 |scaleX−scaleY|(無 scale 回 0)。"""
    peaks = [max((abs(sx - sy) for (sx, sy) in _scale_xy(ch)), default=0.0)
             for ch in anim.get("bones", {}).values()]
    return max(peaks, default=0.0)


def _shear_peak(anim):
    """該 anim 全 bone 的峰 |shearX|(無 shear 回 0)。"""
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _is_strict_inc(xs):
    return all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                       # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)    # 帶檔位
    squash_beats = _squash_beats(base)
    R = {}

    # ---- ST1 present + backward-compat ----
    t1 = {"squash_beats": squash_beats, "base_no_dual": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": []}
    for qb in squash_beats:
        if not any(_shear_x(ch) and _scale_xy(ch) for ch in base[qb].get("bones", {}).values()):
            t1["base_no_dual"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            if not an.get("bones"):
                t1["no_bones"].append(vk)
            if not any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values()):
                t1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                t1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:      # base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    t1_pass = (bool(squash_beats) and not any(t1[k] for k in
               ["base_no_dual", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed"]))
    R["ST1_present_backward_compat"] = {**t1, "pass": t1_pass}

    # ---- ST2 crux: aniso + shear peak monotone across tiers ----
    t2 = {"beats": {}, "fail_aniso_mono": [], "fail_shear_mono": [], "fail_base": []}
    for qb in squash_beats:
        an_pk = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        sh_pk = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_an = _aniso_peak(base[qb]); base_sh = _shear_peak(base[qb])
        a_mono = _is_strict_inc(an_pk); s_mono = _is_strict_inc(sh_pk)
        base_ok = abs(an_pk[0] - base_an) <= 1e-4 and abs(sh_pk[0] - base_sh) <= 1e-4
        t2["beats"][qb] = {"aniso_peaks": [round(p, 4) for p in an_pk],
                           "shear_peaks": [round(p, 3) for p in sh_pk],
                           "base_aniso": round(base_an, 4), "base_shear": round(base_sh, 3),
                           "aniso_mono": a_mono, "shear_mono": s_mono, "super_eq_base": base_ok}
        if not a_mono:
            t2["fail_aniso_mono"].append(qb)
        if not s_mono:
            t2["fail_shear_mono"].append(qb)
        if not base_ok:
            t2["fail_base"].append(qb)
    t2_pass = (bool(t2["beats"]) and not t2["fail_aniso_mono"]
               and not t2["fail_shear_mono"] and not t2["fail_base"])
    R["ST2_dual_peak_monotone"] = {**t2, "pass": t2_pass}

    # ---- ST3 crux: volume conservation + damped signatures preserved per tier ----
    t3 = {"bad_volume": [], "squash_not_damped": [], "shear_bad_endpoints": [],
          "shear_few_sign_changes": [], "shear_not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                sx = _shear_x(ch)
                if not interior or not sx:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                vok, aok, dok, det = _sq3_eval(interior)   # (a)volume (c)squash 幅度遞減
                ends_ok = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                nsc = _sign_changes_zero(sx)
                sh_damp = _extrema_mags_decreasing(sx)
                t3["detail"][key] = {"volume": det["prod"], "squash_damped": dok,
                                     "shear_n_sign_changes": nsc, "shear_damped": sh_damp}
                if not vok:
                    t3["bad_volume"].append(key)
                if not dok:
                    t3["squash_not_damped"].append(key)
                if not ends_ok:
                    t3["shear_bad_endpoints"].append(key)
                if nsc < 3:
                    t3["shear_few_sign_changes"].append(key)
                if not sh_damp:
                    t3["shear_not_damped"].append(key)
    t3_pass = (bool(t3["detail"]) and not t3["bad_volume"] and not t3["squash_not_damped"]
               and not t3["shear_bad_endpoints"] and not t3["shear_few_sign_changes"]
               and not t3["shear_not_damped"])
    R["ST3_volume_and_damped_per_tier"] = {**t3, "pass": t3_pass}

    # ---- ST4 identity interface per tier ----
    t4 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]; end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                t4["bad_interface"].append("{}__{}".format(qb, t))
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                    t4["shear_endpoints_nonzero"].append("{}__{}::{}".format(qb, t, bn))
                xy = _scale_xy(ch)
                if xy and (abs(xy[0][0] - 1.0) > 1e-6 or abs(xy[0][1] - 1.0) > 1e-6
                           or abs(xy[-1][0] - 1.0) > 1e-6 or abs(xy[-1][1] - 1.0) > 1e-6):
                    t4["scale_endpoints_nonident"].append("{}__{}::{}".format(qb, t, bn))
    R["ST4_identity_interface"] = {**t4, "pass": (not t4["bad_interface"]
                                                  and not t4["shear_endpoints_nonzero"]
                                                  and not t4["scale_endpoints_nonident"])}

    # ---- ST5 negative controls ----
    t5 = {}
    # (a) 平增益守衛:全 1.0 → 遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for qb in squash_beats:
        an_pk = [_aniso_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(an_pk):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    t5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) crux — 耦合必要性:同一 base squash bone,天真非耦合 amplify @Legend → 破壞體積守恆;耦合 → 保持
    gL = gains["Legend"]
    coupling_bad, coupling_ok = [], []
    for qb in squash_beats:
        for bn, ch in base[qb].get("bones", {}).items():
            if not (_interior_scale(ch) and _shear_x(ch)):
                continue
            uncoupled = TV.amplify_bone_tl(ch, gL, coupled=False)
            coupled = TV.amplify_bone_tl(ch, gL, coupled=True)
            vu = _sq3_eval(_interior_scale(uncoupled))[0]   # volume_ok(非耦合應 FALSE)
            vc = _sq3_eval(_interior_scale(coupled))[0]      # volume_ok(耦合應 TRUE)
            key = "{}::{}".format(qb, bn)
            if not vu:
                coupling_bad.append(key)    # 非耦合正確地破壞體積守恆(vu==False)
            if vc:
                coupling_ok.append(key)     # 耦合正確地保持體積守恆(vc==True)
    # 守衛通過 = 至少一個 bone 上「非耦合破壞、耦合保持」皆成立(證耦合是必要修正)
    t5["b_coupling_necessity"] = {
        "uncoupled_breaks_volume": coupling_bad, "coupled_keeps_volume": coupling_ok,
        "pass": bool(coupling_bad) and bool(coupling_ok)
                and set(coupling_bad) == set(coupling_ok)}
    # (c) 耦合隔離:只有 squash(含 __tier 變體)同時帶 shear + 非均勻 scale
    leak = []
    for nm, an in anims.items():
        if G.beat_category(nm.split("__")[0]) == "squash":
            continue
        for bn, ch in an.get("bones", {}).items():
            if _shear_x(ch) and _has_aniso_scale(ch):
                leak.append((nm, bn))
    t5["c_coupling_isolated"] = {"leaked": leak, "pass": not leak}
    R["ST5_neg_control"] = {**t5, "pass": all(v["pass"] for v in t5.values())}

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
        for k in ["ST1_present_backward_compat", "ST2_dual_peak_monotone",
                  "ST3_volume_and_damped_per_tier", "ST4_identity_interface", "ST5_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("ST2 dual peaks per tier {}:".format(TIERS))
        for qb, d in R["ST2_dual_peak_monotone"]["beats"].items():
            print("  {:10s} aniso {}  shear {}  (base aniso {} shear {})".format(
                qb, d["aniso_peaks"], d["shear_peaks"], d["base_aniso"], d["base_shear"]))
        b = R["ST5_neg_control"]["b_coupling_necessity"]
        print("ST5(b) uncoupled-breaks-volume:", b["uncoupled_breaks_volume"],
              " coupled-keeps-volume:", b["coupled_keeps_volume"])
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
