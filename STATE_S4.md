# S4 進度狀態 (STATE_S4) — 補圖/切圖獨立排程續跑核心

> 本檔僅供 **S4 專屬排程** 使用(分支 `claude/spine-s4-inpainting`)。主排程請看 `STATE.md`。
> 每次 S4 session 結束前**必須**更新此檔。冷啟動背景見 `handoff_S4.md`,執行指令見 `prompts/run_s4.md`。

## 專案狀態

`ACTIVE`  <!-- SETUP / ACTIVE / BLOCKED / DONE -->

> **chunk 38(2026-09-04)**:使用者分享外部開源 Claude skill(GenieLabs
> `spine-animation-ai`)要求評估優化 `spine-asset-request`。萃取兩個未驗證候選(生成式
> 重繪拆件版面、SIFT+RANSAC自動擺位)更新進 skill,**授權為 PolyForm Noncommercial 禁止
> 商業使用,只做知識萃取不抄程式碼**。見下方「chunk 38」段落與
> `knowledge/s4-genielabs-spine-ai-knowledge.md`。
>
> **⚠️ chunk 36/37 是同一時段兩個並行 session 撞號的結果,合併時才發現(見下方兩段
> 與 `knowledge/s4-viewer-plan.md`「與並行 session 的工作塊撞號」章節,下一個 session
> 動工前務必先讀)**:
>
> **chunk 36(2026-09-04,使用者直接指示,時間較早)**:使用者要求推進 viewer + skill
> 兩項。完成 `tools/mesh_gen/s4_ai_viewer.html`(純瀏覽器端,驗證 OpenAI API 允許 CORS,
> 不需要中介後端/不依賴 Photoshop;PSD 解析仍留在 Python `psd_slice.py`,瀏覽器吃匯出的
> manifest+PNG)+ `.claude/skills/spine-asset-request/SKILL.md`(初步版,把既有 S4 工具
> 串成「需求→判斷缺口→驅動切圖/補圖→驗證→記錄」流程)。見 `knowledge/s4-ai-viewer-tool.md`。
>
> **chunk 37(2026-09-04,排程自動觸發,時間較晚,獨立不知情地做了同名工作)**:本次排程
> session 環境變數**沒有 `OPENAI_API_KEY`**(chunk 34 記錄的 key 只在對話當次暫存變數
> 用完即清,不會被下個 session 繼承)——候選17「先定評分方式再擴大樣本」的下一步結構性
> 做不了。轉向不受此限制、chunk 34 已裁決但「尚未拆解成有界工作塊」的 **viewer** 方向:
> 拆解為 V1~V5,完成 **V1(PSD 純瀏覽器端解析)**——`tools/mesh_gen/psd_viewer.html`
> (架構不同於 chunk 36:直接引入 ag-psd 在瀏覽器端解析原始 .psd,不經過 Python 匯出)。
> headless 驗證(Playwright + 本機 vendor 副本繞過此容器 CDN 阻塞,僅測試手段)對兩份
> 真實 PSD 交叉比對 Python `psd-tools` 地面真值:圖層名稱/順序/bbox 100% 相符,composite
> premultiplied 像素比對 mean diff 0.03~0.04/255。**合併後的定調**:`s4_ai_viewer.html`
> (chunk 36)功能更完整、且是使用者直接指示,視為 viewer 主線;`psd_viewer.html`
> (chunk 37)是獨立驗證過的次要能力(可不跑 Python 匯出、直接讀原始 .psd),不建議
> 視為主線 V1→V2→V3 的必經步驟(主線的等價功能已經做完)。見下方「chunk 36」「chunk 37」
> 兩段與 `knowledge/s4-viewer-plan.md`。
>
> **三項使用者裁決現況(合併兩邊後)**:(1) 候選17——技術阻塞(網路政策)已解除,已完成
> 第一次真實驗證(chunk 35),發現 1a 評分方法論可能不適合生成式輸出、下一步待定生成式
> 專屬評分方式;此外**缺持久化 API key 之前,自動化排程 session 無法繼續擴大樣本**,需
> 使用者設定 environment secret;(2) skill——**初步版已完成**(chunk 36,
> `spine-asset-request`),chunk 38 用外部知識萃取做了第一次優化(平圖拆件/自動擺位新增
> 未驗證候選路徑),後續依實戰使用回饋繼續迭代;(3) viewer——**主線初步版已完成**
> (chunk 36,`s4_ai_viewer.html`,已用 Playwright mock API 驗證前端邏輯,未打真實付費
> API 做端到端驗證);次要能力 V1(chunk 37,`psd_viewer.html`)也已完成並驗證。
> **候選15已裁決「無限期擱置」**,不再是待裁決項,見下方「chunk 33」段落。

## 範圍

S4 = 切圖 + 補圖。**(A) 切圖已大致完成**(PSD-first 對 2 真實 PSD 無損 + ⇄ Award 逐件吻合);
**(B) 補圖未開始 = 本排程主任務**。詳見 `handoff_S4.md`。

## 已完成(繼承自主排程,切圖半邊)

- ✅ PSD-first 切圖 pipeline `psd_slice.py` + 重組無損閘(合成 + 2 份真實生產 PSD 全 PASS)。
- ✅ PSD 圖層 ⇄ Award spine slot `機器人拆件/<圖層名>` 逐件對應(+2px padding)、texture-IoU 閉環(0.92~0.99)。
- ✅ `atlas_crop.py` 多頁 + derotate 方向修正(CW);給美術的 PSD 交檔契約 `knowledge/s4-psd-contract.md`。
- 誠實界定:平圖(未分層)自動拆件在 CPU 到頂(同材質語意召回 0),升級需 GPU → 屬資源決策。
- ✅ **修 `reassemble()` 超出畫布邊界 crash(2026-08-28,使用者上傳真實檔觸發)** — 圖層 offset
  為負(往左/上超出畫布)時原本會因 numpy 負索引語意 crash;已裁到畫布邊界內再疊。對真實美術檔
  `Main_idle_(ai).psd`(DJ 貓角色,offset x=-1 的背景層)驗證修好;`robot_parts.psd`/`Symbol_Ww.psd`
  回歸測試無影響。誠實發現:該角色目前只有右手單獨拆件,其餘全身黏一起,尚不足以做豐富 idle 律動。

## 已完成(補圖半邊,本排程新增)

- ✅ **chunk 0:補圖閘 v1 + Level 1/2 CPU baseline 完成(里程碑,2026-08-28)** — `tools/mesh_gen/inpaint_eval.py`
  (合成真值挖洞法,`interior`/`edge` 兩種洞;`premult_mae`/`alpha_mae`/`seam_grad_diff`/`ssim` 四指標;
  正對照 `gt`+負對照 `none`/`random` 內建 `calibration_check`)。對 `robot_parts.psd` 真實件(光暈/身體/左手)
  跑閘:校準全過(負對照皆被抓到 fail)。**量化出誠實邊界**:CPU baseline(nearest-fill / cv2.inpaint)在
  平滑漸層區(光暈)全 PASS(ssim 0.99+),但在機械細節紋理區(身體/左手)**任何洞尺寸皆 fail**(ssim 上限
  ~0.51,掃過 2%~12% 內容面積 5 種尺寸皆同);edge(咬輪廓外推)比 interior(內部內插)明顯更難。
  見 `knowledge/s4-inpaint-evaluator.md`(含完整結果表)。
- ✅ **圖片預覽器(使用者直接指定,2026-08-28)** — `tools/mesh_gen/psd_preview.html`(單檔瀏覽器工具,
  比照 `spine_inspector.html` 拖檔/file input、無需伺服器):切圖分頁即時疊圖+對 PSD composite 的差異
  熱圖;補圖分頁 8 格卡片(真值/破洞/正負對照/3 baseline)並排比對+點圖開大圖看差異熱圖。`psd_slice.py`/
  `inpaint_eval.py` 隨附新增預覽用輸出(composite.png、holed/original PNG、manifest.json),向後相容
  (下游 `build_spine.py` 等重跑 `overall_pass: true` 無回歸)。用 Playwright+headless Chromium 驗證
  互動正確。見 `knowledge/s4-preview-tool.md`(含一個環境限定 caveat:Playwright `setInputFiles` 對中文
  檔名的已知限制,與工具本身無關)。

## 架構原則:切圖/補圖都在 PSD 內編輯(使用者要求,2026-08-28,見 `knowledge/s4-psd-inplace-edit.md`)

補圖不該對 `psd_slice.py` 匯出的裁切 PNG(局部座標)編輯完就結束——那樣要自己把結果貼回
PSD 全域座標,重新發明一次 offset 換算,正是先前 `reassemble()` 踩過的 bug 類型。**改為直接
在 PSD 內編輯**:新增 `tools/mesh_gen/psd_inplace_patch.py`,讀某圖層原本的 `layer.left/top`
當唯一基準,補完的圖直接用同一組全域座標寫回同一個 PSD,座標系一致性由 psd-tools API 保證。
往後所有補圖產出都應該走這條路徑,不要停在「匯出 PNG 補完」那一步。

過程中修正兩個真實 psd-tools 陷阱:(1)寫入中文圖層名會 `UnicodeEncodeError`——改用
`Tag.UNICODE_LAYER_NAME`(`luni`)tagged block 比照真實 Photoshop 存檔慣例;(2)**重存後的
PSD,預設 `composite()` 會吃到壞掉的合併預覽圖(整張變 RGB 無 alpha)**,導致 `psd_slice.py`
的評估閘誤判(orphan_ratio 從 0 暴增到 0.55)——已在 `psd_slice.py` 兩處 `composite()` 呼叫
加上 `force=True` 修正,對原生 Photoshop PSD 回歸測試無影響(數字完全一致)。端到端驗證:
對「身體」「左手」兩層跑合成挖洞→補→寫回→`--eval` 自驗,皆 `overall_pass: true`。

## 補圖問題定義修正(使用者釐清,2026-08-28,見 `knowledge/s4-inpaint-taxonomy.md`)

補圖不是單一問題,分三種情境,**驗收標準不同**:

- **1a 拆件破綻・需表演**(如墨鏡拿掉後眼睛要眨眼):要真的畫對,通常回歸切圖/契約層。
- **1b 拆件破綻・防穿幫**(如墨鏡拿掉後臉部空洞,眼睛不表演):只要動態下不露破綻,標準比 1a 寬鬆
  很多。**⚠️ 既有 `s4-inpaint-evaluator.md` 的「CPU 補不動」結論是用 1a 嚴格標準測的,1b 情境下可能
  其實夠用,需要另一組寬鬆閘重新檢視。**
- **2 動畫規劃驅動視角外推**(如水平轉向露出原圖沒有的側/背面):本質是「原圖不存在的內容」,不是
  紋理修補,cv2.inpaint/LaMa 這類演算法對此無效;可行路徑是跟美術要額外視角參考圖(契約層)、生成式
  AI(GPU)、或動畫設計端規避真轉向。**這屬於 S1(反推分析器)的需求前移範疇,不是 S4 補圖演算法能解**。

- ✅ **1b 專用寬鬆閘完成(里程碑,2026-08-28)** — `inpaint_eval.py` 擴充 `score_1b`(自我參照,不比對
  真值洞內內容):`alpha_gap`/`seam_ratio`/`tone_gap` 三指標;正對照(gt)/負對照(none/random)校準
  全過。**核心結果驗證假設**:身體/左手(機械紋理)在 1a 嚴格標準下 fail 的 3 個 CPU baseline
  (nearest/cv2_telea/cv2_ns),在 1b 標準下**全部 PASS**——證實「CPU 補不動」是 1a 嚴格標準下的結論,
  1b(防穿幫)情境同一批廉價 baseline 其實夠用,不必升 LaMa/GPU。範圍收斂:1b 判定只在 `interior`
  模式啟用(edge 模式的洞跨真實輪廓,輪廓天然有 tone/alpha 梯度,套自我參照假設會誤判正對照本身,
  已用 gt 校準抓到並收斂範圍,非猜測)。`psd_preview.html` 補圖卡片已加上雙判定燈(1a/1b)。
  見 `knowledge/s4-inpaint-1b-lenient-gate.md`。

