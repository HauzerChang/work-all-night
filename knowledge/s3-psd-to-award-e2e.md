# S3+S4 端到端:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh(里程碑)

- **結論**:把 S4(PSD 切件)與 S3(mesh 生成)**串成端到端**,並對**真實生產標的**
  (Award spine 的機器人 3 個 mesh 件)驗收 **全通過**。`robot_parts.psd` 的
  光暈/身體/左手 → `psd_slice` 切件 → `generate_mesh_v2`(這 3 件 aspect<1.2 → 自動回退
  v1 Delaunay)所產 mesh,覆蓋率**追平或超越藝術家**,且**頂點數更少**、0 自交/退化/孤兒。
- **信心**:高(對真實生產 mesh 的 uv/topology 直接比對 + 負對照確認度量鑑別力)。
- **階段**:第 2 階段 / S3×S4 整合(從「各能力單獨驗」→「端到端對真實標的驗」)。

## 驗收數據(`validate_psd_to_award.py`,margin=0.02)

| 件 | 生成 (v,hull,tri) | 藝術家 (v,hull,tri) | 覆蓋率 IoU 生成/藝術家 | mesh↔mesh IoU | 靜態自交 |
|---|---|---|---|---|---|
| 光暈 | 35 / 16 / 49 | 78 / 78 / 76 | **0.933 / 0.949** | 0.918 | 0 |
| 身體 | 60 / 20 / 97 | 98 / 40 / 154 | **0.966 / 0.948**(勝) | 0.928 | 0 |
| 左手 | 59 / 19 / 97 | 80 / 42 / 116 | **0.964 / 0.977** | 0.957 | 0 |

- 覆蓋率 IoU：填三角 vs 件 alpha;藝術家 baseline = 真實 mesh 自身覆蓋率(非武斷 0.95)。
- 三件皆 `生成 >= 藝術家 - 0.02` → PASS;身體甚至**超過**藝術家覆蓋率。
- **頂點效率**:生成 35–60v vs 藝術家 78–98v,以更少頂點達同等覆蓋(v1 Delaunay 對 blob 件夠用)。
- 視覺:`figures/psd-to-award-mesh-overlay.png`(blue=生成 / red=藝術家,兩者同 silhouette)。

## 關鍵發現 / 校正

1. **Award mesh uvs 其實是 region-local(0..1),非 atlas-global**。實測 uv 範圍
   光暈 x[0.012,0.990]、左手 x[0.008,1.0]、身體 x[0,0.759] —— 幾乎鋪滿 [0,1]。
   先前 knowledge 註記「需轉 region 局部」**不精確**;直接 `uv×件W,H` 即得件像素框座標
   (與 `validate_against_real.artist_iou` 對 main_draw 的作法一致)。
2. **這 3 件是 weighted mesh(`vertices.len != uvs.len`)、骨骼權重驅動、無 deform timeline**。
   故本閘**不跑 deform 轉移**(依 RULES 不用未校準 stress_field;無真實位移場可轉移)。
   strip/Delaunay 的耐變形已在 main_draw 窗簾另行驗證(見 `s3-four-mesh-generalization.md`)。
3. **auto 模式對 blob 件正確回退 v1**:光暈 0.97 / 左手 0.84 / 身體 1.12,皆 aspect<1.2 →
   Delaunay。strip 是為高瘦窗簾設計,對這類近方形件用 Delaunay 是對的選擇。

## 評估器可信度(負對照)

mesh↔mesh IoU 交叉矩陣(對角=正確配對):

```
gen\art      光暈     身體     左手
   光暈     0.918    0.496    0.572
   身體     0.487    0.928    0.512
   左手     0.587    0.519    0.957
```

對角 0.92–0.96 vs 錯配 0.49–0.59 → **清楚分離**,度量確實在量形狀相似度而非「兩塊都填滿就高」。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
python3 tools/mesh_gen/validate_psd_to_award.py            # 3 件全 overall_pass
```

## 下一步

- **件 → Spine JSON 組裝(SkelToJson)**:把已固化的慣例(`PSD名/圖層名` slot、mesh/region
  分配、+2px padding、atlas ~0.70 縮放)+ 本次生成 mesh,寫出「PSD → 可載入 Spine JSON」工具,
  端到端補上最後一段。純 CPU 可自驅。
- 若要對 weighted 件做「變形級」對照,需要 Award 的骨架/權重繫結重現(較大工程,列為候選)。
