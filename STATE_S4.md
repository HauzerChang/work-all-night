# S4 進度狀態 (STATE_S4) — 補圖/切圖獨立排程續跑核心

> 本檔僅供 **S4 專屬排程** 使用(分支 `claude/spine-s4-inpainting`)。主排程請看 `STATE.md`。
> 每次 S4 session 結束前**必須**更新此檔。冷啟動背景見 `handoff_S4.md`,執行指令見 `prompts/run_s4.md`。

## 專案狀態

`ACTIVE`  <!-- SETUP / ACTIVE / BLOCKED / DONE -->

> **chunk 51(2026-09-05)**:承接 chunk 50 留下的候選項,對 `suggestions.json` 尚未驗證過
> 的部件全部裁圖複核(先前 chunk 47-50 只查過下半身手/腿/靴子),盤點角色頭/頸部一帶,
> 發現 **5 個部件(`head`/`fox_ears`/`hair_front`/`earrings`/`choker`)框全部對不準**,原
> 信心多標 `high`。共同模式:這張圖是帶版面文字的角色設定圖(標題「JIUWEI·YANLIAN」+
> 引言疊在上方深色背景),臉部要到畫面中段才開始,原始框卻普遍偏在最上方的文字區域,跟
> 先前發現的「跟鄰居部件內容混淆」不是同一種錯誤,是更基礎的「壓根沒框到內容」。用網格
> 疊圖工具定位五官/耳朵/耳環/頸飾實際像素位置後改框,confidence 從 high 下修為 medium。
> **自驗**:20 部件 `--contour rect --eval` AC1 pass,逐格複核修正後裁圖確實是完整臉部/
> 雙耳/髮絲/耳環/頸飾。**誠實限制**:`hair_front` 跟 `head`/`fox_ears` 新框大幅重疊(髮型
> 本身無清楚瀏海分界,留待使用者用 assist viewer 確認);`earrings` 只框到畫面上唯一可見
> 的單耳耳環(另一耳被長髮遮住);`bodice`/`sleeve_right`/`tag_pendant`/`skirt` 裁圖後仍
> 有跟鄰近部件重疊跡象,本次未處理(前兩者是 chunk 48 已知演算法歧異案例,後兩者是新觀察
> 到、還沒深入定位的疑慮);驗證用決策檔仍非 chunk46-48 真實那份,不能延續其統計數字;
> 未重跑 `--contour sam`(容器未持久化 MobileSAM 權重)。見下方「chunk 51」段落與
> `knowledge/s4-decompose-box-fix-face.md`。
>
> **chunk 50(2026-09-04)**:承接 chunk 49 做法,獨立複查 chunk 48 留下的第三個「框有
> 問題」案例 `hand_right`——換算 `suggestions.json` 像素框跟 chunk 48 報告的錯誤座標
> 幾乎完全吻合,確認同樣是 chunk 43 草稿就錯,依既有慣例(chunk 26/49)在源頭修正。
> **複查過程中額外發現 `hand_left` 也是同類「框完全沒對準」錯誤**——這一項先前沒有任何
> chunk 標記過:chunk 47 用使用者當次手動調整過、未持久化進 repo 的真實決策檔測試,把
> `hand_left` 列為「9 個明確正確」之一,但這次獨立用網格疊圖工具檢視 `suggestions.json`
> 這份持久化草稿,發現它的 `hand_left` 框完全落在尾巴/翅膀狀毛髮紋理上,跟實際手部位置
> 完全不重疊。兩個框都改對準畫面上實際的手(手腕紅色纏繞絲帶+完整五指),confidence
> 從 high 下修為 medium。**自驗**:20 部件 `--contour rect --eval` AC1 pass,逐格複核
> 修正後裁圖確實是完整左手/右手。**誠實限制**:驗證用決策檔仍非 chunk46-48 真實那份,
> 不能延續其統計數字;`hand_left` 的落差提高一個疑慮——`suggestions.json` 草稿裡目前
> 沒被回報過問題的其餘部件也可能有同類「使用者當次修好但未持久化」的落差,不能只靠
> 「沒被回報」就假設框是對的,若要更全面盤點需逐一複查而非等下游回報;未重跑
> `--contour sam`(容器未持久化 MobileSAM 權重)。見下方「chunk 50」段落與
> `knowledge/s4-decompose-box-fix-hands.md`。
>
> **chunk 49(2026-09-04)**:執行 chunk 48 留下的選項 (a)(零成本、唯一已知有效的
> 改進動作),本次排程無活人裁決,依既有慣例(chunk 26)執行不需授權的選項。**追溯
> 錯誤來源**:chunk46-48 用的使用者手動確認決策檔未持久化進 repo,改查 repo 裡持久化
> 的 `assets/jiuwei_yanlian_char_crop.suggestions.json`(chunk43 我自己的原始草稿),
> 換算 `leg_left`/`boot_left` 的 `bbox_pct`→像素,跟 chunk48 報告的錯誤座標完全吻合
> ——確認錯誤從 chunk43 就已存在。用網格疊圖工具放大檢視來源圖,發現兩腿在畫面上緊貼
> 重疊、肉眼分不出左右腿分界,靴子同理只有單一連續靴筒輪廓;比照已驗證正確的
> `leg_right`/`boot_right`(框住連續膚色/靴筒右半),把兩個錯誤框改框到左半部,
> confidence 從 high 下修為 medium 並記錄材質限制。**自驗**:20 部件
> `--contour rect --eval` AC1 pass,逐格複核修正後裁圖確實是大腿膚色/黑色靴筒(不再
> 是手/布料+毛髮)。**誠實限制**:框位置修對後,`leg_left`/`leg_right` 裁出的內容仍
> 是同一團連續膚色的左右兩半(兩腿本來就視覺重疊、不可分,是素材限制不是分割問題,
> 若後續要做成真正獨立擺動的兩個 spine slot 需另外處理);本次驗證用的 20 部件決策檔
> 是從 `suggestions.json` 重新換算,不是 chunk46-48 那份使用者手動調整過的真實決策
> 檔,不能延續其統計數字;未重跑 `--contour sam`(容器未持久化 MobileSAM 權重);
> `hand_right` 框未對準問題本次未修正。見下方「chunk 49」段落與
> `knowledge/s4-decompose-box-fix-legs.md`。
>
> **chunk 48(2026-09-04)**:使用者選 chunk 47 提案方向1(點提示)。**先於Python層直接
> 驗證再蓋UI**:憑印象猜點第一輪失敗(方法論有瑕疵);第二輪放大逐格目視確認框內容,
> 意外發現比點提示本身更重要的事——`leg_left`/`boot_left`根本不是分割問題,決策檔框
> 位置從一開始就沒框住目標(裡面是手/絲帶布料,不是腿/靴子),正確修法是回assist viewer
> 手動重框,不需要演算法。對真正「框正確但SAM選錯」的案例(bodice/sleeve_right)測點提示
> (正向點+正負點組合共4次)**全部沒有解決**,即使點是目視精準確認過的。**沒有蓋UI**
> (中途加的骨架驗證無效已還原)。見下方「chunk 48」段落與
> `knowledge/s4-sam-point-prompt-investigation.md`。
>
> **chunk 47(2026-09-04)**:使用者實測矩形裁切後明確反對,要求框內精準找不規則輪廓。
> **GrabCut(傳統色彩分割)實測完全失敗**(3/3測試案例全選錯,沒有語意理解)。改用
> **MobileSAM**(Apache2.0,CPU可跑,huggingface.co被擋改用raw.githubusercontent.com
> 直接抓權重)整合進 `s4_decompose_cut.py`(`--contour sam`)。真實20部件決策檔+
> **逐格人工視覺複核**:9個明確正確、2個自動攔截、**5個(25%)自動heuristic完全沒
> 抓到的靜默錯誤**(框跟鄰近部件重疊,SAM選到鄰居內容,遮罩乾淨信心不低,測不出來)。
> 誠實結論:比GrabCut好很多但不是解決方案,pipeline目前不能盲目信任自動輸出。見下方
> 「chunk 47」段落與 `knowledge/s4-sam-segment.md`。
>
> **chunk 46(2026-09-04)**:使用者裁示「排程上優先區塊一(切割),到一定技術水準再進
> 區塊二」,建 `s4_decompose_cut.py`(決策檔→硬邊界矩形裁切→manifest.json)+
> `psd_node/manifest_to_psd.js`(Node/ag-psd 組回PSD,不需node-canvas)。自驗閘經歷
> 兩次真實失敗才收斂(套錯判準+盲點),過程完整記錄。**使用者接著提供自己用assist
> viewer調整過的真實決策檔實測**,視覺逐格檢視20個裁出部件後誠實發現:多個部件的
> bleed比「邊緣破損」嚴重得多(head框裝了大半標題文字等),已超出原授權範疇,留3個
> 方向給使用者裁決。見下方「chunk 46」段落與 `knowledge/s4-decompose-cut-tool.md`。
>
> **chunk 45(2026-09-04)**:使用者要求把「拆解」拆成兩個獨立研究區塊:**切割**(裁
> 部件,邊緣允許破損,已授權沿用既有六階段第3點,不需另開新研究)vs **切片**(單層拆
> 多層——淺層:物件/陰影/光源分離;深層:遮擋物+底下被遮內容分離,如墨鏡下的眼睛)。
> 純研究筆記(零API花費零production代碼異動):切割是空間切分,像素資訊都還在;切片是
> 訊號分離/反推,難度依底下內容是否還在畫面裡分兩級——陰影/光源分離提出CPU反推
> blend-mode構想(未驗證);遮擋物底下內容必須生成式inpainting腦補,跟情境2視角外推
> 同難度,不可直接沿用candidate17已驗證的邊緣修補可靠度。留4項待使用者裁示,見下方
> 「chunk 45」段落與 `knowledge/s4-cut-vs-slice-research-split.md`。
>
> **chunk 44(2026-09-04)**:使用者確認 chunk 43 提案的 part list JSON schema 後,建
> `tools/mesh_gen/s4_decompose_assist.html`(六階段第6點輔助拆圖viewer):載入圖+選填
> 載入 Claude 建議JSON(`bbox_pct`自動換算像素框+信心色)→拖曳畫新框/選取/移動/調整
> 大小/刪除/編輯欄位→匯出使用者確認過的決策檔(`bbox_px`像素座標)。純前端零API零花費,
> Playwright用真實九尾焰蓮素材(20建議部件)完整驗證,零JS錯誤。**順帶關閉 chunk 43
> 技術問題#2**:驗證瀏覽器端 `ag-psd` 的 `writePsd()` 可用(與獨立 Python `psd-tools`
> 交叉驗證圖層名稱/bbox/像素完全匹配),足以承擔第3點PSD組裝需求。第3/4點仍未開始。
> 見下方「chunk 44」段落與 `knowledge/s4-decompose-assist-viewer.md`。
>
> **chunk 43(2026-09-04)**:使用者裁示把「拆解」重新分成六階段(Claude語意分析→使用者
> 確認邊界→幾何裁切+PSD轉換→GPT局部修補→viewer簡化回只留補圖→輔助拆圖viewer),取代
> chunk 39/42 的「AI一鍵重繪整張圖」設計。**第5點已完成**(viewer 移除切片/拆解/需求
> 精靈,Playwright驗證無回歸)。**第1/2點現場示範**(用九尾焰蓮案例,零成本 Claude vision
> 分析,產出 part list JSON,對困難部件誠實回報低信心)——**等待使用者確認格式後再建
> 第6點輔助viewer**。見下方「chunk 43」段落與 `knowledge/s4-decompose-restage-plan.md`。
>
> **chunk 42(2026-09-04)**:使用者實測拆解功能對一對機械翅膀輸出完全不相干的人形部件
> (真實付費呼叫)。診斷確認是拆解分頁預設 prompt 寫死人形假設(head/torso/arms/legs)
> 導致 —— **我的設計疏失,非模型隨機失效**。已修正 prompt(主體無關+錨定語句)+ size
> 自動建議,Playwright 驗證邏輯正確但**新版本尚未經真實付費呼叫重新驗證**。見下方
> 「chunk 42」段落與 `knowledge/s4-decompose-prompt-bug-wings-case.md`。
>
> **chunk 41(2026-09-04)**:使用者對話貼一張角色設定圖(「九尾・焰蓮」),要求提取角色
> 拆解,定調為新課題「高複雜度人物如何轉換成 spine」。從 session JSONL 記錄復原檔案
> (對話貼圖無現成存檔工具,見下方「取檔手法」),存進 `assets/`,裁出角色主圖。內容
> 解析+難度評估(九尾同色重疊/半透明材質/長髮尾巴同色系)見下方「chunk 41」段落與
> `knowledge/s4-highcomplexity-charsheet-jiuweiyanlian.md`。**尚未做任何拆解實驗**。
>
> **chunk 40(2026-09-04)**:使用者要求 viewer 三功能對焦同一份檔案,不要各別載入。重構
> `s4_ai_viewer.html` 為單一「主素材」狀態(`setMainAsset()` 唯一寫入點),拆解拿掉獨立
> file picker 改讀共用主素材,新增 composite 偽圖層列自動選取。**寫測試抓到一個真實 bug**
> (遮罩畫布預設模式下不能互動)並修正。5 組 Playwright 測試全過。見下方「chunk 40」段落
> 與 `knowledge/s4-ai-viewer-v3-unified.md`。
>
> **chunk 39(2026-09-04)**:使用者要求 viewer 補上拆圖能力。在主線 `s4_ai_viewer.html`
> 上擴充成 4 分頁(補圖/切片/拆解-實驗性/需求精靈),不另開新檔。切片沿用 chunk 37 驗證過
> 的 ag-psd 解析;拆解萃取自 chunk 38 的 GenieLabs 知識(獨立重新實作);需求精靈是
> `spine-asset-request` 決策表的可點選版本。5 組 Playwright 測試全過(含合成圖驗證分割
> 演算法精確偵測3個部件),全程 mock 付費 API。見下方「chunk 39」段落與
> `knowledge/s4-ai-viewer-v2-slicing.md`。
>
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
> API 做端到端驗證);次要能力 V1(chunk 37,`psd_viewer.html`)也已完成並驗證;**chunk 39
> 補上拆圖能力**(切片/拆解-實驗性/需求精靈三分頁),viewer 目前功能涵蓋使用者原始三項
> 需求(檢視/編輯 PSD、與 AI 即時溝通補圖、拆圖)。
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

