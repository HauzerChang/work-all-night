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
- **S3×S4 端到端對照 Award 藝術家 mesh:通過(里程碑,2026-07-06)** — 機器人 PSD 3 mesh 件
  (光暈/身體/左手)切件 → `generate_mesh_v2` → 對 Award 藝術家真實 mesh 做同一 alpha 覆蓋 IoU,
  **3/3 PASS 且生成 mesh 覆蓋 ≥ 藝術家、頂點只約一半**(見 `knowledge/s3-award-mesh-compare.md`)。
  校正生成器:v1 加 `drop_orphans`(移孤兒頂點)+ 預設 epsilon 0.008→0.004(覆蓋由 hull 密度決定,
  頂點預算優先給邊界)。釐清定位:**v1 細-hull=靜態/骨骼件、v2 strip=逐頂點 deform 件**。
  副產:確認 Spine JSON mesh uvs 本就 region 局部 0..1(不需 atlas UV 轉換,推翻 STATE 舊註記)。
- S1 / S5 尚未開始。

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

下一個 bounded chunk 候選:
1. ✅ **已完成(2026-07-06):PSD件→S3 mesh→對照 Award 真實 mesh**(3/3 PASS,見上)。
2. **❗最高優先:切圖→Spine JSON 組裝(SkelToJson)**。把已驗證的慣例固化成工具,端到端產 Spine JSON:
   slot 命名 `<PSD名>/<圖層名>`、+2px atlas padding、mesh vs region 分配(是否 warp)、atlas 0.70 縮放、
   mesh 用 `generate_mesh_v2`(有機件細 hull / deform 件 strip)。輸出可被 spine_inspector 載入的完整 JSON。
   驗收:對 robot_parts 產出的 JSON 之 slot/attachment/size 對齊 Award ground truth。
3. **S2 補圖閘 / 骨架閘**(補齊 S2 樞紐;純 CPU)。
4. **S1 反推分析器**:需一支 benchmark 影片(repo 無影片資產)。
5. ~~spine_inspector 實機 round-trip~~:**⛔ CDN(jsDelivr)被網路政策擋(403);需使用者改政策或提供離線 spine-webgl。**

> S3(對真實藝術家 mesh)+ S4(PSD 切圖)皆已對真實生產檔驗收通過。建議下一步:把兩者的慣例
> 固化成「PSD → Spine JSON」組裝工具(SkelToJson),完成端到端產線;之後補 S2 補圖/骨架閘。

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
- 2026-06-26:**S4 真實驗收(里程碑)** — 使用者提供 2 份生產 PSD + 機器人對應 spine(Award)。
  psd_slice 對兩檔切圖無損 PASS;機器人 5 圖層 ⇄ Award slot `機器人拆件/<圖層名>` 逐件吻合(+2px)。
  抓修閘第三次 miscalibration(composite 透明區白底 → 改 premultiplied 比對 + 套圖層 opacity)。
  收 Award.json/atlas + 2 PSD 進 assets;校準契約。
- 2026-06-26:**texture 級驗證 + atlas_crop 修正(里程碑)** — 收到 Award.png/Award2.png(雙頁,~0.70 縮小)。
  PSD 切件 ↔ atlas 切件 alpha-IoU 0.92~0.99 → 確認同素材,PSD↔spine↔atlas 閉環。
  **用 PSD 外部真值揪出 atlas_crop derotate 方向 bug(CCW→CW),被 round-trip 自洽掩蓋**;
  升級 atlas_crop 多頁 + 修方向 + 修 evaluate_slicing.repack;main_draw 4 mesh + slicing 重驗全過(rotate=false 不受影響)。
