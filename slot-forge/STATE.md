# slot-forge STATE

> 每次排程 session 開頭讀此檔;結束前更新。最後更新:2026-10-13(run #1)

## 最小閉環完成度:約 5%
(demo → rules.json 的 schema/驗證已可跑;腳手架、狀態機生成、滾輪、假後端皆未開始,且 T1 被 refs 阻塞)

## 軌道進度
| # | 軌道 | 狀態 | 備註 |
|---|------|------|------|
| T1 | 專案腳手架 | 未開始(阻塞) | 需 refs/1070s |
| T2 | 規則導入 → 流程 | **研究中**(rules schema v0.1 + validator + 1070s 範例 + slot-rules-ingest 草稿) | 第二段(狀態機程式生成)需 1070s 事件命名 |
| T3 | UI 生成 | 未開始 | |
| T4 | 滾輪模組 | 未開始(部分阻塞) | 需 1048s/1061s/1070s |
| T5 | 美術接口 | 未開始 | |
| T6 | 節奏 | 未開始 | |
| T7 | Spine | 未開始 | 可接 repo 內既有 spine-ai-editor 研究 |
| T8 | 數學模型 | 未開始 | |
| T9 | 協議 / 假後端 | 未開始 | spin 協議 schema 可獨立先做 |
| T10–T15 | 補充軌道 | 未開始 | |

## 上次做到哪
run #1:建立 slot-forge 目錄、`schemas/rules.schema.json`、`schemas/examples/1070s.rules.json`、`skills/slot-rules-ingest/`(SKILL.md + validate_rules.py + flow-patterns)、`knowledge/T2/rules-schema.md`、`maps/slot-forge-overview.md`。

## 待提供(阻塞項)
- [ ] `refs/1070s/` —— OMGSlotKit 範本(T1、T2-b、T4 主要依據)
- [ ] `refs/1048s/` —— core 來源、WAYS 實作
- [ ] `refs/1061s/` —— cascade 狀態設計、通用修正
- [ ] `refs/demo/fanren-xiuxian-slot.html` —— 規則來源(T2 反向驗證必需)

## 待確認問題
1. 1070s 符號清單與 paytable(目前範例全為 tbd)
2. 倍數階梯 ×1·×2·×3·×5:每次 cascade 前進一階?封頂 ×5?每 Spin 重置?
3. 蒐集門檻數量、計數範圍(單局 / 跨局累積)
4. R3 整軸 WILD RESPIN:次數、期間是否 cascade、倍數是否沿用
5. Feature 判定時點:cascade 鏈結束後才判定?
6. OMGSlotKit 的狀態/事件命名(決定 flow 事件名)
7. symbol / 滾輪框最終尺寸
8. 分支策略:排程 prompt 要求 `slot-forge/<YYYYMMDD-HHMM>-<track>` 分支,但執行環境指定開發分支 `claude/loving-planck-61g2xa`;run #1 遵循環境指定分支。若要改用 slot-forge/* 分支請告知。

## 下一步(依優先序,refs 未到時)
1. T9:spin request/response 協議 schema(`schemas/spin-protocol.schema.json`)+ 1070s 範例(cascade 多段結果、respin)—— 不依賴 refs
2. T9:最小 mock server(讀 rules.json 產隨機合法結果,ways + cascade 評估)→ 同時當 rules.json 的可執行驗證
3. T6:pacing.json schema 草稿
4. refs 到位後:立即轉 T1(1070s 結構盤點 → slot-scaffold)