- 2026-09-05:**修正 head/fox_ears/hair_front/earrings/choker 決策檔框位置錯誤(chunk 51)** —
  承接 chunk 50 留下的候選項,對 `suggestions.json` 尚未驗證過的部件全部裁圖複核(先前
  chunk 47-50 只查過下半身手/腿/靴子),盤點角色頭/頸部一帶,發現 5 個部件框全部對不準
  (`head`/`fox_ears`/`hair_front`/`earrings`/`choker`,原信心多標 `high`)。共同模式:
  這張圖是帶版面文字的角色設定圖(標題+引言疊在上方深色背景),臉部要到畫面中段才開始,
  原始框卻普遍偏在最上方的文字區域——跟先前發現的「跟鄰居部件內容混淆」不同,是更基礎的
  「壓根沒框到內容」。用網格疊圖工具定位五官/耳朵/耳環/頸飾實際像素位置後改框,confidence
  從 high 下修為 medium。自驗:20 部件 `--contour rect --eval` AC1 pass,逐格複核修正後
  裁圖確實是完整臉部/雙耳/髮絲/耳環/頸飾。**誠實限制**:`hair_front` 跟 `head`/`fox_ears`
  新框大幅重疊(髮型本身無清楚瀏海分界,留待使用者用 assist viewer 確認);`earrings` 只
  框到畫面上唯一可見的單耳耳環(另一耳被長髮遮住);`bodice`/`sleeve_right`/`tag_pendant`/
  `skirt` 裁圖後仍有跟鄰近部件重疊跡象,本次未處理;驗證用決策檔仍非 chunk46-48 真實那份,
  不能延續其統計數字;未重跑 `--contour sam`(容器未持久化 MobileSAM 權重)。見
  `knowledge/s4-decompose-box-fix-face.md`、`log/s4-2026-09-05-051.md`。

