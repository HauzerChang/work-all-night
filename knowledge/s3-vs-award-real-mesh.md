# S3 生成 mesh 對照 Award 真實(藝術家)mesh — 端到端「件→mesh」對真實生產標的驗收

- **結論**:把 Award 生產 spine 中三個藝術家手做 mesh 件(機器人拆件的 **光暈 / 身體 / 左手**)的
  真實輪廓(atlas region alpha)餵給 S3 `generate_mesh_v2`,生成 mesh 的**覆蓋率(coverage IoU)
  達到或超過藝術家 mesh,且用更少頂點**。三件全 PASS,S3 對真實生產標的可用。
- **信心**:高。單一真值來源(atlas region alpha)、藝術家 mesh 覆蓋率 0.98 自證座標映射正確、
  正/負向自校驗、對 4 個 main_draw strip mesh 無回歸。
- **階段**:第 2 階段 / S3 × S4 端到端串接(里程碑:合成/main_draw → **真實生產 mesh 標的**)。

## 量化結果(`compare_gen_vs_artist.py`,2026-07-06)

| 件 | 藝術家 v / IoU | S3 v / IoU | 判定 |
|---|---|---|---|
| 光暈 | 78v / 0.9834 | **53v / 0.9832** | PASS(打平,頂點 −32%) |
| 身體 | 98v / 0.9834 | **44v / 0.9858** | PASS(超越,頂點 −55%) |
| 左手 | 80v / 0.9806 | **47v / 0.9816** | PASS(超越,頂點 −41%) |

判定 = S3 coverage IoU ≥ 藝術家 IoU − 0.03 且靜態結構健全(格式/無退化/無孤兒)。

## 方法(座標與真值)

- **單一真值 = atlas region 的 alpha 輪廓**(`atlas_crop.extract` 去旋轉回 orig 方向;CW 已校正)。
  兩個 mesh(藝術家、S3)都對「同一張 alpha」算覆蓋率 → 公平比較,零跨空間配準誤差。
- **藝術家 mesh 的 uvs 是 region-local `[0,1]`**(Spine runtime 才套 atlas 旋轉/縮放,**未烤進 JSON uvs**)
  → 直接 `(u·W, v·H)` 落到輪廓像素格。**光暈/身體/左手 v 方向皆不翻轉**,藝術家覆蓋率 0.98
  同時**反證映射正確**(映射錯會塌成低 IoU)。
- 之所以用 atlas alpha 而非 PSD 切件:兩者已證同素材(alpha-IoU 0.92–0.99,見 `s4-psd-to-spine-real.md`),
  但 atlas alpha 與藝術家 uvs 同在一個原生空間,免去 PSD↔atlas 的 0.70 縮放與方向對齊。

## ★ 關鍵發現:覆蓋率由 hull epsilon 決定,內部點密度無關

對光暈掃描 `epsilon_frac`(hull 近似)× `max_interior`(內部點):

| epsilon | nv | IoU |
|---|---|---|
| 0.008(舊預設) | 29 | 0.9316(不足) |
| 0.004 | 37 | 0.9677 |
| **0.002** | 53 | **0.9832**(≈藝術家) |
| 0.001 | 73 | 0.9924 |

`max_interior` 40→80 **不提升**覆蓋率(反而可能製造孤兒點)。與先前 strip 的
「IoU 由 rows 決定、cols 不影響」同一規律:**覆蓋率是邊界/hull 現象**。
舊 v1/v2 blob 路徑固定 epsilon=0.008,對「大而軟」的件(光暈)hull 太粗 → 覆蓋不足。

## 修正:blob 路徑加入覆蓋率驅動的 epsilon 精修(Build-Verify 內建)

`generate_mesh_v2.generate(..., target_cov=0.97, vertex_cap=80)`:blob(Delaunay)路徑
由粗到細試 epsilon(0.008→0.001),取「達標且頂點 ≤ cap 的最粗解」(頂點最省)。
`target_cov=None` 關閉(還原舊行為)。**strip 路徑不受影響**(4 個 main_draw mesh 走 strip,重驗全過)。
CLI:`--target-cov` / `--vertex-cap`。

- 這正是專案主張的「評估器在迴圈內」自主收斂:生成 → 量覆蓋 → 精修,無需人手調參。
- auto 路由正確:光暈/身體/左手(aspect<1.2、blob)走 v1 Delaunay;窗簾/影子(高瘦)走 strip。

## 可重現

```
python3 tools/mesh_gen/compare_gen_vs_artist.py          # 3 件全 PASS,exit 0
python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot image/curtain_left --name image/curtain_left  # 無回歸
```

圖:`knowledge/figures/s3-vs-award-artist-mesh.png`(藝術家 vs S3 線框疊輪廓)。

## 已知邊界 / 下一步

- 覆蓋率是**靜態幾何**指標。這 3 件在 Award **無 deform timeline**(靠骨骼權重變形),
  故無法用它們的真實位移場跑變形閘;變形穩健仍以 main_draw 的真實 deform 為準(已過)。
- 藝術家 mesh 為 **weighted**(綁骨),S3 產 unweighted;下一步若要完全對齊需 S3 加權重(BBW)。
- 下一步候選:(1) 固化「件→Spine attachment JSON 組裝」(SkelToJson:`PSD名/圖層名`、+2px、mesh/region 分配);
  (2) S2 補圖閘 / 骨架閘;(3) S3 unweighted→weighted(BBW)以完整對齊藝術家綁定。
