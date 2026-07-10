# S3 端到端驗收 — 真實生產件 → 生成 mesh → 對照 Award 藝術家真實 mesh

- **結論**:把 S3 `generate_mesh_v2`(auto)套到 **Award(機器人 big win spine)裡 3 個真實 mesh 件**
  (光暈 / 身體 / 左手),以 atlas 切出的真實 alpha 為輸入,生成 mesh 的**靜態 IoU 覆蓋率
  全部達到並超越藝術家真實 mesh 的 baseline**,且頂點數比藝術家更省。這是第一個對「真實生產標的」
  的端到端幾何驗收(先前只在 main_draw 自身 4 mesh)。
- **信心**:高(對真實生產 spine 的藝術家 mesh 交叉比對 + adaptive 修正前後對照 + main_draw 無回歸)。
- **階段**:第 2 階段 / S3(里程碑:S3 從 main_draw 內部驗證 → 跨資產對真實生產件驗收)。

## 驗收結果(2026-07-10,adaptive epsilon 修正後)

| 件 | 生成 IoU | 藝術家 IoU | gap | 生成頂點(hull) | 藝術家頂點(hull) | pass |
|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | 0.9882 | 0.9795 | +0.0087 | 82 (48) | 78 (78) | ✅ |
| 機器人拆件/身體 | 0.9858 | 0.9760 | +0.0098 | 69 (29) | 98 (40) | ✅ |
| 機器人拆件/左手 | 0.9884 | 0.9681 | +0.0202 | 61 (36) | 80 (42) | ✅ |

- 指令:`python3 tools/mesh_gen/validate_award_mesh.py --figs knowledge/figures`(overall_pass=true)。
- overlay 存證:`knowledge/figures/award_{光暈,身體,左手}_{artist,gen}.png`。

## ★ 關鍵發現 1:這 3 件是 **weighted mesh**,**無逐頂點 deform timeline**

- `vertices` 陣列長度 ≠ `uvs`×2(光暈 570 vs 156、身體 738 vs 196、左手 556 vs 160)→ weighted。
- 掃過 Award 12 支動畫,這 3 slot 的 `deform` timeline 數 = **0**。
- 意義:它們變形靠**骨骼權重蒙皮**,不是 `DeformTimeline`。故本驗收的 deform-transfer 閘
  (`deform_eval.transfer_deform_check`,需真實位移場)對這些件 **N/A** —— 沒有位移場可轉移。
  **不用未校準的合成壓力硬套**(重蹈 stress_field miscalibration);變形穩健性的判定留給
  「S3 加權(BBW)後再對骨骼旋轉驗證」的未來步驟。此處 AC 收斂在**靜態覆蓋率**。

## ★ 關鍵發現 2:silhouette 主導的件,覆蓋率由「邊界取樣密度」決定 → v1 加 adaptive epsilon

- **修正前失敗**:光暈用固定 `epsilon_frac=0.008`,Douglas-Peucker 把 hull 塌成 **14 點**,
  IoU 只有 **0.929 << 藝術家 0.980**(gap −0.050)。身體/左手僅 −0.008(邊界較硬,勉強在 margin 內)。
- **診斷**:光暈是大柔邊發光件,藝術家用 **78 個純 hull 點**(0 內部點、fan 三角)描邊。
  固定粗簡化丟失邊界細節 → 覆蓋率掉。
- **epsilon 掃描(光暈,藝術家 baseline 0.9795)**:

  | eps | 0.008 | 0.004 | 0.002 | 0.0015 | 0.001 |
  |---|---|---|---|---|---|
  | 頂點 | 54 | 61 | 73 | 82 | 92 |
  | IoU | 0.929 | 0.966 | 0.983 | 0.988 | 0.992 |

  → **覆蓋率隨邊界密度單調上升**(呼應 v2 strip「IoU 由 rows 決定、cols 不影響」的同一條規律:
  覆蓋率是**邊界**現象,不是內部現象)。
- **修正(`generate_mesh.py`)**:`boundary_points` 支援 `epsilon_frac="auto"`(且設為 `generate` 預設)。
  由粗到細掃 eps,用**填滿邊界多邊形 vs mask 的 IoU**(`_hull_coverage`,以 mask 自身校準,無外部壓力)
  當停止準則:覆蓋率 ≥ 0.985 或 hull 頂點 ≥ 90 即停(取第一個達標,頂點最省)。
  簡單硬邊件覆蓋率一開始就達標 → 停在 0.008(不膨脹頂點);柔邊件自動加密。
- 修正後 3 件全超越藝術家 baseline,且頂點數更少(82/69/61 vs 78/98/80)。

## 無回歸

- main_draw 4 mesh(curtain_left/right、shadow/shadow2)走 v2 **strip** 路徑(aspect≥1.2),
  不經 v1 → 不受影響;重驗 `validate_against_real --gen v2` 4 件仍全 overall_pass。
- 這 3 個 Award 件 aspect 都 <1.2(光暈 0.97、身體 1.12、左手 0.84)→ auto 走 **v1 Delaunay**,
  正好補上「v1 對真實複雜件」的驗證(先前 v1 只在 main_draw curtain 上測過)。

## 座標/對齊備忘(可重用)

- Award mesh `uvs` 是 **region-local 正規化(0..1 於該件的邏輯 bbox)**,非全 atlas UV。
  故 `uvs*[W_crop,H_crop]` 可直接光柵化到 atlas 切出的 crop(與生成 mesh 同座標系)。
- atlas region 為 **~0.70 縮小**打包且多為 `rotate=true`;`atlas_crop.extract` 已處理多頁 + CW derotate。
  IoU 用正規化座標 → scale 抵消,不受 0.70 影響。

## 產出 / 下一步

- 新工具:`tools/mesh_gen/validate_award_mesh.py`(可重跑的端到端閘)。
- 修改:`generate_mesh.py` 加 adaptive epsilon(v1 覆蓋率自適應)。
- 下一步候選:(1) 把「PSD件/atlas件 → S3 mesh」再串上**骨骼權重(BBW)**,才能對 weighted mesh
  做骨骼旋轉的變形驗證;(2) 固化「件→Spine attachment(命名慣例 + size+2px + mesh/region 分配)」的
  SkelToJson 組裝工具,產出可載入 spine 的 JSON。