- 2026-09-04:**修正 hand_left/hand_right 決策檔框位置錯誤(chunk 50)** — 承接 chunk 49
  做法,獨立複查 chunk 48 留下的第三個「框有問題」案例 `hand_right`,換算
  `suggestions.json` 像素框跟 chunk48 報告的錯誤座標幾乎完全吻合,確認同樣是 chunk43
  草稿就錯,依源頭修正。複查過程額外發現 `hand_left` 也是同類錯誤(先前未被任何 chunk
  標記——chunk47 用未持久化的真實決策檔判定 `hand_left`「明確正確」,但 `suggestions.
  json` 這份持久化草稿的框其實完全落在毛髮紋理上、跟真實手部位置不重疊)。用網格疊圖
  工具找出兩隻手實際位置(手腕紅色纏繞絲帶+完整五指)後改框,confidence 下修為
  medium。自驗:20部件決策檔`--contour rect --eval`AC1 pass,逐格複核裁圖確認是完整
  左手/右手(不再是毛髮紋理/符紙標籤+白紗)。誠實限制:驗證用決策檔仍非chunk46-48真實
  那份不能延續統計;hand_left 的落差提高一個疑慮——`suggestions.json` 草稿裡目前沒被
  回報過問題的其餘部件也可能有同類「使用者當次修好但未持久化」的落差,不能只靠「沒被
  回報」就假設框是對的;未重跑sam(權重未持久化)。見
  `knowledge/s4-decompose-box-fix-hands.md`、`log/s4-2026-09-04-050.md`。
