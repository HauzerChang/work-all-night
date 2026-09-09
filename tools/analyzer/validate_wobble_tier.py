#!/usr/bin/env python3
"""candidate G-4'' 自我驗收閘 — wobble(斜拉 shear)接 tier 幅度差異化(純 CPU)。

G-4'(`validate_shear_gen.py`)讓 `gen_wobble` **第一次**產出 shear 通道並端到端補償,但留下
honest boundary:**wobble 尚未接 tier 幅度差異化**(shear 峰不隨檔位遞增;wobble ∉ MAIN_SHOW_CATS)。
本次(G-4'')比照 (J) 對 scale/rotate 所做,把 wobble 納入 `MAIN_SHOW_CATS`,並讓
`tier_variants.amplify_bone_tl` 對 **shear 通道**對 0 對稱放大 `v'=g*v`(同 rotate/translate),
使 `{wobble}__{tier}` 的 shear 峰 **Super<Mega<Omg<Legend 嚴格遞增**,而阻尼振盪簽章與 identity
介面對所有檔位保形(端點 0 仍 0、相繼極值同乘 g → **阻尼比 r 不變**、峰值隨 g 遞增)。

真值/fixture 與 (E/H/I/J/G-4') 一致:從**先驗庫**(slot_bigwin,含 wobble beat)經 `analyze_target`
→ **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。主秀運動無唯一
正解(PROPOSAL 手感),閘驗**客觀結構簽章(shear 峰單調 + 阻尼振盪 + 阻尼形狀不變)**,非美感;
負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  T1 present + shear per tier : 每 wobble beat × 每檔位皆產 `{beat}__{tier}` 且 finite/有 bone/
                                ≥1 bone shear 峰 |shearX| ≥ MIN_SHEAR;base wobble 逐位元 == 無檔位(向後相容)。
  T2 crux monotone peak       : 每 wobble beat —— shear 峰 Super<Mega<Omg<Legend **嚴格遞增**,
                                且峰[tier] == base_peak × gain[tier](端到端經 amplify);Legend 峰 < 90°
                                (det=cos(shear)>0,無翻面)。
  T3 damped signature kept    : **每檔位** —— 每 wobble bone 的 shearX 首尾 0、繞 0 變號 ≥3、
                                相繼極值嚴格遞減(阻尼)→ 簽章對所有檔位保形。
  T4 identity interface       : **每檔位** —— sample(0)/sample(dur) rotate/scale/translate identity
                                且 shear 首尾 0 → 可插 Loop 間。
  T5 neg-control / isolation  : (a) **平增益守衛**:增益全 1.0 → T2 峰單調 FALSE 且 Super 峰==Legend 峰
                                   (證閘真在測遞增,非恆真);
                                (b) **隔離/加性**:base wobble 逐位元 == 無檔位;帶 tier_gains 時所有 base
                                   beat 逐位元不變;shear **只**出現在 wobble 變體(其餘 beat 變體 0 bone 帶 shear);
                                (c) **阻尼形狀不變(誠實邊界)**:相繼極值比 |e_{i+1}/e_i| 對 Super 與 Legend
                                   逐項相等(均勻放大 → 只放大幅度、不改阻尼比 r → 檔位改「多晃」非「怎麼晃」)。

用法:
  python3 validate_wobble_tier.py            # 摘要
  python3 validate_wobble_tier.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze
import tier_variants as TV
# 復用 G-4' 的 shear 度量與阻尼簽章判準,確保與生成器閘完全一致
from validate_shear_gen import (_shear_x, _sign_changes_zero, _extrema_mags_decreasing,
                                _wobble_beats, _is_ident)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,base wobble 峰值下限(同 G-4')
AMP_TOL = 0.02      # 度,峰[tier] vs base_peak×gain 的絕對容忍(round(,3) 誤差)
FLIP_LIMIT = 90.0   # 度,shear 峰上限(|shear|<90 → det=cosφ>0 無翻面)
RATIO_TOL = 1e-3    # 阻尼比逐項相等容忍


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/wobble_tier_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _shear_peak(anim):
    """anim 內所有 bone shear 峰 |shearX| 的最大值(無 shear → 0)。"""
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _extrema_ratios(vals, dead=1e-6):
    """相繼非零極值幅度比 |e_{i+1}/e_i| 序列(阻尼形狀指紋,與絕對幅度無關)。"""
    nz = [abs(v) for v in vals if abs(v) > dead]
    return [nz[i + 1] / nz[i] for i in range(len(nz) - 1)] if len(nz) >= 2 else []


def _is_incr(xs):
    return all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                       # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)     # 帶檔位
    wobble_beats = _wobble_beats(base)
    R = {}

    # ---- T1 present + shear per tier + backward-compat base ----
    t1 = {"wobble_beats": wobble_beats, "missing": [], "not_finite": [], "no_bones": [],
          "no_shear": [], "weak_peak": [], "base_changed": [], "peak_by_variant": {}}
    for wb in wobble_beats:
        for t in TIERS:
            vk = "{}__{}".format(wb, t)
            an = anims.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            if not an.get("bones"):
                t1["no_bones"].append(vk)
            pk = _shear_peak(an)
            t1["peak_by_variant"][vk] = round(pk, 3)
            if pk <= 0.0:
                t1["no_shear"].append(vk)
            elif pk < MIN_SHEAR:
                t1["weak_peak"].append(vk)
    # base wobble 逐位元 == 無檔位輸出
    for wb in wobble_beats:
        if json.dumps(base[wb], sort_keys=True) != json.dumps(anims.get(wb), sort_keys=True):
            t1["base_changed"].append(wb)
    t1_pass = (bool(wobble_beats) and not any(t1[k] for k in
               ("missing", "not_finite", "no_bones", "no_shear", "weak_peak", "base_changed")))
    R["T1_present_shear"] = {**t1, "pass": t1_pass}

    # ---- T2 crux: monotone shear peak + gain ladder + no flip ----
    t2 = {"beats": {}, "fail_mono": [], "fail_ladder": [], "fail_flip": []}
    for wb in wobble_beats:
        base_peak = _shear_peak(base[wb])
        peaks = [_shear_peak(anims["{}__{}".format(wb, t)]) for t in TIERS]
        expect = [round(base_peak * gains[t], 3) for t in TIERS]
        mono = _is_incr(peaks)
        ladder = all(abs(p - e) <= AMP_TOL for p, e in zip(peaks, expect))
        noflip = max(peaks) < FLIP_LIMIT
        t2["beats"][wb] = {"base_peak": round(base_peak, 3),
                           "peaks": [round(p, 3) for p in peaks],
                           "expect": expect, "mono": mono, "ladder": ladder, "noflip": noflip}
        if not mono:
            t2["fail_mono"].append(wb)
        if not ladder:
            t2["fail_ladder"].append(wb)
        if not noflip:
            t2["fail_flip"].append(wb)
    R["T2_monotone_peak"] = {**t2,
        "pass": not (t2["fail_mono"] or t2["fail_ladder"] or t2["fail_flip"])}

    # ---- T3 damped-oscillation signature preserved per tier ----
    t3 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": []}
    for wb in wobble_beats:
        for t in TIERS:
            an = anims["{}__{}".format(wb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(wb, t, bn)
                if not (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6):
                    t3["bad_endpoints"].append(key)
                if _sign_changes_zero(sx) < 3:
                    t3["few_sign_changes"].append(key)
                if not _extrema_mags_decreasing(sx):
                    t3["not_damped"].append(key)
    R["T3_damped_signature"] = {**t3,
        "pass": not (t3["bad_endpoints"] or t3["few_sign_changes"] or t3["not_damped"])}

    # ---- T4 identity interface per tier (insertable between Loop) ----
    t4 = {"bad_interface": [], "shear_endpoints_nonzero": []}
    for wb in wobble_beats:
        for t in TIERS:
            an = anims["{}__{}".format(wb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                t4["bad_interface"].append("{}__{}".format(wb, t))
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                    t4["shear_endpoints_nonzero"].append("{}__{}::{}".format(wb, t, bn))
    R["T4_identity_interface"] = {**t4,
        "pass": not (t4["bad_interface"] or t4["shear_endpoints_nonzero"])}

    # ---- T5 negative controls / isolation ----
    t5 = {}
    # (a) 平增益守衛:全 1.0 → 峰單調 FALSE 且 Super==Legend
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat = False
    super_eq_legend = True
    for wb in wobble_beats:
        fp = [_shear_peak(flat_anims["{}__{}".format(wb, t)]) for t in TIERS]
        if _is_incr(fp):
            any_mono_flat = True
        if abs(fp[0] - fp[-1]) > AMP_TOL:
            super_eq_legend = False
    t5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat,
                          "flat_super_eq_legend": super_eq_legend,
                          "pass": (not any_mono_flat) and super_eq_legend}
    # (b) 隔離/加性:base 全部逐位元不變 + shear 只在 wobble 變體
    base_changed = [k for k in base
                    if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True)]
    shear_leak = []
    for k, an in anims.items():
        if "__" not in k:
            continue
        stem = k.split("__")[0]
        if G.beat_category(stem) == "wobble":
            continue
        for bn, ch in an.get("bones", {}).items():
            if _shear_x(ch):
                shear_leak.append("{}::{}".format(k, bn))
    t5["b_isolation"] = {"base_changed": base_changed, "shear_leak_nonwobble": shear_leak,
                         "pass": not base_changed and not shear_leak}
    # (c) 阻尼形狀不變:極值比對 Super 與 Legend 逐項相等
    ratio_mismatch = []
    ratio_detail = {}
    for wb in wobble_beats:
        an_s = anims["{}__Super".format(wb)]
        an_l = anims["{}__Legend".format(wb)]
        for bn, ch in an_s.get("bones", {}).items():
            sx_s = _shear_x(ch)
            sx_l = _shear_x(an_l["bones"].get(bn, {}))
            if not sx_s or not sx_l:
                continue
            rs = _extrema_ratios(sx_s)
            rl = _extrema_ratios(sx_l)
            key = "{}::{}".format(wb, bn)
            ratio_detail[key] = {"super": [round(x, 4) for x in rs],
                                 "legend": [round(x, 4) for x in rl]}
            if len(rs) != len(rl) or any(abs(a - b) > RATIO_TOL for a, b in zip(rs, rl)):
                ratio_mismatch.append(key)
    t5["c_damping_shape_invariant"] = {"detail": ratio_detail, "mismatch": ratio_mismatch,
                                       "pass": bool(ratio_detail) and not ratio_mismatch}
    R["T5_neg_control"] = {**t5, "pass": all(v["pass"] for v in t5.values())}

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
        for k in ["T1_present_shear", "T2_monotone_peak", "T3_damped_signature",
                  "T4_identity_interface", "T5_neg_control"]:
            print("{:24s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("T2 shear peaks (per wobble beat, Super→Legend):")
        for wb, d in R["T2_monotone_peak"]["beats"].items():
            print("  {:8s} peaks {} expect {}".format(wb, d["peaks"], d["expect"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
