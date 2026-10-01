#!/usr/bin/env python3
"""S1 分析器對真值校驗 — robot_parts.psd 反推規格 ⇄ Award 真實生產 spine。

Award 是 robot_parts 的真實成品(機器人拆件 5 slot / 綁 5 骨 / 12 動畫 = 4 檔位×In/Loop/Out)。
用它當真值,量化 analyze_target.py 的反推召回:
  ① 可動件召回:反推件 vs Award 機器人拆件 slot(名稱對應)。
  ② 特效分類:光暈 應判為特效;其餘結構。
  ③ mesh/region 建議 vs Award 實際 attachment type。
  ④ 分鏡結構:提案 In/Loop/Out(+檔位) 是否**涵蓋** Award 動畫命名結構(召回,非嚴格相等)。
  ⑤ 露出項合理性:各 reveal 的 mover 骨在 Award 是否真的有足量運動(位移/旋轉)。
"""
import argparse, json, os, sys, re
sys.path.insert(0, os.path.dirname(__file__))
from analyze_target import analyze

ROBOT_PREFIX = "機器人拆件"
# 真值:Award attachment type(見 knowledge/s4-psd-to-spine-real.md)
AWARD_TYPE = {"光暈": "mesh", "右手": "region", "頭": "region", "身體": "mesh", "左手": "mesh"}
AWARD_EFFECT = {"光暈"}  # 語意上的特效件(發光背景)


def award_slots(sk):
    return [s for s in sk["slots"] if s["name"].startswith(ROBOT_PREFIX)]


def bone_motion(sk):
    """每骨在所有動畫中的最大 |位移|、|旋轉|、scale 偏離1(反映實際運動量)。"""
    mag = {}
    for an, ad in sk.get("animations", {}).items():
        for bn, tl in ad.get("bones", {}).items():
            m = mag.setdefault(bn, {"tr": 0.0, "rot": 0.0, "sc": 0.0})
            for it in tl.get("translate", []):
                m["tr"] = max(m["tr"], abs(it.get("x", 0)), abs(it.get("y", 0)))
            for it in tl.get("rotate", []):
                m["rot"] = max(m["rot"], abs(it.get("angle", 0)))
            for it in tl.get("scale", []):
                m["sc"] = max(m["sc"], abs(it.get("x", 1) - 1), abs(it.get("y", 1) - 1))
    return mag


def beat_structure(proposed_beats, award_beats, proposed_tiers, award_tiers):
    """④ 分鏡結構判準 = 召回(recall),非嚴格相等。

    Award 只命名**結構** beat(In/Loop/Out);分析器累積的主秀先驗(burst/cascade/
    charge/combo/hit/squash/twist/wobble)在 Award 無對應命名動畫 —— 它們是 PROPOSAL
    (同 validate_priors 的 prior_beats_unused 誠實處理),不應算 match 失敗。
    正確條件:Award 命名的每個 beat 都被提出(award ⊆ proposed)且至少命中一個檔位。
    `beats_match`(嚴格相等)仍一併回報作透明佐證(有 PROPOSAL 多出時為 False)。
    """
    proposed_beats, award_beats = set(proposed_beats), set(award_beats)
    proposed_tiers, award_tiers = set(proposed_tiers), set(award_tiers)
    beats_covered = award_beats <= proposed_beats            # 召回:結構 beat 全被提出
    beats_match = proposed_beats == award_beats              # 嚴格相等(透明佐證)
    proposal_only = sorted(proposed_beats - award_beats)     # 主秀 PROPOSAL(Award 未命名)
    tiers_hit = proposed_tiers & award_tiers
    return {
        "proposed_beats": sorted(proposed_beats),
        "award_beats": sorted(award_beats),
        "beats_covered": beats_covered,
        "beats_match": beats_match,
        "beats_proposal_only": proposal_only,
        "award_tiers": sorted(award_tiers),
        "tiers_hit": sorted(tiers_hit),
        "pass": beats_covered and len(tiers_hit) >= 1,
    }


