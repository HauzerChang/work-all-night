#!/usr/bin/env python3
"""candidate 0g 自我驗收閘 — 主秀 payoff 節拍**併入 genre 先驗庫**的端到端驗證(純 CPU)。

candidate 0f 的 `beat_templates`(gen_hit/gen_reveal)已由 `validate_beat_templates.py` 驗過
**結構簽章**;但它用**合成 storyboard**(直接塞 beat key "hit"/"reveal")驗模板本身,**沒有驗**
「真實 genre 先驗(slot_bigwin)會不會在 `analyze_target → build_storyboard → build_animations`
端到端**吐出主秀節拍**」。實測 0g 前 `build_spine --animate --genre slot_bigwin` 只有 In/Loop/Out
(見 log),主秀 payoff 缺席。本閘補這條:

  W1 emit_show_beat : slot_bigwin 端到端(build_spine.build --animate)輸出含主秀類別 beat(Hit),
                      完整序列 In→Hit→Loop→Out。
  W2 signature      : 吐出的 Hit 每 bone 具 hit 簽章(peak≥1.12 + anticipation 蓄力 + settle 變號≥3;
                      **復用 0f `validate_beat_templates._hit_signature` 判定器**,同一可信簽章來源)。
  W3 seamless_chain : In 尾 / Hit 首尾 / Loop 首尾 / Out 首 皆 setup identity → 相鄰 beat 邊界位移=0,
                      In→Hit→Loop→Out 可無縫串接(補齊「入場→payoff→待機→退場」的完整演出)。
  W4 truth_regress  : `validate_priors` overall_pass 仍 True 且 slot_bigwin 覆蓋率仍 1.0
                      (Award In/Loop/Out 未被破壞;Hit 為提案節拍→validate_priors 標 unused,誠實)。
  W5 neg_control    : (a) 天真對稱脈衝(gen_pulse)取代 Hit → 簽章 False(閘能分辨主秀 vs 泛用脈衝);
                      (b) 先驗**移除 Hit** → 端到端 0 主秀 beat(證「併入先驗」才是主秀出現的主因)。
  W6 both_genres    : slot_reveal 端到端仍吐 reveal(open)+ hit(hit)兩主秀類別(未被本次改動波及)。

真值界定同 0f:主秀 beat 無唯一正確運動(先驗手感),閘驗**客觀結構簽章 + 介面契約 + 真值覆蓋回歸**,
非美感;緩動幅度手感留使用者(A 類)。

用法:
  python3 validate_show_beat_wiring.py           # 精簡 pass/fail
  python3 validate_show_beat_wiring.py --json     # 完整 JSON
"""
import argparse, copy, json, os, sys, tempfile

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import genre_priors as GP
import validate_beat_templates as BT   # 復用 0f 可信判定器 / 度量
import validate_priors as VP

ROBOT = "assets/robot_parts.psd"
SHOW_CATS = {"hit", "reveal"}
IDENT = BT.IDENT
TOL = 1e-4


def _build(genre):
    """端到端跑 build_spine.build(--animate),回傳 animations dict(真實組裝路徑)。"""
    import build_spine
    with tempfile.TemporaryDirectory() as td:
        build_spine.build(ROBOT, td, genre=genre, animate=True)   # 寫 skeleton.json 到 td
        skel = json.load(open(os.path.join(td, "skeleton.json"), encoding="utf-8"))
    return skel["animations"]


def _show_beats(anims):
    return [k for k in anims if G.beat_category(k) in SHOW_CATS]


def _pose(anim, t):
    """bone -> {rotate,x,y,scaleX,scaleY};未被 timeline 觸及的 bone 視為 setup identity。"""
    return SA.sample(anim, t)["bones"]


def _endpoint_identity(anim, which):
    """which='start'|'end'|'both':該端所有 bone 皆 identity(slot alpha≈1)。"""
    dur = SA.duration(anim)
    ts = {"start": [0.0], "end": [dur], "both": [0.0, dur]}[which]
    ok = True
    for t in ts:
        s = SA.sample(anim, t)
        ok = ok and all(BT.is_ident(v, TOL) for v in s["bones"].values())
        ok = ok and all(abs(sl["alpha"] - 1.0) <= 1e-3 for sl in s["slots"].values())
    return ok


