# S1 — squash 接檔位幅度差異化(體積守恆乘冪放大,candidate G-4''''',`squash_tier_amplitude` L2)

> 2026-09-13。續 (G-4''''):(G-4'''') 讓 `gen_squash` 成為**第一個同時產 shear + 非均勻 scale
> (體積守恆擠壓)**的生成器,但把 squash 排除在 `MAIN_SHOW_CATS` 外 —— 一般幅度增益會**破壞體積守恆**。
> 本次補上**體積守恆的乘冪(對數空間)耦合放大**,把 squash 併入 `MAIN_SHOW_CATS`,使**擠壓強度
> (非均勻度)隨檔位嚴格遞增**而**每個檔位仍精確體積守恆**。

## 缺口(honest boundary 的接續)

- **(G-4'''')** 的 honest boundary 明寫:「squash 未接 tier 幅度(`_amp_scale` 只放大 identity 上方
  → 破壞體積守恆,需**耦合 amplify**)」。squash 的 scale 是體積守恆對 `(scaleX, scaleY)=(1+q, 1/(1+q))`:
  一般 `_amp_scale`(`v'=1+g(v−1)` 僅 v≥1、下方樓地板不動)會**放大 scaleX>1、凍結 scaleY<1**
  → `scaleX·scaleY≠1`,擠壓變成「單邊拉長」,不再是守恆擠壓。
- 本次(G-4''''')正好照那條邊界接上:**擠壓強度隨檔位遞增而體積仍守恆**。

## 關鍵:守恆量必須在 log 空間(乘冪)放大,不能加法

先前所有增益都是**加法/線性**:scale 的 `1+g(v−1)`、rotate/translate/shear 的 `g*v`。但**乘積守恆量
無法用加法放大** —— 加法會破壞乘積。守恆放大必須放大**指數**:

    _amp_scale_vp(v, g) = v ** g

    關鍵恆等式:  sx**g · sy**g = (sx·sy)**g = 1**g = 1   ⇒ 放大後乘積仍精確 == 1(體積守恆)
    identity:    1**g = 1                                 ⇒ 首尾介面契約對所有檔位保持
    非均勻遞增:  sx>1 → sx**g 隨 g 遞增、sy<1 → sy**g 隨 g 遞減 ⇒ |sx**g − sy**g| 隨檔位嚴格遞增

這是產線**第一個乘法(幾何)增益**。等價於在 log-scale 上做線性放大(`log s' = g·log s`),故它同時
是 identity-preserving(log 1 = 0)、乘積守恆(log 分配於乘積)、且對「擠壓深度」單調放大。

- **shear 軸**仍走 `g*v`(同 wobble,對 0 對稱阻尼擺動的自然保形)。
- **scale 軸**改走 `v**g`(coupled_scale)。兩軸各自對其通道保形 → squash 整體「更斜更擠、體積仍守恆」。

## 做了什麼(全 additive,g=1.0 逐位元向後相容)

1. **`tier_variants.py`**:
   - `MAIN_SHOW_CATS` 加 `"squash"`。
   - 新增 `COUPLED_SCALE_CATS = {"squash"}`(scale 為體積守恆非均勻 squash、須乘冪放大的類別)。
   - 新增 `_amp_scale_vp(v, g) = v ** g`。
   - `amplify_bone_tl(b, g, coupled_scale=False)`:`coupled_scale=True` 時 scale 通道走 `_amp_scale_vp`
     (兩軸同冪 → 乘積守恆)取代逐軸 `_amp_scale`;shear/rotate/translate 不受影響。
   - `amplify_anim(anim, g, coupled_scale=False)` 透傳。
2. **`gen_animations.py`**:`build_animations` 匯入 `COUPLED_SCALE_CATS`;tier 迴圈依 `cat ∈ COUPLED_SCALE_CATS`
   決定 `coupled`,傳給 `_amplify_anim(..., coupled_scale=coupled)`。
3. **`validate_squash_tier.py`**(新,5 AC)。
4. 圖 `knowledge/figures/s1_squash_tier.png`(左:各檔位 scaleX↑/scaleY↓ 對稱張開;中:scaleX·scaleY 各檔位恆 1;
   右:峰非均勻 + 峰 shear 雙軸隨檔位遞增)。

> **無新旗標**:squash 早在 (G-4'''') 就走 `--shear-pivot`;本次併入 MAIN_SHOW_CATS 後,既有
> `build_spine --animate --tier-variants --shear-pivot` **直接**多出 `squash__{Super,Mega,Omg,Legend}`。

## 自我驗收(`validate_squash_tier.py`,5 AC 全 PASS)

從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(tier_gains)` 端到端量;判準復用
G-4'(shear 阻尼簽章)與 G-4''''(`_sq3_eval` 體積守恆/非均勻/阻尼純函式)確保閘一致可信:

- **SQT1 present + backward-compat**:每檔位 `squash__{tier}` finite/有 bone/≥1 bone **同時**帶 shear+scale、
  名經 `beat_category` 仍路由回 squash;**base 逐位元不變**(帶/不帶 tier_gains 的 base + In/Loop/Out 相同)。
- **SQT2 crux — 非均勻峰單調**:各檔位峰 |scaleX−scaleY| **[0.298, 0.403, 0.510, 0.633]** Super<Mega<Omg<Legend
  嚴格遞增且 Super==base;shear 峰 **[16, 21.6, 27.2, 33.6]°** 亦嚴格遞增(兩軸一致遞增)。
- **SQT3 crux#2 — 放大後仍守恆**:**每檔位**每個 scale 極值幀 (a)`|scaleX·scaleY−1| ≤ 0.02`(實測 ≤1.5e-4,
  **乘冪放大保守恆**);(b)至少一極值非均勻 ≥0.05;(c)squash 幅度 |scaleX−1| 隨極值嚴格遞減(阻尼耦合保形);
  (d)shear 亦阻尼保形(首尾 0 + 繞 0 變號≥3 + 相繼極值遞減)。
- **SQT4 identity 介面 / 檔位**:每檔位 sample(0)/sample(dur) identity + shear 首尾 0 + scale 首尾 (1,1)。
- **SQT5 負對照**:
  (a) **平增益守衛**:增益全 1.0 → SQT2 非均勻遞增 FALSE 且各檔位逐位元 == base(證閘測遞增非恆真)。
  (b) **耦合 vs 加法對照(crux 鑑別)**:對合成體積守恆 pair 施**錯的**加法 `_amp_scale` → 體積**破壞**
      (積≠1,`additive_volume_ok=False`);施**對的**乘冪 `_amp_scale_vp` → 體積守恆(`vp_volume_ok=True`)
      **且**非均勻變大 → 直接證「守恆須乘冪、加法會壞」是閘實測性質、耦合放大器**必要**。
  (c) **通道隔離單元測**:`amplify_bone_tl(coupled_scale=True)` 對體積守恆 scale-only bone → 積仍≈1、非均勻變大、
      不生 shear 鍵;對 shear-only bone → shear `g*v` 放大、不生 scale 鍵。

**端到端**:`build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}`;
pivot 補償(Δ=(M−I)(O−P))只加 translate、不動 scale/shear → 各檔位體積守恆(max dev ≤1.5e-4)、非均勻與
shear 峰皆遞增於 pivot 不動的一般仿射之上(pivot≈中心的身體/光暈正確略過補償)。

## 關鍵發現 / 踩雷

- **守恆量的檔位放大 = log 空間線性放大(乘冪)**:這是本里程碑的核心洞見,也是產線**第一個非加法增益**。
  「檔位差異化」的通用範式至此有**三種增益算子**:(1) scale overshoot 加法 `1+g(v−1)`(J);
  (2) 對 0 對稱線性 `g*v`(rotate/translate/shear,G-4'');(3) **體積守恆乘冪 `v**g`(squash,本次)** ——
  每種都對其通道的「介面契約 + 結構簽章」保形,選錯算子(如對 squash 用加法)會破壞守恆(SQT5b 實證)。
- **必須 cat-aware,不能靠偵測**:是否走乘冪放大由 `cat ∈ COUPLED_SCALE_CATS` 決定,而非在 keyframe 偵測
  「scaleX·scaleY≈1」—— 後者對一般等比 pulse(積=1.44≠1)雖不誤觸,但把守恆語意藏進數值巧合並不誠實;
  沿用產線既有「依 cat 路由」的架構最穩(同 `_count_maps` / `_PHASE_AWARE`)。
- **回歸踩雷:`_min_peaks` 對 squash 無語意**。`validate_tier_combo_count` 的 K5(c)「count 只作用 combo」
  用 impact 峰計數器 `_min_peaks` 掃所有非-combo 主秀 beat 檢查峰數各檔位恆定。squash 的 scaleX 峰(Super
  1.14)本在 impact 顯著度門檻**下**,乘冪放大在高檔位越過門檻 → 峰數 [0,1,1,1] 隨**幅度**變(非 count 外洩;
  squash 從不在 COUNT_AWARE_CATS)。修法:K5(c) 跳過 `SHEAR_CATS`(其 scaleX/shear 為振盪/守恆擠壓,非離散
  impact pulse,`_min_peaks` 對其無語意);count 隔離由各自專屬閘覆蓋。

## 回歸

16 閘全綠 + squash_gen + 本閘 = **18 閘全綠**:shear_gen / wobble_tier / wobble_count / shear_pivot(G-4)/
scale_pivot(G-3)/ pivot_rotation(0i)/ tier_variants(J)/ tier_combo_count(J-2,K5c 更新)/ priors /
priors_beats / priors_combo_charge / priors_cascade / cascade / more_beats / beat_templates / deform_gen /
squash_gen(G-4'''')/ squash_tier(本次)。

## honest boundary(仍在)

- 增益階梯 [1.0, 1.35, 1.70, 2.10] 沿用 (J)(擠壓強度客觀遞增、多擠才對味的手感留使用者 A 類)。
- squash **count-aware**(擠壓段數 nosc 隨檔位,`gen_squash(nosc=)` 參數已備)為後續(比照 G-4'''/J-2)。
- 仍只 shearX(shearY≡0);雙軸 shear / shear+scale+rotate 三通道同時的運動基元為後續。
- 單一真值資產(robot_parts)、運動基元先驗 → `spine-anim-forge` 區塊**仍 HOLD**(防固化)。

## 下一步(擇一,皆純自主)

- **squash count-aware**(擠壓段數隨檔位,`nosc` 已備,比照 G-4''')—— 補本次的 honest boundary。
- 產 **shearY**(雙軸 shear)/ shear+scale+rotate 三通道同時的運動基元(塞滿一般仿射 M 全自由度)。
- **(J-3)** cascade 波速/散佈/件數隨檔位(cascade 的 count-aware:跨件波第三種檔位軸)。
- **(G-1)** `--rig`×pivot 各 flag per-bone 語意去重;**(G-2)** 主秀 beat 下 limb 繞關節 AC。
- S5→L3 仍待 **(D) 多 rig 真值**(C/資源類,使用者提供)。
