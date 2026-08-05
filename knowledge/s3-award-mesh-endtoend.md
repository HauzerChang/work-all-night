# S3 端到端驗收:機器人件 → generate_mesh_v2 → 對照 Award 真實 mesh(有真值)

- **結論**:對真實生產 spine（`Award`）的 3 個 weighted mesh 件（光暈 / 左手 / 身體），
  以其 atlas 切件 alpha 跑 `generate_mesh_v2`，**3/3 端到端 overall_pass**：覆蓋 IoU 不輸藝術家、
  結構閘全過（0 孤兒 / 0 退化 / 預算內），且生成頂點數更精簡（60/48/61 vs 藝術家 78/80/98）。
- **信心**:高（對真實生產標的、藝術家 mesh 為真值交叉比對、評估器先過自一致性）。
- **階段**:第 2 階段 / S3（里程碑:S3 從「main_draw 自家 mesh」推廣到「另一支生產 spine 的真值對照」）。
- 產出:`tools/mesh_gen/compare_award_mesh.py`（比對閘）、`knowledge/figures/s3-award-robot-mesh-compare.png`（GEN vs ARTIST 疊圖）。

## 對照結果（`python3 tools/mesh_gen/compare_award_mesh.py`,overall_pass=true）

| 件 | 藝術家(真值) | 生成(v2 auto) | 生成 IoU | 藝術家自我 IoU | 覆蓋 | 結構 |
|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | 78v/76t/hull78, weighted | 60v/95t/hull21, delaunay-v1-adaptive | 0.963 | 0.980 | ✅ | ✅ |
| 機器人拆件/左手 | 80v/116t/hull42, weighted | 48v/76t/hull18 | 0.960 | 0.968 | ✅ | ✅ |
| 機器人拆件/身體 | 98v/154t/hull40, weighted | 61v/98t/hull21 | 0.968 | 0.976 | ✅ | ✅ |

判準（L2 客觀項）：`alignment_ok`(藝術家自我 IoU≥0.80，證 UV 慣例/derotate 對齊自洽) ∧
`coverage_pass`(生成 IoU ≥ 藝術家自我 IoU − 0.03) ∧ `structure_pass`(格式/退化/孤兒/預算全過)。

## 揭示 / 確認的事實

1. **這 3 件在 Award 皆為 weighted mesh 且無 deform timeline**（靠骨骼/權重變形，非逐頂點 deform）。
   故對照用「靜態拓樸/覆蓋率對藝術家真值」，**不套 deform 轉移閘**（後者需 deform timeline，見 `s3-deform-evaluator.md`）。
   → S3 生成器產 *unweighted* mesh，覆蓋/拓樸可比；權重綁定（BBW）是後續 S3 未完部分。
2. **UV 慣例 + atlas derotate=CW 在 weighted+rotated 件上再獲獨立驗證**:光暈/身體在 atlas 為 `rotate:true`
   （縮小 ~0.70 打包），藝術家自我 IoU 仍 0.976~0.980 → `atlas_crop` 的 CW 修正（`s4-psd-to-spine-real.md`）
   對 mesh 件同樣正確；mesh uvs 為 0..1-over-region 慣例對 rotated 件也成立。
3. **端到端素材閉環**:此比對用的 alpha 來自 Award atlas 切件，而前一里程碑已證「PSD 切件 ↔ atlas 切件
   alpha-IoU 0.92~0.99 同素材」→ 「PSD件 → 素材 → S3 mesh → 對真值」整條可信。

## 修掉的真實 bug + 新增能力（本次）

### ① v1 孤兒頂點 bug（correctness，通用）
`generate_mesh.filter_triangles` 會丟掉「重心落在 mask 外」的三角；對凹形/軟邊件，某內部頂點的
**所有**相鄰三角都被丟 → 該頂點變孤兒（AC2c fail，Spine 格式非法）。光暈即中招。
**修**:新增 `prune_orphans()`——過濾後移除 idx≥n_hull 的未引用頂點並重編索引；hull（邊界環）一律保留、
順序/數量不變。main_draw 走 strip 不受影響；robot 左手/身體（走 v1）驗證無回歸。

### ② 自我驗證式邊界加密 `generate_adaptive()`（收斂能力）
固定 `epsilon_frac=0.008`（佔周長比例）對**大軟邊 blob**（光暈：軟羽化、周長長）取樣過疏
→ 只 14 hull 點、IoU 0.929。epsilon 掃描顯示覆蓋隨邊界密度**單調上升**（見下）。
不引 per-shape 魔數,改用專案本身的「generate→evaluate→refine」迴圈:
從粗 epsilon 起→量覆蓋 IoU→未達標且預算未滿就縮小 epsilon 加密→**硬邊件早停(頂點少)、
軟邊 blob 自動加密到達標或撞預算**。接進 v2 非-strip fallback（模式標 `delaunay-v1-adaptive`）。

epsilon 掃描（光暈,藝術家自我 IoU=0.980,門檻 base−0.03=0.9495）:

| epsilon_frac | 頂點 | hull | 覆蓋 IoU |
|---|---|---|---|
| 0.008 | 53 | 14 | 0.929 |
| 0.005 | 60 | 21 | **0.963**（自我驗證迴圈早停於此:達標且 ≤64 預算） |
| 0.003 | 68 | 32 | 0.978（超 64 預算） |
| 0.001 | 92 | 58 | 0.992 |

**教訓**:固定幾何參數對「尺度/邊界柔度差異大」的件不通用;把評估器接進生成器做自我驗證迴圈,
讓每件自動收斂到「達標且最精簡」,才是自主化的正解（呼應 RULES「每能力必配評估器」）。

## 殘差 / 已知限制

- 光暈生成 IoU 0.963 < 藝術家 0.980:藝術家用 78 個純邊界點（hull=nUV，無內部）緊貼羽化邊的
  細絲/凹槽;生成在深凹處以較直的邊裁過（見疊圖）。在 margin 內通過,若要更貼可降 min_eps/提預算。
- 生成 mesh 為 **unweighted**;真實件是 weighted。**權重綁定（BBW）仍是 S3 未完的一塊**
  （拓樸/覆蓋已達標，綁骨是下一步）。

## 可重現

```
python3 tools/mesh_gen/compare_award_mesh.py            # 3/3 overall_pass
# 單件除錯:掃 epsilon 看覆蓋單調性 / 看 adaptive 早停點
```
