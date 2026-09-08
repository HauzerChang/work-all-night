# S1 件繞關節 pivot 的一般仿射變換(非均勻 scale / shear,G-4)

> 里程碑 2026-09-08(session,candidate G-4)。把 0i(繞 pivot **轉**)/ G-3(繞 pivot **均勻縮放**)
> 推廣到**非均勻 scale(sx≠sy)與 shear** —— 此時 bone local M 是**一般仿射、不再是相似變換**,
> 但同一條補償公式 `Δ=(M−I)(O−P)` 仍讓關節 pivot P 為**精確不動點**。
> 工具:`tools/analyzer/pivot_rotation.py`(擴充)、`validate_shear_pivot.py`、圖 `figures/s1_shear_pivot.png`。

## 動機(接 0i / G-3 的最後一塊仿射)

- 0i:件繞關節 pivot **轉**,M=R(θ),補償 `Δ=(R−I)(O−P)`。
- G-3:件繞關節 pivot **縮放**,M=R·diag(s,s)(均勻),`Δ=(M−I)(O−P)`;均勻 scale 約 pivot 為
  **相似變換** `∀x |world(x)−P| = s·|x−P|`,G-3 的 AC5 即靠此等式成立來證「等比繞 pivot」。
- **缺口**:Spine bone 還有 **shear**(shearX/shearY)與**非均勻 scale**(sx≠sy)——squash-and-stretch、
  斜向拉伸等表情會用到。此時 M **不再是相似變換**,G-3 的 `|world(x)−P|=s|x−P|` 判準**必然失效**
  (各方向拉伸比不同)。STATE 建議 (G-4):「Δ 公式已通用,只差非均勻 scale 的相似性 → **仿射保形**驗證」。

## 數學:Δ 公式對「任意」2×2 M 都讓 pivot 不動

補償推導完全不依賴 M 是旋轉/相似;純代數:件貼在 bone 上,pivot 的附著局部點 ℓ_P=P−O(setup M=I),
加補償 translate Δ 後世界座標 = (O+Δ) + M·(P−O)。要它 == P:
```
Δ = P − O − M(P−O) = (M − I)(O − P)          ← 對任意 2×2 M 成立
```
代回任意附著點 x(局部 x−O):
```
world(x) − P = (O+Δ−P) + M(x−O) = M(O−P) + M(x−O) = M·(x − P)     ← 仿射保形(精確)
```
**關鍵洞見**:相似性 `|world(x)−P|=s|x−P|` 只是「M=s·R」的特例;一般仿射下該等距-類比**壞掉**,
但更弱、更本質的 **`world(x)−P = M·(x−P)`** 對任意 M 精確成立。這就是 G-4 用來取代 G-3 相似 AC 的判準。

## 真實 Spine 3.8 bone local 矩陣(含 shear)

`transform_matrix_full(θ, sx, sy, shx, shy)` 實作 `Bone.updateWorldTransform`(TransformMode.Normal):
```
a = cos(θ+shx)·sx     b = cos(θ+90+shy)·sy
c = sin(θ+shx)·sx     d = sin(θ+90+shy)·sy      M = [[a,b],[c,d]]
```
- **shx=shy=0 逐位元退化回 G-3 的 `transform_matrix`**(cos(θ+90)=−sin θ、sin(θ+90)=cos θ)→ 0i/G-3 零回歸。
- **這是真實 Spine shear,不是天真 unit-shear**:純 shearX φ 的 `det = cos φ`(shear 同時改變面積),
  而天真 `[[1,tanφ],[0,1]]` 的 det≡1。閘 AC6(b) 以 `det==cosφ` 鎖定實作的是**真 Spine 定義**(負對照:
  天真 unit-shear det 差 0.5 @ φ=60°)。

## 實作(全部 additive,0i/G-3 路徑逐位元不變)

`pivot_rotation.py` 新增:
- `transform_matrix_full(deg,sx,sy,shx,shy)` — 真實 Spine local 2×2。
- `pivot_delta_affine(m,O,P)` — 由完整 2×2 tuple 算 Δ=(M−I)(O−P)。
- `pivot_channels_affine(rotate,scale,shear,O,P,dt,existing_translate)` — 三通道(任一/多)→
  密網格 M=`transform_matrix_full`、Δ=`pivot_delta_affine`;`shear=None` 時退化 == G-3 的 `pivot_channels_srt`。
