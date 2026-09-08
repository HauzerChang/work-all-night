#!/usr/bin/env python3
"""candidate (J) 自我驗收閘 — slot_bigwin 檔位(tier)幅度差異化(純 CPU)。

`genre_priors.slot_bigwin` 宣告 `tiers=[Super,Mega,Omg,Legend]` 已久,但生成器從未用它
(所有檔位共用同一組主秀幅度)—— 又一「宣告/模板就緒 ≠ 生成器接上」的缺口。本閘從**先驗庫**
經 `analyze_target.build_storyboard` → **真實 build_spine robot 骨架** → `build_animations(..., tier_gains=…)`
端到端量測,證明:主秀 beat 依檔位**幅度單調遞增**,且**每個檔位都仍保有介面契約與結構簽章**。

真值界定同 (E)/(H)/(I):主秀運動無唯一正解(先驗手感),閘驗**客觀結構簽章非美感**;
「愈高檔位愈爆」是可量化的**檔位簽章**,用負對照證鑑別力(閘可信)。

  J1 present+routing : 每主秀 beat(cat∈MAIN_SHOW)× 每檔位皆產出 `{beat}__{tier}` 且 finite/有 bone;
                       變體名經 `beat_category` 仍路由回原類別(命名不破壞產線路由);base beat 不變。
  J2 interface IF    : **每個檔位**——hit/combo/charge/cascade 首尾 bone 皆 setup identity;
                       burst(reveal)尾 identity、首為 collapsed 樓地板(檔位無關)→ 皆可插 Loop 間。
  J3 crux monotone   : **每主秀 beat**——scaleX overshoot 幅度(與 rotate 幅度)
                       Super<Mega<Omg<Legend **嚴格遞增**(端到端經 build_animations 量)。
  J4 signature kept  : **每個檔位**——combo 仍 ≥3 遞增 impact 峰、charge 仍長蓄力(squash 非 collapse)、
                       hit 仍 anticipation+settle((scale−1) 變號 ≥3)、cascade 仍跨件峰時刻遞增散佈。
                       (幅度增益只放大 identity 上方 overshoot、不動下方樓地板與時間軸 → 簽章保形。)
  J5 neg-control     : (a) In/Loop/Out(進退場/待機)**不產**檔位變體(檔位只針對主秀);
                       (b) 無宣告 tier 的 genre(slot_reveal)→ `gains_for` 回 None → **不產**變體,
                          且 base 與無檔位呼叫逐位元相同;
                       (c) **平增益守衛**:把增益階梯全設 1.0 → J3 單調性 FALSE(證閘真的在測遞增,非恆真);
                          且 reveal collapsed 首幀 Super==Legend(下方樓地板檔位無關 → 誠實)。

用法:
  python3 validate_tier_variants.py            # 摘要
  python3 validate_tier_variants.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze
import tier_variants as TV
# 復用既有度量,確保簽章判準與 0f/0g/0h 閘完全一致
from validate_cascade import (series, sign_changes, impact_peaks, peak_time,
                              has_cascade_signature, is_strictly_increasing, SPREAD_THR)
from validate_more_beats import has_combo_signature, has_charge_signature
# candidate G-4'':wobble 併入主秀後,其結構簽章 = 阻尼 shear 振盪(非 scale overshoot)。
# 復用 validate_shear_gen 的判準,確保 J 閘與 G-4' 閘對 shear 的判定完全一致。
from validate_shear_gen import _shear_x, _sign_changes_zero, _extrema_mags_decreasing

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
PEAK_THR = 1.12
COLLAPSE_FLOOR = 0.10   # reveal 首幀 collapsed(~0.02)判準


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/tier_variants_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _part_order(skel, sb):
    bone_names = {b["name"] for b in skel["bones"]}
    order = []
    for pe in sb["beats"][0]["parts"]:
        bn = "b_" + G.safe(pe["part"])
        if bn in bone_names:
            order.append(bn)
    return order


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _scale_overshoot(anim):
    """max over bones of (max scaleX − 1) —— 主秀 overshoot 幅度(identity 上方)。"""
    bones = anim.get("bones", {})
    return max((max(series(anim, b)) - 1.0 for b in bones), default=0.0)


def _rotate_amp(anim):
    """max over bones of max|angle| —— rotate 幅度(0 對稱)。"""
    bones = anim.get("bones", {})
    amps = []
    for b in bones:
        vals = series(anim, b, key="rotate")
        amps.append(max(abs(v) for v in vals))
    return max(amps, default=0.0)


def _shear_amp(anim):
    """max over bones of max|shearX| —— shear 幅度(0 對稱;candidate G-4'')。
    shear 不經 SA.sample(其只回 rotate/x/y/scaleX/scaleY),故直接讀原始 shear 關鍵幀。"""
    amps = []
    for ch in anim.get("bones", {}).values():
        sx = _shear_x(ch)
        if sx:
            amps.append(max(abs(v) for v in sx))
    return max(amps, default=0.0)


# base beat key → 類別 → 該套哪個結構簽章
def _base_beats(anims):
    return {nm: G.beat_category(nm) for nm in anims if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    order = _part_order(skel, sb)
    gains = TV.gains_for(GENRE)
    base = G.build_animations(skel, sb)                          # tiers=None
    anims = G.build_animations(skel, sb, tier_gains=gains)        # 帶檔位
    main_beats = _base_beats(base)   # {beat: cat} for main-show only

    R = {}

    # ---- J1 present + routing + backward-compat base ----
    j1 = {"missing": [], "not_finite": [], "no_bones": [], "misrouted": [], "base_changed": []}
    for beat, cat in main_beats.items():
        for t in TIERS:
            vk = "{}__{}".format(beat, t)
            an = anims.get(vk)
            if an is None:
                j1["missing"].append(vk); continue
            if not SA.all_finite(an):
                j1["not_finite"].append(vk)
            if not an.get("bones"):
                j1["no_bones"].append(vk)
            if G.beat_category(vk) != cat:      # 命名不破壞路由
                j1["misrouted"].append((vk, G.beat_category(vk), cat))
    for k in base:                              # base(含 In/Loop/Out)逐位元不變
        if json.dumps(base[k], sort_keys=True) != json.dumps(anims.get(k), sort_keys=True):
            j1["base_changed"].append(k)
    R["J1_present_routing"] = {
        "n_main_beats": len(main_beats), "beats": sorted(main_beats),
        "n_variants_expected": len(main_beats) * len(TIERS),
        "n_variants_present": len(main_beats) * len(TIERS) - len(j1["missing"]),
        **j1,
        "pass": not any(j1[k] for k in j1)}

    # ---- J2 interface contract per tier ----
    j2 = {"bad_end": [], "bad_start": []}
    for beat, cat in main_beats.items():
        for t in TIERS:
            an = anims["{}__{}".format(beat, t)]
            dur = SA.duration(an)
            end = SA.sample(an, dur)["bones"]
            start = SA.sample(an, 0.0)["bones"]
            # 尾:所有 beat 皆須回 identity(可接 Loop)
            for b, bd in end.items():
                if not _is_ident(bd):
                    j2["bad_end"].append(("{}__{}".format(beat, t), b, round(bd["scaleX"], 3)))
            # 首:hit/combo/charge/cascade identity;burst(reveal)為 collapsed 樓地板
            if cat == "reveal":
                for b, bd in start.items():
                    if bd["scaleX"] > COLLAPSE_FLOOR:   # 應 collapsed
                        j2["bad_start"].append(("{}__{}".format(beat, t), b, round(bd["scaleX"], 3)))
            else:
                for b, bd in start.items():
                    if not _is_ident(bd):
                        j2["bad_start"].append(("{}__{}".format(beat, t), b, round(bd["scaleX"], 3)))
    R["J2_interface"] = {**j2, "pass": not j2["bad_end"] and not j2["bad_start"]}

    # ---- J3 crux: monotone amplitude per main-show beat ----
    # 通道感知(candidate G-4''):每 beat 只對其**實際存在**的幅度通道(scale overshoot / rotate /
    # shear)要求嚴格遞增,且至少一個通道存在(不可空過)。既有 scale-based beat 皆有 scale → 與舊
    # 判準等價;wobble 只有 shear → 改以 shear 峰遞增為 crux。
    j3 = {"beats": {}, "fail": []}
    for beat in main_beats:
        sc = [_scale_overshoot(anims["{}__{}".format(beat, t)]) for t in TIERS]
        ro = [_rotate_amp(anims["{}__{}".format(beat, t)]) for t in TIERS]
        sh = [_shear_amp(anims["{}__{}".format(beat, t)]) for t in TIERS]
        # 通道「存在」= 任一檔位幅度 > TOL;存在才要求嚴格遞增。
        sc_present, ro_present, sh_present = max(sc) > TOL, max(ro) > TOL, max(sh) > TOL
        sc_mono = is_strictly_increasing(sc) if sc_present else None
        ro_mono = is_strictly_increasing(ro) if ro_present else None
        sh_mono = is_strictly_increasing(sh) if sh_present else None
        present = [m for m in (sc_mono, ro_mono, sh_mono) if m is not None]
        j3["beats"][beat] = {"scale_overshoot": [round(x, 4) for x in sc],
                             "rotate_amp": [round(x, 3) for x in ro],
                             "shear_amp": [round(x, 3) for x in sh],
                             "scale_mono": sc_mono, "rotate_mono": ro_mono, "shear_mono": sh_mono}
        # 至少一通道存在,且所有存在通道皆嚴格遞增。
        if not present or not all(present):
            j3["fail"].append(beat)
    R["J3_monotone"] = {**j3, "pass": not j3["fail"]}

    # ---- J4 structural signature preserved per tier ----
    j4 = {"fail": []}
    sig_detail = {}
    for beat, cat in main_beats.items():
        per = {}
        for t in TIERS:
            an = anims["{}__{}".format(beat, t)]
            if cat == "combo":
                ok = has_combo_signature(an)
            elif cat == "charge":
                ok = has_charge_signature(an)
            elif cat == "hit":
                ok = all(sign_changes(series(an, b)) >= 3 for b in an.get("bones", {}))
            elif cat == "cascade":
                ok = has_cascade_signature(an, order, thr=SPREAD_THR)
            elif cat == "reveal":
                # burst:峰≥門檻 且 首幀 collapsed(reveal 簽章)
                ok = all(max(series(an, b)) >= PEAK_THR for b in an.get("bones", {})) and \
                     all(SA.sample(an, 0.0)["bones"][b]["scaleX"] <= COLLAPSE_FLOOR for b in an.get("bones", {}))
            elif cat == "wobble":
                # candidate G-4'':阻尼 shear 振盪簽章仍在(每 bone shearX 首尾 0、繞 0 變號 ≥3、極值遞減)
                shear_bones = [ch for ch in an.get("bones", {}).values() if _shear_x(ch)]
                ok = bool(shear_bones) and all(
                    abs(_shear_x(ch)[0]) < 1e-6 and abs(_shear_x(ch)[-1]) < 1e-6
                    and _sign_changes_zero(_shear_x(ch)) >= 3
                    and _extrema_mags_decreasing(_shear_x(ch))
                    for ch in shear_bones)
            else:
                ok = True
            per[t] = ok
            if not ok:
                j4["fail"].append(("{}__{}".format(beat, t), cat))
        sig_detail[beat] = {"cat": cat, "per_tier": per}
    R["J4_signature"] = {"detail": sig_detail, **j4, "pass": not j4["fail"]}

    # ---- J5 negative controls ----
    j5 = {}
    # (a) In/Loop/Out 不產變體
    staging_variants = [k for k in anims if "__" in k and G.beat_category(k) in ("intro", "loop", "outro")]
    j5["a_no_staging_variants"] = {"found": staging_variants, "pass": not staging_variants}
    # (b) slot_reveal(tiers=None)→ gains_for None → 不產變體 + base 相同
    rv_gains = TV.gains_for("slot_reveal")
    rv_sb = _storyboard("slot_reveal")
    rv_base = G.build_animations(skel, rv_sb)
    rv_tier = G.build_animations(skel, rv_sb, tier_gains=rv_gains)
    rv_new = sorted(set(rv_tier) - set(rv_base))
    rv_identical = all(json.dumps(rv_base[k], sort_keys=True) == json.dumps(rv_tier[k], sort_keys=True)
                       for k in rv_base)
    j5["b_no_tier_genre"] = {"gains_for_slot_reveal": rv_gains, "new_keys": rv_new,
                             "base_identical": rv_identical,
                             "pass": rv_gains is None and not rv_new and rv_identical}
    # (c) 平增益守衛:全 1.0 → J3 單調性應 FALSE(否則閘恆真);且 reveal 首幀 Super==Legend
    flat = {t: 1.0 for t in TIERS}
    flat_anims = G.build_animations(skel, sb, tier_gains=flat)
    any_mono_flat = False
    for beat in main_beats:
        sc = [_scale_overshoot(flat_anims["{}__{}".format(beat, t)]) for t in TIERS]
        if is_strictly_increasing(sc):
            any_mono_flat = True
    # reveal collapsed 首幀:Super vs Legend 相同(下方樓地板檔位無關)
    reveal_beat = next((b for b, c in main_beats.items() if c == "reveal"), None)
    floor_equal = True
    if reveal_beat:
        b0 = next(iter(anims["{}__Super".format(reveal_beat)].get("bones", {})), None)
        if b0:
            s_sup = SA.sample(anims["{}__Super".format(reveal_beat)], 0.0)["bones"][b0]["scaleX"]
            s_leg = SA.sample(anims["{}__Legend".format(reveal_beat)], 0.0)["bones"][b0]["scaleX"]
            floor_equal = abs(s_sup - s_leg) <= TOL
    j5["c_flat_guard"] = {"flat_ladder_any_monotone": any_mono_flat,
                          "reveal_floor_super_eq_legend": floor_equal,
                          "pass": (not any_mono_flat) and floor_equal}
    R["J5_neg_control"] = {**j5, "pass": all(v["pass"] for v in j5.values())}

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
        for k in ["J1_present_routing", "J2_interface", "J3_monotone", "J4_signature", "J5_neg_control"]:
            print("{:22s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("J3 amplitudes:")
        for beat, d in R["J3_monotone"]["beats"].items():
            print("  {:8s} scale_overshoot {} rotate_amp {}".format(beat, d["scale_overshoot"], d["rotate_amp"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
