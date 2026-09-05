# S4 — 九尾焰蓮拆解:第一份完整組裝 PSD(chunk 53)

## 背景

chunk 46 已把「拆解第3點(幾何裁切+PSD組裝)」的工具鏈(`s4_decompose_cut.py` +
`psd_node/manifest_to_psd.js`)做出來並用使用者當次手動調整過、**未持久化進 repo** 的
真實決策檔跑過一次;chunk 49 發現那份測試用決策檔跟 repo 裡持久化的
`assets/jiuwei_yanlian_char_crop.suggestions.json` 有落差,之後 chunk 49-52 全部改成
「從 `suggestions.json` 重新換算決策檔」的方式做逐項框位置複核與修正,但每次都只是
產出裁圖(`cut_rect/` PNG + `manifest.json`)驗證單一部件,**沒有真的組出一份 .psd
檔案**——第3點工具鏈跑的都是驗證用的部分輸出,不是生產交付物。

chunk 47-52 已完成「對 `suggestions.json` 全部 20 個部件至少裁圖複核一次,框完全落錯
類錯誤已無新候選」的里程碑(見 `s4-decompose-box-fix-tag-pendant.md`)。剩餘懸而未決的
`bodice`/`sleeve_right`(演算法歧異,需人工/SAM 決策)與 `hair_front`(精確語意邊界,
需 assist viewer 手動確認)都需要使用者裁決,本次排程無活人在場。**這次選擇零成本、
不需授權的動作**:既然框已經是目前最佳版本(chunk52 修正後),直接跑完整第3點 pipeline
產出一份真正的 .psd 交付物,把 chunk47-52 的框位置修正成果變成看得到、用得到的產出,
而不是停在「還要再檢查一次有沒有新的框錯誤」的迴圈裡空轉。

## 執行

1. 複用 chunk52 重建的決策檔(`tools/mesh_gen/s4_data/chunk52/decision_reconstructed.json`,
   已反映 chunk52 對 `tag_pendant` 的修正)存一份快照到
   `tools/mesh_gen/s4_data/chunk53/decision_final.json`。逐欄比對確認它確實是
   `suggestions.json` 目前版本的忠實轉換(換算 `tag_pendant`/`skirt` 的 `bbox_pct`→
   `bbox_px` 跟快照內容一致)。
2. 跑 `s4_decompose_cut.py assets/jiuwei_yanlian_char_crop.png decision_final.json
   -o cut_rect --contour rect --eval` → 20/20 部件產出,`AC1_parts_produced.pass=true`,
   `overall_pass: true`(`AC3_no_orphan` 因來源圖 100% alpha=255 略過,見工具字串說明,
   非本次新狀況)。
3. `npm install`(`tools/mesh_gen/psd_node` 首次在本環境裝 `ag-psd`/`pngjs`,之前只驗證過
   一次未持久化 node_modules)+ `node manifest_to_psd.js manifest.json cut_rect
   jiuwei_yanlian_decompose.psd` → 20 圖層 PSD,圖層名稱=各部件中文 label。

## 自我驗證

1. **AC1(裁切階段)**:`s4_decompose_cut.py --eval` 20/20 產出,`overall_pass: true`。
2. **AC2(PSD 圖層幾何 round-trip)**:用 `psd-tools` 重新開啟輸出的 .psd,逐圖層比對
   `manifest.json` 記錄的 `name`/`offset`/`size` 三項——**20/20 完全相符**。
3. **AC3(PSD 圖層像素 round-trip)**:每個圖層 `layer.composite(force=True)` 跟
   `cut_rect/` 對應的裁圖 PNG 逐像素比較(RGBA 四通道)——**20/20 `max_diff=0`**(位元
   級精確,ag-psd 讀寫無損)。
4. **PSD composite() 健全性**:`psd.composite(force=True)` 正常回傳 460×898 RGBA、
   全像素 alpha=1.0(來源本為扁平不透明圖,非 chunk28 記錄過的「重存後合併預覽壞掉」
   那種案例——這裡是首次寫入,非重存,不適用該已知坑)。

全部三項 AC 都是可重跑的量化檢查(psd-tools 重新讀檔逐欄/逐像素比對),不是肉眼判斷。

## 誠實限制

- 這份 PSD 用的框位置反映 chunk52 為止的修正水準,**`bodice`/`sleeve_right`
  (chunk48 已知演算法歧異案例)與 `hair_front`(跟 `head`/`fox_ears` 大幅重疊、髮型
  本身無清楚瀏海分界)兩類已知問題原樣保留在這份 PSD 裡**,未來這兩類決議底定後需要
  重跑本 pipeline 產生新版 PSD,這份不是「最終定案」交付物,是「目前最佳可用框」的
  快照。
- 邊緣 bleed(矩形窗口裁切鄰接部件內容)按既有授權原樣保留在各圖層裡,不是新引入的
  限制,是 chunk46 就拍板的切割階段設計(見 `s4-decompose-cut-tool.md`)。
- `manifest_to_psd.js` 的 `node_modules` 此環境未持久化(容器重建會清空),下次排程
  若要重跑本 pipeline 需要重新 `npm install`(`package.json`/`package-lock.json` 已在
  repo,`npm install` 應為離線可重現,除非套件源不可達)。
- 未做第4點(GPT 局部修補),那是六階段的下一步,且需要 API key 授權(候選17同一個
  阻塞點)。
- 未重跑 `--contour sam`(容器未持久化 MobileSAM 權重,同既有限制)。

## 檔案

- 新增 `tools/mesh_gen/s4_data/chunk53/decision_final.json`(快照)、
  `tools/mesh_gen/s4_data/chunk53/cut_rect/`(20 張部件 PNG + composite.png +
  manifest.json)、`tools/mesh_gen/s4_data/chunk53/jiuwei_yanlian_decompose.psd`
  (本次產出的完整 20 圖層 PSD)。
- `tools/mesh_gen/psd_node/node_modules/` 為本次 `npm install` 產物(容器內暫存,
  已在 `.gitignore` 範圍,不預期被提交;若被提交下次排程可省略 install)。
- 未修改任何既有 production 代碼(`s4_decompose_cut.py`/`manifest_to_psd.js` 沿用
  chunk46 版本,零改動)。
