#!/usr/bin/env python3
"""candidate G-4''''''-vol 自我驗收閘 — **體積守恆扭轉**(反相雙軸 shear 接均勻耦合體積守恆 scale)端到端(純 CPU)。

補 (G-4'''''') 一路留到現在的 honest boundary:twist(反相雙軸阻尼 shear)的 Spine local 一般仿射
det = scaleX·scaleY·cos(shearX−shearY);純雙軸 shear(scaleX=scaleY=1)時 **det = cos(shearX−shearY) ≠ 1**
→ 擰轉會**變面積**(擰毛巾愈用力、面積縮愈多)。本 candidate 讓 twist 節拍(twist_vol)加**均勻耦合體積守恆
scale**(每 shear 極值 scaleX=scaleY=1/√cos(shearX−shearY))使 **det ≡ 1** → **擰而不變面積**:shear 與 scale
兩通道同時被生成器驅動、塞滿一般仿射四自由度(rotate 由 pivot 補償、非均勻/斜切由兩條 shear 軸)且**體積守恆**。

**為何均勻(sx==sy)而非 squash 的非均勻**:det 只約束 scaleX·scaleY 之積;均勻 split 是**唯一不另引入任意
各向異性**的守恆補償 —— 一般仿射的非相似性(斜切/各向異性)全由**兩條 shear 軸**給定,scale 僅補回 shear
造成的面積損失。非均勻 split(選某各向異性比)守恆同樣成立,但屬手感 A 類主觀選擇(honest boundary,見文末)。

**與 squash(G-4'''')的分工**:squash = shearX + **非均勻**耦合 scale(scaleX≠scaleY,scaleX·scaleY≡1);
twist_vol = 反相**雙軸** shear + **均勻**耦合 scale(scaleX==scaleY,det≡1)。兩者皆體積守恆但幾何互補
(squash 是斜拉擠壓、twist_vol 是等積扭轉)。

真值/fixture 與 (E/H/I/J/G-4'/G-4''''/G-4'''''') 一致:從**先驗庫**(slot_bigwin,新增 twist_vol beat)經
`analyze_target` → **真實 build_spine robot 骨架** → `build_animations` 端到端量。主秀運動無唯一正解
(PROPOSAL 手感),閘驗**客觀結構簽章(雙軸阻尼振盪 + 反相耦合 + 體積守恆 det≡1)+ 端到端不動點且守恆存活**,
非美感;負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  VV1 present + tri-channel(crux): twist_vol beat 直出、finite、有 bone,且 ≥1 bone **同時**帶 shear(雙軸:
                                   shearX 峰、shearY 峰皆 ≥ MIN_SHEAR)**與** scale 通道。
  VV2 twist 簽章保持              : 每個 twist_vol bone 的 shearX 與 shearY 各自阻尼振盪(首尾 0 + 繞 0 變號 ≥3 +
                                   相繼極值遞減),且每內部極值反相(shearX·shearY<0)—— 加 scale 不擾動扭轉幾何。
  VV3 體積守恆(crux)            : 每個 twist_vol bone 的**每個** shear 關鍵幀:Spine local
                                   det = scaleX·scaleY·cos(shearX−shearY) 滿足 |det−1| ≤ TOL_VOL → 擰而不變面積。
  VV4 負對照 / 均勻守衛(crux)   : (a)**純 shear 守衛**:同 shear 但無耦合 scale(scaleX=scaleY=1,即舊 twist)→
                                   峰極值 |det−1| ≥ NEG_DET(擰轉變面積)證耦合 scale 是守恆關鍵;
                                   (b)**非守恆守衛**:只放大一軸(scaleX=1/√cos、scaleY=1,積≠1/cos)→ |det−1| ≥ NEG_DET
                                   證守恆需**特定** sx·sy=1/cos 耦合、非任意 scale;(c)**均勻守衛**:twist_vol scale
                                   逐幀 scaleX==scaleY(等向補償,非 squash 的非均勻)→ 與 squash 幾何區隔。
  VV5 identity 介面 + 向後相容    : (a)sample(0)/sample(dur) 各 bone identity、shear 首尾 (0,0)、scale 首尾 (1,1);
                                   (b)**純 twist beat 逐位元不變且無 scale 通道**(vol 為 opt-in,舊 twist 向後相容);
                                   (c)**加性**:移除 twist_vol 的 storyboard → 其餘 beat 逐位元不變(零回歸)。
  VV6 端到端守恆存活             : `build_spine --shear-pivot`(真實 robot)產 twist_vol 帶補償;凡有關節 pivot 的
                                   bone pivot 殘差 < TOL_FIX(vs 內建負對照未補償大位移);且**建出的 twist_vol 動畫
                                   det ≡ 1 仍保持**(pivot 補償為純平移、不改 det → 體積守恆端到端存活)。

用法:
  python3 validate_twist_vol.py            # 摘要
  python3 validate_twist_vol.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import math
import numpy as np
import spine_anim as SA
import gen_animations as G
# 復用 G-4' 的 shearX 讀取與阻尼簽章判準 + G-4'''''' 的雙軸讀取/反相判準(與 shear-gen / twist-gen 閘完全一致)
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_twist_gen import _shear_y, _shear_xy, _interior_shear, _tw3_eval, _has_shear_y
from validate_shear_pivot import _world           # 真實 Spine local(含雙軸 shear + scale)世界座標求值
from pivot_rotation import transform_matrix_full  # 真實 Spine local 2×2(det 量體積)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,twist_vol 兩軸峰下限(shearY 峰 = 0.7×shearX 峰,head 最小 7° → 餘裕)
TOL_VOL = 2e-4      # |det−1| 上限(scale 4 位捨入下實測 worst ≈9e-5;同 squash SC2 守恆容差)
TOL_VOL_E2E = 1e-2  # 端到端 |det−1| 上限(--shear-pivot 對關節 bone 把 shear/scale 密網格重取樣 → 網格不落在
                    # 原極值上,於極值時刻取樣有 ~5e-3 內插殘差;仍 >20× 低於未守恆 baseline 0.11。非重取樣 bone 走 TOL_VOL)
NEG_DET = 0.02      # 負對照峰極值 |det−1| 下限(純 shear head 最小峰 A=10 → 0.044;effect A=16 → 0.11 → 餘裕)
TOL_FIX = 0.5       # px,pivot 不動點殘差上限(同 G-4/G-4'/G-4''''/twist-gen)
MIN_NEG = 5.0       # px,VV6 負對照(未補償)位移下限
NEG_RATIO = 20.0    # 負對照/不動點 位移比下限


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


def _twist_vol_beats(anims):
    """體積守恆扭轉 beat(twist_vol):beat_category 仍為 twist,但名帶 'vol' 且非 tier 變體。"""
    return [nm for nm in anims if "__" not in nm and "vol" in nm.lower()
            and G.beat_category(nm) == "twist"]


def _scale_xy(ch):
    """bone channels → [(scaleX, scaleY)] 關鍵幀序列(無 scale 通道回 [])。"""
    fr = ch.get("scale")
    return [(f["x"], f["y"]) for f in fr] if fr else []


def _det(shx, shy, sx, sy):
    """真實 Spine local 一般仿射 det(θ=0)= scaleX·scaleY·cos(shearX−shearY)。"""
    a, b, c, d = transform_matrix_full(0.0, sx, sy, shx, shy)
    return a * d - b * c


def _det_series(ch):
    """對齊 shear 與 scale 關鍵幀(同 time),回傳每幀 det(無 scale → 各幀 sx=sy=1)。"""
    sh = ch.get("shear") or []
    sc = {round(f["time"], 4): (f["x"], f["y"]) for f in (ch.get("scale") or [])}
    out = []
    for f in sh:
        sx, sy = sc.get(round(f["time"], 4), (1.0, 1.0))
        out.append(_det(f["x"], f["y"], sx, sy))
    return out


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    tv_beats = _twist_vol_beats(anims)
    R = {}

    # ---- VV1 present + tri-channel (shear dual-axis + coupled scale) ----
    s1 = {"twist_vol_beats": tv_beats, "not_finite": [], "no_bones": [], "no_tri_channel": [],
          "weak_shearx": [], "weak_sheary": [], "peak_by_beat": {}}
    for tb in tv_beats:
        an = anims[tb]
        if not SA.all_finite(an):
            s1["not_finite"].append(tb)
        if not an.get("bones"):
            s1["no_bones"].append(tb)
        tri = {bn: ch for bn, ch in an.get("bones", {}).items()
               if _shear_xy(ch) and _scale_xy(ch)}
        if not tri:
            s1["no_tri_channel"].append(tb); continue
        shx_pk = max(max(abs(v) for v in _shear_x(ch)) for ch in tri.values())
        shy_pk = max(max(abs(v) for v in _shear_y(ch)) for ch in tri.values())
        s1["peak_by_beat"][tb] = {"shearX": round(shx_pk, 3), "shearY": round(shy_pk, 3),
                                  "bones_tri": len(tri)}
        if shx_pk < MIN_SHEAR:
            s1["weak_shearx"].append(tb)
        if shy_pk < MIN_SHEAR:
            s1["weak_sheary"].append(tb)
    s1_pass = (bool(tv_beats) and not s1["not_finite"] and not s1["no_bones"]
               and not s1["no_tri_channel"] and not s1["weak_shearx"] and not s1["weak_sheary"])
    R["VV1_present_tri_channel"] = {**s1, "pass": s1_pass}

    # ---- VV2 twist signature preserved (both axes damped + counter-phase) ----
    s2 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "not_counterphase": []}
    for tb in tv_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            for axis, vals in (("x", _shear_x(ch)), ("y", _shear_y(ch))):
                if not vals:
                    continue
                key = "{}::{}::{}".format(tb, bn, axis)
                if not (abs(vals[0]) < 1e-6 and abs(vals[-1]) < 1e-6):
                    s2["bad_endpoints"].append(key)
                if _sign_changes_zero(vals) < 3:
                    s2["few_sign_changes"].append(key)
                if not _extrema_mags_decreasing(vals):
                    s2["not_damped"].append(key)
            interior = _interior_shear(ch)
            if interior and _has_shear_y(ch):
                cp_ok, _, _ = _tw3_eval(interior)
                if not cp_ok:
                    s2["not_counterphase"].append("{}::{}".format(tb, bn))
    s2_pass = (bool(tv_beats) and not s2["bad_endpoints"] and not s2["few_sign_changes"]
               and not s2["not_damped"] and not s2["not_counterphase"])
    R["VV2_twist_signature_preserved"] = {**s2, "pass": s2_pass}

    # ---- VV3 volume conservation: det ≡ 1 at every shear keyframe (crux) ----
    s3 = {"violations": [], "worst_by_bone": {}, "worst": 0.0}
    for tb in tv_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            if not _scale_xy(ch):
                continue
            devs = [abs(d - 1.0) for d in _det_series(ch)]
            w = max(devs) if devs else 0.0
            s3["worst_by_bone"]["{}::{}".format(tb, bn)] = round(w, 6)
            s3["worst"] = max(s3["worst"], w)
            if w > TOL_VOL:
                s3["violations"].append({"bone": "{}::{}".format(tb, bn), "worst_det_dev": round(w, 6)})
    s3["worst"] = round(s3["worst"], 6)
    s3_pass = (bool(s3["worst_by_bone"]) and not s3["violations"])
    R["VV3_volume_conservation"] = {**s3, "tol": TOL_VOL, "pass": s3_pass}

    # ---- VV4 neg-controls / uniform guard (crux) ----
    s4 = {}
    # 取一支真實 twist_vol bone 的內部極值 (shx,shy) 當基準幾何
    ref = None
    for tb in tv_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            iv = _interior_shear(ch)
            if iv:
                ref = iv; break
        if ref:
            break
    # (a) 純 shear 守衛:同 shear 但 scale=identity(舊 twist)→ |det−1| 峰 ≥ NEG_DET(擰轉變面積)
    dev_plain = max(abs(_det(shx, shy, 1.0, 1.0) - 1.0) for (shx, shy) in ref) if ref else 0.0
    s4["a_plain_shear_guard"] = {"peak_det_dev": round(dev_plain, 4), "pass": dev_plain >= NEG_DET}
    # (b) 非守恆守衛:只放大一軸(sx=1/√cos、sy=1,積≠1/cos)→ |det−1| 峰 ≥ NEG_DET(需特定耦合)
    def _one_axis(shx, shy):
        c = math.cos(math.radians(shx - shy)); sx = 1.0 / math.sqrt(c)
        return abs(_det(shx, shy, sx, 1.0) - 1.0)
    dev_one = max(_one_axis(shx, shy) for (shx, shy) in ref) if ref else 0.0
    s4["b_nonconserving_guard"] = {"peak_det_dev": round(dev_one, 4), "pass": dev_one >= NEG_DET}
    # (c) 均勻守衛:twist_vol scale 逐幀 scaleX==scaleY(等向,非 squash 非均勻)
    non_uniform = []
    for tb in tv_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            for (sx, sy) in _scale_xy(ch):
                if abs(sx - sy) > 1e-9:
                    non_uniform.append("{}::{}".format(tb, bn)); break
    s4["c_uniform_guard"] = {"non_uniform_bones": non_uniform, "pass": not non_uniform}
    s4_pass = all(v["pass"] for v in s4.values())
    R["VV4_neg_control_uniform"] = {**s4, "pass": s4_pass}

    # ---- VV5 identity interface + backward-compat + additivity ----
    s5 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for tb in tv_beats:
        an = anims[tb]
        dur = SA.duration(an)
        start = SA.sample(an, 0.0)["bones"]
        end = SA.sample(an, dur)["bones"]
        if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
            s5["bad_interface"].append(tb)
        for bn, ch in an.get("bones", {}).items():
            xy = _shear_xy(ch)
            if xy and (abs(xy[0][0]) > 1e-6 or abs(xy[0][1]) > 1e-6
                       or abs(xy[-1][0]) > 1e-6 or abs(xy[-1][1]) > 1e-6):
                s5["shear_endpoints_nonzero"].append("{}::{}".format(tb, bn))
            sc = _scale_xy(ch)
            if sc and (abs(sc[0][0] - 1) > 1e-6 or abs(sc[0][1] - 1) > 1e-6
                       or abs(sc[-1][0] - 1) > 1e-6 or abs(sc[-1][1] - 1) > 1e-6):
                s5["scale_endpoints_nonident"].append("{}::{}".format(tb, bn))
    # (b) 純 twist 向後相容:移除 twist_vol 的 storyboard → 純 twist beat 逐位元不變且**無 scale 通道**
    sb_no = {**sb, "beats": [b for b in sb["beats"] if "vol" not in b["beat"].lower()]}
    anims_no = G.build_animations(skel, sb_no)
    plain_twist = [nm for nm in anims_no if "__" not in nm and "vol" not in nm.lower()
                   and G.beat_category(nm) == "twist"]
    plain_has_scale = []
    plain_changed = []
    for nm in plain_twist:
        for bn, ch in anims_no[nm].get("bones", {}).items():
            if ch.get("scale"):
                plain_has_scale.append("{}::{}".format(nm, bn))
        if json.dumps(anims_no[nm], sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            plain_changed.append(nm)
    s5["plain_twist_has_scale"] = plain_has_scale
    s5["plain_twist_changed"] = plain_changed
    # (c) 加性:移除 twist_vol → 其餘 beat 逐位元不變
    regressed = [nm for nm, an in anims_no.items()
                 if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True)]
    s5["additive_regressed"] = regressed
    s5["removed_beats"] = [b["beat"] for b in sb["beats"] if "vol" in b["beat"].lower()]
    s5_pass = (bool(tv_beats) and not s5["bad_interface"] and not s5["shear_endpoints_nonzero"]
               and not s5["scale_endpoints_nonident"] and not s5["plain_twist_has_scale"]
               and not s5["plain_twist_changed"] and not s5["additive_regressed"])
    R["VV5_interface_backcompat_additive"] = {**s5, "pass": s5_pass}

    # ---- VV6 end-to-end: pivot-fixed AND volume conservation survives --shear-pivot ----
    import build_spine
    out = "/tmp/twist_vol_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    # 原始 twist_vol 極值時刻(pre-pivot base beat 的內部 shear 關鍵幀 time)—— 守恆在極值處量最嚴
    # (該處 shear 最大 → 未守恆時 |det−1| 最大;純 twist 於此達 0.11 baseline)。--shear-pivot 對關節 bone
    # 密網格重取樣後,於這些極值時刻**取樣**(SA._interp)建出的 shear/scale 算 det → 驗守恆是否端到端存活。
    base_tv = _twist_vol_beats(anims)
    ext_times = []
    if base_tv:
        for ch in anims[base_tv[0]].get("bones", {}).values():
            sh = ch.get("shear")
            if sh and len(sh) >= 3:
                ext_times = [round(f["time"], 4) for f in sh[1:-1]]
                break

    def _det_sampled(ch, t):
        shd = SA._interp(ch["shear"], t, ["x", "y"])
        scd = SA._interp(ch["scale"], t, ["x", "y"])
        return _det(shd["x"], shd["y"], scd["x"], scd["y"])

    s6 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0,
          "det_violations": [], "worst_det_dev_e2e": 0.0, "ext_times": ext_times}
    for tb in _twist_vol_beats(sp_skel["animations"]):
        an = sp_skel["animations"][tb]
        for bn, ch in an.get("bones", {}).items():
            # 端到端守恆:於原極值時刻取樣建出的 shear+scale 算 det。pivot 補償為純平移不改 det,
            # 但關節 bone 的 shear/scale 被密網格重取樣 → 極值處內插殘差(~5e-3),非關節 bone 保原 6 幀 → 精確守恆。
            if ch.get("shear") and ch.get("scale") and ext_times:
                densified = len(ch["shear"]) > 12   # 關節 bone 被重取樣(6 → 49);非關節保 6 幀
                tol = TOL_VOL_E2E if densified else TOL_VOL
                w = max(abs(_det_sampled(ch, t) - 1.0) for t in ext_times)
                s6["worst_det_dev_e2e"] = max(s6["worst_det_dev_e2e"], w)
                if w > tol:
                    s6["det_violations"].append({"bone": "{}::{}".format(tb, bn),
                                                 "worst_det_dev": round(w, 6),
                                                 "densified": densified, "tol": tol})
            if bn not in joints or bn not in centers:
                continue
            O = np.array(centers[bn], float); P = np.array(joints[bn], float)
            ellP = P - O
            tr = ch.get("translate")
            if not tr:
                continue
            s6["n_joint_bones"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            rec = {"bone": bn, "beat": tb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2)}
            s6["checked"].append(rec)
            if not (fix < TOL_FIX):
                s6["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                s6["fail_negctrl"].append(rec)
    s6["worst_det_dev_e2e"] = round(s6["worst_det_dev_e2e"], 6)
    s6_pass = (s6["n_joint_bones"] >= 1 and not s6["fail_fixed"] and not s6["fail_negctrl"]
               and not s6["det_violations"])
    R["VV6_end2end_conserving_pivot_fixed"] = {**s6, "pass": s6_pass}

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
        for k in ["VV1_present_tri_channel", "VV2_twist_signature_preserved",
                  "VV3_volume_conservation", "VV4_neg_control_uniform",
                  "VV5_interface_backcompat_additive", "VV6_end2end_conserving_pivot_fixed"]:
            print("{:38s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("VV1 peaks:", R["VV1_present_tri_channel"]["peak_by_beat"])
        print("VV3 worst |det-1|:", R["VV3_volume_conservation"]["worst"], "(tol", TOL_VOL, ")")
        print("VV4 neg-controls:",
              "plain", R["VV4_neg_control_uniform"]["a_plain_shear_guard"]["peak_det_dev"],
              "| one-axis", R["VV4_neg_control_uniform"]["b_nonconserving_guard"]["peak_det_dev"],
              "| uniform_ok", R["VV4_neg_control_uniform"]["c_uniform_guard"]["pass"])
        print("VV6 end-to-end worst |det-1|:", R["VV6_end2end_conserving_pivot_fixed"]["worst_det_dev_e2e"])
        for rec in R["VV6_end2end_conserving_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
