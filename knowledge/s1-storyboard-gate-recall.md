# S1 分鏡結構閘：從「逐字相等」修正為「對 Award 相位的 recall(subset)」

> 2026-09-30 run 002。修 `tools/analyzer/validate_analyzer_award.py` 的 `④ 4_storyboard_structure`
> 這條**pre-existing false-RED**閘。屬評估器可信度修復(非新增生成能力)。

## 問題(false RED 的成因)

`validate_analyzer_award.py` 的 ④ 分鏡結構閘原本用**逐字相等**判斷：

```python
beats_ok = proposed_beats == beat_kinds     # 舊(錯)
```

- `beat_kinds`：從 **Award 動畫命名**抽相位後綴 `_(In|Loop|Out)$` → `{In, Loop, Out}`(Award 只有這三個相位)。
- `proposed_beats`：分析器 `spec["3_motion_storyboard"]["beats"]` 的 `beat` 欄集合。**隨累積先驗庫
  `genre_priors.slot_bigwin` 一路長大**,現為 `{In, Loop, Out, burst, cascade, charge, combo, hit,
  squash, twist, wobble}`(3 相位 + 8 主秀 beat)。

因分析器**提得比 Award 多**(8 個主秀 beat 於 Award 無命名),`==` 永久 False → 閘永久 RED。
但這是「提案更豐富」不是「提錯」:`proposed_beats ⊇ award_beats`(超集)。舊 `==` 把「提得更多」誤判成「提錯」。

- **不是 J-4/J-3 造成**:先前已用 `git stash` 在 clean tree(59cf2b2)確認同樣 RED(所有純加性 tier 候選都不新增 beat)。
- **check_readiness 影響**:`analyze_target`(核心 gen L2)cap 被此閘拖成 RED,出現在**兩個區塊**
  (「目標圖/PSD→可載入 Spine 素材」「反推分析/需求規格」),讓 readiness 儀表板出現**假失敗**。
  `run_validator` 以 `returncode==0` 判 GREEN,而閘 `raise SystemExit(1 if not overall_pass)` → 兩 cap RED。

## 修法(objective evaluator-correctness fix)

分鏡結構閘的**正確語意 = 對 Award 真值相位結構的 recall(subset)**,不是逐字相等:
分析器提案須**涵蓋** Award 實際使用的每個相位;額外提出的主秀 beat 於 Award 無命名 = **PROPOSAL**
(更豐富的分鏡提案,非錯誤),明列 `prior_beats_unused` 誠實揭示。

```python
def beats_cover(award_beats, proposed_beats):
    return set(award_beats) <= set(proposed_beats)   # award ⊆ proposed

beats_ok = beats_cover(beat_kinds, proposed_beats)
prior_beats_unused = sorted(proposed_beats - beat_kinds)
```

report 新增兩欄(誠實 + 相容):`award_beats_covered`(= beats_ok)、`prior_beats_unused`
(提案中未被 Award 命名者 = PROPOSAL 邊界);`beats_match` 保留但語意改為 subset。

### 為什麼是 objective(非 A 類創意岔路)

- Award 真值相位 `{In,Loop,Out}` 是**時間軸相位**;先驗提出的 `{burst,cascade,...}` 是**主秀運動 beat**——
  兩者是不同粒度/命名體系。逐字相等從一開始就在比不同層級的東西。正確的召回問題是「分析器的分鏡是否
  涵蓋真值相位?」→ 涵蓋即通過;額外提案誠實標為 PROPOSAL。方向明確,不涉美術主觀決定。

## 閘非 vacuous:負對照(`--selftest`)

放寬為 subset 後**方向仍在**:漏掉任一 Award 相位即 False。`validate_analyzer_award.py --selftest`
(不需資產)跑 6 例全 PASS:
- 正對照:超集涵蓋全相位 → True;邊界:恰等(無額外提案)→ True。
- 負對照:漏掉 Loop / 漏掉 In+Out / 空提案 / 提案完全不含相位(只有主秀 beat)→ 皆 False。

## 驗收結果(AC-first)

- **AC1** 修後 `validate_analyzer_award.py` exit 0、`4_storyboard_structure.pass=True`、`overall_pass=True`。✅
- **AC2** `beats_match` 語意=subset(`{In,Loop,Out} ⊆ {In,Loop,Out,burst,...}`=True)。✅
- **AC3** report 新增 `prior_beats_unused=[burst,cascade,charge,combo,hit,squash,twist,wobble]`(誠實揭示 PROPOSAL)。✅
- **AC4** `--selftest` 正/負對照 6 例全 PASS(閘非因放寬而失效)。✅
- **AC5** 全 readiness 回歸:`analyze_target` 兩 cap RED→GREEN,無其他 GREEN→RED。✅(見 log/2026-09-30-002.md)

## honest boundary(仍在)

- 累積先驗提出的 8 個主秀 beat 於 Award 無命名,屬 **PROPOSAL**(單一真值資產 Award 只有 In/Loop/Out
  三相位;要驗「這些主秀 beat 是否對得上真實成品」需**更豐富分鏡的真值資產**,屬使用者資源)。
- 本次只修**評估器語意**,未改分析器/生成器輸出(純評估器可信度修復)。
