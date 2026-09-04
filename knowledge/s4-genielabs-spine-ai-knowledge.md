# S4 外部知識吸收:GenieLabs `spine-animation-ai`(開源 Claude skill)

> 分支 `claude/spine-s4-inpainting`,2026-09-04(chunk 38)。使用者分享
> `https://github.com/GenielabsOpenSource/spine-animation-ai`,要求評估能否優化
> `spine-asset-request` skill。透過 `WebFetch` 讀取 README/SKILL.md/`split_character.py`/
> LICENSE(未 clone 原始碼進本 repo)。

## ⚠️ 授權限制(務必遵守,優先於任何技術內容)

**授權為 PolyForm Noncommercial 1.0.0,明確禁止商業使用**(「任何目的都允許,商業目的除外」)。
`CLAUDE.md` 開頭明載本專案環境是「lula slot game」,屬商業專案。**因此本檔只做知識萃取
(技術思路/參數/演算法選型),不得複製/移植/衍生任何原始碼**——跟處理 `s4-gptfill-plugin-
knowledge.md` 同一種紀律,而且這次授權條款更明確,風險更需要留意。任何要落地的實作都必須是
**獨立重新實作**,不可對照原始碼逐行翻譯。

## 專案概覽

一個已發布的開源 **Claude skill**(有自己的 `SKILL.md`,GitHub Actions 自動重建),定位是
「骨架綁定協駕員」,pipeline:身體部件 PNG → SIFT+RANSAC 自動定位 → 建構 Spine JSON(骨架
階層+繪製順序)→ 紋理圖集打包 → 官方 Spine Web Player HTML 預覽。技術棧:Python(OpenCV/
Pillow/NumPy)+ Google Gemini(部分模組)。目標版本 **Spine 4.2**(本專案是 3.8,JSON 格式
細節不完全相通,見下方)。

## 兩個對本專案有實質參考價值的技術思路

### 1. ★★ `split_character.py`:用生成式模型「重繪成已拆件版面」,再用經典 CV 切——
**直接回應本專案「平圖自動拆件」的既有誠實限制**

`CLAUDE.md` 記載的既有結論:「平圖(未分層)自動拆件在 CPU 到頂(同材質語意召回 0),升級
需 GPU」——這假設的路徑是「對原圖做語意分割」,這件事對糾纏在一起的美術圖確實極難。

`split_character.py` 換了一個角度:**不對原圖做分割,而是請生成式模型把角色重繪成一個
「部件已經物理分離、留白間距、白色背景」的新版面**(這對生成式模型是簡單得多的任務——它本來
就會生成新圖,不需要理解/分割複雜的原圖),**分割這個新生成的乾淨版面**再用最基礎的 CPU
連通元件分析(8-connected components,二值化門檻+面積過濾+padding)就能可靠切開。

具體做法(思路,非程式碼):
- 呼叫一個支援圖生圖的模型(該專案用 `gemini-3.1-flash-image-preview`),正向 prompt 明確
  要求「2D 遊戲精靈圖集用途、完全解構成頭/軀幹/四肢/手腳分離、清晰間距無重疊、白色背景、
  完全匹配參考圖的風格/陰影/色調」;負向 prompt 排除 3D、風格漂移、重疊、動態姿態、背景雜物。
- 拿到重繪的「已拆件圖集」後,灰階二值化(前景 = 灰度值 < 門檻,預設 240)→ 8-connected
  components 標記連通區塊 → 面積門檻(預設 500px)過濾雜訊 → 各元件邊界框 padding 擴展
  (預設 12px)→ 非該元件像素設透明 → 逐個存 PNG。
- **誠實記錄該專案自己的限制**(其 SKILL.md 承認):**沒有命名**(只給序號 `part_00`/
  `part_01`)、**沒有 z-order**、**沒有原始座標映射回原圖**——這三項都要接後續步驟
  (`position_parts.py`,見下)才能補上。

**對 S4/S1 的意義**:這是一個**尚未實作、值得評估的新候選路徑**,原理上可以用我們已經打通
的 gpt-image-2(候選17,`s4_openai_client.py`)嘗試同一招,不需要 Gemini。如果驗證有效,
能部分解掉「平圖自動拆件」這格既有的死結——但**這是全新的候選,尚未做任何量化實驗**,不能
直接當結論,下一步應該是用本專案既有的評估器精神(合成真值/校準)先小規模驗證這招對我們的
素材有沒有用,而不是直接假設它可行。

