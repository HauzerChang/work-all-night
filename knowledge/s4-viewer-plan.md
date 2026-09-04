# S4「viewer」路線圖 + V1(PSD 純瀏覽器端解析)完成

> 分支 `claude/spine-s4-inpainting`,2026-09-04(chunk 37)。前置:chunk 34 使用者裁決
> 三項方向之一——「viewer(Photoshop 插件 HTML 版):PSD 檢視/編輯 + 與 ChatGPT 即時
> 溝通」,方向已定但「尚未拆解成有界工作塊」。chunk 35 把當次排程資源用在候選17(需要
> API key,本次 session 環境變數未帶 key,技術上做不了),故本次改推進不依賴 API key、
> 可獨立驗證的 viewer 路線。

## 為什麼是這個工作塊(對這次 session 的判斷)

candidate 17(gpt-image-2)的下一步是「先定生成式評分方式再擴大樣本」——但擴大樣本需要
真的呼叫 API,而本次排程執行環境**沒有 `OPENAI_API_KEY`**(chunk 34 已記錄:使用者的 key
只在對話當次的暫存 shell 變數用完即清,不寫入任何檔案/環境設定,故下次排程 session 不會
繼承)。這代表沒有活人在場提供 key 的自動化排程 session,本質上無法繼續候選17的真實呼叫
實驗。viewer 方向(chunk 34 第3項裁決)則明確記錄「**不受候選17網路狀況影響,可獨立先
開工**」——且其 API key 使用模式是「使用者在自己瀏覽器輸入,存 `localStorage`」,不經過
此排程容器,天生不受此問題影響。故本次選擇推進 viewer。

## 路線圖(拆解為有界工作塊,比照 candidate 17/1b 的候選編號慣例)

viewer 的完整目標「PSD 檢視/編輯 + 與 ChatGPT 即時溝通做切圖/補圖」規模等同於把
`psd_slice.py`/`psd_inplace_patch.py`/`s4_openai_client.py`(Python,S4 既有補圖 pipeline)
整支搬進使用者瀏覽器、變成純前端單檔工具(比照 `spine_inspector.html`/`psd_preview.html`
architecture)。依 `RULES.md`「步驟太大→先拆子步驟,這次只做第一個」,拆解如下:

- **V1(本次完成)**:純瀏覽器端 PSD 解析——載入 .psd → 圖層樹(含巢狀 group)+ 逐圖層
  metadata(bbox/opacity/blendMode/visible/clipping)+ composite 渲染 + 逐圖層點陣圖預覽。
  這是後續所有步驟的地基:沒有可靠的瀏覽器端 PSD 讀取,「檢視/編輯」無從談起。
- **V2(下一步候選)**:互動編輯——遮罩繪製 UI(圈選要補的區域,產生 mask,比照
  `s4-gptfill-plugin-knowledge.md` 的 8px/24px dilate 慣例)+ 依 visible 開關即時重新
  合成(目前 V1 只顯示 PSD 內建的 composite 快照,不支援互動式顯示/隱藏圖層後重繪)。
- **V3**:與 ChatGPT/gpt-image-2 即時溝通——把 `s4_openai_client.py` 的核心邏輯(mask
  編碼、prompt 組裝、API 呼叫)搬成瀏覽器端 `fetch()`,key 存 `localStorage`(使用者
  自行輸入,不寫入原始碼/不進 git,呼應 chunk 34 記錄的安全設計)。
- **V4**:寫回——`writePsd`(ag-psd 也支援寫入)把 V3 補完的圖層資料寫回同一份 PSD 的
  同一組全域座標,呼應 `psd_inplace_patch.py` 已建立的「PSD 內編輯,不匯出裁切 PNG 另外
  換算座標」原則(`knowledge/s4-psd-inplace-edit.md`)。
- **V5**:對位管線——生成結果不會像素對位(候選17已知的限制,見
  `s4-gptfill-plugin-knowledge.md` §3),V3/V4 若要真的可用,晚一點需要搬插件的五層對位
  邏輯(平移/縮放/位移場/次像素/接受門檻),量級與 V1-V4 加總相當,獨立列出。

