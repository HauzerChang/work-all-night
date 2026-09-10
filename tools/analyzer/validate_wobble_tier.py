#!/usr/bin/env python3
"""candidate (G-4'') 自我驗收閘 — wobble(shear 通道)接 tier 幅度差異化(純 CPU)。

續 (G-4')(生成器**第一次產出 shear 通道**:斜拉 jelly wobble,阻尼 shearX 擺動)與
(J)(檔位幅度差異化,但 `amplify_bone_tl` 只放大 scale/rotate/translate,**沒碰 shear**,
且 wobble ∉ MAIN_SHOW_CATS → 檔位變體未接)。honest boundary:**shear 峰不隨檔位遞增**。
本閘證那段已接上——wobble 納入 MAIN_SHOW_CATS、`amplify_bone_tl` 放大 shear(對 0 對稱 `v'=g*v`):

真值/fixture 與 (E/H/I/J/G-4') 一致:從**先驗庫**(slot_bigwin)經 `analyze_target`
→ **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。
主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章 + 檔位單調**,非美感;負對照證鑑別力。

AC(客觀、可量測):
  T1 present + routing + BC : 帶 tier_gains 時每檔位產 `wobble__{tier}` 且 finite/有 bone/帶 shear 通道;
                              變體名經 `beat_category` 仍路由回 wobble;`tier_gains=None` → **不產** wobble 變體;
                              且 **base wobble 逐位元 == tier_gains=None 的 base**(向後相容)。
  T2 crux shear-peak mono   : 每 wobble bone 的峰 |shearX| Super<Mega<Omg<Legend **嚴格遞增**;
                              端到端比值 ≈ TIER_GAIN 階梯(增益端到端存活到關鍵幀)。
  T3 interface kept per tier: **每檔位**——sample(0)/sample(dur) rotate/scale/translate identity
                              且 shear 首尾 0 → 檔位放大不破壞介面契約(仍可插 Loop 間)。
  T4 damped-osc kept /tier  : **每檔位**——shearX 序列繞 0 變號 ≥3 且相繼極值幅度嚴格遞減(阻尼)。
                              (增益 g>0 對 0 對稱放大 → 不改變號序列、相繼極值同乘 g → 遞減關係保留。)
  T5 orthogonality / neg    : (a) **平增益守衛**:增益全 1.0 → T2 峰單調 FALSE(證閘真在測遞增,非恆真);
                              (b) **backward-compat 逐位元**:`wobble__Super`(g=1.0)== base wobble byte-for-byte;
                              (c) **shear 隔離存活於 tiering**:帶 tier_gains 時,非 wobble 主秀變體
                                 (hit/burst/combo…__tier)仍 **0 bone 帶 shear**(放大只作用 wobble 的 shear)。

用法:
  python3 validate_wobble_tier.py            # 摘要
  python3 validate_wobble_tier.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
# 復用 G-4' 閘的 shear 簽章判準,確保與該閘完全一致
from validate_shear_gen import (_shear_x, _sign_changes_zero, _extrema_mags_decreasing, _is_ident)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
TOL = 1e-4
RATIO_TOL = 0.02   # 端到端峰比值 vs TIER_GAIN 階梯 相對誤差上限


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/wobble_tier_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _wobble_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "wobble"]


def _peak_shear(anim):
    """max over bones of max|shearX| —— wobble 峰幅度(0 對稱通道)。"""
    vals = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(vals, default=0.0)


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                       # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)     # 帶檔位
    wobble_beats = _wobble_beats(base)
    R = {"gains": gains, "wobble_beats": wobble_beats}

    # ---- T1 present + routing + backward-compat ----
    t1 = {"missing": [], "not_finite": [], "no_bones": [], "no_shear": [],
          "misrouted": [], "base_changed": [], "none_produced_variants": []}
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
    # base(tier_gains=None)不含任何 wobble 變體
    none_variants = [k for k in base if "__" in k and G.beat_category(k) == "wobble"]
    t1["none_produced_variants"] = none_variants
    # base wobble 本體逐位元不變(帶 tier 與不帶 tier 的 base 一致)
    for wb in wobble_beats:
        if json.dumps(base[wb], sort_keys=True) != json.dumps(anims.get(wb), sort_keys=True):
            t1["base_changed"].append(wb)
    t1_pass = (bool(wobble_beats) and not any(t1[k] for k in t1))
    R["T1_present_routing_bc"] = {**t1, "pass": t1_pass}

    # ---- T2 crux: shear peak monotone per tier + ratio ≈ gain ladder ----
    t2 = {"beats": {}, "fail_mono": [], "fail_ratio": []}
    for wb in wobble_beats:
        peaks = [_peak_shear(anims["{}__{}".format(wb, t)]) for t in TIERS]
        mono = all(peaks[i + 1] > peaks[i] + 1e-9 for i in range(len(peaks) - 1))
        # 比值 vs TIER_GAIN 階梯(以 Super 為基準)
        base_peak = peaks[0]
        ladder = [gains[t] for t in TIERS]
        ratio_ok = True
        if base_peak > TOL:
            for i, t in enumerate(TIERS):
                exp = base_peak * ladder[i]
                if abs(peaks[i] - exp) > RATIO_TOL * max(exp, 1.0):
                    ratio_ok = False
        t2["beats"][wb] = {"peaks": [round(p, 3) for p in peaks],
                           "expected": [round(base_peak * g, 3) for g in ladder],
                           "mono": mono, "ratio_ok": ratio_ok}
        if not mono:
            t2["fail_mono"].append(wb)
        if not ratio_ok:
            t2["fail_ratio"].append(wb)
    t2_pass = bool(t2["beats"]) and not t2["fail_mono"] and not t2["fail_ratio"]
    R["T2_shear_peak_monotone"] = {**t2, "pass": t2_pass}

    # ---- T3 interface contract preserved per tier ----
    t3 = {"bad_interface": [], "shear_endpoints_nonzero": []}
    for wb in wobble_beats:
        for t in TIERS:
            an = anims["{}__{}".format(wb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                t3["bad_interface"].append("{}__{}".format(wb, t))
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                    t3["shear_endpoints_nonzero"].append("{}__{}::{}".format(wb, t, bn))
    R["T3_interface_kept"] = {**t3, "pass": not t3["bad_interface"] and not t3["shear_endpoints_nonzero"]}

    # ---- T4 damped-oscillation signature preserved per tier ----
    t4 = {"few_sign_changes": [], "not_damped": [], "detail": {}}
    for wb in wobble_beats:
        for t in TIERS:
            an = anims["{}__{}".format(wb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(wb, t, bn)
                nsc = _sign_changes_zero(sx)
                damp = _extrema_mags_decreasing(sx)
                t4["detail"][key] = {"n_sign_changes": nsc, "damped": damp}
                if nsc < 3:
                    t4["few_sign_changes"].append(key)
                if not damp:
                    t4["not_damped"].append(key)
    t4_pass = bool(t4["detail"]) and not t4["few_sign_changes"] and not t4["not_damped"]
    R["T4_damped_kept"] = {**t4, "pass": t4_pass}

    # ---- T5 orthogonality / negative controls ----
    t5 = {}
    # (a) 平增益守衛:全 1.0 → 峰值全相同 → T2 單調 FALSE
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat = False
    for wb in wobble_beats:
        peaks = [_peak_shear(flat_anims["{}__{}".format(wb, t)]) for t in TIERS]
        if all(peaks[i + 1] > peaks[i] + 1e-9 for i in range(len(peaks) - 1)):
            any_mono_flat = True
    t5["a_flat_guard"] = {"flat_peak_any_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) backward-compat 逐位元:wobble__Super(g=1.0)== base wobble
    bc = []
    for wb in wobble_beats:
        sup = anims.get("{}__Super".format(wb))
        if json.dumps(sup, sort_keys=True) != json.dumps(base[wb], sort_keys=True):
            bc.append(wb)
    t5["b_super_byte_identical"] = {"changed": bc, "pass": not bc}
    # (c) shear 隔離存活於 tiering:非 wobble 主秀變體皆 0 bone 帶 shear
    leak = []
    for nm, an in anims.items():
        if "__" not in nm:
            continue
        cat = G.beat_category(nm)
        if cat == "wobble":
            continue
        sheared = [bn for bn, ch in an.get("bones", {}).items() if _shear_x(ch)]
        if sheared:
            leak.append((nm, sheared))
    t5["c_shear_isolated_in_tiering"] = {"leaked": leak, "pass": not leak}
    R["T5_orthogonality_neg"] = {**t5, "pass": all(v["pass"] for v in t5.values())}

    R["OVERALL_PASS"] = all(R[k]["pass"] for k in R if k.startswith(("T1", "T2", "T3", "T4", "T5")))
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    R = run()
    if a.json:
        print(json.dumps(R, ensure_ascii=False, indent=2))
    else:
        for k in ["T1_present_routing_bc", "T2_shear_peak_monotone", "T3_interface_kept",
                  "T4_damped_kept", "T5_orthogonality_neg"]:
            print("{:26s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("T2 shear peaks by tier:")
        for wb, d in R["T2_shear_peak_monotone"]["beats"].items():
            print("  {:10s} peaks {} (expected {})".format(wb, d["peaks"], d["expected"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
