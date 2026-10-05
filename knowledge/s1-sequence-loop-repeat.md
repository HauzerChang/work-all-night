# S1 序列內 Loop 重播 N 次 + loopability 不變量 — candidate (L-3)

> 2026-10-05 run 001。把 candidate (L) 的序列組合閘從「每 beat 只出現一次」補到「**同一支 clip
> 重複 N 次**」—— 真實大獎序列的播放形態(進場 → Loop 重播待機 → 收尾)。新增 `is_loopable`
> 不變量把「可安全重播」顯式化,並以 `In→Loop×3→Out` 端到端釘回歸閘。
> 這是**組合層的覆蓋補強 + 一條純判斷 helper**,無改任何 beat 生成 / 產線值。

## 補的缺口(能力早在、AC 從缺;同 L / G-2 的整合閘精神)

candidate (L) 的 `compose_sequence(anims, order)` 以 `order` 列表串接 beat clip,其 **`order`
本就可重複同一 beat 名**(逐一 iterate、查 `anims[name]`、平移 offset、extend)。所以
`order = ["In","Loop","Loop","Loop","Out"]` **本就能跑** —— 這正是真實大獎序列的形態:進場後
**Loop 重播 N 次**(贏分計數滾動時循環待機),再收尾。但 L 的正向序列每個 beat **只出現一次**,
**從未有閘**驗過「同一支 clip 重複 N 次」這條路徑:

1. 重複鍵的 **offset 累加**是否正確(segments 記 N 個獨立條目、起點逐份遞增、總時長對)。
2. clip 接在**自己**後面的**自接點**(前份尾 → 後份首)是否無縫 —— 即 **loopability**;L 只驗過
   **相異** beat 的接點。
3. N 份重播是否**逐幀還原**同一孤立 clip(重播機制不隨份數漂移 / 不累積誤差)。
4. 平鋪後是否真是一段**非靜止**且**嚴格週期**的循環運動(否則「無縫」是空驗)。

## 選題理由(延續 L / L-2 / G-2,刻意不加參數軸)

近期多為「單一 robot 加一軸」。L / L-2 / G-2 已刻意轉向整合/組合閘。L-3 的客觀新不變量 =
**loopability(自接點無縫)+ 週期平鋪保真**,L 的相異-beat 接點閘涵蓋不到。直指 north star
「產出**可循環播放**的大獎動畫」。

## 做了什麼(全 additive)

1. **`gen_animations.is_loopable(clip, tol=1e-6)`**:判斷「首幀狀態 == 尾幀狀態」(所有通道 C0
   相等,含 shear)。首尾相等 → 把 clip 接在自己後面(重複 N 次)時自接點值連續、無 C0 跳變 /
   pop —— 遊戲 idle / Loop 動畫可無限重播的前提。純判斷、不依賴任何既有索引、不改值。
   - 介面契約下:Loop / 主秀 beat(hit/combo/wobble…)首尾皆 setup identity → **loopable**;
     In(collapsed→identity)、Out(identity→collapsed)首≠尾 → **非** loopable。
   - 明記:loopable 只保證 **C0**;**不**保證「有運動」或「速度連續(C1)」。
   - 附 `_state_max_diff`(與 L 的 `_state_diff` 同源,含 shear)供閘複用,判準同源。
2. **新閘 `validate_sequence_loop.py`(L-3,5 AC)**:正向序列 `In→Loop×3→Out`,從**先驗庫 →
   真實 build_spine robot 骨架 → build_animations** 端到端(與 L / charge 同一 fixture)。

## 5 AC(全 PASS)

- **LP1 present + loopable + offset**:`is_loopable(Loop)`==True;compose 後為合法 Spine timeline;
  segments 恰含 3 個 "Loop" 條目於**累加 offset** `[0.6, 2.6, 4.6]`;總時長 `7.0` == In(0.6)+
  3·Loop(2.0)+Out(0.4);用到的 bone 皆現身。
- **LP2 crux — 自接點無縫**:每個 Loop→Loop **自接點**(前份尾幀值 vs 後份首幀值)殘差 `0.0` <
  1e-3(= loopability 的 C0 判準,clip 端點層);並確認 compose 產物為連續函數(wrap shrink 比 ≈0.1)。
- **LP3 periodicity / idempotent**:3 份 Loop 重播各自去 offset 後**逐幀還原**孤立 Loop clip
  (殘差 `0.0` < 1e-4),且 3 份彼此逐幀相同 → 重播機制不隨份數漂移。
- **LP4 non-static + period-tile**:(a) Loop 有**真實內部運動**(孤立 clip 內部最大離 setup 位移
  `5.0` ≥ 1.0;否則「無縫」為空驗);(b) 平鋪區內 `sample(t) == sample(t+Loop_dur)`(嚴格週期,
  殘差 `0.0`)→ N 份重播平鋪成一段恰 N 週期的循環運動。
