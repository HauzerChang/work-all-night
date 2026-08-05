# S3 端到端驗收:對照真實生產 mesh(Award 機器人)

> 里程碑(2026-08-05):S3 mesh 生成器首次放到**另一份、未見過的生產資產**上,對照
> 美術實際手做的 weighted mesh 量化評分。工具 `tools/mesh_gen/compare_to_real_mesh.py`。
> 先前 S3 只在 main_draw 4 mesh 做自我/自一致驗證;本次證明輪廓擬合**泛化到真實標的**。

## 標的

`assets/Award.json`(big win 機器人 spine)裡 3 個 **mesh** 型 attachment(其餘 `右手`/`頭` 是 region):

| part | 真實 verts | 真實 hull | atlas region(packed) | rotate |
|---|---|---|---|---|
| 機器人拆件/光暈 (glow) | 78 | 78(全外周) | 496×480 @ Award2 | true |
| 機器人拆件/身體 (body) | 98 | 40 | 267×299 @ Award2 | true |
| 機器人拆件/左手 (lefthand) | 80 | 42 | 181×152 @ Award | false |

## 座標對映(關鍵,已用外部真值校正)

Award mesh 的 `uvs` 是 **region-local [0,1]**(每件各自撐滿 0..1,**非整頁**正規化);
`width/height` = **原始邏輯尺寸**(光暈 708×685 ≈ PSD bbox 706×683 ✓,身體 381×427 ≈ 379×425 ✓,
左手 259×217 ≈ 257×215 ✓)。因此 region-local 像素 = `uv × crop_dims`,其中 crop = `atlas_crop`
還原旋轉後的 upright region;**無需 flip / swap / 整頁換算**。

校正方法(避免「自洽但方向錯」陷阱,承接 006 的 derotate bug 教訓):掃 8 種
`u-flip × v-flip × swap` 組合,選「真實 hull 點落在 dilate 後 alpha 剪影內比例」最高者。
**三件一致選中 `u0v0s0`(直對映)且明顯勝出**(0.83–0.85 vs 其餘 ≤0.6),
即以外部真值(alpha 剪影)確認對映正確。dilate=6px 時 光暈/身體 hull 100% 落在剪影內
→ 美術 hull 慣例是「略在剪影外幾 px 完整包住」,符合預期。

## 量化結果(`compare_to_real_mesh.py`,auto 模式)

| part | 生成模式 | gen V | real V | **gen∩real IoU** | gen_cov | real_cov | map_inside | gate |
|---|---|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 54 | 78 | **0.911** | 0.926 | 0.972 | 1.00 | PASS |
| 身體 | delaunay-v1 | 61 | 98 | **0.955** | 0.966 | 0.972 | 1.00 | PASS |
| 左手 | delaunay-v1 | 48 | 80 | **0.945** | 0.960 | 0.968 | 0.91 | PASS |

- **gen∩real IoU**:生成 hull 多邊形 ∩ 真實 hull 多邊形。**0.91–0.955** 全過 0.85 閘 → S3 在未見資產上,
  輪廓與美術手做**高度一致**。
- **gen_cov / real_cov**:各自 hull vs 真實 alpha 剪影 的 IoU。美術 mesh 穩定覆蓋 **~0.97**
  (三件幾乎相同 → 反向再驗對映無誤);S3 達 **0.926–0.966**,落在美術 ~1–4% 內,
  且用 **少 30–40% 頂點**(54/61/48 vs 78/98/80)。
- 視覺對照:`knowledge/figures/s3-vs-real-robot-hulls.png`(綠=美術 hull、橙=S3 hull、灰=剪影)。

## 結論與教訓

1. **`auto` 模式正確選 delaunay-v1**:三件 aspect<1.2(blobby),strip 的矩形 hull 較鬆;
   實測 delaunay 在 gen∩real 與覆蓋率**全面優於 strip**(承接先前「strip 適高瘦/凸如窗簾,
   delaunay 適團塊」的分工結論,這次由真實標的再確認)。
2. **美術基準 = 剪影覆蓋 ~0.97 + hull 略在剪影外幾 px**;S3 用更少頂點達到接近覆蓋率。
   頂點數差距**不是品質缺口**:美術多頂點是為 bone-weighted **平滑變形**,不是為輪廓 —— 兩者目的不同。
3. **對映健全度必附外部真值檢核**(`map_inside`);承接 006 教訓,round-trip 自洽不足以保證方向對。

## 局限 / 待續

- 本次只驗**靜態輪廓**。Award 機器人 mesh 是 **weighted(骨驅動)**,沒有 deform timeline
  → 無法取「真實位移場」跑 `deform_eval`,故**變形穩健性未對這 3 件驗證**。若要驗變形,需
  有 deform-timeline 的生產 mesh(main_draw 窗簾已驗)或美術提供骨骼權重下的極端幀真值。
- `compare_to_real_mesh.py` 現寫死機器人 3 件的對映假設(region-local uv);換其他生產檔前,
  先跑內建 `map_inside` 檢核(<0.85 代表對映需重新校正)。
