# S1 candidate 0g — 主秀 beat 併入 genre 先驗庫(顯式 cat 分派 + slot_bigwin Burst payoff)

> 里程碑 2026-09-03。把 candidate 0f 的主秀模板(hit/reveal)**真正接進 `build_spine --animate` 的生產路徑**。
> 工具:`genre_priors.py`(beat 加 `cat`)、`analyze_target.build_storyboard`(帶 cat)、
> `gen_animations.build_animations`(顯式 cat 優先分派)、`validate_mainshow_wiring.py`(6AC 端到端閘)。

## 問題(0f 的缺口)

candidate 0f 造了 big-win 主秀模板 `gen_hit` / `gen_reveal`,但只用 **`validate_beat_templates.py` 的手搭
storyboard**(beat 名硬寫 `"hit"`/`"reveal"`)驗過。真正的 `build_spine --animate` 走的是 **genre 先驗庫
(`genre_priors.PRIORS`)的 beats**,經 `analyze_target.build_storyboard` → `gen_animations.build_animations`:

- **`slot_bigwin` 先驗只有 In / Loop / Out** → `build_spine --animate --genre slot_bigwin` 端到端**沒有任何主秀 payoff 節拍**
  (In 只是 `gen_in` 溫和 overshoot 1.12,Loop 微呼吸)。大獎演出**缺高潮**。
- `slot_reveal` 先驗有 `open` / `hit`,但當時是**靠 beat 名關鍵字碰巧命中**(`gen_animations._CAT_KEYWORDS` 裡
  `open`∈intro 關鍵字、又∈ `REVEAL_KEYWORDS`;`hit`∈`HIT_KEYWORDS`),**脆弱**:換個 beat 名就錯位。

## 做法

### 1. 顯式 `cat`(運動類別)欄位 — 取代脆弱的 beat 名關鍵字猜測

`genre_priors.PRIORS[*]["beats"][*]` 新增可選 `"cat"`,直接宣告該 beat 要走哪個 `gen_animations._DISPATCH`
類別(`intro`/`loop`/`outro`/`hold`/`pulse`/`hit`/`reveal`)。串接:

- `analyze_target.build_storyboard`:把 `b.get("cat")` 帶進 storyboard beat entry(存在才帶,向後相容)。
- `gen_animations.build_animations`:`cat = beat.get("cat") or beat_category(name)`(**顯式優先,缺省才推斷**)。

宣告值:
- `slot_bigwin`:In=intro、**Burst=hit(新)**、Loop=loop、Out=outro。
- `slot_reveal`:static=hold、idle=loop、comeout=intro、**open=reveal**、**hit=hit**、loop=loop、close=outro。

### 2. `slot_bigwin` 加 **Burst(cat=hit)** payoff 節拍

- 位置:接在 **In 之後、Loop 之前**(In 入場 → Burst 主秀重擊 → Loop 待機 → Out 退場,構成完整演出)。
- 用 `gen_hit`(**首尾皆 identity**)→ 可無縫插在 In(尾 identity)與 Loop(首 identity)之間,也可插在 Loop 循環間當重音。
- **為何不用 reveal**:reveal 起於 collapsed(scale~0/alpha 0),適合當**第一個**入場節拍;Burst 是**中段** payoff,
  必須起於 identity(件已可見),故用 hit。**這正是需要顯式 cat 的原因**:beat 名 `"Burst"` 經 `beat_category`
  會命中 `'burst'∈REVEAL_KEYWORDS` → 誤判成 reveal(起 collapsed);顯式 `cat="hit"` 覆蓋之。

## 驗收 — `validate_mainshow_wiring.py`(走 build_spine --animate 相同路徑,6AC 全 PASS)

