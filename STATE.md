# 進度狀態 (STATE) — 續跑核心

> 每次 session 結束前**必須**更新此檔。

## 專案狀態

`ACTIVE`  <!-- SETUP / ACTIVE / BLOCKED / DONE -->

## 目前階段

**專案三階段：第 2 階段(用工具鍛鍊四能力)。**
- 第 1 階段(可視化工具)已完成 → `spine_inspector.html`(含 `window.spineTool` API)。
- **S3 mesh 生成器：完成且對 4 個真實 mesh 收斂達標**(v2 strip 通用,見 `knowledge/s3-four-mesh-generalization.md`)。
- **S2 評估器套件:四評估器全到位(里程碑,2026-07-01)** — 切圖 `evaluate_slicing.py`、
  mesh `evaluate_mesh`+`deform_eval`、**骨架 `evaluate_skeleton.py`**、**補圖 `evaluate_inpaint.py`**。
  骨架閘正對照 main_draw+Award+gen 全過(先驗揪出並修 clipping 誤判);補圖閘補圖能力梯三態可分(作升級決策)。
  「每能力必配評估器」的自主收斂樞紐完成。見 `knowledge/s2-skeleton-inpaint-gates.md`、`s2-slicing-evaluator.md`。
- **S4 PSD-first 切圖:已對真實生產檔驗收通過(里程碑)** — `psd_slice.py` 對 2 份真實 PSD
  (`Symbol_Ww` 18件 / `robot_parts` 機器人 5件)切圖無損 PASS;機器人 5 圖層 ⇄ 真實 spine `Award` 的
  slot `機器人拆件/<圖層名>` 逐件吻合(+2px padding)。閘經 premultiplied 校正(透明區白底假性失敗)。
  見 `knowledge/s4-psd-to-spine-real.md`、`s4-psd-contract.md`(已用真實檔校準)。
- **S3×S4 端到端(里程碑,2026-07-01):對真實生產 mesh 驗收通過** — `validate_award_mesh.py`
  對 Award「機器人拆件」3 個 mesh(光暈/左手/身體)做藝術家真值覆蓋率對照:**生成 mesh 覆蓋率
  達到/超過藝術家且頂點更少**(3 件 overall_pass,exit 0)。釐清兩種 regime(weighted+無 deform
  →覆蓋率保真/v1 Delaunay/UV 拓樸;unweighted+有 deform→位移場轉移/v2 strip)。
  通則:覆蓋率由邊界 epsilon 決定、內部頂點不影響(呼應 strip 的 rows)。見 `knowledge/s3-award-mesh-endtoend.md`。
- **S4 SkelToJson(里程碑,2026-07-01):件→完整 skeleton JSON 打通** — `skel_to_json.py` 把「切件+生 mesh」
  組裝成可載入的完整 Spine 3.8 skeleton JSON。對真實 `robot_parts.psd` 產出**結構與 Award 逐 slot 吻合**
  (4 AC 全過:schema / loader-roundtrip / layout / Award-parity,exit 0)。**pipeline 三段串通**:
  psd_slice → generate_mesh → skel_to_json。尚缺骨架權重/綁定(=S5)、動畫。見 `knowledge/s4-skel-to-json.md`。
- **S5 骨架半自動:可自動部分落地(2026-07-01)** — `rig_draft.py` 由件 alpha 重疊自動推合法骨架階層
  + 關節 pivot 草案,世界版面保真,過 `evaluate_skeleton`。待人:root 確認 / pivot 微調 / mesh 權重綁定(BBW)。
  見 `knowledge/s5-rig-draft.md`。
