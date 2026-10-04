#!/usr/bin/env python3
"""candidate (L-2) 自我驗收閘 — 大獎序列組合的 **shear 通道無縫**(cross-beat composition, shear-aware)。

**補的缺口(candidate L 明列的 honest boundary)**:candidate L 的序列組合閘以 `spine_anim.sample()`
量接點殘差,但 `sample()` 當時只覆蓋 rotate/translate/scale(+slot alpha)——**shear 通道對取樣器
不可見**。wobble/squash/twist 這三支 beat 的運動基元**正是活在 shear 通道上**,故 candidate L 的
正向序列 `In→hit→combo→charge→cascade→Loop→Out` **刻意不含任何 shear beat**:不是因為 shear beat
不能組合,而是因為「組不組得起來」當時**驗不了**(接點閘看不見 shear)。

本次 (L-2):
  (1) `spine_anim.sample()` 補 shear 取樣(additive,setup 預設 (0,0),既有呼叫端逐位元不變);
  (2) 本閘把 wobble/squash/twist **真的放進序列**,以 **shear-inclusive** 接點殘差驗三支 shear beat
      **也能無縫組合**,並直接驗其 shear 通道端點皆 identity(=其無縫的結構原因);
  (3) **crux 負對照(閘可信)**:造一支端點 shear≠0 的壞 shear beat →
      **shear-aware 接點閘抓得到**(殘差 >> SEAM_TOL)、**舊的 shear-blind 接點閘仍判無縫**
      (rotate/x/y/scale 都還是 identity)→ 證「補 shear 覆蓋」是**抓到這類非無縫的必要條件**
      (舊閘對這塊是盲的),而非冗餘。

真值界定:beat **排序**仍是 PROPOSAL(手感 A 類);但「接點 shear 殘差」「shear 端點 identity」
「回切 shear 逐幀還原」皆為**客觀可量測**不變量。從**先驗庫** → **真實 build_spine robot 骨架** →
`build_animations` 端到端,與 candidate L / J / charge 同一 fixture。

AC(客觀、可量測):
  LS1 present+well-formed : 含 shear beat 的序列 compose 後為合法 Spine timeline;shear beat 皆現身且
                           其 shear 通道確實被帶進 composed(≥1 bone 的 composed["bones"][b]["shear"] 非空)。
  LS2 crux shear-aware seam: 含 shear beat 的序列每個**內部接點**的 **shear-inclusive** 跨通道殘差
                           < SEAM_TOL(三支 shear beat 端點皆 identity → 接點無縫,連 shear 一起看也無縫)。
  LS3 shear endpoints id  : 每支 shear beat 的**每個** bone shear 通道首/末幀皆 (0,0)(tol 內)——
                           這是 LS2 無縫的**結構原因**(直接讀原始幀,獨立於 sample)。
  LS4 faithful concat sh  : 回切每支 shear beat 段(composed 在 [start,start+dur] 取樣)**逐幀還原**
                           孤立 clip,**含 shear 通道**(shear-aware 殘差 < FAITH_TOL)→ 平移不扭曲 shear。
  LS5 neg-control (crux)  : 造端點 shear≠0 的壞 wobble 放序列中段 →
                           (a) shear-aware 接點閘抓到(殘差 > NEG_MULT×SEAM_TOL 且正確指認肇因接點);
                           (b) **同一接點** shear-blind 殘差 < SEAM_TOL(舊閘判無縫)→ 證 shear 覆蓋必要。

用法:
  python3 validate_sequence_compose_shear.py          # 摘要
  python3 validate_sequence_compose_shear.py --json   # 完整 JSON
"""
import argparse, copy, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
from analyze_target import analyze

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"

# setup identity,含 shear 兩鍵(shear-aware);shear-blind 用子集(前 5 鍵)。
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0,
         "shearX": 0.0, "shearY": 0.0}
BLIND_KEYS = ("rotate", "x", "y", "scaleX", "scaleY")   # candidate L 舊閘可見的通道
SHEAR_KEYS = ("shearX", "shearY")

SEAM_TOL = 1e-3     # 接點 C0 殘差上限(identity==identity 實測 ~0;幀值 round 到 4 位)
FAITH_TOL = 1e-4    # 回切還原殘差上限(純時間平移)
NEG_MULT = 10.0     # 負對照接點殘差須 > NEG_MULT × SEAM_TOL
SHEAR_INJECT = 15.0 # 壞 beat 注入的端點 shear 值(度)

# 含 shear beat 的正向序列(皆 identity 介面 → 應無縫;shear beat 夾在主秀段中間):
#   In(collapsed→id) → hit → wobble → squash → twist → combo → Loop → Out
POS_ORDER = ["In", "hit", "wobble", "squash", "twist", "combo", "Loop", "Out"]
SHEAR_BEATS = ["wobble", "squash", "twist"]


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/seq_compose_shear_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


