# S1 candidate (G-4)— 件繞關節 pivot 任意仿射保形(非均勻 scale / shear)

> 里程碑 2026-09-08。補 STATE「下一個 bounded chunk」建議 **(G-4)**:把 0i(繞 pivot **轉**,等距)/
> G-3(繞 pivot **均勻縮放**,相似)的補償推廣到**任意仿射線性部 M**(非均勻 scale sx≠sy、shear)。
> 工具:`tools/analyzer/pivot_rotation.py`(加通用原語)、`validate_shear_pivot.py`(7 AC)。

## 問題(G-3 誠實界定裡標明的缺口)

G-3 的補償 `Δ=(M−I)(O−P)` 用 `M=R(θ)·diag(sx,sy)`,程式路徑已能吃 `sx≠sy`(`pivot_channels_srt`
分開讀 scale.x/scale.y),但**從未驗過**:G-3 的 AC5 是「相似變換」`|world(x)−P|=s·|x−P|`,只在**均勻**
scale(單一 s)下成立。`sx≠sy`(或 shear)時到 P 的距離比不再是單一常數 → 相似性**失效**,G-3 的判準
無法覆蓋。G-3 的知識文件末尾已明記此界:「sx≠sy 的非均勻縮放仍正確補償(Δ 公式通用),但 AC5 相似性
只對均勻 scale 成立」。本塊把「仿射保形」這條**更廣、對非均勻仍成立**的判準補齊。

## 數學(補償對完整仿射群成立)

貼在 bone(setup 原點 O)的局部點 `x−O`,套「translate T + M·local」後世界座標:

```
world(x) = (O + Δ) + M·(x − O),  取 Δ = (M − I)(O − P)
         = O + (M−I)(O−P) + M(x−O)
         = M(x−P) + P
⟹  world(x) − P == M·(x − P)      ∀x,  對**任意** 2×2 M
```

- **不動點**:`x=P` ⟹ `world=P`(P 固定,與 M 無關)。
- **件相對 P 依 M 仿射變形**:非均勻 scale = 沿兩軸不同倍率繞 P 拉伸;shear = 繞 P 剪切。
- **退化**:M 均勻 scale `sI` ⟹ `|world−P|=s|x−P|`(相似,G-3 AC5);M=R ⟹ 等距(0i);M=I ⟹ Δ=0(identity)。

**相似性 vs 仿射保形(本塊的判別核心)**:定義各件點「到 P 距離比」`r_k=|world(x_k)−P|/|x_k−P|`。
均勻 scale → 所有 `r_k` 皆 = s(離散度 ≈ 0);**非均勻 scale / shear → `r_k` 隨方向不同(離散度 > 0)**
→ 沒有單一 s → G-3 相似 AC 會 FALSE。但仿射恆等式 `world(x)==M(x−P)+P` 逐點殘差仍 ≈ 0(TRUE)。
「離散度大 + 仿射殘差小」正是 G-4 相對 G-3 的判別點。

實作(`pivot_rotation.py`,新增通用原語,**既有函式逐位元不變**):
- `pivot_delta_matrix(M, O, P)` = `Δ=(M−I)(O−P)`,M 為任意 `(m00,m01,m10,m11)`;`pivot_delta`/
  `pivot_delta_full` 皆為其特例(後者改為委派 → G-3 路徑逐位元不變,已回歸驗證)。
- `transform_matrix_full(θ, sx, sy, kx=0, ky=0)` = `R·K·diag(sx,sy)`,`K=[[1,kx],[ky,1]]`(shear);
  `kx=ky=0` ⟹ 同 `transform_matrix`(向後相容)。`matmul`/`shear_matrix`/`apply_matrix` 輔助。
- 端到端仍走既有 `apply_pivots(include_scale=True)` → `pivot_channels_srt`(吃 rotate+scale.x/.y,
  故涵蓋非均勻 scale;shear 目前無 bone 通道,以靜態 M 經 `pivot_delta_matrix` 直驗)。

## 驗收(`validate_shear_pivot.py`,7 AC 全 PASS)

真值 = 真實 Award **左手**世界輪廓(42 頂點)+ `infer_pivots` 推得**肩 pivot**(|O−P|=117px),
純 Python 逐點量測:

