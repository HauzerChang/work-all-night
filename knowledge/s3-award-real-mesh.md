# S3 對真實生產 mesh(Award)端到端驗收 + 自適應覆蓋

> 結論:S3 生成器在「給足與藝術家相當的頂點預算」時,對 Award 三個真實 weighted mesh 件
> (光暈/身體/左手)**覆蓋 IoU 全達或超過藝術家,且用更少頂點**。揭示「覆蓋率 = hull 密度」
> 對 blobby 件同樣成立、預設參數對 blobby 件過粗、以及 **64 頂點預算與藝術家密度(78–98)的張力**。
> 信心:高(有生產真值對照;對齊基礎經 alpha-IoU 驗證)。相關階段:S3(mesh)× S4(PSD→spine)整合。

## 為什麼這是有價值的真值

先前 S3 只對 main_draw 的 **4 個 unweighted、strip(高瘦)mesh**(窗簾/陰影)驗過。Award 機器人拆件
提供**另一類**真值:**weighted、blobby(近方形)** 的生產 mesh —— 光暈(496×480, hull78/78v)、
身體(267×299, hull40/98v)、左手(181×152, hull42/80v)。這檢驗 S3 對「非 strip 件」的通用性。

## 對齊基礎(比對有效性的前提,已驗)

- **Award mesh `uvs` 為 region-local [0,1]**(相對原始未旋轉件),非 atlas page 全域 UV。
  (光暈 0.012–0.99、身體 0–0.759 等子範圍只是件內容未填滿外接框,不影響。)
- `atlas_crop.extract`(**CW** derotate,見 s4-psd-to-spine-real.md)還原上正件;以藝術家
  `uvs×(W,H)` 填回該件 alpha,三件 **alpha-IoU 0.968~0.980** → 確認比對座標系一致、extract 方向正確。
- 三件以同一張 atlas crop alpha 為基準比對(藝術家覆蓋 IoU = AC1 門檻 bar)。

## 結果(`tools/mesh_gen/compare_to_award.py`)

預設(epsilon_frac=0.008)**全部低於**藝術家覆蓋:

| 件 | crop | 藝術家 IoU(verts) | 生成預設 IoU(verts) | 達標? |
|---|---|---|---|---|
| 光暈 | 496×480 | 0.9795 (78) | 0.9292 (54) | ✗ |
| 身體 | 267×299 | 0.9760 (98) | 0.9680 (61) | ✗ |
| 左手 | 181×152 | 0.9681 (80) | 0.9602 (48) | ✗ |

自適應覆蓋(`generate(..., target_iou=藝術家IoU)`,沿 eps 階梯加密輪廓):

| 件 | budget=64 | budget=100 | budget=100 verts vs 藝術家 |
|---|---|---|---|
| 光暈 | 0.9656 (61, capped) ✗ | **0.9832 (73)** ✓ | 73 < 78 |
| 身體 | 0.9680 (61, capped) ✗ | **0.9858 (69)** ✓ | 69 < 98 |
| 左手 | **0.9816 (57)** ✓ | **0.9816 (57)** ✓ | 57 < 80 |

→ **給足預算(≈藝術家密度)時,3/3 達或超過藝術家覆蓋,且用更少頂點**;static AC(重心/退化/孤兒/格式)全過。

## 關鍵發現

1. **「覆蓋率由 hull 密度(epsilon_frac)決定,內部點(max_interior)幾乎不影響」對 blobby 件同樣成立**
   —— 與 v2 strip 的「IoU 由 rows 決定、cols 不影響」是同一條結論。覆蓋是輪廓性質。
2. **v1 預設 epsilon_frac=0.008 對 blobby 生產件過粗**(輪廓被過度簡化 → 低覆蓋)。它是對 curtain/shadow
   strip 調的;對 Award blobby 件需 eps≈0.002–0.004 才追上藝術家。
3. **64 頂點預算 vs 藝術家密度(78–98)的張力**:要追上細緻近圓件(光暈)的覆蓋需 ~73 頂點(>64)。
   藝術家自己也用 78–98 頂點。**選擇**:(a) 對細緻件放寬預算到 ~100;(b) 接受略低覆蓋換精簡。
   屬主觀/專案決策(預算 vs 保真),留給里程碑審查;客觀上「給足預算即可達標」已證。
4. **deform 閘不適用於這三件**:Award 中機器人 5 件**無 deform timeline**(剛體,靠骨骼)→ 無真實位移場。
   依 AC.md 不用未校準 stress_field 當 pass/fail,故此處只報靜態 AC。

## 工具產出(可續跑)

- `tools/mesh_gen/compare_to_award.py` —— 對 Award 3 件的整合對照 gate(預設 vs 自適應,以藝術家 IoU 為門檻)。
  指令:`python tools/mesh_gen/compare_to_award.py --budget 100`(3/3 達標,exit 0)。
- `generate_mesh.generate(..., target_iou=, vertex_budget=)` —— 新增**自適應覆蓋**(opt-in;
  target_iou=None 時行為與舊版 byte-identical,零回歸)。沿 eps 階梯取「達標且最省點」解;
  預算內達不到則回退最高覆蓋解並標 `_budget_capped`。`generate_mesh_v2.generate` 已透傳 target_iou。
- 回歸驗證:main_draw `validate_against_real --gen v2` 4 mesh 仍全 PASS(exit 0;4 mesh 走 strip,不受影響)。

## 未解 / 下一步

- 自適應預設值:是否把 v1 預設 epsilon 由 0.008 降到 0.004(改善 blobby、不影響 strip 路徑)?
  目前選擇保守:預設不動,自適應為 opt-in。可在串「件→Spine JSON」組裝工具時,依件型自動帶 target_iou。
- 真正的端到端還缺「件→Spine JSON 組裝(SkelToJson)」:把 PSD 件 + 生成 mesh + `<PSD檔名>/<圖層名>`
  命名慣例 + size+2px padding 寫成 Spine attachment。本次已備齊 mesh 端與真值對照。
