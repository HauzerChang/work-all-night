# S1 主秀 beat 接進 genre 先驗庫(candidate 0f→E,2026-09-04)

> 里程碑:把 candidate 0f 的**主秀 beat 模板**(hit/reveal,anticipation+settle)
> **接進已驗證的類型先驗庫**(`genre_priors.py`),使 `build_spine --animate` 對**真實 genre**
> 直接輸出主秀節拍簽章,而非只在 0f 的 fixture storyboard 才有。

## 問題(0f 之後的缺口)

candidate 0f 交付了兩個主秀模板(`beat_templates.gen_hit` / `gen_reveal`),並在
`gen_animations._DISPATCH` 註冊了 `hit`/`reveal` 兩個類別。但**觸發它們**只靠
`beat_category(name)` 的關鍵字命中:

- `slot_reveal` 恰好有 `open`(∈REVEAL_KEYWORDS)、`hit`(∈HIT_KEYWORDS)→ 自動命中主秀模板;
- **`slot_bigwin`(Award 大獎主角,主排程最核心 genre)beat 只有 `In`/`Loop`/`Out`** →
  `In` 被關鍵字歸為泛用 `intro`(`gen_in`:單峰、無反向預備、無阻尼回擺)。

即「大獎主角入場」這個**最該是主秀**的節拍,反而用最平淡的 intro 基元 → 主秀模板等於沒接上大獎流程。

## 做法:先驗庫明確宣告運動基元類別(`cat`)

不改關鍵字(關鍵字是 `validate_priors` 覆蓋率的判準,動了會破真值驗證),改在
**先驗 beat 上加一個可選欄位 `"cat"`**,明確宣告該節拍要驅動哪個運動基元
(`gen_animations._DISPATCH` 的 key)。這讓**已驗證的先驗庫**成為「節拍→主秀模板」的權威對映:

| genre | beat | 原(關鍵字回退)| 新(`cat` 明確宣告)|
|---|---|---|---|
| `slot_bigwin` | `In` | `intro`(gen_in 平淡入場)| **`reveal`**(現身式:藏→蓄勢→越過 identity overshoot→阻尼回穩)|
| `slot_reveal` | `open` | `reveal`(關鍵字恰中)| **`reveal`**(明確化,不再靠巧合)|
| `slot_reveal` | `hit` | `hit`(關鍵字恰中)| **`hit`**(明確化)|

其餘 beat(Loop/Out/comeout/static/idle/loop/close)不填 `cat`,維持關鍵字回退(向後相容)。

### 改動點(3 檔 + 1 常數)

- `genre_priors.py`:新增 `VALID_CATS`;3 個 beat 加 `"cat"`(見上表)+ docstring 說明。
- `analyze_target.build_storyboard`:把先驗 beat 的 `cat` 傳遞進 storyboard entry(有才帶)。
- `gen_animations.build_animations`:`cat = beat.get("cat")`;無效或未填才 `beat_category(name)` 回退。

**關鍵設計**:`cat` 只改**運動基元的選擇**,完全不動 beat 關鍵字 →
`validate_priors` 的覆蓋率(真值:真實動畫命名能否歸類)**不受任何影響**(實測仍 1.0/1.0)。

## 自我驗收:`validate_priors_beats.py`(5 AC 全 PASS)

端到端經 `analyze → build_animations`(對真實 `robot_parts.psd` 拆件+role),復用 0f 閘的
簽章度量(`series`/`sign_changes`/`_hit_signature`),確保「先驗接線」與「模板本身」用同一把尺。

| AC | 判準 | 結果 |
|---|---|---|
| **P1** wiring/coverage | 每個 beat 的 `cat`(若有)∈ VALID_CATS;兩支 validated genre 覆蓋率仍 == 1.0 | ✅ |
| **P2** bigwin In=reveal | `slot_bigwin` 的 `In` 每 bone 具 reveal 簽章(起 collapsed 0.02→峰 1.35→阻尼穿越≥2→尾 identity)| ✅ |
| **P3** reveal open/hit | `slot_reveal` `open` 具 reveal 簽章、`hit` 具 hit 簽章((scale-1) 變號≥3)| ✅ |
| **P4** chaining kept | 主秀 In/open **尾皆 setup identity**、Loop 首尾 identity → 仍可與 0d Loop/Out 無縫串接 | ✅ |
| **P5** discrimination | 剝除 `cat` → `In` 退回 `intro`(gen_in 單峰無阻尼)→ **FAIL** reveal 簽章;有 cat 版 PASS | ✅ |

**P5 是本閘的核心鑑別力**:證明「主秀簽章的來源就是這次的接線」——同一組拆件、同一 skeleton,
唯一差別是 storyboard beat 有沒有 `cat`;有 → reveal 主秀簽章,無 → 退回泛用 intro(無簽章)。
見圖 `figures/s1_priors_beats_wiring.png`(接線前後 `In` 的 body scale 包絡對比)。

## 回歸(未破壞既有)

- `validate_priors`:slot_bigwin/slot_reveal 覆蓋率仍 **1.0 / 1.0**(exit 0)。
- `validate_anim`(slot_bigwin,`--selftest`):AC1–AC4 + AC5 負對照全 PASS
  —— `In` 改 reveal 後仍滿足 AC4「In 尾 identity + 起始 collapsed + overshoot」契約(reveal 比 intro 更符合)。
- `validate_anim`(slot_reveal:robot_parts + Symbol_Ww):全 PASS。
- `validate_beat_templates`(0f)、`validate_deform_gen`(0e)、`validate_build`(靜態幾何):全 PASS。

## 誠實界定 / 下一步

- 主秀運動屬**先驗手感**(無唯一正解);本閘驗**客觀結構簽章 + 接線正確性**,非美感 → 緩動幅度手感留使用者(A 類)。
- `spine-anim-forge` 區塊仍 **HOLD**:運動基元為手感先驗、單一真值資產(防固化,達 L3 前不打包)。
  本次是**填補接線覆蓋**(讓已驗證 genre 直接吐主秀),非新演算法,不改變 HOLD 判定。
- 續充實候選:(F) 更多主秀節拍(anticipate-hold / multi-hit combo / cascade,各配結構簽章 AC);
  (G) S5 接觸縫 pivot 餵給 keyframe(件繞關節轉);未驗證先驗類型(slot_symbol/character_idle)待真值。
