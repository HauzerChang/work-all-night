#!/usr/bin/env python3
"""candidate (J-2) 自我驗收閘 — combo 連擊**數**隨檔位遞增(純 CPU)。

candidate (J) 讓主秀 beat 依檔位**幅度**差異化(峰更高);本閘驗 J-2:combo 主秀的檔位變體
連擊**數**也隨檔位遞增(Super 3 連 → Legend 6 連),且幅度增益仍疊加其上。從**先驗庫**經
`analyze_target` → **真實 build_spine robot 骨架** → `build_animations(..., tier_gains, tier_combo_peaks)`
端到端量測。

真值界定同 (E)/(H)/(I)/(J):主秀運動無唯一正解(先驗手感),閘驗**客觀結構簽章非美感**。
「連擊數隨檔位遞增」是 cascade(跨件時序)之外的**第二個跨參數簽章** —— 單一 tier 曲線看不出
「隨檔位遞增」,只有**跨檔位比峰數**才看得出;故需獨立整合閘,並以「平峰數守衛」證鑑別力。

  K1 present+routing : 每檔位皆產出 `combo__{tier}` 且 finite/有 bone、名仍路由回 combo 類別;
                       base combo 不變、`combo__Super`(3 連 × g=1.0)**逐位元 == base combo**。
  K2 interface IF    : 每檔位 combo__{tier} 首尾 bone 皆 setup identity(可插 Loop 間)。
  K3 crux count-mono : **每檔位每 bone** 的 impact 峰**數** == 該檔位宣告連擊數,且各檔位峰數
                       Super<Mega<Omg<Legend **嚴格遞增**(3<4<5<6)。(端到端經 build_animations 量。)
  K4 signature+amp   : 每檔位仍 has_combo_signature(遞增 impact 峰)且**非** charge(互斥);
                       且 J 的幅度單調仍成立 —— finale(全域峰)幅度隨檔位嚴格遞增(峰數增加不破壞幅度增益)。
  K5 neg-control     : (a) **平峰數守衛**:把連擊數階梯全設 3 → K3 峰數單調性 FALSE(證閘真在測峰數遞增,非恆真);
                       (b) 不帶 tier_combo_peaks(=None)→ 各檔位 combo 皆 3 峰(峰數非單調)——證峰數遞增源於 J-2;
                       (c) escalate **不外洩**:非 combo 主秀 beat(hit/burst/charge/cascade)各檔位峰數
                          與 base 同、且 In/Loop/Out 不產 combo 變體(峰數遞增只作用於 combo)。

用法:
  python3 validate_tier_combo.py            # 摘要
  python3 validate_tier_combo.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze
import tier_variants as TV
# 復用既有度量,確保簽章判準與 0g/(J) 閘完全一致
from validate_more_beats import series, impact_peaks, has_combo_signature, has_charge_signature

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/tier_combo_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _peak_counts(anim):
    """回傳 {bone: impact 峰數}。"""
    return {b: len(impact_peaks(series(anim, b))) for b in anim.get("bones", {})}


def _global_peak(anim):
    """全域峰(所有 bone scaleX 最大值)—— 用於幅度單調(finale 幅度)。"""
    return max((max(series(anim, b)) for b in anim.get("bones", {})), default=1.0)


def _is_strict_inc(xs):
    return all(xs[i] < xs[i + 1] for i in range(len(xs) - 1))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    peaks_map = TV.combo_peaks_for(GENRE)
    base = G.build_animations(skel, sb)                                   # 無檔位
    anims = G.build_animations(skel, sb, tier_gains=gains, tier_combo_peaks=peaks_map)   # J-2

    R = {}

    # ---- K1 present + routing + backward-compat ----
    k1 = {"missing": [], "not_finite": [], "no_bones": [], "misrouted": [], "super_not_identical": False,
          "base_changed": False}
    for t in TIERS:
        vk = "combo__{}".format(t)
        an = anims.get(vk)
        if an is None:
            k1["missing"].append(vk); continue
        if not SA.all_finite(an):
            k1["not_finite"].append(vk)
        if not an.get("bones"):
            k1["no_bones"].append(vk)
        if G.beat_category(vk) != "combo":
            k1["misrouted"].append((vk, G.beat_category(vk)))
    # base combo 逐位元不變 + combo__Super == base combo
    if json.dumps(base.get("combo"), sort_keys=True) != json.dumps(anims.get("combo"), sort_keys=True):
        k1["base_changed"] = True
    if json.dumps(anims.get("combo__Super"), sort_keys=True) != json.dumps(base.get("combo"), sort_keys=True):
        k1["super_not_identical"] = True
    R["K1_present_routing"] = {"peaks_declared": peaks_map, **k1,
                               "pass": (not k1["missing"] and not k1["not_finite"] and not k1["no_bones"]
                                        and not k1["misrouted"] and not k1["base_changed"]
                                        and not k1["super_not_identical"])}

    # ---- K2 interface contract per tier ----
    k2 = {"bad_start": [], "bad_end": []}
    for t in TIERS:
        an = anims["combo__{}".format(t)]
        dur = SA.duration(an)
        for b, bd in SA.sample(an, 0.0)["bones"].items():
            if not _is_ident(bd):
                k2["bad_start"].append(("combo__{}".format(t), b, round(bd["scaleX"], 3)))
        for b, bd in SA.sample(an, dur)["bones"].items():
            if not _is_ident(bd):
                k2["bad_end"].append(("combo__{}".format(t), b, round(bd["scaleX"], 3)))
    R["K2_interface"] = {**k2, "pass": not k2["bad_start"] and not k2["bad_end"]}

    # ---- K3 crux: per-tier peak COUNT == declared, and strictly increasing across tiers ----
    k3 = {"per_tier": {}, "count_mismatch": [], "counts": []}
    for t in TIERS:
        an = anims["combo__{}".format(t)]
        pc = _peak_counts(an)
        counts = sorted(set(pc.values()))
        declared = peaks_map[t]
        # 每個 bone 峰數都須 == 宣告連擊數
        if counts != [declared]:
            k3["count_mismatch"].append((t, declared, counts))
        k3["per_tier"][t] = {"declared": declared, "bone_counts": counts}
        k3["counts"].append(declared)
    # 各檔位峰數嚴格遞增(用「實測」——每檔位取眾數/唯一值)
    measured = [k3["per_tier"][t]["bone_counts"][0] if len(k3["per_tier"][t]["bone_counts"]) == 1
                else max(k3["per_tier"][t]["bone_counts"]) for t in TIERS]
    k3["measured_counts"] = measured
    count_mono = _is_strict_inc(measured)
    R["K3_count_monotone"] = {**k3, "count_monotone": count_mono,
                              "pass": not k3["count_mismatch"] and count_mono}

    # ---- K4 signature preserved + amplitude still monotone ----
    k4 = {"sig_fail": [], "global_peaks": []}
    for t in TIERS:
        an = anims["combo__{}".format(t)]
        csig = has_combo_signature(an)
        hsig = has_charge_signature(an)
        if not (csig and not hsig):
            k4["sig_fail"].append((t, csig, hsig))
        k4["global_peaks"].append(round(_global_peak(an), 4))
    amp_mono = _is_strict_inc(k4["global_peaks"])
    R["K4_signature_amp"] = {**k4, "amp_monotone": amp_mono,
                             "pass": not k4["sig_fail"] and amp_mono}

    # ---- K5 negative controls ----
    k5 = {}
    # (a) 平峰數守衛:連擊數階梯全 3 → K3 峰數單調性應 FALSE
    flat_peaks = {t: 3 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=gains, tier_combo_peaks=flat_peaks)
    flat_counts = [max(set(_peak_counts(flat_anims["combo__{}".format(t)]).values())) for t in TIERS]
    k5["a_flat_count_guard"] = {"flat_counts": flat_counts,
                                "monotone": _is_strict_inc(flat_counts),
                                "pass": not _is_strict_inc(flat_counts)}
    # (b) 不帶 tier_combo_peaks → 各檔位 combo 皆 3 峰(峰數非單調),仍具 combo 簽章
    noesc = G.build_animations(skel, sb, tier_gains=gains)   # tier_combo_peaks=None
    noesc_counts = [max(set(_peak_counts(noesc["combo__{}".format(t)]).values())) for t in TIERS]
    noesc_all3 = all(c == 3 for c in noesc_counts)
    noesc_sig = all(has_combo_signature(noesc["combo__{}".format(t)]) for t in TIERS)
    k5["b_no_escalate_default"] = {"counts": noesc_counts, "all_three": noesc_all3,
                                   "combo_sig": noesc_sig, "not_monotone": not _is_strict_inc(noesc_counts),
                                   "pass": noesc_all3 and noesc_sig and not _is_strict_inc(noesc_counts)}
    # (c) escalate 不外洩:非 combo 主秀 beat 各檔位峰數 == base;In/Loop/Out 不產 combo 變體
    leak = {"nonbase_changed": [], "combo_staging_variants": []}
    main_non_combo = [nm for nm in base if "__" not in nm
                      and G.beat_category(nm) in TV.MAIN_SHOW_CATS and G.beat_category(nm) != "combo"]
    for nm in main_non_combo:
        base_counts = sorted(set(_peak_counts(base[nm]).values()))
        for t in TIERS:
            vk = "{}__{}".format(nm, t)
            if vk not in anims:
                continue
            tc = sorted(set(_peak_counts(anims[vk]).values()))
            if tc != base_counts:
                leak["nonbase_changed"].append((vk, base_counts, tc))
    # In/Loop/Out 不該有 combo 類別變體(本來就不產任何主秀變體,這裡確認無 combo__ 之外的擾動)
    staging_combo = [k for k in anims if "__" in k and G.beat_category(k) in ("intro", "loop", "outro")]
    leak["combo_staging_variants"] = staging_combo
    k5["c_no_leak"] = {**leak, "n_non_combo_main": len(main_non_combo),
                       "pass": not leak["nonbase_changed"] and not leak["combo_staging_variants"]}
    # (d) 無宣告 combo_peaks 的 genre → combo_peaks_for None
    other = TV.combo_peaks_for("slot_reveal")
    k5["d_no_decl_genre"] = {"combo_peaks_for_slot_reveal": other, "pass": other is None}
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
        for k in ["K1_present_routing", "K2_interface", "K3_count_monotone", "K4_signature_amp", "K5_neg_control"]:
            print("{:22s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("K3 measured combo peak counts per tier:", R["K3_count_monotone"]["measured_counts"])
        print("K4 finale(global-peak) amplitude per tier:", R["K4_signature_amp"]["global_peaks"])
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
