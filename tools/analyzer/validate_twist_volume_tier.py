#!/usr/bin/env python3
"""candidate (G-4''''''-vol-tier) 自我驗收閘 — volume-conserving twist 接檔位差異化(純 CPU)。

twist 系列的**最後一條 honest boundary**(G-4''''''-vol `validate_twist_volume.py` 明列):
「vol 僅作用 **base twist**;tier 變體仍 shear-only。vol 隨檔位放大需**重算補償 scale** 以維持 det≡1
(tier 放大 shear → cos(shearX−shearY) 變 → 補償 s 須跟著**非線性**重算,比照 squash 的耦合 amplify)」。

本次(G-4''''''-vol-tier)把體積守恆補到 twist 的**每個檔位變體**:tier 放大把兩軸 shear 同比拉大
(shearX'=g·shearX、shearY'=g·shearY → 兩基底夾角偏離 Δ'=(shearX−shearY)·g),於是真正的守恆補償變成
`s' = 1/√cos(g·Δ)` —— 對 g **非線性**。`amplify_bone_tl(twist_vol=True)` 先放大 shear、再**依放大後的 shear
重算**每個 scale 極值的等向 s(`_recompute_twist_scale_iso`)→ 全域 local det≡1 在**任一檔位**保持,
補償量隨檔位**非線性遞增**;`build_animations(twist_volume=True, tier_gains=…)` / `build_spine --animate
--tier-variants --twist-volume --shear-pivot` 端到端直出。

crux(與 squash tier 耦合 amplify 的機制對比):
  - squash(G-4''''')的耦合是 `sy'=1/sx'`(倒數耦合、與 shear 無關,scale 本身即擠壓);
  - twist 的補償是**依放大後 shear 重算的等向 s**(`s'=1/√cos(g·Δ)`,值來自 shear、非各向異)。
  兩者同為「跨通道約束由建構保證」,但一個是倒數、一個是 cos 反推 —— **不同源**。
關鍵鑑別(VTT3):逐軸線性 `_amp_scale(s,g)=1+g·(s−1)` 追不上非線性 cos 曲線 → 破 det≡1(負對照 0.11–0.31);
依放大後 shear 重算 → 守恆(≤1e-4)。

真值界定同 twist 系列(E/H/I/J/G-4'…):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章**
(每檔位體積守恆 + 補償/shear 峰遞增 + 反相雙軸阻尼 + φ 保形 + 端到端 pivot 不動)非美感;負對照證鑑別力。
從**先驗庫**(slot_bigwin twist beat)→ **真實 build_spine robot 骨架** → `build_animations` 端到端量。

AC(客觀、可量測):
  VTT1 present + backward-compat  : twist base beat(vol)雙通道(shear+**等向** scale);每檔位 `twist__{tier}`
                                   皆產出、finite、有 bone、≥1 bone 同時帶 shear+scale、scale 每幀等向
                                   (scaleX==scaleY)、名經 `beat_category` 仍路由回 twist;**base(In/Loop/Out +
                                   base twist vol)帶/不帶 tier_gains 逐位元不變**;**Super(g=1.0)逐位元 == base
                                   twist vol**(重算補償於 g=1 退化回 base)。
  VTT2 crux — 守恆 + 補償/峰遞增   : **每個檔位**每 twist bone 每內部 scale 極值,全域 local det |det−1|≤TOL_DET
                                   (體積守恆在檔位放大下仍保持);且峰**補償 scale** s 與峰 |shearX| 皆
                                   Super<Mega<Omg<Legend **嚴格遞增**(補償隨檔位非線性遞增),Super 峰==base 峰。
  VTT3 crux 負對照 — 線性破守恆    : 對 base twist(vol)施**逐軸線性** amplify(`amplify_bone_tl(twist_vol=False,
                                   coupled=False)`,Legend 增益)→ ≥1 內部極值 |det−1| **> TOL_DET**(線性內插
                                   追不上 cos);對照**重算**(twist_vol=True)同增益仍守恆 ≤TOL_DET → 證重算的必要性
                                   與閘測「守恆」非恆真;另附重算單元測(依放大後 shear → det≡1、s 隨 g 增大)。
  VTT4 雙軸反相阻尼 + φ + 介面     : **每個檔位**每 twist bone:shearX 與 shearY 各自(a)首尾 0(b)繞 0 變號≥3
                                   (c)相繼極值遞減(阻尼);每內部極值反相(shx·shy<0);φ 比值(shearY峰/shearX峰)
                                   ≈TWIST_PHI 逐檔不變(等向 scale 不擾動 shear 簽章);且 sample(0)/sample(dur)
                                   identity、shear 首尾 (0,0)、scale 首尾 (1,1)(可插 Loop 間,任一檔位)。
  VTT5 端到端三通道 pivot 不動      : `build_spine --animate --tier-variants --twist-volume --shear-pivot`(真實 robot)
                                   產 `twist__{tier}` 帶 shear+scale+rotate 補償;凡有關節 pivot 的 bone,pivot
                                   殘差 < TOL_FIX;內建負對照(繞件中心)大位移 → 證含重算補償 scale 三通道皆錨在 pivot。
  VTT6 隔離/加性/平增益守衛        : (a)**平增益守衛**:增益全 1.0 → VTT2 補償遞增 FALSE 且各檔位 twist 逐位元
                                   == base twist vol;(b)**隔離**:非 twist 的主秀 tier 變體(如 wobble shear-only)
                                   **不被** twist_vol 重算路徑波及(不冒出 scale 通道);(c)**加性**:移除 twist 的
                                   storyboard → 其餘 beat(含 wobble/squash tier 變體)逐位元不變(零回歸)。

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
# 復用 twist 系列閘的讀取/阻尼/反相/守恆判準,確保與 twist_gen/twist_tier/twist_volume 完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_shear_pivot import _world
from validate_twist_gen import (_shear_y, _shear_xy, _interior_shear, _tw3_eval, _has_shear_y,
                               _psd, _skeleton, _storyboard, _is_ident,
                               GENRE, TOL_FIX, MIN_NEG, NEG_RATIO)
from validate_twist_volume import _scale_frames, _local_det, TOL_DET, MIN_SHRINK
from validate_twist_tier import _peak_x, _peak_y, _is_strict_inc

TIERS = ["Super", "Mega", "Omg", "Legend"]
MIN_SHEAR = 5.0     # base twist 兩軸峰下限(head 最小 shearX 10°、shearY 7°)
PHI_TOL = 2e-3      # shearY峰/shearX峰 對 TWIST_PHI 的容差(g*v 4 位捨入餘裕)


def _scale_peak(anim):
    """該 anim 全 bone 的峰補償 scale max(scaleX)(無 scale 回 1.0)。"""
    vals = []
    for ch in anim.get("bones", {}).values():
        sc = _scale_frames(ch)
        if sc:
            vals.append(max(sx for (sx, sy) in sc))
    return max(vals, default=1.0)


def _twist_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "twist"]


def _dual_bones(anim):
    """≥1 bone 同時帶雙軸 shear 與 scale 通道 → dict {bone: chans}。"""
    return {bn: ch for bn, ch in anim.get("bones", {}).items()
            if _shear_xy(ch) and _scale_frames(ch)}


def _max_det_dev(ch):
    """單一 bone 內部 scale 極值的峰 |det−1|(shear/scale 同 τ 共生;無 scale 回 None)。"""
    xy = _shear_xy(ch); sc = _scale_frames(ch)
    if len(xy) < 3 or len(sc) != len(xy):
        return None
    return max(abs(_local_det(scx, scy, shx, shy) - 1.0)
              for (shx, shy), (scx, scy) in list(zip(xy, sc))[1:-1])


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    ttc = TV.twist_cycles_for(GENRE)
    # base = 體積守恆 base twist(無檔位);anims = 帶檔位 + 段數 + 體積守恆
    base = G.build_animations(skel, sb, twist_volume=True)
    anims = G.build_animations(skel, sb, tier_gains=gains, tier_twist_cycles=ttc, twist_volume=True)
    twist_beats = _twist_beats(base)
    R = {}

    # ---- VTT1 present + backward-compat ----
    s1 = {"twist_beats": twist_beats, "base_weak": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "anisotropic": [], "misrouted": [],
          "base_changed": [], "super_ne_base": []}
    for tb in twist_beats:
        if _peak_x(base[tb]) < MIN_SHEAR or _peak_y(base[tb]) < MIN_SHEAR or not _dual_bones(base[tb]):
            s1["base_weak"].append(tb)
        for t in TIERS:
            vk = "{}__{}".format(tb, t)
            an = anims.get(vk)
            if an is None:
                s1["missing"].append(vk); continue
            if not SA.all_finite(an):
                s1["not_finite"].append(vk)
            if not an.get("bones"):
                s1["no_bones"].append(vk)
            if not _dual_bones(an):
                s1["variant_no_dual"].append(vk)
            for bn, ch in an.get("bones", {}).items():
                if any(abs(sx - sy) > 1e-6 for (sx, sy) in _scale_frames(ch)):
                    s1["anisotropic"].append("{}::{}".format(vk, bn))
            if G.beat_category(vk) != "twist":
                s1["misrouted"].append((vk, G.beat_category(vk)))
        # Super(g=1.0)逐位元 == base twist vol
        if json.dumps(anims.get("{}__Super".format(tb)), sort_keys=True) != \
           json.dumps(base[tb], sort_keys=True):
            s1["super_ne_base"].append(tb)
    for k in base:  # base(含 In/Loop/Out + base twist vol)帶/不帶 tier_gains 逐位元不變
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            s1["base_changed"].append(k)
    s1_pass = (bool(twist_beats) and not any(s1[k] for k in
               ["base_weak", "missing", "not_finite", "no_bones", "variant_no_dual",
                "anisotropic", "misrouted", "base_changed", "super_ne_base"]))
    R["VTT1_present_backward_compat"] = {**s1, "pass": s1_pass}

    # ---- VTT2 crux: volume conservation per tier + compensation-scale/shear-peak monotone ----
    s2 = {"beats": {}, "bad_volume": [], "fail_scale_mono": [], "fail_shear_mono": [], "fail_base": []}
    for tb in twist_beats:
        # (a) 每檔位每 bone 每內部極值守恆
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                dev = _max_det_dev(ch)
                if dev is not None and dev > TOL_DET:
                    s2["bad_volume"].append("{}__{}::{}".format(tb, t, bn))
        # (b) 峰補償 scale / 峰 shearX 隨檔位嚴格遞增,Super==base
        s_peaks = [_scale_peak(anims["{}__{}".format(tb, t)]) for t in TIERS]
        x_peaks = [_peak_x(anims["{}__{}".format(tb, t)]) for t in TIERS]
        base_s, base_x = _scale_peak(base[tb]), _peak_x(base[tb])
        s2["beats"][tb] = {"scale_peaks": [round(v, 4) for v in s_peaks],
                           "shearX_peaks": [round(v, 3) for v in x_peaks],
                           "base_scale": round(base_s, 4), "base_shearX": round(base_x, 3),
                           "scale_mono": _is_strict_inc(s_peaks), "shear_mono": _is_strict_inc(x_peaks),
                           "super_eq_base": abs(s_peaks[0] - base_s) <= 1e-4 and abs(x_peaks[0] - base_x) <= 1e-4}
        if not _is_strict_inc(s_peaks):
            s2["fail_scale_mono"].append(tb)
        if not _is_strict_inc(x_peaks):
            s2["fail_shear_mono"].append(tb)
        if not (abs(s_peaks[0] - base_s) <= 1e-4 and abs(x_peaks[0] - base_x) <= 1e-4):
            s2["fail_base"].append(tb)
    s2_pass = (bool(s2["beats"]) and not s2["bad_volume"] and not s2["fail_scale_mono"]
               and not s2["fail_shear_mono"] and not s2["fail_base"])
    R["VTT2_conserved_monotone"] = {**s2, "pass": s2_pass}

    # ---- VTT3 crux neg-control: per-axis linear amplify breaks vs recompute keeps ----
    s3 = {"linear_max_dev": {}, "recompute_max_dev": {}, "linear_broke": [], "recompute_kept": []}
    gL = gains["Legend"]
    for tb in twist_beats:
        for bn, ch in base[tb].get("bones", {}).items():
            if not (_shear_xy(ch) and _scale_frames(ch)):
                continue
            lin = TV.amplify_bone_tl(ch, gL, coupled=False, twist_vol=False)   # 逐軸線性(負對照)
            rec = TV.amplify_bone_tl(ch, gL, coupled=False, twist_vol=True)    # 依放大後 shear 重算(對照)
            n_dev, c_dev = _max_det_dev(lin), _max_det_dev(rec)
            key = "{}::{}".format(tb, bn)
            s3["linear_max_dev"][key] = round(n_dev, 5) if n_dev is not None else None
            s3["recompute_max_dev"][key] = round(c_dev, 6) if c_dev is not None else None
            if n_dev is not None and n_dev > TOL_DET:       # 線性應破守恆(負對照生效)
                s3["linear_broke"].append(key)
            if c_dev is not None and c_dev <= TOL_DET:      # 重算應守恆(對照)
                s3["recompute_kept"].append(key)
    n_dual = len(s3["linear_max_dev"])
    # 重算單元測:依放大後 shear → det≡1 且 s 隨 g 增大(非線性)
    unit_sh = [{"time": 0.0, "x": 0.0, "y": 0.0}, {"time": 0.3, "x": 16.0, "y": -11.2},
               {"time": 0.6, "x": -8.0, "y": 5.6}, {"time": 0.9, "x": 0.0, "y": 0.0}]
    unit_sc = [{"time": 0.0, "x": 1.0, "y": 1.0}, {"time": 0.3, "x": 1.0603, "y": 1.0603},
               {"time": 0.6, "x": 1.0148, "y": 1.0148}, {"time": 0.9, "x": 1.0, "y": 1.0}]
    b1 = TV.amplify_bone_tl({"shear": unit_sh, "scale": unit_sc}, 1.0, twist_vol=True)
    b2 = TV.amplify_bone_tl({"shear": unit_sh, "scale": unit_sc}, gL, twist_vol=True)
    u_det1 = _max_det_dev(b1); u_det2 = _max_det_dev(b2)
    u_s1 = max(f["x"] for f in b1["scale"]); u_s2 = max(f["x"] for f in b2["scale"])
    unit_ok = (u_det1 is not None and u_det1 <= TOL_DET and u_det2 is not None and u_det2 <= TOL_DET
               and u_s2 > u_s1 + 1e-6)
    s3["recompute_unit"] = {"det_g1": round(u_det1, 6), "det_gL": round(u_det2, 6),
                            "s_g1": round(u_s1, 4), "s_gL": round(u_s2, 4), "pass": unit_ok}
    s3_pass = (n_dual >= 1 and len(s3["linear_broke"]) == n_dual
               and len(s3["recompute_kept"]) == n_dual and unit_ok)
    R["VTT3_crux_linear_breaks_volume"] = {**s3, "n_dual_bones": n_dual, "pass": s3_pass}

    # ---- VTT4 dual-axis counter-phase damped + phi ratio + identity interface per tier ----
    s4 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "not_counterphase": [],
          "bad_ratio": [], "bad_interface": [], "shear_ends_nonzero": [], "scale_ends_nonident": [],
          "ratio_detail": {}}
    for tb in twist_beats:
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]; end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                s4["bad_interface"].append("{}__{}".format(tb, t))
            for bn, ch in an.get("bones", {}).items():
                # 兩軸各自阻尼振盪
                for axis, vals in (("x", _shear_x(ch)), ("y", _shear_y(ch))):
                    if not vals:
                        continue
                    key = "{}__{}::{}::{}".format(tb, t, bn, axis)
                    if not (abs(vals[0]) < 1e-6 and abs(vals[-1]) < 1e-6):
                        s4["bad_endpoints"].append(key)
                    if _sign_changes_zero(vals) < 3:
                        s4["few_sign_changes"].append(key)
                    if not _extrema_mags_decreasing(vals):
                        s4["not_damped"].append(key)
                # 反相耦合
                interior = _interior_shear(ch)
                if interior and _has_shear_y(ch):
                    cp_ok, _dev_ok, _ = _tw3_eval(interior)
                    if not cp_ok:
                        s4["not_counterphase"].append("{}__{}::{}".format(tb, t, bn))
                # φ 比值保形
                sx, sy = _shear_x(ch), _shear_y(ch)
                if sx and sy:
                    pkx = max(abs(v) for v in sx); pky = max(abs(v) for v in sy)
                    if pkx > 1e-9:
                        ratio = pky / pkx
                        s4["ratio_detail"]["{}__{}::{}".format(tb, t, bn)] = round(ratio, 5)
                        if abs(ratio - TWIST_PHI) > PHI_TOL:
                            s4["bad_ratio"].append(("{}__{}::{}".format(tb, t, bn), round(ratio, 5)))
                # shear/scale 端點介面
                xy = _shear_xy(ch)
                if xy and (abs(xy[0][0]) > 1e-6 or abs(xy[0][1]) > 1e-6
                           or abs(xy[-1][0]) > 1e-6 or abs(xy[-1][1]) > 1e-6):
                    s4["shear_ends_nonzero"].append("{}__{}::{}".format(tb, t, bn))
                sc = _scale_frames(ch)
                if sc and (abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6
                           or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6):
                    s4["scale_ends_nonident"].append("{}__{}::{}".format(tb, t, bn))
    s4_pass = (bool(s4["ratio_detail"]) and not any(s4[k] for k in
               ["bad_endpoints", "few_sign_changes", "not_damped", "not_counterphase",
                "bad_ratio", "bad_interface", "shear_ends_nonzero", "scale_ends_nonident"]))
    R["VTT4_signature_phi_interface"] = {**s4, "phi": TWIST_PHI, "pass": s4_pass}

    # ---- VTT5 end-to-end 3-channel pivot-fixed via build_spine --tier-variants --twist-volume --shear-pivot ----
    import build_spine
    out = "/tmp/twist_vol_tier_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, tier_variants=True,
                             twist_volume=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {}); centers = summ.get("pivot_centers", {})
    variant_beats = [nm for nm in sp_skel["animations"]
                     if "__" in nm and G.beat_category(nm.split("__")[0]) == "twist"]
    s5 = {"variant_beats": variant_beats, "checked": [], "fail_fixed": [], "fail_negctrl": [],
          "n_joint_bones": 0, "n_with_scale": 0}
    for tb in variant_beats:
        an = sp_skel["animations"][tb]
        for bn, ch in an.get("bones", {}).items():
            if bn not in joints or bn not in centers:
                continue
            O = np.array(centers[bn], float); P = np.array(joints[bn], float)
            ellP = P - O
            tr = ch.get("translate")
            if not tr:
                continue
            s5["n_joint_bones"] += 1
            if ch.get("scale"):
                s5["n_with_scale"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"bone": bn, "beat": tb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2), "has_scale": bool(ch.get("scale"))}
            s5["checked"].append(rec)
            if not (fix < TOL_FIX):
                s5["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                s5["fail_negctrl"].append(rec)
    s5_pass = (bool(variant_beats) and s5["n_joint_bones"] >= 1 and s5["n_with_scale"] >= 1
               and not s5["fail_fixed"] and not s5["fail_negctrl"])
    R["VTT5_end2end_pivot_fixed"] = {**s5, "pass": s5_pass}

    # ---- VTT6 isolation / additive / flat-gain guard ----
    s6 = {}
    # (a) 平增益守衛(隔離幅度軸,故**不帶段數** ttc):全 1.0 → 補償 scale 遞增 FALSE 且各檔位逐位元
    #     == base twist vol(補償峰 = 首極值 (1+φ)A 的 cos 反推,與 gain 無關即恆定 → 證 VTT2 的遞增純由 gain 驅動)。
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat, twist_volume=True)
    any_mono_flat, flat_base_diff = False, []
    for tb in twist_beats:
        s_peaks = [_scale_peak(flat_anims["{}__{}".format(tb, t)]) for t in TIERS]
        if _is_strict_inc(s_peaks):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(tb, t)], sort_keys=True) != \
               json.dumps(base[tb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(tb, t))
    s6["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) 隔離:非 twist 主秀 tier 變體(如 wobble shear-only)不被 twist_vol 重算波及 → 不生 scale 通道
    leak = []
    for nm, an in anims.items():
        if "__" not in nm:
            continue
        base_name = nm.split("__")[0]
        if G.beat_category(base_name) == "twist":
            continue
        base_has_scale = any(_scale_frames(ch) for ch in base.get(base_name, {}).get("bones", {}).values())
        var_has_scale = any(_scale_frames(ch) for ch in an.get("bones", {}).values())
        if var_has_scale and not base_has_scale:
            leak.append(nm)
    s6["b_isolated"] = {"leaked": leak, "pass": not leak}
    # (c) 加性:移除 twist 的 storyboard → 其餘 beat(含 wobble/squash tier 變體)逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "twist"]}
    anims_no = G.build_animations(skel, sb_no, tier_gains=gains, tier_twist_cycles=ttc, twist_volume=True)
    regressed = [nm for nm in anims_no
                 if json.dumps(anims_no[nm], sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True)]
    s6["c_additive"] = {"regressed": regressed,
                        "removed": [b["beat"] for b in sb["beats"] if G.beat_category(b["beat"]) == "twist"],
                        "pass": not regressed}
    R["VTT6_isolation_additive"] = {**s6, "pass": all(v["pass"] for v in s6.values())}

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
        for k in ["VTT1_present_backward_compat", "VTT2_conserved_monotone",
                  "VTT3_crux_linear_breaks_volume", "VTT4_signature_phi_interface",
                  "VTT5_end2end_pivot_fixed", "VTT6_isolation_additive"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("VTT2 compensation scale / shearX peaks per tier {}:".format(TIERS))
        for tb, d in R["VTT2_conserved_monotone"]["beats"].items():
            print("  {:10s} scale {}  shearX {}  (base s {}, shX {})".format(
                tb, d["scale_peaks"], d["shearX_peaks"], d["base_scale"], d["base_shearX"]))
        print("VTT3 crux linear(neg) vs recompute max |det-1| (Legend):")
        for key in R["VTT3_crux_linear_breaks_volume"]["linear_max_dev"]:
            print("  {:16s} linear {}  recompute {}".format(
                key, R["VTT3_crux_linear_breaks_volume"]["linear_max_dev"][key],
                R["VTT3_crux_linear_breaks_volume"]["recompute_max_dev"][key]))
        u = R["VTT3_crux_linear_breaks_volume"]["recompute_unit"]
        print("  unit: det g1 {} gL {}  s g1 {} gL {}".format(u["det_g1"], u["det_gL"], u["s_g1"], u["s_gL"]))
        print("VTT5 end-to-end pivot-fixed (fixed/negctrl px):")
        for rec in R["VTT5_end2end_pivot_fixed"]["checked"]:
            print("  {:20s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}  scale={}".format(
                rec["beat"] + "/" + rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"], rec["has_scale"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
