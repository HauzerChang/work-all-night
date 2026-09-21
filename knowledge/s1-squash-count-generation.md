# S1 (G-4'''''-c) squash 擠壓段數隨檔位遞增 —— count-aware × 幅度 × 體積守恆三效正交

- **結論**:squash(斜拉果凍擠壓,G-4'''' 第一個同時產 shear + 體積守恆非均勻 scale 的節拍)的擠壓
  **段數** `nosc` 已能**隨檔位嚴格遞增**(Super 4 → Mega 5 → Omg 6 → Legend 7),補齊 G-4''''' 明白
  列出的 honest boundary(「squash count-aware(段數,`gen_squash(nosc=)` 已備參數未接)」)。**關鍵**:
  段數增多(多長出低幅擠壓極值)與既有的**幅度**檔位差異化(G-4''''' 耦合 amplify)**正交可疊**,且
  **每個檔位、每個(含新增的)擠壓極值都仍體積守恆**(`scaleX·scaleY≡1`)—— 段數 × 幅度 × 守恆三效同時成立。
- **依據/來源**:`tools/analyzer/tier_variants.py`(`TIER_SQUASH_CYCLES` + `squash_cycles_for` +
  squash 併入 `COUNT_AWARE_CATS`)、`gen_animations.py`(`build_animations(..., tier_squash_cycles=)`,
  `_count_maps` 加 squash 路由)、`build_spine.py`(`--tier-variants` 帶入 `squash_cycles_for`)、
  自我驗收閘 `tools/analyzer/validate_squash_count.py`(**5 AC 全 PASS**)。從**先驗庫**(slot_bigwin)→
  **真實 build_spine robot 骨架** → `build_animations(..., tier_gains, tier_squash_cycles)` 端到端量;
  端到端另經 `build_spine --animate --tier-variants --shear-pivot` 直出
  `squash__{Super4,Mega5,Omg6,Legend7}` 且 `validate_build` round-trip overall_pass(premult MAE 0.031)。
- **信心程度**:高(客觀結構簽章 + crux 守恆量測 + 正交/負對照 + round-trip;段數/幅度階梯為 PROPOSAL 屬使用者 A 類)。
- **相關階段**:第 2 階段(用工具鍛鍊四能力)之 S1 生成器 / 檔位差異化「結構(段數)軸」。

## 為什麼幅度增益加不出段數(要走「重生成」而非 amplify)

G-4''''' 的耦合 amplify 只能把既有極值**同比放大**(拉長軸 `sx'=1+g·q`、壓縮軸 `sy'=1/sx'`),
無法在包絡裡**多長一段**。擠壓段數 = shear 包絡繞 0 交替變號的極值**個數**(= 耦合 squash 極值個數),
是關鍵幀**拓樸**,必須在 `gen_squash` 生成當下由 `nosc` 決定。故對 squash 檔位變體以該檔位 `nosc`
**重生成**整支 beat(`_build_beat(..., count=nosc)` → `gen_squash(role, side, radial, nosc)`),
再疊 G-4''''' 的**耦合**幅度增益 g。此模式與 (G-4'') 對 wobble 振盪段數、(J-2) 對 combo 連擊數所做
**完全同構**,惟段數階梯**各類別獨立**(combo→`TIER_COMBO_HITS`、wobble→`TIER_WOBBLE_CYCLES`、
squash→`TIER_SQUASH_CYCLES`,`build_animations` 依 cat 路由 `_count_maps`)。

## squash count 獨有的 crux(與 wobble count 的關鍵差異)

wobble 只產**純 shearX**(無 scale 約束),段數增多不涉及守恆;**squash∈`COUPLED_SCALE_CATS`** —— 段數
重生成後仍走**耦合** amplify,故段數 × 幅度 × **體積守恆**三效必須**同時**成立。段數增多會多長出**低幅**
擠壓極值(`q_i = Q·rⁱ` 隨 i 遞減,r=0.5;Legend 的 nosc=7 最末極值 `q_6 = Q/64`),閘的 crux 就是證這些
**新增的**低幅極值也守恆:每個內部極值都由 `_squash_env` 建構為 `(1+q_i, 1/(1+q_i))` → `scaleX·scaleY≡1`,
再經耦合 amplify(壓縮軸恆取倒數)→ 守恆**由建構保證**。實測各檔位所有內部極值 `max|scaleX·scaleY−1| = 9.7e-05`
(≤ TOL_VOL=2e-4;主誤差為倒數存 4 位捨入)。

## 向後相容(byte-identical)

- `gen_squash(nosc=4)` 逐位元 == `gen_squash()` 預設(squash 無 wobble 那條 `nosc==4` 手調 golden 特例,
  但預設本就是 4)→ **Super(nosc=4, g=1.0)逐位元 == base squash**(耦合 amplify 於 g=1 對這組 q 值為 identity)。
- **不帶** `tier_squash_cycles`(=None)時,squash 變體逐位元 == G-4''''' 幅度-only 輸出(加性 opt-in、零回歸)。
- 四個 tier 參數(`tier_gains`/`tier_combo_hits`/`tier_wobble_cycles`/`tier_squash_cycles`)皆 None → 逐位元同舊行為。

## 端到端量測(5 AC 全 PASS,`validate_squash_count.py`)

- **SC1** present + backward-compat:每檔位 `squash__{tier}` 產出/finite/有 bone/**dual-channel(shear+scale)**;
  base squash 恆 4 段且逐位元不變;`tsc=None` 逐位元同 G-4''''' 幅度-only。
- **SC2 crux**:段數 [4,5,6,7]==宣告、Super<Mega<Omg<Legend 嚴格遞增、Super 段數==base;**且**每檔位每內部
  scale 極值 `|scaleX·scaleY−1|≤2e-4`(max 9.7e-05)—— 段數增多的低幅極值仍守恆。
- **SC3**:每檔位仍(a)shearX 首尾 0;(b)繞 0 變號≥3;(c)相繼 shear 極值嚴格遞減(阻尼保形);**且**峰 |shearX|
  與峰非均勻 |scaleX−scaleY| 仍隨檔位嚴格遞增(段數軸不抵消幅度/擠壓軸)。
- **SC4 正交**:(a) 段數 + 平增益(全 g=1.0)→ 段數仍遞增、峰非均勻**不**遞增、**且體積仍守恆**
  (段數單獨作用不破守恆);(b) 增益 + 無段數(tsc=None)→ 段數恆 4、峰非均勻遞增(兩軸可獨立開關)。
- **SC5 負對照**:(a) 平段數(全 4)→ 段數單調性 FALSE;(b) 無宣告的 genre(slot_reveal)→ `squash_cycles_for`
  回 None 且無檔位增益 → 不產 squash 段數變體;(c) 段數只作用 squash → 非-squash 主秀 beat 的 shear 段數
  在各檔位恆定(不外洩;wobble 仍 4 段)。

端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super4,Mega5,Omg6,Legend7}`
(pivot 補償後段數不變);`validate_build` round-trip overall_pass(premult MAE 0.031)。

## 關鍵發現

- **結構(段數)軸的檔位差異化已在三個不同通道成立**:combo=scale 峰數、wobble=shear 振盪段數、
  squash=耦合 squash 段數 —— 同一 count-aware 概念(重生成 + 各類別獨立段數階梯 + 與幅度軸正交)可推廣。
- **帶跨通道守恆約束的類別,count-aware 要多驗一層**:squash 的段數軸不只是「多幾個關鍵幀」,而是「多幾個
  **守恆**極值」;阻尼比 r=0.5 讓新增的低幅極值 `q_i` 天然變小 → 守恆殘差反而更小(倒數捨入誤差隨 q 減小)。
- 三效正交可疊(段數 × 幅度 × 守恆)是「檔位機制就緒 ≠ 每個新軸接上」在 squash 上的最後一塊(幅度已於 G-4''''' 接、段數本次接)。

## 回歸

19 閘全綠(18 既有 + 新 `squash_count`):squash_tier(G-4''''')/squash_gen(G-4'''')/wobble_count/wobble_tier/
tier_combo_count/tier_variants/shear_gen/shear_pivot/scale_pivot/pivot_rotation/cascade/priors/priors_beats/
priors_combo_charge/priors_cascade/more_beats/beat_templates/deform_gen + round-trip `validate_build` overall_pass。

## honest boundary(仍在)

- 段數階梯 [4,5,6,7] 與幅度階梯皆為 **PROPOSAL**(手感屬使用者 A 類)。
- `shearY≡0`(單軸 shear;雙軸 shear / shear+scale+rotate 三通道同時 = G-4'''''' 為後續)。
- 單一真值資產(robot_parts);`spine-anim-forge` 區塊**仍 HOLD**(運動基元先驗、防固化)。
- cap `squash_tier_count_aware` L2 併入 `spine-anim-forge`。
