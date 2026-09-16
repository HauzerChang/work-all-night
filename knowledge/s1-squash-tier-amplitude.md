# S1 (G-4''''') squash 斜拉擠壓強度隨檔位遞增(體積守恆耦合放大)

- **結論**:補上 (G-4'''') 留的 honest boundary —— 「squash 未接 tier 幅度差異化」。把 `squash`(斜拉果凍
  擠壓,shear + 耦合非均勻 scale)併入 `MAIN_SHOW_CATS`,並新增 **`_amp_scale_coupled`(體積守恆耦合放大)**,
  使 squash 的斜拉擠壓強度隨檔位嚴格遞增(shear 峰 16°→33.6°、scale 非均勻 0.30→0.59),
  而 **體積守恆(scaleX·scaleY≡1)在每個檔位保持**。5 AC 全 PASS + 17 閘全綠 + round-trip overall_pass。
- **依據**:`tools/analyzer/validate_squash_tier.py`(先驗庫→**真實 build_spine robot 骨架**→
  `build_animations(tier_gains=…)`);cap `squash_tier_amplitude` L2(`spine-anim-forge`,仍 HOLD)。
- **信心**:高(客觀結構簽章 + 耦合必要性負對照;手感/檔位階梯屬 PROPOSAL,留使用者 A 類)。
- **相關階段**:專案第 2 階段 S1(反推分析器 → 檔位差異化產線),接 (J)/(G-4'')/(G-4''')/(G-4'''')。

## 問題:為何 squash 過去被排除於檔位差異化

(G-4'''') 讓 `gen_squash` 成為**第一個同時產 shear + 非均勻 scale** 的生成器,其 scale 通道是
**體積守恆**的:`scaleX=1+q_i`(拉長)、`scaleY=1/(1+q_i)`(壓扁)⇒ `scaleX·scaleY≡1`。但 (J) 的
檔位幅度增益 `_amp_scale` 是**只放大 identity 上方 overshoot**(`v'=1+g(v−1)` 僅當 v≥1;下方
squash/collapse 樓地板不動)。這條規則對 hit/combo/reveal 是**誠實**的(蓄力深度/藏匿是結構語意、
非大獎強度),但套到 squash 會**放大 scaleX>1 卻凍結 scaleY<1** →
`scaleX'·scaleY' = (1+g·q)·1/(1+q) ≠ 1`(g>1 時破壞體積守恆)。故 (G-4'''') 把 squash **刻意排除**於
`MAIN_SHOW_CATS`,並在 note 標記「squash 的檔位差異化需**耦合 amplify**」為 honest boundary。

## 解法:`_amp_scale_coupled`(拉長軸線性放大、壓縮軸取倒數)

```
_amp_scale_coupled(sx, sy, g):
  拉長軸(≥1 的那軸)  s = 1 + g*(v − 1)      # 同 _amp_scale,與其他主秀 scale beat 逐位元一致
  壓縮軸               = 1 / s                 # 取倒數 → scaleX'·scaleY' ≡ 1 恆保持
```

- **體積守恆**:輸出積恆 1(至 4 位小數捨入),對任意 g 成立 —— 把放大鎖在「體積守恆流形」上。
- **identity 保持**:(1,1)→(拉長軸 v=1 → s=1 → 壓縮軸=1)→(1,1)(可插 Loop 間,檔位無關)。
- **向後相容 byte-identical**:g=1 → 拉長軸 s=v、壓縮軸 1/v,與 gen 端 `1/(1+q)` 逐位元相同 → Super==base。
- **對稱**:以 `sx>=sy` 判拉長軸,故反向 squash(Y 拉長)亦正確處理。
- shear 通道續走 (G-4'') 的 `v'=g*v`(對 0 對稱)→ shear 峰隨檔位遞增、阻尼振盪簽章保形。

路由:`tier_variants.COUPLED_SCALE_CATS={squash}`;`build_animations` 對 `cat ∈ COUPLED_SCALE_CATS` 的
tier 變體以 `amplify_anim(..., coupled=True)` 放大,其餘(hit/reveal/combo/charge/cascade/wobble)不變。

## AC(validate_squash_tier.py,5 條全 PASS)

- **ST1 present + backward-compat**:每檔位 `squash__{tier}` finite/有 bone/≥1 bone 同時帶 shear+scale;
  名經 `beat_category` 仍路由回 squash;**base(含 In/Loop/Out + base squash)帶/不帶 tier_gains 逐位元不變**。
- **ST2 crux — dual-peak monotone**:scale 非均勻峰 `[0.30,0.39,0.49,0.59]` **與** shear 峰 `[16,21.6,27.2,33.6]`
  皆 Super<Mega<Omg<Legend 嚴格遞增,且 Super==base(向後相容)。
- **ST3 crux — volume + damped per tier**:**每個檔位**的每個 scale 極值幀 `|scaleX·scaleY−1|≤TOL_VOL`
  (實測 worst ≤1e-4,4 位捨入)+ squash 幅度隨極值遞減 + shear 阻尼振盪(首尾 0、繞 0 變號≥3、極值遞減)。
- **ST4 identity interface per tier**:每檔位 shear 首尾 0、scale 首尾 (1,1)、sample(0)/sample(dur) identity。
- **ST5 neg-control**:(a) 平增益全 1.0 → ST2 遞增 FALSE 且各檔位逐位元 == base;
  **(b) crux 耦合必要性**:同一 base squash bone 套**天真非耦合** `amplify_bone_tl(coupled=False)` @Legend →
  體積守恆 FALSE(偏離實測 0.15,>1500×);對照 `coupled=True` 積≈1(≤1e-4)→ **證耦合放大是必要、非裝飾**;
  (c) 耦合隔離:只有 squash 及其 `__tier` 變體同時帶 shear + 非均勻 scale(零外洩)。

端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}`
(pivot 補償後體積守恆仍 <0.02),`validate_build` round-trip overall_pass(premult MAE 0.031)。

## 關鍵發現

- **體積守恆變換的檔位放大是 log/倒數耦合,不是逐軸獨立放大**。天真逐軸放大(對每軸各自套 `_amp_scale`)
  會把守恆變換推離守恆流形;正確做法是把放大鎖在流形上(拉長軸放大、壓縮軸取倒數保積 1)。這是
  「檔位機制就緒 ≠ 每個新通道接上」的又一實例(同 E/H/I/J/G-4'/G-4''),惟本次通道的**約束**
  (體積守恆)使天真放大**直接違反物理**,故必須改放大規則本身,而非只新增一個通道。
- **副修:`validate_tier_combo_count.py` K5(c) 由 impact-峰數 proxy 改為 byte-identity**。原 proxy
  (「非-combo 主秀 beat 的 impact 峰數在各檔位不變」)對 squash 假陽性:squash 的 scaleX overshoot 隨檔位
  放大會越過 impact-peak 偵測門檻 → 峰數 0→1 被誤判為 count 外洩。但那是**幅度**差異化(ST2/K2 正確覆蓋)
  非 count 差異化。改比「非-combo 變體在『幅度+連擊數』build 與『幅度-only』build 逐位元相同」——精確隔離
  count vs amplitude 兩軸,且更嚴格。

## honest boundary(仍在)/ 下一步

- shear 峰階梯沿用 (J) 增益 `{1.0,1.35,1.70,2.10}`(PROPOSAL 手感留使用者 A 類)。
- shearY≡0(斜拉只在 X);squash 段數 nosc **count-aware 未接**(已備參數;比照 J-2/G-4''' 可讓擠壓段數隨檔位遞增)。
- 單一真值資產(robot);與 `spine-anim-forge` 同 HOLD(運動基元先驗、防半成品固化)。
- 圖 `figures/s1_squash_tier.png`。
