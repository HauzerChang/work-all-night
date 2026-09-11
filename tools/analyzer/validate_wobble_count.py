#!/usr/bin/env python3
"""candidate (G-4''') 自我驗收閘 — wobble 阻尼「擺動段數」隨檔位遞增(純 CPU)。

candidate (G-4'') 讓 wobble 的 shearX **峰**隨檔位放大(愈高檔位愈斜),但所有檔位的 wobble 仍是
**同樣四段**阻尼擺動 ——「多斜」有了、「晃幾下」沒有。本閘驗 (G-4'''):wobble 的阻尼**擺動段數**
= nswings **隨檔位嚴格遞增**(Super 4 → Mega 5 → Omg 6 → Legend 7),且此**結構**軸與 (G-4'')/(J)
的**幅度**軸**正交可疊**、不破壞阻尼振盪簽章與 setup identity 介面契約。

段「數」是關鍵幀**拓樸**(gen 時決定,事後 amplify 同比放大整條包絡只能改幅度、無法多長一段)——
故走 `tier_wobble_swings` 在 `build_animations` 對 wobble 檔位變體以該檔位 nswings **重生成**再套幅度
增益(同 J-2 對 combo nhits)。真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(先驗手感),
閘驗**客觀結構簽章非美感**;用負對照證鑑別力(閘可信)。

閘從**先驗庫**經 `analyze_target`(build_storyboard)→ **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains, tier_wobble_swings)` 端到端量,與 (G-4'') 閘同一 fixture。

  C1 present + backward-compat : 每檔位皆產 `wobble__{tier}` 且 finite/有 bone/≥1 bone 帶 shear/名仍
                                路由回 wobble;base wobble 不變(恆 nswings=4,逐位元同 base);
                                **且** 不帶 `tier_wobble_swings`(=None)時 wobble 變體逐位元同 (G-4'')
                                幅度-only 輸出 → 證 (G-4''') 為**加性 opt-in**、對 (G-4'') 零回歸。
  C2 swing count monotone(crux): 各檔位 wobble 的擺動**段數**(非零 shear 極值個數)== 宣告 nswings 且
                                Super<Mega<Omg<Legend **嚴格遞增**;每檔位變體內部相繼極值仍**嚴格遞減**
                                (阻尼);Super 段數 == base 段數(=4,向後相容)。
  C3 interface+signature kept : 每檔位——首尾 shearX==0(setup identity 介面)、繞 0 變號 ≥3、相繼極值
                                嚴格遞減(阻尼保形);且 shearX **峰**仍 Super<Mega<Omg<Legend 單調
                                (證與 (G-4'') 幅度軸疊加不衝突)。
  C4 orthogonality            : (a) swings + **平增益**(全 1.0)→ 段數仍遞增(段數是**結構**,與幅度無關)
                                且各檔位峰**相等**(幅度被關掉);(b) gains + **無 swings**(None)→ 各檔位
                                wobble 段數**恆 4**、但峰遞增 → 兩軸可獨立開關(正交)。
  C5 neg-control              : (a) **平段數**(全 4)→ C2 段數單調性 FALSE(證閘在測遞增、非恆真);
                                (b) 無宣告 swings 的 genre(slot_reveal)→ `wobble_swings_for` 回 None
                                   → 不產 wobble tier 變體(gains 亦 None);
                                (c) **只有 wobble 是 swing-count-aware**:同時帶 swings 時,非-wobble 主秀
                                   beat 在各檔位仍 0 bone 帶 shear(段數恆 0,不外洩到別的節拍)。

用法:
  python3 validate_wobble_count.py            # 摘要
  python3 validate_wobble_count.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze
import tier_variants as TV
# 復用 G-4' 的阻尼簽章判準,確保與 shear-gen / wobble-tier 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_cascade import is_strictly_increasing

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
DEAD = 1e-6


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/wobble_count_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _sheared(anim):
    """該 anim 各 bone 的 shearX 序列(只回真正帶 shear 的 bone)。"""
    return [sx for ch in anim.get("bones", {}).values() if (sx := _shear_x(ch))]


def _min_swings(anim):
    """擺動段數 = 各 sheared bone 的非零 shear 極值個數之最小值(所有件都至少晃這麼多段)。"""
    return min((sum(1 for v in sx if abs(v) > DEAD) for sx in _sheared(anim)), default=0)


def _peak(anim):
    """該 anim 全 bone 的峰 |shearX|(無 shear 回 0)。"""
    return max((max(abs(v) for v in sx) for sx in _sheared(anim)), default=0.0)


def _wobble_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "wobble"]


def _main_beats(anims):
    return {nm: G.beat_category(nm) for nm in anims
            if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    swings = TV.wobble_swings_for(GENRE)

    base = G.build_animations(skel, sb)                                          # 無檔位
    amp_only = G.build_animations(skel, sb, tier_gains=gains)                    # (G-4'') 幅度-only
    full = G.build_animations(skel, sb, tier_gains=gains, tier_wobble_swings=swings)  # (G-4''') 幅度+段數

    wobble_beats = _wobble_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- C1 present + backward-compat ----
    c1 = {"missing": [], "not_finite": [], "no_bones": [], "variant_no_shear": [],
          "misrouted": [], "base_changed": [], "amp_only_regressed": []}
    for wb in wobble_beats:
        for t in TIERS:
            vk = "{}__{}".format(wb, t)
            an = full.get(vk)
            if an is None:
                c1["missing"].append(vk); continue
            if not SA.all_finite(an):
                c1["not_finite"].append(vk)
            if not an.get("bones"):
                c1["no_bones"].append(vk)
            if not _sheared(an):
                c1["variant_no_shear"].append(vk)
            if G.beat_category(vk) != "wobble":
                c1["misrouted"].append((vk, G.beat_category(vk)))
    # base wobble 不變(恆 nswings=4,逐位元同 base)
    for wb in wobble_beats:
        if _min_swings(full[wb]) != 4 or \
           json.dumps(base[wb], sort_keys=True) != json.dumps(full[wb], sort_keys=True):
            c1["base_changed"].append(wb)
    # tier_wobble_swings=None 時,wobble 變體逐位元同 (G-4'') 幅度-only(加性 opt-in)
    none_run = G.build_animations(skel, sb, tier_gains=gains, tier_wobble_swings=None)
    for wb in wobble_beats:
        for t in TIERS:
            vk = "{}__{}".format(wb, t)
            if json.dumps(none_run.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                c1["amp_only_regressed"].append(vk)
    R["C1_present_backward_compat"] = {"wobble_beats": wobble_beats, **c1,
                                       "pass": bool(wobble_beats) and not any(c1[k] for k in c1)}

    # ---- C2 swing count monotone (crux) ----
    c2 = {"beats": {}, "fail": []}
    expected = [swings[t] for t in TIERS]
    for wb in wobble_beats:
        counts = [_min_swings(full["{}__{}".format(wb, t)]) for t in TIERS]
        damped_each = all(all(_extrema_mags_decreasing(sx) for sx in _sheared(full["{}__{}".format(wb, t)]))
                          for t in TIERS)
        base_count = _min_swings(base[wb])
        mono = is_strictly_increasing(counts)
        matches = (counts == expected)
        super_eq_base = (counts[0] == base_count)
        c2["beats"][wb] = {"counts": counts, "expected": expected, "base_count": base_count,
                           "monotone": mono, "matches_declared": matches,
                           "super_eq_base": super_eq_base, "each_damped": damped_each}
        if not (mono and matches and super_eq_base and damped_each):
            c2["fail"].append(wb)
    R["C2_swing_count_monotone"] = {"tiers": TIERS, **c2, "pass": not c2["fail"] and bool(wobble_beats)}

    # ---- C3 interface + damped signature preserved + peak still monotone ----
    c3 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "peak_not_mono": []}
    for wb in wobble_beats:
        for t in TIERS:
            an = full["{}__{}".format(wb, t)]
            for sx in _sheared(an):
                key = "{}__{}".format(wb, t)
                if not (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6):
                    c3["bad_endpoints"].append(key)
                if _sign_changes_zero(sx) < 3:
                    c3["few_sign_changes"].append(key)
                if not _extrema_mags_decreasing(sx):
                    c3["not_damped"].append(key)
        peaks = [_peak(full["{}__{}".format(wb, t)]) for t in TIERS]
        if not is_strictly_increasing(peaks):
            c3["peak_not_mono"].append((wb, [round(p, 3) for p in peaks]))
    R["C3_interface_signature"] = {**c3, "pass": not any(c3[k] for k in c3)}

    # ---- C4 orthogonality ----
    # (a) swings + 平增益 → 段數仍遞增(結構獨立於幅度)、各檔位峰相等(幅度關掉)
    flat_gain = {t: 1.0 for t in TIERS}
    ca = G.build_animations(skel, sb, tier_gains=flat_gain, tier_wobble_swings=swings)
    counts_flatgain = {wb: [_min_swings(ca["{}__{}".format(wb, t)]) for t in TIERS] for wb in wobble_beats}
    peaks_flatgain = {wb: [round(_peak(ca["{}__{}".format(wb, t)]), 4) for t in TIERS] for wb in wobble_beats}
    a_ok = (bool(wobble_beats)
            and all(is_strictly_increasing(v) for v in counts_flatgain.values())
            and all(len(set(v)) == 1 for v in peaks_flatgain.values()))   # 峰相等 → 幅度確被關掉
    # (b) gains + 無 swings → 段數恆 4、峰遞增
    swings_gainonly = {wb: [_min_swings(amp_only["{}__{}".format(wb, t)]) for t in TIERS] for wb in wobble_beats}
    peaks_gainonly = {wb: [_peak(amp_only["{}__{}".format(wb, t)]) for t in TIERS] for wb in wobble_beats}
    b_ok = (bool(wobble_beats)
            and all(v == [4, 4, 4, 4] for v in swings_gainonly.values())
            and all(is_strictly_increasing(v) for v in peaks_gainonly.values()))
    R["C4_orthogonality"] = {
        "a_swings_with_flat_gain": counts_flatgain, "a_peaks_flat": peaks_flatgain, "a_pass": a_ok,
        "b_gain_only_swings_fixed4": swings_gainonly, "b_pass": b_ok,
        "pass": a_ok and b_ok}

    # ---- C5 negative controls ----
    c5 = {}
    # (a) 平段數(全 4)→ 段數單調性 FALSE
    flat_swings = {t: 4 for t in TIERS}
    fs = G.build_animations(skel, sb, tier_gains=gains, tier_wobble_swings=flat_swings)
    any_mono_flat = any(is_strictly_increasing([_min_swings(fs["{}__{}".format(wb, t)]) for t in TIERS])
                        for wb in wobble_beats)
    c5["a_flat_swings_guard"] = {"any_count_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) 無宣告 swings 的 genre → wobble_swings_for None → 不產 wobble tier 變體
    rv_swings = TV.wobble_swings_for("slot_reveal")
    rv_sb = _storyboard("slot_reveal")
    rv_gains = TV.gains_for("slot_reveal")
    rv_full = G.build_animations(skel, rv_sb, tier_gains=rv_gains, tier_wobble_swings=rv_swings)
    rv_wobble_variants = [k for k in rv_full if "__" in k and G.beat_category(k) == "wobble"]
    c5["b_no_swings_genre"] = {"wobble_swings_for_slot_reveal": rv_swings,
                               "wobble_variants": rv_wobble_variants,
                               "pass": rv_swings is None and not rv_wobble_variants}
    # (c) swing-count 只作用於 wobble:非-wobble 主秀 beat 在各檔位仍 0 bone 帶 shear
    leak = []
    for beat, cat in main_beats.items():
        if cat == "wobble":
            continue
        sheared_counts = [len(_sheared(full["{}__{}".format(beat, t)])) for t in TIERS]
        if any(sheared_counts):        # 任何檔位帶 shear → 外洩
            leak.append((beat, cat, sheared_counts))
    c5["c_swing_isolated_to_wobble"] = {"leaked": leak, "pass": not leak}
    R["C5_neg_control"] = {**c5, "pass": all(v["pass"] for v in c5.values())}

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
        for k in ["C1_present_backward_compat", "C2_swing_count_monotone", "C3_interface_signature",
                  "C4_orthogonality", "C5_neg_control"]:
            print("{:28s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("C2 wobble swing counts per tier {}:".format(TIERS))
        for wb, d in R["C2_swing_count_monotone"]["beats"].items():
            print("  {:10s} swings {} (declared {}, base {})".format(
                wb, d["counts"], d["expected"], d["base_count"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
