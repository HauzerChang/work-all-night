# S3 端到端驗收 — 生成 mesh 對照 Award 真實生產 mesh（有真值）

- **結論**：機器人拆件 3 個 mesh 件（光暈 / 身體 / 左手）以真實生產 spine `Award` 的
  藝術家手做 mesh 為 IoU 真值基準，S3 生成器（v1 Delaunay + 新增**自適應 epsilon 收斂**）
  **3/3 達到藝術家級覆蓋率**（皆過 0.96 art-grade 目標、與藝術家 IoU 差 ≤0.02），
  且只用 **藝術家頂點數的 ~40–50%**（37–38v vs 78–98v）。端到端「件 alpha → 生成 mesh
  ≈ 藝術家 mesh」對真實標的成立。
- **信心**：高（真實生產資產真值 + 雙向校驗 uv 慣例 + 自我收斂閘 + 4-mesh 無回歸）。
- **階段**：第 2 階段 / S3 ⇄ S4 串接（里程碑：從合成/main_draw → 對真實生產 mesh 有真值對照）。

## 真值來源與 uv 慣例（校正先前假設）

- 3 件在 `Award` 皆為 **weighted mesh**（無 deform timeline，靠骨骼/權重變形）：
  光暈 78v/76t/hull78（純邊界環）、身體 98v/154t/hull40、左手 80v/116t/hull42。
- **Award mesh 的 `uvs` 是 region-local 正規化 [0,1]**（uv 全幅約 [0,1]），
  **非 atlas-page UV**（更正 `s4-psd-to-spine-real.md` 的謹慎假設）。
- **v 軸不需翻轉**：對 `atlas_crop.extract()` 的 CW-derotate region alpha,
  `flip_v=False` 藝術家 IoU 0.97–0.98；`flip_v=True` 掉到 0.44–0.61 → 確認慣例。
- region alpha 尺寸 ≈ PSD × 0.70（atlas 打包縮小,見 s4 筆記）；uvs 正規化故不受縮放影響。

## 對照結果（`compare_to_award.py`，真值 = extract 的 region alpha）

| 件 | region px | 藝術家 v / IoU | 生成 v / IoU | eps | 判定 |
|---|---|---|---|---|---|
| 光暈 | 496×480 | 78 / 0.9795 | 37 / 0.9677 | 0.004 | PASS |
| 身體 | 267×299 | 98 / 0.9760 | 37 / 0.9677 | 0.008 | PASS |
| 左手 | 181×152 | 80 / 0.9681 | 38 / 0.9602 | 0.008 | PASS |

AC：① 生成 IoU ≥ 藝術家基準 − 0.02 且過 0.96 art-grade；② 頂點 ≤ min(64, 藝術家)；
③ 格式（unweighted/hull/索引）、0 退化、0 孤兒；④ 三角重心全在 mask 內。四項皆過。

## ★ 關鍵發現：固定 epsilon 對「大而彎的件」欠取樣 → 自適應收斂

- 首跑（固定 `epsilon_frac=0.008`）**光暈 fail**：hull 只簡化到 14 點、IoU 0.9316。
  身體/左手（較小/邊界較簡單）在 0.008 已過。
- 掃描證實 **IoU 由邊界取樣（epsilon）決定,內部點（min_dist）幾乎不影響覆蓋率**
  （與 4-mesh「IoU 由 rows 決定、cols 不影響」同一規律的散點版）：
  光暈 eps 0.008→14hull/0.932、0.004→22hull/0.968、0.002→38hull/0.983、0.001→58hull/0.992。
- **修法(Build-Verify 方法論落地)**:`generate_mesh.generate_adaptive()` 由粗到細掃 epsilon,
  用內嵌 IoU 閘驅動,取「第一個 IoU≥target 且 v≤budget」→ 生成器用自己的評估器自我收斂。
  避免固定 epsilon 對大件欠取樣、對小件過取樣。收斂 meta 寫入 `mesh["_adaptive"]`。

## 教訓 / 方法論

- **有真值就用真值**：藝術家 mesh 給了「覆蓋率該多少、頂點花多少」的客觀天花板;
  沒它時只能自比,容易把「固定 eps 欠取樣」當成通過。真值揭示生成器需自適應。
- 生成器頂點更省(~半)但覆蓋率追平藝術家 → 對「量少求穩」的 runtime 是利多;
  但**光暈是純邊界環,藝術家 78 點全 hull**,若之後要逐頂點 deform,取樣密度可能仍需再加。

## 可重現

```
python3 tools/mesh_gen/compare_to_award.py            # 3 件全 PASS，exit 0
python3 tools/mesh_gen/compare_to_award.py --generator v2   # 對照:固定參數(光暈 fail)
```

## 下一步

- 把 `PSD名/圖層名` + size+2px padding + mesh/region 分配 + 自適應生成,固化成
  「件 → Spine attachment（含 mesh）」的 SkelToJson 組裝工具(端到端產 Spine JSON)。
- 或補 S2 補圖閘 / 骨架閘（純 CPU 樞紐)。
