# S1 (L-8) crossfade 序列軸整合進先驗庫 — prior-driven crossfade sequence

> candidate **L-8**(2026-10-07 run 002)。把 L-6/L-7 已驗的 **crossfade 序列軸整合進 `genre_priors`**,
> 如 (E)/(H)/(I) 把 beat 整合進先驗庫一樣。工具:`tools/analyzer/genre_priors.py`(+`sequence_recipe`)、
> 閘 `tools/analyzer/validate_sequence_crossfade_priors.py`。

## 補的缺口(L-7 的 honest boundary / 下一步)

candidate (L-6/L-7) 把序列接點 **crossfade** 機制做出來並一般化成 **per-junction**(逐接點 xf),
**但 `order` 與逐接點 `xf` 一直由各閘硬編**(`FORWARD`/`VEC`),從未像 (E)/(H)/(I) 把 beat 整合進先驗庫
那樣,把**播放序列配方**(播放哪些 beat、以何序、每接點混多久)整合進 `genre_priors`。本次把配方宣告進
`genre_priors.slot_bigwin["sequence"]`,並以 `genre_priors.sequence_recipe(prior)` 讀出,使**大獎 crossfade
序列可完全由先驗庫驅動** —— 從**先驗庫 → 真實 build_spine robot 骨架 → build_animations → (先驗配方)
→ crossfade_sequence** 端到端,不再靠閘硬編 order/xf。

## 做了什麼(全 additive)

`tools/analyzer/genre_priors.py`:
- `slot_bigwin` 加 `"sequence"` 欄位(**獨立命名空間**,不在 beat dict 內):
  - `order`:`["In","hit","combo","charge","cascade","Loop","Out"]`(beat key 播放序,可含重複鍵如 `Loop×N`)。
  - `crossfade_xf`:`[0.0, 0.15, 0.15, 0.15, 0.2, 0.3]`(**逐接點**重疊秒數;In→hit=0 保撞擊、Loop→Out=0.3 柔收尾)。
  - `ramp`:`"smoothstep"`。
- `sequence_recipe(prior)` → `{order, xf, ramp}`(全**新副本**,純函式);無 `sequence` 欄位 → `None`(零回歸)。
  讀取當下做結構校驗:order 非空、每 key ∈ 先驗 beat keys(**負對照:幻影 beat → ValueError**)、
  xf scalar 或長度==`len(order)-1`、每值有限 ≥0、ramp ∈ {smoothstep,smootherstep,linear};malformed → ValueError。

**無改任何生成 / 產線值**:crossfade 機制本身(L-6/L-7)完全沿用;本 cap 只加「先驗可宣告配方 + 讀出器」。

## crux(本 run 核心發現)

**先驗宣告的「播放順序 + 每接點混場秒數」(A 類手感)可被 L-7 的客觀機制如實逐接點落地。**
先驗把 In→hit 設 `xf=0`(保撞擊)、其餘接點 `xf>0`(平滑),經 `crossfade_sequence` 驅動後:
- In→hit 接點 kink **重現**為 L-5 瞬切極限 `seam_velocity_gap` = **114.35**(≥ SEAM_KINK_MIN),
- 其餘接點被 smoothstep 消成 **0**,
- `is_c1_crossfade_sequence(配方)` = **False**(留一瞬切即破全程 C1)。

即:**先驗只宣告要哪種手感,機制忠實落地** —— 把「選擇性平滑」從閘硬編上移到**先驗庫的可宣告配方**,
完成 L 系列從「機制(L-6)→一般化(L-7)→先驗整合(L-8)」的收束(對映 0g→(H)/0h→(I) 把節拍整合進先驗)。

## AC(5 條全 PASS)

`python3 tools/analyzer/validate_sequence_crossfade_priors.py` → OVERALL PASS。

- **R1 配方 present + well-formed + schema + 零回歸**:slot_bigwin 有 `sequence`;`sequence_recipe` 回
  `{order,xf,ramp}`(order key∈beats、xf scalar/長度==接點數 且有限≥0、ramp 合法);**additive**(`sequence`
  不在任何 beat dict、slot_reveal 配方 `None`);**純函式**(改動回傳不污染 PRIORS)。
- **R2 prior-driven 端到端 realizable**:recipe.order 每個 beat key 皆由該先驗自身 storyboard 經
  `build_animations` 產出;`crossfade_sequence(配方)` 產合法 Spine timeline(finite / 嚴格遞增)、
  總時長 **5.45** == Σdur − Σxf(= 6.4 − 0.95)。
- **R3 crux 選擇性平滑如實落地**:In→hit kink **114.35 重現 == L-5 c1_gap**(≥10)、其餘接點 kink≤1e-6、
  `is_c1`(配方)=False、把該 0 換成 XF「全平滑」覆寫 → `is_c1`=True(證破 C1 的正是先驗宣告保留的撞擊接點)。
- **R4 配方忠實 == 顯式 + body 忠實**:`crossfade_sequence(anims, recipe.order, recipe.xf, ramp)` **逐位元 ==**
  以同值顯式呼叫;body 區 emitted vs 孤立 clip **0.004**≤FAITH_TOL;junction kinks 配方==顯式 逐一相等。
- **R5 守衛 + 負對照 + vacuity**:malformed 配方(order 空 / 幻影 beat / xf 長度不符 / 負 xf / 未知 ramp)
  → `sequence_recipe` 於**讀取當下** ValueError;未宣告 sequence 的先驗 → `None`(非 error,零回歸);
  xf 全零配方 → `crossfade_sequence` 委派 `compose_sequence` 逐位元(無 crossfade)。

## 回歸

`python3 tools/check_readiness.py` → **0 RED**(新增 cap `sequence_crossfade_priors` GREEN,併入
`spine-anim-forge`,仍 HOLD)。`validate_priors.py` 覆蓋率仍 **1.0**(sequence 欄位 additive,不擾
`classify_anim` / beat 清單)。既有 L-6/L-7 crossfade 閘逐一 GREEN 證配方只是忠實宣告、不改機制。

## honest boundary(仍在)

- `order` / `xf` 取值仍屬**美術手感(A 類 PROPOSAL)**:本 cap 只把先驗宣告的**機制配方**取出並校驗,
  不替使用者決定取值(同 L-6/L-7)。閘只驗機制 threading / 零回歸 / 選擇性平滑如實落地,不驗美感。
- Award 真值僅 In/Loop/Out → 中段主秀 beat 同 `beats` 的 `prior_beats_unused`(誠實,覆蓋率不受擾)。
- **build_spine CLI 直出序列檔**(把 crossfaded 序列當單一 animation 寫進 skeleton.json)為後續;
  本 cap 的端到端在閘內驗(prior→build→crossfade),build_spine 尚未新增 `--sequence` 旗標。
- 單一真值資產(robot);cap `sequence_crossfade_priors` L2 併入 `spine-anim-forge`(仍 HOLD)。

## 下一步(候選,皆自主)

- **build_spine `--sequence`**:讀先驗配方,把 `crossfade_sequence` 的輸出當單一可載入 animation 寫進
  skeleton.json(真正端到端落地檔;配 round-trip `validate_build`)。
- **crossfade × tier**:高檔位更緊湊 / 更長接點混場(xf 隨檔位,比照 J;方向與基值為 A 類)。
- **非對稱單接點 crossfade**(左 xf≠右 xf):需把 `_crossfade_layout` 對稱重疊拆成前退 / 後進兩段
  (modeling 選擇較多,較不唯一)。
- **slot_reveal 也宣告 sequence 配方**(main_draw 真值,open 主秀柔收尾),把 L-8 推廣到第二 genre。
