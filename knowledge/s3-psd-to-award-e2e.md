# S3 端到端:PSD 件 → generate_mesh_v2 → 對照 Award 真實 mesh(靜態驗收)

- **結論**:把 `robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手)切件 alpha 餵給 S3
  `generate_mesh_v2`,對照生產 spine `Award` 的藝術家 mesh 做**靜態覆蓋率 + 拓樸 + 頂點預算**,
  **3 件全 overall_pass**。生成器達到「藝術家覆蓋率同級 or 更好」且**頂點更精簡、拓樸乾淨**。
- **信心**:高(真實生產標的 + 藝術家 ground truth + 評估器可信度自檢 + 負對照鑑別力)。
- **階段**:第 2 階段 / S3×S4 串接(端到端里程碑:PSD→件→mesh 對真實標的)。
- **工具**:`tools/mesh_gen/compare_psd_to_award.py`(標準指令,見底部)。

## 量化結果

| 件 | gen 模式 | gen 頂點(hull) | gen IoU | 藝術家 頂點(hull) | 藝術家 baseline IoU | 頂點比 gen/artist | overall |
|---|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 35 (16) | 0.933 | 78 (78) | 0.949 | 0.45 | ✅ PASS |
| 身體 | delaunay-v1 | 60 (20) | 0.966 | 98 (40) | 0.948 | 0.61 | ✅ PASS |
| 左手 | delaunay-v1 | 59 (19) | 0.964 | 80 (42) | 0.977 | 0.74 | ✅ PASS |

(coverage AC:gen IoU ≥ 藝術家 baseline − 0.02;topology:0 degenerate / 0 orphan / format ok;budget ≤ 64。)

## 關鍵發現

1. **模式選擇(regime)確立**:`generate_mesh_v2` auto 對這 3 件(長寬比 0.84~1.12,非高瘦)
   **全數退回 v1 Delaunay**。與曲簾(strip)互補 →
   **strip 給 deform-heavy 直條件;Delaunay 給剛體 / 骨骼權重的團塊件**。合理:
   這 5 件在 Award **無 deform timeline**(靠骨骼/權重變形),deform 閘 N/A,靜態覆蓋率 + 拓樸即為對的收斂目標。

2. **解掉 UV frame 懸案(s4 doc 曾標『Award mesh uvs 需轉 region 局部』)**:
   評估器可信度自檢同時算兩種詮釋 —— `region_local`(uvs 直接 ×W,H)與 `minmax_norm`(先 min-max 正規化)。
   **region_local 對 3 件全高(0.949/0.948/0.977)= 正確詮釋**;minmax_norm 對身體只有 0.639
   (因藝術家 mesh 未貼滿 region bbox,身體 u 僅到 0.759)。→ **Award mesh uvs 本就是 region-local 0..1**,
   直接 ×(W,H) 即可,不需再轉。曲簾(main_draw)uvs 也是 region-local 0..1,一致。

3. **負對照(cross-mask IoU 矩陣,證明閘有鑑別力非恆過)**:
   對角(正確配對)0.949/0.948/0.977 vs 非對角(錯件)0.48~0.58,分離約 0.4 → 評估器可信。

4. **光暈是純 hull ring mesh**(藝術家 78 頂點全在 hull、0 內部);生成器給填滿 Delaunay 團塊(35 頂點)。
   **靜態覆蓋率兩者皆過**,但藝術家的拓樸選擇(環狀)是為了發光邊緣柔性;若日後光暈需 deform,
   應改走「環狀 / 中空」拓樸(目前生成器不產環)。記為 S3 待強化項,非本 chunk failure。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts   # 切件
PYTHONPATH=tools/mesh_gen python3 tools/mesh_gen/compare_psd_to_award.py          # 端到端 AC(exit 0 = all_pass)
```

## 下一步(見 STATE.md)

- 把「件→Spine attachment」慣例(`PSD名/圖層名`、mesh/region 分配、+2px padding、region-local uvs)
  固化成 SkelToJson 組裝工具,端到端產 Spine JSON(候選 #2)。
- S3 光暈環狀 / 中空拓樸能力(若後續需求 glow deform)。
