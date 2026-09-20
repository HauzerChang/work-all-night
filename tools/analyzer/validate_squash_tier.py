#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 的體積守恆擠壓)接檔位幅度差異化(純 CPU)。

candidate (G-4'''') 讓 `gen_squash` 成為**第一個同時產 shear + 非均勻 scale** 的生成器,但當時的
honest boundary:squash **不在** `MAIN_SHOW_CATS` → 檔位機制未放大它。原因很具體:squash 的 scale 是
**體積守恆對**(scaleX=1+q 拉長、scaleY=1/(1+q) 壓扁,scaleX·scaleY==1);(J) 的 `_amp_scale`
**只放大 identity 上方**(scaleX>1 被放大)而**下方樓地板不動**(scaleY<1 保持)→ 放大後 scaleX·scaleY≠1
**破壞體積守恆**(squash 變成單軸拉長,不再是擠壓)。

本次(G-4''''')補上:把 squash 併入 `MAIN_SHOW_CATS` 並讓 scale 走 **log 空間耦合 amplify**
(`_amp_scale_coupled`:v'=v^g,兩軸同以 g 次冪放大)。key insight:log 空間放大**天然保守恆**——
放大後積 = (scaleX·scaleY)^g = 1^g = 1(**任意 g、與哪一軸拉長無關**),同時非均勻 |scaleX−scaleY|
隨檔位遞增、identity(1)→1^g==1 不動、g=1.0 逐位元不變(v^1==v)。shear 通道沿用 (G-4'') 的 v'=g*v
(對 0 對稱)→ **shear 峰與 squash 非均勻峰同隨檔位遞增(雙通道耦合放大)**,且阻尼振盪 + 體積守恆
兩簽章在每個檔位都保形。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位愈斜愈擠**且仍守恆**」是可量化的檔位簽章,用負對照證鑑別力(閘可信)。從**先驗庫** →
**真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  V1 present + backward-compat : squash base beat 雙通道(shear+scale);每檔位 `squash__{tier}` 皆產出、
                                finite、有 bone、≥1 bone 同時帶 shear+scale、名經 `beat_category` 仍路由回
                                squash;**base 逐位元不變**(帶/不帶 tier_gains 的 base squash + In/Loop/Out 相同)。
  V2 crux — dual peak monotone : 各檔位 squash 的峰 |shearX| **且** scale 非均勻峰 |scaleX−scaleY| 皆
                                Super<Mega<Omg<Legend **嚴格遞增**(端到端經 build_animations 量);
                                首檔(Super,g=1)兩峰 == base(向後相容)。
  V3 crux — volume preserved   : **每個檔位**的 squash bone,每個內部(去端點)squash 極值幀:(a)scaleX·scaleY≈1
     across all tiers            (|積−1|≤TOL_VOL,**耦合放大不破壞守恆**=本 cap 的核心);(b)至少一極值非均勻
                                |scaleX−scaleY|≥MIN_ANISO;(c)squash 幅度 |scaleX−1| 隨極值嚴格遞減(阻尼)。
                                並復用 G-4' 判準驗 shear 阻尼振盪(首尾 0 + 繞 0 變號 ≥3 + 相繼極值遞減)每檔位保形。
  V4 identity interface/tier   : **每個檔位** sample(0)/sample(dur) 各 bone identity,shear 首尾 0 + scale 首尾 (1,1)。
  V5 neg-control               : (a) **平增益守衛**:增益階梯全 1.0 → V2 遞增 FALSE 且各檔位逐位元 == base;
                                (b) **耦合 amplify 必要性守衛(crux)**:對同一 squash scale 套 (J) 舊
                                `_amp_scale`(非耦合)於 g>1 → 體積守恆 FALSE(|積−1| 大);套本 cap
                                `_amp_scale_coupled` → 守恆仍 TRUE → 證「不能沿用舊 amplify、耦合 amplify 必要」;
                                (c) **通道隔離單元測**:`_amp_scale_coupled` 對守恆對 (1+q,1/(1+q)) g=2 → 積仍==1;
                                `amplify_bone_tl(coupled_scale=True)` 對「只有 shear」bone → shear 放大 g*v、
                                不生 scale 鍵(證耦合旗標只改 scale 路徑、其他通道與 (G-4'') 一致)。
  V6 crux — amplified pivot     : 端到端 `build_spine --animate --tier-variants --shear-pivot`(真實 robot),
                                凡有關節 pivot 的 bone,**放大後**的檔位變體(含最爆 Legend)pivot 殘差
                                < TOL_FIX;內建負對照 = 未補償(繞件中心)大位移 → 證放大不破壞端到端不動點
                                (apply_pivots 對放大後的一般仿射重算補償 Δ,愈爆檔位 M 愈非相似仍精確錨定)。

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
# 復用 G-4' 的 shear 讀取與阻尼簽章判準
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
# 復用 G-4'''' 的 scale 讀取、內部極值抽取、體積守恆/非均勻/阻尼判準(同一判準 → 閘一致可信)
from validate_squash_gen import (_scale_xy, _interior_scale, _sq3_eval,
                                 MIN_SHEAR, MIN_ANISO, TOL_VOL, TOL_FIX, MIN_NEG, NEG_RATIO)
from validate_shear_pivot import _world   # 真實 Spine local(含 shear + 非均勻 scale)世界座標求值

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


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _squash_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "squash"]


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _aniso_peak(anim):
    """該 anim 全 bone 的峰 |scaleX−scaleY|(無 scale 回 0)。"""
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
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": []}
    for qb in squash_beats:
        dual_base = any(_shear_x(ch) and _scale_xy(ch) for ch in base[qb].get("bones", {}).values())
        if not dual_base:
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

    # ---- V2 crux: dual-channel (shear + aniso) peak monotone across tiers ----
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
    R["V2_dual_peak_monotone"] = {**v2, "pass": v2_pass}

    # ---- V3 crux: volume conservation + damped signature preserved per tier ----
    v3 = {"bad_volume": [], "no_aniso": [], "scale_not_damped": [],
          "shear_bad_endpoints": [], "shear_few_sign_changes": [], "shear_not_damped": [],
          "detail": {}}
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
                shdamp = _extrema_mags_decreasing(sx)
                sh_ends = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                v3["detail"][key] = {**det, "shear_nsc": nsc, "shear_damped": shdamp}
                if not vok:
                    v3["bad_volume"].append(key)
                if not aok:
                    v3["no_aniso"].append(key)
                if not dok:
                    v3["scale_not_damped"].append(key)
                if not sh_ends:
                    v3["shear_bad_endpoints"].append(key)
                if nsc < 3:
                    v3["shear_few_sign_changes"].append(key)
                if not shdamp:
                    v3["shear_not_damped"].append(key)
    v3_pass = (bool(v3["detail"]) and not any(v3[k] for k in
               ["bad_volume", "no_aniso", "scale_not_damped",
                "shear_bad_endpoints", "shear_few_sign_changes", "shear_not_damped"]))
    R["V3_volume_preserved_per_tier"] = {**v3, "pass": v3_pass}

    # ---- V4 identity interface per tier ----
    v4 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            vk = "{}__{}".format(qb, t)
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                v4["bad_interface"].append(vk)
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                    v4["shear_endpoints_nonzero"].append("{}::{}".format(vk, bn))
                xy = _scale_xy(ch)
                if xy and (abs(xy[0][0] - 1.0) > 1e-6 or abs(xy[0][1] - 1.0) > 1e-6
                           or abs(xy[-1][0] - 1.0) > 1e-6 or abs(xy[-1][1] - 1.0) > 1e-6):
                    v4["scale_endpoints_nonident"].append("{}::{}".format(vk, bn))
    R["V4_identity_interface_per_tier"] = {**v4, "pass": (not v4["bad_interface"]
                                                          and not v4["shear_endpoints_nonzero"]
                                                          and not v4["scale_endpoints_nonident"])}

    # ---- V5 negative controls ----
    v5 = {}
    # (a) 平增益守衛:全 1.0 → 遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for qb in squash_beats:
        sh_peaks = [_shear_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        an_peaks = [_aniso_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(sh_peaks) or _is_strict_inc(an_peaks):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    v5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) 耦合 amplify 必要性守衛(crux):對真實 squash scale,舊 _amp_scale(非耦合)於 g>1 破壞守恆,
    #     本 cap _amp_scale_coupled 保守恆 → 證不能沿用舊 amplify。
    g_test = 2.10
    # 取真實 squash 的一個 bone 的內部極值 scale(base)
    qb0 = squash_beats[0]
    ref_ch = None
    for ch in base[qb0].get("bones", {}).values():
        if _interior_scale(ch):
            ref_ch = ch; break
    interior = _interior_scale(ref_ch)
    old_interior = [(round(TV._amp_scale(sx, g_test), 4), round(TV._amp_scale(sy, g_test), 4))
                    for (sx, sy) in interior]
    new_interior = [(round(TV._amp_scale_coupled(sx, g_test), 4), round(TV._amp_scale_coupled(sy, g_test), 4))
                    for (sx, sy) in interior]
    old_vol, _, _, old_det = _sq3_eval(old_interior)
    new_vol, new_aniso, _, new_det = _sq3_eval(new_interior)
    v5["b_coupled_necessity"] = {
        "g": g_test, "old_amp_volume_ok": old_vol, "new_amp_volume_ok": new_vol,
        "new_amp_aniso_ok": new_aniso,
        "old_max_prod_err": round(max(abs(sx * sy - 1.0) for (sx, sy) in old_interior), 5),
        "new_max_prod_err": round(max(abs(sx * sy - 1.0) for (sx, sy) in new_interior), 5),
        # 舊 amplify 應**破壞**守恆(volume FALSE)、耦合 amplify 應**保**守恆且非均勻仍 TRUE
        "pass": (not old_vol) and new_vol and new_aniso}
    # (c) 通道隔離單元測
    #   c1: 耦合 amplify 對守恆對 (1+q, 1/(1+q)) g=2 → 積仍==1
    q = 0.16
    cx, cy = TV._amp_scale_coupled(1.0 + q, 2.0), TV._amp_scale_coupled(1.0 / (1.0 + q), 2.0)
    c1_ok = abs(cx * cy - 1.0) <= 1e-6 and abs(cx - cy) > abs((1.0 + q) - 1.0 / (1.0 + q))  # 非均勻放大
    #   c2: coupled_scale=True 對 shear-only bone → shear g*v、無 scale 鍵(旗標只改 scale 路徑)
    shear_only = {"shear": [{"time": 0.0, "x": 0.0, "y": 0.0}, {"time": 0.5, "x": 10.0, "y": 0.0},
                            {"time": 1.0, "x": 0.0, "y": 0.0}]}
    a_sh = TV.amplify_bone_tl(shear_only, 2.0, coupled_scale=True)
    c2_ok = ("scale" not in a_sh) and abs(a_sh["shear"][1]["x"] - 2.0 * 10.0) <= 1e-6
    #   c3: coupled g=1.0 → 逐位元不變(向後相容)
    c3_ok = (TV._amp_scale_coupled(1.16, 1.0) == 1.16 and TV._amp_scale_coupled(0.8621, 1.0) == 0.8621)
    v5["c_channel_isolation"] = {"coupled_pair_conserved": c1_ok, "shear_only_no_scale": c2_ok,
                                 "g1_byte_identical": c3_ok,
                                 "pass": c1_ok and c2_ok and c3_ok}
    R["V5_neg_control"] = {**v5, "pass": all(v["pass"] for v in v5.values())}

    # ---- V6 crux: amplified variant still pivots (end-to-end --tier-variants --shear-pivot) ----
    # 檔位放大讓 shear/squash 更大 → 一般仿射 M 更「非相似」;apply_pivots 對**放大後**的變體重算補償
    # translate Δ=(M−I)(O−P) → 凡有關節 pivot 的 bone,即使最爆檔位(Legend)pivot 仍精確不動
    # (證放大不破壞端到端不動點;內建負對照=未補償繞件中心大位移)。
    import numpy as np
    import build_spine
    out = "/tmp/squash_tier_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True, tier_variants=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    v6 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0, "tiers_seen": set()}
    # 只驗檔位變體(base squash 的不動點由 SQ5 保證);Legend 為最爆檔位(最嚴苛)
    for qb in sp_skel["animations"]:
        base_nm = qb.split("__")[0]
        if "__" not in qb or G.beat_category(base_nm) != "squash":
            continue
        tier = qb.split("__")[1]
        an = sp_skel["animations"][qb]
        for bn, ch in an.get("bones", {}).items():
            if bn not in joints or bn not in centers:
                continue
            O = np.array(centers[bn], float); P = np.array(joints[bn], float); ellP = P - O
            tr = ch.get("translate")
            if not tr:
                continue
            v6["n_joint_bones"] += 1
            v6["tiers_seen"].add(tier)
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"variant": qb, "bone": bn, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            v6["checked"].append(rec)
            if not (fix < TOL_FIX):
                v6["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                v6["fail_negctrl"].append(rec)
    v6["tiers_seen"] = sorted(v6["tiers_seen"])
    v6_pass = (v6["n_joint_bones"] >= 1 and "Legend" in v6["tiers_seen"]
               and not v6["fail_fixed"] and not v6["fail_negctrl"])
    R["V6_amplified_pivot_fixed"] = {**v6, "pass": v6_pass}

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
        for k in ["V1_present_backward_compat", "V2_dual_peak_monotone",
                  "V3_volume_preserved_per_tier", "V4_identity_interface_per_tier",
                  "V5_neg_control", "V6_amplified_pivot_fixed"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V2 dual peaks per tier {}:".format(TIERS))
        for qb, d in R["V2_dual_peak_monotone"]["beats"].items():
            print("  {:10s} shear {} (base {})  aniso {} (base {})".format(
                qb, d["shear_peaks"], d["base_shear"], d["aniso_peaks"], d["base_aniso"]))
        nb = R["V5_neg_control"]["b_coupled_necessity"]
        print("V5b coupled-necessity: old_amp vol_ok={} (prod_err {}) | new_amp vol_ok={} aniso_ok={} (prod_err {})".format(
            nb["old_amp_volume_ok"], nb["old_max_prod_err"], nb["new_amp_volume_ok"],
            nb["new_amp_aniso_ok"], nb["new_max_prod_err"]))
        print("V6 amplified pivot-fixed (fixed/negctrl px), tiers {}:".format(
            R["V6_amplified_pivot_fixed"]["tiers_seen"]))
        for rec in R["V6_amplified_pivot_fixed"]["checked"]:
            print("  {:16s} {:8s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["variant"], rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
