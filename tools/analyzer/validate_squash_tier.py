#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

candidate (J) 讓主秀 beat 依檔位**幅度**差異化、(G-4'') 讓 wobble 的 shear 峰隨檔位遞增;但 squash
(G-4'''',斜拉果凍**擠壓**)一直**不在** `MAIN_SHOW_CATS` —— 因為它的 scale 是**體積守恆的非均勻對**
(scaleX·scaleY≡1、scaleX≠scaleY),而逐軸 `_amp_scale` 只放大 identity 上方(scaleX>1 被放大、scaleY<1
樓地板不動)→ **破壞體積守恆**(scaleX·scaleY≠1)。這是 G-4/G-4' 一路留到 G-4'''' 的 honest boundary。
本次(G-4''''')補上**耦合 amplify**:對「體積守恆非均勻 scale 幀」放大拉長軸(套與逐軸相同的
`1+g(v−1)`)、壓縮軸取其**倒數** → 放大後仍 scaleX·scaleY≡1(體積守恆保形),使 squash 的斜拉+擠壓
強度隨檔位嚴格遞增,同時**體積守恆與非均勻/阻尼簽章在每個檔位保持**(強度變、結構不變)。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位斜拉+擠壓愈大**且仍體積守恆**」是可量化的檔位簽章,用負對照證鑑別力(閘可信)。從**先驗庫**
→ **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  V1 present + backward-compat : squash base beat 同時帶 shear + 非均勻 scale;每檔位 `squash__{tier}`
                                皆產出、finite、有 bone、≥1 bone **同時**帶 shear 與非均勻 scale、名經
                                `beat_category` 仍路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains 的
                                base squash + 其他 base beat 相同)。
  V2 crux — dual-channel monotone: 各檔位 squash 的峰 |shearX| **與** squash 拉長峰 max|scaleX−1|
                                皆 Super<Mega<Omg<Legend **嚴格遞增**(端到端經 build_animations 量),
                                且首檔(Super,g=1)兩峰皆 == base 峰(向後相容)。
  V3 crux — volume conserved per tier: **每個檔位**的 squash bone 內部極值仍 (a)scaleX·scaleY≈1
                                (|積−1|≤TOL_VOL,**體積守恆保形 = 本次修的 honest boundary**);
                                (b)非均勻 max|scaleX−scaleY|≥MIN_ANISO(真擠壓,非等比 pulse);
                                (c)拉長幅度 |scaleX−1| 隨極值嚴格遞減(阻尼耦合);shearX 亦 (d)首尾 0
                                (e)繞 0 變號 ≥3 (f)相繼極值遞減(阻尼)。
  V4 coupling isolated         : 全 storyboard(含所有檔位變體)中,**只有 squash 及其 `__tier` 變體**同時
                                帶 shear 與非均勻 scale;非-squash 主秀 beat 及其變體皆非「shear+非均勻 scale」
                                (wobble 有 shear 無非均勻 scale、其餘有等比 scale 無 shear)→ 耦合為 squash 獨佔。
  V5 neg-control               : (a) **平增益守衛**:增益階梯全 1.0 → V2 兩峰遞增 FALSE(證閘測遞增非恆真)
                                且各檔位 squash 逐位元 == base squash;
                                (b) **耦合 amplify 單元測 vs 逐軸破壞守恆**:對合成體積守恆非均勻對
                                `amplify_bone_tl` → (i)放大後仍 scaleX·scaleY≈1 且拉長軸放大(耦合成立);
                                (ii)**逐軸破壞守恆守衛**:同一對用逐軸 `_amp_scale`(舊法)放大 → 積 ≠ 1
                                (證本次修的耦合確有必要、閘測的是守恆保形非恆真);
                                (iii)**等比守衛**:等比 pulse(scaleX==scaleY)不走耦合路 → 兩軸皆逐軸放大
                                (積改變、非被強制為 1 → 證耦合路確以「非均勻」gating)。

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
# 復用 G-4' 阻尼簽章判準 + G-4'''' 體積守恆/非均勻/阻尼判準(確保與 shear-gen / squash-gen 閘一致)
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import (_squash_beats, _scale_xy, _interior_scale, _sq3_eval,
                                 MIN_ANISO, TOL_VOL)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
MIN_SHEAR = 5.0     # 度,base squash 峰 |shearX| 下限


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/squash_tier_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _stretch_peak(anim):
    """該 anim 全 bone 的 squash 拉長峰 max|scaleX−1|(取非均勻 scale 幀;無回 0)。"""
    peaks = []
    for ch in anim.get("bones", {}).values():
        mags = [abs(sx - 1.0) for (sx, sy) in _scale_xy(ch) if abs(sx - sy) > MIN_ANISO]
        if mags:
            peaks.append(max(mags))
    return max(peaks, default=0.0)


def _has_coupled(chans):
    """該 bone 是否同時帶 shear 與非均勻 scale(squash 耦合簽章)。"""
    has_shear = bool(_shear_x(chans))
    has_aniso = any(abs(sx - sy) > MIN_ANISO for (sx, sy) in _scale_xy(chans))
    return has_shear and has_aniso


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

    # ---- V1 present + backward-compat ----
    v1 = {"squash_beats": squash_beats, "base_no_coupling": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_coupling": [], "misrouted": [], "base_changed": []}
    for qb in squash_beats:
        if not any(_has_coupled(ch) for ch in base[qb].get("bones", {}).values()) \
           or _shear_peak(base[qb]) < MIN_SHEAR:
            v1["base_no_coupling"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                v1["missing"].append(vk); continue
            if not SA.all_finite(an):
                v1["not_finite"].append(vk)
            if not an.get("bones"):
                v1["no_bones"].append(vk)
            if not any(_has_coupled(ch) for ch in an.get("bones", {}).values()):
                v1["variant_no_coupling"].append(vk)
            if G.beat_category(vk) != "squash":
                v1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            v1["base_changed"].append(k)
    v1_pass = (bool(squash_beats) and not any(v1[k] for k in
               ["base_no_coupling", "missing", "not_finite", "no_bones", "variant_no_coupling",
                "misrouted", "base_changed"]))
    R["V1_present_backward_compat"] = {**v1, "pass": v1_pass}

    # ---- V2 crux: dual-channel (shear peak + stretch peak) monotone across tiers ----
    v2 = {"beats": {}, "fail_mono_shear": [], "fail_mono_stretch": [], "fail_base": []}
    for qb in squash_beats:
        sh_peaks = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        st_peaks = [_stretch_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_sh = _shear_peak(base[qb])
        base_st = _stretch_peak(base[qb])
        mono_sh = _is_strict_inc(sh_peaks)
        mono_st = _is_strict_inc(st_peaks)
        super_eq = abs(sh_peaks[0] - base_sh) <= 1e-4 and abs(st_peaks[0] - base_st) <= 1e-4
        v2["beats"][qb] = {"shear_peaks": [round(p, 3) for p in sh_peaks],
                           "stretch_peaks": [round(p, 4) for p in st_peaks],
                           "base_shear": round(base_sh, 3), "base_stretch": round(base_st, 4),
                           "mono_shear": mono_sh, "mono_stretch": mono_st, "super_eq_base": super_eq}
        if not mono_sh:
            v2["fail_mono_shear"].append(qb)
        if not mono_st:
            v2["fail_mono_stretch"].append(qb)
        if not super_eq:
            v2["fail_base"].append(qb)
    v2_pass = (bool(v2["beats"]) and not v2["fail_mono_shear"]
               and not v2["fail_mono_stretch"] and not v2["fail_base"])
    R["V2_dual_channel_monotone"] = {**v2, "pass": v2_pass}

    # ---- V3 crux: volume conservation + aniso + damped signature preserved per tier ----
    v3 = {"not_volume_conserved": [], "not_aniso": [], "not_damped_scale": [],
          "bad_shear_ends": [], "few_sign_changes": [], "not_damped_shear": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                if not _has_coupled(ch):
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                interior = _interior_scale(ch)
                vol_ok, aniso_ok, damp_sc_ok, det = _sq3_eval(interior)
                sx = _shear_x(ch)
                ends_ok = bool(sx) and abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                nsc = _sign_changes_zero(sx)
                damp_sh = _extrema_mags_decreasing(sx)
                v3["detail"][key] = {"vol_prod": det["prod"], "aniso": det["aniso"],
                                     "scale_mag": det["mag"], "n_sign_changes": nsc,
                                     "shear_damped": damp_sh}
                if not vol_ok:
                    v3["not_volume_conserved"].append(key)
                if not aniso_ok:
                    v3["not_aniso"].append(key)
                if not damp_sc_ok:
                    v3["not_damped_scale"].append(key)
                if not ends_ok:
                    v3["bad_shear_ends"].append(key)
                if nsc < 3:
                    v3["few_sign_changes"].append(key)
                if not damp_sh:
                    v3["not_damped_shear"].append(key)
    v3_pass = (bool(v3["detail"]) and not any(v3[k] for k in
               ["not_volume_conserved", "not_aniso", "not_damped_scale",
                "bad_shear_ends", "few_sign_changes", "not_damped_shear"]))
    R["V3_volume_conserved_per_tier"] = {**v3, "pass": v3_pass}

    # ---- V4 coupling (shear+aniso scale) isolated to squash (incl. all tier variants) ----
    v4 = {"leaked": []}
    for nm, an in anims.items():
        base_name = nm.split("__")[0]
        if G.beat_category(base_name) == "squash":
            continue
        coupled = [bn for bn, ch in an.get("bones", {}).items() if _has_coupled(ch)]
        if coupled:
            v4["leaked"].append((nm, coupled))
    R["V4_coupling_isolated"] = {**v4, "pass": not v4["leaked"]}

    # ---- V5 negative controls ----
    v5 = {}
    # (a) 平增益守衛:全 1.0 → 兩峰遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for qb in squash_beats:
        sh = [_shear_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        st = [_stretch_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(sh) or _is_strict_inc(st):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    v5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) 耦合 amplify 單元測 vs 逐軸破壞守恆 / 等比 gating
    g = 2.0
    Q = 0.14
    sx0, sy0 = round(1.0 + Q, 4), round(1.0 / (1.0 + Q), 4)     # 體積守恆非均勻對
    coupled_bone = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0},
                              {"time": 0.5, "x": sx0, "y": sy0},
                              {"time": 1.0, "x": 1.0, "y": 1.0}]}
    a_co = TV.amplify_bone_tl(coupled_bone, g)
    cx, cy = a_co["scale"][1]["x"], a_co["scale"][1]["y"]
    coupled_vol_ok = abs(cx * cy - 1.0) <= TOL_VOL                    # (i) 放大後仍守恆
    coupled_stretch = abs(cx - (1.0 + g * Q)) <= 1e-3                 #     拉長軸 = 1+g(v−1)
    # (ii) 逐軸破壞守恆守衛(舊法):scaleX 放大、scaleY(<1)樓地板不動 → 積 ≠ 1
    naive_x = TV._amp_scale(sx0, g)
    naive_y = TV._amp_scale(sy0, g)                                   # sy0<1 → 不變
    naive_breaks = abs(naive_x * naive_y - 1.0) > 0.05
    # (iii) 等比 gating 守衛:等比 pulse 不走耦合 → 兩軸皆逐軸放大(積改變、非被強制為 1)
    pulse_bone = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0},
                            {"time": 0.5, "x": 1.3, "y": 1.3},
                            {"time": 1.0, "x": 1.0, "y": 1.0}]}
    a_pu = TV.amplify_bone_tl(pulse_bone, g)
    px, py = a_pu["scale"][1]["x"], a_pu["scale"][1]["y"]
    pulse_peraxis = (abs(px - (1.0 + g * 0.3)) <= 1e-6 and abs(py - (1.0 + g * 0.3)) <= 1e-6
                     and abs(px * py - 1.0) > 0.05)
    v5["b_coupled_vs_peraxis"] = {
        "coupled_vol_ok": coupled_vol_ok, "coupled_stretch_amplified": coupled_stretch,
        "coupled_pair": [cx, cy, round(cx * cy, 6)],
        "naive_peraxis_breaks_volume": naive_breaks,
        "naive_pair": [round(naive_x, 4), round(naive_y, 4), round(naive_x * naive_y, 6)],
        "pulse_uses_peraxis": pulse_peraxis,
        "pass": coupled_vol_ok and coupled_stretch and naive_breaks and pulse_peraxis}
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
        for k in ["V1_present_backward_compat", "V2_dual_channel_monotone",
                  "V3_volume_conserved_per_tier", "V4_coupling_isolated", "V5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V2 peaks per tier {}:".format(TIERS))
        for qb, d in R["V2_dual_channel_monotone"]["beats"].items():
            print("  {:10s} shear={}  stretch={}".format(qb, d["shear_peaks"], d["stretch_peaks"]))
        print("V5(b) coupled pair {} vs naive per-axis {} (naive breaks volume: {})".format(
            R["V5_neg_control"]["b_coupled_vs_peraxis"]["coupled_pair"],
            R["V5_neg_control"]["b_coupled_vs_peraxis"]["naive_pair"],
            R["V5_neg_control"]["b_coupled_vs_peraxis"]["naive_peraxis_breaks_volume"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
