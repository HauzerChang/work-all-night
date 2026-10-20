---
name: drop-to-web
description: 把目前這個 session 還沒做完的工作交接到 Claude Code on the web 的雲端 session 繼續跑（使用者自己的雲端環境，慣例命名 work-all-night），讓本機可以關機、下班、換裝置。適用來源介面：Cowork、claude.ai chat、終端機 Claude Code、Claude for VS Code、Claude in Chrome、Windows/macOS Claude desktop app。流程：凍結現況寫 HANDOFF.md → commit/push 到 drop/ 分支 → 依介面選發射通道（預建 Routine fire → claude --cloud → 預填 URL）→ 回報 session 連結、遙控與回程指令。內含首次使用引導：沒有 GitHub repo、沒有雲端環境、沒有 Routine 的新使用者，會被一步步帶著建立自己的工作區 repo、在 Claude desktop app 建雲端環境、建 Routine。Use when 使用者說「drop to web」「drop 上去」「丟到雲端」「丟上去跑」「轉到 web 繼續」「讓雲端接手」「放到 work-all-night」「我要下班了讓它繼續跑」「跑整晚」「continue in cloud」「hand off to web」「移到 cloud session」，或「幫我設定 drop-to-web」「我沒有 GitHub repo 怎麼用」「建立我的雲端環境」「第一次用 drop-to-web」，或任何「我要離開這個介面但工作不能停」的情境——即使沒說出 skill 名稱也要用。不是 remote-control（那是本機繼續跑、從手機遙控），不是 teleport（那是雲端拉回本機，本 skill 只在回程段提到）。
---

# drop-to-web — 把進行中的工作交接到雲端接續

## 設定慣例（每個使用者一套，靠慣例少填設定）

| 項目 | 慣例值 | 怎麼知道目前使用者的值 |
|---|---|---|
| 雲端環境名稱 | `work-all-night` | 預填 URL 用名稱即可；`env_...` ID 在終端機 `~/.claude/settings.json` 的 `remote.defaultEnvironmentId`（跑過 `/remote-env` 才有） |
| 工作區 repo（hub） | `<github-user>/work-all-night`（GitHub、Private） | CLI：`gh api user -q .login`；Cowork：`list_triggers` 裡 `drop-to-web` Routine 的 `session_request.config.sources[].git_repository.url`；chat / Chrome：問使用者 |
| 預建 Routine | 名稱 `drop-to-web`，綁 hub（＋常用專案 repo），環境 work-all-night，API trigger | Cowork：`list_triggers`；CLI：問使用者或 `/schedule list` |
| 終端機環境變數 | `DROP_TO_WEB_FIRE_URL`、`DROP_TO_WEB_TOKEN` | `[ -n "$DROP_TO_WEB_TOKEN" ]` |

第一次跟某位使用者合作、或上表任何一項查不到，先走**步驟 0 首次使用引導**，別急著發射。有記憶功能時把該使用者的值記下來（GitHub 帳號、環境名、Routine 是否建好），下次直接用。

## 核心觀念

雲端 session 是一個**全新的 Claude**：沒有這段對話的記憶、沒有你的本機檔案、沒有本機 MCP（Cocos Creator MCP、chrome-devtools 都沒有）。它唯一拿得到的是 **git 裡的東西 + 你送過去的 prompt**。所以這個 skill 的價值有八成在「交接文件寫得夠不夠讓陌生人接得上」，兩成在發射機制。寧可多花三分鐘把 HANDOFF.md 寫實，也不要快速丟一句「繼續做」上去。

雲端 session 一旦停下來問問題，人不在就等到環境過期。所以交接時要把「已定案的決策」和「遇到分岔的預設選擇」寫清楚，讓它能自己走完。

## 流程總覽

0. 首次使用引導（只在缺工作區 / 環境 / Routine 時走）
1. 判斷介面與可交接性（30 秒）
2. 凍結現況：寫 HANDOFF.md、commit 到 `drop/` 分支、push
3. 組雲端 prompt（短，指向 HANDOFF.md）
4. 依介面發射：Routine fire → `claude --cloud` → 預填 URL
5. 確認 session 建立，回報連結、遙控指令、回程指令、無法交接的項目

