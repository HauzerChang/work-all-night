#!/usr/bin/env python3
"""candidate (L-7) 自我驗收閘 — **per-junction(逐接點 / 選擇性 / 非對稱)crossfade**(純 CPU,確定性)。

**補的缺口(L-6 的「下一步」/ honest boundary)**:candidate (L-6) 的 `crossfade_sequence` 把接點 C1 kink
消掉了,**但 `xf` 是單一 scalar,所有接點套同一重疊秒數**。L-6 誠實列為未做的 honest boundary:
「**接點平滑的選擇性套用**(per-接點 xf / 只平滑特定接點)」—— 哪些接點要混、各給多長屬美術手感(A 類),
但「**可逐接點指定**」這個**機制**本身是客觀的。本次把 L-6 的 `xf` 由 scalar **一般化成 per-junction 列表**,
並以閘把關:機制正確、零回歸、且**選擇性平滑**(混部分接點、保留其餘瞬切撞擊)每接點各自正確。

**crux / 本 run 的核心發現**:
  **crossfade 的「平滑 / 不平滑」可以逐接點獨立決定** —— 某接點給 `xf=0` 即退化為**瞬切**(不混場),
  其接點 C1 kink **重現**為 L-5 的 `seam_velocity_gap`(瞬切極限);其餘 `xf>0` 接點仍被 smoothstep 消成 0。
  故「序列全程 C1」當且僅當**每個**接點都被平滑(任一接點留瞬切 → `is_c1_crossfade_sequence`=False)。
  這把 L-6 的「全有(全平滑)」擴成「可選擇性(混哪些)」—— 保留離散節拍撞擊感的接點與平滑過渡的接點可並存。

**選題理由(延續 L 系列整合 / 組合閘,不加新參數軸)**:L-7 **不是**新生成軸,而是把 L-6 **同一條 crossfade
重疊軸的取值**由「單一 scalar」一般化成「逐接點向量」(同 J-5→J-6 把方向軸由離散補成連續的精神)。機制
一般化 = 客觀;**取值(混哪些接點、各多長)仍是美術手感(A 類 PROPOSAL)**,本閘不替使用者決定。
從**先驗庫 → 真實 build_spine robot 骨架 → build_animations** 端到端,與 L / L-5 / L-6 同一 fixture。

一般化務必分清**含與不含**(零回歸鐵則):scalar `xf` **== 等值 per-junction 向量 `[xf]·(m−1)`**(逐位元),
`xf=0`(scalar 或全零向量)**委派 `compose_sequence`**(逐位元)。per-junction 的時間佈局守衛在均勻取值時
退化為 L-6 的 `xf ≤ min_dur/2` scalar 守衛。

AC(客觀、可量測):
  P1 present+well-formed+總時長+零回歸 : (a) **等值向量 ≡ scalar**:`crossfade_sequence([XF]·(m−1))` 逐位元 ==
                                        `crossfade_sequence(XF)`、junction kinks max 亦逐一相等;(b) **全零向量 ≡
                                        compose**:`crossfade_sequence([0]·(m−1))` 逐位元 == `compose_sequence`;
                                        (c) per-junction **相異向量 VEC** 產合法 Spine timeline(finite / 嚴格遞增)、
                                        總時長 == Σdur − ΣVEC、相鄰段區間相交 == **各自** VEC[i]。
  P2 crux — 選擇性平滑              : SEL = 全 XF 但第 SHARP 接點設 0 → (a) 其餘接點(xf>0)每接點 kink ≤
                                        KINK_ZERO_TOL(仍被平滑);(b) SHARP 接點 kink **重現** == L-5
                                        `sequence_seam_gaps` 的 c1_gap(瞬切極限)且 ≥ SEAM_KINK_MIN;(c)
                                        `is_c1_crossfade_sequence(SEL)`==False(留一瞬切即破全程 C1)**而** 全平滑
                                        `is_c1_crossfade_sequence([XF]·(m−1))`==True。
  P3 per-junction C1 + 線性負對照   : 相異向量 VEC,(a) **smoothstep** 每接點 kink ≤ KINK_ZERO_TOL(各接點不論自身
                                        xf 寬窄皆被消)、`is_c1`==True;(b) **linear**(負對照)每接點 kink ≥
                                        SEAM_KINK_MIN、`is_c1`==False → 證**消 kink 的是 C1 斜坡、非 per-junction 機制
                                        本身**(L-6 X4 的 per-junction 版)。
  P4 真混合 + body 忠實 + 非對稱     : 相異向量 VEC,(a) **每個**接點重疊中點姿勢與前 / 後 beat 單獨皆不同(≥
                                        BLEND_MIN)→ 各接點都真的在混合(非瞬切);(b) **body 區忠實**:非對稱鄰接下
                                        每 beat body 內部 emitted 取樣 vs 孤立 clip ≤ FAITH_TOL;(c) **非對稱**:VEC
                                        非均勻 → 總時長 ≠ 均勻 [XF] 總時長(逐接點寬窄真的改變佈局)。
  P5 metric 良定義 + 守衛 + 空驗     : (a) **閉式==數值**:非 XF 寬度(0.5)的 clean clip 對線性斜坡閉式
                                        `crossfade_seam_kink` == `crossfade_pose_at` 數值有限差分(rel < NUM_REL_TOL);
                                        (b) **守衛**:長度不符列表 → ValueError、負元素 → ValueError、per-beat
                                        三方重疊(左右重疊和 > 該 beat 時長)→ ValueError、全零向量不報錯(委派);
                                        (c) **空驗**:兩**靜止** clip 間 xf=0 接點 → `seam_velocity_gap`=0(無運動 →
                                        瞬切亦無 kink)→ 證「SHARP kink 重現」須配**非靜止**才有意義(呼應 L-5/L-6)。

用法:
  python3 validate_sequence_crossfade_selective.py          # 摘要
  python3 validate_sequence_crossfade_selective.py --json   # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"

XF = 0.15               # 均勻基準重疊(與 L-6 同;< 最短 beat Out=0.4 的一半 0.2)
NSAMP = 16
VEC = [0.1, 0.15, 0.2, 0.25, 0.3, 0.2]   # per-junction 相異重疊(6 接點;守衛:每 beat 左右和 ≤ 其時長)
SHARP = 0               # 選擇性測試:留第 SHARP 接點(In->hit)瞬切(其 L-5 gap≈114),其餘平滑
KINK_ZERO_TOL = 1e-6
SEAM_KINK_MIN = 10.0
VEL_TOL = 1.0
FAITH_TOL = 0.05
BLEND_MIN = 0.3
MOTION_VEL_THR = 1.0
NUM_REL_TOL = 1e-3

FORWARD = ["In", "hit", "combo", "charge", "cascade", "Loop", "Out"]
NJ = len(FORWARD) - 1


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/seq_xf_sel_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _static(dur=2.0):
    return {"bones": {"b_身體": {"rotate": [{"time": 0.0, "angle": 0.0}, {"time": dur, "angle": 0.0}]}}}


# ---------------- AC ----------------
def ac_P1(anims):
    # (a) 等值向量 ≡ scalar(逐位元)
    cs, ss = G.crossfade_sequence(anims, FORWARD, XF, NSAMP, "smoothstep")
    cv, sv = G.crossfade_sequence(anims, FORWARD, [XF] * NJ, NSAMP, "smoothstep")
    uni_emit = (json.dumps(cs, sort_keys=True) == json.dumps(cv, sort_keys=True)) and (ss == sv)
    ks = G.crossfade_junction_kinks(anims, FORWARD, XF, "smoothstep")
    kv = G.crossfade_junction_kinks(anims, FORWARD, [XF] * NJ, "smoothstep")
    uni_kink = all(abs(a["max"] - b["max"]) <= 1e-12 for a, b in zip(ks, kv))
    # (b) 全零向量 ≡ compose
    cz, sz = G.crossfade_sequence(anims, FORWARD, [0.0] * NJ)
    cc, sc = G.compose_sequence(anims, FORWARD)
    zero_emit = (json.dumps(cz, sort_keys=True) == json.dumps(cc, sort_keys=True)) and (sz == sc)
    # (c) 相異向量 VEC well-formed + 總時長 + 段相交 == VEC[i]
    comp, segs = G.crossfade_sequence(anims, FORWARD, VEC, NSAMP, "smoothstep")
    wf = SA.all_finite(comp)
    total = SA.duration(comp)
    exp_total = sum(SA.duration(anims[n]) for n in FORWARD) - sum(VEC)
    total_ok = abs(total - exp_total) <= 1e-6
    seg_ok = all(abs((segs[i]["start"] + segs[i]["dur"]) - (segs[i + 1]["start"] + VEC[i])) <= 1e-6
                 for i in range(NJ))
    ok = uni_emit and uni_kink and zero_emit and wf and total_ok and seg_ok
    return {"pass": bool(ok), "uniform_vec_bit_identical_to_scalar": bool(uni_emit),
            "uniform_vec_kinks_equal_scalar": bool(uni_kink),
            "zero_vec_bit_identical_to_compose": bool(zero_emit),
            "well_formed_finite_strict_increasing": bool(wf),
            "total_dur": round(total, 6), "expected_total": round(exp_total, 6), "total_ok": bool(total_ok),
            "segments_overlap_by_per_junction_xf": bool(seg_ok)}


def ac_P2(anims):
    sel = [XF] * NJ
    sel[SHARP] = 0.0
    kinks = G.crossfade_junction_kinks(anims, FORWARD, sel, "smoothstep")
    others_zero = all(k["max"] <= KINK_ZERO_TOL for i, k in enumerate(kinks) if i != SHARP)
    l5 = G.sequence_seam_gaps(anims, FORWARD, 1e-3)[SHARP]["c1_gap"]
    sharp_k = kinks[SHARP]["max"]
    sharp_reappears = (abs(sharp_k - l5) <= 1e-6) and (sharp_k >= SEAM_KINK_MIN)
    sel_c1 = G.is_c1_crossfade_sequence(anims, FORWARD, sel, "smoothstep", VEL_TOL)
    all_c1 = G.is_c1_crossfade_sequence(anims, FORWARD, [XF] * NJ, "smoothstep", VEL_TOL)
    ok = others_zero and sharp_reappears and (not sel_c1) and all_c1
    return {"pass": bool(ok), "sharp_seam": kinks[SHARP]["seam"],
            "other_seams_smoothed_zero": bool(others_zero), "kink_zero_tol": KINK_ZERO_TOL,
            "sharp_kink": round(sharp_k, 4), "l5_concat_c1_gap": round(l5, 4),
            "sharp_kink_reappears_equals_l5": bool(sharp_reappears), "seam_kink_min": SEAM_KINK_MIN,
            "is_c1_selective_false": (not sel_c1), "is_c1_all_smoothed_true": bool(all_c1),
            "per_seam_kink": {k["seam"]: round(k["max"], 6) for k in kinks}}


def ac_P3(anims):
    ks = G.crossfade_junction_kinks(anims, FORWARD, VEC, "smoothstep")
    smooth_zero = all(k["max"] <= KINK_ZERO_TOL for k in ks)
    kl = G.crossfade_junction_kinks(anims, FORWARD, VEC, "linear")
    lin_kink = all(k["max"] >= SEAM_KINK_MIN for k in kl)
    smooth_c1 = G.is_c1_crossfade_sequence(anims, FORWARD, VEC, "smoothstep", VEL_TOL)
    lin_c1 = G.is_c1_crossfade_sequence(anims, FORWARD, VEC, "linear", VEL_TOL)
    ok = smooth_zero and lin_kink and smooth_c1 and (not lin_c1)
    return {"pass": bool(ok), "distinct_xf": VEC,
            "smoothstep_all_kinks_zero": bool(smooth_zero), "smoothstep_is_c1": bool(smooth_c1),
            "linear_all_kinks_ge_min": bool(lin_kink), "linear_is_c1_false": (not lin_c1),
            "smoothstep_kinks": {k["seam"]: round(k["max"], 9) for k in ks},
            "linear_kinks": {k["seam"]: round(k["max"], 3) for k in kl}}


def ac_P4(anims):
    offsets, durs, total = G._crossfade_layout(anims, FORWARD, VEC)
    # (a) 每個接點真混合
    blends = {}
    blend_ok = True
    for i in range(NJ):
        T = offsets[i + 1] + VEC[i] * 0.5
        mix = G.crossfade_pose_at(anims, FORWARD, VEC, T, "smoothstep")
        da = G._state_max_diff(mix, SA.sample(anims[FORWARD[i]], T - offsets[i]))
        db = G._state_max_diff(mix, SA.sample(anims[FORWARD[i + 1]], T - offsets[i + 1]))
        blends["{}->{}".format(FORWARD[i], FORWARD[i + 1])] = {"da": round(da, 3), "db": round(db, 3)}
        if min(da, db) < BLEND_MIN:
            blend_ok = False
    # (b) body 忠實(非對稱鄰接)
    comp, _ = G.crossfade_sequence(anims, FORWARD, VEC, NSAMP, "smoothstep")
    faith = 0.0
    for i, nm in enumerate(FORWARD):
        lo = offsets[i] + (VEC[i - 1] if i > 0 else 0.0)
        hi = offsets[i] + durs[i] - (VEC[i] if i < NJ else 0.0)
        for frac in (0.3, 0.5, 0.7):
            t = lo + (hi - lo) * frac
            faith = max(faith, G._state_max_diff(SA.sample(comp, t), SA.sample(anims[nm], t - offsets[i])))
    faith_ok = faith <= FAITH_TOL
    # (c) 非對稱:VEC 總時長 ≠ 均勻 [XF] 總時長
    uni_total = sum(SA.duration(anims[n]) for n in FORWARD) - NJ * XF
    asym_ok = abs(total - uni_total) > 1e-6
    ok = blend_ok and faith_ok and asym_ok
    return {"pass": bool(ok), "real_blend_each_junction": bool(blend_ok), "blend_min": BLEND_MIN,
            "blends": blends, "body_faithful_maxerr": round(faith, 6), "faith_tol": FAITH_TOL,
            "body_faithful": bool(faith_ok), "vec_total": round(total, 6),
            "uniform_total": round(uni_total, 6), "asymmetric_changes_layout": bool(asym_ok)}


def ac_P5(anims):
    # (a) 閉式 == 數值(非 XF 寬度 0.5 的 clean clip 對,線性斜坡)
    A = {"bones": {"b": {"rotate": [{"time": 0.0, "angle": 0.0}, {"time": 1.0, "angle": 10.0}]}}}
    B = {"bones": {"b": {"rotate": [{"time": 0.0, "angle": 0.0}, {"time": 1.0, "angle": -20.0}]}}}
    syn = {"a": A, "b": B}
    xf = 0.5
    closed = G.crossfade_seam_kink(A, B, xf, "linear")

    def _num_kink(h=1e-5):
        offs, durs, _ = G._crossfade_layout(syn, ["a", "b"], [xf])   # per-junction 列表路徑
        end = offs[0] + durs[0]

        def onesided(T, hh):
            s0 = G.crossfade_pose_at(syn, ["a", "b"], [xf], T, "linear")
            s1 = G.crossfade_pose_at(syn, ["a", "b"], [xf], T + hh, "linear")
            return (s1["bones"]["b"]["rotate"] - s0["bones"]["b"]["rotate"]) / hh
        return (abs(onesided(end - xf, -h) - onesided(end - xf, h)),
                abs(onesided(end, -h) - onesided(end, h)))
    nl, nr = _num_kink()
    rel_l = abs(closed["left"] - nl) / closed["left"] if closed["left"] > 1e-9 else 0.0
    rel_r = abs(closed["right"] - nr) / closed["right"] if closed["right"] > 1e-9 else 0.0
    closed_num_ok = (rel_l < NUM_REL_TOL) and (rel_r < NUM_REL_TOL)
    # (b) 輸入守衛
    guards = {}
    for spec, label in [([XF] * (NJ - 1), "wrong_length"),
                        ([XF, -0.1] + [XF] * (NJ - 2), "neg_element"),
                        ([0.3, 0.3] + [XF] * (NJ - 2), "triple_overlap")]:
        try:
            G.crossfade_sequence(anims, FORWARD, spec)
            guards[label] = False
        except ValueError:
            guards[label] = True
    try:
        G.crossfade_sequence(anims, FORWARD, [0.0] * NJ)   # 全零 → 委派不報錯
        guards["zero_vec_delegates"] = True
    except Exception:
        guards["zero_vec_delegates"] = False
    guard_ok = all(guards.values())
    # (c) 空驗:兩靜止 clip 間 xf=0 接點 → seam_velocity_gap=0(無運動)
    st = {"a": _static(), "b": _static()}
    k0 = G.crossfade_junction_kinks(st, ["a", "b"], [0.0], "smoothstep")[0]["max"]
    vac_ok = k0 <= 1e-9
    ok = closed_num_ok and guard_ok and vac_ok
    return {"pass": bool(ok),
            "closed_vs_numerical": {"pass": bool(closed_num_ok), "closed_left": round(closed["left"], 4),
                                    "closed_right": round(closed["right"], 4), "num_left": round(nl, 4),
                                    "num_right": round(nr, 4), "rel_l": round(rel_l, 6), "rel_r": round(rel_r, 6)},
            "input_guards": {"pass": bool(guard_ok), **guards},
            "static_vacuity": {"pass": bool(vac_ok), "static_zero_junction_kink": round(k0, 9)}}


def run():
    skel = _skeleton()
    spec = analyze(_psd(), GENRE)
    anims = G.build_animations(skel, spec["3_motion_storyboard"])
    missing = [nm for nm in FORWARD if nm not in anims]
    if missing:
        return {"overall_pass": False, "error": "missing beats in fixture: {}".format(missing),
                "available": sorted(anims.keys())}
    results = {"P1_present_wellformed_total_zero_regression": ac_P1(anims),
               "P2_crux_selective_smoothing": ac_P2(anims),
               "P3_per_junction_C1_linear_negctrl": ac_P3(anims),
               "P4_real_blend_body_faithful_asymmetric": ac_P4(anims),
               "P5_metric_welldefined_guards_vacuity": ac_P5(anims)}
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
        print("candidate (L-7) per-junction(選擇性 / 非對稱)crossfade 序列閘 — _normalize_xf + 逐接點 xf")
        for k in ["P1_present_wellformed_total_zero_regression", "P2_crux_selective_smoothing",
                  "P3_per_junction_C1_linear_negctrl", "P4_real_blend_body_faithful_asymmetric",
                  "P5_metric_welldefined_guards_vacuity"]:
            v = res.get(k, {})
            print("  {:44s} {}".format(k, "PASS" if v.get("pass") else "FAIL"))
        if "error" in res:
            print("  ERROR:", res["error"])
        if "P1_present_wellformed_total_zero_regression" in res:
            p = res["P1_present_wellformed_total_zero_regression"]
            print("    uniform-vec==scalar={} | zero-vec==compose={} | total {}=={} seg_overlap={}".format(
                p["uniform_vec_bit_identical_to_scalar"], p["zero_vec_bit_identical_to_compose"],
                p["total_dur"], p["expected_total"], p["segments_overlap_by_per_junction_xf"]))
        if "P2_crux_selective_smoothing" in res:
            p = res["P2_crux_selective_smoothing"]
            print("    sharp {} kink={} ==L5 {} | others_zero={} | is_c1 selective_false={} all_smoothed={}".format(
                p["sharp_seam"], p["sharp_kink"], p["l5_concat_c1_gap"], p["other_seams_smoothed_zero"],
                p["is_c1_selective_false"], p["is_c1_all_smoothed_true"]))
            print("    per-seam kink:", p["per_seam_kink"])
        if "P3_per_junction_C1_linear_negctrl" in res:
            p = res["P3_per_junction_C1_linear_negctrl"]
            print("    smoothstep all-zero={} is_c1={} | linear all>=min={} is_c1_false={}".format(
                p["smoothstep_all_kinks_zero"], p["smoothstep_is_c1"],
                p["linear_all_kinks_ge_min"], p["linear_is_c1_false"]))
            print("    linear kinks:", p["linear_kinks"])
        if "P4_real_blend_body_faithful_asymmetric" in res:
            p = res["P4_real_blend_body_faithful_asymmetric"]
            print("    real_blend={} body_faithful={} ({}) | asymmetric total {} vs uniform {}".format(
                p["real_blend_each_junction"], p["body_faithful"], p["body_faithful_maxerr"],
                p["vec_total"], p["uniform_total"]))
        if "P5_metric_welldefined_guards_vacuity" in res:
            p = res["P5_metric_welldefined_guards_vacuity"]
            print("    closed==numerical L {}/{} R {}/{} | guards {} | static zero-junction kink={}".format(
                p["closed_vs_numerical"]["closed_left"], p["closed_vs_numerical"]["num_left"],
                p["closed_vs_numerical"]["closed_right"], p["closed_vs_numerical"]["num_right"],
                {k: v for k, v in p["input_guards"].items() if k != "pass"},
                p["static_vacuity"]["static_zero_junction_kink"]))
        print("OVERALL:", "PASS" if res.get("overall_pass") else "FAIL")
    return 0 if res.get("overall_pass") else 1


if __name__ == "__main__":
    sys.exit(main())