- `apply_pivots(..., include_shear=False)` — 新旗標(預設 False → 走 0i/G-3 路徑,byte-for-byte);
  True 時用仿射路徑,補償有 `rotate`/`scale`/`shear` 的 bone。

## 驗收 `validate_shear_pivot.py`(真實 Award 左手 + 推得肩 pivot,|O−P|≈117px,7 AC 全 PASS)

| AC | 內容 | 實測 |
|---|---|---|
| AC1 | **非均勻 scale**(1.6,1.2)pivot 不動點 | 0.0001px(< 0.5;負對照繞件中心 69.3px) |
| AC2 | **shear** 25° pivot 不動點 | 0.0122px(< 0.5;負對照 49.9px) |
| AC3 | **仿射保形**(關鍵幀)`world(x)−P==M·(x−P)` | 4.3e-4px(< 2e-3,純關鍵幀量化,非公式限制) |
| AC4 | **相似性壞掉**(鑑別)anisotropy=max\|Md\|−min\|Md\| | 均勻 4e-16 / 非均勻 0.40 / shear 0.43(≥0.10) |
| AC5 | identity 介面(首尾幀 Δ=0) | 0/0px |
| AC6 | 矩陣正確性 | (a) shear=0 退化差 2e-16;(b) det==cosφ 差 0(天真差 0.5);(c) shear=None==srt 路徑 |
| AC7 | 端到端 `apply_pivots(include_shear=True)`(rotate+scale+shear) | 有限/無縫/pivot 殘差 0.0495px vs 負對照 93.4px |

**AC4 是本閘的 crux**:anisotropy(= M 的奇異值差)在均勻 scale 下為 0(相似,和 G-3 一致),
非均勻 scale 與 shear 下顯著 >0 → 證此閘測的**確實是一般仿射、不是 G-3 相似的重驗**;若閘還在驗
`|world(x)−P|=s|x−P|` 就會對非均勻/ shear 假陰性。

## 關鍵發現 / 踩雷

1. **同一條 Δ=(M−I)(O−P) 貫穿 0i→G-3→G-4**:0i(M=R)、G-3(M=R·sI)、G-4(M=真實 Spine local 含 shear/
   非均勻 scale)只差 M 的填法;不動點性質是純代數,和 M 是否相似無關。
2. **相似 → 仿射,判準要換**:G-3 用等距-類比 `|w−P|=s|x−P|`;G-4 必須改用**仿射保形 world−P=M(x−P)** +
   **anisotropy** 鑑別子。誠實地說,shear/非均勻 scale 下「等比」概念不存在,硬套會假陰性。
3. **真 Spine shear ≠ 天真 unit-shear**:`det(pure shearX φ)=cos φ`(改面積),用 det 鎖定實作正確性。
4. **AC3 的殘差是關鍵幀量化,不是公式誤差**:角度/shear 存檔捨入 4dp(≈5e-5°)經件點偏移 ~350px 放大到
   ~4e-4px;數學上 world−P=M(x−P) 精確為 0。仍比 0.5px 不動點門檻緊 250×。
5. **honest boundary(生成器側)**:此能力補齊的是**幾何/公式 + 閘**;目前 `gen_animations` 尚未產出 `shear`
   通道(產線的主秀節拍只用 rotate/scale)。「公式/閘就緒 ≠ 生成器接上」再現——當某節拍需要 shear
   (如斜拉 squash)時,只需讓 beat 產 shear 通道、build 帶 `include_shear=True` 即接上(管路已通,見 AC7)。

## 回歸(全綠)

`validate_pivot_rotation`(0i,7AC)、`validate_scale_pivot`(G-3,7AC)、round-trip `validate_build`
對 `--scale-pivot` build(overall_pass、premult MAE 0.031、setup 不變)、以及 tier/priors/beat 系列
(`validate_tier_variants`/`tier_combo_count`/`priors_*`/`more_beats`/`beat_templates`/`cascade`/`deform_gen`)全 PASS。

## cap / skill

新增 cap `shear_pivot_affine` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
