#!/usr/bin/env python3
"""candidate G-4''''' 自我驗收閘 — squash(斜拉果凍擠壓)接 tier 檔位差異化,**體積守恆耦合 amplify**(純 CPU)。

一路的 honest boundary(G-4'''':`validate_squash_gen.py`):`gen_squash` 產出**耦合的 shear + 非均勻
scale**(scaleX·scaleY==1 的體積守恆擠壓),但 **squash 未接檔位機制** —— 當時 squash **不在**
`MAIN_SHOW_CATS`,因為 (J) 的幅度增益 `_amp_scale` 只放大 identity **上方**(拉長軸)、壓扁軸樓地板
不動 → **破壞體積守恆**(scaleX·scaleY≠1)。本閘(G-4''''')驗證最後一段**已接上**:把 squash 併入
`MAIN_SHOW_CATS` 並用**耦合 amplify**(`_amp_squash_coupled`:從拉長軸回推擠壓量 q,以 g 放大
q→g·q,再重建壓扁軸 1/(1+g·q))→ 擠壓 strain 隨檔位**嚴格遞增**,同時 **scaleX·scaleY==1 恆守恆**。

**關鍵:squash 是第一個 scale 通道為體積守恆的主秀節拍**,其檔位差異化不能逐軸放大(破壞守恆),
必須耦合放大 strain。shear 通道則同 wobble(v'=g*v,對 0 對稱同比放大)→ shear 峰亦隨檔位遞增。
兩軸(shear 峰 / squash strain)以同一增益 g 同源放大,阻尼比 r=0.5 不變 → 阻尼振盪與體積守恆
兩簽章逐檔保形。本次為 **amplitude 軸**;count-aware(擠壓段數隨檔位,nosc 已備參)為後續(比照 G-4'''')。

真值/fixture 與 (E/H/I/J/G-4'/G-4'') 一致:從**先驗庫**(slot_bigwin)經 `analyze_target` →
**真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。主秀運動無唯一正解
(PROPOSAL 手感),閘驗**客觀結構簽章(體積守恆 + 遞增 strain + 阻尼保形)**,非美感;負對照證鑑別力。

AC(客觀、可量測):
  V1 present + backward-compat : 每檔位 `squash__{tier}` 直出、finite、有 bone、**同時**帶 shear+scale;
                                 base squash 逐位元不變;**squash__Super(g=1.0)逐位元 == base squash**
                                 (耦合 amplify 在 g=1 為 identity → 向後相容)。
  V2 crux amplitude + volume  : **每 squash bone**——(a)squash strain 峰 |scaleX−1|
                                 Super<Mega<Omg<Legend **嚴格遞增**、Super==base;(b)shear 峰亦嚴格遞增、
                                 Super==base;(c)**crux 體積守恆保持**:每檔位每個 squash 極值幀
                                 |scaleX·scaleY−1|≤TOL_VOL(耦合 amplify 保積==1,天真逐軸則破壞);
                                 (d)非均勻保持:每檔位仍 max|scaleX−scaleY|≥MIN_ANISO(仍真擠壓非等比 pulse)。
  V3 signature preserved      : **每檔位**——(a)shear 阻尼振盪(首尾 0、繞 0 變號≥3、相繼極值遞減);
                                 (b)squash strain 隨極值嚴格遞減(阻尼耦合);(c)sample(0)/sample(dur)
                                 各 bone identity(scale 首尾 (1,1))→ 可插 Loop。
  V4 coupled == regen(Q·g)    : **耦合 amplify 等價於「以 Q→g·Q 重生成 gen_squash」**——對每檔位每 bone,
                                 `amplify` 後的 scale 幀與「gen_squash 用 g·Q 直接生成」在容差內相等
                                 (證耦合 amplify 就是生成器自身的擠壓 strain 旋鈕,同 J-2/G-4''' 的重生成等價)。
  V5 neg-control              : (a)**平增益守衛**:增益全 1.0 → V2 strain 遞增 FALSE 且各檔位==base
                                 (證閘測遞增非恆真);(b)**天真逐軸破壞守恆(honest boundary 證明)**:對同一
                                 squash 幀改用舊 `_amp_scale` 逐軸放大 → 高檔位 |scaleX·scaleY−1| 顯著漂離 0
                                 (證耦合 amplify 為必要,非等效);(c)**耦合隔離**:耦合 amplify 只作用
                                 squash(VOLUME_CONSERVE_CATS)—— 非-squash 主秀 beat 的 tier 變體與「逐軸
                                 amplify」逐位元相同(scale 通道未被耦合路徑污染)。

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
# 復用 G-4'/G-4'''' 的 shear 讀取、阻尼簽章、體積守恆判準 —— 與 shear-gen / squash-gen 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import (_scale_xy, _interior_scale, _sq3_eval, _has_aniso_scale,
                                 MIN_SHEAR, MIN_ANISO, TOL_VOL)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
REGEN_TOL = 2e-4    # V4 耦合 amplify vs 重生成 Q·g 的逐幀容差(雙 4 位小數 round 疊加餘裕)
NAIVE_BREAK = 0.02  # V5(b) 天真逐軸在最高檔位 |積−1| 應顯著漂離(遠大於耦合的 <1e-4)


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


def _strain_peak(ch):
    """該 bone scale 通道的最大 squash strain |scaleX−1|(無 scale 回 0)。"""
    xy = _scale_xy(ch)
    return max((abs(sx - 1.0) for (sx, sy) in xy), default=0.0)


def _shear_peak(ch):
    sx = _shear_x(ch)
    return max((abs(v) for v in sx), default=0.0)


def _is_strict_inc(xs):
    return len(xs) >= 2 and all(xs[i + 1] > xs[i] + 1e-9 for i in range(len(xs) - 1))


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                          # 無檔位
    amp_only = G.build_animations(skel, sb, tier_gains=gains)     # 帶檔位(squash 走耦合 amplify)
    squash_beats = _squash_beats(base)
    R = {}

    # ---- V1 present + backward-compat ----
    v1 = {"squash_beats": squash_beats, "missing": [], "not_finite": [], "no_bones": [],
          "no_dual": [], "base_changed": [], "super_ne_base": []}
    for qb in squash_beats:
        # base 逐位元不變
        if json.dumps(base[qb], sort_keys=True) != json.dumps(amp_only.get(qb), sort_keys=True):
            v1["base_changed"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = amp_only.get(vk)
            if an is None:
                v1["missing"].append(vk); continue
            if not SA.all_finite(an):
                v1["not_finite"].append(vk)
            if not an.get("bones"):
                v1["no_bones"].append(vk)
            dual = any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values())
            if not dual:
                v1["no_dual"].append(vk)
        # squash__Super(g=1.0)逐位元 == base squash(耦合 amplify g=1 為 identity)
        sk = "{}__Super".format(qb)
        if json.dumps(amp_only.get(sk), sort_keys=True) != json.dumps(base[qb], sort_keys=True):
            v1["super_ne_base"].append(qb)
    v1_pass = (bool(squash_beats) and not any(v1[k] for k in
               ("missing", "not_finite", "no_bones", "no_dual", "base_changed", "super_ne_base")))
    R["V1_present_backward_compat"] = {**v1, "pass": v1_pass}

    # ---- V2 crux: amplitude ladder + volume conservation + non-uniform, per bone ----
    v2 = {"strain_not_mono": [], "super_ne_base_strain": [], "shear_not_mono": [],
          "super_ne_base_shear": [], "bad_volume": [], "weak_aniso": [], "detail": {}}
    for qb in squash_beats:
        bones = [bn for bn, ch in base[qb].get("bones", {}).items() if _scale_xy(ch) and _shear_x(ch)]
        for bn in bones:
            strain = [_strain_peak(amp_only["{}__{}".format(qb, t)]["bones"][bn]) for t in TIERS]
            shear = [_shear_peak(amp_only["{}__{}".format(qb, t)]["bones"][bn]) for t in TIERS]
            base_strain = _strain_peak(base[qb]["bones"][bn])
            base_shear = _shear_peak(base[qb]["bones"][bn])
            # (c) 體積守恆 + (d) 非均勻:每檔位每極值幀
            vol_ok, aniso_ok = True, True
            vmax = 0.0
            for t in TIERS:
                interior = _interior_scale(amp_only["{}__{}".format(qb, t)]["bones"][bn])
                vok, aok, dok, det = _sq3_eval(interior)
                vmax = max(vmax, max((abs(p - 1.0) for p in det["prod"]), default=0.0))
                vol_ok = vol_ok and vok
                aniso_ok = aniso_ok and aok
            key = "{}::{}".format(qb, bn)
            v2["detail"][key] = {"strain": [round(x, 4) for x in strain],
                                 "shear": [round(x, 3) for x in shear],
                                 "max_vol_dev": round(vmax, 6)}
            if not _is_strict_inc(strain):
                v2["strain_not_mono"].append(key)
            if abs(strain[0] - base_strain) > TOL:
                v2["super_ne_base_strain"].append(key)
            if not _is_strict_inc(shear):
                v2["shear_not_mono"].append(key)
            if abs(shear[0] - base_shear) > TOL:
                v2["super_ne_base_shear"].append(key)
            if not vol_ok:
                v2["bad_volume"].append(key)
            if not aniso_ok:
                v2["weak_aniso"].append(key)
    v2_pass = (bool(v2["detail"]) and not any(v2[k] for k in
               ("strain_not_mono", "super_ne_base_strain", "shear_not_mono",
                "super_ne_base_shear", "bad_volume", "weak_aniso")))
    R["V2_amplitude_volume"] = {**v2, "pass": v2_pass}

    # ---- V3 signature preserved per tier ----
    v3 = {"shear_bad": [], "strain_not_damped": [], "bad_interface": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = amp_only["{}__{}".format(qb, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                v3["bad_interface"].append("{}__{}".format(qb, t))
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                ends_ok = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                nsc = _sign_changes_zero(sx)
                damp = _extrema_mags_decreasing(sx)
                if not (ends_ok and nsc >= 3 and damp):
                    v3["shear_bad"].append(key)
                # squash strain 隨極值嚴格遞減(阻尼耦合)
                interior = _interior_scale(ch)
                mag = [abs(sx_ - 1.0) for (sx_, sy_) in interior]
                if not (len(mag) >= 2 and all(mag[i + 1] < mag[i] - 1e-9 for i in range(len(mag) - 1))):
                    v3["strain_not_damped"].append(key)
                v3["detail"][key] = {"n_sign_changes": nsc, "damped": damp, "strain_mag": [round(m, 4) for m in mag]}
    v3_pass = (bool(v3["detail"]) and not v3["shear_bad"]
               and not v3["strain_not_damped"] and not v3["bad_interface"])
    R["V3_signature_preserved"] = {**v3, "pass": v3_pass}

    # ---- V4 coupled amplify == regenerate gen_squash with Q→g·Q ----
    # 對每檔位每 bone:耦合 amplify 後的 scale 幀,應與「以該檔位 gains 直接放大生成器擠壓量 Q」相等。
    # 這裡以「等價命題」量化:耦合 amplify 的 (scaleX−1) == g × (base scaleX−1)(逐極值),且積仍==1。
    # (gen_squash 的 q_i=Q·rⁱ;放大 Q→g·Q ⇒ 各 q_i→g·q_i ⇒ scaleX−1=g·q_i。)
    v4 = {"mismatch": [], "detail": {}}
    for qb in squash_beats:
        for bn, chb in base[qb].get("bones", {}).items():
            base_int = _interior_scale(chb)
            if not base_int:
                continue
            base_q = [sx - 1.0 for (sx, sy) in base_int]
            for t, g in gains.items():
                amp_int = _interior_scale(amp_only["{}__{}".format(qb, t)]["bones"][bn])
                amp_q = [sx - 1.0 for (sx, sy) in amp_int]
                exp_q = [g * q for q in base_q]
                key = "{}__{}::{}".format(qb, t, bn)
                # 逐極值:放大量 == g×base;且積==1(重建壓扁軸)
                q_ok = len(amp_q) == len(exp_q) and all(abs(a - e) <= REGEN_TOL for a, e in zip(amp_q, exp_q))
                prod_ok = all(abs(sx * sy - 1.0) <= TOL_VOL for (sx, sy) in amp_int)
                if not (q_ok and prod_ok):
                    v4["mismatch"].append(key)
                if t == "Legend":
                    v4["detail"][key] = {"amp_q": [round(x, 4) for x in amp_q],
                                         "expected_gQ": [round(x, 4) for x in exp_q]}
    v4_pass = bool(v4["detail"]) and not v4["mismatch"]
    R["V4_coupled_eq_regen"] = {**v4, "pass": v4_pass}

    # ---- V5 negative controls ----
    v5 = {}
    # (a) 平增益守衛:全 1.0 → strain 遞增 FALSE + 各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_ne_base = False, []
    for qb in squash_beats:
        for bn, ch in base[qb].get("bones", {}).items():
            if not _scale_xy(ch):
                continue
            strain = [_strain_peak(flat_anims["{}__{}".format(qb, t)]["bones"][bn]) for t in TIERS]
            if _is_strict_inc(strain):
                any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_ne_base.append("{}__{}".format(qb, t))
    v5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_ne_base,
                          "pass": (not any_mono_flat) and not flat_ne_base}
    # (b) 天真逐軸破壞守恆(honest boundary 證明):對真實 squash 幀改用舊 `_amp_scale` 逐軸 →
    #     高檔位 |scaleX·scaleY−1| 顯著漂離 0(證耦合 amplify 為必要;耦合則 <1e-4)。
    g_leg = gains["Legend"]
    naive_max, coupled_max = 0.0, 0.0
    for qb in squash_beats:
        for bn, ch in base[qb].get("bones", {}).items():
            for (sx, sy) in _interior_scale(ch):
                nx = round(TV._amp_scale(sx, g_leg), 4)   # 拉長軸放大
                ny = round(TV._amp_scale(sy, g_leg), 4)   # 壓扁軸(<1)樓地板不動
                naive_max = max(naive_max, abs(nx * ny - 1.0))
                cx, cy = TV._amp_squash_coupled(sx, sy, g_leg)
                coupled_max = max(coupled_max, abs(cx * cy - 1.0))
    v5["b_naive_breaks_volume"] = {"naive_max_vol_dev": round(naive_max, 5),
                                   "coupled_max_vol_dev": round(coupled_max, 6),
                                   "pass": naive_max >= NAIVE_BREAK and coupled_max <= TOL}
    # (c) 耦合隔離:耦合 amplify 只作用 squash → 非-squash 主秀 beat 的 tier 變體 == 逐軸 amplify。
    # 以「手動逐軸 amplify base beat」與「build_animations 產出」逐位元對照(非-squash beat)。
    leak = []
    for beat in base:
        if "__" in beat or G.beat_category(beat) not in TV.MAIN_SHOW_CATS:
            continue
        if G.beat_category(beat) in TV.VOLUME_CONSERVE_CATS:
            continue
        for t, g in gains.items():
            vk = "{}__{}".format(beat, t)
            if vk not in amp_only:
                continue
            manual = TV.amplify_anim(base[beat], g, coupled_scale=False)
            if json.dumps(manual, sort_keys=True) != json.dumps(amp_only[vk], sort_keys=True):
                leak.append(vk)
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
        for k in ["V1_present_backward_compat", "V2_amplitude_volume", "V3_signature_preserved",
                  "V4_coupled_eq_regen", "V5_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V2 strain/shear peaks per tier {}:".format(TIERS))
        for key, d in R["V2_amplitude_volume"]["detail"].items():
            print("  {:16s} strain {}  shear {}  max|prod-1| {}".format(
                key, d["strain"], d["shear"], d["max_vol_dev"]))
        print("V5(b) naive_max_vol_dev {} vs coupled {}".format(
            R["V5_neg_control"]["b_naive_breaks_volume"]["naive_max_vol_dev"],
            R["V5_neg_control"]["b_naive_breaks_volume"]["coupled_max_vol_dev"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
