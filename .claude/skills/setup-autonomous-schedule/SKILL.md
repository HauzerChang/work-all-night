---
name: setup-autonomous-schedule
description: Guide a user through setting up a long-running, self-driving SCHEDULED task (a Routine) on Claude Code on the web — for research, development, maintenance, or recurring reports. Use when the user wants to "set up a schedule / routine / recurring task", "make a repo run autonomously", "have AI work on this daily/nightly", or asks how scheduling / cron / triggers work on Claude Code on the web. Walks through the checkpoint-and-resume architecture, prepares the repo files + SessionStart hook, and leads them through creating the Routine in the web UI.
---

# 引導他人設定自驅排程 (Routine)

你的任務:**手把手帶使用者**,把一個 repo 變成「交給 AI、按排程自動推進的長期任務」,
並在 Claude Code on the web 建立 Routine。完整教材在 `docs/自驅排程引導手冊.md`(若在本 repo);
本 skill 是「執行劇本」——告訴你怎麼帶人、依序做什麼、怎麼驗證。

## 核心觀念(務必先讓使用者理解)

雲端容器是**臨時的**(閒置/結束即回收,記憶體全丟)。所以不能「一個 session 跑好幾天」,
要用 **檢查點+續跑**:排程每次開**全新失憶**的 session → 讀 repo 檔案 → 推進一小塊 → commit 回 repo → 結束。
**一句話心法:要續跑的一切都得寫在 repo 裡。**

## 引導流程(依序進行,逐步確認)

### 步驟 1 — 釐清任務
問清楚:① 要排程做什麼?② 頻率(每天/每幾小時/每週)?③ 成果存哪個 repo?
頻率未定就建議「每天一次」(穩定省額度)。

### 步驟 2 — 讓 repo「可自驅」(檢查/建立這些檔案)
確認 repo 有以下;缺的就幫忙建(可抄本 repo 範本):
- `RULES.md`(操作守則/遞迴規則/升級政策)
- `PLAN.md`(階段目標/完成條件)
- `STATE.md`(**續跑核心**:現在在哪、下一步、未解問題)
- `prompts/run.md`(每次排程的指令;見下方範本)
- `knowledge/`、`log/`(長期記憶與紀錄)
- 依賴清單(`requirements.txt` 等)
- `.claude/hooks/session-start.sh` + `.claude/settings.json`(SessionStart hook 自動裝依賴)

`prompts/run.md` 必含:讀 RULES/PLAN/STATE → 推進**一個有界工作塊** → **可量測**自我驗證 →
更新 STATE/knowledge/log → **commit & push 回 default 分支** → 收尾不長跑。

### 步驟 3 — SessionStart hook(關鍵,讓新容器自動就緒)
建 `.claude/hooks/session-start.sh`:remote-only(`[ "${CLAUDE_CODE_REMOTE:-}" != "true" ] && exit 0`)、
idempotent、`pip install -r requirements.txt`、必要時寫 `PYTHONPATH` 到 `$CLAUDE_ENV_FILE`。
`chmod +x` 後**驗證**:`CLAUDE_CODE_REMOTE=true CLAUDE_PROJECT_DIR=$PWD CLAUDE_ENV_FILE=/tmp/e ./.claude/hooks/session-start.sh`。
在 `.claude/settings.json` 註冊 SessionStart hook。

### 步驟 4 — 分支策略(否則續跑會失敗)
Routine **從 default 分支 clone**、預設只能推 **`claude/` 開頭**分支。最省事:
**開發分支命名 `claude/xxx` 且設為 repo 的 default 分支**。這樣讀得到最新進度、改完推回同一條。
提醒在 run.md 明確「push 回 default 分支」。全部 commit & push 上去。

### 步驟 5 — 帶使用者在網頁建立 Routine
排程功能 = **Routines**,在 **https://claude.ai/code/routines**(web session 內 `/schedule` 隱藏,用網頁)。
唸給使用者照做:
1. 開 routines 頁 → **New routine**。
2. **Name + Prompt**:Prompt 貼「請依照 prompts/run.md 的指示推進這個專案。」;Model 選夠強的(研究/開發建議 Opus)。
3. **Select repositories**:加他們的 repo(每次從 default 分支 clone)。
4. **Select an environment**:一般 **Default**(Trusted 網路,允許套件庫)。要連自家服務才改 Custom/Full。
5. **Select a trigger → Schedule**:選頻率(時間用當地時區;會晚幾分鐘啟動屬正常)。自訂間隔用 CLI `/schedule update` 設 cron(最短 1 小時)。
6. **Connectors/Permissions**:移除用不到的 connector;一般不用開 unrestricted branch pushes。
7. **Create**。

### 步驟 6 — 立刻驗證(務必)
請使用者在詳情頁點 **Run now**,別等下次。檢查:repo 多一筆 commit、`log/` 新增一筆、`STATE.md` 下一步更新。
**提醒:綠燈 ≠ 成功**(只代表 session 沒崩);要看 transcript / commit 才算數。
若第一次跑有問題,依「常見問題」修正後再 Run now。

## 常見問題(快速對應)

- **每次從頭、沒記憶** → 進度沒推回 default 或沒更新 STATE.md。
- **缺套件/import 失敗** → hook 沒生效(`.claude/` 不在 default 分支 / 沒 chmod / requirements 錯)。
- **403 host_not_allowed** → 環境網路太緊;改 Custom 加網域或 Full。
- **推不上去** → 非 `claude/` 分支被擋;讓 default 是 `claude/xxx` 或開 unrestricted pushes。
- **`/schedule` 找不到** → 在 web session 內(用網頁 UI),或 API key 登入 / 設了 DISABLE_TELEMETRY / CLI 太舊。
- **綠燈沒進展** → 點進 run 看 transcript。

## 收尾
完成後告訴使用者:① 怎麼看進度(log / STATE / commits);② 它何時會找他(三種升級情況);
③ 怎麼調整(改頻率、暫停、或直接編輯 STATE/PLAN 改方向)。指向 `docs/自驅排程引導手冊.md` 作為完整參考。
