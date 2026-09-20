#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 體積守恆非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

(G-4'''')讓 `gen_squash` 成為第一個同時產 **shear + 非均勻 scale** 的生成器(斜拉果凍擠壓,
每極值幀 scaleX=1+q、scaleY=1/(1+q) 體積守恆),但當時 squash **不在** `MAIN_SHOW_CATS` —— 因為 (J)
的幅度增益逐軸 `_amp_scale` 只放大 identity 上方 overshoot(拉長軸 scaleX>1 被放大、壓扁軸 scaleY<1
樓地板不動)→ **會破壞 scaleX·scaleY==1**。本次(G-4''''')把 squash 併入 `MAIN_SHOW_CATS`,並為它引入
**耦合 amplify**(`COUPLED_SCALE_CATS` / `_amp_scale_pair`):放大擠壓量 q 於拉長軸(1+g·q,與 `_amp_scale`
對 overshoot 同式)、另一軸取倒數還原守恆(1/(1+g·q))。⇒ squash 的擠壓幅度**與 shear 峰同檔位增益 g
一起隨檔位遞增**,而**體積守恆簽章逐檔位保持**(這是 crux:耦合放大不破壞 scaleX·scaleY==1)。
又一「檔位機制就緒 ≠ 每個新通道接上」實例(同 E/H/I/J/G-4'/G-4''),但 squash 是**首個需耦合放大**者。

真值界定同 (J/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位擠壓愈大 + 斜拉愈斜」是可量化的檔位簽章,以負對照證鑑別力(閘可信)。從**先驗庫** →
**真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  Q1 present + backward-compat : squash base beat 有 shear + 非均勻 scale;每檔位 `squash__{tier}` 皆
                                產出、finite、有 bone、≥1 bone **同時**帶 shear 與非均勻 scale、名經
                                `beat_category` 仍路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains
                                的 base squash + In/Loop/Out 相同 → 純加性)。
  Q2 crux — dual-channel mono  : 各檔位 squash 的峰 |shearX| **與** 峰擠壓量(aniso=|scaleX−scaleY|)
                                皆 Super<Mega<Omg<Legend **嚴格遞增**(端到端經 build_animations 量),
                                且首檔(Super,g=1)兩峰 == base 峰(向後相容)。
  Q3 crux — volume preserved   : **每個檔位**的 squash bone,內部極值幀仍 (a)|scaleX·scaleY−1|≤TOL_VOL
                                (體積守恆**逐檔位保持** —— 耦合放大不破壞守恆,本 candidate 的核心);
                                (b)非均勻(max aniso≥MIN_ANISO);(c)擠壓幅度 |scaleX−1| 相繼遞減(阻尼保形)。
  Q4 identity interface        : **每個檔位**的 squash bone 首尾 scale==(1,1) 且 shear==0
                                (介面契約對所有檔位保形 → 可插 Loop 間)。
  Q5 neg-control               : (a) **平增益守衛**:增益全 1.0 → Q2 遞增 FALSE 且各檔位逐位元==base;
                                (b) **naive-amplify 守衛(crux 鑑別)**:對同一 squash pair 走**逐軸**
                                `amplify_bone_tl(coupled_scale=False)` → 體積守恆**被破壞**
                                (|scaleX·scaleY−1|>TOL_VOL)→ 證「耦合放大」必要、且閘測得出差異;
                                (c) **耦合單元測**:`_amp_scale_pair` 對 identity(1,1)→ 不變;對守恆 pair →
                                仍守恆(積≈1)且擠壓量放大;對均勻 overshoot → 退回逐軸 `_amp_scale`。

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
# 復用 G-4' 的阻尼簽章判準 + G-4'''' 的 squash 判準,確保與既有 squash/wobble 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import (_scale_xy, _interior_scale, _sq3_eval, _has_aniso_scale,
                                 MIN_SHEAR, MIN_ANISO, TOL_VOL)

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


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _aniso_peak(anim):
    """該 anim 全 bone 的峰擠壓量 |scaleX−scaleY|(無非均勻 scale 回 0)。"""
    peaks = [max((abs(sx - sy) for (sx, sy) in _scale_xy(ch)), default=0.0)
             for ch in anim.get("bones", {}).values()]
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

    # ---- Q1 present + backward-compat ----
    q1 = {"squash_beats": squash_beats, "base_no_dual": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": []}
    for qb in squash_beats:
        # base squash 須同時具 shear 與非均勻 scale
        bdual = any(_shear_x(ch) and _has_aniso_scale(ch) for ch in base[qb].get("bones", {}).values())
        if not (bdual and _shear_peak(base[qb]) >= MIN_SHEAR):
            q1["base_no_dual"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                q1["missing"].append(vk); continue
            if not SA.all_finite(an):
                q1["not_finite"].append(vk)
            if not an.get("bones"):
                q1["no_bones"].append(vk)
            if not any(_shear_x(ch) and _has_aniso_scale(ch) for ch in an.get("bones", {}).values()):
                q1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                q1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:      # base(In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變(純加性)
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            q1["base_changed"].append(k)
    q1_pass = (bool(squash_beats) and not any(q1[k] for k in
               ["base_no_dual", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed"]))
    R["Q1_present_backward_compat"] = {**q1, "pass": q1_pass}

    # ---- Q2 crux: dual-channel (shear + squash) amplitude monotone across tiers ----
    q2 = {"beats": {}, "fail_shear_mono": [], "fail_aniso_mono": [], "fail_base": []}
    for qb in squash_beats:
        sh_peaks = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        an_peaks = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_sh, base_an = _shear_peak(base[qb]), _aniso_peak(base[qb])
        sh_mono, an_mono = _is_strict_inc(sh_peaks), _is_strict_inc(an_peaks)
        base_ok = abs(sh_peaks[0] - base_sh) <= 1e-4 and abs(an_peaks[0] - base_an) <= 1e-4
        q2["beats"][qb] = {"shear_peaks": [round(p, 3) for p in sh_peaks],
                           "aniso_peaks": [round(p, 4) for p in an_peaks],
                           "base_shear": round(base_sh, 3), "base_aniso": round(base_an, 4),
                           "shear_mono": sh_mono, "aniso_mono": an_mono, "super_eq_base": base_ok}
        if not sh_mono:
            q2["fail_shear_mono"].append(qb)
        if not an_mono:
            q2["fail_aniso_mono"].append(qb)
        if not base_ok:
            q2["fail_base"].append(qb)
    q2_pass = (bool(q2["beats"]) and not q2["fail_shear_mono"]
               and not q2["fail_aniso_mono"] and not q2["fail_base"])
    R["Q2_dual_channel_monotone"] = {**q2, "pass": q2_pass}

    # ---- Q3 crux: volume-preserving coupling preserved per tier ----
    q3 = {"bad_volume": [], "no_aniso": [], "not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior:
                    continue
                vol_ok, an_ok, damp_ok, detail = _sq3_eval(interior)
                key = "{}__{}::{}".format(qb, t, bn)
                q3["detail"][key] = detail
                if not vol_ok:
                    q3["bad_volume"].append(key)
                if not an_ok:
                    q3["no_aniso"].append(key)
                if not damp_ok:
                    q3["not_damped"].append(key)
    q3_pass = (bool(q3["detail"]) and not q3["bad_volume"]
               and not q3["no_aniso"] and not q3["not_damped"])
    R["Q3_volume_preserved_per_tier"] = {**q3, "pass": q3_pass}

    # ---- Q4 identity interface per tier ----
    q4 = {"bad_scale_ends": [], "bad_shear_ends": []}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                key = "{}__{}::{}".format(qb, t, bn)
                xy = _scale_xy(ch)
                if xy:
                    if not (abs(xy[0][0] - 1) < 1e-6 and abs(xy[0][1] - 1) < 1e-6
                            and abs(xy[-1][0] - 1) < 1e-6 and abs(xy[-1][1] - 1) < 1e-6):
                        q4["bad_scale_ends"].append(key)
                sx = _shear_x(ch)
                if sx and not (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6):
                    q4["bad_shear_ends"].append(key)
    q4_pass = not q4["bad_scale_ends"] and not q4["bad_shear_ends"]
    R["Q4_identity_interface"] = {**q4, "pass": q4_pass}

    # ---- Q5 negative controls ----
    q5 = {}
    # (a) 平增益守衛:全 1.0 → dual-channel 遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for qb in squash_beats:
        sh_peaks = [_shear_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        an_peaks = [_aniso_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(sh_peaks) or _is_strict_inc(an_peaks):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    q5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}

    # (b) naive-amplify 守衛(crux 鑑別):同一守恆 pair 走逐軸(coupled_scale=False)→ 破壞守恆
    g = 2.1
    squash_pair = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0},
                             {"time": 0.5, "x": 1.16, "y": round(1.0 / 1.16, 6)},   # 守恆:積==1
                             {"time": 1.0, "x": 1.0, "y": 1.0}]}
    naive = TV.amplify_bone_tl(squash_pair, g, coupled_scale=False)
    coupled = TV.amplify_bone_tl(squash_pair, g, coupled_scale=True)
    naive_prod = naive["scale"][1]["x"] * naive["scale"][1]["y"]
    coupled_prod = coupled["scale"][1]["x"] * coupled["scale"][1]["y"]
    naive_breaks = abs(naive_prod - 1.0) > TOL_VOL          # 逐軸放大 → 積偏離 1(應 True)
    coupled_holds = abs(coupled_prod - 1.0) <= TOL_VOL      # 耦合放大 → 守恆(應 True)
    coupled_amplified = coupled["scale"][1]["x"] > 1.16 + 1e-9   # 擠壓量確有放大
    q5["b_naive_amplify_guard"] = {"naive_prod": round(naive_prod, 5), "coupled_prod": round(coupled_prod, 6),
                                   "naive_breaks_volume": naive_breaks, "coupled_holds_volume": coupled_holds,
                                   "coupled_amplified": coupled_amplified,
                                   "pass": naive_breaks and coupled_holds and coupled_amplified}

    # (c) 耦合單元測:_amp_scale_pair 三情境
    id_x, id_y = TV._amp_scale_pair(1.0, 1.0, g)
    px, py = TV._amp_scale_pair(1.16, 1.0 / 1.16, g)         # 守恆 squash pair
    ux, uy = TV._amp_scale_pair(1.3, 1.3, g)                 # 均勻 overshoot → 退回逐軸 _amp_scale
    ident_ok = abs(id_x - 1.0) < 1e-9 and abs(id_y - 1.0) < 1e-9
    pair_conserve = abs(px * py - 1.0) <= 1e-3 and abs(px - py) > MIN_ANISO   # 4 位捨入 → ~1e-4 誤差
    pair_amp = abs(px - (1.0 + g * 0.16)) <= 1e-4           # 拉長軸 = 1+g·q
    uniform_fallback = abs(ux - (1.0 + g * 0.3)) <= 1e-6 and abs(uy - (1.0 + g * 0.3)) <= 1e-6
    q5["c_coupling_unit"] = {"identity_fixed": ident_ok, "pair_conserve": pair_conserve,
                             "pair_amplified": pair_amp, "uniform_fallback": uniform_fallback,
                             "pass": ident_ok and pair_conserve and pair_amp and uniform_fallback}

    R["Q5_neg_control"] = {**q5, "pass": all(v["pass"] for v in q5.values())}

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
        for k in ["Q1_present_backward_compat", "Q2_dual_channel_monotone",
                  "Q3_volume_preserved_per_tier", "Q4_identity_interface", "Q5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("Q2 peaks per tier {} (shear° / aniso):".format(TIERS))
        for qb, d in R["Q2_dual_channel_monotone"]["beats"].items():
            print("  {:10s} shear {}  aniso {}  (base {}/{})".format(
                qb, d["shear_peaks"], d["aniso_peaks"], d["base_shear"], d["base_aniso"]))
        gd = R["Q5_neg_control"]["b_naive_amplify_guard"]
        print("Q5b naive vs coupled product: naive {} (breaks={}) / coupled {} (holds={})".format(
            gd["naive_prod"], gd["naive_breaks_volume"], gd["coupled_prod"], gd["coupled_holds_volume"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
