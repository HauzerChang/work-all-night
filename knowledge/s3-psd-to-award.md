# S3 端到端：PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**：端到端「robot_parts.psd 件 → `generate_mesh_v2` → 對照 Award 生產 mesh」在**靜態輪廓保真**
  上對 3 件真實 mesh(光暈/身體/左手)**全數 PASS**(生成 IoU ≥ 藝術家基準,且 `evaluate_mesh` 靜態 AC 全過)。
- **依據**：`tools/mesh_gen/validate_psd_to_award.py`(本次新增),`assets/robot_parts.psd` + `assets/Award.json` 真值。
- **信心**:高(有生產 spine 真值對照;純 CPU 可重現)。
- **相關階段**:第 2 階段 S3(mesh 生成)× S4(PSD 切圖)串接;里程碑。

## 驗收數字(epsilon_frac=0.002,新預設)

| 件 | 尺寸 | 生成 verts/tris | 生成 IoU | 藝術家 verts/tris | 藝術家 IoU | margin |
|---|---|---|---|---|---|---|
| 光暈 | 706×683 | 64 / 80 | 0.9796 | 78 / 76 | 0.9486 | **+0.031** |
| 身體 | 379×425 | 77 / 115 | 0.9908 | 98 / 154 | 0.9477 | **+0.043** |
| 左手 | 257×215 | 84 / 122 | 0.9901 | 80 / 116 | 0.9768 | **+0.013** |

生成頂點數(64–84)與藝術家(78–98)同量級 —— 貼齊輪廓且未過度堆點。

## 三個關鍵發現

1. **結構事實(重要):Award 這 3 件是 weighted + 無 deform**。
   - 每頂點綁 1~2 骨(`vertices.length != uvs.length`);9×3=27 條動畫掃過**皆無** deform timeline。
   - 形變靠**骨骼權重**驅動,不是 deform —— 與 main_draw 的 4 個 **unweighted + deform 驅動** mesh 是**不同機制**。
   - 推論:S3 的「deform 穩健度閘」(`transfer_deform_check`,為 deform 驅動而建)對這類件**不適用**;
     此處可自動驗的只有**靜態輪廓保真**。要真正逼近 Award 這類件,S3 還缺 **BBW 權重生成**(把幾何綁到骨)——
     屬 S3 路線圖已列、**尚未實作**的下一個真缺口。geometry-only ≠ 生產可用 rig。

2. **UV 空間更正**:Award mesh 的 `uvs` 是 **region 局部正規化 0..1**(實測三件 uv 皆近 [0,1]),
   **不是**整頁 atlas UV —— **更正 session006 的假設**(「需先轉 region 局部」)。因此藝術家基準可直接
   `uvs*W, uvs*H` 填入件遮罩比對,無需 atlas→局部換算。(atlas 打包旋轉是載入細節,不反映在存檔 uv。)

3. **調參:v1 預設 epsilon_frac 0.008 → 0.002**。
   - 0.008 是為合成小圖調的;真實生產件(數百 px)下 `approxPolyDP` 只給 hull 16–20 點,輪廓太粗,
     IoU 比藝術家低 ~1.3–1.6%(光暈 −0.0155、左手 −0.0126)。
   - `epsilon_frac` 是**周長比例(尺度不變)**,0.002 對三件全部收斂且頂點數仍精簡 → 設為 v1 新預設,
     並讓 `generate_mesh_v2.generate(epsilon_frac=)` 透傳。
   - **strip 模式(main_draw 4 mesh)不受影響**(不走 epsilon);回歸實測 4 mesh 全 `overall_pass` 不變。

## 副記

- **+2px padding 再確認**:attachment w/h(如光暈 708×685)= PSD 件尺寸(706×683)+ 2px(承 session005)。
- **教訓延續**:先前三次評估器 miscalibration;這次先以「藝術家 mesh 對同一 alpha 的 IoU」當基準(自帶
  真值),避免用武斷閾值,是對的做法。

## 下一步(見 STATE)

- S3 缺口已定位為 **BBW 權重生成**(unweighted 幾何 → weighted rig)。可先做「權重品質閘」(S2 樞紐:
  沒閘無法自主收斂),再做 BBW。或先做「件→Spine JSON 組裝(SkelToJson)」把已通過的幾何 + 命名慣例
  `<PSD檔名>/<圖層名>` + 2px padding 固化成可寫出的 attachment。
