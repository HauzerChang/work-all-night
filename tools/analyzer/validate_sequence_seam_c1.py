#!/usr/bin/env python3
"""candidate (L-5) 自我驗收閘 — **相異 beat 接點**的 C1(速度)連續性 / 序列全程 C1(純 CPU,確定性)。

**補的缺口(L-4 誠實列出的 honest boundary)**:candidate (L-4) 把「可**無頓挫**重播」顯式化,但**只驗自接點**
(同一支 Loop 重播 N 次,前份尾→後份首)。L-4 的「下一步」明記:序列**全程** C1 連續(不只自接點,也含**相異
beat 接點** In→hit / … / Loop→Out 的速度連續)尚未驗。本次把這條 boundary 關掉:新增
`gen_animations.seam_velocity_gap`(相異接點 C1 量,一般化 `loop_seam_velocity_gap`)+ `sequence_seam_gaps`
(序列全程逐接點 C0/C1 報告)+ `is_c1_continuous_sequence`(序列全程 C1 判準),並以閘把關。
直指 north star「產出可**平順**播放的大獎序列」。

**crux / 本 run 的核心發現(與 L-4 的新區別)**:
  1. 真實大獎正向序列 In→hit→combo→charge→cascade→Loop→Out 的**每個相異接點都 C0 無縫**(值連續,L 已驗)
     **但都 C1 不連續**(接點速度突變 15~114):大獎序列本質是一串**離散節拍/撞擊**,不是速度平滑的變形。本閘
     量化並**逐接點定位** kick(誠實攤開:這是設計使然、非 bug;要不要平滑屬美術手感 A 類)。
  2. **自接點 C1(L-4)與相異接點 C1(L-5)是兩個獨立不變量**:`Loop` 自接點 C1-loopable==True(可安全重播,
     gap 0.19)**卻**在與鄰 beat 的接點(cascade→Loop、Loop→Out)C1 gap≈15 ≫ tol —— 因 Loop 端點正在呼吸擺動
     (端點速度≈15)而鄰 beat 近靜止到達/離開。故 `is_c1_loopable(Loop)` **不蘊含**序列在 Loop 兩側接點 C1。
     這是本 repo 通則「真簽章常需兩獨立條件並立 / 量在哪一層」在 loop↔序列層的又一實例。

**選題理由(不選又一條參數軸)**:延續 (L)/(L-2)/(L-3)/(L-4)/(G-2) 刻意選**整合 / 組合閘**。L-5 的客觀新不變量
= 相異接點 C1 連續(序列全程),L/L-4 的 C0 與自接點 C1 判準涵蓋不到。從**先驗庫 → 真實 build_spine robot
骨架 → build_animations** 端到端,與 L / L-3 / L-4 同一 fixture。

真值界定:大獎序列**是否該被設計成全程 C1** 屬美術手感(A 類);但「相異接點速度 gap」「序列 C0 連續但 C1
不連續」「自接點 C1 ⊬ 序列接點 C1」皆為**客觀可量測**不變量。正/負對照(① 共線切分的兩半 → 接點 C1≈0 閘
放行;② C0 連續但注入切線不符 → 閘抓出 C1 kick;③ 兩靜止 clip → C1 trivially 過但無運動 → 空驗守衛)證閘
既能放行真 C1、又能抓出 C0 看不到的頓挫、又不被靜止空驗騙過。

AC(客觀、可量測):
  S1 present+C0-recap+非空驗 : 正向序列每個相異接點 `c0_gap ≤ C0_TOL`(值無縫,可串接播放,L 複驗);接點**真有
                               運動**(接點兩側 max 端點速度 ≥ MOTION_VEL_THR,否則 C1 判準空驗);`sequence_seam_gaps`
                               良構(長度==len(order)-1、每項 finite)。
  S2 crux — metric 良定義    : 相異接點 C1 gap 對取樣步長 h 穩定(h∈{2e-3,1e-3,5e-4} 相對差 < H_REL_TOL)→ 單側
                               差分 = 端點**切線**,非有限差分 artifact;並**確認**須在 clip 端點層量 —— composed
                               時間軸的接點速度是 sampling/dedup 相依 artifact(≥1 接點 composed **低報**真 kick
                               達 SMEAR_MARGIN 以上)。
  S3 crux — 序列 C0 無縫但非 C1: 正向序列**全程** C0 無縫(每接點 c0_gap ≤ C0_TOL)**但每個**相異接點 c1_gap ≥
                               SEAM_KINK_MIN → `is_c1_continuous_sequence(order)`==False,且**非**因 C0(C0 全過)
                               → 證序列可無跳變播放卻仍逐接點頓挫;報告**最大 kick 接點**定位之。
  S4 crux — 自接點C1⊬序列接點C1: `Loop` `is_c1_loopable`==True(自接點 gap < VEL_SEAM_TOL,L-4)**但** Loop 的兩個
                               序列接點(cascade→Loop、Loop→Out)c1_gap ≥ SEAM_KINK_MIN,且 min(Loop 序列接點)/
                               Loop 自接點 ≥ SELF_INTER_RATIO_MIN → 證自接點 C1 **不蘊含**序列接點 C1(兩獨立不變量)。
  S5 pos+neg+空驗守衛        : (a) **正對照(放行力)**:共線切分 clip(rotate 0→10→20 於 t_m 切兩半)→ 接點 c0_gap≈0
                               且 c1_gap≈0(兩半共享 t_m 切線)→ `is_c1_continuous_sequence`==True → 證閘能**放行**
                               真 C1 接點(非恆判 False 的廢閘);
                               (b) **crux 負對照**:同前半 + 切線不符的後半(rotate 10→5)→ c0_gap≈0(值仍連續)
                               **但** c1_gap > VEL_SEAM_TOL 且 `is_c1_continuous_sequence`==False → 抓出 C0 看不到的
                               速度 kink;
                               (c) **空驗守衛**:兩靜止 clip → c0_gap==c1_gap==0 trivially「C1」且 is_c1_continuous==True
                               **但**接點兩側端點速度 ≈0 < MOTION_VEL_THR(無運動)→ 證「gap≤tol」必要不充分、須配
                               非靜止(呼應 L-4 C1e-b / L-3 LP4)。

用法:
  python3 validate_sequence_seam_c1.py            # 摘要
  python3 validate_sequence_seam_c1.py --json     # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"

H = 1e-3               # 接點速度單側差分步長
C0_TOL = 1e-6          # 接點 C0 值無縫上限(實測全 0)
VEL_SEAM_TOL = 1.0     # C1 接點速度 gap 上限(與 L-4 同;Loop 自接點 0.19 < 1 < 序列接點 ≥15)
SEAM_KINK_MIN = 10.0   # 真實序列每個相異接點須有的 C1 kick 下限(實測最小 cascade->Loop / Loop->Out 14.997)
MOTION_VEL_THR = 1.0   # 接點兩側須有的最小端點速度(非空驗)
H_REL_TOL = 1e-3       # gap 對 h 的相對穩定上限(實測最大 In->hit 5.8e-4)
SMEAR_MARGIN = 0.9     # composed 接點速度須對 ≥1 接點低報真 kick(composed < SMEAR_MARGIN × clip 端點 gap)
SELF_INTER_RATIO_MIN = 50.0  # min(Loop 序列接點 C1)/Loop 自接點 C1 須 ≥(實測 14.997/0.188 ≈ 80)

FORWARD = ["In", "hit", "combo", "charge", "cascade", "Loop", "Out"]


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/seq_seam_c1_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


# ---------------- 量測器 ----------------
def _endpoint_max_speed_start(clip, h=H):
    vs = G._state_velocity(clip, True, h)
    m = 0.0
    for d in vs["bones"].values():
        for v in d.values():
            m = max(m, abs(v))
    for d in vs["slots"].values():
        m = max(m, abs(d["alpha"]))
    return m


def _endpoint_max_speed_end(clip, h=H):
    ve = G._state_velocity(clip, False, h)
    m = 0.0
    for d in ve["bones"].values():
        for v in d.values():
            m = max(m, abs(v))
    for d in ve["slots"].values():
        m = max(m, abs(d["alpha"]))
    return m


def _seam_motion(anims, a, b, h=H):
    """接點兩側 max 端點速度(前 beat 尾 + 後 beat 首)。"""
    return max(_endpoint_max_speed_end(anims[a], h), _endpoint_max_speed_start(anims[b], h))


def _colinear_split(t_m=1.0):
    """共線 clip(rotate 0→10→20,全程同斜率)切成兩半 → 接點 C1 連續(切線相同)。"""
    ca = {"bones": {"b_身體": {"rotate": [{"time": 0.0, "angle": 0.0}, {"time": t_m, "angle": 10.0}]}}}
    cb = {"bones": {"b_身體": {"rotate": [{"time": 0.0, "angle": 10.0}, {"time": t_m, "angle": 20.0}]}}}
    return ca, cb


def _kink_after(t_m=1.0):
    """切線不符的後半(rotate 10→5):C0 值仍續(10==10)但切線反向 → C1 kink。"""
    return {"bones": {"b_身體": {"rotate": [{"time": 0.0, "angle": 10.0}, {"time": t_m, "angle": 5.0}]}}}


def _static(dur=2.0):
    return {"bones": {"b_身體": {"rotate": [{"time": 0.0, "angle": 0.0}, {"time": dur, "angle": 0.0}]}}}


# ---------------- AC ----------------
def ac_S1(anims):
    gaps = G.sequence_seam_gaps(anims, FORWARD, H)
    well_formed = (len(gaps) == len(FORWARD) - 1) and all(
        math.isfinite(g["c0_gap"]) and math.isfinite(g["c1_gap"]) for g in gaps)
    c0_all = all(g["c0_gap"] <= C0_TOL for g in gaps)
    motions = {g["seam"]: round(_seam_motion(anims, FORWARD[g["i"]], FORWARD[g["i"] + 1]), 4) for g in gaps}
    non_vacuous = all(m >= MOTION_VEL_THR for m in motions.values())
    ok = well_formed and c0_all and non_vacuous
    return {"pass": bool(ok), "n_seams": len(gaps), "well_formed": bool(well_formed),
            "c0_all_seamless": bool(c0_all), "c0_tol": C0_TOL,
            "seam_c0_gaps": {g["seam"]: round(g["c0_gap"], 9) for g in gaps},
            "seam_motions": motions, "non_vacuous": bool(non_vacuous), "motion_vel_thr": MOTION_VEL_THR}


def ac_S2(anims):
    # h-stability over all forward inter-beat seams
    rels = {}
    for i in range(len(FORWARD) - 1):
        a, b = FORWARD[i], FORWARD[i + 1]
        g = {h: G.seam_velocity_gap(anims[a], anims[b], h) for h in (2e-3, 1e-3, 5e-4)}
        base = g[1e-3]
        rels["{}->{}".format(a, b)] = (max(abs(v - base) for v in g.values()) / base) if base > 1e-12 else 0.0
    h_stable = all(r < H_REL_TOL for r in rels.values())
    # must-measure-at-clip-endpoint: composed wrap velocity under-reports the true clip-endpoint kink for ≥1 seam.
    composed, segs = G.compose_sequence(anims, FORWARD)
    eps = 1e-3

    def _comp_vel(t0, t1):
        s0, s1 = SA.sample(composed, t0), SA.sample(composed, t1)
        return G._state_max_diff(
            {"bones": {bn: {k: (s1["bones"].get(bn, G._LOOP_IDENT).get(k, G._LOOP_IDENT[k])
                                 - s0["bones"].get(bn, G._LOOP_IDENT).get(k, G._LOOP_IDENT[k])) / (t1 - t0)
                            for k in G._LOOP_IDENT} for bn in set(s0["bones"]) | set(s1["bones"])}, "slots": {}},
            {"bones": {}, "slots": {}})
    under = {}
    for i, s in enumerate(segs[1:], 1):
        t = s["start"]
        a, b = segs[i - 1]["beat"], s["beat"]
        comp_gap = abs(_comp_vel(t - eps, t) - _comp_vel(t, t + eps))
        clip_gap = G.seam_velocity_gap(anims[a], anims[b], H)
        under["{}->{}".format(a, b)] = {"composed": round(comp_gap, 4), "clip_endpoint": round(clip_gap, 4),
                                        "under_reports": bool(comp_gap < SMEAR_MARGIN * clip_gap)}
    any_under = any(v["under_reports"] for v in under.values())
    ok = h_stable and any_under
    return {"pass": bool(ok), "h_rel_spreads": {k: round(v, 9) for k, v in rels.items()},
            "h_stable": bool(h_stable), "h_rel_tol": H_REL_TOL,
            "composed_vs_clip": under, "composed_under_reports_somewhere": bool(any_under),
            "smear_margin": SMEAR_MARGIN}


def ac_S3(anims):
    gaps = G.sequence_seam_gaps(anims, FORWARD, H)
    c0_all = all(g["c0_gap"] <= C0_TOL for g in gaps)              # 全程 C0 無縫
    c1_all_kink = all(g["c1_gap"] >= SEAM_KINK_MIN for g in gaps)   # 每接點都有 C1 kink
    seq_c1 = G.is_c1_continuous_sequence(anims, FORWARD, C0_TOL, VEL_SEAM_TOL, H)
    not_c1_but_c0 = (not seq_c1) and c0_all                         # 非 C1 但確因速度(C0 全過)
    worst = max(gaps, key=lambda g: g["c1_gap"])
    ok = c0_all and c1_all_kink and not_c1_but_c0
    return {"pass": bool(ok), "seq_C0_seamless": bool(c0_all), "every_seam_kink": bool(c1_all_kink),
            "seam_kink_min": SEAM_KINK_MIN, "is_c1_continuous_sequence": bool(seq_c1),
            "not_c1_but_c0": bool(not_c1_but_c0),
            "seam_c1_gaps": {g["seam"]: round(g["c1_gap"], 3) for g in gaps},
            "worst_kink_seam": worst["seam"], "worst_kink_gap": round(worst["c1_gap"], 3)}


def ac_S4(anims):
    loop = anims["Loop"]
    self_c1 = G.loop_seam_velocity_gap(loop, H)
    loop_is_c1 = G.is_c1_loopable(loop)                 # 自接點 C1-loopable (L-4) True
    # Loop 的兩個序列接點
    into = G.seam_velocity_gap(anims["cascade"], loop, H)   # cascade -> Loop
    outof = G.seam_velocity_gap(loop, anims["Out"], H)      # Loop -> Out
    inter_min = min(into, outof)
    inter_kink = (into >= SEAM_KINK_MIN) and (outof >= SEAM_KINK_MIN)
    ratio = (inter_min / self_c1) if self_c1 > 1e-9 else float("inf")
    ratio_ok = ratio >= SELF_INTER_RATIO_MIN
    # 自接點 C1 但序列接點非 C1 → 兩獨立不變量
    independent = loop_is_c1 and inter_kink
    ok = loop_is_c1 and inter_kink and ratio_ok and independent
    return {"pass": bool(ok), "loop_self_seam_c1": round(self_c1, 4), "loop_is_c1_loopable": bool(loop_is_c1),
            "cascade_to_Loop_c1": round(into, 3), "Loop_to_Out_c1": round(outof, 3),
            "inter_both_kink": bool(inter_kink), "seam_kink_min": SEAM_KINK_MIN,
            "inter_over_self_ratio": round(ratio, 1), "ratio_min": SELF_INTER_RATIO_MIN,
            "self_and_inter_independent": bool(independent)}


def ac_S5(anims):
    # (a) 正對照:共線切分 → 接點 C1 連續,閘放行
    ca, cb = _colinear_split()
    pos = {"a": ca, "b": cb}
    pg = G.sequence_seam_gaps(pos, ["a", "b"], H)[0]
    pos_c1 = G.is_c1_continuous_sequence(pos, ["a", "b"], C0_TOL, VEL_SEAM_TOL, H)
    pos_speed = max(_endpoint_max_speed_end(ca, H), _endpoint_max_speed_start(cb, H))
    a_ok = (pg["c0_gap"] <= C0_TOL) and (pg["c1_gap"] <= VEL_SEAM_TOL) and pos_c1 and (pos_speed >= MOTION_VEL_THR)
    # (b) crux 負對照:C0 續但切線不符 → C1 kink,閘攔
    neg = {"a": ca, "b": _kink_after()}
    ng = G.sequence_seam_gaps(neg, ["a", "b"], H)[0]
    neg_c1 = G.is_c1_continuous_sequence(neg, ["a", "b"], C0_TOL, VEL_SEAM_TOL, H)
    b_ok = (ng["c0_gap"] <= C0_TOL) and (ng["c1_gap"] > VEL_SEAM_TOL) and (not neg_c1)
    # (c) 空驗守衛:兩靜止 clip → trivially C1 但無運動
    st = {"a": _static(), "b": _static()}
    sg = G.sequence_seam_gaps(st, ["a", "b"], H)[0]
    st_c1 = G.is_c1_continuous_sequence(st, ["a", "b"], C0_TOL, VEL_SEAM_TOL, H)
    st_speed = max(_endpoint_max_speed_end(st["a"], H), _endpoint_max_speed_start(st["b"], H))
    c_ok = (sg["c0_gap"] <= 1e-9) and (sg["c1_gap"] <= 1e-9) and st_c1 and (st_speed < MOTION_VEL_THR)
    ok = a_ok and b_ok and c_ok
    return {"pass": bool(ok),
            "a_positive_colinear": {"pass": bool(a_ok), "c0_gap": round(pg["c0_gap"], 9),
                                    "c1_gap": round(pg["c1_gap"], 9), "is_c1_continuous": bool(pos_c1),
                                    "endpoint_speed": round(pos_speed, 4)},
            "b_neg_c0_ok_c1_kink": {"pass": bool(b_ok), "c0_gap": round(ng["c0_gap"], 9),
                                    "c1_gap": round(ng["c1_gap"], 4), "is_c1_continuous": bool(neg_c1),
                                    "note": "C0 連續(10==10)但切線反向 → C1 kink,C0 看不到"},
            "c_static_vacuity": {"pass": bool(c_ok), "c0_gap": round(sg["c0_gap"], 9),
                                 "c1_gap": round(sg["c1_gap"], 9), "is_c1_continuous": bool(st_c1),
                                 "endpoint_speed": round(st_speed, 9),
                                 "note": "gap=0 trivially C1 但無運動 → gap≤tol 必要不充分"}}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    missing = [nm for nm in FORWARD if nm not in anims]
    if missing:
        return {"overall_pass": False, "error": "missing beats in fixture: {}".format(missing),
                "available": sorted(anims.keys())}
    results = {"S1_present_C0recap_nonvacuous": ac_S1(anims),
               "S2_crux_metric_welldefined": ac_S2(anims),
               "S3_crux_seq_C0_seamless_but_not_C1": ac_S3(anims),
               "S4_crux_selfC1_not_imply_seqC1": ac_S4(anims),
               "S5_pos_neg_vacuity_guard": ac_S5(anims)}
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
        print("candidate (L-5) 相異 beat 接點 C1(速度)連續閘 — seam_velocity_gap + sequence_seam_gaps + is_c1_continuous_sequence")
        for k in ["S1_present_C0recap_nonvacuous", "S2_crux_metric_welldefined",
                  "S3_crux_seq_C0_seamless_but_not_C1", "S4_crux_selfC1_not_imply_seqC1",
                  "S5_pos_neg_vacuity_guard"]:
            v = res.get(k, {})
            print("  {:36s} {}".format(k, "PASS" if v.get("pass") else "FAIL"))
        if "error" in res:
            print("  ERROR:", res["error"])
        if "S3_crux_seq_C0_seamless_but_not_C1" in res:
            p = res["S3_crux_seq_C0_seamless_but_not_C1"]
            print("    seq C0-seamless={} | is_c1_continuous={} | seam C1 gaps={} | worst={}@{}".format(
                p["seq_C0_seamless"], p["is_c1_continuous_sequence"], p["seam_c1_gaps"],
                p["worst_kink_gap"], p["worst_kink_seam"]))
        if "S4_crux_selfC1_not_imply_seqC1" in res:
            p = res["S4_crux_selfC1_not_imply_seqC1"]
            print("    Loop self-seam C1={} (is_c1_loopable={}) | cascade->Loop={} Loop->Out={} | ratio={}x".format(
                p["loop_self_seam_c1"], p["loop_is_c1_loopable"], p["cascade_to_Loop_c1"],
                p["Loop_to_Out_c1"], p["inter_over_self_ratio"]))
        if "S5_pos_neg_vacuity_guard" in res:
            p = res["S5_pos_neg_vacuity_guard"]
            print("    pos colinear c1={} (continuous={}) | neg kink c1={} (continuous={}) | static c1={} speed={}".format(
                p["a_positive_colinear"]["c1_gap"], p["a_positive_colinear"]["is_c1_continuous"],
                p["b_neg_c0_ok_c1_kink"]["c1_gap"], p["b_neg_c0_ok_c1_kink"]["is_c1_continuous"],
                p["c_static_vacuity"]["c1_gap"], p["c_static_vacuity"]["endpoint_speed"]))
        print("OVERALL:", "PASS" if res.get("overall_pass") else "FAIL")
    return 0 if res.get("overall_pass") else 1


if __name__ == "__main__":
    sys.exit(main())
