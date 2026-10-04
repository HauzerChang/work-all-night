#!/usr/bin/env python3
"""candidate (L) 自我驗收閘 — 大獎**序列組合**(cross-beat composition,純 CPU,確定性)。

**補的缺口(能力早在、AC 從缺 —— 同 G-2 的整合閘精神)**:`build_animations` 產出的是**各自獨立**的
beat clip(In/Loop/Out + 主秀 beat + `{beat}__{tier}`),每支首尾皆 setup identity,**設計上**可在 runtime
依序播放成無縫大獎序列(In → 主秀節拍… → Loop → Out)。但**從未有閘**驗過「把這些 clip 真的串接成單一
timeline 時,接點真的無縫、各 beat 的結構簽章在序列脈絡中仍成立、且串接不扭曲任何值」。本次新增
`gen_animations.compose_sequence`(純時間平移 + 接點去重,additive)把串接**顯式做出來**,並以此閘把關。

**選題理由(不選又一條參數軸)**:近期里程碑連續多是「單一 robot 資產加一軸」(tier/count/cascade-dir、
charge count…)。本 run 刻意選**整合/組合閘**——價值在於 (1) 證既有一整櫃主秀 beat 真能**組裝成可播放的
大獎序列**(直指 north star「產出大獎動畫」);(2) 抓回歸(接點契約、序列可組性);非再多一個手感 PROPOSAL。

真值界定:beat **排序**是 PROPOSAL(手感 A 類);但「接點 C0 無縫殘差」「回切逐幀還原」「簽章在序列中
仍成立」皆為**客觀可量測**不變量。用負對照(把 collapse-起手的 burst / collapse-收尾的 Out 放序列中段)
證接點閘有鑑別力(閘可信)。從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations` 端到端,
與 J/charge 等同一 fixture。

AC(客觀、可量測):
  L1 well-formed+present : 正向序列 compose 後為合法 Spine timeline(每通道時間嚴格遞增、值 finite);
                          總時長 == Σ 各段時長(接點零長去重不改);segments 恰好覆蓋宣告序列;
                          序列內任一 beat 用到的 bone 皆現身於 composed。
  L2 crux — 接點無縫    : 正向序列(In→hit→combo→charge→cascade→Loop→Out)每個**內部接點**的跨通道
                          狀態殘差(前一 beat 尾幀 vs 後一 beat 首幀)< SEAM_TOL(皆 identity==identity)。
  L3 faithful concat    : 回切每一段(composed 在 [start,start+dur] 取樣)**逐幀還原**該孤立 beat clip
                          (純時間平移、無值扭曲)→ 最大殘差 < FAITH_TOL(證 offset/合併實作正確)。
  L4 in-context 簽章    : 從 **composed** 回切主秀段量測,其結構簽章仍成立且 == 孤立 clip 量值:
                          combo 段遞增 impact 峰 ≥3、cascade 段跨件峰時刻散佈 ≥ SPREAD_THR、charge 段峰前長蓄力。
  L5 neg-control        : (a) **crux**:burst(collapse 起手)插序列中段 → 其前接點殘差 >> SEAM_TOL
                          (identity→collapsed)→ 接點閘正確判**非無縫**(證 L2 有鑑別力);
                          (b) Out(collapse 收尾)插序列中段 → 其後接點殘差 >> SEAM_TOL → 同上;
                          (c) **composability 發現**:把主秀 beat(皆 identity 介面)彼此對調順序 →
                          所有內部接點仍 < SEAM_TOL **且**各段簽章仍成立 → 證 identity-介面 beat **可自由排序**
                          (In 必首、Out 必尾、burst 僅可起手為位置約束,由 (a)(b) 界定)。

用法:
  python3 validate_sequence_compose.py            # 摘要
  python3 validate_sequence_compose.py --json     # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
from validate_more_beats import (impact_peaks, pre_peak_hold_frac, is_escalating,
                                 HOLD_LEVEL, HOLD_FRAC_THR, N)
from validate_cascade import SPREAD_THR

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}

SEAM_TOL = 1e-3     # 接點 C0 殘差上限(identity==identity 實測 ~0;幀值 round 到 4 位)
FAITH_TOL = 1e-4    # 回切還原殘差上限(純時間平移,實測 ~1e-6 round)
NEG_MULT = 10.0     # 負對照接點殘差須 > NEG_MULT × SEAM_TOL(實測 ~0.9,>900×)

# 正向大獎序列(PROPOSAL 手感排序;客觀不變量 = 接點無縫 / 回切還原 / 簽章保持):
#   In(collapsed→id) → hit → combo → charge → cascade(皆 id→id)→ Loop(id→id)→ Out(id→collapsed)
# 內部接點全為 identity==identity → C0 無縫;序列首為 collapsed 起手、尾為 collapsed 收尾(合理進出場)。
POS_ORDER = ["In", "hit", "combo", "charge", "cascade", "Loop", "Out"]


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/seq_compose_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


# ---------------- 量測器 ----------------
def _state_diff(s1, s2):
    """兩個 sample() 狀態的跨 bone/slot 最大絕對差(缺席通道視為 setup identity)。"""
    m = 0.0
    for b in set(s1["bones"]) | set(s2["bones"]):
        d1 = s1["bones"].get(b, IDENT)
        d2 = s2["bones"].get(b, IDENT)
        for k in IDENT:
            m = max(m, abs(d1.get(k, IDENT[k]) - d2.get(k, IDENT[k])))
    for s in set(s1["slots"]) | set(s2["slots"]):
        a1 = s1["slots"].get(s, {"alpha": 1.0})["alpha"]
        a2 = s2["slots"].get(s, {"alpha": 1.0})["alpha"]
        m = max(m, abs(a1 - a2))
    return m


def _junction_seams(anims, order):
    """各內部接點殘差(前一 beat 尾幀狀態 vs 後一 beat 首幀狀態)。回傳 [{pair, seam}, ...]。"""
    seams = []
    for i in range(len(order) - 1):
        a, b = anims[order[i]], anims[order[i + 1]]
        end = SA.sample(a, SA.duration(a))
        start = SA.sample(b, 0.0)
        seams.append({"pair": "{}->{}".format(order[i], order[i + 1]),
                      "seam": round(_state_diff(end, start), 6)})
    return seams


def _seg_series(composed, bone, start, dur, key="scaleX", n=N):
    """composed 在段 [start,start+dur] 上對某 bone 某通道取樣序列(in-context 量測)。"""
    dflt = 1.0 if "scale" in key else 0.0
    return [SA.sample(composed, start + dur * i / n)["bones"].get(bone, {}).get(key, dflt)
            for i in range(n + 1)]


def _clip_series(clip, bone, key="scaleX", n=N):
    dur = SA.duration(clip)
    dflt = 1.0 if "scale" in key else 0.0
    return [SA.sample(clip, dur * i / n)["bones"].get(bone, {}).get(key, dflt) for i in range(n + 1)]


def _any_bone(clip):
    bs = list(clip.get("bones", {}).keys())
    return bs[0] if bs else None


def _peak_time_window(composed, bone, start, dur, n=N):
    v = _seg_series(composed, bone, start, dur, n=n)
    return max(range(len(v)), key=lambda i: v[i]) / n


def _well_formed(composed):
    for group in ("bones", "slots"):
        for chans in composed.get(group, {}).values():
            for frames in chans.values():
                last = None
                for f in frames:
                    t = f.get("time")
                    if t is None or not math.isfinite(t):
                        return False
                    if last is not None and not (t > last):
                        return False
                    last = t
                    for k, val in f.items():
                        if k == "time":
                            continue
                        if isinstance(val, (int, float)) and not math.isfinite(val):
                            return False
    return True


# ---------------- AC ----------------
def ac_L1(anims):
    composed, segs = G.compose_sequence(anims, POS_ORDER)
    wf = _well_formed(composed)
    sum_dur = round(sum(s["dur"] for s in segs), 6)
    tot = round(SA.duration(composed), 6)
    covers = [s["beat"] for s in segs] == POS_ORDER
    used_bones = set()
    for nm in POS_ORDER:
        used_bones |= set(anims[nm].get("bones", {}).keys())
    present = used_bones <= set(composed.get("bones", {}).keys())
    ok = wf and covers and present and abs(sum_dur - tot) <= 1e-4 and tot > 0
    return {"pass": bool(ok), "well_formed": wf, "covers_order": covers,
            "all_bones_present": present, "sum_dur": sum_dur, "total_dur": tot,
            "segments": segs}


def ac_L2(anims):
    seams = _junction_seams(anims, POS_ORDER)
    worst = max((s["seam"] for s in seams), default=0.0)
    ok = worst < SEAM_TOL
    return {"pass": bool(ok), "worst_seam": worst, "tol": SEAM_TOL, "seams": seams}


def ac_L3(anims):
    composed, segs = G.compose_sequence(anims, POS_ORDER)
    worst = 0.0
    worst_at = None
    for s in segs:
        clip = anims[s["beat"]]
        dur = s["dur"]
        grid = 24
        for i in range(grid + 1):
            t = dur * i / grid
            d = _state_diff(SA.sample(composed, s["start"] + t), SA.sample(clip, t))
            if d > worst:
                worst, worst_at = d, {"beat": s["beat"], "t": round(t, 4)}
    ok = worst < FAITH_TOL
    return {"pass": bool(ok), "worst_residual": round(worst, 9), "worst_at": worst_at, "tol": FAITH_TOL}


def _combo_ok_in_context(composed, seg, clip):
    b = _any_bone(clip)
    vs_ctx = _seg_series(composed, b, seg["start"], seg["dur"])
    vs_iso = _clip_series(clip, b)
    pk_ctx = impact_peaks(vs_ctx)
    pk_iso = impact_peaks(vs_iso)
    match = len(pk_ctx) == len(pk_iso) and all(abs(a - c) <= 1e-4 for a, c in zip(pk_ctx, pk_iso))
    sig = len(pk_ctx) >= 3 and is_escalating(pk_ctx)
    return {"peaks_ctx": len(pk_ctx), "escalating": bool(is_escalating(pk_ctx)),
            "match_isolated": bool(match), "pass": bool(sig and match)}


def _cascade_ok_in_context(composed, seg, clip):
    bones = list(clip.get("bones", {}).keys())
    pts_ctx = [_peak_time_window(composed, b, seg["start"], seg["dur"]) for b in bones]
    spread_ctx = (max(pts_ctx) - min(pts_ctx)) if len(pts_ctx) >= 2 else 0.0
    pts_iso = [max(range(N + 1), key=lambda i: _clip_series(clip, b)[i]) / N for b in bones]
    spread_iso = (max(pts_iso) - min(pts_iso)) if len(pts_iso) >= 2 else 0.0
    match = abs(spread_ctx - spread_iso) <= 2.0 / N
    sig = spread_ctx >= SPREAD_THR
    return {"spread_ctx": round(spread_ctx, 4), "spread_iso": round(spread_iso, 4),
            "match_isolated": bool(match), "pass": bool(sig and match)}


def _charge_ok_in_context(composed, seg, clip):
    b = _any_bone(clip)
    vs_ctx = _seg_series(composed, b, seg["start"], seg["dur"])
    frac_ctx = pre_peak_hold_frac(vs_ctx)
    frac_iso = pre_peak_hold_frac(_clip_series(clip, b))
    match = abs(frac_ctx - frac_iso) <= 1e-3
    sig = frac_ctx >= HOLD_FRAC_THR
    return {"hold_frac_ctx": round(frac_ctx, 4), "hold_frac_iso": round(frac_iso, 4),
            "match_isolated": bool(match), "pass": bool(sig and match)}


def ac_L4(anims):
    composed, segs = G.compose_sequence(anims, POS_ORDER)
    seg_of = {s["beat"]: s for s in segs}
    res = {}
    res["combo"] = _combo_ok_in_context(composed, seg_of["combo"], anims["combo"])
    res["cascade"] = _cascade_ok_in_context(composed, seg_of["cascade"], anims["cascade"])
    res["charge"] = _charge_ok_in_context(composed, seg_of["charge"], anims["charge"])
    ok = all(r["pass"] for r in res.values())
    return {"pass": bool(ok), **res}


def ac_L5(anims):
    # (a) burst(collapse 起手)插中段 → 其前接點(hit->burst)殘差應 >> SEAM_TOL
    order_a = ["In", "hit", "burst", "combo", "charge", "cascade", "Loop", "Out"]
    seams_a = _junction_seams(anims, order_a)
    worst_a = max(s["seam"] for s in seams_a)
    seamless_a = worst_a < SEAM_TOL
    flagged_a = (worst_a > NEG_MULT * SEAM_TOL) and (not seamless_a)
    # 指認肇因接點確為 *->burst
    off_a = max(seams_a, key=lambda s: s["seam"])["pair"]
    a_ok = flagged_a and off_a.endswith("->burst")

    # (b) Out(collapse 收尾)插中段 → 其後接點(Out->charge)殘差應 >> SEAM_TOL
    order_b = ["In", "hit", "combo", "Out", "charge", "cascade", "Loop"]
    seams_b = _junction_seams(anims, order_b)
    worst_b = max(s["seam"] for s in seams_b)
    off_b = max(seams_b, key=lambda s: s["seam"])["pair"]
    b_ok = (worst_b > NEG_MULT * SEAM_TOL) and off_b.startswith("Out->")

    # (c) composability:主秀 beat(皆 identity 介面)對調 → 仍無縫 且 各段簽章仍成立
    order_c = ["In", "cascade", "charge", "combo", "hit", "Loop", "Out"]
    seams_c = _junction_seams(anims, order_c)
    worst_c = max(s["seam"] for s in seams_c)
    seamless_c = worst_c < SEAM_TOL
    composed_c, segs_c = G.compose_sequence(anims, order_c)
    seg_of_c = {s["beat"]: s for s in segs_c}
    combo_c = _combo_ok_in_context(composed_c, seg_of_c["combo"], anims["combo"])["pass"]
    casc_c = _cascade_ok_in_context(composed_c, seg_of_c["cascade"], anims["cascade"])["pass"]
    chg_c = _charge_ok_in_context(composed_c, seg_of_c["charge"], anims["charge"])["pass"]
    c_ok = seamless_c and combo_c and casc_c and chg_c

    ok = a_ok and b_ok and c_ok
    return {"pass": bool(ok),
            "a_burst_mid": {"pass": bool(a_ok), "worst_seam": round(worst_a, 4),
                            "offender": off_a, "correctly_non_seamless": bool(not seamless_a)},
            "b_out_mid": {"pass": bool(b_ok), "worst_seam": round(worst_b, 4), "offender": off_b},
            "c_reorder_composable": {"pass": bool(c_ok), "worst_seam": round(worst_c, 6),
                                     "seamless": bool(seamless_c),
                                     "combo_sig": bool(combo_c), "cascade_sig": bool(casc_c),
                                     "charge_sig": bool(chg_c)}}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    # 確認序列用到的 beat 皆存在(fixture 完整性)
    missing = [nm for nm in set(POS_ORDER) if nm not in anims]
    if missing:
        return {"overall_pass": False, "error": "missing beats in fixture: {}".format(missing),
                "available": sorted(anims.keys())}
    results = {"L1_wellformed_present": ac_L1(anims),
               "L2_crux_seamless": ac_L2(anims),
               "L3_faithful_concat": ac_L3(anims),
               "L4_incontext_signature": ac_L4(anims),
               "L5_neg_control": ac_L5(anims)}
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
        print("candidate (L) 大獎序列組合閘 — compose_sequence")
        print("序列:", " -> ".join(POS_ORDER))
        for k in ["L1_wellformed_present", "L2_crux_seamless", "L3_faithful_concat",
                  "L4_incontext_signature", "L5_neg_control"]:
            v = res.get(k, {})
            print("  {:28s} {}".format(k, "PASS" if v.get("pass") else "FAIL"))
        if "L2_crux_seamless" in res:
            print("    L2 worst interior seam: {:.2e} (tol {:.0e})".format(
                res["L2_crux_seamless"]["worst_seam"], SEAM_TOL))
        if "L3_faithful_concat" in res:
            print("    L3 worst回切殘差: {:.2e}".format(res["L3_faithful_concat"]["worst_residual"]))
        if "L5_neg_control" in res:
            n = res["L5_neg_control"]
            print("    L5a burst-mid worst seam: {} (offender {})".format(
                n["a_burst_mid"]["worst_seam"], n["a_burst_mid"]["offender"]))
            print("    L5c reorder seamless: {} worst {:.2e}".format(
                n["c_reorder_composable"]["seamless"], n["c_reorder_composable"]["worst_seam"]))
        print("OVERALL:", "PASS" if res.get("overall_pass") else "FAIL")
    return 0 if res.get("overall_pass") else 1


if __name__ == "__main__":
    sys.exit(main())
