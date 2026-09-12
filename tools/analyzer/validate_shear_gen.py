#!/usr/bin/env python3
"""candidate G-4' 自我驗收閘 — 生成器實際產出 `shear` 通道端到端(純 CPU)。

G-4(`validate_shear_pivot.py`)補齊了「件繞關節 pivot 的**一般仿射**(含 shear/非均勻 scale)」的
**公式 + 閘**(`transform_matrix_full`/`pivot_channels_affine`/`apply_pivots(include_shear=True)`),
但當時的 honest boundary:**沒有任何 beat 生成器產出 shear 通道**(產線主秀只用 rotate/scale),
AC7 只用**合成** shear 驗過管路。本閘(G-4')驗證那最後一段**已接上**:

  1. 生成器 `gen_wobble`(斜拉 jelly wobble)實際**產出 shear 通道**,經先驗庫直出;
  2. `build_spine --shear-pivot` 帶 `include_shear=True` 對該 shear **端到端補償**,件繞關節 pivot
     做一般仿射變換而 pivot 精確不動。

真值/fixture 與 (E/H/I/J) 一致:從**先驗庫**(slot_bigwin,新增 wobble beat)經 `analyze_target`
→ **真實 build_spine robot 骨架** → `build_animations` 端到端量。主秀運動無唯一正解(PROPOSAL 手感),
閘驗**客觀結構簽章(阻尼振盪)+ 端到端不動點**,非美感;負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  W1 present + shear 產出(crux): wobble beat 直出、finite、有 bone,且 ≥1 bone 帶 `shear` 通道
                                 且峰值 |shearX| ≥ MIN_SHEAR → **這是產線第一次產出 shear**(接上 G-4 邊界)。
  W2 阻尼振盪簽章             : 每個 wobble bone 的 shearX 序列 —— (a)首尾 == 0;(b)繞 0 變號 ≥3(振盪+回穩);
                                 (c)相繼極值幅度**嚴格遞減**(阻尼)。
  W3 identity 介面(可插 Loop): sample(0)/sample(dur) 各 bone rotate/translate/scale 皆 identity
                                 且 shear 首尾 0 → 與 In/Loop/Out 無縫串接。
  W4 端到端 pivot 不動        : `build_spine --shear-pivot`(真實 robot)產出 wobble 帶補償;凡有關節 pivot
                                 的 bone,pivot 殘差 < TOL_FIX;內建負對照 = 未補償(繞件中心含 shear)pivot 大位移。
  W5 負對照/隔離             : (a)天真單調 shear(0→A→hold)→ W2 阻尼簽章 FALSE(證閘測阻尼振盪非「有 shear 即可」);
                                 (b)shear 隔離:全 storyboard 僅 wobble beat 帶 shear,其餘 beat 皆 0 bone 帶 shear;
                                 (c)加性:移除 wobble 的 storyboard,其餘 beat 的 anim 逐位元不變(對既有節拍零回歸)。

用法:
  python3 validate_shear_gen.py            # 摘要
  python3 validate_shear_gen.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim as SA
import gen_animations as G
from analyze_target import analyze
from validate_shear_pivot import _world   # 真實 Spine local(含 shear)世界座標求值

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,wobble 峰值 |shearX| 下限(確認確實有明顯 shear)
TOL_FIX = 0.5       # px,pivot 不動點殘差上限(同 G-4)
MIN_NEG = 5.0       # px,W4 負對照(未補償)位移下限
NEG_RATIO = 20.0    # 負對照/不動點 位移比下限


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/shear_gen_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _shear_x(chans):
    """bone channels → shearX 關鍵幀值序列(無 shear 通道回 [])。"""
    fr = chans.get("shear")
    return [f["x"] for f in fr] if fr else []


def _sign_changes_zero(vals, dead=1e-6):
    """繞 0 的變號次數(忽略 |v|<dead 的近零項)。"""
    sgn = [(1 if v > dead else (-1 if v < -dead else 0)) for v in vals]
    sgn = [s for s in sgn if s != 0]
    return sum(1 for i in range(1, len(sgn)) if sgn[i] != sgn[i - 1])


def _extrema_mags_decreasing(vals, dead=1e-6):
    """相繼**局部極值**幅度是否嚴格遞減(阻尼)。取非零關鍵幀的 |v| 峰序列。"""
    nz = [abs(v) for v in vals if abs(v) > dead]
    if len(nz) < 2:
        return False
    return all(nz[i + 1] < nz[i] - 1e-9 for i in range(len(nz) - 1))


def _wobble_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "wobble"]


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    wobble_beats = _wobble_beats(anims)
    R = {}

    # ---- W1 present + shear emitted (crux) ----
    w1 = {"wobble_beats": wobble_beats, "missing_shear": [], "not_finite": [],
          "no_bones": [], "weak_peak": [], "peak_by_beat": {}}
    for wb in wobble_beats:
        an = anims[wb]
        if not SA.all_finite(an):
            w1["not_finite"].append(wb)
        if not an.get("bones"):
            w1["no_bones"].append(wb)
        sheared = {bn: _shear_x(ch) for bn, ch in an.get("bones", {}).items() if _shear_x(ch)}
        if not sheared:
            w1["missing_shear"].append(wb); continue
        peak = max(max(abs(v) for v in s) for s in sheared.values())
        w1["peak_by_beat"][wb] = round(peak, 3)
        if peak < MIN_SHEAR:
            w1["weak_peak"].append(wb)
    w1_pass = (bool(wobble_beats) and not w1["missing_shear"] and not w1["not_finite"]
               and not w1["no_bones"] and not w1["weak_peak"])
    R["W1_present_shear_emitted"] = {**w1, "pass": w1_pass}

    # ---- W2 damped-oscillation signature ----
    w2 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "detail": {}}
    for wb in wobble_beats:
        for bn, ch in anims[wb].get("bones", {}).items():
            sx = _shear_x(ch)
            if not sx:
                continue
            key = "{}::{}".format(wb, bn)
            ends_ok = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
            nsc = _sign_changes_zero(sx)
            damp = _extrema_mags_decreasing(sx)
            w2["detail"][key] = {"n_sign_changes": nsc, "damped": damp,
                                 "peaks": [round(v, 3) for v in sx]}
            if not ends_ok:
                w2["bad_endpoints"].append(key)
            if nsc < 3:
                w2["few_sign_changes"].append(key)
            if not damp:
                w2["not_damped"].append(key)
    w2_pass = (bool(w2["detail"]) and not w2["bad_endpoints"]
               and not w2["few_sign_changes"] and not w2["not_damped"])
    R["W2_damped_oscillation"] = {**w2, "pass": w2_pass}

    # ---- W3 identity interface (insertable between Loop) ----
    w3 = {"bad_interface": [], "shear_endpoints_nonzero": []}
    for wb in wobble_beats:
        an = anims[wb]
        dur = SA.duration(an)
        start = SA.sample(an, 0.0)["bones"]
        end = SA.sample(an, dur)["bones"]
        if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
            w3["bad_interface"].append(wb)
        for bn, ch in an.get("bones", {}).items():
            sx = _shear_x(ch)
            if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                w3["shear_endpoints_nonzero"].append("{}::{}".format(wb, bn))
    R["W3_identity_interface"] = {**w3, "pass": not w3["bad_interface"] and not w3["shear_endpoints_nonzero"]}

    # ---- W4 end-to-end pivot-fixed via build_spine --shear-pivot ----
    import build_spine
    out = "/tmp/shear_gen_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    w4 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0}
    for wb in _wobble_beats(sp_skel["animations"]):
        an = sp_skel["animations"][wb]
        for bn, ch in an.get("bones", {}).items():
            if bn not in joints or bn not in centers:
                continue
            O = np.array(centers[bn], float); P = np.array(joints[bn], float)
            ellP = P - O
            tr = ch.get("translate")
            if not tr:
                continue
            w4["n_joint_bones"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            # 內建負對照:未補償(繞件中心)—— 用同 shear 但無 translate
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"bone": bn, "beat": wb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            w4["checked"].append(rec)
            if not (fix < TOL_FIX):
                w4["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                w4["fail_negctrl"].append(rec)
    w4_pass = (w4["n_joint_bones"] >= 1 and not w4["fail_fixed"] and not w4["fail_negctrl"])
    R["W4_end2end_pivot_fixed"] = {**w4, "pass": w4_pass}

    # ---- W5 negative controls / isolation ----
    w5 = {}
    # (a) 天真單調 shear(0→A→hold)→ 阻尼振盪簽章 FALSE
    naive = [0.0, 16.0, 16.0]
    naive_ok = (_sign_changes_zero(naive) >= 3 and _extrema_mags_decreasing(naive))
    w5["a_naive_shear_guard"] = {"naive_peaks": naive, "sign_changes": _sign_changes_zero(naive),
                                 "damped": _extrema_mags_decreasing(naive),
                                 "signature_true": naive_ok, "pass": not naive_ok}
    # (b) shear 隔離:非 shear-emitter beat 皆 0 bone 帶 shear
    #     (G-4'''':shear 產出者集合擴為 {wobble, squash};squash 亦合法產 shear,以 SHEAR_CATS 認定)
    import tier_variants as _TV
    leak = []
    for nm, an in anims.items():
        if "__" in nm or G.beat_category(nm) in _TV.SHEAR_CATS:
            continue
        sheared = [bn for bn, ch in an.get("bones", {}).items() if _shear_x(ch)]
        if sheared:
            leak.append((nm, sheared))
    w5["b_shear_isolated"] = {"leaked": leak, "pass": not leak}
    # (c) 加性:移除 wobble 的 storyboard → 其餘 beat 逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "wobble"]}
    anims_no = G.build_animations(skel, sb_no)
    regressed = []
    for nm, an in anims_no.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    w5["c_additive_no_regression"] = {"regressed": regressed,
                                      "removed_beats": [b["beat"] for b in sb["beats"]
                                                        if G.beat_category(b["beat"]) == "wobble"],
                                      "pass": not regressed}
    R["W5_neg_control"] = {**w5, "pass": all(v["pass"] for v in w5.values())}

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
        for k in ["W1_present_shear_emitted", "W2_damped_oscillation", "W3_identity_interface",
                  "W4_end2end_pivot_fixed", "W5_neg_control"]:
            print("{:28s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("W1 shear peak by beat:", R["W1_present_shear_emitted"]["peak_by_beat"])
        print("W4 pivot-fixed (fixed/negctrl px):")
        for rec in R["W4_end2end_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
