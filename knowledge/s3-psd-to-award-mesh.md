# S3 端到端驗收 — PSD 切件 → generate_mesh_v2 → 對照 Award 真實生產 mesh

- **結論**:把 `robot_parts.psd` 的 3 個 mesh 件(光暈 / 身體 / 左手)走完整 pipeline
  「PSD 切件 → `generate_mesh_v2`(auto) → 對照 Award 真實藝術家 mesh」,**3 件全 `overall_pass`**。
  生成 mesh 用**更少頂點**(35/60/59 vs 藝術家 78/98/80)達到 **≈ 或優於**藝術家的靜態覆蓋率。
- **信心**:高。有真實生產 mesh 當 ground truth;藝術家 mesh 描到 PSD 切件 alpha 上 IoU 0.95~0.98
  (非平凡值)反向確認**方向/素材對齊正確**(PSD切件 ↔ Award uvs 同一份、同朝向);視覺疊圖佐證。
- **階段**:第 2 階段 / S3(里程碑:S3+S4 端到端串通,對真實生產標的驗收)。

## 數據(`compare_award_mesh.py`,margin=0.03)

| 件 | auto 模式 | 生成頂點 | 藝術家頂點 | 生成 IoU | 藝術家基準 | IoU pass | rest 自交 | overall |
|---|---|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | delaunay-v1 | 35 (hull16) | 78 (hull78) | 0.933 | 0.949 | ✅ | 0 | ✅ |
| 機器人拆件/身體 | delaunay-v1 | 60 (hull20) | 98 (hull40) | 0.966 | 0.948 | ✅(**超越**) | 0 | ✅ |
| 機器人拆件/左手 | delaunay-v1 | 59 (hull19) | 80 (hull42) | 0.964 | 0.977 | ✅ | 0 | ✅ |

視覺疊圖:`knowledge/figures/award_mesh_compare.png`(左藝術家橘/右生成綠,皆疊在 PSD 切件 alpha)。

## ★ 關鍵發現

1. **auto 模式正確地把這 3 件路由到 v1(Delaunay 散點),而非 v2 strip。**
   - 依據:strip 只在「長寬比 ≥ 1.2 且 row-convex」時採用。機器人件長寬比 0.84~1.12(近方/寬),
     不符 → 回退 v1。這與窗簾(高瘦 strip)形成對照。
   - **為何 v1 對這幾件是對的**:knowledge/s4 已確認**這 5 件在 Award 無 deform timeline** ——
     靠骨骼/權重變形,非逐頂點 deform。無極端單向拉伸 → v1 散點拓樸的「靜態最優覆蓋」正合適,
     不需 v2 為耐 deform 犧牲的規則直條。**deform-bearing 件用 v2、bone/weight-driven 件用 v1** ——
     auto 的長寬比+row-convex 閘剛好近似這條分界。
2. **生成 mesh 更精簡卻不輸覆蓋率**:v1 用約藝術家一半的頂點達到 ≈ 覆蓋率(身體甚至 0.966 > 0.948)。
   → 對「靜態 / 骨骼驅動」件,自動生成的頂點效率可接受。
3. **反向確認素材閉環(topology 層)**:藝術家 mesh(atlas-region-local uvs 0..1)描到 **PSD 切件** 的
   alpha 上就有 0.95~0.98 IoU → PSD 切件與 Award 貼圖是同一素材、同朝向。補強了 s4 的 alpha-IoU 閉環。

## ⚠️ 誠實邊界(這次「沒」驗到什麼)

- Award 這 3 件**無 deform timeline** → **無法跑真實位移場 deform 閘**(區別 v1/v2 的硬約束)。
  本次 AC = **靜態覆蓋率對齊 + rest-pose 良構(0 自交 / 0 退化 / 格式正確)**,
  **不含**「耐大變形」驗證。即:此處證明的是「v1 能為骨骼驅動件產出堪用的靜態 mesh」,
  **不**推翻「deform-bearing 件仍需 v2」的先前結論(見 `s3-four-mesh-generalization.md`)。
- 視覺觀察:生成 光暈 對頂部細長觸手 / 底部細足**略欠覆蓋**(粗規則格漏細附肢),藝術家用較密邊界取樣補足。
  IoU 仍在 margin 內,但若要更貼合細節,需提高邊界取樣密度(v1 的 Canny 點數 / hull 細分)。

## 修過的坑

- `deform_eval.check(verts,tris,setup_signs)` 的 `setup_signs` 要傳**布林 `area>0`**,
  不能傳 `np.sign()`(-1/0/+1):`(a>0) != setup_signs[i]` 對 -1.0 會恆為 True → 假性「全三角翻面」。
  修正後 rest flips 皆 0(同組頂點自比必然),真正有意義的良構指標是 `self_intersections`。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
python3 tools/mesh_gen/compare_award_mesh.py --parts-dir /tmp/robot_parts   # all_pass=True
```

## 下一步

- 把慣例固化成「件 → Spine mesh attachment」寫出器(SkelToJson):PSD 切件 →(mesh via v2 auto)
  + slot 命名 `<PSD名>/<圖層名>` + size(+2px)+ atlas 0.70 縮放 → 端到端產可載入的 Spine JSON。
- (可選)提高 v1 邊界取樣密度以貼合細長附肢,並加「hull 覆蓋率」子指標抓「漏細附肢」這種 IoU 不敏感的欠缺。
