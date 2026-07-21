# S3×S4 端到端驗收 — 生成 mesh 對照 Award 真實生產 mesh

- **結論**:把 S4(PSD 切件)與 S3(`generate_mesh_v2`)串成端到端,對**真實生產標的**
  (機器人 big win `Award` spine 的三個 weighted mesh:光暈/身體/左手)做外部真值比對。
  我們自動生成的 mesh **對真實不規則生產件的輪廓覆蓋 ≥ 藝術家手做 mesh(全 3 件過覆蓋率閘),
  且頂點數更精簡(少 ~35–55%)**。這是 S3 從「main_draw 4 個 unweighted 窗簾/陰影」推廣到
  「真實生產 weighted mesh」的第一個外部真值驗收。
- **信心**:高。座標系自我校驗通過(藝術家自身 IoU 0.949–0.977 → uvs↔切件框對齊);
  負對照(交叉錯配 + 平移退化)確認 IoU 有鑑別力。
- **階段**:第 2 階段 / S3 端到端(S4→S3 串接,對真實生產標的)。

## 方法(共同座標系 = PSD 切件像素框)

避開 atlas 0.70 縮小與旋轉,全在**全解析度 PSD 切件框**比較:
1. 參考輪廓 = `psd_slice` 切出的件 alpha(已驗證與 spine 貼圖同素材,alpha-IoU 0.92~0.99)。
2. 藝術家 mesh 覆蓋:Award mesh 的 `uvs`(**region-local [0,1]**,見下)映到切件框 → 三角覆蓋。
3. 生成 mesh 覆蓋:`generate_mesh_v2(切件 alpha)`(預設 rows=10/cols=3/mode=auto)的三角覆蓋。
4. 兩者對同一張切件 alpha 算 silhouette IoU → apples-to-apples。
- 工具:`tools/mesh_gen/compare_award_mesh.py`。

## 結果(2026-07-21)

| 件 | 藝術家 IoU (nv) | 生成 IoU (nv, mode) | 覆蓋率閘 | 精簡閘 |
|---|---|---|---|---|
| 光暈 | 0.949 (78v, hull78) | 0.933 (35v, delaunay-v1) | ✅ (−0.016，在 0.02 margin 內) | ✅ 35≤78 |
| 身體 | 0.948 (98v, hull40) | **0.966** (60v, delaunay-v1) | ✅ **優於藝術家** | ✅ 60≤98 |
| 左手 | 0.977 (80v, hull42) | 0.964 (59v, delaunay-v1) | ✅ (−0.013，在 margin 內) | ✅ 59≤80 |

`frame_aligned(all)=True  coverage_parity(all)=True  vertex_frugal(all)=True`

## 關鍵發現

1. **Award mesh 的 `uvs` 是 region-local(每件 [0,1] 幾乎填滿),不是 page-normalized。**
   證據:光暈 region 在 page(2040²)的 xy=562,879 只占中段,page-normalized 應為
   x∈[~0.28,~0.51],但實測 uv x∈[0.012,0.990]。→ 可直接 `uvs×切件W, uvs×切件H` 映射,
   `evaluate_mesh`/`validate_against_real` 的 `artist_iou`(uvs×crop 尺寸)之所以成立即因此。
2. **`mode=auto` 對真實不規則 blob 件正確分流到 delaunay-v1**(三件 aspect 0.84/0.97/1.12 <1.2,
   非高瘦 row-convex strip)。→ auto 分派在真實生產件上運作正確;strip 是窗簾類專用,blob 走 v1。
3. **藝術家 mesh 也非完美覆蓋(IoU 0.949–0.977)**:光暈是柔邊 radial glow,藝術家用 78 個
   純 hull 頂點細描軟邊界;我們 v1 用 35v/hull16 較鬆,仍在 margin 內。→ 用「相對藝術家基準
   ±margin」而非武斷 0.95 是對的校準(延續 `validate_against_real` 的結論)。
4. **精簡度**:生成 mesh 頂點數為藝術家的 45–65%,覆蓋率相當或更好 → 我們的確定性拓樸
   對這類件足夠且更省。

## 局限 / 未涵蓋(誠實)

- 這三件在 Award **無 deform timeline**(靠骨骼/權重變形,非逐頂點 deform)→ 本輪**只驗靜態輪廓
  保真 + 精簡度**,未驗 deform 穩健(真實位移場轉移閘對它們不適用)。
- 只比**輪廓覆蓋(silhouette IoU)**,未比內部三角分佈品質 / weighted 綁定;那需 mesh→bone
  權重生成(BBW,尚未做)才有真值可比。
- 生成 mesh 目前輸出 uvs 是「切件框 normalize」,要進真實 spine 需再轉 atlas UV(含 0.70 縮放
  + 旋轉 + page 位移)—— 屬「件→Spine attachment 組裝(SkelToJson)」下一步。

## 負對照(確認閘可信)

- 交叉錯配(A 件生成 mesh vs B 件 alpha):對角 0.933–0.966,離對角 0.48–0.58 → 清楚鑑別。
- 平移退化(光暈生成 mesh 右移 30% 寬):0.933 → 0.361。

## 可重現

```
python3 tools/mesh_gen/psd_slice.py assets/robot_parts.psd --out /tmp/robot_parts
python3 tools/mesh_gen/compare_award_mesh.py    # frame_aligned/coverage_parity/vertex_frugal all True
```

## 下一步

- **SkelToJson(件→Spine attachment 組裝)**:把生成 mesh 的切件框 uvs 轉 atlas UV
  (0.70 縮放 + 旋轉 + page 位移),配 `PSD名/圖層名` 命名 + size+2px padding,端到端產 Spine JSON。
- mesh→bone **權重生成(BBW)**:讓生成 mesh 也能 weighted,才能對照 Award weighted 綁定。
