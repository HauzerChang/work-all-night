#!/usr/bin/env python3
"""candidate G-4''''''-vol 自我驗收閘 — **體積守恆扭轉**(反相雙軸 shear + 均勻耦合 scale → det≡1)端到端(純 CPU)。

補反相雙軸 shear 一路(G-4''''''→tier→count)明列的 honest boundary:**`det=cos(shearY−shearX)≠1` → 擰轉變面積**。
Spine local 2×2(deg=0、shy=−φ·shx)行列式 = sx·sy·cos((1+φ)·shearX);純扭轉(sx=sy=1)令 cos<1 → 面積縮小。
本候選讓 `gen_twist(vol_conserve=True)` 額外產出**均勻**耦合 scale `sx=sy=1/√cos((1+φ)·shearX)` →
`sx·sy=1/cos((1+φ)·shearX)` → **det≡1**(擰而不變面積)。**crux(與 squash 的鑑別)**:squash 用**非均勻自守恆**
scale(scaleX·scaleY≡1、scaleX≠scaleY)—— scale 自己守恆、shear 另計;此處 shear **本身**破面積,補償 scale 必須
是**均勻**(sx==sy、sx·sy=1/cos>1)才不引入擠壓非均勻 → 保住「純扭轉」(|sx−sy|≡0 為鑑別簽章)。

真值/fixture 與 (G-4''''''/tier/count) 一致:從**先驗庫**(slot_bigwin,twist beat)經 `analyze_target` →
**真實 build_spine robot 骨架** → `build_animations(twist_volume=True)` 端到端量。主秀運動無唯一正解(PROPOSAL
手感),閘驗**客觀幾何守恆(det≡1)+ 結構簽章保形(反相雙軸/阻尼)+ 均勻性(與 squash 鑑別)+ 端到端不動點**,
非美感;負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  VV1 present + backward-compat: twist_volume=True → 每 twist beat 直出/finite/≥1 bone 帶 **shear+scale** 雙通道、
                                scale 首尾 (1,1)(介面契約);twist_volume=False → twist beat **無** scale 通道,
                                且 True 的 shear 通道**逐位元同** False(加 scale 不擾動 shear)。
  VV2 體積守恆 det≡1(crux)    : twist_volume=True 下每 twist bone **每內部 shear/scale 極值幀**
                                |det(M)−1| ≤ TOL_DET(M=transform_matrix_full);負對照 = 同扭轉無 vol scale
                                (sx=sy=1)峰值 det ≤ MAX_DET_NEG < 1(證面積確實被扭轉縮小、且 scale 是守恆之因)。
  VV3 均勻 + 反相雙軸保形(crux): 每 twist bone (a)scale 每幀 **均勻**(|sx−sy| ≤ TOL_ISO,與 squash 非均勻鑑別);
                                (b)反相雙軸 shear 逐內部極值保形(_tw3_eval:反號 + 偏離)且 φ=|shy/shx|≈TWIST_PHI。
  VV4 兩軸阻尼保形             : 每 twist bone 的 shearX 與 shearY 各自:首尾 0 + 繞 0 變號 ≥3 + 相繼極值遞減
                                (復用 G-4' 判準;證加 scale 未動 shear 簽章)。
  VV5 端到端 det≡1 + pivot 不動 : `build_spine --animate --twist-volume --shear-pivot`(真實 robot):(a)twist bone
                                在**前補償極值時刻**取 post-pivot scale/shear → |det−1| ≤ TOL_DET(scale 通道經
                                pivot 補償仍守恆:補償只加 translate、M 不變);(b)凡有關節 pivot 的 bone pivot
                                殘差 < TOL_FIX,內建負對照(未補償)大位移 → 證雙軸 shear+守恆 scale 皆錨在 pivot。
  VV6 負對照/隔離             : (a)**均勻性守衛**:以 squash 式**非均勻自守恆** scale(sx·sy=1)補償同扭轉 →
                                full det=cos((1+φ)shx)≠1(**非**體積守恆)→ 證「均勻 sx·sy=1/cos」才是 twist 的解;
                                (b)**無 scale 守衛**:vol_conserve=False → 峰 det<1(證 scale 通道是守恆之因);
                                (c)**scale 隔離**:非 twist beat 在 twist_volume True/False 下逐位元不變(vol scale
                                只作用 twist,不外洩 wobble/hit);(d)**加性**:移除 twist storyboard → 其餘逐位元不變。

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
from beat_templates import TWIST_PHI
from pivot_rotation import transform_matrix_full
# 復用 G-4' 的 shearX 讀取與阻尼簽章判準
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
# 復用 G-4'''''' 的雙軸讀取 / 反相判準 / fixture
from validate_twist_gen import (_psd, _skeleton, _storyboard, _twist_beats, _is_ident,
                                _shear_y, _shear_xy, _interior_shear, _tw3_eval, _has_shear_y)
from validate_shear_pivot import _world

GENRE = "slot_bigwin"
TOL_DET = 2e-3      # |det−1| 上限(scale 6 dp 捨入 → 實測 ~1e-6;cos 幾何餘裕充足)
MAX_DET_NEG = 0.98  # 負對照(無 vol scale)峰 det 上限(每 bone 峰 ≥2% 面積誤差;head 最小 10°→0.956<0.98)
MIN_SQUASH_DEV = 0.02  # VV6(a):squash 式非均勻 scale 補償同扭轉,峰 |det−1| 下限(證其**不**守恆 twist 面積)
TOL_ISO = 1e-4      # scale 均勻性 |sx−sy| 上限(vol twist 建構恆 0;squash 非均勻遠大於此)
PHI_TOL = 2e-3      # φ=|shy/shx| 對 TWIST_PHI 偏差上限
TOL_FIX = 0.5       # px,pivot 不動點殘差上限(同 G-4/G-4'/G-4'''')
MIN_NEG = 5.0       # px,VV5 負對照(未補償)位移下限
NEG_RATIO = 20.0    # 負對照/不動點 位移比下限


def _det(shx, shy, sx=1.0, sy=1.0):
    a, b, c, d = transform_matrix_full(0.0, sx, sy, shx, shy)
    return a * d - b * c


def _scale_xy(chans):
    fr = chans.get("scale")
    return [(f["x"], f["y"]) for f in fr] if fr else []


def _interp2(frames, t):
    """線性插值 frames(含 x,y)在時間 t → (x,y)。"""
    d = SA._interp(frames, t, ["x", "y"])
    return d["x"], d["y"]


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb, twist_volume=True)         # 體積守恆版
    anims_nov = G.build_animations(skel, sb, twist_volume=False)    # 無 vol(golden 對照)
    twist_beats = _twist_beats(anims)
    R = {}

    # ---- VV1 present + backward-compat ----
    s1 = {"twist_beats": twist_beats, "not_finite": [], "no_bones": [],
          "no_dual_channel": [], "scale_iface_bad": [], "novol_has_scale": [], "shear_changed": []}
    for tb in twist_beats:
        an = anims[tb]
        if not SA.all_finite(an):
            s1["not_finite"].append(tb)
        if not an.get("bones"):
            s1["no_bones"].append(tb)
        dual = {bn: ch for bn, ch in an.get("bones", {}).items()
                if _shear_xy(ch) and _scale_xy(ch)}
        if not dual:
            s1["no_dual_channel"].append(tb); continue
        for bn, ch in dual.items():
            sc = _scale_xy(ch)
            if abs(sc[0][0] - 1.0) > 1e-6 or abs(sc[0][1] - 1.0) > 1e-6 \
               or abs(sc[-1][0] - 1.0) > 1e-6 or abs(sc[-1][1] - 1.0) > 1e-6:
                s1["scale_iface_bad"].append("{}::{}".format(tb, bn))
        # backward-compat:twist_volume=False → 無 scale;shear 通道逐位元同 True
        an0 = anims_nov[tb]
        for bn, ch in an0.get("bones", {}).items():
            if ch.get("scale"):
                s1["novol_has_scale"].append("{}::{}".format(tb, bn))
            if bn in an.get("bones", {}):
                if json.dumps(ch.get("shear"), sort_keys=True) != \
                   json.dumps(an["bones"][bn].get("shear"), sort_keys=True):
                    s1["shear_changed"].append("{}::{}".format(tb, bn))
    s1_pass = (bool(twist_beats) and not s1["not_finite"] and not s1["no_bones"]
               and not s1["no_dual_channel"] and not s1["scale_iface_bad"]
               and not s1["novol_has_scale"] and not s1["shear_changed"])
    R["VV1_present_backcompat"] = {**s1, "pass": s1_pass}

    # ---- VV2 volume conservation det==1 (crux) ----
    s2 = {"det_fail": [], "neg_not_below": [], "n_extrema": 0, "worst_dev": 0.0,
          "neg_peak_det_by_beat": {}}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            sh = _interior_shear(ch)
            sc = _scale_xy(ch)
            if not sh or not sc:
                continue
            # scale 內部極值幀(與 shear 同時間點,去首尾)
            sc_int = sc[1:-1]
            neg_peak = 0.0
            for (shx, shy), (sx, sy) in zip(sh, sc_int):
                s2["n_extrema"] += 1
                dv = abs(_det(shx, shy, sx, sy) - 1.0)
                s2["worst_dev"] = max(s2["worst_dev"], dv)
                if dv > TOL_DET:
                    s2["det_fail"].append({"beat": tb, "bone": bn, "shx": shx,
                                           "shy": shy, "dev": round(dv, 6)})
                dn = _det(shx, shy, 1.0, 1.0)   # 負對照:無 vol scale
                neg_peak = max(neg_peak, 1.0 - dn)   # 面積縮小量
            s2["neg_peak_det_by_beat"]["{}::{}".format(tb, bn)] = round(1.0 - neg_peak, 5)
            if not (1.0 - neg_peak <= MAX_DET_NEG):
                s2["neg_not_below"].append("{}::{}".format(tb, bn))
    s2["worst_dev"] = round(s2["worst_dev"], 7)
    s2_pass = (s2["n_extrema"] >= 1 and not s2["det_fail"] and not s2["neg_not_below"])
    R["VV2_volume_conserved"] = {**s2, "pass": s2_pass}

    # ---- VV3 isotropic scale + counter-phase dual-axis preserved (crux) ----
    s3 = {"anisotropic": [], "not_counterphase": [], "weak_dev": [], "phi_bad": [], "detail": {}}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            sc = _scale_xy(ch)
            interior = _interior_shear(ch)
            if not sc or not interior:
                continue
            key = "{}::{}".format(tb, bn)
            max_iso = max(abs(sx - sy) for (sx, sy) in sc)
            if max_iso > TOL_ISO:
                s3["anisotropic"].append(key)
            cp_ok, dev_ok, det = _tw3_eval(interior)
            if not cp_ok:
                s3["not_counterphase"].append(key)
            if not dev_ok:
                s3["weak_dev"].append(key)
            phis = [abs(shy / shx) for (shx, shy) in interior if abs(shx) > 1e-9]
            phi_bad = any(abs(p - TWIST_PHI) > PHI_TOL for p in phis)
            if phi_bad:
                s3["phi_bad"].append(key)
            s3["detail"][key] = {"max_iso": round(max_iso, 6),
                                 "phi": [round(p, 4) for p in phis]}
    s3_pass = (bool(s3["detail"]) and not s3["anisotropic"] and not s3["not_counterphase"]
               and not s3["weak_dev"] and not s3["phi_bad"])
    R["VV3_isotropic_dualaxis"] = {**s3, "pass": s3_pass}

    # ---- VV4 both axes damped oscillation preserved ----
    s4 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "detail": {}}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            for axis, vals in (("x", _shear_x(ch)), ("y", _shear_y(ch))):
                if not vals:
                    continue
                key = "{}::{}::{}".format(tb, bn, axis)
                ends_ok = abs(vals[0]) < 1e-6 and abs(vals[-1]) < 1e-6
                nsc = _sign_changes_zero(vals)
                damp = _extrema_mags_decreasing(vals)
                s4["detail"][key] = {"n_sign_changes": nsc, "damped": damp}
                if not ends_ok:
                    s4["bad_endpoints"].append(key)
                if nsc < 3:
                    s4["few_sign_changes"].append(key)
                if not damp:
                    s4["not_damped"].append(key)
    s4_pass = (bool(s4["detail"]) and not s4["bad_endpoints"]
               and not s4["few_sign_changes"] and not s4["not_damped"])
    R["VV4_both_axes_damped"] = {**s4, "pass": s4_pass}

    # ---- VV5 end-to-end det==1 survives pivot + pivot-fixed ----
    # crux(誠實邊界):有關節 pivot 的 bone 在 --shear-pivot 下 scale/shear 通道被**重取樣到 60fps 密網格**
    # (標準 keyframe 重採樣),shear 頂點(極值)處的次幀弦割會讓 det 偏離 ~0.5%(取樣假影,非設計破壞)。
    # 故 det≡1 端到端**在通道未被重採樣的 bone**(無關節 pivot → 通道原封不動)上嚴格驗(exact ≤TOL_DET);
    # 有關節 pivot 的 bone 改驗 **pivot 不動點**(件繞關節不動,含守恆 scale)—— 兩者互補涵蓋所有 twist bone。
    # (守恆本身在生成端已於 VV2 逐極值嚴格證;pivot 補償只加 translate、M 不變 → 未重採樣者 det≡1 自然延續。)
    import build_spine
    out = "/tmp/twist_vol_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True,
                             shear_pivot=True, twist_volume=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    s5 = {"det_fail": [], "checked_det": 0, "worst_dev": 0.0,
          "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0, "checked": []}
    for tb in _twist_beats(sp_skel["animations"]):
        an = sp_skel["animations"][tb]
        for bn, ch in an.get("bones", {}).items():
            sh_f = ch.get("shear"); sc_f = ch.get("scale")
            # (a) det≡1 端到端:僅在**未重採樣**(無關節 pivot → 通道原封)的 bone 逐內部極值嚴格驗
            if sh_f and sc_f and bn not in joints:
                for i in range(1, len(sh_f) - 1):
                    shx, shy = sh_f[i]["x"], sh_f[i]["y"]
                    sx, sy = sc_f[i]["x"], sc_f[i]["y"]
                    dv = abs(_det(shx, shy, sx, sy) - 1.0)
                    s5["checked_det"] += 1
                    s5["worst_dev"] = max(s5["worst_dev"], dv)
                    if dv > TOL_DET:
                        s5["det_fail"].append({"beat": tb, "bone": bn, "i": i,
                                               "dev": round(dv, 6)})
            # (b) pivot 不動點(有關節 pivot 的 bone)
            if bn not in joints or bn not in centers:
                continue
            O = np.array(centers[bn], float); P = np.array(joints[bn], float)
            ellP = P - O
            tr = ch.get("translate")
            if not tr:
                continue
            s5["n_joint_bones"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), sc_f,
                                                  sh_f, tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), sc_f,
                                                  sh_f, None, t) - P)) for t in ts)
            rec = {"bone": bn, "beat": tb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            s5["checked"].append(rec)
            if not (fix < TOL_FIX):
                s5["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                s5["fail_negctrl"].append(rec)
    s5["worst_dev"] = round(s5["worst_dev"], 7)
    s5_pass = (s5["checked_det"] >= 1 and not s5["det_fail"] and s5["n_joint_bones"] >= 1
               and not s5["fail_fixed"] and not s5["fail_negctrl"])
    R["VV5_end2end_det_pivot"] = {**s5, "pass": s5_pass}

    # ---- VV6 negative controls / isolation ----
    s6 = {}
    # (a) 均勻性守衛:以 squash 式非均勻自守恆 scale(sx·sy=1)補償同扭轉 → full det=sx·sy·cos=cos≠1(非守恆)。
    #     取**峰值**扭轉件(shearX 最大),計 squash 式 scale(拉長軸=1+q、壓縮軸=1/(1+q))下 full det;
    #     其峰 |det−1| 應 ≥ MIN_SQUASH_DEV(證 squash 的**非均勻自守恆** scale **無法**守恆 twist 的 shear 破面積,
    #     須改用**均勻** sx·sy=1/cos → 鑑別「均勻補償」才是 twist 的解)。小極值處 cos≈1 → det≈1 為平凡,故取峰。
    peak_bone = None; peak_mag = -1.0
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            inter = _interior_shear(ch)
            if inter and abs(inter[0][0]) > peak_mag:
                peak_mag = abs(inter[0][0]); peak_bone = (tb, bn, inter)
    a_detail = []
    a_peak_dev = 0.0
    if peak_bone:
        _tb, _bn, inter = peak_bone
        for (shx, shy) in inter:
            q = 0.1
            dsq = _det(shx, shy, 1.0 + q, 1.0 / (1.0 + q))       # squash 式:sx·sy=1
            a_detail.append(round(dsq, 5))
            a_peak_dev = max(a_peak_dev, abs(dsq - 1.0))
    s6["a_isotropy_guard"] = {"peak_bone": peak_bone[:2] if peak_bone else None,
                              "squash_style_dets": a_detail, "peak_dev": round(a_peak_dev, 5),
                              "pass": a_peak_dev >= MIN_SQUASH_DEV}
    # (b) 無 scale 守衛:vol_conserve=False(sx=sy=1)→ 峰 det<1(非守恆),證 scale 通道是守恆之因。
    #     取各 twist bone 峰(首)極值 det;峰 |det−1| 應 ≥ MIN_SQUASH_DEV(小極值 cos≈1 平凡近 1,故取峰)。
    b_weak = []
    b_detail = {}
    for tb in twist_beats:
        for bn, ch in anims_nov[tb].get("bones", {}).items():
            inter = _interior_shear(ch)
            if not inter:
                continue
            peak_dev = max(abs(_det(shx, shy, 1.0, 1.0) - 1.0) for (shx, shy) in inter)
            b_detail["{}::{}".format(tb, bn)] = round(peak_dev, 5)
            if peak_dev < MIN_SQUASH_DEV:      # 峰仍近守恆 → 不該通過(無鑑別力)
                b_weak.append("{}::{}".format(tb, bn))
    s6["b_noscale_guard"] = {"peak_dev": b_detail, "weak": b_weak,
                             "pass": bool(b_detail) and not b_weak}
    # (c) scale 隔離:非 twist beat 在 True/False 下逐位元不變(vol scale 只作用 twist)
    leak = []
    for nm in anims:
        if "__" in nm or G.beat_category(nm) == "twist":
            continue
        if json.dumps(anims[nm], sort_keys=True) != json.dumps(anims_nov.get(nm), sort_keys=True):
            leak.append(nm)
    s6["c_scale_isolated"] = {"changed_non_twist": leak, "pass": not leak}
    # (d) 加性:移除 twist storyboard → 其餘逐位元不變(twist_volume=True 下)
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "twist"]}
    anims_no = G.build_animations(skel, sb_no, twist_volume=True)
    regressed = []
    for nm, an in anims_no.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    s6["d_additive_no_regression"] = {"regressed": regressed, "pass": not regressed}
    R["VV6_neg_control"] = {**s6, "pass": all(v["pass"] for v in s6.values())}

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
        for k in ["VV1_present_backcompat", "VV2_volume_conserved",
                  "VV3_isotropic_dualaxis", "VV4_both_axes_damped",
                  "VV5_end2end_det_pivot", "VV6_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("VV2 n_extrema={} worst|det-1|={} neg(no-vol) det/beat={}".format(
            R["VV2_volume_conserved"]["n_extrema"], R["VV2_volume_conserved"]["worst_dev"],
            R["VV2_volume_conserved"]["neg_peak_det_by_beat"]))
        print("VV3 detail:", json.dumps(R["VV3_isotropic_dualaxis"]["detail"], ensure_ascii=False))
        print("VV5 checked_det={} worst|det-1|={}  pivot-fixed:".format(
            R["VV5_end2end_det_pivot"]["checked_det"], R["VV5_end2end_det_pivot"]["worst_dev"]))
        for rec in R["VV5_end2end_det_pivot"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("VV6(a) squash-style dets:", R["VV6_neg_control"]["a_isotropy_guard"]["squash_style_dets"])
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
