# S1 (G-4''''') squash 接檔位幅度差異化 —— **體積守恆耦合放大**(擠壓隨檔位變強、面積恆守恆)

> candidate G-4'''''(2026-09-16)。補 G-4'''' 留下的 honest boundary:
> **「squash 未接 tier 幅度(`_amp_scale` 只放大 identity 上方 → 破壞體積守恆,需耦合 amplify)」**。

## 一句話

把 squash(斜拉果凍擠壓:shearX 阻尼擺 + 耦合體積守恆 scale)併入 `MAIN_SHOW_CATS`,並為它加一條
**體積守恆耦合放大** `_amp_scale_coupled`:放大時**保乘積 scaleX·scaleY 不變、只把非均勻比 scaleX/scaleY
以 g 次方放大**。⇒ squash 的**兩個耦合通道(shear 峰 + scale 擠壓非均勻)皆隨檔位嚴格遞增**,而
**面積守恆(scaleX·scaleY==1)在每個檔位精確保持**。

## 為什麼是這一步(補的 honest boundary)

- (J) `tier_variant_amplitude` 讓主秀 beat 依檔位幅度差異化,但增益 `_amp_scale` 只放大 identity **上方**
  overshoot(`v'=1+g(v−1)` 僅當 v≥1;v<1 樓地板不動)。
- squash 的 scale 是 **squash & stretch**:scaleX=1+q>1(拉長)、scaleY=1/(1+q)<1(壓扁),兩軸都動且
  **乘積==1**。用 `_amp_scale`:scaleX>1 被放大、scaleY<1 **樓地板不動** → 乘積 ≠ 1 → **體積守恆破壞**。
  故 G-4'''' 時 squash **不在** `MAIN_SHOW_CATS`(否則檔位一開就把它擠爆膨脹)。
- 本次(G-4'''''):加**耦合** amplify —— 兩軸一起以體積守恆方式放大,squash 得以隨檔位變強而不破壞面積。
  又一「檔位機制就緒 ≠ 每個新通道接上」實例(同 E/H/I/J/G-4'/''/''')。

## 耦合放大的機制(`tier_variants._amp_scale_coupled`,純代數,確定性)

把 (scaleX, scaleY) 分解為「幾何均值 m=√(sx·sy)」×「非均勻比 ratio=sx/sy」:

```
scaleX' = m · √(ratioᵍ)      scaleY' = m / √(ratioᵍ)
```

- **乘積精確守恆**:scaleX'·scaleY' = m² = sx·sy(**不因 g 漂移** —— 保留輸入的面積,squash 恆 ≈1)。
- **等比/identity 不變**:sx==sy → ratio==1 → ratioᵍ==1 → sx'==sy'(g 無關);(1,1) → (1,1)(介面契約)。
- **單調**:sx>sy(拉 X 壓 Y)→ ratioᵍ 隨 g 遞增 → scaleX' 遞增、scaleY' 遞減(擠壓隨檔位變強)。
- **g=1 逐位元不變**:m·√(sx/sy)=√(sx·sy)·√(sx/sy)=√(sx²)=sx(sy 同理)→ round 後 == 原值(向後相容)。

`amplify_bone_tl(b, g, coupled_scale)`:squash 傳 `coupled_scale=True` → scale 走耦合放大、shear 照 `g·v`
放大(對 0 對稱,同 wobble);其餘主秀 beat `coupled_scale=False` → 走通用 overshoot 放大(scale 等比)。
`build_animations` 依 `cat ∈ SCALE_COUPLED_CATS`({"squash"})帶入 coupled 旗標。

## 端到端量(build_spine robot 真實骨架,slot_bigwin 四檔位)

| tier | gain g | shear 峰 |shearX| | scale 非均勻峰 max|sX−sY| | 最差 |sX·sY−1| |
|---|---|---|---|---|
| Super | 1.00 | 16.0° | 0.298 | 4.8e-05 |
| Mega | 1.35 | 21.6° | 0.403 | 6.2e-05 |
| Omg | 1.70 | 27.2° | 0.510 | 7.0e-05 |
| Legend | 2.10 | 33.6° | 0.633 | 1.2e-04 |

兩通道皆嚴格遞增(Super==base 向後相容);體積守恆誤差全 < 1.2e-4 ≪ TOL_VOL(0.02)。

## 自驗閘 `validate_squash_tier.py`(先驗庫 → 真實 build_spine robot 骨架 → build_animations)

**5 AC 全 PASS**:

- **V1 present + backward-compat**:base squash 同時帶 shear(≥MIN_SHEAR)+非均勻 scale(≥MIN_ANISO);
  每檔位 `squash__{tier}` 皆產出/finite/有 bone/≥1 bone **同時**帶 shear 與 scale/路由回 squash;
  **base 逐位元不變**(帶/不帶 tier_gains)。
