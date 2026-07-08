# S3+S4 端到端:PSD件 → 生成 mesh → 對照 Award 真實生產 mesh

> 結論:**「PSD→件→S3 mesh」對真實生產標的(Award 機器人拆件 3 個 mesh)靜態驗收全通過。**
> 過程揪出並修好 v1 delaunay 的一個通用性缺陷(固定 epsilon 對「邊界主導的柔邊件」取樣過疏)。
> 依據:`tools/mesh_gen/compare_award_mesh.py`(可重跑)。信心:高(對藝術家真值量化比對)。相關:S3、S4。

## 標的與方法

`robot_parts.psd` 5 圖層 ⇄ Award spine slot `機器人拆件/<圖層名>`(見 `s4-psd-to-spine-real.md`)。
其中 **光暈 / 左手 / 身體** 在 Award 是 **mesh**(右手/頭是 region)。流程:

`psd_slice` 切件 PNG → `generate_mesh_v2(mode=auto)` 生成 mesh → 三條靜態 AC:
1. **覆蓋率 IoU**:生成 mesh 對「PSD 切件 alpha」的覆蓋率,對比藝術家真實 mesh 對「Award atlas
   region alpha」的覆蓋率(margin 0.03)。兩者皆自相對覆蓋率 → orientation/scale 不變、可比。
2. **頂點預算**:生成 nv ≤ 64。
3. **靜態良構**:生成 mesh 的 uv 佈局 0 自交 / 0 退化(`deform_eval.check`)。

## ⚠️ 誠實邊界:此標的**無法驗耐變形**

Award 的這 3 個 mesh 在**全部 12 支動畫皆無 deform timeline**(`compare_award_mesh.assert_no_deform`
確認),靠骨骼剛體驅動。故「真實位移場轉移」閘對此標的 **N/A**。耐變形已在 main_draw 4 mesh 對
藝術家真值驗過(見 `s3-four-mesh-generalization.md`),此處只補「靜態覆蓋率/預算/良構」對真實標的。

## 結果(2026-07-08)

| slot | 生成 mode | 生成 nv | 生成 IoU | 藝術家基準 | 真實 nv/hull | pass |
|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | delaunay(eps=0.002) | 64 | 0.9796 | 0.9795 | 78 / 78(全hull) | ✅ |
| 機器人拆件/左手 | delaunay(eps=0.008) | 59 | 0.9642 | 0.9681 | 80 / 42 | ✅ |
| 機器人拆件/身體 | delaunay(eps=0.008) | 60 | 0.966 | 0.976 | 98 / 40 | ✅ |

三件皆 aspect < 1.2 → auto 正確回退 delaunay(非 strip)。

## 關鍵發現:固定 epsilon 不通用 → 改「預算內自適應加密」

- **初測光暈 fail**:eps=0.008 只描出 16 hull 點,IoU 0.933 < 基準 0.980。原因:光暈是 **halo(柔邊、
  邊界主導)**,藝術家用 **78 個全 hull 點**密描外周;delaunay 固定粗 epsilon 描不出複雜邊界。
- **邊界複雜度因件而異**:實心件(手/身體,hull 40~42 + 內部點)0.008 就夠;柔邊/環狀件需更密。
  單一 epsilon 不通用。
- **修法**:`generate_mesh_v2.gen_delaunay_adaptive()` 沿 epsilon 階梯(0.008→0.0012)由粗到細,
  取「nv ≤ budget(64) 內 IoU 最高」者。光暈自動選 eps=0.002(nv=64、IoU 0.9796 ≥ 基準);
  手/身體維持 0.008(本就最佳)。**對 main_draw 4 mesh 無影響**(全走 strip 分支;已回歸驗證)。
- 副產原則(呼應 strip「IoU 由 rows 決定」):**delaunay 的 IoU 由 hull 邊界取樣密度(epsilon)決定**;
  兩種拓樸的覆蓋率槓桿都是「邊界取樣密度」,內部點只影響變形品質不影響覆蓋率。

## 可重跑指令

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
python3 tools/mesh_gen/compare_award_mesh.py   # exit 0 = 三件全 overall_pass
```
