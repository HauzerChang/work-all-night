# S3 端到端「PSD件 → mesh」對真實生產 mesh 驗收(Award 機器人)

- **結論**:端到端「PSD 切件 → `generate_mesh_v2` → 對照 Award 真實藝術家 mesh」**production-critical 全過(3/3)**。
  自動生成的 mesh 以**約一半頂點數**達到(甚至超過)藝術家 mesh 的 alpha 覆蓋率。里程碑:S3+S4 串成端到端、對真實生產標的驗收。
- **依據**:新工具 `tools/mesh_gen/validate_psd_to_mesh.py`;對 `robot_parts.psd` 的 3 個 mesh 件
  (光暈/身體/左手,對應 Award slot `機器人拆件/<圖層名>`)量化對照。
- **信心**:高(有真實藝術家 mesh 當 ground truth;評估器先以藝術家真值校準過)。
- **階段**:第 2 階段(能力鍛鍊)— S3 mesh × S4 PSD 端到端。

## 量化結果(2026-08-16)

| 件 | 生成 (v1 Delaunay) | 藝術家真值 | 覆蓋率 gen / artist | production_pass |
|---|---|---|---|---|
| 光暈 | 50v / 79t / hull15 | 78v / 76t / hull78 | 0.9289 / 0.9232 | ✅ |
| 身體 | 38v / 53t / hull20 | 98v / 154t / hull40 | 0.9653 / 0.9467 | ✅ |
| 左手 | 41v / 61t / hull19 | 80v / 116t / hull42 | 0.9624 / 0.9661 | ✅ |

- production-critical AC = **alpha 覆蓋率(≥ 藝術家基準 − 0.02)+ Spine 格式(unweighted / hull 合法 / 0 退化 / 0 孤兒 / 三角索引界內)**。
- 這 3 件在 Award **無 deform timeline**(靠骨骼剛體動,見 log 2026-06-26-005),故覆蓋率+格式即production-critical。

## 座標對齊(可重用方法)

1. **Award mesh 的 uvs 是 region-local(0..1)**(實測:光暈/身體/左手 uv 皆近乎鋪滿 0..1;非 page-normalized)。
   main_draw 的 mesh uvs 同為 region-local → `artist_iou(uv×W, uv×H)` 對兩資產皆正確。
2. **attachment.width/height = PSD 件尺寸 + 2px**(atlas padding,實測 6/6 邊皆 +1px 對稱):
   光暈 706×683→att 708×685、身體 379×425→381×427、左手 257×215→259×217。
3. **對齊法**:把 PSD 件 bbox alpha **置中貼進 (attW×attH) 畫布** → 藝術家 mesh(uv×att)與在該畫布生成的 mesh
   落在同一像素座標系 → IoU/拓樸可公平對照。`psd_slice` 用 `layer.topil()` 產 bbox-cropped 件,正好可用。

## 修到的兩個真實缺陷

### 1. 生成器孤兒頂點 bug(修好)
- `generate_mesh.py`(v1)`filter_triangles` 濾掉「重心在 mask 外」的凹形三角後,**其獨占頂點變孤兒**
  (光暈 5、身體 1),違反 Spine 格式清潔度(evaluate_mesh AC2c)。
- **修法**:新增 `compact_vertices()`:丟掉未被任何三角引用的頂點、保序重編索引;
  因保序壓縮,hull 頂點(原 index < n_hull)自然仍排最前,新 hull = 存活 hull 頂點數。
- 修後 3 件全 0 孤兒;main_draw 4 mesh(v1 curtain_left + v2 全 4)回歸全過,無退化。

### 2. deform 韌性 gate 的**幅度未校準**(第 4 次同類教訓,已校正)
- 這 3 件無原生 deform → 用 main_draw `curtain_left` 的**真實最大位移場**經 UV 轉移當韌性探針
  (RULES:用真實位移場、不可用未校準 `stress_field`)。
- **陷阱**:curtain 的位移場是**絕對像素(max 314px)**;直接施於小件(左手 259px 寬)= >120% 拉伸,
  **連藝術家真值 mesh 都撕裂** → gate 在該幅度下不可信。
- **校正**:把位移場**依目標件寬高等比縮放**(fx×attW/curtainW, fy×attH/curtainH),讓「相對 warp」不變
  (≈ 佔件尺寸 90%,即 curtain close 動畫的真實極端幅度)。校正後**藝術家真值在 3 件全 clean → gate 可信**。
- 教訓再確認:**真實位移場 ≠ 自動可轉移**;跨件尺寸轉移必須正規化幅度,否則重演 miscalibration。

## 韌性探針的鑑別結果(額外,非 milestone 判定)

校準後 gate 對藝術家真值全 clean,且**能鑑別**:在 ~90% 尺寸的極端 warp 下
- 身體 / 左手:生成 mesh 與藝術家 mesh 皆 clean。
- **光暈:生成 mesh 自交(6 self-int + 1 flip),藝術家 mesh clean**。
  光暈是近正方形 blob(aspect≈0.97)→ 落 v1 Delaunay(strip 只吃 aspect≥1.2 的高瘦件);
  內部散點在強剪切下互穿。藝術家用 **78 頂點全在 hull 的邊界扇形**分散變形 → 耐撐。
- 這重申先前 S3 結論:**邊界跟隨/strip 拓樸 > 內部 Delaunay 散點**(強單向拉伸下)。
  但光暈實際 deform=0,此為 out-of-envelope 探針,故單列不併入 production 判定。

## 後續候選

- **blob 專用生成模式**(aspect<1.2 的圓形/塊狀件):邊界密集扇形(仿藝術家光暈)以提升耐變形,
  補上目前 v1 對 blob 的韌性缺口。屬新生成能力,獨立 chunk。
- 有 deform 的生產 mesh 若之後拿到,可做「原生位移場」保真對照(非轉移探針)。
