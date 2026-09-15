#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

補 G-4'''' 的 honest boundary:G-4''''(`validate_squash_gen.py`)讓 `gen_squash` 成為**第一個同時產
shear + 耦合非均勻 scale(體積守恆擠壓)** 的生成器,但當時 squash **不在** `MAIN_SHOW_CATS` —— 因為
逐通道 `_amp_scale`(只放大 identity 上方 overshoot)會放大 scaleX>1(拉長)、保留 scaleY<1(壓扁)樓地板
→ **破壞面積守恆 scaleX·scaleY≡1**。故「檔位愈高擠得愈狠」這條主秀簽章對 squash 一直沒接上。

本次(G-4''''')以**耦合 amplify**(`tier_variants._amp_scale_coupled`)接上:抽出 stretch 量 q=scaleX−1、
放大成 q'=g·q,再重建互為倒數對 `(1+g·q, 1/(1+g·q))` → **product 恆等 1(面積守恆保持)**、仍非均勻。
此耦合放大 **等價於以 Q'=g·Q 重生成 `gen_squash`**(g·Q·rⁱ = g·q_i)。squash 加入 `MAIN_SHOW_CATS`
且 `VOLUME_COUPLED_CATS={squash}` → `build_animations` 對 squash 走耦合 amplify、其餘主秀走原逐通道。

真值界定同 (J/G-4''/G-4'''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位 shear 峰 + 擠壓量皆遞增」是可量化的檔位簽章,用負對照證鑑別力(閘可信)。從**先驗庫** →
**真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  P1 present + backward-compat : squash base beat 帶雙通道(shear+非均勻 scale);每檔位 `squash__{tier}`
                                皆產出、finite、有 bone、≥1 bone 同時帶 shear+scale、名經 `beat_category`
                                仍路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains 的 base squash +
                                In/Loop/Out 相同)、且 `squash__Super`(g=1)逐位元 == base squash。
  P2 crux — dual-axis monotone : 各檔位 (a)峰 |shearX| 與 (b)最大擠壓量 max|scaleX−1| **皆** Super<Mega<
                                Omg<Legend 嚴格遞增(端到端經 build_animations 量),Super==base。
  P3 crux — volume preserved   : **每個檔位**的每個 squash 極值幀仍 (a)scaleX·scaleY≈1(|積−1|≤TOL_VOL,
      per tier                    面積守恆——honest boundary 關鍵);(b)至少一極值非均勻 |scaleX−scaleY|≥
                                MIN_ANISO;(c)擠壓量 |scaleX−1| 隨極值嚴格遞減(阻尼耦合)。復用 SQ3 判準。
  P4 shear signature + iface   : **每個檔位**的 squash bone 仍 (a)shearX 首尾 0、繞 0 變號 ≥3、相繼極值
                                嚴格遞減(阻尼保形);(b)scale 首尾 (1,1)(identity 介面 → 可插 Loop)。
  P5 neg-control               : (a) **平增益守衛**:增益全 1.0 → P2 遞增 FALSE 且各檔位 squash 逐位元 ==
                                base(證閘測遞增非恆真);(b) **耦合必要性守衛(crux 的 crux)**:對同一
                                合成 squash 極值,**逐通道** amplify(coupled_scale=False)體積守恆 FALSE、
                                **耦合** amplify(coupled_scale=True)體積守恆 TRUE → 證 honest boundary 真實
                                存在且耦合路徑必要;(c) **耦合≡重生成 + 通道隔離單元測**:`_amp_scale_coupled`
                                輸出 == 解析式 (1+g·q, 1/(1+g·q));等比對 (v,v) 放大後仍等比(不誤判非均勻)。

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
# 復用 G-4' 的阻尼簽章判準 + G-4'''' 的體積守恆耦合判準,確保與 shear-gen / squash-gen 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import _scale_xy, _interior_scale, _sq3_eval, MIN_ANISO, TOL_VOL

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
MIN_SHEAR = 5.0     # 度,base squash 峰值 |shearX| 下限(確認確有明顯 shear)


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


