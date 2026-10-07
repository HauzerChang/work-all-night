# S1 (L-7) per-junction(逐接點 / 選擇性 / 非對稱)crossfade

> candidate **L-7**(2026-10-07 run 001)。承 L-6:把 crossfade 的單一 scalar `xf` 一般化成**逐接點向量**。
> 程式:`tools/analyzer/gen_animations.py`(crossfade 段 + 新 `_normalize_xf`)・閘
> `tools/analyzer/validate_sequence_crossfade_selective.py`。

## 補的缺口(L-6 的 honest boundary)

candidate (L-6) 的 `crossfade_sequence` 把序列接點 C1 kink 消掉了,**但 `xf` 是單一 scalar —— 所有接點套
同一重疊秒數**。L-6 誠實列為未做的 honest boundary:

> 「**接點平滑的選擇性套用**(per-接點 xf / 只平滑特定接點)—— 但哪些接點、xf 多長觸美術手感 A 類,屬 PROPOSAL。」

L-7 把這個 honest boundary 關掉的方式與整個 L 系列一致:**客觀化機制,不替使用者決定取值**。把 L-6 的
`xf` 由 scalar 一般化成 **per-junction 列表**(長度 = `len(order)−1`),機制上可逐接點指定重疊秒數,
某接點給 `0` 即該接點**不混場**(保留瞬切撞擊感)。至於**混哪些接點、各給多長**仍是美術手感(A 類
PROPOSAL),本閘不決定。

這**不是新生成軸**,而是把 L-6 **同一條 crossfade 重疊軸的取值**由「單一 scalar」一般化成「逐接點向量」——
同 J-5→J-6 把 cascade 方向軸由 4 向離散補成任意角連續的精神(機制一般化 = 客觀;取值 = 手感 A 類)。

## crux:crossfade 的「平滑 / 不平滑」可以逐接點獨立決定

某接點給 `xf=0` → 退化為**瞬切**(不混場),其接點 C1 kink **重現**為 L-5 的 `seam_velocity_gap`
(= `xf→0` 的瞬切極限);其餘 `xf>0` 接點仍被 smoothstep 消成 0。因此:

> **「序列全程 C1」當且僅當每個接點都被平滑 —— 任一接點留瞬切 → `is_c1_crossfade_sequence` = False。**

這把 L-6 的「全有(全部平滑)」擴成「可選擇性(混哪些)」:保留離散節拍撞擊感的接點與平滑過渡的接點
**可並存**。例:只平滑 `Loop→Out`(收尾要柔)、其餘主秀接點保留撞擊,是合法且各接點各自正確的序列。

## 做了什麼(全 additive,`tools/analyzer/gen_animations.py`)

- **`_normalize_xf(order, xf)`** → `(xf_list, was_scalar)`:scalar(int/float)→ 廣播成等值向量
  `[xf]·(m−1)`、`was_scalar=True`;list/tuple → 驗長度 == 接點數、每元素 ≥0、`was_scalar=False`。
  長度不符 / 負元素 → `ValueError`。
- **`_crossfade_layout`** 吃逐接點 xf:
  - **scalar 路徑(零回歸)**:沿用 L-6 的「xf ≤ 最短 beat 時長的一半」scalar 守衛(逐位元相容)。
  - **per-junction 路徑**:對每個 beat,其**左右重疊和**(左接點 + 右接點 xf)不得超過該 beat 時長
    (避免三方重疊);此守衛在均勻取值時**退化**為 scalar 守衛(`2·xf ≤ min_dur ⟺ xf ≤ min_dur/2`)。
  - `offsets[i+1] = offsets[i] + dur[i] − xf[i]`(每接點縮**各自** xf)。
- **`crossfade_pose_at`** / **`crossfade_sequence`** 的左 / 右重疊、body 區邊界、重疊細分都改讀逐接點
  `xfs[i-1]`(左)/`xfs[i]`(右);`crossfade_sequence` 的統一時間解析度 `dt = min(非零 xf)/nsamp`;
  xf=0 的接點不做重疊細分(body 區相接 = 瞬切);**全零向量(含 scalar 0)委派 `compose_sequence`**。
- **`crossfade_junction_kinks`** 吃逐接點 xf:接點 xf>0 → 閉式 `crossfade_seam_kink`;接點 **xf=0 → 回報
  `seam_velocity_gap`**(L-5 瞬切極限的接點 kink)。多回一個 `"xf"` 欄位(additive,不動既有欄位)。
- **`is_c1_crossfade_sequence`** 不改碼,經 `crossfade_junction_kinks` 自動支援逐接點。

## 零回歸鐵則(一般化務必分清含與不含)

- **scalar `xf` == 等值 per-junction 向量 `[xf]·(m−1)`**:emitted animation 逐位元相等、junction kinks max
  逐一相等(閘 P1a)。
- **`xf=0`(scalar)或全零向量**:委派 `compose_sequence`,逐位元相容(閘 P1b / P5b)。
- per-junction 時間佈局守衛在**均勻取值**時退化為 L-6 的 `xf ≤ min_dur/2`(見上)。

## AC(`validate_sequence_crossfade_selective.py`,5 AC 全 PASS)

從**先驗庫 → 真實 build_spine robot 骨架 → build_animations** 端到端,與 L / L-5 / L-6 同一 fixture
(正向序列 `In→hit→combo→charge→cascade→Loop→Out`)。VEC = `[0.1,0.15,0.2,0.25,0.3,0.2]`。

