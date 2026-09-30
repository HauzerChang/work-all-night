# S1 (J-4) cascade 跨件散佈隨檔位遞增 — 跨件時序通道的「連續」軸,補證 amplify 是值空間專屬

> candidate J-4 · 2026-09-30 run 001 · cap `cascade_tier_span_spread` L2(併入 `spine-anim-forge`,仍 HOLD)
> 閘:`tools/analyzer/validate_cascade_span.py`(5 AC 全 PASS)

## 補的 honest boundary

candidate (J) 讓 cascade 波峰**幅度**隨檔位放大(值空間軸);(J-3) 讓 cascade 波**掃過整體的次數** `nrip`
隨檔位遞增(跨件時序的**結構/拓樸**軸)。但跨件時序還有一條軸沒接:**各件錯開的「散佈」**——一道波掃過所有件時,
第一件到最後一件的**峰時刻間距**。本次補上 cascade 的**跨件散佈** `span` **隨檔位嚴格遞增**
(Super 0.54 → Mega 0.58 → Omg 0.62 → Legend 0.66,愈高檔位波掃愈開、各件錯開愈明顯)。

## crux:span 是「連續軸」卻仍須重生成 — 修正「連續軸=可事後 amplify」的直覺(本次核心新意)

到 (J-3) 為止,檔位差異化的軸可粗分兩型,似乎對應兩種實作:
- **結構(拓樸)軸**(nrip 波掃道數、combo/wobble/squash/twist 段數)→ 改**關鍵幀數/窗數** → 事後
  `amplify_bone_tl` 加不出一段 → 必須 **gen 時重生成**。
- **幅度(值)軸**(g)→ 改**峰高** → `amplify_bone_tl` 直接放大值欄位即可 → **事後 amplify**。

直覺會把「連續 vs 離散」對上「可 amplify vs 須重生成」。**J-4 的 span 打破這個對應**:

- span 是**連續軸**(像 g):它只改各件的峰**時刻**(第一件恆落 `LEAD`、最後一件落 `LEAD+span`),
  **關鍵幀數/拓樸完全不變**——不是加一道波,只是把同一道波掃得更開。看起來該像 g 一樣可事後 amplify。
- **但它仍必須 gen 時重生成**。原因:`amplify_bone_tl` 只放大**值**欄位(angle / x / y / scaleX / scaleY),
  **從不觸碰 time 欄位**;而 span 活在**時間軸**(峰時刻)。值空間的放大器動不到時間軸的量。

**結論(新發現)**:`amplify` 是**值空間專屬**變換。決定「可 amplify vs 須重生成」的**不是連續/離散**,
而是**這條軸活在值空間還是時間軸**:
- 值空間軸(峰高 g)→ 事後 amplify。
- 時間軸軸(不論**結構** nrip 改窗數、或**連續** span 改峰時刻)→ 一律 gen 時重生成。

於是 cascade 的跨件時序通道現有**兩條**軸(結構 nrip + 連續 span),都走重生成;加上值空間的幅度 g,
**三軸正交可疊**(nrip × span × g 互相獨立)。

## 生成:span 只縮放相位窗中心,拓樸不變

`gen_cascade(role, side, radial, phase, nrip=1, span=None)`:各件(相位 `p`)在第 k 道 sweep 的中心
`c_k = (k + LEAD + p·span)/nrip`。span 只出現在 `p·span` 這一項——p=0 的第一件恆落 `LEAD/nrip`(不受 span 影響)、
p=1 的最後一件落 `(k+LEAD+span)/nrip`,故**整體散佈 = span**(每道 sweep 內壓縮成 `span/nrip`)。

- **`span is None` → 用 `CASCADE_SPAN`(0.54)→ 逐位元同基礎 cascade**(向後相容 byte-identical)。
- **上界 `CASCADE_SPAN_MAX = 0.68`**:要保住「首尾 setup identity」介面,末件尾幀須仍在窗內 →
  `LEAD + span + 0.16 ≤ 1 ⇒ span ≤ 1−0.16−0.16 = 0.68`;取 Legend 0.66 < 0.68 留餘裕。clamp 至 `[0, 0.68]`。
- 拓樸(關鍵幀數)不變 → 與 nrip 的窗數軸、g 的峰高軸互不干擾。

## 路由(全 additive,三軸正交)

- `tier_variants.py`:新增 `TIER_CASCADE_SPAN={Super0.54,Mega0.58,Omg0.62,Legend0.66}` + `cascade_spans_for(genre)`。
  **Super 必須 == `beat_templates.CASCADE_SPAN`**(Y1 斷言此鎖定,否則 g=1 下 Super≠base)。
