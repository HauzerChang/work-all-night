#!/usr/bin/env python3
"""candidate (J-4) 自我驗收閘 — cascade 跨件波的相位**散佈寬** span 隨檔位遞增(純 CPU)。

candidate (J) 讓主秀 beat 依檔位**幅度**差異化(峰愈大);(J-3) 讓 cascade 的**波掃道數** nrip 隨檔位遞增
(掃幾道)。本閘驗 (J-4):cascade 的**跨件散佈寬** span —— 各件峰時刻散得多開(波掃過整體多闊)——
**隨檔位嚴格遞增**(Super 0.54 → Mega 0.58 → Omg 0.62 → Legend 0.66),且此為 cascade 的**第三條**檔位軸,
與 nrip(波掃道數=結構)、幅度增益 g(峰大小)**三軸正交**。

**crux(第三條 cascade 軸 = 純跨件時序的散佈)**:span 只改各件峰的**相對時刻**(第一件峰在 LEAD、最後一件峰
在 LEAD+span),**不改峰數**(仍每件 pop nrip 次)、**不改峰幅**(仍 role peak);與 nrip 正交 —— 同時開兩軸時
每道 sweep 的跨件散佈=span/nrip,把 per-sweep 散佈**×nrip** 即還原 span → span 軸可在任一 nrip 下獨立量得。
span 是**連續時序參數**(非 count/拓樸),故在 `build_animations` 走獨立於 `_count_maps` 的 `_span_maps` 路由,
以該檔位 span **重生成** cascade 檔位變體再套幅度增益 g(散佈×道數×幅度多效正交可疊)。

真值界定同 (E/H/I/J/J-2/J-3):主秀運動無唯一正解(先驗手感),閘驗**客觀結構簽章非美感**;方向(span 遞增
=波掃愈闊)為 A 類 PROPOSAL,反向(遞減=愈同步/愈快)為對等替代待使用者拍板;用負對照證鑑別力(閘可信)。

閘從**先驗庫**經 `analyze_target`(build_storyboard)→ **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains, tier_cascade_spread[, tier_cascade_ripples])` 端到端量,與 (J)/(J-3) 閘同一 fixture。

  SP1 present + backward-compat : 每檔位皆產 `cascade__{tier}` 且 finite/有 bone;base cascade 不變(逐位元同
                                 純 base、Super 逐位元==base ← span Super=CASCADE_SPAN=0.54);**且** 不帶
                                 `tier_cascade_spread`(=None)時 cascade 變體逐位元同 (J) 幅度-only 輸出
                                 → 證 (J-4) 為**加性 opt-in**、對 (J)/(J-3) 零回歸。
  SP2 spread monotone (crux)   : 各檔位 cascade 跨件散佈(單 sweep 各件峰時刻 max−min)Super<Mega<Omg<Legend
                                 **嚴格遞增**且 ≈ 宣告 span(取樣誤差內);以 span-only(nrip=1)量。
  SP3 orthogonal-signature      : (crux)每檔位——各件峰時刻仍依**真實件序嚴格遞增**(散佈變寬仍是有序跨件波,
     + interface + amp mono       非切碎/非亂序);且每件 pop 次數**不隨 span 變**(恆 1,散佈非道數);每件首尾
                                 setup identity、特效 slot alpha 首尾=1(可插 Loop 間);且**幅度**峰仍隨檔位
                                 遞增(span 與 (J) 幅度軸疊加不衝突)。
  SP4 orthogonality (3-way)    : (a) spread + **平增益**(全 1.0)→ 散佈遞增(時序軸獨立於幅度)、峰幅**不**遞增;
                                 (b) gains + **無 spread**(None)→ 各檔位散佈**恆=base**(不隨檔位變)、峰幅遞增;
                                 (c) spread × **ripples 同時開** → 每檔位 pop 次數==nrip 階梯([1,2,3,4])**且**
                                    還原 span(per-sweep 散佈×nrip)嚴格遞增 ≈ 宣告 → 散佈/道數兩軸互不干擾(可疊)。
  SP5 neg-control              : (a) **平散佈寬**(全 0.54)→ SP2 單調性 FALSE(證閘在測遞增、非恆真);
                                 (b) 無宣告 spread 的 genre(slot_reveal)→ `cascade_spread_for` 回 None
                                    → 不產 spread 變體(cascade 檔位變體逐位元同幅度-only);
                                 (c) **只有 cascade 是 span-aware**:同時帶 spread 時,非-cascade 主秀 beat 的
                                    檔位變體**逐位元同**幅度-only(span 不外洩到別的節拍)。

用法:
  python3 validate_cascade_spread.py            # 摘要
  python3 validate_cascade_spread.py --json     # 完整 JSON
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

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
IMPACT = BT.IMPACT_PROM          # 1.10:pop 峰門檻(所有 role peak≥1.18 皆過)
N = 240
SPREAD_TOL = 2.0 / N             # 散佈量測的取樣容差(峰落在 N 格 → 最多 1 格誤差,兩端 → 2 格)


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/cascade_spread_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _part_order(sb):
    return ["b_" + G.safe(p["part"]) for p in sb["beats"][0]["parts"]]


def peak_times(anim, bone, n=N):
    """該 bone scaleX 的所有 impact 峰(局部極大 ≥ IMPACT)時刻 τ,升序。cascade 每道 sweep 一個 pop。"""
    v = series(anim, bone, n=n)
    return [i / n for i in range(1, len(v) - 1) if v[i] >= IMPACT and v[i - 1] < v[i] >= v[i + 1]]


def pop_counts(anim):
    """各件(bone)pop 次數 → (min, max)。span 不改峰數 → span-only 時應全 == 1。"""
    bones = anim.get("bones", {})
    cnts = [len(peak_times(anim, b)) for b in bones]
    return (min(cnts) if cnts else 0, max(cnts) if cnts else 0)


def scale_overshoot(anim):
    bones = anim.get("bones", {})
    return max((max(series(anim, b)) - 1.0 for b in bones), default=0.0)


def sweep_spread(anim, order, sweep=0):
    """第 `sweep` 道波的各件第 sweep 峰時刻(依件序)→ (spread=max−min, increasing?, times, counts)。

    span-only(nrip=1)時 sweep=0、每件 1 峰 → 跨件散佈直接=span。nrip>1 時取第 k 道:每件 nrip 峰,
    取第 k 個 → 跨件散佈=span/nrip(×nrip 還原 span)。"""
    bones = [b for b in order if b in anim.get("bones", {})]
    per = [peak_times(anim, b) for b in bones]
    counts = [len(p) for p in per]
    if any(len(p) <= sweep for p in per):
        return None, False, [], counts
    pts = [p[sweep] for p in per]
    return cascade_spread(pts), is_strictly_increasing(pts), [round(x, 3) for x in pts], counts


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
    spread = TV.cascade_spread_for(GENRE)
    rip = TV.cascade_ripples_for(GENRE)

    base = G.build_animations(skel, sb)                                              # 無檔位
    amp_only = G.build_animations(skel, sb, tier_gains=gains)                        # (J) 幅度-only
    full = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_spread=spread)  # (J-4) 幅度+散佈寬

    cbeats = _cascade_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- SP1 present + backward-compat ----
    sp1 = {"missing": [], "not_finite": [], "no_bones": [], "base_changed": [],
           "super_ne_base": [], "amp_only_regressed": []}
    for cb in cbeats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            an = full.get(vk)
            if an is None:
                sp1["missing"].append(vk); continue
            if not SA.all_finite(an):
                sp1["not_finite"].append(vk)
            if not an.get("bones"):
                sp1["no_bones"].append(vk)
        # base 不變(逐位元同純 base)、Super 逐位元==base(span=0.54=CASCADE_SPAN、g=1.0)
        if json.dumps(base[cb], sort_keys=True) != json.dumps(full[cb], sort_keys=True):
            sp1["base_changed"].append(cb)
        if json.dumps(full[cb], sort_keys=True) != json.dumps(full["{}__Super".format(cb)], sort_keys=True):
            sp1["super_ne_base"].append(cb)
    # tier_cascade_spread=None → cascade 變體逐位元同 (J) 幅度-only
    none_run = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_spread=None)
    for cb in cbeats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            if json.dumps(none_run.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                sp1["amp_only_regressed"].append(vk)
    R["SP1_present_backward_compat"] = {"cascade_beats": cbeats, "span_ladder": spread, **sp1,
                                        "pass": bool(cbeats) and not any(sp1[k] for k in sp1)}

    # ---- SP2 spread monotone (crux) ----  span-only(nrip=1)量跨件散佈
    span_only = G.build_animations(skel, sb, tier_gains={t: 1.0 for t in TIERS}, tier_cascade_spread=spread)
    sp2 = {"beats": {}, "fail": []}
    declared = [spread[t] for t in TIERS]
    for cb in cbeats:
        spreads, near = [], True
        for i, t in enumerate(TIERS):
            spr, inc, _times, cnts = sweep_spread(span_only["{}__{}".format(cb, t)], order, sweep=0)
            spreads.append(round(spr, 4) if spr is not None else None)
            if spr is None or abs(spr - declared[i]) > SPREAD_TOL or set(cnts) != {1}:
                near = False
        mono = all(x is not None for x in spreads) and is_strictly_increasing(spreads)
        sp2["beats"][cb] = {"spreads": spreads, "declared": declared, "monotone": mono, "matches_declared": near}
        if not (mono and near):
            sp2["fail"].append(cb)
    R["SP2_spread_monotone"] = {"tiers": TIERS, **sp2, "pass": bool(cbeats) and not sp2["fail"]}

    # ---- SP3 orthogonal-signature + interface + amp monotone ----
    sp3 = {"bad_order": [], "count_changed": [], "bad_interface": [], "amp_not_mono": [], "detail": {}}
    for cb in cbeats:
        for t in TIERS:
            an = full["{}__{}".format(cb, t)]
            spr, inc, times, cnts = sweep_spread(an, order, sweep=0)   # gains 開,但 nrip=1 → 每件 1 峰
            sp3["detail"]["{}__{}".format(cb, t)] = {"times": times, "increasing": inc, "counts": cnts}
            if not inc:
                sp3["bad_order"].append("{}__{}".format(cb, t))
            if set(cnts) != {1}:                                       # span 不改峰數(恆 1)
                sp3["count_changed"].append("{}__{}".format(cb, t))
            dur = SA.duration(an)
            b0 = SA.sample(an, 0.0)["bones"]; bE = SA.sample(an, dur)["bones"]
            s0 = SA.sample(an, 0.0)["slots"]; sE = SA.sample(an, dur)["slots"]
            iface = (all(_is_ident(v) for v in b0.values()) and all(_is_ident(v) for v in bE.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in s0.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in sE.values()))
            if not iface:
                sp3["bad_interface"].append("{}__{}".format(cb, t))
        amp = [scale_overshoot(full["{}__{}".format(cb, t)]) for t in TIERS]
        if not is_strictly_increasing(amp):
            sp3["amp_not_mono"].append((cb, [round(x, 3) for x in amp]))
    R["SP3_orthogonal_signature"] = {"bad_order": sp3["bad_order"], "count_changed": sp3["count_changed"],
                                     "bad_interface": sp3["bad_interface"], "amp_not_mono": sp3["amp_not_mono"],
                                     "detail": sp3["detail"],
                                     "pass": not sp3["bad_order"] and not sp3["count_changed"]
                                     and not sp3["bad_interface"] and not sp3["amp_not_mono"]}

    # ---- SP4 orthogonality (3-way) ----
    flat_gain = {t: 1.0 for t in TIERS}
    # (a) spread + 平增益 → 散佈遞增、峰幅不遞增
    spr_flatgain = {cb: [round(sweep_spread(span_only["{}__{}".format(cb, t)], order, 0)[0], 4) for t in TIERS]
                    for cb in cbeats}
    amp_flatgain = {cb: [round(scale_overshoot(span_only["{}__{}".format(cb, t)]), 3) for t in TIERS]
                    for cb in cbeats}
    a_ok = bool(cbeats) and all(is_strictly_increasing(v) for v in spr_flatgain.values()) \
        and not any(is_strictly_increasing(v) for v in amp_flatgain.values())
    # (b) gains + 無 spread → 散佈恆=base(不隨檔位變)、峰幅遞增
    spr_gainonly = {cb: [round(sweep_spread(amp_only["{}__{}".format(cb, t)], order, 0)[0], 4) for t in TIERS]
                    for cb in cbeats}
    amp_gainonly = {cb: [scale_overshoot(amp_only["{}__{}".format(cb, t)]) for t in TIERS] for cb in cbeats}
    b_ok = bool(cbeats) and all(len(set(v)) == 1 for v in spr_gainonly.values()) \
        and all(is_strictly_increasing(v) for v in amp_gainonly.values())
    # (c) spread × ripples 同時開 → pop 次數==nrip 階梯 且 還原 span(per-sweep 散佈×nrip)遞增 ≈ 宣告
    both = G.build_animations(skel, sb, tier_gains=gains,
                              tier_cascade_ripples=rip, tier_cascade_spread=spread)
    c_detail = {}
    c_ok = bool(cbeats)
    for cb in cbeats:
        counts, recovered = [], []
        for t in TIERS:
            an = both["{}__{}".format(cb, t)]
            (mn, mx) = pop_counts(an)
            counts.append(mx if mn == mx else -1)                        # -1 = 件間 pop 數不一致
            spr0, inc0, _t, _c = sweep_spread(an, order, sweep=0)        # 第 0 道波的跨件散佈=span/nrip
            recovered.append(round(spr0 * rip[t], 4) if spr0 is not None else None)
        counts_ok = (counts == [rip[t] for t in TIERS])
        # 還原 span = per-sweep 散佈(span/nrip)×nrip;量測量化誤差(每端 ≤1/N)乘 nrip 放大 → 容差 2·nrip/N。
        rec_ok = all(r is not None for r in recovered) and is_strictly_increasing(recovered) \
            and all(abs(recovered[i] - spread[TIERS[i]]) <= 2.0 * rip[TIERS[i]] / N for i in range(len(TIERS)))
        c_detail[cb] = {"pop_counts": counts, "declared_nrip": [rip[t] for t in TIERS],
                        "recovered_span": recovered, "declared_span": [spread[t] for t in TIERS],
                        "counts_ok": counts_ok, "recovered_ok": rec_ok}
        c_ok = c_ok and counts_ok and rec_ok
    R["SP4_orthogonality"] = {"a_spread_flatgain": spr_flatgain, "a_amp_flatgain": amp_flatgain, "a_pass": a_ok,
                              "b_spread_gainonly": spr_gainonly, "b_pass": b_ok,
                              "c_spread_x_ripples": c_detail, "c_pass": c_ok,
                              "pass": a_ok and b_ok and c_ok}

    # ---- SP5 negative controls ----
    sp5 = {}
    # (a) 平散佈寬(全 0.54)→ 單調性 FALSE
    flat_spread = {t: BT.CASCADE_SPAN for t in TIERS}
    fs = G.build_animations(skel, sb, tier_gains=flat_gain, tier_cascade_spread=flat_spread)
    any_mono_flat = False
    for cb in cbeats:
        vals = [round(sweep_spread(fs["{}__{}".format(cb, t)], order, 0)[0], 4) for t in TIERS]
        if is_strictly_increasing(vals):
            any_mono_flat = True
    sp5["a_flat_spread_guard"] = {"any_spread_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) 無宣告 spread 的 genre → cascade_spread_for None → 不產 spread 變體(同幅度-only)
    rv_spread = TV.cascade_spread_for("slot_reveal")
    rv_sb = _storyboard("slot_reveal")
    rv_gains = TV.gains_for("slot_reveal")
    rv_amp = G.build_animations(skel, rv_sb, tier_gains=rv_gains)
    rv_full = G.build_animations(skel, rv_sb, tier_gains=rv_gains, tier_cascade_spread=rv_spread)
    rv_casc_leak = [k for k in rv_full if "__" in k and G.beat_category(k) == "cascade"
                    and json.dumps(rv_full[k], sort_keys=True) != json.dumps(rv_amp.get(k), sort_keys=True)]
    sp5["b_no_spread_genre"] = {"cascade_spread_for_slot_reveal": rv_spread,
                                "cascade_variants_changed": rv_casc_leak,
                                "pass": rv_spread is None and not rv_casc_leak}
    # (c) span 只作用於 cascade:非-cascade 主秀 beat 的檔位變體逐位元同幅度-only(不外洩)。
    leak = []
    for beat, cat in main_beats.items():
        if cat == "cascade":
            continue
        for t in TIERS:
            vk = "{}__{}".format(beat, t)
            if json.dumps(full.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                leak.append(vk)
    sp5["c_span_isolated_to_cascade"] = {"leaked": leak, "pass": not leak}
    R["SP5_neg_control"] = {**sp5, "pass": all(v["pass"] for v in sp5.values())}

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
        for k in ["SP1_present_backward_compat", "SP2_spread_monotone", "SP3_orthogonal_signature",
                  "SP4_orthogonality", "SP5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("SP2 cascade cross-part spread per tier {}:".format(TIERS))
        for cb, d in R["SP2_spread_monotone"]["beats"].items():
            print("  {:10s} spreads {} (declared {})".format(cb, d["spreads"], d["declared"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
