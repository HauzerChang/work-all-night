# S4 圖片預覽器(2026-08-28)— `tools/mesh_gen/psd_preview.html`

> 使用者直接要求:「建立 PSD 圖片預覽器,讓切圖/補圖能力能即時預覽成果」。單檔瀏覽器工具,
> 風格比照 `spine_inspector.html`(拖檔/file input,無需伺服器,vanilla JS + canvas,無外部依賴)。

## 功能

單一 HTML,兩個分頁,依載入的 `manifest.json` 內容自動判斷模式並切換:

- **切圖 Slicing**:載入 `psd_slice.py -o <dir>` 的輸出資料夾(`manifest.json` + 各件 PNG +
  `composite.png`)。左側圖層清單(縮圖、z、offset/size/opacity、顯示開關);右側「重組」canvas
  依 offset+z+opacity 即時疊圖;若有 `composite.png`(PSD 原始 composite)則多顯示「參照」+
  「差異熱圖」(premultiplied 差異,越紅差越大)+ MAE 數字,可即時看到「切圖/藏顯某層」對重組結果的影響。
- **補圖 Inpainting**:載入 `inpaint_eval.py -o <dir>` 的輸出資料夾(`manifest.json` + 各案例/
  各方法 PNG)。案例下拉選擇(`檔名::interior|edge`);頂部顯示校準狀態 chip(通過/未過);
  8 張卡片網格(真值/破洞/正對照/兩種負對照/L1 邊緣外擴/L2 cv2 Telea/L2 cv2 NS),每張標
  pass(綠點)/fail(紅點)+ 四項指標;點卡片開大圖,可切換「對 original 差異熱圖」精確看補丁
  在哪裡、差多少。

## 對應的 Python 端修改(讓輸出可被預覽器讀)

- `psd_slice.py`:`slice_psd(..., out_dir=...)` 現在額外存 `composite.png`(PSD 完整 composite,
  供預覽器比對用),`manifest.json` 多一個 `"composite"` 欄位。**純新增,回傳的 `manifest`/`parts`
  結構不變**,已確認 `build_spine.py`/`analyze_target.py`/`validate_build.py`/`validate_flat_recall.py`
  等下游消費者只用 `parts` list(依 `e["file"]` 個別取用),不受影響(`validate_build.py` 對
  `robot_parts.psd` 重跑仍 `overall_pass: true`)。
- `inpaint_eval.py`:`run_one()` 現在也存「真值原圖」「破洞輸入」兩張 PNG(先前只存各方法補完結果),
  每個方法的分數字典多一個 `"file"` 欄位;`-o` 給定時額外寫出 `manifest.json`(整份 report,含
  檔名參照)。stdout JSON 結構向後相容(只新增欄位)。

## 使用方式

1. 產生資料夾:
   - 切圖:`python3 tools/mesh_gen/psd_slice.py <psd> -o <dir>`
   - 補圖:`python3 tools/mesh_gen/inpaint_eval.py <png...> --modes interior edge -o <dir>`
2. 瀏覽器開 `tools/mesh_gen/psd_preview.html`(無需伺服器,`file://` 可直接開)。
3. 把 `<dir>` 整個資料夾拖進「拖放區」,或用「Choose Files」多選該資料夾內所有檔案
   (manifest.json 必須跟資料一起選,才能被辨識)。會自動判斷是切圖還是補圖 manifest 並切分頁。

## 驗證(2026-08-28,Playwright + headless Chromium)

用 `/opt/pw-browsers/chromium-1194` + 全域 `playwright`(node,`NODE_PATH=/opt/node22/lib/node_modules`)
跑過三類互動,截圖確認:

- 切圖:載入 `robot_parts.psd` 切圖輸出 → 重組與參照 pixel-perfect 疊合(diff MAE 0.02/255,近乎純藍
  即無差異);關掉「左手」圖層 → 重組正確露出破洞、diff 熱圖精準框出左手輪廓(MAE 升到 8.23)。
- 補圖:載入身體(interior 洞)案例 → 8 張卡正確顯示,pass/fail 紅綠點與 `inpaint_eval.py` 的
  JSON 輸出逐項吻合;開 L1 邊緣外擴大圖,切換「對 original 差異」→ 熱圖精準框出洞的圓形範圍,
  視覺清楚呈現前次交接文件量化出的「補丁模糊、補不出機械細節」結論。

⚠️ **測試時發現的環境限定 caveat,與工具本身無關**:Playwright 的 `setInputFiles` 在本容器對
**含中文檔名的檔案會靜默丟棄**(`ERR_BLOB_REFERENCED_FILE_UNAVAILABLE` / `input.files` 少了對應筆數),
即使是最小 repro(空白頁 `<input type=file>`)也重現,證實與 `psd_preview.html` 的程式碼無關。改用
`DataTransfer` + `new File([bytes], name)` 直接模擬瀏覽器原生拖放(繞過 `setInputFiles` 的上傳通道)
即可正確保留中文檔名並通過全部測試 —— 這才是貼近真實使用者「拖資料夾/選檔案」路徑的測試方式。
**真實瀏覽器(非自動化)用原生檔案對話框/拖放不會有此問題**;此限制只影響「日後想用 Playwright
`setInputFiles` 自動化本工具的中文檔名資料夾」這種測試場景,記錄下來省得下次重踩。

## 誠實界定

- 差異熱圖 / MAE 為瀏覽器端即時粗算(供快速視覺檢查),**非正式驗收指標** —— 正式判定仍以
  `psd_slice.py --eval` 的 `premult_rgb_mae` 與 `inpaint_eval.py` 的四項指標為準(已在頁面上
  用黃色提示標註)。
- 目前只吃「資料夾/多檔選取」路徑;若要接單一 zip 或伺服器路徑,需再加載入方式(非本次需求範圍)。
