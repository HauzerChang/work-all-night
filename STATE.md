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

S3 生成器 + deform 評估器(含真實 benchmark)皆完成。下一個 bounded chunk 候選:

**(a) 把 deform 耐受納入 S3 正式 AC + 參數掃描**(純 CPU,不需 PNG)— 建議
  - 將「stress_field @ ~315px 下 0 自交/0 翻面」寫入 generate+evaluate 的整合 AC。
  - 掃描內部點密度 / min-dist,找「最少頂點 × 仍通過耐變形」的甜蜜點。

**(b) 真實貼圖驗證**(待 `main_draw.png` 檔)— 裁 curtain_left 區域 → 生成 mesh → texture IoU + UV 撕裂。

**(c) spine_inspector 實機 round-trip**(需 headless 瀏覽器)— `setMeshVertices`/`getMeshBounds`/`screenshot`。

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
- 2026-06-24:**deform 評估器課題完成** — Python 重現 Spine deform;真實 4mesh×9anim benchmark 全乾淨
  (_checker_validated);負對照可抓自交/翻面;生成 mesh 耐變形 ≈ 藝術家手做(撐過 315px)。
