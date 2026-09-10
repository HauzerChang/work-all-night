#!/usr/bin/env python3
"""candidate G-4'' 自我驗收閘 — wobble 斜拉節拍的 **shear 峰隨檔位(tier)遞增**(純 CPU)。

G-4'(`validate_shear_gen.py`)讓 `gen_wobble` 成為**第一個產出 shear 通道**的生成器,但其 honest
boundary:wobble ∉ `MAIN_SHOW_CATS` 且 `amplify_bone_tl` 不碰 shear 通道 → **檔位變體未接**(所有檔位
共用同一 shear 幅度)。這是「(J) 幅度差異化只覆蓋 scale/rotate/translate,漏了 shear」的缺口 —— 又一
「模板/宣告就緒 ≠ 生成器接上」實例(同 (E)/(H)/(I)/(J)/(J-2)/(G-4'))。

本次(G-4'')補上那一段:把 `wobble` 併入 `MAIN_SHOW_CATS`、`amplify_bone_tl` 對 **shear 通道**套幅度
增益 `v'=g*v`(對 0 對稱,同 rotate/translate)。⇒ shear 峰 = base 峰 × g 隨檔位**單調遞增**,而
**首尾 0 介面契約**與**阻尼振盪簽章**(振盪+遞減)對所有檔位保形。

真值界定同 (J):主秀運動無唯一正解(先驗手感,PROPOSAL),閘驗**客觀結構簽章非美感**——
「愈高檔位斜拉愈大」是可量化的**檔位簽章**;負對照證鑑別力(閘可信)。fixture 與 (E/H/I/J/G-4') 一致:
先驗庫(slot_bigwin,含 wobble beat)→ `analyze_target` → **真實 build_spine robot 骨架** → `build_animations`。

AC(客觀、可量測):
  TW1 present+routing+shear : 每個 wobble base beat × 每檔位皆產出 `{beat}__{tier}`,finite/有 bone、
                              ≥1 bone 帶 shear 通道且峰 |shearX| ≥ MIN_SHEAR;變體名經 `beat_category`
                              仍路由回 "wobble"(命名不破壞產線路由);base wobble beat 逐位元不變。
  TW2 crux monotone shear   : **每個 wobble beat**——max|shearX| 峰 Super<Mega<Omg<Legend **嚴格遞增**,
                              且峰比 ≈ TIER_GAIN 階梯(peak_tier ≈ peak_base × gain,誤差 < TOL_RATIO)。
  TW3 damped sig per tier    : **每個檔位**——shearX 序列(a)首尾 0;(b)繞 0 變號 ≥3;(c)相繼極值嚴格
                              遞減(阻尼)。g>0 同乘不改符號、保序 → 簽章保形。
  TW4 interface+isolation    : (a)每檔位 sample(0)/sample(dur) 各 bone 皆 setup identity(可插 Loop);
                              (b)shear 首尾 0;(c)**通道隔離**——wobble 檔位變體只動 shear(不冒出
                              scale/rotate/translate 通道);且非 wobble 主秀 beat 變體 0 bone 帶 shear。
  TW5 neg-control/guard      : (a)**平增益守衛**:增益全 1.0 → TW2 單調性 FALSE(證閘測遞增非恆真);
                              (b)**shear-blind 守衛(crux)**:若 amplify 不碰 shear(僅動 scale/rotate/
                              translate)→ 峰跨檔位**恆定** → 單調性 FALSE ⇒ 證「本次補上的 shear 處理」
                              正是讓 TW2 通過的原因(非其他通道);(c)加性:In/Loop/Out 不產 wobble 變體、
                              且 slot_reveal(tiers=None)不產任何變體。

用法:
  python3 validate_tier_wobble.py            # 摘要
  python3 validate_tier_wobble.py --json     # 完整 JSON
"""
import argparse, copy, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze
import tier_variants as TV

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
MIN_SHEAR = 5.0        # 度,base wobble 峰 |shearX| 下限
TOL_RATIO = 0.02       # 峰比 vs TIER_GAIN 相對誤差上限
MOTION_CHANS = ("scale", "rotate", "translate")   # 非 shear 的運動通道(隔離檢核)


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/tier_wobble_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _shear_x(anim, bone):
    fr = anim.get("bones", {}).get(bone, {}).get("shear")
    return [f["x"] for f in fr] if fr else []


def _shear_peak(anim):
    """max over bones of max|shearX|(無 shear 回 0)。"""
    return max((max((abs(v) for v in _shear_x(anim, b)), default=0.0)
               for b in anim.get("bones", {})), default=0.0)


