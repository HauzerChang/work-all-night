#!/usr/bin/env python3
"""candidate (J-3) 自我驗收閘 — cascade 跨件波**掃過整體的次數** nrip 隨檔位遞增(純 CPU)。

candidate (J) 讓主秀 beat 依檔位**幅度**差異化(愈高檔位愈爆),cascade 亦在其中(波峰隨檔位放大),
但所有檔位的 cascade 仍是**同一道**跨件波 ——「掃得多猛」有了、「掃幾道」沒有。本閘驗 (J-3):
cascade 的**波掃次數** nrip **隨檔位嚴格遞增**(Super 1 → Mega 2 → Omg 3 → Legend 4),且此**結構**軸與
(J) 的**幅度**軸**正交可疊**、不破壞任何既有簽章 / 介面契約。

**與單件 count(combo/wobble/squash/twist)本質不同(crux)**:那些 count 是**單件內**極值數(同一件連幾下,
段數落在單件曲線);cascade 的 nrip 是**跨件波掃幾道**(段數落在**跨件時序**通道,cascade∈_PHASE_AWARE)。
故 count 簽章需同時驗兩層:① 每件 pop nrip 次(單件峰數);② **每道 sweep 內各件峰時刻仍依件序遞增**
(跨件排序在每道波皆保住,不是把一道波切碎成雜訊)。波掃道數是**結構**(gen 時決定關鍵幀窗,事後 amplify
只能同比放大既有 pop、加不出第二道 sweep)—— 故走 `tier_cascade_ripples` 在 `build_animations` 對 cascade
檔位變體以該檔位 nrip **重生成**再套幅度增益。真值界定同 (E/H/I/J/J-2):主秀運動無唯一正解(先驗手感),
閘驗**客觀結構簽章非美感**;用負對照證鑑別力(閘可信)。

閘從**先驗庫**經 `analyze_target`(build_storyboard)→ **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains, tier_cascade_ripples)` 端到端量,與 (J)/(J-2) 閘同一 fixture。

  X1 present + backward-compat : 每檔位皆產 `cascade__{tier}` 且 finite/有 bone;base cascade 不變(恆 nrip=1
                                逐位元不變、Super 逐位元==base);**且** 不帶 `tier_cascade_ripples`(=None)時
                                cascade 變體逐位元同 (J) 幅度-only 輸出 → 證 (J-3) 為**加性 opt-in**、對 (J) 零回歸。
  X2 ripple monotone (crux)   : 各檔位 cascade 每件 pop 次數(impact 峰數)== 宣告 nrip 且 Super<Mega<Omg<Legend
                                **嚴格遞增**;每檔位**所有件**pop 次數一致(min==max==nrip)。
  X3 per-sweep cross-part sig  : (crux)每檔位——**每一道 sweep k** 的各件第 k 峰時刻依**真實件序嚴格遞增**且
     + interface kept           散佈 ≥ 門檻(每道波皆是有序跨件波,非切碎);且每件首尾 setup identity、
                                特效 slot alpha 首尾=1(可插 Loop 間);且**幅度**峰仍隨檔位遞增(與 (J) 疊加不衝突)。
  X4 orthogonality            : (a) ripples + **平增益**(全 1.0)→ 波掃次數仍遞增(結構獨立於幅度)、峰幅**不**遞增;
                                (b) gains + **無 ripples**(None)→ 各檔位波掃次數**恆 1**、但峰幅遞增
                                → 兩軸可獨立開關(正交)。
  X5 neg-control              : (a) **平波掃次數**(全 1)→ X2 單調性 FALSE(證閘在測遞增、非恆真);
                                (b) 無宣告 ripple 的 genre(slot_reveal)→ `cascade_ripples_for` 回 None
                                   → 不產 cascade ripple 變體(不亂加波);
                                (c) **只有 cascade 是 ripple-aware**:同時帶 ripples 時,非-cascade 主秀 beat 的
                                   檔位變體**逐位元同**幅度-only(ripple 不外洩到別的節拍)。

用法:
  python3 validate_cascade_count.py            # 摘要
  python3 validate_cascade_count.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import beat_templates as BT
from analyze_target import analyze
import tier_variants as TV
from validate_cascade import series, is_strictly_increasing, cascade_spread, has_cascade_signature

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
IMPACT = BT.IMPACT_PROM          # 1.10:pop 峰門檻(所有 role peak≥1.18 皆過)
N = 240


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/cascade_count_skel"
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


def ripple_counts(anim):
    """各件(bone)pop 次數(= 波掃道數的單件視角)→ (min, max)。所有件應一致 == nrip。"""
    bones = anim.get("bones", {})
    cnts = [len(peak_times(anim, b)) for b in bones]
    return (min(cnts) if cnts else 0, max(cnts) if cnts else 0), cnts


def scale_overshoot(anim):
    bones = anim.get("bones", {})
    return max((max(series(anim, b)) - 1.0 for b in bones), default=0.0)


def per_sweep_ordered(anim, order, nrip):
    """每一道 sweep k(k=0..nrip-1)的各件第 k 峰時刻依件序嚴格遞增且散佈 ≥ 門檻。

    門檻 = 0.6 * (CASCADE_SPAN / nrip):每道 sweep 的相位窗被壓縮 1/nrip,故理論散佈=SPAN/nrip;
    取 0.6 倍為容忍取樣誤差的實散佈下界(仍遠高於近同時觸發 combo 的 spread≈0 負對照)。"""
    bones = [b for b in order if b in anim.get("bones", {})]
    floor = 0.6 * (BT.CASCADE_SPAN / max(1, nrip))
    per = [peak_times(anim, b) for b in bones]
    # 每件都必須恰好 nrip 個峰,才能逐 sweep 取第 k 峰
    if any(len(p) != nrip for p in per) or nrip < 1:
        return False, {"reason": "not all parts have nrip peaks", "counts": [len(p) for p in per]}
    rows = []
    ok = True
    for k in range(nrip):
        pts = [p[k] for p in per]
        inc = is_strictly_increasing(pts)
        spread = cascade_spread(pts)
        good = inc and spread >= floor
        rows.append({"sweep": k, "times": [round(x, 3) for x in pts],
                     "increasing": inc, "spread": round(spread, 3), "floor": round(floor, 3), "pass": good})
        ok = ok and good
    return ok, {"n_parts": len(bones), "sweeps": rows}


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
    rip = TV.cascade_ripples_for(GENRE)

    base = G.build_animations(skel, sb)                                             # 無檔位
    amp_only = G.build_animations(skel, sb, tier_gains=gains)                       # (J) 幅度-only
    full = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip)  # (J-3) 幅度+波掃次數

    cbeats = _cascade_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- X1 present + backward-compat ----
    x1 = {"missing": [], "not_finite": [], "no_bones": [], "base_changed": [],
          "super_ne_base": [], "amp_only_regressed": []}
    for cb in cbeats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            an = full.get(vk)
            if an is None:
                x1["missing"].append(vk); continue
            if not SA.all_finite(an):
                x1["not_finite"].append(vk)
            if not an.get("bones"):
                x1["no_bones"].append(vk)
        # base 不變(恆 1 道波)、Super 逐位元==base(nrip=1、g=1.0)
        (bmin, bmax), _ = ripple_counts(full[cb])
        if bmin != 1 or bmax != 1 or json.dumps(base[cb], sort_keys=True) != json.dumps(full[cb], sort_keys=True):
            x1["base_changed"].append(cb)
        if json.dumps(full[cb], sort_keys=True) != json.dumps(full["{}__Super".format(cb)], sort_keys=True):
            x1["super_ne_base"].append(cb)
    # tier_cascade_ripples=None → cascade 變體逐位元同 (J) 幅度-only
    none_run = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=None)
    for cb in cbeats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            if json.dumps(none_run.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                x1["amp_only_regressed"].append(vk)
    R["X1_present_backward_compat"] = {"cascade_beats": cbeats, **x1,
                                       "pass": bool(cbeats) and not any(x1[k] for k in x1)}

    # ---- X2 ripple monotone (crux) ----
    x2 = {"beats": {}, "fail": []}
    expected = [rip[t] for t in TIERS]
    for cb in cbeats:
        counts, consistent = [], True
        for t in TIERS:
            (mn, mx), _ = ripple_counts(full["{}__{}".format(cb, t)])
            counts.append(mx)
            if mn != mx:
                consistent = False
        mono = is_strictly_increasing(counts)
        matches = (counts == expected)
        x2["beats"][cb] = {"counts": counts, "expected": expected,
                           "monotone": mono, "matches_declared": matches, "all_parts_consistent": consistent}
        if not (mono and matches and consistent):
            x2["fail"].append(cb)
    R["X2_ripple_monotone"] = {"tiers": TIERS, **x2, "pass": bool(cbeats) and not x2["fail"]}

    # ---- X3 per-sweep cross-part signature + interface + amplitude monotone ----
    x3 = {"bad_sweep": [], "bad_interface": [], "amp_not_mono": [], "detail": {}}
    for cb in cbeats:
        for t in TIERS:
            an = full["{}__{}".format(cb, t)]
            nrip = rip[t]
            ok_sweep, d = per_sweep_ordered(an, order, nrip)
            x3["detail"]["{}__{}".format(cb, t)] = d
            if not ok_sweep:
                x3["bad_sweep"].append("{}__{}".format(cb, t))
            dur = SA.duration(an)
            b0 = SA.sample(an, 0.0)["bones"]; bE = SA.sample(an, dur)["bones"]
            s0 = SA.sample(an, 0.0)["slots"]; sE = SA.sample(an, dur)["slots"]
            iface = (all(_is_ident(v) for v in b0.values()) and all(_is_ident(v) for v in bE.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in s0.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in sE.values()))
            if not iface:
                x3["bad_interface"].append("{}__{}".format(cb, t))
        amp = [scale_overshoot(full["{}__{}".format(cb, t)]) for t in TIERS]
        if not is_strictly_increasing(amp):
            x3["amp_not_mono"].append((cb, [round(x, 3) for x in amp]))
    R["X3_per_sweep_signature"] = {"bad_sweep": x3["bad_sweep"], "bad_interface": x3["bad_interface"],
                                   "amp_not_mono": x3["amp_not_mono"], "detail": x3["detail"],
                                   "pass": not x3["bad_sweep"] and not x3["bad_interface"] and not x3["amp_not_mono"]}

    # ---- X4 orthogonality ----
    # (a) ripples + 平增益 → 波掃次數仍遞增、峰幅不遞增
    flat_gain = {t: 1.0 for t in TIERS}
    ca = G.build_animations(skel, sb, tier_gains=flat_gain, tier_cascade_ripples=rip)
    counts_flatgain = {cb: [ripple_counts(ca["{}__{}".format(cb, t)])[0][1] for t in TIERS] for cb in cbeats}
    amp_flatgain = {cb: [round(scale_overshoot(ca["{}__{}".format(cb, t)]), 3) for t in TIERS] for cb in cbeats}
    a_ok = bool(cbeats) and all(is_strictly_increasing(v) for v in counts_flatgain.values()) \
        and not any(is_strictly_increasing(v) for v in amp_flatgain.values())
    # (b) gains + 無 ripples → 波掃次數恆 1、峰幅遞增
    counts_gainonly = {cb: [ripple_counts(amp_only["{}__{}".format(cb, t)])[0][1] for t in TIERS] for cb in cbeats}
    amp_gainonly = {cb: [scale_overshoot(amp_only["{}__{}".format(cb, t)]) for t in TIERS] for cb in cbeats}
    b_ok = bool(cbeats) and all(v == [1, 1, 1, 1] for v in counts_gainonly.values()) \
        and all(is_strictly_increasing(v) for v in amp_gainonly.values())
    R["X4_orthogonality"] = {"a_counts_with_flat_gain": counts_flatgain, "a_amp_flat_gain": amp_flatgain,
                             "a_pass": a_ok, "b_gain_only_counts_fixed1": counts_gainonly, "b_pass": b_ok,
                             "pass": a_ok and b_ok}

    # ---- X5 negative controls ----
    x5 = {}
    # (a) 平波掃次數(全 1)→ 單調性 FALSE
    flat_rip = {t: 1 for t in TIERS}
    fr = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=flat_rip)
    any_mono_flat = any(is_strictly_increasing([ripple_counts(fr["{}__{}".format(cb, t)])[0][1] for t in TIERS])
                        for cb in cbeats)
    x5["a_flat_ripples_guard"] = {"any_count_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) 無宣告 ripple 的 genre → cascade_ripples_for None → 不產 ripple 變體
    rv_rip = TV.cascade_ripples_for("slot_reveal")
    rv_sb = _storyboard("slot_reveal")
    rv_gains = TV.gains_for("slot_reveal")
    rv_full = G.build_animations(skel, rv_sb, tier_gains=rv_gains, tier_cascade_ripples=rv_rip)
    rv_casc_variants = [k for k in rv_full if "__" in k and G.beat_category(k) == "cascade"]
    x5["b_no_ripple_genre"] = {"cascade_ripples_for_slot_reveal": rv_rip,
                               "cascade_variants": rv_casc_variants,
                               "pass": rv_rip is None and not rv_casc_variants}
    # (c) ripple 只作用於 cascade:非-cascade 主秀 beat 的檔位變體逐位元同幅度-only(不外洩)。
    leak = []
    for beat, cat in main_beats.items():
        if cat == "cascade":
            continue
        for t in TIERS:
            vk = "{}__{}".format(beat, t)
            if json.dumps(full.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                leak.append(vk)
    x5["c_ripple_isolated_to_cascade"] = {"leaked": leak, "pass": not leak}
    R["X5_neg_control"] = {**x5, "pass": all(v["pass"] for v in x5.values())}

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
        for k in ["X1_present_backward_compat", "X2_ripple_monotone", "X3_per_sweep_signature",
                  "X4_orthogonality", "X5_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("X2 cascade ripple(sweep) counts per tier {}:".format(TIERS))
        for cb, d in R["X2_ripple_monotone"]["beats"].items():
            print("  {:10s} counts {} (declared {})".format(cb, d["counts"], d["expected"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