- 2026-09-04:**修正 leg_left/boot_left 決策檔框位置錯誤(chunk 49)** — 執行 chunk 48
  選項(a)(零成本、唯一已知有效的改進動作),無活人裁決依既有慣例執行不需授權的選項。
  追溯發現錯誤從 chunk43 我自己的原始 vision 草稿(`assets/jiuwei_yanlian_char_crop.
  suggestions.json`)就已存在(換算 bbox_pct→像素跟 chunk48 報告的錯誤座標完全吻合),
  改在這份持久化檔案上修正,不需要使用者重新提供未持久化的真實決策檔。視覺定位:兩腿
  在來源圖裡緊貼重疊、肉眼分不出左右分界,比照已驗證正確的 leg_right/boot_right(框
  右半),把 leg_left/boot_left 改框到同一片連續膚色/靴筒的左半部,confidence 下修為
  medium。自驗:20部件決策檔`--contour rect --eval`AC1 pass,逐格複核裁圖確認是大腿
  膚色/黑色靴筒。誠實限制:兩腿視覺本來就重疊不可分(素材限制非分割問題)、驗證用決策
  檔非chunk46-48真實那份不能延續統計、未重跑sam(權重未持久化)、hand_right未修正。
  見 `knowledge/s4-decompose-box-fix-legs.md`、`log/s4-2026-09-04-049.md`。
- 2026-09-04:**點提示能否修正SAM靜默錯誤?負面結果+更有用的發現(chunk 48)** —
  使用者對chunk47提出的兩個改進方向選了方向1(點提示)。**在蓋UI前先於Python層直接
  驗證演算法有沒有用,避免蓋一個沒被驗證有效的功能**:第一輪憑印象猜點測5個已知失敗
  案例,結果全部沒有明顯改善——但這輪方法論有瑕疵(誠實記錄):連自己選的點都可能沒
  點準,不算是在測「點提示有沒有用」。**第二輪改用網格疊圖工具放大逐一目視確認框內容
  才選點**,過程中意外發現一件比點提示測試本身更重要的事:chunk47統計的5個靜默錯誤裡,
  **`leg_left`跟`boot_left`根本不是分割演算法的問題**——放大一看,這兩個框
  (`leg_left`:124,512,212,656;`boot_left`:124,602,225,889)裡完全沒有腿/靴子,
  分別是一隻手(帶紅指甲)+尾巴毛髮、絲帶裝飾布料+尾巴毛髮。**決策檔框位置從一開始就
  沒框住標籤指定的目標**,不管換哪種分割演算法(GrabCut、MobileSAM、甚至完美人工分割)
  都救不回來——正確修法是回到既有`s4_decompose_assist.html`手動重新框,不需要任何
  演算法投入,零成本。對真正「框確實正確、純粹SAM選錯候選」的案例(`bodice`、
  `sleeve_right`)測點提示:只加正向點(目視確認精準位置)、加正向+負向點組合,兩輪共
  4次嘗試,**全部沒有解決**——`bodice`仍主要選到頭髮、`sleeve_right`仍主要選到紅色
  胸衣,結果跟純框版本幾乎沒有實質差異。**誠實結論**:點提示在這批測試案例上沒有展現
  可靠修正能力,原因未確認(MobileSAM的TinyViT表達力較弱對點提示不夠敏感?或這批素材
  本身——半透明材質、大範圍髮絲交疊——對任何box+point分割都結構性困難?完整版SAM
  未測試,是唯一還沒排除的技術變因)。**沒有蓋UI**:中途在
  `s4_decompose_assist.html`加了點選按鈕骨架(尚未接JS邏輯),驗證點提示無效後用
  `git checkout`還原,repo無殘留半成品——蓋一個看起來能用實際上解決不了問題的假選項
  比不蓋更糟。**修正chunk47的統計數字**:「25%靜默錯誤(5/20)」應拆解為2個決策檔框
  位置錯誤(現成零成本修法)+3個真正演算法歧義(目前無解)。**留3個未執行選項給使用者
  裁決**:(a)先修2個錯誤框(零成本,唯一已知有效的改進動作)、(b)對剩下3個接受人工
  處理、(c)測試完整版SAM(ViT-H,~2.4GB,CPU推論會慢很多,成本明顯更高,需使用者先
  確認再測試,不像MobileSAM那樣可以先斬後奏)。見
  `knowledge/s4-sam-point-prompt-investigation.md`、`log/s4-2026-09-04-048.md`。