---

## 步驟 0：首次使用引導（新使用者，或缺任何一項設定時）

目標是讓一個「只有 claude.ai 帳號、沒有 GitHub repo、沒開過雲端 session」的人，在 20 分鐘內擁有：一個私有工作區 repo、一個叫 work-all-night 的雲端環境、一個叫 drop-to-web 的 Routine。逐項確認，已具備的直接跳過；每一步做完請使用者回報結果再往下，別一次丟七步。

### 0.1 前提檢查

- claude.ai 方案是 Pro / Max / Team，或 Enterprise 且持有 premium seat / Chat + Claude Code seat（Claude Code on the web 目前是這些方案的研究預覽；一般 Enterprise seat 不算）。Team / Enterprise 使用者若在 claude.ai/code 看到「GitHub access is required」卻沒有登入按鈕，要請組織 Owner 到 **Admin settings → Connectors** 開啟 GitHub connector，這步使用者自己解不了。
- 有 GitHub 帳號；沒有就到 https://github.com/signup 建一個（免費即可）。
- Windows 使用者：安裝 Claude desktop app（https://claude.com/download，選 Windows x64 或 ARM64），登入後左側有 **Code** 分頁；另外裝 [Git for Windows](https://git-scm.com/downloads/win)，本機 session 建 worktree 會用到。終端機路徑可選：另裝 Claude Code CLI 並 `/login`。

### 0.2 建立工作區 repo（hub）

hub 的角色：Routine 的固定 checkout、HANDOFF 歸檔（`drops/`）、本 skill 的原始檔存放處（方便再交付給下一個人）。

網頁：https://github.com/new → Repository name `work-all-night` → **Private** → 勾 **Add a README file** → Create。
或 CLI（已裝 `gh` 且 `gh auth login` 過）：

```bash
gh repo create work-all-night --private --add-readme --clone
cd work-all-night
mkdir -p drops skills/drop-to-web && touch drops/.gitkeep
# 把本 skill 的 SKILL.md 存到 skills/drop-to-web/SKILL.md
git add -A && git commit -m "chore: init drop-to-web workspace" && git push
```

沒有 `gh` 的人用網頁建好後，請 Claude 在任何有 shell 的介面幫他 clone、補上 `drops/` 與 `skills/drop-to-web/SKILL.md`、push。

### 0.3 把 GitHub 連到 Claude Code on the web

1. 瀏覽器開 https://claude.ai/code，若出現安裝 app 的頁面點最下方 **Continue on web**。
2. 點 **Sign in with GitHub** → 到 GitHub 授權 → 回到 claude.ai/code。
3. 安裝 Claude GitHub App：https://github.com/apps/claude/installations/new → 選自己的帳號 → **Only select repositories** → 勾 `work-all-night` 和之後會 drop 的專案 repo。私有 repo 沒裝 App 就 clone 不到。
4. 有 `gh` 的人可改在終端機 Claude Code 裡跑 `/web-setup`，把 `gh` token 交給帳號，不必裝 App（Team / Enterprise 需 Owner 開 **Quick web setup**）。

驗證：claude.ai/code 的 repo 選擇器看得到 `work-all-night`。

### 0.4 建立雲端環境（Windows / macOS Claude desktop app 或網頁）

desktop app：**Code** 分頁 → 新 session 的訊息框上方有環境下拉（顯示 Local / Cloud / WSL 等）→ 選 **Cloud** → 再打開同一個下拉 → **Add cloud environment**。網頁版：claude.ai/code 訊息框上方那個顯示環境名稱的雲朵按鈕 → **Add cloud environment**。對話框四個欄位：

| 欄位 | 建議 |
|---|---|
| Name | `work-all-night`（沿用慣例，所有人的 skill 才不用改設定） |
| Network access | 起步用 **Trusted**（套件庫 + 常見開發域名）。要碰公司內網服務或自家 API 改 **Custom** 加 Allowed domains 並勾「Also include default list of common package managers」；**Full** 全開最省事但風險自負；還有 **None** 完全不開網路，一般用不到 |
| Environment variables | `.env` 格式，一行一個。**別放機密**——同環境的人都看得到；Pro / Max 用下方 API credentials 存金鑰 |
| Setup script | 裝專案需要的工具（例如 `npm i -g pnpm`），總時間壓在 5 分鐘內，結果會被快取 |