- ✅ **PSD 內編輯統一座標系完成(里程碑,2026-08-28)** — `psd_inplace_patch.py`(見上一節詳述),
  修正兩個真實 psd-tools 陷阱(中文圖層名寫入、composite() 合併預覽壞掉),對「身體」「左手」
  兩層端到端驗證 `overall_pass: true`。

- ✅ **修正 `fill_cv2_inpaint` 的 edge 模式 alpha 處理(2026-08-28)** — 新增
  `estimate_alpha_taper`(距離場×局部量測漸縮寬度):洞外已知背景當 0 端錨點算距離 `d_bg`,
  漸縮寬度 `ell` 從洞周圍看得到的真實 AA 邊緣像素梯度量出(不是猜的常數),`alpha=clip(255*d_bg/ell,0,255)`。
  實測發現兩個直覺解法(對 alpha 整顆跑 `cv2.inpaint`、alpha 單點最近鄰外推)反而更差(把洞中段
  該有的高 alpha 拉低),予以排除。跨 3 個原始件 + 4 個新獨立件(`Symbol_Ww.psd`)、interior/edge
  兩模式全跑:interior 持平(alpha_mae 仍 0),edge 全面改善,6 處 1a `pass` 判定翻盤(全部
  False→True,無反向)。刻意不套用到 `fill_nearest`(Level 1)——同一函式會讓環形鏤空件
  (`框`)的 ssim 判定從 PASS 翻成 FAIL,故只用在 RGB 走獨立通道的 `fill_cv2_inpaint`。順帶
  發現 1b 的 `tone_gap` 校準在新材質上不成立(列為候選 8)。見
  `knowledge/s4-inpaint-evaluator.md`、`log/s4-2026-08-28-008.md`。

- ✅ **評分→採用→落地完整鏈路打通(里程碑,2026-08-28)** — `inpaint_eval.py` 新增
  `score_candidates()`/`select_best()`(對候選 baseline 各跑一次、用 1b 分數盲選,因為真實
  補圖沒有 gt 可用 1a 選);`psd_inplace_patch.py` 新增 `patch_layer_auto()`(真實情境入口,
  呼叫端給 mask)+ `demo_auto_patch()`(自我測試:合成挖洞模擬盲選,寫回後才揭曉 1a 分數驗證
  選擇邏輯誠實)。CLI 新增 `--auto`/`--mask`。**踩到並修正一個新坑**:1b 只在 `interior` 模式
  校準過(見 `s4-inpaint-1b-lenient-gate.md`),第一版沒做這層 gating 會讓 `edge` 洞被誤標高
  信心的 `pass_1b`——新增 `applicable` 旗標(`select_best(..., applicable=mode=="interior")`),
  edge 模式一律走 fallback 並標 `1b_not_applicable_edge_mode_fallback_lowest_seam_ratio`,
  已用左手 edge 案例驗證修正生效。回歸:舊 `--method` 路徑、`psd_slice.py --eval`、
  `inpaint_eval.py` 校準流程對 `robot_parts.psd` 重跑皆無影響。見
  `knowledge/s4-inpaint-auto-select-pipeline.md`。

## 里程碑審查(chunk 26,2026-09-02):S4 核心目標已達成,建議轉維護模式

依 chunk 25「下一步」指定,候選15/17 兩個 A 類岔路本次排程無活人可裁決,故執行選項
(b):綜合盤點既有 25 個 chunk,逐項清點 S4 原始使命(切圖可靠性/補圖評估器/CPU補圖能力
邊界/1a-1b邊界實戰意義/LaMa投資值不值得/分類法有效性/類別2歸屬)——**確認每一項都已有
交叉驗證的答案,無「不知道」狀態**。剩餘候選15/17 性質是「答案已有、待裁決是否套用」的
執行層決策,不是研究缺口。**建議**:S4 核心目標已達成,維持 `ACTIVE` 但降低排程優先度,
資源轉向 S1/S2/S3/S5(符合 `PLAN.md` 既有槓桿排序);不建議標 `DONE`(候選15/17 仍是合理
後續工作,且未來接上 S1/S5 pipeline 實跑新素材可能冒出新材質類型)。**本次未新增量化實驗、
未改動任何 production 代碼**,純綜合評估。三項具體決策點彙整交還使用者:(1) 候選15
trade-off 接受與否;(2) 候選17 API key+費用授權與否(且 1b 已解決實戰標準的前提下,此項
優先度應重新評估);(3) 本排程(`claude/spine-s4-inpainting`)接下來維持現狀待命/降頻或
暫停轉資源給主排程/其他方向。見 `knowledge/s4-convergence-review.md`、
`log/s4-2026-09-02-026.md`。

**下一個有界工作塊候選(擇一推進):**
4. ✅ 已完成(見下方 chunk 16)——探測 Level 3(LaMa):網路政策部分允許,但通用預訓練權重
   不足以解 1a,且 1b 已經解決實用性問題,不建議投入。
6. ✅ 已完成(見下方 chunk 17)——用本閘測 `Symbol_Ww.psd` 其他層(icon 類,可能有更多平面
   色塊),擴大樣本、交叉驗證邊界。
7. ✅ **已調查(見下方 chunk 18)**——用 Claude vision 當人工標註代理嘗試反向校準 1b 閾值,
   結論:代理與既有數字判定高度一致,唯一浮現的落差(`身體`/`左手` 高頻細節丟失)是指標
   維度缺失、不是門檻問題,故不變更 `THRESH_1B`,留候選 16 給後續。
16. **(新候選,chunk 18 提出)** 1b 加第 4 個指標(高頻細節保留度)或把補圖貼回真實
    `assets/Award.json/atlas/png` spine 場景在 `spine_inspector.html` 跑動畫截圖比對——
    真正回答「動態動畫尺度下會不會穿幫」,比候選 7 的靜態 vision 代理更貼近實戰,但屬於
    獨立量級的工作塊(需要真實貼圖 pipeline 整合),見 `knowledge/s4-inpaint-1b-lenient-gate.md`
    候選 7 章節。**chunk 19 更新**:指標方向已被外部獨立來源具體化,見候選 18。
    **chunk 21/22 更新**:路徑 (a) 的兩次具體嘗試(候選 18「邊界證據延續性」、候選 20
    「局部高頻能量/方差比」)皆校準失敗、不採用,原因各自不同(候選 18 結構性偏向獎勵
    平滑;候選 20 正對照本身因材質局部統計不均勻而失真,且無法分辨真實紋理/拼貼假邊/
    純雜訊)。路徑 (a) 目前看來這個方向本身(用單一自我參照數字去抓「高頻細節保留度」)
    持續撞到同一類根因(材質局部統計不均勻 + 無法區分「有結構的樣式」與「量級相近的雜訊」),
    再嘗試需要換更複雜的統計量(如頻域/樣式匹配),已逼近與 1a `ssim` 職責重疊,價值存疑;
    **路徑 (b)(貼回真實 Award spine 場景跑動畫截圖比對)是目前唯一未嘗試、且不依賴發明
    新自我參照指標的路徑**,建議候選 16 若要再推進,優先做 (b)。見
    `knowledge/s4-inpaint-1b-lenient-gate.md` 候選 20 章節。
    ✅ **chunk 23 更新(見本次)**:路徑 (b) 已完成第一個真實案例(`左手`)——見下方新增段落。
18. ✅ 已完成(見上方 chunk 21)——候選 18「邊界證據延續性」不採用,見候選 16 更新。
20. ✅ **已完成(見本次 chunk 22)**——候選 16 路徑 (a) 第二次具體嘗試「局部高頻能量/方差比」
    (`tools/mesh_gen/s4_energy_ratio.py`),結論:兩個獨立失效模式,不採用。見上方候選 16
    更新、`knowledge/s4-inpaint-1b-lenient-gate.md` 候選 20 章節。
21. ✅ **已完成(見本次 chunk 23)**——候選 16 路徑 (b):補圖貼回真實 `assets/Award.json/
    atlas/png` spine 場景,headless 動畫截圖比對(`左手`,`Award_Legend_In/Loop` 11 個
    時間點)。**結論**:實際渲染尺度下(該材質全場景只佔 ~0.5~0.6% 畫布)候選7已知的高頻
    細節丟失瑕疵仍在,但不構成一眼可見的穿幫。新增 `atlas_patch.py`(已自我驗證,5 region
    round-trip 全 `max_diff=0`)、`s4_spine_render_harness.html`(多頁 atlas 正確支援,
    `spine_inspector.html` 不支援雙頁因而不可共用)、`s4_award_screenshot_compare.py`。
    **下一步(若再推進)**:擴大到 `身體`/`光暈`,或取得真實遊戲顯示縮放比例驗證佔比假設。
    見 `knowledge/s4-inpaint-spine-render-compare.md`、`log/s4-2026-09-01-023.md`。
    ✅ **chunk 24 更新**:第二個案例(`身體`,`rotate=true`)已完成,見下方。
    ✅ **chunk 25 更新**:第三個案例(`光暈`,平滑漸層,第三種材質類型)已完成,見下方——
    候選16路徑(b)三種材質類型覆蓋完成。

---

**以下三項來自 chunk 19 吸收使用者自製 Photoshop `GPT Fill` UXP 插件 v1.18(見
`knowledge/s4-gptfill-plugin-knowledge.md`)。**

19. ✅ **已完成(見下方 chunk 20)**——上下文假設重測:結論「1a 全 fail」不是零上下文的
    人工產物——interior 模式下 windowed(512px 真實場景上下文)與孤立裁切版三個 CPU
    baseline 輸出逐位元相同,edge 模式效果小且不一致,無案例翻盤。見
    `knowledge/s4-inpaint-context-window.md`。
18. ✅ **已實作與校準(見上方 chunk 21)**——「邊界證據延續性」具體化為 `grad_continuity_gap`
    (洞外邊界梯度線性外推 MAE),結論:構造本身結構性偏向獎勵平滑填補(跟設計意圖相反),
    正對照(gt)在機械紋理材質上分數比 `nearest` 平坦複製還差,不採用。候選 16 若要再推進,
    改走原構想 (a)「局部高頻能量/方差比」方向,見 `knowledge/s4-inpaint-1b-lenient-gate.md`
    候選 18 章節。
17. 🔀 **【需使用者授權,A 類岔路】headless 生成式補圖 baseline** — 插件證實使用者端已有
    可用的生成路徑(`gpt-image-2` via `api.openai.com`),它打的是純 HTTP API,原則上可從
    Python headless 呼叫(不需 Photoshop)。配方已抄齊(mask 編碼、8px/24px dilate、
    ≥512px 上下文、16 對齊、長寬比 1:3~3:1、面積下限 0.65MP、三張參考圖、prompt 模板),
    見 knowledge 檔第 4/5 節。**做法**:接成 `inpaint_eval.py` 的第 4 個 baseline
    (`gpt_fill`),用同一把尺量它是否是本專案**第一個跨過 1a 門檻(ssim>0.75)的方法**。
    **阻塞點**:需要 API key + 逐次呼叫費用 → 需使用者明確授權才可進行。
    ⚠️ **另一個必須先解的技術前提**:生成結果**不會像素對位**(會漂移+整體縮放),
    `psd_inplace_patch.py` 目前假設「補出來的像素就地落在 mask 原位」,那個假設一接生成
    路徑就破——插件的五層對位管線(平移/縮放/錨點位移場/次像素/接受門檻)已記錄在
    knowledge 檔第 3 節,是這個候選真正的工程主體,不是呼叫 API 那一行。
9. ✅ 已完成(見下方 chunk 11)——延伸候選:Symbol_Ww 沒有多層互相遮擋的真實案例可用,若要
   把「真實遮擋洞」方法論覆核 `框`/`臉部陰影`,需另找/另造有真實重疊的分層素材。
10. ✅ 已完成(見下方 chunk 13)——光暈材質 1a 邊界再校準:控制實驗排除「形狀」「位置」單一
    變數假設,誠實結論是 1a 邊界無法化約成單一合成洞參數,呼應候選 1/8「該用 1b 而非 1a」。
