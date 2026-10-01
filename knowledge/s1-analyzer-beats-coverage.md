# S1 分析器 AC4 分鏡對齊:exact-equal → coverage(誠實修一條 pre-existing RED)

> candidate ENV-1(2026-10-01 run 001)。修 STATE 長期掛著的「未解問題 / pre-existing RED」:
> `tools/analyzer/validate_analyzer_award.py` 的 `4_storyboard_structure` AC 失敗 → analyzer gen 閘
> 兩個 readiness 條目同步 RED。非 J-4 造成(J-4 純加性),是先驗累積造成的**判準誤比**。

## 根因:跨分類法的 exact-equal 誤比

`validate_analyzer_award.py` AC4(分鏡結構 vs Award 動畫命名)原本:
```python
beats_ok = proposed_beats == beat_kinds   # exact-equal
```
- `beat_kinds` = 從 Award 動畫名 `Award_<tier>_<In|Loop|Out>` 以 regex `_(In|Loop|Out)$` 抽出
  → **只有相位級節拍** `{In, Loop, Out}`(Award 於動畫層級就只命名這三相)。
- `proposed_beats` = `genre_priors.slot_bigwin` 先驗提出的分鏡 beat keys。隨研究推進,先驗**累積**了
  8 個 motion-primitive 主秀節拍(burst/hit/combo/charge/cascade/wobble/squash/twist),外加 In/Loop/Out
  → `{In, Loop, Out, burst, hit, combo, charge, cascade, wobble, squash, twist}`(11 個)。

兩者是**不同分類法**:Award 的是「**相位**」(win 序列的三段),先驗的額外 8 個是「**運動基元**」
(落在 In/Loop/Out 時間軸**內**的內容細化,Award 不在動畫命名層級曝露)。exact-equal 把這兩種軸硬比,
且先驗只會愈加愈多 → `proposed == award` **永遠 False**。這不是分析器變差,是判準錯了。

實測(修前):`proposed_beats` 11 個、`award_beats` 3 個、`beats_match=False`、`tiers_hit` 4/4 完美、
`overall_pass=False`(exit 1 → RED)。

## 修法:涵蓋(coverage,award ⊆ proposed)+ 退化守衛

正確的對齊判準是「Award 命名的節拍都被先驗提出」(涵蓋),非相等:
```python
def beats_coverage(award_beats, proposed_beats):
    award, proposed = set(award_beats), set(proposed_beats)
    return len(award) > 0 and award.issubset(proposed)   # 空集守衛 + 子集
```
- `award ⊆ proposed`:`{In,Loop,Out} ⊆ {11 個}` → **True**(本來就該過)。
- `len(award) > 0`:退化守衛 —— Award 未命名任何節拍(空集)時,空集是任意集合子集會**矇過**,須擋掉。
- 多出的 8 個運動基元以 `proposed_only_proposal` 在報告中**誠實列出**為 PROPOSAL(Award 未命名),不藏匿。

report `4_storyboard_structure` 新增 `match_mode: "coverage(award ⊆ proposed)"` 與
`proposed_only_proposal`,`beats_match` 語意改為「涵蓋」,`pass = beats_covered and tiers_hit≥1`。

這與 `analyze_target.build_storyboard` 既有的 `status="PROPOSAL(先驗已對真值驗證覆蓋)"` 一致,也呼應
`validate_priors` 對 coverage / `prior_beats_unused` 的處理(先驗提出但真值未命名 = PROPOSAL,不當失敗)。

## 誠實守衛閘(證「放寬≠為轉綠而弱化」)

`validate_analyzer_beats_coverage.py` **5 AC 全 PASS**(gate=eval,驗判準本身可信):
- **C1** 真值涵蓋 + **嚴格超集**:coverage True 且 `proposed_only` 恰 8 個(確認是「超集」非「相等」)。
- **C2 負對照(漏節拍)**:逐一拔掉 In/Loop/Out 任一 → coverage **False**(漏 Award 命名節拍抓得到)。
- **C3 負對照(退化)**:Award 空集 → coverage **False**(空集守衛生效)。
- **C4 端到端真值**:robot_parts.psd ⇄ Award.json 跑 `validate()` → `overall_pass=True`、AC4 pass、
  `award_beats=={In,Loop,Out}`。
- **C5 向後相容**:`proposed==award`(假想精簡先驗)在新判準下**仍** True —— 放寬是「相等 ⇒ 涵蓋」的
  真超集,舊 exact-equal 會過的情形新判準全都過(不破壞既有語意,只多接納合法的超集)。

## 關鍵發現

- **「閘永遠 RED」先看判準是否跨分類法誤比**:兩個不同語意軸(相位 vs 運動基元)被 exact-equal 硬比,
  且其中一軸(先驗)單調增長 → 結構性永遠 False。放寬成 coverage 是對齊語意,不是降標準。
- **放寬判準必配負對照**:coverage 比 exact-equal 寬,必須證它仍能抓「漏 Award 命名節拍」(C2)與
  「Award 空集矇過」(C3),否則就是偷偷弱化。C5 再證放寬向後相容(真超集)。
- **誠實不靠隱藏**:多出的運動基元不是刪掉讓集合相等,而是明列為 `proposed_only_proposal` PROPOSAL
  (Award 未於動畫層級命名),判準只要求涵蓋 Award 真正命名的部分。

## 影響

- readiness 兩個 analyzer gen 條目(`spine-asset-forge` / `spine-target-analysis` 區塊)由 RED → GREEN。
- 新增 cap `analyzer_beats_coverage`(eval,L2)併入 `spine-target-analysis`(仍 HOLD:分析器生成能力策略不變)。
- STATE「未解問題」該條標記已解。注意舊里程碑「N 閘全綠」原本即指**動畫/功能閘**,此 PSD analyzer
  gen 閘的環境相依 RED 與那些里程碑無關,本次一併釐清。
