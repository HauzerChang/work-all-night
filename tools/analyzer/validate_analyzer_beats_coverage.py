#!/usr/bin/env python3
"""誠實守衛:AC4 由 exact-equal 放寬為 coverage(award ⊆ proposed)後,證此放寬
**非**「只為轉綠而弱化」——relaxed 判準仍能抓出「提案漏掉 Award 命名節拍」與
「Award 空集」兩種失敗,且端到端真值(robot_parts.psd ⇄ Award.json)確實通過。

背景:先驗庫 slot_bigwin 累積了 motion-primitive 主秀節拍(burst/hit/combo/charge/
cascade/wobble/squash/twist)這些 Award 於動畫層級未命名的 PROPOSAL,使 exact-equal
`proposed==award` 永遠 False(跨分類法誤比:相位 In/Loop/Out vs 運動基元)。見 STATE
未解問題。本閘鎖住 `beats_coverage` 的語意,避免未來再退回誤比或被退化情形矇混。

AC:
  C1 真值涵蓋:Award 命名節拍 {In,Loop,Out} ⊆ 先驗提案 → coverage True;且 proposed 嚴格
     超集(有 PROPOSAL 外溢節拍)→ proposed_only 非空(確認「超集」非「相等」)。
  C2 負對照(漏節拍):proposed 若少掉任一 Award 命名節拍 → coverage False。
  C3 負對照(退化):Award 命名節拍為空集 → coverage False(空集守衛,不得矇過)。
  C4 端到端:validate_analyzer_award.validate 整體 overall_pass 且 AC4 pass、beats_match True。
  C5 正對照(嚴格相等不再是必要條件):proposed==award(假想精簡先驗)仍 coverage True
     —— 證放寬是「相等 ⇒ 涵蓋」的真超集,向後相容舊語意(舊通過者仍通過)。
"""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from validate_analyzer_award import beats_coverage, validate

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PSD = os.path.join(ROOT, "assets", "robot_parts.psd")
AWARD = os.path.join(ROOT, "assets", "Award.json")

AWARD_NAMED = {"In", "Loop", "Out"}
PRIOR_LIKE = AWARD_NAMED | {"burst", "hit", "combo", "charge",
                            "cascade", "wobble", "squash", "twist"}


def main():
    r = {}

    # C1 真值涵蓋 + 嚴格超集
    cov = beats_coverage(AWARD_NAMED, PRIOR_LIKE)
    only = sorted(PRIOR_LIKE - AWARD_NAMED)
    r["C1_covers_and_strict_superset"] = {
        "coverage": cov, "proposed_only_proposal": only,
        "pass": cov is True and len(only) == 8}

    # C2 負對照:漏掉 Award 命名節拍之一(逐一拔掉 In/Loop/Out 都該 False)
    drops = {}
    for miss in sorted(AWARD_NAMED):
        proposed_missing = PRIOR_LIKE - {miss}
        drops[miss] = beats_coverage(AWARD_NAMED, proposed_missing)
    r["C2_missing_award_beat_fails"] = {
        "drop_result": drops, "pass": all(v is False for v in drops.values())}

    # C3 負對照:Award 空集 → 退化守衛 False
    degen = beats_coverage(set(), PRIOR_LIKE)
    r["C3_empty_award_fails"] = {"coverage": degen, "pass": degen is False}

    # C4 端到端真值
    rep = validate(PSD, AWARD)
    sb = rep["4_storyboard_structure"]
    r["C4_end_to_end_truth"] = {
        "overall_pass": rep["overall_pass"], "ac4_pass": sb["pass"],
        "beats_match": sb["beats_match"], "match_mode": sb.get("match_mode"),
        "award_beats": sb["award_beats"], "proposed_only": sb["proposed_only_proposal"],
        "pass": (rep["overall_pass"] is True and sb["pass"] is True
                 and sb["beats_match"] is True
                 and set(sb["award_beats"]) == AWARD_NAMED)}

    # C5 向後相容:exact-equal 的舊通過情形(proposed==award)在新判準下仍通過
    equal_cov = beats_coverage(AWARD_NAMED, set(AWARD_NAMED))
    r["C5_exact_equal_still_passes"] = {
        "coverage": equal_cov, "pass": equal_cov is True}

    r["overall_pass"] = all(v["pass"] for v in r.values())
    print(json.dumps(r, ensure_ascii=False, indent=2))
    raise SystemExit(0 if r["overall_pass"] else 1)


if __name__ == "__main__":
    main()
