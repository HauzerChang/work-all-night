#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

candidate (G-4'''') 讓 `gen_squash` 成為第一個**同時**產出 `shear` 與非均勻 `scale`(體積守恆擠壓)的
生成器,但它當時**不在** `MAIN_SHOW_CATS` —— 因為舊的幅度增益 `_amp_scale`(只放大 identity 上方
overshoot、下方樓地板不動)會**破壞體積守恆**:squash 的 scaleX=1+q>1 被放大、scaleY=1/(1+q)<1 樓地板
不動 → scaleX·scaleY≠1(不再是擠壓,而是「拉長 + 微壓」的變形)。這是 G-4'''' 留下的 honest boundary
(「squash 未接 tier 幅度,需**耦合 amplify**」)。

本次(G-4''''')補上:把 squash 併入 `MAIN_SHOW_CATS`,並讓其 scale 通道走**體積守恆耦合放大**
(`tier_variants._amp_squash_pair`:把拉長量 q=scaleX−1 放大 g 倍、scaleY 重建為 1/(1+g·q))⇒ 檔位愈高、
擠壓愈強(shear 峰↑、拉長量↑、非均勻↑)而**面積恆守恆**(scaleX·scaleY≡1)、首尾仍 identity。此式等價於
「以 Q'=g·Q 重跑 gen_squash」—— 與 (J) 的 wobble/scale/rotate 幅度軸**正交可疊**,且 shear 峰仍隨檔位遞增
(復用 amplify_bone_tl 對 shear 的 v'=g·v)。**關鍵:squash 的檔位差異化必須兩軸耦合,不能逐軸獨立**
(逐軸 = 破壞守恆 → 見 V5b 判別子)。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**
(體積守恆 + 阻尼耦合 + 檔位單調),用負對照證鑑別力(閘可信)。從**先驗庫** → **真實 build_spine robot
骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  V1 present + backward-compat  : squash base beat 為雙通道(≥1 bone 同時帶 shear 與非均勻 scale);每檔位
                                 `squash__{tier}` 皆產出、finite、有 bone、≥1 bone 帶 shear+scale、名經
                                 `beat_category` 仍路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains 的
                                 base squash + In/Loop/Out 相同);**Super(g=1)逐位元 == base squash**。
  V2 crux — coupled amp monotone: 各檔位 squash Super<Mega<Omg<Legend **嚴格遞增**且 Super==base:
                                 (a)shear 峰 |shearX|;(b)拉長峰 |scaleX−1|;(c)非均勻峰 |scaleX−scaleY|。
  V3 crux — volume kept per tier : **每個檔位**的 squash bone、**每個** scale 極值幀 (a)scaleX·scaleY≈1
                                 (|積−1|≤TOL_VOL,耦合放大保守恆);(b)至少一極值 |scaleX−scaleY|≥MIN_ANISO
                                 (仍真擠壓);(c)|scaleX−1| 隨極值嚴格遞減(阻尼耦合保形)。
  V4 damped + identity per tier  : **每個檔位** shear (a)首尾 0、(b)繞 0 變號 ≥3、(c)相繼極值遞減(阻尼);
                                 且 scale 首尾 (1,1)(identity 介面 → 可插 Loop)。
  V5 neg-control                 : (a) **平增益守衛**:增益全 1.0 → V2 遞增 FALSE 且各檔位逐位元 == base;
                                 (b) **耦合判別子(crux)**:對 base squash 的 scale 施**舊逐軸** `_amp_scale`
                                    (Legend g)→ 體積守恆 FALSE(|積−1|>TOL_VOL);真正的耦合變體(同 g)→
                                    體積守恆 TRUE。證閘測的是「耦合守恆放大」非「有 scale 放大即可」。
                                 (c) **耦合放大單元測**:`_amp_squash_pair` 對守恆對施同 g → 積==1(精確)、
                                    q=0 幀 →(1,1)不動;`amplify_bone_tl(coupled_scale=True)` 保守恆、
                                    `coupled_scale=False`(逐軸)破壞守恆(同一 bone、同一 g)。

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
# 復用 G-4' 的 shear 讀取與阻尼簽章判準、G-4'''' 的 squash scale 判準,確保與各閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import _scale_xy, _interior_scale, _sq3_eval, MIN_ANISO, TOL_VOL, MIN_SHEAR

GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
PSD = "assets/robot_parts.psd"


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/squash_tier_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _squash_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "squash"]


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _stretch_peak(anim):
    """全 bone 的峰 |scaleX−1|(拉長量;squash 慣例 scaleX≥1)。"""
    peaks = [max(abs(sx - 1.0) for (sx, sy) in _scale_xy(ch))
             for ch in anim.get("bones", {}).values() if _scale_xy(ch)]
    return max(peaks, default=0.0)


def _aniso_peak(anim):
    """全 bone 的峰 |scaleX−scaleY|(非均勻程度)。"""
    peaks = [max(abs(sx - sy) for (sx, sy) in _scale_xy(ch))
             for ch in anim.get("bones", {}).values() if _scale_xy(ch)]
    return max(peaks, default=0.0)


def _is_strict_inc(xs):
    return len(xs) >= 2 and all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                       # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)    # 帶檔位
    squash_beats = _squash_beats(base)
    R = {}

    # ---- V1 present + backward-compat ----
    v1 = {"squash_beats": squash_beats, "base_not_dual": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_not_dual": [], "misrouted": [], "base_changed": [],
          "super_ne_base": []}
    for qb in squash_beats:
        base_dual = any(_shear_x(ch) and _scale_xy(ch) for ch in base[qb].get("bones", {}).values())
        if not base_dual:
            v1["base_not_dual"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                v1["missing"].append(vk); continue
            if not SA.all_finite(an):
                v1["not_finite"].append(vk)
            if not an.get("bones"):
                v1["no_bones"].append(vk)
            if not any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values()):
                v1["variant_not_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                v1["misrouted"].append((vk, G.beat_category(vk)))
        # Super(g=1)逐位元 == base squash
        sup = anims.get("{}__Super".format(qb))
        if json.dumps(sup, sort_keys=True) != json.dumps(base[qb], sort_keys=True):
            v1["super_ne_base"].append(qb)
    # base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            v1["base_changed"].append(k)
    v1_pass = (bool(squash_beats) and not any(v1[k] for k in
               ["base_not_dual", "missing", "not_finite", "no_bones", "variant_not_dual",
                "misrouted", "base_changed", "super_ne_base"]))
    R["V1_present_backward_compat"] = {**v1, "pass": v1_pass}

    # ---- V2 crux: coupled amplitude monotone across tiers (shear / stretch / aniso) ----
    v2 = {"beats": {}, "fail": []}
    for qb in squash_beats:
        sh = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        st = [_stretch_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        an_ = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_sh, base_st, base_an = _shear_peak(base[qb]), _stretch_peak(base[qb]), _aniso_peak(base[qb])
        sh_ok = _is_strict_inc(sh) and abs(sh[0] - base_sh) <= 1e-4
        st_ok = _is_strict_inc(st) and abs(st[0] - base_st) <= 1e-4
        an_ok = _is_strict_inc(an_) and abs(an_[0] - base_an) <= 1e-4
        v2["beats"][qb] = {"shear_peaks": [round(x, 3) for x in sh],
                           "stretch_peaks": [round(x, 4) for x in st],
                           "aniso_peaks": [round(x, 4) for x in an_],
                           "shear_mono": sh_ok, "stretch_mono": st_ok, "aniso_mono": an_ok}
        if not (sh_ok and st_ok and an_ok):
            v2["fail"].append(qb)
    v2_pass = bool(v2["beats"]) and not v2["fail"]
    R["V2_coupled_amplitude_monotone"] = {**v2, "pass": v2_pass}

    # ---- V3 crux: volume conservation preserved per tier ----
    v3 = {"bad_volume": [], "no_aniso": [], "not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior or not _shear_x(ch):
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                vok, aok, dok, det = _sq3_eval(interior)
                v3["detail"][key] = det
                if not vok:
                    v3["bad_volume"].append(key)
                if not aok:
                    v3["no_aniso"].append(key)
                if not dok:
                    v3["not_damped"].append(key)
    v3_pass = (bool(v3["detail"]) and not v3["bad_volume"] and not v3["no_aniso"] and not v3["not_damped"])
    R["V3_volume_kept_per_tier"] = {**v3, "pass": v3_pass}

    # ---- V4 damped shear + identity interface per tier ----
    v4 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "scale_endpoints_nonident": []}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                key = "{}__{}::{}".format(qb, t, bn)
                if sx:
                    if not (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6):
                        v4["bad_endpoints"].append(key)
                    if _sign_changes_zero(sx) < 3:
                        v4["few_sign_changes"].append(key)
                    if not _extrema_mags_decreasing(sx):
                        v4["not_damped"].append(key)
                xy = _scale_xy(ch)
                if xy and (abs(xy[0][0] - 1.0) > 1e-6 or abs(xy[0][1] - 1.0) > 1e-6
                           or abs(xy[-1][0] - 1.0) > 1e-6 or abs(xy[-1][1] - 1.0) > 1e-6):
                    v4["scale_endpoints_nonident"].append(key)
    v4_pass = not any(v4[k] for k in v4)
    R["V4_damped_identity_per_tier"] = {**v4, "pass": v4_pass}

    # ---- V5 negative controls ----
    v5 = {}
    # (a) 平增益守衛:全 1.0 → V2 遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for qb in squash_beats:
        st = [_stretch_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        sh = [_shear_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(st) or _is_strict_inc(sh):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    v5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}

    # (b) 耦合判別子(crux):對 base squash scale 施舊逐軸 _amp_scale(Legend g)→ 破壞守恆;
    #     真正耦合變體(同 g)→ 守恆。證閘測「耦合守恆放大」非「有 scale 放大即可」。
    g_leg = gains["Legend"]
    naive_broken, coupled_kept = False, True
    naive_detail, coupled_detail = {}, {}
    for qb in squash_beats:
        for bn, ch in base[qb].get("bones", {}).items():
            interior = _interior_scale(ch)
            if not interior or not _shear_x(ch):
                continue
            key = "{}::{}".format(qb, bn)
            # 舊逐軸放大(_amp_scale 各軸獨立)
            naive = [(TV._amp_scale(sx, g_leg), TV._amp_scale(sy, g_leg)) for (sx, sy) in interior]
            n_prod = [round(sx * sy, 5) for (sx, sy) in naive]
            naive_detail[key] = n_prod
            if any(abs(p - 1.0) > TOL_VOL for p in n_prod):
                naive_broken = True
            # 真正耦合變體(同 g=Legend)
            cvar = anims["{}__Legend".format(qb)]["bones"][bn]
            c_interior = _interior_scale(cvar)
            c_prod = [round(sx * sy, 5) for (sx, sy) in c_interior]
            coupled_detail[key] = c_prod
            if any(abs(p - 1.0) > TOL_VOL for p in c_prod):
                coupled_kept = False
    v5["b_coupling_discriminator"] = {"naive_axiswise_breaks_volume": naive_broken,
                                      "coupled_keeps_volume": coupled_kept,
                                      "naive_prod": naive_detail, "coupled_prod": coupled_detail,
                                      "pass": naive_broken and coupled_kept}

    # (c) 耦合放大單元測:_amp_squash_pair 精確守恆 + q=0 不動;amplify_bone_tl coupled vs 逐軸
    g = 2.0
    pair = [(1.16, 1.0 / 1.16), (1.08, 1.0 / 1.08)]
    unit_exact = all(abs(TV._amp_squash_pair(sx, sy, g)[0] * TV._amp_squash_pair(sx, sy, g)[1] - 1.0) <= 1e-9
                     for (sx, sy) in pair)
    ident_fixed = TV._amp_squash_pair(1.0, 1.0, g) == (1.0, 1.0)
    squashy = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0},
                         {"time": 0.4, "x": 1.16, "y": round(1.0 / 1.16, 4)},
                         {"time": 1.0, "x": 1.0, "y": 1.0}]}
    a_coupled = TV.amplify_bone_tl(squashy, g, coupled_scale=True)
    a_axiswise = TV.amplify_bone_tl(squashy, g, coupled_scale=False)
    cp = a_coupled["scale"][1]
    ap = a_axiswise["scale"][1]
    coupled_prod_ok = abs(cp["x"] * cp["y"] - 1.0) <= 2e-4       # 耦合保守恆
    axiswise_prod_broken = abs(ap["x"] * ap["y"] - 1.0) > TOL_VOL  # 逐軸破壞守恆
    v5["c_amplify_unit"] = {"pair_exact_conserve": unit_exact, "identity_fixed": ident_fixed,
                            "coupled_prod": round(cp["x"] * cp["y"], 5),
                            "axiswise_prod": round(ap["x"] * ap["y"], 5),
                            "coupled_prod_ok": coupled_prod_ok,
                            "axiswise_prod_broken": axiswise_prod_broken,
                            "pass": unit_exact and ident_fixed and coupled_prod_ok and axiswise_prod_broken}
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
        for k in ["V1_present_backward_compat", "V2_coupled_amplitude_monotone",
                  "V3_volume_kept_per_tier", "V4_damped_identity_per_tier", "V5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V2 peaks per tier {}:".format(TIERS))
        for qb, d in R["V2_coupled_amplitude_monotone"]["beats"].items():
            print("  {:8s} shear {}  stretch {}  aniso {}".format(
                qb, d["shear_peaks"], d["stretch_peaks"], d["aniso_peaks"]))
        db = R["V5_neg_control"]["b_coupling_discriminator"]
        print("V5b discriminator: naive_axiswise breaks_volume={} coupled keeps_volume={}".format(
            db["naive_axiswise_breaks_volume"], db["coupled_keeps_volume"]))
        print("     naive_prod:", db["naive_prod"])
        print("     coupled_prod:", db["coupled_prod"])
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
