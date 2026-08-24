# 進度狀態 (STATE) — 續跑核心

> 每次 session 結束前**必須**更新此檔。

## 專案狀態

`ACTIVE`  <!-- SETUP / ACTIVE / BLOCKED / DONE -->

## 目前階段

**專案三階段：第 2 階段(用工具鍛鍊四能力)。**
- 第 1 階段(可視化工具)已完成 → `spine_inspector.html`(含 `window.spineTool` API)。
- **S3 mesh 生成器：完成且對 4 個真實 mesh 收斂達標**(v2 strip 通用,見 `knowledge/s3-four-mesh-generalization.md`)。
- **S2 評估器套件:切圖閘已完成** — `evaluate_slicing.py`,main_draw 45/45 region 重組 MAE=0/0孤兒/0重疊,
  雙向負對照確認鑑別力(見 `knowledge/s2-slicing-evaluator.md`)。S2 尚缺:補圖閘、骨架閘。
- **S4 PSD-first 切圖:已對真實生產檔驗收通過(里程碑)** — `psd_slice.py` 對 2 份真實 PSD
  (`Symbol_Ww` 18件 / `robot_parts` 機器人 5件)切圖無損 PASS;機器人 5 圖層 ⇄ 真實 spine `Award` 的
  slot `機器人拆件/<圖層名>` 逐件吻合(+2px padding)。閘經 premultiplied 校正(透明區白底假性失敗)。
  見 `knowledge/s4-psd-to-spine-real.md`、`s4-psd-contract.md`(已用真實檔校準)。
- **S3 端到端對真實美術 mesh 驗收(里程碑,2026-08-19)** — `compare_robot_mesh.py` 對 Award
  機器人 3 mesh 件(光暈/左手/身體)生成 mesh,同 region 框內靜態覆蓋率 IoU **3 件全 PASS**
  (達美術基準 −0.03 內、0 孤兒),且頂點更省(37~48 vs 美術 78~98)。發現 **mesh uvs 是 region-local**;
  新增 `boundary-dense-v1` 軟邊 blob 模式(光暈 0.92→0.98)+ 通用 `prune_orphans`。
  ⚠️ 限制:weighted mesh 骨骼變形平滑度未驗(靜態 IoU 不涵蓋)。見 `knowledge/s3-robot-mesh-vs-award.md`。
- **S1 目標圖反推分析器:首個原型 + 真值驗收(里程碑,2026-08-19,使用者新增研究項目)** —
  `tools/analyzer/analyze_target.py`(分層 PSD → 五段規格:運動構件/周邊特效/動作分鏡/拆圖策略/補圖項目)
  + `validate_analyzer_award.py`(對 `robot_parts.psd ⇄ Award` 真值)**5 項校驗全 PASS**
  (件召回 1.0、特效 5/5、幾何無 mismatch、分鏡 In/Loop/Out+4 檔位全中、露出 4/4)。
  誠實界定:補圖需求**輸入契約相依**(分層 PSD 0 封閉破洞);#3 分鏡為類型先驗提案。見 `knowledge/s1-target-image-analyzer.md`。
- **S1 擴充:平圖流程 + 分鏡先驗庫(2026-08-19,使用者指定)** —
  (A) `segment_flat.py`+`validate_flat_recall.py`:平圖純 CPU 自動拆件 baseline;壓平 PSD 對真值召回顯示
  同材質/重疊角色 **0/5、0/18 語意召回**,僅「不相連塊」可靠(正對照 3/3)→ 佐證 PSD-first。
  (B) `genre_priors.py`+`validate_priors.py`:先驗庫 `slot_bigwin`(Award)、`slot_reveal`(main_draw)
  覆蓋率皆 **1.0** + 2 未驗證類型。修 2 bug(decomposability 反向、動畫名子字串誤判)。
  見 `knowledge/s1-flat-pipeline-and-priors.md`。
