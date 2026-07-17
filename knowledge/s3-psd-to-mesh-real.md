# S3 端到端「件 → mesh」對真實生產 mesh 驗收(Award 機器人 3 mesh 件)

- **結論**:把 S4 切件(PSD 或 atlas 兩來源)餵進 S3 `generate_mesh_v2`,對 Award 生產 spine 的
  3 個 **mesh 件(光暈 / 身體 / 左手)** 做靜態幾何對照,**6 組(3 件 × 2 來源)全 PASS**:
  生成 mesh 覆蓋率 IoU **0.992~0.995**,全部 **≥ 藝術家 mesh 覆蓋率基準**(0.948~0.980),
  頂點數 73~95 與藝術家 78~98 同級。端到端「件 → S3 mesh」對真實生產標的成立。
- **信心**:高。藝術家 mesh 真值與生成 mesh **在同一 frame** 比覆蓋率(uvs 為 region-local 0..1,
  ×crop size 即對齊),閘可自一致驗;附視覺線框對照 `figures/psd2mesh_robot_wireframe.png`。
- **階段**:第 2 階段 / S3 × S4 串接(里程碑:S3 首次對「有真值的真實生產 mesh」驗收)。

## 關鍵發現

1. **blobby(Delaunay-v1)件的覆蓋率 IoU 由 hull 密度(`epsilon_frac`)決定** —— 與 v2 strip
   「IoU 由 rows 決定」完全對應。固定粗 `epsilon=0.008` 對大件(光暈 atlas 496px)hull 只有 14 點,
   IoU 僅 **0.93 < 藝術家 0.98**(唯一初次 fail)。
2. **修法 = budget-targeted auto-epsilon**:`generate_mesh.generate(target_vertices=N)` 沿
   `_EPS_LADDER` 由粗到細,取「總頂點 ≤ N 的最細 hull」(頂點數隨 epsilon 單調遞增,找到即停)。
   以**生產級頂點預算**(這 3 件藝術家用 78~98)為目標 → 同等頂點數下達到/超越藝術家覆蓋率
   (6 件全 IoU>0.99)。已 thread 進 `generate_mesh_v2.generate(target_vertices=)`(僅對 Delaunay
   fallback 生效;strip 密度仍由 rows/cols 決定,**main_draw 4 mesh 不受影響、重驗仍過**)。
3. **固定 budget=64 太緊**:藝術家這 3 件本身 78~98 頂點 > 64。生產級件的頂點預算應以目標/藝術家
   為準,不是武斷小值。閘預設 `budget=96`。

## ⚠️ 誠實邊界(未做到的)

- **這 3 件在 Award 無 deform timeline** —— 靠**骨骼 + 頂點權重(weighted mesh)**變形,非逐頂點
  deform。故 `real-deform-field` 閘(S3 主力變形閘)**不適用**,本次只驗**靜態覆蓋 + 拓樸/預算**。
- **S3 目前只產 unweighted mesh** → 對「骨骼驅動的 weighted 件」還不能做 like-for-like 取代;
  **缺的子能力 = BBW/骨骼權重自動綁定**(PLAN 中 S3 的 mesh 生成尚未含權重)。這是下一個 S3 缺口。

## uvs / 對齊備忘(校正先前 handoff note)

- Award mesh 的 `uvs` **已是 region-local 0..1**(非全頁 atlas UV);×region crop size 即落在切件上
  (實測 3 件藝術家 mesh vs atlas crop alpha IoU 0.968~0.980)。先前 handoff「需先轉 region 局部」
  的顧慮在此資產不成立 —— Spine JSON 匯出已把 UV 正規化到 region。
- 兩來源 alpha:atlas 切件(0.70 縮小打包、光暈/身體 rotate=true,CW derotate)與 PSD 切件(原始解析度)
  為**同素材**;藝術家 baseline 在兩 frame 略不同(縮放/羽化),故各自 frame 內比對。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts   # 先切 PSD 件(psd 來源用)
python3 tools/mesh_gen/validate_psd_to_mesh.py --source both                     # 6 組全 PASS
```

## 下一步候選

- **S3 加 BBW/骨骼權重**(最大缺口:讓生成 mesh 能對接骨骼驅動的生產件)。需骨架 + bind pose。
- 把「件 → Spine attachment(mesh)」寫進 SkelToJson 組裝工具:命名 `<PSD名>/<圖層名>`、
  +2px padding、mesh 用 auto-epsilon@budget、region 用旋轉 —— 端到端產可用 Spine JSON。
