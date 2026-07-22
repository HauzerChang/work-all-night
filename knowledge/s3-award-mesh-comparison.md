# S3+S4 端到端驗收 — PSD 件 → 生成 mesh 對照 Award 真實生產 mesh

- **結論**:把 `robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手)跑 `generate_mesh_v2`(auto),
  與 Award spine 裡**藝術家手做的真實 mesh**(ground truth)做覆蓋率對照 —— **3 件全 PASS**:
  我方生成 mesh 覆蓋率 ≈ 藝術家 mesh(margin 0.02 內,身體甚至更高),且**用更少頂點**達成。
  這是「PSD→件→mesh」pipeline 首次對**真實生產標的 + 真值 mesh** 的整合驗收(此前 S3 只對 main_draw
  atlas 切件、S4 只驗切圖無損)。
- **信心**:高。評估器經雙重校準(對 atlas region 與 PSD 件兩個貼圖真值 + 6 種 uv 朝向負對照)。
- **階段**:第 2 階段 / S3×S4 交會(里程碑:端到端串起 PSD 切圖 → mesh 生成 → 真值對照)。

## 量化結果(`compare_award_mesh.py`)

| 件 | 生成 IoU(vs 件 alpha) | 藝術家 IoU(vs 件 alpha) | 生成↔藝術家 IoU | 生成頂點 | 藝術家頂點 | mode |
|---|---|---|---|---|---|---|
| 光暈 | 0.933 | 0.949 | 0.918 | **35** (hull16) | 78 (hull78) | delaunay-v1 |
| 身體 | 0.966 | 0.948 | 0.928 | **60** (hull20) | 98 (hull40) | delaunay-v1 |
| 左手 | 0.964 | 0.977 | 0.957 | **59** (hull19) | 80 (hull42) | delaunay-v1 |

- PASS 判準:`生成 IoU >= 藝術家 IoU − 0.02`(對齊藝術家覆蓋率,不用武斷閾值,與既有 AC 一致)+ 拓樸健全。
- **生成↔藝術家 IoU 0.92~0.96**:兩 mesh 覆蓋幾乎重合(疊圖見 `figures/cover_*.png`,黃=兩者重疊佔絕大部分)。
- 3 件長寬比都接近方形(0.84~1.12,< 1.2)→ auto 全走 **v1 Delaunay**(非窗簾那種直條 strip)。

## 關鍵發現 / 教訓

1. **★ 對照藝術家 mesh 覆蓋率必須用 `uvs`,不可用 `vertices`**(踩過的坑,已記)。
   Award mesh 的 `vertices` 在 **bone-local / 旋轉框**:span 與中心都不對齊 attachment W/H
   (例:光暈 vert x span 802 vs W=708、中心 ≈ −88 而非 0)。誤用 vertices 光柵化 → 藝術家 IoU
   假性掉到 0.48~0.62(看似「藝術家 mesh 蓋不住自己貼圖」的荒謬結果)。改用 `uvs`(貼圖座標)後
   回到合理的 0.95~0.98。**這與 `validate_against_real.artist_iou` 用 uvs 的做法一致。**

2. **★ 修正舊 caveat:Award mesh 的 uvs 已是 region-local upright(0..1),不需再做「atlas→region」轉換。**
   `s4-psd-to-spine-real.md` 舊「下一步」寫「Award mesh uvs 為 atlas UV,需先轉 region 局部」是**過度保守/誤判**。
   實測:uvs 直接 ×(region W,H) 對 `atlas_crop` CW 還原的 upright region alpha IoU **0.97~0.98**;
   6 種朝向負對照(swap/flipx/flipy 組合)只有 **plain 唯一正確**(其餘 0.40~0.70)→ 確認 uvs 就是 region-local upright,
   且與 atlas_crop 的 CW derotation 對齊。**評估器據此校準,可信。**

3. **生成 mesh 用更少頂點達到相當覆蓋**(35/60/59 vs 78/98/80):v1 Delaunay 對這類件夠用。
   殘差主要在**尖角/細長凸起**:光暈的針狀光芒,藝術家用 78 點純 hull 細描,我方 16 hull 點
   (epsilon 0.008)略為圓鈍 → 藝術家 IoU 略高(0.949 vs 0.933)。**hull 點預算(epsilon)↔ 尖角保真**
   是可調 tradeoff;若要逼近可降 epsilon,但頂點數會上升。

4. **這 5 件在 Award 無 deform timeline**(確認:掃全 12 動畫,`機器人拆件` slot 的 deform = NONE)。
   靠骨骼/權重變形,非逐頂點 deform → **沒有可轉移的真實位移場**。故本 AC **只驗靜態覆蓋 + setup 拓樸健全**,
   **不下 deform pass/fail**(遵 RULES:不用未校準壓力場當閘)。deform 穩健性對這些件在此**未驗**
   (與 main_draw 窗簾不同,窗簾有真實 deform 場可轉移)。屬已知範圍限制。

## 可重現

```
python3 tools/mesh_gen/compare_award_mesh.py --figs knowledge/figures
# overall_pass: true;3 件逐件 AC_iou/gen_vs_artist/topology 見 stdout JSON
```

## 下一步候選

- **切圖→Spine JSON 組裝(SkelToJson)**:把「件→attachment」慣例固化成工具 —— slot=`<PSD檔名>/<圖層名>`、
  size+2px padding、mesh vs region 由件屬性決定(會 warp→mesh、剛體→region);對 mesh 件呼叫
  `generate_mesh_v2` 產拓樸,端到端吐出可載入的 Spine JSON。**這是把 S3+S4 收斂成單一產出的自然下一步。**
- 若要逼近藝術家尖角保真:對高曲率輪廓件自動降 epsilon / 加 hull 點,再跑本對照看 IoU 是否追上。
