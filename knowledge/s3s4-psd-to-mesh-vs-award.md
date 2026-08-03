# S3+S4 端到端:PSD件 → 生成 mesh → 對照 Award 真實藝術家 mesh

- **結論**:把 S4 切件與 S3 mesh 生成串成端到端,並用 Award 生產 spine 的**真實藝術家 mesh 當真值**驗收。
  機器人 3 個 mesh 件(光暈 / 身體 / 左手)`robot_parts.psd` → `psd_slice` → `generate_mesh_v2` 的
  **生成輪廓與藝術家 mesh 輪廓 IoU 0.91 / 0.93 / 0.96**(gen∩art hull),且生成 mesh 用**更少頂點**
  達到相當(甚至更好)的 alpha 覆蓋。**端到端「PSD→件→mesh」對真實生產標的通過(靜態輪廓)。**
- **信心**:高(對真實生產 spine 的 ground-truth mesh 交叉比對 + 座標校準自證 + 判別力驗證)。
- **階段**:第 2 階段 / S3×S4 整合里程碑(2026-08-03)。
- **工具**:`tools/mesh_gen/compare_to_award.py`(可重現,exit 0 = PASS)。

## ★ 座標系關鍵發現(先前把它當 bug 踩過)

Spine JSON 的 mesh `uvs` 是 **region-local 正規化 [0,1]**(runtime 由 `AtlasAttachmentLoader`
再 remap 進 atlas page 的 UV 矩形),**不是 atlas-page 正規化**。證據:Award 三件 mesh 的 uv 跨滿
[0,1](光暈 u 0.012→0.990、v 0.001→0.952),若是 page 正規化則應落在該件小 region 矩形內。

→ 藝術家 mesh 的 uv **已經直接等於「件圖正規化座標」**(u 右、v 下、[0,1] over 件),與
`generate_mesh_v2` 產出的 uv(`x/W, y/H`)**同一座標系**。比對**不需要**任何 atlas region /
旋轉(rotate:true/false)映射。第一版誤把 uv 當 page 正規化再減 region xy → 身體 IoU=0.0(假性失敗),
修正後三件全對齊。**教訓:先驗證座標假設(印 uv 值域),別急著套 atlas 幾何。**

## 方法(每件)

1. `psd_slice` 切件 PNG → alpha 當真值輪廓(downscale 到 max 邊 256 加速)。
2. `generate_mesh_v2` 產 mesh → hull uv 多邊形 rasterize，量 `gen_hull ∩ alpha`。
3. 藝術家 mesh(`Award.json`)hull uv 多邊形 → 量 `art_hull ∩ alpha`。
4. 兩 hull 互比 `gen ∩ art`(核心指標:生成輪廓 ≈ 藝術家輪廓)。
5. **校準自證**:對藝術家 uv 試 8 種 flip/transpose,確認 **identity(不翻不轉)勝出**才採信 →
   證兩者座標系真對齊,不是靠搜尋硬湊。

## 量化結果(gen∩art hull IoU 門檻 0.85)

| 件 | 生成 v/hull/tri | 藝術家 v/hull/tri | gen∩alpha | art∩alpha | **gen∩art** | 校準 |
|---|---|---|---|---|---|---|
| 光暈 | 35/16/49 | 78/78/76 | 0.912 | 0.934 | **0.911** | identity ✓ |
| 身體 | 60/20/97 | 98/40/154 | 0.965 | 0.939 | **0.931** | identity ✓ |
| 左手 | 59/19/97 | 80/42/116 | 0.953 | 0.978 | **0.959** | identity ✓ |

- **判別力驗證**:身體 8 候選中 identity 0.939 遠勝次高 0.603(其餘 0.41–0.60)→ 對齊非偶然。
- **頂點效率**:生成 mesh 頂點數 35/60/59 < 藝術家 78/98/80,alpha 覆蓋卻相當(身體生成 0.965 > 藝術家 0.939)。
- 三件在 `generate_mesh_v2` 都走 **delaunay-v1**(不規則團塊,aspect<1.2 / 非 row-convex),
  非窗簾那種高直條 strip → **v1 對這類件才是對的分支**(auto 模式判對)。

## 誠實邊界(這次**沒**驗到的)

1. **只驗靜態輪廓(hull silhouette)**,未驗內部三角剖分品質(生成 49–97 tri vs 藝術家 76–154,拓樸不同)。
2. **未驗 deform**:Award 這 5 件**無 deform timeline**,靠**骨骼 + 權重**變形(藝術家 mesh 是 **weighted**)。
   故無法像窗簾那樣做「真實位移場轉移」閘。生成 mesh 目前 **unweighted** → **BBW 權重生成是下一個缺口**。
3. 未做貼圖級 texture 對照(件↔atlas alpha-IoU 已於 S4 knowledge 確認同素材,此處不重覆)。

## 下一步候選

- **權重(BBW)生成**:讓生成 mesh 可 weighted-bind 到骨架,補上這條 pipeline 對「骨骼驅動 mesh」的支援。
- **切圖→Spine JSON 組裝(SkelToJson)**:把 `PSD名/圖層名` 命名 + size+2px padding + mesh/region 分配 +
  本次生成的 mesh 幾何,寫成完整 Spine attachment,端到端產出可載入 JSON。
- 內部三角剖分品質閘(目前只有輪廓;可加三角形長寬比 / 最小角度等 mesh-quality 指標)。
