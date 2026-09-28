#!/usr/bin/env python3
"""candidate (G-4''''''-vol-tier) 自我驗收閘 — **volume-conserving twist 接檔位差異化**(純 CPU)。

candidate (G-4''''''-vol) 讓 base twist 掛一條**等向**補償 scale `s=1/√cos(shearX−shearY)` → 全域
local 行列式 `det≡1`(擰而不變面積),但明白列出 honest boundary:「**vol 僅作用 base twist**(tier 變體仍
shear-only:vol 隨檔位放大需**重算補償 scale** 以維持 det≡1,比照 squash 耦合 amplify,為後續)」。

本 chunk 補上那條缺口:讓 volume-conserving twist 的**檔位變體**(`twist__{tier}`)也維持體積守恆。
**crux(為何不能沿用既有 amplify)**:補償 scale 是 shearX/shearY 的**函式**(`s=1/√cos(shearX−shearY)`),
不是 scale 自身可線性放大的量。檔位放大 shear(shearX'=g·shearX、shearY'=g·shearY)後,兩基底夾角偏離
隨 g 變大 → `cos(shearX'−shearY')=cos(g·(shearX−shearY))` 隨 g **非線性**縮小,正確補償變成
`s'=1/√cos(g·(shearX−shearY))`。逐軸 `_amp_scale`(線性放大 identity 上方)甚至耦合倒數 `_amp_scale_coupled`
都算不出這個非線性補償 → 破守恆(實測逐軸放大 Legend |det−1| 達 0.31)。**解法**:`amplify_bone_tl` 對
volume-conserving twist 走 shear-compensated 分支 —— 先放大 shear,再**從放大後的 shear 重算**等向補償 scale
→ det≡1 於**每個檔位**由建構保證。

**crux(與 squash 耦合 amplify 的機制差異)**:squash(G-4''''')的體積守恆耦合是 scale **內部**倒數
(scaleY=1/scaleX,永不讀 shear);twist-vol 的補償是**跨通道**(scale 從放大後的 shear 重算)。兩者皆維持
det≡1 但**不同源** —— 同一守恆目標,squash 走 scale-內部非均勻倒數、twist 走從 shear 重算的等向補償;
scale 的「語意角色」(自己是擠壓 vs 補償別人)決定放大機制。

真值界定同 twist 系列(E/H/I/J/G-4'/G-4''''/G-4''''''/-tier/-count/-vol):主秀運動無唯一正解(PROPOSAL 手感),
閘驗**客觀結構簽章**(兩軸峰遞增 + φ 逐檔不變 + 體積守恆 + 阻尼反相簽章 + 端到端不動點)非美感;
負對照證鑑別力(閘可信)。從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(..., tier_gains,
twist_volume=True)` 端到端量。

AC(客觀、可量測):
  VVT1 present + backward-compat  : base twist(vol)帶雙軸 shear + 等向 scale;每檔位 `twist__{tier}` 皆
                                   產出、finite、有 bone、≥1 bone **同時**帶雙軸 shear **與**等向 scale、名經
                                   `beat_category` 仍路由回 twist;**Super(g=1)逐位元 == base twist(vol)**;
                                   base(含 In/Loop/Out + base twist)帶/不帶 tier_gains 逐位元不變;
                                   **`twist_volume=False` → twist 檔位變體逐位元 == shear-only 檔位變體**(無 scale 通道)。
  VVT2 crux — 體積守恆 per tier   : **每個檔位**每 twist bone 每內部極值幀,全域 local 行列式 |det−1| ≤ TOL_DET
                                   (**擰而不變面積**於每個檔位);**負對照** = 對 vol base scale 施**逐軸線性**放大
                                   (`shear_compensated=False`)→ 高檔位 |det−1| ≥ MIN_BREAK(破守恆)→ 證閘測
                                   「真體積守恆(重算補償)」非「有 scale 通道即可」。
  VVT3 兩軸峰遞增 + φ + 等向 + 補償遞增: 各檔位峰 |shearX|、|shearY| 皆 Super<Mega<Omg<Legend 嚴格遞增(Super==base);
                                   每 twist bone 每檔位 shearY峰/shearX峰 ≈ TWIST_PHI(逐檔不變);scale 每檔位**等向**
                                   (scaleX==scaleY);**補償 scale 峰**隨檔位嚴格遞增(擰愈狠 → 等向補償愈大,scale 通道的檔位簽章)。
  VVT4 阻尼反相簽章保形 per tier   : **每個檔位**每 twist bone 的 shearX **與** shearY 各自(a)首尾 0(b)繞 0 變號 ≥3
                                   (c)相繼極值遞減(阻尼);且每內部極值反號(反相耦合,復用 TW3 判準)。
  VVT5 端到端三通道 pivot 不動     : `build_spine --tier-variants --twist-volume --shear-pivot`(真實 robot)產
                                   `twist__{tier}` 帶 shear+scale+rotate 補償;凡有關節 pivot 的 bone,pivot 殘差
                                   < TOL_FIX;內建負對照 = 未補償(繞件中心)大位移 → 三通道(含補償 scale)皆錨在 pivot。
  VVT6 負對照/隔離/正交            : (a)**平增益守衛**:增益全 1.0 → VVT3 兩軸遞增 FALSE 且各檔位 == base twist(vol);
                                   (b)**機制隔離**:twist(vol)檔位變體 scale **等向**(shear-compensated 重算)、squash
                                   檔位變體 scale **非均勻**(scale-內部耦合倒數)→ 兩種守恆機制不外洩;wobble 檔位變體
                                   仍 shear-only(無 scale);(c)**段數正交**:`twist_volume=True` + `tier_twist_cycles`
                                   → 扭轉段數 [4,5,6,7] 隨檔位遞增 **且**每檔位每擠壓極值仍體積守恆(段數×幅度×體積守恆三效正交)。

用法:
  python3 validate_twist_vol_tier.py            # 摘要
  python3 validate_twist_vol_tier.py --json     # 完整 JSON
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
# 復用 twist 系列閘的讀取/阻尼/反相判準,確保與 twist-gen/-tier/-count/-vol 完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_shear_pivot import _world
from validate_twist_gen import (_shear_y, _shear_xy, _interior_shear, _tw3_eval,
                                _has_shear_y, _is_ident, TOL_FIX, MIN_NEG, NEG_RATIO)
from validate_twist_volume import _scale_frames, _local_det, TOL_DET

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
MIN_SHEAR = 5.0      # 度,base twist 兩軸峰下限(head 最小:shearX 10°、shearY 7°)
PHI_TOL = 2e-3       # shearY峰/shearX峰 對 TWIST_PHI 的容差(g*v 4 位捨入下的餘裕)
MIN_BREAK = 0.02     # 負對照(逐軸線性放大)高檔位 |det−1| 下限(實測 Legend 0.31、Omg 0.16 → 充足餘裕)


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/twist_vol_tier_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _twist_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "twist"]


def _peak_x(anim):
    ps = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(ps, default=0.0)


def _peak_y(anim):
    ps = [max(abs(v) for v in _shear_y(ch)) for ch in anim.get("bones", {}).values() if _shear_y(ch)]
    return max(ps, default=0.0)


def _peak_scale(anim):
    """該 anim 全 bone 補償 scale 的峰值(等向 → 取 scaleX 峰;無 scale 回 0)。"""
    ps = [max(sx for (sx, sy) in _scale_frames(ch)) for ch in anim.get("bones", {}).values()
          if _scale_frames(ch)]
    return max(ps, default=0.0)


def _is_strict_inc(xs):
    return all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb, twist_volume=True)                       # base 帶 vol,無檔位
    anims = G.build_animations(skel, sb, tier_gains=gains, twist_volume=True)     # 帶檔位 + vol
    off = G.build_animations(skel, sb, tier_gains=gains)                          # twist_volume=False(shear-only 檔位變體)
    twist_beats = _twist_beats(base)
    R = {}

    # ---- VVT1 present + backward-compat ----
    t1 = {"twist_beats": twist_beats, "base_weak": [], "base_no_scale": [], "missing": [],
          "not_finite": [], "no_bones": [], "variant_no_shear": [], "variant_no_scale": [],
          "variant_anisotropic": [], "misrouted": [], "base_changed": [], "super_ne_base": [],
          "off_has_scale": [], "off_ne_shearonly": []}
    for tb in twist_beats:
        if _peak_x(base[tb]) < MIN_SHEAR or _peak_y(base[tb]) < MIN_SHEAR:
            t1["base_weak"].append(tb)
        if not any(_scale_frames(ch) for ch in base[tb].get("bones", {}).values()):
            t1["base_no_scale"].append(tb)
        # Super(g=1)逐位元 == base twist(vol)
        if json.dumps(base[tb], sort_keys=True) != json.dumps(anims.get(tb + "__Super"), sort_keys=True):
            t1["super_ne_base"].append(tb)
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
                    t1["variant_anisotropic"].append("{}::{}".format(vk, bn))
            if G.beat_category(vk) != "twist":
                t1["misrouted"].append((vk, G.beat_category(vk)))
            # twist_volume=False → 檔位變體無 scale 通道且逐位元 == shear-only
            off_an = off.get(vk)
            if off_an and any(_scale_frames(ch) for ch in off_an.get("bones", {}).values()):
                t1["off_has_scale"].append(vk)
    # base(含 In/Loop/Out + base twist,皆 twist_volume=True)帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    # off(twist_volume=False)== 顯式 twist_volume=False(健全性,兩者應同)
    off2 = G.build_animations(skel, sb, tier_gains=gains, twist_volume=False)
    if json.dumps(off, sort_keys=True) != json.dumps(off2, sort_keys=True):
        t1["off_ne_shearonly"].append("default_vs_explicit_false")
    t1_pass = (bool(twist_beats) and not any(t1[k] for k in
               ["base_weak", "base_no_scale", "missing", "not_finite", "no_bones",
                "variant_no_shear", "variant_no_scale", "variant_anisotropic", "misrouted",
                "base_changed", "super_ne_base", "off_has_scale", "off_ne_shearonly"]))
    R["VVT1_present_backward_compat"] = {**t1, "pass": t1_pass}

    # ---- VVT2 crux: volume conservation per tier + naive-amplify negative control ----
    t2 = {"break_conserve": [], "neg_not_break": [], "detail": {}}
    for tb in twist_beats:
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            # 帶補償(shear-compensated 重算)→ det≡1
            dev_vol = []
            for bn, ch in an.get("bones", {}).items():
                xy = _shear_xy(ch); sc = _scale_frames(ch)
                if len(xy) < 3 or len(sc) != len(xy):
                    continue
                for (shx, shy), (scx, scy) in list(zip(xy, sc))[1:-1]:
                    dev_vol.append(abs(_local_det(scx, scy, shx, shy) - 1.0))
            # 負對照:對 base vol scale 施**逐軸線性**放大(shear_compensated=False)→ 破守恆
            naive = TV.amplify_anim(base[tb], gains[t], coupled=False, shear_compensated=False)
            dev_naive = []
            for bn, ch in naive.get("bones", {}).items():
                xy = _shear_xy(ch); sc = _scale_frames(ch)
                if len(xy) < 3 or len(sc) != len(xy):
                    continue
                for (shx, shy), (scx, scy) in list(zip(xy, sc))[1:-1]:
                    dev_naive.append(abs(_local_det(scx, scy, shx, shy) - 1.0))
            mv = max(dev_vol, default=0.0)
            mn = max(dev_naive, default=0.0)
            t2["detail"]["{}__{}".format(tb, t)] = {"max_dev_vol": round(mv, 6),
                                                    "max_dev_naive": round(mn, 5)}
            if mv > TOL_DET:
                t2["break_conserve"].append("{}__{}".format(tb, t))
            # Super(g=1)naive 也≈守恆(g=1 無放大)→ 只要求高檔位(g>1)破守恆
            if gains[t] > 1.0 + 1e-9 and mn < MIN_BREAK:
                t2["neg_not_break"].append("{}__{}".format(tb, t))
    t2_pass = (bool(t2["detail"]) and not t2["break_conserve"] and not t2["neg_not_break"])
    R["VVT2_volume_conserved_per_tier"] = {**t2, "pass": t2_pass}

    # ---- VVT3 dual-axis peak monotone + phi invariant + isotropic + compensation-scale monotone ----
    t3 = {"beats": {}, "fail_mono_x": [], "fail_mono_y": [], "fail_super": [],
          "bad_ratio": [], "fail_scale_mono": [], "ratio_detail": {}}
    for tb in twist_beats:
        px = [_peak_x(anims["{}__{}".format(tb, t)]) for t in TIERS]
        py = [_peak_y(anims["{}__{}".format(tb, t)]) for t in TIERS]
        ps = [_peak_scale(anims["{}__{}".format(tb, t)]) for t in TIERS]
        bx, by = _peak_x(base[tb]), _peak_y(base[tb])
        super_eq = abs(px[0] - bx) <= 1e-4 and abs(py[0] - by) <= 1e-4
        t3["beats"][tb] = {"shearX_peaks": [round(p, 3) for p in px],
                           "shearY_peaks": [round(p, 3) for p in py],
                           "scale_peaks": [round(p, 4) for p in ps],
                           "mono_x": _is_strict_inc(px), "mono_y": _is_strict_inc(py),
                           "scale_mono": _is_strict_inc(ps), "super_eq_base": super_eq}
        if not _is_strict_inc(px):
            t3["fail_mono_x"].append(tb)
        if not _is_strict_inc(py):
            t3["fail_mono_y"].append(tb)
        if not _is_strict_inc(ps):
            t3["fail_scale_mono"].append(tb)
        if not super_eq:
            t3["fail_super"].append(tb)
        # φ ratio per bone per tier(等向已在 VVT1 驗;此處驗 φ)
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
                key = "{}__{}::{}".format(tb, t, bn)
                t3["ratio_detail"][key] = round(ratio, 5)
                if abs(ratio - TWIST_PHI) > PHI_TOL:
                    t3["bad_ratio"].append((key, round(ratio, 5)))
    t3_pass = (bool(t3["beats"]) and not t3["fail_mono_x"] and not t3["fail_mono_y"]
               and not t3["fail_scale_mono"] and not t3["fail_super"] and not t3["bad_ratio"])
    R["VVT3_peaks_phi_iso_comp"] = {**t3, "phi": TWIST_PHI, "pass": t3_pass}

    # ---- VVT4 dual-axis damped counter-phase signature preserved per tier ----
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
    t4_pass = not any(t4[k] for k in ["bad_endpoints", "few_sign_changes",
                                      "not_damped", "not_counterphase"])
    R["VVT4_damped_counterphase_per_tier"] = {**t4, "pass": t4_pass}

    # ---- VVT5 end-to-end 3-channel pivot-fixed per tier ----
    import build_spine
    out = "/tmp/twist_vol_tier_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, tier_variants=True,
                             twist_volume=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    tier_twist = [nm for nm in sp_skel["animations"]
                  if "__" in nm and G.beat_category(nm.split("__")[0]) == "twist"]
    s5 = {"tier_twist_anims": tier_twist, "checked": 0, "fail_fixed": [], "fail_negctrl": [],
          "n_joint_bones": 0, "n_with_scale": 0, "worst_fixed": 0.0}
    for nm in tier_twist:
        an = sp_skel["animations"][nm]
        for bn, ch in an.get("bones", {}).items():
            if bn not in joints or bn not in centers:
                continue
            tr = ch.get("translate")
            if not tr:
                continue
            O = np.array(centers[bn], float); P = np.array(joints[bn], float)
            ellP = P - O
            s5["n_joint_bones"] += 1
            if ch.get("scale"):
                s5["n_with_scale"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 200 for i in range(201)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            s5["checked"] += 1
            s5["worst_fixed"] = max(s5["worst_fixed"], fix)
            rec = {"anim": nm, "bone": bn, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            if not (fix < TOL_FIX):
                s5["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                s5["fail_negctrl"].append(rec)
    s5["worst_fixed"] = round(s5["worst_fixed"], 4)
    s5_pass = (s5["n_joint_bones"] >= 1 and s5["n_with_scale"] >= 1
               and not s5["fail_fixed"] and not s5["fail_negctrl"])
    R["VVT5_end2end_pivot_fixed"] = {**s5, "pass": s5_pass}

    # ---- VVT6 neg-control / isolation / orthogonality ----
    s6 = {}
    # (a) 平增益守衛:增益全 1.0 → 兩軸峰不遞增 且 各檔位 == base twist(vol)
    flat = {t: 1.0 for t in TIERS}
    anims_flat = G.build_animations(skel, sb, tier_gains=flat, twist_volume=True)
    flat_mono = any(_is_strict_inc([_peak_x(anims_flat["{}__{}".format(tb, t)]) for t in TIERS])
                    for tb in twist_beats)
    flat_all_eq = all(json.dumps(anims_flat["{}__{}".format(tb, t)], sort_keys=True)
                      == json.dumps(base[tb], sort_keys=True)
                      for tb in twist_beats for t in TIERS)
    s6["a_flat_gain_guard"] = {"flat_gain_monotone": flat_mono, "flat_all_eq_base": flat_all_eq,
                               "pass": (not flat_mono) and flat_all_eq}
    # (b) 機制隔離:twist(vol)檔位變體 scale 等向;squash 檔位變體 scale 非均勻;wobble 檔位變體無 scale
    sq_beats = [nm for nm in base if "__" not in nm and G.beat_category(nm) == "squash"]
    wb_beats = [nm for nm in base if "__" not in nm and G.beat_category(nm) == "wobble"]
    tw_iso = all(abs(sx - sy) <= 1e-6
                 for tb in twist_beats for t in TIERS
                 for ch in anims["{}__{}".format(tb, t)].get("bones", {}).values()
                 for (sx, sy) in _scale_frames(ch))
    sq_aniso = any(abs(sx - sy) > 1e-6
                   for sq in sq_beats for t in TIERS
                   for ch in anims["{}__{}".format(sq, t)].get("bones", {}).values()
                   for (sx, sy) in _scale_frames(ch))
    wb_noscale = all(not _scale_frames(ch)
                     for wb in wb_beats for t in TIERS
                     for ch in anims["{}__{}".format(wb, t)].get("bones", {}).values())
    s6["b_mechanism_isolation"] = {"twist_tier_isotropic": tw_iso,
                                   "squash_tier_nonuniform": sq_aniso,
                                   "wobble_tier_no_scale": wb_noscale,
                                   "squash_beats": sq_beats, "wobble_beats": wb_beats,
                                   "pass": tw_iso and sq_aniso and wb_noscale}
    # (c) 段數×幅度×體積守恆三效正交:twist_volume + tier_twist_cycles → 段數遞增 且每檔位仍守恆
    ttc = TV.twist_cycles_for(GENRE)
    anims_cnt = G.build_animations(skel, sb, tier_gains=gains, tier_twist_cycles=ttc, twist_volume=True)

    def _nseg(anim):
        # 該 anim 全 bone shearX 內部極值最多者的段數(= sign changes + 1 的近似;直接數 shearX 非零極值)
        best = 0
        for ch in anim.get("bones", {}).values():
            xs = _shear_x(ch)
            if xs:
                best = max(best, sum(1 for v in xs[1:-1] if abs(v) > 1e-9))
        return best
    seg_counts, cnt_break = [], []
    for tb in twist_beats:
        segs = [_nseg(anims_cnt["{}__{}".format(tb, t)]) for t in TIERS]
        seg_counts.append((tb, segs))
        # 每檔位每內部極值仍守恆
        for t in TIERS:
            an = anims_cnt["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                xy = _shear_xy(ch); sc = _scale_frames(ch)
                if len(xy) < 3 or len(sc) != len(xy):
                    continue
                for (shx, shy), (scx, scy) in list(zip(xy, sc))[1:-1]:
                    if abs(_local_det(scx, scy, shx, shy) - 1.0) > TOL_DET:
                        cnt_break.append("{}__{}::{}".format(tb, t, bn))
    seg_mono = all(_is_strict_inc(segs) for (_tb, segs) in seg_counts)
    s6["c_count_orthogonal"] = {"seg_counts": seg_counts, "seg_monotone": seg_mono,
                                "cnt_break_conserve": cnt_break,
                                "pass": seg_mono and not cnt_break}
    R["VVT6_neg_isolation_orthogonal"] = {**s6, "pass": all(v["pass"] for v in s6.values())}

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
        for k in ["VVT1_present_backward_compat", "VVT2_volume_conserved_per_tier",
                  "VVT3_peaks_phi_iso_comp", "VVT4_damped_counterphase_per_tier",
                  "VVT5_end2end_pivot_fixed", "VVT6_neg_isolation_orthogonal"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("VVT2 det per tier:", json.dumps(R["VVT2_volume_conserved_per_tier"]["detail"], ensure_ascii=False))
        print("VVT3 beats:", json.dumps(R["VVT3_peaks_phi_iso_comp"]["beats"], ensure_ascii=False))
        print("VVT5 worst pivot residual px:", R["VVT5_end2end_pivot_fixed"]["worst_fixed"],
              "| checked:", R["VVT5_end2end_pivot_fixed"]["checked"],
              "| with scale:", R["VVT5_end2end_pivot_fixed"]["n_with_scale"])
        print("VVT6 (a) flat mono:", R["VVT6_neg_isolation_orthogonal"]["a_flat_gain_guard"]["flat_gain_monotone"],
              "eq base:", R["VVT6_neg_isolation_orthogonal"]["a_flat_gain_guard"]["flat_all_eq_base"],
              "| (b) twist iso:", R["VVT6_neg_isolation_orthogonal"]["b_mechanism_isolation"]["twist_tier_isotropic"],
              "squash aniso:", R["VVT6_neg_isolation_orthogonal"]["b_mechanism_isolation"]["squash_tier_nonuniform"],
              "| (c) seg mono:", R["VVT6_neg_isolation_orthogonal"]["c_count_orthogonal"]["seg_monotone"])
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
