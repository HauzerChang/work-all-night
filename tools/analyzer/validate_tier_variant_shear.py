#!/usr/bin/env python3
"""candidate G-4'' 自我驗收閘 — wobble(shear 通道)接檔位(tier)幅度差異化(純 CPU)。

背景 / honest boundary 接續:
  (J)(`validate_tier_variants.py`)把 slot_bigwin 的 **scale/rotate 主秀** beat 依檔位產幅度差異化
  變體 `{beat}__{tier}`(愈高檔位愈爆);(J-2) 再讓 combo 的**連擊數**隨檔位遞增。但 (J) 的度量只認
  scale/rotate,而 G-4'(`gen_wobble`)產出的 wobble 幅度落在 **shear** 通道 —— 故 G-4' 收尾時明列
  honest boundary:「wobble ∉ MAIN_SHOW_CATS → tier 變體未接」。本閘(G-4'')驗證那一段**已接上**:
  wobble 的 **shearX 峰隨檔位嚴格遞增**,且**端到端**(`build_spine --tier-variants --shear-pivot`)
  放大後的 shear 仍繞關節 pivot 精確不動。

設計(同 (J)/(J-2)):shear 幅度增益 `v'=g*v`(對 0 對稱,同 rotate)——
  只放大幅度,**不動阻尼振盪結構**(繞 0 變號數、相繼極值遞減比 r 皆對所有檔位保形)。
  wobble 走 `tier_variants.SHEAR_SHOW_CATS`(與 scale/rotate 主秀分開列),故 (J) 閘範圍逐位元不變。
  主秀運動無唯一正解(PROPOSAL 手感);閘驗**客觀結構簽章 + 端到端不動點**非美感,負對照證鑑別力。

真值/fixture 同 (E/H/I/J/G-4'):從**先驗庫**(slot_bigwin)經 `analyze_target` → **真實 build_spine
robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  L1 present + backward-compat : 每 wobble beat × 每檔位皆產 `wobble__{tier}`、finite/有 bone/≥1 bone 帶 shear;
                                 變體名經 `beat_category` 仍路由回 wobble;base 逐位元不變;
                                 **`wobble__Super`(g=1.0)逐位元 == base wobble**(向後相容)。
  L2 crux: shear peak monotone : 每 wobble bone 的 |shearX| 峰 Super<Mega<Omg<Legend **嚴格遞增**,
                                 且 == 宣告增益 × base 峰(**精確縮放**,非只單調)。
  L3 signature+interface / tier : **每個檔位**——每 wobble bone shearX(a)首尾 0、(b)繞 0 變號 ≥3、
                                 (c)相繼極值嚴格遞減(阻尼);且 identity 介面(sample rotate/trans/scale
                                 首尾 identity + shear 首尾 0 → 可插 Loop 間)對所有檔位保持。
  L4 orthogonality + isolation : (a)**阻尼比 r 對檔位不變**(Super 與 Legend 的相繼極值比序列相同 →
                                 增益只改幅度、不改振盪結構,幅度⟂結構);(b)shear 隔離:帶檔位建構下,
                                 **非 wobble** 的 beat/變體皆 0 bone 帶 shear(增益不無中生有注入 shear)。
  L5 end-to-end pivot / tier   : `build_spine --animate --tier-variants --shear-pivot`(真實 robot)——
                                 **每個檔位**的 `wobble__{tier}` 凡有關節 pivot 的 bone,pivot 殘差 < TOL_FIX;
                                 內建負對照 = 未補償(繞件中心)大位移。證放大後的 shear(至 Legend 峰)
                                 仍繞關節精確不動(放大幅度 ≠ 破壞不動點)。
  L6 neg-control               : (a)平增益守衛(全 1.0)→ L2 單調性 FALSE(證閘真的在測遞增);
                                 (b)In/Loop/Out 不產 wobble/shear 檔位變體;
                                 (c)加性:tier_gains=None → 無 `wobble__{tier}` 且 base 相同;
                                    移除 wobble 的 storyboard → 其餘 beat 的檔位變體逐位元不變(零回歸)。

用法:
  python3 validate_tier_variant_shear.py            # 摘要
  python3 validate_tier_variant_shear.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
# 復用 G-4' 閘的 shear 度量,確保簽章判準與該閘完全一致
from validate_shear_gen import (_shear_x, _sign_changes_zero, _extrema_mags_decreasing,
                                _is_ident, _psd, MIN_SHEAR, TOL_FIX, MIN_NEG, NEG_RATIO)
from validate_shear_pivot import _world   # 真實 Spine local(含 shear)世界座標求值

GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
TOL = 1e-4
GAIN_TOL = 1e-2     # 峰 == 增益×base 的容差(amplify round 到 4 位)
RATIO_TOL = 1e-6    # 阻尼比對檔位不變的容差


def _skeleton():
    import build_spine
    out = "/tmp/tvshear_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _wobble_bases(anims):
    """base(非檔位變體)的 wobble beat 名。"""
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "wobble"]


def _shear_bones(an):
    """anim → {bone: shearX 序列}(只含帶 shear 通道的 bone)。"""
    return {bn: _shear_x(ch) for bn, ch in an.get("bones", {}).items() if _shear_x(ch)}


def _peak(sx):
    return max(abs(v) for v in sx) if sx else 0.0


def _extrema_mags(vals, dead=1e-6):
    """非零關鍵幀 |v| 序列(供阻尼比檢核)。"""
    return [abs(v) for v in vals if abs(v) > dead]


def _is_increasing(seq, tol=1e-9):
    return all(seq[i + 1] > seq[i] + tol for i in range(len(seq) - 1))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)                                   # {tier: gain}
    base = G.build_animations(skel, sb)                          # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)        # 帶檔位
    wob_bases = _wobble_bases(base)
    R = {}

    # ---- L1 present + backward-compat ----
    l1 = {"wobble_bases": wob_bases, "missing": [], "not_finite": [], "no_bones": [],
          "no_shear": [], "misrouted": [], "base_changed": [], "super_not_bwc": []}
    for wb in wob_bases:
        for t in TIERS:
            vk = "{}__{}".format(wb, t)
            an = anims.get(vk)
            if an is None:
                l1["missing"].append(vk); continue
            if not SA.all_finite(an):
                l1["not_finite"].append(vk)
            if not an.get("bones"):
                l1["no_bones"].append(vk)
            if not _shear_bones(an):
                l1["no_shear"].append(vk)
            if G.beat_category(vk) != "wobble":
                l1["misrouted"].append((vk, G.beat_category(vk)))
        # Super(g=1.0)逐位元 == base wobble(向後相容)
        sup = anims.get("{}__Super".format(wb))
        if json.dumps(sup, sort_keys=True) != json.dumps(base[wb], sort_keys=True):
            l1["super_not_bwc"].append(wb)
    for k in base:                                               # base 逐位元不變
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            l1["base_changed"].append(k)
    l1_pass = bool(wob_bases) and not any(l1[k] for k in l1 if k != "wobble_bases")
    R["L1_present_backward_compat"] = {**l1, "pass": l1_pass}

    # ---- L2 crux: shear peak monotone + exact gain per tier ----
    l2 = {"peaks": {}, "fail_mono": [], "fail_gain": [], "weak": []}
    for wb in wob_bases:
        per_tier = {t: _shear_bones(anims["{}__{}".format(wb, t)]) for t in TIERS}
        bones = sorted(per_tier["Super"])
        for bn in bones:
            peaks = [round(_peak(per_tier[t].get(bn, [])), 4) for t in TIERS]
            l2["peaks"]["{}::{}".format(wb, bn)] = peaks
            if not _is_increasing(peaks):
                l2["fail_mono"].append("{}::{}".format(wb, bn))
            base_peak = peaks[0]                                  # Super == base(g=1.0)
            if base_peak < MIN_SHEAR:
                l2["weak"].append("{}::{}".format(wb, bn))
            # 精確縮放:peak(tier) == gain[tier] * base_peak
            for t, pk in zip(TIERS, peaks):
                if abs(pk - gains[t] * base_peak) > GAIN_TOL:
                    l2["fail_gain"].append(("{}::{}".format(wb, bn), t, pk,
                                            round(gains[t] * base_peak, 4)))
    l2_pass = (bool(l2["peaks"]) and not l2["fail_mono"]
               and not l2["fail_gain"] and not l2["weak"])
    R["L2_shear_peak_monotone"] = {**l2, "pass": l2_pass}

    # ---- L3 damped-oscillation signature + identity interface per tier ----
    l3 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [],
          "bad_interface": [], "shear_endpoints_nonzero": []}
    for wb in wob_bases:
        for t in TIERS:
            an = anims["{}__{}".format(wb, t)]
            for bn, sx in _shear_bones(an).items():
                key = "{}__{}::{}".format(wb, t, bn)
                if not (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6):
                    l3["bad_endpoints"].append(key)
                if _sign_changes_zero(sx) < 3:
                    l3["few_sign_changes"].append(key)
                if not _extrema_mags_decreasing(sx):
                    l3["not_damped"].append(key)
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                l3["bad_interface"].append("{}__{}".format(wb, t))
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                    l3["shear_endpoints_nonzero"].append("{}__{}::{}".format(wb, t, bn))
    l3_pass = not any(l3[k] for k in l3)
    R["L3_signature_interface_per_tier"] = {**l3, "pass": l3_pass}

    # ---- L4 orthogonality (damping ratio tier-invariant) + shear isolation ----
    l4 = {"ratio_detail": {}, "ratio_variant": [], "shear_leak": []}
    # (a) 阻尼比對檔位不變:比較 Super 與 Legend 每 bone 的相繼極值比序列
    for wb in wob_bases:
        sup = _shear_bones(anims["{}__Super".format(wb)])
        leg = _shear_bones(anims["{}__Legend".format(wb)])
        for bn in sorted(sup):
            ms = _extrema_mags(sup[bn]); ml = _extrema_mags(leg[bn])
            rs = [round(ms[i + 1] / ms[i], 6) for i in range(len(ms) - 1)] if len(ms) > 1 else []
            rl = [round(ml[i + 1] / ml[i], 6) for i in range(len(ml) - 1)] if len(ml) > 1 else []
            l4["ratio_detail"]["{}::{}".format(wb, bn)] = {"super": rs, "legend": rl}
            if len(rs) != len(rl) or any(abs(a - b) > RATIO_TOL for a, b in zip(rs, rl)):
                l4["ratio_variant"].append("{}::{}".format(wb, bn))
    # (b) shear 隔離:帶檔位建構下,非 wobble 的 beat/變體皆 0 bone 帶 shear
    for nm, an in anims.items():
        base_nm = nm.split("__")[0]
        if G.beat_category(base_nm) == "wobble":
            continue
        sheared = [bn for bn, ch in an.get("bones", {}).items() if _shear_x(ch)]
        if sheared:
            l4["shear_leak"].append((nm, sheared))
    l4_pass = not l4["ratio_variant"] and not l4["shear_leak"]
    R["L4_orthogonality_isolation"] = {**l4, "pass": l4_pass}

    # ---- L5 end-to-end pivot-fixed per tier via build_spine --tier-variants --shear-pivot ----
    import build_spine
    out = "/tmp/tvshear_sp"
    summ = build_spine.build(_psd(), out, genre=GENRE, animate=True,
                             tier_variants=True, shear_pivot=True)
    sp_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    joints = summ.get("pivot_joints", {})
    centers = summ.get("pivot_centers", {})
    l5 = {"checked": [], "fail_fixed": [], "fail_negctrl": [], "n_checks": 0, "tiers_seen": set()}
    for wb in wob_bases:
        for t in TIERS:
            vk = "{}__{}".format(wb, t)
            an = sp_skel["animations"].get(vk)
            if an is None:
                continue
            for bn, ch in an.get("bones", {}).items():
                if bn not in joints or bn not in centers:
                    continue
                tr = ch.get("translate")
                if not tr:
                    continue
                O = np.array(centers[bn], float); P = np.array(joints[bn], float)
                ellP = P - O
                l5["n_checks"] += 1
                l5["tiers_seen"].add(t)
                ts = [tr[0]["time"] + (tr[-1]["time"] - tr[0]["time"]) * i / 300 for i in range(301)]
                fix = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                       ch.get("shear"), tr, tt) - P)) for tt in ts)
                neg = max(float(np.linalg.norm(_world(ellP, O, ch.get("rotate"), ch.get("scale"),
                                                       ch.get("shear"), None, tt) - P)) for tt in ts)
                rec = {"variant": vk, "bone": bn, "arm": round(float(np.linalg.norm(ellP)), 1),
                       "shear_peak": round(_peak(_shear_x(ch)), 2),
                       "fixed": round(fix, 4), "negctrl": round(neg, 2)}
                l5["checked"].append(rec)
                if not (fix < TOL_FIX):
                    l5["fail_fixed"].append(rec)
                if not (neg > fix * NEG_RATIO and neg >= MIN_NEG):
                    l5["fail_negctrl"].append(rec)
    l5["tiers_seen"] = sorted(l5["tiers_seen"])
    l5_pass = (l5["n_checks"] >= len(TIERS) and len(l5["tiers_seen"]) == len(TIERS)
               and not l5["fail_fixed"] and not l5["fail_negctrl"])
    R["L5_end2end_pivot_per_tier"] = {**l5, "pass": l5_pass}

    # ---- L6 negative controls ----
    l6 = {}
    # (a) 平增益守衛:全 1.0 → 峰單調性 FALSE
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat = False
    for wb in wob_bases:
        per = {t: _shear_bones(flat_anims["{}__{}".format(wb, t)]) for t in TIERS}
        for bn in sorted(per["Super"]):
            peaks = [_peak(per[t].get(bn, [])) for t in TIERS]
            if _is_increasing(peaks):
                any_mono_flat = True
    l6["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) In/Loop/Out 不產 wobble/shear 檔位變體
    staging = [k for k in anims if "__" in k
               and G.beat_category(k.split("__")[0]) in ("intro", "loop", "outro")]
    l6["b_no_staging_variants"] = {"found": staging, "pass": not staging}
    # (c) 加性:tier_gains=None → 無 wobble__tier 且 base 相同;移除 wobble → 其餘變體逐位元不變
    none_variants = [k for k in base if "__" in k]
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "wobble"]}
    anims_no_wob = G.build_animations(skel, sb_no, tier_gains=gains)
    regressed = []
    for nm, an in anims_no_wob.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            regressed.append(nm)
    l6["c_additive"] = {"none_build_variants": none_variants, "regressed": regressed,
                        "removed": [b["beat"] for b in sb["beats"]
                                    if G.beat_category(b["beat"]) == "wobble"],
                        "pass": not none_variants and not regressed}
    l6_pass = all(v["pass"] for v in l6.values())
    R["L6_neg_control"] = {**l6, "pass": l6_pass}

    R["OVERALL_PASS"] = all(R[k]["pass"] for k in R)
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    R = run()
    if a.json:
        print(json.dumps(R, ensure_ascii=False, indent=2, default=list))
    else:
        for k in ["L1_present_backward_compat", "L2_shear_peak_monotone",
                  "L3_signature_interface_per_tier", "L4_orthogonality_isolation",
                  "L5_end2end_pivot_per_tier", "L6_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("L2 shear peak per tier {}:".format(TIERS))
        for key, pk in R["L2_shear_peak_monotone"]["peaks"].items():
            print("  {:22s} {}".format(key, pk))
        print("L5 end-to-end pivot-fixed (tiers {}):".format(R["L5_end2end_pivot_per_tier"]["tiers_seen"]))
        for rec in R["L5_end2end_pivot_per_tier"]["checked"]:
            print("  {:18s} arm {:6.1f} shear {:5.1f}  fixed {:.4f}  negctrl {:.2f}".format(
                rec["variant"], rec["arm"], rec["shear_peak"], rec["fixed"], rec["negctrl"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
