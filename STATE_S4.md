# S4 進度狀態 (STATE_S4) — 補圖/切圖獨立排程續跑核心

> 本檔僅供 **S4 專屬排程** 使用(分支 `claude/spine-s4-inpainting`)。主排程請看 `STATE.md`。
> 每次 S4 session 結束前**必須**更新此檔。冷啟動背景見 `handoff_S4.md`,執行指令見 `prompts/run_s4.md`。

## 專案狀態

`ACTIVE`  <!-- SETUP / ACTIVE / BLOCKED / DONE -->

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

**下一個有界工作塊候選(擇一推進):**
4. **探測 Level 3(LaMa)**:深度 inpaint 權重下載是否被網路政策擋?先探測可行性(注意:1b 已經解決
   了機械紋理 interior 案例的實用性問題,LaMa 現在的優先序降低,除非要解 1a 或 edge 模式)。
6. 用本閘測 `Symbol_Ww.psd` 其他層(icon 類,可能有更多平面色塊),擴大樣本、交叉驗證邊界。
7. **1b 閾值反向校準**:目前 1b 閾值靠正負對照的數值分野訂定,理想上應收集人工「這樣補看起來有沒有
   穿幫」的標註來反過來校準,目前這步驟還沒做(見 `s4-inpaint-1b-lenient-gate.md` 誠實界定)。
9. ✅ 已完成(見下方 chunk 11)——延伸候選:Symbol_Ww 沒有多層互相遮擋的真實案例可用,若要
   把「真實遮擋洞」方法論覆核 `框`/`臉部陰影`,需另找/另造有真實重疊的分層素材。
10. **光暈材質 1a 邊界再校準**:候選 1 發現「光暈 CPU 補得動」的結論隱含「小面積圓形洞」前提,
    大面積/不規則真實遮擋形狀下 `seam_grad_diff` 會超標(1b 仍 pass)。可考慮:(a) 對光滑漸層
    材質額外測合成挖洞在更大面積/非圓形狀下的 1a 表現,量化出真正的邊界;(b) 或直接接受
    「光暈這類材質的驗收線也該用 1b,而非 1a」,呼應候選 8/候選 1 一致的結論方向。

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

## 未解問題 / 阻塞 (open questions / blockers)

- ❓ LaMa 等深度 inpaint 權重下載是否被網路政策擋?(第 3 級才需要;已用 CPU 1–2 級量化出明確需要升級的案例)
- ❓ 補圖真值來源:目前用「合成挖洞」自造(已完成校準);「遮擋真值法」(候選 1)待驗證是否與合成挖洞判定一致。

## 進度摘要 (progress log)

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
