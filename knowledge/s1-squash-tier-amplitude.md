# S1 — squash 接檔位幅度差異化(耦合體積守恆 amplify)(candidate G-4''''',`squash_tier_amplitude` L2)

> 2026-09-16。把 (G-4'''') 新生成的 **squash 節拍(shear + 耦合體積守恆非均勻 scale)** 接進 (J)/(G-4'')
> 的**檔位幅度差異化**機制:squash 的擠壓/斜拉強度隨檔位(Super→Legend)嚴格遞增,而**每個檔位仍體積
> 守恆**(scaleX·scaleY==1)。又一「檔位機制就緒 ≠ 每個新通道接上」實例,惟此通道需**耦合**放大。

## 缺口(G-4'''' 留下的 honest boundary)

- **(J)/(G-4'')/(G-4''')** 讓主秀 beat 的 **scale / rotate / translate / shear** 幅度隨檔位遞增,
  `tier_variants.amplify_bone_tl` 對 scale 用 `_amp_scale`(**只放大 identity 上方 overshoot、保留下方樓地板**)。
- **(G-4'''')** 讓 `gen_squash` 成為第一個產出**耦合 shear + 體積守恆非均勻 scale** 的生成器,但當時
  `squash ∉ MAIN_SHOW_CATS` —— **squash 完全不隨檔位放大**。且 G-4'''' 誠實標記:squash 的 scale 是
  **體積守恆**(scaleX=1+q、scaleY=1/(1+q)、scaleX·scaleY==1),若用 `_amp_scale` per-channel 放大會
  **破壞守恆**(scaleX 過門檻放大、scaleY<1 樓地板保留 → 積 (1+gq)/(1+q)≠1),故「需耦合 amplify」。
- 本次(G-4''''')正好照那條邊界接上:**squash 走耦合 amplify**。

## 關鍵洞見:體積守恆節拍的檔位放大**必須耦合**

per-channel amplify 是錯的。squash 的兩個 scale 通道間有**約束**(scaleX·scaleY≡1);放大時增益要作用在
**squash 參數** q(=拉長量),而非各通道值:

```
naive(錯):scaleX' = 1 + g·(scaleX−1),  scaleY' = scaleY(<1 樓地板不動)
           → scaleX'·scaleY' = (1+gq)/(1+q) ≠ 1   ✗ 破壞面積守恆
coupled(對):q' = g·q,  scaleX' = 1+q',  scaleY' = 1/(1+q')
           → scaleX'·scaleY' ≡ 1   ✓ 守恆保持,且非均勻 |scaleX'−scaleY'| 隨 g 增大
```

實測真實幀 `(scaleX,scaleY)=(1.16, 0.8621)`、g=2:naive 積 **1.138**(破壞守恆 +14%)vs 耦合積 **1.00003**
(守恆),且耦合更非均勻(aniso 0.562 > naive 0.458)。這正是 V5(b) 的 crux 負對照(證機制**有作用且必要**)。

## 做了什麼(全 additive)

1. **`tier_variants.MAIN_SHOW_CATS`** 加入 `"squash"`。
2. **`tier_variants.COUPLED_SCALE_CATS = {"squash"}`**(新)—— scale 通道為體積守恆非均勻、需耦合放大的類別。
3. **`tier_variants._amp_squash_scale(sx, sy, g)`**(新):`q'=g·(scaleX−1)` → `(1+q', 1/(1+q'))`;
   `g=1.0` → 逐位元不變(squash 幀已 4 位小數)。
4. **`amplify_bone_tl(b, g, coupled_scale=False)`** / **`amplify_anim(anim, g, coupled_scale=False)`**:
   `coupled_scale=True` → scale 走 `_amp_squash_scale`;shear 仍 `v'=g·v`(與 scale 同源 → 兩通道耦合放大)。
5. **`gen_animations.build_animations`**:squash ∈ `COUPLED_SCALE_CATS` → 產 `squash__{tier}` 時傳 `coupled_scale=True`。
6. **`validate_squash_tier.py`**(新,5 AC)。
7. **`validate_tier_combo_count.py`**(J-2 閘)K5(c) 隔離守衛改用**幅度不變量** `_min_scale_maxima`
   (見下「回歸修正」)。
8. **`check_readiness`** 新增 cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(仍 HOLD)。
9. 圖 `knowledge/figures/s1_squash_tier.png`(a 峰遞增、b 每檔位守恆、c naive vs coupled 積、d 擠壓橢圓)。

## 驗收(`validate_squash_tier.py` OVERALL PASS,先驗庫→真實 build_spine robot 骨架→build_animations)

- **V1 present + backward-compat**:squash base ≥1 bone dual-channel(shear+scale);每檔位 `squash__{tier}`
  產出、finite、dual-channel、名仍路由回 squash;**base 帶/不帶 tier_gains 逐位元不變**;Super(g=1)==base。
- **V2 crux — 耦合幅度遞增**:拉長峰 |scaleX−1| **[0.16, 0.216, 0.272, 0.336]**、shear 峰 **[16, 21.6, 27.2, 33.6]°**、
  非均勻峰 |scaleX−scaleY| **[0.298, 0.394, 0.486, 0.588]** 皆 Super<Mega<Omg<Legend 嚴格遞增,且 Super==base。
- **V3 crux — 守恆放大後不破**:**每檔位每極值幀** (a)scaleX·scaleY≈1(實測 |積−1|<5e-5);(b)非均勻;
  (c)|scaleX−1| 隨極值嚴格遞減(阻尼)。且 shear 阻尼振盪簽章(首尾 0 + 變號≥3 + 極值遞減)每檔位保形。
- **V4 identity 介面 per tier**:每檔位變體 shear 首尾 0 + scale 首尾 (1,1)。
- **V5 負對照**:(a)平增益全 1.0 → V2 遞增 FALSE 且各檔位==base;(b)**耦合 vs naive 守衛(crux)**:
  真實幀 [1.16,0.8621] naive 積 1.138(破壞守恆)vs 耦合積 1.00003(守恆)且更非均勻 → 證耦合有作用且必要;
  (c)耦合隔離:含所有檔位變體,只有 squash 及其變體「同時帶 shear 且非均勻 scale」。
- **端到端**:`build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}`,
  `validate_build` round-trip overall_pass(AC1–AC4 全 PASS)。18 閘全綠回歸。

## 回歸修正:tier_combo_count K5(c) 改用幅度不變量段數代理

把 squash 併入 `MAIN_SHOW_CATS` 後,J-2 閘 K5(c)(「count 只作用 combo:非-combo 主秀 beat 段數各檔位不變」)
對 squash 假陽性:原用 `_min_peaks`(**impact 門檻 1.10** 計數),但 squash 體積守恆擠壓 scaleX 幅度小
(Super 峰 1.10–1.16,**貼近門檻**),耦合 amplify 把各件 scaleX 推過/未過 1.10 → 過門檻**計數**隨檔位變
(`[0,1,1,1]`)—— 這是**幅度貼門檻的計數擾動**,非真正加段。改用 **`_min_scale_maxima`**(scaleX 結構局部
極大**數**,不設 impact 門檻,只要 >identity):幅度增益 g 只等比放大 overshoot、不改拓樸 → 極值數與檔位
無關,唯真正加段(combo nhits)才改變 → 守衛**更貼題且可信**(直接量段數結構,非幅度代理)。

## honest boundary(仍在)

- squash 尚未接 **count-aware**:擠壓/振盪**段數** nosc 隨檔位遞增(比照 (G-4''') 對 wobble、(J-2) 對 combo,
  須在 `gen_squash` 生成當下決定,事後 amplify 加不出段數)。`gen_squash(nosc=)` 參數已備、未接。
- 仍只產 **shearX**(shearY≡0)。
- 拉長峰階梯沿用 (J) 幅度增益 `{Super:1.0,Mega:1.35,Omg:1.70,Legend:2.10}`(PROPOSAL,結構簽章客觀、手感留使用者 A 類)。
- 單一真值資產(robot_parts)。與 `spine-anim-forge` 區塊同 **HOLD**(運動基元為先驗手感、防固化)。

## 續(擇一,皆純自主)

- **(G-4'''''')** squash 接 count-aware:擠壓段數隨檔位遞增(nosc 已備參數,比照 G-4''')。
- 產 **shearY**(雙軸 shear)/ shear+scale+rotate 三通道同時的運動基元(塞滿一般仿射 M 的所有自由度)。
- **(J-3)** cascade 波速/散佈/件數隨檔位(跨件波的檔位軸)。
- **(G-1)** `--rig`×pivot 系列 per-bone 語意去重;**(G-2)** 主秀 beat 下 limb 繞關節 AC。
- S5→L3 仍待 **(D) 多 rig 真值**(C/資源類,使用者提供)。
