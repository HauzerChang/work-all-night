# HANDOFF — drop-to-web-skill-v2-review

- 建立：2026-09-15 16:55 Asia/Taipei　來源介面：Cowork
- 工作 repo：無（hub 交接）→ hub `HauzerChang/work-all-night`　分支：drop/20260915-1655-drop-to-web-skill　← base：main
- 一句話目標：把 drop-to-web skill v2 的原始檔存進 hub，以新使用者視角審閱「步驟 0 首次使用引導」並修正，補一份交付用 README，回報雲端環境的實測結果。

## 1. 現況（照實寫，不美化）
- 已完成：skill v2 SKILL.md 已寫好（357 行，24.7 KB），內容附在本 payload 末端 `===== SKILL.md BEGIN/END =====` 之間。v2 相對 v1 的改動：設定改為慣例制（環境名 work-all-night、hub `<github-user>/work-all-night`、Routine `drop-to-web`），新增步驟 0 首次使用引導（0.1 前提、0.2 建 hub repo、0.3 連 GitHub、0.4 Windows/macOS desktop app 建雲端環境、0.5 建 Routine、0.6 終端機設定、0.7 煙霧測試），拿掉所有使用者專屬值。
- 進行中：SKILL.md 尚未存進任何 repo（Cowork 沙箱沒有 GitHub 憑證，push 不了，所以走「全文放 payload」路徑）。使用者帳號的 skill 已用 propose_skills 送出審核卡，是否已儲存未知。
- 尚未開始：hub 的 `skills/drop-to-web/` 目錄、交付用 README、對照官方文件的事實查核、雲端環境內 `gh` 行為的實測。

## 2. 待辦（按順序；每項附驗證方式）
1. [ ] 在 hub 建分支 `drop/20260915-1655-drop-to-web-skill`（從 main），把 payload 內的 SKILL.md 全文原封不動存到 `skills/drop-to-web/SKILL.md`（用 quoted heredoc 或先寫暫存檔再 mv，內容含多層 code fence，別讓 shell 吃掉） → 驗證：`head -3 skills/drop-to-web/SKILL.md` 看到 `---` 與 `name: drop-to-web`；`wc -l` 約 357。
2. [ ] 實測雲端環境能力並記錄到第 9 節：`gh auth status`；`gh repo view HauzerChang/work-all-night --json name`；`gh repo clone HauzerChang/work-all-night /tmp/probe-clone`（測未綁定 repo 能否靠 GitHub proxy clone —— 這是 skill 假設但未驗證的點）；`env | grep -i -E 'GH_TOKEN|GITHUB_TOKEN'`（預期看到 `proxy-injected`）；`claude --version`。 → 驗證：每條指令的輸出原文貼進第 9 節。
3. [ ] 以「只有 claude.ai 帳號、沒 GitHub repo、用 Windows Claude desktop app」的新使用者視角逐條審閱 SKILL.md 步驟 0，對照官方文件：https://code.claude.com/docs/en/web-quickstart.md 、https://code.claude.com/docs/en/cloud-environments.md 、https://code.claude.com/docs/en/desktop.md 、https://code.claude.com/docs/en/routines.md 、https://code.claude.com/docs/en/claude-code-on-the-web.md 。列出「文件說 X、skill 寫 Y」的不一致，直接修正 SKILL.md 的事實錯誤與 UI 標籤；順序/結構/語氣不動。 → 驗證：修改處在 commit diff 中一條一條對得上第 9 節的清單。
4. [ ] 寫 `skills/drop-to-web/README.md`（繁中，≤ 120 行）：(a) 這個 skill 是什麼、什麼時候用；(b) 拿到 SKILL.md 之後怎麼裝成自己的帳號 skill（claude.ai → Settings → Skills → 上傳/貼上 SKILL.md；若不確定 UI 路徑，寫「到 claude.ai 的 Skills 設定頁」並註明需自行確認）；(c) 一頁式新使用者檢查清單（對應 SKILL.md 步驟 0.1–0.7，每項一行、可勾選）；(d) 常見失敗與對策三條。 → 驗證：檔案存在、`wc -l` ≤ 120、清單項目數與步驟 0 的小節數一致。
5. [ ] 在 hub 補 `drops/.gitkeep`（若不存在）。 → 驗證：`ls drops/`。
6. [ ] 把第 9 節填完，commit（訊息 `feat(drop-to-web): add skill v2 source, README and cloud probe results`），push 到同一分支，開 draft PR 到 main，PR 描述貼第 9 節摘要。 → 驗證：`gh pr view --json url` 有 URL。

