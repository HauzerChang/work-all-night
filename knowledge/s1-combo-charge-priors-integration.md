# S1 (H) — combo/charge 接進 genre 先驗庫(`build_spine --animate` 直出連擊/蓄力)

> 里程碑 2026-09-06(claude/spine-main)。續 (E) 對 hit/reveal 所做,把 candidate 0g 的
> **combo(連擊)/ charge(蓄力充能)** 主秀 beat 模板**接進 `genre_priors.py`**,讓
> `build_spine --animate --genre slot_bigwin` 直接輸出帶 combo/charge 簽章的完整演出,
> 而非只在 0g 的合成 fixture 裡驗模板。

## 動機 / 缺口

0g(`beat_templates.gen_combo`/`gen_anticipate_hold` + `validate_more_beats.py`)驗的是**模板本身**:
它用**手寫合成 storyboard**(`{"beat":"combo"},{"beat":"charge"}`)直接餵 `build_animations`。
但實際產線是 `build_spine --animate` → `analyze_target.build_storyboard(genre)` → `build_animations`,
storyboard 的 beat 集合**由 genre 先驗庫決定**。診斷:接 (H) 前 `slot_bigwin` 的先驗 beats 為
`In / burst / hit / Loop / Out`(burst/hit 由 (E) 加入)—— **完全沒有 combo/charge**,故 0g 的
combo/charge 模板對產線**從未被觸發**。這是「評估器/模板就緒 ≠ 生成器接上」的**又一次再現**。

## 做法(additive,勿動已驗先驗)

`genre_priors.py` 的 `slot_bigwin` **新增兩個主秀 beat**(不改任何既有 beat):
- `combo` → `beat_category` 路由到 **combo** 類別(`gen_combo`):連擊,遞增 impact 峰 ≥3。
- `charge` → **charge** 類別(`gen_anticipate_hold`):蓄力充能,峰前長 hold。
- 同步加 `_BIGWIN_ROLES["combo"]`/`["charge"]` 描述(僅供 storyboard 文字,不影響生成)。

**路由機制**:beat key 本身就是 `beat_category(name)` 的輸入 —— `combo`∈`COMBO_KEYWORDS`、
`charge`∈`CHARGE_KEYWORDS`(見 `beat_templates.py` 檔尾),故 key 一命中就路由到對應類別。

**為何 coverage 不受影響**:`validate_priors` 覆蓋率 = 真實動畫名能否歸入**某** beat(單調非遞減:
加 beat 只多 keyword→beat 對映,不奪走既有匹配)。Award 真值動畫僅 `In/Loop/Out`(無 combo/charge
命名 token)→ 兩新 beat 於報告列為 `prior_beats_unused`(誠實 PROPOSAL,主秀運動無命名真值)。
`slot_bigwin` 覆蓋率仍 **1.0 / pass**;`prior_beats_unused` 由 `['burst','hit']` 變 `['burst','hit','combo','charge']`。

## 整合閘 `validate_priors_combo_charge.py`(5 AC,與 0g/(E) 閘互補)

**差別**:0g 驗合成模板;(E) 閘只涵蓋 hit/reveal;本閘從**先驗庫**經
`analyze_target.build_storyboard`(真實 robot 5 拆件 role)→ `build_animations`,證 combo/charge
**真的從先驗流到最終 animations**。度量(`series`/`impact_peaks`/`pre_peak_hold_frac`/
`has_combo_signature`/`has_charge_signature`)直接**復用 `validate_more_beats`**,確保判準一致。

| AC | 判準 | 結果 |
|---|---|---|
| H1 present+routing | 每宣告 combo/charge beat 的 validated genre,經先驗→build 的 clip 路由到 combo/charge 類別且真峰 ≥1.12 | ✅ combo 1.347 / charge 1.347 |
| H2 interface 契約 | combo/charge clip 首尾皆 setup identity(可插 Loop 循環間) | ✅ |
| H3 結構簽章 | combo clip `has_combo_signature`(遞增 impact 峰≥3);charge clip `has_charge_signature`(峰前長蓄力≥0.35);**兩簽章互斥** | ✅ combo 峰 [1.207,1.28,1.347]/charge holdfrac 0.456 |
| H4 coverage 保留 | validated genre `validate_priors` 覆蓋率仍 ==1.0 pass(combo/charge 為 prior_beats_unused) | ✅ 兩 genre 1.0 |
| H5 negative control | (a) 無 combo/charge beat 的 `character_idle` 產 0 combo/charge clip 且無 clip 具其簽章;(b) 主秀 genre 的非 combo/charge beat(In/Loop/Out/hit/reveal/burst)不得具 combo/charge 簽章 | ✅ |

