#!/usr/bin/env python3
"""candidate G-4'''''' 自我驗收閘 — 生成器實際產出 `shearY` 通道(雙軸 shear)端到端(純 CPU)。

背景 honest boundary:G-4'(`gen_wobble`)讓產線第一次產 **shearX** 通道;G-4''''(`gen_squash`)加上
耦合非均勻 scale;但兩者都硬寫 `shearY == 0` —— shearY 通道(一般仿射 M 的最後一個未用自由度)
從未被任何生成器填過。本閘(G-4'''''')驗證那最後一段 shear honest boundary **已接上**:

  1. 生成器 `gen_twist`(斜拉對角絞擰)實際**產出 shearY 通道**(shearX 阻尼擺 + shearY=−shearX),經先驗庫直出;
  2. 該節拍做的是**真正非相似的一般仿射**(det=cos(2·shearX)<1,對角純剪切),非旋轉偽裝;
  3. `build_spine --shear-pivot` 帶 `include_shear=True` 對含 shearY 的變換**端到端補償**,件繞關節 pivot
     做一般仿射而 pivot 精確不動(`transform_matrix_full` 的 `ry=θ+90+shearY` 項與 `_world` 早已就緒)。

真值/fixture 同 (G-4'/G-4''''):從**先驗庫**(slot_bigwin,新增 twist beat)經 `analyze_target`
→ **真實 build_spine robot 骨架** → `build_animations` 端到端量。主秀運動無唯一正解(PROPOSAL 手感),
閘驗**客觀結構簽章 + 端到端不動點**,非美感;負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  V1 present + shearY 產出(crux) : twist beat 直出、finite、有 bone,且 ≥1 bone 帶 `shear` 通道
                                    且峰值 |shearY| ≥ MIN_SHEAR → **這是產線第一次填 shearY 通道**。
  V2 雙軸阻尼振盪                 : 每個 twist bone 的 shearX **與** shearY 序列各 —— (a)首尾==0;
                                    (b)繞 0 變號 ≥3;(c)相繼極值幅度嚴格遞減(阻尼);且 (d)shearY==−shearX 逐幀(反相)。
  V3 identity 介面(可插 Loop)   : sample(0)/sample(dur) rotate/translate/scale identity 且 shearX/shearY 首尾 0。
  V4 非相似一般仿射(crux)        : 峰值絞擰幀 det(M)=cos(shearX−shearY) 偏離 1 ≥ MIN_ANISO_DET
                                    ⇒ shearX≠shearY(**非旋轉**,真對角剪切),證填的 shearY 帶來真自由度。
  V5 端到端 pivot 不動           : `build_spine --shear-pivot`(真實 robot)產出 twist 帶補償;凡有關節 pivot 的
                                    bone,pivot 殘差 < TOL_FIX;內建負對照=未補償(繞件中心含雙軸 shear)大位移。
  V6 負對照/隔離                : (a)**旋轉偽裝**:同節拍但 shearY:=+shearX → M=R(φ),det≡1 → V4 非相似簽章 FALSE
                                    (證閘測的是真剪切非「有 shearY 即可」);(b)shearY 隔離:全 storyboard 僅 twist
                                    beat 帶非零 shearY,wobble/squash 等其餘 shear 節拍 shearY≡0;(c)加性:移除 twist 的
                                    storyboard,其餘 beat 逐位元不變(對既有節拍零回歸)。

用法:
  python3 validate_twist_gen.py            # 摘要
  python3 validate_twist_gen.py --json     # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim as SA
import gen_animations as G
from analyze_target import analyze
from pivot_rotation import transform_matrix_full
from validate_shear_pivot import _world   # 真實 Spine local(含 shearX/shearY)世界座標求值

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0        # 度,twist 峰值 |shearY| 下限(確認確實有明顯 shearY)
MIN_ANISO_DET = 0.05   # V4:峰值幀 |1−det| 下限(非相似=真對角剪切;旋轉 det≡1 → 0)
TOL_FIX = 0.5          # px,pivot 不動點殘差上限(同 G-4)
MIN_NEG = 5.0          # px,V5 負對照(未補償)位移下限
NEG_RATIO = 20.0       # 負對照/不動點 位移比下限


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/twist_gen_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _shear_xy(chans):
    """bone channels → (shearX 序列, shearY 序列)(無 shear 通道回 ([],[]))。"""
    fr = chans.get("shear")
    if not fr:
        return [], []
    return [f["x"] for f in fr], [f["y"] for f in fr]


def _sign_changes_zero(vals, dead=1e-6):
    sgn = [(1 if v > dead else (-1 if v < -dead else 0)) for v in vals]
    sgn = [s for s in sgn if s != 0]
    return sum(1 for i in range(1, len(sgn)) if sgn[i] != sgn[i - 1])


def _extrema_mags_decreasing(vals, dead=1e-6):
    nz = [abs(v) for v in vals if abs(v) > dead]
    if len(nz) < 2:
        return False
    return all(nz[i + 1] < nz[i] - 1e-9 for i in range(len(nz) - 1))


def _det_at(shx, shy):
    """真實 Spine local M=transform_matrix_full(0,1,1,shx,shy) 的 det = cos(shx−shy)。"""
    m = transform_matrix_full(0.0, 1.0, 1.0, shx, shy)
    return m[0] * m[3] - m[1] * m[2]


def _nonsimilarity_signature(shx_seq, shy_seq):
    """非相似(真對角剪切)簽章:某幀 |1−det| ≥ MIN_ANISO_DET 且峰值 |shearY| ≥ MIN_SHEAR。
    旋轉偽裝(shy==shx)→ det≡1 → max|1−det|=0 → False。回傳 (signature_bool, max_1mdet, peak_shy)。"""
    if not shy_seq:
        return False, 0.0, 0.0
    max_1md = max(abs(1.0 - _det_at(x, y)) for x, y in zip(shx_seq, shy_seq))
    peak_shy = max(abs(y) for y in shy_seq)
    return (max_1md >= MIN_ANISO_DET and peak_shy >= MIN_SHEAR), max_1md, peak_shy


def _twist_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "twist"]


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    twist_beats = _twist_beats(anims)
    R = {}

    # ---- V1 present + shearY emitted (crux) ----
    v1 = {"twist_beats": twist_beats, "missing_shear": [], "not_finite": [],
          "no_bones": [], "weak_sheary": [], "sheary_peak_by_beat": {}}
    for tb in twist_beats:
        an = anims[tb]
        if not SA.all_finite(an):
            v1["not_finite"].append(tb)
        if not an.get("bones"):
            v1["no_bones"].append(tb)
        sheared = {bn: _shear_xy(ch) for bn, ch in an.get("bones", {}).items() if _shear_xy(ch)[1]}
        if not sheared:
            v1["missing_shear"].append(tb); continue
        peak_y = max(max(abs(v) for v in sy) for (_sx, sy) in sheared.values())
        v1["sheary_peak_by_beat"][tb] = round(peak_y, 3)
        if peak_y < MIN_SHEAR:
            v1["weak_sheary"].append(tb)
    v1_pass = (bool(twist_beats) and not v1["missing_shear"] and not v1["not_finite"]
               and not v1["no_bones"] and not v1["weak_sheary"])
    R["V1_present_sheary_emitted"] = {**v1, "pass": v1_pass}

    # ---- V2 dual-axis damped oscillation (+ anti-phase) ----
    v2 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "not_antiphase": [], "detail": {}}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            sx, sy = _shear_xy(ch)
            if not sy:
                continue
            key = "{}::{}".format(tb, bn)
            for axis, seq in (("x", sx), ("y", sy)):
                ends_ok = abs(seq[0]) < 1e-6 and abs(seq[-1]) < 1e-6
                nsc = _sign_changes_zero(seq)
                damp = _extrema_mags_decreasing(seq)
                v2["detail"]["{}:{}".format(key, axis)] = {
                    "n_sign_changes": nsc, "damped": damp, "peaks": [round(v, 3) for v in seq]}
                if not ends_ok:
                    v2["bad_endpoints"].append("{}:{}".format(key, axis))
                if nsc < 3:
                    v2["few_sign_changes"].append("{}:{}".format(key, axis))
                if not damp:
                    v2["not_damped"].append("{}:{}".format(key, axis))
            # 反相:shearY == −shearX 逐幀
            if not all(abs(y + x) < 1e-4 for x, y in zip(sx, sy)):
                v2["not_antiphase"].append(key)
    v2_pass = (bool(v2["detail"]) and not v2["bad_endpoints"] and not v2["few_sign_changes"]
               and not v2["not_damped"] and not v2["not_antiphase"])
    R["V2_dual_axis_damped"] = {**v2, "pass": v2_pass}

    # ---- V3 identity interface ----
    v3 = {"bad_interface": [], "shear_endpoints_nonzero": []}
    for tb in twist_beats:
        an = anims[tb]
        dur = SA.duration(an)
        start = SA.sample(an, 0.0)["bones"]
        end = SA.sample(an, dur)["bones"]
        if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
            v3["bad_interface"].append(tb)
        for bn, ch in an.get("bones", {}).items():
            sx, sy = _shear_xy(ch)
            if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6 or abs(sy[0]) > 1e-6 or abs(sy[-1]) > 1e-6):
                v3["shear_endpoints_nonzero"].append("{}::{}".format(tb, bn))
    R["V3_identity_interface"] = {**v3, "pass": not v3["bad_interface"] and not v3["shear_endpoints_nonzero"]}

    # ---- V4 non-similarity general affine (crux) ----
    v4 = {"detail": {}, "fail_similar": []}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            sx, sy = _shear_xy(ch)
            if not sy:
                continue
            sig, max_1md, peak_y = _nonsimilarity_signature(sx, sy)
            v4["detail"]["{}::{}".format(tb, bn)] = {
                "max_1_minus_det": round(max_1md, 4), "peak_sheary": round(peak_y, 3), "nonsimilar": sig}
            if not sig:
                v4["fail_similar"].append("{}::{}".format(tb, bn))
    v4_pass = bool(v4["detail"]) and not v4["fail_similar"]
    R["V4_nonsimilarity_affine"] = {**v4, "pass": v4_pass}

    # ---- V5 end-to-end pivot-fixed via build_spine --shear-pivot ----
    import build_spine
    out = "/tmp/twist_gen_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    v5 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0}
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
            v5["n_joint_bones"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"bone": bn, "beat": tb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            v5["checked"].append(rec)
            if not (fix < TOL_FIX):
                v5["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                v5["fail_negctrl"].append(rec)
    v5_pass = (v5["n_joint_bones"] >= 1 and not v5["fail_fixed"] and not v5["fail_negctrl"])
    R["V5_end2end_pivot_fixed"] = {**v5, "pass": v5_pass}

    # ---- V6 negative controls / isolation ----
    v6 = {}
    # (a) 旋轉偽裝:同節拍但 shearY:=+shearX → M=R(φ),det≡1 → 非相似簽章 FALSE
    rot_disguise_true = []
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            sx, sy = _shear_xy(ch)
            if not sy:
                continue
            sig, max_1md, _ = _nonsimilarity_signature(sx, sx)   # shy := shx(旋轉偽裝)
            if sig:
                rot_disguise_true.append({"bone": "{}::{}".format(tb, bn),
                                          "max_1_minus_det": round(max_1md, 6)})
    v6["a_rotation_disguise_guard"] = {"nonsimilar_when_shy_eq_shx": rot_disguise_true,
                                       "pass": not rot_disguise_true}
    # (b) shearY 隔離:非 twist beat 皆 0 bone 帶非零 shearY(wobble/squash 等 shearY≡0)
    leak = []
    for nm, an in anims.items():
        if "__" in nm or G.beat_category(nm) == "twist":
            continue
        sheared_y = [bn for bn, ch in an.get("bones", {}).items()
                     if any(abs(y) > 1e-6 for y in _shear_xy(ch)[1])]
        if sheared_y:
            leak.append((nm, sheared_y))
    v6["b_sheary_isolated"] = {"leaked": leak, "pass": not leak}
    # (c) 加性:移除 twist 的 storyboard → 其餘 beat 逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "twist"]}
    anims_no = G.build_animations(skel, sb_no)
    regressed = []
    for nm, an in anims_no.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    v6["c_additive_no_regression"] = {"regressed": regressed,
                                      "removed_beats": [b["beat"] for b in sb["beats"]
                                                        if G.beat_category(b["beat"]) == "twist"],
                                      "pass": not regressed}
    R["V6_neg_control"] = {**v6, "pass": all(v["pass"] for v in v6.values())}

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
        for k in ["V1_present_sheary_emitted", "V2_dual_axis_damped", "V3_identity_interface",
                  "V4_nonsimilarity_affine", "V5_end2end_pivot_fixed", "V6_neg_control"]:
            print("{:28s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V1 shearY peak by beat:", R["V1_present_sheary_emitted"]["sheary_peak_by_beat"])
        print("V4 non-similarity (max|1-det|):",
              {k: v["max_1_minus_det"] for k, v in R["V4_nonsimilarity_affine"]["detail"].items()})
        print("V5 pivot-fixed (fixed/negctrl px):")
        for rec in R["V5_end2end_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
