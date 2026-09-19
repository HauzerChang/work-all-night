#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

candidate (G-4'''') 讓 `gen_squash` 成為第一個同時產 **shear + 耦合體積守恆非均勻 scale** 的生成器,
但當時 squash **不在** `MAIN_SHOW_CATS` —— 因為 (J) 的幅度增益 `_amp_scale` 逐軸只放大 identity 上方,
squash 的 scaleY<1(壓扁)樓地板會被保留而 scaleX>1 被放大 → **破壞體積守恆(scaleX·scaleY≠1)**,
把「果凍擠壓」變成單軸拉伸。這是 (G-4'''') 明列的 honest boundary。

本次(G-4''''')把 squash 併入 `MAIN_SHOW_CATS`,並讓 scale 通道走**耦合放大**
(`tier_variants._amp_squash_pair`:自 scaleX 還原 squash 量 q、線性放大 q'=g·q、再以生成器同式重建
兩軸 scaleX'=1+q'、scaleY'=1/(1+q'))→ **squash 的兩個幅度軸(shear 峰 + 擠壓量)隨檔位嚴格遞增,
且體積守恆 scaleX·scaleY≡1 在每個檔位保持**(shear 通道同 wobble 走 v'=g·v)。這是又一「檔位機制
就緒 ≠ 每個新通道接上」實例(同 E/H/I/J/G-4'/G-4''),且首次讓**耦合雙通道**同步隨檔位放大。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位愈斜、愈擠」是可量化的檔位簽章,體積守恆是可量化的物理約束,用負對照證鑑別力(閘可信)。
從**先驗庫**(slot_bigwin 已含 squash beat)→ **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  P1 present + backward-compat : squash base beat 為雙通道(有 shear 且有非均勻 scale);每檔位
                                `squash__{tier}` 皆產出、finite、有 bone、≥1 bone **同時**帶 shear 與非均勻
                                scale、名經 `beat_category` 仍路由回 squash;**base 逐位元不變**
                                (帶/不帶 tier_gains 的 base squash + In/Loop/Out 相同)。
  P2 crux — dual-axis monotone : 各檔位 squash 的 (a)峰 |shearX| 與 (b)峰擠壓量 |scaleX−1| 皆
                                Super<Mega<Omg<Legend **嚴格遞增**,且首檔(Super,g=1)兩者皆 == base
                                (向後相容)。→ 耦合雙通道同步隨檔位放大。
  P3 crux — volume + signatures: **每個檔位**的每個 squash bone:(a)**體積守恆**每擠壓幀 |scaleX·scaleY−1|
                                ≤ TOL_VOL(此即 `_amp_scale` 會破壞、耦合放大保住的關鍵);(b)非均勻
                                |scaleX−scaleY| 峰 ≥ MIN_ANISO;(c)擠壓量隨極值嚴格遞減(阻尼耦合);
                                (d)shear 首尾 0 + 繞 0 變號 ≥3 + 相繼極值遞減(阻尼保形);(e)scale 首尾 identity。
  P4 coupling isolated         : 全 storyboard(含所有檔位變體)中,**只有 squash 及其 `__tier`** 同時帶
                                shear 與非均勻 scale;wobble 帶 shear 但無非均勻 scale、其餘主秀等比 scale
                                無 shear → 耦合放大路徑只作用 squash,對其他節拍零外洩。
  P5 neg-control               : (a) **平增益守衛**:增益全 1.0 → P2 兩軸遞增皆 FALSE 且各檔位 squash 逐
                                位元 == base(證閘測遞增非恆真、且 g=1 耦合路徑為精確 identity);
                                (b) **耦合 vs 逐軸單元測(crux)**:對合成體積守恆 squash 對,
                                `_amp_squash_pair`(耦合)放大後 scaleX·scaleY≡1 且擠壓量嚴格遞減;
                                同一對用逐軸 `_amp_scale` 放大 → scaleX·scaleY **明顯 ≠ 1**(守恆破壞)
                                → 證耦合放大確實在做事(此即補上的 honest boundary)。

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
# 復用 G-4'/G-4'''' 的判準,確保與 shear-gen / wobble-tier / squash-gen 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import (_squash_beats, _scale_xy, _interior_scale, _sq3_eval,
                                 _has_aniso_scale, MIN_SHEAR, MIN_ANISO, TOL_VOL)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
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


def _shear_peak(anim):
    """該 anim 全 bone 的峰 |shearX|(無 shear 回 0)。"""
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _squash_peak(anim):
    """該 anim 全 bone 的峰擠壓量 max|scaleX−1|(無 scale 回 0)。"""
    peaks = []
    for ch in anim.get("bones", {}).values():
        xy = _scale_xy(ch)
        if xy:
            peaks.append(max(abs(sx - 1.0) for (sx, _sy) in xy))
    return max(peaks, default=0.0)


def _is_strict_inc(xs):
    return all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def _is_dual(anim):
    """該 anim 是否 ≥1 bone **同時**帶 shear 與非均勻 scale(squash 雙通道簽章)。"""
    for ch in anim.get("bones", {}).values():
        if _shear_x(ch) and _has_aniso_scale(ch):
            return True
    return False


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                       # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)    # 帶檔位
    squash_beats = _squash_beats(base)
    R = {}

    # ---- P1 present + backward-compat ----
    p1 = {"squash_beats": squash_beats, "base_not_dual": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_not_dual": [], "misrouted": [], "base_changed": []}
    for qb in squash_beats:
        if not _is_dual(base[qb]):
            p1["base_not_dual"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                p1["missing"].append(vk); continue
            if not SA.all_finite(an):
                p1["not_finite"].append(vk)
            if not an.get("bones"):
                p1["no_bones"].append(vk)
            if not _is_dual(an):
                p1["variant_not_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                p1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            p1["base_changed"].append(k)
    p1_pass = (bool(squash_beats) and not any(p1[k] for k in
               ["base_not_dual", "missing", "not_finite", "no_bones", "variant_not_dual",
                "misrouted", "base_changed"]))
    R["P1_present_backward_compat"] = {**p1, "pass": p1_pass}

    # ---- P2 crux: dual-axis (shear peak + squash amount) monotone across tiers ----
    p2 = {"beats": {}, "fail_shear_mono": [], "fail_shear_base": [],
          "fail_squash_mono": [], "fail_squash_base": []}
    for qb in squash_beats:
        sh_peaks = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        sq_peaks = [_squash_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        sh_base = _shear_peak(base[qb])
        sq_base = _squash_peak(base[qb])
        sh_mono, sq_mono = _is_strict_inc(sh_peaks), _is_strict_inc(sq_peaks)
        sh_eq = abs(sh_peaks[0] - sh_base) <= 1e-4
        sq_eq = abs(sq_peaks[0] - sq_base) <= 1e-4
        p2["beats"][qb] = {"shear_peaks": [round(p, 3) for p in sh_peaks], "shear_base": round(sh_base, 3),
                           "squash_peaks": [round(p, 4) for p in sq_peaks], "squash_base": round(sq_base, 4),
                           "shear_mono": sh_mono, "squash_mono": sq_mono,
                           "super_eq_base": {"shear": sh_eq, "squash": sq_eq}}
        if not sh_mono:
            p2["fail_shear_mono"].append(qb)
        if not sh_eq:
            p2["fail_shear_base"].append(qb)
        if not sq_mono:
            p2["fail_squash_mono"].append(qb)
        if not sq_eq:
            p2["fail_squash_base"].append(qb)
    p2_pass = (bool(p2["beats"]) and not p2["fail_shear_mono"] and not p2["fail_shear_base"]
               and not p2["fail_squash_mono"] and not p2["fail_squash_base"])
    R["P2_dual_axis_monotone"] = {**p2, "pass": p2_pass}

    # ---- P3 crux: volume conservation + damped signatures preserved per tier ----
    p3 = {"vol_broken": [], "not_aniso": [], "scale_not_damped": [], "bad_scale_ends": [],
          "shear_bad_ends": [], "shear_few_sign": [], "shear_not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                xy = _scale_xy(ch)
                if not sx and not xy:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                # scale: 體積守恆 + 非均勻 + 阻尼(去首尾 identity 端點的內部擠壓幀)
                interior = _interior_scale(ch)
                vol_ok, aniso_ok, damp_ok, sc_detail = _sq3_eval(interior)
                ends_scale_ok = (not xy) or (abs(xy[0][0] - 1.0) < 1e-6 and abs(xy[0][1] - 1.0) < 1e-6
                                             and abs(xy[-1][0] - 1.0) < 1e-6 and abs(xy[-1][1] - 1.0) < 1e-6)
                # shear: 阻尼振盪簽章(同 wobble)
                ends_shear_ok = (not sx) or (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6)
                nsc = _sign_changes_zero(sx) if sx else 0
                sh_damp = _extrema_mags_decreasing(sx) if sx else True
                p3["detail"][key] = {**sc_detail, "n_sign_changes": nsc,
                                     "vol_ok": vol_ok, "aniso_ok": aniso_ok, "sc_damped": damp_ok,
                                     "shear_damped": sh_damp}
                if interior and not vol_ok:
                    p3["vol_broken"].append(key)
                if interior and not aniso_ok:
                    p3["not_aniso"].append(key)
                if interior and not damp_ok:
                    p3["scale_not_damped"].append(key)
                if not ends_scale_ok:
                    p3["bad_scale_ends"].append(key)
                if not ends_shear_ok:
                    p3["shear_bad_ends"].append(key)
                if sx and nsc < 3:
                    p3["shear_few_sign"].append(key)
                if sx and not sh_damp:
                    p3["shear_not_damped"].append(key)
    p3_pass = (bool(p3["detail"]) and not any(p3[k] for k in
               ["vol_broken", "not_aniso", "scale_not_damped", "bad_scale_ends",
                "shear_bad_ends", "shear_few_sign", "shear_not_damped"]))
    R["P3_volume_and_signatures"] = {**p3, "pass": p3_pass}

    # ---- P4 coupling (shear + non-uniform scale) isolated to squash ----
    p4 = {"leaked": []}
    for nm, an in anims.items():
        base_name = nm.split("__")[0]
        if G.beat_category(base_name) == "squash":
            continue
        if _is_dual(an):    # 非 squash 卻同時帶 shear + 非均勻 scale → 耦合外洩
            p4["leaked"].append(nm)
    R["P4_coupling_isolated"] = {**p4, "pass": not p4["leaked"]}

    # ---- P5 negative controls ----
    p5 = {}
    # (a) 平增益守衛:全 1.0 → 兩軸遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_sh_mono, any_sq_mono, flat_base_diff = False, False, []
    for qb in squash_beats:
        sh = [_shear_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        sq = [_squash_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(sh):
            any_sh_mono = True
        if _is_strict_inc(sq):
            any_sq_mono = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    p5["a_flat_guard"] = {"flat_shear_monotone": any_sh_mono, "flat_squash_monotone": any_sq_mono,
                          "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_sh_mono) and (not any_sq_mono) and not flat_base_diff}
    # (b) 耦合 vs 逐軸單元測(crux):合成體積守恆 squash 對,g=2.0
    g = 2.0
    Q = [0.16, 0.08, 0.04, 0.02]                 # 阻尼遞減擠壓量(同 gen_squash r=0.5)
    pairs = [(round(1.0 + q, 4), round(1.0 / (1.0 + q), 4)) for q in Q]
    coupled = [TV._amp_squash_pair(sx, sy, g) for (sx, sy) in pairs]
    naive = [(round(TV._amp_scale(sx, g), 4), round(TV._amp_scale(sy, g), 4)) for (sx, sy) in pairs]
    coupled_prod = [round(sx * sy, 6) for (sx, sy) in coupled]
    naive_prod = [round(sx * sy, 6) for (sx, sy) in naive]
    coupled_vol_ok = all(abs(p - 1.0) <= TOL_VOL for p in coupled_prod)
    naive_vol_broken = any(abs(p - 1.0) > 0.05 for p in naive_prod)   # 逐軸明顯破壞守恆
    coupled_mag = [abs(sx - 1.0) for (sx, _sy) in coupled]
    coupled_damped = all(coupled_mag[i + 1] < coupled_mag[i] - 1e-9 for i in range(len(coupled_mag) - 1))
    coupled_amplified = coupled_mag[0] > (pairs[0][0] - 1.0) + 1e-9   # 擠壓量確被放大
    p5["b_coupled_vs_naive"] = {"pairs": pairs, "coupled": coupled, "coupled_prod": coupled_prod,
                                "naive": naive, "naive_prod": naive_prod,
                                "coupled_vol_ok": coupled_vol_ok, "naive_vol_broken": naive_vol_broken,
                                "coupled_damped": coupled_damped, "coupled_amplified": coupled_amplified,
                                "pass": (coupled_vol_ok and naive_vol_broken and coupled_damped
                                         and coupled_amplified)}
    R["P5_neg_control"] = {**p5, "pass": all(v["pass"] for v in p5.values())}

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
        for k in ["P1_present_backward_compat", "P2_dual_axis_monotone",
                  "P3_volume_and_signatures", "P4_coupling_isolated", "P5_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("P2 dual-axis per tier {}:".format(TIERS))
        for qb, d in R["P2_dual_axis_monotone"]["beats"].items():
            print("  {:10s} shear {} squash {} (base sh {} sq {})".format(
                qb, d["shear_peaks"], d["squash_peaks"], d["shear_base"], d["squash_base"]))
        pb = R["P5_neg_control"]["b_coupled_vs_naive"]
        print("P5(b) coupled prod {} | naive prod {}".format(pb["coupled_prod"], pb["naive_prod"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