| AC | 內容 | 結果 |
|---|---|---|
| **M1 bigwin_payoff** | slot_bigwin 端到端產出「宣告 cat==hit」的 beat(Burst),且具主秀 hit 簽章(真峰≥1.12 + 反向預備 + (scale−1) 變號≥3) | ✅ Burst hit_signature=True |
| **M2 reveal_mainshow** | slot_reveal 產 open(reveal 簽章:起 collapsed→峰→峰後穿越≥2)+ hit(hit 簽章);皆對應 main_draw 真值 anim | ✅ |
| **M3 cat_drives_dispatch** | Burst 宣告 cat=hit → 起於 identity;拔掉 cat 走關鍵字('burst'→reveal)→ 起於 collapsed;兩路徑相異 | ✅ routes_differ=True |
| **M4 chainable_interface** | Burst(hit)首尾 identity;open(reveal)首 collapsed 尾 identity | ✅ |
| **M5 discriminative** | In/Loop/Out **不具**主秀 hit 簽章;stripped(拔 cat+Burst)先驗使 slot_bigwin **無任何 hit/reveal 類別 beat** | ✅ stripped_cats=[intro,loop,outro] |
| **M6 regression** | `validate_priors`(真值覆蓋)+ `validate_beat_templates`(模板簽章)仍 overall_pass | ✅ |

**回歸**:`validate_anim --selftest`(對 `build_spine --animate` 產物,現含 Burst)4AC + AC5 負對照全 PASS;
`validate_deform_gen` 7AC、`validate_build` round-trip、`validate_priors` 覆蓋率 1.0(兩 genre)皆 PASS。

## 關鍵發現 / 誠實界定

1. **顯式 cat > beat 名關鍵字**:M3 客觀證明——同一 beat 名 `"Burst"`,關鍵字路徑判成 reveal(起 collapsed,
   破壞中段插入),顯式 cat 判成 hit(起 identity,正確)。beat 名與運動類別**本該解耦**。
2. **鑑別力靠結構簽章、非單看 peak**:In/comeout 的**特效件** intro scale 也可達 1.25(接近 hit 峰),故不能只看
   峰值;`_hit_signature`(峰 + **反向預備 dip** + **(scale−1) 變號≥3 阻尼回擺**)才穩定分開主秀 hit 與一般入場
   (一般入場 0.02→峰→1 只有 **1 次**穿越 → FAIL)。
3. **honest boundary**:`slot_bigwin` 的真值 `Award` 只有 `{tier}_{In,Loop,Out}` 12 支——**payoff 收在 In 一支內、
   無獨立 anim**。故 Burst 是**可復用的主秀模板提案**,非 Award 觀測節拍:`validate_priors` 把它列 `prior_beats_unused`
   (資訊,非 fail),覆蓋率仍 1.0。相對地 `slot_reveal` 的 open/hit **有 main_draw 真值 anim 支撐**(已驗證主秀)。
4. 緩動幅度/手感仍屬美術(A 類),閘只驗**客觀結構簽章**。

## 連帶調整:`validate_analyzer_award.py` ④ 分鏡結構(exact-equal → subset)

slot_bigwin 加 Burst 後,分析器對 Award 提的分鏡 beats 變 `{In,Burst,Loop,Out}`,與 Award 觀測的
`{In,Loop,Out}` 不再**完全相等** → 原 `beats_ok = proposed == award` FAIL。此為**過嚴**:分析器本就該
「**重現 Award 全部觀測節拍** + 可另提**可復用主秀模板節拍**(Burst,Award 未獨立成 anim,payoff 收在 In 內)」。
故放寬為 **`covers_award = award ⊆ proposed`**(缺任一真值節拍仍 FAIL,鑑別力保留:實測 missing-Out→False),
並透明列 `extra_template_beats`。這是**真值語意的精修**(重現保真 + 透明額外提案),非為過閘而弱化——
額外 beats 皆來自 curated `genre_priors`(分析器不憑空造節拍)。放寬後 `validate_analyzer_award` 5 項全 PASS。

## 影響

`build_spine --animate --genre slot_bigwin` 現輸出 **In→Burst→Loop→Out** 的完整大獎演出(含主秀高潮);
主秀模板從「只在測試中存在」變成「生產路徑預設輸出」。cap `mainshow_wiring` L2 併入 `spine-anim-forge`
區塊(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
