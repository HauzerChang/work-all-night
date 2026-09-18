#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

補上 (G-4'''') 一路留到現在的 honest boundary:squash(斜拉果凍**擠壓**)是第一個同時產出
**shear + 耦合體積守恆非均勻 scale**(scaleX·scaleY≡1、scaleX≠scaleY)的生成器,但當時**未接檔位差異化**
—— 因為 (J) 的 scale 幅度增益 `_amp_scale` 只放大 identity 上方 overshoot、下方樓地板不動,對 squash 會把
scaleX(>1)放大卻讓 scaleY(<1)不動 → **破壞體積守恆**(scaleX·scaleY≠1),故 squash 一直不在
`MAIN_SHOW_CATS`。本次(G-4''''')替 squash 的 scale 通道改走**耦合 amplify**(`_amp_scale_coupled`,對數
應變空間同比放大:scaleX'=scaleX^g、scaleY'=scaleY^g → (scaleX·scaleY)^g≡1 **仍守恆**、非均勻
|scaleX'−scaleY'| 隨 g **單調遞增**),並把 squash 併入 `MAIN_SHOW_CATS` → squash 的**擠壓強度隨檔位遞增**
而**體積守恆與阻尼耦合簽章在每個檔位保持**。shear 通道沿用 (G-4'') 的 v'=g*v(shear 峰亦隨檔位遞增)。

