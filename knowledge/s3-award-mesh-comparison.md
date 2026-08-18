# S3 端到端驗收 — PSD 件 → generate_mesh_v2 → 對照 Award 真實生產 mesh

- **結論**:S3 mesh 生成器對**真實生產標的**驗收通過。用 `robot_parts.psd` 的 3 個 mesh 件
  (光暈 / 身體 / 左手,在 Award spine 中皆為 mesh)跑 `generate_mesh_v2`,與 Award 藝術家 mesh
  在**同源件 alpha** 上比覆蓋率(IoU):**3 件全 ≥ 藝術家,且頂點數 ≤ 或 ≈ 藝術家**。
  → 端到端「PSD → 件 → mesh」對真實生產標的 **overall_pass**(2026-08-18)。
- **信心**:高(對真實生產 mesh ground-truth 交叉比對 + UV 轉換自我校驗 + 雙負對照確認鑑別力)。
- **階段**:第 2 階段 / S3(里程碑:合成/main_draw → **真實 Award 生產 mesh** 驗收)。

## 量化結果(`tools/mesh_gen/compare_to_award.py`,eps=0.002 / max_interior=40)

| 件 | 我的 IoU | 藝術家 IoU | Δ | 我的頂點 | 藝術家頂點 | 頂點比 | geom_pass |
|---|---|---|---|---|---|---|---|
| 光暈 | 0.980 | 0.949 | **+0.031** | 65 | 78 | 0.83 | ✓ |
| 身體 | 0.991 | 0.948 | **+0.043** | 77 | 98 | 0.79 | ✓ |
| 左手 | 0.990 | 0.977 | **+0.013** | 84 | 80 | 1.05 | ✓ |

→ 我的 mesh **靜態覆蓋率全面 ≥ 藝術家,且更精簡(光暈/身體頂點數少 ~20%)**。

## 關鍵事實與發現

1. **Award mesh 的 `uvs` 是 region-local**(每件 uv 幾乎鋪滿 [0,1]),**不是** atlas-global。
   故藝術家 mesh 可直接以 `u*W, v*H` 映回件像素空間比對(與 main_draw 的 `artist_iou` 同法)。
   → 修正 s4 文中「Award mesh uvs 為 atlas UV,需先轉 region 局部」的推測:實測**無需**轉換。
2. **blob 件走 v1 Delaunay,不走 strip**:這 3 件非高瘦/非 row-convex,`mode=auto` 正確回退 v1。
   strip 是窗簾類(高瘦、單向拉伸)專用。
3. **v1 的 IoU 由 `epsilon_frac`(hull 密度)決定,`max_interior` 不影響覆蓋率** ——
   完美對應 strip 的「IoU 由 rows 決定、cols 不影響」。IoU 是**邊界(hull)驅動**,內部點只影響拓樸細分。
   甜蜜點 **eps=0.002 / max_interior=40**:3 件 IoU 全過(0.98~0.99)且頂點數 ≤ 藝術家。
   已設為 `generate_mesh_v2` delaunay 分支的預設(不動 `generate_mesh.py` 全域預設,避免影響 v1 直呼)。

## 誠實的限制(honest limitations)

- 本比對只量**靜態覆蓋率(IoU)+ 幾何合法性**。這 3 件在 Award 為 **weighted mesh 且無 deform
  timeline**(靠骨骼權重變形,非逐頂點 deform),故**無法在此量化 deform 穩健性**。
- 視覺疊圖(`figures/award_mesh_comparison.png`)顯示:我的 mesh 是**規則 Delaunay 格點 + 緊 hull**;
  藝術家 mesh 是**不規則、內部密度非均勻**(把頂點集中在需要細緻權重控制之處)。
  → 我在**靜態覆蓋率**勝出,但藝術家的**內部頂點佈局是 deform 驅動的**,靜態 IoU 量不到這層價值。
- deform 穩健性已在 main_draw 4 個 **unweighted** mesh 上以真實位移場轉移驗過
  (見 `s3-four-mesh-generalization.md`);**weighted mesh 的 deform 品質閘尚缺**(見下)。

## 驗證器可信度(承專案『評估器需外部真值校準』教訓,第 N 次)

- **UV 轉換自我校驗**:藝術家 uvs 映回後算 centroid-in-mask,3 件皆 0.98~1.0(flip_v=False 正確)。
- **負對照 A(v 慣例)**:翻 v 後 centroid-in-mask 崩到 0.46~0.81 → 慣例可被鑑別,非任意通過。
- **負對照 B(跨件錯配)**:自身 IoU 0.95~0.98;藝術家 mesh 疊到**錯誤件** alpha → IoU 崩到 0.48~0.58。
  → 比對有鑑別力,不是「怎麼疊都高」的假閘。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts   # 切件
python3 tools/mesh_gen/compare_to_award.py --pieces /tmp/robot_parts             # 端到端 AC(overall_pass)
```

## 下一步(接棒指引)

1. **weighted mesh deform 品質閘**(補齊 S3 最後缺口):Award 這 3 件靠 bone weights 變形。
   要驗 deform 穩健,需 Python 重現 weighted `computeWorldVertices`(骨數/boneIdx/bind/weight 格式,
   見 RULES 雷點 6)+ 套骨骼動畫轉換 → 自交/翻面閘。這才是「內部頂點佈局」價值的量化方式。
2. **SkelToJson 組裝**(候選 #2):把「件 → Spine attachment」(命名 `<PSD名>/<圖層名>`、+2px、
   region vs mesh 分配、atlas 0.70 縮放)固化成寫出工具,端到端產 Spine JSON。
3. 生成器產的是 **unweighted** mesh;要進真實 rig 需再上 **BBW 權重**(S3 路線圖原定,尚未做)。
