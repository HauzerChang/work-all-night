# S1 (J-4) cascade 跨件波相位散佈寬隨檔位遞增 — cascade 的第三條檔位軸(純跨件時序散佈)

> candidate J-4 · 2026-09-29 run 003 · cap `cascade_tier_spread` L2(併入 `spine-anim-forge`,仍 HOLD)
> 閘:`tools/analyzer/validate_cascade_spread.py`(5 AC 全 PASS)

## 補的下一條軸

cascade 至此已有兩條檔位軸:
- **(J) 幅度**:波峰大小隨檔位放大(愈高檔位愈爆)。
- **(J-3) 波掃道數 nrip**:整體 ripple 掃過幾道隨檔位遞增(Super1→Legend4;跨件時序通道的「count」)。

本次補上第三條:**跨件散佈寬 span** —— 各件峰時刻散得多開(第一件峰在 LEAD、最後一件峰在 LEAD+span,
單一 sweep 內)—— **隨檔位嚴格遞增**(Super 0.54 → Mega 0.58 → Omg 0.62 → Legend 0.66)。
語意(A 類手感 PROPOSAL):檔位愈高 → 跨件亮相散得愈開(波掃過整體愈闊/慢,每件有更分明的先後時刻),
讀作「大獎的跨件亮相更鋪張、更有儀式感」。

## crux:cascade 第三條檔位軸 = 純「跨件時序的散佈」

三軸各自改的東西**互不重疊**,是本次的核心新意:

| 軸 | 改什麼 | 通道性質 | candidate |
|---|---|---|---|
| 幅度 g | 峰**大小** | 事後 amplify | J |
| nrip | 波掃**道數**(峰**數**) | 結構/拓樸(gen 時窗) | J-3 |
| **span** | 各件峰的**相對時刻**(散佈) | **連續時序參數**(gen 時相位) | **J-4** |

- span **不改峰數**(仍每件 pop nrip 次)、**不改峰幅**(仍 role peak)—— 只改各件峰**何時**發生的相對錯開。
- 與 nrip **正交**:同時開兩軸時,每道 sweep 的跨件散佈 = **span/nrip**;把 per-sweep 散佈 **×nrip** 即**還原 span**
  → span 軸可在任一 nrip 下獨立量得(SP4c)。
- 與幅度正交:span 是時序、g 是幅度,兩者作用在不同量上(SP4a/b)。

## 生成:一個連續 span 參數縮放跨件相位窗

`gen_cascade(role, side, radial, phase, nrip=1, span=None)`:各件第 k 道 sweep 中心
`c_k = (k + LEAD + phase·span)/nrip`。`phase = pi/(nvalid−1)`(件序相位)。

- `span is None` → 用模組常數 `CASCADE_SPAN`(=0.54)→ **逐位元同基礎 cascade / (J-3)**(向後相容 byte-identical)。
- span 愈大 → 相位 `phase·span` 拉得愈開 → 各件峰時刻散佈愈寬(=span,單 sweep;=span/nrip,每道 sweep)。
- **窗排 packing 上界 `span < 0.68`**:任一件(phase p)第 k 道尾點 =(k+LEAD+p·span+0.16)/nrip,最壞 p=1、k=nrip−1
  → (nrip−1+LEAD+span+0.16)/nrip < 1 ⇔ LEAD+span+0.16 < 1 ⇔ **span < 0.68**(與 nrip 無關;LEAD=0.16)。
  首點 (LEAD+p·span−0.09)/nrip > 0 恆成立;件內相鄰 sweep 間隙 0.75/nrip > 0 **與 span 無關**(span 只把該件
  所有 sweep **同步平移**,不改窗內結構)。→ Legend 0.66 仍留餘裕(0.66 < 0.68)。
- 錨定 **Super = 0.54 = CASCADE_SPAN** → 「Super 逐位元 == base」(同 J/J-2/J-3 各軸 base=Super 的向後相容契約)。

## 路由(全 additive;span 走**獨立**於 count 的路由)

