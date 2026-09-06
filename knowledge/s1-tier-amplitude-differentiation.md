# S1 (J) — 檔位(tier)主秀幅度差異化(build --animate --tiers 直出 Super…Legend 遞增波)

- **結論**:`slot_bigwin` 一直宣告 tiers `[Super, Mega, Omg, Legend]`,但這只是 metadata ——
  分鏡→動畫(`build_animations`)對所有檔位產出**完全相同幅度**的主秀,「檔位」形同虛設。
  本能力把**檔位 gain 政策**(`genre_priors.tier_gains`,單調遞增)乘在主秀 overshoot(peak−1)上
  (`beat_templates._tier_peak`),讓 `build_spine --animate --tiers` 把主秀節拍(hit/reveal/combo/
  charge/cascade)**展開**成 `<Tier>_<beat>` 變體(`Super_hit`…`Legend_hit`),**幅度隨檔位單調遞增**
  (愈大獎主秀愈大),而**端點介面契約與 back-compat 完全不受影響**。
- **信心**:高。整合閘 `validate_priors_tiers.py`(從**先驗庫**經 `analyze_target.build_storyboard`
  → **真實 build_spine 骨架** → `build_animations(tiers=True)`)對真實 robot 5 拆件 **5 AC 全 PASS**。
- **相關**:S1 分鏡先驗庫(candidate E/H/I 主秀 beat 接進 genre 先驗)、candidate 0f/0g/0h 主秀 beat 模板。

## 缺口與定位

這是又一個本 repo 反覆出現的主題 **「模板 / metadata 就緒 ≠ 生成器接上」** 的實例:
`tiers` 欄位存在已久(且 `build_storyboard` 一路把 `tier_variants` 帶到規格),但**沒有任何一段生成
邏輯真的依檔位改變輸出**。本次補的就是「檔位 → 幅度」這條實際的生成連線,並用整合閘證明它端到端存活。

## 做法(一條 gain 貫穿,端點恆等不變式)

1. **gain 政策住在先驗庫**(檔位差異是**類型先驗知識**):`genre_priors.tier_gains(genre)` 回傳
   `{tier: gain}` 單調遞增,`gain_i = 1 + i*STEP`(`TIER_GAIN_STEP=0.2` → Super 1.0 / Mega 1.2 /
   Omg 1.4 / Legend 1.6)。**Super=1.0=base**,故 Super 變體與未分檔輸出一致。無 tiers 的類型回 None。
2. **放大只動峰值,端點恆等**:`beat_templates._tier_peak(base, intensity)=1 + intensity*(base−1)`。
   - **關鍵不變式**:對 identity(base==1.0)恆回 1.0 → **端點/介面與 intensity 無關保持**;
     collapsed(reveal 的 0.02)、anticipation/settle 常數、rotate/color 皆**不動** → 簽章乾淨。
   - 五個主秀產生器(`gen_hit/gen_reveal/gen_combo/gen_anticipate_hold/gen_cascade`)各加
     `intensity=1.0` 參數,只把 `peak` 換成 `_tier_peak(...)`。combo 的 p1/p2/p3 由 peak 導出 →
     三峰全隨檔位遞增;charge 釋放峰、cascade 各件 pop 峰亦然。
3. **產線接線**:`gen_animations.build_animations(skeleton, storyboard, tiers=False)`。
   `tiers=True` 且 storyboard 有 `tier_gains` 時,對 `_MAIN_SHOW_TIERED={hit,reveal,combo,charge,
   cascade}` 的 beat **依檔位展開**成 `<Tier>_<beat>`(intensity=該檔 gain);框架節拍
   (In/Loop/Out)檔位無關,單一產出。`build_spine --animate --tiers` 暴露之。
   - `_beat_timelines(...)` 抽出單 beat 具體化;cascade 仍走 `_PHASE_AWARE`(phase + intensity 併帶)。

## AC(整合閘 `validate_priors_tiers.py`,5 全 PASS)

- **T1 present+routing**:tiers=True → slot_bigwin 主秀展開 **4 檔 × 5 節拍 = 20 支** `<Tier>_<beat>`,
  各經 `beat_category` 路由回正確主秀類別、全域 scale 真峰 ≥1.12;框架節拍 In/Loop/Out 單一;
  且 **tiers=False 產出無任何檔位前綴名**。
