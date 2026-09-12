#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

一路的 honest boundary:candidate (J) 讓主秀 beat 依檔位**幅度**差異化(愈高檔位愈爆),(G-4'')把
**wobble** 的 shear 峰接上檔位;但 (G-4'''') 新生成的 **squash**(斜拉果凍擠壓)有 shear **且**體積守恆
非均勻 scale(scaleX·scaleY==1),當時**刻意不在** `MAIN_SHOW_CATS`:普通 `_amp_scale`(只放大 identity
上方、下方壓縮軸樓地板不動)會把 scaleX>1 放大、scaleY<1 保留 → **破壞體積守恆**(scaleX·scaleY≠1)。
本次(G-4''''')補上 squash 的檔位差異化,用**耦合 amplify**(`_amp_scale_coupled`:放大拉長軸以
`1+g(v−1)`、壓縮軸取其倒數)→ 讓 squash 的**擠壓強度(非均勻)與 shear 峰同時隨檔位遞增**,而
**體積守恆在所有檔位精確保持**(這正是普通 amplify 做不到、需要耦合的關鍵)。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位擠壓愈大、但仍守恆」是可量化的檔位簽章,用負對照證鑑別力(閘可信)。從**先驗庫** →
**真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  QT1 present + backward-compat  : squash base beat 同時帶 shear+scale;每檔位 `squash__{tier}` 皆產出、
                                  finite、有 bone、≥1 bone **同時**帶 shear 與 scale 通道、名經
                                  `beat_category` 仍路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains
                                  的 base squash + In/Loop/Out 相同);**無 tier_gains → 不產任何 `squash__`**。
  QT2 crux — 擠壓非均勻 monotone : 各檔位 squash 的峰非均勻 max|scaleX−scaleY| Super<Mega<Omg<Legend
                                  **嚴格遞增**(端到端經 build_animations 量),且首檔(Super,g=1)== base(向後相容)。
  QT3 crux — 體積守恆逐檔保持    : **每個檔位**的 squash bone 的每個內部極值幀:(a)scaleX·scaleY≈1
                                  (|積−1|≤TOL_VOL,守恆對所有檔位不破 —— 耦合 amplify 的關鍵);
                                  (b)至少一極值非均勻 |scaleX−scaleY|≥MIN_ANISO;(c)squash 幅度
                                  |scaleX−1| 隨極值嚴格遞減(阻尼耦合保形)。復用 `_sq3_eval`,與 G-4'''' 閘一致。
  QT4 shear 峰 monotone + 阻尼   : 各檔位 squash 的峰 |shearX| 亦 Super<Mega<Omg<Legend **嚴格遞增**
                                  (shear 與 scale 兩通道**一起**隨檔位放大),且**每個檔位**仍首尾 shearX==0
                                  + 繞 0 變號 ≥3 + 相繼極值嚴格遞減(阻尼簽章逐檔保形)。
  QT5 neg-control               : (a) **平增益守衛**:增益階梯全 1.0 → QT2 遞增 FALSE 且各檔位逐位元==base;
                                  (b) **naive-amplify 守衛(crux)**:對同一 squash 幀施普通 `_amp_scale`(非耦合)
                                  → 高檔位 |scaleX·scaleY−1| > TOL_VOL(體積守恆**破壞**)→ 證 QT3 非恆真、
                                  耦合 amplify 為**必要**(閘可信、非空過);
                                  (c) **耦合路由隔離**:build 的 `squash__{tier}` == `_amplify_anim(base, g,
                                  coupled_scale=True)`(且在 g>1 時 != coupled_scale=False);而非-squash 主秀
                                  scale beat 的 `__{tier}` == `_amplify_anim(base, g, coupled_scale=False)`
                                  (普通 amplify、壓縮軸樓地板不動)→ 證耦合只路由給 squash、不外洩到 (J)/(J-2) 節拍。

用法:
  python3 validate_squash_tier.py            # 摘要
  python3 validate_squash_tier.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import gen_animations as G
import tier_variants as TV
# 復用 G-4'''' 的 squash 讀取/判準與 G-4' 的阻尼簽章判準,確保與 squash-gen / shear-gen 閘完全一致
from validate_squash_gen import (
    _skeleton, _storyboard, _squash_beats, _scale_xy, _interior_scale, _sq3_eval,
    GENRE, MIN_SHEAR, MIN_ANISO, TOL_VOL,
)
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing

