#!/usr/bin/env python3
"""candidate G-4'''' 自我驗收閘 — 生成器產出**耦合的 shear + 非均勻 scale**(體積守恆 squash)端到端(純 CPU)。

一路的 honest boundary:G-4(`validate_shear_pivot.py`)補齊「件繞關節 pivot 的**一般仿射**(含 shear
**且**非均勻 scale sx≠sy)」的公式/閘,但 AC4/AC7 的非均勻 scale 只用**合成**值驗管路;G-4'
(`validate_shear_gen.py`)的 wobble 只產**純 shearX**(scaleX≡scaleY≡1)。本閘(G-4'''')驗證最後一段
**已接上**:生成器 `gen_squash`(斜拉果凍擠壓)實際產出**耦合的 shear + 非均勻 scale** —— 斜拉的同時
拉一軸、壓一軸使**面積守恆**(scaleX·scaleY==1),經先驗庫直出;`build_spine --shear-pivot`
(include_shear=True 隱含 include_scale)端到端把 rotate/scale/**shear** 三通道一起繞關節 pivot 補償
→ 件做**真正的一般仿射**(非相似)變換而 pivot 精確不動(G-4 通用 Δ=(M−I)(O−P) 第一次被**生成器產的**
非均勻 scale + shear 同時驅動)。

真值/fixture 與 (E/H/I/J/G-4') 一致:從**先驗庫**(slot_bigwin,新增 squash beat)經 `analyze_target`
→ **真實 build_spine robot 骨架** → `build_animations` 端到端量。主秀運動無唯一正解(PROPOSAL 手感),
閘驗**客觀結構簽章(阻尼振盪 + 體積守恆耦合)+ 端到端不動點**,非美感;負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  SQ1 present + dual-channel(crux): squash beat 直出、finite、有 bone,且 ≥1 bone **同時**帶 `shear`
                                    與 `scale` 通道;shearX 峰 ≥ MIN_SHEAR **且** scale 最大非均勻
                                    |scaleX−scaleY| ≥ MIN_ANISO → **產線第一次產出耦合 shear+非均勻 scale**。
  SQ2 shear 阻尼振盪               : 每個 squash bone 的 shearX(同 wobble):(a)首尾 0;(b)繞 0 變號 ≥3;
                                    (c)相繼極值幅度嚴格遞減(阻尼)—— 復用 G-4' 判準,與 shear-gen 閘一致。
  SQ3 體積守恆 squash 耦合(crux) : 每個 squash bone 的**每個** shear 極值幀:(a)scaleX·scaleY≈1
                                    (|積−1|≤TOL_VOL,面積守恆);(b)至少一極值 |scaleX−scaleY|≥MIN_ANISO
                                    (真擠壓=非均勻,非等比 pulse);(c)squash 幅度 |scaleX−1| 隨極值
                                    **嚴格遞減**(與 shear 同源同阻尼 → 耦合)。
  SQ4 identity 介面(可插 Loop)   : sample(0)/sample(dur) 各 bone identity,且 shear 首尾 0 + scale 首尾 (1,1)。
  SQ5 端到端一般仿射 pivot 不動    : `build_spine --shear-pivot`(真實 robot)產出 squash 帶補償;凡有關節
                                    pivot 的 bone,pivot 殘差 < TOL_FIX;內建負對照 = 未補償(繞件中心,含
                                    shear+非均勻 scale)大位移 → 證補償真的把非相似變換也錨在 pivot。
  SQ6 負對照/隔離                 : (a)**等比 scale 守衛**:合成 scaleX==scaleY(pulse)→ SQ3 非均勻 FALSE
                                    (證閘測「真擠壓」非「有 scale 即可」);(b)**非守恆守衛**:合成非均勻但
                                    scaleX·scaleY≠1(兩軸皆拉長)→ SQ3 體積守恆 FALSE(證(a)(b)彼此獨立);
                                    (c)**耦合隔離**:非 squash beat 皆非「同時帶 shear 且非均勻 scale」
                                    (wobble 有 shear 無 scale、其餘主秀有等比 scale 無 shear → squash 獨佔耦合);
                                    (d)**加性**:移除 squash 的 storyboard → 其餘 beat 逐位元不變(零回歸)。

用法:
  python3 validate_squash_gen.py            # 摘要
  python3 validate_squash_gen.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
# 復用 G-4' 的 shear 讀取與阻尼簽章判準,確保與 shear-gen / wobble-tier / wobble-count 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_shear_pivot import _world   # 真實 Spine local(含 shear + 非均勻 scale)世界座標求值

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,squash 峰值 |shearX| 下限
MIN_ANISO = 0.05    # scale 非均勻 |scaleX−scaleY| 峰下限(head 峰≈0.19 → 充足餘裕)
TOL_VOL = 0.02      # 體積守恆 |scaleX·scaleY − 1| 上限(實測 <5e-5 → 巨大餘裕)
TOL_FIX = 0.5       # px,pivot 不動點殘差上限(同 G-4/G-4')
MIN_NEG = 5.0       # px,SQ5 負對照(未補償)位移下限
NEG_RATIO = 20.0    # 負對照/不動點 位移比下限


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/squash_gen_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _squash_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "squash"]


def _scale_xy(chans):
    """bone channels → [(scaleX, scaleY)] 關鍵幀序列(無 scale 通道回 [])。"""
    fr = chans.get("scale")
    return [(f["x"], f["y"]) for f in fr] if fr else []


def _interior_scale(chans):
    """squash 的 scale 極值幀(去掉首尾 identity 端點)。首尾為 (1,1) → 內部即各 shear 極值時刻的 squash。"""
    xy = _scale_xy(chans)
    return xy[1:-1] if len(xy) >= 3 else []


def _sq3_eval(interior):
    """給一組內部 squash 極值 [(sx,sy)] → (volume_ok, aniso_ok, damped_ok, detail)。
    純函式 → 可對真實 squash 與合成負對照施同一判準(閘可信)。"""
    if not interior:
        return False, False, False, {"prod": [], "aniso": [], "mag": []}
    prod = [sx * sy for (sx, sy) in interior]
    aniso = [abs(sx - sy) for (sx, sy) in interior]
    mag = [abs(sx - 1.0) for (sx, sy) in interior]
    volume_ok = all(abs(p - 1.0) <= TOL_VOL for p in prod)
    aniso_ok = max(aniso) >= MIN_ANISO
    damped_ok = len(mag) >= 2 and all(mag[i + 1] < mag[i] - 1e-9 for i in range(len(mag) - 1))
    detail = {"prod": [round(p, 5) for p in prod], "aniso": [round(a, 4) for a in aniso],
              "mag": [round(m, 4) for m in mag]}
    return volume_ok, aniso_ok, damped_ok, detail


def _has_aniso_scale(chans):
    return any(abs(sx - sy) > MIN_ANISO for (sx, sy) in _scale_xy(chans))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    squash_beats = _squash_beats(anims)
    R = {}

    # ---- SQ1 present + dual-channel emitted (crux) ----
    s1 = {"squash_beats": squash_beats, "not_finite": [], "no_bones": [], "no_dual": [],
          "weak_shear": [], "weak_aniso": [], "peak_by_beat": {}}
    for qb in squash_beats:
        an = anims[qb]
        if not SA.all_finite(an):
            s1["not_finite"].append(qb)
        if not an.get("bones"):
            s1["no_bones"].append(qb)
        dual = {bn: ch for bn, ch in an.get("bones", {}).items() if _shear_x(ch) and _scale_xy(ch)}
        if not dual:
            s1["no_dual"].append(qb); continue
        shpk = max(max(abs(v) for v in _shear_x(ch)) for ch in dual.values())
        anpk = max(max(abs(sx - sy) for (sx, sy) in _scale_xy(ch)) for ch in dual.values())
        s1["peak_by_beat"][qb] = {"shear": round(shpk, 3), "aniso": round(anpk, 4)}
        if shpk < MIN_SHEAR:
            s1["weak_shear"].append(qb)
        if anpk < MIN_ANISO:
            s1["weak_aniso"].append(qb)
    s1_pass = (bool(squash_beats) and not s1["not_finite"] and not s1["no_bones"]
               and not s1["no_dual"] and not s1["weak_shear"] and not s1["weak_aniso"])
    R["SQ1_present_dual_channel"] = {**s1, "pass": s1_pass}

    # ---- SQ2 shear damped-oscillation (reuse G-4' criteria) ----
    s2 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "detail": {}}
    for qb in squash_beats:
        for bn, ch in anims[qb].get("bones", {}).items():
            sx = _shear_x(ch)
            if not sx:
                continue
            key = "{}::{}".format(qb, bn)
            ends_ok = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
            nsc = _sign_changes_zero(sx)
            damp = _extrema_mags_decreasing(sx)
            s2["detail"][key] = {"n_sign_changes": nsc, "damped": damp}
            if not ends_ok:
                s2["bad_endpoints"].append(key)
            if nsc < 3:
                s2["few_sign_changes"].append(key)
            if not damp:
                s2["not_damped"].append(key)
    s2_pass = (bool(s2["detail"]) and not s2["bad_endpoints"]
               and not s2["few_sign_changes"] and not s2["not_damped"])
    R["SQ2_shear_damped_oscillation"] = {**s2, "pass": s2_pass}

    # ---- SQ3 volume-preserving squash coupling (crux) ----
    s3 = {"bad_volume": [], "no_aniso": [], "not_damped": [], "detail": {}}
    for qb in squash_beats:
        for bn, ch in anims[qb].get("bones", {}).items():
            interior = _interior_scale(ch)
            if not interior or not _shear_x(ch):
                continue
            key = "{}::{}".format(qb, bn)
            vok, aok, dok, det = _sq3_eval(interior)
            s3["detail"][key] = det
            if not vok:
                s3["bad_volume"].append(key)
            if not aok:
                s3["no_aniso"].append(key)
            if not dok:
                s3["not_damped"].append(key)
    s3_pass = (bool(s3["detail"]) and not s3["bad_volume"] and not s3["no_aniso"] and not s3["not_damped"])
    R["SQ3_volume_preserving_coupling"] = {**s3, "pass": s3_pass}

    # ---- SQ4 identity interface ----
    s4 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for qb in squash_beats:
        an = anims[qb]
        dur = SA.duration(an)
        start = SA.sample(an, 0.0)["bones"]
        end = SA.sample(an, dur)["bones"]
        if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
            s4["bad_interface"].append(qb)
        for bn, ch in an.get("bones", {}).items():
            sx = _shear_x(ch)
            if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                s4["shear_endpoints_nonzero"].append("{}::{}".format(qb, bn))
            xy = _scale_xy(ch)
            if xy and (abs(xy[0][0] - 1.0) > 1e-6 or abs(xy[0][1] - 1.0) > 1e-6
                       or abs(xy[-1][0] - 1.0) > 1e-6 or abs(xy[-1][1] - 1.0) > 1e-6):
                s4["scale_endpoints_nonident"].append("{}::{}".format(qb, bn))
    R["SQ4_identity_interface"] = {**s4, "pass": (not s4["bad_interface"]
                                                  and not s4["shear_endpoints_nonzero"]
                                                  and not s4["scale_endpoints_nonident"])}

    # ---- SQ5 end-to-end general-affine pivot-fixed via build_spine --shear-pivot ----
    import build_spine
    out = "/tmp/squash_gen_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    s5 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0}
    for qb in _squash_beats(sp_skel["animations"]):
        an = sp_skel["animations"][qb]
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
            # 內建負對照:未補償(繞件中心)—— 同 shear+非均勻 scale 但無 translate
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"bone": bn, "beat": qb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            s5["checked"].append(rec)
            if not (fix < TOL_FIX):
                s5["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                s5["fail_negctrl"].append(rec)
    s5_pass = (s5["n_joint_bones"] >= 1 and not s5["fail_fixed"] and not s5["fail_negctrl"])
    R["SQ5_end2end_affine_pivot_fixed"] = {**s5, "pass": s5_pass}

    # ---- SQ6 negative controls / isolation ----
    s6 = {}
    # (a) 等比 scale 守衛:scaleX==scaleY(pulse)→ 非均勻 FALSE(aniso 判準應 FALSE)
    uni = [(1.14, 1.14), (1.07, 1.07), (1.035, 1.035), (1.0175, 1.0175)]
    v_u, a_u, d_u = _sq3_eval(uni)[:3]
    s6["a_uniform_scale_guard"] = {"aniso_ok": a_u, "pass": not a_u}
    # (b) 非守恆守衛:非均勻但兩軸皆拉長 → scaleX·scaleY≠1(volume 判準應 FALSE),aniso 仍 TRUE
    nonvol = [(1.14, 1.07), (1.07, 1.035), (1.035, 1.0175), (1.0175, 1.009)]
    v_nv, a_nv, d_nv = _sq3_eval(nonvol)[:3]
    s6["b_nonvolume_guard"] = {"volume_ok": v_nv, "aniso_ok": a_nv,
                               "pass": (not v_nv) and a_nv}
    # (c) 耦合隔離:非 squash beat 皆非「同時帶 shear 且非均勻 scale」
    leak = []
    for nm, an in anims.items():
        if "__" in nm or G.beat_category(nm) == "squash":
            continue
        for bn, ch in an.get("bones", {}).items():
            if _shear_x(ch) and _has_aniso_scale(ch):
                leak.append((nm, bn))
    s6["c_coupling_isolated"] = {"leaked": leak, "pass": not leak}
    # (d) 加性:移除 squash 的 storyboard → 其餘 beat 逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "squash"]}
    anims_no = G.build_animations(skel, sb_no)
    regressed = []
    for nm, an in anims_no.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    s6["d_additive_no_regression"] = {"regressed": regressed,
                                      "removed_beats": [b["beat"] for b in sb["beats"]
                                                        if G.beat_category(b["beat"]) == "squash"],
                                      "pass": not regressed}
    R["SQ6_neg_control"] = {**s6, "pass": all(v["pass"] for v in s6.values())}

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
        for k in ["SQ1_present_dual_channel", "SQ2_shear_damped_oscillation",
                  "SQ3_volume_preserving_coupling", "SQ4_identity_interface",
                  "SQ5_end2end_affine_pivot_fixed", "SQ6_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("SQ1 peaks by beat:", R["SQ1_present_dual_channel"]["peak_by_beat"])
        print("SQ3 detail:", json.dumps(R["SQ3_volume_preserving_coupling"]["detail"], ensure_ascii=False))
        print("SQ5 pivot-fixed (fixed/negctrl px):")
        for rec in R["SQ5_end2end_affine_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
