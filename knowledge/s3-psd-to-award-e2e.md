# S3×S4 端到端:PSD 件 → mesh → 對照 Award 真實生產 mesh

- **結論**:把 S4(PSD 切圖)接 S3(`generate_mesh_v2`)串成端到端,對**真實生產標的**
  (`Award` spine 的 3 個機器人 mesh:光暈/身體/左手)驗收 **3/3 全過** —— 自動生成 mesh 的
  輪廓覆蓋 **≥ 藝術家自身 mesh 的覆蓋 IoU,且頂點數更少**(73/78、77/98、67/80)。
- **依據**:`tools/mesh_gen/validate_psd_to_award.py`(exit 0);報告存
  `knowledge/reports/psd-to-award-e2e.json`。
- **信心**:高(有藝術家真值可比;正/負校準見下)。**相關階段**:第 2 階段 S3/S4 整合。

## 兩條驗證路徑

| 路徑 | 做什麼 | 意義 |
|---|---|---|
| **A. PSD 出身** | `psd_slice` 切件 PNG → `generate_mesh_v2` → 對自身 alpha 的靜態 IoU + 格式/0孤兒/0退化 | 證明「PSD→件→mesh」自動產出**結構合法**且覆蓋自身輪廓的 mesh |
| **B. 藝術家真值** | atlas 切 region → `generate_mesh_v2` → IoU 對照 **Award 藝術家 mesh 覆蓋率**(`artist_iou`)+ 頂點預算 | 證明自動拓樸覆蓋 **≥ 生產藝術家 mesh**、且頂點更省 |

PSD 件 ↔ atlas region 為同素材(前次 alpha-IoU 0.92~0.99),兩路徑對得起來。

## 關鍵發現 1:`epsilon_frac`(hull 追蹤密度)是**不規則/柔邊件的覆蓋槓桿**

delaunay 路徑用 `cv2.approxPolyDP(eps_frac * 周長)` 定 hull。周長長/形狀不規則的件在
**預設 0.008 下 hull 點太少、輪廓追不到位 → 覆蓋不足**:

| 件 | eps=0.008 | eps=0.002 | 藝術家 |
|---|---|---|---|
| 光暈(柔邊 halo) | hull 14, IoU 0.929(gap **+0.050**,fail) | hull 38, IoU 0.983(**pass**) | IoU 0.9795, 78v |
| 身體 | hull 21, IoU 0.968(gap +0.008) | hull 37, IoU 0.993(pass) | 0.976, 98v |
| 左手 | hull 18, IoU 0.960(gap +0.008) | hull 43, IoU 0.991(pass) | 0.968, 80v |

- `min_dist`(內點間距)**幾乎不影響覆蓋** → 再次印證「覆蓋由邊界/hull 決定,不是內點」
  (與 S3『IoU 由 rows 決定、cols 不影響』一致)。
- **校準值 `epsilon_frac=0.002`**:3 件皆 IoU ≥ 藝術家、頂點皆 < 藝術家 → 用更少頂點達 ≥ 生產覆蓋。
  已把 `epsilon_frac` 參數穿進 `generate_mesh_v2.generate`(**預設仍 0.008,不動既有 v2/strip/main_draw 行為**);
  `validate_psd_to_award` 以 0.002 呼叫。
- **啟示**:未來自動選 eps 可依「周長² / 面積」(形狀複雜度)自適應;柔邊件(glow/煙霧)偏小 eps。

## 關鍵發現 2:Award 機器人 mesh 是 **weighted(骨驅動)、無 deform timeline** → deform 閘**不適用**

- 3 件皆 `vertices.length != uvs.length`(weighted 攤平格式);9/12 動畫**皆無** deform timeline
  →它們的形變**只靠骨骼權重**,不靠 deform。
- 因此 `validate_against_real` 的真實位移場轉移閘(針對 main_draw 的 **unweighted + deform** 窗簾)
  **結構上不適用**於這些件。本工具明確標 `deform_gate.applicable=false`(而非用零位移假性通過)。
- **這揭示 S3 的下一個能力缺口**:對骨驅動件,拓樸生成只做了一半 —— 還需 **權重指派(BBW/骨骼綁定)**
  才能對齊生產。`generate_mesh_v2` 目前只出 unweighted mesh。

## 兩種 mesh 生產範式(重要對照)

| 資產 | mesh 類型 | 形變來源 | S3 驗收閘 |
|---|---|---|---|
| main_draw 窗簾/陰影 | unweighted | **deform timeline** | 真實位移場轉移(0 自交/翻面) |
| Award 機器人件 | **weighted** | **骨骼權重(無 deform)** | 靜態覆蓋 + 頂點預算(deform 閘 N/A) |

→ 「S3 完成」需分兩軌:deform 驅動件(已達標)vs 骨驅動件(**拓樸達標,權重待建**)。

## 可信度(評估器校準)

- **正對照**:藝術家 mesh 自身 `artist_iou` 0.968~0.980(用同一 mask、同法量測,與 gen_iou 可比)。
- **負對照(內建於過程)**:eps=0.008 時 3 件 coverage 皆 fail(gate 有鑑別力,不是恆真);
  eps 由 0.008→0.001 IoU 單調升(0.929→0.992),行為可解釋。
- 頂點預算閘:gen 頂點 < 藝術家 → 排除「靠爆頂點刷 IoU」。

## 下一步候選

1. **S3 權重指派(BBW)**:讓 `generate_mesh_v2` 對骨驅動件輸出 weighted mesh,對照 Award 藝術家權重驗。
   —— 這是把 S3 對「生產骨驅動件」補完的關鍵缺口。
2. `epsilon_frac` 自適應(形狀複雜度 → eps),免手調。
3. 件→Spine JSON 組裝(SkelToJson):把 mesh + `機器人拆件/<層名>` 命名 + offset 寫出可載入 Spine JSON。