**本次(chunk 37)只做 V1**,且做完就有自己的驗收證據,不與 V2+ 混在同一輪。

## V1 實作:`tools/mesh_gen/psd_viewer.html`

單檔架構,比照 `spine_inspector.html`/`psd_preview.html`慣例(拖檔或 file input,無需
伺服器)。核心解析庫是 **ag-psd**(npm 套件,MIT,主動維護,對 Node/瀏覽器兩端都原生
支援,`readPsd(ArrayBuffer)` 直接回傳含 `HTMLCanvasElement` 的圖層樹,無需 polyfill)。

- CDN 載入比照 `SPINE_CDNS` 多來源 fallback 慣例(`AGPSD_CDNS`:jsdelivr npm CDN → unpkg
  → cdnjs,皆指到 `dist/bundle.js`,UMD 掛在 `window.agPsd`)。
- 圖層樹遞迴解析 ag-psd 的巢狀 `children`(group 有 `children` 屬性,一般圖層沒有,
  依官方 README_PSD.md 慣例判斷),攤平成含 `path`(含 group 路徑)的清單方便顯示與 API
  查詢。
- UI:左側圖層樹(縮排顯示巢狀、group/kind 標籤、顯示/隱藏樣式提示)、中央 composite
  畫布、右側 inspector(選取圖層的 bbox/opacity/blendMode/clipping 等 metadata + 該圖層
  自己的點陣圖預覽)。
- **Phase-2 API**(比照 `CLAUDE.md` 的 `window.spineTool` 慣例,供 agent 自主驅動/驗收,
  不依賴模擬使用者拖檔):`window.psdViewerTool = { ready(), loadFromArrayBuffer(buf),
  getDocInfo(), getLayers(), getCompositeDataURL(), getLayerDataURL(name), selectLayer(name) }`。

## 自我驗證(headless,Playwright + 本機 vendor 副本)

此排程容器網路政策擋 `cdn.jsdelivr.net`/`unpkg.com`(候選4/17 已知同一機制;`api.openai.com`
是唯一目前另外放行的例外)。production 的 `psd_viewer.html` 仍然指向真 CDN(給使用者
自己的瀏覽器用,那邊網路正常),但要在本容器內做 headless 驗證,借用 Playwright 的
`page.route()` 把 CDN 請求攔截、回傳 `npm pack ag-psd` 下載下來的官方 `dist/bundle.js`
(僅測試環境用,不寫進 `psd_viewer.html`,不改變其 production CDN 路徑——這是驗證手段,
不是核心代碼變更)。`npm` 沒裝在此容器,改用 `curl` 直接打 `registry.npmjs.org` 的
tarball URL(允許,不同於被擋的 `unpkg.com`/`cdn.jsdelivr.net`)下載官方 `.tgz`、解壓取
`package/dist/bundle.js`。Playwright 本身用 `pip install playwright`(此容器 pip 可通)
裝上,配合系統已預裝的 `/opt/pw-browsers/chromium`。

驗收目標:對真實素材 `assets/robot_parts.psd`(5 層,含中文圖層名)、`assets/Symbol_Ww.psd`
(18 層)兩份既有測試 PSD,比對 `psd_viewer.html` 的解析結果 vs **獨立**的 Python
`psd-tools`(既有 pipeline 使用的函式庫,兩者互不共用程式碼,交叉驗證有意義)地面真值:

| 檢查項 | robot_parts.psd | Symbol_Ww.psd |
|---|---|---|
| 圖層名稱+順序完全一致 | ✅ | ✅ |
| 每個圖層 bbox(left/top/right/bottom)逐一比對 | ✅ 全部相符,0 mismatch | ✅ 全部相符,0 mismatch |
| composite 尺寸相符 | ✅ 713×693 | ✅ 180×180 |
| composite 像素比對(見下方 PMA 注意事項) | premult mean diff 0.028(/255) | premult mean diff 0.043(/255) |
| 逐圖層點陣圖擷取(`getLayerDataURL`)可用 | ✅ | ✅ |

