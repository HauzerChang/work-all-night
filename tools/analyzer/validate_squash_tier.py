#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 體積守恆耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

一路的 honest boundary:G-4''''(`validate_squash_gen.py`)讓生成器 `gen_squash` 第一次產出**耦合的
shear + 非均勻 scale**(scaleX·scaleY≡1 的體積守恆擠壓),但當時 squash **刻意不在** `MAIN_SHOW_CATS` ——
因為舊的 `amplify_bone_tl`/`_amp_scale`(只放大 identity 上方 overshoot、下方樓地板不動)會把 scaleX(>1)
放大而 scaleY(<1 壓扁)保留 → **破壞體積守恆**(scaleX·scaleY≠1)。本次(G-4''''')補上**耦合 amplify**
(`_amp_scale_coupled`:log 空間同指數放大 v'=v**g,兩軸同 g 次冪 → 積 (sx·sy)**g 守恆),把 squash
併入 `MAIN_SHOW_CATS`,使 **squash 的非均勻峰(與 shear 峰)隨檔位嚴格遞增,而體積守恆與阻尼簽章在每個
檔位保持**(愈高檔位=更斜更擠,非別種運動;守恆不破)。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位擠壓愈非均勻」是可量化的檔位簽章,用負對照證鑑別力(閘可信)—— 尤其 P5(b) 直接示範
「舊樓地板 amplify 會破壞守恆、耦合 amplify 才守得住」,證此候選的必要性可被量測。從**先驗庫** →
**真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  P1 present + backward-compat   : 每檔位 `squash__{tier}` 皆產出、finite、有 bone、≥1 bone **同時**帶
                                  shear 與 scale 通道、名經 `beat_category` 仍路由回 squash;
                                  **base squash 逐位元不變**(帶/不帶 tier_gains 的 base squash + In/Loop/Out 相同)。
  P2 crux — monotone + 守恆      : (a) 非均勻峰 |scaleX−scaleY| Super<Mega<Omg<Legend **嚴格遞增**、且
                                  Super(g=1)== base(向後相容);(b) shear 峰 |shearX| 亦嚴格遞增(shear 通道
                                  同步放大);(c) **crux**:**每個**檔位的**每個** scale 極值幀仍 |scaleX·scaleY−1|
                                  ≤ TOL_VOL(體積守恆在放大後存活 —— 舊樓地板 amplify 辦不到,見 P5b)。
  P3 signatures preserved/tier   : **每個**檔位的 squash bone 仍 (a) shear 阻尼振盪(首尾 0、繞 0 變號 ≥3、
                                  相繼極值嚴格遞減);(b) SQ3 體積守恆耦合(volume_ok、aniso_ok、squash 幅度
                                  |scaleX−1| 嚴格遞減)。→ 兩通道簽章逐檔位保形。
  P4 coupling isolated           : 全 storyboard(含所有檔位變體)中,**只有 squash 及其 `__tier` 變體**
                                  同時帶 shear 且非均勻 scale(耦合)→ squash 獨佔耦合,對既有節拍零外洩。
  P5 neg-control                 : (a) **平增益守衛**:增益全 1.0 → P2 非均勻峰遞增 FALSE 且各檔位 squash 逐位元
                                  == base;(b) **crux 單元測(必要性)**:對真實 squash 極值 (sx,sy)(sx·sy≈1),
                                  **舊** `_amp_scale`(逐軸樓地板)以 g=2.1 放大 → 積偏離 1(守恆**破壞**),而
                                  **新** `_amp_scale_coupled`(v**g)→ 積≈1(守恆保持)→ 證耦合 amplify 非多餘、
                                  且閘能鑑別;(c) **耦合 amplify 性質單元測**:`_amp_scale_coupled(1,g)==1`
                                  (identity 介面)、g==1 → v(向後相容)、對合成 (1.2,1/1.2) 任意 g 積守恆。

用法:
  python3 validate_squash_tier.py            # 摘要
  python3 validate_squash_tier.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
# 復用 G-4' 的阻尼簽章判準(與 shear-gen / wobble-tier / squash-gen 閘完全一致)
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
# 復用 G-4'''' 的 squash 讀取/耦合判準(與 squash-gen 閘完全一致)
from validate_squash_gen import (_scale_xy, _interior_scale, _sq3_eval, _has_aniso_scale,
                                 _is_ident, TOL_VOL, MIN_ANISO, MIN_SHEAR)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/squash_tier_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _squash_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "squash"]


