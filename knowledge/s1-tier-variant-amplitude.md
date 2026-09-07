# S1 檔位(tier)幅度差異化 — candidate (J)

> 里程碑 2026-09-07。把 `genre_priors.slot_bigwin` 宣告已久卻從未被生成器使用的
> `tiers=[Super,Mega,Omg,Legend]` 接上產線:主秀 beat 依檔位產出**幅度差異化**變體
> (檔位愈高、主秀愈爆),並用整合閘證明「愈高檔位幅度愈大」是可量化的檔位簽章,
> 同時**每個檔位都仍保有介面契約與結構簽章**。

## 動機:又一個「宣告/模板就緒 ≠ 生成器接上」

`slot_bigwin` 的 `tiers` 早在先驗庫建立時就宣告了,但一路到 (E)/(H)/(I) 把主秀 beat 接進
產線後,**所有檔位仍共用同一組主秀幅度** —— `build_animations` 對每個 beat 只產一支動畫,
與檔位無關。這與 0f→(E)、0g→(H)、0h→(I) 反覆出現的模式相同:資料/模板就緒不代表生成器
真的會用它。(J) 補上這個缺口。

## 幅度增益規則(關鍵:對介面契約與結構簽章皆保形)

`tools/analyzer/tier_variants.py` 把檔位轉成一個**主秀幅度增益** `g`,對 base beat 的
timeline 逐通道套用:

| 通道 | 規則 | 保形理由 |
|---|---|---|
| **scale** | `v' = 1 + g·(v−1)` **僅當 v≥1**;`v<1` 保持不動 | 端點/樓地板=identity 的幀 g 後仍 identity(介面契約對**所有檔位**保持);overshoot 峰隨 g 單調變大(檔位簽章);squash/collapse 下方樓地板檔位無關(誠實);`(scale−1)` 符號序列不變 → anticipation+settle 簽章保持 |
| **rotate** | `v' = g·v`(對 0 對稱) | 0 仍 0(端點保持);幅度隨 g 放大 |
| **translate** | `v' = g·v` | 同上 |
| **color/alpha** | **不動** | 可見度非運動幅度;放大 alpha 會破壞 collapse/burst 語意且可能溢出 [0,1] |

**只放大主秀類別**(`MAIN_SHOW_CATS = {hit, reveal, burst, combo, charge, cascade}`);
In/Loop/Out(進退場/待機)**檔位無關**(idle 呼吸不該隨大獎檔位脹縮)。

**增益階梯** `TIER_GAIN["slot_bigwin"] = {Super:1.0, Mega:1.35, Omg:1.70, Legend:2.10}`
(嚴格遞增)。**base tier Super g=1.0 → `amplify_*` 為 identity 變換 → 逐位元 == 無檔位輸出**
(向後相容:舊路徑不動)。

### 為什麼「只放大 identity 上方 overshoot、不動下方樓地板」是正確的

天真作法「對 identity 均勻縮放 `1+g(v−1)`」會把 reveal 的 collapsed 起點(scale 0.02)
在 `g>1` 時推成負值(`1−0.98g<0` = 翻面)。正確作法是把下方(squash 蓄力 ~0.85、
collapse 藏匿 ~0.02)視為**結構語意樓地板**(蓄力多深、藏得多小是設計,不是大獎強度),
檔位無關;檔位只放大 identity **上方**的 overshoot(pop 多高)。這條規則同時:

1. **保端點**:凡 =identity 的幀(所有主秀 beat 首尾;hit/combo/charge/cascade 全程可回)
   增益後仍 =identity → 每個檔位都能插在 Loop 循環間(介面契約)。
2. **保簽章**:下方幀不動、上方幀等比放大、零幀仍零 →
   - hit/combo/charge 的 `(scale−1)` 變號數不變(anticipation+settle);
   - combo 三峰皆 >1、同乘 g → 嚴格遞增 `p1<p2<p3` 保持,且皆 ≥ `IMPACT_PROM`;
   - charge 的長蓄力 hold(下方 0.85)與時間軸都不動 → holdfrac 檔位間**相同**;
   - cascade 各件峰**時刻**不動(只動值)→ 跨件遞增+散佈簽章保持。
3. **單調放大**:overshoot 峰 = `1+g(peak−1)`,對 g 嚴格遞增 = 檔位簽章。

## 端到端接線

- `gen_animations.build_animations(skeleton, storyboard, tier_gains=None)`:`tier_gains={tier:g}`
  時,對每個主秀 beat 額外產出 `{beat}__{tier}` = `amplify_anim(base_beat, g)`;base beat 不變。
  `tier_gains=None`(預設)→ 逐位元同舊行為。
- `build_spine.py --animate --tier-variants`:依 genre 宣告檔位(`gains_for(genre)`)產變體。
  無宣告 tier 的 genre → `gains_for` 回 None → 不產變體。
