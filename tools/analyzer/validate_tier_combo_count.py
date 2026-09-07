#!/usr/bin/env python3
"""candidate (J-2) 自我驗收閘 — combo 連擊「數」隨檔位遞增(純 CPU)。

candidate (J) 讓主秀 beat 依檔位**幅度**差異化(愈高檔位愈爆),但所有檔位的 combo 仍是**同樣三連擊**
——「多爆」有了、「連幾下」沒有。本閘驗 (J-2):combo 的 impact 峰**數** = nhits **隨檔位嚴格遞增**
(Super 3 → Mega 4 → Omg 5 → Legend 6),且此**結構**軸與 (J) 的**幅度**軸**正交可疊**、
不破壞任何既有簽章/介面契約。

連擊數是**結構**(gen 時決定峰數,非事後 amplify 能加出來)—— 故走 `tier_combo_hits` 在 `build_animations`
對 combo 檔位變體以該檔位 nhits **重生成**再套幅度增益。真值界定同 (E/H/I/J):主秀運動無唯一正解
(先驗手感),閘驗**客觀結構簽章非美感**;用負對照證鑑別力(閘可信)。

閘從**先驗庫**經 `analyze_target`(build_storyboard)→ **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains, tier_combo_hits)` 端到端量,與 (J) 閘同一 fixture。

  K1 present + backward-compat : 每檔位皆產 `combo__{tier}` 且 finite/有 bone;base combo 不變(恆 nhits=3);
                                **且** 不帶 `tier_combo_hits`(=None)時 combo 變體逐位元同 (J) 幅度-only 輸出
                                → 證 (J-2) 為**加性 opt-in**、對 (J) 零回歸。
  K2 count monotone (crux)    : 各檔位 combo 的 impact 峰**數** == 宣告 nhits 且 Super<Mega<Omg<Legend
                                **嚴格遞增**;每檔位變體內部峰值仍**嚴格遞增**(escalating)。
  K3 interface+signature kept : 每檔位——首尾 setup identity、仍 has_combo_signature(遞增峰≥3)、仍 settle
                                (變號≥3)、**仍非 charge**(連擊數增多不致誤入長蓄力簽章)、且**幅度**仍
                                Super<Mega<Omg<Legend 單調(證與 (J) 疊加不衝突)。
  K4 orthogonality            : (a) counts + **平增益**(全 1.0)→ 峰數仍遞增(連擊數是**結構**,與幅度無關);
                                (b) gains + **無 counts**(None)→ 各檔位 combo 峰數**恆 3**、但幅度遞增
                                → 兩軸可獨立開關(正交)。
  K5 neg-control              : (a) **平連擊數**(全 3)→ K2 峰數單調性 FALSE(證閘在測遞增、非恆真);
                                (b) 無宣告 count 的 genre(slot_reveal)→ `combo_hits_for` 回 None
                                   → combo 變體峰數**恆 base**(不亂加連擊);
                                (c) **只有 combo 是 count-aware**:同時帶 counts 時,hit/charge/cascade/burst
                                   等非-combo 主秀 beat 的峰數在各檔位**不變**(count 不外洩到別的節拍)。

用法:
  python3 validate_tier_combo_count.py            # 摘要
  python3 validate_tier_combo_count.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze
import tier_variants as TV
from validate_more_beats import (series, sign_changes, impact_peaks,
                                 has_combo_signature, has_charge_signature)
from validate_cascade import is_strictly_increasing

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/tier_combo_count_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _min_peaks(anim):
    """該 anim 各 bone 的 impact 峰數之最小值(所有件都至少連這麼多下)。"""
    bones = anim.get("bones", {})
    return min((len(impact_peaks(series(anim, b))) for b in bones), default=0)


def _all_escalating(anim):
    return has_combo_signature(anim)


def _scale_overshoot(anim):
    bones = anim.get("bones", {})
    return max((max(series(anim, b)) - 1.0 for b in bones), default=0.0)


def _combo_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "combo"]


def _main_beats(anims):
    return {nm: G.beat_category(nm) for nm in anims
            if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    hits = TV.combo_hits_for(GENRE)

    base = G.build_animations(skel, sb)                                       # 無檔位
    amp_only = G.build_animations(skel, sb, tier_gains=gains)                 # (J) 幅度-only
    full = G.build_animations(skel, sb, tier_gains=gains, tier_combo_hits=hits)  # (J-2) 幅度+連擊數

    combo_beats = _combo_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- K1 present + backward-compat ----
    k1 = {"missing": [], "not_finite": [], "no_bones": [], "base_changed": [], "amp_only_regressed": []}
    for cb in combo_beats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            an = full.get(vk)
            if an is None:
                k1["missing"].append(vk); continue
            if not SA.all_finite(an):
                k1["not_finite"].append(vk)
            if not an.get("bones"):
                k1["no_bones"].append(vk)
    # base combo 不變(恆 nhits=3 → 3 峰)
    for cb in combo_beats:
        if _min_peaks(full[cb]) != 3 or json.dumps(base[cb], sort_keys=True) != json.dumps(full[cb], sort_keys=True):
            k1["base_changed"].append(cb)
    # tier_combo_hits=None 時,combo 變體逐位元同 (J) 幅度-only(加性 opt-in)
    none_run = G.build_animations(skel, sb, tier_gains=gains, tier_combo_hits=None)
    for cb in combo_beats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            if json.dumps(none_run.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                k1["amp_only_regressed"].append(vk)
    R["K1_present_backward_compat"] = {"combo_beats": combo_beats, **k1,
                                       "pass": not any(k1[k] for k in k1)}

    # ---- K2 count monotone (crux) ----
    k2 = {"beats": {}, "fail": []}
    expected = [hits[t] for t in TIERS]
    for cb in combo_beats:
        counts = [_min_peaks(full["{}__{}".format(cb, t)]) for t in TIERS]
        esc_each = all(_all_escalating(full["{}__{}".format(cb, t)]) for t in TIERS)
        mono = is_strictly_increasing(counts)
        matches = (counts == expected)
        k2["beats"][cb] = {"counts": counts, "expected": expected,
                           "monotone": mono, "matches_declared": matches, "each_escalating": esc_each}
        if not (mono and matches and esc_each):
            k2["fail"].append(cb)
    R["K2_count_monotone"] = {"tiers": TIERS, **k2, "pass": not k2["fail"] and bool(combo_beats)}

    # ---- K3 interface + signature preserved + amplitude still monotone ----
    k3 = {"bad_interface": [], "no_combo_sig": [], "no_settle": [], "is_charge": [], "amp_not_mono": []}
    for cb in combo_beats:
        for t in TIERS:
            an = full["{}__{}".format(cb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                k3["bad_interface"].append("{}__{}".format(cb, t))
            if not has_combo_signature(an):
                k3["no_combo_sig"].append("{}__{}".format(cb, t))
            if not all(sign_changes(series(an, b)) >= 3 for b in an.get("bones", {})):
                k3["no_settle"].append("{}__{}".format(cb, t))
            if has_charge_signature(an):     # 連擊數增多不得誤入 charge 長蓄力簽章
                k3["is_charge"].append("{}__{}".format(cb, t))
        amp = [_scale_overshoot(full["{}__{}".format(cb, t)]) for t in TIERS]
        if not is_strictly_increasing(amp):
            k3["amp_not_mono"].append((cb, [round(x, 3) for x in amp]))
    R["K3_interface_signature"] = {**k3, "pass": not any(k3[k] for k in k3)}

    # ---- K4 orthogonality ----
    # (a) counts + 平增益 → 峰數仍遞增(結構獨立於幅度)
    flat_gain = {t: 1.0 for t in TIERS}
    ca = G.build_animations(skel, sb, tier_gains=flat_gain, tier_combo_hits=hits)
    counts_flatgain = {cb: [_min_peaks(ca["{}__{}".format(cb, t)]) for t in TIERS] for cb in combo_beats}
    a_ok = all(is_strictly_increasing(v) for v in counts_flatgain.values()) and bool(combo_beats)
    # (b) gains + 無 counts → 峰數恆 3、幅度遞增
    cb_gainonly = {cb: [_min_peaks(amp_only["{}__{}".format(cb, t)]) for t in TIERS] for cb in combo_beats}
    amp_gainonly = {cb: [_scale_overshoot(amp_only["{}__{}".format(cb, t)]) for t in TIERS] for cb in combo_beats}
    b_ok = all(v == [3, 3, 3, 3] for v in cb_gainonly.values()) and \
        all(is_strictly_increasing(v) for v in amp_gainonly.values()) and bool(combo_beats)
    R["K4_orthogonality"] = {
        "a_counts_with_flat_gain": counts_flatgain, "a_pass": a_ok,
        "b_gain_only_counts_fixed3": cb_gainonly, "b_pass": b_ok,
        "pass": a_ok and b_ok}

    # ---- K5 negative controls ----
    k5 = {}
    # (a) 平連擊數(全 3)→ 峰數單調性 FALSE
    flat_hits = {t: 3 for t in TIERS}
    fh = G.build_animations(skel, sb, tier_gains=gains, tier_combo_hits=flat_hits)
    any_mono_flat = any(is_strictly_increasing([_min_peaks(fh["{}__{}".format(cb, t)]) for t in TIERS])
                        for cb in combo_beats)
    k5["a_flat_hits_guard"] = {"any_count_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) 無宣告 count 的 genre → combo_hits_for None → 峰數恆 base(此 fixture 借用 slot_bigwin 骨架 + slot_reveal 分鏡)
    rv_hits = TV.combo_hits_for("slot_reveal")
    rv_sb = _storyboard("slot_reveal")
    rv_gains = TV.gains_for("slot_reveal")
    rv_full = G.build_animations(skel, rv_sb, tier_gains=rv_gains, tier_combo_hits=rv_hits)
    rv_combo_variants = [k for k in rv_full if "__" in k and G.beat_category(k) == "combo"]
    # slot_reveal 無 tier 宣告 → 連 tier 變體都不該產(gains None);且 combo_hits_for None
    k5["b_no_count_genre"] = {"combo_hits_for_slot_reveal": rv_hits,
                              "combo_variants": rv_combo_variants,
                              "pass": rv_hits is None and not rv_combo_variants}
    # (c) count 只作用於 combo:非-combo 主秀 beat 的峰數在各檔位不變
    leak = []
    for beat, cat in main_beats.items():
        if cat == "combo":
            continue
        counts = [_min_peaks(full["{}__{}".format(beat, t)]) for t in TIERS]
        if len(set(counts)) != 1:      # count 外洩 → 各檔位峰數不同
            leak.append((beat, cat, counts))
    k5["c_count_isolated_to_combo"] = {"leaked": leak, "pass": not leak}
    R["K5_neg_control"] = {**k5, "pass": all(v["pass"] for v in k5.values())}

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
        for k in ["K1_present_backward_compat", "K2_count_monotone", "K3_interface_signature",
                  "K4_orthogonality", "K5_neg_control"]:
            print("{:28s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("K2 combo peak counts per tier {}:".format(TIERS))
        for cb, d in R["K2_count_monotone"]["beats"].items():
            print("  {:10s} counts {} (declared {})".format(cb, d["counts"], d["expected"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
