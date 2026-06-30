# 進度狀態 (STATE) — 續跑核心

> 每次 session 結束前**必須**更新此檔。

## 專案狀態

`ACTIVE`  <!-- SETUP / ACTIVE / BLOCKED / DONE -->

## 目前階段

**專案三階段：第 2 階段(用工具鍛鍊四能力)。**
- 第 1 階段(可視化工具)已完成 → `spine_inspector.html`(含 `window.spineTool` API)。
- **S3 mesh 生成器：完成且對 4 個真實 mesh 收斂達標**(v2 strip 通用,見 `knowledge/s3-four-mesh-generalization.md`)。
- **S3 推廣到 blob 型真實 mesh(里程碑,2026-06-30)** — 端到端 **PSD→件→S3→對照 Award 生產 mesh**:
  光暈/身體/左手 3 件(v2-auto→v1 Delaunay)全過藝術家覆蓋率基準且頂點數 ≤ 藝術家。發現
  **邊界密度 `epsilon_frac` 是 blob 的 IoU 槓桿**(對應 strip 的 rows);v1 預設 0.008→**0.002**。
  負對照(粗化 eps=0.012 全 FAIL)+ 真值自一致性(0.968~0.980)確認閘可信;改細未傷 deform。
  ⚠️ Award mesh 無 deform timeline(骨權變形)→ 只測靜態覆蓋率,bone-weighted 變形屬 S5。
  工具 `tools/mesh_gen/validate_award_mesh.py`;見 `knowledge/s3-blob-generalization-award.md`。
- **S2 評估器套件:切圖閘已完成** — `evaluate_slicing.py`,main_draw 45/45 region 重組 MAE=0/0孤兒/0重疊,
  雙向負對照確認鑑別力(見 `knowledge/s2-slicing-evaluator.md`)。S2 尚缺:補圖閘、骨架閘。
- **S4 PSD-first 切圖:已對真實生產檔驗收通過(里程碑)** — `psd_slice.py` 對 2 份真實 PSD
  (`Symbol_Ww` 18件 / `robot_parts` 機器人 5件)切圖無損 PASS;機器人 5 圖層 ⇄ 真實 spine `Award` 的
  slot `機器人拆件/<圖層名>` 逐件吻合(+2px padding)。閘經 premultiplied 校正(透明區白底假性失敗)。
  見 `knowledge/s4-psd-to-spine-real.md`、`s4-psd-contract.md`(已用真實檔校準)。
- **SkelToJson 件→可載入 Spine 資產集:完成(里程碑,2026-06-30)** — `skel_to_json.py` 把切件 manifest
  組裝成 `<name>.json+.atlas+.png` 整組,固化 Award 慣例(命名/一件一 bone 置中/draw order/`--mesh` 走 S3/
  shelf atlas +2px padding 無損)。2 份真實 PSD(robot 5件/symbol 18件)端到端 **5 條 AC 全過**,
  切回 alpha-IoU=1.0。產出為**中性骨架**(unweighted/無動畫);配權與 pivot 屬 S5。見 `knowledge/s4-skel-to-json.md`。
- **自動配權(bone-distance heat):完成(里程碑,2026-06-30)** — `auto_weight.py` 把 unweighted mesh +
  沿主軸自動骨鏈配成 weighted mesh(inverse-distance + top-K + 沿 mesh 邊 Laplacian 平滑)。2 真實衍生
  mesh(curtain strip 3骨/robot blob 2骨)彎折 60° 掃描 **0 自交/0 翻面**;真值自一致性(Award 7 件
  weighted 權重和=1)+ 負對照(k=1 硬指派下 AC3 失敗)確認閘有鑑別力。確定性純 CPU(非 BBW)。
  見 `knowledge/s5-auto-weight.md`。**未做**:分叉骨架/pivot(S5 核心,人微調)、寫回 SkelToJson。