**⚠️ 踩到一個跟 `CLAUDE.md` PMA 雷點同構的校準坑,記錄避免重踩**:composite 畫布是
RGBA,直接逐 byte 比較 raw RGBA 會在 alpha 低/為 0 的像素上炸出巨大的假差異(本次首次
比對量到 mean diff ~30~100/255)——原因是「完全透明」的像素其 RGB 值在視覺上不具意義,
`psd-tools`(Pillow 合成)與 `ag-psd`(HTML canvas 合成)兩邊各自對這些不可見像素填的
RGB 底色不同,但兩者的 alpha 通道本身幾乎完全一致(mean alpha diff ~0.007~0.008/255)。
改成 **premultiplied-alpha 比對**(`RGB × alpha/255` 再比較,呼應 `inpaint_eval.py` 既有
`premult_mae` 指標同一套邏輯)後,兩份素材的差異降到 mean 0.03~0.04(滿量程 255 分之幾)、
max 不到 3——這個殘差量級符合「PNG 編碼/canvas 內部色彩管理的無害捨入誤差」,不是解析
邏輯錯誤。**結論:ag-psd 對這兩份真實美術 PSD 的圖層結構、bbox、composite 渲染皆與獨立
的 Python pipeline 交叉驗證一致,V1 解析本身可信。**

測試腳本本身是驗證用暫存檔(在 session scratchpad,非 repo 內),不納入版控——這支
repo 目前的慣例是把「一次性驗收證據」(截圖/比對圖)排除在版控外,但**方法論本身**
(用 premultiplied 比對而非 raw RGBA)有沉澱價值,已記錄於此供未來 V2+ 或其他瀏覽器端
渲染驗證重複使用。

## 已知限制(誠實記錄,留給 V2+)

- V1 只做「檢視」,composite 是 PSD 檔內建的靜態快照(依 PSD 儲存當時的圖層可見性),
  切換某圖層的顯示/隱藏 checkbox **不會**重新合成畫面(UI 上暫時只是視覺提示，未接
  `renderAll` 的重繪邏輯)——這是刻意留給 V2 的範圍,不是遺漏。
  ⚠️ 更正:目前程式碼裡圖層樹的「隱藏樣式」只是根據 PSD 存檔當下的 `hidden` 狀態套 CSS
  灰階/斜體樣式提示,並沒有可勾選切換的 checkbox 控制項——UI 上暫無互動式顯示/隱藏,
  這點比原計畫描述更保守,避免誤導下一個 session 以為已有互動但未接线。
- ag-psd README 明列的既有限制(不支援 16bit/CMYK/部分特效等)沿用其官方文件,未針對
  本專案素材另外驗證是否會撞到;本專案兩份既有測試 PSD(RGB、8bit)都在支援範圍內。
- 未測試巢狀 group 的真實案例(`robot_parts.psd`/`Symbol_Ww.psd` 皆為扁平結構,無
  group)——遞迴解析邏輯是依官方文件寫的,但沒有真實素材可驗證 group 巢狀情境,若未來
  素材含 group 需要另外找/造樣本補測。
- 生產環境的 CDN 可達性(`cdn.jsdelivr.net`/`unpkg.com`/`cdnjs.cloudflare.com`)無法在
  此容器內直接驗證(網路政策擋),使用者實際瀏覽器環境是否暢通需要使用者自己打開驗證;
  若使用者環境也擋 CDN,`AGPSD_CDNS` 陣列可以改指向使用者能連到的鏡像或自行 vendor。

## ⚠️ 與並行 session 的工作塊撞號(合併時發現,務必先讀)

