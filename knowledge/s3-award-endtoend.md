# S3×S4 端到端驗收 — PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把 `robot_parts.psd` 三個「在 Award 為 mesh」的件(光暈 / 身體 / 左手)用 `psd_slice` 切出 alpha,
  餵 `generate_mesh_v2`(auto→v1 Delaunay),與 **Award 藝術家 mesh 真值**逐件量化對照 → **3 件全 overall_pass**。
  這是首次把 S4(切圖)+S3(mesh 生成)串成端到端,並對「真實生產標的」而非合成/自身資產驗收。
- **信心**:高。有生產真值(Award mesh)、負對照確認閘鑑別力、座標映射經先前 alpha-IoU 交叉確認。
- **階段**:第 2 階段 / S3×S4 整合(里程碑)。

## 對照結果(gen = generate_mesh_v2;artist = Award 生產 mesh)

| 件 | gen 頂點 | artist 頂點 | gen coverage | artist coverage | gen IoU | artist IoU | gen sliver | artist sliver |
|---|---|---|---|---|---|---|---|---|
| 光暈 | 35 | 78 | 0.951 | 0.959 | 0.933 | 0.949 | 0.10 | **0.55** |
| 身體 | 60 | 98 | 0.974 | 0.961 | 0.966 | 0.948 | 0.13 | 0.13 |
| 左手 | 59 | 80 | 0.977 | 0.997 | 0.964 | 0.977 | 0.03 | 0.18 |

**要點**:
1. 生成 mesh **頂點數約為藝術家的 45~75%**(35/60/59 vs 78/98/80),coverage/IoU 都在藝術家基準 ±margin 內
   (cov_margin 0.02、iou_margin 0.03)→ **更精簡但覆蓋等價**。
2. 生成 mesh **三角品質普遍優於藝術家**(sliver_frac 更低、median 最小內角更大)。光暈藝術家 mesh
   sliver 高達 0.55(放射狀薄扇形是手繪常態),我方均勻 Delaunay 反而更健康。→ 靜態網格健康度不輸真值。
3. 這 3 件在 Award 是 **weighted mesh 且無 deform timeline**(骨骼/權重驅動,非逐頂點 deform),
   故「真實位移場轉移」deform 閘對它們 **N/A**。本閘做「靜態覆蓋 + 拓樸 + 三角品質」對真值對照,
   與 curtain/shadow(有 deform)的 `validate_against_real` 互補,合起來覆蓋兩種變形範式。

## 座標映射(免處理 atlas 縮放 / weighted bind)

Award mesh `uvs` 是 0..1 相對「該件原圖(切件)」,直接 `uvs×(W,H)` 即落在 PSD 切件像素座標
(先前 alpha-IoU 0.933~0.991 已證 PSD 切件 == spine 貼圖素材)。故藝術家基準能在切件座標直接算,
**不需碰 atlas 0.70 縮放、也不需解 weighted bind→世界座標**。實測 artist coverage 0.959/0.961/0.997 佐證映射正確。

## 閘可信度(負對照,第四次守住「先校準再信」)

- NEG 縮小 0.5×:coverage 0.961→**0.248**,coverage 閘正確 FAIL。
- NEG 放大 1.4×(外溢 alpha):IoU 0.948→**0.673**,IoU 閘正確 FAIL。
- 藝術家 mesh 自身度量自洽(0.9477/0.961)。→ 閘有鑑別力、未過鬆。

## 可重現

```
python3 tools/mesh_gen/compare_award_mesh.py            # 3 件全跑 → overall_pass, exit 0
python3 tools/mesh_gen/compare_award_mesh.py --piece 身體
```

## 未解 / 下一步

- **生成器目前為 unweighted mesh**;真實生產這 3 件是 weighted(骨骼綁定)。要完全對齊真值,
  下一能力是 **S3 權重指派(BBW / heat)**,把骨架 + unweighted mesh → weighted mesh。需先有骨架(S5)或人工骨。
- 端到端還差最後一段:**件 + mesh → 寫出可用 Spine JSON attachment**(SkelToJson 組裝,含 `PSD名/圖層名`
  命名慣例、+2px padding、atlas 0.70 縮放),把 S3×S4 產物落成 spine 檔。
