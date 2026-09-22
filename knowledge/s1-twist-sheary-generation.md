# S1 — 生成器產 shearY 通道(雙軸對角絞擰 twist,candidate G-4'''''')

> 里程碑 2026-09-22。補上 wobble/squash 系列一路留到現在的**最後一條 shear 通道 honest boundary**:
> 此前所有產 shear 的生成器都 `shearY≡0`;本次讓 `gen_twist` 實際填 shearY,塞滿一般仿射 M 的最後一個自由度。

## 問題(honest boundary)

- G-4'(`gen_wobble`)讓產線第一次產 **shearX** 通道;G-4''''(`gen_squash`)再加耦合非均勻 scale。
- 但兩者都硬寫 `"y": 0.0` —— **shearY 通道從未被任何生成器填過**。
- Spine 3.8 真實 bone local(`transform_matrix_full`)為
  `M = (cos(θ+shx)·sx, cos(θ+90+shy)·sy, sin(θ+shx)·sx, sin(θ+90+shy)·sy)`,
  其中 `shy`(shearY)是一般仿射 M 仍未被生成器驅動的最後一個自由度。pivot 補償公式(G-4)、
  `_world`、`apply_pivots(include_shear=True)` 早已把 `shy` 一路吃進來,但缺一個實際產 shearY 的節拍。

## 解法:gen_twist(斜拉對角絞擰)

運動基元 = **阻尼 shearX 擺動 + shearY = −shearX**(逐幀反相):

- `shearX(τ)`:同 wobble 阻尼擺動 `0→+A→−rA→+r²A→…→0`(繞 0 變號、相繼極值遞減,r=0.5)。
- `shearY(τ)`:= `−shearX(τ)` → 首尾 0(identity 介面),shearY 通道被填。

### 關鍵幾何(為什麼這是「真正的雙軸剪切」而非旋轉)

rot=0、sx=sy=1 時:

```
M = transform_matrix_full(0, 1, 1, +φ, −φ)
  = [[cos φ,  sin φ],
     [sin φ,  cos φ]]          # 對稱矩陣
det(M) = cos²φ − sin²φ = cos(2φ) < 1
```

- **對稱矩陣** = 沿 ±45° 對角的**純剪切**(一對角拉伸、另一對角壓縮);
- `det = cos(2φ) < 1` → 面積隨絞擰縮小(如擰毛巾)→ **真正非相似的一般仿射**(非旋轉、非相似)。
- 對照:若 `shearX == shearY = φ` 則 `M = R(φ)`(**旋轉**,det≡1)—— 即「填了 shearY 卻只是旋轉偽裝」。
  這是本能力最鋒利的負對照:`det ≡ cos(shearX − shearY)`,twist 取 `shearY=−shearX` → `det=cos(2φ)≠1`(真剪切),
  旋轉偽裝取 `shearY=+shearX` → `det≡1`(旋轉)。閘測的是「真剪切」非「有 shearY 即可」。

## 端到端(零改動 pivot 層)

`transform_matrix_full(θ,sx,sy,shx,shy)` 的 `ry=θ+90+shy` 項、`_world` 對 shear 的 `["x","y"]` 內插、
`pivot_channels_affine`/`apply_pivots(include_shear=True)` 對 shear.y 的取樣與寫回**早已就緒**(G-4 補齊)。
故 `build_spine --shear-pivot` 直接把含 shearY 的 twist 端到端補償,件繞關節 pivot 做一般仿射而 pivot 精確不動,
**不需改任何 pivot/矩陣程式碼**。`amplify_bone_tl` 也早已對 shear.y 做 `g*v`(tier 幅度就緒,見 honest boundary)。

## 接線(全 additive)

- `beat_templates.py`:`gen_twist` + `_twist_env` + `TWIST_KEYWORDS` + `DUR["twist"]=0.8`;role→首極值 `_TWIST_SHEAR`。
- `gen_animations.py`:`_DISPATCH["twist"]` + `_CAT_KEYWORDS["twist"]`(關鍵字與其餘節拍無交集,順序不影響)。
- `tier_variants.py`:`twist` 併入 `SHEAR_CATS`(shear-isolation 閘認定合法 shear 產出者);**未併 MAIN_SHOW_CATS**(honest boundary)。
- `genre_priors.py`:`slot_bigwin` 新增 twist beat(additive;Award 真值僅 In/Loop/Out → 列 prior_beats_unused,覆蓋率仍 1.0)。

## 驗收:`validate_twist_gen.py` 6 AC 全 PASS

從先驗庫 → `analyze_target` → **真實 build_spine robot 骨架** → `build_animations` 端到端量:

- **V1** present + shearY 產出(crux):twist beat 直出、finite、有 bone,峰值 |shearY| = 16° ≥ MIN。**產線第一次填 shearY 通道**。
- **V2** 雙軸阻尼振盪:shearX **與** shearY 各首尾 0、繞 0 變號 ≥3、相繼極值嚴格遞減(阻尼),且 shearY==−shearX 逐幀(反相)。
- **V3** identity 介面:sample(0)/sample(dur) rotate/translate/scale identity 且 shearX/shearY 首尾 0(可插 Loop 間)。
- **V4** 非相似一般仿射(crux):峰值絞擰幀 `|1−det|` 最大 0.152(≥ 0.05)→ shearX≠shearY(非旋轉,真對角剪切)。
- **V5** 端到端 pivot 不動:`build_spine --shear-pivot`(真實 robot)pivot 殘差 <0.03px vs 內建負對照(未補償繞件中心)8–30px。
- **V6** 負對照/隔離:(a)**旋轉偽裝** shearY:=shearX → det≡1 → V4 非相似簽章 FALSE;(b)shearY 隔離(僅 twist 帶非零 shearY,wobble/squash 皆 0);(c)加性(移除 twist 其餘 beat 逐位元不變)。

端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 twist,`validate_build` round-trip overall_pass(premult MAE 0.031)。
**回歸:20 閘全綠**(19 既有 + 新 twist_gen)。新增 cap `twist_sheary_generation` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。

## 關鍵發現

- **一般仿射 M 的所有自由度現已被生成器塞滿**:rotate(0i)、非均勻 scale(G-4'''')、shearX(G-4')、**shearY(本次)**。
  shear 通道 honest boundary(`shearY≡0`)自此關閉。
- **「填了通道」≠「用對通道」**:填 shearY 若取 `=shearX` 只是旋轉偽裝(det≡1);真價值在 `shearX≠shearY`(det≠1,非相似)。
  這是繼「真簽章常需兩獨立條件並立」(squash 體積守恆且非均勻)之後,又一「單有通道不夠、要驗語意」的實例。
- **det = cos(shearX − shearY)** 是雙軸 shear 是否退化為旋轉的閉式判準(rot=0,sx=sy=1),乾淨可量、負對照鋒利。

## honest boundary(仍在)

- twist 未接 MAIN_SHOW_CATS(tier 幅度差異化)—— 比照 G-4' 當時 wobble 亦先只產通道、tier 由 G-4'' 補
  (amplify_bone_tl 對 shear.y 已 `g*v` 就緒,接上即可)。
- `shearY = −shearX` 為對稱特例(對角純剪切);**獨立 shearY 幅度**(shearY 與 shearX 不同源)為後續泛化。
- 絞擰形狀為 PROPOSAL(結構簽章客觀、手感留使用者 A 類);單一真值資產(robot)。

見圖 `knowledge/figures/`(可後補)、`tools/analyzer/{beat_templates,gen_animations,tier_variants,genre_priors}.py`、`tools/analyzer/validate_twist_gen.py`。