13. ✅ 已完成(見下方 chunk 14)——`estimate_alpha_taper` 小樣本 bug:量化觸發頻率後修正
    `min_ring`(5→20),3 組既有回歸案例 JSON diff 為空。
14. ✅ **已調查(見下方 chunk 15)**——`estimate_alpha_taper` 的另一種獨立失敗模式:拆解出
    兩個獨立根因(材質內部紋理雜訊污染 ring 統計 / 光滑材質非線性衰減使線性外推模型結構性
    失效),嘗試 4 種修法皆非零回歸,本次未修改 production 代碼,留 A 類岔路候選給使用者裁決。

**本次(chunk 22,2026-09-01)已完成:**
- ✅ **候選 20(1b「局部高頻能量/方差比」第 4 指標,候選 16 路徑 (a) 第二次嘗試)實作與
  校準完成,結論:兩個獨立失效模式,不採用** — 新增 `tools/mesh_gen/s4_energy_ratio.py`
  (`energy_ratio` = 洞內 core 局部方差 / `score_1b` 既有 `local_ring` 基準的局部方差,
  只測 interior 模式)。跨 `robot_parts.psd` 三材質(光暈/身體/左手)校準,撞到兩個獨立
  根因:(1) **光暈正對照本身失真** — gt 的 `energy_ratio` 只有 0.0036,比全部三個 CPU
  baseline(0.02~0.22)都低,呼應候選 10 已確認的材質性質(光暈局部統計空間上不均勻,
  核心陡外圈平緩),`local_ring` 這種固定外環當全域基準的設計,這次連正對照都失真,跟
  候選 8/18 是同一類根因;(2) **左手負對照鑑別力崩潰**——跨 4 個 seed(0/1/2/3)重跑
  確認非單一樣本僥倖:`random` 的 `energy_ratio`(0.83~1.67)與 `gt`(0.92~1.37)、
  `nearest`(0.75~1.33)同一數量級,分不開;且排序方向跟既有證據矛盾:已知會產生
  blocky 拼貼(非真實紋理)的 `nearest` 反而比 vision/1a ssim 都判定更好的 `cv2_telea`/
  `cv2_ns` 更貼近 gt(cv2 系列 `energy_ratio` 只有 0.08~0.17)。根因:局部方差量的是
  「數值有多跳動」而非「跳動的樣式對不對」,量級相近時無法分辨「正確高頻細節」「拼貼
  假邊」「純雜訊」三者,這已經逼近 1a `ssim` 的職責重疊(候選 16 原文就預見這個風險)。
  **決策**:不採用,不動 `score_1b`/`THRESH_1B`。候選 16 路徑 (a) 的兩次具體嘗試(候選
  18、候選 20)皆已排除,若再走這個大方向需要換能分辨「結構/樣式」而非只看「量級」的
  統計量,價值存疑;**路徑 (b)(貼回真實 Award spine 場景跑動畫截圖比對)是候選 16 目前
  唯一未嘗試、不依賴發明新自我參照指標的路徑**,建議後續優先做 (b)。本次未改動任何
  production 代碼。見 `knowledge/s4-inpaint-1b-lenient-gate.md` 候選 20 章節、
  `log/s4-2026-09-01-022.md`。

**本次(chunk 21,2026-08-31)已完成:**
- ✅ **候選 18(1b「邊界證據延續性」第 4 指標)實作與校準完成,結論:設計方向本身有結構性
  偏差,不採用** — 新增 `tools/mesh_gen/s4_boundary_evidence.py`,把 chunk 19 讀到的
  GPT Fill 插件 SHADOW REASONING prompt 具體化成 `grad_continuity_gap`(洞內像素離「洞外
  邊界局部梯度線性外推預測值」的 MAE)。校準發現核心問題:機械紋理材質(身體/左手)的
  **正對照(gt,真實內容)分數反而比平坦複製(`nearest`)差**(身體 gt=24.8 > nearest=14.9,
  左手 gt=90.6 > nearest=56.2),`probe_depth` 6px→2px(緊貼邊界)偏差依然成立,排除
  「探測太深」的解釋。**根因**:指標的預測基準是「局部線性(=平滑)外推」,真正有高頻
  細節的材質本來就不服從平滑外推(這正是「有紋理」的定義),但把洞抹平的 baseline 天生
  貼近自己的平滑預測值——偏誤方向跟設計意圖(抓「過度平滑的奶油糊」)剛好相反,換算
  `recon_gap/gt_gap` 比值也救不回來(nearest 比值 0.60~0.62,即比真實內容更「連續」)。
  不是候選 8/6 那種「換個正規化就好」的門檻問題,是構造本身自我矛盾。**決策**:不採用,
  未改動 `inpaint_eval.py`/`THRESH_1B`;候選 16 若要再推進,建議改走原構想 (a)「局部高頻
  能量/方差比」方向而非本次的梯度外推路線(那條路不會因為獎勵平滑而倒錯方向)。見
  `knowledge/s4-inpaint-1b-lenient-gate.md`(候選 18 章節)、`log/s4-2026-08-31-021.md`。

**本次(chunk 20,2026-08-31)已完成:**
- ✅ **候選 19(上下文假設重測)完成,結論:「1a 全 fail」不是零上下文的人工產物** — 新增
  `tools/mesh_gen/s4_context_window.py`。同一顆隨機挖洞分別套進「孤立層裁切」與「以 PSD
  真實場景當背景、比照插件 512px 下限的大畫布視窗」,重跑既有三個 CPU baseline 配對比較。
  過程踩到兩層校準坑(`psd.composite()` 被後畫圖層污染目標層自身內容;改用
  `alpha_composite` 貼回又在半透明邊緣撞見「場景合成 alpha」≠「圖層自身 alpha」的假警報)
  ——改用硬覆蓋(不經 alpha 混合)後 6 案例校準全數逐位元通過。**核心結果**:`身體`/`左手`
  在 **interior 模式下 windowed 與孤立版三個 baseline 輸出逐位元相同(delta 恰好
  0.0000)**——`nearest`(最近有效值)與 `cv2.inpaint`(極小半徑 FMM)都是局部演算法,
  視野被演算法自身限制死,不是被裁圖裁掉的。edge 模式效果小且方向不一致(`nearest` 因
  誤用鄰近圖層像素反而變差,seam_grad_diff 43.6→107.6),無案例跨過 1a 門檻(ssim>0.75,
  windowed 最高僅 0.44,與孤立版相同)。**結論收窄候選 19 原假設**:512px 上下文對生成式
  模型(候選 17)才有意義,對現有 CPU baseline 無效;「生成式路徑能不能解 1a」仍只能由
  候選 17 回答。未改動任何 production 代碼(`inpaint_eval.py` 本身不變)。誠實限制:只測
  `robot_parts.psd` 的身體/左手兩材質,未擴大到 icon 類材質;`光暈` 回歸檢查是退化案例
  (bbox 已 ≥512px,pad_to=512 擴不出更大視窗)。見 `knowledge/s4-inpaint-context-window.md`、
  `log/s4-2026-08-31-020.md`。

