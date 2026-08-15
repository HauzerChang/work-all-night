# S3+S4 端到端驗收 — PSD 切件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把 S4(PSD 切圖)與 S3(mesh 生成)**串成端到端**,並用**真實生產標的**
  (`Award.json` 機器人 3 個 mesh 件:光暈/身體/左手)當真值驗收。
  三件生成 mesh 的**輪廓覆蓋率全部達到藝術家等級**(gen_iou ≥ artist_iou − 0.03),
  且**頂點數遠少於藝術家**(35/60/59 vs 78/98/80)。里程碑:S3+S4 對真實標的閉環成立。
- **信心**:高(真值 = 生產 spine 藝術家 mesh;覆蓋率同框對照;朝向自證;正/負對照方法論一致)。
- **階段**:第 2 階段 / S3×S4 整合。工具:`tools/mesh_gen/validate_psd_to_award.py`。

## 量化結果(2026-08-15,`--gen v2`,auto 皆退回 delaunay-v1)

| 件 | 生成 mesh | gen_iou | 藝術家 mesh | artist_iou | 覆蓋 pass |
|---|---|---|---|---|---|
| 光暈 | 35v / 49t / hull16 | 0.9244 | 78v | 0.9393 | ✅ (差 0.015 < 0.03) |
| 身體 | 60v / 97t / hull20 | 0.9599 | 98v | 0.9435 | ✅ **生成反超藝術家** |
| 左手 | 59v / 97t / hull19 | 0.9491 | 80v | 0.9768 | ✅ (差 0.028 < 0.03) |

→ 全 `overall_pass`。生成器用**更少頂點**達到相近甚至更高的靜態覆蓋率。

## ★ 新發現:Spine JSON mesh `uvs` 存的是「上正立作圖框」,不是 atlas 旋轉框

驗收時對每件的 alpha 做 8 朝向(4 旋轉 × 水平翻)搜尋「最佳對齊」,結果**三件全 `rot0`**——
包含在 atlas 中 `rotate:true` 的**光暈、身體**。這證明:

- **mesh 的 `uvs` 是藝術家在上正立影像上作圖的 0-1 座標**,runtime 才依 atlas 的 `rotate`
  旗標在取樣時處理旋轉;**JSON 層面 uvs 與 atlas 打包旋轉/縮放(~0.70)無關**。
- 實務意義:未來寫 SkelToJson / mesh round-trip 時,**artist uvs 可直接疊到上正立切件**
  (`u·W, v·H`),不需為 atlas rotate 做逆旋轉。此點修正了先前「Award uvs 為 atlas UV,
  需先轉 region 局部」的模糊描述(見 `s4-psd-to-spine-real.md` 下一步欄):**region 局部 = 上正立框**。

## 變形穩健度(附加檢查,非 pass 門檻)

這 3 個 Award mesh **無 deform timeline**(靠骨骼/權重變形,見 `s4-psd-to-spine-real.md`),
故本閘門檻只看**靜態覆蓋率**。另把 main_draw 窗簾的**真實位移場轉移**到生成 mesh 當極端壓力測:

- 光暈、身體:si=0 / flip=0 **乾淨**。
- **左手:si=10 / flip=3(自交)** — 小而 blobby(aspect 0.84)的 Delaunay 散點在**極端單向拉伸**
  下仍會自交,與 S3 舊發現一致(strip 較耐變形,但 strip 只適用高瘦 row-convex 件)。
  因左手實際無 deform,不影響驗收;但標記:**若某件未來要吃大 deform,blobby Delaunay 需補強**
  (候選:各向異性佈點 / 沿主變形軸加規則格 / 局部 strip)。

## 可重現

```
python3 tools/mesh_gen/validate_psd_to_award.py --gen v2            # 全 3 件,exit 0
python3 tools/mesh_gen/validate_psd_to_award.py --gen v1 --layer 身體
```

朝向自證 + 同框 IoU 對照的實作在 `validate_psd_to_award.py`(`best_orientation_iou`)。
證據圖:`knowledge/figures/psd-to-award-mesh.png`(生成 mesh 線框疊在切件 alpha 上,綠=三角/紅=hull)。

## 下一步候選

1. **SkelToJson 組裝**:把「件→mesh(本閘已驗)+ `PSD名/圖層名` slot 命名 + size+2px padding +
   uvs=上正立框」固化成工具,端到端由 PSD 產出可載入的 Spine JSON attachment 區塊。
2. blobby 件的 deform 穩健度補強(僅在確有大 deform 需求時才做,避免過度工程)。
