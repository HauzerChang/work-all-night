# S1 (G-4''''') squash 接檔位差異化 — **體積守恆的耦合 amplify**(擠壓隨檔位遞增而 scaleX·scaleY≡1)

> candidate G-4'''''(2026-09-20)。補 G-4''''(`squash_shear_scale_coupling`)留到現在的 honest boundary:
> 「**squash 未接 tier 幅度差異化**」。續 (J)→(G-4'')→本次的檔位-幅度線,把最後一個主秀節拍(squash)接上檔位。

## 一句話

squash(斜拉果凍擠壓)的 scale 幅度軸是**一對體積守恆的值**(scaleX=1+q 拉長、scaleY=1/(1+q) 壓扁,
scaleX·scaleY≡1);要讓擠壓**強度隨檔位遞增**又不破壞面積守恆,不能用逐軸獨立的 `_amp_scale`(它會放大
拉長軸卻讓壓縮軸樓地板不動 → 積≠1),必須走**耦合 amplify**:放大擠壓量 q→g·q、壓縮軸取放大後拉長軸的
倒數。⇒ 非均勻峰 |scaleX−scaleY| Super<Mega<Omg<Legend 嚴格遞增,**且每檔位每極值幀 scaleX·scaleY==1
仍守恆**;shear 峰同 wobble 逐幀 g·v 放大、雙通道阻尼簽章逐檔保形。

## 為什麼是這一步(補的 honest boundary)

- **(J)** `tier_variant_amplitude` 讓主秀 beat 依檔位產 `{beat}__{tier}` 幅度變體,但增益只作用
  scale(逐軸 `_amp_scale`,只放大 identity 上方)/rotate/translate。
- **(G-4'')** `wobble_tier_amplitude` 把 wobble 的 **shear** 峰接上檔位(`v'=g·v`,對 0 對稱)。
- **(G-4'''')** `squash_shear_scale_coupling` 讓 `gen_squash` 產出耦合 shear+非均勻 scale,但把 squash
  **排除在 `MAIN_SHOW_CATS` 之外**,因逐軸 `_amp_scale` 會破壞其體積守恆 —— 明列為 honest boundary。
- **本次(G-4''''')**:補上 squash 的檔位差異化,關鍵是**耦合 amplify**。又一「機制就緒 ≠ 每個新通道/新
  節拍接上」實例(同 E/H/I/J/G-4'/G-4''/G-4''')。

## 關鍵:為什麼逐軸獨立 amplify 不行(crux)

`_amp_scale(v,g) = 1+g(v−1) if v≥1 else v`(下方樓地板不動)。對 squash 對 (1+q, 1/(1+q)):
- 拉長軸(≥1)被放大成 1+g·q;壓縮軸(<1)**樓地板保留** 1/(1+q) 不動。
- ⇒ 積 = (1+g·q)/(1+q) ≠ 1(g>1 時 >1)→ **破壞面積守恆**,squash 變成「純拉長無壓縮」的膨脹。

實測(特效 bone,base q 峰 0.16):逐軸獨立 amplify 的 scaleX·scaleY 峰偏離 —
Mega 0.048、Omg 0.097、**Legend 0.152**(遠超守恆容差 TOL_VOL=0.02)。

**耦合 amplify**(`_amp_scale_coupled(x,y,g)`)把兩軸當一對:拉長軸取 `sx=round(1+g(x−1),4)`、壓縮軸取
`round(1/sx,4)` → 積在任何增益下 ≈1(僅 4dp 儲存誤差 ~5e-5,與基元本身同量級)。軸無關寫法(取兩軸中
≥1 者為拉長軸)以防未來 shearY/反向擠壓。`g==1.0` 與 identity(1,1)原樣回傳 → base=Super 逐位元向後相容。

## 端到端(全 additive,依 cat 路由兩條 amplify 路徑)

- `tier_variants.py`:`squash` 加入 `MAIN_SHOW_CATS`;新增 `COUPLED_SCALE_CATS={"squash"}` +
  `_amp_scale_coupled` + `amplify_bone_tl(b,g,coupled_scale=)`/`amplify_anim(...,coupled_scale=)`。
- `gen_animations.build_animations`:`coupled = cat in COUPLED_SCALE_CATS` → squash 走耦合 amplify,
  其餘主秀(hit/combo/… 等比 scale overshoot)仍走逐軸 `_amp_scale`(等比放大、樓地板保留),互不干擾。
- `build_spine --animate --shear-pivot --tier-variants` 直出 `squash__{Super,Mega,Omg,Legend}`
  (pivot 補償後仍守恆:補償只加 translate/rotate,不動 scale/shear 通道)。

## 自驗閘 `validate_squash_tier.py`(先驗庫→**真實 build_spine robot 骨架**→build_animations)

**5 AC 全 PASS**:

- **Q1 present + backward-compat**:每檔位 `squash__{tier}` 產出、finite、有 bone、≥1 bone **同時**帶
  shear+scale、名經 `beat_category` 仍路由回 squash;**base(含 In/Loop/Out + base squash)帶/不帶
  tier_gains 逐位元不變**。
