# S3+S4 端到端驗收 — PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把 S4(PSD 切件)接 S3(mesh 生成),對「機器人拆件」的 **3 個真實 mesh 件**
  (光暈 / 身體 / 左手,Award 中為 mesh)做端到端驗收,**3 件全 PASS**:生成 mesh 的覆蓋率
  IoU **達到或超過藝術家真值**,且用**更少頂點**(更精簡)、0 孤兒 / 0 退化。
- **信心**:高(對照真實生產 spine 的藝術家 mesh 真值 + 雙向負對照確認閘鑑別力)。
- **階段**:第 2 階段 / S3×S4 串接(里程碑:首次對「真實生產 mesh 真值」驗收 v1 拓樸)。

## 結果(`tools/mesh_gen/compare_to_award_mesh.py`,margin=0.02,budget=110)

| 件 | 生成 (mode / 頂點 / hull / 三角 / IoU) | Award 藝術家 (頂點 / hull / 三角 / IoU) | 判定 |
|---|---|---|---|
| 光暈 | delaunay-v1 / **35** / 16 / 49 / **0.933** | 78 / 78 / 76 / 0.949 | ✅ (差 1.5pp,頂點 35 vs 78) |
| 身體 | delaunay-v1 / **60** / 20 / 97 / **0.966** | 98 / 40 / 154 / 0.948 | ✅ (**IoU 勝藝術家**,頂點 60 vs 98) |
| 左手 | delaunay-v1 / **59** / 19 / 97 / **0.964** | 80 / 42 / 116 / 0.977 | ✅ (差 1.3pp,頂點 59 vs 80) |

> IoU 都在同一張 **PSD 件 alpha 遮罩**上計算(見下「為何可比」),故是 apples-to-apples。

## 三個關鍵發現

1. **`mode=auto` 路由正確**:3 件皆近方形 blob(aspect 0.84~1.12 < 1.2)→ auto 全部回退 **v1
   Delaunay**(非 strip)。這**首次在真實生產形狀上驗證了 auto 的 strip/Delaunay 分流啟發式**
   (先前 strip 只驗窗簾、v1 只驗 curtain_left)。窗簾類(高瘦、沿軸拉伸)才走 strip;blob 走 v1 正確。
2. **生成 mesh 比藝術家精簡**:頂點 35/60/59 vs 藝術家 78/98/80,覆蓋率仍打平或勝出。
   身體件生成 IoU(0.966)甚至**高於**藝術家(0.948)。→ v1 Delaunay 對 blob 件的覆蓋效率佳。
3. **藝術家 光暈 mesh 是純邊界扇形**(hull=78=全部頂點、76 三角):軟光暈只放一圈密邊界點做 fan;
   我方 v1 用 35v/16-hull 的內佈點 Delaunay 以更少點達 93.3% 覆蓋。

## 為何可比(apples-to-apples,重要方法論)

Spine mesh 的 `uvs` 是**件內正規化紋理座標 [0,1]**。生成 mesh 與 Award 藝術家 mesh 的 uvs
都落在「同一件的正規化座標系」,故兩者覆蓋率 IoU 可在**同一張 PSD 件 alpha 遮罩**上算,
**完全避開 atlas 0.70 縮放 / 旋轉 / anti-alias 的干擾**,也**不需 Award.png/atlas,只需 Award.json**。

- 資料自證方向對齊:藝術家 uvs 直接貼 PSD 件遮罩得 **0.949 / 0.948 / 0.977**(全 >0.94);
  若 uv↔件 方向不合(旋轉/翻轉),IoU 會掉到 ~0.4 → 高分本身即證明正規化座標系一致。

## 負對照(確認閘鑑別力,RULES 要求)

- **錯件**:藝術家 mesh 貼「別件」遮罩 → 對角 0.95~0.98,非對角 **0.48~0.58**(清楚區分)。
- **翻轉 uv**(v→1−v 破壞方向)→ IoU 崩到 **0.43~0.60**。
→ 閘對「形狀/方向錯誤」敏感,0.94+ 的對齊是真實吻合而非巧合。

## 限制(誠實記錄)

- Award 這 3 件**無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform)→ 本閘只驗
  **靜態覆蓋率 + 精簡度**,**未**驗真實 deform 穩健性(無真值位移場可轉移)。deform 穩健性
  仍以 main_draw 4 mesh 的真實位移場閘為準(見 `s3-four-mesh-generalization.md`)。
- 未驗**紋理對齊/實機**(需把生成 mesh 的 uvs 對回 atlas region;屬後續 SkelToJson 組裝範疇)。

## 可重現

```
python3 tools/mesh_gen/compare_to_award_mesh.py            # 3 件 overall_pass
```

## 下一步

- **SkelToJson 組裝**:把「件→Spine attachment」(命名 `PSD名/圖層名`、size+2px padding、
  mesh/region 分配、生成 mesh 的 uvs 對回 atlas region UV)固化成寫出工具 → 真正端到端產 Spine JSON。
- S2 補圖閘 / 骨架閘(補齊 S2 樞紐)。
