# S1 (G-4''''') squash 接檔位幅度差異化 —— 體積守恆**耦合 amplify**(log 空間 v^g)

> candidate G-4'''''(2026-09-20)。續 G-4''''(`gen_squash` 產耦合 shear + 非均勻 scale),補上它留到
> 現在的第一個 honest boundary:**squash 未接 tier(需耦合 amplify)**。

## 一句話

把 squash(shear + 體積守恆非均勻 scale 的斜拉擠壓)接進檔位機制:scale 通道改走 **log 空間耦合放大
`v' = v^g`**,使 **shear 峰與 squash 非均勻峰同隨檔位遞增**(愈高檔位愈斜愈擠),同時 **體積守恆
`scaleX·scaleY ≡ 1` 對每個檔位都保持** —— 而 (J) 舊 `_amp_scale` 會破壞守恆。

## 為什麼是這一步(補的 honest boundary)

G-4''''(`squash_shear_scale_coupling`)讓 `gen_squash` 成為第一個同時產 shear + 非均勻 scale 的生成器,
但當時 **squash 不在 `MAIN_SHOW_CATS`** → 檔位機制(J/G-4'')完全沒放大它。原因很具體、是個真正的機制缺口:

- squash 的 scale 是**體積守恆對**:`scaleX = 1+q`(拉長 >1)、`scaleY = 1/(1+q)`(壓扁 <1),`scaleX·scaleY == 1`。
- (J) 的 `_amp_scale(v,g) = 1 + g(v−1) if v≥1 else v`:**只放大 identity 上方、下方樓地板不動** ——
  對 squash 就是 `scaleX>1` 被放大、`scaleY<1` 原封不動 → 放大後 **`scaleX·scaleY ≠ 1`,破壞守恆**
  (squash 退化成單軸拉長,不再是「擠壓」)。實測 Legend(g=2.1)下積誤差達 **0.15**(見 V5b / 圖右)。

所以 squash 的檔位差異化**不能沿用**幅度增益,需要一個**保守恆的 amplify**。這就是本 cap。

## 機制(deterministic,`tier_variants`)

**key insight:log 空間放大天然保守恆。** 對 scale 值取 g 次冪:

```
_amp_scale_coupled(v, g) = v ** g        # (v==1 → 1^g==1;g==1 → v,逐位元不變)
```

兩軸**同以 g 次冪**放大 ⇒ 放大後積 `= (scaleX·scaleY)^g = 1^g = 1` —— **守恆對任意 g 保持,且與哪一軸
拉長無關**(軸無關/一般,不必知道 scaleX 是拉長軸)。同時:

- **非均勻遞增**:`|scaleX^g − scaleY^g|` 隨 g 單調變大 → 檔位愈高擠壓愈明顯(圖左/中/右)。
- **identity 介面保持**:端點 `scaleX==scaleY==1 → 1^g==1` 不動 → 可插 Loop 間(同其他主秀 beat)。
- **阻尼耦合保形**:每極值 `q_i = Q·rⁱ` 遞減 → `(1+q_i)^g − 1` 仍隨 i 嚴格遞減(單調函數保序)→ SQ3 阻尼簽章保。
- **g=1.0 逐位元不變**:`v**1.0 == v`(Super 檔位 → 向後相容 byte-identical)。

shear 通道沿用 (G-4'') 的 `v' = g*v`(對 0 對稱)→ **shear 與 squash 兩通道同以檔位增益 g 一起放大
(耦合放大)**:愈高檔位「愈斜」且「愈擠」,兩簽章(阻尼振盪 + 體積守恆)都在每個檔位保形。

### 接線

- `tier_variants.MAIN_SHOW_CATS` 加入 `squash`;新增 `VOLUME_CONSERVING_CATS = {"squash"}`。
- `amplify_bone_tl(b, g, coupled_scale=False)` / `amplify_anim(anim, g, coupled_scale=False)`:
  `coupled_scale=True` → scale 走 `_amp_scale_coupled`(v^g),否則走 `_amp_scale`(舊,只放大上方)。
  shear/rotate/translate 兩路徑一致(v'=g*v)。
- `gen_animations.build_animations`:`cat ∈ VOLUME_CONSERVING_CATS` 時以 `coupled=True` 呼叫 `amplify_anim`。
  端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}`。

## 量化結果(真實 robot 骨架,bone `b_光暈`)

| tier   | gain g | shear 峰(°) | 非均勻峰 \|sx−sy\| | 積 scaleX·scaleY | 端到端 pivot 殘差(px) |
|--------|--------|-------------|-------------------|------------------|----------------------|
| Super  | 1.00   | 16.0        | 0.298             | ≈1 (±1e-4)       | 0.018(左手,arm 126）|
| Mega   | 1.35   | 21.6        | 0.403             | ≈1               | 0.033                |
| Omg    | 1.70   | 27.2        | 0.510             | ≈1               | 0.053                |
| Legend | 2.10   | 33.6        | 0.633             | ≈1               | **0.084**            |

兩通道峰皆嚴格遞增;積恆守恆;放大後最爆檔位 pivot 仍精確不動(負對照未補償達 72px,>800×)。

## 自我驗收閘 `validate_squash_tier.py`(6 AC 全 PASS)

- **V1** present + backward-compat:每檔位 `squash__{tier}` 產出/finite/雙通道;名經 `beat_category` 仍路由回
  squash;base + In/Loop/Out 帶/不帶 tier_gains 逐位元不變。
- **V2 crux** dual-channel peak monotone:shear 峰 **且** 非均勻峰 Super<Mega<Omg<Legend 嚴格遞增;Super==base。
- **V3 crux** volume preserved per tier:**每個檔位**每極值 `|scaleX·scaleY−1|≤TOL_VOL`(耦合放大不破壞守恆)
  + 非均勻 + squash 幅度阻尼遞減 + shear 阻尼振盪(復用 G-4'/G-4'''' 判準)。