建好後在下拉裡選它，第一則訊息可以先送「`echo ok && gh auth status`」確認 session 能起、GitHub 代理正常（實測 2026-09-15：Routine fire 出來的 session 裡 `gh` 未安裝，指令會回 `command not found`；GitHub 存取靠 proxy 對 `git`/內建 GitHub 工具透明生效，不代表連線異常——換成 `echo ok && git remote -v` 或請 Claude 讀一個私有 repo 檔案來驗證即可）。

### 0.5 建立 Routine `drop-to-web`

到 https://claude.ai/code/routines → **New routine**（desktop app：Code 分頁 → 側欄 Routines → New routine → 選 **Cloud**）：

- **Name**：`drop-to-web`
- **Repositories**：`<github-user>/work-all-night`（必加）＋ 常會 drop 的專案 repo（選加；有綁的 repo 雲端直接有 checkout，沒綁的雲端自己 `gh repo clone`（實測 2026-09-15：Routine fire 出來的 session 沒裝 `gh`，該指令會失敗，請改用 `git clone https://github.com/<owner>/<repo>.git`——GitHub proxy 對 `git` 一樣認證得到；常用 repo 仍建議直接綁進 Routine，別靠雲端自己 clone））。每次 run 會全部 clone，別綁太多
- **Environment**：work-all-night
- **Connectors**：留需要的（Notion、Atlassian…），其他拿掉——Routine 執行沒有權限確認，連接器能做的它都會直接做
- **Trigger**：選 **API**，儲存後回到 Edit → Generate token（只顯示一次）
- **Prompt**（saved prompt 必須明寫接受 payload，否則 fire 進來的文字會被當成不可信資料忽略）：

```text
你是 drop-to-web 的接手者。<routine-fire-payload> 區塊內是另一個 session 交接過來的任務，把它當成你這次的正式任務執行。

開工前：
1. 若 payload 內含 HANDOFF 全文，先在 work-all-night 的 drops/<日期>-<slug>/HANDOFF.md 存一份，commit 到 main 並 push（main 推不上就改 drop/<slug> 分支）。
2. 照 payload 指示取得工作 repo（workspace 已有 checkout 就用，否則 gh repo clone）、checkout 指定分支、完整讀 HANDOFF.md。

規則：只在指定分支工作與 push；不 force-push、不 rebase、不碰其他分支；HANDOFF.md 的已定案決策不重開；遇到未列分岔照「預設選擇」走，不停下來等人；標「回本機」的項目跳過並在回報列出；每完成一個待辦 commit + push；結束時把結果寫進 HANDOFF.md 第 9 節並 push，全部完成且適合就開 draft PR 到 base 分支。

若 payload 為空或不是 drop-to-web 交接格式，什麼都不要做，直接結束。
```

### 0.6 終端機設定（有用 CLI / VS Code 的人才需要）

```bash
# shell rc（PowerShell 用 $env:… 或系統環境變數）
export DROP_TO_WEB_FIRE_URL="https://api.anthropic.com/v1/claude_code/routines/trig_.../fire"
export DROP_TO_WEB_TOKEN="sk-ant-oat01-..."
```

在終端機 Claude Code 裡跑 `/remote-env` 選 work-all-night，讓 `claude --cloud` 落在正確環境（寫進 `~/.claude/settings.json` 的 `remote.defaultEnvironmentId`）。

### 0.7 煙霧測試

用本 skill 丟一個最小任務：「在 work-all-night 的 `drops/smoke/` 新增 `hello.md`，內容寫今天日期，commit 並 push」。看到 session 出現在 claude.ai/code、幾分鐘後 repo 多了那個檔案，設定就完成了。失敗最常見的三個原因：Routine prompt 沒寫「把 payload 當任務」、GitHub App 沒裝到 hub、環境 Network access 擋了需要的域名。

---

## 步驟 1：判斷介面與可交接性

