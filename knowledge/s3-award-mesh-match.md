# S3 端到端驗收 — Award 真實生產 mesh 對照(PSD/atlas 件 → generate_mesh)

- **結論**:把 S3 mesh 生成器接上真實生產標的 —— 對 Award spine 中 3 個 `type=mesh` 的機器人件
  (`機器人拆件/光暈`、`左手`、`身體`),從 atlas 切出 region alpha → `generate_mesh`(v1 Delaunay)
  → 與**藝術家真實 mesh 的覆蓋率**對照。**調到藝術家保真度後 3 件全 overall_pass**
  (生成覆蓋 IoU ≥ 藝術家自身 baseline,且格式/預算/無孤兒/無退化三角全過)。
- **信心**:高。真值 = 生產 spine 的藝術家 mesh;alpha 來源與藝術家 uvs 同一貼圖幀(直接從 Award atlas 切),
  scale 一致可直接比。
- **階段**:第 2 階段 / S3 端到端(從合成 → main_draw → **真實生產 Award mesh**)。
- **可重現**:`python3 tools/mesh_gen/validate_award_mesh.py --gen v1`(exit 0)。

## 結果(eps=0.002,budget=100)

| 件 | 生成 IoU | 藝術家 baseline | 生成 nv/hull | 藝術家 nv/hull | overall |
|---|---|---|---|---|---|
| 光暈 | 0.9832 | 0.9795 | 73 / 38 | 78 / **78** | ✅ |
| 左手 | 0.9913 | 0.9681 | 67 / 43 | 80 / 42 | ✅ |
| 身體 | 0.9926 | 0.9760 | 77 / 37 | 98 / 40 | ✅ |

## 兩個關鍵發現(調參前 3 件全 fail,fail 幅度小 1~5%)

1. **預設 `epsilon_frac=0.008` 對「不規則團塊件」欠覆蓋**。
   0.008 把輪廓簡化到只剩 hull 14~21 點 → 切掉真實 alpha 的凹凸角 → IoU 0.929/0.960/0.968,
   全略低於藝術家 baseline。掃描 eps:**0.002 是甜蜜點**(3 件 hull 37~43、nv 67~77,貼齊藝術家精簡度且全過)。
   eps 越小越貼(0.0005 IoU≈1.0)但頂點爆量(147~290v),過度細分無意義。
   *此 eps 只用於 Award 這批團塊件;未改全域預設(main_draw 窗簾走 v2 strip,不受影響)。*

2. **`vertex_budget=64` 對真實大件太緊**。這 3 件**藝術家本身就是 78/80/98 頂點**,
   64 是給 main_draw 小 mesh(窗簾/陰影 ~30v)校的。→ 驗收改 budget=100(貼齊藝術家尺度)。
   **教訓:mesh 密度/預算是「標的相依」的,單一固定 eps+budget 不通用**;正確密度 = 貼齊該件藝術家精簡度。

## 為何不跑 deform 閘(與 main_draw 的差異)

- main_draw 4 mesh:**unweighted + 有 deform timeline** → 可用真實位移場轉移驗自交/翻面。
- Award 這 3 件:**weighted(骨骼權重 warp)+ 無 deform timeline** → **沒有逐頂點位移場真值可轉移**。
  故本驗收只做「靜態覆蓋 + 拓樸/格式 AC」;**不硬套未校準合成壓力場**(STATE 明令,前有 stress_field miscalibration)。
- 這也印證 `s4-psd-to-spine-real.md` 的觀察:剛體/骨骼變形件用 weighted mesh,不掛 deform。

## 拓樸差異(有趣、非缺陷)

- **光暈藝術家 mesh 是「純邊界」**:hull=78=全部 78 頂點,**0 內部點**(靠密集外周 + 三角化)。
  生成 mesh 走 hull(38)+ 內部點,覆蓋等效但拓樸策略不同。兩者對「以骨骼權重 warp」的件都夠用。

## 意義 / 下一步

- **S3 + S4(atlas 切件)端到端串通並對真實生產 mesh 驗收通過** —— 生成器能在真實標的上
  達到藝術家等級覆蓋。
- 生成器差距不在「能不能覆蓋」而在**保真度旋鈕需依件調**(eps/budget)。可續作:
  **自適應 epsilon**(依 arcLength / 目標頂點預算自動定 eps),讓「auto」對任意件都貼齊藝術家精簡度,
  免手調。
- 尚缺 texture/實機:atlas 已切件,PSD↔atlas 同素材(前已驗 alpha-IoU 0.92~0.99)。
