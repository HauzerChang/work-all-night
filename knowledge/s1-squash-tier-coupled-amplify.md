# S1 (G-4''''') squash 接檔位差異化 —— 體積守恆**耦合 amplify**(雙通道:shear + 非均勻 scale 同時隨檔位遞增)

- **結論**:squash(斜拉果凍擠壓,G-4'''' 第一個同時產 shear + 體積守恆非均勻 scale 的節拍)**已併入
  `MAIN_SHOW_CATS`**,經新的**耦合 amplify** 隨檔位差異化 —— 擠壓愈高檔位愈強,而 `scaleX·scaleY≡1`
  (面積守恆)在**任一檔位**保持。這補齊了 G-4'''' 當時明白列出的 honest boundary:「squash 未接 tier 幅度
  (`_amp_scale` 只放大 identity 上方 → 破壞體積守恆,需**耦合 amplify**)」。
- **依據/來源**:`tools/analyzer/tier_variants.py`(`_amp_scale_coupled` + `amplify_bone_tl(coupled=)` +
  `COUPLED_SCALE_CATS` + squash 併入 `MAIN_SHOW_CATS`)、`gen_animations.py`(build_animations 依 cat 路由耦合)、
  自我驗收閘 `tools/analyzer/validate_squash_tier.py`(**6 AC 全 PASS**)。從**先驗庫**(slot_bigwin)→ **真實
  build_spine robot 骨架** → `build_animations(..., tier_gains=…)` 端到端量;端到端另經 `build_spine
  --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}` 且 `validate_build`
  round-trip overall_pass(premult MAE 0.031)。
- **信心程度**:高(客觀結構簽章 + crux 負對照 + round-trip;主秀手感為 PROPOSAL 屬使用者 A 類)。
- **相關階段**:第 2 階段(用工具鍛鍊四能力)之 S1 生成器 / 檔位差異化軸。

## 為什麼逐軸 `_amp_scale` 會破壞守恆(honest boundary 的成因)

(J) 的幅度增益 `_amp_scale(v,g)=1+g(v−1) if v≥1 else v` 是**逐軸**且**只放大 identity 上方 overshoot**、
下方樓地板(squash/collapse 語意)不動。這對 hit/combo/reveal 的 scale 是對的,但對 squash 是**錯的**:
squash 每個極值幀是 `(scaleX, scaleY)=(1+q, 1/(1+q))`(拉一軸、壓一軸,`scaleX·scaleY≡1`)。逐軸增益會
**脹 scaleX(>1)** 卻**保留 scaleY(<1)樓地板不動** → `scaleX·scaleY≠1`(面積不再守恆,擠壓變成「單邊拉長」
的假擠壓)。實測 Legend 增益下逐軸 amplify 讓 `|scaleX·scaleY−1|` 高達 **0.10–0.15**(見 crux 負對照)。

## 耦合 amplify(解法)

`_amp_scale_coupled(sx, sy, g)`:找**拉長軸**(值 ≥1 的一軸,squash 恆為 scaleX),以既有 `_amp_scale`
放大其 overshoot(`sx'=1+g·q`),**壓縮軸設為其倒數** `sy'=1/sx'`。因此:

- **體積守恆由建構保證**:`scaleX'·scaleY'=1`(不論輸入 sy 的 4 位捨入誤差;實測殘差 ≤1e-4,主因倒數存 4 位)。
- **介面契約保持**:identity 幀 sx==sy==1 → `_amp_scale(1,g)=1` → `(1,1)`(可插 Loop 間,各檔位皆然)。
- **擠壓強度隨檔位遞增**:非均勻 `|scaleX'−scaleY'|=|(1+g·q)−1/(1+g·q)|` 隨 g **單調增大**(檔位擠壓簽章)。
- **與其餘主秀 scale 增益同語意**:拉長軸走同一條 `_amp_scale`(overshoot 線性增益);差別只在壓縮軸走倒數而非樓地板。
- **shear 通道不變**:squash 的 shearX 仍走既有 `v'=g*v`(對 0 對稱)→ 同源 shear 峰亦隨檔位遞增、阻尼簽章保形。

`build_animations` 依 `COUPLED_SCALE_CATS={squash}` 決定該用耦合(squash)或逐軸(其餘主秀)amplify —— 集中一處,
後續再加別種「shear + 體積守恆非均勻 scale」耦合節拍只需擴這個集合。

## 端到端量測(6 AC 全 PASS)

- **ST1** present + backward-compat:每檔位 `squash__{tier}` 產出/finite/有 bone/**dual-channel(shear+scale)**/
  路由回 squash;base(In/Loop/Out + base squash)逐位元不變;**Super(g=1.0)逐位元 == base squash**(耦合 amplify 於 g=1 為 identity)。
- **ST2 crux**:**每檔位每 bone 每內部極值** `|scaleX·scaleY−1|≤2e-4`(守恆在檔位放大下仍保持);且峰**非均勻**
  `|scaleX−scaleY|` [0.298,0.394,0.486,0.588] 與峰**拉長** `scaleX−1` [0.16,0.216,0.272,0.336] 皆 **嚴格遞增**,Super==base。
- **ST3** shear 雙通道:shearX 峰 [16,21.6,27.2,33.6]° **嚴格遞增**(Super==base);且**每檔位**仍首尾 0 + 繞 0 變號≥3 +
  相繼極值嚴格遞減(阻尼簽章保形)。→ shear 與 scale **兩通道同時**隨檔位放大而各自簽章不破。
- **ST4** identity 介面:每檔位 sample(0)/sample(dur) identity + shear 首尾 0 + scale 首尾 (1,1)。
- **ST5 crux 負對照**:對 base squash 施**逐軸** amplify(Legend 增益)→ 每個 dual-channel bone `|scaleX·scaleY−1|`
  達 **0.10–0.15 > 2e-4**(逐軸破守恆);對照耦合 amplify 同增益殘差 ≤1e-4(>500× 鑑別餘裕)→ 證耦合 amplify 的
  必要性(沒它 squash 無法檔位差異化)與閘測「守恆」非恆真。
- **ST6** 負對照/隔離:(a) 平增益全 1.0 → ST2 遞增 FALSE 且各檔位 == base;(b) `_amp_scale_coupled` 單元測
  (identity 保介面、g>1 積≈1 且拉長/非均勻皆增);(c) **耦合隔離**:非 squash 的主秀 tier 變體(如 wobble,shear-only)
  不被耦合路徑波及(不生 scale 倒數鍵);(d) 加性:移除 squash storyboard → 其餘 beat(含 wobble tier 變體)逐位元不變。

## 關鍵發現 / 踩雷

1. **「面積守恆」是耦合約束,不能逐軸放大**:squash 的檔位差異化與 wobble(G-4'')/combo(J) 的**逐軸/對 0 對稱**
   幅度增益本質不同 —— 它有一條跨軸不變量 `scaleX·scaleY≡1`,放大時必須沿**該流形**走(拉長軸自由、壓縮軸=倒數),
   否則就跳出守恆流形變成假擠壓。這是**第一個帶跨通道守恆約束的檔位軸**(先前 rotate/translate 對 0 對稱、
   scale-overshoot 逐軸,皆無跨軸耦合)。
2. **雙通道同時檔位差異化**:squash 是第一個 **shear + 非均勻 scale 兩通道同時**隨檔位遞增而各自結構簽章
   (阻尼振盪 / 體積守恆)皆保形的節拍(wobble 只有 shear 單通道)。
3. **回歸踩雷 —— combo 專屬 impact-peak 指標對 squash 誤判**:`validate_tier_combo_count` K5(c) 的
   `_min_peaks`(數 scaleX≥1.10 的 impact 峰)是 **combo 專屬**指標;squash 的 head role base 峰恰為 1.10,
   耦合**幅度**增益把它推過門檻 → 峰數隨檔位變,但這是**幅度非 combo count 外洩**(tier_combo_hits 根本不路由
   到 squash)。修正=K5(c) 排除 `SHEAR_CATS`(這類節拍的 count 隔離由各自的閘驗:wobble 段數 U5c 用 `_nosc`;
   squash 目前非 count-aware)。教訓:**類別專屬的結構指標不可跨類別當通用「count」用**。

## 仍在的 honest boundary(後續候選)

- **squash count-aware**(擠壓段數隨檔位):`gen_squash(nosc=)` 已備參數但未接 `tier_variants` 路由
  (比照 G-4''' wobble / J-2 combo,需加 `TIER_SQUASH_CYCLES` + `_count_maps` 一列,並確認 nosc 遞增下體積守恆
  逐極值仍保持)。**本次只做幅度(耦合 amplify)軸,未做段數軸**。
- **shearY≡0**:squash/wobble 仍只產 shearX;雙軸 shear / rotate+scale+shear 三通道同時的運動基元(塞滿一般仿射 M
  所有自由度)為後續。
- squash 幅度階梯沿用 (J) 增益 [1.0,1.35,1.70,2.10] 為 PROPOSAL(手感留使用者 A 類)。

cap `squash_tier_coupled_amplify` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
圖 `figures/s1_squash_tier_coupled.png`(左:coupled scaleX 拉長/scaleY 壓扁隨檔位;中:volume product 耦合≡1 vs 逐軸破線;右:aniso & shear 雙通道皆遞增)。