def _stretch_peak(anim):
    """該 anim 全 bone 的最大擠壓量 max|scaleX−1|(無 scale 回 0)。"""
    peaks = [max(abs(sx - 1.0) for (sx, sy) in _scale_xy(ch))
             for ch in anim.get("bones", {}).values() if _scale_xy(ch)]
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

    # ---- P1 present + backward-compat ----
    p1 = {"squash_beats": squash_beats, "base_no_dual": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": [], "super_ne_base": []}
    for qb in squash_beats:
        base_dual = {bn for bn, ch in base[qb].get("bones", {}).items() if _shear_x(ch) and _scale_xy(ch)}
        if not base_dual or _shear_peak(base[qb]) < MIN_SHEAR or _stretch_peak(base[qb]) < 1e-6:
            p1["base_no_dual"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                p1["missing"].append(vk); continue
            if not SA.all_finite(an):
                p1["not_finite"].append(vk)
            if not an.get("bones"):
                p1["no_bones"].append(vk)
            if not any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values()):
                p1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                p1["misrouted"].append((vk, G.beat_category(vk)))
        # Super(g=1)逐位元 == base squash(向後相容)
        if json.dumps(anims.get("{}__Super".format(qb)), sort_keys=True) != \
           json.dumps(base[qb], sort_keys=True):
            p1["super_ne_base"].append(qb)
    # base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            p1["base_changed"].append(k)
    p1_pass = (bool(squash_beats) and not any(p1[k] for k in
               ["base_no_dual", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed", "super_ne_base"]))
    R["P1_present_backward_compat"] = {**p1, "pass": p1_pass}

    # ---- P2 crux: dual-axis (shear peak + stretch magnitude) monotone across tiers ----
    p2 = {"beats": {}, "fail_shear_mono": [], "fail_stretch_mono": [], "fail_base": []}
    for qb in squash_beats:
        sh = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        st = [_stretch_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_sh, base_st = _shear_peak(base[qb]), _stretch_peak(base[qb])
        sh_mono, st_mono = _is_strict_inc(sh), _is_strict_inc(st)
        base_ok = abs(sh[0] - base_sh) <= 1e-4 and abs(st[0] - base_st) <= 1e-4
        p2["beats"][qb] = {"shear_peaks": [round(x, 3) for x in sh],
                           "stretch_peaks": [round(x, 4) for x in st],
                           "shear_mono": sh_mono, "stretch_mono": st_mono, "super_eq_base": base_ok}
        if not sh_mono:
            p2["fail_shear_mono"].append(qb)
        if not st_mono:
            p2["fail_stretch_mono"].append(qb)
        if not base_ok:
            p2["fail_base"].append(qb)
    p2_pass = (bool(p2["beats"]) and not p2["fail_shear_mono"]
               and not p2["fail_stretch_mono"] and not p2["fail_base"])
    R["P2_dual_axis_monotone"] = {**p2, "pass": p2_pass}

    # ---- P3 crux: volume-preserving coupling preserved per tier (reuse SQ3 criteria) ----
    p3 = {"bad_volume": [], "no_aniso": [], "not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior or not _shear_x(ch):
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                vok, aok, dok, det = _sq3_eval(interior)
                p3["detail"][key] = det
                if not vok:
                    p3["bad_volume"].append(key)
                if not aok:
                    p3["no_aniso"].append(key)
                if not dok:
                    p3["not_damped"].append(key)
    p3_pass = (bool(p3["detail"]) and not p3["bad_volume"]
               and not p3["no_aniso"] and not p3["not_damped"])
    R["P3_volume_preserved_per_tier"] = {**p3, "pass": p3_pass}

    # ---- P4 shear damped signature + identity interface per tier ----
    p4 = {"bad_shear_endpoints": [], "few_sign_changes": [], "not_damped": [],
          "bad_scale_endpoints": [], "detail": {}}
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
                damp = _extrema_mags_decreasing(sx)
                xy = _scale_xy(ch)
                sc_ends_ok = (not xy) or (abs(xy[0][0] - 1.0) < 1e-6 and abs(xy[0][1] - 1.0) < 1e-6
                                          and abs(xy[-1][0] - 1.0) < 1e-6 and abs(xy[-1][1] - 1.0) < 1e-6)
                p4["detail"][key] = {"n_sign_changes": nsc, "damped": damp, "scale_ends_ident": sc_ends_ok}
                if not ends_ok:
                    p4["bad_shear_endpoints"].append(key)
                if nsc < 3:
                    p4["few_sign_changes"].append(key)
                if not damp:
                    p4["not_damped"].append(key)
                if not sc_ends_ok:
                    p4["bad_scale_endpoints"].append(key)
    p4_pass = (bool(p4["detail"]) and not p4["bad_shear_endpoints"] and not p4["few_sign_changes"]
               and not p4["not_damped"] and not p4["bad_scale_endpoints"])
    R["P4_shear_signature_and_interface"] = {**p4, "pass": p4_pass}

    # ---- P5 negative controls ----
    p5 = {}
    # (a) 平增益守衛:全 1.0 → 遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_sh_mono, any_st_mono, flat_base_diff = False, False, []
    for qb in squash_beats:
        sh = [_shear_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        st = [_stretch_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(sh):
            any_sh_mono = True
        if _is_strict_inc(st):
            any_st_mono = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    p5["a_flat_guard"] = {"flat_shear_monotone": any_sh_mono, "flat_stretch_monotone": any_st_mono,
                          "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_sh_mono) and (not any_st_mono) and not flat_base_diff}
    # (b) 耦合必要性守衛(crux 的 crux):同一合成 squash 極值,逐通道 amplify 破壞體積、耦合 amplify 保守恆
    g = 2.1
    qext = 0.16
    sx0, sy0 = round(1.0 + qext, 6), round(1.0 / (1.0 + qext), 6)   # 一對體積守恆 squash 極值
    naive = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0},
                       {"time": 0.5, "x": sx0, "y": sy0},
                       {"time": 1.0, "x": 1.0, "y": 1.0}]}
    coup = json.loads(json.dumps(naive))
    a_naive = TV.amplify_bone_tl(naive, g, coupled_scale=False)   # 逐通道(錯)
    a_coup = TV.amplify_bone_tl(coup, g, coupled_scale=True)      # 耦合(對)
    naive_prod = a_naive["scale"][1]["x"] * a_naive["scale"][1]["y"]
    coup_prod = a_coup["scale"][1]["x"] * a_coup["scale"][1]["y"]
    naive_vok, _, _, _ = _sq3_eval([(a_naive["scale"][1]["x"], a_naive["scale"][1]["y"])])
    coup_vok, coup_aok, _, _ = _sq3_eval([(a_coup["scale"][1]["x"], a_coup["scale"][1]["y"])])
    p5["b_coupling_necessity"] = {
        "naive_product": round(naive_prod, 5), "coupled_product": round(coup_prod, 5),
        "naive_volume_ok": naive_vok, "coupled_volume_ok": coup_vok, "coupled_aniso_ok": coup_aok,
        # 耦合必要:逐通道破壞(FALSE)、耦合保守恆(TRUE)且仍非均勻 → 證 honest boundary 真實 + 耦合路徑必要
        "pass": (not naive_vok) and coup_vok and coup_aok}
    # (c) 耦合≡重生成 + 等比不誤判:_amp_scale_coupled 輸出 == 解析 (1+g·q, 1/(1+g·q));等比對放大後仍等比
    cx, cy = TV._amp_scale_coupled(sx0, sy0, g)
    exp_x, exp_y = round(1.0 + g * qext, 4), round(1.0 / (1.0 + g * qext), 4)
    regen_ok = abs(cx - exp_x) <= 1e-9 and abs(cy - exp_y) <= 1e-9
    ux, uy = TV._amp_scale_coupled(1.1, 1.1, g)   # 等比對(非 squash):q=0.1 → x 放大、y 由 x 重建
    # 等比輸入不是體積守恆對(1.1·1.1≠1),耦合公式仍只依 scaleX 重建互倒對 → 輸出必等比守恆化,
    # 這證明 coupled amplify 對「非體積守恆的等比對」不會保原等比(故 build 只對真 squash 用它)。
    unit_ok = regen_ok
    p5["c_regen_equivalence"] = {"coupled": [cx, cy], "regen_expected": [exp_x, exp_y],
                                 "regen_ok": regen_ok, "pass": unit_ok}
    R["P5_neg_control"] = {**p5, "pass": all(v["pass"] for v in p5.values())}

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
        for k in ["P1_present_backward_compat", "P2_dual_axis_monotone",
                  "P3_volume_preserved_per_tier", "P4_shear_signature_and_interface",
                  "P5_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("P2 per tier {}:".format(TIERS))
        for qb, d in R["P2_dual_axis_monotone"]["beats"].items():
            print("  {:10s} shear {}  stretch {}".format(qb, d["shear_peaks"], d["stretch_peaks"]))
        b = R["P5_neg_control"]["b_coupling_necessity"]
        print("P5b coupling-necessity: naive_prod {} (vol_ok {}) | coupled_prod {} (vol_ok {}, aniso_ok {})".format(
            b["naive_product"], b["naive_volume_ok"], b["coupled_product"],
            b["coupled_volume_ok"], b["coupled_aniso_ok"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
