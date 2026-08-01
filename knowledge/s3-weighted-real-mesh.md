# S3 對真實生產 weighted mesh 驗收(機器人拆件)— 端到端 PSD→件→mesh vs 真實 mesh

- **結論**:S3 v2 生成器對真實生產的 **weighted、骨骼驅動 mesh** 中「硬邊實心件」通用良好
  (左手/身體端到端過關,覆蓋不輸藝術家、頂點僅 0.6×);但對「軟邊放射狀光暈」不通用
  (光暈 fail),已定位根因並找到可行修法方向。
- **信心**:高(有藝術家真值逐件比對;PSD 路徑與 atlas 路徑獨立一致)。
- **相關階段**:第 2 階段 S3(mesh 生成器)× S4(PSD 切件),端到端串接。
- **日期**:2026-08-01

## 重大體制發現:weighted/骨驅 ≠ unweighted/deform 驅

Award 的 `機器人拆件/光暈`、`/左手`、`/身體` 三個 mesh 全部是 **weighted**
(`vertices.length != uvs.length`),且**在全部 12 支動畫裡都沒有 deform timeline** →
它們靠骨骼 skinning 剛性/加權移動,**不做逐頂點 deform**。

因此對這類 mesh,窗簾時代的關鍵閘「deform 耐受(0 自交/翻面)」**不適用**
(`transfer_deform_check` 會因無 deform 場而報 `different number of values and points`,
非 bug 而是 N/A)。正確驗證體制改為:

| 體制 | 代表件 | 驅動 | 關鍵閘 |
|---|---|---|---|
| deform 驅動(unweighted) | 窗簾/陰影 | deform timeline 逐頂點 | **deform 耐受**(單軸大拉伸不自交) |
| 骨骼驅動(weighted) | 機器人拆件 | bone skinning | **覆蓋保真 + 頂點經濟**(deform 閘 N/A) |

→ 新工具 `tools/mesh_gen/validate_weighted_real.py`:atlas 切件(derotate)→ 生成 →
靜態 IoU vs mask、藝術家 mesh 覆蓋 IoU baseline、頂點經濟比;deform 閘明確標 N/A。

## 端到端結果(標準指令,見文末)

| 件 | 模式 | 生成 IoU | 藝術家覆蓋 IoU | Δ | 生成/藝術家頂點 | overall |
|---|---|---|---|---|---|---|
| 左手 | delaunay-v1 | 0.960 | 0.968 | −0.008 | 48 / 80 (0.60×) | **PASS** |
| 身體 | delaunay-v1 | 0.968 | 0.976 | −0.008 | 61 / 98 (0.62×) | **PASS** |
| 光暈 | delaunay-v1 | 0.929 | 0.980 | −0.050 | 54 / 78 (0.69×) | **FAIL** |

- **左手/身體**:覆蓋僅落後藝術家 0.008,且只用 0.6× 頂點 → S3 對硬邊實心生產件通用達標。
- **PSD 路徑交叉驗證**(從 `robot_parts.psd` 圖層切件 alpha 再生成):左手 IoU 0.964、
  身體 0.967、光暈 0.934 —— 與 atlas 路徑各自吻合(±0.006)。
  → **端到端「PSD→件→mesh」對真實生產標的閉環成立**(兩條獨立來源殊途同歸)。

## 光暈為何 fail —— 根因已定位

- 光暈 alpha **31% 為羽化半透明**(`0<a<255` 佔 a>10 的 0.309);硬門檻切出的邊界破碎。
- 失敗兩點:
  1. `AC2c_orphans=1`:硬門檻(127)把最外圈微弱光暈切成孤島。
     **修法可行**:門檻降到 10 → orphans=0(已實測)。morphological close **無效甚至更糟**。
  2. `AC1_iou=0.929`:Canny 散點內部佈局的外殼**填不滿放射狀光暈**(藝術家用更寬鬆的環狀外框達 0.98)。
- **拓樸策略實驗**(對光暈 thr=10 mask):
  - 凸包(convexHull, 38v):IoU **0.794**(過度外擴,光暈有凹陷)。
  - `approxPolyDP` eps=0.02 / 0.01 / 0.005 → 10v/12v/21v,IoU 0.896 / 0.918 / **0.966**。
  - → **中度簡化的外輪廓(eps≈0.005, 21 邊界點)即達 0.966,逼近藝術家 0.98**。

## 可推廣結論:**件的形狀類別決定拓樸策略**(與窗簾發現同源)

| 形狀類別 | 特徵 | 最佳拓樸 | 依據 |
|---|---|---|---|
| 高瘦、單軸拉伸 | 窗簾 | **vertical strip** | s3-four-mesh-generalization |
| 硬邊實心 | 左手/身體 | **Canny 散點 Delaunay(v1/auto)** | 本篇(0.96–0.97 過關) |
| 軟邊放射狀 | 光暈 | **低門檻 + 外輪廓 approxPolyDP 邊界(非散點)** | 本篇(散點 0.93→輪廓 0.966) |

散點法對硬邊實心通用;對軟邊光暈需切換到「邊界主導」拓樸(和窗簾 strip 一樣是邊界主導)。

## 下一個 bounded chunk 候選

1. **給 v2 加 `mode=radial/contour`**:軟 alpha 前處理(門檻 10 + 去孤島)+ 外輪廓
   `approxPolyDP`(eps≈0.005)為主 hull + 少量內點 → 目標光暈 IoU ≥ 0.96、orphans=0。
   驗收沿用 `validate_weighted_real.py`(光暈轉 PASS 即收斂)。
   `mode=auto` 偵測:`soft_edge_fraction > 0.25` 且近放射狀 → radial。
2. 把三類拓樸的 auto 偵測(高瘦→strip、軟邊→radial、其餘→scatter)整併進 `generate_mesh_v2`。

## 標準指令

```
python3 tools/mesh_gen/validate_weighted_real.py \
  --skeleton assets/Award.json --atlas assets/Award.atlas --png assets/Award.png \
  --psd assets/robot_parts.psd --tmp <tmpdir>
# exit 0 = 三件全 overall_pass;目前 2/3(光暈待 radial 模式)。
```