# ---------------- 量測器 ----------------
def _state_diff(s1, s2, keys):
    """兩個 sample() 狀態的跨 bone/slot 最大絕對差,只比 `keys` 指定的 bone 通道(+slot alpha)。
    keys=BLIND_KEYS → 重現 candidate L 舊閘(shear 盲);keys=IDENT → shear-aware。"""
    m = 0.0
    for b in set(s1["bones"]) | set(s2["bones"]):
        d1 = s1["bones"].get(b, IDENT)
        d2 = s2["bones"].get(b, IDENT)
        for k in keys:
            m = max(m, abs(d1.get(k, IDENT[k]) - d2.get(k, IDENT[k])))
    for s in set(s1["slots"]) | set(s2["slots"]):
        a1 = s1["slots"].get(s, {"alpha": 1.0})["alpha"]
        a2 = s2["slots"].get(s, {"alpha": 1.0})["alpha"]
        m = max(m, abs(a1 - a2))
    return m


def _junction_seams(anims, order, keys):
    """各內部接點殘差(前一 beat 尾幀狀態 vs 後一 beat 首幀狀態),以 `keys` 決定可見通道。"""
    seams = []
    for i in range(len(order) - 1):
        a, b = anims[order[i]], anims[order[i + 1]]
        end = SA.sample(a, SA.duration(a))
        start = SA.sample(b, 0.0)
        seams.append({"pair": "{}->{}".format(order[i], order[i + 1]),
                      "seam": round(_state_diff(end, start, keys), 6)})
    return seams


def _well_formed(composed):
    for group in ("bones", "slots"):
        for chans in composed.get(group, {}).values():
            for frames in chans.values():
                last = None
                for f in frames:
                    t = f.get("time")
                    if t is None or not math.isfinite(t):
                        return False
                    if last is not None and not (t > last):
                        return False
                    last = t
                    for k, val in f.items():
                        if k == "time":
                            continue
                        if isinstance(val, (int, float)) and not math.isfinite(val):
                            return False
    return True


def _make_bad_wobble(anims):
    """candidate L-2 負對照:複製 wobble,把某 bone shear 通道的**末幀** x 設為 SHEAR_INJECT(≠0)。
    rotate/x/y/scale 一律不動 → 此端點對 shear-blind 仍是 identity、對 shear-aware 非 identity。"""
    bad = copy.deepcopy(anims["wobble"])
    for bn, chans in bad.get("bones", {}).items():
        if "shear" in chans and chans["shear"]:
            chans["shear"][-1] = dict(chans["shear"][-1])
            chans["shear"][-1]["x"] = SHEAR_INJECT
            return bad, bn
    raise RuntimeError("wobble 無 shear 通道,fixture 異常")


# ---------------- AC ----------------
def ac_LS1(anims):
    composed, segs = G.compose_sequence(anims, POS_ORDER)
    wf = _well_formed(composed)
    covers = [s["beat"] for s in segs] == POS_ORDER
    present = all(nm in anims for nm in SHEAR_BEATS)
    # shear 通道確實被帶進 composed(至少一 bone 有非空 shear)
    shear_threaded = any("shear" in chans and chans["shear"]
                         for chans in composed.get("bones", {}).values())
    ok = wf and covers and present and shear_threaded
    return {"pass": bool(ok), "well_formed": wf, "covers_order": covers,
            "shear_beats_present": present, "shear_threaded_into_composed": shear_threaded,
            "segments": segs}


def ac_LS2(anims):
    seams = _junction_seams(anims, POS_ORDER, IDENT)   # shear-aware
    worst = max((s["seam"] for s in seams), default=0.0)
    ok = worst < SEAM_TOL
    return {"pass": bool(ok), "worst_seam_shear_aware": worst, "tol": SEAM_TOL, "seams": seams}


def ac_LS3(anims):
    """每支 shear beat 每個 bone 的 shear 通道首/末幀 == (0,0)。"""
    bad = []
    checked = 0
    for nm in SHEAR_BEATS:
        for bn, chans in anims[nm].get("bones", {}).items():
            fr = chans.get("shear")
            if not fr:
                continue
            checked += 1
            for end in (fr[0], fr[-1]):
                if abs(end.get("x", 0.0)) > SEAM_TOL or abs(end.get("y", 0.0)) > SEAM_TOL:
                    bad.append("{}::{}".format(nm, bn))
                    break
    ok = checked > 0 and not bad
    return {"pass": bool(ok), "shear_channels_checked": checked, "nonident_endpoints": bad}


