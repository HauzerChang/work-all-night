# S3 v3 輪廓貼合生成器 + PSD→件→mesh 端到端對照 Award 真實 mesh

- **結論**:新增 **v3(輪廓 hull + 規則內部格點 + 約束 Delaunay)** 生成器,對「緊湊凸形生產件」
  同時達成**高覆蓋率(≈/勝藝術家)**與**變形穩健(0 自交/0 翻面)**,補上 v1/v2 對這類件的雙缺口。
  以此把 **S4(PSD 切件)＋S3(mesh 生成)** 串成端到端,並對**真實生產標的**(Award 藝術家 mesh)驗收通過。
- **依據**:新閘 `tools/mesh_gen/validate_psd_to_award.py`;真值 = `robot_parts.psd` 三個 mesh 件
  (光暈/身體/左手)在生產 spine `Award` 裡的藝術家 weighted mesh。
- **信心**:高(對照真實生產 mesh;評估器先自校準:藝術家 mesh 對自身紋理覆蓋率 0.97~0.98 合理)。
- **相關階段**:第 2 階段(S3 mesh 生成)＋ S3×S4 整合。日期 2026-08-16。

## 背景:v1/v2 對緊湊件的雙缺口(端到端對照才暴露)

機器人三件都是 **row-convex 且 col-convex 的緊湊凸形**(aspect 0.84~1.12,fill 0.47~0.68),
不是窗簾那種高瘦條狀,所以:

- **v2 的 strip 模式從不觸發**(gate 要 aspect≥1.2)→ 一律回退 **v1 Canny 散點 Delaunay**。
- **v1 缺口**:覆蓋率對柔邊 blob 不足(光暈 0.933 < 藝術家 0.98),且拓樸不規則,
  轉移真實位移場下**自交**(左手 10 self-int / 3 flips)。
- **強制 strip 也不行**:變形乾淨,但多邊形上下蓋只用單列取樣 → 曲面 blob 覆蓋率封頂
  ~0.93(光暈/身體),提高 rows 到 28 仍 <0.95。**strip 只適合沿拉伸軸的高瘦件(窗簾)**。

## v3 做法(=藝術家實際做法 / SpriteToMesh)

1. `cv2.findContours` 取最大外輪廓 → `approxPolyDP` 二分 epsilon 逼近成 ~`target_hull` 點的 hull
   (**貼合曲面邊界** → 覆蓋率上得去)。
2. 內部佈**規則格點**(lattice,格距≈邊界對角/9;只留輪廓內且離邊界≥0.35×格距者,避免貼邊細長三角)。
3. hull 當 PSLG 邊界做**約束 Delaunay**(`triangle` 'pYY':不加 Steiner 點、保留輸入頂點、輸入序不變)。
   → hull 排 vertices 最前(Spine 格式);內部**規則格**比散點**耐拉扯**。

`target_hull=40` 為三件共同甜蜜點(hull~32 時內部格相對太疏,左手出現 7 self-int;hull=40 全乾淨)。

## 端到端結果(`validate_psd_to_award.py`,margin=0.03)

| gen | 光暈 cov | 身體 cov | 左手 cov | 左手 deform | overall |
|---|---|---|---|---|---|
| v1 / v2(皆退回 delaunay) | 0.933 **F** | 0.966 P | 0.964 P | 10 self-int **F** | **False** |
| **v3 contour-grid** | **0.979** P | **0.992** P | **0.988** P | **0 self-int** P | **True** |

藝術家基準:光暈 0.980(78v)/ 身體 0.976(98v)/ 左手 0.968(80v)。
v3 覆蓋率**≈或勝**藝術家,頂點數更省(51/54/58 < 78/98/80),轉移真實場(main_draw curtain_left
最大位移幀)後 **0 自交 / 0 翻面**。

## 評估器可信度(先校準再判定,遵 RULES)

- 藝術家 mesh 對自身 atlas region alpha 覆蓋率 0.968~0.980(合理,非 1.0 因 hull 略內縮)→ 基準可信。
- **踩到並修正的雷**:Award mesh 的 `uvs` 是 **region-local [0,1]**(非 atlas-page 正規化;
  數值確認 raw uv≈0..1)。初版誤當 page 正規化 → 身體 artist_iou=0.0 假象。改直接對 atlas_crop
  還原(de-rotate upright)的 region 點陣圖量測後,基準恢復合理。v-origin(y-up/down)自校準取較高者。
- 誠實聲明:gen 覆蓋率量在 **PSD 件** 自身紋理空間,artist 量在 **atlas region** 空間;兩者為同素材
  (PSD↔atlas alpha-IoU 0.92~0.99,見 s4-psd-to-spine-real.md),IoU 為比例量(尺度不變)故可比。
- AC3 是**轉移真實位移場的穩健性探針**(這些件在 Award 無 deform timeline、靠 weighted 骨骼變形),
  非其真實變形;但「轉移平滑場即自交」足以判定拓樸脆弱(v1 左手)。

## 生成器選擇政策(現況)

- **高瘦、沿拉伸軸的 row-convex 件(窗簾)** → **v2 strip**(已對 main_draw 4 mesh 驗證、沿拉伸軸最穩)。
- **緊湊凸形件(機器人光暈/身體/左手類)** → **v3 contour-grid**(本次驗證)。
- 未驗:v3 對高瘦窗簾、對凹形/多連通件的表現(下一步候選)。

## 檔案

- 新增 `tools/mesh_gen/generate_mesh_v3.py`(`generate(path, target_hull=40, grid_step=None)`)。
- 新增 `tools/mesh_gen/validate_psd_to_award.py`(端到端整合 AC;`--gen v1|v2|v3`,預設 v3)。
- 標準指令:`python tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts`
  → `python tools/mesh_gen/validate_psd_to_award.py`(exit 0 = 三件全 overall_pass)。
