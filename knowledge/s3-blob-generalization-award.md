# S3 推廣到 blob 型真實 mesh（Award 機器人件，端到端 PSD→件→mesh→真值）

- **結論**：S3 生成器在 main_draw 4 mesh（高瘦 strip）外，對 **Award 生產 spine 的 3 個 blob 型
  weighted mesh（光暈/身體/左手）** 也能達標。v2-auto 正確把這 3 件（長寬比 <1.2）路由到
  **v1 Delaunay** 路徑；唯一需校準的是 **邊界取樣密度（`epsilon_frac`）**——它就是 blob 的 IoU 槓桿
  （對應 strip 的 `rows`）。把 v1 預設 `epsilon_frac` 由 **0.008 → 0.002** 後，3 件全過藝術家覆蓋率
  基準，且頂點數仍 ≤ 藝術家預算。
- **信心**：高（對真實生產 spine 的藝術家 mesh 做覆蓋率對照 + 負對照 + 真值自一致性 0.968~0.980）。
- **階段**：第 2 階段 / S3（里程碑：從 main_draw strip → 真實生產 blob 通用化）。

## 驗證設定（真值來源）

- 件來源：`assets/Award.{json,atlas,png/Award2.png}`（機器人對應的 big win 生產 spine，雙頁 atlas）。
- 切件：`atlas_crop.extract`（多頁 + **CW** derotate；光暈/身體 在 atlas 中 rotate=true）。
  → 上正 crop（~0.70 縮小版）；其 alpha 當生成來源 mask。
- 真值：Award.json 的 weighted mesh attachment。**關鍵交叉確認**：藝術家 mesh 的 uvs 直接
  `uvs×(cropW,cropH)` 重建即與上正 crop 對齊，artist_iou = **0.968 / 0.976 / 0.980**（高）
  → 同時再次印證 `atlas_crop` 的 **CW derotate 方向正確**（CCW 會錯位）。
- 工具：`tools/mesh_gen/validate_award_mesh.py`（靜態覆蓋率 IoU，**不做 deform 閘**，見下）。

## ★ 核心發現：邊界密度 = blob 的 IoU 槓桿（epsilon 掃描）

| 件 | 藝術家 base | eps=0.008(舊預設) | eps=0.004 | **eps=0.002(新預設)** | eps=0.001 |
|---|---|---|---|---|---|
| 左手 | 0.9681 | 0.9602 ✗ | 0.9816 ✓ | **0.9913 ✓ (67v)** | 0.9963 (107v) |
| 身體 | 0.9760 | 0.9680 ✗ | 0.9858 ✓ | **0.9926 ✓ (77v)** | 0.9946 (100v) |
| 光暈 | 0.9795 | 0.9292 ✗ | 0.9656 ✗ | **0.9832 ✓ (73v)** | 0.9924 (92v) |

- 舊預設 0.008 三件全**覆蓋率不足**；最糟是 **光暈**（柔邊發光，藝術家用 hull=78 全邊界點細描）。
- `epsilon_frac` 只控 **hull（外周）取樣密度**，不動 `max_interior`；調細 hull → 覆蓋率單調上升。
- **0.002 是甜蜜點**：3 件全過基準，頂點數 67/77/73 仍 **≤ 藝術家 80/98/78**
  （= 用更少頂點達到藝術家覆蓋率）。故設為 v1 新預設。
- 普遍規律：**「邊界取樣密度」是覆蓋率的通用槓桿** —— strip 是 `rows`、blob 是 `epsilon_frac`；
  柔邊/細節多的件（光暈）需更密邊界。

## 評估器可信度（校準 + 負對照）

- **真值自一致性**：藝術家 weighted mesh 自身覆蓋率 0.968~0.980（非 1.0；blob 邊界本就有殘差）→ 用其當基準合理。
- **負對照**：故意粗化邊界（eps=0.012）→ 3 件 IoU 0.910/0.953/0.938 全 **< base 正確 FAIL** → 閘有鑑別力、未過鬆。
- v1 預設改細**未傷變形**：`validate_against_real --gen v1`（curtain_left，真實 deform 轉移）
  IoU 0.918→**0.9946**、self-intersections **0**、flips **0** → 更密邊界對 deform 安全（甚至更好）。

## ⚠️ 範圍限制（誠實標註）

- Award 機器人 5 件在 spine 中**無 deform timeline**，靠**骨骼權重（weighted）**變形。
  本驗收只做**靜態覆蓋率**；bone-weighted 變形需重現整段骨骼動畫（屬 **S5** 範圍），本階段**未測**。
- 生成的是 **unweighted** mesh（拓樸/覆蓋率對照);自動配權（BBW）尚未做（S3 後續 / S5 介面）。

## 可重現

```
python3 tools/mesh_gen/validate_award_mesh.py --gen v2          # 3 件全 overall_pass，EXIT 0
python3 tools/mesh_gen/validate_award_mesh.py --gen v2 --slot 機器人拆件/光暈
```

## 下一步

- 把「件→Spine attachment」組裝慣例（`PSD名/圖層名`、+2px padding、atlas ~0.70 縮放、
  mesh/region 分配）固化成 **SkelToJson** 寫出工具，端到端產 Spine JSON（含本 mesh）。
- 自動配權（BBW / heat / bone-distance）使生成 mesh 可被骨骼驅動 —— S3→S5 銜接點。
