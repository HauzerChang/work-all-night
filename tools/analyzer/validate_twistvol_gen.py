#!/usr/bin/env python3
"""candidate G-4''''''-vol 自我驗收閘 — 生成器產出**全仿射行列式守恆的反相雙軸 twist**端到端(純 CPU)。

補上 G-4''''''(twist)明白列出的 honest boundary:twist 的反相雙軸 shear 令 `det(M)=cos(shearY−shearX)≠1`
(擰轉會**變面積** —— 峰 Δφ=(1+φ)|shearX|=27.2° → det=cos=0.889 → 面積剩 ~89%)。本閘(G-4''''''-vol)驗證:
生成器 `gen_twistvol`(斜扭果凍守恆扭轉)在 twist 的反相雙軸 shear 上疊一條**耦合等軸 scale**
s=1/√(cos(shearY−shearX)) 使 **全 2×2 仿射 det≡1**(擰而**不變面積**),經先驗庫直出;`build_spine --shear-pivot`
端到端把 rotate/scale/shearX/shearY 一起繞關節 pivot 補償 → 件做**全仿射行列式守恆**的扭轉而 pivot 精確不動。

**與 squash 體積守恆不同層級(crux 區別)**:squash 守 `scaleX·scaleY≡1`(scale 通道自守、shearY≡0、
非均勻),故其**全** det=1·cos(shearX)≠1;twistvol 守**全矩陣** det≡1(scale 精確補償 shear 的 det 損失),
且 scale **等軸**(scaleX==scaleY)。負對照(TV6)以此兩點(shear-only、squash 式 scale)證守的是全矩陣、scale 等軸。

真值/fixture 與 (G-4'/G-4''''/G-4'''''')一致:從**先驗庫**(slot_bigwin,新增 twistvol beat)經 `analyze_target`
→ **真實 build_spine robot 骨架** → `build_animations` 端到端量。主秀運動無唯一正解(PROPOSAL 手感),閘驗
**客觀結構簽章(反相雙軸阻尼 shear + 全仿射 det 守恆 + 等軸 scale)+ 端到端不動點**,非美感;負對照證鑑別力。

AC(客觀、可量測):
  TV1 present + 雙軸 shear + 耦合 scale : twistvol beat 直出、finite、有 bone,且 ≥1 bone 同時帶 shear 與
                                          scale 通道;shearX 峰 ≥ MIN_SHEAR **且** shearY 峰 ≥ MIN_SHEAR
                                          **且** scale 最大膨脹 max(scaleX)−1 ≥ MIN_INFLATE(scale 為補償 shear det 而生)。
  TV2 兩軸阻尼振盪 + 反相              : 每 twistvol bone 的 shearX 與 shearY 各自(a)首尾 0;(b)繞 0 變號≥3;
                                          (c)相繼極值嚴格遞減(阻尼)—— 復用 G-4' 判準;且每內部極值 shearX·shearY<0
                                          (反相 → 確為 twist 而非任意 shear+scale)。
  TV3 全仿射 det 守恆 + 等軸(crux)   : 每 twistvol bone 的**每個**內部極值幀:(a)det(M)=sx·sy·cos(shearX−shearY)
                                          ≈1(|det−1|≤TOL_DET,**全 2×2 仿射**體積守恆);(b)scaleX==scaleY
                                          (|scaleX−scaleY|≤TOL_ISO,**等軸**膨脹,非 squash 的非均勻);(c)scaleX>1
                                          (為補償 shear det<1 而膨脹);且**去掉 scale**(令 sx=sy=1)後 det=cos<1
                                          → 證守恆由等軸 scale 補償達成(非 shear 自守)。
  TV4 identity 介面(可插 Loop)       : sample(0)/sample(dur) 各 bone identity;shear 首尾 (0,0)、scale 首尾 (1,1)。
  TV5 端到端 pivot 不動               : `build_spine --shear-pivot`(真實 robot)產出 twistvol 帶補償;凡有關節 pivot
                                          的 bone,pivot 殘差 < TOL_FIX(**在 shearY≠0 + scale 同時驅動下**);內建負對照
                                          = 未補償(繞件中心,含雙軸 shear+scale)大位移 → 證補償把全仿射錨在 pivot。
  TV6 負對照/隔離                     : (a)**shear-only 守衛**:雙軸 shear 但 scale≡(1,1)→ 全 det=cos<1 → 守恆 FALSE
                                          (證等軸 scale 在做 det 補償);(b)**squash 式 scale 守衛**:scaleX·scaleY≡1 但
                                          非均勻,配雙軸 shear → 全 det=1·cos≠1 → 守恆 FALSE(證守的是**全矩陣** det,
                                          非 scale 產物;且 aniso≠0 → 非等軸);(c)**同相守衛**:shearX==shearY(純旋轉)
                                          → 反相 FALSE;(d)**隔離**:非 twistvol beat 皆非「同時帶 shearY≠0 且等軸膨脹
                                          scale」(twist 有 shearY 無 scale、squash 有 scale 但非均勻且 shearY≡0);
                                          (e)**加性**:移除 twistvol 的 storyboard → 其餘 beat 逐位元不變(零回歸)。

用法:
  python3 validate_twistvol_gen.py            # 摘要
  python3 validate_twistvol_gen.py --json     # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim as SA
import gen_animations as G
# 復用 G-4' 的 shearX 讀取與阻尼簽章判準,確保與 shear-gen / squash-gen / twist-gen 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_shear_pivot import _world   # 真實 Spine local(含雙軸 shear + scale)世界座標求值
from pivot_rotation import transform_matrix_full  # 真實 Spine local 2×2(det 由此求,與管路一致)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0      # 度,twistvol 峰值 |shearX| / |shearY| 下限(head shearY 峰 0.7×10=7° → 餘裕)
MIN_INFLATE = 0.01   # scale 最大膨脹 max(scaleX)−1 下限(head 首極值 Δφ=17° → s−1≈0.011 → 餘裕)
TOL_DET = 2e-3       # 全仿射 |det−1| 上限(實測 <1e-5 → 巨大餘裕;負對照 shear-only |det−1|≈0.11 → >50× 鑑別)
TOL_ISO = 1e-3       # 等軸 |scaleX−scaleY| 上限(twistvol 建構恆 0;squash 負對照 aniso≈0.19 → >100× 鑑別)
MIN_DET_WORK = 0.02  # 去掉 scale 後**峰值** area loss 下限(min det_noscale ≤ 1−此值 → 證 scale 補償的是真 det 損失;
                     # head 峰 det_noscale=0.956 → loss 0.044 ≥ 0.02 餘裕;小極值 loss 天然趨零故只驗峰值)
TOL_FIX = 0.5        # px,pivot 不動點殘差上限(同 G-4/G-4'/G-4''''/G-4'''''')
MIN_NEG = 5.0        # px,TV5 負對照(未補償)位移下限
NEG_RATIO = 20.0     # 負對照/不動點 位移比下限


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/twistvol_gen_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    from analyze_target import analyze
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _twistvol_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "twistvol"]


def _shear_y(chans):
    fr = chans.get("shear")
    return [f["y"] for f in fr] if fr else []


def _shear_xy(chans):
    fr = chans.get("shear")
    return [(f["x"], f["y"]) for f in fr] if fr else []


def _scale_xy(chans):
    fr = chans.get("scale")
    return [(f["x"], f["y"]) for f in fr] if fr else []


def _has_shear_y(chans):
    return any(abs(shy) > 1e-6 for shy in _shear_y(chans))


def _has_iso_inflate_scale(chans):
    """該 bone 的 scale 是否為「等軸膨脹」(twistvol 簽章):≥1 個內部幀 scaleX==scaleY 且 >1。"""
    sc = _scale_xy(chans)
    return any(abs(sx - sy) <= TOL_ISO and sx > 1.0 + 1e-6 for (sx, sy) in sc[1:-1]) if len(sc) >= 3 else False


def _det(shx, shy, sx, sy):
    """真實 Spine local 2×2 行列式 = sx·sy·cos(shearX−shearY)(由 transform_matrix_full 求,與管路一致)。"""
    a, b, c, d = transform_matrix_full(0.0, sx, sy, shx, shy)
    return a * d - b * c


def _interior_full(chans):
    """twistvol 的內部極值幀 → [(shx, shy, sx, sy)]。shear 與 scale 通道極值 τ 同點(同 env)→ 依 index 對齊。
    首尾為 (0,0,1,1)。回傳去端點的內部幀;若通道缺席或長度不符回 []。"""
    sh = _shear_xy(chans)
    sc = _scale_xy(chans)
    if len(sh) < 3 or len(sh) != len(sc):
        return []
    return [(sh[i][0], sh[i][1], sc[i][0], sc[i][1]) for i in range(1, len(sh) - 1)]


def _tv3_eval(interior):
    """給一組內部極值 [(shx,shy,sx,sy)] → (det_ok, iso_ok, inflate_ok, scale_does_work, detail)。
    純函式 → 可對真實 twistvol 與合成負對照施同一判準(閘可信)。
      det_ok         : 每幀 |det(sx,sy,shx,shy) − 1| ≤ TOL_DET(全仿射守恆)。
      iso_ok         : 每幀 |scaleX − scaleY| ≤ TOL_ISO(等軸)。
      inflate_ok     : 每幀 scaleX > 1(補償 shear det<1 而膨脹)。
      scale_does_work: **峰值**去掉 scale 的 det=cos ≤ 1−MIN_DET_WORK(證守恆靠 scale 補償真 det 損失;
                       小極值 area loss 天然趨零,故驗最深損失 min(det_noscale) 而非每幀)。
    """
    if not interior:
        return False, False, False, False, {"det": [], "iso": [], "det_noscale": []}
    det = [_det(shx, shy, sx, sy) for (shx, shy, sx, sy) in interior]
    iso = [abs(sx - sy) for (shx, shy, sx, sy) in interior]
    inflate = [sx for (shx, shy, sx, sy) in interior]
    det_ns = [_det(shx, shy, 1.0, 1.0) for (shx, shy, sx, sy) in interior]
    det_ok = all(abs(dv - 1.0) <= TOL_DET for dv in det)
    iso_ok = all(iv <= TOL_ISO for iv in iso)
    inflate_ok = all(v > 1.0 + 1e-9 for v in inflate)
    scale_does_work = min(det_ns) <= 1.0 - MIN_DET_WORK   # 峰值 shear-only area loss 材料級 → scale 在補償真 det
    detail = {"det": [round(d, 6) for d in det], "iso": [round(v, 6) for v in iso],
              "det_noscale": [round(d, 6) for d in det_ns]}
    return det_ok, iso_ok, inflate_ok, scale_does_work, detail


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    tv_beats = _twistvol_beats(anims)
    R = {}

    # ---- TV1 present + dual-axis shear + coupled scale emitted ----
    s1 = {"twistvol_beats": tv_beats, "not_finite": [], "no_bones": [], "no_coupled": [],
          "weak_shearx": [], "weak_sheary": [], "weak_inflate": [], "peak_by_beat": {}}
    for tb in tv_beats:
        an = anims[tb]
        if not SA.all_finite(an):
            s1["not_finite"].append(tb)
        if not an.get("bones"):
            s1["no_bones"].append(tb)
        coupled = {bn: ch for bn, ch in an.get("bones", {}).items()
                   if _shear_xy(ch) and _scale_xy(ch)}
        if not coupled:
            s1["no_coupled"].append(tb); continue
        shx_pk = max(max(abs(v) for v in _shear_x(ch)) for ch in coupled.values())
        shy_pk = max(max(abs(v) for v in _shear_y(ch)) for ch in coupled.values())
        infl = max(max(sx for (sx, sy) in _scale_xy(ch)) for ch in coupled.values()) - 1.0
        s1["peak_by_beat"][tb] = {"shearX": round(shx_pk, 3), "shearY": round(shy_pk, 3),
                                  "inflate": round(infl, 4)}
        if shx_pk < MIN_SHEAR:
            s1["weak_shearx"].append(tb)
        if shy_pk < MIN_SHEAR:
            s1["weak_sheary"].append(tb)
        if infl < MIN_INFLATE:
            s1["weak_inflate"].append(tb)
    s1_pass = (bool(tv_beats) and not s1["not_finite"] and not s1["no_bones"]
               and not s1["no_coupled"] and not s1["weak_shearx"] and not s1["weak_sheary"]
               and not s1["weak_inflate"])
    R["TV1_present_coupled"] = {**s1, "pass": s1_pass}

    # ---- TV2 both axes damped oscillation + counter-phase ----
    s2 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "not_counterphase": [], "detail": {}}
    for tb in tv_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            sh = _shear_xy(ch)
            if not sh:
                continue
            for axis, vals in (("x", _shear_x(ch)), ("y", _shear_y(ch))):
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
            interior = _interior_full(ch)
            if interior and not all(shx * shy < -1e-9 for (shx, shy, sx, sy) in interior):
                s2["not_counterphase"].append("{}::{}".format(tb, bn))
    s2_pass = (bool(s2["detail"]) and not s2["bad_endpoints"] and not s2["few_sign_changes"]
               and not s2["not_damped"] and not s2["not_counterphase"])
    R["TV2_both_axes_damped_counterphase"] = {**s2, "pass": s2_pass}

    # ---- TV3 full-affine det conserved + isotropic scale (crux) ----
    s3 = {"det_broken": [], "not_iso": [], "not_inflated": [], "scale_no_work": [], "detail": {}}
    for tb in tv_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            interior = _interior_full(ch)
            if not interior:
                continue
            key = "{}::{}".format(tb, bn)
            det_ok, iso_ok, infl_ok, work_ok, det = _tv3_eval(interior)
            s3["detail"][key] = det
            if not det_ok:
                s3["det_broken"].append(key)
            if not iso_ok:
                s3["not_iso"].append(key)
            if not infl_ok:
                s3["not_inflated"].append(key)
            if not work_ok:
                s3["scale_no_work"].append(key)
    s3_pass = (bool(s3["detail"]) and not s3["det_broken"] and not s3["not_iso"]
               and not s3["not_inflated"] and not s3["scale_no_work"])
    R["TV3_full_det_conserved_iso"] = {**s3, "pass": s3_pass}

    # ---- TV4 identity interface ----
    s4 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for tb in tv_beats:
        an = anims[tb]
        dur = SA.duration(an)
        start = SA.sample(an, 0.0)["bones"]
        end = SA.sample(an, dur)["bones"]
        if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
            s4["bad_interface"].append(tb)
        for bn, ch in an.get("bones", {}).items():
            sh = _shear_xy(ch)
            if sh and (abs(sh[0][0]) > 1e-6 or abs(sh[0][1]) > 1e-6
                       or abs(sh[-1][0]) > 1e-6 or abs(sh[-1][1]) > 1e-6):
                s4["shear_endpoints_nonzero"].append("{}::{}".format(tb, bn))
            sc = _scale_xy(ch)
            if sc and (abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6
                       or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6):
                s4["scale_endpoints_nonident"].append("{}::{}".format(tb, bn))
    R["TV4_identity_interface"] = {**s4, "pass": (not s4["bad_interface"]
                                                 and not s4["shear_endpoints_nonzero"]
                                                 and not s4["scale_endpoints_nonident"])}

    # ---- TV5 end-to-end pivot-fixed via build_spine --shear-pivot ----
    import build_spine
    out = "/tmp/twistvol_gen_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    s5 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0}
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
    R["TV5_end2end_pivot_fixed"] = {**s5, "pass": s5_pass}

    # ---- TV6 negative controls / isolation ----
    s6 = {}
    # (a) shear-only 守衛:雙軸 shear 但 scale≡(1,1)→ 全 det=cos<1 → 守恆 FALSE
    shear_only = [(16.0, -11.2, 1.0, 1.0), (-8.0, 5.6, 1.0, 1.0),
                  (4.0, -2.8, 1.0, 1.0), (-2.0, 1.4, 1.0, 1.0)]
    det_so, iso_so, infl_so, work_so, _ = _tv3_eval(shear_only)
    s6["a_shear_only_guard"] = {"det_ok": det_so, "pass": not det_so}
    # (b) squash 式 scale 守衛:scaleX·scaleY≡1 但非均勻,配雙軸 shear → 全 det=1·cos≠1 且非等軸
    sq_scale = [(16.0, -11.2, 1.06, 1.0 / 1.06), (-8.0, 5.6, 1.03, 1.0 / 1.03),
                (4.0, -2.8, 1.015, 1.0 / 1.015), (-2.0, 1.4, 1.007, 1.0 / 1.007)]
    det_sq, iso_sq, infl_sq, work_sq, _ = _tv3_eval(sq_scale)
    s6["b_squash_scale_guard"] = {"det_ok": det_sq, "iso_ok": iso_sq,
                                  "pass": (not det_sq) and (not iso_sq)}
    # (c) 同相守衛:shearX==shearY(純旋轉,基底仍正交)→ 反相 FALSE
    same = [(16.0, 16.0, 1.0, 1.0), (-8.0, -8.0, 1.0, 1.0),
            (4.0, 4.0, 1.0, 1.0), (-2.0, -2.0, 1.0, 1.0)]
    cp_same = all(shx * shy < -1e-9 for (shx, shy, sx, sy) in same)
    s6["c_samephase_guard"] = {"counterphase_ok": cp_same, "pass": not cp_same}
    # (d) 隔離:非 twistvol beat 皆非「同時 shearY≠0 且等軸膨脹 scale」(twistvol 獨佔此組合)
    leak = []
    for nm, an in anims.items():
        if "__" in nm or G.beat_category(nm) == "twistvol":
            continue
        for bn, ch in an.get("bones", {}).items():
            if _has_shear_y(ch) and _has_iso_inflate_scale(ch):
                leak.append((nm, bn))
    s6["d_isolated"] = {"leaked": leak, "pass": not leak}
    # (e) 加性:移除 twistvol 的 storyboard → 其餘 beat 逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "twistvol"]}
    anims_no = G.build_animations(skel, sb_no)
    regressed = []
    for nm, an in anims_no.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    s6["e_additive_no_regression"] = {"regressed": regressed,
                                      "removed_beats": [b["beat"] for b in sb["beats"]
                                                        if G.beat_category(b["beat"]) == "twistvol"],
                                      "pass": not regressed}
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
        for k in ["TV1_present_coupled", "TV2_both_axes_damped_counterphase",
                  "TV3_full_det_conserved_iso", "TV4_identity_interface",
                  "TV5_end2end_pivot_fixed", "TV6_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("TV1 peaks by beat:", R["TV1_present_coupled"]["peak_by_beat"])
        print("TV3 detail:", json.dumps(R["TV3_full_det_conserved_iso"]["detail"], ensure_ascii=False))
        print("TV5 pivot-fixed (fixed/negctrl px):")
        for rec in R["TV5_end2end_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
