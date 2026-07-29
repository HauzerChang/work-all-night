# 端到端「PSD 件 → S3 生成 mesh → 對照 Award 真實 mesh」(里程碑)

- **結論**:把 `robot_parts.psd` 的 3 個 mesh 件(光暈 / 身體 / 左手)切件 alpha 餵進 S3
  生成器,產出的 mesh 對照生產 spine `Award` 的**藝術家真實 mesh**,靜態覆蓋率 IoU
  **3 件全數達標**(≥ 藝術家自身基準 − 0.02),且格式/預算/無孤兒/無退化全過。
  首次把 S4(PSD 切件)→ S3(生成 mesh)串成端到端,並對**真實生產標的**驗收。
- **信心**:高(對真實生產 mesh 交叉比對 + 負對照確認閘鑑別力 + 尺度抵消設計)。
- **階段**:第 2 階段 / S3+S4 端到端。

## 結果(gen=v2 auto)

| 件 | slot | gen 頂點/三角/hull | 生成模式 | gen IoU | 藝術家基準 | mesh↔mesh 一致 | 判定 |
|---|---|---|---|---|---|---|---|
| 光暈 | 機器人拆件/光暈 | 35 / 49 / 16 | delaunay-v1 | 0.933 | 0.949 | 0.918 | ✅ |
| 身體 | 機器人拆件/身體 | 60 / 97 / 20 | delaunay-v1 | **0.966** | 0.948 | 0.928 | ✅(勝基準) |
| 左手 | 機器人拆件/左手 | 59 / 97 / 19 | delaunay-v1 | 0.964 | 0.977 | 0.957 | ✅ |

- 藝術家 mesh:光暈 78v/76t/hull78(**純邊界環,無內部點**)、身體 98v/154t/hull40、左手 80v/116t/hull42,**皆 weighted**。
- 生成 mesh 更精簡(35–60v vs 78–98v)卻達到相當覆蓋率;身體甚至略勝藝術家基準。

## 關鍵發現

1. **v2 `auto` 正確路由**:這 3 件長寬比 < 1.2(近方/塊狀,非高瘦條狀)→ auto 全走 **v1 Delaunay**,
   不套 strip。這是對的:strip 是為「大單向拉伸的 deform-bearing 件(窗簾/陰影)」設計;
   Award 這 3 件是 **weighted mesh 且無 deform timeline**(靠骨骼權重變形,非逐頂點 deform),
   v1 的 deform-fragility 疑慮在此不適用,靜態覆蓋才是判準,而 v1 覆蓋良好。
2. **deform 轉移閘對這 3 件 N/A**:Award 中 `機器人拆件/*` 無任何 deform timeline
   (實測 anims 掃描 0 命中),故沒有真實位移場可轉移。閘只驗**靜態覆蓋率 + 拓樸格式**,
   並在報告中明記 `deform_gate: N/A`,避免誤用未校準的合成壓力(重蹈 stress_field 覆轍)。
3. **Award mesh uvs = region-local 0..1**(實測:光暈 x∈[0.012,0.99]、身體 x∈[0,0.759]…),
   與 main_draw 同慣例 → **推翻 s4 筆記中「Award uvs 為 atlas-global,需轉 region 局部」的過度保守假設**。
   Spine 3.8 JSON 的 mesh uvs 本就存 region-local(載入時才由 atlas region 映射到貼圖座標)。
4. **尺度自動抵消**:PSD 切件(如光暈 706×683)與 atlas region(~0.70 縮小)雖尺度不同,
   但兩邊都以 uv 分數 × 同一遮罩尺寸光柵化 → 比對與絕對尺度無關,無需先對齊 scale。

## 評估器可信度(負對照,先驗後判)

- **收縮頂點**(向重心 ×0.85 / ×0.70):身體 IoU 0.966 → **0.709 / 0.483**(皆 fail < 0.928)。
- **錯 slot**(光暈藝術家 mesh 疊到身體遮罩):IoU **0.488**(空間特異性確認)。
- ⚠️ **踩到閘自身的座標來源坑**:`evaluate_mesh.AC1_iou` 用的是 `mesh["vertices"]`(置中座標),
  **不是 uvs**。初版負對照誤改 uvs → IoU 不變(假性「無鑑別力」);改corrupt `vertices` 才正確觸發。
  教訓:驗閘的鑑別力時,要corrupt「閘實際讀的那個欄位」。

## 產出 / 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts   # 切 5 件
for s in "00_光暈.png:機器人拆件/光暈" "03_身體.png:機器人拆件/身體" "04_左手.png:機器人拆件/左手"; do
  python3 tools/mesh_gen/validate_psd_to_award.py "/tmp/robot_parts/${s%%:*}" --slot "${s##*:}" --gen v2
done   # 3 件 overall_pass=True
```

新增工具:`tools/mesh_gen/validate_psd_to_award.py`(PSD件→生成mesh→Award真值靜態覆蓋 AC)。

## 下一步候選

- **切件 → Spine JSON 組裝(SkelToJson)**:把已驗證的慣例(`PSD名/圖層名`、+2px padding、
  mesh vs region 分配、uvs region-local、生成 mesh 頂點格式)固化成工具,端到端產出可載入的 Spine JSON。
- 加權重(BBW)讓生成 mesh 也能像 Award 一樣靠骨骼變形(目前生成的是 unweighted)。
