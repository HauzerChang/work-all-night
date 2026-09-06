# S1 (I) — cascade 接進 genre 先驗庫(`build_spine --animate` 直出跨件錯開波)

> 里程碑 2026-09-06 session 002(claude/spine-main)。續 (E)/(H) 對 hit/reveal、combo/charge 所做,
> 把 candidate 0h 的 **cascade(跨件錯開波)** 主秀 beat 模板**接進 `genre_priors.py`**,讓
> `build_spine --animate --genre slot_bigwin` 直接輸出帶 **跨件** cascade 簽章的完整演出,
> 而非只在 0h 的手搭 fixture 裡驗模板。

## 動機 / 缺口

0h(`beat_templates.gen_cascade` + `validate_cascade.py`)驗的是**模板本身**:它用**手搭 fixture**
(自訂 bone 座標 `x=100+30i`、手寫 `{"beat":"cascade"}`)直接餵 `build_animations`。
但實際產線是 `build_spine --animate` → `analyze_target.build_storyboard(genre)` → `build_animations`,
storyboard 的 beat 集合**由 genre 先驗庫決定**。診斷:接 (I) 前 `slot_bigwin` 的先驗 beats 為
`In / burst / hit / combo / charge / Loop / Out` —— **沒有 cascade**,故 0h 的 cascade 模板對產線
**從未被觸發**,且從未在**真實 build_spine 骨架 + 真實件序**上驗過。這是「評估器/模板就緒 ≠ 生成器
接上」的**再一次再現**。

## 為什麼 cascade 比 (E)/(H) 多驗一層

hit/reveal(E)、combo/charge(H)都是**單件內**的時間簽章:同一 beat 套到每件、**每件時序相同**,
簽章看單件曲線就成立。cascade 是**跨件**時間簽章 —— 同一 beat 套每件,但每件依其**件序相位**
`phase = pi/(nvalid-1)` 錯開觸發成一道波(peak 時刻隨件序遞增)。這條相位由 `gen_animations` 的
`_PHASE_AWARE = {"cascade"}` 分支把件序帶進各件的 `gen_cascade(role, side_sign, radial, phase)`。
因此本整合閘不只證「beat 有流到 animations」,還證 **件序相位 threading 端到端存活**——
這在單件曲線裡看不出,只有各件峰時刻的**排序 + 散佈**看得出。

## 做法(additive,勿動已驗先驗)

`genre_priors.py` 的 `slot_bigwin` **新增一個主秀 beat**(不改任何既有 beat):
- `cascade` → `beat_category` 路由到 **cascade** 類別(`gen_cascade`):各件依件序 pop、峰時刻遞增成波。
- `kw` 用 `CASCADE_KEYWORDS`(cascade/wave/ripple/sequence/sweep/wipe/錯開/波/依序/接連),
  與 Award 真值 In/Loop/Out **不相交** → 覆蓋率單調保持 1.0,cascade 列 `prior_beats_unused`(誠實 PROPOSAL)。
- `_BIGWIN_ROLES["cascade"]` 給四角色(body/head/limb/effect)cascade 期的動作描述(給 rigger 起手)。

## 整合閘 `validate_priors_cascade.py`(5 AC 全 PASS)

從 **genre 先驗庫** 出發,經 `analyze_target.build_storyboard`(真實 robot 5 拆件 role + **真實件序**)
→ **真實 `build_spine` 骨架** → `build_animations`,驗 5 AC:

- **I1 present+routing**:cascade beat 經先驗→真實骨架→build 路由到 cascade 類別,每件真峰
  scale overshoot ≥ 1.12(光暈 1.336 / 身體 1.271 / 右手 1.177 / 頭 1.176 / 左手 1.18)。
- **I2 interface契約**:cascade clip 每件首尾皆 setup identity、特效 slot alpha 首尾=1(可插 Loop 間)。
- **I3 跨件 cascade 簽章(crux)**:各件峰時刻**依真實件序** `[0.158, 0.296, 0.429, 0.567, 0.70]`
  嚴格遞增、散佈 **0.542 ≥ 0.30**(has_cascade_signature),且**非** combo 簽章(單件單峰,證與 0g 正交)。
  → 件序相位端到端存活。
- **I4 coverage 保留**:validated genre 的 `validate_priors` 覆蓋率仍 1.0 pass(cascade 為
  prior_beats_unused,加 beat 單調,不擾動已驗先驗)。
- **I5 negative control**:(a) character_idle(無 cascade beat)產 0 cascade clip、無 clip 具跨件簽章;
  (b) slot_bigwin 的非 cascade beat 各件峰時刻不成波。

## 關鍵發現:跨件簽章需**兩條件並立**,散佈單獨不足

I5(b) 的負對照數據揭露一個**易被忽略的鑑別點**:

| beat | 各件峰時刻散佈 spread | 嚴格遞增? | cascade 簽章 |
|---|---|---|---|
| combo / charge / hit / burst / Out | ≈ 0.0 | — | ✗(近同時觸發,非波) |
| In | 0.20(< 0.30 門檻) | — | ✗ |
| **Loop** | **0.50(> 門檻!)** | **否** | **✗** |
| cascade | 0.542 | 是 | ✓ |

**Loop 的散佈 0.50 甚至比 cascade 的 0.542 只小一點**,若簽章只看散佈就會**假陽性**。原因:Loop 是各件
微呼吸循環,峰時刻**散但無序**(不隨件序遞增)。cascade 簽章同時要求「散佈 ≥ 門檻」**且**「依件序
嚴格遞增」→ Loop 因非遞增被正確排除。這印證 0h 的簽章設計(`has_cascade_signature = is_strictly_increasing
AND spread ≥ thr`)兩條件缺一不可;此處在**真實產線**上再現了該鑑別力,而非只在 0h 的手搭 fixture。

## 誠實界定

- 主秀運動無唯一正解(先驗手感),cascade 相位窗 `LEAD=0.16 / SPAN=0.54` 屬美術參數;閘驗**客觀結構
  簽章**(跨件遞增+散佈)+ 介面契約,非美感。峰值幅度依 role 不同(effect 最高),不影響峰**時刻**判定。
- 覆蓋率為單調操作:Award 真值僅 In/Loop/Out,cascade 誠實列 `prior_beats_unused`。
- 能力仍 **HOLD**:運動基元先驗、單一真值資產(Award robot),防固化。

## 產出

- `genre_priors.py`:`slot_bigwin` 加 `cascade` beat + `_BIGWIN_ROLES["cascade"]`。
- `tools/analyzer/validate_priors_cascade.py`:整合閘(5 AC)。
- 圖 `knowledge/figures/s1_cascade_priors.png`:先驗→真實件的各件 scale 曲線,峰時刻依件序錯開成波。
- cap `cascade_priors_integration` L2 併入 `spine-anim-forge`(仍 HOLD)。

## 回歸(全 PASS)

`validate_priors`(cov 1.0、unused 增列 cascade)、`validate_cascade`(0h)、`validate_priors_combo_charge`(H)、
`validate_priors_beats`(E)、`validate_more_beats`(0g)、`validate_beat_templates`(0f)、
`validate_anim`(+selftest)、`validate_pivot_rotation`(0i)、`validate_scale_pivot`(G-3)、
round-trip `validate_build`。
