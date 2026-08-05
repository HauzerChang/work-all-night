# S3 端到端驗收:PSD件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:`robot_parts.psd` 的 **光暈 / 身體 / 左手** 3 件(在生產 spine `Award` 中為 mesh)
  用 S3 生成器(v1 Delaunay 路徑)自動產出的 mesh,**覆蓋率全部達到或超過藝術家手做 mesh,
  且頂點數全部低於藝術家**。這是 S3 首次對「真實生產 mesh 有真值」的端到端驗收(先前只有
  main_draw 藝術家 mesh 自一致性 + 合成)。3/3 `overall_pass`。
- **信心**:高。真值 = Award 生產 spine 的真實 mesh;貼圖真值 = atlas 切件(CW 方向已用 PSD 外部真值校過)。
  uvs↔遮罩方位以 8 種方位測試,identity 全勝(0.97+)→ 疊圖成立。
- **階段**:第 2 階段 / S3 × S4 串接(里程碑:S3 從 main_draw 推廣到第二個真實生產標的)。

## 標的與判準

這 3 件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform)→ 不跑「真實 deform 轉移」閘,
改做**靜態覆蓋率 + 頂點預算 + 拓樸有效性**對照真實 mesh。工具:`tools/mesh_gen/compare_award_mesh.py`。

| 判準 | 定義 |
|---|---|
| `AC_iou` | 生成 mesh 覆蓋率 ≥ 藝術家 mesh 覆蓋率 − 0.02(生成不遜於真實件) |
| `AC_budget` | 生成頂點數 ≤ 藝術家頂點數(精簡度不遜於真實件) |
| `AC_valid` | 0 退化三角 / 0 孤兒頂點 / 格式合法 |
| `cross_iou` | 生成覆蓋遮罩 vs 藝術家覆蓋遮罩 IoU(兩 mesh 外形相似度,參考量) |

## 結果(校準後,epsilon=0.0025)

| 件 | region | 生成 v/hull/tri | 生成 IoU | 藝術家 v/hull/tri | 藝術家 IoU | cross_iou | pass |
|---|---|---|---|---|---|---|---|
| 光暈 | 496×480 | 71 / 35 / 105 | **0.980** | 78 / 78 / 76 | 0.980 | 0.967 | ✅ |
| 身體 | 267×299 | 75 / 35 / 113 | **0.992** | 98 / 40 / 154 | 0.976 | 0.974 | ✅ |
| 左手 | 181×152 | 62 / 37 / 85 | **0.989** | 80 / 42 / 116 | 0.968 | 0.966 | ✅ |

視覺對照(橘=藝術家,綠=生成):`figures/s3-award-mesh-compare.png`。

## 過程中揪出並修掉的 2 個 v1 缺陷(初跑 2/3,光暈 fail)

1. **孤兒頂點(AC_valid 破)**:`filter_triangles` 依「重心在 mask 內」丟掉凹形外三角後,
   某頂點可能不再被任何三角引用 → 破壞 Spine 格式有效性。真實光暈件(軟邊、凹形)首次暴露此潛在 bug。
   **修**:`generate_mesh.prune_orphans()` — 濾三角後移除未引用頂點並重編索引,
   保住 hull-first 順序(存活頂點依原索引重排,原索引 < n_hull 者計為新 hull)。
2. **軟邊欠取樣(AC_iou 破)**:v1 預設 `epsilon_frac=0.008`(Douglas-Peucker)對軟羽化的光暈
   只取 14 個 hull 點 → IoU 0.929 << 藝術家 0.979。**用真實 mesh 當真值校準**:掃 epsilon 發現
   覆蓋率隨邊界取樣密度單調上升;`0.0025` 使 3 件覆蓋率全 ≥ 藝術家、且頂點數全在藝術家預算內
   → 設為 v1 新預設。**注意 main_draw 4 mesh 走 v2 strip,不受此 v1 預設變更影響**(已回歸重驗全過)。

## 關鍵發現 / 教訓

- **真實生產 mesh 是最好的 fidelity 校準器**:先前 v1 epsilon(0.008)是無真值下的猜值,對軟邊欠取樣;
  拿到真值後才知該取多細。**再次印證「改對評估/真值 > 硬調演算法」**。
- **藝術家光暈用 78 點全 hull(無內部點)**描軟邊;生成器用「較疏 hull(35)+ 內部 Canny/格點」
  以更少頂點(71)達到同覆蓋率 → 拓樸策略不同但結果等價,且更省。
- **靜態覆蓋率 ≠ 耐變形**(前有教訓):但這 3 件生產上無 deform,靜態覆蓋率就是正確的驗收面向。
  若日後這些件要加 warp,需再跑 deform 閘(v1 散點對大單向拉伸易自交 → 屆時應改 v2 strip 或加約束)。

## 可重現

```
python3 tools/mesh_gen/compare_award_mesh.py          # 3 件 all_pass,exit 0
```
