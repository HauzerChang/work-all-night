# S3+S4 端到端:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh(靜態覆蓋率)

- **結論**:把「PSD→件→S3 mesh」整條接到真實生產標的上驗收。用 `robot_parts.psd` 三件
  (光暈/身體/左手,在生產 spine `Award` 中皆為 mesh),`generate_mesh_v2` 生成的 mesh
  **覆蓋率不劣於藝術家 mesh、且頂點更省**。3 件 `overall_pass=True`,負對照有鑑別力。
- **信心**:高(對真實生產 mesh 交叉比對 + 覆蓋率 IoU + 頂點預算 + 交叉件負對照 + 疊圖)。
- **階段**:第 2 階段 / S3×S4 交會(端到端里程碑)。

## ★ 校正既有假設(重要)

`s4-psd-to-spine-real.md` 早期記「Award mesh uvs 為 atlas UV,需先轉 region 局部」。
**這是錯的**。實測 3 件 UV bbox 都約 0..1(光暈 u 0.012–0.990、身體 v 0.049–0.989),
且 atlas region 明明在 page 的非 0 位置(光暈 xy=562,879 於 1780×1376 頁、rotate=true)。
→ **Spine JSON 的 mesh `uvs` 是 region-local 0..1**(runtime 靠 AtlasAttachmentLoader
把它重映到 atlas region;JSON 不存 atlas-global UV)。

證據:PSD 件像素框直接套 `uv*(W,H)` 得藝術家覆蓋,對 PSD 件 alpha 的 IoU:
無 flip = **0.95 / 0.95 / 0.98**;任一 flip 都掉到 0.40–0.76 → 框天然對齊,**無需 atlas 轉換、無需 flip**。
(這也表示 `validate_against_real.artist_iou` 的 `uvs*W` 對這些件同樣正確。)

## 結果(`validate_psd_to_award.py`,gen v2 auto)

| 件 | 藝術家 v/t/hull | 生成 v/t/hull(mode) | IoU 藝/alpha | IoU 生/alpha | IoU 生/藝 |
|---|---|---|---|---|---|
| 光暈 | 78 / 76 / 78 | **35** / 49 / 16 (delaunay-v1) | 0.949 | 0.933 | 0.918 |
| 身體 | 98 / 154 / 40 | **60** / 97 / 20 (delaunay-v1) | 0.948 | **0.966** | 0.928 |
| 左手 | 80 / 116 / 42 | **59** / 97 / 19 (delaunay-v1) | 0.977 | 0.964 | 0.957 |

- 生成覆蓋率均在藝術家 ±0.02 內(身體甚至更高),頂點數約為藝術家的 45–61%(更省)。
- 疊圖 `figures/psd_to_award_mesh.png`:綠(交集)為主、紅(藝術家獨有)/藍(生成獨有)僅細邊。

## 負對照(閘鑑別力)

每件生成 mesh vs「其他件」藝術家覆蓋(resize 到同框後比形狀):
同件 0.918–0.957 vs 交叉件 **0.484–0.584**,gap>0.33 → 閘能區分「對的件」與「錯的件」。

## 兩個重點觀察

1. **三件全走 delaunay-v1,不是 strip**:這些機器人件是團塊狀(aspect 0.84–1.12,非高瘦
   row-convex),不滿足 v2 auto 的 strip 條件(aspect≥1.2 且 row-convex)→ 回退 v1。
   窗簾走 strip、機器人團塊件走 v1,**auto 模式的分流在真實件上如預期運作**。
2. **這些 Award mesh 是 weighted、無 deform timeline**(靠骨骼+權重變形,非逐頂點 deform)。
   故本閘只驗**靜態覆蓋率 / 拓樸預算**。v1 散點的「deform 自交」弱點(見 s3-four-mesh)
   對 bone-driven 件不適用 —— 要談這些件的變形穩健需先有 S5 權重,超出本 chunk。
   ⇒ 誠實範圍:**已驗證「生成 mesh 的覆蓋/拓樸配得上真實生產 mesh」,未驗證 bone-driven 變形**。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
python3 tools/mesh_gen/validate_psd_to_award.py --figure knowledge/figures/psd_to_award_mesh.png
# overall_pass=True;3 件 AC_cover_ge_artist & AC_verts_le_artist,負對照 discriminates
```

## 下一步候選

- **切件→Spine JSON 組裝(SkelToJson)**:把「`PSD名/圖層名` slot 命名 + size+2px padding +
  mesh/region 分配 + 生成 mesh」固化成工具,對一件端到端產出 attachment JSON。
- S5 權重(bone-driven 變形驗證的前提;唯一卡死環節)。
- S2 補圖閘 / 骨架閘。
