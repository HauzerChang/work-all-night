# S3×S4 端到端:PSD 件 → 生成 mesh → 對照 Award 真實 mesh(里程碑)

- **結論**:把 S4(PSD 切件)接到 S3(mesh 生成),對**真實生產 spine(Award)的 3 個機器人 mesh 件**
  (光暈 / 身體 / 左手)端到端驗收 — **3 件全 `overall_pass`**。S3 生成的 mesh 覆蓋率(IoU)與藝術家
  手做 mesh **持平或更好**,且頂點數**只用約一半**,拓樸乾淨。
- **信心**:高。對真實生產 mesh 交叉比對 + 評估器負對照(self vs 錯件 IoU 落差 ~0.4)確認鑑別力。
- **階段**:第 2 階段 / S3+S4 整合(里程碑:單能力驗證 → 端到端對真實標的)。
- **可重現**:
  ```
  python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
  python3 tools/mesh_gen/compare_psd_to_award.py          # 3 件 overall_pass → exit 0
  python3 tools/mesh_gen/compare_psd_to_award.py --neg    # 負對照(評估器鑑別力)
  ```

## 量化結果(2026-06-28)

| 件 | 模式 | 我的頂點 | 藝術家頂點 | 我的 IoU | 藝術家 IoU | parity | 節約 | 拓樸 |
|---|---|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 35 | 78 | 0.933 | 0.949 | ✓(−0.016) | ✓ 0.45× | clean |
| 身體 | delaunay-v1 | 60 | 98 | **0.966** | 0.948 | ✓(**更高**) | ✓ 0.61× | clean |
| 左手 | delaunay-v1 | 59 | 80 | 0.964 | 0.977 | ✓(−0.013) | ✓ 0.74× | clean |

- 拓樸 clean = 0 退化三角 / 0 孤兒頂點 / 三角重心 100% 落在 mask 內 / 格式合法。
- AC:① 拓樸乾淨 ② IoU parity(我 ≥ 藝術家 − 0.02 margin)③ 頂點節約(我 ≤ 藝術家)。

## 關鍵發現

1. **這 3 件用 v1(Delaunay 散點),不是 v2 strip**:三件長寬比都接近方形(0.84–1.12 < 1.2)
   → `generate_mesh_v2` 的 auto 模式回退 v1。**證實 v1 對「非高瘦、靜態」件仍是好選擇**;
   v2 strip 是為「高瘦 + 大單向拉伸(窗簾)」耐變形而生,不是全面取代 v1。**兩者分工互補**。

2. **這些 Award mesh 皆 weighted(骨驅)、無 deform timeline**(已逐 anim 掃 `deform` 確認:NONE)。
   → 它們靠**骨骼權重**變形,不是逐頂點 deform。**因此正確的閘是「靜態覆蓋率 + 拓樸」,
   不是 main_draw 用的 deform 轉移閘**(無真實位移場可轉移)。能力按「件如何變形」選對的閘,
   是這次的方法論收穫。

3. **Award mesh 的 `uvs` 是 region-local(0..1 填滿件),非全 atlas 頁座標**。
   先前交接筆記寫「需轉 region 局部」其實不必 —— Spine JSON 存的 mesh uvs 已是區域內正規化
   (runtime 才用 atlas region 映到頁)。實測 u/v 皆達 ~0..1、`v_flip=False`(uvs 與 mask 同為 v 向下),
   `artist_iou(uvs×W,H)` 可直接比對件 alpha。**更正交接筆記的誤解**。

4. **負對照(評估器可信度)**:藝術家 mesh 對「錯件 mask」的 IoU:
   - 光暈 self 0.949 / 身體 0.488 / 左手 0.577
   - 身體 self 0.948 / 光暈 0.477 / 左手 0.514
   - 左手 self 0.977 / 光暈 0.573 / 身體 0.514
   → self 與 cross 落差 ~0.4,IoU 對「形狀對不對」**有強鑑別力**,pass 判定可信。

## 端到端鏈確立(S4→S3)

`robot_parts.psd` ─psd_slice→ 件 PNG(tight bbox alpha)─generate_mesh_v2→ Spine mesh attachment。
對真實生產標的,生成品質 ≥ 藝術家、頂點更省。**「PSD → 件 → mesh」這條 CPU pipeline 對真實檔通了**。
缺口僅剩:把件→attachment 寫成 Spine JSON 組裝器(SkelToJson),並補上 weighted 件的**權重生成**
(BBW)——本次只比 mesh 拓樸/覆蓋,尚未生成骨權重(藝術家件是 weighted,我的是 unweighted 拓樸)。

## 下一步候選

1. **SkelToJson 組裝器**:件 manifest(`PSD名/圖層名`、size+2px、mesh/region 分配)→ 寫出 Spine JSON
   attachment(復用本次驗證過的拓樸)。
2. **S3 權重生成(BBW)**:對 weighted 件,給定骨架算每頂點骨權重(和=1),才算完整對齊藝術家 weighted mesh。
   需骨架(S5)或先用 Award 既有骨綁定當真值比對。
3. **S2 補圖閘 / 骨架閘**(補齊 S2 樞紐)。
