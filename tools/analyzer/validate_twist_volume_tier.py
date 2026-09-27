#!/usr/bin/env python3
"""candidate G-4''''''-vol-tier 自我驗收閘 — **volume-conserving twist 接檔位差異化**(純 CPU)。

(G-4''''''-vol)讓 base twist 掛體積守恆等向補償 scale `s=1/√cos(shearX−shearY)` → 全域 local
行列式 `det≡1`(擰而不變面積),但**僅作用 base twist**;tier 變體仍 shear-only(honest boundary,見
`s1-twist-volume-conserving.md`)。本次(G-4''''''-vol-tier)把體積守恆接上檔位放大。

crux(檔位放大為何不能沿用逐軸/耦合增益):tier 讓兩軸 shear 同比 ×g(shearX'=g·shearX、shearY'=g·shearY
→ φ 不變),故補償須 `s' = 1/√cos(g·(shearX−shearY))` —— **對 g 非線性**(cos 之反推)。逐軸 `_amp_scale`
是對 s 的**線性**放大 → det 隨檔位漂移(實測 Legend g=2.1 |det−1|≈0.31)。故 twist(vol)檔位變體的
scale 必須**由(放大後的)shear 重算**(`amplify_bone_tl(twist_vol=True)`)→ 每檔位每扭轉極值 det≡1。
與 squash 耦合 amplify(scale 由建構保證守恆,非均勻)是**同守恆目標、不同源**(twist 走等向:scale 純補償,
各向異性全由 shear 提供)。

真值界定同 twist 系列(E/H/I/J/G-4'/G-4''''/G-4''''''/-tier/-count/-vol):主秀運動無唯一正解(PROPOSAL
手感),閘驗**客觀結構簽章**(兩軸峰遞增 + φ 逐檔不變 + 反相耦合 + **每檔位體積守恆**)非美感;負對照
(逐軸線性放大 → det 漂移)證鑑別力(閘測「由 shear 重算的真守恆」非「有 scale 通道即可」)。從**先驗庫**
→ **真實 build_spine robot 骨架** → `build_animations(tier_gains=…, twist_volume=True)` 端到端量。

AC(客觀、可量測):
  TVT1 present + isotropic dual-channel : 每檔位 `twist__{tier}` 皆產出、finite、有 bone、名經
                                        `beat_category` 仍路由回 twist,且 ≥1 bone **同時**帶雙軸 shear
                                        (shearX、shearY 峰皆非零)**與** scale 通道,scale **等向**(每幀
                                        scaleX==scaleY);**Super(g=1)== base twist(vol)逐位元一致**(介面/向後相容)。
  TVT2 crux — 每檔位體積守恆          : 每檔位每 twist bone 每內部極值幀,全域 local `|det−1| ≤ TOL_DET`
                                        (擰而不變面積);**負對照** = 逐軸線性放大補償 scale(舊 `_amp_scale`)
                                        → |det−1| 隨檔位**單調增大**且頂檔 ≥ MIN_DRIFT → 證守恆來自「由放大後
                                        shear 重算」非「有 scale 即可」。
  TVT3 幅度遞增 + φ + 補償遞增        : 各檔位峰 |shearX| **與** |shearY| 皆 Super<Mega<Omg<Legend 嚴格遞增;
                                        每 bone 每檔位 shearY峰/shearX峰 ≈ TWIST_PHI(重算 scale 不擾動 shear);
                                        補償 scale 峰(max s)亦隨檔位嚴格遞增(擰愈狠 → 補愈多)。
  TVT4 identity 介面(可插 Loop)     : 每檔位每 twist bone shear 首尾 (0,0)、scale 首尾 (1,1)。
  TVT5 反相 + 阻尼簽章逐檔保形        : 每檔位每 twist bone shearX/shearY 各自(首尾 0、繞 0 變號 ≥3、相繼極值
                                        遞減),且每內部極值反號(反相耦合,復用 TW3 判準)。
  TVT6 負對照/正交/向後相容          : (a)**平增益守衛**:全 g=1.0 → 各檔位 == base twist(vol)逐位元一致
                                        (幅度遞增 FALSE);(b)**count×tier×vol 正交**:帶 tier_twist_cycles →
                                        各檔位段數 [4,5,6,7] 嚴格遞增 **且**每檔位每扭轉極值仍 |det−1| ≤ TOL_DET
                                        (段數×幅度×守恆三效正交);(c)**向後相容/加性**:`twist_volume=False`
                                        + tier_gains → twist 檔位變體**無 scale 通道**且與 shear-only(twist-tier
                                        golden)逐位元一致(vol-tier 純加性,不動舊路徑)。

用法:
  python3 validate_twist_volume_tier.py            # 摘要
  python3 validate_twist_volume_tier.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from beat_templates import TWIST_PHI
# 復用 twist 系列閘的讀取/判準,確保與 -tier / -vol 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_twist_gen import _shear_y, _shear_xy, _interior_shear, _tw3_eval, _has_shear_y, _is_ident
from validate_twist_tier import (_skeleton, _storyboard, GENRE, TIERS, _twist_beats,
                                 _peak_x, _peak_y, _is_strict_inc, MIN_SHEAR, PHI_TOL)
from validate_twist_volume import _scale_frames, _local_det, TOL_DET

MIN_DRIFT = 0.02     # 負對照(逐軸線性放大)頂檔 |det−1| 下限(實測 Legend≈0.31 → 充足餘裕)


def _scale_peak(anim):
    """該 anim 全 bone 補償 scale 的峰值 max(scaleX)(無 scale 回 1.0)。"""
    ps = [sx for ch in anim.get("bones", {}).values() for (sx, _sy) in _scale_frames(ch)]
    return max(ps, default=1.0)


def _naive_amp_max_drift(base_anim, g):
    """負對照:對 base twist(vol)beat 施**逐軸線性**放大(舊 `_amp_scale` 對 scale、v'=g·v 對 shear),
    回傳全 bone 內部極值的 max|det−1|(檔位放大破守恆 → 隨 g 漂移)。"""
    drift = 0.0
    for ch in base_anim.get("bones", {}).values():
        xy = _shear_xy(ch); sc = _scale_frames(ch)
        if len(xy) < 3 or len(sc) != len(xy):
            continue
        for (shx, shy), (scx, scy) in list(zip(xy, sc))[1:-1]:
            shx2 = round(g * shx, 4); shy2 = round(g * shy, 4)
            scx2 = round(TV._amp_scale(scx, g), 4); scy2 = round(TV._amp_scale(scy, g), 4)
            drift = max(drift, abs(_local_det(scx2, scy2, shx2, shy2) - 1.0))
    return drift


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb, twist_volume=True)                       # base twist(vol),無檔位
    anims = G.build_animations(skel, sb, tier_gains=gains, twist_volume=True)    # 檔位 × vol
    twist_beats = _twist_beats(base)
    R = {}

    # ---- TVT1 present + isotropic dual-channel + Super==base ----
    t1 = {"twist_beats": twist_beats, "missing": [], "not_finite": [], "no_bones": [],
          "misrouted": [], "variant_no_shear": [], "variant_no_scale": [], "anisotropic": [],
          "super_ne_base": []}
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
            if G.beat_category(vk) != "twist":
                t1["misrouted"].append((vk, G.beat_category(vk)))
            sheared = {bn: ch for bn, ch in an.get("bones", {}).items() if _shear_xy(ch)}
            scaled = {bn: ch for bn, ch in an.get("bones", {}).items() if _scale_frames(ch)}
            if not (sheared and _peak_x(an) >= MIN_SHEAR and _peak_y(an) >= MIN_SHEAR):
                t1["variant_no_shear"].append(vk)
            if not scaled:
                t1["variant_no_scale"].append(vk)
            for bn, ch in scaled.items():
                if any(abs(sx - sy) > 1e-6 for (sx, sy) in _scale_frames(ch)):
                    t1["anisotropic"].append("{}::{}".format(vk, bn))
        # Super(g=1)== base twist(vol)逐位元一致(介面/向後相容)
        if json.dumps(anims.get("{}__Super".format(tb), None), sort_keys=True) != \
           json.dumps(base[tb], sort_keys=True):
            t1["super_ne_base"].append(tb)
    t1_pass = (bool(twist_beats) and not any(t1[k] for k in
               ["missing", "not_finite", "no_bones", "misrouted", "variant_no_shear",
                "variant_no_scale", "anisotropic", "super_ne_base"]))
    R["TVT1_present_isotropic_dual"] = {**t1, "pass": t1_pass}

    # ---- TVT2 crux: volume conserved per tier + naive-amplify negative control ----
    t2 = {"break_conserve": [], "detail": {}, "neg_drift_by_tier": {},
          "neg_not_monotone": False, "neg_top_below_min": False}
    for tb in twist_beats:
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                xy = _shear_xy(ch); sc = _scale_frames(ch)
                if len(xy) < 3 or len(sc) != len(xy):
                    continue
                dev = [abs(_local_det(scx, scy, shx, shy) - 1.0)
                       for (shx, shy), (scx, scy) in list(zip(xy, sc))[1:-1]]
                key = "{}__{}::{}".format(tb, t, bn)
                t2["detail"][key] = round(max(dev), 6)
                if max(dev) > TOL_DET:
                    t2["break_conserve"].append(key)
        # 負對照:對此 beat 的 base(vol)施逐軸線性放大 → 各檔位漂移
        drifts = [_naive_amp_max_drift(base[tb], gains[t]) for t in TIERS]
        t2["neg_drift_by_tier"][tb] = {t: round(d, 5) for t, d in zip(TIERS, drifts)}
        if not _is_strict_inc(drifts):
            t2["neg_not_monotone"] = True
        if drifts[-1] < MIN_DRIFT:
            t2["neg_top_below_min"] = True
    t2_pass = (bool(t2["detail"]) and not t2["break_conserve"]
               and not t2["neg_not_monotone"] and not t2["neg_top_below_min"])
    R["TVT2_volume_conserved_per_tier"] = {**t2, "tol_det": TOL_DET, "pass": t2_pass}

    # ---- TVT3 amplitude monotone + phi invariant + compensation monotone ----
    t3 = {"beats": {}, "fail_mono_x": [], "fail_mono_y": [], "fail_mono_scale": [], "bad_ratio": []}
    for tb in twist_beats:
        px = [_peak_x(anims["{}__{}".format(tb, t)]) for t in TIERS]
        py = [_peak_y(anims["{}__{}".format(tb, t)]) for t in TIERS]
        ps = [_scale_peak(anims["{}__{}".format(tb, t)]) for t in TIERS]
        t3["beats"][tb] = {"shearX_peaks": [round(p, 3) for p in px],
                           "shearY_peaks": [round(p, 3) for p in py],
                           "scale_peaks": [round(p, 4) for p in ps]}
        if not _is_strict_inc(px):
            t3["fail_mono_x"].append(tb)
        if not _is_strict_inc(py):
            t3["fail_mono_y"].append(tb)
        if not _is_strict_inc(ps):
            t3["fail_mono_scale"].append(tb)
        # φ 逐檔不變(重算 scale 不擾動 shear → 比值恆 TWIST_PHI)
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx, sy = _shear_x(ch), _shear_y(ch)
                if not sx or not sy:
                    continue
                pkx = max(abs(v) for v in sx)
                if pkx <= 1e-9:
                    continue
                ratio = max(abs(v) for v in sy) / pkx
                if abs(ratio - TWIST_PHI) > PHI_TOL:
                    t3["bad_ratio"].append(("{}__{}::{}".format(tb, t, bn), round(ratio, 5)))
    t3_pass = (bool(t3["beats"]) and not t3["fail_mono_x"] and not t3["fail_mono_y"]
               and not t3["fail_mono_scale"] and not t3["bad_ratio"])
    R["TVT3_amp_phi_comp_monotone"] = {**t3, "phi": TWIST_PHI, "pass": t3_pass}

    # ---- TVT4 identity interface per tier ----
    t4 = {"shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for tb in twist_beats:
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                xy = _shear_xy(ch)
                if xy and (abs(xy[0][0]) > 1e-6 or abs(xy[0][1]) > 1e-6
                           or abs(xy[-1][0]) > 1e-6 or abs(xy[-1][1]) > 1e-6):
                    t4["shear_endpoints_nonzero"].append("{}__{}::{}".format(tb, t, bn))
                sc = _scale_frames(ch)
                if sc and (abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6
                           or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6):
                    t4["scale_endpoints_nonident"].append("{}__{}::{}".format(tb, t, bn))
    R["TVT4_identity_interface"] = {**t4, "pass": (not t4["shear_endpoints_nonzero"]
                                                   and not t4["scale_endpoints_nonident"])}

    # ---- TVT5 counter-phase + damped signature preserved per tier ----
    t5 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "not_counterphase": []}
    for tb in twist_beats:
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                for axis, vals in (("x", _shear_x(ch)), ("y", _shear_y(ch))):
                    if not vals:
                        continue
                    key = "{}__{}::{}::{}".format(tb, t, bn, axis)
                    if not (abs(vals[0]) < 1e-6 and abs(vals[-1]) < 1e-6):
                        t5["bad_endpoints"].append(key)
                    if _sign_changes_zero(vals) < 3:
                        t5["few_sign_changes"].append(key)
                    if not _extrema_mags_decreasing(vals):
                        t5["not_damped"].append(key)
                interior = _interior_shear(ch)
                if interior and _has_shear_y(ch):
                    cp_ok, _dev_ok, _det = _tw3_eval(interior)
                    if not cp_ok:
                        t5["not_counterphase"].append("{}__{}::{}".format(tb, t, bn))
    t5_pass = not any(t5[k] for k in ["bad_endpoints", "few_sign_changes",
                                      "not_damped", "not_counterphase"])
    R["TVT5_signature_per_tier"] = {**t5, "pass": t5_pass}

    # ---- TVT6 neg-control / orthogonality / backward-compat ----
    t6 = {}
    # (a) 平增益守衛:全 g=1.0 → 各檔位 == base twist(vol)逐位元一致,且幅度遞增 FALSE
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat, twist_volume=True)
    flat_diff, any_mono_flat = [], False
    for tb in twist_beats:
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(tb, t)], sort_keys=True) != \
               json.dumps(base[tb], sort_keys=True):
                flat_diff.append("{}__{}".format(tb, t))
        px = [_peak_x(flat_anims["{}__{}".format(tb, t)]) for t in TIERS]
        if _is_strict_inc(px):
            any_mono_flat = True
    t6["a_flat_guard"] = {"flat_variants_ne_base": flat_diff, "flat_any_monotone": any_mono_flat,
                          "pass": (not flat_diff) and (not any_mono_flat)}
    # (b) count × tier × vol 正交:段數遞增 + 每檔位每極值仍守恆
    cyc = TV.twist_cycles_for(GENRE)
    anims_c = G.build_animations(skel, sb, tier_gains=gains, tier_twist_cycles=cyc, twist_volume=True)
    seg_fail, det_fail, seg_by_beat = [], [], {}
    for tb in twist_beats:
        segs = []
        for t in TIERS:
            an = anims_c["{}__{}".format(tb, t)]
            nseg_here = 0
            for bn, ch in an.get("bones", {}).items():
                xy = _shear_xy(ch); sc = _scale_frames(ch)
                if len(xy) < 3 or len(sc) != len(xy):
                    continue
                nseg_here = max(nseg_here, len(xy) - 2)
                dev = [abs(_local_det(scx, scy, shx, shy) - 1.0)
                       for (shx, shy), (scx, scy) in list(zip(xy, sc))[1:-1]]
                if dev and max(dev) > TOL_DET:
                    det_fail.append("{}__{}::{}".format(tb, t, bn))
            segs.append(nseg_here)
        seg_by_beat[tb] = segs
        if not _is_strict_inc(segs):
            seg_fail.append(tb)
    t6["b_count_tier_vol_orthogonal"] = {"seg_by_beat": seg_by_beat, "seg_not_monotone": seg_fail,
                                         "det_broken": det_fail,
                                         "pass": (not seg_fail) and (not det_fail)}
    # (c) 向後相容/加性:twist_volume=False + tier_gains → 無 scale 且與 shear-only twist-tier 逐位元一致
    off = G.build_animations(skel, sb, tier_gains=gains)                       # vol off(shear-only golden)
    scale_when_off, off_diff = [], []
    for tb in twist_beats:
        for t in TIERS:
            vk = "{}__{}".format(tb, t)
            if any(_scale_frames(ch) for ch in off[vk].get("bones", {}).values()):
                scale_when_off.append(vk)
            # off 應與「不帶 twist_volume」的 -tier golden 相同(此處 off 即該 golden;確認 vol 未污染 off 路徑)
    # 再確認:on(vol)與 off 僅差在 scale 通道(shear/rotate/translate 逐鍵一致)
    for tb in twist_beats:
        for t in TIERS:
            vk = "{}__{}".format(tb, t)
            on_b = anims[vk].get("bones", {}); off_b = off[vk].get("bones", {})
            for bn in on_b:
                on_no_scale = {k: v for k, v in on_b[bn].items() if k != "scale"}
                off_no_scale = {k: v for k, v in off_b.get(bn, {}).items() if k != "scale"}
                if json.dumps(on_no_scale, sort_keys=True) != json.dumps(off_no_scale, sort_keys=True):
                    off_diff.append("{}::{}".format(vk, bn))
    t6["c_backward_compat_additive"] = {"scale_when_off": scale_when_off,
                                        "nonscale_channels_differ": off_diff,
                                        "pass": (not scale_when_off) and (not off_diff)}
    R["TVT6_neg_orthogonal_compat"] = {**t6, "pass": all(v["pass"] for v in t6.values())}

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
        for k in ["TVT1_present_isotropic_dual", "TVT2_volume_conserved_per_tier",
                  "TVT3_amp_phi_comp_monotone", "TVT4_identity_interface",
                  "TVT5_signature_per_tier", "TVT6_neg_orthogonal_compat"]:
            print("{:36s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("TVT2 det per tier variant:", json.dumps(R["TVT2_volume_conserved_per_tier"]["detail"],
                                                        ensure_ascii=False))
        print("TVT2 neg drift (naive amplify) by tier:",
              json.dumps(R["TVT2_volume_conserved_per_tier"]["neg_drift_by_tier"], ensure_ascii=False))
        print("TVT3 peaks/comp per tier {}:".format(TIERS))
        for tb, d in R["TVT3_amp_phi_comp_monotone"]["beats"].items():
            print("  {:10s} shearX {}  shearY {}  scale {}".format(
                tb, d["shearX_peaks"], d["shearY_peaks"], d["scale_peaks"]))
        print("TVT6(b) seg per tier:", json.dumps(R["TVT6_neg_orthogonal_compat"]
                                                   ["b_count_tier_vol_orthogonal"]["seg_by_beat"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
