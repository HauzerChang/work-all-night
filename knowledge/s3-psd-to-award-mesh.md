# 端到端 PSD件 → S3 mesh → 對照 Award 真實藝術家 mesh(里程碑)

- **結論**:把 S4 切件與 S3 生成器串成端到端管線,對**真實生產標的**驗收:
  `robot_parts.psd` 的 3 個 mesh 件(光暈 / 身體 / 左手)經 `generate_mesh_v2` 生成的 mesh,
  **覆蓋率(填滿 IoU)全部達到或超越 Award 生產 spine 中藝術家手做 mesh 的水準,且用更少頂點**。
- **信心**:高。用真實藝術家 mesh 當基準 + 三重負對照確認 IoU 有鑑別力 + 藝術家 uvs 落在 PSD 遮罩上的
  高吻合度(~0.95)反證了座標/朝向對齊正確。
- **階段**:第 2 階段 / S3×S4 端到端(里程碑:合成/單資產 → 真實生產標的端到端)。

## 結果(`tools/mesh_gen/validate_against_award.py`)

| 件 | 生成模式 | 生成 v / hull / tri | 生成 IoU | 藝術家 v(weighted)/ hull | 藝術家 IoU | Δ | 判定 |
|---|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 35 / 16 / 49 | 0.9331 | 78 / 78 | 0.9486 | −0.0155 | PASS |
| 身體 | delaunay-v1 | 60 / 20 / 97 | 0.9660 | 98 / 40 | 0.9477 | **+0.0183** | PASS |
| 左手 | delaunay-v1 | 59 / 19 / 97 | 0.9642 | 80 / 42 | 0.9768 | −0.0126 | PASS |

- 判定門檻:生成 IoU ≥ 藝術家基準 − 0.02(對齊 AC.md AC1「對齊藝術家而非武斷 0.95」),
  且 evaluate_mesh 靜態有效性(重心在內 / 無退化 / 無孤兒 / Spine 格式)全過。**overall_pass=true**。
- 3 件在 `mode=auto` 下**全落回 delaunay-v1**(compact/blobby、非高瘦 row-convex),
  與窗簾 strip(v2)互補 → 驗證了 v1 Delaunay 對真實生產「緊湊件」的覆蓋能力。

## 評估器可信度(先校準再下判定,RULES 規則)

同一遮罩上的負/平凡對照,確認 IoU 非「因件近似填滿 bbox 而虛高」:

| 件 | 遮罩填充率 | 全 bbox 矩形 IoU | 藝術家 mesh 縮 15% IoU | 藝術家/生成(實際) |
|---|---|---|---|---|
| 光暈 | 0.465 | 0.465 | 0.684 | ~0.94 |
| 身體 | 0.498 | 0.498 | 0.705 | ~0.95–0.97 |
| 左手 | 0.683 | 0.683 | 0.730 | ~0.96–0.98 |

→ 平凡矩形只得填充率(0.47–0.68),縮 15% 掉到 0.68–0.73,**都遠低於 ~0.95**;
達到 0.93+ 確實需要貼合輪廓 → 指標有鑑別力。

## 對齊細節(踩雷紀錄)

- **Award mesh uvs = region-local 0..1**(光暈 0.01–0.99 等),width/height = 原始邏輯尺寸;
  與 PSD 上直切件同向。故 uvs×(遮罩 W,H) 直接落在 PSD 遮罩上。
- 光暈 / 身體 在 atlas 是 `rotate=true`,但 **JSON 的 uvs 在上直邏輯 region 空間**(非 atlas 旋轉後空間);
  藝術家 IoU ~0.95(高)即證此對齊 —— 若朝向搞錯會掉到 ~0.4。**遮罩故意用 PSD native
  上直件**(乾淨、無 atlas 0.70 縮放與旋轉還原插值),避免 atlas_crop 路徑的雜訊。

## ⚠️ 誠實界線(本閘**沒**驗到的)

- Award 這 3 件是 **weighted mesh(靠骨骼權重變形,無 deform timeline)**;頂點較密**是為了骨骼蒙皮
  的平滑變形**,不是為了覆蓋。本閘只證「**靜態覆蓋**用更少頂點打平藝術家」,**未證**這 35–60 個
  unweighted 頂點在骨骼驅動下能蒙皮得一樣順 —— 那需要 S3 尚未做的 **BBW 權重 + 骨架綁定**臂。
- 因無 deform timeline,`transfer_deform_check` 真實變形閘在此**不適用**(已刻意略過,非遺漏)。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts   # 切件
python3 tools/mesh_gen/validate_against_award.py                                 # 端到端閘,exit 0 = PASS
```

## 下一步

- 把「件→Spine attachment」慣例(`PSD名/圖層名`、mesh/region 分配、+2px padding、
  region-local uvs、atlas 0.70 縮放)固化成 SkelToJson 組裝工具,端到端產出 Spine JSON。
- 若要驗 weighted 蒙皮平滑度,需先建 S3 權重臂(BBW)+ 從 Award 借骨架綁定。
