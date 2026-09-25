#!/usr/bin/env python3
"""candidate G-4''''''-vol 自我驗收閘 — 生成器產**反相雙軸 shear + 均勻體積守恆 scale**(擰而不變面積)端到端(純 CPU)。

補 twist(G-4'''''')留到現在的 honest boundary —— twist 是反相雙軸阻尼 shear(shearX + 反相 shearY),
但**純 shear 會改變面積**:Spine local 2×2 的 `det(M) = scaleX·scaleY·cos(shearX − shearY)`;twist 令
scaleX=scaleY=1、shearY=−φ·shearX ⇒ `det = cos((1+φ)·shearX) < 1`(擰轉時面積收縮,峰值 ~8.5%)。
squash(G-4'''')以**非均勻**體積守恆 scale(scaleX·scaleY≡1 且 scaleX≠scaleY)解 shearX 的體積問題;
本節拍 `gen_twistvol` 對**反相雙軸** shear 施**均勻**體積守恆 scale —— **crux 區別**:twist 的面積虧損
`cos(shearX−shearY)` 是各向同性的行列式虧損(不偏好任何軸),補回它最乾淨的方式是**均勻**放大
scaleX=scaleY=s=1/√(cos(shearX−shearY)) ⇒ `det≡1`(面積守恆)且**長寬比不變**(不引入 squash 的擠壓)。
⇒ **產線第一個把一般仿射四自由度(rotate/scale/shearX/shearY)同時用滿且面積守恆的節拍**。

真值/fixture 與 (G-4'/G-4''''/G-4'''''') 一致:從**先驗庫**(slot_bigwin,新增 twistvol beat)經
`analyze_target` → **真實 build_spine robot 骨架** → `build_animations` 端到端量。主秀運動無唯一正解
(PROPOSAL 手感),閘驗**客觀結構簽章(體積守恆 det≡1 + 均勻 scale + twist 全簽章保形)+ 端到端不動點**,
非美感;負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  TV1 present + dual-axis + scale emitted : twistvol beat 直出、finite、有 bone;≥1 bone 帶 shear,
                                           shearX 峰 ≥ MIN_SHEAR **且** shearY 峰 ≥ MIN_SHEAR(仍雙軸);
                                           **且**帶 scale 通道、補償峰 max|s−1| ≥ MIN_COMP(非平凡 scale)。
  TV2 volume conservation(crux)         : 每個 twistvol bone 的**每個關鍵幀** det=scaleX·scaleY·cos(shearX−shearY)
                                           滿足 |det−1| ≤ TOL_VOL(面積守恆);內建負對照 = 同 shear 但 s≡1
                                           (純 twist)→ 峰值 det<1−MARGIN(證閘測的是守恆非「有 scale 即可」)。
  TV3 uniform scale(crux vs squash)     : 每個 twistvol bone 每關鍵幀 scaleX==scaleY(|sx−sy| ≤ TOL_UNIF,
                                           **均勻**=不改長寬比,與 squash 的非均勻 scaleX≠scaleY 區別);
                                           且內部極值 s ≥ 1(補償放大)、|s−1| 隨極值嚴格遞減(隨 shear 阻尼)。
  TV4 twist signature preserved          : 加 scale 通道**不擾動 shear** —— (a)twistvol 的 shear 通道與同參數
                                           `gen_twist` **逐鍵相同**;(b)兩軸各自阻尼振盪(繞 0 變號≥3 + 相繼極值遞減);
                                           (c)每內部極值反相 shearX·shearY<0;(d)shearY 峰/shearX 峰 ≈ TWIST_PHI。
  TV5 identity interface(可插 Loop)      : sample(0)/sample(dur) 各 bone identity;shear 首尾 (0,0)、scale 首尾 (1,1)。
  TV6 端到端一般仿射 pivot 不動           : `build_spine --shear-pivot`(真實 robot)產 twistvol 帶補償;凡有關節
                                           pivot 的 bone,pivot 殘差 < TOL_FIX(**在 shearY≠0 且 scale≠1 同時驅動下**);
                                           內建負對照 = 未補償(繞件中心)大位移 → 證補償把四通道仿射也錨在 pivot。
  TV7 負對照/隔離                        : (a)**體積守衛**:合成純 twist 極值(s≡1)→ TV2 守恆 FALSE;
                                           (b)**均勻守衛**:合成非均勻 scale(scaleX≠scaleY,squash 樣)→ TV3 均勻 FALSE;
                                           (c)**shearY 隔離**:非 SHEARY_CATS beat 皆 shearY≡0(shearY 由 twist/twistvol 獨佔);
                                           (d)**加性**:移除 twistvol 的 storyboard → 其餘 beat 逐位元不變(零回歸)。

用法:
  python3 validate_twist_vol.py            # 摘要
  python3 validate_twist_vol.py --json     # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim as SA
import gen_animations as G
import tier_variants as _TV
import beat_templates as BT
from beat_templates import TWIST_PHI
# 復用既有判準,確保與 shear-gen / twist-gen / squash-gen 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_twist_gen import _shear_y, _shear_xy, _interior_shear, _tw3_eval, _has_shear_y
from validate_squash_gen import _scale_xy, _interior_scale
from validate_shear_pivot import _world   # 真實 Spine local(含雙軸 shear + scale)世界座標求值

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,twistvol 兩軸峰下限(head:shearX 10°、shearY 7° → 餘裕)
MIN_COMP = 5e-3     # 補償 scale 峰 max|s−1| 下限(head shx−shy=17° → s≈1.023 → |s−1|≈0.023 餘裕)
TOL_VOL = 2e-3      # |det−1| 上限(scale 6 位、shear 4 位捨入下的餘裕)
VOL_MARGIN = 0.02   # 負對照純 twist 峰值 det 至少低於 1 的量(峰 det≈0.915 → 餘裕)
TOL_UNIF = 1e-6     # |scaleX−scaleY| 上限(均勻:由建構 sx==sy)
TOL_FIX = 0.5       # px,pivot 不動點殘差上限(同 G-4/G-4'/G-4''''/G-4'''''')
MIN_NEG = 5.0       # px,TV6 負對照(未補償)位移下限
NEG_RATIO = 20.0    # 負對照/不動點 位移比下限
PHI_TOL = 2e-3      # shearY峰/shearX峰 對 TWIST_PHI 的容差(同 twist-tier/count)


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/twistvol_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    from analyze_target import analyze
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _twistvol_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "twistvol"]


def _det_frames(chans):
    """回傳每關鍵幀 (t, det=scaleX·scaleY·cos(shearX−shearY))。shear/scale 由建構同 τ 點、同長度。"""
    sh = chans.get("shear") or []
    sc = chans.get("scale") or []
    if not sh or not sc or len(sh) != len(sc):
        return []
    out = []
    for fs, fc in zip(sh, sc):
        det = fc["x"] * fc["y"] * math.cos(math.radians(fs["x"] - fs["y"]))
        out.append((fs["time"], det))
    return out


def _det_no_scale(chans):
    """負對照:同 shear 但 s≡1(純 twist)→ 每幀 det=cos(shearX−shearY)(峰值 <1)。"""
    return [(fs["time"], math.cos(math.radians(fs["x"] - fs["y"]))) for fs in (chans.get("shear") or [])]


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    tv_beats = _twistvol_beats(anims)
    R = {}

    # ---- TV1 present + dual-axis + scale emitted ----
    s1 = {"twistvol_beats": tv_beats, "not_finite": [], "no_bones": [], "no_shear": [],
          "no_scale": [], "weak_shearx": [], "weak_sheary": [], "weak_comp": [], "peak_by_beat": {}}
    for tb in tv_beats:
        an = anims[tb]
        if not SA.all_finite(an):
            s1["not_finite"].append(tb)
        if not an.get("bones"):
            s1["no_bones"].append(tb)
        sheared = {bn: ch for bn, ch in an.get("bones", {}).items() if _shear_xy(ch)}
        scaled = {bn: ch for bn, ch in an.get("bones", {}).items() if _scale_xy(ch)}
        if not sheared:
            s1["no_shear"].append(tb); continue
        if not scaled:
            s1["no_scale"].append(tb)
        shx_pk = max(max(abs(v) for v in _shear_x(ch)) for ch in sheared.values())
        shy_pk = max(max(abs(v) for v in _shear_y(ch)) for ch in sheared.values())
        comp_pk = max((max(abs(sx - 1.0) for (sx, sy) in _scale_xy(ch)) for ch in scaled.values()),
                      default=0.0)
        s1["peak_by_beat"][tb] = {"shearX": round(shx_pk, 3), "shearY": round(shy_pk, 3),
                                  "scale_comp": round(comp_pk, 5)}
        if shx_pk < MIN_SHEAR:
            s1["weak_shearx"].append(tb)
        if shy_pk < MIN_SHEAR:
            s1["weak_sheary"].append(tb)
        if comp_pk < MIN_COMP:
            s1["weak_comp"].append(tb)
    s1_pass = (bool(tv_beats) and not s1["not_finite"] and not s1["no_bones"] and not s1["no_shear"]
               and not s1["no_scale"] and not s1["weak_shearx"] and not s1["weak_sheary"]
               and not s1["weak_comp"])
    R["TV1_present_dual_axis_scale"] = {**s1, "pass": s1_pass}

    # ---- TV2 volume conservation (crux) + built-in negative control ----
    s2 = {"bad_frames": [], "max_det_err": 0.0, "negctrl_min_det": 1.0, "detail": {}}
    for tb in tv_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            dets = _det_frames(ch)
            if not dets:
                continue
            errs = [abs(d - 1.0) for (_, d) in dets]
            me = max(errs)
            s2["max_det_err"] = max(s2["max_det_err"], me)
            s2["detail"]["{}::{}".format(tb, bn)] = {"max_det_err": round(me, 6),
                                                     "dets": [round(d, 6) for (_, d) in dets]}
            if me > TOL_VOL:
                s2["bad_frames"].append("{}::{}".format(tb, bn))
            # 內建負對照:同 shear、s≡1 → 峰值 det<1(擰轉未補償變面積)
            ns = _det_no_scale(ch)
            if ns:
                s2["negctrl_min_det"] = min(s2["negctrl_min_det"], min(d for (_, d) in ns))
    s2_pass = (bool(s2["detail"]) and not s2["bad_frames"]
               and s2["negctrl_min_det"] < 1.0 - VOL_MARGIN)
    R["TV2_volume_conservation"] = {**s2, "max_det_err": round(s2["max_det_err"], 6),
                                    "negctrl_min_det": round(s2["negctrl_min_det"], 6), "pass": s2_pass}

    # ---- TV3 uniform scale (crux vs squash) + compensating + damped ----
    s3 = {"non_uniform": [], "not_compensating": [], "not_damped": [], "detail": {}}
    for tb in tv_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            sxy = _scale_xy(ch)
            if not sxy:
                continue
            key = "{}::{}".format(tb, bn)
            unif = max(abs(sx - sy) for (sx, sy) in sxy)
            interior = _interior_scale(ch)             # 去首尾 (1,1)
            comps = [sx - 1.0 for (sx, sy) in interior]   # 均勻 → sx==sy,取 sx 代表
            comp_ok = bool(comps) and all(c >= -1e-9 for c in comps)   # 補償放大(s≥1)
            mags = [abs(c) for c in comps]
            damp_ok = len(mags) >= 2 and all(mags[i + 1] < mags[i] - 1e-9 for i in range(len(mags) - 1))
            s3["detail"][key] = {"max_uniform_err": round(unif, 7),
                                 "interior_comp": [round(c, 5) for c in comps]}
            if unif > TOL_UNIF:
                s3["non_uniform"].append(key)
            if not comp_ok:
                s3["not_compensating"].append(key)
            if not damp_ok:
                s3["not_damped"].append(key)
    s3_pass = (bool(s3["detail"]) and not s3["non_uniform"]
               and not s3["not_compensating"] and not s3["not_damped"])
    R["TV3_uniform_scale"] = {**s3, "pass": s3_pass}

    # ---- TV4 twist signature preserved (shear undisturbed by scale) ----
    s4 = {"shear_differs_from_twist": [], "bad_endpoints": [], "few_sign_changes": [],
          "not_damped": [], "not_counterphase": [], "bad_phi": [], "detail": {}}
    # (a) 單元:twistvol 的 shear 通道與同參數 gen_twist 逐鍵相同(scale 純加性,不擾動 shear)
    for role in ("body", "head", "limb", "特效"):
        for ss in (1.0, -1.0):
            bt_vol, _ = BT.gen_twistvol(role, ss, (0.0, 0.0), 4)
            bt_tw, _ = BT.gen_twist(role, ss, (0.0, 0.0), 4)
            if json.dumps(bt_vol.get("shear"), sort_keys=True) != json.dumps(bt_tw.get("shear"), sort_keys=True):
                s4["shear_differs_from_twist"].append("{}/{}".format(role, ss))
    # (b–d) 端到端每 twistvol bone 兩軸阻尼振盪 + 反相 + φ 比值
    for tb in tv_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            sx_vals, sy_vals = _shear_x(ch), _shear_y(ch)
            if not sx_vals or not _has_shear_y(ch):
                continue
            key = "{}::{}".format(tb, bn)
            for axis, vals in (("x", sx_vals), ("y", sy_vals)):
                ends_ok = abs(vals[0]) < 1e-6 and abs(vals[-1]) < 1e-6
                if not ends_ok:
                    s4["bad_endpoints"].append(key + "::" + axis)
                if _sign_changes_zero(vals) < 3:
                    s4["few_sign_changes"].append(key + "::" + axis)
                if not _extrema_mags_decreasing(vals):
                    s4["not_damped"].append(key + "::" + axis)
            interior = _interior_shear(ch)
            cp_ok, _, _ = _tw3_eval(interior)
            if not cp_ok:
                s4["not_counterphase"].append(key)
            shx_pk = max(abs(v) for v in sx_vals)
            shy_pk = max(abs(v) for v in sy_vals)
            phi = shy_pk / shx_pk if shx_pk else 0.0
            s4["detail"][key] = {"phi": round(phi, 5)}
            if abs(phi - TWIST_PHI) > PHI_TOL:
                s4["bad_phi"].append(key)
    s4_pass = (not s4["shear_differs_from_twist"] and not s4["bad_endpoints"]
               and not s4["few_sign_changes"] and not s4["not_damped"]
               and not s4["not_counterphase"] and not s4["bad_phi"] and bool(s4["detail"]))
    R["TV4_twist_signature_preserved"] = {**s4, "pass": s4_pass}

    # ---- TV5 identity interface ----
    s5 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for tb in tv_beats:
        an = anims[tb]
        dur = SA.duration(an)
        start = SA.sample(an, 0.0)["bones"]
        end = SA.sample(an, dur)["bones"]
        if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
            s5["bad_interface"].append(tb)
        for bn, ch in an.get("bones", {}).items():
            xy = _shear_xy(ch)
            if xy and (abs(xy[0][0]) > 1e-6 or abs(xy[0][1]) > 1e-6
                       or abs(xy[-1][0]) > 1e-6 or abs(xy[-1][1]) > 1e-6):
                s5["shear_endpoints_nonzero"].append("{}::{}".format(tb, bn))
            sxy = _scale_xy(ch)
            if sxy and (abs(sxy[0][0] - 1.0) > 1e-6 or abs(sxy[0][1] - 1.0) > 1e-6
                        or abs(sxy[-1][0] - 1.0) > 1e-6 or abs(sxy[-1][1] - 1.0) > 1e-6):
                s5["scale_endpoints_nonident"].append("{}::{}".format(tb, bn))
    R["TV5_identity_interface"] = {**s5, "pass": (not s5["bad_interface"]
                                                 and not s5["shear_endpoints_nonzero"]
                                                 and not s5["scale_endpoints_nonident"])}

    # ---- TV6 end-to-end general-affine pivot-fixed via build_spine --shear-pivot ----
    import build_spine
    out = "/tmp/twistvol_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    s6 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0}
    for tb in _twistvol_beats(sp_skel["animations"]):
        an = sp_skel["animations"][tb]
        for bn, ch in an.get("bones", {}).items():
            if bn not in joints or bn not in centers:
                continue
            O = np.array(centers[bn], float); P = np.array(joints[bn], float)
            ellP = P - O
            tr = ch.get("translate")
            if not tr:
                continue
            s6["n_joint_bones"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"bone": bn, "beat": tb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            s6["checked"].append(rec)
            if not (fix < TOL_FIX):
                s6["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                s6["fail_negctrl"].append(rec)
    s6_pass = (s6["n_joint_bones"] >= 1 and not s6["fail_fixed"] and not s6["fail_negctrl"])
    R["TV6_end2end_affine_pivot_fixed"] = {**s6, "pass": s6_pass}

    # ---- TV7 negative controls / isolation ----
    s7 = {}
    # (a) 體積守衛:純 twist 極值(s≡1)→ det=cos<1 → 守恆 FALSE(證閘測守恆,非「有 scale 即可」)
    tw_ch = None
    for tb in tv_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            if _shear_xy(ch):
                tw_ch = ch; break
        if tw_ch:
            break
    ns = _det_no_scale(tw_ch) if tw_ch else []
    vol_guard_fail = bool(ns) and min(d for (_, d) in ns) < 1.0 - VOL_MARGIN
    s7["a_volume_guard"] = {"min_det_no_scale": round(min((d for (_, d) in ns), default=1.0), 6),
                            "pass": vol_guard_fail}
    # (b) 均勻守衛:合成非均勻 scale(scaleX≠scaleY,squash 樣)→ 均勻判準 FALSE
    nonuni = [(1.14, 0.877), (1.07, 0.935), (1.035, 0.966)]   # scaleX·scaleY≈1 但 sx≠sy(squash 樣)
    uniform_ok = all(abs(sx - sy) <= TOL_UNIF for (sx, sy) in nonuni)
    s7["b_uniform_guard"] = {"uniform_ok": uniform_ok, "pass": not uniform_ok}
    # (c) shearY 隔離:非 SHEARY_CATS beat 皆 shearY≡0(shearY 由 twist/twistvol 獨佔)
    leak_y = []
    for nm, an in anims.items():
        if "__" in nm or G.beat_category(nm) in _TV.SHEARY_CATS:
            continue
        for bn, ch in an.get("bones", {}).items():
            if _has_shear_y(ch):
                leak_y.append((nm, bn))
    s7["c_sheary_isolated"] = {"leaked": leak_y, "pass": not leak_y}
    # (d) 加性:移除 twistvol 的 storyboard → 其餘 beat 逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "twistvol"]}
    anims_no = G.build_animations(skel, sb_no)
    regressed = []
    for nm, an in anims_no.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    s7["d_additive_no_regression"] = {"regressed": regressed,
                                      "removed_beats": [b["beat"] for b in sb["beats"]
                                                        if G.beat_category(b["beat"]) == "twistvol"],
                                      "pass": not regressed}
    R["TV7_neg_control"] = {**s7, "pass": all(v["pass"] for v in s7.values())}

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
        for k in ["TV1_present_dual_axis_scale", "TV2_volume_conservation", "TV3_uniform_scale",
                  "TV4_twist_signature_preserved", "TV5_identity_interface",
                  "TV6_end2end_affine_pivot_fixed", "TV7_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("TV1 peaks by beat:", R["TV1_present_dual_axis_scale"]["peak_by_beat"])
        print("TV2 max |det-1|:", R["TV2_volume_conservation"]["max_det_err"],
              " negctrl(no-scale) min det:", R["TV2_volume_conservation"]["negctrl_min_det"])
        print("TV6 pivot-fixed (fixed/negctrl px):")
        for rec in R["TV6_end2end_affine_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
