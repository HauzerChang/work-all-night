#!/usr/bin/env python3
"""candidate (L-6) 自我驗收閘 — 跨 beat **crossfade / mix** 序列組合:以 C1 斜坡消接點 C1 kink(純 CPU,確定性)。

**補的缺口(L-5 的「下一步」/ STATE 的 crossfade 軸)**:candidate (L)/(L-5) 的 `compose_sequence` 只做**純時間
平移 + 接點去重**,相鄰 beat 在接點**瞬間切換**。L-5 證實正向大獎序列每個相異接點雖 **C0 無縫**(值連續、可
串接播放)卻 **C1 不連續**(接點速度突變 15~114):各 beat 是離散節拍,端點切線互不相同。純平移去重**做不到**
平滑接點 —— 需真正的 **mix 機制**。本次新增 `crossfade_sequence`:相鄰 beat 時間重疊 `xf` 秒,重疊區以權重
斜坡 `w(s)` 混合兩 beat 姿勢,並以閘把關「crossfade + C1 斜坡」能把 L-5 的接點 kink 消掉。把 L-5 的「量化 /
攤開」推到「修正」,直指 north star「產出可**平順**播放的大獎序列」。

**crux / 本 run 的核心發現**:
  **crossfade 能否消接點 C1 kink,取決於斜坡本身是否 C1(w'(0)=w'(1)=0),而非 crossfade 本身。**
  閉式推導(見 `gen_animations` crossfade 段頂部):重疊區 `P(T)=(1−w(s))A(ta)+w(s)B(tb)`,接點**引入**的速度
  不連續只在重疊兩界:左界 `(w'(0)/xf)(B_start−A(d−xf))`、右界 `(w'(1)/xf)(B(xf)−A_end)`。
  - smoothstep / smootherstep(w'(0)=w'(1)=0)→ 每接點 kink **恆 0(閉式精確)**:離散瞬切換成 xf 秒平滑過渡。
  - 線性斜坡(w'≡1)→ 兩界 kink **猶存** 15~120:crossfade 本身**不足以** C1,**C1 的斜坡**才是鑑別子。
  閉式(乘 w' 導數)與有限差分步長、與 clip **內部關鍵幀位置**皆無關 → 不會把 beat 自身節拍 kink 誤計為接點
  artifact(L-5 的 `seam_velocity_gap` 是 `xf→0` 的瞬切極限,本閘量 crossfade **後**殘餘的接點 kink)。

**選題理由(不選又一條參數軸)**:延續 (L)/(L-2)/(L-3)/(L-4)/(L-5)/(G-2) 刻意選**整合 / 組合閘**。L-6 的客觀
新能力 = 在組合層以 crossfade **修正** L-5 攤開的 C1 kink。從**先驗庫 → 真實 build_spine robot 骨架 →
build_animations** 端到端,與 L / L-3 / L-4 / L-5 同一 fixture(正向序列 In→hit→combo→charge→cascade→Loop→Out)。

真值界定:**哪些接點該平滑、xf 多長**屬美術手感(A 類;離散節拍的撞擊感可能該保留);但「crossfade 後接點
kink」「C1 斜坡 vs 線性斜坡」「emitted 忠實度」皆為**客觀可量測**不變量。正/負對照證閘既能認證 smoothstep 消
kink、又能抓出線性斜坡仍頓挫、又不被靜止空驗騙過。

AC(客觀、可量測):
  X1 present+well-formed+faithful+bc : `crossfade_sequence`(smoothstep,xf=XF)產**合法 Spine timeline**(每通道
                                       時間嚴格遞增、finite);總時長 == Σdur − (m−1)·xf;**body 區忠實**(emitted
                                       取樣 vs 孤立 clip 平移後 ≤ FAITH_TOL);**backward-compat**:`xf=0` 逐位元 ==
                                       `compose_sequence`。
  X2 crux — smoothstep 消接點 kink    : smoothstep crossfade 每接點閉式 kink ≤ KINK_ZERO_TOL(≈0)**對照**純接續
                                       (L-5 `seam_velocity_gap`)每接點 ≥ SEAM_KINK_MIN(15~114)→ crossfade 消 kink;
                                       `is_c1_crossfade_sequence`(smoothstep)==True **而** `is_c1_continuous_sequence`
                                       (純接續)==False。
  X3 真混合 + 非空驗                  : 重疊中點(s=0.5)姿勢與**前 beat 單獨**、**後 beat 單獨**皆不同(各 ≥ BLEND_MIN)
                                       → 真的在混合、非瞬切;重疊**真縮短**總時長 (m−1)·xf;序列有運動(接點兩側端點
                                       速度 ≥ MOTION_VEL_THR,否則 kink=0 空驗)。
  X4 crux — C1 斜坡才是鑑別子(負對照): **線性**斜坡 crossfade 每接點閉式 kink ≥ SEAM_KINK_MIN(crossfade 本身不足以
                                       C1)、`is_c1_crossfade_sequence`(linear)==False → 證**斜坡的 C1 性**(w'兩端=0)
                                       才是消 kink 的原因,非 crossfade 本身;且 **smootherstep**(C2)亦每接點 ≤
                                       KINK_ZERO_TOL → 證關鍵 = w'(0)=w'(1)=0(共性),非特定 smoothstep。
  X5 metric 良定義 + 守衛 + 空驗       : (a) **閉式==數值**:合成 clean clip 對(無內部關鍵幀干擾),線性斜坡的閉式
                                       `crossfade_seam_kink` == `crossfade_pose_at` 的數值有限差分(rel < NUM_REL_TOL);
                                       (b) **emitted 重疊忠實**:emitted 在重疊取樣 vs 解析 `crossfade_pose_at` ≤
                                       RESAMPLE_TOL(且隨 nsamp 收斂);(c) **輸入守衛**:xf<0 與 xf>min_dur/2 → ValueError、
                                       xf=0 不報錯(委派);(d) **空驗守衛**:兩**靜止** clip crossfade → smoothstep **與**
                                       線性 kink 皆 0(靜止 → 無論斜坡皆無 kink)**但**無運動 → 證「kink=0」須配非靜止才
                                       有意義(smoothstep 在**會動**的真 beat 上 kink=0 才是實質結果;呼應 L-5 空驗)。

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

XF = 0.15               # crossfade 重疊秒數(< 最短 beat 時長 Out=0.4 的一半 0.2;重疊界避開 clip 內部節拍 kink)
NSAMP = 16              # 重疊重取樣段數
KINK_ZERO_TOL = 1e-6    # smoothstep/smootherstep 閉式接點 kink 上限(實測精確 0)
SEAM_KINK_MIN = 10.0    # 純接續(L-5)與線性斜坡 crossfade 每接點須有的 C1 kink 下限(實測最小 15)
VEL_TOL = 1.0           # is_c1_crossfade_sequence 的接點 kink 容忍(與 L-5 同)
FAITH_TOL = 0.05        # body 區 emitted vs 孤立 clip 忠實上限(實測 0.0019)
RESAMPLE_TOL = 0.5      # 重疊 emitted vs 解析 pose_at 上限(nsamp=16 實測 0.19,隨 nsamp 收斂)
BLEND_MIN = 0.3         # 重疊中點混合姿勢與前/後 beat 單獨的最小差(證真混合;實測最小 0.577)
MOTION_VEL_THR = 1.0    # 接點兩側須有的最小端點速度(非空驗)
NUM_REL_TOL = 1e-3      # 閉式 vs 數值有限差分的相對差上限

FORWARD = ["In", "hit", "combo", "charge", "cascade", "Loop", "Out"]


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/seq_xf_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


# ---------------- 量測器 ----------------
def _endpoint_max_speed(clip, at_start, h=1e-3):
    v = G._state_velocity(clip, at_start, h)
    m = 0.0
    for d in v["bones"].values():
        for x in d.values():
            m = max(m, abs(x))
    for d in v["slots"].values():
        m = max(m, abs(d["alpha"]))
    return m


def _static(dur=2.0):
    return {"bones": {"b_身體": {"rotate": [{"time": 0.0, "angle": 0.0}, {"time": dur, "angle": 0.0}]}}}


# ---------------- AC ----------------
def ac_X1(anims):
    comp, segs = G.crossfade_sequence(anims, FORWARD, XF, NSAMP, "smoothstep")
    well_formed = SA.all_finite(comp)
    total = SA.duration(comp)
    exp_total = sum(SA.duration(anims[n]) for n in FORWARD) - (len(FORWARD) - 1) * XF
    total_ok = abs(total - exp_total) <= 1e-6
    # body 區忠實:每 beat body 內部(避開重疊)取樣 emitted vs 孤立 clip 平移
    offsets, durs, _ = G._crossfade_layout(anims, FORWARD, XF)
    faith = 0.0
    last = len(FORWARD) - 1
    for i, nm in enumerate(FORWARD):
        lo = offsets[i] + (XF if i > 0 else 0.0)
        hi = offsets[i] + durs[i] - (XF if i < last else 0.0)
        for frac in (0.2, 0.4, 0.6, 0.8):
            t = lo + (hi - lo) * frac
            faith = max(faith, G._state_max_diff(SA.sample(comp, t), SA.sample(anims[nm], t - offsets[i])))
    faith_ok = faith <= FAITH_TOL
    # backward-compat xf=0 逐位元 == compose_sequence
    c0, s0 = G.crossfade_sequence(anims, FORWARD, 0.0)
    cc, sc = G.compose_sequence(anims, FORWARD)
    bc = (json.dumps(c0, sort_keys=True) == json.dumps(cc, sort_keys=True)) and (s0 == sc)
    seg_overlap = all(abs((segs[i]["start"] + segs[i]["dur"]) - (segs[i + 1]["start"] + XF)) <= 1e-6
                      for i in range(last))  # 相鄰段區間相交 xf
    ok = well_formed and total_ok and faith_ok and bc and seg_overlap
    return {"pass": bool(ok), "well_formed_strict_increasing_finite": bool(well_formed),
            "total_dur": round(total, 6), "expected_total": round(exp_total, 6), "total_ok": bool(total_ok),
            "body_faithful_maxerr": round(faith, 6), "faith_tol": FAITH_TOL, "faith_ok": bool(faith_ok),
            "xf0_bit_identical_to_compose": bool(bc), "segments_overlap_by_xf": bool(seg_overlap)}


def ac_X2(anims):
    concat = G.sequence_seam_gaps(anims, FORWARD, 1e-3)
    xf_k = G.crossfade_junction_kinks(anims, FORWARD, XF, "smoothstep")
    per = {}
    all_zero = True
    all_concat_kink = True
    for cg, xk in zip(concat, xf_k):
        per[cg["seam"]] = {"concat_c1": round(cg["c1_gap"], 3), "crossfade_c1": round(xk["max"], 9)}
        if xk["max"] > KINK_ZERO_TOL:
            all_zero = False
        if cg["c1_gap"] < SEAM_KINK_MIN:
            all_concat_kink = False
    xf_c1 = G.is_c1_crossfade_sequence(anims, FORWARD, XF, "smoothstep", VEL_TOL)
    concat_c1 = G.is_c1_continuous_sequence(anims, FORWARD, 1e-6, VEL_TOL, 1e-3)
    ok = all_zero and all_concat_kink and xf_c1 and (not concat_c1)
    return {"pass": bool(ok), "smoothstep_all_kinks_zero": bool(all_zero), "kink_zero_tol": KINK_ZERO_TOL,
            "concat_all_kink": bool(all_concat_kink), "seam_kink_min": SEAM_KINK_MIN,
            "is_c1_crossfade_sequence_smoothstep": bool(xf_c1),
            "is_c1_continuous_sequence_concat": bool(concat_c1), "per_seam": per}


def ac_X3(anims):
    offsets, durs, total = G._crossfade_layout(anims, FORWARD, XF)
    last = len(FORWARD) - 1
    blends = {}
    blend_ok = True
    for i in range(last):
        ov = offsets[i + 1]
        t = ov + XF * 0.5
        mix = G.crossfade_pose_at(anims, FORWARD, XF, t, "smoothstep")
        a_only = SA.sample(anims[FORWARD[i]], t - offsets[i])
        b_only = SA.sample(anims[FORWARD[i + 1]], t - offsets[i + 1])
        da = G._state_max_diff(mix, a_only)
        db = G._state_max_diff(mix, b_only)
        blends["{}->{}".format(FORWARD[i], FORWARD[i + 1])] = {"d_from_A": round(da, 3), "d_from_B": round(db, 3)}
        if da < BLEND_MIN or db < BLEND_MIN:
            blend_ok = False
    # 重疊真縮短總時長 (m-1)*xf
    concat_total = sum(durs)
    shorten = concat_total - total
    shorten_ok = abs(shorten - (len(FORWARD) - 1) * XF) <= 1e-6
    # 非空運動:接點兩側端點速度
    motions = {}
    motion_ok = True
    for i in range(last):
        a, b = FORWARD[i], FORWARD[i + 1]
        m = max(_endpoint_max_speed(anims[a], False), _endpoint_max_speed(anims[b], True))
        motions["{}->{}".format(a, b)] = round(m, 3)
        if m < MOTION_VEL_THR:
            motion_ok = False
    ok = blend_ok and shorten_ok and motion_ok
    return {"pass": bool(ok), "blend_nonvacuous": bool(blend_ok), "blend_min": BLEND_MIN, "mid_overlap_blends": blends,
            "total_shorten": round(shorten, 6), "expected_shorten": round((len(FORWARD) - 1) * XF, 6),
            "shorten_ok": bool(shorten_ok), "seam_motions": motions, "motion_ok": bool(motion_ok),
            "motion_vel_thr": MOTION_VEL_THR}


def ac_X4(anims):
    lin_k = G.crossfade_junction_kinks(anims, FORWARD, XF, "linear")
    lin_all_kink = all(j["max"] >= SEAM_KINK_MIN for j in lin_k)
    lin_c1 = G.is_c1_crossfade_sequence(anims, FORWARD, XF, "linear", VEL_TOL)
    smoo_k = G.crossfade_junction_kinks(anims, FORWARD, XF, "smootherstep")
    smoo_all_zero = all(j["max"] <= KINK_ZERO_TOL for j in smoo_k)
    ok = lin_all_kink and (not lin_c1) and smoo_all_zero
    return {"pass": bool(ok), "linear_all_kink": bool(lin_all_kink),
            "linear_kinks": {j["seam"]: round(j["max"], 3) for j in lin_k},
            "is_c1_crossfade_sequence_linear": bool(lin_c1),
            "smootherstep_all_kinks_zero": bool(smoo_all_zero),
            "note": "線性斜坡 crossfade 仍每接點頓挫 → C1 斜坡(w'兩端=0)才是鑑別子;smootherstep(C2)亦=0 證共性是 w'(0)=w'(1)=0"}


def ac_X5(anims):
    # (a) 閉式 == 數值(合成 clean clip 對,線性斜坡;無內部關鍵幀干擾)
    A = {"bones": {"b": {"rotate": [{"time": 0.0, "angle": 0.0}, {"time": 1.0, "angle": 10.0}]}}}
    B = {"bones": {"b": {"rotate": [{"time": 0.0, "angle": 0.0}, {"time": 1.0, "angle": -20.0}]}}}
    syn = {"a": A, "b": B}
    xf = 0.5
    closed = G.crossfade_seam_kink(A, B, xf, "linear")

    def _num_kink(h=1e-5):
        offs, durs, total = G._crossfade_layout(syn, ["a", "b"], xf)
        end = offs[0] + durs[0]

        def onesided(T, hh):
            s0 = G.crossfade_pose_at(syn, ["a", "b"], xf, T, "linear")
            s1 = G.crossfade_pose_at(syn, ["a", "b"], xf, T + hh, "linear")
            return (s1["bones"]["b"]["rotate"] - s0["bones"]["b"]["rotate"]) / hh
        return (abs(onesided(end - xf, -h) - onesided(end - xf, h)),
                abs(onesided(end, -h) - onesided(end, h)))
    nl, nr = _num_kink()
    rel_l = abs(closed["left"] - nl) / closed["left"] if closed["left"] > 1e-9 else 0.0
    rel_r = abs(closed["right"] - nr) / closed["right"] if closed["right"] > 1e-9 else 0.0
    closed_num_ok = (rel_l < NUM_REL_TOL) and (rel_r < NUM_REL_TOL)
    # (b) emitted 重疊忠實 + 隨 nsamp 收斂
    offsets, _, _ = G._crossfade_layout(anims, FORWARD, XF)
    errs = {}
    for ns in (16, 64):
        comp, _ = G.crossfade_sequence(anims, FORWARD, XF, ns, "smoothstep")
        m = 0.0
        for i in range(len(FORWARD) - 1):
            for frac in (0.1, 0.3, 0.5, 0.7, 0.9):
                t = offsets[i + 1] + XF * frac
                m = max(m, G._state_max_diff(SA.sample(comp, t), G.crossfade_pose_at(anims, FORWARD, XF, t, "smoothstep")))
        errs[ns] = round(m, 6)
    resample_ok = (errs[16] <= RESAMPLE_TOL) and (errs[64] < errs[16])
    # (c) 輸入守衛
    guards = {}
    for xfg, label in [(-0.1, "neg"), (0.5, "too_big")]:
        try:
            G.crossfade_pose_at(anims, FORWARD, xfg, 0.1)
            guards[label] = False
        except ValueError:
            guards[label] = True
    try:
        G.crossfade_sequence(anims, FORWARD, 0.0)  # xf=0 不報錯
        guards["xf0_delegates"] = True
    except Exception:
        guards["xf0_delegates"] = False
    guard_ok = all(guards.values())
    # (d) 空驗守衛:兩靜止 clip → 任何斜坡 kink 皆 0(靜止 → 無論斜坡皆無 kink)但無運動
    st = {"a": _static(), "b": _static()}
    smoo = G.crossfade_seam_kink(st["a"], st["b"], 0.5, "smoothstep")["max"]
    linr = G.crossfade_seam_kink(st["a"], st["b"], 0.5, "linear")["max"]
    st_speed = max(_endpoint_max_speed(st["a"], False), _endpoint_max_speed(st["b"], True))
    vac_ok = (smoo <= 1e-9) and (linr <= 1e-9) and (st_speed < MOTION_VEL_THR)
    ok = closed_num_ok and resample_ok and guard_ok and vac_ok
    return {"pass": bool(ok),
            "closed_vs_numerical": {"pass": bool(closed_num_ok), "closed_left": round(closed["left"], 4),
                                    "closed_right": round(closed["right"], 4), "num_left": round(nl, 4),
                                    "num_right": round(nr, 4), "rel_l": round(rel_l, 6), "rel_r": round(rel_r, 6)},
            "resample_faithful": {"pass": bool(resample_ok), "err_by_nsamp": errs, "resample_tol": RESAMPLE_TOL},
            "input_guards": {"pass": bool(guard_ok), **guards},
            "static_vacuity": {"pass": bool(vac_ok), "smoothstep_kink": round(smoo, 9), "linear_kink": round(linr, 9),
                               "endpoint_speed": round(st_speed, 9),
                               "note": "靜止→任何斜坡皆無 kink→kink=0 須配非靜止才有意義(smoothstep 在會動 beat 上 kink=0 才是實質結果)"}}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    missing = [nm for nm in FORWARD if nm not in anims]
    if missing:
        return {"overall_pass": False, "error": "missing beats in fixture: {}".format(missing),
                "available": sorted(anims.keys())}
    results = {"X1_present_wellformed_faithful_bc": ac_X1(anims),
               "X2_crux_smoothstep_kills_seam_kink": ac_X2(anims),
               "X3_real_blend_nonvacuous": ac_X3(anims),
               "X4_crux_C1_ramp_is_discriminator": ac_X4(anims),
               "X5_metric_welldefined_guards_vacuity": ac_X5(anims)}
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
        print("candidate (L-6) 跨 beat crossfade / mix 序列組合閘 — crossfade_pose_at + crossfade_seam_kink + crossfade_sequence")
        for k in ["X1_present_wellformed_faithful_bc", "X2_crux_smoothstep_kills_seam_kink",
                  "X3_real_blend_nonvacuous", "X4_crux_C1_ramp_is_discriminator",
                  "X5_metric_welldefined_guards_vacuity"]:
            v = res.get(k, {})
            print("  {:38s} {}".format(k, "PASS" if v.get("pass") else "FAIL"))
        if "error" in res:
            print("  ERROR:", res["error"])
        if "X2_crux_smoothstep_kills_seam_kink" in res:
            p = res["X2_crux_smoothstep_kills_seam_kink"]
            print("    smoothstep all-kinks-zero={} | concat is_c1={} vs crossfade is_c1={}".format(
                p["smoothstep_all_kinks_zero"], p["is_c1_continuous_sequence_concat"],
                p["is_c1_crossfade_sequence_smoothstep"]))
            print("    per-seam concat_c1 vs crossfade_c1:", {s: (d["concat_c1"], d["crossfade_c1"]) for s, d in p["per_seam"].items()})
        if "X4_crux_C1_ramp_is_discriminator" in res:
            p = res["X4_crux_C1_ramp_is_discriminator"]
            print("    linear kinks={} (is_c1={}) | smootherstep all-zero={}".format(
                p["linear_kinks"], p["is_c1_crossfade_sequence_linear"], p["smootherstep_all_kinks_zero"]))
        if "X5_metric_welldefined_guards_vacuity" in res:
            p = res["X5_metric_welldefined_guards_vacuity"]
            print("    closed==numerical L {}/{} R {}/{} | resample err {} | guards {} | static kink smoo={} lin={}".format(
                p["closed_vs_numerical"]["closed_left"], p["closed_vs_numerical"]["num_left"],
                p["closed_vs_numerical"]["closed_right"], p["closed_vs_numerical"]["num_right"],
                p["resample_faithful"]["err_by_nsamp"],
                {k: v for k, v in p["input_guards"].items() if k != "pass"},
                p["static_vacuity"]["smoothstep_kink"], p["static_vacuity"]["linear_kink"]))
        print("OVERALL:", "PASS" if res.get("overall_pass") else "FAIL")
    return 0 if res.get("overall_pass") else 1


if __name__ == "__main__":
    sys.exit(main())
