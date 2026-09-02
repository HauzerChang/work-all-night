# S1 candidate 0g — 主秀 payoff 節拍「併入 genre 先驗庫」端到端(2026-09-02)

## 問題(0f 留下的端到端缺口)

candidate 0f 做了 `beat_templates.py`(`gen_hit`/`gen_reveal`,anticipation+settle),
`validate_beat_templates.py` 已驗過**模板本身的結構簽章**(6 AC PASS)。但那份閘用的是
**合成 storyboard**——直接塞 beat key `"hit"`/`"reveal"` 給 `build_animations`,驗的是「模板拿到
正確 beat key 時會不會動對」。

**它沒驗的是**:真實 genre 先驗會不會在 `analyze_target → build_storyboard → build_animations`
端到端**吐出主秀節拍**。實測(0g 前):

```
build_spine --animate --genre slot_bigwin  →  anims = [In, Loop, Out]   # 主秀 payoff 缺席!
```

`slot_bigwin` 先驗只有 In/Loop/Out 三 beat;`In`→`intro`(gen_in 簡單彈入,**無** anticipation/settle),
loop/out 亦非主秀。big-win 演出的**核心 payoff 瞬間**根本沒被生成。
(對照:`slot_reveal` 先驗有 `open`→reveal、`hit`→hit,端到端**本來就**會吐主秀節拍。)

## 做法(把 Hit payoff 節拍併入 slot_bigwin 先驗)

`genre_priors.py`:在 `slot_bigwin` 的 beats **In 與 Loop 之間**插入新 beat `Hit`:

```python
{"key": "Hit", "kw": ["hit","impact","punch","slam","throb","win","命中","重擊","衝擊","打擊"],
 "desc": "主秀重擊(payoff):蓄力→命中放大→阻尼回擺(anticipation+settle;首尾 identity 無縫)"},
```

並補 `_BIGWIN_ROLES["Hit"]`(body/head/limb/effect 動作描述,供人讀 storyboard)。

**為何選 Hit(而非 Reveal)當 big-win 主秀**:`gen_hit` 的介面是 **identity→peak→identity**
(首尾皆 setup identity),可**無縫夾在** In(尾 identity)與 Loop(首 identity)之間,補齊
「入場→**payoff 重擊**→待機」的完整演出。反觀 `gen_reveal` 首幀是 **collapsed(scale~0/alpha 0)**,
只能當「從無到有現身」的第一拍——接在已可見的 In 之後會 pop-to-invisible,破壞串接。故:
- big-win:In 已是「彈入現身」→ 主秀用 **Hit**(payoff 重擊夾在中間)。
- reveal(main_draw):物件本來藏著 → 主秀用 **open→reveal**(collapsed 起手),已存在。

`gen_animations` 端**無需改動**:0f 已把 `hit`/`reveal` 註冊進 `_DISPATCH`/`_CAT_KEYWORDS`;
`beat_category("Hit")`→`hit`→`gen_hit`。純先驗庫改動即接通端到端。

## 誠實界定(真值覆蓋)

Award(slot_bigwin 的 validated_against)真實動畫命名只有 `Award_<tier>_In/Loop/Out`——
**沒有**單獨的 hit/payoff 動畫,payoff 是**融進 `In` 動畫裡**的。所以新 `Hit` beat 在真值中
**無對應命名** → `validate_priors` 會把它列為 `prior_beats_unused: ["Hit"]`。這是**誠實的**:
- Hit 是**提案節拍**(把「入場+payoff」拆成兩拍的建議),不是觀測到的真值 beat。
- 它**不占**真值覆蓋率:Award 12 支仍全由 In/Loop/Out 覆蓋 → `slot_bigwin coverage 1.0` 不變。
- 「勿動已驗先驗」達成:In/Loop/Out 的 key/kw 一字未改,只**新增** Hit。

## 評估器 `validate_show_beat_wiring.py`(6 AC,全 PASS)

閘走**真實組裝路徑**(`build_spine.build --animate` 寫 skeleton.json 再讀回),非合成 storyboard。

