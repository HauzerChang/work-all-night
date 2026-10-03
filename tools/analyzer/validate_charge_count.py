#!/usr/bin/env python3
"""candidate (G-4'''''-charge) 自我驗收閘 — charge 蓄力充能**階段數**隨檔位遞增(count-aware,純 CPU)。

candidate (J) 讓 charge 的 release 峰**幅度**隨檔位遞增(愈高檔位愈爆),但各檔位仍是**同樣 1 階**單發蓄力
—— 有「多爆」沒「蓄幾段」。本次 (G-4'''''-charge) 補上 charge 的充能-釋放**階段數** ncharge **隨檔位嚴格
遞增**(Super 1 → Mega 2 → Omg 3 → Legend 4):愈高檔位愈多階蓄力(每階一段長 hold + 遞增 release)。

**關鍵:幅度增益加不出蓄力階段** —— 階數是關鍵幀**拓樸**(dip→hold→release 的窗數),必須在 `gen_anticipate_hold`
生成當下決定;事後 `amplify_bone_tl` 只能同比放大既有 overshoot、無法多長一階。故不走 amplify,而是對 charge
檔位變體以該檔位 ncharge **重生成**整個 beat,再疊 (J) 幅度增益 g → 與幅度軸**正交可疊**(階數 [1,2,3,4] ×
release 峰幅皆遞增)。此模式同 (J-2)combo / (G-4''')wobble / (G-4'''''-c)squash / (G-4''''''-count)twist,
惟階數階梯各類別獨立(charge→TIER_CHARGE_CYCLES,build_animations 依 cat 路由)。

**charge 獨有 crux(與 combo count 的差異 —— 計數簽章須多驗一層)**:combo 與 charge count 的**外形相同**
(都是「N 個遞增 scale 峰」)—— 光數 impact 峰無法鑑別。差別在**峰間**:combo 峰間只有**短** dip
(擊間微回 >HOLD_LEVEL,hold 佔比小);charge 每階在 release 前有一段**持續**低 hold(sustained,佔該階大半)。
故 charge count 簽章須在「階數 == ncharge」之外**多驗一層**:**每一階都是真蓄力階**(該階 hold 佔比 ≥ 門檻)。
以此對 combo 做負對照(combo 每階 hold 佔比 < 門檻 → FAIL charge-count 簽章)—— 證「數峰 + 每階 hold」兩條件
並立才是 charge count,呼應 (J-3)「跨件 count 比單件 count 多驗一層」的精神(真簽章常需兩獨立條件並立)。

真值界定同 (E/H/I/J/J-2/G-4'''…):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位蓄愈多階」是可量化的檔位簽章,用負對照證鑑別力(閘可信)。從**先驗庫** → **真實 build_spine
robot 骨架** → `build_animations(..., tier_gains, tier_charge_cycles)` 端到端量,與 (J) 同一 fixture。

AC(客觀、可量測):
  CC1 present + backward-compat : 每檔位 `charge__{tier}` 皆產出、finite、有 bone;**base charge 恆 1 階不變**
                                (逐位元同無檔位);且 **charge__Super(ncharge=1,g=1)逐位元同 base charge**;
                                **不帶** `tier_charge_cycles`(=None)時 charge 變體逐位元同 (J) 幅度-only
                                (加性 opt-in 零回歸)。
  CC2 crux — stage count monotone: 各檔位 charge 的蓄力**階段數**(= impact release 峰數)== 宣告 [1,2,3,4] 且
                                Super<Mega<Omg<Legend **嚴格遞增**;Super 階數 == base 階數(向後相容)。
  CC3 signature preserved        : **每檔位** charge 仍 (a)首尾 setup identity(可插 Loop);(b)具 charge 簽章
                                (峰前長蓄力佔比 ≥HOLD_FRAC_THR 且峰前非塌陷 > SQUASH_FLOOR,非 reveal);
                                (c)**每一階**的 hold 佔比 ≥ STAGE_HOLD_THR(crux 多驗層:每階皆真蓄力階);
                                (d)階內 release 峰嚴格遞增(末階=role peak)。**且**峰幅仍隨檔位嚴格遞增
                                (階數軸不抵消幅度軸,兩效可疊)。
  CC4 orthogonality             : (a) 階數 + **平增益**(全 g=1.0)→ 階數仍遞增(結構獨立於幅度)、峰幅**不**遞增;
                                (b) 增益 + **無階數**(tcc=None)→ 階數恆 1、峰幅遞增(兩軸可獨立開關)。
  CC5 neg-control               : (a) **平階數**(全 1)→ 階數單調性 FALSE(證閘測遞增非恆真);
                                (b) **crux discriminator**:combo clip(與 charge count 同為「N 遞增 scale 峰」)
                                每階 hold 佔比 < STAGE_HOLD_THR → **FAIL charge-count 簽章** → 證「每階持續 hold」
                                是 charge count 與 combo count 的鑑別子(光數峰不夠);
                                (c) 階數**只作用 charge**:非-charge 主秀 beat 變體逐位元同幅度-only(不外洩);
                                且無宣告的 genre(slot_reveal)→ `charge_cycles_for` 回 None → 不亂加階數變體。

用法:
  python3 validate_charge_count.py            # 摘要
  python3 validate_charge_count.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
import beat_templates as BT
from analyze_target import analyze
# 復用 0g 的 charge 度量,確保簽章判準與 validate_more_beats / validate_priors_combo_charge 完全一致
from validate_more_beats import (series, impact_peaks, pre_peak_hold_frac, has_charge_signature,
                                 HOLD_LEVEL, HOLD_FRAC_THR, SQUASH_FLOOR, N)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL_IDENT = 1e-4
# crux 門檻:每階 hold 佔比(release 前一階區間內 scale<HOLD_LEVEL 的佔比)。實測 charge 每階 ≥0.70、
# combo 每階 ≤0.48 → 0.60 居中,兩側皆有 >0.1 餘裕(見 CC5b 負對照)。
STAGE_HOLD_THR = 0.60


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/charge_count_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _charge_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "charge"]


def _main_beats(anims):
    return {nm: G.beat_category(nm) for nm in anims
            if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


def _peaks_idx(vals, prom=BT.IMPACT_PROM):
    """時間序中 ≥prom 的局部極大值**索引**(嚴格上升→非上升);release 峰 = 蓄力階段數。"""
    return [i for i in range(1, len(vals) - 1) if vals[i] >= prom and vals[i - 1] < vals[i] >= vals[i + 1]]


def _stage_count(anim):
    """該 anim 的蓄力階段數 = 各 bone scaleX 的 impact release 峰數(各 bone 同形 → 取一致;不一致回 -1)。"""
    counts = set()
    for bn in anim.get("bones", {}):
        counts.add(len(_peaks_idx(series(anim, bn))))
    if not counts:
        return 0
    return counts.pop() if len(counts) == 1 else -1


def _stage_hold_fracs(vals, level=HOLD_LEVEL):
    """各階(前一峰→本峰的區間)內 scale<level 的佔比 → [frac_0, frac_1, ...]。

    charge 每階一段長 hold → 每階佔比高;combo 每階僅短 dip(擊間微回 >level)→ 每階佔比低。
    這是 charge count 與 combo count 的鑑別子(crux 多驗層)。"""
    pk = _peaks_idx(vals)
    fracs, start = [], 0
    for p in pk:
        seg = vals[start:p]
        if seg:
            fracs.append(sum(1 for v in seg if v < level) / len(seg))
        start = p
    return fracs


def _global_peak(anim):
    """該 anim 全 bone scaleX 的全域峰值(release overshoot 強度)。"""
    pk = 1.0
    for bn in anim.get("bones", {}):
        vs = series(anim, bn)
        if vs:
            pk = max(pk, max(vs))
    return pk


def _release_peaks(anim):
    """任一 bone 的各階 release 峰值序列(用於驗階內遞增,末階=amplified role peak)。"""
    for bn in anim.get("bones", {}):
        vs = series(anim, bn)
        pv = [vs[i] for i in _peaks_idx(vs)]
        if pv:
            return pv
    return []


def _endpoints_identity(anim, tol=TOL_IDENT):
    """首尾幀皆 setup identity(可插 Loop)。"""
    dur = SA.duration(anim)
    for t in (0.0, dur):
        bs = SA.sample(anim, t)["bones"]
        for bd in bs.values():
            if not all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT):
                return False
    return True


def _is_strict_inc(xs):
    return len(xs) >= 2 and all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def _dj(a):
    return json.dumps(a, sort_keys=True)


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    cyc = TV.charge_cycles_for(GENRE)

    base = G.build_animations(skel, sb)                                              # 無檔位
    amp_only = G.build_animations(skel, sb, tier_gains=gains)                        # (J) 幅度-only
    full = G.build_animations(skel, sb, tier_gains=gains, tier_charge_cycles=cyc)    # 幅度+階數

    charge_beats = _charge_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- CC1 present + backward-compat ----
    c1 = {"charge_beats": charge_beats, "missing": [], "not_finite": [], "no_bones": [],
          "base_changed": [], "super_ne_base": [], "amp_only_regressed": []}
    for cb in charge_beats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            an = full.get(vk)
            if an is None:
                c1["missing"].append(vk); continue
            if not SA.all_finite(an):
                c1["not_finite"].append(vk)
            if not an.get("bones"):
                c1["no_bones"].append(vk)
        # base charge 恆 1 階且逐位元同無檔位
        if _stage_count(full[cb]) != 1 or _dj(base[cb]) != _dj(full[cb]):
            c1["base_changed"].append(cb)
        # charge__Super(ncharge=1,g=1)逐位元同 base charge
        if _dj(full.get(cb + "__Super")) != _dj(base[cb]):
            c1["super_ne_base"].append(cb)
    # tier_charge_cycles=None 時,charge 變體逐位元同 (J) 幅度-only(加性 opt-in)
    none_run = G.build_animations(skel, sb, tier_gains=gains, tier_charge_cycles=None)
    for cb in charge_beats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            if _dj(none_run.get(vk)) != _dj(amp_only.get(vk)):
                c1["amp_only_regressed"].append(vk)
    c1_pass = bool(charge_beats) and not any(c1[k] for k in
              ["missing", "not_finite", "no_bones", "base_changed", "super_ne_base", "amp_only_regressed"])
    R["CC1_present_backward_compat"] = {**c1, "pass": c1_pass}

    # ---- CC2 crux: stage count monotone ----
    c2 = {"beats": {}, "fail": []}
    expected = [cyc[t] for t in TIERS]
    for cb in charge_beats:
        counts = [_stage_count(full["{}__{}".format(cb, t)]) for t in TIERS]
        base_count = _stage_count(base[cb])
        mono = _is_strict_inc(counts)
        matches = (counts == expected)
        super_eq_base = (counts[0] == base_count)
        c2["beats"][cb] = {"counts": counts, "expected": expected, "base_count": base_count,
                           "monotone": mono, "matches_declared": matches, "super_eq_base": super_eq_base}
        if not (mono and matches and super_eq_base):
            c2["fail"].append(cb)
    c2_pass = bool(charge_beats) and not c2["fail"]
    R["CC2_stage_count_monotone"] = {"tiers": TIERS, **c2, "pass": c2_pass}

    # ---- CC3 signature preserved per tier + amplitude still monotone ----
    c3 = {"bad_endpoints": [], "no_charge_sig": [], "weak_stage_hold": [], "stages_not_escalating": [],
          "amp_not_mono": [], "detail": {}}
    for cb in charge_beats:
        for t in TIERS:
            an = full["{}__{}".format(cb, t)]
            key = "{}__{}".format(cb, t)
            ends_ok = _endpoints_identity(an)
            sig_ok = has_charge_signature(an)
            # 每階 hold 佔比(取各 bone 最小階 → 最嚴格)
            min_stage_frac = 1.0
            for bn in an.get("bones", {}):
                for fr in _stage_hold_fracs(series(an, bn)):
                    min_stage_frac = min(min_stage_frac, fr)
            rel = _release_peaks(an)
            escal = _is_strict_inc(rel) if len(rel) >= 2 else True   # 單階(Super)無遞增可驗 → 視為 OK
            c3["detail"][key] = {"endpoints_identity": ends_ok, "charge_sig": sig_ok,
                                 "min_stage_hold_frac": round(min_stage_frac, 3),
                                 "release_peaks": [round(x, 3) for x in rel], "stages_escalating": escal}
            if not ends_ok:
                c3["bad_endpoints"].append(key)
            if not sig_ok:
                c3["no_charge_sig"].append(key)
            if min_stage_frac < STAGE_HOLD_THR:
                c3["weak_stage_hold"].append(key)
            if not escal:
                c3["stages_not_escalating"].append(key)
        # 峰幅仍隨檔位嚴格遞增(階數軸不抵消幅度軸)
        peaks = [_global_peak(full["{}__{}".format(cb, t)]) for t in TIERS]
        if not _is_strict_inc(peaks):
            c3["amp_not_mono"].append((cb, [round(p, 3) for p in peaks]))
    c3_pass = (bool(c3["detail"]) and not c3["bad_endpoints"] and not c3["no_charge_sig"]
               and not c3["weak_stage_hold"] and not c3["stages_not_escalating"] and not c3["amp_not_mono"])
    R["CC3_signature_preserved"] = {"stage_hold_thr": STAGE_HOLD_THR, **c3, "pass": c3_pass}

    # ---- CC4 orthogonality ----
    # (a) 階數 + 平增益 → 階數仍遞增、峰幅不遞增(結構獨立於幅度)
    flat_gain = {t: 1.0 for t in TIERS}
    ca = G.build_animations(skel, sb, tier_gains=flat_gain, tier_charge_cycles=cyc)
    counts_flatgain = {cb: [_stage_count(ca["{}__{}".format(cb, t)]) for t in TIERS] for cb in charge_beats}
    peaks_flatgain = {cb: [round(_global_peak(ca["{}__{}".format(cb, t)]), 3) for t in TIERS] for cb in charge_beats}
    a_ok = (bool(charge_beats) and all(_is_strict_inc(v) for v in counts_flatgain.values())
            and all(not _is_strict_inc(v) for v in peaks_flatgain.values()))
    # (b) 增益 + 無階數 → 階數恆 1、峰幅遞增
    counts_gainonly = {cb: [_stage_count(amp_only["{}__{}".format(cb, t)]) for t in TIERS] for cb in charge_beats}
    peaks_gainonly = {cb: [round(_global_peak(amp_only["{}__{}".format(cb, t)]), 3) for t in TIERS] for cb in charge_beats}
    b_ok = (bool(charge_beats) and all(v == [1, 1, 1, 1] for v in counts_gainonly.values())
            and all(_is_strict_inc(v) for v in peaks_gainonly.values()))
    R["CC4_orthogonality"] = {
        "a_counts_with_flat_gain": counts_flatgain, "a_peaks_with_flat_gain": peaks_flatgain, "a_pass": a_ok,
        "b_gain_only_counts_fixed1": counts_gainonly, "b_gain_only_peaks": peaks_gainonly, "b_pass": b_ok,
        "pass": a_ok and b_ok}

    # ---- CC5 negative controls ----
    c5 = {}
    # (a) 平階數(全 1)→ 階數單調性 FALSE
    flat_cyc = {t: 1 for t in TIERS}
    fc = G.build_animations(skel, sb, tier_gains=gains, tier_charge_cycles=flat_cyc)
    any_mono_flat = any(_is_strict_inc([_stage_count(fc["{}__{}".format(cb, t)]) for t in TIERS]) for cb in charge_beats)
    c5["a_flat_cycles_guard"] = {"any_count_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) crux discriminator:combo(同為 N 遞增 scale 峰)每階 hold 佔比 < 門檻 → FAIL charge-count 簽章
    combo_variants = [k for k in full if "__" in k and G.beat_category(k) == "combo"]
    combo_stage_max = {}
    combo_all_below = True
    for vk in combo_variants:
        an = full[vk]
        mx = 0.0
        for bn in an.get("bones", {}):
            for fr in _stage_hold_fracs(series(an, bn)):
                mx = max(mx, fr)
        combo_stage_max[vk] = round(mx, 3)
        if mx >= STAGE_HOLD_THR:
            combo_all_below = False
    # 且 combo 確有多個 release 峰(證「外形相同」非「combo 沒峰」)
    combo_has_peaks = all(_stage_count(full[vk]) >= 3 for vk in combo_variants)
    c5["b_combo_discriminator"] = {"combo_variants": combo_variants, "combo_max_stage_hold_frac": combo_stage_max,
                                   "thr": STAGE_HOLD_THR, "combo_all_below_thr": combo_all_below,
                                   "combo_has_multiple_peaks": combo_has_peaks,
                                   "pass": bool(combo_variants) and combo_all_below and combo_has_peaks}
    # (c) 階數只作用 charge:非-charge 主秀 beat 變體逐位元同幅度-only(不外洩)
    leak = []
    for beat, cat in main_beats.items():
        if cat == "charge":
            continue
        for t in TIERS:
            vk = "{}__{}".format(beat, t)
            if _dj(full.get(vk)) != _dj(amp_only.get(vk)):
                leak.append((vk, cat))
    # 且無宣告的 genre → charge_cycles_for None → 不產階數變體(借 slot_bigwin 骨架 + slot_reveal 分鏡)
    rv_cyc = TV.charge_cycles_for("slot_reveal")
    c5["c_cycles_isolated_to_charge"] = {"leaked_variants": leak,
                                         "charge_cycles_for_slot_reveal": rv_cyc,
                                         "pass": not leak and rv_cyc is None}
    R["CC5_neg_control"] = {**c5, "pass": all(v["pass"] for v in c5.values())}

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
        for k in ["CC1_present_backward_compat", "CC2_stage_count_monotone",
                  "CC3_signature_preserved", "CC4_orthogonality", "CC5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("CC2 charge stage counts per tier {}:".format(TIERS))
        for cb, d in R["CC2_stage_count_monotone"]["beats"].items():
            print("  {:14s} {}  (base {})".format(cb, d["counts"], d["base_count"]))
        print("CC5b combo discriminator max per-stage hold frac (thr {}):".format(STAGE_HOLD_THR))
        for vk, mx in R["CC5_neg_control"]["b_combo_discriminator"]["combo_max_stage_hold_frac"].items():
            print("  {:16s} {}".format(vk, mx))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
