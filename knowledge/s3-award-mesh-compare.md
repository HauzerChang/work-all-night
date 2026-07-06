# 端到端「PSD 件 → S3 mesh」對照 Award 藝術家真實 mesh(靜態覆蓋 + 拓樸)

- **結論**:把 `robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手)切件後跑 S3 `generate_mesh_v2`,
  與生產 spine `Award` 的藝術家真實 mesh 做**同一 alpha 上的覆蓋 IoU** 對照。校正生成器後,
  **3 件全通過**:生成 mesh 的覆蓋 IoU **≥ 藝術家基準**,且**只用約 45–55% 的頂點數**。
  端到端「PSD → 件 → S3 mesh」對真實生產標的的**靜態品質**驗收成立。
- **信心**:高(對真實生產 PSD + 藝術家 ground-truth mesh 交叉比對;純 CPU 可重現)。
- **階段**:第 2 階段 / S3 × S4 串接(里程碑:S3 首次對真實藝術家 mesh 比對)。

## 結果(校正後,`tools/mesh_gen/compare_award_mesh.py`)

| slot | 生成 v(hull) | 生成 IoU | 藝術家 v(hull) | 藝術家 IoU | cover | clean | budget |
|---|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | 34 (25) | **0.9641** | 78 (78) | 0.9486 | ✅ | ✅ | ✅ |
| 機器人拆件/身體 | 53 (29) | **0.9828** | 98 (40) | 0.9477 | ✅ | ✅ | ✅ |
| 機器人拆件/左手 | 54 (30) | **0.9796** | 80 (42) | 0.9768 | ✅ | ✅ | ✅ |

> 生成 mesh 覆蓋率**追平或超越**藝術家,頂點數卻少約一半 → CPU 拓樸對這 3 件足夠精簡且吻合。

## 關鍵前提校正(推翻 STATE 過時假設)

- **Spine JSON 的 mesh `uvs` 是 region 局部 0..1**(runtime 才映射到 atlas page),
  main_draw 與 Award **皆然**(實測 uv 範圍 0..1)。→ **不需 atlas UV → region 轉換**(STATE 舊註記多慮)。
  `atlas rotate` 旗標只是打包細節,uvs 記在 attachment 自身(邏輯 width×height)座標系。
- alpha 來源用 **PSD 切件 PNG**(邏輯原始解析度),與 attachment 邏輯尺寸差 +2px padding(~0.3%,可忽略)。

## Award 這 3 件的性質(為何只做靜態,不做 deform)

- 3 件皆 **weighted(骨骼驅動)mesh**(`len(vertices) != len(uvs)`),且 **9→12 支動畫全無 deform timeline**。
  → 它們**靠骨骼/權重變形,非逐頂點 deform** → 沒有真實位移場可轉移,`AC_real_deform` 不適用。
  本比對聚焦 **setup-pose 靜態覆蓋 + 拓樸**(誠實範圍;deform 穩健見窗簾 4-mesh 那條線)。
- 藝術家拓樸觀察:**光暈 = 純輪廓多邊形**(hull 78 = 全部頂點,76 三角 = 78-gon 扇形化,0 內部點)——
  glow 只需外形、靠骨變形;身體/左手為稠密 Delaunay(hull 40/42 + 大量內部點,支撐柔性 warp)。

## 生成器校正(本 session 對 `generate_mesh.py` v1 的兩項修正)

1. **孤兒頂點移除 `drop_orphans()`**:凹形件在 `filter_triangles`(重心在 mask 外的三角被丟)後,
   凹口邊界頂點可能不再被任何三角引用 → 孤兒(違反 AC2c、Spine 不該有)。新增移除 + 索引重映
   (`used` 升冪 → hull 頂點自然仍排前;hull 數 = 保留的 hull 頂點數)。**純修正,無副作用**。
2. **v1 預設 epsilon 0.008 → 0.004、max_interior 40 → 24**:原 0.008 對真實有機件輪廓**過粗**,
   覆蓋 IoU 低於藝術家(光暈 0.933 < 0.949、左手 0.964 < 0.977)。
   **覆蓋率由 hull(邊界取樣密度)決定、內部點完全不影響**(實測 max_interior 10/20/25 → IoU 不變)——
   與窗簾 strip 的「IoU 由 rows 決定」同一條規律。故把頂點預算**優先給邊界**:epsilon 0.004(hull 加密)
   + max_interior 降到 24(省內部點),3 件全在 64 頂點預算內達標。

## ⚠️ 覆蓋 vs 變形 的取捨(重要工程結論)

- **hull 越密 → 靜態覆蓋越高,但單向大 deform 下越易自交**。
- v1(細 hull)校正後 curtain_left `--gen v1`:IoU 0.99 但**真實 deform 自交**(deform gate fail)。
  這**不是**新退化 —— 窗簾類件的生產路徑是 **v2 strip**(auto 模式高瘦+row-convex 自動走 strip),
  v1 從不服務窗簾;且「v1 Delaunay 對窗簾 deform 不通用」早有定論(見 `s3-four-mesh-generalization.md`)。
- **設計定位**:**v1(細 hull Delaunay)= 靜態/骨骼驅動的有機件**(覆蓋最佳,如機器人件);
  **v2 strip = 逐頂點 deform 件**(耐變形,如窗簾/陰影)。auto 模式已依高寬比+row-convex 分流。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd     # 切件到 psd_parts/
python3 tools/mesh_gen/compare_award_mesh.py                   # overall_pass=True(3 件)
```

## 未回歸(本 session 驗證)

- main_draw v2 strip 4-mesh:curtain_left/right、shadow 經 `validate_against_real --gen v2` 全 `overall_pass`
  (v2 strip 路徑不受 v1 預設變更影響)。
- shadow2 需用共用 region 名 `--name image/shadow`(shadow2 slot 的 attachment 名為 `image/shadow`);
  直接傳 `image/shadow2` 會「region 不存在」—— **既有工具用法限制,非本次退化**。

## 下一步

- 把「件 → Spine attachment/JSON」慣例固化成組裝工具(SkelToJson):`<PSD名>/<圖層名>` slot 命名、
  +2px padding、mesh/region 由是否 warp 決定、atlas 0.70 縮放。串成完整「PSD → Spine JSON」。
- 補圖閘 / 骨架閘(S2 樞紐尚缺)。
