# S1 跨 beat 混場 crossfade(時間重疊 + 權重混合)— candidate (L-5)

> 2026-10-06 run 001。補 candidate (L) 誠實列出的 honest boundary:`compose_sequence` 只做**純時間
> 平移 + 接點去重**(C0 拼接),接點值不等(A 尾 ≠ B 首)就留一個 pop,做不到真實遊戲轉場用的
> 「**時間重疊 + 權重混合**」。本次補上這個 mix 機制:`crossfade_state`(混場取樣 ground truth 混合律)
> + `crossfade`(產可載入混場 clip)+ `crossfade_weight`(過渡權重)。**crux 發現**:即使 A 尾 ≠ B 首
> (拼接會 pop),crossfade 在整段仍 **C0 連續** —— pop 被攤平到 mix 窗(寬 `mix_dur`,一個可調旋鈕);
> 對同一接點**硬切**則留一個 eps-無關的真 step。全 additive,無改任何 beat 生成 / 產線值。

## 補的缺口(L 誠實列出的 honest boundary)

candidate (L) 的 `compose_sequence(anims, order)` 把各 beat clip 依序**時間平移**串成單一可播放序列,
相鄰 beat 在接點(前 beat 尾幀 == 後 beat 首幀)值相等時 C0 無縫,並**去重**重合接點幀。它在
`knowledge/s1-sequence-composition.md` 誠實記著:接點值**不等**時是真不連續,「應由上游排序避免;本函式
不做值檢查」。也就是說 compose 的**純平移拼接**沒有「把兩支在一段時間窗內同時播、以權重由 A 混到 B」的
能力 —— 這正是真實遊戲 runtime 的 **crossfade / mix**(Spine AnimationState 的 track mixing / mix duration)。
本次把這條 boundary 關掉。

## 選題理由(延續 L / L-2 / L-3 / L-4,刻意不加參數軸)

近期多為整合 / 組合閘而非再加生成軸。L-5 的客觀新機制 = **時間重疊權重混合**,是 compose 純平移拼接
**做不到的下一組合層**。直指 north star「序列組合的下一組合層 = 真正的混場,而非拼接」。

## 做了什麼(全 additive,`tools/analyzer/gen_animations.py`)

1. **`crossfade_weight(tau, kind="linear")`** → float:過渡權重 w(τ),τ∈[0,1],w(0)=0(全 A)、
   w(1)=1(全 B)、單調。`linear`(對齊 Spine 預設 MixBlend 線性混合)或 `smooth`(smoothstep 3τ²−2τ³,
   端點速度 0 的更順過渡)。
2. **`_blend_states(sa, sb, w)`** → state:兩個 `spine_anim.sample()` 狀態的逐通道線性混合
   `(1−w)·A + w·B`(缺席通道視為 setup identity;bone rotate/x/y/scale/shear + slot alpha 全涵蓋)。
3. **`crossfade_state(clipA, clipB, mix_dur, t, weight)`** → state:**ground truth 混合律**。時間軸三段
   (w0 = dur_A − mix_dur 為 mix 窗起點;總長 dur_A + dur_B − mix_dur):
   - `t ∈ [0, w0)` → 純 A(`sample(A, t)`);
   - `t ∈ [w0, dur_A]` → mix 窗:A 續播到自己的尾(local=t),B 從 0 起(local=t−w0),
     τ=(t−w0)/mix_dur,w=weight(τ),state=`_blend_states(sample(A,t), sample(B,t−w0), w)`;
   - `t ∈ (dur_A, 總長]` → 純 B(local=t−w0)。
   端點銜接:w0 處 w=0 → 純 A 尾段值連續;dur_A 處 w=1 → 純 B 起段值連續。**故整段 C0 連續,與 A 尾 /
   B 首是否相等無關**(crux)。
4. **`crossfade(clipA, clipB, mix_dur, steps=16, weight, merge_tol)`** → `(composed, info)`:以
   `crossfade_state` 為真值,在一組**節點**上取混合狀態存成**線性**關鍵幀。節點 = {均勻格點(窗內間距
   dt = mix_dur/steps,全程同密度)} ∪ {A 原關鍵幀時間(純 A 區)} ∪ {B 原關鍵幀時間平移後(純 B 區)}
   ∪ {0, w0, dur_A, 總長}。於是純 A/B 區的**原關鍵幀時間節點上 bone 通道逐位元還原孤立 clip**,窗內節點
   逐位元等於混合律,節點**之間**為線性近似(真值為分段二次 + A/B 本身可能 bezier → 誤差隨 steps→0 收斂)。
   `mix_dur=0` → 退化為**純拼接**(`compose_sequence([A,B])`,bit-identical)。

## 驗收閘(`validate_sequence_crossfade.py`,5 AC 全 PASS)

fixture:先驗庫 → 真實 `build_spine` robot 骨架 → `build_animations`(與 L/L-3/L-4 同一 fixture)。
**A = `Out`**(identity→collapsed,尾為**非** identity)、**B = `Loop`**(起於 identity)→ 接點 A 尾 ≠ B 首,
**真有不連續 J≈25**,混場才有意義。無縫對照 = `hit`→`Loop`(皆 identity 介面,J≈0)。

- **X1 present + backward-compat + 非空驗**:`crossfade(Out,Loop,mix)` 產有限可載入 clip,時長 ==
  dur_A+dur_B−mix;`mix=0` **bit-identical** `compose_sequence([Out,Loop])`;接點 J≥5(非空驗:真有 pop 要攤平)。
