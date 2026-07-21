# S3 端到端驗收:PSD 件 → 生成 mesh vs Award 真實生產 mesh

- **結論**:機器人 `robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手),經 `psd_slice` 切件 →
  `generate_mesh_v2`(auto)生成 mesh,對照 **Award 真實生產 mesh** 做覆蓋率/預算/拓樸驗收
  → **3/3 生產相關 AC 全過**(exit 0)。端到端「PSD → 件 → S3 mesh」首次對**真實生產標的**驗收通過。
- **信心**:高(有藝術家真值 mesh 逐件對照,純 CPU 可重現)。
- **相關階段**:第 2 階段 S3(mesh 生成器)× S4(PSD 切圖)串接;工具 `tools/mesh_gen/validate_psd_to_mesh.py`。
- **報告**:`knowledge/figures/s3-psd-to-award-report.json`。

## 對照數字(生成 auto vs 藝術家真值)

| slot | 件尺寸 | 生成 v / hull / IoU | 藝術家 v / hull / IoU | mode | AC |
|---|---|---|---|---|---|
| 機器人拆件/光暈 | 706×683 | 35 / 16 / **0.933** | 78 / 78 / 0.949 | delaunay-v1 | ✅ |
| 機器人拆件/身體 | 379×425 | 60 / 20 / **0.966** | 98 / 40 / 0.948 | delaunay-v1 | ✅ |
| 機器人拆件/左手 | 257×215 | 59 / 19 / **0.964** | 80 / 42 / 0.977 | delaunay-v1 | ✅ |

- **覆蓋率不輸藝術家**(margin 0.02 內;身體甚至略高),且**頂點更精簡**(35/60/59 vs 78/98/80)。
- 藝術家「光暈」用 **hull=78 純輪廓 mesh**(無內部點)——glow 這種軟邊件常見手法;我們的散點 v1 用 35v/16hull 也達標。

## 關鍵事實:這 3 件在 Award **全無 deform**(骨骼驅動)

- 稽核 Award 12 動畫全部 `deform` timeline:**5 個 `機器人拆件/*` slot 皆無 deform**(含 region 的右手/頭)。
- 意義:**這些件靠骨骼 transform 動,mesh 不變形**。故生產相關 AC =「靜態覆蓋 + 頂點預算 + 靜態拓樸乾淨」,
  **不是**耐變形。要求生成 mesh 比真實資產本身還耐變形是過度嚴格 → 因此 deform 只做 informational 探針。

## deform-robustness 探針(informational,非 gating)——但揭示一個改進點

把 main_draw `curtain_left` 的**真實位移場**轉移到生成 mesh(「若這件被拿去 warp 會怎樣」):

| slot | auto(v1)結果 | 強制 strip 結果 |
|---|---|---|
| 光暈 | clean(si=0) | clean(si=0, 30v) |
| 身體 | clean(si=0) | clean(si=0, 30v) |
| **左手** | **si=10 / flips=3 / FAIL** | **clean(si=0, 30v)** |

- **左手(近方形 aspect 0.84)** auto 走 v1 Delaunay,在大單軸拉伸下**自交**;**強制 strip 則乾淨**。
- 這**重申並延伸** `s3-four-mesh-generalization.md` 的發現:v1 散點不耐大拉伸;strip 才耐。
- **改進候選**:`generate_mesh_v2` 的 auto strip 門檻 `aspect≥1.2` 會讓**近方形但可能 warp** 的件落回不安全的 v1。
  對「會變形」的近方形件,現行 auto 不會自動選 strip。**但對本批機器人件無影響**(生產不 deform)。
  - 尚未改 auto 啟發式:strip 需 row-convex + 明確拉伸主軸;方形件無明確主軸,盲目強制 strip 未必對
    (不同 warp 樣式)。留作「當件確定要 deform 時,由上游指定 mode=strip 或給拉伸軸」的設計點。

## 方法論備註

- **同一參考 mask 比對**:生成與藝術家 mesh 都在「切件 alpha」上重建三角求 IoU,消除 +2px padding/offset 的
  微小影響(件尺寸 vs 藝術家 mesh 尺寸差 +2px,對 IoU 影響 <0.3%)。
- **真值即上限**:藝術家 mesh IoU 本身 0.95~0.98(非 1.0),因 mesh 是凸三角覆蓋、邊緣鋸齒;故用
  「gen ≥ artist − margin」而非武斷 0.95(延續 `validate_against_real` 的校正原則)。
