# S1 (G-4''''') squash 接檔位幅度差異化 —— **耦合 amplify**(體積守恆的對數應變放大)

> candidate G-4'''''(2026-09-17)。續 G-4''''(`gen_squash` 第一個同時產 shear+非均勻 scale)的 honest
> boundary:**squash 未接 tier 幅度差異化**(squash 不在 `MAIN_SHOW_CATS`,因一般 `_amp_scale` 會破壞體積守恆)。

## 一句話

squash(斜拉果凍擠壓)的檔位差異化不能用一般 `_amp_scale`(只放大 identity 上方、下方樓地板不動 →
`scaleX·scaleY≠1` 破壞守恆);改用**耦合 amplify** `_amp_scale_coupled(v,g)=v**g`(均勻放大對數應變),
使 squash 的 **shear 峰與 scale 非均勻峰皆隨檔位嚴格遞增**,而**體積守恆(面積守恆)在每個檔位保持**。

## 為什麼是這一步(補的 honest boundary)

- (J) `tier_variant_amplitude` 讓主秀 beat 依檔位**幅度**差異化,但增益只作用 scale/rotate/translate;
  (G-4'') 讓 wobble 的 **shear** 峰隨檔位遞增(對 0 對稱 → `v'=g*v`)。
- G-4'''' 的 squash 其 scale 通道是**體積守恆**(`scaleX·scaleY==1`、`scaleY<1` 壓扁)。若沿用
  `_amp_scale`(`v≥1` → `1+g(v−1)`;`v<1` 樓地板不動),則 `scaleX` 被放大而 `scaleY` 不動 →
  `scaleX·scaleY≠1`(守恆破壞)。故 G-4'''' 當時把 squash 留在 `MAIN_SHOW_CATS` 外,檔位差異化留白。
- 本次(G-4''''')補上 squash 專用的**耦合 amplify**,把「保積 scale 節拍的檔位放大」這最後一段接上。
  又一「檔位機制就緒 ≠ 每個新通道接上」實例(同 E/H/I/J/G-4'/G-4''/G-4''')。

## 核心:體積守恆 scale 的自然幅度座標 = 對數應變

保積 scale 的一對值是 `(scaleX=s, scaleY=1/s)`,故 `ln(scaleX) = −ln(scaleY)`。令對數應變 `u = ln(v)`,
以增益 `g` **均勻放大** `u' = g·u` ⇒ `v' = v**g`。此變換的四個關鍵性質:

1. **保積(對 g 恆真)**:對任一對 `(sx, sy)` 且 `sx·sy==1` → `sx**g · sy**g = (sx·sy)**g = 1**g = 1`。
   —— 不需 `sy` 恰為 `1/sx` 的閉式,只需其積為 1,故對 gen 出來的(已四捨五入)值同樣穩健(積≈1 → 放大後仍≈1)。
2. **identity 定點**:`1**g = 1` → 端點(首尾 (1,1))與任何 identity 幀對**所有檔位保持**(可插 Loop)。
3. **單調**:`sx>1`(拉長)→ `sx**g` 隨 g 變大;`sy<1`(壓扁)→ `sy**g` 隨 g 變小(擠壓更深) → 非均勻峰 `|sx−sy|` 隨 g 遞增。
4. **g=1.0 → identity 變換**:`v**1.0==v` 於 float 精確 → 對已 4 位小數的 gen 輸出逐位元不變(向後相容)。

對照:`_amp_scale`(線性、只放大上方)是**非保積 overshoot**(hit/combo/charge 的等比 pulse)的正確幅度規則;
兩者各自適用不同 scale 語意 —— 由 `COUPLED_SCALE_CATS` 依類別路由。

## 實作(全 additive)

- `tier_variants.py`:squash 加入 `MAIN_SHOW_CATS`;新 `COUPLED_SCALE_CATS = {"squash"}`;
  新 `_amp_scale_coupled(v,g)=v**g`;`amplify_bone_tl(b,g,coupled_scale=False)` / `amplify_anim(...)` 加旗標
  (`coupled_scale` 時 scale 走耦合 amplify,shear/rotate/translate 兩路相同 `v'=g*v`)。
