# S1 — squash 擠壓強度隨檔位遞增(candidate G-4''''',`squash_tier_amplitude` L2)

> 2026-09-12。續 (G-4''''):(G-4'''') 的 `gen_squash` 是第一個同時產 `shear` + 非均勻 `scale`
> (體積守恆擠壓)的生成器,但當時**刻意不在** `MAIN_SHOW_CATS` —— 因為普通 `_amp_scale`
> 只放大 identity **上方** overshoot(scaleX>1 放大、scaleY<1 樓地板不動)會**破壞體積守恆**
> (scaleX·scaleY≠1)。本次補上 squash 的檔位差異化,用**耦合 amplify** 讓擠壓強度隨檔位遞增
> 而 `scaleX·scaleY==1` 精確保持。

## 缺口(honest boundary 的接續)

- **(G-4'''')** 誠實標記:「squash 未接 tier 幅度(`_amp_scale` 只放大 identity 上方 → 破壞體積守恆,
  需**耦合 amplify**,後續)」。
- 本次(G-4''''')正好照那條邊界接上:squash 的**擠壓非均勻**與 **shear 峰**同時隨檔位遞增,而**體積守恆
  逐檔精確保持**。

## 關鍵:體積守恆的檔位放大需「耦合 amplify」

squash 幀是體積守恆的:`scaleX=1+q`(拉長)、`scaleY=1/(1+q)`(壓扁)⇒ `scaleX·scaleY==1`。

- **普通 `_amp_scale`(非耦合)**:`v'=1+g(v−1)` 僅當 v≥1,v<1 樓地板不動。對 squash → scaleX 放大、
  scaleY **原地不動** → 積偏離 1(Legend g=2.1:1.16→1.336、0.8621 不動 → 積 **1.152**,守恆**破壞**)。
- **耦合 `_amp_scale_coupled`**:放大**拉長軸**(≥1 的那軸)以 `1+g(v−1)`,再把**壓縮軸設為其倒數**
  (`sy'=1/sx'`)→ 積 **恆 1**(Legend:1.336 → 0.7485,積 1.0000)。g=1 時 `sx'=sx`、`sy'=1/sx`
  (== 原生成器的 sy,因 sy 本即 1/sx)→ **逐位元向後相容**;identity 幀(1,1)任何 g → 仍 (1,1)。

雙軸一起放大(shear 走既有 `v'=g*v`、scale 走耦合)→ 檔位愈高「愈斜 + 愈擠」,而**面積不變、簽章保形**。

## 做了什麼(全 additive)

1. **`tier_variants.py`**:`squash` 併入 `MAIN_SHOW_CATS`;新增 `COUPLED_SCALE_CATS={"squash"}`;
   新增 `_amp_scale_coupled(sx, sy, g)`;`amplify_bone_tl(b, g, coupled_scale=False)` /
   `amplify_anim(anim, g, coupled_scale=False)` 加 `coupled_scale` 開關(True → scale 走耦合路徑)。
2. **`gen_animations.py`**:`build_animations` 對 `cat ∈ COUPLED_SCALE_CATS` 的主秀 beat 以
   `_amplify_anim(..., coupled_scale=True)` 產檔位變體(其餘節拍 `coupled_scale=False` 走普通 amplify)。
3. **`validate_squash_tier.py`**(新,5 AC),復用 `validate_squash_gen` 的 `_sq3_eval`/`_interior_scale`
   與 `validate_shear_gen` 的阻尼簽章判準。
4. **`validate_tier_combo_count.py`** K5c 由「數 impact 峰數」改為 **full vs amp_only 逐位元隔離**
   (原峰數判定對 squash 體積守恆 scale 會因幅度跨越 IMPACT_PROM 閾值而**誤報**;逐位元比對更強且不受閾值影響)。
5. **`check_readiness`** 新增 cap `squash_tier_amplitude` L2 併入 `spine-anim-forge`(仍 HOLD)。
6. 圖 `knowledge/figures/s1_squash_tier.png`(非均勻峰/shear 峰隨檔位遞增 + 耦合 vs 普通 amplify 的守恆對照)。

## 自我驗收(`validate_squash_tier.py`,5 AC 全 PASS)

從**先驗庫** → **真實 build_spine robot 骨架** → `build_animations(tier_gains)` 端到端量:

- **QT1 present + backward-compat**:每檔位 `squash__{tier}` finite/有 bone/≥1 bone **同時**帶 shear+scale;
  帶/不帶 tier_gains 的 base(非 `__`)beat 逐位元相同;**無 tier_gains → 不產任何 `squash__` 變體**。
- **QT2 crux — 擠壓非均勻單調**:峰 `max|scaleX−scaleY|` Super<Mega<Omg<Legend **嚴格遞增**
  (**0.298→0.394→0.486→0.588**);Super == base。
- **QT3 crux — 體積守恆逐檔保持**:**每檔位**每個內部極值幀 (a)`|scaleX·scaleY−1| ≤ 2e-2`(實測 ≤4e-5,
  **未被放大**);(b)至少一極值非均勻 ≥0.05;(c)squash 幅度 |scaleX−1| 隨極值嚴格遞減(阻尼耦合保形)。
- **QT4 shear 峰單調 + 阻尼**:峰 |shearX| 亦 **[16, 21.6, 27.2, 33.6]°** 嚴格遞增(shear+scale 兩通道
  一起放大);每檔位仍首尾 0 + 繞 0 變號 ≥3 + 相繼極值嚴格遞減。
- **QT5 負對照**:(a) 平增益全 1.0 → QT2 遞增 FALSE 且各檔位逐位元 == base;
  (b) **naive-amplify 守衛(crux)**:對同一 squash 幀施普通 `_amp_scale` → Legend |積−1|=**0.152**(>2e-2,
  守恆**破壞**),耦合 ≤4e-5(守恆保持)→ 證 QT3 非恆真、耦合 amplify 為**必要**(閘可信);
  (c) **耦合路由隔離**:build 的 `squash__{tier}` == `amplify_anim(base, g, coupled_scale=True)`
  且高檔位 != `coupled_scale=False`;非-squash 非-count-aware 主秀 beat 的 scale 壓縮軸(<1)樓地板
  **逐檔不變**(= 普通 amplify 未被耦合)→ 證耦合只路由給 squash。

**端到端**:`build_spine --animate --tier-variants --shear-pivot` 直出
`squash__{Super,Mega,Omg,Legend}`,`validate_build` round-trip **overall_pass**(premult MAE 0.031)。

## 關鍵發現 / 踩雷

- **結構軸×幅度軸雙軸差異化推廣到「耦合通道」**:(G-4''') 證了 count-aware 概念在 combo/wobble 兩通道成立;
  本次證了**幅度**檔位差異化在需要**跨通道守恆約束**的 squash 上也成立——關鍵不是「能不能放大」,而是
  「放大時保不保守恆」。耦合 amplify 就是把守恆約束帶進放大變換。
- **普通 amplify 的樓地板設計對 squash 反成 bug**:(J) 為 anticipation/collapse 語意特意「下方樓地板不動」,
  但 squash 的 scaleY<1 是**守恆的另一半**、不是樓地板;誤用會破壞守恆。→ 通道語意決定 amplify 策略,
  故需 `COUPLED_SCALE_CATS` 明確路由。
- **閘的可信度靠負對照 crux**:QT5b 用「普通 amplify 破守恆(0.15)vs 耦合保守恆(4e-5)」直接證 QT3
  不是恆真、耦合是必要,否則 QT3「守恆保持」對任何 amplify 都可能空過。
- **維護一致性:新主秀類別會踩到既有負對照的隱含假設**。squash 進 `MAIN_SHOW_CATS` 後,
  `tier_combo_count` K5c 的 impact-峰數 隔離判定對 squash 體積守恆 scale 誤報(幅度跨閾值 → 峰數隨檔位變);
  改逐位元隔離(combo_hits 不改任何非-combo beat)後更強且免疫閾值——同前次把 shear-isolation 抽成
  `SHEAR_CATS` 的維護模式。

## honest boundary(仍在)

- 非均勻峰階梯沿用 (J) 幅度增益 g=[1.0,1.35,1.70,2.10](**PROPOSAL**,擠多少才對味的手感留使用者 A 類)。
- 目前只產 **shearX**(shearY≡0);squash **count-aware**(擠壓段數 nosc 隨檔位,已備參數未接,比照 G-4''')為後續。
- 單一真值資產(robot_parts)、運動基元先驗 → `spine-anim-forge` 區塊**仍 HOLD**(防固化)。

## 下一步(擇一,皆純自主)

- **(G-4'''''')** 產 **shearY**(雙軸 shear)/ shear+scale+rotate 三通道同時的運動基元(塞滿一般仿射 M 全自由度)。
- squash **count-aware**(擠壓段數隨檔位,nosc 已備參數,比照 G-4''')。
- **(J-3)** cascade 波速/散佈/件數隨檔位(cascade 的第三種檔位軸)。
- **(G-1)** `--rig`×pivot 各 flag per-bone 語意去重;**(G-2)** 主秀 beat 下 limb 繞關節 AC。
- S5→L3 仍待 **(D) 多 rig 真值**(C/資源類,使用者提供)。