先看自己有哪些工具，決定走哪條發射通道：

| 介面 | 判斷依據 | 發射通道 |
|---|---|---|
| Cowork | 有 `mcp__claude-code-remote__list_triggers` / `fire_trigger` | A. Routine fire（工具）；若無 Routine → D. 預填 URL |
| 終端機 Claude Code / VS Code 擴充 | 有 Bash，`claude --version` 可跑 | B. Routine fire（curl）→ C. `claude --cloud` → D |
| Claude in Chrome | 有 `mcp__claude-in-chrome__*`、沒有 shell | E. 瀏覽器直接操作 claude.ai/code |
| claude.ai chat | 沒有 shell、沒有瀏覽器工具 | D. 預填 URL + 貼上區塊 |
| Desktop app 的 Code 分頁（本機 session） | 使用者說他在 Desktop app 的 Code 分頁 | 內建 **Continue in → Claude Code on the web**（session 工具列右下角 VS Code 圖示的選單）會自己 push 分支、摘要對話、開雲端 session；仍先做步驟 2 寫好 HANDOFF.md 再按，摘要品質差很多 |

再確認工作本體能不能過去，並決定 HANDOFF.md 放哪：

- **有目標 repo 且在 GitHub**（`git remote -v`）→ HANDOFF.md 放目標 repo 的 `drop/` 分支。GitLab 之類的非 GitHub remote 雲端拿不到，只能靠終端機的 bundle 上傳且無法 push 回去。
- **沒有目標 repo**（研究、文件、Notion/Jira 上的工作）→ HANDOFF.md 放 hub 的 `drops/<YYYYMMDD-HHmm>-<slug>/HANDOFF.md`。雲端有 claude.ai 連接器（Routine 建立時選的那些），所以這類工作可以交接。
- **本機檔案**（Cowork 連接的資料夾、`~/Downloads` 裡的素材）雲端碰不到，一律要進 git 才算交接。不進 git 的就明列在「無法交接」。
- **需要本機工具的步驟**（Cocos Creator 編輯器預覽、Spine 視覺確認、瀏覽器操作測試站、本機 MCP）雲端做不了，寫進 HANDOFF.md 第 8 節讓雲端跳過。

若整份工作都是本機素材處理、進不了 git 也不在連接器裡，老實告訴使用者這個不能 drop，改為產出一份 HANDOFF.md 讓他日後在任何地方接續。

---

## 步驟 2：凍結現況

### 2a. 蒐集材料

- 有 TaskList 工具就先讀，把任務狀態直接搬進待辦。
- `git status`、`git diff --stat`、`git log --oneline -10`，確認改了什麼、改到哪。
- 回顧對話：使用者做過哪些決定、否決過什麼、踩過什麼坑、罵過什麼。這些是雲端最容易重蹈覆轍的地方。
- 使用者的相關偏好如果影響這件工作，寫進決策段——雲端 session 也有帳號記憶，但不保證會去讀。

### 2b. 寫 HANDOFF.md（固定結構）

```markdown
# HANDOFF — <slug>

- 建立：<YYYY-MM-DD HH:mm 時區>　來源介面：<Cowork / CLI / VS Code / Chrome / chat>
- 工作 repo：<owner/repo 或「無（hub 交接）」>　分支：drop/<YYYYMMDD-HHmm>-<slug>　← base：<原分支>
- 一句話目標：<做完要達成什麼>

## 1. 現況（照實寫，不美化）
- 已完成：
- 進行中（精確到檔案 / 函式 / 目前行為 / 最後一次測試結果）：
- 尚未開始：

## 2. 待辦（按順序；每項附驗證方式）
1. [ ] <做什麼> → 驗證：<跑哪個指令 / 看哪個結果>
2. [ ] ...

## 3. 已定案的決策（不要重開）
- <決策> ← 理由：<為什麼>

## 4. 預設選擇（雲端遇到分岔時照這個走，不要停下來問）
- 遇到 <情境> → 選 <做法>

## 5. 地雷 / 已踩過的坑
- <現象> → <原因 / 避法>（含精確錯誤訊息）

## 6. 相關檔案與入口
- <路徑>：<這檔案跟任務的關係>

## 7. 完成定義（全部成立才算完成）
- [ ] ...

## 8. 回本機才能做的事（雲端跳過，回報時列出）
- ...

## 9. 雲端回報（由雲端 session 填寫）
```