- 2026-09-04:**box-prompted語意分割(MobileSAM)取代矩形裁切(chunk 47)** — 使用者
  對 chunk 46 的矩形裁切結果明確反對:「只切出矩形 不符合我的需求, 我想要的是 框選的
  範圍內 精準找到部件 並切割出來, 你需照偵測各種不規則的輪廓 進行提取」。**候選1
  OpenCV GrabCut**(不需下載模型,最低成本候選,先試):對 head/choker/earrings 三個
  代表性部件測試(rect初始化+手動seed mask兩種模式)**全部選錯**——head選到背景暗色塊、
  choker選到裸肩、earrings選到整張臉。根因:GrabCut只做顏色統計分割,沒有語意理解,
  框裡如果同時有小物件跟視覺更顯著的內容,一律選顯著的那個,不管標籤寫什麼。**候選2
  MobileSAM**(Meta Segment Anything輕量版,Apache2.0商用無虞,TinyViT encoder,
  CPU可跑,權重~40MB):huggingface.co被org網路政策明確擋掉(gateway 403),使用者
  同意開放後測試仍擋;改查發現該repo少見地把權重直接放在repo裡而非HuggingFace,改用
  `raw.githubusercontent.com`(可用,不受repo授權範圍限制,跟`codeload.github.com`/
  `api.github.com`不同)直接下載成功,記錄可重現指令+sha256;mobile_sam原始碼非PyPI
  套件,用`git clone`取得(Apache2.0)。整合進`tools/mesh_gen/s4_decompose_cut.py`
  新增`--contour {rect,sam}`參數(預設rect不動舊行為),新增`tools/mesh_gen/
  s4_sam_segment.py`封裝SAM推論+兩個信心heuristic(前景比例過高/連通元件破碎)。
  **真實20部件決策檔完整測試**(同chunk46使用者手動確認過的決策檔),**逐格人工視覺
  複核,不只信任聚合指標或自動heuristic**:9個明確正確(head/fox_ears/hair_front/
  choker/sleeve_left/tag_pendant/leg_right/boot_right/hand_left)、2個被自動heuristic
  正確標記low_confidence(earrings框過鬆/sash_train破碎)、2個是Claude第1/2點分析時
  已知本來就難的案例(hair_main/tails_mass同材質重疊)、**5個(25%)是自動heuristic
  完全沒抓到的靜默錯誤**(bodice選到頭髮、leg_left/boot_left選到布料裝飾、
  sleeve_right選到胸衣、hand_right選到袖子布料)。**共同失敗模式**:這5個案例的原始框
  都跟鄰近部件的視覺內容大幅重疊,SAM選到了「框裡另一個看起來也像獨立物件的鄰居」而非
  自己,且選錯後遮罩形狀通常乾淨、信心分數不低,前景比例跟破碎度兩個heuristic都測不出
  來。**誠實結論**:比GrabCut好非常多(3/3全錯 vs 9/20明確對+2/20正確攔截),證實
  「需要語意理解模型」判斷方向正確,**但不是解決方案,是進步**——25%靜默錯誤率意味著
  這個pipeline目前不能盲目信任自動輸出,每次都需要人工複核(這次示範的做法)。提出
  兩個未實作的改進方向留給使用者裁決是否投入:(a) SAM原生支援框+點提示組合,加一步
  「點選目標物件內部」很可能直接解決這5個歧義案例;(b) 收緊決策檔階段的框邊界,降低
  跟鄰居的重疊,不用改分割演算法本身。見 `knowledge/s4-sam-segment.md`、
  `log/s4-2026-09-04-047.md`。
- 2026-09-04:**拆解第3點正式落地:裁切工具+PSD組裝+使用者真實決策檔實測(chunk 46)**
  — 使用者裁示「排程上優先研究區塊一,達到一定技術水準後再進區塊二」,建
  `tools/mesh_gen/s4_decompose_cut.py`(讀決策檔→硬邊界矩形裁切各部件→輸出
  psd_slice.py相容manifest.json)+ `tools/mesh_gen/psd_node/`(獨立Node子套件,
  `manifest_to_psd.js`讀manifest+PNG用ag-psd組回.psd;node-canvas在此環境因缺
  pangocairo裝不起來,改查ag-psd型別定義發現Layer.imageData直接吃純像素陣列不需要
  真Canvas,換pngjs純JS解PNG)。**自驗閘經歷兩次真實失敗才收斂,完整誠實記錄診斷
  過程**:第一版直接照搬psd_slice.py的threshold,對九尾焰蓮測試素材(真實跑過
  assist viewer匯出的決策檔,20部件)兩項全部fail(重組MAE13/61,孤兒率24%);沒有
  直接調高threshold蒙混,先畫洋紅疊圖定位孤兒像素分布,根因確認是該素材
  `mode=RGB`完全沒有alpha通道(矩形面板裁圖,非去背角色)——孤兒檢查拿「alpha>8」當
  角色判準,對這種來源等於把整張畫布(含背景/標題文字)當角色內容,不是裁切邏輯錯,
  是套錯判準。**驗證修法本身有效**:改用robot_parts.psd(真alpha)的psd_slice.py
  ground-truth座標回歸測試,孤兒率精確0.0通過,證實邏輯本身沒問題。**兩次負對照**
  (拿掉部件重跑)找到工具真實限制:拿掉「身體」沒被抓到(因為「光暈」部件bbox幾乎
  蓋滿全圖,幾何涵蓋了身體區域,矩形裁切來源是同一張扁平圖導致的固有盲點);改拿掉
  涵蓋全圖的「光暈」本身才正確抓到(孤兒率4.18%,fail)——誠實記錄這個檢查只能抓
  「完全沒被任何框蓋到」的真空隙,抓不到「被另一個大框幾何涵蓋住的漏部件」。
  **最終版驗收邏輯**:AC1(部件數>0)硬性;AC2(重組落差)降級為資訊性,不擋
  overall_pass(矩形窗口邊緣柔化落差是設計本身接受的代價,呼應「邊緣允許破損」);
  AC3(孤兒)對幾乎全alpha=255的無意義去背來源自動skip並說明原因,只在真的有意義的
  alpha時才當硬性檢查。**端到端管線驗證**:九尾焰蓮20部件真實決策檔跑完整
  裁切→PSD組裝,像素級抽樣核對(head部件)完全相符,獨立psd-tools交叉驗證圖層
  數量/名稱/offset/size/像素內容全部精確匹配。**使用者接著提供自己用assist viewer
  調整過的真實決策檔**(對照可見真實調整:fox_ears/leg_right/sleeve_left/tails_mass
  座標都跟我方草稿不同),要求「讓我看看切完之後的成果」——這是六階段「使用者做最終
  邊界決策」第一次真實發生。跑完後**視覺逐格檢視20個裁出部件(不只看聚合指標)**,
  誠實發現:矩形裁切的bleed比「邊緣有點破損」嚴重得多——head框裝了大半標題文字
  (JIUWEI・YANLIAN)+部分狐耳,頭部本體只佔小半;earrings框幾乎整個是臉;choker框
  主要是裸露肩膀。這是有機、不規則、大範圍前後遮擋的角色插畫跟robot_parts那種方形
  機械部件的本質差異,**已超出使用者原本授權的「邊緣允許破損」範疇**,單靠第4點局部
  邊緣修補很可能不夠清理。**留給使用者裁決3個方向**:(a)接受現況靠加大第4點修補範圍
  硬做、(b)升級assist viewer支援不規則多邊形/筆刷選取取代矩形、(c)認清這類角色屬於
  「高複雜度人物」獨立課題,用更寬鬆標準分階段處理——未自行決定。見
  `knowledge/s4-decompose-cut-tool.md`、`log/s4-2026-09-04-046.md`。
