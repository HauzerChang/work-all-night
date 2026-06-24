# 進度狀態 (STATE) — 續跑核心

> 每次 session 結束前**必須**更新此檔。

## 專案狀態

`ACTIVE`  <!-- SETUP / ACTIVE / BLOCKED / DONE -->

## 目前階段

**專案三階段：第 2 階段(用工具鍛鍊四能力)。**
- 第 1 階段(可視化工具)已完成 → `spine_inspector.html`(含 `window.spineTool` API)。
- **S3 mesh 生成器：最小原型 + 評估器已完成,合成資料 6 條 AC 全過**
  (見 `tools/mesh_gen/`、`knowledge/s3-mesh-generator.md`)。
- S1 / S2(其他能力評估器)/ S4 / S5 尚未開始。

## 真實資產(已收進 `assets/`)

- `assets/main_draw.json`(真實骨架:28 bones / 40 slots / 9 anims / 4 unweighted mesh)。
- `assets/main_draw.atlas`(region 矩形;sheet `main_draw.png` 2023×1896)。
- ⚠️ **`main_draw.png` 像素檔尚缺**(只在對話中顯示,未存成檔)。像素級工作(裁切貼圖、
  texture IoU、實機截圖)在拿到該 PNG 前 BLOCKED;但 **deform 幾何分析不需要 PNG**。

## 下一步動作 (next action) — 下一個課題

**課題:deform-aware mesh 評估器 + 用真實 main_draw 當 benchmark**(純 CPU,不需 PNG)

1. **用 Python 實作 Spine deform**:setup `vertices` + 每幀 `deform.offset/vertices` → 該幀 mesh 形狀
   (unweighted 直接逐頂點加 offset;對照 CLAUDE.md 雷點 #4 的同步 re-pose 數學)。
2. **真實 mesh 的 deform 行為量化**:對 9 支動畫逐幀計算 `curtain_left/right`、`shadow/shadow2` 的
   變形後幾何,檢查 **自交(邊交叉)/ 三角翻面(winding 變號=撕裂)/ 面積比 / 包圍盒**。
   → 這建立「藝術家手做 mesh 在 deform 下長怎樣」的 benchmark(鍛鍊五件套的 benchmark + 評估器)。
3. **把它變成 S3 生成器的閘**:生成的 mesh 必須在等效 deform 壓力下 0 自交 / 0 翻面。
4. 結果寫進 `knowledge/`,更新 STATE / log。

> 後續(待 `main_draw.png`):texture IoU 對真實貼圖、`spine_inspector` 實機 round-trip 截圖。

## 環境前置(已驗證可用)

- 排程容器為臨時,CPU 套件需每次重裝。**已確認可裝**:numpy 2.4.6 / opencv-python-headless 4.13.0 /
  triangle / scipy 1.17.1(見 `requirements.txt`)。
- 每次排程執行前先 `pip install -r requirements.txt`。

## 未解問題 / 阻塞 (open questions / blockers)

- ❓ 排程頻率未定(使用者尚未決定)。
- ❓ `main_draw.png` 像素檔尚缺(對話顯示過但未存成檔)→ texture/IoU/實機截圖 BLOCKED;deform 幾何不受影響。
- ❓ 切圖/補圖(S4)最大槓桿是「能否要到分層 PSD」— 屬使用者層級決策。
- ℹ️ spine_inspector 實機 round-trip 需瀏覽器自動化(headless),尚未設置。

## 進度摘要 (progress log)

- 2026-06-24：建立自驅研究框架骨架(RULES/PLAN/STATE/knowledge/log/prompts)。
- 2026-06-24：匯入「Spine mesh system analysis」完整交接;PLAN/RULES/STATE 依實際研究內容填妥,狀態轉 `ACTIVE`。
- 2026-06-24：**S3 第一輪** — 探測並安裝 CPU 套件;完成 mesh 生成器 + 評估器 + 合成測試;6 條 AC 全過(IoU 0.99)。
- 2026-06-24:收到真實 `main_draw.json` + `.atlas`(存入 `assets/`);解析確認 4 mesh + 9 anim deform;
  下一課題定為 deform-aware 評估器(純 CPU,不需 PNG)。
