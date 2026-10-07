#!/usr/bin/env python3
"""candidate (L-7) 自我驗收閘 — crossfade 接點重疊 xf 隨**檔位**差異化(序列組合層的檔位軸;純 CPU,確定性)。

**補的缺口(L-6 的「下一步」/ STATE crossfade×tier)**:candidate (L-6) 的 `crossfade_sequence` 以固定 xf=0.15
把序列的接點 C1 kink 消掉。本次把 **xf 本身**接上檔位軸:`tier_crossfade_sequence(anims, order, tier)` 依
`TIER_CROSSFADE_XF[genre][tier]` 選接點重疊秒數 —— 高檔位接點重疊**更多**(beat 更連綿、總序列更緊湊)。

**本 run 的新位置(為何不是「又一條檔位軸」)**:既有全部檔位軸(幅度 g、combo/wobble/squash/twist/charge
段數、cascade span/dir)都在 **per-beat 值生成** 或 **跨件相位** 層;**xf 是第一條落在「序列組合層」的檔位軸**
—— 它不改任一 beat 的值或內部時間,只改**相鄰 beat 疊多少 → 總時長**。這逼出兩個客觀 crux:

  **crux T3 — 檔位(xf)軸 ⟂ C1(斜坡)性質**:smoothstep 的 `w'(0)=w'(1)=0` 使接點閉式 kink 恆 0 **與 xf 無關**
    → 無論哪個檔位把接點壓得多緊,接點 C1 kink 都 =0(壓縮接點**不會**重新引入頓挫)。線性斜坡在**每個**檔位
    仍每接點頓挫 → 證 C1 來自斜坡、與 xf 檔位正交。
  **crux T4 — 檔位(xf)軸不可由值增益達成(需重組合,呼應 J-4)**:`amplify_bone_tl`(TIER_GAIN 的值增益 g)
    只放大 bone 的**值**、不碰任一幀的 `time` → beat 時長不變 → crossfade 總時長 / 接點重疊**不變**。因此
    值幅度檔位(TIER_GAIN)**動不到** xf / 總時長這條軸 —— 它必須靠不同 xf **重新組合**(與 J-4「cascade span
    是時間位置的幅度,需重生成,非 post-hoc 值增益」同一階發現,但落在**序列組合層**而非 beat 內)。

**選題理由**:延續 (L)/(L-2..L-6) 刻意選**整合 / 組合閘**,不加 per-beat 參數軸。從**先驗庫 → 真實 build_spine
robot 骨架 → build_animations** 端到端,與 L-5 / L-6 同一 fixture(正向序列 In→hit→combo→charge→cascade→Loop→Out)。

真值界定:**xf 隨檔位遞增 vs 遞減、各檔位 xf 值**屬美術手感(A 類;高檔位該更連綿或更分明皆可辯);但
「xf 嚴格遞增」「總時長嚴格遞減」「每檔位接點 C1 kink=0」「值增益動不到總時長」「base==L-6 golden 逐位元」
皆**客觀可量測**。flat-xf 負對照證單調性是真 xf 驅動、非 artifact。

AC(客觀、可量測):
  T1 present + well-formed + base bitwise + guard : 四檔位 `tier_crossfade_sequence`(smoothstep)皆產**合法 Spine
                                       timeline**(每通道時間嚴格遞增 / finite);每檔位 xf < 最短 beat 時長的一半
                                       (守衛不觸發);**base Super xf==0.15 且逐位元 == `crossfade_sequence(...,0.15,
                                       "smoothstep")`(L-6 golden)**。
  T2 crux — xf 與總時長嚴格單調(佈局檔位軸) : xf 嚴格遞增 Super<Mega<Omg<Legend;每檔位總時長 == Σdur−(m−1)·xf
                                       (閉式)且**嚴格遞減**(重疊越多越短);每接點重疊長 == 該檔位 xf。
  T3 crux — 檔位(xf)軸 ⟂ C1(斜坡)性質   : **每個**檔位 smoothstep 接點閉式 kink ≤ KINK_ZERO_TOL(≈0)且
                                       `is_c1_crossfade_sequence`(smoothstep)==True **對照** 純接續
                                       `is_c1_continuous_sequence`==False;**負對照** 線性斜坡在**每個**檔位仍
                                       每接點 kink ≥ SEAM_KINK_MIN、`is_c1_crossfade_sequence`(linear)==False
                                       → 證壓縮接點(xf 檔位)不重新引入 kink,C1 來自斜坡、與 xf 正交。
  T4 crux — 值增益動不到佈局軸(需重組合)  : `amplify_anim`(TIER_GAIN Legend g=2.1)套到每 beat → 每 beat 時長**不變**
                                       (SA.duration 放大前後相等);放大後以 Super xf 重 crossfade → 總時長 == Super
                                       總時長(值增益不改時間)**且 != Legend 總時長**(Legend 需更大 xf 重組合)→ 證
                                       值幅度檔位 ⟂ 佈局檔位,xf/總時長軸須重組合(呼應 J-4);且放大後 smoothstep
                                       接點 kink 仍 0(值增益亦 ⟂ C1)。
  T5 flat-xf 負對照 + body 忠實 + 守衛       : (a) **flat-xf 負對照**:四檔位全用同一 xf(=Super)→ 總時長全相等、xf
                                       非嚴格遞增 → 證 T2 的單調性是真 xf 驅動、非量測 artifact;(b) **body 忠實**:
                                       每檔位 body 區 emitted vs 孤立 clip 平移 ≤ FAITH_TOL;(c) **輸入守衛**:未宣告
                                       genre → ValueError、未知檔位 → ValueError。

用法:
  python3 validate_crossfade_tier.py            # 摘要
  python3 validate_crossfade_tier.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
NSAMP = 16
KINK_ZERO_TOL = 1e-6    # smoothstep 每檔位閉式接點 kink 上限(實測精確 0)
SEAM_KINK_MIN = 10.0    # 純接續 / 線性斜坡每接點 C1 kink 下限(L-5/L-6 實測最小 15)
VEL_TOL = 1.0           # is_c1_crossfade_sequence 接點 kink 容忍(與 L-5/L-6 同)
FAITH_TOL = 0.05        # body 區 emitted vs 孤立 clip 忠實上限(L-6 實測 0.0019)
GOLDEN_XF = 0.15        # L-6 golden crossfade xf(== base Super)
LEGEND_GAIN = 2.10      # TIER_GAIN slot_bigwin Legend 值幅度增益(T4 用)

FORWARD = ["In", "hit", "combo", "charge", "cascade", "Loop", "Out"]


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/seq_xftier_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _total_closed(anims, xf):
    return sum(SA.duration(anims[n]) for n in FORWARD) - (len(FORWARD) - 1) * xf


# ---------------- AC ----------------
def ac_T1(anims):
    tbl = TV.crossfade_xf_for(GENRE)
    min_d = min(SA.duration(anims[n]) for n in FORWARD)
    per = {}
    wf_ok = True
    guard_ok = True
    for t in TIERS:
        comp, segs = G.tier_crossfade_sequence(anims, FORWARD, t, GENRE, NSAMP, "smoothstep")
        wf = SA.all_finite(comp)
        xf = tbl[t]
        g = xf < min_d / 2.0 + 1e-12
        per[t] = {"xf": xf, "well_formed": bool(wf), "xf_below_half_mindur": bool(g),
                  "total": round(SA.duration(comp), 6)}
        wf_ok = wf_ok and wf
        guard_ok = guard_ok and g
    # base Super == L-6 golden 逐位元
    base = G.tier_crossfade_sequence(anims, FORWARD, "Super", GENRE, NSAMP, "smoothstep")
    gold = G.crossfade_sequence(anims, FORWARD, GOLDEN_XF, NSAMP, "smoothstep")
    bc = (json.dumps(base[0], sort_keys=True) == json.dumps(gold[0], sort_keys=True)) and (base[1] == gold[1])
    base_xf_ok = abs(tbl["Super"] - GOLDEN_XF) <= 1e-12
    ok = wf_ok and guard_ok and bc and base_xf_ok
    return {"pass": bool(ok), "all_well_formed": bool(wf_ok), "all_xf_below_half_mindur": bool(guard_ok),
            "min_beat_dur": round(min_d, 6), "base_super_xf": tbl["Super"], "base_xf_equals_golden": bool(base_xf_ok),
            "base_super_bit_identical_to_L6_golden": bool(bc), "per_tier": per}


def ac_T2(anims):
    tbl = TV.crossfade_xf_for(GENRE)
    xfs = [tbl[t] for t in TIERS]
    xf_mono = all(xfs[i] < xfs[i + 1] for i in range(len(xfs) - 1))
    totals = []
    closed_ok = True
    overlap_ok = True
    per = {}
    for t in TIERS:
        comp, segs = G.tier_crossfade_sequence(anims, FORWARD, t, GENRE, NSAMP, "smoothstep")
        xf = tbl[t]
        tot = SA.duration(comp)
        totals.append(tot)
        ct = _total_closed(anims, xf)
        c_ok = abs(tot - ct) <= 1e-6
        # 每接點重疊長 == xf(相鄰段區間相交 xf)
        ov = all(abs((segs[i]["start"] + segs[i]["dur"]) - (segs[i + 1]["start"] + xf)) <= 1e-6
                 for i in range(len(FORWARD) - 1))
        per[t] = {"xf": xf, "total": round(tot, 6), "closed_total": round(ct, 6),
                  "closed_ok": bool(c_ok), "overlap_eq_xf": bool(ov)}
        closed_ok = closed_ok and c_ok
        overlap_ok = overlap_ok and ov
    total_mono = all(totals[i] > totals[i + 1] for i in range(len(totals) - 1))  # 嚴格遞減
    ok = xf_mono and total_mono and closed_ok and overlap_ok
    return {"pass": bool(ok), "xf_strictly_increasing": bool(xf_mono), "xfs": xfs,
            "total_strictly_decreasing": bool(total_mono), "totals": [round(x, 6) for x in totals],
            "closed_form_total_ok": bool(closed_ok), "overlap_eq_xf_all": bool(overlap_ok), "per_tier": per}


def ac_T3(anims):
    tbl = TV.crossfade_xf_for(GENRE)
    per = {}
    smoo_all_zero = True
    smoo_all_c1 = True
    lin_all_kink = True
    lin_none_c1 = True
    for t in TIERS:
        xf = tbl[t]
        sk = G.crossfade_junction_kinks(anims, FORWARD, xf, "smoothstep")
        smax = max(j["max"] for j in sk)
        sc1 = G.is_c1_crossfade_sequence(anims, FORWARD, xf, "smoothstep", VEL_TOL)
        lk = G.crossfade_junction_kinks(anims, FORWARD, xf, "linear")
        lmin = min(j["max"] for j in lk)
        lc1 = G.is_c1_crossfade_sequence(anims, FORWARD, xf, "linear", VEL_TOL)
        per[t] = {"xf": xf, "smoothstep_max_kink": round(smax, 9), "smoothstep_is_c1": bool(sc1),
                  "linear_min_kink": round(lmin, 3), "linear_is_c1": bool(lc1)}
        smoo_all_zero = smoo_all_zero and (smax <= KINK_ZERO_TOL)
        smoo_all_c1 = smoo_all_c1 and sc1
        lin_all_kink = lin_all_kink and (lmin >= SEAM_KINK_MIN)
        lin_none_c1 = lin_none_c1 and (not lc1)
    concat_c1 = G.is_c1_continuous_sequence(anims, FORWARD, 1e-6, VEL_TOL, 1e-3)
    ok = smoo_all_zero and smoo_all_c1 and lin_all_kink and lin_none_c1 and (not concat_c1)
    return {"pass": bool(ok), "smoothstep_all_tiers_kink_zero": bool(smoo_all_zero),
            "smoothstep_all_tiers_is_c1": bool(smoo_all_c1), "kink_zero_tol": KINK_ZERO_TOL,
            "linear_all_tiers_kink": bool(lin_all_kink), "linear_no_tier_is_c1": bool(lin_none_c1),
            "seam_kink_min": SEAM_KINK_MIN, "concat_is_c1": bool(concat_c1), "per_tier": per}


def ac_T4(anims):
    # 值增益(TIER_GAIN Legend g)套到每 beat → 時長不變;總時長 / 接點 kink 不受值增益影響
    amp = {}
    dur_unchanged = True
    for n in FORWARD:
        a2 = TV.amplify_anim(anims[n], LEGEND_GAIN)
        amp[n] = a2
        if abs(SA.duration(a2) - SA.duration(anims[n])) > 1e-9:
            dur_unchanged = False
    # 放大後以 Super xf 重 crossfade → 總時長 == 原 Super 總時長
    base_total = SA.duration(G.tier_crossfade_sequence(anims, FORWARD, "Super", GENRE, NSAMP, "smoothstep")[0])
    amp_super_total = SA.duration(G.crossfade_sequence(amp, FORWARD, TV.crossfade_xf_for(GENRE)["Super"], NSAMP, "smoothstep")[0])
    legend_total = SA.duration(G.tier_crossfade_sequence(anims, FORWARD, "Legend", GENRE, NSAMP, "smoothstep")[0])
    gain_keeps_total = abs(amp_super_total - base_total) <= 1e-6       # 值增益不改總時長
    gain_neq_layout = abs(amp_super_total - legend_total) > 1e-6       # 達不到 Legend 佈局(需重組合)
    # 值增益 ⟂ C1:放大後 smoothstep 接點 kink 仍 0
    amp_kink = max(j["max"] for j in G.crossfade_junction_kinks(amp, FORWARD, GOLDEN_XF, "smoothstep"))
    gain_keeps_c1 = amp_kink <= KINK_ZERO_TOL
    ok = dur_unchanged and gain_keeps_total and gain_neq_layout and gain_keeps_c1
    return {"pass": bool(ok), "gain_keeps_beat_durations": bool(dur_unchanged), "legend_gain": LEGEND_GAIN,
            "base_super_total": round(base_total, 6), "amplified_super_total": round(amp_super_total, 6),
            "legend_total": round(legend_total, 6), "gain_keeps_total": bool(gain_keeps_total),
            "gain_cannot_reach_legend_layout": bool(gain_neq_layout),
            "amplified_smoothstep_max_kink": round(amp_kink, 9), "gain_keeps_c1": bool(gain_keeps_c1),
            "note": "值幅度檔位(TIER_GAIN)⟂ 佈局檔位(TIER_CROSSFADE_XF);xf/總時長須重組合(呼應 J-4)"}


def ac_T5(anims):
    tbl = TV.crossfade_xf_for(GENRE)
    # (a) flat-xf 負對照:四檔位全用 Super xf → 總時長全相等、xf 非嚴格遞增
    flat_xf = tbl["Super"]
    flat_totals = [SA.duration(G.crossfade_sequence(anims, FORWARD, flat_xf, NSAMP, "smoothstep")[0]) for _ in TIERS]
    flat_all_equal = all(abs(flat_totals[i] - flat_totals[0]) <= 1e-9 for i in range(len(flat_totals)))
    flat_not_mono = not all(flat_totals[i] > flat_totals[i + 1] for i in range(len(flat_totals) - 1))
    flat_ok = flat_all_equal and flat_not_mono
    # (b) body 忠實(每檔位)
    faith = {}
    faith_ok = True
    last = len(FORWARD) - 1
    for t in TIERS:
        xf = tbl[t]
        comp, _ = G.tier_crossfade_sequence(anims, FORWARD, t, GENRE, NSAMP, "smoothstep")
        offsets, durs, _ = G._crossfade_layout(anims, FORWARD, xf)
        m = 0.0
        for i, nm in enumerate(FORWARD):
            lo = offsets[i] + (xf if i > 0 else 0.0)
            hi = offsets[i] + durs[i] - (xf if i < last else 0.0)
            for frac in (0.2, 0.4, 0.6, 0.8):
                tt = lo + (hi - lo) * frac
                m = max(m, G._state_max_diff(SA.sample(comp, tt), SA.sample(anims[nm], tt - offsets[i])))
        faith[t] = round(m, 6)
        faith_ok = faith_ok and (m <= FAITH_TOL)
    # (c) 輸入守衛
    guards = {}
    try:
        G.tier_crossfade_sequence(anims, FORWARD, "Super", "no_such_genre")
        guards["unknown_genre"] = False
    except ValueError:
        guards["unknown_genre"] = True
    try:
        G.tier_crossfade_sequence(anims, FORWARD, "NoSuchTier", GENRE)
        guards["unknown_tier"] = False
    except ValueError:
        guards["unknown_tier"] = True
    guard_ok = all(guards.values())
    ok = flat_ok and faith_ok and guard_ok
    return {"pass": bool(ok),
            "flat_xf_negative_control": {"pass": bool(flat_ok), "flat_xf": flat_xf,
                                         "flat_totals": [round(x, 6) for x in flat_totals],
                                         "all_equal": bool(flat_all_equal), "not_strictly_decreasing": bool(flat_not_mono),
                                         "note": "全檔位同 xf → 總時長全等 → T2 單調性是真 xf 驅動、非 artifact"},
            "body_faithful": {"pass": bool(faith_ok), "maxerr_by_tier": faith, "faith_tol": FAITH_TOL},
            "input_guards": {"pass": bool(guard_ok), **guards}}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    missing = [nm for nm in FORWARD if nm not in anims]
    if missing:
        return {"overall_pass": False, "error": "missing beats in fixture: {}".format(missing),
                "available": sorted(anims.keys())}
    results = {"T1_present_wellformed_base_bitwise": ac_T1(anims),
               "T2_crux_xf_total_strict_monotone": ac_T2(anims),
               "T3_crux_tier_orthogonal_to_C1": ac_T3(anims),
               "T4_crux_value_gain_cannot_reach_layout": ac_T4(anims),
               "T5_flat_xf_negctrl_faithful_guards": ac_T5(anims)}
    results["overall_pass"] = all(v["pass"] for v in results.values())
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    res = run()
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print("candidate (L-7) crossfade 接點重疊 xf 隨檔位差異化閘 — tier_crossfade_sequence (序列組合層檔位軸)")
        for k in ["T1_present_wellformed_base_bitwise", "T2_crux_xf_total_strict_monotone",
                  "T3_crux_tier_orthogonal_to_C1", "T4_crux_value_gain_cannot_reach_layout",
                  "T5_flat_xf_negctrl_faithful_guards"]:
            v = res.get(k, {})
            print("  {:42s} {}".format(k, "PASS" if v.get("pass") else "FAIL"))
        if "error" in res:
            print("  ERROR:", res["error"])
        if "T2_crux_xf_total_strict_monotone" in res:
            p = res["T2_crux_xf_total_strict_monotone"]
            print("    xf={} (inc={}) | totals={} (dec={})".format(
                p["xfs"], p["xf_strictly_increasing"], p["totals"], p["total_strictly_decreasing"]))
        if "T3_crux_tier_orthogonal_to_C1" in res:
            p = res["T3_crux_tier_orthogonal_to_C1"]
            print("    smoothstep all-tiers kink=0 {} & is_c1 {} | linear all-tiers kink {} none-c1 {} | concat is_c1 {}".format(
                p["smoothstep_all_tiers_kink_zero"], p["smoothstep_all_tiers_is_c1"],
                p["linear_all_tiers_kink"], p["linear_no_tier_is_c1"], p["concat_is_c1"]))
        if "T4_crux_value_gain_cannot_reach_layout" in res:
            p = res["T4_crux_value_gain_cannot_reach_layout"]
            print("    gain keeps durs={} | amp_super_total={} == base {} != legend {} | gain keeps c1={}".format(
                p["gain_keeps_beat_durations"], p["amplified_super_total"], p["base_super_total"],
                p["legend_total"], p["gain_keeps_c1"]))
        print("OVERALL:", "PASS" if res.get("overall_pass") else "FAIL")
    return 0 if res.get("overall_pass") else 1


if __name__ == "__main__":
    sys.exit(main())
