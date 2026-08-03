# S3 推廣到真實生產 weighted mesh —— Award 機器人拆件(靜態 IoU 軸)

- **結論**:S3 mesh 生成器**能推廣**到真實生產 spine「Award」裡藝術家手做的 3 個 **weighted** mesh
  (`機器人拆件/光暈`、`左手`、`身體`;78~98 頂點)—— 但**必須把頂點預算拉到 ≈ 藝術家水準**。
  用「為簡單 curtain/shadow 校準的預設 ~30v 預算」時,3 件的 IoU 全部**低於藝術家自身 baseline**(fail);
  拉高預算後 3 件全部**達標或超越**藝術家覆蓋率。
- **依據**:`tools/mesh_gen/validate_award_static.py`(真值 = 同一 atlas region alpha + 藝術家 mesh 自身
  IoU baseline)。純 CPU、可重跑。
- **信心**:高(有藝術家真值可比、雙預算對照)。**限制**:僅靜態 IoU 軸;weighted deform 閘尚未做。
- **相關階段**:第 2 階段 S3(mesh)× S4(切圖),端到端「PSD/atlas 件 → 生成 mesh → 對照真實生產 mesh」。

## 量化結果

| 件 | alpha | 藝術家 v / IoU_self | 預設預算 gen | 拉高預算(matched)gen |
|---|---|---|---|---|
| 光暈(soft halo) | 496×480 | 78 / 0.9795 | 54v → 0.929 ❌ | 156v → **0.983 ✅** |
| 左手 | 181×152 | 80 / 0.9681 | 48v → 0.960 ❌ | 163v → **0.991 ✅** |
| 身體 | 267×299 | 98 / 0.976  | 61v → 0.968 ❌ | 157v → **0.993 ✅** |

指令:`python3 tools/mesh_gen/validate_award_static.py --budget matched`(exit 0)/ `--budget default`(exit 1)。

## 頂點預算 sweep(IoU 隨密度單調上升,證明缺口 = 預算而非拓樸)

| 件 | ~50v | ~102v | ~156v | ~185v | 達 baseline 所需 |
|---|---|---|---|---|---|
| 光暈 | 0.929 | 0.966 | 0.983 | 0.988 | ~120v(soft edge 最難) |
| 左手 | 0.960 | 0.982 | 0.991 | 0.993 | ~80v(≈ 藝術家量) |
| 身體 | 0.968 | 0.986 | 0.993 | 0.993 | ~80v(≈ 藝術家量) |

## 關鍵發現 / 教訓

1. **預設 30v 是為簡單 mesh 校準的,不是全域最優**:curtain/shadow 是近凸直條輪廓,strip 30v 就夠;
   機器人件是**複雜凹輪廓 + 內部細節**,`generate_mesh_v2` 的 auto 模式因 `is_row_convex` 不成立而
   **退回 delaunay-v1**,且需要 2~3 倍頂點才能貼合真實輪廓。→ 生成器需**依輪廓複雜度調頂點預算**,
   不能一個常數走天下。
2. **頂點效率不如藝術家**:藝術家用 78~98v 就達 0.97~0.98(頂點精準落在輪廓轉折);我們的 delaunay
   要 ~156v 才追平 halo。差距在「頂點分布智慧」而非能不能做到 → 後續可用**輪廓自適應取樣**(轉角密、
   直邊疏)提升效率,但不影響「能達標」的結論。
3. **soft edge(光暈)最吃頂點**:半透明徑向邊緣用直邊三角難完全覆蓋,是 IoU 天花板較低的根因;
   藝術家在此件的 IoU_self 亦僅 0.98,非我們獨有。

## 已對生成器做的變更(backward-compatible)

- `generate_mesh_v2.generate(..., density=None)`:新增選填 `density=(max_interior, epsilon_frac, min_dist)`
  透傳給 delaunay-v1 fallback,提高頂點預算。**`None` = 沿用舊預設,不影響現有 4-mesh 校準**
  (`validate_against_real --gen v2` 不受影響)。

## 下一塊工作(natural next chunk)

**weighted mesh 的 deform 閘**:`deform_eval.real_deform_field` 目前用 `vertices.reshape(-1,2)`,
只支援 unweighted;weighted 的 `vertices` 是變長 `[boneCount, boneIdx, bindX, bindY, weight, ...]`,
且 deform 偏移作用在 bind 座標 → 需先實作 weighted 的世界座標/位移場抽取,並以自一致性(藝術家真值
si=0)校準後,才能把「真實 deform 轉移」閘套到 Award 的 3 件上,完成 weighted mesh 的完整整合 AC。
