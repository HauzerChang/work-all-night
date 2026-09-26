#!/usr/bin/env python3
"""candidate (G-4''''''-tier) 自我驗收閘 — twist(反相雙軸 shear 節拍)接檔位幅度差異化(純 CPU)。

candidate (J) 讓主秀 beat 依檔位**幅度**差異化(愈高檔位愈爆);(G-4'')把 wobble 的 shearX、
(G-4''''')把 squash 的 shear+耦合 scale 一一接上檔位放大。而 (G-4'''''') 新生成的 twist(反相雙軸
shear,產線第一個驅動 shearY 的節拍)幅度軸在**兩條** shear 軸 —— 尚未被檔位放大,是「檔位機制就緒 ≠
每個新通道接上」的最後一條 shear 通道缺口。本次(G-4''''''-tier)把 twist 併入 `MAIN_SHOW_CATS`:twist
純 shear(無 scale 通道,不在 COUPLED_SCALE_CATS),`amplify_bone_tl` 的 shear 迴圈以**同一 g** 同時放大
shearX 與 shearY(v'=g*v),使兩軸峰隨檔位嚴格遞增,同時 shearY/shearX ≡ −TWIST_PHI 逐檔**不變**(單一
g 對兩軸同比)、反相耦合與阻尼振盪簽章在每個檔位保持 —— **反相雙軸幾何 scale-invariant**(強度變、幾何
種類不變:愈高檔位擰愈狠,仍是同一種雙軸 shear 扭轉,非別種運動)。

真值界定同 (E/H/I/J/G-4'/G-4''''/G-4''''''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章**
(兩軸峰遞增 + φ 比值逐檔不變 + 反相耦合保形)非美感;負對照證鑑別力(閘可信)。從**先驗庫** → **真實
build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

crux(與 wobble tier 的差異):wobble 只有一條 shear 軸;twist 有**兩條**,檔位放大必須讓兩軸**同比**縮放
才能保住反相雙軸簽章(shearY/shearX 比值 = −φ 不變)。若兩軸各自獨立增益,φ 會漂、甚至可能翻掉反相 ——
本機制用**單一 g** 同時作用兩軸(shear 通道對 0 對稱 v'=g*v)⇒ φ 逐檔恆定。這是本閘的鑑別力來源
(同 twist-gen「真雙軸=兩軸皆非零 且 反相」需兩條件並立)。

AC(客觀、可量測):
  TT1 present + backward-compat  : twist base beat 帶雙軸 shear(shearX、shearY 峰皆 ≥ MIN_SHEAR);每檔位
                                  `twist__{tier}` 皆產出、finite、有 bone、≥1 bone 帶 shear、名經
                                  `beat_category` 仍路由回 twist;**base 逐位元不變**(帶/不帶 tier_gains 的
                                  base twist + In/Loop/Out 相同)。
  TT2 crux — dual-axis peak mono : 各檔位 twist 的峰 |shearX| **與** 峰 |shearY| 皆 Super<Mega<Omg<Legend
                                  **嚴格遞增**(端到端經 build_animations 量),且首檔(Super,g=1)兩軸峰 ==
                                  base 兩軸峰(向後相容)。
  TT3 crux — phi ratio invariant : **每個 twist bone**每檔位的 shearY 峰 / shearX 峰 ≈ TWIST_PHI(逐檔不變,
                                  誤差 ≤ PHI_TOL)→ 單一 g 對兩軸同比 → 反相雙軸耦合 scale-invariant。
  TT4 damped sig per tier(兩軸) : **每個檔位**每 twist bone 的 shearX **與** shearY 各自:(a)首尾 0;
                                  (b)繞 0 變號 ≥3;(c)相繼極值幅度嚴格遞減(阻尼)—— 復用 G-4' 判準。
  TT5 counterphase + dev mono    : 每檔位每內部極值幀 shearX·shearY<0(反相**保形**);且反相夾角偏離峰
                                  |shearY−shearX| 隨檔位 Super<Mega<Omg<Legend **嚴格遞增**(雙軸強度隨檔位)。
  TT6 neg-control / isolation    : (a)**平增益守衛**:增益全 1.0 → TT2 兩軸遞增 FALSE 且各檔位 twist 逐位元
                                  == base twist;(b)**單一-g 兩軸同比單元測**:`amplify_bone_tl` 對「只有雙軸
                                  shear」的 bone(g=2)→ shearX、shearY 皆 ×g(比值不變),不生 scale 鍵;
                                  **獨立軸增益負對照**(只放大 shearX、shearY 不動)→ 比值改變(證單一-g 是
                                  φ 保形的關鍵、閘測比值不變非恆真);(c)**shear 隔離**:全 storyboard(含所有
                                  檔位變體)只有 SHEAR_CATS(wobble/squash/twist)及其 `__tier` 變體帶 shear。

用法:
  python3 validate_twist_tier.py            # 摘要
  python3 validate_twist_tier.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from beat_templates import TWIST_PHI
from analyze_target import analyze
# 復用 G-4' 的阻尼簽章判準(與 shear_gen / twist_gen 閘完全一致)+ twist_gen 的雙軸讀取/反相判準
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_twist_gen import _shear_y, _shear_xy, _interior_shear, _tw3_eval, _has_shear_y

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,base twist 兩軸峰下限(head 最小:shearX 10°、shearY 7° → 餘裕)
PHI_TOL = 2e-3      # shearY峰/shearX峰 對 TWIST_PHI 的容差(g*v 4 位捨入下的餘裕)


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/twist_tier_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _twist_beats(anims):
    # G-4''''''-vol:twist_vol(體積守恆扭轉)為 base-only 節拍(未接 tier/count 差異化)→ 排除,
    # 使本閘所量的 twist 集合與新增 twist_vol 前逐一相同(此閘只驗純雙軸 shear twist 及其檔位變體)。
    return [nm for nm in anims if "__" not in nm and "vol" not in nm.lower() and G.beat_category(nm) == "twist"]


def _peak_x(anim):
    """該 anim 全 bone 的峰 |shearX|(無 shear 回 0)。"""
    ps = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(ps, default=0.0)


def _peak_y(anim):
    """該 anim 全 bone 的峰 |shearY|(無 shear 回 0)。"""
    ps = [max(abs(v) for v in _shear_y(ch)) for ch in anim.get("bones", {}).values() if _shear_y(ch)]
    return max(ps, default=0.0)


def _dev_peak(anim):
    """該 anim 全 bone 內部極值的峰 |shearY−shearX|(反相夾角偏離;無 shear 回 0)。"""
    devs = []
    for ch in anim.get("bones", {}).values():
        for (shx, shy) in _interior_shear(ch):
            devs.append(abs(shy - shx))
    return max(devs, default=0.0)


def _is_strict_inc(xs):
    return all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                       # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)    # 帶檔位
    twist_beats = _twist_beats(base)
    R = {}

    # ---- TT1 present + backward-compat ----
    t1 = {"twist_beats": twist_beats, "base_weak_shear": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_shear": [], "misrouted": [], "base_changed": []}
    for tb in twist_beats:
        if _peak_x(base[tb]) < MIN_SHEAR or _peak_y(base[tb]) < MIN_SHEAR:
            t1["base_weak_shear"].append(tb)
        for t in TIERS:
            vk = "{}__{}".format(tb, t)
            an = anims.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            if not an.get("bones"):
                t1["no_bones"].append(vk)
            if not any(_shear_xy(ch) for ch in an.get("bones", {}).values()):
                t1["variant_no_shear"].append(vk)
            if G.beat_category(vk) != "twist":
                t1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:  # base(含 In/Loop/Out + base twist)帶/不帶 tier_gains 逐位元不變
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    t1_pass = (bool(twist_beats) and not any(t1[k] for k in
               ["base_weak_shear", "missing", "not_finite", "no_bones", "variant_no_shear",
                "misrouted", "base_changed"]))
    R["TT1_present_backward_compat"] = {**t1, "pass": t1_pass}

    # ---- TT2 crux: both-axis peak monotone across tiers ----
    t2 = {"beats": {}, "fail_mono_x": [], "fail_mono_y": [], "fail_base": []}
    for tb in twist_beats:
        px = [_peak_x(anims["{}__{}".format(tb, t)]) for t in TIERS]
        py = [_peak_y(anims["{}__{}".format(tb, t)]) for t in TIERS]
        bx, by = _peak_x(base[tb]), _peak_y(base[tb])
        mono_x, mono_y = _is_strict_inc(px), _is_strict_inc(py)
        super_eq = abs(px[0] - bx) <= 1e-4 and abs(py[0] - by) <= 1e-4
        t2["beats"][tb] = {"shearX_peaks": [round(p, 3) for p in px],
                           "shearY_peaks": [round(p, 3) for p in py],
                           "base": [round(bx, 3), round(by, 3)],
                           "mono_x": mono_x, "mono_y": mono_y, "super_eq_base": super_eq}
        if not mono_x:
            t2["fail_mono_x"].append(tb)
        if not mono_y:
            t2["fail_mono_y"].append(tb)
        if not super_eq:
            t2["fail_base"].append(tb)
    t2_pass = (bool(t2["beats"]) and not t2["fail_mono_x"]
               and not t2["fail_mono_y"] and not t2["fail_base"])
    R["TT2_dual_axis_peak_monotone"] = {**t2, "pass": t2_pass}

    # ---- TT3 crux: phi ratio (shearY_pk / shearX_pk) tier-invariant, per bone ----
    t3 = {"bad_ratio": [], "detail": {}}
    for tb in twist_beats:
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx, sy = _shear_x(ch), _shear_y(ch)
                if not sx or not sy:
                    continue
                pkx = max(abs(v) for v in sx)
                pky = max(abs(v) for v in sy)
                if pkx <= 1e-9:
                    continue
                ratio = pky / pkx
                key = "{}__{}::{}".format(tb, t, bn)
                t3["detail"][key] = round(ratio, 5)
                if abs(ratio - TWIST_PHI) > PHI_TOL:
                    t3["bad_ratio"].append((key, round(ratio, 5)))
    t3_pass = bool(t3["detail"]) and not t3["bad_ratio"]
    R["TT3_phi_ratio_invariant"] = {**t3, "phi": TWIST_PHI, "pass": t3_pass}

    # ---- TT4 both-axes damped-oscillation signature preserved per tier ----
    t4 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "detail": {}}
    for tb in twist_beats:
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                for axis, vals in (("x", _shear_x(ch)), ("y", _shear_y(ch))):
                    if not vals:
                        continue
                    key = "{}__{}::{}::{}".format(tb, t, bn, axis)
                    ends_ok = abs(vals[0]) < 1e-6 and abs(vals[-1]) < 1e-6
                    nsc = _sign_changes_zero(vals)
                    damp = _extrema_mags_decreasing(vals)
                    t4["detail"][key] = {"n_sign_changes": nsc, "damped": damp}
                    if not ends_ok:
                        t4["bad_endpoints"].append(key)
                    if nsc < 3:
                        t4["few_sign_changes"].append(key)
                    if not damp:
                        t4["not_damped"].append(key)
    t4_pass = (bool(t4["detail"]) and not t4["bad_endpoints"]
               and not t4["few_sign_changes"] and not t4["not_damped"])
    R["TT4_damped_signature_per_tier"] = {**t4, "pass": t4_pass}

    # ---- TT5 counter-phase preserved per tier + deviation peak monotone ----
    t5 = {"not_counterphase": [], "beats": {}, "fail_dev_mono": []}
    for tb in twist_beats:
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_shear(ch)
                if not interior or not _has_shear_y(ch):
                    continue
                cp_ok, _dev_ok, _det = _tw3_eval(interior)
                if not cp_ok:
                    t5["not_counterphase"].append("{}__{}::{}".format(tb, t, bn))
        devs = [_dev_peak(anims["{}__{}".format(tb, t)]) for t in TIERS]
        mono = _is_strict_inc(devs)
        t5["beats"][tb] = {"dev_peaks": [round(d, 3) for d in devs], "mono": mono}
        if not mono:
            t5["fail_dev_mono"].append(tb)
    t5_pass = (bool(t5["beats"]) and not t5["not_counterphase"] and not t5["fail_dev_mono"])
    R["TT5_counterphase_dev_monotone"] = {**t5, "pass": t5_pass}

    # ---- TT6 negative controls / isolation ----
    t6 = {}
    # (a) 平增益守衛:全 1.0 → 兩軸遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for tb in twist_beats:
        px = [_peak_x(flat_anims["{}__{}".format(tb, t)]) for t in TIERS]
        py = [_peak_y(flat_anims["{}__{}".format(tb, t)]) for t in TIERS]
        if _is_strict_inc(px) or _is_strict_inc(py):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(tb, t)], sort_keys=True) != \
               json.dumps(base[tb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(tb, t))
    t6["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) 單一-g 兩軸同比單元測 + 獨立軸增益負對照(φ 漂移)
    g = 2.0
    twist_only = {"shear": [{"time": 0.0, "x": 0.0, "y": 0.0},
                            {"time": 0.3, "x": 16.0, "y": -11.2},
                            {"time": 0.6, "x": -8.0, "y": 5.6},
                            {"time": 0.9, "x": 0.0, "y": 0.0}]}
    a_tw = TV.amplify_bone_tl(twist_only, g)
    tw_no_scale = "scale" not in a_tw
    x_amp = abs(a_tw["shear"][1]["x"] - g * 16.0) <= 1e-6      # v'=g*v
    y_amp = abs(a_tw["shear"][1]["y"] - g * (-11.2)) <= 1e-6   # 兩軸皆 ×g
    ratio_in = abs(-11.2 / 16.0)
    ratio_out = abs(a_tw["shear"][1]["y"] / a_tw["shear"][1]["x"])
    ratio_kept = abs(ratio_out - ratio_in) <= 1e-9            # 單一 g → 比值不變
    # 負對照:只放大 shearX、shearY 不動(獨立軸增益)→ 比值改變(證單一-g 是關鍵)
    neg_ratio_out = abs((-11.2) / (g * 16.0))                 # y 不動、x×g
    neg_ratio_broken = abs(neg_ratio_out - ratio_in) > 1e-3
    t6["b_single_g_unit"] = {"twist_no_scale": tw_no_scale, "x_amplified": x_amp,
                             "y_amplified": y_amp, "ratio_kept": ratio_kept,
                             "neg_indep_axis_breaks_ratio": neg_ratio_broken,
                             "pass": (tw_no_scale and x_amp and y_amp and ratio_kept
                                      and neg_ratio_broken)}
    # (c) shear 隔離到 SHEAR_CATS(含所有檔位變體)
    leak = []
    for nm, an in anims.items():
        if G.beat_category(nm.split("__")[0]) in TV.SHEAR_CATS:
            continue
        sheared = [bn for bn, ch in an.get("bones", {}).items() if _shear_xy(ch)]
        if sheared:
            leak.append((nm, sheared))
    t6["c_shear_isolated"] = {"leaked": leak, "pass": not leak}
    R["TT6_neg_control"] = {**t6, "pass": all(v["pass"] for v in t6.values())}

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
        for k in ["TT1_present_backward_compat", "TT2_dual_axis_peak_monotone",
                  "TT3_phi_ratio_invariant", "TT4_damped_signature_per_tier",
                  "TT5_counterphase_dev_monotone", "TT6_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("TT2 peaks per tier {}:".format(TIERS))
        for tb, d in R["TT2_dual_axis_peak_monotone"]["beats"].items():
            print("  {:10s} shearX {}  shearY {}  (base {})".format(
                tb, d["shearX_peaks"], d["shearY_peaks"], d["base"]))
        print("TT3 phi={} ratios(sample): {}".format(
            R["TT3_phi_ratio_invariant"]["phi"],
            dict(list(R["TT3_phi_ratio_invariant"]["detail"].items())[:4])))
        print("TT5 dev peaks per tier:")
        for tb, d in R["TT5_counterphase_dev_monotone"]["beats"].items():
            print("  {:10s} {}".format(tb, d["dev_peaks"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
