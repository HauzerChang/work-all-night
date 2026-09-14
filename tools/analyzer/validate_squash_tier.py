#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合體積守恆非均勻 scale)接檔位幅度差異化(純 CPU)。

G-4''''(`validate_squash_gen.py`)讓生成器 `gen_squash` 第一次產出**耦合的 shear + 非均勻 scale**
(斜拉擠壓,scaleX·scaleY==1),但它的 honest boundary 是「squash **未接** tier 幅度差異化」——
因為舊 `_amp_scale` 只放大 identity 上方(拉長軸),壓縮軸(scaleY<1)樓地板不動 → scaleX·scaleY≠1
(破壞體積守恆)。本次(G-4''''')補上**耦合 amplify**:放大拉長軸的 overshoot、壓縮軸重算為其倒數 →
**scaleX·scaleY==1 對所有檔位保持**,同時 shear 峰與非均勻幅度**同時**隨檔位嚴格遞增。squash 因此得以
併入 `MAIN_SHOW_CATS`(G-4'''' 當時的 honest boundary「squash 不在 MAIN_SHOW_CATS」解除)。

**關鍵:守恆量的檔位放大必須放大不變量本身(q),不能各軸獨立放大**。squash 對 = (1+q, 1/(1+q));
檔位放大 q→g·q ⇒ (1+g·q, 1/(1+g·q)) 仍守恆。舊路徑各軸獨立套 `_amp_scale` 會把拉長軸放大、壓縮軸
不動 → 積 ≠ 1(V5a 負對照量到 Legend 檔積達 ~1.15,15% 破壞)。這是「守恆不變量的差異化」通則
(對後續任何體積/長度守恆基元皆適用)。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量,
負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  V1 present + backward-compat  : squash base 帶 shear+scale;每檔位 `squash__{tier}` 皆產出、finite、
                                 有 bone、≥1 bone **同時**帶 shear 與 scale、名經 `beat_category` 仍路由回
                                 squash;**base 逐位元不變**(帶/不帶 tier_gains 的 base squash + In/Loop/Out
                                 相同),且 `tier_gains=None` 逐位元同無檔位輸出。
  V2 crux — dual-channel mono   : 各檔位 squash 的 (a) shear 峰 |shearX| 與 (b) 非均勻峰 |scaleX−scaleY|
                                 皆 Super<Mega<Omg<Legend **嚴格遞增**(兩通道同時隨檔位放大),且首檔
                                 (Super,g=1)兩量 == base(向後相容)。
  V3 crux — volume kept per tier: **每個檔位**的**每個** squash 極值幀 scaleX·scaleY≈1(|積−1|≤TOL_VOL)
                                 → 耦合 amplify 的關鍵回報:守恆對所有檔位保持(非只 base);且每檔位 squash
                                 幅度 |scaleX−1| 隨極值嚴格遞減(阻尼耦合保形)。
  V4 identity IF + damped per tier: 每檔位:shear 首尾 0、scale 首尾 (1,1)(可插 Loop);shear 繞 0 變號 ≥3
                                 + 相繼極值遞減(阻尼簽章,復用 G-4' 判準)。
  V5 neg-control / isolation    : (a) **naive 守衛(crux 鑑別子)**:對同一 base squash 套**舊** `_amp_scale`
                                 各軸獨立放大 → 體積守恆**破壞**(Legend 檔 max|積−1| ≥ NAIVE_BREAK)而耦合
                                 路徑 ≈0 → 證 V3 非恆真、耦合 amplify 真在做事;
                                 (b) **平增益守衛**:增益全 1.0 → V2 遞增 FALSE 且各檔位 squash 逐位元 == base;
                                 (c) **耦合隔離**:`COUPLED_SCALE_CATS=={squash}` 且 squash∈MAIN_SHOW_CATS;
                                 單元測 `amplify_bone_tl(coupled=)` 對合成守恆對:coupled=True 保守恆、
                                 coupled=False 破壞;對「獨立雙軸 scale」(combo 式)coupled=False 逐位元同
                                 舊 `_amp_scale`(非 squash 主秀 beat 零回歸)。

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
# 復用 G-4' 阻尼簽章判準 + G-4'''' 的 scale 讀取/體積守恆判準,確保與既有閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import _scale_xy, _interior_scale, _sq3_eval

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0       # 度,base squash 峰 |shearX| 下限
MIN_ANISO = 0.05      # base squash 非均勻峰下限
TOL_VOL = 1e-3        # 放大後體積守恆 |scaleX·scaleY−1| 上限(耦合實測 <1e-4;含 4dp 捨入餘裕)
NAIVE_BREAK = 0.05    # V5a:naive 放大於 Legend 檔的體積破壞下限(實測 ~0.15 → 充足鑑別)


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/squash_tier_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _squash_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "squash"]


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _aniso_peak(anim):
    """該 anim 全 bone 的峰 |scaleX−scaleY|(非均勻幅度;無 scale 回 0)。"""
    peaks = [max((abs(sx - sy) for (sx, sy) in _scale_xy(ch)), default=0.0)
             for ch in anim.get("bones", {}).values()]
    return max(peaks, default=0.0)


