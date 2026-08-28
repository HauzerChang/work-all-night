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
1. **遮擋真值法**:用 Award/機器人多件疊合 composite,找已知被上層遮住、但 PSD 該層本身有畫全的真實
   區域當真值(比合成挖洞更貼近實戰);對照合成挖洞閘的判定是否一致。
2. **1b 的 edge 模式支援**:目前 edge 模式標「不適用」;可嘗試比對「這個材質沿真實輪廓其他段落的
   天然 tone/alpha 變化範圍」當基準(而非整個件的內部區域),看能否收斂出可信判定。
4. **探測 Level 3(LaMa)**:深度 inpaint 權重下載是否被網路政策擋?先探測可行性(注意:1b 已經解決
   了機械紋理 interior 案例的實用性問題,LaMa 現在的優先序降低,除非要解 1a 或 edge 模式)。
5. **修正 `fill_cv2_inpaint` 的 edge 模式 alpha 處理**:目前洞區強制設不透明,與柔和邊緣真值 alpha
   漸縮不符(`alpha_mae` 28~42)→ 應改為對 alpha 也跑 inpaint 或用距離場漸縮。
6. 用本閘測 `Symbol_Ww.psd` 其他層(icon 類,可能有更多平面色塊),擴大樣本、交叉驗證邊界。
7. **1b 閾值反向校準**:目前 1b 閾值靠正負對照的數值分野訂定,理想上應收集人工「這樣補看起來有沒有
   穿幫」的標註來反過來校準,目前這步驟還沒做(見 `s4-inpaint-1b-lenient-gate.md` 誠實界定)。

## 未解問題 / 阻塞 (open questions / blockers)

- ❓ LaMa 等深度 inpaint 權重下載是否被網路政策擋?(第 3 級才需要;已用 CPU 1–2 級量化出明確需要升級的案例)
- ❓ 補圖真值來源:目前用「合成挖洞」自造(已完成校準);「遮擋真值法」(候選 1)待驗證是否與合成挖洞判定一致。

## 進度摘要 (progress log)

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
