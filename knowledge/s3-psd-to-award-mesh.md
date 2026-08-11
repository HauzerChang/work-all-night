# S3 端到端:PSD 件 → mesh → 對照 Award 真實藝術家 mesh(靜態覆蓋率真值)

> 里程碑(2026-08-11):把 S4(PSD 切件)與 S3(mesh 生成)串成端到端,並第一次
> 對**真實生產 spine 的 weighted mesh**(Award 機器人 3 件)以藝術家 mesh 為真值驗收覆蓋率。
> 工具:`tools/mesh_gen/validate_psd_to_award_mesh.py`。

## 為什麼這件事重要

先前 S3 v2 只在 `main_draw` 的 4 個 **unweighted** mesh(窗簾/陰影,高瘦條狀)驗過。
Award 的機器人件是**weighted mesh**、形狀 blobby(光暈近圓、身體/左手團塊),與窗簾截然不同
→ 是 S3「泛化到真實生產標的」的硬考,而且有藝術家 mesh 當**外部真值**可比。

對應 STATE 的最高優先候選:「PSD件→S3 mesh→對照 Award 真實 mesh」。

## 驗收設計(兩條互補路徑,每部位)

- **(P) PSD 路徑**:`robot_parts.psd` 圖層 alpha → `generate_mesh_v2(auto)` → `evaluate_mesh`
  (格式閘 + 覆蓋率 IoU)。證明「PSD→件→mesh」純 CPU 端到端可跑、產物合法(unweighted、
  hull-first、0 孤兒、0 退化、索引合法)。
- **(A) 真值對照**:同部位在 Award atlas 的 region alpha(`atlas_crop.extract`,多頁自動選 page)
  上,比較「生成 mesh 覆蓋率 IoU」vs「藝術家 mesh 覆蓋率 IoU(`artist_iou`,同一 mask)」。
  過關 = 生成 ≥ 藝術家 − margin(0.03),與 `validate_against_real` 同哲學(對齊藝術家水準,
  不用武斷絕對閾值)。

3 件皆 aspect < 1.2 且非 row-convex → v2 auto 正確路由到 **v1 Delaunay**(strip 對 blob 反而差:
光暈 strip 18×5 只有 0.92,v1 可達 0.98)。

## 關鍵發現:覆蓋率 IoU 由 hull DP 容差決定,不是內部點密度

對光暈(496×480 近圓大 blob)掃參數:

| epsilon_frac | hull 頂點 | 覆蓋率 IoU |
|---|---|---|
| 0.008(舊預設) | 14 | 0.929 ❌ |
| 0.004 | 22 | 0.966 |
| 0.002 | 38 | 0.983 |
| 0.001 | 58 | 0.992 |

`max_interior`(內部點)40→60 幾乎不動 IoU(0.929→0.930)。**固定的「周長比例」epsilon 對大而圓
的件會欠取樣 hull**:平滑大圓周長很長,`0.008×peri` 是很粗的絕對容差,把圓輪廓切成粗多邊形。
窗簾/陰影小又簡單,0.008 剛好夠 → 之前沒暴露這個問題。

## 修正:自適應 hull 精化(綁到評估器)

`generate_mesh.generate(..., auto_hull_target=0.97, vertex_cap=96)`:由粗到細試
`[0.008,0.004,0.002,0.001]`,取**達到覆蓋率目標的最粗(頂點最少)**拓樸;達不到就用最細者,
頂點超過 `vertex_cap` 即停(預算保護)。`auto_hull_target=None` 回退舊固定行為。
把生成直接綁到 IoU 目標,大而圓的件自動加密 hull,不需人工調 epsilon。
v2 的 delaunay 退回路徑(`gen_v1(path)`)吃到新預設,自動受惠。

## 結果(3/3 overall_pass)

| 部位 | 模式 | 生成 nv | 生成 IoU | 藝術家 IoU | 藝術家 nv | 判定 |
|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 73 | 0.983 | 0.980 | 78 | ✅ |
| 左手 | delaunay-v1 | 57 | 0.982 | 0.968 | 80 | ✅ |
| 身體 | delaunay-v1 | 69 | 0.986 | 0.976 | 98 | ✅ |

生成 mesh 的靜態覆蓋率**達到或略勝藝術家**,且頂點數比藝術家更精簡(57–73 vs 78–98)。
PSD 路徑三件亦全 format/coverage 合格(PSD alpha 上 IoU 0.980/0.980/0.983)。

**無回歸**:`main_draw` 4 mesh 的 `validate_against_real --gen v2` 仍全 overall_pass
(strip 模式不受影響;v1 auto_hull 只在覆蓋率不足時才加密)。

## 刻意未做 / open item:weighted mesh 的 deform 閘

Award mesh 是 **weighted**:`vertices` 為 `[骨數, boneIdx,bindX,bindY,weight, ...]` 變長格式,
且 deform timeline 的 `vertices` 是**逐權重項偏移**(非逐頂點)。現行 `deform_eval.real_deform_field`
/ `load_mesh` 假設 unweighted 逐頂點,直接 reshape 會壞。要對 weighted mesh 取真實位移場需先重建
skinning(boneCount/bindpose/weights → local/world)。本次**刻意只驗靜態覆蓋率**,deform 閘留待
後續(需擴充 deform_eval 支援 weighted;或以「把 Award weighted 展平成等效 unweighted setup pose
+ 逐頂點合成 offset」近似)。⚠️ 依 RULES 不得用未校準的 `stress_field` 當 pass/fail 閘。

## 標準指令

```
PYTHONPATH=tools/mesh_gen python3 tools/mesh_gen/validate_psd_to_award_mesh.py
```