- 2026-09-04:**研究分流:圖片切割 vs 圖片切片/圖層分解(chunk 45)** — 使用者裁示把
  「拆解」底下容易混為一談的兩種動作正式拆成兩個獨立研究區塊。**核心判斷**:切割是
  空間切分(部件本來就在畫面上並排/疊放,幾何裁切還原,原始像素資訊都還在,不需要
  無中生有),切片是訊號分離/反推(同一像素疊了多種效果,要拆開已經混合的東西),而
  切片內部又依「底下內容是否還留在畫面裡」分兩級難度。**區塊1(切割)**:確認沿用
  既有六階段第3點,不需另開新研究,使用者明確授權「邊緣允許破損」正式解除了裁切階段
  追求完美邊緣的壓力,把邊緣品質完全交給第4點GPT局部修補收尾。**區塊2(切片)**:
  新研究主題。**2a淺層**(物件/陰影/光源分離)提出具體CPU-first構想——對部件圖做
  顏色分群找出打底基準色,再用multiply/screen blend mode的反函數,從合成後像素+基準色
  反推陰影層/光源層各自的顏色與alpha,原理上不需要生成式模型;可行性評估中等信心,
  風險在「基準色分群」對厚塗漸層風格可能失敗,**尚未用真實素材驗證**。**2b深層**
  (遮擋物+底下被遮內容分離,如墨鏡下的眼睛)判定本質是「補全」不是「分解」——被遮
  的像素在原圖裡根本不存在,唯一路徑是生成式inpainting腦補,難度等同 CLAUDE.md
  提過的「情境2視角外推」;遮擋物本身的分離仍屬區塊1切割問題(語意分析+使用者框選
  即可),但底下內容補全雖然API呼叫模式跟candidate17(masked edit)相同,**mask
  用途完全不同**(candidate17已驗證的是小範圍邊緣延伸,這裡是遮擋物完整footprint的
  語意推理補全),明確標注不能直接沿用candidate17的可靠度結論。純研究筆記,零API
  花費零production代碼異動。**留4項待使用者裁示**:兩區塊優先序、跟六階段第3/4點的
  優先序、2a驗證需要已知分層的真實素材(有沒有現成的?)、2b目前是假設性需求(墨鏡是
  舉例)——是否有實際素材真的遇到這種情境,沒有的話建議先擱置(呼應candidate15的
  處理方式)。見 `knowledge/s4-cut-vs-slice-research-split.md`、
  `log/s4-2026-09-04-045.md`。
- 2026-09-04:**輔助拆圖viewer(六階段第6點)+PSD寫入路徑驗證(chunk 44)** — 使用者對
  chunk 43 提案的 part list JSON schema(`id`/`label`/`confidence`/`bbox_pct`/`notes`)
  回「可以 先試試看」,授權建第6點。新建 `tools/mesh_gen/s4_decompose_assist.html`(單檔
  純前端,~440行,零外部依賴):載入單張圖(拖曳/file input)→選填載入 Claude 建議JSON
  (依圖片尺寸把`bbox_pct`換算成像素框,套信心色:綠high/黃medium/紅low/藍
  user_confirmed,座標不完整的項目自動跳過)→ canvas 互動編輯(空白處拖曳畫新框、點框
  選取、拖曳內部移動、拖曳四角handle調整大小、Delete/Backspace刪除、Esc取消選取)→右側
  部件清單(即時同步,可點選/點×刪除,編輯面板改id/label/confidence/notes)→匯出決策檔
  JSON(`bbox_px`像素座標,供下游第3點直接裁切不用再換算)。**Playwright驗證**(用真實
  `jiuwei_yanlian_char_crop.png`460×898+對應20部件建議JSON,零API呼叫零花費):圖片
  載入正確、建議JSON換算正確(20/20套用,抽樣核對`bbox_pct`→`bbox_px`換算誤差在四捨
  五入範圍)、模擬滑鼠拖曳畫新框成功(20→21)、清單點選載入既有框資料正確、欄位編輯即時
  同步清單顯示、刪除鈕與鍵盤刪除都正確(21→20→19,鍵盤刪除前先點畫布轉移焦點驗證不會
  誤觸輸入框裡的Delete鍵)、匯出JSON結構正確(19部件,每個都有4元素合法`bbox_px`)。
  全程**零JS console error**。**順帶用 Playwright 關閉 chunk 43 留下的技術問題#2**
  (PSD寫入路徑未定):直接呼叫瀏覽器端 `ag-psd` 的 `writePsd({width,height,children:
  [{name,left,top,right,bottom,canvas}]}）`,產出2層(不同座標/顏色)測試PSD,獨立用
  Python `psd-tools`(非同一套函式庫)重新讀取交叉驗證——圖層名稱/bbox/像素顏色三項
  全部精確匹配。**結論**:`ag-psd` 讀寫能力都足夠,承擔第3點「裁切結果組回PSD」不需要
  另尋`pytoshop`等替代方案,這步不確定性已消除。**誠實限制**:這個viewer本身完全不做
  任何影像處理(不裁切/不生成/不呼叫API),只負責「使用者確認邊界」;框沒有防呆(允許
  超出畫布邊界/重疊,id重複已擋但其他無驗證);沒有undo機制(清空全部有二次確認,單一
  刪除沒有);只支援單張圖不支援直接讀PSD(來源是PSD要先用既有工具匯出composite);
  PSD寫入驗證只是2層100×100最小可行性測試,不是第3點完整實作。第3點(實際拆解+PSD組裝)
  跟第4點(GPT局部修補,可直接複用簡化後`s4_ai_viewer.html`不需新工具)**仍未開始**,
  等使用者用這個viewer對真實素材做出決策檔後再繼續。見
  `knowledge/s4-decompose-assist-viewer.md`、`log/s4-2026-09-04-044.md`。
