# S3 端到端:PSD 件 → 生成 mesh → 對照 Award 真實 mesh

- **結論**:把 `robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手)跑「S4 切件 → S3 `generate_mesh_v2`」,
  與生產 spine `Award` 的藝術家 mesh 做**靜態幾何**對照,**3 件全 overall_pass**。這是 S3 生成器
  第一次對**真實生產標的 + 藝術家真值**(非合成、非窗簾)端到端驗收通過。
- **依據**:`tools/mesh_gen/validate_psd_to_mesh.py`(2026-07-22 執行,exit 0)。
- **信心**:高(對藝術家真值量化,同 frame 可比;負面向也誠實記錄如下)。
- **相關階段**:專案第 2 階段(S3 mesh + S4 切圖串接)。

## 量化結果(gen v1 Delaunay,margin 0.02)

| 件 | gen IoU (PSD frame) | artist IoU (PSD) | artist IoU (atlas) | gen 頂點 | artist 頂點 | setup 自交 | pass |
|---|---|---|---|---|---|---|---|
| 光暈 | 0.9331 | 0.9486 | 0.9795 | 35 | 78 | 0 | ✅(margin 內) |
| 身體 | 0.9660 | 0.9477 | 0.9760 | 60 | 98 | 0 | ✅(**優於**藝術家) |
| 左手 | 0.9642 | 0.9768 | 0.9681 | 59 | 80 | 0 | ✅(margin 內) |

- **生成 mesh 覆蓋率 ≈ 或優於藝術家,且頂點數少 ~25–55%**(35–60 vs 78–98)→ S3 拓樸精簡度不劣於人手。
- setup pose 下 3 件皆 0 自交 / 0 翻面 / 0 退化,format 合法(hull-first、unweighted)。
- 3 件長寬比皆 < 1.2 → `generate_mesh_v2` auto 全回退 **v1 Delaunay**(strip 只對高瘦窗簾觸發)。
  → 本次實質驗收的是 **v1 散點 Delaunay 在真實不規則團塊形狀上的靜態表現**。

## 誠實記錄的限制(不要被「全過」誤導)

1. **Award 機器人 mesh 是 weighted(骨骼驅動)、無 deform timeline** → **無法**跑
   `deform_eval.transfer_deform_check`(沒有真實逐頂點位移場可轉移)。骨骼旋轉下的耐受度是
   **另一個 regime**,本 chunk 未涵蓋。窗簾(main_draw)那條「靜態≠變形穩健」的教訓在此**不適用也未被推翻**。
2. **光暈是三件中最難的**:藝術家用「全 hull 78 點」貼合羽化光暈邊界;生成器 Douglas-Peucker
   邊界簡化(35 點)略切掉軟邊,gen IoU 0.9331 低於藝術家 0.9486 約 1.55%,**僅靠 margin 過關**。
   → 若之後要求 IoU **嚴格 ≥ 藝術家**,光暈需更密的邊界取樣(調 `epsilon_frac` 或改 strip/contour 混合)。
3. **frame 差異**:uvs 在 atlas frame(+2px padding)下 IoU 較高(0.976–0.980);同 frame 公平基準用
   `artist_iou_on_psd`(PSD 切件無 padding)。工具兩者都輸出,避免用 padding 差異灌水。

## 意義 / 下一步槓桿

- **S3 + S4 已串成端到端**且對真實生產標的驗收:PSD → 切件(無損)→ 生成 mesh(覆蓋 ≈ 藝術家、更精簡、setup 乾淨)。
- 尚缺「件 → Spine JSON 組裝(SkelToJson)」把生成 mesh + 命名慣例 `<PSD檔名>/<圖層名>` + size+2px
  寫成可直接進 Cocos 的 attachment;那是把本 chunk 產物變成可用資產的最後一哩。
- 光暈羽化邊界 → S3 邊界取樣密度的自適應(依 hull 曲率/羽化寬度)是可量化的收斂目標。
