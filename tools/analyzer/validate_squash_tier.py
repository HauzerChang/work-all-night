#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

一路的 honest boundary:G-4''''(`validate_squash_gen.py`)讓 `gen_squash` 成為第一個同時產出
**耦合 shear + 體積守恆非均勻 scale**(scaleX·scaleY==1)的生成器,但它一直被擋在 `MAIN_SHOW_CATS`
**之外** —— 因為 (J) 的 per-axis `_amp_scale` 只放大 identity 上方(scaleX>1 被放大)、下方樓地板
不動(scaleY<1 不變)→ 會**破壞體積守恆**(scaleX·scaleY≠1)。本次(G-4''''')補上**耦合 amplify**
(`tier_variants._amp_scale_coupled`:放大拉長軸偏移 q→g·q、另一軸取倒數保 scaleX·scaleY≡1),
使 squash 可安全併入 MAIN_SHOW_CATS:**squash 的擠壓/斜拉強度隨檔位嚴格遞增,而體積守恆與阻拉振盪
簽章在每個檔位保持**(強度變、結構不變 —— 誠實地:檔位=更擠更斜,非別種運動)。

**又一「檔位機制就緒 ≠ 每個新通道接上」實例**(同 J/G-4''/G-4'''):(J) 幅度增益、(G-4'') 讓
wobble 的 shear 隨檔位放大、(G-4''') wobble 段數隨檔位;本次是**耦合 scale**(體積守恆的非均勻
squash)隨檔位放大 —— per-axis 放大會破壞守恆,故需**專屬的耦合 amplify** 才接得上。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章
(體積守恆耦合 + 阻尼振盪)+ 端到端不動點**非美感;負對照證鑑別力(閘可信)。從**先驗庫** →
**真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  X1 present + backward-compat : squash base beat dual-channel(帶 shear 且非均勻 scale);每檔位
                                `squash__{tier}` 皆產出、finite、有 bone、≥1 bone 同時帶 shear+scale、
                                名經 `beat_category` 仍路由回 squash;**base 逐位元不變**(帶/不帶
                                tier_gains 的 base squash + In/Loop/Out 相同)。
  X2 crux — stretch↑ + volume : 各檔位 squash 的**拉長峰** max|scaleX−1| 與**shear 峰** |shearX|
                                Super<Mega<Omg<Legend **嚴格遞增**(端到端經 build_animations 量),
                                Super==base;**且每個檔位每個極值幀 scaleX·scaleY≈1(體積守恆不被
                                檔位破壞)** —— 這正是耦合 amplify 補上、per-axis 做不到的關鍵。
  X3 coupling+damped per tier : **每個檔位**的 squash bone 仍(a)shear 阻尼振盪(繞 0 變號 ≥3 +
                                相繼極值嚴格遞減);(b)體積守恆耦合(SQ3:每極值積≈1、≥1 極值非均勻、
                                squash 幅度隨極值嚴格遞減)—— 復用 G-4'/G-4'''' 判準,逐檔位保形。
  X4 end-to-end pivot-fixed   : `build_spine --tier-variants --shear-pivot`(真實 robot)產出
                                `squash__{tier}` 帶補償;放大後(Legend)凡有關節 pivot 的 bone,
                                pivot 殘差 < TOL_FIX;內建負對照 = 未補償(繞件中心)大位移 →
                                證放大後的一般仿射(耦合非均勻 scale + shear)仍精確錨在 pivot。
  X5 neg-control              : (a)**平增益守衛**:增益全 1.0 → X2 遞增 FALSE(證閘測遞增非恆真)
                                且各檔位 squash 峰 == base;(b)**耦合 vs per-axis 單元測**:對合成
                                squash scale 幀,`amplify_bone_tl(coupled_scale=True)` 保 scaleX·scaleY≈1
                                且放大拉長峰,而 `coupled_scale=False`(per-axis `_amp_scale`)**破壞守恆**
                                (積≠1)—— 證耦合 amplify 是本次補上的關鍵、亦證閘測的是「守恆下放大」。

用法:
  python3 validate_squash_tier.py            # 摘要
  python3 validate_squash_tier.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
# 復用 G-4' 的 shear 讀取與阻尼簽章判準、G-4'''' 的體積守恆耦合判準 → 與 squash-gen / wobble-tier 閘一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import _scale_xy, _interior_scale, _sq3_eval, _has_aniso_scale
from validate_shear_pivot import _world   # 真實 Spine local(含 shear + 非均勻 scale)世界座標求值

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,base squash 峰值下限
MIN_STRETCH = 0.05  # base squash 拉長峰 |scaleX−1| 下限
TOL_VOL = 0.02      # 體積守恆 |scaleX·scaleY − 1| 上限(實測 <5e-5 → 巨大餘裕;同 squash-gen)
TOL_FIX = 0.5       # px,pivot 不動點殘差上限(同 G-4/G-4'/G-4'''')
MIN_NEG = 5.0       # px,X4 負對照(未補償)位移下限
NEG_RATIO = 20.0    # 負對照/不動點 位移比下限


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
    """該 anim 全 bone 的拉長峰 max|scaleX−1|(無 scale 回 0)。"""
    peaks = [max(abs(sx - 1.0) for (sx, sy) in _scale_xy(ch))
             for ch in anim.get("bones", {}).values() if _scale_xy(ch)]
    return max(peaks, default=0.0)