| AC | 內容 | 實測 | 門檻 |
|---|---|---|---|
| AC1 | 非均勻 scale `diag(1.6,0.7)` 不動點殘差 | **0.0000px** | <0.5 |
| AC2 | **負對照**:繞件中心(Δ=0)pivot 位移 | **69.5px** | ≥10, >20×AC1 |
| AC3 | **crux 仿射保形**:∀點 \|world(x)−(M(x−P)+P)\| | **0.0000px** | <0.5 |
| AC4 | **crux 相似性失效**:非均勻「到P距離比」離散度(std) | **0.28**(相似 FAIL);正對照均勻 M **0.0000** | ≥0.05 / <1e-3 |
| AC5 | **純 shear** `[[1,0.35],[0.2,1]]`:不動點+仿射+負對照+離散度 | 0/0 / **24.3px** / **0.20** | 全過 |
| AC6 | identity M=I ⟹ Δ=0 且∀件點零位移 | **0 / 1.4e-14px** | <1e-6 |
| AC7 | **端到端** `apply_pivots(include_scale)` 非均勻 scale(sx≠sy)+rotate:逐幀 pivot 不動+仿射保形;負對照未套用會動 | 0.025px / 0.0001px vs **71.9px** | <0.5 |

**負對照/正對照設計**:AC2/AC5 負對照 = 同 M 不補償(繞件中心)→ pivot 漂;AC4 **正對照** = 均勻 scale
使離散度回 0(證離散度判別子確能分辨均勻/非均勻,而非恆為正);AC7(d) = `apply_pivots` 前的 raw 通道
(繞件中心)→ 漂 71.9px。AC7 是 `pivot_channels_srt` 在 **sx≠sy** 下的**首次端到端驗證**(G-3 端到端只走 sx==sy)。

**回歸(全綠)**:0i `validate_pivot_rotation`、G-3 `validate_scale_pivot`(委派後逐 AC 不變)、
`validate_anim`(+`--selftest`)對 `--scale-pivot` build overall_pass、round-trip `validate_build`
對 `--scale-pivot` build overall_pass;`validate_more_beats`/`beat_templates`/`cascade`/`priors*`/
`tier_variants`/`tier_combo_count` 皆 overall_pass。

## 關鍵發現

1. **一條公式吃整個仿射群**:`Δ=(M−I)(O−P)` 對**任意** 2×2 M 給 `world(x)−P==M(x−P)`。0i(等距)、
   G-3(相似)只是 M=R、M=sI 的特例;非均勻 scale、shear 都不需新公式,只需把 M 餵進去。
2. **相似 ⊊ 仿射,離散度是分水嶺**:0i 判準「距離不變」、G-3 判準「距離等比」都預設**各向同性**;
   非均勻 M 各向異性 → 到 P 的距離比隨方向而異(離散度 >0)。正確判準退回**仿射恆等式**
   `world(x)==M(x−P)+P`,對所有 M 成立。用「距離比離散度」既證相似性失效、又反證仿射保形。
3. **程式路徑早就通、判準才補上**:`pivot_channels_srt` 分讀 scale.x/.y,`sx≠sy` 一直能算;缺的是
   一條對非均勻仍為真的 AC(又一「能力就緒 ≠ 驗過」)。AC7 首次在 sx≠sy 下端到端證明它正確。

## 誠實界定 / honest boundary

- 閘驗**仿射不動點/保形**(客觀:P 是否固定、件是否依 M 繞 P 仿射變形)。「拉多扁、剪多斜」屬美術
  微調(RULES **A 類**),留使用者。
- **生成器目前不產非均勻 scale / shear**:`gen_animations` 的 In/Out/pulse/主秀 beat 全出**均勻** scale、
  無 shear 通道。故 AC7 以合成的 sx≠sy 節拍、AC5 以靜態 shear M 驗證 —— 補償**已證對完整仿射群正確**,
  未來若加「拉伸/剪切」節拍(如 squash-stretch 誇張、風吹傾斜)即自動覆蓋,無需再改補償。
- pivot 真值仍 S5 接觸縫**草案**;Award 僅機器人一件可拆肢體 rig(多 rig 真值屬使用者資源)。
- 只在**非 rig** 下套用;與 `--rig` per-bone 語意去重(G-1)非本塊範圍。
- 故 cap `affine_pivot_keyframe` L2 併入 `spine-anim-forge`,**區塊仍 HOLD**(運動基元先驗、單一真值資產,防固化)。