- 變體名 `{beat}__{tier}` 經 `beat_category` 仍路由回原類別(主秀類別置前於 `_CAT_KEYWORDS`,
  `hit__legend` 先命中 `hit` 而非 `legend` 裡的 `end`)→ 不破壞產線既有路由。

## 驗收閘 `validate_tier_variants.py`(真實 robot 5 拆件,5 AC 全 PASS)

從**先驗庫**經 `analyze_target.build_storyboard` → **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains=…)`:

- **J1 present+routing**:每主秀 beat × 每檔位皆產出 `{beat}__{tier}` 且 finite/有 bone;
  變體名經 `beat_category` 仍路由回原類別;base(含 In/Loop/Out)逐位元不變。
- **J2 interface**:**每個檔位**——hit/combo/charge/cascade 首尾 bone 皆 setup identity;
  burst(reveal)尾 identity、首為 collapsed 樓地板(檔位無關)→ 皆可插 Loop 間。
- **J3 crux monotone**:**每主秀 beat**——scaleX overshoot 幅度與 rotate 幅度
  Super<Mega<Omg<Legend **嚴格遞增**(端到端經 build_animations 量)。實測:

  | beat | scaleX overshoot(Super→Legend) | rotate amp |
  |---|---|---|
  | burst | 0.350 → 0.473 → 0.595 → 0.735 | 30.0 → 63.0 |
  | hit | 0.348 → 0.470 → 0.592 → 0.732 | 17.9 → 37.6 |
  | combo | 0.347 → 0.469 → 0.591 → 0.730 | 17.8 → 37.5 |
  | charge | 0.347 → 0.469 → 0.590 → 0.729 | 18.0 → 37.8 |
  | cascade | 0.336 → 0.455 → 0.573 → 0.709 | 16.0 → 33.6 |

- **J4 signature kept**:**每個檔位**——combo 仍 ≥3 遞增 impact 峰、charge 仍長蓄力
  (squash 非 collapse)、hit 仍 anticipation+settle((scale−1) 變號 ≥3)、cascade 仍跨件
  峰時刻遞增散佈。(復用 `validate_more_beats`/`validate_cascade` 的判定器,判準一致。)
- **J5 neg-control**:(a) In/Loop/Out 不產變體;(b) 無宣告 tier 的 slot_reveal `gains_for`
  回 None → 不產變體且 base 相同;(c) **平增益守衛**——把階梯全設 1.0 → J3 單調性 FALSE
  (證閘真的在測遞增、非恆真),且 reveal collapsed 首幀 Super==Legend(下方樓地板檔位無關 → 誠實)。

**回歸全綠**:validate_priors / priors_beats(E)/ more_beats(0g)/ beat_templates(0f)/
cascade(0h)/ priors_combo_charge(H)/ priors_cascade(I)/ anim(+selftest)/
pivot_rotation(0i)/ scale_pivot(G-3)/ deform_gen(0e)/ round-trip validate_build
(含 `--tier-variants` build,setup pose 不受擾動)。

## 誠實界定

- 主秀運動仍**先驗手感**;增益階梯數值(1.0/1.35/1.70/2.10)是 **PROPOSAL**,閘驗**客觀
  結構性質**(單調、介面、簽章保持)非美感;確切幅度手感留使用者(A 類)。
- 蓄力深度/藏匿(下方樓地板)**刻意檔位無關** —— 那是結構語意,不是大獎強度。
- 單一真值資產(Award/robot);新增 cap `tier_variant_amplitude` L2 併入 `spine-anim-forge`
  (**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。

## 檔案

- `tools/analyzer/tier_variants.py` —— 增益階梯 + `amplify_bone_tl`/`amplify_anim`/`gains_for`。
- `tools/analyzer/gen_animations.py` —— `build_animations(..., tier_gains=)`(附加,向後相容)。
- `tools/analyzer/build_spine.py` —— `--tier-variants` 旗標。
- `tools/analyzer/validate_tier_variants.py` —— 5 AC 整合閘。
- 圖 `knowledge/figures/s1_tier_variants.png`(hit 每檔位包絡 / J3 幅度階梯 / combo 介面+簽章)。

## 續(擇一,皆自主)

- **(J-2) 連擊數隨檔位遞增**:讓高檔位 combo 的 impact 峰**數**增加(現只放大幅度),
  需 `gen_combo` 依檔位吃可變峰數,並加 AC 驗「Legend 峰數 > Super 且仍嚴格遞增」。
- **(J-3) cascade 波速/件數隨檔位**:高檔位散佈更大或波更快。
- **(G-1)** `--rig`×`--pivot-rotate`/`--scale-pivot` per-bone 語意去重;**(G-2)** 主秀 beat 下
  limb 繞關節 AC;**(G-4)** shear/非均勻 scale 仿射保形 AC。
