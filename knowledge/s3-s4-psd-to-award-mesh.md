# S3+S4 端到端:PSD 件 → 生成 mesh → 對照 Award 真實 mesh

- **結論**:把 S4(切圖)與 S3(mesh 生成)首次串成端到端,並**對真實生產標的(Award spine
  的藝術家 mesh)做 ground-truth 對照**。3 個在 Award 為 mesh 的機器人件(光暈 / 身體 / 左手)
  全數通過:生成 mesh 的覆蓋率 IoU 在藝術家基準的 0.02 margin 內(身體甚至反超),且**頂點數
  遠少於藝術家**(35 vs 78、60 vs 98、59 vs 80),拓樸乾淨(重心全在 mask、0 退化、0 孤兒)。
- **信心**:高(對真實藝術家 mesh 交叉比對;藝術家 mesh 對自身件 mask IoU 僅 0.948~0.977,
  證明「對齊藝術家」才是正確標竿,而非「完美貼齊 alpha」)。
- **階段**:第 2 階段 / S3×S4 整合(里程碑:合成/strip → 真實非 strip blob + 端到端)。

## 這次揭示的新事實

1. **首次驗證「非 strip」regime**:先前 S3 只在窗簾/陰影(strip 拓樸)驗過。機器人 3 件都是
   接近正方的 blob(光暈 aspect 0.97、身體 1.12、左手 0.84),`generate_mesh_v2(mode=auto)`
   因 aspect < 1.2 **全部回退 v1 Delaunay**。→ 這是 v1 Delaunay 對真實藝術家 mesh 的第一次驗收
   (先前 v1 只有合成資料 + curtain_left 單件)。
2. **生成器比藝術家更精簡且覆蓋相當**:v1 用 findContours+DP 簡化 hull(16~20 hull 點)+ 內部
   Canny/格點,頂點數約藝術家的一半,覆蓋率 IoU 仍達標。對 runtime 記憶體/計算是優勢。
3. **藝術家 mesh 覆蓋率不是 1.0**(0.948~0.977):mesh 是輪廓的粗近似,不逐 alpha 像素貼齊。
   所以 AC 標竿設「≥ 藝術家 − 0.02」而非武斷 0.95,延續 curtain 課題的校準教訓。
4. **座標系一致性已確認**:Award mesh `uvs` 為 region 正規化 [0,1];PSD 件是該 region 的緊湊
   bbox 裁切(±2px atlas padding)。兩者直接對齊(藝術家 mesh 對件 mask IoU 0.95~0.98)。
   Award mesh 皆 **weighted**,但 `artist_iou` 只用 uvs+triangles(不碰 bind vertices),故適用。

## 逐件結果(`--gen v2`,auto→v1 Delaunay)

| 件 | 件 px | 藝術家 v/tri/hull | 生成 v/tri/hull | 藝術家 IoU | 生成 IoU | 判定 |
|---|---|---|---|---|---|---|
| 光暈 | 706×683 | 78 / 76 / 78(全 hull) | 35 / 49 / 16 | 0.949 | 0.933 | ✅(−0.016) |
| 身體 | 379×425 | 98 / 154 / 40 | 60 / 97 / 20 | 0.948 | 0.966 | ✅(**+0.018**) |
| 左手 | 257×215 | 80 / 116 / 42 | 59 / 97 / 19 | 0.977 | 0.964 | ✅(−0.013) |

視覺對照(藝術家橙 / 生成綠 wireframe 疊件):`knowledge/figures/psd2award_wireframe.png`。
光暈藝術家用「全 hull 扇形」精描毛邊發光輪廓(78 點全在邊界、無內部),生成器用格點覆蓋,
IoU 仍達標;身體/左手兩者拓樸型態相近。

## ⚠️ deform 閘為何 N/A(誠實記錄)

這 3 件在 Award **無 deform timeline**(見 `s4-psd-to-spine-real.md`:靠骨骼/權重變形,
非逐頂點 deform)。沒有真實位移場可轉移;依 RULES「不要用未校準 stress_field」,本次
**只做靜態覆蓋率 + 拓樸乾淨 + 預算對照**(皆有藝術家 ground truth,可信)。
變形穩健度的驗證仍以 main_draw 的 4 個有 deform timeline 的 mesh 為準(見 s3 四件推廣)。

## 可重現

```
python3 tools/mesh_gen/validate_psd_to_award.py --gen v2   # overall_pass=true, exit 0
```
(內部:psd_slice 切件 → generate_mesh_v2 → 對件 alpha 量 IoU,對照 Award.json 藝術家 mesh。)

## 下一步(見 STATE)

- 把「件 → Spine attachment」慣例(`PSD名/圖層名` slot、size+2px、mesh/region 分配、uvs 正規化)
  固化成 SkelToJson 組裝工具:輸入 PSD → 輸出可載入的 Spine JSON(含生成 mesh)。
- 或補 S2 補圖閘 / 骨架閘(純 CPU 樞紐)。