- **V4** identity 介面/tier:每檔位 sample(0)/sample(dur) identity、shear 首尾 0、scale 首尾 (1,1)。
- **V5** neg-control:(a) 平增益全 1.0 → 遞增 FALSE 且各檔位 == base;
  **(b crux)耦合必要性守衛**:同一 squash scale 套**舊** `_amp_scale`(g=2.1)→ 體積守恆 **FALSE**(積誤差 0.152),
  套**耦合** `_amp_scale_coupled` → 守恆 TRUE(誤差 1e-4)且非均勻 TRUE → 證「不能沿用舊 amplify、耦合 amplify 必要」;
  (c) 通道隔離單元測(守恆對放大後積==1、coupled 旗標只改 scale 路徑、g=1 byte-identical)。
- **V6 crux** amplified pivot-fixed:端到端 `--tier-variants --shear-pivot`,**放大後**的變體(含最爆 Legend)
  pivot 殘差 < TOL_FIX,負對照 >20× → 放大不破壞端到端不動點(`apply_pivots` 對放大後的一般仿射重算補償 Δ)。

## 關鍵發現

- **log 空間放大是體積守恆變換的自然保形操作**:如同「同比放大 g*v 是阻尼振盪簽章的保形變換」(G-4''),
  「取 g 次冪 v^g」是**體積守恆對**的保形變換 —— 檔位改強度、不改守恆結構,且軸無關(不必知哪軸拉長)。
- **一個節拍加入檔位機制,得先問它的簽章在哪個代數群下保形**:平移/旋轉/純 shear 在加法群(g*v 保形);
  體積守恆 scale 在乘法群(v^g 保形)。選錯放大算子(對守恆對用加法 amplify)就破壞簽章。
- 又一「檔位機制就緒 ≠ 每個新通道接上」實例(同 E/H/I/J/G-4'/G-4''/G-4'''),惟本次的接法需**換放大算子**
  (前幾次都在加法群內)—— 是這條線第一次因通道的**保形群不同**而改 amplify。

## honest boundary(仍在)

- squash **count-aware 未接**(擠壓段數隨檔位;`gen_squash(nosc=)` 已備參數,比照 G-4''' 之於 wobble)——
  本次只做幅度軸(段數恆 4)。與段數軸正交,為後續。
- shearY≡0(單軸 shear;雙軸 shear / 三通道同時仍為後續 G-4'''''')。
- 增益階梯數值 [1.0,1.35,1.70,2.10] 沿用 (J)(PROPOSAL,結構簽章非美感;手感留使用者 A 類)。
- 單一真值資產(robot);與 `spine-anim-forge` 同 HOLD(運動基元為先驗手感、防固化)。

## 檔案

- 生成:`tools/analyzer/tier_variants.py`(`_amp_scale_coupled` / `VOLUME_CONSERVING_CATS` / `amplify_*` 加
  `coupled_scale`)、`tools/analyzer/gen_animations.py`(build_animations 依 cat 路由耦合放大)。
- 閘:`tools/analyzer/validate_squash_tier.py`(6 AC)。
- 回歸修:`tools/analyzer/validate_tier_combo_count.py`(K5c 改用 full vs amp_only 逐位元隔離,對 squash
  等非-scale-overshoot 節拍穩健;原 `_min_peaks` 啟發式對 squash 誤判)。
- 圖:`knowledge/figures/s1_squash_tier.png`。
