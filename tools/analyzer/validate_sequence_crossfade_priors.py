#!/usr/bin/env python3
"""candidate (L-8) 自我驗收閘 — **crossfade 序列軸整合進先驗庫**(prior-driven crossfade sequence,純 CPU,確定性)。

**補的缺口(L-7 的「下一步」/ honest boundary)**:candidate (L-6/L-7) 把序列接點 crossfade 機制做出來並
一般化成 per-junction,**但 `order` 與逐接點 `xf` 一直由各閘硬編**(FORWARD / VEC),從未像 (E)/(H)/(I)
把 beat 整合進先驗庫那樣,把**播放序列配方**整合進 `genre_priors`。本次把「播放哪些 beat、以何序、每接點
混多久」宣告進 `genre_priors.slot_bigwin["sequence"]`,並以 `genre_priors.sequence_recipe(prior)` 讀出,
使**大獎 crossfade 序列可完全由先驗庫驅動** —— 從**先驗庫 → 真實 build_spine robot 骨架 → build_animations
→ (先驗配方) → crossfade_sequence** 端到端,不再靠閘硬編 order/xf。

**crux / 本 run 的核心發現**:
  **先驗宣告的「播放順序 + 每接點混場秒數」(A 類手感)可被 L-7 的客觀機制如實實現** —— 先驗把 In→hit
  設 xf=0(保撞擊)、其餘接點 xf>0(平滑),經 `crossfade_sequence` 驅動後:In→hit 接點 kink **重現**為
  L-5 瞬切極限 `seam_velocity_gap`(≥ SEAM_KINK_MIN),其餘接點被 smoothstep 消成 0,`is_c1`=False。
  即:先驗只**宣告**要哪種手感,機制**逐接點**忠實落地 —— 把「選擇性平滑」從閘硬編上移到**先驗庫的可宣告配方**。

**選題理由(延續 (E)/(H)/(I) 整合先驗 + L 系列組合閘,不加新生成軸)**:L-8 **不是**新機制,是把 L-6/L-7
已驗的 crossfade 序列軸**整合進先驗庫**(如 beat 之於先驗)。`order`/`xf` 取值仍是**美術手感(A 類 PROPOSAL)**,
本閘只驗**機制 threading / 零回歸 / 選擇性平滑如實落地**,不驗美感;Award 真值僅 In/Loop/Out → 中段主秀
beat 同 beats 的 `prior_beats_unused`(誠實,覆蓋率不受擾,見 `validate_priors`)。

零回歸鐵則:(a) **先驗配方驅動 == 顯式參數驅動**(逐位元):`crossfade_sequence(anims, recipe.order,
recipe.xf, ramp=recipe.ramp)` == 以同值顯式呼叫;(b) **未宣告 sequence 的先驗** → `sequence_recipe`=None
(slot_reveal 等行為不變);(c) 先驗 `beats` 清單 / `classify_anim` / 覆蓋率不受 `sequence` 欄位影響
(additive,獨立命名空間)。

AC(客觀、可量測):
  R1 配方 present + well-formed + schema + 零回歸 : (a) slot_bigwin 有 `sequence`、`sequence_recipe` 回
                                        `{order,xf,ramp}`;order 非空、每 key ∈ 先驗 beat keys;xf 為 scalar 或
                                        長度==len(order)-1 列表、每值有限 ≥0;ramp 合法;(b) **additive**:
                                        `sequence` 不在任何 beat dict 內(獨立命名空間)、slot_reveal
                                        `sequence_recipe`=None;(c) **純函式**:改動回傳值不污染 PRIORS。
  R2 prior-driven end-to-end realizable : recipe.order 每個 beat key 皆由該先驗自身的 storyboard 經
                                        `build_animations` 產出(配方可由先驗自足實現,不需外部 beat);
                                        `crossfade_sequence(recipe)` 產合法 Spine timeline(finite / 嚴格遞增)、
                                        總時長 == Σdur − Σxf。
  R3 crux — 配方如實落地選擇性平滑       : 先驗 xf 的 **In→hit=0**(impact)、其餘 >0 →(a)In→hit 接點 kink
                                        **重現** == L-5 `sequence_seam_gaps` c1_gap(瞬切極限)且 ≥ SEAM_KINK_MIN;
                                        (b) 其餘接點 kink ≤ KINK_ZERO_TOL(被平滑);(c)`is_c1_crossfade_sequence`
                                        (配方)==False(留一瞬切即破全程 C1);(d) 把該 0 換成 XF 的「全平滑」
                                        覆寫 → `is_c1`==True(證破 C1 的正是先驗宣告保留的那個撞擊接點)。
  R4 配方忠實 == 顯式 + body 忠實       : (a) **逐位元**:`crossfade_sequence(anims, recipe.order, recipe.xf,
                                        ramp=recipe.ramp)` == 以同值顯式呼叫(配方是忠實宣告、不引入新行為);
                                        (b) **body 忠實**:emitted body 區取樣 vs 孤立 clip ≤ FAITH_TOL;
                                        (c) junction kinks(配方)== junction kinks(顯式)逐一相等。
  R5 守衛 + 負對照 + vacuity           : (a) **守衛**:malformed 配方(order 空 / 引用幻影 beat / xf 長度不符 /
                                        負 xf / 未知 ramp)→ `sequence_recipe` 於**讀取當下** ValueError;
                                        (b) **負對照**:未宣告 sequence 的先驗 → None(非 error,零回歸);
                                        (c) **vacuity**:xf 全零配方 → `crossfade_sequence` 委派 `compose_sequence`
                                        逐位元(無 crossfade),證「選擇性平滑」須至少一接點 xf>0 才有意義。

用法:
  python3 validate_sequence_crossfade_priors.py          # 摘要
  python3 validate_sequence_crossfade_priors.py --json   # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import genre_priors as GP
from analyze_target import analyze

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"

NSAMP = 16
XF = 0.15                 # 「全平滑」覆寫基準(與 L-6/L-7 同)
KINK_ZERO_TOL = 1e-6
SEAM_KINK_MIN = 10.0
VEL_TOL = 1.0
FAITH_TOL = 0.05


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/seq_xf_priors_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _recipe():
    return GP.sequence_recipe(GP.get(GENRE))


# ---------------- AC ----------------
def ac_R1():
    prior = GP.get(GENRE)
    r = _recipe()
    present = (prior.get("sequence") is not None) and isinstance(r, dict) and \
        set(r.keys()) == {"order", "xf", "ramp"}
    beat_keys = {b["key"] for b in prior["beats"]}
    order_ok = bool(r["order"]) and all(k in beat_keys for k in r["order"])
    njunc = len(r["order"]) - 1
    xf = r["xf"]
    import math
    if isinstance(xf, list):
        xf_ok = (len(xf) == njunc) and all(math.isfinite(v) and v >= 0 for v in xf)
    else:
        xf_ok = math.isfinite(float(xf)) and float(xf) >= 0
    ramp_ok = r["ramp"] in GP._RAMPS
    # (b) additive:sequence 不在任何 beat dict / slot_reveal 無配方
    seq_not_in_beats = all("sequence" not in b for b in prior["beats"])
    reveal_none = GP.sequence_recipe(GP.get("slot_reveal")) is None
    # (c) 純函式:改動回傳不污染 PRIORS
    r["order"].append("__SENTINEL__")
    if isinstance(r["xf"], list):
        r["xf"].append(999.0)
    r2 = _recipe()
    pure = ("__SENTINEL__" not in r2["order"]) and (r2 != r)
    ok = present and order_ok and xf_ok and ramp_ok and seq_not_in_beats and reveal_none and pure
    return {"pass": bool(ok), "present_wellformed": bool(present),
            "order_keys_in_beats": bool(order_ok), "xf_wellformed": bool(xf_ok),
            "ramp_valid": bool(ramp_ok), "sequence_not_in_beat_dicts": bool(seq_not_in_beats),
            "slot_reveal_recipe_none": bool(reveal_none), "recipe_pure_copy": bool(pure),
            "recipe": r2}


def ac_R2(anims):
    r = _recipe()
    realizable = all(k in anims for k in r["order"])
    comp, segs = G.crossfade_sequence(anims, r["order"], r["xf"], NSAMP, r["ramp"])
    wf = SA.all_finite(comp)
    total = SA.duration(comp)
    xfs, _ = G._normalize_xf(r["order"], r["xf"])
    exp_total = sum(SA.duration(anims[n]) for n in r["order"]) - sum(xfs)
    total_ok = abs(total - exp_total) <= 1e-6
    ok = realizable and wf and total_ok
    return {"pass": bool(ok), "all_beats_realizable_from_prior": bool(realizable),
            "well_formed_finite_strict_increasing": bool(wf),
            "total_dur": round(total, 6), "expected_total": round(exp_total, 6),
            "total_ok": bool(total_ok), "order": r["order"], "xf": xfs}


def ac_R3(anims):
    r = _recipe()
    order = r["order"]
    xfs, _ = G._normalize_xf(order, r["xf"])
    # 找先驗宣告為 impact(xf==0)的接點;配方語意:In->hit 保撞擊
    sharp = [i for i, v in enumerate(xfs) if v == 0.0]
    kinks = G.crossfade_junction_kinks(anims, order, r["xf"], r["ramp"])
    l5 = G.sequence_seam_gaps(anims, order, 1e-3)
    sharp_ok = True
    sharp_detail = {}
    for i in sharp:
        reappear = abs(kinks[i]["max"] - l5[i]["c1_gap"]) <= 1e-6
        big = kinks[i]["max"] >= SEAM_KINK_MIN
        sharp_detail[kinks[i]["seam"]] = {"kink": round(kinks[i]["max"], 4),
                                          "l5_c1_gap": round(l5[i]["c1_gap"], 4),
                                          "reappears": bool(reappear), "ge_min": bool(big)}
        sharp_ok = sharp_ok and reappear and big
    others_zero = all(k["max"] <= KINK_ZERO_TOL for i, k in enumerate(kinks) if i not in sharp)
    recipe_c1 = G.is_c1_crossfade_sequence(anims, order, r["xf"], r["ramp"], VEL_TOL)
    # (d) 把 impact 接點換成 XF 的「全平滑」覆寫 → is_c1 True
    allsmooth = list(xfs)
    for i in sharp:
        allsmooth[i] = XF
    allsmooth_c1 = G.is_c1_crossfade_sequence(anims, order, allsmooth, r["ramp"], VEL_TOL)
    ok = bool(sharp) and sharp_ok and others_zero and (not recipe_c1) and allsmooth_c1
    return {"pass": bool(ok), "impact_junctions": [kinks[i]["seam"] for i in sharp],
            "impact_kink_reappears_equals_l5": sharp_detail, "seam_kink_min": SEAM_KINK_MIN,
            "other_seams_smoothed_zero": bool(others_zero), "kink_zero_tol": KINK_ZERO_TOL,
            "is_c1_recipe_false": (not recipe_c1), "is_c1_all_smoothed_true": bool(allsmooth_c1),
            "per_seam_kink": {k["seam"]: round(k["max"], 6) for k in kinks}}


def ac_R4(anims):
    r = _recipe()
    # (a) 配方驅動 == 顯式參數驅動(逐位元)
    cr, sr = G.crossfade_sequence(anims, r["order"], r["xf"], NSAMP, r["ramp"])
    ce, se = G.crossfade_sequence(anims, list(r["order"]), list(r["xf"]) if isinstance(r["xf"], list) else r["xf"],
                                  NSAMP, r["ramp"])
    bit_identical = (json.dumps(cr, sort_keys=True) == json.dumps(ce, sort_keys=True)) and (sr == se)
    # (b) body 忠實
    offsets, durs, _ = G._crossfade_layout(anims, r["order"], r["xf"])
    xfs, _ = G._normalize_xf(r["order"], r["xf"])
    nj = len(r["order"]) - 1
    faith = 0.0
    for i, nm in enumerate(r["order"]):
        lo = offsets[i] + (xfs[i - 1] if i > 0 else 0.0)
        hi = offsets[i] + durs[i] - (xfs[i] if i < nj else 0.0)
        for frac in (0.3, 0.5, 0.7):
            t = lo + (hi - lo) * frac
            faith = max(faith, G._state_max_diff(SA.sample(cr, t), SA.sample(anims[nm], t - offsets[i])))
    faith_ok = faith <= FAITH_TOL
    # (c) junction kinks 配方 == 顯式
    kr = G.crossfade_junction_kinks(anims, r["order"], r["xf"], r["ramp"])
    ke = G.crossfade_junction_kinks(anims, list(r["order"]), xfs, r["ramp"])
    kink_eq = all(abs(a["max"] - b["max"]) <= 1e-12 for a, b in zip(kr, ke))
    ok = bit_identical and faith_ok and kink_eq
    return {"pass": bool(ok), "recipe_vs_explicit_bit_identical": bool(bit_identical),
            "body_faithful_maxerr": round(faith, 6), "faith_tol": FAITH_TOL,
            "body_faithful": bool(faith_ok), "junction_kinks_equal": bool(kink_eq)}


def ac_R5(anims):
    prior = GP.get(GENRE)
    beats = prior["beats"]
    guards = {}
    for seq, label in [
            ({"order": [], "crossfade_xf": 0.0}, "empty_order"),
            ({"order": ["In", "__phantom__"], "crossfade_xf": [0.1]}, "phantom_beat"),
            ({"order": ["In", "hit", "Out"], "crossfade_xf": [0.1]}, "wrong_xf_length"),
            ({"order": ["In", "hit"], "crossfade_xf": [-0.1]}, "neg_xf"),
            ({"order": ["In", "hit"], "crossfade_xf": [0.1], "ramp": "__zzz__"}, "bad_ramp")]:
        fake = {"beats": beats, "sequence": seq}
        try:
            GP.sequence_recipe(fake)
            guards[label] = False
        except ValueError:
            guards[label] = True
    guard_ok = all(guards.values())
    # (b) 負對照:未宣告 sequence → None(非 error)
    no_seq = GP.sequence_recipe({"beats": beats}) is None
    # (c) vacuity:xf 全零配方 → 委派 compose(逐位元)
    r = _recipe()
    nj = len(r["order"]) - 1
    cz, sz = G.crossfade_sequence(anims, r["order"], [0.0] * nj)
    cc, sc = G.compose_sequence(anims, r["order"])
    vac_ok = (json.dumps(cz, sort_keys=True) == json.dumps(cc, sort_keys=True)) and (sz == sc)
    ok = guard_ok and no_seq and vac_ok
    return {"pass": bool(ok), "input_guards": {"pass": bool(guard_ok), **guards},
            "no_sequence_returns_none": bool(no_seq),
            "zero_xf_delegates_to_compose_bit_identical": bool(vac_ok)}


def run():
    skel = _skeleton()
    spec = analyze(_psd(), GENRE)
    anims = G.build_animations(skel, spec["3_motion_storyboard"])
    r = _recipe()
    if r is None:
        return {"overall_pass": False, "error": "slot_bigwin 未宣告 sequence 配方"}
    missing = [nm for nm in r["order"] if nm not in anims]
    if missing:
        return {"overall_pass": False, "error": "missing beats in fixture: {}".format(missing),
                "available": sorted(anims.keys())}
    results = {"R1_recipe_present_wellformed_zero_regression": ac_R1(),
               "R2_prior_driven_end_to_end_realizable": ac_R2(anims),
               "R3_crux_selective_smoothing_realized": ac_R3(anims),
               "R4_recipe_faithful_vs_explicit_body": ac_R4(anims),
               "R5_guards_negctrl_vacuity": ac_R5(anims)}
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
        print("candidate (L-8) crossfade 序列軸整合進先驗庫 — genre_priors.sequence_recipe → crossfade_sequence")
        for k in ["R1_recipe_present_wellformed_zero_regression", "R2_prior_driven_end_to_end_realizable",
                  "R3_crux_selective_smoothing_realized", "R4_recipe_faithful_vs_explicit_body",
                  "R5_guards_negctrl_vacuity"]:
            v = res.get(k, {})
            print("  {:46s} {}".format(k, "PASS" if v.get("pass") else "FAIL"))
        if "error" in res:
            print("  ERROR:", res["error"])
        if "R1_recipe_present_wellformed_zero_regression" in res:
            p = res["R1_recipe_present_wellformed_zero_regression"]
            print("    recipe:", p.get("recipe"))
            print("    additive(sequence∉beats)={} reveal_none={} pure_copy={}".format(
                p["sequence_not_in_beat_dicts"], p["slot_reveal_recipe_none"], p["recipe_pure_copy"]))
        if "R2_prior_driven_end_to_end_realizable" in res:
            p = res["R2_prior_driven_end_to_end_realizable"]
            print("    realizable={} total {}=={} well_formed".format(
                p["all_beats_realizable_from_prior"], p["total_dur"], p["expected_total"]))
        if "R3_crux_selective_smoothing_realized" in res:
            p = res["R3_crux_selective_smoothing_realized"]
            print("    impact {} reappears==L5 | others_zero={} | is_c1 recipe_false={} all_smoothed_true={}".format(
                p["impact_junctions"], p["other_seams_smoothed_zero"],
                p["is_c1_recipe_false"], p["is_c1_all_smoothed_true"]))
            print("    per-seam kink:", p["per_seam_kink"])
        if "R4_recipe_faithful_vs_explicit_body" in res:
            p = res["R4_recipe_faithful_vs_explicit_body"]
            print("    recipe==explicit bit_identical={} | body_faithful={} ({}) | kinks_equal={}".format(
                p["recipe_vs_explicit_bit_identical"], p["body_faithful"],
                p["body_faithful_maxerr"], p["junction_kinks_equal"]))
        if "R5_guards_negctrl_vacuity" in res:
            p = res["R5_guards_negctrl_vacuity"]
            print("    guards {} | no_seq_none={} | zero_xf==compose={}".format(
                {k: v for k, v in p["input_guards"].items() if k != "pass"},
                p["no_sequence_returns_none"], p["zero_xf_delegates_to_compose_bit_identical"]))
        print("OVERALL:", "PASS" if res.get("overall_pass") else "FAIL")
    return 0 if res.get("overall_pass") else 1


if __name__ == "__main__":
    sys.exit(main())
