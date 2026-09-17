#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear+體積守恆非均勻 scale 節拍)接檔位差異化(純 CPU)。

一路 honest boundary:candidate (J) 讓主秀 beat 依檔位**幅度**差異化;(G-4'') 讓 wobble 的 shear 峰隨
檔位遞增;而 (G-4'''') 新生成的 squash(斜拉果凍擠壓)其 scale 通道是**體積守恆**(scaleX·scaleY==1、
scaleY<1 壓扁)—— 一般的 `_amp_scale`(只放大 identity 上方、下方樓地板不動)會**破壞守恆**,故當時
squash **不在** MAIN_SHOW_CATS(檔位差異化留白)。本次(G-4''''')補上:以**耦合 amplify**
(`_amp_scale_coupled`:scaleX、scaleY 一起 `v**g` 放大)接檔位 —— 對數應變均勻放大 ⇒ 保
scaleX·scaleY==1 且 identity 定點,shear 峰同步隨檔位放大。使 **squash 的 shear 峰與 scale 非均勻峰
皆隨檔位嚴格遞增**,而**體積守恆 + 阻尼振盪 + identity 介面三簽章在每個檔位保持**。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章**
(shear/非均勻峰隨檔位遞增、每檔位體積守恆、阻尼、identity 介面)非美感;負對照證鑑別力(閘可信),
其中最關鍵者 = **證「用天真 `_amp_scale` 會破壞體積守恆」→ 耦合 amplify 是必要而非裝飾**。
從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  ST1 present + backward-compat : squash base beat 有 shear+scale;每檔位 `squash__{tier}` 皆產出、finite、
                                 有 bone、≥1 bone **同時**帶 shear 與 scale、名經 `beat_category` 仍路由回
                                 squash;**base 逐位元不變**(帶/不帶 tier_gains 的 base + In/Loop/Out 相同)。
  ST2 crux — dual-channel peak monotone: 各檔位 (a) shear 峰 |shearX| 與 (b) scale 非均勻峰 |scaleX−scaleY|
                                 皆 Super<Mega<Omg<Legend **嚴格遞增**(端到端經 build_animations 量),
                                 且首檔(Super,g=1)兩峰 == base(向後相容)。
  ST3 crux — volume preserved per tier: **每個檔位**的 squash bone,其**每個** scale 極值幀
                                 |scaleX·scaleY − 1| ≤ TOL_VOL(耦合 amplify 保積 → 檔位放大不破壞守恆;
                                 天真 amplify 會在此失敗,見 ST6b)。
  ST4 damped signature per tier : **每個檔位**的 squash bone 仍 (a) shearX 首尾 0、繞 0 變號 ≥3、相繼極值
                                 嚴格遞減(阻尼);(b) squash 幅度 |scaleX−1| 隨極值嚴格遞減(耦合阻尼)。
  ST5 identity interface per tier: **每個檔位**的 sample(0)/sample(dur) 各 bone identity,且 shear 首尾 0
                                 + scale 首尾 (1,1)(可插 Loop 循環間)。
  ST6 neg-control / necessity   : (a) **平增益守衛**:增益階梯全 1.0 → ST2 兩峰遞增 FALSE 且各檔位逐位元
                                 == base(證閘測遞增非恆真);
                                 (b) **crux 必要性 — 天真 amplify 破壞守恆**:對同一 squash scale 幀施
                                 天真 `_amp_scale`(coupled_scale=False,g=Legend)→ 至少一極值
                                 |scaleX·scaleY−1| > TOL_VOL(守恆破壞),而耦合 amplify 同 g 仍守恆
                                 → 證耦合 amplify 是**必要**;
                                 (c) **耦合 amplify 單元測**:`_amp_scale_coupled` 對保積對 (sx,sy=1/sx)
                                 → sx**g·sy**g==1(對多個 g)、g=1.0 逐位元不變(向後相容);
                                 (d) **隔離/加性**:加入 squash 到 MAIN_SHOW_CATS 不擾動其他 beat —— 全檔位
                                 build 中,凡非 squash 的 beat 及其 `__tier` 變體,與「移除 squash 的 storyboard」
                                 之同名輸出逐位元相同(其餘主秀 scale 節拍仍走 `_amp_scale`,零回歸)。

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
# 復用 G-4' 的 shear 讀取與阻尼簽章判準,確保與 shear-gen / wobble-tier / squash-gen 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,base squash 峰值下限(確認確有明顯 shear)
MIN_ANISO = 0.05    # base squash scale 非均勻峰下限
TOL_VOL = 0.02      # 體積守恆 |scaleX·scaleY − 1| 上限(同 squash-gen 閘)


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


def _scale_xy(chans):
    fr = chans.get("scale")
    return [(f["x"], f["y"]) for f in fr] if fr else []


