#!/usr/bin/env python3
"""candidate 0f→(E) 整合閘 — 主秀 beat 已接進 genre 先驗庫,`build_spine --animate` 直接輸出主秀節拍。

與 `validate_beat_templates.py` 的差別(補的缺口):
  - `validate_beat_templates` 用**合成 storyboard**(手寫 {"beat":"hit"},{"beat":"reveal"})直接餵
    `build_animations`,只驗模板本身;**不經** genre 先驗 → storyboard 這條路。
  - 本閘從 **genre 先驗庫**(`genre_priors.PRIORS`)出發,經 `analyze_target.build_storyboard`
    (真實 robot 拆件 role)→ `build_animations`,證明**主秀節拍真的會從先驗流到最終 animations**,
    即 `build_spine --animate --genre <g>` 會輸出帶主秀簽章的 clip。

真值界定同 0f:主秀運動無唯一正解(先驗手感),故驗**客觀結構簽章**(anticipation+settle / collapse→burst)
與**介面契約**(可與 In/Loop/Out 無縫串接),非美感;並以負對照證鑑別力。

  P1 main-show present : 每個宣告主秀 beat 的 validated genre,經先驗→build 產出的 clip 路由到
                        hit/reveal 類別且有真峰 scale overshoot ≥ 1.12(泛用 Loop 微幅遠達不到)。
  P2 interface契約     : reveal clip 首 collapsed(scale/alpha≤)+ 尾 identity;hit clip 首尾皆 identity。
  P3 結構簽章          : hit clip 具 _hit_signature(反向預備+阻尼回擺+真峰);
                        reveal clip 首 collapse-hold + 峰後穿越 identity ≥2(非天真單峰脈衝)。
  P4 coverage 保留     : validated genre 的 validate_priors 覆蓋率仍 ==1.0 pass(未擾動已驗先驗)。
  P5 negative control  : (a) 無主秀 beat 的 genre(character_idle)產 0 個 hit/reveal 類別 clip、
                        無任何 clip 具主秀簽章;(b) 同一 genre 的非主秀 beat(Loop/idle)不得具主秀簽章。

用法:
  python3 validate_priors_beats.py            # 摘要
  python3 validate_priors_beats.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import genre_priors as GP
import validate_priors as VP
from analyze_target import analyze
# 復用 0f 的度量,確保簽章判準一致
from validate_beat_templates import series, sign_changes, _hit_signature

PSD = "assets/robot_parts.psd"
MAIN_SHOW_CATS = {"hit", "reveal"}
PEAK_THR = 1.12
COLLAPSE = 0.10
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}


def _skeleton():
    """建一份真實 robot 拆件 skeleton(bones 依件名;genre 不影響 bone 命名)。"""
    import build_spine
    out = "/tmp/priors_beats_skel"
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


def main_show_beats(skel, genre):
    """回傳 {beat_name: (category, anim)}:該 genre 經先驗→build 後路由到主秀類別的 clip。"""
    anims, _ = _build_genre_anims(skel, genre)
    out = {}
    for nm, an in anims.items():
        cat = G.beat_category(nm)
        if cat in MAIN_SHOW_CATS:
            out[nm] = (cat, an)
    return out, anims


# ---------------- AC ----------------
def check_p1(skel, genres):
    detail, ok = {}, True
    any_show = False
    for g in genres:
        ms, _ = main_show_beats(skel, g)
        rows = {}
        for nm, (cat, an) in ms.items():
            pk = _peak(an)
            good = pk >= PEAK_THR
            rows[nm] = {"cat": cat, "peak": round(pk, 3), "pass": good}
            ok = ok and good
            any_show = True
        detail[g] = {"n_main_show": len(ms), "clips": rows}
    return ok and any_show, detail


def check_p2(skel, genres):
    detail, ok = {}, True
    for g in genres:
        ms, _ = main_show_beats(skel, g)
        rows = {}
        for nm, (cat, an) in ms.items():
            dur = SA.duration(an)
            b0 = SA.sample(an, 0.0)["bones"]; bE = SA.sample(an, dur)["bones"]
            s0 = SA.sample(an, 0.0)["slots"]; sE = SA.sample(an, dur)["slots"]
            end_id = all(_is_ident(v) for v in bE.values()) and \
                all(abs(s["alpha"] - 1) <= 1e-4 for s in sE.values())
            if cat == "reveal":
                start_collapsed = all(b0[b]["scaleX"] <= COLLAPSE for b in b0) or \
                    (len(s0) > 0 and all(s["alpha"] <= COLLAPSE for s in s0.values()))
                good = start_collapsed and end_id
                rows[nm] = {"cat": cat, "start_collapsed": start_collapsed, "end_identity": end_id, "pass": good}
            else:  # hit
                start_id = all(_is_ident(v) for v in b0.values()) and \
                    all(abs(s["alpha"] - 1) <= 1e-4 for s in s0.values())
                good = start_id and end_id
                rows[nm] = {"cat": cat, "start_identity": start_id, "end_identity": end_id, "pass": good}
            ok = ok and good
        detail[g] = rows
    return ok, detail


def check_p3(skel, genres):
    detail, ok = {}, True
    for g in genres:
        ms, _ = main_show_beats(skel, g)
        rows = {}
        for nm, (cat, an) in ms.items():
            if cat == "hit":
                good = _hit_signature(an)
                rows[nm] = {"cat": cat, "hit_signature": good, "pass": good}
            else:  # reveal:首 collapse-hold + 峰後穿越 ≥2(非天真單峰)
                sub_ok = True
                info = {}
                for b in an.get("bones", {}):
                    v = series(an, b)
                    v0 = v[0]
                    v15 = SA.sample(an, 0.15 * SA.duration(an))["bones"][b]["scaleX"]
                    hold = (v0 <= COLLAPSE and abs(v15 - v0) <= 0.02)
                    pk_idx = max(range(len(v)), key=lambda i: v[i])
                    cross = sign_changes(v[pk_idx:])
                    bgood = hold and cross >= 2
                    info[b] = {"collapse_hold": hold, "post_peak_crossings": cross, "pass": bgood}
                    sub_ok = sub_ok and bgood
                good = sub_ok
                rows[nm] = {"cat": cat, "pass": good, "bones": info}
            ok = ok and good
        detail[g] = rows
    return ok, detail


def check_p4(repo="."):
    """已驗先驗覆蓋率不受主秀 beat 加入影響(monotonic,仍 1.0 pass)。"""
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


def check_p5(skel, genres):
    """負對照:(a) 無主秀 beat 的 genre 產 0 主秀 clip;(b) 非主秀 beat 不具主秀簽章。"""
    detail = {}
    # (a) character_idle 無 hit/reveal beat
    ms_idle, anims_idle = main_show_beats(skel, "character_idle")
    no_show = (len(ms_idle) == 0) and not any(_hit_signature(a) for a in anims_idle.values())
    detail["character_idle_no_main_show"] = {"n_main_show": len(ms_idle), "pass": no_show}

    # (b) 主秀 genre 的非主秀 beat(如 Loop/idle)不得被誤判具主秀 hit 簽章
    non_show_clean = True
    ns_info = {}
    for g in genres:
        anims, _ = _build_genre_anims(skel, g)
        for nm, an in anims.items():
            if G.beat_category(nm) not in MAIN_SHOW_CATS:
                sig = _hit_signature(an)
                if sig:
                    non_show_clean = False
                ns_info[f"{g}:{nm}"] = {"cat": G.beat_category(nm), "hit_signature": sig}
    detail["non_main_show_beats_lack_signature"] = {"clean": non_show_clean, "clips": ns_info}
    return no_show and non_show_clean, detail


def run_all(repo="."):
    skel = _skeleton()
    # 有宣告主秀 beat 的 validated genres
    genres = []
    for g, prior in GP.PRIORS.items():
        if not prior.get("validated_against"):
            continue
        ms, _ = main_show_beats(skel, g)
        if ms:
            genres.append(g)
    res = {}
    res["P1_main_show_present"] = check_p1(skel, genres)
    res["P2_interface_contract"] = check_p2(skel, genres)
    res["P3_structural_signature"] = check_p3(skel, genres)
    res["P4_coverage_preserved"] = check_p4(repo)
    res["P5_negative_control"] = check_p5(skel, genres)
    overall = all(v[0] for v in res.values())
    return {"overall_pass": overall,
            "genres_with_main_show": genres,
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
                          "genres_with_main_show": report["genres_with_main_show"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
