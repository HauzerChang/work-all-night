# S1 自接點 C1(速度)連續 / C1-loopability — candidate (L-4)

> 2026-10-05 run 002。關掉 candidate (L-3) 誠實列出的 honest boundary:`is_loopable` 只驗 **C0**
> (自接點值連續),明記「不保證 C1 速度連續(loop 重啟頓挫)」。本次把 **C1**(自接點速度連續)
> 顯式量化並以閘把關。**crux 發現**:真實一次性主秀 beat 首尾皆 setup identity → `is_loopable`(C0)
> **一律 True**,L-3 的判準會**誤把單發節拍當可安全重播**;唯有 C1 能把真 idle-Loop 與單發 beat 區分開。
> 這是**組合層的覆蓋補強 + 兩條純量測函式**,無改任何 beat 生成 / 產線值。

## 補的缺口(L-3 誠實列出的 honest boundary)

candidate (L-3) 的 `is_loopable(clip)` 判「首幀狀態 == 尾幀狀態」(所有通道 C0 相等),把「可安全
重播」顯式化。但它在 `knowledge/s1-sequence-loop-repeat.md` 誠實記著(該檔 honest boundary 第 3 條):

> 這裡只驗 **C0**(值連續);**C1 速度連續**(loop 重啟時無「速度感的頓挫」)是更高階的手感不變量。

把一支 clip 平鋪重播時,即使端點**值**相等(C0),若**進入 t=0⁺ 的外向速度 ≠ 逼近 t=dur⁻ 的內向
速度**,自接點就有**速度突變(velocity kink / 頓挫)**。本次把這條 C1 不變量關掉。

## 選題理由(延續 L / L-2 / L-3 / G-2,刻意不加參數軸)

近期多為整合 / 組合閘而非再加生成軸。L-4 的客觀新不變量 = **自接點 C1 速度連續**,L-3 的 C0 判準
涵蓋不到(且會誤判,見下 crux)。直指 north star「產出**可無頓挫**循環播放的大獎 Loop」。

## 做了什麼(全 additive)

1. **`gen_animations.loop_seam_velocity_gap(clip, h=1e-3)`** → float:自接點 C1 不連續量 =
   `max |v_end − v_start|`(跨所有 bone 通道 rotate/x/y/scale/shear + 每 slot alpha,單側有限差分)。
   單位 = `_state_max_diff` 的混合單位 **每秒**。純函式、additive、不依賴任何既有索引。
2. **`gen_animations.is_c1_loopable(clip, tol=1e-6, vel_tol=1.0, h=1e-3)`** → bool:
   `= is_loopable(clip, tol)` **AND** `loop_seam_velocity_gap(clip, h) <= vel_tol`。C1 ⇒ C0(嚴格更強)。
3. 內部 helper `_state_velocity(clip, at_start, h)`:單側差分的「狀態速度」(對 `sample()` 兩次取值
   相減除 h)。
4. **新閘 `validate_sequence_loop_c1.py`(L-4,5 AC)**:從**先驗庫 → 真實 build_spine robot 骨架 →
   build_animations** 端到端(與 L / L-3 同一 fixture)。

## 5 AC(全 PASS)

- **C1a present + C0 複驗 + 非空驗**:`is_loopable(Loop)`==True;Loop 端點**真有速度**
  (max 端點速度 ≈15 deg/s ≥ 1,否則 C1 判準空驗);gap 可算且 finite。
- **C1b crux — metric 良定義**:Loop 自接點 gap 對 h∈{2e-3,1e-3,5e-4} **bit-stable**(相對差 < 1e-3)
  → 單側差分 = 端點**切線**,非有限差分 artifact。並**確認**須在 clip 端點層量:跨 **composed** 接點
  因 L-3 的時間去重會被抹平(composed 恆 C0)→ composed wrap 兩側速度差 ≪ clip 端點真 gap(0.19),
  量不到真 kink。
- **C1c crux — Loop C1 + 通道分解**:`loop_seam_velocity_gap(Loop)` = **0.188** < 1.0 且
  `is_c1_loopable(Loop)`==True;通道分解:**剛體 limb rotate 通道精確 C1**(右手/左手/頭 rotate
  gap ≈ 1e-12 ≤ 1e-6),唯一殘差來自**光暈呼吸**(scaleY 0.024 / alpha 0.188)→ 誠實指認 Loop 的
  C1 殘差來源(光暈的 breathing pulse 上升再下降,自接點速度符號翻轉)。
