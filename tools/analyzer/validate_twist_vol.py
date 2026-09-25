#!/usr/bin/env python3
"""candidate G-4''''''-vol 自我驗收閘 — 生成器產出**體積守恆扭轉**(反相雙軸 shear + 均勻面積補償
scale ⇒ **完整局部仿射行列式 det≡1**)端到端(純 CPU)。

一路留到現在的 honest boundary(twist G-4''''''/tier/count 一直明列):反相雙軸 shear 使
**完整** Spine local 仿射 det = scaleX·scaleY·cos(shearX−shearY) 在 shearX−shearY=(1+φ)·shearX≠0
時 <1 → **擰轉使面積縮**(至今所有產 shear 的節拍——wobble 純 shearX、squash shearX+體積守恆非均勻
scale、twist 反相雙軸——沒有一個令**完整** det≡1;squash 只令 scale 通道自身 scaleX·scaleY≡1,完整
det 仍=cos(shearX))。本閘(G-4''''''-vol)驗證最後一段**已接上**:`gen_twist_vol`(體積守恆扭轉)在
反相雙軸 shear 上額外產一支**均勻**(isotropic,sx=sy) scale s=1/√cos(shearX−shearY) 抵消 shear 的
cos 因子 → **完整仿射 det≡1**(擰而不變面積)—— **產線第一個令完整局部仿射行列式守恆** 的節拍。
`build_spine --shear-pivot`(include_shear 隱含 include_scale)端到端把 rotate/scale/shearX/shearY 一起
繞關節 pivot 補償 → 件做**用滿兩條 shear 軸且面積守恆**的一般仿射而 pivot 精確不動。

真值/fixture 與 (E/H/I/J/G-4'/G-4''''/G-4'''''') 一致:從**先驗庫**(slot_bigwin,新增 voltwist beat)
經 `analyze_target` → **真實 build_spine robot 骨架** → `build_animations` 端到端量。主秀運動無唯一
正解(PROPOSAL 手感),閘驗**客觀結構簽章(兩軸阻尼振盪 + 反相 + 完整 det 守恆 + 均勻補償)+ 端到端
不動點**,非美感;負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  VV1 present + dual-channel(crux) : voltwist beat 直出、finite、有 bone,且 ≥1 bone **同時**帶反相雙軸
                                     `shear`(shearX 峰≥MIN_SHEAR **且** shearY 峰≥MIN_SHEAR)**與** `scale`
                                     通道 → **產線第一次產出「反相雙軸 shear + 面積補償 scale」耦合**。
  VV2 兩軸阻尼振盪 + 反相          : 每個 voltwist bone 的 shearX **與** shearY 各自(復用 twist 判準):
                                     (a)首尾 0;(b)繞 0 變號≥3;(c)相繼極值幅度嚴格遞減(阻尼);且每個
                                     內部極值 shearX·shearY<0(反相)—— 證仍是「同一種雙軸 shear 扭轉」。
  VV3 完整仿射 det 守恆(crux)     : 每個 voltwist bone 的**每幀** |scaleX·scaleY·cos(shearX−shearY) − 1|
                                     ≤ TOL_DET(完整局部仿射行列式≡1);端點 det=1。**這是新不變量**——
                                     負對照(純 twist 無補償 scale)det=cos(shx−shy)<1 → 破。
  VV4 均勻(isotropic)補償 scale  : 每幀 |scaleX−scaleY|≤TOL_UNI(等向,非 squash 的非均勻);內部極值
                                     scale >1(補償**放大**面積、恰抵 shear 損失)、端點 (1,1)。**均勻=與
                                     squash(sx≠sy)的關鍵區別**。
  VV5 identity 介面(可插 Loop)   : sample(0)/sample(dur) 各 bone identity,且 shear 首尾 (0,0) + scale 首尾 (1,1)。
  VV6 端到端一般仿射 pivot 不動    : `build_spine --shear-pivot`(真實 robot)產出 voltwist 帶補償;凡有關節
                                     pivot 的 bone,pivot 殘差 < TOL_FIX(**在 shearY≠0 + 補償 scale 驅動下**);
                                     內建負對照 = 未補償(繞件中心)大位移 → 證補償把「雙軸 shear+面積補償
                                     scale」也錨在 pivot。
  VV7 負對照/隔離                 : (a)**純 twist 守衛**(gate credibility):真 twist beat(shearX/Y 同 voltwist
                                     但無補償 scale,視 sx=sy=1)→ VV3 完整 det 守恆 FALSE(det=cos(shx−shy)<1)
                                     —— 證閘測的是「完整 det≡1」非「有 scale 即可」;(b)**squash 守衛**:合成非均勻
                                     scaleX·scaleY≡1 但 shearY≡0(squash 樣)→ 完整 det=cos(shearX)≠1(VV3 FALSE)
                                     **且**非均勻(VV4 均勻 FALSE)—— 證「完整 det≡1」≠ squash 的「scale 自身守恆」、
                                     且均勻性把兩者分開;(c)**shearY 隔離**:非 SHEARY_CATS 的 beat 皆 shearY≡0
                                     (twist/voltwist 獨佔第二條 shear 軸);(d)**加性**:移除 voltwist 的 storyboard
                                     → 其餘 beat 逐位元不變(零回歸)。

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
import tier_variants as TV
# 復用 twist 的雙軸 shear 讀取與反相/阻尼判準,確保與 twist-gen / twist-tier / twist-count 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_twist_gen import _shear_y, _shear_xy, _interior_shear, _tw3_eval, _has_shear_y
from validate_shear_pivot import _world   # 真實 Spine local(含雙軸 shear + scale)世界座標求值

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,voltwist 峰值 |shearX| / |shearY| 下限(shearY 峰=0.7×shearX 峰,head 最小軸 7° → 餘裕)
TOL_DET = 1e-3      # 完整仿射 |det − 1| 上限(實測 <5e-6 → 巨大餘裕);純 twist 峰 det=cos(27.2°)=0.889 → 破 0.11
TOL_UNI = 1e-3      # scale 均勻 |scaleX−scaleY| 上限(voltwist sx==sy 恰 0 → 巨大餘裕)
MIN_COMP = 0.003    # 內部極值補償 scale 相對 identity 的最小放大量(head 末極值 span 2.1° → s−1≈3.4e-4;首極值 body span 23.8° → s−1≈0.045;取峰 > MIN_COMP)
TOL_FIX = 0.5       # px,pivot 不動點殘差上限(同 G-4/G-4'/G-4'''''')
MIN_NEG = 5.0       # px,VV6 負對照(未補償)位移下限
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


def _voltwist_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "voltwist"]


def _scale_xy(chans):
    """bone channels → [(scaleX, scaleY)] 關鍵幀序列(無 scale 通道回 [])。"""
    fr = chans.get("scale")
    return [(f["x"], f["y"]) for f in fr] if fr else []


def _full_det(shx, shy, sx, sy):
    """完整 Spine local 仿射行列式 det(M) = scaleX·scaleY·cos(shearX−shearY)(度)。
    見 validate_shear_pivot.transform_matrix_full:兩基底夾角=90+shearY−shearX → det=sx·sy·cos(shx−shy)。"""
    return sx * sy * math.cos(math.radians(shx - shy))


def _combined(chans):
    """把一 bone 的 shear 與 scale 通道對齊成 [(shx,shy,sx,sy)](同 gen 時同 τ 逐幀對齊)。
    無 scale 通道(如純 twist)→ 視 sx=sy=1(便於對純 twist 施同一守恆判準做負對照)。"""
    sh = _shear_xy(chans)
    sc = _scale_xy(chans)
    if not sh:
        return []
    if sc and len(sc) == len(sh):
        return [(shx, shy, sx, sy) for (shx, shy), (sx, sy) in zip(sh, sc)]
    return [(shx, shy, 1.0, 1.0) for (shx, shy) in sh]


def _vv_eval(frames):
    """給對齊幀 [(shx,shy,sx,sy)] → (det_ok, uniform_ok, comp_ok, detail)。
    純函式 → 可對真實 voltwist 與合成負對照(純 twist / squash 樣)施同一判準(閘可信)。
      det_ok    : 每幀 |完整 det − 1| ≤ TOL_DET(完整仿射行列式守恆)。
      uniform_ok: 每幀 |scaleX−scaleY| ≤ TOL_UNI(均勻/等向補償,非 squash 非均勻)。
      comp_ok   : 內部極值補償 scale 峰 > 1+MIN_COMP(真的有面積補償,非全 1)。"""
    if not frames:
        return False, False, False, {"det": [], "aniso": [], "scale": []}
    dets = [_full_det(*f) for f in frames]
    aniso = [abs(sx - sy) for (shx, shy, sx, sy) in frames]
    interior = frames[1:-1] if len(frames) >= 3 else []
    comp_peak = max((0.5 * (sx + sy) for (shx, shy, sx, sy) in interior), default=1.0)
    det_ok = all(abs(d - 1.0) <= TOL_DET for d in dets)
    uniform_ok = max(aniso) <= TOL_UNI
    comp_ok = comp_peak > 1.0 + MIN_COMP
    detail = {"det": [round(d, 6) for d in dets], "aniso": [round(a, 5) for a in aniso],
              "scale": [round(0.5 * (sx + sy), 5) for (shx, shy, sx, sy) in frames]}
    return det_ok, uniform_ok, comp_ok, detail


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    vt_beats = _voltwist_beats(anims)
    R = {}

    # ---- VV1 present + dual-channel emitted (crux) ----
    s1 = {"voltwist_beats": vt_beats, "not_finite": [], "no_bones": [], "no_dual": [],
          "weak_shearx": [], "weak_sheary": [], "no_scale": [], "peak_by_beat": {}}
    for vb in vt_beats:
        an = anims[vb]
        if not SA.all_finite(an):
            s1["not_finite"].append(vb)
        if not an.get("bones"):
            s1["no_bones"].append(vb)
        dual = {bn: ch for bn, ch in an.get("bones", {}).items()
                if _shear_xy(ch) and _scale_xy(ch)}
        if not dual:
            s1["no_dual"].append(vb); continue
        shx_pk = max(max(abs(v) for v in _shear_x(ch)) for ch in dual.values())
        shy_pk = max(max(abs(v) for v in _shear_y(ch)) for ch in dual.values())
        s1["peak_by_beat"][vb] = {"shearX": round(shx_pk, 3), "shearY": round(shy_pk, 3)}
        if shx_pk < MIN_SHEAR:
            s1["weak_shearx"].append(vb)
        if shy_pk < MIN_SHEAR:
            s1["weak_sheary"].append(vb)
    s1_pass = (bool(vt_beats) and not s1["not_finite"] and not s1["no_bones"]
               and not s1["no_dual"] and not s1["weak_shearx"] and not s1["weak_sheary"])
    R["VV1_present_dual_channel"] = {**s1, "pass": s1_pass}

    # ---- VV2 both axes damped oscillation + counter-phase (reuse twist criteria) ----
    s2 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [],
          "not_counterphase": [], "detail": {}}
    for vb in vt_beats:
        for bn, ch in anims[vb].get("bones", {}).items():
            for axis, vals in (("x", _shear_x(ch)), ("y", _shear_y(ch))):
                if not vals:
                    continue
                key = "{}::{}::{}".format(vb, bn, axis)
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
            interior = _interior_shear(ch)
            if interior and _has_shear_y(ch):
                cp_ok, _dev_ok, _det = _tw3_eval(interior)
                if not cp_ok:
                    s2["not_counterphase"].append("{}::{}".format(vb, bn))
    s2_pass = (bool(s2["detail"]) and not s2["bad_endpoints"]
               and not s2["few_sign_changes"] and not s2["not_damped"]
               and not s2["not_counterphase"])
    R["VV2_dual_axis_damped_counterphase"] = {**s2, "pass": s2_pass}

    # ---- VV3/VV4 full-determinant conservation + isotropic compensation (crux) ----
    s3 = {"bad_det": [], "detail": {}}
    s4 = {"non_uniform": [], "no_compensation": [], "bad_scale_endpoints": [], "detail": {}}
    for vb in vt_beats:
        for bn, ch in anims[vb].get("bones", {}).items():
            frames = _combined(ch)
            if not frames or not _scale_xy(ch):
                continue
            key = "{}::{}".format(vb, bn)
            det_ok, uni_ok, comp_ok, det = _vv_eval(frames)
            s3["detail"][key] = det["det"]
            s4["detail"][key] = {"aniso": det["aniso"], "scale": det["scale"]}
            if not det_ok:
                s3["bad_det"].append(key)
            if not uni_ok:
                s4["non_uniform"].append(key)
            if not comp_ok:
                s4["no_compensation"].append(key)
            sc = _scale_xy(ch)
            if (abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6
                    or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6):
                s4["bad_scale_endpoints"].append(key)
    R["VV3_full_determinant_conserved"] = {**s3, "pass": (bool(s3["detail"]) and not s3["bad_det"])}
    R["VV4_isotropic_compensation"] = {**s4, "pass": (bool(s4["detail"]) and not s4["non_uniform"]
                                                      and not s4["no_compensation"]
                                                      and not s4["bad_scale_endpoints"])}

    # ---- VV5 identity interface ----
    s5 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for vb in vt_beats:
        an = anims[vb]
        dur = SA.duration(an)
        start = SA.sample(an, 0.0)["bones"]
        end = SA.sample(an, dur)["bones"]
        if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
            s5["bad_interface"].append(vb)
        for bn, ch in an.get("bones", {}).items():
            xy = _shear_xy(ch)
            if xy and (abs(xy[0][0]) > 1e-6 or abs(xy[0][1]) > 1e-6
                       or abs(xy[-1][0]) > 1e-6 or abs(xy[-1][1]) > 1e-6):
                s5["shear_endpoints_nonzero"].append("{}::{}".format(vb, bn))
            sc = _scale_xy(ch)
            if sc and (abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6
                       or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6):
                s5["scale_endpoints_nonident"].append("{}::{}".format(vb, bn))
    R["VV5_identity_interface"] = {**s5, "pass": (not s5["bad_interface"]
                                                  and not s5["shear_endpoints_nonzero"]
                                                  and not s5["scale_endpoints_nonident"])}

    # ---- VV6 end-to-end general-affine pivot-fixed via build_spine --shear-pivot ----
    import build_spine
    out = "/tmp/twist_vol_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    s6 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0}
    for vb in _voltwist_beats(sp_skel["animations"]):
        an = sp_skel["animations"][vb]
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
            # 內建負對照:未補償(繞件中心)—— 同雙軸 shear + 補償 scale 但無 translate
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"bone": bn, "beat": vb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            s6["checked"].append(rec)
            if not (fix < TOL_FIX):
                s6["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                s6["fail_negctrl"].append(rec)
    s6_pass = (s6["n_joint_bones"] >= 1 and not s6["fail_fixed"] and not s6["fail_negctrl"])
    R["VV6_end2end_affine_pivot_fixed"] = {**s6, "pass": s6_pass}

    # ---- VV7 negative controls / isolation ----
    s7 = {}
    # (a) 純 twist 守衛(gate credibility):shearX/Y 同 voltwist 但無補償 scale(sx=sy=1)→ 完整 det=cos(shx−shy)<1
    #     取真實 twist beat 的 shear、視 sx=sy=1 → 完整 det 守恆應 FALSE(證閘測「完整 det≡1」非「有 scale 即可」)。
    twist_beats = [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "twist"]
    plain_break = []
    plain_checked = 0
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            frames = _combined(ch)  # 純 twist 無 scale → sx=sy=1
            if not frames or _scale_xy(ch):
                continue
            plain_checked += 1
            det_ok, _u, _c, _d = _vv_eval(frames)
            if det_ok:                      # 純 twist 竟守恆 → 閘失去鑑別力
                plain_break.append("{}::{}".format(tb, bn))
    s7["a_plain_twist_guard"] = {"checked": plain_checked, "conserved_wrongly": plain_break,
                                 "pass": (plain_checked >= 1 and not plain_break)}
    # (b) squash 守衛:合成非均勻 scaleX·scaleY≡1 但 shearY≡0(squash 樣)→ 完整 det=cos(shearX)≠1(守恆 FALSE)
    #     且非均勻(均勻 FALSE)。證「完整 det≡1」≠ squash 的「scale 通道自身守恆」、且均勻性把兩者分開。
    squash_like = [(0.0, 0.0, 1.0, 1.0), (14.0, 0.0, 1.14, round(1.0 / 1.14, 6)),
                   (-7.0, 0.0, 1.07, round(1.0 / 1.07, 6)), (3.5, 0.0, 1.035, round(1.0 / 1.035, 6)),
                   (0.0, 0.0, 1.0, 1.0)]
    det_sq, uni_sq, _c_sq, _d_sq = _vv_eval(squash_like)
    s7["b_squash_guard"] = {"full_det_ok": det_sq, "uniform_ok": uni_sq,
                            "pass": (not det_sq) and (not uni_sq)}
    # (c) shearY 隔離:非 SHEARY_CATS 的 beat 皆 shearY≡0(twist/voltwist 獨佔第二條 shear 軸)
    leak = []
    for nm, an in anims.items():
        if "__" in nm or G.beat_category(nm) in TV.SHEARY_CATS:
            continue
        for bn, ch in an.get("bones", {}).items():
            if _has_shear_y(ch):
                leak.append((nm, bn))
    s7["c_sheary_isolated"] = {"leaked": leak, "pass": not leak}
    # (d) 加性:移除 voltwist 的 storyboard → 其餘 beat 逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "voltwist"]}
    anims_no = G.build_animations(skel, sb_no)
    regressed = []
    for nm, an in anims_no.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    s7["d_additive_no_regression"] = {"regressed": regressed,
                                      "removed_beats": [b["beat"] for b in sb["beats"]
                                                        if G.beat_category(b["beat"]) == "voltwist"],
                                      "pass": not regressed}
    R["VV7_neg_control"] = {**s7, "pass": all(v["pass"] for v in s7.values())}

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
        for k in ["VV1_present_dual_channel", "VV2_dual_axis_damped_counterphase",
                  "VV3_full_determinant_conserved", "VV4_isotropic_compensation",
                  "VV5_identity_interface", "VV6_end2end_affine_pivot_fixed", "VV7_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("VV1 peaks by beat:", R["VV1_present_dual_channel"]["peak_by_beat"])
        print("VV3 det detail:", json.dumps(R["VV3_full_determinant_conserved"]["detail"], ensure_ascii=False))
        print("VV6 pivot-fixed (fixed/negctrl px):")
        for rec in R["VV6_end2end_affine_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("VV7(a) plain-twist guard:", R["VV7_neg_control"]["a_plain_twist_guard"])
        print("VV7(b) squash guard:", R["VV7_neg_control"]["b_squash_guard"])
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
