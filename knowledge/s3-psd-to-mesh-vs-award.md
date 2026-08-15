# S3+S4 端到端驗收 — PSD 件 → 生成 mesh → 對照真實生產 mesh(Award, ground truth)

- **結論**:把 S4 切圖與 S3 生成串起來,對**真實生產標的**驗收通過(里程碑)。
  用 `robot_parts.psd` 的 3 個 mesh 件(光暈/身體/左手),`generate_mesh_v2` 生成的 mesh
  對「同一張 PSD alpha」的 **coverage IoU 與藝術家手做 mesh 持平(±1.5%,身體反超)**,
  且**頂點數少 26–55%**。3 件全 `piece_pass`,工具 `validate_psd_mesh_vs_spine.py` exit 0。
- **信心**:高。真值 = 真實 spine(`Award.json`)藝術家 mesh;內建正/負對照確認指標可信。
- **階段**:第 2 階段 / S3×S4 整合(從「對 main_draw 內部一致」升到「對外部生產真值」)。

## 為何用 coverage IoU 當真值指標(不是 deform 閘)

機器人這 3 件在 Award 是 **weighted(骨骼權重驅動)且無 deform timeline**
(`vertices` 長度 ≠ 2×nv;9/12 anim 對這些 slot 皆無 `deform`)。它們靠骨骼變形,
不是逐頂點 deform → 「真實位移場轉移」閘對它們 **N/A**。可比的真值就是
「藝術家 mesh 對自身素材的覆蓋率」,以及頂點預算與格式合法性。

## 結果(`python3 tools/mesh_gen/validate_psd_mesh_vs_spine.py`,margin=0.02)

| 件 | 生成 IoU | 藝術家 IoU(真值) | Δ | 生成 nv/tris/hull | 藝術家 nv/tris/hull | 省頂點 | 負對照(翻Y) |
|---|---|---|---|---|---|---|---|
| 光暈 | 0.9331 | 0.9486 | −0.0155 | 35/49/16 | 78/76/78 | 55.1% | 0.4264 |
| 身體 | **0.9660** | 0.9477 | **+0.0183** | 60/97/20 | 98/154/40 | 38.8% | 0.6038 |
| 左手 | 0.9642 | 0.9768 | −0.0126 | 59/97/19 | 80/116/42 | 26.2% | 0.5896 |

- 全部三件都在 margin 內達到藝術家覆蓋率;**身體反超藝術家**。
- 藝術家自身 IoU 也只有 ~0.95(非 1.0)—— 這是**低多邊形逼近曲線輪廓的自然上限**,
  生成 mesh 正好貼著這個上限。
- 三件都用**更少頂點**達到同覆蓋率(「同覆蓋、更精簡」)。

## 評估器可信度(內建雙保險,每件都測)

- **正對照**:藝術家 mesh 對自身 PSD 素材 IoU 0.948~0.977(高、自一致)→ 指標有意義。
- **負對照**:同一藝術家 mesh 但 uv_y→1−uv_y(上下翻)→ IoU 崩到 0.43~0.60,
  跌幅 0.34~0.52 → **指標對「錯位」有鑑別力**,非任何形狀都給高分。
- 兩者皆過才允許下 pass 判定(延續「先驗評估器再判定」原則,避免第 4 次 miscalibration)。

## 座標/校準要點(可重用)

1. **Award mesh `uvs` 是 region-local(0..1)**、且為**未旋轉的原圖朝向**;直接 `uvs×(W,H)`
   即可對 PSD 全解析度 alpha 渲染比對(atlas 的 `rotate:true` 不影響 regionUVs)。
2. **y 朝向**:uv_y 直接對應影像列(top-down),與生成器 `to_spine` 的 `y/H` 慣例一致
   (翻轉版本 IoU 崩掉可反證)。
3. **margin=0.02** 吸收跨源雜訊:比對用的 PSD 件(全解析度)與藝術家 mesh 當初依據的 atlas 件
   (0.70 縮小 + 羽化)為同素材但非同像素(前測 alpha-IoU 0.92~0.99)。
4. 三件 aspect≈方形 → `generate_mesh_v2` auto 落回 **v1 Delaunay**(strip 是給高瘦 deform 件的);
   對骨骼驅動、非 deform-bearing 的件,輪廓 Delaunay 拓樸正合適。

## 限制 / 未竟(誠實留痕)

- 只驗**拓樸/覆蓋**,未產**權重**:生成的是 unweighted mesh;要 drop-in 進 Award 這種
  weighted 件仍需綁權重(S3 的 BBW,尚未做)。
- 光暈藝術家用 78 個 hull-only 頂點(密邊界)做柔光暈;生成 35 頂點覆蓋率持平,但更密的邊界
  可能讓引擎內邊緣漸層更順 —— 屬主觀畫質,非覆蓋率缺陷。
- deform-robustness 對這批件 N/A(weighted、無 deform timeline);curtain 類 deform-bearing 件
  仍走 v2 strip + 真實位移場閘(見 `s3-four-mesh-generalization.md`)。

## 可重現

```
python3 tools/mesh_gen/validate_psd_mesh_vs_spine.py \
    --psd assets/robot_parts.psd --spine assets/Award.json --prefix 機器人拆件
# → overall_pass: true (exit 0);3 件 piece_pass 全 true
```
