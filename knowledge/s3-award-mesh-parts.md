# S3 端到端驗收 — 機器人生產件(Award weighted mesh)+ 自調參生成器

- **結論**:對 3 個**真實生產** mesh 件(`機器人拆件/光暈·左手·身體`)跑「atlas 切件 → S3 生成 →
  對照藝術家 mesh」端到端,靜態輪廓維度**三件全過**(生成 IoU ≥ 藝術家 且頂點數 ≤ 藝術家)。
  關鍵:S3 預設 `epsilon=0.008`(為 main_draw 大窗簾調的)對這些較複雜/柔邊的件**覆蓋不足**;
  新增 `generate_auto`(自調 epsilon 到絕對 IoU target)在 2–3 輪內收斂達標。
- **信心**:高(對真實藝術家 mesh 有真值比對 + 評估器負對照確認鑑別力)。
- **階段**:第 2 階段 / S3+S4 串接(STATE 下一步候選 #1,最高優先)。

## 三件結果(`validate_award_parts.py`,IoU target=0.98,vertex budget=藝術家頂點數)

| 件 | mask(atlas) | 藝術家 v / IoU / weighted | 生成 v / hull / IoU / eps / 輪 | 過? |
|---|---|---|---|---|
| 光暈 | 496×480 | 78 / 0.9795 / **weighted** | 73 / 38 / **0.9832** / 0.002 / 3 | ✅ |
| 左手 | 181×152 | 80 / 0.9681 / **weighted** | 57 / 30 / **0.9816** / 0.004 / 2 | ✅ |
| 身體 | 267×299 | 98 / 0.9760 / **weighted** | 69 / 29 / **0.9858** / 0.004 / 2 | ✅ |

生成件用**更少頂點**達到**≥ 藝術家**的輪廓覆蓋。

## 關鍵發現

1. **IoU 由邊界取樣密度決定(再度驗證)**:預設 eps=0.008 三件全 fail(0.929/0.960/0.968);
   對半縮 eps(加密輪廓)→ 0.002~0.004 全過。與 v2 strip 的「IoU 由 rows 決定」同一結論:
   **輪廓密度是覆蓋率的收斂旋鈕**。→ 新增 `generate_auto`(從 eps0 對半縮到達標,≤6 輪,對齊 5 輪預算),
   target 為**絕對** IoU(不看真值),真實 pipeline 無藝術家 mesh 時仍可自驅。
2. **這三件在 Award 是 weighted mesh**(`vertices.length != uvs.length`)、**無 deform timeline**
   → 靠**骨骼權重**變形,不是逐頂點 deform。這與 main_draw 的 4 個 unweighted+deform mesh 是**兩種不同 rig 範式**:
   - main_draw:mesh 由 `deform` timeline 逐頂點動 → S3 的 deform 閘(真實位移場轉移)適用。
   - Award 機器人:mesh 頂點綁骨、由骨骼變換帶動 → **無 deform 可驗**,deform 閘為 N/A。
3. **S3 目前只產 unweighted mesh**:本次端到端只驗**靜態輪廓 + 拓樸/頂點預算**維度。
   **權重綁定(BBW)尚未實作**(S3 roadmap 的下一塊),故「對照真實 weighted mesh」的
   *rig 維度*還沒串。這是誠實邊界,別宣稱已完成 weighted mesh 生成。

## 評估器可信度(每次比對前先驗)

- 正對照:藝術家 mesh 對自身 atlas 切件 IoU 0.968~0.980(合理,非 1.0 因 0.70 縮放插值 + hull 逼近)。
- 負對照:把生成 mesh 頂點向重心縮 → IoU 0.99→**0.80**(縮 10%)→**0.64**(縮 20%),閘有鑑別力。

## 可重現

```
python3 tools/mesh_gen/validate_award_parts.py            # 三件全過 → exit 0
python3 tools/mesh_gen/validate_award_parts.py --iou 0.98 # 自訂輪廓 IoU target
```
`generate_mesh.generate_auto(png, iou_target=0.98, vertex_budget=N)` 可單獨用於任一 PNG 件。

## 下一步(承接)

- **權重維度**:實作 BBW / heat-diffusion 權重(需骨架),把「對照真實 weighted mesh」補到 rig 維度
  (S3 roadmap 最後一塊,需 S5 骨架或先用 Award 既有骨架當輸入)。
- **件→Spine attachment 組裝**(SkelToJson):把 `generate_auto` 輸出 + `PSD名/圖層名` 命名 + size+2px
  固化成端到端「PSD件 → Spine mesh attachment JSON」寫出工具(STATE 候選 #2)。
