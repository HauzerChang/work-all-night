#!/usr/bin/env python3
"""candidate G-4''''''-vol 自我驗收閘 — 生成器產出**體積守恆的反相雙軸 shear**(twistvol)端到端(純 CPU)。

補 twist(G-4'''''')一路留到現在的 honest boundary:**反相雙軸 shear 未接體積守恆**。**關鍵幾何**:Spine
local 2×2 的行列式(=面積縮放)= scaleX·scaleY·cos(shearY−shearX)(見 `pivot_rotation.transform_matrix_full`:
det = sx·sy·sin(90+shy−shx) = sx·sy·cos(shy−shx))。twist 令 scaleX=scaleY=1 → det = cos(shearY−shearX) < 1
(反相時 shy−shx=−(1+φ)·shearX → cos<1)→ **擰轉會縮面積**(擰毛巾投影變小)。twistvol 加一條**各向同性**
補償 scale sx=sy=1/√cos(shearY−shearX) 使**完整** local det ≡ 1(含兩條 shear 軸的真面積守恆),首尾 identity。

**與 squash 的鑑別(本閘的鑑別力來源)**:squash 用**非均勻** scale(sx≠sy、scaleX·scaleY=1)做擠壓,只守
**scale 子塊**;其完整 det = (sx·sy)·cos(shearX) = cos(shearX) < 1 → squash **仍縮面積**。twistvol 用**各向同性**
scale(sx==sy)做面積回補,守恆**完整** det(含 shear)→ **第一個守恆完整仿射面積的節拍**。三者對照:
  - 純 twist(sx=sy=1)         → det=cos<1(縮面積)              → 負對照(a)
  - squash 式(sx≠sy、sx·sy=1) → det=cos(shearX)<1(仍縮)+ 非均勻 → 負對照(b:守子塊非守完整、非各向同性)
  - twistvol(sx=sy=1/√cos)   → det≡1(完整守恆)+ 各向同性          → 本 beat
shear+scale+rotate 三通道同時、塞滿一般仿射四自由度且守恆 —— twist 那條 honest boundary 就此補上。

真值/fixture 與 (E/H/I/J/G-4'/G-4''''/G-4'''''') 一致:從**先驗庫**(slot_bigwin,新增 twistvol beat)經
`analyze_target` → **真實 build_spine robot 骨架** → `build_animations` 端到端量。主秀運動無唯一正解
(PROPOSAL 手感),閘驗**客觀結構簽章(兩軸阻尼振盪 + 反相雙軸 + 完整面積守恆 + 各向同性)+ 端到端不動點**,
非美感;負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  VT1 present + dual-axis + scale(crux): twistvol beat 直出、finite、有 bone,且 ≥1 bone **同時**帶 shear
                                    (shearX 峰 ≥ MIN_SHEAR 且 shearY 峰 ≥ MIN_SHEAR)與 `scale` 通道 → **產線
                                    第一次產出「雙軸 shear + 體積補償 scale」**。
  VT2 兩軸皆阻尼振盪               : 每個 twistvol bone 的 shearX **與** shearY 各自:(a)首尾 0;(b)繞 0 變號 ≥3;
                                    (c)相繼極值幅度嚴格遞減(阻尼)—— 復用 G-4' 判準(承 twist 簽章)。
  VT3 反相雙軸 shear 耦合(crux)  : 每個內部極值幀 shearX·shearY<0 且夾角偏離 |shearY−shearX| ≥ MIN_DEV
                                    (承 twist 反相雙軸簽章)。
  VT4 完整面積守恆 + 各向同性(crux): 每個關鍵幀 (a)完整 det = scaleX·scaleY·cos(shearY−shearX) ≈ 1
                                    (|det−1| ≤ TOL_VOL,含 shear 的真面積守恆);(b)scale **各向同性**
                                    |scaleX−scaleY| ≤ TOL_ISO(有別 squash 非均勻擠壓);(c)內部至少一幀補償拉伸
                                    scaleX > 1+MIN_STRETCH(shear 縮面積 → scale 回補)。
  VT5 identity 介面(可插 Loop)   : sample(0)/sample(dur) 各 bone identity,且 shear 首尾 (0,0)、scale 首尾 (1,1)。
  VT6 端到端一般仿射 pivot 不動    : `build_spine --shear-pivot`(真實 robot)產出 twistvol 帶補償;凡有關節 pivot
                                    的 bone,pivot 殘差 < TOL_FIX(在雙軸 shear + 補償 scale 驅動下);內建負對照
                                    = 未補償(繞件中心)大位移 → 證補償把「用滿一般仿射四自由度且守恆」也錨在 pivot。
  VT7 負對照/隔離                 : (a)**純 twist 守衛**:合成雙軸 shear + identity scale(sx=sy=1)→ VT4 完整守恆
                                    FALSE(det=cos<1)→ 證閘測「完整面積守恆」非「有 scale 即可」;
                                    (b)**squash 式守衛**:合成非均勻 scale(sx≠sy、sx·sy=1)+ 雙軸 shear → 完整 det
                                    =cos(shearX)<1(VT4 volume FALSE)且各向同性 FALSE → 證 twistvol 守**完整** det
                                    (squash 只守子塊)且**各向同性**(非 squash 擠壓);
                                    (c)**耦合隔離**:非 twistvol beat 皆非「同時帶 shearY 且帶 scale 通道」
                                    (twist 有 shearY 無 scale、squash 有 scale 無 shearY → twistvol 獨佔此耦合);
                                    (d)**加性**:移除 twistvol 的 storyboard → 其餘 beat(含**純 twist 逐位元不變**,證
                                    未改 gen_twist)逐位元不變(零回歸)。

用法:
  python3 validate_twist_volume.py            # 摘要
  python3 validate_twist_volume.py --json     # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim as SA
import gen_animations as G
import tier_variants as TV
# 復用既有讀取器與判準,確保與 shear-gen / twist-gen / squash-gen 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_twist_gen import _shear_y, _shear_xy, _interior_shear, _tw3_eval, _has_shear_y
from validate_squash_gen import _scale_xy
from validate_shear_pivot import _world   # 真實 Spine local(含雙軸 shear + scale)世界座標求值

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,twistvol 峰值 |shearX| / |shearY| 下限(同 twist_gen)
MIN_DEV = 8.0       # 度,反相夾角偏離峰下限(同 twist_gen)
TOL_VOL = 2e-3      # 完整 det |det−1| 上限(實測 ~1e-6 → 巨大餘裕)
TOL_ISO = 1e-3      # scale 各向同性 |scaleX−scaleY| 上限(實測 0 → 餘裕)
MIN_STRETCH = 0.005 # 內部補償拉伸 scaleX−1 下限(head 峰 (1+φ)·10=17° → 1/√cos−1≈0.011 → 餘裕)
TOL_FIX = 0.5       # px,pivot 不動點殘差上限(同 twist_gen/squash_gen)
MIN_NEG = 5.0       # px,VT6 負對照(未補償)位移下限
NEG_RATIO = 20.0    # 負對照/不動點 位移比下限


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


def _det_full(shx, shy, sx, sy):
    """完整 Spine local 2×2 行列式 = scaleX·scaleY·cos(shearY−shearX)(度)。"""
    return sx * sy * math.cos(math.radians(shy - shx))


def _vt4_eval(sh_xy, sc_xy):
    """給對齊的 shear [(shx,shy)] 與 scale [(sx,sy)] → (volume_ok, iso_ok, stretch_ok, detail)。

    volume:每幀完整 det ≈ 1(|det−1|≤TOL_VOL);iso:每幀各向同性 |sx−sy|≤TOL_ISO;
    stretch:內部至少一幀補償拉伸 sx>1+MIN_STRETCH。純函式 → 對真實 twistvol 與合成負對照施同一判準(閘可信)。"""
    if not sh_xy or not sc_xy or len(sh_xy) != len(sc_xy):
        return False, False, False, {"det": [], "iso": []}
    dets = [_det_full(shx, shy, sx, sy) for (shx, shy), (sx, sy) in zip(sh_xy, sc_xy)]
    iso = [abs(sx - sy) for (sx, sy) in sc_xy]
    interior_sx = [sc_xy[i][0] for i in range(1, len(sc_xy) - 1)]
    volume_ok = all(abs(d - 1.0) <= TOL_VOL for d in dets)
    iso_ok = max(iso) <= TOL_ISO
    stretch_ok = any(sx > 1.0 + MIN_STRETCH for sx in interior_sx)
    detail = {"det": [round(d, 6) for d in dets], "iso": [round(a, 6) for a in iso]}
    return volume_ok, iso_ok, stretch_ok, detail


def _has_scale(chans):
    return bool(chans.get("scale"))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    tvol_beats = _twistvol_beats(anims)
    R = {}

    # ---- VT1 present + dual-axis shear + scale channel (crux) ----
    s1 = {"twistvol_beats": tvol_beats, "not_finite": [], "no_bones": [], "no_triple": [],
          "weak_shearx": [], "weak_sheary": [], "peak_by_beat": {}}
    for tb in tvol_beats:
        an = anims[tb]
        if not SA.all_finite(an):
            s1["not_finite"].append(tb)
        if not an.get("bones"):
            s1["no_bones"].append(tb)
        triple = {bn: ch for bn, ch in an.get("bones", {}).items()
                  if _shear_xy(ch) and _has_scale(ch)}
        if not triple:
            s1["no_triple"].append(tb); continue
        shx_pk = max(max(abs(v) for v in _shear_x(ch)) for ch in triple.values())
        shy_pk = max(max(abs(v) for v in _shear_y(ch)) for ch in triple.values())
        s1["peak_by_beat"][tb] = {"shearX": round(shx_pk, 3), "shearY": round(shy_pk, 3)}
        if shx_pk < MIN_SHEAR:
            s1["weak_shearx"].append(tb)
        if shy_pk < MIN_SHEAR:
            s1["weak_sheary"].append(tb)
    s1_pass = (bool(tvol_beats) and not s1["not_finite"] and not s1["no_bones"]
               and not s1["no_triple"] and not s1["weak_shearx"] and not s1["weak_sheary"])
    R["VT1_present_dual_axis_scale"] = {**s1, "pass": s1_pass}

    # ---- VT2 both axes damped oscillation (承 twist) ----
    s2 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "detail": {}}
    for tb in tvol_beats:
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

    # ---- VT3 counter-phase two-axis coupling (承 twist,復用 _tw3_eval) ----
    s3 = {"not_counterphase": [], "weak_dev": [], "detail": {}}
    for tb in tvol_beats:
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

    # ---- VT4 full-matrix volume conservation + isotropy (crux) ----
    s4 = {"bad_volume": [], "not_isotropic": [], "no_stretch": [], "detail": {}}
    for tb in tvol_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            sh_xy, sc_xy = _shear_xy(ch), _scale_xy(ch)
            if not sh_xy or not sc_xy:
                continue
            key = "{}::{}".format(tb, bn)
            vok, iok, sok, det = _vt4_eval(sh_xy, sc_xy)
            s4["detail"][key] = det
            if not vok:
                s4["bad_volume"].append(key)
            if not iok:
                s4["not_isotropic"].append(key)
            if not sok:
                s4["no_stretch"].append(key)
    s4_pass = (bool(s4["detail"]) and not s4["bad_volume"]
               and not s4["not_isotropic"] and not s4["no_stretch"])
    R["VT4_full_volume_conservation_isotropic"] = {**s4, "pass": s4_pass}

    # ---- VT5 identity interface ----
    s5 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for tb in tvol_beats:
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
            sc = _scale_xy(ch)
            if sc and (abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6
                       or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6):
                s5["scale_endpoints_nonident"].append("{}::{}".format(tb, bn))
    R["VT5_identity_interface"] = {**s5, "pass": (not s5["bad_interface"]
                                                  and not s5["shear_endpoints_nonzero"]
                                                  and not s5["scale_endpoints_nonident"])}

    # ---- VT6 end-to-end general-affine pivot-fixed via build_spine --shear-pivot ----
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
            # 內建負對照:未補償(繞件中心)—— 同雙軸 shear + 補償 scale 但無 translate
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
    R["VT6_end2end_affine_pivot_fixed"] = {**s6, "pass": s6_pass}

    # ---- VT7 negative controls / isolation ----
    s7 = {}
    # 共用合成反相雙軸 shear 極值(φ=0.7 → shearY=−0.7·shearX,反相 + 阻尼)
    syn_sh = [(16.0, -11.2), (-8.0, 5.6), (4.0, -2.8), (-2.0, 1.4)]
    # (a) 純 twist 守衛:identity scale(sx=sy=1)→ 完整 det=cos<1 → volume FALSE(證測「完整守恆」非「有 scale」)
    sc_plain = [(1.0, 1.0)] * len(syn_sh)
    v_p, i_p, _st_p, _d_p = _vt4_eval(syn_sh, sc_plain)
    s7["a_plain_twist_guard"] = {"volume_ok": v_p, "pass": not v_p}
    # (b) squash 式守衛:非均勻 scale(sx≠sy、sx·sy=1)→ 完整 det=cos(shearX)≠1(volume FALSE)且各向同性 FALSE
    #     (證 twistvol 守完整 det 且各向同性,squash 只守子塊且非均勻)
    sc_squash = [(1.14, 1.0 / 1.14), (1.07, 1.0 / 1.07), (1.035, 1.0 / 1.035), (1.0175, 1.0 / 1.0175)]
    v_s, i_s, _st_s, _d_s = _vt4_eval(syn_sh, sc_squash)
    s7["b_squash_style_guard"] = {"volume_ok": v_s, "iso_ok": i_s,
                                  "pass": (not v_s) and (not i_s)}
    # 正對照(閘可信度):真 twistvol 各向同性補償 → volume TRUE 且 iso TRUE
    sc_true = []
    from beat_templates import _twistvol_scale
    for (shx, shy) in syn_sh:
        s_iso = _twistvol_scale(shx, shy)
        sc_true.append((round(s_iso, 6), round(s_iso, 6)))
    v_t, i_t, st_t, _d_t = _vt4_eval(syn_sh, sc_true)
    s7["a2_true_positive_unit"] = {"volume_ok": v_t, "iso_ok": i_t, "stretch_ok": st_t,
                                   "pass": (v_t and i_t and st_t)}
    # (c) 耦合隔離:非 twistvol beat 皆非「同時帶 shearY 且帶 scale 通道」
    leak = []
    for nm, an in anims.items():
        if "__" in nm or G.beat_category(nm) == "twistvol":
            continue
        for bn, ch in an.get("bones", {}).items():
            if _has_shear_y(ch) and _has_scale(ch):
                leak.append((nm, bn))
    s7["c_coupling_isolated"] = {"leaked": leak, "pass": not leak}
    # (d) 加性:移除 twistvol 的 storyboard → 其餘 beat(含純 twist)逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "twistvol"]}
    anims_no = G.build_animations(skel, sb_no)
    regressed = []
    for nm, an in anims_no.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    twist_unchanged = (json.dumps(anims_no.get("twist"), sort_keys=True)
                       == json.dumps(anims.get("twist"), sort_keys=True))
    s7["d_additive_no_regression"] = {"regressed": regressed, "twist_unchanged": twist_unchanged,
                                      "removed_beats": [b["beat"] for b in sb["beats"]
                                                        if G.beat_category(b["beat"]) == "twistvol"],
                                      "pass": (not regressed) and twist_unchanged}
    R["VT7_neg_control"] = {**s7, "pass": all(v["pass"] for v in s7.values())}

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
                  "VT3_counterphase_coupling", "VT4_full_volume_conservation_isotropic",
                  "VT5_identity_interface", "VT6_end2end_affine_pivot_fixed", "VT7_neg_control"]:
            print("{:40s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("VT1 peaks by beat:", R["VT1_present_dual_axis_scale"]["peak_by_beat"])
        print("VT4 detail:", json.dumps(R["VT4_full_volume_conservation_isotropic"]["detail"], ensure_ascii=False))
        print("VT6 pivot-fixed (fixed/negctrl px):")
        for rec in R["VT6_end2end_affine_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