- **S3 weighted mesh 骨骼變形驗收(里程碑,2026-08-24)—補上唯一未驗維度** —
  新建 `spine_skeleton.py`(Spine 3.8 骨架 FK + weighted 蒙皮)+ `weighted_deform_eval.py`
  (**可見性 gating** 變形評估器)+ `generate_weighted_mesh.py`(拓樸+內部密度+BBW 代理權重)+
  `validate_weighted_gen.py`(整合閘)。評估器經生產美術 mesh 校準 `_checker_validated=True`
  + 負對照 3702 自交(有鑑別力);我方生成 3 件(左手/身體/光暈)在真實動畫骨 pose 下
  **AC-W1 變形拓樸全乾淨(0 自交/0 翻面)**。**校正舊假設**:這 3 件其實**有** bone 變形動畫
  (`Award_Legend_In`/`_Loop`)。**雷點 #2/#3 實證**:光暈爆開折疊發生在 slot alpha=0 不可見幀 →
  變形閘必須先過 attachment+alpha gating。誠實限制:骨集合用真值、權重為 inverse-distance 代理、
  AC-W2(CV)為弱代理(嚴格閘是 AC-W1)。見 `knowledge/s3-weighted-mesh-deform.md`。
- **S1 端到端「目標圖→可載入 Spine 素材」打通(里程碑,2026-08-19)** —
  `build_spine.py`(analyze_target+psd_slice+generate_mesh_v2 → Spine 3.8 json+atlas+png)+
  `validate_build.py`(round-trip 重建 setup pose == 原 PSD composite)。robot(5件)/Symbol_Ww(18件)
  **全 PASS**(premult MAE 0.03/0.24、0 孤兒、0 未解析 attachment)。mesh/region 分派沿用分析器建議。
  誠實界定:只驗靜態幾何/貼圖編碼;動畫 keyframe / mesh 變形 / 關節 pivot 屬後續。見 `knowledge/s1-build-spine-end-to-end.md`。
- S5 尚未開始。

## 真實資產(已收進 `assets/`)

- `assets/main_draw.json`(真實骨架:28 bones / 40 slots / 9 anims / 4 unweighted mesh)。
- `assets/main_draw.atlas`(region 矩形;sheet `main_draw.png` 2023×1896)。
- **`assets/Symbol_Ww.psd`**(symbol,180×180,18 圖層)、**`assets/robot_parts.psd`**(機器人拆件 big win,713×693,5 圖層)。
- **`assets/Award.json` + `assets/Award.atlas` + `assets/Award.png`(2040²)+ `assets/Award2.png`(1780×1376)**
  (機器人對應的生產 spine,77 bones/47 slots/12 anims,雙頁 atlas;貼圖被縮小 ~0.70 打包)。
- ⚠️ **`main_draw.png` 像素檔尚缺**(只在對話中顯示,未存成檔)。像素級工作(裁切貼圖、
  texture IoU、實機截圖)在拿到該 PNG 前 BLOCKED;但 **deform 幾何分析不需要 PNG**。

## 下一步動作 (next action)

**S3 已推廣到全部 4 個 mesh(里程碑,2026-06-26)**:整合 AC 跑 curtain_left/right + shadow/shadow2。
- **v1(散點 Delaunay)不通用**:靜態 IoU 高但 curtain_right(19 si)/shadow(64 si)真實 deform 自交。
- **v2(strip)通用**:4 mesh 全 deform 乾淨;`rows=10,cols=3`(30v)IoU 全過藝術家基準 → 設為 v2 預設。
- 關鍵副產:**IoU 由 rows 決定、cols 不影響覆蓋率**;評估器先以藝術家真值自一致性(4 mesh si=0)確認可信。
- 詳見 `knowledge/s3-four-mesh-generalization.md`。標準指令 `validate_against_real.py --gen v2` 對 4 mesh 全 overall_pass。

**使用者新增研究方向(2026-08-24):動畫律動「各部位時間差」(overlapping action / 慣性)** —
利用各部位移動時間差(相位延遲 + 末梢過衝/回穩,阻尼彈簧慣性)讓律動鮮活,對治「全身同步紙板感/待機僵硬」。
**已在 Award_Legend_Loop 真實資產量測到時間差**(大腿鏈谷底 0.5→0.6→0.667、末梢落後 lag +0.083s、通道解耦、特效錯拍)。
併入候選 0d(分鏡→keyframe):生成呼吸 loop 時套用時間差模型 + 相位延遲剖面評估器。
見 `knowledge/anim-overlapping-action-timing-offset.md`。

