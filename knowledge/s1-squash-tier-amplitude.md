# S1 — squash 接 tier 檔位幅度差異化(體積守恆耦合 amplify)(candidate G-4''''',`squash_tier_amplitude` L2)

> 2026-09-15。把 (G-4'''') 新生成的 **squash 節拍(shear + 耦合非均勻 scale 的體積守恆擠壓)** 接進 (J)
> 的檔位幅度差異化機制:squash 的擠壓 strain(|scaleX−1|)與 shear 峰隨檔位(Super→Legend)嚴格遞增,
> 同時 **scaleX·scaleY==1 的體積守恆與阻尼振盪簽章在每個檔位保形**。
> 又一「檔位機制就緒 ≠ 每個新通道接上」實例(同 E/H/I/J/G-4'/G-4'')——但這次的接法**不是照抄** (J):
> squash 的 scale 是體積守恆的一拉一壓,逐軸放大會破壞守恆,必須**耦合放大 strain**。

## 缺口(honest boundary 的接續)

- **(J)** 讓主秀 beat 依檔位產出 `{beat}__{tier}` 幅度變體,其 `amplify_bone_tl` 的 scale 增益是
  `_amp_scale`:**只放大 identity 上方**(`v'=1+g(v−1)` 僅當 v≥1),下方(squash/collapse 樓地板)不動。
- **(G-4'''')** 讓 `gen_squash` 成為**第一個產出耦合 shear + 非均勻 scale** 的生成器,scale 通道是
  **體積守恆**的一拉一壓:scaleX=1+q(≥1)、scaleY=1/(1+q)(≤1),積==1。但當時 **squash ∉ MAIN_SHOW_CATS**,
  G-4'''' 誠實標記原因:天真 `_amp_scale` 逐軸做 → 拉長軸 scaleX 放大成 1+g·q、壓扁軸 scaleY<1 樓地板
  **不動** → 積 = (1+g·q)·(1/(1+q)) **≠ 1**,**破壞體積守恆**。
- 本次(G-4''''')正好照那條邊界接上,但需要**新機制**(耦合 amplify),不是把 squash 塞進舊路徑。

## 關鍵洞察:體積守恆節拍的檔位放大必須「耦合」

squash 一幀 = **一軸拉長、一軸壓扁使面積守恆**。要把「擠壓強度」隨檔位放大而**保持** scaleX·scaleY==1,
必須把兩軸當一個耦合對一起放大,而非各自獨立:

- 從拉長軸回推擠壓量 `q = scaleX − 1`,以 g 放大 `q → g·q`,再**重建**壓扁軸 `scaleY = 1/(1+g·q)`
  ⇒ **積恆 == 1**(守恆保持)、strain `|scaleX−1| = g·q` 隨 g **嚴格遞增**(檔位簽章)。
- 對「哪一軸拉長」**對稱**(scaleX≥scaleY → X 拉長,gen_squash 慣例;反之 Y 拉長,防未來 side 反相)。
- **等價命題(可驗)**:耦合 amplify **等同於「以 Q→g·Q 重生成 gen_squash」** ——
  `q_i = Q·rⁱ → g·q_i = (g·Q)·rⁱ`,阻尼比 r=0.5 不變 → 相繼極值遞減(阻尼)簽章逐檔保形。
  這與 (J-2)/(G-4''') 的「重生成等價」是同一種正交性,只是這裡放大的是**擠壓 strain 旋鈕 Q** 而非段數。
- shear 通道則同 wobble(對 0 對稱 `v'=g*v`)→ shear 峰亦隨檔位遞增,阻尼振盪保形。兩軸同一增益 g 同源放大。

## 做了什麼(全 additive)

1. **`tier_variants.MAIN_SHOW_CATS`** 加入 `"squash"` → `build_animations(tier_gains=)` 對 squash 也產
   `squash__{tier}` 變體。
2. **`tier_variants.VOLUME_CONSERVE_CATS = {"squash"}`**(新集合):scale 通道為體積守恆的節拍,
   tier 放大走**耦合 amplify** 而非逐軸 `_amp_scale`。
3. **`tier_variants._amp_squash_coupled(scx,scy,g)`**(新):體積守恆耦合 amplify(見上式)。
   `g==1.0` → 直接回傳輸入(逐位元 identity;向後相容:`squash__Super == base squash` byte-identical)。
4. **`tier_variants.amplify_bone_tl(b,g,coupled_scale=False)`** / **`amplify_anim(...,coupled_scale=False)`**:
   加 `coupled_scale` 旗標;True 時 scale 通道走耦合、shear/rotate/translate 不變。
5. **`gen_animations.build_animations`**:tier 迴圈依 `cat in VOLUME_CONSERVE_CATS` 路由 `coupled_scale`
   給 `amplify_anim`(與既有 `COUNT_AWARE` 段數路由並存;squash 本次**只接幅度軸**,count-aware 為後續)。
6. **`validate_squash_tier.py`**(新,5 AC)。
7. **`validate_tier_combo_count.py`** K5(c) 強化(見下「回歸修正」)。
8. **`check_readiness`** 新增 cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(仍 HOLD)。
9. 圖 `knowledge/figures/s1_squash_tier.png`。

## 驗收閘 `validate_squash_tier.py`(5 AC 全 PASS)

從**先驗庫**(slot_bigwin)經 `analyze_target` → **真實 build_spine robot 骨架** → `build_animations(tier_gains=)`
端到端量。真值同 (E/H/I/J/G-4'/G-4''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章**非美感。

- **V1 present + backward-compat**:每檔位 `squash__{tier}` 直出、finite、有 bone、同時帶 shear+scale;
  base squash 逐位元不變;**squash__Super(g=1.0)逐位元 == base squash**(耦合 amplify 在 g=1 為 identity)。
- **V2 crux amplitude + volume**(每 squash bone):(a)strain 峰 |scaleX−1| Super<Mega<Omg<Legend
  **嚴格遞增**、Super==base;(b)shear 峰亦嚴格遞增、Super==base;(c)**crux 體積守恆保持**:每檔位每極值幀
  |scaleX·scaleY−1|≤2e-2(實測 ≤1e-4);(d)非均勻保持:每檔位仍 max|scaleX−scaleY|≥0.05(仍真擠壓)。
  實測(光暈)strain [0.16,0.216,0.272,0.336]、shear [16,21.6,27.2,33.6]°,max|prod−1| 5e-5。
- **V3 signature preserved**(每檔位):(a)shear 阻尼振盪(首尾 0、繞 0 變號≥3、相繼極值遞減);
  (b)squash strain 隨極值嚴格遞減(阻尼耦合);(c)sample(0)/sample(dur)各 bone identity → 可插 Loop。
- **V4 coupled == regen(Q·g)**:耦合 amplify 後的擠壓量 == g×base 擠壓量(逐極值,容差 2e-4)且積仍==1
  → 證耦合 amplify 就是生成器自身的**擠壓 strain 旋鈕**(同 J-2/G-4''' 的重生成等價)。
