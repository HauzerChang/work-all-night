# S1 (J-4) cascade 跨件波散佈幅度隨檔位遞增 — 跨件時序通道的「幅度式」軸

> candidate J-4 · 2026-09-30 run 001 · cap `cascade_tier_span` L2(併入 `spine-anim-forge`,仍 HOLD)
> 閘:`tools/analyzer/validate_cascade_span.py`(5 AC 全 PASS)

## 補的 honest boundary

(J-3) 讓 cascade 的**波掃次數** `nrip` 隨檔位遞增(掃**幾道**波 = 跨件時序通道的**結構/拓樸**軸)。
但一道 sweep 內**各件峰時刻的散佈**在所有檔位仍固定(base SPAN=0.54)——「掃幾道」有了、「一道掃多開」沒有。
本次補上 cascade 的**散佈幅度** `span`(第一件峰落 LEAD、最後一件峰落 LEAD+span)**隨檔位嚴格遞增**
(Super 0.54 → Mega 0.58 → Omg 0.62 → Legend 0.66):愈高檔位波掃**愈開**(跨件錯開愈戲劇)。

跨件時序通道至此有**兩條正交軸**:結構(nrip,J-3)× 幅度(span,J-4)。

## crux:「幅度」語意 ≠「幅度」機制(本次的核心新意 / honest distinction)

此前所有「幅度」軸(J 的主秀增益、wobble/squash/twist 的 tier 峰增益)都用 **post-hoc 值增益** `g`
(`v' = g·v`)實現——因為它們放大的是關鍵幀的**值**(scale overshoot、shear 角度)。

span 的語意也是「幅度」(愈大波掃愈開),照理應照搬 `g`。**但不能** —— 這是 J-4 揭示的分野:

- 跨件散佈活在關鍵幀的**時間位置**(峰中心 `c_k = (LEAD + p·span)/nrip`),**不在值**。
- post-hoc 值增益 `g` 只放大每件 pop 的**深度**(scale 峰值 overshoot),各件峰**時刻分毫不動** → 散佈不變。
- 故 span 雖語意屬幅度,**機制上必須在 gen 當下重生成**(同 count 軸),因為它是
  **time-position domain 的幅度**,而非 **value domain 的幅度**。

閘的 **Y5(b)** 直接證這一點:對 base cascade 施 post-hoc 值增益 `amplify`(g=2.1,J 的幅度機制)→
峰**深度** 0.336 → 0.708 確實變大(amplify 有作用、非空操作),但跨件**散佈** 0.5417 == 0.5417
**完全不變** → 證此軸無法由幅度機制產生、非重生成不可。

## 生成:span 決定一道 sweep 內各件峰的散佈

`gen_cascade(role, side, radial, phase, nrip=1, span=None)`:`span is None → CASCADE_SPAN`(0.54,base)
→ **逐位元同基礎**。給定 span → 各件在窗內中心 `c_k = (k + LEAD + p·span)/nrip`,故:

- **nrip=1(隔離量測)**:各件峰時刻 = `LEAD + p·span`(p=件序相位 0→1)→ 跨件散佈 == `span`。
  實測 [0.5417, 0.5833, 0.6208, 0.6625] ≈ 宣告 [0.54, 0.58, 0.62, 0.66](取樣誤差 ≤ 2/240)。
- **nrip>1(與結構軸疊加)**:每道 sweep 的散佈 = `span/nrip`(窗被壓縮 1/nrip)。故量測「span 加寬」須
  **固定 nrip** 比 span vs base(閘 Y4c):同 nrip 下 span[t]>0.54 者每道 sweep 更寬(如 Legend nrip=4:
  span 版 sweep0 散佈 0.1625 > base 版 0.1333)。
- **上界 `span < 1 − LEAD − 0.16 = 0.68`**:末件末幀 `(LEAD + span + 0.16)/nrip < 1`(任一 nrip 首尾仍
  identity、時間嚴格遞增)。Legend 0.66 < 0.68(餘裕 0.02)。

## 路由(全 additive,三軸正交可疊)

- `tier_variants.py`:新增 `TIER_CASCADE_SPAN={Super0.54,Mega0.58,Omg0.62,Legend0.66}` + `cascade_span_for(genre)`。
- `gen_animations.py`:`build_animations(tier_cascade_span=)` 對 cascade 變體以該檔位 span **重生成**;
  `_build_beat(cascade_span=)` 的 `_PHASE_AWARE` 分支把 span 透傳 gen_cascade(與 `count=nrip` 並存 →
  nrip 道各以該檔位 span 散佈,兩軸皆重生成、可同時帶入);再套單一-g 幅度增益(值深度軸)。
