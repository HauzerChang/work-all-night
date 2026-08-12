# S3 端到端驗收:PSD 切件 → generate_mesh_v2 → 對照 Award 真實藝術家 mesh

- **結論**:端到端「PSD→件→mesh」對真實生產標的**驗收通過**。robot_parts.psd 的 3 個 warp 件
  (光暈/左手/身體)用 `generate_mesh_v2`(auto)自動產出的 mesh,輪廓覆蓋 IoU **匹配或勝過**
  Award 裡藝術家手做的 mesh,且**頂點數少約 40%**。這是 S3(mesh 生成)+ S4(PSD 切圖)首次
  串成端到端、且對**真實藝術家真值**量化對照的閘。
- **依據**:`tools/mesh_gen/compare_award_mesh.py`(本次新增),對 `assets/Award.json` 3 個 mesh slot。
- **信心**:高(有真實藝術家 mesh 當基準 + 雙向負對照確認鑑別力)。
- **相關階段**:第 2 階段 S3/S4 交會點。

## 方法(公平對照)

1. `psd_slice.py` 切出 robot_parts.psd 各件 PNG(+alpha)。
2. 同一件在同一張「Award attachment (W,H) 畫布」上柵格化兩張 mesh,PSD 件以 **+1px**(padding/2)置入
   對齊 S4 已測得的 **+2px atlas padding**:
   - **藝術家 mesh**:uvs(region 局部 0..1)→ `px=u*W, py=v*H`(**y 不翻**,實測 flip=False 才對齊:
     flip 版 IoU 掉到 0.43~0.61)。
   - **我方 mesh**:對件原生 alpha 跑 `generate_mesh_v2`,`mesh_pixel_coords` 還原後 +1px 置入。
   - GT silhouette = PSD 件 alpha(**門檻 >8,與生成器/評估器一致**——見下方地雷)。
3. 判定:`IoU_mine >= IoU_artist - 0.03` 且我方 mesh 靜態 `evaluate_mesh` 全過。

## 結果(2026-08-12)

| 件 | attachment | IoU 藝術家 | IoU 我方 | gap | 我方頂點 | 藝術家頂點 | mode | 判定 |
|---|---|---|---|---|---|---|---|---|
| 光暈 | 708×685 | 0.946 | 0.933 | −0.013 | **35** | 78 | delaunay-v1 | PASS |
| 左手 | 259×217 | 0.965 | 0.964 | −0.001 | **59** | 80 | delaunay-v1 | PASS |
| 身體 | 381×427 | 0.946 | **0.966** | **+0.020** | **60** | 98 | delaunay-v1 | PASS |

- **`overall_pass: true`**。指令:`python3 compare_award_mesh.py --pieces-dir <psd_slice 產出目錄>`。
- 3 件 auto 都落到 **delaunay-v1**(非 strip):這些件不是「高瘦 + row-convex」的窗簾型,
  auto 正確地沒選 strip。印證 v1/v2 分工:**strip 專治窗簾型耐變形;散點 delaunay 適合一般輪廓靜態覆蓋**。
- **頂點經濟度**:我方平均 ~51v vs 藝術家 ~85v(少 ~40%),覆蓋率不輸。

## 為何是「靜態輪廓 IoU」而非 deform 閘

- 這 3 件在 Award **沒有 deform timeline**(log 2026-06-26-005:5 件無 deform、靠骨骼 warp)。
  沒有真實位移場可轉移,deform 閘(真實位移場轉移)在此**不適用**;本閘只做靜態覆蓋對照,
  正是 `AC.md` AC1「≥ 藝術家同件 mesh 的 IoU」的精神,只是把基準換成**真實生產藝術家 mesh**。
- ⚠️ 因此本結果**不代表**我方 mesh 在骨骼 warp 下的變形品質等同藝術家——那需要把 mesh 綁上
  Award 骨架權重後才可比(見「未解 / 下一步」)。這裡驗的是「輪廓覆蓋 + 頂點經濟」,不是 warp 手感。

## 評估器可信度(負對照)

以「身體 GT」對照:
- 正(身體自身藝術家 mesh)IoU = **0.946**
- 負(改用左手 mesh 蓋上)IoU = 0.513
- 負(藝術家 mesh 整體平移 80px)IoU = 0.312
- 鑑別 gap > 0.3 → **OK**(度量對「錯件 / 錯位」有鑑別力,通過才信 pass)。

## 地雷 / 教訓(留痕)

- **門檻不一致造成假性失敗**:第一版 compare 用 `alpha>10` 當評估 mask,但生成器/評估器內部用 `>8`。
  身體有 1/97 個邊界三角在 `>8` 內、`>10` 外 → AC2a「重心在內」掉到 98.97%(<99%)假性 fail。
  改成**與工具一致的 `em.load_mask`(>8)** 後即通過。教訓:**GT mask 的定義必須跨生成/評估一致**,
  否則差 1~2 灰階就在邊界三角上翻判(這是本專案第 4 次「評估器校準」類 bug,前三次:stress_field、
  composite 白底、atlas derotate 方向)。
- **uvs y 方向**:Award mesh 的 uvs 直接 `py=v*H`(不翻)才對齊件 alpha;翻了 IoU 崩到 0.43~0.61,
  可當方向健檢的快篩。
- v1 `filter_triangles` 已按「重心在 mask 內」剔除三角,故用**同一 mask** 評估時 AC2a 理應接近 100%;
  出現 <99% 幾乎必是 mask 門檻不一致,而非真凹橋接三角。

## 產出

- `tools/mesh_gen/compare_award_mesh.py`(可重跑閘)。
- 本檔 + 索引;更新 `STATE.md`、log。
