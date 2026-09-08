#!/usr/bin/env python3
"""candidate G-4'' 自我驗收閘 — wobble(shear 通道)接 tier 幅度差異化(純 CPU)。

續 G-4'(`validate_shear_gen.py`,`gen_wobble` 為**第一個產 shear 通道的生成器**)與 J
(`validate_tier_variants.py`,主秀 beat 依檔位幅度差異化,但當時只放大 scale/rotate)。
G-4' 的 honest boundary:wobble ∉ MAIN_SHOW_CATS 且 `amplify_bone_tl` 不動 shear →
**wobble 的 shear 峰不隨檔位遞增**(所有檔位共用同一斜拉幅度)。本次把 wobble 併入主秀、
讓 `amplify_bone_tl` 以 `v'=g*v`(繞 0 對稱,比照 rotate)放大 shear → shear 峰隨檔位遞增,
而**阻尼振盪簽章與 identity 介面對所有檔位保形**(g*0=0 守零、相繼極值同乘 g → 阻尼比不變)。

真值/fixture 與 (E/H/I/J/G-4') 一致:從**先驗庫**(slot_bigwin,含 wobble beat)經 `analyze_target`
→ **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。主秀運動無唯一
正解(斜拉幅度 PROPOSAL 手感),閘驗**客觀結構簽章(shear 峰單調 + 阻尼簽章保形)**,非美感;
負對照(平增益守衛 / shear 隔離 / 阻尼比正交)證鑑別力(閘可信)。

AC(客觀、可量測):
  X1 present + routing + backward-compat: 每 wobble beat × 每檔位皆產 `{beat}__{tier}` 且 finite/有 bone
        /帶 shear 通道;變體名經 `beat_category` 仍路由回 "wobble";base wobble beat 與 `tier_gains=None`
        逐位元不變(向後相容);In/Loop/Out 不產 wobble 變體。
  X2 crux monotone shear peak: 每 wobble beat 的 shearX 峰(max|shearX| over bones)
        Super<Mega<Omg<Legend **嚴格遞增**,且比值 == 宣告增益階梯(端到端經 build_animations)。
  X3 damped signature kept   : **每個檔位**——每 wobble bone 的 shearX 仍(a)首尾 0;(b)繞 0 變號 ≥3;
        (c)相繼極值嚴格遞減(阻尼)→ 幅度增益不破壞阻尼振盪簽章。
  X4 identity interface       : **每個檔位**——sample(0)/sample(dur) 各 bone rotate/translate/scale
        皆 identity 且 shear 首尾 0 → 與 In/Loop/Out 無縫串接。
  X5 neg-control / 正交       : (a)**平增益守衛**:增益階梯全 1.0 → X2 單調性 FALSE(證閘測遞增非恆真);
        (b)**shear 隔離保持**:tier 放大不讓非 wobble beat 的變體憑空長出 shear 通道(shear 僅在 wobble);
        (c)**阻尼比正交**:相繼極值比 r 對所有檔位相同(幅度軸與形狀/阻尼軸正交 → 只改「多斜」不改波形)。

用法:
  python3 validate_wobble_tier.py            # 摘要
  python3 validate_wobble_tier.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze
import tier_variants as TV
# 復用 G-4' 的 shear 判準,確保簽章判定與 shear-gen 閘完全一致。
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
RATIO_TOL = 1e-3   # 相繼極值比(阻尼比)跨檔位一致的容差


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


def _wobble_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "wobble"]


def _shear_peak(anim):
    """該 anim 的 shearX 峰值(max|shearX| over bones;無 shear 回 0)。"""
    return max((max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values()
                if _shear_x(ch)), default=0.0)


def _extrema_ratios(vals, dead=1e-6):
    """非零關鍵幀 |v| 序列的相繼比 [|v1|/|v0|, |v2|/|v1|, ...]。"""
    nz = [abs(v) for v in vals if abs(v) > dead]
    return [nz[i + 1] / nz[i] for i in range(len(nz) - 1)] if len(nz) >= 2 else []


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                       # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)     # 帶檔位
    wobble_beats = _wobble_beats(base)
    R = {}

    # ---- X1 present + routing + backward-compat ----
    x1 = {"wobble_beats": wobble_beats, "missing": [], "not_finite": [], "no_bones": [],
          "no_shear": [], "misrouted": [], "base_changed": [], "staging_wobble_variants": []}
    for beat in wobble_beats:
        for t in TIERS:
            vk = "{}__{}".format(beat, t)
            an = anims.get(vk)
            if an is None:
                x1["missing"].append(vk); continue
            if not SA.all_finite(an):
                x1["not_finite"].append(vk)
            if not an.get("bones"):
                x1["no_bones"].append(vk)
            if not any(_shear_x(ch) for ch in an.get("bones", {}).values()):
                x1["no_shear"].append(vk)
            if G.beat_category(vk) != "wobble":
                x1["misrouted"].append((vk, G.beat_category(vk)))
    # base(含 In/Loop/Out)逐位元不變(tier_gains=None 路徑 == 帶檔位下的 base key)
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            x1["base_changed"].append(k)
    # In/Loop/Out 不產 wobble 變體(檔位只針對主秀)
    for k in anims:
        if "__" in k and G.beat_category(k) in ("intro", "loop", "outro"):
            x1["staging_wobble_variants"].append(k)
    x1_pass = bool(wobble_beats) and not any(x1[k] for k in x1 if k != "wobble_beats")
    R["X1_present_routing"] = {**x1, "n_variants_expected": len(wobble_beats) * len(TIERS),
                               "pass": x1_pass}

    # ---- X2 crux: monotone shear peak across tiers ----
    x2 = {"beats": {}, "fail_mono": [], "fail_ratio": []}
    ladder = [gains[t] for t in TIERS]
    for beat in wobble_beats:
        peaks = [_shear_peak(anims["{}__{}".format(beat, t)]) for t in TIERS]
        mono = all(peaks[i + 1] > peaks[i] + TOL for i in range(len(peaks) - 1))
        # 峰值比 == 宣告增益階梯(base=peaks[0]/ladder[0])
        base_peak = peaks[0] / ladder[0] if ladder[0] else 0.0
        expect = [round(base_peak * g, 3) for g in ladder]
        ratio_ok = all(abs(peaks[i] - expect[i]) <= 1e-2 for i in range(len(peaks)))
        x2["beats"][beat] = {"peaks": [round(p, 3) for p in peaks], "expect_by_gain": expect,
                             "monotone": mono, "matches_gain_ladder": ratio_ok}
        if not mono:
            x2["fail_mono"].append(beat)
        if not ratio_ok:
            x2["fail_ratio"].append(beat)
    R["X2_monotone_shear_peak"] = {**x2, "gain_ladder": ladder,
                                   "pass": bool(wobble_beats) and not x2["fail_mono"] and not x2["fail_ratio"]}

    # ---- X3 damped-oscillation signature kept per tier ----
    x3 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [], "n_checked": 0}
    for beat in wobble_beats:
        for t in TIERS:
            an = anims["{}__{}".format(beat, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                x3["n_checked"] += 1
                key = "{}__{}::{}".format(beat, t, bn)
                if not (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6):
                    x3["bad_endpoints"].append(key)
                if _sign_changes_zero(sx) < 3:
                    x3["few_sign_changes"].append(key)
                if not _extrema_mags_decreasing(sx):
                    x3["not_damped"].append(key)
    x3_pass = (x3["n_checked"] >= len(wobble_beats) * len(TIERS)
               and not x3["bad_endpoints"] and not x3["few_sign_changes"] and not x3["not_damped"])
    R["X3_damped_signature_kept"] = {**x3, "pass": x3_pass}

    # ---- X4 identity interface per tier ----
    x4 = {"bad_interface": [], "shear_endpoints_nonzero": []}
    for beat in wobble_beats:
        for t in TIERS:
            an = anims["{}__{}".format(beat, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                x4["bad_interface"].append("{}__{}".format(beat, t))
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                    x4["shear_endpoints_nonzero"].append("{}__{}::{}".format(beat, t, bn))
    R["X4_identity_interface"] = {**x4,
                                  "pass": not x4["bad_interface"] and not x4["shear_endpoints_nonzero"]}

    # ---- X5 negative controls / orthogonality ----
    x5 = {}
    # (a) 平增益守衛:全 1.0 → X2 單調性應 FALSE(否則閘恆真)
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat = False
    for beat in wobble_beats:
        peaks = [_shear_peak(flat_anims["{}__{}".format(beat, t)]) for t in TIERS]
        if all(peaks[i + 1] > peaks[i] + TOL for i in range(len(peaks) - 1)):
            any_mono_flat = True
    x5["a_flat_guard"] = {"flat_ladder_any_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) shear 隔離保持:非 wobble beat 的檔位變體皆不帶 shear(tier 放大不憑空造 shear 通道)
    leak = []
    for nm, an in anims.items():
        if "__" not in nm:
            continue
        if G.beat_category(nm) == "wobble":
            continue
        if any(_shear_x(ch) for ch in an.get("bones", {}).values()):
            leak.append(nm)
    x5["b_shear_isolated_under_tiers"] = {"leaked_variants": leak, "pass": not leak}
    # (c) 阻尼比正交:相繼極值比 r 對所有檔位相同(幅度改變、波形/阻尼不變)
    ratio_fail = []
    ratio_detail = {}
    for beat in wobble_beats:
        for bn in {b for t in TIERS for b in anims["{}__{}".format(beat, t)].get("bones", {})}:
            per_tier = []
            for t in TIERS:
                ch = anims["{}__{}".format(beat, t)].get("bones", {}).get(bn, {})
                sx = _shear_x(ch)
                if sx:
                    per_tier.append(_extrema_ratios(sx))
            if len(per_tier) < 2:
                continue
            ref = per_tier[0]
            key = "{}::{}".format(beat, bn)
            ratio_detail[key] = [round(x, 4) for x in ref]
            for rr in per_tier[1:]:
                if len(rr) != len(ref) or any(abs(a - b) > RATIO_TOL for a, b in zip(rr, ref)):
                    ratio_fail.append(key); break
    x5["c_damping_ratio_orthogonal"] = {"ratios_ref": ratio_detail, "fail": ratio_fail,
                                        "pass": bool(ratio_detail) and not ratio_fail}
    R["X5_neg_control"] = {**x5, "pass": all(v["pass"] for v in x5.values())}

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
        for k in ["X1_present_routing", "X2_monotone_shear_peak", "X3_damped_signature_kept",
                  "X4_identity_interface", "X5_neg_control"]:
            print("{:28s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("X2 shear peaks by tier (Super/Mega/Omg/Legend):")
        for beat, d in R["X2_monotone_shear_peak"]["beats"].items():
            print("  {:10s} {}  (gain-expect {})".format(beat, d["peaks"], d["expect_by_gain"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
