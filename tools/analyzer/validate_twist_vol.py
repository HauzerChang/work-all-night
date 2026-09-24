#!/usr/bin/env python3
"""candidate G-4''''''-vol 自我驗收閘 — 生成器產出**體積(面積)守恆**的反相雙軸 shier 扭轉端到端(純 CPU)。

補上 twist(G-4'''''')一路留到現在的 honest boundary:twist 產反相雙軸 shear 但**擰轉會變面積** ——
真實 Spine local M 的 det(M)=scaleX·scaleY·cos(shearX−shearY);twist 無 scale(scaleX≡scaleY≡1)、
反相 shearX≠shearY → det=cos((1+φ)shearX)<1(擰愈狠面積縮愈多,一般仿射非等積)。本閘(G-4''''''-vol)驗證:
生成器 `gen_twist_vol` 在**每個 shear 極值**施耦合 **uniform** scale s=1/√cos(shearX−shearY) 使
**det(M)≡1(真面積守恆)且 scaleX==scaleY(uniform)** —— 塞滿一般仿射四自由度(旋轉/uniform scale/雙軸 shear)
且等積。經先驗庫直出;`build_spine --shear-pivot` 端到端把 rotate/scale/shearX/shearY 一起繞關節 pivot 補償 →
件做**面積守恆的一般仿射**變換而 pivot 精確不動。

真值/fixture 與 (twist G-4''''''/squash G-4'''') 一致:從**先驗庫**(slot_bigwin,新增 twistvol beat)經
`analyze_target` → **真實 build_spine robot 骨架** → `build_animations` 端到端量。主秀運動無唯一正解
(PROPOSAL 手感),閘驗**客觀結構簽章(反相雙軸阻尼振盪 + 真面積守恆 + uniform scale)+ 端到端不動點**,非美感;
負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  TV1 present + dual-axis + uniform 補償 scale(crux): twistvol beat 直出、finite、有 bone,且 ≥1 bone 同時帶
                                     shear(shearX 峰≥MIN_SHEAR·shearY 峰≥MIN_SHEAR)**與** scale 通道;scale 峰 >1
                                     (補償縮面)且**每個 scale 幀 scaleX==scaleY(uniform)**。
  TV2 兩軸皆阻尼振盪               : 每 twistvol bone 的 shearX **與** shearY 各自(a)首尾 0(b)繞 0 變號≥3
                                    (c)相繼極值幅度嚴格遞減(阻尼)—— 復用 G-4'/twist 判準。
  TV3 反相雙軸 shear 耦合(crux)  : 每 twistvol bone 每內部極值幀(a)shearX·shearY<0(反號)(b)夾角偏離
                                    |shearY−shearX|≥MIN_DEV —— 復用 twist `_tw3_eval`。
  TV4 identity 介面(可插 Loop)   : sample(0)/sample(dur) 各 bone identity;shear 首尾(0,0)、scale 首尾(1,1)。
  TV5 真面積(det)守恆(crux)     : 每 twistvol bone 每內部 shear 極值幀 |det(M)−1|≤TOL_DET(M=_M_spine(0,sx,sy,shx,shy));
                                    **內建負對照**:(a)無 scale(twist,s≡1)max|det−1|≥MIN_DEV_DET(不守恆);
                                    (b)squash 式**非均勻** sx·sy=1(scale 積守恆)→ det=cos(shearX−shearY),
                                    max|det−1|≥MIN_DEV_DET(scale 積守恆 ≠ 真面積守恆)。證真面積守恆須 s²=1/cos。
  TV6 端到端 + 隔離               : (a)`build_spine --shear-pivot`(真實 robot)產 twistvol 帶補償;凡有關節 pivot 的
                                    bone,pivot 殘差<TOL_FIX(**在 det≡1 的一般仿射驅動下**);內建負對照=未補償(繞件
                                    中心)大位移。(b)**uniform vs squash 非均勻**:twistvol 每 scale 幀 scaleX==scaleY,
                                    對照 squash beat 有極值幀 scaleX≠scaleY(兩守恆機制正交)。(c)**shearY 隔離**:非
                                    DUAL_AXIS_CATS beat 皆 shearY≡0。(d)**加性**:移除 twistvol 的 storyboard → 其餘
                                    beat 逐位元不變(零回歸)。

用法:
  python3 validate_twist_vol.py            # 摘要
  python3 validate_twist_vol.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import gen_animations as G   # 先 import 解循環相依(註冊 _DISPATCH/_CAT_KEYWORDS)
import spine_anim as SA
import tier_variants as TV
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_shear_pivot import _world, _M_spine
from validate_twist_gen import _shear_y, _shear_xy, _interior_shear, _tw3_eval, _has_shear_y

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,峰值 |shearX|/|shearY| 下限(head shearY 峰=10×0.7=7° → 餘裕)
MIN_DEV = 8.0       # 度,反相夾角偏離峰下限(head 首極值 10+7=17° → 充足)
MIN_SCALE = 1.005   # scale 峰下限(head 峰≈1.023;確認補償存在)
TOL_DET = 2e-3      # 真面積守恆殘差上限(實測 ≤1e-4;圓整餘裕)
MIN_DEV_DET = 0.02  # 負對照 max|det−1| 下限(head 無 scale 峰 |cos17°−1|≈0.044 → >2× 餘裕)
TOL_FIX = 0.5       # px,pivot 不動點殘差上限(同 twist/squash 系列)
MIN_NEG = 5.0       # px,TV6 負對照(未補償)位移下限
NEG_RATIO = 20.0    # 負對照/不動點 位移比下限


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/twist_vol_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    from analyze_target import analyze
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _tv_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "twistvol"]


def _scale_xy(chans):
    fr = chans.get("scale")
    return [(f["x"], f["y"]) for f in fr] if fr else []


def _det(shx, shy, sx, sy):
    """真實 Spine local M=_M_spine(0,sx,sy,shx,shy) 的行列式(rot=0:det 與 rot 無關)。"""
    m = _M_spine(0.0, sx, sy, shx, shy)
    return float(m[0, 0] * m[1, 1] - m[0, 1] * m[1, 0])


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    tv_beats = _tv_beats(anims)
    R = {}

    # ---- TV1 present + dual-axis + uniform compensating scale (crux) ----
    s1 = {"tv_beats": tv_beats, "not_finite": [], "no_bones": [], "no_shear_scale": [],
          "weak_shearx": [], "weak_sheary": [], "weak_scale": [], "nonuniform_scale": [],
          "peak_by_beat": {}}
    for tb in tv_beats:
        an = anims[tb]
        if not SA.all_finite(an):
            s1["not_finite"].append(tb)
        if not an.get("bones"):
            s1["no_bones"].append(tb)
        both = {bn: ch for bn, ch in an.get("bones", {}).items()
                if _shear_xy(ch) and _scale_xy(ch)}
        if not both:
            s1["no_shear_scale"].append(tb); continue
        shx_pk = max(max(abs(v) for v in _shear_x(ch)) for ch in both.values())
        shy_pk = max(max(abs(v) for v in _shear_y(ch)) for ch in both.values())
        sc_pk = max(max(max(x, y) for (x, y) in _scale_xy(ch)) for ch in both.values())
        s1["peak_by_beat"][tb] = {"shearX": round(shx_pk, 3), "shearY": round(shy_pk, 3),
                                  "scale": round(sc_pk, 4)}
        if shx_pk < MIN_SHEAR:
            s1["weak_shearx"].append(tb)
        if shy_pk < MIN_SHEAR:
            s1["weak_sheary"].append(tb)
        if sc_pk < MIN_SCALE:
            s1["weak_scale"].append(tb)
        for bn, ch in both.items():
            if any(abs(x - y) > 1e-9 for (x, y) in _scale_xy(ch)):
                s1["nonuniform_scale"].append("{}::{}".format(tb, bn))
    s1_pass = (bool(tv_beats) and not s1["not_finite"] and not s1["no_bones"]
               and not s1["no_shear_scale"] and not s1["weak_shearx"]
               and not s1["weak_sheary"] and not s1["weak_scale"]
               and not s1["nonuniform_scale"])
    R["TV1_present_dual_axis_uniform_scale"] = {**s1, "pass": s1_pass}

    # ---- TV2 both axes damped oscillation ----
    s2 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "detail": {}}
    for tb in tv_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            for axis, vals in (("x", _shear_x(ch)), ("y", _shear_y(ch))):
                if not vals:
                    continue
                key = "{}::{}::{}".format(tb, bn, axis)
                ends_ok = abs(vals[0]) < 1e-6 and abs(vals[-1]) < 1e-6
                nsc = _sign_changes_zero(vals)
                damp = _extrema_mags_decreasing(vals)
                s2["detail"][key] = {"n_sign_changes": nsc, "damped": damp}
                if not ends_ok:
                    s2["bad_endpoints"].append(key)
                if nsc < 3:
                    s2["few_sign_changes"].append(key)
                if not damp:
                    s2["not_damped"].append(key)
    s2_pass = (bool(s2["detail"]) and not s2["bad_endpoints"]
               and not s2["few_sign_changes"] and not s2["not_damped"])
    R["TV2_both_axes_damped"] = {**s2, "pass": s2_pass}

    # ---- TV3 counter-phase two-axis coupling (crux) ----
    s3 = {"not_counterphase": [], "weak_dev": [], "detail": {}}
    for tb in tv_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            interior = _interior_shear(ch)
            if not interior or not _has_shear_y(ch):
                continue
            key = "{}::{}".format(tb, bn)
            cp_ok, dev_ok, det = _tw3_eval(interior)
            s3["detail"][key] = det
            if not cp_ok:
                s3["not_counterphase"].append(key)
            if not dev_ok:
                s3["weak_dev"].append(key)
    s3_pass = (bool(s3["detail"]) and not s3["not_counterphase"] and not s3["weak_dev"])
    R["TV3_counterphase_coupling"] = {**s3, "pass": s3_pass}

    # ---- TV4 identity interface ----
    s4 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_noniden": []}
    for tb in tv_beats:
        an = anims[tb]
        dur = SA.duration(an)
        start = SA.sample(an, 0.0)["bones"]
        end = SA.sample(an, dur)["bones"]
        if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
            s4["bad_interface"].append(tb)
        for bn, ch in an.get("bones", {}).items():
            xy = _shear_xy(ch)
            if xy and (abs(xy[0][0]) > 1e-6 or abs(xy[0][1]) > 1e-6
                       or abs(xy[-1][0]) > 1e-6 or abs(xy[-1][1]) > 1e-6):
                s4["shear_endpoints_nonzero"].append("{}::{}".format(tb, bn))
            sc = _scale_xy(ch)
            if sc and (abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6
                       or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6):
                s4["scale_endpoints_noniden"].append("{}::{}".format(tb, bn))
    R["TV4_identity_interface"] = {**s4, "pass": (not s4["bad_interface"]
                                                 and not s4["shear_endpoints_nonzero"]
                                                 and not s4["scale_endpoints_noniden"])}

    # ---- TV5 true-area (det) conservation (crux) + built-in negatives ----
    s5 = {"fail_conserve": [], "detail": {}, "neg_noscale_maxdev": 0.0,
          "neg_squash_prod1_maxdev": 0.0}
    for tb in tv_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            sh = _shear_xy(ch); sc = _scale_xy(ch)
            if len(sh) < 3 or len(sc) < 3:
                continue
            key = "{}::{}".format(tb, bn)
            dets = []
            noscale = []
            prod1 = []
            for (shx, shy), (sx, sy) in zip(sh[1:-1], sc[1:-1]):   # 內部極值
                dets.append(_det(shx, shy, sx, sy))
                noscale.append(_det(shx, shy, 1.0, 1.0))           # 負對照(a):s≡1
                # 負對照(b):squash 式非均勻 sx·sy=1(scale 積守恆);任取 stretch=|sx| 之一致方向
                stretch = 1.2
                prod1.append(_det(shx, shy, stretch, 1.0 / stretch))
            s5["detail"][key] = {"det": [round(d, 6) for d in dets]}
            if any(abs(d - 1.0) > TOL_DET for d in dets):
                s5["fail_conserve"].append(key)
            s5["neg_noscale_maxdev"] = max(s5["neg_noscale_maxdev"],
                                           max((abs(d - 1.0) for d in noscale), default=0.0))
            s5["neg_squash_prod1_maxdev"] = max(s5["neg_squash_prod1_maxdev"],
                                                max((abs(d - 1.0) for d in prod1), default=0.0))
    s5["neg_noscale_maxdev"] = round(s5["neg_noscale_maxdev"], 5)
    s5["neg_squash_prod1_maxdev"] = round(s5["neg_squash_prod1_maxdev"], 5)
    s5_pass = (bool(s5["detail"]) and not s5["fail_conserve"]
               and s5["neg_noscale_maxdev"] >= MIN_DEV_DET
               and s5["neg_squash_prod1_maxdev"] >= MIN_DEV_DET)
    R["TV5_true_area_conservation"] = {**s5, "pass": s5_pass}

    # ---- TV6 end-to-end pivot-fixed + isolation ----
    import build_spine
    out = "/tmp/twist_vol_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    s6 = {}
    # (a) 端到端一般仿射(det≡1)pivot 不動 + 內建負對照
    a = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0}
    for tb in _tv_beats(sp_skel["animations"]):
        an = sp_skel["animations"][tb]
        for bn, ch in an.get("bones", {}).items():
            if bn not in joints or bn not in centers:
                continue
            O = np.array(centers[bn], float); P = np.array(joints[bn], float)
            ellP = P - O
            tr = ch.get("translate")
            if not tr:
                continue
            a["n_joint_bones"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"bone": bn, "beat": tb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            a["checked"].append(rec)
            if not (fix < TOL_FIX):
                a["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                a["fail_negctrl"].append(rec)
    a["pass"] = (a["n_joint_bones"] >= 1 and not a["fail_fixed"] and not a["fail_negctrl"])
    s6["a_end2end_pivot_fixed"] = a
    # (b) uniform vs squash 非均勻:twistvol scale 全 uniform;squash beat 有極值 scaleX≠scaleY
    tv_nonuniform = []
    for tb in tv_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            if any(abs(x - y) > 1e-9 for (x, y) in _scale_xy(ch)):
                tv_nonuniform.append("{}::{}".format(tb, bn))
    squash_beats = [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "squash"]
    squash_has_nonuniform = False
    for qb in squash_beats:
        for bn, ch in anims[qb].get("bones", {}).items():
            if any(abs(x - y) > 1e-6 for (x, y) in _scale_xy(ch)):
                squash_has_nonuniform = True
    s6["b_uniform_vs_squash"] = {"twistvol_nonuniform": tv_nonuniform,
                                 "squash_beats": squash_beats,
                                 "squash_has_nonuniform_scale": squash_has_nonuniform,
                                 "pass": (not tv_nonuniform and squash_has_nonuniform)}
    # (c) shearY 隔離到 DUAL_AXIS_CATS(非 twist/twistvol 的 beat 皆 shearY≡0)
    leak = []
    for nm, an in anims.items():
        if "__" in nm or G.beat_category(nm) in TV.DUAL_AXIS_CATS:
            continue
        for bn, ch in an.get("bones", {}).items():
            if _has_shear_y(ch):
                leak.append((nm, bn))
    s6["c_sheary_isolated"] = {"leaked": leak, "pass": not leak}
    # (d) 加性:移除 twistvol 的 storyboard → 其餘 beat 逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "twistvol"]}
    anims_no = G.build_animations(skel, sb_no)
    regressed = [nm for nm, an in anims_no.items()
                 if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True)]
    s6["d_additive_no_regression"] = {"regressed": regressed,
                                      "removed_beats": [b["beat"] for b in sb["beats"]
                                                        if G.beat_category(b["beat"]) == "twistvol"],
                                      "pass": not regressed}
    R["TV6_end2end_and_isolation"] = {**s6, "pass": all(v["pass"] for v in s6.values())}

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
        for k in ["TV1_present_dual_axis_uniform_scale", "TV2_both_axes_damped",
                  "TV3_counterphase_coupling", "TV4_identity_interface",
                  "TV5_true_area_conservation", "TV6_end2end_and_isolation"]:
            print("{:36s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("TV1 peaks by beat:", R["TV1_present_dual_axis_uniform_scale"]["peak_by_beat"])
        print("TV5 conserve detail:", json.dumps(R["TV5_true_area_conservation"]["detail"], ensure_ascii=False))
        print("TV5 neg maxdev  noscale={}  squash_prod1={}".format(
            R["TV5_true_area_conservation"]["neg_noscale_maxdev"],
            R["TV5_true_area_conservation"]["neg_squash_prod1_maxdev"]))
        print("TV6a pivot-fixed (fixed/negctrl px):")
        for rec in R["TV6_end2end_and_isolation"]["a_end2end_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