下一個 bounded chunk 候選:
0. **S1 分析器接續**:(a) ~~規格 → 實際素材~~ ✅ 完成(`build_spine.py`+`validate_build.py`,round-trip 全 PASS);
   (b) ~~平圖流程~~ ✅ baseline 完成(CPU 到頂,升級需 GPU 語意分層,屬資源決策);
   (c) ~~分鏡先驗庫~~ ✅ 2 類型已驗證;續補需**有真值**的類型 spine。
   **下一個最高優先**:(d) **分鏡 → 動畫 keyframe**:把 #3 storyboard(尤其 Loop 呼吸)轉成 Spine `animations`
   timeline,讓產出的素材「會動」;可用 spine_inspector 或幾何量化(bone 位移/旋轉範圍)自驗。純 CPU 可自驅。
   **⭐併入使用者新增方向:各部位「時間差」(overlapping action / 慣性)** —— 生成時對每骨套用相位延遲
   (τ∝骨鏈深度)+ 末梢過衝/回穩(阻尼彈簧),避免全身同步的紙板感;用相位延遲剖面評估器對 Award loop
   對照(已量測到真實時間差為真值基準)。見 `knowledge/anim-overlapping-action-timing-offset.md`。
   (e) 關節 pivot 推斷(件中心→相鄰件關節),供 S5。
1. ~~PSD件→S3 mesh→對照 Award 真實 mesh~~ **✅ 已完成(2026-08-19,見上)**。3 件靜態覆蓋率全 PASS。
2. ~~S3 weighted mesh + 內部取樣密度 + BBW 權重~~ **✅ 已完成(2026-08-24,見上里程碑)**。
   變形拓樸 AC-W1 全 PASS;補上「weighted mesh 骨骼變形」這唯一未驗維度。
   **後續(此塊的延伸,非最高優先)**:(a) 真 BBW(離散拉普拉斯/有界雙調和)取代 inverse-distance 代理;
   (b) 把 weighted mesh 接回 `build_spine.py`(目前只輸出 region/unweighted);
   (c) 更嚴格變形平滑度指標(相鄰頂點 Jacobian 變異)取代 AC-W2 弱代理。
3. **切圖→Spine JSON 組裝(SkelToJson)**:把 `機器人拆件/<圖層名>` 命名慣例 + size+2px padding +
   atlas 0.70 縮放固化成「件→Spine attachment」工具,端到端產可載入 Spine JSON。
4. **S2 補圖閘 / 骨架閘**(補齊 S2 樞紐;純 CPU)。
5. **S1 反推分析器**:需一支 benchmark 影片(repo 無影片資產)。
6. ~~spine_inspector 實機 round-trip~~:**⛔ CDN(jsDelivr)被網路政策擋(403);需使用者改政策或提供離線 spine-webgl。**

> S3 已端到端串通並對真實生產美術 mesh 驗收(靜態 IoU + **weighted 骨骼變形拓樸**兩層級皆過)。
> **建議下一步:候選 0d(分鏡→動畫 keyframe,讓 build_spine 產出「會動」的素材)** 為最高槓桿的下一塊
> (純 CPU 可自驅,用 spine_skeleton 幾何量化自驗);或候選 2 延伸(真 BBW / 把 weighted 接回 build_spine)。

## 環境前置(已驗證可用)

- 排程容器為臨時,CPU 套件需每次重裝。**已確認可裝**:numpy 2.4.6 / opencv-python-headless 4.13.0 /
  triangle / scipy 1.17.1(見 `requirements.txt`)。
- 每次排程執行前先 `pip install -r requirements.txt`。

## 未解問題 / 阻塞 (open questions / blockers)

- ❓ 排程頻率未定(使用者尚未決定)。
- ✅ `main_draw.png`(2023×1896,含 alpha)已收進 `assets/`;texture/IoU 已解鎖。atlas 切圖工具見 `tools/mesh_gen/atlas_crop.py`。
- ❓ 切圖/補圖(S4)最大槓桿是「能否要到分層 PSD」— 屬使用者層級決策。
- ℹ️ spine_inspector 實機 round-trip 需瀏覽器自動化(headless),尚未設置。

