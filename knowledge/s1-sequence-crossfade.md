# S1 (L-5) 跨 beat 混場 crossfade / mix 序列接點 —— 整合/組合閘

> candidate **(L-5)**,2026-10-06 run 001。延續 (L)/(L-2)/(L-3)/(L-4) 刻意選**整合 / 組合閘**,
> 不加任何參數軸。補的是 L 系列一路圍繞的 `compose_sequence` 的 honest boundary:它做不到「疊加」。

## 一句話

`compose_sequence`(L~L-4 的基石)是**純時間平移 + 接點去重 = C0 拼接** —— 任一瞬間**恰好一支 beat 在作用**。
真實大獎序列常用**混場 / 溶接(crossfade / dissolve)**:在一段**重疊窗**內前 beat 淡出、後 beat 淡入,
**兩者同時貢獻(疊加 superposition)**。純平移 + 去重**在結構上做不到疊加**(它只能把時間錯開,不能讓兩 beat
在同一瞬間並存),所以 crossfade 是**序列組合的下一個組合層軸**,需要真正的 mix 機制。本次把它補上並以閘把關。

## 做了什麼(全 additive)

- `gen_animations.crossfade_weight(tau, overlap, fade="linear")` — 混場權重 `w(tau)∈[0,1]`:進窗 0(全 A)→
  出窗 1(全 B);A 權重 = `1-w`(**partition of unity**,和恆 = 1)。預設 linear,`smooth`=smoothstep 保留但
  不設預設(不在整合閘引入美感軸)。純函式。
- `gen_animations.blend_states(sa, sb, w)` — 兩個 `spine_anim.sample()` 狀態的逐通道線性混合 `(1-w)·A + w·B`
  (bones 全通道 rotate/translate/scale/shear + slot alpha;缺席通道視為 setup identity)。純函式。
- `gen_animations.crossfade_pair(A, B, overlap, dt=1/30, fade="linear")` — **烘焙式混場**,產單一可載入 clip
  (duration = `durA + durB − overlap`):
  - `[0, offsetB)` 純 A(原關鍵幀,保真);`offsetB = durA − overlap`
  - `[offsetB, durA]` 重疊窗:以 `dt` 網格同步取樣 A(local=t)與 B(local=t−offsetB),混合後發出關鍵幀
  - `(durA, total]` 純 B(原關鍵幀平移 +offsetB,保真)
  - `overlap==0`(退化)→ **委派 `compose_sequence`**,保證**逐位元**等同 C0 拼接。
- `gen_animations.crossfade_sequence(anims, order, overlap, …)` — 多 beat **左折疊**成單一 crossfade 序列。
- `validate_sequence_crossfade.py`(L-5,5 AC):從**先驗庫 → 真實 build_spine robot 骨架 → build_animations**
  端到端(`combo→cascade`,OV=0.5),與 L / L-3 / L-4 同一 fixture。

## 契約與不變量

| 不變量 | 說明 |
|---|---|
| partition of unity | A 權重 `1-w` + B 權重 `w` = 1 ⇒ 兩**等值**常數 clip 混合仍恆值(無 bump) |
| 退化(strict generalization) | `overlap==0` ⇒ **逐位元** == `compose_sequence` 的 C0 拼接 |
| C0 窗邊界 | 進窗 w=0 → A(offsetB);出窗 w=1 → B(overlap);與純區段值連續 |
| 真疊加(concat 做不到) | 窗內兩 beat 皆非 identity 時,混合值 `(1-w)A+wB` 既 ≠ 純 A 亦 ≠ 純 B;而 concat 同一時間只拿得到單一 beat |
| 純區段保真 | 窗外逐幀還原孤立 A / B(只動重疊窗) |

## 5 AC 全 PASS(真實 robot 骨架)

- **CF1 present + mechanism-active**:crossfade(combo,cascade,0.5)可載入(all_finite・時間嚴格遞增)、
  duration == `durA+durB−OV` = 1.6;**非空驗**:重疊窗內 ∃ grid 時間兩 beat **同時**非 identity
  (max min(devA,devB) = **9.13** ≥ 1)→ 真有疊加發生,非兩個 identity 空混。
- **CF2 crux — C0 窗邊界連續**:進窗 `cf(offsetB)==A(offsetB)`、出窗 `cf(durA)==B(OV)`;**骨殘差 ≤ 1e-4
  (精確銜接)**,全狀態殘差 ≤ QUANT_TOL(slot 8-bit 量化)→ 混合窗無縫黏回純區段。
