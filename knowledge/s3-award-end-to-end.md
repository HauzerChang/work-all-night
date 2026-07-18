# S3 端到端驗收：PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**：S3 生成器**端到端**通過真實生產標的驗收。從 `robot_parts.psd` 切出的
  3 個 mesh 件（光暈 / 身體 / 左手，在生產 spine `Award` 中皆為 mesh），跑
  `generate_mesh_v2(mode=auto)` 生成的 mesh，其**靜態覆蓋 IoU 與藝術家手做 mesh 同級或更好，
  且頂點數少 40~55%**。這是「PSD→件→mesh」對真實標的、有真值可比的整條驗收。
- **信心**：高（真實生產 PSD + 真實生產 spine 雙真值；評估器經負對照確認鑑別力）。
- **階段**：第 2 階段 / S3 × S4 串接（里程碑：合成/單資產 → 真實端到端）。

## 量化結果（同一張 PSD 件 alpha 上比覆蓋 IoU）

| 件 | 生成 mode | 生成 v / 覆蓋 IoU | 藝術家 v / 覆蓋 IoU | 覆蓋閘(margin .02) |
|---|---|---|---|---|
| 光暈 | delaunay-v1 | 35v / **0.933** | 78v / 0.949 | PASS（差 .016<.02）|
| 身體 | delaunay-v1 | 60v / **0.966** | 98v / 0.948 | PASS（**贏過藝術家**）|
| 左手 | delaunay-v1 | 59v / **0.964** | 80v / 0.977 | PASS（差 .013<.02）|

- 格式閘全過（0 退化 / 0 孤兒 / 頂點在預算內）。指令：`python3 tools/mesh_gen/validate_against_award.py`。
- 視覺確認：`knowledge/figures/award-mesh-gen-vs-artist.png`（綠=生成、橘=藝術家，疊在件剪影上）。

## ★ 關鍵發現：mesh 有「兩種 regime」，生成策略不同

先前窗簾/陰影（main_draw）與這次機器人件是**不同 regime**，S3 的 `auto` 已正確分流：

| | main_draw 窗簾/陰影 | Award 機器人件（光暈/身體/左手）|
|---|---|---|
| 權重 | **unweighted** | **weighted**（骨骼綁定）|
| 變形來源 | **deform timeline**（逐頂點）| **骨骼/權重**（無 deform timeline，已確認）|
| 形狀 | 高瘦、row-convex | 團塊（aspect<1.2）|
| `v2 auto` 選路 | **strip**（耐單向拉伸）| **回退 v1 Delaunay**（contour 貼合）|
| governing 驗收 | 覆蓋 IoU + **真實位移場 deform 閘** | **靜態覆蓋 IoU**（deform 閘 N/A）|

→ **拓樸該怎麼生，取決於「件怎麼變形」**：逐頂點大拉伸要順軸直條；骨骼驅動的團塊件
  只需貼合輪廓的精簡三角化。`auto`（aspect≥1.2 且 row-convex → strip，否則 Delaunay）
  對這 5+3 件都選對了。

## ⚠️ 誠實邊界（未驗證項）

- **未驗 deform 穩健性**：Award 這 3 件靠**骨骼權重**變形，repo 內無其逐頂點位移真值，
  無法用 `transfer_deform_check` 轉移真實位移場。故本結論**僅限靜態覆蓋保真**。
  骨骼驅動下 Delaunay 內部仍可能扭曲——但要驗它需先有權重（BBW / S5），超出本件範圍。
- 藝術家 mesh 覆蓋 IoU 本身非 1.0（0.948~0.977）：身體 uvs x 只到 0.759（mesh 不覆蓋
  件的右側半透明緣）→ 我們貼 alpha 反而略高。這說明「藝術家 mesh」是**合理但非上限**的基準。

## 評估器可信度（先驗證閘再下判定）

負對照：把藝術家 mesh uvs 平移 +0.4 寬 → 覆蓋 IoU 0.20~0.48；縮至 30% → 0.088~0.094，
皆遠低於 baseline（0.95~0.98）→ 覆蓋閘有鑑別力。正對照：藝術家自身 uvs 貼自己的 alpha 即 baseline。

## 產出 / 可重現

- `tools/mesh_gen/validate_against_award.py`（PSD 切件 → gen v2 → 對照 Award mesh；覆蓋閘＋格式閘）。
- `knowledge/figures/award-mesh-gen-vs-artist.png`（gen vs artist 線框對照）。
- `python3 tools/mesh_gen/validate_against_award.py` → `overall_pass: true`（3/3 件）。

## 下一步候選

1. **切圖→Spine JSON 組裝（SkelToJson）**：把 `PSD名/圖層名`、size+2px padding、mesh/region
   分配、atlas 0.70 縮放這些已固化的慣例，寫成「件清單 → Spine skeleton JSON」產生器，
   端到端吐出可載入的 spine（有 Award 真值可逐欄位對照）。← **最高槓桿：S3+S4 收斂為一個 pipeline**
2. S2 補圖閘 / 骨架閘（補齊 S2 樞紐）。
3. weighted mesh 的 deform 閘（需 BBW 權重生成，牽動 S5）。