## 進度摘要 (progress log)

- 2026-06-24：建立自驅研究框架骨架(RULES/PLAN/STATE/knowledge/log/prompts)。
- 2026-06-24：匯入「Spine mesh system analysis」完整交接;PLAN/RULES/STATE 依實際研究內容填妥,狀態轉 `ACTIVE`。
- 2026-06-24：**S3 第一輪** — 探測並安裝 CPU 套件;完成 mesh 生成器 + 評估器 + 合成測試;6 條 AC 全過(IoU 0.99)。
- 2026-06-24:收到真實 `main_draw.json` + `.atlas`(存入 `assets/`);解析確認 4 mesh + 9 anim deform;
  下一課題定為 deform-aware 評估器(純 CPU,不需 PNG)。
- 2026-06-24:**deform 評估器課題完成** — Python 重現 Spine deform;真實 4mesh×9anim benchmark 全乾淨
  (_checker_validated);負對照可抓自交/翻面;生成 mesh 耐變形 ≈ 藝術家手做(撐過 315px)。
- 2026-06-24:**真實資產驗證(里程碑)** — 收到 main_draw.png;atlas_crop 切真實貼圖;生成 mesh 靜態 IoU 0.98 過
  但耐變形失敗 → 發現「靜態≠變形穩健」,藝術家直條拓樸更耐變形。下一步定為 S3 v2 deform-aware 生成器。
- 2026-06-24:**S3 驗證 + 自我更正** — 真實位移場轉移評估器(自一致性驗證);推翻先前『耐變形失敗』
  (合成壓力 miscalibration);更正後 v1 對 curtain_left 整合 AC 通過(IoU 0.98、真實變形乾淨)。
- 2026-06-24:**排程就緒(B)** — 建 SessionStart hook(.claude/,自動裝 CPU 套件+PYTHONPATH,已驗證)、
  硬化 prompts/run.md、寫 SCHEDULE.md turnkey 指南。剩使用者在 web 建每日 trigger。
- 2026-06-26:**S3 推廣到全部 4 mesh(里程碑)** — v1 不通用(curtain_right/shadow 真實 deform 自交);
  v2 strip 通用(4 mesh 全乾淨)。發現 IoU 由 rows 決定、cols 不影響;v2 預設 rows 8→10,4 mesh 全 overall_pass。
  評估器先以藝術家真值自一致性(4 mesh si=0)確認可信再下判定。開 PR #1(zealous→hopeful default,a 方案)。
- 2026-06-26:**S2 切圖閘完成** — `evaluate_slicing.py` 端到端重組驗證;main_draw 45/45 region MAE=0/0孤兒/0重疊;
  雙向負對照確認鑑別力(rotate 對稱 region 不可區分為已知局限)。發現 spine_inspector round-trip 被 CDN 政策擋(blocker)。
- 2026-06-26:**S4 PSD 契約 pipeline 打通(使用者拍板)** — psd-tools 可裝;`make_test_psd.py`(合成 fixture)+
  `psd_slice.py`(PSD→各部位件+manifest+自驗閘);4 層 PSD 重組 MAE=0.01/0孤兒,漏層負對照抓到。
  寫 `knowledge/s4-psd-contract.md`(給美術的交檔規範)。待真實 PSD 驗收。
- 2026-06-26:**分支策略定案** — 排程 trigger 改**直接指向開發分支 `claude/zealous-noether-y2ecwu`**,
  不再走 PR/merge(零摩擦)。更新 `prompts/run.md`(分支說明 + 移除過時快照,改以 STATE 為準)、`SCHEDULE.md`。
  PR #1 已 merge;PR #2 關閉(改用分支直讀)。
- 2026-08-19:**S1 端到端「目標圖→可載入 Spine 素材」(里程碑)** — `build_spine.py`+`validate_build.py`;
  robot/Symbol_Ww round-trip 重建 == 原圖 全 PASS。規格→素材打通。下一步定為分鏡→動畫 keyframe。
