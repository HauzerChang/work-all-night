#!/usr/bin/env python3
"""candidate (G-4'') 自我驗收閘 — wobble(shear 通道節拍)接檔位幅度差異化(純 CPU)。

candidate (J) 讓主秀 beat 依檔位**幅度**差異化(愈高檔位愈爆),但當時的幅度增益只作用在
scale/rotate/translate;而 (G-4') 新生成的 wobble(斜拉 jelly wobble)幅度軸在 **shear** —— 未被
檔位放大,是「檔位機制就緒 ≠ 每個新通道接上」的又一缺口。本次(G-4'')把 wobble 併入 `MAIN_SHOW_CATS`
並讓 `amplify_bone_tl` 一併放大 shear(對 0 對稱 → v'=g*v),使 **wobble 的 shearX 峰隨檔位嚴格遞增**,
同時**阻尼振盪簽章(振盪+遞減)在每個檔位保持**(強度變、結構不變 —— 誠實地:檔位=更斜更晃,非別種運動)。

真值界定同 (E/H/I/J/G-4'):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位 shear 愈大」是可量化的檔位簽章,用負對照證鑑別力(閘可信)。從**先驗庫** → **真實
build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  T1 present + backward-compat : wobble base beat 有 shear;每檔位 `wobble__{tier}` 皆產出、finite、
                                有 bone、≥1 bone 帶 shear 通道、名經 `beat_category` 仍路由回 wobble;
                                **base 逐位元不變**(帶/不帶 tier_gains 的 base wobble + In/Loop/Out 相同)。
  T2 crux — shear peak monotone: 各檔位 wobble 的峰 |shearX| Super<Mega<Omg<Legend **嚴格遞增**
                                (端到端經 build_animations 量),且首檔(Super,g=1)峰 == base 峰(向後相容)。
  T3 damped signature per tier : **每個檔位**的 wobble bone 仍 (a)首尾 shearX==0;(b)繞 0 變號 ≥3;
                                (c)相繼極值幅度嚴格遞減(阻尼)。→ g*v 同比放大 → 符號序列與遞減比不變。
  T4 shear isolated to wobble  : 全 storyboard(含所有檔位變體)中,**只有 wobble 及其 `__tier` 變體**帶
                                shear 通道;非-wobble 主秀 beat 及其變體皆 0 bone 帶 shear → `include_shear`
                                補償對象仍只鎖 wobble,對 (J) 既有 scale/rotate 節拍零 shear 外洩。
  T5 neg-control               : (a) **平增益守衛**:增益階梯全 1.0 → T2 shear 遞增 FALSE(證閘測遞增非恆真)
                                且各檔位 wobble 逐位元 == base wobble;
                                (b) **通道隔離單元測**:`amplify_bone_tl` 對「只有 scale」的 bone → 不生 shear 鍵、
                                scale 照放大;對「只有 shear」的 bone → shear 放大 g*v、不生 scale 鍵
                                (證 shear 增益是加性、與其他通道正交)。

用法:
  python3 validate_wobble_tier.py            # 摘要
  python3 validate_wobble_tier.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
# 復用 G-4' 的阻尼簽章判準,確保與 shear-gen 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,base wobble 峰值下限(確認確有明顯 shear)


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/wobble_tier_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _wobble_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "wobble"]


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
    wobble_beats = _wobble_beats(base)
    R = {}

    # ---- T1 present + backward-compat ----
    t1 = {"wobble_beats": wobble_beats, "base_no_shear": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_shear": [], "misrouted": [], "base_changed": []}
    for wb in wobble_beats:
        if _shear_peak(base[wb]) < MIN_SHEAR:
            t1["base_no_shear"].append(wb)
        for t in TIERS:
            vk = "{}__{}".format(wb, t)
            an = anims.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            if not an.get("bones"):
                t1["no_bones"].append(vk)
            if not any(_shear_x(ch) for ch in an.get("bones", {}).values()):
                t1["variant_no_shear"].append(vk)
            if G.beat_category(vk) != "wobble":
                t1["misrouted"].append((vk, G.beat_category(vk)))
    # base(含 In/Loop/Out + base wobble)帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    t1_pass = (bool(wobble_beats) and not any(t1[k] for k in
               ["base_no_shear", "missing", "not_finite", "no_bones", "variant_no_shear",
                "misrouted", "base_changed"]))
    R["T1_present_backward_compat"] = {**t1, "pass": t1_pass}

    # ---- T2 crux: shear peak monotone across tiers ----
    t2 = {"beats": {}, "fail_mono": [], "fail_base": []}
    for wb in wobble_beats:
        peaks = [_shear_peak(anims["{}__{}".format(wb, t)]) for t in TIERS]
        base_peak = _shear_peak(base[wb])
        mono = _is_strict_inc(peaks)
        super_eq_base = abs(peaks[0] - base_peak) <= 1e-4     # Super g=1 → 同 base
        t2["beats"][wb] = {"shear_peaks": [round(p, 3) for p in peaks],
                           "base_peak": round(base_peak, 3),
                           "mono": mono, "super_eq_base": super_eq_base}
        if not mono:
            t2["fail_mono"].append(wb)
        if not super_eq_base:
            t2["fail_base"].append(wb)
    t2_pass = bool(t2["beats"]) and not t2["fail_mono"] and not t2["fail_base"]
    R["T2_shear_peak_monotone"] = {**t2, "pass": t2_pass}

    # ---- T3 damped-oscillation signature preserved per tier ----
    t3 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "detail": {}}
    for wb in wobble_beats:
        for t in TIERS:
            an = anims["{}__{}".format(wb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(wb, t, bn)
                ends_ok = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                nsc = _sign_changes_zero(sx)
                damp = _extrema_mags_decreasing(sx)
                t3["detail"][key] = {"n_sign_changes": nsc, "damped": damp}
                if not ends_ok:
                    t3["bad_endpoints"].append(key)
                if nsc < 3:
                    t3["few_sign_changes"].append(key)
                if not damp:
                    t3["not_damped"].append(key)
    t3_pass = (bool(t3["detail"]) and not t3["bad_endpoints"]
               and not t3["few_sign_changes"] and not t3["not_damped"])
    R["T3_damped_signature_per_tier"] = {**t3, "pass": t3_pass}

    # ---- T4 shear isolated to shear-emitters (incl. all tier variants) ----
    # (G-4'''':shear 產出者集合擴為 {wobble, squash};以 SHEAR_CATS 認定,squash 亦合法帶 shear)
    t4 = {"leaked": []}
    for nm, an in anims.items():
        base_name = nm.split("__")[0]
        if G.beat_category(base_name) in TV.SHEAR_CATS:
            continue
        sheared = [bn for bn, ch in an.get("bones", {}).items() if _shear_x(ch)]
        if sheared:
            t4["leaked"].append((nm, sheared))
    R["T4_shear_isolated"] = {**t4, "pass": not t4["leaked"]}

    # ---- T5 negative controls ----
    t5 = {}
    # (a) 平增益守衛:全 1.0 → shear 遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for wb in wobble_beats:
        peaks = [_shear_peak(flat_anims["{}__{}".format(wb, t)]) for t in TIERS]
        if _is_strict_inc(peaks):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(wb, t)], sort_keys=True) != \
               json.dumps(base[wb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(wb, t))
    t5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) 通道隔離單元測:amplify_bone_tl 對 scale-only / shear-only bone
    g = 2.0
    scale_only = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0}, {"time": 0.5, "x": 1.3, "y": 1.3},
                            {"time": 1.0, "x": 1.0, "y": 1.0}]}
    shear_only = {"shear": [{"time": 0.0, "x": 0.0, "y": 0.0}, {"time": 0.5, "x": 10.0, "y": 0.0},
                            {"time": 1.0, "x": 0.0, "y": 0.0}]}
    a_sc = TV.amplify_bone_tl(scale_only, g)
    a_sh = TV.amplify_bone_tl(shear_only, g)
    sc_no_shear = "shear" not in a_sc
    sc_amplified = abs(a_sc["scale"][1]["x"] - (1.0 + g * 0.3)) <= 1e-6   # v'=1+g(v-1)
    sh_no_scale = "scale" not in a_sh
    sh_amplified = abs(a_sh["shear"][1]["x"] - g * 10.0) <= 1e-6          # v'=g*v
    t5["b_channel_isolation"] = {"scale_only_no_shear": sc_no_shear, "scale_amplified": sc_amplified,
                                 "shear_only_no_scale": sh_no_scale, "shear_amplified": sh_amplified,
                                 "pass": sc_no_shear and sc_amplified and sh_no_scale and sh_amplified}
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
        for k in ["T1_present_backward_compat", "T2_shear_peak_monotone",
                  "T3_damped_signature_per_tier", "T4_shear_isolated", "T5_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("T2 shear peaks per tier {}:".format(TIERS))
        for wb, d in R["T2_shear_peak_monotone"]["beats"].items():
            print("  {:10s} {}  (base {})".format(wb, d["shear_peaks"], d["base_peak"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