def _aniso_peak(anim):
    """該 anim 全 bone scale 通道的峰 |scaleX−scaleY|(無 scale 回 0)。"""
    peaks = [max((abs(sx - sy) for (sx, sy) in _scale_xy(ch)), default=0.0)
             for ch in anim.get("bones", {}).values() if _scale_xy(ch)]
    return max(peaks, default=0.0)


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _worst_volume_dev(anim):
    """該 anim 全 bone 所有 scale 極值幀的最大 |scaleX·scaleY − 1|(無 scale 回 0)。"""
    worst = 0.0
    for ch in anim.get("bones", {}).values():
        for (sx, sy) in _interior_scale(ch):
            worst = max(worst, abs(sx * sy - 1.0))
    return worst


def _is_strict_inc(xs):
    return all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                       # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)    # 帶檔位
    squash_beats = _squash_beats(base)
    R = {}

    # ---- P1 present + backward-compat ----
    p1 = {"squash_beats": squash_beats, "missing": [], "not_finite": [], "no_bones": [],
          "no_dual": [], "misrouted": [], "base_changed": []}
    for qb in squash_beats:
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                p1["missing"].append(vk); continue
            if not SA.all_finite(an):
                p1["not_finite"].append(vk)
            if not an.get("bones"):
                p1["no_bones"].append(vk)
            dual = any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values())
            if not dual:
                p1["no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                p1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:  # base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            p1["base_changed"].append(k)
    p1_pass = (bool(squash_beats) and not any(p1[k] for k in
               ["missing", "not_finite", "no_bones", "no_dual", "misrouted", "base_changed"]))
    R["P1_present_backward_compat"] = {**p1, "pass": p1_pass}

    # ---- P2 crux: monotone aniso/shear peak + volume conserved per tier ----
    p2 = {"beats": {}, "fail_aniso_mono": [], "fail_shear_mono": [], "fail_super_base": [],
          "fail_volume": []}
    for qb in squash_beats:
        an_peaks = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        sh_peaks = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        vol_devs = [_worst_volume_dev(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_aniso = _aniso_peak(base[qb])
        aniso_mono = _is_strict_inc(an_peaks)
        shear_mono = _is_strict_inc(sh_peaks)
        super_eq = abs(an_peaks[0] - base_aniso) <= 1e-4
        vol_ok = all(d <= TOL_VOL for d in vol_devs)
        p2["beats"][qb] = {"aniso_peaks": [round(a, 4) for a in an_peaks],
                           "shear_peaks": [round(s, 3) for s in sh_peaks],
                           "worst_vol_dev": [round(d, 6) for d in vol_devs],
                           "base_aniso": round(base_aniso, 4),
                           "aniso_mono": aniso_mono, "shear_mono": shear_mono,
                           "super_eq_base": super_eq, "volume_ok": vol_ok}
        if not aniso_mono:
            p2["fail_aniso_mono"].append(qb)
        if not shear_mono:
            p2["fail_shear_mono"].append(qb)
        if not super_eq:
            p2["fail_super_base"].append(qb)
        if not vol_ok:
            p2["fail_volume"].append(qb)
    p2_pass = (bool(p2["beats"]) and not p2["fail_aniso_mono"] and not p2["fail_shear_mono"]
               and not p2["fail_super_base"] and not p2["fail_volume"])
    R["P2_monotone_volume_conserved"] = {**p2, "pass": p2_pass}

    # ---- P3 shear + coupling signatures preserved per tier ----
    p3 = {"bad_shear": [], "bad_coupling": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                interior = _interior_scale(ch)
                if not sx or not interior:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                ends_ok = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                nsc = _sign_changes_zero(sx)
                damp = _extrema_mags_decreasing(sx)
                shear_ok = ends_ok and nsc >= 3 and damp
                vok, aok, dok, det = _sq3_eval(interior)
                coupling_ok = vok and aok and dok
                p3["detail"][key] = {"shear_ok": shear_ok, "n_sign_changes": nsc, "damped": damp,
                                     "volume_ok": vok, "aniso_ok": aok, "sq_damped": dok}
                if not shear_ok:
                    p3["bad_shear"].append(key)
                if not coupling_ok:
                    p3["bad_coupling"].append(key)
    p3_pass = bool(p3["detail"]) and not p3["bad_shear"] and not p3["bad_coupling"]
    R["P3_signatures_per_tier"] = {**p3, "pass": p3_pass}

    # ---- P4 coupling isolated to squash (incl. all tier variants) ----
    p4 = {"leaked": []}
    for nm, an in anims.items():
        base_name = nm.split("__")[0]
        if G.beat_category(base_name) == "squash":
            continue
        for bn, ch in an.get("bones", {}).items():
            if _shear_x(ch) and _has_aniso_scale(ch):
                p4["leaked"].append((nm, bn))
    R["P4_coupling_isolated"] = {**p4, "pass": not p4["leaked"]}

    # ---- P5 negative controls ----
    p5 = {}
    # (a) 平增益守衛:全 1.0 → 非均勻峰遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for qb in squash_beats:
        peaks = [_aniso_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(peaks):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    p5["a_flat_guard"] = {"flat_any_aniso_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) crux 單元測:舊樓地板 amplify 破壞守恆、耦合 amplify 守住(證此候選必要且可鑑別)
    g = TV.gains_for(GENRE)["Legend"]   # 2.1
    # 取真實 base squash 一個極值幀 (sx,sy)(sx·sy≈1)
    ex = None
    for bn, ch in base[squash_beats[0]].get("bones", {}).items():
        it = _interior_scale(ch)
        if it:
            ex = it[0]; break
    sx, sy = ex
    floor_prod = TV._amp_scale(sx, g) * TV._amp_scale(sy, g)     # 舊逐軸樓地板
    coupled_prod = TV._amp_scale_coupled(sx, g) * TV._amp_scale_coupled(sy, g)  # 新耦合
    floor_breaks = abs(floor_prod - 1.0) > TOL_VOL              # 舊法應破壞守恆
    coupled_keeps = abs(coupled_prod - 1.0) <= TOL_VOL          # 新法應守住
    p5["b_floor_breaks_coupled_keeps"] = {
        "extreme": [round(sx, 4), round(sy, 4)], "gain": g,
        "floor_product": round(floor_prod, 5), "coupled_product": round(coupled_prod, 6),
        "floor_breaks_volume": floor_breaks, "coupled_keeps_volume": coupled_keeps,
        "pass": floor_breaks and coupled_keeps}
    # (c) 耦合 amplify 性質單元測:identity 保介面、g==1 向後相容、任意 g 積守恆
    id_ok = abs(TV._amp_scale_coupled(1.0, 3.7) - 1.0) < 1e-12
    g1_ok = abs(TV._amp_scale_coupled(1.23, 1.0) - 1.23) < 1e-12
    prod_ok = all(abs(TV._amp_scale_coupled(1.2, gg) * TV._amp_scale_coupled(1.0 / 1.2, gg) - 1.0) < 1e-9
                  for gg in (0.5, 1.0, 1.7, 2.1, 3.0))
    p5["c_coupled_properties"] = {"identity_preserved": id_ok, "g1_backward_compat": g1_ok,
                                  "product_conserved_any_g": prod_ok,
                                  "pass": id_ok and g1_ok and prod_ok}
    R["P5_neg_control"] = {**p5, "pass": all(v["pass"] for v in p5.values())}

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
        for k in ["P1_present_backward_compat", "P2_monotone_volume_conserved",
                  "P3_signatures_per_tier", "P4_coupling_isolated", "P5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("P2 per tier {}:".format(TIERS))
        for qb, d in R["P2_monotone_volume_conserved"]["beats"].items():
            print("  {:8s} aniso {}  shear {}  worst_vol_dev {}".format(
                qb, d["aniso_peaks"], d["shear_peaks"], d["worst_vol_dev"]))
        b = R["P5_neg_control"]["b_floor_breaks_coupled_keeps"]
        print("P5b necessity: extreme {} g={} -> floor_prod {} (breaks={}), coupled_prod {} (keeps={})".format(
            b["extreme"], b["gain"], b["floor_product"], b["floor_breaks_volume"],
            b["coupled_product"], b["coupled_keeps_volume"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