- 2026-08-19:**S1 擴充:平圖流程 + 分鏡先驗庫(使用者指定)** — (A) 平圖純 CPU 拆件 baseline + 真值召回閘
  (同材質角色 0/5、0/18 語意召回,僅不相連塊可靠 → 佐證 PSD-first);(B) 先驗庫 slot_bigwin/slot_reveal
  對 Award/main_draw 覆蓋率 1.0。修 2 評估器 bug(decomposability 反向、動畫名子字串誤判)。
- 2026-08-24:**使用者新增研究方向:動畫律動「各部位時間差」** — overlapping action / 慣性(阻尼彈簧模型)。
  用 spine_skeleton FK 在 Award_Legend_Loop **量測到真實時間差**(大腿鏈谷底 0.5→0.6→0.667、末梢落後
  lag +0.083s、通道解耦、特效錯拍)。寫 `knowledge/anim-overlapping-action-timing-offset.md`(含生成模型 +
  評估器構想);併入候選 0d。
- 2026-08-24:**S3 weighted mesh 骨骼變形驗收(里程碑)** — 補上唯一未驗維度。建 Spine 3.8 骨架 FK+蒙皮
  (`spine_skeleton.py`)+ 可見性 gating 變形評估器(`weighted_deform_eval.py`)+ weighted 生成器
  (`generate_weighted_mesh.py`)+ 整合閘(`validate_weighted_gen.py`)。評估器經美術 mesh 校準
  (`_checker_validated=True`)+ 負對照(3702 自交)驗鑑別力;生成 3 件真實動畫骨 pose 下 AC-W1 全乾淨。
  **校正舊假設**:這 3 件其實有 bone 變形動畫(Legend_In/Loop)。**雷點 #2/#3 實證**:光暈折疊在 alpha=0
  不可見幀 → 變形閘須先過 attachment+alpha gating。
- 2026-08-19:**S1 目標圖反推分析器(里程碑,使用者新增研究項目)** — 分層 PSD → 五段規格
  (運動構件/周邊特效/動作分鏡/拆圖策略/補圖項目);`tools/analyzer/` + 對 Award 真值 5 項校驗全 PASS
  (件召回 1.0)。誠實界定補圖需求為輸入契約相依(分層 PSD 0 破洞)、#3 分鏡為類型先驗提案。
- 2026-08-19:**S3 端到端對真實美術 mesh 驗收(里程碑)** — `compare_robot_mesh.py`:Award 機器人
  3 mesh 件靜態覆蓋率全 PASS(頂點更省 37~48 vs 78~98)。校正 STATE 舊假設:**mesh uvs 是 region-local**
  (非 atlas 分數,4 組合實測 vflip=False)。新增軟邊 blob `boundary-dense-v1` 模式(光暈 0.92→0.98)+
  通用 `prune_orphans`(修 filter 造孤兒)。4 curtain/shadow strip 迴歸全 PASS。誠實限制:weighted 骨骼
  變形平滑度未驗 → 下一步定為 S3 weighted+BBW。見 `knowledge/s3-robot-mesh-vs-award.md`。
- 2026-06-26:**S4 真實驗收(里程碑)** — 使用者提供 2 份生產 PSD + 機器人對應 spine(Award)。
  psd_slice 對兩檔切圖無損 PASS;機器人 5 圖層 ⇄ Award slot `機器人拆件/<圖層名>` 逐件吻合(+2px)。
  抓修閘第三次 miscalibration(composite 透明區白底 → 改 premultiplied 比對 + 套圖層 opacity)。
  收 Award.json/atlas + 2 PSD 進 assets;校準契約。
- 2026-06-26:**texture 級驗證 + atlas_crop 修正(里程碑)** — 收到 Award.png/Award2.png(雙頁,~0.70 縮小)。
  PSD 切件 ↔ atlas 切件 alpha-IoU 0.92~0.99 → 確認同素材,PSD↔spine↔atlas 閉環。
  **用 PSD 外部真值揪出 atlas_crop derotate 方向 bug(CCW→CW),被 round-trip 自洽掩蓋**;
  升級 atlas_crop 多頁 + 修方向 + 修 evaluate_slicing.repack;main_draw 4 mesh + slicing 重驗全過(rotate=false 不受影響)。
