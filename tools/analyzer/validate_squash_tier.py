#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

candidate (J) 讓主秀 beat 依檔位**幅度**差異化,(G-4'') 讓 wobble 的 **shear** 峰隨檔位遞增,但 squash
(G-4'''' 的斜拉果凍**擠壓**:shearX 阻尼擺 + 耦合體積守恆 scale,scaleX·scaleY==1 且 scaleX≠scaleY)
一直**不在** `MAIN_SHOW_CATS` —— 因通用幅度增益 `_amp_scale` 只放大 identity 上方 overshoot(scaleX>1 放大、
scaleY<1 樓地板不動)會**破壞體積守恆**。這是「檔位機制就緒 ≠ 每個新通道接上」的又一缺口(同 E/H/I/J/G-4'/'')。

本次(G-4''''')把 squash 併入 `MAIN_SHOW_CATS`,並讓 `amplify_bone_tl(coupled_scale=True)` 對 squash 的
scale 通道走**體積守恆耦合放大**(`_amp_scale_coupled`:保乘積 sx·sy、只把非均勻比 sx/sy 以 g 次方放大)
+ shear 通道照 g*v 放大 → squash 的**兩個耦合通道(shear 峰 + scale 擠壓非均勻)皆隨檔位嚴格遞增**,
**而體積守恆(scaleX·scaleY==1)在每個檔位保持**(強度變、面積守恆的結構簽章不變 —— 誠實地:檔位=更斜更擠,
非別種運動、非「越擠越膨脹」)。

真值界定同 (E/H/I/J/G-4'/''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位擠壓愈強且面積恆守恆」是可量化的檔位簽章,用負對照證鑑別力(閘可信 —— 尤其負對照 V5b 直接證
通用 `_amp_scale` 會破壞體積守恆、故耦合放大是必要)。從**先驗庫** → **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  V1 present + backward-compat : squash base beat 同時帶 shear + 非均勻 scale;每檔位 `squash__{tier}` 皆
                                產出、finite、有 bone、≥1 bone **同時**帶 shear 與 scale 通道、名經
                                `beat_category` 仍路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains)。
  V2 crux — dual-channel monotone: 各檔位 squash 的 (a) 峰 |shearX| 與 (b) scale 非均勻峰 max|scaleX−scaleY|
                                **皆** Super<Mega<Omg<Legend 嚴格遞增(端到端經 build_animations 量),
                                且首檔(Super,g=1)兩者峰 == base 峰(向後相容)。→ 兩耦合通道一起變強。
  V3 crux — volume conserved   : **每個檔位**、**每個** squash bone、**每個** scale 關鍵幀:|scaleX·scaleY−1|
                                ≤ TOL_VOL(面積守恆)。→ 耦合放大在所有檔位保持體積守恆(通用 overshoot
                                放大會在此崩掉,見 V5b 負對照)。
  V4 signature kept per tier   : **每個檔位**的 squash bone 仍 (a) shearX 首尾 0 + 繞 0 變號 ≥3 + 相繼極值
                                嚴格遞減(阻尼);(b) scale 首尾 (1,1)(identity 介面);(c) squash 幅度
                                |scaleX−1| 隨極值嚴格遞減(耦合阻尼保形)。
  V5 neg-control               : (a) **平增益守衛**:增益全 1.0 → V2 兩通道遞增皆 FALSE 且各檔位 squash
                                逐位元 == base;
                                (b) **耦合必要性守衛(crux 誠實)**:對合成 squash 極值 (1.16, 0.8621) 施
                                g=2.1 —— 通用 `_amp_scale`(overshoot-only)→ scaleX·scaleY **偏離 1**
                                (|積−1| > TOL_VOL,體積守恆**破壞**);`_amp_scale_coupled` → 體積守恆
                                (|積−1| ≤ TOL_VOL)。證體積守恆判準有牙且耦合放大是必要(非可有可無)。
                                (c) **通道隔離**:`amplify_bone_tl(coupled_scale=True)` 對「只有 scale」bone →
                                scale 耦合放大(乘積守恆)、不生 shear 鍵;對「只有 shear」bone → shear 放大
                                g*v、不生 scale 鍵。

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
# 復用 G-4' 阻尼簽章判準與 G-4'''' 的 scale/體積判準,確保與既有 shear/squash 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import (_scale_xy, _interior_scale, _sq3_eval,
                                 TOL_VOL, MIN_ANISO, MIN_SHEAR)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4


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
    """該 anim 全 bone 的峰 |shearX|(無 shear 回 0)。"""
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _aniso_peak(anim):
    """該 anim 全 bone 的 scale 非均勻峰 max|scaleX−scaleY|(無 scale 回 0)。"""
    peaks = []
    for ch in anim.get("bones", {}).values():
        xy = _scale_xy(ch)
        if xy:
            peaks.append(max(abs(sx - sy) for (sx, sy) in xy))
    return max(peaks, default=0.0)


