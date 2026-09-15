# S1 — squash 接檔位幅度差異化(candidate G-4''''',`squash_tier_amplitude` L2)

> 2026-09-15。把 (G-4'''') 新生成的 **shear + 耦合非均勻 scale 節拍(squash)** 接進 (J) 的**檔位幅度
> 差異化**機制:squash 的 shear 峰**與**擠壓量隨檔位(Super→Legend)**雙軸**嚴格遞增,同時**體積守恆
> (scaleX·scaleY≡1)在每個檔位保持**。關鍵新招:**體積守恆軸的幅度放大必須「耦合 amplify」**,不能逐通道。

## 缺口(honest boundary 的接續)

- **(J)** 讓主秀 beat 依檔位產出 `{beat}__{tier}` 幅度差異化變體;scale 增益走 `_amp_scale`
  = **只放大 identity 上方 overshoot**(`v'=1+g(v−1)` 僅當 v≥1;下方樓地板不動)。
- **(G-4'''')** 讓 `gen_squash` 成為**第一個同時產 shear + 耦合非均勻 scale** 的生成器:squash 極值為
  `(scaleX=1+q, scaleY=1/(1+q))`,scaleX·scaleY≡1(面積守恆)。但正因為這個**體積守恆耦合**,
  `_amp_scale` 會放大 scaleX(>1)、保留 scaleY(<1)樓地板 → **破壞守恆**(實測 g=2.1 對 q=0.16:
  scaleX 1.16→1.336、scaleY 0.862 不動 → prod **1.15≠1**)。故 G-4'''' 誠實把 squash 排除在
  `MAIN_SHOW_CATS` 外,標記「squash 未接 tier,需**耦合 amplify**」為 honest boundary。
- 本次(G-4''''')正好照那條邊界接上:**用耦合 amplify 讓 squash 也吃檔位增益且守恆不破**。

## 核心洞見:耦合 amplify

體積守恆對 `(scaleX, scaleY)` 的幅度放大,**兩通道必須一起、以守恆式重建**:

```
_amp_scale_coupled(sx, sy, g):
    q  = sx − 1               # stretch 量(squash 的 scaleX 恆 ≥1)
    q' = g · q                # 放大 stretch 量
    return (1 + q',  1/(1 + q'))   # 重建互為倒數對 → product 恆等 1
```

- **product 恆等 1**(面積守恆保持,honest boundary 關鍵);**scaleX'≠scaleY'**(仍非均勻真擠壓);
  q=0(identity 端點)→ (1,1) 不動;`g==1.0`(Super)→ 原樣返回 → 逐位元同 base(向後相容)。
- **等價於以 Q'=g·Q 重生成 `gen_squash`**:`gen_squash` 於極值 i 產 `q_i=Q·rⁱ`,放大即 `g·Q·rⁱ = g·q_i`
  → 兩路數值一致(實測 `_amp_scale_coupled` 輸出 == 解析式,P5c)。這是「幅度放大 = 在更大擠壓量重生成」
  的乾淨不變式,與 (J) 的 `_amp_scale`「= 在更大 overshoot 重生成」同構。
- **對照:逐通道 amplify(錯)**對同一極值 → scaleX 1.336、scaleY 0.862、prod 1.15 → 守恆破。
  這正是負對照 P5b(crux 的 crux)量到的鑑別點:**逐通道 FALSE / 耦合 TRUE**,證 honest boundary
  真實存在且耦合路徑必要。

## 做了什麼(全 additive)

1. **`tier_variants.MAIN_SHOW_CATS`** 加入 `"squash"`;新增 **`VOLUME_COUPLED_CATS = {"squash"}`**
   = scale 為體積守恆耦合對的類別。
2. **`tier_variants._amp_scale_coupled(sx, sy, g)`**(見上)+ `amplify_bone_tl(b, g, coupled_scale=False)`
   / `amplify_anim(anim, g, coupled_scale=False)` 加旗標:`coupled_scale=True` 時 scale 走耦合重建,
   `False`(預設)走原逐通道 `_amp_scale`(hit/combo/charge/reveal 的 anticipation squash 樓地板照舊不動)。
   **shear 通道不變**:仍 `v'=g*v`(對 0 對稱,同 wobble)—— 阻尼振盪簽章逐檔保形。
3. **`gen_animations.build_animations`**:`coupled = cat in VOLUME_COUPLED_CATS` → 對 squash 傳
   `coupled_scale=True`、其餘主秀傳 `False`。squash 非 count-aware(不在 `COUNT_AWARE_CATS`)→ cnt=None。
4. **`validate_squash_tier.py`**(新,5 AC)。
5. **`validate_tier_combo_count.py`** K5(c) 修正:原以 impact **峰計數**測「count 只作用 combo」,但 squash
   的 tier **幅度**差異化(scale 峰隨檔位變,屬 (J) 幅度軸非 (J-2) 連擊數)會被峰計數跨閾**誤判**為「峰數變」。
   改為 **full(gains+hits) == amp_only(gains) 逐位元比對**非-combo 變體 —— 直接隔離「連擊數」效應、
   不依賴 impact 峰計數,是更強更直接的判準(非弱化:峰計數只是原本能過的間接代理)。
