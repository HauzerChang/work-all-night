#!/usr/bin/env python3
"""candidate (M) 自我驗收閘 — 跨 beat **混場 (crossfade / overlap-mix)** 接點機制(純 CPU,確定性)。

**補的缺口(L-4 誠實列出的 honest boundary)**:candidate (L) 的 `compose_sequence` 把 beat **純時間平移
+ 接點去重**串成序列 —— 任一時刻輸出**恰等於某一支 clip**(平移後),**從不產生兩支 clip 的混合**。真實
大獎序列常需「前一拍還沒收完、後一拍已經起」:兩拍在一段**時間重疊窗**內**同時作用**、以權重交叉淡入淡出
(Spine runtime 的 track mix)。這無法用平移+去重做到(去重要求接點值相等才無損;值不等被抹成陡坡,見 L-3),
**需要真正的 mix 機制**。本次新增 `gen_animations.crossfade_pair`(+`crossfade_sequence` fold)在重疊窗內
**同步取樣兩支 clip 並做凸組合** `out=(1-w)·A+w·B`,並以閘把關其客觀不變量。

**crux / 本 run 的核心鑑別(M3)**:crossfade 在重疊窗內可達「**兩支 clip 當下都不在**」的中間態(≈0.5A+0.5B);
compose 的平移+去重**永遠做不到**(任一時刻 = 某一支 clip 的值)。在**同一對 beat、同一絕對時間**上同時量
crossfade 與 compose 對「兩支 clip 當下狀態」的最小距離(mix depth):crossfade 達 ≥DEPTH_MIN、compose ≈0 →
證本機制是 compose **做不到**的新組合層軸,而非換皮。第二 crux(M5a):**窗→0 連續退化回 compose 的 C0 拼接**
(crossfade 是 concat 的推廣),證兩者同源、crossfade 嚴格更一般。

**選題理由(延續 L/L-2/L-3/L-4 的整合/組合閘,不加參數軸)**:crossfade 的新客觀不變量 = 「重疊窗凸組合」,
compose 的接點閘涵蓋不到。從**先驗庫 → 真實 build_spine robot 骨架 → build_animations** 端到端,與 L/L-3/L-4
同一 fixture(hit×combo)。

真值界定:重疊窗長 `window`、權重曲線(linear/smooth)屬**美術手感(A 類)**;但「端點精確(窗首==A、
窗尾==B)」「單位分解(窗內兩拍一致 ⇒ 不失真)」「凸性/有界(無 overshoot)」「混場深度 compose 做不到」
「窗→0 退化回 concat」皆**客觀可量測**。負對照(① 兩支相同靜止 hold 混場殘差=0 的 partition-of-unity 守衛
② 窗內逐 knot 凸性無越界 ③ 窗→0 == compose)證閘有鑑別力、機制無失真。

AC(客觀、可量測):
  M1 present+structure       : `crossfade_pair(hit,combo,W)` 產單一可載入 clip;`total==durA+durB−W`、
                               `overlap==[durA−W,durA]`、`all_finite`、bones 齊 → 機制產出合法。
  M2 crux — 端點精確+非空驗   : 窗首 cf(offsetB)==A(offsetB)、窗尾 cf(durA)==B(window)(bone <TOL_BONE、
                               含 alpha <TOL_ENDPT 的 8-bit 量化容忍);**中點** cf==0.5·A+0.5·B(混場公式忠實
                               烘進 keyframe);非空驗:中點 |A−B|≥MIX_THR(確實在混、非兩拍恰好重合)。
  M3 crux — 混場深度 compose 做不到 : 重疊窗格點上,crossfade 對「{A(t),B(t−offsetB)}」的最小距離(mix depth)
                               max ≥ DEPTH_MIN(達兩拍都不在的中間態);而 `compose_sequence([hit,combo])` 在
                               **同一絕對時間**的 mix depth ≤ COMPOSE_DEPTH_MAX(≈0,恆等於某一支 clip)。
  M4 faithful outside overlap: 窗外逐位元沿用原 clip 幀 → A 內部 knot(time<offsetB)cf==A、B 內部 knot
                               (B-time>window,右移 offsetB)cf==B,殘差 <FAITH_TOL(只動重疊窗)。
  M5 neg-control+守衛         : (a) **crux 窗→0 連續退化**:cf(W) vs `compose_sequence([hit,combo])` 的 sup-dist
                               **線性於 W**(窗外純-B 段較 concat 右移恰 W → sup=接點速度·W;三小窗斜率恆定、
                               隨 W 遞減)→ W→0 時 →0,concat = 零窗 crossfade;
                               (b) **partition-of-unity 守衛**:兩支**相同靜止 hold**(恆 P)混場 → 窗內 cf==P
                               殘差 ≈0(若權重非和=1,如相加,會得 2P)→ 證凸組合;
                               (c) **凸性守衛**:窗內逐 knot 每通道 cf∈[min(A,B),max(A,B)] 無越界(違規數==0)。

用法:
  python3 validate_sequence_crossfade.py            # 摘要
  python3 validate_sequence_crossfade.py --json     # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"

W = 0.3                 # 重疊窗(≤ min(dur_hit=0.5, dur_combo=0.9))
TOL_BONE = 1e-4         # bone 通道端點精確上限
TOL_ENDPT = 0.01        # 含 alpha 的端點容忍(slot color 8-bit 量化 ≈1/255)
MIX_THR = 1.0           # 中點 |A−B| 非空驗下限(實測 ≈8.3)
DEPTH_MIN = 1.0         # crossfade mix depth 須達(實測中點 ≈4.2)
COMPOSE_DEPTH_MAX = 1e-6  # compose mix depth 上限(恆等某 clip → ≈0)
FAITH_TOL = 1e-6        # 窗外忠實度上限(逐位元沿用原幀)
CONVEX_EPS = 1e-4       # 凸性越界容忍(6-digit round + 8-bit 量化)


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/seq_crossfade_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


# ---------------- 量測器 ----------------
def _blend_state(sA, sB, w):
    """兩個 sample() 狀態的凸組合(1-w)·A+w·B(含 shear + alpha;缺席 part 以 setup identity 補)。"""
    bones = {}
    for p in set(sA["bones"]) | set(sB["bones"]):
        da = sA["bones"].get(p, G._LOOP_IDENT)
        db = sB["bones"].get(p, G._LOOP_IDENT)
        bones[p] = {k: (1.0 - w) * da.get(k, G._LOOP_IDENT[k]) + w * db.get(k, G._LOOP_IDENT[k])
                    for k in G._LOOP_IDENT}
    slots = {}
    for s in set(sA["slots"]) | set(sB["slots"]):
        aa = sA["slots"].get(s, {"alpha": 1.0})["alpha"]
        ab = sB["slots"].get(s, {"alpha": 1.0})["alpha"]
        slots[s] = {"alpha": (1.0 - w) * aa + w * ab}
    return {"bones": bones, "slots": slots}


def _bone_only_diff(s1, s2):
    """只比 bone 通道的最大絕對差(排除 alpha 的 8-bit 量化,用於端點 bone 精確度)。"""
    m = 0.0
    for b in set(s1["bones"]) | set(s2["bones"]):
        d1 = s1["bones"].get(b, G._LOOP_IDENT)
        d2 = s2["bones"].get(b, G._LOOP_IDENT)
        for k in G._LOOP_IDENT:
            m = max(m, abs(d1.get(k, G._LOOP_IDENT[k]) - d2.get(k, G._LOOP_IDENT[k])))
    return m


def _interior_knot_times(clip, lo, hi):
    """clip 中落在 (lo,hi) 開區間內的所有 keyframe 時間(去重排序),供忠實度逐 knot 複驗。"""
    ts = set()
    for group in ("bones", "slots"):
        for chans in clip.get(group, {}).values():
            for tl in chans.values():
                for f in tl:
                    if lo + 1e-9 < f["time"] < hi - 1e-9:
                        ts.add(round(f["time"], 6))
    return sorted(ts)


def _static_hold(pose_deg=20.0, dur=1.0):
    """恆定姿勢 hold(rotate==pose_deg 不變):兩支相同時,混場任一 w 皆應回同一 pose(partition-of-unity 守衛)。"""
    return {"bones": {"b_身體": {"rotate": [{"time": 0.0, "angle": pose_deg},
                                            {"time": dur, "angle": pose_deg}]}}}


# ---------------- AC ----------------
def ac_M1(anims):
    A, B = anims["hit"], anims["combo"]
    cf, info = G.crossfade_pair(A, B, W)
    durA, durB = SA.duration(A), SA.duration(B)
    total_ok = abs(info["total"] - (durA + durB - W)) <= 1e-6
    overlap_ok = (abs(info["overlap"][0] - (durA - W)) <= 1e-6 and
                  abs(info["overlap"][1] - durA) <= 1e-6)
    dur_ok = abs(SA.duration(cf) - (durA + durB - W)) <= 1e-6
    finite = SA.all_finite(cf)
    bones_ok = len(cf.get("bones", {})) >= 3
    ok = total_ok and overlap_ok and dur_ok and finite and bones_ok
    return {"pass": bool(ok), "info": info, "cf_duration": round(SA.duration(cf), 6),
            "total_ok": bool(total_ok), "overlap_ok": bool(overlap_ok), "dur_ok": bool(dur_ok),
            "all_finite": bool(finite), "n_bones": len(cf.get("bones", {}))}


def ac_M2(anims):
    A, B = anims["hit"], anims["combo"]
    cf, info = G.crossfade_pair(A, B, W)
    offB, durA = info["offsetB"], info["durA"]
    # 窗首 w=0 → 純 A(offsetB)
    head_bone = _bone_only_diff(SA.sample(cf, offB), SA.sample(A, offB))
    head_full = G._state_max_diff(SA.sample(cf, offB), SA.sample(A, offB))
    # 窗尾 w=1 → 純 B(window)
    tail_bone = _bone_only_diff(SA.sample(cf, durA), SA.sample(B, W))
    tail_full = G._state_max_diff(SA.sample(cf, durA), SA.sample(B, W))
    # 中點 w=0.5 → 0.5A+0.5B(公式忠實)
    tm = offB + W / 2.0
    cf_mid = SA.sample(cf, tm)
    blend_mid = _blend_state(SA.sample(A, tm), SA.sample(B, tm - offB), 0.5)
    mid_bone = _bone_only_diff(cf_mid, blend_mid)
    mid_full = G._state_max_diff(cf_mid, blend_mid)
    # 非空驗:中點兩拍確實不同
    ab_gap = G._state_max_diff(SA.sample(A, tm), SA.sample(B, tm - offB))
    endpoints_ok = (head_bone < TOL_BONE and head_full < TOL_ENDPT and
                    tail_bone < TOL_BONE and tail_full < TOL_ENDPT)
    mid_ok = mid_bone < TOL_BONE and mid_full < TOL_ENDPT
    nonvacuous = ab_gap >= MIX_THR
    ok = endpoints_ok and mid_ok and nonvacuous
    return {"pass": bool(ok), "head_bone": round(head_bone, 7), "head_full": round(head_full, 6),
            "tail_bone": round(tail_bone, 7), "tail_full": round(tail_full, 6),
            "mid_bone": round(mid_bone, 7), "mid_full": round(mid_full, 6),
            "endpoints_ok": bool(endpoints_ok), "mid_formula_ok": bool(mid_ok),
            "midpoint_AB_gap": round(ab_gap, 4), "non_vacuous": bool(nonvacuous),
            "tol_bone": TOL_BONE, "tol_endpt": TOL_ENDPT, "mix_thr": MIX_THR}


def ac_M3(anims):
    A, B = anims["hit"], anims["combo"]
    cf, info = G.crossfade_pair(A, B, W)
    offB, durA = info["offsetB"], info["durA"]
    cat, _segs = G.compose_sequence({"hit": A, "combo": B}, ["hit", "combo"])
    # 重疊窗格點(避開端點,取窗內)
    N = 19
    cf_depths, cat_depths = [], []
    for i in range(1, N):
        t = offB + (durA - offB) * i / N
        sA_t = SA.sample(A, t)
        sB_t = SA.sample(B, t - offB)
        s_cf = SA.sample(cf, t)
        s_cat = SA.sample(cat, t)
        # 對「兩支 clip 當下狀態」的最小距離 = mix depth(達 >0 表到了兩拍都不在的中間態)
        cf_depths.append(min(G._state_max_diff(s_cf, sA_t), G._state_max_diff(s_cf, sB_t)))
        cat_depths.append(min(G._state_max_diff(s_cat, sA_t), G._state_max_diff(s_cat, sB_t)))
    cf_max = max(cf_depths)
    cat_max = max(cat_depths)
    ok = (cf_max >= DEPTH_MIN) and (cat_max <= COMPOSE_DEPTH_MAX)
    return {"pass": bool(ok), "crossfade_max_mix_depth": round(cf_max, 4),
            "compose_max_mix_depth": round(cat_max, 9),
            "depth_min": DEPTH_MIN, "compose_depth_max": COMPOSE_DEPTH_MAX,
            "note": "crossfade 達兩拍都不在的中間態;compose 恆等某一支 clip"}


def ac_M4(anims):
    A, B = anims["hit"], anims["combo"]
    cf, info = G.crossfade_pair(A, B, W)
    offB, durA, total = info["offsetB"], info["durA"], info["total"]
    # 窗前:A 內部 knot(time<offsetB)cf==A
    preA = _interior_knot_times(A, 0.0, offB)
    pre_res = max((_bone_only_diff(SA.sample(cf, t), SA.sample(A, t)) for t in preA), default=0.0)
    # 窗後:B 內部 knot(B-time>window)→ 絕對時間 = B-time+offsetB;cf==B(B-time)
    postB_btimes = _interior_knot_times(B, W, SA.duration(B))
    post_res = max((_bone_only_diff(SA.sample(cf, bt + offB), SA.sample(B, bt)) for bt in postB_btimes),
                   default=0.0)
    # alpha 也逐位元(窗外 color 幀沿用原幀)→ 用 full diff 複驗
    pre_full = max((G._state_max_diff(SA.sample(cf, t), SA.sample(A, t)) for t in preA), default=0.0)
    post_full = max((G._state_max_diff(SA.sample(cf, bt + offB), SA.sample(B, bt)) for bt in postB_btimes),
                    default=0.0)
    ok = (pre_res < FAITH_TOL and post_res < FAITH_TOL and
          pre_full < FAITH_TOL and post_full < FAITH_TOL and
          len(preA) >= 2 and len(postB_btimes) >= 2)
    return {"pass": bool(ok), "n_preA_knots": len(preA), "n_postB_knots": len(postB_btimes),
            "pre_bone_res": round(pre_res, 9), "post_bone_res": round(post_res, 9),
            "pre_full_res": round(pre_full, 9), "post_full_res": round(post_full, 9),
            "faith_tol": FAITH_TOL}


def ac_M5(anims):
    A, B = anims["hit"], anims["combo"]
    # (a) crux 窗→0 **連續退化**回 compose:crossfade 的窗外純-B 段較 concat 右移恰 W(offsetB=durA−W
    #     vs concat 的 durA),故 sup-dist(cf(W) vs concat) == (接點速度)·W → **線性於 W**,W→0 時 →0
    #     (零窗 crossfade == concat)。量三個小窗,sup/W 應恆定(斜率不變 ⇒ 線性 ⇒ 連續退化)。
    cat, _ = G.compose_sequence({"hit": A, "combo": B}, ["hit", "combo"])
    durA = SA.duration(A)
    windows = [0.04, 0.02, 0.01]
    slopes, sups = [], []
    for Wv in windows:
        cfw, infow = G.crossfade_pair(A, B, Wv)
        total = infow["total"]
        N = 400
        sup = 0.0
        for i in range(N + 1):
            t = total * i / N
            if abs(t - durA) <= Wv + 1e-6:   # 避開重疊窗(窗內本就是混場,非退化測試對象)
                continue
            sup = max(sup, G._state_max_diff(SA.sample(cfw, t), SA.sample(cat, t)))
        sups.append(round(sup, 6))
        slopes.append(sup / Wv)
    base = slopes[0]
    slope_spread = max(abs(s - base) for s in slopes) / base if base > 1e-9 else 0.0
    decreasing = sups[0] > sups[1] > sups[2]
    a_ok = (slope_spread < 1e-3) and decreasing and (base > 1.0)
    degen = sups[-1]
    # (b) partition-of-unity 守衛:兩支相同靜止 hold 混場 → 窗內 cf==P 殘差≈0
    hold = _static_hold(20.0, 1.0)
    cfh, infoh = G.crossfade_pair(hold, hold, 0.3)
    offBh, durAh = infoh["offsetB"], infoh["durA"]
    pou = 0.0
    for i in range(0, 11):
        t = offBh + (durAh - offBh) * i / 10.0
        v = SA.sample(cfh, t)["bones"]["b_身體"]["rotate"]
        pou = max(pou, abs(v - 20.0))
    b_ok = pou < 1e-4
    # (c) 凸性守衛:窗內逐 knot 每通道 cf∈[min(A,B),max(A,B)] 無越界
    cf, info = G.crossfade_pair(A, B, W)
    offB = info["offsetB"]
    durA = info["durA"]
    knots = [f["time"] for f in cf["bones"].get("b_光暈", {}).get("scale", [])
             if offB - 1e-9 <= f["time"] <= durA + 1e-9]
    violations = 0
    worst = 0.0
    for t in knots:
        s_cf = SA.sample(cf, t)
        s_a = SA.sample(A, t)
        s_b = SA.sample(B, t - offB)
        for p in s_cf["bones"]:
            da = s_a["bones"].get(p, G._LOOP_IDENT)
            db = s_b["bones"].get(p, G._LOOP_IDENT)
            dc = s_cf["bones"][p]
            for k in G._LOOP_IDENT:
                lo = min(da.get(k, G._LOOP_IDENT[k]), db.get(k, G._LOOP_IDENT[k]))
                hi = max(da.get(k, G._LOOP_IDENT[k]), db.get(k, G._LOOP_IDENT[k]))
                over = max(lo - dc[k], dc[k] - hi, 0.0)
                if over > CONVEX_EPS:
                    violations += 1
                worst = max(worst, over)
    c_ok = violations == 0
    ok = a_ok and b_ok and c_ok
    return {"pass": bool(ok),
            "a_window0_degeneracy": {"pass": bool(a_ok), "windows": windows,
                                     "sup_dist_vs_compose": sups,
                                     "sup_over_W": [round(s, 3) for s in slopes],
                                     "slope_spread": round(slope_spread, 6), "decreasing": bool(decreasing),
                                     "note": "sup-dist 線性於 W(斜率恆定)→ W→0 連續退化回 concat"},
            "b_partition_of_unity": {"pass": bool(b_ok), "max_dev_from_P": round(pou, 9),
                                     "note": "兩支相同 hold(P=20°)混場 → 窗內恆 P(權重和=1)"},
            "c_convex_bound": {"pass": bool(c_ok), "violations": violations,
                               "worst_overshoot": round(worst, 7), "convex_eps": CONVEX_EPS,
                               "n_knots": len(knots)}}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    needed = ["hit", "combo"]
    missing = [nm for nm in needed if nm not in anims]
    if missing:
        return {"overall_pass": False, "error": "missing beats in fixture: {}".format(missing),
                "available": sorted(anims.keys())}
    results = {"M1_present_structure": ac_M1(anims),
               "M2_crux_endpoint_exact_blend": ac_M2(anims),
               "M3_crux_mix_depth_vs_compose": ac_M3(anims),
               "M4_faithful_outside_overlap": ac_M4(anims),
               "M5_neg_control_guards": ac_M5(anims)}
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
        print("candidate (M) 跨 beat 混場(crossfade/overlap-mix)閘 — crossfade_pair")
        for k in ["M1_present_structure", "M2_crux_endpoint_exact_blend",
                  "M3_crux_mix_depth_vs_compose", "M4_faithful_outside_overlap",
                  "M5_neg_control_guards"]:
            v = res.get(k, {})
            print("  {:34s} {}".format(k, "PASS" if v.get("pass") else "FAIL"))
        if "error" in res:
            print("  ERROR:", res["error"])
        if "M2_crux_endpoint_exact_blend" in res:
            p = res["M2_crux_endpoint_exact_blend"]
            print("    head bone={} tail bone={} mid-formula bone={} | midpoint |A-B|={}".format(
                p["head_bone"], p["tail_bone"], p["mid_bone"], p["midpoint_AB_gap"]))
        if "M3_crux_mix_depth_vs_compose" in res:
            p = res["M3_crux_mix_depth_vs_compose"]
            print("    crossfade mix depth={} (>={}) vs compose={} (<={})".format(
                p["crossfade_max_mix_depth"], p["depth_min"],
                p["compose_max_mix_depth"], p["compose_depth_max"]))
        if "M5_neg_control_guards" in res:
            p = res["M5_neg_control_guards"]
            da = p["a_window0_degeneracy"]
            print("    window->0: sup/W={} (linear={}) | partition-of-unity dev={} | convex violations={}".format(
                da["sup_over_W"], da["decreasing"],
                p["b_partition_of_unity"]["max_dev_from_P"],
                p["c_convex_bound"]["violations"]))
        print("OVERALL:", "PASS" if res.get("overall_pass") else "FAIL")
    return 0 if res.get("overall_pass") else 1


if __name__ == "__main__":
    sys.exit(main())
