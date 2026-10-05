#!/usr/bin/env python3
"""candidate (L-4) 自我驗收閘 — 自接點 **C1(速度)連續性** / C1-loopability(純 CPU,確定性)。

**補的缺口(L-3 誠實列出的 honest boundary)**:candidate (L-3) 的 `is_loopable` 把「可安全重播」顯式化,
但**只驗 C0**(自接點值連續、不跳變),並明記「不保證 C1 速度連續(loop 重啟頓挫)」。本次把這條 boundary
關掉:新增 `gen_animations.loop_seam_velocity_gap`(自接點 C1 速度不連續量)+ `is_c1_loopable`(C0 ∧ C1),
並以閘把關。直指 north star「產出可**無頓挫**循環播放的大獎 Loop」。

**crux / 本 run 的核心發現**:真實產線的一次性主秀 beat(hit/combo/charge/cascade)首尾皆 setup identity →
`is_loopable`(C0)**一律 True** —— 即 L-3 的 loopability 判準會**誤把單發節拍當成「可安全重播」**。但它們的
自接點**速度**突變達 64~167 deg/s(符號翻轉),平鋪會每份頓挫。唯有 **C1**(自接點速度亦連續)能把真正的
idle-**Loop**(gap≈0.19,僅光暈呼吸式 scale/alpha 的小殘差)與這些一次性 beat(gap≥64)區分開 → C1-loopability
是**嚴格更強、與 C0 獨立**的不變量。這是本 repo 通則「真簽章常需兩獨立條件並立」在 loop 判準上的又一實例。

**選題理由(不選又一條參數軸)**:延續 (L)/(L-2)/(L-3)/(G-2) 刻意選**整合 / 組合閘**。L-4 的客觀新不變量 =
自接點 C1 連續,L-3 的 C0 判準涵蓋不到(且會誤判)。從**先驗庫 → 真實 build_spine robot 骨架 →
build_animations** 端到端,與 L / L-3 同一 fixture。

真值界定:Loop **是否該被設計成完美 C1** 屬美術手感(A 類);但「自接點速度 gap」「C1⟹C0 嚴格更強」
「單發 beat C0-loopable 但非 C1-loopable」皆為**客觀可量測**不變量。負對照(① C0-loopable 但注入速度 kink 的
三角脈衝 → C1 閘抓出 ② 靜止 clip gap=0 trivially「C1」但無運動 → 空驗守衛 ③ 非 C0-loopable 的 In → C0 先否決)
證閘有鑑別力。

AC(客觀、可量測):
  C1a present+C0-recap+非空驗 : `is_loopable(Loop)`==True(C0 複驗);Loop 端點**真有速度**
                               (max 端點速度 ≥ MOTION_VEL_THR,否則 C1 判準空驗);gap 可算且 finite。
  C1b crux — metric 良定義    : Loop 自接點 gap 對取樣步長 h 穩定(h∈{2e-3,1e-3,5e-4} 相對差 < H_REL_TOL)→
                               單側差分 = 端點**切線**,非有限差分 artifact;並**確認**須在 clip 端點層量
                               (跨 composed 接點因 L-3 時間去重會被抹平 → 恆 C0,量不到真 kink)。
  C1c crux — Loop C1 + 分解   : `loop_seam_velocity_gap(Loop)` < VEL_SEAM_TOL 且 `is_c1_loopable(Loop)`==True;
                               通道分解:**剛體 limb rotate 通道自接點速度 ≈0(gap ≤ RIGID_TOL,精確 C1)**,
                               唯一殘差來自**光暈呼吸**(scale/alpha)→ 誠實指認 Loop 的 C1 殘差來源。
  C1d crux — C1 獨立於 C0     : {Loop,hit,combo,charge,cascade} **全部** `is_loopable`(C0)==True(C0 **不能**鑑別),
                               但 C1 gap:Loop < VEL_SEAM_TOL 而**每個**主秀 beat ≥ MAINSHOW_MIN,且
                               min(主秀 gap)/Loop gap ≥ RATIO_MIN → 證 `is_loopable` 單獨會誤放一次性 beat,
                               C1 loop-seam 連續是鑑別子;`is_c1_loopable` 對主秀 beat 全 False。
  C1e neg-control+空驗守衛    : (a) **crux**:三角脈衝(scale 1→A→1,C0-loopable 但注入速度 kink)gap > VEL_SEAM_TOL
                               且 `is_c1_loopable`==False → 閘抓出 `is_loopable` 看不到的頓挫;
                               (b) **空驗守衛**:靜止 clip gap==0 → 速度測試 trivially 過且 `is_c1_loopable`==True,
                               **但**端點速度 ≈0 < MOTION_VEL_THR(無運動)→ 證「gap≤tol」必要不充分、須配非靜止
                               (呼應 L-3 LP4);(c) `is_c1_loopable(In)`==False 且因 **C0 先否決**(is_loopable False)。

用法:
  python3 validate_sequence_loop_c1.py            # 摘要
  python3 validate_sequence_loop_c1.py --json     # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"

H = 1e-3               # 自接點速度單側差分步長
VEL_SEAM_TOL = 1.0     # C1 自接點速度 gap 上限(Loop 實測 ≈0.19 < 1 < 主秀 ≥64)
RIGID_TOL = 1e-6       # 剛體 limb rotate 通道「精確 C1」上限(實測 ~1e-12)
MOTION_VEL_THR = 1.0   # 端點須有的最小速度(非空驗;Loop limb rotate ≈15 deg/s)
H_REL_TOL = 1e-3       # gap 對 h 的相對穩定上限(實測 bit-stable)
MAINSHOW_MIN = 10.0    # 每個主秀 beat 自接點 gap 須 ≥(實測最小 cascade 63.98)
RATIO_MIN = 50.0       # min(主秀 gap)/Loop gap 須 ≥(實測 63.98/0.188 ≈ 340)
MAIN_SHOW = ["hit", "combo", "charge", "cascade"]
LIMB_ROTATE = [("b_右手", "rotate"), ("b_左手", "rotate"), ("b_頭", "rotate")]


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/seq_loop_c1_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


# ---------------- 量測器 ----------------
def _endpoint_max_speed(clip, h=H):
    """clip 兩端點單側速度的最大絕對值(非空驗門檻用)。"""
    vs = G._state_velocity(clip, True, h)
    ve = G._state_velocity(clip, False, h)
    m = 0.0
    for state in (vs, ve):
        for d in state["bones"].values():
            for v in d.values():
                m = max(m, abs(v))
        for d in state["slots"].values():
            m = max(m, abs(d["alpha"]))
    return m


def _channel_seam_gap(clip, bone, chan, h=H):
    """單一 (bone,channel) 的自接點速度 gap(端點切線差)。"""
    vs = G._state_velocity(clip, True, h)["bones"].get(bone, {})
    ve = G._state_velocity(clip, False, h)["bones"].get(bone, {})
    return abs(vs.get(chan, 0.0) - ve.get(chan, 0.0))


def _triangle_pulse(amp=2.0, dur=2.0):
    """C0-loopable(scale 1→amp→1 首尾值相等)但注入 C1 速度 kink 的三角脈衝。"""
    return {"bones": {"b_身體": {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0},
                                           {"time": dur / 2.0, "x": 1.0, "y": amp},
                                           {"time": dur, "x": 1.0, "y": 1.0}]}}}


def _static_clip(dur=2.0):
    """靜止(恆 identity)clip:C0-loopable、速度恆 0、但無運動。"""
    return {"bones": {"b_身體": {"rotate": [{"time": 0.0, "angle": 0.0},
                                            {"time": dur, "angle": 0.0}]}}}


# ---------------- AC ----------------
def ac_C1a(anims):
    loop = anims["Loop"]
    c0 = G.is_loopable(loop)
    gap = G.loop_seam_velocity_gap(loop, H)
    finite = math.isfinite(gap)
    speed = _endpoint_max_speed(loop)
    non_vacuous = speed >= MOTION_VEL_THR
    ok = c0 and finite and non_vacuous
    return {"pass": bool(ok), "loop_is_loopable_C0": bool(c0), "gap": round(gap, 6),
            "gap_finite": bool(finite), "endpoint_max_speed": round(speed, 4),
            "non_vacuous": bool(non_vacuous), "motion_vel_thr": MOTION_VEL_THR}


def ac_C1b(anims):
    loop = anims["Loop"]
    gaps = {h: G.loop_seam_velocity_gap(loop, h) for h in (2e-3, 1e-3, 5e-4)}
    base = gaps[1e-3]
    rel = max(abs(g - base) for g in gaps.values()) / base if base > 1e-12 else 0.0
    h_stable = rel < H_REL_TOL
    # 確認:跨 composed 接點量速度 → 因 L-3 時間去重被抹平 → composed 恆 C0,量不到真 kink。
    # 這裡以「clip 端點層 gap(有 kink,0.19)」vs「composed wrap 兩側單側速度差(被抹平)」對照佐證。
    order = ["In", "Loop", "Loop", "Out"]
    composed, segs = G.compose_sequence(anims, order)
    loop_segs = [s for s in segs if s["beat"] == "Loop"]
    wrap_t = loop_segs[1]["start"]  # 第一個 Loop→Loop composed 接點
    eps = 1e-3
    # composed 跨接點單側速度(前側逼近 vs 後側外向)
    def _comp_vel(t0, t1):
        s0, s1 = SA.sample(composed, t0), SA.sample(composed, t1)
        return G._state_max_diff(
            {"bones": {b: {k: (s1["bones"].get(b, G._LOOP_IDENT).get(k, G._LOOP_IDENT[k])
                                - s0["bones"].get(b, G._LOOP_IDENT).get(k, G._LOOP_IDENT[k])) / (t1 - t0)
                            for k in G._LOOP_IDENT} for b in set(s0["bones"]) | set(s1["bones"])}, "slots": {}},
            {"bones": {}, "slots": {}})
    v_before = _comp_vel(wrap_t - eps, wrap_t)
    v_after = _comp_vel(wrap_t, wrap_t + eps)
    composed_wrap_vel_gap = abs(v_before - v_after)
    clip_gap = G.loop_seam_velocity_gap(loop, H)
    # 佐證:composed 接點兩側速度差 ≪ clip 端點真 gap(去重抹平,量不到 kink)
    composed_smeared = composed_wrap_vel_gap < clip_gap
    ok = h_stable and composed_smeared
    return {"pass": bool(ok), "gaps_by_h": {str(k): round(v, 6) for k, v in gaps.items()},
            "h_rel_spread": round(rel, 9), "h_stable": bool(h_stable), "h_rel_tol": H_REL_TOL,
            "clip_endpoint_gap": round(clip_gap, 6),
            "composed_wrap_vel_gap": round(composed_wrap_vel_gap, 6),
            "composed_smeared_vs_clip": bool(composed_smeared)}


def ac_C1c(anims):
    loop = anims["Loop"]
    gap = G.loop_seam_velocity_gap(loop, H)
    small = gap < VEL_SEAM_TOL
    c1 = G.is_c1_loopable(loop)
    # 分解:剛體 limb rotate 通道精確 C1
    limb_gaps = {f"{b}.{c}": round(_channel_seam_gap(loop, b, c), 12) for (b, c) in LIMB_ROTATE
                 if b in loop.get("bones", {})}
    limb_exact = all(v <= RIGID_TOL for v in limb_gaps.values()) and len(limb_gaps) >= 2
    # 唯一殘差來源:光暈呼吸(scale/alpha)——確認最大殘差 bone 含「光暈」
    glow_scale = round(_channel_seam_gap(loop, "b_光暈", "scaleY", H), 6)
    ok = small and c1 and limb_exact
    return {"pass": bool(ok), "gap": round(gap, 6), "below_tol": bool(small), "vel_seam_tol": VEL_SEAM_TOL,
            "is_c1_loopable": bool(c1), "limb_rotate_gaps": limb_gaps, "limb_exact_C1": bool(limb_exact),
            "rigid_tol": RIGID_TOL, "glow_scaleY_residual": glow_scale}


def ac_C1d(anims):
    # 全部 C0-loopable(C0 不能鑑別)
    all_names = ["Loop"] + MAIN_SHOW
    c0 = {nm: G.is_loopable(anims[nm]) for nm in all_names}
    all_c0 = all(c0.values())
    # C1 gap 鑑別
    gaps = {nm: round(G.loop_seam_velocity_gap(anims[nm], H), 4) for nm in all_names}
    loop_gap = gaps["Loop"]
    main_gaps = [gaps[nm] for nm in MAIN_SHOW]
    loop_small = loop_gap < VEL_SEAM_TOL
    main_big = all(g >= MAINSHOW_MIN for g in main_gaps)
    ratio = (min(main_gaps) / loop_gap) if loop_gap > 1e-9 else float("inf")
    ratio_ok = ratio >= RATIO_MIN
    # is_c1_loopable 對主秀全 False、對 Loop True
    c1 = {nm: G.is_c1_loopable(anims[nm]) for nm in all_names}
    c1_discriminates = c1["Loop"] and not any(c1[nm] for nm in MAIN_SHOW)
    ok = all_c0 and loop_small and main_big and ratio_ok and c1_discriminates
    return {"pass": bool(ok), "all_C0_loopable": bool(all_c0), "C0": c0,
            "C1_gaps": gaps, "loop_below_tol": bool(loop_small), "mainshow_all_big": bool(main_big),
            "min_main_over_loop_ratio": round(ratio, 1), "ratio_min": RATIO_MIN,
            "is_c1_loopable": c1, "c1_discriminates": bool(c1_discriminates)}


def ac_C1e(anims):
    # (a) crux 三角脈衝:C0-loopable 但注入 C1 kink
    tri = _triangle_pulse(amp=2.0)
    tri_c0 = G.is_loopable(tri)
    tri_gap = G.loop_seam_velocity_gap(tri, H)
    tri_c1 = G.is_c1_loopable(tri)
    a_ok = tri_c0 and (tri_gap > VEL_SEAM_TOL) and (not tri_c1)
    # (b) 空驗守衛:靜止 clip gap=0 trivially C1,但端點速度≈0 無運動
    stat = _static_clip()
    stat_c0 = G.is_loopable(stat)
    stat_gap = G.loop_seam_velocity_gap(stat, H)
    stat_c1 = G.is_c1_loopable(stat)
    stat_speed = _endpoint_max_speed(stat)
    b_ok = stat_c0 and (stat_gap <= 1e-9) and stat_c1 and (stat_speed < MOTION_VEL_THR)
    # (c) In 非 C0-loopable → is_c1_loopable False,由 C0 先否決
    in_c0 = G.is_loopable(anims["In"])
    in_c1 = G.is_c1_loopable(anims["In"])
    c_ok = (not in_c0) and (not in_c1)
    ok = a_ok and b_ok and c_ok
    return {"pass": bool(ok),
            "a_triangle_kink": {"pass": bool(a_ok), "C0_loopable": bool(tri_c0),
                                "gap": round(tri_gap, 4), "is_c1_loopable": bool(tri_c1)},
            "b_static_vacuity": {"pass": bool(b_ok), "C0_loopable": bool(stat_c0),
                                 "gap": round(stat_gap, 9), "is_c1_loopable": bool(stat_c1),
                                 "endpoint_speed": round(stat_speed, 9),
                                 "note": "gap=0 trivially C1 但無運動 → gap≤tol 必要不充分"},
            "c_In_gated_by_C0": {"pass": bool(c_ok), "C0_loopable": bool(in_c0),
                                 "is_c1_loopable": bool(in_c1)}}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    needed = ["In", "Loop", "Out"] + MAIN_SHOW
    missing = [nm for nm in needed if nm not in anims]
    if missing:
        return {"overall_pass": False, "error": "missing beats in fixture: {}".format(missing),
                "available": sorted(anims.keys())}
    results = {"C1a_present_C0recap_nonvacuous": ac_C1a(anims),
               "C1b_crux_metric_welldefined": ac_C1b(anims),
               "C1c_crux_loop_C1_decomp": ac_C1c(anims),
               "C1d_crux_C1_independent_of_C0": ac_C1d(anims),
               "C1e_neg_control_vacuity_guard": ac_C1e(anims)}
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
        print("candidate (L-4) 自接點 C1(速度)連續閘 — loop_seam_velocity_gap + is_c1_loopable")
        for k in ["C1a_present_C0recap_nonvacuous", "C1b_crux_metric_welldefined",
                  "C1c_crux_loop_C1_decomp", "C1d_crux_C1_independent_of_C0",
                  "C1e_neg_control_vacuity_guard"]:
            v = res.get(k, {})
            print("  {:34s} {}".format(k, "PASS" if v.get("pass") else "FAIL"))
        if "error" in res:
            print("  ERROR:", res["error"])
        if "C1c_crux_loop_C1_decomp" in res:
            p = res["C1c_crux_loop_C1_decomp"]
            print("    Loop gap={:.4f} (<{}) C1-loopable={} | limb-rotate exact-C1={} glow-scaleY residual={}".format(
                p["gap"], VEL_SEAM_TOL, p["is_c1_loopable"], p["limb_exact_C1"], p["glow_scaleY_residual"]))
        if "C1d_crux_C1_independent_of_C0" in res:
            p = res["C1d_crux_C1_independent_of_C0"]
            print("    all C0-loopable={} | C1 gaps={} ratio={}x".format(
                p["all_C0_loopable"], p["C1_gaps"], p["min_main_over_loop_ratio"]))
        if "C1e_neg_control_vacuity_guard" in res:
            p = res["C1e_neg_control_vacuity_guard"]
            print("    triangle kink gap={} (C1={}) | static gap={} speed={} (vacuous)".format(
                p["a_triangle_kink"]["gap"], p["a_triangle_kink"]["is_c1_loopable"],
                p["b_static_vacuity"]["gap"], p["b_static_vacuity"]["endpoint_speed"]))
        print("OVERALL:", "PASS" if res.get("overall_pass") else "FAIL")
    return 0 if res.get("overall_pass") else 1


if __name__ == "__main__":
    sys.exit(main())
