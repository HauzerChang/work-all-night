#!/usr/bin/env python3
"""candidate G-4''''''-vol-tier 自我驗收閘 — volume-conserving twist 接檔位差異化(純 CPU)。

補 G-4''''''-vol 明白列出的最後一條 honest boundary:「**vol 僅作用 base twist**;tier 變體仍 shear-only —
vol 隨檔位放大需**重算補償 scale** 以維持 det≡1(tier 放大 shear → cos(shearX−shearY) 變 → 補償 s 須跟著
非線性重算,比照 squash 的耦合 amplify),為後續」。

G-4''''''-vol 讓 base twist 掛等向補償 scale `s=1/√cos(shearX−shearY)` → 全域 local 行列式 det≡1(擰而不變面積);
G-4''''''-tier 讓兩軸 shear 峰隨檔位以同一 g 同比放大(shearY/shearX≡−φ 逐檔不變)。但兩者相乘時有一個**跨通道
耦合陷阱**:檔位放大以 `v'=g*v` 同比放大兩軸 shear → `cos(shearX'−shearY')=cos(g·(shearX−shearY))` **隨 g 改變**
(擰得愈狠、面積縮愈多)→ base 幅度算出的補償 scale **已不足**維持 det≡1。若沿用 base scale(或對 base scale 線性
放大)→ 高檔位面積守恆破裂(實測 Legend |det−1| 達 0.39)。

解法(`tier_variants._twist_vol_scale_from_shear` + `amplify_bone_tl(twist_vol=True)`):tier 變體的補償等向 scale
由**放大後**的 shear **重算** `s'=1/√cos(shearX'−shearY')` → det≡1 **由建構保證**在任一檔位保持。crux(與 squash
耦合 amplify 的差異):squash 的守恆約束(scaleX·scaleY≡1)**與 shear 無關**(由 scaleX 反推 scaleY);twist 的守恆
約束(`s²·cos(shearX−shearY)≡1`)**耦合到放大後的 shear 值**,故必須讀放大後 shear 才能重算 s —— 這是 twist
vol-tier 獨有的鑑別點(比照 squash G-4''''' 沿守恆流形放大,惟 twist 走**等向**且補償量取決於放大後 shear)。

真值界定同 twist 系列(E/H/I/J/G-4'/G-4''''/G-4''''''/-tier/-count/-vol):主秀運動無唯一正解(PROPOSAL 手感),
閘驗**客觀結構簽章**(每檔位體積守恆 + 雙軸阻尼反相 + φ 保形 + 補償量遞增)非美感;負對照證鑑別力(閘可信)。
從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(tier_gains, twist_volume=True)` 端到端量。

AC(客觀、可量測):
  VTT1 present + dual-channel + backward-compat : 每檔位 `twist__{tier}` 皆產出、finite、有 bone、≥1 bone 帶雙軸
        shear(shearX/shearY 峰 ≥ MIN_SHEAR)**與**等向 scale(scaleX==scaleY 每幀);名經 `beat_category` 仍路由回
        twist;base(In/Loop/Out + base twist,twist_volume=True)帶/不帶 tier_gains 逐位元不變;**向後相容**:
        twist_volume=False → tier 變體**無 scale 通道**(shear-only),且與不帶 twist_volume 的 (G-4''''''-tier) 輸出逐位元同。
  VTT2 crux — volume conserved every tier      : **每個檔位**每 twist bone 每內部極值幀,全域 local det |det−1| ≤ TOL_DET
        (擰而不變面積,不只 base);**負對照(a)無補償**:同(放大後)shear 但 scale≡1 → |det−1| ≥ MIN_SHRINK 且隨檔位
        **嚴格遞增**(縮愈多);**負對照(b)base scale 未重算**:對高檔位放大後 shear 施 Super base scale → |det−1| ≥
        MIN_BASECOMP_BREAK(Mega/Omg/Legend)且隨檔位嚴格遞增 → 證「補償 scale 必須由放大後 shear 重算」非「沿用 base 即可」。
  VTT3 isotropic + peaks & comp magnitude mono : 每檔位 scale 等向(scaleX==scaleY);兩軸 shear 峰 |shearX|、|shearY|
        皆 Super<Mega<Omg<Legend **嚴格遞增**;補償 scale 幅度 max|s−1| 亦隨檔位**嚴格遞增**(擰愈狠→補愈多)。
  VTT4 dual-axis damped + counterphase + phi   : 每檔位每 twist bone shearX **與** shearY 各自(首尾 0、繞 0 變號≥3、
        相繼極值遞減阻尼);每內部極值反號(反相耦合);shearY 峰/shearX 峰 ≈ TWIST_PHI(φ 逐檔不變,誤差 ≤ PHI_TOL)。
  VTT5 identity interface per tier             : 每檔位 sample(0)/sample(dur) 各 bone identity;shear 首尾 (0,0)、scale 首尾 (1,1)。
  VTT6 end-to-end three-channel pivot-fixed    : `build_spine --twist-volume --tier-variants --shear-pivot`(真實 robot)
        產每檔位 twist__{tier} 帶 shear+scale+rotate 補償;凡有關節 pivot 的 bone pivot 殘差 < TOL_FIX;內建負對照
        (繞件中心)大位移 → 證三通道(含重算補償 scale)皆錨在 pivot,且高檔位(最強一般仿射)亦不動。

用法:
  python3 validate_twist_volume_tier.py            # 摘要
  python3 validate_twist_volume_tier.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from beat_templates import TWIST_PHI
from pivot_rotation import transform_matrix_full
# 復用 twist 系列閘的讀取/阻尼/反相判準,確保與 twist-gen/-tier/-vol 完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_shear_pivot import _world
from validate_twist_gen import (_shear_y, _shear_xy, _interior_shear, _tw3_eval,
                                _has_shear_y, _psd, _skeleton, _storyboard, _is_ident,
                                GENRE, MIN_SHEAR, TOL_FIX, MIN_NEG, NEG_RATIO)
from validate_twist_volume import _scale_frames, _local_det, TOL_DET, MIN_SHRINK

TIERS = ["Super", "Mega", "Omg", "Legend"]
PHI_TOL = 2e-3            # shearY峰/shearX峰 對 TWIST_PHI 的容差(g*v 4 位捨入下的餘裕)
MIN_BASECOMP_BREAK = 0.05  # 高檔位沿用 base(Super)scale → |det−1| 下限(實測 Mega 0.099 → 餘裕)


def _twist_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "twist"]


def _peak_x(anim):
    ps = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(ps, default=0.0)


def _peak_y(anim):
    ps = [max(abs(v) for v in _shear_y(ch)) for ch in anim.get("bones", {}).values() if _shear_y(ch)]
    return max(ps, default=0.0)


def _comp_peak(anim):
    """該 anim 全 bone 補償等向 scale 的峰 |s−1|(無 scale 回 0)。"""
    ms = []
    for ch in anim.get("bones", {}).values():
        for (sx, sy) in _scale_frames(ch):
            ms.append(abs(sx - 1.0))
    return max(ms, default=0.0)


def _is_strict_inc(xs):
    return all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb, twist_volume=True)                      # tiers=None(base 帶 vol)
    anims = G.build_animations(skel, sb, tier_gains=gains, twist_volume=True)    # 檔位 + vol
    twist_beats = _twist_beats(base)
    R = {}

    # ---- VTT1 present + dual-channel + backward-compat ----
    t1 = {"twist_beats": twist_beats, "missing": [], "not_finite": [], "no_bones": [],
          "variant_no_shear": [], "variant_no_scale": [], "weak_shearx": [], "weak_sheary": [],
          "anisotropic_scale": [], "misrouted": [], "base_changed": [], "off_has_scale": [],
          "off_ne_tieronly": []}
    for tb in twist_beats:
        for t in TIERS:
            vk = "{}__{}".format(tb, t)
            an = anims.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            if not an.get("bones"):
                t1["no_bones"].append(vk)
            sheared = {bn: ch for bn, ch in an.get("bones", {}).items() if _shear_xy(ch)}
            scaled = {bn: ch for bn, ch in an.get("bones", {}).items() if _scale_frames(ch)}
            if not sheared:
                t1["variant_no_shear"].append(vk)
            if not scaled:
                t1["variant_no_scale"].append(vk)
            if sheared and (max(_peak_x(an), 0.0) < MIN_SHEAR):
                t1["weak_shearx"].append(vk)
            if sheared and (max(_peak_y(an), 0.0) < MIN_SHEAR):
                t1["weak_sheary"].append(vk)
            for bn, ch in scaled.items():
                if any(abs(sx - sy) > 1e-6 for (sx, sy) in _scale_frames(ch)):
                    t1["anisotropic_scale"].append("{}::{}".format(vk, bn))
            if G.beat_category(vk) != "twist":
                t1["misrouted"].append((vk, G.beat_category(vk)))
    # base(含 In/Loop/Out + base twist,twist_volume=True)帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    # 向後相容:twist_volume=False → tier 變體 shear-only(無 scale)且逐位元同 (G-4''''''-tier)
    anims_off = G.build_animations(skel, sb, tier_gains=gains)                   # 預設 twist_volume=False
    for tb in twist_beats:
        for t in TIERS:
            vk = "{}__{}".format(tb, t)
            an_off = anims_off.get(vk, {})
            if any(_scale_frames(ch) for ch in an_off.get("bones", {}).values()):
                t1["off_has_scale"].append(vk)
    t1_pass = (bool(twist_beats) and not any(t1[k] for k in
               ["missing", "not_finite", "no_bones", "variant_no_shear", "variant_no_scale",
                "weak_shearx", "weak_sheary", "anisotropic_scale", "misrouted", "base_changed",
                "off_has_scale"]))
    R["VTT1_present_dual_channel_compat"] = {**t1, "pass": t1_pass}

    # ---- VTT2 crux: volume conserved at EVERY tier + neg-controls ----
    t2 = {"break_conserve": [], "beats": {}, "fail_shrink_mono": [], "fail_basecomp_break": [],
          "fail_basecomp_mono": []}
    for tb in twist_beats:
        shrink_by_tier, basecomp_by_tier = [], []
        base_scale_of = {bn: _scale_frames(ch) for bn, ch in
                         anims["{}__{}".format(tb, "Super")].get("bones", {}).items()}
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            dev_vol_max, dev_plain_max, dev_basecomp_max = 0.0, 0.0, 0.0
            for bn, ch in an.get("bones", {}).items():
                xy = _shear_xy(ch); sc = _scale_frames(ch)
                if len(xy) < 3 or len(sc) != len(xy):
                    continue
                bsc = base_scale_of.get(bn, [])
                for i, ((shx, shy), (scx, scy)) in enumerate(list(zip(xy, sc))):
                    if i == 0 or i == len(xy) - 1:
                        continue  # 去首尾 identity,只量內部極值
                    dv = abs(_local_det(scx, scy, shx, shy) - 1.0)        # 帶重算補償 → ≈1
                    dp = abs(_local_det(1.0, 1.0, shx, shy) - 1.0)         # 負對照(a)scale≡1 → 縮
                    dev_vol_max = max(dev_vol_max, dv)
                    dev_plain_max = max(dev_plain_max, dp)
                    if i < len(bsc):                                       # 負對照(b)base scale 未重算
                        db = abs(_local_det(bsc[i][0], bsc[i][1], shx, shy) - 1.0)
                        dev_basecomp_max = max(dev_basecomp_max, db)
                    key = "{}__{}::{}".format(tb, t, bn)
                    if dv > TOL_DET and key not in t2["break_conserve"]:
                        t2["break_conserve"].append(key)
            shrink_by_tier.append(round(dev_plain_max, 6))
            basecomp_by_tier.append(round(dev_basecomp_max, 6))
        t2["beats"][tb] = {"plain_shrink_by_tier": shrink_by_tier,
                           "basecomp_break_by_tier": basecomp_by_tier}
        if not (min(shrink_by_tier) >= MIN_SHRINK and _is_strict_inc(shrink_by_tier)):
            t2["fail_shrink_mono"].append(tb)
        # base scale 未重算:Super(g=1)≈0(base 本身正確),Mega/Omg/Legend 須破裂且遞增
        higher = basecomp_by_tier[1:]
        if not (higher and min(higher) >= MIN_BASECOMP_BREAK):
            t2["fail_basecomp_break"].append(tb)
        if not _is_strict_inc(basecomp_by_tier):
            t2["fail_basecomp_mono"].append(tb)
    t2_pass = (bool(t2["beats"]) and not t2["break_conserve"] and not t2["fail_shrink_mono"]
               and not t2["fail_basecomp_break"] and not t2["fail_basecomp_mono"])
    R["VTT2_volume_conserved_every_tier"] = {**t2, "TOL_DET": TOL_DET, "pass": t2_pass}

    # ---- VTT3 isotropic + peaks & compensation magnitude monotone ----
    t3 = {"beats": {}, "fail_mono_x": [], "fail_mono_y": [], "fail_mono_comp": [], "anisotropic": []}
    for tb in twist_beats:
        px = [_peak_x(anims["{}__{}".format(tb, t)]) for t in TIERS]
        py = [_peak_y(anims["{}__{}".format(tb, t)]) for t in TIERS]
        pc = [_comp_peak(anims["{}__{}".format(tb, t)]) for t in TIERS]
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                if any(abs(sx - sy) > 1e-6 for (sx, sy) in _scale_frames(ch)):
                    t3["anisotropic"].append("{}__{}::{}".format(tb, t, bn))
        t3["beats"][tb] = {"shearX_peaks": [round(v, 3) for v in px],
                           "shearY_peaks": [round(v, 3) for v in py],
                           "comp_peaks": [round(v, 4) for v in pc]}
        if not _is_strict_inc(px):
            t3["fail_mono_x"].append(tb)
        if not _is_strict_inc(py):
            t3["fail_mono_y"].append(tb)
        if not _is_strict_inc(pc):
            t3["fail_mono_comp"].append(tb)
    t3_pass = (bool(t3["beats"]) and not t3["fail_mono_x"] and not t3["fail_mono_y"]
               and not t3["fail_mono_comp"] and not t3["anisotropic"])
    R["VTT3_isotropic_peaks_comp_monotone"] = {**t3, "pass": t3_pass}

    # ---- VTT4 dual-axis damped + counterphase + phi invariant per tier ----
    t4 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [],
          "not_counterphase": [], "bad_ratio": []}
    for tb in twist_beats:
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                for axis, vals in (("x", _shear_x(ch)), ("y", _shear_y(ch))):
                    if not vals:
                        continue
                    key = "{}__{}::{}::{}".format(tb, t, bn, axis)
                    if not (abs(vals[0]) < 1e-6 and abs(vals[-1]) < 1e-6):
                        t4["bad_endpoints"].append(key)
                    if _sign_changes_zero(vals) < 3:
                        t4["few_sign_changes"].append(key)
                    if not _extrema_mags_decreasing(vals):
                        t4["not_damped"].append(key)
                interior = _interior_shear(ch)
                if interior and _has_shear_y(ch):
                    cp_ok, _dev_ok, _det = _tw3_eval(interior)
                    if not cp_ok:
                        t4["not_counterphase"].append("{}__{}::{}".format(tb, t, bn))
                sx, sy = _shear_x(ch), _shear_y(ch)
                if sx and sy:
                    pkx = max(abs(v) for v in sx)
                    if pkx > 1e-9:
                        ratio = max(abs(v) for v in sy) / pkx
                        if abs(ratio - TWIST_PHI) > PHI_TOL:
                            t4["bad_ratio"].append(("{}__{}::{}".format(tb, t, bn), round(ratio, 5)))
    t4_pass = not any(t4[k] for k in ["bad_endpoints", "few_sign_changes", "not_damped",
                                      "not_counterphase", "bad_ratio"])
    R["VTT4_dual_axis_damped_phi"] = {**t4, "phi": TWIST_PHI, "pass": t4_pass}

    # ---- VTT5 identity interface per tier ----
    t5 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for tb in twist_beats:
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                t5["bad_interface"].append("{}__{}".format(tb, t))
            for bn, ch in an.get("bones", {}).items():
                xy = _shear_xy(ch)
                if xy and (abs(xy[0][0]) > 1e-6 or abs(xy[0][1]) > 1e-6
                           or abs(xy[-1][0]) > 1e-6 or abs(xy[-1][1]) > 1e-6):
                    t5["shear_endpoints_nonzero"].append("{}__{}::{}".format(tb, t, bn))
                sc = _scale_frames(ch)
                if sc and (abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6
                           or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6):
                    t5["scale_endpoints_nonident"].append("{}__{}::{}".format(tb, t, bn))
    t5_pass = not any(t5[k] for k in ["bad_interface", "shear_endpoints_nonzero",
                                      "scale_endpoints_nonident"])
    R["VTT5_identity_interface"] = {**t5, "pass": t5_pass}

    # ---- VTT6 end-to-end three-channel pivot-fixed (tier variants) ----
    import build_spine
    out = "/tmp/twist_vol_tier_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True,
                             tier_variants=True, twist_volume=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    tier_twist = [nm for nm in sp_skel["animations"]
                  if "__" in nm and G.beat_category(nm.split("__")[0]) == "twist"]
    s6 = {"tier_twist_beats": sorted(tier_twist), "checked": [], "fail_fixed": [],
          "fail_negctrl": [], "n_joint_bones": 0, "n_with_scale": 0}
    for tb in tier_twist:
        an = sp_skel["animations"][tb]
        for bn, ch in an.get("bones", {}).items():
            if bn not in joints or bn not in centers:
                continue
            tr = ch.get("translate")
            if not tr:
                continue
            O = np.array(centers[bn], float); P = np.array(joints[bn], float)
            ellP = P - O
            s6["n_joint_bones"] += 1
            if ch.get("scale"):
                s6["n_with_scale"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 200 for i in range(201)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"beat": tb, "bone": bn, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2), "has_scale": bool(ch.get("scale"))}
            s6["checked"].append(rec)
            if not (fix < TOL_FIX):
                s6["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                s6["fail_negctrl"].append(rec)
    s6_pass = (bool(tier_twist) and s6["n_joint_bones"] >= 1 and s6["n_with_scale"] >= 1
               and not s6["fail_fixed"] and not s6["fail_negctrl"])
    R["VTT6_end2end_pivot_fixed"] = {**s6, "pass": s6_pass}

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
        for k in ["VTT1_present_dual_channel_compat", "VTT2_volume_conserved_every_tier",
                  "VTT3_isotropic_peaks_comp_monotone", "VTT4_dual_axis_damped_phi",
                  "VTT5_identity_interface", "VTT6_end2end_pivot_fixed"]:
            print("{:36s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("VTT2 per-tier {} conservation/neg-controls:".format(TIERS))
        for tb, d in R["VTT2_volume_conserved_every_tier"]["beats"].items():
            print("  {:8s} plain-shrink {}  base-not-recomputed-break {}".format(
                tb, d["plain_shrink_by_tier"], d["basecomp_break_by_tier"]))
        print("VTT3 per-tier {} peaks:".format(TIERS))
        for tb, d in R["VTT3_isotropic_peaks_comp_monotone"]["beats"].items():
            print("  {:8s} shearX {}  shearY {}  comp|s-1| {}".format(
                tb, d["shearX_peaks"], d["shearY_peaks"], d["comp_peaks"]))
        print("VTT6 pivot-fixed (fixed/negctrl px):")
        for rec in R["VTT6_end2end_pivot_fixed"]["checked"]:
            print("  {:18s} {:8s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}  scale={}".format(
                rec["beat"], rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"], rec["has_scale"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