- 2026-09-04:**拆解流程重新分階段(chunk 43)** — 承接 chunk 42 翅膀失敗案例,使用者裁示
  六階段重新設計:(1) Claude語意分析圖片(善用GenieLabs知識)(2) 列出認知部件/使用者
  框選範圍決定切點 (3) 執行拆解+PSD轉換+結果預覽 (4) 修飾階段才讓GPT參與,針對切割後
  邊緣破損局部修補 (5) viewer先移除切片/拆解/需求精靈,只留補圖 (6) 製作輔助拆圖viewer
  (使用者決策後產生檔案輔助Claude找拆解點,再丟回Claude實際拆解)。**核心思路**:把
  chunk 39/42 那種「AI一鍵重繪整張圖」的不可控設計拆開,語意理解交給Claude(vision,
  不需生成)、邊界決策交給使用者(尤其困難案例)、GPT縮回它已驗證可靠的用法(局部遮罩
  修補,呼應chunk35補圖案例)。**第5點已完成**:`s4_ai_viewer.html` 移除切片/拆解/需求
  精靈,僅留補圖(檔案載入+composite偽列+遮罩繪製+OpenAI呼叫+套用下載+用量記錄)。
  Playwright驗證:確認三項功能DOM元素已移除、既有補圖流程(含真實PSD載入)無回歸,零
  JS錯誤。**第1/2點現場示範**(零成本,不呼叫任何API):用 Claude 自己的視覺理解分析
  `assets/jiuwei_yanlian_char_crop.png`,套用GenieLabs「先辨識自然部件」思路,產出結構化
  part list JSON(id/label/confidence/bbox_pct/notes)——對清楚部件(頭/軀幹/四肢/配件)
  信心高;對困難部件(九尾狐尾同色重疊只能給整體範圍無法個別拆分/半透明寬袖/飄逸拖尾
  跟尾巴交疊)**誠實回報低信心+具體說明原因,不假裝有答案**——驗證了「用Claude語意理解
  取代生成式重繪做定位」這個方向初步可行。**尚未解決**:第6點輔助viewer的UI設計(載入→
  疊加建議框→使用者拖曳調整→匯出決策檔)、第3點PSD轉換的技術路徑(傾向用ag-psd的
  `writePsd`,尚未測試,`psd-tools`寫入能力有限)、第4點GPT局部修補的mask設計(可直接
  複用簡化後的補圖介面,不需另做)。**等待使用者確認part list格式/方向後再建第6點UI**,
  避免格式訂錯導致UI白做。見 `knowledge/s4-decompose-restage-plan.md`、
  `log/s4-2026-09-04-043.md`。
- 2026-09-04:**拆解功能真實失敗案例:預設prompt寫死人形假設,已修正(chunk 42)** —
  使用者用 viewer 拆解分頁對一對機械翅膀(對話貼圖,非 repo 素材)實測,真實付費呼叫
  **輸出完全不相干**——回傳一套黑色皮甲人形角色部件(臉/兜帽/胸甲/護臂/手套/靴子),
  跟翅膀毫無關係。從 session JSONL 復原輸入輸出兩張圖確認(同 chunk 41 的取檔手法)。
  **讀程式碼確診根因**:拆解分頁預設 prompt 寫死「separate the head, torso, arms, and
  legs/feet」,假設主體是人形角色——翅膀輸入沒有頭/軀幹/手臂/腿,文字描述跟實際圖片
  直接矛盾,加上拆解刻意用全域可編輯 mask(整張圖 100% 可重繪,無局部錨定),模型選擇
  跟著文字走、幾乎沒理會輸入圖。**明確是我寫的預設 prompt 只考慮人形角色情境的設計疏失,
  不是模型隨機失效**——同一 bug 對任何非人形主體(道具/動物/載具等)都會複現。**修正**:
  (1) 改寫預設 prompt 為主體無關通用版本,加入明確錨定語句(「Take the EXACT subject
  shown... do not invent, replace, or substitute it」),UI 加提示說明背景+新版本仍
  未驗證;(2) 順帶修正 size 下拉未依輸入長寬比自動建議的次要風險(新增
  `updateDecomposeSizeSuggestion()`,主素材變更時自動建議最接近長寬比的 size 選項)。
  Playwright 驗證:新 prompt 含錨定語句、三種長寬比正確觸發對應 size 建議、既有流程
  (mock API)無回歸,零 JS 錯誤。**誠實限制**:只驗證程式碼邏輯符合預期,**新 prompt
  本身尚未經真實付費呼叫重新驗證**,錨定語句能不能真的解決「跟著文字走」的傾向仍是合理
  推測非已證結論。提醒:候選17「拆解」與「補圖」呼叫模式完全不同(整張圖可編輯 vs 局部
  mask),可信度需獨立評估,不能用補圖那邊的正面結果類推拆解可靠。見
  `knowledge/s4-decompose-prompt-bug-wings-case.md`、`log/s4-2026-09-04-042.md`。
