#!/usr/bin/env python3
"""candidate 0g→(H) 整合閘 — combo/charge 主秀節拍已接進 genre 先驗庫,
`build_spine --animate --genre slot_bigwin` 直接輸出 combo(連擊)/charge(蓄力充能)節拍。

與既有閘的分工(補的缺口):
  - `validate_more_beats.py`(0g):用**合成 storyboard**(手寫 {"beat":"combo"},{"beat":"charge"})
    直接餵 `build_animations`,只驗**模板本身**;**不經** genre 先驗。
  - `validate_priors_beats.py`(E):同型的閘,但只涵蓋 **hit/reveal** 兩類。
  - 本閘:從 **genre 先驗庫**(`genre_priors.PRIORS`)出發,經 `analyze_target.build_storyboard`
    (真實 robot 拆件 role)→ `build_animations`,證明 **combo/charge 節拍真的會從先驗流到最終
    animations**,即 `build_spine --animate --genre slot_bigwin` 會輸出帶 combo/charge 簽章的 clip。
    這是「模板就緒 ≠ 生成器接上」在 combo/charge 上的補上(0g 模板要被觸發需先驗庫有對應 beat)。

真值界定同 0g/(E):主秀運動無唯一正解(先驗手感),故驗**客觀結構簽章**(combo=遞增 impact 峰、
charge=峰前長蓄力)+ **介面契約**(可與 In/Loop/Out 無縫串接),非美感;並以負對照證鑑別力。

  H1 present+routing : 每個宣告 combo/charge beat 的 validated genre,經先驗→build 產出的 clip 路由到
                       combo/charge 類別且有真峰 scale overshoot ≥ 門檻(泛用 Loop 微幅遠達不到)。
  H2 interface契約   : combo/charge clip 首尾皆 setup identity(可插在 Loop 循環間)。
  H3 結構簽章        : combo clip 具遞增 impact 峰 ≥3(has_combo_signature);
                       charge clip 具峰前長蓄力佔比 ≥門檻(has_charge_signature);兩簽章**互斥**。
  H4 coverage 保留   : validated genre 的 validate_priors 覆蓋率仍 ==1.0 pass(combo/charge 為
                       prior_beats_unused,加 beat 為單調操作,不擾動已驗先驗)。
  H5 negative control: (a) 無 combo/charge beat 的 genre(character_idle)產 0 個 combo/charge 類別
                       clip、無任何 clip 具 combo/charge 簽章;(b) 主秀 genre 的非 combo/charge beat
                       (In/Loop/Out/hit/reveal/burst)不得具 combo/charge 簽章。

用法:
  python3 validate_priors_combo_charge.py            # 摘要
  python3 validate_priors_combo_charge.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import genre_priors as GP
import validate_priors as VP
from analyze_target import analyze
# 復用 0g 的度量,確保簽章判準與 validate_more_beats 完全一致
from validate_more_beats import (series, has_combo_signature, has_charge_signature,
                                 impact_peaks, pre_peak_hold_frac)

PSD = "assets/robot_parts.psd"
TARGET_CATS = {"combo", "charge"}
PEAK_THR = 1.12
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}


def _skeleton():
    """建一份真實 robot 拆件 skeleton(bones 依件名;genre 不影響 bone 命名)。"""
    import build_spine
    out = "/tmp/priors_combo_charge_skel"
    build_spine.build(PSD, out, genre="slot_bigwin", animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _build_genre_anims(skel, genre):
    """genre 先驗 → storyboard(真實拆件 role)→ animations(這就是 --animate 的路徑)。"""
    sb = analyze(PSD, genre)["3_motion_storyboard"]
    return G.build_animations(skel, sb), sb


def _is_ident(bd, tol=1e-4):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _peak(anim):
    pk = 1.0
    for b in anim.get("bones", {}):
        vs = series(anim, b)
        if vs:
            pk = max(pk, max(vs))
    return pk


def target_beats(skel, genre):
    """回傳 {beat_name: (category, anim)}:該 genre 經先驗→build 後路由到 combo/charge 類別的 clip。"""
    anims, _ = _build_genre_anims(skel, genre)
    out = {}
    for nm, an in anims.items():
        cat = G.beat_category(nm)
        if cat in TARGET_CATS:
            out[nm] = (cat, an)
    return out, anims


# ---------------- AC ----------------
def check_h1(skel, genres):
    detail, ok, any_show = {}, True, False
    for g in genres:
        tb, _ = target_beats(skel, g)
        rows = {}
        for nm, (cat, an) in tb.items():
            pk = _peak(an)
            good = pk >= PEAK_THR
            rows[nm] = {"cat": cat, "peak": round(pk, 3), "pass": good}
            ok = ok and good
            any_show = True
        detail[g] = {"n_target": len(tb), "clips": rows}
    return ok and any_show, detail


def check_h2(skel, genres):
    detail, ok = {}, True
    for g in genres:
        tb, _ = target_beats(skel, g)
        rows = {}
        for nm, (cat, an) in tb.items():
            dur = SA.duration(an)
            b0 = SA.sample(an, 0.0)["bones"]; bE = SA.sample(an, dur)["bones"]
            s0 = SA.sample(an, 0.0)["slots"]; sE = SA.sample(an, dur)["slots"]
            start_id = all(_is_ident(v) for v in b0.values()) and \
                all(abs(s["alpha"] - 1) <= 1e-4 for s in s0.values())
            end_id = all(_is_ident(v) for v in bE.values()) and \
                all(abs(s["alpha"] - 1) <= 1e-4 for s in sE.values())
            good = start_id and end_id
            rows[nm] = {"cat": cat, "start_identity": start_id, "end_identity": end_id, "pass": good}
            ok = ok and good
        detail[g] = rows
    return ok, detail


def check_h3(skel, genres):
    """結構簽章:combo→has_combo_signature、charge→has_charge_signature,且兩簽章互斥。"""
    detail, ok = {}, True
    for g in genres:
        tb, _ = target_beats(skel, g)
        rows = {}
        for nm, (cat, an) in tb.items():
            csig = has_combo_signature(an)
            hsig = has_charge_signature(an)
            if cat == "combo":
                good = csig and not hsig          # 有 combo 簽章、且非 charge(互斥)
            else:  # charge
                good = hsig and not csig
            b = next(iter(an.get("bones", {})), None)
            v = series(an, b) if b else []
            rows[nm] = {"cat": cat, "combo_sig": csig, "charge_sig": hsig,
                        "peaks": [round(p, 3) for p in impact_peaks(v)] if v else [],
                        "hold_frac": round(pre_peak_hold_frac(v), 3) if v else None,
                        "pass": good}
            ok = ok and good
        detail[g] = rows
    return ok, detail


def check_h4(repo="."):
    """已驗先驗覆蓋率不受 combo/charge beat 加入影響(monotonic,仍 1.0 pass)。"""
    detail, ok = {}, True
    for g, prior in GP.PRIORS.items():
        if not prior.get("validated_against"):
            continue
        r = VP.validate_genre(g, prior, repo)
        good = r.get("pass") and abs(r.get("coverage", 0) - 1.0) < 1e-9
        detail[g] = {"coverage": r.get("coverage"), "pass": r.get("pass"),
                     "prior_beats_unused": r.get("prior_beats_unused"), "ok": good}
        ok = ok and good
    return ok, detail


def check_h5(skel, genres):
    """負對照:(a) 無 combo/charge beat 的 genre 產 0 combo/charge clip 且無 clip 具其簽章;
    (b) 主秀 genre 的非 combo/charge beat(In/Loop/Out/hit/reveal/burst)不得具 combo/charge 簽章。"""
    detail = {}
    # (a) character_idle 無 combo/charge beat
    tb_idle, anims_idle = target_beats(skel, "character_idle")
    no_target = (len(tb_idle) == 0) and \
        not any(has_combo_signature(a) or has_charge_signature(a) for a in anims_idle.values())
    detail["character_idle_no_combo_charge"] = {"n_target": len(tb_idle), "pass": no_target}

    # (b) 主秀 genre 的非 combo/charge beat 不得被誤判具 combo/charge 簽章
    non_target_clean = True
    ns_info = {}
    for g in genres:
        anims, _ = _build_genre_anims(skel, g)
        for nm, an in anims.items():
            if G.beat_category(nm) not in TARGET_CATS:
                csig = has_combo_signature(an)
                hsig = has_charge_signature(an)
                if csig or hsig:
                    non_target_clean = False
                ns_info[f"{g}:{nm}"] = {"cat": G.beat_category(nm),
                                        "combo_sig": csig, "charge_sig": hsig}
    detail["non_target_beats_lack_signature"] = {"clean": non_target_clean, "clips": ns_info}
    return no_target and non_target_clean, detail


def run_all(repo="."):
    skel = _skeleton()
    # 有宣告 combo/charge beat 的 validated genres
    genres = []
    for g, prior in GP.PRIORS.items():
        if not prior.get("validated_against"):
            continue
        tb, _ = target_beats(skel, g)
        if tb:
            genres.append(g)
    res = {}
    res["H1_present_routing"] = check_h1(skel, genres)
    res["H2_interface_contract"] = check_h2(skel, genres)
    res["H3_structural_signature"] = check_h3(skel, genres)
    res["H4_coverage_preserved"] = check_h4(repo)
    res["H5_negative_control"] = check_h5(skel, genres)
    overall = all(v[0] for v in res.values())
    return {"overall_pass": overall,
            "genres_with_combo_charge": genres,
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
                          "genres_with_combo_charge": report["genres_with_combo_charge"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
