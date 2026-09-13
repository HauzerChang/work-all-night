#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合體積守恆非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

(G-4'''')讓 `gen_squash` 成為第一個**同時**產 shear + 非均勻 scale(體積守恆擠壓)的生成器,但當時把
squash 排除在 `MAIN_SHOW_CATS` 外(honest boundary):一般幅度增益 `_amp_scale`(只放大 identity 上方
overshoot、下方樓地板不動)會**放大 scaleX>1、凍結 scaleY<1 → scaleX·scaleY≠1**,破壞體積守恆。本次
(G-4''''')補上**體積守恆的乘冪(對數空間)耦合放大** `_amp_scale_vp(v,g)=v**g`,把 squash 併入
`MAIN_SHOW_CATS`,使**擠壓強度(非均勻度)隨檔位嚴格遞增**而**每個檔位仍精確體積守恆**。

**關鍵(此里程碑的新機制)**:守恆量無法用加法放大 —— 加法會破壞乘積。必須放大**指數**:
    sx**g · sy**g = (sx·sy)**g = 1**g = 1 ⇒ 放大後積仍==1(守恆);identity 1**g=1(介面保持);
    sx>1 → sx**g 遞增、sy<1 → sy**g 遞減 ⇒ 非均勻 |sx**g−sy**g| 隨 g 嚴格遞增(檔位簽章)。
