#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合體積守恆非均勻 scale)接檔位幅度差異化(純 CPU)。

candidate (J) 讓主秀 beat 依檔位**幅度**差異化,(G-4'') 把 wobble(純 shear)接上,(G-4'''') 讓
`gen_squash` 產出**耦合的 shear + 體積守恆非均勻 scale**,但當時 squash **不在** `MAIN_SHOW_CATS` ——
因為天真 `_amp_scale` 只放大 identity 上方 overshoot(scaleX>1)、squash 樓地板(scaleY<1)不動 →
**破壞體積守恆**(scaleX·scaleY≠1)。這是 (G-4'''') 明列的 honest boundary。

本次(G-4''''')引入**耦合 amplify**(`tier_variants._amp_scale_coupled`:視 scale 為 scaleX·scaleY≡1
的擠壓對,以 q=scaleX−1 為擠壓量放大 q→g·q → scaleX'=1+g·q、scaleY'=1/(1+g·q))⇒ 放大後仍
**scaleX'·scaleY'≡1**;shear 通道續用 (G-4'') 的 `v'=g*v` 對稱放大。squash 遂併入 `MAIN_SHOW_CATS`
且以 `COUPLED_SCALE_CATS` 標記走耦合路徑 → **squash 的 shear 峰與擠壓幅度雙軸隨檔位嚴格遞增,而每個
檔位仍體積守恆**(強度變、體積守恆結構不變 —— 誠實地:檔位=更斜更擠,非別種運動、非漏氣脹縮)。

真值界定同 (E/H/I/J/G-4'/G-4''/G-4''''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章
(阻尼振盪 + 體積守恆耦合 + 雙軸幅度遞增)非美感**;負對照證鑑別力(閘可信)。從**先驗庫** → **真實
build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  ST1 present + backward-compat  : squash base beat 有 dual channel(shear + 非均勻 scale);每檔位
                                  `squash__{tier}` 皆產出、finite、有 bone、≥1 bone **同時**帶 shear
                                  與 scale、名經 `beat_category` 仍路由回 squash;**base 逐位元不變**
                                  (帶/不帶 tier_gains 的 base + In/Loop/Out 相同);**Super(g=1)逐位元 == base**。
  ST2 crux — dual amp monotone  : 端到端經 build_animations 量,各檔位 squash 的 (a)峰 |shearX| 與
                                  (b)峰擠壓非均勻 |scaleX−scaleY| **皆** Super<Mega<Omg<Legend 嚴格遞增,
                                  且首檔(Super,g=1)兩者皆 == base(向後相容)。**兩軸同時遞增才算檔位差異化**。
  ST3 crux — volume-preserving  : **每個檔位**的 squash 仍滿足 (G-4'''') 的耦合簽章(復用 `_sq3_eval`):
      per tier                    每個內部擠壓極值 (a)scaleX·scaleY≈1(|積−1|≤TOL_VOL,體積守恆);
                                  (b)≥1 極值 |scaleX−scaleY|≥MIN_ANISO(真擠壓=非均勻);(c)squash 幅度
                                  |scaleX−1| 隨極值嚴格遞減(阻尼)。且 shear 亦仍阻尼振盪(首尾 0、變號≥3、遞減)。
                                  → 耦合 amplify **放大幅度但不破壞體積守恆**(關鍵鑑別點,對比 ST5b 天真放大)。
  ST4 coupling isolated         : 全 storyboard(含所有檔位變體)中,只有 squash 及其 `__tier` 變體同時帶
                                  shear 與非均勻 scale(以 `SHEAR_CATS` 認定合法 shear 產出者);非-squash
                                  主秀 beat 及其變體皆非「同時 shear+非均勻 scale」→ 耦合對象仍只鎖 squash。
  ST5 neg-control               : (a)**平增益守衛**:增益階梯全 1.0 → ST2 雙軸遞增 FALSE 且各檔位逐位元 == base;
                                  (b)**耦合 vs 天真單元測(閘可信)**:對一個體積守恆對 (scaleX,scaleY),
                                  `amplify_bone_tl(coupled=True)` → 積仍≈1 且 q 放大;`amplify_bone_tl(coupled=False)`
                                  (天真獨立 `_amp_scale`)→ 積顯著偏離 1(破壞守恆)。**證耦合路徑是體積守恆的
                                  必要條件、且閘測的是「守恆放大」非「有 scale 即可」**。

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
# 復用 G-4' 的阻尼簽章判準 + G-4'''' 的體積守恆耦合判準,確保跨閘完全一致。
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import _scale_xy, _interior_scale, _sq3_eval, _has_aniso_scale, \
    MIN_SHEAR, MIN_ANISO, TOL_VOL

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
    """該 anim 全 bone 的峰擠壓非均勻 |scaleX−scaleY|(無 scale 回 0)。"""
    peaks = []
    for ch in anim.get("bones", {}).values():
        xy = _scale_xy(ch)
        if xy:
            peaks.append(max(abs(sx - sy) for (sx, sy) in xy))
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
    t1 = {"squash_beats": squash_beats, "base_no_dual": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": [], "super_ne_base": []}
    for qb in squash_beats:
        # base 須有 ≥1 bone 同時帶 shear + scale(dual channel)
        if not any(_shear_x(ch) and _scale_xy(ch) for ch in base[qb].get("bones", {}).values()):
            t1["base_no_dual"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            if not an.get("bones"):
                t1["no_bones"].append(vk)
            if not any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values()):
                t1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                t1["misrouted"].append((vk, G.beat_category(vk)))
        # Super(g=1)逐位元 == base squash
        if json.dumps(anims.get("{}__Super".format(qb)), sort_keys=True) != \
           json.dumps(base[qb], sort_keys=True):
            t1["super_ne_base"].append(qb)
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    t1_pass = (bool(squash_beats) and not any(t1[k] for k in
               ["base_no_dual", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed", "super_ne_base"]))
    R["ST1_present_backward_compat"] = {**t1, "pass": t1_pass}

    # ---- ST2 crux: dual-axis amplitude monotone across tiers ----
    t2 = {"beats": {}, "fail_shear_mono": [], "fail_aniso_mono": [], "fail_base": []}
    for qb in squash_beats:
        sh_peaks = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        an_peaks = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_sh, base_an = _shear_peak(base[qb]), _aniso_peak(base[qb])
        sh_mono, an_mono = _is_strict_inc(sh_peaks), _is_strict_inc(an_peaks)
        base_ok = abs(sh_peaks[0] - base_sh) <= 1e-4 and abs(an_peaks[0] - base_an) <= 1e-4
        t2["beats"][qb] = {"shear_peaks": [round(p, 3) for p in sh_peaks],
                           "aniso_peaks": [round(p, 4) for p in an_peaks],
                           "base_shear": round(base_sh, 3), "base_aniso": round(base_an, 4),
                           "shear_mono": sh_mono, "aniso_mono": an_mono, "super_eq_base": base_ok}
        if not sh_mono:
            t2["fail_shear_mono"].append(qb)
        if not an_mono:
            t2["fail_aniso_mono"].append(qb)
        if not base_ok:
            t2["fail_base"].append(qb)
    t2_pass = (bool(t2["beats"]) and not t2["fail_shear_mono"]
               and not t2["fail_aniso_mono"] and not t2["fail_base"])
    R["ST2_dual_amplitude_monotone"] = {**t2, "pass": t2_pass}

    # ---- ST3 crux: volume-preserving coupling + damped shear preserved per tier ----
    t3 = {"bad_volume": [], "no_aniso": [], "scale_not_damped": [], "shear_bad": [], "detail": {}}
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
                # shear 阻尼振盪(首尾 0、繞 0 變號≥3、相繼極值遞減)
                sh_ok = (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                         and _sign_changes_zero(sx) >= 3 and _extrema_mags_decreasing(sx))
                t3["detail"][key] = {**det, "shear_ok": sh_ok}
                if not vok:
                    t3["bad_volume"].append(key)
                if not aok:
                    t3["no_aniso"].append(key)
                if not dok:
                    t3["scale_not_damped"].append(key)
                if not sh_ok:
                    t3["shear_bad"].append(key)
    t3_pass = (bool(t3["detail"]) and not t3["bad_volume"] and not t3["no_aniso"]
               and not t3["scale_not_damped"] and not t3["shear_bad"])
    R["ST3_volume_preserving_per_tier"] = {**t3, "pass": t3_pass}

    # ---- ST4 coupling isolated to squash (incl. all tier variants) ----
    t4 = {"leaked": []}
    for nm, an in anims.items():
        base_name = nm.split("__")[0]
        if G.beat_category(base_name) == "squash":
            continue
        for bn, ch in an.get("bones", {}).items():
            if _shear_x(ch) and _has_aniso_scale(ch):
                t4["leaked"].append((nm, bn))
    R["ST4_coupling_isolated"] = {**t4, "pass": not t4["leaked"]}

    # ---- ST5 negative controls ----
    t5 = {}
    # (a) 平增益守衛:全 1.0 → 雙軸遞增 FALSE 且各檔位 == base
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
    t5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) 耦合 vs 天真單元測:同一體積守恆對,coupled 保積、naive 破積
    g = 2.0
    sx0, sy0 = 1.14, round(1.0 / 1.14, 4)   # 一個 gen_squash 式體積守恆擠壓對
    vol_pair = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0},
                          {"time": 0.5, "x": sx0, "y": sy0},
                          {"time": 1.0, "x": 1.0, "y": 1.0}]}
    a_cp = TV.amplify_bone_tl(vol_pair, g, coupled=True)
    a_nv = TV.amplify_bone_tl(vol_pair, g, coupled=False)
    cp_x, cp_y = a_cp["scale"][1]["x"], a_cp["scale"][1]["y"]
    nv_x, nv_y = a_nv["scale"][1]["x"], a_nv["scale"][1]["y"]
    cp_vol = abs(cp_x * cp_y - 1.0)
    nv_vol = abs(nv_x * nv_y - 1.0)
    cp_amplified = abs(cp_x - (1.0 + g * (sx0 - 1.0))) <= 1e-4    # q 放大到 g·q
    t5["b_coupled_vs_naive"] = {
        "coupled": {"x": cp_x, "y": cp_y, "vol_resid": round(cp_vol, 6)},
        "naive": {"x": nv_x, "y": nv_y, "vol_resid": round(nv_vol, 6)},
        # coupled:積守恆(≤TOL_VOL 通過守恆閘)且 q 放大;naive:積 > TOL_VOL(**破守恆閘**)
        # 且 ≥100× coupled 殘差 → 證耦合路徑是體積守恆的必要條件(閘可信)。
        "pass": (cp_vol <= TOL_VOL) and cp_amplified
                and (nv_vol > TOL_VOL) and (nv_vol >= 100 * cp_vol)}
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
        for k in ["ST1_present_backward_compat", "ST2_dual_amplitude_monotone",
                  "ST3_volume_preserving_per_tier", "ST4_coupling_isolated", "ST5_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("ST2 dual-axis peaks per tier {}:".format(TIERS))
        for qb, d in R["ST2_dual_amplitude_monotone"]["beats"].items():
            print("  {:8s} shear {}  aniso {}  (base sh {} an {})".format(
                qb, d["shear_peaks"], d["aniso_peaks"], d["base_shear"], d["base_aniso"]))
        b = R["ST5_neg_control"]["b_coupled_vs_naive"]
        print("ST5b coupled vol_resid {} | naive vol_resid {} (broken)".format(
            b["coupled"]["vol_resid"], b["naive"]["vol_resid"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