| AC | 判準 | 結果 |
|---|---|---|
| **W1** emit_show_beat | slot_bigwin 端到端吐主秀類別 beat;序列 == In→Hit→Loop→Out | ✅ |
| **W2** signature | 吐出的 Hit 每 bone 具 hit 簽章(**復用 0f `_hit_signature`**:peak≥1.12+蓄力<0.99+變號≥3) | ✅ 5/5 bone(peak 1.18–1.35、pre-min 0.931、sc=4) |
| **W3** seamless_chain | In 尾/Hit 首尾/Loop 首尾/Out 首 皆 identity → 相鄰邊界位移=0 | ✅ max_disc 0.0 |
| **W4** truth_regression | `validate_priors` overall_pass True 且 slot_bigwin 覆蓋 1.0(Hit=unused) | ✅ |
| **W5** neg_control | (a) 對稱脈衝取代 Hit→簽章 False;(b) 先驗移除 Hit→端到端 0 主秀 beat(退回 In/Loop/Out) | ✅ |
| **W6** both_genres | slot_reveal 端到端仍吐 reveal(open)+hit(hit)兩主秀類別 | ✅ |

**負對照的鑑別力**:W5(b) 直接證明「主秀節拍出現 = 併入先驗」的因果——把 Hit 從先驗拿掉,
端到端立刻退回 `[In, Loop, Out]`(主秀消失)。W5(a) 沿用 0f 的「對稱脈衝無簽章」證閘不是
「有 scale peak 就算主秀」。

## 踩到的耦合:`validate_analyzer_award` check-4 過嚴(已修)

`check_readiness` 抓到一個**非預期回歸**:加 Hit 後 `validate_analyzer_award.py` 的
`4_storyboard_structure` 由 GREEN→RED(連帶 spine-asset-forge / spine-target-analysis 兩區塊變 HOLD)。
根因:check-4 原用**嚴格集合相等** `proposed_beats == {In,Loop,Out}`。那個 `==` 是「先驗剛好 3 拍」的
**特例**,其真正意圖(STATE:「分鏡 beats 全中」)是**分析器要復現 Award 每一個真實 beat**。

修法(非降門檻,是修正過嚴的等式):
- `recovered = {In,Loop,Out} ⊆ proposed`(準確度保證:不漏任何真值 beat)。
- `extra = proposed − observed`;**每個 extra 都必須是合法主秀類別**(`beat_category ∈ {hit,reveal}`),
  否則(隨機/幻覺 beat)仍 FAIL → **保留反捏造鑑別力**(實測 extra={wiggle} → beats_ok False)。

這與 validate_priors 的立場一致(extra 主秀節拍記 `unused`、不占覆蓋),兩閘現對「提案節拍」同調。

## 關鍵結論

- **主秀節拍是「先驗庫」層的事,不是「模板」層**:0f 把模板做好也驗好了,但先驗庫沒引用它 →
  端到端等於沒有。真正讓 `build --animate` 吐主秀的,是先驗 beat 表新增一拍。
- **介面契約(identity endpoints)決定哪個模板能插哪裡**:Hit(identity 兩端)可夾在序列中段;
  Reveal(collapsed 起手)只能當首拍。這是 0d 建立的「setup identity 介面」在主秀節拍上的推廣。
- 回歸:0d `validate_anim`(robot+`--selftest`+Symbol_Ww)、0e `validate_deform_gen`、
  0f `validate_beat_templates` 全 PASS(新增 Hit beat 不擾動既有 In/Loop/Out 介面)。

## 產出 / 下一步

- 新增:`tools/analyzer/validate_show_beat_wiring.py`、本檔。
- 更新:`tools/analyzer/genre_priors.py`(slot_bigwin +Hit beat、+role)、`tools/check_readiness.py`
  (cap `show_beat_wiring` L2)。
- cap `show_beat_wiring` L2;`spine-anim-forge` **仍 HOLD**(運動基元先驗、單一真值資產,防固化)。
- 下一小步候選:(F) 更多主秀節拍(anticipate-hold / multi-hit combo / cascade,各配結構簽章 AC);
  (G) S1(e) 關節 pivot 餵給 keyframe(件繞關節轉而非件中心)。
