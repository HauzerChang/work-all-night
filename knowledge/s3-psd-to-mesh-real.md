# S3 端到端 — PSD 件 → 生成 mesh → 對照真實生產 mesh(Award)

- **結論**:把 S3 mesh 生成器接到 S4 切圖輸出,對 `robot_parts.psd` 的 3 個「在生產 spine `Award`
  裡是 mesh」的件(光暈 / 身體 / 左手)跑 `generate_mesh_v2`,與 **Award 真實藝術家 mesh(ground truth)**
  做靜態覆蓋率對照 → **3 件全 `overall_pass`**。這是「PSD → 件 → mesh」對真實生產標的的**端到端驗收**。
- **信心**:高(對真實生產 mesh 交叉比對 + 雙向負對照確認鑑別力)。
- **階段**:第 2 階段 / S3 × S4 串接(里程碑:從單一資產 main_draw → 跨資產真實生產標的)。

## 為何是「靜態覆蓋率」而非 deform 閘(關鍵區別)

這 3 件在 Award 是 **weighted / 骨骼驅動 mesh,且 9→12 支動畫全部 0 deform timeline**
(已核對 `animations[*].deform`,無任何 `機器人*` slot)。它們靠**骨骼 + 權重**變形,不是
逐頂點 deform。故:

- **不套 deform 閘**(`transfer_deform_check` 需 deform 位移場,這裡沒有;骨骼/權重變形不在 S3 範疇)。
- 改用**靜態覆蓋率**對照真值。這與 4 個窗簾/陰影(unweighted + deform-bearing)是**不同 mesh 類別**,
  正好測 S3 對「blob 型 weighted mesh」的泛化。

## 結果(`validate_psd_to_mesh.py`,margin=0.02)

| 件 | 生成 mode | 生成 v/hull/tri | 藝術家 v/hull/tri | 生成覆蓋 IoU | 藝術家基準 | gen↔art IoU | pass |
|---|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 35 / 16 / 49 | 78 / **78** / 76 | 0.933 | 0.949 | 0.918 | ✅ |
| 身體 | delaunay-v1 | 60 / 20 / 97 | 98 / 40 / 154 | **0.966** | 0.948 | 0.928 | ✅ |
| 左手 | delaunay-v1 | 59 / 19 / 97 | 80 / 42 / 116 | 0.964 | 0.977 | 0.957 | ✅ |

- **三件都走 v1(散點 Delaunay)**:aspect 皆 < 1.2(0.97/1.12/0.84)且非高瘦 → v2 auto 正確回退 v1。
  → 印證分工:**v2 strip 給高瘦、單向拉伸的 deform mesh(窗簾);v1 Delaunay 給 blob 型件**。
  這裡沒有 deform 撕裂風險(骨骼驅動),v1 的靜態覆蓋率就夠且頂點更省。
- **生成頂點數全 < 藝術家**(35<78、60<98、59<80):我方拓樸更精簡仍達同等覆蓋。
- **藝術家覆蓋率也不是 1.0(~0.95)**:三角化多邊形 vs 羽化 alpha 邊緣的必然殘差 → 用「對齊藝術家」
  而非武斷 0.95 當基準是對的(延續 curtain 教訓)。
- 光暈藝術家 **hull=78=全頂點**(純邊界環 fan):美術對光暈只描一圈細邊界、無內部點;
  我方 v1 有內部點但邊界較粗(hull 16)→ 覆蓋略低仍在 margin 內。

## 評估器可信度(先驗 + 負對照)

- **方向敏感度**:各件生成覆蓋 vs「水平翻轉遮罩」IoU 掉 0.19~0.57(光暈 .93→.49、身體 .97→.40、
  左手 .96→.77)→ 閘對錯位/翻面敏感。
- **錯配件**:光暈生成 mesh vs 身體藝術家 mesh IoU=0.496 vs 正確配對 0.918 → 明顯區分。
- **gen↔art IoU 0.92~0.96 本身即一致性檢查**:PSD 件與 Award mesh 落在同一區域,無 flip/座標系錯位
  (呼應 s4 texture alpha-IoU 0.92~0.99「同一素材」結論)。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd     # 產 psd_parts/*.png
python3 tools/mesh_gen/validate_psd_to_mesh.py                 # 3 件 overall_pass
```
圖:`knowledge/figures/psd-to-mesh-vs-award.png`(綠=生成 v1,紅=藝術家真實 mesh,灰=件 alpha)。

## 意義 / 下一步

- **S3 + S4 端到端首次對「真實生產標的」閉環**:切件不再只重組還原,而是驅動 mesh 生成並被真值背書。
- 剩「件 → Spine JSON attachment 組裝(SkelToJson)」即可產出可直接載入的 spine mesh
  (命名 `PSD名/圖層名`、size+2px、mesh vs region 分配已在 s4 doc 固化)。← 建議下一個 chunk。
- weighted mesh 的**權重(BBW)生成**尚未做;目前只驗拓樸/覆蓋。骨骼驅動變形品質需 S5 骨架後才能整體驗。
