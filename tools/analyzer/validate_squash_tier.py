#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位差異化(純 CPU)。

(G-4'''')的 honest boundary:squash 生成器產出**體積守恆非均勻 scale**(scaleX=1+q、scaleY=1/(1+q),
scaleX·scaleY≡1),但**未接檔位差異化** —— 因一般幅度增益 `_amp_scale` 只放大 identity 上方 overshoot:
對 squash 只會放大拉長軸(scaleX>1)、壓扁軸(scaleY<1)保留 → 積 (1+g·q)/(1+q)≠1 **破壞體積守恆**,
故當時 squash **不在** `MAIN_SHOW_CATS`。本次(G-4''''')補上:把 squash 併入 `MAIN_SHOW_CATS`,其 scale
改走 `COUPLED_SCALE_CATS` 的**耦合 amplify**(`_amp_squash_scale`:放大拉長軸、壓扁軸取倒數)
→ **非均勻隨檔位嚴格遞增而體積恆守恆**;shear 峰同 wobble 以 g·v 隨檔位放大。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感,留使用者 A 類),閘驗**客觀結構
簽章非美感**。「愈高檔位擠壓愈強(非均勻更大、shear 更斜)且體積恆守恆、阻尼簽章保形」皆可量化,
用負對照(平增益、plain 非耦合 amplify、耦合隔離)證鑑別力(閘可信)。從**先驗庫** → **真實
build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  V1 present + backward-compat : squash base beat 有 shear+非均勻 scale;每檔位 `squash__{tier}` 皆產出、
                                finite、有 bone、≥1 bone 帶 shear 且帶非均勻 scale、名經 `beat_category`
                                仍路由回 squash;**base(含 In/Loop/Out + base squash)逐位元不變**;
                                首檔(Super,g=1)shear 峰與非均勻峰皆 == base(向後相容,tol)。
  V2 crux — coupled volume-preserving amplify:
                                (a)**每檔位每極值幀** |scaleX·scaleY − 1| ≤ TOL_VOL(體積恆守恆);
                                (b)非均勻峰 max|scaleX−scaleY| Super<Mega<Omg<Legend **嚴格遞增**
                                (端到端經 build_animations 量;檔位=更強擠壓)。
  V3 shear peak monotone       : 各檔位 squash 的峰 |shearX| Super<Mega<Omg<Legend **嚴格遞增**,
                                且 Super == base(向後相容)。scale 與 shear 兩幅度軸同步隨檔位放大。
  V4 signatures preserved      : **每個檔位**的 squash bone 仍 (a)shear 首尾 0 + 繞 0 變號 ≥3 + 相繼極值
                                嚴格遞減(阻尼);(b)squash 幅度 |scaleX−1| 隨極值嚴格遞減(阻尼耦合)。
                                → 耦合 amplify(拉長軸 g·overshoot、壓扁軸倒數)是簽章保形變換。
  V5 neg-control               : (a)**耦合必要性**:對 base squash scale 施 plain(非耦合)amplify(g=Legend)
                                → 體積守恆 FALSE(|積−1| ≫ TOL_VOL)→ 證 (G-4'''') 未接的正是這條、耦合非多餘;
                                (b)**平增益守衛**:增益階梯全 1.0 → V2 非均勻/V3 shear 遞增 FALSE 且各檔位
                                squash 逐位元 == base(耦合在 g=1 退化為 identity 變換);
                                (c)**耦合隔離**:耦合 amplify 只作用 squash(cat∈COUPLED_SCALE_CATS)——
                                對等比 pulse bone(scaleX==scaleY)施耦合會破壞等比(sy=1/sx≠sx),
                                證產線只對 squash 路由耦合、對 hit/combo 等仍走 plain(等比幅度)。

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
# 復用 G-4' 阻尼簽章判準 + G-4'''' squash 判準,確保與既有閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import (_squash_beats, _scale_xy, _interior_scale, _sq3_eval,
                                 TOL_VOL, MIN_ANISO, MIN_SHEAR)

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


