# S3 端到端驗收 — PSD 件 → 生成 mesh 對照 Award『真實生產 mesh』

- **結論**:第一次拿**真實藝術家手做 mesh** 當 ground truth 驗 S3。管線 `robot_parts.psd → psd_slice
  切件 alpha → generate_mesh_v2(auto) → 對照 Award.json 對應 slot 的真實 mesh`,3 件 mesh
  (光暈/身體/左手)**全部通過**:覆蓋率 ≥ 藝術家 −2%、外周輪廓 IoU 0.91–0.96、頂點數比藝術家更精簡、
  校準過的極端 deform 下 0 自交 / 0 翻面。
- **信心**:高(對真實生產 mesh 交叉比對 + 對齊假設實測驗證 + deform 閘經 scale 校準)。
- **階段**:第 2 階段 / S3 端到端(里程碑:合成/自身基準 → **真實外部 ground truth**)。
- **工具**:`tools/mesh_gen/compare_to_award.py`(可重跑);圖 `knowledge/figures/s3-vs-award-hull-overlay.png`。

## 對照的三件 mesh(Award 中為 mesh 型;右手/頭為 region 故排除)

| slot | 藝術家 mesh | PSD 件尺寸 |
|---|---|---|
| 機器人拆件/光暈 | 78v / 76t / hull78(純外周) | 706×683 |
| 機器人拆件/身體 | 98v / 154t / hull40 | 379×425 |
| 機器人拆件/左手 | 80v / 116t / hull42 | 257×215 |

(Award mesh 皆為 **weighted**:vertices 攤平長度 ≠ uvs;但 `uvs`/`triangles`/`hull` 給的是拓樸 ground truth。)

## ★ 對齊依據(先實測再比較,避免自欺)

Spine 3.8 mesh 的 `uvs` 是**region 局部正規化座標**(件的正立邏輯座標),不是 atlas 頁 UV。
故直接 `(u*W, v*H)` 即映到 PSD 切件像素空間。**實測**:光暈藝術家 mesh 填三角 vs PSD alpha,
`flip=False` IoU=0.943、`flip=True` 僅 0.426 → 對齊成立、不需 v-flip。這一步是整個比較的地基。

## 量化結果(auto 模式 = 生產預設)

| slot | 生成拓樸 | 頂點(gen/藝) | 覆蓋率 gen/藝 | Δ覆蓋 | 外周IoU | deform(校準後) |
|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 35/78 | 0.933 / 0.949 | −0.016 | 0.910 | si0 / fl0 ✅ |
| 身體 | delaunay-v1 | 60/98 | 0.966 / 0.948 | **+0.018** | 0.932 | si0 / fl0 ✅ |
| 左手 | delaunay-v1 | 59/80 | 0.964 / 0.977 | −0.013 | 0.957 | si0 / fl0 ✅ |

- **覆蓋率**:3 件全在藝術家 −2% 內,身體甚至更高 → S3 對輪廓的覆蓋 ≈ 藝術家。
- **外周輪廓 IoU 0.91–0.96**:生成的外周多邊形與藝術家外周幾何吻合(見疊圖:紅=gen 貼著綠=藝術家)。
- **頂點預算**:3 件都用**比藝術家更少**的頂點(35/60/59 < 78/98/80)→ 更精簡。

## 為何 auto 選 delaunay-v1(不是 strip)—— 拓樸自動選對

光暈/身體/左手長寬比 0.97 / 1.12 / 0.84,**全 < 1.2 strip 門檻** → auto 回退 v1 Delaunay。
forced-strip 對這些方塊/團狀件覆蓋率掉到 0.878(< 藝術家 0.949),外周 IoU 也降 →
**證實 strip 只適「高瘦、row-convex」件(窗簾);v1 才適團狀件**,aspect 門檻選對了拓樸。

## ⚠️ 評估器校準(第 4 次 miscalibration,務必記取)

窗簾真實位移場是**絕對像素**(max 313px)。直接轉移到不同大小的件 → 相對形變量嚴重不一致:
313px 對 706px 光暈 = 44%,對 257px 左手 = >100%。**未正規化時左手 v1 area_ratio 衝到 1.58 →
假性 si10/fl3 FAIL**。依 `part_diag / curtain_diag` 縮放位移場,讓每件承受與窗簾閘相同的
**相對**極端拉伸(area_ratio 回到校準的 1.12–1.24)→ 左手 v1 **轉為 si0/fl0 PASS**。

**教訓(累計:stress_field → composite 白底 → atlas derotate 方向 → 本次跨件位移場尺度)**:
任何跨資產轉移的量化閘,先確認**量綱/尺度對齊**再下判定;錯把「小件被超量拉伸」讀成「拓樸脆弱」。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd --out /tmp/robot_slice
python3 tools/mesh_gen/compare_to_award.py            # auto 整體 PASS ✅,詳表 /tmp/compare_award.json
```

## 意義 / 下一步

- S3 首次對**真實生產 ground truth** 收斂:覆蓋、輪廓、精簡度、耐變形四項全過 → S3 生成器可信度再升一級。
- 端到端 `PSD → 件 → mesh` 已通到「對真實標的驗收」。**下一哩**:把「件 → Spine attachment」
  (命名 `PSD名/圖層名`、size+2px、mesh/region 依 aspect 或美術標記分配、uvs/vertices/hull 寫入)
  固化成 **SkelToJson 組裝工具**,產出可直接載入的 Spine JSON(候選 #2)。
- 註:Award mesh 為 weighted(骨骼權重驅動、無 deform timeline);本測比的是**平面拓樸/覆蓋**,
  權重生成(BBW)屬 S3 後段/S5 範疇,尚未觸及。
