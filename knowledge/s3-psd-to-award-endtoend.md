# S3+S4 端到端驗收 — PSD 件 → 生成 mesh → 對照 Award 真實藝術家 mesh

- **結論**:把 S4(PSD 切件)串上 S3(mesh 生成器),對 `robot_parts.psd` 的 3 個 mesh 件
  (光暈/左手/身體 —— 在生產 spine `Award` 中確為 mesh),端到端跑「PSD→件→`generate_mesh_v2`」,
  生成 mesh 對真實藝術家 mesh 達成**覆蓋率(IoU)平價**,且用**更少頂點**、拓樸全乾淨。
  **3 件全 `overall_pass`**。這是首次把 S3 生成器對「真實生產藝術家 mesh」ground truth 做端到端驗收。
- **信心**:高(真實生產 PSD + 真實 spine mesh ground truth + 拓樸閘 + 覆蓋率基準對照)。
- **階段**:第 2 階段 / S3×S4 整合(STATE 候選 #1,里程碑)。
- **可重現**:`python3 tools/mesh_gen/validate_psd_to_award.py`(EXIT 0 = PASS)。

## 量化結果(2026-07-28)

| 件 | 生成 mode | 生成頂點 | 生成 IoU | 藝術家頂點 | 藝術家 IoU | 覆蓋率平價 | 頂點省 |
|---|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 35 (hull16) | 0.933 | 78 (weighted) | 0.949 | ✅(98.4%,margin內) | 55% |
| 左手 | delaunay-v1 | 59 (hull19) | 0.964 | 80 (weighted) | 0.977 | ✅(98.7%,margin內) | 26% |
| 身體 | delaunay-v1 | 60 (hull20) | 0.966 | 98 (weighted) | 0.948 | ✅(**101.9%,勝藝術家**) | 39% |

- 拓樸閘全過:0 退化三角、0 孤兒頂點、hull 有效、頂點在預算(≤96)內。
- 圖:`figures/s3-psd-to-award-mesh.png`(左=藝術家橘、右=生成綠,疊在件 alpha 上)。

## 關鍵發現 / 教訓

1. **blobby 件自動走 v1 Delaunay(正確)**:3 件長寬比皆 <1.2 且非 row-convex,`generate_mesh_v2`
   auto 模式全回退 v1 散點 Delaunay。strip 模式是為窗簾這類「高瘦、單向拉伸」件設計的;
   這裡的機器人肢體/光暈是團塊狀,Delaunay 是對的拓樸。**驗證了 auto 路由的判斷正確**。
2. **生成器達到藝術家覆蓋率平價,且更精簡**:35–60 頂點 vs 藝術家 78–98,IoU 差距 ≤1.6%
   (身體甚至勝出)。藝術家 mesh 頂點多是為了**變形經濟**(平滑 warp),不是為了純覆蓋率
   → 純靜態 IoU 上生成器不吃虧;差距落在邊緣 anti-alias 尺度(margin 0.02 合理)。
3. **Award mesh uvs = region-local(0..1)**:實測對 PSD 件 alpha 直接 `uv×(W,H)` 得高 IoU
   (0.949/0.977/0.948)→ 確認 region-local 解讀。身體 uv x-max 僅 0.759 是**該件本身右側有透明邊距**
   (coverage 0.498),非 UV 慣例問題。
4. **端到端閉環**:PSD 圖層 →(psd_slice)→ 件 alpha →(generate_mesh_v2)→ mesh,
   對真實 spine 生產標的的覆蓋率與藝術家同級 → 「PSD→件→mesh」pipeline 對真實檔可用。

## ⚠️ 誠實邊界(尚未涵蓋)

- **只驗證靜態幾何/覆蓋率,未驗證權重**:生成 mesh 為 **unweighted**,藝術家 mesh 為 **weighted**
  (骨綁定 + 每頂點權重)。本 AC **不**檢驗 BBW/骨綁定正確性 —— S3 尚無權重生成(PLAN 列為後續)。
- **deform 閘 N/A**:這 3 件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform),
  故此處不做 deform 轉移閘。逐頂點 deform 穩健性已於 `main_draw` 4 mesh(有 deform)驗證
  (見 `s3-four-mesh-generalization.md`)。兩者互補:一個驗 deform-mesh、一個驗 bone-driven-mesh 的靜態覆蓋。
- margin=0.02 為容差(藝術家 mesh 非以最大覆蓋為目標);margin=0 時 光暈/左手 會以 ~1.5% 差落榜,
  屬 anti-alias 尺度,不代表生成器品質不足。

## 下一步建議

- **權重生成(BBW)**:要真正取代藝術家 weighted mesh,需 S3 加骨綁定 + BBW 權重
  (PLAN S3 完成條件的一部分);屆時可對照 Award 的 `vertices`(weighted 攤平)驗證權重分佈。
- **件→Spine JSON 組裝(SkelToJson)**:把 `PSD名/圖層名` 命名、size+2px、mesh/region 分配、
  atlas 0.70 縮放固化成工具,端到端產出可載入的 Spine JSON(STATE 候選 #2)。
