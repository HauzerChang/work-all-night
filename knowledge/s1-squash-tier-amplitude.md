# S1 — squash 接檔位差異化:體積守恆耦合放大(candidate G-4''''')

> 里程碑 2026-09-14。補 G-4''''(`gen_squash` 產耦合 shear + 非均勻 scale 體積守恆擠壓)留下的
> honest boundary:**squash 未接 tier 幅度差異化**。相關:`s1-squash-shear-scale-coupling.md`(G-4'''')、
> `s1-wobble-tier-amplitude.md`(G-4''、shear 峰接檔位)、`s1-tier-variant-amplitude.md`(J、幅度增益機制)。

## 問題:守恆量的檔位放大不能各軸獨立

candidate (J) 的檔位幅度增益 `_amp_scale(v,g)=1+g(v−1) (v≥1) / v (v<1)`:只放大 identity **上方**
overshoot,下方(squash/collapse 樓地板)不動。這對 hit/combo 的**獨立雙軸** scale 是對的
(拉長軸放大、壓縮/樓地板保結構語意)。

但 squash 的 scale 兩軸是**面積守恆對**:`(scaleX, scaleY) = (1+q, 1/(1+q))`,乘積 ≡ 1。
各軸獨立套 `_amp_scale` 會把拉長軸(scaleX=1+q ≥1)放大成 `1+g·q`、壓縮軸(scaleY=1/(1+q) <1)
**樓地板不動** → 乘積 `(1+g·q)·1/(1+q) ≠ 1` → **體積守恆破壞**。實測 Legend 檔(g=2.1)乘積達
**1.15**(15% 破壞)。這正是 G-4'''' 把 squash **排除**在 `MAIN_SHOW_CATS` 外的原因。

## 解法:耦合放大——放大不變量本身(q),另一軸重算為倒數

**關鍵洞見:守恆量的檔位差異化,必須放大守恆結構的自由參數(這裡是 squash 量 q),不是各軸獨立放大。**
squash 對由單一 q 參數化;檔位放大 `q → g·q` ⇒ `(1+g·q, 1/(1+g·q))` **仍守恆**(乘積恆 1)。

實作 `tier_variants._amp_scale_coupled(x, y, g)`:
- 認**拉長軸**=較大者(對稱,未來雙軸 squash / shearY 亦適用);
- 拉長軸套原 `_amp_scale`(`x'=1+g(x−1)`,與其他主秀 beat 拉長軸**同一語意**);
- 壓縮軸**重算為拉長軸的倒數**(`y'=1/x'`)→ `x'·y'≡1` 對**所有檔位**保持;
- identity 幀(x==y==1)→ 仍 identity(g 無關,端點介面契約保持,可插 Loop)。

幅度 `q'=g·q` 隨檔位單調變大(非均勻峰遞增)、q 序列同乘 g → 相繼遞減比不變(阻尼耦合保形)。
shear 通道與 coupled 無關,仍 `v'=g*v`(同 wobble/rotate/translate)→ **shear 峰與非均勻幅度同時隨檔位遞增**。

### 接線(全 additive,向後相容)

- `amplify_bone_tl(b, g, coupled=False)` / `amplify_anim(anim, g, coupled=False)`:coupled=True 時 scale
  走耦合放大;**預設 False → 逐位元同舊行為**(hit/combo/… 獨立雙軸 scale 不變)。
- `COUPLED_SCALE_CATS = {"squash"}`;`squash` 併入 `MAIN_SHOW_CATS`(G-4'''' 的 boundary 解除)。
- `build_animations`:`coupled = cat in COUPLED_SCALE_CATS` → squash 變體走耦合放大,其餘主秀走原路徑。

## 驗收閘 `validate_squash_tier.py`(5 AC 全 PASS)