def _interior_scale(chans):
    """squash 的 scale 極值幀(去掉首尾 identity 端點)。"""
    xy = _scale_xy(chans)
    return xy[1:-1] if len(xy) >= 3 else []


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _aniso_peak(anim):
    """該 anim 全 bone 的峰 |scaleX−scaleY|(無 scale 回 0)。"""
    peaks = [max((abs(sx - sy) for (sx, sy) in _scale_xy(ch)), default=0.0)
             for ch in anim.get("bones", {}).values() if _scale_xy(ch)]
    return max(peaks, default=0.0)


def _is_strict_inc(xs):
    return all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                       # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)    # 帶檔位
    squash_beats = _squash_beats(base)
    R = {}

    # ---- ST1 present + backward-compat ----
    t1 = {"squash_beats": squash_beats, "base_weak": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": []}
    for qb in squash_beats:
        if _shear_peak(base[qb]) < MIN_SHEAR or _aniso_peak(base[qb]) < MIN_ANISO:
            t1["base_weak"].append(qb)
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
    # base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    t1_pass = (bool(squash_beats) and not any(t1[k] for k in
               ["base_weak", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed"]))
    R["ST1_present_backward_compat"] = {**t1, "pass": t1_pass}

    # ---- ST2 crux: dual-channel (shear + aniso) peaks monotone across tiers ----
    t2 = {"beats": {}, "fail_shear_mono": [], "fail_aniso_mono": [], "fail_base": []}
    for qb in squash_beats:
        sh_peaks = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        an_peaks = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_sh, base_an = _shear_peak(base[qb]), _aniso_peak(base[qb])
        sh_mono, an_mono = _is_strict_inc(sh_peaks), _is_strict_inc(an_peaks)
        super_eq = abs(sh_peaks[0] - base_sh) <= 1e-4 and abs(an_peaks[0] - base_an) <= 1e-4
        t2["beats"][qb] = {"shear_peaks": [round(p, 3) for p in sh_peaks],
                           "aniso_peaks": [round(p, 4) for p in an_peaks],
                           "base_shear": round(base_sh, 3), "base_aniso": round(base_an, 4),
                           "shear_mono": sh_mono, "aniso_mono": an_mono, "super_eq_base": super_eq}
        if not sh_mono:
            t2["fail_shear_mono"].append(qb)
        if not an_mono:
            t2["fail_aniso_mono"].append(qb)
        if not super_eq:
            t2["fail_base"].append(qb)
    t2_pass = (bool(t2["beats"]) and not t2["fail_shear_mono"]
               and not t2["fail_aniso_mono"] and not t2["fail_base"])
    R["ST2_dual_channel_peak_monotone"] = {**t2, "pass": t2_pass}

    # ---- ST3 crux: volume conservation preserved at every tier ----
    t3 = {"bad_volume": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                prod = [sx * sy for (sx, sy) in interior]
                t3["detail"][key] = [round(p, 5) for p in prod]
                if any(abs(p - 1.0) > TOL_VOL for p in prod):
                    t3["bad_volume"].append(key)
    t3_pass = bool(t3["detail"]) and not t3["bad_volume"]
    R["ST3_volume_preserved_per_tier"] = {**t3, "pass": t3_pass}

    # ---- ST4 damped signature (shear oscillation + squash-amount damping) per tier ----
    t4 = {"bad_shear_endpoints": [], "few_sign_changes": [], "shear_not_damped": [],
          "squash_not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                interior = _interior_scale(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                ends_ok = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                nsc = _sign_changes_zero(sx)
                sh_damp = _extrema_mags_decreasing(sx)
                mag = [abs(scx - 1.0) for (scx, scy) in interior]
                sq_damp = len(mag) >= 2 and all(mag[i + 1] < mag[i] - 1e-9 for i in range(len(mag) - 1))
                t4["detail"][key] = {"n_sign_changes": nsc, "shear_damped": sh_damp,
                                     "squash_mag": [round(m, 4) for m in mag], "squash_damped": sq_damp}
                if not ends_ok:
                    t4["bad_shear_endpoints"].append(key)
                if nsc < 3:
                    t4["few_sign_changes"].append(key)
                if not sh_damp:
                    t4["shear_not_damped"].append(key)
                if not sq_damp:
                    t4["squash_not_damped"].append(key)
    t4_pass = (bool(t4["detail"]) and not t4["bad_shear_endpoints"] and not t4["few_sign_changes"]
               and not t4["shear_not_damped"] and not t4["squash_not_damped"])
    R["ST4_damped_signature_per_tier"] = {**t4, "pass": t4_pass}

    # ---- ST5 identity interface per tier ----
    t5 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                t5["bad_interface"].append("{}__{}".format(qb, t))
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                    t5["shear_endpoints_nonzero"].append("{}__{}::{}".format(qb, t, bn))
                xy = _scale_xy(ch)
                if xy and (abs(xy[0][0] - 1.0) > 1e-6 or abs(xy[0][1] - 1.0) > 1e-6
                           or abs(xy[-1][0] - 1.0) > 1e-6 or abs(xy[-1][1] - 1.0) > 1e-6):
                    t5["scale_endpoints_nonident"].append("{}__{}::{}".format(qb, t, bn))
    t5_pass = (not t5["bad_interface"] and not t5["shear_endpoints_nonzero"]
               and not t5["scale_endpoints_nonident"])
    R["ST5_identity_interface_per_tier"] = {**t5, "pass": t5_pass}

    # ---- ST6 negative controls / necessity ----
    t6 = {}
    # (a) 平增益守衛:全 1.0 → 兩峰遞增 FALSE 且各檔位 == base
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
    t6["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) crux 必要性:天真 _amp_scale(coupled=False)在 g=Legend 破壞守恆;耦合(True)守恆
    g_leg = gains["Legend"]
    # 取一個真實 squash bone 的 scale 幀作 fixture
    fix_ch = None
    for bn, ch in base[squash_beats[0]]["bones"].items():
        if _interior_scale(ch):
            fix_ch = {"scale": [dict(f) for f in ch["scale"]]}
            break
    naive = TV.amplify_bone_tl(fix_ch, g_leg, coupled_scale=False)
    coup = TV.amplify_bone_tl(fix_ch, g_leg, coupled_scale=True)
    naive_prod = [f["x"] * f["y"] for f in naive["scale"][1:-1]]
    coup_prod = [f["x"] * f["y"] for f in coup["scale"][1:-1]]
    naive_breaks = any(abs(p - 1.0) > TOL_VOL for p in naive_prod)
    coup_holds = all(abs(p - 1.0) <= TOL_VOL for p in coup_prod)
    t6["b_naive_breaks_volume"] = {"g": g_leg, "naive_prod": [round(p, 4) for p in naive_prod],
                                   "coupled_prod": [round(p, 5) for p in coup_prod],
                                   "naive_breaks": naive_breaks, "coupled_holds": coup_holds,
                                   "pass": naive_breaks and coup_holds}
    # (c) 耦合 amplify 單元測:保積 + g=1 逐位元不變
    unit_ok, g1_ident = True, True
    # fixture 用 4 位小數(同 gen_squash 實際輸出精度)→ g=1.0 逐位元不變是可保證的向後相容契約
    for s in [1.14, 1.08, 1.2]:
        pair = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0},
                          {"time": 0.5, "x": s, "y": round(1.0 / s, 4)},
                          {"time": 1.0, "x": 1.0, "y": 1.0}]}
        for g in [1.35, 1.7, 2.1]:
            a = TV.amplify_bone_tl(pair, g, coupled_scale=True)
            sx, sy = a["scale"][1]["x"], a["scale"][1]["y"]
            if abs(sx * sy - 1.0) > TOL_VOL:
                unit_ok = False
        a1 = TV.amplify_bone_tl(pair, 1.0, coupled_scale=True)
        if json.dumps(a1, sort_keys=True) != json.dumps(pair, sort_keys=True):
            g1_ident = False
    t6["c_coupled_unit"] = {"volume_ok_all_g": unit_ok, "g1_byte_identical": g1_ident,
                            "pass": unit_ok and g1_ident}
    # (d) 隔離/加性:squash 入 MAIN_SHOW_CATS 不擾動其他 beat 及其 __tier 變體
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "squash"]}
    anims_no = G.build_animations(skel, sb_no, tier_gains=gains)
    regressed = []
    for nm, an in anims_no.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    t6["d_isolation_additive"] = {"regressed": regressed, "pass": not regressed}
    R["ST6_neg_control"] = {**t6, "pass": all(v["pass"] for v in t6.values())}

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
        for k in ["ST1_present_backward_compat", "ST2_dual_channel_peak_monotone",
                  "ST3_volume_preserved_per_tier", "ST4_damped_signature_per_tier",
                  "ST5_identity_interface_per_tier", "ST6_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("ST2 peaks per tier {}:".format(TIERS))
        for qb, d in R["ST2_dual_channel_peak_monotone"]["beats"].items():
            print("  {:10s} shear {}  aniso {}".format(qb, d["shear_peaks"], d["aniso_peaks"]))
        b = R["ST6_neg_control"]["b_naive_breaks_volume"]
        print("ST6b necessity (g={}): naive_prod {} (breaks={}) | coupled_prod {} (holds={})".format(
            b["g"], b["naive_prod"], b["naive_breaks"], b["coupled_prod"], b["coupled_holds"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
