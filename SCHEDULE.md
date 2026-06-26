# 每日排程設定指南 (照著做)

讓這個研究專案每天自動推進一步。**排程 trigger 必須在 Claude Code on the web 介面建立**
(session 內建的排程活不過容器回收)。以下是全部步驟。

## 前置(已完成 ✅)

- ✅ `requirements.txt` — CPU 套件清單。
- ✅ `.claude/hooks/session-start.sh` + `.claude/settings.json` — 每個新 session 自動裝套件、設 PYTHONPATH。
- ✅ `prompts/run.md` — 每次執行要做什麼。
- ✅ `RULES.md` / `PLAN.md` / `STATE.md` — 守則、路線圖、續跑狀態。

> ✅ **分支策略(2026-06-26 定案)**:排程 trigger **直接指向開發分支 `claude/zealous-noether-y2ecwu`**,
> 不再走「合併進 default」流程。每次排程從此分支開、推進、push 回此分支,下次接續 —— 零 merge 摩擦。
> SessionStart hook 與所有設定都在此分支上(✅ 已 push),故 hook 對排程 session 生效。

## 建立排程(web 介面)

1. 開 Claude Code on the web,進到 `HauzerChang/work-all-night` 的環境。
2. 找 **Scheduled sessions / Triggers**(排程)功能,新建一個。
3. 填入:
   - **Repository**:`HauzerChang/work-all-night`
   - **Branch**:`claude/zealous-noether-y2ecwu` ← **務必選這條開發分支**(非 default)。
   - **Schedule / 頻率**:每天一次(例:每天 09:00;時區依你)。
   - **Prompt**:貼這一句 ——
     ```
     請依照 prompts/run.md 的指示推進這個研究專案。
     ```
4. 儲存。完成後,平台每天到點會自動開一個新 session,讀狀態 → 推進一個工作塊 → commit 回來。

## 它每天會做什麼

依 `prompts/run.md`:讀 `STATE.md` 的下一步 → 推進**一個有界工作塊** → 用評估器自我驗證 →
更新 `STATE.md` / `knowledge/` / `log/` → commit & push → 結束。下一天從新斷點接續。

## 你如何掌握進度

- **看 `log/`**:每天一個檔,摘要當天做了什麼。
- **看 `STATE.md`**:永遠是「目前到哪、下一步」。
- **看 commit 歷史**:每天一筆。
- **被找**:只有三種情況它會停下等你(見 `RULES.md` 升級政策):不可自決岔路、超預算卡關、里程碑審查。

## 調整

- **想更快**:把頻率改每 N 小時(較耗額度)。
- **想暫停**:在 web 停用該 trigger。
- **改方向**:直接編輯 `STATE.md` 的「下一步動作」或 `PLAN.md`,下次排程就會照新方向走。

## 路線圖(排程會依序推進,見 PLAN.md)

S3 mesh 生成器(進行中,curtain_left 已過)→ 推廣 4 mesh → S1 反推分析器 → S2 評估器套件 →
S4 切圖+補圖 → S5 骨架半自動。
