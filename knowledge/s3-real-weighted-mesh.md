# S3 推廣到真實生產 weighted mesh + 自適應輪廓密度

> 結論:S3 v2 的 Delaunay 回退路徑,對真實生產 mesh(Award 機器人 3 件)**預設 epsilon 取樣過疏**,
> IoU 差藝術家基準 0.008~0.050。差距**全來自邊界(hull)密度,內部無關**。
> 加入**自適應輪廓密度**(逐步加密 boundary 直到 recon IoU 達 target,在頂點預算內)後,
> 3 件全部 **IoU ≥ 藝術家基準、0 孤兒、頂點數還比藝術家少**。
> 依據:實測(下表);信心:高(有藝術家真值對照)。相關階段:專案第 2 階段 / S3。

## 背景

先前 S3 只在 `main_draw` 的 4 個 **unweighted、簡單拓樸**(hull 12~16)mesh 上驗過。
本次推到真實生產標的:`Award.json` 裡機器人 big win 的 3 個 mesh。它們是 **weighted**
(靠骨骼 skinning 變形,**無 deform timeline**),輪廓遠比窗簾複雜(hull 40~78)。

真值來源:`Award.atlas` + `Award.png`/`Award2.png`(`atlas_crop` 處理多頁 + rotate)。
- `機器人拆件/光暈` Award2.png rotate=true,region 496×480(mesh 708×685,~0.70 打包縮放)
- `機器人拆件/左手` Award.png  rotate=false,region 181×152(mesh 259×217)
- `機器人拆件/身體` Award2.png rotate=true,region 267×299(mesh 381×427)

## 為何改「靜態 + 結構健全」而非 deform 轉移閘

1. 這 3 件是 **weighted**(`vertices.len != uvs.len`);`deform_eval` 目前只實作 unweighted。
2. Award 裡這 3 件**沒有 deform timeline**(grep `機器人` 於所有 `deform` 為空)→ 位移場轉移無資料可轉。
→ 用 ① 靜態 IoU vs 藝術家覆蓋率基準 ② `evaluate_mesh` 結構健全度(重心在內/退化/孤兒/頂點預算)。
（未來若要 deform 級驗:需先實作 weighted skinning + 骨骼動畫套用,屬另一個較大工作塊。）

## 關鍵發現:IoU 差距 = 邊界密度(Douglas-Peucker epsilon 太粗)

固定 `epsilon_frac` 掃描(v1 Delaunay,`max_interior=40`),對照藝術家 IoU 基準:

| mesh | 藝術家基準 | eps=0.008(舊預設) | 0.004 | 0.002 | 0.001 |
|---|---|---|---|---|---|
| 光暈 | 0.9795 | 0.9292 (hull14, **1 orphan**) | 0.9656 | **0.9832** | 0.9924 |
| 左手 | 0.9681 | 0.9602 (hull18) | 0.9816 | 0.9913 | 0.9963 |
| 身體 | 0.9760 | 0.9680 (hull21) | 0.9858 | 0.9926 | 0.9946 |

- 舊預設 `epsilon_frac=0.008` 是在 main_draw 簡單 mesh 上調的 → 對複雜生產輪廓取樣過疏。
- 內部點(Canny+格點)一直夠;**IoU 完全由 hull 邊界密度決定**(呼應 v2 strip 的「IoU 由 rows 決定」)。
- 副作用:eps=0.008 在光暈還產生 1 個孤兒頂點(生成健全度 bug);加密後消失。

## 修法:自適應輪廓密度(已固化)

`generate_mesh.generate(..., target_iou=0.982, vertex_budget=110)`:
- `target_iou=None` → 舊行為(固定 epsilon,**完全向後相容**,現有 main_draw 驗證不變)。
- 設 `target_iou` → 由疏到密掃 `eps_schedule=(0.008…0.0005)`,用 `_recon_iou`(三角化 recon vs mask,
  **自量測、不需外部真值**)判斷;取「達標且最省頂點」的一版,預算內達不到則回傳預算內 IoU 最佳者。
- `generate_mesh_v2` 的 Delaunay 回退改呼叫此路徑(`target_iou=0.982, vertex_budget=110`),
  `_mode` 標為 `delaunay-v1-adaptive`。**strip 路徑(main_draw 4 mesh 走的)完全不受影響**。

## 驗收結果(`validate_robot_mesh.py --gen v2`,all_pass=True)

| mesh | 生成(v/hull/tri) | 藝術家(v/hull/tri) | IoU | 基準 | 孤兒 | PASS |
|---|---|---|---|---|---|---|
| 光暈 | 73 / 38 / 106 | 78 / 78 / 76 | 0.9832 | 0.9795 | 0 | ✅ |
| 左手 | 67 / 43 / 89 | 80 / 42 / 116 | 0.9913 | 0.9681 | 0 | ✅ |
| 身體 | 69 / 29 / 107 | 98 / 40 / 154 | 0.9858 | 0.9760 | 0 | ✅ |

- 3 件全部 IoU ≥ 藝術家基準,**頂點數還比藝術家少**(73<78 / 67<80 / 69<98)。
- 光暈用 hull 38 就蓋過藝術家 hull 78 的覆蓋率 → 自適應密度足夠、無需盲目堆點。

## 教訓 / 對 pipeline 的意義

- **「在簡單資產調的參數不會自動泛化」**再次成立(呼應 rows、premultiplied、derotate 三次校準)。
  正確作法:把「絕對量的參數」換成「自量測回饋迴圈」(target IoU 自適應),讓生成器對形狀自我校準。
- 評估閘的**頂點預算**也不是常數:main_draw 簡單 mesh 用 64,真實生產 mesh 藝術家自身就用 78~98。
  閘應以「藝術家真值 + 餘裕」為準,`validate_robot_mesh` 已改 `max(110, art_nv+12)`。
- 端到端「(PSD/atlas)件 → S3 mesh → 對照真實生產 mesh」對**複雜 weighted 標的**首次全綠。

## 未解 / 下一步

- weighted mesh 的 **deform 級**驗證仍缺(需 skinning + 骨骼動畫);目前只到靜態 + 結構健全。
- 生成的是 unweighted mesh;要真正替換生產 weighted mesh 還需**綁權重**(BBW,S3 路線的下半)。
- `robot_parts.psd` 直接切件 → 生成(而非從 atlas 取)可再收一次「PSD 端到端」;本次用 atlas 真值對照更嚴。