- **X2 crux — 端點銜接 + 純區保真**:窗首 t=w0 == 孤立 `sample(Out,w0)`(w=0)、窗尾 t=dur_A ==
  孤立 `sample(Loop,mix)`(w=1),殘差 ≤0.01;純 A 區在 Out 原關鍵幀節點上 bone 通道逐位元還原(diff=0)、
  純 B 區數點還原 Loop → mix 侷限窗內、兩端純播無損。
- **X3 crux — 不連續接點 C0 vs 硬切**:J≥5;crossfade 接點差 `|s(seam−eps)−s(seam+eps)|` 在 eps=1e-4 時
  **0.0096 ≤0.05** 且隨 eps **線性縮小**(1e-3→1e-4 ratio≈10)→ **C0 連續**(pop 被攤平);**同一接點硬切**
  差 **≈25 恆定**(eps ratio≈1)→ 真 step。證 crossfade 消掉了硬切留下的 pop。
  > 踩雷(預算內自修):初版把「eps=1e-3 的接點差 ≤0.05」當 C0 門檻 → FAIL(0.096>0.05)。那是**端點切線
  > 斜率 × 2eps**(有限、連續),不是跳變。改判準為「**最小 eps** 的接點差小 **且** 隨 eps 線性縮小」才對
  > ——「隨 eps→0 縮小」區分連續(斜率),「eps-無關」區分 step(跳變);真 step 才 eps-無關。
- **X4 — 混合律 + 權重 + steps 收斂**:線性 τ=0.5 == 0.5·(A⊕B) 殘差 0;`crossfade_weight` 線性/smoothstep
  皆單調、端點 0/1 精確;窗內節點 comp bone 逐位元==混合律(diff=0)、slot ≤1/255;重取樣 steps 8→32→128
  逼近誤差**嚴格遞減**(0.167→0.0103→0.0019,格點近似收斂量化)。
- **X5 負對照 + 空驗守衛 + 守衛**:(a) **可調旋鈕** peak 過渡速度 mix=0.1 / mix=0.2 = 230.8/106.1 ratio
  **2.18≈2×**(mix 愈小愈陡 → mix 是 compose 沒有的平滑旋鈕);(b) **空驗守衛** 無縫對 hit→Loop J=0<1 →
  其 C0 宣稱空驗,證 X3 的 crux 須配**不連續** fixture;(c) 非法 mix_dur(>min 時長 / <0)與空 clip 皆觸 ValueError。

## 關鍵發現 / 可複用結論

1. **「C0 連續 vs 真 step」的客觀判準 = 接點差對取樣 eps 的行為**:連續函數接點差 = 切線斜率 × 2eps
   → **隨 eps→0 線性縮小**;真跳變(step)接點差 = 跳變量 **恆定、eps-無關**。用兩個 eps 量比值即可鑑別,
   不需知道絕對門檻(呼應 L-3/L-4「量在哪一層 + 對無關變數的行為」決定能看見什麼)。
2. **crossfade 的價值 = compose 沒有的『平滑旋鈕』**:pop 被攤平到寬度 = mix_dur 的窗,peak 過渡速度 ∝
   1/mix_dur(實測 mix 減半 → peak 約 2×)。拼接只有「接 / 不接」,混場多一個連續可調的轉場時長。
3. **混場端點必須銜接純段**:節點含 w0 與 dur_A(窗首值=純 A 尾、窗尾值=純 B 首),否則窗與純段接縫自己會 pop。
4. **踩雷(curve 重用):** 初版想「純 A 區複製原關鍵幀、只重取樣 mix 窗」,但稀疏 bezier clip(如 Out 只有
   0/0.4 兩幀)把一條 bezier 緩動**壓到更短區間**會扭曲緩動(t=0.1 的值跑到孤立 clip t=0.3 的深度)。改為
   **整段以 `crossfade_state` 重取樣**(節點釘住 A/B 原關鍵幀時間),純區節點逐位元、節點間線性近似(收斂)。

## honest boundary(本 candidate 誠實邊界)

- **mix_dur / 權重曲線 / 用在哪兩支 beat 之間**屬美術手感(**A 類**,PROPOSAL)。
- 節點**之間**為線性近似(真值為兩支分段線性 × w 的分段二次 + A/B 本身 bezier);誤差隨 `steps`→0 收斂,
  **已量化**(X4 steps 收斂)。要精確可改產 bezier / 用 A/B 關鍵幀聯集加密,屬後續。
- slot alpha 的 8-bit 量化(1/255)為 Spine color 格式**固有**,非演算法誤差。
- 無改任何 beat 生成 / 產線值(三新函式純量測 / 純產檔);**單一真值資產**(robot)。

## 待續(擇一,皆純自主)

- **(L-5') 混場的 C1(速度)連續**:smoothstep 權重讓端點速度 =0 → 混場進出更順;可量 crossfade 在
  窗首 / 窗尾的速度連續性(linear 權重在窗界有速度 kink,smooth 沒有),為轉場手感客觀化(比照 L-4 對 loop)。
- **(L-6) 三段以上的混場序列**:把 `crossfade` 推廣成 `compose_with_crossfades(order, mix_durs)`,
  讓整條 In→主秀…→Loop→Out 的每個接點可選「拼接 or 混場 + 時長」(組合層再上一階)。
- **(L-5'') 加性混合(additive mix)**:crossfade 是**取代式**(A→B);另一種是**疊加**(B 疊在 A 上,
  如主秀節拍疊在 Loop 之上),對應 Spine 的 additive animation,語意不同,是另一條混合軸。