寫法要點：
- 寫給一個聰明但完全沒脈絡的人看。「繼續調胸部動態」不行，「`Main_Idle_face_3` 的 `chest_L` translate 曲線第 0.4s 峰值要延後 2 frame，face_2 已完成可對照」才行。
- 錯誤訊息貼原文，指令貼可直接複製的完整版。
- 不要把 secrets、token、`.env` 內容寫進去，這份會進 repo。
- 第 4 節「預設選擇」是防止雲端卡住的保險，至少寫三條。

### 2c. 進 git

**有目標 repo**（HANDOFF.md 放 repo 根目錄）：

```bash
BASE=$(git rev-parse --abbrev-ref HEAD)
SLUG=<kebab-case-短描述>
BR="drop/$(date +%Y%m%d-%H%M)-$SLUG"
git checkout -b "$BR"
git add -A            # 先看 git status，不該進 repo 的（.env、金鑰、大型素材）不要 add
git commit -m "wip(drop): $SLUG — handoff to cloud

Base: $BASE
Co-Authored-By: Claude <noreply@anthropic.com>"
git push -u origin "$BR"
```

原分支不動，所有 WIP 都在 `drop/` 分支上，使用者回來要丟掉也乾淨。

**沒有目標 repo**（HANDOFF.md 放 hub）：clone hub，在 `drops/<YYYYMMDD-HHmm>-<slug>/HANDOFF.md` 寫入，同樣開 `drop/<...>-<slug>` 分支 commit、push。

**push 不了的情境**：
- Cowork 連接資料夾：git 指令用 `device_bash` 在 `$HOME/mnt/<folder>` 跑；push 失敗（沒憑證、egress 擋）就請使用者自己 push，再繼續發射。
- Cowork 雲端沙箱（通常沒有 GitHub 憑證）或 chat：HANDOFF.md 全文改放進 prompt（見步驟 3）；有程式碼改動就 `git format-patch <base>..HEAD` 產 patch 交付給使用者，請他 apply 後 push，並在回報裡講清楚「雲端拿到的 code 是 remote 上的版本」。Routine 的 saved prompt 會把 prompt 內的 HANDOFF 存進 hub 的 `drops/`，歸檔不會漏。

---

## 步驟 3：組雲端 prompt

短、指向明確、把規則講死。HANDOFF.md 才是本體，prompt 只是入口：

```text
[drop-to-web 交接] <slug>
來源：<介面> session · <YYYY-MM-DD HH:mm 時區>
工作 repo：<owner/repo 或「無」>　分支：<drop 分支>（base：<原分支>）
HANDOFF：<owner/repo>@<drop 分支>:HANDOFF.md（或 hub drops/<...>/HANDOFF.md，或「見下方全文」）

第一步：取得工作 repo（workspace 已有 checkout 就直接用，否則 `gh repo clone <owner/repo>`），`git fetch origin && git checkout <drop 分支>`，完整讀 HANDOFF.md 再動手。

目標：<一句話>
完成定義：<HANDOFF.md 第 7 節的濃縮>

接手規則：
- 只在 <drop 分支> 上工作、push 回同一分支；不要 force-push、不要碰其他分支、不要 rebase。
- HANDOFF.md 第 3 節是已定案決策，不要重開；遇到未列的分岔照第 4 節預設走，不要停下來等人。
- 第 8 節標「回本機」的項目跳過，最後回報時列出。
- 每完成一個待辦就 commit + push 一次（小步提交，人隨時能從手機看進度）。
- 完成或卡住時：把結果、未完成項、需要人決定的事寫進 HANDOFF.md 第 9 節，commit + push；若全部完成且 base 分支適合，開 draft PR 到 <原分支>，PR 描述引用 HANDOFF.md。
```

HANDOFF.md 沒能進 git 的情境，把全文接在這段後面（Cowork 的 `fire_trigger` text 上限 64 KiB，夠用；走 URL 預填則全文改成給使用者貼的區塊）。

