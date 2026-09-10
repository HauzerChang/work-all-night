#!/usr/bin/env python3
"""candidate (G-4''') 自我驗收閘 — wobble 搖擺「段數」隨檔位遞增(純 CPU)。

candidate (G-4'') 讓 wobble 依檔位**幅度**差異化(shear 峰愈斜),但所有檔位仍是**同樣 4 段**阻尼
振盪 ——「更斜」有了、「晃幾下」沒有(同 (J)→(J-2) 對 combo 的「更爆」vs「連幾下」)。本閘驗
(G-4'''):wobble 的搖擺**段數** = nswing **隨檔位嚴格遞增**(Super 4 → Mega 5 → Omg 6 → Legend 7),
且此**結構**軸與 (G-4'') 的 shear **幅度**軸**正交可疊**、不破壞阻尼振盪簽章/介面契約。

段數是**結構**(gen 時決定極值段數,非事後 amplify 能加出來:amplify 只同比放大既有段)—— 故走
`tier_wobble_swings` 在 `build_animations` 對 wobble 檔位變體以該檔位 nswing **重生成**再套幅度增益。
真值界定同 (E/H/I/J/J-2/G-4'):主秀運動無唯一正解(先驗手感),閘驗**客觀結構簽章非美感**;
用負對照證鑑別力(閘可信)。從**先驗庫** → **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains, tier_wobble_swings)` 端到端量,與 (G-4'') 閘同一 fixture。

  N1 present + backward-compat : 每檔位皆產 `wobble__{tier}` 且 finite/有 bone/≥1 bone 帶 shear;
                                base wobble 不變(恆 nswing=4);**且** 不帶 `tier_wobble_swings`(=None)時
                                wobble 變體逐位元同 (G-4'') 幅度-only 輸出 → 證 (G-4''') 為**加性 opt-in**、
                                對 (G-4'') 零回歸。
  N2 swing count monotone (crux): 各檔位 wobble 的搖擺**段數**(非零 shear 極值數) == 宣告 nswing 且
                                Super<Mega<Omg<Legend **嚴格遞增**;每檔位變體仍阻尼振盪(變號≥3、遞減)。
  N3 signature + amplitude kept: 每檔位——首尾 shearX==0、繞 0 變號≥3、相繼極值嚴格遞減(阻尼),且
                                shear **峰幅度**仍 Super<Mega<Omg<Legend 單調(證與 (G-4'') 疊加不衝突)。
  N4 orthogonality            : (a) counts + **平增益**(全 1.0)→ 段數仍遞增(段數是**結構**,與幅度無關)
                                且各檔位 shear 峰 == base 峰(幅度軸關掉);
                                (b) gains + **無 counts**(None)→ 各檔位段數**恆 4**、但 shear 峰遞增
                                → 兩軸可獨立開關(正交)。
  N5 neg-control              : (a) **平段數**(全 4)→ N2 段數單調性 FALSE(證閘在測遞增、非恆真);
                                (b) 無宣告 swing 的 genre(slot_reveal)→ `wobble_swings_for` 回 None
                                   → 該 genre 無 tier 宣告(gains None)→ 不產任何 wobble 變體;
                                (c) **只有 wobble 是 swing-count-aware**:同時帶 wobble swings 時,combo 檔位
                                   變體的連擊峰數**不受影響**(仍由 tier_combo_hits 決定 → swing 不外洩到 combo)。

用法:
  python3 validate_wobble_swings.py            # 摘要
  python3 validate_wobble_swings.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
# 復用 G-4' 的阻尼簽章判準,確保與 shear-gen / wobble-tier 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_more_beats import series, impact_peaks
from validate_cascade import is_strictly_increasing

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
DEAD = 1e-6


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/wobble_swings_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _wobble_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "wobble"]


def _swing_count(anim):
    """該 anim 各帶 shear 的 bone 的**非零 shear 極值段數**之最小值(所有 wobble 件都至少晃這麼多段)。
    wobble 純 shearX、每個關鍵幀即一個極值段,故 = 非零 shearX 關鍵幀數。"""
    counts = []
    for ch in anim.get("bones", {}).values():
        sx = _shear_x(ch)
        if sx:
            counts.append(sum(1 for v in sx if abs(v) > DEAD))
    return min(counts, default=0)


def _shear_peak(anim):
    """該 anim 全 bone 的峰 |shearX|(無 shear 回 0)。"""
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _damped_ok(anim):
    """每個帶 shear 的 bone:首尾 0 + 繞 0 變號≥3 + 相繼極值遞減。"""
    seen = False
    for ch in anim.get("bones", {}).values():
        sx = _shear_x(ch)
        if not sx:
            continue
        seen = True
        if not (abs(sx[0]) < DEAD and abs(sx[-1]) < DEAD):
            return False
        if _sign_changes_zero(sx) < 3:
            return False
        if not _extrema_mags_decreasing(sx):
            return False
    return seen


def _combo_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "combo"]


def _min_impact_peaks(anim):
    bones = anim.get("bones", {})
    return min((len(impact_peaks(series(anim, b))) for b in bones), default=0)


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    swings = TV.wobble_swings_for(GENRE)
    hits = TV.combo_hits_for(GENRE)

    base = G.build_animations(skel, sb)                                          # 無檔位
    amp_only = G.build_animations(skel, sb, tier_gains=gains)                    # (G-4'') 幅度-only
    full = G.build_animations(skel, sb, tier_gains=gains, tier_wobble_swings=swings)  # (G-4''') 幅度+段數

    wobble_beats = _wobble_beats(base)
    R = {}

    # ---- N1 present + backward-compat ----
    n1 = {"missing": [], "not_finite": [], "no_bones": [], "variant_no_shear": [],
          "base_changed": [], "amp_only_regressed": []}
    for wb in wobble_beats:
        for t in TIERS:
            vk = "{}__{}".format(wb, t)
            an = full.get(vk)
            if an is None:
                n1["missing"].append(vk); continue
            if not SA.all_finite(an):
                n1["not_finite"].append(vk)
            if not an.get("bones"):
                n1["no_bones"].append(vk)
            if not any(_shear_x(ch) for ch in an.get("bones", {}).values()):
                n1["variant_no_shear"].append(vk)
    # base wobble 不變(恆 nswing=4)
    for wb in wobble_beats:
        if _swing_count(full[wb]) != 4 or \
           json.dumps(base[wb], sort_keys=True) != json.dumps(full[wb], sort_keys=True):
            n1["base_changed"].append(wb)
    # tier_wobble_swings=None 時,wobble 變體逐位元同 (G-4'') 幅度-only(加性 opt-in)
    none_run = G.build_animations(skel, sb, tier_gains=gains, tier_wobble_swings=None)
    for wb in wobble_beats:
        for t in TIERS:
            vk = "{}__{}".format(wb, t)
            if json.dumps(none_run.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                n1["amp_only_regressed"].append(vk)
    R["N1_present_backward_compat"] = {"wobble_beats": wobble_beats, **n1,
                                       "pass": bool(wobble_beats) and not any(n1[k] for k in n1)}

    # ---- N2 swing count monotone (crux) ----
    n2 = {"beats": {}, "fail": []}
    expected = [swings[t] for t in TIERS]
    for wb in wobble_beats:
        counts = [_swing_count(full["{}__{}".format(wb, t)]) for t in TIERS]
        damped_each = all(_damped_ok(full["{}__{}".format(wb, t)]) for t in TIERS)
        mono = is_strictly_increasing(counts)
        matches = (counts == expected)
        n2["beats"][wb] = {"swings": counts, "expected": expected,
                           "monotone": mono, "matches_declared": matches, "each_damped": damped_each}
        if not (mono and matches and damped_each):
            n2["fail"].append(wb)
    R["N2_swing_count_monotone"] = {"tiers": TIERS, **n2, "pass": not n2["fail"] and bool(wobble_beats)}

    # ---- N3 signature + amplitude preserved ----
    n3 = {"not_damped": [], "amp_not_mono": []}
    for wb in wobble_beats:
        for t in TIERS:
            if not _damped_ok(full["{}__{}".format(wb, t)]):
                n3["not_damped"].append("{}__{}".format(wb, t))
        peaks = [_shear_peak(full["{}__{}".format(wb, t)]) for t in TIERS]
        if not is_strictly_increasing(peaks):
            n3["amp_not_mono"].append((wb, [round(p, 3) for p in peaks]))
    R["N3_signature_amplitude"] = {**n3, "pass": not any(n3[k] for k in n3)}

    # ---- N4 orthogonality ----
    # (a) counts + 平增益 → 段數仍遞增(結構獨立於幅度)、shear 峰 == base 峰(幅度軸關掉)
    flat_gain = {t: 1.0 for t in TIERS}
    ca = G.build_animations(skel, sb, tier_gains=flat_gain, tier_wobble_swings=swings)
    counts_flatgain = {wb: [_swing_count(ca["{}__{}".format(wb, t)]) for t in TIERS] for wb in wobble_beats}
    peaks_flatgain = {wb: [round(_shear_peak(ca["{}__{}".format(wb, t)]), 3) for t in TIERS] for wb in wobble_beats}
    a_ok = (all(is_strictly_increasing(v) for v in counts_flatgain.values())
            and all(abs(p - _shear_peak(base[wb])) <= 1e-4 for wb in wobble_beats for p in peaks_flatgain[wb])
            and bool(wobble_beats))
    # (b) gains + 無 counts → 段數恆 4、shear 峰遞增
    cnt_gainonly = {wb: [_swing_count(amp_only["{}__{}".format(wb, t)]) for t in TIERS] for wb in wobble_beats}
    peak_gainonly = {wb: [_shear_peak(amp_only["{}__{}".format(wb, t)]) for t in TIERS] for wb in wobble_beats}
    b_ok = (all(v == [4, 4, 4, 4] for v in cnt_gainonly.values())
            and all(is_strictly_increasing(v) for v in peak_gainonly.values())
            and bool(wobble_beats))
    R["N4_orthogonality"] = {
        "a_counts_with_flat_gain": counts_flatgain, "a_peaks_eq_base": peaks_flatgain, "a_pass": a_ok,
        "b_gain_only_counts_fixed4": cnt_gainonly, "b_pass": b_ok,
        "pass": a_ok and b_ok}

    # ---- N5 negative controls ----
    n5 = {}
    # (a) 平段數(全 4)→ 段數單調性 FALSE
    flat_sw = {t: 4 for t in TIERS}
    fs = G.build_animations(skel, sb, tier_gains=gains, tier_wobble_swings=flat_sw)
    any_mono_flat = any(is_strictly_increasing([_swing_count(fs["{}__{}".format(wb, t)]) for t in TIERS])
                        for wb in wobble_beats)
    n5["a_flat_swings_guard"] = {"any_count_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) 無宣告 swing 的 genre(slot_reveal)→ wobble_swings_for None 且不產 wobble 變體
    rv_sw = TV.wobble_swings_for("slot_reveal")
    rv_sb = _storyboard("slot_reveal")
    rv_gains = TV.gains_for("slot_reveal")
    rv_full = G.build_animations(skel, rv_sb, tier_gains=rv_gains, tier_wobble_swings=rv_sw)
    rv_wobble_variants = [k for k in rv_full if "__" in k and G.beat_category(k) == "wobble"]
    n5["b_no_swing_genre"] = {"wobble_swings_for_slot_reveal": rv_sw,
                              "wobble_variants": rv_wobble_variants,
                              "pass": rv_sw is None and not rv_wobble_variants}
    # (c) swing 只作用於 wobble:同時帶 wobble swings + combo hits,combo 連擊峰數仍由 hits 決定(不受 swing 干擾)
    combo_beats = _combo_beats(base)
    both = G.build_animations(skel, sb, tier_gains=gains, tier_combo_hits=hits, tier_wobble_swings=swings)
    combo_only = G.build_animations(skel, sb, tier_gains=gains, tier_combo_hits=hits)
    combo_unaffected = all(
        json.dumps(both["{}__{}".format(cb, t)], sort_keys=True)
        == json.dumps(combo_only["{}__{}".format(cb, t)], sort_keys=True)
        for cb in combo_beats for t in TIERS)
    combo_counts = {cb: [_min_impact_peaks(both["{}__{}".format(cb, t)]) for t in TIERS] for cb in combo_beats}
    n5["c_swing_isolated_to_wobble"] = {"combo_variants_unaffected_by_swings": combo_unaffected,
                                        "combo_counts_still_from_hits": combo_counts,
                                        "pass": combo_unaffected and bool(combo_beats)
                                        and all(v == [hits[t] for t in TIERS] for v in combo_counts.values())}
    R["N5_neg_control"] = {**n5, "pass": all(v["pass"] for v in n5.values())}

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
        for k in ["N1_present_backward_compat", "N2_swing_count_monotone",
                  "N3_signature_amplitude", "N4_orthogonality", "N5_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("N2 wobble swing counts per tier {}:".format(TIERS))
        for wb, d in R["N2_swing_count_monotone"]["beats"].items():
            print("  {:10s} swings {} (declared {})".format(wb, d["swings"], d["expected"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
