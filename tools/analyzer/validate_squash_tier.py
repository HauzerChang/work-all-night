#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

一路的 honest boundary:candidate (J) 讓主秀 beat 依檔位**幅度**差異化;(G-4'')/(G-4''') 把 wobble
(純 shear)接上檔位幅度/段數;(G-4'''') 讓 `gen_squash` 產出**耦合的 shear + 體積守恆非均勻 scale**,
但當時 squash **不在** `MAIN_SHOW_CATS` —— 因為一般 `_amp_scale`(只放大 identity 上方 overshoot)會
單邊放大 scaleX、保留 scaleY 壓扁樓地板 → **破壞體積守恆**(scaleX·scaleY≠1)。本次(G-4''''')補上
**耦合 amplify**:放大擠壓幅度 q=scaleX−1 為 g·q、重生 scaleY=1/(1+g·q),使檔位放大後**仍嚴格**
scaleX·scaleY≡1(且非均勻),squash 得以併入 `MAIN_SHOW_CATS` → 檔位愈高、擠壓愈狠而體積恆守。

真值/fixture 與 (E/H/I/J/G-4'/G-4'''') 一致:從**先驗庫**(slot_bigwin,squash beat)經 `analyze_target`
→ **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。主秀運動無唯一正解
(PROPOSAL 手感),閘驗**客觀結構簽章**(阻尼振盪 + 體積守恆耦合 + 檔位單調)非美感;負對照證鑑別力。

AC(客觀、可量測):
  V1 present + backward-compat  : squash base beat 有耦合雙通道;每檔位 `squash__{tier}` 皆產出、finite、
                                 有 bone、≥1 bone **同時**帶 shear 與 scale、名經 `beat_category` 仍路由回
                                 squash;**base 逐位元不變**(帶/不帶 tier_gains 的 base squash + In/Loop/Out
                                 相同);首檔 `squash__Super`(g=1)逐位元 == base squash(向後相容)。
  V2 crux — dual-axis monotone : 各檔位 squash 的 (a)峰 |shearX| 與 (b)峰非均勻 |scaleX−scaleY| **兩軸皆**
                                 Super<Mega<Omg<Legend 嚴格遞增(端到端經 build_animations 量),Super==base。
  V3 crux — volume preserved/tier: **每個檔位**的每個 squash 極值幀仍 (a)scaleX·scaleY≈1(體積守恆,
                                 耦合 amplify 的核心 —— 放大不破壞守恆);(b)非均勻;(c)擠壓幅度隨極值嚴格遞減。
  V4 damped shear per tier      : **每個檔位**的 squash shearX 仍 (a)首尾 0;(b)繞 0 變號 ≥3;(c)相繼極值遞減。
  V5 neg-control / 正交         : (a)**平增益守衛**:增益階梯全 1.0 → V2 兩軸遞增 FALSE 且各檔位逐位元 == base;
                                 (b)**耦合必要性單元測(crux 守衛)**:對真實 squash scale 幀,`coupled=True`
                                 放大後體積守恆(積≈1)且擠壓幅度 = g·q;而 `coupled=False`(天真 `_amp_scale`)
                                 放大後**破壞守恆**(積顯著偏 1)→ 證「耦合」是必要且此機制正是修正;
                                 g=1 耦合逐位元 == 原幀、identity 幀恆保 identity。

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
import beat_templates as BT
from analyze_target import analyze
# 復用 G-4' 的 shear 讀取與阻尼簽章判準、G-4'''' 的體積守恆判準,確保跨閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import _scale_xy, _interior_scale, _sq3_eval, MIN_SHEAR, MIN_ANISO, TOL_VOL

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


def _squash_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "squash"]


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _aniso_peak(anim):
    """該 anim 全 bone 的峰非均勻 |scaleX−scaleY|(無 scale 回 0)。"""
    peaks = [max((abs(sx - sy) for (sx, sy) in _scale_xy(ch)), default=0.0)
             for ch in anim.get("bones", {}).values() if _scale_xy(ch)]
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
    v1 = {"squash_beats": squash_beats, "base_no_dual": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": [], "super_ne_base": []}
    for qb in squash_beats:
        bdual = any(_shear_x(ch) and _scale_xy(ch) for ch in base[qb].get("bones", {}).values())
        if not bdual:
            v1["base_no_dual"].append(qb)
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
                v1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                v1["misrouted"].append((vk, G.beat_category(vk)))
        # Super(g=1)逐位元 == base squash(向後相容)
        if json.dumps(anims.get("{}__Super".format(qb), {}), sort_keys=True) != \
           json.dumps(base[qb], sort_keys=True):
            v1["super_ne_base"].append(qb)
    # base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            v1["base_changed"].append(k)
    v1_pass = (bool(squash_beats) and not any(v1[k] for k in
               ["base_no_dual", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed", "super_ne_base"]))
    R["V1_present_backward_compat"] = {**v1, "pass": v1_pass}

    # ---- V2 crux: dual-axis (shear + aniso) peak monotone across tiers ----
    v2 = {"beats": {}, "fail_shear_mono": [], "fail_aniso_mono": [], "fail_base": []}
    for qb in squash_beats:
        sh_peaks = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        an_peaks = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_sh, base_an = _shear_peak(base[qb]), _aniso_peak(base[qb])
        sh_mono, an_mono = _is_strict_inc(sh_peaks), _is_strict_inc(an_peaks)
        super_eq = abs(sh_peaks[0] - base_sh) <= 1e-4 and abs(an_peaks[0] - base_an) <= 1e-4
        v2["beats"][qb] = {"shear_peaks": [round(p, 3) for p in sh_peaks],
                           "aniso_peaks": [round(p, 4) for p in an_peaks],
                           "base_shear": round(base_sh, 3), "base_aniso": round(base_an, 4),
                           "shear_mono": sh_mono, "aniso_mono": an_mono, "super_eq_base": super_eq}
        if not sh_mono:
            v2["fail_shear_mono"].append(qb)
        if not an_mono:
            v2["fail_aniso_mono"].append(qb)
        if not super_eq:
            v2["fail_base"].append(qb)
    v2_pass = (bool(v2["beats"]) and not v2["fail_shear_mono"]
               and not v2["fail_aniso_mono"] and not v2["fail_base"])
    R["V2_dual_axis_monotone"] = {**v2, "pass": v2_pass}

    # ---- V3 crux: volume conservation preserved at EVERY tier ----
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
    v3_pass = (bool(v3["detail"]) and not v3["bad_volume"]
               and not v3["no_aniso"] and not v3["not_damped"])
    R["V3_volume_preserved_per_tier"] = {**v3, "pass": v3_pass}

    # ---- V4 damped shear signature preserved per tier ----
    v4 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                ends_ok = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                nsc = _sign_changes_zero(sx)
                damp = _extrema_mags_decreasing(sx)
                v4["detail"][key] = {"n_sign_changes": nsc, "damped": damp}
                if not ends_ok:
                    v4["bad_endpoints"].append(key)
                if nsc < 3:
                    v4["few_sign_changes"].append(key)
                if not damp:
                    v4["not_damped"].append(key)
    v4_pass = (bool(v4["detail"]) and not v4["bad_endpoints"]
               and not v4["few_sign_changes"] and not v4["not_damped"])
    R["V4_damped_shear_per_tier"] = {**v4, "pass": v4_pass}

    # ---- V5 negative controls / orthogonality ----
    v5 = {}
    # (a) 平增益守衛:全 1.0 → 兩軸遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_sh_mono_flat, any_an_mono_flat, flat_base_diff = False, False, []
    for qb in squash_beats:
        sh_peaks = [_shear_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        an_peaks = [_aniso_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(sh_peaks):
            any_sh_mono_flat = True
        if _is_strict_inc(an_peaks):
            any_an_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    v5["a_flat_guard"] = {"flat_shear_monotone": any_sh_mono_flat, "flat_aniso_monotone": any_an_mono_flat,
                          "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_sh_mono_flat) and (not any_an_mono_flat) and not flat_base_diff}
    # (b) 耦合必要性單元測(crux 守衛):對真實 squash scale 幀,coupled=True 守恆、coupled=False 破壞
    sq_b, _ = BT.gen_squash("特效", 1.0)   # role 特效:Q=0.16(最深擠壓 → 破壞最明顯)
    interior_base = _interior_scale(sq_b)
    g = 2.10                                # Legend 增益(最大 → 差異最明顯)
    cpl = TV.amplify_bone_tl(sq_b, g, coupled=True)
    nai = TV.amplify_bone_tl(sq_b, g, coupled=False)
    cpl_int = _interior_scale(cpl)
    nai_int = _interior_scale(nai)
    cpl_prod = [round(sx * sy, 5) for (sx, sy) in cpl_int]
    nai_prod = [round(sx * sy, 5) for (sx, sy) in nai_int]
    cpl_vol_ok = all(abs(p - 1.0) <= TOL_VOL for p in cpl_prod)
    nai_vol_broken = any(abs(p - 1.0) > TOL_VOL for p in nai_prod)   # 天真放大**必**破壞守恆
    # 耦合放大量 = g·q:base 首極值 q0=scaleX0−1,耦合後 scaleX0'−1 應 == g·q0
    q0 = interior_base[0][0] - 1.0
    amp_ratio_ok = abs((cpl_int[0][0] - 1.0) - g * q0) <= 1e-4
    # g=1 耦合逐位元 == 原;identity 幀恆 identity
    cpl1 = TV.amplify_bone_tl(sq_b, 1.0, coupled=True)
    g1_identical = json.dumps(cpl1, sort_keys=True) == json.dumps(sq_b, sort_keys=True)
    endpoints_ident = (abs(cpl["scale"][0]["x"] - 1.0) < 1e-9 and abs(cpl["scale"][0]["y"] - 1.0) < 1e-9
                       and abs(cpl["scale"][-1]["x"] - 1.0) < 1e-9 and abs(cpl["scale"][-1]["y"] - 1.0) < 1e-9)
    v5["b_coupling_necessity"] = {
        "coupled_products": cpl_prod, "naive_products": nai_prod,
        "coupled_vol_ok": cpl_vol_ok, "naive_vol_broken": nai_vol_broken,
        "amp_ratio_ok": amp_ratio_ok, "g1_byte_identical": g1_identical,
        "endpoints_identity": endpoints_ident,
        "pass": (cpl_vol_ok and nai_vol_broken and amp_ratio_ok and g1_identical and endpoints_ident)}
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
        for k in ["V1_present_backward_compat", "V2_dual_axis_monotone",
                  "V3_volume_preserved_per_tier", "V4_damped_shear_per_tier", "V5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V2 dual-axis peaks per tier {}:".format(TIERS))
        for qb, d in R["V2_dual_axis_monotone"]["beats"].items():
            print("  {:10s} shear {}  aniso {}".format(qb, d["shear_peaks"], d["aniso_peaks"]))
        b = R["V5_neg_control"]["b_coupling_necessity"]
        print("V5 coupled products {} (vol_ok {}) vs naive {} (broken {})".format(
            b["coupled_products"], b["coupled_vol_ok"], b["naive_products"], b["naive_vol_broken"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
