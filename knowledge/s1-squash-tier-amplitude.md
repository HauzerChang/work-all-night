# S1 (G-4''''') squash — 擠壓強度隨檔位遞增(**體積守恆耦合 amplify**)

> candidate G-4'''''(2026-09-12 session 002)。續 G-4''''(squash 生成器)線,補上一路留到現在的
> honest boundary:**squash 未接 tier 幅度差異化**(`_amp_scale` 只放大 identity 上方會破壞體積守恆,
> 故 squash 當時**刻意不在** `MAIN_SHOW_CATS`)。

## 一句話

新增**體積守恆耦合 amplify** `_amp_scale_coupled`(log 空間同指數放大 `v' = v**g`),把 squash 併入
`MAIN_SHOW_CATS`,使**非均勻峰(與 shear 峰)隨檔位嚴格遞增,而體積守恆(scaleX·scaleY==1)+ 阻尼簽章
在每個檔位保持**(愈高檔位 = 更斜更擠,不是別種運動、守恆不破)。

## 為什麼需要新的 amplify(補的 honest boundary)

- (J) 的 `_amp_scale(v,g)= 1+g(v−1) if v≥1 else v`:**只放大 identity 上方 overshoot,下方(v<1)樓地板不動**。
  這對 hit/combo/reveal 是**誠實**的(squash-floor / collapse 深度是結構語意、非大獎強度)。
- 但 squash 的 scale 是**耦合的體積守恆非均勻 scale**:`scaleX = 1+q`(>1 拉長)、`scaleY = 1/(1+q)`(<1 壓扁),
  `scaleX·scaleY ≡ 1`。用 `_amp_scale` 逐軸獨立放大 → scaleX(>1)被放大、scaleY(<1)**樓地板不動** →
  `scaleX·scaleY ≠ 1`(**破壞體積守恆**)。這正是 G-4'''' 把 squash 留在 MAIN_SHOW_CATS 外的原因。
- 又一「檔位機制就緒 ≠ 每個通道接上」實例(同 E/H/I/J/G-4'/G-4''/G-4''')—— 但這次接上的不是「多加一個
  被放大的通道」,而是**通道的放大方式本身需換一種數學**(逐軸樓地板 → log 空間耦合)。

## 耦合 amplify（deterministic,`tier_variants._amp_scale_coupled`）

`_amp_scale_coupled(v, g) = v ** g`（log 空間同指數放大）。四條性質同時成立:

1. **體積守恆**:同幀兩軸各 `g` 次冪 → 積 `(scaleX·scaleY)**g`;原積==1 → 放大後**恆==1**(對任意 g)。
   這是逐軸樓地板 amplify 辦不到的關鍵。
2. **identity 介面保持**:`v==1 → 1**g == 1`(首尾 (1,1) 幀對所有檔位仍 identity,可插 Loop)。
3. **非均勻峰隨 g 遞增**:g>1 時 scaleX(>1)更大、scaleY(<1)更小 → `|scaleX−scaleY|` 單調變大(檔位簽章);
   g==1 → identity 變換(**向後相容逐位元**)。
4. **阻尼遞減保形**:各極值 `q_i` 嚴格遞減 → `(1+q_i)**g` 亦嚴格遞減(`x**g` 對 x>0 單調)→ squash 幅度序列
   遞減簽章保持。

`coupled` 旗標只作用 **scale** 通道;shear / rotate / translate 仍 `v'=g*v`(對 0 對稱,同 wobble/hit)。
`build_animations` 依 `cat in VOLUME_CONSERVE_CATS` 路由該 beat 的 scale 用一般 or 耦合增益。

## 實測(端到端,slot_bigwin robot,tier_gains g=[1.0,1.35,1.70,2.10])

| tier | 非均勻峰 \|scaleX−scaleY\| | shear 峰 \|shearX\|° | 最壞 \|scaleX·scaleY−1\| |
|---|---|---|---|
| Super  | 0.2979 | 16.0 | 4.8e-5 |
| Mega   | 0.4034 | 21.6 | 1.25e-4 |
| Omg    | 0.5100 | 27.2 | 1.51e-4 |
| Legend | 0.6334 | 33.6 | 1.16e-4 |

非均勻峰 + shear 峰皆嚴格遞增;體積守恆偏差每檔位 ≤1.5e-4 << TOL_VOL 0.02(放大後守恆存活)。

## 自驗閘 `validate_squash_tier.py`（先驗庫 → 真實 build_spine robot 骨架 → build_animations(tier_gains=…)）

**5 AC 全 PASS**:

- **P1 present + backward-compat**:每檔位 `squash__{tier}` 產出、finite、有 bone、≥1 bone **同時**帶
  shear+scale、名經 `beat_category` 仍路由回 squash;**base squash 逐位元不變**(帶/不帶 tier_gains 相同)。
