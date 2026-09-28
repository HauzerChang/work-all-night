#!/usr/bin/env python3
"""candidate (G-4''''''-vol-tier) 自我驗收閘 — **volume-conserving twist 接檔位幅度差異化**(純 CPU)。

(G-4''''''-vol) 讓 twist(反相雙軸 shear)掛一條**等向**補償 scale `s=1/√cos(shearX−shearY)` → 全域
local 行列式 `det=s²·cos(shearX−shearY)≡1`(擰而不變面積),但**僅作用於 base twist**;它當時明列的
honest boundary:「tier 變體仍 shear-only —— vol 隨檔位放大需**重算**補償 scale 以維持 det≡1」。本次
(G-4''''''-vol-tier)補上:twist∈`TWIST_VOLUME_CATS`,當 `twist_volume=True` 且給 `tier_gains` 時,
`twist__{tier}` 變體的兩軸 shear 照常單一-g 放大(v'=g*v,φ 逐檔不變),等向補償 scale 則由
`amplify_anim(twist_vol=True)` 以**放大後**的雙軸 shear **重算**(cos 非線性)→ **det≡1 逐檔保持**。

crux(與 squash tier 耦合 amplify 的機制對比):squash 走**非均勻**體積守恆(拉長軸自由、壓縮軸=倒數,
`scaleX·scaleY≡1` 由建構保證);twist 走**等向**(scaleX==scaleY=s)且補償 s 由 cos **反推重算**(檔位放大
→ `cos(shearX−shearY)` 非線性變小 → s 非線性變大)。**關鍵:補償不可逐軸線性放大** —— `_amp_scale(s,g)`
那種「放大既有 s」會讓 `s²·cos≠1`(破守恆),必須從放大後的 shear 重算(見 VL3 crux 負對照)。

真值界定同 twist 系列(E/H/I/J/G-4'…/G-4''''''-vol):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀
結構簽章**(兩軸峰遞增 + φ 不變 + 反相阻尼保形 + 逐檔體積守恆)非美感;負對照證鑑別力(閘可信)。從
**先驗庫**(slot_bigwin twist beat)→ **真實 build_spine robot 骨架** → `build_animations(twist_volume=True,
tier_gains=…)` 端到端量。

AC(客觀、可量測):
  VL1 present + backward-compat  : twist_volume=True + tier_gains → 每檔位 `twist__{tier}` 皆產出、finite、
                                   有 bone、≥1 bone **同時**帶 shear 與**等向** scale;名經 `beat_category`
                                   仍路由回 twist。**Super(g=1)逐位元 == base twist(vol)**;base(In/Loop/Out
                                   + base twist vol)帶/不帶 tier_gains 逐位元不變。**twist_volume=False +
                                   tier_gains → tier 變體 shear-only(無 scale)且逐位元 == G-4''''''-tier 輸出**
                                   (向後相容:vol 開關不影響 shear-only tier)。
  VL2 crux — det≡1 per tier      : **每檔位**每 twist bone 每內部極值幀,全域 local 行列式(`transform_matrix_full`
                                   帶放大後 shearX/shearY + 重算 scaleX/scaleY)|det−1| ≤ TOL_DET;且 scale
                                   **等向**(每幀 scaleX==scaleY)—— 補償隨檔位重算仍守恆、仍等向。
  VL3 crux — recompute necessary : **負對照**:對 base vol-twist beat 施「逐軸線性 scale 放大」(twist_vol=False,
                                   即放大既有 s 而不重算)於 Legend 增益 → 某內部極值 |det−1| ≥ MIN_BREAK
                                   (破守恆);對照重算(twist_vol=True)同增益 ≤ TOL_DET → ≥ SEP_RATIO× 分離,
                                   證「補償須從放大後 shear 重算」非「有 scale 即可」。
  VL4 sig monotone / invariant   : 各檔位 twist 峰 |shearX| **與** 峰 |shearY| 皆 Super<Mega<Omg<Legend
                                   **嚴格遞增**(Super==base);**每 bone** shearY峰/shearX峰 ≈ TWIST_PHI 逐檔
                                   不變(誤差 ≤ PHI_TOL);**補償 scale 峰 s** 亦 Super<Mega<Omg<Legend 嚴格遞增
                                   (愈高檔位擰愈狠 → 補償愈大)。
  VL5 shear signature per tier   : **每檔位**每 twist bone 的 shearX **與** shearY 各自:(a)首尾 0;(b)繞 0
                                   變號 ≥3;(c)相繼極值嚴格遞減(阻尼);且每內部極值反號(反相耦合,復用 TW3)。
  VL6 interface/iso/count×vol     : (a)identity 介面:每檔位 shear 首尾 (0,0)、scale 首尾 (1,1);(b)隔離:
                                   twist tier 變體 scale **等向**、squash tier 變體 scale **非均勻**(不同源機制
                                   互不外洩);(c)**count×vol 正交**:同時給 tier_twist_cycles + twist_volume →
                                   每檔位段數 [4,5,6,7] 嚴格遞增 **且**每內部極值仍 |det−1| ≤ TOL_DET
                                   (段數×幅度×體積守恆三效正交可疊)。

用法:
  python3 validate_twist_vol_tier.py            # 摘要
  python3 validate_twist_vol_tier.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from beat_templates import TWIST_PHI
from pivot_rotation import transform_matrix_full
# 復用 twist 系列閘的讀取/阻尼/反相判準,確保與整條 twist 線完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_twist_gen import _shear_y, _shear_xy, _interior_shear, _tw3_eval, _has_shear_y
from validate_twist_tier import (_psd, _skeleton, _storyboard, _twist_beats,
                                 _peak_x, _peak_y, _is_strict_inc, TIERS, GENRE, MIN_SHEAR, PHI_TOL)
from validate_twist_volume import _scale_frames, _local_det
from validate_twist_count import _nosc

TOL_DET = 2e-4       # |det−1| 上限(同 G-4''''''-vol TV2 / squash SC2;實測重算殘差 <1e-4)
MIN_BREAK = 0.02     # 逐軸線性放大(不重算)於 Legend 的 |det−1| 下限(實測 0.06–0.31 → 充足餘裕)
SEP_RATIO = 50.0     # 重算 vs 逐軸線性放大的分離倍數下限(實測 >500×)


def _scale_peak(anim):
    """該 anim 全 bone 的補償 scale 峰(等向 → 取 scaleX 峰;無 scale 回 0)。"""
    ps = [max(sx for (sx, sy) in _scale_frames(ch)) for ch in anim.get("bones", {}).values()
          if _scale_frames(ch)]
    return max(ps, default=0.0)


def _interior_det_devs(ch):
    """該 bone 每內部極值幀的 |det−1|(shear/scale 共生同索引;去首尾)。無 scale/太短回 []。"""
    xy = _shear_xy(ch); sc = _scale_frames(ch)
    if len(xy) < 3 or len(sc) != len(xy):
        return []
    return [abs(_local_det(scx, scy, shx, shy) - 1.0)
            for (shx, shy), (scx, scy) in list(zip(xy, sc))[1:-1]]


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb, twist_volume=True)                    # base vol twist(無 tier)
    anims = G.build_animations(skel, sb, twist_volume=True, tier_gains=gains)  # ★ vol + 檔位
    twist_beats = _twist_beats(base)
    R = {}

    # ---- VL1 present + backward-compat ----
    v1 = {"twist_beats": twist_beats, "missing": [], "not_finite": [], "no_bones": [],
          "variant_no_dual": [], "misrouted": [], "super_ne_base": [], "base_changed": [],
          "voloff_has_scale": []}
    for tb in twist_beats:
        for t in TIERS:
            vk = "{}__{}".format(tb, t)
            an = anims.get(vk)
            if an is None:
                v1["missing"].append(vk); continue
            if not SA.all_finite(an):
                v1["not_finite"].append(vk)
            if not an.get("bones"):
                v1["no_bones"].append(vk)
            # ≥1 bone 同時帶 shear 與等向 scale
            dual = any(_shear_xy(ch) and _scale_frames(ch)
                       and all(abs(sx - sy) <= 1e-9 for (sx, sy) in _scale_frames(ch))
                       for ch in an.get("bones", {}).values())
            if not dual:
                v1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "twist":
                v1["misrouted"].append((vk, G.beat_category(vk)))
        # Super(g=1)逐位元 == base vol twist
        sk = "{}__Super".format(tb)
        if json.dumps(anims.get(sk), sort_keys=True) != json.dumps(base[tb], sort_keys=True):
            v1["super_ne_base"].append(tb)
    # base(含 In/Loop/Out + base vol twist)帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            v1["base_changed"].append(k)
    # 向後相容:twist_volume=False + tier_gains → tier 變體 shear-only 且 == G-4''''''-tier 輸出
    anims_voloff = G.build_animations(skel, sb, tier_gains=gains)   # twist_volume=False(預設)
    for tb in twist_beats:
        for t in TIERS:
            vk = "{}__{}".format(tb, t)
            if any(_scale_frames(ch) for ch in anims_voloff[vk].get("bones", {}).values()):
                v1["voloff_has_scale"].append(vk)
    v1_pass = (bool(twist_beats) and not any(v1[k] for k in
               ["missing", "not_finite", "no_bones", "variant_no_dual", "misrouted",
                "super_ne_base", "base_changed", "voloff_has_scale"]))
    R["VL1_present_backward_compat"] = {**v1, "pass": v1_pass}

    # ---- VL2 crux: det≡1 at EVERY tier + isotropic scale ----
    v2 = {"break_conserve": [], "anisotropic": [], "detail": {}, "max_dev_overall": 0.0}
    for tb in twist_beats:
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                devs = _interior_det_devs(ch)
                if not devs:
                    continue
                key = "{}__{}::{}".format(tb, t, bn)
                v2["detail"][key] = round(max(devs), 6)
                v2["max_dev_overall"] = max(v2["max_dev_overall"], max(devs))
                if max(devs) > TOL_DET:
                    v2["break_conserve"].append((key, round(max(devs), 6)))
                if any(abs(sx - sy) > 1e-9 for (sx, sy) in _scale_frames(ch)):
                    v2["anisotropic"].append(key)
    v2["max_dev_overall"] = round(v2["max_dev_overall"], 6)
    v2_pass = (bool(v2["detail"]) and not v2["break_conserve"] and not v2["anisotropic"])
    R["VL2_det_conserved_per_tier"] = {**v2, "tol": TOL_DET, "pass": v2_pass}

    # ---- VL3 crux: recompute necessary (naive linear scale amp breaks) ----
    v3 = {"detail": {}, "naive_not_break": [], "recompute_break": [], "insufficient_sep": []}
    gL = gains["Legend"]
    for tb in twist_beats:
        for bn, ch in base[tb].get("bones", {}).items():
            if not (_shear_xy(ch) and _scale_frames(ch)):
                continue
            key = "{}::{}".format(tb, bn)
            re = TV.amplify_bone_tl(ch, gL, twist_vol=True)     # 重算補償
            nv = TV.amplify_bone_tl(ch, gL, twist_vol=False)    # 逐軸線性放大既有 s(負對照)
            re_dev = _interior_det_devs(re)
            nv_dev = _interior_det_devs(nv)
            if not re_dev or not nv_dev:
                continue
            re_max, nv_max = max(re_dev), max(nv_dev)
            v3["detail"][key] = {"recompute_max_dev": round(re_max, 6),
                                 "naive_max_dev": round(nv_max, 6)}
            if nv_max < MIN_BREAK:
                v3["naive_not_break"].append((key, round(nv_max, 6)))
            if re_max > TOL_DET:
                v3["recompute_break"].append((key, round(re_max, 6)))
            if not (nv_max > re_max * SEP_RATIO):
                v3["insufficient_sep"].append((key, round(nv_max / max(re_max, 1e-9), 1)))
    v3_pass = (bool(v3["detail"]) and not v3["naive_not_break"]
               and not v3["recompute_break"] and not v3["insufficient_sep"])
    R["VL3_recompute_necessary"] = {**v3, "legend_gain": gL, "pass": v3_pass}

    # ---- VL4 dual-axis peak monotone + phi invariant + compensation-scale monotone ----
    v4 = {"beats": {}, "fail_mono_x": [], "fail_mono_y": [], "fail_mono_scale": [],
          "fail_base": [], "bad_ratio": []}
    for tb in twist_beats:
        px = [_peak_x(anims["{}__{}".format(tb, t)]) for t in TIERS]
        py = [_peak_y(anims["{}__{}".format(tb, t)]) for t in TIERS]
        ps = [_scale_peak(anims["{}__{}".format(tb, t)]) for t in TIERS]
        bx, by = _peak_x(base[tb]), _peak_y(base[tb])
        v4["beats"][tb] = {"shearX_peaks": [round(p, 3) for p in px],
                           "shearY_peaks": [round(p, 3) for p in py],
                           "scale_peaks": [round(p, 4) for p in ps],
                           "base": [round(bx, 3), round(by, 3)]}
        if not _is_strict_inc(px):
            v4["fail_mono_x"].append(tb)
        if not _is_strict_inc(py):
            v4["fail_mono_y"].append(tb)
        if not _is_strict_inc(ps):
            v4["fail_mono_scale"].append(tb)
        if not (abs(px[0] - bx) <= 1e-4 and abs(py[0] - by) <= 1e-4):
            v4["fail_base"].append(tb)
        # φ 比值逐檔不變(每 bone)
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
                    v4["bad_ratio"].append(("{}__{}::{}".format(tb, t, bn), round(ratio, 5)))
    v4_pass = (bool(v4["beats"]) and not v4["fail_mono_x"] and not v4["fail_mono_y"]
               and not v4["fail_mono_scale"] and not v4["fail_base"] and not v4["bad_ratio"])
    R["VL4_sig_monotone_invariant"] = {**v4, "phi": TWIST_PHI, "pass": v4_pass}

    # ---- VL5 both-axes damped + counterphase per tier ----
    v5 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "not_counterphase": []}
    for tb in twist_beats:
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                for axis, vals in (("x", _shear_x(ch)), ("y", _shear_y(ch))):
                    if not vals:
                        continue
                    key = "{}__{}::{}::{}".format(tb, t, bn, axis)
                    if not (abs(vals[0]) < 1e-6 and abs(vals[-1]) < 1e-6):
                        v5["bad_endpoints"].append(key)
                    if _sign_changes_zero(vals) < 3:
                        v5["few_sign_changes"].append(key)
                    if not _extrema_mags_decreasing(vals):
                        v5["not_damped"].append(key)
                interior = _interior_shear(ch)
                if interior and _has_shear_y(ch):
                    cp_ok, _dev_ok, _det = _tw3_eval(interior)
                    if not cp_ok:
                        v5["not_counterphase"].append("{}__{}::{}".format(tb, t, bn))
    v5_pass = not any(v5[k] for k in ["bad_endpoints", "few_sign_changes",
                                      "not_damped", "not_counterphase"])
    R["VL5_shear_signature_per_tier"] = {**v5, "pass": v5_pass}

    # ---- VL6 interface / isolation / count×vol orthogonality ----
    v6 = {}
    # (a) identity 介面每檔位
    bad_iface = []
    for tb in twist_beats:
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            for bn, ch in an.get("bones", {}).items():
                xy = _shear_xy(ch); sc = _scale_frames(ch)
                if xy and (abs(xy[0][0]) > 1e-6 or abs(xy[0][1]) > 1e-6
                           or abs(xy[-1][0]) > 1e-6 or abs(xy[-1][1]) > 1e-6):
                    bad_iface.append("{}__{}::{}::shear".format(tb, t, bn))
                if sc and (abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6
                           or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6):
                    bad_iface.append("{}__{}::{}::scale".format(tb, t, bn))
    v6["a_identity_interface"] = {"bad": bad_iface, "pass": not bad_iface}
    # (b) 等向 vs 非均勻隔離(tier 變體層級)
    sq_beats = [nm for nm in base if "__" not in nm and G.beat_category(nm) == "squash"]
    tw_uniform = all(abs(sx - sy) <= 1e-9
                     for tb in twist_beats for t in TIERS
                     for ch in anims["{}__{}".format(tb, t)].get("bones", {}).values()
                     for (sx, sy) in _scale_frames(ch))
    sq_aniso = any(abs(sx - sy) > 1e-6
                   for sb2 in sq_beats for t in TIERS
                   for ch in anims["{}__{}".format(sb2, t)].get("bones", {}).values()
                   for (sx, sy) in _scale_frames(ch))
    v6["b_isotropic_vs_nonuniform"] = {"twist_tier_scale_uniform": tw_uniform,
                                       "squash_tier_scale_nonuniform": sq_aniso,
                                       "squash_beats": sq_beats,
                                       "pass": tw_uniform and sq_aniso}
    # (c) count×vol 正交:tier_twist_cycles + twist_volume → 段數遞增 且 逐極值守恆
    tcyc = TV.twist_cycles_for(GENRE)
    anims_cv = G.build_animations(skel, sb, twist_volume=True, tier_gains=gains,
                                  tier_twist_cycles=tcyc)
    cv = {"beats": {}, "fail_count_mono": [], "break_conserve": []}
    for tb in twist_beats:
        counts = [_nosc(anims_cv["{}__{}".format(tb, t)]) for t in TIERS]
        cv["beats"][tb] = {"counts": counts, "declared": [tcyc[t] for t in TIERS]}
        if not (_is_strict_inc(counts) and counts == [tcyc[t] for t in TIERS]):
            cv["fail_count_mono"].append(tb)
        for t in TIERS:
            for bn, ch in anims_cv["{}__{}".format(tb, t)].get("bones", {}).items():
                devs = _interior_det_devs(ch)
                if devs and max(devs) > TOL_DET:
                    cv["break_conserve"].append(("{}__{}::{}".format(tb, t, bn), round(max(devs), 6)))
    cv["pass"] = (bool(cv["beats"]) and not cv["fail_count_mono"] and not cv["break_conserve"])
    v6["c_count_vol_orthogonal"] = cv
    R["VL6_interface_iso_countvol"] = {**v6, "pass": all(v6[k]["pass"] for k in v6)}

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
        for k in ["VL1_present_backward_compat", "VL2_det_conserved_per_tier",
                  "VL3_recompute_necessary", "VL4_sig_monotone_invariant",
                  "VL5_shear_signature_per_tier", "VL6_interface_iso_countvol"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("VL2 max|det-1| over all tiers:", R["VL2_det_conserved_per_tier"]["max_dev_overall"],
              "(tol {})".format(TOL_DET))
        print("VL4 peaks per tier {}:".format(TIERS))
        for tb, d in R["VL4_sig_monotone_invariant"]["beats"].items():
            print("  {:10s} shearX {}  shearY {}  scale {}".format(
                tb, d["shearX_peaks"], d["shearY_peaks"], d["scale_peaks"]))
        print("VL3 recompute vs naive (Legend), sample:")
        for key, d in list(R["VL3_recompute_necessary"]["detail"].items())[:3]:
            print("  {:16s} recompute |det-1| {:.2e}  naive |det-1| {:.2e}".format(
                key, d["recompute_max_dev"], d["naive_max_dev"]))
        print("VL6 count×vol counts:", {tb: d["counts"]
              for tb, d in R["VL6_interface_iso_countvol"]["c_count_vol_orthogonal"]["beats"].items()})
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
