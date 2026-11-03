# 狀態機樣板(依 features 組合)

| features 組合 | 追加狀態 | 關鍵轉移 |
|---------------|----------|----------|
| 基本(無 feature) | Idle, Spin, Stop, Evaluate, Win | Evaluate --hasWin--> Win --winShown--> Idle |
| + cascade | Cascade | Win --winShown--> Cascade --refillDone--> Evaluate(循環直到 noWin) |
| + multiplierLadder(advanceOn=cascade) | — | 在 Cascade 進入時 ladder 前進一階;spinStart 重置 |
| + respin(由 collect 觸發) | RespinIntro, Respin, RespinOutro | Evaluate --noWin[phase==base && triggered]--> RespinIntro;Respin 週期內 Evaluate --noWin[respinsLeft==0]--> RespinOutro |
| + freeGame | FreeIntro, Free, FreeOutro | 同 respin,phase==free |
| + buyFeature | — | Idle --buyPressed--> FreeIntro / RespinIntro |

原則:**Feature 判定一律在 cascade 鏈結束(noWin)後**,避免 cascade 中途切場。(1070s 實際時點待 refs 確認)
