#!/usr/bin/env python3
"""candidate (G-4''''') 自我驗收閘 — squash(shear+耦合非均勻 scale 節拍)接檔位幅度差異化(純 CPU)。

candidate (J) 讓主秀 beat 依檔位**幅度**差異化,(G-4'')把 wobble 的 **shear** 峰接上檔位增益;但
(G-4'''')新生的 squash(斜拉果凍擠壓)幅度軸是一對**體積守恆的 scale**(scaleX·scaleY≡1)+ shear,
被留在 honest boundary 未接檔位 —— 因逐軸 `_amp_scale` 只放大 identity 上方(scaleX>1 放大、scaleY<1
樓地板不動)→ 會**破壞體積守恆**。本次(G-4''''')讓 squash 併入 `MAIN_SHOW_CATS`,scale 走
**耦合 amplify**(`_amp_scale_coupled`:放大擠壓強度 q→g·q、壓縮軸取倒數)→ 擠壓**非均勻峰隨檔位嚴格
遞增**,同時**體積守恆(scaleX·scaleY==1)在每個檔位保持**,shear 峰亦隨檔位遞增、雙通道阻尼簽章保形。

真值界定同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章**(體積守恆
耦合 + 阻尼振盪)非美感;「愈高檔位擠壓愈猛」是可量化檔位簽章,用負對照證鑑別力(閘可信)。從
**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量。

AC(客觀、可量測):
  Q1 present + backward-compat  : squash base beat 雙通道;每檔位 `squash__{tier}` 皆產出、finite、有
                                 bone、≥1 bone **同時**帶 shear + scale、名經 `beat_category` 仍路由回
                                 squash;**base 逐位元不變**(帶/不帶 tier_gains 的 base + In/Loop/Out 相同)。
  Q2 crux — aniso↑ & volume-kept: 各檔位 squash 的**非均勻峰** |scaleX−scaleY| Super<Mega<Omg<Legend
                                 **嚴格遞增**,**且每檔位每極值幀 |scaleX·scaleY−1|≤TOL_VOL(體積守恆
                                 在放大後仍保持)**;首檔(Super,g=1)峰 == base 峰(向後相容)。
  Q3 dual-channel signature/tier: **每檔位**每 squash bone (a)shearX 峰隨檔位遞增;(b)shearX 首尾 0、繞 0
                                 變號 ≥3、相繼極值遞減(阻尼);(c)squash 幅度 |scaleX−1| 隨極值嚴格遞減
                                 (耦合阻尼)—— 強度隨檔位變、結構簽章逐檔保形。
  Q4 coupled-amplify necessity  : (a)**crux 守衛**:對同一 squash 對施**逐軸獨立** `_amp_scale`(舊法)→ g>1
                                 時 scaleX·scaleY 明顯偏離 1(破壞守恆)→ 證耦合 amplify 非多餘、且 Q2 的
                                 守恆判準有鑑別力;(b)**平增益守衛**:增益全 1.0 → Q2 非均勻遞增 FALSE
                                 且各檔位 squash 逐位元 == base。
  Q5 neg-control / isolation    : (a)`_amp_scale_coupled` 單元:identity(1,1)→(1,1)、g=1 原樣、g=2 對合成
                                 squash 對守恆(積≈1)且非均勻放大;(b)**耦合隔離**:等比 scale 主秀
                                 (hit,scaleX==scaleY overshoot)的檔位變體仍 scaleX==scaleY(未被誤當
                                 squash 施耦合 amplify)→ 耦合 amplify 只作用 squash。

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
# 復用 G-4' 阻尼簽章判準 + G-4'''' 的 squash scale 讀取/評估,確保與既有 shear/squash 閘完全一致
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing
from validate_squash_gen import _scale_xy, _interior_scale, _sq3_eval, TOL_VOL, MIN_ANISO

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


def _squash_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "squash"]


def _shear_peak(anim):
    peaks = [max(abs(v) for v in _shear_x(ch)) for ch in anim.get("bones", {}).values() if _shear_x(ch)]
    return max(peaks, default=0.0)


def _aniso_peak(anim):
    """該 anim 全 bone 的峰 |scaleX−scaleY|(無 scale 回 0)。"""
    peaks = [max(abs(sx - sy) for (sx, sy) in _scale_xy(ch))
             for ch in anim.get("bones", {}).values() if _scale_xy(ch)]
    return max(peaks, default=0.0)


def _volume_dev(anim):
    """該 anim 全 bone 各 squash 極值幀的最大 |scaleX·scaleY−1|(守恆偏離峰)。"""
    devs = []
    for ch in anim.get("bones", {}).values():
        for (sx, sy) in _interior_scale(ch):
            devs.append(abs(sx * sy - 1.0))
    return max(devs, default=0.0)


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

    # ---- Q1 present + backward-compat ----
    q1 = {"squash_beats": squash_beats, "base_no_dual": [], "missing": [], "not_finite": [],
          "no_bones": [], "variant_no_dual": [], "misrouted": [], "base_changed": []}
    for qb in squash_beats:
        bdual = any(_shear_x(ch) and _scale_xy(ch) for ch in base[qb].get("bones", {}).values())
        if not bdual or _shear_peak(base[qb]) < MIN_SHEAR:
            q1["base_no_dual"].append(qb)
        for t in TIERS:
            vk = "{}__{}".format(qb, t)
            an = anims.get(vk)
            if an is None:
                q1["missing"].append(vk); continue
            if not SA.all_finite(an):
                q1["not_finite"].append(vk)
            if not an.get("bones"):
                q1["no_bones"].append(vk)
            if not any(_shear_x(ch) and _scale_xy(ch) for ch in an.get("bones", {}).values()):
                q1["variant_no_dual"].append(vk)
            if G.beat_category(vk) != "squash":
                q1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            q1["base_changed"].append(k)
    q1_pass = (bool(squash_beats) and not any(q1[k] for k in
               ["base_no_dual", "missing", "not_finite", "no_bones", "variant_no_dual",
                "misrouted", "base_changed"]))
    R["Q1_present_backward_compat"] = {**q1, "pass": q1_pass}

    # ---- Q2 crux: anisotropy peak monotone AND volume conserved per tier ----
    q2 = {"beats": {}, "fail_mono": [], "fail_base": [], "fail_volume": []}
    for qb in squash_beats:
        aniso = [_aniso_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        vdev = [_volume_dev(anims["{}__{}".format(qb, t)]) for t in TIERS]
        base_aniso = _aniso_peak(base[qb])
        mono = _is_strict_inc(aniso)
        super_eq_base = abs(aniso[0] - base_aniso) <= 1e-4
        vol_ok = all(d <= TOL_VOL for d in vdev)
        q2["beats"][qb] = {"aniso_peaks": [round(a, 4) for a in aniso],
                           "base_aniso": round(base_aniso, 4),
                           "volume_dev": [round(d, 6) for d in vdev],
                           "mono": mono, "super_eq_base": super_eq_base, "volume_ok": vol_ok}
        if not mono:
            q2["fail_mono"].append(qb)
        if not super_eq_base:
            q2["fail_base"].append(qb)
        if not vol_ok:
            q2["fail_volume"].append(qb)
    q2_pass = (bool(q2["beats"]) and not q2["fail_mono"] and not q2["fail_base"]
               and not q2["fail_volume"])
    R["Q2_aniso_monotone_volume_kept"] = {**q2, "pass": q2_pass}

    # ---- Q3 dual-channel damped signature preserved per tier ----
    q3 = {"shear_peaks": {}, "fail_shear_mono": [], "bad_shear_sig": [], "bad_squash_damp": []}
    for qb in squash_beats:
        shpk = [_shear_peak(anims["{}__{}".format(qb, t)]) for t in TIERS]
        q3["shear_peaks"][qb] = [round(p, 3) for p in shpk]
        if not _is_strict_inc(shpk):
            q3["fail_shear_mono"].append(qb)
        for t in TIERS:
            an = anims["{}__{}".format(qb, t)]
            for bn, ch in an.get("bones", {}).items():
                key = "{}__{}::{}".format(qb, t, bn)
                sx = _shear_x(ch)
                if sx:
                    if not (abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                            and _sign_changes_zero(sx) >= 3 and _extrema_mags_decreasing(sx)):
                        q3["bad_shear_sig"].append(key)
                interior = _interior_scale(ch)
                if interior:
                    mag = [abs(sx_ - 1.0) for (sx_, sy_) in interior]
                    if not (len(mag) >= 2 and all(mag[i + 1] < mag[i] - 1e-9
                                                  for i in range(len(mag) - 1))):
                        q3["bad_squash_damp"].append(key)
    q3_pass = (bool(q3["shear_peaks"]) and not q3["fail_shear_mono"]
               and not q3["bad_shear_sig"] and not q3["bad_squash_damp"])
    R["Q3_dual_channel_signature_per_tier"] = {**q3, "pass": q3_pass}

    # ---- Q4 coupled-amplify necessity ----
    q4 = {}
    # (a) crux 守衛:對真實 squash 對施舊逐軸 _amp_scale → g>1 破壞守恆
    naive_dev = {}
    for qb in squash_beats:
        for bn, ch in base[qb].get("bones", {}).items():
            interior = _interior_scale(ch)
            if not interior:
                continue
            for t, g in zip(TIERS, [gains[t] for t in TIERS]):
                if g == 1.0:
                    continue
                devs = []
                for (sx, sy) in interior:
                    nx = round(TV._amp_scale(sx, g), 4)
                    ny = round(TV._amp_scale(sy, g), 4)
                    devs.append(abs(nx * ny - 1.0))
                naive_dev.setdefault(t, 0.0)
                naive_dev[t] = max(naive_dev[t], max(devs))
    naive_breaks = all(naive_dev[t] > TOL_VOL for t in naive_dev)  # 每個 g>1 檔位都破壞守恆
    q4["a_naive_breaks_volume"] = {"naive_max_volume_dev": {t: round(v, 4) for t, v in naive_dev.items()},
                                   "tol_vol": TOL_VOL, "pass": bool(naive_dev) and naive_breaks}
    # (b) 平增益守衛:全 1.0 → 非均勻不遞增 且 各檔位 == base
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat, flat_base_diff = False, []
    for qb in squash_beats:
        peaks = [_aniso_peak(flat_anims["{}__{}".format(qb, t)]) for t in TIERS]
        if _is_strict_inc(peaks):
            any_mono_flat = True
        for t in TIERS:
            if json.dumps(flat_anims["{}__{}".format(qb, t)], sort_keys=True) != \
               json.dumps(base[qb], sort_keys=True):
                flat_base_diff.append("{}__{}".format(qb, t))
    q4["b_flat_guard"] = {"flat_any_monotone": any_mono_flat, "flat_variants_ne_base": flat_base_diff,
                          "pass": (not any_mono_flat) and not flat_base_diff}
    R["Q4_coupled_amplify_necessity"] = {**q4, "pass": all(v["pass"] for v in q4.values())}

    # ---- Q5 neg-control / isolation ----
    q5 = {}
    # (a) _amp_scale_coupled 單元
    ident_ok = TV._amp_scale_coupled(1.0, 1.0, 2.0) == (1.0, 1.0)
    g1_ok = TV._amp_scale_coupled(1.16, 0.8621, 1.0) == (1.16, 0.8621)
    sx2, sy2 = TV._amp_scale_coupled(1.16, 0.8621, 2.0)
    vol2_ok = abs(sx2 * sy2 - 1.0) <= TOL_VOL
    aniso_grew = abs(sx2 - sy2) > abs(1.16 - 0.8621)
    q5["a_coupled_unit"] = {"identity": ident_ok, "g1_identity": g1_ok,
                            "g2_volume_ok": vol2_ok, "g2_aniso_grew": aniso_grew,
                            "pass": ident_ok and g1_ok and vol2_ok and aniso_grew}
    # (b) 耦合隔離:等比 scale 主秀(hit)的檔位變體仍 scaleX==scaleY(未被誤施耦合 amplify)
    #     hit 用 scale overshoot(等比,scaleX==scaleY);耦合 amplify 會把兩軸拆成 (v,1/v) → 不再相等。
    equi_leak = []
    for nm, an in anims.items():
        base_name = nm.split("__")[0]
        if "__" not in nm or G.beat_category(base_name) in TV.COUPLED_SCALE_CATS:
            continue
        for bn, ch in an.get("bones", {}).items():
            for (sx, sy) in _scale_xy(ch):
                if abs(sx - sy) > 1e-6:               # 等比通道被拆成非均勻 → 洩漏
                    equi_leak.append((nm, bn, round(sx, 4), round(sy, 4)))
                    break
    q5["b_coupled_isolated"] = {"equi_scale_leaked": equi_leak, "pass": not equi_leak}
    R["Q5_neg_control"] = {**q5, "pass": all(v["pass"] for v in q5.values())}

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
        for k in ["Q1_present_backward_compat", "Q2_aniso_monotone_volume_kept",
                  "Q3_dual_channel_signature_per_tier", "Q4_coupled_amplify_necessity",
                  "Q5_neg_control"]:
            print("{:36s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("Q2 aniso peaks per tier {}:".format(TIERS))
        for qb, d in R["Q2_aniso_monotone_volume_kept"]["beats"].items():
            print("  {:10s} aniso {}  vol_dev {}  (base {})".format(
                qb, d["aniso_peaks"], d["volume_dev"], d["base_aniso"]))
        print("Q3 shear peaks per tier:", R["Q3_dual_channel_signature_per_tier"]["shear_peaks"])
        print("Q4 naive independent amplify volume dev:",
              R["Q4_coupled_amplify_necessity"]["a_naive_breaks_volume"]["naive_max_volume_dev"])
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