def _worst_volume_err(anim):
    """該 anim 全 bone 全 scale 關鍵幀的最差 |scaleX·scaleY − 1|(無 scale 回 0)。"""
    worst = 0.0
    for ch in anim.get("bones", {}).values():
        for (sx, sy) in _scale_xy(ch):
            worst = max(worst, abs(sx * sy - 1.0))
    return worst


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
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": []}
    for qb in squash_beats:
        # base squash 需同時帶 shear(峰≥MIN_SHEAR)與非均勻 scale(峰≥MIN_ANISO)
        if _shear_peak(base[qb]) < MIN_SHEAR or _aniso_peak(base[qb]) < MIN_ANISO:
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
            # ≥1 bone 同時帶 shear 與 scale 通道
            dual = any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values())
            if not dual:
                v1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                v1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:                              # base(含 In/Loop/Out + base squash)逐位元不變
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            v1["base_changed"].append(k)
    v1_pass = (bool(squash_beats) and not any(v1[k] for k in
               ["base_no_dual", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed"]))
    R["V1_present_backward_compat"] = {**v1, "pass": v1_pass}

    # ---- V2 crux: dual-channel monotone (shear peak + scale anisotropy) ----
    v2 = {"beats": {}, "fail_shear_mono": [], "fail_aniso_mono": [], "fail_base": []}
    for qb in squash_beats:
        sh_peaks = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        an_peaks = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_sh, base_an = _shear_peak(base[qb]), _aniso_peak(base[qb])
        sh_mono, an_mono = _is_strict_inc(sh_peaks), _is_strict_inc(an_peaks)
        base_ok = abs(sh_peaks[0] - base_sh) <= 1e-4 and abs(an_peaks[0] - base_an) <= 1e-4
        v2["beats"][qb] = {"shear_peaks": [round(p, 3) for p in sh_peaks],
                           "aniso_peaks": [round(p, 4) for p in an_peaks],
                           "base_shear": round(base_sh, 3), "base_aniso": round(base_an, 4),
                           "shear_mono": sh_mono, "aniso_mono": an_mono, "super_eq_base": base_ok}
        if not sh_mono:
            v2["fail_shear_mono"].append(qb)
        if not an_mono:
            v2["fail_aniso_mono"].append(qb)
        if not base_ok:
            v2["fail_base"].append(qb)
    v2_pass = (bool(v2["beats"]) and not v2["fail_shear_mono"]
               and not v2["fail_aniso_mono"] and not v2["fail_base"])
    R["V2_dual_channel_monotone"] = {**v2, "pass": v2_pass}

    # ---- V3 crux: volume conserved per tier ----
    v3 = {"worst_by_variant": {}, "violations": []}
    for qb in squash_beats:
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            worst = _worst_volume_err(anims[vk])
            v3["worst_by_variant"][vk] = round(worst, 6)
            if worst > TOL_VOL:
                v3["violations"].append((vk, round(worst, 6)))
    v3_pass = bool(v3["worst_by_variant"]) and not v3["violations"]
    R["V3_volume_conserved"] = {**v3, "tol": TOL_VOL, "pass": v3_pass}

    # ---- V4 signature preserved per tier (shear damped + scale identity + squash damped) ----
    v4 = {"bad_shear_ends": [], "few_sign_changes": [], "shear_not_damped": [],
          "bad_scale_ends": [], "squash_not_damped": [], "no_aniso": []}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                xy = _scale_xy(ch)
                key = "{}__{}::{}".format(qb, t, bn)
                if sx:
                    if not (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6):
                        v4["bad_shear_ends"].append(key)
                    if _sign_changes_zero(sx) < 3:
                        v4["few_sign_changes"].append(key)
                    if not _extrema_mags_decreasing(sx):
                        v4["shear_not_damped"].append(key)
                if xy:
                    # scale 首尾 identity (1,1)
                    if not (abs(xy[0][0] - 1.0) < 1e-4 and abs(xy[0][1] - 1.0) < 1e-4
                            and abs(xy[-1][0] - 1.0) < 1e-4 and abs(xy[-1][1] - 1.0) < 1e-4):
                        v4["bad_scale_ends"].append(key)
                    interior = _interior_scale(ch)
                    _, aniso_ok, damped_ok, _ = _sq3_eval(interior)
                    if not aniso_ok:
                        v4["no_aniso"].append(key)
                    if not damped_ok:
                        v4["squash_not_damped"].append(key)
    v4_pass = not any(v4[k] for k in v4)
    R["V4_signature_per_tier"] = {**v4, "pass": v4_pass}

    # ---- V5 negative controls ----
    v5 = {}
    # (a) 平增益守衛:全 1.0 → 兩通道遞增皆 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_sh_mono, any_an_mono, flat_base_diff = False, False, []
    for qb in squash_beats:
        sh = [_shear_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        an = [_aniso_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(sh):
            any_sh_mono = True
        if _is_strict_inc(an):
            any_an_mono = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    v5["a_flat_guard"] = {"flat_shear_monotone": any_sh_mono, "flat_aniso_monotone": any_an_mono,
                          "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_sh_mono) and (not any_an_mono) and not flat_base_diff}
    # (b) 耦合必要性守衛:通用 _amp_scale 破壞體積守恆、_amp_scale_coupled 守恆(證判準有牙 + 耦合必要)
    g = 2.1
    sx0, sy0 = 1.16, 0.8621   # 合成 squash 極值(scaleX·scaleY≈1)
    naive_x = round(TV._amp_scale(sx0, g), 4)
    naive_y = round(TV._amp_scale(sy0, g), 4)   # sy0<1 → 樓地板不動
    naive_err = abs(naive_x * naive_y - 1.0)
    cpl_x, cpl_y = TV._amp_scale_coupled(sx0, sy0, g)
    cpl_err = abs(cpl_x * cpl_y - 1.0)
    v5["b_coupled_necessity"] = {"naive": [naive_x, naive_y], "naive_vol_err": round(naive_err, 6),
                                 "coupled": [cpl_x, cpl_y], "coupled_vol_err": round(cpl_err, 6),
                                 "pass": naive_err > TOL_VOL and cpl_err <= TOL_VOL}
    # (c) 通道隔離單元測:amplify_bone_tl(coupled_scale=True) 對 scale-only / shear-only bone
    scale_only = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0}, {"time": 0.4, "x": 1.16, "y": 0.8621},
                            {"time": 1.0, "x": 1.0, "y": 1.0}]}
    shear_only = {"shear": [{"time": 0.0, "x": 0.0, "y": 0.0}, {"time": 0.4, "x": 12.0, "y": 0.0},
                            {"time": 1.0, "x": 0.0, "y": 0.0}]}
    a_sc = TV.amplify_bone_tl(scale_only, g, coupled_scale=True)
    a_sh = TV.amplify_bone_tl(shear_only, g, coupled_scale=True)
    sc_no_shear = "shear" not in a_sc
    sc_vol_ok = abs(a_sc["scale"][1]["x"] * a_sc["scale"][1]["y"] - 1.0) <= TOL_VOL
    sc_stretched = a_sc["scale"][1]["x"] > sx0 + 1e-6            # 擠壓變強(耦合放大)
    sh_no_scale = "scale" not in a_sh
    sh_amplified = abs(a_sh["shear"][1]["x"] - g * 12.0) <= 1e-6  # v'=g*v
    v5["c_channel_isolation"] = {"scale_only_no_shear": sc_no_shear, "scale_vol_conserved": sc_vol_ok,
                                 "scale_stretched": sc_stretched, "shear_only_no_scale": sh_no_scale,
                                 "shear_amplified": sh_amplified,
                                 "pass": sc_no_shear and sc_vol_ok and sc_stretched and sh_no_scale
                                 and sh_amplified}
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
                  "V3_volume_conserved", "V4_signature_per_tier", "V5_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V2 per tier {}:".format(TIERS))
        for qb, d in R["V2_dual_channel_monotone"]["beats"].items():
            print("  {:10s} shear {} aniso {} (base shear {} aniso {})".format(
                qb, d["shear_peaks"], d["aniso_peaks"], d["base_shear"], d["base_aniso"]))
        print("V3 worst |scaleX·scaleY−1| per variant (tol {}):".format(TOL_VOL))
        for vk, w in R["V3_volume_conserved"]["worst_by_variant"].items():
            print("  {:22s} {:.2e}".format(vk, w))
        print("V5b coupled necessity: naive_vol_err {} vs coupled_vol_err {}".format(
            R["V5_neg_control"]["b_coupled_necessity"]["naive_vol_err"],
            R["V5_neg_control"]["b_coupled_necessity"]["coupled_vol_err"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
