# S3 weighted mesh 骨綁權重 + 變形平滑度真值閘(補上唯一未驗維度)

- **結論**:新增 weighted-mesh 骨綁權重能力(**有界調和權重 / bounded harmonic weights**,BBW
  在純 CPU 上可證有界＋單位分解的主幹形式),並以 Award 生產 spine 的 **3 個真實藝術家 weighted mesh**
  (光暈/左手/身體)為真值,量化「骨骼變形平滑度」——**5 條 AC × 3 件全 PASS**。
  這補上了 `s3-robot-mesh-vs-award.md` 誠實標記的**唯一未驗維度**(靜態 IoU PASS ≠ 變形品質對等)。
- **信心**:高。真值 = 藝術家手綁權重 + 真實骨架 FK 重建幾何;含自一致性、雙向對照、負對照。
- **階段**:第 2 階段 / S3(里程碑:weighted mesh 變形品質首次對真實美術權重量化驗收)。
- **工具**:`tools/mesh_gen/weighted_mesh.py`(能力)+ `tools/mesh_gen/validate_weights.py`(真值閘)。

## 標準指令

```
python3 tools/mesh_gen/validate_weights.py   # 3 件 × 5 AC 全 PASS → exit 0
```

## 方法

1. **FK**:`compute_bone_world` 由 Spine 3.8 `bones` 陣列(local x/y/rot/scale + parent 樹)
   算 setup-pose 世界變換(2×2 + 原點)。root=identity;shear=0。
2. **重建幾何**:`reconstruct_setup` 由藝術家 weighted vertices(`[n, boneIdx,bx,by,w, ...]`)
   還原每頂點 setup 世界座標 = Σ w·boneWorld(bind)。**mesh 與 bone origin 同在 Award 骨架空間 → 免 frame 轉換。**
   驗證:重建 span 對 3 件 ≈ 宣告 width/height(左手 257×216 vs 259×217)。
3. **有界調和權重**:`harmonic_weights` 用**餘切 Laplacian**(鈍角截負保正定/最大值原理)解每 handle
   的調和場,Dirichlet BC = seed 頂點 w=1、其餘 handle seed w=0。
   - 由**最大值原理** → 每權重自動 ∈ [0,1](有界);
   - 各 handle BC 互斥且覆蓋所有 seed + 調和唯一性 → 逐列和 ≡ 1(**單位分解 partition of unity**);
   - 調和 = 給定 BC 的 **Dirichlet 能量最小**內插(內部最平滑)。
4. **LBS 變形**:`deform` 每頂點 = Σ_h w_h · xform_h(v)。合成 pose 用**鑑別性**設定
   (每骨繞自身原點旋不同角度+不同平移),使權重指派強烈影響變形場。

## AC 與量化結果(3 件全 PASS)

| AC | 判準 | 光暈(78v/4骨) | 左手(80v/2骨) | 身體(98v/3骨) |
|---|---|---|---|---|
| AC1 自一致 | identity pose → 誤差≈0 | 5.7e-14 ✅ | 5.7e-14 ✅ | 5.7e-14 ✅ |
| AC2 有界+單位分解 | w∈[0,1] 且 \|Σw−1\|<1e-6 | ✅(1e-16) | ✅ | ✅ |
| AC3 平滑度 | Dirichlet ours ≤ art×1.10 | 0.0454≤0.0480 ✅ | 0.0046≤0.0076 ✅ | 0.0168≤0.0263 ✅ |
| AC4 變形一致 | anchor RMS/diag ≤ 0.12 | 0.018 ✅ | 0.038 ✅ | 0.027 ✅ |
| AC5 負對照 | 隨機權重 RMS ≫ 我方×1.5 | 0.147≫0.018 ✅ | 0.092≫0.038 ✅ | 0.132≫0.027 ✅ |

視覺證據:`knowledge/figures/s3_weighted_bbw.png`(身體:setup/藝術家/harmonic/random 變形線框 +
`4_LEG3` 權重熱圖 藝術家 vs harmonic)。harmonic(橙)緊貼藝術家真值(綠);random(紅)自交撕裂。

## 兩種 seed 模式(誠實界定)

- **anchor(方法驗證,閘採用)**:seed = 藝術家「純區」頂點(某骨 w≥0.9)。這是驗證**內插方法**
  是否合格 —— 給定與藝術家相同的硬指派,harmonic 過渡帶是否平滑且變形接近。anchor RMS/diag 0.018~0.038。
- **auto(實際使用,一併回報)**:seed = 每骨最近的 mesh 頂點(**無藝術家真值時的預設路徑**,
  供新生成 mesh 用)。auto RMS/diag 0.051~0.087 —— 較 anchor 大(seed 位置非藝術家指派)但仍
  遠優於負對照,證明「純靠骨原點幾何」也能產出合理權重。

## 關鍵發現

1. **有界調和權重 = BBW 的 CPU 可解主幹**:餘切 Laplace 解即得有界+單位分解+平滑,
   不需 BBW 完整的 biharmonic + 不等式約束二次規劃。對三角網格足以量化變形平滑度。
2. **AC3 嚴格不等式對軟邊件不成立**:光暈羽化帶藝術家錨點非全純(w≈0.9 非 1),藝術家對此並非
   相同 BC 的可行解 → harmonic 可能略高(光暈 +4%)。故判準用「相當或更平滑,容差 10%」;
   身體/左手 harmonic 嚴格更平滑(−30%/−34%)。
3. **鑑別性 pose 是負對照的前提**:若各骨同角度繞近鄰原點旋轉 ≈ 剛體同動,隨機權重也不會差很多
   (初版 AC5 誤 fail)。改成每骨不同角度+平移後,隨機權重 RMS 飆到我方 5~8 倍。
4. **重建即免費驗 FK**:重建 span ≈ 宣告 region w/h,順帶確認 FK/bind 解析正確。

## 對照先前限制的閉合

`s3-robot-mesh-vs-award.md` 標:「靜態 IoU PASS ≠ weighted 骨骼變形平滑度對等,需 BBW 權重能力補齊」。
本次即補齊該點:對同 3 件,weighted 變形品質(平滑度 AC3 + 變形一致 AC4 + 負對照 AC5)全對真值 PASS。

## 下一步候選

- **接上 generate_mesh_v2**:目前閘用「重建幾何 + 藝術家骨」驗方法;下一步把 auto 權重接到
  S3 自產 mesh + `build_spine` 輸出的骨,產出**帶權重的可載入 weighted mesh**(端到端 SkelToJson weighted)。
- **內部取樣密度 ↔ 變形平滑度**:美術身體用 98v 密內部點服務平滑;量化「內部點數 vs Dirichlet/變形誤差」曲線,
  給 generate_mesh_v2 一個「依變形需求決定內部密度」的旋鈕。
