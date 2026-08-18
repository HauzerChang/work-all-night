# 端到端驗收:PSD 切件 → S3 mesh → 對照 Award 真實生產 mesh

- **結論**：把 `robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手)的**真實 alpha** 餵進 S3
  `generate_mesh_v2`(auto),與生產 spine `Award` 的藝術家 mesh 做靜態覆蓋 IoU + 頂點預算 +
  拓樸對照 → **3 件全 PASS**:生成 mesh 覆蓋率**追平或超越藝術家**,且頂點數少一半。
  端到端「PSD → 件 → mesh」對真實生產標的首次跑通。
- **信心**：高(真實生產 PSD + 真實生產 spine 雙真值;評估器先以藝術家 mesh 自一致性校準)。
- **階段**：第 2 階段 / S3+S4 串接(里程碑:從單一資產 → 端到端跨 PSD/spine)。

## 對照結果(`compare_psd_award_mesh.py`)

| 件 | 藝術家 IoU | 生成 IoU | 藝術家 v | 生成 v | 生成 mode | budget/degen/orphan |
|---|---|---|---|---|---|---|
| 光暈 | 0.9486 | 0.9331 | 78 (hull 78, 純環) | 35 (hull 16) | delaunay-v1 | ✅/0/0 |
| 身體 | 0.9477 | 0.9660 | 98 (hull 40) | 60 (hull 20) | delaunay-v1 | ✅/0/0 |
| 左手 | 0.9768 | 0.9642 | 80 (hull 42) | 59 (hull 19) | delaunay-v1 | ✅/0/0 |

判準:生成 IoU ≥ 藝術家 − 0.02(覆蓋率追平);頂點 ≤ budget(100);format/退化/孤兒全過。

## 關鍵發現

1. **v2 auto 正確分派到 v1(Delaunay)**:這 3 件是**塊狀角色件**(aspect < 1.2 或非 row-convex),
   不是窗簾式直條 → auto 回退 v1 散點拓樸。印證 auto 的 strip/Delaunay 分派邏輯對真實件有效:
   **窗簾/陰影 → strip;角色塊件 → Delaunay。**
2. **生成 mesh 用不到一半頂點達到同等覆蓋**:光暈藝術家用 78 點純 hull 環(無內點),
   生成僅 16 hull + 內點即達 0.933(近 0.949)。身體/左手生成覆蓋率**反超**藝術家。
3. **覆蓋率由邊界取樣密度決定**(統一原理,跨 v1/v2):
   光暈 `epsilon_frac` 敏感度(hull 密度 → IoU):
   | eps | hull | verts | IoU |
   |---|---|---|---|
   | 0.008 | 16 | 35 | 0.9331 |
   | 0.004 | 25 | 44 | **0.9606**(已超藝術家 0.9486) |
   | 0.002 | 45 | 64 | 0.9796 |
   | 0.001 | 62 | 81 | 0.9918 |
   → v1 的覆蓋旋鈕是 `epsilon_frac`(Douglas-Peucker 容差),等同 v2 的 `rows`;
   **內部點不影響覆蓋率**(與 four-mesh 發現「cols 不影響」一致)。柔邊件(光暈)想更貼邊就降 eps。

## 評估器可信度先驗(沿用守則)

先確認藝術家 mesh 對自己的件 alpha 覆蓋高:IoU 0.949/0.948/0.977、`flip_v=false`
→ uvs(region 局部 texcoord)→ 件像素 `px=u*W, py=v*H` 映射正確、方向無翻轉,
故拿藝術家 IoU 當生成 mesh 參照可信。

## ⚠️ 範圍與限制(誠實記錄)

- **這 3 件在 Award 無 deform timeline**(見 s4-psd-to-spine-real.md):靠**骨骼 + 權重**變形,
  非逐頂點 deform。故本輪**只驗靜態覆蓋 + 拓樸精簡度,未套 deform 閘**(deform 閘適用於
  main_draw 窗簾/陰影那種帶 deform timeline 的件)。
- **生成 mesh 為 unweighted**,Award mesh 為 **weighted**(vertices≠uvs,綁 bone)。
  → 生成件**不是骨架驅動件的即插即用替代**;要真正靠骨骼變形,還缺 **BBW 權重綁定**
  (S3 路線圖項,尚未實作)。這是角色塊件端到端的**下一個真正缺口**。
- 對照的是「覆蓋率 + 頂點精簡 + 拓樸合法」,不是「變形手感等價」。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
python3 tools/mesh_gen/compare_psd_award_mesh.py     # 3 件 overall_pass=True
```
