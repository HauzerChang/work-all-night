#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 體積守恆非均勻 scale 節拍)接檔位差異化(純 CPU)。

一路的 honest boundary:G-4''''(`validate_squash_gen.py`)讓 `gen_squash` 成為第一個**同時**產
shear + 非均勻 scale(體積守恆擠壓)的生成器,但當時 **squash 被排除在 `MAIN_SHOW_CATS` 之外** ——
因為 (J) 的幅度增益 `_amp_scale` 是**逐軸只放大 identity 上方 overshoot**:對 squash 會脹 scaleX(>1)
卻保留 scaleY(<1)樓地板 → **破壞體積守恆**(scaleX·scaleY≠1)。故「檔位愈高擠壓愈強」這個本該有的
檔位簽章,squash 一直沒有(又一「檔位機制就緒 ≠ 每個新通道接上」缺口,同 E/H/I/J/G-4'/G-4'')。

本次(G-4''''')補上**耦合 amplify**(`tier_variants._amp_scale_coupled`):放大**拉長軸**的 overshoot、
壓縮軸設其**倒數** → scaleX·scaleY≡1(面積守恆)在**任一檔位**保持,而擠壓非均勻度(拉長量/壓扁量)
隨檔位**嚴格遞增**;同源的 shearX 峰亦隨檔位遞增(shear 走既有 v'=g*v)→ squash 成為**雙通道
(shear + 體積守恆非均勻 scale)同時檔位差異化**的第一個節拍。squash 併入 `MAIN_SHOW_CATS`,
`build_animations` 依 `COUPLED_SCALE_CATS` 路由該用耦合 amplify(squash)或逐軸(其餘主秀)。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章**
(體積守恆 + 非均勻遞增 + 阻尼 shear 遞增)非美感;crux 負對照(ST5:逐軸 amplify 破守恆)證
耦合 amplify 的必要性與閘的鑑別力。從**先驗庫**(slot_bigwin) → **真實 build_spine robot 骨架**
→ `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  ST1 present + backward-compat : squash base beat 雙通道(shear+非均勻 scale);每檔位 `squash__{tier}`
                                 皆產出、finite、有 bone、≥1 bone **同時**帶 shear+scale、名經 `beat_category`
                                 仍路由回 squash;**base(In/Loop/Out + base squash)逐位元不變**(帶/不帶
                                 tier_gains 相同);**Super(g=1.0)逐位元 == base squash**(耦合 amplify 於 g=1 為 identity)。
  ST2 crux — 耦合守恆 + 非均勻遞增: **每個檔位**的 squash bone,其每個內部 scale 極值 |scaleX·scaleY−1|≤TOL_VOL
                                 (面積守恆在檔位放大下仍保持);且峰**非均勻** |scaleX−scaleY| 與峰**拉長**
                                 (scaleX−1)皆 Super<Mega<Omg<Legend **嚴格遞增**(檔位擠壓簽章),
                                 且 Super 峰 == base 峰(向後相容)。
  ST3 shear 雙通道遞增 + 阻尼保形: squash 的 shearX 峰亦 Super<Mega<Omg<Legend **嚴格遞增**(Super==base);
                                 且**每個檔位**仍(a)首尾 shearX==0;(b)繞 0 變號≥3;(c)相繼極值嚴格遞減
                                 (阻尼簽章保形)—— shear 與 scale 兩通道**同時**隨檔位放大而各自簽章不破。
  ST4 identity 介面(可插 Loop)  : 每檔位 sample(0)/sample(dur) identity,且 shear 首尾 0 + scale 首尾 (1,1)。
  ST5 crux 負對照 — 逐軸破守恆    : 對 base squash 施**逐軸** amplify(`amplify_bone_tl(coupled=False)`,Legend 增益)
                                 → ≥1 內部極值 |scaleX·scaleY−1| **> TOL_VOL**(逐軸只脹 scaleX、保留 scaleY 樓地板
                                 → 破壞面積守恆);對照**耦合** amplify 同增益仍守恆 → 證耦合 amplify 的必要性
                                 (沒它 squash 無法檔位差異化)與閘測「守恆」非恆真。
  ST6 負對照/隔離                : (a) **平增益守衛**:增益階梯全 1.0 → ST2 非均勻遞增 FALSE 且各檔位 squash
                                 逐位元 == base;(b) **耦合 amplify 單元測**:`_amp_scale_coupled(1,1,g)`==(1,1)
                                 (identity 保介面)、對 (1+q,1/(1+q)) g>1 → 積≈1 且拉長/非均勻皆增大;
                                 (c) **耦合隔離**:非 squash 的主秀 tier 變體(如 wobble,shear-only)**不被**耦合
                                 路徑波及(不生 scale 倒數鍵);(d) **加性**:移除 squash 的 storyboard → 其餘
                                 beat(含 wobble tier 變體)逐位元不變(零回歸)。

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
# 復用 G-4' 的 shear 讀取與阻尼簽章判準(與 shear-gen / wobble-tier / squash-gen 閘完全一致)
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
# 復用 G-4'''' 的 scale 讀取 / 內部極值 / 體積守恆判準
from validate_squash_gen import _scale_xy, _interior_scale, _sq3_eval

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
TOL_VOL = 2e-4      # 體積守恆 |scaleX·scaleY−1| 上限(耦合實測 ≤1e-4 主因倒數 4 位捨入;逐軸負對照 >0.10 → >500× 鑑別餘裕)
MIN_SHEAR = 5.0     # base squash 峰 |shearX| 下限
MIN_ANISO = 0.05    # base squash 峰非均勻 |scaleX−scaleY| 下限


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
    """該 anim 全 bone 的峰非均勻 |scaleX−scaleY|(無 scale 回 0)。"""
    vals = []
    for ch in anim.get("bones", {}).values():
        xy = _scale_xy(ch)
        if xy:
            vals.append(max(abs(sx - sy) for (sx, sy) in xy))
    return max(vals, default=0.0)


def _stretch_peak(anim):
    """該 anim 全 bone 的峰拉長 max(scaleX)−1(無 scale 回 0)。"""
    vals = []
    for ch in anim.get("bones", {}).values():
        xy = _scale_xy(ch)
        if xy:
            vals.append(max(sx for (sx, sy) in xy) - 1.0)
    return max(vals, default=0.0)


def _is_strict_inc(xs):
    return len(xs) >= 2 and all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def _dual_bones(anim):
    """≥1 bone 同時帶 shear 與 scale 通道 → dict {bone: chans}。"""
    return {bn: ch for bn, ch in anim.get("bones", {}).items() if _shear_x(ch) and _scale_xy(ch)}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                       # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)    # 帶檔位
    squash_beats = _squash_beats(base)
    R = {}

    # ---- ST1 present + backward-compat ----
    s1 = {"squash_beats": squash_beats, "base_weak": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": [], "super_ne_base": []}
    for qb in squash_beats:
        if _shear_peak(base[qb]) < MIN_SHEAR or _aniso_peak(base[qb]) < MIN_ANISO:
            s1["base_weak"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                s1["missing"].append(vk); continue
            if not SA.all_finite(an):
                s1["not_finite"].append(vk)
            if not an.get("bones"):
                s1["no_bones"].append(vk)
            if not _dual_bones(an):
                s1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                s1["misrouted"].append((vk, G.beat_category(vk)))
        # Super(g=1.0)逐位元 == base squash
        if json.dumps(anims.get("{}__Super".format(qb)), sort_keys=True) != \
           json.dumps(base[qb], sort_keys=True):
            s1["super_ne_base"].append(qb)
    for k in base:  # base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            s1["base_changed"].append(k)
    s1_pass = (bool(squash_beats) and not any(s1[k] for k in
               ["base_weak", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed", "super_ne_base"]))
    R["ST1_present_backward_compat"] = {**s1, "pass": s1_pass}

    # ---- ST2 crux: coupled volume conservation + anisotropy/stretch monotone across tiers ----
    s2 = {"beats": {}, "bad_volume": [], "fail_aniso_mono": [], "fail_stretch_mono": [], "fail_base": []}
    for qb in squash_beats:
        # (a) 每檔位每 bone 每內部極值 volume ok
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior or not _shear_x(ch):
                    continue
                vok = all(abs(sx * sy - 1.0) <= TOL_VOL for (sx, sy) in interior)
                if not vok:
                    s2["bad_volume"].append("{}__{}::{}".format(qb, t, bn))
        # (b) 峰非均勻 / 峰拉長 隨檔位嚴格遞增,Super==base
        aniso = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        stretch = [_stretch_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_aniso = _aniso_peak(base[qb])
        s2["beats"][qb] = {"aniso": [round(a, 4) for a in aniso],
                           "stretch": [round(s, 4) for s in stretch],
                           "base_aniso": round(base_aniso, 4),
                           "aniso_mono": _is_strict_inc(aniso), "stretch_mono": _is_strict_inc(stretch),
                           "super_eq_base": abs(aniso[0] - base_aniso) <= 1e-4}
        if not _is_strict_inc(aniso):
            s2["fail_aniso_mono"].append(qb)
        if not _is_strict_inc(stretch):
            s2["fail_stretch_mono"].append(qb)
        if abs(aniso[0] - base_aniso) > 1e-4:
            s2["fail_base"].append(qb)
    s2_pass = (bool(s2["beats"]) and not s2["bad_volume"] and not s2["fail_aniso_mono"]
               and not s2["fail_stretch_mono"] and not s2["fail_base"])
    R["ST2_coupled_volume_monotone"] = {**s2, "pass": s2_pass}

    # ---- ST3 shear peak monotone + damped signature per tier ----
    s3 = {"beats": {}, "fail_mono": [], "fail_base": [],
          "bad_endpoints": [], "few_sign_changes": [], "not_damped": []}
    for qb in squash_beats:
        peaks = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_peak = _shear_peak(base[qb])
        s3["beats"][qb] = {"shear_peaks": [round(p, 3) for p in peaks], "base_peak": round(base_peak, 3),
                           "mono": _is_strict_inc(peaks), "super_eq_base": abs(peaks[0] - base_peak) <= 1e-4}
        if not _is_strict_inc(peaks):
            s3["fail_mono"].append(qb)
        if abs(peaks[0] - base_peak) > 1e-4:
            s3["fail_base"].append(qb)
        for t in TIERS:
            for bn, ch in anims["{}__{}".format(qb, t)].get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                if not (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6):
                    s3["bad_endpoints"].append(key)
                if _sign_changes_zero(sx) < 3:
                    s3["few_sign_changes"].append(key)
                if not _extrema_mags_decreasing(sx):
                    s3["not_damped"].append(key)
    s3_pass = (bool(s3["beats"]) and not any(s3[k] for k in
               ["fail_mono", "fail_base", "bad_endpoints", "few_sign_changes", "not_damped"]))
    R["ST3_shear_monotone_damped"] = {**s3, "pass": s3_pass}

    # ---- ST4 identity interface per tier ----
    s4 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            ident = lambda bd: all(abs(bd[k] - IDENT[k]) <= TOL for k in IDENT)
            if not (all(ident(v) for v in start.values()) and all(ident(v) for v in end.values())):
                s4["bad_interface"].append("{}__{}".format(qb, t))
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                    s4["shear_endpoints_nonzero"].append("{}__{}::{}".format(qb, t, bn))
                xy = _scale_xy(ch)
                if xy and (abs(xy[0][0] - 1.0) > 1e-6 or abs(xy[0][1] - 1.0) > 1e-6
                           or abs(xy[-1][0] - 1.0) > 1e-6 or abs(xy[-1][1] - 1.0) > 1e-6):
                    s4["scale_endpoints_nonident"].append("{}__{}::{}".format(qb, t, bn))
    R["ST4_identity_interface"] = {**s4, "pass": (not s4["bad_interface"]
                                                  and not s4["shear_endpoints_nonzero"]
                                                  and not s4["scale_endpoints_nonident"])}

    # ---- ST5 crux neg-control: per-axis amplify breaks volume conservation ----
    s5 = {"per_axis_max_vol_err": {}, "coupled_max_vol_err": {}, "per_axis_broke": [], "coupled_kept": []}
    gL = gains["Legend"]
    for qb in squash_beats:
        for bn, ch in base[qb].get("bones", {}).items():
            if not (_shear_x(ch) and _scale_xy(ch)):
                continue
            naive = TV.amplify_bone_tl(ch, gL, coupled=False)
            coup = TV.amplify_bone_tl(ch, gL, coupled=True)
            n_int = _interior_scale(naive)
            c_int = _interior_scale(coup)
            n_err = max((abs(sx * sy - 1.0) for (sx, sy) in n_int), default=0.0)
            c_err = max((abs(sx * sy - 1.0) for (sx, sy) in c_int), default=0.0)
            key = "{}::{}".format(qb, bn)
            s5["per_axis_max_vol_err"][key] = round(n_err, 5)
            s5["coupled_max_vol_err"][key] = round(c_err, 6)
            if n_err > TOL_VOL:                 # 逐軸應破守恆(負對照生效)
                s5["per_axis_broke"].append(key)
            if c_err <= TOL_VOL:                # 耦合應守恆(對照)
                s5["coupled_kept"].append(key)
    n_dual = len(s5["per_axis_max_vol_err"])
    s5_pass = (n_dual >= 1 and len(s5["per_axis_broke"]) == n_dual
               and len(s5["coupled_kept"]) == n_dual)
    R["ST5_crux_per_axis_breaks_volume"] = {**s5, "n_dual_bones": n_dual, "pass": s5_pass}

    # ---- ST6 negative controls / isolation ----
    s6 = {}
    # (a) 平增益守衛:全 1.0 → 非均勻遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for qb in squash_beats:
        aniso = [_aniso_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(aniso):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    s6["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) 耦合 amplify 單元測
    id_ok = TV._amp_scale_coupled(1.0, 1.0, 2.0) == (1.0, 1.0)
    q = 0.16
    sx1, sy1 = TV._amp_scale_coupled(1.0 + q, 1.0 / (1.0 + q), 1.0)
    sx2, sy2 = TV._amp_scale_coupled(1.0 + q, 1.0 / (1.0 + q), 2.0)
    vol_ok = abs(sx2 * sy2 - 1.0) <= 1e-4
    stretch_up = sx2 > sx1 + 1e-9
    aniso_up = abs(sx2 - sy2) > abs(sx1 - sy1) + 1e-9
    s6["b_coupled_unit"] = {"identity_ok": id_ok, "g2_product": round(sx2 * sy2, 6),
                            "volume_ok": vol_ok, "stretch_up": stretch_up, "aniso_up": aniso_up,
                            "pass": id_ok and vol_ok and stretch_up and aniso_up}
    # (c) 耦合隔離:非 squash 主秀 tier 變體(如 wobble)不被耦合波及 → 不生 scale 倒數鍵。
    #     wobble bones 只帶 shear;耦合路徑只作用 squash → wobble__tier 不應冒出 scale 通道。
    leak = []
    for nm, an in anims.items():
        if "__" not in nm:
            continue
        base_name = nm.split("__")[0]
        if G.beat_category(base_name) == "squash":
            continue
        # 非 squash 的 tier 變體:若其 base beat 無 scale,變體也不該有(耦合倒數鍵不外洩)
        base_has_scale = any(_scale_xy(ch) for ch in base.get(base_name, {}).get("bones", {}).values())
        var_has_scale = any(_scale_xy(ch) for ch in an.get("bones", {}).values())
        if var_has_scale and not base_has_scale:
            leak.append(nm)
    s6["c_coupled_isolated"] = {"leaked": leak, "pass": not leak}
    # (d) 加性:移除 squash 的 storyboard → 其餘 beat(含 wobble tier 變體)逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "squash"]}
    anims_no = G.build_animations(skel, sb_no, tier_gains=gains)
    regressed = [nm for nm, an in anims_no.items()
                 if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True)]
    s6["d_additive_no_regression"] = {"regressed": regressed,
                                      "removed": [b["beat"] for b in sb["beats"]
                                                  if G.beat_category(b["beat"]) == "squash"],
                                      "pass": not regressed}
    R["ST6_neg_control"] = {**s6, "pass": all(v["pass"] for v in s6.values())}

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
        for k in ["ST1_present_backward_compat", "ST2_coupled_volume_monotone",
                  "ST3_shear_monotone_damped", "ST4_identity_interface",
                  "ST5_crux_per_axis_breaks_volume", "ST6_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("ST2 aniso peaks per tier {}:".format(TIERS))
        for qb, d in R["ST2_coupled_volume_monotone"]["beats"].items():
            print("  {:10s} aniso {} stretch {} (base_aniso {})".format(
                qb, d["aniso"], d["stretch"], d["base_aniso"]))
        print("ST3 shear peaks per tier:")
        for qb, d in R["ST3_shear_monotone_damped"]["beats"].items():
            print("  {:10s} {}  (base {})".format(qb, d["shear_peaks"], d["base_peak"]))
        print("ST5 crux per-axis vs coupled max |scaleX*scaleY-1|:")
        for key in R["ST5_crux_per_axis_breaks_volume"]["per_axis_max_vol_err"]:
            print("  {:16s} per-axis {}  coupled {}".format(
                key, R["ST5_crux_per_axis_breaks_volume"]["per_axis_max_vol_err"][key],
                R["ST5_crux_per_axis_breaks_volume"]["coupled_max_vol_err"][key]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
