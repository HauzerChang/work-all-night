# 端到端 S4→S3 驗收:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把切圖(S4)與 mesh 生成(S3)串成端到端流程,對真實生產標的(`Award` spine 中
  機器人拆件的 3 個 mesh 件)以美術手做 mesh 當**真值基準**做量化對照,**3 件全 PASS**。
  這是「PSD → 件 → mesh」對真實生產目標的端到端驗收里程碑。
- **信心**:高(真實生產 PSD + 真實生產 spine ground truth + 負對照確認閘鑑別力)。
- **階段**:第 2 階段 / S3×S4 交叉(里程碑)。
- **工具**:`tools/mesh_gen/compare_psd_to_award_mesh.py`。可重現:`python3 tools/mesh_gen/compare_psd_to_award_mesh.py`。

## 結果(2026-07-29)

| 件 | 美術 mesh(真值) | 生成 mesh(受測) | coverage | topology | parsimony |
|---|---|---|---|---|---|
| 機器人拆件/光暈 | v78 / IoU 0.949 (weighted) | v35 / IoU 0.933 [delaunay-v1] | ✅ | ✅ | ✅ |
| 機器人拆件/身體 | v98 / IoU 0.948 (weighted) | v60 / IoU 0.966 [delaunay-v1] | ✅ | ✅ | ✅ |
| 機器人拆件/左手 | v80 / IoU 0.977 (weighted) | v59 / IoU 0.964 [delaunay-v1] | ✅ | ✅ | ✅ |

AC:coverage(生成 IoU ≥ 美術基準 − 0.02)/ topology(格式有效 + 重心全在 mask + 0 退化 + 0 孤兒)/
parsimony(頂點 ≤ 美術 ×1.6)。**生成 mesh 用更少頂點(35/60/59 vs 78/98/80)達到相近覆蓋率。**

## ★ 重要更正:Award mesh 的 UV 座標系

先前 `s4-psd-to-spine-real.md` 記「Award mesh uvs 為 atlas UV,需先轉 region 局部」— **實測不符**。
2026-07-29 直接讀 Award.json 三個 mesh 的 uvs:範圍皆約 [0,1]
(光暈 x[0.012,0.990] y[0.001,0.952];身體 x[0,0.759] y[0.049,0.989];左手 x[0.008,1.0] y[0.004,1.0])。
若為 atlas-page 正規化,x 應落在 region 起點附近(如 562/1780≈0.32)。

**正解**:Spine JSON 匯出的 mesh `uvs` 是 **region-local 正規化 [0,1]**(runtime 才套用 atlas
變換/旋轉/縮放)。因此 `uvs × [W,H]` 可直接對映到**原始朝向**的 PSD 切件,無需轉換。
`rotate:true`(光暈/身體)與 atlas 0.70 縮小,只影響打包,不影響邏輯 uv。
→ `validate_against_real.artist_iou` 對 main_draw 能直接運作,原理相同,非巧合。

## ★ 這 3 件是 weighted mesh 且無 deform timeline

`len(vertices) != 2×nv` → weighted(骨骼綁定變形),且 Award 中這 5 件無 deform timeline。
→ **不套用逐頂點 deform 閘**(那需 deform 位移場,此處無)。正確 AC = 靜態覆蓋率 + 拓樸有效性。
(對比 main_draw 的窗簾/陰影是 unweighted + 有 deform timeline → 才用 transfer_deform_check。)

## ★ v1 Delaunay 對真實「方正」件通用

這 3 件長寬比 0.84~1.12(< 1.2)→ `generate_mesh_v2` auto 模式落回 **Delaunay v1**,
覆蓋率達標。呼應既有結論:**strip(v2)給高瘦耐變形件(窗簾)、Delaunay(v1)給方正件**,
`mode=auto` 的 aspect 分派正確。此為 v1 對真實生產形狀的首次外部真值驗證(先前只有合成 + main_draw)。

## 負對照(閘鑑別力)

各生成 mesh 對「錯誤件」的 alpha 算覆蓋率:IoU 崩到 0.50~0.58、重心在 mask 比例 0.63~0.74
→ overall FAIL。自身 alpha 則 IoU 0.93~0.97、重心 1.0。**閘能區分對/錯,可信。**

## 下一步

- 把「件 → Spine attachment」慣例(`PSD名/圖層名` slot 命名、mesh/region 分配、+2px padding、
  atlas 0.70 縮放、uvs region-local)固化成 **SkelToJson 組裝工具**,端到端產出可載入的 Spine JSON。
- 生成 mesh 目前為 unweighted;真實件為 weighted。若要完全取代美術件,需 S3 加 **BBW 權重**
  (綁到 Award 對應骨),此為後續 S3 深化項。
