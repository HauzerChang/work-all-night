# S3 端到端驗收:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh(有真值)

- **結論**:`robot_parts.psd` 的 3 個 warp 件(光暈/身體/左手)經 `psd_slice` 切件 →
  `generate_mesh_v2(auto)` 生成 mesh,對照 Award 真實 spine 的**藝術家 weighted mesh**,
  靜態覆蓋 IoU **全部達標(overall_pass=true)**,且頂點數約為藝術家的 **0.6–0.94 倍**(更精簡)。
  這是「PSD → 件 → mesh」對**真實生產標的**的端到端閉環驗收(前段 S4「PSD↔atlas 同素材」已於
  `s4-psd-to-spine-real.md` 驗;本段補上「件→mesh vs 真值」)。
- **依據**:`tools/mesh_gen/psd_to_mesh_vs_award.py`(自我驗證閘,純 CPU,有真值)。
  報告 `knowledge/figures/psd_to_mesh_vs_award_report.json`;線框對照圖 `knowledge/figures/psd_to_mesh_vs_award.png`。
- **信心**:高(對照藝術家真值,雙來源 atlas/PSD 皆過)。
- **階段**:S3 mesh 生成器 × S4 切圖(第 2 階段能力鍛鍊)。

## 量化結果(margin 0.02)

| 件 | 藝術家 IoU / 頂點 | 生成 IoU / 頂點(atlas 來源) | 生成 IoU(PSD 來源) | 頂點效率 | 判定 |
|---|---|---|---|---|---|
| 光暈 glow | 0.9795 / 78 | **0.9832 / 73** | 0.9796 | 0.94 | PASS |
| 身體 body | 0.9760 / 98 | **0.9858 / 69** | 0.9828 | 0.70 | PASS |
| 左手 hand | 0.9681 / 80 | **0.9816 / 57** | 0.9796 | 0.71 | PASS |

- 生成 mesh 的覆蓋 IoU **都超過**藝術家自身覆蓋,且頂點更少 → 生成器在「保真 vs 精簡」上不輸手做。
- 3 件皆 `_mode=delaunay-v1`(blob 狀,非高瘦 strip,故走 v1 Delaunay 路徑,非 curtain 的 strip)。

## 重要限制(誠實記錄)

- **這 3 個 mesh 在 Award 沒有 deform timeline**——它們是 **weighted mesh 靠骨骼擺放**,
  不是 deform warp(見 `s4-psd-to-spine-real.md`)。故**真實位移場轉移閘不適用**,本次只驗**靜態輪廓覆蓋**。
  變形穩健度的真值驗證仍以 main_draw 的 4 個 unweighted deform mesh 為準(`s3-four-mesh-generalization.md`)。
- IoU 為尺度不變的覆蓋比,故 atlas 來源(~0.70 縮小)與 PSD 來源(原尺寸)可直接對打;
  兩來源結果一致(差 <0.004),印證 S4「同素材」前置。

## 生成器改進:adaptive epsilon(本次副產,已固化)

- **問題**:v1 的 Douglas-Peucker `epsilon_frac=0.008` 是對**直邊件(窗簾/strip)**校準的;
  對**平滑凸形(光暈)**會切角、邊界取樣不足 → 覆蓋率掉到 0.929(< 藝術家 0.980,且 1 孤兒頂點)。
- **修法**:`generate_mesh.generate(adaptive=True, target_iou=0.97, vertex_cap=110)`(預設開)。
  沿 epsilon 遞減階梯 `[0.008,0.004,0.002,0.001]` 建網,用 **`self_iou`(生成器自評,對自身 mask 覆蓋)**
  收斂:取第一個達 `target_iou` 且頂點 ≤ `vertex_cap` 者;皆不達標則取 cap 內 IoU 最高者。
  — 符合專案原則:**確定性演算法 + 評估器把關**,不需外部真值即可自我收斂。
- **效果**:光暈 0.929→0.983、身體/左手也升(0.968→0.986、0.960→0.982),孤兒歸零。
- **回歸**:main_draw 4 mesh 走 **strip** 路徑,不受此改動影響;curtain_left/right + shadow
  仍 overall_pass(deform si=0/flips=0)。(shadow2 與 shadow **共用同一 region**,以 name=`image/shadow`
  驗即可;`--name image/shadow2` 查無 region 屬既有測試呼叫慣例,非本次回歸。)

## 可重跑指令

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o <dir>      # PSD→件
python3 tools/mesh_gen/psd_to_mesh_vs_award.py                            # 端到端閘(exit 0=PASS)
```