6. **`check_readiness`** 新增 cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(仍 HOLD)。
7. 圖 `knowledge/figures/s1_squash_tier.png`。

## AC(`validate_squash_tier.py`,5 條全 PASS)

從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(tier_gains=…)` 端到端量:

- **P1 present + backward-compat**:每檔位 `squash__{tier}` finite/有 bone/≥1 bone 同時帶 shear+scale/
  名經 `beat_category` 仍路由回 squash;base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元
  不變、且 `squash__Super`(g=1)逐位元 == base squash。
- **P2 crux — 雙軸遞增**:各檔位 (a)峰 |shearX| [16,21.6,27.2,33.6]° **與** (b)最大擠壓量 max|scaleX−1|
  [0.16,0.216,0.272,0.336] **皆** Super<Mega<Omg<Legend 嚴格遞增;Super==base。
- **P3 crux — 每檔位體積守恆**:每個檔位的每個 squash 極值幀仍 (a)scaleX·scaleY≈1(|prod−1|≤2e-2,
  實測 <5e-5);(b)非均勻 |scaleX−scaleY|≥0.05;(c)擠壓量隨極值嚴格遞減(阻尼耦合)。復用 G-4'''' 的
  `_sq3_eval` 判準 → 與 squash-gen 閘完全一致。**這條證明耦合 amplify 沒破壞守恆(honest boundary 關上)**。
- **P4 shear 簽章 + identity 介面**:每檔位 shear 首尾 0/繞 0 變號≥3/相繼極值嚴格遞減(阻尼保形);
  scale 首尾 (1,1)(可插 Loop 間)。
- **P5 負對照**:(a)**平增益守衛**全 1.0 → P2 遞增 FALSE 且各檔位逐位元 == base(證閘測遞增非恆真);
  (b)**耦合必要性守衛(crux 的 crux)**:同一合成極值逐通道 amplify 體積 FALSE(prod 1.15)vs 耦合 TRUE
  (prod 1.0)且仍非均勻;(c)**耦合≡重生成**:`_amp_scale_coupled` 輸出 == 解析 (1+g·q, 1/(1+g·q))。

端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}`
(經 pivot 補償後體積守恆仍成立),`validate_build` round-trip overall_pass。回歸 **18 閘全綠**
(squash_gen/wobble_count/wobble_tier/tier_combo_count(K5 更新)/tier_variants/shear 全系列/全 priors/beat/pivot)。

## 關鍵發現

- **體積守恆軸的檔位幅度差異化需「耦合 amplify」,不能逐通道** —— 當幅度軸落在一個**互相約束的通道對**
  (scaleX·scaleY≡1)上時,逐通道獨立放大會破壞約束;必須抽出共享參數(stretch 量 q)、放大、再以約束式
  重建整對。這與 (J-2)/(G-4''') 的「段數軸須在 gen 時決定」並列為**「每個軸各有其正確接法」**的第三型:
  幅度軸(J,逐通道)/ 段數軸(J-2、G-4''',gen 時重生成)/ **守恆耦合幅度軸(G-4''''',耦合重建)**。
- **又一「檔位機制就緒 ≠ 每個通道/軸接上」實例**(同 E/H/I/J/G-4'/G-4''/G-4''')。誠實地:檔位差異化
  對 shear 是「更斜」、對守恆 scale 是「擠得更狠但依舊守體積」—— 強度變、結構(守恆+阻尼)不變。
- **閘維護誠實**:tier_combo_count K5(c) 的 impact-峰計數判準對「不改連擊數、只改幅度」的 squash 會假陽性;
  換成「count-map 開/關逐位元比對」是把**測試意圖**(count 只作用 combo)表達得更精準,而非放寬。

## honest boundary(仍在)

- shear 峰 + 擠壓量的檔位階梯沿用 (J) 的增益 `{1.0,1.35,1.70,2.10}`(PROPOSAL,手感留使用者 A 類)。
- `shearY≡0`(純 shearX 斜拉)。
- **squash count-aware**(擠壓/振盪段數隨檔位遞增,`gen_squash(nosc=)` 已備參數,比照 G-4''')為後續
  —— 本次只做幅度軸(耦合),段數軸未接。
- 單一真值資產(robot),運動基元為先驗庫 PROPOSAL → `spine-anim-forge` 區塊仍 **HOLD**(防半成品固化)。

## 相關

- 上游:`s1-squash-shear-scale-coupling.md`(G-4'''',gen_squash 本體)、`s1-tier-variant-amplitude.md`
  (J,`_amp_scale` 逐通道幅度)、`s1-wobble-tier-amplitude.md`(G-4'',shear 峰接檔位)、
  `s1-wobble-count-generation.md` / `s1-tier-variant-combo-count.md`(段數軸)。
- 工具:`tools/analyzer/tier_variants.py`(`_amp_scale_coupled`、`VOLUME_COUPLED_CATS`)、
  `gen_animations.py`(build_animations 路由)、`validate_squash_tier.py`。
