# S3 端到端驗證:PSD件 → 生成 mesh → 對照 Award 生產真值

> **結論**:S3 生成器(v2 auto→v1 Delaunay)在真實生產件上通過**靜態覆蓋**對照 —
> 對 Award 三個機器人 mesh 件,預設參數即以 **2.3× 更少頂點**全數通過絕對閘(IoU≥0.90);
> 調 `epsilon_frac=0.004` 後三件 **IoU 全 ≥ 藝術家且頂點數仍 ≤ 藝術家**。
> **但**:這三件是 **weighted 且無 deform timeline** 的 mesh → S3 的變形閘(real_deform_field)**不適用**,
> 只驗到靜態覆蓋/拓樸;weighted(BBW 權重)仍是 S3 未建能力。
> 信心:高(對照真值 = 生產 spine 的實際 mesh;UV 慣例經藝術家覆蓋 IoU 自洽確認)。相關:S3 / S4。

## 做了什麼

`robot_parts.psd` 的三個「在 Award 中為 mesh」的圖層(光暈 / 左手 / 身體)→ 抽出 alpha 件 →
`generate_mesh_v2.generate` 產 mesh → `evaluate_mesh` 量靜態 AC;同時把 Award **藝術家 mesh** 的
`uvs`(region-local 0..1)× 件尺寸光柵化成覆蓋 mask,量藝術家 IoU 當**同尺度基準**。

三件長寬比皆 <1.2(blob 狀,非高瘦窗簾)→ v2 auto **回退 v1 Delaunay**(strip 不適用,符合預期)。

## 量化結果(對 PSD 件 alpha 的 IoU)

| 件 | 我的(預設 eps=0.008) | 藝術家 | eps=0.004 | 藝術家頂點 |
|---|---|---|---|---|
| 光暈 | 35v / IoU 0.933 | 78v / 0.949 | **44v / 0.961 ✅≥art** | 78(hull=78,**純外周無內點**)|
| 左手 | 59v / IoU 0.964 | 80v / 0.977 | **70v / 0.980 ✅≥art** | 80(hull 42)|
| 身體 | 60v / IoU 0.966 | 98v / 0.948 | **69v / 0.983 ✅≥art** | 98(hull 40)|

- 預設參數:三件皆過絕對靜態閘(IoU≥0.90),頂點數 35/59/60 vs 藝術家 78/80/98(省 ~2.3×);
  身體我方 IoU 已**勝過**藝術家。光暈/左手 IoU 低藝術家 1.3–1.6 點(藝術家頂點多一倍 → 邊界更貼)。
- **IoU 差距純由邊界密度(頂點預算)決定**:`epsilon_frac` 掃描(0.008→0.001)IoU 單調升(光暈 0.933→0.992),
  eps=0.004 即三件全 ≥ 藝術家且頂點數仍 ≤ 藝術家 → **差距是可調的預算選擇,不是能力缺口**。

## 關鍵發現 / 教訓

1. **UV 慣例確認**:Award mesh `uvs` 為 **region-local 0..1、v 向下**;× 件尺寸直接對齊 PSD 件 alpha
   (藝術家覆蓋 IoU 0.95~0.98 高且合理 → 自洽驗證慣例正確,無需 y-flip)。
2. **機器人 mesh 是 weighted 且 9…12 支動畫全無 deform timeline** → 靠 **骨骼 skinning**(權重)驅動,
   不是頂點 deform。故 S3 的 `real_deform_field`/`transfer_deform_check` 閘在此**不適用**;
   本輪只驗靜態。**新缺口浮現**:S3 目前只產 unweighted mesh,weighted/BBW 權重尚未建(路線圖 S3 內含,待做)。
3. **不同設計哲學都有效**:藝術家光暈用「純外周多邊形」(hull=verts=78,零內點)貼柔和輻射光暈;
   我的 v1 會加內點(對近凸 blob 幫助有限)。兩者靜態皆達標;差異在拓樸風格非對錯。
4. **v2 auto 分流正確**:blob 件(aspect<1.2)自動走 v1 Delaunay,窗簾(高瘦)走 strip —— 分流邏輯在真實件上成立。

## 產出

- `scratch_robot/compare.py`(對照腳本;非長期工具,置於 scratch)
- `knowledge/figures/s3-robot-vs-award.png`(三件 藝術家[橘] vs 我方[綠] 線框疊 alpha,eps=0.004)

## 下一步候選

- **端到端固化**:把「PSD件 → generate_mesh → 命名慣例 `機器人拆件/<層>` → 寫 Spine attachment(size+2px)」
  串成 SkelToJson 工具(STATE 候選 #2),用本輪參數(blob 用 eps≈0.004 平衡點)。
- **weighted mesh(BBW)**:補 S3 缺口;需骨架/權重 → 與 S5 相關,屬較大工作,建議先確認需求再開。