def _sign_changes_zero(vals, dead=1e-6):
    sgn = [(1 if v > dead else (-1 if v < -dead else 0)) for v in vals]
    sgn = [s for s in sgn if s != 0]
    return sum(1 for i in range(1, len(sgn)) if sgn[i] != sgn[i - 1])


def _damped(vals, dead=1e-6):
    nz = [abs(v) for v in vals if abs(v) > dead]
    return len(nz) >= 2 and all(nz[i + 1] < nz[i] - 1e-9 for i in range(len(nz) - 1))


def _mono_inc(a):
    return all(a[i + 1] > a[i] + 1e-9 for i in range(len(a) - 1))


def _wobble_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "wobble"]


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)                                   # {tier: g}
    base = G.build_animations(skel, sb)                          # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)        # 帶檔位
    wobble_beats = _wobble_beats(base)
    R = {}

    # ---- TW1 present + routing + shear emitted + base unchanged ----
    t1 = {"wobble_beats": wobble_beats, "missing": [], "not_finite": [], "no_bones": [],
          "no_shear": [], "weak_peak": [], "misrouted": [], "base_changed": []}
    for beat in wobble_beats:
        for t in TIERS:
            vk = "{}__{}".format(beat, t)
            an = anims.get(vk)
            if an is None:
                t1["missing"].append(vk); continue
            if not SA.all_finite(an):
                t1["not_finite"].append(vk)
            if not an.get("bones"):
                t1["no_bones"].append(vk)
            if _shear_peak(an) <= 0.0:
                t1["no_shear"].append(vk)
            if _shear_peak(an) < MIN_SHEAR:
                t1["weak_peak"].append(vk)
            if G.beat_category(vk) != "wobble":
                t1["misrouted"].append((vk, G.beat_category(vk)))
    for k in base:                                               # base 逐位元不變
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            t1["base_changed"].append(k)
    t1_pass = (bool(wobble_beats) and not any(t1[k] for k in
               ("missing", "not_finite", "no_bones", "no_shear", "weak_peak", "misrouted", "base_changed")))
    R["TW1_present_routing_shear"] = {**t1, "pass": t1_pass}

    # ---- TW2 crux: monotone shear peak per wobble beat + ratio ≈ TIER_GAIN ----
    t2 = {"beats": {}, "fail_mono": [], "fail_ratio": []}
    for beat in wobble_beats:
        peaks = [_shear_peak(anims["{}__{}".format(beat, t)]) for t in TIERS]
        p0 = peaks[0]
        ratio = [round(p / p0, 4) if p0 > 0 else None for p in peaks]
        gain = [gains[t] for t in TIERS]
        ratio_ok = p0 > 0 and all(abs(ratio[i] - gain[i]) <= TOL_RATIO for i in range(len(TIERS)))
        mono = _mono_inc(peaks)
        t2["beats"][beat] = {"peaks": [round(p, 3) for p in peaks], "ratio": ratio,
                             "gain": gain, "mono": mono, "ratio_ok": ratio_ok}
        if not mono:
            t2["fail_mono"].append(beat)
        if not ratio_ok:
            t2["fail_ratio"].append(beat)
    t2_pass = bool(t2["beats"]) and not t2["fail_mono"] and not t2["fail_ratio"]
    R["TW2_monotone_shear_peak"] = {**t2, "pass": t2_pass}

    # ---- TW3 damped-oscillation signature preserved per tier ----
    t3 = {"bad_end": [], "few_sign": [], "not_damped": [], "detail": {}}
    for beat in wobble_beats:
        for t in TIERS:
            an = anims["{}__{}".format(beat, t)]
            for b in an.get("bones", {}):
                sx = _shear_x(an, b)
                if not sx:
                    continue
                key = "{}__{}::{}".format(beat, t, b)
                ends = abs(sx[0]) < 1e-6 and abs(sx[-1]) < 1e-6
                nsc = _sign_changes_zero(sx)
                dmp = _damped(sx)
                t3["detail"][key] = {"nsc": nsc, "damped": dmp}
                if not ends:
                    t3["bad_end"].append(key)
                if nsc < 3:
                    t3["few_sign"].append(key)
                if not dmp:
                    t3["not_damped"].append(key)
    t3_pass = (bool(t3["detail"]) and not t3["bad_end"] and not t3["few_sign"] and not t3["not_damped"])
    R["TW3_damped_per_tier"] = {**t3, "pass": t3_pass}

    # ---- TW4 interface + channel isolation ----
    t4 = {"bad_interface": [], "shear_end_nonzero": [], "leaked_motion_chan": [], "nonwobble_shear": []}
    for beat in wobble_beats:
        for t in TIERS:
            an = anims["{}__{}".format(beat, t)]
            dur = SA.duration(an)
            start = SA.sample(an, 0.0)["bones"]
            end = SA.sample(an, dur)["bones"]
            if not (all(_is_ident(v) for v in start.values()) and all(_is_ident(v) for v in end.values())):
                t4["bad_interface"].append("{}__{}".format(beat, t))
            for b, ch in an.get("bones", {}).items():
                sx = _shear_x(an, b)
                if sx and (abs(sx[0]) > 1e-6 or abs(sx[-1]) > 1e-6):
                    t4["shear_end_nonzero"].append("{}__{}::{}".format(beat, t, b))
                # 通道隔離:wobble 只該有 shear 通道,不冒出其他運動通道
                for mc in MOTION_CHANS:
                    if mc in ch:
                        t4["leaked_motion_chan"].append("{}__{}::{}::{}".format(beat, t, b, mc))
    # 非 wobble 主秀 beat 的檔位變體不該帶 shear
    for nm, an in anims.items():
        if "__" not in nm or G.beat_category(nm) == "wobble":
            continue
        if any(_shear_x(an, b) for b in an.get("bones", {})):
            t4["nonwobble_shear"].append(nm)
    t4_pass = not any(t4[k] for k in t4)
    R["TW4_interface_isolation"] = {**t4, "pass": t4_pass}

    # ---- TW5 negative controls / guards ----
    t5 = {}
    # (a) 平增益守衛:全 1.0 → 峰跨檔位恆定 → 單調性 FALSE
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    flat_mono = any(_mono_inc([_shear_peak(flat_anims["{}__{}".format(beat, t)]) for t in TIERS])
                    for beat in wobble_beats)
    t5["a_flat_guard"] = {"any_monotone_under_flat": flat_mono, "pass": not flat_mono}
    # (b) shear-blind 守衛(crux):amplify 若不碰 shear → 峰恆定 → 單調 FALSE
    def _amp_no_shear(anim, g):
        out = {"bones": {}}
        for bn, b in anim.get("bones", {}).items():
            b = copy.deepcopy(b)
            for f in b.get("scale", []):
                f["x"] = round(TV._amp_scale(f["x"], g), 4); f["y"] = round(TV._amp_scale(f["y"], g), 4)
            for f in b.get("rotate", []):
                f["angle"] = round(g * f["angle"], 3)
            for f in b.get("translate", []):
                f["x"] = round(g * f["x"], 3); f["y"] = round(g * f["y"], 3)
            out["bones"][bn] = b            # shear 通道原樣保留(不放大)
        return out
    blind_mono = False
    for beat in wobble_beats:
        peaks = [_shear_peak(_amp_no_shear(base[beat], gains[t])) for t in TIERS]
        if _mono_inc(peaks):
            blind_mono = True
    t5["b_shear_blind_guard"] = {"any_monotone_shear_blind": blind_mono, "pass": not blind_mono}
    # (c) 加性:In/Loop/Out 不產 wobble 變體;slot_reveal(tiers=None)不產變體
    staging = [k for k in anims if "__" in k and G.beat_category(k) in ("intro", "loop", "outro")]
    rv_gains = TV.gains_for("slot_reveal")
    rv_sb = _storyboard("slot_reveal")
    rv_base = G.build_animations(skel, rv_sb)
    rv_tier = G.build_animations(skel, rv_sb, tier_gains=rv_gains)
    rv_new = sorted(set(rv_tier) - set(rv_base))
    t5["c_additive"] = {"staging_variants": staging, "slot_reveal_gains": rv_gains,
                        "slot_reveal_new_keys": rv_new,
                        "pass": not staging and rv_gains is None and not rv_new}
    R["TW5_neg_control"] = {**t5, "pass": all(v["pass"] for v in t5.values())}

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
        for k in ["TW1_present_routing_shear", "TW2_monotone_shear_peak", "TW3_damped_per_tier",
                  "TW4_interface_isolation", "TW5_neg_control"]:
            print("{:28s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("TW2 shear peak by tier (Super/Mega/Omg/Legend):")
        for beat, d in R["TW2_monotone_shear_peak"]["beats"].items():
            print("  {:8s} peaks {} ratio {} gain {}".format(beat, d["peaks"], d["ratio"], d["gain"]))
        print("TW5 guards: flat_mono={} shear_blind_mono={}".format(
            R["TW5_neg_control"]["a_flat_guard"]["any_monotone_under_flat"],
            R["TW5_neg_control"]["b_shear_blind_guard"]["any_monotone_shear_blind"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
