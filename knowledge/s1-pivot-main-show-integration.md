# S1 (G-2) 主秀節拍下 limb 繞關節 pivot 旋轉+縮放 — 整合閘

> 結論:**真實產線直出的主秀節拍(hit/combo/charge/burst/cascade)下,limb 確實繞「S5 推得的關節 pivot」
> 旋轉+縮放,而非繞件中心** —— 端到端(genre 先驗庫 → `build_spine --animate --scale-pivot` robot 骨架 →
> `apply_pivots` 在 build 內實跑)量化驗證,5 AC 全 PASS。
> 依據:`tools/analyzer/validate_pivot_main_show.py`(純 CPU,對真實 robot 拆件幾何 + `infer_pivots` 推得關節)。
> 信心:高(客觀幾何不動點殘差 + 負對照 147× 分離 + 轉換集合精確性)。相關階段:S1(keyframe)× S5(rig pivot)整合。

## 這是什麼(把兩條既有能力接起來「驗」,非新生成能力)

- **能力 A(0i / G-3)**:`pivot_rotation.py` + `build_spine --pivot-rotate`/`--scale-pivot` —— 讓件繞**關節 pivot**
  旋轉+縮放(補償 `Δ=(M−I)(O−P)`,M=R·S),不動骨架結構。
- **能力 B(E/H/I)**:`genre_priors` → `build_spine --animate` 直出主秀節拍(hit/combo/charge/burst/cascade)。
- **缺口**:A 的端到端 AC(`validate_pivot_rotation` AC6 / `validate_scale_pivot` AC7)都只在**合成 skeleton +
  合成單一 beat**(Loop / Win pulse)上驗機制。而 `build_spine` 的 pivot 補償迴圈(`apply_pivots(beat, …)`,
  build_spine.py:351)其實**逐一掃過所有 animations** → 主秀 beat 的 limb rotate/scale **早已**被轉成繞關節版,
  **但從未有 AC 驗過**「真實產線產的主秀節拍下 limb 真的繞關節而非件中心動」。G-2 補這個整合缺口。

## 為什麼值得(整合閘 vs 又一條參數軸)

近期里程碑多是「在單一 robot 資產上加一條參數軸(tier/count/cascade-dir)」。G-2 不同:它是**整合驗證閘**
(呼應 RULES「每能力必配評估器」),把 S5 幾何(關節)與 S1 keyframe(主秀 beat)在**真實產線**接點上建立
回歸防線 —— 若日後 beat 生成或 pivot 接線改動,使 limb 又悄悄繞件中心轉,此閘會抓到。

## 範圍(誠實界定:只驗旋轉/縮放主秀節拍)

- 驗:`cat ∈ MAIN_SHOW_CATS − SHEAR_CATS` = **hit/combo/charge/burst/cascade**(可被 `--scale-pivot` 的 M=R·S
  **完整**補償)。
- 不驗(已另有覆蓋):**shear 節拍 wobble/squash/twist** 需 `--shear-pivot`,其繞關節性質**已**由
  `validate_twist_tier`(TT5)、`validate_twist_volume(_tier)`(TV5/VTT5)、`validate_squash_tier`(ST)等的
  **端到端 pivot 殘差 AC** 覆蓋(那些閘用 `--shear-pivot` build 並量每檔位 pivot 殘差 <Xpx)。

## AC(5,客觀可量測;15 組 pair = 5 主秀節拍 × 3 有關節 limb:右手/頭/左手)

- **M1 present + routing + 零回歸**:兩版 build 皆成功;summary 具 `pivot_centers`/`pivot_joints`;有關節
  limb/head 集合非空;每主秀節拍皆有 ≥1 有關節 limb 帶 rotate/scale + 被補償(有 translate);非關節件
  (光暈=特效、身體=root,無接觸縫)不在 `pivot_joints`;scale-pivot 版結構節拍(In/Loop/Out)仍 finite。
- **M2 crux — 繞關節不動點**:每(主秀節拍 × 有關節 limb),關節附著點世界座標逐幀殘差 **max 0.39px < 0.5**;
  **且**件最遠點位移 ≥ **40.79px**(真的在動非凍住)。
- **M3 neg-control(繞件中心)**:同組 pair 在**不補償版**(`--animate` 無 pivot 旗標)下,逐 pair 比值
  **≥147×**(主判準:補償把關節運動砍 ≥20×,處處成立);且最差 pair 繞件中心位移 **161px**(量級明顯大)。
- **M4 identity 介面(保設定姿勢)**:pivot 補償**不在節拍本就靜止處引入不連續** —— 對每個靜止端點
  (不補償版該端點恰為 setup identity 者,共 **27 個**),補償版亦須 setup identity(補償後 Δ = **0**)。
  hit/combo/charge/cascade 首尾、burst **尾** 皆須 identity;**burst 首(刻意塌陷登場 rot25°/scale0.02,非 setup)
  不受此限**,其關節仍由 M2 保證不動(補償在塌陷幀給出正確的 `Δ=(M−I)(O−P)`)。
- **M5 isolation + 正確轉換集合**:(a) 非關節件(光暈/身體)channels 在 comp/raw 兩版**逐位元相同**
  (補償只動有關節的 limb,不外洩);(b) 兩版**有差異**(被補償)的 bone 集合 == **恰好**有關節 limb 集合
  (該轉的都轉、不該轉的沒轉,無漏轉/多轉)。

## 關鍵發現

1. **「apply_pivots 已掃過所有 beat」≠「主秀 beat 下 limb 真的繞關節」有 AC** —— 能力接線早在,驗證才補上
   (再現專案反覆出現的「X 就緒 ≠ 有 AC 驗 X 在真實產線成立」;同 (E)「模板就緒 ≠ 產線會用它」、
   (0i)「幾何就緒 ≠ 生成器接上」)。整合點最該放回歸閘。
2. **不是所有主秀節拍都「首尾 setup identity 可插 Loop」** —— **burst(reveal/登場式)刻意首幀塌陷**
   (rot 25°、scale 0.02),故 identity-介面 AC 必須**依不補償版該端點是否本就靜止**來決定是否要求,不能
   一律對首尾都要求 identity(否則對 burst 假失敗)。正確不變量 = 「補償**不在節拍本就靜止處**引入不連續」,
   塌陷登場處的關節不動性改由不動點 AC(M2)保證。
3. **負對照的主判準是「逐 pair 比值」而非「絕對位移量」** —— 低幅度節拍(如 cascade/burst 作用在頭,
   |O−P|≈50px)的繞件中心位移可能只 ~9px,若用絕對 floor 會對合法低幅度 pair 假失敗;但**補償/不補償的
   比值**在所有 pair 都 ≥147×(極強鑑別力)。故 M3 = 逐 pair 比值 ≥20× (處處) + 最差 pair 位移量明顯大
   (量級佐證),兩者分工。

## honest boundary(仍在)

- **單一 rig 真值**(robot 一件可拆肢體)—— 同 S5 一路的硬缺口(多 rig 真值屬使用者資源,C 類)。
- 只在**非 rig** 下套用 pivot 補償(`--rig` 走結構性搬骨,互補解法)。
- **shear 主秀節拍**(wobble/squash/twist)的繞關節性質由他閘覆蓋,非本閘。
- 主秀運動的**手感**(繞 pivot 的幅度/曲線是否好看)仍是美術(A 類);本閘只驗**客觀幾何不動點**。
- cap `pivot_main_show_integration` L2 併入 `spine-anim-forge`,該區塊**仍 HOLD**(防固化半成品)。
