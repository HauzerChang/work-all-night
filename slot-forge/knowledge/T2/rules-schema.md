# T2 規則 schema 設計筆記(v0.1)

## 結論
- rules.json 拆成 7 區:`game / board / evaluation / symbols / features / flow / (bet, limits, locales, openQuestions)`。
- **盤面與評估分離**:`board.rowsPerReel` 支援不等高(1070s 為 `[4,5,5,5,4]`),`evaluation.type` 在 lines / ways / cluster / scatterPays 間切換 → 供 T4 滾輪模組參數化。
- **Feature 用統一外型** `{id, type, trigger, params, phase}`,彼此以 `feature:<id>` 字串串接(例:collect 完成 → `feature:r3WildRespin`),validator 檢查引用存在。
- **不捏造數值**:來源未給的 symbol 標 `tbd: true`,問題寫進 `openQuestions`。

## 證據(本次唯一來源)
排程 prompt 給出的 1070s 規則摘要:5 軸 4-5-5-5-4 WAYS(2000 ways)、Cascade、BASE 倍數階梯 ×1·×2·×3·×5、指定符號蒐集 → R3 整軸 WILD RESPIN。
驗算:4×5×5×5×4 = 2000 ✔(validator S2 自動檢查)。
⚠️ `refs/` 尚無任何原始碼,以下皆未對照程式碼證實。

## params 對照表(依 feature.type)
| type | params | 說明 |
|------|--------|------|
| cascade | `refill`(dropFromTop / inPlace), `removeWinning` | 消除後補牌方式 |
| multiplierLadder | `ladder[]`, `advanceOn`(cascade/win), `capAtLast`, `resetOn`(spinStart/featureEnd) | 1070s:`[1,2,3,5]` |
| collect | `onComplete`(feature:<id>), 門檻放 trigger.count | 蒐集計量 |
| respin | `fullReelWild[]`(0-based 軸), `respins` | 1070s:R3 → `[2]` |
| freeGame | `spins`, `retrigger`, `multiplier` | — |
| buyFeature | `costX`, `target`(feature:<id>) | — |

## 語意檢查(validate_rules.py)
S1 軸數一致 · S2 ways 數 = Π rows · S3 lines 合法 · S4 symbol 引用 · S5 狀態全可達 · S6 feature 引用 · S7 倍數階梯遞增。
首跑即抓到範例缺陷:`RespinOutro` 無法從 Idle 抵達(respin 結束轉移漏寫)→ 已修。負向測試(軸數錯 / ways 錯 / 階梯亂序)三項皆 FAIL ✔。

## 坑 / 待確認
- 倍數階梯前進時點(每次 cascade?)與重置時點 —— 需對照 demo。
- cascade 中是否可觸發 respin、respin 中倍數是否沿用 —— 會影響 flow 結構。
- 事件命名需與 OMGSlotKit 對齊(T2 第二段生成程式碼時才能定)。
