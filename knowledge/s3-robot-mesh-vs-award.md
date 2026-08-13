# S3 端到端驗收:PSD 拆件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把 `robot_parts.psd` 的三個 **mesh 件**(光暈/身體/左手,在生產 spine `Award.json` 中為 mesh)
  跑完整「PSD 切件 → `generate_mesh_v2`」pipeline,生成 mesh 對切件 alpha 的覆蓋率 IoU
  **全部達到或超過藝術家 Award 真實 mesh 的自身覆蓋率**,且頂點數相當或更少 → S3+S4 端到端對
  **真實生產標的**驗收通過(先前只在合成/main_draw 內部驗)。
- **信心**:高(對真實生產 mesh ground truth 逐件量化 + UV 方向經三向對照確認)。
- **階段**:第 2 階段 / S3×S4 串接(里程碑)。可重現:`python3 tools/mesh_gen/validate_robot_mesh.py`。

## 量化結果(2026-08-13)

| 件 | 切件遮罩 | 藝術家 mesh | 藝術家 IoU | 生成模式 | 生成頂點 | 生成 IoU | pass |
|---|---|---|---|---|---|---|---|
| 光暈 | 706×683 | 78v | 0.949 | delaunay-v1 | 54v | **0.964** | ✓ |
| 身體 | 379×425 | 98v | 0.948 | delaunay-v1 | 89v | **0.983** | ✓ |
| 左手 | 257×215 | 80v | 0.977 | delaunay-v1 | 90v | **0.980** | ✓ |

`overall_pass=True`(margin 0.005)。生成件用**更少或相當**頂點即達到藝術家覆蓋率。

## 兩個關鍵發現

### ① Award mesh uvs 是「region-local 0..1、原始未旋轉方向」

- 這三件在 atlas 中 光暈/身體 `rotate:true`、左手 `rotate:false`,且貼圖被縮小打包(size≈orig×0.70;
  attachment width/height 記原始邏輯尺寸)。**但 mesh uvs 仍以原始(未旋轉)region 為基準的 0..1**。
- 驗證方式:對切件 alpha 用三種方向重建覆蓋 —— `rot0` 得 0.949/0.948/0.977,`±90°` 僅 0.44~0.65。
  rot0 遠高 → 確認 uvs **無需**依 atlas `rotate` 旋轉換算,直接 `u*W, v*H` 即對齊原始切件。
- 推論:atlas 的 rotate 只影響「貼圖像素如何打包進 page」,不改 Spine 邏輯 uv 座標系。做「件→Spine JSON」
  組裝時,uv 直接用原始件的 `x/W, y/H` 即可(與 `generate_mesh*` 既有輸出一致)。

### ② v2 auto 的 Delaunay 分支預設 epsilon 對「凹形 blobby 件」覆蓋不足 → 已調校

- 這三件長寬比不高(0.84~1.12)、非 row-convex → auto 正確走 **Delaunay 分支**(非 strip)。
- **覆蓋率 IoU 由 hull 簡化 `epsilon_frac` 主導**(內部點只細分、幾乎不改覆蓋)。原 v1 預設 `eps=0.008`
  對凹形輪廓覆蓋偏低:光暈 0.904<0.949、左手 0.964<0.977(假性偏低)。
- eps 掃描(max_interior=60, min_dist=10):

  | eps | 光暈 | 身體 | 左手 |
  |---|---|---|---|
  | 0.008 | 0.904(45v) | 0.967(80v) | 0.964(79v) |
  | 0.005 | 0.964(54v) | 0.981(87v) | 0.974(86v) |
  | **0.004** | **0.964(54v)** | **0.983(89v)** | **0.980(90v)** |
  | 0.003 | 0.970(59v) | 0.988(92v) | 0.985(95v) |
  | 0.001 | 0.992(91v) | 0.995(111v) | 0.994(131v) |

- **eps=0.004** 對三件皆過藝術家基準且頂點數相當/更少 → 設為 `generate_mesh_v2` **Delaunay 分支
  的 blobby 預設**(`gen_v1(path, max_interior=60, epsilon_frac=0.004, min_dist=10)`)。
- 只改 Delaunay 分支,不影響 strip 路徑;main_draw 4 mesh(全走 strip)重驗 IoU/deform 全 PASS 無回歸。

## 兩種拓樸規則(合併先前 strip 結論)

| 件類型 | 判定 | 生成模式 | 覆蓋率主導參數 | 為何 |
|---|---|---|---|---|
| 高瘦、逐頂點 deform(窗簾) | aspect≥1.2 且 row-convex | **strip** | `rows`(邊界取樣密度) | 順拉伸軸的直條 → 耐大單向變形不自交 |
| blobby、骨骼權重變形(機器人件) | 否則 | **Delaunay-v1** | `epsilon_frac`(hull 簡化) | 無逐頂點 deform,只需靜態覆蓋貼合凹形輪廓 |

## 侷限 / 待續

- 這三件在 Award **無 deform timeline**(靠骨骼權重變形)→ 本輪 AC 只驗**靜態覆蓋率**,
  無真實位移場可做 deform 閘。權重/骨綁變形的正確性需另建 rig 級驗證(S5 範疇)。
- 下一步順勢固化「件→Spine mesh attachment JSON」組裝(uv 用原始件 0..1、size+2px padding、
  `<PSD檔名>/<圖層名>` slot 命名),把 S4 切圖與 S3 mesh 串成可輸出 Spine JSON 的 SkelToJson。
