# S3 端到端:PSD 切件 → 生成 mesh → 對照真實生產 Spine(Award)

**結論**：把「PSD 切件 → `generate_mesh_v2` 生成 mesh」這條下游 pipeline,對**真實生產標的**
(機器人 big win 的 Award spine)驗收 —— 3 個機器人 mesh(光暈 / 左手 / 身體)生成 mesh 的
**靜態覆蓋率**皆達到藝術家真實 mesh 的水準(容差內全 PASS),且用**更少頂點**達到相近覆蓋。

**信心**：高(對真實生產 mesh 的量化對照 + 負對照確認鑑別力)。**相關階段**:第 2 階段 S3/S4 串接。

## 工具

`tools/mesh_gen/psd_to_award.py`(端到端閘,純 CPU 可自驅):
1. `slice_psd` 從 `robot_parts.psd` 切出目標圖層(tight-crop,原圖解析度、原始朝向)。
2. `generate_mesh_v2(mode="auto")` 生成拓樸 → `evaluate_mesh` 覆蓋率 IoU(vs 該件 alpha)。
3. 對照 Award 對應 slot 的藝術家真實 mesh(名稱慣例 `機器人拆件/<圖層名>`):
   `artist_iou` 對**同一份 PSD mask** 求覆蓋率基準;overall_pass = 生成 IoU ≥ 基準 − margin(0.02)。

標準指令:`python3 tools/mesh_gen/psd_to_award.py --tmp <dir>`(exit 0 = all_pass)。

## 量化結果(2026-08-18)

| 件 | 生成 IoU | 藝術家基準 | 生成頂點 | 藝術家頂點 | pass |
|---|---|---|---|---|---|
| 光暈 | 0.9331 | 0.9486 | 35 (hull16) | 78 (hull78,純外框) | ✅ |
| 左手 | 0.9642 | 0.9768 | 59 (hull19) | 80 (hull42) | ✅ |
| 身體 | 0.9660 | 0.9477 | 60 (hull20) | 98 (hull40) | ✅ |

- 生成 mesh 頂點數(35~60)遠少於藝術家(78~98),覆蓋率仍相當 → 頂點預算有餘裕。
- 光暈藝術家 mesh 為 hull=nv(78/78)的**純外框環狀** mesh;生成器用 35 點仍覆蓋 0.93。

## 鑑別力(負對照)

同一顆「左手」生成 mesh,量對**錯配** mask 的覆蓋率:
- vs 左手 mask(matched):**0.9642**
- vs 身體 mask:0.5208 / vs 光暈 mask:0.5827(mismatch 明顯掉)→ 覆蓋率閘有鑑別力,非人人都高。

## ⚠️ 重要發現:機器人 mesh 是 weighted 且 bone 驅動,無 deform timeline

- Award 共 7 個 mesh,全部 **weighted**(`len(vertices) != len(uvs)`;JSON 每頂點
  `boneCount,(boneIdx,bindX,bindY,weight)*boneCount`)。左手:80 頂點 / 119 影響(41 個 1-bone、39 個 2-bone)。
- 3 個機器人 mesh 在 12 支動畫**皆無非零 deform 頂點**(逐幀掃過確認)→ 它們靠 **bone 骨架驅動**變形,
  不是 per-vertex deform timeline。
- 影響:現有 `deform_eval.real_deform_field` / `transfer_deform_check`(針對 per-vertex deform)
  以及 `load_mesh`(假設 unweighted `vertices.reshape(-1,2)`)對這些 mesh **N/A**;
  硬跑會 `ValueError: different number of values and points`(weighted vertices 長度 ≠ 2*nv)。
- 因此本閘只做「靜態覆蓋 + 拓樸預算」對照,**不含變形耐受度**。

## 待補(deform 耐受度的正確做法,列後續 chunk)

要量化生成 mesh 在**骨驅變形**下的耐受度(自交/翻面),需要:
1. **BBW 權重**(S3 尚未建):把生成 mesh 綁上骨頭,才能被 bone 動畫驅動。
2. **bone 動畫取樣**:setup pose bone world transform + 各 transform timeline(rotate/translate/
   scale/shear、緊湊 bezier)→ 逐幀 weighted world vertices → 拓樸閘。
或折衷:把「藝術家 weighted mesh 逐頂點 world 位移(setup→動畫幀)」抽成位移場(UV 座標),
再用既有 `transfer_deform_check` 轉移到生成 mesh —— 這條只需 bone 動畫取樣、不需先做 BBW,
是接續此 chunk 的最小可行 deform 閘。
