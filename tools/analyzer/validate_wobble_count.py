#!/usr/bin/env python3
"""candidate (G-4''') 自我驗收閘 — wobble 晃動「段數」隨檔位遞增(純 CPU)。

candidate (G-4'') 讓 wobble 的 shear **峰值**(幅度)隨檔位遞增(愈高檔位愈斜),但所有檔位的
wobble 仍是**同樣四擺**——「多斜」有了、「晃幾下」沒有。本閘驗 (G-4'''):wobble 的阻尼擺動
**極值數** = nseg **隨檔位嚴格遞增**(Super 4 → Mega 5 → Omg 6 → Legend 7),且此**結構**軸與
(G-4'') 的**幅度(shear 峰)**軸**正交可疊**、不破壞任何既有阻尼簽章/介面契約。

擺動段數是**結構**(gen 時決定極值數,非事後 amplify 能加出來,同 J-2 之於 combo)—— 故走
`tier_wobble_segs` 在 `build_animations` 對 wobble 檔位變體以該檔位 nseg **重生成**再套幅度增益。
真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
用負對照證鑑別力(閘可信)。從**先驗庫**經 `analyze_target`(build_storyboard)→ **真實 build_spine
robot 骨架** → `build_animations(..., tier_gains, tier_wobble_segs)` 端到端量,與 (J)/(G-4'') 同一 fixture。

  V1 present + backward-compat : 每檔位皆產 `wobble__{tier}` 且 finite/有 bone/帶 shear;base wobble 不變
                                (恆 nseg=4 → 4 極值、逐位元 == base);**且**不帶 `tier_wobble_segs`(=None)時
                                wobble 變體逐位元同 (G-4'') 幅度-only 輸出 → 證 (G-4''') 為**加性 opt-in**、零回歸。
  V2 count monotone (crux)    : 各檔位 wobble 的阻尼擺動極值**數** == 宣告 nseg 且 Super<Mega<Omg<Legend
                                **嚴格遞增**;每檔位變體內部仍相繼極值遞減(阻尼)。
  V3 interface+sig+amp kept   : 每檔位——首尾 shearX==0、繞 0 變號 ≥3、阻尼(極值遞減),且 shear **峰**仍
                                Super<Mega<Omg<Legend 單調(證與 (G-4'') 幅度軸疊加不衝突——段數變、峰仍隨檔位漲)。
  V4 orthogonality            : (a) segs + **平增益**(全 1.0)→ 段數仍遞增(擺數是**結構**,與幅度無關);
                                (b) gains + **無 segs**(None)→ 各檔位 wobble 段數**恆 4**、但 shear 峰遞增
                                → 兩軸可獨立開關(正交)。
  V5 neg-control              : (a) **平段數**(全 4)→ V2 段數單調性 FALSE(證閘在測遞增、非恆真);
                                (b) 無宣告 seg 的 genre(slot_reveal)→ `wobble_segs_for` 回 None
                                   → 不產 wobble 變體(gains None);
                                (c) **只有 wobble 吃 tier_wobble_segs**:同時帶 segs(tier_combo_hits=None)時,
                                   combo 的 impact 峰數在各檔位**恆 base**(wobble 段數不外洩到 combo)。

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
# 復用 G-4' 阻尼簽章判準 + cascade 的嚴格遞增 + more_beats 的 combo 峰數,確保跨閘一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_cascade import is_strictly_increasing
from validate_more_beats import series, impact_peaks

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


def _wobble_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "wobble"]


def _main_beats(anims):
    return {nm: G.beat_category(nm) for nm in anims
            if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


def _seg_count(anim):
    """該 anim 各 wobble bone 的阻尼擺動極值數(=非零 shearX 關鍵幀數)之最小值。

    首尾 shearX==0 → 只計中間極值;所有 wobble bone 由同一 nseg 驅動故一致,取 min 保守。"""
    counts = []
    for ch in anim.get("bones", {}).values():
        sx = _shear_x(ch)
        if sx:
            counts.append(sum(1 for v in sx if abs(v) > DEAD))
    return min(counts, default=0)


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _all_damped(anim):
    """該 anim 每個帶 shear 的 bone 皆首尾 0 + 變號≥3 + 極值遞減。"""
    got = False
    for ch in anim.get("bones", {}).values():
        sx = _shear_x(ch)
        if not sx:
            continue
        got = True
        if not (abs(sx[0]) < DEAD and abs(sx[-1]) < DEAD
                and _sign_changes_zero(sx) >= 3 and _extrema_mags_decreasing(sx)):
            return False
    return got


def _combo_min_peaks(anim):
    """該 anim 各 bone 的 impact 峰數最小值(供 V5c combo 隔離用)。"""
    bones = anim.get("bones", {})
    return min((len(impact_peaks(series(anim, b))) for b in bones), default=0)


def _combo_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "combo"]


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    segs = TV.wobble_segs_for(GENRE)

    base = G.build_animations(skel, sb)                                          # 無檔位
    amp_only = G.build_animations(skel, sb, tier_gains=gains)                     # (G-4'') 幅度-only
    full = G.build_animations(skel, sb, tier_gains=gains, tier_wobble_segs=segs)  # (G-4''') 幅度+段數

    wobble_beats = _wobble_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- V1 present + backward-compat ----
    v1 = {"missing": [], "not_finite": [], "no_bones": [], "no_shear": [],
          "base_changed": [], "amp_only_regressed": []}
    for wb in wobble_beats:
        for t in TIERS:
            vk = "{}__{}".format(wb, t)
            an = full.get(vk)
            if an is None:
                v1["missing"].append(vk); continue
            if not SA.all_finite(an):
                v1["not_finite"].append(vk)
            if not an.get("bones"):
                v1["no_bones"].append(vk)
            if not any(_shear_x(ch) for ch in an.get("bones", {}).values()):
                v1["no_shear"].append(vk)
    # base wobble 不變(恆 nseg=4 → 4 極值、逐位元 == base)
    for wb in wobble_beats:
        if _seg_count(full[wb]) != 4 or \
           json.dumps(base[wb], sort_keys=True) != json.dumps(full[wb], sort_keys=True):
            v1["base_changed"].append(wb)
    # tier_wobble_segs=None 時,wobble 變體逐位元同 (G-4'') 幅度-only(加性 opt-in)
    none_run = G.build_animations(skel, sb, tier_gains=gains, tier_wobble_segs=None)
    for wb in wobble_beats:
        for t in TIERS:
            vk = "{}__{}".format(wb, t)
            if json.dumps(none_run.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                v1["amp_only_regressed"].append(vk)
    R["V1_present_backward_compat"] = {"wobble_beats": wobble_beats, **v1,
                                       "pass": bool(wobble_beats) and not any(v1[k] for k in v1)}

    # ---- V2 count monotone (crux) ----
    v2 = {"beats": {}, "fail": []}
    expected = [segs[t] for t in TIERS]
    for wb in wobble_beats:
        counts = [_seg_count(full["{}__{}".format(wb, t)]) for t in TIERS]
        damped_each = all(_all_damped(full["{}__{}".format(wb, t)]) for t in TIERS)
        mono = is_strictly_increasing(counts)
        matches = (counts == expected)
        v2["beats"][wb] = {"counts": counts, "expected": expected,
                           "monotone": mono, "matches_declared": matches, "each_damped": damped_each}
        if not (mono and matches and damped_each):
            v2["fail"].append(wb)
    R["V2_count_monotone"] = {"tiers": TIERS, **v2, "pass": not v2["fail"] and bool(wobble_beats)}

    # ---- V3 interface + damped signature preserved + shear peak still monotone ----
    v3 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "peak_not_mono": []}
    for wb in wobble_beats:
        for t in TIERS:
            an = full["{}__{}".format(wb, t)]
            for ch in an.get("bones", {}).values():
                sx = _shear_x(ch)
                if not sx:
                    continue
                key = "{}__{}".format(wb, t)
                if not (abs(sx[0]) < DEAD and abs(sx[-1]) < DEAD):
                    v3["bad_endpoints"].append(key)
                if _sign_changes_zero(sx) < 3:
                    v3["few_sign_changes"].append(key)
                if not _extrema_mags_decreasing(sx):
                    v3["not_damped"].append(key)
        peaks = [_shear_peak(full["{}__{}".format(wb, t)]) for t in TIERS]
        if not is_strictly_increasing(peaks):
            v3["peak_not_mono"].append((wb, [round(p, 3) for p in peaks]))
    R["V3_interface_signature_amp"] = {**v3, "pass": not any(v3[k] for k in v3)}

    # ---- V4 orthogonality ----
    # (a) segs + 平增益 → 段數仍遞增(結構獨立於幅度)
    flat_gain = {t: 1.0 for t in TIERS}
    ca = G.build_animations(skel, sb, tier_gains=flat_gain, tier_wobble_segs=segs)
    counts_flatgain = {wb: [_seg_count(ca["{}__{}".format(wb, t)]) for t in TIERS] for wb in wobble_beats}
    a_ok = all(is_strictly_increasing(v) for v in counts_flatgain.values()) and bool(wobble_beats)
    # (b) gains + 無 segs → 段數恆 4、shear 峰遞增
    segs_gainonly = {wb: [_seg_count(amp_only["{}__{}".format(wb, t)]) for t in TIERS] for wb in wobble_beats}
    peak_gainonly = {wb: [_shear_peak(amp_only["{}__{}".format(wb, t)]) for t in TIERS] for wb in wobble_beats}
    b_ok = all(v == [4, 4, 4, 4] for v in segs_gainonly.values()) and \
        all(is_strictly_increasing(v) for v in peak_gainonly.values()) and bool(wobble_beats)
    R["V4_orthogonality"] = {
        "a_segs_with_flat_gain": counts_flatgain, "a_pass": a_ok,
        "b_gain_only_segs_fixed4": segs_gainonly, "b_pass": b_ok,
        "pass": a_ok and b_ok}

    # ---- V5 negative controls ----
    v5 = {}
    # (a) 平段數(全 4)→ 段數單調性 FALSE
    flat_segs = {t: 4 for t in TIERS}
    fs = G.build_animations(skel, sb, tier_gains=gains, tier_wobble_segs=flat_segs)
    any_mono_flat = any(is_strictly_increasing([_seg_count(fs["{}__{}".format(wb, t)]) for t in TIERS])
                        for wb in wobble_beats)
    v5["a_flat_segs_guard"] = {"any_count_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) 無宣告 seg 的 genre → wobble_segs_for None → 不產 wobble 變體(gains None)
    rv_segs = TV.wobble_segs_for("slot_reveal")
    rv_sb = _storyboard("slot_reveal")
    rv_gains = TV.gains_for("slot_reveal")
    rv_full = G.build_animations(skel, rv_sb, tier_gains=rv_gains, tier_wobble_segs=rv_segs)
    rv_wobble_variants = [k for k in rv_full if "__" in k and G.beat_category(k) == "wobble"]
    v5["b_no_seg_genre"] = {"wobble_segs_for_slot_reveal": rv_segs,
                            "wobble_variants": rv_wobble_variants,
                            "pass": rv_segs is None and not rv_wobble_variants}
    # (c) tier_wobble_segs 只作用於 wobble:同時帶 segs(tier_combo_hits=None)時,combo 峰數各檔位恆 base(3)
    seg_only = G.build_animations(skel, sb, tier_gains=gains, tier_wobble_segs=segs, tier_combo_hits=None)
    combo_beats = _combo_beats(base)
    combo_counts = {cb: [_combo_min_peaks(seg_only["{}__{}".format(cb, t)]) for t in TIERS] for cb in combo_beats}
    leak = [(cb, cnt) for cb, cnt in combo_counts.items() if len(set(cnt)) != 1]
    v5["c_seg_isolated_to_wobble"] = {"combo_counts_per_tier": combo_counts, "leaked": leak,
                                      "pass": bool(combo_beats) and not leak}
    R["V5_neg_control"] = {**v5, "pass": all(v["pass"] for v in v5.values())}

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
        for k in ["V1_present_backward_compat", "V2_count_monotone", "V3_interface_signature_amp",
                  "V4_orthogonality", "V5_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V2 wobble seg counts per tier {}:".format(TIERS))
        for wb, d in R["V2_count_monotone"]["beats"].items():
            print("  {:10s} segs {} (declared {})".format(wb, d["counts"], d["expected"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