本檔完成並 commit 後 push 時發現:**同一時段有另一個 session 直接收到使用者指令**
(「可以開始製作viewer, 建立初步skill」,見 `log/s4-2026-09-04-036.md`)並已推進了
viewer,產出 `tools/mesh_gen/s4_ai_viewer.html` + `.claude/skills/spine-asset-request/
SKILL.md` + `knowledge/s4-ai-viewer-tool.md`,比本檔規劃的 V1~V5 更完整(一次做到
「PSD manifest 載入 + 滑鼠畫遮罩 + 真的接 OpenAI images/edits fetch + 套用/下載 +
用量記錄」,大約等於本檔 V1+V2+V3 的合集),且已完成 Playwright mock-API 互動驗證。
兩個 commit 各自基於同一個 parent(chunk 35)獨立推進,merge 時才發現撞號——已把
本檔工作塊改編號為 **chunk 37**(原比對過程中一度誤植為 36,已修正),讓 36 保留給
時間上更早、且是使用者直接指示的那個 commit。

**架構差異需要記住,避免下一個 session 誤用**:`s4_ai_viewer.html` 刻意選擇「PSD 二進位
解析仍留在 Python(`psd_slice.py` 匯出 manifest+PNG),瀏覽器只吃匯出物」,明確理由是
「不重新發明 PSD 格式解析」;本檔的 `psd_viewer.html` 則是反其道而行,直接在瀏覽器端
解析原始 `.psd`(引入 ag-psd 這個新相依)。兩者不是同一件事的兩個版本,是**兩種不同
架構選擇**——`s4_ai_viewer.html` 目前顯然是使用者實際會用、功能更完整的那條路徑,
**視為 viewer 的主線**;`psd_viewer.html` 保留作為一個獨立驗證過的能力(可以不跑 Python
匯出、直接拖 .psd 原檔進瀏覽器查看),但**不應被當成 V1→V2→V3 路徑上的必經步驟**——
若之後要繼續往 `s4_ai_viewer.html` 那條主線疊加功能,不需要先接 ag-psd。本檔原本規劃的
V2(互動遮罩)/V3(ChatGPT溝通)在主線上已經完成,不需要重做。

## 下一步(建議,已依撞號現況更新)

1. viewer 主線(`s4_ai_viewer.html`)已完成初版且經 mock 驗證,尚未打過真實付費 API
   端到端驗證——建議使用者第一次真實使用時先用小遮罩/低 quality 跑一次確認。
2. `psd_viewer.html`(本檔產出)若要繼續獨立發展,原規劃的 V4(寫回 PSD)/V5(像素對位
   管線)仍是合理候選,但優先度應該重新評估——如果主線已經走 manifest+PNG 路徑,「瀏覽器
   端直接讀寫原始 .psd」的價值主要在「不必先跑一次 Python 匯出」這個便利性,不是核心
   缺口,不建議在還沒被使用者要求前貿然繼續投入。
3. 候選17(擴大 gpt-image-2 樣本)需要使用者在排程環境設定持久化的 `OPENAI_API_KEY`
   (例如透過 Claude Code on the web 的 environment secrets 機制,而非每次對話貼一次),
   否則自動化排程 session 結構性地無法繼續——這點應該明確回報使用者,不要每次排程都
   重新發現同一個阻塞。
4. skill(`spine-asset-request`)已有初步版,後續依實際使用回饋迭代即可,不需要本檔
   額外規劃。
5. **流程面教訓**:這次撞號的根因是兩個 session 都從同一個 stale `STATE_S4.md`(chunk
   35 版本)出發,其中一個是使用者直接對話觸發、另一個是排程自動觸發,彼此看不到對方
   進度就都推進了同一個方向。目前的檔案隔離契約防的是「S4 排程 vs 主排程」衝突,沒有
   涵蓋「多個 S4 session 並行」這個情境——如果使用者會同時開對話 session 又讓排程跑,
   之後可以考慮在動工前先 `git fetch` 確認 remote HEAD 是否已經前進,而不是只看本地
   checkout 當下的 `STATE_S4.md`。

## 檔案

- 新增 `tools/mesh_gen/psd_viewer.html`(V1,純前端,production CDN 依賴)。
- 新增本檔(`knowledge/s4-viewer-plan.md`)。
- `knowledge/README.md` 尾端 append 索引。
- 未修改任何既有 production 代碼(`inpaint_eval.py`/`psd_slice.py`/
  `psd_inplace_patch.py`/`s4_openai_client.py` 皆未動)。
