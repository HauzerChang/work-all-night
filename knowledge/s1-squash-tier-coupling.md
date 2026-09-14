# S1 · squash 接檔位差異化:體積守恆耦合放大(candidate G-4''''')

> 里程碑 2026-09-14。補上 G-4''''(`gen_squash`)一路留到現在的 honest boundary:
> **「squash 未接 tier 幅度」**(斜拉果凍擠壓強度不隨大獎檔位遞增,唯獨它與其他主秀不一致)。
> cap:`squash_shear_scale_coupling` 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產)。

## 問題:普通幅度增益會破壞體積守恆

candidate (J) 的檔位幅度增益 `_amp_scale(v,g)=1+g·(v−1) if v≥1 else v` —— **只放大 identity 上方**
overshoot,下方(squash/collapse 樓地板)凍結。這對 hit/combo/charge(等比 scale,`scaleX==scaleY`)、
wobble(純 shear,`v'=g*v`)都正確。但 squash 的 scale 是**非均勻體積守恆**:

```
scaleX = 1 + q   (拉長軸 ≥ 1)      scaleX · scaleY ≡ 1   (面積守恆)
scaleY = 1/(1+q) (壓縮軸 ≤ 1)      scaleX ≠ scaleY       (非均勻=真擠壓)
```

對它施 `_amp_scale`:拉長軸 `scaleX>1` 被放大成 `1+g·q`,壓縮軸 `scaleY<1` **樓地板被凍結** →
`scaleX·scaleY = (1+g·q)/(1+q) ≠ 1` → **體積守恆被破壞**。這正是 (G-4'''') 當時把 squash 排除在
`MAIN_SHOW_CATS` 外的原因(honest boundary)。

**實測破壞量**(base squash → 舊獨立放大 g=2.0):各 bone 首極值 `|scaleX·scaleY − 1|` = **0.09–0.14**
(見 `validate_squash_tier.py` P6(b) 判別:遠大於 BREAK_VOL=0.01)。

## 解法:體積守恆耦合放大 `_amp_scale_coupled`

放大**拉長軸**的偏離量 q(以 `_amp_scale` 線性放大,與既有 scale 增益哲學一致、且與 shear 峰**同比 g**
耦合),再把**壓縮軸重算為拉長軸的倒數**:

```
拉長軸 = max(scaleX, scaleY)              # gen_squash 恆 scaleX≥1≥scaleY,但以 max/min 認定較穩健
sx' = round(_amp_scale(拉長軸, g), 4)     # = 1 + g·q(拉長量隨檔位線性遞增)
sy' = round(1 / sx', 4)                   # 壓縮軸重算 → scaleX'·scaleY' ≡ 1 精確保持
```

**關鍵性質**:
1. **體積守恆精確保持**:`sx'·sy' = sx'·(1/sx') = 1`(僅末位 round 誤差;實測全檔位 max `|積−1|` = **6e-5** « TOL_VOL=0.02)。
2. **非均勻保持**:`sx' ≠ 1/sx'`(q>0 時)→ 仍是真擠壓。
3. **identity 介面保形**:首尾 `sx==sy==1` → `_amp_scale(1,g)=1`、倒數=1 → 仍 (1,1)(可插 Loop)。
4. **base 逐位元向後相容**:g=1.0 → `_amp_scale(v,1)=v` 精確 → 拉長軸不變、壓縮軸=生成器原值 →
   `squash__Super == base squash` byte-identical。
5. **shear 通道照舊 `v'=g*v`**(同 wobble)→ **斜拉量(shear 峰)與擠壓量(squash q)同比 g 耦合遞增**,
   強度一致(檔位=更斜更擠,非別種運動)。

實測檔位階梯(role 特效):shear 峰 **16→21.6→27.2→33.6°**、squash 拉長量 **0.16→0.216→0.272→0.336**,
兩通道皆嚴格遞增(見 `knowledge/figures/s1_squash_tier.png`)。

## 端到端與正交性

- 併入 `tier_variants.MAIN_SHOW_CATS` + 新集合 `VOLUME_CONSERVE_CATS={"squash"}`;`build_animations`
  依 `cat ∈ VOLUME_CONSERVE_CATS` 對 squash 檔位變體改用 `amplify_anim_coupled`(其餘主秀仍用原 `amplify_anim`)。
- `build_spine --shear-pivot --tier-variants` 端到端:squash__{tier} 帶 pivot 補償(pivot 補償只加
  translate、不動 scale/shear → 體積守恆在 round-trip 後**存活**);有關節 pivot 的 bone(右手/頭/左手)
  在**放大後檔位**仍 pivot 殘差 <0.05px vs 負對照 9–44px → 一般仿射不動點在各檔位成立。
- squash **不是** count-aware(振盪/擠壓段數 nosc 隨檔位為後續 honest boundary,參數已備);
  幅度軸(本次)與段數軸正交,同 (G-4'') vs (G-4''') 對 wobble。

## 驗收閘 `validate_squash_tier.py`(6 AC 全 PASS)

- **P1** present + backward-compat + identity:squash__{tier} 皆產出/finite/dual-channel/路由回 squash;
  base 逐位元不變 + `squash__Super==base`;每檔位端點 identity。
- **P2** crux 耦合幅度遞增:峰 |shearX| **與** 峰 |scaleX−1| **皆** Super<Mega<Omg<Legend 嚴格遞增、Super==base。
- **P3** crux 體積守恆 per tier:復用 SQ3 判準,每檔位每極值幀 `scaleX·scaleY≈1` + 非均勻 + 阻尼遞減(max 誤差 6e-5)。
- **P4** shear 阻尼簽章 per tier:每檔位首尾 0 + 繞 0 變號 ≥3 + 相繼極值遞減。
- **P5** 端到端:build_spine round-trip 後各檔位體積守恆存活 + 有關節 bone pivot 不動(負對照 >20×)。
- **P6** 負對照:(a) 平增益守衛全 1.0→遞增 FALSE 且各檔位==base;(b) **耦合必要性判別**:舊獨立放大破壞守恆
  (|積−1| 0.09–0.14)、新耦合守恆(6e-5)→ 證耦合放大真在做事;(c) 非均勻 scale 隔離到 squash 及其變體。

## 連帶修正(誠實記錄)

`validate_tier_combo_count.py` K5(c) count-isolation 原用 `_min_peaks`(impact 峰**數**)當「非-combo beat
count 不外洩」的探針。squash 進 MAIN_SHOW_CATS 後,其阻尼多極值 scale 峰**隨檔位放大會跨越 impact 峰
prominence 門檻** → `_min_peaks(squash)` 各檔位 [0,1,1,1](非結構外洩,是幅度跨門檻的假陽性)。改用
**scale 關鍵幀數** `_min_scale_keyframes`(真正的結構量:只受 count-aware 重生成影響、不受幅度增益影響)→
squash 幀數各檔位恆定、combo 重生成才變 → 探針更貼合「count 外洩」本意。

## 關鍵發現

**「檔位機制就緒 ≠ 每個新通道接上」再一實例**(同 E/H/I/J/G-4'/G-4''/G-4'''):每加一種運動基元的新通道
(scale→shear→非均勻耦合 scale),檔位放大都要重新對「該通道的保形變換」設計。squash 的保形變換是
**體積守恆耦合**(log 面積 = `log sx + log sy = 0` 不變;本實作以「放大一軸、另一軸取倒數」達成,比
`sx^g, sy^g` 冪律更省 round 誤差且複用 `_amp_scale`),不是單純 `v'=g*v` 或 `1+g(v−1)`。
