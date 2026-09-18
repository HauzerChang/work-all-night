#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear + 耦合非均勻 scale)接檔位幅度差異化,**體積守恆放大**(純 CPU)。

一路的 honest boundary:G-4''''(`validate_squash_gen.py`)讓 `gen_squash` **第一次**產出耦合的 shear +
非均勻 scale(斜拉果凍擠壓,scaleX·scaleY≡1);但當時 squash **不在** `MAIN_SHOW_CATS` —— 因為 (J) 的預設
scale 增益 `_amp_scale` 只放大 identity **上方**(scaleX>1 被放大而 scaleY<1 樓地板不動)→ 會**破壞體積守恆**
(scaleX·scaleY≫1)。於是「愈高檔位主秀愈爆」對其餘節拍都成立,唯獨斜拉擠壓的強度不隨檔位變 = 不一致。

本次(G-4''''')把 squash 併入 `MAIN_SHOW_CATS`,並讓其 scale 通道走**體積守恆 amplify**
(`tier_variants._amp_scale_vc`:兩軸取**同一指數 g** → v'=v^g ⇒ scaleX'·scaleY'=(scaleX·scaleY)^g=1^g=1),
使**擠壓強度(非均勻度)隨檔位嚴格遞增**而**面積守恆 scaleX·scaleY≡1 在每個檔位不破**;shear 峰同時隨檔位遞增
(g*v,沿用 wobble)。⇒ 這是**耦合雙通道**的檔位差異化:shear 與非均勻 scale **同時**放大,且守恆約束保持。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**;
「愈高檔位擠壓愈猛(shear+非均勻同增)且面積守恆不破」是可量化的檔位簽章,用負對照證鑑別力(閘可信)。
從**先驗庫**(slot_bigwin,squash beat)→ **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  ST1 present + backward-compat : base squash 為 dual-channel(≥1 bone 同時帶 shear+非均勻 scale);
                                 每檔位 `squash__{tier}` 皆產出、finite、有 bone、≥1 bone dual-channel、
                                 名經 `beat_category` 仍路由回 squash;帶/不帶 tier_gains 的 base(含
                                 In/Loop/Out + base squash)逐位元不變;**Super(g=1)變體逐位元 == base squash**。
  ST2 crux — 耦合雙通道遞增      : 各檔位 (a) shear 峰 |shearX| 與 (b) scale 非均勻峰 |scaleX−scaleY| **皆**
                                 Super<Mega<Omg<Legend 嚴格遞增(端到端經 build_animations 量),且 Super==base。
                                 → 證「愈高檔位擠壓愈猛」是**兩通道同增**(非只一軸)。
  ST3 crux — 體積守恆逐檔保持     : **每個檔位變體**的每個內部擠壓極值幀:(a)scaleX·scaleY≈1(|積−1|≤TOL_VOL,
                                 面積守恆**在放大後不破**);(b)非均勻 |scaleX−scaleY|≥MIN_ANISO;(c)squash 幅度
                                 |scaleX−1| 隨極值嚴格遞減(阻尼保形)。復用 G-4'''' 的 `_sq3_eval`(判準一致)。
  ST4 阻尼 shear + identity 介面 : 每檔位變體的 shear 仍 (a)首尾 0;(b)繞 0 變號 ≥3;(c)相繼極值嚴格遞減
                                 (阻尼);且 scale/shear 首尾 identity((1,1)/0)→ 可插 Loop(復用 SQ2/SQ4 判準)。
  ST5 負對照/守衛                : (a)**naive-amplify 守衛(crux)**:對 base squash 以**舊的** `_amp_scale`
                                 (只放大上方)放大 Legend 增益 → 體積守恆**破壞**(∃ 極值幀 |積−1|>TOL_VOL)→ 證
                                 體積守恆 amplify **必要**(直接展示被補上的 honest boundary);
                                 (b)**平增益守衛**:增益全 1.0 → ST2 遞增 FALSE 且各檔位逐位元 == base;
                                 (c)**體積守恆 amplify 單元測**:`amplify_bone_tl(..., volume_conserving=True)` 對
                                 合成 (1+q,1/(1+q)) 對 → 積≈1 且 g>1 時非均勻變大、shear v'=g*v;非守恆模式對同輸入
                                 → 積破壞(單元級鏡射 (a),證兩模式差異來自 scale 通道)。

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
# 復用 G-4' 的 shear 讀取與阻尼簽章判準、G-4'''' 的 scale/體積守恆判準 —— 與 shear-gen/squash-gen 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import (_scale_xy, _interior_scale, _sq3_eval, _squash_beats,
                                 _is_ident, _has_aniso_scale,
                                 MIN_SHEAR, MIN_ANISO, TOL_VOL)

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


