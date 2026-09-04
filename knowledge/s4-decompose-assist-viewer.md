# S4 輔助拆圖 Viewer(六階段第6點)

> 承接 `s4-decompose-restage-plan.md` 的六階段重設計。本篇記錄第6點「輔助拆圖 viewer」
> 的實作與驗證,同時關閉該篇留下的兩個開放技術問題之一(PSD 寫入路徑,見下方)。

## 目的

六階段設計把「語意理解」「邊界決策」「像素修補」分開負責。第1/2點(Claude 語意分析,產出
part list JSON)只能給**建議**,不能替使用者做最終決定——尤其是像九尾焰蓮案例裡「九尾同色
重疊」「長髮與尾巴邊界不清」這類 Claude 自己誠實承認低信心的部件。使用者需要一個工具能:

1. 看到 Claude 的建議框疊在原圖上。
2. 依自己的判斷拖曳調整/新增/刪除/改名/改信心等級。
3. 匯出一份「使用者已確認」的決策檔(像素座標),交還給 Claude 執行第3點的實際幾何裁切。

這個 viewer 就是做這件事的純前端工具,不呼叫任何 API、不花錢。

## 檔案

`tools/mesh_gen/s4_decompose_assist.html`(單檔,~440 行,無外部依賴,瀏覽器直接開啟)。

## 功能

- **載入圖片**:拖曳或 file input,單張 PNG/JPG(包含 `psd_slice.py` 匯出的 composite.png)。
- **載入建議(選填)**:讀取 Claude 產出的 part list JSON(`bbox_pct` 格式,見
  `s4-decompose-restage-plan.md` 的 schema),依目前圖片尺寸自動換算成像素框,套用信心色
  (綠 high / 黃 medium / 紅 low / 藍 user_confirmed)。跳過 `bbox_pct` 含 `null` 的項目
  (呼應 schema 允許「完全無法定位、留給使用者從零框」的情況)。沒有建議檔也能完全手動框。
- **互動式框選編輯**(canvas,`baseCanvas` 顯示圖 + `overlayCanvas` 疊框):
  - 空白處拖曳 = 畫新框。
  - 點框 = 選取,右側面板可編輯 `id`/`label`/`confidence`/`notes`。
  - 拖曳框內部 = 移動;拖曳四角小方塊(`HANDLE_R=6px` 容許誤差)= 調整大小。
  - 選取後 Delete/Backspace 刪除(輸入框有焦點時不觸發,避免打字誤刪);Esc 取消選取。
- **右側部件清單**:即時同步框的數量/顏色/標籤,可點選/點 × 刪除。
- **匯出決策檔**:輸出 JSON(`source_image`/`image_size`/`generated_by`/
  `parts:[{id,label,confidence,notes,bbox_px:[x0,y0,x1,y1]}]`,座標為**像素**,不是
  百分比——跟輸入的 `bbox_pct` 建議檔格式刻意不同,方便下游第3點直接用整數像素裁切,不用
  再換算)。

## 驗證(Playwright,headless Chromium,零 API 呼叫)

用 chunk 43 產出的真實素材測試:`assets/jiuwei_yanlian_char_crop.png`(460×898)+
`assets/jiuwei_yanlian_char_crop.suggestions.json`(20 個建議部件,含多個 low confidence
案例如 `tails_mass`)。

1. 圖片載入 → `已載入 jiuwei_yanlian_char_crop.png(460×898)`,正確。
2. 建議 JSON 載入 → `已套用 20 個建議框(0 個因座標不完整跳過)`,`bbox_pct`→`bbox_px`
   換算正確(用 `image_size` 反推抽樣核對,如 `fox_ears` 換算後 `[138,0,345,72]`,對應
   `bbox_pct [30,0,75,8]` × 460/898,誤差在四捨五入範圍內)。