**本次(chunk 19,2026-08-31)已完成:**
- ✅ **吸收使用者自製 Photoshop `GPT Fill` UXP 插件 v1.18.0 的切圖/補圖知識(使用者直接指定)** —
  使用者上傳 rar(容器讀不到本機 `C:\`,改用上傳;`libarchive-c` 解 RAR5),完整讀過 5 檔含
  `main.js` 1986 行。產出 `knowledge/s4-gptfill-plugin-knowledge.md`。**四個對 S4 有實質影響的
  收穫**:(1) **mask 慣例外部真值**:重建洞 dilate **8px** 融合邊界、移除物件 footprint dilate
  **24px** 給陰影重建、任務模式自動判定門檻「洞占比 ≥30%」、mask 編碼是 `alpha=255-selection`
  (透明=可編輯);(2) 🔥 **揭露我們一個沒意識到的方法論限制**:插件給生成模型的重建上下文下限
  **512px**,而我們的補圖閘從頭到尾只吃單層裁切、零上下文——「1a 機械紋理全 fail」這個核心結論
  是在「只看單層」條件下量的,列為候選 19(零成本純 CPU,有機會收窄既有結論,建議下一個做);
  (3) ⚠️ **生成結果不會像素對位**(會漂移+整體縮放),插件為此做了五層對位(平移 10px/縮放 ±5%/
  8 錨點 IDW 位移場/次像素拋物線/「改善不夠顯著就不套用」的接受門檻)——我們
  `psd_inplace_patch.py` 的「就地落在 mask 原位」假設一接生成路徑就破,這是候選 17 真正的工程
  主體;(4) ★ **獨立來源佐證 chunk 18 的發現**:插件 prompt 的 SHADOW REASONING 明確禁止
  「flat, uniformly-lit color」填補(理由:亮度與暗邊界不匹配就像貼上去的),與 chunk 18 用
  vision 發現的「奶油糊」失真維度完全同構 → 候選 16 的指標方向具體化為「邊界證據延續性」
  (候選 18)。另收穫:插件獨立收斂到 premultiplied 插值、用便宜幾何代理指標盲選多候選、
  自我輸出污染自我評估的防呆(`GPT •` 圖層守衛)——三者都與本 repo 既有做法同型,是外部佐證。
  新增候選 17/18/19,並標註候選 4「不建議投入生成式」的**前提已變**(不需容器內養 GPU)。
  本次未改動任何 production 代碼。見 `knowledge/s4-gptfill-plugin-knowledge.md`、
  `log/s4-2026-08-31-019.md`。

**本次(chunk 18,2026-08-31)已完成:**
7. ✅ **候選 7(1b 閾值反向校準,用 Claude vision 代理人工標註)調查完成,結論:不變更閾值,
   浮現新候選 16** — 新增 `tools/mesh_gen/s4_vision_proxy_compare.py`(裁切洞附近區域+疊
   棋盤格+放大拼成比較圖),對 6 個涵蓋四種材質類型的案例(光暈/身體/左手/左手3/鬢角1/鬢角2)
   用自己的 vision 讀圖判斷「像不像有破綻」,對照既有 1a/1b 數字判定。**負對照(none/random)、
   平滑漸層(光暈)、全平坦(左手3)三類 vision 與數字 100% 一致**;`鬢角1` 的 gt 用 vision
   確認確實無破綻,補上候選 8 `tone_gap` false-positive 結論的第一手視覺證據(之前只有數字
   論證)。**核心發現**:機械紋理(身體/左手,既有 1b pass)的 CPU baseline 補丁近距離看
   會丟失周圍鋸齒面板的高頻細節(呈放射狀模糊),但這不對應現有三指標(alpha_gap/seam_ratio/
   tone_gap)中任何一個門檻訂得不好——三者衡量的是「接縫突不突兀」,本來就沒有涵蓋「細節
   保留度」這個維度,調數字解不了。**誠實限制**:此代理是靜態、單層、人工放大的觀察條件,
   不是 1b 真正要問的「動態動畫、真實尺度」條件,弱於真人標註,不足以單獨動閾值。**決策**:
   不變更 `THRESH_1B`/`THRESH_1B_EDGE`;候選 7 就此收斂,提出候選 16(加第 4 個指標,或
   把補圖貼回真實 Award spine 場景跑動畫截圖比對)給後續獨立工作塊。見
   `knowledge/s4-inpaint-1b-lenient-gate.md`(候選 7 章節)、`log/s4-2026-08-31-018.md`。

**本次(chunk 17,2026-08-31)已完成:**
6. ✅ **候選 6(擴大樣本至 `Symbol_Ww.psd` icon 類其他 11 層)完成** — 用 `psd_slice.py`
   切出之前未測過的 11 層(`左手1/2/3`、`右手1/2`、`耳機1/2`、`鬢角1/2`、`音符1/2`),對每層
   跑 `inpaint_eval.py`(interior+edge)。**1a 邊界延續且擴及 icon 類材質**:僅真正平坦的
   `左手3` 通過,其餘細節材質(耳機弧線/手指關節/鬢角毛流)全 fail,再次證實決定因素是
   局部紋理複雜度、不限機械紋理。**1b 邊界多數延續**(8 層 CPU baseline 全 pass,驗證
   核心結論可攜到 icon 材質),但新揪出 2 筆 `tone_gap` 正對照 fail(`音符1/2`、`右手2`
   edge 壓線)——量化證實驅動因素是材質色調變化量級而非面積(`鬢角1`/`鬢角2` 面積幾乎相同
   卻一 fail 一 pass),屬候選 8 已知限制的再驗證,維持不調整全域門檻。另用更小尺度樣本
   (120~637px)再次確認小尺寸材質 edge 模式 1b 覆蓋率缺口(候選 9/2)依然成立。本次僅擴大
   測試樣本,未改動 production 代碼,無需回歸測試。見 `knowledge/s4-inpaint-tone-gap-limits.md`
   (候選 6 章節)、`log/s4-2026-08-31-017.md`。

**本次(chunk 16,2026-08-30)已完成:**
4. ✅ **候選 4(LaMa 可行性探測)完成,結論:網路政策不擋,但通用權重不足以解 1a,不建議投入** —
   新增 `tools/mesh_gen/s4_lama_probe.py`(一次性 probe)。網路面:PyPI `torch`/
   `simple-lama-inpainting`、GitHub release 的 `big-lama.pt`(196MB)皆可下載;
   `download.pytorch.org`/`huggingface.co` 被 proxy 擋(403)。裝置代價:唯一可行路徑
   (預設 PyPI `torch`)會多帶 ~2GB CUDA 依賴(非 CPU-only wheel)。跑分面:通用預訓練
   LaMa(未微調)對 `身體`/`左手`(已知 1a fail 機械紋理材質)interior+edge 共 8 個指標,
   6 個贏過全部 3 個 CPU baseline(如 `身體` ssim 0.441→0.574,`左手` premult_mae
   66.4→57.7),但**沒有任何一個案例跨過 1a 門檻**(ssim>0.75)。1b(實戰標準)兩者本來
   就已 pass,LaMa 換不到新增益。**誠實結論**:通用權重是穩定量化改善、非質變,真要解 1a
   大機率需微調(超出可行性探測範圍);當前優先序下不建議投入,`torch`/
   `simple-lama-inpainting` 不寫進 `requirements.txt`。見
   `knowledge/s4-lama-feasibility.md`、`log/s4-2026-08-30-016.md`。

**本次(chunk 15,2026-08-30)已完成:**
14. ✅ **候選 14 調查完成,結論:兩個獨立根因,4 種修法皆非零回歸** — 拆解候選 14:(1) 硬邊
    材質(`右手`)ring 內被材質內部 alpha 紋理雜訊污染(271 樣本中 180 個是離背景 8~15px 的
    雜訊、只有 55 個是離背景 1~1.4px 的真邊界像素),中位數被雜訊支配誤判成軟邊;(2) 光滑
    材質(`光暈`)ring 本身測到的斜率一致偏低(非雙峰,不是污染問題),是「單一常數 ell
    線性外推全洞」模型結構對非線性衰減材質失效。用全部 1233 筆量化資料測試 4 種修法(距背景
    固定半徑過濾——對寬漸縮材質災難性錯誤,未列入正式比較;只換統計量 percentile;只做
    方向濾波;兩者組合):最佳方案(方向濾波+p90)13 fixed、9 newly broken(`n_mae_gt_20`
    39→35,mean_mae 2.668→1.978)——**淨提升但非零回歸**,不符合本專案落地門檻,故本次
    未修改 `inpaint_eval.py` production 代碼。新增候選 15(A 類岔路):候選 D 的 trade-off
    是否可接受,需使用者裁決。見 `knowledge/s4-inpaint-alpha-taper-candidate14.md`、
    `log/s4-2026-08-30-015.md`。

**本次(chunk 9,2026-08-29)已完成:**
8. ✅ **1b `tone_gap` 在新材質上重新校準(調查完成,結論:無法簡單修正)** —
   先修正一個真實 bug:`punch_hole` interior 模式在材質太薄(如 `框`,環形鏤空)時原本會
   靜默偽造不合規範的洞(margin 退化 fallback),汙染了 session 008 對 `框` 的異常發現;
   已修正為縮小洞或明確報錯,`run_one`/`calibration_check` 對應處理 `skipped` case,批次
   評測不再因單一材質太薄就整批 crash。修正後 `框` 的 `tone_gap` 從 81.75 降到 32.84(仍壓線
   fail,但已排除偽造洞的干擾)。對真正的殘留案例(`臉部陰影`,合法 interior 洞但材質本身
   色調變化大)嘗試兩種 `tone_gap` 正規化(位置比對取樣基準/局部粗糙度基準),**兩者皆量化
   證明失敗**——`臉部陰影` 的 gt 與 `左手` 的 random 在正規化後的分布本身重疊,任何單一
   全域門檻都無法同時滿足兩者。**誠實結論**:`tone_gap` 目前僅在機器人拆件材質家族內可信,
   不是門檻沒調好,是這批新材質在此特徵維度上本來就跟 gt/random 不可分;跨材質家族需要
   各自重新校準,不強行塞一個看似合理但實際上會製造假信心的全域正規化。回歸驗證:原本
   3 個機器人件(光暈/身體/左手)校準與 `psd_inplace_patch.py` 端到端數字皆與 session 008
   一致,無回歸。見 `knowledge/s4-inpaint-tone-gap-limits.md`、`log/s4-2026-08-29-009.md`。

**本次(chunk,2026-08-28)已完成:**
5. ✅ **修正 `fill_cv2_inpaint` 的 edge 模式 alpha 處理** — 原本洞區強制設不透明,與柔和邊緣真值
   alpha 漸縮不符(`alpha_mae` 28~42)。實測兩個直覺解法(alpha 整顆跑 cv2.inpaint / alpha 單點
   最近鄰外推)都更差,改用「距離場×局部量測漸縮寬度」(`estimate_alpha_taper`)全面改善,無回歸。
   見下方「已完成」與 `knowledge/s4-inpaint-evaluator.md`。

**本次(chunk 10,2026-08-29)已完成:**
1. ✅ **遮擋真值法完成(里程碑,候選 1)** — 新增 `tools/mesh_gen/real_occlusion_eval.py`,用機器人
   拆件 5 個真實 PSD 圖層兩兩疊合的真實遮擋輪廓當洞(比合成挖洞的隨機圓更貼近實戰,gt = 圖層自己
   的原始像素)。重構 `inpaint_eval.py` 抽出共用核心 `run_with_mask()`,讓兩種洞來源共用完全同一套
   baseline/指標/門檻/校準邏輯(純函式抽取,對 `run_one()` 外部行為無影響,已回歸驗證)。**過程中
   揪出並修正一個真實 miscalibration**:1b `seam_ratio` 的 `baseline_grad` 原本用整件全域平均,
   對局部漸層不均勻的材質(光暈:核心陡、外圈平緩)會被稀釋失真——`光暈←右手` 真實案例(遮擋範圍
   跨過光暈核心)讓正對照(gt)本身誤判 1b fail;改成洞周圍固定 12px 寬的局部環狀帶當基準後,
   4 組真實遮擋案例校準全過,6 個既有材質×模式(機器人 3 材質 interior/edge + Symbol_Ww 框/臉部
   陰影)回歸測試零反向、`psd_inplace_patch.py` 端到端數字不變。**核心結果**:機械紋理(身體←左手)
   真實遮擋判定與合成挖洞閘完全一致(1a fail/1b pass);光滑漸層材質(光暈)在真實不規則/大面積
   遮擋形狀下,1a 的 `seam_grad_diff` 會超標(合成小圓洞從未量到),雖然 1b 仍全數 pass——確認
   候選 0「光暈 CPU 補得動」的結論隱含「小面積圓形洞」前提,呼應候選 8 的分類法(1a 嚴格/1b 實戰)。
   見 `knowledge/s4-inpaint-real-occlusion.md`、`log/s4-2026-08-29-010.md`。

**本次(chunk 11,2026-08-29)已完成:**
9. ✅ **候選 1 延伸:遮擋真值法擴大配對樣本至 8 組** — `real_occlusion_eval.py` PAIRS 從 4 組
   擴到 8 組,新增小面積/懸殊比例配對(右手←頭 6.5%、身體←頭 1.0%[本檔最小絕對洞尺寸
   829px]、頭←右手 46.5%[本檔最大比例]、頭←身體 12.9%),排除「X←光暈」全覆蓋退化案例
   (frac=1.0,整層清空屬 taxonomy 情境 2,非局部遮洞問題)。`calibration.pass` 維持 `True`。
   **機械紋理結論可攜到新材質 `右手`**(interior:1a 三 baseline 全 fail、1b 全 pass),且
   在本檔測過最小絕對洞尺寸(829px)依然成立,校準沒因樣本縮小而失真。**核心發現**:小尺寸
   圖層(`頭`,內容僅 6405px,5 層最小)的兩個測試配對都被 `classify_mode()` 判成 `edge`——
   小圖層的真實遮擋洞天生更容易碰到自己的內容邊界。**這代表 1b 目前對這類小尺寸素材完全
   沒有可用的驗收線**(只能退回 1a 嚴格標準,而 1a 對機械紋理材質全 fail),是用真實樣本
   量出來的評估器覆蓋率缺口,不是理論假設——候選 2(1b edge 模式支援)的優先度應上修。
   回歸驗證:原 4 組案例的 gt/none/random pass-fail 與 session 010 逐項一致。見
   `knowledge/s4-inpaint-real-occlusion.md`(新增章節)、`log/s4-2026-08-29-011.md`。

**本次(chunk 12,2026-08-29)已完成:**
2. ✅ **1b 的 edge 模式支援(里程碑,候選 2,候選 9 驗證後優先度上修)** —
   `score_1b()` 新增 `mode="edge"`。第一版依原始構想(比對真實輪廓其他段落的天然變化當
   基準)量化後證實鑑別力不足(premultiplied 在背景側恆 0,亂補與正確填補的落差量級糾纏
   不清,任何門檻都分不開);改採「排除貼真實輪廓的邊界段落,只評內容內部轉接」,直接
   複用 interior 既有的 `local_ring` baseline(單位一致,新增 `THRESH_1B_EDGE`,`tone_gap`
   收緊到 23.0)。**核心結果**:機器人拆件家族(光暈/身體/左手)edge 模式 1b 校準通過,
   與 interior 模式結論同型;**候選 9 揭露的關鍵缺口案例 `頭←右手`(小尺寸圖層,edge)
   現在有真正判定**——`applicable=True`,3 個 CPU baseline 全 pass,之前「沒有任何量化閘
   能判定動態下是否穿幫」的小尺寸機械材質補圖,現在有驗收線了。過程中踩到一個真實 bug:
   `content` 在校準流程與真實落地流程語意不同(是否含洞區域),導致
   `patch_layer_auto`/`demo_auto_patch` 端到端測試 `applicable` 恆 `False`——改用
   `content|mask` 統一語意後修正,`--auto --mode edge` 端到端驗證恢復正常
   (`chosen_reason` 從 fallback 變成真正的 `pass_1b`)。Symbol_Ww `框`/`臉部陰影` 的
   已知 tone_gap 限制(候選 8)在 edge 模式下延續(非新問題,`框` interior 模式下本來就
   已 fail calibration)。回歸驗證:interior 模式逐位元不變(機器人 3 材質 + Symbol_Ww
   2 材質數值與 session 008/009 完全一致);`real_occlusion_eval.py` 既有 5 組 interior
   案例數值與 session 010/011 一致;`psd_inplace_patch.py --auto --mode interior`
   `chosen_method` 不變。見 `knowledge/s4-inpaint-1b-edge-gate.md`、
   `log/s4-2026-08-29-012.md`。

**本次(chunk 25,2026-09-01)已完成:**
- ✅ **候選 16 路徑 (b) 第三個案例:機器人拆件/光暈(第三種材質類型,平滑漸層)** —
  沿用 chunk 23/24 的通用工具重跑(`--slot "機器人拆件/光暈"`),不改 production 代碼。
  **核心結果**:(1) 零外洩驗證通過(全 11 個時間點差異像素皆落在目標 slot 螢幕框內);
  (2) **量級遠低於前兩個機械紋理案例**——`mae_0_255` 穩定在 0.01~0.04(`左手`/`身體`是
  0.9~1.05,低約兩個數量級),每幀差異像素僅 52~83px;(3) 實際螢幕佔比 3.4~7.3%,是三案例
  中最大的(`左手` 0.5~0.6%、`身體` 1.0~1.1%),但人眼 8x 放大複查仍**完全看不出差異**——
  排除「佔比小才不明顯」的替代解釋,支持「材質紋理複雜度才是補圖難度決定因素」的既有結論
  (候選0/8/10)。三種材質類型(機械紋理×2+平滑漸層×1)覆蓋完成,候選16路徑(b)可視為
  已達成初始目標。見 `knowledge/s4-inpaint-spine-render-compare.md`(新增「第三個案例」
  章節)、`log/s4-2026-09-01-025.md`。

**本次(chunk 24,2026-09-01)已完成:**
- ✅ **候選 16 路徑 (b) 第二個案例:機器人拆件/身體(驗證 rotate=true 路徑)** —
  沿用 chunk 23 的通用工具 `s4_award_screenshot_compare.py`(不改 production 代碼,只換
  `--slot`/`--att-name` 參數),對 `身體`(`rotate=true`,`左手` 是 `rotate=false`)跑同一套
  流程。**核心結果**:(1) 全 900×900 場景像素比對 orig vs patched,11 個時間點差異像素
  全部落在目標 slot 螢幕框內、0 外洩——首次在真實 spine-webgl 渲染管線下驗證
  `atlas_patch.py` 的旋轉還原正確(之前只有 `--selftest` 靜態自測覆蓋);(2) 該材質實際
  螢幕佔比 ~1.0~1.1%(約 `左手` 的兩倍),人眼複查(實際渲染尺寸,未放大)orig/patched
  仍幾乎無法分辨,「不構成一眼可見穿幫」的結論可攜到第二個材質,且尚未在更大佔比下翻盤。
  1b 盲選同樣選中 `nearest`(`pass_1b`)。見 `knowledge/s4-inpaint-spine-render-compare.md`
  (新增「第二個案例」章節)、`log/s4-2026-09-01-024.md`。

## 未解問題 / 阻塞 (open questions / blockers)

- ✅ LaMa 等深度 inpaint 權重下載是否被網路政策擋?(候選 4,已解:部分允許但代價高,通用權重
  不足以解 1a,不建議投入,見 `knowledge/s4-lama-feasibility.md`)
  ⚠️ **前提已變(chunk 19)**:候選 4 的「不建議投入」是以「本容器要自建 GPU/LaMa」為前提。
  使用者端已有在跑的 API 生成路徑(`gpt-image-2`,見 `knowledge/s4-gptfill-plugin-knowledge.md`),
  不需要在容器裡養 GPU。既有量化數字仍有效,但**結論的適用前提要連著這條一起讀**;
  「生成式路徑能不能解 1a」改由候選 17 回答(尚未跑,不可先當結論)。
- ❓ 補圖真值來源:目前用「合成挖洞」自造(已完成校準);「遮擋真值法」(候選 1)待驗證是否與合成挖洞判定一致。
- ✅ 1b 閾值反向校準是否可行?(候選 7,已解:用 vision 代理調查過,現有三指標框架解不了
  「高頻細節丟失」這個新發現的維度,不是門檻問題,見 `knowledge/s4-inpaint-1b-lenient-gate.md`)
- ✅ **候選 16(chunk 18 提出,chunk 21/22/23/24/25 更新,路徑 (b) 已完成)**:路徑 (a)「1b
  加第 4 個指標」的兩次具體嘗試都已實作校準並排除——「邊界證據延續性」(候選 18,結構性
  偏向獎勵平滑)、「局部高頻能量/方差比」(候選 20,正對照本身因材質不均勻失真 + 無法
  分辨真實紋理/拼貼假邊/純雜訊)。路徑 (a) 這個大方向若要再嘗試,需要換成能分辨
  「結構/樣式」而非只看「量級」的統計量,已逼近與 1a `ssim` 職責重疊,價值存疑。**路徑
  (b) 已完成三個真實案例(chunk 23 `左手`、chunk 24 `身體`、chunk 25 `光暈`)**:貼回真實
  Award spine 場景截圖比對。機械紋理兩案例(`左手`/`身體`)結論一致——「瑕疵仍在但實際
  渲染尺度下不構成一眼可見穿幫」,`身體` 額外驗證了 `atlas_patch.py` 旋轉還原
  (`rotate=true`)在真實渲染管線下正確。平滑漸層案例(`光暈`)結論更乾淨——差異量級比
  機械紋理案例低約兩個數量級,即使實際佔比是三者最大(3.4~7.3%)人眼放大複查仍看不出
  差異,排除「佔比小才不明顯」的替代解釋。**三種材質類型已覆蓋,候選16路徑(b)可視為已
  達成初始目標**(回答「動態動畫尺度下會不會穿幫」)。剩餘延伸(取得真實遊戲顯示縮放比例
  驗證佔比門檻)需要外部資源,屬非阻塞性 A 類岔路。見 `knowledge/s4-inpaint-spine-render-compare.md`。
- ✅ **候選 15(2026-08-30 提出,2026-09-04 chunk 33 裁決:無限期擱置)**:`estimate_alpha_taper`
  候選 14 的最佳修法(方向濾波+p90)是「13 例大幅改善換 9 例壓線新增 fail」的 trade-off,
  不符合零回歸門檻。chunk 33 確認此 trade-off 用的 `alpha_mae>20` 只是診斷尺,不是
  `passes()`/`passes_1b()` 實際生產判定門檻,兩個代表材質在真實 1b 門檻下本來就已 PASS,
  接不接受都不影響任何真實上線判定——使用者裁決無限期擱置(非永久否決,保留未來重新評估
  彈性)。詳見 `knowledge/s4-inpaint-alpha-taper-candidate14.md`、`log/s4-2026-09-04-033.md`。
- ✅ **里程碑審查完成(chunk 26,2026-09-02)**:S4 核心研究問題已全部有交叉驗證的答案
  (見上方「里程碑審查」段落與 `knowledge/s4-convergence-review.md`)。候選15/17 是唯二
  剩餘的執行層決策(非研究缺口),連同「本排程接下來走向」共三項一併彙整交還使用者裁決,
  屬非阻塞性——本排程建議轉維護模式而非標 `BLOCKED`/`DONE`。

## 進度摘要 (progress log)

- 2026-09-04:**外部知識吸收:GenieLabs `spine-animation-ai`,優化 skill(chunk 38)** —
  使用者分享 `https://github.com/GenielabsOpenSource/spine-animation-ai`(一個已發布的
  開源 Claude skill,骨架綁定協駕員),要求評估能否優化 `spine-asset-request`。用
  `WebFetch` 讀 README/SKILL.md/`split_character.py`/LICENSE(未 clone 進 repo)。
  **⚠️ 授權 PolyForm Noncommercial 明確禁止商業使用**(本專案 lula slot game 屬商業),
  故只做知識萃取,不複製任何程式碼,並在知識檔與 skill 更新處都標註此限制。**萃取兩個未
  驗證候選**:(1) `split_character.py` 思路——不對原圖語意分割,改請生成式模型把角色
  重繪成「部件已分離、留白、白底」乾淨版面,再用簡單 OpenCV connected-components 分割,
  直接回應本專案「平圖自動拆件 CPU 到頂」的既有死結,原理上可換候選17已打通的 gpt-image-2
  嘗試;(2) `position_parts.py` 思路——SIFT+RANSAC 特徵匹配自動擺位+遮擋投票定 z-order,
  對 S5(骨架半自動)是互補候選,含具體調校參數起始值。更新
  `.claude/skills/spine-asset-request/SKILL.md`:「平圖拆件」與新增「自動擺位/z-order」
  兩條都標註為「未驗證候選,需要獨立重新實作+驗證,不可抄程式碼」,不誇大成已可用能力。
  順帶記錄該外部專案鎖定 Spine 4.2、與本專案 3.8 JSON 語法不通用(只有概念層可轉移)。
  本次未新增任何量化實驗、未改動 production 代碼。見
  `knowledge/s4-genielabs-spine-ai-knowledge.md`、`log/s4-2026-09-04-038.md`。
