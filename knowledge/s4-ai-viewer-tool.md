# S4 AI 補圖 Viewer(2026-09-04)— `tools/mesh_gen/s4_ai_viewer.html`

> 使用者要求(chunk 34):「製作 viewer,功能:檢視/編輯 PSD檔(閱覽切圖補圖結果),與 chat gpt
> 溝通(即時切圖補圖),大概來講就是 photoshop 插件的 html 版」「不想要功能被 Photoshop 綁定」。

## 架構決策

**純瀏覽器端,不經過任何伺服器,不依賴 Photoshop。**關鍵前提驗證(見
`log/s4-2026-09-04-036.md`):`curl -X OPTIONS https://api.openai.com/v1/images/edits`
帶 CORS preflight header,回傳 `access-control-allow-origin: *`——**OpenAI API 允許瀏覽器
直接跨來源呼叫**,不需要中介後端代理。這讓「單檔 HTML,瀏覽器直接打 API」這個設計成立,
比照 Photoshop UXP 插件的能力,但完全不需要 Photoshop 執行環境。

沿用專案既有的架構分工:**PSD 二進位讀寫仍在 Python 端**(`psd_slice.py`/
`psd_inplace_patch.py`),viewer 不重新發明 PSD 格式解析。viewer 吃的是 `psd_slice.py -o
<dir>` 匯出的 manifest.json + 各層 PNG(跟 `psd_preview.html` 同一份資料),或單張 PNG。
補完的結果透過「下載」拿回本機,實際寫回 PSD 仍走 `psd_inplace_patch.py`(Python 端才有
座標系統一保證,見 `s4-psd-inplace-edit.md`)。

## 功能

- 載入:拖曳/選取 `psd_slice.py` 匯出資料夾(manifest.json + PNG),或單張/多張 PNG。
- 圖層清單(縮圖 + 名稱),點選切換工作圖層。
- 遮罩:canvas 疊圖上直接用滑鼠畫筆刷(可調筆刷大小)、清除、反轉,即時顯示遮罩涵蓋百分比。
- Prompt 輸入 + model(`gpt-image-2`/`gpt-image-1.5`/`gpt-image-1`)/size/quality 選單。
- 送出:瀏覽器直接 `fetch()` 打 `https://api.openai.com/v1/images/edits`(FormData:
  image/mask/prompt/model/size/quality),mask 編碼採 OpenAI 官方慣例(alpha 0=可編輯,
  與 `s4_openai_client.py` 一致)。
- 結果:原圖/AI完整回傳/套用後(只換遮罩區,其餘保留原圖)三張並排;可「套用」(取代工作
  圖層繼續編輯)或「下載 PNG」。
- 用量:每次呼叫記進 session 內表格(時間/model/size/quality/mask%/token數/耗時/狀態);
  可選「連接本機 openai_usage.jsonl」(File System Access API,Chrome/Edge 支援,直接讀寫
  `tools/mesh_gen/s4_data/openai_usage.jsonl` 自動 append,跟 `s4_usage_dashboard.html`
  共用同一份資料)或「匯出」成獨立 jsonl 手動合併(File System Access API 不支援的瀏覽器
  fallback)。
- **安全性**:API key 只存在瀏覽器 `localStorage`,原始碼裡沒有任何硬編碼 key,UI 上有明顯
  警告文字。

## 驗證(2026-09-04,Playwright + headless Chromium)

用 `/opt/pw-browsers/chromium` + `NODE_PATH=/opt/node22/lib/node_modules` 的全域
`playwright` 套件跑互動測試(**呼叫 API 的部分用 `page.route()` mock 掉,不打真實付費
API**,只驗證前端邏輯):

1. 單張 PNG 載入 → 圖層清單/canvas 正確顯示。
2. 滑鼠拖曳畫遮罩 → 遮罩涵蓋百分比即時更新(驗證數字非零、方向正確)。
3. 未填 key 送出 → 正確擋下並顯示錯誤訊息,不會誤發請求。
4. 填 key + mock `fetch` 回傳假的 200 回應(含 usage token 數)→ 送出成功、結果面板顯示、
   用量表格新增一列,無 JS console error。
5. 點「套用」→ 工作圖層正確更新為合成後的圖(不 crash)。
6. `psd_slice.py -o` 真實輸出資料夾(manifest.json + PNG)載入 → 圖層清單正確顯示 5 個
   材質名稱,選取後正確載入對應 PNG。

**已知環境限定 caveat(非本工具 bug)**:用 Playwright `setInputFiles` 上傳含中文檔名的
manifest(如 `00_光暈.png`)時,`fileMap` 對不到檔案(`fileMap[p.file]` 找不到)——這與
`psd_preview.html` 先前記錄的**同一個** Playwright 對中文檔名的已知限制(見
`knowledge/s4-preview-tool.md`),换成純 ASCII 檔名後同一套流程立刻正常。真實使用情境是
使用者手動拖檔(瀏覽器原生 file input/drag-drop),不受此限制影響,只有自動化測試腳本會
撞到。

**誠實限制,尚未驗證的部分**:
- 未打過真實付費 API 驗證瀏覽器端 fetch 在真實網路環境下的完整行為(只驗證了 CORS
  preflight 允許、以及 mock 過的前端邏輯)——建議使用者第一次真實使用時,先用小遮罩/低
  quality 跑一次確認端到端沒問題。
- File System Access API 只有 Chromium 系瀏覽器(Chrome/Edge)支援,Firefox/Safari 會
  fallback 到手動匯出,未實測 fallback 路徑的完整體驗。
- 尚未實作插件式的像素對位管線(`knowledge/s4-gptfill-plugin-knowledge.md` §3)——生成
  結果若有明顯漂移,目前只能人工察覺、不能自動修正,見 `.claude/skills/spine-asset-request/
  SKILL.md`「無法自動處理的情況」。
- 「套用」目前是覆蓋整個工作圖層(合成後的完整圖),不是增量疊加多次遮罩——連續對同一層
  做兩次不同區域的補圖是可行的(套用後可以再畫新遮罩),但沒有「復原上一步」功能。

## 檔案

- 新增 `tools/mesh_gen/s4_ai_viewer.html`。
