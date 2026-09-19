#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 的體積守恆擠壓)接檔位**幅度**差異化(純 CPU)。

candidate (J) 讓主秀 beat 依檔位**幅度**差異化(愈高檔位愈爆),(G-4'')把 wobble 的 **shear** 通道接上檔位。
但 squash 的另一半幅度軸在**非均勻 scale**(scaleX=1+q 拉長、scaleY=1/(1+q) 壓扁、scaleX·scaleY≡1 體積守恆),
一直是 (G-4'''') 明列的 honest boundary:一般 `_amp_scale` 只放大 identity **上方**(scaleX>1 放大、scaleY<1
樓地板不動)→ 兩軸增益不對稱 → **破壞體積守恆**,故 squash 當時無法進 `MAIN_SHOW_CATS`、無檔位變體。

本次(G-4''''')補上這個缺口:對 squash 的 scale 通道**耦合放大**(`_amp_squash_scale`:以 q=scaleX−1 為
擠壓量,q'=g·q → scaleX'=1+q'、scaleY'=1/(1+q'))⇒ **放大後 scaleX'·scaleY'≡1(體積守恆對所有檔位保持)**
且 scaleX'≠scaleY'(非均勻仍在);shear 通道同 wobble(v'=g·v,阻尼簽章保形)。squash 因需**耦合** amplify
故不入 MAIN_SHOW_CATS,改由 `COUPLED_AMP_CATS` 集合在 `build_animations` 路由到 `amplify_squash_anim`
(與 J 的 `amplify_anim` 互斥)。⇒ squash 的 **shear 峰**與**擠壓量 q** 雙雙隨檔位嚴格遞增,體積守恆與
非均勻與首尾 identity 介面在每個檔位保持。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位擠壓愈深、斜拉愈大,但仍體積守恆」是可量化的檔位簽章,用負對照(平增益 + 破壞守恆的一般 amplify)
證鑑別力(閘可信)。從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  S1 present + backward-compat : squash base beat 帶 shear + 非均勻 scale;每檔位 `squash__{tier}` 皆產出、
                                finite、有 bone、≥1 bone 同時帶 shear 與 scale 通道、名經 `beat_category` 仍
                                路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains 的 base squash + In/Loop/Out 相同)。
  S2 crux — stretch monotone   : 各檔位 squash 的峰**擠壓量 q**(=max scaleX − 1)Super<Mega<Omg<Legend
                                **嚴格遞增**(端到端經 build_animations 量),且首檔(Super,g=1)峰 == base 峰(向後相容)。
  S3 crux — volume kept @all    : **每個檔位**的每個 squash 極值幀 (a)|scaleX·scaleY − 1| ≤ TOL_VOL(體積守恆);
                                (b)非均勻 |scaleX−scaleY| 峰 ≥ MIN_ANISO(擠壓仍非等比);(c)首尾 scale==(1,1)
                                且 shearX==0(setup identity 介面 → 可插 Loop 間)。→ 耦合 amplify 對所有檔位保守恆。
  S4 shear monotone + damped   : 各檔位 squash 的峰 |shearX| 亦 Super<Mega<Omg<Legend 嚴格遞增(shear 同被
                                放大),且**每個檔位**仍 (a)首尾 shearX==0;(b)繞 0 變號 ≥3;(c)相繼極值幅度
                                嚴格遞減(阻尼)。→ 雙通道同比放大,結構簽章逐檔保形。
  S5 neg-control               : (a) **平增益守衛**:增益階梯全 1.0 → S2 擠壓遞增 FALSE 且各檔位 squash
                                逐位元 == base squash(證閘測遞增非恆真);
                                (b) **破壞守恆守衛**:對 squash bone 施**一般** `amplify_bone_tl`(_amp_scale
                                只放大 scaleX>1、scaleY<1 樓地板不動)→ 體積 |積−1| 遠超 TOL_VOL(守恆壞掉);
                                而耦合 `amplify_squash_bone_tl` 同 g 下守恆仍成立 → 證**耦合 amplify 必要**且閘抓得到破壞。

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
# 復用 G-4' 阻尼簽章判準 + G-4'''' squash 極值/體積判準(與 shear-gen / squash-gen 閘完全一致)
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import (_squash_beats, _interior_scale, _scale_xy,
                                 TOL_VOL, MIN_ANISO)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
MIN_SHEAR = 5.0     # 度,base squash shearX 峰值下限(確認確有明顯 shear)
MIN_Q = 0.05        # base squash 峰擠壓量 q 下限(確認確有明顯非均勻擠壓)


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/squash_tier_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _shear_peak(anim):
    """該 anim 全 bone 的峰 |shearX|(無 shear 回 0)。"""
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _stretch_peak(anim):
    """該 anim 全 bone squash 極值的峰擠壓量 q = max(scaleX) − 1(無 scale 回 0)。"""
    peaks = []
    for ch in anim.get("bones", {}).values():
        xy = _scale_xy(ch)
        if xy:
            peaks.append(max(sx for sx, _ in xy) - 1.0)
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

    # ---- S1 present + backward-compat ----
    s1 = {"squash_beats": squash_beats, "base_weak": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": []}
    for sb_name in squash_beats:
        if _shear_peak(base[sb_name]) < MIN_SHEAR or _stretch_peak(base[sb_name]) < MIN_Q:
            s1["base_weak"].append(sb_name)
        for t in TIERS:
            vk = "{}__{}".format(sb_name, t)
            an = anims.get(vk)
            if an is None:
                s1["missing"].append(vk); continue
            if not SA.all_finite(an):
                s1["not_finite"].append(vk)
            if not an.get("bones"):
                s1["no_bones"].append(vk)
            # ≥1 bone 同時帶 shear 與 scale(雙通道)
            dual = any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values())
            if not dual:
                s1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                s1["misrouted"].append((vk, G.beat_category(vk)))
    # base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            s1["base_changed"].append(k)
    s1_pass = (bool(squash_beats) and not any(s1[k] for k in
               ["base_weak", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed"]))
    R["S1_present_backward_compat"] = {**s1, "pass": s1_pass}

    # ---- S2 crux: stretch (擠壓量 q) monotone across tiers ----
    s2 = {"beats": {}, "fail_mono": [], "fail_base": []}
    for sb_name in squash_beats:
        peaks = [_stretch_peak(anims["{}__{}".format(sb_name, t)]) for t in TIERS]
        base_peak = _stretch_peak(base[sb_name])
        mono = _is_strict_inc(peaks)
        super_eq_base = abs(peaks[0] - base_peak) <= 1e-4
        s2["beats"][sb_name] = {"stretch_peaks": [round(p, 4) for p in peaks],
                                "base_peak": round(base_peak, 4),
                                "mono": mono, "super_eq_base": super_eq_base}
        if not mono:
            s2["fail_mono"].append(sb_name)
        if not super_eq_base:
            s2["fail_base"].append(sb_name)
    s2_pass = bool(s2["beats"]) and not s2["fail_mono"] and not s2["fail_base"]
    R["S2_stretch_monotone"] = {**s2, "pass": s2_pass}

    # ---- S3 crux: volume preserved + non-uniform + identity interface @ every tier ----
    s3 = {"vol_break": [], "not_aniso": [], "bad_interface": [], "detail": {}}
    for sb_name in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(sb_name, t)]
            for bn, ch in an.get("bones", {}).items():
                xy = _scale_xy(ch)
                if not xy:
                    continue
                key = "{}__{}::{}".format(sb_name, t, bn)
                interior = _interior_scale(ch)
                prod = [sx * sy for (sx, sy) in interior]
                aniso = [abs(sx - sy) for (sx, sy) in interior]
                vol_ok = bool(interior) and all(abs(p - 1.0) <= TOL_VOL for p in prod)
                aniso_ok = bool(aniso) and max(aniso) >= MIN_ANISO
                # 首尾 identity 介面:scale==(1,1) 且 shearX==0
                sx0, sy0 = xy[0]; sxE, syE = xy[-1]
                shx = _shear_x(ch)
                iface_ok = (abs(sx0 - 1.0) < 1e-6 and abs(sy0 - 1.0) < 1e-6 and
                            abs(sxE - 1.0) < 1e-6 and abs(syE - 1.0) < 1e-6 and
                            (not shx or (abs(shx[0]) < 1e-6 and abs(shx[-1]) < 1e-6)))
                s3["detail"][key] = {"prod": [round(p, 5) for p in prod],
                                     "aniso_peak": round(max(aniso), 4) if aniso else 0.0,
                                     "vol_ok": vol_ok, "aniso_ok": aniso_ok, "iface_ok": iface_ok}
                if not vol_ok:
                    s3["vol_break"].append(key)
                if not aniso_ok:
                    s3["not_aniso"].append(key)
                if not iface_ok:
                    s3["bad_interface"].append(key)
    s3_pass = (bool(s3["detail"]) and not s3["vol_break"]
               and not s3["not_aniso"] and not s3["bad_interface"])
    R["S3_volume_kept_all_tiers"] = {**s3, "pass": s3_pass}

    # ---- S4 shear peak monotone + damped signature per tier ----
    s4 = {"beats": {}, "fail_mono": [], "bad_endpoints": [], "few_sign_changes": [], "not_damped": []}
    for sb_name in squash_beats:
        peaks = [_shear_peak(anims["{}__{}".format(sb_name, t)]) for t in TIERS]
        mono = _is_strict_inc(peaks)
        s4["beats"][sb_name] = {"shear_peaks": [round(p, 3) for p in peaks], "mono": mono}
        if not mono:
            s4["fail_mono"].append(sb_name)
        for t in TIERS:
            an = anims["{}__{}".format(sb_name, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(sb_name, t, bn)
                if not (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6):
                    s4["bad_endpoints"].append(key)
                if _sign_changes_zero(sx) < 3:
                    s4["few_sign_changes"].append(key)
                if not _extrema_mags_decreasing(sx):
                    s4["not_damped"].append(key)
    s4_pass = (bool(s4["beats"]) and not s4["fail_mono"] and not s4["bad_endpoints"]
               and not s4["few_sign_changes"] and not s4["not_damped"])
    R["S4_shear_monotone_damped"] = {**s4, "pass": s4_pass}

    # ---- S5 negative controls ----
    s5 = {}
    # (a) 平增益守衛:全 1.0 → 擠壓遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for sb_name in squash_beats:
        peaks = [_stretch_peak(flat_anims["{}__{}".format(sb_name, t)]) for t in TIERS]
        if _is_strict_inc(peaks):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(sb_name, t)], sort_keys=True) != \
               json.dumps(base[sb_name], sort_keys=True):
                flat_base_diff.append("{}__{}".format(sb_name, t))
    s5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) 破壞守恆守衛:一般 amplify_bone_tl(_amp_scale)對 squash bone → 體積壞掉;耦合 amplify → 守恆
    g = 2.1
    sb0 = squash_beats[0]
    # 取 base squash 一支有 scale 極值(內部非均勻)的 bone
    src_bn, src_ch = next((bn, ch) for bn, ch in base[sb0]["bones"].items() if _interior_scale(ch))
    naive = TV.amplify_bone_tl(src_ch, g)         # 一般(J)amplify → 破壞守恆
    coupled = TV.amplify_squash_bone_tl(src_ch, g)  # 耦合 amplify → 守恆
    naive_prod = [sx * sy for (sx, sy) in _interior_scale(naive)]
    coupled_prod = [sx * sy for (sx, sy) in _interior_scale(coupled)]
    naive_max_err = max(abs(p - 1.0) for p in naive_prod) if naive_prod else 0.0
    coupled_max_err = max(abs(p - 1.0) for p in coupled_prod) if coupled_prod else 1.0
    s5["b_conservation_guard"] = {
        "naive_max_vol_err": round(naive_max_err, 5), "coupled_max_vol_err": round(coupled_max_err, 5),
        "naive_breaks": naive_max_err > TOL_VOL, "coupled_keeps": coupled_max_err <= TOL_VOL,
        "pass": naive_max_err > TOL_VOL and coupled_max_err <= TOL_VOL}
    R["S5_neg_control"] = {**s5, "pass": all(v["pass"] for v in s5.values())}

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
        for k in ["S1_present_backward_compat", "S2_stretch_monotone", "S3_volume_kept_all_tiers",
                  "S4_shear_monotone_damped", "S5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("S2 stretch peaks (q) per tier {}:".format(TIERS))
        for nm, d in R["S2_stretch_monotone"]["beats"].items():
            print("  {:10s} {}  (base {})".format(nm, d["stretch_peaks"], d["base_peak"]))
        print("S4 shear peaks per tier {}:".format(TIERS))
        for nm, d in R["S4_shear_monotone_damped"]["beats"].items():
            print("  {:10s} {}".format(nm, d["shear_peaks"]))
        b = R["S5_neg_control"]["b_conservation_guard"]
        print("S5(b) naive vol_err={} (breaks={}) | coupled vol_err={} (keeps={})".format(
            b["naive_max_vol_err"], b["naive_breaks"], b["coupled_max_vol_err"], b["coupled_keeps"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
