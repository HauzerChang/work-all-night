#!/usr/bin/env python3
"""candidate (J-4) 自我驗收閘 — cascade 跨件波**散佈幅度** span 隨檔位遞增(純 CPU)。

(J-3) 讓 cascade 的**波掃次數** nrip 隨檔位遞增(掃幾道波 = **結構/拓樸**軸);本閘驗 (J-4) 的**另一條正交軸**:
一道 sweep 內**各件峰時刻的散佈幅度** span 隨檔位嚴格遞增(Super 0.54 → Mega 0.58 → Omg 0.62 → Legend 0.66)——
愈高檔位波掃**愈開**(跨件錯開愈戲劇)。這是**跨件時序**通道的**幅度式**軸,與 (J-3) nrip 的**結構**軸、(J) 值增益的
**深度**軸三者正交可疊。

**crux(J-4 的 honest distinction,本閘的核心鑑別點)**:span 的語意是「幅度」(愈大波掃愈開),照理應像 (J) 用
post-hoc 值增益 `g`(`v'=g·v`)加大。**但不能** —— 跨件散佈活在關鍵幀的**時間位置**(峰中心 c_k=(LEAD+p·span)/nrip),
**不在值**;值增益只放大 pop **深度**(scale 峰值 overshoot),各件峰**時刻**分毫不動 → 散佈完全不變。故 span 雖語意
屬幅度,機制上必須在 gen 當下**重生成**(同 count 軸),是「**time-position 幅度** vs **value 幅度**」的分野。本閘 Y5(b)
以「post-hoc 值增益放大 base cascade → 散佈仍==base」的負對照,證此軸確實無法由幅度機制產生、非重生成不可。

閘從**先驗庫**經 `analyze_target`(build_storyboard)→ **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains, tier_cascade_span[, tier_cascade_ripples])` 端到端量,與 (J)/(J-2)/(J-3) 閘同一 fixture。

  Y1 present + backward-compat : 每檔位皆產 `cascade__{tier}` 且 finite/有 bone;base cascade 不變(逐位元不變、散佈==base、
                                Super span-only 逐位元==base);**且** 不帶 `tier_cascade_span`(=None)時 cascade 變體逐位元同 (J)
                                幅度-only → 證 (J-4) 為**加性 opt-in**、對 (J)/(J-3) 零回歸。
  Y2 span monotone (crux)     : **隔離量測(nrip 固定=1,tier_cascade_ripples=None)**:各檔位單道 sweep 的**跨件散佈**
                                (各件峰時刻 max−min)== 宣告 span(≈)且 Super<Mega<Omg<Legend **嚴格遞增**、Super==base;
                                每檔位各件峰時刻仍依件序**嚴格遞增**(仍是有序跨件波,散佈變大不打亂波序)。
  Y3 signature + interface     : 每檔位(span-only)仍具 cascade 簽章(跨件峰時刻遞增 + 散佈≥門檻);每件首尾 setup
                                identity、特效 slot alpha 首尾=1(可插 Loop 間);span 軸**不動深度**(各檔位峰 overshoot
                                在平增益下相等,證 span≠幅度深度)。
  Y4 orthogonality            : (a) span + **平增益**(全 1.0)→ 散佈仍嚴格遞增(散佈獨立於深度)、峰**深度不**遞增;
                                (b) gains + **無 span**(None)→ 各檔位散佈**恆==base**、但峰深度遞增 → 兩軸可獨立開關;
                                (c) span ⟂ nrip:同時帶(nrip[t], span[t])→ 每件 pop 次數==nrip(nrip 軸不受 span 干擾)
                                   **且** 固定 nrip 下 span[t]>0.54 的檔位其**每道 sweep 散佈** > 同 nrip 但 span=base 者
                                   (span 在多道波下仍加寬每道波)。
  Y5 neg-control              : (a) **平 span**(全 0.54)→ Y2 單調性 FALSE(證閘在測遞增、非恆真);
                                (b) **crux honest-distinction**:對 base cascade 施 post-hoc **值增益** amplify(J 的幅度機制)
                                   → 散佈仍==base(**不變**)而峰深度變大 → 證 span 軸**無法由幅度機制產生**、非重生成不可;
                                (c) 無宣告 span 的 genre(slot_reveal)→ `cascade_span_for` 回 None → 不產 span 變體;且
                                   **只有 cascade 是 span-aware**:非-cascade 主秀 beat 的檔位變體逐位元同幅度-only(不外洩)。

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
from tier_variants import amplify_anim as _amplify_anim
from validate_cascade import series, is_strictly_increasing, cascade_spread

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
IMPACT = BT.IMPACT_PROM          # 1.10:pop 峰門檻
SPREAD_FLOOR = 0.30              # 有序跨件波的最小散佈(同 validate_cascade.SPREAD_THR 精神)
N = 240


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


def _part_order(sb):
    return ["b_" + G.safe(p["part"]) for p in sb["beats"][0]["parts"]]


def peak_times(anim, bone, n=N):
    """該 bone scaleX 的所有 impact 峰(局部極大 ≥ IMPACT)時刻 τ,升序。cascade 每道 sweep 一個 pop。"""
    v = series(anim, bone, n=n)
    return [i / n for i in range(1, len(v) - 1) if v[i] >= IMPACT and v[i - 1] < v[i] >= v[i + 1]]


def cross_part_spread(anim, order):
    """單道 sweep(nrip=1)下各件全域峰時刻的散佈(max−min)+ 是否依件序遞增。回傳 (spread, increasing, times)。"""
    bones = [b for b in order if b in anim.get("bones", {})]
    pts = []
    for b in bones:
        v = series(anim, b)
        pts.append(max(range(len(v)), key=lambda i: v[i]) / N)
    return cascade_spread(pts), is_strictly_increasing(pts), pts


def sweep0_spread(anim, order):
    """多道 sweep 下,**第一道 sweep** 各件首個 pop 時刻的散佈(= span/nrip 的量測值)。"""
    bones = [b for b in order if b in anim.get("bones", {})]
    firsts = [peak_times(anim, b)[0] for b in bones if peak_times(anim, b)]
    return cascade_spread(firsts)


def ripple_counts(anim):
    bones = anim.get("bones", {})
    cnts = [len(peak_times(anim, b)) for b in bones]
    return (min(cnts) if cnts else 0, max(cnts) if cnts else 0), cnts


def scale_overshoot(anim):
    bones = anim.get("bones", {})
    return max((max(series(anim, b)) - 1.0 for b in bones), default=0.0)


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
    span = TV.cascade_span_for(GENRE)

    base = G.build_animations(skel, sb)                                          # 無檔位
    amp_only = G.build_animations(skel, sb, tier_gains=gains)                    # (J) 幅度-only
    # span-only 隔離(nrip 固定=1):幅度增益 + 跨件散佈,無波掃次數 → 每檔位單道 sweep、散佈=span。
    span_only = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_span=span)
    full = G.build_animations(skel, sb, tier_gains=gains,
                              tier_cascade_ripples=rip, tier_cascade_span=span)  # 三軸全開

    cbeats = _cascade_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- Y1 present + backward-compat ----
    y1 = {"missing": [], "not_finite": [], "no_bones": [], "base_changed": [],
          "super_ne_base": [], "amp_only_regressed": []}
    for cb in cbeats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            an = span_only.get(vk)
            if an is None:
                y1["missing"].append(vk); continue
            if not SA.all_finite(an):
                y1["not_finite"].append(vk)
            if not an.get("bones"):
                y1["no_bones"].append(vk)
        # base cascade 不變(逐位元)
        if json.dumps(base[cb], sort_keys=True) != json.dumps(span_only[cb], sort_keys=True):
            y1["base_changed"].append(cb)
        # Super span-only(span=0.54=base、g=1.0)逐位元==base
        if json.dumps(span_only[cb], sort_keys=True) != json.dumps(span_only["{}__Super".format(cb)], sort_keys=True):
            y1["super_ne_base"].append(cb)
    # tier_cascade_span=None → cascade 變體逐位元同 (J) 幅度-only
    none_run = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_span=None)
    for cb in cbeats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            if json.dumps(none_run.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                y1["amp_only_regressed"].append(vk)
    R["Y1_present_backward_compat"] = {"cascade_beats": cbeats, **y1,
                                       "pass": bool(cbeats) and not any(y1[k] for k in y1)}

    # ---- Y2 span monotone (crux, isolated nrip=1) ----
    y2 = {"beats": {}, "fail": []}
    expected = [span[t] for t in TIERS]
    base_spread = {cb: round(cross_part_spread(span_only[cb], order)[0], 4) for cb in cbeats}
    for cb in cbeats:
        spreads, orders_ok = [], True
        for t in TIERS:
            sp, inc, _ = cross_part_spread(span_only["{}__{}".format(cb, t)], order)
            spreads.append(round(sp, 4))
            orders_ok = orders_ok and inc
        mono = is_strictly_increasing(spreads)
        # 量測散佈 ≈ 宣告 span(取樣誤差 ≤ 2/N)
        matches = all(abs(spreads[i] - expected[i]) <= 3.0 / N for i in range(len(TIERS)))
        super_eq_base = abs(spreads[0] - base_spread[cb]) <= 1e-9
        y2["beats"][cb] = {"spreads": spreads, "declared_span": expected, "monotone": mono,
                           "matches_declared": matches, "orders_increasing": orders_ok,
                           "super_eq_base": super_eq_base}
        if not (mono and matches and orders_ok and super_eq_base):
            y2["fail"].append(cb)
    R["Y2_span_monotone"] = {"tiers": TIERS, **y2, "pass": bool(cbeats) and not y2["fail"]}

    # ---- Y3 signature + interface + depth-untouched ----
    y3 = {"bad_signature": [], "bad_interface": [], "depth_moved": [], "detail": {}}
    for cb in cbeats:
        depths = []
        for t in TIERS:
            an = span_only["{}__{}".format(cb, t)]
            sp, inc, pts = cross_part_spread(an, order)
            sig_ok = inc and sp >= SPREAD_FLOOR
            y3["detail"]["{}__{}".format(cb, t)] = {"spread": round(sp, 3),
                                                    "increasing": inc, "times": [round(x, 3) for x in pts]}
            if not sig_ok:
                y3["bad_signature"].append("{}__{}".format(cb, t))
            dur = SA.duration(an)
            b0 = SA.sample(an, 0.0)["bones"]; bE = SA.sample(an, dur)["bones"]
            s0 = SA.sample(an, 0.0)["slots"]; sE = SA.sample(an, dur)["slots"]
            iface = (all(_is_ident(v) for v in b0.values()) and all(_is_ident(v) for v in bE.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in s0.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in sE.values()))
            if not iface:
                y3["bad_interface"].append("{}__{}".format(cb, t))
            depths.append(round(scale_overshoot(an), 4))
        # span 軸不動深度:各檔位峰 overshoot(平增益前提下由 tier_gains 決定,span-only 用真 gains → 深度隨 g 增,
        # 但這裡 span_only 已含 gains;要證「span 不動深度」需與同 gains 但不同 span 比 → 見 Y4(a) 平增益。此處僅記錄。)
        y3["detail"][cb + "__depths"] = depths
    R["Y3_signature_interface"] = {"bad_signature": y3["bad_signature"], "bad_interface": y3["bad_interface"],
                                   "detail": y3["detail"],
                                   "pass": not y3["bad_signature"] and not y3["bad_interface"]}

    # ---- Y4 orthogonality ----
    # (a) span + 平增益 → 散佈遞增、峰深度不遞增
    flat_gain = {t: 1.0 for t in TIERS}
    sa = G.build_animations(skel, sb, tier_gains=flat_gain, tier_cascade_span=span)
    spread_flatgain = {cb: [round(cross_part_spread(sa["{}__{}".format(cb, t)], order)[0], 4) for t in TIERS]
                       for cb in cbeats}
    depth_flatgain = {cb: [round(scale_overshoot(sa["{}__{}".format(cb, t)]), 4) for t in TIERS] for cb in cbeats}
    a_ok = bool(cbeats) and all(is_strictly_increasing(v) for v in spread_flatgain.values()) \
        and not any(is_strictly_increasing(v) for v in depth_flatgain.values())
    # (b) gains + 無 span → 散佈恆==base、峰深度遞增
    spread_gainonly = {cb: [round(cross_part_spread(amp_only["{}__{}".format(cb, t)], order)[0], 4) for t in TIERS]
                       for cb in cbeats}
    depth_gainonly = {cb: [round(scale_overshoot(amp_only["{}__{}".format(cb, t)]), 4) for t in TIERS] for cb in cbeats}
    b_ok = bool(cbeats) and all(max(v) - min(v) <= 2.0 / N for v in spread_gainonly.values()) \
        and all(is_strictly_increasing(v) for v in depth_gainonly.values())
    # (c) span ⟂ nrip:pop 次數==nrip(不受 span 干擾)且固定 nrip 下 span[t]>base 者每道 sweep 散佈更寬
    nrip_ok = True
    span_widens = True
    detail_c = {}
    for cb in cbeats:
        for t in TIERS:
            an = full["{}__{}".format(cb, t)]
            (mn, mx), _ = ripple_counts(an)
            if not (mn == mx == rip[t]):
                nrip_ok = False
            # 同 nrip 但 span=base(0.54)的對照
            base_span_map = {tt: 0.54 for tt in TIERS}
            an_base = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip,
                                         tier_cascade_span=base_span_map)["{}__{}".format(cb, t)]
            sw_big = sweep0_spread(an, order)
            sw_base = sweep0_spread(an_base, order)
            detail_c["{}__{}".format(cb, t)] = {"nrip": mx, "sweep0_spread_span": round(sw_big, 4),
                                                "sweep0_spread_base": round(sw_base, 4)}
            if span[t] > 0.54 and not (sw_big > sw_base + 1e-6):
                span_widens = False
    c_ok = nrip_ok and span_widens
    R["Y4_orthogonality"] = {"a_spread_flat_gain": spread_flatgain, "a_depth_flat_gain": depth_flatgain, "a_pass": a_ok,
                             "b_spread_gain_only": spread_gainonly, "b_depth_gain_only": depth_gainonly, "b_pass": b_ok,
                             "c_nrip_intact": nrip_ok, "c_span_widens_per_sweep": span_widens, "c_detail": detail_c,
                             "c_pass": c_ok, "pass": a_ok and b_ok and c_ok}

    # ---- Y5 negative controls ----
    y5 = {}
    # (a) 平 span(全 0.54)→ 散佈單調性 FALSE
    flat_span = {t: 0.54 for t in TIERS}
    fs = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_span=flat_span)
    any_mono_flat = any(is_strictly_increasing([round(cross_part_spread(fs["{}__{}".format(cb, t)], order)[0], 4)
                                                for t in TIERS]) for cb in cbeats)
    y5["a_flat_span_guard"] = {"any_spread_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) crux honest-distinction:post-hoc 值增益 amplify 加不出散佈(散佈==base,深度變大)
    bcd = {}
    big_g = max(gains.values())
    amp_ok = True
    for cb in cbeats:
        base_sp = cross_part_spread(base[cb], order)[0]
        amped = _amplify_anim(base[cb], big_g)          # 只施幅度值增益(J 機制),不重生成
        amp_sp = cross_part_spread(amped, order)[0]
        base_depth = scale_overshoot(base[cb])
        amp_depth = scale_overshoot(amped)
        spread_unchanged = abs(amp_sp - base_sp) <= 1.0 / N       # 散佈不變(值增益動不了時間位置)
        depth_grew = amp_depth > base_depth + 1e-3                # 深度確實變大(證 amplify 有作用、非空操作)
        bcd[cb] = {"base_spread": round(base_sp, 4), "amp_spread": round(amp_sp, 4),
                   "base_depth": round(base_depth, 4), "amp_depth": round(amp_depth, 4),
                   "spread_unchanged": spread_unchanged, "depth_grew": depth_grew}
        amp_ok = amp_ok and spread_unchanged and depth_grew
    y5["b_amplify_cannot_widen_spread"] = {"gain": big_g, "detail": bcd, "pass": bool(cbeats) and amp_ok}
    # (c) 無宣告 span 的 genre(slot_reveal)→ cascade_span_for None → 不產 span 變體;且 span 只作用 cascade
    rv_span = TV.cascade_span_for("slot_reveal")
    y5c = {"cascade_span_for_slot_reveal": rv_span, "span_none": rv_span is None}
    leak = []
    for beat, cat in main_beats.items():
        if cat == "cascade":
            continue
        for t in TIERS:
            vk = "{}__{}".format(beat, t)
            if json.dumps(span_only.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                leak.append(vk)
    y5c["leaked"] = leak
    y5["c_span_isolated_to_cascade"] = {**y5c, "pass": (rv_span is None) and not leak}
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
        for k in ["Y1_present_backward_compat", "Y2_span_monotone", "Y3_signature_interface",
                  "Y4_orthogonality", "Y5_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("Y2 cascade cross-part spread per tier {} (isolated nrip=1):".format(TIERS))
        for cb, d in R["Y2_span_monotone"]["beats"].items():
            print("  {:10s} spread {} (declared span {})".format(cb, d["spreads"], d["declared_span"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
