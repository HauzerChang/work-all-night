# S3×S4 端到端:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把 `robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手)經 `psd_slice` 切件 →
  `generate_mesh_v2(mode=auto)` 生成 mesh,與 Award spine **藝術家真實 mesh** 在同一張件
  alpha 剪影上量化對照,**3 件全 PASS**:生成覆蓋率不遜於藝術家(容差 0.03 內),且用
  **更少頂點**(35/60/59 vs 藝術家 78/98/80)。這是 S3(mesh 生成)+ S4(PSD 切圖)第一次
  串成端到端、且對**真實生產標的有真值**的驗收。
- **信心**:高(對真實出貨 mesh 比對 + 通過負對照)。**限於靜態剪影覆蓋**(見下方限制)。
- **相關階段**:第 2 階段(S3 mesh / S4 切圖);工具 `tools/mesh_gen/compare_psd_to_award_mesh.py`。

## 量化結果(2026-07-22)

| 件 | 藝術家 v/tri/hull | 生成 v/tri/hull/mode | 藝術家 self-IoU | 生成 IoU | 覆蓋率過? |
|---|---|---|---|---|---|
| 光暈 | 78 / 76 / 78 (weighted) | 35 / 49 / 16 / delaunay-v1 | 0.949 | 0.933 | ✅(−0.016) |
| 身體 | 98 / 154 / 40 (weighted) | 60 / 97 / 20 / delaunay-v1 | 0.948 | 0.966 | ✅(+0.018) |
| 左手 | 80 / 116 / 42 (weighted) | 59 / 97 / 19 / delaunay-v1 | 0.977 | 0.964 | ✅(−0.013) |

`validate_against_real` 風格 AC:①校準可信 ②覆蓋率 ≥ 藝術家−0.03 ③靜態幾何乾淨
(無退化/孤兒/格式正確) ④頂點數 ≤ 藝術家。四項全過。

## 關鍵發現

1. **Award mesh uvs 是 region-local(0..1),不是 global atlas UV**。實測光暈 uvs u∈[0.012,0.990]
   v∈[0.001,0.952],幾乎鋪滿 → 直接把 uvs×(件 W,H) 就能光柵化到 PSD 件剪影上,不需 atlas 轉換。
   (log 006「需先轉 region 局部」的顧慮在此資產不成立;Spine 匯出已是 region-local。)
   **PSD 件 frame ⇄ Award region-local uv frame 對齊**(同一美術、同上正朝向,僅打包縮放差)。
2. **校準即可信度閘**:先算「藝術家 mesh 對自己剪影的 IoU」。3 件皆 0.95~0.98(≥0.80)→ frame
   對齊、比對可信。**負對照**:把 uvs swapUV(模擬 90° 錯位)→ 0.47~0.71;flipV → 0.43~0.60,
   全 < 0.80 → ART_MIN=0.80 有鑑別力,frame 錯位會被抓到(不會假性 pass)。
3. **這 3 件走 delaunay-v1 而非 strip**:`mode=auto` 判定它們非「高瘦 row-convex」→ 回退 v1
   散點 Delaunay。故本次驗證的是 **v1 在真實生產件上的靜態覆蓋**;v1 先前的疑慮(大單向拉伸
   deform 自交)在此**不適用**——這 5 件在 Award **無 deform timeline**,由骨骼驅動(log 005)。
4. **生成 mesh 比藝術家精簡**:頂點少 25~55%,覆蓋率仍相當 → 演算法在「精簡 vs 覆蓋」取捨
   合理;但藝術家多頂點是為 **weighted 骨骼變形品質**(不是為靜態覆蓋),兩者目標不同(見限制)。

## 限制 / 未解(誠實標註)

- **只驗靜態剪影覆蓋**,未驗變形品質。藝術家 mesh 是 **weighted**(綁 77 骨之數骨),我方生成為
  **unweighted**;要真正對等需 BBW 權重綁定(S3 路線圖待建項)+ 有 deform/骨骼動畫真值。此 3 件
  在 Award 無 deform timeline,無法用 `deform_eval` 的真實位移場轉移閘,故變形穩健性此處**未測**。
- 覆蓋率殘差(~1.5%)來源:PSD 件為圖層 tight bbox、Award region 為 art 邊界+2px padding + ~0.70
  打包縮放插值 → 少量邊緣差,屬已知且可接受。
- 下一步自然延伸:把「件→Spine attachment(slot=`<PSD檔名>/<圖層名>`、size+2px、mesh/region 分配)」
  固化成 SkelToJson,端到端產 Spine JSON;weighted 綁定(BBW)為更遠一步。
