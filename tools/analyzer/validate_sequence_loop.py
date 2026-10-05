#!/usr/bin/env python3
"""candidate (L-3) 自我驗收閘 — 序列內 **Loop 重複 N 次**(in-sequence loop repeat,純 CPU,確定性)。

**補的缺口(能力早在、AC 從缺 —— 同 L / G-2 的整合閘精神)**:candidate (L) 的 `compose_sequence(anims, order)`
把各 beat clip 串接成單一可播放序列,其 `order` **本就可重複同一 beat 名**(如 `In→Loop×N→Out`)——這正是真實
大獎序列的播放形態:進場後 **Loop 重播 N 次**(贏分計數滾動時循環待機)再收尾。但 (L) 的正向序列每個 beat
**只出現一次**,**從未有閘**驗過「同一支 clip 重複 N 次」這條路徑:(1) 重複鍵的 offset 累加是否正確、
(2) clip 接在**自己**後面的**自接點**(end→start)是否無縫(= loopability,L 只驗過**相異** beat 的接點)、
(3) N 份重複是否**逐幀還原**同一孤立 clip(重播機制不漂移)、(4) 平鋪後是否真是一段**非靜止**且**嚴格週期**
的循環運動(否則「無縫」是空驗)。本次新增 `gen_animations.is_loopable`(把 loopability 不變量顯式化,additive)
並以此閘把關,直指 north star「產出可循環播放的大獎動畫」。

**選題理由(不選又一條參數軸)**:延續 (L)/(L-2)/(G-2) 刻意選**整合 / 組合閘**而非再加生成軸。L-3 的
客觀新不變量 = loopability(自接點無縫)+ 週期平鋪保真,L 的相異-beat 接點閘涵蓋不到。

真值界定:beat **排序 / 重複次數**是 PROPOSAL(手感 A 類);但「自接點 C0 無縫」「N 份重播逐幀還原」
「平鋪為嚴格週期且非靜止」皆為**客觀可量測**不變量。用負對照(把 **非 loopable** 的 In/Out 重複 → 自接點
pop;以及**靜止** clip 雖 loopable 但平鋪無意義 → LP4 非靜止驗證抓出)證閘有鑑別力(閘可信)。
從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations` 端到端,與 L / charge 同一 fixture。

AC(客觀、可量測):
  LP1 present+loopable+offset : `is_loopable(Loop)`==True;正向序列 `In→Loop×N→Out` compose 後為合法
                               Spine timeline;segments 恰含 N 個 "Loop" 條目於**累加 offset**上;
                               總時長 == In_dur + N·Loop_dur + Out_dur;用到的 bone 皆現身。
  LP2 crux — 自接點無縫      : 每個 Loop→Loop **自接點**殘差(前份尾幀 vs 後份首幀)< SEAM_TOL;且從
                               **composed** 直接量每個 wrap 邊界兩側狀態無 C0 跳變(real tiled motion 無 pop)。
  LP3 periodicity/idempotent : N 份 Loop 重播各自去 offset 後**逐幀還原**孤立 Loop clip(殘差 < FAITH_TOL),
                               且 N 份彼此逐幀相同 → 證重播機制不隨份數漂移 / 不累積誤差。
  LP4 non-static+period-tile : (a) Loop 有**真實內部運動**(孤立 clip 內部最大離 setup 位移 ≥ MOTION_THR;
                               否則「無縫」為空驗);(b) 平鋪區內 `sample(t) == sample(t+Loop_dur)`(嚴格週期,
                               殘差 < FAITH_TOL)→ 證 N 份重播平鋪成一段恰 N 週期的循環運動。
  LP5 neg-control            : (a) **crux**:`is_loopable(In)`==False(In=collapsed→identity)且 In 重複的
                               In→In **自接點**殘差 >> SEAM_TOL(identity→collapsed pop)→ 閘正確判非 loopable;
                               (b) Out(identity→collapsed)同理自接點 pop + is_loopable False;
                               (c) **crux 空驗守衛**:合成一支**靜止**(恆 identity)clip → is_loopable==True 且
                               自接點殘差 0(trivially 無縫)**但** LP4 非靜止檢查 == 0 → 證「光自接點無縫」
                               不足以是有意義的 loop(必須同時非靜止 + 嚴格週期),LP4 有鑑別力。

用法:
  python3 validate_sequence_loop.py            # 摘要
  python3 validate_sequence_loop.py --json     # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0,
         "shearX": 0.0, "shearY": 0.0}

N_REPEAT = 3        # Loop 重播份數
SEAM_TOL = 1e-3     # 接點 C0 殘差上限(loopable self-seam identity==identity 實測 ~0)
FAITH_TOL = 1e-4    # 回切還原 / 週期殘差上限(純時間平移,實測 ~1e-6 round)
MOTION_THR = 1.0    # Loop 內部最小運動幅度(實測 ~5.0;靜止 clip=0 → LP4 空驗守衛抓出)
NEG_MULT = 10.0     # 負對照自接點殘差須 > NEG_MULT × SEAM_TOL(In/Out 實測 25~40,>>)
WRAP_EPS = 1e-4     # 量 wrap 邊界兩側 C0 跳變的微小時移

# 正向序列(PROPOSAL 手感):In(collapsed→id) → Loop 重播 N 次(id→id) → Out(id→collapsed)。
LOOP_ORDER = ["In"] + ["Loop"] * N_REPEAT + ["Out"]


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/seq_loop_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


# ---------------- 量測器 ----------------
def _state_diff(s1, s2):
    """複用 gen_animations 的狀態差(含 shear),確保閘與產線判準同源。"""
    return G._state_max_diff(s1, s2)


def _self_seams(anims, order):
    """各內部接點殘差(前一 beat 尾幀 vs 後一 beat 首幀)。回傳 [{pair, seam}, ...]。"""
    seams = []
    for i in range(len(order) - 1):
        a, b = anims[order[i]], anims[order[i + 1]]
        end = SA.sample(a, SA.duration(a))
        start = SA.sample(b, 0.0)
        seams.append({"pair": "{}->{}".format(order[i], order[i + 1]),
                      "seam": round(_state_diff(end, start), 6)})
    return seams


def _interior_motion(clip, n=24):
    """孤立 clip 內部(不含首尾)離 setup identity 的最大位移。"""
    dur = SA.duration(clip)
    if dur <= 0:
        return 0.0
    empty = {"bones": {}, "slots": {}}
    m = 0.0
    for i in range(1, n):
        m = max(m, _state_diff(SA.sample(clip, dur * i / n), empty))
    return m


def _static_loop_clip(dur=2.0):
    """合成一支**靜止**(恆 identity)clip:有時間跨度但無運動 → loopable 但平鋪無意義。"""
    return {"bones": {"b_身體": {"rotate": [{"time": 0.0, "angle": 0.0},
                                            {"time": dur, "angle": 0.0}]}}}


# ---------------- AC ----------------
def ac_LP1(anims):
    loopable = G.is_loopable(anims["Loop"])
    composed, segs = G.compose_sequence(anims, LOOP_ORDER)
    # well-formed:每通道時間嚴格遞增、值 finite
    wf = True
    for group in ("bones", "slots"):
        for chans in composed.get(group, {}).values():
            for frames in chans.values():
                last = None
                for f in frames:
                    t = f.get("time")
                    if t is None or not math.isfinite(t) or (last is not None and not (t > last)):
                        wf = False
                    last = t
                    for k, val in f.items():
                        if k != "time" and isinstance(val, (int, float)) and not math.isfinite(val):
                            wf = False
    loop_segs = [s for s in segs if s["beat"] == "Loop"]
    n_ok = len(loop_segs) == N_REPEAT
    # offset 累加:In@0, 之後每份 Loop 起點 = 前者起點+前者時長
    in_dur = SA.duration(anims["In"])
    loop_dur = SA.duration(anims["Loop"])
    out_dur = SA.duration(anims["Out"])
    expect_starts = [round(in_dur + k * loop_dur, 6) for k in range(N_REPEAT)]
    got_starts = [s["start"] for s in loop_segs]
    offsets_ok = got_starts == expect_starts
    sum_dur = round(in_dur + N_REPEAT * loop_dur + out_dur, 6)
    tot = round(SA.duration(composed), 6)
    dur_ok = abs(sum_dur - tot) <= 1e-4 and tot > 0
    used_bones = set()
    for nm in set(LOOP_ORDER):
        used_bones |= set(anims[nm].get("bones", {}).keys())
    present = used_bones <= set(composed.get("bones", {}).keys())
    ok = loopable and wf and n_ok and offsets_ok and dur_ok and present
    return {"pass": bool(ok), "loop_is_loopable": bool(loopable), "well_formed": bool(wf),
            "n_loop_segments": len(loop_segs), "n_expected": N_REPEAT,
            "offsets_ok": bool(offsets_ok), "loop_starts": got_starts, "expected_starts": expect_starts,
            "sum_dur": sum_dur, "total_dur": tot, "all_bones_present": bool(present)}


def _wrap_continuity_ratio(composed, bt, eps=WRAP_EPS):
    """量 compose 輸出在 wrap 邊界 bt 的**連續性**:以 eps / eps·0.1 兩尺度量跨邊界有限差,
    回 shrink 比 = jump(eps·0.1) / jump(eps)。C0 連續 → 比 ≈ 0.1(差隨 eps 線性縮小);
    **真正不連續**(固定跳變)→ 比 ≈ 1(縮不下去)。
    ⚠️ 關鍵:`compose_sequence` 的**時間去重**會把「同時刻、不同值」的接點 collapse 成單幀 →
    值不符的接點被**抹成陡坡**而非真跳變,故 composed 取樣**恆 C0**(此比對 Loop 與 tiled-In 皆 ≈0.1)。
    → **loopability 只能在 clip 端點層(self-seam / is_loopable)判,不能從 composed 時間軸判**。本函式僅
    **確認** compose 產物確為連續函數(非 loop 判準);真 pop 判準見 self-seam。"""
    j_big = _state_diff(SA.sample(composed, bt - eps), SA.sample(composed, bt + eps))
    j_small = _state_diff(SA.sample(composed, bt - eps * 0.1), SA.sample(composed, bt + eps * 0.1))
    return j_small / j_big if j_big > 1e-12 else 0.0


def ac_LP2(anims):
    # crux C0 loop 判準 = **clip 端點層 self-seam**(前份尾幀值 vs 後份首幀值);與 is_loopable 同源。
    seams = _self_seams(anims, LOOP_ORDER)
    worst = max((s["seam"] for s in seams), default=0.0)
    self_seams = [s for s in seams if s["pair"] == "Loop->Loop"]
    worst_self = max((s["seam"] for s in self_seams), default=0.0)
    n_self = len(self_seams)
    # 確認 compose 產物為連續函數(非 loop 判準,僅佐證 compose 正確):shrink 比 ≈0.1。
    composed, segs = G.compose_sequence(anims, LOOP_ORDER)
    loop_segs = [s for s in segs if s["beat"] == "Loop"]
    shrink = max((_wrap_continuity_ratio(composed, s["start"]) for s in loop_segs[1:]), default=0.0)
    compose_c0 = shrink < 0.2  # 線性縮小 → 連續(非固定跳變)
    ok = worst < SEAM_TOL and n_self == N_REPEAT - 1 and compose_c0
    return {"pass": bool(ok), "worst_seam": worst, "worst_self_seam": worst_self,
            "n_self_seams": n_self, "compose_wrap_shrink_ratio": round(shrink, 4),
            "compose_is_c0": bool(compose_c0), "tol": SEAM_TOL, "seams": seams}


def ac_LP3(anims):
    composed, segs = G.compose_sequence(anims, LOOP_ORDER)
    loop = anims["Loop"]
    loop_dur = SA.duration(loop)
    loop_segs = [s for s in segs if s["beat"] == "Loop"]
    grid = 24
    # (1) 每份去 offset 逐幀還原孤立 Loop
    worst = 0.0
    worst_at = None
    per_repeat_series = []
    for s in loop_segs:
        series = []
        for i in range(grid + 1):
            t = loop_dur * i / grid
            ctx = SA.sample(composed, s["start"] + t)
            series.append(ctx)
            d = _state_diff(ctx, SA.sample(loop, t))
            if d > worst:
                worst, worst_at = d, {"start": s["start"], "t": round(t, 4)}
        per_repeat_series.append(series)
    faithful = worst < FAITH_TOL
    # (2) N 份彼此逐幀相同(重播不漂移)
    mutual = 0.0
    for r in range(1, len(per_repeat_series)):
        for i in range(grid + 1):
            mutual = max(mutual, _state_diff(per_repeat_series[r][i], per_repeat_series[0][i]))
    identical = mutual < FAITH_TOL
    ok = faithful and identical
    return {"pass": bool(ok), "worst_residual": round(worst, 9), "worst_at": worst_at,
            "mutual_repeat_diff": round(mutual, 9), "tol": FAITH_TOL}


def ac_LP4(anims):
    loop = anims["Loop"]
    loop_dur = SA.duration(loop)
    motion = _interior_motion(loop)
    non_static = motion >= MOTION_THR
    # 嚴格週期:平鋪區內 sample(t) == sample(t+loop_dur)。取樣橫跨第 1→2 份 Loop。
    composed, segs = G.compose_sequence(anims, LOOP_ORDER)
    loop_segs = [s for s in segs if s["beat"] == "Loop"]
    base = loop_segs[0]["start"]  # 第一份 Loop 起點
    grid = 24
    worst_period = 0.0
    for i in range(grid + 1):
        t = base + loop_dur * i / grid
        d = _state_diff(SA.sample(composed, t), SA.sample(composed, t + loop_dur))
        worst_period = max(worst_period, d)
    periodic = worst_period < FAITH_TOL
    ok = non_static and periodic
    return {"pass": bool(ok), "interior_motion": round(motion, 4), "motion_thr": MOTION_THR,
            "non_static": bool(non_static), "worst_period_residual": round(worst_period, 9),
            "periodic": bool(periodic), "tol": FAITH_TOL}


def ac_LP5(anims):
    # (a) crux:In(collapsed→identity)非 loopable,重複 In → In->In 自接點 pop。
    #   **深一層 crux**:tiled-In 的 composed 經時間去重後 wrap **看起來仍 C0**(pop 被抹成陡坡,
    #   shrink 比 ≈0.1 與合格 Loop 無異)→ 證「loopability 不能從 composed 判」,唯 clip 端點 self-seam 揭露。
    in_loopable = G.is_loopable(anims["In"])
    order_a = ["In", "In", "Loop", "Out"]
    seams_a = _self_seams(anims, order_a)
    self_a = [s for s in seams_a if s["pair"] == "In->In"][0]["seam"]
    comp_a, segs_a = G.compose_sequence(anims, order_a)
    in_segs_a = [s for s in segs_a if s["beat"] == "In"]
    tiled_in_shrink = _wrap_continuity_ratio(comp_a, in_segs_a[1]["start"])
    composed_looks_c0 = tiled_in_shrink < 0.2   # 去重抹平 → composed 誤看 C0
    a_ok = (not in_loopable) and (self_a > NEG_MULT * SEAM_TOL) and composed_looks_c0

    # (b) Out(identity→collapsed)非 loopable,重複 Out → Out->Out 自接點 pop
    out_loopable = G.is_loopable(anims["Out"])
    order_b = ["In", "Loop", "Out", "Out"]
    seams_b = _self_seams(anims, order_b)
    self_b = [s for s in seams_b if s["pair"] == "Out->Out"][0]["seam"]
    b_ok = (not out_loopable) and (self_b > NEG_MULT * SEAM_TOL)

    # (c) crux 空驗守衛:靜止 clip loopable 且自接點 0,但 LP4 非靜止檢查 == 0 → 光無縫不夠
    static = _static_loop_clip()
    static_loopable = G.is_loopable(static)
    static_self = _state_diff(SA.sample(static, SA.duration(static)), SA.sample(static, 0.0))
    static_motion = _interior_motion(static)
    # 證:static 既 loopable 又自接點無縫(像個「合格 loop」),唯有 LP4 的「非靜止」能把它判掉
    c_ok = static_loopable and (static_self < SEAM_TOL) and (static_motion < MOTION_THR)

    ok = a_ok and b_ok and c_ok
    return {"pass": bool(ok),
            "a_in_not_loopable": {"pass": bool(a_ok), "is_loopable": bool(in_loopable),
                                  "self_seam": round(self_a, 4),
                                  "tiled_composed_looks_c0": bool(composed_looks_c0),
                                  "tiled_shrink_ratio": round(tiled_in_shrink, 4)},
            "b_out_not_loopable": {"pass": bool(b_ok), "is_loopable": bool(out_loopable),
                                   "self_seam": round(self_b, 4)},
            "c_static_vacuity_guard": {"pass": bool(c_ok), "is_loopable": bool(static_loopable),
                                       "self_seam": round(static_self, 6),
                                       "interior_motion": round(static_motion, 6)}}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    needed = set(LOOP_ORDER) | {"Out"}
    missing = [nm for nm in needed if nm not in anims]
    if missing:
        return {"overall_pass": False, "error": "missing beats in fixture: {}".format(missing),
                "available": sorted(anims.keys())}
    results = {"LP1_present_loopable_offset": ac_LP1(anims),
               "LP2_crux_self_seamless": ac_LP2(anims),
               "LP3_periodicity_idempotent": ac_LP3(anims),
               "LP4_nonstatic_period_tile": ac_LP4(anims),
               "LP5_neg_control": ac_LP5(anims)}
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
        print("candidate (L-3) 序列內 Loop 重播閘 — compose_sequence(order 重複鍵)+ is_loopable")
        print("序列:", " -> ".join(LOOP_ORDER))
        for k in ["LP1_present_loopable_offset", "LP2_crux_self_seamless",
                  "LP3_periodicity_idempotent", "LP4_nonstatic_period_tile", "LP5_neg_control"]:
            v = res.get(k, {})
            print("  {:30s} {}".format(k, "PASS" if v.get("pass") else "FAIL"))
        if "error" in res:
            print("  ERROR:", res["error"])
        if "LP2_crux_self_seamless" in res:
            p = res["LP2_crux_self_seamless"]
            print("    LP2 worst self-seam: {:.2e}  compose-C0(shrink {:.2f}): {} (tol {:.0e})".format(
                p["worst_self_seam"], p["compose_wrap_shrink_ratio"], p["compose_is_c0"], SEAM_TOL))
        if "LP3_periodicity_idempotent" in res:
            p = res["LP3_periodicity_idempotent"]
            print("    LP3 worst回切殘差: {:.2e}  mutual: {:.2e}".format(
                p["worst_residual"], p["mutual_repeat_diff"]))
        if "LP4_nonstatic_period_tile" in res:
            p = res["LP4_nonstatic_period_tile"]
            print("    LP4 interior motion: {:.3f}  period residual: {:.2e}".format(
                p["interior_motion"], p["worst_period_residual"]))
        if "LP5_neg_control" in res:
            p = res["LP5_neg_control"]
            print("    LP5a In self-seam: {} (loopable={})".format(
                p["a_in_not_loopable"]["self_seam"], p["a_in_not_loopable"]["is_loopable"]))
            print("    LP5c static: loopable={} self-seam={} motion={}".format(
                p["c_static_vacuity_guard"]["is_loopable"],
                p["c_static_vacuity_guard"]["self_seam"],
                p["c_static_vacuity_guard"]["interior_motion"]))
        print("OVERALL:", "PASS" if res.get("overall_pass") else "FAIL")
    return 0 if res.get("overall_pass") else 1


if __name__ == "__main__":
    sys.exit(main())