---

## 步驟 4：發射

### A. Cowork — 用 Routine 工具 fire（首選）

1. `list_triggers`，找名稱為 `drop-to-web` 的 Routine。
2. `fire_trigger(trigger_id=<trig_...>, text=<步驟 3 的 prompt>)`。
3. 回傳裡的 session 連結記下來；回傳沒有連結的話，稍等幾秒再 `list_triggers`，用該 Routine 的 `last_run.session_id`（`cse_...` 或 `session_...`）組成 `https://claude.ai/code/<session_id>`。fire 的 text 會以 `<routine-fire-payload>` 包起來送給雲端，Routine 的 saved prompt 已寫好「把 payload 當交接任務執行」，所以會動。
4. 找不到 `drop-to-web` Routine → 帶使用者走步驟 0.5 建一個（三分鐘），或改走 D。

不要用 `create_trigger` 臨時造 Routine：它沒有 repo 參數，造出來的 session 沒有 checkout；Routine 請在網頁上預建一次。

### B. 終端機 / VS Code — 用 API trigger fire（有 token 就用）

先確認 `[ -n "$DROP_TO_WEB_FIRE_URL" ] && [ -n "$DROP_TO_WEB_TOKEN" ]`，兩個都有才走這條：

```bash
python3 -c 'import json;print(json.dumps({"text":open(".drop-prompt.md").read()}))' > .drop-payload.json
curl -sS -X POST "$DROP_TO_WEB_FIRE_URL" \
  -H "Authorization: Bearer $DROP_TO_WEB_TOKEN" \
  -H "anthropic-beta: experimental-cc-routine-2026-04-01" \
  -H "anthropic-version: 2023-06-01" \
  -H "Content-Type: application/json" \
  --data-binary @.drop-payload.json
rm -f .drop-payload.json
```

回傳 JSON 的 `claude_code_session_url` 就是新 session（`401` 表示 token 錯或已 revoke）。token 只能從環境變數讀，不要 echo、不要寫進任何檔案或對話。

### C. 終端機 / VS Code — `claude --cloud`

前提：使用者已用 `/remote-env` 把預設環境設成 work-all-night。先 `grep defaultEnvironmentId ~/.claude/settings.json`，沒有就提醒使用者跑一次 `/remote-env`，否則會落到 Default 環境。

```bash
git push -u origin "$BR"   # --cloud 是 clone GitHub remote 上的目前分支，不是本地 working tree
timeout 150 claude --cloud "$(cat .drop-prompt.md)" </dev/null 2>&1 | tee .drop-launch.log
grep -o 'https://claude.ai/code/[A-Za-z0-9_]*' .drop-launch.log | head -1
```

- `claude --cloud "<描述>"` 在有終端機時是互動式（會顯示佈建進度、可以接著打字）。從 Claude 的 Bash 工具裡跑是沒有 TTY 的巢狀執行，行為不保證：抓到 session URL 就成功；沒抓到、或看到「巢狀 session」「Input must be provided」之類的錯，就不要硬試，把 `claude --cloud "$(cat .drop-prompt.md)"` 這行連同 `.drop-prompt.md` 的路徑印給使用者，請他在另一個終端視窗執行，再回來貼 session URL。
- `.drop-prompt.md`、`.drop-launch.log` 是暫存檔，發射完刪掉，不要 commit。
- `--environment` 旗標只收自架 `ccpool_` 環境 ID，Anthropic 託管的 `env_` 會被拒絕，所以 work-all-night 只能靠 `/remote-env` 預設。
- 非 GitHub remote 才用 `CCR_FORCE_BUNDLE=1 claude --cloud ...`（上傳本地 bundle，含已追蹤檔的未提交改動、不含 untracked；雲端無法 push 回該 remote）。

### D. 預填 URL（chat 的唯一路徑；其他介面的最後退路）

```
https://claude.ai/code?environment=work-all-night&repositories=<owner/repo>&prompt=<URL-encoded 短 prompt>
```

