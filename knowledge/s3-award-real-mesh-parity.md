# S3 端到端驗收 — PSD件 → 生成 mesh 對照 Award 真實生產 mesh(有真值)

- **結論**:S3 `generate_mesh_v2`(auto)對 Award(big win spine)中機器人拆件的 3 個
  **真實生產 mesh**(光暈/身體/左手)自動生成的 mesh,**靜態覆蓋率(IoU)全達生產 mesh 同級**
  (差距 ≤0.008,左手甚至超過藝術家),且**頂點數更精簡**(57–64 vs 藝術家 78–98)。
  這是「PSD→件→mesh」對**真實生產標的**的端到端驗收(先前只在 main_draw 自身 mesh 上驗)。
- **信心**:高(對照真實生產 spine 的 ground-truth mesh;IoU 用同一像素框公平比對;
  評估器格式/退化/孤兒自檢全過;main_draw 4 mesh 回歸不受影響)。
- **階段**:第 2 階段 / S3(串接 S4 切件 → S3 生成 → 生產真值對照)。

## 對照結果(`tools/mesh_gen/compare_award_mesh.py`)

| 件 | 生成 IoU | 藝術家 IoU | parity(±0.02) | 生成 nv | 藝術家 nv | mode |
|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | 0.9779 | 0.9795 | ✓ (−0.0016) | 64 | 78 | delaunay-adaptive |
| 機器人拆件/身體 | 0.9686 | 0.9760 | ✓ (−0.0074) | 63 | 98 | delaunay-adaptive |
| 機器人拆件/左手 | 0.9755 | 0.9681 | ✓ (+0.0074) | 57 | 80 | delaunay-adaptive |

**overall_pass = True**。

## 方法要點

- 遮罩來源 = `atlas_crop.extract`(de-rotate 後、atlas ~0.70 尺度)的切件 alpha。
- Award mesh 的 `uvs` 是 **region-local [0,1]**(與 main_draw 同慣例,非全 atlas UV)→ `uvs×(W,H)`
  直接落在切件上;藝術家 mesh 重組 IoU 高達 0.968–0.980 反證此對齊正確。
- 生成器吃**同一張切件** → 生成 mesh 與藝術家 mesh 在同一像素框、同尺度公平對照。

## 這次揪出並修好的 2 個生成器缺陷(由真值對照驅動)

1. **固定 epsilon 對「大面積細緻剪影」邊界取樣不足** — 光暈用預設 `epsilon=0.008` 只得
   hull=14、IoU 0.9296(落後生產 0.98 達 −0.05),且粗糙凹邊界會 strand 出孤兒頂點。
   → 新增 **`generate_adaptive`**:以 **hull-only 覆蓋率**(不需 ground truth 的自我指標)為目標,
   由粗到細降 epsilon(0.008→0.0008),達 `boundary_iou_target=0.965` 或觸頂點預算即停。
   光暈自動降到 eps 0.002 級距 → IoU 0.978、0 孤兒。`generate_mesh_v2` 非 strip 分支改用此路徑
   (`mode=delaunay-adaptive`)。curtain/shadow 等簡單件維持粗 hull(第一階 eps 即達標)。
2. **凹形三角過濾後遺留內部孤兒頂點** — `filter_triangles`(centroid-in-mask)在凹處刪三角後,
   某內部點可能不再被任何三角引用(身體:index 22)。→ 新增 **`prune_orphans`**:只清**內部**孤兒
   (hull 頂點 0..n_hull−1 一律保留以維持邊界 loop 與 hull-first 順序),重新編號 triangles。
   `generate` / `generate_adaptive` 尾端都套用。

兩個修正**只影響 delaunay 分支**;main_draw 的 4 mesh 全走 strip → 回歸驗證 4/4 全過(IoU/deform 不變)。

## ⚠️ 誠實的範圍限制

- **Award 機器人這 5 件在 spine 無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform)
  → 無真實位移場可轉移,故本對照**只驗靜態覆蓋率 parity,不含變形閘**(不拿未校準合成壓力冒充)。
  變形穩健性仍靠 main_draw 的真實 deform 閘背書(strip 拓樸)。
- 生成 mesh 頂點較少屬**靜態覆蓋**優勢;藝術家多出的內部頂點多為**權重變形**用途,
  本 unweighted 靜態比對不涵蓋。若日後要驅動 bone-weighted warp,內部密度需另評。

## 可重現

```
python3 tools/mesh_gen/compare_award_mesh.py            # 3 件 overall_pass=True
python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot image/curtain_left --name image/curtain_left  # 回歸
```
