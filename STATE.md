# 進度狀態 (STATE) — 續跑核心

> 每次 session 結束前**必須**更新此檔。

## 專案狀態

`ACTIVE`  <!-- SETUP / ACTIVE / BLOCKED / DONE -->

## 目前階段

**專案三階段：第 2 階段(用工具鍛鍊四能力)。**
- 第 1 階段(可視化工具)已完成 → `spine_inspector.html`(含 `window.spineTool` API)。
- **S3 mesh 生成器：完成且對 4 個真實 mesh 收斂達標**(v2 strip 通用,見 `knowledge/s3-four-mesh-generalization.md`)。
- **S2 評估器套件:四閘齊備(里程碑,2026-07-03)** — 切圖閘 `evaluate_slicing`、mesh 閘
  `evaluate_mesh`+`deform_eval`、**補圖閘 `evaluate_inpaint`**(真實遮擋自監督 benchmark 校準,
  正對照全過、黑洞/平色/噪聲全抓;cv2 級補繪實測只夠平滑件 → 量化證實降階鏈)、
  **骨架閘 `evaluate_skeleton`**(結構+pivot 空間關聯,main_draw 98.6%/Award 100%/生成 robot 100% 過,
  強負對照全抓)。見 `knowledge/s2-inpaint-evaluator.md`、`s2-skeleton-evaluator.md`。
- **S4 PSD-first 切圖:已對真實生產檔驗收通過(里程碑)** — `psd_slice.py` 對 2 份真實 PSD
  (`Symbol_Ww` 18件 / `robot_parts` 機器人 5件)切圖無損 PASS;機器人 5 圖層 ⇄ 真實 spine `Award` 的
  slot `機器人拆件/<圖層名>` 逐件吻合(+2px padding)。閘經 premultiplied 校正(透明區白底假性失敗)。
  見 `knowledge/s4-psd-to-spine-real.md`、`s4-psd-contract.md`(已用真實檔校準)。
- **S3×S4 端到端串接:對真實生產標的 Award 驗收通過(里程碑,2026-07-03)** —
  `validate_psd_to_mesh.py`:robot_parts.psd 的 3 個 mesh 件(光暈/身體/左手)→ `generate_mesh_v2`
  → 對照 Award 真實藝術家 mesh,**靜態覆蓋率 IoU ≥ 藝術家**(光暈 0.964/身體 0.966/左手 0.980,
  藝術家 0.949/0.948/0.977),格式閘全過,`overall_pass` 全 True。
  關鍵:①Award 件為 **weighted+無 deform timeline** → 變形靠骨/權重,**變形閘 N/A**(需 BBW,S3 後續);
  ②`epsilon_frac` 由外形複雜度決定,加入**覆蓋率驅動的 epsilon 細化**(≤4 輪)自動收斂到藝術家基準;
  ③修生成器**凹形件內部孤兒頂點 bug**(`generate_mesh.prune_orphans`,hull 順序不變)。
  見 `knowledge/s3-psd-to-award.md`。
- **S4 下游組裝:PSD → 完整可載入 Spine 資產(里程碑,2026-07-03)** —
  `skel_to_json.py`(件→Spine 3.8 JSON,setup pose=PSD 平面佈局)+ `pack_atlas.py`(件→.atlas+PNG sheet)。
  對 robot_parts 端到端產出 `robot.json`+`robot.atlas`+`robot.png`,多重自驗全過:
  位置解析式 round-trip **0px** / 結構有效 / mesh 格式閘 / **光柵重建 MAE 0.031(視覺完美還原機器人)**;
  atlas 用真實-atlas 讀取碼(`atlas_crop.extract`)裁回 **MAE 0**;JSON↔atlas region/size 全一致。
  ⚠️ 誠實邊界:**未在 Spine runtime 實載**(CDN 擋、無 headless loader);rotation=0 平面 setup(綁定屬 S5)。
  見 `knowledge/s4-skel-to-json.md`。
- **S5 骨架草案:起步即對真值收斂(里程碑,2026-07-03)** — `skeleton_draft.py`(件重疊分析 →
  effect/trunk/limb 角色 + trunk 優先階層 + 關節=重疊質心 pivot)+ `skel_to_json --draft`(階層化
  組裝,佈局不變 0.001px/光柵 0.031)+ `validate_draft_vs_award.py`(對 Award 藝術家骨架:
  **拓樸完全一致、可比 pivot 全在 6.9% 件對角線內**,頭 4.3px)。骨架閘全過。
  A 類留人:effect 件(光暈)場景錨、pivot 手感微調。見 `knowledge/s5-skeleton-draft.md`。