- 2026-09-04:**⚠️ chunk 36/37 撞號說明(合併 push 時發現)** — 兩個並行 session 從同一份
  chunk 35 狀態各自獨立推進 viewer,`git push` 才發現撞號。時間較早、使用者直接指示的
  commit 保留編號 chunk 36(`s4_ai_viewer.html` + skill);時間較晚、排程自動觸發、獨立
  不知情做了同名工作的 commit 重新編號為 chunk 37(`psd_viewer.html`)。兩者是不同架構
  選擇,不是重複——但 chunk 36 功能更完整,視為 viewer 主線。詳見
  `knowledge/s4-viewer-plan.md`「與並行 session 的工作塊撞號」章節、
  `log/s4-2026-09-04-036.md`(主線)、`log/s4-2026-09-04-037.md`(次要能力)。
- 2026-09-04:**viewer 路線圖 + V1(PSD 純瀏覽器端解析)完成(chunk 37,次要能力,見上方
  撞號說明)** — 發現本次排程 session 無 `OPENAI_API_KEY`,候選17結構性無法繼續,轉向
  chunk 34 裁決但未拆解的 viewer 方向。拆解為 V1~V5,完成 V1:新增
  `tools/mesh_gen/psd_viewer.html`(ag-psd 直接在瀏覽器端解析原始 .psd,圖層樹+composite+
  逐圖層 metadata,`window.psdViewerTool` Phase-2 API)。Playwright headless(page.route
  攔截 CDN 請求到本機 `npm pack` vendor 副本,僅測試用,production 仍走真 CDN)對
  `robot_parts.psd`(5層)/`Symbol_Ww.psd`(18層)交叉比對 Python `psd-tools` 地面真值:
  圖層名稱/順序/bbox 100% 相符。踩到一個跟 `CLAUDE.md` PMA 雷點同構的校準坑(raw RGBA
  比對被透明像素的無意義 RGB 值污染出假差異),改用 premultiplied 比對後 mean diff 僅
  0.03~0.04/255。誠實限制:V1 僅檢視,無互動顯示/隱藏重繪;未測巢狀 group 素材;生產
  CDN 可達性需使用者自己驗證;且既然 chunk 36 的 `s4_ai_viewer.html` 已是功能更完整的
  主線,本檔的 V2~V5 不建議在未經使用者要求前繼續投入。同時記錄候選17若要在自動化排程
  下持續推進,需使用者設定持久化 `OPENAI_API_KEY` environment secret。見
  `knowledge/s4-viewer-plan.md`、`log/s4-2026-09-04-037.md`。
