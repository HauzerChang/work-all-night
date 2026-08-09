# S3 對第二個真實生產資產(Award weighted mesh)驗收 + 自適應輪廓密度修正

- **結論**:把 S3 mesh 生成器端到端接到**第二個真實生產 spine(Award「機器人拆件」)**,對其 3 個
  **weighted mesh**(光暈/身體/左手)以「靜態 IoU + 拓樸」對藝術家真值驗收。**初測光暈 fail**
  (固定 epsilon 過度簡化細節外框)→ 加**自適應輪廓密度**(deterministic,由填充 IoU 驅動、預算內加密)
  → **3 件全 PASS,且 IoU 均超越藝術家、頂點更省**(64/64/59v vs 藝術家 78/98/80v)。順手修掉 v1 孤兒頂點 bug。
- **信心**:高(對真實生產 mesh 的 uvs/triangles 真值比對 + 視覺線框對照 + main_draw 4-mesh 無回歸)。
- **階段**:第 2 階段 / S3(里程碑:S3 從只驗 main_draw → **跨第二個真實資產且涵蓋 weighted mesh 這一新類別**)。

## 為何要另寫閘 `validate_award_mesh.py`(不能沿用 validate_against_real.py)

Award 的 3 個機器人 mesh 是 **weighted**(骨骼權重驅動,`len(vertices)!=len(uvs)`)且**無 deform timeline**
(靠骨骼變形,非逐頂點 deform)。既有 `validate_against_real` 的 deform 閘 `real_deform_field` 只能讀
unweighted 攤平頂點(`reshape(-1,2)`),對 weighted 會 **shape 不符直接 crash**(本次實測 griddata
`different number of values and points`)。

∴ 對這類件只做**可誠實驗證**的兩件事,deform 閘標 **N/A + 原因**(不做零位移場的假性通過):
1. **靜態 IoU**:生成 mesh 填充覆蓋率 vs 藝術家 mesh 覆蓋率(藝術家為 ground-truth 基準,margin 0.03)。
2. **拓樸/格式健全**:格點在 mask 內、無退化/孤兒、頂點預算內;並列印藝術家 vs 生成頂點/hull/三角數。

alpha 來源 = Award atlas 切出的 region(`atlas_crop.extract`,CW+多頁已修,~0.70 縮放;IoU 正規化不受影響)。
藝術家 uvs 正規化於同一 region → 對齊。`artist_iou` 只用 uvs+triangles,weighted-safe。

## 關鍵發現:固定 epsilon 對「細節外框件」過度簡化

`generate_mesh.py`(v1 Delaunay)原用固定 `epsilon_frac=0.008` 做 Douglas-Peucker 輪廓簡化。
對 blob 件(身體/左手)夠用,但**光暈**是藝術家刻意做的**純邊界環**(hull=78=全頂點、0 內部點、
沿發光暈細緻外框),固定 0.008 只留 hull 14 → **IoU 0.929 < 藝術家 0.9795(gap 0.05)fail**,還留 1 個孤兒頂點。

epsilon 掃描(光暈 region)佐證是「取樣密度」問題,非演算法問題:

| epsilon | hull | 頂點 | IoU | 孤兒 |
|---|---|---|---|---|
| 0.008(舊預設) | 14 | 54 | 0.929 | 1 |
| 0.004 | 22 | 61 | 0.966 | 0 |
| 0.002 | 38 | 78 | 0.983 | 0 |
| 0.001 | 58 | 98 | 0.992 | 0 |

## 修正:自適應輪廓密度(deterministic,無 ML)

`adaptive_boundary_points()`:由粗到細降低 epsilon,直到 hull 填充 IoU 達 target(0.985)或 hull 逼近
`max_hull`(預算-8)→ 取「符合上限中最保真」者。並**動態夾 interior**使 hull+interior ≤ vertex_budget(64)。
- blob 件(身體/左手)早停於粗 epsilon,不浪費頂點;細節件(光暈)在預算內自動加密。
- 符合專案哲學:**確定性演算法 + 評估器回饋驅動**,不用 ML 學「沒有唯一解的頂點佈局」。
- `generate(..., adaptive=True)` 為新預設;`adaptive=False` 保留舊固定行為。v2 auto 對非 strip 件回退 v1 即走此路徑。

## 驗收結果(3 件全 PASS)

| 件 | 生成 IoU | 藝術家基準 | 生成頂點(hull) | 藝術家頂點 | 孤兒 | overall |
|---|---|---|---|---|---|---|
| 光暈 halo | **0.983** | 0.9795 | 64 (38) | 78 | 0 | ✅ |
| 身體 body | **0.986** | 0.976 | 64 (29) | 98 | 0 | ✅ |
| 左手 lhand | **0.987** | 0.9681 | 59 (36) | 80 | 0 | ✅ |

→ 生成 mesh **IoU 全超越藝術家、頂點數更省**。視覺線框對照見 `figures/award_mesh_compare.png`
(綠=生成 / 橘=藝術家;三形狀輪廓皆乾淨貼合,含光暈的尖角突起與波浪下緣)。

## 無回歸

main_draw 4 mesh(curtain_left/right、shadow、shadow2)全走 **v2 strip 模式**,不經 v1 自適應路徑,
`validate_against_real --gen v2` 4 件仍全 `overall_pass`(shadow2 attachment 名為 `image/shadow`,與 shadow 共用 region)。

## 可重現

```
python3 tools/mesh_gen/validate_award_mesh.py            # 3 件全 PASS,exit 0
# 單件掃描 epsilon 亦可直接 generate_mesh.generate(path, adaptive=False, epsilon_frac=...)
```

## 教訓 / 下一步

- **教訓**:mesh 頂點預算不該是單一硬值 —— 形狀複雜度決定所需邊界密度。自適應 + 預算夾比固定 epsilon 通用。
- **里程碑意義**:S3 現已對「兩個」真實生產資產(main_draw unweighted + Award weighted)驗收,且評估器對
  weighted mesh 這一新類別誠實處理(deform N/A)。
- 下一步候選:(1) **切件→Spine JSON 組裝(SkelToJson)**,把命名慣例 `PSD名/圖層名`+size+2px padding+
  自適應 mesh 固化成端到端「PSD→可用 Spine attachment」工具;(2) weighted mesh 的骨骼變形閘(需綁定權重來源,
  屬 S5 骨架領域);(3) S2 補圖閘/骨架閘。
