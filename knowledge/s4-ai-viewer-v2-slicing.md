# S4 AI Viewer v2:新增切片/拆解/需求精靈(2026-09-04,chunk 39)

> 分支 `claude/spine-s4-inpainting`。使用者要求(chunk 38 對談延續):
> 「viewer 也需要能夠有拆圖功能(目前只有補圖),指標是匯入2D圖,能夠進行拆解/切片/補圖等等
> 操作,更進階是能夠收集spine設計需求,規劃出編輯圖片的方向」。

## 決策:擴充既有 `s4_ai_viewer.html`,不是另開新檔

viewer 主線是 chunk 36 的 `tools/mesh_gen/s4_ai_viewer.html`(見 `s4-ai-viewer-tool.md`)。
本次直接在同一個檔案上擴充成 4 個分頁,而不是像 chunk 37 的 `psd_viewer.html` 那樣另開
獨立檔案——理由:使用者要的是「一個工具能做完整件事」,不是分散的多個工具;既有補圖邏輯
(mask 繪製、OpenAI 呼叫、用量記錄)可以直接被新分頁複用(`callOpenAiEdit()` 抽成共用
函式),沒有重新發明的必要。

## 新增的三個分頁

### 切片(PSD 圖層匯出)

沿用 chunk 37(`psd_viewer.html`)已驗證過的 ag-psd 解析邏輯(同一套 CDN fallback、圖層
遞迴攤平),但這次**不是另一個檢視器**,而是把解析出的圖層直接餵進既有的「圖層/圖片」
共用清單——選檔邏輯改成三路辨識:拖 `.psd` 原檔 → ag-psd 解析;拖
`manifest.json`+PNG(`psd_slice.py` 匯出物)→ 走既有邏輯(不變);拖單張/多張 PNG → 當
獨立圖片清單(不變)。切片分頁本身只加兩個東西:composite 預覽 canvas、每個圖層清單項目
右側的「⬇下載」按鈕(取代 Python `psd_slice.py -o` 匯出檔案的功能,但完全在瀏覽器端完成,
不需要伺服器/Python)。

**跟切圖 pipeline 的分工**:這個「下載單一圖層 PNG」不等於 `psd_slice.py` 的完整輸出
(沒有 manifest.json、沒有 offset/z/opacity 的結構化紀錄,只是純圖片)。如果後續要接
`psd_inplace_patch.py`/`atlas_crop.py` 等既有 Python pipeline,還是建議走 `psd_slice.py`
產生完整 manifest;這個瀏覽器內建切片功能定位是「快速預覽/單獨抽取一兩個圖層」,不是要
取代整條 Python pipeline。

### 拆解(平圖,明確標示實驗性)

**目標**:給一張完全沒有分層的平面角色圖,嘗試自動拆出部件。這是 `CLAUDE.md` 記載的既有
死結(CPU 語意分割做不到),chunk 38 從 GenieLabs `spine-animation-ai` 的
`split_character.py` 萃取到一個思路(不抄程式碼,見 `knowledge/s4-genielabs-spine-ai-knowledge.md`):

1. 呼叫 gpt-image-2(用既有 `callOpenAiEdit()`,mask 用「全域可編輯」——alpha 全 0 的空白
   canvas,等同於「沒有 mask 限制,整張圖都能重繪」),prompt 要求把角色重繪成「部件已分離、
   留白間距、白色背景」的乾淨版面(prompt 內容已預填在 UI,可自行調整)。
2. 對重繪結果跑瀏覽器端 **8-connected components** 分割(獨立重新實作,不是抄
   `split_character.py` 的 Python 版):灰階二值化(門檻可調,預設 240)→ BFS 標記連通
   區塊(用陣列當佇列,避免遞迴爆疊)→ 面積過濾(預設 500px)→ bounding box + padding
   (預設 12px)→ 逐部件裁切,非該部件像素設透明 → 每個部件可單獨下載。