def _shear_peak(anim):
    """該 anim 全 bone 的峰 |shearX|(無 shear 回 0)。"""
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _aniso_peak(anim):
    """該 anim 全 bone 的峰非均勻 max|scaleX−scaleY|(無 scale 回 0)。"""
    peaks = []
    for ch in anim.get("bones", {}).values():
        xy = _scale_xy(ch)
        if xy:
            peaks.append(max(abs(sx - sy) for (sx, sy) in xy))
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

    # ---- V1 present + backward-compat ----
    v1 = {"squash_beats": squash_beats, "base_no_shear": [], "base_no_aniso": [], "missing": [],
          "not_finite": [], "no_bones": [], "variant_no_shear": [], "variant_no_aniso": [],
          "misrouted": [], "base_changed": [], "super_ne_base": []}
    for wb in squash_beats:
        if _shear_peak(base[wb]) < MIN_SHEAR:
            v1["base_no_shear"].append(wb)
        if _aniso_peak(base[wb]) < MIN_ANISO:
            v1["base_no_aniso"].append(wb)
        for t in TIERS:
            vk = "{}__{}".format(wb, t)
            an = anims.get(vk)
            if an is None:
                v1["missing"].append(vk); continue
            if not SA.all_finite(an):
                v1["not_finite"].append(vk)
            if not an.get("bones"):
                v1["no_bones"].append(vk)
            if not any(_shear_x(ch) for ch in an.get("bones", {}).values()):
                v1["variant_no_shear"].append(vk)
            if _aniso_peak(an) < MIN_ANISO:
                v1["variant_no_aniso"].append(vk)
            if G.beat_category(vk) != "squash":
                v1["misrouted"].append((vk, G.beat_category(vk)))
        # Super(g=1)shear/aniso 峰 == base(向後相容;耦合在 g=1 退化 identity)
        sup = "{}__Super".format(wb)
        if sup in anims:
            if abs(_shear_peak(anims[sup]) - _shear_peak(base[wb])) > 1e-4 or \
               abs(_aniso_peak(anims[sup]) - _aniso_peak(base[wb])) > 1e-4:
                v1["super_ne_base"].append(wb)
    # base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            v1["base_changed"].append(k)
    v1_pass = (bool(squash_beats) and not any(v1[k] for k in
               ["base_no_shear", "base_no_aniso", "missing", "not_finite", "no_bones",
                "variant_no_shear", "variant_no_aniso", "misrouted", "base_changed", "super_ne_base"]))
    R["V1_present_backward_compat"] = {**v1, "pass": v1_pass}

    # ---- V2 crux: coupled volume-preserving amplify (conservation all tiers + aniso monotone) ----
    v2 = {"beats": {}, "vol_broken": [], "fail_aniso_mono": []}
    for wb in squash_beats:
        aniso_peaks = []
        for t in TIERS:
            an = anims["{}__{}".format(wb, t)]
            # 每 bone 每極值幀體積守恆
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior:
                    continue
                for (sx, sy) in interior:
                    if abs(sx * sy - 1.0) > TOL_VOL:
                        v2["vol_broken"].append(("{}__{}::{}".format(wb, t, bn), round(sx * sy, 5)))
            aniso_peaks.append(round(_aniso_peak(an), 4))
        mono = _is_strict_inc(aniso_peaks)
        v2["beats"][wb] = {"aniso_peaks": aniso_peaks, "mono": mono}
        if not mono:
            v2["fail_aniso_mono"].append(wb)
    v2_pass = bool(v2["beats"]) and not v2["vol_broken"] and not v2["fail_aniso_mono"]
    R["V2_coupled_volume_preserving"] = {**v2, "pass": v2_pass}

    # ---- V3 shear peak monotone across tiers ----
    v3 = {"beats": {}, "fail_mono": [], "fail_base": []}
    for wb in squash_beats:
        peaks = [_shear_peak(anims["{}__{}".format(wb, t)]) for t in TIERS]
        base_peak = _shear_peak(base[wb])
        mono = _is_strict_inc(peaks)
        super_eq_base = abs(peaks[0] - base_peak) <= 1e-4
        v3["beats"][wb] = {"shear_peaks": [round(p, 3) for p in peaks],
                           "base_peak": round(base_peak, 3),
                           "mono": mono, "super_eq_base": super_eq_base}
        if not mono:
            v3["fail_mono"].append(wb)
        if not super_eq_base:
            v3["fail_base"].append(wb)
    v3_pass = bool(v3["beats"]) and not v3["fail_mono"] and not v3["fail_base"]
    R["V3_shear_peak_monotone"] = {**v3, "pass": v3_pass}

    # ---- V4 signatures preserved per tier (shear damped + squash damping ladder) ----
    v4 = {"shear_bad": [], "squash_bad": [], "detail": {}}
    for wb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(wb, t)]
            for bn, ch in an.get("bones", {}).items():
                key = "{}__{}::{}".format(wb, t, bn)
                sx = _shear_x(ch)
                if sx:
                    ends_ok = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                    nsc = _sign_changes_zero(sx)
                    damp = _extrema_mags_decreasing(sx)
                    if not (ends_ok and nsc >= 3 and damp):
                        v4["shear_bad"].append(key)
                interior = _interior_scale(ch)
                if interior:
                    _, _, damped_ok, det = _sq3_eval(interior)
                    v4["detail"][key] = det
                    if not damped_ok:
                        v4["squash_bad"].append(key)
    v4_pass = bool(v4["detail"]) and not v4["shear_bad"] and not v4["squash_bad"]
    R["V4_signatures_preserved"] = {**v4, "pass": v4_pass}

    # ---- V5 negative controls ----
    v5 = {}
    wb0 = squash_beats[0]
    # (a) 耦合必要性:對 base squash scale 施 plain(非耦合)amplify → 體積守恆 FALSE
    g_leg = gains["Legend"]
    plain_broken, coupled_ok = [], []
    for bn, ch in base[wb0]["bones"].items():
        if not _interior_scale(ch):
            continue
        plain = TV.amplify_bone_tl(ch, g_leg, coupled_scale=False)
        coupled = TV.amplify_bone_tl(ch, g_leg, coupled_scale=True)
        pmax = max(abs(sx * sy - 1.0) for (sx, sy) in _interior_scale(plain))
        cmax = max(abs(sx * sy - 1.0) for (sx, sy) in _interior_scale(coupled))
        plain_broken.append(pmax > TOL_VOL)      # plain 應破壞守恆
        coupled_ok.append(cmax <= TOL_VOL)       # coupled 應守恆
    v5["a_coupling_necessary"] = {
        "plain_max_vol_err": round(max(
            max(abs(sx * sy - 1.0) for (sx, sy) in _interior_scale(
                TV.amplify_bone_tl(ch, g_leg, coupled_scale=False)))
            for bn, ch in base[wb0]["bones"].items() if _interior_scale(ch)), 4),
        "all_plain_broke_conservation": all(plain_broken),
        "all_coupled_conserved": all(coupled_ok),
        "pass": bool(plain_broken) and all(plain_broken) and all(coupled_ok)}
    # (b) 平增益守衛:全 1.0 → aniso/shear 遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_aniso_mono, any_shear_mono, flat_base_diff = False, False, []
    for wb in squash_beats:
        ap = [_aniso_peak(flat_anims["{}__{}".format(wb, t)]) for t in TIERS]
        sp = [_shear_peak(flat_anims["{}__{}".format(wb, t)]) for t in TIERS]
        if _is_strict_inc(ap):
            any_aniso_mono = True
        if _is_strict_inc(sp):
            any_shear_mono = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(wb, t)], sort_keys=True) != \
               json.dumps(base[wb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(wb, t))
    v5["b_flat_guard"] = {"flat_aniso_monotone": any_aniso_mono, "flat_shear_monotone": any_shear_mono,
                          "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_aniso_mono) and (not any_shear_mono) and not flat_base_diff}
    # (c) 耦合隔離:耦合 amplify 對等比 pulse bone 破壞等比(証耦合只該路由給 squash)
    g = 2.0
    pulse = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0}, {"time": 0.5, "x": 1.3, "y": 1.3},
                       {"time": 1.0, "x": 1.0, "y": 1.0}]}
    plain_pulse = TV.amplify_bone_tl(pulse, g, coupled_scale=False)   # 產線對 hit/combo 走這條
    coupled_pulse = TV.amplify_bone_tl(pulse, g, coupled_scale=True)  # 若誤把耦合套到 pulse
    pp = plain_pulse["scale"][1]
    cp = coupled_pulse["scale"][1]
    plain_keeps_uniform = abs(pp["x"] - pp["y"]) <= 1e-6              # plain 保持等比
    coupled_breaks_uniform = abs(cp["x"] - cp["y"]) > 1e-3           # coupled 破壞等比(sy=1/sx)
    # 產線確認:所有非-squash 主秀變體的 scale 仍等比(未被耦合污染)
    leaked = []
    for nm, an in anims.items():
        if "__" not in nm or G.beat_category(nm) in TV.COUPLED_SCALE_CATS:
            continue
        for bn, ch in an.get("bones", {}).items():
            for (sx, sy) in _scale_xy(ch):
                if abs(sx - sy) > MIN_ANISO:      # 非-squash 主秀不該出現非均勻 scale
                    leaked.append((nm, bn, round(sx - sy, 4)))
    v5["c_coupling_isolated"] = {"plain_pulse_uniform": plain_keeps_uniform,
                                 "coupled_pulse_breaks_uniform": coupled_breaks_uniform,
                                 "nonsquash_aniso_leaked": leaked,
                                 "pass": plain_keeps_uniform and coupled_breaks_uniform and not leaked}
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
        for k in ["V1_present_backward_compat", "V2_coupled_volume_preserving",
                  "V3_shear_peak_monotone", "V4_signatures_preserved", "V5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V2 non-uniformity peaks per tier {}:".format(TIERS))
        for wb, d in R["V2_coupled_volume_preserving"]["beats"].items():
            print("  {:10s} {}".format(wb, d["aniso_peaks"]))
        print("V3 shear peaks per tier {}:".format(TIERS))
        for wb, d in R["V3_shear_peak_monotone"]["beats"].items():
            print("  {:10s} {}  (base {})".format(wb, d["shear_peaks"], d["base_peak"]))
        print("V5a plain-amplify max vol err (should ≫ {}): {}".format(
            TOL_VOL, R["V5_neg_control"]["a_coupling_necessary"]["plain_max_vol_err"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
