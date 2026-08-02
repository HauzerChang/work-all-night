# S3×S4 端到端驗收 — 「PSD 件 → 生成 mesh」對照 Award 真實藝術家 mesh

- **結論**:把 `robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手)端到端跑「切件 → `generate_mesh_v2`
  → 對照生產 spine `Award` 的**藝術家 weighted mesh**」,3 件全 `overall_pass`。我方生成 mesh
  **覆蓋美術不遜於藝術家(iou_alpha 相當),與藝術家覆蓋同一 footprint(cross-IoU 0.92~0.96),
  且更精簡(頂點數約藝術家的一半)**。這是 S3(mesh 生成)+ S4(PSD 切圖)串成端到端、且對**真實生產標的**驗收的里程碑。
- **信心**:高(真實 PSD 素材 + 真實 spine 藝術家 mesh 當雙真值 + 三向負對照確認閘鑑別力)。
- **階段**:第 2 階段 / S3×S4 整合(合成→真實件→真實藝術家 mesh 對照)。

## 量化結果(`tools/mesh_gen/compare_award_mesh.py`)

| 件 | 我方 iou_alpha | 藝術家 iou_alpha | cross-IoU | 我方頂點/三角 | 藝術家頂點/三角 | mode |
|---|---|---|---|---|---|---|
| 光暈 | 0.933 | 0.949 | 0.918 | 35 / 49 | 78 / 76 | delaunay-v1 |
| 身體 | **0.966** | 0.948 | 0.928 | 60 / 97 | 98 / 154 | delaunay-v1 |
| 左手 | 0.964 | 0.977 | 0.957 | 59 / 97 | 80 / 116 | delaunay-v1 |

- **iou_alpha**:mesh 光柵化覆蓋 vs 切件 alpha(越高越貼合美術可見區)。
- **cross-IoU**:我方覆蓋 vs 藝術家覆蓋(同一塊 footprint 嗎)。
- 身體我方 iou_alpha 甚至**高於**藝術家(0.966>0.948):藝術家 mesh 外周略放寬留裕度,我方更貼 alpha>8 邊界。
- 3 件長寬比 <1.2 → v2 `auto` 皆回退 **v1 Delaunay**(散點內部佈局)。這 3 件在 Award **無 deform timeline**
  (靠骨骼/權重變形,非逐頂點 deform)→ 此處驗收標的是**靜態覆蓋 + 精簡度**,不是耐變形(耐變形結論見窗簾 4-mesh 文件)。

視覺對照圖:`knowledge/figures/s3xs4-award-mesh-compare.png`(orange=藝術家、green=我方,疊在切件 footprint 上)。

## 關鍵技術點:Award mesh `uvs` = region 局部正規化

- Award 的 mesh 是 **weighted**(`len(vertices) != len(uvs)`;vertices 為 `[骨數,骨idx,bindX,bindY,權重,...]`
  攤平變長格式),setup 頂點座標不能直接拿來比幾何。
- 但 mesh **`uvs` 是 0..1 在該 attachment 自身 region 內的局部正規化**(Spine 3.8 JSON 慣例;runtime
  再用 atlas region 的 u,v,u2,v2 映到貼圖頁)→ `px = u*W, py = v*H` 即還原到**切件像素座標**,
  即可光柵化出藝術家覆蓋來對照。(att.width/height 記原始邏輯尺寸 ≈ 切件 +2px,對齊用切件 W,H 即可。)
- **v 朝向**(上/下原點)未知 → 兩種都試,取對切件 alpha IoU 較高者;藝術家 mesh 必然貼合自身素材,
  所以「正確朝向」= IoU 高者。本資產 3 件皆 `v_flip=false`。

## 評估器可信度(先校準才信 PASS — 第 N 次落實此紀律)

- **正對照(內建)**:用 Award uvs 還原的藝術家 mesh 對自身 alpha IoU = 0.95~0.98 → 還原+朝向正確。
- **負對照 1(平移 40% 寬)**:cross 0.19、iou_alpha 0.20 → AC2 正確 FAIL。
- **負對照 2(以重心縮 55%)**:iou_alpha 0.30 → AC1 正確 FAIL(遠低於藝術家 0.948)。
- **負對照 3(藝術家 mesh 用錯 v 朝向)**:iou_alpha 0.60 « 正確 0.95 → 朝向偵測有意義、非巧合。

## AC 定義(端到端閘)

- **AC1 覆蓋不遜藝術家**:我方 `iou_alpha ≥ 藝術家 iou_alpha − 0.02`。
- **AC2 footprint 一致**:`cross-IoU ≥ 0.90`。
- **AC3 精簡度可比**:我方頂點數 `≤ 藝術家頂點數 × 1.10`(實際我方遠更精簡)。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts   # 切件
python3 tools/mesh_gen/compare_award_mesh.py                                     # 端到端閘(exit 0)
```

## 下一步 / 開放

- 這 3 件無 deform GT,故只驗靜態覆蓋+精簡度。**耐變形**已在 main_draw 窗簾/陰影 4-mesh(v2 strip)驗過。
- **待固化**:把「件→Spine mesh attachment」寫進 SkelToJson 組裝(命名 `PSD名/圖層名`、size +2px、
  weighted 需綁骨才等價藝術家;目前我方輸出為 unweighted → 若要進 Award 需再加 BBW 權重綁定,屬 S3 後段)。
- 光暈藝術家用「幾乎純 hull 扇形」(78v 全 hull),我方 Delaunay 加了內部點;兩者覆蓋相當 →
  對純外形柔性件,外形取樣密度比內部點更關鍵(呼應 4-mesh「IoU 由 rows 決定」發現)。
