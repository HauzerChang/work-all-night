# S1 — squash 擠壓強度隨檔位遞增(耦合 amplify 保體積守恆,candidate G-4''''')

> 里程碑 2026-09-18。補上 (G-4'''') 一路留到現在的 honest boundary:**squash 未接 tier 檔位差異化**。
> 讓斜拉果凍**擠壓**(shear + 耦合非均勻 scale)的強度隨大獎檔位遞增,而**體積守恆**與**阻尼耦合簽章**
> 在每個檔位保持。工具:`tools/analyzer/tier_variants.py`(新增 `_amp_scale_coupled` / `COUPLED_SCALE_CATS`)、
> `tools/analyzer/gen_animations.py`(build_animations 路由耦合 scale)、閘 `tools/analyzer/validate_squash_tier.py`。

## 問題:普通幅度 amplify 會破壞體積守恆

`genre_priors.slot_bigwin` 的 `tiers=[Super,Mega,Omg,Legend]` 檔位機制早已就緒((J) candidate),
主秀 beat 依檔位增益 g 放大;wobble(純 shear)也已於 (G-4'') 接上(shear v'=g·v)。但 **squash 一直不在
`MAIN_SHOW_CATS`** —— 因為它的 scale 是**體積守恆的非均勻擠壓**:每個 shear 極值 i,`scaleX=1+q_i`(拉長)、
`scaleY=1/(1+q_i)`(壓扁),兩軸乘積 `scaleX·scaleY≡1`(面積守恆)。而 (J) 的 scale 幅度增益 `_amp_scale`
規則是「**只放大 identity 上方 overshoot、下方樓地板不動**」(保 anticipation/collapse 語意):

```
_amp_scale(v, g) = 1 + g·(v−1)   if v ≥ 1   else   v   (v<1 不動)
```

對 squash 施此規則:scaleX(>1)被放大成 `1+g·q`,但 scaleY(<1)是樓地板 → **不動**。乘積
`(1+g·q)·(1/(1+q)) ≠ 1` → **體積守恆被破壞**。實測對真實 base squash 極值以 Legend g=2.1 放大:
`max|scaleX·scaleY−1|` = **0.152**(遠超容忍 0.02);Mega/Omg/Legend 皆破。這正是 (G-4'''') 誠實標注的
honest boundary。

## 解法:耦合 amplify = 對數應變空間同比放大(power)

體積守恆量的**正確放大**不在線性空間,而在**對數應變空間**。設 `σ = ln(scaleX)`(對數應變),
體積守恆即 `ln(scaleX)+ln(scaleY)=σ+(−σ)=0`。要「把擠壓變強 g 倍」= 把應變 σ 放大 g 倍:

```
_amp_scale_coupled(v, g) = v ** g          # σ' = g·σ  ⇒  v' = exp(g·σ) = v^g
```

對一組 `(scaleX, scaleY)=(1+q, 1/(1+q))`:

- `scaleX' = (1+q)^g`、`scaleY' = (1+q)^(−g)`
- 乘積 `scaleX'·scaleY' = (scaleX·scaleY)^g = 1^g ≡ 1` → **體積仍守恆**(精確)。
- 非均勻 `|scaleX'−scaleY'| = |(1+q)^g − (1+q)^(−g)|` 隨 g **單調遞增** → 擠壓更強。
- `identity(v=1) → 1^g=1`(介面契約保持);`g=1.0 → v^1=v`(Super 向後相容 identity 變換)。
- squash 幅度 `|scaleX'−1|=(1+q_i)^g−1` 隨 q_i(=Q·rⁱ 阻尼遞減)**仍嚴格遞減** → 阻尼耦合簽章保形。

## 實作(全 additive、opt-in)

- `tier_variants.py`:新增 `_amp_scale_coupled(v,g)=v**g`;`amplify_bone_tl(b,g,coupled_scale=False)` /
  `amplify_anim(anim,g,coupled_scale=False)` 加 `coupled_scale` 旗標(True → scale 走耦合、預設 False → 走
  `_amp_scale`);新增 `COUPLED_SCALE_CATS={"squash"}`;把 `squash` 併入 `MAIN_SHOW_CATS`。
  shear/rotate/translate 通道不變(皆對 0 對稱 v'=g·v)。
- `gen_animations.py` `build_animations`:對主秀 beat 產檔位變體時,`coupled = cat in COUPLED_SCALE_CATS`,
  傳給 `amplify_anim(..., coupled_scale=coupled)`。squash 非 count-aware(擠壓段數隨檔位為後續)→ 走幅度-only 分支。
- `build_spine --animate --tier-variants --shear-pivot` 端到端直出 `squash__{Super,Mega,Omg,Legend}`。

## 驗收(`validate_squash_tier.py`,5 AC 全 PASS)

| AC | 內容 | 結果 |
|---|---|---|
| ST1 | present + backward-compat + dual-channel(每檔位 finite/有 bone/同時帶 shear+scale;base 逐位元不變) | ✅ |
| ST2 | **crux** 體積守恆跨檔位:每檔位每極值 `\|scaleX·scaleY−1\|≤0.02`(實測 ≤ 8e-5) | ✅ |
| ST3 | **crux** 強度遞增:非均勻峰 [0.298,0.403,0.510,0.633] + shear 峰 [16,21.6,27.2,33.6]° 皆嚴格遞增,Super==base | ✅ |
| ST4 | 每檔位 identity 介面 + shear 阻尼振盪 + squash 幅度遞減皆保形 | ✅ |
| ST5 | 負對照 a 平增益→遞增 FALSE / **b 耦合必要性 crux** / c 耦合只作用 squash / d 加性零回歸 | ✅ |

**ST5b(耦合必要性,crux)**:對真實 base squash 極值,舊 `_amp_scale` 以 Legend g 放大 → `vol_err 0.152 > 0.02`
(**破壞**);`_amp_scale_coupled` → `vol_err 0.0001 ≤ 0.02`(**守恆**)且非均勻更大。直接證「耦合 amplify 是修正、
普通樓地板 amplify 會壞」—— 把 (G-4'''') 的 honest boundary 客觀地關掉。

端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 4 檔位變體;`validate_build` round-trip
overall_pass(premult MAE 0.031)。

## 回歸與一處閘精修

- **18 閘全綠**:validate_squash_tier(新)+ squash_gen / shear_gen / wobble_tier / wobble_count / shear_pivot /
  scale_pivot / pivot_rotation / tier_variants / tier_combo_count / cascade / more_beats / beat_templates /
  deform_gen / priors / priors_beats / priors_combo_charge / priors_cascade。
- **tier_combo_count K5c 隔離判準改精準**:原「非-combo 主秀 beat 峰數各檔位恆定」用 `_min_peaks`(scale 峰數,
  門檻 IMPACT_PROM=1.10)。squash 併入 MAIN_SHOW 後,其**幅度隨檔位遞增**的 scaleX 會因跨越 1.10 門檻而使峰數
  在檔位間變動(`[0,1,1,1]`)—— 那是**幅度效果非 count 外洩**。改為「非-combo 檔位變體在 full(gains+hits)與
  amp_only(gains-only)**逐位元相同**」,直接鎖定「連擊數機制只碰 combo」,不受幅度門檻假象干擾(更強、更精準)。

## 誠實限制 / 下一步

- 幅度階梯沿用 (J) 增益(Super1.0→Legend2.1)為 **PROPOSAL**,手感留使用者(A 類)。
- `shearY≡0`(單軸斜拉);squash **count-aware**(擠壓/振盪段數隨檔位,`nosc` 已備參數,比照 (G-4'''))為後續。
- **shear-pivot densify 中間幀**:體積守恆是**關鍵幀性質**;`--shear-pivot` 為補償非線性所加的線性內插中間幀,
  其 scale product 略偏(≤1.5%,同 (G-4'''') base squash),屬 Spine 線性內插固有,**非本候選回歸**(ST2 於極值量測)。
- cap `squash_tier_amplitude` L2,併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。

圖:`knowledge/figures/s1_squash_tier.png`(左:非均勻峰 & shear 峰隨檔位遞增;右:coupled 守恆 vs floor amplify 破壞)。
