# S1 — squash 擠壓段數隨檔位遞增(candidate G-4''''',`squash_count_generation` L2)

> 2026-09-16。續 (G-4''''):(G-4'''') 讓 `gen_squash`(斜拉果凍擠壓)成為第一個**同時產 shear + 非均勻
> scale**(體積守恆)的生成器,但各檔位仍是**同樣 4 段**擠壓 —— 有「擠多深」沒「擠幾下」。且 squash
> **不在** `MAIN_SHOW_CATS`(其 `scaleY<1` 壓扁樓地板會被 (J) 的 `_amp_scale` 保留、`scaleX>1` 被放大 →
> 破壞 `scaleX·scaleY==1` 體積守恆),故 (J) 的幅度差異化對 squash 是**已標記的 honest boundary**
> (需耦合 amplify)。本次**繞開幅度軸**先拿下**段數軸**:squash 的擠壓**段數** `nosc` 隨檔位嚴格遞增
> (Super 4 → Mega 5 → Omg 6 → Legend 7)。這是繼 (J-2) combo 連擊數、(G-4''') wobble 振盪段數之後,
> 第三個**結構(拓樸)軸**的檔位差異化。

## 缺口(honest boundary 的接續)

- **(G-4'''')** 誠實標記兩條 honest boundary:①「squash 未接 tier(需耦合 amplify:`_amp_scale` 只放大
  identity 上方會破壞守恆)」;②「count-aware nosc 已備參數未接」。
- 本次(G-4''''')接上**第②條**(count-aware 段數軸),而**刻意不碰第①條**(幅度軸)—— 因為段數軸
  **不需要動幅度**就能推進,且不動幅度正是**保住體積守恆**的關鍵。第①條(squash 幅度隨檔位)仍待後續。

## 關鍵:段數軸能在未解的幅度耦合前**獨立**推進

段數 = 關鍵幀**拓樸**(繞 0 交替變號的極值個數)。對 squash 以該檔位 `nosc` **重生成**整支 beat 即得
更多段;因為只是**多長幾個極值、每個極值仍用同一組體積守恆公式** `scaleX=1+q_i、scaleY=1/(1+q_i)`,
所以**每幀仍嚴格 `scaleX·scaleY≡1`**(面積守恆)。反觀幅度軸(把既有極值放大)才會踩到 `_amp_scale`
只放大 identity 上方 → 破壞守恆。故:

- **段數軸**(結構,gen 時決定,**本次接上**):`nosc` [4,5,6,7],**不套幅度增益**(g≡1.0)。
- **幅度軸**(事後 amplify,**仍 honest boundary**):需耦合 amplify 才能守恆,後續。
- **兩者可解耦**:段數軸拿下「不破壞守恆」的那一半;首極值幅度(shear 峰 16°、非均勻峰 0.298)
  **各檔位恆定 == base**(段數軸不動幅度 → 與未接的幅度軸互不干涉)。

這是本里程碑的**方法論收穫**:當一個能力被兩個軸(結構 × 幅度)差異化、而其中一軸卡在未解的耦合
(honest boundary)時,**另一軸若不依賴該耦合就能先獨立拿下**。squash 的檔位差異化因此先完成一半。

## 做了什麼(全 additive)

1. **`tier_variants.py`**:新增 `TIER_SQUASH_CYCLES = {slot_bigwin: {Super4,Mega5,Omg6,Legend7}}` +
   `squash_cycles_for(genre)`;把 `squash` 併入 `COUNT_AWARE_CATS`。**注意 squash 仍不在 MAIN_SHOW_CATS**
   (幅度 honest boundary 不變)。上界 7 同 wobble(共用 `DUR["squash"]==0.8s` 窗、`r=0.5` 阻尼):末擠壓
   `q_6=特效 Q0.16·r⁶=0.0025 → scaleX 1.0025 / scaleY 0.9975`,4 位小數可辨、`|scaleX·scaleY−1|<5e-5`。
2. **`gen_animations.build_animations(..., tier_squash_cycles=None)`**:新增分支處理「count-aware 但**不在**
   MAIN_SHOW_CATS」的類別(squash)——`elif cat in COUNT_AWARE_CATS and _count_maps.get(cat):` 對每檔位以
   該檔位 `nosc` **重生成**(`_build_beat(..., count=cnt)`)而**不套 `_amplify_anim`**。與 tier_gains 無關
   (即使給 tier_gains,squash 仍只走此段數軸,因不在 MAIN_SHOW)。`gen_squash`/`_squash_env` 早已支援
   任意 `nosc`(G-4'''' 已備),故生成器零改動。
3. **`build_spine.py`**:`--tier-variants` 時額外取 `squash_cycles_for(genre)` → `tier_squash_cycles`
   傳入 `build_animations`。
4. **`validate_squash_count.py`**(新)+ `check_readiness.py` 註冊 cap `squash_count_generation` L2。

## 驗收閘 `validate_squash_count.py`(先驗庫 → 真實 build_spine robot 骨架 → build_animations)

真值界定同 (G-4'/G-4''/G-4'''/G-4''''):主秀運動無唯一正解(PROPOSAL 手感),閘驗**客觀結構簽章非美感**。
**5 AC 全 PASS**:

- **V1 present + backward-compat**:每檔位 `squash__{tier}` 產出、finite、有 bone、**同時**帶 shear+scale
  雙通道;**base squash 恆 4 段逐位元不變**;`tier_squash_cycles=None` **完全不產** squash 變體(加性 opt-in);
  **`tier_gains` 單開亦不產** squash 變體(squash 不在 MAIN_SHOW_CATS → 幅度機制碰不到它)。
- **V2 crux — count monotone(雙通道耦合相等)**:各檔位擠壓段數由 **shear 與 scale 兩通道各自**量得,
  皆 == 宣告 [4,5,6,7]、皆嚴格遞增、**兩通道段數相等**(同一 `nosc` 耦合驅動 shear 與 scale)、Super==base。
- **V3 signature preserved**:每檔位仍 (a) shearX 首尾 0 + 繞 0 變號 ≥3 + 相繼極值嚴格遞減(阻尼);
  (b) **體積守恆耦合(crux)**:復用 (G-4'''') 的 `_sq3_eval` 判準 —— 每個 scale 極值幀 `scaleX·scaleY≈1`、
  至少一極值非均勻 `|scaleX−scaleY|≥0.05`、擠壓幅度隨極值嚴格遞減。**段數增多不破壞守恆**。
- **V4 no-amplitude(honest boundary)**:squash 變體**只走段數軸、不套幅度增益** —— 各檔位 shear 峰、
  非均勻峰皆**恆定 == base**(不隨檔位遞增,對照 wobble/combo 段數變體會再疊 (J) 幅度增益);
  且 tier_gains 單開仍零 squash 變體。此 AC **明確把「本次刻意不碰幅度」寫成可量測守衛**。
- **V5 neg-control**:(a) 平段數(全 4)→ 段數單調性 FALSE(閘可信);(b) 無宣告的 genre(slot_reveal)→
  `squash_cycles_for` 回 None → 不產段數變體;(c) 段數只作用 squash → 非-squash 主秀 beat 不因 `tsc` 產變體。

## 端到端 + 回歸

- `build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super4,Mega5,Omg6,Legend7}` 段;
  pivot 補償(一般仿射 `Δ=(M−I)(O−P)`,含 shear+非均勻 scale)後**段數仍 [4,5,6,7]**;
  round-trip `validate_build` **overall_pass**(premult MAE 0.031、setup 不變)。
- 回歸:`validate_squash_gen`(G-4'''')/`wobble_count`(G-4''')/`wobble_tier`(G-4'')/`tier_variants`(J)/
  `tier_combo_count`(J-2)/`shear_gen`(G-4')/全 priors/beat/pivot 系列 —— **18 閘全綠**。

## honest boundary(仍在)

- squash 的**幅度**差異化(shear 峰/擠壓峰隨檔位遞增)仍待**耦合 amplify**(scaleX/scaleY 一起以體積守恆
  放大,不破壞 `scaleX·scaleY==1`);squash 因此仍不在 `MAIN_SHOW_CATS`。段數階梯 [4,5,6,7] 為 PROPOSAL
  (手感留使用者 A 類);shearY≡0;單一真值資產。cap `squash_count_generation` L2 併入 `spine-anim-forge`(**仍 HOLD**)。
