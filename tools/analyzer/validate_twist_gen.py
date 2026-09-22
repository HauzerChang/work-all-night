#!/usr/bin/env python3
"""candidate G-4'''''' 自我驗收閘 — 生成器實際產出 `shearY` 通道(雙軸 shear 正交扭,純 CPU)。

補上 wobble(G-4',純 shearX)/ squash(G-4'''',shearX+耦合非均勻 scale)一路留到現在的**最後一條
shear honest boundary** —— 一般仿射的公式/閘早就吃 shearY(`transform_matrix_full` 的
`b=cos(θ+90+shy)·sy`、`d=sin(θ+90+shy)·sy`;`pivot_channels_affine`/`_world` 亦讀 `shy`),但當時
**沒有任何生成器產 shearY**(所有 beat 皆 shearY≡0)。本閘(G-4'''''')驗證那最後一段**已接上**:

  1. 生成器 `gen_twist`(斜扭果凍)實際**產出雙軸 shear(shearX **且** shearY)**,經先驗庫直出;
  2. 兩軸相位錯開 90°(正交):shearX 峰時 shearY≈0、反之亦然(區隔「真扭」與「同相退化雙通道」);
  3. `build_spine --shear-pivot` 帶 `include_shear=True` 對**含 shearY** 的一般仿射端到端補償,件繞
     關節 pivot 精確不動 → 證 `transform_matrix_full` 的 shearY 項第一次被生成器產的值端到端驅動。

真值/fixture 與 (G-4'/G-4'''') 一致:從**先驗庫**(slot_bigwin,新增 twist beat)經 `analyze_target`
→ **真實 build_spine robot 骨架** → `build_animations` 端到端量。主秀運動無唯一正解(PROPOSAL 手感),
閘驗**客觀結構簽章(雙軸阻尼振盪 + 正交相位)+ 端到端不動點**,非美感;負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  TW1 present + 雙軸 shear 產出(crux): twist beat 直出、finite、有 bone,且 ≥1 bone 帶 `shear` 通道
                                        且峰 |shearX| ≥ MIN_SHEAR **且**峰 |shearY| ≥ MIN_SHEAR
                                        → **這是產線第一次產 shearY**(接上最後一條 shear 邊界)。
  TW2 雙軸阻尼振盪簽章               : 每個 twist bone 的 shearX **與** shearY 序列各自 —— (a)首尾==0;
                                        (b)繞 0 變號 ≥3(振盪+回穩);(c)相繼極值幅度**嚴格遞減**(阻尼)。
  TW3 正交相位(crux)               : shearX 全域峰時刻 |shearY| ≤ QUAD_TOL·峰shearY;shearY 全域峰時刻
                                        |shearX| ≤ QUAD_TOL·峰shearX → 兩軸相位錯開(真扭,非同相斜拉)。
  TW4 identity 介面(可插 Loop)     : sample(0)/sample(dur) 各 bone 皆 identity 且 shearX/shearY 首尾 0。
  TW5 端到端 pivot 不動(含 shearY) : `build_spine --shear-pivot`(真實 robot)產出 twist 帶補償;凡有關節
                                        pivot 的 bone pivot 殘差 < TOL_FIX;內建負對照=未補償(繞件中心含
                                        雙軸 shear)pivot 大位移 → 證 shearY 項端到端被正確補償。
  TW6 負對照/隔離                    : (a)純 shearX(shearY≡0,同 wobble)→ TW1 雙軸 crux FALSE(證閘測的是
                                        真 shearY 非「有 shear 即可」);(b)同相 shear(shearY==shearX)→ TW3
                                        正交 FALSE(證閘測相位錯開非「有第二通道即可」);(c)shear 隔離:
                                        非 SHEAR_CATS beat 皆 0 bone 帶 shear;(d)加性:移除 twist storyboard
                                        → 其餘 beat 逐位元不變。

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
import beat_templates as BT
from analyze_target import analyze
from validate_shear_pivot import _world   # 真實 Spine local(含 shearX/shearY)世界座標求值

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,twist 峰值 |shearX|、|shearY| 各自下限(確認雙軸皆有明顯 shear)
QUAD_TOL = 0.25     # 正交比上限:一軸全域峰時,另一軸 |值|/自身峰 ≤ 此值(真扭≈0、同相=1.0)
TOL_FIX = 0.5       # px,pivot 不動點殘差上限(同 G-4)
MIN_NEG = 5.0       # px,TW5 負對照(未補償)位移下限
NEG_RATIO = 20.0    # 負對照/不動點 位移比下限


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


def _shear_axis(chans, axis):
    """bone channels → shear 指定軸('x' or 'y')關鍵幀 (time, val) 序列(無 shear 通道回 [])。"""
    fr = chans.get("shear")
    return [(f["time"], f[axis]) for f in fr] if fr else []


def _sign_changes_zero(vals, dead=1e-6):
    """繞 0 的變號次數(忽略 |v|<dead 的近零項)。"""
    sgn = [(1 if v > dead else (-1 if v < -dead else 0)) for v in vals]
    sgn = [s for s in sgn if s != 0]
    return sum(1 for i in range(1, len(sgn)) if sgn[i] != sgn[i - 1])


def _extrema_mags_decreasing(vals, dead=1e-6):
    """相繼非零關鍵幀 |v| 峰序列是否嚴格遞減(阻尼)。"""
    nz = [abs(v) for v in vals if abs(v) > dead]
    if len(nz) < 2:
        return False
    return all(nz[i + 1] < nz[i] - 1e-9 for i in range(len(nz) - 1))


def _peak_and_time(pairs):
    """[(time, val)] → (峰值 |val| 最大者的 time, |val|)。空回 (None, 0)。"""
    if not pairs:
        return None, 0.0
    t, v = max(pairs, key=lambda tv: abs(tv[1]))
    return t, abs(v)


def _val_at(pairs, t):
    """在 (time,val) 關鍵幀上線性內插 t 的值。"""
    if not pairs:
        return 0.0
    if t <= pairs[0][0]:
        return pairs[0][1]
    if t >= pairs[-1][0]:
        return pairs[-1][1]
    for i in range(1, len(pairs)):
        if t <= pairs[i][0]:
            t0, v0 = pairs[i - 1]
            t1, v1 = pairs[i]
            a = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            return v0 + (v1 - v0) * a
    return pairs[-1][1]


def _twist_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "twist"]


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    twist_beats = _twist_beats(anims)
    R = {}

    # ---- TW1 present + dual-axis shear emitted (crux) ----
    t1 = {"twist_beats": twist_beats, "missing_shear": [], "not_finite": [],
          "no_bones": [], "weak_x": [], "weak_y": [], "peak_by_beat": {}}
    for tb in twist_beats:
        an = anims[tb]
        if not SA.all_finite(an):
            t1["not_finite"].append(tb)
        if not an.get("bones"):
            t1["no_bones"].append(tb)
        best_x = best_y = 0.0
        has_shear = False
        for bn, ch in an.get("bones", {}).items():
            sx = _shear_axis(ch, "x"); sy = _shear_axis(ch, "y")
            if not (sx or sy):
                continue
            has_shear = True
            best_x = max(best_x, max((abs(v) for _, v in sx), default=0.0))
            best_y = max(best_y, max((abs(v) for _, v in sy), default=0.0))
        if not has_shear:
            t1["missing_shear"].append(tb); continue
        t1["peak_by_beat"][tb] = {"x": round(best_x, 3), "y": round(best_y, 3)}
        if best_x < MIN_SHEAR:
            t1["weak_x"].append(tb)
        if best_y < MIN_SHEAR:     # crux:shearY 必須也明顯(這是產線第一次產 shearY)
            t1["weak_y"].append(tb)
    t1_pass = (bool(twist_beats) and not t1["missing_shear"] and not t1["not_finite"]
               and not t1["no_bones"] and not t1["weak_x"] and not t1["weak_y"])
    R["TW1_present_dual_shear"] = {**t1, "pass": t1_pass}

    # ---- TW2 damped-oscillation signature on BOTH axes ----
    t2 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "detail": {}}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            for axis in ("x", "y"):
                pairs = _shear_axis(ch, axis)
                if not pairs:
                    continue
                vals = [v for _, v in pairs]
                key = "{}::{}::{}".format(tb, bn, axis)
                ends_ok = abs(vals[0]) < 1e-6 and abs(vals[-1]) < 1e-6
                nsc = _sign_changes_zero(vals)
                damp = _extrema_mags_decreasing(vals)
                t2["detail"][key] = {"n_sign_changes": nsc, "damped": damp,
                                     "vals": [round(v, 3) for v in vals]}
                if not ends_ok:
                    t2["bad_endpoints"].append(key)
                if nsc < 3:
                    t2["few_sign_changes"].append(key)
                if not damp:
                    t2["not_damped"].append(key)
    t2_pass = (bool(t2["detail"]) and not t2["bad_endpoints"]
               and not t2["few_sign_changes"] and not t2["not_damped"])
    R["TW2_damped_oscillation_both"] = {**t2, "pass": t2_pass}

    # ---- TW3 quadrature / phase-offset (crux) ----
    t3 = {"detail": {}, "fail_quad": [], "n_checked": 0}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            sx = _shear_axis(ch, "x"); sy = _shear_axis(ch, "y")
            if not (sx and sy):
                continue
            tx, px = _peak_and_time(sx)      # shearX 峰時刻/峰值
            ty, py = _peak_and_time(sy)      # shearY 峰時刻/峰值
            if px <= 0 or py <= 0:
                continue
            y_at_xpeak = abs(_val_at(sy, tx))   # shearX 峰時的 shearY
            x_at_ypeak = abs(_val_at(sx, ty))   # shearY 峰時的 shearX
            rx = y_at_xpeak / py                # 應 ≈0(真扭);同相=1.0
            ry = x_at_ypeak / px
            key = "{}::{}".format(tb, bn)
            t3["n_checked"] += 1
            t3["detail"][key] = {"y_ratio_at_xpeak": round(rx, 4),
                                 "x_ratio_at_ypeak": round(ry, 4)}
            if not (rx <= QUAD_TOL and ry <= QUAD_TOL):
                t3["fail_quad"].append(key)
    t3_pass = (t3["n_checked"] >= 1 and not t3["fail_quad"])
    R["TW3_quadrature"] = {**t3, "pass": t3_pass}

    # ---- TW4 identity interface (insertable between Loop) ----
    t4 = {"bad_interface": [], "shear_endpoints_nonzero": []}
    for tb in twist_beats:
        an = anims[tb]
        dur = SA.duration(an)
        start = SA.sample(an, 0.0)["bones"]
        end = SA.sample(an, dur)["bones"]
        if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
            t4["bad_interface"].append(tb)
        for bn, ch in an.get("bones", {}).items():
            for axis in ("x", "y"):
                pairs = _shear_axis(ch, axis)
                if pairs and (abs(pairs[0][1]) > 1e-6 or abs(pairs[-1][1]) > 1e-6):
                    t4["shear_endpoints_nonzero"].append("{}::{}::{}".format(tb, bn, axis))
    R["TW4_identity_interface"] = {**t4, "pass": not t4["bad_interface"]
                                   and not t4["shear_endpoints_nonzero"]}

    # ---- TW5 end-to-end pivot-fixed (with shearY) via build_spine --shear-pivot ----
    import build_spine
    out = "/tmp/twist_gen_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    t5 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0, "max_shy": 0.0}
    for tb in _twist_beats(sp_skel["animations"]):
        an = sp_skel["animations"][tb]
        for bn, ch in an.get("bones", {}).items():
            if bn not in joints or bn not in centers:
                continue
            sh = ch.get("shear")
            tr = ch.get("translate")
            if not tr or not sh:
                continue
            shy_peak = max(abs(f.get("y", 0.0)) for f in sh)
            t5["max_shy"] = max(t5["max_shy"], shy_peak)
            O = np.array(centers[bn], float); P = np.array(joints[bn], float)
            ellP = P - O
            t5["n_joint_bones"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  sh, tr, t) - P)) for t in ts)
            # 內建負對照:未補償(繞件中心)—— 同雙軸 shear 但無 translate
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  sh, None, t) - P)) for t in ts)
            rec = {"bone": bn, "beat": tb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "shy_peak": round(shy_peak, 3), "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            t5["checked"].append(rec)
            if not (fix < TOL_FIX):
                t5["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                t5["fail_negctrl"].append(rec)
    t5_pass = (t5["n_joint_bones"] >= 1 and t5["max_shy"] >= MIN_SHEAR
               and not t5["fail_fixed"] and not t5["fail_negctrl"])
    R["TW5_end2end_pivot_fixed"] = {**t5, "max_shy": round(t5["max_shy"], 3), "pass": t5_pass}

    # ---- TW6 negative controls / isolation ----
    t6 = {}
    # (a) 純 shearX(shearY≡0,同 wobble)→ 雙軸 crux FALSE(峰 shearY==0 < MIN_SHEAR)
    bx, _ = BT.gen_wobble("body")
    wob_y = max((abs(f.get("y", 0.0)) for f in bx.get("shear", [])), default=0.0)
    a_dual = wob_y >= MIN_SHEAR
    t6["a_pure_shearx_guard"] = {"wobble_peak_shearY": round(wob_y, 4),
                                 "dual_axis_true": a_dual, "pass": not a_dual}
    # (b) 同相 shear(shearY==shearX,同時刻同值)→ 正交 FALSE
    b_tw, _ = BT.gen_twist("body")
    sh = b_tw["shear"]
    in_phase = [{"time": f["time"], "x": f["x"], "y": f["x"]} for f in sh]  # y 設 == x(同相)
    pairs_x = [(f["time"], f["x"]) for f in in_phase]
    pairs_y = [(f["time"], f["y"]) for f in in_phase]
    tx, px = _peak_and_time(pairs_x); ty, py = _peak_and_time(pairs_y)
    rx = abs(_val_at(pairs_y, tx)) / py if py > 0 else 0.0
    ry = abs(_val_at(pairs_x, ty)) / px if px > 0 else 0.0
    b_quad_true = (rx <= QUAD_TOL and ry <= QUAD_TOL)
    t6["b_in_phase_guard"] = {"y_ratio_at_xpeak": round(rx, 4), "x_ratio_at_ypeak": round(ry, 4),
                              "quadrature_true": b_quad_true, "pass": not b_quad_true}
    # (c) shear 隔離:非 SHEAR_CATS beat 皆 0 bone 帶 shear
    import tier_variants as _TV
    leak = []
    for nm, an in anims.items():
        if "__" in nm or G.beat_category(nm) in _TV.SHEAR_CATS:
            continue
        sheared = [bn for bn, ch in an.get("bones", {}).items() if ch.get("shear")]
        if sheared:
            leak.append((nm, sheared))
    t6["c_shear_isolated"] = {"leaked": leak, "pass": not leak}
    # (d) 加性:移除 twist 的 storyboard → 其餘 beat 逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "twist"]}
    anims_no = G.build_animations(skel, sb_no)
    regressed = []
    for nm, an in anims_no.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    t6["d_additive_no_regression"] = {"regressed": regressed,
                                      "removed_beats": [b["beat"] for b in sb["beats"]
                                                        if G.beat_category(b["beat"]) == "twist"],
                                      "pass": not regressed}
    R["TW6_neg_control"] = {**t6, "pass": all(v["pass"] for v in t6.values())}

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
        for k in ["TW1_present_dual_shear", "TW2_damped_oscillation_both", "TW3_quadrature",
                  "TW4_identity_interface", "TW5_end2end_pivot_fixed", "TW6_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("TW1 shear peak by beat:", R["TW1_present_dual_shear"]["peak_by_beat"])
        print("TW3 quadrature:", R["TW3_quadrature"]["detail"])
        print("TW5 pivot-fixed (shy_peak / fixed / negctrl px):")
        for rec in R["TW5_end2end_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  shy {:.2f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["shy_peak"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
