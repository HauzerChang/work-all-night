#!/usr/bin/env python3
"""candidate (J) 整合閘 — tier(檔位)變體幅度差異化。

`slot_bigwin` 宣告 tiers=[Super,Mega,Omg,Legend],但主秀 beat 至今各檔位共用同一組幅度。
本能力讓 `build_spine --animate --tiers`(或 `build_animations(..., tiers=True)`)對**主秀**節拍
(hit/reveal/combo/charge/cascade)依檔位序位產出**差異化幅度**的變體 `<beat>_<Tier>`:愈高檔位
主秀愈誇張。機制 = 對一個 beat 的**幾何 excursion**(scale 相對 identity=1、rotate 相對 0)乘上
單參數增益 g=1+STEP·序位(見 `beat_templates.apply_tier_gain`),一致縮放。

驗的是**客觀**性質(主秀運動無唯一美感正解):
  J1 present+routing : slot_bigwin tiers=True → 每主秀 beat 恰產 len(tiers) 支 `<beat>_<Tier>`,
                       各路由到正確類別;In/Loop/Out(結構,非主秀)仍單支、名不變。
  J2 幅度單調遞增    : 每主秀 beat,scale 幅度(各 bone max_t|scaleX−1| 取最大)依宣告檔位序**嚴格遞增**
                       Super<Mega<Omg<Legend;且**量化增益吻合** —— Legend excess / Super excess ≈ g_Legend
                       (=2.05,證是真實幾何增益非任意數);rotate 幅度亦非遞減。
  J3 介面契約(逐檔位): 每檔位變體仍保 setup identity 介面 —— hit/combo/charge/cascade 首尾 identity;
                       reveal(burst)首 collapsed(alpha≈0)尾 identity。放大不破壞可串接性。
  J4 結構簽章(逐檔位): 放大**不跨越**簽章 —— combo 仍遞增峰≥3、charge 仍長蓄力佔比≥0.35 且 squash(非塌陷)、
                       cascade 仍跨件峰時刻遞增+散佈、hit/burst 仍**非** combo/charge。
  J5 regression+負對照: (a) Super(序位 0 → g=1.0)clip 與**未分檔** build 的該 beat **逐位元相同**、且
                       In/Loop/Out 於分檔前後逐位元相同(g=1.0 no-op,既有閘不受擾);
                       (b) tiers=None 的 genre(slot_reveal)以 tiers=True build **產 0 支** `_<Tier>` clip(fallback 單支);
                       (c) 鑑別力:各檔位峰值**非全相等**(真差異化非共用)、且依宣告序遞增(降序排序 ≠ 宣告序 → 方向有意義)。

與既有閘分工:本閘是唯一驗「**檔位→幅度**」映射的閘;beat 本身的簽章/介面由 0f–0h + (E)(H)(I) 閘保證,
本閘 J3/J4 只確認**放大後**這些性質仍逐檔位成立(即 tier 增益是保結構的一致縮放)。

用法:
  python3 validate_tier_variants.py            # 摘要
  python3 validate_tier_variants.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import genre_priors as GP
import beat_templates as BT
from analyze_target import analyze
# 復用既有簽章度量,判準與 0g/0h/(E)(H)(I) 閘完全一致
from validate_more_beats import (series, impact_peaks, is_escalating, pre_peak_hold_frac,
                                 has_combo_signature, has_charge_signature, is_ident,
                                 HOLD_FRAC_THR, SQUASH_FLOOR)
from validate_cascade import (peak_times_in_order, cascade_spread, is_strictly_increasing,
                              has_cascade_signature, SPREAD_THR)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
PEAK_THR = 1.12
N = 240
CAT_OF = {"hit": "hit", "burst": "reveal", "combo": "combo", "charge": "charge", "cascade": "cascade"}


def _skeleton():
    import build_spine
    out = "/tmp/tier_variants_skel"
    build_spine.build(PSD, out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(PSD, genre)["3_motion_storyboard"]


def _part_order(skel, sb):
    bone_names = {b["name"] for b in skel["bones"]}
    order = []
    for pe in sb["beats"][0]["parts"]:
        bn = "b_" + G.safe(pe["part"])
        if bn in bone_names:
            order.append(bn)
    return order


def _scale_amp(anim):
    """clip 的主秀 scale 幅度 = 各 bone **正向 pop overshoot**(max_t scaleX − 1)取最大。
    用正向 overshoot 而非 |scaleX−1|:reveal 的 collapsed 起點(scale~0.02,結構性「藏」)是**向下**
    excursion 且放大後 clamp 飽和,非「愈高檔位愈誇張」的主秀幅度;真正隨檔位放大的是**向上的 pop**。"""
    amp = 0.0
    for b in anim.get("bones", {}):
        v = series(anim, b, "scaleX", N)
        amp = max(amp, max(v) - 1.0)
    return amp


def _rot_amp(anim):
    """clip 的 rotate 幅度 = 各 bone max_t|angle| 取最大。"""
    amp = 0.0
    for b in anim.get("bones", {}):
        tl = anim["bones"][b].get("rotate")
        if tl:
            amp = max(amp, max(abs(f["angle"]) for f in tl))
    return amp


def _tiered_anims(skel, genre):
    return G.build_animations(skel, _storyboard(genre), tiers=True)


def _base_anims(skel, genre):
    return G.build_animations(skel, _storyboard(genre), tiers=False)


# ---------------- AC ----------------
def check_j1(skel):
    """每主秀 beat 恰產 len(tiers) 支 <beat>_<Tier>,類別正確;In/Loop/Out 仍單支不改名。"""
    tiers = GP.get(GENRE)["tiers"]
    anims = _tiered_anims(skel, genre=GENRE)
    detail, ok = {}, True
    for beat, cat in CAT_OF.items():
        names = [f"{beat}_{t}" for t in tiers]
        present = [nm in anims for nm in names]
        routed = all(G.beat_category(nm) == cat for nm in names if nm in anims)
        good = all(present) and routed
        detail[beat] = {"expected": names, "all_present": all(present),
                        "routed_ok": routed, "pass": good}
        ok = ok and good
    # 非主秀 beat:In/Loop/Out 仍單支、無 _Tier 後綴
    structural = {"In", "Loop", "Out"}
    struct_single = all(s in anims for s in structural) and \
        not any(nm.startswith(tuple(f"{s}_" for s in structural)) for nm in anims)
    detail["structural_beats_single"] = {"names": sorted(structural & set(anims)),
                                         "no_tier_suffix": struct_single, "pass": struct_single}
    return ok and struct_single, detail


def check_j2(skel):
    """每主秀 beat 的 scale 幅度依檔位序嚴格遞增,rotate 幅度非遞減,且量化增益吻合 g。"""
    tiers = GP.get(GENRE)["tiers"]
    anims = _tiered_anims(skel, genre=GENRE)
    detail, ok = {}, True
    for beat in CAT_OF:
        samps = [(t, anims[f"{beat}_{t}"]) for t in tiers]
        s_amps = [round(_scale_amp(a), 5) for _, a in samps]
        r_amps = [round(_rot_amp(a), 4) for _, a in samps]
        s_inc = all(s_amps[i] < s_amps[i + 1] for i in range(len(s_amps) - 1))
        r_nondec = all(r_amps[i] <= r_amps[i + 1] + 1e-9 for i in range(len(r_amps) - 1))
        # 量化:Legend/Super excess 比 ≈ g_Legend(=tier_amp_gain(last idx))
        g_last = BT.tier_amp_gain(len(tiers) - 1)
        ratio = (s_amps[-1] / s_amps[0]) if s_amps[0] > 1e-9 else 0.0
        gain_ok = abs(ratio - g_last) <= 0.02
        good = s_inc and r_nondec and gain_ok
        detail[beat] = {"scale_amp_by_tier": dict(zip(tiers, s_amps)),
                        "rot_amp_by_tier": dict(zip(tiers, r_amps)),
                        "scale_strictly_increasing": s_inc, "rot_nondecreasing": r_nondec,
                        "excess_ratio_last_over_first": round(ratio, 4),
                        "expected_gain": g_last, "gain_match": gain_ok, "pass": good}
        ok = ok and good
    return ok, detail


def check_j3(skel):
    """逐檔位介面契約:hit/combo/charge/cascade 首尾 identity;reveal(burst)首 collapsed 尾 identity。"""
    tiers = GP.get(GENRE)["tiers"]
    anims = _tiered_anims(skel, genre=GENRE)
    detail, ok = {}, True
    for beat, cat in CAT_OF.items():
        rows = {}
        for t in tiers:
            an = anims[f"{beat}_{t}"]
            dur = SA.duration(an)
            b0 = SA.sample(an, 0.0)["bones"]; bE = SA.sample(an, dur)["bones"]
            end_id = all(is_ident(v) for v in bE.values())
            if cat == "reveal":
                # 首 collapsed:effect/mesh slot alpha≈0(藏),bone scale 亦壓縮
                s0 = SA.sample(an, 0.0)["slots"]
                start_ok = (len(s0) == 0) or any(abs(s["alpha"]) <= 1e-3 for s in s0.values())
                # 尾 identity(bone),slot alpha 回 1
                sE = SA.sample(an, dur)["slots"]
                end_id = end_id and all(abs(s["alpha"] - 1) <= 1e-3 for s in sE.values())
                good = start_ok and end_id
                rows[t] = {"start_collapsed": start_ok, "end_identity": end_id, "pass": good}
            else:
                start_id = all(is_ident(v) for v in b0.values())
                good = start_id and end_id
                rows[t] = {"start_identity": start_id, "end_identity": end_id, "pass": good}
            ok = ok and good
        detail[beat] = rows
    return ok, detail


def check_j4(skel):
    """逐檔位結構簽章:放大不跨越簽章(combo 遞增峰 / charge 長蓄力squash / cascade 跨件波 / hit,burst 非 combo,charge)。"""
    tiers = GP.get(GENRE)["tiers"]
    sb = _storyboard(GENRE)
    order = _part_order(skel, sb)
    anims = _tiered_anims(skel, genre=GENRE)
    detail, ok = {}, True
    for beat, cat in CAT_OF.items():
        rows = {}
        for t in tiers:
            an = anims[f"{beat}_{t}"]
            if cat == "combo":
                good = has_combo_signature(an) and not has_charge_signature(an)
            elif cat == "charge":
                good = has_charge_signature(an) and not has_combo_signature(an)
            elif cat == "cascade":
                good = has_cascade_signature(an, order) and not has_combo_signature(an)
            else:  # hit / reveal(burst):單發,非 combo 非 charge
                good = (not has_combo_signature(an)) and (not has_charge_signature(an))
            rows[t] = {"cat": cat, "pass": bool(good)}
            ok = ok and good
        detail[beat] = rows
    return ok, detail


def check_j5(skel):
    """regression + 負對照。"""
    tiers = GP.get(GENRE)["tiers"]
    base = _base_anims(skel, genre=GENRE)
    tiered = _tiered_anims(skel, genre=GENRE)
    detail = {}

    # (a) Super == 未分檔基準(逐位元);In/Loop/Out 分檔前後逐位元相同
    super_eq = {}
    a_ok = True
    for beat in CAT_OF:
        eq = tiered[f"{beat}_{tiers[0]}"] == base[beat]
        super_eq[beat] = eq
        a_ok = a_ok and eq
    struct_eq = all(tiered[s] == base[s] for s in ("In", "Loop", "Out"))
    detail["a_super_eq_base_and_structural_unchanged"] = {
        "super_eq_base": super_eq, "structural_identical": struct_eq,
        "pass": a_ok and struct_eq}

    # (b) tiers=None 的 genre 以 tiers=True build → 0 支 _Tier clip(fallback 單支)
    reveal_anims = G.build_animations(skel, _storyboard("slot_reveal"), tiers=True)
    # slot_reveal 檔位為 None → 不應出現任何 "<beat>_<Tier>" 命名(以 slot_bigwin 檔位名探測)
    suffixes = tuple(f"_{t}" for t in tiers)
    n_tier_clips = sum(1 for nm in reveal_anims if nm.endswith(suffixes))
    b_ok = (n_tier_clips == 0)
    detail["b_no_tiers_genre_no_tier_clips"] = {
        "genre": "slot_reveal", "tier_variants": GP.get("slot_reveal")["tiers"],
        "n_tier_suffixed_clips": n_tier_clips, "pass": b_ok}

    # (c) 鑑別力:各檔位峰值非全相等,且依宣告序嚴格遞增(降序排序 ≠ 宣告序 → 方向有意義)
    disc_rows, c_ok = {}, True
    for beat in CAT_OF:
        amps = [round(_scale_amp(tiered[f"{beat}_{t}"]), 5) for t in tiers]
        not_all_equal = len(set(amps)) == len(amps)   # 全相異(共用會全相等)
        increasing = all(amps[i] < amps[i + 1] for i in range(len(amps) - 1))
        direction_matters = sorted(amps, reverse=True) != amps  # 宣告序非降序 → 方向有意義
        good = not_all_equal and increasing and direction_matters
        disc_rows[beat] = {"amps": amps, "all_distinct": not_all_equal,
                           "increasing": increasing, "direction_matters": direction_matters,
                           "pass": good}
        c_ok = c_ok and good
    detail["c_discrimination"] = disc_rows

    return (a_ok and struct_eq and b_ok and c_ok), detail


def run_all():
    skel = _skeleton()
    res = {}
    res["J1_present_routing"] = check_j1(skel)
    res["J2_monotonic_amplitude"] = check_j2(skel)
    res["J3_interface_contract"] = check_j3(skel)
    res["J4_structural_signature"] = check_j4(skel)
    res["J5_regression_negative"] = check_j5(skel)
    overall = all(v[0] for v in res.values())
    return {"overall_pass": overall, "genre": GENRE,
            "tiers": GP.get(GENRE)["tiers"], "tier_step": BT.TIER_STEP,
            "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    report = run_all()
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"overall_pass": report["overall_pass"],
                          "tiers": report["tiers"], "tier_step": report["tier_step"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