## 關鍵發現:H5 逼出 charge vs reveal 的鑑別子(閘找出真實漏洞)

H5(b) 初跑 **FAIL**:`burst`(reveal 類別)被 `has_charge_signature` 誤判為 True。根因:
**charge 的 squash-hold 與 reveal 的 collapse-hold 峰前皆長時間低於 0.97** —— 原 charge 簽章只看
「峰前 <0.97 的時間佔比 ≥0.35」,無法區分「壓縮蓄力」(squash,~0.85)與「塌陷藏起」(collapse,~0.02)。

**修法(強化 `has_charge_signature`,`validate_more_beats.py`)**:加 **squash-floor** —— 峰前**最低**
scale 須 `> SQUASH_FLOOR(0.50)`。charge 壓到 ~0.85(>floor,squash)保持通過;reveal 塌到 ~0.02
(<floor,collapse)被正確排除。這是兩者本質差異的量化:**windup 是壓縮,不是消失**。
0g 閘(`validate_more_beats`)回歸仍 **6 AC 全 PASS**(gen_anticipate_hold squash 0.85 在 band 內)。

> 同型於 (E) 的 P5(b):(E) 閘假設「非 hit/reveal beat 皆無 hit 簽章」,但 combo/charge 依設計
> **共享** anticipation+settle 的 `_hit_signature`(0g M5),故 (E) 閘的負對照須把 combo/charge/cascade
> 也視為主秀類別排除(新增 `ALL_MAIN_SHOW_CATS`)。加 beat 到共享 genre → genre 級的閘須同步更新其
> 「主秀類別」定義,是加節拍的必然連帶(已一併修好)。

## 回歸(未破壞既有,全綠)

- `validate_priors.py`:overall_pass,兩 genre 覆蓋率 1.0;`slot_bigwin` unused=['burst','hit','combo','charge']。
- `validate_more_beats.py`(0g,含 squash-floor 強化):6 AC PASS。
- `validate_priors_beats.py`(E,含 `ALL_MAIN_SHOW_CATS` 更新):5 AC PASS。
- `validate_beat_templates.py`(0f)/`validate_cascade.py`(0h):PASS。
- `build_spine --animate --genre slot_bigwin`:animations = In/burst/hit/**combo**/**charge**/Loop/Out;
  `validate_anim`(+`--selftest`)PASS;round-trip `validate_build` PASS(setup pose 不變)。
- `--pivot-rotate` / `--scale-pivot` build + 0i/G-3 閘:PASS(apply_pivots 掃到新 beat 亦正常)。

## 誠實界定 / honest boundary

- 主秀運動仍是**先驗手感**(無唯一正解),閘驗**客觀結構簽章 + 介面契約 + 負對照**,非美感;
  連擊次數/蓄力時長/彈幅屬美術微調(A 類)留使用者。
- combo/charge 於 Award 無命名真值 → `prior_beats_unused`(PROPOSAL);單一真值資產。
- cap `combo_charge_priors_integration` L2(pipeline)併入 `spine-anim-forge`;區塊**仍 HOLD**
  (運動基元先驗、單一真值資產,防固化;達 L3/打包屬 C 類使用者拍板)。

## 產出檔案

- 更新:`tools/analyzer/genre_priors.py`(slot_bigwin +combo/+charge beat、`_BIGWIN_ROLES` +2 role)、
  `tools/analyzer/validate_more_beats.py`(`has_charge_signature` 加 squash-floor)、
  `tools/analyzer/validate_priors_beats.py`(`ALL_MAIN_SHOW_CATS` 負對照更新)、
  `tools/check_readiness.py`(cap `combo_charge_priors_integration`)。
- 新增:`tools/analyzer/validate_priors_combo_charge.py`、`knowledge/figures/s1_combo_charge_priors.png`、本 doc。

## 下一步候選

- (H 續)cascade 也接進先驗庫(如需跨件波直出)、或 combo/charge 的 tier 變體(Super/Mega/…各異幅)。
- (G-1) `--rig`×`--pivot-rotate`/`--scale-pivot` per-bone 語意去重;(G-2) 主秀 beat 下 limb 繞關節 AC;
  (G-4) shear / 非均勻 scale 仿射保形 AC。
- S5→L3 仍待 (D) 多 rig 真值(使用者資源)。
