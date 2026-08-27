# S3 — weighted mesh 生成器(內部取樣 + heat-diffusion 權重 / BBW 近似)

- **結論**:補上 STATE 候選 2 的最後一塊。`tools/mesh_gen/generate_weighted_mesh.py`:
  輪廓多邊形 → `triangle` 三角化(max-area 控**內部取樣密度**)→ **heat-diffusion 骨綁權重**
  (Baran & Popović 2007「bone heat」,BBW 的純 CPU 稀疏解近似)→ Spine weighted vertices 格式。
  用上一個里程碑的 `weighted_deform_eval` 過同一道閘驗收。**對 Award 機器人不透明結構件(身體/左手)
  4 條 AC 全 PASS**:重建乾淨、真實 Legend 動畫 si=0、變形平滑度 ≈ 藝術家、頂點預算 ≤1.4×。
- **依據/來源**:Award.json 機器人件骨架 + hull 輪廓(真值);`validate_weighted_gen.py` 逐件量化。
- **信心**:高(對真實生產美術 weighted mesh 逐件量化 + 同閘正/負對照已驗)。
- **相關階段**:第 2 階段 S3;候選 2 主體。

## 演算法(heat-diffusion 權重)

解稀疏線性系統 **`(L + H) W = H P`**:
- `L` = cotangent Laplacian(半正定慣例:`L_ii=Σcot`, `L_ij=-cot`)。
- `H` = `diag(scale / d_i²)`,`d_i` = 頂點到最近骨線段距離(線段 = parent_origin→bone_origin,setup 世界);
  `scale` = 中位邊長² 尺度化(穩定條件數)。
- `P` = 最近骨 one-hot 指示。
- **天然滿足 partition of unity**(每頂點權重和=1):因 `L·1=0` → `(L+H)·1=H·1`,故 `W·1≡1`。
- 剪成每頂點至多 k=4 骨(Spine 上限)、重正規化。
- bind 座標 = 頂點經**逆骨變換**(`inverse_transform_point`)投到各骨 setup 局部系 → computeWorldVertices 於 setup 還原原位。

## 驗收結果(validate_weighted_gen.py)

| 件 | 類型 | 藝術家 nv | 生成 nv | si | flip | cv增幅 | ar_std | 判定 |
|---|---|---|---|---|---|---|---|---|
| 身體 | opaque | 98 | **98** | 0 | 0 | 0.000(藝術 0.000) | 0.146(藝術 0.146) | **PASS ✅** |
| 左手 | opaque | 80 | 104 | 0 | 0 | **0.000(藝術 0.004,更平滑)** | 0.150(藝術 0.150) | **PASS ✅** |
| 光暈 | soft | 78 | 207 | 368 | 23 | 0.67 | 0.24 | 記錄(見下) |

- **body 頂點數可精準調到 == 藝術家(98)**;IoU 由邊界多邊形固定,內部密度由 `max_area` 連續控制。
- **left hand 變形比藝術家更平滑**(cv 增幅 0.000 vs 0.004):均勻 Delaunay + 平滑權重之效。
- 圖 `figures/s3_weighted_mesh_gen.png`:藝術家 vs 生成 setup + 變形幀線框,生成拓樸更規則、變形乾淨。

## 誠實界定 / 已知限制

- **軟性加成件(光暈 halo)未追平藝術家**:生成 si=368 vs 藝術家 si=71。光暈綁 4 骨、In reveal 期
  極端張開,藝術家用**手工非均勻拓樸**吸收折疊;我方均勻 Delaunay + heat 權重在此會過度纏繞。
  因 additive 混合下重疊視覺無害(閘已把此類歸為 si-tolerant),**不列硬性 fail**,但明確記為限制。
  → 若要追平:軟件需「沿骨向拉伸的非均勻取樣 + 各向異性權重」,屬後續。
- **左手頂點數(104)略高於藝術家(80)**:受邊界多邊形頂點數下限限制(hull 42 點),仍 ≤1.4× 通過預算 AC。
- **尚未端到端**:生成的 weighted mesh 尚未寫回 `build_spine` 產完整可載入 spine(下一步,達 L3 才 skill 化)。
- 只支援 `transform="normal"` 骨(承 `weighted_deform_eval` 限制)。

## 對 skill 化的影響(完成度機制)

`spine-weighted-forge` 區塊:`bbw_weights` 與 `interior_sampling` 由 L0/L1 → **L2**(不透明件真值驗收)。
但區塊仍 **HOLD**:缺 ≥1 條 L3 端到端(`weighted_end2end`:接 build_spine)。HOLD 理由由「生成器未做」
轉為健康的「待端到端串接」。見 `skills/READINESS.md`。

## 標準指令

```
PYTHONPATH=tools/mesh_gen python3 tools/mesh_gen/validate_weighted_gen.py            # opaque 件全 PASS
PYTHONPATH=tools/mesh_gen python3 tools/mesh_gen/generate_weighted_mesh.py assets/Award.json "機器人拆件/身體" 1500
```

## 下一步

1. **端到端**:把 weighted mesh 生成接進 `build_spine`,產出含 weighted skin 的可載入 spine,round-trip 驗 → 讓 weighted-forge 達 L3。
2. **軟件拓樸**:沿骨向非均勻取樣 + 各向異性權重,追平光暈類。
3. 之後 weighted-forge 併入 `spine-asset-forge` skill。
