#!/usr/bin/env python3
"""candidate G-4''''''-vol-tier 自我驗收閘 — **volume-conserving twist 接檔位差異化**(純 CPU)。

一路的 honest boundary:G-4''''''-vol(`validate_twist_volume.py`)讓 twist 掛一條**等向**補償 scale
`s = 1/√cos(shearX − shearY)` 使全域 local 行列式 `det ≡ 1`(擰而不變面積),但當時 **vol 只作用 base twist**
—— tier 變體仍 shear-only:因為 (J) 的幅度增益對 scale 用**逐軸** `_amp_scale`(線性放大 identity 上方),
對 twist 的等向補償 scale 會給 `1 + g·(s−1)` ≠ `1/√cos(g·(shearX−shearY))`(cos 非線性)→ **破壞體積守恆**
(同 squash 當初逐軸破守恆的 honest boundary)。故「檔位愈高擰愈狠、面積仍守恆」這個本該有的檔位簽章,
vol twist 一直沒有(又一「檔位機制就緒 ≠ 每個新通道接上」缺口,同 E/H/I/J/G-4'/G-4''/G-4''''')。

本次(G-4''''''-vol-tier)補上:tier 放大 shear(兩軸同一 g → 扭角差 `g·(shearX−shearY)`)後,補償 scale 由
`tier_variants._twist_vol_scale` 從**放大後 shear** 逐幀重算 `s'=1/√cos(g·(shearX−shearY))` → 每檔位
`det = s'²·cos(g·(shearX−shearY)) ≡ 1`(體積守恆在任一檔位保持),而 shear 兩軸峰隨檔位嚴格遞增、φ 比值不變。
crux(與 squash 耦合 amplify 的差異):squash 的補償**非均勻**(scaleX·scaleY≡1,scale 自己即擠壓);twist 的補償
**等向**(scaleX==scaleY,scale 純補償 shear)→ 同一守恆目標、不同源機制。且從**實際存下的放大後 shear** 重算
(非從舊 scale 值反推),與 runtime 用的 shear 精確配對 → det 殘差同 base 級(不隨 g 疊大)、Super(g=1)逐位元同 base。

真值界定同 twist 系列(E/H/I/J/G-4'…):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章**
(每檔位體積守恆 + 雙軸峰遞增 + 反相阻尼 + φ 不變)非美感;crux 負對照(TVT5:逐軸 amplify 破守恆)證
重算補償的必要性與閘的鑑別力。從**先驗庫**(slot_bigwin) → **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains=…, twist_volume=True)` 端到端量。

AC(客觀、可量測):
  TVT1 present + backward-compat : base twist(vol)雙通道(shear+等向 scale);每檔位 `twist__{tier}` 皆產出、
                                  finite、有 bone、≥1 bone **同時**帶 shear+scale 且 scale **等向**、名經
                                  `beat_category` 仍路由回 twist;**base(In/Loop/Out + base twist(vol))逐位元
                                  不變**(帶/不帶 tier_gains,twist_volume=True 下相同);**Super(g=1.0)逐位元 ==
                                  base twist(vol)**(重算補償於 g=1、base shear 皆 4-dec 精確 → identity)。
  TVT2 crux — 每檔位守恆 + 雙軸峰遞增: **每個檔位**的 twist bone,其每個內部極值幀全域 local |det−1|≤TOL_DET
                                  (`transform_matrix_full` 帶 shearX/shearY/scaleX/scaleY)—— 體積守恆在檔位放大下
                                  仍保持;且 shearX 峰**與** shearY 峰皆 Super<Mega<Omg<Legend **嚴格遞增**
                                  (雙軸檔位簽章),Super 峰 == base 峰(向後相容)。
  TVT3 雙軸反相阻尼 + φ 保形     : **每個檔位**每 twist bone,shearX 與 shearY 各自(a)首尾 0(b)繞 0 變號≥3
                                  (c)相繼極值遞減(阻尼);每內部極值反號(反相耦合);且 φ = 峰shearY/峰shearX
                                  ≈ TWIST_PHI 逐檔不變(單一-g 對兩軸同比 → 補償 scale 不擾 shear 比值)。
  TVT4 identity 介面(可插 Loop) : 每檔位 sample(0)/sample(dur) identity;shear 首尾 (0,0)、scale 首尾 (1,1)。
  TVT5 crux 負對照 — 逐軸破守恆   : 對 base twist(vol)施**逐軸** amplify(`amplify_bone_tl(twist_vol=False)`,Legend
                                  增益 → scale 走線性 `_amp_scale`)→ ≥1 內部極值 |det−1| **> TOL_DET**(線性補償
                                  對不上放大後 shear 的 cos → 破守恆);對照 `twist_vol=True` 同增益仍守恆 → 證重算
                                  補償的必要性與閘測「守恆」非恆真;附 `_twist_vol_scale` 單元(shear=0→s=1、
                                  shear≠0→s>1 且 s²·cos≡1)。
  TVT6 隔離/加性/三效正交/端到端  : (a)**平增益守衛**:增益階梯全 1.0 → TVT2 雙軸峰遞增 FALSE 且各檔位 twist 逐位元
                                  == base;(b)**等向隔離**:twist tier 變體 scale 皆等向(scaleX==scaleY),且非
                                  twist 主秀 tier 變體(如 wobble,shear-only)不冒出 scale 通道;(c)**加性**:移除
                                  twist 的 storyboard → 其餘 beat(含 wobble tier 變體)逐位元不變;(d)**三效正交**:
                                  tier_gains × tier_twist_cycles × twist_volume 併用 → 每檔位段數遞增(4→7)且
                                  每內部極值仍 |det−1|≤TOL_DET(段數×幅度×體積守恆三效可疊);(e)**端到端**:
                                  `build_spine --tier-variants --twist-volume --shear-pivot`(真實 robot)每檔位
                                  twist 變體帶 shear+scale+rotate,凡有關節 pivot 的 bone pivot 殘差 < TOL_FIX,
                                  內建負對照(繞件中心)大位移。

用法:
  python3 validate_twist_volume_tier.py            # 摘要
  python3 validate_twist_volume_tier.py --json     # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from beat_templates import TWIST_PHI
from analyze_target import analyze
from pivot_rotation import transform_matrix_full
# 復用 twist 系列閘的讀取與阻尼/反相判準,確保與 twist-gen/tier/count/volume 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_shear_pivot import _world
from validate_twist_gen import (_shear_y, _shear_xy, _interior_shear, _tw3_eval,
                                _has_shear_y, _is_ident, TOL_FIX, MIN_NEG, NEG_RATIO)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
TOL = 1e-4
TOL_DET = 2e-4       # |det−1| 上限(重算補償實測 ≤1e-4 各檔位;逐軸負對照 >0.02 → >200× 鑑別餘裕;同 twist_volume TV2)
MIN_SHEAR = 5.0      # 度,base twist 兩軸峰下限(head 最小:shearX 10°、shearY 7°)
PHI_TOL = 2e-3       # 峰shearY/峰shearX 對 TWIST_PHI 的容差(g*v 4 位捨入餘裕;同 twist_tier)
MIN_SHRINK = 0.02    # 逐軸負對照 |det−1| 下限(證破守恆)


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


def _scale_frames(chans):
    fr = chans.get("scale")
    return [(f["x"], f["y"]) for f in fr] if fr else []


def _local_det(scaleX, scaleY, shx, shy):
    a, b, c, d = transform_matrix_full(0.0, scaleX, scaleY, shx, shy)
    return a * d - b * c


def _peak_x(anim):
    ps = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(ps, default=0.0)


def _peak_y(anim):
    ps = [max(abs(v) for v in _shear_y(ch)) for ch in anim.get("bones", {}).values() if _shear_y(ch)]
    return max(ps, default=0.0)


def _dual_bones(anim):
    """≥1 bone 同時帶 shear 與 scale 通道 → dict {bone: chans}。"""
    return {bn: ch for bn, ch in anim.get("bones", {}).items() if _shear_xy(ch) and _scale_frames(ch)}


def _is_strict_inc(xs):
    return len(xs) >= 2 and all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def _interior_pairs(ch):
    """去首尾的 (shearX, shearY, scaleX, scaleY) 內部極值(shear/scale 同 τ 同索引)。"""
    xy = _shear_xy(ch); sc = _scale_frames(ch)
    if len(xy) < 3 or len(sc) != len(xy):
        return []
    return [(shx, shy, scx, scy) for (shx, shy), (scx, scy) in list(zip(xy, sc))[1:-1]]


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb, twist_volume=True)                    # base twist(vol),tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains, twist_volume=True) # 帶檔位 + vol
    twist_beats = _twist_beats(base)
    R = {}

    # ---- TVT1 present + backward-compat ----
    t1 = {"twist_beats": twist_beats, "base_weak": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "anisotropic": [], "misrouted": [],
          "base_changed": [], "super_ne_base": []}
    for tb in twist_beats:
        if _peak_x(base[tb]) < MIN_SHEAR or _peak_y(base[tb]) < MIN_SHEAR \
           or not any(_scale_frames(ch) for ch in base[tb].get("bones", {}).values()):
            t1["base_weak"].append(tb)
        for t in TIERS:
            vk = "{}__{}".format(tb, t)
            an = anims.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            if not an.get("bones"):
                t1["no_bones"].append(vk)
            if not _dual_bones(an):
                t1["variant_no_dual"].append(vk)
            for bn, ch in an.get("bones", {}).items():
                if any(abs(sx - sy) > 1e-6 for (sx, sy) in _scale_frames(ch)):
                    t1["anisotropic"].append("{}::{}".format(vk, bn))
            if G.beat_category(vk) != "twist":
                t1["misrouted"].append((vk, G.beat_category(vk)))
        if json.dumps(anims.get("{}__Super".format(tb)), sort_keys=True) != \
           json.dumps(base[tb], sort_keys=True):
            t1["super_ne_base"].append(tb)
    for k in base:  # base(含 In/Loop/Out + base twist(vol))帶/不帶 tier_gains 逐位元不變
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    t1_pass = (bool(twist_beats) and not any(t1[k] for k in
               ["base_weak", "missing", "not_finite", "no_bones", "variant_no_dual",
                "anisotropic", "misrouted", "base_changed", "super_ne_base"]))
    R["TVT1_present_backward_compat"] = {**t1, "pass": t1_pass}

    # ---- TVT2 crux: per-tier volume conservation + dual-axis peaks monotone ----
    t2 = {"beats": {}, "bad_volume": [], "fail_x_mono": [], "fail_y_mono": [], "fail_base": []}
    for tb in twist_beats:
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_pairs(ch)
                if not interior:
                    continue
                if any(abs(_local_det(scx, scy, shx, shy) - 1.0) > TOL_DET
                       for (shx, shy, scx, scy) in interior):
                    t2["bad_volume"].append("{}__{}::{}".format(tb, t, bn))
        xpk = [_peak_x(anims["{}__{}".format(tb, t)]) for t in TIERS]
        ypk = [_peak_y(anims["{}__{}".format(tb, t)]) for t in TIERS]
        bx, by = _peak_x(base[tb]), _peak_y(base[tb])
        t2["beats"][tb] = {"shearX_peaks": [round(v, 3) for v in xpk],
                           "shearY_peaks": [round(v, 3) for v in ypk],
                           "base_x": round(bx, 3), "base_y": round(by, 3),
                           "x_mono": _is_strict_inc(xpk), "y_mono": _is_strict_inc(ypk)}
        if not _is_strict_inc(xpk):
            t2["fail_x_mono"].append(tb)
        if not _is_strict_inc(ypk):
            t2["fail_y_mono"].append(tb)
        if abs(xpk[0] - bx) > 1e-4 or abs(ypk[0] - by) > 1e-4:
            t2["fail_base"].append(tb)
    t2_pass = (bool(t2["beats"]) and not any(t2[k] for k in
               ["bad_volume", "fail_x_mono", "fail_y_mono", "fail_base"]))
    R["TVT2_crux_volume_peaks_monotone"] = {**t2, "pass": t2_pass}

    # ---- TVT3 dual-axis counter-phase damped signature + φ preserved per tier ----
    t3 = {"beats": {}, "bad_endpoints": [], "few_sign_changes": [], "not_damped": [],
          "not_counterphase": [], "phi_off": []}
    for tb in twist_beats:
        phi_by_tier = {}
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                for axis, vals in (("x", _shear_x(ch)), ("y", _shear_y(ch))):
                    if not vals:
                        continue
                    key = "{}__{}::{}::{}".format(tb, t, bn, axis)
                    if not (abs(vals[0]) < 1e-6 and abs(vals[-1]) < 1e-6):
                        t3["bad_endpoints"].append(key)
                    if _sign_changes_zero(vals) < 3:
                        t3["few_sign_changes"].append(key)
                    if not _extrema_mags_decreasing(vals):
                        t3["not_damped"].append(key)
                interior = _interior_shear(ch)
                if interior and _has_shear_y(ch):
                    cp_ok, _, _ = _tw3_eval(interior)
                    if not cp_ok:
                        t3["not_counterphase"].append("{}__{}::{}".format(tb, t, bn))
            xpk, ypk = _peak_x(an), _peak_y(an)
            phi = ypk / xpk if xpk else 0.0
            phi_by_tier[t] = round(phi, 5)
            if abs(phi - TWIST_PHI) > PHI_TOL:
                t3["phi_off"].append("{}__{}".format(tb, t))
        t3["beats"][tb] = {"phi_by_tier": phi_by_tier}
    t3_pass = not any(t3[k] for k in ["bad_endpoints", "few_sign_changes", "not_damped",
                                      "not_counterphase", "phi_off"]) and bool(t3["beats"])
    R["TVT3_dual_axis_phi_preserved"] = {**t3, "pass": t3_pass}

    # ---- TVT4 identity interface per tier ----
    t4 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for tb in twist_beats:
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                t4["bad_interface"].append("{}__{}".format(tb, t))
            for bn, ch in an.get("bones", {}).items():
                xy = _shear_xy(ch)
                if xy and (abs(xy[0][0]) > 1e-6 or abs(xy[0][1]) > 1e-6
                           or abs(xy[-1][0]) > 1e-6 or abs(xy[-1][1]) > 1e-6):
                    t4["shear_endpoints_nonzero"].append("{}__{}::{}".format(tb, t, bn))
                sc = _scale_frames(ch)
                if sc and (abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6
                           or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6):
                    t4["scale_endpoints_nonident"].append("{}__{}::{}".format(tb, t, bn))
    R["TVT4_identity_interface"] = {**t4, "pass": (not t4["bad_interface"]
                                                   and not t4["shear_endpoints_nonzero"]
                                                   and not t4["scale_endpoints_nonident"])}

    # ---- TVT5 crux neg-control: per-axis amplify breaks volume conservation + unit ----
    t5 = {"per_axis_max_det_err": {}, "twistvol_max_det_err": {}, "per_axis_broke": [],
          "twistvol_kept": []}
    gL = gains["Legend"]
    for tb in twist_beats:
        for bn, ch in base[tb].get("bones", {}).items():
            if not (_shear_xy(ch) and _scale_frames(ch)):
                continue
            naive = TV.amplify_bone_tl(ch, gL, twist_vol=False)   # 逐軸線性補償 → 應破守恆
            good = TV.amplify_bone_tl(ch, gL, twist_vol=True)     # 從放大後 shear 重算 → 應守恆
            n_err = max((abs(_local_det(scx, scy, shx, shy) - 1.0)
                         for (shx, shy, scx, scy) in _interior_pairs(naive)), default=0.0)
            g_err = max((abs(_local_det(scx, scy, shx, shy) - 1.0)
                         for (shx, shy, scx, scy) in _interior_pairs(good)), default=0.0)
            key = "{}::{}".format(tb, bn)
            t5["per_axis_max_det_err"][key] = round(n_err, 5)
            t5["twistvol_max_det_err"][key] = round(g_err, 6)
            if n_err > MIN_SHRINK:
                t5["per_axis_broke"].append(key)
            if g_err <= TOL_DET:
                t5["twistvol_kept"].append(key)
    n_dual = len(t5["per_axis_max_det_err"])
    # 單元:_twist_vol_scale(0,0)==1(介面);shear≠0 → s>1 且 s²·cos(dφ)≡1
    u_id = TV._twist_vol_scale(0.0, 0.0) == 1.0
    su = TV._twist_vol_scale(20.0, -14.0)   # 峰扭角差 34°
    u_gt = su > 1.0
    u_vol = abs(su * su * math.cos(math.radians(20.0 - (-14.0))) - 1.0) <= 1e-4
    t5["unit"] = {"identity_ok": u_id, "s_gt1": u_gt, "s": round(su, 4), "vol_ok": u_vol}
    t5_pass = (n_dual >= 1 and len(t5["per_axis_broke"]) == n_dual
               and len(t5["twistvol_kept"]) == n_dual and u_id and u_gt and u_vol)
    R["TVT5_crux_per_axis_breaks_volume"] = {**t5, "n_dual_bones": n_dual, "pass": t5_pass}

    # ---- TVT6 isolation / additive / triple-orthogonality / end-to-end ----
    t6 = {}
    # (a) 平增益守衛:全 1.0 → 峰不遞增 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat, twist_volume=True)
    any_mono_flat, flat_base_diff = False, []
    for tb in twist_beats:
        xpk = [_peak_x(flat_anims["{}__{}".format(tb, t)]) for t in TIERS]
        ypk = [_peak_y(flat_anims["{}__{}".format(tb, t)]) for t in TIERS]
        if _is_strict_inc(xpk) or _is_strict_inc(ypk):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(tb, t)], sort_keys=True) != \
               json.dumps(base[tb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(tb, t))
    t6["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) 等向隔離:twist tier 變體 scale 皆等向;非 twist 主秀 tier 變體(shear-only)不冒出 scale 通道
    tw_iso = all(abs(sx - sy) <= 1e-6
                 for tb in twist_beats for t in TIERS
                 for ch in anims["{}__{}".format(tb, t)].get("bones", {}).values()
                 for (sx, sy) in _scale_frames(ch))
    leak = []
    for nm, an in anims.items():
        if "__" not in nm:
            continue
        bn0 = nm.split("__")[0]
        if G.beat_category(bn0) == "twist":
            continue
        base_has = any(_scale_frames(ch) for ch in base.get(bn0, {}).get("bones", {}).values())
        var_has = any(_scale_frames(ch) for ch in an.get("bones", {}).values())
        if var_has and not base_has:
            leak.append(nm)
    t6["b_isotropic_isolated"] = {"twist_scale_uniform": tw_iso, "leaked": leak,
                                  "pass": tw_iso and not leak}
    # (c) 加性:移除 twist 的 storyboard → 其餘 beat(含 wobble tier 變體)逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "twist"]}
    anims_no = G.build_animations(skel, sb_no, tier_gains=gains, twist_volume=True)
    regressed = [nm for nm, an in anims_no.items()
                 if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True)]
    t6["c_additive"] = {"regressed": regressed,
                        "removed": [b["beat"] for b in sb["beats"]
                                    if G.beat_category(b["beat"]) == "twist"],
                        "pass": not regressed}
    # (d) 三效正交:tier_gains × tier_twist_cycles × twist_volume 併用 → 段數遞增 且每檔位守恆
    ttc = TV.twist_cycles_for(GENRE)
    tri = G.build_animations(skel, sb, tier_gains=gains, tier_twist_cycles=ttc, twist_volume=True)
    seg_by_beat, bad_vol_tri = {}, []
    for tb in twist_beats:
        segs = []
        for t in TIERS:
            an = tri["{}__{}".format(tb, t)]
            nseg = 0
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_pairs(ch)
                nseg = max(nseg, len(interior))
                if any(abs(_local_det(scx, scy, shx, shy) - 1.0) > TOL_DET
                       for (shx, shy, scx, scy) in interior):
                    bad_vol_tri.append("{}__{}::{}".format(tb, t, bn))
            segs.append(nseg)
        seg_by_beat[tb] = segs
    seg_ok = all(_is_strict_inc(s) for s in seg_by_beat.values())
    t6["d_triple_orthogonal"] = {"segments_by_beat": seg_by_beat, "seg_monotone": seg_ok,
                                 "bad_volume": bad_vol_tri, "pass": seg_ok and not bad_vol_tri}
    # (e) 端到端:build_spine --tier-variants --twist-volume --shear-pivot,tier 變體 pivot 不動
    import build_spine
    out = "/tmp/twist_vol_tier_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, tier_variants=True,
                             twist_volume=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {}); centers = summ.get("pivot_centers", {})
    e = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0, "n_with_scale": 0}
    variant_names = [nm for nm in sp_skel["animations"]
                     if "__" in nm and G.beat_category(nm.split("__")[0]) == "twist"]
    for vk in variant_names:
        an = sp_skel["animations"][vk]
        for bn, ch in an.get("bones", {}).items():
            if bn not in joints or bn not in centers:
                continue
            tr = ch.get("translate")
            if not tr:
                continue
            O = np.array(centers[bn], float); P = np.array(joints[bn], float); ellP = P - O
            e["n_joint_bones"] += 1
            if ch.get("scale"):
                e["n_with_scale"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 200 for i in range(201)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"variant": vk, "bone": bn, "fixed": round(fix, 4), "negctrl": round(neg, 2),
                   "has_scale": bool(ch.get("scale"))}
            e["checked"].append(rec)
            if not (fix < TOL_FIX):
                e["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                e["fail_negctrl"].append(rec)
    e_pass = (e["n_joint_bones"] >= 1 and e["n_with_scale"] >= 1
              and not e["fail_fixed"] and not e["fail_negctrl"])
    t6["e_end2end_pivot_fixed"] = {**e, "pass": e_pass}
    R["TVT6_isolation_additive_orthogonal_e2e"] = {**t6, "pass": all(v["pass"] for v in t6.values())}

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
        for k in ["TVT1_present_backward_compat", "TVT2_crux_volume_peaks_monotone",
                  "TVT3_dual_axis_phi_preserved", "TVT4_identity_interface",
                  "TVT5_crux_per_axis_breaks_volume", "TVT6_isolation_additive_orthogonal_e2e"]:
            print("{:38s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("TVT2 shearX/shearY peaks per tier {}:".format(TIERS))
        for tb, d in R["TVT2_crux_volume_peaks_monotone"]["beats"].items():
            print("  {:8s} X {} Y {} (base X {} Y {})".format(
                tb, d["shearX_peaks"], d["shearY_peaks"], d["base_x"], d["base_y"]))
        print("TVT3 φ per tier:", {tb: d["phi_by_tier"] for tb, d in R["TVT3_dual_axis_phi_preserved"]["beats"].items()})
        print("TVT5 crux per-axis vs twist_vol max|det-1|:")
        for key in R["TVT5_crux_per_axis_breaks_volume"]["per_axis_max_det_err"]:
            print("  {:14s} per-axis {}  twist_vol {}".format(
                key, R["TVT5_crux_per_axis_breaks_volume"]["per_axis_max_det_err"][key],
                R["TVT5_crux_per_axis_breaks_volume"]["twistvol_max_det_err"][key]))
        print("TVT6 (d) segments per tier:", R["TVT6_isolation_additive_orthogonal_e2e"]["d_triple_orthogonal"]["segments_by_beat"])
        print("TVT6 (e) end-to-end pivot-fixed (fixed/negctrl px):")
        for rec in R["TVT6_isolation_additive_orthogonal_e2e"]["e_end2end_pivot_fixed"]["checked"]:
            print("  {:18s} {:8s} fixed {:.4f}  negctrl {:.2f}  scale={}".format(
                rec["variant"], rec["bone"], rec["fixed"], rec["negctrl"], rec["has_scale"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
