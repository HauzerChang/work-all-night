#!/usr/bin/env python3
"""candidate 0g 自我驗收閘 — slot_bigwin「主秀重擊(Hit)」beat 端到端接進先驗庫(純 CPU)。

補上 0f 的缺口:0f 的 gen_hit/gen_reveal 主秀模板雖已註冊到 gen_animations._DISPATCH,
但 **slot_bigwin 的預設分鏡只有 In/Loop/Out**(Award 生產檔把主秀節拍折進 In,無獨立 hit 動畫),
故 `build_spine --animate --genre slot_bigwin` **從不輸出主秀節拍**。本 chunk 在 genre_priors 的
slot_bigwin 加一個 PROPOSAL 主秀 beat `Hit`(路由到 gen_hit),讓端到端演出含蓄力→命中→阻尼回擺。

**驗證真相**:主秀節拍無唯一美術正解(先驗手感),故閘驗的是**定義主秀的客觀結構簽章**
(反向預備 anticipation + 阻尼回擺 settle,沿用 0f validate_beat_templates 的判定子),
並以**負對照**(同一 build 的 In/Loop 不具此簽章)證明加的是真·主秀而非改名。

  G1 reachability : `build_spine --animate --genre slot_bigwin` 端到端輸出含 'Hit' 動畫,結構件 bone ≥1。
  G2 hit signature: 結構件(body)scale 包絡:真峰 ≥1.12 + 命中前下蹲 <0.99 + (scale-1) 變號 ≥3(阻尼回擺)。
  G3 chainable    : 'Hit' 首尾幀皆 setup identity(scale≈1、alpha≈1)→ 可插在 Loop 循環間當重音。
  G4 neg-control  : 同一 build 的 'In'(intro)與 'Loop' 皆**不**具 hit 簽章 → 證主秀為新增之獨立節拍。
  G5 regression   : validate_priors slot_bigwin 覆蓋率仍 1.0、overall_pass 不變,Award In/Loop/Out 歸類不動
                    (新 'Hit' 對 Award 命名不命中,列 prior_beats_unused → 誠實 PROPOSAL)。

用法:
  python3 validate_bigwin_mainshow.py           # 摘要
  python3 validate_bigwin_mainshow.py --json     # 完整 JSON
"""
import argparse, json, os, sys, tempfile

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
# 沿用 0f 的結構簽章判定子,確保與 validate_beat_templates 一致
from validate_beat_templates import series, sign_changes, _hit_signature, is_ident, N

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"


def build_bigwin_spine():
    """端到端:build_spine --animate --genre slot_bigwin(真實 robot_parts PSD)→ skeleton dict。"""
    from build_spine import build
    tmp = tempfile.mkdtemp(prefix="bigwin_mainshow_")
    build(PSD, tmp, genre=GENRE, weighted=False, animate=True, rig=False, deform=False)
    return json.load(open(os.path.join(tmp, "skeleton.json"), encoding="utf-8"))


def _struct_bone(skeleton, anim):
    """挑一個結構件(body 優先)的 bone 名;fallback 任一有 scale 的 bone。"""
    # role 資訊在 storyboard;這裡由 build_meta 之外簡化:body 件名含 '身'/'body'
    for b in anim.get("bones", {}):
        nm = b.removeprefix("b_")
        if "身" in nm or "body" in nm.lower():
            return b
    return next(iter(anim.get("bones", {})), None)


def check_g1(skeleton):
    anims = skeleton.get("animations", {})
    hit = anims.get("Hit", {})
    nb = len(hit.get("bones", {}))
    ok = ("Hit" in anims) and nb >= 1
    return ok, {"anims": list(anims.keys()), "hit_bones": nb}


def check_g2(skeleton):
    hit = skeleton["animations"]["Hit"]
    b = _struct_bone(skeleton, hit)
    v = series(hit, b)
    peak = max(v)
    pk_idx = max(range(len(v)), key=lambda i: v[i])
    pre_min = min(v[:pk_idx]) if pk_idx > 0 else 1.0
    sc = sign_changes(v)
    ok = (peak >= 1.12) and (pre_min < 0.99) and (sc >= 3)
    return ok, {"bone": b, "peak": round(peak, 3), "pre_impact_min": round(pre_min, 4),
                "settle_sign_changes": sc, "thr": {"peak": 1.12, "pre_min": 0.99, "sc": 3}}


def check_g3(skeleton):
    hit = skeleton["animations"]["Hit"]
    dur = SA.duration(hit)
    ok = True
    detail = {}
    for tag, t in (("start", 0.0), ("end", dur)):
        smp = SA.sample(hit, t)
        b_id = all(is_ident(bd, 1e-4) for bd in smp["bones"].values())
        s_id = all(abs(sd["alpha"] - 1.0) <= 1e-4 for sd in smp["slots"].values())
        detail[tag] = {"bones_identity": b_id, "slots_alpha_1": s_id}
        ok = ok and b_id and s_id
    return ok, detail


def check_g4(skeleton):
    """負對照:同一 build 的 In / Loop 不具 hit 簽章。"""
    anims = skeleton["animations"]
    out = {}
    for nm in ("In", "Loop"):
        a = anims.get(nm, {})
        out[f"{nm}_no_hit_signature"] = (a != {} and _hit_signature(a) is False)
    return all(out.values()), out


def check_g5():
    """回歸:validate_priors slot_bigwin 覆蓋率 1.0、Award In/Loop/Out 歸類不動、Hit 為 unused。"""
    import genre_priors as GP
    from validate_priors import validate_genre
    r = validate_genre("slot_bigwin", GP.PRIORS["slot_bigwin"], ".")
    boa = r.get("beat_of_anim", {})
    cov_ok = abs(r.get("coverage", 0) - 1.0) < 1e-9 and r.get("pass") is True
    inout_ok = all(k in boa for k in ("In", "Loop", "Out")) and "Hit" not in boa
    unused_ok = "Hit" in r.get("prior_beats_unused", [])
    ok = cov_ok and inout_ok and unused_ok
    return ok, {"coverage": r.get("coverage"), "pass": r.get("pass"),
                "mapped_beats": sorted(boa.keys()), "prior_beats_unused": r.get("prior_beats_unused")}


def run_all():
    skeleton = build_bigwin_spine()
    res = {}
    res["G1_reachability"] = check_g1(skeleton)
    res["G2_hit_signature"] = check_g2(skeleton)
    res["G3_chainable_interface"] = check_g3(skeleton)
    res["G4_negative_control"] = check_g4(skeleton)
    res["G5_priors_regression"] = check_g5()
    overall = all(v[0] for v in res.values())
    return {"overall_pass": overall,
            "anims": list(skeleton.get("animations", {}).keys()),
            "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    report = run_all()
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"overall_pass": report["overall_pass"], "anims": report["anims"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
