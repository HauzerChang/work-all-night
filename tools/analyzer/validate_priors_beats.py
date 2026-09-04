#!/usr/bin/env python3
"""candidate 0f→E 自我驗收閘 — 「主秀 beat 接進 genre 先驗庫」端到端驗證(純 CPU)。

candidate 0f 的主秀模板(hit/reveal,anticipation+settle)原本只在 `validate_beat_templates.py`
的 fixture storyboard 被驗;本閘驗的是**它們已正確接進已驗證的先驗庫**(`genre_priors.py`),
使 `build_spine --animate` 對真實 genre 直接輸出主秀節拍簽章:

  P1 wiring/coverage : 每個先驗 beat 的 `cat`(若有)∈ VALID_CATS;且兩支 validated genre
                       (slot_bigwin/slot_reveal)的 beat 關鍵字覆蓋率仍 == 1.0(cat 不動關鍵字 → 覆蓋不受影響)。
  P2 bigwin reveal   : slot_bigwin 的 `In` beat(端到端經 analyze→build_animations)每件 bone
                       具 **reveal 主秀簽章**(藏 collapsed → 越過 identity 的 overshoot 峰 → 阻尼回擺 → 尾 identity)。
  P3 reveal open/hit : slot_reveal 的 `open` beat 具 reveal 簽章、`hit` beat 具 **hit 主秀簽章**
                       (反向蓄力 + 阻尼回擺 (scale-1) 變號 ≥3)。
  P4 chaining kept   : 主秀 In/open **尾皆 setup identity**、Loop 首尾 identity → 仍可與 0d 的 Loop/Out 無縫串接。
  P5 discrimination  : **證接線本身是簽章來源**——把 `cat` 剝除(回退關鍵字)後 slot_bigwin `In`
                       退回泛用 intro(gen_in:單峰、無阻尼回擺)→ FAIL reveal 簽章;有 cat 版 PASS。

真值界定:主秀運動屬先驗手感(無唯一正解),本閘驗**客觀結構簽章**與**接線正確性**,非美感。

用法:
  python3 validate_priors_beats.py            # P1–P5
  python3 validate_priors_beats.py --json
"""
import argparse, copy, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import genre_priors as GP
from analyze_target import analyze
from validate_priors import validate_genre
# 復用 0f 閘的簽章度量,確保「先驗接線」與「模板本身」用同一把尺
from validate_beat_templates import series, sign_changes, _hit_signature, N, COLLAPSE

PSD = "assets/robot_parts.psd"   # genre 獨立於 PSD:件來自 PSD、beat 來自 genre


def _end_bones(anim):
    return SA.sample(anim, SA.duration(anim))["bones"]


def _end_slots(anim):
    return SA.sample(anim, SA.duration(anim))["slots"]


def _start_bones(anim):
    return SA.sample(anim, 0.0)["bones"]


def _reveal_signature(anim):
    """一支動畫是否具「主秀 reveal」結構簽章:每 bone 藏(起 collapsed)→ 峰越過 identity →
    峰後阻尼回擺(穿越 identity ≥2)→ 尾 identity。"""
    if not anim.get("bones"):
        return False
    endb = _end_bones(anim)
    startb = _start_bones(anim)
    for b in anim["bones"]:
        v = series(anim, b)
        pk_idx = max(range(len(v)), key=lambda i: v[i])
        if startb[b]["scaleX"] > COLLAPSE:            # 起點必須「藏」
            return False
        if max(v) < 1.12:                              # 必須真峰(越過 identity)
            return False
        if sign_changes(v[pk_idx:]) < 2:               # 峰後阻尼回擺穿越 identity
            return False
        if abs(endb[b]["scaleX"] - 1.0) > 1e-4:        # 尾 identity
            return False
    return True


def _build(genre):
    sb = analyze(PSD, genre)["3_motion_storyboard"]
    # 最小 skeleton:每件一根 bone(模板不依賴 radial 精度)
    parts = {}
    for beat in sb["beats"]:
        for p in beat["parts"]:
            parts[p["part"]] = p["role"]
    bones = [{"name": "root"}]
    for i, (p, _) in enumerate(parts.items()):
        bones.append({"name": "b_" + G.safe(p), "x": 100.0 + 30 * i, "y": 80.0})
    skel = {"skeleton": {"width": 713, "height": 693}, "bones": bones}
    anims = G.build_animations(skel, sb)
    return skel, sb, anims


