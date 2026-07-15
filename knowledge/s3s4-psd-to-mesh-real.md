# S3+S4 端到端 — PSD 件 → 生成 mesh → 對照真實生產 mesh(靜態覆蓋)

- **結論**:把 S4 切圖(`psd_slice`)與 S3 mesh 生成(`generate_mesh_v2`)串成端到端,對**真實生產標的**
  (`Award.json` 中機器人拆件的 3 個 mesh:光暈 / 身體 / 左手)驗收。3 件全 **overall_pass**:
  生成 mesh 的覆蓋率 IoU **達到或超過藝術家真實 mesh**,且頂點數在預算內、拓樸乾淨(margin=0)。
- **信心**:高(對真實生產 spine mesh 做真值對照 + 負對照確認鑑別力 + 拓樸閘)。
- **階段**:第 2 階段 / S3×S4 整合(里程碑:切圖 pipeline → mesh pipeline → 對真實 mesh 收斂)。

## 逐件結果(`validate_psd_to_mesh.py`,eps=0.002,margin=0)

| 件 | gen IoU | 藝術家基準 | 負對照(flip) | gen 頂點 | 藝術家頂點 | 拓樸 |
|---|---|---|---|---|---|---|
| 光暈 | 0.9796 | 0.9486 | 0.470 | 64 | 78 | clean |
| 身體 | 0.9908 | 0.9477 | 0.604 | 77 | 98 | clean |
| 左手 | 0.9901 | 0.9768 | 0.763 | 84 | 80 | clean |

→ 生成件覆蓋率全 **≥ 藝術家**,頂點數 ≈ 或少於藝術家(左手 +4)。負對照(uv 任一軸翻轉)掉到
0.47–0.76,證明覆蓋率量測有鑑別力(左手較對稱故負對照僅 0.76,仍遠低於通過門檻)。

## 關鍵發現

1. **Award mesh uvs = region-local 0..1(非 atlas-page)、y 同影像向、無 flip**。實測校正:
   直接 `uvs×(pieceW,pieceH)` 疊在 `psd_slice` 切件 alpha 上 → 藝術家自身覆蓋率 0.948/0.948/0.977;
   任一軸 flip 掉到 0.40–0.61。**推翻 s4 doc 舊註記「Award uvs 為 atlas UV 需轉 region 局部」** —
   實際不需轉換(切件 orientation 已對齊 region-local uv 空間)。
2. **這 3 件是 weighted mesh(骨骼驅動)、無 deform timeline** → 依 RULES 不得用未校準 stress_field
   下 deform 判定;本閘只判**靜態覆蓋 + 拓樸 + 頂點預算**。有 deform 的 unweighted 窗簾件仍由
   `validate_against_real.py`(真實位移場轉移)管。**兩條驗收路線各司其職,不要混用。**
3. **`epsilon_frac`(v1 Douglas-Peucker 邊界簡化)控制覆蓋率**:細緻的 blob 生產件在預設 0.008 略低於
   藝術家(光暈 0.933、左手 0.964);**eps=0.002 全部達標且拓樸乾淨、頂點 64/77/84 仍在預算內**。
   eps=0.004 對光暈拓樸不乾淨(有退化);eps=0.001 頂點膨脹到 81–111。**0.002 為此類件的甜蜜點**。
   (窗簾走 v2 strip 模式,不受 v1 eps 影響 → main_draw 4 mesh 結論不變,已回歸驗證 curtain_left 仍 PASS。)
4. **auto 模式對這 3 件全走 v1 Delaunay**(長寬比 <1.2 或非 row-convex),等於用真實生產件驗證了
   v1 對「不規則 blob」的覆蓋能力(先前只在合成 + 窗簾驗過)。

## 可重現

```
python3 tools/mesh_gen/validate_psd_to_mesh.py            # 3 件全 overall_pass(exit 0)
python3 tools/mesh_gen/validate_psd_to_mesh.py --epsilon 0.008   # 看 eps 靈敏度(光暈/左手 under)
```

## 下一步

- 把對應慣例(`PSD名/圖層名` slot、+2px padding、mesh/region 分配、eps 建議值)固化進
  「件→Spine JSON 組裝工具」(SkelToJson),端到端產出 Spine mesh attachment(候選 #2)。
- 右手/頭為 region(剛體旋轉),非 mesh → 屬 region attachment 組裝,不進 mesh 閘。