這是產線**第一個乘法(幾何)增益**(先前 scale 的 1+g(v−1)、rotate/translate/shear 的 g*v 皆加法/線性)。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章
(體積守恆 + 非均勻隨檔位遞增 + 阻尼保形)非美感**;負對照證鑑別力(閘可信)。從**先驗庫** →
**真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。判準復用 G-4'/G-4''''
既有純函式(`_shear_x`/阻尼簽章、`_sq3_eval`/`_interior_scale`)確保與 shear-gen / squash-gen 閘完全一致。

AC(客觀、可量測):
  SQT1 present + backward-compat : squash base beat 帶 shear+非均勻 scale;每檔位 `squash__{tier}` 皆產出、
                                  finite、有 bone、≥1 bone **同時**帶 shear 與 scale、名經 `beat_category`
                                  仍路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains 的 base + In/Loop/Out 相同)。
  SQT2 crux — aniso peak monotone: 各檔位 squash 的峰 |scaleX−scaleY| Super<Mega<Omg<Legend **嚴格遞增**
                                  (端到端經 build_animations 量),且首檔(Super,g=1)峰 == base 峰(向後相容)。
                                  shear 峰亦隨檔位嚴格遞增(shear 軸沿用 g*v,與 aniso 軸一致遞增)。
  SQT3 crux#2 — volume kept/tier : **每個檔位**的 squash bone 每個 scale 極值幀 (a)scaleX·scaleY≈1
                                  (|積−1|≤TOL_VOL,**放大後仍守恆**);(b)至少一極值非均勻 |scaleX−scaleY|≥MIN_ANISO;
                                  (c)squash 幅度 |scaleX−1| 隨極值嚴格遞減(阻尼耦合保形);(d)shear 亦阻尼保形
                                  (首尾 0 + 繞 0 變號≥3 + 相繼極值遞減)。→ 乘冪放大保守恆亦保阻尼。
  SQT4 identity interface / tier : **每個檔位** sample(0)/sample(dur) identity;shear 首尾 0 + scale 首尾 (1,1)。
  SQT5 neg-control               : (a) **平增益守衛**:增益全 1.0 → SQT2 aniso 遞增 FALSE 且各檔位逐位元==base;
                                  (b) **耦合 vs 加法對照(crux 鑑別)**:對合成體積守恆 squash pair 施**錯的**加法
                                  增益 `_amp_scale`(逐軸 1+g(v−1))→ 體積**破壞**(積≠1);施**對的**乘冪
                                  `_amp_scale_vp`(v**g)→ 體積守恆(積==1)**且**非均勻變大 → 證「守恆須乘冪、
                                  加法會壞」是閘實測的性質(非恆真)、且耦合放大器是**必要**的;
                                  (c) **通道隔離單元測**:`amplify_bone_tl(coupled_scale=True)` 對體積守恆 scale-only
                                  bone → 積仍≈1、非均勻變大、不生 shear 鍵;對 shear-only bone → shear g*v 放大、不生 scale 鍵。

用法:
  python3 validate_squash_tier.py            # 摘要
  python3 validate_squash_tier.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
# 復用 G-4' 阻尼簽章判準 + G-4'''' 的體積守恆/非均勻/阻尼純函式(閘一致、可信)
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import (_scale_xy, _interior_scale, _sq3_eval, _has_aniso_scale,
                                 MIN_ANISO, TOL_VOL, MIN_SHEAR)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/squash_tier_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _squash_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "squash"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _aniso_peak(anim):
    """該 anim 全 bone 的峰 |scaleX−scaleY|(無 scale 回 0)。"""
    peaks = [max(abs(sx - sy) for (sx, sy) in _scale_xy(ch)) for ch in anim.get("bones", {}).values()
             if _scale_xy(ch)]
    return max(peaks, default=0.0)


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _is_strict_inc(xs):
    return all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                       # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)    # 帶檔位
    squash_beats = _squash_beats(base)
    R = {}

    # ---- SQT1 present + backward-compat ----
    t1 = {"squash_beats": squash_beats, "base_no_dual": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": []}
    for qb in squash_beats:
        bd = base[qb]
        base_dual = any(_shear_x(ch) and _scale_xy(ch) for ch in bd.get("bones", {}).values())
        if not base_dual:
            t1["base_no_dual"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            if not an.get("bones"):
                t1["no_bones"].append(vk)
            if not any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values()):
                t1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                t1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:                                          # base 逐位元不變
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    t1_pass = (bool(squash_beats) and not any(t1[k] for k in
               ["base_no_dual", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed"]))
    R["SQT1_present_backward_compat"] = {**t1, "pass": t1_pass}

    # ---- SQT2 crux: anisotropy (and shear) peak monotone across tiers ----
    t2 = {"beats": {}, "fail_aniso_mono": [], "fail_shear_mono": [], "fail_base": []}
    for qb in squash_beats:
        ani_pk = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        sh_pk = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_ani = _aniso_peak(base[qb])
        ani_mono = _is_strict_inc(ani_pk)
        sh_mono = _is_strict_inc(sh_pk)
        super_eq_base = abs(ani_pk[0] - base_ani) <= 1e-4
        t2["beats"][qb] = {"aniso_peaks": [round(p, 4) for p in ani_pk],
                           "shear_peaks": [round(p, 3) for p in sh_pk],
                           "base_aniso": round(base_ani, 4),
                           "aniso_mono": ani_mono, "shear_mono": sh_mono,
                           "super_eq_base": super_eq_base}
        if not ani_mono:
            t2["fail_aniso_mono"].append(qb)
        if not sh_mono:
            t2["fail_shear_mono"].append(qb)
        if not super_eq_base:
            t2["fail_base"].append(qb)
    t2_pass = (bool(t2["beats"]) and not t2["fail_aniso_mono"] and not t2["fail_shear_mono"]
               and not t2["fail_base"])
    R["SQT2_aniso_peak_monotone"] = {**t2, "pass": t2_pass}

    # ---- SQT3 crux#2: volume conservation + damped signature preserved per tier ----
    t3 = {"bad_volume": [], "no_aniso": [], "scale_not_damped": [], "shear_bad": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                sx = _shear_x(ch)
                if not interior or not sx:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                vok, aok, dok, det = _sq3_eval(interior)   # 同 squash-gen 判準(閘一致)
                # shear 阻尼保形(復用 G-4' 判準)
                ends_ok = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                nsc = _sign_changes_zero(sx)
                sh_damp = _extrema_mags_decreasing(sx)
                shear_ok = ends_ok and nsc >= 3 and sh_damp
                t3["detail"][key] = {**det, "shear_ok": shear_ok,
                                     "shear_n_sign_changes": nsc, "shear_damped": sh_damp}
                if not vok:
                    t3["bad_volume"].append(key)
                if not aok:
                    t3["no_aniso"].append(key)
                if not dok:
                    t3["scale_not_damped"].append(key)
                if not shear_ok:
                    t3["shear_bad"].append(key)
    t3_pass = (bool(t3["detail"]) and not t3["bad_volume"] and not t3["no_aniso"]
               and not t3["scale_not_damped"] and not t3["shear_bad"])
    R["SQT3_volume_kept_per_tier"] = {**t3, "pass": t3_pass}

    # ---- SQT4 identity interface per tier ----
    t4 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                t4["bad_interface"].append("{}__{}".format(qb, t))
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                    t4["shear_endpoints_nonzero"].append("{}__{}::{}".format(qb, t, bn))
                xy = _scale_xy(ch)
                if xy and (abs(xy[0][0] - 1.0) > 1e-6 or abs(xy[0][1] - 1.0) > 1e-6
                           or abs(xy[-1][0] - 1.0) > 1e-6 or abs(xy[-1][1] - 1.0) > 1e-6):
                    t4["scale_endpoints_nonident"].append("{}__{}::{}".format(qb, t, bn))
    R["SQT4_identity_interface"] = {**t4, "pass": (not t4["bad_interface"]
                                                   and not t4["shear_endpoints_nonzero"]
                                                   and not t4["scale_endpoints_nonident"])}

    # ---- SQT5 negative controls ----
    t5 = {}
    # (a) 平增益守衛:全 1.0 → aniso 遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for qb in squash_beats:
        peaks = [_aniso_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(peaks):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    t5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}

    # (b) 耦合 vs 加法對照(crux 鑑別):合成體積守恆 squash pair
    g = 2.0
    pair = [(1.0, 1.0), (1.14, round(1.0 / 1.14, 6)), (1.07, round(1.0 / 1.07, 6)),
            (1.035, round(1.0 / 1.035, 6)), (1.0, 1.0)]
    # 錯的加法增益(逐軸 _amp_scale)→ 應破壞體積守恆
    add = [(TV._amp_scale(sx, g), TV._amp_scale(sy, g)) for (sx, sy) in pair]
    add_interior = add[1:-1]
    add_vol_ok = all(abs(sx * sy - 1.0) <= TOL_VOL for (sx, sy) in add_interior)
    # 對的乘冪增益(_amp_scale_vp)→ 應守恆且非均勻變大
    vp = [(TV._amp_scale_vp(sx, g), TV._amp_scale_vp(sy, g)) for (sx, sy) in pair]
    vp_interior = vp[1:-1]
    vp_vol_ok = all(abs(sx * sy - 1.0) <= TOL_VOL for (sx, sy) in vp_interior)
    base_aniso = max(abs(sx - sy) for (sx, sy) in pair[1:-1])
    vp_aniso = max(abs(sx - sy) for (sx, sy) in vp_interior)
    vp_aniso_grew = vp_aniso > base_aniso + 1e-9
    t5["b_coupled_vs_additive"] = {
        "additive_volume_ok": add_vol_ok, "vp_volume_ok": vp_vol_ok,
        "vp_aniso": round(vp_aniso, 4), "base_aniso": round(base_aniso, 4),
        "vp_aniso_grew": vp_aniso_grew,
        # 加法**必須**破壞守恆(證耦合放大器必要);乘冪**必須**守恆且放大非均勻
        "pass": (not add_vol_ok) and vp_vol_ok and vp_aniso_grew}

    # (c) 通道隔離單元測:amplify_bone_tl(coupled_scale=True)
    vp_scale_only = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0},
                               {"time": 0.5, "x": 1.2, "y": round(1.0 / 1.2, 6)},
                               {"time": 1.0, "x": 1.0, "y": 1.0}]}
    shear_only = {"shear": [{"time": 0.0, "x": 0.0, "y": 0.0}, {"time": 0.5, "x": 10.0, "y": 0.0},
                            {"time": 1.0, "x": 0.0, "y": 0.0}]}
    a_sc = TV.amplify_bone_tl(vp_scale_only, g, coupled_scale=True)
    a_sh = TV.amplify_bone_tl(shear_only, g, coupled_scale=True)
    mid = a_sc["scale"][1]
    sc_vol_ok = abs(mid["x"] * mid["y"] - 1.0) <= TOL_VOL
    sc_aniso_grew = abs(mid["x"] - mid["y"]) > abs(1.2 - 1.0 / 1.2) + 1e-9
    sc_no_shear = "shear" not in a_sc
    sh_no_scale = "scale" not in a_sh
    sh_amplified = abs(a_sh["shear"][1]["x"] - g * 10.0) <= 1e-6
    t5["c_channel_isolation"] = {"vp_scale_volume_ok": sc_vol_ok, "vp_scale_aniso_grew": sc_aniso_grew,
                                 "vp_scale_no_shear": sc_no_shear, "shear_only_no_scale": sh_no_scale,
                                 "shear_amplified": sh_amplified,
                                 "pass": sc_vol_ok and sc_aniso_grew and sc_no_shear
                                         and sh_no_scale and sh_amplified}
    R["SQT5_neg_control"] = {**t5, "pass": all(v["pass"] for v in t5.values())}

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
        for k in ["SQT1_present_backward_compat", "SQT2_aniso_peak_monotone",
                  "SQT3_volume_kept_per_tier", "SQT4_identity_interface", "SQT5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("SQT2 aniso / shear peaks per tier {}:".format(TIERS))
        for qb, d in R["SQT2_aniso_peak_monotone"]["beats"].items():
            print("  {:10s} aniso {}  shear {}  (base aniso {})".format(
                qb, d["aniso_peaks"], d["shear_peaks"], d["base_aniso"]))
        b = R["SQT5_neg_control"]["b_coupled_vs_additive"]
        print("SQT5(b) additive_vol_ok={} (must be False)  vp_vol_ok={}  vp_aniso {} > base {}".format(
            b["additive_volume_ok"], b["vp_volume_ok"], b["vp_aniso"], b["base_aniso"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
