# S1 大獎序列組合(cross-beat composition)— candidate (L)

> 2026-10-04 run 001。把一整櫃獨立 beat clip **串接成單一可播放的大獎序列**,並以整合閘把關
> 「接點無縫 / 回切逐幀還原 / 簽章在序列脈絡中仍成立」。directly serves north star「產出大獎動畫」。

## 補的缺口(能力早在、AC 從缺 —— 同 G-2 整合閘精神)

- `gen_animations.build_animations` 產出的是**各自獨立**的 beat clip:`In/Loop/Out` + 主秀 beat
  (`hit/combo/charge/cascade/burst/wobble/squash/twist`)+ 檔位變體 `{beat}__{tier}`。每支 timeline
  時間都由 0 起;**設計上**靠「各 beat 首尾皆 setup identity」讓遊戲端在 runtime 依序播放達成無縫。
- 但**從未有閘**驗過:把這些 clip 真的**串接成單一 timeline** 時,(1) 接點真的 C0 無縫;(2) 串接
  不扭曲任何 beat 的值;(3) 各 beat 的結構簽章在**序列脈絡**中仍成立。這正是「X 就緒 ≠ 產線成立」
  通則(同 E/H/I/J…G-2)在**組合層**的實例。

## 選題理由(刻意不選「又一條參數軸」)

近期里程碑連續多是「單一 robot 資產加一軸」(tier / count / cascade-dir;J~J-7、charge count)。
本 run 刻意選**整合/組合閘**:價值在 (a) 證既有主秀 beat 真能**組裝成可播放大獎序列**(直指 north
star);(b) 抓回歸(接點契約、序列可組性);非再多一個手感 PROPOSAL。呼應 RULES「每能力必配評估器」
與 G-2 的選題精神。

## 實作(全 additive,無改既有生成/產線碼)

`gen_animations.compose_sequence(anims, order, gap=0.0, merge_tol=1e-6)` → `(composed, segments)`:
- 把第 i 個 beat 的所有關鍵幀時間平移 `offset_i = Σ_{j<i}(dur_j + gap)`,合併成**單一**連續 timeline。
- 接點時間重合(前一 beat 尾 == 後一 beat 首)→ **去重**接點幀以滿足 Spine「同通道時間嚴格遞增」。
- `segments = [{beat,start,dur}, …]` 供回切各段做 in-context 量測。
- 純時間平移 + 接點去重 **不改任何值**;`gap>0` 留空窗(不去重),供顯式製造不連續的負對照。

## 踩雷(預算內自修)— 接點去重的「無損方向」

初版去重**丟後者首幀**(`sh = sh[1:]`)→ **L3 回切殘差 7.09**(非無損!)。根因:**Spine 緩動
curve 掛在「起點幀」**(控制該幀 → 下一幀的內插)。後者首幀帶的是**進入後段**該有的 outgoing
curve;丟掉它、改用前者尾幀的 curve(屬前段、且前段尾幀的 outgoing curve 其實無意義)→ 後段首段
內插**用錯緩動** → 端點值對但中段值偏(b_光暈/b_身體 rotate/scale 差)。
**修法:改丟『前者尾幀』、保留後者首幀(連其 curve)** → 回切殘差 **0.00 逐幀還原**。
> 通則:接點去重的無損性取決於**保留帶「正確 outgoing curve」的那一幀**。緩動掛在起點幀,
> 去重方向錯會悄悄換掉後段的緩動,端點相等會掩蓋這個 bug —— 必須用「回切逐幀還原」而非只驗端點。

## 正向序列(PROPOSAL 排序;客觀不變量另驗)

`In → hit → combo → charge → cascade → Loop → Out`
- `In`:collapsed→identity(序列起手);`Out`:identity→collapsed(序列收尾)。
- 中段 `hit/combo/charge/cascade/Loop`:皆 identity→identity → **內部接點全 identity==identity → C0 無縫**。
- 排序本身是手感 A 類 PROPOSAL;但「接點殘差 / 回切還原 / 簽章保持」皆**客觀可量測**。

## 自我驗證 — `validate_sequence_compose.py` 5 AC 全 PASS(真實 robot 骨架)

從**先驗庫** → **真實 `build_spine` robot 骨架** → `build_animations` → `compose_sequence`,與 J/charge 同 fixture。
- **L1 well-formed+present**:合法 Spine timeline(每通道時間嚴格遞增、值 finite)・總時長 == Σ 各段時長
  ・segments 恰覆蓋宣告序列・序列用到的 bone 皆現身於 composed。
- **L2 crux 接點無縫**:正向序列每**內部接點**跨通道狀態殘差(前尾 vs 後首)= **0.0** < 1e-3(皆 identity==identity)。
- **L3 faithful concat**:回切每段(composed 在 `[start,start+dur]` 取樣)**逐幀還原**孤立 clip → 殘差 **0.00** < 1e-4。
- **L4 in-context 簽章**:從 **composed** 回切主秀段量測,簽章仍成立且 == 孤立 clip 量值 ——
  combo 遞增 impact 峰 ≥3、cascade 跨件散佈 ≥0.30、charge 峰前長蓄力。
- **L5 neg-control**:
  - **(a) crux**:`burst`(collapse 起手)插序列中段 → 其前接點(`hit->burst`)殘差 **30.0** >> 1e-3 →
    正確判**非無縫**、肇因接點確為 `*->burst` → 證 L2 有鑑別力;
  - **(b)** `Out`(collapse 收尾)插序列中段 → 其後接點(`Out->*`)殘差大 → 同;
  - **(c) composability 發現**:把主秀 beat(皆 identity 介面)彼此對調順序 → 所有內部接點仍 **0.0 無縫**
    **且**各段簽章仍成立 → 證 **identity-介面 beat 可自由排序**。

## 關鍵發現

1. **「各 beat 首尾 identity」≠「串起來真的無縫可播放」有 AC** —— 組合層最該放整合閘(再現
   「X 就緒 ≠ 產線成立」在 compose 上的實例)。
2. **接點去重的無損性取決於保留帶「正確 outgoing curve」的幀** —— Spine 緩動掛在起點幀,去重方向
   錯會悄悄換掉後段緩動;端點相等會掩蓋,必須以「回切逐幀還原」驗。
3. **identity-介面構成一個可自由排序的 beat 集合** —— 進出場(In/Out/burst 的 collapse 端)是**唯一**
   位置約束。這是一張 beat 可組性拓樸:自由層(identity↔identity)+ 起手/收尾層(collapse 端)。

## honest boundary

- beat **排序**是 PROPOSAL(手感 A 類);閘驗的是客觀組合不變量,非序列好不好看。
- shear beat(wobble/squash/twist)的 **shear 通道不被 `spine_anim.sample()` 覆蓋**(sample 只回
  rotate/x/y/scaleX/scaleY/alpha);正向序列採**無 shear** 的 hit/combo/charge/cascade。shear beat 的
  組合無縫(其 shear 端點亦為 0)可由原始端點比對另驗,為後續。
- 單一真值資產(robot)。`spine-anim-forge` 仍 **HOLD**(運動基元為手感先驗,未學自真值)。

相關:`knowledge/s1-pivot-main-show-integration.md`(G-2 整合閘)、`s1-cascade-beat.md`、`s1-more-beats.md`、
`s1-storyboard-to-animation.md`。
