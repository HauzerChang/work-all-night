#!/usr/bin/env python3
"""candidate G-4'' 自我驗收閘 — 斜拉 wobble 接 tier 幅度差異化:shear 峰隨檔位遞增(純 CPU)。

G-4'(`validate_shear_gen.py`)讓 `gen_wobble` **產出 shear 通道**並經先驗庫直出、`--shear-pivot`
端到端補償;honest boundary:**wobble ∉ 檔位變體集合**(`tier_variants` 只放大 scale/rotate/translate,
且 wobble 不在 `MAIN_SHOW_CATS`)→ shear 幅度不隨檔位變化。本閘(G-4'')驗那一段**已接上**:
比照 (J) 對 scale/rotate 所做,讓 wobble 的 **shear 擺幅峰值隨檔位嚴格遞增**,而**阻尼振盪簽章與
identity 介面對每個檔位皆保形**。

機制(全 additive,零回歸):
  - `tier_variants.SHEAR_SHOW_CATS={"wobble"}` + `TIER_VARIANT_CATS=MAIN_SHOW_CATS∪SHEAR_SHOW_CATS`;
    `build_animations` 依 `TIER_VARIANT_CATS` 決定產變體 → wobble 現在也產 `{beat}__{tier}`。
  - `amplify_bone_tl` 對 `shear` 通道 `v'=g*v`(0 對稱,同 rotate):0 端點仍 0、符號序列不變
    (阻尼簽章保形)、相繼極值同乘 g>0 → 嚴格遞減仍成立、峰值隨 g 單調變大。
  - `MAIN_SHOW_CATS` **未動** → (J)/(J-2) 閘用 scale/rotate 度量的 base 集合不變 → 逐位元零回歸。

真值/fixture 同 (E/H/I/J/G-4'):從**先驗庫**(slot_bigwin,含 wobble beat)經 `analyze_target`
→ **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。閘驗**客觀結構
簽章(峰隨檔位遞增 + 阻尼振盪保形)**,非美感;負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  S1 present+routing+base : 每 wobble beat × 每檔位皆產 `{beat}__{tier}` 且 finite/有 bone、≥1 bone 帶
                            shear;名經 `beat_category` 仍路由回 wobble;base(tiers=None)逐位元不變。
  S2 identity interface   : **每檔位**——各 bone sample(0)/sample(dur) 皆 setup identity 且 shear 首尾 0
                            → 與 In/Loop/Out 無縫串接(檔位不破壞介面契約)。
  S3 crux shear monotone  : **每 wobble beat**——shear 擺幅峰值 max|shearX| Super<Mega<Omg<Legend
                            **嚴格遞增**(端到端經 build_animations 量;這是 G-4'' 的核心宣稱)。
  S4 damped signature kept: **每檔位每 bone**——shearX 序列 (a)首尾 0;(b)繞 0 變號 ≥3;(c)相繼極值嚴格
                            遞減(阻尼)→ 增益放大峰值但不改振盪/遞減結構(簽章對所有檔位保形)。
  S5 neg-control/isolation: (a)**平增益守衛**:增益階梯全 1.0 → S3 峰值單調 FALSE(證閘真在測遞增,非恆真);
                            (b)base=Super 逐位元 == 無檔位 wobble(base tier 向後相容);
                            (c)shear 增益**隔離**:scale/rotate 主秀 beat(hit…)的檔位變體不含 shear 通道
                               (shear 放大不外洩到非 shear 節拍);
                            (d)MAIN_SHOW_CATS 未被污染(仍為原 6 類,wobble 不在其中 → (J) 度量不受影響)。

用法:
  python3 validate_tier_shear.py            # 摘要
  python3 validate_tier_shear.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
# 復用 G-4' 的 shear 度量,確保簽章判準與 shear-gen 閘完全一致
from validate_shear_gen import (_shear_x, _sign_changes_zero,
                                _extrema_mags_decreasing, _wobble_beats)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0     # 度,base wobble 峰值 |shearX| 下限(同 G-4')
_EXPECT_MAIN = {"hit", "reveal", "burst", "combo", "charge", "cascade"}


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/tier_shear_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _shear_peak(anim):
    """整支 anim 的 shear 擺幅峰值 = max over bones of max|shearX|(無 shear → 0)。"""
    peak = 0.0
    for ch in anim.get("bones", {}).values():
        sx = _shear_x(ch)
        if sx:
            peak = max(peak, max(abs(v) for v in sx))
    return peak


def _is_increasing(seq):
    return all(seq[i + 1] > seq[i] + 1e-9 for i in range(len(seq) - 1))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                       # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)     # 帶檔位
    wobble_beats = _wobble_beats(base)                        # base wobble beat 名(無 __ )
    R = {}

    # ---- S1 present + routing + backward-compat base ----
    s1 = {"wobble_beats": wobble_beats, "missing": [], "not_finite": [],
          "no_bones": [], "no_shear": [], "misrouted": [], "base_changed": []}
    for beat in wobble_beats:
        for t in TIERS:
            vk = "{}__{}".format(beat, t)
            an = anims.get(vk)
            if an is None:
                s1["missing"].append(vk); continue
            if not SA.all_finite(an):
                s1["not_finite"].append(vk)
            if not an.get("bones"):
                s1["no_bones"].append(vk)
            if not any(_shear_x(ch) for ch in an.get("bones", {}).values()):
                s1["no_shear"].append(vk)
            if G.beat_category(vk) != "wobble":
                s1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:                                            # base 逐位元不變
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            s1["base_changed"].append(k)
    s1_pass = bool(wobble_beats) and not any(s1[k] for k in
                  ("missing", "not_finite", "no_bones", "no_shear", "misrouted", "base_changed"))
    R["S1_present_routing"] = {
        "n_variants_expected": len(wobble_beats) * len(TIERS),
        "n_variants_present": len(wobble_beats) * len(TIERS) - len(s1["missing"]),
        **s1, "pass": s1_pass}

    # ---- S2 identity interface per tier ----
    s2 = {"bad_interface": [], "shear_endpoints_nonzero": []}
    for beat in wobble_beats:
        for t in TIERS:
            an = anims["{}__{}".format(beat, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                s2["bad_interface"].append("{}__{}".format(beat, t))
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                    s2["shear_endpoints_nonzero"].append("{}__{}::{}".format(beat, t, bn))
    R["S2_identity_interface"] = {**s2,
        "pass": not s2["bad_interface"] and not s2["shear_endpoints_nonzero"]}

    # ---- S3 crux: shear peak strictly increasing per wobble beat ----
    s3 = {"beats": {}, "fail": []}
    for beat in wobble_beats:
        peaks = [_shear_peak(anims["{}__{}".format(beat, t)]) for t in TIERS]
        mono = _is_increasing(peaks)
        s3["beats"][beat] = {"shear_peak": [round(p, 3) for p in peaks], "monotone": mono}
        if not mono:
            s3["fail"].append(beat)
    R["S3_shear_monotone"] = {**s3, "pass": bool(s3["beats"]) and not s3["fail"]}

    # ---- S4 damped-oscillation signature preserved per tier ----
    s4 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": []}
    for beat in wobble_beats:
        for t in TIERS:
            for bn, ch in anims["{}__{}".format(beat, t)].get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(beat, t, bn)
                if not (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6):
                    s4["bad_endpoints"].append(key)
                if _sign_changes_zero(sx) < 3:
                    s4["few_sign_changes"].append(key)
                if not _extrema_mags_decreasing(sx):
                    s4["not_damped"].append(key)
    s4_pass = not any(s4[k] for k in s4)
    R["S4_damped_signature"] = {**s4, "pass": s4_pass}

    # ---- S5 negative controls / isolation ----
    s5 = {}
    # (a) 平增益守衛:全 1.0 → 峰值單調 FALSE
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat = False
    for beat in wobble_beats:
        pk = [_shear_peak(flat_anims["{}__{}".format(beat, t)]) for t in TIERS]
        if _is_increasing(pk):
            any_mono_flat = True
    s5["a_flat_guard"] = {"any_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) base=Super 逐位元 == 無檔位 wobble(base tier 向後相容)
    super_diff = []
    for beat in wobble_beats:
        vk = "{}__Super".format(beat)
        if json.dumps(anims[vk], sort_keys=True) != json.dumps(base[beat], sort_keys=True):
            super_diff.append(beat)
    s5["b_super_eq_base"] = {"diff": super_diff, "pass": not super_diff}
    # (c) shear 增益隔離:scale/rotate 主秀 beat 的檔位變體不含 shear 通道
    leak = []
    for nm, an in anims.items():
        if "__" not in nm:
            continue
        base_name = nm.rsplit("__", 1)[0]
        if G.beat_category(base_name) == "wobble":
            continue
        sheared = [bn for bn, ch in an.get("bones", {}).items() if _shear_x(ch)]
        if sheared:
            leak.append((nm, sheared))
    s5["c_shear_isolated"] = {"leaked": leak, "pass": not leak}
    # (d) MAIN_SHOW_CATS 未被污染(wobble 不在其中 → (J) 度量不受影響)
    main_ok = (set(TV.MAIN_SHOW_CATS) == _EXPECT_MAIN and "wobble" not in TV.MAIN_SHOW_CATS
               and "wobble" in TV.SHEAR_SHOW_CATS and "wobble" in TV.TIER_VARIANT_CATS)
    s5["d_main_cats_clean"] = {"main_show_cats": sorted(TV.MAIN_SHOW_CATS),
                              "shear_show_cats": sorted(TV.SHEAR_SHOW_CATS),
                              "pass": main_ok}
    R["S5_neg_control"] = {**s5, "pass": all(v["pass"] for v in s5.values())}

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
        for k in ["S1_present_routing", "S2_identity_interface", "S3_shear_monotone",
                  "S4_damped_signature", "S5_neg_control"]:
            print("{:24s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("S3 shear peak by tier (Super/Mega/Omg/Legend):")
        for beat, d in R["S3_shear_monotone"]["beats"].items():
            print("  {:10s} {}".format(beat, d["shear_peak"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
