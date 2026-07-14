# S4→S3 端到端:PSD 件 → 生成 mesh → 對照真實生產 mesh(Award)

- **結論**:把 `robot_parts.psd` 的 3 個「在 Award 中是 mesh」的件(光暈/身體/左手)切出來,
  餵給 S3 `generate_mesh_v2`(auto),與 Award 藝術家手做 mesh 做**同底 IoU 對照**:
  **3 件全 overall_pass** — 覆蓋率匹配或勝過藝術家、頂點數更精簡、拓樸乾淨。
  這是第一次把「S4 切件 → S3 生成 mesh」端到端跑在**真實生產標的**上並對真值驗收。
- **信心**:高(對真實 Award 生產 mesh 逐件對照;UV 座標系經 4 變體實測確認;同一 mask、同一 IoU 函式 apples-to-apples)。
- **階段**:第 2 階段 / S3+S4 整合(里程碑)。
- **工具**:`tools/mesh_gen/validate_psd_to_mesh.py`(可重現);圖 `figures/s4s3-psd-to-mesh-vs-award.png`。

## 對照結果(margin 0.02)

| 件 | mode | gen IoU | artist IoU | gen 頂點 | artist 頂點 | gen 三角 | artist 三角 | pass |
|---|---|---|---|---|---|---|---|---|
| 光暈 | delaunay-v1 | 0.933 | 0.949 | 35 | 78 | 49 | 76 | ✅ |
| 身體 | delaunay-v1 | **0.966** | 0.948 | 60 | 98 | 97 | 154 | ✅ |
| 左手 | delaunay-v1 | 0.964 | 0.977 | 59 | 80 | 97 | 116 | ✅ |

- **身體覆蓋率反勝藝術家**(0.966 > 0.948);光暈/左手在 margin 內。
- 3 件生成頂點數皆 **< 藝術家**(35/60/59 vs 78/98/80)→ 更精簡、非以量取勝。
- 拓樸全乾淨:0 退化 / 0 孤兒 / 三角重心 100% 在 mask。

## 關鍵判定與座標系驗證

- **這 3 件在 Award 皆 weighted mesh、且無 deform timeline**(`has_deform_timeline=false`)
  → 靠骨骼權重變形,非逐頂點 deform。故對這些件,**逐頂點 deform 耐受閘不適用**;
  真值是「輪廓覆蓋率 + 精簡度」,而 `generate_mesh_v2` auto 對這種低長寬比 blob 會回退
  **v1(Delaunay,覆蓋率導向)** —— 正好是對的工具。(deform-bearing 的窗簾/陰影才走 v2 strip。)
- **UV 座標系(推翻舊假設)**:舊 STATE 記「Award mesh uvs 為 atlas UV,需先轉 region 局部」。
  實測:Award mesh 的 `uvs` **已是 region-local 0..1**(每件各自 span ~0..1),
  "as-is" 直接對 PSD 件 alpha IoU 0.95/0.95/0.98,而 flipX/flipY/flipXY 皆 0.4~0.76
  → **as-is 唯一正確,不需翻轉/轉座標**。(Spine JSON 匯出的 mesh uvs 即 region-local;
  atlas 貼圖 UV 由 loader 在載入時重映。)

## 觀察 / 局限

- 光暈是**全 hull(78 點)的柔性發光輪廓**;v1 以 `epsilon_frac=0.008` 簡化掉左上觸角尖端的
  羽化細絲(見圖 cyan 缺角)→ 0.933 略低於藝術家 0.949 但仍過 margin。若要更貼,可對
  高羽化件降 epsilon;但用更少頂點過閘本身是優點,故不追加迭代。
- 本 AC 只驗**幾何**(切件 alpha 已於 s4 knowledge 對 atlas texture 驗過同素材,alpha-IoU 0.92~0.99)。
  尚未做:把生成 mesh 寫回 Spine JSON(需權重/骨綁 → 下一步 SkelToJson)。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd -o /tmp/robot_parts
python3 tools/mesh_gen/validate_psd_to_mesh.py            # all_pass=true (exit 0)
```
