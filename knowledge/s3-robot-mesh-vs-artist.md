# S3 端到端驗收 — atlas 件 → generate_mesh_v2 → 對照 Award 真實藝術家 mesh

- **結論**:首次以**真實生產藝術家 mesh** 當 ground truth,驗證 S3 生成器對 3 個機器人 mesh 件
  (光暈/身體/左手)。生成器對**剛體/緊湊件(身體/左手)輪廓 IoU 幾乎追平藝術家(Δ≈−0.008),
  且只用約 6 成頂點**;對**柔性放射狀件(光暈)落後(Δ−0.050)**。所有件拓樸/格式 AC 全過、
  靜態 0 自交 0 退化。過程揪出並修好生成器一個真實 bug:**內部孤兒頂點**(光暈)。
- **信心**:高(直接對生產藝術家 mesh 輪廓量化;可重現 `compare_robot_mesh.py`)。
- **階段**:第 2 階段 / S3 × S4 端到端(里程碑:合成/自資產 → **真實生產標的**)。

## 量化結果(alpha 來源 = Award atlas 切件;藝術家 uvs 為 region-local 0..1)

| 件 | 生成模式 | 生成 IoU | 藝術家 IoU | Δ | 生成 nv | 藝術家 nv | AC 全過 |
|---|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 0.9292 | 0.9795 | **−0.050** | 53 | 78 | ✅ |
| 身體 | delaunay-v1 | 0.9680 | 0.9760 | −0.008 | 61 | 98 | ✅ |
| 左手 | delaunay-v1 | 0.9602 | 0.9681 | −0.008 | 48 | 80 | ✅ |

- 靜態(setup pose)self-intersections / degenerate:生成與藝術家皆 0。
- 頂點經濟度:生成用藝術家的 **54%~62% 頂點**(48–61 vs 78–98)仍近乎追平剛體件輪廓。

## 關鍵發現

1. **auto 模式路由正確**:3 件皆近方形(aspect 0.84~1.12 < 1.2)→ 全部回退 **v1 Delaunay**
   (strip 專給高瘦、row-convex 的窗簾)。確認 v2 auto 的分流邏輯對真實件有效。
2. **v1 對緊湊件通用性佳**:身體/左手 Δ 僅 −0.008,以更少頂點追平藝術家輪廓。
3. **柔性放射狀件(光暈)是弱點**:epsilon=0.008 的 hull 簡化只給 hull=14 → 粗多邊形貼不住
   圓潤羽化邊,IoU 0.929 明顯低於藝術家的密網(78v)。**改善方向:對低 solidity/圓潤件降 epsilon
   加密 hull**(後續)。
4. **Award mesh uvs 實測為 region-local 0..1**(非全頁 atlas UV):直接 ×crop(W,H) 對齊即高 IoU
   (0.968~0.980,noflip,無需 y 翻)。這也**再次確認 atlas_crop 的 CW derotate 正確**
   (光暈/身體 rotate=true,對齊後 IoU 高)。修正先前 knowledge 註記(當時假設需轉 region 局部)。
5. **Award 機器人 mesh 無 deform timeline** → 靠骨骼/權重變形,無真實位移場可轉移。
   故本輪 **AC5(真實 deform 轉移)N/A**;這些柔性件在 v1 下的耐變形性未被生產資料驗證。

## 修的 bug — 內部孤兒頂點(generate_mesh.py)

光暈生成 mesh 有 1 個內部頂點(idx 30,≥hull)未被任何三角參照(AC2c fail)。成因:
`filter_triangles` 把其周圍三角全濾掉(重心落 mask 外)後留下孤兒。
**修法**:`prune_orphans()` — 只剪**內部**孤兒(index ≥ n_hull)並重映射三角索引;
hull 頂點即使暫無參照也保留(維持 hull-first 不變量)。剪掉不影響覆蓋率(孤兒不貢獻填滿):
光暈 nv 54→53、IoU 不變(0.9292)、AC2c 轉 PASS。main_draw 窗簾 v2 回歸不受影響(仍 overall_pass)。

## 可重現

```
python3 tools/mesh_gen/compare_robot_mesh.py            # 3 件 vs 藝術家對照
python3 tools/mesh_gen/validate_against_real.py --gen v2  # main_draw 窗簾回歸(未回歸)
```

## 下一步候選

- **光暈類柔性件的 hull 加密**:對低 solidity(圓潤/羽化)件自動降 epsilon,量測 IoU 是否追平藝術家。
- 把「件→Spine attachment」命名慣例(`PSD名/圖層名`、+2px、atlas 0.70 縮放、mesh/region 分配)
  固化成 SkelToJson 組裝工具(S4→端到端產 Spine JSON)。
- S2 補圖閘 / 骨架閘(補齊 S2 樞紐)。
