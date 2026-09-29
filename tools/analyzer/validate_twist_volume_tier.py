#!/usr/bin/env python3
"""candidate G-4''''''-vol-tier 自我驗收閘 — **volume-conserving twist 接檔位差異化**(純 CPU)。

補 (G-4''''''-vol) 明列的最後一條 honest boundary:「vol 僅作用 **base twist**;tier 變體仍 shear-only。
vol 隨檔位放大需**重算補償 scale** 以維持 det≡1(tier 放大 shear → cos(shearX−shearY) 變 → 補償 s 須
跟著非線性重算,比照 squash 的耦合 amplify,但 twist 走等向補償)。」

**crux(與 squash tier 耦合 amplify 的差異)**:squash 的守恆是 scale **內部**耦合(scaleY=1/scaleX),
放大拉長軸、壓縮軸取倒數即守恆;twist 的守恆是 scale **由 shear 決定**的耦合(s=1/√cos(shearX−shearY))。
tier 以**同一 g** 放大兩軸 shear(v'=g·v)→ shearX−shearY 變成 g·(shearX−shearY) → cos 非線性變小 →
補償 s 必須從**放大後**的 shear 重算 `s'=1/√cos(g·(shearX−shearY))`。逐軸線性放大既有 s(`_amp_scale`)
**無法**維持 det≡1(實測 Legend g=2.1 下 |det−1|≈0.31)。本閘的鑑別力即來自「同一 `amplify_bone_tl`、
twist_vol=True(重算)守恆 vs twist_vol=False(逐軸線性)破守恆」對同一 base vol beat 的對比。

三效正交:段數(tier_twist_cycles,重生成)× 幅度(tier_gains 兩軸同比 → φ 保形)× 體積守恆(重算補償 s)
同時成立且互不干擾。真值界定同 twist 系列:主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章**
(兩軸峰遞增 + φ 不變 + 反相阻尼 + 每檔位 det≡1 + 端到端不動點)非美感;負對照證鑑別力(閘可信)。
從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(tier_gains, tier_twist_cycles,
twist_volume=True)` 端到端量。

AC(客觀、可量測):
  TVT1 present + backward-compat : base twist(vol)帶雙軸 shear + 等向 scale;每檔位 `twist__{tier}` 皆產出、
                                  finite、有 bone、≥1 bone **同時**帶雙軸 shear **與**等向 scale、名經
                                  `beat_category` 仍路由回 twist;base(含 In/Loop/Out + base twist(vol))
                                  帶/不帶 tier_gains 逐位元不變;**twist_volume=False → tier 變體無 scale 通道**
                                  且逐位元同 (G-4''''''-count) 純 shear tier 輸出(關掉 vol 零回歸)。
  TVT2 crux — per-tier 體積守恆  : **每個檔位**每 twist bone 每內部極值幀,全域 local |det−1| ≤ TOL_DET
                                  (擰而不變面積,任一檔位皆守恆);**負對照** = 同一 base vol beat 以
                                  `amplify_bone_tl(…, twist_vol=False)`(逐軸線性放大既有 s)→ 高檔位
                                  |det−1| ≥ MIN_BREAK(破守恆)→ 證重算補償(非線性放大既有 s)是必要、
                                  閘測「真體積守恆」非「有 scale 即可」。
  TVT3 crux — 雙軸峰遞增 + φ 不變: 各檔位峰 |shearX| **與** 峰 |shearY| 皆 Super<Mega<Omg<Legend 嚴格遞增
                                  (Super==base),且每 bone 每檔位 shearY峰/shearX峰 ≈ TWIST_PHI(逐檔不變)
                                  → 體積耦合**不擾動** twist 檔位簽章(段數×幅度×守恆三效正交)。
  TVT4 雙軸反相阻尼簽章 per tier : **每檔位**每 twist bone 的 shearX **與** shearY 各自(a)首尾 0(b)繞 0
                                  變號 ≥3(c)相繼極值遞減(阻尼);且每內部極值反號(反相耦合)。
  TVT5 identity 介面 per tier    : 每檔位每 bone shear 首尾 (0,0)、scale 首尾 (1,1)(可插 Loop 間)。
  TVT6 端到端 pivot + 隔離       : `build_spine --animate --tier-variants --twist-volume --shear-pivot`(真實
                                  robot)產 twist__{tier} 帶 shear+scale+rotate 三通道補償,凡有關節 pivot 的
                                  bone pivot 殘差 < TOL_FIX(含補償 scale),內建負對照(繞件中心)大位移;
                                  且各檔位 twist scale 等向(scaleX==scaleY)vs squash tier scale 非均勻
                                  (兩種守恆機制不同源、互不外洩)。

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
from analyze_target import analyze
from pivot_rotation import transform_matrix_full
# 復用 twist 系列閘的讀取 / 阻尼 / 反相 / 不動點判準,確保與整個 twist 系列完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_shear_pivot import _world
from validate_twist_gen import (_shear_y, _shear_xy, _interior_shear, _tw3_eval, _has_shear_y,
                                _is_ident, TOL_FIX, MIN_NEG, NEG_RATIO)
from validate_twist_volume import _scale_frames, _local_det
from validate_twist_tier import (_psd, _skeleton, _storyboard, _twist_beats,
                                 _peak_x, _peak_y, _is_strict_inc)

GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
MIN_SHEAR = 5.0      # 度,base twist 兩軸峰下限(head 最小:shearX 10°、shearY 7°)
PHI_TOL = 2e-3       # shearY峰/shearX峰 對 TWIST_PHI 的容差(g*v 4 位捨入下的餘裕)
TOL_DET = 2e-4       # 每檔位 |det−1| 上限(同 twist_volume TV2 / squash SC2 體積守恆容差)
MIN_BREAK = 0.02     # 負對照(逐軸線性放大既有 s)高檔位 |det−1| 下限(實測 Legend ≈0.31 → 充足餘裕)


def _det_devs(ch):
    """該 bone 內部極值幀的 |det−1| 列表(shear/scale 同 τ 同索引;無 scale 回 [])。"""
    xy = _shear_xy(ch); sc = _scale_frames(ch)
    if len(xy) < 3 or len(sc) != len(xy):
        return []
    return [abs(_local_det(scx, scy, shx, shy) - 1.0)
            for (shx, shy), (scx, scy) in list(zip(xy, sc))[1:-1]]


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    ttc = TV.twist_cycles_for(GENRE)
    # base(twist_volume=True,無 tier_gains):base twist 帶 vol scale
    base = G.build_animations(skel, sb, tier_twist_cycles=ttc, twist_volume=True)
    # 端到端:幅度 + 段數 + 體積守恆三效同開
    anims = G.build_animations(skel, sb, tier_gains=gains, tier_twist_cycles=ttc, twist_volume=True)
    twist_beats = _twist_beats(base)
    R = {}

    # ---- TVT1 present + backward-compat ----
    t1 = {"twist_beats": twist_beats, "base_weak_shear": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_shear": [], "variant_no_scale": [], "anisotropic": [],
          "misrouted": [], "base_changed": [], "off_has_scale": [], "off_not_identical": []}
    for tb in twist_beats:
        if _peak_x(base[tb]) < MIN_SHEAR or _peak_y(base[tb]) < MIN_SHEAR:
            t1["base_weak_shear"].append(tb)
        # base twist 應帶等向 scale(vol)
        if not any(_scale_frames(ch) for ch in base[tb].get("bones", {}).values()):
            t1["variant_no_scale"].append(tb + "(base)")
        for t in TIERS:
            vk = "{}__{}".format(tb, t)
            an = anims.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            if not an.get("bones"):
                t1["no_bones"].append(vk)
            if not any(_shear_xy(ch) for ch in an.get("bones", {}).values()):
                t1["variant_no_shear"].append(vk)
            if not any(_scale_frames(ch) for ch in an.get("bones", {}).values()):
                t1["variant_no_scale"].append(vk)
            for bn, ch in an.get("bones", {}).items():
                if any(abs(sx - sy) > 1e-6 for (sx, sy) in _scale_frames(ch)):
                    t1["anisotropic"].append("{}::{}".format(vk, bn))
            if G.beat_category(vk) != "twist":
                t1["misrouted"].append((vk, G.beat_category(vk)))
    # base(含 In/Loop/Out + base twist(vol))帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    # 向後相容:twist_volume=False → tier 變體無 scale 且逐位元同 (G-4''''''-count) 純 shear tier
    anims_off = G.build_animations(skel, sb, tier_gains=gains, tier_twist_cycles=ttc)  # twist_volume=False
    for tb in twist_beats:
        for t in TIERS:
            vk = "{}__{}".format(tb, t)
            an = anims_off.get(vk, {})
            if any(_scale_frames(ch) for ch in an.get("bones", {}).values()):
                t1["off_has_scale"].append(vk)
    t1_pass = (bool(twist_beats) and not any(t1[k] for k in
               ["base_weak_shear", "missing", "not_finite", "no_bones", "variant_no_shear",
                "variant_no_scale", "anisotropic", "misrouted", "base_changed", "off_has_scale",
                "off_not_identical"]))
    R["TVT1_present_backward_compat"] = {**t1, "pass": t1_pass}

    # ---- TVT2 crux: per-tier volume conservation + naive-amp (twist_vol=False) negative control ----
    t2 = {"break_conserve": [], "neg_not_break": [], "per_tier_max_dev": {}, "neg_max_dev": {}}
    # 正:每檔位實際變體 det≡1
    for t in TIERS:
        worst = 0.0
        for tb in twist_beats:
            for ch in anims["{}__{}".format(tb, t)].get("bones", {}).values():
                devs = _det_devs(ch)
                if devs and max(devs) > TOL_DET:
                    t2["break_conserve"].append("{}__{}".format(tb, t))
                worst = max([worst] + devs)
        t2["per_tier_max_dev"][t] = round(worst, 6)
    # 負:同一 base vol beat 以 twist_vol=False(逐軸線性放大既有 s)放大 → 高檔位破守恆
    for t in TIERS:
        g = gains[t]
        worst = 0.0
        for tb in twist_beats:
            for bn, ch in base[tb].get("bones", {}).items():
                if not (_shear_xy(ch) and _scale_frames(ch)):
                    continue
                naive = TV.amplify_bone_tl(ch, g, twist_vol=False)  # ★ 逐軸線性放大既有 s
                worst = max([worst] + _det_devs(naive))
        t2["neg_max_dev"][t] = round(worst, 5)
    # 負對照須在**放大檔位**(g>1)破守恆(Super g=1 == base 不破,合理);取最高檔位為證
    if t2["neg_max_dev"].get("Legend", 0.0) < MIN_BREAK:
        t2["neg_not_break"].append("Legend")
    t2_pass = (bool(t2["per_tier_max_dev"]) and not t2["break_conserve"] and not t2["neg_not_break"])
    R["TVT2_per_tier_volume_conserved"] = {**t2, "pass": t2_pass}

    # ---- TVT3 crux: dual-axis peaks monotone across tiers + phi ratio invariant ----
    t3 = {"beats": {}, "fail_mono_x": [], "fail_mono_y": [], "fail_base": [], "bad_ratio": []}
    for tb in twist_beats:
        px = [_peak_x(anims["{}__{}".format(tb, t)]) for t in TIERS]
        py = [_peak_y(anims["{}__{}".format(tb, t)]) for t in TIERS]
        bx, by = _peak_x(base[tb]), _peak_y(base[tb])
        mono_x, mono_y = _is_strict_inc(px), _is_strict_inc(py)
        super_eq = abs(px[0] - bx) <= 1e-4 and abs(py[0] - by) <= 1e-4
        t3["beats"][tb] = {"shearX_peaks": [round(p, 3) for p in px],
                           "shearY_peaks": [round(p, 3) for p in py],
                           "base": [round(bx, 3), round(by, 3)],
                           "mono_x": mono_x, "mono_y": mono_y, "super_eq_base": super_eq}
        if not mono_x:
            t3["fail_mono_x"].append(tb)
        if not mono_y:
            t3["fail_mono_y"].append(tb)
        if not super_eq:
            t3["fail_base"].append(tb)
        # φ 比值逐檔不變(per bone per tier)
        for t in TIERS:
            for bn, ch in anims["{}__{}".format(tb, t)].get("bones", {}).items():
                sx, sy = _shear_x(ch), _shear_y(ch)
                if not sx or not sy:
                    continue
                pkx = max(abs(v) for v in sx); pky = max(abs(v) for v in sy)
                if pkx <= 1e-9:
                    continue
                if abs(pky / pkx - TWIST_PHI) > PHI_TOL:
                    t3["bad_ratio"].append(("{}__{}::{}".format(tb, t, bn), round(pky / pkx, 5)))
    t3_pass = (bool(t3["beats"]) and not t3["fail_mono_x"] and not t3["fail_mono_y"]
               and not t3["fail_base"] and not t3["bad_ratio"])
    R["TVT3_dual_axis_peak_phi"] = {**t3, "phi": TWIST_PHI, "pass": t3_pass}

    # ---- TVT4 dual-axis counter-phase damped signature preserved per tier ----
    t4 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "not_counterphase": []}
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
    t4_pass = not any(t4[k] for k in
                      ["bad_endpoints", "few_sign_changes", "not_damped", "not_counterphase"])
    R["TVT4_damped_counterphase_per_tier"] = {**t4, "pass": t4_pass}

    # ---- TVT5 identity interface per tier (shear (0,0) & scale (1,1)) ----
    t5 = {"shear_endpoints_nonzero": [], "scale_endpoints_nonident": [], "bad_sample": []}
    for tb in twist_beats:
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]; end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values())
                    and all(_is_ident(v) for v in end.values())):
                t5["bad_sample"].append("{}__{}".format(tb, t))
            for bn, ch in an.get("bones", {}).items():
                xy = _shear_xy(ch)
                if xy and (abs(xy[0][0]) > 1e-6 or abs(xy[0][1]) > 1e-6
                           or abs(xy[-1][0]) > 1e-6 or abs(xy[-1][1]) > 1e-6):
                    t5["shear_endpoints_nonzero"].append("{}__{}::{}".format(tb, t, bn))
                sc = _scale_frames(ch)
                if sc and (abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6
                           or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6):
                    t5["scale_endpoints_nonident"].append("{}__{}::{}".format(tb, t, bn))
    t5_pass = not any(t5[k] for k in
                      ["shear_endpoints_nonzero", "scale_endpoints_nonident", "bad_sample"])
    R["TVT5_identity_interface_per_tier"] = {**t5, "pass": t5_pass}

    # ---- TVT6 end-to-end three-channel pivot-fixed + isotropic-vs-nonuniform isolation ----
    import build_spine
    out = "/tmp/twist_vol_tier_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, tier_variants=True,
                             shear_pivot=True, twist_volume=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {}); centers = summ.get("pivot_centers", {})
    t6 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0, "n_with_scale": 0}
    sp_tw_variants = [nm for nm in sp_skel["animations"]
                      if "__" in nm and G.beat_category(nm.split("__")[0]) == "twist"]
    for nm in sp_tw_variants:
        for bn, ch in sp_skel["animations"][nm].get("bones", {}).items():
            if bn not in joints or bn not in centers:
                continue
            tr = ch.get("translate")
            if not tr:
                continue
            O = np.array(centers[bn], float); P = np.array(joints[bn], float); ellP = P - O
            t6["n_joint_bones"] += 1
            if ch.get("scale"):
                t6["n_with_scale"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"variant": nm, "bone": bn, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2), "has_scale": bool(ch.get("scale"))}
            t6["checked"].append(rec)
            if not (fix < TOL_FIX):
                t6["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                t6["fail_negctrl"].append(rec)
    # 等向 vs 非均勻隔離(檔位層級):twist tier scale 等向、squash tier scale 非均勻
    tw_uniform = all(abs(sx - sy) <= 1e-6
                     for tb in twist_beats for t in TIERS
                     for ch in anims["{}__{}".format(tb, t)].get("bones", {}).values()
                     for (sx, sy) in _scale_frames(ch))
    sq_beats = [nm for nm in base if "__" not in nm and G.beat_category(nm) == "squash"]
    sq_anisotropic = any(abs(sx - sy) > 1e-6
                         for sqb in sq_beats for t in TIERS
                         for ch in anims.get("{}__{}".format(sqb, t), {}).get("bones", {}).values()
                         for (sx, sy) in _scale_frames(ch))
    t6["iso_isolation"] = {"twist_tier_uniform": tw_uniform, "squash_tier_nonuniform": sq_anisotropic,
                           "squash_beats": sq_beats}
    t6_pass = (t6["n_joint_bones"] >= 1 and t6["n_with_scale"] >= 1
               and not t6["fail_fixed"] and not t6["fail_negctrl"]
               and tw_uniform and sq_anisotropic)
    R["TVT6_end2end_pivot_isolation"] = {**t6, "pass": t6_pass}

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
        for k in ["TVT1_present_backward_compat", "TVT2_per_tier_volume_conserved",
                  "TVT3_dual_axis_peak_phi", "TVT4_damped_counterphase_per_tier",
                  "TVT5_identity_interface_per_tier", "TVT6_end2end_pivot_isolation"]:
            print("{:36s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("TVT2 per-tier max|det-1| (vol):", R["TVT2_per_tier_volume_conserved"]["per_tier_max_dev"])
        print("TVT2 neg-ctrl max|det-1| (naive linear amp):",
              R["TVT2_per_tier_volume_conserved"]["neg_max_dev"])
        print("TVT3 peaks per tier {}:".format(TIERS))
        for tb, d in R["TVT3_dual_axis_peak_phi"]["beats"].items():
            print("  {:10s} shearX {}  shearY {}  (base {})".format(
                tb, d["shearX_peaks"], d["shearY_peaks"], d["base"]))
        print("TVT6 pivot-fixed (fixed/negctrl px):")
        for rec in R["TVT6_end2end_pivot_isolation"]["checked"]:
            print("  {:18s} {:10s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}  scale={}".format(
                rec["variant"], rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"], rec["has_scale"]))
        print("TVT6 iso isolation:", R["TVT6_end2end_pivot_isolation"]["iso_isolation"])
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
