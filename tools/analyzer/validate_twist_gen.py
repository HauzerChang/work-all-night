#!/usr/bin/env python3
"""candidate G-4'''''' 自我驗收閘 — 生成器產出**雙軸 shear(shearX 且 shearY)**旋擰基元端到端(純 CPU)。

wobble/squash 系列一路留到現在的**最後一條 shear 通道 honest boundary**:G-4'(`validate_shear_gen.py`)
的 wobble 只產**純 shearX**、G-4''''(`validate_squash_gen.py`)的 squash 產 shearX + 耦合非均勻 scale ——
**兩者 shearY≡0**。真實 Spine local M=[[cos(θ+shx)sx, cos(θ+90+shy)sy],[sin(θ+shx)sx, sin(θ+90+shy)sy]]:
shearX 只擾第一欄(a,c)的角、shearY 只擾第二欄(b,d)的角 → **只有 shearX 與 shearY 同時非零**,兩欄
的角才各自獨立、M 才是**真正的一般 2×2(四自由度全填)**;只產 shearX 時第二欄恆與第一欄近正交。本閘
(G-4'''''')驗證最後一段**已接上**:生成器 `gen_twist`(旋擰果凍晃)實際產出**雙軸 shear** —— shear 向量
(shearX,shearY)以 90° 步旋擰掃過(正交:一軸峰時另一軸≈0),並掛旋轉體積守恆 squash;`build_spine
--shear-pivot`(include_shear=True 讀 shy)端到端把此**真正一般仿射**繞關節 pivot 補償而 pivot 精確不動
(G-4 通用 Δ=(M−I)(O−P) 第一次被**生成器產的雙軸 shear** 驅動)。

真值/fixture 與 (E/H/I/J/G-4'/G-4'''') 一致:從**先驗庫**(slot_bigwin,新增 twist beat)經
`analyze_target` → **真實 build_spine robot 骨架** → `build_animations` 端到端量。主秀運動無唯一正解
(PROPOSAL 手感),閘驗**客觀結構簽章(雙軸阻尼振盪 + 旋擰正交 + 旋轉體積守恆)+ 端到端不動點**,
非美感;負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  TW1 present + 雙軸 shear(crux) : twist beat 直出、finite、有 bone,且 ≥1 bone **同時**帶 shearX
                                   **且** shearY(兩軸皆非零)與 scale 通道;峰 |shearX|≥MIN_SHEAR **且**
                                   峰 |shearY|≥MIN_SHEAR(← 產線第一次 shearY≢0)**且** scale 峰非均勻
                                   |scaleX−scaleY|≥MIN_ANISO。
  TW2 雙軸阻尼振盪                : 每 twist bone 的 shearX **與** shearY **各自**:(a)首尾 0;(b)繞 0
                                   變號 ≥3;(c)相繼極值幅度嚴格遞減(阻尼)—— 兩軸皆復用 G-4' 判準。
  TW3 旋擰/正交(crux)           : 每 twist bone 存在幀 |shearY|≥MIN_SHEAR 而 |shearX|<QUAD_TOL(shearY
                                   主導)**且**存在幀 |shearX|≥MIN_SHEAR 而 |shearY|<QUAD_TOL(shearX 主導)
                                   → shear 向量方向確實**旋轉**(非固定斜向)。負對照:對角 shear
                                   (shearY=c·shearX 共線)兩軸同時過零 → 無此錯位幀。
  TW4 旋轉體積守恆 squash        : 每 twist bone 的**每個** scale 極值幀:(a)scaleX·scaleY≈1(面積守恆);
                                   (b)≥1 極值 |scaleX−scaleY|≥MIN_ANISO(非均勻=真擠壓);(c)拉長軸**在
                                   X/Y 間交替**(既有 scaleX>scaleY 幀也有 scaleX<scaleY 幀 → 旋轉,非固定軸)。
  TW5 identity 介面(可插 Loop)  : sample(0)/sample(dur) 各 bone identity,且 shear 首尾 (0,0) + scale 首尾 (1,1)。
  TW6 端到端一般仿射 pivot 不動   : `build_spine --shear-pivot`(真實 robot)產 twist 帶補償;凡有關節 pivot
                                   的 bone,pivot 殘差 < TOL_FIX 且 M 於雙軸 shear 幀為**真一般仿射**
                                   (anisotropy≥MIN_ANISO_M 且 shy≠0);內建負對照=未補償(繞件中心)大位移。
  TW7 負對照/隔離                : (a)**shearY≡0 守衛**:合成純 shearX(wobble)→ TW1 shearY-present FALSE
                                   且 TW3 旋擰 FALSE(證閘測「雙軸」非「有 shear 即可」);(b)**對角 shear
                                   守衛**:合成 shearY=0.5·shearX(共線)→ TW3 旋擰 FALSE(兩軸同時過零);
                                   (c)**固定軸 squash 守衛**:合成 scaleX 恆≥scaleY → TW4 旋轉 FALSE;
                                   (d)**隔離**:非 twist beat 皆非「同時帶 shearX 且 shearY」(wobble/squash
                                   的 shearY≡0 → twist 獨佔雙軸);(e)**加性**:移除 twist 的 storyboard →
                                   其餘 beat 逐位元不變(零回歸)。

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
# 復用 G-4' 的 shearX 讀取與阻尼簽章判準,確保與 shear-gen / squash-gen 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import _scale_xy, _interior_scale   # 復用 squash 的 scale 讀取
from validate_shear_pivot import _world                      # 真實 Spine local(含雙軸 shear)世界座標
from pivot_rotation import transform_matrix_full             # 真實 Spine local 2×2(判 M 是否一般仿射)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,twist 峰值 |shearX|/|shearY| 下限
QUAD_TOL = 1.0      # 度,正交判定:主導軸為峰時另一軸須 <此值(twist 於極值時另一軸恰=0)
MIN_ANISO = 0.05    # scale 非均勻 |scaleX−scaleY| 峰下限
MIN_ANISO_M = 0.05  # M 的奇異值差(anisotropy)下限,證雙軸 shear 幀為真一般仿射
TOL_VOL = 0.02      # 體積守恆 |scaleX·scaleY − 1| 上限(實測 <1e-4)
TOL_FIX = 0.5       # px,pivot 不動點殘差上限(同 G-4/G-4'/G-4'''')
MIN_NEG = 5.0       # px,TW6 負對照(未補償)位移下限
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


def _tw3_rotary(shx, shy):
    """給對齊的 (shearX, shearY) 序列 → (rotary_ok, detail)。純函式(可對合成負對照施同一判準)。

    rotary = 存在幀 shearY 主導(|shy|≥MIN_SHEAR 而 |shx|<QUAD_TOL)且存在幀 shearX 主導
    (|shx|≥MIN_SHEAR 而 |shy|<QUAD_TOL)→ shear 向量方向確實旋轉(過兩軸)。共線(對角)shear
    兩軸同時過零 → 無「一軸大另一軸≈0」的錯位幀 → FALSE。"""
    n = min(len(shx), len(shy))
    y_dom = any(abs(shy[i]) >= MIN_SHEAR and abs(shx[i]) < QUAD_TOL for i in range(n))
    x_dom = any(abs(shx[i]) >= MIN_SHEAR and abs(shy[i]) < QUAD_TOL for i in range(n))
    return (y_dom and x_dom), {"y_dominant_frame": y_dom, "x_dominant_frame": x_dom}


def _tw4_rotating_squash(interior):
    """給內部 scale 極值 [(sx,sy)] → (volume_ok, aniso_ok, rotating_ok, detail)。
    純函式 → 可對真實 twist 與合成負對照(固定軸 squash)施同一判準(閘可信)。"""
    if not interior:
        return False, False, False, {"prod": [], "aniso": [], "sign": []}
    prod = [sx * sy for (sx, sy) in interior]
    aniso = [abs(sx - sy) for (sx, sy) in interior]
    sign = [(1 if sx > sy + 1e-6 else (-1 if sx < sy - 1e-6 else 0)) for (sx, sy) in interior]
    volume_ok = all(abs(p - 1.0) <= TOL_VOL for p in prod)
    aniso_ok = max(aniso) >= MIN_ANISO
    rotating_ok = (1 in sign) and (-1 in sign)   # 拉長軸既在 X 也在 Y(旋轉)→ 非固定軸 squash
    detail = {"prod": [round(p, 5) for p in prod], "aniso": [round(a, 4) for a in aniso], "sign": sign}
    return volume_ok, aniso_ok, rotating_ok, detail


def _biaxial_scale(chans):
    """bone 是否同時帶非零 shearX 且非零 shearY(雙軸 shear)。"""
    shx = _shear_x(chans); shy = _shear_y(chans)
    return (any(abs(v) > 1e-6 for v in shx) and any(abs(v) > 1e-6 for v in shy))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    twist_beats = _twist_beats(anims)
    R = {}

    # ---- TW1 present + biaxial shear emitted (crux) ----
    s1 = {"twist_beats": twist_beats, "not_finite": [], "no_bones": [], "no_biaxial": [],
          "weak_shearx": [], "weak_sheary": [], "weak_aniso": [], "peak_by_beat": {}}
    for tb in twist_beats:
        an = anims[tb]
        if not SA.all_finite(an):
            s1["not_finite"].append(tb)
        if not an.get("bones"):
            s1["no_bones"].append(tb)
        biax = {bn: ch for bn, ch in an.get("bones", {}).items()
                if _biaxial_scale(ch) and _scale_xy(ch)}
        if not biax:
            s1["no_biaxial"].append(tb); continue
        xpk = max(max(abs(v) for v in _shear_x(ch)) for ch in biax.values())
        ypk = max(max(abs(v) for v in _shear_y(ch)) for ch in biax.values())
        anpk = max(max(abs(sx - sy) for (sx, sy) in _scale_xy(ch)) for ch in biax.values())
        s1["peak_by_beat"][tb] = {"shearX": round(xpk, 3), "shearY": round(ypk, 3), "aniso": round(anpk, 4)}
        if xpk < MIN_SHEAR:
            s1["weak_shearx"].append(tb)
        if ypk < MIN_SHEAR:
            s1["weak_sheary"].append(tb)
        if anpk < MIN_ANISO:
            s1["weak_aniso"].append(tb)
    s1_pass = (bool(twist_beats) and not s1["not_finite"] and not s1["no_bones"]
               and not s1["no_biaxial"] and not s1["weak_shearx"]
               and not s1["weak_sheary"] and not s1["weak_aniso"])
    R["TW1_present_biaxial_shear"] = {**s1, "pass": s1_pass}

    # ---- TW2 dual-axis damped oscillation (both shearX and shearY) ----
    s2 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "detail": {}}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            for axis, vals in (("shX", _shear_x(ch)), ("shY", _shear_y(ch))):
                if not vals or all(abs(v) < 1e-9 for v in vals):
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
    # 需同時涵蓋 shX 與 shY(證雙軸皆阻尼振盪,非只 shearX)
    have_x = any(k.endswith("::shX") for k in s2["detail"])
    have_y = any(k.endswith("::shY") for k in s2["detail"])
    s2_pass = (have_x and have_y and not s2["bad_endpoints"]
               and not s2["few_sign_changes"] and not s2["not_damped"])
    R["TW2_dual_axis_damped"] = {**s2, "have_shearX": have_x, "have_shearY": have_y, "pass": s2_pass}

    # ---- TW3 rotary / quadrature (crux) ----
    s3 = {"not_rotary": [], "detail": {}}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            shx = _shear_x(ch); shy = _shear_y(ch)
            if not shx or not shy:
                continue
            key = "{}::{}".format(tb, bn)
            rot_ok, det = _tw3_rotary(shx, shy)
            s3["detail"][key] = det
            if not rot_ok:
                s3["not_rotary"].append(key)
    s3_pass = bool(s3["detail"]) and not s3["not_rotary"]
    R["TW3_rotary_quadrature"] = {**s3, "pass": s3_pass}

    # ---- TW4 rotating volume-preserving squash ----
    s4 = {"bad_volume": [], "no_aniso": [], "not_rotating": [], "detail": {}}
    for tb in twist_beats:
        for bn, ch in anims[tb].get("bones", {}).items():
            interior = _interior_scale(ch)
            if not interior or not _shear_x(ch):
                continue
            key = "{}::{}".format(tb, bn)
            vok, aok, rok, det = _tw4_rotating_squash(interior)
            s4["detail"][key] = det
            if not vok:
                s4["bad_volume"].append(key)
            if not aok:
                s4["no_aniso"].append(key)
            if not rok:
                s4["not_rotating"].append(key)
    s4_pass = (bool(s4["detail"]) and not s4["bad_volume"]
               and not s4["no_aniso"] and not s4["not_rotating"])
    R["TW4_rotating_squash"] = {**s4, "pass": s4_pass}

    # ---- TW5 identity interface ----
    s5 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for tb in twist_beats:
        an = anims[tb]
        dur = SA.duration(an)
        start = SA.sample(an, 0.0)["bones"]
        end = SA.sample(an, dur)["bones"]
        if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
            s5["bad_interface"].append(tb)
        for bn, ch in an.get("bones", {}).items():
            shx = _shear_x(ch); shy = _shear_y(ch)
            if (shx and (abs(shx[0]) > 1e-6 or abs(shx[-1]) > 1e-6)) or \
               (shy and (abs(shy[0]) > 1e-6 or abs(shy[-1]) > 1e-6)):
                s5["shear_endpoints_nonzero"].append("{}::{}".format(tb, bn))
            xy = _scale_xy(ch)
            if xy and (abs(xy[0][0] - 1.0) > 1e-6 or abs(xy[0][1] - 1.0) > 1e-6
                       or abs(xy[-1][0] - 1.0) > 1e-6 or abs(xy[-1][1] - 1.0) > 1e-6):
                s5["scale_endpoints_nonident"].append("{}::{}".format(tb, bn))
    R["TW5_identity_interface"] = {**s5, "pass": (not s5["bad_interface"]
                                                  and not s5["shear_endpoints_nonzero"]
                                                  and not s5["scale_endpoints_nonident"])}

    # ---- TW6 end-to-end general-affine pivot-fixed via build_spine --shear-pivot ----
    import build_spine
    out = "/tmp/twist_gen_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    s6 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "fail_general_affine": [], "n_joint_bones": 0}
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
            s6["n_joint_bones"] += 1
            ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
            fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), tr, t) - P)) for t in ts)
            neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                  ch.get("shear"), None, t) - P)) for t in ts)
            # M 是否真一般仿射:取雙軸 shear 峰幀(shy 絕對值最大者),算 M 的 anisotropy(奇異值差)
            sh = ch.get("shear") or []
            gen_ok, aniso_M, shy_at = False, 0.0, 0.0
            if sh:
                fpk = max(sh, key=lambda f: abs(f.get("y", 0.0)))
                tpk = fpk["time"]
                ang = SA._interp(ch["rotate"], tpk, ["angle"])["angle"] if ch.get("rotate") else 0.0
                if ch.get("scale"):
                    sd = SA._interp(ch["scale"], tpk, ["x", "y"]); sxv, syv = sd["x"], sd["y"]
                else:
                    sxv = syv = 1.0
                shd = SA._interp(sh, tpk, ["x", "y"]); shxv, shyv = shd["x"], shd["y"]
                a, bb, c, d = transform_matrix_full(ang, sxv, syv, shxv, shyv)
                M = np.array([[a, bb], [c, d]], float)
                sv = np.linalg.svd(M, compute_uv=False)
                aniso_M = float(sv[0] - sv[-1]); shy_at = float(shyv)
                gen_ok = (aniso_M >= MIN_ANISO_M) and (abs(shyv) > 1e-6)
            rec = {"bone": bn, "beat": tb, "arm": round(float(np.linalg.norm(ellP)), 1),
                   "fixed": round(fix, 4), "negctrl": round(neg, 2),
                   "anisoM": round(aniso_M, 4), "shyPk": round(shy_at, 3)}
            s6["checked"].append(rec)
            if not (fix < TOL_FIX):
                s6["fail_fixed"].append(rec)
            if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                s6["fail_negctrl"].append(rec)
            if not gen_ok:
                s6["fail_general_affine"].append(rec)
    s6_pass = (s6["n_joint_bones"] >= 1 and not s6["fail_fixed"]
               and not s6["fail_negctrl"] and not s6["fail_general_affine"])
    R["TW6_end2end_affine_pivot_fixed"] = {**s6, "pass": s6_pass}

    # ---- TW7 negative controls / isolation ----
    s7 = {}
    # (a) shearY≡0 守衛:純 shearX(wobble)→ 非雙軸 + 非旋擰
    shx_only = [16.0, 0.0, -8.0, 0.0, 4.0, 0.0]
    shy_zero = [0.0] * len(shx_only)
    rot_a, _ = _tw3_rotary(shx_only, shy_zero)
    biax_a = any(abs(v) > 1e-6 for v in shx_only) and any(abs(v) > 1e-6 for v in shy_zero)
    s7["a_sheary_zero_guard"] = {"biaxial": biax_a, "rotary": rot_a, "pass": (not biax_a) and (not rot_a)}
    # (b) 對角 shear 守衛:shearY=0.5·shearX(共線)→ 旋擰 FALSE(兩軸同時過零,無錯位幀)
    shx_diag = [16.0, 8.0, -8.0, -4.0, 4.0, 2.0]
    shy_diag = [0.5 * v for v in shx_diag]
    rot_b, det_b = _tw3_rotary(shx_diag, shy_diag)
    s7["b_diagonal_shear_guard"] = {"rotary": rot_b, "detail": det_b, "pass": not rot_b}
    # (c) 固定軸 squash 守衛:scaleX 恆 ≥ scaleY(不旋轉)→ TW4 rotating FALSE
    fixed_axis = [(1.14, 1.0 / 1.14), (1.07, 1.0 / 1.07), (1.035, 1.0 / 1.035)]
    _, a_fx, rot_fx, _ = _tw4_rotating_squash(fixed_axis)
    s7["c_fixed_axis_squash_guard"] = {"aniso_ok": a_fx, "rotating": rot_fx,
                                       "pass": a_fx and (not rot_fx)}
    # (d) 隔離:非 twist beat 皆非「同時帶 shearX 且 shearY」(wobble/squash 的 shearY≡0)
    leak = []
    for nm, an in anims.items():
        if "__" in nm or G.beat_category(nm) == "twist":
            continue
        for bn, ch in an.get("bones", {}).items():
            if _biaxial_scale(ch):
                leak.append((nm, bn))
    s7["d_biaxial_isolated"] = {"leaked": leak, "pass": not leak}
    # (e) 加性:移除 twist 的 storyboard → 其餘 beat 逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "twist"]}
    anims_no = G.build_animations(skel, sb_no)
    regressed = []
    for nm, an in anims_no.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    s7["e_additive_no_regression"] = {"regressed": regressed,
                                      "removed_beats": [b["beat"] for b in sb["beats"]
                                                        if G.beat_category(b["beat"]) == "twist"],
                                      "pass": not regressed}
    R["TW7_neg_control"] = {**s7, "pass": all(v["pass"] for v in s7.values())}

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
        for k in ["TW1_present_biaxial_shear", "TW2_dual_axis_damped", "TW3_rotary_quadrature",
                  "TW4_rotating_squash", "TW5_identity_interface",
                  "TW6_end2end_affine_pivot_fixed", "TW7_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("TW1 peaks by beat:", R["TW1_present_biaxial_shear"]["peak_by_beat"])
        print("TW3 rotary detail:", json.dumps(R["TW3_rotary_quadrature"]["detail"], ensure_ascii=False))
        print("TW6 pivot-fixed (fixed/negctrl px, anisoM, shyPk):")
        for rec in R["TW6_end2end_affine_pivot_fixed"]["checked"]:
            print("  {:14s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}  anisoM {:.3f}  shyPk {:.2f}".format(
                rec["bone"], rec["arm"], rec["fixed"], rec["negctrl"], rec["anisoM"], rec["shyPk"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
