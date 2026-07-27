# S3 端到端對照生產 mesh：機器人拆件（Award）幾何達標 + 揭露 weighted 缺口

- **結論**：端到端「PSD 件 → S3 生成 mesh」對 **Award 生產 spine 的 3 個 warp 件**（光暈/身體/左手）
  做**靜態覆蓋率**對照，S3（v1 自適應 epsilon）**達到或超過藝術家手做 mesh 的覆蓋**，
  且頂點預算相當、零孤兒/零退化 → **幾何層對生產標準驗收通過**。
- **依據**：真值取自生產檔 `assets/Award.json`（機器人對應 spine）。兩邊 mesh 都在**同一張
  去旋轉 region 遮罩**上量覆蓋(apples-to-apples)。工具 `tools/mesh_gen/validate_robot_parts.py`。
- **信心**：高（外部生產真值 + 同遮罩比對）。
- **相關階段**：第 2 階段 S3（mesh）× S4（切圖）串接;第一次對「非 main_draw」真實生產標的驗收。

## 量化結果（2026-07-27）

| 件 | region px | 藝術家 (weighted) uv/hull/tris/IoU | S3 生成 nv/hull/tris/IoU | AC 覆蓋≥藝術家 |
|---|---|---|---|---|
| 光暈 | 496×480 | 78 / 78 / 76 / **0.9795** | 78 / 38 / 116 / **0.9832** | ✅ |
| 身體 | 267×299 | 98 / 40 / 154 / **0.9760** | 69 / 29 / 107 / **0.9858** | ✅ |
| 左手 | 181×152 | 80 / 42 / 116 / **0.9681** | 70 / 30 / 108 / **0.9816** | ✅ |

`overall_pass=true`；三件皆 format 乾淨（無孤兒/退化）。

## 關鍵發現一（最重要 / 結構性）：生產 warp 件是 **weighted mesh、無 deform**

- Award 這三件 `vertices.length != uvs.length` → **weighted**（骨骼驅動綁定），且**沒有 deform timeline**
  （對照 session 005 結論：warp 件靠骨骼、不是逐頂點 deform）。與 main_draw 4 件（unweighted + deform 驅動）
  在**驅動機制上根本不同**。
- 影響：
  1. main_draw 用的「真實 deform 位移場轉移閘」在此**不適用**（沒有位移場）→ 本次只驗**靜態幾何/覆蓋**。
  2. S3 v2 目前輸出 **unweighted 幾何**：能對齊覆蓋率與拓樸，但**尚無 BBW 權重 + 骨綁**。
     → 要產出「生產等價」的機器人 mesh，缺的是 **BBW 權重生成 + 骨架綁定（SkelToJson 寫回）**，
     這正是 S3 路線圖列出但**未建的組件**。幾何層已通，權重層是下一個真正的槓桿。

## 關鍵發現二（方法）：固定 epsilon 不通用 → 改**自適應 epsilon**

- v1 原本固定 `epsilon_frac=0.008` 是為窗簾（高瘦 strip）調的。對中型塊狀件覆蓋不足：
  光暈只有 0.919 且**軟邊產生孤兒頂點**（filter_triangles 丟掉軟邊/凹形三角 → 內部點沒人參照）。
- Epsilon 掃描證明**覆蓋差距純粹是邊界取樣密度**：eps 0.008→0.002 時三件 IoU 全升到 0.983~0.993、孤兒歸零。
- 修法（`generate_mesh.py`）：
  - `epsilon_frac="auto"`：沿階梯 `[0.008,0.004,0.002,0.001]` 由粗到細，直到覆蓋達 `target_iou`（預設 0.97）
    或碰到 `vertex_budget`（預設 100）→ **每件自對齊藝術家水準**，不再靠人為常數。
  - `compact_orphans()`：只移除 **index≥n_hull** 的未參照內部點（hull-first 順序與 hull 數不變）→ 安全消除孤兒。
  - `generate_mesh_v2.py` 塊狀件回退 v1 時改用 `epsilon_frac="auto", min_dist=8`。
- **無回歸**：main_draw 4 mesh（strip 路徑，不走 v1）`validate_against_real --gen v2` 全 `overall_pass`
  （curtain_left/right、shadow、shadow2 IoU 全過、deform 0 自交/0 翻面）。

## 復現指令

```
python3 tools/mesh_gen/validate_robot_parts.py          # 3 件端到端對照（PASS）
# 回歸：main_draw 4 mesh（shadow2 的 region 名為 image/shadow，兩 slot 共用）
python3 tools/mesh_gen/validate_against_real.py --slot image/curtain_left --name image/curtain_left --gen v2
python3 tools/mesh_gen/validate_against_real.py --slot image/shadow2      --name image/shadow      --gen v2
```

## 下一步槓桿

1. **BBW 權重 + 骨綁生成**（S3 未建組件）：把生成的 unweighted 幾何綁到骨架、產 weighted mesh，
   對照 Award 這三件的權重/骨綁 → 才是「生產等價」而非只是覆蓋等價。需先有骨架（S5）或用 Award 現成骨架當靶。
2. **件→Spine JSON 組裝（SkelToJson）**：把 `<PSD檔名>/<圖層名>` 命名 + size+2px padding + 這裡的
   mesh 產生器固化成一鍵「PSD → Spine attachment JSON」。
