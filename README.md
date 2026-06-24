# Autonomous Research Harness — "work-all-night"

這是一套讓 AI **長時間、跨 session 自主推進研究專案**的框架。

核心問題:雲端執行環境是臨時的(容器閒置或結束後會被回收),記憶體裡的進度會消失。
解法:**檢查點 + 續跑(checkpoint & resume)**。把所有進度狀態寫進這個 repo,
用排程定期觸發一個全新 session,每次讀狀態 → 推進一個階段 → commit 回來 → 結束。
下一次排程從斷點接續。

---

## 檔案結構

| 檔案 / 目錄 | 用途 |
|---|---|
| `RULES.md` | **遞迴規則 / 操作守則**。每次 session 開頭必讀,定義如何推進、如何分解子目標、何時停、如何更新狀態。 |
| `PLAN.md` | **階段目標 / 路線圖**。分階段的里程碑,每階段有明確的「完成條件」。 |
| `STATE.md` | **進度狀態(續跑核心)**。目前在哪個階段、下一步要做什麼、未解問題。每次跑完必須更新。 |
| `knowledge/` | **能力培訓 / 知識累積**。研究過程中學到的東西、結論、可重用的方法。 |
| `log/` | **每次執行的紀錄**。一次 session 一個檔案,方便回溯「上次做了什麼」。 |
| `prompts/run.md` | **每次排程要送的指令**。把這份內容當作 trigger 的 prompt。 |
| (其他) | 實際的研究產出 / 程式碼(目標開發)。 |

---

## 如何設定長期排程(Claude Code on the web)

這套框架的「自動推進」需要在 **web 介面**建立 Triggers / Scheduled session
(session 內無法建立會跨容器回收存活的排程)。設定步驟:

1. 在 Claude Code on the web 為這個 repo 建立一個 **Scheduled session / Trigger**。
2. 頻率:依需求設定(例如每天一次)。
3. 該排程的 prompt 設為:**「請依照 `prompts/run.md` 的指示推進這個研究專案。」**
   (或直接把 `prompts/run.md` 的內容貼進去。)
4. 完成。之後每到時間,平台會自動開一個新 session,讀取狀態、推進一階段、commit 回來。

文件:https://code.claude.com/docs/en/claude-code-on-the-web

---

## 目前狀態

> ⚠️ **待填入**:本專案來自 cowork 對話「Spine mesh system analysis」,
> 實際的研究目標、階段、遞迴規則與既有發現尚未匯入。
> 請把那段對話的交接摘要提供進來,會被整理進 `PLAN.md` / `RULES.md` / `knowledge/`。
