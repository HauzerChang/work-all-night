# S3 端到端驗收:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh(里程碑)

- **結論**:把 `robot_parts.psd` 的 3 個 mesh 件(光暈 / 身體 / 左手)經 `psd_slice` 切件 →
  `generate_mesh`(S3)→ 對照 **Award(big win)真實生產 mesh** 做靜態幾何驗收,**3 件全 `overall_pass`**。
  這是 S3 首次對「與 main_draw 窗簾**不同類別**的真實生產 mesh」端到端驗收(PSD→件→mesh 全鏈)。
- **信心**:高。真值 = Award 藝術家 mesh(uvs/triangles);件 alpha = PSD 切件(session 006 已以
  alpha-IoU 0.92~0.99 確認 = spine 生產貼圖同素材)。評估器先自檢(藝術家 mesh 填入件 alpha
  IoU 0.95~0.98,證明座標框一致)才下判定。
- **階段**:第 2 階段 / S3(推廣到第二類真實 mesh)+ S3↔S4 串接。

## 這類 mesh 與窗簾的差異(為何是好的通用性測試)

| | main_draw 窗簾/陰影 | Award 機器人 光暈/身體/左手 |
|---|---|---|
| 變形方式 | **逐頂點 deform timeline**(9 anim 全有) | **無 deform timeline**;靠 **weighted bone** 變形 |
| 藝術家拓樸 | 直條 strip(耐單軸大拉伸) | 密集 Delaunay 式(hull 40/42 + 內部點;光暈為 78v 全 hull 環狀 fan) |
| 形狀 | 高瘦 row-convex | blob / 凹形 / 羽化邊 |

→ 因**無 deform timeline**,本驗收**不套用** real-deform 轉移閘(誠實標 `N/A`),
改用靜態幾何三 AC。這也印證 s4 的觀察:mesh vs region、strip vs dense 是**美術依變形需求**選的。

## AC(靜態幾何,對照藝術家真值)

1. **AC_iou**:生成 mesh 覆蓋率(vs 件 alpha) ≥ 藝術家 mesh 對同一 alpha 的覆蓋率 baseline。
2. **AC_topo**:`evaluate_mesh` 全過(格式 / 重心在 mask / 無退化 / 無孤兒 / 頂點預算)。
3. **AC_budget**:生成頂點數 ≤ 藝術家頂點數 × 1.15(精簡度不落後藝術家太多)。

## 關鍵發現

1. **`auto` 路由正確**:3 件 blob 皆被 `generate_mesh_v2` auto 判為**非 strip → 回退 v1 Delaunay**
   (aspect 未達 1.2 或非 row-convex)。strip 是為窗簾單軸拉伸設計,對 blob 用 Delaunay 才對——
   與藝術家自己的拓樸選擇一致。
2. **v1 預設 `epsilon_frac=0.008`(為窗簾調)對羽化/凹形件覆蓋率略低於藝術家**:
   光暈 0.933 < 0.949、左手 0.964 < 0.977(身體 0.966 > 0.948 已過)。
3. **覆蓋率單調隨邊界取樣密度上升**(與 v2「IoU 由 rows 決定」同一機制:IoU ≈ hull 多邊形貼合度,
   內部點不影響覆蓋)。epsilon 掃描(0.008→0.001)IoU 對 3 件皆單調升。
4. **adaptive 解法(自我校準到目標)**:沿 epsilon 階梯加密,取**達標且拓樸全過的第一個(最精簡)**版本。
   結果每件挑到最省的密度:

| 件 | chosen eps | 生成 v (hull) | 生成 IoU | 藝術家 v | 藝術家 IoU | 結果 |
|---|---|---|---|---|---|---|
| 光暈 | 0.002 | 64 (45) | 0.980 | 78 | 0.949 | ✅ 三 AC 全過 |
| 身體 | 0.008 | 60 (20) | 0.966 | 98 | 0.948 | ✅(預設即足) |
| 左手 | 0.003 | 75 (35) | 0.985 | 80 | 0.977 | ✅ |

→ **生成 mesh 以更少頂點達到 ≥ 藝術家的輪廓覆蓋**,拓樸全乾淨。

## 教訓 / 副產

- **coarse epsilon 的 topo 失敗來源是「孤兒內部點」**(centroid 過濾後有內部點無三角引用):
  光暈 eps 0.003 有 2 孤兒,加密到 0.002 消失。→ adaptive 同時把 IoU 與孤兒一起解掉。
- **不硬改 v1 全域預設**(0.008 是窗簾情境的合理值,且 main_draw 走 strip 不受影響);
  把「加密到覆蓋目標」做成 adaptive 迴圈更通用,不會過densify 小件。
- 未動任何既有工具 → main_draw 4 mesh + slicing 回歸不受影響(已抽驗 curtain_left overall_pass)。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
# 預設不足(示範):光暈/左手 iou_pass=False
python3 tools/mesh_gen/compare_to_award.py --parts-dir /tmp/robot_parts --no-adaptive --eps 0.008
# adaptive(自我校準到藝術家 baseline):3 件全 overall_pass,exit 0
python3 tools/mesh_gen/compare_to_award.py --parts-dir /tmp/robot_parts
```

## 下一步

- 把「件→Spine JSON attachment」組裝固化(SkelToJson):`PSD名/圖層名` slot 命名、+2px padding、
  mesh vs region 分配、adaptive mesh 密度 → 端到端輸出可用 Spine JSON(候選 #2)。
- weighted-bone 變形的**權重**尚未生成(這 3 件靠 bone 變形,S3 目前只出 unweighted 幾何);
  若要完全複現 Award mesh 行為,需 BBW 權重(S3 路線圖後段)。目前幾何/拓樸已對標藝術家。