- `tier_variants.py`:新增 `TIER_CASCADE_SPREAD={Super0.54,Mega0.58,Omg0.62,Legend0.66}` + `cascade_spread_for(genre)`。
- `gen_animations.py`:`build_animations(tier_cascade_spread=)`;**新增 `_span_maps={"cascade": tier_cascade_spread}`**
  (與 `_count_maps` 分開 —— span 是**連續時序參數**,非 count/拓樸,語意上不該與波掃道數混一路);
  `_build_beat(span=)` 的 `_PHASE_AWARE` 分支把 span 帶入 gen_cascade(kwargs:`count`→nrip、`span`→span,
  皆 None 則 golden byte-identical)。tier 迴圈:`cnt or spn 任一非 None` → 以該檔位參數**重生成** beat 再套幅度增益 g。
- `build_spine.py`:`--tier-variants` 透傳 `cascade_spread_for` → 直出 `cascade__{Super,Mega,Omg,Legend}`(散佈隨檔位遞增)。

## 驗收 `validate_cascade_spread.py`(先驗庫 → 真實 build_spine robot 骨架 → build_animations)5 AC 全 PASS

- **SP1 present + backward-compat**:每檔位 `cascade__{tier}` finite/有 bone;base cascade 逐位元不變、
  **Super 逐位元==base**(span=0.54);`tier_cascade_spread=None` 時 cascade 變體逐位元同 (J) 幅度-only → 加性 opt-in、對 (J)/(J-3) 零回歸。
- **SP2 spread monotone(crux)**:各檔位跨件散佈(單 sweep 各件峰時刻 max−min)= **[0.5417,0.5833,0.6208,0.6625]**
  嚴格遞增且 ≈ 宣告 [0.54,0.58,0.62,0.66](取樣誤差 ≤2/N 內);以 span-only(nrip=1)量。
- **SP3 orthogonal-signature + interface + amp mono(crux)**:每檔位各件峰時刻仍依**真實件序嚴格遞增**
  (散佈變寬仍是有序跨件波,非切碎/亂序);每件 pop 次數**恆 1**(散佈非道數);每件首尾 setup identity、
  特效 slot alpha 首尾=1(可插 Loop 間);幅度峰仍隨檔位遞增(span 與 (J) 幅度軸疊加不衝突)。
- **SP4 orthogonality(3-way)**:(a) spread + 平增益 → 散佈遞增、峰幅**不**遞增;(b) gains + 無 spread → 散佈
  **恆=base**(不隨檔位變)、峰幅遞增;(c) **crux** spread × ripples 同時開 → pop 次數==nrip [1,2,3,4] **且**
  還原 span(per-sweep 散佈×nrip)嚴格遞增 ≈ 宣告(容差 2·nrip/N)→ 散佈/道數兩軸互不干擾、可疊。
- **SP5 negative control**:(a) 平散佈寬(全 0.54)→ SP2 單調性 FALSE(證閘測遞增非恆真);
  (b) slot_reveal → `cascade_spread_for` None → 不產 spread 變體(cascade 變體逐位元同幅度-only);
  (c) span 只作用 cascade → 非-cascade 主秀 beat 檔位變體逐位元同幅度-only(不外洩)。

## 關鍵發現

- **cascade 三軸(幅度 J / 波掃道數 J-3 / 散佈寬 J-4)全數正交成立**;**跨件時序通道自身已長出兩條獨立子軸**:
  「道數(count / 拓樸)」與「散佈(連續時序)」。這是首次在同一通道內把「多幾道」與「散多開」分成兩把獨立旋鈕。
- **連續時序參數走獨立於 count 的路由(`_span_maps`)** —— 沿用 J-3 的 `_count_maps` 會把「連續散佈」與「離散道數」
  混為一軸,語意錯誤且無法各自開關。分路由後兩軸乾淨正交(SP4c 的「還原 span = per-sweep 散佈×nrip」即為此正交性
  的量化證據)。
- **量化誤差隨 ×nrip 放大** —— 還原 span 用 per-sweep 散佈×nrip,取樣量化(每端 ≤1/N)被 nrip 放大 → 容差須
  取 2·nrip/N(非固定 2/N),否則高檔位(nrip 大)誤判 fail。這是「複合量測的容差要跟著複合因子縮放」的一例。

## honest boundary(仍在)

- 散佈寬階梯 [0.54,0.58,0.62,0.66] 為 **PROPOSAL**(結構簽章客觀;方向 = 遞增=波掃愈闊,**反向**(遞減=波掃愈快/
  愈同步)為對等替代,手感節奏留使用者 A 類拍板)。
- 單一真值資產(robot_parts;防固化)。
- cap `cascade_tier_spread` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產)。
