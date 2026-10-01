# S1 分析器真值閘 ④ 分鏡結構判準:嚴格相等 → 召回(修 pre-existing RED)

> candidate ENV-fix(2026-10-01 run 001)。修掉累積數個 session 的 pre-existing RED:
> `tools/analyzer/validate_analyzer_award.py` 的 `4_storyboard_structure` 閘。純閘語意修正、
> **不動任何生成器**。

## 問題(為何 RED)

`validate_analyzer_award.py` ④ 分鏡結構原判準是**嚴格集合相等**:

```python
beats_ok = proposed_beats == beat_kinds   # 舊:exact-equal
```

- `proposed_beats` = 分析器(`analyze_target` 經 `genre_priors.slot_bigwin`)提出的 beat 集。
- `beat_kinds` = Award 真實動畫命名中出現的結構 beat = **只有 `{In, Loop, Out}`**
  (Award 動畫命名 `Award_<tier>_In/Loop/Out`)。

隨著主秀 beat 生成系列(E/H/I/J…G-4''''''…)一路把節拍併進 `genre_priors.slot_bigwin`,
`proposed_beats` 現在是 **11 個**:`{In, Loop, Out, burst, cascade, charge, combo, hit,
squash, twist, wobble}`。那多出來的 **8 個主秀 beat 在 Award 沒有對應的命名動畫**
(Award 只有 In/Loop/Out 結構幀 + 4 檔位),於是 `proposed == award` 永遠 False → 閘 RED。

**這不是回歸**:用 `git stash` 在 clean J-3 tree(59cf2b2)上確認同樣 RED,與 J-4 無關;
純粹是「分析器提出的 PROPOSAL 主秀節拍」被一個過嚴的 exact-equal 判準誤判為失敗。
`check_readiness.py` 不呼叫 `sys.exit` → 總是 exit 0,**不能用 exit code 判 RED**(須看各閘
`閘:GREEN/RED`);此閘在 check_readiness 被兩個 skill 區塊引用(line 58、88)→ 顯示為 **2 個 RED**。

## 修法(召回,非嚴格相等)

正確語意 = **召回(recall)**:Award 命名的每個結構 beat 都被提出即可(`award ⊆ proposed`);
分析器額外提出、Award 未命名的主秀 beat 是 **PROPOSAL**,honestly 列出但不算 match 失敗 ——
**完全比照 `validate_priors.py` 既有的 `prior_beats_unused` + `coverage>=0.9` 處理**(那裡也早已
不是 exact-equal,而是召回門檻 + 誠實列出未對上的先驗 beat)。

抽出純函數 `beat_structure(proposed_beats, award_beats, proposed_tiers, award_tiers)`
(可獨立測試),回報:

- `beats_covered` = `award ⊆ proposed`（**真正判準**:結構 beat 全召回）
- `beats_match`   = `proposed == award`（**仍一併回報作透明佐證**,現為 False=有 PROPOSAL 多出)
- `beats_proposal_only` = `sorted(proposed − award)` = 那 8 個主秀 PROPOSAL(誠實攤開)
- `pass` = `beats_covered and len(tiers_hit) >= 1`

`beats_match` 保留在輸出裡 → 讀報告的人一眼看到「嚴格相等=False、但召回=True、多出的正是這 8 個
PROPOSAL」,**沒有藏任何東西**。docstring ④ 同步改為「是否**涵蓋** Award 動畫命名結構(召回)」。

## 閘仍可信(負對照 = `--selftest`)

放寬判準最大的風險是「閘失去鑑別力(一律 pass)」。故把負對照固化成
`validate_analyzer_award.py --selftest`(純邏輯、不讀資產,future session 可重跑):

- **POS**:真實累積提案(涵蓋 In/Loop/Out + 8 PROPOSAL)→ `pass=True`、`beats_match=False`、
  `proposal_only` 恰 8 個。
- **NEG 漏結構 beat**:提案少了 `In`(Award 有的)→ `beats_covered=False` → `pass=False`
  (證**真漏召回時閘仍 fail**)。
- **NEG 漏 Loop/Out**:同上 fail。
- **NEG 0 tiers**:涵蓋 beat 但命中 0 檔位 → fail(保留 tier 條件)。
- **EXACT**:提案==Award(無 PROPOSAL 多出)→ `pass=True` 且 `beats_match=True`
  (證放寬只「加容忍 PROPOSAL extras」,未改變嚴格情形的行為)。

`--selftest` 9 條斷言全 PASS。

## 結果

- `validate_analyzer_award.py` → `overall_pass=True`、exit 0、`4_storyboard_structure.pass=True`。
- `check_readiness.py`:原本的 **2 個 PSD analyzer `gen` 閘 RED → GREEN**,其餘動畫/功能閘
  全綠不動(0 GREEN→RED)。自此 repo **真正全綠**,不再需要每個里程碑附「另有 2 個 analyzer 閘 RED」的 caveat。

## honest boundary

- 這是**閘語意修正**,不是新能力:分析器對 Award 的件召回/特效分類/幾何/露出判準全未動;
  主秀 beat 仍是先驗手感 PROPOSAL(Award 無真值命名),此修正只是讓閘**誠實地**把它們標為
  PROPOSAL 而非 match 失敗(與 `validate_priors` 一致)。
- `spine-anim-forge` 區塊**仍 HOLD**(運動基元先驗、單一真值資產,防固化)—— 本修正不改成熟度。
- 若未來拿到**有命名主秀動畫的第二個真值資產**,可把對應 beat 從 `beats_proposal_only` 升級為
  被 `beat_kinds` 命中的召回項(屆時 coverage 自然提高)。
