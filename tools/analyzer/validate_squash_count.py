#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash 擠壓**段數**隨檔位遞增(count-aware,純 CPU)。

(G-4'''') 讓 `gen_squash` 成為第一個同時產 shear + 耦合非均勻 scale(體積守恆擠壓)的生成器,但
squash **不接檔位差異化**:squash 的**幅度**軸需放大 Q → `_amp_scale` 只放大 identity 上方會破壞
體積守恆(scaleX·scaleY≠1),故 squash 未進 MAIN_SHOW_CATS(honest boundary,見 STATE)。

本次 (G-4''''') 補上 squash 的**段數**軸檔位差異化 —— 擠壓段數 nosc **隨檔位嚴格遞增**(Super 4 →
Mega 5 → Omg 6 → Legend 7),**繞過**幅度耦合難題:段數是關鍵幀**拓樸**,以該檔位 nosc 用
`gen_squash(nosc=k)` **重生成**整個 beat。**關鍵(crux,與幅度軸對照)**:重生成的包絡對**任意** nosc
天然體積守恆(scaleX·scaleY≡1、squash 幅度 q_i=Q·rⁱ 逐極值嚴格遞減)→ 段數增多**不破**守恆;而幅度軸
(放大 Q)才會破壞守恆。故 squash 走**純結構軸**:段數隨檔位遞增,而**振幅(峰 |shearX|、峰非均勻)
跨檔位恆定**(誠實:幅度耦合 amplify 仍為 boundary,不假裝已解)。squash∈COUNT_ONLY_CATS →
build_animations 產 `squash__{tier}` 只重生成段數、**不**套幅度增益 g。此模式接續 (J-2) combo 峰數、
(G-4''') wobble 振盪段數 —— **count-aware 概念第三次落在新通道**(combo=scale 峰數、wobble=shear 振盪段數、
squash=體積守恆擠壓段數),各類別段數階梯獨立(build_animations 依 cat 路由)。

真值界定同 (E/H/I/J/J-2/G-4'/G-4''/G-4'''/G-4''''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀
結構簽章非美感**;「愈高檔位擠愈多段」是可量化檔位簽章,用負對照證鑑別力(閘可信)。從**先驗庫** →
**真實 build_spine robot 骨架** → `build_animations(..., tier_gains, tier_squash_cycles)` 端到端量,
與 (J)/(G-4'''') 同一 fixture。復用 squash-gen 閘的 shear/scale 判準,確保與 G-4'''' 完全一致。

AC(客觀、可量測):
  Q1 present + backward-compat : 帶 tier_squash_cycles 時,每檔位 `squash__{tier}` 皆產出、finite、有 bone、
                                **同時**帶 shear 與 scale 通道(雙通道);**base squash 恆 4 段且逐位元同無檔位**;
                                且**不帶** tier_squash_cycles(=None)時 squash **不產任何檔位變體**
                                (加性 opt-in、向後相容同 G-4'''' 前),且加此參數不改動任何非-squash beat。
  Q2 crux — count monotone     : 各檔位 squash 的擠壓**段數**(繞 0 交替 shear 極值個數)== 宣告 [4,5,6,7] 且
                                Super<Mega<Omg<Legend **嚴格遞增**;Super 段數 == base 段數(向後相容)。
  Q3 signature preserved       : **每檔位** squash 仍 (a)shear 首尾 0、繞 0 變號 ≥3、相繼極值嚴格遞減(阻尼);
                                **且 (b) 體積守恆耦合逐檔位保持(crux)**:每檔位每 bone 的每個 squash 極值
                                scaleX·scaleY≈1(|積−1|≤TOL_VOL)、非均勻峰 ≥ MIN_ANISO、squash 幅度嚴格遞減
                                —— **段數增多不破體積守恆**(對照:幅度軸放大 Q 會破守恆,故 squash 只走段數軸)。
  Q4 amplitude-flat (honest)   : **crux honesty** — squash 的**振幅**(峰 |shearX|、峰非均勻 |scaleX−scaleY|)
                                **跨檔位恆定**(各檔位相等、非遞增)→ 證此為**純段數(結構)軸**,幅度耦合
                                差異化仍為 boundary(不假裝已解)。對照 wobble(G-4''')段數**與**幅度**雙軸**遞增,
                                squash 只段數軸遞增、幅度平 —— 誠實界定範圍。並驗正交:段數 + 平增益(全 g=1.0)
                                → 段數仍遞增(結構獨立於幅度、squash 本就不吃 g)。
  Q5 neg-control               : (a) **平段數**(全 4)→ 段數單調性 FALSE(證閘測遞增非恆真);
                                (b) 無宣告的 genre(slot_reveal)→ `squash_cycles_for` 回 None → 不產 squash 變體;
                                (c) 段數**只作用 squash**:非-squash beat 的段數/峰在各檔位恆定(不外洩);
                                (d) **體積守恆守衛**:合成「非守恆」擠壓(兩軸皆拉長,積≠1)經 Q3 判準 → 守恆 FALSE
                                (證 Q3 真的在量守恆、非「有 scale 即可」)。

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
# 復用 G-4'/G-4'''' 的 shear/scale 讀取與判準,確保與 shear-gen / squash-gen 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import (_scale_xy, _interior_scale, _sq3_eval, _has_aniso_scale,
                                 TOL_VOL, MIN_ANISO)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
DEAD = 1e-6


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
    """非-squash 的主秀 beat(cat∈MAIN_SHOW_CATS)——用於 Q5(c) 段數不外洩驗證。"""
    return {nm: G.beat_category(nm) for nm in anims
            if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


def _nosc(anim):
    """該 anim 的 squash 擠壓段數 = 任一 shear bone 的**繞 0 交替極值個數**(=非零 shearX 關鍵幀數)。

    包絡 [0, e1, …, e_nosc, 0] 每內部極值交替變號 → 非零內部關鍵幀數即段數(同 wobble 判準)。"""
    for ch in anim.get("bones", {}).values():
        sx = _shear_x(ch)
        if sx:
            return len([v for v in sx if abs(v) > DEAD])
    return 0


def _shear_peak(anim):
    """該 anim 全 bone 的峰 |shearX|(無 shear 回 0)。"""
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _aniso_peak(anim):
    """該 anim 全 bone 的峰非均勻 |scaleX−scaleY|(無 scale 回 0)。"""
    peaks = [max(abs(sx - sy) for (sx, sy) in _scale_xy(ch))
             for ch in anim.get("bones", {}).values() if _scale_xy(ch)]
    return max(peaks, default=0.0)


def _is_strict_inc(xs):
    return len(xs) >= 2 and all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def _all_equal(xs, tol=1e-6):
    return len(xs) >= 2 and all(abs(x - xs[0]) <= tol for x in xs)


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    cyc = TV.squash_cycles_for(GENRE)

    base = G.build_animations(skel, sb)                                              # 無檔位
    gain_only = G.build_animations(skel, sb, tier_gains=gains)                       # 幅度-only(squash 不產變體)
    full = G.build_animations(skel, sb, tier_gains=gains, tier_squash_cycles=cyc)    # (G-4''''') 段數

    squash_beats = _squash_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- Q1 present + backward-compat ----
    q1 = {"squash_beats": squash_beats, "missing": [], "not_finite": [], "no_bones": [],
          "variant_not_dual": [], "base_changed": [], "no_tsc_has_variant": [], "nonsquash_regressed": []}
    for qb in squash_beats:
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = full.get(vk)
            if an is None:
                q1["missing"].append(vk); continue
            if not SA.all_finite(an):
                q1["not_finite"].append(vk)
            if not an.get("bones"):
                q1["no_bones"].append(vk)
            # 雙通道:≥1 bone 同時帶 shear 與 scale(squash 定義簽章)
            if not any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values()):
                q1["variant_not_dual"].append(vk)
        # base squash 恆 4 段且逐位元同無檔位
        if _nosc(full[qb]) != 4 or json.dumps(base[qb], sort_keys=True) != json.dumps(full[qb], sort_keys=True):
            q1["base_changed"].append(qb)
        # tier_squash_cycles=None 時 squash **不產任何檔位變體**(向後相容:同 G-4'''' 前)
        for t in TIERS:
            if "{}__{}".format(qb, t) in gain_only:
                q1["no_tsc_has_variant"].append("{}__{}".format(qb, t))
    # 加 tier_squash_cycles 不改動任何**非-squash** beat(零回歸;對照 gain_only 除 squash 變體外全同)
    for nm, an in gain_only.items():
        if G.beat_category(nm.split("__")[0]) == "squash":
            continue
        if json.dumps(full.get(nm), sort_keys=True) != json.dumps(an, sort_keys=True):
            q1["nonsquash_regressed"].append(nm)
    q1_pass = bool(squash_beats) and not any(q1[k] for k in
              ["missing", "not_finite", "no_bones", "variant_not_dual", "base_changed",
               "no_tsc_has_variant", "nonsquash_regressed"])
    R["Q1_present_backward_compat"] = {**q1, "pass": q1_pass}

    # ---- Q2 crux: squash-segment count monotone ----
    q2 = {"beats": {}, "fail": []}
    expected = [cyc[t] for t in TIERS]
    for qb in squash_beats:
        counts = [_nosc(full["{}__{}".format(qb, t)]) for t in TIERS]
        base_count = _nosc(base[qb])
        mono = _is_strict_inc(counts)
        matches = (counts == expected)
        super_eq_base = (counts[0] == base_count)
        q2["beats"][qb] = {"counts": counts, "expected": expected, "base_count": base_count,
                           "monotone": mono, "matches_declared": matches, "super_eq_base": super_eq_base}
        if not (mono and matches and super_eq_base):
            q2["fail"].append(qb)
    q2_pass = bool(squash_beats) and not q2["fail"]
    R["Q2_count_monotone"] = {"tiers": TIERS, **q2, "pass": q2_pass}

    # ---- Q3 signature preserved per tier: damped shear + volume-conserving coupling (crux) ----
    q3 = {"bad_endpoints": [], "few_sign_changes": [], "shear_not_damped": [],
          "bad_volume": [], "no_aniso": [], "squash_not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = full["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                # (a) shear 阻尼振盪簽章
                if not (abs(sx[0]) < DEAD and abs(sx[-1]) < DEAD):
                    q3["bad_endpoints"].append(key)
                if _sign_changes_zero(sx) < 3:
                    q3["few_sign_changes"].append(key)
                if not _extrema_mags_decreasing(sx):
                    q3["shear_not_damped"].append(key)
                # (b) 體積守恆耦合(crux):重生成的每檔位仍守恆
                interior = _interior_scale(ch)
                vok, aok, dok, det = _sq3_eval(interior)
                q3["detail"][key] = det
                if not vok:
                    q3["bad_volume"].append(key)
                if not aok:
                    q3["no_aniso"].append(key)
                if not dok:
                    q3["squash_not_damped"].append(key)
    q3_pass = (bool(q3["detail"]) and not any(q3[k] for k in
               ["bad_endpoints", "few_sign_changes", "shear_not_damped",
                "bad_volume", "no_aniso", "squash_not_damped"]))
    R["Q3_signature_preserved"] = {**q3, "pass": q3_pass}

    # ---- Q4 amplitude-flat (honest boundary) + orthogonality ----
    q4 = {"shear_peaks": {}, "aniso_peaks": {}, "shear_not_flat": [], "aniso_not_flat": [],
          "counts_flat_gain": {}, "count_not_mono_flatgain": []}
    for qb in squash_beats:
        sh = [round(_shear_peak(full["{}__{}".format(qb, t)]), 4) for t in TIERS]
        an = [round(_aniso_peak(full["{}__{}".format(qb, t)]), 4) for t in TIERS]
        q4["shear_peaks"][qb] = sh
        q4["aniso_peaks"][qb] = an
        # crux honesty:振幅跨檔位恆定(非遞增)—— 純段數軸,幅度耦合仍 boundary
        if not _all_equal(sh):
            q4["shear_not_flat"].append((qb, sh))
        if not _all_equal(an):
            q4["aniso_not_flat"].append((qb, an))
    # 正交:段數 + 平增益(全 g=1.0)→ 段數仍遞增(squash 本就不吃 g,故與 full 相同,額外守衛不同 gain 不影響段數)
    flat_gain = {t: 1.0 for t in TIERS}
    ca = G.build_animations(skel, sb, tier_gains=flat_gain, tier_squash_cycles=cyc)
    for qb in squash_beats:
        counts = [_nosc(ca["{}__{}".format(qb, t)]) for t in TIERS]
        q4["counts_flat_gain"][qb] = counts
        if not _is_strict_inc(counts):
            q4["count_not_mono_flatgain"].append(qb)
    q4_pass = (bool(squash_beats) and not q4["shear_not_flat"] and not q4["aniso_not_flat"]
               and not q4["count_not_mono_flatgain"])
    R["Q4_amplitude_flat"] = {**q4, "pass": q4_pass}

    # ---- Q5 negative controls ----
    q5 = {}
    # (a) 平段數(全 4)→ 段數單調性 FALSE
    flat_cyc = {t: 4 for t in TIERS}
    fc = G.build_animations(skel, sb, tier_gains=gains, tier_squash_cycles=flat_cyc)
    any_mono_flat = any(_is_strict_inc([_nosc(fc["{}__{}".format(qb, t)]) for t in TIERS]) for qb in squash_beats)
    q5["a_flat_cycles_guard"] = {"any_count_monotone": any_mono_flat, "pass": not any_mono_flat}
    # (b) 無宣告段數的 genre → squash_cycles_for None → 不產 squash 變體
    rv_cyc = TV.squash_cycles_for("slot_reveal")
    rv_sb = _storyboard("slot_reveal")
    rv_gains = TV.gains_for("slot_reveal")
    rv_full = G.build_animations(skel, rv_sb, tier_gains=rv_gains, tier_squash_cycles=rv_cyc)
    rv_squash_variants = [k for k in rv_full if "__" in k and G.beat_category(k) == "squash"]
    q5["b_no_cycle_genre"] = {"squash_cycles_for_slot_reveal": rv_cyc,
                              "squash_variants": rv_squash_variants,
                              "pass": rv_cyc is None and not rv_squash_variants}
    # (c) 段數只作用於 squash:非-squash 主秀 beat 的段數/shear 峰在各檔位恆定(不外洩)
    leak = []
    for beat, cat in main_beats.items():
        if cat == "squash":
            continue
        counts = [_nosc(full["{}__{}".format(beat, t)]) for t in TIERS]
        if len(set(counts)) != 1:      # 段數外洩 → 各檔位不同
            leak.append((beat, cat, counts))
    q5["c_cycles_isolated_to_squash"] = {"leaked": leak, "pass": not leak}
    # (d) 體積守恆守衛:合成非守恆擠壓(兩軸皆拉長,積≠1)→ Q3 volume 判準 FALSE(證閘量守恆非「有 scale 即可」)
    nonvol = [(1.14, 1.07), (1.07, 1.035), (1.035, 1.0175)]   # prod≠1、皆拉長
    v_nv, a_nv, d_nv, _ = _sq3_eval(nonvol)
    q5["d_nonvolume_guard"] = {"volume_ok": v_nv, "aniso_ok": a_nv, "pass": (not v_nv) and a_nv}
    q5_pass = all(v["pass"] for v in q5.values())
    R["Q5_neg_control"] = {**q5, "pass": q5_pass}

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
        for k in ["Q1_present_backward_compat", "Q2_count_monotone",
                  "Q3_signature_preserved", "Q4_amplitude_flat", "Q5_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("Q2 squash-segment counts per tier {}:".format(TIERS))
        for qb, d in R["Q2_count_monotone"]["beats"].items():
            print("  {:10s} {}  (base {})".format(qb, d["counts"], d["base_count"]))
        print("Q4 amplitude flat across tiers (honest boundary):")
        for qb in R["Q4_amplitude_flat"]["shear_peaks"]:
            print("  {:10s} shear {}  aniso {}".format(
                qb, R["Q4_amplitude_flat"]["shear_peaks"][qb], R["Q4_amplitude_flat"]["aniso_peaks"][qb]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
