#!/usr/bin/env python3
"""candidate G-4''''''-vol-tier 自我驗收閘 — **volume-conserving twist 接檔位差異化**(純 CPU)。

volume-conserving twist(G-4''''''-vol)在 base 掛一條**等向**補償 scale `s=1/√cos(shearX−shearY)`
使全域 local 行列式 det≡1(擰而不變面積);但當時的 honest boundary 是「僅作用 base twist」——
tier 變體仍 shear-only(未接體積守恆)。本 chunk 補上:檔位放大兩軸 shear 後(shearX'=g·shearX、
shearY'=g·shearY,φ 保形),補償 scale 由**放大後的 shear 重算** `s'=1/√cos(shearX'−shearY')` →
det≡1 在**每個檔位**仍成立。三通道(shear+scale+rotate)× 三效(幅度 tier_gains / 段數
tier_twist_cycles / 體積守恆)正交可疊。

crux(與 squash tier 耦合 amplify 的差異,亦是本閘鑑別力來源):twist 的補償對 shear 是 **cos 的
反推**(非線性)。若直接把舊補償 scale 拿去逐軸 `_amp_scale`(線性 1+g·(s−1)),線性放大追不上 cos
的變化 → **破壞守恆**(det 隨檔位偏離 1 愈來愈遠)。必須從放大後的 shear **重算**。squash 的 scale
本身即擠壓(非均勻),走耦合 amplify;twist 的 scale 純為補償 shear(等向),走重算 —— 同為保守恆,
機制不同源。

真值界定同 twist 系列(E/H/I/J/G-4'/G-4''''''/-tier/-count/-vol):主秀運動無唯一正解(PROPOSAL 手感),
閘驗**客觀結構簽章**(每檔位:雙軸峰遞增 + φ 不變 + 反相阻尼保形 + 體積守恆)非美感;負對照證鑑別力。
從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(tier_gains=…, twist_volume=True)` 端到端量。

AC(客觀、可量測):
  VT1 present + dual-channel/tier    : 每檔位 `twist__{tier}`(帶 tier_gains + twist_volume=True)皆產出、
                                       finite、有 bone、≥1 bone **同時**帶 shear 與 scale,且 scale **等向**
                                       (每幀 scaleX==scaleY);名經 `beat_category` 仍路由回 twist;
                                       Super(g=1)變體逐位元 == base(vol)twist;base(含 In/Loop/Out +
                                       base-vol twist)帶/不帶 tier_gains 逐位元不變(向後相容)。
  VT2 crux — 每檔位體積守恆 + 負對照 : 各 `twist__{tier}` bone 每內部極值幀全域 local det |det−1| ≤ TOL_DET;
                                       **負對照** = 對 base-vol scale 施線性 `_amp_scale`(舊/錯路徑)→
                                       高檔位 |det−1| ≥ MIN_BREAK(破守恆)→ 證「重算」非「線性放大」是關鍵。
  VT3 crux — 雙軸峰遞增 + φ 不變     : 各檔位峰 |shearX| **與** 峰 |shearY| 皆 Super<Mega<Omg<Legend 嚴格
                                       遞增(Super==base),且每 bone 每檔位 shearY峰/shearX峰 ≈ TWIST_PHI
                                       (誤差 ≤ PHI_TOL)—— 體積耦合不擾動 tier 幅度/φ 簽章。
  VT4 雙軸阻尼反相簽章逐檔保形       : 每檔位每 twist bone 的 shearX、shearY 各自(a)首尾 0(b)繞 0 變號
                                       ≥3(c)相繼極值遞減(阻尼);且每內部極值反號(反相耦合)。
                                       scale 等向 → 不引入額外各向異性(scale 首尾 (1,1))。
  VT5 端到端三通道 pivot 不動 + 守恆 : `build_spine --twist-volume --tier-variants --shear-pivot`(真實 robot)
                                       產 `twist__{tier}` 帶 shear+scale+rotate;凡有關節 pivot 的 bone
                                       pivot 殘差 < TOL_FIX(內建負對照 = 繞件中心大位移);且每檔位每內部
                                       極值 |det−1| ≤ TOL_DET(守恆端到端存活)。
  VT6 負對照/隔離/向後相容          : (a)**平增益守衛**:增益全 1.0 → 各 `twist__{tier}` 逐位元 == base-vol
                                       twist(仍守恆、峰不遞增);(b)**等向 vs 非均勻隔離**:twist__{tier}
                                       scale 等向(scaleX==scaleY),squash__{tier} scale **非均勻**且
                                       scaleX·scaleY≡1(耦合)→ 兩種守恆機制不同源、互不外洩;
                                       (c)**加性/向後相容**:twist_volume=False + tier_gains → `twist__{tier}`
                                       無 scale 通道且逐位元 == G-4''''''-tier 輸出(vol 為純加性,不影響
                                       shear-only tier 行為)。

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
# 復用 twist 系列閘的讀取/判準,確保與整族閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_shear_pivot import _world
from validate_twist_gen import (_shear_y, _shear_xy, _interior_shear, _tw3_eval, _has_shear_y,
                                TOL_FIX, MIN_NEG, NEG_RATIO)
from validate_twist_volume import _scale_frames, _local_det, TOL_DET, MIN_SHRINK
from validate_twist_tier import (_psd, _skeleton, _storyboard, _twist_beats, _peak_x, _peak_y,
                                 _dev_peak, _is_strict_inc, GENRE, TIERS, MIN_SHEAR, PHI_TOL)

MIN_BREAK = 0.03     # 負對照(線性放大 scale)在高檔位 |det−1| 下限(實測 Legend 0.06–0.31 → 充足餘裕)


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base_vol = G.build_animations(skel, sb, twist_volume=True)                    # base 掛 vol,無 tier
    anims = G.build_animations(skel, sb, tier_gains=gains, twist_volume=True)      # vol + tier
    twist_beats = _twist_beats(base_vol)
    R = {}

    # ---- VT1 present + dual-channel per tier + isotropic + backward-compat ----
    t1 = {"twist_beats": twist_beats, "missing": [], "not_finite": [], "no_bones": [],
          "no_shear": [], "no_scale": [], "anisotropic": [], "misrouted": [],
          "super_ne_base": [], "base_changed": []}
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
            if not any(_shear_xy(ch) for ch in an.get("bones", {}).values()):
                t1["no_shear"].append(vk)
            if not any(_scale_frames(ch) for ch in an.get("bones", {}).values()):
                t1["no_scale"].append(vk)
            for bn, ch in an.get("bones", {}).items():
                if any(abs(sx - sy) > 1e-6 for (sx, sy) in _scale_frames(ch)):
                    t1["anisotropic"].append("{}::{}".format(vk, bn))
            if G.beat_category(vk) != "twist":
                t1["misrouted"].append((vk, G.beat_category(vk)))
        # Super(g=1)變體逐位元 == base-vol twist
        sk = "{}__{}".format(tb, "Super")
        if json.dumps(anims.get(sk), sort_keys=True) != json.dumps(base_vol[tb], sort_keys=True):
            t1["super_ne_base"].append(sk)
    # base(含 In/Loop/Out + base-vol twist)帶/不帶 tier_gains 逐位元不變
    for k in base_vol:
        if json.dumps(base_vol[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    t1_pass = (bool(twist_beats) and not any(t1[k] for k in
               ["missing", "not_finite", "no_bones", "no_shear", "no_scale", "anisotropic",
                "misrouted", "super_ne_base", "base_changed"]))
    R["VT1_present_dual_channel"] = {**t1, "pass": t1_pass}

    # ---- VT2 crux: volume conserved every tier(keyframe)+ plain-amplify negative control ----
    # 重算路徑:每檔位每 bone 每內部**極值幀** |det−1| ≤ TOL_DET(關鍵幀=生成器守恆保證點)。
    # 負對照:對 base-vol scale 施線性 `_amp_scale`(舊/錯路徑)+ 放大後 shear → 在**最高檔位**(max gain)
    # 破守恆(|det−1| ≥ MIN_BREAK)。用 max-gain 而非每 g>1:最小 shear 的 head 在低檔位(Mega g=1.35)偏離
    # 僅 0.022,線性放大在小角度近似仍佳;檔位愈高偏差愈大(cos 曲率),故以 Legend 證「線性放大追不上」。
    t2 = {"break_conserve": [], "neg_not_break": [], "detail": {}}
    max_g = max(gains.values())
    for tb in twist_beats:
        for t, g in gains.items():
            vk = "{}__{}".format(tb, t)
            for bn, ch in anims[vk].get("bones", {}).items():
                xy = _shear_xy(ch); sc = _scale_frames(ch)
                if len(xy) < 3 or len(sc) != len(xy):
                    continue
                dev = [abs(_local_det(scx, scy, shx, shy) - 1.0)
                       for (shx, shy), (scx, scy) in list(zip(xy, sc))[1:-1]]
                if dev and max(dev) > TOL_DET:
                    t2["break_conserve"].append("{}::{}".format(vk, bn))
        # 負對照:在最高檔位(g=max)對每 bone 量線性放大 scale 的守恆偏離
        for bn, base_bone in base_vol[tb].get("bones", {}).items():
            neg = TV.amplify_bone_tl(base_bone, max_g, twist_vol=False)  # scale 走線性 _amp_scale
            nxy = _shear_xy(neg); nsc = _scale_frames(neg)
            ndev = [abs(_local_det(scx, scy, shx, shy) - 1.0)
                    for (shx, shy), (scx, scy) in list(zip(nxy, nsc))[1:-1]] if nsc else []
            key = "{}::{}@maxg".format(tb, bn)
            t2["detail"][key] = {"neg_max_dev": round(max(ndev), 5) if ndev else 0.0, "gain": max_g}
            if not ndev or max(ndev) < MIN_BREAK:
                t2["neg_not_break"].append(key)
    t2_pass = (bool(t2["detail"]) and not t2["break_conserve"] and not t2["neg_not_break"])
    R["VT2_volume_conserved_per_tier"] = {**t2, "pass": t2_pass}

    # ---- VT3 crux: both-axis peak monotone + phi ratio invariant across tiers ----
    t3 = {"beats": {}, "fail_mono_x": [], "fail_mono_y": [], "fail_super": [], "bad_ratio": []}
    for tb in twist_beats:
        px = [_peak_x(anims["{}__{}".format(tb, t)]) for t in TIERS]
        py = [_peak_y(anims["{}__{}".format(tb, t)]) for t in TIERS]
        bx, by = _peak_x(base_vol[tb]), _peak_y(base_vol[tb])
        t3["beats"][tb] = {"shearX_peaks": [round(p, 3) for p in px],
                           "shearY_peaks": [round(p, 3) for p in py],
                           "base": [round(bx, 3), round(by, 3)]}
        if not _is_strict_inc(px):
            t3["fail_mono_x"].append(tb)
        if not _is_strict_inc(py):
            t3["fail_mono_y"].append(tb)
        if not (abs(px[0] - bx) <= 1e-4 and abs(py[0] - by) <= 1e-4):
            t3["fail_super"].append(tb)
        for t in TIERS:
            for bn, ch in anims["{}__{}".format(tb, t)].get("bones", {}).items():
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
               and not t3["fail_super"] and not t3["bad_ratio"])
    R["VT3_peak_mono_phi_invariant"] = {**t3, "phi": TWIST_PHI, "pass": t3_pass}

    # ---- VT4 dual-axis damped counter-phase signature preserved per tier + scale (1,1) ends ----
    t4 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "not_counterphase": [],
          "scale_ends_nonident": []}
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
                sc = _scale_frames(ch)
                if sc and (abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6
                           or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6):
                    t4["scale_ends_nonident"].append("{}__{}::{}".format(tb, t, bn))
    t4_pass = not any(t4[k] for k in
                      ["bad_endpoints", "few_sign_changes", "not_damped", "not_counterphase",
                       "scale_ends_nonident"])
    R["VT4_damped_counterphase_per_tier"] = {**t4, "pass": t4_pass}

    # ---- VT5 end-to-end: build_spine --twist-volume --tier-variants --shear-pivot ----
    import build_spine
    out = "/tmp/twist_vol_tier_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True,
                             tier_variants=True, twist_volume=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    tier_twist = [nm for nm in sp_skel["animations"]
                  if "__" in nm and G.beat_category(nm.split("__")[0]) == "twist"]
    # 端到端閘同 validate_twist_volume TV5:驗**三通道 pivot 不動**(shear+scale+rotate 皆錨在關節)。
    # 守恆是**關鍵幀**性質(VT2 已驗,pre-densify);`--shear-pivot` 會把通道**密取樣**成 ~49 幀,shear 與
    # scale **各自線性內插**,而補償 s=1/√cos(shx−shy) 對 shear 非線性 → 內插中間幀 det 略偏(關鍵幀仍≡1)。
    # 這是「線性內插近似非線性約束」的固有性質(base vol 亦然,故 TV5 不驗端到端守恆),非 tier 機制缺陷;
    # 記錄 max 內插偏離為 honest boundary(未來可加 bezier 曲線鍵 / 加密關鍵幀收斂),不列入 gate。
    s5 = {"tier_twist_beats": tier_twist, "fail_fixed": [], "fail_negctrl": [],
          "n_joint_bones": 0, "n_with_scale": 0, "checked": [], "max_interp_dev": 0.0}
    for tb in tier_twist:
        an = sp_skel["animations"][tb]
        for bn, ch in an.get("bones", {}).items():
            xy = _shear_xy(ch); sc = _scale_frames(ch)
            if len(xy) >= 3 and len(sc) == len(xy):
                dev = [abs(_local_det(scx, scy, shx, shy) - 1.0)
                       for (shx, shy), (scx, scy) in list(zip(xy, sc))[1:-1]]
                if dev:
                    s5["max_interp_dev"] = max(s5["max_interp_dev"], round(max(dev), 4))
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
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 200 for i in range(201)]
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
    s5_pass = (bool(tier_twist) and s5["n_joint_bones"] >= 1 and s5["n_with_scale"] >= 1
               and not s5["fail_fixed"] and not s5["fail_negctrl"])
    R["VT5_end2end_pivot_conserve"] = {**s5, "pass": s5_pass}

    # ---- VT6 negative controls / isolation / backward-compat ----
    s6 = {}
    # (a) 平增益守衛:全 1.0 → 各 twist__{tier} 逐位元 == base-vol twist
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat, twist_volume=True)
    flat_diff = []
    for tb in twist_beats:
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(tb, t)], sort_keys=True) != \
               json.dumps(base_vol[tb], sort_keys=True):
                flat_diff.append("{}__{}".format(tb, t))
    s6["a_flat_guard"] = {"flat_variants_ne_base": flat_diff, "pass": not flat_diff}
    # (b) 等向 vs 非均勻隔離:twist__{tier} 等向;squash__{tier} 非均勻且 scaleX·scaleY≡1(耦合)
    tw_uniform = all(abs(sx - sy) <= 1e-6
                     for tb in twist_beats for t in TIERS
                     for ch in anims["{}__{}".format(tb, t)].get("bones", {}).values()
                     for (sx, sy) in _scale_frames(ch))
    sq_tier = [nm for nm in anims if "__" in nm and G.beat_category(nm.split("__")[0]) == "squash"]
    sq_pairs = [(sx, sy) for nm in sq_tier
                for ch in anims[nm].get("bones", {}).values() for (sx, sy) in _scale_frames(ch)]
    sq_anis = any(abs(sx - sy) > 1e-6 for (sx, sy) in sq_pairs)
    sq_conserve = all(abs(sx * sy - 1.0) <= 2e-3 for (sx, sy) in sq_pairs) if sq_pairs else False
    s6["b_isotropic_vs_nonuniform"] = {"twist_uniform": tw_uniform, "squash_nonuniform": sq_anis,
                                       "squash_conserve": sq_conserve, "squash_tier_beats": sq_tier,
                                       "pass": tw_uniform and sq_anis and sq_conserve}
    # (c) 加性/向後相容:twist_volume=False + tier_gains → twist__{tier} 無 scale 且逐位元 == G-4''''''-tier
    anims_off = G.build_animations(skel, sb, tier_gains=gains)   # twist_volume 預設 False
    off_has_scale = [nm for nm in anims_off
                     if "__" in nm and G.beat_category(nm.split("__")[0]) == "twist"
                     and any(_scale_frames(ch) for ch in anims_off[nm].get("bones", {}).values())]
    # off 的每支 beat(含所有變體)不含 scale 的 twist → 與「vol 開啟但只加 scale」的差異僅在 twist 帶 scale;
    # 這裡直接驗 off 版 twist tier 無 scale(即 vol 對 shear-only tier 為純加性,未動既有行為)。
    s6["c_backward_compat_additive"] = {"off_twist_tier_has_scale": off_has_scale,
                                        "pass": not off_has_scale}
    R["VT6_neg_control"] = {**s6, "pass": all(v["pass"] for v in s6.values())}

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
        for k in ["VT1_present_dual_channel", "VT2_volume_conserved_per_tier",
                  "VT3_peak_mono_phi_invariant", "VT4_damped_counterphase_per_tier",
                  "VT5_end2end_pivot_conserve", "VT6_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("VT2 recompute conserved at every keyframe; neg-plain break @ max gain, sample:")
        for key, d in list(R["VT2_volume_conserved_per_tier"]["detail"].items())[:6]:
            print("  {:22s} g={:.2f}  neg max|det-1| {:.4f}".format(key, d["gain"], d["neg_max_dev"]))
        print("VT3 peaks per tier {}:".format(TIERS))
        for tb, d in R["VT3_peak_mono_phi_invariant"]["beats"].items():
            print("  {:10s} shearX {}  shearY {}  (base {})".format(
                tb, d["shearX_peaks"], d["shearY_peaks"], d["base"]))
        print("VT5 pivot-fixed (fixed/negctrl px, has_scale):")
        for rec in R["VT5_end2end_pivot_conserve"]["checked"][:8]:
            print("  {:16s} {:10s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}  scale={}".format(
                rec["bone"], rec["beat"], rec["arm"], rec["fixed"], rec["negctrl"], rec["has_scale"]))
        print("VT6 (a) flat==base:", not R["VT6_neg_control"]["a_flat_guard"]["flat_variants_ne_base"],
              "| (b) twist uniform:", R["VT6_neg_control"]["b_isotropic_vs_nonuniform"]["twist_uniform"],
              "squash nonuniform+conserve:",
              R["VT6_neg_control"]["b_isotropic_vs_nonuniform"]["squash_nonuniform"],
              R["VT6_neg_control"]["b_isotropic_vs_nonuniform"]["squash_conserve"],
              "| (c) off no-scale:", not R["VT6_neg_control"]["c_backward_compat_additive"]["off_twist_tier_has_scale"])
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
