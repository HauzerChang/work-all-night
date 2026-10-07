# S1 — crossfade 接點重疊 xf 隨檔位差異化(candidate L-7)

> 把 L-6 的 crossfade 固定重疊 `xf=0.15` 接上**檔位軸**:高檔位接點重疊更多、beat 更連綿、總序列更緊湊。
> **本 run 的新位置 = 第一條落在「序列組合層」的檔位軸**。純 CPU、確定性、全 additive。

## 背景與缺口

- candidate (L-6) `crossfade_sequence` 以固定 `xf=0.15` 把 L-5 攤開的接點 C1 kink(純接續速度突變 15~114)消成 0
  (smoothstep 斜坡 w'兩端=0 → 閉式接點 kink 恆 0)。L-6 的 honest boundary 列出 `xf 多長`屬美術手感 + 可接
  tier。
- 既有**全部**檔位軸都在兩個層:
  - **per-beat 值生成**:幅度 g(`TIER_GAIN`)、combo/wobble/squash/twist/charge 段數(`TIER_*_CYCLES`)、
    cascade span(`TIER_CASCADE_SPAN`)。
  - **跨件相位**:cascade dir(`TIER_CASCADE_DIR`)。
- **缺口**:沒有一條檔位軸落在**序列組合層**(beat 與 beat 之間)。`xf`(接點重疊秒數)正是這一層的參數。

## 做了什麼(全 additive)

1. `tier_variants.TIER_CROSSFADE_XF`(genre→`{tier: xf}`)+ `crossfade_xf_for(genre)` 查表:
   `slot_bigwin = {Super:0.15, Mega:0.163, Omg:0.176, Legend:0.19}`,**嚴格遞增**,全 `< 最短 beat 時長 Out=0.4
   的一半 0.2`(Legend 0.19 餘裕 0.01 → `_crossfade_layout` 守衛不觸發)。base Super=0.15 == L-6 golden。
2. `gen_animations.tier_crossfade_sequence(anims, order, tier, genre, nsamp, ramp)` → 委派
   `crossfade_sequence(anims, order, xf=TIER_CROSSFADE_XF[genre][tier], ...)`;genre 未宣告 / 未知檔位 → ValueError。
3. 閘 `validate_crossfade_tier.py`(L-7,5 AC)從**先驗庫 → 真實 build_spine robot 骨架 → build_animations** 端到端,
   與 L-5 / L-6 同一 fixture(正向序列 In→hit→combo→charge→cascade→Loop→Out)。

## 5 AC(全 PASS)

- **T1 present + well-formed + base bitwise + guard**:四檔位 smoothstep 皆合法 Spine timeline(每通道時間嚴格
  遞增 / finite)、每檔位 xf < min_dur/2;**base Super 逐位元 == `crossfade_sequence(...,0.15,"smoothstep")`
  (L-6 golden)**。
- **T2 crux — xf 與總時長嚴格單調(佈局檔位軸)**:xf 嚴格遞增 `[0.15,0.163,0.176,0.19]`;總時長嚴格**遞減**
  `[5.5,5.422,5.344,5.26]`,各 == `Σdur−(m−1)·xf`(閉式);每接點重疊長 == 該檔位 xf。
- **T3 crux — 檔位(xf)軸 ⟂ C1(斜坡)性質**:**每個**檔位 smoothstep 接點閉式 kink 恆 0(≤1e-6)、
  `is_c1_crossfade_sequence`=True,對照純接續 `is_c1_continuous_sequence`=False;**負對照** 線性斜坡在**每個**
  檔位仍每接點 kink≥10、`is_c1_crossfade_sequence`(linear)=False。→ 壓縮接點(xf 檔位)**不會**重新引入
  kink;C1 來自斜坡的 `w'(0)=w'(1)=0`,與 xf 檔位**正交**。
- **T4 crux — 值增益動不到佈局軸(需重組合,呼應 J-4)**:`amplify_anim`(`TIER_GAIN` Legend g=2.1)套到每 beat
  → 每 beat 時長不變(只放大 bone **值**、不碰任一幀 `time`)→ 放大後以 Super xf 重 crossfade 總時長 == Super
  `5.5` **且 != Legend `5.26`**(Legend 需更大 xf **重新組合**)→ 值幅度檔位(`TIER_GAIN`)⟂ 佈局檔位
  (`TIER_CROSSFADE_XF`);放大後 smoothstep 接點 kink 仍 0 → 值增益亦 ⟂ C1。
- **T5 flat-xf 負對照 + body 忠實 + 守衛**:(a) 四檔位全用同一 xf(=Super)→ 總時長全相等、非嚴格遞減 → 證
  T2 的單調性是真 xf 驅動、非量測 artifact;(b) 每檔位 body 區 emitted vs 孤立 clip ≤ FAITH_TOL(0.05);
  (c) 未宣告 genre / 未知檔位 → ValueError。

## 關鍵發現

1. **檔位差異化至此落到三個層**:per-beat **值**(幅度 g)、per-beat **結構**(段數 nosc/nhits/ncharge/nrip)、
   **序列組合**(接點重疊 xf)。xf 是**第一條組合層**的檔位軸。
2. **佈局(xf)軸與值增益正交、需重組合**:`xf` 是**時間佈局**參數(beat 之間疊多少 → 總時長),`amplify_bone_tl`
   的值增益只碰值不碰時間 → 動不到。這與 **J-4(cascade span)同階**——「時間位置的幅度需重生成,非 post-hoc 值
   增益」——但 J-4 在 **beat 內**(sweep 窗),L-7 在 **beat 之間**(接點重疊)。
3. **tier 軸 ⟂ C1 性質**:smoothstep 的 `w'(0)=w'(1)=0` 使接點閉式 kink 與 `xf` **無關** → 無論哪個檔位把接點壓
   得多緊,接點 C1 kink 都 =0。把「接點多緊(xf 檔位)」與「接得多平順(斜坡 C1)」分成兩條正交可量測軸(再現
   本 repo 通則「真簽章常需兩獨立條件並立 / 量在哪一層決定看見哪種不變量」)。

## honest boundary

- **xf 隨檔位遞增 vs 遞減、各檔位 xf 的具體值**屬美術手感(A 類;高檔位該更連綿[本選擇]或更分明皆可辯)。
- 無改任何生成 / 產線值(全新查表 + 委派;base Super==L-6 golden 逐位元);單一真值資產(robot_parts)。
- 未接 `build_spine` CLI 旗標(L 系列 crossfade 都停在 gen/閘層,未進 build_spine `--animate` 產線;屬後續)。

## 檔案

- `tools/analyzer/tier_variants.py`:`TIER_CROSSFADE_XF` / `crossfade_xf_for`。
- `tools/analyzer/gen_animations.py`:`tier_crossfade_sequence`。
- `tools/analyzer/validate_crossfade_tier.py`:L-7 自我驗收閘(5 AC)。
- `tools/check_readiness.py`:新增 cap `crossfade_tier`(L2,併入 `spine-anim-forge`,仍 HOLD)。
