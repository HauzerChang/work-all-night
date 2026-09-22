#!/usr/bin/env python3
"""candidate (G-4'''''') 自我驗收閘 — 生成器實際產出 **shearY** 通道(雙軸 shear)端到端(純 CPU)。

背景:wobble(G-4')與 squash(G-4'''')雖已把 **shearX** 通道接進產線,但兩者皆 `shearY≡0`
—— 這是 wobble/squash 系列一路留下的**最後一條 shear 通道 honest boundary**(見 STATE (G-4'''''')。
真實 Spine 3.8 local 2×2 的**第二個基向量**由 shearY 獨立傾斜(`transform_matrix_full`:
  b = cos(rot+90+shearY)·sy、d = sin(rot+90+shearY)·sy),與第一個基向量(受 shearX 傾斜)正交獨立。
本閘驗證那最後一段**已接上**:

  1. 生成器 `gen_twist`(斜拉扭轉)實際**產出 shearY 通道**(且非零),經先驗庫直出;
  2. shearX / shearY 是**兩個獨立自由度**(非比例、非同相)—— 平行四邊形的兩條邊各自傾斜,
     shear 方向隨時間旋轉(不是把單軸 shear 換個方向);
  3. `build_spine --shear-pivot`(include_shear=True)對含 shearY 的一般仿射**端到端補償**,件繞關節
     pivot 精確不動 —— 這是 `pivot_channels_affine` 第一次被**生成器產的 shearY≠0** 驅動。

真值/fixture 與 (E/H/I/J/G-4'/G-4'''') 一致:從**先驗庫**(slot_bigwin,新增 twist beat)經
`analyze_target` → **真實 build_spine robot 骨架** → `build_animations` 端到端量。主秀運動無唯一正解
(PROPOSAL 手感),閘驗**客觀結構簽章(雙軸阻尼 + 獨立性)+ 端到端不動點**,非美感;負對照證鑑別力。

AC(客觀、可量測):
  V1 present + shearY 產出(crux): twist beat 直出、finite、有 bone,且 ≥1 bone 帶 `shear` 通道,其
                                 峰 |shearX| ≥ MIN_SHEAR **且**峰 |shearY| ≥ MIN_SHEAR
                                 → **這是產線第一次產出 shearY≠0**(接上最後一條 shear 邊界)。
  V2 雙軸阻尼振盪               : 每個 twist bone 的 shearX **與** shearY 各自(取合併網格上的**轉折點**還原
                                 真實極值)—— (a)首尾 == 0;(b)繞 0 變號 ≥3;(c)相繼極值幅度嚴格遞減(阻尼)。
  V3 雙軸獨立(crux)           : (a) 非比例:shearY ≠ k·shearX(最小平方比例殘差比 ≥ MIN_RESID);
                                 (b) 正交:乘積 shearX·shearY 於密網格上繞 0 **變號 ≥ MIN_PRODSC**
                                 (正交 → 乘積振盪;比例 shy=k·shx → 乘積恆同號、0 次變號)。
  V4 identity 介面(可插 Loop) : sample(0)/sample(dur) 各 bone 皆 identity,且 shear 首尾 x==y==0。
  V5 端到端 pivot 不動         : `build_spine --shear-pivot`(真實 robot)產 twist 帶補償;凡有關節 pivot
                                 的 bone,pivot 殘差 < TOL_FIX;內建負對照 = 未補償(繞件中心含 shearY)大位移。
  V6 負對照/隔離               : (a)單軸(shearY≡0,=wobble)→ V1 shearY 產出 FALSE + V3 正交 FALSE;
                                 (b)比例(shy=k·shx,只是旋轉過的單軸 shear)→ V3 (a)(b) 皆 FALSE(證第二軸是獨立 DOF);
                                 (c)shear 隔離:非 SHEAR_CATS beat 皆 0 bone 帶 shear;
                                 (d)加性:移除 twist 的 storyboard → 其餘 beat 逐位元不變(對既有節拍零回歸)。

用法:
  python3 validate_twist_gen.py            # 摘要
  python3 validate_twist_gen.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
from validate_shear_pivot import _world               # 真實 Spine local(含 shear)世界座標求值
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0       # 度,兩軸峰值 |shear| 下限(確認確實有明顯雙軸 shear)
MIN_RESID = 0.3       # V3(a) 比例殘差比下限(twist ~0.72–0.82;比例 shy=k·shx → 0.0)
MIN_PRODSC = 4        # V3(b) 乘積繞 0 變號次數下限(twist ≥6;比例/單軸 → 0)
TOL_FIX = 0.5         # px,pivot 不動點殘差上限(同 G-4)
MIN_NEG = 5.0         # px,V5 負對照(未補償)位移下限
NEG_RATIO = 20.0      # 負對照/不動點 位移比下限
DENSE = 400           # V3 乘積取樣點數


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


def _shear_y(chans):
    """bone channels → shearY 關鍵幀值序列(無 shear 通道回 [])。"""
    fr = chans.get("shear")
    return [f.get("y", 0.0) for f in fr] if fr else []


def _turning_points(vals, dead=1e-6):
    """合併網格上還原**真實阻尼極值**:內部點 i 若 (v[i]−v[i−1]) 與 (v[i+1]−v[i]) 異號 → 轉折點。

    twist 的 shear timeline 是兩軸極值時刻的**聯集**(單一 Spine shear 通道每幀含 x,y),故單軸值序列
    含線性段上的內插點;取轉折點即還原該軸真實的阻尼極值序列(用於套 `_sign_changes_zero`/遞減判準)。"""
    tp = []
    n = len(vals)
    for i in range(1, n - 1):
        d0 = vals[i] - vals[i - 1]
        d1 = vals[i + 1] - vals[i]
        if (d0 > dead and d1 < -dead) or (d0 < -dead and d1 > dead):
            tp.append(vals[i])
    return tp


def _axis_signature(vals):
    """單軸阻尼振盪簽章:回傳 (ends_ok, n_sign_changes, damped, turning_points)。
    首尾 == 0;轉折點繞 0 變號 ≥3;轉折點幅度嚴格遞減(阻尼)。"""
    ends_ok = bool(vals) and abs(vals[0]) < 1e-6 and abs(vals[-1]) < 1e-6
    tp = _turning_points(vals)
    nsc = _sign_changes_zero(tp)
    damp = _extrema_mags_decreasing(tp)
    return ends_ok, nsc, damp, tp


def _sample_xy(shear_frames, t):
    d = SA._interp(shear_frames, t, ["x", "y"])
    return d["x"], d["y"]


def _prop_resid_ratio(x, y):
    """最小平方比例擬合 y≈k·x 的殘差比 = ‖y−k·x‖/‖y‖。比例(y=k·x)→0;正交/獨立→大。"""
    x = np.asarray(x, float); y = np.asarray(y, float)
    xx = float(np.dot(x, x))
    if xx <= 1e-12:
        return 0.0
    k = float(np.dot(x, y)) / xx
    denom = float(np.linalg.norm(y))
    if denom <= 1e-9:
        return 0.0
    return float(np.linalg.norm(y - k * x)) / denom


def _twist_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "twist"]


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    twist_beats = _twist_beats(anims)
    R = {}

    # ---- V1 present + shearY emitted (crux) ----
    v1 = {"twist_beats": twist_beats, "missing_shear": [], "not_finite": [], "no_bones": [],
          "weak_x": [], "weak_y": [], "peak_by_beat": {}}
    for tb in twist_beats:
        an = anims[tb]
        if not SA.all_finite(an):
            v1["not_finite"].append(tb)
        if not an.get("bones"):
            v1["no_bones"].append(tb)
        sheared = {bn: (_shear_x(ch), _shear_y(ch)) for bn, ch in an.get("bones", {}).items() if _shear_x(ch)}
        if not sheared:
            v1["missing_shear"].append(tb); continue
        peakx = max(max(abs(v) for v in sx) for sx, _ in sheared.values())
        peaky = max(max(abs(v) for v in sy) for _, sy in sheared.values())
        v1["peak_by_beat"][tb] = {"x": round(peakx, 3), "y": round(peaky, 3)}
        if peakx < MIN_SHEAR:
            v1["weak_x"].append(tb)
        if peaky < MIN_SHEAR:                # crux:shearY 必須非零(接上最後一條 shear 邊界)
            v1["weak_y"].append(tb)
    v1_pass = (bool(twist_beats) and not v1["missing_shear"] and not v1["not_finite"]
               and not v1["no_bones"] and not v1["weak_x"] and not v1["weak_y"])
    R["V1_present_shearY_emitted"] = {**v1, "pass": v1_pass}

    # ---- V2 biaxial damped-oscillation signature ----
    v2 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "detail": {}}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            sx, sy = _shear_x(ch), _shear_y(ch)
            if not sx:
                continue
            for axis, vals in (("x", sx), ("y", sy)):
                ends, nsc, damp, tp = _axis_signature(vals)
                key = "{}::{}::{}".format(tb, bn, axis)
                v2["detail"][key] = {"n_sign_changes": nsc, "damped": damp,
                                     "turning_points": [round(v, 3) for v in tp]}
                if not ends:
                    v2["bad_endpoints"].append(key)
                if nsc < 3:
                    v2["few_sign_changes"].append(key)
                if not damp:
                    v2["not_damped"].append(key)
    v2_pass = (bool(v2["detail"]) and not v2["bad_endpoints"]
               and not v2["few_sign_changes"] and not v2["not_damped"])
    R["V2_biaxial_damped"] = {**v2, "pass": v2_pass}

    # ---- V3 biaxial independence (crux): non-proportional + orthogonal ----
    v3 = {"low_resid": [], "few_prod_sign_changes": [], "detail": {}}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            fr = ch.get("shear")
            if not fr:
                continue
            t0, t1 = fr[0]["time"], fr[-1]["time"]
            ts = [t0 + (t1 - t0) * i / (DENSE - 1) for i in range(DENSE)]
            xs, ys = [], []
            for t in ts:
                vx, vy = _sample_xy(fr, t)
                xs.append(vx); ys.append(vy)
            resid = _prop_resid_ratio(xs, ys)
            prod = [xs[i] * ys[i] for i in range(len(ts))]
            psc = _sign_changes_zero(prod, dead=1e-4)
            key = "{}::{}".format(tb, bn)
            v3["detail"][key] = {"prop_resid_ratio": round(resid, 3), "prod_sign_changes": psc}
            if not (resid >= MIN_RESID):
                v3["low_resid"].append(key)
            if not (psc >= MIN_PRODSC):
                v3["few_prod_sign_changes"].append(key)
    v3_pass = (bool(v3["detail"]) and not v3["low_resid"] and not v3["few_prod_sign_changes"])
    R["V3_biaxial_independence"] = {**v3, "pass": v3_pass}

    # ---- V4 identity interface ----
    v4 = {"bad_interface": [], "shear_endpoints_nonzero": []}
    for tb in twist_beats:
        an = anims[tb]
        dur = SA.duration(an)
        start = SA.sample(an, 0.0)["bones"]
        end = SA.sample(an, dur)["bones"]
        if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
            v4["bad_interface"].append(tb)
        for bn, ch in an.get("bones", {}).items():
            sx, sy = _shear_x(ch), _shear_y(ch)
            if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6
                       or abs(sy[0]) > 1e-6 or abs(sy[-1]) > 1e-6):
                v4["shear_endpoints_nonzero"].append("{}::{}".format(tb, bn))
    R["V4_identity_interface"] = {**v4, "pass": not v4["bad_interface"] and not v4["shear_endpoints_nonzero"]}

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
            peaky = max(abs(f.get("y", 0.0)) for f in ch["shear"]) if ch.get("shear") else 0.0
            rec = {"bone": bn, "beat": tb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "peak_shearY": round(peaky, 2), "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            v5["checked"].append(rec)
            if not (fix < TOL_FIX):
                v5["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                v5["fail_negctrl"].append(rec)
    v5_pass = (v5["n_joint_bones"] >= 1 and not v5["fail_fixed"] and not v5["fail_negctrl"])
    R["V5_end2end_pivot_fixed"] = {**v5, "pass": v5_pass}

    # ---- V6 negative controls / isolation ----
    v6 = {}
    # 取一支真實 twist bone 的 shear 作為負對照素材
    ref = None
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            if ch.get("shear"):
                ref = ch["shear"]; break
        if ref:
            break
    dense_t = None
    if ref:
        t0, t1 = ref[0]["time"], ref[-1]["time"]
        dense_t = [t0 + (t1 - t0) * i / (DENSE - 1) for i in range(DENSE)]
    # (a) 單軸(shearY≡0,=wobble)→ shearY 峰 0(V1 FALSE)+ 乘積恆 0(V3 正交 FALSE)
    if ref and dense_t:
        xs = [_sample_xy(ref, t)[0] for t in dense_t]
        y0 = [0.0] * len(xs)
        peaky0 = max(abs(v) for v in y0)
        prod0 = [xs[i] * y0[i] for i in range(len(xs))]
        v6["a_single_axis_guard"] = {"peak_shearY": peaky0, "prod_sign_changes": _sign_changes_zero(prod0, 1e-4),
                                     "shearY_emitted": peaky0 >= MIN_SHEAR,
                                     "pass": (peaky0 < MIN_SHEAR) and (_sign_changes_zero(prod0, 1e-4) < MIN_PRODSC)}
    else:
        v6["a_single_axis_guard"] = {"pass": False, "reason": "no ref shear"}
    # (b) 比例(shy=k·shx)→ 殘差 0 + 乘積 0 次變號(證第二軸非獨立 → V3 FALSE)
    if ref and dense_t:
        xs = [_sample_xy(ref, t)[0] for t in dense_t]
        yk = [0.6 * v for v in xs]
        resid_k = _prop_resid_ratio(xs, yk)
        psc_k = _sign_changes_zero([xs[i] * yk[i] for i in range(len(xs))], 1e-4)
        v6["b_proportional_guard"] = {"prop_resid_ratio": round(resid_k, 4), "prod_sign_changes": psc_k,
                                      "independence_true": (resid_k >= MIN_RESID and psc_k >= MIN_PRODSC),
                                      "pass": not (resid_k >= MIN_RESID and psc_k >= MIN_PRODSC)}
    else:
        v6["b_proportional_guard"] = {"pass": False, "reason": "no ref shear"}
    # (c) shear 隔離:非 SHEAR_CATS beat 皆 0 bone 帶 shear
    leak = []
    for nm, an in anims.items():
        if "__" in nm or G.beat_category(nm) in TV.SHEAR_CATS:
            continue
        sheared = [bn for bn, ch in an.get("bones", {}).items() if _shear_x(ch)]
        if sheared:
            leak.append((nm, sheared))
    v6["c_shear_isolated"] = {"leaked": leak, "pass": not leak}
    # (d) 加性:移除 twist 的 storyboard → 其餘 beat 逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "twist"]}
    anims_no = G.build_animations(skel, sb_no)
    regressed = []
    for nm, an in anims_no.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    v6["d_additive_no_regression"] = {"regressed": regressed,
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
        for k in ["V1_present_shearY_emitted", "V2_biaxial_damped", "V3_biaxial_independence",
                  "V4_identity_interface", "V5_end2end_pivot_fixed", "V6_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V1 shear peak by beat (x,y):", R["V1_present_shearY_emitted"]["peak_by_beat"])
        print("V3 independence (resid/prodSC):",
              {k: v for k, v in R["V3_biaxial_independence"]["detail"].items()})
        print("V5 pivot-fixed (fixed/negctrl px):")
        for rec in R["V5_end2end_pivot_fixed"]["checked"]:
            print("  {:12s} arm {:6.1f}  peakShY {:5.2f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["peak_shearY"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