- S1 尚未開始。

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
1. ~~PSD件→S3 mesh→對照 Award 真實 mesh~~ **✅ 已完成(2026-07-03)**。
2. ~~切圖→Spine JSON 組裝 + atlas 打包~~ **✅ 已完成(2026-07-03):完整資產閉環**。
3. ~~S2 補圖閘 / 骨架閘~~ **✅ 已完成(2026-07-03):S2 四閘齊備**。
4. ~~S5 骨架草案起步~~ **✅ 已完成(2026-07-03):拓樸全中、pivot ≤6.9% 對角線**。
5. **❗最高優先(純 CPU 可自驅):weighted mesh + BBW 權重**。骨架草案已有 → 對草案骨架算
   Bounded Biharmonic Weights(或 heat/inverse-distance 起步),把 unweighted mesh 升級 weighted,
   使件能隨骨動 → 用 deform 幾何閘(自交/翻面)+ 對 Award weighted 真值(78/80/98v 權重分佈)驗。
   這是 S3 最後一塊,也是「能動起來」的前置。
6. **完整資產 Spine runtime 實載驗**:需**離線 spine-webgl** 或 headless 瀏覽器(CDN 被網路政策擋)
   → 屬環境/使用者層級決策(A 類:提供離線 runtime 或放行 CDN)。
7. **S1 反推分析器**:需一支 benchmark 影片(repo 無影片資產)。
8. **多資產推廣**:skeleton_draft 啟發式僅在 robot 一個 GT 校準;Symbol_Ww(18 層)可當第二測試
   (無骨架 GT,但可過閘 + 人審)。

> S5 草案 + S2 四閘後,pipeline 只剩「權重(BBW)」就能從靜態資產走到「可動資產」。
> 建議下一步走 5(BBW);6/7 待使用者解鎖。

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
- 2026-07-03:**S3×S4 端到端串接對 Award 驗收(里程碑)** — `validate_psd_to_mesh.py`:robot_parts.psd
  3 mesh 件→`generate_mesh_v2`→對 Award 真實 mesh,覆蓋率全 ≥ 藝術家、格式全過、overall_pass 全 True。
  發現 Award 件 weighted+無 deform → 變形閘 N/A(需 BBW);epsilon 由外形決定→加覆蓋率驅動細化;
  修生成器凹形孤兒頂點 bug(`prune_orphans`)。main_draw 3 deform mesh + slicing 回歸全過。
- 2026-07-03:**S5 骨架草案起步即收斂(里程碑)** — skeleton_draft(重疊分析→角色/階層/pivot)
  對 Award 藝術家真值:拓樸完全一致、pivot 頭 4.3px(0.027)/全件 ≤0.069 對角線。兩個失敗驅動的
  設計:trunk 優先規則(防 z 交叉假邊:劍從臉前過→頭誤掛手)、無序 pair key 要 sorted(左手被誤判孤島)。
  skel_to_json 支援 --draft(階層化、佈局不變);修 eval 對 offset mesh 的影像框推定。全回歸 11 項 PASS。
- 2026-07-03:**S2 四閘齊備(里程碑)** — 補圖閘:真實遮擋自監督 benchmark(robot_parts 圖層互遮+
  美術畫全層當真值)校準;兩次 miscalibration 當場被正對照抓出(AC3 下限誤殺平滑內容→僅上限;
  遠參考帶 seam 不穩→局部化,意外解鎖 GT-free 抓平色填充);Laplacian 分噪聲/細節(Sobel 分不開)。
  骨架閘:setup 世界變換(含 weighted mesh)+ d_norm 空間關聯(0.5/95%,兩真實骨架分佈校準);
  **關鍵發現:負對照必須 rebind**(bone-relative 幾何不變性)。三骨架 selftest 全 PASS,全套回歸 PASS。
- 2026-07-03:**PSD→完整 Spine 資產閉環(里程碑,一個工作天)** — `skel_to_json.py`(件→Spine 3.8 JSON,
  setup=PSD 佈局;4 AC 全過:位置 0px/結構/mesh 格式/光柵重建 MAE 0.031 且視覺完美)+ `pack_atlas.py`
  (件→.atlas+PNG,用真實-atlas 讀取碼裁回 MAE 0)。完整資產 robot.json+atlas+png 一致。
  修位置 AC 初版誤用 mesh 頂點外接框(→改量影像框,0px)。誠實邊界:未 runtime 實載(CDN 擋)、rotation=0 平面 setup。
- 2026-06-26:**texture 級驗證 + atlas_crop 修正(里程碑)** — 收到 Award.png/Award2.png(雙頁,~0.70 縮小)。
  PSD 切件 ↔ atlas 切件 alpha-IoU 0.92~0.99 → 確認同素材,PSD↔spine↔atlas 閉環。
  **用 PSD 外部真值揪出 atlas_crop derotate 方向 bug(CCW→CW),被 round-trip 自洽掩蓋**;
  升級 atlas_crop 多頁 + 修方向 + 修 evaluate_slicing.repack;main_draw 4 mesh + slicing 重驗全過(rotate=false 不受影響)。
