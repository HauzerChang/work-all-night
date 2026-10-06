#!/usr/bin/env python3
"""candidate (L-5) 自我驗收閘 — 跨 beat 混場 crossfade / mix 序列接點(純 CPU,確定性)。

**補的缺口(L / L-2 / L-3 / L-4 一路誠實列出的 honest boundary)**:這四個 candidate 都圍繞
`compose_sequence`,而它是**純時間平移 + 接點去重** = **C0 拼接** —— 任一瞬間**恰好一支 beat 在作用**
(前 beat 尾 == 後 beat 首時無縫銜接)。真實大獎序列常用**混場 / 溶接(crossfade / dissolve)**:在一段
**重疊窗**內前 beat **淡出**、後 beat **淡入**,兩者**同時貢獻**(疊加 superposition)。純平移 + 去重
**在結構上做不到疊加**(它只能把時間錯開,不能讓兩 beat 在同一瞬間並存),所以 crossfade 是**序列組合的
下一個組合層軸**,需要真正的 mix 機制。本次把它補上:`gen_animations.crossfade_pair`(烘焙式混場 —— 重疊窗
內同步取樣兩 clip、加權線性混合、以 dt 網格發出混合關鍵幀;窗外維持純 A / 純 B 保真)+ `crossfade_sequence`
(多 beat 左折疊)+ 本閘。

**選題理由(不選又一條參數軸)**:延續 (L)/(L-2)/(L-3)/(L-4) 刻意選**整合 / 組合閘**。L-5 的客觀新機制 =
重疊窗內的**加權疊加**,`compose_sequence` 的 C0 拼接**結構上**涵蓋不到(同一全域時間只能是單一 clip 的值)。
從**先驗庫 → 真實 build_spine robot 骨架 → build_animations** 端到端,與 L / L-3 / L-4 同一 fixture。

**crux / 本 run 的核心**:crossfade 在重疊窗內讓兩 beat **同時貢獻**。取窗內某 grid 時間 t*(兩 beat 皆非
identity)—— 混合值 `(1-w)·A(t*) + w·B(t*−offsetB)` 既**明顯 ≠ 純 A** 亦**≠ 純 B**(兩者都在出力);而
`compose_sequence` 在同一 t*(<durA)只會是**純 A 的值**(單一 beat),與混合值差 >MIX_MIN → 直接證明
**C0 拼接結構上做不到疊加**,crossfade 是真的新組合層。

真值界定:crossfade 的**窗長 / 緩動曲線**屬美術手感(A 類,本閘用 linear 權重、不引入美感軸);但
「混合 = 加權線性疊加」「partition of unity(A 權重 1-w、B 權重 w、和=1)」「重疊窗兩端 C0 連續」「overlap=0
退化為 C0 拼接」「純區段保真」皆為**客觀可量測**不變量。負對照(① overlap=0 逐位元 == compose_sequence ②
兩等值常數 clip 混合無 bump ③ concat 在同一時間拿不到混合值)證閘有鑑別力。

**量測精度誠實**:骨通道(rotate/translate/scale/shear)混合**精確**(殘差僅 6 位時間 round 的 ~1e-5,
BONE_TOL=1e-4);slot alpha 受 Spine 8-hex color 格式**8-bit 量化**(≤1/255≈0.0039),故全狀態殘差以
QUANT_TOL=1/255+eps 把關,並**分離**回報骨殘差(精確)與全狀態殘差(含量化)。
honest boundary:slot 混合假設 alpha-only 白色 tint(本資產光暈成立),重疊窗 slot color 以 "ffffff"+alpha
重發(純區段保留原 hex);非白 tint 的 rgb 混合為後續。

AC(客觀、可量測):
  CF1 present+mechanism-active : crossfade(combo,cascade,OV)可載入(all_finite・時間嚴格遞增)、
                                duration == durA+durB−OV;**非空驗**:重疊窗內 ∃ grid 時間兩 beat
                                **同時**非 identity(max min(devA,devB) ≥ SUPERPOS_MIN)→ 真有疊加。
  CF2 crux — C0 窗邊界連續      : 進窗(offsetB,w=0→A(offsetB))與出窗(durA,w=1→B(OV))與純區段值連續;
                                **骨殘差 ≤ BONE_TOL(精確銜接)**,全狀態殘差 ≤ QUANT_TOL(slot 8-bit 量化)。
  CF3 crux — 真疊加/concat 做不到: 窗內 grid t*(w∈(0,1)、兩 beat 皆非 identity):(a)線性 cf(t*)==
                                (1-w)A+wB 骨精確;(b)兩者皆貢獻 |cf−純A|>MIX_MIN 且 |cf−純B|>MIX_MIN;
                                (c)**crux** compose_sequence(t*)==純 A(骨 ≤BONE_TOL)且 |concat−cf|>MIX_MIN
                                → C0 拼接同一時間只拿得到單一 beat,結構上做不到混合。
  CF4 partition+退化守衛        : (a)partition of unity:兩常數 clip(10°,30°)窗內每 w 混合==10+20w 精確、
                                端點 10/30;(b)**no-bump 守衛**:兩等值常數(20°,20°)窗內恆 20(dev≤1e-9)→
                                權重和=1 無 artifact;(c)**crux overlap=0 逐位元 == compose_sequence** →
                                crossfade 是嚴格推廣,零重疊退化回 L 的 C0 拼接。
  CF5 純區段保真+多 beat       : 純前段 [0,t0](t0=最後一個 <offsetB 的 A 關鍵幀)逐幀還原孤立 A、
                                純後段 (durA,total] 逐幀還原孤立 B(骨 ≤BONE_TOL 全狀態 ≤QUANT_TOL)→
                                混場只動重疊窗、不擾動純區段;crossfade_sequence(hit→combo→cascade,
                                每接點 0.3s)可載入且 duration == Σdur − 2·0.3。

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

A_BEAT = "combo"       # 前 beat(dur 0.9,純前段充足)
B_BEAT = "cascade"     # 後 beat(dur 1.2,純後段充足)
OVERLAP = 0.5          # 重疊窗(秒;≤ min(durA,durB)=0.9)
DT = 1.0 / 30.0        # 重疊窗混合取樣網格

BONE_TOL = 1e-4        # 骨通道混合精確上限(僅 6 位時間 round 殘差 ~1e-5)
QUANT_TOL = 1.0 / 255.0 + 1e-6   # slot alpha 8-bit 量化上限(≈0.003925)
SUPERPOS_MIN = 1.0     # 非空驗:窗內兩 beat 同時偏離 identity 的最小量(實測 ≈9.1)
MIX_MIN = 1.0          # 「真疊加」與「concat 做不到」的最小鑑別距離(實測 ≈5~8)


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/seq_crossfade_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


# ---------------- 量測器 ----------------
def _bone_diff(s1, s2):
    """兩 state 的**骨通道**最大絕對差(不含 slot;缺席=setup identity)。"""
    m = 0.0
    for b in set(s1["bones"]) | set(s2["bones"]):
        d1 = s1["bones"].get(b, G._LOOP_IDENT)
        d2 = s2["bones"].get(b, G._LOOP_IDENT)
        for k in G._LOOP_IDENT:
            m = max(m, abs(d1.get(k, G._LOOP_IDENT[k]) - d2.get(k, G._LOOP_IDENT[k])))
    return m


def _whole_diff(s1, s2):
    return G._state_max_diff(s1, s2)


def _dev_from_identity(clip, t):
    """clip 在 t 離 setup identity 的最大偏離(含 slot alpha)。"""
    s = SA.sample(clip, t)
    return _whole_diff(s, {"bones": {}, "slots": {}})


def _grid(offsetB, durA, ov, dt=DT):
    n = max(1, int(math.ceil(ov / dt - 1e-9)))
    g = [offsetB + i * dt for i in range(n + 1)]
    g[-1] = durA
    if len(g) >= 2 and abs(g[-1] - g[-2]) <= 1e-6:
        g.pop(-2)
    return g


def _const_clip(v, dur=1.0):
    return {"bones": {"b_身體": {"rotate": [{"time": 0.0, "angle": v},
                                            {"time": dur, "angle": v}]}}}


def _last_kf_before(clip, t):
    """clip 中時間 < t 的最大關鍵幀時間(骨通道)。"""
    best = 0.0
    for chans in clip.get("bones", {}).values():
        for tl in chans.values():
            for f in tl:
                if f["time"] < t - 1e-9:
                    best = max(best, f["time"])
    return best


# ---------------- AC ----------------
def ac_CF1(anims):
    A, B = anims[A_BEAT], anims[B_BEAT]
    dA, dB = SA.duration(A), SA.duration(B)
    offB, total = dA - OVERLAP, dA + dB - OVERLAP
    cf = G.crossfade_pair(A, B, OVERLAP, dt=DT)
    loadable = SA.all_finite(cf)
    dur_ok = abs(SA.duration(cf) - total) < 1e-6
    best = 0.0
    for tg in _grid(offB, dA, OVERLAP):
        best = max(best, min(_dev_from_identity(A, tg), _dev_from_identity(B, tg - offB)))
    non_vacuous = best >= SUPERPOS_MIN
    ok = loadable and dur_ok and non_vacuous
    return {"pass": bool(ok), "loadable": bool(loadable), "duration": round(SA.duration(cf), 6),
            "expected_duration": round(total, 6), "dur_ok": bool(dur_ok),
            "max_simultaneous_dev": round(best, 4), "superpos_min": SUPERPOS_MIN,
            "non_vacuous": bool(non_vacuous)}


def ac_CF2(anims):
    A, B = anims[A_BEAT], anims[B_BEAT]
    dA = SA.duration(A)
    offB = dA - OVERLAP
    cf = G.crossfade_pair(A, B, OVERLAP, dt=DT)
    # 進窗:w=0 → A(offsetB);出窗:w=1 → B(OVERLAP)
    entry_bone = _bone_diff(SA.sample(cf, offB), SA.sample(A, offB))
    entry_whole = _whole_diff(SA.sample(cf, offB), SA.sample(A, offB))
    exit_bone = _bone_diff(SA.sample(cf, dA), SA.sample(B, OVERLAP))
    exit_whole = _whole_diff(SA.sample(cf, dA), SA.sample(B, OVERLAP))
    bones_exact = entry_bone <= BONE_TOL and exit_bone <= BONE_TOL
    whole_ok = entry_whole <= QUANT_TOL and exit_whole <= QUANT_TOL
    ok = bones_exact and whole_ok
    return {"pass": bool(ok), "entry_bone_resid": round(entry_bone, 8),
            "exit_bone_resid": round(exit_bone, 8), "bone_tol": BONE_TOL,
            "entry_whole_resid": round(entry_whole, 6), "exit_whole_resid": round(exit_whole, 6),
            "quant_tol": round(QUANT_TOL, 6), "bones_exact": bool(bones_exact),
            "whole_within_quant": bool(whole_ok)}


def ac_CF3(anims):
    A, B = anims[A_BEAT], anims[B_BEAT]
    dA = SA.duration(A)
    offB = dA - OVERLAP
    cf = G.crossfade_pair(A, B, OVERLAP, dt=DT)
    # 選窗內(嚴格內部)兩 beat 同時最偏離 identity 的 grid 時間
    interior = [tg for tg in _grid(offB, dA, OVERLAP) if offB + 1e-9 < tg < dA - 1e-9]
    tstar = max(interior, key=lambda tg: min(_dev_from_identity(A, tg),
                                             _dev_from_identity(B, tg - offB)))
    w = G.crossfade_weight(tstar - offB, OVERLAP)
    # (a) 線性:cf == (1-w)A + wB
    exp = G.blend_states(SA.sample(A, tstar), SA.sample(B, tstar - offB), w)
    lin_bone = _bone_diff(SA.sample(cf, tstar), exp)
    lin_whole = _whole_diff(SA.sample(cf, tstar), exp)
    linear_ok = lin_bone <= BONE_TOL and lin_whole <= QUANT_TOL
    # (b) 兩者皆貢獻
    d_pureA = _whole_diff(SA.sample(cf, tstar), SA.sample(A, tstar))
    d_pureB = _whole_diff(SA.sample(cf, tstar), SA.sample(B, tstar - offB))
    both_contribute = d_pureA > MIX_MIN and d_pureB > MIX_MIN
    # (c) crux:concat 同一時間 == 純 A(<durA),拿不到混合
    comp, _ = G.compose_sequence({"__A": A, "__B": B}, ["__A", "__B"])
    concat_is_pureA = _bone_diff(SA.sample(comp, tstar), SA.sample(A, tstar)) <= BONE_TOL
    concat_vs_cf = _whole_diff(SA.sample(comp, tstar), SA.sample(cf, tstar))
    concat_cannot = concat_is_pureA and concat_vs_cf > MIX_MIN
    ok = linear_ok and both_contribute and concat_cannot
    return {"pass": bool(ok), "t_star": round(tstar, 4), "w": round(w, 4),
            "linearity_bone_resid": round(lin_bone, 8), "linearity_whole_resid": round(lin_whole, 6),
            "linear_ok": bool(linear_ok), "dist_to_pureA": round(d_pureA, 4),
            "dist_to_pureB": round(d_pureB, 4), "both_contribute": bool(both_contribute),
            "concat_is_pureA": bool(concat_is_pureA), "concat_vs_cf": round(concat_vs_cf, 4),
            "concat_cannot_mix": bool(concat_cannot), "mix_min": MIX_MIN}


def ac_CF4(anims):
    A, B = anims[A_BEAT], anims[B_BEAT]
    # (a) partition of unity:兩常數 clip 10°,30° → 窗內 == 10+20w 精確
    ca, cb, ov = 10.0, 30.0, 0.5
    cfp = G.crossfade_pair(_const_clip(ca), _const_clip(cb), ov, dt=DT)
    offB = 1.0 - ov
    pu_max = 0.0
    for tg in _grid(offB, 1.0, ov):
        w = G.crossfade_weight(tg - offB, ov)
        got = SA.sample(cfp, tg)["bones"]["b_身體"]["rotate"]
        pu_max = max(pu_max, abs(got - (ca + (cb - ca) * w)))
    ends_ok = (abs(SA.sample(cfp, offB)["bones"]["b_身體"]["rotate"] - ca) <= BONE_TOL and
               abs(SA.sample(cfp, 1.0)["bones"]["b_身體"]["rotate"] - cb) <= BONE_TOL)
    pu_ok = pu_max <= BONE_TOL and ends_ok
    # (b) no-bump 守衛:兩等值常數 → 窗內恆值
    cfn = G.crossfade_pair(_const_clip(20.0), _const_clip(20.0), ov, dt=DT)
    bump = 0.0
    for i in range(21):
        tg = offB + ov * i / 20.0
        bump = max(bump, abs(SA.sample(cfn, tg)["bones"]["b_身體"]["rotate"] - 20.0))
    no_bump = bump <= 1e-9
    # (c) crux overlap=0 逐位元 == compose_sequence
    cf0 = G.crossfade_pair(A, B, 0.0)
    comp, _ = G.compose_sequence({"__A": A, "__B": B}, ["__A", "__B"])
    bitcompat = json.dumps(cf0, sort_keys=True, ensure_ascii=False) == \
        json.dumps(comp, sort_keys=True, ensure_ascii=False)
    ok = pu_ok and no_bump and bitcompat
    return {"pass": bool(ok), "partition_of_unity_max_err": round(pu_max, 8),
            "partition_endpoints_ok": bool(ends_ok), "partition_ok": bool(pu_ok),
            "no_bump_max_dev": round(bump, 12), "no_bump_ok": bool(no_bump),
            "overlap0_bitcompat_with_compose": bool(bitcompat)}


def ac_CF5(anims):
    A, B = anims[A_BEAT], anims[B_BEAT]
    dA, dB = SA.duration(A), SA.duration(B)
    offB, total = dA - OVERLAP, dA + dB - OVERLAP
    cf = G.crossfade_pair(A, B, OVERLAP, dt=DT)
    # 純前段 [0, t0] 逐幀還原孤立 A
    t0 = _last_kf_before(A, offB)
    preA_bone = preA_whole = 0.0
    for i in range(41):
        t = t0 * i / 40.0
        preA_bone = max(preA_bone, _bone_diff(SA.sample(cf, t), SA.sample(A, t)))
        preA_whole = max(preA_whole, _whole_diff(SA.sample(cf, t), SA.sample(A, t)))
    # 純後段 (durA, total] 逐幀還原孤立 B(local = t-offsetB)
    postB_bone = postB_whole = 0.0
    for i in range(1, 41):
        t = dA + (total - dA) * i / 40.0
        postB_bone = max(postB_bone, _bone_diff(SA.sample(cf, t), SA.sample(B, t - offB)))
        postB_whole = max(postB_whole, _whole_diff(SA.sample(cf, t), SA.sample(B, t - offB)))
    pre_ok = preA_bone <= BONE_TOL and preA_whole <= QUANT_TOL
    post_ok = postB_bone <= BONE_TOL and postB_whole <= QUANT_TOL
    # 多 beat crossfade_sequence
    order = ["hit", "combo", "cascade"]
    seq_ov = 0.3
    seq = G.crossfade_sequence(anims, order, seq_ov, dt=DT)
    exp_dur = sum(SA.duration(anims[n]) for n in order) - seq_ov * (len(order) - 1)
    seq_ok = SA.all_finite(seq) and abs(SA.duration(seq) - exp_dur) < 1e-6
    ok = pre_ok and post_ok and seq_ok
    return {"pass": bool(ok), "pre_region_end": round(t0, 4),
            "preA_bone_resid": round(preA_bone, 8), "preA_whole_resid": round(preA_whole, 6),
            "pre_faithful": bool(pre_ok), "postB_bone_resid": round(postB_bone, 8),
            "postB_whole_resid": round(postB_whole, 6), "post_faithful": bool(post_ok),
            "multibeat_loadable": bool(SA.all_finite(seq)), "multibeat_duration": round(SA.duration(seq), 6),
            "multibeat_expected": round(exp_dur, 6), "multibeat_ok": bool(seq_ok)}


def run():
    skel = _skeleton()
    sb = analyze(_psd(), GENRE)["3_motion_storyboard"]
    anims = G.build_animations(skel, sb)
    needed = [A_BEAT, B_BEAT, "hit"]
    missing = [nm for nm in needed if nm not in anims]
    if missing:
        return {"overall_pass": False, "error": "missing beats: {}".format(missing),
                "available": sorted(anims.keys())}
    results = {"CF1_present_mechanism_active": ac_CF1(anims),
               "CF2_crux_C0_boundaries": ac_CF2(anims),
               "CF3_crux_superposition_concat_cannot": ac_CF3(anims),
               "CF4_partition_degeneracy_guards": ac_CF4(anims),
               "CF5_faithful_pure_regions_multibeat": ac_CF5(anims)}
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
        print("candidate (L-5) 跨 beat 混場 crossfade/mix 序列接點閘 — crossfade_pair + crossfade_sequence")
        for k in ["CF1_present_mechanism_active", "CF2_crux_C0_boundaries",
                  "CF3_crux_superposition_concat_cannot", "CF4_partition_degeneracy_guards",
                  "CF5_faithful_pure_regions_multibeat"]:
            v = res.get(k, {})
            print("  {:38s} {}".format(k, "PASS" if v.get("pass") else "FAIL"))
        if "error" in res:
            print("  ERROR:", res["error"])
        if "CF1_present_mechanism_active" in res:
            p = res["CF1_present_mechanism_active"]
            print("    dur={} (exp {}) | max simultaneous dev={} (≥{})".format(
                p["duration"], p["expected_duration"], p["max_simultaneous_dev"], p["superpos_min"]))
        if "CF3_crux_superposition_concat_cannot" in res:
            p = res["CF3_crux_superposition_concat_cannot"]
            print("    t*={} w={} | cf→pureA={} cf→pureB={} | concat==pureA={} concat vs cf={}".format(
                p["t_star"], p["w"], p["dist_to_pureA"], p["dist_to_pureB"],
                p["concat_is_pureA"], p["concat_vs_cf"]))
        if "CF4_partition_degeneracy_guards" in res:
            p = res["CF4_partition_degeneracy_guards"]
            print("    partition err={} | no-bump dev={} | overlap0==compose bitcompat={}".format(
                p["partition_of_unity_max_err"], p["no_bump_max_dev"],
                p["overlap0_bitcompat_with_compose"]))
        print("OVERALL:", "PASS" if res.get("overall_pass") else "FAIL")
    return 0 if res.get("overall_pass") else 1


if __name__ == "__main__":
    sys.exit(main())
