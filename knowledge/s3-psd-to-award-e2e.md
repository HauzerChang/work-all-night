# S3 端到端:機器人件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把 S3 `generate_mesh_v2`(auto→這 3 件落在 Delaunay v1 路徑)用在 Award「機器人拆件」
  的 3 個 **mesh 件(光暈/身體/左手)**,在「atlas region 去旋轉局部框」對照真實藝術家 mesh,
  **3 件全 overall_pass**:生成覆蓋率 IoU **0.988–0.993 ≥ 藝術家基準 0.968–0.980**,
  0 退化 / 0 孤兒 / 頂點數在預算內。端到端「件→mesh」對**真實生產標的**首次驗收通過。
- **信心**:高(對照真實生產 spine 的藝術家 mesh,apples-to-apples 同座標系;另含 v1 兩個 bug 的
  發現＋修復＋回歸驗證)。
- **階段**:第 2 階段 / S3↔S4 串接(里程碑:合成/單資產 → 真實生產件對照真值)。
- **工具**:`tools/mesh_gen/validate_against_award.py`(標準指令見末)。

## 1) 關鍵資料事實:Award mesh uvs 是 region-local、v-down

Award 的 mesh attachment(光暈 78v / 身體 98v / 左手 80v)`uvs` **不是 page-relative atlas UV**,
而是 **region 局部 [0,1]、v 向下**(與 `generate_mesh` 輸出 `u=x/W, v=y/H` 同慣例)。
驗證:把 artist uvs 直接 `(u*W, v*H)` 疊到 `atlas_crop.extract` 切出的 region 遮罩,
artist IoU = **0.968 / 0.979 / 0.976**(v-down);v-up 只有 0.44–0.61。

副產確認:光暈/身體在 atlas 為 **rotate=true**,artist mesh 仍對齊得這麼好 →
**`atlas_crop` 的 CW 去旋轉對 rotate=true 件正確**(再次以外部真值佐證 S4 的 CCW→CW 修正)。
這也讓 artist mesh 與生成 mesh 落在同一像素框,IoU 可直接對比(公平)。

## 2) 用真實標的揪出並修好 v1 兩個 bug(都在 `generate_mesh.py`)

光暈(大圓 halo,496×480,凹度低但輪廓平滑)初次 **FAIL**,暴露兩問題:

| Bug | 症狀 | 根因 | 修法 | 效果 |
|---|---|---|---|---|
| **孤兒內部頂點** | evaluate_mesh AC2c orphans=1 | `filter_triangles` 以重心剔除凹外三角,可能把某內部頂點的**所有**相鄰三角剔光 → 該點留在 vertices 卻無三角引用 | 新增 `prune_orphans()`:剔除 `index>=n_hull` 的未引用點並重索引(hull 一律保留以維持 hull-first 與外周) | orphans 1→0 |
| **大平滑輪廓取樣過疏** | 光暈 IoU 僅 0.929(< 基準 0.980) | hull epsilon = `epsilon_frac*peri`(純比例),周長越大絕對偏差越大 → 多邊形內縮 | `boundary_points` 加**絕對像素偏差上限** `eps=min(frac*peri, max_dev_px=2.0)` | IoU 0.929→0.992 |

> 與既有結論呼應:**IoU 由邊界取樣密度決定**(v2 是 `rows`,v1 是 hull epsilon)。
> `max_dev_px=2.0` 讓 hull 點數 56/37/36 ≈ 藝術家 78/40/42,保真度與件大小脫鉤。

## 3) deform 閘不適用(誠實標註)

這 5 件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform)→ **沒有真實位移場可轉移**。
依 RULES「不用未校準的合成 stress_field」,本驗收只做**靜態覆蓋率 + 拓樸合法性 + 頂點預算**。
(窗簾類「逐頂點 deform」件的耐變形已在 `s3-four-mesh-generalization.md` 用真實位移場驗過。)

## 4) 數據

| 件 | region | mode | gen 頂點/三角/hull | gen IoU | artist IoU | 通過 |
|---|---|---|---|---|---|---|
| 光暈 | 496×480 | delaunay-v1 | 90 / 122 / 56 | 0.9918 | 0.9795 | ✓ |
| 身體 | 267×299 | delaunay-v1 | 77 / 115 / 37 | 0.9925 | 0.9760 | ✓ |
| 左手 | 181×152 | delaunay-v1 | 61 / 84 / 36 | 0.9884 | 0.9681 | ✓ |

## 5) 回歸(確認 v1 改動無副作用)

- `validate_against_real.py --gen v1`(curtain_left):overall_pass、self_intersections=0 ✓
- `--gen v2`(curtain_left / curtain_right / shadow):全 overall_pass ✓
  (shadow2 與 shadow **共用同一 atlas region `image/shadow`**;以 `--name image/shadow2`
   呼叫會在 extract 找不到 region,屬呼叫端 region 名解析,非本次改動;mesh 生成同 shadow。)

## 可重現

```
python3 tools/mesh_gen/validate_against_award.py          # 3 件 overall_pass(exit 0)
python3 tools/mesh_gen/validate_against_real.py --gen v1  # 回歸:curtain_left v1
```

## 下一步

- **件→Spine JSON 組裝(SkelToJson)**:把已驗的慣例(`PSD名/圖層名` slot、size+2px、
  atlas ~0.70 縮放、mesh/region 分配)+ 本工具的生成 mesh 寫成端到端「件→Spine attachment」輸出工具。
- 或:S2 補圖閘 / 骨架閘(純 CPU 補齊 S2 樞紐)。