- **Q2 crux — 非均勻峰遞增 且 體積守恆保持**:非均勻峰 [0.298, 0.394, 0.486, 0.588] 嚴格遞增(Super==base
  0.298),**且每檔位每極值幀 |scaleX·scaleY−1|≤5.6e-5 ≤ TOL_VOL**(放大後守恆仍保持——耦合 amplify 的本質)。
- **Q3 雙通道阻尼簽章逐檔保形**:shearX 峰 [16.0, 21.6, 27.2, 33.6] 遞增;每檔位每 squash bone shearX 首尾
  0、繞 0 變號 ≥3、相繼極值遞減;squash 幅度 |scaleX−1| 隨極值嚴格遞減(耦合阻尼)。
- **Q4 耦合 amplify 必要性**:(a)**crux 守衛**:對同一 squash 對施舊逐軸 `_amp_scale` → g>1 每檔位
  scaleX·scaleY 偏離 [0.048, 0.097, 0.152] 皆 >TOL_VOL(破壞守恆)→ 證耦合非多餘、且 Q2 守恆判準有鑑別力;
  (b)**平增益守衛**:增益全 1.0 → 非均勻不遞增且各檔位逐位元 == base。
- **Q5 負對照/隔離**:(a)`_amp_scale_coupled` 單元:identity(1,1)→(1,1)、g=1 原樣、g=2 對合成 squash 對
  守恆且非均勻放大;(b)**耦合隔離**:等比 scale 主秀(hit,scaleX==scaleY overshoot)的檔位變體仍
  scaleX==scaleY(未被誤施耦合 amplify)→ 耦合 amplify 只作用 squash,對 (J) 等比節拍零外洩。

## 回歸

18 閘全綠(squash_gen/wobble_tier/wobble_count/tier_variants(J)/tier_combo_count(J-2)/shear_gen/
shear_pivot/scale_pivot/pivot_rotation/priors/priors_beats/priors_combo_charge/priors_cascade/cascade/
more_beats/beat_templates/deform_gen)+ round-trip `validate_build` 對 `--shear-pivot --tier-variants`
build overall_pass(premult MAE 0.031、setup 不變)。

> **`validate_tier_combo_count.py` K5(c) 修正(更精準,非放寬)**:原以「非-combo 主秀 beat 的 impact 峰
> **數**在各檔位不變」測「連擊數不外洩」。squash 併入 MAIN_SHOW_CATS 後,其**多個阻尼 scale 極值**會因
> **幅度增益 g**(非 tier_combo_hits)跨過 impact-prominence 門檻而使峰數隨檔位變動 → 舊判準假陽性。改為
> **直接比對 `full`(gains+counts)與 `amp_only`(gains-only)的非-combo 變體逐位元相同** —— 這才是
> 「tier_combo_hits 只作用 combo」的乾淨測法(對任意節拍穩健、不受 prominence 門檻干擾)。

## 關鍵發現

- **不同通道的「檔位放大」需不同保形變換**:rotate/translate/shear 對 0 對稱 → `v'=g·v`;等比 scale
  overshoot → 逐軸 `1+g(v−1)`(樓地板保留);**體積守恆的 squash 對 → 耦合 `(1+g·q, 1/(1+g·q))`**。
  「檔位=更強、結構不變」對每個通道都成立,但保形變換的**形式**由該通道的簽章決定。
- **量測「數」的負對照需與量測「幅度」的效應解耦**:combo-count 閘的峰數判準遇到「幅度會改變峰數」的
  節拍(squash 的多阻尼極值)會假陽性;改用「與幅度-only 基線逐位元比對」把「數」的隔離測乾淨。

## Honest boundary(仍在,後續候選)

- **squash count-aware**(擠壓段數 nosc 隨檔位遞增,`gen_squash(nosc=)` 已備參數未接,比照 J-2/G-4''';
  需把 squash 加入 `COUNT_AWARE_CATS` + `TIER_SQUASH_CYCLES` + `_count_maps` 路由)。
- shearY≡0(斜拉只在 X);shear+scale+rotate 三通道同時的運動基元(塞滿一般仿射 M 全自由度)。
- 檔位增益階梯 [1.0,1.35,1.70,2.10] 沿用 (J)(PROPOSAL;手感留使用者 A 類)。

## 檔案 / 指令

- 機制:`tools/analyzer/tier_variants.py`(`COUPLED_SCALE_CATS`/`_amp_scale_coupled`/`amplify_bone_tl(coupled_scale=)`)。
- 路由:`tools/analyzer/gen_animations.py`(`build_animations` 依 `COUPLED_SCALE_CATS` 選 amplify 路徑)。
- 端到端:`build_spine.py --animate --shear-pivot --tier-variants`。
- 閘:`tools/analyzer/validate_squash_tier.py`(`python3 validate_squash_tier.py [--json]`)。
- 圖:`knowledge/figures/s1_squash_tier.png`。
- 能力:cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
