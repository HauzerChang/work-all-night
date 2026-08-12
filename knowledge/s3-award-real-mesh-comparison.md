# S3 端到端驗收:PSD件 → mesh → 對照 Award 真實生產 mesh

- **結論**:S3 生成器(`generate_mesh_v2` auto → delaunay 分支)對 Award 機器人 **3 件真實
  weighted mesh(光暈/身體/左手)覆蓋 IoU 皆 ≥ 藝術家生產 mesh,且頂點數持平或更少、0 孤兒**。
  這是第一次把 S3 對「真實生產 mesh 真值」做端到端對照(先前皆對藝術家自身或合成)。
- **關鍵修正**:delaunay 分支舊預設 `epsilon_frac=0.008` 對團塊件過粗 → 覆蓋率低於真值。
  收緊到 **0.002**(仍 < 藝術家頂點數)後三件全過。
- **信心**:高(有外部真值 = 生產 spine 的 uvs/triangles;量化 + 視覺雙證)。
- **階段**:第 2 階段 S3 / S4 串接。

## 對照設定

- **標的**:`assets/Award.json` 的 slot `機器人拆件/{光暈,身體,左手}`(皆 mesh、weighted、**無 deform
  timeline** → 靠骨骼驅動)。右手/頭為 region(剛體),不列入 mesh 對照。
- **遮罩空間**:用 `atlas_crop` 從 `Award.png/Award2.png` 切該 region(多頁 + rotate CW 已校正)。
  這正是藝術家 uvs 所在空間 → IoU 為 apples-to-apples。該 region 已於 session 005 驗證與
  `robot_parts.psd` 切件同一輪廓(alpha-IoU 0.92–0.99),故等同「PSD件」。
- **工具**:`tools/mesh_gen/compare_award_mesh.py`(標準指令,exit 0 = all pass)。
- **判準**(對照真值,非武斷絕對值):
  1. 覆蓋 IoU `mine ≥ artist_baseline`(藝術家 mesh 三角化覆蓋率,`artist_iou`)。
  2. 頂點預算 `mine ≤ artist`(效率:不比藝術家多用點)。
  3. 幾何健康:0 孤兒、0 退化三角、重心在遮罩內、格式合法。
  4. deform 閘 **N/A**(這批件無 deform timeline)。

## 量化結果(2026-08-12,預設設定)

| region | my IoU | artist IoU | my verts | artist verts | ratio | geom | PASS |
|---|---|---|---|---|---|---|---|
| 光暈 glow | 0.9832 | 0.9795 | 73 | 78 | 0.94 | clean | ✅ |
| 身體 body | 0.9926 | 0.9760 | 77 | 98 | 0.79 | clean | ✅ |
| 左手 hand | 0.9913 | 0.9681 | 67 | 80 | 0.84 | clean | ✅ |

視覺對照(藝術家橘 / 本工具綠,疊在 alpha 上):`knowledge/figures/award_mesh_{glow,body,lefthand}.png`。

## 覆蓋率定律的推廣(重要)

- 先前 strip 路徑發現「**IoU 由 rows(邊界取樣密度)決定,cols(內部點)不影響覆蓋率**」。
- 本次對 delaunay 路徑做 epsilon × 內部密度掃描,**同一定律成立**:
  覆蓋 IoU 由 **`epsilon_frac`(輪廓簡化容差 = 邊界取樣密度)** 單調決定,
  `min_dist`/`max_interior`(內部點數)對覆蓋率**無影響**。
- 掃描(光暈,artist=0.9795):eps 0.008→0.929、0.004→0.966、**0.002→0.983(過)**、0.001→0.992;
  三種內部密度在同 eps 下 IoU 幾乎不變(±0.005)。
- **設計啟示**:要提高覆蓋率就加**邊界**取樣;內部點是給**變形平滑度**用的,不是覆蓋率。

## 評估器校準(本次第 4 次抓到 miscalibration 類問題)

- `evaluate_mesh` 的絕對 `vertex_budget=64` **比真實生產還嚴**(藝術家用 78/98/80,全會 fail)。
- 對照真值時,頂點預算應以**藝術家頂點數**為參照,而非武斷 64。
  `compare_award_mesh.py` 已改成傳 `vertex_budget=art_nv` + 另判 `mine ≤ artist`。
- 教訓延續 RULES「閘要先校準」:絕對閾值在換標的(合成→生產)時要重新對真值校準。

## 產出 / 變更

- 新增 `tools/mesh_gen/compare_award_mesh.py`(端到端對照 harness)。
- 改 `tools/mesh_gen/generate_mesh_v2.py`:delaunay 分支預設 `epsilon` 0.008→0.002
  (加 `delaunay_epsilon` 參數;strip 路徑不受影響 → main_draw 4 mesh v2 驗證無回歸)。
- 圖:`knowledge/figures/award_mesh_{glow,body,lefthand}.png`。

## 未解 / 下一步

- 這批件無 deform → 未測「生成 mesh 在 weighted 骨骼驅動下的變形品質」。若要驗,需把
  Award 的骨綁 + 權重轉移到生成 mesh(BBW),超出本 chunk。
- 真正的「PSD→件→mesh」全鏈:目前用 atlas region 當遮罩(已證=PSD件輪廓)。若要純從 PSD 起,
  可接 `psd_slice` 輸出的件 PNG 直接跑(需處理 PSD↔atlas 的縮放/註冊),為可選加固。
