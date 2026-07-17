# S3 端到端驗收:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:S3 `generate_mesh_v2` 對 3 個**真實生產 mesh 件**(`robot_parts.psd` 的光暈/身體/左手,
  在 spine `Award` 裡是 mesh)端到端跑通並**達到藝術家覆蓋率**:生成 IoU 0.933/0.966/0.964 vs
  藝術家自身 self-IoU 0.949/0.948/0.977(margin 0.02 內全過),且**頂點數更精簡**
  (生成 35/60/59 vs 藝術家 78/98/80)。這是 S3 首次對「真實生產標的、有藝術家 mesh 真值」的驗收。
- **信心**:高(對真實生產 PSD + 真實 spine mesh 交叉;座標慣例經 self-IoU sanity check 確認)。
- **階段**:第 2 階段 / S3 × S4 端到端(STATE.md 最高優先候選 #1,里程碑)。

## 驗收方式(`tools/mesh_gen/validate_against_award.py`)

1. 用 `psd_slice` 從 `robot_parts.psd` 切出**乾淨全解析度 alpha**(真值鏈:PSD 切件 == Award 生產貼圖
   素材,alpha-IoU 0.92~0.99,見 `s4-psd-to-spine-real.md`)。
2. 對切件 alpha 跑 `generate_mesh_v2(mode="auto")`。
3. 讀 Award 藝術家 mesh(region-local normalized uvs),與生成 mesh **各自對切件 alpha 算覆蓋 IoU**。
4. 判準:①座標 sanity(藝術家 self-IoU ≥ 0.80)②生成 IoU ≥ 藝術家 self-IoU − 0.02 ③格式/無退化/無孤兒。

```
python3 tools/mesh_gen/validate_against_award.py   # all_pass=true(3/3)
```

## 量化結果

| 件 | 旋轉 | 生成 mode | 生成 v/hull/tris | 生成 IoU | 藝術家 v/hull/tris | 藝術家 self-IoU |
|---|---|---|---|---|---|---|
| 光暈 | rotate:true | delaunay-v1 | 35/16/49 | **0.933** | 78/**78**/76 | 0.949 |
| 身體 | rotate:true | delaunay-v1 | 60/20/97 | **0.966** | 98/40/154 | 0.948 |
| 左手 | rotate:false | delaunay-v1 | 59/19/97 | **0.964** | 80/42/116 | 0.977 |

視覺對照:`knowledge/figures/award_robot_generated_vs_artist.png`(左綠=生成、右黃=藝術家)。

## 關鍵發現

1. **auto 模式對 blob 件正確選 v1(Delaunay)**:3 件長寬比 <1.2 或非 row-convex → 不走 strip。
   印證分工:**v2 strip = 高瘦/會拉伸的窗簾;v1 Delaunay = 有機 blob 件**(光暈/身體/手)。同一 `auto` 入口自動分流。
2. **座標慣例對『旋轉區域』也成立**:光暈/身體在 atlas 是 `rotate:true`,但 Spine JSON 的 mesh `uvs`
   存於**未旋轉 logical 區域**內 normalize(rotate 只影響 atlas 打包)。以 `uvs*W,uvs*H` 直接映射切件
   即得藝術家 self-IoU 0.95/0.95 → 慣例確認(這正是先前 atlas_crop derotate bug 的同類陷阱,此處以 self-IoU 先驗)。
3. **藝術家 光暈 是純 hull mesh(78/78 全在邊界、無內部點)**:以 radial fan 三角化。視覺上藝術家沿
   **細長指向突起(右上)**用 hull 點精描,我的 Delaunay 對該細突起取樣不足 → 光暈 IoU 最低(0.933)。
   啟示:**thin protrusion 的覆蓋率靠邊界取樣密度**;若要再逼近,對高曲率邊界加點(v1 目前用固定 Canny 密度)。
4. **S3 用更少頂點達同等覆蓋**(平均約藝術家的 0.6×)→ 對 runtime 友善;但藝術家多頂點是為**權重變形自由度**,
   非為覆蓋率 —— 頂點預算的「對」要看變形需求,不能只看靜態 IoU(見下方邊界)。

## 誠實的能力邊界(重要)

- 這 3 件在 Award **無 deform timeline**(靠骨骼權重變形,非逐頂點 deform)→ 本閘**只驗靜態幾何/拓樸**,
  **未驗 blob 件的變形穩健度**(此處無 deform 場可轉移;RULES 禁用未校準 stress_field)。
- S3 的**變形穩健**已由 `validate_against_real`(main_draw 4 窗簾 mesh,有真實 deform)驗過;
  blob 件的變形穩健若要驗,需一支「blob + deform timeline」的真實件或校準過的權重形變模型。
- 因此本結論的正確讀法:**「S3 對真實生產件的靜態拓樸/覆蓋達藝術家水準」**,而非「變形也達標」。

## 下一步

- (2) 把「件 → Spine attachment」組裝固化成 SkelToJson:用此處驗過的生成 mesh + `機器人拆件/<圖層名>`
  命名慣例 + size+2px padding + atlas 0.70 縮放,端到端產一份可載入的 Spine JSON(對 blob 件用 v1、strip 件用 v2)。
- 若要提升 blob 件 thin-protrusion 覆蓋:v1 加「高曲率邊界自適應加點」再對光暈重驗。
