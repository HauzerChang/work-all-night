#!/usr/bin/env python3
"""candidate G-4''''' 自我驗收閘 — squash 接檔位(tier)幅度差異化,**體積守恆耦合放大**(純 CPU)。

一路的 honest boundary(G-4'''' 留):squash(斜拉果凍擠壓,shear + 體積守恆非均勻 scale)是生成器
第一個同時產 shear+非均勻 scale 的節拍,但**未接檔位差異化** —— 因為 (J) 的 `amplify` 用
`_amp_scale`(只放大 identity **上方** overshoot、把 scaleY<1 當樓地板不動),對 squash 會**破壞
體積守恆**(scaleX 放大、scaleY 不動 → scaleX·scaleY≠1),故 G-4'''' 刻意把 squash 排除在
`MAIN_SHOW_CATS` 外。本次(G-4''''')補上:新增 `_amp_scale_coupled`(把兩軸共用的「squash 量 q」
以增益 g **一起**放大:scaleX=1+g·q、scaleY=1/(1+g·q)),`COUPLED_SCALE_CATS={squash}` 路由,
squash 併入 `MAIN_SHOW_CATS` → squash 的斜擠強度隨檔位遞增而**體積恆守恆**。

**關鍵:squash 的檔位軸需耦合放大** —— 幅度增益必須尊重「非均勻 scale 是體積守恆對」這個結構,
否則放大會把「squash & stretch」變成「單邊拉長」(破壞面積守恆)。這是 (J) 對稱 `_amp_scale`
(scale 對 identity 單邊、rotate/translate/shear 對 0 對稱)之外的**第三種**通道放大規則。

真值/fixture 同 (E/H/I/J/G-4'~G-4''''):從**先驗庫**(slot_bigwin,含 squash beat)→ `analyze_target`
→ **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。主秀運動無唯一
正解(PROPOSAL 手感),閘驗**客觀結構簽章(耦合放大下體積守恆 + 幅度遞增 + 阻尼簽章保形)**,
非美感;負對照(天真非耦合放大破壞體積守恆 / 平增益 / 隔離)證鑑別力(閘可信)。

AC(客觀、可量測):
  P1 present + backward-compat : 每檔位 `squash__{tier}` 直出、finite、有 bone、≥1 bone 同時帶
                                 shear+scale;名經 `beat_category` 仍路由回 squash;**Super==base**
                                 (g=1.0 逐位元不變)、base squash 與無檔位呼叫逐位元相同;
                                 `tier_gains=None` → **不產** squash 變體。
  P2 crux coupled monotone     : 三通道**同時**隨檔位嚴格遞增(耦合):(a)shearX 峰;(b)拉長量
                                 max(scaleX−1);(c)非均勻峰 max|scaleX−scaleY|,Super<Mega<Omg<Legend。
  P3 crux volume preserved     : **每個檔位**每個 squash bone 的每個內部極值幀 |scaleX·scaleY−1|≤TOL_VOL
                                 (放大後**體積仍守恆**)—— 正是天真 `_amp_scale` 會破壞、耦合放大才保住的點。
  P4 signature+interface kept  : **每個檔位**——shear 阻尼振盪(首尾 0、繞 0 變號≥3、相繼極值遞減)、
                                 squash 幅度 |scaleX−1| 隨極值嚴格遞減(阻尼耦合)、sample(0/dur) identity。
  P5 neg-control               : (a)**天真非耦合放大守衛(crux)**:對 base squash 施 `coupled_scale=False`
                                 的 (J) 放大(Legend g)→ 至少一極值 |scaleX·scaleY−1|>TOL_VOL(**體積被破壞**),
                                 而耦合放大同 g 下全 ≤TOL_VOL → 證耦合放大確實在做事、閘非恆真;
                                 (b)**平增益守衛**:增益全 1.0 → P2 三通道皆非遞增,且 squash__tier==base;
                                 (c)**耦合隔離**:`COUPLED_SCALE_CATS=={squash}`;squash 變體走耦合(≠非耦合放大
                                 結果),非-squash 主秀 beat 的變體 == 標準 (J) 放大(不受耦合影響、加性零回歸)。

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
# 復用 G-4' 的 shear 讀取與阻尼簽章判準,確保與 shear-gen / squash-gen 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
TOL_VOL = 0.02      # 體積守恆 |scaleX·scaleY − 1| 上限(同 squash-gen 閘;耦合放大實測 <2e-4)
MIN_ANISO = 0.05    # scale 非均勻峰下限


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


def _scale_xy(ch):
    fr = ch.get("scale")
    return [(f["x"], f["y"]) for f in fr] if fr else []


def _interior_scale(ch):
    xy = _scale_xy(ch)
    return xy[1:-1] if len(xy) >= 3 else []


def _is_strict_inc(v):
    return all(v[i + 1] > v[i] + 1e-9 for i in range(len(v) - 1))


def _shear_peak(an):
    return max((max(abs(v) for v in _shear_x(ch)) for ch in an.get("bones", {}).values() if _shear_x(ch)),
               default=0.0)


def _stretch_peak(an):
    """max over bones of max(scaleX − 1)(拉長量峰)。"""
    peaks = []
    for ch in an.get("bones", {}).values():
        xy = _scale_xy(ch)
        if xy:
            peaks.append(max(sx - 1.0 for (sx, sy) in xy))
    return max(peaks, default=0.0)


def _aniso_peak(an):
    """max over bones of max|scaleX − scaleY|(非均勻峰)。"""
    peaks = []
    for ch in an.get("bones", {}).values():
        xy = _scale_xy(ch)
        if xy:
            peaks.append(max(abs(sx - sy) for (sx, sy) in xy))
    return max(peaks, default=0.0)


def _max_vol_err(an):
    """該 anim 全 squash bone 全內部極值的 max |scaleX·scaleY − 1|(體積守恆偏差)。"""
    errs = []
    for ch in an.get("bones", {}).values():
        for (sx, sy) in _interior_scale(ch):
            errs.append(abs(sx * sy - 1.0))
    return max(errs, default=0.0)


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                        # tier_gains=None
    full = G.build_animations(skel, sb, tier_gains=gains)      # 帶檔位
    squash_beats = _squash_beats(base)
    R = {}

    # ---- P1 present + backward-compat + dual-channel ----
    p1 = {"squash_beats": squash_beats, "missing": [], "not_finite": [], "no_bones": [],
          "no_dual": [], "misrouted": [], "super_ne_base": [], "base_changed": [], "variants_when_none": []}
    for qb in squash_beats:
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = full.get(vk)
            if an is None:
                p1["missing"].append(vk); continue
            if not SA.all_finite(an):
                p1["not_finite"].append(vk)
            if not an.get("bones"):
                p1["no_bones"].append(vk)
            if not any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values()):
                p1["no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                p1["misrouted"].append((vk, G.beat_category(vk)))
        # Super(g=1.0)逐位元 == base squash(向後相容)
        if json.dumps(full.get("{}__Super".format(qb)), sort_keys=True) != json.dumps(base[qb], sort_keys=True):
            p1["super_ne_base"].append(qb)
    # base(含所有 beat)逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(full.get(k), sort_keys=True):
            p1["base_changed"].append(k)
    # tier_gains=None → 不產任何 __tier squash 變體
    p1["variants_when_none"] = [k for k in base if "__" in k and G.beat_category(k) == "squash"]
    p1_pass = (bool(squash_beats) and not any(p1[k] for k in
               ["missing", "not_finite", "no_bones", "no_dual", "misrouted",
                "super_ne_base", "base_changed", "variants_when_none"]))
    R["P1_present_backward_compat"] = {**p1, "pass": p1_pass}

    # ---- P2 crux: coupled amplitude monotone (three channels together) ----
    p2 = {"beats": {}, "fail": []}
    for qb in squash_beats:
        sh = [_shear_peak(full["{}__{}".format(qb, t)]) for t in TIERS]
        st = [_stretch_peak(full["{}__{}".format(qb, t)]) for t in TIERS]
        an = [_aniso_peak(full["{}__{}".format(qb, t)]) for t in TIERS]
        sh_mono, st_mono, an_mono = _is_strict_inc(sh), _is_strict_inc(st), _is_strict_inc(an)
        p2["beats"][qb] = {"shear_peak": [round(x, 3) for x in sh],
                           "stretch_peak": [round(x, 4) for x in st],
                           "aniso_peak": [round(x, 4) for x in an],
                           "shear_mono": sh_mono, "stretch_mono": st_mono, "aniso_mono": an_mono}
        if not (sh_mono and st_mono and an_mono):
            p2["fail"].append(qb)
    R["P2_coupled_monotone"] = {"tiers": TIERS, **p2, "pass": bool(squash_beats) and not p2["fail"]}

    # ---- P3 crux: volume conservation preserved per tier ----
    p3 = {"per_tier_max_vol_err": {}, "bad": []}
    for qb in squash_beats:
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            err = _max_vol_err(full[vk])
            p3["per_tier_max_vol_err"][vk] = round(err, 6)
            if err > TOL_VOL:
                p3["bad"].append((vk, round(err, 6)))
    R["P3_volume_preserved"] = {"tol_vol": TOL_VOL, **p3, "pass": bool(squash_beats) and not p3["bad"]}

    # ---- P4 signature + identity interface preserved per tier ----
    p4 = {"bad_shear_ends": [], "few_sign_changes": [], "shear_not_damped": [],
          "squash_not_damped": [], "bad_interface": []}
    for qb in squash_beats:
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = full[vk]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                p4["bad_interface"].append(vk)
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if sx:
                    if not (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6):
                        p4["bad_shear_ends"].append("{}::{}".format(vk, bn))
                    if _sign_changes_zero(sx) < 3:
                        p4["few_sign_changes"].append("{}::{}".format(vk, bn))
                    if not _extrema_mags_decreasing(sx):
                        p4["shear_not_damped"].append("{}::{}".format(vk, bn))
                interior = _interior_scale(ch)
                if interior:
                    mag = [abs(sx_ - 1.0) for (sx_, sy_) in interior]
                    if not (len(mag) >= 2 and all(mag[i + 1] < mag[i] - 1e-9 for i in range(len(mag) - 1))):
                        p4["squash_not_damped"].append("{}::{}".format(vk, bn))
    R["P4_signature_interface"] = {**p4, "pass": not any(p4[k] for k in p4)}

    # ---- P5 negative controls ----
    p5 = {}
    g_leg = gains["Legend"]
    # (a) 天真非耦合放大守衛(crux):對 base squash 施 coupled_scale=False 的放大 → 破壞體積守恆;
    #     耦合放大同 g 下仍守恆 → 證耦合放大確實在做事(閘測「體積守恆」非「有 scale 即可」)。
    a_detail = {}
    naive_breaks_all = True
    coupled_holds_all = True
    for qb in squash_beats:
        naive = TV.amplify_anim(base[qb], g_leg, coupled_scale=False)
        coupled = TV.amplify_anim(base[qb], g_leg, coupled_scale=True)
        e_naive = _max_vol_err(naive)
        e_coup = _max_vol_err(coupled)
        a_detail[qb] = {"naive_vol_err": round(e_naive, 5), "coupled_vol_err": round(e_coup, 5)}
        if not (e_naive > TOL_VOL):
            naive_breaks_all = False
        if not (e_coup <= TOL_VOL):
            coupled_holds_all = False
    p5["a_naive_amplify_breaks_volume"] = {"detail": a_detail,
                                           "pass": bool(squash_beats) and naive_breaks_all and coupled_holds_all}
    # (b) 平增益守衛:全 1.0 → P2 三通道皆非遞增 且 squash__tier == base(逐位元)
    flat = {t: 1.0 for t in TIERS}
    flat_full = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat = False
    flat_ident = True
    for qb in squash_beats:
        for ch_name, fn in (("shear", _shear_peak), ("stretch", _stretch_peak), ("aniso", _aniso_peak)):
            vals = [fn(flat_full["{}__{}".format(qb, t)]) for t in TIERS]
            if _is_strict_inc(vals):
                any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_full["{}__{}".format(qb, t)], sort_keys=True) != json.dumps(base[qb], sort_keys=True):
                flat_ident = False
    p5["b_flat_gain_guard"] = {"any_channel_monotone_flat": any_mono_flat, "flat_variants_eq_base": flat_ident,
                               "pass": (not any_mono_flat) and flat_ident}
    # (c) 耦合隔離:COUPLED_SCALE_CATS=={squash};squash 變體走耦合(≠非耦合放大);
    #     非-squash 主秀 beat 變體 == 標準 (J) 放大(coupled_scale=False)—— 耦合不外洩。
    coupled_set_ok = TV.COUPLED_SCALE_CATS == {"squash"}
    squash_routed_coupled = True
    for qb in squash_beats:
        got = full["{}__Legend".format(qb)]
        exp_coupled = TV.amplify_anim(base[qb], g_leg, coupled_scale=True)
        exp_naive = TV.amplify_anim(base[qb], g_leg, coupled_scale=False)
        if not (json.dumps(got, sort_keys=True) == json.dumps(exp_coupled, sort_keys=True)
                and json.dumps(got, sort_keys=True) != json.dumps(exp_naive, sort_keys=True)):
            squash_routed_coupled = False
    # 非-squash 主秀 beat:變體 == 標準放大(非耦合)
    leak = []
    # 非-squash、非-count-aware 主秀 beat(count-aware 變體另重生成,不宜比逐位元放大)
    main_beats = {nm: G.beat_category(nm) for nm in base
                  if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS
                  and G.beat_category(nm) not in ({"squash"} | TV.COUNT_AWARE_CATS)}
    for beat, cat in main_beats.items():
        for t in TIERS:
            vk = "{}__{}".format(beat, t)
            exp = TV.amplify_anim(base[beat], gains[t], coupled_scale=False)
            if json.dumps(full.get(vk), sort_keys=True) != json.dumps(exp, sort_keys=True):
                leak.append((vk, cat))
    p5["c_coupling_isolated"] = {"coupled_set": sorted(TV.COUPLED_SCALE_CATS),
                                 "coupled_set_ok": coupled_set_ok,
                                 "squash_routed_coupled": squash_routed_coupled,
                                 "non_squash_leak": leak,
                                 "pass": coupled_set_ok and squash_routed_coupled and not leak}
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
        for k in ["P1_present_backward_compat", "P2_coupled_monotone", "P3_volume_preserved",
                  "P4_signature_interface", "P5_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("P2 per-tier (shear / stretch / aniso) {}:".format(TIERS))
        for qb, d in R["P2_coupled_monotone"]["beats"].items():
            print("  {:10s} shear {}  stretch {}  aniso {}".format(
                qb, d["shear_peak"], d["stretch_peak"], d["aniso_peak"]))
        print("P3 per-tier max |scaleX·scaleY−1|:", R["P3_volume_preserved"]["per_tier_max_vol_err"])
        print("P5a naive-vs-coupled vol err:", R["P5_neg_control"]["a_naive_amplify_breaks_volume"]["detail"])
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
