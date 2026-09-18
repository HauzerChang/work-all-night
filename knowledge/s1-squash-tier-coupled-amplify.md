# S1 (G-4''''') squash 接檔位差異化 —— 體積守恆**耦合放大**

> candidate G-4'''''(2026-09-18)。續 G-4''''(`gen_squash` 產耦合 shear + 非均勻 scale)。
> 補上一路留到現在的 honest boundary:**「squash 未接 tier —— 需耦合 amplify」**。

## 一句話

squash 的 scale 是**體積守恆對**(scaleX=1+q、scaleY=1/(1+q),scaleX·scaleY==1)。要讓斜拉擠壓
強度隨檔位遞增,不能沿用 (J) 兩軸各自獨立放大的 `_amp_scale`(那會破壞守恆);本次加**耦合放大**
`_amp_scale_pair`,放大拉長量 q→g·q、另一軸取倒數,使**放大後面積仍守恆**,squash 得以併入
`MAIN_SHOW_CATS`、`build_spine --tier-variants` 直出 `squash__{tier}`。

## 為什麼是這一步(補的 honest boundary)

- **(J)** `tier_variant_amplitude`:主秀 beat 依檔位幅度增益 g 放大。scale 通道用 `_amp_scale(v,g)=
  1+g(v−1) if v≥1 else v` —— **只放大 identity 上方 overshoot、下方樓地板不動**。