- 2026-09-04:**viewer + skill 初步版完成(chunk 36,viewer 主線)** — 使用者要求推進 viewer(PSD檢視/編輯
  +與ChatGPT即時溝通,類Photoshop插件HTML版)與 skill(需求驅動切圖補圖)兩項。**關鍵前提
  驗證**:`curl -X OPTIONS https://api.openai.com/v1/images/edits` 帶 CORS preflight header,
  回傳 `access-control-allow-origin: *`——確認瀏覽器可以直接跨來源呼叫 OpenAI API,viewer
  不需要中介後端,「純前端 Photoshop 插件替代品」這個架構成立。新增
  `tools/mesh_gen/s4_ai_viewer.html`:載入圖層(manifest.json+PNG 或單張 PNG)→畫遮罩
  (canvas 筆刷)→prompt→直接 `fetch()` 呼叫 API→結果三欄比對→套用/下載;key 只存瀏覽器
  localStorage;每次呼叫記錄用量(可選 File System Access API 直接寫入
  `tools/mesh_gen/s4_data/openai_usage.jsonl`,跟儀表板共用)。用 Playwright 
  headless Chromium 驗證前端邏輯(檔案載入/遮罩繪製/驗證擋錯/mock API 呼叫/套用/manifest
  載入共6項),**mock 掉真實 API 呼叫,未花費真實金錢驗證**。踩到並確認一個已知環境限定
  caveat(非工具 bug):Playwright `setInputFiles` 對中文檔名的限制,跟 `psd_preview.html`
  先前記錄的是同一個問題。同時建立 `.claude/skills/spine-asset-request/SKILL.md`(初步版,
  ⚠️ 位於 `.claude/skills/`,非本排程「檔案隔離契約」列出的 S4 專屬路徑,但屬使用者當面
  直接要求的新增內容,不觸碰主排程任何既有檔案,判斷不違反契約精神):把「使用者描述動畫
  需求→依 taxonomy 判斷缺口類型(A切圖/B補圖-CPU優先/C補圖-生成式/D視角外推無解)→驅動對應
  S4 工具→真實場景驗證→記錄」串成一套可重複流程,含工具速查表與「誠實回報無法自動處理的
  情況」清單。見 `knowledge/s4-ai-viewer-tool.md`、`log/s4-2026-09-04-036.md`。
- 2026-09-04:**候選17網路阻塞解除 + 第一次真實驗證,發現 1a 評分方法論可能不適合生成式
  輸出(chunk 35)** — 使用者放行 `api.openai.com`。驗證步驟:(1) 不帶 key 測 models 端點
  拿到 401(非連線層級 403,確認網路已通);(2) 帶 key 測拿到 200,確認 `gpt-image-2` 在
  帳號模型清單裡。新增 `tools/mesh_gen/s4_openai_client.py`(獨立於 Photoshop 的 REST
  呼叫模組,mask 用官方慣例編碼,key 只讀環境變數,每次呼叫記錄含真實 usage token 數的
  metadata,不含 key/圖片)+ `tools/mesh_gen/s4_usage_dashboard.html`(純前端用量儀表板,
  比照 `psd_preview.html` 架構;`platform.openai.com` 未放行查不到 $ 定價,先呈現 token
  數)。對已知 1a 全 fail 的 `機器人拆件/左手` 跑第一次真實測試(`punch_hole` 同組參數,
  `quality=low`)。**核心結果**:API 呼叫成功,1a 依然 fail(ssim 0.274,同量級 LaMa),
  但 1b 大幅 pass 且是本專案至今最佳(tone_gap 5.04)。**關鍵發現**:三圖並排 4x 放大比對,
  補丁視覺上完全看不出破綻(材質風格/反光/明暗一致,還合理加了螺絲細節),跟 CPU baseline
  的「奶油糊」完全不同等級——但 ssim/premult_mae 判 fail 是因為生成了幾何形狀不同的
  合理替代方案,不是重建同一組像素。**這代表逐像素比對 gt 的 1a 評分方法論可能從一開始
  就不適合評估生成式輸出**,不是「gpt-image-2 也不行」的結論。n=1,未做正負對照校準,
  建議下一步先定生成式方法的正確評分方式(1b 或 vision-proxy)再擴大樣本。順帶更正
  `s4-gptfill-plugin-knowledge.md` 的 provenance 誤記(該插件是開源專案,非使用者自製,
  使用者當面更正)。見 `knowledge/s4-inpaint-candidate17-gptimage2.md`、
  `log/s4-2026-09-04-035.md`。
- 2026-09-04:**使用者對談中三項裁決 + 關鍵網路阻塞發現(chunk 34)** — 使用者一次裁決:
  (1) 候選17授權(提供 API key,無費用上限,需用量可視化監控);(2) 本排程走向:精煉一個
  依 spine 動畫需求驅動切圖/補圖的 skill;(3) 新增 viewer 需求(PSD 檢視/編輯+與 ChatGPT
  即時溝通,類 Photoshop 插件 HTML 版)。**安全性處理**:API key 使用者直接貼在對話裡(非
  安全管道),本次僅在暫存 shell 變數測試後即清除,未寫入任何 git 追蹤檔案/未 commit/無
  殘留檔案;建議使用者之後旋轉該 key 並改用環境變數/secrets 機制。**關鍵發現**:用該 key
  測試 `GET https://api.openai.com/v1/models`(零成本),被此容器的 proxy 以 403 policy
  denial 拒絕(`recentRelayFailures` 確認是網路政策層級拒絕,非 key 本身問題)——候選17
  原設計「排程容器內 headless 呼叫 gpt-image-2」路線目前技術上走不通,需使用者確認能否
  調整 environment 網路政策放行 `api.openai.com`。**不受影響**:viewer(第3項)是純瀏覽器
  端工具(比照現有 `spine_inspector.html`/`psd_preview.html`),不經過此容器,可獨立先推進。
  本次**未接任何 production 代碼**(連線不通,接了也無法驗證,會產生死代碼),僅記錄三項
  裁決與網路阻塞發現,待使用者回覆網路政策後拆解成有界工作塊繼續推進。見
  `log/s4-2026-09-04-034.md`。
- 2026-09-04:**候選15 使用者裁決:無限期擱置(chunk 33,使用者對談中直接裁決)** — 使用者
  先問「用 gpt-image-2 是否讓候選15的追求變得沒必要」,本次對談用 `s4_alpha_taper_candidate14.py`
  既有函式(`estimate_alpha_taper`/`estimate_combined`)重新跑出候選15的真實視覺範例(`右手`
  edge fixed 案例 alpha_mae 115.6→2.6、`光暈` edge newly-broken 案例 13.3→23.3),送圖給
  使用者後,回頭確認一個關鍵事實澄清了決策:**候選15用的 `alpha_mae>20` 是研究者自訂的診斷
  尺,不是 `passes()`/`passes_1b()` 實際採用的生產判定門檻**(1a 判定用 `premult_mae`/
  `ssim`/`seam_grad_diff`;1b 判定用 `alpha_gap`/`seam_ratio`/`tone_gap`)——兩個材質在真正
  的 1b 生產門檻下本來就已 PASS,候選15不管接不接受都不改變任何真實上線判定,純粹是补丁
  邊緣視覺精度的錦上添花。使用者裁決:**無限期擱置**(不同於「不採用」的永久否決,保留未來
  若情境改變可重新評估的彈性,但目前不排入任何排程工作)。**剩餘待裁決點收斂為兩項**:候選17
  (API 授權)、本排程走向。未修改 `inpaint_eval.py` production 代碼(候選15的 `min_ring=20`/
  `median` 現行實作維持不變,`estimate_combined` 等候選函式留在
  `tools/mesh_gen/s4_alpha_taper_candidate14.py` 供未來若重新評估時使用)。見
  `log/s4-2026-09-04-033.md`。
- 2026-09-04:**排程第 7 次觸發,仍無新裁決,極簡檢查後維持 `BLOCKED`,不重複通知
  (chunk 32)** — 依 chunk 27–31 建立的極簡檢查慣例:HEAD 仍是 chunk 31 commit,
  `claude/spine-s4-inpainting` 分支無任何 PR(`list_pull_requests` 空陣列),
  `ReadNotifications` queue 為空,三項決策點狀態不變。chunk 29 已通知過一次,情況未變,
  本次不再重複發送。未新增量化實驗、未改動 production 代碼。見 `log/s4-2026-09-04-032.md`。
- 2026-09-03:**排程第 6 次觸發,仍無新裁決,極簡檢查後維持 `BLOCKED`,不重複通知
  (chunk 31)** — 依 chunk 30 定下的極簡檢查慣例:HEAD 仍是 chunk 30 commit,`STATE_S4.md`
  歷史全部由 Claude 提交(無使用者直接編輯痕跡),`claude/spine-s4-inpainting` 目前無任何
  PR(無 PR comment 裁決管道),`ReadNotifications` queue 為空。三項決策點狀態不變。chunk 29
  已通知過一次,情況未變,依「不重複通知」慣例本次不再發送。未新增量化實驗、未改動
  production 代碼。見 `log/s4-2026-09-03-031.md`。
- 2026-09-03:**排程第 5 次觸發,仍無新裁決,極簡檢查後維持 `BLOCKED`,不重複通知
  (chunk 30)** — 依 chunk 28/29 建立的極簡檢查慣例:HEAD 仍是 chunk 29 commit,三項決策點
  狀態不變。remote 出現大量其他排程 session 分支,非使用者裁決管道,逐一核對無意義。
  chunk 29 已通知過一次,情況未變,依「通知該省則省」原則本次不再重複發送。未新增量化
  實驗、未改動 production 代碼。見 `log/s4-2026-09-03-030.md`。
- 2026-09-03:**排程第 4 次觸發,仍無新裁決,極簡檢查後維持 `BLOCKED`,主動通知使用者
  (chunk 29)** — 依 chunk 28 補充的停止條件,執行極簡檢查(不重跑盤點):HEAD 仍是
  chunk 28 commit,三項決策點狀態不變。**發現**:chunk 27/28 交叉檢查所用的「主排程
  分支」名稱在 remote 已不存在(該分支名每個 session 會輪替,非固定),這個交叉檢查
  管道已失效,之後不應再依賴比對特定主排程分支名。**本次執行主動通知使用者**(chunk 28
  已判斷值得通知但未實際發出)。未新增量化實驗、未改動 production 代碼。見
  `log/s4-2026-09-03-029.md`。
- 2026-09-03:**排程再次觸發,仍無新裁決,維持 `BLOCKED`(chunk 28)** — 檢查本分支
  commit history 與主排程分支 `STATE.md`,皆無使用者對三項決策點(候選15/候選17/排程
  走向)裁決的痕跡。這是連續第 3 次(chunk 26/27/28)排程觸發卡在同一組決策點,已超過
  `RULES.md`「連續 2 次無進展」門檻,判斷值得主動通知使用者而非持續靜默等待。以極簡
  檢查取代重跑盤點,未新增量化實驗、未改動 production 代碼,`STATE_S4.md` 頂部停止條件
  說明補充「下次觸發若仍無裁決痕跡,應更快確認並停,不需再深入」。見
  `log/s4-2026-09-03-028.md`。
- 2026-09-02:**排程觸發確認,標記 `BLOCKED`(chunk 27)** — 排程自動觸發,讀
  `STATE_S4.md` 發現 chunk 26(同日稍早)已完成里程碑審查並明確寫「下一步:等待使用者
  裁決」。檢查無任何使用者裁決痕跡,三項決策點(候選15/候選17/排程走向)與 chunk 26
  結束時狀態相同。依 `RULES.md` 停止條件(需要人類決策 + 連續 2 次無實質新進展),不
  重跑同一輪盤點,改為把專案狀態由 `ACTIVE` 明改 `BLOCKED`,避免下次排程觸發再空轉燒
  token 產生重複內容。未新增量化實驗、未改動任何 production 代碼。見
  `log/s4-2026-09-02-027.md`。
- 2026-09-02:**里程碑審查完成(chunk 26),結論:S4 核心研究問題已閉環** — 依 chunk 25
  「下一步」指定(候選15/17 需人裁決,本次排程無活人在場,執行選項(b))。逐項清點原始
  使命七個問題(切圖可靠性/補圖評估器/CPU補圖能力邊界/1a-1b邊界實戰意義/LaMa投資值不值得
  /分類法有效性/類別2歸屬),確認全部有交叉驗證答案。剩餘候選15/17 是執行層決策非研究
  缺口。建議:S4 維持 `ACTIVE` 但降低排程優先度,資源轉向 S1/S2/S3/S5;不建議標 `DONE`。
  三項決策點(候選15/候選17/本排程走向)彙整交還使用者。順帶補上 chunk 24/25 遺漏的
  `knowledge/README.md` 索引 append(檔案隔離契約範圍內的小修正)。未新增量化實驗、未
  改動任何 production 代碼。見 `knowledge/s4-convergence-review.md`、
  `log/s4-2026-09-02-026.md`。
