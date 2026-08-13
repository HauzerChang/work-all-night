# S3 端到端驗收:PSD 機器人件 → generate_mesh_v2 → 對照 Award 真實生產 mesh

> 結論:**S3 生成器對真實生產標的(Award 機器人 3 個 mesh 件)端到端通過** —— 生成 mesh 的覆蓋率
> 追平/超越藝術家 mesh,且頂點更省。過程順帶(a)修正 log 006 的 UV 誤解、(b)修掉 v1 兩個生成缺陷。
> 依據:`tools/mesh_gen/robot_mesh_gt.py`(可重跑,exit 0 = 全過)。信心:高(有藝術家真值 + 負對照)。
> 相關階段:專案第 2 階段 S3;串接 S4(PSD 切圖)→ S3(mesh)端到端。

## 標的與方法

- `robot_parts.psd`(big win 主角)5 圖層 ⇄ Award spine slot `機器人拆件/<圖層名>`(log 005)。
- 其中 **3 件是 weighted mesh**:`光暈`(78v/76tri/hull78,全 hull)、`左手`(80v/116tri/hull42)、
  `身體`(98v/154tri/hull40)。另 2 件(右手/頭)是 region+旋轉(剛體)。
- ground truth = Award 這 3 個藝術家 mesh 的**覆蓋率**(把其 uvs/triangles 填入 region alpha 算 IoU)。
- 對照對象 = 對**同一份 atlas region 切件 alpha** 跑 `generate_mesh_v2`(auto)後的覆蓋率。

## 關鍵校正 1:Award mesh 的 uvs 是「region 局部 0..1」,不是 atlas 頁 uv

log 006 曾推測「Award mesh uvs 為 atlas UV,需先轉 region 局部」。**實測推翻**:3 件的 u、v 皆
滿佈 0..1(例:左手 u∈[0.008,1.0]、v∈[0.004,1.0]),若是整頁 uv 則 181px 件在 2040px 頁上
u 只會跨 ~0.09。→ **正確映射就是 `col=u·cropW, row=v·cropH`(v 為 top-down,對齊影像座標)**,
對 atlas_crop derotate 後的切件即可。負對照 = v-flip,IoU 由 0.97→0.44~0.61 明顯崩壞,確認映射方向。

- 副產:映射高覆蓋(0.976~0.980)**再次確認 atlas_crop 的 CW derotate 正確**(旋轉件若方向錯,
  覆蓋率會像 v-flip 一樣崩掉)—— 與 log 006 用 PSD 外部真值得到的結論一致,獨立第二證。

## 關鍵校正 2:v1 生成器兩個缺陷(本 session 修掉)

初跑 3 件:左手/身體通過,但 **`光暈`(大而平滑的圓形光暈)fail**,暴露 v1 兩個問題:

1. **孤兒頂點**(evaluate_mesh AC2c):`filter_triangles` 依「重心在 mask 內」刪凹形外三角後,
   某些點失去所有相鄰三角 → 孤兒。**修法**:`drop_orphans()` 移除未引用頂點並重映射索引;
   `used` 升冪排序 → hull(<n_hull)恆排在 interior 前,hull-first 順序不變,n_hull 依實留數更新。
2. **邊界簡化對平滑曲邊覆蓋不足**:以「周長比例」當 approxPolyDP epsilon,對周長長的大曲邊件
   得到過大絕對容差 → glow 被簡化成 **14 邊形、IoU 僅 0.93**。**修法**:`boundary_points()` 改
   **自適應**——由粗到細降 epsilon,取「填充多邊形覆蓋達標(預設 0.985)」的最粗解,並以
   `hull_cap = budget-8` 為上限;達不到就取上限內最細解。對已是角狀的件粗 epsilon 就達標、不過度增點。
   - 配套:`generate()` 改吃 `vertex_budget`(預設 64),`interior_budget = budget - len(hull)`,
     hull 追曲邊後仍能保住總頂點預算。

> glow epsilon 掃描實測(佐證):eps_frac 0.008→hull14/IoU0.93/1孤兒;0.004→22/0.966/0;
> 0.002→38/0.983/0(但 nv73 超 64);自適應 =「在 64 預算內把覆蓋最大化」的落點。

## 最終結果(全過,exit 0)

| 件 | rotate | 藝術家 IoU(真值) | v-flip 負對照 | 生成 IoU | margin | 生成 nv / 藝術家 nv | orphans |
|---|---|---|---|---|---|---|---|
| 光暈 | true | 0.980 | 0.440 | **0.987** | +0.007 | 64 / 78 (82%) | 0 |
| 左手 | false | 0.968 | 0.595 | **0.990** | +0.022 | 64 / 80 (80%) | 0 |
| 身體 | true | 0.976 | 0.607 | **0.988** | +0.012 | 64 / 98 (65%) | 0 |

- **三件生成 mesh 覆蓋率皆 ≥ 藝術家、頂點數皆更省(65~82%)**;format 全合法、0 孤兒、0 退化、≤預算。
- 無回歸:main_draw 4 mesh(v2 strip,不走 v1 邊界)`validate_against_real --gen v2` 全 `overall_pass`;
  合成 curtain gen+eval 全過;v1 直呼不 crash。

## 尚缺 / 下一步(重要)

- **3 件真值都是 weighted mesh(綁骨、無 deform timeline)** —— 靠骨骼 warp,不是 deform 位移場。
  本 session 只驗到**拓樸/靜態覆蓋率**;要真正取代生產 mesh,S3 還缺 **BBW 骨權重生成**(路線圖既定項)。
  → 下一個能力缺口明確:給生成的 unweighted 拓樸配骨、算 BBW 權重,再對 Award 真值做「綁骨後 warp」比對。
- 因 3 件長寬比(0.84/0.97/1.12)未達 strip 門檻(≥1.2),全走 **v1 Delaunay fallback**;v1 經本次
  自適應邊界 + 孤兒修正後,對這類非長條件已達生產覆蓋水準。
- 工具:`tools/mesh_gen/robot_mesh_gt.py`(端到端真值閘,可重跑續驗)。
