#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

一路的 honest boundary:G-4''''(`validate_squash_gen.py`)讓 `gen_squash` 成為**第一個同時產 shear +
非均勻體積守恆 scale** 的生成器,但當時 squash **不在** `MAIN_SHOW_CATS` —— 因為檔位增益 `_amp_scale`
只放大 identity 上方(scaleX>1 被放大、scaleY<1 樓地板被凍結)會**破壞體積守恆**(scaleX·scaleY≠1),
故 squash 完全不隨檔位放大(檔位愈高主秀愈爆,唯獨斜拉擠壓強度不變=不一致)。本次(G-4''''')補上
**體積守恆耦合放大**:把 squash 併入 `MAIN_SHOW_CATS` + `VOLUME_CONSERVE_CATS`,`amplify_bone_tl_coupled`
放大「拉長軸」(以 `_amp_scale` 線性放大 q,與 shear 峰同比 g)、壓縮軸重算為其倒數 → **scaleX·scaleY≡1
精確保持、非均勻保持**,且 shear 峰亦以 g 放大 → 斜拉量與擠壓量**同比耦合遞增**。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章**
(體積守恆 + 阻尼振盪 + 耦合遞增)**非美感**;負對照證鑑別力(閘可信)。從**先驗庫** → **真實
build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。復用 G-4'/G-4'''' 的
shear 阻尼判準與 SQ3 體積守恆判準,確保與 shear-gen / squash-gen 閘完全一致。

AC(客觀、可量測):
  P1 present + backward-compat + identity : base squash 帶 shear+非均勻 scale;每檔位 `squash__{tier}`
                                    皆產出/finite/有 bone/≥1 bone **同時**帶 shear+scale/名經 `beat_category`
                                    仍路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains 的 base squash +
                                    In/Loop/Out 相同)且 **squash__Super == base squash 逐位元**(g=1 向後相容);
                                    每檔位變體 sample(0)/sample(dur) identity + shear 首尾 0 + scale 首尾 (1,1)。
  P2 crux — coupled amplitude monotone   : 各檔位 (i) 峰 |shearX| 與 (ii) 峰 squash 拉長量 max|scaleX−1|
                                    **皆** Super<Mega<Omg<Legend **嚴格遞增**(shear+scale **兩通道同比耦合**
                                    放大),且首檔(Super,g=1)== base(向後相容)。
  P3 crux — volume conservation per tier : **每個檔位**的 squash bone 每個 shear 極值幀 (a)scaleX·scaleY≈1
                                    (|積−1|≤TOL_VOL,面積守恆);(b)至少一極值非均勻 |scaleX−scaleY|≥MIN_ANISO;
                                    (c)squash 幅度 |scaleX−1| 隨極值嚴格遞減(阻尼)—— 復用 SQ3 判準;
                                    → 耦合放大在**所有檔位**都不破壞體積守恆(honest boundary 真的補上)。
  P4 damped shear signature per tier     : 每個檔位 squash bone 的 shearX (a)首尾 0;(b)繞 0 變號 ≥3;
                                    (c)相繼極值嚴格遞減(阻尼)—— g*v 同比放大 → 簽章保形。
  P5 end-to-end pivot-fixed + volume     : `build_spine --shear-pivot --tier-variants`(真實 robot)產出
                                    squash__{tier} 帶補償;(a)有關節 pivot 的 bone pivot 殘差 < TOL_FIX 且
                                    負對照(未補償繞件中心)>NEG_RATIO×(端到端一般仿射不動點在**放大後檔位**仍成立);
                                    (b)每檔位變體體積守恆(SQ3)在 build_spine round-trip + pivot 補償後**存活**
                                    (pivot 補償只加 translate,不動 scale/shear → scaleX·scaleY≡1 不受影響)。
  P6 neg-control                         : (a)**平增益守衛**:增益全 1.0 → P2 遞增 FALSE 且各檔位 == base 逐位元;
                                    (b)**耦合必要性判別(crux)**:對 base squash 幀施**舊獨立** `amplify_bone_tl`
                                    (g=2.0)→ 體積守恆**破壞**(∃幀 |積−1|>BREAK_VOL);施**新耦合**
                                    `amplify_bone_tl_coupled` → 守恆(所有幀 |積−1|≤TOL_VOL)→ 證耦合放大真的
                                    在做事、閘偵測得到差異(否則耦合放大形同虛設);
                                    (c)**非均勻 scale 隔離**:全 storyboard(含所有檔位變體)中,只有 squash 及其
                                    `__tier` 變體帶非均勻 scale(|scaleX−scaleY|>MIN_ANISO);其餘主秀 beat 及變體
                                    皆等比 scale → 耦合放大對象仍只鎖 squash,零外洩。

用法:
  python3 validate_squash_tier.py            # 摘要
  python3 validate_squash_tier.py --json     # 完整 JSON
"""
import argparse, copy, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
# 復用 G-4' shear 阻尼判準 + G-4'''' SQ3 體積守恆判準 + G-4 端到端不動點求值(閘間一致)
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import (_sq3_eval, _interior_scale, _scale_xy, _squash_beats,
                                 _has_aniso_scale, TOL_VOL, MIN_ANISO, MIN_SHEAR,
                                 TOL_FIX, MIN_NEG, NEG_RATIO)
