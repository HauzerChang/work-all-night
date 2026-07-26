# S3 端到端驗收：PSD 件 → 生成 mesh → 對照 Award 真實 mesh

- **結論**：把 S4 切圖(`psd_slice`)與 S3 mesh 生成(`generate_mesh_v2`)**串成端到端**,
  對真實生產標的(`robot_parts.psd` 的 3 個 mesh 件 ⇄ 生產 spine `Award` 的真實 mesh)驗收。
  發現 v1 Delaunay 舊預設 `epsilon_frac=0.008` 對真實生產 blob **邊界太粗**(hull 16~20 點),
  覆蓋率低於藝術家基準;**校準到 `eps=0.002`(hull 37~45 點)後,3 件 IoU 全 ≥ 藝術家且頂點數 ≤ 藝術家**。
- **信心**:高(有 spine ground truth 真值 mesh 交叉比對 + 掃描確認單調關係 + 回歸不破壞 main_draw)。
- **階段**:第 2 階段 / S3 × S4 串接(里程碑:合成/單件 → 端到端對真實生產標的)。

## 標的(3 個在 Award 中為 mesh 的件)

| PSD 件 | 件尺寸 | Award slot/name | 藝術家 mesh | 型態 |
|---|---|---|---|---|
| 光暈 | 706×683 | `機器人拆件/光暈` | 78v / 76t / hull78(**全周界環**) | **weighted,無 deform timeline** |
| 身體 | 379×425 | `機器人拆件/身體` | 98v / 154t / hull40 | weighted,無 deform timeline |
| 左手 | 257×215 | `機器人拆件/左手` | 80v / 116t / hull42 | weighted,無 deform timeline |

**關鍵前提**:這 3 件在 Award **全為 weighted mesh(`vertices.len≠uvs.len`)且無任何 deform timeline**
(12 支動畫全查過) → 靠**骨骼/權重**驅動變形,非逐頂點 deform。
故 `deform_eval` 的 **deform-transfer 閘(deform timeline)在此不適用**;本次比對限於**靜態 IoU + 拓樸**。
(bone-skin 驅動的變形場提取是獨立、較大的子任務,列為下一步。)

## 校準前 vs 校準後(對照藝術家真值 IoU)

生成器 IoU 需 ≥ 藝術家 mesh 對同一 alpha 的覆蓋率(沿用 `validate_against_real` 精神,非武斷 0.95)。

| 件 | 藝術家 IoU | v1 舊(eps=0.008) | v1 校準(eps=0.002) |
|---|---|---|---|
| 光暈 | 0.9486 | 0.9331 nv35/hull16 ❌ | **0.9796 nv64/hull45 ✅** |
| 身體 | 0.9477 | 0.9660 nv60/hull20 ✅ | **0.9908 nv77/hull37 ✅** |
| 左手 | 0.9768 | 0.9642 nv59/hull19 ❌ | **0.9901 nv84/hull44 ✅** |

- eps 掃描(0.008→0.001)呈**單調**:邊界越密 → hull 越多 → IoU 越高、頂點數越多。
- `eps=0.002` 是甜蜜點:3 件 IoU 全過藝術家,且生成頂點數(64/77/84)**≤ 藝術家**(78/98/80)
  → **確定性生成器用更精簡的頂點達到 ≥ 藝術家的覆蓋率**。
- 印證並推廣 strip 版結論:**IoU 由「邊界取樣密度」決定**(strip 是 rows、Delaunay 是 epsilon_frac);
  cols / 內部點只補內部,不影響覆蓋率。

## 動作(已落地)

- `generate_mesh_v2.generate()` 新增 `epsilon_frac`(預設 **0.002**)、`max_interior` 參數,
  threaded 進 blob 走的 Delaunay(v1)fallback;CLI 加 `--epsilon`。
- 舊 `generate_mesh.py` 本體預設維持 0.008(合成 AC 測試不受影響)。
- **回歸**:main_draw 4 個 mesh 走 strip 路徑,不受此改動影響 —— 全 `overall_pass`
  (IoU ≥ 藝術家、真實 deform 0 自交 / 0 翻面)。

## 可重現

```
export PYTHONPATH=tools/mesh_gen
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts   # 切件
python3 tools/mesh_gen/compare_to_award.py --mode auto                            # 3 件對照 → overall_pass
# 回歸(strip 路徑不受影響):
python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot image/curtain_left --name image/curtain_left
python3 tools/mesh_gen/validate_against_real.py --gen v2 --slot image/shadow2     --name image/shadow   # shadow2 共用 shadow region
```

## 下一步

- **bone-skin 變形場對照(補完 deform 面向)**:這 3 件靠骨骼/權重變形。可用 Award 的 bone
  transforms + mesh 權重,計算 setup vs 動畫幀的真實世界頂點位移場,轉移到生成 mesh 上跑
  自交/翻面閘(等同 `transfer_deform_check`,但場源自 skinning 而非 deform timeline)。
- **切圖 → Spine JSON 組裝(SkelToJson)**:把 `<PSD名>/<圖層名>`、size+2px、mesh/region 分配、
  校準後的 mesh 生成參數固化成「件 → Spine attachment」寫出工具,端到端產 Spine JSON。
