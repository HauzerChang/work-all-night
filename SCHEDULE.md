# 每日排程設定指南 (照著做)

讓這個研究專案每天自動推進一步。**排程 trigger 必須在 Claude Code on the web 介面建立**
(session 內建的排程活不過容器回收)。以下是全部步驟。

---

## 🔀 目前排程規劃(2026-08-28 定案)—— 兩條並行 Routine + 固定分支

專案由**兩條獨立 Routine** 並行推進,各**釘一條固定分支**、各有專屬狀態檔,**互不覆蓋、不再增生分支**:

| Routine | 範圍 | **固定分支** | 執行指令 | 狀態檔 | 交接檔 |
|---|---|---|---|---|---|
| **主研究** | S1 / S2(骨架閘)/ S3 / S5 | `claude/spine-main` | `prompts/run.md` | `STATE.md` | `handoff_brief.md` |
| **S4 切圖+補圖** | S4(補圖為主)| `claude/spine-s4-inpainting` | `prompts/run_s4.md` | `STATE_S4.md` | `handoff_S4.md` |

### ⚠️ 為什麼一定要「釘固定分支」(否則分支會爆量)

Routine 每次 run 都**從 default branch clone**,並由 Claude Code **自動開一條隨機名 `claude/<家族>-<隨機碼>` 工作分支**。
若收尾指令是「push 回啟動時所在的分支」(動態偵測),因為每次啟動的隨機分支都不同 → **每 run 產生一條新分支**。
這正是本 repo 一度累積出 **200+ 條 `claude/vibrant-franklin-*`** 的原因。
**根治 = 每條 routine 開頭明確 `git checkout <固定分支>`、收尾 push 回同一固定名**(見兩份 run prompt 的步驟 0)。

### 分支 push 權限(官方最新機制,已更正舊說法)

依官方 [routines 文件](https://code.claude.com/docs/en/routines)「Repositories and branch permissions」:
- **`claude/` 開頭的分支 → 一律被接受**(我們兩條固定分支都是,故**不需任何額外權限設定**;
  舊版「Allow unrestricted branch pushes」開關**已不存在**)。
- 非 `claude/` 分支 → 自動檢查 3 條件(未 protected、無他人 open PR、無他人 commit),全過才 push。

### 建立 Routine(在 [claude.ai/code/routines](https://claude.ai/code/routines) → New routine)

兩條都用「**自帶切分支的完整版 Prompt**」,即使 default branch 落後也能讀到自己的 run prompt:

**① 主研究 Routine** — Name 例如「Spine 研究每日推進」,Prompt:
```
請先切到主排程固定分支再開始:
git fetch origin claude/spine-main
git checkout claude/spine-main
git pull --ff-only origin claude/spine-main
然後依照 prompts/run.md 的指示推進這個研究專案,完成後 commit 並 push 回 claude/spine-main。
```

**② S4 Routine** — Name 例如「Spine S4 補圖研究」,Prompt:
```
請先切到 S4 專屬固定分支再開始:
git fetch origin claude/spine-s4-inpainting
git checkout claude/spine-s4-inpainting
git pull --ff-only origin claude/spine-s4-inpainting
然後依照 prompts/run_s4.md 的指示推進 S4(切圖+補圖)獨立研究排程,完成後 commit 並 push 回 claude/spine-s4-inpainting。
```

- **Repositories**:兩條都加 `HauzerChang/work-all-night`。**Environment**:Default(hook 自動裝 CPU 套件)。
- **Trigger**:Schedule 每天一次(兩條可錯開時段)。兩條固定分支都已推上 remote,Run now 即可試跑。

### ★ 建議一次性設定:把 repo default branch 改成 `claude/spine-main`

Routine 一律從 default clone。把 default 設為 `claude/spine-main` 後,clone 出來就是主排程最新狀態,
上面 Prompt 的 checkout 變成 no-op(更穩、更快)。步驟:
- GitHub → `HauzerChang/work-all-night` → **Settings → General → Default branch** → 點切換圖示 →
  選 `claude/spine-main` → **Update**。
- (S4 Routine 不受影響:它的 Prompt 仍會自己 checkout `claude/spine-s4-inpainting`。)

### 舊分支清理(選配,安全)

200+ 條 `claude/vibrant-franklin-*` / `claude/zealous-noether-*` 是過去動態偵測造成的歷史殘留。
確認最新研究成果都已在 `claude/spine-main` 後,可安全刪除舊分支(GitHub UI 或
`git push origin --delete <branch>`)。不確定的先留;它們不影響兩條固定分支運作。

---

## (以下為單排程原始指南,觀念仍適用;分支策略以上方為準)

## 前置(已完成 ✅)

- ✅ `requirements.txt` — CPU 套件清單。
- ✅ `.claude/hooks/session-start.sh` + `.claude/settings.json` — 每個新 session 自動裝套件、設 PYTHONPATH。
- ✅ `prompts/run.md` / `prompts/run_s4.md` — 兩條排程各自的每次執行指令。
- ✅ `RULES.md` / `PLAN.md` / `STATE.md`(+ `STATE_S4.md`) — 守則、路線圖、續跑狀態。

> ⚠️ **分支機制(依官方文件 /en/routines)**:Routines **沒有「選 branch」欄位**,每次一律從 repo default branch clone
> (原文:"cloned ... starting from the default branch ... unless your prompt specifies otherwise"),
> 並自動開 `claude/` 隨機名工作分支。故續跑靠「Prompt 開頭 checkout 固定分支」達成(見上方)。

## 建立 / 設定排程(Routines)

排程功能 = **Routines**,在 [claude.ai/code/routines](https://claude.ai/code/routines) 管理(或 CLI `/schedule`)。

> 📌 **分支/建立步驟已改採「固定分支」策略,請看本檔最上方「🔀 目前排程規劃」段。**
> 該段有兩條 Routine 的完整 Prompt、default branch 建議、舊分支清理。以下僅保留每日行為/掌握進度的通用說明。

> 注意:run 列表顯示綠燈只代表 session 正常啟動結束,**不代表任務成功**;要開 run 看 transcript / 看 `log/` 確認。

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
