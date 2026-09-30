#!/usr/bin/env python3
"""S1 分析器對真值校驗 — robot_parts.psd 反推規格 ⇄ Award 真實生產 spine。

Award 是 robot_parts 的真實成品(機器人拆件 5 slot / 綁 5 骨 / 12 動畫 = 4 檔位×In/Loop/Out)。
用它當真值,量化 analyze_target.py 的反推召回:
  ① 可動件召回:反推件 vs Award 機器人拆件 slot(名稱對應)。
  ② 特效分類:光暈 應判為特效;其餘結構。
  ③ mesh/region 建議 vs Award 實際 attachment type。
  ④ 分鏡結構:提案分鏡須 **涵蓋(recall/subset)** Award 動畫命名的每個相位(In/Loop/Out);
     額外提出的主秀 beat(來自累積先驗庫)於 Award 無命名 = PROPOSAL(prior_beats_unused,誠實揭示)。
  ⑤ 露出項合理性:各 reveal 的 mover 骨在 Award 是否真的有足量運動(位移/旋轉)。
"""
import argparse, json, os, sys, re
sys.path.insert(0, os.path.dirname(__file__))
from analyze_target import analyze

def beats_cover(award_beats, proposed_beats):
    """分鏡結構閘的核心判準:分析器提案是否**涵蓋**Award 真值的每個相位(recall/subset)。

    True ⟺ award_beats ⊆ proposed_beats。額外提案的主秀 beat 不算錯(屬 PROPOSAL);
    但漏掉任一 Award 相位即 False(負對照方向仍在,閘不因放寬而失效)。
    """
    return set(award_beats) <= set(proposed_beats)


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
    # 分鏡結構閘語意 = 對 Award 真值相位結構的 **recall(subset)**,非逐字相等。
    # 分析器提出的分鏡須「涵蓋」Award 實際使用的每個相位(In/Loop/Out);額外提出的主秀
    # beat(burst/cascade/combo/... 來自累積先驗庫 genre_priors.slot_bigwin)於 Award 並無
    # 命名 → 屬 PROPOSAL(更豐富的分鏡提案,非錯誤),明列於 prior_beats_unused 誠實揭示。
    # 舊版用 `==`(逐字相等):先驗庫一長就永久 RED,誤把「提得更多」當「提錯」。
    # 負對照方向仍在:分析器若漏掉任一 Award 相位 → beat_kinds ⊄ proposed_beats → False
    # (見 --selftest 的 dropped-phase 負對照,證閘非因放寬而失效)。
    beats_ok = beats_cover(beat_kinds, proposed_beats)   # award ⊆ proposed
    prior_beats_unused = sorted(proposed_beats - beat_kinds)
    tiers_hit = proposed_tiers & tiers

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
        "4_storyboard_structure": {"proposed_beats": sorted(proposed_beats),
                                    "award_beats": sorted(beat_kinds),
                                    "award_beats_covered": beats_ok,
                                    "beats_match": beats_ok,  # 語意=recall(subset),見 beats_cover
                                    "prior_beats_unused": prior_beats_unused,  # PROPOSAL 邊界(誠實揭示)
                                    "award_tiers": sorted(tiers), "tiers_hit": sorted(tiers_hit),
                                    "pass": beats_ok and len(tiers_hit) >= 1},
        "5_reveal_motion_check": {"checks": reveal_checks,
                                  "mover_move_rate": round(reveal_move_rate, 3),
                                  "pass": reveal_move_rate >= 0.9},
    }
    report["overall_pass"] = all(v["pass"] for k, v in report.items())
    return report


def selftest():
    """④ 分鏡結構閘的正/負對照 —— 證放寬為 subset 後閘仍非 vacuous。

    正對照:分析器提案為 Award 相位的超集(涵蓋 In/Loop/Out + 額外主秀 beat)→ True。
    負對照:分析器漏掉任一 Award 相位(如缺 Loop)→ 必須 False(否則閘失效)。
    邊界:提案==Award(無額外提案)→ True;空提案 → False。
    """
    award = {"In", "Loop", "Out"}
    rich = {"In", "Loop", "Out", "burst", "cascade", "combo", "hit"}
    cases = [
        ("正對照:超集涵蓋全相位", beats_cover(award, rich), True),
        ("邊界:恰等(無額外提案)", beats_cover(award, award), True),
        ("負對照:漏掉 Loop", beats_cover(award, rich - {"Loop"}), False),
        ("負對照:漏掉 In+Out", beats_cover(award, {"Loop", "burst"}), False),
        ("負對照:空提案", beats_cover(award, set()), False),
        ("負對照:提案完全不含相位(只有主秀 beat)", beats_cover(award, {"burst", "hit"}), False),
    ]
    ok = True
    for name, got, want in cases:
        good = (got == want)
        ok = ok and good
        print(f"  [{'PASS' if good else 'FAIL'}] {name}: beats_cover={got} (want {want})")
    print(f"selftest {'PASS' if ok else 'FAIL'}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--award", default="assets/Award.json")
    ap.add_argument("--selftest", action="store_true",
                    help="只跑 ④ 分鏡結構閘的正/負對照(不需資產),證閘非 vacuous")
    a = ap.parse_args()
    if a.selftest:
        raise SystemExit(0 if selftest() else 1)
    rep = validate(a.psd, a.award)
    print(json.dumps(rep, ensure_ascii=False, indent=2))
    raise SystemExit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
