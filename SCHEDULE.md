# 每日排程設定指南 (照著做)

讓這個研究專案每天自動推進一步。**排程 trigger 必須在 Claude Code on the web 介面建立**
(session 內建的排程活不過容器回收)。以下是全部步驟。

## 前置(已完成 ✅)

- ✅ `requirements.txt` — CPU 套件清單。
- ✅ `.claude/hooks/session-start.sh` + `.claude/settings.json` — 每個新 session 自動裝套件、設 PYTHONPATH。
- ✅ `prompts/run.md` — 每次執行要做什麼。
- ✅ `RULES.md` / `PLAN.md` / `STATE.md` — 守則、路線圖、續跑狀態。

> ⚠️ **分支機制(2026-06-26 更正,依官方文件 /en/routines)**:Claude Code **Routines 沒有「選 branch」欄位**,
> 每次執行**一律從 repo 的 default branch clone**(文件原文:"cloned ... starting from the default branch ...
> unless your prompt specifies otherwise")。預設只能 push 到 `claude/` 開頭的分支。
> 因此要讓排程跑在開發分支 `claude/zealous-noether-y2ecwu` 上,二選一(見下)。

## 建立 / 設定排程(Routines)

排程功能 = **Routines**,在 [claude.ai/code/routines](https://claude.ai/code/routines) 管理(或 CLI `/schedule`)。

### 讓排程接續開發分支 `claude/zealous-noether-y2ecwu` — 二選一

**方案 B(推薦,最省事):把 GitHub repo 的 default branch 改成 `claude/zealous-noether-y2ecwu`。**
- GitHub → `HauzerChang/work-all-night` → **Settings → General**(或 **Branches**)→ "Default branch" → 點切換圖示 →
  選 `claude/zealous-noether-y2ecwu` → **Update**。
- 之後 Routine 自動從它 clone,Prompt 維持簡單一句即可。
- 一次設定永久生效;符合 routine「從 default clone」的機制。

**方案 A(不碰 GitHub 設定):在 Routine 的 Instructions/Prompt 開頭加切分支指令。**
- 位置:[claude.ai/code/routines](https://claude.ai/code/routines) → 點該 routine → **鉛筆圖示 (Edit routine)** → 改 **Instructions**;或 CLI `/schedule update`。
- Prompt 用這段(routine 從 default clone 後,自己切到開發分支):
  ```
  請先切到開發分支再開始:
  git fetch origin claude/zealous-noether-y2ecwu
  git checkout claude/zealous-noether-y2ecwu
  git pull origin claude/zealous-noether-y2ecwu
  然後依照 prompts/run.md 的指示推進這個研究專案,完成後 commit 並 push 回 claude/zealous-noether-y2ecwu。
  ```
- `claude/zealous-noether-y2ecwu` 是 `claude/` 開頭 → routine 預設就能 push,**不需**開啟 "Allow unrestricted branch pushes"。

### 建立步驟(Routines 表單)

1. 到 [claude.ai/code/routines](https://claude.ai/code/routines) → **New routine**。
2. **Name**:取個名(如 "Spine 研究每日推進")。**Prompt/Instructions**:用上面方案 A 的那段(或方案 B 時用簡單一句
   `請依照 prompts/run.md 的指示推進這個研究專案。`)。
3. **Repositories**:加 `HauzerChang/work-all-night`。
4. **Environment**:選有網路/套件的環境(Default 即可;hook 會自動裝 CPU 套件)。
5. **Trigger**:選 **Schedule** → 每天一次(時區自動換算)。最短間隔 1 小時。
6. **Create**。可按 **Run now** 立即試跑一次,開該 run 的 session 看 transcript 確認。

> 注意:run 列表顯示綠燈只代表 session 正常啟動結束,**不代表任務成功**;要開 run 看 transcript / 看 `log/` 確認。

## 它每天會做什麼

依 `prompts/run.md`:讀 `STATE.md` 的下一步 → 推進**一個有界工作塊** → 用評估器自我驗證 →
更新 `STATE.md` / `knowledge/` / `log/` → commit & push → 結束。下一天從新斷點接續。

## 你如何掌握進度

- **看 `log/`**:一次 run 一個檔,內含每個工作塊一個小節。
- **看 `STATE.md`**:永遠是「目前到哪、下一步」。
- **看 commit 歷史**:每個工作塊一筆(一次 run 6–8 筆)。
- **被找**:只有三種情況它會停下等你(見 `RULES.md` 升級政策):不可自決岔路、超預算卡關、里程碑審查。

## 單次 run 的工作量(2026-07-01 起)

一次 run 推進 **6–8 個有界工作塊**(逐塊 commit,見 `RULES.md`「單次執行的工作量」)。
即使維持每天 1 次,每天產出也 ≈ 6–8 塊。若要再放大,才需疊加下面的「調整頻率」。

## 調整頻率(目前每天一次 → 改每 N 小時)

排程 = **Routines**,在 [claude.ai/code/routines](https://claude.ai/code/routines) 管理(或 CLI `/schedule`)。

1. 到 [claude.ai/code/routines](https://claude.ai/code/routines),找到這個 routine(如 "Spine 研究每日推進")。
2. 點該 routine → **鉛筆圖示 (Edit routine)**(CLI 則 `/schedule update`)。
3. 找 **Trigger** 區塊 → **Schedule**:把「每天一次 (Daily)」改成 **每 N 小時 (Every N hours)**。
   - **最短間隔 = 1 小時**(平台限制)。
   - 常用:每 6 小時 = 4 run/天(≈ 24–32 塊/天);每 4 小時 = 6 run/天;每 1 小時 = 24 run/天。
4. **Save**。可按 **Run now** 立即試跑一次驗證。

> ⚠️ token 成本 ≈ **run 次數 × 每 run 塊數**,大致線性。建議先用「每 run 6–8 塊 + 維持每日」觀察一天的
> 帳號用量(claude.ai Usage/Billing),再決定要不要提高頻率——避免頻率與塊數同時拉高導致額度暴衝。

## 其他調整

- **想暫停**:在 [claude.ai/code/routines](https://claude.ai/code/routines) 停用該 trigger。
- **改每 run 塊數**:編輯 `RULES.md`「單次執行的工作量」的「6–8 個」數字 + `prompts/run.md` 對應處。
- **改方向**:直接編輯 `STATE.md` 的「下一步動作」或 `PLAN.md`,下次排程就會照新方向走。

## 路線圖(排程會依序推進,見 PLAN.md)

S3 mesh 生成器(進行中,curtain_left 已過)→ 推廣 4 mesh → S1 反推分析器 → S2 評估器套件 →
S4 切圖+補圖 → S5 骨架半自動。
