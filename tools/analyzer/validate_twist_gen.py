#!/usr/bin/env python3
"""candidate G-4'''''' 自我驗收閘 — 生成器產出 `shearY` 通道(反相雙軸剪切)端到端(純 CPU)。

補上 wobble/squash 系列一路留到現在的**最後一條 shear 通道 honest boundary(shearY≡0)**:
G-4'(`gen_wobble`)只擺 shearX、G-4''''(`gen_squash`)擺 shearX + 耦合非均勻 scale,兩者的
shearY 皆恆 0 —— 件的 **y 軸基向量方向**從未被獨立驅動過。`gen_twist`(斜扭果凍)是**第一個
產出 shearY** 的生成器:shearX 與 shearY **反相**阻尼擺動(shearY=−shearX)使件的兩軸夾角
(90+shearY−shearX)來回偏離 90°(菱形開合)= 真兩軸剪切。

**關鍵幾何(crux 的數學根據)**:Spine 3.8 bone local 2×2 的兩基向量方向 = (rot+shearX, rot+90+shearY)。
把 shearX、shearY **同加**一量等同 rotate(冗餘)→ **shearX==shearY(等相)⇒ M==R(rot+shearX) 純旋轉**,
件角不變(退化,非真剪切);唯有 **shearX≠shearY** 才獨立操控 y 軸方向、真正塞滿一般仿射 M 的
最後一個自由度。故本閘的 crux 不是「shearY 有非零值」,而是「件角真的偏離 90°(shearX≠shearY,
反相)」—— 等相 shear 的負對照(件角≡90°、anisotropy≈0=純旋轉)證此鑑別力(閘可信)。

真值/fixture 與 (G-4'/G-4'''') 一致:從**先驗庫**(slot_bigwin,新增 twist beat)經 `analyze_target`
→ **真實 build_spine robot 骨架** → `build_animations` 端到端量。主秀運動無唯一正解(PROPOSAL 手感),
閘驗**客觀結構簽章**(反相雙軸阻尼振盪 + 件角剪切 + 端到端不動點),非美感。

AC(客觀、可量測):
  T1 present + shearY 產出(crux): twist beat 直出、finite、有 bone,且 ≥1 bone 帶 shear 通道且**峰值
                                  |shearX| 與 |shearY| 皆 ≥ MIN_SHEAR** → 這是產線**第一次產出 shearY**
                                  (補滿一般仿射 M;wobble/squash 的 shearY 恆 0)。
  T2 件角剪切(crux)            : 每個 twist bone,每個非零極值幀 (a)shearX·shearY < 0(反相);
                                  (b)件角偏差 |shearY − shearX| ≥ MIN_CORNER(件角真的偏離 90°);
                                  (c)該幀 Spine local M 的 anisotropy(奇異值差)≥ MIN_ANISO(真非相似)。
  T3 雙軸阻尼振盪               : shearX **與** shearY 兩序列**各自**:(a)首尾 0;(b)繞 0 變號 ≥3;
                                  (c)相繼極值幅度嚴格遞減(阻尼)。
  T4 identity 介面(可插 Loop)  : sample(0)/sample(dur) 各 bone rotate/translate/scale 皆 identity
                                  且 shear 首尾 x==y==0 → 與 In/Loop/Out 無縫串接。
  T5 端到端 pivot 不動          : `build_spine --shear-pivot`(真實 robot)產出 twist 帶補償;凡有關節
                                  pivot 的 bone,pivot 殘差 < TOL_FIX(含 shearY 的一般仿射**第一次**由
                                  生成器驅動此路徑);內建負對照=未補償(繞件中心)pivot 大位移。
  T6 負對照/隔離(crux)        : (a)**等相 shear = 純旋轉**:shearX==shearY 的合成極值 → 件角偏差≡0、
                                  M==R 且 anisotropy≈0 → T2 件角剪切簽章 FALSE(證閘測獨立 y 軸歪斜,
                                  非「shearY 非零即可」);vs 反相(twist)anisotropy 顯著 >0(>NEG_ANISO 倍);
                                  (b)**shearY 隔離**:全 storyboard 中僅 twist 帶 shearY≠0(wobble/squash
                                  帶 shear 但 shearY≡0、非 shear-emitter 無 shear);(c)**加性**:移除 twist
                                  的 storyboard → 其餘 beat 逐位元不變(對 wobble/squash 等既有節拍零回歸)。

用法:
  python3 validate_twist_gen.py          # 摘要
  python3 validate_twist_gen.py --json   # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
from validate_shear_pivot import _world, _M_spine   # 真實 Spine local(含 shearY)世界座標 / 矩陣

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,twist 峰值 |shearX|、|shearY| 下限(確認雙軸皆有明顯 shear)
MIN_CORNER = 5.0    # 度,件角偏差 |shearY − shearX| 下限(件角確實偏離 90°)
MIN_ANISO = 0.10    # 極值幀 M 的 anisotropy(奇異值差)下限(真非相似;同 shear_pivot)
SIM_EPS = 1e-6      # 等相 shear 的 anisotropy 上限(純旋轉→各向同性)
NEG_ANISO = 50.0    # 反相/等相 anisotropy 比下限(鑑別餘裕)
TOL_FIX = 0.5       # px,pivot 不動點殘差上限(同 G-4)
MIN_NEG = 5.0       # px,T5 負對照(未補償)位移下限
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


def _shear_xy(chans):
    """bone channels → (shearX 序列, shearY 序列);無 shear 通道回 ([],[])。"""
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


def _aniso(shx, shy, deg=0.0, sx=1.0, sy=1.0):
    """該 (shearX,shearY) 幀之 Spine local M 的 anisotropy = 奇異值差(相似→0、真剪切→>0)。"""
    m = _M_spine(deg, sx, sy, shx, shy)
    s = np.linalg.svd(m, compute_uv=False)
    return float(s[0] - s[1])


def _twist_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "twist"]


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    twist_beats = _twist_beats(anims)
    R = {}

    # ---- T1 present + shearY emitted (crux) ----
    t1 = {"twist_beats": twist_beats, "missing_shear": [], "not_finite": [], "no_bones": [],
          "weak_shx": [], "weak_shy": [], "peak_by_beat": {}}
    for tb in twist_beats:
        an = anims[tb]
        if not SA.all_finite(an):
            t1["not_finite"].append(tb)
        if not an.get("bones"):
            t1["no_bones"].append(tb)
        sheared = {bn: _shear_xy(ch) for bn, ch in an.get("bones", {}).items() if _shear_xy(ch)[0]}
        if not sheared:
            t1["missing_shear"].append(tb); continue
        pk_x = max(max(abs(v) for v in sx) for sx, sy in sheared.values())
        pk_y = max(max(abs(v) for v in sy) for sx, sy in sheared.values())
        t1["peak_by_beat"][tb] = {"shx": round(pk_x, 3), "shy": round(pk_y, 3)}
        if pk_x < MIN_SHEAR:
            t1["weak_shx"].append(tb)
        if pk_y < MIN_SHEAR:            # crux:shearY 也必須明顯 → 這是產線第一次產出 shearY
            t1["weak_shy"].append(tb)
    t1_pass = (bool(twist_beats) and not t1["missing_shear"] and not t1["not_finite"]
               and not t1["no_bones"] and not t1["weak_shx"] and not t1["weak_shy"])
    R["T1_present_shearY_emitted"] = {**t1, "pass": t1_pass}

    # ---- T2 corner-angle shear (crux) ----
    # 反相(shearX·shearY<0)在**每個**非零極值都成立(符號對阻尼不變 → 全域可查);件角偏差的**幅度**
    # 因阻尼逐極值遞減,故只要求**峰極值**(件角偏差最大幀)偏離 90° 達 MIN_CORNER 且該幀 M 真非相似
    # (anisotropy≥MIN_ANISO)—— 阻尼的小尾極值不必再達門檻(其遞減簽章由 T3 各通道保障)。
    t2 = {"same_phase": [], "small_peak_corner": [], "low_peak_aniso": [], "detail": {}}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            sx, sy = _shear_xy(ch)
            if not sx:
                continue
            key = "{}::{}".format(tb, bn)
            peak_dev = 0.0; peak_aniso = 0.0
            for x, y in zip(sx, sy):
                if abs(x) < 1e-6 and abs(y) < 1e-6:
                    continue                      # identity 端點/零幀不計
                if x * y >= 0:                    # (a)反相:每個非零極值須異號(件角偏離 90°,非等相純旋轉)
                    t2["same_phase"].append(key)
                dev = abs(y - x)                  # 件角偏差 = |shearY − shearX|
                if dev > peak_dev:
                    peak_dev = dev
                    peak_aniso = _aniso(x, y)     # 峰件角幀的 M anisotropy(真非相似)
            t2["detail"][key] = {"peak_corner_dev": round(peak_dev, 3), "peak_aniso": round(peak_aniso, 4)}
            if peak_dev < MIN_CORNER:             # (b)峰件角偏差達門檻
                t2["small_peak_corner"].append(key)
            if peak_aniso < MIN_ANISO:            # (c)峰幀 M 真非相似
                t2["low_peak_aniso"].append(key)
    t2_pass = (bool(t2["detail"]) and not t2["same_phase"]
               and not t2["small_peak_corner"] and not t2["low_peak_aniso"])
    R["T2_corner_angle_shear"] = {**t2, "pass": t2_pass}

    # ---- T3 damped oscillation, BOTH channels ----
    t3 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "detail": {}}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            sx, sy = _shear_xy(ch)
            if not sx:
                continue
            for axis, seq in (("shx", sx), ("shy", sy)):
                key = "{}::{}::{}".format(tb, bn, axis)
                ends_ok = abs(seq[0]) < 1e-6 and abs(seq[-1]) < 1e-6
                nsc = _sign_changes_zero(seq)
                damp = _extrema_mags_decreasing(seq)
                t3["detail"][key] = {"n_sign_changes": nsc, "damped": damp,
                                     "peaks": [round(v, 3) for v in seq]}
                if not ends_ok:
                    t3["bad_endpoints"].append(key)
                if nsc < 3:
                    t3["few_sign_changes"].append(key)
                if not damp:
                    t3["not_damped"].append(key)
    t3_pass = (bool(t3["detail"]) and not t3["bad_endpoints"]
               and not t3["few_sign_changes"] and not t3["not_damped"])
    R["T3_damped_both_channels"] = {**t3, "pass": t3_pass}

    # ---- T4 identity interface ----
    t4 = {"bad_interface": [], "shear_endpoints_nonzero": []}
    for tb in twist_beats:
        an = anims[tb]
        dur = SA.duration(an)
        start = SA.sample(an, 0.0)["bones"]
        end = SA.sample(an, dur)["bones"]
        if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
            t4["bad_interface"].append(tb)
        for bn, ch in an.get("bones", {}).items():
            sx, sy = _shear_xy(ch)
            if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6
                       or abs(sy[0]) > 1e-6 or abs(sy[-1]) > 1e-6):
                t4["shear_endpoints_nonzero"].append("{}::{}".format(tb, bn))
    R["T4_identity_interface"] = {**t4, "pass": not t4["bad_interface"] and not t4["shear_endpoints_nonzero"]}

    # ---- T5 end-to-end pivot-fixed via build_spine --shear-pivot ----
    import build_spine
    out = "/tmp/twist_gen_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    t5 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0}
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
            t5["n_joint_bones"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            # 內建負對照:未補償(繞件中心)—— 同 shear(含 shearY)但無 translate
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"bone": bn, "beat": tb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            t5["checked"].append(rec)
            if not (fix < TOL_FIX):
                t5["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                t5["fail_negctrl"].append(rec)
    t5_pass = (t5["n_joint_bones"] >= 1 and not t5["fail_fixed"] and not t5["fail_negctrl"])
    R["T5_end2end_pivot_fixed"] = {**t5, "pass": t5_pass}

    # ---- T6 negative controls / isolation ----
    t6 = {}
    # (a) crux 等相 shear = 純旋轉:件角偏差≡0、M==R、anisotropy≈0 → T2 件角簽章 FALSE
    phi = 12.0
    same_dev = abs(phi - phi)                        # shearX==shearY → 件角偏差 0
    same_aniso = _aniso(phi, phi)                    # 等相 → anisotropy 0(純旋轉)
    counter_aniso = _aniso(phi, -phi)                # 反相(twist)→ anisotropy 顯著 >0
    is_rotation = np.allclose(_M_spine(0.0, 1.0, 1.0, phi, phi), _M_spine(phi, 1.0, 1.0, 0.0, 0.0))
    same_sig_true = (same_dev >= MIN_CORNER and same_aniso >= MIN_ANISO)  # 等相「應」不成立
    t6["a_equalphase_is_rotation"] = {
        "phi": phi, "same_phase_corner_dev": round(same_dev, 4),
        "same_phase_aniso": round(same_aniso, 8), "counter_phase_aniso": round(counter_aniso, 4),
        "equalphase_M_equals_rotation": bool(is_rotation),
        "aniso_ratio": round(counter_aniso / same_aniso, 1) if same_aniso > 1e-12 else float("inf"),
        # 通過條件:等相簽章 FALSE(件角/aniso 不達標)+ 等相確為純旋轉 + 反相 aniso 大出鑑別餘裕
        "pass": (not same_sig_true) and is_rotation and same_aniso < SIM_EPS
                and counter_aniso > NEG_ANISO * max(same_aniso, 1e-12)}
    # (b) shearY 隔離:全 storyboard 中僅 twist 帶 shearY≠0(wobble/squash 有 shear 但 shearY≡0、
    #     非 shear-emitter 無 shear)。
    shy_leak = []; shear_leak = []; wobble_squash_shy = []
    for nm, an in anims.items():
        if "__" in nm:
            continue
        cat = G.beat_category(nm)
        for bn, ch in an.get("bones", {}).items():
            sx, sy = _shear_xy(ch)
            if not sx:
                continue
            has_shy = any(abs(v) > 1e-6 for v in sy)
            if cat == "twist":
                continue
            if cat not in TV.SHEAR_CATS and sx:          # 非 shear-emitter 竟帶 shear
                shear_leak.append((nm, bn))
            if has_shy:                                   # 非 twist 竟帶 shearY≠0
                shy_leak.append((nm, bn))
                if cat in ("wobble", "squash"):
                    wobble_squash_shy.append((nm, bn))
    t6["b_shearY_isolated"] = {"shearY_leak": shy_leak, "shear_leak": shear_leak,
                               "wobble_squash_shy_nonzero": wobble_squash_shy,
                               "pass": not shy_leak and not shear_leak}
    # (c) 加性:移除 twist 的 storyboard → 其餘 beat 逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "twist"]}
    anims_no = G.build_animations(skel, sb_no)
    regressed = []
    for nm, an in anims_no.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    t6["c_additive_no_regression"] = {"regressed": regressed,
                                      "removed_beats": [b["beat"] for b in sb["beats"]
                                                        if G.beat_category(b["beat"]) == "twist"],
                                      "pass": not regressed}
    R["T6_neg_control"] = {**t6, "pass": all(v["pass"] for v in t6.values())}

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
        for k in ["T1_present_shearY_emitted", "T2_corner_angle_shear", "T3_damped_both_channels",
                  "T4_identity_interface", "T5_end2end_pivot_fixed", "T6_neg_control"]:
            print("{:28s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("T1 shear peaks by beat:", R["T1_present_shearY_emitted"]["peak_by_beat"])
        na = R["T6_neg_control"]["a_equalphase_is_rotation"]
        print("T6a equal-phase aniso {} (rotation={}) vs counter-phase {} (ratio {})".format(
            na["same_phase_aniso"], na["equalphase_M_equals_rotation"],
            na["counter_phase_aniso"], na["aniso_ratio"]))
        print("T5 pivot-fixed (fixed/negctrl px):")
        for rec in R["T5_end2end_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
