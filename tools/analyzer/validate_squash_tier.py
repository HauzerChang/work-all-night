#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

candidate (J) 讓主秀 beat 依檔位**幅度**差異化,(G-4'') 把 wobble 的 shear 峰接上檔位放大;
但 (G-4'''') 新生成的 squash(斜拉果凍擠壓)幅度軸除 shear 外還有**體積守恆的耦合 scale 對**
(scaleX·scaleY==1、scaleX≠scaleY)。天真 `_amp_scale`(只放大 identity 上方、下方樓地板不動)會把
scaleX(>1)放大而 scaleY(<1)保留 → scaleX·scaleY≠1 **破壞體積守恆** —— 這正是 (G-4'''') 當時把
squash 留在 `MAIN_SHOW_CATS` 之外的 honest boundary。本次(G-4''''')以**耦合 amplify**
(`_amp_scale_coupled`:q=scaleX−1 隨檔位放大 → scaleX'=1+g·q、scaleY'=1/scaleX')把 squash 接上檔位:
擠壓幅度隨檔位嚴格遞增,而**放大後每幀仍 scaleX'·scaleY'==1**(體積守恆保形)。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位擠壓愈大且仍體積守恆」是可量化的檔位簽章,用負對照(平增益 + 天真非耦合 amplify)證鑑別力。
從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  ST1 present + backward-compat  : squash base beat 有 shear+scale;每檔位 `squash__{tier}` 皆產出、finite、
                                  有 bone、≥1 bone 同時帶 shear 與 scale、名經 `beat_category` 仍路由回 squash;
                                  **base 逐位元不變**(帶/不帶 tier_gains 的 base squash + In/Loop/Out 相同)。
  ST2 crux — squash amp monotone: 各檔位 squash 的峰擠壓量 |scaleX−1|(及 |scaleX−scaleY| 非均勻峰)
                                  Super<Mega<Omg<Legend **嚴格遞增**(端到端經 build_animations 量),
                                  shear 峰亦嚴格遞增(兩通道皆放大),且首檔(Super,g=1)峰 == base 峰。
  ST3 crux — volume preserved    : **每個檔位**的 squash bone,每個內部擠壓極值幀 (a)|scaleX·scaleY−1|≤TOL_VOL
                                  (面積守恆);(b)|scaleX−scaleY|≥MIN_ANISO(非均勻=真擠壓);
                                  (c)擠壓幅度 |scaleX−1| 隨極值嚴格遞減(阻尼耦合)。→ 耦合 amplify 於**放大後**仍守恆。
  ST4 signature/interface per tier: **每個檔位**的 squash bone (a)shear 首尾 0、scale 首尾 (1,1)(identity 介面,
                                  可插 Loop);(b)shear 繞 0 變號 ≥3 且相繼極值嚴格遞減(阻尼振盪保形)。
  ST5 neg-control                : (a) **平增益守衛**:增益階梯全 1.0 → ST2 遞增 FALSE(證閘測遞增非恆真)
                                  且各檔位峰 == base 峰;
                                  (b) **耦合守衛(crux)**:對真實 squash Legend 變體,耦合 amplify 守恆
                                  (max|prod−1|≤TOL_VOL),而天真 `_amp_scale`(非耦合)**破壞守恆**
                                  (max|prod−1|>TOL_VOL)→ 證「耦合」是本能力的 load-bearing 差異、閘可信;
                                  (c) **耦合單元測**:`_amp_scale_coupled` 對 (1,1)→(1,1)(identity 保持)、
                                  對守恆對放大後 scaleX'·scaleY'==1、且 |scaleX'−1| 隨 g 單調遞增。

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
# 復用 G-4' 的阻尼簽章判準 + G-4'''' 的體積守恆判準,確保與 shear-gen / squash-gen 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import (_scale_xy, _interior_scale, _sq3_eval,
                                 TOL_VOL, MIN_ANISO, MIN_SHEAR)

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


def _stretch_peak(anim):
    """該 anim 全 bone 內部擠壓極值的峰 |scaleX−1|(無 scale 回 0)。"""
    peaks = []
    for ch in anim.get("bones", {}).values():
        interior = _interior_scale(ch)
        if interior:
            peaks.append(max(abs(sx - 1.0) for (sx, sy) in interior))
    return max(peaks, default=0.0)


def _aniso_peak(anim):
    """該 anim 全 bone 內部擠壓極值的峰 |scaleX−scaleY|(無 scale 回 0)。"""
    peaks = []
    for ch in anim.get("bones", {}).values():
        interior = _interior_scale(ch)
        if interior:
            peaks.append(max(abs(sx - sy) for (sx, sy) in interior))
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
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": []}
    for qb in squash_beats:
        # base 有 shear + scale 雙通道
        if _shear_peak(base[qb]) < MIN_SHEAR or _aniso_peak(base[qb]) < MIN_ANISO:
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
            # ≥1 bone **同時**帶 shear 與 scale(耦合節拍)
            if not any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values()):
                t1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                t1["misrouted"].append((vk, G.beat_category(vk)))
    # base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    t1_pass = (bool(squash_beats) and not any(t1[k] for k in
               ["base_no_dual", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed"]))
    R["ST1_present_backward_compat"] = {**t1, "pass": t1_pass}

    # ---- ST2 crux: squash amplitude (+shear) monotone across tiers ----
    t2 = {"beats": {}, "fail_stretch_mono": [], "fail_aniso_mono": [],
          "fail_shear_mono": [], "fail_base": []}
    for qb in squash_beats:
        stretch = [_stretch_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        aniso = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        shear = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_stretch = _stretch_peak(base[qb])
        t2["beats"][qb] = {"stretch_peaks": [round(p, 4) for p in stretch],
                           "aniso_peaks": [round(p, 4) for p in aniso],
                           "shear_peaks": [round(p, 3) for p in shear],
                           "base_stretch": round(base_stretch, 4)}
        if not _is_strict_inc(stretch):
            t2["fail_stretch_mono"].append(qb)
        if not _is_strict_inc(aniso):
            t2["fail_aniso_mono"].append(qb)
        if not _is_strict_inc(shear):
            t2["fail_shear_mono"].append(qb)
        if abs(stretch[0] - base_stretch) > 1e-4:      # Super g=1 → 同 base
            t2["fail_base"].append(qb)
    t2_pass = (bool(t2["beats"]) and not t2["fail_stretch_mono"] and not t2["fail_aniso_mono"]
               and not t2["fail_shear_mono"] and not t2["fail_base"])
    R["ST2_squash_amp_monotone"] = {**t2, "pass": t2_pass}

    # ---- ST3 crux: volume conservation preserved per tier (after amplify) ----
    t3 = {"bad_volume": [], "bad_aniso": [], "not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior:
                    continue
                vol_ok, aniso_ok, damp_ok, det = _sq3_eval(interior)
                key = "{}__{}::{}".format(qb, t, bn)
                t3["detail"][key] = det
                if not vol_ok:
                    t3["bad_volume"].append(key)
                if not aniso_ok:
                    t3["bad_aniso"].append(key)
                if not damp_ok:
                    t3["not_damped"].append(key)
    t3_pass = (bool(t3["detail"]) and not t3["bad_volume"]
               and not t3["bad_aniso"] and not t3["not_damped"])
    R["ST3_volume_preserved_per_tier"] = {**t3, "pass": t3_pass}

    # ---- ST4 signature/interface preserved per tier ----
    t4 = {"bad_shear_ends": [], "bad_scale_ends": [], "few_sign_changes": [],
          "not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                sc = _scale_xy(ch)
                if not sx and not sc:
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                shear_ends = (not sx) or (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6)
                scale_ends = (not sc) or (abs(sc[0][0] - 1.0) < 1e-6 and abs(sc[0][1] - 1.0) < 1e-6
                                          and abs(sc[-1][0] - 1.0) < 1e-6 and abs(sc[-1][1] - 1.0) < 1e-6)
                nsc = _sign_changes_zero(sx) if sx else 0
                damp = _extrema_mags_decreasing(sx) if sx else True
                t4["detail"][key] = {"n_sign_changes": nsc, "damped": damp}
                if not shear_ends:
                    t4["bad_shear_ends"].append(key)
                if not scale_ends:
                    t4["bad_scale_ends"].append(key)
                if sx and nsc < 3:
                    t4["few_sign_changes"].append(key)
                if sx and not damp:
                    t4["not_damped"].append(key)
    t4_pass = (bool(t4["detail"]) and not t4["bad_shear_ends"] and not t4["bad_scale_ends"]
               and not t4["few_sign_changes"] and not t4["not_damped"])
    R["ST4_signature_interface_per_tier"] = {**t4, "pass": t4_pass}

    # ---- ST5 negative controls ----
    t5 = {}
    # (a) 平增益守衛:全 1.0 → 峰不遞增且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for qb in squash_beats:
        stretch = [_stretch_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(stretch):
            any_mono_flat = True
        base_s = _stretch_peak(base[qb])
        for i, t in enumerate(TIERS):
            if abs(stretch[i] - base_s) > 1e-4:
                flat_base_diff.append("{}__{}".format(qb, t))
    t5["a_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_peaks_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    # (b) 耦合守衛(crux):真實 squash Legend 變體,耦合守恆 vs 天真非耦合破壞守恆
    g = gains["Legend"]
    coupled_max, naive_max = 0.0, 0.0
    for qb in squash_beats:
        for bn, ch in base[qb].get("bones", {}).items():
            if not _scale_xy(ch):
                continue
            a_coupled = TV.amplify_bone_tl(ch, g, coupled=True)
            a_naive = TV.amplify_bone_tl(ch, g, coupled=False)
            for f in _interior_scale(a_coupled):
                coupled_max = max(coupled_max, abs(f[0] * f[1] - 1.0))
            for f in _interior_scale(a_naive):
                naive_max = max(naive_max, abs(f[0] * f[1] - 1.0))
    t5["b_coupling_guard"] = {"coupled_max_vol_dev": round(coupled_max, 6),
                              "naive_max_vol_dev": round(naive_max, 6),
                              "pass": coupled_max <= TOL_VOL and naive_max > TOL_VOL}
    # (c) 耦合單元測:identity 保持 / 放大後守恆 / |scaleX'−1| 隨 g 單調
    idxp, idyp = TV._amp_scale_coupled(1.0, 1.0, 2.1)
    ident_ok = abs(idxp - 1.0) < 1e-9 and abs(idyp - 1.0) < 1e-9
    sx0, sy0 = 1.14, 1.0 / 1.14   # 體積守恆對
    vol_after = []
    stretch_by_g = []
    for gg in [1.0, 1.5, 2.0, 2.5]:
        xp, yp = TV._amp_scale_coupled(sx0, sy0, gg)
        vol_after.append(abs(xp * yp - 1.0))
        stretch_by_g.append(abs(xp - 1.0))
    vol_ok = all(v < 1e-9 for v in vol_after)
    mono_ok = _is_strict_inc(stretch_by_g)
    t5["c_coupled_unit"] = {"identity_fixed": ident_ok, "volume_after": [round(v, 9) for v in vol_after],
                            "stretch_by_g": [round(s, 6) for s in stretch_by_g],
                            "pass": ident_ok and vol_ok and mono_ok}
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
        for k in ["ST1_present_backward_compat", "ST2_squash_amp_monotone",
                  "ST3_volume_preserved_per_tier", "ST4_signature_interface_per_tier",
                  "ST5_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("ST2 stretch/aniso/shear peaks per tier {}:".format(TIERS))
        for qb, d in R["ST2_squash_amp_monotone"]["beats"].items():
            print("  {:8s} stretch {} aniso {} shear {}".format(
                qb, d["stretch_peaks"], d["aniso_peaks"], d["shear_peaks"]))
        b = R["ST5_neg_control"]["b_coupling_guard"]
        print("ST5(b) coupled vol dev {} vs naive {} (TOL_VOL {})".format(
            b["coupled_max_vol_dev"], b["naive_max_vol_dev"], TOL_VOL))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