- **P2 crux — monotone + 守恆**:(a) 非均勻峰 Super<Mega<Omg<Legend 嚴格遞增且 Super==base;
  (b) shear 峰亦嚴格遞增;(c) **crux**:**每個**檔位的**每個** scale 極值幀 `|scaleX·scaleY−1| ≤ TOL_VOL`
  (體積守恆在放大後存活 —— 舊樓地板 amplify 辦不到,見 P5b)。
- **P3 signatures preserved / tier**:每檔位 squash bone 仍 (a) shear 阻尼振盪(首尾 0、變號≥3、極值遞減);
  (b) SQ3 體積守恆耦合(volume_ok、aniso_ok、squash 幅度嚴格遞減)。兩通道簽章逐檔位保形。
- **P4 coupling isolated**:全 storyboard(含所有檔位變體)只有 squash 及其 `__tier` 變體同時帶 shear+非均勻
  scale(耦合)→ squash 獨佔耦合,對既有節拍零外洩。
- **P5 neg-control**:(a) **平增益守衛**:增益全 1.0 → P2 非均勻峰遞增 FALSE 且各檔位 squash 逐位元==base;
  (b) **crux 必要性單元測**:對真實極值 (1.16, 0.8621)(積≈1)以 g=2.1 —— **舊** `_amp_scale` 逐軸 →
  積 **1.152**(守恆**破壞**),**新** `_amp_scale_coupled` → 積 **1.000076**(守恆保持)→ 證耦合 amplify
  **非多餘、且閘能鑑別**;(c) **耦合性質單元測**:`_amp_scale_coupled(1,g)==1`(identity 介面)、
  g==1 → v(向後相容)、對合成 (1.2, 1/1.2) 任意 g 積守恆。

## 關鍵發現

- **「檔位機制就緒 ≠ 每個通道接上」的深一層**:前幾個候選(E/H/I/J/G-4''/G-4''')接新通道時,放大方式
  沿用既有(scale 樓地板 / shear·rotate 對 0 對稱)。但**體積守恆的耦合非均勻 scale 需要換一種放大數學**
  —— log 空間同指數放大,才能同時守積、放大非均勻、保介面、保阻尼。放大方式必須匹配通道的**不變量**。
- **log 空間是體積守恆變換的自然放大空間**:`ln(scaleX)+ln(scaleY)=0`(守恆)的線性放大 = 兩軸同乘 g =
  `v**g`;守恆是 log 空間的一條過原點直線,同指數放大 = 沿該直線縮放 → 天然不離開守恆流形。
- **負對照直接量「必要性」**:P5(b) 把「舊法會壞、新法守住」寫成可跑的單元測 —— 不只驗新法對,還驗
  「不換數學就會錯」,這是比一般負對照更強的必要性證明(同 SQ6 兩條件獨立守衛的精神再進一步)。

## Honest boundary(仍在,後續候選)

- **非均勻峰階梯沿用 (J) 幅度增益**(g=[1,1.35,1.70,2.10],PROPOSAL;結構簽章客觀、手感留使用者 A 類)。
- **squash count-aware 未接**:擠壓**段數** nosc 隨檔位(`gen_squash(nosc=)` 參數已就緒,比照 J-2/G-4''')
  為後續 —— 需 `TIER_SQUASH_CYCLES` + build_animations 路由(結構軸,與本次幅度軸正交)。
- shearY≡0(斜拉只在 X);單一真值資產(robot)。與 anim-forge 同 HOLD(防固化)。

## 檔案 / 指令

- amplify:`tools/analyzer/tier_variants.py`(`_amp_scale_coupled`、`amplify_bone_tl(coupled=)`、
  `amplify_anim(coupled=)`、新增 `VOLUME_CONSERVE_CATS={"squash"}`、squash 併入 `MAIN_SHOW_CATS`)。
- 路由:`gen_animations.py`(`build_animations` 依 `cat in VOLUME_CONSERVE_CATS` 傳 `coupled`)。
- 閘:`tools/analyzer/validate_squash_tier.py`(`python3 validate_squash_tier.py [--json]`)。
- 回歸修正:`validate_tier_combo_count.py` K5c 改 channel-aware,略過 `VOLUME_CONSERVE_CATS`
  (squash 的 scaleX 是阻尼多極值體積守恆包絡、非 combo impact 連擊,對它施 `impact_peaks` 是類別誤用;
  squash 不在 `_count_maps` → combo 的 nhits 本就不作用於它)。
- 端到端:`build_spine.py --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}`。
- 回歸:18 閘全綠 + round-trip `validate_build` 對 `--tier-variants --shear-pivot` build overall_pass(premult MAE 0.031)。
- 圖:`knowledge/figures/s1_squash_tier.png`。
- 能力:cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
