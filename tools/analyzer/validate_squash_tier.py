#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

candidate (J) 讓主秀 beat 依檔位**幅度**差異化;(G-4'') 把 wobble 的 **shear** 峰接上檔位增益。
但 (G-4'''') 新生成的 squash(斜拉果凍擠壓)其 scale 是**體積守恆耦合**(scaleX=1+q 拉長、
scaleY=1/(1+q) 壓扁,scaleX·scaleY≡1)—— 若沿用單軸 `_amp_scale`(只放大 identity 上方),
scaleX 被放大而 scaleY 樓地板保留 → **破壞體積守恆**(scaleX·scaleY≠1);故 squash 一直被排除在
`MAIN_SHOW_CATS` 外(honest boundary)。本次(G-4''''')補上**耦合 amplify**(`amplify_bone_tl(coupled_scale=True)`:
只放大擠壓量 q、scaleY 依 1/(1+q') 重算)→ 讓 squash 的 shear 峰**與**擠壓深度**雙通道**隨檔位嚴格遞增,
而**體積守恆對所有檔位保持**(強度變、結構不變 —— 誠實地:檔位=更斜更擠,非別種運動)。

真值界定同 (E/H/I/J/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**。
從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  ST1 present + backward-compat : squash base beat 同時帶 shear+scale;每檔位 `squash__{tier}` 皆產出、
                                finite、有 bone、≥1 bone 同時帶 shear+scale、名經 `beat_category` 仍路由回 squash;
                                **base 逐位元不變**(帶/不帶 tier_gains 的 base squash + In/Loop/Out 相同)。
  ST2 crux — dual-channel monotone: 各檔位 squash 的**擠壓深度**(峰非均勻 |scaleX−scaleY|)**與 shear 峰**
                                皆 Super<Mega<Omg<Legend **嚴格遞增**(端到端經 build_animations 量),
                                且首檔(Super,g=1)兩者 == base(向後相容)。
  ST3 crux — volume conserved per tier: **每個檔位**的 squash 每個 scale 極值幀 (a)|scaleX·scaleY−1|≤TOL_VOL
                                (面積守恆對所有檔位保持,耦合 amplify 的關鍵);(b)非均勻 |scaleX−scaleY|≥MIN_ANISO
                                (真擠壓,非等比);(c)擠壓幅度 |scaleX−1| 隨極值嚴格遞減(阻尼耦合保形)。
  ST4 shear damped per tier    : **每個檔位**的 squash shear 通道仍 (a)首尾 shearX==0;(b)繞 0 變號 ≥3;
                                (c)相繼極值嚴格遞減(阻尼);且 scale 首尾 == (1,1)(identity 介面,可插 Loop)。
  ST5 shear isolated           : 全 storyboard(含所有檔位變體)中,只有 shear-emitters(`SHEAR_CATS`,含
                                其 `__tier` 變體)帶 shear;非 shear-emitter 主秀 beat 及其變體 0 bone 帶 shear。
  ST6 neg-control              : (a) **平增益守衛**:增益全 1.0 → ST2 遞增 FALSE 且各檔位 == base;
                                (b) **crux 天真-amplify 守衛**:對 squash 極值幀施**單軸** `_amp_scale`(非耦合)
                                → |scaleX·scaleY−1| 遠超 TOL_VOL(證 ST3 的守恆檢查有鑑別力、耦合 amplify 必要);
                                (c) **耦合單元測**:`amplify_bone_tl(coupled_scale=True)` 對 squash bone 守恆
                                (積≡1)且擠壓放大;`coupled_scale=False`(單軸)對同 bone 破壞守恆(對照 c 內含)。

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
# 復用 G-4'/G-4'''' 的阻尼簽章與體積守恆判準,確保與既有閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import (_scale_xy, _interior_scale, _sq3_eval, _squash_beats,
                                 TOL_VOL, MIN_ANISO)

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
MIN_SHEAR = 5.0     # 度,base squash 峰值 |shearX| 下限


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


def _squash_depth(anim):
    """該 anim 全 bone 的峰非均勻 |scaleX−scaleY|(=擠壓深度;無 scale 回 0)。"""
    depths = [max((abs(sx - sy) for (sx, sy) in _scale_xy(ch)), default=0.0)
              for ch in anim.get("bones", {}).values()]
    return max(depths, default=0.0)


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
    t1 = {"squash_beats": squash_beats, "base_no_dualchannel": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dualchannel": [], "misrouted": [], "base_changed": []}
    for sq in squash_beats:
        # base squash 須同時有 shear(峰≥MIN_SHEAR)與 scale(非均勻)
        if _shear_peak(base[sq]) < MIN_SHEAR or _squash_depth(base[sq]) < MIN_ANISO:
            t1["base_no_dualchannel"].append(sq)
        for t in TIERS:
            vk = "{}__{}".format(sq, t)
            an = anims.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            if not an.get("bones"):
                t1["no_bones"].append(vk)
            dual = any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values())
            if not dual:
                t1["variant_no_dualchannel"].append(vk)
            if G.beat_category(vk) != "squash":
                t1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    t1_pass = (bool(squash_beats) and not any(t1[k] for k in
               ["base_no_dualchannel", "missing", "not_finite", "no_bones",
                "variant_no_dualchannel", "misrouted", "base_changed"]))
    R["ST1_present_backward_compat"] = {**t1, "pass": t1_pass}

    # ---- ST2 crux: dual-channel (squash depth + shear peak) monotone across tiers ----
    t2 = {"beats": {}, "fail_depth_mono": [], "fail_shear_mono": [], "fail_base": []}
    for sq in squash_beats:
        depths = [_squash_depth(anims["{}__{}".format(sq, t)]) for t in TIERS]
        shears = [_shear_peak(anims["{}__{}".format(sq, t)]) for t in TIERS]
        base_depth, base_shear = _squash_depth(base[sq]), _shear_peak(base[sq])
        depth_mono, shear_mono = _is_strict_inc(depths), _is_strict_inc(shears)
        super_eq = abs(depths[0] - base_depth) <= 1e-4 and abs(shears[0] - base_shear) <= 1e-4
        t2["beats"][sq] = {"squash_depth": [round(d, 4) for d in depths],
                           "shear_peak": [round(s, 3) for s in shears],
                           "base_depth": round(base_depth, 4), "base_shear": round(base_shear, 3),
                           "depth_mono": depth_mono, "shear_mono": shear_mono, "super_eq_base": super_eq}
        if not depth_mono:
            t2["fail_depth_mono"].append(sq)
        if not shear_mono:
            t2["fail_shear_mono"].append(sq)
        if not super_eq:
            t2["fail_base"].append(sq)
    t2_pass = (bool(t2["beats"]) and not t2["fail_depth_mono"]
               and not t2["fail_shear_mono"] and not t2["fail_base"])
    R["ST2_dual_channel_monotone"] = {**t2, "pass": t2_pass}

    # ---- ST3 crux: volume conservation + non-uniform + damped coupling preserved per tier ----
    t3 = {"detail": {}, "fail_volume": [], "fail_aniso": [], "fail_damped": []}
    for sq in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(sq, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior:
                    continue
                vol_ok, aniso_ok, damp_ok, det = _sq3_eval(interior)
                key = "{}__{}::{}".format(sq, t, bn)
                t3["detail"][key] = det
                if not vol_ok:
                    t3["fail_volume"].append(key)
                if not aniso_ok:
                    t3["fail_aniso"].append(key)
                if not damp_ok:
                    t3["fail_damped"].append(key)
    t3_pass = (bool(t3["detail"]) and not t3["fail_volume"]
               and not t3["fail_aniso"] and not t3["fail_damped"])
    R["ST3_volume_conserved_per_tier"] = {**t3, "pass": t3_pass}

    # ---- ST4 shear damped-oscillation signature + scale identity endpoints per tier ----
    t4 = {"bad_shear_ends": [], "few_sign_changes": [], "not_damped": [], "bad_scale_ends": [], "detail": {}}
    for sq in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(sq, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                xy = _scale_xy(ch)
                if not sx:
                    continue
                key = "{}__{}::{}".format(sq, t, bn)
                sh_ends = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                nsc = _sign_changes_zero(sx)
                damp = _extrema_mags_decreasing(sx)
                sc_ends = (not xy) or (abs(xy[0][0] - 1.0) < 1e-4 and abs(xy[0][1] - 1.0) < 1e-4
                                       and abs(xy[-1][0] - 1.0) < 1e-4 and abs(xy[-1][1] - 1.0) < 1e-4)
                t4["detail"][key] = {"n_sign_changes": nsc, "damped": damp, "scale_ends_ident": sc_ends}
                if not sh_ends:
                    t4["bad_shear_ends"].append(key)
                if nsc < 3:
                    t4["few_sign_changes"].append(key)
                if not damp:
                    t4["not_damped"].append(key)
                if not sc_ends:
                    t4["bad_scale_ends"].append(key)
    t4_pass = (bool(t4["detail"]) and not t4["bad_shear_ends"] and not t4["few_sign_changes"]
               and not t4["not_damped"] and not t4["bad_scale_ends"])
    R["ST4_shear_damped_per_tier"] = {**t4, "pass": t4_pass}

    # ---- ST5 shear isolated to shear-emitters (incl. all tier variants) ----
    t5 = {"leaked": []}
    for nm, an in anims.items():
        base_name = nm.split("__")[0]
        if G.beat_category(base_name) in TV.SHEAR_CATS:
            continue
        sheared = [bn for bn, ch in an.get("bones", {}).items() if _shear_x(ch)]
        if sheared:
            t5["leaked"].append((nm, sheared))
    R["ST5_shear_isolated"] = {**t5, "pass": not t5["leaked"]}

    # ---- ST6 negative controls ----
    t6 = {}
    # (a) 平增益守衛:全 1.0 → 深度/shear 遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for sq in squash_beats:
        depths = [_squash_depth(flat_anims["{}__{}".format(sq, t)]) for t in TIERS]
        shears = [_shear_peak(flat_anims["{}__{}".format(sq, t)]) for t in TIERS]
        if _is_strict_inc(depths) or _is_strict_inc(shears):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(sq, t)], sort_keys=True) != \
               json.dumps(base[sq], sort_keys=True):
                flat_base_diff.append("{}__{}".format(sq, t))
    t6["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) crux 天真-amplify 守衛:對真實 squash 極值幀施單軸 _amp_scale(非耦合)→ 破壞體積守恆。
    #     取一支 base squash bone 的內部極值,g=Legend,證 |prod-1| 遠超 TOL_VOL(耦合則 ≤TOL_VOL)。
    g_leg = gains["Legend"]
    naive_worst, coupled_worst = 0.0, 0.0
    sample_bone = None
    for sq in squash_beats:
        for bn, ch in base[sq].get("bones", {}).items():
            interior = _interior_scale(ch)
            if not interior:
                continue
            sample_bone = "{}::{}".format(sq, bn)
            for (sx, sy) in interior:
                # 單軸(舊 _amp_scale,各軸獨立):scaleY<1 樓地板不動 → 破壞守恆
                nx, ny = TV._amp_scale(sx, g_leg), TV._amp_scale(sy, g_leg)
                naive_worst = max(naive_worst, abs(nx * ny - 1.0))
                # 耦合(新):守恆
                cx, cy = TV._amp_scale_coupled(sx, g_leg)
                coupled_worst = max(coupled_worst, abs(cx * cy - 1.0))
            break
        if sample_bone:
            break
    t6["b_naive_amplify_breaks_volume"] = {
        "sample_bone": sample_bone, "gain": g_leg,
        "naive_worst_vol_err": round(naive_worst, 6), "coupled_worst_vol_err": round(coupled_worst, 8),
        "pass": naive_worst > TOL_VOL and coupled_worst <= TOL_VOL}
    # (c) 耦合單元測:amplify_bone_tl coupled vs 單軸 對同一 squash bone
    sq_bone = {"scale": [{"time": 0.0, "x": 1.0, "y": 1.0},
                         {"time": 0.4, "x": 1.16, "y": round(1.0 / 1.16, 4)},
                         {"time": 0.8, "x": 1.0, "y": 1.0}],
               "shear": [{"time": 0.0, "x": 0.0, "y": 0.0}, {"time": 0.4, "x": 16.0, "y": 0.0},
                         {"time": 0.8, "x": 0.0, "y": 0.0}]}
    g = 2.0
    a_cp = TV.amplify_bone_tl(sq_bone, g, coupled_scale=True)
    a_nc = TV.amplify_bone_tl(sq_bone, g, coupled_scale=False)
    cp_mid = a_cp["scale"][1]
    nc_mid = a_nc["scale"][1]
    cp_vol_ok = abs(cp_mid["x"] * cp_mid["y"] - 1.0) <= 1e-4          # 耦合守恆
    cp_amplified = cp_mid["x"] > 1.16 + 1e-6                           # 擠壓被放大
    cp_ends_ident = (abs(a_cp["scale"][0]["x"] - 1.0) < 1e-9 and abs(a_cp["scale"][0]["y"] - 1.0) < 1e-9
                     and abs(a_cp["scale"][-1]["x"] - 1.0) < 1e-9 and abs(a_cp["scale"][-1]["y"] - 1.0) < 1e-9)
    nc_vol_broken = abs(nc_mid["x"] * nc_mid["y"] - 1.0) > TOL_VOL     # 單軸破壞守恆
    cp_shear_amp = abs(a_cp["shear"][1]["x"] - g * 16.0) <= 1e-6       # shear v'=g*v(兩路徑同)
    t6["c_coupled_unit"] = {"coupled_volume_ok": cp_vol_ok, "coupled_amplified": cp_amplified,
                            "coupled_ends_identity": cp_ends_ident, "noncoupled_volume_broken": nc_vol_broken,
                            "coupled_shear_amplified": cp_shear_amp,
                            "pass": cp_vol_ok and cp_amplified and cp_ends_ident
                                    and nc_vol_broken and cp_shear_amp}
    R["ST6_neg_control"] = {**t6, "pass": all(v["pass"] for v in t6.values())}

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
        for k in ["ST1_present_backward_compat", "ST2_dual_channel_monotone",
                  "ST3_volume_conserved_per_tier", "ST4_shear_damped_per_tier",
                  "ST5_shear_isolated", "ST6_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("ST2 squash depth / shear peak per tier {}:".format(TIERS))
        for sq, d in R["ST2_dual_channel_monotone"]["beats"].items():
            print("  {:10s} depth {}  shear {}".format(sq, d["squash_depth"], d["shear_peak"]))
        b = R["ST6_neg_control"]["b_naive_amplify_breaks_volume"]
        print("ST6b naive vol-err {} vs coupled {} (TOL_VOL {})".format(
            b["naive_worst_vol_err"], b["coupled_worst_vol_err"], TOL_VOL))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
