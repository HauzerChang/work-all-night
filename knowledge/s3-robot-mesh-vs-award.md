# S3+S4 端到端:PSD 切件 → 生成 mesh → 對照 Award 真實 mesh(里程碑)

- **結論**:把 S4(PSD 切件)與 S3(mesh 生成)**串成端到端**,並首次對「真實生產 mesh 的 ground truth」
  (`Award.json` 中機器人 3 件 weighted mesh)做覆蓋率對照。**3 件全 PASS**:我方自動生成 mesh
  的三角覆蓋率(IoU)與藝術家手做 mesh 在 margin 內相當,且**頂點數少一半以上**。
- **信心**:高。對真實生產 mesh 交叉比對 + 雙向負對照(交叉配對 / UV 翻轉)確認評估器有鑑別力。
- **階段**:第 2 階段 / S3×S4 整合(里程碑:合成 → 真實 mesh ground truth)。
- **可重現**:`python3 tools/mesh_gen/validate_robot_mesh.py`(exit 0 = 全過)。
  先 `python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts` 切件。

## 對照結果(margin 0.02)

| 件 | 件尺寸 | 我方 mesh | 藝術家 mesh | 我方 IoU | 藝術家 IoU | pass |
|---|---|---|---|---|---|---|
| 光暈 | 706×683 | 35v/hull16/49t (**v1**) | 78v/hull78/76t (weighted) | 0.9331 | 0.9486 | ✅ |
| 身體 | 379×425 | 60v/hull20/97t (**v1**) | 98v/hull40/154t (weighted) | 0.9660 | 0.9477 | ✅(反超) |
| 左手 | 257×215 | 59v/hull19/97t (**v1**) | 80v/hull42/116t (weighted) | 0.9642 | 0.9768 | ✅ |

## 關鍵發現

1. **3 件全走 v1 Delaunay,不走 v2 strip**。原因:strip 只在「高瘦(aspect≥1.2)且 row-convex」時觸發
   —— 那是窗簾類。機器人這些是**塊狀(blob)件**(aspect 0.84~1.12),`generate_mesh_v2` auto 模式
   正確回退 v1 散點 Delaunay。**結論:兩種拓樸各有其類**——條狀件用 strip(耐單向拉伸)、塊狀件用 Delaunay
   (內部散點貼合輪廓)。auto 分派符合預期。

2. **我方 mesh 用不到藝術家一半的頂點就達到同級覆蓋率**(35 vs 78、60 vs 98、59 vs 80)。
   藝術家的密頂點是為了**權重變形的平滑度**(這些是 weighted mesh、靠骨骼變形),不是為了靜態覆蓋。
   → 靜態覆蓋率相當不代表變形品質相當;見下方限制。

3. **光暈 artist hull=78=全部頂點**(純外環 mesh,無內部點)——柔光暈是薄環狀,藝術家只沿輪廓佈點。
   我方 Delaunay 給 hull16+內部點,IoU 0.933 vs 藝術家 0.949(藝術家自身也只 0.949,因羽化邊光柵化近似)。

4. **獨立佐證 Award mesh uvs 是 region-local 且方向正確**:artist mesh 的 `uvs`×(件W,H) 光柵化後
   與 PSD 切件 alpha 的 IoU 高達 0.948~0.977。若 uvs 是「整頁 atlas UV」會對到錯的小區塊 → 近 0。
   這也再次確認 **PSD 切件 == spine 生產素材**(呼應 texture alpha-IoU 0.92~0.99 的閉環)。

## 負對照(確認評估器可信)

- **交叉配對**(A 件 mesh 疊到 B 件 alpha):對角(正確)0.949/0.948/0.977,離對角掉到 **0.48~0.58**。
- **UV 垂直翻轉**(非對稱件應掉):光暈 0.949→0.426、身體 0.948→0.604、左手 0.977→0.590(Δ 0.34~0.52)。
- → 評估器對「錯件 / 錯方向」有明確鑑別力,非恆高。

## 限制 / 誠實標註

- **無 deform 閘**:Award 這 5 件在其動畫中**無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform),
  故真實位移場不存在 → 本次只驗**靜態覆蓋率**,未驗變形穩健。這與 main_draw 窗簾(有 deform,可跑
  `transfer_deform_check`)不同。**塊狀件的變形品質**要另找有 deform 或 weighted 動作的真值才能驗。
- 我方生成 mesh 為 **unweighted**;藝術家為 **weighted**(骨綁定)。要真正取代生產 mesh 還需 S? 權重生成(BBW)。
  本次證明的是「**拓樸/覆蓋率**」層級的對真值可行,不含權重。
- 件尺寸差 +2px(PSD 379×425 vs Award 邏輯 381×427 = atlas padding),對 IoU 影響 <0.5%,已忽略。

## 圖

- `knowledge/figures/robot_mesh_vs_award.png` — 3 件左(藝術家紅)/右(我方綠)三角網格疊在件 alpha 上。

## 下一步候選

- **權重生成(BBW)**:把 S3 從「只出拓樸」升到「出 weighted mesh」,才能端到端替代生產 mesh。需骨架 → 接 S5。
- **切件→Spine JSON 組裝(SkelToJson)**:把 `PSD名/圖層名` 命名 + size + mesh/region 分派 + 生成 mesh
  固化成一支工具,端到端吐出可載入的 Spine skin。
- 塊狀件的變形穩健驗證:找一個帶 weighted-mesh 骨骼動作的真值(Award 有 12 anim,可挑有旋轉/縮放骨的幀)。
