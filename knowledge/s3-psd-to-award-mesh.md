# S3 端到端驗收 — PSD 切件 → generate_mesh_v2 → 對照 Award 真實生產 mesh

- **結論**:把 `robot_parts.psd` 切出的 3 個 mesh 件(光暈/身體/左手)跑 S3 `generate_mesh_v2`,
  在**同一件 alpha 幀**上與生產 spine `Award` 的藝術家手做 mesh 比覆蓋率(IoU)。
  **3 件全過**:生成 mesh 覆蓋率在藝術家基準 ±3% 內,且**頂點數明顯更省**。
  這是「PSD→件→mesh」對真實生產標的的首次端到端整合 AC(此前 S3 只對 main_draw 自身驗)。
- **信心**:高(對真實生產藝術家 mesh 交叉比對 + 座標系由藝術家自身 IoU≈0.95 反證正確 + 視覺疊圖確認)。
- **階段**:第 2 階段 / S3×S4 串接(里程碑:S3 對外部生產真值驗收)。

## 量化結果(`compare_to_award.py`,iou_margin=0.03)

| slot | 藝術家 mesh | 藝術家 IoU | 生成 mesh(mode) | 生成 IoU | Δ(生成−藝術家) |
|---|---|---|---|---|---|
| 機器人拆件/光暈 | 78v / 76t / hull78 | 0.9486 | **35v** / 49t (delaunay-v1) | 0.9331 | −0.0155 ✅ |
| 機器人拆件/身體 | 98v / 154t / hull40 | 0.9477 | **60v** / 97t (delaunay-v1) | 0.9660 | +0.0183 ✅ |
| 機器人拆件/左手 | 80v / 116t / hull42 | 0.9768 | **59v** / 97t (delaunay-v1) | 0.9642 | −0.0126 ✅ |

overall_pass = true(全 3 件 IoU ≥ 藝術家基準 − 0.03、format_ok、0 孤兒)。

## 關鍵發現

1. **座標系自證**:兩邊 mesh 的 `uvs` 皆為 **region-local [0,1]**(非 atlas-page-normalized)。
   驗證:直接 `uvs*(W_slice,H_slice)` 疊到切件像素幀,藝術家 mesh IoU 落在 0.95~0.98 ——
   若旋轉/座標系處理錯,藝術家 mesh IoU 會崩壞。故**免處理 atlas rotate 旗標**
   (rotate 是打包細節,JSON uvs 存邏輯正立座標)。⚠️ 別誤用 mesh 的 `vertices`:
   Award mesh `vertices` span(802×780)> width/height(708×685)且未置中 → vertices 是
   骨架/setup-scale 後的幾何座標,**不對應貼圖像素**;貼圖覆蓋比對一律用 `uvs`。

2. **藝術家 IoU 不是 1.0(~0.95)是正常的**:mesh hull 刻意略超出/內縮 alpha 緊邊
   (留變形餘裕、避免邊緣裁切)。所以 AC 用「對齊藝術家基準」而非武斷 0.95(延續
   `validate_against_real` 的校正精神)。

3. **auto-router 對這 3 件全落 delaunay-v1(非 strip)**:光暈/身體/左手是低長寬比的塊狀件
   (非高瘦 row-convex 窗簾),`generate_mesh_v2` 的 `mode=auto` 正確回退 v1 散點 Delaunay,
   覆蓋率反而略優(身體 +0.018)。這**合理且安全**:這 3 件在 Award **無 deform timeline**
   (骨骼/權重驅動,非逐頂點 deform)→ v1 的「大單向拉伸自交」風險在此不適用。
   strip 拓樸的價值仍在窗簾類 deform 件(main_draw 4 mesh 已另驗)。

4. **生成 mesh 更省頂點**(35/60/59 vs 78/98/80,約 45~55% 縮減)同時覆蓋率相當
   → 在「輪廓保真」維度,確定性演算法可達生產品質且拓樸更精簡。

## 誠實範圍與未做

- **未套 deform 閘**:這 3 件無真實位移場可轉移;RULES 禁用未校準 stress_field。deform
  耐受性由 main_draw 4 mesh 另行建立,此 chunk 只驗**靜態覆蓋保真**。
- IoU 是覆蓋率(面積)指標,不評「三角配置美學 / 權重綁定」;後者屬 S5 骨架 / 主觀項。
- 貼圖 texture 級(PSD切件 vs atlas切件 alpha-IoU 0.92~0.99)已於 `s4-psd-to-spine-real.md` 驗過,
  此處以 PSD 切件 alpha 為幾何真值來源(免受 atlas 0.70 縮放影響,IoU 對縮放不變)。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
python3 tools/mesh_gen/compare_to_award.py --viz_dir /tmp/viz_award   # overall_pass=true
```

`--viz_dir` 產出左(橘=藝術家)右(綠=生成)疊圖,肉眼確認對齊。

## 下一步

- 把「件→Spine mesh attachment」寫成組裝工具(SkelToJson):`機器人拆件/<圖層名>` 命名 +
  size+2px padding + region-local uvs + generate_mesh_v2 幾何,端到端吐出可載入的 Spine JSON。
  本檔已把最後一塊真值對照補齊 → 組裝工具的輸出可直接用此 AC 迴歸。
