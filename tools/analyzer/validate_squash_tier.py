#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

候選 (J) 讓主秀 beat 依檔位**幅度**差異化,(G-4'') 再讓 shear 通道(wobble)隨檔位放大;但 squash
(斜拉果凍**擠壓**,shear + **耦合體積守恆** scale)一直**不在** MAIN_SHOW_CATS —— 因為逐軸 `_amp_scale`
只放大 identity 上方(scaleX>1)卻把 scaleY<1 當樓地板保留 → **破壞** scaleX·scaleY≡1(體積守恆),是
「檔位機制就緒 ≠ 每個新通道接上」自 G-4'''' 留到現在的 honest boundary。本次(G-4''''')把 squash 併入
MAIN_SHOW_CATS,並新增**體積守恆耦合放大** `_amp_scale_coupled`(以 scaleX 復原擠壓量 q、線性放大
q'=g·q、重建 scaleX'=1+q'、scaleY'=1/scaleX')→ squash 的擠壓幅度隨檔位嚴格遞增而 **scaleX·scaleY≡1
恆保持**、shear 峰亦隨檔位遞增(雙通道一起放大),阻尼耦合簽章逐檔保形。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**。
從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  ST1 present + backward-compat : squash base 有 shear+非均勻 scale;每檔位 `squash__{tier}` 皆產出、
                                 finite、有 bone、≥1 bone 同時帶 shear+scale、名經 `beat_category` 仍路由回
                                 squash;**base 逐位元不變**(帶/不帶 tier_gains 的 base + In/Loop/Out 相同)。
  ST2 crux — dual-channel monotone: 各檔位 squash 的**擠壓峰** |scaleX−1| 與 **shear 峰** |shearX| 皆
                                 Super<Mega<Omg<Legend **嚴格遞增**(端到端經 build_animations 量),
                                 且首檔(Super,g=1)兩峰 == base 兩峰(向後相容)。
  ST3 volume-conserv. coupling preserved per tier(crux):**每個**檔位的 squash bone,每個擠壓極值幀:
                                 (a)scaleX·scaleY≈1(|積−1|≤TOL_VOL,面積守恆**在放大後仍保持**);
                                 (b)≥1 極值 |scaleX−scaleY|≥MIN_ANISO(非均勻=真擠壓,非等比 pulse);
                                 (c)擠壓幅度 |scaleX−1| 隨極值嚴格遞減(阻尼耦合)。復用 squash-gen 的 `_sq3_eval`。
  ST4 identity interface per tier: 每檔位 squash bone 首尾 shearX==0 且 scale 首尾 (1,1)(可插 Loop 間)。
  ST5 shear isolated to shear-emitters : 全 storyboard(含所有檔位變體)中,只有 SHEAR_CATS(wobble/squash)
                                 及其 `__tier` 變體帶 shear → `include_shear` 補償對象明確,零 shear 外洩。
  ST6 neg-control              : (a) **平增益守衛**:增益全 1.0 → ST2 遞增 FALSE 且各檔位 == base;
                                 (b) **耦合必要性守衛(crux)**:對真實 squash scale 施**天真** per-axis
                                    `_amp_scale`(舊行為)→ 體積守恆**破壞**(product 峰誤差 ≫ TOL_VOL,
                                    達耦合放大地板的 >100×)→ 證閘測的是「耦合守恆」非「有 scale 即可」、
                                    且耦合放大**必要**;
                                 (c) **耦合隔離**:`amplify_bone_tl(coupled=False)` 對等比 scale(pulse)
                                    → 保持 scaleX==scaleY(不亂耦合);`coupled=True` 對 squash scale
                                    → scaleX·scaleY≈1(證 coupled 旗標只作用於 coupled-scale 類別)。

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
# 復用 G-4' 阻尼簽章判準 + G-4'''' 體積守恆耦合判準(與 shear-gen / squash-gen 閘完全一致)
from validate_shear_gen import _shear_x
from validate_squash_gen import (_scale_xy, _interior_scale, _sq3_eval,
                                 TOL_VOL, MIN_ANISO)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
MIN_SHEAR = 5.0     # 度,base squash 峰值下限(確認確有明顯 shear)
MIN_STRETCH = 0.05  # base squash 擠壓峰 |scaleX−1| 下限(確認確有明顯擠壓)


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
    """該 anim 全 bone 的擠壓峰 |scaleX−1|(去首尾 identity;無 scale 回 0)。"""
    peaks = []
    for ch in anim.get("bones", {}).values():
        interior = _interior_scale(ch)
        if interior:
            peaks.append(max(abs(sx - 1.0) for (sx, sy) in interior))
    return max(peaks, default=0.0)


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
    t1 = {"squash_beats": squash_beats, "base_no_shear": [], "base_no_stretch": [], "missing": [],
          "not_finite": [], "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": []}
    for sq in squash_beats:
        if _shear_peak(base[sq]) < MIN_SHEAR:
            t1["base_no_shear"].append(sq)
        if _stretch_peak(base[sq]) < MIN_STRETCH:
            t1["base_no_stretch"].append(sq)
        for t in TIERS:
            vk = "{}__{}".format(sq, t)
            an = anims.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            if not an.get("bones"):
                t1["no_bones"].append(vk)
            # 至少一 bone 同時帶 shear + scale(dual-channel)
            if not any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values()):
                t1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                t1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    t1_pass = (bool(squash_beats) and not any(t1[k] for k in
               ["base_no_shear", "base_no_stretch", "missing", "not_finite", "no_bones",
                "variant_no_dual", "misrouted", "base_changed"]))
    R["ST1_present_backward_compat"] = {**t1, "pass": t1_pass}

    # ---- ST2 crux: dual-channel (stretch + shear) peaks monotone across tiers ----
    t2 = {"beats": {}, "fail_mono_stretch": [], "fail_mono_shear": [], "fail_base": []}
    for sq in squash_beats:
        st_peaks = [_stretch_peak(anims["{}__{}".format(sq, t)]) for t in TIERS]
        sh_peaks = [_shear_peak(anims["{}__{}".format(sq, t)]) for t in TIERS]
        base_st, base_sh = _stretch_peak(base[sq]), _shear_peak(base[sq])
        mono_st, mono_sh = _is_strict_inc(st_peaks), _is_strict_inc(sh_peaks)
        super_eq = abs(st_peaks[0] - base_st) <= 1e-4 and abs(sh_peaks[0] - base_sh) <= 1e-4
        t2["beats"][sq] = {"stretch_peaks": [round(p, 4) for p in st_peaks],
                           "shear_peaks": [round(p, 3) for p in sh_peaks],
                           "base_stretch": round(base_st, 4), "base_shear": round(base_sh, 3),
                           "mono_stretch": mono_st, "mono_shear": mono_sh, "super_eq_base": super_eq}
        if not mono_st:
            t2["fail_mono_stretch"].append(sq)
        if not mono_sh:
            t2["fail_mono_shear"].append(sq)
        if not super_eq:
            t2["fail_base"].append(sq)
    t2_pass = (bool(t2["beats"]) and not t2["fail_mono_stretch"]
               and not t2["fail_mono_shear"] and not t2["fail_base"])
    R["ST2_dual_channel_monotone"] = {**t2, "pass": t2_pass}

    # ---- ST3 crux: volume-conserving coupling preserved per tier ----
    t3 = {"detail": {}, "fail_volume": [], "fail_aniso": [], "fail_damped": []}
    for sq in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(sq, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior:
                    continue
                vol_ok, aniso_ok, damp_ok, det = _sq3_eval(interior)
                key = "{}__{}::{}".format(sq, t, bn)
                t3["detail"][key] = {"volume_ok": vol_ok, "aniso_ok": aniso_ok,
                                     "damped_ok": damp_ok, **det}
                if not vol_ok:
                    t3["fail_volume"].append(key)
                if not aniso_ok:
                    t3["fail_aniso"].append(key)
                if not damp_ok:
                    t3["fail_damped"].append(key)
    t3_pass = (bool(t3["detail"]) and not t3["fail_volume"]
               and not t3["fail_aniso"] and not t3["fail_damped"])
    R["ST3_volume_coupling_per_tier"] = {**t3, "pass": t3_pass}

    # ---- ST4 identity interface per tier ----
    t4 = {"bad_shear_ends": [], "bad_scale_ends": []}
    for sq in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(sq, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if sx and not (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6):
                    t4["bad_shear_ends"].append("{}__{}::{}".format(sq, t, bn))
                xy = _scale_xy(ch)
                if xy:
                    x0, y0 = xy[0]; x1, y1 = xy[-1]
                    if not (abs(x0 - 1.0) < 1e-6 and abs(y0 - 1.0) < 1e-6
                            and abs(x1 - 1.0) < 1e-6 and abs(y1 - 1.0) < 1e-6):
                        t4["bad_scale_ends"].append("{}__{}::{}".format(sq, t, bn))
    t4_pass = not t4["bad_shear_ends"] and not t4["bad_scale_ends"]
    R["ST4_identity_interface_per_tier"] = {**t4, "pass": t4_pass}

    # ---- ST5 shear isolated to shear-emitters (incl. all tier variants) ----
    t5 = {"leaked": []}
    for nm, an in anims.items():
        base_name = nm.split("__")[0]
        if G.beat_category(base_name) in TV.SHEAR_CATS:
            continue
        sheared = [bn for bn, ch in an.get("bones", {}).items() if _shear_x(ch)]
        if sheared:
            t5["leaked"].append((nm, sheared))
    R["ST5_shear_isolated"] = {**t5, "pass": not t5["leaked"]}

    # ---- ST6 negative controls ----
    t6 = {}
    # (a) 平增益守衛:全 1.0 → 兩峰遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for sq in squash_beats:
        stp = [_stretch_peak(flat_anims["{}__{}".format(sq, t)]) for t in TIERS]
        shp = [_shear_peak(flat_anims["{}__{}".format(sq, t)]) for t in TIERS]
        if _is_strict_inc(stp) or _is_strict_inc(shp):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(sq, t)], sort_keys=True) != \
               json.dumps(base[sq], sort_keys=True):
                flat_base_diff.append("{}__{}".format(sq, t))
    t6["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}

    # (b) 耦合必要性守衛(crux):對真實 squash scale 施天真 per-axis _amp_scale → 體積守恆破壞。
    #     量 coupled 放大 vs naive 放大 的體積誤差峰,證 naive 破壞、耦合必要(比值 ≫1)。
    g_test = gains["Legend"]                       # 用最大檔位增益(破壞最明顯)
    coupled_maxerr, naive_maxerr = 0.0, 0.0
    for sq in squash_beats:
        for bn, ch in base[sq].get("bones", {}).items():
            interior = _interior_scale(ch)
            if not interior:
                continue
            # coupled(本次實作)
            for (sx, sy) in interior:
                cx, cy = TV._amp_scale_coupled(sx, g_test)
                coupled_maxerr = max(coupled_maxerr, abs(cx * cy - 1.0))
            # naive(逐軸 _amp_scale:scaleX>1 放大、scaleY<1 樓地板保留 → 破壞守恆)
            for (sx, sy) in interior:
                nx = round(TV._amp_scale(sx, g_test), 4)
                ny = round(TV._amp_scale(sy, g_test), 4)
                naive_maxerr = max(naive_maxerr, abs(nx * ny - 1.0))
    ratio = (naive_maxerr / coupled_maxerr) if coupled_maxerr > 0 else float("inf")
    t6["b_coupling_necessity"] = {
        "coupled_max_volerr": round(coupled_maxerr, 6), "naive_max_volerr": round(naive_maxerr, 6),
        "ratio_naive_over_coupled": round(ratio, 1),
        # coupled 守恆(≤TOL_VOL)、naive 破壞(>TOL_VOL)、且 naive 遠大於 coupled(>100×)
        "pass": (coupled_maxerr <= TOL_VOL) and (naive_maxerr > TOL_VOL) and (ratio > 100.0)}

    # (c) 耦合隔離:coupled=False 對等比 pulse 保持等比;coupled=True 對 squash scale 守恆。
    g = 2.0
    pulse = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0}, {"time": 0.5, "x": 1.3, "y": 1.3},
                       {"time": 1.0, "x": 1.0, "y": 1.0}]}
    squashy = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0}, {"time": 0.5, "x": 1.16, "y": 0.8621},
                         {"time": 1.0, "x": 1.0, "y": 1.0}]}
    a_pulse = TV.amplify_bone_tl(pulse, g, coupled=False)
    a_squash = TV.amplify_bone_tl(squashy, g, coupled=True)
    pulse_iso = all(abs(f["x"] - f["y"]) < 1e-9 for f in a_pulse["scale"])   # 等比放大仍等比
    pk = a_squash["scale"][1]
    squash_vol = abs(pk["x"] * pk["y"] - 1.0) <= TOL_VOL and abs(pk["x"] - pk["y"]) >= MIN_ANISO
    t6["c_coupled_isolation"] = {"pulse_stays_isotropic": pulse_iso,
                                 "squash_conserved_nonuniform": squash_vol,
                                 "pass": pulse_iso and squash_vol}

    R["ST6_neg_control"] = {**t6, "pass": all(v["pass"] for v in t6.values())}

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
        for k in ["ST1_present_backward_compat", "ST2_dual_channel_monotone",
                  "ST3_volume_coupling_per_tier", "ST4_identity_interface_per_tier",
                  "ST5_shear_isolated", "ST6_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("ST2 per-tier peaks {}:".format(TIERS))
        for sq, d in R["ST2_dual_channel_monotone"]["beats"].items():
            print("  {:8s} stretch {}  shear {}".format(sq, d["stretch_peaks"], d["shear_peaks"]))
        b = R["ST6_neg_control"]["b_coupling_necessity"]
        print("ST6b coupled volErr {} vs naive {} (naive/coupled = {}×)".format(
            b["coupled_max_volerr"], b["naive_max_volerr"], b["ratio_naive_over_coupled"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
