# 進度狀態 (STATE) — 續跑核心

> 每次 session 結束前**必須**更新此檔。

## 專案狀態

`ACTIVE`  <!-- SETUP / ACTIVE / BLOCKED / DONE -->

## 目前階段

**專案三階段：第 2 階段(用工具鍛鍊四能力)。**
- 第 1 階段(可視化工具)已完成 → `spine_inspector.html`(含 `window.spineTool` API)。
- 能力路線圖 S1–S5 皆未開始。

## 下一步動作 (next action)

> 建議第一個動手的能力：**S3 mesh 生成器**(純 CPU、收益最大、能立即拆掉「新建 mesh 需 Spine editor」限制)。
> 但其自主迭代需要評估器(S2)，所以第一個 bounded chunk 先做「S3 的評估器 + 拓樸原型」的最小版本。

1. **定 AC**：為 S3 mesh 生成器寫可量測的驗收目標
   (例：對 `curtain_left` 的來源區域重建 mesh，在極端 deform 幀 0 自交、輪廓 IoU ≥ 門檻、頂點數 ≤ 預算)。
2. **最小原型**：用 `cv2.findContours` → Douglas-Peucker → (多通道 Canny 內部邊界放點) → Delaunay，
   對一張遮罩產出三角網格;先不做 BBW 權重(unweighted 即可，對應 main_draw 全為 unweighted)。
3. **接評估器**:三角形重心在 mask 內過濾、自交檢查、輪廓比對。寫成可重跑腳本。
4. **驗證**:把生成的 mesh 寫進 Spine JSON 格式,用 `spine_inspector.html` 的 `setMeshVertices`/
   `getMeshBounds`/`screenshot` 自我驗收。
5. 結果寫進 `knowledge/`,更新本檔與 `log/`。

> ⚠️ 環境前置:需確認排程 session 能否安裝/使用 `opencv-python`、`triangle`、`numpy` 等
> (純 CPU 套件)。第一次執行先做環境探測,若無法安裝則記錄為 BLOCKED 並回報。

## 未解問題 / 阻塞 (open questions / blockers)

- ❓ 排程頻率未定(使用者尚未決定)。
- ❓ 貼圖/PMA 完整視覺驗證需 `main_draw.png`(目前僅在使用者端,未進 repo)。
- ❓ 切圖/補圖(S4)最大槓桿是「能否要到分層 PSD」— 屬使用者層級決策。
- ⛔(待第一次執行確認)排程環境的 Python CPU 套件可用性。

## 進度摘要 (progress log)

- 2026-06-24：建立自驅研究框架骨架(RULES/PLAN/STATE/knowledge/log/prompts)。
- 2026-06-24：匯入「Spine mesh system analysis」完整交接 — `spine_inspector.html`、`CLAUDE.md`、
  `handoff_brief.md`、`自主Spine工作流_SOP.md`、`Spine能力鍛鍊計畫.md`、`main_draw_解析報告.md`;
  PLAN/RULES/STATE 依實際研究內容填妥,狀態轉 `ACTIVE`。