- 2026-09-04:**新測試素材:「九尾・焰蓮」角色設定圖,定調高複雜度人物轉spine課題
  (chunk 41)** — 使用者對話直接貼圖,要求「提取角色,分析後進行拆解」,並主動定調此圖
  對應課題方向是「高複雜度人物如何轉換成 spine」,跟既有素材(機器人拆件/Symbol_Ww)
  複雜度區隔。**取檔手法**:使用者透過對話貼圖(非給路徑/非上傳到可存取位置),這個
  排程容器沒有現成工具能把對話裡貼的圖存成檔案——`find` 找不到任何對應檔案。改掃 Claude
  Code session 的 JSONL 完整逐輪記錄(`~/.claude/projects/<repo>/<session-id>.jsonl`),
  寫小 Python 腳本遞迴找 `{"type":"image","source":{"type":"base64",...}}` 內容區塊、
  base64 解碼復原成檔案——成功找回這張圖(連同本 session 稍早我自己送給使用者的3張比較
  圖一併找到)。**這是可重用技巧**,記錄供未來同類情境參考。存檔
  `assets/jiuwei_yanlian_ref.webp`(1024×1536完整資料表)+
  `assets/jiuwei_yanlian_char_crop.png`(460×898,裁出角色主圖,座標0%,3%,45%,61.5%)。
  裁切用視覺疊代(裁一刀→Read看結果→調整,3輪收斂),曾嘗試 OpenCV Canny+輪廓自動偵測
  面板框線失敗(背景本身有暗紅漸層紋理,非乾淨留白,找不到穩定矩形)。**內容解析**:
  這不是單一角色插畫,是多面板角色設定資料表;最有價值的不是主圖本身——**三視圖**(正/
  側/背)直接回應既有「情境2視角外推」難題(不需生成式AI去猜背面/側面)、**表情設定**
  (6張)可直接支援 spine 常見的臉部 slot 切換表情做法。**難度評估**(肉眼判斷,未經任何
  實驗驗證):九尾狐尾顏色高度相近且大量重疊,是「同材質語意召回0」的教科書案例;長髮跟
  尾巴同色系交疊範圍大;雙臂白紗寬袖是半透明材質,傳統像素歸屬判定不可靠——三者都是既有
  測試素材沒真正遇過的複雜度。**本次只完成取檔+裁圖,未進行任何拆解實驗**(不論候選17
  生成式重繪或其他方法),未新增量化實驗、未改動 production 代碼。見
  `knowledge/s4-highcomplexity-charsheet-jiuweiyanlian.md`、`log/s4-2026-09-04-041.md`。
- 2026-09-04:**viewer v3:統一主素材架構(chunk 40)** — 使用者要求補圖/切片/拆解對焦到
  同一份已載入檔案(「不要各別載入」)。v2 的拆解分頁有自己獨立的 file picker,跟左側
  圖層清單無關,是要改掉的問題。重構:單一「主素材」面板(`mainCanvas`+`maskCanvas`)
  持續顯示、跨模式共用;`setMainAsset(img, name, isComposite)` 是唯一狀態寫入點(點圖層
  清單/composite偽列/補圖套用結果都走這裡);拆解拿掉 `#decomposeInput`,送出按鈕直接讀
  `mainImg`;新增「◆整體(composite)」偽圖層列(PSD/manifest 含 composite.png 時),載入
  後自動選取。**寫測試過程抓到一個真實 bug**:遮罩畫布(`#maskCanvas`)原本只在「切換到
  補圖模式」的點擊事件裡才被 JS 加上 `.active`(pointer-events 生效),但補圖是頁面載入
  時的預設模式,從未觸發那個事件——結果剛載入頁面時遮罩畫不出來(肉眼看畫面正常,只是
  滑鼠事件被吃掉,若不寫自動化互動測試很可能不會發現)。已修正(`#maskCanvas` HTML 直接
  帶初始 `class="active"`)並重新驗證。**5 組 Playwright 測試全過**(單張PNG自動成為主
  素材/遮罩繪製修bug後正確算出28.7%涵蓋率+mock補圖+套用後主素材正確更新/真實PSD載入後
  composite偽列自動選取+切圖層+切模式不重置主素材+切回composite/拆解確認無獨立upload
  元素+直接用主素材送出+合成圖精確偵測3部件+用量記錄跨模式累積2筆/需求精靈跳轉),全程
  mock 真實付費 API,零 JS console error。見 `knowledge/s4-ai-viewer-v3-unified.md`、
  `log/s4-2026-09-04-040.md`。
- 2026-09-04:**viewer v2:補上切片/拆解/需求精靈(chunk 39)** — 使用者要求 viewer 補上
  拆圖能力(當時只有補圖)。決定在主線 `s4_ai_viewer.html` 上直接擴充成 4 分頁,不另開
  新檔(既有補圖邏輯 `callOpenAiEdit()` 抽成共用函式,新分頁直接複用)。**切片**:沿用
  chunk 37 已驗證的 ag-psd 解析(同一套 CDN fallback+遞迴攤平),拖 .psd 原檔即可在瀏覽器
  端列出圖層、composite 預覽、逐層下載 PNG,不需伺服器/Python(定位是快速預覽/單獨抽取,
  不取代 `psd_slice.py` 完整 manifest pipeline)。**拆解(實驗性)**:萃取自 chunk 38 讀到
  的 GenieLabs `split_character.py` 思路(獨立重新實作,不抄程式碼——授權限制):呼叫
  gpt-image-2(mask 用全域可編輯的空白 canvas)把平面角色圖重繪成「部件分離、留白、白底」
  版面,再用瀏覽器端 8-connected components(BFS 陣列佇列,避免遞迴爆疊)分割成獨立部件,
  UI 明確標示「未在真實素材驗證過」+沿用該專案自己承認的限制(無命名/無z-order/無座標
  映射回原圖)。**需求精靈**:對照 `spine-asset-request/SKILL.md` 決策表(A/B/C/D,新增
  E類「完全沒分層平圖」)做成可點選介面,規則式判斷不呼叫 AI 不花錢,選情境給建議+一鍵
  跳轉分頁。**驗證**:Playwright 5 組互動測試(tab切換、補圖流程回歸確認擴充沒壞既有功能、
  真實 `robot_parts.psd` 切片正確顯示5圖層、**合成測試圖〔3個獨立色塊〕驗證分割演算法精確
  偵測出3個部件**、需求精靈跳轉),全程 mock 真實付費 API(CDN 用 `npm pack` vendor 副本、
  OpenAI 呼叫用假回應),零 JS console error。**誠實限制**:拆解功能的核心假設(生成式
  重繪能否解決平圖拆件)完全未經真實付費 API 呼叫驗證,只驗證了分割演算法本身邏輯正確;
  需求精靈是規則表非真正的智慧規劃(若要自然語言理解+規劃需要接 LLM 推理,是另一個量級的
  工作,本次未做);切片下載的單一 PNG 不含 manifest 結構化資訊,不能直接餵給既有 Python
  pipeline。見 `knowledge/s4-ai-viewer-v2-slicing.md`、`log/s4-2026-09-04-039.md`。
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
