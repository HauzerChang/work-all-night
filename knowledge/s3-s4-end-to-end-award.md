# S3+S4 端到端:PSD 件 → 生成 mesh → 對照 Award 真實生產 mesh

- **結論**:把 S4(PSD 切圖)與 S3(mesh 生成 v2)串起來,對「真實生產 mesh」(big win spine
  `Award.json` 的機器人拆件 光暈/左手/身體)做整合 AC,**3 件全 overall_pass**:生成 mesh 的
  剪影覆蓋率在藝術家 mesh ±0.03 內(1 件還更高),且頂點數只用藝術家的 45%~74%。
- **依據**:`tools/mesh_gen/compare_award_mesh.py`(本次新增),`python3 tools/mesh_gen/compare_award_mesh.py` → exit 0。
- **信心**:高。真值來自真實生產檔;比較經負對照確認有鑑別力;附視覺圖佐證。
- **相關階段**:專案第 2 階段(S3 mesh + S4 切圖 串接);對 STATE「下一步候選 1」的驗收。

## 關鍵發現:Spine mesh uvs 是 region-local 0..1、logical(未旋轉)方位

實測(把 Award mesh `uvs × PSD 件尺寸`,疊回 PSD 件 alpha):
- 光暈 IoU 0.949、左手 0.977、身體 0.948 —— 全高。

→ 證明兩件事:
1. **PSD 件 = spine 生產貼圖同一素材**(呼應 session 006 texture alpha-IoU 0.92~0.99)。
2. Spine JSON 的 mesh `uvs` 記的是 **region 內部 0..1**(不是整頁 UV),且是**logical 方位**
   (atlas 的 `rotate:true` 由 runtime 套用,JSON 內的 uv 未旋轉)。
   → 因此**生成 mesh(件像素空間)與藝術家 mesh 可在同一個 PSD 件像素空間直接比較**;
   atlas 的 ~0.70 縮放在覆蓋率(IoU)正規化下自動抵銷,無需處理旋轉/縮放。

## 比較法(蘋果對蘋果:皆在 PSD 件像素空間、對同一 alpha 剪影)

| 指標 | 定義 |
|---|---|
| `gen_iou` | IoU(生成 mesh 三角填滿, 件 alpha) |
| `artist_iou` | IoU(Award 真實 mesh 三角填滿, 件 alpha) — 基準真值 |
| AC 覆蓋率 | `gen_iou >= artist_iou - 0.03` |
| AC 頂點預算 | `gen_verts <= artist_verts × 1.5` |
| AC 格式合法 | evaluate_mesh 的 format/退化/孤兒/重心(unweighted) |

## 量化結果(2026-07-15)

| 件 | mode | 藝術家 v / gen v (比) | artist_iou | gen_iou | Δ | overall |
|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 78 / 35 (0.45) | 0.9486 | 0.9331 | −0.0155 | ✅ |
| 左手 | delaunay-v1 | 80 / 59 (0.74) | 0.9768 | 0.9642 | −0.0126 | ✅ |
| 身體 | delaunay-v1 | 98 / 60 (0.61) | 0.9477 | 0.9660 | **+0.0183** | ✅ |

- 3 件皆非高瘦 strip → v2 auto 回退 Delaunay(v1),合理。
- 生成 mesh 用**更少頂點**達到接近/超越藝術家的覆蓋率。

## 負對照(確認評估器有鑑別力)

生成 mesh(列)對各件 alpha(欄)的 coverage IoU:對角(正確配對)0.93~0.97,
離對角(錯配)崩到 0.48~0.58 → 覆蓋率不是對任何剪影都虛高,指標可信。

```
mesh\alpha   光暈    左手    身體
   光暈     0.933  0.578  0.502
   左手     0.583  0.964  0.521
   身體     0.482  0.516  0.966
```

## 視覺佐證

`knowledge/figures/s3-award-mesh-compare.png` — 3 件並排,藝術家 mesh(綠)vs 生成 mesh(紅)
疊在件貼圖上;生成線框以較少頂點貼合輪廓。

## 侷限 / 尚未做(交下一個 chunk)

- ⚠️ **未含 deform 閘**:Award 這 3 件都是 **weighted mesh**(`len(vertices)≠len(uvs)`),
  其變形須重現 Award 12 支動畫的 weighted deform 才能做位移場轉移;本次只做幾何/覆蓋對照。
  main_draw 走的 `transfer_deform_check` 是 unweighted 位移場,無法直接套 weighted。
- 覆蓋率在**件像素空間**量(gen 與 artist 皆是),故 0.70 縮放無影響;但兩者對「同一張件 alpha」,
  所以是公平比較。margin 0.03 為 raster 容差,已文件化。
- 生成的是 **unweighted** mesh;要落地成可用 Spine attachment 還需(a)綁權重或接受 unweighted、
  (b)uv 轉回 atlas region 座標 + 處理 rotate。→ 併入「件→Spine JSON 組裝(SkelToJson)」chunk。