- **CF3 crux — 真疊加 / concat 做不到(本 run 核心)**:窗內 grid `t*=0.6`(`w=0.4`,兩 beat 皆非 identity):
  (a) 線性 `cf(t*)==(1-w)A+wB` 骨精確;(b) 兩者皆貢獻 `|cf−純A|=5.25>1` 且 `|cf−純B|=7.88>1`;
  (c) **crux** `compose_sequence(t*)==純 A`(骨 ≤1e-4)且 `|concat−cf|=5.25>1` → **C0 拼接同一時間只拿得到
  單一 beat,結構上做不到混合**。
- **CF4 partition + 退化守衛**:(a) partition of unity:兩常數 clip 10°/30° 窗內 `==10+20w` 精確(err 1.3e-5,
  僅 6 位時間 round)、端點 10/30;(b) **no-bump 守衛**:兩等值常數 20°/20° 窗內恆 20(dev 0)→ 權重和 = 1 無
  artifact;(c) **crux overlap=0 逐位元 == `compose_sequence`** → crossfade 是嚴格推廣,零重疊退化回 L 的 C0 拼接。
- **CF5 純區段保真 + 多 beat**:純前段 `[0,t0]`(t0 = 最後一個 <offsetB 的 A 關鍵幀)逐幀還原孤立 A、
  純後段 `(durA,total]` 逐幀還原孤立 B(骨 ≤1e-4 全狀態 ≤量化)→ 混場只動重疊窗;
  `crossfade_sequence(hit→combo→cascade,每接點 0.3s)` 可載入且 duration == `Σdur − 2·0.3` = 2.0。

## 量測精度誠實(分離回報)

- **骨通道(rotate/translate/scale/shear)混合精確** —— 殘差僅來自 6 位**時間 round**(~1e-5),故 BONE_TOL=1e-4。
- **slot alpha 受 Spine 8-hex color 格式 8-bit 量化**(≤1/255≈0.0039),故全狀態殘差以 `QUANT_TOL=1/255+eps`
  把關,並與骨殘差**分離**回報。這是誠實標示「哪一部分精確、哪一部分受格式量化」,非把兩者混在一個鬆 tol 裡。

## 關鍵發現

1. **C0 拼接(L~L-4)與加權疊加(L-5)是兩個結構不同的組合層**:前者**時間互斥**(錯開時間、一次一 beat)、
   後者**同時並存**(重疊窗內兩 beat 疊加)。`compose_sequence` 在重疊時間拿不到混合值是**結構性限制**,
   不是精度問題 —— 這是本 run 最清楚的鑑別點(CF3c:同一 t* concat==純 A 而 cf 明顯含兩者)。
2. **partition of unity 是「混合無 artifact」的保證**:A 權重 `1-w` + B 權重 `w` = 1,使兩等值輸入混合後仍為該值
   (no-bump 守衛)—— 這和 L-3 LP4「光自接點無縫不足以是有意義 loop」同屬「機制正確性需專門守衛,不能從正向 case 推得」。
3. **退化測試(overlap=0 逐位元 == compose_sequence)把新機制釘回舊機制**:證明 crossfade 是 C0 拼接的**嚴格推廣**
   (而非另起爐灶),零重疊時行為完全一致 —— 這是「新軸不破壞既有不變量」最強的回歸形式。

## honest boundary

- 窗長 / 緩動曲線屬**美術手感**(A 類):本閘用 linear 權重、固定 OV,不引入美感軸(smoothstep 已備用未設預設)。
- **slot 混合假設 alpha-only 白色 tint**(本資產光暈成立):重疊窗 slot color 以 `ffffff`+alpha 重發,
  純區段保留原 hex;非白 tint 的 rgb 混合為後續。
- 單一真值資產(robot_parts)。cap `sequence_crossfade` L2 併入 `spine-anim-forge`(生成能力仍 L0/L1 → 仍 **HOLD**)。

## 下一個候選(擇一,皆純自主)

- **(L-6)** crossfade **權重曲線**客觀化:smoothstep vs linear 的「速度連續(C1 at 窗邊界)」—— 接 L-4 的 C1 精神到
  混場(linear 權重在窗兩端有速度 kink;smoothstep 窗邊界速度 = 0 → C1)。這是 crossfade 的客觀新不變量,非美感。
- **(L-7)** crossfade **保形 / 幾何守恆**:混合兩個各自體積守恆的 beat,其混合在重疊窗內是否仍守恆?(線性混合
  **不**保 `det≡1` —— 揭示「疊加」與「保形」兩約束何時相容,呼應 twist volume 系列)。
- **(J-8)** 擴充 cascade geo `source`;或 **(G-1)** `--rig`×pivot 變換 per-bone 語意去重。
