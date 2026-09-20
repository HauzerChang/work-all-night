#!/usr/bin/env python3
"""candidate G-4''''' 自我驗收閘 — squash(體積守恆擠壓)接檔位(tier)幅度差異化,**耦合 amplify**(純 CPU)。

補上 G-4''''(`validate_squash_gen.py`)留下的 honest boundary:squash 是產線第一個同時產出
**shear + 耦合非均勻 scale**(scaleX=1+q、scaleY=1/(1+q)、scaleX·scaleY≡1)的節拍,但當時**未接檔位**——
`squash ∉ MAIN_SHOW_CATS`,因為舊的逐軸 `_amp_scale` 只放大 identity 上方(scaleX>1 被放大),
壓扁軸(scaleY<1)的樓地板保留不動 → **破壞面積守恆**(scaleX·scaleY≠1)。

本次(G-4''''')把 squash 併入 `MAIN_SHOW_CATS`,並為它走**體積守恆的耦合 amplify**
(`tier_variants._amp_scale_coupled`,經 `COUPLED_SCALE_CATS` 路由):放大**擠壓量** q(拉長軸−1)、
以倒數導出壓扁軸 → scaleX·scaleY **仍≡1**、阻尼比 r 逐極值不變、identity 幀不動。於是每個檔位的
squash 擠壓**強度隨檔位遞增**(檔位愈高擠壓愈狠),而**體積守恆 + 非均勻 + 阻尼**三簽章逐檔保形。

**又一「檔位機制就緒 ≠ 每個新通道/節拍接上」實例**(同 E/H/I/J/G-4'/G-4''/G-4''');惟本例的
關鍵新意 = **耦合放大**:多通道約束(scaleX·scaleY≡1)下,幅度差異化不能逐軸獨立做,必須沿約束流形
放大(放大擠壓量而非各軸自由伸縮)。base tier(Super)g=1.0 → 耦合 amplify 為 identity →
`squash__Super` 逐位元 == 無檔位 squash(向後相容)。

真值/fixture 同 (J/G-4''/G-4'''):從**先驗庫**(slot_bigwin)經 `analyze_target` → **真實 build_spine
robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。主秀運動無唯一正解(PROPOSAL 手感),
閘驗**客觀結構簽章 + 檔位單調**,非美感;負對照證鑑別力(閘可信)。

AC(客觀、可量測):
  SQT1 present + backward-compat : 每檔位 `squash__{tier}` 直出、finite、有 bone 且**同時**帶 shear+scale;
                                   `squash__Super`(g=1.0)**逐位元** == 無檔位 squash(耦合 amplify g=1 → identity);
                                   base squash 與無檔位呼叫逐位元同;`tier_gains=None` → 不產 squash 變體。
  SQT2 volume preserved (crux)   : **每個檔位**、每個 squash bone 的每個內部極值幀 |scaleX·scaleY−1|≤TOL_VOL
                                   (面積守恆在放大後**仍成立** → 耦合 amplify 正確)。復用 `_sq3_eval` 判準。
  SQT3 magnitude monotone (crux) : **每個 squash bone**——擠壓峰 |scaleX−1| 與 shear 峰 |shearX|
                                   Super<Mega<Omg<Legend **嚴格遞增**(端到端經 build_animations 量);
                                   且擠壓峰比值 ≈ tier_gains 比值(線性放大 q → 擠壓量按增益等比放大)。
  SQT4 signature preserved       : **每個檔位**——(a)非均勻 max|scaleX−scaleY|≥MIN_ANISO(真擠壓保形);
                                   (b)擠壓幅度 |scaleX−1| 逐極值嚴格遞減(阻尼耦合保形);
                                   (c)shear 阻尼振盪(繞 0 變號≥3 + 相繼極值遞減);(d)identity 首尾介面。
  SQT5 negative controls         : (a)**耦合守衛(crux)**:對**同一** squash scale 幀施舊的逐軸獨立
                                   `_amp_scale`(pre-G-4''''' 錯誤路徑)於 Legend → 體積守恆 FALSE
                                   (證「必須耦合」且 SQT2 的體積判準有鑑別力);耦合路徑同幀則 TRUE。
                                   (b)**平增益守衛**:增益全 1.0 → 各檔位擠壓峰**不**嚴格遞增(相等)且
                                   `squash__{tier}` 逐位元 == base(證 SQT3 測的是真遞增)。
                                   (c)**路由隔離**:非-squash 主秀 beat 的 scale **不**被耦合處理——
                                   其 tier 變體仍等比(scaleX==scaleY,逐軸獨立放大),證耦合只施於 squash。

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
# 復用 G-4'''' 的 squash 讀取/判準 + G-4' 的 shear 阻尼簽章,確保與 squash_gen / wobble_tier 閘一致
from validate_squash_gen import (_squash_beats, _scale_xy, _interior_scale, _sq3_eval,
                                 MIN_ANISO, TOL_VOL, MIN_SHEAR)
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
RATIO_TOL = 0.02   # 擠壓峰增益比 vs tier_gain 比 的相對誤差上限(線性放大 q → 比值應吻合)


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


def _stretch_peak(chans):
    """squash bone 的擠壓峰 = max 內部極值 |scaleX−1|(拉長軸相對 identity 的最大量)。"""
    interior = _interior_scale(chans)
    return max((abs(sx - 1.0) for (sx, sy) in interior), default=0.0)


def _shear_peak(chans):
    sx = _shear_x(chans)
    return max((abs(v) for v in sx), default=0.0)


def _is_strict_inc(xs):
    return len(xs) >= 2 and all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)                                   # {tier: g}
    base = G.build_animations(skel, sb)                          # 無檔位
    amp_only = G.build_animations(skel, sb, tier_gains=gains)    # (J) 幅度(對 squash 走耦合)
    squash_beats = _squash_beats(base)
    R = {}

    # ---- SQT1 present + backward-compat ----
    t1 = {"squash_beats": squash_beats, "missing": [], "not_finite": [], "no_dual": [],
          "super_not_identical": [], "base_changed": [], "none_produced_variant": []}
    for qb in squash_beats:
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = amp_only.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            dual = [bn for bn, ch in an.get("bones", {}).items() if _shear_x(ch) and _scale_xy(ch)]
            if not dual:
                t1["no_dual"].append(vk)
        # Super(g=1.0)耦合 amplify = identity → 逐位元 == 無檔位 squash
        sup = amp_only.get("{}__Super".format(qb))
        if json.dumps(sup, sort_keys=True) != json.dumps(base[qb], sort_keys=True):
            t1["super_not_identical"].append(qb)
    # base(含 In/Loop/Out 與 base squash)逐位元不變(加檔位不改 base)
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(amp_only.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    # tier_gains=None → 不產任何 squash 變體
    novar = [k for k in base if "__" in k and G.beat_category(k) == "squash"]
    t1["none_produced_variant"] = novar
    t1_pass = (bool(squash_beats) and not any(t1[k] for k in
               ["missing", "not_finite", "no_dual", "super_not_identical",
                "base_changed", "none_produced_variant"]))
    R["SQT1_present_backward_compat"] = {**t1, "pass": t1_pass}

    # ---- SQT2 volume preserved across all tiers (crux) ----
    t2 = {"bad_volume": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = amp_only["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior or not _shear_x(ch):
                    continue
                vok, aok, dok, det = _sq3_eval(interior)
                key = "{}__{}::{}".format(qb, t, bn)
                t2["detail"][key] = {"prod": det["prod"], "volume_ok": vok}
                if not vok:
                    t2["bad_volume"].append(key)
    t2_pass = bool(t2["detail"]) and not t2["bad_volume"]
    R["SQT2_volume_preserved"] = {**t2, "pass": t2_pass}

    # ---- SQT3 magnitude monotone increasing across tiers (crux) ----
    t3 = {"stretch_not_mono": [], "shear_not_mono": [], "ratio_off": [], "detail": {}}
    # 逐 squash bone 量各檔位擠壓峰/ shear 峰
    for qb in squash_beats:
        bns = set()
        for t in TIERS:
            bns |= set(amp_only["{}__{}".format(qb, t)].get("bones", {}))
        for bn in sorted(bns):
            st = [_stretch_peak(amp_only["{}__{}".format(qb, t)].get("bones", {}).get(bn, {}))
                  for t in TIERS]
            sh = [_shear_peak(amp_only["{}__{}".format(qb, t)].get("bones", {}).get(bn, {}))
                  for t in TIERS]
            key = "{}::{}".format(qb, bn)
            t3["detail"][key] = {"stretch_peak": [round(x, 4) for x in st],
                                 "shear_peak": [round(x, 3) for x in sh]}
            if not _is_strict_inc(st):
                t3["stretch_not_mono"].append(key)
            if not _is_strict_inc(sh):
                t3["shear_not_mono"].append(key)
            # 擠壓峰比值應 ≈ tier_gain 比值(線性放大 q:peak_t = g_t · q_base → peak_t/peak_Super = g_t)
            if st[0] > 1e-6:
                for i, t in enumerate(TIERS):
                    exp = gains[t]                       # g_Super=1.0 → ratio 1
                    got = st[i] / st[0]
                    if abs(got - exp) > RATIO_TOL * max(exp, 1.0):
                        t3["ratio_off"].append((key, t, round(got, 4), exp))
    t3_pass = (bool(t3["detail"]) and not t3["stretch_not_mono"]
               and not t3["shear_not_mono"] and not t3["ratio_off"])
    R["SQT3_magnitude_monotone"] = {**t3, "pass": t3_pass}

    # ---- SQT4 signature preserved per tier ----
    t4 = {"no_aniso": [], "stretch_not_damped": [], "shear_not_damped": [],
          "few_sign_changes": [], "bad_interface": []}
    for qb in squash_beats:
        for t in TIERS:
            an = amp_only["{}__{}".format(qb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]; end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values())
                    and all(_is_ident(v) for v in end.values())):
                t4["bad_interface"].append("{}__{}".format(qb, t))
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                shx = _shear_x(ch)
                if not interior or not shx:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                vok, aok, dok, det = _sq3_eval(interior)   # aniso_ok / damped_ok(擠壓幅度遞減)
                if not aok:
                    t4["no_aniso"].append(key)
                if not dok:
                    t4["stretch_not_damped"].append(key)
                if _sign_changes_zero(shx) < 3:
                    t4["few_sign_changes"].append(key)
                if not _extrema_mags_decreasing(shx):
                    t4["shear_not_damped"].append(key)
    t4_pass = not any(t4[k] for k in t4)
    R["SQT4_signature_preserved"] = {**t4, "pass": t4_pass}

    # ---- SQT5 negative controls ----
    t5 = {}
    # (a) 耦合守衛(crux):對同一 squash 幀施舊逐軸獨立 _amp_scale → 體積守恆 FALSE;耦合則 TRUE
    #     取任一 squash bone 的 base 內部極值幀,以 Legend 增益比較兩種放大路徑。
    gL = gains["Legend"]
    ref_qb = squash_beats[0]
    ref_bn = next(bn for bn, ch in base[ref_qb]["bones"].items()
                  if _interior_scale(ch) and _shear_x(ch))
    ref_frames = _interior_scale(base[ref_qb]["bones"][ref_bn])   # [(sx,sy)]
    indep = [(TV._amp_scale(sx, gL), TV._amp_scale(sy, gL)) for (sx, sy) in ref_frames]
    coup = [TV._amp_scale_coupled(sx, sy, gL) for (sx, sy) in ref_frames]
    indep_vol_ok = _sq3_eval(indep)[0]
    coup_vol_ok = _sq3_eval(coup)[0]
    t5["a_coupling_required"] = {
        "bone": ref_bn, "beat": ref_qb, "gain": gL,
        "indep_prod": [round(x * y, 5) for (x, y) in indep],
        "coupled_prod": [round(x * y, 5) for (x, y) in coup],
        "indep_volume_ok": indep_vol_ok, "coupled_volume_ok": coup_vol_ok,
        "pass": (not indep_vol_ok) and coup_vol_ok}     # 逐軸獨立壞守恆、耦合守恆
    # (b) 平增益守衛:全 1.0 → 擠壓峰不遞增 + squash__{tier} 逐位元 == base
    flat = {t: 1.0 for t in TIERS}
    fa = G.build_animations(skel, sb, tier_gains=flat)
    any_mono = False; flat_changed = []
    for qb in squash_beats:
        for bn in base[qb].get("bones", {}):
            st = [_stretch_peak(fa["{}__{}".format(qb, t)].get("bones", {}).get(bn, {})) for t in TIERS]
            if _is_strict_inc(st):
                any_mono = True
        for t in TIERS:
            if json.dumps(fa["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_changed.append("{}__{}".format(qb, t))
    t5["b_flat_gain_guard"] = {"any_stretch_monotone": any_mono, "flat_changed": flat_changed,
                               "pass": (not any_mono) and (not flat_changed)}
    # (c) 路由隔離:非-squash 主秀 beat 的 scale 仍等比(未被耦合處理)
    leak = []
    for nm, an in amp_only.items():
        if "__" not in nm or G.beat_category(nm) == "squash":
            continue
        cat = G.beat_category(nm)
        if cat not in TV.MAIN_SHOW_CATS:
            continue
        for bn, ch in an.get("bones", {}).items():
            xy = _scale_xy(ch)
            # 非-squash 節拍的 scale 是等比 pulse(scaleX==scaleY);若被耦合誤處理會變非均勻
            if any(abs(sx - sy) > 1e-4 for (sx, sy) in xy):
                leak.append((nm, bn))
    t5["c_routing_isolated"] = {"non_squash_aniso_leak": leak, "pass": not leak}
    R["SQT5_neg_control"] = {**t5, "pass": all(v["pass"] for v in t5.values())}

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
        for k in ["SQT1_present_backward_compat", "SQT2_volume_preserved",
                  "SQT3_magnitude_monotone", "SQT4_signature_preserved", "SQT5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("SQT3 stretch/shear peaks per tier {}:".format(TIERS))
        for key, d in R["SQT3_magnitude_monotone"]["detail"].items():
            print("  {:22s} stretch {}  shear {}".format(key, d["stretch_peak"], d["shear_peak"]))
        a5 = R["SQT5_neg_control"]["a_coupling_required"]
        print("SQT5(a) coupling-required guard: indep_prod {} (vol_ok={})  coupled_prod {} (vol_ok={})".format(
            a5["indep_prod"], a5["indep_volume_ok"], a5["coupled_prod"], a5["coupled_volume_ok"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