從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(tier_gains)` 端到端量:

- **V1** present + backward-compat:每檔位 `squash__{tier}` finite/有 bone/≥1 bone 同時帶 shear+scale/
  路由回 squash;**base 逐位元不變**;`tier_gains=None` 一致。
- **V2 crux** dual-channel monotone:shear 峰 `[16, 21.6, 27.2, 33.6]°` 與非均勻峰
  `[0.298, 0.394, 0.486, 0.588]` **皆** Super<Mega<Omg<Legend 嚴格遞增,且 Super==base。
- **V3 crux** 體積守恆每檔位保持:每檔位每極值幀 `|scaleX·scaleY−1| ≤ 1e-3`(耦合實測 <1e-4);
  squash 幅度每檔位阻尼遞減。**這是耦合 amplify 的關鍵回報(守恆對所有檔位,非只 base)。**
- **V4** 每檔位 identity 介面 + shear 阻尼簽章(變號≥3、極值遞減)保形。
- **V5** 負對照/隔離:
  - **(a) naive 守衛(crux 鑑別子)**:對同一 base squash 套**舊**各軸獨立 `_amp_scale` → Legend 檔
    體積破壞 **0.152** vs 耦合 **0.0001**(>1000×)→ 證 V3 非恆真、耦合 amplify 真在做事。
  - **(b) 平增益守衛**:全 1.0 → V2 遞增 FALSE 且各檔位 == base。
  - **(c) 耦合隔離**:`COUPLED_SCALE_CATS=={squash}`;獨立雙軸 scale 在 coupled=False 逐位元同舊
    `_amp_scale`(非 squash 主秀 beat 零回歸)。

端到端 `build_spine --animate --tier-variants --shear-pivot` 直出
`squash__{Super,Mega,Omg,Legend}`,round-trip `validate_build` overall_pass(premult MAE 0.031)。

## 回歸

18 閘全綠:squash_gen(G-4'''')/tier_variants(J)/tier_combo_count/wobble_tier/wobble_count/shear_gen/
shear_pivot/scale_pivot/pivot_rotation/priors/priors_beats/priors_combo_charge/priors_cascade/cascade/
more_beats/beat_templates/deform_gen/squash_tier + anim selftest + round-trip validate_build。

**副產(閘可信度提升)**:`validate_tier_combo_count.py` 的 K5(c)「count 隔離」舊以 scaleX impact
峰數為 proxy,對「scaleX 幅度隨檔位成長並跨越 impact 峰門檻」的 squash 拉長軸會**假陽性**(0→1 峰
是幅度效應非 count 外洩)。改為**本質比對**:非-combo 變體 `full(gains+hits)` 逐位元 == `amp_only(gains)`
—— 直接證 `tier_combo_hits` 不觸及非-combo beat,更強且不受幅度成長擾動。

## honest boundary(仍在)

- 增益階梯 `[1.0, 1.35, 1.70, 2.10]` 沿用 (J)(**PROPOSAL**;手感留使用者 A 類決策)。
- **shearY≡0**(squash 只掛 shearX + scaleX/scaleY;雙軸 shear 為後續)。
- **squash count-aware 未接**:擠壓段數隨檔位(nosc 已備參數,比照 G-4''' 對 wobble)為後續結構軸。
- **on-disk densify 中介幀漂移**:`build_spine --shear-pivot` 對 joint bone(右手/頭/左手)把 scale
  重取樣到密網格 → **極值關鍵幀守恆精確**(非 densify 的 光暈/身體 bone 乘積 4e-5),但 densify
  中介幀(倒數曲線凸性,線性內插)漂移 ≤0.013(Legend,同 base 比例)。屬 **shear-pivot 重取樣**
  性質、與 base squash 共享,**非耦合 amplify 引入**;設計層守恆(RULES 真相來源)精確。
- 單一真值資產(robot),cap `squash_tier_amplitude` L2(gen)併入 `spine-anim-forge` **仍 HOLD**
  (運動基元先驗、防固化;打包政策見 `skills/README.md`)。

## 通則(可推廣)

這是**「守恆不變量的檔位差異化」**首例:凡涉及守恆律(體積/長度/面積)的運動基元,其檔位放大
都須放大**守恆結構的自由參數**而非各輸出軸獨立放大。同 pattern 對後續任何守恆基元(等長鏈、
不可壓縮軟體)皆適用。另與 G-4''(wobble shear 峰接檔位)、J-2/G-4'''(count-aware 結構軸)並列,
再證「檔位機制就緒 ≠ 每個新通道/守恆結構接上」。
