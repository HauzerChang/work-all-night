# S1 (J-3) cascade 跨件波掃次數隨檔位遞增 — 第一個「跨件時序」通道的 count-aware

> candidate J-3 · 2026-09-29 run 002 · cap `cascade_tier_ripple_count` L2(併入 `spine-anim-forge`,仍 HOLD)
> 閘:`tools/analyzer/validate_cascade_count.py`(5 AC 全 PASS)

## 補的 honest boundary

candidate (J) 讓主秀 beat 依檔位**幅度**差異化(愈高檔位波峰愈爆),cascade 亦在其中。但**所有檔位的
cascade 仍是同一道跨件波** ——「掃得多猛」有了、「掃幾道」沒有。本次補上 cascade 的**波掃次數** `nrip`
(整體 ripple 掃過幾道)**隨檔位嚴格遞增**(Super 1 → Mega 2 → Omg 3 → Legend 4)。

## crux:跨件 count vs 單件 count(本次的核心新意)

結構(段數)軸此前已在**四個單件通道**成立:combo=scale 峰數、wobble=shearX 振盪段數、
squash=耦合擠壓段數、twist=反相雙軸扭轉段數。**這四者的 count 都是「單件內」的極值數**
(同一件連幾下,段數落在單件曲線的拓樸裡;`COUNT_AWARE_CATS`)。

cascade 不同:它是 `_PHASE_AWARE` 的**跨件時序**節拍(每件依件序相位 `p=pi/(nvalid−1)` 錯開觸發成一道
波),其簽章不在單件曲線而在**件之間**(各件峰時刻依件序排序+散佈)。所以 cascade 的「count」不是單件
連幾下,而是**跨件波掃過整體幾道** —— **第一個落在跨件時序通道的 count-aware 軸**。

因此跨件 count 的簽章要**多驗一層**(單件 count 沒有的):
1. **每件 pop `nrip` 次**(單件視角的峰數;同單件 count 的量法);
2. **每一道 sweep k 內,各件的第 k 峰時刻仍依件序嚴格遞增且散佈達標**(跨件排序在**每道**波都保住,
   不是把一道有序波切碎成 `nrip` 段雜訊)。

## 生成:整段 τ 均分 nrip 個壓縮 sweep 窗

`gen_cascade(role, side, radial, phase, nrip=1)`:把整段 τ∈[0,1] 均分成 `nrip` 個窗,第 k 窗(k=0..nrip−1)
是一次**壓縮版**跨件 sweep —— 該件在窗內中心 `c_k = (k + LEAD + p·SPAN)/nrip`(同一 phase → 每道 sweep
內各件仍依件序錯開),窗內包絡寬(dip/pop/settle 偏移)壓縮 `1/nrip`。

- **窗互不重疊**:`(c_{k+1}−0.09/n) − (c_k+0.16/n) = 0.75/n > 0`(對任一 n)→ 時間嚴格遞增、每件 pop
  之間回 identity → `nrip` 個乾淨可辨的 impact 峰(pop 峰值 = role peak ≥1.18 > IMPACT_PROM 1.10)。
- **首尾仍 identity**:首窗 `c_0−0.09/n=(LEAD−0.09+p·SPAN)/n ≥ 0.07/n > 0`、末窗
  `c_last+0.16/n = (n−0.14)/n < 1` → 可插 Loop 間(同基礎 cascade)。
- **`nrip==1` 逐位元同基礎單 sweep cascade**(w=1、單窗 → env/rotate/color 完全還原)→ 向後相容 byte-identical。
- **每道 sweep 內散佈 = SPAN/n**(Mega 0.271 / Omg 0.179 / Legend 0.133;實測 = 0.54/n 精確)。

## 路由(全 additive,與幅度軸正交)

- `tier_variants.py`:新增 `TIER_CASCADE_RIPPLES={Super1,Mega2,Omg3,Legend4}` + `cascade_ripples_for(genre)`。
  **不**併入 `COUNT_AWARE_CATS`(cascade 留在 `_PHASE_AWARE`);波掃次數自成一路階梯(各類別 count 階梯獨立)。
