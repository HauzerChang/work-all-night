---
name: slot-rules-ingest
description: 讀 slot demo 網站 / HTML(內含規則與表演示意)→ 產出符合 slot-forge/schemas/rules.schema.json 的 rules.json,並驗證盤面、WAYS/Lines、cascade、倍數、蒐集、Respin、Free Game 與狀態機的一致性。觸發詞:「規則導入」「rules.json」「demo 轉規則」「讀 demo 網站」「slot 規則 schema」「slot-rules-ingest」。
---

# slot-rules-ingest(草稿 v0.1 — 研究中)

> slot-forge 技能鏈 T2 的第一段:**demo → rules.json**。第二段(rules.json → Cocos 狀態機程式碼)待 1070s refs 提供後補。

## Input
- demo 網址或本機 HTML(例:`refs/demo/fanren-xiuxian-slot.html`)
- (選填)專案代號 `game.code`、語系清單

## 職責節點(MAP)
| 節點 | 職責 | 分工模式 | 產出 |
|------|------|----------|------|
| N1 抓取 | 取 HTML + 內嵌 JS;網址則下載保存快照 | 單一 agent | `demo.snapshot.html` |
| N2 規則抽取 | 從 DOM 文字 / JS 常數抽:盤面、評估方式、paytable、reel strip、feature 參數 | 單一 agent,讀 JS 常數優先於讀說明文字 | 草稿 rules.json |
| N3 流程推導 | 由 features 推狀態與轉移(Idle→Spin→Stop→Evaluate→Win→Cascade→…) | 單一 agent,套 `references/flow-patterns.md` 樣板 | `flow` 區段 |
| N4 驗證閘 | `scripts/validate_rules.py`(schema + S1–S7 語意) | 機械化 | PASS/FAIL 報告 |
| N5 缺口回報 | 無法從來源確認者寫入 `openQuestions`,symbol 標 `tbd` | 單一 agent | 待確認清單 |

N4 FAIL → 回 N2/N3 修正,最多 3 輪;仍 FAIL 則回報人工。

## Output
- `rules.json`(通過 validator)
- `openQuestions` 清單 → 併入 `slot-forge/STATE.md` 待確認問題

## 驗收方法
1. `python3 scripts/validate_rules.py rules.json` → PASS
2. 反向驗證(軌道 T2 驗收):用 1070s 的 demo 跑本 skill,產出的 rules.json 與 `schemas/examples/1070s.rules.json`(人工校正後的金標準)比對 board / evaluation / features 等價
3. 不得出現來源沒有的數值(paytable、門檻等):無來源 → `tbd` + `openQuestions`

## 已知限制
- demo HTML 尚未提供(`refs/` 空),N1/N2 未實測;目前只有 schema + validator + 人工範例。
- 狀態機事件名(`spinPressed`、`resultReceived`…)為暫定,需對照 1070s 的 OMGSlotKit 實際事件命名後統一。
- guard 運算式目前為自由字串,validator 只檢查 `feature:<id>` 引用。