- **V5 neg-control**:(a)**平增益守衛**:增益全 1.0 → V2 strain 遞增 FALSE 且各檔位==base(證閘測遞增
  非恆真);(b)**天真逐軸破壞守恆(honest boundary 的量化證明)**:對同一 squash 幀改用舊 `_amp_scale` 逐軸
  → 最高檔位 |scaleX·scaleY−1| **實測 0.152(15%)** 顯著漂離 0,而耦合 amplify 為 9.7e-5 → **證耦合為必要、
  非等效**;(c)**耦合隔離**:耦合 amplify 只作用 squash → 非-squash 主秀 beat 的 tier 變體與逐軸 amplify 逐位元相同。

## 回歸修正:`validate_tier_combo_count.py` K5(c)(強化,非放水)

squash 進 MAIN_SHOW_CATS 後,K5(c)「count 只作用 combo:非-combo beat 峰數在各檔位不變」對 squash **偽陽性**:
它以 scaleX **impact-peak 計數** 為 proxy,而 squash 是**體積守恆單一衰減 bump**(非離散連擊),其真實 scaleX
overshoot 隨檔位遞增,頭件峰值(Super 1.10)在高檔位越過固定 `IMPACT_PROM` 門檻 → 計數 0→1 跳變,被誤判外洩。
**真正的隔離不變量**是「`tier_combo_hits` 路由只改 combo」,即非-combo beat 的 tier 變體與**純幅度**(amp_only)
**逐位元相同**。改以此 byte-equality 判定 → 對任何幅度門檻穩健,且比計數 proxy **更強**(涵蓋所有非-combo
類別含 squash)。此為**強化非放水**:byte-equality ⇒ 峰數必相同,反之不然。

## 端到端 & 全域回歸

- `build_spine --animate --tier-variants --shear-pivot` **直出** `squash__{Super,Mega,Omg,Legend}`(pivot
  補償後 strain 仍隨檔位嚴格遞增);`validate_build` round-trip **overall_pass**(premult MAE 0.031、setup 不變)。
- 回歸 **18 閘全綠**:squash_tier(新)+ squash_gen(G-4'''')+ tier_variants(J,squash 現納入 J3 channel-aware
  且通過)+ tier_combo_count(J-2,K5(c) 強化後)+ wobble_tier(G-4'')/wobble_count(G-4''')/shear_gen(G-4')/
  shear_pivot(G-4)/scale_pivot(G-3)/pivot_rotation(0i)/priors/priors_beats/priors_combo_charge/priors_cascade/
  cascade/more_beats/beat_templates/deform_gen。

## honest boundary(仍在)

- **squash count-aware 未接**:擠壓**段數**隨檔位(nosc 已備參,比照 G-4''' 對 wobble)為後續 —— 本次只做
  **幅度軸**(strain 隨檔位)。這正對應 wobble 先 G-4''(幅度)再 G-4'''(段數)的兩步。
- 擠壓 strain 階梯沿用 (J) 增益(PROPOSAL;手感留使用者 A 類);shearY≡0(純 shearX 斜拉)。
- cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。

## 關鍵發現(可推廣)

**「檔位放大」的正確形式取決於通道的守恆結構**:對 0 對稱通道(rotate/translate/shear)→ `v'=g*v`;
對 identity 上方 overshoot(scale pulse)→ 只放大上方 `1+g(v−1)`;對**體積守恆對**(squash 的一拉一壓)
→ **耦合放大 strain 再重建守恆軸**。三者都滿足「g=1 identity、端點/簽章保形、幅度單調」,但公式各異 ——
把新通道接上檔位機制不能盲抄,要看它的不變量是什麼。這是繼「結構軸×幅度軸雙軸差異化」(G-4''')之後,
檔位機制的第三類通道語意。
