# S1 (G-4''''') squash 接檔位(tier)幅度差異化 —— 體積守恆的**耦合 amplify**

> candidate G-4'''''(2026-09-20)。補上 G-4''''(`s1-squash-shear-scale-coupling.md`)留下的 honest
> boundary:squash 是產線第一個同時產出 **shear + 耦合非均勻 scale**(scaleX·scaleY≡1)的節拍,但當時
> **未接檔位**。本次讓 squash 的擠壓強度隨檔位(Super→Legend)遞增,關鍵新意 = **耦合放大**。

## 問題(honest boundary of G-4'''')

`genre_priors.slot_bigwin` 宣告 `tiers=[Super,Mega,Omg,Legend]`;(J) 讓主秀 beat 依檔位以增益 g
放大幅度。但 squash **不在** `MAIN_SHOW_CATS`,因為舊的逐軸 `_amp_scale` 只放大 identity 上方
(`v'=1+g(v−1)` 僅當 v≥1),squash 的**壓扁軸**(scaleY=1/(1+q) < 1)樓地板保留不動,而**拉長軸**
(scaleX=1+q > 1)被放大 → **破壞面積守恆**(scaleX·scaleY ≠ 1):

```
base squash 極值(body):(scaleX, scaleY) = (1.14, 0.877)   prod ≈ 1.000  ✅
逐軸獨立 _amp_scale Legend g=2.1:(1.294, 0.877)          prod ≈ 1.135  ❌ 守恆破壞
```

## 解法 —— 沿約束流形放大擠壓量(`_amp_scale_coupled`)

多通道約束(scaleX·scaleY≡1)下,幅度差異化**不能逐軸獨立做**,必須沿約束流形放大:放大**擠壓量**
q(以拉長軸 = max(sx,sy)−1 認定,對稱處理拉長在 x 或 y、**絕不換軸**),再以倒數導出壓扁軸——

```
拉長軸' = 1 + g·q        # 線性放大 q → 阻尼比 r 逐極值不變(q_i=Q·rⁱ → g·Q·rⁱ,比值恆 r)
壓扁軸' = 1 / 拉長軸'      # 面積守恆:scaleX'·scaleY' ≡ 1(精確,非近似)
```

性質:①identity 幀 (1,1) → q=0 → (1,1) 不動(**介面契約對所有檔位保持**,可插 Loop);②g=1.0 → 逐位元
同輸入(拉長軸=1+1·q=sx、壓扁軸=1/sx≈sy → **向後相容**,`squash__Super` == 無檔位 squash);③擠壓峰
|scaleX−1| 隨 g **嚴格遞增**且比值 ≈ tier_gain 比值(線性)。shear 通道沿用 (G-4'') 的對 0 對稱放大
`v'=g*v`(符號序列與遞減比不變 → 阻尼振盪簽章保形)。

## 接線(全 additive)

- `tier_variants.py`:`squash` 併入 `MAIN_SHOW_CATS`;新增 `COUPLED_SCALE_CATS={"squash"}` 與
  `_amp_scale_coupled`;`amplify_bone_tl(b,g,coupled_scale=False)` / `amplify_anim(anim,g,coupled_scale=False)`
  新增旗標(預設 False → 其餘節拍逐軸獨立,逐位元不變)。
- `gen_animations.build_animations`:主秀變體迴圈依 `cat in COUPLED_SCALE_CATS` 決定
  `coupled_scale`,透傳到 `_amplify_anim`。
- `build_spine --animate --tier-variants --shear-pivot`:直出 `squash__{Super,Mega,Omg,Legend}`,且
  `apply_pivots` 掃全部 animations → 各檔位變體亦繞關節 pivot 補償(Δ=(M−I)(O−P) 對任意 M 精確,
  放大後的更極端一般仿射 M 殘差仍 < 0.02px)。

## 閘 `validate_squash_tier.py` — 5 AC 全 PASS

從**先驗庫**(slot_bigwin)→ **真實 build_spine robot 骨架** → `build_animations(tier_gains=…)` 端到端量:

- **SQT1** present + backward-compat:每檔位 `squash__{tier}` 直出/finite/dual-channel;`squash__Super`
  逐位元 == 無檔位 squash;base(含 In/Loop/Out)逐位元不變;`tier_gains=None` → 不產 squash 變體。
- **SQT2 volume preserved(crux)**:每檔位、每 squash bone 每內部極值幀 |scaleX·scaleY−1| ≤ TOL_VOL
  —— 面積守恆**放大後仍成立**(證耦合 amplify 正確)。