### 2. `position_parts.py`:SIFT+RANSAC 自動定位 + 遮擋投票定 z-order —— 對 S5(骨架半自動)有參考價值

給定「參考圖(目標姿勢/組裝後的完整圖)+ 已分離的部件 PNG」,用 SIFT 關鍵點匹配 + RANSAC
估計相似轉換(4 自由度:平移/縮放/旋轉)把每個部件自動擺到參考圖裡對應的位置,小/無特徵部件
用 template matching 當 fallback,再用「兩兩部件的遮擋投票」推算繪製順序(z-order)。

已知調校參數(對「風格化遊戲美術」這個素材類型,可能是有意義的起始值,而非普適常數):
- SIFT contrast threshold 降到 **0.02**(預設通常更高,風格化美術特徵較弱)。
- Lowe's ratio test 門檻 **0.80**。
- RANSAC 接受門檻:至少 **4** 個 inlier matches。
- 合理性檢查:縮放係數落在 **0.3~3.0 倍**、旋轉角 **±20°** 內才接受,超出視為誤匹配。

**對 S5 的意義**:`Spine能力鍛鍊計畫.md` 原規劃 S5 走 RTMPose/MediaPipe(人形)+ 光流運動
分群(非人形),沒有這條「有參考圖時用經典 CV 特徵匹配自動擺位」的路徑。這是一個**互補**候選
(不是取代):在「有一張目標姿勢參考圖、要把既有部件擺上去」這個子情境下,可能比姿態估計模型
更輕量、更好除錯(SIFT 匹配可視化)。**同樣尚未驗證對本專案素材(機器人拆件、Symbol 類)是否
有效**——本專案素材風格化程度、部件複雜度跟該專案範例(`examples/sombrero/`,人形角色)不一定
同構。

## 對 Spine 版本差異的提醒

該專案鎖定 **Spine 4.2** JSON 格式(`SKILL.md` 明載:rotation 用單一屬性 `"value"`+4 元素
bezier,translate/scale/shear 用兩屬性 x/y+各 8 元素 bezier)。本專案是 **Spine 3.8**,
`CLAUDE.md` 已記載 3.8 的緊湊 bezier 是 `{"curve":cx1,"c2":cy1,"c3":cx2,"c4":cy2}` 散鍵
格式,`"stepped"`/`"linear"` 為特例——**兩個版本的 JSON 語法不相通,不可對照抄格式**,只有
「動畫生成的思路」(preset generator、bezier 緩動、bones 間相位差做 follow-through)是
可轉移的概念層知識。

## 這份 SKILL.md 本身的寫法,值得借鏡的結構(非內容)

該專案的 `SKILL.md` 有三個結構性優點,已經在 chunk 38 這次更新裡部分採納到
`spine-asset-request/SKILL.md`:
1. **Decision Tree**(ASCII 樹狀圖):依「使用者提供了什麼」分支到對應動作,一眼看懂路由邏輯。
2. **File Outputs 表格**:每個產出檔案配一句話用途,方便串接下游步驟。
3. **Limitations & Manual Intervention Required** 獨立區塊:誠實列出「什麼情況一定要人工
   介入」,不假裝全自動——這跟本專案一貫的誠實紀律(RULES.md)同型,是好的外部佐證。

## 誠實限制

- 本檔內容全部來自 `WebFetch` 讀取(README/SKILL.md/`split_character.py`/LICENSE),**不是
  逐行讀完整個 repo**,`position_parts.py`/`build_spine_json.py` 等其他腳本只讀過
  `SKILL.md` 對它們的摘要說明,未深入原始碼。
- 兩個技術思路(生成式重繪拆件、SIFT+RANSAC自動擺位)都是**尚未在本專案驗證的候選**,列入
  `Spine能力鍛鍊計畫.md`/未來 S1/S5 工作塊時,需要走本專案自己的評估器紀律(合成真值/正負
  對照校準)重新驗證,不能因為「別人的專案這樣做」就直接採信有效。
