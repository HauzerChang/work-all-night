# S3 端到端「PSD→件→mesh」對照真實生產標的 (Award 機器人拆件)

- **結論**:對 Award 3 個真實 mesh 件(光暈/左手/身體)跑 S3 `generate_mesh_v2`,靜態輪廓覆蓋率
  **全部 meet-or-beat 藝術家 mesh**,且頂點數 ≤ 藝術家。修正一個 v1 預設值即達標。
- **依據**:`tools/mesh_gen/validate_award_mesh.py`(新增,對 Award atlas 切件 + 藝術家 uvs 對照)。
- **信心**:高(對真實生產 mesh 逐件量化;有藝術家真值當基準)。
- **相關階段**:第 2 階段 S3(mesh 生成器)/ S4(PSD→spine)串接;純 CPU 可自驅。

## 兩個關鍵發現

### 1. 真實「拆件」mesh 是 weighted + 純骨骼驅動,無 deform timeline

Award 的 3 個 mesh 件全是 **weighted mesh**(`len(vertices) != len(uvs)`),
且在 12 支動畫中**沒有任何 deform timeline** 引用它們 —— 它們靠**骨骼權重**變形,
不是 deform。對照 main_draw 窗簾:**unweighted + deform 驅動**。

→ 因此 S3 既有的 **deform-transfer 閘(讀 deform 位移場)對這些件不適用**;
本次只驗「靜態輪廓/覆蓋率」軸。weighted 件的「耐變形」正確性屬 S3 尚未建的
**BBW 權重生成**範疇(路線圖 S3「+ BBW 權重」),是下一個真正待補的能力。
這是一個**範疇邊界發現**,不是失敗:兩類 mesh(deform-驅動 vs 骨骼-驅動)需要不同的閘。

各件真值(region-local uvs、+2px padding 的原始邏輯尺寸):
| 件 | 頂點 | 三角 | hull | 型態 |
|---|---|---|---|---|
| 光暈 | 78 | 76 | 78(全 hull,fan) | weighted,軟邊放射光暈 |
| 左手 | 80 | 116 | 42 | weighted |
| 身體 | 98 | 154 | 40 | weighted |

3 件長寬比皆 <1.2 且非直條 → v2 auto **全部回退 v1 Delaunay**(非 strip)。

### 2. 「邊界取樣密度決定 IoU 覆蓋率」律,在 v1 Delaunay 路徑同樣成立

v1 預設 `epsilon_frac=0.008`(合成/窗簾期調的)對**軟邊放射光暈**只給 **14 hull 點**
→ IoU 0.92 << 藝術家 0.98。收緊 epsilon 掃描(光暈):

| epsilon | hull | 頂點 | IoU |
|---|---|---|---|
| 0.008 | 14 | 54 | 0.919 |
| 0.004 | 22 | 62 | 0.966 |
| **0.002** | **38** | **78** | **0.983** |
| 0.001 | 58 | 98 | 0.992 |

且 `max_interior` 40→80 對 IoU **零影響**(0.9295→…→0.983 皆與內部點數無關)。
→ 與 v2 strip 的「**IoU 由 rows 決定、cols 不影響**」完全同構:
**覆蓋率是邊界問題,不是內部填充問題**(v1/v2 共通律)。

## 修正與驗收

- 改 `generate_mesh_v2.py` 的 v1 回退呼叫:`epsilon_frac 0.008 → 0.002`、`min_dist 8`。
- `validate_award_mesh.py` 三件全 PASS(容差對齊藝術家覆蓋 -0.02):
  - 光暈 gen **0.983** ≥ 藝術家 0.980(nv 78 = 藝術家 78)
  - 左手 gen **0.991** ≥ 藝術家 0.968(nv 83 vs 80)
  - 身體 gen **0.993** ≥ 藝術家 0.976(nv **77** vs 98,更省)
- **無回歸**:main_draw 4 mesh 全走 strip 模式,不受 v1 回退改動影響,`validate_against_real --gen v2` 4 件全 overall_pass。

## 待續

- **S3 BBW 權重生成**:這是把「骨骼驅動 mesh 件」端到端做完的缺口(本次僅補齊靜態拓樸/輪廓軸)。
  完成後才能對 weighted 件做「耐變形」對照(而非只有靜態 IoU)。
- 「件→Spine JSON 組裝」(SkelToJson):把 `<PSD檔名>/<圖層名>` 命名 + size+2px padding +
  (mesh 件用生成拓樸、剛體用 region)固化成寫檔工具,端到端產出 Spine JSON。