def _max_vol_err(anim):
    """該 anim 全 bone squash 極值幀的 max |scaleX·scaleY − 1|(體積破壞量)。"""
    errs = []
    for ch in anim.get("bones", {}).values():
        for (sx, sy) in _interior_scale(ch):
            errs.append(abs(sx * sy - 1.0))
    return max(errs, default=0.0)


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

    # ---- V1 present + backward-compat ----
    v1 = {"squash_beats": squash_beats, "base_weak": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": [], "none_diff": []}
    for qb in squash_beats:
        if _shear_peak(base[qb]) < MIN_SHEAR or _aniso_peak(base[qb]) < MIN_ANISO:
            v1["base_weak"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                v1["missing"].append(vk); continue
            if not SA.all_finite(an):
                v1["not_finite"].append(vk)
            if not an.get("bones"):
                v1["no_bones"].append(vk)
            if not any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values()):
                v1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                v1["misrouted"].append((vk, G.beat_category(vk)))
    # base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            v1["base_changed"].append(k)
    # tier_gains=None 逐位元同無檔位(重呼叫一致性)
    base2 = G.build_animations(skel, sb, tier_gains=None)
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(base2.get(k), sort_keys=True):
            v1["none_diff"].append(k)
    v1_pass = (bool(squash_beats) and not any(v1[k] for k in
               ["base_weak", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed", "none_diff"]))
    R["V1_present_backward_compat"] = {**v1, "pass": v1_pass}

    # ---- V2 crux: dual-channel (shear + aniso) amplitude monotone across tiers ----
    v2 = {"beats": {}, "fail_shear_mono": [], "fail_aniso_mono": [], "fail_base": []}
    for qb in squash_beats:
        sh = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        an = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_sh, base_an = _shear_peak(base[qb]), _aniso_peak(base[qb])
        sh_mono, an_mono = _is_strict_inc(sh), _is_strict_inc(an)
        base_ok = abs(sh[0] - base_sh) <= 1e-4 and abs(an[0] - base_an) <= 1e-4  # Super g=1 → base
        v2["beats"][qb] = {"shear_peaks": [round(x, 3) for x in sh],
                           "aniso_peaks": [round(x, 4) for x in an],
                           "base_shear": round(base_sh, 3), "base_aniso": round(base_an, 4),
                           "shear_mono": sh_mono, "aniso_mono": an_mono, "super_eq_base": base_ok}
        if not sh_mono:
            v2["fail_shear_mono"].append(qb)
        if not an_mono:
            v2["fail_aniso_mono"].append(qb)
        if not base_ok:
            v2["fail_base"].append(qb)
    v2_pass = (bool(v2["beats"]) and not v2["fail_shear_mono"]
               and not v2["fail_aniso_mono"] and not v2["fail_base"])
    R["V2_dual_channel_monotone"] = {**v2, "pass": v2_pass}

    # ---- V3 crux: volume conservation preserved for EVERY tier ----
    v3 = {"bad_volume": [], "not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior or not _shear_x(ch):
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                vok, aok, dok, det = _sq3_eval(interior)   # 復用 G-4'''' 判準
                # 用本閘的 TOL_VOL(較 G-4'''' 的 0.02 緊)重評體積;damped 用 _sq3_eval 的 mag 遞減
                vol_ok = all(abs(p - 1.0) <= TOL_VOL for p in [sx * sy for (sx, sy) in interior])
                v3["detail"][key] = {"prod": det["prod"], "mag": det["mag"]}
                if not vol_ok:
                    v3["bad_volume"].append(key)
                if not dok:
                    v3["not_damped"].append(key)
    v3_pass = (bool(v3["detail"]) and not v3["bad_volume"] and not v3["not_damped"])
    R["V3_volume_kept_per_tier"] = {**v3, "pass": v3_pass}

    # ---- V4 identity interface + damped shear signature per tier ----
    v4 = {"bad_interface": [], "shear_ends_nonzero": [], "scale_ends_nonident": [],
          "few_sign_changes": [], "not_damped_shear": []}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                v4["bad_interface"].append("{}__{}".format(qb, t))
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if sx:
                    if abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6:
                        v4["shear_ends_nonzero"].append("{}__{}::{}".format(qb, t, bn))
                    if _sign_changes_zero(sx) < 3:
                        v4["few_sign_changes"].append("{}__{}::{}".format(qb, t, bn))
                    if not _extrema_mags_decreasing(sx):
                        v4["not_damped_shear"].append("{}__{}::{}".format(qb, t, bn))
                xy = _scale_xy(ch)
                if xy and (abs(xy[0][0] - 1.0) > 1e-6 or abs(xy[0][1] - 1.0) > 1e-6
                           or abs(xy[-1][0] - 1.0) > 1e-6 or abs(xy[-1][1] - 1.0) > 1e-6):
                    v4["scale_ends_nonident"].append("{}__{}::{}".format(qb, t, bn))
    v4_pass = not any(v4[k] for k in v4)
    R["V4_identity_damped_per_tier"] = {**v4, "pass": v4_pass}

    # ---- V5 negative controls / coupling isolation ----
    v5 = {}
    # (a) naive 守衛(crux 鑑別子):對 base squash 套舊各軸獨立 _amp_scale → 體積守恆破壞
    naive_break, coupled_ok = [], []
    for qb in squash_beats:
        for t in TIERS:
            g = gains[t]
            naive = TV.amplify_anim(base[qb], g, coupled=False)   # 舊路徑(各軸獨立)
            coup = anims["{}__{}".format(qb, t)]                  # 新路徑(耦合)
            naive_break.append({"beat": "{}__{}".format(qb, t), "g": g,
                                "max_vol_err": round(_max_vol_err(naive), 4)})
            coupled_ok.append({"beat": "{}__{}".format(qb, t),
                               "max_vol_err": round(_max_vol_err(coup), 5)})
    legend_break = max((r["max_vol_err"] for r in naive_break
                        if r["beat"].endswith("Legend")), default=0.0)
    coupled_max = max((r["max_vol_err"] for r in coupled_ok), default=0.0)
    v5["a_naive_guard"] = {"naive_legend_break": legend_break, "coupled_max_err": coupled_max,
                           "naive_detail": naive_break, "coupled_detail": coupled_ok,
                           "pass": legend_break >= NAIVE_BREAK and coupled_max <= TOL_VOL}
    # (b) 平增益守衛:全 1.0 → V2 遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for qb in squash_beats:
        sh = [_shear_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        an = [_aniso_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(sh) or _is_strict_inc(an):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    v5["b_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (c) 耦合隔離:集合關係 + amplify_bone_tl coupled 旗標單元測
    g = 2.0
    conserving = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0}, {"time": 0.5, "x": 1.20, "y": 0.8333},
                            {"time": 1.0, "x": 1.0, "y": 1.0}]}
    independent = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0}, {"time": 0.5, "x": 1.30, "y": 0.90},
                             {"time": 1.0, "x": 1.0, "y": 1.0}]}   # combo 式獨立雙軸
    a_cT = TV.amplify_bone_tl(conserving, g, coupled=True)
    a_cF = TV.amplify_bone_tl(conserving, g, coupled=False)
    a_iF = TV.amplify_bone_tl(independent, g, coupled=False)
    cT_prod = a_cT["scale"][1]["x"] * a_cT["scale"][1]["y"]
    cF_prod = a_cF["scale"][1]["x"] * a_cF["scale"][1]["y"]
    # 獨立雙軸 coupled=False → 各軸各自 _amp_scale(向後相容):x'=1+g(1.3−1)=1.6、y'=0.9(<1 樓地板不動)
    iF_x_ok = abs(a_iF["scale"][1]["x"] - (1.0 + g * 0.30)) <= 1e-6
    iF_y_ok = abs(a_iF["scale"][1]["y"] - 0.90) <= 1e-6
    v5["c_coupling_isolation"] = {
        "COUPLED_SCALE_CATS": sorted(TV.COUPLED_SCALE_CATS),
        "squash_in_main_show": "squash" in TV.MAIN_SHOW_CATS,
        "coupledTrue_prod": round(cT_prod, 6), "coupledFalse_prod": round(cF_prod, 6),
        "indep_x_amp_ok": iF_x_ok, "indep_y_floor_ok": iF_y_ok,
        "pass": (TV.COUPLED_SCALE_CATS == {"squash"} and "squash" in TV.MAIN_SHOW_CATS
                 and abs(cT_prod - 1.0) <= 1e-4 and abs(cF_prod - 1.0) > 1e-2
                 and iF_x_ok and iF_y_ok)}
    R["V5_neg_control_isolation"] = {**v5, "pass": all(v["pass"] for v in v5.values())}

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
        for k in ["V1_present_backward_compat", "V2_dual_channel_monotone",
                  "V3_volume_kept_per_tier", "V4_identity_damped_per_tier",
                  "V5_neg_control_isolation"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V2 dual-channel peaks per tier {}:".format(TIERS))
        for qb, d in R["V2_dual_channel_monotone"]["beats"].items():
            print("  {:10s} shear {}  aniso {}".format(qb, d["shear_peaks"], d["aniso_peaks"]))
        va = R["V5_neg_control_isolation"]["a_naive_guard"]
        print("V5a naive Legend vol-break {} vs coupled max {}".format(
            va["naive_legend_break"], va["coupled_max_err"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
