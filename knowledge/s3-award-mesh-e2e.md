# S3 端到端驗收 — 機器人 3 mesh 件 對照 Award 藝術家真值(+ 自適應 epsilon 修正)

- **結論**:把 S4 切件 → S3 `generate_mesh_v2` → 對照真實生產 spine(`Award`)的藝術家 mesh,
  **3 個 mesh 件(光暈 / 左手 / 身體)全部 PASS**:覆蓋率不輸藝術家(在 margin 內)、頂點數更精簡、
  0 孤島 / 0 退化。這是 **S3+S4 首次對「真實生產標的 + 藝術家真值」端到端驗收**(里程碑)。
- **關鍵發現(並已修)**:光暈(放射狀光暈,高曲率輪廓)一開始 **FAIL** — v1 Delaunay 預設
  `epsilon_frac=0.008` 把 hull 過度簡化(hull=14),`filter_triangles` 在凹口挖掉三角 → 覆蓋率僅 0.934
  + 留 1 個未覆蓋孤島。**修法:v1 fallback 改自適應 epsilon**(由粗到細,取達覆蓋目標且 0 孤島中最省頂點者)。
- **信心**:高(對真實生產 spine 的 3 個 mesh 逐件量化 + 藝術家重建經自一致性/視覺雙重校驗;
  main_draw 4-mesh 基準未回歸)。
- **階段**:第 2 階段 / S3+S4 串接(里程碑)。

## 驗收數字(margin=0.03,覆蓋率對 SIL 256² 正規化 IoU)

| 件 | rotate | 藝術家 v/hull | 藝術家 cover | S3 v/hull | S3 cover | 孤島 | piece_pass |
|---|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | true | 78 / 78 | 0.982 | **61 / 22** | 0.969 | 0 | ✅ |
| 機器人拆件/左手 | false | 80 / 42 | 0.975 | **52 / 24** | 0.959 | 0 | ✅ |
| 機器人拆件/身體 | true | 98 / 40 | 0.983 | **61 / 21** | 0.968 | 0 | ✅ |

- 三件 S3 mesh 覆蓋率均 ≥ 藝術家−0.03,且頂點數 52~61 << 藝術家 78~98 → **更精簡且不輸覆蓋**。
- 圖:`knowledge/figures/s3-award-mesh-compare.png`(silhouette | 藝術家線框 | S3 線框)。

## 兩個方法論要點(留痕)

### 1. 藝術家 mesh 重建要「方向穩健」+ 自一致性校驗
- Award mesh 的 `uvs` 實測為 **region-local(~0-1)**,非 page-global atlas UV
  (先前 `s4-psd-to-spine-real.md` 記為「atlas UV 需轉 region 局部」— 本次實測更正:已是 region-local)。
- 但 rotate=true 的件(光暈/身體),region-local uv 的軸向相對「去旋轉切件(atlas_crop CW)」有 90° 歧義。
  → 重建藝術家覆蓋時做 **8 個二面體(dihedral)朝向搜尋**,挑與 silhouette IoU 最佳者,不猜方向。
- **可信度校驗**:三件藝術家 mesh 對自身 silhouette 覆蓋 = 0.975 / 0.982 / 0.983(全高、best=r0)→
  重建可信,才拿它當 S3 的比較基準。(呼應專案守則:評估器/真值先自校驗再下判定。)

### 2. deform 閘不適用本批 → 靜態幾何為主
- 機器人 5 件在 Award **無 deform timeline**(靠骨骼權重變形,非逐頂點 deform),
  故不做 `deform_eval` 真實位移場轉移;AC 聚焦「靜態輪廓覆蓋 + 頂點預算 + 拓樸乾淨」。

## S3 修正:v1 自適應 epsilon(`generate_mesh_v2.gen_v1_adaptive`)

- 由粗到細掃 `eps_schedule=(0.008,0.006,0.004,0.003,0.002)`,對每個候選用 `_coverage_orphans`
  (填三角 → 覆蓋 recall + 未覆蓋連通塊數,忽略 <0.5% 的羽化小塊)量測,
  取**第一個(=最省頂點)達 `cover_target=0.96` 且 0 孤島**者;超 `max_verts=80` 即停(更細只會更多點)。
- 高曲率輪廓自動加密 hull(光暈 14→22);平滑件維持精簡(左手/身體仍 ~20 hull)。
- **隔離性**:只走非 strip 的 v1 fallback;main_draw 4 mesh 全為 strip 模式 → 基準完全不受影響
  (重驗 curtain_left/right IoU 0.934/0.933、shadow 0.955,全 overall_pass、0 自交)。
- `generate(path, adaptive=True)` 為預設;`adaptive=False` 回舊行為。

## 可重現

```
python3 tools/mesh_gen/compare_award_mesh.py           # 3 件端到端 → OVERALL PASS
python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot image/shadow --name image/shadow  # 基準未回歸
```

## 下一步候選

- **SkelToJson 組裝**:把「件→Spine attachment」慣例(`PSD名/圖層名`、+2px padding、mesh/region 分配、
  自適應 mesh 生成)固化成工具,端到端產出可載入的 Spine JSON(mesh 件用 S3、剛體件用 region+旋轉)。
- **weighted mesh 骨綁**:Award 這 3 件是 weighted(靠骨權重變形)。目前 S3 產 unweighted;
  下一難點是自動配權重(BBW),需先有骨架(S5)。可作為 S3→S5 的橋。
- S2 補圖閘 / 骨架閘(純 CPU 可續)。
