# S3 端到端(PSD 件→mesh→對照 Award 生產 mesh)— 靜態覆蓋率驗收

- **結論**:把「PSD 件 → `generate_mesh_v2` → 對照真實生產 mesh」端到端跑到**第二個生產 spine
  `Award`** 的機器人 3 件(光暈/左手/身體),**靜態覆蓋率全數追平藝術家**(公平判準:對齊頂點預算後
  `coverage_iou ≥ 藝術家 − 0.015` 雜訊地板)。證實 S3 生成器不只對 `main_draw` 的窗簾/陰影通,
  對 blobby 機器人部件也達生產品質。
- **信心**:高。兩個覆蓋率評估器都跑過負對照有鑑別力;PSD 件 ⇄ atlas region 剪影 IoU 0.95–0.99
  證「輸入 == spine 用的同一素材」,端到端非拼湊。
- **階段**:第 2 階段 / S3(推廣到第二資產)。工具:`tools/mesh_gen/validate_award_static.py`。

## 數據(2026-07-31)

| 件 | PSD⇄atlas 剪影 IoU | 藝術家 | default(省) | 預算對齊 | 靜態通過 |
|---|---|---|---|---|---|
| 光暈 | 0.949 | 78v / 0.9795 | 37v / 0.9337 ✗雜訊外 | 103v / **0.9877** ✓ | ✅ |
| 左手 | 0.986 | 80v / 0.9681 | 59v / 0.9642 ✓雜訊內 | 63v / 0.9686 ✓ | ✅ |
| 身體 | 0.949 | 98v / 0.9760 | 60v / 0.9666 ✓雜訊內 | 63v / 0.9709 ✓ | ✅ |

## 關鍵發現

1. **覆蓋率是「輪廓取樣密度」界定的,不是拓樸缺陷**。光暈是柔邊 glow(單一輪廓、無孔洞,
   findContours=1 / interior_holes=0),default preset(`epsilon_frac=0.008`, hull 16)把 spiky 柔邊
   過度簡化 → 欠覆蓋 0.046。降 `epsilon_frac` 到 0.002 提到 89v→0.983,**在藝術家自己的頂點量級
   (78v)就追平/超越藝術家**。密度掃描:eps 0.008/0.004/0.002/0.0015/0.001 → nv 37/56/89/111/136,
   IoU 0.934/0.964/0.983/0.988/0.992,單調。
2. **緊實部件(左手/身體)default 就在雜訊地板內達標**,且**比藝術家更省**(59–60v vs 80–98v)。
   對這兩件加頂點幾乎不再提升覆蓋率(左手 59v→0.964,115v→0.963;plateaus)→ 殘差 <1% 是
   **三角化/柵格化雜訊地板**:直邊三角化無法完美貼柔邊,藝術家 mesh 自身也僅 0.968–0.980(非 1.0)。
   故 AC margin 設 **0.015**(> 雙合法三角化互差,< 光暈 default 的 0.046 真實欠覆蓋 → 具鑑別力)。
3. **公平判準 = 對齊頂點預算**。`gen_budget_matched`:在 `≤1.35×藝術家 nv` 內取覆蓋率最高的生成
   → 排除「default 偏省」對「能否追平藝術家」的干擾。省 vs 追平是兩個獨立故事,分開報。

## 重要邊界 / 尚未做(誠實記錄)

- **這 3 件在 `Award` 中無 deform timeline**(weighted mesh,純骨骼蒙皮驅動,頂點不做 mesh deform)。
  → **真實位移場轉移 deform 閘對它們 N/A**;strip 拓樸耐 deform 已於 `main_draw` 4 個會 deform 的
  mesh 驗過(`s3-four-mesh-generalization.md`)。此處只驗**靜態幾何**。
- **weighted / 骨綁未生成**:生成的是 unweighted mesh。要真正取代生產 mesh 還需 BBW 權重 + 骨綁定
  (S3 後段 / S5),本輪未做。生產價值(骨骼驅動變形)未端到端驗。
- 覆蓋率在各自像素空間量(生成在 PSD 件、藝術家在 atlas region);IoU scale-invariant,PSD⇄atlas
  剪影 IoU 高證同形,故可比。

## 評估器可信度(先驗,負對照)

- 生成用 `evaluate()`(rasterize **vertices**):左手 normal 0.9642 → 頂點內縮 75% 0.559 / jitter 0.774。✓
- 藝術家用 `artist_iou()`(rasterize **uvs**):左手 normal 0.9681 → uvs 內縮 70% 0.506。✓
  (注意:`evaluate` 只吃 vertices、不吃 uvs;負對照要打對欄位,否則假陰性。)

## 可重現指令

```
python3 tools/mesh_gen/validate_award_static.py   # all_static_pass=True, exit 0
```
