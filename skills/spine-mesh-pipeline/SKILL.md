---
name: spine-mesh-pipeline
description: |
  純 CPU 的 Spine 2D 資產前處理 pipeline —— 把「圖層/貼圖」自動變成「可載入、耐變形、可量化驗收」的 Spine mesh 與切件。與 spine-ai-editor(編輯/Cocos MCP 推送)互補:此 skill 負責「資產生成 + 自我品質閘」那半。

  Use when the user wants to:
  (1) 從一張 PNG(alpha)自動生成 unweighted Spine mesh(findContours + Douglas-Peucker hull + Canny/格點內部點 + 約束 Delaunay,或 strip 拓樸),並用 IoU/拓樸/變形閘量化驗收;
  (2) 從分層 PSD 依「一圖層=一部位」契約自動切件 + 出 manifest + 自驗重組無損(S4 PSD-first 切圖);
  (3) 驗證/重組 atlas(依 region xy/size/rotate 切貼圖,含多頁 + CW derotate)、或做「切圖→重組」保真閘(S2);
  (4) 檢查一個會被 deform 的 mesh 在真實位移場下是否自交/翻面/退化(deform-aware 評估器);
  (5) 對照「藝術家真實 mesh」做端到端驗收(對齊頂點成本比 IoU),確認生成器達到生產標準。

  觸發詞:「PNG 轉 mesh」「自動生成 mesh」「mesh 拓樸」「切圖」「PSD 切件」「atlas 重組」「mesh 會不會撕裂/自交」「deform 驗證」「頂點覆蓋率 IoU」「切件對照 spine」「資產前處理」「S2」「S3」「S4」。

  Requires: Python 3 + numpy / opencv-python-headless / scipy / triangle / psd-tools(見 requirements.txt)。純 CPU,無需 GPU / 無需 Cocos。
---

# spine-mesh-pipeline

把「一張圖 / 一份分層 PSD」自動變成「可載入、耐變形、可**量化驗收**」的 Spine 資產。
所有能力都純 CPU、可自動跑、附**機讀 pass/fail 閘**(exit code + JSON),不靠肉眼。

> 這是 `work-all-night` 自驅研究專案(Spine mesh 系統)累積成果的打包版。
> 上游源頭(含完整 log / knowledge / 真實測試資產)在該 repo;此 skill 是可攜的快照。
> 與 **spine-ai-editor** 併用:本 skill 產「乾淨資產(mesh/切件)」→ spine-ai-editor 把它們組進 spine JSON 並推 Cocos 預覽。

---

## 安裝 / 前置

```bash
pip install -r requirements.txt          # numpy opencv-python-headless scipy triangle psd-tools
```
`tools/` 內腳本互相 import(靠 `sys.path.insert(0, dirname)`),整個 `tools/` 資料夾一起用即可。
詳見 `INSTALL.md`(如何在 cowork/chat 啟用)。

---

## 何時觸發

| 使用者徵兆 | 對應能力 | 工具 |
|---|---|---|
| 「這張 PNG 幫我做成 mesh」「自動生成骨骼網格」 | S3 mesh 生成 | `tools/generate_mesh.py` / `generate_mesh_v2.py` |
| 「這個 mesh 動起來會不會破/撕裂」 | 變形閘 | `tools/deform_eval.py` |
| 「生成的 mesh 夠好嗎」「跟藝術家比」 | 靜態 + 對照閘 | `tools/evaluate_mesh.py` / `validate_against_real.py` / `validate_award_mesh.py` |
| 「這份 PSD 幫我切件」 | S4 PSD 切圖 | `tools/psd_slice.py` |
| 「atlas 切一件出來」「切圖對不對」 | atlas 重組 / S2 閘 | `tools/atlas_crop.py` / `evaluate_slicing.py` |

---

## 核心能力與驗證過的指令(recipes)

### S3 — PNG(alpha) → Spine mesh

兩條拓樸路徑,`generate_mesh_v2` 的 `auto` 會自動選:
- **strip**(掃描線直條):高瘦、每列單一 alpha 區段的件(如窗簾)。變形時各條平滑滑動、最耐拉伸。
- **delaunay**(v1):blob / 凹形件(如光暈、身體)。約束 Delaunay + 重心過濾 + **孤兒頂點修剪**。

```bash
# 直接生成(strip/delaunay 自動)
python3 tools/generate_mesh_v2.py part.png -o part_mesh.json          # 預設 rows=10,cols=3
# blob 件對齊「藝術家頂點成本」→ 用 target_verts 自適應 epsilon(輪廓解析度)
python3 -c "import sys;sys.path.insert(0,'tools');from generate_mesh import generate;import json;\
m,_=generate('part.png', target_verts=80); json.dump(m, open('part_mesh.json','w'))"
```