- **LP5 neg-control**:
  - (a) **crux**:In(collapsed→identity)`is_loopable`==False,In→In **自接點** `40.0` >> SEAM_TOL
    → 閘正確判非 loopable。**深一層 crux**:tiled-In 的 composed 經時間去重後 wrap **看起來仍 C0**
    (shrink 比 0.1 與合格 Loop 無異)→ 證「loopability 不能從 composed 判」,唯 clip 端點 self-seam 揭露。
  - (b) Out(identity→collapsed)`is_loopable`==False,Out→Out 自接點 `25.0` >>。
  - (c) **crux 空驗守衛**:合成一支**靜止**(恆 identity)clip → `is_loopable`==True 且自接點 `0`
    (trivially 無縫)**但** LP4 非靜止檢查 == `0` → 證「光自接點無縫」不足以是有意義的 loop
    (須同時非靜止 + 嚴格週期),LP4 有鑑別力。

## 迭代踩雷(預算內自修)— 揭示 compose 的時間去重會抹平 pop

初版 LP2 想從 **composed 時間軸**直接量 wrap 邊界兩側 C0 跳變(`sample(bt−ε)` vs `sample(bt+ε)`),
對合格 Loop 量到 `3e-3` 誤判 FAIL。追查發現:

- 這是**量測 artifact**:`sample(bt−ε)` vs `sample(bt+ε)` 捕捉的是 Loop 邊界附近的**真實非零速度**
  (end-velocity·ε + start-velocity·ε),不是 C0 不連續;ε→0 時線性縮小(實測 2.999e-2 → 2.999e-3,
  每縮 10× ÷10)。
- **更關鍵的發現**:`compose_sequence` 的**時間去重**(coincident-time 幀 collapse 成單幀,只看時間
  不看值)會把「同時刻、不同值」的接點(非 loopable beat)**抹成陡坡**而非真跳變 —— 去重丟前份尾幀、
  保留後份首幀,於是通道從 identity 一路內插到後份的 collapsed 值。結果 **composed 取樣恆 C0**
  (tiled-In 與合格 Loop 的 wrap shrink 比皆 ≈0.1,無從鑑別)。

結論與修法:**loopability 只能在 clip 端點層(self-seam / `is_loopable`)判,不能從 composed
時間軸判**。LP2 crux 改用 clip 端點 self-seam(前份尾幀值 vs 後份首幀值);composed 的連續性(shrink
比 ≈0.1)僅作**佐證 compose 正確**,非 loop 判準。LP5a 把這點固化成負對照(tiled-In 的 composed 仍
看似 C0,唯 self-seam=40 揭露)。

## 關鍵發現

1. **`compose_sequence` 的時間去重讓 composed 恆 C0**:值不符的接點被抹成陡坡而非真跳變 → 從
   composed 時間軸永遠看不出一個 beat 是否 loopable。**loop 判準必須在 clip 端點層**(首幀 vs 尾幀),
   這正是 `is_loopable` 做的事。(呼應 L-2:量測基石決定能看見什麼 —— 這裡是「量在哪一層」決定能看見什麼。)
2. **「首尾 identity → loopable」是 C0,不是全部**:一支恆 identity 的靜止 clip 也 loopable 且自接點
   無縫,但平鋪後毫無意義。有意義的 loop 需「非靜止 + 嚴格週期」兩條件並立(LP4)—— 再現本 repo 通則
   「真簽章常需兩獨立條件並立」(cascade 散佈+遞增、squash 守恆+非均勻、twist 反相+雙軸、charge 數峰+持續 hold)。
3. **重複鍵的 offset 累加 / 逐幀還原 / 彼此相同三者並驗**才證重播機制對「同一 clip 出現 N 次」正確
   (L 的相異-beat 路徑驗不到「同 clip 多份是否漂移」)。

## honest boundary(仍在)

- 重播次數 N 為 PROPOSAL(手感 A 類);beat 排序同前亦 PROPOSAL。
- 無改任何 beat 的生成 / 產線值(`is_loopable` 純判斷;`compose_sequence` 本就支援重複鍵,本 cap 只補
  判斷 helper + 新閘)。
- 這裡只驗 **C0**(值連續);**C1 速度連續**(loop 重啟時無「速度感的頓挫」)是更高階的手感不變量,
  屬美術 / 後續(A 類),本閘不涵蓋。
- 單一真值資產(robot)。cap `sequence_loop_repeat` L2 併入 `spine-anim-forge`(仍 HOLD)。

## 檔案

- `tools/analyzer/gen_animations.py` — 新增 `is_loopable` + `_state_max_diff`(additive)。
- `tools/analyzer/validate_sequence_loop.py` — L-3 閘(5 AC)。
- `tools/check_readiness.py` — 新增 cap `sequence_loop_repeat`。
