#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

補 (G-4'''') 的 honest boundary:G-4'''' 讓 `gen_squash` 成為**第一個同時產 shear + 體積守恆非均勻
scale** 的生成器,但當時 squash **不在** `MAIN_SHOW_CATS` —— 因樸素的各軸獨立幅度增益(`_amp_scale`)
會放大拉長軸(scaleX>1)卻保留壓縮軸(scaleY<1)樓地板不動 → **破壞體積守恆**(scaleX·scaleY≠1)。
本次(G-4''''')把 squash 併入 `MAIN_SHOW_CATS` 並新增**耦合 amplify**(`_amp_squash_pair`:放大拉長軸、
壓縮軸取其**倒數** → scaleX·scaleY≡1 面積守恆且仍非均勻),使 **squash 的擠壓幅度與 shear 峰皆隨檔位
嚴格遞增**,同時**體積守恆 + 阻尼振盪簽章在每個檔位保持**(強度變、結構不變)。

真值界定同 (E/H/I/J/G-4'/G-4''/G-4'''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章
(體積守恆 + 兩軸幅度遞增 + 阻尼)非美感**;「愈高檔位擠壓愈爆但仍守恆」是可量化的檔位簽章,用負對照
證鑑別力(**耦合 vs 樸素**:樸素增益破壞守恆)。從**先驗庫** → **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  V1 present + backward-compat    : squash base beat 同時帶 shear+scale;每檔位 `squash__{tier}` 皆產出、
                                   finite、有 bone、≥1 bone **同時**帶 shear 與 scale、名經 `beat_category`
                                   仍路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains 的 base + In/Loop/Out 相同)。
  V2 crux — 體積守恆耦合保持每檔位 : **每個檔位**的 squash bone,每個 shear 極值幀 (a)scaleX·scaleY≈1
                                   (|積−1|≤TOL_VOL,面積守恆);(b)非均勻 |scaleX−scaleY|≥MIN_ANISO;
                                   (c)squash 幅度 |scaleX−1| 隨極值嚴格遞減(阻尼)—— 復用 G-4'''' 的 `_sq3_eval`。
  V3 crux — 兩軸峰隨檔位遞增       : 各檔位 squash 的峰擠壓幅度 max|scaleX−1| **與** 峰 |shearX| 皆
                                   Super<Mega<Omg<Legend **嚴格遞增**(端到端經 build_animations 量),
                                   且首檔(Super,g=1)== base(向後相容);且每檔位阻尼振盪簽章(shear
                                   繞 0 變號≥3 + 相繼極值遞減)保持。
  V4 identity 介面每檔位          : **每個檔位** squash 首尾 shearX==0 且 scale 首尾 (1,1)(可插 Loop 間)。
  V5 neg-control                 : (a) **耦合 vs 樸素(crux 鑑別)**:對同一 squash 極值幀套**樸素**各軸
                                   獨立增益(coupled_scale=False,g=Legend)→ 體積守恆 FALSE(|積−1| 大);
                                   耦合(coupled_scale=True)→ 守恆 TRUE → 證耦合 amplify 必要且閘可辨;
                                   (b) **平增益守衛**:增益全 1.0 → V3 遞增 FALSE 且各檔位 == base;
                                   (c) **耦合單元測**:`_amp_squash_pair` 對 identity (1,1)→(1,1)、對體積守恆對
                                   (1.2,1/1.2) g=2 → 拉長軸 1.4、積≈1、非均勻(證耦合是加性、與守恆一致)。

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
# 復用 G-4' 的 shear 讀取 + 阻尼簽章判準、G-4'''' 的 scale 讀取 + 體積守恆耦合判準(確保跨閘一致)
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import _scale_xy, _interior_scale, _sq3_eval, MIN_ANISO, TOL_VOL, MIN_SHEAR

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


def _squash_mag_peak(anim):
    """該 anim 全 bone 的峰擠壓幅度 max|scaleX−1|(無 scale 回 0)。"""
    peaks = [max(abs(sx - 1.0) for (sx, sy) in _scale_xy(ch)) for ch in anim.get("bones", {}).values()
             if _scale_xy(ch)]
    return max(peaks, default=0.0)


def _shear_peak(anim):
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

    # ---- V1 present + backward-compat ----
    v1 = {"squash_beats": squash_beats, "base_no_dual": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": []}
    for qb in squash_beats:
        dual0 = any(_shear_x(ch) and _scale_xy(ch) for ch in base[qb].get("bones", {}).values())
        if not dual0:
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
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            v1["base_changed"].append(k)
    v1_pass = (bool(squash_beats) and not any(v1[k] for k in
               ["base_no_dual", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed"]))
    R["V1_present_backward_compat"] = {**v1, "pass": v1_pass}

    # ---- V2 crux: volume-preserving coupling preserved per tier ----
    v2 = {"bad_volume": [], "no_aniso": [], "not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior or not _shear_x(ch):
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                vok, aok, dok, det = _sq3_eval(interior)
                v2["detail"][key] = det
                if not vok:
                    v2["bad_volume"].append(key)
                if not aok:
                    v2["no_aniso"].append(key)
                if not dok:
                    v2["not_damped"].append(key)
    v2_pass = (bool(v2["detail"]) and not v2["bad_volume"] and not v2["no_aniso"] and not v2["not_damped"])
    R["V2_volume_preserving_per_tier"] = {**v2, "pass": v2_pass}

    # ---- V3 crux: both squash-magnitude & shear peaks monotone across tiers ----
    v3 = {"beats": {}, "fail_mag_mono": [], "fail_shear_mono": [], "fail_base": [],
          "fail_damped": []}
    for qb in squash_beats:
        mag_peaks = [_squash_mag_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        shr_peaks = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_mag = _squash_mag_peak(base[qb]); base_shr = _shear_peak(base[qb])
        mag_mono = _is_strict_inc(mag_peaks)
        shr_mono = _is_strict_inc(shr_peaks)
        base_ok = abs(mag_peaks[0] - base_mag) <= 1e-4 and abs(shr_peaks[0] - base_shr) <= 1e-4
        # 阻尼簽章每檔位保持(shear 繞 0 變號≥3 + 相繼極值遞減)
        damped_ok = True
        for t in TIERS:
            for ch in anims["{}__{}".format(qb, t)].get("bones", {}).values():
                sx = _shear_x(ch)
                if sx and not (_sign_changes_zero(sx) >= 3 and _extrema_mags_decreasing(sx)):
                    damped_ok = False
        v3["beats"][qb] = {"mag_peaks": [round(p, 4) for p in mag_peaks],
                           "shear_peaks": [round(p, 3) for p in shr_peaks],
                           "base_mag": round(base_mag, 4), "base_shear": round(base_shr, 3),
                           "mag_mono": mag_mono, "shear_mono": shr_mono,
                           "base_ok": base_ok, "damped_ok": damped_ok}
        if not mag_mono:
            v3["fail_mag_mono"].append(qb)
        if not shr_mono:
            v3["fail_shear_mono"].append(qb)
        if not base_ok:
            v3["fail_base"].append(qb)
        if not damped_ok:
            v3["fail_damped"].append(qb)
    v3_pass = (bool(v3["beats"]) and not v3["fail_mag_mono"] and not v3["fail_shear_mono"]
               and not v3["fail_base"] and not v3["fail_damped"])
    R["V3_both_axes_peak_monotone"] = {**v3, "pass": v3_pass}

    # ---- V4 identity interface per tier ----
    v4 = {"shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                key = "{}__{}::{}".format(qb, t, bn)
                sx = _shear_x(ch)
                if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                    v4["shear_endpoints_nonzero"].append(key)
                xy = _scale_xy(ch)
                if xy and (abs(xy[0][0] - 1.0) > 1e-6 or abs(xy[0][1] - 1.0) > 1e-6
                           or abs(xy[-1][0] - 1.0) > 1e-6 or abs(xy[-1][1] - 1.0) > 1e-6):
                    v4["scale_endpoints_nonident"].append(key)
    R["V4_identity_interface_per_tier"] = {**v4, "pass": (not v4["shear_endpoints_nonzero"]
                                                          and not v4["scale_endpoints_nonident"])}

    # ---- V5 negative controls ----
    v5 = {}
    # (a) 耦合 vs 樸素(crux 鑑別):對真實 squash bone 的 scale 通道,套樸素 vs 耦合增益(g=Legend)
    gL = gains["Legend"]
    qb0 = squash_beats[0]
    bn0 = next(bn for bn, ch in base[qb0]["bones"].items() if _shear_x(ch) and _scale_xy(ch))
    ch0 = base[qb0]["bones"][bn0]
    naive = TV.amplify_bone_tl(ch0, gL, coupled_scale=False)
    coupled = TV.amplify_bone_tl(ch0, gL, coupled_scale=True)
    naive_int = _interior_scale(naive)
    coupled_int = _interior_scale(coupled)
    naive_vol_ok = _sq3_eval(naive_int)[0] if naive_int else True
    coupled_vol_ok = _sq3_eval(coupled_int)[0] if coupled_int else False
    naive_max_dev = max((abs(sx * sy - 1.0) for (sx, sy) in naive_int), default=0.0)
    coupled_max_dev = max((abs(sx * sy - 1.0) for (sx, sy) in coupled_int), default=0.0)
    v5["a_coupled_vs_naive"] = {"naive_volume_ok": naive_vol_ok, "coupled_volume_ok": coupled_vol_ok,
                                "naive_max_dev": round(naive_max_dev, 5),
                                "coupled_max_dev": round(coupled_max_dev, 5),
                                "pass": (not naive_vol_ok) and coupled_vol_ok
                                        and naive_max_dev > TOL_VOL}
    # (b) 平增益守衛:全 1.0 → 兩軸峰遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mag_mono_flat, any_shr_mono_flat, flat_base_diff = False, False, []
    for qb in squash_beats:
        if _is_strict_inc([_squash_mag_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]):
            any_mag_mono_flat = True
        if _is_strict_inc([_shear_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]):
            any_shr_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    v5["b_flat_guard"] = {"flat_mag_monotone": any_mag_mono_flat,
                          "flat_shear_monotone": any_shr_mono_flat,
                          "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mag_mono_flat) and (not any_shr_mono_flat)
                                  and not flat_base_diff}
    # (c) 耦合單元測:identity 與體積守恆對
    id_x, id_y = TV._amp_squash_pair(1.0, 1.0, 2.0)
    px, py = TV._amp_squash_pair(1.2, 1.0 / 1.2, 2.0)
    id_ok = abs(id_x - 1.0) <= 1e-9 and abs(id_y - 1.0) <= 1e-9
    stretch_ok = abs(px - 1.4) <= 1e-6                 # 1+2*(1.2-1)=1.4
    vol_ok = abs(px * py - 1.0) <= 1e-9
    aniso_ok = abs(px - py) >= MIN_ANISO
    v5["c_pair_unit"] = {"identity_ok": id_ok, "stretch_ok": stretch_ok, "volume_ok": vol_ok,
                         "aniso_ok": aniso_ok,
                         "pass": id_ok and stretch_ok and vol_ok and aniso_ok}
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
        for k in ["V1_present_backward_compat", "V2_volume_preserving_per_tier",
                  "V3_both_axes_peak_monotone", "V4_identity_interface_per_tier", "V5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V3 peaks per tier {}:".format(TIERS))
        for qb, d in R["V3_both_axes_peak_monotone"]["beats"].items():
            print("  {:8s} mag {}  shear {}  (base mag {} shear {})".format(
                qb, d["mag_peaks"], d["shear_peaks"], d["base_mag"], d["base_shear"]))
        a5 = R["V5_neg_control"]["a_coupled_vs_naive"]
        print("V5(a) coupled vs naive volume dev: naive {} (ok={}) / coupled {} (ok={})".format(
            a5["naive_max_dev"], a5["naive_volume_ok"], a5["coupled_max_dev"], a5["coupled_volume_ok"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
