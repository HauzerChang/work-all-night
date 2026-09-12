# S1 (G-4'''') squash — 生成器產出**耦合的 shear + 非均勻 scale**(體積守恆擠壓)端到端

> candidate G-4''''(2026-09-12)。續 G-4' / G-4'' / G-4''' 的 shear 生成器線,補上一路留到現在的
> honest boundary:**`shearY≡0`、斜拉 squash(shear + coupled scale)為後續**。

## 一句話

`gen_squash`(斜拉果凍**擠壓**)是**第一個同時產出 `shear` 與非均勻 `scale`(sx≠sy)通道**的生成器:
斜拉的同時**拉一軸、壓一軸使面積守恆**(scaleX·scaleY==1),`build_spine --shear-pivot` 端到端把
rotate/scale/**shear** 三通道一起繞關節 pivot 補償 → 件做**真正的一般仿射(非相似)變換**而 pivot 精確不動。

## 為什麼是這一步(補的 honest boundary)

- **G-4**(`shear_pivot_affine`)補齊了「件繞關節 pivot 的**一般仿射**(含 shear **且**非均勻 scale)」的
  **公式 + 閘**(`transform_matrix_full`/`pivot_delta_affine`/`apply_pivots(include_shear=)`),但 AC4/AC7
  的非均勻 scale 只用**合成**值驗管路。
- **G-4'**(`shear_channel_generation`)讓 `gen_wobble` 成為第一個產 shear 的生成器,但只產**純 shearX**
  (scaleX≡scaleY≡1)—— 那仍是**相似變換的特例**(等距 + 純 skew),沒真正驅動非均勻 scale。
- 本次(G-4''''):讓某節拍**實際產出耦合的 shear + 非均勻 scale** —— G-4 的通用公式 Δ=(M−I)(O−P)
  **第一次被生成器產的非均勻 scale + shear 同時驅動**,把「公式/閘就緒 ≠ 生成器接上」這最後一段接上。
  又一「就緒 ≠ 接上」實例(同 E/H/I/J/G-4'/G-4''/G-4''')。

## 運動基元(deterministic,`beat_templates.gen_squash`)

- **shearX(τ)**:同 wobble 的阻尼擺動 `0 → +A → −rA → +r²A → …(nosc 個交替遞減極值)→ 0`,r=0.5。
- **coupled scale(τ)**:每個 shear 極值時刻 i 施一次**體積守恆 squash** ——
  `scaleX = 1 + q_i`(拉長)、`scaleY = 1/(1+q_i)`(壓扁),`q_i = Q·rⁱ`(擠壓幅度與 shear **同源同阻尼**)。
  ⇒ `scaleX·scaleY ≡ 1`(面積守恆)且 `scaleX ≠ scaleY`(非均勻=真擠壓);首尾 `scaleX==scaleY==1`(identity)。
- role→shearX 峰沿用 `_WOBBLE_SHEAR`;role→scaleX 拉長峰 `_SQUASH_STRETCH`(body 0.14 / 特效 0.16 / head 0.10 / limb 0.12)。
- **shearY≡0**(仍純斜拉;shearY 為更後續)。`nosc` 參數已就緒(count-aware 為後續,見下 honest boundary)。

## 結構簽章(可量化、負對照乾淨分離)

1. **首尾 identity**:shearX==0、scaleX==scaleY==1 → 可插 Loop 循環間(同其他主秀 beat)。
2. **shear 阻尼振盪**(復用 G-4' 判準):繞 0 變號 ≥3、相繼極值幅度嚴格遞減。
3. **體積守恆 squash 耦合(crux)**,每個 shear 極值幀:(a) `|scaleX·scaleY − 1| ≤ TOL_VOL`(面積守恆);
   (b) `max|scaleX − scaleY| ≥ MIN_ANISO`(真擠壓=非均勻,非等比 pulse);(c) squash 幅度 `|scaleX−1|`
   隨極值**嚴格遞減**(與 shear 同源同阻尼 → 耦合)。

## 自驗閘 `validate_squash_gen.py`(從**先驗庫 → 真實 build_spine robot 骨架 → build_animations**)

**6 AC 全 PASS**:

- **SQ1 present + dual-channel(crux)**:squash beat 直出、finite、有 bone,≥1 bone **同時**帶 shear 與
  scale;shearX 峰 16.0° ≥ MIN_SHEAR **且** 非均勻峰 0.298 ≥ MIN_ANISO → **產線第一次產耦合 shear+非均勻 scale**。
- **SQ2 shear 阻尼振盪**:每 squash bone 的 shearX 首尾 0、繞 0 變號 ≥3、相繼極值遞減。
- **SQ3 體積守恆耦合(crux)**:每極值幀 scaleX·scaleY≈1(實測 |積−1|≤5e-5)、非均勻峰 0.19–0.30、
  squash 幅度 [Q,Q/2,Q/4,Q/8] 嚴格遞減。
- **SQ4 identity 介面**:sample(0)/sample(dur) 各 bone identity,shear 首尾 0、scale 首尾 (1,1)。
- **SQ5 端到端一般仿射 pivot 不動**:`build_spine --shear-pivot`(真實 robot)產出 squash 帶補償;
  有關節 pivot 的 bone pivot 殘差 **0.005–0.018px** vs 內建負對照(未補償,繞件中心含 shear+非均勻 scale)
  **9–33px**(比值 >1000×)→ 證補償真的把**非相似**變換也錨在 pivot(頭/右手/左手,pivot≈件中心的身體/光暈正確略過)。
- **SQ6 負對照/隔離**:(a)**等比 scale 守衛**:合成 scaleX==scaleY(pulse)→ 非均勻判準 FALSE;
  (b)**非守恆守衛**:合成非均勻但兩軸皆拉長(積≠1)→ 體積守恆判準 FALSE 而非均勻仍 TRUE
  (證(a)(b)彼此獨立、閘非「有 scale + 有 shear 即通過」);(c)**耦合隔離**:非 squash beat 皆非「同時帶
  shear 且非均勻 scale」(wobble 有 shear 無 scale、其餘主秀有等比 scale 無 shear → squash 獨佔耦合);
  (d)**加性**:移除 squash 的 storyboard → 其餘 beat 逐位元不變(零回歸)。

## 關鍵發現

- **純 shear 是相似特例;shear + 非均勻 scale 才是真正的一般仿射**。G-4 的 Δ=(M−I)(O−P) 對**任意** 2×2
  線性部成立(純代數,不需 M 是旋轉/相似),本次讓生成器實際產出**非相似** M(det=scaleX·scaleY·cos(shear))
  —— 端到端 pivot 殘差仍 <0.02px,首次以**生成器產的**非均勻 scale+shear 驗證了公式的完整通用性。
- **體積守恆是 squash 的客觀簽章**,與「非均勻」正交:單靠非均勻(兩軸皆拉長)不是 squash;
  單靠體積守恆(等比不可能守恆除非=1)也不是。兩條件並立(積≈1 **且** sx≠sy)才鎖定「squash & stretch」。
  這與 (I) cascade「散佈 **且** 遞增」、(H) charge「長 hold **且** squash-floor」同型:**真簽章常需兩獨立條件並立**。

## Honest boundary(仍在,後續候選)

- **squash 未接 tier 幅度差異化**:squash **不在** `MAIN_SHOW_CATS`。因 `_amp_scale` 只放大 identity **上方**
  (scaleX>1 放大、scaleY<1 樓地板不動)→ 對 squash 會**破壞體積守恆**(scaleX·scaleY≠1)。squash 的檔位
  差異化需**耦合 amplify**(scaleX、scaleY 一起以體積守恆方式放大),為後續 (G-4''''' 型) 候選。
- shearY≡0(斜拉只在 X);squash 段數 `nosc` count-aware(隨檔位)已備參數未接(比照 J-2/G-4''')。
- 斜拉 squash 形狀為 PROPOSAL(結構簽章客觀、手感留使用者 A 類)。

## 檔案 / 指令

- 基元:`tools/analyzer/beat_templates.py`(`gen_squash`/`_squash_env`/`_SQUASH_STRETCH`/`SQUASH_KEYWORDS`)。
- 註冊:`gen_animations.py`(`_DISPATCH["squash"]`、`_CAT_KEYWORDS` 置前)。
- 先驗庫:`genre_priors.py`(slot_bigwin 加 squash beat,additive、coverage 仍 1.0、列 prior_beats_unused)。
- 類別集合:`tier_variants.py` 新增 `SHEAR_CATS = {"wobble","squash"}`(shear 產出者集中一處;
  shear-isolation 閘 shear_gen W5b / wobble_tier T4 改以此認定,便於後續再加)。
- 端到端:`build_spine.py --animate --shear-pivot`(include_shear=True 隱含 include_scale)。
- 閘:`tools/analyzer/validate_squash_gen.py`(`python3 validate_squash_gen.py [--json]`)。
- 回歸:16 閘全綠 + round-trip `validate_build` 對 `--shear-pivot` build overall_pass(premult MAE 0.031)。
- 圖:`knowledge/figures/s1_squash_coupling.png`。
- 能力:cap `squash_shear_scale_coupling` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