- S1 尚未開始。S3+S4 已串成端到端「PSD→件→(mesh)→Spine JSON」;S5 配權已能讓 mesh 被骨鏈驅動。

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
1. ~~PSD件→S3 mesh→對照 Award 真實 mesh~~ **✅ 完成(2026-06-30)**。
2. ~~SkelToJson(件→Spine JSON 組裝)~~ **✅ 完成(2026-06-30,見上里程碑)**。
3. ~~自動配權(bone-distance heat)~~ **✅ 完成(2026-06-30,見上里程碑)**。
4. **❗最高優先:把 auto_weight 寫回 SkelToJson(端到端閉環)**。把 `auto_weight` 產的 weighted
   vertices 寫進 skin、並在 skeleton 的 bones 陣列加入骨鏈(取代該件的單一置中 bone),draw order/命名不變。
   端到端產「PSD→件→S3 mesh→自動配權→**可骨驅** Spine JSON」;自驗:沿用 skel_to_json 的結構/
   round-trip AC + auto_weight 的 partition/deform AC,並確認 weighted mesh 的 boneIdx 對得上新 bones 陣列。
5. **S2 補圖閘 / 骨架閘**(補齊 S2 樞紐;純 CPU)。
6. **S1 反推分析器**:需一支 benchmark 影片(repo 無影片資產)。
7. **BBW 精度升級**(bone-distance heat → biharmonic)、**分叉骨架/pivot**(S5 核心,需人微調)。
8. ~~spine_inspector 實機 round-trip~~:**⛔ CDN(jsDelivr)被網路政策擋(403);需離線 spine-webgl。**

> S3+S4+S5(配權)三件都有了:PSD→件→mesh→配權各自驗收通過。
> 建議下一步:把它們**寫回 SkelToJson 串成一條可骨驅 Spine JSON 的閉環**(候選 4)。

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
- 2026-06-30:**自動配權完成(里程碑)** — `auto_weight.py` unweighted mesh + 沿主軸自動骨鏈 →
  weighted mesh(inverse-distance + top-K + 沿邊 Laplacian 平滑)。2 真實衍生 mesh(curtain strip/robot blob)
  彎折 60° 0 自交/0 翻面;真值自一致性(Award 7 件權重和=1)+ 負對照(k=1 硬指派失敗)確認閘可信。
  確定性純 CPU(非 BBW)。下一步:寫回 SkelToJson 成可骨驅閉環。
- 2026-06-30:**SkelToJson 完成(里程碑)** — `skel_to_json.py` 件→可載入 Spine 整組(json+atlas+png);
  固化 Award 慣例(命名/一件一 bone 置中/draw order/`--mesh` 走 S3/shelf atlas +2px 無損)。
  2 份真實 PSD(robot 5件/symbol 18件)端到端 5 AC 全過,切回 alpha-IoU=1.0。產出為中性骨架
  (unweighted/無動畫),配權與 pivot 屬 S5。S3+S4 至此串成端到端。下一步:自動配權。
- 2026-06-30:**S3 推廣到 blob 型真實 mesh(里程碑)** — 端到端 PSD→件→S3→對照 Award 生產 mesh;
  光暈/身體/左手 3 件 v2-auto→v1 Delaunay 全過藝術家覆蓋率基準(頂點數 ≤ 藝術家)。發現邊界密度
  `epsilon_frac` 是 blob 的 IoU 槓桿(對應 strip rows);v1 預設 0.008→0.002。負對照+真值自一致性確認
  閘可信,改細未傷 deform(curtain_left si=0/flips=0)。新增 `validate_award_mesh.py`。
  ⚠️ Award mesh 無 deform timeline(骨權變形)→ 只測靜態,bone-weighted 變形屬 S5。
- 2026-06-26:**texture 級驗證 + atlas_crop 修正(里程碑)** — 收到 Award.png/Award2.png(雙頁,~0.70 縮小)。
  PSD 切件 ↔ atlas 切件 alpha-IoU 0.92~0.99 → 確認同素材,PSD↔spine↔atlas 閉環。
  **用 PSD 外部真值揪出 atlas_crop derotate 方向 bug(CCW→CW),被 round-trip 自洽掩蓋**;
  升級 atlas_crop 多頁 + 修方向 + 修 evaluate_slicing.repack;main_draw 4 mesh + slicing 重驗全過(rotate=false 不受影響)。
