# S3×S4 端到端 — PSD 件 → 生成 mesh → 對照 Award 真實 mesh

- **結論**:把 S4(PSD 切件)與 S3(mesh 生成)串成端到端,並對**真實生產 spine(Award)的 mesh**
  做覆蓋率對照。`robot_parts.psd` 的 3 個 mesh 件(光暈 / 身體 / 左手)用 S3 v1 Delaunay
  (`epsilon_frac=0.003`)生成的 mesh,**覆蓋率 IoU 全部 ≥ 藝術家真實 mesh、頂點數更少、基礎拓樸乾淨**。
  → 「PSD → 件 → mesh」對真實生產標的整合驗收通過。
- **信心**:高(對真實生產 mesh ground truth 對照 + frame 驗證 + 跨件負對照)。
- **階段**:第 2 階段 / S3×S4 整合。工具:`tools/mesh_gen/validate_psd_mesh.py`。

## Frame 驗證(關鍵前置:確認真值可用)

生產 spine mesh 的 `uvs` 是否為 region-local?先驗:把 Award mesh uvs 直接 ×(件 W,H)疊到
**PSD 切件 alpha** 上量覆蓋率:

| 件 | uvs as-is IoU | v-flip IoU |
|---|---|---|
| 光暈 | **0.9486** | 0.4264 |
| 身體 | **0.9477** | 0.6038 |
| 左手 | **0.9768** | 0.5896 |

as-is 高、v-flip 崩 → 證實:① Spine JSON mesh `uvs` = **region-local [0,1]**(不是整頁 atlas UV,
不需除以 page 尺寸)② **不需翻 v**;③ PSD 切件 = spine mesh 素材(同一份、同朝向)。
與 `validate_against_real.py::artist_iou` 對 main_draw 的用法一致 → 通用結論。

## 生成結果(eps=0.003,對照藝術家)

| 件 | 生成 nv/hull/tri | 藝術家 nv/hull/tri | 生成 IoU | 藝術家 IoU | 覆蓋 pass | 基礎 si/degen |
|---|---|---|---|---|---|---|
| 光暈 | 49/30/61 | 78/78/76 | 0.9663 | 0.9486 | ✅ | 0/0 |
| 身體 | 72/32/110 | 98/40/154 | 0.9880 | 0.9477 | ✅ | 0/0 |
| 左手 | 75/35/113 | 80/42/116 | 0.9849 | 0.9768 | ✅ | 0/0 |

**生成 mesh 覆蓋率 ≥ 藝術家,且頂點數更精簡(49~75 vs 78~98)。**

## ⚠️ 重要參數發現:`epsilon_frac` 是 v1 的覆蓋率旋鈕(大件要調小)

延續四-mesh「IoU 由 rows 決定(strip)」的發現,v1(Delaunay)的對應旋鈕是
**`epsilon_frac`(hull Douglas-Peucker 簡化係數)**。掃描(eps → 生成 IoU):

| eps | 光暈 | 身體 | 左手 |
|---|---|---|---|
| 0.008(舊預設) | 0.9331 ✗ | 0.9660 ✅ | 0.9642 ✗ |
| 0.005 | 0.9606 ✅ | 0.9802 ✅ | 0.9737 ✗ |
| **0.003** | **0.9663 ✅** | **0.9880 ✅** | **0.9849 ✅** |
| 0.002 | 0.9796 | 0.9908 | 0.9901 |
| 0.001 | 0.9918 | 0.9947 | 0.9942 |

- **舊預設 0.008 是對 main_draw 小窗簾(~數百 px)調的,對 ~700px 的機器人件太粗** → hull 只 16~19 點,
  覆蓋率略低於藝術家。調到 **0.003 → 3 件全過**且 hull 30~35(仍遠少於光暈藝術家的 78)。
- eps 越小 hull 越貼、IoU 越高、頂點越多 → 覆蓋率/精簡度的旋鈕。0.003 是「過藝術家基準又保精簡」的甜蜜點。
- **`validate_psd_mesh.py` 預設 eps=0.003**;窗簾/陰影等 deform-bearing 件仍走 `validate_against_real.py`
  (strip + 真實 deform 閘)。

## auto 模式的正確行為

`generate_mesh_v2(mode="auto")` 對這 3 件**全部回退 v1 Delaunay**(aspect < 1.2 或非 row-convex),
strip 模式對它們 IoU 反而低(0.88~0.92)。→ **strip 是 deform-bearing 直條件(窗簾/陰影)專用;
blobby 身體部位走 Delaunay 正確**。auto 的啟發式判對了。

## 負對照(閘鑑別力)

生成 mesh(ROW)疊到別件 alpha(COL)的 IoU 矩陣:

|  | 光暈 | 身體 | 左手 |
|---|---|---|---|
| 光暈 | **0.966** | 0.480 | 0.575 |
| 身體 | 0.484 | **0.988** | 0.518 |
| 左手 | 0.577 | 0.517 | **0.985** |

對角(正確配對)0.97~0.99,非對角(錯件)0.48~0.58 → 閘能明確區分,不是無腦高分。

## weighted / deform 說明(為何不套 transfer_deform_check)

這 3 件在 Award 為 **weighted mesh 且無 deform timeline**(靠骨骼權重變形,非逐頂點 deform),
故本閘只量「靜態覆蓋率 + 基礎拓樸(setup 0 自交/0 退化)」,不套 `transfer_deform_check`
(那需 deform timeline,見 curtain/shadow)。生成的是 unweighted mesh;若要進 Award 走骨骼變形,
下一步需 S5 綁權重(BBW),超出本 chunk。

## 可重現

```
python3 tools/mesh_gen/validate_psd_mesh.py    # robot_parts.psd 3 mesh 件 → overall_pass=True
# 換件:--psd <PSD> --skeleton <spine.json> --prefix <slot前綴> --gen v1 --epsilon 0.003
```
