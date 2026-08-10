# S3 端到端驗收 — PSD件 → generate_mesh_v2 → 對照 Award 真實 mesh

- **結論**:把 S4(PSD 切件)與 S3(mesh 生成)串成端到端,對**真實生產標的**(Award spine 的
  機器人拆件 mesh)驗收:用 `robot_parts.psd` 切出的 3 個 mesh 件(光暈/身體/左手)跑
  `generate_mesh_v2`,生成 mesh 的靜態覆蓋率 IoU **達到或超過藝術家真實 mesh 覆蓋率(margin 0.02)**,
  且**頂點數大幅更少**。3 件全 `overall_pass`。
- **信心**:高(對真實生產 mesh 交叉比對;藝術家自身覆蓋率作基準;格式/退化/孤兒閘全過)。
- **階段**:第 2 階段 / S3+S4 端到端(里程碑:合成/單能力 → 跨能力串接對真實標的)。

## 資料與方法

- 來源走**完整 PSD 契約路徑**:`psd_slice.slice_psd(robot_parts.psd)` → 各件緊湊 PNG(alpha),
  而非從 atlas 切 → 驗的是「美術交 PSD → 自動生 mesh」這條端到端。
- 對照真值:`Award.json` 對應 slot `機器人拆件/<圖層名>` 的藝術家 mesh(uvs 為 **region-local 0..1**,
  非 atlas-page UV —— 先前假設需轉換,實測不需要;三 mesh uv 皆近滿 0..1 跨度)。
- 指標:同一 alpha mask 下,把「生成 mesh 三角」與「藝術家 mesh 三角」各自填多邊形求 IoU,
  比 `gen_iou >= artist_iou - 0.02`。

## 結果(3 件全過)

| 件 | 生成 mode | 生成 v/tris | 生成 IoU | 藝術家 v/hull/tris | 藝術家 IoU | Δ | pass |
|---|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 35 / 49 | 0.9331 | 78 / 78 / 76 | 0.9486 | -0.0155 | ✅ |
| 身體 | delaunay-v1 | 60 / 97 | 0.9660 | 98 / 40 / 154 | 0.9477 | **+0.0183** | ✅ |
| 左手 | delaunay-v1 | 59 / 97 | 0.9642 | 80 / 42 / 116 | 0.9768 | -0.0126 | ✅ |

- 生成 mesh 全部**格式有效、0 退化三角、0 孤兒頂點**。
- **用更少頂點達到相當覆蓋率**(35 vs 78、60 vs 98、59 vs 80)。

## 關鍵發現(可重用)

1. **v2 `auto` 對這 3 件全選 Delaunay-v1,不是 strip** —— 因為它們**非高瘦**(aspect H/W
   分別 0.97 / 1.12 / 0.84,皆 < 1.2 門檻)。strip 模式是為窗簾(高瘦、單向拉伸)設計;
   robot 這種緊湊/寬件回退 Delaunay 是對的路由。**這是首批 auto 未觸發 strip 的真實件**。
2. **Award 這些 mesh 皆 weighted**(`len(vertices)!=len(uvs)`),且**無 deform timeline** ——
   靠骨骼/權重(skinning)變形,非逐頂點 deform。故 per-vertex **deform 閘 N/A**;
   本輪只驗靜態覆蓋率 + 格式。
3. 光暈藝術家 mesh 是 **78 頂點全 hull(0 內部點)的環狀 fan**,IoU 仍只 0.949 ——
   因為是柔性發光(羽化邊),mesh 本就不緊貼 alpha>8 邊界;我方 IoU 同級屬正常。
4. uvs 為 region-local(非 atlas-page)→ 覆蓋率比對可直接 `uv*mask_size`,免座標轉換。

## 未解 / 下一步

- **⚠️ Delaunay-v1 的變形穩健性對這批件未驗**:先前結論「v1 在大單向拉伸下自交」是對 deform-timeline
  件而言;這批是 skinning 驅動,理論上變形較平滑。但**無真實位移場可轉移**(Award 無 deform),
  故無法用既有 deform 閘量化。若要補:需 Award 的 skinning 權重 + 骨骼動畫做 forward-kinematics
  變形後再驗自交(比 deform-timeline 複雜)。屬 S5(骨架/權重)範疇。
- 下一步槓桿:把「件→Spine attachment」組裝(命名 `PSD名/圖層名`、+2px padding、mesh/region 分配)
  固化成 SkelToJson 工具,產出可載入 spine 的 JSON(見 STATE 候選 2)。

## 可重現

```
python3 tools/mesh_gen/compare_psd_to_award.py   # 自動切 PSD → 生 mesh → 對照 Award,3 件 OVERALL_PASS
```
