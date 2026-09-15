# S1 — squash 接檔位幅度差異化,體積守恆耦合放大(candidate G-4''''',`squash_tier_coupled_amplify` L2)

> 2026-09-15。續 (G-4''''):(G-4'''') 讓 `gen_squash`(斜拉果凍擠壓)成為**第一個同時產 shear + 非均勻
> scale** 的生成器(scaleX=1+q 拉長、scaleY=1/(1+q) 壓扁,scaleX·scaleY≡1 面積守恆),但**未接檔位差異化**。
> 本次補上:squash 的斜擠強度隨檔位(Super→Legend)遞增,而**體積恆守恆**。

## 缺口(honest boundary 的接續)

- (G-4'''') 誠實標記:「squash 未接 tier —— `_amp_scale` 只放大 identity **上方** overshoot、把 scaleY<1
  當樓地板不動 → 對 squash 破壞體積守恆(scaleX 放大、scaleY 不動 → scaleX·scaleY≠1),需**耦合 amplify**」。
- 所以 G-4'''' 刻意把 `squash` **排除**在 `MAIN_SHOW_CATS` 外(不然 (J) 的檔位機制會用錯的放大規則)。
- 本次(G-4''''')正好照那條邊界接上。

## 關鍵:squash 的檔位軸需**耦合放大**(非均勻 scale 是體積守恆對)

(J) 的 `_amp_scale` 對 scale **各軸獨立**、只放大 identity 上方:`v'=1+g(v−1) 僅當 v≥1`,下方樓地板不動。
這對 hit/combo/reveal 的 overshoot 是對的(collapse 樓地板本就該檔位無關)。但 squash 的兩軸是**一對**
(scaleX=1+q、scaleY=1/(1+q),共用同一「squash 量 q」使積≡1)。獨立放大會:

- scaleX=1+q → 放大到 1+g·q(正確,拉更長);
- scaleY=1/(1+q)<1 → 被當**樓地板不動** → 積 = (1+g·q)·(1/(1+q)) ≠ 1 → **體積被破壞**(squash&stretch 變成單邊拉長)。

**解法**:對兩軸共用的 q 一起放大。從各軸取回同一個 q，再以 g 放大：

```
_amp_scale_coupled(sx, sy, g):
    scaleX' = 1 + g·(sx − 1)            # 由 scaleX 取回 q = sx−1
    scaleY' = 1 / (1 + g·(1/sy − 1))    # 由 scaleY 取回 q:sy=1/(1+q) → q = 1/sy−1
```

- **體積恆守恆**:兩軸取回的 q 同源(基態下 sx−1 ≈ 1/sy−1)⇒ scaleX'·scaleY' ≈ (1+gq)/(1+gq) = 1
  (實測:Super 4.8e-5 → Legend 1.3e-4,遠 < TOL_VOL 0.02)。
- **非均勻隨檔位遞增**:|scaleX'−scaleY'| 峰 0.30→0.39→0.49→0.59(檔位簽章)。
- **端點 identity 保持**:sx=sy=1 → 兩式皆回 1(對所有 g)。
- **g=1 逐位元不變**:scaleX'=sx、scaleY'=1/(1/sy)=sy(idempotent；兩軸皆已 4 位小數 → round 還原)。

這是繼 (J) 對稱 `_amp_scale`(scale 對 identity 單邊)、rotate/translate/shear 對 0 對稱之後的
**第三種通道放大規則**。shear 通道仍走 v'=g·v（與 squash 量同 g 放大 → **shear↔squash 耦合保持**）。

## 做了什麼(全 additive)

1. **`tier_variants.py`**:
   - `MAIN_SHOW_CATS` 加入 `squash`(現可產 `squash__{tier}` 變體)。
   - 新增 `COUPLED_SCALE_CATS = {"squash"}`(哪些類別的 scale 走耦合放大)。
   - 新增 `_amp_scale_coupled(sx, sy, g)`(上式)。
   - `amplify_bone_tl(b, g, coupled_scale=False)` / `amplify_anim(anim, g, coupled_scale=False)`:
     `coupled_scale=True` 時 scale 通道走耦合放大;`False`(預設)→ 原各軸獨立 `_amp_scale`(零回歸)。
2. **`gen_animations.build_animations`**:對主秀 beat 產檔位變體時,`coupled = cat in COUPLED_SCALE_CATS`
   傳給 `amplify_anim` —— squash 走耦合、其餘走標準。
3. **`validate_squash_tier.py`**(新,5 AC)。
4. **`validate_tier_combo_count.py` K5(c) 修正**(見下「回歸踩雷」)。
5. `check_readiness.py` 新增 cap `squash_tier_coupled_amplify` L2 併入 `spine-anim-forge`;重生成 `skills/READINESS.md`。
6. knowledge 本檔 + 索引;圖 `knowledge/figures/s1_squash_tier.png`。

## 自我驗收(validate_squash_tier.py 5 AC 全 PASS)

- **P1 present + backward-compat**:每檔位 `squash__{tier}` finite/有 bone/≥1 bone dual channel(shear+scale)、
  名經 `beat_category` 仍路由回 squash;**Super==base**(g=1.0 逐位元不變)、base 全 beat 不變;
  `tier_gains=None` → **不產** squash 變體。
- **P2 crux 耦合三通道同時遞增**:shear 峰 [16,21.6,27.2,33.6]°、拉長量 max(scaleX−1) [0.16,0.216,0.272,0.336]、
  非均勻峰 |scaleX−scaleY| [0.30,0.39,0.49,0.59],Super<Mega<Omg<Legend **皆嚴格遞增**。
- **P3 crux 體積守恆保住**:**每個檔位**每個 squash bone 每個內部極值 |scaleX·scaleY−1| ≤ 2e-4(TOL_VOL 0.02)
  —— 正是天真 `_amp_scale` 會破壞、耦合放大才保住的點。
- **P4 簽章+介面保形**:每檔位 shear 阻尼振盪(首尾 0、繞 0 變號≥3、相繼極值遞減)、squash 幅度 |scaleX−1|
  隨極值嚴格遞減(阻尼耦合)、sample(0)/sample(dur) identity。
- **P5 負對照(閘可信)**:
  - (a) **crux 天真非耦合放大守衛**:對 base squash 施 `coupled_scale=False` 的放大(Legend g=2.1)→
    體積誤差 **0.152 ≫ 0.02(破壞)**,而耦合放大同 g 下 **1.3e-4 ≤ 0.02(守恆)** → 證耦合放大確實在做事、閘非恆真。
  - (b) 平增益守衛:增益全 1.0 → P2 三通道皆非遞增 且 `squash__tier`==base(逐位元)。
  - (c) 耦合隔離:`COUPLED_SCALE_CATS=={squash}`;squash 變體走耦合(≠非耦合放大結果);非-squash 主秀 beat
    的變體 == 標準 (J) 放大(`coupled_scale=False`)—— 耦合不外洩。

**端到端** `build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}`
(dual channel + pivot 補償),`validate_build` round-trip overall_pass。

## 回歸踩雷:squash 併入 MAIN_SHOW_CATS 讓 combo-count 隔離閘假陰性

`validate_tier_combo_count.py` K5(c)「連擊數只作用 combo:非-combo 主秀 beat 各檔位 impact 峰數恆定」原用
`_min_peaks`(scaleX 局部極大 ≥ IMPACT_PROM 的個數)量各檔位峰數是否恆定。squash 的 scaleX 是**單一** stretch 峰
(阻尼單調下降,只有一個局部極大),但**耦合放大讓那個峰隨檔位升高跨越 IMPACT_PROM(1.10)門檻** ——
head 件(Q=0.10)在 Super scaleX 峰=1.10 恰在門檻附近,Mega 起 >1.10 → `_min_peaks` 給 [0,1,1,1](非恆定)→
誤判「連擊數外洩」。**這是幅度差異化(squash 合法)被峰數計數混淆**,非 combo 連擊數真的洩漏。

**修正**:K5(c) 改測**精確不變量** —— 傳入 `tier_combo_hits` 不得改動任何**非-combo** 主秀 beat 的變體:
判準用「`full`(帶 combo_hits)vs `amp_only`(僅幅度增益、同 gains)**逐位元相同**」。兩側 gains 相同,差別只在有無
combo_hits → **不被幅度混淆**,且是「連擊數隔離於 combo」的精確陳述(combo_hits 只重路由 combo)。閘**未被弱化**
(反而更精確)。

## 關鍵發現

- **每種 scale 語意需要自己的檔位放大規則**:overshoot(單邊,樓地板保留)vs 體積守恆耦合(雙軸同源 q 放大)。
  通道放大到現在有三類:scale-overshoot 單邊(J)、rotate/translate/shear 對 0 對稱(J/G-4'')、**scale 體積守恆耦合(本次)**。
- **結構約束在放大時必須被尊重**:squash 的「scaleX·scaleY≡1」是這個運動基元的**定義性結構**,天真放大會破壞它。
  同型於前面幾個「真簽章需兩獨立條件並立」的發現 —— 這裡是「放大必須保住定義性不變量」。
- **又一「機制就緒 ≠ 每個新通道/語意接上」實例**(同 E/H/I/J/G-4'~G-4''''):檔位機制(J)早就在,squash 的
  scale 語意特殊,直到補上耦合放大才真正接上。

## honest boundary(仍在)/ 下一步

- **squash count-aware nosc 未接**:擠壓段數隨檔位遞增(比照 J-2 combo / G-4''' wobble;`gen_squash` 已備 `nosc` 參數,`TIER_*` 尚未宣告)。
- **shearY≡0**(斜拉只在 X);幅度階梯沿用 (J) 增益(PROPOSAL,手感留使用者 A 類)。
- 單一真值資產(robot);與 `spine-anim-forge` 同 HOLD(運動基元為先驗、防固化)。
- 見圖 `figures/s1_squash_tier.png`(三面板:耦合放大 scaleX/scaleY 隨檔位、體積積守恆 vs 天真破壞、三通道同步遞增)。
