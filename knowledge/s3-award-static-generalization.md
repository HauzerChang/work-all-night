# S3 對第二個真實資產(Award 機器人拆件)靜態驗收 + v1 epsilon 修正

> 結論:S3 mesh 生成器**推廣到第二個真實生產資產**(Award 機器人),且首次涵蓋
> **v1 Delaunay 路徑對「weighted / 無 deform / blob 形」真實 mesh** 的驗收。
> 過程揪出並修正 v1 的一個取樣缺陷。信心:高(對藝術家真值量化 + 視覺確認)。相關階段:S3 / S2。

## 為什麼要做這個(與 main_draw 的差異)

先前 S3 只對 `main_draw` 4 個 mesh 驗收,而那 4 個都是:**unweighted + strip 形 + 有 deform timeline**,
全走 v2 strip 路徑。Award 的機器人 3 個 mesh 恰好相反,是第一次真實驗收 v1 Delaunay 路徑:

| 面向 | main_draw(4 mesh) | Award 機器人(3 mesh) |
|---|---|---|
| 綁定 | unweighted | **weighted**(靠骨骼權重動) |
| 變形來源 | deform timeline | **無 deform**(骨骼帶動,5 件無 deform) |
| 形狀 | 高瘦 strip | **blob**(光暈/身體/左手) |
| 生成路徑 | v2 strip | **v1 Delaunay(auto 回退)** |

→ deform 閘**不適用**(無 deform timeline)。改建**靜態幾何對照**驗收。

## 驗收工具:`tools/mesh_gen/validate_award_static.py`

對每個 mesh 件:atlas 裁 region(藝術家 mesh 的精確來源貼圖)→ `generate_mesh_v2(auto)` →
1. **覆蓋率 IoU**:生成 mesh 三角面 vs alpha,對照「藝術家 mesh 自身覆蓋率」baseline(margin 0.03)。
2. **頂點預算**:生成頂點數 ≤ 藝術家 × 1.5(精簡度)。
3. **hull 多邊形 IoU**:生成外周 vs 藝術家外周(輪廓貼合度,參考指標)。
- 藝術家覆蓋率同樣只用 `uvs/triangles`,故 weighted mesh 也適用(權重不影響靜態覆蓋)。

## 揪出並修正:v1 的 DP epsilon 對「大而平滑輪廓」取樣不足

初測 3 件裡 **光暈(soft glow)覆蓋率 0.929 < 目標 0.950 fail**;身體/左手過。
根因:v1 `boundary_points` 用 **周長比例** 的 Douglas-Peucker epsilon(`epsilon_frac=0.008`),
即容差 = 0.008 × 周長。**輪廓越大越平滑,絕對容差越大 → 用大弦切掉圓弧 → 覆蓋率掉**。
光暈是大而圓滑的件,受害最深(hull 只剩 14 點)。

epsilon 掃描(光暈,藝術家 baseline=0.9795):

| epsilon | hull | verts | cov_IoU |
|---|---|---|---|
| 0.008(舊預設) | 14 | 54 | 0.9292 ❌ |
| **0.005(新預設)** | 21 | 60 | **0.9629 ✅** |
| 0.003 | 32 | 68 | 0.9779 |
| 0.001 | 58 | 92 | 0.9924 |

**修正**:`generate_mesh.py` 預設 `epsilon_frac` 0.008 → **0.005**(函式 + CLI)。

## 修正後結果(全 PASS)

| 件 | 模式 | 生成頂點 | 藝術家頂點 | 覆蓋率 | baseline | hull IoU | 判定 |
|---|---|---|---|---|---|---|---|
| 光暈 | v1 Delaunay | 60 | 78 | 0.9629 | 0.9795 | 0.954 | ✅ |
| 身體 | v1 Delaunay | 68 | 98 | 0.9834 | 0.9760 | 0.965 | ✅ |
| 左手 | v1 Delaunay | 53 | 80 | 0.9755 | 0.9681 | 0.956 | ✅ |

- 生成頂點數皆 << 藝術家(精簡度佳,預算充裕)。身體/左手覆蓋率甚至**超過**藝術家 baseline。
- 視覺確認:`knowledge/figures/award-robot-mesh-v1.png`(hull 貼合、三角乾淨覆蓋)。

## 無回歸

epsilon 只影響 v1 Delaunay 路徑。main_draw 4 個 mesh 全走 v2 strip → 不受影響,重驗數字與里程碑一致
(curtain_left 0.9338 / curtain_right 0.9335 / shadow 0.9549,deform 全乾淨)。
(`image/shadow2` slot 與 `image/shadow` 共用同一 region,經 shadow 一併涵蓋。)

## 教訓 / 對後續的意義

- **周長比例 epsilon 不是尺度不變的**;大平滑件被系統性欠取樣。0.005 為目前跨 7 個真實 mesh
  (4 strip + 3 blob)的穩健預設;若未來遇更大更圓滑件,可考慮改「絕對像素容差 + 比例上限」。
- **S3 現已對兩個真實生產資產、兩條生成路徑(strip/Delaunay)、weighted/unweighted 皆驗收通過** →
  端到端「真實件 → mesh」對生產標的的靜態保真已建立。
- 尚缺:Award 機器人件的**變形**驗收無法用 deform timeline(無);若要驗其耐變形,需另建「骨骼權重
  帶動」的變形模型(未來 S5 骨架 + weighted deform)才有真值可比。
