#!/usr/bin/env python3
"""candidate (L-5) 自我驗收閘 — 跨 beat **混場 / crossfade(時間重疊 + 權重混合)**(純 CPU,確定性)。

**補的缺口(L 誠實列出的 honest boundary)**:candidate (L) 的 `compose_sequence` 只做**純時間平移 + 接點
去重**(C0 拼接)—— 相鄰 beat 在接點值相等(無縫序列)才無損;接點值**不等**(A 尾 ≠ B 首)就會留一個
C0 跳變(pop),compose 的純平移做不到「把兩支在一段時間窗內同時播並以權重混合」。真實遊戲轉場用的是
**crossfade / mix**。本次補上這個 mix 機制:`gen_animations.crossfade_state`(混場取樣,ground truth 混合律)
+ `crossfade`(產出單一可載入的混場 clip)+ `crossfade_weight`(過渡權重)。直指 north star「序列組合的下一
組合層 = 真正的時間重疊混合,而非拼接」。

**crux / 本 run 的核心發現**:即使 **A 尾 ≠ B 首**(真實 C0 不連續,拼接會 pop),crossfade 在整段仍 **C0 連續**
—— pop 被攤平到 mix 窗(寬度 = mix_dur,一個可調旋鈕);而對同一不連續接點做**硬切**(hard cut:t<接點取 A、
t≥接點取 B)則留一個**與取樣步長 eps 無關**的真跳變(step)。這把「混場把不連續攤成連續」客觀量化:crossfade
的接點兩側差 `|s(seam−eps)−s(seam+eps)|` 隨 eps→0 **線性縮小→0**,hard cut 則**恆 ≈ J**(跳變量)。

**選題理由(不選又一條參數軸)**:延續 (L)/(L-2)/(L-3)/(L-4) 刻意選**整合 / 組合閘**。L-5 的客觀新機制 =
時間重疊權重混合(crossfade),是 compose 的**純平移拼接做不到**的下一組合層。從**先驗庫 → 真實 build_spine
robot 骨架 → build_animations** 端到端,與 L / L-3 / L-4 同一 fixture。A = **Out**(identity→collapsed,尾為
**非** identity),B = **Loop**(起於 identity)→ 接點 A 尾 ≠ B 首,**真有不連續**(J≈25),混場才有意義。

真值界定:mix_dur / 權重曲線 / 用在哪兩支 beat 之間屬**美術手感**(A 類);但「混場端點銜接 A→B」「整段 C0
連續」「hard cut 留 eps-無關跳變」「peak 過渡速度 ∝ 1/mix_dur(mix 是平滑旋鈕)」「mix=0 退化為拼接」皆為
**客觀可量測**不變量。負對照(① hard cut 同接點留真 step ② 無縫對 hit→Loop 的 J<DISCONT → C0 宣稱空驗、
須配不連續 fixture ③ 非法 mix_dur/空 clip 觸 ValueError)證閘有鑑別力。

AC(客觀、可量測):
  X1 present+backward-compat+非空驗 : `crossfade(Out,Loop,mix)` 產有限可載入 clip,時長==dur_A+dur_B−mix_dur;
                                      `mix=0` **bit-identical** `compose_sequence([Out,Loop])`(退化=拼接);
                                      接點不連續 J≥DISCONT_MIN(非空驗:真有 pop 要攤平)。
  X2 crux — 端點銜接 + 純區保真     : 窗首 t=w0 的混場態 == 孤立 `sample(Out,w0)`(w=0 純 A)、窗尾 t=dur_A
                                      == 孤立 `sample(Loop,mix)`(w=1 純 B),殘差 ≤ ENDPOINT_TOL;純 A 區在 Out
                                      原關鍵幀時間節點上 bone 通道逐位元還原孤立 Out(≤NODE_BONE_TOL)、純 B 區
                                      數點還原孤立 Loop(≤PURE_TOL)→ mix 侷限於窗內,兩端純播無損。
  X3 crux — 不連續接點 C0 vs 硬切   : J≥DISCONT_MIN;crossfade 接點差隨 eps∈{1e-3,1e-4}**線性縮小**(ratio≥SHRINK_MIN)
                                      且 ≤C0_STEP_TOL(→ C0 連續,pop 被攤平);**同一接點硬切**差對 eps **恆 ≈J**
                                      (ratio≈1、≥HARDCUT_MIN)→ 真 step。證 crossfade 消掉了硬切留下的 pop。
  X4 — 混合律 + 權重 + steps 收斂   : 線性 τ=0.5 混場態 == 0.5·(A⊕B) 精確(≤1e-9);`crossfade_weight` 線性/
                                      smoothstep 皆單調且端點 0/1 精確;窗內節點上 comp bone 通道逐位元==混合律
                                      (≤NODE_BONE_TOL)、slot ≤COLOR_QUANT;重取樣 steps 8→32→128 全程逼近誤差
                                      **嚴格遞減**(格點近似收斂,honest boundary 量化)。
  X5 neg-control + 空驗守衛 + 守衛  : (a) **可調旋鈕** peak 過渡速度 mix=0.1 / mix=0.2 ∈[RATIO_LO,RATIO_HI](≈2×,
                                      mix 愈小愈陡 → mix 是 compose 沒有的平滑旋鈕);(b) **空驗守衛** 無縫對
                                      hit→Loop 的 J<SEAMLESS_MAX → 其 C0 宣稱空驗,證 X3 的 crux 須配不連續 fixture;
                                      (c) 非法 mix_dur(>min 時長 / <0)與空 clip 皆觸 ValueError。

用法:
  python3 validate_sequence_crossfade.py          # 摘要
  python3 validate_sequence_crossfade.py --json    # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"

STEPS = 32
MIX1 = 0.1             # 小 mix 窗(Out dur=0.4,≤min)
MIX2 = 0.2             # 大 mix 窗
DISCONT_MIN = 5.0      # Out→Loop 接點不連續量下限(實測 J≈25)
SEAMLESS_MAX = 1.0     # 無縫對 hit→Loop 接點量上限(實測 ≈0)
ENDPOINT_TOL = 0.01    # 端點銜接殘差上限(含 8-bit alpha 量化 1/255≈0.004)
PURE_TOL = 0.01        # 純區保真殘差上限
NODE_BONE_TOL = 1e-6   # 窗內/純區節點上 bone 通道逐位元還原上限
COLOR_QUANT = 1.0 / 255 + 1e-6  # slot alpha 8-bit 量化
C0_EPS = (1e-3, 1e-4)  # C0 連續性量測的兩個 eps
C0_STEP_TOL = 0.05     # crossfade 接點差上限(eps=1e-3 時實測 ≤0.1→用 1e-4 收斂)
SHRINK_MIN = 5.0       # crossfade 接點差隨 eps 線性縮小比下限(1e-3→1e-4 應 ≈10×)
HARDCUT_MIN = 0.9      # hard cut 接點差 / J 下限(真 step,恆 ≈J)
RATIO_LO, RATIO_HI = 1.7, 2.6   # peak(mix=0.1)/peak(mix=0.2) 控制性比值區間(≈2×)


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
def _jump(clipA, clipB):
    """接點不連續量 = |A 尾 − B 首|(clip 端點層,非 composed —— 呼應 L-3:composed 去重會抹平)。"""
    return G._state_max_diff(SA.sample(clipA, SA.duration(clipA)), SA.sample(clipB, 0.0))


def _bone_only_diff(s1, s2):
    """只比 bone 通道的最大差(排除 slot 的 8-bit 量化,量 bone 的真逐位元還原)。"""
    m = 0.0
    for b in set(s1["bones"]) | set(s2["bones"]):
        d1 = s1["bones"].get(b, G._LOOP_IDENT)
        d2 = s2["bones"].get(b, G._LOOP_IDENT)
        for k in G._LOOP_IDENT:
            m = max(m, abs(d1.get(k, G._LOOP_IDENT[k]) - d2.get(k, G._LOOP_IDENT[k])))
    return m


def _slot_only_diff(s1, s2):
    m = 0.0
    for s in set(s1["slots"]) | set(s2["slots"]):
        a1 = s1["slots"].get(s, {"alpha": 1.0})["alpha"]
        a2 = s2["slots"].get(s, {"alpha": 1.0})["alpha"]
        m = max(m, abs(a1 - a2))
    return m


def _seam_step(clip, seam, eps):
    """clip 在 seam 兩側 ±eps 的狀態差(C0 連續 → 隨 eps→0;真 step → eps-無關)。"""
    return G._state_max_diff(SA.sample(clip, seam - eps), SA.sample(clip, seam + eps))


def _hardcut_step(clipA, clipB, seam, eps):
    """硬切取樣器(t<seam 取 A、否則取 B,local=t−seam)在 seam 兩側的差。"""
    def hc(t):
        return SA.sample(clipA, t) if t < seam else SA.sample(clipB, t - seam)
    return G._state_max_diff(hc(seam - eps), hc(seam + eps))


def _peak_speed(clip, a, b, h=1e-4, n=600):
    """[a,b] 區間內單側有限差分速度的最大值(過渡陡峭度)。"""
    m = 0.0
    for i in range(n):
        t = a + (b - a) * i / n
        m = max(m, G._state_max_diff(SA.sample(clip, t), SA.sample(clip, t + h)) / h)
    return m


def _interp_err(clipA, clipB, mix, steps, weight="linear", n=500):
    """重取樣 clip 與 ground-truth 混合律在稠密點的最大差(格點近似誤差)。"""
    comp, info = G.crossfade(clipA, clipB, mix, steps=steps, weight=weight)
    m = 0.0
    for i in range(1, n):
        t = info["total"] * i / n
        m = max(m, G._state_max_diff(SA.sample(comp, t), G.crossfade_state(clipA, clipB, mix, t, weight)))
    return m


# ---------------- AC ----------------
def ac_X1(A, B):
    comp, info = G.crossfade(A, B, MIX2, steps=STEPS)
    dur_ok = abs(SA.duration(comp) - info["total"]) <= 1e-6
    total_ok = abs(info["total"] - (SA.duration(A) + SA.duration(B) - MIX2)) <= 1e-9
    finite = SA.all_finite(comp)
    # backward-compat: mix=0 == compose
    c0, _ = G.crossfade(A, B, 0.0)
    cc, _ = G.compose_sequence({"__A": A, "__B": B}, ["__A", "__B"])
    bitident = json.dumps(c0, sort_keys=True) == json.dumps(cc, sort_keys=True)
    J = _jump(A, B)
    nonvac = J >= DISCONT_MIN
    ok = dur_ok and total_ok and finite and bitident and nonvac
    return {"pass": bool(ok), "duration_matches_total": bool(dur_ok), "total": info["total"],
            "finite": bool(finite), "nkeys": info["nkeys"], "mix0_bitident_compose": bool(bitident),
            "jump_J": round(J, 4), "nonvacuous_discont": bool(nonvac), "discont_min": DISCONT_MIN}


def ac_X2(A, B):
    comp, info = G.crossfade(A, B, MIX2, steps=STEPS)
    w0, dA = info["w0"], info["dur_a"]
    # 端點銜接
    r_start = G._state_max_diff(SA.sample(comp, w0), SA.sample(A, w0))
    r_end = G._state_max_diff(SA.sample(comp, dA), SA.sample(B, MIX2))
    ends_ok = r_start <= ENDPOINT_TOL and r_end <= ENDPOINT_TOL
    # 純 A 區:Out 原關鍵幀時間(<w0)bone 通道逐位元還原
    akt = [t for t in sorted(G._clip_key_times(A)) if t < w0 - 1e-6]
    pureA = max((_bone_only_diff(SA.sample(comp, t), SA.sample(A, t)) for t in akt), default=0.0)
    pureA_ok = pureA <= NODE_BONE_TOL
    # 純 B 區:數點還原孤立 Loop
    bpts = [dA + 0.2 + 0.4 * k for k in range(4)]
    pureB = max(G._state_max_diff(SA.sample(comp, t), SA.sample(B, t - w0)) for t in bpts)
    pureB_ok = pureB <= PURE_TOL
    ok = ends_ok and pureA_ok and pureB_ok
    return {"pass": bool(ok), "window_start_residual": round(r_start, 6),
            "window_end_residual": round(r_end, 6), "endpoints_ok": bool(ends_ok),
            "pureA_keynode_bonediff": round(pureA, 9), "pureA_ok": bool(pureA_ok),
            "pureB_residual": round(pureB, 6), "pureB_ok": bool(pureB_ok),
            "endpoint_tol": ENDPOINT_TOL, "node_bone_tol": NODE_BONE_TOL}


def ac_X3(A, B):
    J = _jump(A, B)
    discont = J >= DISCONT_MIN
    comp, info = G.crossfade(A, B, MIX2, steps=STEPS)
    seam = info["dur_a"]
    cf = {e: _seam_step(comp, seam, e) for e in C0_EPS}
    # C0 判準:(i) 最小 eps 的接點差已小(連續,非 step);(ii) 隨 eps **線性縮小**(10× eps → ≈10× 小)。
    # 較大 eps 的接點差 = 端點切線斜率 × 2eps(有限、遞減),不應拿來當「跳變」門檻 —— 真 step 才 eps-無關。
    cf_small = cf[C0_EPS[1]] <= C0_STEP_TOL
    cf_shrink = (cf[C0_EPS[0]] / cf[C0_EPS[1]]) if cf[C0_EPS[1]] > 1e-12 else float("inf")
    cf_c0 = cf_small and cf_shrink >= SHRINK_MIN   # 隨 eps 線性縮小 → 連續
    # 同一接點硬切 → 真 step(eps-無關,恆 ≈J)
    hc = {e: _hardcut_step(A, B, seam, e) for e in C0_EPS}
    hc_big = all(v >= HARDCUT_MIN * J for v in hc.values())
    hc_ratio = (hc[C0_EPS[0]] / hc[C0_EPS[1]]) if hc[C0_EPS[1]] > 1e-12 else float("inf")
    hc_step = hc_big and hc_ratio <= 1.5          # 對 eps 幾乎不變 → 真跳變
    ok = discont and cf_c0 and hc_step
    return {"pass": bool(ok), "jump_J": round(J, 4), "genuine_discont": bool(discont),
            "crossfade_seam": {str(k): round(v, 6) for k, v in cf.items()},
            "crossfade_shrink_ratio": round(cf_shrink, 2), "crossfade_is_C0": bool(cf_c0),
            "hardcut_seam": {str(k): round(v, 6) for k, v in hc.items()},
            "hardcut_over_J": round(min(hc.values()) / J, 3), "hardcut_ratio": round(hc_ratio, 3),
            "hardcut_is_step": bool(hc_step), "c0_step_tol": C0_STEP_TOL}


def ac_X4(A, B):
    mix = MIX2
    w0 = SA.duration(A) - mix
    tmid = w0 + 0.5 * mix
    # 混合律:線性 τ=0.5 == 0.5 blend
    cs = G.crossfade_state(A, B, mix, tmid, "linear")
    manual = G._blend_states(SA.sample(A, tmid), SA.sample(B, tmid - w0), 0.5)
    law_ok = G._state_max_diff(cs, manual) <= 1e-9
    # 權重單調 + 端點
    wl = [G.crossfade_weight(t, "linear") for t in (0, .25, .5, .75, 1)]
    ws = [G.crossfade_weight(t, "smooth") for t in (0, .25, .5, .75, 1)]
    mono = all(wl[i] <= wl[i + 1] for i in range(4)) and all(ws[i] <= ws[i + 1] for i in range(4))
    ends = wl[0] == 0.0 and wl[-1] == 1.0 and ws[0] == 0.0 and ws[-1] == 1.0
    # 窗內節點逐位元(bone)+ slot 量化
    comp, info = G.crossfade(A, B, mix, steps=STEPS)
    node_t = [round(w0 + j * mix / STEPS, 6) for j in range(STEPS + 1)]
    nb = max(_bone_only_diff(SA.sample(comp, t), G.crossfade_state(A, B, mix, t)) for t in node_t)
    nsl = max(_slot_only_diff(SA.sample(comp, t), G.crossfade_state(A, B, mix, t)) for t in node_t)
    node_ok = nb <= NODE_BONE_TOL and nsl <= COLOR_QUANT
    # steps 收斂
    errs = {s: _interp_err(A, B, mix, s) for s in (8, 32, 128)}
    conv = errs[8] > errs[32] > errs[128]
    ok = law_ok and mono and ends and node_ok and conv
    return {"pass": bool(ok), "linear_half_blend_residual": round(G._state_max_diff(cs, manual), 12),
            "law_ok": bool(law_ok), "weight_linear": wl, "weight_smooth": [round(x, 4) for x in ws],
            "weight_monotonic": bool(mono), "weight_endpoints_ok": bool(ends),
            "node_bone_diff": round(nb, 9), "node_slot_diff": round(nsl, 6), "node_exact_ok": bool(node_ok),
            "interp_err_by_steps": {str(k): round(v, 6) for k, v in errs.items()},
            "steps_converge": bool(conv)}


def ac_X5(A, B, seamless):
    # (a) 可調旋鈕:peak 速度 mix=0.1 / mix=0.2 ≈ 2×
    c1, i1 = G.crossfade(A, B, MIX1, steps=STEPS)
    c2, i2 = G.crossfade(A, B, MIX2, steps=STEPS)
    p1 = _peak_speed(c1, i1["w0"], i1["dur_a"])
    p2 = _peak_speed(c2, i2["w0"], i2["dur_a"])
    ratio = p1 / p2 if p2 > 1e-9 else float("inf")
    knob_ok = RATIO_LO <= ratio <= RATIO_HI
    # (b) 空驗守衛:無縫對 J<SEAMLESS_MAX → C0 宣稱空驗
    Js = _jump(*seamless)
    seamless_ok = Js < SEAMLESS_MAX and _jump(A, B) >= DISCONT_MIN
    # (c) 非法輸入守衛
    guards = []
    for args in [(A, B, SA.duration(A) + 0.1), (A, B, -0.1)]:
        try:
            G.crossfade(*args); guards.append(False)
        except ValueError:
            guards.append(True)
    try:
        G.crossfade({"bones": {}}, B, 0.05); guards.append(False)
    except ValueError:
        guards.append(True)
    guard_ok = all(guards)
    ok = knob_ok and seamless_ok and guard_ok
    return {"pass": bool(ok), "peak_mix01": round(p1, 2), "peak_mix02": round(p2, 2),
            "peak_ratio": round(ratio, 3), "ratio_band": [RATIO_LO, RATIO_HI], "knob_ok": bool(knob_ok),
            "seamless_jump": round(Js, 4), "discont_jump": round(_jump(A, B), 4),
            "seamless_vacuity_ok": bool(seamless_ok),
            "guards_mixhi_mixneg_empty": guards, "guards_ok": bool(guard_ok)}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    needed = ["In", "Loop", "Out", "hit"]
    missing = [nm for nm in needed if nm not in anims]
    if missing:
        return {"overall_pass": False, "error": "missing beats: {}".format(missing),
                "available": sorted(anims.keys())}
    A, B = anims["Out"], anims["Loop"]            # 不連續 fixture(Out 尾 collapsed ≠ Loop 首 identity)
    seamless = (anims["hit"], anims["Loop"])      # 無縫 fixture(皆 identity 介面)
    results = {"X1_present_bwcompat_nonvacuous": ac_X1(A, B),
               "X2_crux_endpoint_handoff_purefaith": ac_X2(A, B),
               "X3_crux_C0_across_discont_vs_hardcut": ac_X3(A, B),
               "X4_mixlaw_weight_steps_converge": ac_X4(A, B),
               "X5_negctrl_vacuity_guard": ac_X5(A, B, seamless)}
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
        print("candidate (L-5) 跨 beat 混場 crossfade 閘 — crossfade_state + crossfade + crossfade_weight")
        order = ["X1_present_bwcompat_nonvacuous", "X2_crux_endpoint_handoff_purefaith",
                 "X3_crux_C0_across_discont_vs_hardcut", "X4_mixlaw_weight_steps_converge",
                 "X5_negctrl_vacuity_guard"]
        for k in order:
            v = res.get(k, {})
            print("  {:38s} {}".format(k, "PASS" if v.get("pass") else "FAIL"))
        if "error" in res:
            print("  ERROR:", res["error"])
        if "X3_crux_C0_across_discont_vs_hardcut" in res:
            p = res["X3_crux_C0_across_discont_vs_hardcut"]
            print("    J={} | crossfade seam {} (C0={}) vs hardcut {} (step={})".format(
                p["jump_J"], p["crossfade_seam"], p["crossfade_is_C0"],
                p["hardcut_seam"], p["hardcut_is_step"]))
        if "X4_mixlaw_weight_steps_converge" in res:
            p = res["X4_mixlaw_weight_steps_converge"]
            print("    interp err by steps {} converge={} | node bone diff {}".format(
                p["interp_err_by_steps"], p["steps_converge"], p["node_bone_diff"]))
        if "X5_negctrl_vacuity_guard" in res:
            p = res["X5_negctrl_vacuity_guard"]
            print("    peak mix.1/.2 = {}/{} ratio={} (knob) | seamless J={} vs discont J={}".format(
                p["peak_mix01"], p["peak_mix02"], p["peak_ratio"], p["seamless_jump"], p["discont_jump"]))
        print("OVERALL:", "PASS" if res.get("overall_pass") else "FAIL")
    return 0 if res.get("overall_pass") else 1


if __name__ == "__main__":
    sys.exit(main())
