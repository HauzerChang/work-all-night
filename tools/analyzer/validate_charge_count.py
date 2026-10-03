#!/usr/bin/env python3
"""candidate (G-4'''''-charge) 自我驗收閘 — charge 蓄力「階梯數」隨檔位遞增(純 CPU)。

candidate (J) 讓主秀 beat 依檔位**幅度**差異化(愈高檔位愈爆),但所有檔位的 charge 仍是**同樣單段長蓄力**
——「多爆」有了、「充幾段」沒有。本閘驗 (G-4'''''-charge):charge 的充能**階梯數** = nstage **隨檔位嚴格遞增**
(Super 1 → Mega 2 → Omg 3 → Legend 4),且此**結構**軸與 (J) 的**幅度**軸**正交可疊**、不破壞任何既有簽章/介面契約。

階梯數是**結構**(gen 時決定 pre-peak 充能台數,非事後 amplify 能加出來——amplify 只脹 identity 上方的釋放
overshoot、下方充能樓地板不動)—— 故走 `tier_charge_stages` 在 `build_animations` 對 charge 檔位變體以該檔位
nstage **重生成**再套幅度增益。真值界定同 (E/H/I/J):主秀運動無唯一正解(先驗手感),閘驗**客觀結構簽章非美感**;
用負對照證鑑別力(閘可信)。

**charge 段數獨有 crux(與 combo 段數的本質差異)**:combo 的段數 = **遞增 impact 峰數**(各峰 ≥IMPACT_PROM);
charge 的段數 = **pre-peak 充能台數**(各為局部極小,**全在 identity 下方** <1.0 <IMPACT_PROM)。故 charge 階梯數
增多**不增 impact 峰**(唯一 impact 仍是釋放)→ 段數增多後仍 **has_charge_signature 且非 combo**(兩簽章互斥
不因段數變化而混淆)。這是本閘相對 K(combo count)多驗的一層。

閘從**先驗庫**經 `analyze_target`(build_storyboard)→ **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains, tier_charge_stages)` 端到端量,與 (J)/(J-2) 閘同一 fixture。

  CH1 present + backward-compat : 每檔位皆產 `charge__{tier}` 且 finite/有 bone;base charge 不變(恆 nstage=1,
                                 逐位元同無檔位);**且** 不帶 `tier_charge_stages`(=None)時 charge 變體逐位元同 (J)
                                 幅度-only 輸出 → 證 (G-4'''''-charge) 為**加性 opt-in**、對 (J) 零回歸。
  CH2 count monotone (crux)    : 各檔位 charge 的**充能台數**(pre-peak 局部極小數)== 宣告 nstage 且
                                 Super<Mega<Omg<Legend **嚴格遞增**;每檔位變體各充能台**逐段更深**(distinct 局部極小)。
  CH3 interface+signature kept : 每檔位——首尾 setup identity、仍 has_charge_signature(hold 佔比≥0.35 + squash-floor)、
                                 仍 settle(變號≥3)、**仍非 combo**(crux:充能台全在 identity 下方 → 段數增多不造出
                                 第二 impact 峰)、且**幅度**(釋放 overshoot)仍 Super<Mega<Omg<Legend 單調
                                 (證與 (J) 疊加不衝突)。
  CH4 orthogonality            : (a) stages + **平增益**(全 1.0)→ 台數仍遞增(階梯數是**結構**,與幅度無關);
                                 (b) gains + **無 stages**(None)→ 各檔位 charge 台數**恆 1**、但幅度遞增
                                 → 兩軸可獨立開關(正交);**crux**:幅度增益**加不出第二道充能台**(證結構須重生成)。
  CH5 neg-control              : (a) **平階梯數**(全 1)→ CH2 台數單調性 FALSE(證閘在測遞增、非恆真);
                                 (b) 無宣告 count 的 genre(slot_reveal)→ `charge_stages_for` 回 None
                                    → charge 變體不產(gains 亦 None);
                                 (c) **charge count 不外洩**:只帶 `tier_charge_stages`(不帶其餘 count 圖)時,
                                    非-charge 的 count-aware 主秀 beat(combo/wobble/squash/twist)之 tier 變體
                                    逐位元同 (J) 幅度-only(charge 的段數圖不路由到別的節拍)。

用法:
  python3 validate_charge_count.py            # 摘要
  python3 validate_charge_count.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze
import tier_variants as TV
from validate_more_beats import (series, sign_changes, impact_peaks,
                                 has_combo_signature, has_charge_signature,
                                 pre_peak_hold_frac)
from validate_cascade import is_strictly_increasing

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
STAGE_PROM = 0.015  # 充能台 prominence 門檻:台底須較其後 re-grip 回升 ≥此才計一台
                    # (台底↔re-grip 最小落差 0.03 = CHARGE_FLOOR_HI−CHARGE_REGRIP 的 |0.90−0.93|,遠大於此;
                    #  用「回升幅度」而非逐樣本差 → 對 sampler 慢坡/捨入穩健,見 charge_stages docstring)


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/charge_count_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def charge_stages(vals, prom=STAGE_PROM):
    """pre-peak 充能台數 = 全域峰前以 prominence 計的局部極小(谷)數(flat 谷算 1)。

    充能台皆在 identity 下方且逐段更深,台間以 re-grip(<0.97)分隔、末台由釋放 overshoot 收回 → 每台是一個
    谷。**用「谷底↔其後回升幅度 ≥prom」計谷,而非逐樣本差**:re-grip/釋放的回升在 N=240 取樣下每樣本斜率可能
    <任何固定 eps(慢坡),逐樣本差會把慢坡誤判成平段而漏數;prominence(值域落差)對取樣密度/捨入穩健。
    golden 單段(flat 0.85 hold)= 一個谷(由釋放回升 ≥prom)→ 1。"""
    pk = max(range(len(vals)), key=lambda i: vals[i])
    seg = vals[:pk + 1]
    if len(seg) < 2:
        return 0
    stages = 0
    last_max = seg[0]
    trough = seg[0]
    in_descent = False
    for v in seg[1:]:
        if v < trough:                      # 續降(更新谷底)
            trough = v
            in_descent = True
        elif in_descent and v >= trough + prom:   # 自谷底回升 ≥prom → 計一台充能
            stages += 1
            in_descent = False
            last_max = v
            trough = v
        elif not in_descent and v > last_max:     # 谷間高點(re-grip 頂)→ 推高基準
            last_max = v
            trough = v
    return stages


def _min_stages(anim):
    """該 anim 各 bone scale 曲線的充能台數之最小值(所有件都至少充這麼多段)。"""
    bones = anim.get("bones", {})
    return min((charge_stages(series(anim, b)) for b in bones), default=0)


def _stages_each(anim):
    """各 bone 的充能台數(用於 distinct/一致性檢查)。"""
    return {b: charge_stages(series(anim, b)) for b in anim.get("bones", {})}


def _scale_overshoot(anim):
    bones = anim.get("bones", {})
    return max((max(series(anim, b)) - 1.0 for b in bones), default=0.0)


def _n_impact(anim):
    """該 anim 各 bone 的 impact 峰數之最大值(charge 應恆 1 = 唯一釋放峰)。"""
    bones = anim.get("bones", {})
    return max((len(impact_peaks(series(anim, b))) for b in bones), default=0)


def _charge_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "charge"]


def _main_beats(anims):
    return {nm: G.beat_category(nm) for nm in anims
            if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    stages = TV.charge_stages_for(GENRE)

    base = G.build_animations(skel, sb)                                          # 無檔位
    amp_only = G.build_animations(skel, sb, tier_gains=gains)                    # (J) 幅度-only
    full = G.build_animations(skel, sb, tier_gains=gains, tier_charge_stages=stages)  # (G-4'''''-charge) 幅度+階梯數

    charge_beats = _charge_beats(base)
    R = {}

    # ---- CH1 present + backward-compat ----
    ch1 = {"missing": [], "not_finite": [], "no_bones": [], "base_changed": [], "amp_only_regressed": []}
    for cb in charge_beats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            an = full.get(vk)
            if an is None:
                ch1["missing"].append(vk); continue
            if not SA.all_finite(an):
                ch1["not_finite"].append(vk)
            if not an.get("bones"):
                ch1["no_bones"].append(vk)
    # base charge 不變(恆 nstage=1 → 1 台),且逐位元同無檔位版
    for cb in charge_beats:
        if _min_stages(full[cb]) != 1 or \
           json.dumps(base[cb], sort_keys=True) != json.dumps(full[cb], sort_keys=True):
            ch1["base_changed"].append(cb)
    # tier_charge_stages=None 時,charge 變體逐位元同 (J) 幅度-only(加性 opt-in)
    none_run = G.build_animations(skel, sb, tier_gains=gains, tier_charge_stages=None)
    for cb in charge_beats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            if json.dumps(none_run.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                ch1["amp_only_regressed"].append(vk)
    R["CH1_present_backward_compat"] = {"charge_beats": charge_beats, **ch1,
                                        "pass": bool(charge_beats) and not any(ch1[k] for k in ch1)}

    # ---- CH2 count monotone (crux) ----
    ch2 = {"beats": {}, "fail": []}
    expected = [stages[t] for t in TIERS]
    for cb in charge_beats:
        counts = [_min_stages(full["{}__{}".format(cb, t)]) for t in TIERS]
        # 各檔位內每 bone 充能台數一致(同一 beat 套到每件,台數相同)
        consistent = all(len(set(_stages_each(full["{}__{}".format(cb, t)]).values())) <= 1 for t in TIERS)
        mono = is_strictly_increasing(counts)
        matches = (counts == expected)
        ch2["beats"][cb] = {"counts": counts, "expected": expected,
                            "monotone": mono, "matches_declared": matches, "per_bone_consistent": consistent}
        if not (mono and matches and consistent):
            ch2["fail"].append(cb)
    R["CH2_count_monotone"] = {"tiers": TIERS, **ch2, "pass": not ch2["fail"] and bool(charge_beats)}

    # ---- CH3 interface + signature preserved + amplitude monotone ----
    ch3 = {"bad_interface": [], "no_charge_sig": [], "no_settle": [], "is_combo": [],
           "multi_impact": [], "amp_not_mono": []}
    for cb in charge_beats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            an = full[vk]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                ch3["bad_interface"].append(vk)
            if not has_charge_signature(an):
                ch3["no_charge_sig"].append(vk)
            if not all(sign_changes(series(an, b)) >= 3 for b in an.get("bones", {})):
                ch3["no_settle"].append(vk)
            if has_combo_signature(an):         # crux:階梯數增多不得誤入 combo 遞增多峰簽章
                ch3["is_combo"].append(vk)
            if _n_impact(an) != 1:              # crux:唯一 impact 峰 = 釋放(充能台不計 impact)
                ch3["multi_impact"].append((vk, _n_impact(an)))
        amp = [_scale_overshoot(full["{}__{}".format(cb, t)]) for t in TIERS]
        if not is_strictly_increasing(amp):
            ch3["amp_not_mono"].append((cb, [round(x, 3) for x in amp]))
    R["CH3_interface_signature"] = {**ch3, "pass": not any(ch3[k] for k in ch3)}

    # ---- CH4 orthogonality ----
    # (a) stages + 平增益 → 台數仍遞增(結構獨立於幅度)
    flat_gain = {t: 1.0 for t in TIERS}
    ca = G.build_animations(skel, sb, tier_gains=flat_gain, tier_charge_stages=stages)
    stages_flatgain = {cb: [_min_stages(ca["{}__{}".format(cb, t)]) for t in TIERS] for cb in charge_beats}
    a_ok = all(is_strictly_increasing(v) for v in stages_flatgain.values()) and bool(charge_beats)
    # (b) gains + 無 stages → 台數恆 1、幅度遞增(crux:幅度加不出第二道充能台)
    cb_gainonly = {cb: [_min_stages(amp_only["{}__{}".format(cb, t)]) for t in TIERS] for cb in charge_beats}
    amp_gainonly = {cb: [_scale_overshoot(amp_only["{}__{}".format(cb, t)]) for t in TIERS] for cb in charge_beats}
    b_ok = all(v == [1, 1, 1, 1] for v in cb_gainonly.values()) and \
        all(is_strictly_increasing(v) for v in amp_gainonly.values()) and bool(charge_beats)
    R["CH4_orthogonality"] = {
        "a_stages_with_flat_gain": stages_flatgain, "a_pass": a_ok,
        "b_gain_only_stages_fixed1": cb_gainonly, "b_gain_only_amp_monotone": {k: [round(x, 3) for x in v] for k, v in amp_gainonly.items()},
        "b_pass": b_ok,
        "pass": a_ok and b_ok}

    # ---- CH5 negative controls ----
    ch5 = {}
    # (a) 平階梯數(全 1)→ 台數單調性 FALSE
    flat_stages = {t: 1 for t in TIERS}
    fs = G.build_animations(skel, sb, tier_gains=gains, tier_charge_stages=flat_stages)
    any_mono_flat = any(is_strictly_increasing([_min_stages(fs["{}__{}".format(cb, t)]) for t in TIERS])
                        for cb in charge_beats)
    ch5["a_flat_stages_guard"] = {"any_count_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) 無宣告 count 的 genre → charge_stages_for None → 不產 charge tier 變體(gains 亦 None)
    rv_stages = TV.charge_stages_for("slot_reveal")
    rv_sb = _storyboard("slot_reveal")
    rv_gains = TV.gains_for("slot_reveal")
    rv_full = G.build_animations(skel, rv_sb, tier_gains=rv_gains, tier_charge_stages=rv_stages)
    rv_charge_variants = [k for k in rv_full if "__" in k and G.beat_category(k) == "charge"]
    ch5["b_no_count_genre"] = {"charge_stages_for_slot_reveal": rv_stages,
                               "charge_variants": rv_charge_variants,
                               "pass": rv_stages is None and not rv_charge_variants}
    # (c) charge count 不外洩:只帶 tier_charge_stages(不帶其餘 count 圖)時,非-charge 的 count-aware
    #     主秀 beat 之 tier 變體逐位元同 (J) 幅度-only(charge 段數圖不路由到別的節拍)。
    charge_only = G.build_animations(skel, sb, tier_gains=gains, tier_charge_stages=stages)
    leak = []
    for beat, cat in _main_beats(base).items():
        if cat == "charge":
            continue
        for t in TIERS:
            vk = "{}__{}".format(beat, t)
            if json.dumps(charge_only.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                leak.append(vk)
    ch5["c_count_isolated_to_charge"] = {"leaked": leak, "pass": not leak}
    R["CH5_neg_control"] = {**ch5, "pass": all(v["pass"] for v in ch5.values())}

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
        for k in ["CH1_present_backward_compat", "CH2_count_monotone", "CH3_interface_signature",
                  "CH4_orthogonality", "CH5_neg_control"]:
            print("{:28s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("CH2 charge stage counts per tier {}:".format(TIERS))
        for cb, d in R["CH2_count_monotone"]["beats"].items():
            print("  {:14s} counts {} (declared {})".format(cb, d["counts"], d["expected"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
