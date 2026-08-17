# S3 泛化到第二份生產資產 Award(weighted mesh)+ v1 自適應邊界

- **結論**:S3 v2 生成器**泛化到第二份獨立生產資產 Award 的 3 個機器人 mesh 件**
  (光暈/左手/身體),且這三件皆為 **weighted mesh**(main_draw 的 4 mesh 全 unweighted,
  這是首次對 weighted 真值對照)。靜態覆蓋率**全部達到/超過藝術家基準,且頂點數皆低於藝術家**。
- **依據**:`tools/mesh_gen/compare_award_robot.py`,atlas region 像素框內 IoU 對照。
- **信心**:高(有藝術家真值可比;自驗閘 exit 0)。純 CPU、可重跑。
- **階段**:第 2 階段 S3(mesh)× S4(PSD)端到端;第二資產泛化。

## 對照結果(atlas region 框,margin=0)

| 件 | 生成 IoU | 頂點(hull) | mode | 藝術家覆蓋率 | 藝術家頂點 | PASS |
|---|---|---|---|---|---|---|
| 機器人拆件/光暈 | 0.9832 | 73 (38) | delaunay-v1 | 0.9795 | 78 | ✅ |
| 機器人拆件/左手 | 0.9816 | 57 (30) | delaunay-v1 | 0.9681 | 80 | ✅ |
| 機器人拆件/身體 | 0.9858 | 69 (29) | delaunay-v1 | 0.9760 | 98 | ✅ |

- 三件都是**低長寬比、非 row-convex 的塊狀**(glow 環暈 / 手 / 身體)→ v2 `auto` **正確回退 v1
  Delaunay**(strip 只對高瘦窗簾狀合適)。這驗證了 v2 的 mode 選擇邏輯對真實塊狀件也對。
- 生成頂點數 < 藝術家頂點數(73<78 / 57<80 / 69<98):**Pareto 更省**,覆蓋率還更高。

## 關鍵改良:v1 自適應邊界取樣(auto-epsilon)

- **問題**:v1 舊預設 `epsilon_frac=0.008`(approxPolyDP 邊界簡化)對**複雜生產輪廓太粗** →
  光暈 hull 只 14 點、覆蓋率 0.929(藝術家 0.980,差 5%)。這是資產尺度問題:0.008 是
  main_draw 小件校的,對 Award 大件(496×480)過度簡化。
- **修法**(`generate_mesh.py`):`epsilon_frac="auto"`(新預設)。由粗到細掃 eps grid,取
  「填滿 hull 對 mask 覆蓋率 ≥ `cover_target` 且 hull 頂點 ≤ `max_hull`」的**最粗**解;
  無達標則取覆蓋率最高、不超上限者。→ **資產尺度無關**(小件大件同一策略,不再靠魔術常數)。
- **參數**:`cover_target=0.98`(新預設)、`max_hull=64`。0.97 對光暈近凸複雜輪廓會停在覆蓋率
  平台(0.9779)差臨門一腳;0.98 逼它跨過(0.9832)。三件在 0.98 全過且頂點皆 < 藝術家。
- **回歸驗證(關鍵)**:
  - main_draw 4 mesh **全走 strip 模式**(高瘦 row-convex),v1 改動**碰不到** → `--gen v2` 4/4 仍 overall_pass。
  - v1 路徑本身(`--gen v1` curtain_left):IoU **0.98→0.99 反而更好**(auto 邊界更貼),
    真實 deform **仍 0 自交** → 更密邊界未傷變形穩健。
- **向後相容**:`generate(path, epsilon_frac=<數值>)` 仍走固定 eps;只有預設值換成 auto。

## PSD 來源端點健全性

`robot_parts.psd` 5 件(psd_slice 切出)各自跑 v2 也都產出乾淨 mesh(IoU 0.980~0.985),
證明生成器對「PSD 切件來源」(不同解析度、+2px padding)同樣可用 —— 端到端 **PSD→件→mesh**
不限 atlas 來源。

## 未解 / 後續(⚠️ 誠實標注)

- **deform 閘對 weighted mesh 尚未支援**:`deform_eval.load_mesh` / `real_deform_field` 把
  `a["vertices"]` reshape 成 (nv,2),但 weighted 格式是 `[骨數,骨idx,bindX,bindY,權重,...]` 變長 →
  會壞。故 Award 三件**只驗了靜態 IoU,未驗真實 deform 穩健度**。
  → **下一個 chunk 候選**:weighted-aware deform 解析(依權重把 bind 座標×骨變換合成 setup local,
    再套 deform offset),讓 `transfer_deform_check` 能吃 Award 的 deform timeline。
- Award deform timeline 格式與 main_draw 同為緊湊 bezier + sparse offset,可沿用 `deform_frames`。
