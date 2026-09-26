#!/usr/bin/env python3
"""candidate G-4''''''-vol 自我驗收閘 — 生成器產出**體積守恆反相雙軸 shear(完整 det≡1)**端到端(純 CPU)。

補上 twist(G-4'''''')/(G-4''''''-tier)/(G-4''''''-count)一路留到現在的 honest boundary:反相雙軸 shear
**會改變面積**。真實 Spine local 一般仿射 M(見 `pivot_rotation.transform_matrix_full`)的行列式
    det(M) = sx·sy·cos(shearY − shearX)
    (推導:a·d − b·c = sx·sy·[cos(rot+shx)·sin(rot+90+shy) − cos(rot+90+shy)·sin(rot+shx)]
                     = sx·sy·sin(90 + shy − shx) = sx·sy·cos(shy − shx),與 rot 無關)
純 twist(sx=sy=1、shearY=−φ·shearX)⇒ det = cos((1+φ)·shearX) < 1 → **擰轉時件面積縮小**。
本 beat `gen_twist_vol` 補上耦合**均勻** scale s=1/√(cos(shearY−shearX)) 使 det = s²·cos(shy−shx) ≡ 1 ——
擰而不變面積(像擰乾毛巾),rotate/scale/shearX/shearY **四通道**同時被生成器驅動且面積逐關鍵幀嚴格守恆。

**crux(與 squash 的體積守恆對立)**:squash 守的是 **scale 子塊** scaleX·scaleY≡1(但其 shearX≠0 →
完整 det=cos(shearX)≠1,不守完整矩陣);twist_vol 守的是**完整 Spine local 矩陣** det(M)≡1,其 scale
為**均勻** sx=sy=s>1 → scaleX·scaleY=s²>1(與 squash 的 ≡1 恰相反)。兩者在「守 scale 子塊 vs 守完整
矩陣」上正交對立 —— 這是 twist_vol 獨有、與 squash 乾淨分離的鑑別點(負對照 c)。

真值/fixture 與 (twist 系列)一致:從**先驗庫**(slot_bigwin,新增 twist_vol beat)經 `analyze_target`
→ **真實 build_spine robot 骨架** → `build_animations` 端到端量。主秀運動無唯一正解(PROPOSAL 手感),
閘驗**客觀結構簽章(兩軸阻尼振盪 + 反相雙軸耦合 + 完整矩陣體積守恆)+ 端到端不動點**,非美感;負對照
證鑑別力(閘可信)。

AC(客觀、可量測):
  VT1 present + dual-axis + scale(crux setup): twist_vol beat 直出、finite、有 bone,且 ≥1 bone 同時帶
                                    shear(shearX 峰 ≥ MIN_SHEAR、shearY 峰 ≥ MIN_SHEAR)**與** scale 通道
                                    (峰 |s−1| ≥ MIN_SCALE)—— 與純 twist(無 scale 通道)分離。
  VT2 兩軸皆阻尼振盪              : 每 twist_vol bone 的 shearX 與 shearY 各自(a)首尾 0;(b)繞 0 變號 ≥3;
                                   (c)相繼極值幅度嚴格遞減 —— 復用 twist/wobble 判準。
  VT3 反相雙軸 shear 耦合(crux) : 每 twist_vol bone 每個內部極值幀 shearX·shearY<0 且夾角偏離 ≥ MIN_DEV
                                   (復用 twist `_tw3_eval`;反相雙軸仍成立)。
  VT4 完整矩陣體積守恆(crux)    : 每 twist_vol bone 每個內部 shear 極值幀:(a)det=s²·cos(shy−shx)≈1
                                   (|det−1|≤TOL_DET);(b)scale **均勻**(|sx−sy|≤TOL);(c)scale 確實修正
                                   (峰 scaleX·scaleY>1+PROD_MARGIN;且對照 純-twist det=cos(shy−shx) 在峰處
                                   縮小 ≥ SHRINK_MIN → 證 scale 在做真實功)。
  VT5 identity 介面 + 端到端 pivot 不動 : sample(0)/sample(dur) identity 且 shear 首尾(0,0)/scale 首尾(1,1);
                                   `build_spine --shear-pivot`(真實 robot)產出 twist_vol 帶補償,凡有關節
                                   pivot 的 bone pivot 殘差 < TOL_FIX(**在 scale+雙軸 shear 同時驅動下**);
                                   內建負對照=未補償(繞件中心)大位移。
  VT6 負對照 / 隔離              : (a)**純-twist 守衛**:scale≡1(無修正)→ 完整體積守恆 FALSE(det=cos<1);
                                   (b)**定值-scale 守衛**:常數 s(非 1/√cos)→ det≠1 → 守恆 FALSE(證測的是
                                   特定 s=1/√cos 關係,非「有 scale 即可」);(c)**squash-式守衛(crux)**:
                                   scaleX·scaleY≡1 非均勻(squash 樣)→ 完整 det=cos(shy−shx)≠1 → 守恆 FALSE
                                   (證守 scale 子塊 ≠ 守完整矩陣);(d)**正控**:正確 s=1/√cos → 守恆 TRUE;
                                   (e)shearY 隔離:非 {twist,twist_vol} beat 皆 shearY≡0;(f)加性:移除 twist_vol
                                   的 storyboard → 其餘 beat 逐位元不變(零回歸)。

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
# 復用 twist / shear-gen 判準,確保與既有 shear 系列閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_shear_pivot import _world
from validate_twist_gen import (_shear_y, _shear_xy, _interior_shear, _tw3_eval,
                                _has_shear_y, _is_ident)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TOL = 1e-4
MIN_SHEAR = 5.0      # 度,twist_vol 峰值 |shearX| / |shearY| 下限(同 twist_gen)
MIN_DEV = 8.0        # 度,反相夾角偏離峰下限(同 twist_gen)
MIN_SCALE = 0.01     # scale 峰 |s−1| 下限(head 最小軸峰 s≈1.0225 → 餘裕;證 scale 通道非零)
TOL_DET = 2e-3       # 完整 det 守恆殘差上限(scale 捨入到 4 位 → det 誤差 ~1e-4,餘裕充足)
PROD_MARGIN = 0.01   # scaleX·scaleY 峰須 >1+此值(均勻修正 → s²>1;與 squash 的 ≡1 分離)
SHRINK_MIN = 0.02    # 純-twist det 在峰處相對 1 的縮小量下限(證 scale 在做真實功;head 峰 0.044)
TOL_FIX = 0.5        # px,pivot 不動點殘差上限(同 twist 系列)
MIN_NEG = 5.0        # px,VT5 負對照(未補償)位移下限
NEG_RATIO = 20.0     # 負對照/不動點 位移比下限


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


def _tv_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "twist_vol"]


def _scale_xy(chans):
    """bone channels → [(scaleX, scaleY)] 關鍵幀序列(無 scale 通道回 [])。"""
    fr = chans.get("scale")
    return [(f["x"], f["y"]) for f in fr] if fr else []


def _interior_scale(chans):
    sc = _scale_xy(chans)
    return sc[1:-1] if len(sc) >= 3 else []


def _det_local(shx, shy, sx, sy):
    """完整 Spine local 一般仿射行列式 det(M)=sx·sy·cos(shearY−shearX)(度)。"""
    return sx * sy * math.cos(math.radians(shy - shx))


def _vt4_eval(quad):
    """給一組內部極值 [(shx,shy,sx,sy)] → (conserved, uniform, dets, prods, shrinks)。
    純函式 → 可對真實 twist_vol 與合成負對照施同一判準(閘可信)。
      conserved = 每幀 |det−1|≤TOL_DET;uniform = 每幀 |sx−sy|≤TOL;
      shrinks = 每幀純-twist(sx=sy=1)相對 1 的縮小量 1−cos(shy−shx)。"""
    if not quad:
        return False, False, [], [], []
    dets = [_det_local(shx, shy, sx, sy) for (shx, shy, sx, sy) in quad]
    prods = [sx * sy for (_, _, sx, sy) in quad]
    shrinks = [1.0 - math.cos(math.radians(shy - shx)) for (shx, shy, _, _) in quad]
    conserved = all(abs(d - 1.0) <= TOL_DET for d in dets)
    uniform = all(abs(sx - sy) <= TOL for (_, _, sx, sy) in quad)
    return conserved, uniform, dets, prods, shrinks


def _interior_quad(ch):
    """twist_vol bone → 內部極值 [(shx,shy,sx,sy)](shear 與 scale 極值 τ 同點,逐 index 對齊)。"""
    ish = _interior_shear(ch)          # [(shx,shy)]
    isc = _interior_scale(ch)          # [(sx,sy)]
    n = min(len(ish), len(isc))
    return [(ish[i][0], ish[i][1], isc[i][0], isc[i][1]) for i in range(n)]


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    tv_beats = _tv_beats(anims)
    R = {}

    # ---- VT1 present + dual-axis shear + scale channel (crux setup) ----
    s1 = {"tv_beats": tv_beats, "not_finite": [], "no_bones": [], "no_shear": [],
          "no_scale": [], "weak_shearx": [], "weak_sheary": [], "weak_scale": [],
          "peak_by_beat": {}}
    for tb in tv_beats:
        an = anims[tb]
        if not SA.all_finite(an):
            s1["not_finite"].append(tb)
        if not an.get("bones"):
            s1["no_bones"].append(tb)
        sheared = {bn: ch for bn, ch in an.get("bones", {}).items()
                   if _shear_xy(ch) and _scale_xy(ch)}
        if not sheared:
            s1["no_shear"].append(tb); continue
        shx_pk = max(max(abs(v) for v in _shear_x(ch)) for ch in sheared.values())
        shy_pk = max(max(abs(v) for v in _shear_y(ch)) for ch in sheared.values())
        sc_pk = max(max(abs(sx - 1.0) for (sx, _) in _scale_xy(ch)) for ch in sheared.values())
        s1["peak_by_beat"][tb] = {"shearX": round(shx_pk, 3), "shearY": round(shy_pk, 3),
                                  "scale_dev": round(sc_pk, 4)}
        if shx_pk < MIN_SHEAR:
            s1["weak_shearx"].append(tb)
        if shy_pk < MIN_SHEAR:
            s1["weak_sheary"].append(tb)
        if sc_pk < MIN_SCALE:
            s1["weak_scale"].append(tb)
    s1_pass = (bool(tv_beats) and not s1["not_finite"] and not s1["no_bones"]
               and not s1["no_shear"] and not s1["weak_shearx"] and not s1["weak_sheary"]
               and not s1["weak_scale"])
    R["VT1_present_dual_axis_scale"] = {**s1, "pass": s1_pass}

    # ---- VT2 both axes damped oscillation ----
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
    R["VT2_both_axes_damped"] = {**s2, "pass": s2_pass}

    # ---- VT3 counter-phase two-axis coupling (crux) ----
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
    R["VT3_counterphase_coupling"] = {**s3, "pass": s3_pass}

    # ---- VT4 full-matrix volume conservation (crux) ----
    s4 = {"not_conserved": [], "not_uniform": [], "no_prod_margin": [], "weak_shrink": [],
          "detail": {}}
    for tb in tv_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            quad = _interior_quad(ch)
            if not quad or not _has_shear_y(ch):
                continue
            key = "{}::{}".format(tb, bn)
            conserved, uniform, dets, prods, shrinks = _vt4_eval(quad)
            s4["detail"][key] = {"det_max_err": round(max(abs(d - 1.0) for d in dets), 6),
                                 "prod_peak": round(max(prods), 5),
                                 "shrink_peak": round(max(shrinks), 5),
                                 "uniform_max_gap": round(max(abs(sx - sy) for (_, _, sx, sy) in quad), 8)}
            if not conserved:
                s4["not_conserved"].append(key)
            if not uniform:
                s4["not_uniform"].append(key)
            if not (max(prods) > 1.0 + PROD_MARGIN):
                s4["no_prod_margin"].append(key)
            if not (max(shrinks) >= SHRINK_MIN):
                s4["weak_shrink"].append(key)
    s4_pass = (bool(s4["detail"]) and not s4["not_conserved"] and not s4["not_uniform"]
               and not s4["no_prod_margin"] and not s4["weak_shrink"])
    R["VT4_volume_conservation"] = {**s4, "pass": s4_pass}

    # ---- VT5 identity interface + end-to-end pivot fixed ----
    s5i = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for tb in tv_beats:
        an = anims[tb]
        dur = SA.duration(an)
        start = SA.sample(an, 0.0)["bones"]
        end = SA.sample(an, dur)["bones"]
        if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
            s5i["bad_interface"].append(tb)
        for bn, ch in an.get("bones", {}).items():
            xy = _shear_xy(ch)
            if xy and (abs(xy[0][0]) > 1e-6 or abs(xy[0][1]) > 1e-6
                       or abs(xy[-1][0]) > 1e-6 or abs(xy[-1][1]) > 1e-6):
                s5i["shear_endpoints_nonzero"].append("{}::{}".format(tb, bn))
            sc = _scale_xy(ch)
            if sc and (abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6
                       or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6):
                s5i["scale_endpoints_nonident"].append("{}::{}".format(tb, bn))

    import build_spine
    out = "/tmp/twist_vol_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    s5 = {**s5i, "checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0}
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
            s5["n_joint_bones"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"bone": bn, "beat": tb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            s5["checked"].append(rec)
            if not (fix < TOL_FIX):
                s5["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                s5["fail_negctrl"].append(rec)
    s5_pass = (not s5["bad_interface"] and not s5["shear_endpoints_nonzero"]
               and not s5["scale_endpoints_nonident"] and s5["n_joint_bones"] >= 1
               and not s5["fail_fixed"] and not s5["fail_negctrl"])
    R["VT5_interface_end2end_pivot_fixed"] = {**s5, "pass": s5_pass}

    # ---- VT6 negative controls / isolation ----
    s6 = {}
    # 合成 body-like 反相雙軸內部極值(A=14, r=0.5, φ=0.7, nosc=4)
    A, r, phi = 14.0, 0.5, 0.7
    exs = [((-1.0) ** i) * A * (r ** i) for i in range(4)]
    eys = [-phi * e for e in exs]
    correct_s = [1.0 / math.sqrt(math.cos(math.radians(ey - ex))) for ex, ey in zip(exs, eys)]
    # (a) 純-twist 守衛:scale≡1 → 完整體積守恆 FALSE(det=cos<1)
    quad_pure = [(ex, ey, 1.0, 1.0) for ex, ey in zip(exs, eys)]
    cons_pure, _, dets_pure, _, _ = _vt4_eval(quad_pure)
    s6["a_pure_twist_guard"] = {"conserved": cons_pure, "det_min": round(min(dets_pure), 5),
                                "pass": not cons_pure}
    # (b) 定值-scale 守衛:常數 s=1.05(非 1/√cos)→ det≠1 → FALSE
    quad_const = [(ex, ey, 1.05, 1.05) for ex, ey in zip(exs, eys)]
    cons_const, _, dets_const, _, _ = _vt4_eval(quad_const)
    s6["b_const_scale_guard"] = {"conserved": cons_const,
                                 "det_max_err": round(max(abs(d - 1.0) for d in dets_const), 5),
                                 "pass": not cons_const}
    # (c) squash-式守衛(crux):scaleX·scaleY≡1 非均勻 → 完整 det=cos(shy−shx)≠1 → FALSE
    q = 0.14
    quad_sq = [(ex, ey, 1.0 + q, 1.0 / (1.0 + q)) for ex, ey in zip(exs, eys)]
    cons_sq, unif_sq, dets_sq, prods_sq, _ = _vt4_eval(quad_sq)
    s6["c_squash_style_guard"] = {"conserved_full": cons_sq, "uniform": unif_sq,
                                  "prod_peak": round(max(prods_sq), 5),
                                  "det_min": round(min(dets_sq), 5),
                                  # crux:squash 守 scale 子塊(prod≈1)卻不守完整矩陣(det≠1);且非均勻
                                  "pass": (not cons_sq) and (not unif_sq) and abs(max(prods_sq) - 1.0) < 1e-6}
    # (d) 正控:正確 s=1/√cos → 守恆 TRUE 且均勻
    quad_ok = [(ex, ey, s, s) for ex, ey, s in zip(exs, eys, correct_s)]
    cons_ok, unif_ok, _, prods_ok, _ = _vt4_eval(quad_ok)
    s6["d_correct_positive_ctrl"] = {"conserved": cons_ok, "uniform": unif_ok,
                                     "prod_peak": round(max(prods_ok), 5),
                                     "pass": cons_ok and unif_ok and max(prods_ok) > 1.0 + PROD_MARGIN}
    # (e) shearY 隔離:非 {twist,twist_vol} beat 皆 shearY≡0
    sheary_cats = {"twist", "twist_vol"}
    leak = []
    for nm, an in anims.items():
        if "__" in nm or G.beat_category(nm) in sheary_cats:
            continue
        for bn, ch in an.get("bones", {}).items():
            if _has_shear_y(ch):
                leak.append((nm, bn))
    s6["e_sheary_isolated"] = {"leaked": leak, "pass": not leak}
    # (f) 加性:移除 twist_vol 的 storyboard → 其餘 beat 逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "twist_vol"]}
    anims_no = G.build_animations(skel, sb_no)
    regressed = []
    for nm, an in anims_no.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    s6["f_additive_no_regression"] = {"regressed": regressed,
                                      "removed_beats": [b["beat"] for b in sb["beats"]
                                                        if G.beat_category(b["beat"]) == "twist_vol"],
                                      "pass": not regressed}
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
        for k in ["VT1_present_dual_axis_scale", "VT2_both_axes_damped",
                  "VT3_counterphase_coupling", "VT4_volume_conservation",
                  "VT5_interface_end2end_pivot_fixed", "VT6_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("VT1 peaks by beat:", R["VT1_present_dual_axis_scale"]["peak_by_beat"])
        print("VT4 detail:", json.dumps(R["VT4_volume_conservation"]["detail"], ensure_ascii=False))
        print("VT5 pivot-fixed (fixed/negctrl px):")
        for rec in R["VT5_interface_end2end_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("VT6 detail:", json.dumps(R["VT6_neg_control"], ensure_ascii=False))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