def ac_LS4(anims):
    """回切每支 shear beat 段逐幀還原孤立 clip,含 shear 通道。"""
    composed, segs = G.compose_sequence(anims, POS_ORDER)
    seg_of = {s["beat"]: s for s in segs}
    worst = 0.0
    worst_at = None
    for nm in SHEAR_BEATS:
        s = seg_of[nm]
        clip = anims[nm]
        grid = 24
        for i in range(grid + 1):
            t = s["dur"] * i / grid
            d = _state_diff(SA.sample(composed, s["start"] + t), SA.sample(clip, t), IDENT)
            if d > worst:
                worst, worst_at = d, {"beat": nm, "t": round(t, 4)}
    ok = worst < FAITH_TOL
    return {"pass": bool(ok), "worst_residual_shear_aware": round(worst, 9),
            "worst_at": worst_at, "tol": FAITH_TOL}


def ac_LS5(anims):
    """crux 負對照:端點 shear≠0 的壞 wobble 放序列中段。
    shear-aware 閘抓到、shear-blind 閘漏判 → 證 shear 覆蓋必要。"""
    bad_wobble, bad_bone = _make_bad_wobble(anims)
    a2 = dict(anims)
    a2["wobble_bad"] = bad_wobble
    # 壞 wobble 夾在中段(其末幀 shear≠0,與後一 beat 首幀 shear=0 → shear 接點應斷)
    order = ["In", "hit", "wobble_bad", "squash", "twist", "combo", "Loop", "Out"]

    seams_aware = _junction_seams(a2, order, IDENT)
    seams_blind = _junction_seams(a2, order, BLIND_KEYS)
    # shear-aware:最壞接點應 > NEG_MULT×SEAM_TOL 且肇因為 wobble_bad-> 的接點
    worst_aware = max(s["seam"] for s in seams_aware)
    off_aware = max(seams_aware, key=lambda s: s["seam"])["pair"]
    aware_catches = (worst_aware > NEG_MULT * SEAM_TOL) and off_aware.startswith("wobble_bad->")

    # shear-blind:**同一肇因接點**殘差應 < SEAM_TOL(舊閘判無縫 → 盲)
    blind_at_offender = next(s["seam"] for s in seams_blind if s["pair"] == off_aware)
    blind_misses = blind_at_offender < SEAM_TOL
    # 且壞接點的 shear-aware 殘差≈注入量(確認是 shear 造成的)
    aware_at_offender = next(s["seam"] for s in seams_aware if s["pair"] == off_aware)
    caused_by_shear = abs(aware_at_offender - SHEAR_INJECT) < 1e-3

    ok = aware_catches and blind_misses and caused_by_shear
    return {"pass": bool(ok),
            "offender_junction": off_aware, "bad_bone": bad_bone,
            "shear_aware_catches": bool(aware_catches), "worst_seam_aware": round(worst_aware, 6),
            "shear_blind_misses": bool(blind_misses),
            "blind_residual_at_offender": round(blind_at_offender, 6),
            "aware_residual_at_offender": round(aware_at_offender, 6),
            "caused_by_shear": bool(caused_by_shear), "inject": SHEAR_INJECT}


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    anims = G.build_animations(skel, sb)
    missing = [nm for nm in set(POS_ORDER) if nm not in anims]
    if missing:
        return {"overall_pass": False, "error": "missing beats in fixture: {}".format(missing),
                "available": sorted(anims.keys())}
    results = {"LS1_wellformed_present": ac_LS1(anims),
               "LS2_crux_shear_aware_seam": ac_LS2(anims),
               "LS3_shear_endpoints_identity": ac_LS3(anims),
               "LS4_faithful_concat_shear": ac_LS4(anims),
               "LS5_neg_control": ac_LS5(anims)}
    results["overall_pass"] = all(v["pass"] for v in results.values())
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    res = run()
    if a.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print("candidate (L-2) 大獎序列組合閘 — shear 通道無縫")
        print("序列:", " -> ".join(POS_ORDER))
        for k in ["LS1_wellformed_present", "LS2_crux_shear_aware_seam",
                  "LS3_shear_endpoints_identity", "LS4_faithful_concat_shear", "LS5_neg_control"]:
            v = res.get(k, {})
            print("  {:30s} {}".format(k, "PASS" if v.get("pass") else "FAIL"))
        if "LS2_crux_shear_aware_seam" in res:
            print("    LS2 worst shear-aware seam: {:.2e} (tol {:.0e})".format(
                res["LS2_crux_shear_aware_seam"]["worst_seam_shear_aware"], SEAM_TOL))
        if "LS5_neg_control" in res:
            n = res["LS5_neg_control"]
            print("    LS5 offender {} | aware={} ({:.3g}) blind-misses={} ({:.3g})".format(
                n.get("offender_junction"), n.get("shear_aware_catches"),
                n.get("aware_residual_at_offender", 0.0), n.get("shear_blind_misses"),
                n.get("blind_residual_at_offender", 0.0)))
        if "error" in res:
            print("  ERROR:", res["error"])
        print("OVERALL:", "PASS" if res.get("overall_pass") else "FAIL")
    return 0 if res.get("overall_pass") else 1


if __name__ == "__main__":
    sys.exit(main())
