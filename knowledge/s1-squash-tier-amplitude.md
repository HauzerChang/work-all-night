# S1 — squash 接檔位差異化:耦合體積守恆 amplify(candidate G-4''''',`squash_tier_amplitude` L2)

> 2026-09-14。把 (G-4'''') 新生成的 **squash 節拍(shear + 耦合非均勻 scale 的體積守恆擠壓)** 接進
> (J) 的**檔位幅度差異化**機制:squash 的擠壓強度隨檔位(Super→Legend)遞增 —— **非均勻峰
> |scaleX−scaleY| 與 shear 峰兩軸同步嚴格遞增,而體積 scaleX·scaleY≡1 恆守恆、阻尼簽章每檔位保形**。
> 又一「檔位機制就緒 ≠ 每個新通道接上」實例(同 E/H/I/J/G-4'/G-4''),且是**第一個需要「耦合 amplify」
> 的通道**(前面所有通道的檔位增益都是逐軸獨立的)。

## 缺口(G-4'''' 明標的 honest boundary)

- **(G-4'''')** 讓 `gen_squash` 成為第一個同時產 **shear + 非均勻 scale** 的生成器,scale 通道是
  **體積守恆對**:scaleX=1+q(拉長)、scaleY=1/(1+q)(壓扁),scaleX·scaleY≡1。
- 但當時 **squash ∉ `MAIN_SHOW_CATS`**,因為 (J) 的幅度增益 `_amp_scale` **只放大 identity 上方
  overshoot**(`v'=1+g(v−1)` 僅當 v≥1,下方樓地板不動)。套到 squash 對:
  - 拉長軸 scaleX=1+q (≥1) → 放大成 1+g·q ✅
  - 壓扁軸 scaleY=1/(1+q) (<1) → **不動**(視為 collapse 樓地板)❌
  - 積 = (1+g·q)/(1+q) **≠ 1 → 體積守恆壞掉**(g=2.1、q=0.16 時積=1.152)。
- G-4'''' 誠實標記:「squash 的檔位差異化需**耦合 amplify**,後續」。本次正好照那條邊界接上。

## 做了什麼(全 additive)

1. **`tier_variants.MAIN_SHOW_CATS`** 加入 `"squash"` → `build_animations(tier_gains=)` 對 squash
   也產 `squash__{tier}` 變體(In/Loop/Out 仍檔位無關)。
2. **`tier_variants.COUPLED_SCALE_CATS = {"squash"}`**:標記「scale 為體積守恆非均勻對、需耦合 amplify」
   的類別(依 cat 路由,同 `COUNT_AWARE_CATS` 的路由方式)。
3. **`tier_variants._amp_squash_scale(x, y, g)`**(耦合增益,體積守恆):
   ```
   sx = _amp_scale(x, g)      # 放大拉長軸:1 + g·(x−1)(沿用 J 的 linear-in-overshoot)
   sy = 1.0 / sx              # 壓扁軸取拉長軸的倒數 → sx·sy ≡ 1(體積恆守恆)
   ```
   - x==1(identity 幀)→ (1,1):**介面契約保持**(可插 Loop);
   - **g==1.0 → sx=x、sy=1/x==原 scaleY**:耦合在 base 檔位退化為 identity 變換(向後相容)。
4. **`amplify_bone_tl(b, g, coupled_scale=False)` / `amplify_anim(..., coupled_scale=False)`**:
   `coupled_scale=True` → scale 走 `_amp_squash_scale`;預設 False → 逐軸獨立 `_amp_scale`
   (等比 pulse:hit/combo/… 及所有既有節拍**逐位元不變**,向後相容)。
5. **`gen_animations.build_animations`**:`coupled = cat in COUPLED_SCALE_CATS` → 產 squash 變體時傳
   `coupled_scale=True`。squash 不在 `COUNT_AWARE_CATS`(nosc 恆 4、不隨檔位;count-aware 為後續)。

## 為什麼「耦合」是本質、逐軸獨立不行

- 前面所有檔位通道(scale-pulse 的 scaleX/scaleY、rotate、translate、shear)都對 identity/0 **逐軸
  對稱**,故逐軸獨立放大就對。squash 的兩軸**互為倒數約束**(scaleX·scaleY≡1),放大一軸就**強制**另一軸,
  這是第一個**跨軸耦合**的檔位增益。
- 選 `sy=1/sx` 而非「兩軸都乘 g」的理由:體積守恆是 squash 的**定義性簽章**(SQ3 crux);任何破壞
  scaleX·scaleY≡1 的放大都會把「果凍擠壓」變成「脹大/縮小」,語意就變了。倒數約束讓「擠壓更狠」
  (非均勻更大)與「體積不變」兩件事同時成立。

## 驗收(`validate_squash_tier.py`,先驗庫→**真實 build_spine robot 骨架**→build_animations(tier_gains))

**5 AC 全 PASS**:

- **V1 present + backward-compat**:每檔位 `squash__{tier}` 產出、finite、有 bone、≥1 bone 帶 shear
  且帶非均勻 scale、名經 `beat_category` 仍路由回 squash;**base(含 In/Loop/Out + base squash)
  逐位元不變**;Super(g=1)shear/非均勻峰皆 == base。
- **V2 crux — 耦合體積守恆 amplify**:(a) **每檔位每極值幀** |scaleX·scaleY−1| ≤ 0.02(實測 max 4.6e-5,
  巨大餘裕);(b) 非均勻峰 max|scaleX−scaleY| **Super 0.298 < Mega 0.394 < Omg 0.486 < Legend 0.588**
  嚴格遞增。
- **V3 shear peak monotone**:峰 |shearX| **[16, 21.6, 27.2, 33.6]°** 嚴格遞增且 Super==base
  (scale 與 shear 兩幅度軸同步放大)。
- **V4 signatures preserved**:每檔位仍 (a) shear 首尾 0 + 繞 0 變號≥3 + 相繼極值嚴格遞減(阻尼);
  (b) squash 幅度 |scaleX−1| 隨極值嚴格遞減(阻尼耦合)→ 耦合 amplify 是簽章保形變換。
- **V5 neg-control**:(a) **耦合必要性守衛**:對 base squash 施 plain(非耦合)amplify(g=Legend)→
  |積−1| = 0.152 ≫ 0.02 **體積守恆 FALSE**(coupled 同幀 ≤4.6e-5)→ 證 (G-4'''') 未接的正是這條、
  耦合非多餘;(b) **平增益守衛**:全 1.0 → V2/V3 遞增 FALSE 且各檔位 squash 逐位元==base(耦合 g=1
  退化 identity);(c) **耦合隔離**:耦合 amplify 只路由給 squash —— 對等比 pulse bone(scaleX==scaleY)
  施耦合會破壞等比(sy=1/sx≠sx),故產線對 hit/combo 等仍走 plain;全 storyboard 非-squash 主秀變體
  的 scale 皆等比(未被耦合污染)。

**端到端**:`build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}`
(5 bone 全帶 shear+scale;pivot 補償後仍體積守恆),`validate_build` round-trip **overall_pass**
(premult MAE 0.031、setup 不變)。

**回歸**:squash_gen(G-4'''')/wobble_tier(G-4'')/wobble_count(G-4''')/shear_gen(G-4')/
shear_pivot(G-4)/scale_pivot(G-3)/pivot_rotation(0i)/tier_variants(J)/**tier_combo_count(J-2,
K5c 更新)**/priors/priors_beats/priors_combo_charge/priors_cascade/cascade/more_beats/
beat_templates/deform_gen **全綠**。

- ⚠️ **tier_combo_count K5c 微調(類別錯配修正)**:K5c「count 只作用 combo」以 `impact_peaks`
  (scaleX **脈衝串**偵測器)量非-combo 主秀 beat 的峰數是否各檔位不變。squash 進 MAIN_SHOW 後,其
  scaleX 是**體積守恆拉長**(nosc 恆 4、不隨檔位;耦合 amplify 讓拉長幅度隨檔位遞增)→ 更多阻尼峰跨過
  impact prominence 門檻 → peak-count 隨檔位變。這是**幅度效應非 count 外洩**(squash 從不被
  `tier_combo_hits` 重生成)。以 scaleX 脈衝計數量 squash 屬**類別錯配**,故 K5c 略過 `SHEAR_CATS`
  (wobble/squash);wobble 無 scale(峰數恆 0)本就不觸發,squash 由此排除。intent 不變。

## 關鍵發現

1. **耦合 amplify 是新的一類檔位增益**:前面所有通道逐軸/對稱獨立放大即可;squash 的兩軸倒數約束
   (scaleX·scaleY≡1)使**放大一軸強制另一軸**,是第一個跨軸耦合的檔位增益。`COUPLED_SCALE_CATS`
   把這條路由集中一處,便於後續其他體積守恆節拍沿用。
2. **兩幅度軸同步、結構軸(段數)不動**:squash 同時吃 shear 增益(g·v)與 scale 耦合增益,兩軸同步遞增;
   而振盪**段數** nosc 恆 4(count-aware 為後續,同 G-4''' 之於 wobble)—— 幅度與段數再次正交。
3. **負對照 (a) 直接量出 G-4'''' 標記的邊界**:同一份 base squash,plain amplify 破壞體積守恆
   (0.152)、coupled 守恆(4.6e-5),把「為什麼需要耦合」變成可量化、可回歸的守衛。

## honest boundary(仍在)

- **squash 未接 count-aware**:擠壓段數 nosc 恆 4,不隨檔位;`gen_squash(nosc=)` 已備參數,接法同
  (G-4''')之於 wobble(`TIER_SQUASH_CYCLES` + build 依 cat 路由)。
- **shearY≡0**:squash 只產 shearX(單軸 shear);雙軸 shear / shear+scale+rotate 三通道同時的運動基元
  (塞滿一般仿射 M 的所有自由度)為後續(G-4'''''')。
- 增益階梯沿用 (J) 的 TIER_GAIN(PROPOSAL,手感留使用者 A 類);單一真值資產(robot)。

cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
圖 `figures/s1_squash_tier.png`(左:各檔位落在體積守恆雙曲線上、plain amplify 掉出線外;
中:非均勻峰與 shear 峰兩軸同步遞增;右:每檔位阻尼階梯保形)。
