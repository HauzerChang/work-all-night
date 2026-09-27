#!/usr/bin/env python3
"""candidate G-4''''''-vol 自我驗收閘 — **volume-conserving twist**(反相雙軸 shear 接體積守恆等向 scale;純 CPU)。

twist(G-4'''''')的 honest boundary(一路留到現在):反相雙軸 shear 的 Spine local 行列式
`det = cos(shearX − shearY)`(兩基底夾角 = 90 + shearY − shearX,反相時被擰緊 → cos<1)→ **擰轉使面積縮小**
(`det≠1`,見 STATE「volume-conserving twist 為後續」)。本 chunk 補上一條**等向**(uniform)補償 scale
`s = 1/√cos(shearX − shearY)` → 全域 local 行列式 `det = (s·s)·cos(shearX − shearY) ≡ 1`(**擰而不變面積**):
`shear + scale + rotate` 三通道**同時**作用、塞滿一般仿射四自由度**且體積守恆**。`build_spine --twist-volume
--shear-pivot` 端到端把三通道一起繞關節 pivot 補償。

crux:twist 的補償為**等向**(scaleX==scaleY)—— twist 的各向異性全由 shear 提供,scale 只做等向的面積復原;
此與 squash(G-4'''')的**非均勻**(scaleX≠scaleY)體積守恆機制**不同源**(squash 的 scale 本身即擠壓)。
det 是 sx·sy 的約束,等向是最小(不再引入額外各向異性)的守恆選擇。

真值/fixture 與 twist 系列一致:從**先驗庫**(slot_bigwin twist beat)經 `analyze_target` → **真實 build_spine
robot 骨架** → `build_animations(twist_volume=True)` 端到端量。主秀運動無唯一正解(PROPOSAL 手感),閘驗
**客觀結構簽章(雙軸阻尼振盪 + 反相 + 體積守恆)+ 端到端不動點**,非美感;負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  TV1 present + shear&scale 雙通道(crux): twist(vol)beat 直出、finite、有 bone,且 ≥1 bone **同時**帶 shear
                                    (雙軸:shearX 峰 ≥ MIN_SHEAR 且 shearY 峰 ≥ MIN_SHEAR)**與** scale 通道,
                                    且 scale 為**等向**(每幀 scaleX==scaleY)→ shear+scale 同時、補償等向。
  TV2 體積守恆(crux)              : 每個 twist bone 每個內部極值幀,全域 local 行列式(`transform_matrix_full`
                                    帶 shearX/shearY/scaleX/scaleY)|det−1| ≤ TOL_DET(**擰而不變面積**);
                                    **負對照** = 同 shear 但 scale≡1(=純 twist)→ |det−1| ≥ MIN_SHRINK
                                    (擰轉縮面積)→ 證閘測「真體積守恆」非「有 scale 即可」。
  TV3 雙軸反相 shear 簽章保形      : 體積耦合**不破壞** twist 簽章 —— 每 twist bone 的 shearX 與 shearY 各自
                                    (a)首尾 0(b)繞 0 變號 ≥3(c)相繼極值遞減(阻尼);且每內部極值反號
                                    (反相耦合,復用 TW3 判準)。scale 等向 → 不引入額外各向異性。
  TV4 identity 介面(可插 Loop)   : sample(0)/sample(dur) 各 bone identity;shear 首尾 (0,0)、scale 首尾 (1,1)。
  TV5 端到端三通道 pivot 不動      : `build_spine --twist-volume --shear-pivot`(真實 robot)產 twist 帶
                                    shear+scale+rotate 補償;凡有關節 pivot 的 bone,pivot 殘差 < TOL_FIX;
                                    內建負對照 = 未補償(繞件中心)大位移 → 證三通道(含補償 scale)皆錨在 pivot。
  TV6 負對照/隔離/向後相容        : (a)**無補償守衛**:scale≡1(純 twist)→ 體積守恆 FALSE(det 縮);
                                    (b)**等向 vs 非均勻隔離**:twist(vol)scale 等向(scaleX==scaleY)、squash
                                    scale **非均勻**(scaleX≠scaleY)→ 兩種體積守恆機制不同源、互不外洩;
                                    (c)**向後相容/加性**:`twist_volume=False` → twist 逐位元同 shear-only
                                    (無 scale 通道);移除 twist storyboard → 其餘 beat 逐位元不變(零回歸)。

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
from pivot_rotation import transform_matrix_full
# 復用 twist-gen / shear-gen 閘的讀取與阻尼/反相判準,確保與 twist 系列閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_shear_pivot import _world
from validate_twist_gen import (_shear_y, _shear_xy, _interior_shear, _tw3_eval,
                                _has_shear_y, _psd, _skeleton, _storyboard, _is_ident,
                                GENRE, MIN_SHEAR, MIN_DEV, TOL_FIX, MIN_NEG, NEG_RATIO)

TOL_DET = 2e-4       # |det−1| 上限(4-dec keyframe 捨入殘差實測 <9e-5;同 squash SC2 體積守恆容差)
MIN_SHRINK = 0.02    # 純 twist(scale≡1)|det−1| 下限(head 首極值縮 4.4%、特效縮 11% → 充足餘裕)


def _scale_frames(chans):
    """bone channels → scale 關鍵幀 [(scaleX, scaleY)](無 scale 通道回 [])。"""
    fr = chans.get("scale")
    return [(f["x"], f["y"]) for f in fr] if fr else []


def _local_det(scaleX, scaleY, shx, shy):
    """真實 Spine local 2×2(rotate 對 det 無影響 → deg=0)的行列式。"""
    a, b, c, d = transform_matrix_full(0.0, scaleX, scaleY, shx, shy)
    return a * d - b * c


def _twist_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "twist"]


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb, twist_volume=True)   # ★ 體積守恆 twist 直出
    twist_beats = _twist_beats(anims)
    R = {}

    # ---- TV1 present + shear&scale dual-channel, isotropic scale (crux) ----
    s1 = {"twist_beats": twist_beats, "not_finite": [], "no_bones": [], "no_shear": [],
          "no_scale": [], "weak_shearx": [], "weak_sheary": [], "anisotropic_scale": [],
          "peak_by_beat": {}}
    for tb in twist_beats:
        an = anims[tb]
        if not SA.all_finite(an):
            s1["not_finite"].append(tb)
        if not an.get("bones"):
            s1["no_bones"].append(tb)
        sheared = {bn: ch for bn, ch in an.get("bones", {}).items() if _shear_xy(ch)}
        scaled = {bn: ch for bn, ch in an.get("bones", {}).items() if _scale_frames(ch)}
        if not sheared:
            s1["no_shear"].append(tb); continue
        if not scaled:
            s1["no_scale"].append(tb)
        shx_pk = max(max(abs(v) for v in _shear_x(ch)) for ch in sheared.values())
        shy_pk = max(max(abs(v) for v in _shear_y(ch)) for ch in sheared.values())
        s1["peak_by_beat"][tb] = {"shearX": round(shx_pk, 3), "shearY": round(shy_pk, 3)}
        if shx_pk < MIN_SHEAR:
            s1["weak_shearx"].append(tb)
        if shy_pk < MIN_SHEAR:
            s1["weak_sheary"].append(tb)
        # scale 等向:每幀 scaleX==scaleY(twist 的補償為 uniform)
        for bn, ch in scaled.items():
            if any(abs(sx - sy) > 1e-6 for (sx, sy) in _scale_frames(ch)):
                s1["anisotropic_scale"].append("{}::{}".format(tb, bn))
    s1_pass = (bool(twist_beats) and not s1["not_finite"] and not s1["no_bones"]
               and not s1["no_shear"] and not s1["no_scale"] and not s1["weak_shearx"]
               and not s1["weak_sheary"] and not s1["anisotropic_scale"])
    R["TV1_present_shear_scale"] = {**s1, "pass": s1_pass}

    # ---- TV2 volume conservation (crux) + no-compensation negative control ----
    s2 = {"break_conserve": [], "neg_not_shrink": [], "detail": {}}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            xy = _shear_xy(ch); sc = _scale_frames(ch)
            if len(xy) < 3 or len(sc) != len(xy):
                continue
            key = "{}::{}".format(tb, bn)
            # 內部極值(去首尾 identity);shear/scale 關鍵幀同 τ 同索引(耦合生成)
            dev_vol, dev_plain = [], []
            for (shx, shy), (scx, scy) in list(zip(xy, sc))[1:-1]:
                dev_vol.append(abs(_local_det(scx, scy, shx, shy) - 1.0))     # 帶補償 → ≈1
                dev_plain.append(abs(_local_det(1.0, 1.0, shx, shy) - 1.0))   # 負對照 scale≡1 → 縮
            s2["detail"][key] = {"max_dev_vol": round(max(dev_vol), 6),
                                 "max_dev_plain": round(max(dev_plain), 6)}
            if max(dev_vol) > TOL_DET:
                s2["break_conserve"].append(key)
            if max(dev_plain) < MIN_SHRINK:
                s2["neg_not_shrink"].append(key)
    s2_pass = (bool(s2["detail"]) and not s2["break_conserve"] and not s2["neg_not_shrink"])
    R["TV2_volume_conserved"] = {**s2, "pass": s2_pass}

    # ---- TV3 dual-axis counter-phase damped signature preserved ----
    s3 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [],
          "not_counterphase": [], "weak_dev": [], "detail": {}}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            # 兩軸各自阻尼振盪
            for axis, vals in (("x", _shear_x(ch)), ("y", _shear_y(ch))):
                if not vals:
                    continue
                key = "{}::{}::{}".format(tb, bn, axis)
                s3["detail"][key] = {"n_sign_changes": _sign_changes_zero(vals),
                                     "damped": _extrema_mags_decreasing(vals)}
                if not (abs(vals[0]) < 1e-6 and abs(vals[-1]) < 1e-6):
                    s3["bad_endpoints"].append(key)
                if _sign_changes_zero(vals) < 3:
                    s3["few_sign_changes"].append(key)
                if not _extrema_mags_decreasing(vals):
                    s3["not_damped"].append(key)
            # 反相耦合
            interior = _interior_shear(ch)
            if interior and _has_shear_y(ch):
                cp_ok, dev_ok, _ = _tw3_eval(interior)
                if not cp_ok:
                    s3["not_counterphase"].append("{}::{}".format(tb, bn))
                if not dev_ok:
                    s3["weak_dev"].append("{}::{}".format(tb, bn))
    s3_pass = (bool(s3["detail"]) and not s3["bad_endpoints"] and not s3["few_sign_changes"]
               and not s3["not_damped"] and not s3["not_counterphase"] and not s3["weak_dev"])
    R["TV3_dual_axis_signature"] = {**s3, "pass": s3_pass}

    # ---- TV4 identity interface (shear (0,0) & scale (1,1) at ends) ----
    s4 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for tb in twist_beats:
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
            sc = _scale_frames(ch)
            if sc and (abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6
                       or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6):
                s4["scale_endpoints_nonident"].append("{}::{}".format(tb, bn))
    R["TV4_identity_interface"] = {**s4, "pass": (not s4["bad_interface"]
                                                  and not s4["shear_endpoints_nonzero"]
                                                  and not s4["scale_endpoints_nonident"])}

    # ---- TV5 end-to-end shear+scale+rotate pivot-fixed via build_spine --twist-volume --shear-pivot ----
    import build_spine
    out = "/tmp/twist_vol_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True, twist_volume=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    s5 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0,
          "n_with_scale": 0}
    for tb in _twist_beats(sp_skel["animations"]):
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
            if ch.get("scale"):
                s5["n_with_scale"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"bone": bn, "beat": tb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2),
                   "has_scale": bool(ch.get("scale"))}
            s5["checked"].append(rec)
            if not (fix < TOL_FIX):
                s5["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                s5["fail_negctrl"].append(rec)
    s5_pass = (s5["n_joint_bones"] >= 1 and s5["n_with_scale"] >= 1
               and not s5["fail_fixed"] and not s5["fail_negctrl"])
    R["TV5_end2end_pivot_fixed"] = {**s5, "pass": s5_pass}

    # ---- TV6 negative controls / isolation / backward-compat ----
    s6 = {}
    # (a) 無補償守衛:scale≡1(純 twist)→ 對真實 twist shear 施 det 度量 → 體積守恆 FALSE(縮面積)
    tw_shears = []
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            tw_shears += _interior_shear(ch)
    plain_dev = [abs(_local_det(1.0, 1.0, shx, shy) - 1.0) for (shx, shy) in tw_shears]
    a_ok = bool(plain_dev) and max(plain_dev) >= MIN_SHRINK
    s6["a_no_compensation_shrinks"] = {"max_dev_plain": round(max(plain_dev), 5) if plain_dev else 0.0,
                                       "pass": a_ok}
    # (b) 等向 vs 非均勻隔離:twist(vol)scale 等向;squash scale 非均勻(不同源機制,互不外洩)
    sq_beats = [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "squash"]
    tw_uniform = all(abs(sx - sy) <= 1e-6
                     for tb in twist_beats for ch in anims[tb].get("bones", {}).values()
                     for (sx, sy) in _scale_frames(ch))
    sq_anisotropic = any(abs(sx - sy) > 1e-6
                         for sb2 in sq_beats for ch in anims[sb2].get("bones", {}).values()
                         for (sx, sy) in _scale_frames(ch))
    s6["b_isotropic_vs_nonuniform"] = {"twist_scale_uniform": tw_uniform,
                                       "squash_scale_nonuniform": sq_anisotropic,
                                       "squash_beats": sq_beats,
                                       "pass": tw_uniform and sq_anisotropic}
    # (c) 向後相容/加性:twist_volume=False → twist 無 scale 通道且逐位元同舊;移除 twist → 其餘不變
    anims_off = G.build_animations(skel, sb)   # 預設 twist_volume=False
    twist_has_scale_off = any(_scale_frames(ch)
                              for tb in _twist_beats(anims_off)
                              for ch in anims_off[tb].get("bones", {}).values())
    # off 的 twist 與 on 的**其餘 beat** 皆逐位元一致(僅 twist beat 因掛 scale 而異)
    regressed = [nm for nm in anims_off
                 if G.beat_category(nm) != "twist"
                 and json.dumps(anims_off[nm], sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True)]
    # 移除 twist storyboard → 其餘 beat 逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "twist"]}
    anims_no = G.build_animations(skel, sb_no, twist_volume=True)
    removed_regressed = [nm for nm in anims_no
                         if json.dumps(anims_no[nm], sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True)]
    s6["c_backward_compat_additive"] = {"twist_has_scale_when_off": twist_has_scale_off,
                                        "regressed_nontwist": regressed,
                                        "removed_regressed": removed_regressed,
                                        "pass": (not twist_has_scale_off and not regressed
                                                 and not removed_regressed)}
    R["TV6_neg_control"] = {**s6, "pass": all(v["pass"] for v in s6.values())}

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
        for k in ["TV1_present_shear_scale", "TV2_volume_conserved",
                  "TV3_dual_axis_signature", "TV4_identity_interface",
                  "TV5_end2end_pivot_fixed", "TV6_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("TV1 peaks by beat:", R["TV1_present_shear_scale"]["peak_by_beat"])
        print("TV2 det detail:", json.dumps(R["TV2_volume_conserved"]["detail"], ensure_ascii=False))
        print("TV5 pivot-fixed (fixed/negctrl px):")
        for rec in R["TV5_end2end_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}  scale={}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"], rec["has_scale"]))
        print("TV6 (a) plain max|det-1|:", R["TV6_neg_control"]["a_no_compensation_shrinks"]["max_dev_plain"],
              "| (b) twist uniform:", R["TV6_neg_control"]["b_isotropic_vs_nonuniform"]["twist_scale_uniform"],
              "squash nonuniform:", R["TV6_neg_control"]["b_isotropic_vs_nonuniform"]["squash_scale_nonuniform"])
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