def _is_strict_inc(xs):
    return all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _worst_volume(anim):
    """該 anim 全 bone 全內部極值幀的最差 |scaleX·scaleY − 1|(無內部極值回 0)。"""
    worst = 0.0
    for ch in anim.get("bones", {}).values():
        for (sx, sy) in _interior_scale(ch):
            worst = max(worst, abs(sx * sy - 1.0))
    return worst


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                       # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)    # 帶檔位
    squash_beats = _squash_beats(base)
    R = {}

    # ---- X1 present + backward-compat ----
    x1 = {"squash_beats": squash_beats, "base_weak": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": []}
    for qb in squash_beats:
        if _shear_peak(base[qb]) < MIN_SHEAR or _stretch_peak(base[qb]) < MIN_STRETCH:
            x1["base_weak"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                x1["missing"].append(vk); continue
            if not SA.all_finite(an):
                x1["not_finite"].append(vk)
            if not an.get("bones"):
                x1["no_bones"].append(vk)
            if not any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values()):
                x1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                x1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:      # base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            x1["base_changed"].append(k)
    x1_pass = (bool(squash_beats) and not any(x1[k] for k in
               ["base_weak", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed"]))
    R["X1_present_backward_compat"] = {**x1, "pass": x1_pass}

    # ---- X2 crux: stretch & shear peak monotone + volume conserved per tier ----
    x2 = {"beats": {}, "fail_stretch_mono": [], "fail_shear_mono": [],
          "fail_super_base": [], "fail_volume": []}
    for qb in squash_beats:
        st = [_stretch_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        sh = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        vol = [_worst_volume(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_st, base_sh = _stretch_peak(base[qb]), _shear_peak(base[qb])
        st_mono, sh_mono = _is_strict_inc(st), _is_strict_inc(sh)
        super_eq = abs(st[0] - base_st) <= 1e-4 and abs(sh[0] - base_sh) <= 1e-4
        vol_ok = all(v <= TOL_VOL for v in vol)
        x2["beats"][qb] = {"stretch_peaks": [round(x, 4) for x in st],
                           "shear_peaks": [round(x, 3) for x in sh],
                           "worst_volume_dev": [round(v, 6) for v in vol],
                           "base_stretch": round(base_st, 4), "base_shear": round(base_sh, 3),
                           "stretch_mono": st_mono, "shear_mono": sh_mono,
                           "super_eq_base": super_eq, "volume_ok": vol_ok}
        if not st_mono:
            x2["fail_stretch_mono"].append(qb)
        if not sh_mono:
            x2["fail_shear_mono"].append(qb)
        if not super_eq:
            x2["fail_super_base"].append(qb)
        if not vol_ok:
            x2["fail_volume"].append(qb)
    x2_pass = (bool(x2["beats"]) and not x2["fail_stretch_mono"] and not x2["fail_shear_mono"]
               and not x2["fail_super_base"] and not x2["fail_volume"])
    R["X2_stretch_shear_monotone_volume"] = {**x2, "pass": x2_pass}

    # ---- X3 coupling + damped signature preserved per tier ----
    x3 = {"bad_shear_endpoints": [], "few_sign_changes": [], "shear_not_damped": [],
          "bad_volume": [], "no_aniso": [], "scale_not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                interior = _interior_scale(ch)
                if not sx or not interior:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                ends_ok = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                nsc = _sign_changes_zero(sx)
                sh_damp = _extrema_mags_decreasing(sx)
                vok, aok, sc_damp, det = _sq3_eval(interior)
                x3["detail"][key] = {"n_sign_changes": nsc, "shear_damped": sh_damp,
                                     "volume_ok": vok, "aniso_ok": aok, "scale_damped": sc_damp}
                if not ends_ok:
                    x3["bad_shear_endpoints"].append(key)
                if nsc < 3:
                    x3["few_sign_changes"].append(key)
                if not sh_damp:
                    x3["shear_not_damped"].append(key)
                if not vok:
                    x3["bad_volume"].append(key)
                if not aok:
                    x3["no_aniso"].append(key)
                if not sc_damp:
                    x3["scale_not_damped"].append(key)
    x3_pass = (bool(x3["detail"]) and not any(x3[k] for k in
               ["bad_shear_endpoints", "few_sign_changes", "shear_not_damped",
                "bad_volume", "no_aniso", "scale_not_damped"]))
    R["X3_coupling_damped_per_tier"] = {**x3, "pass": x3_pass}

    # ---- X4 end-to-end general-affine pivot-fixed for amplified tier variants ----
    import build_spine
    out = "/tmp/squash_tier_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True, tier_variants=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    variant_beats = [nm for nm in sp_skel["animations"]
                     if "__" in nm and G.beat_category(nm.split("__")[0]) == "squash"]
    x4 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0,
          "variant_beats": sorted(variant_beats)}
    for qb in variant_beats:
        an = sp_skel["animations"][qb]
        for bn, ch in an.get("bones", {}).items():
            if bn not in joints or bn not in centers:
                continue
            O = np.array(centers[bn], float); P = np.array(joints[bn], float)
            ellP = P - O
            tr = ch.get("translate")
            if not tr:
                continue
            x4["n_joint_bones"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"bone": bn, "beat": qb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            x4["checked"].append(rec)
            if not (fix < TOL_FIX):
                x4["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                x4["fail_negctrl"].append(rec)
    x4_pass = (x4["n_joint_bones"] >= 1 and not x4["fail_fixed"] and not x4["fail_negctrl"])
    R["X4_end2end_pivot_fixed"] = {**x4, "pass": x4_pass}

    # ---- X5 negative controls ----
    x5 = {}
    # (a) 平增益守衛:全 1.0 → 峰不遞增 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_diff = False, []
    for qb in squash_beats:
        st = [_stretch_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(st):
            any_mono_flat = True
        base_st, base_sh = _stretch_peak(base[qb]), _shear_peak(base[qb])
        for t in TIERS:
            fst = _stretch_peak(flat_anims["{}__{}".format(qb, t)])
            fsh = _shear_peak(flat_anims["{}__{}".format(qb, t)])
            if abs(fst - base_st) > 1e-4 or abs(fsh - base_sh) > 1e-4:
                flat_diff.append("{}__{}".format(qb, t))
    x5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_peaks_ne_base": flat_diff,
                          "pass": (not any_mono_flat) and not flat_diff}
    # (b) 耦合 vs per-axis 單元測:合成 squash scale 幀
    g = 2.0
    q = 0.16
    sx0, sy0 = round(1.0 + q, 4), round(1.0 / (1.0 + q), 4)
    squash_bone = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0},
                             {"time": 0.4, "x": sx0, "y": sy0},
                             {"time": 1.0, "x": 1.0, "y": 1.0}],
                   "shear": [{"time": 0.0, "x": 0.0, "y": 0.0},
                             {"time": 0.4, "x": 12.0, "y": 0.0},
                             {"time": 1.0, "x": 0.0, "y": 0.0}]}
    a_coup = TV.amplify_bone_tl(squash_bone, g, coupled_scale=True)
    a_naive = TV.amplify_bone_tl(squash_bone, g, coupled_scale=False)
    cx, cy = a_coup["scale"][1]["x"], a_coup["scale"][1]["y"]
    nx, ny = a_naive["scale"][1]["x"], a_naive["scale"][1]["y"]
    coup_vol_ok = abs(cx * cy - 1.0) <= 1e-3           # 耦合保守恆
    coup_stretch_up = cx > sx0 + 1e-6                   # 拉長峰被放大
    coup_shear_up = abs(a_coup["shear"][1]["x"] - g * 12.0) <= 1e-6   # shear v'=g*v
    naive_breaks_vol = abs(nx * ny - 1.0) > 1e-2        # per-axis 破壞守恆(nx 放大、ny 樓地板不動)
    x5["b_coupled_vs_peraxis"] = {
        "coupled": {"x": cx, "y": cy, "prod": round(cx * cy, 6)},
        "naive": {"x": nx, "y": ny, "prod": round(nx * ny, 6)},
        "coupled_volume_ok": coup_vol_ok, "coupled_stretch_up": coup_stretch_up,
        "coupled_shear_up": coup_shear_up, "naive_breaks_volume": naive_breaks_vol,
        "pass": coup_vol_ok and coup_stretch_up and coup_shear_up and naive_breaks_vol}
    R["X5_neg_control"] = {**x5, "pass": all(v["pass"] for v in x5.values())}

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
        for k in ["X1_present_backward_compat", "X2_stretch_shear_monotone_volume",
                  "X3_coupling_damped_per_tier", "X4_end2end_pivot_fixed", "X5_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("X2 per tier {}:".format(TIERS))
        for qb, d in R["X2_stretch_shear_monotone_volume"]["beats"].items():
            print("  {:10s} stretch {}  shear {}  vol_dev {}".format(
                qb, d["stretch_peaks"], d["shear_peaks"], d["worst_volume_dev"]))
        print("X5(b) coupled prod {} vs naive prod {}".format(
            R["X5_neg_control"]["b_coupled_vs_peraxis"]["coupled"]["prod"],
            R["X5_neg_control"]["b_coupled_vs_peraxis"]["naive"]["prod"]))
        print("X4 pivot-fixed (fixed/negctrl px):")
        for rec in R["X4_end2end_pivot_fixed"]["checked"]:
            print("  {:16s} {:10s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["beat"], rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
