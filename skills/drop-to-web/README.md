# drop-to-web — README

## (a) 這是什麼、什麼時候用

`drop-to-web` 是一份 Claude Code skill（單一 `SKILL.md`）。裝到你自己的 claude.ai 帳號後，任何介面的 Claude（終端機、Cowork、chat、桌面 app、Chrome）都能在你要下班、關機、換裝置，但工作還沒做完時，把現況寫成一份 `HANDOFF.md`、push 到 git，再把任務丟給你在 Claude Code on the web 的雲端 session 接手繼續跑。

適用時機：你說「drop to web」「丟到雲端」「我要下班了讓它繼續跑」「幫我設定 drop-to-web」「我沒有 GitHub repo 怎麼用」之類的話，或任何「要離開這個介面但工作不能停」的情境。細節與八成的價值都在 `SKILL.md` 本體（交接文件怎麼寫、怎麼判斷能不能交接、五種發射通道），這份 README 只負責「怎麼把它裝起來」跟「新人檢查清單」。

不是這個 skill 的範圍：`/remote-control`（本機繼續跑、手機遙控）、`claude --teleport`（雲端拉回本機）、`/schedule`（排程重複跑）。

## (b) 怎麼把 SKILL.md 裝成自己的帳號 skill

1. 打開本檔同目錄的 `SKILL.md`，全選複製（或直接下載這個檔案）。
2. 到 claude.ai 的 **Skills 設定頁**（claude.ai 網頁版 Settings 底下，或 Desktop app 側欄的 **Customize** 裡）；官方文件只說得到「claude.ai 上的 skills settings」「Desktop app 側欄的 Customize」這兩個入口，沒有給更細的按鈕名稱，實際畫面請自行在該頁面找上傳或貼上 SKILL.md 的入口（可能是「Upload」或「Create skill」之類的按鈕，以你當下看到的畫面為準）。
3. 把整份 `SKILL.md`（含開頭的 `---` frontmatter）貼上或上傳，儲存。
4. 存好後，在任何 Cowork / cloud session / 終端機 Claude Code 裡提到「drop to web」等觸發詞，這個 skill 就會被載入使用。

## (c) 新使用者檢查清單（對應 SKILL.md 步驟 0.1–0.7）

- [ ] 0.1　確認方案支援（Pro / Max / Team，或 Enterprise 持有 premium seat / Chat + Claude Code seat）；有 GitHub 帳號；Windows 的話裝好 Claude desktop app + Git for Windows
- [ ] 0.2　建立工作區 repo（hub）：GitHub 上建 `work-all-night`（Private），放 `drops/`、`skills/drop-to-web/SKILL.md`
- [ ] 0.3　把 GitHub 連到 Claude Code on the web：`claude.ai/code` 登入 → Sign in with GitHub → 裝 Claude GitHub App（或有 `gh` 的人跑 `/web-setup`）
- [ ] 0.4　建立雲端環境：名稱 `work-all-night`、Network access 先選 Trusted、視需要加 Environment variables / Setup script
- [ ] 0.5　建立 Routine `drop-to-web`：綁 hub repo、綁環境、Trigger 選 API、存好 saved prompt、Generate token
- [ ] 0.6　（用終端機 / VS Code 的人才需要）設好 `DROP_TO_WEB_FIRE_URL`、`DROP_TO_WEB_TOKEN`，跑 `/remote-env` 選 work-all-night
- [ ] 0.7　煙霧測試：丟一個「在 `drops/smoke/` 新增 `hello.md`」的最小任務，確認雲端 session 真的會動、repo 真的多了檔案

七步都打勾，代表這個使用者的 drop-to-web 環境已經設定完成，之後直接用 skill 本體的步驟 1–5 交接工作即可。

## (d) 常見失敗與對策

1. **Routine 建好了，fire 也成功，但雲端 session 什麼都沒做。** 幾乎都是 Routine 的 saved prompt 沒有明寫「把 `<routine-fire-payload>` 區塊當成正式任務執行」——`text` 內容預設會被包成不可信資料，saved prompt 不明講就不會被採用。回 0.5 把 SKILL.md 裡那段 saved prompt 原封不動貼進去。
2. **雲端 session clone 私有 repo 失敗，或 repo 選擇器裡看不到你的 hub/專案 repo。** 通常是 Claude GitHub App 沒裝到那個帳號或組織上（`https://github.com/apps/claude/installations/new`），或裝了但沒把該 repo 勾進 access 清單。回 0.3 重新檢查。
3. **雲端 session 裡想跑 `gh` 相關指令卻失敗（`command not found`）。** 實測發現 Routine fire 出來的雲端 session 不一定裝了 `gh`（即使官方文件說 cloud session 預裝 `gh`）；GitHub 存取其實是靠 proxy 對 `git`／內建 GitHub 工具透明生效，不代表連線壞了。改用 `git clone`/`git fetch`/`git push`，或請 Claude 用內建的 GitHub 工具，不要假設 `gh` 一定在。