- `build_spine.py`:`--tier-variants` 讀 `cascade_span_for` 透傳 `tier_cascade_span`。
- **八個 tier_* 參數皆 None/False(預設)→ 逐位元同舊行為**(base cascade 恆單道波 span=0.54)。

## 自我驗收(`validate_cascade_span.py`,5 AC 全 PASS)

從**先驗庫**經 `analyze_target`(build_storyboard)→ **真實 build_spine robot 骨架** →
`build_animations(..., tier_gains, tier_cascade_span[, tier_cascade_ripples])`,與 (J)/(J-2)/(J-3) 同一 fixture。

- **Y1 present + backward-compat**:每檔位皆產 `cascade__{tier}` finite/有 bone;base cascade 逐位元不變;
  Super span-only(span=0.54=base、g=1.0)逐位元==base;`tier_cascade_span=None` 時 cascade 變體逐位元同
  (J) 幅度-only → 加性 opt-in、對 (J)/(J-3) 零回歸。
- **Y2 span monotone(crux,隔離量測 nrip=1)**:各檔位單道 sweep 跨件散佈 [0.5417,0.5833,0.6208,0.6625]
  嚴格遞增、== 宣告 span、Super==base;每檔位各件峰時刻仍依件序**嚴格遞增**(散佈變大不打亂波序)。
- **Y3 signature + interface**:每檔位仍具 cascade 簽章(跨件峰時刻遞增 + 散佈 ≥0.30);每件首尾 setup
  identity、特效 slot alpha 首尾=1(可插 Loop 間)。
- **Y4 orthogonality**:(a) span + **平增益**(全 1.0)→ 散佈遞增 [0.54..0.66]、深度**不**遞增(恆 0.3363);
  (b) gains + **無 span** → 散佈**恆==base**(0.5417×4)、深度遞增 [0.336..0.708] → 兩軸可獨立開關;
  (c) span ⟂ nrip:同時帶(nrip[t],span[t])→ 每件 pop 次數==nrip(不受 span 干擾)**且**固定 nrip 下
  span[t]>0.54 者每道 sweep 散佈更寬。
- **Y5 neg-control**:(a) 平 span(全 0.54)→ 散佈單調性 FALSE(證閘測遞增非恆真);
  (b) **crux honest-distinction** post-hoc 值增益 amplify(g=2.1)→ 深度 0.34→0.71 變大但散佈 0.5417==0.5417
  **不變** → 證 span 軸無法由幅度機制產生、非重生成不可;(c) slot_reveal `cascade_span_for` None 不亂加、
  span 只作用 cascade(非-cascade 主秀變體逐位元同幅度-only,不外洩)。

端到端 `build_spine --animate --tier-variants` 直出 `cascade__{Super,Mega,Omg,Legend}`(散佈隨檔位漸開)。

## 關鍵發現

1. **跨件時序通道有兩條正交軸**:結構(nrip=幾道波,J-3)× 幅度(span=一道多開,J-4)——與各單件通道的
   結構軸×幅度軸雙軸差異化同構,惟兩者皆落在「跨件時序」而非「單件曲線」。
2. **「幅度」未必用幅度機制**:當一個「幅度式」量活在關鍵幀的**時間位置**而非**值**時,post-hoc 值增益
   加不出來,必須**重生成**——這是 value domain 幅度(J/wobble/squash/twist 峰增益)與 time-position
   domain 幅度(span)的機制分野。span 語意像幅度、機制像 count。
3. Y5(b) 是本次的核心鑑別點:同一個 amplify 對深度有效、對散佈無效,乾淨證明軸的獨立性與重生成的必要性。

## honest boundary(仍在)

- 散佈階梯(0.54–0.66)為 **PROPOSAL**(手感 A 類,留使用者定);單一真值資產(防固化)。
- span 上界 0.68(結構限制:末件須在 [0,1] 內回 identity);若要更誇張的錯開需改變窗形設計(後續)。
- cap `cascade_tier_span` L2 併入 `spine-anim-forge`(仍 HOLD:運動基元先驗手感、單一真值資產,防固化)。

## 後續候選

- (J-5?) cascade **波方向**由空間位置決定(左→右 / 中心外擴,件序相位改由 bd.x/徑向而非件序);
- charge 蓄力段數 / 其他 count-aware 節拍;(G-1) rig×pivot per-bone 語意去重;(G-2) 主秀 beat 下 limb 繞關節 AC。
