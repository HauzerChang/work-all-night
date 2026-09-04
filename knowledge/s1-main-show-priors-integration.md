# S1 (E) — 主秀 beat 接進 genre 先驗庫(`build_spine --animate` 直出主秀節拍)

> 里程碑 2026-09-04(claude/spine-main)。把 candidate 0f 的 big-win 主秀 beat 模板
> (`gen_hit`/`gen_reveal`)**接進 `genre_priors.py`**,讓 `build_spine --animate --genre <g>`
> 直接輸出帶主秀簽章的完整演出,而非只在合成 fixture 裡驗模板。

## 動機 / 缺口

candidate 0f(`beat_templates.py` + `validate_beat_templates.py`)驗的是**模板本身**:它用
**手寫合成 storyboard**(`{"beat":"hit"},{"beat":"reveal"}`)直接餵 `build_animations`。
但實際產線是 `build_spine --animate` → `analyze_target.build_storyboard(genre)` → `build_animations`,
storyboard 的 beat 集合**由 genre 先驗庫決定**。診斷發現:

| genre | 先驗 beats | 主秀 clip(接 0f 前) |
|---|---|---|
| `slot_reveal` | static/idle/comeout/**open**/**hit**/loop/close | **已有** `open`→reveal(peak 1.35)、`hit`→hit(peak 1.34)(0f 註冊後自動路由) |
| `slot_bigwin` | In/Loop/Out | **無**(只有 gen_in 的入場 overshoot,無 anticipation/settle 主秀) |

即:**0f 的模板對 `slot_bigwin` 完全沒被觸發** —— 先驗庫沒有會路由到 hit/reveal 類別的 beat。

## 做法(additive,勿動已驗先驗)

`genre_priors.py` 的 `slot_bigwin` **新增兩個主秀 beat**(不改任何既有 beat):
- `burst` → `beat_category` 路由到 **reveal** 類別(`gen_reveal`):大獎「現身炸開」
  (collapsed→蓄勢 hold→overshoot→阻尼回擺,首 collapsed 尾 identity)。
- `hit` → **hit** 類別(`gen_hit`):慶祝期衝擊重音(anticipation→impact→settle,首尾 identity,可插 Loop 間)。
- 同步加 `_BIGWIN_ROLES["burst"]`/`["hit"]` 描述(僅供 storyboard 文字,不影響生成)。

**為何 coverage 不受影響**:`validate_priors` 覆蓋率 = 真實動畫名能否歸入**某** beat(單調非遞減:
加 beat 只會多 keyword→beat 對映,不會奪走既有匹配)。Award 真值動畫僅 `In/Loop/Out`
(無 hit/burst 命名 token)→ 兩新 beat 於報告列為 `prior_beats_unused`(誠實 PROPOSAL,主秀運動無命名真值)。
`slot_bigwin`/`slot_reveal` 覆蓋率仍 **1.0 / pass**。

## 整合閘 `validate_priors_beats.py`(5 AC,與 0f 閘互補)

**差別**:0f 驗合成模板;本閘從**先驗庫**經 `analyze_target.build_storyboard`(真實 robot 5 拆件+role)
→ `build_animations`,證主秀節拍**真的從先驗流到最終 animations**。

| AC | 判準 | 結果 |
|---|---|---|
| P1 main-show present | 每宣告主秀 beat 的 validated genre,經先驗→build 產出的 clip 路由到 hit/reveal 且真峰 scale ≥1.12 | ✅ bigwin: burst 1.35 / hit 1.348;reveal: open 1.35 / hit 1.348 |
| P2 介面契約 | reveal clip 首 collapsed(scale/alpha≤0.1)+尾 identity;hit clip 首尾皆 identity | ✅ |
| P3 結構簽章 | hit clip 具 `_hit_signature`(反向預備+阻尼回擺+真峰);reveal 首 collapse-hold + 峰後穿越 identity ≥2 | ✅(逐 bone) |
| P4 coverage 保留 | validated genre `validate_priors` 覆蓋率仍 ==1.0 pass(未擾動已驗先驗) | ✅ 兩 genre 1.0 |
| P5 negative control | (a) 無主秀 beat 的 `character_idle` 產 0 個 hit/reveal clip 且無 clip 具主秀簽章;(b) 主秀 genre 的非主秀 beat(In/Loop/idle/…)不得誤帶主秀簽章 | ✅ idle 0 clip;非主秀 clip 全 clean |

度量(`series`/`sign_changes`/`_hit_signature`)直接復用 `validate_beat_templates`,確保簽章判準一致。

## 回歸(未破壞既有)

- `validate_priors.py`:overall_pass,兩 genre 覆蓋率 1.0。
- `validate_anim.py`(robot slot_bigwin / Symbol_Ww slot_reveal)+ `--selftest`:全 PASS。
- `validate_beat_templates.py`(0f 合成模板 6 AC):PASS。
- `build_spine --animate --deform` 路徑:`validate_anim`(bone/slot)+ `validate_deform_gen.py` 7 AC:PASS。

## 關鍵發現 / 誠實界定

- **0f 模板要「被觸發」需先驗庫有對應 beat**:模板就緒 ≠ 產線會用它。`slot_reveal` 因命名恰好含
  `open`/`hit` 自動受惠;`slot_bigwin` 需顯式補 beat。這是「評估器/模板就緒 ≠ 生成器接上」的又一例。
- 主秀運動仍是**先驗手感**(無唯一正解),閘驗**客觀結構簽章 + 介面契約 + 負對照**,非美感;緩動幅度手感留使用者(A 類)。
- burst/hit 於 Award 無命名真值 → `prior_beats_unused`(PROPOSAL);單一真值資產。
- cap `main_show_priors_integration` L2(pipeline)併入 `spine-anim-forge`;區塊**仍 HOLD**
  (運動基元先驗、單一真值資產,防固化;達 L3/打包屬 C 類使用者拍板)。

## 產出檔案

- 更新:`tools/analyzer/genre_priors.py`(slot_bigwin +burst/+hit beat、`_BIGWIN_ROLES` +2 role)、
  `tools/check_readiness.py`(cap `main_show_priors_integration`)。
- 新增:`tools/analyzer/validate_priors_beats.py`、`knowledge/figures/s1_priors_beats.png`(本doc)。

## 下一步候選

- (F) 更多主秀節拍:anticipate-hold / multi-hit combo / cascade,各配結構簽章 AC。
- (G) S1 (e) 關節 pivot 接 keyframe(件繞 S5 接觸縫 pivot 轉而非件中心)。
- S5→L3 仍待 (D) 多 rig 真值(使用者資源)。