def validate(psd_path, award_path):
    spec = analyze(psd_path)
    sk = json.load(open(award_path))
    slots = award_slots(sk)
    slot_names = {s["name"].split("/", 1)[1]: s for s in slots}   # 圖層名 -> slot
    mag = bone_motion(sk)

    # ① 可動件召回
    parts = [p["name"] for p in spec["1_movable_parts"]]
    matched = [p for p in parts if p in slot_names]
    recall = len(matched) / max(len(slot_names), 1)

    # ② 特效分類
    eff = {e["name"]: e["is_effect"] for e in spec["2_effects"]}
    eff_ok = {n: (eff.get(n, False) == (n in AWARD_EFFECT)) for n in slot_names}

    # ③ mesh/region 建議 vs 真值
    geo_map = {r["part"]: r["geometry"] for r in spec["4_slicing_strategy"]["parts"]}
    geo_eval = {}
    for n in slot_names:
        rec = geo_map.get(n, "")
        rec_mesh = rec.startswith("mesh")
        truth = AWARD_TYPE.get(n)
        if "按需" in rec or "或" in rec:
            verdict = "partial(建議二選一)"
        else:
            verdict = "match" if (rec_mesh == (truth == "mesh")) else "mismatch"
        geo_eval[n] = {"recommend": "mesh" if rec_mesh else "region",
                       "award": truth, "verdict": verdict}

    # ④ 分鏡結構 vs Award 動畫命名
    anims = list(sk.get("animations", {}).keys())
    beat_kinds = set()
    tiers = set()
    for a in anims:
        m = re.search(r"_(In|Loop|Out)$", a)
        if m:
            beat_kinds.add(m.group(1))
        t = re.match(r"Award_(\w+?)_(In|Loop|Out)$", a)
        if t:
            tiers.add(t.group(1))
    proposed_beats = {b["beat"] for b in spec["3_motion_storyboard"]["beats"]}
    proposed_tiers = set(spec["3_motion_storyboard"]["tier_variants"] or [])
    storyboard = beat_structure(proposed_beats, beat_kinds, proposed_tiers, tiers)

    # ⑤ 露出項合理性:露出需「遮擋者移開」或「被遮件自己移出」二者之一有足量運動
    slot_bone = {s["name"].split("/", 1)[1]: s.get("bone") for s in slots}

    def moved(name):
        m = mag.get(slot_bone.get(name), {"tr": 0, "rot": 0, "sc": 0})
        return m, (m["tr"] >= 10 or m["rot"] >= 5 or m["sc"] >= 0.1)

    reveal_checks = []
    for it in spec["5_occlusion"]["reveal_on_move"]:
        occluder, revealed = it["hidden_by"], it["revealed_part"]
        mo, occ_moves = moved(occluder)
        mr, rev_moves = moved(revealed)
        reveal_checks.append({
            "revealed": revealed, "hidden_by": occluder,
            "occluder_moves": occ_moves, "revealed_part_moves": rev_moves,
            "revealed_bone_max": {"tr": round(mr["tr"], 1), "rot": round(mr["rot"], 1)},
            "actually_reveals": occ_moves or rev_moves})
    reveal_move_rate = (sum(1 for r in reveal_checks if r["actually_reveals"]) /
                        max(len(reveal_checks), 1))

    report = {
        "1_parts_recall": {"proposed": parts, "award": list(slot_names), "matched": matched,
                           "recall": round(recall, 3), "pass": recall >= 0.9},
        "2_effect_classification": {"per_part": eff_ok, "pass": all(eff_ok.values())},
        "3_geometry_vs_award": {"per_part": geo_eval,
                                "pass": all(v["verdict"] != "mismatch" for v in geo_eval.values())},
        "4_storyboard_structure": storyboard,
        "5_reveal_motion_check": {"checks": reveal_checks,
                                  "mover_move_rate": round(reveal_move_rate, 3),
                                  "pass": reveal_move_rate >= 0.9},
    }
    report["overall_pass"] = all(v["pass"] for k, v in report.items())
    return report


def selftest():
    """④ 召回判準的負對照:證放寬後的閘仍有鑑別力(非一律 pass)。

    放寬 beats_match(嚴格相等)為 beats_covered(award ⊆ proposed)只是為了容忍
    Award 未命名的主秀 PROPOSAL;閘必須仍能抓到**真正漏掉 Award 結構 beat** 的情形。
    """
    AWARD = {"In", "Loop", "Out"}
    TIERS = {"Super", "Mega", "Omg", "Legend"}
    PROPOSED = AWARD | {"burst", "cascade", "charge", "combo",
                        "hit", "squash", "twist", "wobble"}
    cases = []

    def expect(name, got, want):
        cases.append((name, got == want, got, want))

    pos = beat_structure(PROPOSED, AWARD, TIERS, TIERS)
    expect("POS covers Award -> pass", pos["pass"], True)
    expect("POS has 8 PROPOSAL extras", len(pos["beats_proposal_only"]), 8)
    expect("POS beats_match honestly False", pos["beats_match"], False)

    neg1 = beat_structure(PROPOSED - {"In"}, AWARD, TIERS, TIERS)
    expect("NEG drop In -> fail", neg1["pass"], False)
    expect("NEG drop In -> not covered", neg1["beats_covered"], False)

    neg2 = beat_structure({"In", "Out", "hit"}, AWARD, TIERS, TIERS)
    expect("NEG drop Loop -> fail", neg2["pass"], False)

    neg3 = beat_structure(PROPOSED, AWARD, set(), TIERS)
    expect("NEG 0 tiers -> fail", neg3["pass"], False)

    exact = beat_structure(AWARD, AWARD, TIERS, TIERS)
    expect("EXACT -> pass", exact["pass"], True)
    expect("EXACT -> beats_match True", exact["beats_match"], True)

    all_ok = all(ok for _, ok, _, _ in cases)
    for name, ok, got, want in cases:
        print(f"  [{'PASS' if ok else 'FAIL'}] {name}: got={got} want={want}")
    print(f"=== selftest {'PASS' if all_ok else 'FAIL'} ===")
    return all_ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--selftest", action="store_true",
                    help="跑 ④ 召回判準的負對照(證閘仍有鑑別力),不讀資產")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    rep = validate(a.psd, a.award)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
