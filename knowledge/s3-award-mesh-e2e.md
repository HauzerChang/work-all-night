# S3 端到端:真實生產貼圖件 → 生成 mesh → 對照 Award 真實 mesh(里程碑)

- **結論**:對機器人 3 個 mesh 件(光暈/身體/左手)在 **Award 生產貼圖 region** 上跑 S3 生成器,
  對照 **Award 真實生產 mesh**,3 件**全部 PASS**:覆蓋率 IoU **超過**藝術家自身覆蓋率、
  頂點數**更精簡**、setup 拓樸 0 自交。首次把「素材件 → 生成 mesh」對**真實生產標的**閉環驗收。
- **信心**:高(共同座標系直接對照真值 mesh + 覆蓋率/頂點/自交三閘 + 修正後重驗)。
- **階段**:第 2 階段 / S3(里程碑:合成/自產真值 → **真實生產 mesh 真值**)。
- **可重現**:`python3 tools/mesh_gen/validate_award_mesh.py --gen v2`(ALL PASS)。

## 結果(gen v2,epsilon_px=2、內部預算 12)

| 件 | region | 我方 IoU | 藝術家 IoU | 我方頂點 | 藝術家頂點 | 我方自交 | 判定 |
|---|---|---|---|---|---|---|---|
| 光暈 | 496×480 | **0.992** | 0.980 | **68** | 78 | 0 | PASS |
| 身體 | 267×299 | **0.993** | 0.976 | **49** | 98 | 0 | PASS |
| 左手 | 181×152 | **0.988** | 0.968 | **48** | 80 | 0 | PASS |

→ 三件覆蓋率都優於藝術家,且頂點數 0.6–0.5×(身體只用一半)。

## 方法(對照框架)

- 共同座標系用 **Award atlas 切件**(`atlas_crop.extract`,多頁自動選 page + CW derotate):
  我方 mesh 與 Award mesh 的 **region-local UV** 同框,IoU 直接可比(尺度不變)。
  PSD 切件 ↔ atlas 切件 alpha-IoU 0.92–0.99 先前已證同素材(`s4-psd-to-spine-real.md`),
  故 atlas region = PSD 件的等價來源。
- 藝術家 mesh 覆蓋率 = 用其三角+region-local UV 光柵化回 region、與 alpha 取 IoU(即
  `validate_against_real.artist_iou` 同法)。
- 三閘:**cover**(我方 IoU ≥ 藝術家−1%)、**budget**(頂點 ≤ 藝術家)、**clean**(setup 0 自交)。

## ★ 關鍵發現:覆蓋率由「邊界取樣密度」決定,內部點不影響(與 strip 的 rows 同構)

- 初版(`epsilon_frac=0.008` 周長相對)**光暈覆蓋率只 0.929 < 0.980 → FAIL**。掃描證實:
  - 覆蓋率**單調隨邊界密度上升**,幾乎**不隨內部點數變化**(maxint 0→40 同一 IoU)。
    這與 S3 strip「IoU 由 rows 決定、cols 不影響」是同一條原理(覆蓋率=邊界擬合)。
- **根因**:`epsilon_frac` 是**周長相對**,大而平滑的件(光暈周長 1927px)得到過大的絕對
  epsilon(~15px)→ Douglas-Peucker 切過平滑曲線 → 邊界內縮、覆蓋率不足。
- **修正**:改用 **絕對像素容差 `epsilon_px`**(DP 對真實輪廓的固定像素偏差,與件大小無關)。
  `epsilon_px=2` 對 3 件全部覆蓋率 > 藝術家且頂點更精簡;3px 亦全過(更省點)。設 **2px 為預設**。
- 內部點對**靜態覆蓋率**無益 → 回退 Delaunay 的內部預算調精簡(`max_interior=12`)守住頂點預算。

## 生成器改動(已落地,含向後相容 + 無回歸)

- `generate_mesh.py`:`boundary_points(mask, epsilon_frac, epsilon_px=None)`;`generate(...,
  epsilon_px=2.0)` 預設走絕對像素;CLI 加 `--epsilon-px`(<0 退回周長相對)。
- `generate_mesh_v2.py`:blob/寬件回退 Delaunay 改 `gen_v1(path, max_interior=12, epsilon_px=2.0)`。
- **無回歸**:main_draw 4 mesh 走 **strip**(不觸及 Delaunay),`validate_against_real --gen v2`
  4 件全 `overall_pass=true`(strip,IoU 0.933/0.933/0.955/0.955)重驗通過。

## ⚠️ 範圍與未測(誠實聲明)

- Award 這 3 件是 **weighted mesh 且無 deform timeline**(靠骨骼權重變形,非逐頂點 deform);
  我方輸出為 **unweighted**。故本輪只驗**靜態拓樸/覆蓋率**,**未**驗 deform 穩健性
  (變形機制不同,無法用 `real_deform_field` 轉移場對照)。
- **後續**:①weighted-mesh deform 對照需另建(BBW 權重生成 + 骨骼驅動;S3 路線的 BBW 部分)。
  ②把 `epsilon_px` 預設 2px + blob 內部 12 固化進切圖→Spine JSON 組裝工具(SkelToJson)。