- `gen_animations.py`:`build_animations(tier_cascade_ripples=)` 把 cascade 併入 `_count_maps`;cmap 查詢改
  `_count_maps.get(cat)`(涵蓋單件段數 + cascade 波掃次數);`_build_beat` 的 `_PHASE_AWARE` 分支吃
  `count=nrip`(給定→帶入 gen_cascade,None→預設 nrip=1 golden)。
- **幅度 amplify 加不出第二道 sweep**(拓樸=gen 時決定的關鍵幀窗;事後 `amplify_bone_tl` 只能同比放大既有
  pop、不動時間軸)→ 對 cascade 檔位變體以該檔位 `nrip` **重生成**再套單一-g 幅度增益 → 波掃道數×幅度兩效
  **正交可疊**(比照 combo/wobble/squash/twist 的段數重生成)。
- `build_spine.py`:`--tier-variants` 透傳 `cascade_ripples_for` → 直出 `cascade__{Super,Mega,Omg,Legend}`。

## 驗收 `validate_cascade_count.py`(先驗庫 → 真實 build_spine robot 骨架 → build_animations)5 AC 全 PASS

- **X1 present + backward-compat**:每檔位 `cascade__{tier}` finite/有 bone;base cascade 恆 1 道逐位元不變、
  **Super 逐位元==base**;`tier_cascade_ripples=None` 時 cascade 變體逐位元同 (J) 幅度-only → 加性 opt-in、零回歸。
- **X2 ripple monotone(crux)**:各檔位每件 pop 次數 == 宣告 nrip = **[1,2,3,4] 嚴格遞增**、每檔位所有件一致(min==max==nrip)。
- **X3 per-sweep cross-part signature + interface(crux)**:每檔位**每一道 sweep k** 的各件第 k 峰時刻依**真實件序
  嚴格遞增**且散佈 ≥ 0.6·SPAN/nrip(每道波皆有序跨件波,非切碎);每件首尾 setup identity、特效 slot alpha 首尾=1;
  幅度峰仍隨檔位遞增(與 (J) 疊加不衝突)。
- **X4 orthogonality**:(a) ripples + 平增益 → 波掃次數仍遞增、峰幅**不**遞增(結構獨立於幅度);
  (b) gains + 無 ripples → 波掃次數**恆 1**、峰幅遞增 → 兩軸可獨立開關。
- **X5 negative control**:(a) 平波掃次數(全 1)→ X2 單調性 FALSE(證閘測遞增非恆真);
  (b) slot_reveal → `cascade_ripples_for` None → 不產 ripple 變體(不亂加波);
  (c) ripple 只作用 cascade → 非-cascade 主秀 beat 檔位變體逐位元同幅度-only(不外洩)。

端到端 `build_spine --animate --tier-variants` 直出 `cascade__{Super,Mega,Omg,Legend}`;round-trip
`validate_build` overall_pass(premult MAE 0.031)。**回歸 25 閘全綠**(24 既有 + 新 cascade_tier_ripple_count;
`check_readiness.py` 退出 0,0 RED,無 GREEN→RED)。

## 關鍵發現

- **結構(段數)軸已在 combo/wobble/squash/twist 四個單件通道 + cascade 跨件通道 成立**。
- **跨件 count 的簽章需比單件 count 多驗一層「每道 sweep 仍保跨件排序」** —— 單件 count 只需驗峰數;
  跨件 count 若只驗「每件 pop nrip 次」會漏掉「這 nrip 道波是否仍各自有序」(可能把一道有序波切成雜訊仍
  過峰數關)。故正確簽章 = 峰數==nrip **且** 逐 sweep 跨件遞增,兩層並立(呼應本專案反覆出現的「真簽章常需
  兩獨立條件並立」:cascade 散佈+遞增、squash 守恆+非均勻、twist 反相+雙軸)。
- **波掃道數是結構(gen 時窗)、幅度是事後 amplify** —— 同 combo/wobble 的「段數重生成 × 幅度增益」正交模式,
  在**跨件**通道再次成立。

## honest boundary(仍在)

- 波掃次數階梯 [1,2,3,4] 為 **PROPOSAL**(結構簽章客觀、手感節奏留使用者 A 類)。
- 單一真值資產(robot_parts;防固化)。
- cap `cascade_tier_ripple_count` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產)。