- **C1d crux — C1 獨立於 C0(本 run 核心)**:{Loop, hit, combo, charge, cascade} **全部**
  `is_loopable`(C0)==True → **C0 不能鑑別**。但 C1 gap:Loop **0.188** 而主秀 beat
  hit 134 / combo 109 / charge 167 / cascade 64,每個 ≥ 10,且 min(主秀)/Loop = **340×** ≥ 50
  → 證 `is_loopable` 單獨會**誤放**一次性 beat,C1 loop-seam 連續是鑑別子;`is_c1_loopable` 對主秀
  beat **全 False**、對 Loop True。
- **C1e neg-control + 空驗守衛**:
  - (a) **crux**:三角脈衝(scale 1→2→1,C0-loopable 但注入速度 kink)gap **2.0** > 1.0 且
    `is_c1_loopable`==False → 閘抓出 `is_loopable` 看不到的頓挫。
  - (b) **空驗守衛**:靜止 clip gap==0 → 速度測試 trivially 過且 `is_c1_loopable`==True,**但**端點
    速度 ≈0 < 1(無運動)→ 證「gap≤tol」必要不充分、須配非靜止(呼應 L-3 LP4)。
  - (c) In(collapsed→identity)`is_c1_loopable`==False,且由 **C0 先否決**(`is_loopable(In)`==False)。

## 關鍵發現

1. **`is_loopable`(C0)會誤把單發主秀 beat 當『可安全重播』**:hit/combo/charge/cascade 首尾皆 setup
   identity → C0 判準全 True,但它們自接點速度突變 64~167 deg/s(符號翻轉)—— 平鋪會每份頓挫一次。
   **C1(自接點速度連續)是把真 idle-Loop 與一次性 beat 區分開的鑑別子**。這是本 repo 通則「真簽章常需
   兩獨立條件並立」在 loop 判準上的又一實例(呼應 L-3 的「C0 無縫 + 非靜止週期」兩條件)。
2. **同一支 Loop 在不同通道有不同階的連續性**:剛體 limb rotate 是**精確 C1**(端點切線完全相等,
   gap ~1e-12 = 由週期性擺動設計保證),光暈的 breathing scale/alpha 只做到 **C0**(端點值相等但速度
   符號翻轉,0.19 殘差 kick)。C1-loopability 要看**全通道最大** gap,但分解到通道能誠實指認殘差來源。
3. **C1 metric 的良定義須證對取樣步長 h 不敏感**(bit-stable → 真端點切線非 artifact);且與 L-3 同理,
   **必須在 clip 端點層量**,不能跨 composed 接點(時間去重會抹平 kick)。「量在哪一層 + 量對無關變數
   是否穩定」再次決定能不能看見真不變量(呼應 L-2 / L-3 / Z4 aliasing)。

## honest boundary(仍在)

- **Loop 是否該被設計成完美 C1 屬美術手感(A 類)**:光暈 breathing 的 0.19 速度 kick 是已知邊界,
  要不要消除(例如讓光暈呼吸用整週期正弦使端點速度對稱)是後續手感決策,本閘只**量化並誠實攤開**它。
- `vel_tol=1.0` 為量級選擇(Loop 0.19 ≪ 1 ≪ 主秀 ≥64,分離餘裕充足);混合單位沿用 `_state_max_diff`。
- 無改任何 beat 的生成 / 產線值(兩新函式純量測 / 純判斷)。
- 單一真值資產(robot)。cap `sequence_loop_c1` L2 併入 `spine-anim-forge`(仍 HOLD)。

## 檔案

- `tools/analyzer/gen_animations.py` — 新增 `loop_seam_velocity_gap` + `is_c1_loopable` +
  `_state_velocity`(全 additive)。
- `tools/analyzer/validate_sequence_loop_c1.py` — L-4 閘(5 AC)。
- `tools/check_readiness.py` — 新增 cap `sequence_loop_c1`。
