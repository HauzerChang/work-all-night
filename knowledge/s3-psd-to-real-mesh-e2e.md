# S3 端到端驗收:PSD 件 → 自產 mesh → 對照真實生產 mesh(外部真值)

- **結論**:S3 mesh 生成器**首次以「真實藝術家 mesh」為外部真值**通過端到端驗收。
  機器人 3 個 mesh 件(光暈/身體/左手)從 `robot_parts.psd` 切件 → `generate_mesh_v2` →
  對照 `Award.json` 對應 slot 的真實 weighted mesh,自產 mesh **覆蓋率與藝術家持平**
  (Δ 皆在 ±0.017),且**頂點數少 40~55%**、拓樸乾淨。
- **信心**:高(有外部真值 + 負對照確認鑑別力)。
- **相關階段**:第 2 階段 S3(mesh),銜接 S4(PSD 切圖)→ 端到端 PSD→件→mesh。
- **工具**:`tools/mesh_gen/compare_to_real_mesh.py`(本次新增)。

## 量化結果(`compare_to_real_mesh.py --parts_dir <psd_slice輸出>`)

| slot | 自產 mode | 自產頂點 | 自產覆蓋 IoU | 藝術家頂點 | 藝術家覆蓋 IoU | Δ(自產−藝術家) |
|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | delaunay-v1 | 35 | 0.9331 | 78 | 0.9487 | −0.0156 |
| 機器人拆件/身體 | delaunay-v1 | 60 | 0.9660 | 98 | 0.9493 | **+0.0167** |
| 機器人拆件/左手 | delaunay-v1 | 59 | 0.9642 | 80 | 0.9808 | −0.0166 |

- 3 件皆 `pass_coverage`(容差 0.02)+ `clean_topology`(0 退化 / 0 孤兒)→ **OVERALL PASS**。
- 身體件自產覆蓋率**優於**藝術家;光暈/左手略低但在容差內(藝術家 hull 較密、貼輪廓更緊)。

## 關鍵發現

1. **自產 mesh 更精簡卻覆蓋相當**:35/60/59 v.s 藝術家 78/98/80(少約一半頂點),
   覆蓋率持平。印證 S3「確定性演算法 + 評估器」路線對真實標的可用,非只對合成/自證資料。
2. **v2 auto-mode 正確路由**:3 件皆 blob 形(非高瘦 row-convex)→ 自動回退 **delaunay-v1**
   (strip 只適窗簾類)。證明 auto 判準(aspect≥1.2 且 row-convex 才 strip)對真實件成立。
3. **對齊約定確認**:PSD 切件 size = Award attachment `width/height` − 2px(padding),故
   **PSD 件像素空間 ≈ mesh 局部 (uv·W, uv·H) 空間**;真實 mesh uv→pixel 最佳方向皆
   `flip_y=False`(spine uv 為 v-down / 左上原點,同影像)。這是把「自產 vs 藝術家」放同框比的基礎。
4. **負對照(鑑別力)**:真實 mesh × 交叉件 alpha 的最佳方向 IoU 矩陣,對角(正確配對)
   0.949/0.949/0.981,離對角(錯配)僅 0.47~0.58 —— **~0.4 落差**,證明覆蓋率閘能區分
   正確 part↔mesh 對齊,非僥倖全過。

## 限制 / 未做(誠實留痕)

- **本次僅靜態覆蓋 + 拓樸**,無 deform 閘:Award 這 3 件是 **weighted(骨骼驅動)、無 deform
  timeline**(log 005:5 件靠骨骼、無 deform)→ 無真實位移場可轉移。依 RULES「變形閘用真實
  位移場、不用未校準 stress_field」,故此處不做變形閘。S3 的耐變形能力已在 main_draw 4 個
  **有 deform** 的 mesh 上用真實位移場驗過(見 `s3-four-mesh-generalization.md`)。
- 覆蓋率基準本身非 1.0:藝術家 mesh 對 alpha 也只 ~0.95(mesh 是輪廓近似)。因此目標是
  **「達到藝術家基準」而非「完美貼 alpha」**,容差 0.02 合理。
- 覆蓋率 IoU 對「內部三角佈局」不敏感(只看填滿範圍);內部佈局的優劣需 deform 閘才顯現,
  而此標的無 deform → 內部拓樸品質對這 3 件不構成風險(骨骼剛性驅動)。

## 復現指令

```
python tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o <out_dir>
python tools/mesh_gen/compare_to_real_mesh.py --parts_dir <out_dir>
```