def check_w1_w2_w3(anims):
    keys = list(anims.keys())
    show = _show_beats(anims)
    w1 = {"anim_sequence": keys,
          "has_show_beat": len(show) > 0,
          "show_beats": show,
          "hit_present": "Hit" in anims and G.beat_category("Hit") == "hit",
          "full_show_sequence": keys == ["In", "Hit", "Loop", "Out"]}
    w1_ok = w1["has_show_beat"] and w1["hit_present"] and w1["full_show_sequence"]

    # W2:吐出的 Hit 具主秀簽章(復用 0f 判定器);逐 bone 明細
    hit = anims.get("Hit", {"bones": {}})
    per_bone = {}
    for b in hit.get("bones", {}):
        v = BT.series(hit, b)
        pk = max(range(len(v)), key=lambda i: v[i])
        per_bone[b] = {"peak": round(max(v), 3),
                       "pre_impact_min": round(min(v[:pk]) if pk > 0 else 1.0, 4),
                       "sign_changes": BT.sign_changes(v)}
    w2_ok = BT._hit_signature(hit) is True and len(per_bone) > 0
    w2 = {"hit_signature": w2_ok, "per_bone": per_bone}

    # W3:介面契約 → 任意相鄰 beat 邊界位移=0
    # In 尾 identity / Hit 首尾 identity / Loop 首尾 identity / Out 首 identity
    req = {"In": "end", "Hit": "both", "Loop": "both", "Out": "start"}
    idcheck = {k: _endpoint_identity(anims[k], w) for k, w in req.items() if k in anims}
    # 邊界不連續量(union bones,缺席=identity)
    order = ["In", "Hit", "Loop", "Out"]
    boundary = {}
    max_disc = 0.0
    for a, bb in zip(order, order[1:]):
        if a not in anims or bb not in anims:
            continue
        pa = _pose(anims[a], SA.duration(anims[a]))
        pb = _pose(anims[bb], 0.0)
        d = 0.0
        for bone in set(pa) | set(pb):
            va = pa.get(bone, IDENT); vb = pb.get(bone, IDENT)
            d = max(d, max(abs(va[k] - vb[k]) for k in IDENT))
        boundary[f"{a}->{bb}"] = round(d, 6)
        max_disc = max(max_disc, d)
    w3_ok = all(idcheck.values()) and max_disc <= TOL
    w3 = {"endpoint_identity": idcheck, "boundary_discontinuity": boundary,
          "max_discontinuity": round(max_disc, 6)}
    return (w1_ok, w1), (w2_ok, w2), (w3_ok, w3)


def check_w4():
    reports = [VP.validate_genre(g, p, ".") for g, p in GP.PRIORS.items()]
    validated = [r for r in reports if r.get("validated_against")]
    allpass = all(r["pass"] for r in validated) and len(validated) > 0
    bw = next(r for r in reports if r["genre"] == "slot_bigwin")
    ok = allpass and abs(bw["coverage"] - 1.0) < 1e-9
    return ok, {"overall_pass": allpass,
                "slot_bigwin_coverage": bw["coverage"],
                "slot_bigwin_unused_beats": bw["prior_beats_unused"],
                "per_genre": {r["genre"]: {"coverage": r.get("coverage"), "pass": r.get("pass")}
                              for r in validated}}


def check_w5(anims):
    # (a) 對稱脈衝取代 Hit → 簽章 False
    pb, _ = G.gen_pulse("body", 1.0, (0.0, 0.0))
    pulse_anim = {"bones": {"b_pulse": pb}}
    neg_a = BT._hit_signature(pulse_anim) is False

    # (b) 先驗移除 Hit → 端到端 0 主秀 beat(monkeypatch 後還原)
    prior = GP.PRIORS["slot_bigwin"]
    saved = prior["beats"]
    try:
        prior["beats"] = [b for b in saved if b["key"] != "Hit"]
        anims_noHit = _build("slot_bigwin")
    finally:
        prior["beats"] = saved
    neg_b = len(_show_beats(anims_noHit)) == 0
    ok = neg_a and neg_b
    return ok, {"symmetric_pulse_not_signature": neg_a,
                "prior_without_Hit_emits_no_show_beat": neg_b,
                "baseline_seq_without_Hit": list(anims_noHit.keys())}


def check_w6():
    anims = _build("slot_reveal")
    cats = {G.beat_category(k) for k in anims}
    ok = "reveal" in cats and "hit" in cats
    return ok, {"anim_sequence": list(anims.keys()),
                "categories": sorted(cats),
                "has_reveal": "reveal" in cats, "has_hit": "hit" in cats}


def run_all():
    anims = _build("slot_bigwin")
    (w1_ok, w1), (w2_ok, w2), (w3_ok, w3) = check_w1_w2_w3(anims)
    w4_ok, w4 = check_w4()
    w5_ok, w5 = check_w5(anims)
    w6_ok, w6 = check_w6()
    res = {
        "W1_emit_show_beat": {"pass": w1_ok, "detail": w1},
        "W2_signature": {"pass": w2_ok, "detail": w2},
        "W3_seamless_chain": {"pass": w3_ok, "detail": w3},
        "W4_truth_regression": {"pass": w4_ok, "detail": w4},
        "W5_negative_control": {"pass": w5_ok, "detail": w5},
        "W6_both_genres": {"pass": w6_ok, "detail": w6},
    }
    overall = all(v["pass"] for v in res.values())
    return {"overall_pass": overall, "ac": res}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    rep = run_all()
    if a.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"overall_pass": rep["overall_pass"],
                          "ac": {k: v["pass"] for k, v in rep["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