**已知限制**(對照 `split_character.py` 自己承認的限制,獨立實作後依然存在,是問題本質,
不是實作疏漏):**沒有命名**(只給序號)、**沒有 z-order**、**沒有座標映射回原圖**——
這三項都需要後續步驟才能補上,本次未實作。

**⚠️ 誠實限制,務必讓使用者知道**:這整招對本專案素材是否有效**完全沒有驗證過**。UI 上
已用文字明確標示「實驗性」+ 完整警告。驗證方式(下一步若要做):用本專案既有的評估器精神
(合成真值/正負對照校準)在真實素材上測試,而不是主觀看結果順不順眼。

### 需求精靈

規則式(非 AI)決策精靈,直接對照 `.claude/skills/spine-asset-request/SKILL.md` 的缺口
分類表(A/B/C/D 四類 + 本次新增 E 類「完全沒分層的平圖」),點選最接近的情境,顯示對應建議
文字 + 一鍵跳轉到對應分頁。**不呼叫任何 API,不花錢**——是規則表的視覺化,不是真的「收集
需求後智慧規劃」。**誠實界定**:使用者原話「更進階是能夠收集spine設計需求,規劃出編輯圖片的
方向」如果指的是真正的自然語言理解 + 智慧規劃,這個版本還沒做到那個程度(那需要接 LLM API
做推理,是完全不同量級的功能,本次未做,留給下一步視需要評估)。目前這版是「把 skill 的
決策邏輯做成可點選的介面」,幫使用者快速對照自己的情境屬於哪一類、該去哪個分頁。

## 驗證(2026-09-04,Playwright + headless Chromium,全部 mock 真實付費 API)

5 組互動測試,零 JS console error:

1. **Tab 切換**:4 個分頁逐一點擊,`active` class 正確套用。
2. **補圖流程回歸**(確認擴充後既有功能沒壞):單張 PNG 載入→自動跳轉補圖分頁→畫遮罩→
   mock API 呼叫→結果面板顯示→用量表格新增一列→套用成功,與 chunk 36 原版行為一致。
3. **切片(真實 PSD)**:`assets/robot_parts.psd` 透過 CDN mock(`page.route()` 攔截
   `ag-psd@31.0.2` 請求,回傳 `npm pack` 下載的官方 vendor 副本,production 仍走真
   CDN)解析,正確顯示 5 個圖層、composite canvas 正確渲染、單一圖層下載按鈕點擊不 crash。
4. **拆解(合成測試圖)**:自己畫一張 300×300 白底+3 個獨立色塊的合成圖當「AI 重繪結果」
   (mock API 直接回傳這張合成圖,不需真的呼叫),跑分割邏輯——**正確偵測出 3 個部件**,
   面積/bbox 數字合理。這驗證了 connected-components 演算法本身邏輯正確,**不是**驗證
   「gpt-image-2 重繪的結果分割得好」(那需要真實付費呼叫才能驗證,本次未做)。
5. **需求精靈**:5 張選項卡渲染正確,點選後顯示建議文字,跳轉按鈕正確切換到對應分頁。

## 誠實限制(整體)

- 拆解功能的核心假設(生成式重繪+簡單分割能解決平圖拆件)**完全未在真實素材/真實付費
  API 呼叫下驗證**,只驗證了「如果拿到一張像範例那樣的乾淨版面,分割演算法能正確切開」。
- 切片分頁的「下載單一圖層」不含 manifest 結構化資訊,不能直接餵給既有 Python pipeline
  (`atlas_crop.py` 等)需要的格式,只是原始 PNG 檔。
- 需求精靈是規則表,不是真正的「收集需求做智慧規劃」——如果使用者要更進階的自然語言
  規劃能力,那是下一步的獨立工作項(需要接 LLM 推理)。
- 仍未實作插件式像素對位管線(補圖/拆解的生成結果都可能有像素漂移)。

## 檔案

- 更新 `tools/mesh_gen/s4_ai_viewer.html`(510 行 → 擴充為 4 分頁架構)。
