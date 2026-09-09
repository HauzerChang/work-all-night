#!/usr/bin/env python3
"""candidate G-4'' 自我驗收閘 — wobble(斜拉果凍晃)shear 峰隨檔位遞增(純 CPU)。

(J)(`validate_tier_variants.py`)讓主秀 beat 的 **scale/rotate** 幅度隨檔位遞增(愈高愈爆);
(G-4')(`validate_shear_gen.py`)讓 `gen_wobble` 實際產出 **shear** 通道(阻尼振盪、首尾 identity)。
本閘(G-4'')把兩者接起來:wobble 併入 `MAIN_SHOW_CATS`,`amplify_bone_tl` 補上 **shear 軸**,
於是 `build_spine --tier-variants` 讓 wobble 的 **shear 峰隨檔位嚴格遞增**,而阻尼簽章/介面契約/
端到端 pivot 不動點對每個檔位保持。**shear 是與 (J) 的 scale/rotate 幅度軸正交的第三條放大軸**
(產線僅 wobble 帶 shear)。

真值界定同 (E/H/I/J/G-4'):斜拉 wobble 手感為 PROPOSAL(shear 形狀主觀留使用者 A 類);閘驗
**客觀結構簽章(shear 峰單調 + 阻尼振盪 + 端到端不動點)非美感**,負對照證鑑別力(閘可信)。
從**先驗庫**(slot_bigwin,含 wobble)經 `analyze_target` → **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains=…)` / `build_spine --tier-variants --shear-pivot` 端到端量。

AC(客觀、可量測):
  T1 present + routing + backward-compat : wobble base beat 存在;每檔位 `wobble__{tier}` 皆產出、
        finite、有 bone、≥1 bone 帶 `shear` 通道;變體名經 `beat_category` 仍路由回 `wobble`;
        帶檔位時**所有 base beat**(含 In/Loop/Out 與其他主秀)逐位元不變。
  T2 crux monotone shear peak            : wobble 各檔位 max|shearX| **Super<Mega<Omg<Legend 嚴格遞增**,
        且 == base 峰 × 該檔位宣告增益(精確放大,非近似)。**這是本 candidate 的 crux**。
  T3 signature + interface per tier       : **每個檔位**——(a) 每條 shearX 阻尼振盪簽章(首尾 0、繞 0
        變號 ≥3、相繼極值嚴格遞減);(b) sample(0)/sample(dur) 各 bone rotate/translate/scale identity
        且 shear 端點 0 → 可插 Loop 間。(峰幅隨檔位放大但簽章/介面保形。)
  T4 end-to-end pivot-fixed per tier      : `build_spine --tier-variants --shear-pivot`(真實 robot)產出
        wobble 檔位變體;凡有關節 pivot 的 bone,**每個檔位** pivot 殘差 < TOL_FIX,內建負對照
        (未補償=繞件中心)大位移;且端到端 shear 峰仍逐檔遞增(CLI 接線亦驗)。
  T5 orthogonality + isolation + guards   : (a) **shear 軸隔離**:非 wobble 的 beat/變體皆 0 bone 帶 shear
        (amplify 不把 shear 注入 scale/rotate 節拍);(b) **與 (J) 幅度軸正交**:wobble 變體在所有檔位
        scale overshoot==0 且 rotate amp==0(shear 是 wobble 唯一放大軸);(c) **平增益守衛**:增益全 1.0
        → shear 峰逐檔相等 → T2 單調 FALSE(證閘測真遞增非恆真)且 Super==Legend;(d) **向後相容**:
        base wobble(tiers=None)shear 逐位元 == `wobble__Super`(g=1.0)。

用法:
  python3 validate_wobble_tier.py            # 摘要
  python3 validate_wobble_tier.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim as SA
import gen_animations as G
from analyze_target import analyze
import tier_variants as TV
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_shear_pivot import _world   # 真實 Spine local(含 shear)世界座標求值

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,base wobble 峰值下限
TOL_FIX = 0.5       # px,pivot 不動點殘差上限(同 G-4/G-4')
MIN_NEG = 5.0       # px,負對照位移下限
NEG_RATIO = 20.0    # 負對照/不動點 位移比下限


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/wobble_tier_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _shear_peak(anim):
    """max over bones of max|shearX|(無 shear 回 0)。"""
    peaks = [max(abs(v) for v in sx) for sx in
             (_shear_x(ch) for ch in anim.get("bones", {}).values()) if sx]
    return max(peaks, default=0.0)


def _scale_overshoot(anim):
    peaks = []
    for ch in anim.get("bones", {}).values():
        if "scale" in ch:
            peaks.append(max(max(f["x"], f["y"]) for f in ch["scale"]) - 1.0)
    return max(peaks, default=0.0)


def _rotate_amp(anim):
    amps = []
    for ch in anim.get("bones", {}).values():
        if "rotate" in ch:
            amps.append(max(abs(f["angle"]) for f in ch["rotate"]))
    return max(amps, default=0.0)


def _is_strict_inc(xs):
    return all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def _wobble_base_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "wobble"]


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                      # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)    # 帶檔位
    wobble_beats = _wobble_base_beats(base)
    R = {}

    # ---- T1 present + routing + backward-compat ----
    t1 = {"wobble_base": wobble_beats, "missing": [], "not_finite": [],
          "no_bones": [], "no_shear": [], "misrouted": [], "base_changed": []}
    for wb in wobble_beats:
        for t in TIERS:
            vk = "{}__{}".format(wb, t)
            an = anims.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            if not an.get("bones"):
                t1["no_bones"].append(vk)
            if not any(_shear_x(ch) for ch in an.get("bones", {}).values()):
                t1["no_shear"].append(vk)
            if G.beat_category(vk) != "wobble":
                t1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:                                           # base 逐位元不變
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    t1_pass = bool(wobble_beats) and not any(t1[k] for k in
                  ("missing", "not_finite", "no_bones", "no_shear", "misrouted", "base_changed"))
    R["T1_present_routing"] = {**t1, "pass": t1_pass}

    # ---- T2 crux: monotone shear peak per tier (== base × declared gain) ----
    t2 = {"beats": {}, "fail_mono": [], "fail_gain": []}
    for wb in wobble_beats:
        base_peak = _shear_peak(base[wb])
        peaks = [_shear_peak(anims["{}__{}".format(wb, t)]) for t in TIERS]
        exp = [base_peak * gains[t] for t in TIERS]
        mono = _is_strict_inc(peaks)
        gain_ok = all(abs(p - e) <= 1e-2 for p, e in zip(peaks, exp))
        t2["beats"][wb] = {"base_peak": round(base_peak, 3),
                           "peaks": [round(p, 3) for p in peaks],
                           "expected": [round(e, 3) for e in exp],
                           "gains": [gains[t] for t in TIERS],
                           "mono": mono, "gain_exact": gain_ok}
        if not mono:
            t2["fail_mono"].append(wb)
        if not gain_ok:
            t2["fail_gain"].append(wb)
    t2_pass = bool(t2["beats"]) and not t2["fail_mono"] and not t2["fail_gain"]
    R["T2_crux_monotone_shear"] = {**t2, "pass": t2_pass}

    # ---- T3 damped-oscillation signature + identity interface per tier ----
    t3 = {"bad_signature": [], "bad_interface": [], "shear_end_nonzero": []}
    for wb in wobble_beats:
        for t in TIERS:
            an = anims["{}__{}".format(wb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                ends0 = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                if not (ends0 and _sign_changes_zero(sx) >= 3 and _extrema_mags_decreasing(sx)):
                    t3["bad_signature"].append("{}__{}::{}".format(wb, t, bn))
                if not ends0:
                    t3["shear_end_nonzero"].append("{}__{}::{}".format(wb, t, bn))
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]; end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                t3["bad_interface"].append("{}__{}".format(wb, t))
    t3_pass = not t3["bad_signature"] and not t3["bad_interface"] and not t3["shear_end_nonzero"]
    R["T3_signature_interface"] = {**t3, "pass": t3_pass}

    # ---- T4 end-to-end via build_spine --tier-variants --shear-pivot ----
    import build_spine
    out = "/tmp/wobble_tier_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True,
                             tier_variants=True, shear_pivot=True)
    sp = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {}); centers = summ.get("pivot_centers", {})
    t4 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_joint_bones": 0,
          "e2e_peaks": {}, "fail_e2e_mono": []}
    sp_anims = sp["animations"]
    for wb in _wobble_base_beats(sp_anims):
        e2e = [_shear_peak(sp_anims["{}__{}".format(wb, t)]) for t in TIERS]
        t4["e2e_peaks"][wb] = [round(p, 3) for p in e2e]
        if not _is_strict_inc(e2e):
            t4["fail_e2e_mono"].append(wb)
        for t in TIERS:
            an = sp_anims["{}__{}".format(wb, t)]
            for bn, ch in an.get("bones", {}).items():
                if bn not in joints or bn not in centers:
                    continue
                O = np.array(centers[bn], float); P = np.array(joints[bn], float)
                ellP = P - O
                tr = ch.get("translate")
                if not tr:
                    continue
                t4["n_joint_bones"] += 1
                ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 200 for i in range(201)]
                fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                       ch.get("shear"), tr, tt) - P)) for tt in ts)
                neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                       ch.get("shear"), None, tt) - P)) for tt in ts)
                rec = {"bone": bn, "beat": "{}__{}".format(wb, t),
                       "arm": round(float(np.linalg.norm(ellP)), 1),
                       "fixed": round(fix, 4), "negctrl": round(neg, 2)}
                t4["checked"].append(rec)
                if not (fix < TOL_FIX):
                    t4["fail_fixed"].append(rec)
                if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                    t4["fail_negctrl"].append(rec)
    t4_pass = (t4["n_joint_bones"] >= 1 and not t4["fail_fixed"]
               and not t4["fail_negctrl"] and not t4["fail_e2e_mono"])
    R["T4_end2end_pivot_fixed"] = {**t4, "pass": t4_pass}

    # ---- T5 orthogonality + isolation + guards ----
    t5 = {}
    # (a) shear 軸隔離:非 wobble 的 beat/變體皆 0 bone 帶 shear
    leak = []
    for nm, an in anims.items():
        if G.beat_category(nm) == "wobble":
            continue
        sheared = [bn for bn, ch in an.get("bones", {}).items() if _shear_x(ch)]
        if sheared:
            leak.append((nm, sheared))
    t5["a_shear_isolated"] = {"leaked": leak, "pass": not leak}
    # (b) 與 (J) 幅度軸正交:wobble 變體所有檔位 scale overshoot==0 且 rotate amp==0
    non_orth = []
    for wb in wobble_beats:
        for t in TIERS:
            an = anims["{}__{}".format(wb, t)]
            if _scale_overshoot(an) > TOL or _rotate_amp(an) > TOL:
                non_orth.append(("{}__{}".format(wb, t),
                                 round(_scale_overshoot(an), 4), round(_rotate_amp(an), 4)))
    t5["b_orthogonal_to_scale_rotate"] = {"non_orthogonal": non_orth, "pass": not non_orth}
    # (c) 平增益守衛:全 1.0 → shear 峰逐檔相等 → 單調 FALSE,且 Super==Legend
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat = False; sup_eq_leg = True
    for wb in wobble_beats:
        pk = [_shear_peak(flat_anims["{}__{}".format(wb, t)]) for t in TIERS]
        if _is_strict_inc(pk):
            any_mono_flat = True
        if abs(pk[0] - pk[-1]) > TOL:
            sup_eq_leg = False
    t5["c_flat_guard"] = {"flat_any_monotone": any_mono_flat, "super_eq_legend": sup_eq_leg,
                          "pass": (not any_mono_flat) and sup_eq_leg}
    # (d) 向後相容:base wobble shear 逐位元 == wobble__Super(g=1.0)
    bc = []
    for wb in wobble_beats:
        b_sh = {bn: ch.get("shear") for bn, ch in base[wb].get("bones", {}).items() if ch.get("shear")}
        s_sh = {bn: ch.get("shear") for bn, ch in anims["{}__Super".format(wb)].get("bones", {}).items()
                if ch.get("shear")}
        if json.dumps(b_sh, sort_keys=True) != json.dumps(s_sh, sort_keys=True):
            bc.append(wb)
    t5["d_super_eq_base"] = {"mismatched": bc, "pass": not bc}
    R["T5_orthogonality_guards"] = {**t5, "pass": all(v["pass"] for v in t5.values())}

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
        for k in ["T1_present_routing", "T2_crux_monotone_shear", "T3_signature_interface",
                  "T4_end2end_pivot_fixed", "T5_orthogonality_guards"]:
            print("{:28s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        for wb, d in R["T2_crux_monotone_shear"]["beats"].items():
            print("T2 {:8s} shear peaks {} (base {} × gains {})".format(
                wb, d["peaks"], d["base_peak"], d["gains"]))
        print("T4 end-to-end shear peaks:", R["T4_end2end_pivot_fixed"]["e2e_peaks"])
        print("T4 pivot-fixed (fixed/negctrl px), first few:")
        for rec in R["T4_end2end_pivot_fixed"]["checked"][:6]:
            print("  {:16s} arm {:6.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["beat"], rec["arm"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
