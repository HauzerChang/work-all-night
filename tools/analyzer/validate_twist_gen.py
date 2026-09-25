#!/usr/bin/env python3
"""candidate G-4'''''' 自我驗收閘 — 生成器產出**反相雙軸 shear**(首度驅動 shearY)端到端(純 CPU)。

一路的 honest boundary(wobble G-4' / squash G-4'''' 一直留著):至今所有產 shear 的節拍都令 **shearY≡0**
(wobble 純 shearX、squash shearX+耦合非均勻 scale),故 Spine local 一般仿射 M 的第二條 shear 軸(y 軸 skew)
從未被**生成器**驅動 —— 公式/閘早就吃 shy(G-4 `transform_matrix_full(...,shy)` / `pivot_channels_affine` /
`apply_pivots(include_shear=True)` 以**合成** shy 驗過管路),生成端這次才接上。本閘(G-4'''''')驗證:生成器
`gen_twist`(斜扭果凍扭轉)實際產出**雙軸 shear**(shearX 與 shearY 同時非零、反相),經先驗庫直出;
`build_spine --shear-pivot` 端到端把 rotate/scale/shearX/**shearY** 一起繞關節 pivot 補償 → 件做**用滿兩條
shear 軸的一般仿射**變換而 pivot 精確不動(G-4 通用 Δ=(M−I)(O−P) 第一次被**生成器產的 shearY** 驅動)。

真值/fixture 與 (E/H/I/J/G-4'/G-4'''') 一致:從**先驗庫**(slot_bigwin,新增 twist beat)經 `analyze_target`
→ **真實 build_spine robot 骨架** → `build_animations` 端到端量。主秀運動無唯一正解(PROPOSAL 手感),
閘驗**客觀結構簽章(兩軸阻尼振盪 + 反相雙軸耦合)+ 端到端不動點**,非美感;負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  TW1 present + dual-axis shear(crux): twist beat 直出、finite、有 bone,且 ≥1 bone 帶 shear 通道,其
                                       shearX 峰 ≥ MIN_SHEAR **且** shearY 峰 ≥ MIN_SHEAR(shearY 不再 ≡0)
                                       → **產線第一次驅動第二條 shear 軸**。
  TW2 兩軸皆阻尼振盪               : 每個 twist bone 的 shearX **與** shearY 各自:(a)首尾 0;(b)繞 0 變號 ≥3;
                                    (c)相繼極值幅度嚴格遞減(阻尼)—— 復用 G-4' 判準,與 shear-gen 閘一致。
  TW3 反相雙軸 shear 耦合(crux)  : 每個 twist bone 的**每個**內部極值幀:(a)shearX、shearY **反號**
                                    (乘積 < 0);(b)夾角偏離 |shearY−shearX| ≥ MIN_DEV(反相 → =|shearX|+|shearY|);
                                    證「真雙軸 shear」非「同相=旋轉偽裝」。
  TW4 identity 介面(可插 Loop)   : sample(0)/sample(dur) 各 bone identity,且 shear 首尾 (x,y)=(0,0)。
  TW5 端到端一般仿射 pivot 不動    : `build_spine --shear-pivot`(真實 robot)產出 twist 帶補償;凡有關節
                                    pivot 的 bone,pivot 殘差 < TOL_FIX(**在 shearY≠0 驅動下**);內建負對照
                                    = 未補償(繞件中心,含雙軸 shear)大位移 → 證補償把雙軸 shear 也錨在 pivot。
  TW6 負對照/隔離                 : (a)**同相守衛**:合成 shearX==shearY(純旋轉)→ TW3 反號 FALSE
                                    (證閘測「真雙軸 shear」非「旋轉偽裝」);(b)**單軸守衛**:合成 shearY≡0
                                    (wobble 樣)→ 雙軸 FALSE(shearY 峰=0);(c)**雙軸隔離**:非 twist beat 皆
                                    shearY≡0(wobble/squash 有 shearX 無 shearY、其餘無 shear → twist 獨佔 shearY);
                                    (d)**加性**:移除 twist 的 storyboard → 其餘 beat 逐位元不變(零回歸)。

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
import tier_variants as _TV
# 復用 G-4' 的 shearX 讀取與阻尼簽章判準,確保與 shear-gen / squash-gen 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_shear_pivot import _world   # 真實 Spine local(含雙軸 shear)世界座標求值

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,twist 峰值 |shearX| / |shearY| 下限(shearY 峰 = 0.7×shearX 峰,head 最小 7° → 餘裕)
MIN_DEV = 8.0       # 度,反相夾角偏離 |shearY−shearX| 峰下限(head 首極值 10+7=17° → 充足餘裕)
TOL_FIX = 0.5       # px,pivot 不動點殘差上限(同 G-4/G-4'/G-4'''')
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
    from analyze_target import analyze
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _twist_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "twist"]


def _shear_y(chans):
    """bone channels → shearY 關鍵幀值序列(無 shear 通道回 [])。"""
    fr = chans.get("shear")
    return [f["y"] for f in fr] if fr else []


def _shear_xy(chans):
    """bone channels → [(shearX, shearY)] 關鍵幀序列(無 shear 通道回 [])。"""
    fr = chans.get("shear")
    return [(f["x"], f["y"]) for f in fr] if fr else []


def _interior_shear(chans):
    """twist 的內部 shear 極值幀(去掉首尾 identity 端點)。首尾為 (0,0)。"""
    xy = _shear_xy(chans)
    return xy[1:-1] if len(xy) >= 3 else []


def _tw3_eval(interior):
    """給一組內部 shear 極值 [(shx,shy)] → (counterphase_ok, dev_ok, detail)。
    純函式 → 可對真實 twist 與合成負對照施同一判準(閘可信)。"""
    if not interior:
        return False, False, {"prod": [], "dev": []}
    prod = [shx * shy for (shx, shy) in interior]
    dev = [abs(shy - shx) for (shx, shy) in interior]
    counterphase_ok = all(p < -1e-9 for p in prod)   # 每極值 shearX、shearY 反號
    dev_ok = max(dev) >= MIN_DEV
    detail = {"prod": [round(p, 4) for p in prod], "dev": [round(d, 4) for d in dev]}
    return counterphase_ok, dev_ok, detail


def _has_shear_y(chans):
    return any(abs(shy) > 1e-6 for shy in _shear_y(chans))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    twist_beats = _twist_beats(anims)
    R = {}

    # ---- TW1 present + dual-axis shear emitted (crux) ----
    s1 = {"twist_beats": twist_beats, "not_finite": [], "no_bones": [], "no_shear": [],
          "weak_shearx": [], "weak_sheary": [], "peak_by_beat": {}}
    for tb in twist_beats:
        an = anims[tb]
        if not SA.all_finite(an):
            s1["not_finite"].append(tb)
        if not an.get("bones"):
            s1["no_bones"].append(tb)
        sheared = {bn: ch for bn, ch in an.get("bones", {}).items() if _shear_xy(ch)}
        if not sheared:
            s1["no_shear"].append(tb); continue
        shx_pk = max(max(abs(v) for v in _shear_x(ch)) for ch in sheared.values())
        shy_pk = max(max(abs(v) for v in _shear_y(ch)) for ch in sheared.values())
        s1["peak_by_beat"][tb] = {"shearX": round(shx_pk, 3), "shearY": round(shy_pk, 3)}
        if shx_pk < MIN_SHEAR:
            s1["weak_shearx"].append(tb)
        if shy_pk < MIN_SHEAR:
            s1["weak_sheary"].append(tb)
    s1_pass = (bool(twist_beats) and not s1["not_finite"] and not s1["no_bones"]
               and not s1["no_shear"] and not s1["weak_shearx"] and not s1["weak_sheary"])
    R["TW1_present_dual_axis"] = {**s1, "pass": s1_pass}

    # ---- TW2 both axes damped oscillation (reuse G-4' criteria on each axis) ----
    s2 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "detail": {}}
    for tb in twist_beats:
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
    R["TW2_both_axes_damped"] = {**s2, "pass": s2_pass}

    # ---- TW3 counter-phase two-axis coupling (crux) ----
    s3 = {"not_counterphase": [], "weak_dev": [], "detail": {}}
    for tb in twist_beats:
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
    R["TW3_counterphase_coupling"] = {**s3, "pass": s3_pass}

    # ---- TW4 identity interface ----
    s4 = {"bad_interface": [], "shear_endpoints_nonzero": []}
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
    R["TW4_identity_interface"] = {**s4, "pass": (not s4["bad_interface"]
                                                  and not s4["shear_endpoints_nonzero"])}

    # ---- TW5 end-to-end general-affine pivot-fixed via build_spine --shear-pivot ----
    import build_spine
    out = "/tmp/twist_gen_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True)
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
            # 內建負對照:未補償(繞件中心)—— 同雙軸 shear 但無 translate
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
    R["TW5_end2end_affine_pivot_fixed"] = {**s5, "pass": s5_pass}

    # ---- TW6 negative controls / isolation ----
    s6 = {}
    # (a) 同相守衛:shearX==shearY(純旋轉,基底仍正交)→ 反相 FALSE(乘積>0)
    same = [(16.0, 16.0), (-8.0, -8.0), (4.0, 4.0), (-2.0, -2.0)]
    cp_s, dev_s, _ = _tw3_eval(same)
    s6["a_samephase_guard"] = {"counterphase_ok": cp_s, "pass": not cp_s}
    # (b) 單軸守衛:shearY≡0(wobble 樣)→ 反相 FALSE(乘積=0,非 <0)且偏離仍在但無雙軸
    singleaxis = [(16.0, 0.0), (-8.0, 0.0), (4.0, 0.0), (-2.0, 0.0)]
    cp_1, dev_1, _ = _tw3_eval(singleaxis)
    s6["b_singleaxis_guard"] = {"counterphase_ok": cp_1, "pass": not cp_1}
    # (c) 雙軸隔離:非 shearY 產出類別的 beat 皆 shearY≡0(shearY 由 SHEARY_CATS 獨佔第二條 shear 軸)。
    #     (G-4''''''-vol)twistvol 亦驅動 shearY(twist + 均勻體積守恆 scale)→ 以 SHEARY_CATS 認定合法產出者,
    #     集中一處(見 tier_variants.SHEARY_CATS),避免每加一個 shearY 節拍就改此硬編碼。
    leak = []
    for nm, an in anims.items():
        if "__" in nm or G.beat_category(nm) in _TV.SHEARY_CATS:
            continue
        for bn, ch in an.get("bones", {}).items():
            if _has_shear_y(ch):
                leak.append((nm, bn))
    s6["c_sheary_isolated"] = {"leaked": leak, "pass": not leak}
    # (d) 加性:移除 twist 的 storyboard → 其餘 beat 逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "twist"]}
    anims_no = G.build_animations(skel, sb_no)
    regressed = []
    for nm, an in anims_no.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    s6["d_additive_no_regression"] = {"regressed": regressed,
                                      "removed_beats": [b["beat"] for b in sb["beats"]
                                                        if G.beat_category(b["beat"]) == "twist"],
                                      "pass": not regressed}
    R["TW6_neg_control"] = {**s6, "pass": all(v["pass"] for v in s6.values())}

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
        for k in ["TW1_present_dual_axis", "TW2_both_axes_damped",
                  "TW3_counterphase_coupling", "TW4_identity_interface",
                  "TW5_end2end_affine_pivot_fixed", "TW6_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("TW1 peaks by beat:", R["TW1_present_dual_axis"]["peak_by_beat"])
        print("TW3 detail:", json.dumps(R["TW3_counterphase_coupling"]["detail"], ensure_ascii=False))
        print("TW5 pivot-fixed (fixed/negctrl px):")
        for rec in R["TW5_end2end_affine_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
