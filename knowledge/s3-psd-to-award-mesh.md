# S3 端到端驗收 — PSD 切件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把 S4(PSD 切件)與 S3(mesh 生成)串成端到端,對**真實生產 mesh**(Award「機器人拆件」
  的光暈/身體/左手 3 件)驗收。**3 件全 `overall_pass`**:我方 CPU 生成的 unweighted mesh 在
  **靜態覆蓋率(IoU)追平或超過藝術家**、頂點數更精簡、且通過靜態幾何閘(合法 spine 格式 /
  重心在內 / 0 退化 / 0 孤兒)。這是 S3 首次對「真實藝術家 mesh」而非合成/自產真值的對照。
- **信心**:中高。覆蓋率+拓樸對真實真值成立;但**覆蓋率 IoU 是靜態代理指標**,見下方界定。
- **階段**:第 2 階段 / S3×S4 端到端(里程碑候選)。
- **可重現**:`python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd --out /tmp/robot_pieces`
  → `python3 tools/mesh_gen/compare_award_mesh.py --figs knowledge/figures/psd_award_mesh`(exit 0 = all_pass)。

## 量化結果(對 PSD 切件 alpha)

| 件 | 我方 mode | 我方 v / hull / tri | 我方 IoU | 藝術家 v / hull / tri | 藝術家 IoU | 覆蓋 | 經濟 |
|---|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 35 / 16 / 49 | 0.933 | 78 / 78 / 76 | 0.949 | ✅(margin 0.02) | ✅ |
| 身體 | delaunay-v1 | 60 / 20 / 97 | **0.966** | 98 / 40 / 154 | 0.948 | ✅(**超過**) | ✅ |
| 左手 | delaunay-v1 | 59 / 19 / 97 | 0.964 | 80 / 42 / 116 | 0.977 | ✅(margin 0.02) | ✅ |

- 3 件長寬比皆 <1.2 → `generate_mesh_v2` auto 模式**回退 v1 Delaunay**(strip 只適合窗簾式高瘦件)。
  → 本次實測 v1 對「不規則有機形」真實件仍達標。
- **光暈**藝術家用 78v **純外框**(hull=78、無內部點、76 三角=扇形耳切)追柔性光暈輪廓;
  我方 35v(含內部點)覆蓋 93.3%,頂點僅一半。
- **身體**我方覆蓋率**反超藝術家**(0.966 > 0.948):藝術家身體 mesh uv_x 只到 0.759,右側留白
  (mesh 未鋪滿 region);我方沿 alpha 輪廓貼合更緊。

## ★ 關鍵發現:Award JSON mesh uvs 是「邏輯 region-local」,與 PSD 來源同向

- 先前疑慮(STATE):「Award mesh uvs 為 atlas UV,需先轉 region 局部」;且身體 uv_x 只到 0.759、
  光暈/身體在 atlas **rotate=true** 打包(左手 rotate=false)→ 懷疑 uv 被旋轉。
- **以 PSD 切件 alpha 為外部真值,窮舉 8 種方向變換(id/翻u/翻v/翻uv/swap×4)取最高 IoU**:
  **3 件全部 `id` 勝出且差距明顯**(光暈 0.949 vs 次佳 swap 0.705;身體 0.948 vs flipV 0.604;
  左手 0.977 vs flipU 0.763)。
- **定論**:Spine JSON 的 mesh `uvs` 是**未旋轉 region 的邏輯正規化座標(0..1)**;atlas 的
  `rotate`/0.70 縮小只影響**貼圖打包層**,由 atlas loader 處理,**不進 JSON uvs**。
  → 重建藝術家覆蓋直接 `uv * (W,H)` 即可,不需 atlas 旋轉資訊;身體 0.759 是**藝術真的沒鋪滿**,非旋轉假象。
- 方法論(呼應 RULES / s4 的 atlas_crop 教訓):**round-trip 自洽 ≠ 絕對方向正確;方向要拿外部真值(PSD)校驗**。
  這次的 8-方向窮舉即是把該教訓工具化。

## ⚠️ 範圍界定(誠實)

- 這 3 件在 Award 是 **weighted mesh 且無 deform timeline**(靠骨骼權重變形,非逐頂點 deform)。
  故本比對是**靜態覆蓋率 + 拓樸經濟度**,**不是 deform 穩健度**。deform 閘(`transfer_deform_check`)
  對這批件無真實位移場可轉移,不適用。
- **覆蓋率 IoU 是靜態代理**:藝術家的 weighted mesh 內部拓樸是為**骨骼變形**調過的(如左手 hull=42
  佔 80v 一半、身體內部點分佈);我方 unweighted 只保證**輪廓**貼合,不複製其變形能力。
  → 「覆蓋追平藝術家」≠「變形手感追平藝術家」。後者需 weighted 生成(BBW)+ 有 deform 的標的才可驗。

## 下一步啟示

1. **端到端骨幹已通**:真實 PSD → 切件 → S3 mesh → 對真實 spine mesh 量化達標。剩「件→Spine JSON 組裝」
   (SkelToJson:`機器人拆件/<圖層名>` 命名 + size+2px + rotate/0.70 打包)即可產出可載入的 attachment。
2. **weighted 生成(BBW)**是把「覆蓋追平」升級為「變形追平」的關鍵缺口(對應 S3 路線的權重部分);
   需要有 deform timeline 或骨架的標的才能驗收 → 與 S5 骨架能力綁定。