- **V2 crux — dual-channel monotone**:峰 |shearX| **與** scale 非均勻峰 max|scaleX−scaleY| **皆**
  Super<Mega<Omg<Legend 嚴格遞增,且 Super 兩者峰 == base(向後相容)。→ 兩耦合通道一起變強。
- **V3 crux — volume conserved**:**每檔位/每 bone/每 scale 關鍵幀** |scaleX·scaleY−1| ≤ TOL_VOL。
  → 耦合放大在**所有檔位**保持體積守恆(通用 overshoot 放大會在此崩,見 V5b)。
- **V4 signature kept per tier**:每檔位 squash bone 仍 (a) shearX 首尾 0 + 繞 0 變號 ≥3 + 相繼極值遞減
  (阻尼);(b) scale 首尾 (1,1);(c) squash 幅度 |scaleX−1| 隨極值嚴格遞減(耦合阻尼保形)。
- **V5 neg-control**:(a) **平增益守衛**:全 1.0 → V2 兩通道遞增皆 FALSE 且各檔位逐位元 == base;
  (b) **耦合必要性守衛(crux 誠實)**:對合成極值 (1.16, 0.8621) 施 g=2.1 —— 通用 `_amp_scale`
  乘積誤差 **0.152**(體積守恆**破壞**)vs 耦合 **0.0001**(守恆)→ 證體積判準有牙**且耦合放大是必要**;
  (c) **通道隔離**:`amplify_bone_tl(coupled_scale=True)` 對 scale-only bone 耦合放大守乘積、不生 shear;
  對 shear-only bone shear 放大 g·v、不生 scale。

## 關鍵發現

- **體積守恆量放大要在「乘積 × 比值」座標裡做,不能在單軸做**。單軸 overshoot 放大破壞守恆;把 scale
  分解成「面積 m² × 非均勻比 ratio」後,只放大 ratio、面積不動 → 守恆成為放大的**不變量**而非要驗的巧合。
  這是 (J) 增益哲學(對簽章保形的變換)在**耦合通道**上的推廣:(J) 保「符號序列/樓地板」、本次保「面積」。
- **雙軸差異化的兩軸是耦合的**:shear 峰與 scale 擠壓非均勻**同源同阻尼**(q_i 與 |shearX| 共用 r=0.5),
  故一個檔位增益 g 同時把兩者按各自的保形律放大 → 端到端仍是「同一個更強的斜拉擠壓」,非兩個獨立軸失步。
- **負對照直接展示「錯誤放大法會壞掉什麼」**(V5b),比只證「閘非恆真」更強:它證明**這條新機制是必要**
  (通用放大在此崩),而非可有可無的裝飾。同 (I) cascade「散佈且遞增」、(H) charge「長 hold 且 floor」的
  「兩條件並立才鎖定簽章」精神 —— 這裡是「放大且守恆」。

## Honest boundary(仍在,後續候選)

- **squash count-aware 仍未接**:擠壓/振盪**段數** `nosc` 隨檔位遞增(gen 時決定,比照 J-2 combo / G-4'''
  wobble)為獨立的**結構軸**差異化,`gen_squash(nosc=)` 參數已備、`SCALE_COUPLED_CATS` 已就緒,只差
  `tier_variants` 加 `TIER_SQUASH_CYCLES` + `build_animations` 依 cat 路由(同 wobble)。本次只做**幅度軸**。
- shearY≡0(斜拉只在 X);squash 形狀為 PROPOSAL(結構簽章客觀、手感留使用者 A 類)。
- 檔位增益階梯 [1.0,1.35,1.70,2.10] 沿用 (J) 的 `TIER_GAIN`(PROPOSAL)。

## 檔案 / 指令

- 放大:`tools/analyzer/tier_variants.py`(`_amp_scale_coupled`、`amplify_bone_tl(coupled_scale=)`、
  `SCALE_COUPLED_CATS={"squash"}`、`MAIN_SHOW_CATS` 加 squash)。
- 路由:`gen_animations.py`(`build_animations` 依 `cat∈SCALE_COUPLED_CATS` 帶 coupled 旗標)。
- 端到端:`build_spine.py --animate --shear-pivot --tier-variants`(直出 `squash__{Super,Mega,Omg,Legend}`)。
- 閘:`tools/analyzer/validate_squash_tier.py`(`python3 tools/analyzer/validate_squash_tier.py [--json]`,repo 根執行)。
- 回歸:18 閘全綠(原 16 + squash_gen + squash_tier)+ round-trip `validate_build` 對
  `--animate --shear-pivot --tier-variants` build overall_pass。**修**:`validate_tier_combo_count.py` K5(c)
  改以「full(gains+hits)vs amp_only(gains-only)同檔位比對」隔離 count 機制 —— squash 幅度隨檔位變強會令
  head 件 scaleX 擠壓峰跨越 IMPACT_PROM(1.10),原「非-combo beat 峰數跨檔位不變」判準會假陽性(那是幅度效應非
  count 外洩)。
- 圖:`knowledge/figures/s1_squash_tier.png`。
- 能力:cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