def _shear_peak(anim):
    """該 anim 全 bone 的峰 |shearX|(無 shear 回 0)。"""
    return max((max(abs(v) for v in _shear_x(ch))
                for ch in anim.get("bones", {}).values() if _shear_x(ch)), default=0.0)


def _aniso_peak(anim):
    """該 anim 全 bone 的峰 |scaleX−scaleY|(非均勻擠壓幅度;無 scale 回 0)。"""
    return max((max((abs(sx - sy) for (sx, sy) in _scale_xy(ch)), default=0.0)
                for ch in anim.get("bones", {}).values() if _scale_xy(ch)), default=0.0)


def _is_dual(an):
    """該 anim 是否 ≥1 bone 同時帶 shear 與 scale 通道。"""
    return any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values())


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
    s1 = {"squash_beats": squash_beats, "base_not_dual": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_not_dual": [], "misrouted": [], "base_changed": [],
          "super_ne_base": []}
    for qb in squash_beats:
        if not _is_dual(base[qb]):
            s1["base_not_dual"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                s1["missing"].append(vk); continue
            if not SA.all_finite(an):
                s1["not_finite"].append(vk)
            if not an.get("bones"):
                s1["no_bones"].append(vk)
            if not _is_dual(an):
                s1["variant_not_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                s1["misrouted"].append((vk, G.beat_category(vk)))
        # Super(g=1)變體逐位元 == base squash(向後相容:v^1==v、g*v with g=1)
        if json.dumps(anims.get("{}__Super".format(qb)), sort_keys=True) != \
           json.dumps(base[qb], sort_keys=True):
            s1["super_ne_base"].append(qb)
    for k in base:                                            # base 帶/不帶 tier_gains 逐位元不變
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            s1["base_changed"].append(k)
    s1_pass = (bool(squash_beats) and not any(s1[k] for k in
               ["base_not_dual", "missing", "not_finite", "no_bones", "variant_not_dual",
                "misrouted", "base_changed", "super_ne_base"]))
    R["ST1_present_backward_compat"] = {**s1, "pass": s1_pass}

    # ---- ST2 crux: coupled dual-channel amplitude monotone across tiers ----
    s2 = {"beats": {}, "fail_shear_mono": [], "fail_aniso_mono": [], "fail_base": []}
    for qb in squash_beats:
        sh = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        an = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        sh_base, an_base = _shear_peak(base[qb]), _aniso_peak(base[qb])
        sh_mono, an_mono = _is_strict_inc(sh), _is_strict_inc(an)
        base_ok = abs(sh[0] - sh_base) <= 1e-4 and abs(an[0] - an_base) <= 1e-4
        s2["beats"][qb] = {"shear_peaks": [round(x, 3) for x in sh],
                           "aniso_peaks": [round(x, 4) for x in an],
                           "shear_mono": sh_mono, "aniso_mono": an_mono, "super_eq_base": base_ok}
        if not sh_mono:
            s2["fail_shear_mono"].append(qb)
        if not an_mono:
            s2["fail_aniso_mono"].append(qb)
        if not base_ok:
            s2["fail_base"].append(qb)
    s2_pass = (bool(s2["beats"]) and not s2["fail_shear_mono"]
               and not s2["fail_aniso_mono"] and not s2["fail_base"])
    R["ST2_coupled_dual_channel_monotone"] = {**s2, "pass": s2_pass}

    # ---- ST3 crux: volume conservation preserved per tier (reuse G-4'''' _sq3_eval) ----
    s3 = {"bad_volume": [], "no_aniso": [], "not_damped": [], "detail": {}}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                interior = _interior_scale(ch)
                if not interior or not _shear_x(ch):
                    continue
                key = "{}__{}::{}".format(qb, t, bn)
                vok, aok, dok, det = _sq3_eval(interior)
                s3["detail"][key] = det
                if not vok:
                    s3["bad_volume"].append(key)
                if not aok:
                    s3["no_aniso"].append(key)
                if not dok:
                    s3["not_damped"].append(key)
    s3_pass = (bool(s3["detail"]) and not s3["bad_volume"]
               and not s3["no_aniso"] and not s3["not_damped"])
    R["ST3_volume_preserved_per_tier"] = {**s3, "pass": s3_pass}

    # ---- ST4 damped shear + identity interface per tier ----
    s4 = {"bad_endpoints": [], "few_sign_changes": [], "not_damped": [],
          "shear_ends_nonzero": [], "scale_ends_nonident": []}
    for qb in squash_beats:
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                sx = _shear_x(ch)
                if sx:
                    key = "{}__{}::{}".format(qb, t, bn)
                    if not (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6):
                        s4["bad_endpoints"].append(key)
                    if _sign_changes_zero(sx) < 3:
                        s4["few_sign_changes"].append(key)
                    if not _extrema_mags_decreasing(sx):
                        s4["not_damped"].append(key)
                    if abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6:
                        s4["shear_ends_nonzero"].append(key)
                xy = _scale_xy(ch)
                if xy and (abs(xy[0][0] - 1.0) > 1e-6 or abs(xy[0][1] - 1.0) > 1e-6
                           or abs(xy[-1][0] - 1.0) > 1e-6 or abs(xy[-1][1] - 1.0) > 1e-6):
                    s4["scale_ends_nonident"].append("{}__{}::{}".format(qb, t, bn))
    s4_pass = not any(s4[k] for k in s4)
    R["ST4_damped_shear_identity_iface"] = {**s4, "pass": s4_pass}

    # ---- ST5 negative controls / guards ----
    s5 = {}
    # (a) naive-amplify 守衛(crux):對 base squash 以舊 `_amp_scale` 放大 Legend → 體積守恆破壞
    g_leg = gains["Legend"]
    naive_break = {"checked": 0, "broke": []}
    correct_ok = {"checked": 0, "bad": []}
    for qb in squash_beats:
        for bn, ch in base[qb].get("bones", {}).items():
            interior = _interior_scale(ch)
            if not interior:
                continue
            # 舊 naive 放大(只放大 identity 上方 → scaleY<1 樓地板不動)
            naive = [(round(TV._amp_scale(sx, g_leg), 4), round(TV._amp_scale(sy, g_leg), 4))
                     for (sx, sy) in interior]
            naive_break["checked"] += 1
            if not _sq3_eval(naive)[0]:      # volume_ok == False → 破壞(如預期)
                naive_break["broke"].append("{}::{}".format(qb, bn))
            # 對照:正確體積守恆放大應仍守恆(即實際 Legend 變體)
            vc = _interior_scale(anims["{}__Legend".format(qb)]["bones"][bn])
            correct_ok["checked"] += 1
            if not _sq3_eval(vc)[0]:
                correct_ok["bad"].append("{}::{}".format(qb, bn))
    s5["a_naive_amplify_breaks_volume"] = {
        "gain": g_leg, "n_checked": naive_break["checked"],
        "naive_broke": naive_break["broke"], "vc_correct_bad": correct_ok["bad"],
        # 守衛通過 = naive 確實破壞(每個)且 正確體積守恆放大不破壞
        "pass": (naive_break["checked"] >= 1 and len(naive_break["broke"]) == naive_break["checked"]
                 and not correct_ok["bad"])}
    # (b) 平增益守衛:全 1.0 → ST2 遞增 FALSE 且各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_ne_base = False, []
    for qb in squash_beats:
        sh = [_shear_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        an = [_aniso_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(sh) or _is_strict_inc(an):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_ne_base.append("{}__{}".format(qb, t))
    s5["b_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_ne_base,
                          "pass": (not any_mono_flat) and not flat_ne_base}
    # (c) 體積守恆 amplify 單元測:合成 (1+q, 1/(1+q)) 對
    g = 2.0
    q = [0.16, 0.08, 0.04, 0.02]
    sc_frames = ([{"time": 0.0, "x": 1.0, "y": 1.0}]
                 + [{"time": 0.1 * (i + 1), "x": round(1 + qi, 6), "y": round(1 / (1 + qi), 6)}
                    for i, qi in enumerate(q)]
                 + [{"time": 1.0, "x": 1.0, "y": 1.0}])
    bone = {"scale": [dict(f) for f in sc_frames],
            "shear": [{"time": 0.0, "x": 0.0, "y": 0.0}, {"time": 0.5, "x": 10.0, "y": 0.0},
                      {"time": 1.0, "x": 0.0, "y": 0.0}]}
    vc = TV.amplify_bone_tl(bone, g, volume_conserving=True)
    nv = TV.amplify_bone_tl(bone, g, volume_conserving=False)
    vc_int = [(f["x"], f["y"]) for f in vc["scale"][1:-1]]
    nv_int = [(f["x"], f["y"]) for f in nv["scale"][1:-1]]
    vc_vol_ok = all(abs(x * y - 1.0) <= TOL_VOL for (x, y) in vc_int)
    vc_aniso_grew = abs(vc_int[0][0] - vc_int[0][1]) > abs(1 + q[0] - 1 / (1 + q[0])) + 1e-6
    vc_shear_amp = abs(vc["shear"][1]["x"] - g * 10.0) <= 1e-6
    nv_vol_broke = any(abs(x * y - 1.0) > TOL_VOL for (x, y) in nv_int)
    vc_ident_ends = (abs(vc["scale"][0]["x"] - 1.0) <= 1e-9 and abs(vc["scale"][-1]["x"] - 1.0) <= 1e-9)
    s5["c_vc_unit"] = {"vc_volume_ok": vc_vol_ok, "vc_aniso_grew": vc_aniso_grew,
                       "vc_shear_amplified": vc_shear_amp, "naive_volume_broke": nv_vol_broke,
                       "vc_identity_ends": vc_ident_ends,
                       "pass": vc_vol_ok and vc_aniso_grew and vc_shear_amp and nv_vol_broke and vc_ident_ends}
    R["ST5_neg_control"] = {**s5, "pass": all(v["pass"] for v in s5.values())}

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
        for k in ["ST1_present_backward_compat", "ST2_coupled_dual_channel_monotone",
                  "ST3_volume_preserved_per_tier", "ST4_damped_shear_identity_iface",
                  "ST5_neg_control"]:
            print("{:36s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("ST2 peaks per tier {}:".format(TIERS))
        for qb, d in R["ST2_coupled_dual_channel_monotone"]["beats"].items():
            print("  {:8s} shear {}  aniso {}".format(qb, d["shear_peaks"], d["aniso_peaks"]))
        gr = R["ST5_neg_control"]["a_naive_amplify_breaks_volume"]
        print("ST5(a) naive-amplify broke volume on {}/{} bones (vc correct bad: {})".format(
            len(gr["naive_broke"]), gr["n_checked"], gr["vc_correct_bad"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