真值界定同 (J/G-4''/G-4'''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位擠壓愈強**且**仍體積守恆」是可量化的檔位簽章,用負對照證鑑別力(閘可信)。從**先驗庫** →
**真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  ST1 present + backward-compat  : squash base beat 有 shear+scale;每檔位 `squash__{tier}` 皆產出、finite、
                                  有 bone、≥1 bone **同時**帶 shear 與 scale 通道、名經 `beat_category` 仍
                                  路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains 的 base + In/Loop/Out 相同)。
  ST2 crux — 體積守恆跨檔位保持  : **每個檔位**的 squash bone,其**每個** scale 極值幀 |scaleX·scaleY−1|≤TOL_VOL
                                  (耦合 amplify 的關鍵 —— 普通 `_amp_scale` 會破壞,見 ST5b 守衛)。
  ST3 crux — 擠壓強度隨檔位遞增  : 各檔位峰 |scaleX−scaleY|(非均勻擠壓量)Super<Mega<Omg<Legend **嚴格遞增**,
                                  且峰 |shearX| 亦嚴格遞增(端到端經 build_animations 量);首檔(Super,g=1)
                                  兩峰 == base 峰(向後相容)。
  ST4 interface + 阻尼簽章保形   : **每個檔位**——(a)shear 首尾 0、scale 首尾 (1,1)、sample(0)/sample(dur) identity;
                                  (b)shear 阻尼振盪(繞 0 變號 ≥3 + 相繼極值遞減);(c)squash 幅度 |scaleX−1| 隨
                                  極值嚴格遞減(耦合阻尼保形)。
  ST5 neg-control               : (a)**平增益守衛**:增益全 1.0 → ST3 兩峰遞增 FALSE(證閘測遞增非恆真);
                                  (b)**耦合必要性守衛(crux)**:對真實 base squash 極值,用舊 `_amp_scale`(樓地板)
                                     以 Legend g 放大 → 體積守恆 FALSE(max|prod−1|>TOL_VOL);用 `_amp_scale_coupled`
                                     → 體積守恆 TRUE 且非均勻更大 —— 直接證「耦合 amplify 是修正、普通 amplify 會壞」;
                                  (c)**耦合 scale 隔離**:耦合 amplify 只作用 squash —— squash__Legend 的 min scaleY
                                     **低於** base squash min scaleY(樓地板被同比壓低);而非-squash 帶 scale 的主秀
                                     beat(如 hit/combo)其 <1 樓地板(anticipation dip)各檔位**恆定**(仍走 `_amp_scale`);
                                  (d)**加性**:移除 squash 的 storyboard → 其餘 beat(含檔位變體)逐位元不變(零回歸)。

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
# 復用 G-4' 的 shear 讀取與阻尼簽章判準、G-4'''' 的 squash 極值/體積守恆判準 → 與各 shear/squash 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import _scale_xy, _interior_scale, _sq3_eval, TOL_VOL, MIN_ANISO, MIN_SHEAR

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


def _squash_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "squash"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _aniso_peak(anim):
    """該 anim 全 bone 的峰 |scaleX−scaleY|(非均勻擠壓量;無 scale 回 0)。"""
    peaks = [max((abs(sx - sy) for (sx, sy) in _scale_xy(ch)), default=0.0)
             for ch in anim.get("bones", {}).values()]
    return max(peaks, default=0.0)


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _min_scaleY(anim):
    """該 anim 全 bone 的最小 scaleY(squash 的壓扁樓地板 / hit-combo 的 anticipation dip)。"""
    ys = [sy for ch in anim.get("bones", {}).values() for (sx, sy) in _scale_xy(ch)]
    return min(ys, default=1.0)


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

    # ---- ST1 present + backward-compat + dual-channel ----
    t1 = {"squash_beats": squash_beats, "base_weak": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": []}
    for qb in squash_beats:
        # base 確有 shear + 非均勻 scale
        if _shear_peak(base[qb]) < MIN_SHEAR or _aniso_peak(base[qb]) < MIN_ANISO:
            t1["base_weak"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            if not an.get("bones"):
                t1["no_bones"].append(vk)
            dual = any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values())
            if not dual:
                t1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                t1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    t1_pass = (bool(squash_beats) and not any(t1[k] for k in
               ["base_weak", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed"]))
    R["ST1_present_backward_compat"] = {**t1, "pass": t1_pass}

    # ---- ST2 crux: volume conservation preserved across tiers ----
    t2 = {"bad_volume": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior or not _shear_x(ch):
                    continue
                prod = [sx * sy for (sx, sy) in interior]
                worst = max(abs(p - 1.0) for p in prod)
                key = "{}__{}::{}".format(qb, t, bn)
                t2["detail"][key] = {"worst_vol_err": round(worst, 6),
                                     "prod": [round(p, 5) for p in prod]}
                if worst > TOL_VOL:
                    t2["bad_volume"].append(key)
    t2_pass = bool(t2["detail"]) and not t2["bad_volume"]
    R["ST2_volume_preserved_per_tier"] = {**t2, "pass": t2_pass}

    # ---- ST3 crux: squash + shear strength monotone across tiers ----
    t3 = {"beats": {}, "fail_aniso_mono": [], "fail_shear_mono": [], "fail_base": []}
    for qb in squash_beats:
        aniso = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        shear = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_aniso, base_shear = _aniso_peak(base[qb]), _shear_peak(base[qb])
        aniso_mono = _is_strict_inc(aniso)
        shear_mono = _is_strict_inc(shear)
        super_eq = abs(aniso[0] - base_aniso) <= 1e-3 and abs(shear[0] - base_shear) <= 1e-3
        t3["beats"][qb] = {"aniso_peaks": [round(x, 4) for x in aniso],
                           "shear_peaks": [round(x, 3) for x in shear],
                           "base_aniso": round(base_aniso, 4), "base_shear": round(base_shear, 3),
                           "aniso_mono": aniso_mono, "shear_mono": shear_mono, "super_eq_base": super_eq}
        if not aniso_mono:
            t3["fail_aniso_mono"].append(qb)
        if not shear_mono:
            t3["fail_shear_mono"].append(qb)
        if not super_eq:
            t3["fail_base"].append(qb)
    t3_pass = (bool(t3["beats"]) and not t3["fail_aniso_mono"]
               and not t3["fail_shear_mono"] and not t3["fail_base"])
    R["ST3_strength_monotone"] = {**t3, "pass": t3_pass}

    # ---- ST4 interface + damped signature preserved per tier ----
    t4 = {"bad_interface": [], "shear_ends_nonzero": [], "scale_ends_nonident": [],
          "few_sign_changes": [], "shear_not_damped": [], "squash_not_damped": []}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                t4["bad_interface"].append("{}__{}".format(qb, t))
            for bn, ch in an.get("bones", {}).items():
                key = "{}__{}::{}".format(qb, t, bn)
                sx = _shear_x(ch)
                if sx:
                    if abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6:
                        t4["shear_ends_nonzero"].append(key)
                    if _sign_changes_zero(sx) < 3:
                        t4["few_sign_changes"].append(key)
                    if not _extrema_mags_decreasing(sx):
                        t4["shear_not_damped"].append(key)
                xy = _scale_xy(ch)
                if xy and (abs(xy[0][0] - 1.0) > 1e-6 or abs(xy[0][1] - 1.0) > 1e-6
                           or abs(xy[-1][0] - 1.0) > 1e-6 or abs(xy[-1][1] - 1.0) > 1e-6):
                    t4["scale_ends_nonident"].append(key)
                interior = _interior_scale(ch)
                if interior and sx:
                    _, _, dok, _ = _sq3_eval(interior)   # damped_ok = |scaleX−1| 隨極值嚴格遞減
                    if not dok:
                        t4["squash_not_damped"].append(key)
    t4_pass = not any(t4[k] for k in t4)
    R["ST4_interface_damped"] = {**t4, "pass": t4_pass}

    # ---- ST5 negative controls ----
    t5 = {}
    # (a) 平增益守衛:全 1.0 → aniso/shear 遞增皆 FALSE
    flat = {t: 1.0 for t in TIERS}
    fa = G.build_animations(skel, sb, tier_gains=flat)
    any_aniso_mono = any(_is_strict_inc([_aniso_peak(fa["{}__{}".format(qb, t)]) for t in TIERS])
                         for qb in squash_beats)
    any_shear_mono = any(_is_strict_inc([_shear_peak(fa["{}__{}".format(qb, t)]) for t in TIERS])
                         for qb in squash_beats)
    t5["a_flat_gain_guard"] = {"flat_aniso_monotone": any_aniso_mono, "flat_shear_monotone": any_shear_mono,
                               "pass": (not any_aniso_mono) and (not any_shear_mono)}
    # (b) 耦合必要性守衛(crux):對真實 base squash 極值,舊 _amp_scale 破壞體積、耦合 amplify 守恆
    g_leg = gains["Legend"]
    qb0 = squash_beats[0]
    bch = next((ch for ch in base[qb0]["bones"].values()
                if _interior_scale(ch) and _shear_x(ch)), None)
    interior = _interior_scale(bch)
    floor_amp = [(round(TV._amp_scale(sx, g_leg), 4), round(TV._amp_scale(sy, g_leg), 4))
                 for (sx, sy) in interior]
    coup_amp = [(round(TV._amp_scale_coupled(sx, g_leg), 4), round(TV._amp_scale_coupled(sy, g_leg), 4))
                for (sx, sy) in interior]
    floor_v = max(abs(sx * sy - 1.0) for (sx, sy) in floor_amp)
    coup_v = max(abs(sx * sy - 1.0) for (sx, sy) in coup_amp)
    coup_aniso = max(abs(sx - sy) for (sx, sy) in coup_amp)
    base_aniso = max(abs(sx - sy) for (sx, sy) in interior)
    t5["b_coupled_necessity_guard"] = {
        "floor_amp_vol_err": round(floor_v, 5), "coupled_amp_vol_err": round(coup_v, 6),
        "coupled_aniso": round(coup_aniso, 4), "base_aniso": round(base_aniso, 4),
        "pass": (floor_v > TOL_VOL) and (coup_v <= TOL_VOL) and (coup_aniso > base_aniso)}
    # (c) 耦合 scale 隔離:squash 樓地板被同比壓低;非-squash scale 節拍樓地板各檔位恆定
    sq_floor_pushed = True
    for qb in squash_beats:
        base_min = _min_scaleY(base[qb])
        leg_min = _min_scaleY(anims["{}__Legend".format(qb)])
        if not (leg_min < base_min - 1e-4):     # 耦合 → scaleY 樓地板被同比壓低
            sq_floor_pushed = False
    # 非-squash 帶 scale 的主秀 beat(如 hit/combo):<1 樓地板各檔位恆定(仍走 _amp_scale)
    other_floor_const = True
    other_checked = []
    for nm, cat in {nm: G.beat_category(nm) for nm in base}.items():
        if "__" in nm or cat not in TV.MAIN_SHOW_CATS or cat == "squash":
            continue
        if _min_scaleY(base[nm]) >= 1.0 - 1e-6:   # 無 <1 樓地板 → 跳過(如純 shear wobble)
            continue
        floors = [round(_min_scaleY(anims["{}__{}".format(nm, t)]), 4) for t in TIERS]
        other_checked.append((nm, cat, floors))
        if len(set(floors)) != 1:
            other_floor_const = False
    t5["c_coupled_isolated"] = {"squash_floor_pushed": sq_floor_pushed,
                                "other_floor_const": other_floor_const, "other_checked": other_checked,
                                "pass": sq_floor_pushed and other_floor_const}
    # (d) 加性:移除 squash 的 storyboard → 其餘 beat(含檔位變體)逐位元不變
    sb_no = {**sb, "beats": [b for b in sb["beats"] if G.beat_category(b["beat"]) != "squash"]}
    anims_no = G.build_animations(skel, sb_no, tier_gains=gains)
    regressed = [nm for nm in anims_no
                 if json.dumps(anims_no[nm], sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True)]
    t5["d_additive_no_regression"] = {"regressed": regressed,
                                      "removed": [b["beat"] for b in sb["beats"]
                                                  if G.beat_category(b["beat"]) == "squash"],
                                      "pass": not regressed}
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
        for k in ["ST1_present_backward_compat", "ST2_volume_preserved_per_tier",
                  "ST3_strength_monotone", "ST4_interface_damped", "ST5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("ST3 peaks per tier {}:".format(TIERS))
        for qb, d in R["ST3_strength_monotone"]["beats"].items():
            print("  {:8s} aniso {}  shear {}  (base aniso {} shear {})".format(
                qb, d["aniso_peaks"], d["shear_peaks"], d["base_aniso"], d["base_shear"]))
        b = R["ST5_neg_control"]["b_coupled_necessity_guard"]
        print("ST5b coupled-necessity: floor_amp vol_err {} (breaks) vs coupled {} (holds); "
              "coupled aniso {} > base {}".format(b["floor_amp_vol_err"], b["coupled_amp_vol_err"],
                                                  b["coupled_aniso"], b["base_aniso"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