- 2026-09-01:**候選 16 路徑 (b) 第三個案例完成(`光暈`,平滑漸層,第三種材質類型,
  chunk 25)** — 沿用 chunk 23/24 通用工具重跑,不改 production 代碼。核心結果:(1) 零
  外洩驗證通過;(2) 差異量級(`mae_0_255` 0.01~0.04)比前兩個機械紋理案例(0.9~1.05)
  低約兩個數量級;(3) 實際螢幕佔比(3.4~7.3%)是三案例中最大,但人眼 8x 放大複查仍完全
  看不出差異——排除「佔比小才不明顯」的替代解釋,支持「材質紋理複雜度才是決定因素」的
  既有結論(候選0/8/10)。三種材質類型(機械紋理×2+平滑漸層×1)覆蓋完成,候選16路徑(b)
  達成初始目標。見 `knowledge/s4-inpaint-spine-render-compare.md`、`log/s4-2026-09-01-025.md`。
- 2026-09-01:**候選 16 路徑 (b) 第二個案例完成(`身體`,驗證 rotate=true 路徑,chunk 24)** —
  沿用 chunk 23 的通用工具重跑,不改 production 代碼。核心結果:(1) 首次在真實
  spine-webgl 渲染管線驗證 `atlas_patch.py` 旋轉還原正確(全 11 個時間點差異像素零外洩到
  目標 slot 螢幕框外);(2)「高頻細節丟失但不構成一眼可見穿幫」的結論可攜到第二個材質,
  即使其實際佔比(~1.0~1.1%)是 `左手`(~0.5~0.6%)的近兩倍。見
  `knowledge/s4-inpaint-spine-render-compare.md`、`log/s4-2026-09-01-024.md`。
- 2026-09-01:**候選 16 路徑 (b)(補圖貼回真實 Award spine 場景,headless 動畫截圖比對)
  第一個真實案例完成(chunk 23)** — 新增 `tools/mesh_gen/atlas_patch.py`(`atlas_crop.py`
  逆操作,round-trip 自我驗證 5 region 全 `max_diff=0`)、`tools/mesh_gen/
  s4_spine_render_harness.html`(新的 headless 渲染 harness,多頁 atlas 正確支援——
  `spine_inspector.html` 的 `TextureAtlas` textureLoader 固定回傳同一張貼圖,對雙頁 atlas
  的 Award 會讓其中一頁全部貼錯圖,故不可共用,只新增不改動)、`tools/mesh_gen/
  s4_award_screenshot_compare.py`(orchestrator)。跑通 `機器人拆件/左手`(1a fail/1b pass
  代表材質):atlas 解析度挖洞(interior,frac=0.12)→ 1b 盲選補丁(`nearest` 勝出)→ 貼回
  `Award.png` 副本 → `Award_Legend_In`/`Award_Legend_Loop` 11 個時間點截圖比對。**過程踩到
  一個坑**:相機不能只用 setup pose 框(`Award_Legend_In` 爆衝動畫中途會把材質甩出偏移的
  視野),改成先跑 `orig` 場景取全部取樣時間點姿態包圍盒聯集再固定相機,orig/patched 才能
  公平比較。**核心結果**:(1) 全 900×900 場景像素比對,差異只有 205px 且精確落在目標
  slot 範圍內(其他 40+ slots 零差異)——證明雙頁貼圖路由正確;(2) 該材質在此相機框架下
  只佔全場景 ~0.5~0.6% 面積(~70×60px);(3) 兩個獨立時間點 10x 放大人眼複查:候選7已知
  的「高頻細節丟失/奶油糊」瑕疵仍在,但不構成一眼可見的接縫/破洞/色差,要刻意放大才看得
  出摺痕反光細節被抹平一點。**誠實限制**:單一材質/單一 seed/單一盲選方法;相機框架是
  方法論近似,未對照真實遊戲實機顯示縮放比例,若實機把特效放更大則「不明顯」的結論可能
  不成立;人眼複查仍是 Claude vision 自評非真人標註。未改動 `spine_inspector.html`/
  `inpaint_eval.py` 等既有 production 代碼。見 `knowledge/s4-inpaint-spine-render-compare.md`、
  `log/s4-2026-09-01-023.md`。
- 2026-09-01:**候選 20(1b「局部高頻能量/方差比」第 4 指標,候選 16 路徑 (a) 第二次嘗試)
  實作與校準完成,結論:兩個獨立失效模式,不採用(chunk 22)** — 新增
  `tools/mesh_gen/s4_energy_ratio.py`(`energy_ratio` = 洞內 core 局部方差 / 既有
  `score_1b` `local_ring` 基準的局部方差,只測 interior)。撞到兩個獨立根因:(1) 光暈
  正對照本身失真(gt `energy_ratio`=0.0036 比全部 baseline 都低,呼應候選 10 的材質局部
  統計不均勻性,同候選 8/18 那類根因);(2) 左手負對照鑑別力崩潰——跨 4 個 seed 重跑確認,
  `random`(0.83~1.67)與 `gt`(0.92~1.37)同量級分不開,且排序方向與既有 vision/1a ssim
  證據矛盾(已知拼貼假邊的 `nearest` 反而比公認較好的 `cv2_telea`/`cv2_ns` 更貼近 gt)。
  根因:局部方差只量「跳動量級」不量「樣式對不對」,逼近 1a `ssim` 職責重疊。不採用,未動
  `score_1b`/`THRESH_1B`。候選 16 路徑 (a) 兩次具體嘗試(候選 18/20)皆已排除,路徑 (b)
  (貼回真實 Award spine 場景跑動畫截圖比對)是唯一未嘗試路徑,建議後續優先做。見
  `knowledge/s4-inpaint-1b-lenient-gate.md`(候選 20 章節)、`log/s4-2026-09-01-022.md`。
- 2026-08-31:**候選 18(1b「邊界證據延續性」第 4 指標)實作與校準完成,結論:設計方向
  結構性偏差,不採用(chunk 21)** — 新增 `tools/mesh_gen/s4_boundary_evidence.py`,把
  GPT Fill 插件 SHADOW REASONING prompt(chunk 19)具體化成 `grad_continuity_gap`(洞外
  邊界局部梯度線性外推 MAE)。校準發現機械紋理材質(身體/左手)的**正對照(gt)分數反而比
  `nearest` 平坦複製差**(身體 24.8>14.9、左手 90.6>56.2),`probe_depth` 6px→2px 偏差
  依然成立。根因:預測基準本身是「平滑外推」,真實紋理天然不服從、但平坦補丁天生貼近自己
  的平滑預測——偏誤方向跟「抓奶油糊」的設計意圖相反,換算比值也救不回來。不是門檻問題,
  是構造自我矛盾。不採用,未改動 `inpaint_eval.py`/`THRESH_1B`。候選 16 若再推進建議改走
  「局部高頻能量/方差比」方向。見 `knowledge/s4-inpaint-1b-lenient-gate.md`(候選 18
  章節)、`log/s4-2026-08-31-021.md`。
- 2026-08-31:**候選 19(上下文假設重測)完成,結論:「1a 全 fail」不是零上下文的人工
  產物(chunk 20)** — 新增 `tools/mesh_gen/s4_context_window.py`,同一顆挖洞分別套進
  「孤立層裁切」與「PSD 真實場景當背景、比照插件 512px 下限的大畫布視窗」,配對比較既有
  三個 CPU baseline。踩到兩層校準坑(composite 被後畫圖層污染 / alpha_composite 邊緣像素
  的「場景 alpha」≠「圖層自身 alpha」假警報),改硬覆蓋後 6 案例校準逐位元通過。核心結果:
  `身體`/`左手` interior 模式下 windowed 與孤立版三個 baseline **輸出逐位元相同**
  (nearest/cv2.inpaint 都是局部演算法,視野被演算法自身限制死);edge 模式效果小且不一致
  (`nearest` 反而因誤用鄰近圖層像素變差),無案例跨過 1a 門檻。結論收窄原假設:512px
  上下文只對生成式模型(候選 17)有意義,對現有 CPU baseline 無效。未改動 production 代碼。
  見 `knowledge/s4-inpaint-context-window.md`、`log/s4-2026-08-31-020.md`。
- 2026-08-31:**吸收使用者自製 Photoshop `GPT Fill` UXP 插件 v1.18 知識(chunk 19,使用者
  直接指定)** — 完整讀過 5 檔(`main.js` 1986 行),產出
  `knowledge/s4-gptfill-plugin-knowledge.md`。取得 mask 慣例外部真值(8px 融合邊界 /24px
  footprint /洞占比 30% 模式門檻)、揭露我們「1a 全 fail」結論隱含的「零上下文」前提
  (插件下限 512px → 候選 19,零成本可立即驗)、記錄生成結果不像素對位的五層對位管線
  (候選 17 的真正工程主體)、並用獨立來源佐證 chunk 18 發現的失真維度 → 候選 16 具體化為
  「邊界證據延續性」(候選 18)。標註候選 4 結論的前提已變(使用者端已有 API 生成路徑,
  不需容器內養 GPU)。未改動 production 代碼。見 `log/s4-2026-08-31-019.md`。
- 2026-08-31:**候選 7(1b 閾值反向校準,vision 代理)調查完成,結論:不變更閾值,浮現
  候選 16(chunk 18)** — 新增 `tools/mesh_gen/s4_vision_proxy_compare.py`,用 Claude
  自身 vision 讀圖代理缺失已久的人工「有沒有穿幫」標註,跑 6 個涵蓋四種材質類型的案例。
  負對照/平滑漸層/全平坦三類與既有數字判定 100% 一致;`鬢角1` 的 gt 用 vision 確認無破綻,
  補上候選 8 tone_gap false-positive 的第一手視覺證據。核心發現:機械紋理(身體/左手)的
  CPU baseline 補丁會丟失高頻細節,但這是現有三指標共同缺少的維度、不是門檻問題,調數字
  解不了。誠實限制:此代理是靜態放大單層裁切,弱於真實動畫尺度下的真人標註。決策:不變更
  `THRESH_1B`,提出候選 16(加第 4 個指標,或貼回真實 Award spine 場景跑動畫截圖比對)。
  見 `knowledge/s4-inpaint-1b-lenient-gate.md`、`log/s4-2026-08-31-018.md`。
- 2026-08-31:**候選 6(擴大樣本至 `Symbol_Ww.psd` icon 類其他 11 層)完成(chunk 17)** —
  補測 `左手1/2/3`、`右手1/2`、`耳機1/2`、`鬢角1/2`、`音符1/2` 共 11 層。1a 邊界結論延續且
  可攜到 icon 類材質(僅真正平坦的 `左手3` 通過,細節材質全 fail)。1b 邊界多數延續(8 層
  CPU baseline 全 pass),但新增 2 筆 `tone_gap` 正對照 miscalibration(`音符1/2`、`右手2`
  edge 壓線)量化證實驅動因素是色調變化量級而非面積,屬候選 8 已知限制的再驗證,維持不調整
  全域門檻。另確認小尺寸材質(120~637px)edge 模式 1b 覆蓋率缺口延續存在。本次僅擴大測試
  樣本,未改 production 代碼。見 `knowledge/s4-inpaint-tone-gap-limits.md`、
  `log/s4-2026-08-31-017.md`。
- 2026-08-30:**候選 4(LaMa 可行性探測)完成,結論:網路不擋但代價高,通用權重不足以解 1a
  (chunk 16)** — 新增 `tools/mesh_gen/s4_lama_probe.py`。網路政策:PyPI `torch`(帶 ~2GB
  CUDA 依賴)、GitHub release 的 `big-lama.pt` 皆可下載;`download.pytorch.org`/
  `huggingface.co` 被擋。跑分:通用預訓練 LaMa 對機械紋理材質(身體/左手)6/8 指標贏過
  CPU baseline,但無一跨過 1a 門檻;1b 標準下 CPU baseline 已 pass,LaMa 無新增益。
  不建議投入,不寫進 `requirements.txt`。見 `knowledge/s4-lama-feasibility.md`、
  `log/s4-2026-08-30-016.md`。