TIERS = ["Super", "Mega", "Omg", "Legend"]


def _peak_aniso(an):
    """anim → 峰非均勻 max|scaleX−scaleY|(無 scale 回 0)。"""
    vals = [abs(sx - sy) for ch in an.get("bones", {}).values() for (sx, sy) in _scale_xy(ch)]
    return max(vals) if vals else 0.0


def _peak_shear(an):
    """anim → 峰 |shearX|(無 shear 回 0)。"""
    vals = [abs(v) for ch in an.get("bones", {}).values() for v in _shear_x(ch)]
    return max(vals) if vals else 0.0


def _strictly_increasing(seq):
    return len(seq) >= 2 and all(seq[i + 1] > seq[i] + 1e-9 for i in range(len(seq) - 1))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    tg = TV.gains_for(GENRE)
    anims = G.build_animations(skel, sb, tier_gains=tg)
    anims_base = G.build_animations(skel, sb)           # 無 tier_gains(向後相容基準)
    squash_beats = _squash_beats(anims)
    R = {}

    # ---- QT1 present + backward-compat ----
    q1 = {"squash_beats": squash_beats, "missing_variant": [], "not_finite": [], "no_dual": [],
          "misrouted": [], "base_regressed": [], "leaked_without_gains": []}
    # 無 tier_gains → 不得有任何 squash__ 變體
    q1["leaked_without_gains"] = [nm for nm in anims_base if "__" in nm]
    for qb in squash_beats:
        # base squash 同時帶 shear+scale
        base = anims[qb]
        if not any(_shear_x(ch) and _scale_xy(ch) for ch in base.get("bones", {}).values()):
            q1["no_dual"].append(qb)
        for tier in TIERS:
            vn = "{}__{}".format(qb, tier)
            if vn not in anims:
                q1["missing_variant"].append(vn); continue
            an = anims[vn]
            import spine_anim as SA
            if not SA.all_finite(an):
                q1["not_finite"].append(vn)
            if not any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values()):
                q1["no_dual"].append(vn)
            if G.beat_category(vn) != "squash":
                q1["misrouted"].append(vn)
    # base(非 __)beat 帶/不帶 tier_gains 逐位元相同(零回歸)
    for nm, an in anims_base.items():
        if json.dumps(an, sort_keys=True) != json.dumps(anims.get(nm), sort_keys=True):
            q1["base_regressed"].append(nm)
    q1_pass = (bool(squash_beats) and not q1["missing_variant"] and not q1["not_finite"]
               and not q1["no_dual"] and not q1["misrouted"] and not q1["base_regressed"]
               and not q1["leaked_without_gains"])
    R["QT1_present_backward_compat"] = {**q1, "pass": q1_pass}

    # ---- QT2 crux — squash non-uniformity peak strictly increasing per tier ----
    q2 = {"aniso_by_tier": {}, "not_increasing": [], "super_ne_base": []}
    for qb in squash_beats:
        seq = [round(_peak_aniso(anims["{}__{}".format(qb, t)]), 6)
               if "{}__{}".format(qb, t) in anims else None for t in TIERS]
        q2["aniso_by_tier"][qb] = seq
        if None in seq or not _strictly_increasing(seq):
            q2["not_increasing"].append(qb)
        base_pk = round(_peak_aniso(anims[qb]), 6)
        if seq[0] is None or abs(seq[0] - base_pk) > 1e-6:
            q2["super_ne_base"].append(qb)
    q2_pass = (bool(q2["aniso_by_tier"]) and not q2["not_increasing"] and not q2["super_ne_base"])
    R["QT2_aniso_peak_monotone"] = {**q2, "pass": q2_pass}

    # ---- QT3 crux — volume conservation preserved at every tier (reuse _sq3_eval) ----
    q3 = {"bad_volume": [], "no_aniso": [], "not_damped": [], "detail": {}}
    for qb in squash_beats:
        for tier in TIERS:
            vn = "{}__{}".format(qb, tier)
            if vn not in anims:
                continue
            for bn, ch in anims[vn].get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior or not _shear_x(ch):
                    continue
                key = "{}::{}".format(vn, bn)
                vok, aok, dok, det = _sq3_eval(interior)
                q3["detail"][key] = det
                if not vok:
                    q3["bad_volume"].append(key)
                if not aok:
                    q3["no_aniso"].append(key)
                if not dok:
                    q3["not_damped"].append(key)
    q3_pass = (bool(q3["detail"]) and not q3["bad_volume"] and not q3["no_aniso"]
               and not q3["not_damped"])
    R["QT3_volume_preserved_per_tier"] = {**q3, "pass": q3_pass}

    # ---- QT4 shear peak monotone + damped signature per tier ----
    q4 = {"shear_by_tier": {}, "not_increasing": [], "super_ne_base": [],
          "bad_endpoints": [], "few_sign_changes": [], "not_damped": []}
    for qb in squash_beats:
        seq = [round(_peak_shear(anims["{}__{}".format(qb, t)]), 4)
               if "{}__{}".format(qb, t) in anims else None for t in TIERS]
        q4["shear_by_tier"][qb] = seq
        if None in seq or not _strictly_increasing(seq):
            q4["not_increasing"].append(qb)
        base_pk = round(_peak_shear(anims[qb]), 4)
        if seq[0] is None or abs(seq[0] - base_pk) > 1e-4:
            q4["super_ne_base"].append(qb)
        for tier in TIERS:
            vn = "{}__{}".format(qb, tier)
            if vn not in anims:
                continue
            for bn, ch in anims[vn].get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                key = "{}::{}".format(vn, bn)
                if not (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6):
                    q4["bad_endpoints"].append(key)
                if _sign_changes_zero(sx) < 3:
                    q4["few_sign_changes"].append(key)
                if not _extrema_mags_decreasing(sx):
                    q4["not_damped"].append(key)
    q4_pass = (bool(q4["shear_by_tier"]) and not q4["not_increasing"] and not q4["super_ne_base"]
               and not q4["bad_endpoints"] and not q4["few_sign_changes"] and not q4["not_damped"])
    R["QT4_shear_monotone_damped"] = {**q4, "pass": q4_pass}

    # ---- QT5 negative controls ----
    q5 = {}
    # (a) flat gain 1.0 → no increase + each tier == base
    flat = {t: 1.0 for t in TIERS}
    anims_flat = G.build_animations(skel, sb, tier_gains=flat)
    flat_incr, flat_ne_base = [], []
    for qb in squash_beats:
        seq = [_peak_aniso(anims_flat["{}__{}".format(qb, t)]) for t in TIERS]
        if _strictly_increasing(seq):
            flat_incr.append(qb)
        for t in TIERS:
            vn = "{}__{}".format(qb, t)
            if json.dumps(anims_flat[vn], sort_keys=True) != json.dumps(anims[qb], sort_keys=True):
                flat_ne_base.append(vn)
    q5["a_flat_gain_guard"] = {"increasing_beats": flat_incr, "tiers_ne_base": flat_ne_base,
                               "pass": not flat_incr and not flat_ne_base}
    # (b) naive-amplify guard (crux): naive _amp_scale on squash frames breaks volume conservation
    g_hi = tg["Legend"]
    naive_prod_err, coupled_prod_err = [], []
    for qb in squash_beats:
        for bn, ch in anims[qb].get("bones", {}).items():
            for (sx, sy) in _interior_scale(ch):
                nx = TV._amp_scale(sx, g_hi); ny = TV._amp_scale(sy, g_hi)
                naive_prod_err.append(abs(round(nx, 4) * round(ny, 4) - 1.0))
                cx, cy = TV._amp_scale_coupled(sx, sy, g_hi)
                coupled_prod_err.append(abs(round(cx, 4) * round(cy, 4) - 1.0))
    naive_breaks = bool(naive_prod_err) and max(naive_prod_err) > TOL_VOL
    coupled_holds = bool(coupled_prod_err) and max(coupled_prod_err) <= TOL_VOL
    q5["b_naive_amplify_guard"] = {
        "naive_max_prod_err": round(max(naive_prod_err), 5) if naive_prod_err else None,
        "coupled_max_prod_err": round(max(coupled_prod_err), 5) if coupled_prod_err else None,
        "naive_breaks_conservation": naive_breaks, "coupled_holds_conservation": coupled_holds,
        "pass": naive_breaks and coupled_holds}
    # (c) coupled routing isolation
    #  ① squash 變體 == 耦合 amplify(且高檔位 != 普通 amplify → 證耦合確實改變行為、非恆等);
    #  ② 非-squash 主秀 scale beat **未被耦合**:其 scale 壓縮軸(<1)是普通 `_amp_scale` 的**樓地板**
    #     (檔位無關)。coupled 會把壓縮軸改成拉長軸的倒數(隨檔位變),故「<1 值逐檔不變」即證未耦合。
    #     只測非 count-aware 節拍(hit/charge/cascade/burst;combo/wobble 會依檔位重生成段數 → scale 幀本就變)。
    route = {"squash_ne_coupled": [], "squash_eq_naive_at_hi": [], "nonsquash_floor_moved": []}
    for qb in squash_beats:
        base = anims[qb]
        for tier in TIERS:
            vn = "{}__{}".format(qb, tier); g = tg[tier]
            exp_coupled = TV.amplify_anim(base, g, coupled_scale=True)
            if json.dumps(anims[vn], sort_keys=True) != json.dumps(exp_coupled, sort_keys=True):
                route["squash_ne_coupled"].append(vn)
        exp_naive_hi = TV.amplify_anim(base, g_hi, coupled_scale=False)
        if json.dumps(anims["{}__Legend".format(qb)], sort_keys=True) == \
                json.dumps(exp_naive_hi, sort_keys=True):
            route["squash_eq_naive_at_hi"].append(qb)

    def _sub1_scale(an):
        """anim → {bone: [(idx, x, y)]} 只取 scale 值 <1 的幀(壓縮軸樓地板檢查用)。"""
        out = {}
        for bn, ch in an.get("bones", {}).items():
            sub = [(i, f["x"], f["y"]) for i, f in enumerate(ch.get("scale", []))
                   if f["x"] < 1.0 or f["y"] < 1.0]
            if sub:
                out[bn] = sub
        return out

    for nm in [n for n in anims if "__" not in n]:
        cat = G.beat_category(nm)
        if cat not in TV.MAIN_SHOW_CATS or cat == "squash" or cat in TV.COUNT_AWARE_CATS:
            continue
        base_sub1 = _sub1_scale(anims[nm])
        if not base_sub1:
            continue
        for tier in TIERS:
            vn = "{}__{}".format(nm, tier)
            if vn not in anims:
                continue
            if json.dumps(_sub1_scale(anims[vn]), sort_keys=True) != \
                    json.dumps(base_sub1, sort_keys=True):
                route["nonsquash_floor_moved"].append(vn)
    q5["c_coupled_routing_isolated"] = {
        **route, "pass": (not route["squash_ne_coupled"] and not route["squash_eq_naive_at_hi"]
                          and not route["nonsquash_floor_moved"])}
    R["QT5_neg_control"] = {**q5, "pass": all(v["pass"] for v in q5.values())}

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
        for k in ["QT1_present_backward_compat", "QT2_aniso_peak_monotone",
                  "QT3_volume_preserved_per_tier", "QT4_shear_monotone_damped", "QT5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("QT2 aniso peak per tier", TIERS, ":")
        for qb, seq in R["QT2_aniso_peak_monotone"]["aniso_by_tier"].items():
            print("  {:10s} {}".format(qb, seq))
        print("QT4 shear peak per tier", TIERS, ":")
        for qb, seq in R["QT4_shear_monotone_damped"]["shear_by_tier"].items():
            print("  {:10s} {}".format(qb, seq))
        nb = R["QT5_neg_control"]["b_naive_amplify_guard"]
        print("QT5b naive vs coupled max|prod-1|: naive {} (breaks={}) / coupled {} (holds={})".format(
            nb["naive_max_prod_err"], nb["naive_breaks_conservation"],
            nb["coupled_max_prod_err"], nb["coupled_holds_conservation"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
