# S3 端到端驗證:機器人件 → 生成 mesh → 對照 Award 真實藝術家 mesh

- **結論**:S3 `generate_mesh_v2` 在**非窗簾、真實生產標的**(Award big win 機器人 3 件:光暈/身體/左手)
  上,靜態 IoU **全部高於藝術家真值**且頂點更少。auto 模式正確把這些寬扁/圓/軟邊件路由到
  **delaunay**(非 strip);唯一調整是把 delaunay 邊界簡化 `epsilon_frac` 預設由 0.008 收緊到 **0.003**。
- **信心**:高。有藝術家 mesh 當真值,且映射正確性有自檢(藝術家 mesh 對自身 alpha IoU 0.967~0.972)。
- **階段**:第 2 階段 S3(用真實生產標的驗收 S3 通用性)。純 CPU 自驅,不需 Award.png 以外資源。

## 量化結果(`tools/mesh_gen/validate_robot_mesh.py`,eps=0.003)

| 件 | 藝術家 IoU / 頂點 | 生成 IoU / 頂點 | 勝過藝術家 | 省頂點 |
|---|---|---|---|---|
| 機器人拆件/光暈 | 0.9714 / 78(全 hull) | 0.9779 / 68 | ✅ | 10 |
| 機器人拆件/左手 | 0.9674 / 80 | 0.9884 / 61 | ✅ | 19 |
| 機器人拆件/身體 | 0.9716 / 98 | 0.9876 / 71 | ✅ | 27 |

`overall_pass=True`(3/3 mapping_ok 且 beats_artist)。

## 關鍵發現

1. **Award mesh uvs 是 region-local 0..1**(不是整頁 atlas UV)。`(u*cropW, v*cropH)`(y 向下)
   直接命中 `atlas_crop.extract` 的 derotate crop → 藝術家 mesh 對自身 alpha IoU 0.967~0.972。
   這給了「把任何 Award weighted mesh 拉回 region-local 做比對」的可靠映射(供未來 S3 vs 真實 mesh)。
2. **邊界取樣密度(epsilon_frac)主宰圓弧覆蓋率**。光暈是圓形軟邊:
   eps=0.008 → hull 僅 14 點、IoU 0.929(<< 藝術家 0.971);eps=0.004→0.966;eps=0.002→0.983;
   eps=0.001→0.992。**0.003 是甜蜜點**:3 件全勝藝術家、頂點反而更少。
   (窗簾走 strip 模式不受影響 → 收緊 delaunay 預設對 4 mesh 零回歸,已重驗全 pass。)
3. **artists' mesh 不是 IoU 1.0**:藝術家 mesh 對自身 alpha 只 ~0.97(簡化多邊形內接曲線會漏面積 +
   軟邊)。所以「勝過藝術家」是合理且非武斷的 AC 基準。

## 界線 / 待續(誠實標記)

- **只驗了靜態 IoU,沒驗變形**。Award 3 件是 **weighted(骨骼蒙皮)、無 deform timeline**,
  與 main_draw 窗簾(unweighted + deform)不同。生成 mesh 是 unweighted,要驗其耐變形需先做
  **權重轉移**(從藝術家 weighted mesh 或 BBW 指派骨權重)—— 屬 S3 後續能力,尚未做。
- atlas region 是 ~0.70 縮小打包;IoU 為覆蓋率(尺度不變),不受影響。alpha 門檻 >10。

## 產出

- `tools/mesh_gen/generate_mesh_v2.py`:delaunay fallback 加 `eps` 參數,預設 0.003(+CLI `--eps`)。
- `tools/mesh_gen/validate_robot_mesh.py`:新驗證器(atlas 件 → 生成 → 對照 Award 藝術家 mesh)。