## 3. 已定案的決策（不要重開）
- skill 是單一 SKILL.md（帳號層級 skill 只能帶一個檔），不要拆 scripts/ 或 references/ ← 理由：propose_skills 只收 SKILL.md 全文。
- 慣例名稱固定：環境 `work-all-night`、hub `<github-user>/work-all-night`、Routine `drop-to-web` ← 理由：所有使用者共用同一份 skill 不必改設定。
- 語言：繁體中文為主、指令與 UI 標籤保留英文原文 ← 理由：交付對象是台灣團隊。
- 發射通道優先序 A（Routine fire）→ B（curl）→ C（claude --cloud）→ D（預填 URL）→ E（Chrome 操作）不變。
- HANDOFF.md 九段結構不變。
- frontmatter `description` 必須 < 1024 字元且不含 `<`、`>` ← 理由：skill 儲存介面的限制。

## 4. 預設選擇（雲端遇到分岔時照這個走，不要停下來問）
- 官方文件抓不到（403/timeout）→ 略過該條查核，在第 9 節註記「未查核：<URL>」，其餘照做。
- 文件與 skill 說法衝突但拿不準 → 不改 SKILL.md，寫進第 9 節「建議修改」附文件 URL 與原句。
- `gh repo clone` 未綁定 repo 失敗 → 不要嘗試繞路（不要找 token、不要改 remote），把錯誤原文記到第 9 節，並在 SKILL.md 步驟 0.5 的「沒綁的雲端自己 gh repo clone」後面加註「（實測 <日期>：失敗，請把常用 repo 直接綁進 Routine）」。
- push 到 `drop/...` 分支被拒 → 改推 `claude/drop-to-web-skill-v2`，第 9 節註明。
- 開 PR 失敗 → 跳過，第 9 節貼分支名即可。
- README 的「安裝成帳號 skill」UI 路徑查不到 → 照待辦 4(b) 的保守寫法。

