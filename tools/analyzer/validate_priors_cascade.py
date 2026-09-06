#!/usr/bin/env python3
"""candidate 0h→(I) 整合閘 — cascade(跨件錯開波)主秀節拍已接進 genre 先驗庫,
`build_spine --animate --genre slot_bigwin` 直接輸出 cascade(一件接一件依序 pop 的跨件波)。

與既有閘的分工(補的缺口):
  - `validate_cascade.py`(0h):用**手搭 fixture**(自訂 bone 座標、手寫 {"beat":"cascade"})直接餵
    `build_animations`,只驗**模板本身**的跨件簽章;**不經** genre 先驗、非真實 build_spine 骨架。
  - `validate_priors_combo_charge.py`(H)、`validate_priors_beats.py`(E):同型的先驗整合閘,但涵蓋的是
    **單件內**時間簽章的 combo/charge / hit/reveal。
  - 本閘:從 **genre 先驗庫**(`genre_priors.PRIORS`)出發,經 `analyze_target.build_storyboard`
    (真實 robot 拆件 role + **真實件序**)→ **真實 `build_spine` 骨架** → `build_animations`,證明
    cascade 的**跨件相位 threading**真的會從先驗一路流到最終 animations,即
    `build_spine --animate --genre slot_bigwin` 會輸出帶 cascade **跨件**簽章的 clip。
    這是「模板就緒 ≠ 生成器接上」在 cascade 上的補上,且**跨件**特性讓它比 (E)/(H) 多驗一層:
    件序相位必須端到端存活(單件曲線看不出,只有各件峰時刻的排序/散佈看得出)。

真值界定同 0h/(E)/(H):主秀運動無唯一正解(先驗手感),故驗**客觀結構簽章**
(cascade = 各件峰時刻依**件序**嚴格遞增且散佈 ≥ 門檻)+ **介面契約**(可與 In/Loop/Out 無縫串接),
非美感;並以負對照證鑑別力。

  I1 present+routing : slot_bigwin 宣告的 cascade beat,經先驗→**真實 build_spine 骨架**→build 產出的
                       clip 路由到 cascade 類別,且每件有真峰 scale overshoot ≥ 門檻(泛用微幅達不到)。
  I2 interface契約   : cascade clip 每件首尾皆 setup identity、特效 slot alpha 首尾=1(可插 Loop 間)。
  I3 跨件 cascade 簽章: clip 各件峰時刻**依真實件序**嚴格遞增且散佈 ≥ 門檻(has_cascade_signature),
                       且**非** combo 簽章(單件單峰,證與 0g 正交)。**crux**:件序相位端到端存活。
  I4 coverage 保留   : validated genre 的 validate_priors 覆蓋率仍 ==1.0 pass(cascade 為
                       prior_beats_unused,加 beat 為單調操作,不擾動已驗先驗)。
  I5 negative control: (a) 無 cascade beat 的 genre(character_idle)產 0 個 cascade 類別 clip,且無任一
                       clip 具 cascade 跨件簽章;(b) 主秀 genre 的非 cascade beat(In/burst/hit/combo/
                       charge/Loop/Out)各件峰時刻**不成波**(spread≈0 或非遞增)→ 無 cascade 簽章。

用法:
  python3 validate_priors_cascade.py            # 摘要
  python3 validate_priors_cascade.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import genre_priors as GP
import validate_priors as VP
from analyze_target import analyze
# 復用 0h 的度量,確保簽章判準與 validate_cascade 完全一致
from validate_cascade import (peak_time, peak_times_in_order, cascade_spread,
                              is_strictly_increasing, has_cascade_signature,
                              has_combo_signature, SPREAD_THR)

PSD = "assets/robot_parts.psd"
TARGET_CAT = "cascade"
PEAK_THR = 1.12
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}


def _skeleton():
    """建一份真實 robot 拆件 skeleton(bones 依件名;genre 不影響 bone 命名)。"""
    import build_spine
    out = "/tmp/priors_cascade_skel"
    build_spine.build(PSD, out, genre="slot_bigwin", animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(PSD, genre)["3_motion_storyboard"]


def _part_order(skel, sb):
    """storyboard 件序,限縮到**真實有 bone 的件**(= build_animations 配相位用的有效件序)。"""
    bone_names = {b["name"] for b in skel["bones"]}
    beat0 = sb["beats"][0]  # 各 beat 的 parts 列表同序,取任一
    order = []
    for pe in beat0["parts"]:
        bn = "b_" + G.safe(pe["part"])
        if bn in bone_names:
            order.append(bn)
    return order


def _build_genre_anims(skel, genre):
    """genre 先驗 → storyboard(真實拆件 role + 件序)→ animations(這就是 --animate 的路徑)。"""
    sb = _storyboard(genre)
    return G.build_animations(skel, sb), sb


def _is_ident(bd, tol=1e-4):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def target_clips(skel, genre):
    """回傳 {beat_name: anim}:該 genre 經先驗→build 後路由到 cascade 類別的 clip。"""
    anims, sb = _build_genre_anims(skel, genre)
    out = {nm: an for nm, an in anims.items() if G.beat_category(nm) == TARGET_CAT}
    return out, anims, sb


# ---------------- AC ----------------
def check_i1(skel, genres):
    detail, ok, any_show = {}, True, False
    for g in genres:
        tb, _, _ = target_clips(skel, g)
        rows = {}
        for nm, an in tb.items():
            per = {b: round(max(_series(an, b)), 3) for b in an.get("bones", {})}
            good = len(per) > 0 and all(v >= PEAK_THR for v in per.values())
            rows[nm] = {"peak_scale_per_bone": per, "min_required": PEAK_THR, "pass": good}
            ok = ok and good
            any_show = True
        detail[g] = {"n_target": len(tb), "clips": rows}
    return ok and any_show, detail


def _series(anim, bone, key="scaleX", n=240):
    dur = SA.duration(anim)
    return [SA.sample(anim, dur * i / n)["bones"][bone][key] for i in range(n + 1)]


def check_i2(skel, genres):
    detail, ok = {}, True
    for g in genres:
        tb, _, _ = target_clips(skel, g)
        rows = {}
        for nm, an in tb.items():
            dur = SA.duration(an)
            b0 = SA.sample(an, 0.0)["bones"]; bE = SA.sample(an, dur)["bones"]
            s0 = SA.sample(an, 0.0)["slots"]; sE = SA.sample(an, dur)["slots"]
            start_id = all(_is_ident(v) for v in b0.values()) and \
                all(abs(s["alpha"] - 1) <= 1e-4 for s in s0.values())
            end_id = all(_is_ident(v) for v in bE.values()) and \
                all(abs(s["alpha"] - 1) <= 1e-4 for s in sE.values())
            good = start_id and end_id
            rows[nm] = {"start_identity": start_id, "end_identity": end_id, "pass": good}
            ok = ok and good
        detail[g] = rows
    return ok, detail


def check_i3(skel, genres):
    """跨件簽章:各件峰時刻依**真實件序**嚴格遞增且散佈 ≥ 門檻,且非 combo(單件單峰,正交)。"""
    detail, ok = {}, True
    for g in genres:
        tb, _, sb = target_clips(skel, g)
        order = _part_order(skel, sb)
        rows = {}
        for nm, an in tb.items():
            pts = peak_times_in_order(an, order)
            inc = is_strictly_increasing(pts)
            spread = cascade_spread(pts)
            casc = has_cascade_signature(an, order)
            not_combo = not has_combo_signature(an)
            good = casc and not_combo
            rows[nm] = {"peak_times_in_part_order": [round(p, 3) for p in pts],
                        "strictly_increasing": inc, "spread": round(spread, 3),
                        "spread_thr": SPREAD_THR, "cascade_sig": casc,
                        "not_combo_sig": not_combo, "pass": good}
            ok = ok and good
        detail[g] = {"part_order": order, "clips": rows}
    return ok, detail


def check_i4(repo="."):
    """已驗先驗覆蓋率不受 cascade beat 加入影響(monotonic,仍 1.0 pass)。"""
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


def check_i5(skel, genres):
    """負對照:(a) 無 cascade beat 的 genre 產 0 cascade clip 且無 clip 具跨件簽章;
    (b) 主秀 genre 的非 cascade beat(In/burst/hit/combo/charge/Loop/Out)不成波(無 cascade 簽章)。"""
    detail = {}
    # (a) character_idle 無 cascade beat
    anims_idle, sb_idle = _build_genre_anims(skel, "character_idle")
    order_idle = _part_order(skel, sb_idle)
    n_target_idle = sum(1 for nm in anims_idle if G.beat_category(nm) == TARGET_CAT)
    idle_no_sig = not any(has_cascade_signature(a, order_idle) for a in anims_idle.values())
    no_target = (n_target_idle == 0) and idle_no_sig
    detail["character_idle_no_cascade"] = {"n_target": n_target_idle,
                                           "no_cascade_signature": idle_no_sig, "pass": no_target}

    # (b) 主秀 genre 的非 cascade beat 各件峰時刻不成波
    non_target_clean = True
    ns_info = {}
    for g in genres:
        anims, sb = _build_genre_anims(skel, g)
        order = _part_order(skel, sb)
        for nm, an in anims.items():
            if G.beat_category(nm) != TARGET_CAT:
                sig = has_cascade_signature(an, order)
                pts = peak_times_in_order(an, order)
                if sig:
                    non_target_clean = False
                ns_info[f"{g}:{nm}"] = {"cat": G.beat_category(nm),
                                        "cascade_sig": sig,
                                        "spread": round(cascade_spread(pts), 3)}
    detail["non_cascade_beats_not_wave"] = {"clean": non_target_clean, "clips": ns_info}
    return no_target and non_target_clean, detail


def run_all(repo="."):
    skel = _skeleton()
    # 有宣告 cascade beat(→ 路由到 cascade 類別)的 validated genres
    genres = []
    for g, prior in GP.PRIORS.items():
        if not prior.get("validated_against"):
            continue
        tb, _, _ = target_clips(skel, g)
        if tb:
            genres.append(g)
    res = {}
    res["I1_present_routing"] = check_i1(skel, genres)
    res["I2_interface_contract"] = check_i2(skel, genres)
    res["I3_cross_part_cascade_signature"] = check_i3(skel, genres)
    res["I4_coverage_preserved"] = check_i4(repo)
    res["I5_negative_control"] = check_i5(skel, genres)
    overall = all(v[0] for v in res.values())
    return {"overall_pass": overall,
            "genres_with_cascade": genres,
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
                          "genres_with_cascade": report["genres_with_cascade"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