- `gen_animations.py`:`build_animations(tier_cascade_spans=)` 加 `_span_maps={"cascade": tier_cascade_spans}`;
  重生成條件從「cnt is not None」放寬為「**cnt 或 spn 非 None**」;`_build_beat(span=)` 把 span 傳入
  `_PHASE_AWARE` 分支(cascade)。span 不在任何非-cascade 路徑出現 → 不外洩。
- `build_spine.py`:`--tier-variants` 透傳 `cascade_spans_for` → 直出 `cascade__{Super,Mega,Omg,Legend}`
  (同時帶 nrip:各檔位 nrip 1→4 且 span 0.54→0.66,三軸端到端一起作用)。

## 驗收 `validate_cascade_span.py`(先驗庫 → 真實 build_spine robot 骨架 → build_animations)5 AC 全 PASS

- **Y1 present + backward-compat**:每檔位 `cascade__{tier}` finite/有 bone;base 逐位元不變、**Super 逐位元==base**;
  `tier_cascade_spans=None` 時 cascade 變體逐位元同 (J) 幅度-only → 加性 opt-in、對 (J)/(J-3) 零回歸;
  **且 Super 宣告 span == `CASCADE_SPAN`**(Super 鎖定=生成器預設)。
- **Y2 spread monotone(crux)**:各檔位測得跨件散佈 = **[0.542, 0.583, 0.621, 0.662] 嚴格遞增**且 ≈ 宣告 span
  (取樣容忍 3/N 內)。
- **Y3 signature + interface**:每檔位各件峰時刻依**真實件序嚴格遞增**且散佈 ≥ 0.6·CASCADE_SPAN(仍是有序跨件波);
  每件首尾 setup identity、特效 slot alpha 首尾=1(可插 Loop 間)。
- **Y4 orthogonality(3-way)**:
  (a) spans + 平增益 + 無 ripples → 散佈遞增 [0.54→0.66]、峰幅**不**遞增(恆 0.336)、波掃次數恆 1(**span ⊥ 幅度**);
  (b) spans + **固定 ripples(全 nrip=2)** + 平增益 → 波掃次數**恆 2**(span 不加波道)**且**每道 sweep 內散佈仍
  隨檔位遞增(Super 0.271 → Legend 0.329,= span/2 精確)(**span ⊥ nrip,crux**);
  (c) 僅增益(無 spans)→ 散佈**恆 CASCADE_SPAN**(0.5417,不隨檔位變)、峰幅遞增(**span 軸真為 opt-in**)。
- **Y5 negative control**:(a) 平散佈(全 CASCADE_SPAN)→ Y2 單調性 FALSE(證閘測遞增非恆真);
  (b) slot_reveal → `cascade_spans_for` None → 不產 span 變體(不亂加散佈);
  (c) span 只作用 cascade → 非-cascade 主秀 beat 檔位變體逐位元同幅度-only(不外洩)。

端到端 `build_spine --animate --tier-variants` 直出 `cascade__{Super,Mega,Omg,Legend}`;round-trip
`validate_build` overall_pass。**回歸 26 閘全綠**(25 既有 + 新 cascade_tier_span_spread;
`check_readiness.py` 退出 0,0 RED,無 GREEN→RED)。

## 關鍵發現

- **跨件時序通道至此有兩條軸:結構(nrip 波掃道數)+ 連續(span 跨件散佈)**;加上值空間的幅度(g),
  cascade 現由**三軸正交**驅動(nrip × span × g 各自獨立開關、可任意疊加)。
- **`amplify` 是值空間專屬變換** —— 決定一條軸「可事後 amplify vs 須 gen 時重生成」的,**不是它連續或離散,
  而是它活在值空間還是時間軸**:值空間(峰高)可 amplify;時間軸(峰時刻/窗數,不論連續 span 或結構 nrip)
  一律重生成。這修正了 (J-3) 給人的「重生成=因為改拓樸/離散」印象:span 是連續的、不改拓樸,照樣要重生成。

## honest boundary(仍在)

- 散佈階梯 [0.54, 0.58, 0.62, 0.66] 為 **PROPOSAL**(結構簽章客觀、波掃節奏手感留使用者 A 類)。
- 單一真值資產(robot_parts;防固化)。
- cap `cascade_tier_span_spread` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產)。
- 後續可補:cascade **波速**(窗速/加速掃)隨檔位——若以「等間距峰時刻 vs 漸變間距」表達,是 span 之外的另一條
  時間軸連續軸(峰時刻的**分布形狀**而非**總散佈**);或用**空間位置**(bd.x/徑向)決定波方向(左→右/中心外擴)。
