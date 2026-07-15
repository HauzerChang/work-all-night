# S3 對照 Award 真實(藝術家)mesh — 端到端驗收通過 + 覆蓋率自我收斂

- **結論**:S3 生成器對**真實生產標的**驗收通過。拿 Award spine 機器人的 3 個 mesh attachment
  (光暈 / 左手 / 身體)當藝術家真值,S3 自動生成的 mesh 在同一素材、同一像素空間下,
  **覆蓋率不遜於藝術家、且頂點數更精簡**,足跡一致性 IoU 0.94–0.96。
- **依據**:`tools/mesh_gen/compare_to_award.py`,`overall_pass: True`(2026-07-15)。
- **信心**:高(對照真實藝術家 mesh + 座標映射經 AC-A 自驗)。
- **相關階段**:第 2 階段 S3 mesh 生成器(端到端串 S4 切件 → S3 mesh → 對真實標的)。

## 做法(共同座標框)

- 用 `atlas_crop.extract` 把 slot region 去旋轉裁成「上正」素材(atlas 打包 ~0.70 縮放,
  但兩邊都用同一張 → IoU 尺度無關)。
- **藝術家 mesh**:JSON 的 `uvs` 為 **region-local 正規化 [0,1]**(經 AC-A 實證);`uv*(regW,regH)`
  映進 region 像素後三角化足跡與 region alpha 的覆蓋率 IoU = **0.97–0.98** → 同時驗證映射正確。
- **S3 mesh**:直接對這張 region alpha 跑 `generate_mesh_v2`(auto)。三件長寬比 <1.2 → 全走
  **v1 Delaunay** 分支(非 strip)→ 本次等於在真實件上驗 v1。

## AC 與結果

| 件 | region px | 藝術家 nv/hull | 藝術家 IoU | S3 nv/hull | S3 IoU | 足跡 IoU |
|---|---|---|---|---|---|---|
| 光暈 | 496×480 | 78 / 78(全 hull) | 0.9795 | 61 / 22 | 0.9656 | 0.954 |
| 左手 | 181×152 | 80 / 42 | 0.9681 | 48 / 18 | 0.9602 | 0.945 |
| 身體 | 267×299 | 98 / 40 | 0.9760 | 61 / 21 | 0.968  | 0.955 |

AC:A 藝術家覆蓋 ≥0.90(驗映射)· B S3 覆蓋 ≥0.90 且 ≥藝術家−0.05 · C 頂點 ≤max(藝×1.6, 藝+20)
· D 足跡一致 ≥0.85 —— **四條全過**。

## 關鍵發現

1. **軟邊/凸形大件的覆蓋率受 hull 取樣密度(epsilon)限制,非內部點**。光暈是純輻射漸層
   (藝術家用 **78 點全 hull 扇形**、0 內部結構);S3 預設 `epsilon=0.008` 過度簡化羽化邊 →
   覆蓋率只 0.9292(與藝術家 0.9795 相差且卡在 AC 門檻)。epsilon 掃描:
   0.008→0.9292 / 0.004→0.9656 / 0.002→0.9832 / 0.001→0.9924。
   → 與先前 strip 的「**IoU 由 rows 決定、cols 不影響**」同構:Delaunay 版是「**IoU 由 epsilon 決定**」。
2. **修法 = 生成器自帶評估器自我收斂**(呼應「每能力必配評估器」):`generate_mesh.generate` 加入
   `coverage_iou` 迴圈 —— 覆蓋率未達 `target_iou`(預設 0.95)就對半調細 epsilon 重生,
   直到達標 / 觸 epsilon 下限 / 觸頂點預算。光暈自動 0.008→0.004 達 0.9656、nv 61(<藝術家 78)。
   左手/身體預設已 ≥0.95 → 不觸發額外細分,維持精簡。
3. **藝術家 mesh 為 weighted**(供自由變形/綁骨),但機器人這些 slot 在全部動畫**無 deform timeline**
   → 為靜態件。故本比對聚焦靜態覆蓋 + 拓樸;S3 mesh 的耐變形另由 `deform_eval` 單獨把關。
4. **S3 比藝術家精簡**:三件 S3 頂點數都明顯少於藝術家(61<78、48<80、61<98)卻達同等覆蓋 →
   對「純覆蓋型」件 S3 拓樸效率佳(藝術家頂點多可能是為了 weighted 綁骨的變形自由度,非覆蓋需要)。

## 回歸驗證(改動安全性)

`generate_mesh` 加 refine 迴圈只影響 **v1 Delaunay 分支**;main_draw 4 mesh 走 strip 模式不受影響:
curtain_left/right/shadow 重驗 IoU 0.9338/0.9335/0.9549、self_intersections=0,與改前一致。
(shadow2 與 shadow 共用同一 region,region 名查詢需另指定,屬既有細節非本次回歸。)

## 待續

- 把此對應慣例(`機器人拆件/<圖層名>` + region-local uv + 0.70 打包)固化進「件→Spine JSON 組裝
  工具」(SkelToJson),端到端從 PSD 件產出可載入的 Spine mesh attachment(STATE 候選 #2)。
- S3 目前產 **unweighted**;要對接藝術家 weighted 用法需 BBW 權重(S3 路線的下一塊)。
