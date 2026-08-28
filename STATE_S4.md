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

## 下一步動作 (next action)

**下一個有界工作塊候選(擇一推進):**
1. **遮擋真值法**:用 Award/機器人多件疊合 composite,找已知被上層遮住、但 PSD 該層本身有畫全的真實
   區域當真值(比合成挖洞更貼近實戰);對照合成挖洞閘的判定是否一致。
2. **探測 Level 3(LaMa)**:深度 inpaint 權重下載是否被網路政策擋?先探測可行性,若可裝則對「CPU 補不動」
   的身體/左手案例跑一輪,量化 Level 3 能否補救。
3. **修正 `fill_cv2_inpaint` 的 edge 模式 alpha 處理**:目前洞區強制設不透明,與柔和邊緣真值 alpha
   漸縮不符(`alpha_mae` 28~42)→ 應改為對 alpha 也跑 inpaint 或用距離場漸縮。
4. 用本閘測 `Symbol_Ww.psd` 其他層(icon 類,可能有更多平面色塊),擴大「CPU 補得動」樣本、交叉驗證邊界。

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
