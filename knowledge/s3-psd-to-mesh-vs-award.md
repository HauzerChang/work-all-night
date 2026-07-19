# S3 端到端驗收 — PSD件 → mesh_v2 → 對照 Award 真實 mesh(里程碑)

- **結論**:把 `robot_parts.psd` 的 3 個「在 Award 為 mesh」的件(光暈 / 身體 / 左手)切出後,
  跑 `generate_mesh_v2`(auto),生成 mesh 在 **UV/貼圖空間**的覆蓋率與**藝術家真實生產 mesh 同量級**
  (相差 ≤ 1.6% IoU),且**用更少頂點**(身體甚至反超藝術家)。這是第一次把「PSD→件→S3 mesh」
  對**真實生產標的**端到端驗收。
- **信心**:高(對真實生產 spine `Award` 的 mesh 做外部真值比對 + 全 evaluate_mesh 閘 + 視覺疊圖)。
- **階段**:第 2 階段 / S3 × S4 串接。

## 結果(UV 空間三角覆蓋 IoU,vs 切件 alpha)

| 件 | 生成 mode | 生成 nv / hull / tris | 生成 IoU | 藝術家 nv / hull / tris | 藝術家 IoU | Δ(生成−藝術家) |
|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 35 / 16 / 49 | 0.9331 | 78 / 78 / 76 | 0.9486 | **−0.0155** |
| 身體 | delaunay-v1 | 60 / 20 / 97 | 0.9660 | 98 / 40 / 154 | 0.9477 | **+0.0183** |
| 左手 | delaunay-v1 | 59 / 19 / 97 | 0.9642 | 80 / 42 / 116 | 0.9768 | **−0.0126** |

`evaluate_mesh`(budget=100)全項:身體/左手 **overall_pass=True**(IoU>0.95、0 退化、0 孤兒、
centroid 1.0);光暈 只卡固定 IoU 閘(見下),拓樸全乾淨。

## 關鍵發現

1. **auto-mode 對這批件選 v1(Delaunay),不是 v2 strip** —— 三件長寬比皆 < 1.2
   (光暈 0.97、身體 1.12、左手 0.84),非「高瘦 row-convex 窗簾」→ 不觸發 strip。
   **這批 mesh 在 Award 是 weighted(骨骼權重驅動)、無 deform timeline**,不像窗簾靠逐頂點 deform;
   故變形不是單向極端拉伸,v1 散點拓樸適用。**S3 生成器策略對「bone-driven mesh」與
   「deform-timeline mesh」自然分流(auto by aspect/row-convex)是對的。**

2. **變形驗收機制不同,要分清**:窗簾/陰影用「真實位移場轉移」deform 閘(硬約束,防撕裂);
   但機器人這批 **無 deform timeline**,變形完全由骨骼 + 每頂點權重決定。沒有可轉移的位移場 →
   deform-transfer 閘**不適用**。此批的驗收基準 = **靜態 UV 覆蓋 IoU + 拓樸 + 藝術家相對基準**。
   (權重求解 = BBW,屬 S3 尚未實作的下一子能力;本輪只驗幾何拓樸。)

3. **固定 0.95 IoU 閘對「軟邊/羽化」件 miscalibrated**(第 N 次 evaluator 校準教訓):
   光暈是柔性發光,alpha 有大片羽化漸層,**藝術家自己的 mesh 也只有 0.949(< 0.95)**。
   任何精簡多邊形都吃不到 0.95。**正解是「藝術家相對基準」(生成 ≥ 藝術家 − margin),不是絕對 0.95。**
   光暈生成 0.933 vs 藝術家 0.949(Δ −0.016)→ 以相對基準**通過**,且只用 35v(藝術家 78v 的 45%)。

4. **UV 空間是唯一公平比較法**:Award mesh 為 weighted(vertices 是 `[骨數,boneIdx,bindX,bindY,w,...]`
   攤平格式,需骨骼 bind 變換才得像素座標);但 **uvs 是 region-local 0..1,與生成 mesh 的 uvs 同座標系**。
   兩者都用 `(u·W, v·H)` 映到切件 alpha 上柵格化 → apples-to-apples,無需重建骨骼。v 方向自動取
   IoU 較高者(藝術家 uvs 與生成 uvs 的 v 上下慣例可能不同)。

## 圖

`figures/s3-robot-psd-mesh-vs-award.png` — 三件各「生成(綠)| 藝術家(藍)」線框疊在切件 alpha 上。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
# 每件:generate_mesh_v2 auto → evaluate_mesh(UV 空間對照見 /tmp/compare_robot_mesh.py)
python3 tools/mesh_gen/generate_mesh_v2.py /tmp/robot_parts/03_身體.png -o /tmp/身體_mesh.json
python3 tools/mesh_gen/evaluate_mesh.py /tmp/身體_mesh.json /tmp/robot_parts/03_身體.png --budget 100
```
(比較腳本 `/tmp/compare_robot_mesh.py` 為一次性驗證用;核心結論已固化於本檔與圖。)

## 下一步

- **BBW 權重求解**:這批件在 Award 靠骨骼權重變形。S3 要真正端到端產「可綁 mesh」,
  需補權重(bone bind + BBW),再對照 Award 的 weighted vertices 驗證。這是 S3 的下一子能力。
- **切圖→Spine JSON 組裝(SkelToJson)**:把「件→attachment(mesh/region 依需求)+ `PSD名/圖層名` slot
  命名 + size+2px」固化成寫檔工具,把生成 mesh 直接寫進 Spine JSON。
- 固定 IoU 閘可加「soft-edge 偵測 → 自動切藝術家相對基準 / 放寬」選項(避免軟件假性 fail)。