from validate_shear_pivot import _world

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
BREAK_VOL = 0.01   # P6(b):舊獨立放大破壞體積守恆的下限(遠大於 TOL_VOL；實測 Legend 破壞 ~0.1)


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


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _stretch_peak(anim):
    """該 anim 全 bone 的峰 squash 拉長量 max|scaleX−1|(無 scale 回 0)。"""
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

    # ---- P1 present + backward-compat + identity interface ----
    p1 = {"squash_beats": squash_beats, "base_no_dual": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": [],
          "super_ne_base": [], "bad_interface": []}
    for qb in squash_beats:
        bdual = {bn: ch for bn, ch in base[qb].get("bones", {}).items() if _shear_x(ch) and _scale_xy(ch)}
        if not bdual or _shear_peak(base[qb]) < MIN_SHEAR:
            p1["base_no_dual"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                p1["missing"].append(vk); continue
            if not SA.all_finite(an):
                p1["not_finite"].append(vk)
            if not an.get("bones"):
                p1["no_bones"].append(vk)
            dual = {bn: ch for bn, ch in an.get("bones", {}).items() if _shear_x(ch) and _scale_xy(ch)}
            if not dual:
                p1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                p1["misrouted"].append((vk, G.beat_category(vk)))
            # identity 介面(可插 Loop):端點 pose identity + shear/scale 端點
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]; end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                p1["bad_interface"].append(vk)
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch); xy = _scale_xy(ch)
                if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                    p1["bad_interface"].append("{}::shear".format(vk))
                if xy and (abs(xy[0][0] - 1.0) > 1e-6 or abs(xy[0][1] - 1.0) > 1e-6
                           or abs(xy[-1][0] - 1.0) > 1e-6 or abs(xy[-1][1] - 1.0) > 1e-6):
                    p1["bad_interface"].append("{}::scale".format(vk))
        # squash__Super 逐位元 == base squash(g=1 向後相容)
        if json.dumps(anims.get("{}__Super".format(qb)), sort_keys=True) != json.dumps(base[qb], sort_keys=True):
            p1["super_ne_base"].append(qb)
    # base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            p1["base_changed"].append(k)
    p1_pass = (bool(squash_beats) and not any(p1[k] for k in
               ["base_no_dual", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed", "super_ne_base", "bad_interface"]))
    R["P1_present_backward_compat"] = {**p1, "pass": p1_pass}

    # ---- P2 crux: coupled amplitude monotone (shear peak + squash stretch) ----
    p2 = {"beats": {}, "fail_shear_mono": [], "fail_stretch_mono": [], "fail_base": []}
    for qb in squash_beats:
        sh_peaks = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        st_peaks = [_stretch_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_sh = _shear_peak(base[qb]); base_st = _stretch_peak(base[qb])
        sh_mono = _is_strict_inc(sh_peaks); st_mono = _is_strict_inc(st_peaks)
        super_eq = abs(sh_peaks[0] - base_sh) <= 1e-4 and abs(st_peaks[0] - base_st) <= 1e-4
        p2["beats"][qb] = {"shear_peaks": [round(p, 3) for p in sh_peaks],
                           "stretch_peaks": [round(p, 4) for p in st_peaks],
                           "base_shear": round(base_sh, 3), "base_stretch": round(base_st, 4),
                           "shear_mono": sh_mono, "stretch_mono": st_mono, "super_eq_base": super_eq}
        if not sh_mono:
            p2["fail_shear_mono"].append(qb)
        if not st_mono:
            p2["fail_stretch_mono"].append(qb)
        if not super_eq:
            p2["fail_base"].append(qb)
    p2_pass = (bool(p2["beats"]) and not p2["fail_shear_mono"]
               and not p2["fail_stretch_mono"] and not p2["fail_base"])
    R["P2_coupled_amplitude_monotone"] = {**p2, "pass": p2_pass}

    # ---- P3 crux: volume conservation preserved per tier (reuse SQ3) ----
    p3 = {"bad_volume": [], "no_aniso": [], "not_damped": [], "max_vol_err": 0.0, "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior or not _shear_x(ch):
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                vok, aok, dok, det = _sq3_eval(interior)
                p3["detail"][key] = det
                p3["max_vol_err"] = max(p3["max_vol_err"], max(abs(p - 1.0) for p in det["prod"]))
                if not vok:
                    p3["bad_volume"].append(key)
                if not aok:
                    p3["no_aniso"].append(key)
                if not dok:
                    p3["not_damped"].append(key)
    p3["max_vol_err"] = round(p3["max_vol_err"], 6)
    p3_pass = (bool(p3["detail"]) and not p3["bad_volume"]
               and not p3["no_aniso"] and not p3["not_damped"])
    R["P3_volume_preserving_per_tier"] = {**p3, "pass": p3_pass}

    # ---- P4 damped shear signature per tier ----
    p4 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "detail": {}}
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
                p4["detail"][key] = {"n_sign_changes": nsc, "damped": damp}
                if not ends_ok:
                    p4["bad_endpoints"].append(key)
                if nsc < 3:
                    p4["few_sign_changes"].append(key)
                if not damp:
                    p4["not_damped"].append(key)
    p4_pass = (bool(p4["detail"]) and not p4["bad_endpoints"]
               and not p4["few_sign_changes"] and not p4["not_damped"])
    R["P4_damped_shear_per_tier"] = {**p4, "pass": p4_pass}

    # ---- P5 end-to-end: pivot-fixed + volume conservation after build_spine round-trip ----
    import build_spine
    out = "/tmp/squash_tier_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True, tier_variants=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {}); centers = summ.get("pivot_centers", {})
    p5 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "vol_broke": [], "n_joint_bones": 0}
    sp_variants = [nm for nm in sp_skel["animations"]
                   if "__" in nm and G.beat_category(nm.split("__")[0]) == "squash"]
    for vk in sp_variants:
        an = sp_skel["animations"][vk]
        for bn, ch in an.get("bones", {}).items():
            # (b) 體積守恆在 build round-trip + pivot 補償後存活(SQ3 volume)
            interior = _interior_scale(ch)
            if interior and _shear_x(ch):
                vok = all(abs(sx * sy - 1.0) <= TOL_VOL for (sx, sy) in interior)
                if not vok:
                    p5["vol_broke"].append("{}::{}".format(vk, bn))
            # (a) 端到端不動點:有關節 pivot 的 bone
            if bn not in joints or bn not in centers:
                continue
            O = np.array(centers[bn], float); P = np.array(joints[bn], float)
            ellP = P - O
            tr = ch.get("translate")
            if not tr:
                continue
            p5["n_joint_bones"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 200 for i in range(201)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"variant": vk, "bone": bn, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            p5["checked"].append(rec)
            if not (fix < TOL_FIX):
                p5["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                p5["fail_negctrl"].append(rec)
    p5_pass = (p5["n_joint_bones"] >= 1 and not p5["fail_fixed"]
               and not p5["fail_negctrl"] and not p5["vol_broke"])
    R["P5_end2end_pivot_fixed_volume"] = {**p5, "pass": p5_pass}

    # ---- P6 negative controls ----
    p6 = {}
    # (a) 平增益守衛:全 1.0 → 遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for qb in squash_beats:
        sh_peaks = [_shear_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        st_peaks = [_stretch_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(sh_peaks) or _is_strict_inc(st_peaks):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    p6["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) 耦合必要性判別:對 base squash 施舊獨立放大 → 破壞守恆;施新耦合放大 → 守恆
    g = 2.0
    indep_broke, coupled_kept, det_b = [], [], {}
    for qb in squash_beats:
        for bn, ch in base[qb].get("bones", {}).items():
            if not (_shear_x(ch) and _scale_xy(ch)):
                continue
            indep = TV.amplify_bone_tl(copy.deepcopy(ch), g)       # 舊:兩軸獨立 _amp_scale
            coup = TV.amplify_bone_tl_coupled(copy.deepcopy(ch), g)  # 新:耦合守恆
            def _interior_prod(b):
                xy = [(f["x"], f["y"]) for f in b.get("scale", [])]
                return [sx * sy for (sx, sy) in xy[1:-1]] if len(xy) >= 3 else []
            ip = _interior_prod(indep); cp = _interior_prod(coup)
            imax = max((abs(p - 1.0) for p in ip), default=0.0)
            cmax = max((abs(p - 1.0) for p in cp), default=0.0)
            det_b["{}::{}".format(qb, bn)] = {"indep_max_vol_err": round(imax, 5),
                                              "coupled_max_vol_err": round(cmax, 6)}
            if imax > BREAK_VOL:
                indep_broke.append("{}::{}".format(qb, bn))
            if cmax <= TOL_VOL:
                coupled_kept.append("{}::{}".format(qb, bn))
    n_dual = len(det_b)
    p6["b_coupled_necessity"] = {"detail": det_b, "indep_broke": indep_broke,
                                 "coupled_kept": coupled_kept,
                                 "pass": (n_dual >= 1 and len(indep_broke) == n_dual
                                          and len(coupled_kept) == n_dual)}
    # (c) 非均勻 scale 隔離:只有 squash 及其變體帶非均勻 scale
    leak = []
    for nm, an in anims.items():
        if G.beat_category(nm.split("__")[0]) == "squash":
            continue
        for bn, ch in an.get("bones", {}).items():
            if _has_aniso_scale(ch):
                leak.append((nm, bn))
    p6["c_aniso_isolated"] = {"leaked": leak, "pass": not leak}
    R["P6_neg_control"] = {**p6, "pass": all(v["pass"] for v in p6.values())}

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
        for k in ["P1_present_backward_compat", "P2_coupled_amplitude_monotone",
                  "P3_volume_preserving_per_tier", "P4_damped_shear_per_tier",
                  "P5_end2end_pivot_fixed_volume", "P6_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("P2 per-tier peaks {}:".format(TIERS))
        for qb, d in R["P2_coupled_amplitude_monotone"]["beats"].items():
            print("  {:8s} shear {}  stretch {}".format(qb, d["shear_peaks"], d["stretch_peaks"]))
        print("P3 max volume error across all tiers: {}".format(R["P3_volume_preserving_per_tier"]["max_vol_err"]))
        print("P5 pivot-fixed (fixed/negctrl px), vol_broke={}:".format(
            R["P5_end2end_pivot_fixed_volume"]["vol_broke"]))
        for rec in R["P5_end2end_pivot_fixed_volume"]["checked"][:6]:
            print("  {:18s} {:8s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["variant"], rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("P6(b) coupled-necessity detail:", json.dumps(
            R["P6_neg_control"]["b_coupled_necessity"]["detail"], ensure_ascii=False))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
