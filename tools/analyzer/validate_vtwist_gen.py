#!/usr/bin/env python3
"""candidate G-4''''''-vol 自我驗收閘 — 生成器產出**體積守恆扭轉**(反相雙軸 shear + 耦合 uniform scale
使 full-matrix det≡1)端到端(純 CPU)。

twist(G-4'''''')的 honest boundary(一直留著):反相雙軸 shear(shearY=−φ·shearX)本身
`det = sx·sy·cos(shearX−shearY)`,在 sx=sy=1(純雙軸 shear)時 = cos(Δ)(Δ=shearX−shearY=(1+φ)·shearX)
**< 1** → 擰轉會**變面積**(物理上合理,如擰毛巾投影縮小;峰 Δ≈27° → cos≈0.889 → 掉 ~11%)。本閘
(G-4''''''-vol)驗證:生成器 `gen_vtwist` 在反相雙軸 shear 上加一層**耦合 uniform scale** s=1/√cos(Δ) 使
`sx·sy = s² = 1/cos(Δ)` ⇒ **整個 local 仿射 det ≡ 1**(擰而不變面積)—— 塞滿一般仿射四自由度且體積守恆。
`build_spine --shear-pivot`(include_shear 隱含 include_scale)端到端把 rotate/scale/shearX/shearY 一起繞
關節 pivot 補償 → 件做**守恆的一般仿射**變換而 pivot 精確不動。

**與 squash(G-4'''')的關鍵差異(兩種「體積守恆」)**:squash 用**非均勻** scale(scaleX·scaleY=1)但其
純 shearX 仍使 full det=cos(shearX)≠1(守的是 **scale 通道**的積,非整個矩陣);vtwist 用**均勻** scale 使
**full-matrix** det≡1(守的是**整個仿射**的面積)。故 vtwist 的 scale 是 uniform、squash 的是 non-uniform ——
本閘的 V3(c)/V6(e) 以「同一份 build 內 squash 的 full det≠1 vs vtwist 的 full det≡1」量化這個區別(誠實、可追溯)。

真值/fixture 與 (E/H/I/J/G-4'/G-4''''/G-4'''''') 一致:從**先驗庫**(slot_bigwin,新增 vtwist beat)經
`analyze_target` → **真實 build_spine robot 骨架** → `build_animations` 端到端量。主秀運動無唯一正解
(PROPOSAL 手感),閘驗**客觀結構簽章(兩軸阻尼振盪 + 反相 + full-matrix 體積守恆)+ 端到端不動點**,非美感;
負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  VT1 present + dual-channel(crux) : vtwist beat 直出、finite、有 bone;≥1 bone 帶 shear 通道,其 shearX 峰
                                     ≥ MIN_SHEAR **且** shearY 峰 ≥ MIN_SHEAR(反相雙軸);**且**帶 scale 通道,
                                     scale 峰 |s−1| ≥ MIN_SCALE(耦合守恆 scale 實際存在)。
  VT2 兩軸皆阻尼振盪 + 反相        : 每個 vtwist bone 的 shearX **與** shearY 各自:(a)首尾 0;(b)繞 0 變號 ≥3;
                                    (c)相繼極值嚴格遞減(阻尼);且每內部極值 shearX·shearY<0(反相)。復用 twist 判準。
  VT3 full-matrix 體積守恆(crux)  : 每個 vtwist bone 的**每個**內部極值幀:(a)完整 local 仿射
                                    M=transform_matrix_full(0,sx,sy,shx,shy) 的 det ≈ 1(|det−1|≤TOL_VOL);
                                    (b)scale **uniform**(|scaleX−scaleY|≤TOL_UNIFORM,異於 squash 非均勻);
                                    (c)若拿掉 scale(純雙軸 shear)det=cos(Δ)<1(峰面積損失 ≥MIN_SHRINK)—— 證
                                    scale 正是守恆來源(非 shear 本身守恆)。
  VT4 identity 介面(可插 Loop)   : sample(0)/sample(dur) 各 bone identity,shear 首尾 (0,0)、scale 首尾 (1,1)。
  VT5 端到端守恆仿射 pivot 不動    : `build_spine --shear-pivot`(真實 robot)產出 vtwist 帶補償;凡有關節
                                    pivot 的 bone,pivot 殘差 < TOL_FIX;內建負對照 = 未補償(繞件中心,含
                                    雙軸 shear+scale)大位移 → 證補償把守恆一般仿射也錨在 pivot。
  VT6 負對照/隔離                 : (a)**無 scale 守衛**:純雙軸 shear(s≡1,即 twist)→ full det=cos(Δ)≠1 →
                                    體積守恆 FALSE(證 scale 是守恆來源);(b)**非均勻 scale 守衛**:squash 式
                                    scaleX≠scaleY(scaleX·scaleY=1)→ uniform FALSE(證閘測「uniform 守恆 scale」
                                    非「任意耦合 scale」);(c)**shearY 隔離**:非 twist/vtwist beat 皆 shearY≡0;
                                    (d)**加性**:移除 vtwist 的 storyboard → 其餘 beat 逐位元不變(零回歸);
                                    (e)**跨 beat 鑑別(crux)**:同一份 build 內 squash beat 的 full det 明顯 ≠1
                                    (< 1−MIN_SHRINK,守的是 scale 積非整個矩陣)vs vtwist full det ≡1 → 量化兩種
                                    「體積守恆」的差異。

用法:
  python3 validate_vtwist_gen.py            # 摘要
  python3 validate_vtwist_gen.py --json     # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim as SA
import gen_animations as G
# 復用 shear 讀取與阻尼簽章判準,確保與 shear-gen / twist-gen 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_twist_gen import _shear_y, _shear_xy, _interior_shear, _has_shear_y
from validate_shear_pivot import _world   # 真實 Spine local(含雙軸 shear + scale)世界座標求值
from pivot_rotation import transform_matrix_full

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0      # 度,vtwist 峰值 |shearX| / |shearY| 下限(shearY 峰 = 0.7×shearX 峰,head 最小 7° → 餘裕)
MIN_SCALE = 0.005    # 耦合守恆 scale 峰 |s−1| 下限(head 峰≈0.02、特效峰≈0.06 → 餘裕;證 scale 通道實際存在)
MIN_DEV = 8.0        # 度,反相夾角偏離 |shearY−shearX| 峰下限(head 首極值 10+7=17° → 充足餘裕)
TOL_VOL = 3e-3       # full-matrix |det−1| 上限(4dp scale 捨入下實測 <1e-4 → >30× 餘裕)
TOL_UNIFORM = 1e-4   # uniform |scaleX−scaleY| 上限(由建構 sx==sy,捨入相同 → 0)
MIN_SHRINK = 0.02    # 純雙軸 shear 峰面積損失 1−cos(Δ) 下限(峰實測 ~0.11 → 餘裕;證 shear 本身不守恆)
TOL_FIX = 0.5        # px,pivot 不動點殘差上限(同 twist)
MIN_NEG = 5.0        # px,VT5 負對照(未補償)位移下限
NEG_RATIO = 20.0     # 負對照/不動點 位移比下限


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/vtwist_gen_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    from analyze_target import analyze
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _cat_beats(anims, cat):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == cat]


def _scale_xy(chans):
    """bone channels → [(scaleX, scaleY)] 關鍵幀序列(無 scale 通道回 [])。"""
    fr = chans.get("scale")
    return [(f["x"], f["y"]) for f in fr] if fr else []


def _sheared_scaled(chans):
    """bone channels → 依 time 對齊的 [(shx, shy, sx, sy)](僅取 shear 與 scale 皆有的時刻)。
    shear 與 scale 極值 τ 同點(耦合)→ 直接以 time 索引配對。無 shear 或無 scale 回 []。"""
    shf = chans.get("shear"); scf = chans.get("scale")
    if not shf or not scf:
        return []
    sc_by_t = {round(f["time"], 4): (f["x"], f["y"]) for f in scf}
    out = []
    for f in shf:
        key = round(f["time"], 4)
        if key in sc_by_t:
            sx, sy = sc_by_t[key]
            out.append((f["x"], f["y"], sx, sy))
    return out


def _interior_ss(chans):
    """去掉首尾 identity 端點的內部 (shx, shy, sx, sy) 極值。"""
    ss = _sheared_scaled(chans)
    return ss[1:-1] if len(ss) >= 3 else []


def _full_det(shx, shy, sx, sy):
    """完整 Spine local 仿射 M=transform_matrix_full(θ=0,sx,sy,shx,shy) 的 det。
    = sx·sy·cos(shearX−shearY)(shear 度數 → 弧度)。純函式 → 真實 keyframe 與合成負對照同一判準。"""
    m00, m01, m10, m11 = transform_matrix_full(0.0, sx, sy, shx, shy)
    return m00 * m11 - m01 * m10


def _shear_only_det(shx, shy):
    """純雙軸 shear(sx=sy=1)的 det = cos(shearX−shearY)。"""
    return math.cos(math.radians(shx - shy))


def _vt3_eval(interior):
    """給一組內部 (shx,shy,sx,sy) → (vol_ok, uniform_ok, shrink_ok, detail)。
    純函式 → 對真實 vtwist 與合成負對照(無 scale / squash 式非均勻)施同一判準(閘可信)。"""
    if not interior:
        return False, False, False, {"det": [], "aniso": [], "shear_only": []}
    dets = [_full_det(shx, shy, sx, sy) for (shx, shy, sx, sy) in interior]
    aniso = [abs(sx - sy) for (_, _, sx, sy) in interior]
    shear_only = [_shear_only_det(shx, shy) for (shx, shy, _, _) in interior]
    vol_ok = all(abs(d - 1.0) <= TOL_VOL for d in dets)
    uniform_ok = max(aniso) <= TOL_UNIFORM
    shrink_ok = (1.0 - min(shear_only)) >= MIN_SHRINK   # 純 shear 峰面積損失夠大 → scale 有在補
    detail = {"det": [round(d, 6) for d in dets], "aniso": [round(a, 6) for a in aniso],
              "shear_only": [round(s, 5) for s in shear_only]}
    return vol_ok, uniform_ok, shrink_ok, detail


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    vt_beats = _cat_beats(anims, "vtwist")
    R = {}

    # ---- VT1 present + dual-channel emitted (crux) ----
    s1 = {"vtwist_beats": vt_beats, "not_finite": [], "no_bones": [], "no_shear": [],
          "no_scale": [], "weak_shearx": [], "weak_sheary": [], "weak_scale": [], "peak_by_beat": {}}
    for tb in vt_beats:
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
            s1["no_scale"].append(tb); continue
        shx_pk = max(max(abs(v) for v in _shear_x(ch)) for ch in sheared.values())
        shy_pk = max(max(abs(v) for v in _shear_y(ch)) for ch in sheared.values())
        sc_pk = max(max(max(abs(sx - 1.0), abs(sy - 1.0)) for (sx, sy) in _scale_xy(ch))
                    for ch in scaled.values())
        s1["peak_by_beat"][tb] = {"shearX": round(shx_pk, 3), "shearY": round(shy_pk, 3),
                                  "scale": round(sc_pk, 4)}
        if shx_pk < MIN_SHEAR:
            s1["weak_shearx"].append(tb)
        if shy_pk < MIN_SHEAR:
            s1["weak_sheary"].append(tb)
        if sc_pk < MIN_SCALE:
            s1["weak_scale"].append(tb)
    s1_pass = (bool(vt_beats) and not s1["not_finite"] and not s1["no_bones"]
               and not s1["no_shear"] and not s1["no_scale"] and not s1["weak_shearx"]
               and not s1["weak_sheary"] and not s1["weak_scale"])
    R["VT1_present_dual_channel"] = {**s1, "pass": s1_pass}

    # ---- VT2 both axes damped oscillation + counter-phase (reuse twist criteria) ----
    s2 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "not_counterphase": [],
          "detail": {}}
    for tb in vt_beats:
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
            interior = _interior_shear(ch)
            if interior and _has_shear_y(ch):
                if not all(shx * shy < -1e-9 for (shx, shy) in interior):
                    s2["not_counterphase"].append("{}::{}".format(tb, bn))
    s2_pass = (bool(s2["detail"]) and not s2["bad_endpoints"] and not s2["few_sign_changes"]
               and not s2["not_damped"] and not s2["not_counterphase"])
    R["VT2_damped_counterphase"] = {**s2, "pass": s2_pass}

    # ---- VT3 full-matrix volume conservation (crux) ----
    s3 = {"not_conserved": [], "not_uniform": [], "no_shrink": [], "detail": {}}
    for tb in vt_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            interior = _interior_ss(ch)
            if not interior or not _has_shear_y(ch):
                continue
            key = "{}::{}".format(tb, bn)
            vol_ok, uni_ok, shr_ok, det = _vt3_eval(interior)
            s3["detail"][key] = det
            if not vol_ok:
                s3["not_conserved"].append(key)
            if not uni_ok:
                s3["not_uniform"].append(key)
            if not shr_ok:
                s3["no_shrink"].append(key)
    s3_pass = (bool(s3["detail"]) and not s3["not_conserved"] and not s3["not_uniform"]
               and not s3["no_shrink"])
    R["VT3_full_matrix_volume_conserved"] = {**s3, "pass": s3_pass}

    # ---- VT4 identity interface ----
    s4 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for tb in vt_beats:
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
                s4["scale_endpoints_nonident"].append("{}::{}".format(tb, bn))
    R["VT4_identity_interface"] = {**s4, "pass": (not s4["bad_interface"]
                                                  and not s4["shear_endpoints_nonzero"]
                                                  and not s4["scale_endpoints_nonident"])}

    # ---- VT5 end-to-end conserving-affine pivot-fixed via build_spine --shear-pivot ----
    import build_spine
    out = "/tmp/vtwist_gen_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    s5 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0}
    for tb in _cat_beats(sp_skel["animations"], "vtwist"):
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
            # 內建負對照:未補償(繞件中心)—— 同雙軸 shear+scale 但無 translate
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"bone": bn, "beat": tb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            s5["checked"].append(rec)
            if not (fix < TOL_FIX):
                s5["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                s5["fail_negctrl"].append(rec)
    s5_pass = (s5["n_joint_bones"] >= 1 and not s5["fail_fixed"] and not s5["fail_negctrl"])
    R["VT5_end2end_conserving_pivot_fixed"] = {**s5, "pass": s5_pass}

    # ---- VT6 negative controls / isolation ----
    s6 = {}
    # (a) 無 scale 守衛:純雙軸 shear(s≡1,即 twist)→ full det=cos(Δ)≠1 → 體積守恆 FALSE
    noscale = [(16.0, -11.2, 1.0, 1.0), (-8.0, 5.6, 1.0, 1.0), (4.0, -2.8, 1.0, 1.0)]
    vol_a, uni_a, _, _ = _vt3_eval(noscale)
    s6["a_noscale_guard"] = {"volume_ok": vol_a, "pass": not vol_a}
    # (b) 非均勻 scale 守衛:squash 式 scaleX≠scaleY(積=1)→ uniform FALSE(證測「uniform 守恆」非「任意耦合 scale」)
    nonuni = [(16.0, -11.2, 1.12, 1.0 / 1.12), (-8.0, 5.6, 1.06, 1.0 / 1.06),
              (4.0, -2.8, 1.03, 1.0 / 1.03)]
    _, uni_b, _, _ = _vt3_eval(nonuni)
    s6["b_nonuniform_guard"] = {"uniform_ok": uni_b, "pass": not uni_b}
    # (c) shearY 隔離:非 twist/vtwist beat 皆 shearY≡0(反相雙軸節拍獨佔第二條 shear 軸)
    leak = []
    for nm, an in anims.items():
        if "__" in nm or G.beat_category(nm) in ("twist", "vtwist"):
            continue
        for bn, ch in an.get("bones", {}).items():
            if _has_shear_y(ch):
                leak.append((nm, bn))
    s6["c_sheary_isolated"] = {"leaked": leak, "pass": not leak}
    # (d) 加性:移除 vtwist 的 storyboard → 其餘 beat 逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "vtwist"]}
    anims_no = G.build_animations(skel, sb_no)
    regressed = []
    for nm, an in anims_no.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    s6["d_additive_no_regression"] = {"regressed": regressed,
                                      "removed_beats": [b["beat"] for b in sb["beats"]
                                                        if G.beat_category(b["beat"]) == "vtwist"],
                                      "pass": not regressed}
    # (e) 跨 beat 鑑別(crux):同一份 build 內 squash beat 的 full det ≠1(守 scale 積非整個矩陣)
    #     vs vtwist full det ≡1 → 量化兩種「體積守恆」的差異(squash: shearX 使 det=cos(shx)<1)。
    sq_dets = []
    for tb in _cat_beats(anims, "squash"):
        for bn, ch in anims[tb].get("bones", {}).items():
            for (shx, shy, sx, sy) in _interior_ss(ch):
                sq_dets.append(_full_det(shx, shy, sx, sy))
    vt_dets = [d for k, det in s3["detail"].items() for d in det["det"]]
    sq_min_dev = round(1.0 - min(sq_dets), 5) if sq_dets else 0.0   # squash full det 最大偏離 1
    vt_max_dev = round(max(abs(d - 1.0) for d in vt_dets), 6) if vt_dets else 1.0
    s6["e_squash_fulldet_differs"] = {
        "squash_full_det_max_deviation": sq_min_dev, "vtwist_full_det_max_deviation": vt_max_dev,
        "n_squash_extrema": len(sq_dets),
        "pass": (bool(sq_dets) and sq_min_dev >= MIN_SHRINK and vt_max_dev <= TOL_VOL)}
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
        for k in ["VT1_present_dual_channel", "VT2_damped_counterphase",
                  "VT3_full_matrix_volume_conserved", "VT4_identity_interface",
                  "VT5_end2end_conserving_pivot_fixed", "VT6_neg_control"]:
            print("{:36s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("VT1 peaks by beat:", R["VT1_present_dual_channel"]["peak_by_beat"])
        print("VT3 detail:", json.dumps(R["VT3_full_matrix_volume_conserved"]["detail"], ensure_ascii=False))
        e = R["VT6_neg_control"]["e_squash_fulldet_differs"]
        print("VT6(e) squash full-det max-dev {} vs vtwist {} (n_squash_extrema {})".format(
            e["squash_full_det_max_deviation"], e["vtwist_full_det_max_deviation"], e["n_squash_extrema"]))
        print("VT5 pivot-fixed (fixed/negctrl px):")
        for rec in R["VT5_end2end_conserving_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