**關鍵發現(2026-08-10,對 Award 真實生產 mesh 驗證):輪廓解析度(`epsilon`)是 blob mesh 的 IoU 主槓桿,
內部點密度近乎無關**;strip 路徑的對應版是「IoU 由 rows(邊界取樣)決定、cols 不影響」。
→ 用頂點預算反推 epsilon(`target_verts`)就能對齊藝術家覆蓋率。

### S3 驗收閘

```bash
# 靜態(IoU/重心/退化/孤兒/預算/格式,exit 0 = 全過)
python3 tools/evaluate_mesh.py part_mesh.json part.png
# 對真實資產整合驗收(有 deform timeline 的 unweighted mesh,如 main_draw 窗簾)
python3 tools/validate_against_real.py --slot image/curtain_left --name image/curtain_left --gen v2
# 端到端對藝術家真實 mesh(Award 機器人 3 件,對齊頂點成本比 IoU)
python3 tools/validate_award_mesh.py          # all_pass exit 0:光暈/左手/身體 生成 IoU 全 ≥ 藝術家
```

> ⚠️ **變形閘只用真實位移場轉移(`transfer_deform_check`),不要用未校準的 `stress_field`**(合成場面積比遠大於真實,會假性失敗)。
> **weighted + 無 deform timeline 的 mesh**(如 Award 機器人件)沒有逐頂點位移場 → 只能驗**靜態幾何**,變形交給骨架/權重(S5)。

### S4 — 分層 PSD → 各部位切件

```bash
python3 tools/psd_slice.py character.psd --eval     # 切件 + manifest + 重組無損自驗(exit 0 = PASS)
python3 tools/make_test_psd.py                       # 沒真實 PSD 時造合成 fixture
```
契約見 `references/psd_contract.md`(給美術的交檔規範,已對真實生產 PSD 校準)。
真實慣例:**slot 命名 = `<PSD檔名>/<圖層名>`**;一圖層=一 slot;size 對應 spine +2px(atlas padding)。

### S2 / atlas — 切圖與重組保真

```bash
python3 tools/atlas_crop.py character.atlas sheet.png 'image/curtain_left' out.png   # 多頁 + CW derotate
python3 tools/evaluate_slicing.py --atlas assets/main_draw.atlas --png assets/main_draw.png  # 45/45 MAE=0
```

---

## 血淚教訓(評估器校準,務必內化)

1. **評估器先驗可信度再下判定**:每個閘都要先跑「正對照(藝術家真值應 pass)+ 負對照(故意壞的應 fail)」。
   本專案踩過**四次 miscalibration**:stress_field 合成場過猛、PSD composite 透明區填白、
   atlas derotate 方向(CCW↔CW)、固定頂點預算對大件過緊。**未校準的閘會給假結論。**
2. **round-trip 自洽 ≠ 絕對正確**:切圖 extract↔repack 方向一起反仍 MAE=0,靠**外部真值**(PSD 切件)才揪出 derotate 方向 bug。
3. **合成/單一資產測不到的路徑,換真實多樣件才會踩到**:orphan-vertex bug 在窗簾(strip)從不觸發,
   換凹形光暈(Delaunay + 重心過濾)才暴露 → **端到端對真實標的驗收有獨立價值**。
4. **AC 要相對真值、別用武斷常數**:IoU 門檻用「≥ 藝術家同件」;頂點預算用「≤ 藝術家頂點數」。

## Spine 3.8 資產格式雷點(生成/讀寫時)

- unweighted mesh:`len(vertices)==2×頂點數==len(uvs)`;**hull 頂點必排最前**;座標 y-up、以圖中心為原點,uv 為 0..1。
- weighted mesh:`vertices` 為 `[骨數,(骨idx,bindX,bindY,權重)*n]` 變長格式(`len(vertices)≠len(uvs)`),權重每頂點和=1。
- atlas 貼圖可能被縮小打包(Award ~0.70);attachment 的 width/height 記**原始邏輯尺寸**,texture 比對需先 resize 對齊。

---

## 這 pipeline 在整體路線(S1–S5)的位置

- **S2 評估器套件**:切圖閘 ✅、deform 閘 ✅;補圖閘 / 骨架閘 ⬜(待補)。
- **S3 mesh 生成器**:✅ 對 4 個 main_draw mesh + 3 個 Award 真實生產 mesh 端到端驗收通過。
- **S4 切圖 + 補圖**:PSD-first 切圖 ✅(對 2 份真實生產 PSD 無損);補圖 ⬜。
- **S1 反推分析器 / S5 骨架半自動**:⬜(S5 骨架 pivot 是唯一需人力集中處)。

完整狀態與 knowledge 見上游 repo `STATE.md` / `knowledge/`,或本 skill 的 `references/findings.md`(蒸餾版)。
