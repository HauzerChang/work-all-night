#!/usr/bin/env python3
"""candidate (J-4) 自我驗收閘 — cascade 跨件**散佈**(span)隨檔位遞增(純 CPU)。

candidate (J) 讓 cascade 波峰**幅度**隨檔位放大;(J-3) 讓 cascade 波**掃過整體的次數** nrip 隨檔位遞增
(結構/拓樸軸)。本閘驗 (J-4):cascade 的**跨件散佈** span **隨檔位嚴格遞增**(Super 0.54 → Legend 0.66,
愈高檔位波掃愈開、各件錯開愈明顯),且此**連續(散佈)**軸與 (J) 的**幅度**軸、(J-3) 的 nrip **結構**軸
**三軸正交可疊**、不破壞任何既有簽章 / 介面契約。

**crux — span 是「連續軸」卻仍須重生成(修正「連續軸=可事後 amplify」的直覺)**:
  - nrip(J-3)= 跨件時序的**結構(拓樸)**軸(波掃道數 = 關鍵幀窗數) → 事後 amplify 加不出一道波 → 重生成。
  - g(J 幅度)= **值空間**連續軸(峰高) → `amplify_bone_tl` 直接放大值欄位即可(事後 amplify)。
  - span(J-4)= 跨件時序的**連續(散佈)**軸:只改各件峰**時刻**(第一件恆 LEAD、最後一件 LEAD+span),
    拓樸不變 → 看似像 g 可事後 amplify;**但 `amplify_bone_tl` 只動值不動 time**,span 活在**時間軸** →
    仍**必須 gen 時重生成**(與 nrip 同路由,原因不同:nrip 改拓樸、span 改 time 欄位)。
  ⇒ **amplify 是值空間專屬**;任何**時間軸**軸(結構 nrip 或連續 span)都要重生成。這是 J-4 相對 J/J-3 的新發現。

**與單件 count(combo/wobble/squash/twist)本質不同**:那些落在**單件曲線**(同一件連幾下);span/nrip 皆落在
**跨件時序**通道(cascade∈_PHASE_AWARE)。真值界定同 (E/H/I/J/J-2/J-3):主秀運動無唯一正解(先驗手感),
閘驗**客觀結構簽章非美感**;用負對照證鑑別力(閘可信)。

閘從**先驗庫**經 `analyze_target`(build_storyboard)→ **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains, tier_cascade_spans[, tier_cascade_ripples])` 端到端量,與 (J)/(J-3) 閘同一 fixture。

  Y1 present + backward-compat : 每檔位皆產 `cascade__{tier}` 且 finite/有 bone;base cascade 不變
                                (散佈恆 CASCADE_SPAN 逐位元不變、Super 逐位元==base);**且** 不帶 `tier_cascade_spans`
                                (=None)時 cascade 變體逐位元同 (J) 幅度-only 輸出 → 證 (J-4) 為**加性 opt-in**、
                                對 (J)/(J-3) 零回歸;**且** Super 宣告 span == beat_templates.CASCADE_SPAN(Super 鎖定=生成器預設)。
  Y2 spread monotone (crux)   : 各檔位 cascade 跨件散佈(單一 sweep 各件峰時刻 max−min)Super<Mega<Omg<Legend
                                **嚴格遞增**,且測得散佈 ≈ 宣告 span(取樣容忍內)。
  Y3 signature + interface     : 每檔位——各件峰時刻依**真實件序嚴格遞增**且散佈 ≥ 門檻(仍是有序跨件波);
                                且每件首尾 setup identity、特效 slot alpha 首尾=1(可插 Loop 間)。
  Y4 orthogonality (3-way)    : (a) spans + **平增益** + 無 ripples → 散佈遞增、峰幅**不**遞增、波掃次數恆 1
                                   (span ⊥ 幅度);
                                (b) spans + **固定 ripples**(全 nrip=2)+ 平增益 → 波掃次數**恆 2**(span 不加波道)
                                   **且**每道 sweep 內散佈仍隨檔位遞增(span 疊在多道波上)(span ⊥ nrip,crux);
                                (c) **僅增益**(無 spans)→ 散佈**恆 CASCADE_SPAN**(不隨檔位變)、峰幅遞增
                                   (span 軸真為 opt-in)。
  Y5 neg-control              : (a) **平散佈**(全 CASCADE_SPAN)→ Y2 單調性 FALSE(證閘在測遞增、非恆真);
                                (b) 無宣告 span 的 genre(slot_reveal)→ `cascade_spans_for` 回 None
                                   → 不產 cascade span 變體(不亂加散佈);
                                (c) **只有 cascade 是 span-aware**:同時帶 spans 時,非-cascade 主秀 beat 的
                                   檔位變體**逐位元同**幅度-only(span 不外洩到別的節拍)。

用法:
  python3 validate_cascade_span.py            # 摘要
  python3 validate_cascade_span.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import beat_templates as BT
from analyze_target import analyze
import tier_variants as TV
from validate_cascade import series, is_strictly_increasing, cascade_spread
from validate_cascade_count import (peak_times, ripple_counts, scale_overshoot,
                                    per_sweep_ordered, _part_order)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
N = 240
SPREAD_TOL = 3.0 / N     # 散佈量測容忍(argmax 取樣量化 ~1/N;取 3/N 餘裕)
SPREAD_FLOOR = 0.6 * BT.CASCADE_SPAN   # 有序跨件波散佈下界(單 sweep;遠高於近同時 combo 的 spread≈0)


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/cascade_span_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def cross_part_spread(anim, order):
    """單一 sweep(nrip=1)各件**第一個** pop 峰時刻的散佈(max−min,依件序)。"""
    bones = [b for b in order if b in anim.get("bones", {})]
    firsts = [peak_times(anim, b)[0] for b in bones if peak_times(anim, b)]
    return cascade_spread(firsts), firsts


def sweep_spreads(anim, order, nrip):
    """每一道 sweep k 的各件第 k 峰時刻散佈(list,len==nrip)。件峰數不足 nrip → 該 sweep 記 -1。"""
    bones = [b for b in order if b in anim.get("bones", {})]
    per = [peak_times(anim, b) for b in bones]
    out = []
    for k in range(nrip):
        pts = [p[k] for p in per if len(p) > k]
        out.append(cascade_spread(pts) if len(pts) >= 2 else -1.0)
    return out


def _cascade_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "cascade"]


def _main_beats(anims):
    return {nm: G.beat_category(nm) for nm in anims
            if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    order = _part_order(sb)
    gains = TV.gains_for(GENRE)
    spans = TV.cascade_spans_for(GENRE)
    rip = TV.cascade_ripples_for(GENRE)

    base = G.build_animations(skel, sb)                                          # 無檔位
    amp_only = G.build_animations(skel, sb, tier_gains=gains)                    # (J) 幅度-only
    full = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_spans=spans)  # (J-4) 幅度+散佈

    cbeats = _cascade_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- Y1 present + backward-compat ----
    y1 = {"missing": [], "not_finite": [], "no_bones": [], "base_changed": [],
          "super_ne_base": [], "amp_only_regressed": [], "super_span_not_pinned": []}
    # Super 宣告 span 必須 == 生成器預設 CASCADE_SPAN(否則 g=1 下 Super≠base)
    if abs(spans["Super"] - BT.CASCADE_SPAN) > 1e-9:
        y1["super_span_not_pinned"].append({"super_span": spans["Super"], "cascade_span": BT.CASCADE_SPAN})
    for cb in cbeats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            an = full.get(vk)
            if an is None:
                y1["missing"].append(vk); continue
            if not SA.all_finite(an):
                y1["not_finite"].append(vk)
            if not an.get("bones"):
                y1["no_bones"].append(vk)
        # base 不變、Super 逐位元==base(span=CASCADE_SPAN、g=1.0)
        if json.dumps(base[cb], sort_keys=True) != json.dumps(full[cb], sort_keys=True):
            y1["base_changed"].append(cb)
        if json.dumps(full[cb], sort_keys=True) != json.dumps(full["{}__Super".format(cb)], sort_keys=True):
            y1["super_ne_base"].append(cb)
    # tier_cascade_spans=None → cascade 變體逐位元同 (J) 幅度-only
    none_run = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_spans=None)
    for cb in cbeats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            if json.dumps(none_run.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                y1["amp_only_regressed"].append(vk)
    R["Y1_present_backward_compat"] = {"cascade_beats": cbeats, **y1,
                                       "pass": bool(cbeats) and not any(y1[k] for k in y1)}

    # ---- Y2 spread monotone (crux) ----
    y2 = {"beats": {}, "fail": []}
    declared = [spans[t] for t in TIERS]
    for cb in cbeats:
        spreads, matches = [], True
        for t in TIERS:
            sp, _ = cross_part_spread(full["{}__{}".format(cb, t)], order)
            spreads.append(round(sp, 4))
            if abs(sp - spans[t]) > SPREAD_TOL:
                matches = False
        mono = is_strictly_increasing(spreads)
        y2["beats"][cb] = {"spreads": spreads, "declared": declared,
                           "monotone": mono, "matches_declared": matches}
        if not (mono and matches):
            y2["fail"].append(cb)
    R["Y2_spread_monotone"] = {"tiers": TIERS, **y2, "pass": bool(cbeats) and not y2["fail"]}

    # ---- Y3 signature + interface ----
    y3 = {"bad_order": [], "bad_interface": [], "detail": {}}
    for cb in cbeats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            an = full[vk]
            sp, firsts = cross_part_spread(an, order)
            inc = is_strictly_increasing(firsts)
            good = inc and sp >= SPREAD_FLOOR
            y3["detail"][vk] = {"times": [round(x, 3) for x in firsts],
                                "increasing": inc, "spread": round(sp, 3),
                                "floor": round(SPREAD_FLOOR, 3), "pass": good}
            if not good:
                y3["bad_order"].append(vk)
            dur = SA.duration(an)
            b0 = SA.sample(an, 0.0)["bones"]; bE = SA.sample(an, dur)["bones"]
            s0 = SA.sample(an, 0.0)["slots"]; sE = SA.sample(an, dur)["slots"]
            iface = (all(_is_ident(v) for v in b0.values()) and all(_is_ident(v) for v in bE.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in s0.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in sE.values()))
            if not iface:
                y3["bad_interface"].append(vk)
    R["Y3_signature_interface"] = {"bad_order": y3["bad_order"], "bad_interface": y3["bad_interface"],
                                   "detail": y3["detail"],
                                   "pass": not y3["bad_order"] and not y3["bad_interface"]}

    # ---- Y4 orthogonality (3-way) ----
    flat_gain = {t: 1.0 for t in TIERS}
    # (a) spans + 平增益 + 無 ripples → 散佈遞增、峰幅不遞增、波掃次數恆 1
    a_run = G.build_animations(skel, sb, tier_gains=flat_gain, tier_cascade_spans=spans)
    a_spreads = {cb: [round(cross_part_spread(a_run["{}__{}".format(cb, t)], order)[0], 4) for t in TIERS] for cb in cbeats}
    a_amp = {cb: [round(scale_overshoot(a_run["{}__{}".format(cb, t)]), 3) for t in TIERS] for cb in cbeats}
    a_rip = {cb: [ripple_counts(a_run["{}__{}".format(cb, t)])[0][1] for t in TIERS] for cb in cbeats}
    a_ok = bool(cbeats) and all(is_strictly_increasing(v) for v in a_spreads.values()) \
        and not any(is_strictly_increasing(v) for v in a_amp.values()) \
        and all(v == [1, 1, 1, 1] for v in a_rip.values())
    # (b) spans + 固定 ripples(全 2)+ 平增益 → 波掃次數恆 2、每道 sweep 散佈仍隨檔位遞增
    fixed_rip = {t: 2 for t in TIERS}
    b_run = G.build_animations(skel, sb, tier_gains=flat_gain,
                               tier_cascade_spans=spans, tier_cascade_ripples=fixed_rip)
    b_rip = {cb: [ripple_counts(b_run["{}__{}".format(cb, t)])[0][1] for t in TIERS] for cb in cbeats}
    # 每道 sweep k 的散佈,逐檔位取出 → 檢查每道 sweep 皆隨檔位嚴格遞增
    b_sweep = {cb: {t: [round(x, 4) for x in sweep_spreads(b_run["{}__{}".format(cb, t)], order, 2)]
                    for t in TIERS} for cb in cbeats}
    def _all_sweeps_increase(perbeat):
        for k in range(2):
            col = [perbeat[t][k] for t in TIERS]
            if any(c < 0 for c in col) or not is_strictly_increasing(col):
                return False
        return True
    b_ok = bool(cbeats) and all(v == [2, 2, 2, 2] for v in b_rip.values()) \
        and all(_all_sweeps_increase(b_sweep[cb]) for cb in cbeats)
    # (c) 僅增益(無 spans)→ 散佈恆 CASCADE_SPAN、峰幅遞增
    c_spreads = {cb: [round(cross_part_spread(amp_only["{}__{}".format(cb, t)], order)[0], 4) for t in TIERS] for cb in cbeats}
    c_amp = {cb: [scale_overshoot(amp_only["{}__{}".format(cb, t)]) for t in TIERS] for cb in cbeats}
    c_ok = bool(cbeats) \
        and all(all(abs(s - BT.CASCADE_SPAN) <= SPREAD_TOL for s in v) for v in c_spreads.values()) \
        and all(not is_strictly_increasing(v) for v in c_spreads.values()) \
        and all(is_strictly_increasing(v) for v in c_amp.values())
    R["Y4_orthogonality"] = {
        "a_spans_flatgain_noripple": {"spreads": a_spreads, "amp": a_amp, "ripples": a_rip, "pass": a_ok},
        "b_spans_fixedripple2": {"ripples": b_rip, "sweep_spreads": b_sweep, "pass": b_ok},
        "c_gain_only": {"spreads": c_spreads, "amp_increasing": {cb: is_strictly_increasing(v) for cb, v in c_amp.items()}, "pass": c_ok},
        "pass": a_ok and b_ok and c_ok}

    # ---- Y5 negative controls ----
    y5 = {}
    # (a) 平散佈(全 CASCADE_SPAN)→ 單調性 FALSE
    flat_span = {t: BT.CASCADE_SPAN for t in TIERS}
    fs = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_spans=flat_span)
    any_mono_flat = any(is_strictly_increasing([round(cross_part_spread(fs["{}__{}".format(cb, t)], order)[0], 4) for t in TIERS])
                        for cb in cbeats)
    y5["a_flat_spans_guard"] = {"any_spread_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) 無宣告 span 的 genre → cascade_spans_for None → 不產 span 變體
    rv_span = TV.cascade_spans_for("slot_reveal")
    rv_sb = _storyboard("slot_reveal")
    rv_gains = TV.gains_for("slot_reveal")
    rv_full = G.build_animations(skel, rv_sb, tier_gains=rv_gains, tier_cascade_spans=rv_span)
    rv_casc_variants = [k for k in rv_full if "__" in k and G.beat_category(k) == "cascade"]
    y5["b_no_span_genre"] = {"cascade_spans_for_slot_reveal": rv_span,
                             "cascade_variants": rv_casc_variants,
                             "pass": rv_span is None and not rv_casc_variants}
    # (c) span 只作用於 cascade:非-cascade 主秀 beat 的檔位變體逐位元同幅度-only(不外洩)。
    leak = []
    for beat, cat in main_beats.items():
        if cat == "cascade":
            continue
        for t in TIERS:
            vk = "{}__{}".format(beat, t)
            if json.dumps(full.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                leak.append(vk)
    y5["c_span_isolated_to_cascade"] = {"leaked": leak, "pass": not leak}
    R["Y5_neg_control"] = {**y5, "pass": all(v["pass"] for v in y5.values())}

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
        for k in ["Y1_present_backward_compat", "Y2_spread_monotone", "Y3_signature_interface",
                  "Y4_orthogonality", "Y5_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("Y2 cascade cross-part spread per tier {}:".format(TIERS))
        for cb, d in R["Y2_spread_monotone"]["beats"].items():
            print("  {:10s} spreads {} (declared {})".format(cb, d["spreads"], d["declared"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
