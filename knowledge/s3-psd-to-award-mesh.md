# S3 端到端驗收 — PSD 件 → generate_mesh_v2 → 對照 Award 真實藝術家 mesh

- **結論**:把 S3 mesh 生成器接到真實生產件上端到端驗收。對 `robot_parts.psd` 的
  **光暈 / 身體 / 左手** 三件(在生產 spine `Award.json` 中是藝術家手做的 weighted mesh)自動生成 mesh,
  對照藝術家真值:**輪廓形狀吻合 0.886–0.968、覆蓋 IoU 0.933–0.966、頂點數全 < 藝術家、拓樸全乾淨** →
  三件 `piece_pass` 全過,且負對照證明指標有鑑別力。**S3 在真實生產件上達到 ≈ 藝術家品質、更精簡。**
- **信心**:高(對真實生產藝術家 mesh 交叉比對 + 跨件負對照 + 視覺 overlay 三重確認)。
- **階段**:第 2 階段 / S3 × S4 串接(里程碑:S3 從合成/main_draw → 對真實生產標的驗收)。

## 做法(可重現)

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o <dir>          # 切件 PNG
python3 tools/mesh_gen/compare_to_award_mesh.py --pieces-dir <dir>           # 端到端對照(exit 0=全過)
```

四個機讀指標(見 `compare_to_award_mesh.py`):

| 指標 | 定義 | 真值 |
|---|---|---|
| **A 形狀吻合** | 藝術家 hull 多邊形 vs S3 hull 多邊形,各正規化到單位方形,取 8 種二面體對稱最佳 IoU | 藝術家 mesh |
| **B 輪廓覆蓋** | `evaluate_mesh` 三角填充 IoU vs PSD 切件 alpha | PSD alpha |
| **C 頂點預算** | S3 頂點數 ≤ 藝術家頂點數 | 藝術家 mesh |
| **D 拓樸** | 退化三角=0 / 孤兒=0 / 三角重心落 alpha 內 | — |

## 結果

| 件 | S3 模式 | A 形狀 IoU | B 覆蓋 IoU | C 頂點 S3/藝術家 | D 拓樸 |
|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 0.886 | 0.933 | **35 / 78** | ✅ 0退化/0孤兒/重心100%內 |
| 身體 | delaunay-v1 | 0.937 | 0.966 | **60 / 98** | ✅ |
| 左手 | delaunay-v1 | 0.968 | 0.964 | **59 / 80** | ✅ |

負對照(跨件形狀 IoU,應顯著低於同件):**同件最低 0.886 > 跨件最高 0.711**(gap≈0.18)→ 指標 A 有鑑別力。
視覺 overlay:`knowledge/figures/s3-vs-award-robot-mesh.png`(綠=hull、橙=三角、藍點=頂點,全貼合輪廓)。

## 關鍵發現 / 教訓

1. **這三件走 `delaunay-v1`(散點)而非 `strip`**:auto 模式判斷它們是不規則團塊(非高瘦 row-convex),
   自動退回 v1。**印證 v1/v2 分工正確**:窗簾類單向拉伸長條 → v2 strip 耐變形;不規則生產件 → v1 Delaunay 貼合更好。
2. **S3 比藝術家更精簡**:三件頂點數全少於藝術家(35<78 / 60<98 / 59<80),覆蓋卻不輸 → 自動生成沒有為求覆蓋而浪費頂點。
3. **本次只驗靜態(覆蓋/形狀/拓樸),未驗 deform**:此三件在 Award 是 **weighted mesh(靠骨骼權重變形,
   無 deform timeline)** → 沒有逐頂點位移場可轉移比對,deform 閘(真實位移場轉移)不適用。
   若要驗權重變形,需轉移 Award 的 bone binding(未做,屬下一課題)。
4. **刻意用二面體(旋轉/翻轉)不變的形狀 IoU**:atlas region 有 rotate 旗標(光暈/身體 rotate=true)、
   且 atlas_crop 曾出 CCW/CW 方向 bug。此處只問「形狀是否相同」,方向不列入判定 → 順帶避開旋轉方向雷點。
   (best_dihedral 三件皆=0/identity,代表 UV 與像素空間本就同向對齊,不變性沒有掩蓋錯配。)

## 侷限 / 下一步

- **未做**:weighted mesh 的骨骼權重轉移與骨骼驅動變形對照(需 BBW 權重 + Award bone binding 解析)。
- **未做**:texture 級 UV 對齊(本次形狀比對走 bbox 正規化 + 二面體不變,非 atlas 絕對座標對齊)。
- S3+S4 端到端(PSD→件→mesh)已對真實生產標的閉環驗收;下一個自然課題是 **S5 骨架/權重** 或
  把此對應慣例固化進「件→Spine JSON 組裝(SkelToJson)」。
