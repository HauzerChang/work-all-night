# 人工分割輔助工具 `s4_manual_cut.html`(使用者裁決 2026-10-12:bodice/sleeve_right 走人工)

流程:瀏覽器開 `tools/mesh_gen/s4_manual_cut.html` → 載入原圖(`assets/jiuwei_yanlian_char_crop.png`)→ 載入決策檔或
`assets/jiuwei_yanlian_char_crop.suggestions.json`(bbox_pct 也可)→ 點左側部件 → 編輯遮罩 → 匯出 `decision_manual.json`。
裁切:`python3 tools/mesh_gen/s4_decompose_cut.py <原圖> decision_manual.json -o OUT --contour manual --eval`

工具:筆刷 / 套索(點頂點,雙擊或點回起點封閉)/ 魔術棒(容差可調,預設限制在部件框內)× 加選/減選(右鍵暫時反向);
復原(Ctrl+Z,30 步)、以框填滿、反轉、清空、顯示其他部件(半透明色,看重疊)、縮放。
遮罩以 full-canvas PNG(`mask_png` data URL)存於決策檔;沒畫遮罩的部件在 manual 模式退回矩形並警告。

驗證(2026-10-12,Playwright 實跑):載圖→載建議檔(20 部件)→bodice 框填滿→套索減選→筆刷→匯出(有遮罩 1)→
`--contour manual` 裁出 bodice alpha 覆蓋 90.8%(挖洞生效),其餘 19 件退回矩形並警告。
限制:魔術棒容差判定為 RGB 絕對差總和近似;半透明袖子(sleeve_right)建議用套索+筆刷,不建議魔術棒。