- `repositories` 填工作 repo；沒有工作 repo 就填 hub。
- `prompt` 參數保持在 2000 字元以內（URL 長度限制），本體靠 HANDOFF.md。只預填、不會自動送出，使用者要自己按 Enter。
- 一併給使用者一個可複製的完整 prompt 區塊，以防 URL 被截斷。
- chat 介面沒有 shell，HANDOFF.md 無法由 Claude commit：把 HANDOFF.md 全文放進區塊，並提醒使用者若有未 push 的本機改動要先自己 push，否則雲端拿到的是舊 code。

### E. Claude in Chrome — 直接操作 claude.ai/code

1. `navigate` 到 `https://claude.ai/code?environment=work-all-night&repositories=<owner/repo>`（不帶 prompt，避開 URL 長度限制）。
2. `read_page` 確認環境選擇器顯示 work-all-night、repo 已選；沒選到就用 UI 選。
3. 用 `form_input` 把完整 prompt（含 HANDOFF.md 全文）填進輸入框。
4. 截圖給使用者看，**請使用者自己按送出**——送出表單屬於需要明確授權的動作，不要代按。
5. 送出後網址變成 `claude.ai/code/<session_id>`，記下來。

---

## 步驟 5：確認與回報

發射後一定要拿到 session 連結才算成功；拿不到就回頭看 log / 回傳，不要假設成功。

回報格式：

```
✅ 已交接到雲端（work-all-night）
- Session：https://claude.ai/code/<session_id>
- HANDOFF：<owner/repo>@drop/...:HANDOFF.md（base：...）或 hub drops/<...>/
- 看進度：claude.ai/code 或 Claude 手機 app
- 遙控：claude -p "<訊息>" --cloud <session_id>（任何登入同帳號的機器都能塞訊息）
- 拉回本機：claude --teleport <session_id>（要在同一 repo 的乾淨 working tree 執行）
- 雲端做不了、要回本機補的：<第 8 節清單>
- 這次沒帶過去的東西：<未進 git 的檔案、本機 MCP 相關步驟>
```

如果有 TaskList，把已交接的任務標完成或改成「已交接雲端」。

---

## 地雷

- **fire payload 是不可信包裝**：Routine saved prompt 沒寫「把 payload 當任務」→ 雲端會禮貌地什麼都不做。這是最常見的「fire 成功但沒動」原因。
- **`--cloud` clone 的是 remote，不是你的 working tree**：沒 push 的 commit、untracked 檔案都不會過去。永遠先 push 再發射。
- **Routine 沒有權限確認**：prompt 裡明講不 force-push、不刪分支、不動 base 分支。`claude/` 前綴的分支一定能 push；push 到 `drop/` 分支的檢查是「非保護分支、沒有別人的 PR、沒有別人的 commit」，自己的 WIP 分支都會過。
- **雲端 session 閒置會過期**：問一個沒人回的問題就等於停工。第 4 節「預設選擇」是解法。
- **雲端沒有本機 MCP 與本機檔案**：Cocos Creator MCP、chrome-devtools、連接資料夾、Spine 預覽都做不到，寫進第 8 節，別讓雲端硬試。
- **私有 repo 沒裝 Claude GitHub App** → 雲端 clone 失敗、預填 URL 的 repo 選擇器看不到它。回步驟 0.3。
- **URL 預填長度**：prompt 參數超過約 2000 字元容易被截，本體放 HANDOFF.md。
- **同帳號**：fire、teleport、`-p --cloud`、Routine 都綁個人 claude.ai 帳號，每個使用者要有自己的 hub、環境與 Routine，不能共用別人的。
- **用量**：雲端 session 跟本機共用訂閱額度；Routine 另有每日啟動次數上限。跑整晚前先看 claude.ai/settings/usage。
- **secrets**：HANDOFF.md 會進 repo，token、`.env`、內部網址帳密都不要寫；環境變數欄位同環境的人都看得到。

## 常見誤觸

- 「幫我用手機看進度／遙控本機的 session」→ 那是 `/remote-control`，不是這個 skill。
- 「把雲端的 session 拉回本機」→ `claude --teleport <id>`，本 skill 只負責去程。
- 「排程每天跑」→ `/schedule` 建 Routine，不是交接。

