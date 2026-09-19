# S1 — squash 接檔位幅度差異化:耦合 amplify(candidate G-4''''',`squash_tier_amplitude` L2)

> 2026-09-19。把 (G-4'''') 新生成的 **shear + 耦合非均勻 scale 節拍(squash,斜拉果凍擠壓)** 接進 (J) 的
> **檔位幅度差異化**機制:squash 的 shear 峰與 squash 拉長峰**兩通道同步隨檔位(Super→Legend)嚴格遞增**,
> 同時**體積守恆(scaleX·scaleY≡1)與非均勻/阻尼簽章在每個檔位保形**。又一「檔位機制就緒 ≠ 每個新通道接上」
> 實例(同 E/H/I/J/G-4'/G-4'')——這次卡點在**scale 的體積守恆不變量**,不是「加不加通道」而是「怎麼放大才不破壞守恆」。

## 缺口(G-4'''' 明列的 honest boundary)

- **(J)** 讓主秀 beat 依檔位產 `{beat}__{tier}` 幅度差異化變體;**(G-4'')** 已讓 shear 通道也吃檔位增益。
- **(G-4'''')** 的 `gen_squash` 是**第一個同時產 shear + 非均勻 scale** 的生成器,其 scale 是**體積守恆對**
  (scaleX=1+q 拉長、scaleY=1/(1+q) 壓扁 ⇒ scaleX·scaleY≡1)。但 squash **不在** `MAIN_SHOW_CATS`——因為
  `tier_variants._amp_scale` 只放大 identity **上方**(`v≥1 → 1+g(v−1)`,`v<1` 樓地板不動):
  對 squash 對套逐軸 → scaleX>1 被放大、scaleY<1 **不動** → **破壞體積守恆**(scaleX·scaleY≠1)。
  G-4'''' 誠實標記此為 honest boundary(「squash 未接 tier,需耦合 amplify」)。
- 本次(G-4''''')正是照那條邊界接上:**體積守恆對走耦合 amplify**。

## 做了什麼(全 additive)

1. **`tier_variants._amp_scale_pair(sx, sy, g)`**(新):體積守恆非均勻對的**耦合** amplify——放大**拉長軸**
   (套與逐軸相同的 `1+g(v−1)`)、**壓縮軸取其倒數** ⇒ 放大後仍 `scaleX·scaleY≡1`。對稱處理兩軸何者為拉長軸。
2. **`tier_variants.amplify_bone_tl`** 的 scale 迴圈:對每個 scale 幀判「是否體積守恆非均勻對」——
   `|scaleX·scaleY−1| ≤ 1e-3` **且** `|scaleX−scaleY| > 1e-3`。是 → 走 `_amp_scale_pair`(耦合);
   否(等比 overshoot / identity 端點 / 非守恆)→ 逐軸 `_amp_scale`(向後相容,零回歸)。
   - **以數學不變量偵測,不靠 beat 名**:只有 squash 產非均勻 scale(其餘主秀皆等比),故此偵測正好命中
     squash 的 scale 幀,且對**任何**體積守恆擠壓自動成立(現在與未來的新節拍不需改 amplify)。
3. **`tier_variants.MAIN_SHOW_CATS`** 加入 `"squash"` → `build_animations(tier_gains=)` 產 `squash__{tier}`;
   shear 通道同 wobble(`v'=g*v`)→ shear 峰與 squash 拉長峰**同步**隨檔位放大 → **耦合關係(q_i 隨 |shear_i|)保持**。
4. **`validate_squash_tier.py`**(新,5 AC)。
5. **`validate_tier_combo_count.py`**(J-2 閘)K5(c) 改判準:從「用 `impact_peaks` 探針比非-combo beat 峰數」
   改為「full(gains+counts)vs amp_only(gains-only)的非-combo 變體**逐位元相同**」。前版探針是 **combo 專屬**度量,
   squash 加入 MAIN_SHOW_CATS 後其**幅度**檔位差異化(scaleX 隨檔位放大)會跨過 impact prominence 門檻 →
   峰數各檔位不同 → **假陽性**。逐位元比直接測「combo 連擊數機制是否外洩」,與其他節拍用什麼通道無關,無探針假影。
6. **`check_readiness`** 新增 cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(仍 HOLD)。
7. 圖 `knowledge/figures/s1_squash_tier.png`(左:各檔位 shearX 阻尼包絡;中:scaleX 實線拉長/scaleY 虛線壓扁互為倒數;
   右:雙通道峰遞增 bar + worst |scaleX·scaleY−1| 標註)。

## 驗收(`validate_squash_tier.py` OVERALL PASS,先驗庫→真實 build_spine robot 骨架→build_animations)

- **V1 present + backward-compat**:squash base 同時帶 shear+非均勻 scale;每檔位 `squash__{tier}` 產出、finite、
  有 bone、≥1 bone 同時帶 shear 與非均勻 scale、名仍路由回 squash;**base 帶/不帶 tier_gains 逐位元不變**。
- **V2 crux — 雙通道遞增**:峰 |shearX| = **[16.0, 21.6, 27.2, 33.6]°** 且 squash 拉長峰 max|scaleX−1| =
  **[0.160, 0.216, 0.272, 0.336]** 皆 Super<Mega<Omg<Legend 嚴格遞增,Super(g=1)== base(向後相容)。
- **V3 crux — 體積守恆逐檔保形**(=本次修的 honest boundary):每檔位每 squash 極值幀 (a)`|scaleX·scaleY−1|≤2e-2`
  (**實測 worst < 1e-4**);(b)非均勻 max|scaleX−scaleY|≥0.05;(c)拉長幅度隨極值嚴格遞減(阻尼);
  shearX 亦 (d)首尾 0 (e)繞 0 變號 ≥3 (f)相繼極值遞減。
- **V4 耦合隔離**:全 storyboard(含所有 `__tier` 變體)僅 squash 及其變體同時帶 shear+非均勻 scale;
  wobble 有 shear 無非均勻 scale、其餘有等比 scale 無 shear → 耦合為 squash 獨佔。
- **V5 負對照**:(a)**平增益守衛** 全 1.0 → V2 兩峰遞增 FALSE 且各檔位逐位元==base;
  (b)**耦合 vs 逐軸破壞守恆守衛**:對合成守恆對 (1.14, 0.8772) 施 g=2:耦合放大 → **(1.28, 0.7813) 積=1.00006**(守恆);
  同一對用**逐軸舊法** → **(1.28, 0.8772) 積=1.1228**(破壞)⇒ 證修法確有必要、閘測的是守恆保形非恆真;
  (c)**等比 gating 守衛**:等比 pulse(scaleX==scaleY)不走耦合路 → 兩軸皆逐軸放大(積改變、非被強制為 1)。

## 關鍵發現

- **「怎麼放大」而非「加不加通道」是新卡點**。前面幾個檔位接續(G-4''/wobble shear)只需「對 0 對稱同比放大」,
  因通道值沒有相互約束。squash 的 scale 帶了**體積守恆不變量**(scaleX·scaleY≡1),逐軸放大會**破壞不變量**——
  正確做法是**在不變量的自由度上放大**(放大拉長量 q → g·q,壓縮軸自動取倒數),讓放大後仍落在守恆流形上。
- **耦合 amplify 與既有逐軸 amplify 一致**:拉長軸套的正是原 `_amp_scale`(1+g(v−1)),只是把「壓縮軸留原地」改成
  「壓縮軸取拉長軸倒數」。故 squash 拉長峰的檔位階梯與其他 scale 節拍**同一把尺**(J 增益),誠實不另設參數。
- **兩通道同源放大 → 耦合保持**:shear 峰與 squash 拉長峰都乘同一 g,原本「q_i 隨 |shear_i|」的耦合比在各檔位不變
  (檔位改的是整體強度,不改兩通道的相對關係)。
- **數學不變量偵測 > beat 名路由**:用「體積守恆且非均勻」認定走耦合路,比硬編碼 `cat=="squash"` 更 robust——
  對任何未來的體積守恆擠壓節拍自動成立,且不會誤把等比 overshoot 或 identity 端點當耦合。
- **探針要配對度量**:J-2 閘 K5(c) 用 `impact_peaks`(combo 專屬)當跨 beat 泄漏探針,squash 幅度差異化一接上就假陽性;
  改逐位元比 full vs amp_only 才是「機制隔離」的正確、無假影判準(同 wobble_tier 對 J3 改 channel-aware 的教訓)。

## honest boundary(仍在)

- 仍只產 **shearX**(shearY≡0)。
- squash **count-aware** 未接:擠壓/振盪段數隨檔位遞增(`gen_squash` 的 `nosc` 已備參數,同 G-4''' 對 wobble、
  J-2 對 combo 的做法——段數是拓樸,需 gen 時決定,不能事後 amplify)。
- 檔位增益階梯沿用 (J) 的 `{Super:1.0,Mega:1.35,Omg:1.70,Legend:2.10}`(PROPOSAL,結構簽章客觀、手感留使用者 A 類)。
- 單一真值資產(robot_parts)。與 `spine-anim-forge` 區塊同 **HOLD**(運動基元為先驗手感、防固化)。

## 續(擇一,皆純自主)

- **(G-4'''''')** squash **count-aware**:擠壓段數隨檔位遞增(nosc 已備參數,比照 G-4''' wobble / J-2 combo)。
- 產 **shearY**(雙軸 shear)/ shear+scale+rotate 三通道同時的運動基元(真正塞滿一般仿射 M 的所有自由度)。
- **(J-3)** cascade 波速/散佈/件數隨檔位(cascade 的 count-aware:跨件波的第三種檔位軸)。
- **(G-1)** `--rig`×`--pivot-rotate`/`--scale-pivot`/`--shear-pivot` per-bone 語意去重;**(G-2)** 主秀 beat 下 limb 繞關節 AC。
- S5→L3 仍待 **(D) 多 rig 真值**(C/資源類,使用者提供)。
