#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

(G-4'''')讓 `gen_squash` 成為第一個同時產出 **shear + 耦合非均勻 scale(體積守恆擠壓)** 的生成器,
但當時 squash **不在** `MAIN_SHOW_CATS` —— 因為檔位放大器 `_amp_scale` 只放大 identity 上方 overshoot、
下方樓地板不動:對 squash 的 scaleX=1+q(拉長,>1)會被放大、scaleY=1/(1+q)(壓扁,<1)被保留 →
**破壞體積守恆**(scaleX·scaleY≠1)。這是 (G-4'''') 明列的 honest boundary。

本次(G-4''''')以**耦合 amplify**(`tier_variants._amp_scale_coupled`)補上:由 scaleX 還原 squash 量 q、
以增益 g 放大成 g·q,再令 scaleY=1/(1+g·q) → **scaleX·scaleY≡1 精確保持**,squash 得以隨檔位差異化
(擠壓愈高檔位愈狠)而體積守恆不破。shear 通道仍走 g*v(同 wobble,G-4'')。**又一「檔位機制就緒 ≠
每個新通道接上」實例**(同 (J)/(G-4'')對 shear)——此處新「通道」是**耦合非均勻 scale 的體積守恆放大**。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位擠壓愈狠(stretch 峰遞增)且體積守恆在每檔位保持」是可量化的檔位簽章,用負對照(尤其
ST4「天真各軸放大會破壞體積守恆」)證鑑別力(閘可信)。從**先驗庫** → **真實 build_spine robot
骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  ST1 present + backward-compat : squash base beat 帶 shear + 非均勻 scale;每檔位 `squash__{tier}` 皆
                                 產出、finite、有 bone、≥1 bone 同時帶 shear+非均勻 scale、名經
                                 `beat_category` 仍路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains
                                 的 base squash + In/Loop/Out 相同);**Super 變體 == base 逐位元**(g=1)。
  ST2 crux — volume + stretch  : **每個檔位**、每個內部擠壓極值幀 (a)|scaleX·scaleY−1|≤TOL_VOL(**體積
                                 守恆在放大後仍保持** —— 耦合 amplify 的關鍵,`_amp_scale` 各軸放大做不到);
                                 (b)scaleX≠scaleY(仍非均勻)。且各檔位**峰 stretch |scaleX−1|**
                                 Super<Mega<Omg<Legend **嚴格遞增**、Super 峰==base 峰(檔位簽章+向後相容)。
  ST3 shear damped + monotone  : **每個檔位**的 squash bone 仍 (a)首尾 shearX==0;(b)繞 0 變號 ≥3;
                                 (c)相繼極值幅度嚴格遞減(阻尼);且各檔位峰 |shearX| **嚴格遞增**
                                 → shear 與 scale 兩通道**一致隨檔位放大**(耦合放大不只動 scale)。
  ST4 coupled necessity (crux) : 對**同一** base squash beat,分別套**耦合** amplify(coupled=True)與
                                 **天真各軸** amplify(coupled=False)於最高檔位增益:耦合版每幀
                                 |scaleX·scaleY−1|≤TOL_VOL(守恆),天真版 max|scaleX·scaleY−1|>BROKEN_VOL
                                 (**破壞守恆**)。⇒ 證耦合 amplify 為必要、且 ST2 的守恆判準有鑑別力(非恆真)。
  ST5 neg-control / isolation  : (a) **平增益守衛**:增益階梯全 1.0 → ST2 stretch 遞增 FALSE 且各檔位
                                 squash 逐位元 == base;
                                 (b) **耦合隔離**:非-squash 主秀 beat(如 combo/hit)之檔位變體其 scale 仍
                                 **等比**(scaleX==scaleY,無非均勻)→ 耦合放大只作用 squash、不外洩;
                                 (c) **加性**:storyboard 移除 squash beat → 其餘 beat 逐位元不變。

用法:
  python3 validate_squash_tier.py            # 摘要
  python3 validate_squash_tier.py --json     # 完整 JSON
"""
import argparse, copy, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
# 復用 G-4' 阻尼簽章判準 + G-4'''' squash 結構判準(同判準 → 與既有閘一致、可信)
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import (_scale_xy, _interior_scale, _sq3_eval, _has_aniso_scale,
                                 TOL_VOL, MIN_ANISO, MIN_SHEAR)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
BROKEN_VOL = 0.05    # ST4:天真各軸放大破壞體積守恆的下限(實測 Legend ≈0.15 → 巨大餘裕 vs TOL_VOL 0.02)


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


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _stretch_peak(anim):
    """該 anim 全 bone 內部擠壓極值的峰 |scaleX−1|(無非均勻 scale 回 0)。"""
    peaks = []
    for ch in anim.get("bones", {}).values():
        interior = _interior_scale(ch)
        if interior:
            peaks.append(max(abs(sx - 1.0) for (sx, sy) in interior))
    return max(peaks, default=0.0)


def _all_interior_prods(anim):
    """該 anim 全 bone 內部擠壓極值的 [(prod, aniso)]。"""
    out = []
    for ch in anim.get("bones", {}).values():
        for (sx, sy) in _interior_scale(ch):
            out.append((sx * sy, abs(sx - sy)))
    return out


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

    # ---- ST1 present + backward-compat ----
    t1 = {"squash_beats": squash_beats, "base_no_shear": [], "base_no_aniso": [], "missing": [],
          "not_finite": [], "no_bones": [], "variant_no_dual": [], "misrouted": [],
          "base_changed": [], "super_ne_base": []}
    for qb in squash_beats:
        if _shear_peak(base[qb]) < MIN_SHEAR:
            t1["base_no_shear"].append(qb)
        if not any(_has_aniso_scale(ch) for ch in base[qb].get("bones", {}).values()):
            t1["base_no_aniso"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            if not an.get("bones"):
                t1["no_bones"].append(vk)
            # ≥1 bone 同時帶 shear 通道 + 非均勻 scale(雙通道皆在)
            dual = any(_shear_x(ch) and _has_aniso_scale(ch) for ch in an.get("bones", {}).values())
            if not dual:
                t1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                t1["misrouted"].append((vk, G.beat_category(vk)))
        # Super 變體 == base 逐位元(g=1.0)
        if json.dumps(anims.get("{}__Super".format(qb)), sort_keys=True) != \
           json.dumps(base[qb], sort_keys=True):
            t1["super_ne_base"].append(qb)
    # base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    t1_pass = (bool(squash_beats) and not any(t1[k] for k in
               ["base_no_shear", "base_no_aniso", "missing", "not_finite", "no_bones",
                "variant_no_dual", "misrouted", "base_changed", "super_ne_base"]))
    R["ST1_present_backward_compat"] = {**t1, "pass": t1_pass}

    # ---- ST2 crux: volume conserved across ALL tiers + stretch monotone ----
    # 判準與 validate_squash_gen 一致:體積守恆 = **每幀** |prod−1|≤TOL_VOL;非均勻 = **該檔位峰**
    # max|scaleX−scaleY|≥MIN_ANISO(阻尼尾端 q 小 → 該幀 aniso 自然小,故看峰不看每幀,同 SQ3 語意)。
    t2 = {"beats": {}, "bad_volume": [], "no_aniso": [], "fail_mono": [], "fail_base": []}
    for qb in squash_beats:
        stretch_peaks = []
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            prods = _all_interior_prods(an)
            for (p, a) in prods:
                if abs(p - 1.0) > TOL_VOL:
                    t2["bad_volume"].append(("{}__{}".format(qb, t), round(p, 5)))
            aniso_peak = max((a for (p, a) in prods), default=0.0)
            if aniso_peak < MIN_ANISO:
                t2["no_aniso"].append(("{}__{}".format(qb, t), round(aniso_peak, 4)))
            stretch_peaks.append(_stretch_peak(an))
        base_stretch = _stretch_peak(base[qb])
        mono = _is_strict_inc(stretch_peaks)
        super_eq_base = abs(stretch_peaks[0] - base_stretch) <= 1e-4
        t2["beats"][qb] = {"stretch_peaks": [round(p, 4) for p in stretch_peaks],
                           "base_stretch": round(base_stretch, 4),
                           "mono": mono, "super_eq_base": super_eq_base}
        if not mono:
            t2["fail_mono"].append(qb)
        if not super_eq_base:
            t2["fail_base"].append(qb)
    t2_pass = (bool(t2["beats"]) and not t2["bad_volume"] and not t2["no_aniso"]
               and not t2["fail_mono"] and not t2["fail_base"])
    R["ST2_volume_and_stretch"] = {**t2, "pass": t2_pass}

    # ---- ST3 shear damped signature preserved + peak monotone per tier ----
    t3 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [],
          "shear_peaks": {}, "fail_shear_mono": [], "detail": {}}
    for qb in squash_beats:
        peaks = []
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            peaks.append(_shear_peak(an))
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                ends_ok = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                nsc = _sign_changes_zero(sx)
                damp = _extrema_mags_decreasing(sx)
                t3["detail"][key] = {"n_sign_changes": nsc, "damped": damp}
                if not ends_ok:
                    t3["bad_endpoints"].append(key)
                if nsc < 3:
                    t3["few_sign_changes"].append(key)
                if not damp:
                    t3["not_damped"].append(key)
        t3["shear_peaks"][qb] = [round(p, 3) for p in peaks]
        if not _is_strict_inc(peaks):
            t3["fail_shear_mono"].append(qb)
    t3_pass = (bool(t3["detail"]) and not t3["bad_endpoints"] and not t3["few_sign_changes"]
               and not t3["not_damped"] and not t3["fail_shear_mono"])
    R["ST3_shear_damped_monotone"] = {**t3, "pass": t3_pass}

    # ---- ST4 coupled necessity (crux neg-control): naive per-axis amplify breaks volume ----
    # 對同一 base squash beat,套最高檔位增益:耦合版守恆、天真各軸版破壞守恆。
    g_top = gains[TIERS[-1]]
    t4 = {"g": g_top, "beats": {}, "fail": []}
    for qb in squash_beats:
        coupled = TV.amplify_anim(base[qb], g_top, coupled=True)
        naive = TV.amplify_anim(base[qb], g_top, coupled=False)
        c_dev = max((abs(p - 1.0) for (p, a) in _all_interior_prods(coupled)), default=0.0)
        n_dev = max((abs(p - 1.0) for (p, a) in _all_interior_prods(naive)), default=0.0)
        ok = (c_dev <= TOL_VOL) and (n_dev > BROKEN_VOL)
        t4["beats"][qb] = {"coupled_max_vol_dev": round(c_dev, 5),
                           "naive_max_vol_dev": round(n_dev, 5), "pass": ok}
        if not ok:
            t4["fail"].append(qb)
    t4_pass = bool(t4["beats"]) and not t4["fail"]
    R["ST4_coupled_necessity"] = {**t4, "pass": t4_pass}

    # ---- ST5 negative controls / isolation ----
    t5 = {}
    # (a) 平增益守衛:全 1.0 → stretch 遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for qb in squash_beats:
        peaks = [_stretch_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(peaks):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    t5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) 耦合隔離:非-squash 主秀 beat 之檔位變體 scale 仍等比(scaleX==scaleY,無非均勻)
    leak = []
    for nm, an in anims.items():
        base_name = nm.split("__")[0]
        if "__" not in nm or G.beat_category(base_name) == "squash":
            continue
        for bn, ch in an.get("bones", {}).items():
            if _has_aniso_scale(ch):
                leak.append((nm, bn))
    t5["b_coupling_isolation"] = {"aniso_leaked": leak, "pass": not leak}
    # (c) 加性:移除 squash beat → 其餘 beat 逐位元不變
    sb2 = copy.deepcopy(sb)
    sb2["beats"] = [b for b in sb["beats"] if G.beat_category(b["beat"]) != "squash"]
    anims2 = G.build_animations(skel, sb2, tier_gains=gains)
    add_diff = []
    for k, v in anims2.items():
        if json.dumps(v, sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            add_diff.append(k)
    removed_present = [k for k in anims2 if k.split("__")[0] in squash_beats]
    t5["c_additive"] = {"other_beats_changed": add_diff, "squash_still_present": removed_present,
                        "pass": not add_diff and not removed_present}
    R["ST5_neg_control"] = {**t5, "pass": all(v["pass"] for v in t5.values())}

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
        for k in ["ST1_present_backward_compat", "ST2_volume_and_stretch",
                  "ST3_shear_damped_monotone", "ST4_coupled_necessity", "ST5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("ST2 stretch peaks per tier {}:".format(TIERS))
        for qb, d in R["ST2_volume_and_stretch"]["beats"].items():
            print("  {:10s} {}  (base {})".format(qb, d["stretch_peaks"], d["base_stretch"]))
        print("ST3 shear peaks per tier:")
        for qb, ps in R["ST3_shear_damped_monotone"]["shear_peaks"].items():
            print("  {:10s} {}".format(qb, ps))
        print("ST4 coupled-vs-naive volume dev (g={}):".format(R["ST4_coupled_necessity"]["g"]))
        for qb, d in R["ST4_coupled_necessity"]["beats"].items():
            print("  {:10s} coupled {} vs naive {}".format(
                qb, d["coupled_max_vol_dev"], d["naive_max_vol_dev"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