- 這對等比 scale(hit/reveal/combo/charge/cascade,scaleX==scaleY)完全正確;對 (G-4'') 的 wobble
  (純 shear,對 0 對稱 v'=g·v)也正確。
- 但對 **(G-4'''')** 的 squash 就**壞掉**:squash 一幀是 (scaleX=1+q>1, scaleY=1/(1+q)<1)。
  `_amp_scale` 會把 scaleX 放大(1+g·q)、卻讓 scaleY(<1 樓地板)**不動** → 積 = (1+g·q)·(1/(1+q)) ≠ 1
  → **面積不再守恆**,不再是「擠壓」而是「單軸拉長」。這正是 G-4'''' 把 squash **排除在 MAIN_SHOW_CATS
  外**的原因(當時記為 honest boundary)。

## 解法:體積守恆**耦合放大** `tier_variants._amp_scale_pair(x, y, g)`

判準用**雙條件**辨識 squash 對(與等比 pulse、一般 overshoot 乾淨分離):

```
若 (x−1)·(y−1) < 0        # 一軸拉長、一軸壓縮(異側)
   且 |x·y − 1| ≤ 0.02:   # 且積≈1(體積守恆對)
     s  = max(x, y)          # 拉長軸(>1)
     ns = 1 + g·(s−1)        # 放大拉長量 q→g·q(同 _amp_scale 對 overshoot)
     no = 1 / ns             # 壓縮軸取倒數 → ns·no == 1(面積恆守恆)
     回 (ns, no) 或 (no, ns) 依原拉長軸
否則:                        # 等比對 x==y、或積≠1 的一般 scale
     回 _amp_scale(x,g), _amp_scale(y,g)   # 兩軸各自獨立(原行為,逐位元向後相容)
```

- **關鍵不變量**:`ns·no ≡ 1`(理論精確;4 位小數殘差 <1e-3)。squash 幅度隨檔位遞增,而
  **非均勻性 |scaleX−scaleY| 亦隨之遞增**、**體積始終守恆**。
- **向後相容**:等比對 (x==y) → `(x−1)(y−1)=(x−1)²≥0` 不觸發耦合;identity 端點 (1,1) 亦不觸發
  → 既有主秀 beat 的 tier 變體**逐位元不變**;g=1.0(Super)對 squash 對亦 identity → `squash__Super`
  逐位元 == base squash。
- squash 併入 `MAIN_SHOW_CATS`;`amplify_bone_tl` 的 scale 迴圈改成「兩軸一起 `_amp_scale_pair`」。

## 自驗閘 `validate_squash_tier.py`(先驗庫 → 真實 build_spine robot 骨架 → build_animations(tier_gains))

| AC | 內容 | 結果 |
|---|---|---|
| **ST1** present + backward-compat | 每檔位產 `squash__tier`(finite/有 bone/帶 shear+scale 雙通道/路由回 squash);base 逐位元不變;**Super 變體逐位元==base** | PASS |
| **ST2 crux** coupled monotone + volume | 峰 \|shearX\| **[16, 21.6, 27.2, 33.6]** 與峰非均勻 **[0.298, 0.394, 0.486, 0.588]** 皆 Super<Mega<Omg<Legend 嚴格遞增且 Super==base;**每檔位每極值幀 \|scaleX·scaleY−1\|≤0.02(放大後仍守恆,worst 0.0001)** | PASS |
| **ST3** damped signature per tier | 每檔位 shear 阻尼振盪(繞 0 變號≥3 + 相繼極值遞減)+ squash 幅度 \|scaleX−1\| 嚴格遞減保形 | PASS |
| **ST4** coupling isolated | 全 tier build 中「同時帶 shear + 非均勻 scale」僅 squash 及其變體(wobble 有 shear 無 aniso、其餘有等比 scale 無 shear) | PASS |
| **ST5** neg-control | (a) 平增益全 1.0 → 遞增 FALSE 且各檔位==base;(b) **耦合放大 crux 單元守衛** | PASS |

### ST5(b) 耦合放大 crux 守衛(證「為什麼需要耦合」)

對合成 squash 對 `(1.16, 0.8621)`(積≈1)套 g=2:

- **耦合** `_amp_scale_pair`:scaleX→**1.32**(拉長量 q=0.16→0.32)、scaleY→1/1.32,積 **== 1**(vol_err 0.0)。
- **舊式獨立** `_amp_scale`:scaleX→1.32、scaleY(<1)**不動**=0.8621,積 = 1.32×0.8621 = **1.138 ≠ 1**(vol_err 0.138)。
- 等比對 `(1.2, 1.2)`(非 squash 對)→ 耦合放大 **== 獨立放大**(向後相容)。

→ 直接證明:**沿用 (J) 的獨立放大會壞守恆(0.138),耦合放大才對(0.0)**。這是本能力存在的理由,也是閘的鑑別力來源。

圖:`knowledge/figures/s1_squash_tier_coupling.png`(左:shear/非均勻峰隨檔位遞增;中:各檔位每極值積≡1;右:耦合 vs 獨立放大隨 g 的積發散)。

## 端到端 + 回歸

- `build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}`(pivot 補償後
  仍一般仿射不動點),`validate_build` round-trip **overall_pass**(premult MAE 0.031、setup 不變)。
- **18 閘全綠**:squash_tier(新)+ squash_gen/wobble_tier/wobble_count/tier_variants/tier_combo_count/
  shear_gen/shear_pivot/scale_pivot/pivot_rotation/cascade/priors/priors_beats/priors_combo_charge/
  priors_cascade/more_beats/beat_templates/deform_gen。
- **`validate_tier_combo_count.py` K5(c) 修正**:原「非-combo 主秀 beat 峰數跨檔位不變」對 squash 假陽性
  —— squash 的 scaleX 擠壓幅度隨檔位**幅度增益**遞增,threshold-based `impact_peaks` 的跨門檻數會隨之變動,
  那是**幅度軸 (J)** 不是 combo 的 **nhits count 軸 (J-2)**。改為對 squash 測「峰數對 `tier_combo_hits`
  無感」(holding tier_gains 固定、只切連擊映射)—— 正確隔離 count 機制而非混入幅度變因。

## 關鍵發現

1. **通道語意決定放大方式**:對 0 對稱的通道(rotate/translate/shear)用 `v'=g·v`;identity 上方
   overshoot 的等比 scale 用 `1+g(v−1)`;**體積守恆對必須耦合放大**(一軸放大、另一軸取倒數)。放大規則
   不是「一體適用」,而是**依通道的結構不變量**(對稱點 / 守恆量)量身定。
2. **偵測用結構不變量、不用類別名**:`_amp_scale_pair` 以「異側 + 積≈1」辨識 squash 對(不看 beat 名)
   → 對既有等比主秀天然 no-op、對未來任何體積守恆節拍自動生效,且不需在 amplify 層知道 beat 類別。
3. **軸族推廣再現**:檔位差異化已覆蓋 幅度(J,等比 scale/rotate/translate)→ shear 幅度(G-4'')→
   段數(G-4''')→ **體積守恆耦合 scale(本次)**;每次都是「檔位機制就緒 ≠ 每個新通道接上」的同一課題,
   每個新通道要各自證明「強度變、結構簽章保形」。

## honest boundary(仍在)

- 增益階梯數值 [1.0, 1.35, 1.70, 2.10] 仍是 (J) 的 PROPOSAL(結構簽章客觀、手感留使用者 A 類)。
- **squash count-aware**(擠壓段數 nosc 隨檔位遞增,`gen_squash(nosc=)` 參數已備)為後續(比照 G-4''' 對 wobble)。
- shearY≡0(雙軸 shear 為後續 G-4'''''')。
- 單一真值資產(robot_parts);與 `spine-anim-forge` 同 **HOLD**(運動基元先驗、防固化)。