- `gen_animations.py`:`build_animations` 對 `cat in COUPLED_SCALE_CATS` 的 tier 變體傳 `coupled=True`。
- `validate_tier_combo_count.py`:K5c(count 隔離)對 `COUPLED_SCALE_CATS` 略過 —— squash 的 `scaleX` 拉長量
  隨檔位增乃**設計**,`impact_peaks(scaleX)`(combo overshoot 計數器)會在高檔位因越過 prominence 門檻而多算,
  屬類別誤用(squash 的結構 count = nosc 段數,各檔位恆定,由 squash-tier 閘 ST2/ST4 保證);非 combo count 外洩。
- 端到端:`build_spine --animate --tier-variants --shear-pivot` 自動直出 `squash__{tier}`(無需改 build_spine)。

## 自驗閘 `validate_squash_tier.py`(先驗庫 → 真實 build_spine robot 骨架 → build_animations,6 AC 全 PASS)

- **ST1 present + backward-compat**:每檔位 `squash__{tier}` finite/有 bone/≥1 bone 同時帶 shear+scale/名路由回
  squash;base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變。
- **ST2 crux — 雙軸峰遞增**:各檔位 shear 峰 [16,21.6,27.2,33.6]° **與** scale 非均勻峰
  [0.298,0.403,0.510,0.633] **皆嚴格遞增**,且 Super(g=1)兩峰 == base。
- **ST3 crux — 每檔位保積**:每檔位每個 scale 極值幀 `|scaleX·scaleY − 1| ≤ 0.02`(耦合 amplify 保積)。
- **ST4 每檔位阻尼保形**:shearX 首尾 0 + 繞 0 變號 ≥3 + 相繼極值遞減;squash 幅度 `|scaleX−1|` 隨極值遞減。
- **ST5 每檔位 identity 介面**:sample(0)/sample(dur) 各 bone identity、shear 首尾 0、scale 首尾 (1,1)。
- **ST6 負對照/必要性**:(a) 平增益全 1.0 → 兩峰遞增 FALSE 且各檔位==base;
  **(b) crux 必要性**:同一 squash scale 幀施天真 `_amp_scale`(g=Legend)→ 至少一極值 `|scaleX·scaleY−1|>0.02`
  (守恆破壞,實測 prod 1.02–1.15),而耦合 amplify 同 g 仍守恆 → **證耦合 amplify 是必要而非裝飾**;
  (c) 耦合單元測:保積 + g=1 逐位元;(d) 隔離/加性:squash 入 MAIN_SHOW_CATS 不擾動其他 beat 及其 __tier 變體。

## 關鍵發現

- **保積 scale 的幅度放大 = 均勻放大對數應變**(`v**g`)。線性放大(`_amp_scale`)對「有樓地板語意的非保積
  overshoot」正確,但對保積擠壓會破壞守恆 —— **不同 scale 語意需不同幅度規則**,由 `COUPLED_SCALE_CATS` 路由。
- 這是「檔位=更強、不改結構」在**保積通道**的體現:shear 峰與非均勻峰同步變大(更斜更擠),而守恆/阻尼/介面
  三個結構簽章逐檔保形。與 (J)「只放大 identity 上方 overshoot」、(G-4'')「shear v'=g*v」同型,只是保積約束下的正解。

## Honest boundary(仍在,後續候選)

- 幅度增益階梯沿用 (J) `TIER_GAIN`(Super1.0/Mega1.35/Omg1.70/Legend2.10,PROPOSAL,手感留使用者 A 類)。
- **shearY≡0**(斜拉只在 X)。
- **squash count-aware**(擠壓段數 nosc 隨檔位,`nosc` 參數已備、`_squash_env(A,Q,nosc)` 已支援)為後續,比照 J-2/G-4'''。
- 單一真值資產(robot_parts / Award);運動基元為先驗 PROPOSAL。cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(**仍 HOLD**,防固化)。

## 檔案 / 指令

- 幅度:`tools/analyzer/tier_variants.py`(`_amp_scale_coupled`/`COUPLED_SCALE_CATS`/`coupled_scale_for`/`amplify_bone_tl(coupled_scale=)`)。
- 路由:`gen_animations.py`(`build_animations` 依 `COUPLED_SCALE_CATS` 傳 `coupled`)。
- 閘:`tools/analyzer/validate_squash_tier.py`(`python3 validate_squash_tier.py [--json]`)。
- 回歸修正:`validate_tier_combo_count.py` K5c 對 `COUPLED_SCALE_CATS` 略過 impact 計數。
- 端到端:`build_spine.py --animate --tier-variants --shear-pivot`。
- 回歸:18 閘全綠 + round-trip `validate_build` overall_pass。
- 圖:`knowledge/figures/s1_squash_tier.png`。
