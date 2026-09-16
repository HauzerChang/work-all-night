#!/usr/bin/env python3
"""candidate G-4''''' 自我驗收閘 — squash(shear + 耦合體積守恆非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

candidate (J) 讓主秀 beat 依檔位**幅度**差異化,(G-4'') 把 wobble 的 shear 峰接上檔位;但 (G-4'''')
新生成的 squash(斜拉果凍擠壓)的幅度軸在**耦合的 shear + 體積守恆非均勻 scale**(scaleX·scaleY==1)——
未被檔位放大,且**不能**用 per-channel `_amp_scale`:它只放大 identity 上方 scaleX(>1)、保留下方
scaleY(<1)樓地板 → 積 (1+gq)/(1+q)≠1 **破壞體積守恆**(這正是 G-4'''' 留下的 honest boundary,
「squash 未接 tier 幅度,需耦合 amplify」)。本次(G-4''''')讓 squash 走 `COUPLED_SCALE_CATS` 耦合
amplify(對拉長量 q=scaleX−1 施 q'=g·q,再令 scaleX'=1+q'、scaleY'=1/(1+q')),shear 同步 g·v 放大
→ squash 的擠壓/斜拉強度隨檔位嚴格遞增,而**每個檔位仍體積守恆**(scaleX·scaleY==1)。

真值界定同 (E/H/I/J/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位擠壓愈強」是可量化的檔位簽章,用負對照證鑑別力(閘可信)。從**先驗庫** → **真實
build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  V1 present + backward-compat  : squash base beat ≥1 bone **同時**帶 shear+scale;每檔位 `squash__{tier}`
                                 皆產出、finite、有 bone、≥1 bone dual-channel、名經 `beat_category` 仍
                                 路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains);Super(g=1)==base squash。
  V2 crux — coupled amp monotone: 各檔位 squash 的 (a)拉長峰 |scaleX−1|、(b)shear 峰 |shearX|、
                                 (c)非均勻峰 |scaleX−scaleY| 皆 Super<Mega<Omg<Legend **嚴格遞增**
                                 (端到端經 build_animations 量),且 Super 峰 == base 峰(向後相容)。
  V3 crux — volume preserved    : **每個檔位**的 squash **每個**極值幀仍 (a)scaleX·scaleY≈1(TOL_VOL,
                                 面積守恆 —— 耦合 amplify 的重點:放大後守恆不破);(b)非均勻(aniso 峰≥MIN_ANISO);
                                 (c)|scaleX−1| 隨極值嚴格遞減(阻尼)。且 shear 阻尼振盪簽章每檔位保形。
  V4 identity 介面 per tier     : 每檔位變體 shear 首尾 0 + scale 首尾 (1,1) → 可插 Loop 間。
  V5 neg-control                : (a) **平增益守衛**:增益全 1.0 → V2 遞增 FALSE 且各檔位 == base squash;
                                 (b) **耦合 vs naive 守衛(crux,證閘/機制可信)**:對真實 squash 極值幀,
                                    naive per-channel `_amp_scale`(g=2)→ scaleX·scaleY≠1(破壞守恆)、
                                    耦合 `_amp_squash_scale`(g=2)→ scaleX·scaleY==1 且更非均勻 →
                                    證「耦合 amplify 有作用且必要」(naive 會破壞 honest-boundary 不變量);
                                 (c) **耦合隔離**:全 storyboard(含所有檔位變體)中,只有 squash 及其
                                    `__tier` 變體「同時帶 shear 且非均勻 scale」→ 非 squash 主秀變體零外洩。

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
# 復用 G-4'''' squash-gen 閘的讀取/判準,確保與 squash-gen 完全一致(閘間判準統一)
from validate_squash_gen import (_shear_x, _sign_changes_zero, _extrema_mags_decreasing,
                                 _scale_xy, _interior_scale, _sq3_eval, _has_aniso_scale,
                                 MIN_SHEAR, MIN_ANISO)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/squash_tier_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _squash_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "squash"]


def _dual_bones(an):
    """該 anim 中同時帶 shear+scale 的 bone channels(dict bn→ch)。"""
    return {bn: ch for bn, ch in an.get("bones", {}).items() if _shear_x(ch) and _scale_xy(ch)}


def _stretch_peak(an):
    """全 bone 的峰 |scaleX−1|(squash 拉長量;無 scale 回 0)。"""
    peaks = [max(abs(sx - 1.0) for (sx, sy) in _scale_xy(ch)) for ch in an.get("bones", {}).values()
             if _scale_xy(ch)]
    return max(peaks, default=0.0)


def _shear_peak(an):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in an.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _aniso_peak(an):
    peaks = [max(abs(sx - sy) for (sx, sy) in _scale_xy(ch)) for ch in an.get("bones", {}).values()
             if _scale_xy(ch)]
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

    # ---- V1 present + backward-compat + dual-channel ----
    v1 = {"squash_beats": squash_beats, "base_no_dual": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": [], "super_ne_base": []}
    for qb in squash_beats:
        if not _dual_bones(base[qb]):
            v1["base_no_dual"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                v1["missing"].append(vk); continue
            if not SA.all_finite(an):
                v1["not_finite"].append(vk)
            if not an.get("bones"):
                v1["no_bones"].append(vk)
            if not _dual_bones(an):
                v1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                v1["misrouted"].append((vk, G.beat_category(vk)))
        # Super(g=1)逐位元 == base squash(向後相容)
        if json.dumps(anims.get("{}__Super".format(qb)), sort_keys=True) != \
           json.dumps(base[qb], sort_keys=True):
            v1["super_ne_base"].append(qb)
    # base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            v1["base_changed"].append(k)
    v1_pass = (bool(squash_beats) and not any(v1[k] for k in
               ["base_no_dual", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed", "super_ne_base"]))
    R["V1_present_backward_compat"] = {**v1, "pass": v1_pass}

    # ---- V2 crux: coupled amplitude monotone (stretch / shear / aniso) ----
    v2 = {"beats": {}, "fail_mono": [], "fail_base": []}
    for qb in squash_beats:
        stretch = [_stretch_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        shear = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        aniso = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        b_stretch, b_shear, b_aniso = _stretch_peak(base[qb]), _shear_peak(base[qb]), _aniso_peak(base[qb])
        mono = _is_strict_inc(stretch) and _is_strict_inc(shear) and _is_strict_inc(aniso)
        base_eq = (abs(stretch[0] - b_stretch) <= 1e-4 and abs(shear[0] - b_shear) <= 1e-4
                   and abs(aniso[0] - b_aniso) <= 1e-4)
        v2["beats"][qb] = {"stretch_peaks": [round(x, 4) for x in stretch],
                           "shear_peaks": [round(x, 3) for x in shear],
                           "aniso_peaks": [round(x, 4) for x in aniso],
                           "base": [round(b_stretch, 4), round(b_shear, 3), round(b_aniso, 4)],
                           "mono": mono, "super_eq_base": base_eq}
        if not mono:
            v2["fail_mono"].append(qb)
        if not base_eq:
            v2["fail_base"].append(qb)
    v2_pass = bool(v2["beats"]) and not v2["fail_mono"] and not v2["fail_base"]
    R["V2_coupled_amp_monotone"] = {**v2, "pass": v2_pass}

    # ---- V3 crux: volume conservation preserved after amplify (per tier) ----
    v3 = {"bad_volume": [], "no_aniso": [], "not_damped": [],
          "shear_bad_endpoints": [], "shear_few_sc": [], "shear_not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                sx = _shear_x(ch)
                if not interior or not sx:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                vok, aok, dok, det = _sq3_eval(interior)
                v3["detail"][key] = det
                if not vok:
                    v3["bad_volume"].append(key)
                if not aok:
                    v3["no_aniso"].append(key)
                if not dok:
                    v3["not_damped"].append(key)
                # shear 阻尼振盪簽章每檔位保形
                if not (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6):
                    v3["shear_bad_endpoints"].append(key)
                if _sign_changes_zero(sx) < 3:
                    v3["shear_few_sc"].append(key)
                if not _extrema_mags_decreasing(sx):
                    v3["shear_not_damped"].append(key)
    v3_pass = (bool(v3["detail"]) and not v3["bad_volume"] and not v3["no_aniso"]
               and not v3["not_damped"] and not v3["shear_bad_endpoints"]
               and not v3["shear_few_sc"] and not v3["shear_not_damped"])
    R["V3_volume_preserved_per_tier"] = {**v3, "pass": v3_pass}

    # ---- V4 identity interface per tier ----
    v4 = {"bad_interface": [], "shear_endpoints_nonzero": [], "scale_endpoints_nonident": []}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                v4["bad_interface"].append("{}__{}".format(qb, t))
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                    v4["shear_endpoints_nonzero"].append("{}__{}::{}".format(qb, t, bn))
                xy = _scale_xy(ch)
                if xy and (abs(xy[0][0] - 1.0) > 1e-6 or abs(xy[0][1] - 1.0) > 1e-6
                           or abs(xy[-1][0] - 1.0) > 1e-6 or abs(xy[-1][1] - 1.0) > 1e-6):
                    v4["scale_endpoints_nonident"].append("{}__{}::{}".format(qb, t, bn))
    R["V4_identity_interface"] = {**v4, "pass": (not v4["bad_interface"]
                                                and not v4["shear_endpoints_nonzero"]
                                                and not v4["scale_endpoints_nonident"])}

    # ---- V5 negative controls ----
    v5 = {}
    # (a) 平增益守衛:全 1.0 → V2 遞增 FALSE 且各檔位 == base squash
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for qb in squash_beats:
        stretch = [_stretch_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(stretch):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    v5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) 耦合 vs naive 守衛(crux):對真實 squash 首極值幀施 g=2 兩法,量體積守恆
    g = 2.0
    # 取真實 squash base 的一個 dual bone 首極值幀 (scaleX,scaleY)
    sample_xy = None
    for qb in squash_beats:
        for bn, ch in base[qb].get("bones", {}).items():
            interior = _interior_scale(ch)
            if interior and _shear_x(ch):
                sample_xy = interior[0]; break
        if sample_xy:
            break
    naive_prod = coupled_prod = naive_aniso = coupled_aniso = None
    if sample_xy:
        sx0, sy0 = sample_xy
        # naive:對兩軸各自 _amp_scale(scaleX>1 放大、scaleY<1 樓地板不動)
        nx = round(TV._amp_scale(sx0, g), 4); ny = round(TV._amp_scale(sy0, g), 4)
        naive_prod = round(nx * ny, 5); naive_aniso = round(abs(nx - ny), 4)
        # coupled:_amp_squash_scale(守恆)
        cx, cy = TV._amp_squash_scale(sx0, sy0, g)
        coupled_prod = round(cx * cy, 5); coupled_aniso = round(abs(cx - cy), 4)
    naive_breaks = sample_xy is not None and abs(naive_prod - 1.0) > 0.02   # naive 破壞守恆
    coupled_keeps = sample_xy is not None and abs(coupled_prod - 1.0) <= 0.02  # 耦合維持守恆
    coupled_more_aniso = sample_xy is not None and coupled_aniso > abs(sample_xy[0] - sample_xy[1]) + 1e-9
    v5["b_coupled_vs_naive"] = {"sample_xy": [round(sample_xy[0], 4), round(sample_xy[1], 4)] if sample_xy else None,
                                "naive_prod": naive_prod, "naive_aniso": naive_aniso,
                                "coupled_prod": coupled_prod, "coupled_aniso": coupled_aniso,
                                "naive_breaks_volume": naive_breaks, "coupled_keeps_volume": coupled_keeps,
                                "coupled_more_aniso": coupled_more_aniso,
                                "pass": naive_breaks and coupled_keeps and coupled_more_aniso}
    # (c) 耦合隔離:含所有檔位變體,只有 squash 及其變體「同時帶 shear 且非均勻 scale」
    leak = []
    for nm, an in anims.items():
        if G.beat_category(nm.split("__")[0]) == "squash":
            continue
        for bn, ch in an.get("bones", {}).items():
            if _shear_x(ch) and _has_aniso_scale(ch):
                leak.append((nm, bn))
    v5["c_coupling_isolated"] = {"leaked": leak, "pass": not leak}
    R["V5_neg_control"] = {**v5, "pass": all(v["pass"] for v in v5.values())}

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
        for k in ["V1_present_backward_compat", "V2_coupled_amp_monotone",
                  "V3_volume_preserved_per_tier", "V4_identity_interface", "V5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V2 per-tier peaks {}:".format(TIERS))
        for qb, d in R["V2_coupled_amp_monotone"]["beats"].items():
            print("  {:8s} stretch {} shear {} aniso {}".format(
                qb, d["stretch_peaks"], d["shear_peaks"], d["aniso_peaks"]))
        b = R["V5_neg_control"]["b_coupled_vs_naive"]
        print("V5b coupled-vs-naive: sample {} -> naive prod {} (aniso {}) | coupled prod {} (aniso {})".format(
            b["sample_xy"], b["naive_prod"], b["naive_aniso"], b["coupled_prod"], b["coupled_aniso"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
