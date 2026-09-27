#!/usr/bin/env python3
"""candidate G-4''''''-vol-tier 自我驗收閘 — **volume-conserving twist 接檔位差異化**(純 CPU)。

(G-4''''''-vol)讓 base twist 掛**等向**體積守恆補償 scale `s=1/√cos(shearX−shearY)` → 全域 local
`det≡1`(擰而不變面積)。但其 honest boundary(自列):vol **僅作用 base twist**;tier 變體仍 shear-only ——
「vol 隨檔位放大需**重算**補償 scale 以維持 det≡1,比照 squash 耦合 amplify」。本 chunk 補上這條:與 tier_gains
併用時,twist 檔位變體的補償 scale 依**放大後 shear** 於同 τ **重算**(`amplify_bone_tl(..., twist_vol=True)`)。

**crux(為何不能沿用逐軸 _amp_scale)**:補償 s 是 shear 的**函式**(跨通道)。tier 放大令 shear ×g →
`cos(shearX'−shearY')=cos(g·(shearX−shearY))` **非線性改變**;若對 base 的 s 施逐軸 `_amp_scale`(1+g(s−1))
只是線性拉長一個「為 base shear 算的」補償 → 與新 shear 不匹配,det 破守恆(實測 Legend |det−1| 0.31)。必須用
放大後 shear **重算** s'=1/√cos(g·(shearX−shearY))。**與 squash 耦合 amplify 的差異**:squash 由 scale 自身
另一軸反推(scaleX·scaleY≡1,**非均勻**);twist 由同幀 shear 重算(**等向** scaleX==scaleY)—— 不同源。

真值界定同 twist 系列(E/H/I/J/G-4'/…/G-4''''''-vol):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構
簽章**(四效正交:段數×幅度×守恆×φ)非美感;負對照證鑑別力。從**先驗庫** → **真實 build_spine robot 骨架**
→ `build_animations(tier_gains=…, twist_volume=True)` 端到端量。

AC(客觀、可量測):
  VL1 present + backward-compat   : base twist(vol)帶雙軸 shear + 等向 scale;每檔位 `twist__{tier}` 皆產出、
                                   finite、有 bone、≥1 bone **同時**帶 shear+scale、scale 等向、名經
                                   `beat_category` 仍路由回 twist;**base(In/Loop/Out + base twist vol)帶/不帶
                                   tier_gains 逐位元不變**、**Super(g=1)== base twist(vol)逐位元**。
  VL2 crux — 逐檔守恆 + s 遞增 + 負對照: 每檔位每 twist bone 每內部極值幀 |det−1| ≤ TOL_DET(全域 local
                                   `transform_matrix_full` 帶 shearX/shearY/scaleX/scaleY);且補償 s 峰隨檔位
                                   Super<Mega<Omg<Legend **嚴格遞增**(證 scale 真被**重算**非凍結);**負對照**
                                   = 逐軸 `_amp_scale`(twist_vol=False,對 base vol scale 線性拉長)→ 高檔位
                                   |det−1| ≥ MIN_BREAK(破守恆)→ 證閘測「真重算守恆」非「有 scale 即可」。
  VL3 crux — 等向保形 + squash 隔離  : 每檔位每 scale 幀 scaleX==scaleY(補償等向,各向異性全由 shear);squash
                                   檔位變體 scale **非均勻**(scaleX≠scaleY)→ 兩種體積守恆機制不同源、互不外洩。
  VL4 雙軸峰遞增 + φ 逐檔不變       : 各檔位峰 |shearX| 與峰 |shearY| 皆 Super<Mega<Omg<Legend 嚴格遞增且
                                   Super==base;每 twist bone 每檔位 shearY峰/shearX峰 ≈ TWIST_PHI(vol scale
                                   不擾動 shear 簽章 → φ 保形,復用 TT2/TT3 判準)。
  VL5 每檔位介面 + 雙軸阻尼/反相簽章 : 每檔位 shear 首尾 (0,0)、scale 首尾 (1,1);兩軸各自(繞 0 變號≥3 +
                                   相繼極值遞減)+ 每內部極值反相(shearX·shearY<0)(復用 TV3/TT4/TT5 判準)。
  VL6 端到端三通道逐檔 pivot 不動   : `build_spine --twist-volume --tier-variants --shear-pivot`(真實 robot)產
                                   `twist__{tier}` 帶 shear+scale+rotate 補償;凡有關節 pivot 的 bone,pivot 殘差
                                   < TOL_FIX,內建負對照(繞件中心)大位移;且 ≥1 tier bone 帶 scale 通道(三通道
                                   補償逐檔存活)。注意:體積守恆是**關鍵幀級**性質(VL2 於 gen 極值幀量);
                                   build_spine 的 pivot densify 會把 scale/shear 各自線性重取樣到密網格 →
                                   **關鍵幀之間**線性內插的 s 與 shear 天然不滿足 det≡1(base 亦然),故此不在
                                   密網格上重驗守恆(那是內插性質、非本 feature 的迴歸),只驗 pivot 三通道錨定。

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
from pivot_rotation import transform_matrix_full
# 復用 twist 系列閘(gen/tier/vol)的讀取與阻尼/反相/守恆判準,確保與家族完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_shear_pivot import _world
from validate_twist_gen import (_shear_y, _shear_xy, _interior_shear, _tw3_eval,
                                _has_shear_y, _is_ident, TOL_FIX, MIN_NEG, NEG_RATIO)
from validate_twist_tier import (_psd, _skeleton, _storyboard, _twist_beats, _peak_x, _peak_y,
                                 _is_strict_inc, GENRE, TIERS, MIN_SHEAR, PHI_TOL)
from validate_twist_volume import _scale_frames, _local_det, TOL_DET

MIN_BREAK = 0.02     # 負對照(逐軸 _amp_scale)高檔位 |det−1| 下限(Mega 0.06 / Legend 0.31 → 充足餘裕)


def _interior_scale_shear(ch):
    """回傳去首尾 identity 的 [(shearX, shearY, scaleX, scaleY)](無 scale/shear 或長度不符回 [])。"""
    xy = _shear_xy(ch); sc = _scale_frames(ch)
    if len(xy) < 3 or len(sc) != len(xy):
        return []
    return [(shx, shy, scx, scy) for (shx, shy), (scx, scy) in list(zip(xy, sc))[1:-1]]


def _s_peak(anim):
    """該 anim 全 bone 補償 scale 的峰值 max(scaleX)(等向 → scaleX==scaleY;無 scale 回 0)。"""
    ps = [max(sx for (sx, sy) in _scale_frames(ch)) for ch in anim.get("bones", {}).values()
          if _scale_frames(ch)]
    return max(ps, default=0.0)


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb, twist_volume=True)                     # tiers=None(base 帶 vol)
    anims = G.build_animations(skel, sb, tier_gains=gains, twist_volume=True)   # 帶檔位 + vol
    twist_beats = _twist_beats(base)
    R = {}

    # ---- VL1 present + backward-compat ----
    v1 = {"twist_beats": twist_beats, "base_weak_shear": [], "base_no_scale": [], "missing": [],
          "not_finite": [], "no_bones": [], "variant_no_shear": [], "variant_no_scale": [],
          "anisotropic": [], "misrouted": [], "base_changed": [], "super_ne_base": []}
    for tb in twist_beats:
        if _peak_x(base[tb]) < MIN_SHEAR or _peak_y(base[tb]) < MIN_SHEAR:
            v1["base_weak_shear"].append(tb)
        if not any(_scale_frames(ch) for ch in base[tb].get("bones", {}).values()):
            v1["base_no_scale"].append(tb)
        for t in TIERS:
            vk = "{}__{}".format(tb, t)
            an = anims.get(vk)
            if an is None:
                v1["missing"].append(vk); continue
            if not SA.all_finite(an):
                v1["not_finite"].append(vk)
            if not an.get("bones"):
                v1["no_bones"].append(vk)
            if not any(_shear_xy(ch) for ch in an.get("bones", {}).values()):
                v1["variant_no_shear"].append(vk)
            if not any(_scale_frames(ch) for ch in an.get("bones", {}).values()):
                v1["variant_no_scale"].append(vk)
            for bn, ch in an.get("bones", {}).items():
                if any(abs(sx - sy) > 1e-6 for (sx, sy) in _scale_frames(ch)):
                    v1["anisotropic"].append("{}::{}".format(vk, bn))
            if G.beat_category(vk) != "twist":
                v1["misrouted"].append((vk, G.beat_category(vk)))
        # Super(g=1)逐位元 == base twist(vol)
        if json.dumps(anims.get("{}__Super".format(tb)), sort_keys=True) != json.dumps(base[tb], sort_keys=True):
            v1["super_ne_base"].append(tb)
    # base(含 In/Loop/Out + base twist vol)帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            v1["base_changed"].append(k)
    v1_pass = (bool(twist_beats) and not any(v1[k] for k in
               ["base_weak_shear", "base_no_scale", "missing", "not_finite", "no_bones",
                "variant_no_shear", "variant_no_scale", "anisotropic", "misrouted",
                "base_changed", "super_ne_base"]))
    R["VL1_present_backward_compat"] = {**v1, "pass": v1_pass}

    # ---- VL2 crux: per-tier volume conserved + s_peak monotone + naive-amplify negative control ----
    v2 = {"break_conserve": [], "s_peaks": {}, "fail_s_mono": [], "neg_not_break": [], "detail": {}}
    for tb in twist_beats:
        # 逐檔守恆 + 記錄每檔位補償 s 峰
        s_peaks = []
        for t in TIERS:
            an = anims["{}__{}".format(tb, t)]
            s_peaks.append(_s_peak(an))
            worst = 0.0
            for bn, ch in an.get("bones", {}).items():
                for (shx, shy, scx, scy) in _interior_scale_shear(ch):
                    dv = abs(_local_det(scx, scy, shx, shy) - 1.0)
                    worst = max(worst, dv)
                    if dv > TOL_DET:
                        v2["break_conserve"].append("{}__{}::{}".format(tb, t, bn))
            v2["detail"]["{}__{}".format(tb, t)] = {"max_dev": round(worst, 6)}
        v2["s_peaks"][tb] = [round(s, 4) for s in s_peaks]
        if not _is_strict_inc(s_peaks):
            v2["fail_s_mono"].append(tb)
        # 負對照:逐軸 _amp_scale(twist_vol=False)對 base vol beat → 高檔位破守恆
        for t, g in gains.items():
            if abs(g - 1.0) < 1e-9:
                continue   # Super g=1:重算與逐軸重合(det≡1)→ 不作負對照
            naive = TV.amplify_anim(base[tb], g, coupled=False, twist_vol=False)  # ← 逐軸 _amp_scale(錯)
            nworst = 0.0
            for bn, ch in naive.get("bones", {}).items():
                for (shx, shy, scx, scy) in _interior_scale_shear(ch):
                    nworst = max(nworst, abs(_local_det(scx, scy, shx, shy) - 1.0))
            v2["detail"]["{}__{}_NAIVE".format(tb, t)] = {"max_dev": round(nworst, 6)}
            if t == "Legend" and nworst < MIN_BREAK:
                v2["neg_not_break"].append("{}__{}".format(tb, t))
    v2_pass = (bool(v2["detail"]) and not v2["break_conserve"] and not v2["fail_s_mono"]
               and not v2["neg_not_break"])
    R["VL2_per_tier_conserved"] = {**v2, "pass": v2_pass}

    # ---- VL3 crux: isotropy preserved per tier + squash isolation ----
    v3 = {"tw_anisotropic": [], "squash_variant_beats": [], "squash_not_nonuniform": False}
    for tb in twist_beats:
        for t in TIERS:
            for bn, ch in anims["{}__{}".format(tb, t)].get("bones", {}).items():
                if any(abs(sx - sy) > 1e-6 for (sx, sy) in _scale_frames(ch)):
                    v3["tw_anisotropic"].append("{}__{}::{}".format(tb, t, bn))
    sq_variants = [nm for nm in anims if "__" in nm and G.beat_category(nm.split("__")[0]) == "squash"]
    v3["squash_variant_beats"] = sq_variants
    sq_nonuniform = any(abs(sx - sy) > 1e-6
                        for nm in sq_variants for ch in anims[nm].get("bones", {}).values()
                        for (sx, sy) in _scale_frames(ch))
    v3["squash_not_nonuniform"] = not sq_nonuniform
    v3_pass = (not v3["tw_anisotropic"] and bool(sq_variants) and sq_nonuniform)
    R["VL3_isotropy_squash_isolation"] = {**v3, "pass": v3_pass}

    # ---- VL4 dual-axis peak monotone + phi invariant per tier (vol 不擾動 shear 簽章) ----
    v4 = {"beats": {}, "fail_mono_x": [], "fail_mono_y": [], "fail_base": [], "bad_ratio": []}
    for tb in twist_beats:
        px = [_peak_x(anims["{}__{}".format(tb, t)]) for t in TIERS]
        py = [_peak_y(anims["{}__{}".format(tb, t)]) for t in TIERS]
        bx, by = _peak_x(base[tb]), _peak_y(base[tb])
        v4["beats"][tb] = {"shearX_peaks": [round(p, 3) for p in px],
                           "shearY_peaks": [round(p, 3) for p in py],
                           "base": [round(bx, 3), round(by, 3)]}
        if not _is_strict_inc(px):
            v4["fail_mono_x"].append(tb)
        if not _is_strict_inc(py):
            v4["fail_mono_y"].append(tb)
        if not (abs(px[0] - bx) <= 1e-4 and abs(py[0] - by) <= 1e-4):
            v4["fail_base"].append(tb)
        for t in TIERS:
            for bn, ch in anims["{}__{}".format(tb, t)].get("bones", {}).items():
                sx, sy = _shear_x(ch), _shear_y(ch)
                if not sx or not sy:
                    continue
                pkx = max(abs(v) for v in sx); pky = max(abs(v) for v in sy)
                if pkx <= 1e-9:
                    continue
                if abs(pky / pkx - TWIST_PHI) > PHI_TOL:
                    v4["bad_ratio"].append(("{}__{}::{}".format(tb, t, bn), round(pky / pkx, 5)))
    v4_pass = (bool(v4["beats"]) and not v4["fail_mono_x"] and not v4["fail_mono_y"]
               and not v4["fail_base"] and not v4["bad_ratio"])
    R["VL4_dual_peak_phi"] = {**v4, "phi": TWIST_PHI, "pass": v4_pass}

    # ---- VL5 per-tier identity interface + dual-axis damped/counter-phase signature ----
    v5 = {"shear_endpoints_nonzero": [], "scale_endpoints_nonident": [], "few_sign_changes": [],
          "not_damped": [], "not_counterphase": []}
    for tb in twist_beats:
        for t in TIERS:
            for bn, ch in anims["{}__{}".format(tb, t)].get("bones", {}).items():
                xy = _shear_xy(ch)
                if xy and (abs(xy[0][0]) > 1e-6 or abs(xy[0][1]) > 1e-6
                           or abs(xy[-1][0]) > 1e-6 or abs(xy[-1][1]) > 1e-6):
                    v5["shear_endpoints_nonzero"].append("{}__{}::{}".format(tb, t, bn))
                sc = _scale_frames(ch)
                if sc and (abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6
                           or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6):
                    v5["scale_endpoints_nonident"].append("{}__{}::{}".format(tb, t, bn))
                for axis, vals in (("x", _shear_x(ch)), ("y", _shear_y(ch))):
                    if not vals:
                        continue
                    key = "{}__{}::{}::{}".format(tb, t, bn, axis)
                    if _sign_changes_zero(vals) < 3:
                        v5["few_sign_changes"].append(key)
                    if not _extrema_mags_decreasing(vals):
                        v5["not_damped"].append(key)
                interior = _interior_shear(ch)
                if interior and _has_shear_y(ch):
                    cp_ok, _dev, _det = _tw3_eval(interior)
                    if not cp_ok:
                        v5["not_counterphase"].append("{}__{}::{}".format(tb, t, bn))
    v5_pass = not any(v5[k] for k in v5)
    R["VL5_interface_signature_per_tier"] = {**v5, "pass": v5_pass}

    # ---- VL6 end-to-end three-channel pivot-fixed per tier (build_spine) ----
    import build_spine
    out = "/tmp/twist_vol_tier_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True,
                             tier_variants=True, twist_volume=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {}); centers = summ.get("pivot_centers", {})
    v6 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0,
          "n_with_scale": 0}
    tier_twist = [nm for nm in sp_skel["animations"]
                  if "__" in nm and G.beat_category(nm.split("__")[0]) == "twist"]
    for tb in tier_twist:
        an = sp_skel["animations"][tb]
        for bn, ch in an.get("bones", {}).items():
            if bn not in joints or bn not in centers:
                continue
            O = np.array(centers[bn], float); P = np.array(joints[bn], float)
            ellP = P - O
            tr = ch.get("translate")
            if not tr:
                continue
            v6["n_joint_bones"] += 1
            has_scale = bool(ch.get("scale"))
            if has_scale:
                v6["n_with_scale"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"bone": bn, "beat": tb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2), "has_scale": has_scale}
            v6["checked"].append(rec)
            if not (fix < TOL_FIX):
                v6["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                v6["fail_negctrl"].append(rec)
    v6_pass = (v6["n_joint_bones"] >= 1 and v6["n_with_scale"] >= 1 and not v6["fail_fixed"]
               and not v6["fail_negctrl"])
    R["VL6_end2end_pivot_conserved"] = {**v6, "pass": v6_pass}

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
        for k in ["VL1_present_backward_compat", "VL2_per_tier_conserved",
                  "VL3_isotropy_squash_isolation", "VL4_dual_peak_phi",
                  "VL5_interface_signature_per_tier", "VL6_end2end_pivot_conserved"]:
            print("{:36s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("VL2 s_peaks per tier {}:".format(TIERS), R["VL2_per_tier_conserved"]["s_peaks"])
        print("VL2 det detail:", json.dumps(R["VL2_per_tier_conserved"]["detail"], ensure_ascii=False))
        print("VL4 peaks per tier:")
        for tb, d in R["VL4_dual_peak_phi"]["beats"].items():
            print("  {:10s} shearX {}  shearY {}  (base {})".format(
                tb, d["shearX_peaks"], d["shearY_peaks"], d["base"]))
        print("VL6 pivot-fixed (fixed/negctrl px):")
        for rec in R["VL6_end2end_pivot_conserved"]["checked"]:
            print("  {:16s} beat {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}  scale={}".format(
                rec["bone"], rec["beat"], rec["arm"], rec["fixed"], rec["negctrl"], rec["has_scale"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
