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
- S1 / S4 / S5 尚未開始。

## 真實資產(已收進 `assets/`)

- `assets/main_draw.json`(真實骨架:28 bones / 40 slots / 9 anims / 4 unweighted mesh)。
- `assets/main_draw.atlas`(region 矩形;sheet `main_draw.png` 2023×1896)。
- ⚠️ **`main_draw.png` 像素檔尚缺**(只在對話中顯示,未存成檔)。像素級工作(裁切貼圖、
  texture IoU、實機截圖)在拿到該 PNG 前 BLOCKED;但 **deform 幾何分析不需要 PNG**。

## 下一步動作 (next action)

**S3 已推廣到全部 4 個 mesh(里程碑,2026-06-26)**:整合 AC 跑 curtain_left/right + shadow/shadow2。
- **v1(散點 Delaunay)不通用**:靜態 IoU 高但 curtain_right(19 si)/shadow(64 si)真實 deform 自交。
- **v2(strip)通用**:4 mesh 全 deform 乾淨;`rows=10,cols=3`(30v)IoU 全過藝術家基準 → 設為 v2 預設。
- 關鍵副產:**IoU 由 rows 決定、cols 不影響覆蓋率**;評估器先以藝術家真值自一致性(4 mesh si=0)確認可信。
- 詳見 `knowledge/s3-four-mesh-generalization.md`。標準指令 `validate_against_real.py --gen v2` 對 4 mesh 全 overall_pass。

**已完成(2026-06-29,使用者指派後由主線 session 做掉)**:
- ✅ review 優化 a:v2 自適應 rows(`rows="auto"`,shadow 30→18v 省頂點)+ 軟邊件 alpha 加權 IoU。
- ✅ blocker b:純 CPU `render_mesh.py` 取代 inspector 實機 round-trip(setup MAE≈0、deform 無撕裂)。

**→ 後續交由排程接管。** 排程下一個 bounded chunk(依槓桿,優先做不需使用者輸入的純 CPU 項):

1. **【建議先做】S2 補圖閘(inpaint evaluator)** — 承切圖閘,補齊 S2 評估器套件樞紐。純 CPU、不需新資產:
   可對 main_draw region 合成遮擋(挖洞)→ 用分級補圖(cv2.inpaint Telea/NS)→ 評估還原度(極端姿態露出區 0 破洞)。
2. **S2 骨架閘** — 對每根骨單獨旋轉、驗 pivot 是否合理(可用 main_draw 既有骨架當真值)。
3. **S4 切圖能力本體** — 已有 `evaluate_slicing.py` 當收斂目標;❗最大關卡「能否要到分層 PSD」屬**使用者層級決策**(未定,排程遇此標 BLOCKED 待人)。
4. **S1 反推分析器** — 需一支 benchmark 影片當輸入;repo 目前**無影片資產**(排程遇此標 BLOCKED 待人提供)。

> 心法提醒(寫給排程的你):每塊都先定 AC、評估器先自驗(藝術家真值/負對照)再下判定、誠實記錄、
> push 回 default。需使用者決策的(3 PSD / 4 影片)直接標 BLOCKED 並停,不要硬做。

## 環境前置(已驗證可用)

- 排程容器為臨時,CPU 套件需每次重裝。**已確認可裝**:numpy 2.4.6 / opencv-python-headless 4.13.0 /
  triangle / scipy 1.17.1(見 `requirements.txt`)。
- 每次排程執行前先 `pip install -r requirements.txt`。

## 未解問題 / 阻塞 (open questions / blockers)

- ❓ 排程頻率未定(使用者尚未決定)。
- ✅ `main_draw.png`(2023×1896,含 alpha)已收進 `assets/`;texture/IoU 已解鎖。atlas 切圖工具見 `tools/mesh_gen/atlas_crop.py`。
- ❓ 切圖/補圖(S4)最大槓桿是「能否要到分層 PSD」— 屬使用者層級決策。
- ✅ spine_inspector 實機 round-trip 已用純 CPU `render_mesh.py` 取代(離線、可自動化)。互動式 HTML 離線化屬使用者選配。

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
- 2026-06-24:產出**通用自驅排程引導手冊** `docs/自驅排程引導手冊.md` + skill `setup-autonomous-schedule`
  (教他人從零設定自己的排程;含架構、前置、Routine 建立、驗證、疑難排解、範本)。
- 2026-06-29:**review 優化 a 完成** — v2 自適應 rows(shadow 30→18v 省頂點)+ 軟邊件 alpha 加權 IoU
  (解決軟陰影硬 IoU 失真);4 mesh 全過、deform si=0。接著做 (b) spine_inspector CDN blocker。
- 2026-06-29:**(b) CDN blocker 解決** — 查證 jsDelivr/esotericsoftware 403、npm 僅 4.x 不相容 3.8;
  改寫純 CPU `render_mesh.py`(貼圖網格渲染,setup round-trip MAE 2.7/0.66、deform 無撕裂)取代 inspector 實機驗證。
  **review 優化 a + blocker b 皆完成 → 後續交由排程接管。**