- **auto-epsilon 已沉澱進 `generate_mesh.generate_auto`**(單一真相來源;skel_to_json/validate_award_mesh 共用)。
- **S1 反推分析器:啟動(2026-07-01,使用者提供影片)** — benchmark 影片 `assets/robot_dance.mp4`
  (chibi 機器人舞蹈,864×496/24fps/97幀)。塊1 `tools/s1/motion_field.py`(Farneback 光流)定位動態前景
  + 偵測律動(3 AC 全過):背景靜(corner/center 0.0001)、手臂/拳頭主動、頭中等、軀幹/腿穩;
  誠實發現垂直幅度(21.9px)>水平(5.9px)。見 `knowledge/s1-motion-field.md`。tools/s1 已入 PYTHONPATH(hook)。

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
1. ~~PSD件→S3 mesh→對照 Award 真實 mesh~~ **✅ 完成** — `validate_award_mesh.py`。
2. ~~切圖→Spine JSON 組裝(SkelToJson)~~ **✅ 完成** — `skel_to_json.py`。
3. ~~auto-epsilon 沉澱進 generate_mesh~~ **✅ 完成** — `generate_auto`。
4. ~~S2 骨架閘 / 補圖閘~~ **✅ 完成** — `evaluate_skeleton.py` / `evaluate_inpaint.py`(S2 四評估器全到位)。
5. ~~S5 骨架階層草案(可自動部分)~~ **✅ 完成** — `rig_draft.py`(pivot/root/權重待人)。

新的下一步候選:
A. **S5 weighted mesh 綁定(BBW)**:把 unweighted mesh + rig_draft 骨架接成 weighted mesh
   (bone×頂點權重,和=1)。純 CPU(BBW/heat 權重);用 `evaluate_skeleton` AC3 驗權重合法 →
   S5 剩餘可自動部分。之後 pivot 微調待人(A 類)。
B. **🅰 里程碑審查(建議找使用者)**:pipeline 已從「PSD → 件 → mesh → 完整 skeleton JSON → 骨架階層草案」
   全串通並對真實 Award 驗收;S2 四評估器到位。**S5 的 root/pivot 是 A 類岔路,需使用者拍板**;
   S1 需影片資產。→ 適合做一次里程碑審查 + 要 S1 的 benchmark 影片。
C. **S1 反推分析器**:需一支 benchmark 影片(repo 無影片資產)→ 需使用者提供。
D. ~~spine_inspector 實機 round-trip~~:**⛔ CDN(jsDelivr)被政策擋;需使用者改政策或離線 spine-webgl。**

> 第 2 階段(四能力鍛鍊 + 評估器)大致收斂:S3 mesh ✅、S4 切圖+組裝 ✅、S2 四閘 ✅、S5 自動部分 ✅。
> 續跑可做 (A) BBW 權重綁定(最後的純自動塊);之後卡在需人拍板的 pivot(A 類)與需影片的 S1。
> **建議下次或本輪末做一次里程碑審查(B),把 A 類決策與 S1 影片需求一次批次化給使用者。**

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
- 2026-07-01:**S3×S4 端到端對真實生產 mesh 驗收(里程碑)** — 新 `validate_award_mesh.py`:對 Award 機器人
  3 mesh(光暈/左手/身體)做藝術家真值覆蓋率對照。生成 mesh 覆蓋率**達到/超過藝術家且頂點更少**
  (左手 53v/0.976>80v/0.968、身體 68v/0.983>98v/0.976、光暈 68v/0.978≈78v/0.980),3 件 overall_pass。
  釐清兩種 mesh regime(weighted+無 deform→覆蓋率/v1;unweighted+有 deform→位移場轉移/v2 strip);
  發現覆蓋率由邊界 epsilon 決定(內部頂點不影響),柔邊件需更細 epsilon → 內建 AC 驅動 auto-epsilon 搜尋。
  評估器自我校驗(藝術家拓樸乾淨)+ 負對照(縮15%→0.72、移8%→0.70、打亂拓樸→si 數千)確認鑑別力。
- 2026-07-01:**S4 SkelToJson:件→完整 skeleton JSON 打通(里程碑)** — 新 `skel_to_json.py`:PSD→切件→
  生 mesh/region→組裝完整 Spine 3.8 skeleton JSON。對 `robot_parts.psd` 產出結構**與 Award 逐 slot 吻合**
  (5/5 slot:命名 `機器人拆件/<層>`、mesh/region 型別、尺寸 ±2px 全對),4 AC 全過(schema/loader-
  roundtrip/layout/Award-parity),用讀真實資產同一 loader 重載確認。發現:namespace 前綴是 authoring
  選擇(Award=中文群名 機器人拆件 ≠ 檔名 robot_parts)→ 做成可覆寫參數。pipeline 三段串通;缺 rig(=S5)。