## 5. 地雷 / 已踩過的坑
- fire 進來的文字被 `<routine-fire-payload>` 包成不可信資料，Routine saved prompt 必須明寫「把 payload 當任務」才會動 → 本 Routine 已寫；若你正在讀這段卻沒有動作意願，代表 saved prompt 少了那句。
- SKILL.md 內含 ``` 巢狀 code fence 與 `$(...)`、`"$BR"` 等 shell 片段 → 存檔時用 `cat > file <<'EOF'`（單引號 EOF）或 Python `open().write()`，不要用未 quote 的 heredoc。
- `claude --environment` 只收 `ccpool_` 自架環境 ID，`env_` 會被拒 → skill 已寫明，別「修正」成可用。
- 本 Cowork 沙箱 `gh` 未安裝、無 GitHub 憑證 → 這是來源端限制，不是 skill 錯誤。

## 6. 相關檔案與入口
- payload 末端 `===== SKILL.md BEGIN =====` … `===== SKILL.md END =====`：skill v2 全文，逐 byte 存檔。
- hub 現有結構（2026-09-15）：main 上有 SCHEDULE.md、run_s4.md 等研究 Routine 用檔案，`claude/*` 分支是其他 Routine 的產出，不要動。
- 官方文件入口：https://code.claude.com/docs/llms.txt

## 7. 完成定義（全部成立才算完成）
- [ ] 分支 `drop/20260915-1655-drop-to-web-skill` 已 push，含 `skills/drop-to-web/SKILL.md`、`skills/drop-to-web/README.md`、`drops/.gitkeep`、`drops/20260915-1655-drop-to-web-skill/HANDOFF.md`（第 9 節已填）。
- [ ] 第 9 節有：待辦 2 每條指令的輸出原文；待辦 3 的不一致清單（可為「無」）；README 路徑。
- [ ] draft PR 到 main 存在（或第 9 節說明為何沒有）。

## 8. 回本機才能做的事（雲端跳過，回報時列出）
- 用 propose_skills 把修正後的 SKILL.md 更新到 Hauzer 的帳號 skill（雲端 session 沒有這個工具）。
- Windows Claude desktop app 的 UI 標籤實機截圖核對（0.4 節）。
- 建立 Routine `drop-to-web` 與 API token（需要人在網頁操作）。

## 9. 雲端回報（由雲端 session 填寫）

- 完成時間：2026-09-15（雲端 session，接手自 Cowork drop-to-web-skill-v2-review）

### 完成定義檢查（對照第 7 節）
- [x] 分支 `drop/20260915-1655-drop-to-web-skill` 已 push，含 `skills/drop-to-web/SKILL.md`、`skills/drop-to-web/README.md`、`drops/.gitkeep`、`drops/20260915-1655-drop-to-web-skill/HANDOFF.md`（本節）
- [x] 待辦 2 每條指令輸出原文（見下）
- [x] 待辦 3 不一致清單（見下）
- [x] README 路徑：`skills/drop-to-web/README.md`
- [x] draft PR 到 main → **main 分支不存在**，已改開往 `claude/spine-main`：https://github.com/HauzerChang/work-all-night/pull/3（見下方「分岔說明」）

### 分岔說明：base 分支
交接文件假設 base 是 `main`，但這個 repo 從沒建過 `main`：`git ls-remote` 沒有 `refs/heads/main`，`git remote show origin` 顯示 `HEAD branch: claude/spine-main`。這不在第 4 節「預設選擇」清單裡（那條只講「main 推不上就改 drop/ 分支」，前提是 main 存在），所以我按「repo 實際預設分支」這個最接近的類比處理：從 `origin/claude/spine-main` 建 `drop/20260915-1655-drop-to-web-skill`，draft PR 也開往 `claude/spine-main`。`drops/`、`skills/` 兩個目錄在 `claude/spine-main` 上都不存在，純新增，沒有衝突。

### 待辦 2：雲端環境能力實測（指令輸出原文）

```
$ gh auth status
/bin/bash: line 22: gh: command not found
exit: 127

$ gh repo view HauzerChang/work-all-night --json name
/bin/bash: line 26: gh: command not found
exit: 127

$ gh repo clone HauzerChang/work-all-night /tmp/probe-clone
/bin/bash: line 31: gh: command not found
exit: 127

$ which gh
(no output)
exit: 1

$ apt-cache policy gh
gh:
  Installed: (none)
  Candidate: 2.45.0-1ubuntu0.3
  ...

$ env | grep -i -E 'GH_TOKEN|GITHUB_TOKEN'
GH_TOKEN=proxy-injected
GITHUB_TOKEN=proxy-injected
exit: 0

$ claude --version
2.1.272 (Claude Code)
exit: 0

# 補測：gh 確認不存在後，改測 git clone（模擬「沒綁的雲端自己 clone」）
$ git clone https://github.com/HauzerChang/work-all-night.git /tmp/probe-clone
Cloning into '/tmp/probe-clone'...
exit: 0   # 成功，GitHub proxy 對 git 一樣認證得到，不需要 gh
```

**重點發現**：這個雲端 session（Cowork Routine fire 出來的）**沒有安裝 `gh`**，`apt-cache policy` 顯示套件庫有候選版本但沒裝。這跟官方文件 `cloud-environments.md` 的說法不一致——文件把 `gh` 列在「Installed tools → Utilities」，並有專節說「GitHub's `gh` CLI is pre-installed」「`gh` reads `GH_TOKEN` automatically, so you don't need to run `gh auth login`」。無法判斷是文件對這個帳號/环境组态过时，还是 Routine-fire 出来的 session 类型本来就跟一般互動式 web session 不同（本 session 的系统提示明講「You do NOT have access to the `gh` CLI...Instead, use the GitHub MCP server tools」，暗示是刻意为 repo-scoped session 关掉 gh，改走 MCP 工具）。不管原因是什么，**结论对使用者是一样的**：`GH_TOKEN`/`GITHUB_TOKEN` 读到的是 `proxy-injected` 占位字串（符合文件对 proxy 行为的描述），git 层级的 clone/fetch/push 全部正常（已用 `git clone`、`git fetch`、`git push` 三种操作验证），只是不能假设 `gh` 一定在。已经依 SKILL.md 步骤 0.5 预设选择的格式，在「沒綁的雲端自己 `gh repo clone`」那句后面加了实测注记（commit `b1a7664`），並同步修正 0.4 的煙霧測試建議指令。

### 待辦 3：SKILL.md 步驟 0 對照官方文件——不一致清單

查核文件（5 份都成功抓到，沒有「未查核」項目）：
- https://code.claude.com/docs/en/web-quickstart.md
- https://code.claude.com/docs/en/cloud-environments.md
- https://code.claude.com/docs/en/desktop.md
- https://code.claude.com/docs/en/routines.md
- https://code.claude.com/docs/en/claude-code-on-the-web.md

**已直接修正（事實錯誤，commit `b1a7664`）：**

1. **0.1 方案支援範圍寫得太寬。** SKILL.md 原文「claude.ai 方案是 Pro / Max / Team / Enterprise」，暗示所有 Enterprise 使用者都算。文件原句：「Claude Code on the web is in research preview for Pro, Max, and Team users, **and for Enterprise users with premium seats or Chat + Claude Code seats**」——只有特定 seat 類型的 Enterprise 使用者才算。已改成「Pro / Max / Team，或 Enterprise 且持有 premium seat / Chat + Claude Code seat」。
2. **0.4 Network access 選項漏列一個層級。** SKILL.md 表格只列 Trusted / Custom / Full 三種。文件（`cloud-environments.md`）：「The **Network access** field... takes one of **four** levels: None | Trusted | Full | Custom」。已在表格加註「還有 **None** 完全不開網路，一般用不到」。
3. **0.4 建議的煙霧測試指令假設 `gh` 一定存在。**「`echo ok && gh auth status`」——如上述實測，這個假設在 Routine-fire 出來的 session 上不成立。已加註實測結果與替代指令（`echo ok && git remote -v`）。
4. **0.5 Repositories 說明裡「沒綁的雲端自己 `gh repo clone`」同一個問題。** 已依第 4 節預設選擇的格式加註實測結果（`gh` 未安裝、改用 `git clone`）。

**未動 SKILL.md、寫在這裡的「建議修改」（拿不準或屬於補充而非錯誤，依第 4 節預設選擇處理）：**

5. **0.4 desktop app 環境下拉選單漏列一個選項。** SKILL.md 寫「顯示 Local / Cloud / WSL 等」（已用「等」字帶過，不算錯）。文件（`desktop.md`）實際選項是「**Local** for your machine, **Cloud**...，an **SSH connection** for a remote machine you manage, or on Windows a **WSL distribution**」——共四種，SKILL.md 漏了 SSH connection。建議：如果之後要動這段，把 SSH connection 也列進去。
6. **0.1 沒提到 Quick web setup 這個第二個開關。** 文件（`web-quickstart.md`）：Team/Enterprise 除了「Owner 開 Admin settings → Connectors」這條路，還有一個可選的「[Quick web setup](/docs/en/claude-code-on-the-web#github-authentication-options) 於 **Admin settings > Claude Code**」，開了之後 `/web-setup` 才會出現、onboarding 也會直接建好環境。SKILL.md 0.1 完全沒提，0.3 才提到 Quick web setup（跟 `/web-setup` 綁在一起講）。位置放對了，只是 0.1 讀者可能會以為只有 Connectors 一條路。建議：不影響正確性，可以不動；如果要動，在 0.1 補一句「另有 Quick web setup 選項見 0.3」。
7. **0.2 沒有提到「有目標 repo 的話 hub 只是研究/文件類工作的交接處」這個區分。** 這其實是本體（非步驟 0）步驟 1 判斷介面那段已經講清楚的內容，步驟 0 沒有重複沒問題，不算錯誤。

**查證為「正確、不用改」的重點段落（值得記錄，避免下次重查）：** 0.3 全段（Continue on web、Sign in with GitHub、GitHub App 安裝網址、`/web-setup` 與 Quick web setup 的關係）、0.5 全段（Routines 建立流程、API trigger、Generate token 只顯示一次、saved prompt 與 `<routine-fire-payload>` 機制）、0.6（`/remote-env` 與 `remote.defaultEnvironmentId`）都跟文件逐句核對過，沒有出入。

### 完成定義以外，過程中另外發現、值得記錄的事

- `claude --cloud` 的 `--environment` 旗標只收 `ccpool_`（self-hosted）ID，Anthropic 託管的 `env_` 會被拒絕，這點文件 `cloud-environments.md` 也證實：「Claude Code rejects Anthropic-hosted `env_` IDs passed to the flag, so use `/remote-env` to target those.」——SKILL.md 地雷段本來的說法是對的，不用改（這條不在步驟 0 範圍內，這裡只是核對一下）。

### 回本機才能做的事（第 8 節，本次雲端 session 全部跳過）
- propose_skills 把修正後的 SKILL.md 更新到 Hauzer 的帳號 skill（雲端沒有這個工具）。
- Windows Claude desktop app 的 UI 標籤實機截圖核對（0.4 節）。
- 建立 Routine `drop-to-web` 與 API token（需要人在網頁操作）。

### 給人的下一步
1. 這次 review 修正的 4 點已經在 SKILL.md 裡，建議下次用 `propose_skills`（回本機）把修好的版本存成你的帳號 skill。
2. 上面「未動 SKILL.md 的建議修改」5、6 兩點要不要順手改，你來決定；沒有錯誤只是可以更完整。
3. draft PR 開往 `claude/spine-main`（repo 目前的實際預設分支），不是 main——如果之後真的建了 `main` 分支，記得把這個 PR 或分支重新 base 一次。