- **T2 interface 保留(crux 之一)**:放大**不得**破壞介面 —— 每檔變體端點(t=0、t=dur:各 bone
  TRS + 特效 slot alpha)與 base(Super)端點**逐一相等**(intensity 只動內部峰值);且 base 尾端為
  setup identity + 特效 alpha=1(可流入 Loop)。
- **T3 單調放大(crux)**:每主秀節拍、每 bone,檔位 scale 峰值**嚴格遞增** Super<Mega<Omg<Legend;
  且 **Legend/Super overshoot 比 = 1.6 ≈ gain 比**(證 gain 真的套上、非任意數值);全域峰值亦嚴格遞增。
  實測(effect/halo bone):hit [1.348,1.418,1.488,1.558]、combo [1.347,1.417,1.486,1.556]、
  cascade [1.336,1.404,1.472,1.539] —— overshoot 0.348→0.418→0.488→0.558 恰 ×1.2/1.4/1.6。
- **T4 back-compat + 覆蓋率**:(a) `Super_<beat>`(tiers=True)與 `<beat>`(tiers=False)**逐位元一致**
  (Super gain=1.0,`_tier_peak(base,1.0)` 經 round(4) 與原字面值相等);框架節拍 tiers=True/False 一致;
  (b) validate_priors 覆蓋率仍 ==1.0(加 gain 政策不擾覆蓋,tier_gains 與 beat 覆蓋正交)。
- **T5 negative control**:(a) 無 tiers 的 genre(slot_reveal,tier_gains=None)即使 tiers=True 也**不**產
  檔位變體;(b) **等 gain**(全 1.0)令**任何 bone** 都無法通過嚴格遞增判準(證判準有鑑別力,非恆真);
  (c) 框架節拍 In/Loop/Out 即使 tiers=True 也不展開為檔位。

## 關鍵發現

- **「一條 gain + 端點恆等不變式」讓放大與介面正交**:因 `_tier_peak` 對 identity 恆回 1.0,
  「放大主秀幅度」與「保持可串接介面」不再互相牽制 —— 端點逐位元不變(T2)、Super 逐位元回退到未分檔
  (T4a),放大只發生在曲線內部。這與 0i/G-3 的「補償在 setup=identity 時為 0」是同一種設計手法:
  **把新自由度掛在一個對介面點恆為零的變換上**,即可自由加料而不動契約。
- **判準必須被負對照證偽**:T5(b) 用**等 gain** 重跑,顯示嚴格遞增判準在無差異時**確實失敗** ——
  否則「單調遞增全 PASS」可能只是判準恆真的假象。
- **gain STEP 是手感先驗(A 類),閘只驗結構性質**:閘證的是「**單調遞增**且**介面不破**」這客觀性質,
  不是特定倍率;倍率大小(0.2 STEP)屬使用者可調的主觀手感,誠實留白。

## 產出 / 檔案

- `tools/analyzer/beat_templates.py`(+`_tier_peak`,5 主秀產生器加 `intensity`)、
  `tools/analyzer/genre_priors.py`(+`TIER_GAIN_STEP`/`tier_gains`)、
  `tools/analyzer/analyze_target.py`(storyboard 帶 `tier_gains`)、
  `tools/analyzer/gen_animations.py`(`build_animations(tiers=)` + `_beat_timelines` + `_MAIN_SHOW_TIERED`)、
  `tools/analyzer/build_spine.py`(`--tiers` flag)、
  `tools/analyzer/validate_priors_tiers.py`(新,5 AC)、圖 `knowledge/figures/s1_tier_priors.png`。
- 新增 cap `tier_amplitude_differentiation` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、
  單一真值資產,防固化)。

## 邊界 / 待續

- `--tiers` 與 `--deform` 併用未特別整合:deform beat 以 base beat 名(如 `burst`)加 timeline,tiers 下
  bone 主秀為 `<Tier>_burst` → deform 不會落到同一 clip(latent,未驗;本閘不涉 deform)。
- 續(擇一,皆自主):(J-2) 讓**連擊數**也隨檔位遞增(Legend 4 連擊 vs Super 3)—— 需改 combo 包絡結構,
  簽章加「峰數隨檔位遞增」;(J-3) 檔位差異也套到 rotate/whip 幅度(現只放大 scale 峰);
  (G-1) `--rig`×`--pivot-rotate`/`--scale-pivot` per-bone 語意去重;(G-4) shear/非均勻 scale 仿形 AC。