3. 模擬滑鼠拖曳畫新框 → 部件數 20→21,新框自動選取、編輯面板正確顯示預設值
   (`label:"新部件"`, `confidence:"medium"`)。
4. 編輯欄位(label/confidence/notes)→ 即時同步到清單顯示文字。
5. 點清單列選取既有建議框(`head`)→ 編輯面板正確載入該框資料。
6. 刪除鈕刪除選取框 → 21→20;鍵盤 Delete 刪除另一框(先點畫布轉移焦點,避開輸入框吃鍵盤
   事件的分支)→ 20→19。
7. 匯出 → 下載檔案解析為合法 JSON,19 個部件,每個都有 4 元素合法數字的 `bbox_px`,
   欄位結構符合設計。

全程 **零 JS console error**。

## 誠實限制

- 這個工具只做「使用者確認邊界」這一步,**不做**任何影像處理(不裁切、不生成、不呼叫
  任何 API)——裁切執行是下一步(第3點),要交還給 Claude 讀決策檔後用 Python/Pillow 之類
  做實際幾何裁切。這個 viewer 本身完全不知道「裁出來的圖會長怎樣」。
- 框與框之間目前沒有防呆(允許重疊、允許超出畫布邊界、允許 id 重複——`id` 重複時已擋
  且跳出提示,但沒有其他驗證,例如沒檢查 `bbox_px` 是否在圖片範圍內)。使用者若拖出畫布,
  座標可能是負值或超過圖片寬高,第3點裁切時要自行 clamp。
- 沒有「復原(undo)」機制,刪除/清空全部都無法復原(清空全部有 `confirm()` 二次確認,
  單一部件刪除沒有)。
- 只支援單張圖(不支援 PSD 直接載入——若來源是 PSD,先用既有工具匯出 composite PNG 再
  丟進這裡;之後若第3點需要保留原始圖層資訊,要另外設計串接方式,本次未處理)。

## 對六階段計畫的影響

- 關閉 `s4-decompose-restage-plan.md`「尚未解決的技術問題」#1(輔助 viewer 畫面設計)。
- `s4-decompose-restage-plan.md` 的技術問題 #2(PSD 寫入路徑)本次也在旁路驗證清楚:
  用 Playwright 直接呼叫瀏覽器端 `ag-psd` 的 `writePsd(psd)`(輸入 `{width,height,
  children:[{name,left,top,right,bottom,canvas}]}` 格式的 layer 物件陣列),產出的
  `.psd` 用**獨立的 Python `psd-tools`** 重新讀取交叉驗證:兩層(不同座標/顏色)之
  圖層名稱、bbox、像素顏色三項全部精確匹配。確認 `ag-psd` 同時具備讀寫能力,足以承擔
  第3點「幾何裁切結果組回 PSD」的技術需求,不需要另外調研 `pytoshop` 等替代方案。
  這次驗證只是最小可行性測試(2 層 100×100 合成畫布),不是第3點的完整實作。
- 第3點(實際拆解 + PSD 組裝)與第4點(GPT 局部修補,可直接複用簡化後的
  `s4_ai_viewer.html`,概念上不需要新工具)**仍未開始**,等使用者用這個 viewer 對真實
  素材做出決策檔之後再繼續。

## 使用流程(給使用者)

1. 開 `s4_decompose_assist.html`。
2. 載入要拆的圖(單張 PNG,PSD 先用既有工具匯出 composite)。
3. 若已有 Claude 產出的建議 JSON,一併載入,快速起手;沒有的話直接手動框。
4. 逐一檢視/調整/新增/刪除部件框,尤其留意 Claude 標記 `low confidence` 的部件(如
   `tails_mass`)——決定要不要拆、怎麼拆。
5. 確認信心等級全部反映真實狀態(建議把使用者確認過的改成 `user_confirmed`,方便下游
   分辨哪些是原始建議、哪些是人工敲定)。
6. 匯出決策檔,連同原圖一起交給 Claude,執行第3點實際拆解。
