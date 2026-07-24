# S3 端到端:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把 `robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手)用 `psd_slice` 切出 →
  S3 生成器產 mesh → 對照 **Award 真實生產 mesh**(同件、weighted)。**auto-refine epsilon 後
  3 件靜態輪廓 IoU 全達/超藝術家基準,且頂點數比藝術家精簡(43/60/70 vs 78/98/80)。**
  端到端「PSD→件→mesh」對真實生產標的驗收通過(靜態保真 + 頂點經濟)。
- **信心**:高(對真實生產 mesh 交叉比對;正/負對照;auto-refine 收斂可重現)。
- **階段**:第 2 階段 / S3+S4 串接(里程碑:合成/main_draw → 真實 big win 標的)。

## 量化結果(`tools/mesh_gen/compare_to_award.py --refine`)

| 件 | 生成 verts/hull | 生成 IoU | 藝術家 verts/hull | 藝術家覆蓋 IoU | eps | 過? |
|---|---|---|---|---|---|---|
| 光暈 | 43 / 24 | 0.958 | 78 / **78** | 0.949 | 0.006 | ✅ |
| 身體 | 60 / 20 | 0.966 | 98 / 40 | 0.948 | 0.008 | ✅ |
| 左手 | 70 / 30 | 0.980 | 80 / 42 | 0.977 | 0.004 | ✅ |

> 「藝術家覆蓋 IoU」= 把 Award mesh 的 region-local uvs 渲染到相同切件 alpha 框量 IoU
> (同一 alpha>8 門檻)。藝術家自身也 <1(0.948~0.977):真實 mesh **刻意不吃到羽化邊**,
> 故「生成 ≥ 藝術家」= 輪廓至少一樣完整,是合理的地板基準。

## 關鍵發現

1. **固定預設 eps=0.008 對細緻生產件太粗**:v2 auto 對這 3 件因長寬比/非 row-convex 回退
   Delaunay-v1,預設 eps=0.008 只給 hull 16~20 → 光暈/左手 IoU 差藝術家 1.3~1.6% 而 fail。
   **輪廓保真由 Douglas-Peucker `epsilon_frac` 主導**(掃描:eps 0.008→0.001 使 IoU
   0.933→0.992,hull 16→62)。
2. **auto-refine 由粗到細下修 eps 到藝術家基準即收斂**,且頂點仍比藝術家少 12~45%
   → 生成器能以更精簡拓樸達到同等靜態輪廓保真。
3. **AC3 的 64 頂點預算是用簡單 curtain/shadow(≤30v)校準的,對細緻件偏緊**:
   藝術家這幾件用 78~98v;要吃到細節輪廓需放寬到 ~96。預算應**隨件輪廓複雜度縮放**,
   非一刀切。`compare_to_award.py` 用 `--vert-cap 96`。
4. **拓樸策略差異(光暈)**:藝術家光暈 mesh = **78v 全在 hull、0 內部點**(純外環扇形,
   76 三角)—— 柔性徑向光暈靠骨骼 warp,只需外環。我方生成器對它加了內部格點(非必要)。
   對「純 warp、無內部結構」的件,純外環拓樸更貼合美術意圖(未來可加 `ring` 模式)。

## ⚠️ 限制(誠實紀錄)

- Award 這 5 件是 **weighted mesh 且 Award 中無 deform timeline**(靠骨骼權重變形,非逐頂點
  deform)→ 真實位移場轉移閘 `deform_eval.transfer_deform_check` **不適用**,本次只驗
  **靜態輪廓 + 頂點經濟 + 拓樸**。變形穩健結論仍以 main_draw 4 個 unweighted mesh 的
  v2 strip(見 `s3-four-mesh-generalization.md`)為準。
- 生成 mesh 為 unweighted;要成為 Award 那樣的 weighted 件還需 S3 的 BBW 權重階段(未做)。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
python3 tools/mesh_gen/compare_to_award.py            # 固定 eps=0.008 → 光暈/左手 fail(基準太粗)
python3 tools/mesh_gen/compare_to_award.py --refine   # auto-refine → 3 件全過(exit 0)
```

視覺對照(紅=藝術家 / 綠=生成):`knowledge/figures/s3-award-mesh-compare.png`。

## 下一步候選

- 把 auto-refine epsilon(達 IoU 目標的最粗輪廓)固化進 `generate_mesh_v2` 的一個模式,
  並讓頂點預算隨件尺寸/輪廓長度縮放(取代固定 64)。
- 為「純 warp」件加 `ring`(純外環)拓樸模式,對照光暈藝術家策略。
- S3 BBW 權重階段:把生成的 unweighted mesh + 骨架 → weighted,才能對齊 Award 生產件全貌。
