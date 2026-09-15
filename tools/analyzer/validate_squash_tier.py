#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

candidate (J) 讓主秀 beat 依檔位**幅度**差異化(愈高檔位愈爆),(G-4'') 把 wobble 的 **shear** 峰接上。
但 (G-4'''') 新生成的 squash(斜拉果凍擠壓)其 scale 通道是**體積守恆耦合對**(scaleX·scaleY≡1、
scaleX≠scaleY);天真的 `_amp_scale`(僅放大 identity 上方 overshoot)會把 scaleX>1 放大而 scaleY<1
的壓扁樓地板保留不動 → **破壞體積守恆**(scaleX·scaleY≠1)—— 這正是 (G-4'''') 留下的 honest boundary
(「squash 未在 MAIN_SHOW_CATS」)。本次(G-4''''')以**耦合 amplify**(log 空間 v'=v**g,對 (s,1/s)→
(s**g,(1/s)**g),積 (s·1/s)**g==1 精確守恆)把 squash 併入 `MAIN_SHOW_CATS`,使 **squash 的擠壓幅度
與 shear 峰隨檔位嚴格遞增**,同時**體積守恆 + 阻尼耦合簽章在每個檔位保持**(強度變、結構不變)。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位擠壓愈強」是可量化的檔位簽章。crux 負對照 = 用**天真** `_amp_scale`(coupled_scale=False)
放大 squash → 體積守恆 FALSE:證(a)耦合 amplify 是必要的、(b)本閘對該失敗模式敏感(閘可信)。
從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  ST1 present + backward-compat  : squash base beat 有 shear+scale;每檔位 `squash__{tier}` 皆產出、
                                  finite、有 bone、≥1 bone **同時**帶 shear 與 scale、名經 `beat_category`
                                  仍路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains 的所有 base beat 相同)。
  ST2 crux — magnitude monotone : 各檔位 squash 的擠壓峰 |scaleX−1| **與** shear 峰 |shearX|
                                  Super<Mega<Omg<Legend **嚴格遞增**(端到端經 build_animations 量),
                                  且首檔(Super,g=1)兩者峰 == base 峰(向後相容)。
  ST3 volume-conserv per tier   : **每個檔位**的 squash bone 每個 scale 極值幀 (a)scaleX·scaleY≈1
     (crux)                       (面積守恆,|積−1|≤TOL_VOL);(b)至少一極值非均勻 |scaleX−scaleY|≥MIN_ANISO;
                                  (c)擠壓幅度 |scaleX−1| 隨極值嚴格遞減(阻尼);(d)shear 阻尼振盪
                                  (繞 0 變號 ≥3 + 相繼極值遞減)—— 耦合 amplify 同比放大 → 三簽章保形。
  ST4 identity interface        : **每個檔位** shear 首尾 0 + scale 首尾 (1,1)(可插 Loop 間)。
  ST5 neg-control               : (a) **平增益守衛**:增益全 1.0 → ST2 遞增 FALSE 且各檔位逐位元 == base;
                                  (b) **crux 天真放大守衛**:對 squash beat 改用天真 `_amp_scale`
                                     (coupled_scale=False)→ 高檔位體積守恆 FALSE(證耦合 amplify 必要、
                                      本閘偵測得到破壞);耦合版同資料則守恆 TRUE(對照);
                                  (c) **耦合 amplify 單元測**:`_amp_scale_coupled` 對等比對 (v,v)→仍等比
                                     (不憑空造非均勻)、對體積守恆對 (s,1/s)→積仍==1(log 空間守恆)。

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
# 復用 G-4' 的 shear 讀取與阻尼簽章判準、G-4'''' 的體積守恆耦合判準,確保與 squash-gen / wobble-tier 閘一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import _scale_xy, _interior_scale, _sq3_eval, MIN_ANISO, TOL_VOL

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,base squash 峰值 |shearX| 下限
MIN_STRETCH = 0.05  # base squash 擠壓峰 |scaleX−1| 下限(確有明顯擠壓)


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/squash_tier_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _squash_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "squash"]


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _stretch_peak(anim):
    """該 anim 全 bone 的擠壓峰 max|scaleX−1|(無 scale 回 0)。"""
    peaks = [max(abs(sx - 1.0) for (sx, sy) in _scale_xy(ch))
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

    # ---- ST1 present + backward-compat ----
    t1 = {"squash_beats": squash_beats, "base_weak": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": []}
    for qb in squash_beats:
        if _shear_peak(base[qb]) < MIN_SHEAR or _stretch_peak(base[qb]) < MIN_STRETCH:
            t1["base_weak"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            if not an.get("bones"):
                t1["no_bones"].append(vk)
            if not any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values()):
                t1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                t1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    t1_pass = (bool(squash_beats) and not any(t1[k] for k in
               ["base_weak", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed"]))
    R["ST1_present_backward_compat"] = {**t1, "pass": t1_pass}

    # ---- ST2 crux: stretch & shear peak monotone across tiers ----
    t2 = {"beats": {}, "fail_stretch_mono": [], "fail_shear_mono": [], "fail_base": []}
    for qb in squash_beats:
        st = [_stretch_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        sh = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_st, base_sh = _stretch_peak(base[qb]), _shear_peak(base[qb])
        st_mono, sh_mono = _is_strict_inc(st), _is_strict_inc(sh)
        super_eq = abs(st[0] - base_st) <= 1e-4 and abs(sh[0] - base_sh) <= 1e-4
        t2["beats"][qb] = {"stretch_peaks": [round(x, 4) for x in st],
                           "shear_peaks": [round(x, 3) for x in sh],
                           "base_stretch": round(base_st, 4), "base_shear": round(base_sh, 3),
                           "stretch_mono": st_mono, "shear_mono": sh_mono, "super_eq_base": super_eq}
        if not st_mono:
            t2["fail_stretch_mono"].append(qb)
        if not sh_mono:
            t2["fail_shear_mono"].append(qb)
        if not super_eq:
            t2["fail_base"].append(qb)
    t2_pass = (bool(t2["beats"]) and not t2["fail_stretch_mono"]
               and not t2["fail_shear_mono"] and not t2["fail_base"])
    R["ST2_magnitude_monotone"] = {**t2, "pass": t2_pass}

    # ---- ST3 volume-conservation + coupling signature preserved per tier (crux) ----
    t3 = {"bad_volume": [], "no_aniso": [], "scale_not_damped": [],
          "shear_bad_endpoints": [], "shear_few_sign_changes": [], "shear_not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                sx = _shear_x(ch)
                if not interior or not sx:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                vok, aok, dok, det = _sq3_eval(interior)
                nsc = _sign_changes_zero(sx)
                sh_damp = _extrema_mags_decreasing(sx)
                sh_ends = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                t3["detail"][key] = {**det, "shear_nsc": nsc, "shear_damped": sh_damp}
                if not vok:
                    t3["bad_volume"].append(key)
                if not aok:
                    t3["no_aniso"].append(key)
                if not dok:
                    t3["scale_not_damped"].append(key)
                if not sh_ends:
                    t3["shear_bad_endpoints"].append(key)
                if nsc < 3:
                    t3["shear_few_sign_changes"].append(key)
                if not sh_damp:
                    t3["shear_not_damped"].append(key)
    t3_pass = (bool(t3["detail"]) and not any(t3[k] for k in
               ["bad_volume", "no_aniso", "scale_not_damped",
                "shear_bad_endpoints", "shear_few_sign_changes", "shear_not_damped"]))
    R["ST3_volume_conserv_per_tier"] = {**t3, "pass": t3_pass}

    # ---- ST4 identity interface per tier ----
    t4 = {"shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                    t4["shear_endpoints_nonzero"].append("{}__{}::{}".format(qb, t, bn))
                xy = _scale_xy(ch)
                if xy and (abs(xy[0][0] - 1.0) > 1e-6 or abs(xy[0][1] - 1.0) > 1e-6
                           or abs(xy[-1][0] - 1.0) > 1e-6 or abs(xy[-1][1] - 1.0) > 1e-6):
                    t4["scale_endpoints_nonident"].append("{}__{}::{}".format(qb, t, bn))
    R["ST4_identity_interface"] = {**t4, "pass": (not t4["shear_endpoints_nonzero"]
                                                  and not t4["scale_endpoints_nonident"])}

    # ---- ST5 negative controls ----
    t5 = {}
    # (a) 平增益守衛:全 1.0 → 遞增 FALSE 且各檔位逐位元 == base
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
    t5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}

    # (b) crux 天真放大守衛:同一 base squash beat,天真 `_amp_scale`(coupled_scale=False)vs 耦合。
    #     取 base squash 的 dual-channel bone timeline,對高檔位 g 兩路各放大一次,量體積守恆。
    qb0 = squash_beats[0]
    dual_bn = next((bn for bn, ch in base[qb0]["bones"].items()
                    if _shear_x(ch) and _interior_scale(ch)), None)
    g_hi = gains["Legend"]
    naive = TV.amplify_bone_tl(base[qb0]["bones"][dual_bn], g_hi, coupled_scale=False)
    coup = TV.amplify_bone_tl(base[qb0]["bones"][dual_bn], g_hi, coupled_scale=True)
    naive_prod = [round(sx * sy, 5) for (sx, sy) in _interior_scale(naive)]
    coup_prod = [round(sx * sy, 5) for (sx, sy) in _interior_scale(coup)]
    naive_vok = all(abs(p - 1.0) <= TOL_VOL for p in naive_prod)
    coup_vok = all(abs(p - 1.0) <= TOL_VOL for p in coup_prod)
    t5["b_naive_breaks_conservation"] = {"bone": dual_bn, "g": g_hi,
                                         "naive_prod": naive_prod, "coupled_prod": coup_prod,
                                         "naive_volume_ok": naive_vok, "coupled_volume_ok": coup_vok,
                                         "pass": (not naive_vok) and coup_vok}

    # (c) 耦合 amplify 單元測:等比→仍等比;體積守恆→積仍==1
    g = 2.0
    uni_x, uni_y = TV._amp_scale_coupled(1.2, g), TV._amp_scale_coupled(1.2, g)     # (v,v)
    uni_stays = abs(uni_x - uni_y) <= 1e-12
    s = 1.2
    vc_x, vc_y = TV._amp_scale_coupled(s, g), TV._amp_scale_coupled(1.0 / s, g)     # (s,1/s)
    vc_conserved = abs(vc_x * vc_y - 1.0) <= 1e-9
    ident_fixed = abs(TV._amp_scale_coupled(1.0, g) - 1.0) <= 1e-12
    t5["c_coupled_unit"] = {"uniform_stays_uniform": uni_stays, "vc_product": round(vc_x * vc_y, 9),
                            "vc_conserved": vc_conserved, "identity_fixed": ident_fixed,
                            "pass": uni_stays and vc_conserved and ident_fixed}

    R["ST5_neg_control"] = {**t5, "pass": all(v["pass"] for v in t5.values())}

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
        for k in ["ST1_present_backward_compat", "ST2_magnitude_monotone",
                  "ST3_volume_conserv_per_tier", "ST4_identity_interface", "ST5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("ST2 peaks per tier {}:".format(TIERS))
        for qb, d in R["ST2_magnitude_monotone"]["beats"].items():
            print("  {:8s} stretch {} (base {})  shear {} (base {})".format(
                qb, d["stretch_peaks"], d["base_stretch"], d["shear_peaks"], d["base_shear"]))
        b = R["ST5_neg_control"]["b_naive_breaks_conservation"]
        print("ST5(b) naive prod {} (vol_ok {}) vs coupled prod {} (vol_ok {})".format(
            b["naive_prod"], b["naive_volume_ok"], b["coupled_prod"], b["coupled_volume_ok"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
