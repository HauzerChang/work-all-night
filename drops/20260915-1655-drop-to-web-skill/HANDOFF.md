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

