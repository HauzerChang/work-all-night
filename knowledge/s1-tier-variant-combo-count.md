# S1 (J-2) — combo 連擊「數」隨檔位遞增(結構差異化,與幅度正交)

- **結論**:candidate (J) 讓 `{beat}__{tier}` 檔位變體只差**幅度**(愈高檔位愈爆),但 combo 各檔位仍是**同一組三連擊**
  —— 有「多爆」沒「連幾下」。本次補上 (J-2):combo 的 impact 峰**數** = `nhits` **隨檔位嚴格遞增**
  (Super 3 → Mega 4 → Omg 5 → Legend 6)。連擊數是**結構**軸,與 (J) 的**幅度**軸**正交可疊**。
- **信心**:高。整合閘 `validate_tier_combo_count.py`(先驗庫 → 真實 build_spine robot 骨架 → build_animations)
  **5 AC 全 PASS**;回歸(J 幅度-only 閘、more_beats、priors_combo_charge、cascade、round-trip)全綠。
- **相關階段**:第 2 階段(用工具鍛鍊 S1);延續 (E)/(H)/(I)/(J) 的 genre 先驗 → 生成器產線化。

## 為什麼幅度增益加不出「連擊數」

(J) 的 `tier_variants.amplify_anim(anim, g)` 是**事後**對**已生成**的 beat 逐鍵套增益 —— 它只能把既有峰
放大/縮小,**無法憑空多長出一個峰**。連擊「數」是關鍵幀**拓樸**(峰的個數),必須在 `gen_combo` **生成當下**
就決定。故本能力不走 amplify,而是對 combo 檔位變體以該檔位的 `nhits` **重生成**整個 beat,**再**疊上 (J) 的幅度增益。

- **兩軸正交可疊**:`nhits` 決定「連幾下」(結構,gen 時)、`gain` 決定「多爆」(幅度,事後 amplify)。
  端到端量:`combo__Super/Mega/Omg/Legend` 峰數 = **[3,4,5,6]**、overshoot 幅度 = **[0.347,0.469,0.591,0.730]**,
  兩者皆嚴格遞增(K2/K3),且 (K4) 證可獨立開關:counts+平增益 → 峰數仍遞增;gains+無 counts → 峰數恆 3、幅度遞增。

## 實作

- `beat_templates.gen_combo(role, side_sign, radial, nhits=3)`:
  - **`nhits=3` 逐位元同 0g 手調三連擊**(golden case,向後相容;base combo 恆走此路)。
  - `nhits≠3` → 通用生成器 `_combo_env(peak, nhits)`:第 i 擊(f=i/(n−1))峰前 dip(遞深 0.95→0.90)、
    峰 `p=1+q(0.60+0.40f)`(遞增,末擊=role peak,首峰夾 ≥`IMPACT_PROM`)、**擊間微回 0.985**(>`HOLD_LEVEL` 0.97),
    末擊後接固定 settle 尾(0.955→1.030→0.995→1.0,峰 <`IMPACT_PROM`)。
- `tier_variants.py`:`COUNT_AWARE_CATS={"combo"}`、`TIER_COMBO_HITS.slot_bigwin={Super:3,Mega:4,Omg:5,Legend:6}`、
  `combo_hits_for(genre)`。
- `gen_animations.build_animations(..., tier_gains, tier_combo_hits=None)`:抽出 `_build_beat(...,combo_hits=)` helper;
  對 `cat∈COUNT_AWARE_CATS` 的檔位變體以該檔位 nhits 重生成再 `amplify_anim(·, g)`。
  **`tier_combo_hits=None`(預設)→ 逐位元同 (J) 幅度-only 輸出**(加性 opt-in,零回歸)。
- `build_spine --tier-variants`:自動帶 `combo_hits_for(genre)`(combo 檔位變體直出遞增連擊)。

## 關鍵發現 / 踩雷

- **連擊變多不得誤入 charge 長蓄力簽章**:combo 與 charge 的鑑別子(`has_charge_signature`)是「峰前 <0.97 的時間佔比 ≥0.35」。
  峰數愈多 → 直覺上「蓄力段」也愈多,恐把 combo 誤判成 charge。**解法 = 擊間微回設 0.985(>0.97)**:
  峰與峰之間回到 hold-level 之上 → 不計入蓄力佔比。實測 hold-frac 反而**隨 nhits 下降**(n=3→0.30、n=6→0.12,皆 <0.35),
  故 combo↔charge 互斥在所有檔位保持(K3 明確驗 `仍非 charge`)。
- **簽章對更多峰保形**:每擊仍是「dip(<1)→峰(>1)」→ `(scale−1)` 變號數只增不減 → settle(變號≥3)恆成立;
  峰嚴格遞增且皆 ≥`IMPACT_PROM` → `has_combo_signature`(遞增峰≥3)恆成立;首尾 identity(可插 Loop 間)不動。
- **T 固定、峰壓縮**:combo 時長 `DUR["combo"]=0.9s` 不變,更多峰 → 峰間更密(Legend = 更快的連段 flurry)。
  上界定 6:週期檢核下 6 峰仍時間嚴格遞增且峰間不塌陷(_combo_env dip/rec 偏移 0.05/0.035 < 週期 0.10)。
- **負對照證閘可信**(K5):平連擊數(全 3)→ 峰數單調性 FALSE(證閘在測「遞增」非恆真);
  無宣告 count 的 slot_reveal → `combo_hits_for` 回 None,combo 變體不亂加連擊;count **只作用 combo**,
  不外洩到 hit/charge/cascade/burst(各檔位峰數不變)。

## 檔案

- `tools/analyzer/beat_templates.py`(`gen_combo(nhits=)`、`_combo_env`)、`tools/analyzer/tier_variants.py`
  (`COUNT_AWARE_CATS`/`TIER_COMBO_HITS`/`combo_hits_for`)、`tools/analyzer/gen_animations.py`
  (`_build_beat`、`build_animations(tier_combo_hits=)`)、`tools/analyzer/build_spine.py`(`--tier-variants` 帶 count)。
- 閘:`tools/analyzer/validate_tier_combo_count.py`(K1–K5)。圖:`knowledge/figures/s1_tier_combo_count.png`。
- cap `tier_variant_combo_count` L2(pipeline)併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
