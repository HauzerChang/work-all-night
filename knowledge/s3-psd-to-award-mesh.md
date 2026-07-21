# S3 端到端:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh(靜態)

- **結論**:把 `robot_parts.psd` 的 3 個機器人件(光暈/左手/身體,在生產 spine `Award` 中為 mesh)
  跑 `generate_mesh_v2`,與 Award 藝術家 mesh 做**覆蓋 IoU + 頂點預算 + 拓樸乾淨**對照,**3 件全 PASS**。
  我方生成 mesh **用更少頂點達到與藝術家相當的輪廓覆蓋**。這是 S3+S4 首次對「真實生產標的」端到端驗收。
- **依據**:`tools/mesh_gen/compare_award_mesh.py`(overall_pass=True / EXIT=0),純 CPU 可重跑。
- **信心**:高(有藝術家真值對照 + 內建對齊自檢)。
- **相關階段**:S3(mesh 生成)× S4(PSD 切件),第 2 階段能力鍛鍊。

## 對照結果(2026-07-21)

| 件 | 我方 mode | 我方頂點 | 藝術家頂點 | 我方覆蓋 IoU | 藝術家覆蓋 IoU | 覆蓋達標 | 拓樸乾淨 |
|---|---|---:|---:|---:|---:|:--:|:--:|
| 光暈 | delaunay-v1-refined | 64 | 78 | 0.9796 | 0.9795 | ✅ | ✅ |
| 左手 | delaunay-v1-refined | 59 | 80 | 0.9642 | 0.9681 | ✅ | ✅ |
| 身體 | delaunay-v1-refined | 60 | 98 | 0.9660 | 0.9760 | ✅ | ✅ |

- 覆蓋達標判準:`我方 IoU ≥ 藝術家 IoU − 0.03`(對齊藝術家自身覆蓋,非武斷 0.95)。
- 頂點省下 18%(光暈)/ 26%(左手)/ 39%(身體);光暈覆蓋幾乎與藝術家一致(0.9796 vs 0.9795)。

## 三個關鍵校正 / 發現

1. **⚠️ Award mesh uvs 其實是 region 局部 [0,1],不是 atlas 全頁 UV**(STATE 舊註記有誤,已更正)。
   直接 `uvs*(W_img,H_img)` 落在 `atlas_crop` 切出的 region-local upright 圖上即對齊,**不需 Y 翻轉**
   (flip 會崩到 ~0.5)。實測 3 件藝術家 mesh 自覆蓋 0.968~0.980 → 對齊正確之證據(對齊錯會崩,已當自檢 AC)。
   *額外副產*:rotate=true 件(光暈/身體)以 region-local uvs 直接對齊 → **反證 `atlas_crop` 的 CW derotation 方向正確**(呼應 session 006 的 PSD 外部真值校正)。

2. **這 3 件在 Award 全部 12 動畫中無 deform timeline** → 靜態 weighted mesh(只靠骨變形)。
   故**沒有真實位移場可轉移**,本閘為**靜態**對照(覆蓋 + 拓樸),deform 閘對這幾件 N/A(誠實標註)。
   → 若要驗生成 mesh 的耐變形,仍以 main_draw 的 4 個有 deform 的窗簾/陰影 mesh 為準(見 s3-four-mesh-generalization)。

3. **v1 預設 `epsilon_frac=0.008` 對「大而圓的柔邊」件(光暈 706×683)邊界取樣過粗** →
   覆蓋 IoU 由**邊界近似**主導、偏低(35 頂點僅 0.933)。加入 **evaluator 驅動的覆蓋自收斂**
   (`generate_mesh_v2._delaunay_coverage_refine`):逐輪**減半 epsilon** 加密 hull 邊界點,
   接受條件 = 乾淨(0 退化/0 孤兒)且 IoU≥target 且 ≤ 頂點預算;光暈 3 輪內收斂到
   `eps=0.002 → 64v / IoU 0.9796`。中途 `eps=0.004/0.006` 會出 2 個孤兒頂點,故 refine 必須連拓樸一起判(只看 IoU 會選到有孤兒的網格)。

## 工具

- `tools/mesh_gen/compare_award_mesh.py` — 端到端對照閘(PSD 件 → gen v2 refine → 覆蓋 IoU vs Award 真實 mesh)。
- `tools/mesh_gen/generate_mesh_v2.py` — 新增 `generate(..., refine_coverage=True, target_iou, budget)`:
  v1 fallback 路徑的覆蓋自收斂;預設 `refine_coverage=False`(不影響既有 4 mesh 驗證,已回歸測試通過)。

## 教訓

- **覆蓋 IoU 對大/圓/柔邊件是「邊界主導」**,不是內部密度主導 → 調 epsilon(邊界)比加內部點有效
  (加內部點反而可能降 IoU,見 eps=0.008 時 mi=40→0.933 vs mi=60→0.904)。
- **評估器驅動自收斂 > 硬編一組參數**:同一 refine 迴圈對三件不同形狀都自動找到達標且乾淨的設定。
- **對齊必附自檢**:用「藝術家 mesh 自覆蓋必高」當內建負對照,揪出並更正了 STATE 的 atlas-UV 誤記。
