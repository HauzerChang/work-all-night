#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

一路的 honest boundary:candidate (J) 讓主秀 beat 依檔位**幅度**差異化,(G-4'') 讓 wobble 的 shear
接上檔位、(G-4'''') 讓 gen_squash 產出**耦合的 shear + 體積守恆非均勻 scale**;但 squash 當時**不在**
MAIN_SHOW_CATS —— 因為既有幅度增益 `_amp_scale` 兩軸各自獨立放大(只放大 identity 上方 → scaleX 變大、
scaleY<1 樓地板不動)會**破壞體積守恆**(scaleX·scaleY≠1)。本次(G-4''''')以**耦合放大** `_amp_scale_pair`
(偵測 squash 對後放大拉長量 q→g·q、另一軸取倒數保積==1)把 squash 接進檔位差異化:斜拉+擠壓強度隨檔位
遞增,而**面積始終守恆**。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位斜拉/擠壓愈強、但體積恆守恆」是可量化檔位簽章,用負對照證鑑別力(閘可信)。從**先驗庫**
→ **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  ST1 present + backward-compat : squash base beat 帶 shear+scale 雙通道;每檔位 `squash__{tier}` 皆產出、
                                 finite、有 bone、≥1 bone **同時**帶 shear 與 scale、名經 `beat_category`
                                 仍路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains);且 **Super
                                 變體逐位元 == base squash**(g=1.0 → 耦合放大為 identity 變換,向後相容)。
  ST2 crux — coupled monotone   : (a)峰 |shearX| Super<Mega<Omg<Legend **嚴格遞增**且 Super==base;
                 + volume-conserved  (b)峰非均勻 |scaleX−scaleY| **嚴格遞增**(檔位愈高擠壓愈非均勻);
                                 (c)**crux**:每檔位每個 squash 極值幀 |scaleX·scaleY−1|≤TOL_VOL —— 放大後
                                    **面積仍守恆**(這是 `_amp_scale` 兩軸獨立會壞、`_amp_scale_pair` 耦合才對)。
  ST3 damped signature per tier : **每個檔位**:(a)shear 首尾 0 + 繞 0 變號≥3 + 相繼極值遞減(阻尼,復用 G-4');
                                 (b)squash 幅度 |scaleX−1| 隨極值嚴格遞減(擠壓阻尼耦合保形)。
  ST4 coupling isolated to squash: 全 tier build(含所有變體)中,**只有 squash 及其 `__tier` 變體**同時帶
                                 shear 與非均勻 scale;非-squash beat/變體皆非此耦合(wobble 有 shear 無 aniso
                                 scale、其餘主秀有等比 scale 無 shear)→ 耦合補償對象仍鎖 squash。
  ST5 neg-control               : (a) **平增益守衛**:增益全 1.0 → ST2 遞增 FALSE 且各檔位 == base;
                                 (b) **耦合放大 crux 守衛(單元)**:對合成 squash 對 (1.16, 0.8621)(積≈1)——
                                    `_amp_scale_pair(g=2)` 放大拉長量 q→2q(scaleX→1.32)**且積==1**;而舊式
                                    兩軸獨立 `_amp_scale` 會使 scaleY 不動、積=1.32×0.8621≠1(**證耦合是必要且正確**);
                                    對等比對 (1.2, 1.2)(非 squash 對)`_amp_scale_pair` == 獨立 `_amp_scale`(向後相容)。

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
# 復用 G-4' 的阻尼簽章判準 + G-4'''' 的 scale 讀取,確保與 shear-gen / squash-gen 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import _scale_xy, _interior_scale

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,base squash 峰值下限(確認確有明顯 shear)
MIN_ANISO = 0.05    # scale 非均勻峰下限
TOL_VOL = 0.02      # 放大後 |scaleX·scaleY − 1| 上限(耦合放大理論 ==1,4 位小數殘差 <1e-3 → 餘裕)


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


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _aniso_peak(anim):
    """該 anim 全 bone 的峰 |scaleX−scaleY|(無 scale 回 0)。"""
    peaks = [max((abs(sx - sy) for (sx, sy) in _scale_xy(ch)), default=0.0)
             for ch in anim.get("bones", {}).values() if _scale_xy(ch)]
    return max(peaks, default=0.0)


def _has_aniso_scale(chans):
    return any(abs(sx - sy) > MIN_ANISO for (sx, sy) in _scale_xy(chans))


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

    # ---- ST1 present + backward-compat ----
    s1 = {"squash_beats": squash_beats, "base_weak": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": [],
          "super_ne_base": []}
    for qb in squash_beats:
        if _shear_peak(base[qb]) < MIN_SHEAR or _aniso_peak(base[qb]) < MIN_ANISO:
            s1["base_weak"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                s1["missing"].append(vk); continue
            if not SA.all_finite(an):
                s1["not_finite"].append(vk)
            if not an.get("bones"):
                s1["no_bones"].append(vk)
            dual = any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values())
            if not dual:
                s1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                s1["misrouted"].append((vk, G.beat_category(vk)))
        # Super(g=1.0)變體 == base squash 逐位元(耦合放大 identity → 向後相容)
        sk = "{}__Super".format(qb)
        if json.dumps(anims.get(sk), sort_keys=True) != json.dumps(base[qb], sort_keys=True):
            s1["super_ne_base"].append(sk)
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            s1["base_changed"].append(k)
    s1_pass = (bool(squash_beats) and not any(s1[k] for k in
               ["base_weak", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed", "super_ne_base"]))
    R["ST1_present_backward_compat"] = {**s1, "pass": s1_pass}

    # ---- ST2 crux: coupled amplitude monotone + volume conserved ----
    s2 = {"beats": {}, "fail_shear_mono": [], "fail_shear_base": [], "fail_aniso_mono": [],
          "fail_volume": []}
    for qb in squash_beats:
        sh_peaks = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        an_peaks = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_sh = _shear_peak(base[qb])
        sh_mono = _is_strict_inc(sh_peaks)
        an_mono = _is_strict_inc(an_peaks)
        super_eq = abs(sh_peaks[0] - base_sh) <= 1e-4
        # (c) crux:每檔位每個 squash 極值幀放大後仍體積守恆
        worst_vol, bad = 0.0, []
        for t in TIERS:
            for bn, ch in anims["{}__{}".format(qb, t)].get("bones", {}).items():
                for (sx, sy) in _interior_scale(ch):
                    d = abs(sx * sy - 1.0)
                    worst_vol = max(worst_vol, d)
                    if d > TOL_VOL:
                        bad.append(("{}__{}::{}".format(qb, t, bn), round(sx * sy, 5)))
        s2["beats"][qb] = {"shear_peaks": [round(p, 3) for p in sh_peaks],
                           "aniso_peaks": [round(p, 4) for p in an_peaks],
                           "base_shear": round(base_sh, 3),
                           "shear_mono": sh_mono, "aniso_mono": an_mono,
                           "super_eq_base": super_eq, "worst_vol_err": round(worst_vol, 5)}
        if not sh_mono:
            s2["fail_shear_mono"].append(qb)
        if not super_eq:
            s2["fail_shear_base"].append(qb)
        if not an_mono:
            s2["fail_aniso_mono"].append(qb)
        s2["fail_volume"] += bad
    s2_pass = (bool(s2["beats"]) and not s2["fail_shear_mono"] and not s2["fail_shear_base"]
               and not s2["fail_aniso_mono"] and not s2["fail_volume"])
    R["ST2_coupled_monotone_volume"] = {**s2, "pass": s2_pass}

    # ---- ST3 damped signature per tier (shear + squash magnitude) ----
    s3 = {"bad_endpoints": [], "few_sign_changes": [], "shear_not_damped": [],
          "squash_not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                ends_ok = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                nsc = _sign_changes_zero(sx)
                sh_damp = _extrema_mags_decreasing(sx)
                mag = [abs(scx - 1.0) for (scx, scy) in _interior_scale(ch)]
                sq_damp = len(mag) >= 2 and all(mag[i + 1] < mag[i] - 1e-9 for i in range(len(mag) - 1))
                s3["detail"][key] = {"n_sign_changes": nsc, "shear_damped": sh_damp,
                                     "squash_mag": [round(m, 4) for m in mag], "squash_damped": sq_damp}
                if not ends_ok:
                    s3["bad_endpoints"].append(key)
                if nsc < 3:
                    s3["few_sign_changes"].append(key)
                if not sh_damp:
                    s3["shear_not_damped"].append(key)
                if not sq_damp:
                    s3["squash_not_damped"].append(key)
    s3_pass = (bool(s3["detail"]) and not s3["bad_endpoints"] and not s3["few_sign_changes"]
               and not s3["shear_not_damped"] and not s3["squash_not_damped"])
    R["ST3_damped_signature_per_tier"] = {**s3, "pass": s3_pass}

    # ---- ST4 coupling (shear + non-uniform scale) isolated to squash ----
    s4 = {"leaked": []}
    for nm, an in anims.items():
        base_name = nm.split("__")[0]
        if G.beat_category(base_name) == "squash":
            continue
        for bn, ch in an.get("bones", {}).items():
            if _shear_x(ch) and _has_aniso_scale(ch):
                s4["leaked"].append((nm, bn))
    R["ST4_coupling_isolated"] = {**s4, "pass": not s4["leaked"]}

    # ---- ST5 negative controls ----
    s5 = {}
    # (a) 平增益守衛:全 1.0 → shear/aniso 遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for qb in squash_beats:
        sh_peaks = [_shear_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        an_peaks = [_aniso_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(sh_peaks) or _is_strict_inc(an_peaks):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    s5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) 耦合放大 crux 守衛(單元):squash 對耦合放大保積==1 且放大 q;舊式獨立會壞守恆
    g = 2.0
    x0, y0 = 1.16, round(1.0 / 1.16, 4)     # 合成 squash 對(積≈1)
    nx, ny = TV._amp_scale_pair(x0, y0, g)
    coupled_vol = abs(nx * ny - 1.0)
    coupled_stretch = abs(nx - (1.0 + g * (x0 - 1.0)))       # 拉長量放大 q→g·q
    indep_x, indep_y = TV._amp_scale(x0, g), TV._amp_scale(y0, g)  # 舊式兩軸獨立
    indep_vol = abs(indep_x * indep_y - 1.0)                 # 應**明顯≠0**(證耦合必要)
    # 等比對(非 squash 對)→ 耦合放大 == 獨立放大(向後相容)
    ux, uy = 1.2, 1.2
    pux, puy = TV._amp_scale_pair(ux, uy, g)
    iso_match = (abs(pux - TV._amp_scale(ux, g)) <= 1e-9 and abs(puy - TV._amp_scale(uy, g)) <= 1e-9)
    s5["b_coupling_crux_guard"] = {
        "coupled_nx": round(nx, 5), "coupled_ny": round(ny, 5),
        "coupled_vol_err": round(coupled_vol, 6), "coupled_stretch_err": round(coupled_stretch, 6),
        "indep_vol_err": round(indep_vol, 5), "uniform_pair_matches_indep": iso_match,
        "pass": (coupled_vol <= 1e-6 and coupled_stretch <= 1e-6
                 and indep_vol >= 0.05 and iso_match)}
    R["ST5_neg_control"] = {**s5, "pass": all(v["pass"] for v in s5.values())}

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
        for k in ["ST1_present_backward_compat", "ST2_coupled_monotone_volume",
                  "ST3_damped_signature_per_tier", "ST4_coupling_isolated", "ST5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("ST2 per tier {}:".format(TIERS))
        for qb, d in R["ST2_coupled_monotone_volume"]["beats"].items():
            print("  {:8s} shear {}  aniso {}  (base shear {})  worst_vol_err {}".format(
                qb, d["shear_peaks"], d["aniso_peaks"], d["base_shear"], d["worst_vol_err"]))
        cg = R["ST5_neg_control"]["b_coupling_crux_guard"]
        print("ST5 coupling crux: coupled vol_err {} (indep would be {}), stretch_err {}".format(
            cg["coupled_vol_err"], cg["indep_vol_err"], cg["coupled_stretch_err"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