- **SQT3 magnitude monotone(crux)**:每 squash bone 擠壓峰 |scaleX−1| 與 shear 峰 |shearX|
  Super<Mega<Omg<Legend **嚴格遞增**,且擠壓峰比值 ≈ tier_gain 比值 [1.0,1.35,1.70,2.10]。
  實測 body:stretch [0.14, 0.189, 0.238, 0.294]、shear [14.0, 18.9, 23.8, 29.4]°。
- **SQT4 signature preserved**:每檔位仍(a)非均勻 |scaleX−scaleY|≥MIN_ANISO、(b)擠壓幅度逐極值嚴格
  遞減(阻尼耦合)、(c)shear 阻尼振盪(繞 0 變號≥3 + 相繼極值遞減)、(d)identity 首尾介面。
- **SQT5 negative controls**:(a)**耦合守衛(crux)**:對同一 squash 幀施舊逐軸獨立 `_amp_scale`
  於 Legend → 體積守恆 **FALSE**(prod [1.135, 1.072, 1.037, 1.019]),耦合路徑同幀 **TRUE**(prod
  [1,1,1,1]) → 證「必須耦合」且 SQT2 判準有鑑別力;(b)平增益全 1.0 → 擠壓峰**不**遞增且各檔位 == base;
  (c)路由隔離:非-squash 主秀 beat 的 scale 仍等比(scaleX==scaleY),證耦合只施於 squash。

## 回歸(16 閘全綠 + round-trip)

shear_gen(G-4')/wobble_tier(G-4'')/wobble_count(G-4''')/squash_gen(G-4'''')/shear_pivot(G-4)/
scale_pivot(G-3)/pivot_rotation(0i)/tier_variants(J)/**tier_combo_count(J-2,K5(c) 修正見下)**/
priors/priors_beats/priors_combo_charge/priors_cascade/cascade/more_beats/beat_templates/deform_gen
**全 PASS**;`validate_build` round-trip 對 `--tier-variants --shear-pivot` build overall_pass。

**閘找出真實漏洞(K5(c) 精修,同 G-4'' 的 J3 channel-aware 模式)**:tier_combo_count 的 K5(c)
「count 只作用於 combo」原以「非-combo 主秀 beat 的 impact 峰數在各檔位恆定」判斷。squash 的 scaleX 峰值
會因 **tier_gains 幅度**放大而跨越 impact 門檻(1.10)→ 峰數本就會變([0,1,1,1]),那是**幅度效果非
combo count 外洩**,舊判準對它**假陽性**。改用 **full-vs-amp_only 對照**(同 tier_gains 下加/不加
`tier_combo_hits`,峰數變動才算 count 外洩)—— 精確隔離 combo_hits 這一機制(對 squash 兩者逐位元相同
→ 峰數必等),閘更誠實且仍對真 combo count 外洩有鑑別力。

## 關鍵發現

1. **多通道約束下的幅度差異化 = 沿約束流形放大,非逐軸自由放大**。scaleX·scaleY≡1 是一維約束流形
   (擠壓量 q 為唯一自由度);正確做法是放大 q、以約束(倒數)導出另一軸。這是**耦合 amplify** 的一般
   原則,可推廣到任何有守恆量的多通道運動基元(對比 wobble 的純 shear 是無約束的對 0 對稱放大)。
2. **又一「檔位機制就緒 ≠ 每個新通道/節拍接上」**(同 E/H/I/J/G-4'/G-4''/G-4'''),惟本例的接線需
   **新的放大器**而非只是把 cat 加進集合——因為 squash 的 scale 語意(體積守恆)與既有 pulse/anticipation
   的 scale 語意(等比 + 樓地板)不同,共用 `_amp_scale` 會壞守恆。

## honest boundary(仍在,後續)

- squash **count-aware**(擠壓段數隨檔位;`gen_squash(nosc=)` 參數已備,比照 G-4''' 對 wobble)未接
  —— 段數是拓樸,須 gen 時決定;與本次幅度軸正交,可再疊。
- shearY≡0(仍純 shearX 斜拉);shear+scale+rotate 三通道同時塞滿一般仿射 M 的所有自由度為後續
  (G-4'''''')。
- 擠壓峰/shear 峰的檔位階梯沿用 (J) 增益,為 PROPOSAL(結構簽章客觀、手感留使用者 A 類)。
- 單一真值資產(robot);cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元
  先驗、單一真值資產,防固化)。

圖:`figures/s1_squash_tier.png`(左:擠壓/shear 峰隨檔位遞增;中:耦合 vs 逐軸獨立的體積守恆對照;
右:阻尼擠壓階梯逐檔保形)。