# ---------------- AC ----------------
def check_p1():
    detail = {"invalid_cats": []}
    for g, prior in GP.PRIORS.items():
        for b in prior["beats"]:
            c = b.get("cat")
            if c is not None and c not in GP.VALID_CATS:
                detail["invalid_cats"].append({"genre": g, "beat": b["key"], "cat": c})
    cats_ok = not detail["invalid_cats"]
    cov_ok = True
    for g, prior in GP.PRIORS.items():
        r = validate_genre(g, prior, ".")
        if r.get("validated_against"):
            detail[g] = {"coverage": r["coverage"], "pass": r["pass"]}
            cov_ok = cov_ok and (r["coverage"] == 1.0)
    return cats_ok and cov_ok, detail


def check_p2():
    _, _, anims = _build("slot_bigwin")
    In = anims.get("In", {})
    sig = _reveal_signature(In)
    return sig, {"In_reveal_signature": sig,
                 "n_bones": len(In.get("bones", {})),
                 "start_min_scale": round(min(_start_bones(In)[b]["scaleX"] for b in In.get("bones", {})), 4) if In.get("bones") else None,
                 "peak_max_scale": round(max(max(series(In, b)) for b in In.get("bones", {})), 4) if In.get("bones") else None}


def check_p3():
    _, _, anims = _build("slot_reveal")
    open_sig = _reveal_signature(anims.get("open", {}))
    hit_sig = _hit_signature(anims.get("hit", {}))
    ok = open_sig and hit_sig
    return ok, {"open_reveal_signature": open_sig, "hit_hit_signature": hit_sig}


def check_p4():
    detail, ok = {}, True
    for genre, main_beat in (("slot_bigwin", "In"), ("slot_reveal", "open")):
        _, _, anims = _build(genre)
        mb = anims.get(main_beat, {})
        endb = _end_bones(mb); ends = _end_slots(mb)
        main_end_id = (all(abs(endb[b]["scaleX"] - 1.0) <= 1e-4 and abs(endb[b]["rotate"]) <= 1e-4 for b in endb)
                       and all(abs(s["alpha"] - 1.0) <= 1e-4 for s in ends.values()))
        loop = anims.get("Loop") or anims.get("loop") or {}
        loop_id = True
        if loop:
            lb0 = _start_bones(loop); lbE = _end_bones(loop)
            loop_id = all(abs(lb0[b]["scaleX"] - 1.0) <= 1e-4 for b in lb0) and \
                      all(abs(lb0[b]["scaleX"] - lbE[b]["scaleX"]) <= 1e-6 for b in lb0)
        detail[genre] = {f"{main_beat}_end_identity": main_end_id, "loop_seamless_identity": loop_id}
        ok = ok and main_end_id and loop_id
    return ok, detail


def check_p5():
    """負對照:剝除 cat → In 退回關鍵字(intro/gen_in)→ 失去 reveal 主秀簽章。證接線=簽章來源。"""
    sb = analyze(PSD, "slot_bigwin")["3_motion_storyboard"]
    parts = {p["part"]: p["role"] for b in sb["beats"] for p in b["parts"]}
    bones = [{"name": "root"}] + [{"name": "b_" + G.safe(p), "x": 100.0 + 30 * i, "y": 80.0}
                                  for i, p in enumerate(parts)]
    skel = {"skeleton": {"width": 713, "height": 693}, "bones": bones}
    # 有 cat 版
    wired = G.build_animations(skel, sb)
    wired_sig = _reveal_signature(wired.get("In", {}))
    # 剝除 cat 版(模擬接線前:回退關鍵字 'In'->intro)
    sb_nocat = copy.deepcopy(sb)
    for b in sb_nocat["beats"]:
        b.pop("cat", None)
    fallback = G.build_animations(skel, sb_nocat)
    fb_cat = G.beat_category("In")
    fb_sig = _reveal_signature(fallback.get("In", {}))
    ok = wired_sig and (fb_cat == "intro") and (not fb_sig)
    return ok, {"wired_In_reveal_signature": wired_sig,
                "fallback_In_category": fb_cat,
                "fallback_In_reveal_signature": fb_sig,
                "discriminative": ok}


def run_all():
    res = {
        "P1_wiring_coverage": check_p1(),
        "P2_bigwin_In_reveal": check_p2(),
        "P3_reveal_open_hit": check_p3(),
        "P4_chaining_kept": check_p4(),
        "P5_discrimination": check_p5(),
    }
    overall = all(v[0] for v in res.values())
    return {"overall_pass": overall,
            "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    report = run_all()
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"overall_pass": report["overall_pass"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