- 2026-08-30:**候選 14 調查完成,結論:兩個獨立根因,4 種修法皆非零回歸(chunk 15)** —
  拆解出「材質內部紋理雜訊污染 ring 統計」(硬邊材質,如 `右手`)與「光滑材質非線性衰減使
  線性外推模型結構性失效」(如 `光暈`)兩個獨立根因。用全部 1233 筆量化資料測試 4 種修法,
  最佳方案(方向濾波+p90)13 fixed、9 newly broken,淨提升但非零回歸,不符合落地門檻,
  本次未修改 production 代碼。新增候選 15(A 類岔路,trade-off 是否可接受待使用者裁決)。
  見 `knowledge/s4-inpaint-alpha-taper-candidate14.md`、`log/s4-2026-08-30-015.md`。
- 2026-08-30:**`estimate_alpha_taper` 小樣本 bug 量化與修正完成(里程碑,候選 13,chunk 14)** —
  跨 12 個材質(機器人拆件 5 層 + Symbol_Ww 7 層,新增之前沒測過的 底/頭/身體/墨鏡/wild)、
  circle/ellipse 多種洞形狀共 1233 次取樣量化候選 10 意外撞見的 bug:失敗集中在
  `ring_count∈[5,20)`(剛好卡在舊門檻 5 之上、樣本仍不足以讓中位數穩定的縫隙),`alpha_mae`
  平均 4~12、最差 139.9。用同一批資料掃過候選門檻 10~28(不是猜的):20~22 是最後零負面
  案例的安全帶,25 起出現因誤傷有效局部樣本而變差的反向案例——**`min_ring` 從 5 提高到
  20**。回歸驗證:3 組既有案例(機器人 3 材質 interior/edge、8 組真實遮擋、Symbol_Ww 2
  材質、`psd_inplace_patch.py --auto`)修改前後完整 JSON diff 為空(它們的 `ring_count`
  本來就落在不受此次調整影響的桶)。**誠實範圍界定,新發現候選 14**:同一批資料也發現一個
  完全不同根因、大樣本數(50~700+)下依然崩壞的獨立失敗模式(`右手` edge 小洞
  alpha_mae 115.6、`光暈` 特定橢圓洞 alpha_mae ~100),`min_ring` 對這批無效,本次不修,
  留給後續 chunk。見 `knowledge/s4-inpaint-alpha-taper-robustness.md`、
  `log/s4-2026-08-30-014.md`。

- 2026-08-30:**光暈材質 1a 邊界再校準(候選 10)調查完成,結論:無法化約成單一合成參數** —
  `punch_hole` 新增 `shape="ellipse"`(面積/長寬比/朝向獨立可控)+ `center`(固定洞心做
  控制變因實驗),新增 `tools/mesh_gen/s4_1a_shape_boundary.py`。控制實驗分別檢驗「形狀
  狹長度」(固定位置,aspect 1~3 掃描)與「位置」(固定圓形小洞,沿真實遮擋方向掃描)
  兩個候選解釋,**都不足以重現**候選 1 觀察到的非單調 pass/fail——`seam_grad_diff` 在
  可行測試範圍內都遠低於門檻。誠實結論:光暈這類材質的 1a 邊界無法化約成單一合成洞參數
  (面積/長寬比/位置擇一),必須用真實遮擋洞的大面積+真實形狀+位置一起看,呼應候選 1/8
  的既有結論——1b(防穿幫)才是本專案該用的實戰驗收線,不需要再修一個更精確的 1a 邊界公式。
  **意外發現並除錯到根因**:`estimate_alpha_taper` 在特定橢圓 interior 洞下出現真實 bug
  (RGB 補對,alpha 因 n=7 小樣本污染催毀性低估,60 vs 真值 255),列為候選 13。回歸驗證:
  `punch_hole` 新參數皆有預設值、`shape="circle"` 路徑逐行未動,機器人 3 材質(interior+edge)
  + Symbol_Ww 2 材質 + 8 組真實遮擋 + `psd_inplace_patch.py --auto` 端到端數字皆與既有紀錄
  逐位元一致(seam_grad_diff 10.596/21.307/19.314、tone_gap 32.838/57.296、chosen_method
  =nearest 皆重現)。見 `knowledge/s4-inpaint-1a-shape-boundary.md`、`log/s4-2026-08-30-013.md`。

- 2026-08-29:**1b edge 模式支援完成(里程碑,候選 2)** — `score_1b()` 新增
  `mode="edge"`;第一版「比對真實輪廓其他段落天然變化」構想量化後證實鑑別力不足,改採
  「排除貼真實輪廓的邊界段落,只評內容內部轉接」,複用 interior 既有 baseline。機器人
  拆件家族 edge 模式 1b 校準通過;候選 9 揭露的關鍵缺口案例 `頭←右手` 現在有真正判定,
  之前完全沒有驗收線的小尺寸機械材質補圖現在 3 個 CPU baseline 全 pass。過程中修正一個
  真實 bug(`content` 校準流程與真實落地流程語意不同,導致端到端 `applicable` 恆
  `False`)。Symbol_Ww 已知 tone_gap 限制(候選 8)延續,非新問題。回歸驗證 interior
  模式逐位元不變。見 `knowledge/s4-inpaint-1b-edge-gate.md`、`log/s4-2026-08-29-012.md`。

- 2026-08-29:**遮擋真值法擴大樣本至 8 組(候選 9)** — 新增 4 組小面積/懸殊比例配對,含本檔
  測過最小絕對洞尺寸(829px)與最大比例(46.5%)。機械紋理結論可攜到新材質 `右手`。核心發現:
  小尺寸圖層(`頭`)的真實遮擋洞天生易落在 `edge` 模式,揭露 1b 對小素材完全無驗收線可用的
  真實缺口(非理論假設)——候選 2(1b edge 支援)優先度上修。回歸零反向。見
  `knowledge/s4-inpaint-real-occlusion.md`、`log/s4-2026-08-29-011.md`。

- 2026-08-29:**遮擋真值法完成(里程碑,候選 1)** — `real_occlusion_eval.py` 用機器人拆件真實
  圖層疊合輪廓當洞,比合成挖洞更貼近實戰;過程中揪出並修正 1b `seam_ratio` 全域基準
  miscalibration(局部漸層不均勻材質下全域平均基準失真),局部化後回歸零反向。核心結果:
  機械紋理判定與合成挖洞閘一致;光滑漸層材質在真實大面積/不規則遮擋下 1a 會超標(1b 仍
  pass),確認候選 0 結論的隱含前提。見 `knowledge/s4-inpaint-real-occlusion.md`、
  `log/s4-2026-08-29-010.md`。

- 2026-08-28:**S4 拆為獨立排程(由主排程交接)**。建 `handoff_S4.md` / `prompts/run_s4.md` / 本檔。
  切圖半邊繼承既有成果(已完成);補圖半邊為本排程主任務,狀態 `SETUP`,待第一次執行推進 chunk 0。
- 2026-08-28:**第一次 S4 排程執行(SETUP→ACTIVE,里程碑)** — 完成補圖閘 v1(`inpaint_eval.py`)+
  Level 1(邊緣外擴)/Level 2(cv2.inpaint)baseline;校準通過;對真實機器人拆件件量化出「CPU 補得動
  (平滑漸層)vs 補不動(機械細節紋理,任何洞尺寸皆 fail)」的誠實邊界,呼應 PSD-first 契約策略。
  見 `knowledge/s4-inpaint-evaluator.md`、`log/s4-2026-08-28-001.md`。
- 2026-08-28:**PSD 圖片預覽器(使用者直接指定)** — `psd_preview.html` 讓切圖/補圖成果即時視覺化驗收
  (疊圖/差異熱圖/pass-fail 卡片);`psd_slice.py`/`inpaint_eval.py` 增量輸出配合;Playwright 驗證互動,
  無下游回歸。見 `knowledge/s4-preview-tool.md`、`log/s4-2026-08-28-002.md`。
- 2026-08-28:**補圖問題定義修正(使用者釐清)** — 補圖分三種情境(1a 需表演/1b 防穿幫/2 視角外推),
  驗收標準不同;既有補圖閘結論是 1a 嚴格標準,1b 情境需另一組寬鬆閘;類別 2 不是補圖演算法問題,
  屬 S1 需求前移範疇。見 `knowledge/s4-inpaint-taxonomy.md`。
- 2026-08-28:**1b 防穿幫寬鬆閘完成(里程碑)** — 自我參照三指標(alpha_gap/seam_ratio/tone_gap),
  正負對照校準通過;踩到一次真實 miscalibration(alpha 門檻 200→8,天然軟邊素材誤判)並修正;
  發現並收斂 1b 適用範圍(只限 interior 模式)。**核心結果**:先前「CPU 補不動」的機械紋理案例
  (身體/左手)在 1b 標準下 3 個 baseline 全 PASS,驗證使用者假設。`psd_preview.html` 同步加雙判定燈。
  見 `knowledge/s4-inpaint-1b-lenient-gate.md`。
- 2026-08-28:**PSD 內編輯統一座標系(使用者要求,里程碑)** — 新增 `psd_inplace_patch.py`,補圖
  一律直接寫回 PSD 圖層的全域座標(讀 `layer.left/top`,不手動換算 offset)。修正兩個真實
  psd-tools 陷阱:中文圖層名寫入 crash(改用 `luni` tagged block)、重存後 PSD 預設 `composite()`
  吃到壞掉的合併預覽(無 alpha,導致 orphan_ratio 誤判暴增)——`psd_slice.py` 加 `force=True` 修正,
  原生 PSD 回歸無影響。端到端驗證兩層皆 `overall_pass: true`。見 `knowledge/s4-psd-inplace-edit.md`。
- 2026-08-28:**評分→採用→落地完整鏈路打通(里程碑)** — `inpaint_eval.score_candidates`/
  `select_best`(1b 分數盲選候選 baseline)+ `psd_inplace_patch.patch_layer_auto`(真實情境)/
  `demo_auto_patch`(自我測試,盲選後才揭曉 1a 分數驗證選得好不好)。修正新踩到的坑:1b 只在
  interior 校準過,加 `applicable` 旗標避免 edge 洞被誤標高信心 pass_1b(左手 edge 案例驗證
  修正生效)。舊路徑與 psd_slice/inpaint_eval 回歸皆無影響。見
  `knowledge/s4-inpaint-auto-select-pipeline.md`、`log/s4-2026-08-28-007.md`。
- 2026-08-28:**修正 `fill_cv2_inpaint` 的 edge 模式 alpha 處理** — 新增 `estimate_alpha_taper`
  (距離場×局部量測漸縮寬度)取代「洞內強制拉滿不透明」。過程中排除了兩個更直覺但實測更差的
  解法(alpha 整顆跑 cv2.inpaint、alpha 單點最近鄰外推),用量化證據記錄為何不能用。跨 7 個件
  (3 舊 + 4 新獨立資產 `Symbol_Ww.psd`)、interior/edge 全跑回歸:interior 持平、edge 全面
  改善、6 處判定翻盤皆正確方向。刻意不套用到 `fill_nearest`(會讓環形鏤空件判定翻盤變差)。
  順帶發現 1b 的 `tone_gap` 校準對新材質不成立,列為新候選。見
  `knowledge/s4-inpaint-evaluator.md`、`log/s4-2026-08-28-008.md`。
- 2026-08-29:**候選 8(1b `tone_gap` 重新校準)調查完成,結論:無法簡單修正** —
  先修正真實 bug:`punch_hole` interior 模式材質太薄時原本靜默偽造不合規範的洞(`框`
  案例汙染了 session 008 的異常發現),改為縮洞或明確報錯 + 批次評測優雅跳過。對真正的
  殘留案例(`臉部陰影`)嘗試兩種 `tone_gap` 正規化,皆量化證明失敗(不同材質的 gt/random
  分布本身重疊,無單一門檻可解)。誠實結論:`tone_gap` 只在機器人拆件材質家族內可信,
  跨材質家族需個別重新校準,不強行套用會製造假信心的全域正規化。回歸:原 3 材質校準與
  `psd_inplace_patch.py` 端到端數字皆與 session 008 一致。見
  `knowledge/s4-inpaint-tone-gap-limits.md`、`log/s4-2026-08-29-009.md`。
