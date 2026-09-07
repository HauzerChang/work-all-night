#!/usr/bin/env python3
"""candidate (J) 整合閘 — 檔位(tier)幅度差異化已接進生成器,
`build_spine --animate --tier-variants --genre slot_bigwin` 直接輸出每檔位主秀變體
(`Super_<beat>` … `Legend_<beat>`),**愈高檔位幅度愈大**,且每檔位仍保 setup identity 介面、
各 beat 結構簽章不變(只放大幅度,不改種類)。

與既有閘的分工(補的缺口):
  - `validate_beat_templates`(0f)/`validate_more_beats`(0g)/`validate_cascade`(0h):驗**單一幅度**
    下各主秀 beat 的結構簽章(hit/reveal/combo/charge/cascade),**不涉檔位**。
  - `validate_priors_beats`(E)/`_combo_charge`(H)/`_cascade`(I):驗這些 beat 從**先驗庫**接上生成器。
  - 本閘:證 slot_bigwin 宣告的 tiers=[Super,Mega,Omg,Legend] **真的影響生成**(先前只是 metadata,
    所有檔位共用同一組幅度)。從 **genre 先驗庫** → `build_storyboard`(真實 robot 拆件 role/件序)
    → **真實 `build_spine` 骨架** → `build_animations(tier_gains)`,量測各檔位主秀變體的**真峰幅度**
    是否依檔位嚴格遞增,同時**介面契約**與**結構簽章**逐檔位守恆。這是「模板/metadata 就緒 ≠ 生成器
    接上」在檔位維度的補上:檔位標籤要真的驅動幅度,需生成器把 gain threading 到主秀節拍。

設計(gain 只放大越過 identity 的量):`_apply_gain` 對 scale 的 overshoot(>1)`v→1+gain*(v-1)`、
rotate/translate 偏移 ×gain,**不動 alpha**。故 gain=1.0 逐值不變(首檔 Super==無檔位=回歸安全),
squash/collapse/settle 下衝(≤1)保持 → 不出現負 scale、首尾 identity/collapsed 介面守恆;
「峰時刻」「符號變化數」「蓄力佔比」等**時間性/次數性簽章**皆與幅度解耦 → 逐檔位不變。

真值界定同 0f/0g/0h:主秀運動無唯一正解(先驗手感),閘驗**客觀結構**(幅度依檔位遞增 + 介面 +
簽章守恆),非美感;檔位 gain 排程(Super=1.0<Mega<Omg<Legend)為先驗提案。

  J1 present+monotone : 每主秀 beat×每件,`Super/Mega/Omg/Legend` 變體的真峰 scale **嚴格遞增**,
                        且每檔位真峰 ≥ 門檻(仍是真主秀,泛用微幅達不到)。
  J2 interface契約守恆 : 每檔位變體皆**尾** setup identity(alpha=1,Loop 可接);非 collapse 起手的
                        beat(hit/combo/charge/cascade)**首**亦 identity(可插 Loop 間)。放大不破介面。
  J3 結構簽章守恆     : 每檔位變體仍具該 beat 的**判別簽章**(hit=反向預備+阻尼回擺;combo=遞增峰 ≥3;
                        charge=蓄力佔比 ≥門檻+squash floor;cascade=各件峰時刻依件序遞增+散佈;
                        reveal=collapse 起手+真峰)→ 證放大只改幅度不改種類。
  J4 negative control : (a) In/Loop/Out 等非主秀 beat **不產**檔位變體(跨檔位共用進退場);
                        (b) **平坦 gain**(全檔位=1.0)→ 各檔位真峰**相等**(證遞增來自 gain 排程非管線);
                        (c) tier_gains=None 或首檔 gain=1.0 → 與無檔位輸出**逐值一致**(回歸)。
  J5 gating+coverage  : 無 tier_gains 的 genre(slot_reveal,tiers=None → tier_gains 回 None)**不產**
                        檔位變體(feature 正確 gated);validate_priors 覆蓋率仍 ==1.0(檔位變體非 beat,
                        不擾動覆蓋)。

用法:
  python3 validate_tier_variants.py            # 摘要
  python3 validate_tier_variants.py --json     # 完整 JSON
  python3 validate_tier_variants.py --figure   # 另存 knowledge/figures/s1_tier_variants.png
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import genre_priors as GP
import validate_priors as VP
from analyze_target import analyze
# 復用既有各 beat 的結構簽章判準,確保與 0f/0g/0h/(E/H/I) 完全一致
from validate_more_beats import (series, impact_peaks, has_combo_signature,
                                 has_charge_signature)
from validate_beat_templates import _hit_signature
from validate_cascade import has_cascade_signature

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
PEAK_THR = 1.12
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
# 主秀 base beat → 路由類別(用於挑結構簽章判準)
_BEAT_CAT = {"burst": "reveal", "hit": "hit", "combo": "combo",
             "charge": "charge", "cascade": "cascade"}


def _skeleton():
    import build_spine
    out = "/tmp/tier_variants_skel"
    build_spine.build(PSD, out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(PSD, genre)["3_motion_storyboard"]


def _part_order(skel, sb):
    bone_names = {b["name"] for b in skel["bones"]}
    order = []
    for pe in sb["beats"][0]["parts"]:
        bn = "b_" + G.safe(pe["part"])
        if bn in bone_names:
            order.append(bn)
    return order


def _is_ident(bd, tol=1e-4):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _clip_peak_per_bone(anim):
    return {b: round(max(series(anim, b)), 4) for b in anim.get("bones", {})}


def _has_signature(base_beat, anim, order):
    cat = _BEAT_CAT[base_beat]
    if cat == "hit":
        return _hit_signature(anim)
    if cat == "combo":
        return has_combo_signature(anim)
    if cat == "charge":
        return has_charge_signature(anim)
    if cat == "cascade":
        return has_cascade_signature(anim, order)
    if cat == "reveal":
        # burst→reveal:collapse 起手(峰前有真塌陷)+ 真峰
        for b in anim.get("bones", {}):
            v = series(anim, b)
            pk = max(range(len(v)), key=lambda i: v[i])
            if max(v) < PEAK_THR or not (pk > 0 and min(v[:pk]) <= 0.1):
                return False
        return len(anim.get("bones", {})) > 0
    return False


def _tiered_anims(skel, tier_gains):
    sb = _storyboard(GENRE)
    return G.build_animations(skel, sb, tier_gains=tier_gains), sb


# ---------------- AC ----------------
def check_j1(skel, gains):
    """每主秀 base beat × 每件:各檔位真峰嚴格遞增且皆 ≥ 門檻。"""
    anims, sb = _tiered_anims(skel, gains)
    tiers = list(gains.keys())
    detail, ok, any_beat = {}, True, False
    for base, cat in _BEAT_CAT.items():
        if base not in anims:
            continue
        any_beat = True
        # 各檔位 per-bone 真峰
        per_tier = {t: _clip_peak_per_bone(anims[f"{t}_{base}"]) for t in tiers}
        bones = list(per_tier[tiers[0]].keys())
        rows = {}
        for bn in bones:
            seq = [per_tier[t][bn] for t in tiers]
            inc = all(seq[i] < seq[i + 1] for i in range(len(seq) - 1))
            all_peak = all(v >= PEAK_THR for v in seq)
            good = inc and all_peak
            rows[bn] = {"peaks_by_tier": dict(zip(tiers, seq)),
                        "strictly_increasing": inc, "all_ge_thr": all_peak, "pass": good}
            ok = ok and good
        detail[base] = {"cat": cat, "bones": rows}
    return ok and any_beat, detail


def check_j2(skel, gains):
    """每檔位變體:尾 identity(alpha=1);非 collapse 起手 beat 首亦 identity。"""
    anims, sb = _tiered_anims(skel, gains)
    tiers = list(gains.keys())
    detail, ok = {}, True
    for base in _BEAT_CAT:
        if base not in anims:
            continue
        # base 是否 identity 起手(用以決定要不要驗首 identity)
        b0_base = SA.sample(anims[base], 0.0)["bones"]
        base_start_ident = all(_is_ident(v) for v in b0_base.values())
        rows = {}
        for t in tiers:
            an = anims[f"{t}_{base}"]
            dur = SA.duration(an)
            bE = SA.sample(an, dur)["bones"]; sE = SA.sample(an, dur)["slots"]
            end_id = all(_is_ident(v) for v in bE.values()) and \
                all(abs(s["alpha"] - 1) <= 1e-4 for s in sE.values())
            start_ok = True
            if base_start_ident:
                b0 = SA.sample(an, 0.0)["bones"]; s0 = SA.sample(an, 0.0)["slots"]
                start_ok = all(_is_ident(v) for v in b0.values()) and \
                    all(abs(s["alpha"] - 1) <= 1e-4 for s in s0.values())
            good = end_id and start_ok
            rows[t] = {"end_identity": end_id, "start_checked": base_start_ident,
                       "start_identity": start_ok, "pass": good}
            ok = ok and good
        detail[base] = {"base_starts_identity": base_start_ident, "tiers": rows}
    return ok, detail


def check_j3(skel, gains):
    """每檔位變體仍具該 beat 的結構簽章(放大不改種類)。"""
    anims, sb = _tiered_anims(skel, gains)
    order = _part_order(skel, sb)
    tiers = list(gains.keys())
    detail, ok = {}, True
    for base in _BEAT_CAT:
        if base not in anims:
            continue
        rows = {}
        for t in tiers:
            sig = _has_signature(base, anims[f"{t}_{base}"], order)
            rows[t] = {"signature_ok": sig}
            ok = ok and sig
        detail[base] = {"cat": _BEAT_CAT[base], "tiers": rows}
    return ok, detail


def check_j4(skel, gains):
    """(a) 非主秀 beat 不產檔位變體;(b) 平坦 gain → 各檔位真峰相等;(c) 首檔=1.0 逐值同 base。"""
    anims, sb = _tiered_anims(skel, gains)
    tiers = list(gains.keys())
    # (a) In/Loop/Out 等非主秀 base beat 不得有 <tier>_<beat>
    non_main = [b["beat"] for b in sb["beats"] if G.beat_category(b["beat"]) not in G._TIER_VARYING]
    stray = [f"{t}_{nm}" for nm in non_main for t in tiers if f"{t}_{nm}" in anims]
    a_ok = len(stray) == 0

    # (b) 平坦 gain(全 1.0)→ 各主秀 beat 各檔位真峰相等
    flat = {t: 1.0 for t in tiers}
    anims_flat, _ = _tiered_anims(skel, flat)
    equal_all, flat_info = True, {}
    for base in _BEAT_CAT:
        if base not in anims_flat:
            continue
        peaks = [_clip_peak_per_bone(anims_flat[f"{t}_{base}"]) for t in tiers]
        eq = all(peaks[i] == peaks[0] for i in range(1, len(peaks)))
        flat_info[base] = {"all_tiers_equal": eq}
        equal_all = equal_all and eq

    # (c) 首檔(gain=1.0)變體 == base beat 逐值;且 tier_gains=None == base
    first = tiers[0]
    c_ok = all(anims.get(f"{first}_{base}") == anims.get(base) for base in _BEAT_CAT if base in anims)
    anims_none, _ = _tiered_anims(skel, None)
    none_ok = all(anims_none.get(b) == anims.get(b) for b in anims_none) and \
        all(G.beat_category(nm) in G._TIER_VARYING or "_" not in nm for nm in anims_none) and \
        not any(f"{t}_" in nm for nm in anims_none for t in tiers)
    detail = {"a_non_main_no_variants": {"stray_variants": stray, "pass": a_ok},
              "b_flat_gain_equal": {"per_beat": flat_info, "pass": equal_all},
              "c_first_tier_eq_base": {"first_tier": first, "pass": c_ok},
              "c_none_eq_base_only": {"pass": none_ok}}
    return a_ok and equal_all and c_ok and none_ok, detail


def check_j5(skel, repo="."):
    """(a) 無 tier_gains 的 genre(slot_reveal)不產檔位變體;(b) validate_priors 覆蓋率仍 1.0。"""
    # (a) slot_reveal: tiers=None → tier_gains 回 None → 即使傳 gains 也 gated? 用 genre 的 gains
    tg_reveal = GP.tier_gains("slot_reveal")
    sb_rev = _storyboard("slot_reveal")
    anims_rev = G.build_animations(skel, sb_rev, tier_gains=tg_reveal)
    # 無檔位變體命名(所有 anim 名 == 原 beat 名)
    beat_names = {b["beat"] for b in sb_rev["beats"]}
    no_variants = (tg_reveal is None) and all(nm in beat_names for nm in anims_rev)
    # (b) 覆蓋率
    cov_ok, cov = True, {}
    for g, prior in GP.PRIORS.items():
        if not prior.get("validated_against"):
            continue
        r = VP.validate_genre(g, prior, repo)
        good = r.get("pass") and abs(r.get("coverage", 0) - 1.0) < 1e-9
        cov[g] = {"coverage": r.get("coverage"), "pass": r.get("pass"), "ok": good}
        cov_ok = cov_ok and good
    detail = {"a_untiered_genre_no_variants": {"slot_reveal_tier_gains": tg_reveal,
                                              "n_anims": len(anims_rev), "pass": no_variants},
              "b_coverage_preserved": {"genres": cov, "pass": cov_ok}}
    return no_variants and cov_ok, detail


def run_all(repo="."):
    skel = _skeleton()
    gains = GP.tier_gains(GENRE)
    assert gains, "slot_bigwin 應有 tier_gains"
    res = {}
    res["J1_present_monotone_peak"] = check_j1(skel, gains)
    res["J2_interface_contract"] = check_j2(skel, gains)
    res["J3_signature_preserved"] = check_j3(skel, gains)
    res["J4_negative_control"] = check_j4(skel, gains)
    res["J5_gating_and_coverage"] = check_j5(skel, repo)
    overall = all(v[0] for v in res.values())
    return {"overall_pass": overall, "genre": GENRE, "tier_gains": gains,
            "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()}}


def _make_figure(skel, gains, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    anims, sb = _tiered_anims(skel, gains)
    tiers = list(gains.keys())
    order = _part_order(skel, sb)
    # 選 body bone 展示 scale 包絡(挑第一個結構件)
    bone = next((b for b in order if b != "b_光暈"), order[0])
    beats = [b for b in ["burst", "hit", "combo", "charge", "cascade"] if b in anims]
    fig, axes = plt.subplots(1, len(beats), figsize=(3.2 * len(beats), 3.4), squeeze=False)
    colors = {"Super": "#4C9", "Mega": "#39C", "Omg": "#C6C", "Legend": "#E63"}
    N = 200
    for ax, base in zip(axes[0], beats):
        for t in tiers:
            an = anims[f"{t}_{base}"]
            dur = SA.duration(an)
            ts = [dur * i / N for i in range(N + 1)]
            ys = [SA.sample(an, tt)["bones"].get(bone, {"scaleX": 1.0})["scaleX"] for tt in ts]
            ax.plot([tt / dur for tt in ts], ys, color=colors.get(t, "#888"),
                    lw=1.6, label=t)
        ax.axhline(1.0, color="#bbb", lw=0.8, ls="--")
        ax.set_title(f"{base}", fontsize=10)
        ax.set_xlabel("t (norm)", fontsize=8)
    axes[0][0].set_ylabel(f"scale ({bone})", fontsize=8)
    axes[0][-1].legend(fontsize=7, loc="upper right")
    fig.suptitle("candidate J — tier amplitude差異化:愈高檔位主秀 overshoot 愈大,首尾 identity 守恆",
                 fontsize=10)
    fig.tight_layout(rect=[0, 0, 1, 0.94])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fig.savefig(path, dpi=110)
    return path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--figure", action="store_true")
    ap.add_argument("--repo", default=".")
    a = ap.parse_args()
    report = run_all(a.repo)
    if a.figure:
        skel = _skeleton()
        p = _make_figure(skel, GP.tier_gains(GENRE), "knowledge/figures/s1_tier_variants.png")
        report["figure"] = p
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"overall_pass": report["overall_pass"], "genre": report["genre"],
                          "tier_gains": report["tier_gains"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()},
                          **({"figure": report["figure"]} if "figure" in report else {})},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