- **P1 present+well-formed+總時長+零回歸**:(a) 等值向量 `[XF]·6` emitted 逐位元 == scalar XF、junction
  kinks max 逐一相等;(b) 全零向量 emitted 逐位元 == `compose_sequence`;(c) 相異向量 VEC 產合法 Spine
  timeline(finite / 時間嚴格遞增)、總時長 5.2 == Σdur−ΣVEC、相鄰段區間相交 == **各自** VEC[i]。
- **P2 crux 選擇性平滑**:SEL = 全 XF 但第 SHARP(`In→hit`)接點設 0 → (a) 其餘接點 kink ≤ 1e-6(仍平滑);
  (b) SHARP 接點 kink **重現** = **114.35** == L-5 `sequence_seam_gaps` 的 c1_gap(瞬切極限)≥ 10;(c)
  `is_c1_crossfade_sequence(SEL)` = **False**(留一瞬切即破全程 C1)**而** 全平滑 = **True**。
- **P3 per-junction C1 + 線性負對照**:相異 VEC,(a) smoothstep 每接點 kink ≤ 1e-6(各接點**不論自身 xf
  寬窄**皆被消)is_c1=True;(b) **linear**(負對照)每接點 kink ≥ 10(實測 min 13.2)is_c1=False → 證**消
  kink 的是 C1 斜坡、非 per-junction 機制本身**(L-6 X4 的 per-junction 版)。
- **P4 真混合+body 忠實+非對稱**:相異 VEC,(a) **每個**接點重疊中點姿勢與前 / 後 beat 單獨皆不同(≥0.3,
  實測 min 1.15)→ 各接點都真的在混合;(b) **非對稱鄰接下 body 忠實**(0.002 ≤ 0.05);(c) VEC 總時長 5.2
  ≠ 均勻 [XF] 總時長 5.5(逐接點寬窄**真的改變佈局**,非裝飾)。
- **P5 metric 良定義+守衛+空驗**:(a) 非 XF 寬度(0.5)clean clip 對線性斜坡閉式 == 數值有限差分(rel<1e-3);
  (b) 守衛:列表長度不符 / 負元素 / per-beat 三方重疊(左右重疊和 > beat 時長)→ ValueError、全零向量委派
  不報錯;(c) 空驗:兩**靜止** clip 間 xf=0 接點 → `seam_velocity_gap` = 0(無運動 → 瞬切亦無 kink)→ 證
  「SHARP kink 重現」須配**非靜止**才有意義(呼應 L-5 / L-6 空驗)。

## 關鍵發現

1. **crossfade 的平滑是逐接點可分解的屬性** —— 每接點的 C1 連續性只由**該接點自己的 xf 與斜坡**決定,與
   其他接點無關;「序列全程 C1」= 所有接點 C1 的**合取**。故混場不是「全有全無」,而是可逐接點選擇
   (保留撞擊 vs 平滑過渡並存)。
2. **一般化(scalar→向量)的正確性靠「等值特例逐位元等價」釘住** —— 等值向量 ≡ scalar、全零向量 ≡ compose,
   皆逐位元;per-junction 守衛在均勻取值時退化為 scalar 守衛。此為本 repo 一再出現的通則(J-6 的 lr/rl ==
   θ=0°/180° 特例、L-5 `loop_seam_velocity_gap` 委派 `seam_velocity_gap(clip,clip)`)的又一實例。
3. **xf=0 接點 = L-5 的瞬切極限** —— `crossfade_junction_kinks` 在 xf=0 回報 `seam_velocity_gap`,把 L-7 的
   「選擇性瞬切」與 L-5 的「純接續」在同一個量上接起來:L-5 是「全瞬切」、L-6 是「全平滑」、L-7 是「可選」,
   三者在接點 kink 量上連續。
4. **消 kink 的是 C1 斜坡,per-junction 機制只是讓你選接點** —— P3 線性負對照在逐接點下仍成立(每接點
   kink≥10),證 L-6 的 crux「w'兩端=0 才是鑑別子」不因 per-junction 而改變。

## honest boundary(仍在)

- **混哪些接點、各給多長 xf** 仍屬美術手感(A 類 PROPOSAL):離散節拍的撞擊感可能該保留;本閘只一般化
  **機制**(可逐接點指定),不替使用者決定取值。
- `vel_tol=1.0` / `XF=0.15` / VEC 取值為量級選擇;正向序列無 shear(crossfade 機制本身通道無關、含 shear);
  單一真值資產(robot)。
- **無改任何 beat 生成 / 產線值**(全 additive;等值 / 零向量委派後逐位元不變)。cap
  `sequence_crossfade_selective` L2 併入 `spine-anim-forge`(仍 HOLD)。

## 下一步(候選,皆自主)

- **讓先驗庫 / genre 建議「哪些接點該混、各多長」**(把 A 類 PROPOSAL 下推成 per-genre 預設,如
  `In→hit` 保撞擊、`Loop→Out` 柔收尾)—— 但最終手感仍 A 類。
- 或 **crossfade × tier**(高檔位更緊湊 / 更長的接點混場)、**非對稱單接點 crossfade**(左 xf ≠ 右 xf,
  需把 `_crossfade_layout` 的對稱重疊再拆成前退 / 後進兩段)。
- 或回主秀生成軸(charge 蓄力深度 / hold 長度隨檔位)、S5 rig 真值(C/資源類,使用者提供)。
- 詳見 `STATE.md` 的「下一步動作」。
