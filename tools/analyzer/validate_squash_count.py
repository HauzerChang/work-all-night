#!/usr/bin/env python3
"""candidate (G-4'''''-c) 自我驗收閘 — squash 擠壓**段數**隨檔位遞增(count-aware,純 CPU)。

candidate (G-4''''') 讓 squash 的 shearX 峰**幅度** + 非均勻 scale 擠壓強度隨檔位遞增(耦合 amplify,
體積守恆),但各檔位仍是**同樣 4 段**阻尼擠壓 —— 有「擠多重」沒「擠幾下」。本次 (G-4'''''-c) 補上
squash 的擠壓**段數** nosc **隨檔位嚴格遞增**(Super 4 → Mega 5 → Omg 6 → Legend 7)。

**關鍵:幅度增益(即使是耦合)加不出擠壓段數** —— 段數是關鍵幀**拓樸**(shear 繞 0 交替極值個數,
= scale 內部極值個數,由 `_squash_env` 同點耦合),必須在 `gen_squash` 生成當下決定;事後
`amplify_bone_tl`(逐軸或耦合)只能同比放大既有極值、無法多長一段。故不走 amplify,而是對 squash
檔位變體以該檔位 nosc **重生成**整個 beat,再疊 (G-4''''') 的**耦合**幅度增益 g。

**squash 是第一個同時 ∈ COUNT_AWARE_CATS 與 COUPLED_SCALE_CATS 的節拍** —— 故本閘的 crux 是**三效正交**:
① 重生成把 shear 段數 / scale 極值數變多(段數軸);② 耦合 amplify 把每個極值放大(幅度軸);
③ 每個(含新長出的)極值仍 scaleX·scaleY≡1(守恆)。三者互不破壞 —— 這是 wobble count-aware (G-4''')
所沒有的額外約束(wobble 只有純 shear,無跨通道守恆)。

真值界定同 (E/H/I/J/J-2/G-4'/G-4''/G-4'''/G-4''''/G-4'''''):主秀運動無唯一正解(PROPOSAL 手感),
閘驗**客觀結構簽章非美感**(段數遞增 + 每極值守恆 + 阻尼保形);負對照證鑑別力(閘可信)。從**先驗庫**
→ **真實 build_spine robot 骨架** → `build_animations(..., tier_gains, tier_squash_cycles)` 端到端量,
與 (J)/(G-4''''') 同一 fixture。

AC(客觀、可量測):
  SC1 present + backward-compat : 每檔位 `squash__{tier}` 皆產出、finite、有 bone、≥1 bone **同時**帶
                                 shear+scale;**base squash 恆 4 段不變**(shear 段數與 scale 極值數皆 4、
                                 逐位元同無檔位);且**不帶** `tier_squash_cycles`(=None)時 squash 變體逐位元
                                 同 (G-4''''') 耦合幅度-only 輸出(加性 opt-in 零回歸)。
  SC2 crux — count↑ × 守恆       : 各檔位 squash 的 shear 段數(繞 0 交替極值個數)**與** scale 內部極值個數
                                 皆 == 宣告 [4,5,6,7] 且 Super<Mega<Omg<Legend **嚴格遞增**、Super==base;
                                 **且每檔位每個 scale 內部極值 |scaleX·scaleY−1|≤TOL_VOL** —— 段數增多、
                                 耦合幅度放大之後,**每個(含新長出的)極值仍體積守恆**(段數×幅度×守恆三效正交)。
  SC3 signature preserved       : **每檔位** squash 仍(a)首尾 shearX==0;(b)繞 0 變號≥3;(c)shear 相繼極值
                                 幅度嚴格遞減(阻尼);(d)scale 內部 squash 幅度 (scaleX−1) 嚴格遞減(阻尼擠壓)。
                                 **且**峰 |shearX| / 峰非均勻 / 峰拉長 仍隨檔位嚴格遞增(段數軸不抵消幅度軸)。
  SC4 orthogonality             : (a) 段數 + **平增益**(全 g=1.0)→ 段數仍遞增、峰幅(shear/非均勻/拉長)**不**遞增;
                                 (b) 耦合增益 + **無段數**(tsc=None)→ 段數恆 4、峰幅遞增(兩軸可獨立開關)。
  SC5 neg-control               : (a) **平段數**(全 4)→ 段數單調性 FALSE(證閘測遞增非恆真);
                                 (b) 無宣告的 genre(slot_reveal)→ `squash_cycles_for` 回 None → 不亂加段數變體;
                                 (c) 段數**只作用 squash**:非-squash 主秀 beat 的段數在各檔位恆定(不外洩)。

用法:
  python3 validate_squash_count.py            # 摘要
  python3 validate_squash_count.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
# 復用 G-4' 的 shear 讀取與阻尼簽章判準(與 shear-gen / wobble-tier / squash-gen / squash-tier 閘一致)
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
# 復用 G-4'''' 的 scale 讀取 / 內部極值判準
from validate_squash_gen import _scale_xy, _interior_scale

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
DEAD = 1e-6
TOL_VOL = 2e-4     # 體積守恆 |scaleX·scaleY−1| 上限(同 squash-tier 閘;耦合 4 位捨入 ≤1e-4)


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/squash_count_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _squash_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "squash"]


def _main_beats(anims):
    return {nm: G.beat_category(nm) for nm in anims
            if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


def _shear_segs(anim):
    """該 anim 的 squash 擠壓段數 = 任一 shear bone 的**繞 0 交替極值個數**(= 非零 shearX 內部關鍵幀數)。

    `_squash_env` 產包絡 [0, e1, …, e_nosc, 0] 每內部極值交替變號 → 非零內部關鍵幀數即段數;
    各 bone 同形(僅 role 峰值 / side 反相不同)→ 取任一有 shear 的 bone。"""
    for ch in anim.get("bones", {}).values():
        sx = _shear_x(ch)
        if sx:
            return len([v for v in sx if abs(v) > DEAD])
    return 0


def _scale_segs(anim):
    """該 anim 的 squash scale 內部極值個數(= 擠壓段數;首尾 (1,1) 端點不計)。取任一有 scale 的 bone。"""
    for ch in anim.get("bones", {}).values():
        inter = _interior_scale(ch)
        if inter:
            return len(inter)
    return 0


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _aniso_peak(anim):
    vals = []
    for ch in anim.get("bones", {}).values():
        xy = _scale_xy(ch)
        if xy:
            vals.append(max(abs(sx - sy) for (sx, sy) in xy))
    return max(vals, default=0.0)


def _stretch_peak(anim):
    vals = []
    for ch in anim.get("bones", {}).values():
        xy = _scale_xy(ch)
        if xy:
            vals.append(max(sx for (sx, sy) in xy) - 1.0)
    return max(vals, default=0.0)


def _is_strict_inc(xs):
    return len(xs) >= 2 and all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def _is_strict_dec(xs):
    return len(xs) >= 2 and all(xs[i + 1] < xs[i] - 1e-9 for i in range(len(xs) - 1))


def _dual_bone(anim):
    return any(_shear_x(ch) and _scale_xy(ch) for ch in anim.get("bones", {}).values())


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    cyc = TV.squash_cycles_for(GENRE)

    base = G.build_animations(skel, sb)                                               # 無檔位
    amp_only = G.build_animations(skel, sb, tier_gains=gains)                         # (G-4''''') 耦合幅度-only
    full = G.build_animations(skel, sb, tier_gains=gains, tier_squash_cycles=cyc)     # (G-4'''''-c) 幅度+段數

    squash_beats = _squash_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- SC1 present + backward-compat ----
    s1 = {"squash_beats": squash_beats, "missing": [], "not_finite": [], "no_bones": [],
          "variant_no_dual": [], "base_changed": [], "amp_only_regressed": []}
    for qb in squash_beats:
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = full.get(vk)
            if an is None:
                s1["missing"].append(vk); continue
            if not SA.all_finite(an):
                s1["not_finite"].append(vk)
            if not an.get("bones"):
                s1["no_bones"].append(vk)
            if not _dual_bone(an):
                s1["variant_no_dual"].append(vk)
        # base squash 恆 4 段(shear 與 scale)且逐位元同無檔位
        if (_shear_segs(full[qb]) != 4 or _scale_segs(full[qb]) != 4
                or json.dumps(base[qb], sort_keys=True) != json.dumps(full[qb], sort_keys=True)):
            s1["base_changed"].append(qb)
    # tier_squash_cycles=None 時,squash 變體逐位元同 (G-4''''') 耦合幅度-only(加性 opt-in)
    none_run = G.build_animations(skel, sb, tier_gains=gains, tier_squash_cycles=None)
    for qb in squash_beats:
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            if json.dumps(none_run.get(vk), sort_keys=True) != json.dumps(amp_only.get(vk), sort_keys=True):
                s1["amp_only_regressed"].append(vk)
    s1_pass = bool(squash_beats) and not any(s1[k] for k in
              ["missing", "not_finite", "no_bones", "variant_no_dual", "base_changed", "amp_only_regressed"])
    R["SC1_present_backward_compat"] = {**s1, "pass": s1_pass}

    # ---- SC2 crux: count↑ (shear segs AND scale extrema) × per-extremum volume conservation ----
    s2 = {"beats": {}, "fail_shear_count": [], "fail_scale_count": [], "bad_volume": []}
    expected = [cyc[t] for t in TIERS]
    for qb in squash_beats:
        shear_counts = [_shear_segs(full["{}__{}".format(qb, t)]) for t in TIERS]
        scale_counts = [_scale_segs(full["{}__{}".format(qb, t)]) for t in TIERS]
        base_shear = _shear_segs(base[qb])
        base_scale = _scale_segs(base[qb])
        # 每檔位每 bone 每 scale 內部極值 volume ok
        vol_ok = True
        for t in TIERS:
            an = full["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior:
                    continue
                if not all(abs(sx * sy - 1.0) <= TOL_VOL for (sx, sy) in interior):
                    vol_ok = False
                    s2["bad_volume"].append("{}__{}::{}".format(qb, t, bn))
        shear_ok = (shear_counts == expected and _is_strict_inc(shear_counts) and shear_counts[0] == base_shear)
        scale_ok = (scale_counts == expected and _is_strict_inc(scale_counts) and scale_counts[0] == base_scale)
        s2["beats"][qb] = {"shear_counts": shear_counts, "scale_counts": scale_counts,
                           "expected": expected, "base_shear": base_shear, "base_scale": base_scale,
                           "shear_ok": shear_ok, "scale_ok": scale_ok, "volume_ok": vol_ok}
        if not shear_ok:
            s2["fail_shear_count"].append(qb)
        if not scale_ok:
            s2["fail_scale_count"].append(qb)
    s2_pass = (bool(s2["beats"]) and not s2["fail_shear_count"]
               and not s2["fail_scale_count"] and not s2["bad_volume"])
    R["SC2_count_monotone_volume"] = {"tiers": TIERS, **s2, "pass": s2_pass}

    # ---- SC3 signature preserved per tier + amplitude still monotone ----
    s3 = {"bad_endpoints": [], "few_sign_changes": [], "shear_not_damped": [], "squash_not_damped": [],
          "shear_amp_not_mono": [], "aniso_not_mono": [], "stretch_not_mono": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = full["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                inter = _interior_scale(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                ends_ok = abs(sx[0]) < DEAD and abs(sx[-1]) < DEAD
                nsc = _sign_changes_zero(sx)
                shear_damp = _extrema_mags_decreasing(sx)
                # scale 阻尼:內部極值的 (scaleX−1) 幅度嚴格遞減(擠壓愈來愈淺)
                mag = [abs(a - 1.0) for (a, b) in inter]
                sq_damp = len(mag) >= 2 and all(mag[i + 1] < mag[i] - 1e-9 for i in range(len(mag) - 1))
                s3["detail"][key] = {"n_sign_changes": nsc, "shear_damped": shear_damp, "squash_damped": sq_damp}
                if not ends_ok:
                    s3["bad_endpoints"].append(key)
                if nsc < 3:
                    s3["few_sign_changes"].append(key)
                if not shear_damp:
                    s3["shear_not_damped"].append(key)
                if not sq_damp:
                    s3["squash_not_damped"].append(key)
        # 峰幅仍隨檔位嚴格遞增(段數軸不抵消幅度軸)
        shear_peaks = [_shear_peak(full["{}__{}".format(qb, t)]) for t in TIERS]
        aniso_peaks = [_aniso_peak(full["{}__{}".format(qb, t)]) for t in TIERS]
        stretch_peaks = [_stretch_peak(full["{}__{}".format(qb, t)]) for t in TIERS]
        if not _is_strict_inc(shear_peaks):
            s3["shear_amp_not_mono"].append((qb, [round(p, 3) for p in shear_peaks]))
        if not _is_strict_inc(aniso_peaks):
            s3["aniso_not_mono"].append((qb, [round(p, 4) for p in aniso_peaks]))
        if not _is_strict_inc(stretch_peaks):
            s3["stretch_not_mono"].append((qb, [round(p, 4) for p in stretch_peaks]))
    s3_pass = (bool(s3["detail"]) and not any(s3[k] for k in
               ["bad_endpoints", "few_sign_changes", "shear_not_damped", "squash_not_damped",
                "shear_amp_not_mono", "aniso_not_mono", "stretch_not_mono"]))
    R["SC3_signature_preserved"] = {**s3, "pass": s3_pass}

    # ---- SC4 orthogonality ----
    # (a) 段數 + 平增益 → 段數仍遞增、峰幅不遞增(結構獨立於幅度)
    flat_gain = {t: 1.0 for t in TIERS}
    ca = G.build_animations(skel, sb, tier_gains=flat_gain, tier_squash_cycles=cyc)
    counts_fg = {qb: [_shear_segs(ca["{}__{}".format(qb, t)]) for t in TIERS] for qb in squash_beats}
    shpk_fg = {qb: [round(_shear_peak(ca["{}__{}".format(qb, t)]), 3) for t in TIERS] for qb in squash_beats}
    anpk_fg = {qb: [round(_aniso_peak(ca["{}__{}".format(qb, t)]), 4) for t in TIERS] for qb in squash_beats}
    a_ok = (bool(squash_beats) and all(_is_strict_inc(v) for v in counts_fg.values())
            and all(not _is_strict_inc(v) for v in shpk_fg.values())
            and all(not _is_strict_inc(v) for v in anpk_fg.values()))
    # (b) 耦合增益 + 無段數 → 段數恆 4、峰幅遞增
    counts_go = {qb: [_shear_segs(amp_only["{}__{}".format(qb, t)]) for t in TIERS] for qb in squash_beats}
    shpk_go = {qb: [round(_shear_peak(amp_only["{}__{}".format(qb, t)]), 3) for t in TIERS] for qb in squash_beats}
    anpk_go = {qb: [round(_aniso_peak(amp_only["{}__{}".format(qb, t)]), 4) for t in TIERS] for qb in squash_beats}
    b_ok = (bool(squash_beats) and all(v == [4, 4, 4, 4] for v in counts_go.values())
            and all(_is_strict_inc(v) for v in shpk_go.values())
            and all(_is_strict_inc(v) for v in anpk_go.values()))
    R["SC4_orthogonality"] = {
        "a_counts_with_flat_gain": counts_fg, "a_shearpeaks_flat_gain": shpk_fg,
        "a_anisopeaks_flat_gain": anpk_fg, "a_pass": a_ok,
        "b_gain_only_counts_fixed4": counts_go, "b_gain_only_shearpeaks": shpk_go,
        "b_gain_only_anisopeaks": anpk_go, "b_pass": b_ok,
        "pass": a_ok and b_ok}

    # ---- SC5 negative controls ----
    s5 = {}
    # (a) 平段數(全 4)→ 段數單調性 FALSE
    flat_cyc = {t: 4 for t in TIERS}
    fc = G.build_animations(skel, sb, tier_gains=gains, tier_squash_cycles=flat_cyc)
    any_mono_flat = any(_is_strict_inc([_shear_segs(fc["{}__{}".format(qb, t)]) for t in TIERS])
                        for qb in squash_beats)
    s5["a_flat_cycles_guard"] = {"any_count_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) 無宣告段數的 genre(slot_reveal)→ squash_cycles_for None → 不產段數變體
    rv_cyc = TV.squash_cycles_for("slot_reveal")
    rv_sb = _storyboard("slot_reveal")
    rv_gains = TV.gains_for("slot_reveal")
    rv_full = G.build_animations(skel, rv_sb, tier_gains=rv_gains, tier_squash_cycles=rv_cyc)
    rv_squash_variants = [k for k in rv_full if "__" in k and G.beat_category(k) == "squash"]
    s5["b_no_cycle_genre"] = {"squash_cycles_for_slot_reveal": rv_cyc,
                              "squash_variants": rv_squash_variants,
                              "pass": rv_cyc is None and not rv_squash_variants}
    # (c) 段數只作用於 squash:非-squash 主秀 beat 的段數在各檔位恆定(不外洩)
    leak = []
    for beat, cat in main_beats.items():
        if cat == "squash":
            continue
        counts = [_shear_segs(full["{}__{}".format(beat, t)]) for t in TIERS]
        if len(set(counts)) != 1:      # 段數外洩 → 各檔位不同
            leak.append((beat, cat, counts))
    s5["c_cycles_isolated_to_squash"] = {"leaked": leak, "pass": not leak}
    R["SC5_neg_control"] = {**s5, "pass": all(v["pass"] for v in s5.values())}

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
        for k in ["SC1_present_backward_compat", "SC2_count_monotone_volume",
                  "SC3_signature_preserved", "SC4_orthogonality", "SC5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("SC2 counts per tier {}:".format(TIERS))
        for qb, d in R["SC2_count_monotone_volume"]["beats"].items():
            print("  {:10s} shear_segs {} scale_extrema {} (base {}/{}) vol_ok={}".format(
                qb, d["shear_counts"], d["scale_counts"], d["base_shear"], d["base_scale"], d["volume_ok"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
