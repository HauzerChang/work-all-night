#!/usr/bin/env python3
"""candidate (J) 整合閘 — 檔位(tier)主秀幅度差異化已接進產線,
`build_spine --animate --tiers`(slot_bigwin)直接輸出**依檔位單調放大**的主秀節拍
(Super < Mega < Omg < Legend)。

背景與缺口:
  `slot_bigwin` 一直宣告 tiers=[Super,Mega,Omg,Legend],但這只是 metadata —— 分鏡→動畫
  (`build_animations`)對所有檔位產出**完全相同幅度**的主秀,「檔位」形同虛設。本能力讓
  gain 政策(`genre_priors.tier_gains`,單調遞增)乘在主秀 overshoot(peak−1)上
  (`beat_templates._tier_peak`),經 `build_animations(..., tiers=True)` 把主秀節拍展開為
  `<Tier>_<beat>` 變體(Super_hit…Legend_hit),幅度隨檔位遞增 —— 又一個「模板/metadata 就緒
  ≠ 生成器接上」的補上。

真值界定同 (E)/(H)/(I):主秀運動無唯一正解(gain STEP 是手感先驗,A 類主觀留使用者),
故驗**客觀結構性質**——「幅度**單調遞增**且端點介面契約不受放大影響」——非特定數值或美感。

  T1 present+routing : tiers=True 時 slot_bigwin 主秀節拍(reveal/hit/combo/charge/cascade)
                       展開為 4 檔 × 5 節拍 = 20 支 `<Tier>_<beat>`,各經 beat_category 路由回正確
                       主秀類別、真峰 scale overshoot ≥ 門檻;框架節拍 In/Loop/Out 檔位無關(單一)。
                       且 tiers=False 產出**無**任何檔位前綴名(僅 base 名)。
  T2 interface 保留   : 放大**不得**破壞介面 —— 每檔變體的端點(t=0、t=dur:各 bone TRS + 特效 slot
                       alpha)與 base(Super)變體端點**逐一相等**(intensity 只動內部峰值);且 base
                       變體尾端為 setup identity + 特效 alpha=1(可流入 Loop)。
  T3 單調放大(crux) : 每主秀節拍、每 bone,檔位 scale 峰值**嚴格遞增** Super<Mega<Omg<Legend;
                       且 Legend/Super 的 overshoot 比 ≈ gain 比(證 gain 真的套上,非任意)。
  T4 back-compat+cov : (a) `Super_<beat>`(tiers=True)與 `<beat>`(tiers=False)**逐位元一致**
                       (Super gain=1.0);(b) validate_priors 覆蓋率仍 ==1.0(加 gain 政策不擾覆蓋)。
  T5 negative control: (a) 無 tiers 的 genre(slot_reveal,tier_gains=None)即使 tiers=True 也**不**產
                       檔位變體;(b) **等 gain**(全 1.0)會令嚴格遞增判準**失敗**(證鑑別力);
                       (c) 框架節拍 In/Loop/Out 即使 tiers=True 也不展開為檔位。

用法:
  python3 validate_priors_tiers.py            # 摘要
  python3 validate_priors_tiers.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import genre_priors as GP
import validate_priors as VP
from analyze_target import analyze

PSD = "assets/robot_parts.psd"
TIERED_GENRE = "slot_bigwin"
UNTIERED_GENRE = "slot_reveal"      # tiers=None → 負對照(a)
PEAK_THR = 1.12
RATIO_TOL = 0.03
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
MAIN_SHOW = G._MAIN_SHOW_TIERED      # {"hit","reveal","combo","charge","cascade"}


def _skeleton():
    """真實 robot 拆件 skeleton(bones 依件名;genre 不影響 bone 命名)。"""
    import build_spine
    out = "/tmp/priors_tiers_skel"
    build_spine.build(PSD, out, genre=TIERED_GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(PSD, genre)["3_motion_storyboard"]


def _is_ident(bd, tol=1e-4):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _global_peak(anim):
    """clip 全域 scale 峰值(所有 bone、scaleX 取樣最大)。"""
    mx = 1.0
    for b in anim.get("bones", {}):
        s = _series(anim, b)
        if s:
            mx = max(mx, max(s))
    return mx


def _bone_peak(anim, bone):
    s = _series(anim, bone)
    return max(s) if s else 1.0


def _series(anim, bone, key="scaleX", n=240):
    dur = SA.duration(anim)
    return [SA.sample(anim, dur * i / n)["bones"][bone][key] for i in range(n + 1)]


def _tier_names(tiers):
    return list(tiers.keys())


# ---------------- AC ----------------
def check_t1(skel):
    """展開存在+路由正確+真峰;框架節拍不展開;tiers=False 無檔位前綴。"""
    sb = _storyboard(TIERED_GENRE)
    tiers = GP.tier_gains(TIERED_GENRE)
    anims_t = G.build_animations(skel, sb, tiers=True)
    anims_f = G.build_animations(skel, sb, tiers=False)

    # 應展開的主秀 base 節拍(依 category ∈ MAIN_SHOW)
    main_beats = [b["beat"] for b in sb["beats"] if G.beat_category(b["beat"]) in MAIN_SHOW]
    frame_beats = [b["beat"] for b in sb["beats"] if G.beat_category(b["beat"]) not in MAIN_SHOW]

    rows, ok = {}, True
    for base in main_beats:
        for ti in _tier_names(tiers):
            nm = f"{ti}_{base}"
            present = nm in anims_t
            cat_ok = G.beat_category(nm) == G.beat_category(base) if present else False
            peak = round(_global_peak(anims_t[nm]), 3) if present else 0.0
            good = present and cat_ok and peak >= PEAK_THR
            rows[nm] = {"present": present, "routed_cat": G.beat_category(nm) if present else None,
                        "base_cat": G.beat_category(base), "peak": peak,
                        "peak_ok": peak >= PEAK_THR, "pass": good}
            ok = ok and good
    # 框架節拍:tiers=True 時仍單一(無檔位前綴),base 名在
    frame_ok = all(fb in anims_t and not any(f"{ti}_{fb}" in anims_t for ti in tiers)
                   for fb in frame_beats)
    # tiers=False:無任何檔位前綴名
    prefixes = tuple(f"{ti}_" for ti in tiers)
    no_prefix_default = not any(nm.startswith(prefixes) for nm in anims_f)
    good_all = ok and frame_ok and no_prefix_default
    return good_all, {"tiers": tiers, "main_beats": main_beats, "frame_beats": frame_beats,
                      "n_expanded": len(rows), "variants": rows,
                      "frame_beats_single": frame_ok, "default_has_no_tier_prefix": no_prefix_default}


def check_t2(skel):
    """放大不破壞介面:每檔變體端點 == base(Super)端點;base 尾端 setup identity + 特效 alpha=1。"""
    sb = _storyboard(TIERED_GENRE)
    tiers = GP.tier_gains(TIERED_GENRE)
    anims = G.build_animations(skel, sb, tiers=True)
    base_tier = _tier_names(tiers)[0]  # Super
    main_beats = [b["beat"] for b in sb["beats"] if G.beat_category(b["beat"]) in MAIN_SHOW]

    def endpoints(an):
        dur = SA.duration(an)
        s0, sE = SA.sample(an, 0.0), SA.sample(an, dur)
        return s0, sE

    rows, ok = {}, True
    for base in main_beats:
        b_an = anims[f"{base_tier}_{base}"]
        b0, bE = endpoints(b_an)
        # base 尾端 setup identity(bones)+ 特效 slot alpha=1
        end_id = all(_is_ident(v) for v in bE["bones"].values()) and \
            all(abs(s["alpha"] - 1) <= 1e-4 for s in bE["slots"].values())
        variant_match = True
        for ti in _tier_names(tiers):
            an = anims[f"{ti}_{base}"]
            t0, tE = endpoints(an)
            # 端點各 bone TRS 與 base 相等
            same = True
            for bn in b0["bones"]:
                for k in IDENT:
                    if abs(t0["bones"][bn][k] - b0["bones"][bn][k]) > 1e-4:
                        same = False
                    if abs(tE["bones"][bn][k] - bE["bones"][bn][k]) > 1e-4:
                        same = False
            for sn in b0["slots"]:
                if abs(t0["slots"][sn]["alpha"] - b0["slots"][sn]["alpha"]) > 1e-4:
                    same = False
                if abs(tE["slots"][sn]["alpha"] - bE["slots"][sn]["alpha"]) > 1e-4:
                    same = False
            variant_match = variant_match and same
        good = end_id and variant_match
        rows[base] = {"base_end_setup_identity": end_id,
                      "all_tier_endpoints_match_base": variant_match, "pass": good}
        ok = ok and good
    return ok, rows


def check_t3(skel):
    """crux:每主秀節拍、每 bone,檔位 scale 峰值嚴格遞增;Legend/Super overshoot 比 ≈ gain 比。"""
    sb = _storyboard(TIERED_GENRE)
    tiers = GP.tier_gains(TIERED_GENRE)
    tnames = _tier_names(tiers)
    anims = G.build_animations(skel, sb, tiers=True)
    main_beats = [b["beat"] for b in sb["beats"] if G.beat_category(b["beat"]) in MAIN_SHOW]
    gain_ratio = tiers[tnames[-1]] / tiers[tnames[0]]

    rows, ok = {}, True
    for base in main_beats:
        bones = list(anims[f"{tnames[0]}_{base}"].get("bones", {}))
        per_bone = {}
        beat_ok = len(bones) > 0
        for bn in bones:
            peaks = [round(_bone_peak(anims[f"{ti}_{base}"], bn), 4) for ti in tnames]
            strict = all(peaks[i] < peaks[i + 1] for i in range(len(peaks) - 1))
            # overshoot 比(Legend/Super)≈ gain 比
            os_super = peaks[0] - 1.0
            os_leg = peaks[-1] - 1.0
            ratio = os_leg / os_super if os_super > 1e-6 else None
            ratio_ok = ratio is not None and abs(ratio - gain_ratio) <= RATIO_TOL
            good = strict and ratio_ok
            per_bone[bn] = {"peaks_by_tier": peaks, "strict_increasing": strict,
                            "overshoot_ratio": round(ratio, 3) if ratio else None,
                            "gain_ratio": round(gain_ratio, 3), "ratio_ok": ratio_ok, "pass": good}
            beat_ok = beat_ok and good
        # 全域峰值也嚴格遞增
        gpeaks = [round(_global_peak(anims[f"{ti}_{base}"]), 4) for ti in tnames]
        gstrict = all(gpeaks[i] < gpeaks[i + 1] for i in range(len(gpeaks) - 1))
        rows[base] = {"tiers": tnames, "global_peaks": gpeaks, "global_strict": gstrict,
                      "per_bone": per_bone, "pass": beat_ok and gstrict}
        ok = ok and beat_ok and gstrict
    return ok, {"gain_ratio": round(gain_ratio, 3), "beats": rows}


def check_t4(skel, repo="."):
    """(a) Super_<beat>(tiers=True)逐位元 == <beat>(tiers=False);(b) 覆蓋率仍 1.0。"""
    sb = _storyboard(TIERED_GENRE)
    tiers = GP.tier_gains(TIERED_GENRE)
    super_t = _tier_names(tiers)[0]
    anims_t = G.build_animations(skel, sb, tiers=True)
    anims_f = G.build_animations(skel, sb, tiers=False)
    main_beats = [b["beat"] for b in sb["beats"] if G.beat_category(b["beat"]) in MAIN_SHOW]

    bit_rows, bit_ok = {}, True
    for base in main_beats:
        a = json.dumps(anims_t[f"{super_t}_{base}"], sort_keys=True, ensure_ascii=False)
        b = json.dumps(anims_f[base], sort_keys=True, ensure_ascii=False)
        eq = (a == b)
        bit_rows[base] = eq
        bit_ok = bit_ok and eq
    # 框架節拍在 tiers=True/False 也應一致(未受影響)
    frame_beats = [x["beat"] for x in sb["beats"] if G.beat_category(x["beat"]) not in MAIN_SHOW]
    for fb in frame_beats:
        eq = json.dumps(anims_t[fb], sort_keys=True, ensure_ascii=False) == \
            json.dumps(anims_f[fb], sort_keys=True, ensure_ascii=False)
        bit_rows[fb] = eq
        bit_ok = bit_ok and eq

    # 覆蓋率
    cov_rows, cov_ok = {}, True
    for g, prior in GP.PRIORS.items():
        if not prior.get("validated_against"):
            continue
        r = VP.validate_genre(g, prior, repo)
        good = r.get("pass") and abs(r.get("coverage", 0) - 1.0) < 1e-9
        cov_rows[g] = {"coverage": r.get("coverage"), "pass": r.get("pass"), "ok": good}
        cov_ok = cov_ok and good
    return bit_ok and cov_ok, {"super_bit_identical_to_default": bit_rows,
                               "coverage": cov_rows}


def check_t5(skel):
    """(a) 無 tiers 的 genre 即使 tiers=True 也不展開;(b) 等 gain → 嚴格遞增失敗(鑑別力);
    (c) 框架節拍不展開為檔位。"""
    detail = {}
    # (a) slot_reveal tier_gains=None
    sb_u = _storyboard(UNTIERED_GENRE)
    anims_u = G.build_animations(skel, sb_u, tiers=True)
    reveal_tiers = GP.tier_gains(UNTIERED_GENRE)
    # 任何 name 帶 "<X>_" 檔位前綴?slot_reveal 無 tiers → 應 0
    has_variants = any("_" in nm and nm.split("_")[0] in ("Super", "Mega", "Omg", "Legend")
                       for nm in anims_u)
    a_ok = (reveal_tiers is None) and (not has_variants)
    detail["untiered_genre_no_variants"] = {"tier_gains": reveal_tiers,
                                             "has_tier_variants": has_variants, "pass": a_ok}

    # (b) 等 gain(全 1.0)→ 峰值全相等 → 嚴格遞增為 False(判準有鑑別力)
    sb = _storyboard(TIERED_GENRE)
    tiers = GP.tier_gains(TIERED_GENRE)
    tnames = _tier_names(tiers)
    # 用等 gain map 重建
    sb_eq = dict(sb)
    sb_eq["tier_gains"] = {t: 1.0 for t in tnames}
    anims_eq = G.build_animations(skel, sb_eq, tiers=True)
    # 對每主秀節拍每 bone:等 gain 下峰值應全相等 → strict 為 False
    main_beats = [b["beat"] for b in sb["beats"] if G.beat_category(b["beat"]) in MAIN_SHOW]
    any_strict = False
    for base in main_beats:
        bones = list(anims_eq[f"{tnames[0]}_{base}"].get("bones", {}))
        for bn in bones:
            peaks = [round(_bone_peak(anims_eq[f"{ti}_{base}"], bn), 4) for ti in tnames]
            if all(peaks[i] < peaks[i + 1] for i in range(len(peaks) - 1)):
                any_strict = True
    b_ok = not any_strict  # 等 gain 下不該有任何 bone 通過嚴格遞增
    detail["equal_gain_fails_strict_increase"] = {"any_bone_strict_increasing": any_strict,
                                                   "pass": b_ok}

    # (c) 框架節拍 In/Loop/Out 即使 tiers=True 不展開
    anims_t = G.build_animations(skel, sb, tiers=True)
    frame_beats = [x["beat"] for x in sb["beats"] if G.beat_category(x["beat"]) not in MAIN_SHOW]
    frame_single = all(fb in anims_t and not any(f"{ti}_{fb}" in anims_t for ti in tnames)
                       for fb in frame_beats)
    detail["frame_beats_not_tiered"] = {"frame_beats": frame_beats, "single": frame_single,
                                        "pass": frame_single}
    return a_ok and b_ok and frame_single, detail


def run_all(repo="."):
    skel = _skeleton()
    res = {}
    res["T1_present_routing"] = check_t1(skel)
    res["T2_interface_preserved"] = check_t2(skel)
    res["T3_monotone_escalation"] = check_t3(skel)
    res["T4_backcompat_coverage"] = check_t4(skel, repo)
    res["T5_negative_control"] = check_t5(skel)
    overall = all(v[0] for v in res.values())
    return {"overall_pass": overall,
            "tiered_genre": TIERED_GENRE,
            "tier_gains": GP.tier_gains(TIERED_GENRE),
            "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--repo", default=".")
    a = ap.parse_args()
    report = run_all(a.repo)
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"overall_pass": report["overall_pass"],
                          "tier_gains": report["tier_gains"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
