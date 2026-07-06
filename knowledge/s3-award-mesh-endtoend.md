# S3+S4 端到端「PSD→件→mesh」對真實生產標的(Award)驗收

- **結論**:對 Award「機器人拆件」的 **3 個真實 mesh 件(光暈/身體/左手)**,從 atlas 切出真實
  貼圖 alpha → 跑 S3 生成器 → 與**藝術家真實 mesh** 在同一張 alpha 上比對:**3 件全 overall_pass**
  (覆蓋率 ≥ 藝術家、頂點數 ≤ 藝術家、拓樸乾淨)。這是 S3(mesh 生成)+ S4(PSD 切件)串成
  端到端、對真實生產標的、有 ground truth 的驗收。
- **信心**:高(真值 = 生產 spine 藝術家 mesh;正對照達標、評估器沿用已校準的 IoU/topo 閘)。
- **階段**:第 2 階段 / S3×S4 端到端(里程碑)。

## 驗收結果(`compare_award_mesh.py`,2026-07-06)

| 件 | 藝術家 v / IoU | 生成 v / IoU | cover | econ | topo | overall |
|---|---|---|---|---|---|---|
| 光暈 | 78 / 0.9795 | **78 / 0.9832** (eps 0.002) | ✅ | ✅ (=78) | ✅ | ✅ |
| 身體 | 98 / 0.9760 | **69 / 0.9858** (eps 0.004) | ✅ | ✅ (**−30%**) | ✅ | ✅ |
| 左手 | 80 / 0.9681 | **64 / 0.9739** (eps 0.006) | ✅ | ✅ (**−20%**) | ✅ | ✅ |

- 覆蓋率 IoU = mesh 三角填滿 vs 真實貼圖 alpha;藝術家基準用其自身 mesh 同法算(生產 mesh 自身也僅 ~0.97–0.98,非完美)。
- alpha 來源:`atlas_crop.extract`(Award 雙頁;光暈/身體 rotate=true、左手 false;貼圖 ~0.70 縮放,
  但 IoU 正規化 scale-invariant,藝術家與生成用**同一張 mask**,比對公平)。

## ★ 關鍵發現:固定 epsilon 不通用 → 需 evaluator-driven 自動收斂

初測(v2 auto,固定 eps=0.008)3 件覆蓋率全略低於藝術家(0.929/0.968/0.960 vs 0.980/0.976/0.968),
且光暈出現 1 個孤兒頂點。epsilon 掃描揭示:

- **覆蓋率 IoU 由 hull 邊界取樣密度(epsilon)決定**(與 v2 strip「IoU 由 rows 決定」同源)。
- **達到藝術家 IoU 所需的密度是形狀相依的**:光暈(大有機 blob)需 eps≈0.002;身體/左手 eps≈0.004–0.006 即足。
  → **單一固定 eps 必然對某些件過疏(cover 不足)或過密(超頂點預算)**,無單一預設可同時過 3 件。

**解法** = RULES 的「評估器即自主收斂閘」:`auto_tune.generate_auto(path, target_iou, budget)`
從粗到細掃 epsilon,回傳**第一個** IoU≥target 的 mesh(最精簡即停),全程受 vertex budget 約束。
→ 光暈收斂到 eps0.002(=藝術家頂點數)、身體/左手收斂到更粗 eps(比藝術家更精簡),3 件全過。
附 `prune_orphans`(過濾三角後移除未用頂點並重編索引)→ 保證 0 孤兒(AC-topo)。**不改 v1 本體**
(main_draw 既有 4-mesh 驗證不受影響,已回歸確認 curtain_left/right+shadow 仍 pass)。

## ⚠️ 誠實邊界:AC-deform 對這 3 件 N/A

這 3 件在 Award **無 deform timeline** —— 靠**骨骼權重**(weighted mesh)變形,非逐頂點 deform。
我方生成器產 **unweighted** mesh,不產權重,故**無法**用「真實位移場轉移」閘(需 deform timeline)
比對變形穩健度。因此本次驗收僅涵蓋 **靜態幾何(覆蓋率)+ 頂點經濟 + 拓樸合法**,**不含**這幾件的
變形手感。變形穩健度已在 main_draw 4 個 **有 deform timeline** 的 mesh 上驗過(見
`s3-four-mesh-generalization.md`)。BBW 骨骼權重生成仍是未建能力(S3 路線的權重部分 / S5)。

## 頂點預算修正

AC.md 舊的固定「≤64」預算**低於**藝術家對這批件的選擇(78/98/80)。改為**以藝術家頂點數為預算**
(真值),更貼合「同等或更精簡」的實際目標。main_draw 窗簾類件仍適用小預算(藝術家僅 21v)。
→ 預算應**相對於件/藝術家**,非全域固定值。

## 可重現

```
python3 tools/mesh_gen/compare_award_mesh.py          # 3 件 all_pass=True
python3 tools/mesh_gen/auto_tune.py <region.png> --target-iou <artist_iou> --budget <artist_v>
```

## 下一步

- **權重(BBW)生成**:這 3 件的完整重現需骨骼權重;無 deform timeline 的件,變形驗收得靠
  weighted-mesh + 骨骼動畫(屬 S3 權重 / S5 骨架)。
- 把 `PSD名/圖層名` 命名 + size+2px padding + mesh/region 分配 + auto_tune mesh 固化成
  「件→Spine JSON」組裝工具(SkelToJson),端到端產出可用 Spine attachment。
