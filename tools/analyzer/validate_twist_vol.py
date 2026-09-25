#!/usr/bin/env python3
"""candidate G-4''''''-vol 自我驗收閘 — volume-conserving twist(擰而不變面積)端到端(純 CPU)。

補 twist 一路(G-4''''''/-tier/-count)留到現在的**最後一條 honest boundary**:反相雙軸 shear 的 Spine
local `det(M)=sx·sy·cos(shearY−shearX)`;純 shear(sx=sy=1)時 `det=cos(−(1+φ)shearX)<1` → **擰轉使面積
縮小**(實測 base twist 峰 det 低至 0.889,~11% 面積損失)。本次(G-4''''''-vol,opt-in)讓 `gen_twist(
vol_conserve=True)` 補一條**均勻** scale `s=1/√cos(shearY−shearX)` 逐幀 → `det=s²·cos≡1`(體積守恆);
首尾 shear=0 → s=1(identity 介面不變)。**均勻(sx=sy)是關鍵**:只補償面積、不引入 squash 的**非均勻**
(scaleX≠scaleY)簽章 —— twist 與 squash 是**兩種不同的體積守恆幾何**(twist=均勻放大補剪切面積損失;
squash=非均勻拉壓保面積)。至此生成器把 **shear(兩軸)+ 均勻 scale 兩通道同時驅動且守恆**。

真值/fixture 與 (G-4''''''/-tier/-count)一致:從**先驗庫**(slot_bigwin)經 `analyze_target` → **真實
build_spine robot 骨架** → `build_animations(twist_vol_conserve=True)` 端到端量。主秀運動無唯一正解
(PROPOSAL 手感),閘驗**客觀結構簽章(體積守恆 + 均勻補償 + 兩軸阻尼)+ 端到端不動點**,非美感;
負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  VC1 present + dual-axis shear + scale 通道(crux): vol-conserve twist beat 直出、finite、有 bone,
                                    且 ≥1 bone 同時帶 (i)shear(shearX 峰、shearY 峰 ≥ MIN_SHEAR、反相)
                                    與 (ii)**scale 通道**且峰 scale > 1+MIN_SCALE_DEV(真補償,非 identity)。
  VC2 體積守恆(crux)             : 每個 twist bone 的**每個**關鍵幀 `det(M_local)=|scaleX·scaleY·
                                    cos(shearY−shearX)|` 滿足 |det−1| ≤ TOL_DET;內建負對照 = base twist
                                    (無補償)峰 det ≤ 1−NEG_DET_MARGIN(證量的是真守恆,非恆等於 1)。
  VC3 均勻補償 + s≥1 + 阻尼保形    : 每個 twist bone 的每個 scale 幀 (a)|scaleX−scaleY| ≤ TOL_UNIFORM
                                    (均勻,非 squash 非均勻);(b)scale ≥ 1−eps(補償只放大不縮);
                                    (c)峰 scale 幀 == 峰 |shearY−shearX| 幀(scale 跟隨 shear 幅度);
                                    且兩 shear 軸各自仍阻尼振盪(繞 0 變號≥3 + 相繼極值遞減,復用 G-4' 判準)。
  VC4 identity 介面(可插 Loop)   : sample(0)/sample(dur) 各 bone identity,shear 首尾 (0,0)、scale 首尾 (1,1)。
  VC5 端到端一般仿射 pivot 不動    : `build_spine --animate --shear-pivot --twist-volume-conserve`(真實
                                    robot);凡有關節 pivot 的 bone,pivot 殘差 < TOL_FIX(**在 shearX+shearY+
                                    均勻 scale 同時驅動下**);內建負對照 = 未補償(繞件中心)大位移。
  VC6 負對照/隔離/加性            : (a)**非守恆守衛**:base twist(vol_conserve=False)峰 det < 1−NEG_DET_MARGIN
                                    → VC2 對 base FALSE(證閘測真守恆);(b)**非均勻守衛**:合成 squash 式
                                    非均勻對(scaleX≠scaleY)→ 均勻判準 FALSE(證 VC3 拒 squash 式補償);
                                    (c)**向後相容/隔離**:vol_conserve=False 逐位元同預設;vol_conserve=True 下
                                    **非 twist** beat 逐位元同 vol_conserve=False(旗標只作用 twist);移除 twist
                                    storyboard → 其餘 beat 逐位元不變(零回歸)。

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
from pivot_rotation import transform_matrix_full
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_twist_gen import _shear_y, _shear_xy, _twist_beats
from validate_shear_pivot import _world

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0        # 度,shearX / shearY 峰下限(同 twist-gen)
MIN_SCALE_DEV = 0.01   # 補償 scale 峰須 > 1+此值(head 最弱 ~1.023 → 餘裕)
TOL_DET = 1e-3         # |det−1| 上限(守恆)
TOL_UNIFORM = 1e-4     # |scaleX−scaleY| 上限(均勻補償)
NEG_DET_MARGIN = 0.02  # base twist 峰 det ≤ 1−此值(實測最小 ~0.889 → 充足)
TOL_FIX = 0.5          # px,pivot 殘差上限(同 G-4 家族)
MIN_NEG = 5.0          # px,VC5 負對照位移下限
NEG_RATIO = 20.0       # 負對照/不動點 比下限


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


def _scale_xy(chans):
    """bone channels → [(scaleX, scaleY)] 關鍵幀序列(無 scale 通道回 [])。"""
    fr = chans.get("scale")
    return [(f["x"], f["y"]) for f in fr] if fr else []


def _det_local(shx, shy, sx, sy):
    """Spine local 2×2 行列式(rotate=0):det = scaleX·scaleY·cos(shearY−shearX)。
    由真實 `transform_matrix_full` 求值(逐位元同 apply_pivots 端到端所用矩陣)。"""
    m00, m01, m10, m11 = transform_matrix_full(0.0, sx, sy, shx, shy)
    return m00 * m11 - m01 * m10


def _bone_dets(ch):
    """對一個 bone 的 shear/scale 通道逐幀算 det(scale 缺 → (1,1))。回傳 [det]。"""
    sh = _shear_xy(ch)
    sc = _scale_xy(ch)
    out = []
    for i, (shx, shy) in enumerate(sh):
        sx, sy = sc[i] if i < len(sc) else (1.0, 1.0)
        out.append(_det_local(shx, shy, sx, sy))
    return out


def _uniform_ok(scale_pairs, tol=TOL_UNIFORM):
    """純函式:一組 (sx,sy) 是否**均勻**(每對 |sx−sy| ≤ tol)。對真實/合成負對照同判準。"""
    return bool(scale_pairs) and all(abs(sx - sy) <= tol for (sx, sy) in scale_pairs)


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb, twist_vol_conserve=True)
    twist_beats = _twist_beats(anims)
    R = {}

    # ---- VC1 present + dual-axis shear + scale channel emitted (crux) ----
    s1 = {"twist_beats": twist_beats, "not_finite": [], "no_bones": [], "no_dual": [],
          "peak_by_beat": {}}
    for tb in twist_beats:
        an = anims[tb]
        if not SA.all_finite(an):
            s1["not_finite"].append(tb)
        if not an.get("bones"):
            s1["no_bones"].append(tb)
        dual = {}
        for bn, ch in an.get("bones", {}).items():
            shxy = _shear_xy(ch); scxy = _scale_xy(ch)
            if not shxy or not scxy:
                continue
            shx_pk = max(abs(v) for v in _shear_x(ch))
            shy_pk = max(abs(v) for v in _shear_y(ch))
            sc_pk = max(max(sx, sy) for (sx, sy) in scxy)
            if shx_pk >= MIN_SHEAR and shy_pk >= MIN_SHEAR and sc_pk > 1.0 + MIN_SCALE_DEV:
                dual[bn] = {"shearX": round(shx_pk, 3), "shearY": round(shy_pk, 3),
                            "scale": round(sc_pk, 4)}
        if not dual:
            s1["no_dual"].append(tb)
        else:
            # 記一個代表 bone 的峰值
            s1["peak_by_beat"][tb] = next(iter(dual.values()))
    s1_pass = (bool(twist_beats) and not s1["not_finite"] and not s1["no_bones"]
               and not s1["no_dual"])
    R["VC1_present_dual_axis_scale"] = {**s1, "pass": s1_pass}

    # ---- VC2 volume conserved at every keyframe (crux) ----
    s2 = {"bad_det": [], "worst_by_bone": {}}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            if not _scale_xy(ch):
                continue
            dets = _bone_dets(ch)
            worst = max(abs(d - 1.0) for d in dets)
            key = "{}::{}".format(tb, bn)
            s2["worst_by_bone"][key] = round(worst, 6)
            if worst > TOL_DET:
                s2["bad_det"].append(key)
    s2_pass = (bool(s2["worst_by_bone"]) and not s2["bad_det"])
    R["VC2_volume_conserved"] = {**s2, "pass": s2_pass}

    # ---- VC3 uniform compensation + s>=1 + damped signature ----
    s3 = {"non_uniform": [], "scale_below_one": [], "scale_not_tracking": [],
          "few_sign_changes": [], "not_damped": []}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            scxy = _scale_xy(ch)
            if not scxy:
                continue
            key = "{}::{}".format(tb, bn)
            if not _uniform_ok(scxy):
                s3["non_uniform"].append(key)
            if any(sx < 1.0 - 1e-6 or sy < 1.0 - 1e-6 for (sx, sy) in scxy):
                s3["scale_below_one"].append(key)
            # scale 跟隨 shear:峰 scale 幀 == 峰 |shearY−shearX| 幀
            devs = [abs(shy - shx) for (shx, shy) in _shear_xy(ch)]
            scs = [max(sx, sy) for (sx, sy) in scxy]
            if devs and scs and int(np.argmax(scs)) != int(np.argmax(devs)):
                s3["scale_not_tracking"].append(key)
            # 兩 shear 軸各自阻尼振盪(復用 G-4' 判準)
            for axis, vals in (("x", _shear_x(ch)), ("y", _shear_y(ch))):
                if not vals:
                    continue
                if _sign_changes_zero(vals) < 3:
                    s3["few_sign_changes"].append("{}::{}".format(key, axis))
                if not _extrema_mags_decreasing(vals):
                    s3["not_damped"].append("{}::{}".format(key, axis))
    s3_pass = (not s3["non_uniform"] and not s3["scale_below_one"]
               and not s3["scale_not_tracking"] and not s3["few_sign_changes"]
               and not s3["not_damped"])
    R["VC3_uniform_compensation"] = {**s3, "pass": s3_pass}

    # ---- VC4 identity interface ----
    s4 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_off": []}
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
            sc = _scale_xy(ch)
            if sc and (abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6
                       or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6):
                s4["scale_endpoints_off"].append("{}::{}".format(tb, bn))
    R["VC4_identity_interface"] = {**s4, "pass": (not s4["bad_interface"]
                                                 and not s4["shear_endpoints_nonzero"]
                                                 and not s4["scale_endpoints_off"])}

    # ---- VC5 end-to-end general-affine pivot-fixed (shear+shearY+uniform scale) ----
    import build_spine
    out = "/tmp/twist_vol_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True,
                             twist_vol_conserve=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    s5 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0}
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
    s5_pass = (s5["n_joint_bones"] >= 1 and not s5["fail_fixed"] and not s5["fail_negctrl"])
    R["VC5_end2end_affine_pivot_fixed"] = {**s5, "pass": s5_pass}

    # ---- VC6 negative controls / isolation / additivity ----
    s6 = {}
    # (a) 非守恆守衛:base twist(vol_conserve=False)峰 det < 1−margin → VC2 對 base FALSE
    anims_base = G.build_animations(skel, sb)  # 預設 = 非守恆
    base_min_det = 1.0
    for tb in _twist_beats(anims_base):
        for bn, ch in anims_base[tb].get("bones", {}).items():
            if _shear_xy(ch):
                base_min_det = min(base_min_det, min(_bone_dets(ch)))
    s6["a_nonconserve_guard"] = {"base_min_det": round(base_min_det, 4),
                                 "pass": base_min_det <= 1.0 - NEG_DET_MARGIN}
    # (b) 非均勻守衛:squash 式非均勻對(scaleX≠scaleY)→ 均勻判準 FALSE
    squash_like = [(1.0, 1.0), (1.12, 1.0 / 1.12), (1.06, 1.0 / 1.06), (1.0, 1.0)]
    s6["b_nonuniform_guard"] = {"uniform_ok": _uniform_ok(squash_like),
                                "pass": not _uniform_ok(squash_like)}
    # (c) 向後相容/隔離/加性
    anims_off = G.build_animations(skel, sb, twist_vol_conserve=False)
    # c1: vol_conserve=False 逐位元同無旗標預設
    bc = [nm for nm in set(anims_off) | set(anims_base)
          if json.dumps(anims_off.get(nm), sort_keys=True) != json.dumps(anims_base.get(nm), sort_keys=True)]
    # c2: vol_conserve=True 下,非 twist beat 逐位元同 vol_conserve=False(旗標只作用 twist)
    non_twist_leak = []
    for nm, an in anims.items():
        if "__" in nm or G.beat_category(nm) == "twist":
            continue
        if json.dumps(an, sort_keys=True) != json.dumps(anims_off.get(nm), sort_keys=True):
            non_twist_leak.append(nm)
    # c3: 移除 twist storyboard → 其餘 beat 逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "twist"]}
    anims_no = G.build_animations(skel, sb_no, twist_vol_conserve=True)
    regressed = [nm for nm, an in anims_no.items()
                 if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True)]
    s6["c_backcompat_isolation_additive"] = {
        "vc_false_vs_default_diff": bc, "non_twist_leak": non_twist_leak,
        "removed_regressed": regressed,
        "pass": (not bc and not non_twist_leak and not regressed)}
    R["VC6_neg_control"] = {**s6, "pass": all(v["pass"] for v in s6.values())}

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
        for k in ["VC1_present_dual_axis_scale", "VC2_volume_conserved",
                  "VC3_uniform_compensation", "VC4_identity_interface",
                  "VC5_end2end_affine_pivot_fixed", "VC6_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("VC1 peaks by beat:", R["VC1_present_dual_axis_scale"]["peak_by_beat"])
        print("VC2 worst |det-1| by bone:", R["VC2_volume_conserved"]["worst_by_bone"])
        print("VC6a base twist min det (neg-ctrl):", R["VC6_neg_control"]["a_nonconserve_guard"]["base_min_det"])
        print("VC5 pivot-fixed (fixed/negctrl px):")
        for rec in R["VC5_end2end_affine_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
