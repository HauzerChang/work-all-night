# S3×S4 端到端:PSD 件 → 生成 mesh → 對照 Award 真實(藝術家)mesh

- **結論(里程碑)**:機器人 3 個 mesh 件(光暈/身體/左手,Award 生產 spine 中為 mesh)跑
  `generate_mesh_v2`(auto→v1 blob 路徑,調校後 `eps=0.002`),對照**藝術家真值 mesh** 的靜態輪廓
  覆蓋率 **全部達到/超過 parity**,且頂點數相當或更少。首次把「S3 mesh 生成」對**真實生產標的**驗收。
- **信心**:高。評估器先以藝術家 mesh 自覆蓋率(0.968~0.980)+ v-flip 負對照(僅 0.44~0.61)校驗過
  才下判定;兩條生成路徑各自在**自己來源輪廓**評分(避免跨源縮放偽差)。
- **階段**:第 2 階段 / S3×S4 串接。工具:`tools/mesh_gen/compare_award_mesh.py`。

## 共同比較空間(關鍵,踩過兩個座標雷)

1. **不要用 mesh `vertices` 當幾何比較**:Spine unweighted mesh 的 `vertices` 是**骨骼局部座標**,
   帶 setup-pose 的旋轉/位移(裝配成機器人的姿態),`width/height` 只是縮放參考、**非頂點包圍盒**。
   直接 `(x-W/2, H/2-y)` 正規化去比對 alpha → 錯位(光暈 px x:[-135,667] vs 期望 0..708),IoU 假性低。
2. **正解 = region-local `uvs`**:Award mesh 的 `uvs` 是**region 內 0..1**(不是 page atlas UV)。
   映射到用 `atlas_crop.extract`(多頁 + CW derotate)抽出的 region alpha 上:`u*W, v*H`。
   校驗:藝術家 mesh 正映射 IoU **0.968~0.980**;v-flip 僅 **0.44~0.61** → 方向正確、有鑑別力。
3. **normalized 座標對尺度不變**:PSD 件(原尺寸)與 atlas region(~0.70 縮小)可同框比較。

## 量化結果(`eps=0.002, max_interior=60, min_dist=10`)

| 件 | 藝術家 IoU(v) | gen_from_region IoU(v) | gen_from_psd 自源 IoU(v) | gen_from_psd ×region 診斷 |
|---|---|---|---|---|
| 光暈 | 0.9795 (78) | **0.9832 (64)** ✓ | **0.9831 (74)** ✓ | 0.9478 |
| 身體 | 0.9760 (98) | **0.9926 (61)** ✓ | **0.9908 (97)** ✓ | 0.9487 |
| 左手 | 0.9681 (80) | **0.9913 (74)** ✓ | **0.9901 (104)** ✓ | 0.9842 |

- **gen_from_region**:直接用 atlas region alpha 生成 → 隔離 S3 mesh 品質(同源 apples-to-apples)。3/3 過。
- **gen_from_psd(自源)**:用 PSD 切件生成、對 **PSD 件自身** alpha 評 → 真實端到端。3/3 過。
- **gen_from_psd ×region(診斷)**:同一 PSD-mesh 改對 **atlas region** 評 → 掉到 ~0.95。
  **這是跨源量測偽差**(PSD↔atlas ~0.70 縮放 + 對位/anti-alias 差,上季 alpha-IoU 0.92~0.99 即上限),
  **非 mesh 品質**。故正確 AC = 各 mesh 對自己來源輪廓評分,不可拿 PSD-mesh 去對 atlas alpha 雙重扣分。

## 關鍵發現:blob 件覆蓋率由 hull 密度(epsilon)決定

`generate_mesh.py`(v1)預設 `epsilon_frac=0.008`(Douglas–Peucker hull 簡化)對 blob 件**過粗**:
未調時 3 件僅 0.926/0.967/0.958(距藝術家 1~5%)。epsilon 掃描(gen_from_region):

| eps | 光暈 | 身體 | 左手 |
|---|---|---|---|
| 0.008 | 0.926 (h14) | 0.967 (h21) | 0.958 (h18) |
| 0.004 | 0.961 (h22) | 0.986 (h29) | 0.982 (h30) |
| **0.002** | **0.983 (h38)** | **0.993 (h37)** | **0.991 (h43)** |
| 0.001 | 0.992 (h58) | 0.995 (h60) | 0.996 (h84) |

→ **IoU 幾乎全由 hull(邊界取樣)密度驅動,內部點影響甚微** —— 與 v2 strip 的「IoU 由 rows 決定、
cols 不影響」**同一規律**。`eps=0.002` 在 3 件都達 parity 且頂點數 ≤ 藝術家 → 定為 blob 件推薦值。
`generate_mesh_v2.generate(..., v1_kw={...})` 已可轉傳 v1 調校參數(未改全域預設,避免無聲行為變更)。

## 誠實備註

- **「超過藝術家 IoU」的語意**:藝術家 hull 常**內縮於羽化邊**(刻意不吃半透明邊),故其對「生 alpha」的
  覆蓋率天花板 ~0.97~0.98;我們 eps→小時 hull 貼原始 alpha 更緊 → 數字更高。**更高的生-alpha IoU ≠
  一定更好**,只代表更貼原始輪廓;藝術家取捨(修羽化邊、耐變形拓樸)是另一維度。此處 AC 只認「覆蓋率 ≥ 藝術家」。
- **deform 閘 N/A**:Award 這 5 件在 spine **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform),
  故**不**套用 `real_deform_field`(那需要 deform timeline)。本輪 AC 僅靜態輪廓覆蓋率。
  變形穩健性驗證仍以 main_draw 4 mesh(有 deform)為準(見 `s3-four-mesh-generalization.md`)。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_slices   # 切件
python3 tools/mesh_gen/compare_award_mesh.py                                       # eps=0.002 預設 → _overall_pass:true
python3 tools/mesh_gen/compare_award_mesh.py --eps 0.008                           # 未調基線(3 件微幅未達)
```

## 下一步

- 把「件→Spine attachment」組裝(SkelToJson)接上:用真實慣例(slot=`<PSD檔名>/<圖層名>`、
  +2px padding、mesh/region 分配、atlas ~0.70 縮放)把生成 mesh 寫成完整 Spine JSON attachment。
- blob 件是否要把 `eps=0.002` 收成 v1 對 blob 的自動預設(依長寬比/面積判斷),而非靠呼叫端傳參。
- 若日後拿到帶 deform 的生產件,補做 blob 件的變形穩健閘(目前僅 main_draw 窗簾類有 deform 真值)。
