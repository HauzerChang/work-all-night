# 進度狀態 (STATE) — 續跑核心

> 每次 session 結束前**必須**更新此檔。

## 專案狀態

`ACTIVE`  <!-- SETUP / ACTIVE / BLOCKED / DONE -->

## 目前階段

**專案三階段：第 2 階段(用工具鍛鍊四能力)。**
- 第 1 階段(可視化工具)已完成 → `spine_inspector.html`(含 `window.spineTool` API)。
- **S1 自接點 C1(速度)連續 / C1-loopability(里程碑,2026-10-05 run 002,candidate L-4)** —
  關掉 candidate (L-3) 誠實列出的 honest boundary:`is_loopable` 只驗 **C0**(自接點值連續),明記
  「不保證 C1 速度連續(loop 重啟頓挫)」。本次把 **C1**(自接點速度連續)顯式量化並以閘把關,延續
  L/L-2/L-3/G-2 刻意選整合/組合閘、**不加任何參數軸**。**做了什麼(全 additive)**:①
  `gen_animations.loop_seam_velocity_gap(clip, h=1e-3)` → 自接點 C1 不連續量 `max|v_end−v_start|`
  (跨所有 bone 通道 + slot alpha,單側有限差分;單位=`_state_max_diff` 混合單位每秒;純量測、不改值);
  ②`is_c1_loopable(clip, tol, vel_tol=1.0, h)` = `is_loopable`(C0) **AND** gap ≤ vel_tol(C1 ⇒ C0,
  嚴格更強);③新閘 `validate_sequence_loop_c1.py`(L-4,5 AC)從**先驗庫 → 真實 build_spine robot
  骨架 → build_animations** 端到端(與 L/L-3 同一 fixture)。**5 AC 全 PASS**:**C1a** present+C0 複驗
  +非空驗(Loop 端點速度≈15≥1 否則 C1 判準空驗)、**C1b crux metric 良定義**(Loop gap 對 h∈
  {2e-3,1e-3,5e-4} **bit-stable** 相對差<1e-3→單側差分=端點**切線**非有限差分 artifact;並確認須在
  clip 端點層量,跨 **composed** 接點因 L-3 時間去重被抹平恆 C0,composed wrap 速度差≪clip 端點真
  gap 0.19,量不到真 kick)、**C1c crux Loop C1+通道分解**(Loop gap **0.188**<1 且 `is_c1_loopable`
  =True;通道分解:**剛體 limb rotate 精確 C1**(右手/左手/頭 rotate gap≈1e-12≤1e-6),唯一殘差來自
  **光暈呼吸** scaleY 0.024/alpha 0.188 —— breathing pulse 升後降,自接點速度符號翻轉)、**C1d crux
  C1 獨立於 C0(本 run 核心)**:{Loop,hit,combo,charge,cascade} **全部** `is_loopable`(C0)==True
  → **C0 不能鑑別**;但 C1 gap:Loop 0.188 vs 主秀 hit134/combo109/charge167/cascade64(每個≥10,
  min(主秀)/Loop=**340×**≥50)→ 證 **`is_loopable` 單獨會誤把單發 beat 當『可安全重播』**,C1
  loop-seam 連續是鑑別子;`is_c1_loopable` 對主秀 beat **全 False**、對 Loop True、**C1e 負對照+空驗
  守衛**:(a) **crux** 三角脈衝 scale1→2→1(C0-loopable 但注入速度 kink)gap **2.0**>1 且
  `is_c1_loopable`=False → 閘抓出 `is_loopable` 看不到的頓挫;(b) **空驗守衛** 靜止 clip gap==0
  trivially C1 且 `is_c1_loopable`=True **但**端點速度≈0<1 無運動 → 證「gap≤tol」必要不充分須配非
  靜止(呼應 L-3 LP4);(c) In 非 C0-loopable → `is_c1_loopable`=False 且由 **C0 先否決**。
  **回歸:check_readiness 全綠 0 RED / 57 GREEN**(新增 cap `sequence_loop_c1` L2 併入
  `spine-anim-forge`,仍 HOLD;L-3 等既有 56 閘逐一 GREEN 證兩新純量測函式零回歸)。**關鍵發現**:
  ①**`is_loopable`(C0)會誤把單發主秀 beat 當『可安全重播』** —— 它們首尾皆 setup identity → C0 全
  True,但自接點速度突變 64~167 deg/s(符號翻轉),平鋪會每份頓挫;**C1 是把真 idle-Loop 與一次性
  beat 區分開的鑑別子**(再現本 repo 通則「真簽章常需兩獨立條件並立」,呼應 L-3 的 C0 無縫+非靜止週期);
  ②**同一支 Loop 在不同通道有不同階的連續性** —— 剛體 limb rotate 精確 C1(端點切線完全相等,由週期性
  擺動設計保證),光暈 breathing scale/alpha 只做到 C0(0.19 速度 kick);C1-loopability 看全通道最大
  gap,分解到通道能誠實指認殘差來源;③**C1 metric 良定義須證對取樣步長 h 不敏感(bit-stable=真切線)
  且須在 clip 端點層量**(呼應 L-2/L-3/Z4:「量在哪一層 + 對無關變數是否穩定」決定能否看見真不變量)。
  **honest boundary**:Loop 是否該設計成完美 C1 屬美術手感(A 類,光暈 0.19 kick 為已知邊界);
  vel_tol=1.0 為量級選擇;無改任何 beat 生成/產線值(兩新函式純量測/純判斷);單一真值資產。
  見 `knowledge/s1-sequence-loop-c1.md`。
- **S1 序列內 Loop 重播 N 次 + loopability 不變量(里程碑,2026-10-05 run 001,candidate L-3)** —
  延續 L / L-2 / G-2 的整合/組合閘選題,**刻意不加任何參數軸**。candidate (L) 的 `compose_sequence(anims, order)`
  的 `order` **本就可重複同一 beat 名**(逐一 iterate→查 `anims[name]`→平移 offset→extend),所以
  `order=["In","Loop","Loop","Loop","Out"]` **本就能跑** —— 這正是真實大獎序列的播放形態:進場後 **Loop 重播 N 次**
  (贏分計數滾動時循環待機)再收尾。但 L 的正向序列每 beat **只出現一次**,**從未有閘**驗過「同一支 clip 重複 N 次」
  路徑:①重複鍵 offset 累加;②clip 接在**自己**後面的**自接點**(前份尾→後份首)無縫 = **loopability**(L 只驗過
  **相異** beat 接點);③N 份重播逐幀還原同一孤立 clip(重播機制不漂移);④平鋪為**非靜止嚴格週期**(否則「無縫」空驗)。
  **做了什麼(全 additive)**:①`gen_animations.is_loopable(clip, tol)` —— 判「首幀狀態==尾幀狀態」(所有通道 C0 相等,
  **含 shear**),把「可安全重播」不變量顯式化(純判斷、不依賴既有索引、不改值);附 `_state_max_diff`(與 L 的
  `_state_diff` 同源)供閘複用。介面契約下 Loop/主秀 beat(首尾 identity)loopable;In(collapsed→id)/Out(id→collapsed)
  首≠尾 → **非** loopable。明記:loopable 只保證 **C0**,不保證「有運動」或「C1 速度連續」。②新閘
  `validate_sequence_loop.py`(L-3,5 AC)以 `In→Loop×3→Out` 從**先驗庫 → 真實 build_spine robot 骨架 →
  build_animations** 端到端(與 L/charge 同一 fixture)。**5 AC 全 PASS**:**LP1** present+loopable(Loop)+offset
  累加(segments 恰含 3 個 "Loop" 於 `[0.6,2.6,4.6]`・總時長 `7.0`==In0.6+3·Loop2.0+Out0.4・bone 皆現身)、
  **LP2 crux 自接點無縫**(Loop→Loop self-seam `0.0`<1e-3,= loopability 的 clip 端點層 C0 判準;並確認 compose 產物
  為連續函數 wrap shrink 比 ≈0.1)、**LP3 periodicity/idempotent**(3 份重播各去 offset 逐幀還原孤立 Loop 殘差 `0.0`<1e-4,
  且 3 份彼此逐幀相同→重播不隨份數漂移)、**LP4 non-static+嚴格週期**((a) Loop 內部離 setup 最大位移 `5.0`≥1.0 非靜止
  →無縫非空驗;(b) 平鋪區 `sample(t)==sample(t+Loop_dur)` 殘差 `0.0`→N 份平鋪成恰 N 週期循環)、**LP5 負對照**:
  (a) **crux** In `is_loopable`=False・In→In 自接點 `40.0`>>・**深一層 crux** tiled-In 的 composed 經時間去重後 wrap
  **看起來仍 C0**(shrink 0.1 與合格 Loop 無異)→ 證 loopability **不能從 composed 判**唯 clip 端點 self-seam 揭露;
  (b) Out `is_loopable`=False・Out→Out 自接點 `25.0`;(c) **crux 空驗守衛** 合成**靜止**(恆 identity)clip →
  `is_loopable`=True 且自接點 `0`(trivially 無縫)**但** LP4 非靜止=`0` → 證「光自接點無縫」不足以是有意義 loop
  (須同時非靜止+嚴格週期),LP4 有鑑別力。**迭代踩雷(預算內自修)**:初版 LP2 想從 **composed 時間軸**直接量 wrap
  邊界兩側 C0 跳變(`sample(bt−ε)` vs `sample(bt+ε)`),對合格 Loop 量到 3e-3 誤判 FAIL —— 這是**量測 artifact**
  (捕捉的是 Loop 邊界附近**真實非零速度** end-velocity·ε+start-velocity·ε,非不連續;ε→0 線性縮小)。追查更發現
  `compose_sequence` 的**時間去重**(coincident-time 幀只看時間不看值 collapse 成單幀)會把值不符的接點**抹成陡坡**
  而非真跳變 → composed 取樣**恆 C0**(tiled-In 與合格 Loop 的 shrink 比皆 ≈0.1 無從鑑別);改用 clip 端點 self-seam
  作 crux,composed 連續性僅作佐證。**回歸:check_readiness 全綠 0 RED / 56 GREEN**(新增 cap `sequence_loop_repeat`
  L2 併入 `spine-anim-forge`,仍 HOLD;L 等既有閘逐一 GREEN 證 `is_loopable`/`_state_max_diff` 新增純函式零回歸)。
  **關鍵發現**:①**`compose_sequence` 的時間去重讓 composed 恆 C0** —— 值不符接點被抹成陡坡而非真跳變 → 從 composed
  時間軸永遠看不出一個 beat 是否 loopable;**loop 判準必須在 clip 端點層**(首幀 vs 尾幀),這正是 `is_loopable` 做的事
  (呼應 L-2「量在哪一層決定能看見什麼」);②**「首尾 identity→loopable」是 C0 不是全部** —— 靜止 clip 也 loopable 且
  自接點無縫但平鋪無意義,有意義的 loop 需「非靜止+嚴格週期」兩條件並立(再現本 repo 通則「真簽章常需兩獨立條件並立」);
  ③**重複鍵的 offset 累加/逐幀還原/彼此相同三者並驗**才證重播機制對「同 clip 出現 N 次」正確(L 的相異-beat 路徑驗不到)。
  **honest boundary**:重播次數 N 為 PROPOSAL(A 類);只驗 **C0** 不驗 **C1 速度連續**(loop 重啟頓挫,屬美術/後續);
  無改任何 beat 生成/產線值(`is_loopable` 純判斷,`compose_sequence` 本就支援重複鍵);單一真值資產。見 `knowledge/s1-sequence-loop-repeat.md`。
- **S1 序列組合 shear 通道覆蓋:把 L 的接點/回切/簽章閘補到 shear 兩軸(里程碑,2026-10-04 run 002,candidate L-2)** —
  延續 L / G-2 的整合閘選題,**刻意不加任何生成軸**,只關掉 candidate L 誠實列出的 honest boundary:L 的序列
  延續 L / G-2 的整合閘選題,**刻意不加任何生成軸**,只關掉 candidate L 誠實列出的 honest boundary:L 的序列
  組合閘 `validate_sequence_compose` 用 `spine_anim.sample()` 做接點(前 beat 尾幀 vs 後 beat 首幀)與回切
  (composed vs 孤立 clip)比對,但 **`sample()` 原本只取 rotate/translate/scale/alpha,不取 shear** —— 自 G-4'
  起 wobble/squash/twist 三斜拉節拍會產 `shear` timeline(shearX/shearY),L 的正向序列**刻意只用無 shear 的
  hit/combo/charge/cascade** 繞過這個盲點。**做了什麼(全 additive)**:①`sample()` 納入 shear(per-bone 新增
  `shearX`/`shearY`,預設 0=setup identity;shear timeline 存法同 translate/scale 的 x/y 鍵,以同一 `_interp`
  內插;**加性零回歸** —— 既有索引既有鍵 `["rotate"]`/`["scaleX"]`… 的呼叫端逐位元不變,L 的 `_state_diff`
  迭代其**本地** IDENT 5 鍵亦不受影響,無 shear beat 兩端 shear 皆 0 diff 不變);②新閘
  `validate_sequence_compose_shear.py`(L-2,5 AC)以**含 shear 的序列** `In→wobble→squash→twist→Loop→Out`
  (三斜拉節拍全帶 shear、皆 identity 介面)從**先驗庫 → 真實 build_spine robot 骨架 → build_animations** 端到端
  (與 L/J/charge 同一 fixture)。**5 AC 全 PASS**:**LS1** present+shear 真被驅動(composed 保有 shear timeline・
  `sample()` 現輸出 shearX/shearY 鍵・≥1 shear 段回切後 |shearX| 峰≥5° 實測 15.27°,確認測真 shear 非空驗)、
  **LS2 crux 接點無縫含 shear**(含 shear 序列每內部接點 shear-aware 殘差 **0.0**<1e-3)、**LS3 faithful concat
  含 shear**(回切每段逐幀 shear-aware 還原孤立 clip 含 shearX/shearY 殘差 **0.0**<1e-4 → 證 compose 的時間平移+
  接點去重對 **shear 通道**亦**無損**;compose 本就通道無關,此首次在 shear 上釘住)、**LS4 in-context shear 簽章**
  (回切 wobble/twist 段:shearX **阻尼振盪**繞 0 變號≥3+相繼極值遞減,且 twist **兩軸反相** shearX·shearY<0 在
  序列脈絡仍成立,且 in-context shearX==孤立 clip 純平移無扭曲)、**LS5 crux 盲點負對照(本 run 核心)**:構造
  「**5 非 shear 通道全無縫、只 shear 通道不連續**」接點(wobble 尾 shearX=0 其餘 identity → 合成 `held` clip 首
  shearX=12° 其餘 identity)——(a) **shear-aware** diff=**12.0**>10×SEAM_TOL 正確判非無縫+肇因接點指認
  `wobble->__held`;(b) **crux** 模擬擴充前盲點的 **non-shear** diff=**0.0**<SEAM_TOL(擴充前**會誤判無縫**)→
  證 shear 覆蓋補掉一個**真實**接點盲點(非冗餘);(c) 守衛 純 identity(零 shear)接點 shear-aware diff 仍 **0**。
  **迭代踩雷(預算內自修)**:LS4 初版把 N=48 **稠密取樣**的 shearX 序列直接丟 `_extrema_mags_decreasing`
  (validate_shear_gen 的 helper,原設計吃**關鍵幀**極值序列)→ `damped` 恆 False(稠密序列每峰附近多個相近樣本
  非嚴格遞減);修法新增 `_signed_extrema` 先從稠密序列抽**帶號局部極值**再套變號/遞減判準,等同 validate_shear_gen
  對關鍵幀所做。**回歸:check_readiness 全綠 0 RED**(新增 cap `sequence_composition_shear` L2 併入
  `spine-anim-forge`,仍 HOLD;L 等既有閘逐一 GREEN 證 `sample()` 擴充零回歸)。**關鍵發現**:①**一個驗證器的
  「取樣器覆蓋通道數」決定它能看見哪些不連續** —— `sample()` 漏 shear 使**所有以它為基石**的閘(接點無縫/回切
  還原/in-context 簽章)對 shear **一律盲**;補一條通道=補所有下游閘對該通道的鑑別力(盲點不在各閘邏輯、在共用
  量測基石);②**要證「擴充補掉真盲點」須在同一接點上同時跑擴充前(non-shear)與後(shear-aware)兩種 diff**,
  證前者誤判無縫、後者正確判不連續(只證後者會響不足)—— 鑑別的對象是**驗證器自己擴充前後的能力差**;
  ③**稠密取樣序列套結構簽章判準前先確認量測粒度相容**(抽局部極值,勿把稠密序列當極值序列)。**honest boundary**:
  這是**驗證器覆蓋修正、非新生成能力**(無改任何 beat 生成/產線值,`compose_sequence` 本就 iterate 所有 chans 含
  shear);beat 排序仍 PROPOSAL(A 類);單一真值資產。見 `knowledge/s1-sequence-compose-shear.md`。
- **S1 大獎序列組合:把各 beat clip 串接成單一可播放序列(里程碑,2026-10-04 run 001,candidate L)** —
  承 G-2 的選題精神,**刻意選整合/組合閘**而非再加參數軸(近期多是「單一 robot 加一軸」):`build_animations`
  產出的是**各自獨立**的 beat clip(In/Loop/Out + 主秀 beat + `{beat}__{tier}`),每支首尾 setup identity,
  **設計上**可 runtime 依序播放成無縫大獎序列,**但從未有閘**驗過「真串接成單一 timeline 時:接點無縫 /
  回切逐幀還原 / 各 beat 簽章在序列脈絡中仍成立」——「X 就緒 ≠ 產線成立」通則在**組合層**的實例。
  **全 additive**:`gen_animations.compose_sequence(anims, order)`(純時間平移 `offset_i=Σ_{j<i}dur_j` + 接點
  去重,維持 Spine 時間嚴格遞增)把跨 beat 串接**顯式做出來**,回 `(composed, segments)`;直指 north star
  「產出可播放大獎動畫」。正向序列 `In→hit→combo→charge→cascade→Loop→Out`(排序 PROPOSAL;內部接點全
  identity==identity)。整合閘 `validate_sequence_compose.py`(從先驗庫 → **真實 build_spine robot 骨架** →
  build_animations → compose_sequence)**5 AC 全 PASS**:**L1** well-formed+present(合法 Spine timeline 每通道時間
  嚴格遞增/finite・總時長==Σ段時長・segments 覆蓋序列・用到 bone 皆現身)、**L2 crux 接點無縫**(每內部接點
  跨通道狀態殘差 **0.0**<1e-3)、**L3 faithful concat**(回切每段逐幀還原孤立 clip,殘差 **0.00**<1e-4,純平移
  無值扭曲)、**L4 in-context 簽章**(從 composed 回切主秀段:combo 遞增 impact 峰≥3・cascade 跨件散佈≥0.30・
  charge 峰前長蓄力,且==孤立 clip 量值)、**L5 負對照**(a **crux** burst collapse-起手插中段→其前接點
  `hit->burst` 殘差 **30.0**>>1e-3 → 正確判非無縫、肇因接點確為 `*->burst`;b Out collapse-收尾插中段→其後
  接點殘差大;c **composability 發現** 主秀 beat 彼此對調→仍無縫 0.0 且各段簽章仍成立→證 identity-介面 beat
  **可自由排序**)。**迭代踩雷(預算內自修)**:接點去重初版**丟後者首幀**→ **L3 回切殘差 7.09**(非無損)——
  Spine 緩動 curve **掛在起點幀**,丟後者首幀會連帶丟掉它進入後段的 outgoing curve → 後段首段內插用錯緩動
  (端點值對、中段偏);改**丟前者尾幀**(其 outgoing curve 屬 clip 之末、無意義)、保留後者首幀連其 curve →
  回切 0.00 逐幀還原。**回歸:check_readiness 全綠 0 RED / 54 GREEN**(新增 cap `sequence_composition` L2
  併入 `spine-anim-forge`,仍 HOLD;其餘 53 閘逐一 GREEN 證零回歸)。**關鍵發現**:①**「各 beat 首尾 identity」
  ≠「串起來真的無縫可播放」有 AC** —— 組合層最該放整合閘;②**接點去重的無損性取決於保留帶「正確 outgoing
  curve」的幀**(緩動掛起點幀,去重方向錯會悄悄換掉後段緩動;端點相等會掩蓋 → 必須以回切逐幀還原驗);
  ③**identity-介面構成一個可自由排序的 beat 集合**,進出場(In/Out/burst 的 collapse 端)是唯一位置約束
  (一張 beat 可組性拓樸:自由層 identity↔identity + 起手/收尾層 collapse 端)。**honest boundary(仍在)**:
  beat 排序為 PROPOSAL(手感 A 類);shear beat(wobble/squash/twist)之 shear 通道不被 `sample()` 覆蓋(正向
  序列採無 shear 的 hit/combo/charge/cascade);單一真值資產。見 `knowledge/s1-sequence-composition.md`。
- **S1×S5 整合閘:主秀節拍下 limb 繞關節 pivot 旋轉+縮放(里程碑,2026-10-03 run 002,candidate G-2)** —
  刻意選**整合驗證閘**而非再加一條參數軸(近期 J~J-7/charge count 連續多是「單一 robot 資產加一軸」):把 **S5 的
  關節 pivot**(`infer_pivots` 接觸縫)與 **S1 genre 先驗庫直出的主秀節拍**(hit/combo/charge/burst/cascade)在
  **真實產線接點**上釘回歸閘(呼應 RULES「每能力必配評估器」)。**補的缺口**:0i/G-3 的繞關節 pivot 能力
  (`--pivot-rotate`/`--scale-pivot`)端到端 AC(`validate_pivot_rotation` AC6 / `validate_scale_pivot` AC7)都只在
  **合成 skeleton + 合成單一 beat**(Loop/Win pulse)上驗機制;而 `build_spine` 的 `apply_pivots` 迴圈
  (build_spine.py:351)**逐一掃過所有 animations** → 主秀 beat 的 limb rotate/scale **其實早已**被轉成繞關節版,
  **但從未有 AC 驗過**「真實產線產的主秀節拍下 limb 真的繞關節而非件中心動」。**全 additive**(無改生成/產線碼):
  新增 `validate_pivot_main_show.py`(5 AC)—— 從 genre 先驗庫 → **真實 `build_spine --animate --scale-pivot`
  robot 骨架**(apply_pivots 在 build 內實跑)產 comp 版 + **`--animate` 無 pivot 旗標** raw 版(繞件中心負對照);
  世界變換 `world=(O+T)+R(θ)·diag(sx,sy)·local`;範圍 `cat∈MAIN_SHOW_CATS−SHEAR_CATS`=hit/combo/charge/burst/cascade
  (shear 節拍 wobble/squash/twist 需 `--shear-pivot`,已由 `validate_{twist,squash}_*` 端到端 pivot 殘差 AC 覆蓋,
  本閘不重複)× 有關節 limb/head(右手/頭/左手)。**5 AC 全 PASS(15 組 pair)**:M1 present+routing+零回歸
  (summary 具 pivot_centers/joints、每主秀節拍有補償 limb、非關節件光暈/身體不在 joints、結構節拍 finite)、
  **M2 crux 繞關節不動點**(最差殘差 **0.39px**<0.5 且件最遠點位移≥**40.79px** 真在動)、**M3 負對照繞件中心**
  (逐 pair 比值 **≥147×** 主判準,補償砍關節運動≥20× 處處成立;最大位移 **161px** 量級明顯)、**M4 保設定姿勢**
  (27 個靜止端點補償後 Δ=**0**;**burst 首刻意塌陷登場非 setup→不要求 identity**,其關節仍由 M2 保證不動)、
  M5 isolation+正確轉換集合(非關節件 comp/raw 逐位元同、有差異 bone 集合==恰好有關節 limb 集合,無漏轉/多轉)。
  **迭代踩雷(預算內自修)**:①M4 初版對首尾都要求 identity→**burst 假失敗**(reveal/登場式刻意首幀塌陷 rot25°/scale0.02)
  →改依「不補償版該端點是否本就靜止」決定是否要求 identity;②M3 初版用絕對位移 floor→低幅度 pair(頭)neg=9px 假失敗
  →主判準改**逐 pair 比值**(實測 min 147×),絕對量級只檢最差 pair。**回歸:check_readiness 全綠 0 RED / 53 GREEN**
  (新增 cap `pivot_main_show_integration` L2 併入 `spine-anim-forge`,仍 HOLD;其餘 52 閘逐一 GREEN 證零回歸)。
  **關鍵發現**:①**「apply_pivots 已掃過所有 beat」≠「主秀 beat 下 limb 真的繞關節」有 AC** —— 整合點最該放
  回歸閘(再現「X 就緒≠有 AC 驗 X 在真實產線成立」通則:同 (E) 模板就緒≠產線會用、(0i) 幾何就緒≠生成器接上);
  ②**不是所有主秀節拍都「首尾 setup identity」** —— burst 刻意塌陷登場,identity-介面 AC 必須依「該端點是否本就靜止」
  判定,正確不變量=補償**不在節拍本就靜止處**引入不連續;③**負對照主判準是「逐 pair 比值」非「絕對位移量」**
  (低幅度 pair 絕對位移小但比值仍 147×)。**honest boundary(仍在)**:單一 rig 真值、只非 rig 下套用、shear
  主秀節拍另由他閘覆蓋;主秀手感為美術(A 類)。見 `knowledge/s1-pivot-main-show-integration.md`。
- **S1 charge 蓄力充能階段數隨檔位遞增:count-aware 補齊全部單件主秀 beat(里程碑,2026-10-03 run 001,candidate G-4'''''-charge)** —
  candidate (J) 已讓 charge(anticipate_hold,蓄力充能)的 release 峰**幅度**隨檔位遞增,但各檔位仍**同樣 1 階**單發蓄力
  (有「多爆」沒「蓄幾段」)。本次補上充能-釋放**階段數** `ncharge` 隨檔位嚴格遞增(Super1→Mega2→Omg3→Legend4):
  愈高檔位愈多階蓄力,每階 = 快速下蹲 → **長 hold** 充能 → release overshoot(遞增)→ 微回,末階 release = role peak。
  **關鍵:幅度增益加不出蓄力階段** —— 階數是關鍵幀**拓樸**(dip→hold→release 窗數),須在 `gen_anticipate_hold` 生成當下決定;
  事後 amplify 只能同比放大既有 overshoot。故對 charge 檔位變體以該檔位 ncharge **重生成**,再疊 (J) 幅度增益 g(階數×幅度兩效正交可疊)。
  **charge 獨有 crux(與 combo count 的鑑別 —— 計數簽章須多驗一層)**:combo 與 charge count 的**外形相同**(都是「N 個遞增 scale 峰」),
  **光數 impact 峰無法鑑別**;差別在**峰間**——combo 峰間只有**短** dip(擊間微回 >HOLD_LEVEL 0.97,hold 佔比小),charge 每階在
  release 前有一段**持續**低 hold(sustained,佔該階大半)。故 charge count 簽章在「階數==ncharge」之外**多驗一層**:
  **每一階都是真蓄力階**(該階區間內 scale<0.97 的 hold 佔比 ≥ 門檻)。以此對 combo 做負對照 → combo 每階 hold 佔比 ≤0.34 < 門檻 0.60
  → **FAIL charge-count 簽章**,證「數峰 + 每階持續 hold」兩條件並立才是 charge count(呼應 J-3「真簽章常需兩獨立條件並立」)。
  全 additive:`gen_anticipate_hold(role,side_sign,radial,ncharge=1)`(`ncharge==1` 走手調 golden 分支逐位元向後相容,
  `ncharge>1` 走 `_charge_env` 通用多階包絡,首階 release 夾 ≥IMPACT_PROM、階間微回 0.975>HOLD_LEVEL 不併入下一階 hold、末階後
  settle 尾峰 <IMPACT_PROM)+ `charge`∈`COUNT_AWARE_CATS`(純 scale,非 SHEAR/COUPLED → 逐軸 amplify)+ `TIER_CHARGE_CYCLES`
  {slot_bigwin:{Super1,Mega2,Omg3,Legend4}}+`charge_cycles_for`+`build_animations(tier_charge_cycles=)` 的 `_count_maps` 加 `"charge"` 鍵依 cat 路由
  + `build_spine --tier-variants` 透傳。整合閘 `validate_charge_count.py`(先驗庫→**真實 build_spine robot 骨架**→
  build_animations(tier_gains,tier_charge_cycles))**5 AC 全 PASS**:CC1 present+backward-compat(每檔位 `charge__{tier}` 有 bone/finite・
  base charge 恆 1 階逐位元同無檔位・`charge__Super`(ncharge=1,g=1)逐位元==base・tcc=None 逐位元同 (J) 幅度-only)、
  CC2 **crux stage count monotone**(階數[= impact release 峰數]==宣告 [1,2,3,4] 嚴格遞增、Super==base 1)、CC3 每檔位仍
  (a) 首尾 setup identity 可插 Loop (b) 具 charge 簽章(峰前長蓄力佔比≥0.35 且峰前非塌陷 >SQUASH_FLOOR 非 reveal)
  (c) **每一階 hold 佔比 ≥0.60**(crux 多驗層,實測每階 min 0.707)(d) 階內 release 峰嚴格遞增(末階=role peak)**且**峰幅仍隨檔位遞增、
  CC4 正交(a 階數+平增益→階數遞增·峰幅**不**遞增 b 增益+無階數→階數恆1·峰幅遞增)、CC5 負對照(a 平階數全1→單調 FALSE
  b **crux combo 判別子** combo 變體(同為 N 遞增峰)每階 hold 佔比 0.31–0.34 < 0.60 → FAIL charge-count 簽章,且 combo 確有 ≥3 遞增峰
  → 證「每階持續 hold」是鑑別子非「combo 沒峰」 c 階數只作用 charge:非-charge 主秀變體逐位元同幅度-only・slot_reveal `charge_cycles_for` None 不亂加)。
  端到端 `build_spine --animate --tier-variants` 直出 `charge__{Super1,Mega2,Omg3,Legend4}`。**回歸:check_readiness 全綠 0 RED / 52 GREEN**
  (新增 cap `charge_tier_count_aware` L2 併入 `spine-anim-forge`,仍 HOLD;其餘 51 閘逐一 GREEN 證零回歸)。**關鍵發現**:
  ①**count-aware(段數軸)至此補齊全部單件主秀 beat**:combo(連擊數)/wobble(振盪段)/squash(擠壓段)/twist(扭轉段)/
  **charge(蓄力階)** 五通道 + cascade 跨件波掃次數(J-3);②**外形相同的兩種 count 必須靠「峰間行為」鑑別**——combo 與 charge count
  都是「N 遞增 scale 峰」,只數峰會混為一談,真鑑別在峰間(combo 短 dip vs charge 持續 hold),計數簽章要多驗「每階是否保有該 beat
  的本質簽章」(否則加階會悄悄把 charge 退化成 combo);③向後相容錨點選 base 自然值(charge golden 單發 → Super=1,同 cascade nrip)。
  **honest boundary(仍在)**:階數階梯 [1,2,3,4] 為 PROPOSAL(手感 A 類);上界 4(charge T=0.8s 窗容量);單一真值資產。
  見 `knowledge/s1-charge-tier-count.md`。
- **S1 cascade 波方向由件幾何自動導出:把 J-6 方向軸的「取值來源」由手感常數下推成幾何導出(里程碑,2026-10-02 run 002,candidate J-7)** —
  承 (J-5)/(J-6):同一條方向軸的三次精煉,逐步把「用哪個方向」從人手移開。J-5 把相位來源從件序換成**空間**(4 具名
  `lr`/`rl`/`co`/`oc`)、J-6 把其值**連續化**(任意角/向量),**但「用哪個方向」仍是 per-genre 手感常數**
  (`tier_variants.TIER_CASCADE_DIR`,如 `slot_bigwin→"co"`)。本次新增 sentinel `cascade_dir="geo"`:方向**向量由件實際
  幾何導出**(`derive_cascade_dir`:件質心 → 距質心**最遠件**的單位向量;確定性、無 PCA ±符號歧義),隨資產自適應、不再寫死。
  **crux(J-7 的 honest distinction,勿誇大)**:J-7 **不是**新正交軸 —— 導出的方向向量**導出後仍走 J-6 的投影排序(同機制:
  既有相位的重新指派)**;J-7 只把方向軸的**取值來源(provenance)從「人手給」換成「幾何導出」**(J-5 空間化→J-6 連續化→
  J-7 自動化,逐步移除人手指定)。跨件時序通道仍是三條正交軸(結構 nrip × 幅度 span × 方向 dir)。全 additive:新增
  `derive_cascade_dir(centers, source="centroid_farthest")`(退化幾何/空件/未知 source→`ValueError`)+ `_normalize_cascade_dir`
  認 `"geo"`/`("geo",source)` marker(置於通用 length-2 向量分支**前**,否則 `("geo",src)` 被誤當 `(ux,uy)` 而 `float("geo")` 爆錯)
  + `_cascade_phase_of` 的 `kind=="geo"` 用**當前 beat 有效件中心**導出向量再落 J-6 投影路徑;`build_spine --cascade-dir geo`(或 `geo:SOURCE`,
  `_parse_cascade_dir`)。`None`/`"po"`/具名/角度/向量路徑逐位元不變。整合閘 `validate_cascade_dir_geo.py`(先驗庫→**真實 build_spine
  robot 骨架**→build_animations(cascade_dir="geo");geo 向量**由閘自行獨立重算**保持獨立驗證)**5 AC 全 PASS**:W1 present+
  backward-compat(geo 產每 cascade beat 有 bone/finite・非 cascade 主秀 beat 逐位元同 base・po==None)、W2 **crux derived projection
  ordering**(峰時刻依閘獨立導出的質心→最遠件投影鍵嚴格遞增:robot 導出 vec≈`(0.974,0.228)`(13.2°,指向最遠件左手)、波序
  `[右手,光暈,身體,頭,左手]` 時刻 0.158→0.70、**最遠件左手最後 pop**)、W3 geo 仍一道有序跨件波(散佈≥0.30)+首尾 setup identity
  +特效 slot alpha=1、W4 正交(新方向下仍保 (a) dir⟂深度:geo 峰 overshoot==base,HIRES 量 (b) dir⟂nrip:帶 ripples 各件 pop 次數==nrip
  (c) dir⟂span:帶 span 跨件散佈==宣告 span)、W5 負對照(a **crux data-derived discriminator**:同一 `cascade_dir="geo"` 套在**兩個
  不同幾何**——真實 robot(vA≈13°)vs 把「頭」沿 +y 推遠 1200 成最遠件的變體(vB≈92°)——**導出向量不同**且**波序不同**,各自
  **吻合自身幾何**的質心→最遠件投影序 → 證方向**由資料導出、非常數** b 導出向量/波序==閘獨立重算(robot)且最遠件最後 pop
  c geo 波序 ≠ 手感常數 `"co"`(現 `cascade_dir_for(slot_bigwin)`)/≠oc/≠件序 po/≠lr/≠rl → J-7 與所有 J-5 具名 + 現行手感預設皆不同
  d 輸入守衛 未知 geo source/空件/退化幾何(件重合→零方向)→ValueError)。端到端 `build_spine --animate --cascade-dir geo` 直出
  由幾何導向的掃波。**回歸:check_readiness 全綠 0 RED**(新增 cap `cascade_dir_geo` L2 併入 `spine-anim-forge`,仍 HOLD;J-6
  `cascade_dir_vector` 等既有閘逐一 GREEN 證零回歸)。**關鍵發現**:①**「離散→連續」(J-6)之後的下一個通用槓桿是「人手給→資料
  導出」**——凡「某軸的值由人手常數提供」都可問「能否由資產本身的幾何/統計量導出?」,把人手從迴圈再拿掉一層;②**要證「值是
  資料導出、非常數」必須在兩個不同輸入上證輸出跟著變**——單一資產上「導出值==某幾何量」只是巧合對上,真正鑑別是**換一個幾何**看
  導出方向是否跟著轉(W5a);③**幾何導出要挑「無符號歧義」的量**(質心→最遠件天然有向;PCA 主軸只給一條線、正負須另定,反而
  把移除的人手又加回來);④**踩雷:質心反射+重新導出=不變**——反射後導出方向也翻號 → 投影鍵 `k'=k−const`(減常數不改排序)→
  波序**不變**,兩翻號相消、鑑別力為零;改用「只改資料不自我抵消」的變換(把某件搬到新位置成最遠件,方向大幅轉向而非翻號)。
  **honest boundary(仍在)**:J-7 **不是新軸**,是方向軸取值來源的自動化;`source` 選擇(目前只 `centroid_farthest`)與**最終
  手感微調**仍 PROPOSAL(A 類);單一真值資產(robot)。見 `knowledge/s1-cascade-dir-geo.md`。
- **S1 cascade 波方向一般化為任意角投影:把 J-5 的方向軸由 4 向離散補成連續(里程碑,2026-10-02 run 001,candidate J-6)** —
  承 (J-5):J-5 把 cascade 跨件波的**相位來源**從件序換成空間,給方向軸 4 個**具名**取值(基數軸 `lr`/`rl` + radial `co`/`oc`)。
  本次把這**同一條方向軸由離散補成連續**:方向可給**角度(度)或向量 `(ux, uy)`**,相位依件中心在該單位向量上的**投影**
  `k = x·ux + y·uy` 排序(相位值仍 `rank/(nvalid−1)∈[0,1]`,只是 rank 的排序鍵換成任意方向投影)。
  **crux(J-6 的 honest distinction,勿誇大)**:J-6 **不是**第四條正交軸 —— J-5 已把「方向/相位來源」立為第三軸
  (結構 nrip × 幅度 span × 方向),J-6 只把這**同一條方向軸**的**取值**由「4 具名」擴成「連續角 + 任意向量」;機制仍是
  J-5 的「既有相位的重新指派(排列)」,只是**排序鍵**從 `{基數軸 ±x, radial}` 擴成 `{任意投影角, radial}`。價值 =
  對角/垂直/任意角的波,J-5 的 4 向**表達不了**(垂直 90°=`k=y` 在 robot 產波序件序 index `[3,0,4,1,2]`,4 向皆做不出)。
  一般化務必分清**含與不含**:投影族**含** `lr`/`rl`(基數軸=θ=0°/180° 特例,逐位元相容)但**不含** `co`/`oc`(radial 是 2D
  非線性,任何單一投影都無法重現徑向序,保留為各自特例)。全 additive:新增 `_normalize_cascade_dir`(方向規格→`(kind,
  payload)`:po/proj/co/oc,角度→`(cosθ,sinθ)`、向量→正規化單位向量,零向量/長度≠2/bool/未知字串→`ValueError`)+
  `_cascade_phase_of` 改走統一排序鍵;`build_spine --cascade-dir` 吃角度(如 `90`)/向量(如 `"1,1"`)(`_parse_cascade_dir`);
  具名 lr/rl/co/oc/po/auto 不變。整合閘 `validate_cascade_dir_vector.py`(先驗庫→**真實 build_spine robot 骨架**→
  build_animations(cascade_dir=角度/向量))**5 AC 全 PASS**:V1 present+backward-compat(每新方向 90°/270°/45°/135°/向量皆有
  bone・**投影族含具名**:角度 0°/180° 與向量 (±1,0) 逐位元==`lr`/`rl`・po==None・非 cascade beat 不受影響)、V2 **crux
  projection ordering**(每新方向峰時刻依投影鍵 `x·ux+y·uy` 嚴格遞增=任意角波序=投影序)、V3 每新方向仍一道有序跨件波
  (沿投影序散佈≥0.30)+首尾 setup identity+特效 slot alpha=1、V4 正交(新角/向量下仍保 (a) dir⟂深度:HIRES 量峰 overshoot
  跨方向相同 (b) dir⟂nrip:帶 ripples 各件 pop 次數==nrip (c) dir⟂span:帶 span 跨件散佈==span)、V5 負對照(a **crux
  discriminator** 垂直90° 實測峰序 `[3,0,4,1,2]`・對角45° `[3,0,1,2,4]` ∉ 全部 J-5 件序集合 `{po,lr,rl,co,oc}` 證任意角投影
  是**真新方向非換名** b 連續性/端點 0°==lr・180°==rl・90° 兩者皆非(lr/rl 為投影族端點,內部為新)c 投影≠radial:crux 峰序
  ≠co/oc d 輸入守衛 零向量/長度≠2/bool/未知字串→ValueError)。端到端 `build_spine --animate --cascade-dir 90` 直出垂直掃波;
  `validate_build` round-trip overall_pass。**回歸:check_readiness 全綠 0 RED**(新增 cap `cascade_dir_vector` L2 併入
  `spine-anim-forge`,仍 HOLD;J-5 `cascade_dir_spatial` 等既有閘逐一 GREEN 證 lr/rl/co/oc 零回歸)。**關鍵發現**:①**離散→
  連續本身是通用槓桿**——凡是「挑了幾個具名值」的軸,問「這些具名是不是某連續參數的取樣?」往往能一般化(lr/rl 正是連續角
  θ=0°/180° 的取樣);②**一般化時務必分清「含」與「不含」**——誠實的一般化要說清楚哪些舊值被收編成特例(lr/rl)、哪些是
  另一族保留(co/oc radial);③**零回歸的來源是「特例逐位元相等」而非「預設不變」**——lr 的投影 `k=x·1+y·0` 在浮點下 `y·0=0`、
  `x·1=x` 精確 `=x`,與 J-5 直接 `k=x` 逐位元相等 → 想宣稱向後相容要證舊值在新路徑下**逐位元**重現,不能只證預設沒變。
  **honest boundary(仍在)**:J-6 **不是新正交軸**,是方向軸的連續化(取值擴充),跨件時序通道仍是三條正交軸;方向選擇
  (具體用哪角/向量)為 PROPOSAL(手感 A 類);單一真值資產(robot)。見 `knowledge/s1-cascade-dir-vector.md`。
- **S1 cascade 跨件波方向由空間位置決定:跨件時序通道第四條正交軸——相位來源(里程碑,2026-10-01 run 002,candidate J-5)** —
  補 (J-4) 的 honest boundary:至 (J-4) 為止 cascade 各件相位恆為**件序** `pi/(nvalid−1)`,波的**方向** = 作者把件寫進
  storyboard 的**列表順序**(任意/排版,**無物理意義**)。本次把相位的**排序鍵**換成**空間座標**:`lr` 左→右(bd.x 升序)/
  `rl` 右→左/`co` 中心外擴(距畫布中心升序)/`oc` 外向內 —— 波方向變成幾何。相位值仍 `rank/(nvalid−1)∈[0,1]`,
  **波形(SPAN/nrip/深度)分毫不動** → 只重排「哪件何時 pop」。**crux(J-5 的 honest distinction)**:這不是新幅度/段數軸,
  而是**同一道波的方向來源**從件序換成幾何;機制**既非值增益**(深度軸 `v'=g·v`)**也非重生成**(count/span 軸),而是
  **既有相位的重新指派(排列)**——第三種最輕量機制(O(n log n) 排序)。要證「真由空間決定、非換名的件序」,須在
  **件序 ≠ 空間序** 的真實資產上證峰序**跟空間走不跟件序走**:robot 件序 `[光暈,右手,頭,身體,左手]`(x=359,320,361,394,558)
  **非** x 排序(x 最小的右手排件序第 2)→ `lr` 下右手(件序 index 1)比光暈(件序 index 0)**更早** pop,件序相位下不可能。
  全 additive:新增 `_cascade_phase_of`(依方向空間鍵給 rank,tie-break 件序 index)+ `build_animations(cascade_dir=)`/
  `build_spine --cascade-dir{lr,rl,co,oc,auto}`;`cascade_dir=None`/`"po"` 逐位元同件序(向後相容);`tier_variants.cascade_dir_for`
  回 genre 建議(slot_bigwin→co,**opt-in**,預設 None 零回歸)。整合閘 `validate_cascade_dir.py`(先驗庫→**真實 build_spine
  robot 骨架**→build_animations(cascade_dir))**5 AC 全 PASS**:Z1 present+backward-compat(每方向有 bone・po 逐位元==None・
  非 cascade beat 不受影響)、Z2 **crux spatial ordering**(每方向峰時刻依該方向空間鍵嚴格遞增:lr→x 升 [0.158,0.296,0.429,0.567,0.70]・
  rl→x 降・co→徑向升・oc→徑向降)、Z3 每方向仍一道有序跨件波(散佈≥0.30)+首尾 setup identity 可插 Loop、
  Z4 正交(a dir⟂深度:同件峰 overshoot 跨方向相同——**踩雷**:N=240 離散 argmax 量深度有 ~0.008 混疊 artifact,隨 n 二次收斂
  →改 HIRES=9600 量,殘差 3e-4<<1e-3;b dir⟂nrip:帶 ripples 各件 pop 次數==nrip;c dir⟂span:帶 span 跨件散佈跨方向恆==span,
  相位集合只被排列→min/max 不變)、Z5 負對照(a po 逐位元==None;b **crux discriminator** lr 峰序==x 排序 且 ≠件序——
  x 最小件非件序第一件卻最先 pop,證相位來源是空間非件序;c 方向只作用 cascade 非-cascade 逐位元同 None;d 未知方向字串→ValueError 輸入守衛)。
  端到端 `build_spine --animate --cascade-dir co` 直出 cascade(中心外擴:光暈 @0.192 先、左手 @0.842 末);`validate_build`
  round-trip overall_pass(premult MAE 0.031)。**回歸:check_readiness 全綠 0 RED**(新增 cap `cascade_dir_spatial` L2 併入
  `spine-anim-forge`,仍 HOLD);cascade 四兄弟閘 + tier_variants + build round-trip 全 PASS。**關鍵發現**:①**波的方向本是一個
  隱含假設**——J-5 之前「依件序掃」寫死(件序即波向),J-5 把波向從作者排版順序解放成可由幾何指定的物理方向(**把隱含預設
  顯式化成一條可控軸**);②跨件時序通道至此**三條正交軸**:結構(nrip,J-3)× 幅度(span,J-4)× 方向/相位來源(J-5),三者機制
  各異(重生成 / 重生成 / 相位重排);③**離散取樣的混疊會假扮成「軸不正交」**——Z4(a) 初 FAIL 根因是量深度的混疊(時移把峰挪到
  不同幀相位),非真深度變化,證法=加密取樣看殘差是否**二次收斂到 0**(量不變量前先確認量測對無關變數不敏感)。
  **honest boundary(仍在)**:方向選擇(co)為 PROPOSAL(手感 A 類);`co` 在此 fixture 巧合等於件序(鑑別用 lr/rl/oc);
  單一真值資產。見 `knowledge/s1-cascade-dir-spatial.md`。
- **分析器真值閘 ④ 分鏡結構判準:嚴格相等 → 召回(修 pre-existing RED;里程碑,2026-10-01 run 001,candidate ENV-fix)** —
  修掉累積數個 session 的 pre-existing RED:`tools/analyzer/validate_analyzer_award.py` 的 `4_storyboard_structure` 閘。
  **根因**:主秀 beat 生成系列(E/H/I/J…G-4'''''')一路把 **8 個節拍**(burst/cascade/charge/combo/hit/squash/twist/wobble)
  併進 `genre_priors.slot_bigwin` → `proposed_beats` 現 11 個;但 Award 動畫只命名結構 beat `{In,Loop,Out}`(命名 `Award_<tier>_In/Loop/Out`),
  那 8 個主秀 beat 在 Award **無對應命名動畫** → 原判準 `beats_ok = proposed_beats == beat_kinds`(**嚴格集合相等**)永遠 False → 閘 RED。
  **非回歸**(已於上個 session 用 `git stash` 在 clean J-3 tree 59cf2b2 確認同樣 RED;J-4 純加性)。此閘被 `check_readiness.py` 兩個 skill 區塊引用(line 58、88)→ 顯示為 **2 個 RED**。
  **修法 = 召回(recall),非嚴格相等**:正確語意是「Award 命名的每個結構 beat 都被提出(`award ⊆ proposed`)」,分析器額外提出、Award 未命名的主秀 beat 是 **PROPOSAL**,
  誠實列出但不算 match 失敗 —— **完全比照 `validate_priors.py` 既有的 `prior_beats_unused` + coverage 門檻**(那裡早已非 exact-equal)。抽出純函數
  `beat_structure(proposed,award,proposed_tiers,award_tiers)`,回報 `beats_covered`(=`award⊆proposed`,**真正判準**)、`beats_match`(=嚴格相等,**仍一併回報作透明佐證**,現 False)、
  `beats_proposal_only`(=那 8 個主秀 PROPOSAL,誠實攤開)、`pass=beats_covered and tiers_hit≥1`。docstring ④ 同步改「是否**涵蓋** Award 命名結構(召回)」。
  **閘仍可信(負對照固化成 `--selftest`,純邏輯不讀資產,9 斷言全 PASS)**:POS 涵蓋→pass 且 beats_match=False 且 proposal_only 恰 8;NEG 漏 `In`(Award 有的)→`beats_covered`=False→fail(**真漏召回時閘仍 fail**);
  NEG 漏 Loop/Out→fail;NEG 0 檔位→fail(保留 tier 條件);EXACT 提案==Award→pass 且 beats_match=True(證放寬只「加容忍 PROPOSAL extras」,未改嚴格情形行為)。
  **結果**:`validate_analyzer_award.py` overall_pass=True/exit 0/`4_storyboard_structure.pass`=True;`check_readiness.py` **2 個 analyzer `gen` 閘 RED→GREEN**,其餘動畫/功能閘全綠不動(**0 RED / 48 GREEN,0 GREEN→RED**)。
  **自此 repo 真正全綠**,不再需要每個里程碑附「另有 2 個 analyzer 閘 RED」的 caveat。**關鍵發現**:①一個隨「累積先驗」逐步偏離初衷的**過嚴判準**會悄悄變成長期 RED —— 真值閘對「PROPOSAL 多於真值命名」應走**召回 + 誠實列未對上項**(同 `validate_priors`),不是 exact-equal;
  ②放寬判準必附**負對照**證「仍能抓真漏召回」,否則等於拆閘。**honest boundary**:這是**閘語意修正、非新能力**(分析器件召回/特效/幾何/露出判準全未動;主秀 beat 仍先驗手感 PROPOSAL);`spine-anim-forge` 仍 HOLD,成熟度不變。見 `knowledge/s1-analyzer-storyboard-recall-gate.md`。
- **S1 cascade 跨件波散佈幅度隨檔位遞增:跨件時序通道的「幅度式」軸,揭示『幅度』未必用幅度機制(里程碑,2026-09-30 run 001,candidate J-4)** —
  補 (J-3) 的另一條正交軸:(J-3) 讓 cascade **波掃次數** nrip 隨檔位遞增(掃**幾道**波=跨件時序通道的**結構/拓樸**軸),
  但一道 sweep 內各件峰時刻的散佈在所有檔位仍固定(base SPAN=0.54)。本次補上**散佈幅度** span 隨檔位嚴格遞增
  (Super0.54→Mega0.58→Omg0.62→Legend0.66):愈高檔位波掃**愈開**(跨件錯開愈戲劇)。跨件時序通道至此有**兩條正交軸**:
  結構(nrip,J-3)× 幅度(span,J-4)。**crux(J-4 的核心新意 = honest distinction)**:此前所有「幅度」軸(J 主秀增益、
  wobble/squash/twist tier 峰增益)都用 **post-hoc 值增益** `g`(`v'=g·v`)實現——放大的是關鍵幀的**值**。span 語意也是
  「幅度」(愈大波掃愈開),照理應照搬 g;**但不能** —— 跨件散佈活在關鍵幀的**時間位置**(峰中心 `c_k=(LEAD+p·span)/nrip`)
  **不在值**;值增益只放大每件 pop 的**深度**(scale 峰值 overshoot),各件峰**時刻分毫不動** → 散佈不變。故 span 雖語意
  屬幅度,機制上必須 gen 當下**重生成**(同 count 軸),是「**time-position domain 幅度** vs **value domain 幅度**」的分野
  (span 語意像幅度、機制像 count)。全 additive:`gen_cascade(span=None)`(None→`CASCADE_SPAN`=0.54 逐位元同基礎);
  新增 `TIER_CASCADE_SPAN`+`cascade_span_for`;`build_animations(tier_cascade_span=)` 對 cascade 變體以該檔位 span **重生成**
  (與 `count=nrip` 並存 → nrip 道各以該檔位 span 散佈,兩軸皆重生成、可同時帶入);`_build_beat` 的 `_PHASE_AWARE` 分支
  吃 `cascade_span`;`build_spine --tier-variants` 透傳。上界 `span<0.68`(末件末幀 `(LEAD+span+0.16)/nrip<1`,任一 nrip 首尾仍
  identity),Legend 0.66 餘裕 0.02。整合閘 `validate_cascade_span.py`(先驗庫→**真實 build_spine robot 骨架**→
  build_animations(tier_gains,tier_cascade_span))**5 AC 全 PASS**:Y1 present+backward-compat(base 逐位元不變、Super
  span-only 逐位元==base、tcs=None 逐位元同 (J) 幅度-only)、Y2 **crux 隔離量測(nrip 固定=1)** 跨件散佈
  [0.5417,0.5833,0.6208,0.6625] 嚴格遞增且==宣告 span(誤差≤2/240)・每檔位仍依件序遞增(散佈變大不打亂波序)、
  Y3 每檔位仍具 cascade 簽章(遞增+散佈≥0.30)+首尾 setup identity 可插 Loop、Y4 正交(a span+平增益→散佈遞增·深度
  **不**遞增(恆 0.3363)、b 增益+無 span→散佈**恆==base**(0.5417×4)·深度遞增、c span⟂nrip pop 次數==nrip 不受 span 干擾·
  固定 nrip 下 span>base 者每道 sweep 更寬)、Y5 負對照(a 平 span→單調 FALSE、**b crux honest-distinction** post-hoc 值增益
  amplify(g=2.1)→深度 0.34→0.71 變大**但散佈 0.5417==0.5417 不變** 證 span 軸無法由幅度機制產生·非重生成不可、
  c slot_reveal `cascade_span_for` None 不亂加·span 只作用 cascade 非-cascade 變體逐位元同幅度-only)。端到端
  `build_spine --animate --tier-variants` 直出 `cascade__{Super,Mega,Omg,Legend}`(散佈隨檔位漸開)。**回歸:24 個動畫/功能閘
  全綠 + 新 cascade_tier_span**(`check_readiness.py` 新增 cap;⚠️ **另有 2 個 PSD analyzer `gen` 閘 RED,但為
  pre-existing 環境漂移**——`validate_analyzer_award.py` 的 `4_storyboard_structure.beats_match` 因累積先驗提出 8 個主秀 beat
  vs Award 只有 In/Loop/Out 而 False,**已確認在 clean J-3 tree(59cf2b2)同樣 RED,與 J-4 無關**;見未解問題)。新增 cap
  `cascade_tier_span` L2 併入 `spine-anim-forge`(**仍 HOLD**)。**關鍵發現**:①跨件時序通道有兩條正交軸(結構 nrip × 幅度 span);
  ②**「幅度」未必用幅度機制**——當一個「幅度式」量活在關鍵幀的**時間位置**而非**值**時,post-hoc 值增益加不出來,必須
  **重生成**(value domain 幅度 vs time-position domain 幅度的機制分野);Y5(b)乾淨證此(同一 amplify 對深度有效、對散佈無效)。
  **honest boundary(仍在)**:散佈階梯(0.54–0.66)為 PROPOSAL(手感 A 類);span 上界 0.68;單一真值資產。
  見 `knowledge/s1-cascade-tier-span.md`。
- **S1 cascade 跨件波掃次數隨檔位遞增:第一個「跨件時序」通道的 count-aware(里程碑,2026-09-29 run 002,candidate J-3)** —
  補 (J-3) 的 honest boundary:candidate (J) 讓 cascade 波峰**幅度**隨檔位放大,但各檔位仍是**同一道**跨件波
  ——「掃得多猛」有了、「掃幾道」沒有。本次補上波掃次數 `nrip` 隨檔位嚴格遞增(Super1→Mega2→Omg3→Legend4)。
  **crux(與四個單件 count 本質不同)**:combo/wobble/squash/twist 的 count 是**單件內**極值數(同一件連幾下,
  段數落在單件曲線,∈`COUNT_AWARE_CATS`);cascade 的 nrip 是**跨件波掃幾道**(段數落在**跨件時序**通道,
  cascade∈`_PHASE_AWARE`)—— **第一個落在跨件通道的 count-aware 軸**。生成:整段 τ 均分 `nrip` 個窗,第 k 窗是
  壓縮版跨件 sweep(該件中心 `c_k=(k+LEAD+p·SPAN)/nrip`、包絡寬壓縮 `1/nrip` → 窗間隙 `0.75/nrip>0` 互不重疊、
  首尾仍 identity);每件 pop `nrip` 次、整體掃 `nrip` 道有序波;**nrip==1 逐位元同基礎單 sweep cascade**(向後相容)。
  **幅度 amplify 加不出第二道 sweep**(拓樸=gen 時決定的關鍵幀窗)→ 對 cascade 檔位變體以該檔位 `nrip` **重生成**
  再套單一-g 幅度增益(波掃道數×幅度兩效正交可疊,比照 combo/wobble 的段數重生成)。全 additive:新增
  `TIER_CASCADE_RIPPLES` + `cascade_ripples_for`;`gen_cascade(nrip=)`;`build_animations(tier_cascade_ripples=)`
  把 cascade 併入 `_count_maps`(cmap 查詢改 `_count_maps.get(cat)`)、`_build_beat` 的 `_PHASE_AWARE` 分支吃
  `count=nrip`;`build_spine --tier-variants` 透傳。整合閘 `validate_cascade_count.py`(先驗庫→**真實 build_spine
  robot 骨架**→build_animations(tier_gains,tier_cascade_ripples))**5 AC 全 PASS**:X1 present+backward-compat
  (每檔位有 bone、base 恆1道逐位元不變、**Super 逐位元==base**、tcr=None 逐位元同 (J) 幅度-only)、X2 **crux**
  波掃次數 [1,2,3,4] 嚴格遞增且每檔位所有件 pop 次數一致==nrip、X3 **crux 跨件多驗一層** 每檔位**每一道 sweep**
  的各件第 k 峰時刻依件序嚴格遞增且散佈 ≥0.6·SPAN/nrip(每道波皆有序跨件波非切碎)+每檔位首尾 setup identity
  +幅度峰仍遞增、X4 正交(ripples+平增益→波掃次數遞增·峰幅不遞增;增益+無 ripples→波掃次數恆1·峰幅遞增)、
  X5 負對照(平波掃次數全1→單調 FALSE、slot_reveal `cascade_ripples_for` None 不亂加、ripple 只作用 cascade
  非-cascade 主秀變體逐位元同幅度-only 不外洩)。端到端 `build_spine --animate --tier-variants` 直出
  `cascade__{Super,Mega,Omg,Legend}`;round-trip `validate_build` overall_pass(premult MAE 0.031)。**回歸 25 閘全綠**
  (24 既有 + 新 cascade_tier_ripple_count;`check_readiness.py` 退出 0,0 RED,無 GREEN→RED)。新增 cap
  `cascade_tier_ripple_count` L2 併入 `spine-anim-forge`(**仍 HOLD**)。**關鍵發現**:**結構(段數)軸已在
  combo/wobble/squash/twist **四個單件通道** + cascade **跨件通道** 成立**;**跨件 count 的簽章需比單件 count
  多驗一層「每道 sweep 仍保跨件排序」**(單件 count 只驗峰數;跨件 count 若只驗「每件 pop nrip 次」會漏掉
  「這 nrip 道波是否各自仍有序」→ 可能把一道有序波切碎成雜訊仍過峰數關)—— 呼應「真簽章常需兩獨立條件並立」
  (cascade 散佈+遞增、squash 守恆+非均勻、twist 反相+雙軸)。**honest boundary(仍在)**:波掃次數階梯 [1,2,3,4]
  為 PROPOSAL(手感 A 類);單一真值資產。見 `knowledge/s1-cascade-tier-ripple-count.md`。
- **S1 volume-conserving twist 接檔位差異化:補償 scale 依放大後 shear 非線性重算(里程碑,2026-09-29 run 001,candidate G-4''''''-vol-tier)** —
  補 (G-4''''''-vol) 明列的**最後一條 honest boundary**(「vol 僅作用 base twist;tier 變體仍 shear-only,vol 隨檔位放大需
  **重算補償 scale** 維持 det≡1,比照 squash 耦合 amplify」)。tier 放大把兩軸 shear 同比拉大(`shearX'=g·shearX`、
  `shearY'=g·shearY` → 兩基底夾角偏離 `Δ'=(shearX−shearY)·g`)→ 真正的守恆補償變成 `s'=1/√cos(g·Δ)`,對 g **非線性**(cos)。
  `amplify_bone_tl(twist_vol=True)`:**先放大 shear**、再**依放大後 shear 重算**每個 scale 極值的等向 s
  (`_recompute_twist_scale_iso`,捨入比照 gen_twist → g=1 逐位元同 base)→ 全域 local `det≡1` 於**任一檔位**保持,
  補償量隨檔位非線性遞增。**crux(與 squash G-4''''' 耦合 amplify 對比)**:squash 耦合是 `sy'=1/sx'`(倒數、與 shear 無關,
  scale 本身即擠壓);twist 補償是**依放大後 shear 重算的等向 s**(cos 反推、值來自 shear)—— 同為建構保證跨通道約束
  **但不同源**;逐軸線性 `_amp_scale`(`1+g·(s−1)`)追不上非線性 cos 曲線 → 破守恆(VTT3 負對照 Legend 0.11–0.31)。
  全 additive:新增 `VOL_TWIST_CATS={twist}`;`build_animations(twist_volume=True, tier_gains=…)` 對 twist 檔位變體路由
  `twist_vol` 重算(shear 迴圈移到 scale 之前;段數 `tier_twist_cycles` 重生成的變體亦帶 `twist_vol` → 段數×幅度×守恆
  三效正交);`build_spine --animate --tier-variants --twist-volume --shear-pivot`(twist_volume 早已透傳,無需改 build_spine)。
  整合閘 `validate_twist_volume_tier.py`(先驗庫→**真實 build_spine robot 骨架**→build_animations(tier_gains,tier_twist_cycles,
  twist_volume))**6 AC 全 PASS**:VTT1 present+backward-compat(每檔位 dual-channel **等向**、base 逐位元不變、
  **Super(g=1)逐位元==base twist vol**)、VTT2 **crux** 每檔位每內部極值 |det−1|≤9.7e-5(TOL 2e-4)**且**峰補償 scale
  [1.0603,1.1169,1.2024,1.3572]・峰 shearX [16,21.6,27.2,33.6]° 皆嚴格遞增(Super==base)、VTT3 **crux 負對照** 逐軸線性
  amplify Legend |det−1| 0.11–0.31 vs 重算 ≤8.5e-5(>1000× 鑑別)+ 重算單元測(依放大後 shear→det≡1、s 隨 g 增大)、
  VTT4 兩軸反相阻尼簽章 + φ 比值≈0.7 逐檔不變 + identity 介面 每檔位保形、VTT5 端到端三通道 pivot 不動
  (`--tier-variants --twist-volume --shear-pivot` 每檔位 `twist__{tier}` pivot 殘差 <0.33px(Legend 最強)vs 負對照 8–74px)、
  VTT6 平增益守衛(隔離幅度軸→補償不遞增且==base vol)・非 twist 主秀變體不生 scale・移除 twist 其餘逐位元不變。
  **回歸 24 閘全綠**(23 既有 + 新 twist_volume_tier;`check_readiness.py` 退出 0,0 RED,無 GREEN→RED)。新增 cap
  `twist_volume_tier` L2 併入 `spine-anim-forge`(**仍 HOLD**)。**關鍵發現**:**一般仿射四自由度 + 體積守恆已在生成端
  base 與 tier 全檔位成立**;**跨通道約束隨檔位保住的關鍵在「補償是不是放大量的線性函數」—— 是(squash 倒數耦合)
  可線性耦合,否(twist 的 cos 補償)就必須依放大後的驅動量重算**。**honest boundary(仍在)**:幅度階梯為 PROPOSAL
  (手感 A 類);單一真值資產;**twist 系列生成端能力(生成 shearY→tier 幅度→count 段數→vol base→vol tier)至此全數接齊**。
  見 `knowledge/s1-twist-volume-tier.md`。
- **S1 volume-conserving twist:反相雙軸 shear 接體積守恆等向 scale(里程碑,2026-09-27 run 001,candidate G-4''''''-vol)** —
  補 twist 系列(G-4'''''' 生成 → tier → count)一路留到現在的**最後一條 honest boundary**:反相雙軸 shear 的
  Spine local 行列式 `det = cos(shearX − shearY) < 1`(兩基底夾角 90+shearY−shearX,反相被擰緊 → cos<1)→
  **擰轉使面積縮小**。本次掛一條**等向**(uniform)補償 scale `s = 1/√cos(shearX − shearY)`(scaleX==scaleY)使
  全域 local 行列式 `det = (s·s)·cos(shearX − shearY) ≡ 1`(**擰而不變面積**):`shear + scale + rotate` 三通道
  **同時**作用、塞滿一般仿射四自由度**且體積守恆**。**crux(與 squash 體積守恆的機制差異)**:twist 的補償為
  **等向**(scaleX==scaleY)—— twist 的各向異性**全由 shear 提供**,scale 只做等向面積復原;此與 squash(G-4'''')的
  **非均勻**(scaleX≠scaleY,scale 本身即擠壓)體積守恆機制**不同源**。det 是 `sx·sy` 的約束,等向是最小(不再引入
  額外各向異性)的守恆選擇;端點 shear=0 → cos(0)=1 → s=1 → **identity 介面自動保持**。全 additive:
  `gen_twist(vol_conserve=False)` 掛 scale 通道(等向補償),`False`(預設)→ **逐位元同 shear-only twist**;
  `_build_beat(twist_vol=)` twist 專屬 kwarg 只對 cat=="twist" 生效;`build_animations(twist_volume=)` /
  `build_spine --twist-volume`(配 `--shear-pivot` 三通道端到端繞關節 pivot 補償,`include_scale` 隨 shear_pivot 開)。
  整合閘 `validate_twist_volume.py`(先驗庫 twist beat → **真實 build_spine robot 骨架** → build_animations(twist_volume=True))
  **6 AC 全 PASS**:TV1 present+shear&scale 雙通道(crux:≥1 bone 同時帶雙軸 shear shearX 峰16°/shearY 峰11.2° **與**
  scale 通道,且 scale **等向**每幀 scaleX==scaleY)、TV2 **crux 體積守恆**(每內部極值幀全域 |det−1|≤8.8e-5(TOL 2e-4);
  **負對照 scale≡1 純 twist |det−1| 0.04–0.11 縮面積** → >500× 分離,證閘測「真體積守恆」非「有 scale 即可」)、
  TV3 雙軸反相阻尼簽章保形(體積耦合不破壞 twist 簽章:兩軸繞0變號≥3+相繼極值遞減+每內部極值反號)、
  TV4 identity 介面(shear 首尾 (0,0)、scale 首尾 (1,1))、TV5 端到端**三通道** pivot 不動(`--twist-volume --shear-pivot`
  pivot 殘差 <0.016px 含補償 scale vs 負對照繞件中心 8–29px)、TV6 負對照/隔離/向後相容(a 無補償縮面積 0.11、
  b **等向 vs squash 非均勻隔離**(twist scale 等向、squash scale 非均勻,兩種體積守恆機制不同源互不外洩)、
  c `twist_volume=False` 逐位元同 shear-only(無 scale 通道)+ 移除 twist storyboard 其餘 beat 逐位元不變)。
  **回歸 23 閘全綠**(22 既有 + 新 twist_volume;`check_readiness.py` 退出 0,0 RED,無 GREEN→RED)。新增 cap
  `twist_volume_conserving` L2 併入 `spine-anim-forge`(**仍 HOLD**)。**關鍵發現**:**一般仿射四自由度
  (rotate / 非均勻 scale / shearX / shearY)+ 體積守恆全數在生成端成立**;**跨通道約束(twist:det≡1)由建構
  (等向補償 = cos 的反推)保證**;**同一守恆目標,squash 走非均勻、twist 走等向 —— scale 的「語意角色」
  (自己是擠壓 vs 補償別人)決定它是各向異或等向**。**honest boundary(仍在)**:vol 僅作用 **base twist**
  (tier 變體仍 shear-only;vol 隨檔位放大需**重算補償 scale** 以維持 det≡1,比照 squash 耦合 amplify,為後續);
  幅度為 PROPOSAL(手感 A 類);單一真值資產。見 `knowledge/s1-twist-volume-conserving.md`。
- **S1 twist 扭轉段數隨檔位遞增:count-aware × 幅度 × φ 保形三效正交(里程碑,2026-09-24 run 001,candidate G-4''''''-count)** —
  補 (G-4''''''-tier) 明列的 honest boundary(「twist 未接 count-aware,扭轉段數隨檔位,`gen_twist(nosc=)` 已備參數
  未接;比照 wobble G-4'''/squash G-4'''''-c」)。(G-4''''''-tier) 讓 twist 兩軸 shear 峰**幅度**隨檔位遞增(兩軸同一
  g 同比 → φ 不變),但各檔位仍**同樣 4 段**反相雙軸阻尼擺。本次補上扭轉**段數** nosc 隨檔位嚴格遞增
  (Super4→Mega5→Omg6→Legend7)—— 結構(拓樸)軸檔位差異化的**第四個通道**(前三:combo/wobble/squash)。
  **關鍵:幅度增益加不出段數**(段數=繞 0 交替 shearX 極值個數=反相 shearY 極值個數,關鍵幀拓樸須 gen 時決定)
  → 對 twist 檔位變體以該檔位 nosc **重生成**再疊單一-g 幅度增益。新增 `TIER_TWIST_CYCLES` + twist∈`COUNT_AWARE_CATS`;
  `build_animations(tier_twist_cycles=)` 依 cat 路由 `_count_maps`。**twist 獨有 crux(與 wobble count 差異)**:twist
  有**兩條** shear 軸(反相雙軸)—— 段數重生成後兩軸各多長 nosc 個阻尼極值,每個新極值仍由 `_twist_env` 建構
  `shearY=−TWIST_PHI·shearX` → **φ 比值由建構保證、與段數無關**;故段數×幅度×φ 保形三效正交可疊(每檔位不論扭
  幾段,φ 恆定、反相不變)。整合閘 `validate_twist_count.py`(先驗庫→**真實 build_spine robot 骨架**→build_animations)
  **5 AC 全 PASS**:TC1 present+backward-compat(每檔位 dual-axis、base 恆 4 段逐位元不變、ttc=None 逐位元同幅度-only)、
  TC2 **crux** 段數 [4,5,6,7] 嚴格遞增 Super==base **且**每檔位每 bone φ 比值≈0.7 max_phi_err=0.0、TC3 兩軸阻尼簽章
  逐檔保形+兩軸峰仍遞增+每內部極值反相、TC4 正交(段數+平增益→段數遞增·兩軸峰不遞增·φ 仍不變;增益+無段數→
  段數恆4·兩軸峰遞增)、TC5 負對照(平段數→單調 FALSE、slot_reveal None 不亂加、段數只作用 twist 不外洩 wobble/squash
  仍4段)。端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 `twist__{Super4,Mega5,Omg6,Legend7}`
  (兩軸峰隨檔位遞增 shearX16→33.6°、φ 逐檔=0.7000)。**回歸 22 閘全綠**(21 既有 + 新 twist_count;`check_readiness.py`
  退出 0,0 RED,無 GREEN→RED)。新增 cap `twist_tier_count_aware` L2 併入 `spine-anim-forge`(**仍 HOLD**)。**關鍵發現**:
  **結構(段數)軸已在 combo/wobble/squash/twist **四通道**成立**;**帶跨通道關係約束的類別 count-aware 要多驗一層
  「約束在段數增多後仍成立」**(squash:體積守恆;twist:φ 比值+反相)—— 約束由 `_env` 建構保證則段數增多天然
  不破(沿約束流形生成,對照 squash tier 的耦合 amplify「沿守恆流形放大」)。**honest boundary(仍在)**:volume-conserving
  twist(反相雙軸接體積守恆耦合 scale)為後續;段數/幅度/φ 為 PROPOSAL(手感 A 類);單一真值資產。見
  `knowledge/s1-twist-count-generation.md`。
- **S1 twist 反相雙軸 shear 峰隨檔位遞增:兩軸同比 φ 保形(里程碑,2026-09-23 run 002,candidate G-4''''''-tier)** —
  補 (G-4'''''') 明列的 honest boundary(「twist 未接 tier 幅度,`gen_twist(nosc=)` 已備參數未接;比照 wobble
  G-4''/squash G-4'''''」)。twist(反相雙軸阻尼 shear,產線第一個驅動 shearY 的節拍)是主秀節拍,強度理應隨大獎檔位
  遞增,幅度軸在**兩條** shear 軸。**關鍵:twist 純 shear(無 scale 通道,不在 `COUPLED_SCALE_CATS`)** —— 併入
  `MAIN_SHOW_CATS` 後 `amplify_bone_tl` 既有的 shear 迴圈(`v'=g*v`,對 0 對稱)即以**同一 g** 同時放大 shearX 與
  shearY,無須新增任何放大邏輯(twist 亦不在 `COUNT_AWARE_CATS`,走 amplify base、非重生成)。**crux(與 wobble tier
  的差異)**:wobble 只有**一條** shear 軸;twist 有**兩條**,檔位放大必須讓兩軸**同比**縮放才保住「反相雙軸 shear」
  簽章 —— 每幀 shearY=−φ·shearX,amplify 後 shearX'=g·shearX、shearY'=−φ·shearX' ⇒ **shearY/shearX=−φ 逐檔恆定**、
  反相(乘積符號)不變、阻尼比 r=0.5 同比放大 → 符號序列與遞減比不變;若兩軸**各自獨立增益**,φ 會漂、甚至翻反相
  (就不再是同一種扭轉)。用**單一 g** 對兩軸 = **反相雙軸幾何 scale-invariant**(強度變、幾何種類不變:愈高檔位擰愈狠,
  仍是同一種雙軸 shear 扭轉)。整合閘 `validate_twist_tier.py`(先驗庫 slot_bigwin → **真實 build_spine robot 骨架** →
  build_animations(tier_gains))**6 AC 全 PASS**:TT1 present+backward-compat(每檔位 dual-channel、名經 `beat_category`
  仍路由回 twist、base 含 In/Loop/Out 帶/不帶 tier_gains 逐位元不變)、TT2 **crux** 兩軸峰皆嚴格遞增(端到端量:
  shearX [16,21.6,27.2,33.6]°、shearY [11.2,15.12,19.04,23.52]°,Super g=1 == base)、TT3 **crux** φ 比值逐檔≈0.7
  不變(誤差 ≤2e-3)、TT4 兩軸各自阻尼簽章逐檔保形(繞 0 變號≥3 + 相繼極值遞減)、TT5 反相逐檔保形(每內部極值
  shearX·shearY<0)且反相夾角偏離峰 |shearY−shearX| 隨檔位嚴格遞增([27.2,36.72,46.24,57.12]°)、TT6 負對照/隔離
  (a 平增益守衛全 1.0→兩軸遞增 FALSE 且各檔位==base、b 單一-g 兩軸同比單元測 + **獨立軸增益負對照破 φ**證單一-g 是
  φ 保形關鍵、c shear 隔離到 `SHEAR_CATS`{wobble,squash,twist}含所有 `__tier` 變體不外洩)。端到端
  `build_spine --animate --tier-variants --shear-pivot` 直出 `twist__{Super,Mega,Omg,Legend}`(shearY 經 pivot 補償
  仍存活且隨檔位遞增 11.2→23.52°)、`validate_build` round-trip overall_pass(premult MAE 0.031)。**回歸 21 閘全綠**
  (20 既有 + 新 twist_tier;`check_readiness.py` 退出 0,無 GREEN→RED)。新增 cap `twist_tier_amplitude` L2 併入
  `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。**關鍵發現**:**幅度軸的檔位差異化已在
  scale(J)、rotate(J)、shearX(wobble G-4'')、shear+耦合非均勻 scale(squash G-4''''')、**反相雙軸 shear(twist 本次)**
  全數通道成立**;帶跨軸關係約束的類別(twist 的 φ 比值、squash 的體積守恆),tier 幅度要多驗一層「約束在放大後仍成立」
  (twist:兩軸同比 → φ 不變;squash:耦合 amplify → 體積守恆)—— 單一 g 同時作用相關通道是關係保形的通則。
  **honest boundary(仍在)**:twist 未接 count-aware(扭轉段數隨檔位,`gen_twist(nosc=)` 已備參數未接;比照 wobble
  G-4'''、squash G-4'''''-c);反相雙軸未接體積守恆耦合 scale(`det=cos(shearY−shearX)≠1` → 擰轉變面積,
  volume-conserving twist 為後續);幅度/φ 為 PROPOSAL(手感 A 類);單一真值資產。見
  `knowledge/s1-twist-tier-amplitude.md`。
- **S1 twist 反相雙軸 shear:生成器首度驅動 shearY(里程碑,2026-09-23,candidate G-4'''''')** —
  補 wobble(G-4')/squash(G-4'''')一路留到現在的**最後一條 shear 通道 honest boundary(shearY≡0)**。至今所有
  產 shear 的節拍(wobble 純 shearX、squash shearX + 耦合非均勻 scale)都令 shearY≡0,故 Spine local 一般仿射 M
  的 y 軸 skew 自由度**從未被生成器驅動** —— 公式/閘早就吃 `shy`(G-4 `transform_matrix_full(...,shy)` /
  `pivot_channels_affine` / `apply_pivots(include_shear=True)` 以**合成** shy 驗過管路),生成端這次才接上。新增
  `gen_twist`(斜扭果凍扭轉)= **反相(counter-phase)雙軸阻尼 shear**(像擰毛巾:shearX 同 wobble 阻尼擺、
  shearY **反相**且幅度 ×`TWIST_PHI`=0.7,兩軸極值 τ 同點共用阻尼 → 同源同衰減但反相)。**關鍵幾何**:Spine local
  兩基底夾角 = `90 + shearY − shearX`,反相時**偏離 = (1+φ)|shearX| 被放大**(平行四邊形沿對角擰緊)= 真正雙軸
  shear;若**同相**(shearX==shearY)夾角恆 90°(基底仍正交)= 只是旋轉,非 shear —— 這正是負對照(證簽章測
  「真雙軸 shear」非「旋轉偽裝」)。經 `genre_priors.slot_bigwin` 新增 twist beat **直出**(additive、coverage 仍 1.0);
  `build_spine --shear-pivot`(include_shear=True 隱含 include_scale)端到端把 rotate/scale/shearX/**shearY** 一起
  繞關節 pivot 補償 → 件做**用滿兩條 shear 軸的一般仿射**而 pivot 精確不動(G-4 通用 Δ=(M−I)(O−P) 第一次被
  **生成器產的 shearY** 驅動)。整合閘 `validate_twist_gen.py`(先驗庫 slot_bigwin → **真實 build_spine robot
  骨架** → build_animations)**6 AC 全 PASS**:TW1 present+dual-axis(crux:shearX 峰 16°、shearY 峰 **11.2°**≠0)、
  TW2 兩軸各自阻尼振盪(復用 G-4' 判準,繞 0 變號≥3 + 相繼極值遞減)、TW3 **crux 反相耦合**(每內部極值幀
  shearX·shearY<0 且夾角偏離 |shearY−shearX|≥8°,峰 27.2°)、TW4 identity 介面(shear 首尾 (x,y)=(0,0))、
  TW5 端到端**在 shearY≠0 驅動下** pivot 殘差 <0.015px(右手 0.0147/頭 0.0042/左手 0.0145)vs 負對照
  (繞件中心,含雙軸 shear)≈24px(>1000×)、TW6 負對照/隔離(a 同相守衛 shearX==shearY→反相 FALSE=旋轉偽裝、
  b 單軸守衛 shearY≡0→雙軸 FALSE、c 雙軸隔離 twist 獨佔 shearY(wobble/squash shearY≡0)、d 加性移除 twist
  其餘逐位元不變)。端到端 `build_spine --animate --tier-variants --shear-pivot` 直出 `twist`(shearY 經 pivot 補償
  仍存活,峰 11.2°)、`validate_build` round-trip overall_pass(premult MAE 0.031)。**回歸踩雷**:twist 產 shear →
  shear-isolation 閘(shear_gen W5b / wobble_tier T4)原以 `SHEAR_CATS={wobble,squash}` 認定「合法 shear 產出者」
  會誤判 twist 為洩漏 → 把 `twist` 併入 `SHEAR_CATS`(集中一處,避免每加一個 shear 節拍就改多閘硬編碼)後復綠。
  **回歸 20 閘全綠**(19 既有 + 新 twist_gen)。新增 cap `twist_dual_axis_shear` L2 併入 `spine-anim-forge`
  (**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。**關鍵發現**:**一般仿射 M 的 4 自由度
  (rotate / 非均勻 scale / shearX / shearY)生成端至此全數被真實 beat 驅動過**(rotate:0i/G-4 pivot;非均勻
  scale:G-3/squash;shearX:wobble/squash;shearY:twist 本次)—— 公式/閘早通用,這條線(G-4→G-4'''''')逐一把
  「公式就緒 ≠ 生成器接上」的每條通道接齊;**真簽章常需兩獨立條件並立**(twist 真雙軸=兩軸皆非零 **且** 反相;
  同相是旋轉偽裝 → 「有兩條 shear 通道」不足以判雙軸,必驗反相=基底非正交)。**honest boundary(仍在)**:twist
  未接 tier 幅度 / count-aware(比照 wobble G-4''/G-4''',`gen_twist(nosc=)` 已備參數未接);反相雙軸未接體積守恆
  (`det=cos(shearY−shearX)≠1` → 擰轉變面積,volume-conserving twist 為後續);幅度/φ 為 PROPOSAL(手感 A 類);
  單一真值資產。見 `knowledge/s1-twist-dual-axis-shear-generation.md`。
- **S1 squash 擠壓段數隨檔位遞增:count-aware × 幅度 × 體積守恆三效正交(里程碑,2026-09-21 run 002,candidate G-4'''''-c)** —
  補 G-4''''' 明白列出的 honest boundary:「squash **count-aware**(擠壓段數隨檔位,`gen_squash(nosc=)` 已備參數
  未接)」。G-4''''' 讓 squash 的 shear 峰與擠壓**幅度**隨檔位遞增(愈高檔位擠愈深)而體積守恆保持,但各檔位仍
  **同樣 4 段**擠壓(有「擠多深」沒「擠幾下」)。本次補上擠壓**段數** nosc 隨檔位嚴格遞增(Super4→Mega5→Omg6→
  Legend7)。**關鍵:幅度增益加不出段數** —— 段數是關鍵幀**拓樸**(繞 0 交替 shear 極值 = 耦合 squash 極值個數),
  須在 `gen_squash` 生成當下決定;事後 `amplify_bone_tl` 只能同比放大既有極值。故對 squash 檔位變體以該檔位 nosc
  **重生成**(`_build_beat(count=nosc)`→`gen_squash(...,nosc)`),再疊 G-4''''' 的**耦合**幅度增益 g(與幅度軸
  正交可疊)。此模式同 (G-4'')wobble、(J-2)combo,惟**段數階梯各類別獨立**(squash→`TIER_SQUASH_CYCLES`,
  squash 併入 `COUNT_AWARE_CATS`;`build_animations` 依 cat 路由 `_count_maps`;`build_spine --tier-variants` 帶入
  `squash_cycles_for`)。**squash 獨有 crux(與 wobble count 的差異)**:squash∈`COUPLED_SCALE_CATS` —— 段數重生成後
  仍走**耦合** amplify,故段數×幅度×**體積守恆**三效必須**同時**成立;段數增多會多長出低幅擠壓極值(`q_i=Q·rⁱ`
  隨 i 遞減,Legend nosc=7 最末 `q_6=Q/64`),閘須證這些新極值仍由 `_squash_env` 建構 `(1+q_i,1/(1+q_i))` →
  `scaleX·scaleY≡1`,經耦合 amplify 仍守恆。整合閘 `validate_squash_count.py`(先驗庫 slot_bigwin→**真實
  build_spine robot 骨架**→build_animations(tier_gains,tier_squash_cycles))**5 AC 全 PASS**:SC1 present+
  backward-compat(每檔位 dual-channel、base 恆 4 段逐位元不變、`tsc=None` 逐位元同 G-4''''' 幅度-only)、
  SC2 **crux** 段數 [4,5,6,7]==宣告嚴格遞增·Super==base **且**每檔位每內部極值 |scaleX·scaleY−1|≤2e-4
  (max 9.7e-05)、SC3 每檔位仍首尾 0+繞 0 變號≥3+相繼極值遞減(阻尼保形)且峰 |shearX| 與峰非均勻皆仍隨檔位
  遞增、SC4 正交(段數+平增益→段數遞增·非均勻不遞增·**體積仍守恆**;增益+無段數→段數恆 4·非均勻遞增)、
  SC5 負對照(a 平段數全 4→單調 FALSE、b slot_reveal `squash_cycles_for` None 且無增益→不產段數變體、
  c 段數只作用 squash·非-squash 主秀 shear 段數各檔位恆定不外洩·wobble 仍 4 段)。端到端 `build_spine --animate
  --tier-variants --shear-pivot` 直出 `squash__{Super4,Mega5,Omg6,Legend7}`、`validate_build` round-trip
  overall_pass(premult MAE 0.031)。**回歸 19 閘全綠**(18 既有 + 新 squash_count)。新增 cap
  `squash_tier_count_aware` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
  **關鍵發現**:結構(段數)軸的檔位差異化已在 **combo=scale 峰數、wobble=shear 振盪段數、squash=耦合擠壓段數**
  三個不同通道成立;**帶跨通道守恆約束的類別,count-aware 要多驗一層守恆**(段數不只是多幾個關鍵幀,而是多幾個
  **守恆**極值;r=0.5 阻尼讓新增低幅極值天然變小 → 守恆殘差反而更小)。**honest boundary(仍在)**:段數/幅度
  階梯皆 PROPOSAL(手感 A 類);shearY≡0(雙軸 shear / shear+scale+rotate 三通道同時 = G-4'''''' 為後續);
  單一真值資產。見 `knowledge/s1-squash-count-generation.md`。
- **S1 squash 接檔位差異化:體積守恆耦合 amplify(里程碑,2026-09-21,candidate G-4''''')** —
  補 G-4'''' 明白列出的 honest boundary:「squash 未接 tier 幅度(`_amp_scale` 只放大 identity 上方 →
  破壞體積守恆,需**耦合 amplify**)」。**關鍵:面積守恆 `scaleX·scaleY≡1` 是跨通道約束**,放大必須沿
  守恆流形走 —— 逐軸 `_amp_scale` 會脹 scaleX(>1)卻保留 scaleY(<1)樓地板 → 破守恆(實測逐軸 Legend
  增益下 |積−1| 達 0.10–0.15)。解法 `_amp_scale_coupled`:放大**拉長軸** overshoot(`sx'=1+g·q`)、
  壓縮軸設**倒數** `sy'=1/sx'` → `scaleX·scaleY≡1` **由建構保證**在任一檔位保持,擠壓非均勻度隨檔位嚴格遞增;
  同源 shearX 峰亦隨檔位遞增(走既有 `v'=g*v`)⇒ **第一個 shear + 非均勻 scale 兩通道同時檔位差異化**的節拍。
  squash 併入 `MAIN_SHOW_CATS`;新增 `COUPLED_SCALE_CATS={squash}`,`build_animations` 依此路由耦合/逐軸
  amplify(`amplify_bone_tl(coupled=)`)。整合閘 `validate_squash_tier.py`(先驗庫→**真實 build_spine
  robot 骨架**→build_animations(tier_gains))**6 AC 全 PASS**:ST1 present+backward-compat(每檔位 dual-channel、
  base 逐位元不變、**Super g=1 逐位元==base squash**)、ST2 **crux** 每檔位每極值 |scaleX·scaleY−1|≤2e-4 +
  非均勻 [0.298,0.394,0.486,0.588] 與拉長 [0.16,0.216,0.272,0.336] 皆嚴格遞增(Super==base)、ST3 shear 峰
  [16,21.6,27.2,33.6]° 遞增 + 每檔位阻尼簽章(繞 0 變號≥3 + 相繼極值遞減)保形、ST4 identity 介面(shear 首尾 0、
  scale 首尾 (1,1))、ST5 **crux 負對照** 逐軸 amplify 破守恆 0.10–0.15 vs 耦合 ≤1e-4(>500× 鑑別餘裕)、
  ST6 平增益守衛 + 耦合 amplify 單元測 + 耦合隔離(wobble shear-only 不被波及)+ 加性零回歸。端到端
  `build_spine --animate --tier-variants --shear-pivot` 直出 `squash__{Super,Mega,Omg,Legend}`(pivot 殘差
  <0.06px 即使 Legend 最強一般仿射)、`validate_build` round-trip overall_pass(premult MAE 0.031)。
  回歸:squash_gen/wobble_count/wobble_tier/tier_combo_count/tier_variants/shear_gen/shear_pivot/scale_pivot/
  pivot_rotation/cascade/priors/priors_beats/priors_combo_charge/priors_cascade/more_beats/beat_templates/
  deform_gen **18 閘全綠**。**回歸踩雷**:combo 專屬 `_min_peaks`(impact 門檻 1.10)對 squash head(base 峰恰
  1.10)因耦合**幅度**增益推過門檻而誤判 count 外洩 → `validate_tier_combo_count` K5(c) 排除 `SHEAR_CATS`
  (類別專屬結構指標不可跨類別當通用 count;wobble 段數隔離由 U5c 的 `_nosc` 驗)。新增 cap
  `squash_tier_coupled_amplify` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
  **honest boundary(仍在)**:squash **count-aware**(擠壓段數隨檔位,`gen_squash(nosc=)` 已備參數未接,
  需加 `TIER_SQUASH_CYCLES` 並確認 nosc 遞增下逐極值仍守恆);shearY≡0;幅度階梯為 PROPOSAL(手感 A 類)。
  見 `knowledge/s1-squash-tier-coupled-amplify.md`、圖 `knowledge/figures/s1_squash_tier_coupled.png`。
- **S1 生成器產耦合 shear + 非均勻 scale(體積守恆擠壓)端到端(里程碑,2026-09-12,candidate G-4'''')** —
  補一路(G-4/G-4')留到現在的 honest boundary(**`shearY≡0`、斜拉 squash(shear+coupled scale)為後續**)。
  **關鍵:純 shear(G-4' wobble)只是相似變換特例(等距+skew);shear+非均勻 scale 才是真正的一般仿射**。
  `beat_templates.gen_squash`(斜拉果凍**擠壓**)是**第一個同時產 `shear` 與非均勻 `scale`(sx≠sy)** 的生成器:
  shearX 同 wobble 阻尼擺動;每個 shear 極值 i 施體積守恆 squash(`scaleX=1+q_i` 拉長、`scaleY=1/(1+q_i)`
  壓扁,`q_i=Q·rⁱ` 與 shear 同源同阻尼)⇒ `scaleX·scaleY≡1`(面積守恆)且 `scaleX≠scaleY`(非均勻),首尾
  identity。經 `genre_priors.slot_bigwin` 新增 squash beat **直出**(additive、coverage 仍 1.0、列
  prior_beats_unused 誠實);`build_spine --shear-pivot`(include_shear 隱含 include_scale)端到端把
  rotate/scale/**shear** 三通道一起繞關節 pivot 補償 → G-4 的通用 Δ=(M−I)(O−P) **第一次被生成器產的**非均勻
  scale+shear 同時驅動(M 非相似,det=scaleX·scaleY·cos(shear))而 pivot 精確不動。整合閘
  `validate_squash_gen.py`(先驗庫→**真實 build_spine robot 骨架**→build_animations)**6 AC 全 PASS**:
  SQ1 present+dual-channel(crux:shear 峰 16°+非均勻峰 0.298、≥1 bone 同時帶 shear+scale)、SQ2 shear 阻尼
  振盪(復用 G-4' 判準,繞 0 變號≥3+相繼極值遞減)、SQ3 **crux** 體積守恆耦合(每極值幀 |scaleX·scaleY−1|≤5e-5
  +非均勻 0.19–0.30+squash 幅度 [Q,Q/2,Q/4,Q/8] 嚴格遞減)、SQ4 identity 介面(shear 首尾 0+scale 首尾
  (1,1))、SQ5 端到端**一般仿射** pivot 不動(頭/右手/左手殘差 0.005/0.013/0.018px vs 負對照繞件中心
  9.44/17.71/32.78px,>1000×;pivot≈中心的身體/光暈正確略過)、SQ6 負對照/隔離(a 等比 scale 守衛
  scaleX==scaleY→非均勻 FALSE、b 非守恆守衛非均勻但兩軸皆拉長積≠1→體積守恆 FALSE 而非均勻仍 TRUE **證兩條件
  獨立**、c 耦合隔離僅 squash 同時帶 shear+非均勻 scale(wobble 有 shear 無 scale、其餘主秀等比 scale 無 shear)、
  d 加性移除 squash→其餘 beat 逐位元不變)。**關鍵發現:真簽章常需兩獨立條件並立**(體積守恆 **且** 非均勻;
  同 (I) cascade「散佈且遞增」、(H) charge「長 hold 且 squash-floor」)。新增 `tier_variants.SHEAR_CATS=
  {wobble,squash}`(shear 產出者集中一處;shear-isolation 閘 shear_gen W5b / wobble_tier T4 改以此認定,
  便於後續再加 shear 節拍)。回歸:shear_gen(W5b 更新)/wobble_tier(T4 更新)/wobble_count/shear_pivot(G-4)/
  scale_pivot(G-3)/pivot_rotation(0i)/tier_variants(J)/tier_combo_count(J-2)/priors/priors_beats/
  priors_combo_charge/priors_cascade/cascade/more_beats/beat_templates/deform_gen **16 閘全綠** +
  round-trip `validate_build` 對 `--shear-pivot` build overall_pass(premult MAE 0.031)。新增 cap
  `squash_shear_scale_coupling` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
  **honest boundary(仍在)**:squash 未接 tier 幅度(`_amp_scale` 只放大 identity 上方 → 破壞體積守恆,
  需**耦合 amplify**,後續);shearY≡0;count-aware nosc 已備參數未接(比照 J-2/G-4''')。
  見 `knowledge/s1-squash-shear-scale-coupling.md`、圖 `knowledge/figures/s1_squash_coupling.png`。
- **S1 wobble 振盪段數隨檔位遞增(里程碑,2026-09-11,candidate G-4''')** — 補 G-4'' 的 honest boundary
  (「wobble 未接 count-aware」)。(G-4'') 讓 wobble 的 shearX 峰**幅度**隨檔位遞增,但各檔位仍**同樣 4 段**
  阻尼振盪(有「多斜」沒「晃幾下」)。本次補上振盪**段數** `nosc` 隨檔位嚴格遞增(Super 4→Mega 5→Omg 6→
  Legend 7)。**關鍵:幅度增益加不出段數** —— 段數是繞 0 交替變號極值的關鍵幀**拓樸**,事後 `amplify_bone_tl`
  只能同比放大既有極值(`v'=g*v`)、無法多長一段,必須在 `gen_wobble` 生成當下決定;故對 wobble 檔位變體
  以該檔位 nosc **重生成**整支 beat(`gen_wobble(role,side,radial,nosc=4)` + `_wobble_env(A,nosc)`,
  **nosc==4 逐位元同 G-4' 手調 golden**),再疊 (G-4'') 幅度增益 g → 與幅度軸**正交可疊**
  (段數 [4,5,6,7] × 峰幅 [16,21.6,27.2,33.6]° 皆遞增)。**此模式同 (J-2) 對 combo 連擊數**,是第二個**結構
  (拓樸)軸**的檔位差異化,惟**段數階梯各類別獨立**(combo→`TIER_COMBO_HITS`、wobble→`TIER_WOBBLE_CYCLES`,
  `build_animations` 依 cat 路由;`_build_beat(count=None)` 泛化原 `combo_hits`,None → 呼叫生成器自身預設保
  golden byte-identical)。全 additive。整合閘 `validate_wobble_count.py`(先驗庫→**真實 build_spine robot
  骨架**→build_animations(tier_gains,tier_wobble_cycles))**5 AC 全 PASS**:U1 present+backward-compat
  (每檔位 `wobble__{tier}` finite/有 bone/帶 shear、**base 恆 4 段逐位元不變**、`tier_wobble_cycles=None` 逐位元
  同 (G-4'') 幅度-only)、U2 **crux** 段數 [4,5,6,7]==宣告且 Super<Mega<Omg<Legend 嚴格遞增·Super==base、
  U3 每檔位仍首尾 0+繞 0 變號≥3+相繼極值遞減(阻尼保形)**且峰幅仍隨檔位嚴格遞增**(段數軸不抵消幅度軸)、
  U4 正交(段數+平增益→段數遞增·峰幅不遞增;增益+無段數→段數恆 4·峰幅遞增)、U5 負對照(a 平段數全 4→
  U2 遞增 FALSE;b slot_reveal 無宣告→`wobble_cycles_for` None 不亂加;c 段數只作用 wobble 不外洩)。
  **關鍵發現:結構軸×幅度軸雙軸檔位差異化可推廣**——同一 count-aware 概念在 **combo=scale 峰數**、
  **wobble=shear 振盪段數**兩個不同通道皆成立;阻尼比 r=0.5 對任意段數天然保簽章(等比阻尼 `A·rⁱ` →
  相繼極值恆遞減、交替變號 nosc−1 次≥3)。端到端 `build_spine --animate --tier-variants --shear-pivot` 直出
  `wobble__{Super4,Mega5,Omg6,Legend7}` 段(pivot 補償後仍 [4,5,6,7]),`validate_build` round-trip overall_pass。
  回歸:validate_wobble_tier(G-4'')/tier_combo_count(J-2)/tier_variants(J)/shear_gen(G-4')/
  shear_pivot(G-4)/scale_pivot(G-3)/pivot_rotation(0i)/cascade/priors/priors_beats/priors_combo_charge/
  priors_cascade/more_beats/beat_templates/deform_gen **16 閘全綠**。新增 cap `wobble_count_generation` L2
  併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。**honest boundary(仍在)**:
  段數階梯 [4,5,6,7] 為 PROPOSAL(手感留使用者 A 類);shearY≡0;斜拉 squash(shear+coupled scale)為後續。
  見 `knowledge/s1-wobble-count-generation.md`、圖 `knowledge/figures/s1_wobble_count.png`。
- **S1 wobble shear 峰隨檔位遞增(里程碑,2026-09-10 session 001,candidate G-4'')** — 補 G-4' 的 honest
  boundary(「tier 變體未接」)。G-4' 讓 `gen_wobble` 成為第一個產 shear 通道的生成器,但當時
  `wobble ∉ MAIN_SHOW_CATS` 且 (J) 的幅度增益只作用 scale/rotate/translate → **wobble 完全不隨檔位放大**
  (檔位愈高主秀愈爆,唯獨斜拉晃動強度不變=不一致)。本次把 wobble 併入 `MAIN_SHOW_CATS` 並讓
  `tier_variants.amplify_bone_tl` 一併放大 **shear**(對 0 對稱 → `v'=g*v`,同 rotate/translate)→ wobble 的
  shearX 峰隨檔位**嚴格遞增**(Super 16°→Mega 21.6°→Omg 27.2°→Legend 33.6°),同時**阻尼振盪簽章在每個
  檔位保形**(整條包絡乘共同正因子 g:符號序列不動、遞減比 r=0.5 不動 → 「繞 0 變號+相繼極值遞減」兩條件都保)。
  **又一「檔位機制就緒 ≠ 每個新通道接上」實例**(同 E/H/I/J/G-4')。全 additive:g=1.0(Super)identity、無 shear
  的 beat 空轉(零回歸)。整合閘 `validate_wobble_tier.py`(先驗庫→**真實 build_spine robot 骨架**→
  build_animations(tier_gains))**5 AC 全 PASS**:T1 present+backward-compat(每檔位產 `wobble__{tier}` finite/有
  bone/帶 shear、名仍路由回 wobble、**base 逐位元不變**)、T2 **crux** 峰 |shearX| [16,21.6,27.2,33.6] 嚴格遞增且
  Super==base、T3 每檔位仍首尾 0+繞 0 變號≥3+相繼極值遞減(阻尼簽章保形)、T4 shear 隔離(僅 wobble 及其變體
  帶 shear→`include_shear` 補償對象仍鎖 wobble)、T5 負對照(a 平增益全 1.0→T2 遞增 FALSE 且各檔位==base;
  b 通道隔離單元測 scale-only 不生 shear·shear-only 不生 scale)。**關鍵發現:同比放大是阻尼簽章的自然保形變換**
  (檔位改強度不改結構,同 J 對 scale「只放大 identity 上方 overshoot」);**J 閘 J3 改 channel-aware**——
  `SA.sample` 不含 shear 通道,舊 J3 對純 shear 的 wobble 量 scale_overshoot=[0,0,0,0] 會**假陰性**;改「量該 beat
  實際使用的通道(scale-overshoot/rotate/shear,shear 用 `_shear_amp` 直讀 keyframe)」後 J 閘成為完整檔位-幅度閘。
  回歸:validate_tier_variants(J,J3 channel-aware 仍全綠、新增 shear_amp/active 輸出)/tier_combo_count(J-2)/
  shear_gen(G-4')/priors/priors_beats(E)/more_beats(0g)/beat_templates(0f)/cascade(0h)/priors_combo_charge(H)/
  priors_cascade(I)/pivot_rotation(0i)/scale_pivot(G-3)/shear_pivot(G-4)/deform_gen(0e)/round-trip validate_build
  對 `--tier-variants --shear-pivot` build(overall_pass、premult MAE 0.031、setup 不變)全 PASS。新增 cap
  `wobble_tier_amplitude` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
  **honest boundary(仍在)**:shear 峰階梯沿用 (J) 增益(PROPOSAL);shearY≡0;wobble 未接 count-aware
  (晃動段數隨檔位需 gen 時決定,同 J-2 對 combo)。見 `knowledge/s1-wobble-tier-amplitude.md`、圖 `knowledge/figures/s1_wobble_tier.png`。
- **S1 生成器產出 shear 通道端到端:斜拉 wobble beat(里程碑,2026-09-08 session 002,candidate G-4')** —
  補 G-4 的 **honest boundary**:G-4 補齊了「件繞關節 pivot 一般仿射(含 shear)」的**公式+閘**,但當時
  **沒有任何 beat 生成器產出 shear 通道**(產線主秀只用 rotate/scale,G-4 的 AC7 只用**合成** shear 驗管路)。
  本次讓 `beat_templates.gen_wobble`(斜拉 jelly wobble)**實際產出 shear 通道** —— **第一個產 shear 的生成器**:
  純 shearX **阻尼擺動**(0→+A→−rA→+r²A→−r³A→0,r=0.5,role 峰 10–16°,首尾 identity),經
  `genre_priors.slot_bigwin` 新增 wobble beat **直出**;`build_spine --shear-pivot`(`shear_pivot=True` →
  `apply_pivots(include_scale=True, include_shear=True)`,含 --scale-pivot 語意)帶 `include_shear=True`
  **端到端補償** → 件繞關節 pivot 做**一般仿射**而 pivot 精確不動。**又一「公式/模板就緒 ≠ 生成器接上」實例**
  (同 (E)/(H)/(I)/(J)/(J-2))。全 additive:`gen_animations` 註冊 `_DISPATCH["wobble"]`;build summary 回報
  `pivot_centers`(O)/`pivot_joints`(P)供閘端到端驗殘差(同 rig 可觀測性)。整合閘 `validate_shear_gen.py`
  (先驗庫→**真實 build_spine robot 骨架**→build_animations)**5 AC 全 PASS**:W1 present+shear 產出(crux)
  =峰 16°、5 bone 全帶 shear;W2 **阻尼振盪簽章**=繞 0 變號 ≥3(4 次)+ 相繼極值 [16,8,4,2] **嚴格遞減**;
  W3 identity 介面(sample 首尾各 bone identity + shear 端點 0,可插 Loop);**W4 端到端 pivot 不動**=
  `--shear-pivot` 有關節的 bone(右手/頭/左手)pivot 殘差 0.009/0.004/0.013px vs 負對照(繞件中心)8–24px、
  arm(|O−P|)50–164px、比值 >1000×,pivot≈中心的 bone(光暈/身體)正確略過;W5 負對照(a)天真單調 shear
  (0→A→hold)阻尼簽章 FALSE(證閘測阻尼振盪非「有 shear 即可」)(b)shear **隔離**=僅 wobble 帶 shear
  (c)加性=移除 wobble 其餘 beat 逐位元不變。**關鍵發現:阻尼簽章需「振盪+遞減」兩條件並立**(天真單調 shear
  有 shear 值但 0 變號、無遞減 → 若簽章只看「有 shear」就形同虛設);**shear 隔離讓補償對象明確**、對既有節拍
  零回歸。**honest boundary(仍在)**:斜拉 wobble 形狀為 PROPOSAL(結構簽章客觀、手感留使用者 A 類);
  目前只產 shearX(shearY≡0);wobble ∉ `MAIN_SHOW_CATS` → tier 變體未接(可比照 (J) 讓 shear 峰隨檔位遞增)。
  回歸:validate_priors(cov 1.0)/priors_beats(E)/more_beats(0g)/beat_templates(0f)/cascade(0h)/
  priors_combo_charge(H)/priors_cascade(I)/tier_variants(J)/tier_combo_count(J-2)/pivot_rotation(0i)/
  scale_pivot(G-3)/shear_pivot(G-4)/deform_gen(0e)/anim(+selftest)/round-trip validate_build 對 `--shear-pivot`
  build(overall_pass、premult MAE 0.031、setup 不變)全 PASS。新增 cap `shear_channel_generation` L2 併入
  `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。見 `knowledge/s1-shear-channel-generation.md`、
  圖 `knowledge/figures/s1_shear_gen.png`。
- **S1 件繞關節 pivot 一般仿射:非均勻 scale + shear(里程碑,2026-09-08,candidate G-4)** — 把 0i(繞 pivot
  **轉**,M=R)/ G-3(繞 pivot **均勻縮放**,M=R·sI=相似)推廣到**非均勻 scale(sx≠sy)與 shear** —— 此時
  bone local M 是**一般仿射、不再是相似變換**,但**同一條** `Δ=(M−I)(O−P)` 仍讓關節 pivot P 為**精確不動點**
  (純代數,不依賴 M 是旋轉/相似),且對任意附著點 `world(x)−P = M·(x−P)` 精確(**仿射保形**)。矩陣改用
  **真實 Spine 3.8 bone local**(含 shear):`transform_matrix_full(θ,sx,sy,shx,shy)`=(cos(θ+shx)sx,
  cos(θ+90+shy)sy, sin(θ+shx)sx, sin(θ+90+shy)sy);**shx=shy=0 逐位元退化回 G-3 的 `transform_matrix`**
  (零回歸)。**這是真 Spine shear 非天真 unit-shear**:pure shearX φ 的 `det=cos φ`(shear 同時改面積),
  天真 `[[1,tanφ],[0,1]]` det≡1 → 閘以 `det==cosφ` 鎖定實作正確(負對照天真差 0.5)。全部 additive:
  `pivot_rotation.py` 加 `transform_matrix_full`/`pivot_delta_affine`/`pivot_channels_affine`/
  `apply_pivots(include_shear=False 預設)`,0i/G-3 路徑 byte-for-byte 不變。整合閘 `validate_shear_pivot.py`
  對真實 Award 左手+推得肩 pivot(|O−P|=117px)**7 AC 全 PASS**:AC1 非均勻 scale(1.6,1.2)不動點 0.0001px
  (負對照繞件中心 69.3px)、AC2 shear 25° 不動點 0.012px(負對照 49.9px)、AC3 **仿射保形** 關鍵幀
  `world(x)−P==M(x−P)` 4.3e-4px(純關鍵幀量化非公式限制)、**AC4 crux 相似性壞掉**=anisotropy
  (max|Md|−min|Md|=M 奇異值差)均勻 4e-16 / 非均勻 0.40 / shear 0.43(≥0.10)→ 證閘測**一般仿射非 G-3
  相似特例**、AC5 identity 首尾 Δ=0、AC6 矩陣正確(shear=0 退化 2e-16、det==cosφ、shear=None 路徑==srt)、
  AC7 端到端 `apply_pivots(include_shear=True)` rotate+scale+shear 有限/無縫/pivot 0.05px vs 負對照 93px。
  **關鍵發現:相似→仿射,判準必須換** —— G-3 靠等距-類比 `|w−P|=s|x−P|` 證等比繞 pivot,shear/非均勻
  scale 下該概念不存在,硬套會**假陰性**;改驗更本質的仿射保形 `world−P=M(x−P)` + **anisotropy** 鑑別子。
  **honest boundary(生成器側)**:補齊的是幾何/公式+閘;`gen_animations` 尚未產 `shear` 通道(產線主秀節拍
  只用 rotate/scale)——「公式/閘就緒 ≠ 生成器接上」再現,惟管路已通(AC7),某節拍需 shear 時讓 beat 產
  shear 通道 + build 帶 `include_shear=True` 即接上。回歸:validate_pivot_rotation(0i,7AC)、
  validate_scale_pivot(G-3,7AC)、round-trip validate_build 對 --scale-pivot build(overall_pass、premult
  MAE 0.031、setup 不變)、tier/priors/beat 系列(tier_variants/tier_combo_count/priors_*/more_beats/
  beat_templates/cascade/deform_gen)全 PASS。新增 cap `shear_pivot_affine` L2 併入 `spine-anim-forge`
  (**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。見 `knowledge/s1-shear-pivot-affine.md`、圖 `knowledge/figures/s1_shear_pivot.png`。
- **S1 combo 連擊「數」隨檔位遞增(里程碑,2026-09-07 session 002,candidate J-2)** — 續 (J):(J) 讓
  `{beat}__{tier}` 檔位變體只差**幅度**(愈爆),combo 各檔位仍**同一組三連擊** —— 有「多爆」沒「連幾下」。
  本次補上 combo 的 impact 峰**數** = `nhits` **隨檔位嚴格遞增**(Super 3→Mega 4→Omg 5→Legend 6)。
  **關鍵:幅度增益加不出連擊數** —— 峰「數」是關鍵幀**拓樸**,必須在 `gen_combo` 生成當下決定,事後 amplify
  只能放大既有峰、無法多長一個;故不走 amplify,而是對 combo 檔位變體以該檔位 `nhits` **重生成**整個 beat,
  **再**疊 (J) 幅度增益 → 與 (J) 幅度軸**正交可疊**(端到端:峰數 [3,4,5,6] × overshoot [0.347,0.469,0.591,0.730]
  皆遞增)。`gen_combo(role,side,radial,nhits=3)`:**nhits=3 逐位元同 0g 手調三連擊**(golden,向後相容;base combo
  恆走此路),`nhits≠3` → 通用 `_combo_env(peak,nhits)`(遞增 nhits 峰、擊間微回 0.985、固定 settle 尾)。
  `tier_variants.COUNT_AWARE_CATS={"combo"}`+`TIER_COMBO_HITS`+`combo_hits_for`;`build_animations(...,tier_combo_hits=None)`
  抽 `_build_beat(...,combo_hits=)` helper(**None 預設逐位元同 (J) 幅度-only,加性 opt-in 零回歸**);
  `build_spine --tier-variants` 自動帶 count。整合閘 `validate_tier_combo_count.py`(先驗庫→**真實 build_spine
  robot 骨架**→build_animations)對真實 combo **5 AC 全 PASS**:K1 present+backward-compat(每檔位產變體 finite/有
  bone、**base combo 恆 3 峰不變**、`tier_combo_hits=None` 逐位元同 (J) 幅度-only)、K2 **crux** 峰數 [3,4,5,6]==宣告
  且 Super<Mega<Omg<Legend 嚴格遞增·每檔位內部峰仍遞增、K3 每檔位首尾 identity·仍 combo 簽章·仍 settle·
  **仍非 charge**·幅度仍單調(與 J 疊加不衝突)、K4 **正交**(counts+平增益→峰數仍遞增=結構獨立於幅度;
  gains+無 counts→峰數恆 3、幅度遞增=兩軸可獨立開關)、K5 負對照(平連擊數全 3→峰數單調 FALSE 證閘可信、
  slot_reveal 無宣告 count→`combo_hits_for` None 不亂加、count **只作用 combo** 不外洩 hit/charge/cascade/burst)。
  **關鍵發現/踩雷:連擊變多恐誤入 charge 長蓄力簽章**(charge 鑑別子=峰前 <0.97 佔比 ≥0.35,峰數多→蓄力段多)——
  解法=**擊間微回設 0.985(>hold-level 0.97)**,峰間回到 hold 之上不計入蓄力;實測 hold-frac 反**隨 nhits 下降**
  (n=3→0.30、n=6→0.12,皆 <0.35)→ combo↔charge 互斥全檔位保持。回歸:validate_tier_variants(J,幅度-only 不變)/
  more_beats/beat_templates/priors_combo_charge/priors_beats/priors_cascade/cascade/priors/pivot_rotation/scale_pivot/
  deform_gen/round-trip(含 --tier-variants build)全 PASS。新增 cap `tier_variant_combo_count` L2 併入 `spine-anim-forge`
  (**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。見 `knowledge/s1-tier-variant-combo-count.md`、圖 `knowledge/figures/s1_tier_combo_count.png`。
- **S1 檔位(tier)幅度差異化(里程碑,2026-09-07,candidate J)** — 把 `genre_priors.slot_bigwin`
  宣告已久卻**從未被生成器使用**的 `tiers=[Super,Mega,Omg,Legend]` 接上產線:主秀 beat 依檔位產出
  **幅度差異化**變體 `{beat}__{tier}`(檔位愈高、主秀愈爆)—— **又一「宣告就緒 ≠ 生成器接上」實例**
  (同 (E)/(H)/(I) 的模式:資料/宣告就緒不代表生成器會用它)。`tools/analyzer/tier_variants.py` 把檔位轉成
  **主秀幅度增益** g,增益規則**對介面契約與結構簽章皆保形**:scale **只放大 identity 上方 overshoot**
  (`v'=1+g(v−1)` 僅當 v≥1;下方 squash 蓄力 ~0.85 / collapse 藏匿 ~0.02 **樓地板不動**)、
  rotate/translate 對 0 對稱放大(`v'=g·v`)、color/alpha 不動;`MAIN_SHOW_CATS`(hit/reveal/burst/combo/
  charge/cascade)才放大,In/Loop/Out 檔位無關。階梯 `{Super:1.0,Mega:1.35,Omg:1.70,Legend:2.10}`;
  **base=Super g=1.0 → 逐位元 == 無檔位輸出(向後相容)**。`build_animations(...,tier_gains=)`(附加,None 預設不變)
  + `build_spine --animate --tier-variants`;變體名經 `beat_category` 仍路由回原類別(`hit__legend` 先命中 `hit`)。
  整合閘 `validate_tier_variants.py`(從**先驗庫**經 `build_storyboard` → **真實 build_spine robot 骨架** →
  `build_animations`)對真實 robot 5 拆件 **5 AC 全 PASS**:J1 present+routing(每主秀 beat×每檔位皆產變體且
  finite/有 bone、名仍路由回原類別、base 含 In/Loop/Out 逐位元不變)、J2 介面契約(**每檔位** hit/combo/charge/
  cascade 首尾 identity、burst 尾 identity 首 collapsed 樓地板 → 皆可插 Loop 間)、J3 **crux 幅度單調**(scaleX
  overshoot 與 rotate 幅度 Super<Mega<Omg<Legend **嚴格遞增**,端到端量:burst overshoot 0.35→0.47→0.60→0.74)、
  J4 結構簽章保持(**每檔位** combo≥3 遞增峰、charge 長蓄力 squash 非 collapse、hit anticipation+settle
  (scale−1)變號≥3、cascade 跨件峰時刻遞增散佈 —— 復用 0g/0h 判定器)、J5 負對照(In/Loop/Out 不產變體、
  無 tier 的 slot_reveal `gains_for` 回 None 不產變體且 base 相同、**平增益守衛**全 1.0→J3 單調性 FALSE 證閘可信、
  reveal collapsed 首幀 Super==Legend 證下方樓地板檔位無關)。**關鍵發現:增益只放大 identity 上方 overshoot、
  不動下方樓地板與時間軸 → 端點/簽章對所有檔位保形**(檔位簽章=更爆的 overshoot;蓄力深度/藏匿是結構語意非
  大獎強度,誠實地檔位無關;天真「對 identity 均勻縮放」會把 reveal collapsed 0.02 在 g>1 推成負值=翻面)。
  回歸:validate_priors/priors_beats(E)/more_beats(0g)/beat_templates(0f)/cascade(0h)/priors_combo_charge(H)/
  priors_cascade(I)/anim(+selftest)/pivot_rotation(0i)/scale_pivot(G-3)/deform_gen(0e)/round-trip validate_build
  (含 `--tier-variants` build)全 PASS。新增 cap `tier_variant_amplitude` L2 併入 `spine-anim-forge`(**仍 HOLD**:
  運動基元先驗、單一真值資產,防固化)。見 `knowledge/s1-tier-variant-amplitude.md`、圖 `knowledge/figures/s1_tier_variants.png`。
- **S1 cascade 接進 genre 先驗庫(里程碑,2026-09-06 session 002,candidate I)** — 續 (E)/(H) 對 hit/reveal、
  combo/charge 所做,把 0h 的 **cascade(跨件錯開波)** 主秀節拍併入 `genre_priors.slot_bigwin`(additive),
  讓 `build_spine --animate --genre slot_bigwin` **直出** cascade(接 I 前先驗僅 In/burst/hit/combo/charge/Loop/Out,
  0h 的 cascade 模板從未被產線觸發、也從未在真實 build_spine 骨架+真實件序上驗過 —— 「模板就緒 ≠ 生成器接上」再現)。
  beat key 經 `beat_category` 路由到 `gen_cascade`(key∈CASCADE_KEYWORDS)。**cascade 比 (E)/(H) 多驗一層**:
  它是**跨件時序**簽章(同 beat 套每件,但每件依件序相位 `phase=pi/(nvalid-1)` 錯開成波),故本閘證的不只是
  「beat 有流到 animations」,還證 **`_PHASE_AWARE` 的件序相位 threading 端到端存活**(單件曲線看不出,只有各件
  峰時刻的排序/散佈看得出)。整合閘 `validate_priors_cascade.py`(從**先驗庫**經 `analyze_target.build_storyboard`
  → **真實 build_spine 骨架** → `build_animations`)對真實 robot 5 拆件 **5 AC 全 PASS**:I1 present+routing
  (路由到 cascade 類別、每件真峰 光暈1.336/身體1.271/右手1.177/頭1.176/左手1.18≥1.12)、I2 介面契約(每件首尾
  setup identity+特效 slot alpha=1,可插 Loop 間)、I3 **crux 跨件簽章**(各件峰時刻依真實件序
  [0.158,0.296,0.429,0.567,0.70] 嚴格遞增、散佈 0.542≥0.30、且非 combo 簽章=與 0g 正交)、I4 覆蓋率仍 1.0
  (cascade 列 prior_beats_unused)、I5 負對照(character_idle 產 0 cascade clip、非 cascade beat 不成波)。
  **關鍵發現:跨件簽章需兩條件並立,散佈單獨不足** —— I5(b) 負對照顯示 **Loop 散佈 0.50 甚至 > cascade 門檻 0.30**
  (甚至逼近 cascade 的 0.542),若簽章只看散佈就會**假陽性**;因 Loop 各件微呼吸峰時刻**散而無序**(非依件序遞增),
  cascade 簽章同時要求「散佈≥門檻 **且** 嚴格遞增」才正確排除。此鑑別力在**真實產線**再現(0h 只在手搭 fixture 驗過)。
  回歸:validate_priors(cov 1.0、unused 增列 cascade)、validate_cascade(0h)、validate_priors_combo_charge(H)、
  validate_priors_beats(E)、validate_more_beats(0g)、validate_beat_templates(0f)、validate_anim(+selftest)、
  validate_pivot_rotation(0i)、validate_scale_pivot(G-3)、round-trip validate_build 全 PASS。
  新增 cap `cascade_priors_integration` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
  見 `knowledge/s1-cascade-priors-integration.md`、圖 `knowledge/figures/s1_cascade_priors.png`。
- **S1 combo/charge 接進 genre 先驗庫(里程碑,2026-09-06,candidate H)** — 續 (E) 對 hit/reveal 所做,
  把 0g 的 **combo(連擊)/ charge(蓄力充能)** 主秀節拍併入 `genre_priors.py` 的 `slot_bigwin`(additive),
  讓 `build_spine --animate --genre slot_bigwin` **直出** combo/charge(接 H 前先驗僅 In/burst/hit/Loop/Out,
  0g 的 combo/charge 模板從未被產線觸發 —— 「模板就緒 ≠ 生成器接上」再現)。beat key 經 `beat_category` 路由到
  `gen_combo`/`gen_anticipate_hold`(key∈COMBO/CHARGE_KEYWORDS)。coverage 單調:Award 真值僅 In/Loop/Out →
  combo/charge 列 `prior_beats_unused`(誠實 PROPOSAL),覆蓋率仍 1.0。整合閘 `validate_priors_combo_charge.py`
  (從**先驗庫**經 `analyze_target.build_storyboard`→`build_animations`,補 0g 只驗合成模板的缺口)對真實 robot 5 拆件
  **5 AC 全 PASS**:H1 present+routing(路由到 combo/charge 類別、真峰 combo 1.347/charge 1.347≥1.12)、
  H2 介面契約(首尾 setup identity,可插 Loop 間)、H3 結構簽章(combo=遞增 impact 峰 [1.207,1.28,1.347]≥3、
  charge=峰前長蓄力佔比 0.456≥0.35,**兩簽章互斥**)、H4 覆蓋率仍 1.0 未擾動已驗先驗、H5 負對照(character_idle
  產 0 combo/charge clip、非 combo/charge beat 全無其簽章)。**關鍵發現:閘找出真實漏洞** —— H5 初跑抓到
  `burst`(reveal)被 `has_charge_signature` 誤判:charge 的 squash-hold 與 reveal 的 collapse-hold 峰前皆長時間
  <0.97,原簽章分不開。修法=加 **squash-floor**(峰前最低 scale 須 >0.5:charge 壓縮蓄力 ~0.85 是 squash、
  reveal 塌陷 ~0.02 是 collapse)—— **windup 是壓縮不是消失**,強化 `has_charge_signature`(0g 閘回歸仍 6AC PASS)。
  連帶:(E) 閘 P5(b) 負對照須把 combo/charge/cascade 也視為主秀類別排除(新增 `ALL_MAIN_SHOW_CATS`,因它們依設計
  共享 anticipation+settle 簽章)。回歸:validate_priors(cov 1.0、unused=['burst','hit','combo','charge'])、
  validate_priors_beats(E,5AC)、validate_more_beats(0g,6AC)、validate_beat_templates(0f)、validate_cascade(0h)、
  validate_anim(+selftest)、round-trip validate_build、--pivot-rotate/--scale-pivot build + 0i/G-3 閘 全 PASS。
  新增 cap `combo_charge_priors_integration` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
  見 `knowledge/s1-combo-charge-priors-integration.md`、圖 `knowledge/figures/s1_combo_charge_priors.png`。
- **S1 件繞關節 pivot 轉 keyframe(里程碑,2026-09-05,candidate 0i)** — 補 STATE 建議 **(G)**:把 S5 的
  接觸縫 pivot 餵進 S1 keyframe 生成器,讓件**繞關節 pivot 轉**而非件中心。**第一個把 S5(rig 幾何)→
  S1(keyframe)接起來的能力**。非 rig 下 bone 落件中心 O,原 `rotate` 讓件繞 O 轉(對肢體不物理:手臂
  該繞肩、頭該繞頸);`tools/analyzer/pivot_rotation.py` 在 rotate 外加**補償 translate**
  Δ(θ)=(R(θ)−I)(O−P),淨效果=繞 pivot P 轉,**完全不動骨架結構**(與 `--rig` 搬骨的結構性解法互補)。
  `build_spine --animate --pivot-rotate`(非 rig)**復用 `rig_layout` 的樹+接觸縫推斷**取 pivot。
  踩雷:**Δ 對 θ 非線性 → rotate 通道加密重取樣(dt=1/60)**才不會幀間漏(殘差 ~(1/8)|O−P|(dθ_rad)²)。
  `validate_pivot_rotation.py` 對**真實 Award 左手世界幾何 + 推得肩 pivot**(|O−P|=117px)**7 AC 全 PASS**:
  AC1 pivot 不動點殘差 **0.01px**、AC2 負對照繞件中心位移 **48.8px**(>>AC1)、AC3 件最遠點轉 94px、
  AC4 θ=0 幀 Δ=0(identity 介面保持)、AC5 剛性等距 0.01px、AC6 **端到端**經 `build_animations` 產 loop→
  `apply_pivots` 後仍有限/無縫/pivot 不動(內建負對照未套用會動 9.75px)、AC7 bezier 緩動仍成立。
  回歸:`validate_anim`(+`--selftest`)、round-trip `validate_build` 對 `--pivot-rotate` build 全 PASS
  (setup pose 與源 PSD **完全一致** —— 補償在 setup=identity 時為 0)。**關鍵發現:「幾何/模板就緒 ≠ 生成器
  接上」再現**(S5 早能推 pivot,keyframe 這次才用上);非線性補償**必須 densify**(正確性要件非美化)。
  新增 cap `pivot_rotate_keyframe` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
  見 `knowledge/s1-pivot-rotation-keyframe.md`、圖 `knowledge/figures/s1_pivot_rotation.png`。
- **S1 件繞關節 pivot 縮放(里程碑,2026-09-05 session 002,candidate 0i 延伸 G-3)** — 把 0i 的「繞關節
  pivot **轉**」推廣到「繞關節 pivot **縮放**」。In/Out/pulse 給件的 `scale`(In s≈0.02→1 長大、Out →0、
  pulse 峰 1.08)非 rig 下繞**件中心**脹縮 —— 手臂該**從肩伸長**。**一條公式統一旋轉+縮放**:
  `Δ=(M−I)(O−P)`,**M=R(θ)·diag(sx,sy)**(Spine TRS);0i 是 `S=I` 特例、`θ=0,s=1` 時 Δ=0(identity 保持)。
  **純均勻 scale 約 pivot 是相似變換**:`∀x |world(x)−P|=s·|x−P|`(取代 0i 剛性 AC 的判準)。
  `pivot_rotation.py` 延伸(`transform_matrix`/`pivot_delta_full`/`pivot_channels_srt`/
  `apply_pivots(include_scale=)` —— **`include_scale=False` 預設 = 0i 路徑逐位元不變**)+
  `build_spine --animate --scale-pivot`(含 `--pivot-rotate` 語意)。踩雷同 0i:**Δ 對 θ、s 皆非線性 →
  rotate 與 scale 都密網格重取樣**。`validate_scale_pivot.py` 對真實 Award 左手+推得肩 pivot(|O−P|=117px)
  **7 AC 全 PASS**:AC1 不動點 **0.0001px**、AC2 負對照繞件中心 **70.46px**(=0.6×117)、AC3 件最遠點相對變化 0.600、
  AC4 s=1 端點 Δ=0、AC5 相似 |w−P|=s|x−P| 偏差 **0.0001px**、AC6 **rotate 24°+scale 1.6 併** 0.037px(證 M=R·S 組合)、
  AC7 端到端經 `build_animations` pulse(limb scale+rotate 無 translate)pivot 不動 0.014px vs 負對照 22.14px。
  回歸:0i `validate_pivot_rotation`(逐 AC PASS)、`validate_anim`(+selftest)、round-trip `validate_build`
  對 `--scale-pivot` build 全綠(setup pose 不變)。**關鍵發現:0i 與 G-3 是同一仿射補償的兩分量、相似≠等距**
  (0i 到 P 距離不變、G-3 等比 s 倍)。新增 cap `scale_pivot_keyframe` L2 併入 `spine-anim-forge`(**仍 HOLD**)。
  見 `knowledge/s1-scale-pivot-keyframe.md`、圖 `knowledge/figures/s1_scale_pivot.png`。
- **S3 mesh 生成器：完成且對 4 個真實 mesh 收斂達標**(v2 strip 通用,見 `knowledge/s3-four-mesh-generalization.md`)。
- **S2 評估器套件:切圖閘已完成** — `evaluate_slicing.py`,main_draw 45/45 region 重組 MAE=0/0孤兒/0重疊,
  雙向負對照確認鑑別力(見 `knowledge/s2-slicing-evaluator.md`)。S2 尚缺:補圖閘、骨架閘。
- **S4 PSD-first 切圖:已對真實生產檔驗收通過(里程碑)** — `psd_slice.py` 對 2 份真實 PSD
  (`Symbol_Ww` 18件 / `robot_parts` 機器人 5件)切圖無損 PASS;機器人 5 圖層 ⇄ 真實 spine `Award` 的
  slot `機器人拆件/<圖層名>` 逐件吻合(+2px padding)。閘經 premultiplied 校正(透明區白底假性失敗)。
  見 `knowledge/s4-psd-to-spine-real.md`、`s4-psd-contract.md`(已用真實檔校準)。
- **S3 端到端對真實美術 mesh 驗收(里程碑,2026-08-19)** — `compare_robot_mesh.py` 對 Award
  機器人 3 mesh 件(光暈/左手/身體)生成 mesh,同 region 框內靜態覆蓋率 IoU **3 件全 PASS**
  (達美術基準 −0.03 內、0 孤兒),且頂點更省(37~48 vs 美術 78~98)。發現 **mesh uvs 是 region-local**;
  新增 `boundary-dense-v1` 軟邊 blob 模式(光暈 0.92→0.98)+ 通用 `prune_orphans`。
  ⚠️ 限制:weighted mesh 骨骼變形平滑度未驗(靜態 IoU 不涵蓋)。見 `knowledge/s3-robot-mesh-vs-award.md`。
- **S1 目標圖反推分析器:首個原型 + 真值驗收(里程碑,2026-08-19,使用者新增研究項目)** —
  `tools/analyzer/analyze_target.py`(分層 PSD → 五段規格:運動構件/周邊特效/動作分鏡/拆圖策略/補圖項目)
  + `validate_analyzer_award.py`(對 `robot_parts.psd ⇄ Award` 真值)**5 項校驗全 PASS**
  (件召回 1.0、特效 5/5、幾何無 mismatch、分鏡 In/Loop/Out+4 檔位全中、露出 4/4)。
  誠實界定:補圖需求**輸入契約相依**(分層 PSD 0 封閉破洞);#3 分鏡為類型先驗提案。見 `knowledge/s1-target-image-analyzer.md`。
- **S1 擴充:平圖流程 + 分鏡先驗庫(2026-08-19,使用者指定)** —
  (A) `segment_flat.py`+`validate_flat_recall.py`:平圖純 CPU 自動拆件 baseline;壓平 PSD 對真值召回顯示
  同材質/重疊角色 **0/5、0/18 語意召回**,僅「不相連塊」可靠(正對照 3/3)→ 佐證 PSD-first。
  (B) `genre_priors.py`+`validate_priors.py`:先驗庫 `slot_bigwin`(Award)、`slot_reveal`(main_draw)
  覆蓋率皆 **1.0** + 2 未驗證類型。修 2 bug(decomposability 反向、動畫名子字串誤判)。
  見 `knowledge/s1-flat-pipeline-and-priors.md`。
- **S1 端到端「目標圖→可載入 Spine 素材」打通(里程碑,2026-08-19)** —
  `build_spine.py`(analyze_target+psd_slice+generate_mesh_v2 → Spine 3.8 json+atlas+png)+
  `validate_build.py`(round-trip 重建 setup pose == 原 PSD composite)。robot(5件)/Symbol_Ww(18件)
  **全 PASS**(premult MAE 0.03/0.24、0 孤兒、0 未解析 attachment)。mesh/region 分派沿用分析器建議。
  誠實界定:只驗靜態幾何/貼圖編碼;動畫 keyframe / mesh 變形 / 關節 pivot 屬後續。見 `knowledge/s1-build-spine-end-to-end.md`。
- **S3 weighted mesh 變形評估器完成(里程碑,2026-08-27)** — 補上 `deform_eval` 只驗 unweighted 的缺口。
  `weighted_deform_eval.py` 在 Python 重現 Spine 3.8 bone world transform(transform=normal)+ weighted
  skinning + timeline 取樣(緊湊 bezier);`validate_weighted_deform.py` 對 Award 3 機器人 weighted mesh
  **三道校驗全 PASS**:①setup 自一致(3 件重建 0 自交);②藝術家不透明件(身體 98v/左手 80v)真實動畫
  全幀乾淨 si=0;③負對照鑑別力(左手打亂 si=21;身體近剛體用 amp=4 分離:藝術家 si=0 vs 打亂 si=54)。
  修 1 bug:**scale timeline 缺 channel 預設應為 1 非 0**(否則 mesh 塌陷成假性自交);degeneracy 改
  相對面積(避免 big-win scale-from-0 誤判)。發現**軟性加成件(光暈)容許自我重疊**(reveal t=0 精確 keyframe
  si=71,additive 混合無害)→ pass/fail 需依 attachment 語意分類。見 `knowledge/s3-weighted-deform-evaluator.md`、
  圖 `figures/s3_weighted_deform_eval.png`。**這是候選 2(BBW 權重生成)的前置品質閘,現已就緒。**
- **S5 rig pivot 推斷:首個能力 + 真值閘(里程碑,2026-08-29)** — 路線圖「唯一卡死環節」的
  **可客觀化子問題**:給拆件幾何 + 父子樹,推斷每根子骨關節 pivot。`tools/rig/infer_pivots.py`
  (contact-seam:關節=子件最靠近父件的 q 分位點質心,確定性純 CPU)+ `tools/rig/validate_pivots.py`。
  對 Award 機器人 rig 3 關節藝術家真值 **4 AC 全 PASS**(頭 22px/左手 11px/右手 25px,皆 2–5% 軀幹尺度;
  勝質心 baseline 21.6 vs 43px;random/swap/rect 三負對照皆爆閘)。**關鍵發現:pivot 準度=件輪廓保真**——
  region bounding-rect 代理右手誤差 406px,改從 atlas alpha 取真實輪廓降到 25px(PSD-first 論點在 rig 階段再現)。
  `spine-rig-pivot` 區塊 L2 → **HOLD**(僅單一 rig、pivot→bone 樹未接 build_spine)。軸向精修屬美術(A 類)。
  見 `knowledge/s5-rig-pivot-inference.md`、圖 `figures/s5_pivot_inference.png`。
- **S5 (d) `--rig`×`--weighted` 併用(里程碑,2026-08-31,session 002)** — 移除 `--rig`/`--weighted`
  **互斥限制**(原併用直接 `SystemExit`)。weighted mesh 的控制骨改掛**該件關節骨 `b_{nm}`**(座標轉相對局部),
  讓件同時能被關節articulate + 局部 weighted 變形。**純座標問題非演算法衝突**:setup 下父鏈皆純平移 →
  weighted bind 偏移**不用改** → setup 精確保留。`validate_rig_weighted_build.py` 對 robot_parts **4 AC 全 PASS**:
  ①結構(控制骨 parent==關節骨、rig 樹完好);②setup 逐頂點 **0.0000px** 不位移(vs weighted-only);
  ③自articulate(轉 `b_{nm}` rig 動 72/53px vs weighted-only **脫鉤 0px**)+ 鏈帶動(轉 rig 根 `b_身體`
  子件光暈隨動 73.9px vs 脫鉤 0px);④關節旋轉逐幀結構件 si=0/flip=0(effect additive 容忍)。
  **內建負對照=weighted-only 版位移=0**(鑑別力)。honest boundary:此資產 weighted 結構子件為空集
  (肢體是 region 件、weighted 只有身體=rig根+光暈=effect),多跳 weighted 肢體鏈需新素材(使用者資源)。
  新增 cap `rig_weighted_combo` L2 GREEN;`spine-rig-pivot` **仍 HOLD**(L3 硬缺口=多 rig 真值不變)。
  見 `knowledge/s5-rig-weighted-combo.md`。
- **S5 (d') 多跳 weighted 肢體鏈端到端驗收(里程碑,2026-08-31,session 003)** — 補上 combo 唯一的
  honest-boundary 缺口:「**weighted mesh 當鏈中段肢體(既是子又是父)**」在 robot_parts 無樣本
  (其肢體皆 region + 星形單跳,weighted 只有 body=根 + 光暈=effect)。造合成鏈 fixture
  `tools/mesh_gen/make_limb_chain_psd.py`(`body→arm→forearm→hand`,**arm/forearm 皆 weighted mesh**);
  `validate_rig_weighted_chain.py` 對 `build_spine --rig --weighted` **5 AC 全 PASS**:①鏈結構(鏈深 4≥3、
  **非星形**、控制骨掛各自關節骨);②setup 逐頂點 **0.00px**;③**遞迴帶動**——轉 `b_body`→forearm(隔 arm 一跳)
  隨動 **80px**、轉 `b_arm`→forearm 動而 body(祖先)**不動 0px**、weighted-only 版**全脫鉤 0px**(雙軌負對照:
  脫鉤 + 非後代不動 → 證鏈**方向性**);④region 葉件 hand 隨鏈(attachment 世界點);⑤逐幀 si=0/flip=0。
  **關鍵結論:併用機制深度無關**(setup 純平移論點推廣到任意深度鏈)→ 非新演算法,是**填補覆蓋率**。
  踩雷:PSD 寫檔 mac_roman 不吃 CJK 圖層名→用 ASCII;旋轉某骨不移其自身原點→region 葉件看 attachment 世界點。
  新增 cap `rig_weighted_chain` L2 GREEN;`spine-rig-pivot` **仍 HOLD**(L3 缺口=多 rig 真值不變,防固化)。
  見 `knowledge/s5-rig-weighted-chain.md`。
- **S1 (E) 主秀 beat 接進 genre 先驗庫(里程碑,2026-09-04)** — 把 0f 的 hit/reveal 併入 `genre_priors`,
  讓 `build_spine --animate --genre <g>` **直出主秀節拍**(先前 0f 只在合成 fixture 驗模板,產線未觸發)。
  診斷:`slot_reveal` 因命名含 `open`/`hit` 已自動受惠(open→reveal peak1.35、hit→hit peak1.348);
  **`slot_bigwin` 完全沒觸發 0f**(只 In/Loop/Out)→ **additive 補 `burst`(reveal)+`hit` beat**(不改既有 beat)。
  **coverage 單調非遞減**:Award 真值僅 In/Loop/Out(無 hit/burst token)→ 覆蓋率仍 **1.0/pass**,兩新 beat 列
  `prior_beats_unused`(誠實 PROPOSAL,主秀運動無命名真值)。整合閘 `validate_priors_beats.py`(**從先驗庫**經
  `analyze_target.build_storyboard`→`build_animations`,補 0f 只驗合成模板的缺口)對真實 robot 5 拆件 **5 AC 全 PASS**:
  P1 主秀 clip 真峰≥1.12(bigwin burst1.35/hit1.348、reveal open1.35/hit1.348)、P2 介面契約(reveal collapse→identity・
  hit 首尾 identity)、P3 結構簽章(hit_signature+reveal collapse-hold+峰後穿越≥2,逐 bone)、P4 覆蓋率仍 1.0 未擾動已驗先驗、
  P5 負對照(`character_idle` 產 0 主秀 clip、非主秀 beat 全無主秀簽章)。度量復用 `validate_beat_templates`
  (series/sign_changes/_hit_signature)確保判準一致。回歸:validate_priors / validate_anim(bigwin+reveal)+selftest /
  validate_beat_templates / --animate --deform(validate_anim+validate_deform_gen)全 PASS。**關鍵發現:模板就緒 ≠ 產線會用它**
  ——0f 模板要「被觸發」需先驗庫有對應 beat(又一「評估器/模板就緒 ≠ 生成器接上」實例)。新增 cap
  `main_show_priors_integration` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。
  見 `knowledge/s1-main-show-priors-integration.md`、圖 `knowledge/figures/s1_priors_beats.png`。
- **S1 cascade 跨件錯開波:第一個「跨件時序」主秀節拍(里程碑,2026-09-04,session 002,candidate 0h)** —
  補 STATE 建議 (F 續) **cascade**(跨件錯開 reveal)。0f/0g 的 hit/reveal/combo/anticipate_hold 全是**單件內**
  時序簽章(同 beat 套每件、每件時序相同);cascade 是**跨件**時序簽章 —— 每件依**件序相位** phase∈[0,1]
  錯開觸發成一道波,簽章不在單件曲線而在「**各件峰時刻的排序與散佈**」。`beat_templates.py` `gen_cascade`
  (pop 波:每件 identity→蓄力→pop(峰=c=LEAD+phase·SPAN)→阻尼回擺→identity,首尾 identity 可插 Loop 間)+
  **`gen_animations` 架構變更**:新增 `_PHASE_AWARE={"cascade"}`,`build_animations` 先過濾有效件算總數再對
  phase-aware 類別帶 `phase=pi/(nvalid-1)`(**這是生成器第一個 per-part 參數** threading;前四節拍對件無差別故不需)。
  `validate_cascade.py`(端到端經 build_animations 才會帶入 phase → 順帶證 threading 接上)對真實 robot 5 拆件
  **6 AC + 7 條負對照全 PASS**:C4 峰時刻 [0.158,0.296,0.429,0.567,0.700] 依件序嚴格遞增、散佈 0.542≥0.30;
  負對照=combo(同時序)spread≈0 非波、打亂/反序件序非遞增、**cascade 單件非 combo 簽章(證與 0g 正交=不同維度)**、
  單件無 spread 非波。回歸:0f/0g/(E) validate + build --animate/--selftest 全 PASS;keyword `Cascade_Wave`/`跨件波`/`sweep`→cascade。
  **關鍵發現**:cascade 簽章要**端到端量**不能只測 gen_cascade(phase 是 build_animations 配的);「模板就緒 ≠ 生成器接上」
  以新形式再現——這節拍**逼出** build_animations 的 per-part threading。新增 cap `cross_part_cascade` L2 併入
  `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。見 `knowledge/s1-cascade-beat.md`、圖 `knowledge/figures/s1_cascade.png`。
- **S1 擴充主秀 beat 庫:combo + anticipate_hold(里程碑,2026-09-04,candidate 0g)** — 補 STATE
  「下一個 bounded chunk」建議 (F)**更多主秀節拍**。續 0f 再加兩個 big-win 節拍,各有**互不相同、可量化**的
  客觀結構簽章:**combo**(連擊)=遞增 impact 峰數 ≥3(≥1.10 局部極大且嚴格遞增;單發 hit 僅 1 峰)、
  **anticipate_hold**(蓄力充能)=峰前長蓄力時間佔比 ≥0.35(hit 蓄力僅短暫 dip)。皆保 setup identity 介面
  (可插 Loop 間)、共用 0f 的 anticipation+settle。`beat_templates.py`(+`gen_combo`/`gen_anticipate_hold`,wire 進
  `gen_animations` combo/charge 類別)+ `validate_more_beats.py` **6 AC 全 PASS + 9 條負對照**:兩簽章**互斥**、
  單發 hit 與對稱脈衝皆非 combo/charge、**等峰 combo 非遞增**(證「遞增」是必要條件非只看峰數)。
  **關鍵發現:combo 鑑別子是「遞增」非只「多峰」;charge 用「時間佔比」非「深度」**(對峰值/取樣密度解耦最穩);
  impact 門檻 1.10 乾淨切點(loop 微呼吸 ≤1.03、hit settle 回彈 ~1.015 皆在門檻下)。回歸:0f validate_beat_templates 6AC、
  0d/0e validate_anim(+selftest)、(E) validate_priors 全 PASS。新增 cap `beat_library_expansion` L2 併入
  `spine-anim-forge`(**仍 HOLD**:運動基元先驗、單一真值資產,防固化)。見 `knowledge/s1-more-beats.md`、圖 `figures/s1_more_beats.png`。
- **S1 big-win 主秀 beat 模板(里程碑,2026-09-01,session 002,candidate 0f)** — 補 0d 主秀節拍只有
  `gen_pulse` 對稱三角脈衝的缺口,加兩個經典動畫原理:**anticipation(反向預備)+ settle/follow-through(阻尼回擺)**。
  `tools/analyzer/beat_templates.py`:`gen_hit`(蓄力→命中→阻尼回擺,首尾 identity 可插 Loop 間)、`gen_reveal`
  (藏→蓄勢 hold→炸開 overshoot→回穩,首 collapsed 尾 identity)。wire 進 `gen_animations`(新類別 hit/reveal,
  `hit`/`burst` 移出泛用 pulse;註冊放檔尾避 import 迴圈)。`validate_beat_templates.py`(對**真實 robot 5 拆件+role**
  端到端經 build_animations)**6 AC 全 PASS**:B1 well-formed / B2 可串接介面(hit 首尾 identity、reveal 首 collapsed 尾 identity)/
  B3 真峰(hit 1.348·reveal 1.35≥1.12)/ B4 anticipation(hit 命中前下蹲 0.931)/ B5 settle(hit `(scale-1)` 變號≥3 阻尼回擺)/
  **B6 負對照**(對稱脈衝 gen_pulse 判為非主秀、不歸位 FAIL B2、無峰 FAIL B3、真 hit 具簽章)。**關鍵發現:`(scale-1)` 符號
  變化數是分辨「主秀 hit」與「天真脈衝」的強鑑別子**(真 hit≥3、對稱脈衝僅單正峰 0 負向偏移)。真值界定:主秀 beat 無唯一
  正解(先驗手感),閘驗**客觀結構簽章非美感**;緩動幅度手感留使用者(A 類)。回歸:0d validate_anim(+selftest)、0e(+deform)、
  Symbol_Ww slot_reveal 全 PASS。新增 cap `storyboard_beat_templates` L2 併入 `spine-anim-forge`(**仍 HOLD**:運動基元先驗、
  單一真值資產,防固化)。見 `knowledge/s1-beat-templates.md`、圖 `figures/s1_beat_templates.png`。
- **S1 mesh deform timeline 生成(里程碑,2026-09-01,candidate 0e,讓軟件 mesh 本身會動)** — 補 0d
  只產 bone TRS + slot alpha、mesh 本身不變形的缺口。`tools/analyzer/gen_deform.py`:把真實 main_draw
  窗簾/陰影 deform 場(`deform_eval.real_deform_field`,UV 座標可轉移)UV 內插轉移到目標 mesh,beat 包絡
  (loop ucos 無縫 / intro settle-to-setup / pulse,首尾回 setup → 可無縫串接);peak 為真實場分數(≤0.7×)
  → 位移必 ≤ 真實裕度。`build_spine.py --animate --deform` 端到端(deform 預設 off,向後相容)。
  `validate_deform_gen.py` **7 AC 全 PASS**(結構/逐幀乾淨/loop無縫/setup介面/幅度校準/負對照/端到端生成 mesh 乾淨),
  gate=`deform_eval`(真實位移場,已驗 _checker_validated 可信)。**關鍵發現:閘抓的是「拓樸損壞」不是「幅度大」**
  —— 不連貫 scramble×3 場 **4/4 全破**,連貫真實場等比放大 ×4 反而 **4/4 不破**(合法運動方向);稀疏 12v 陰影
  對同幅度 scramble 較耐,負對照需 ×3 才穩定破。回歸:`validate_anim`(bone/slot)對 `--animate --deform` 仍 4AC PASS。
  新增 cap 區塊 `spine-anim-forge`(0d keyframe + 0e deform)L2 → **HOLD**(運動基元先驗、單一真值資產,防固化)。
  見 `knowledge/s1-mesh-deform-generation.md`。
- **S5 肢體父子樹自動推斷(里程碑,2026-08-31)** — 移除 rig pipeline **最後一個「取自先驗」環節**:
  `build_spine --rig` 的 `rig_layout` 原**假設星形**(每結構件直掛 body,root/父邊取自分析器 note);
  改由 `tools/rig/infer_tree.py` 由**拆件相鄰幾何自動推斷父子樹**(root=面積最大 trunk;父邊=接觸距離
  Dijkstra 最短路徑樹,**支援多跳肢體鏈**)。子件 pivot 改對**推得的父件**取接觸縫;bone 以拓樸序輸出。
  `validate_tree.py` 對 Award 機器人真值樹 **AC1–AC4 + 3 負對照全 PASS**(root 對、拓樸==真值、τ band
  穩定、合成鏈驗多跳;NC:隨機父≈1.4%、斷開左手父邊變、天真納光暈汙染樹→證 role 須輸入)。
  接進後 `validate_rig_build.py` 原 **4 AC 端到端回歸全 PASS**(rig_root=b_身體 自動推得)。
  **關鍵發現:root 須 area-primary 非 degree-hub**——純肢體鏈中間件 degree 最高卻非 root(trunk 在鏈端);
  且重疊 composite 下 degree 飽和(4 件互重疊 → 全 degree 3),area 才是決定訊號。
  新增 cap `limb_tree_infer` L2 GREEN;`spine-rig-pivot` **仍 HOLD**(L3 缺口=多 rig 真值不變,屬使用者資源)。
  見 `knowledge/s5-limb-tree-inference.md`。
- **S5 pivot→bone 父子樹寫入 build_spine(里程碑,2026-08-30)** — S5 脫離 HOLD 的**第二個要件**:
  `build_spine.py --rig` 把「關節=父子件接觸縫」接進組裝,產出帶**真正骨骼關節鏈**的可載入 Spine
  (結構子件掛 body、關節落接觸縫;bone 移到關節後 attachment 以 delta 位移保 setup pose;暫不與 `--weighted` 併用)。
  `validate_rig_build.py` 對 Award 機器人 PSD **4 AC 全 PASS**:①骨樹結構;②setup 不位移 max **0.00px**;
  ③pivot 安裝往返(local↔parent 換算)**0.04px**;④關節語意——轉子骨 25° 時 rig 繞接觸縫 vs 非 rig 繞件中心的
  縫撕裂量,3 件 **2.1–3.2× 全減半以上**(非 rig 版即負對照)。`pivot_end2end` **L0→L2 GREEN**。
  **關鍵發現(recalibrate 多 rig 建議)**:Award 47slots/77bones 中**只有機器人(4_LEG)是可拆肢體 rig**;
  `1_OMG`/`2_SUP`/`3_MEG` 皆為**單張角色圖 + 發光/小燈特效**,無接觸縫結構 → 第二個真值 rig 屬**使用者資源**,
  故 `pivot_end2end` 定 L2 非 L3、區塊維持 **HOLD**(防固化)。見 `knowledge/s5-rig-build-integration.md`、圖 `knowledge/figures/s5_rig_build.png`。
- **S3 weighted mesh 生成器完成(里程碑,2026-08-27,候選 2 主體)** — `generate_weighted_mesh.py`:
  輪廓 → triangle 三角化(max-area 控**內部取樣密度**)→ **heat-diffusion 骨綁權重**(BBW 純 CPU 近似,
  `(L+H)W=HP` 天然 partition of unity)→ Spine weighted 格式(bind 經逆骨變換)。`validate_weighted_gen.py`
  對 Award 不透明件**身體/左手 4 條 AC 全 PASS**(body nv 調到 == 藝術家 98、左手變形比藝術家更平滑、
  真實 Legend 動畫 si=0)。誠實限制:**軟性件(光暈極端 reveal)si 未追平藝術家手工非均勻拓樸**
  (additive 無害,閘歸 si-tolerant,不列硬性 fail);尚未端到端接 build_spine(達 L3 才 skill 化)。
  使 `spine-weighted-forge` 的 `bbw_weights`/`interior_sampling` L0/L1 → **L2**。見 `knowledge/s3-weighted-mesh-generator.md`、圖 `figures/s3_weighted_mesh_gen.png`。
- **S3 weighted mesh 端到端接 build_spine(里程碑,2026-08-27 → weighted-forge READY)** — `build_spine.py --weighted`
  端到端產出含 weighted skin 的可載入 Spine(輪廓→PCA 軸骨→heat 權重→全域骨 index + `build_meta.json`
  effect/structural 語意);`validate_weighted_build.py` 4 AC(可載入/setup 重建/輪廓 IoU/合成骨變形)對
  robot_parts **OVERALL PASS**(身體 IoU 0.937 變形 si=0;光暈 effect additive 容忍)。`weighted_end2end` L0→**L3**,
  `spine-weighted-forge` 區塊**達 skill 化門檻 READY**(check_readiness 實跑確認)。
- **skill 化機制建立(2026-08-27,使用者指定)** — 研究成果分區塊、防半成品固化成 skill。
  完成度機制 `tools/check_readiness.py`(實跑各區塊 validator → 成熟度矩陣 + skill 化門檻判定);
  策略 `skills/README.md`(L0–L4 階梯、門檻「核心能力≥L2 GREEN 且≥1 條 L3」、SemVer 維護政策);
  快照 `skills/READINESS.md`。**5 區塊**:`spine-mesh-doctor`(READY ✅)、`spine-asset-forge`(READY ✅)、
  `spine-slicing`(併 forge)、`spine-target-analysis`(折入 forge)、`spine-weighted-forge`(HOLD:BBW 未做)。
  **已固化首個 skill 套件** `skills/spine-mesh-doctor/`(v0.1.0,自含 evaluators + SKILL.md + references,
  自 assets 目錄可獨立跑,PASS)。防固化規則:評估器就緒≠生成器就緒(weighted-forge 閘 L2 但 BBW L0 → HOLD)。
  自驅迴圈 `prompts/run.md` 加步驟 4.5(里程碑跑 readiness + 達門檻才打包升版 + C 類回報)。
- **S1 分鏡→動畫 keyframe 完成(里程碑,2026-08-27,candidate 0d,讓素材「會動」)** —
  `tools/analyzer/spine_anim.py`(純 Python Spine 3.8 timeline 取樣器:緊湊 bezier/stepped/linear,無瀏覽器)
  + `gen_animations.py`(把 `#3 動作分鏡` 的 role×category 確定性轉成 bone TRS + slot alpha;loop 正弦取樣端點強制相等
  →無縫)+ `build_spine.py --animate` 端到端。`validate_anim.py` 對 robot(slot_bigwin)/Symbol_Ww(slot_reveal)
  **4 AC 全 PASS + 負對照(--selftest)全偵測**;intro/loop/outro 介面全落在 setup identity(任意串接無跳變),
  setup-pose round-trip 不受擾動。誠實界定:role→運動基元為先驗手感提案(非學自真值),緩動美感留使用者;
  mesh deform timeline 未生成。見 `knowledge/s1-storyboard-to-animation.md`。
- **⇢ S4(切圖+補圖)已交接給獨立排程(2026-08-28,使用者決策)** — S4 由專屬 Routine 跑在
  `claude/spine-s4-inpainting`(交接 `handoff_S4.md`、狀態 `STATE_S4.md`、指令 `prompts/run_s4.md`);
  **本主排程自此不再推進 S4**。切圖半邊已完成(PSD-first 對 2 真實 PSD 無損 + ⇄ Award 逐件吻合);
  補圖半邊為該排程主任務。S2 補圖閘亦隨之移出本排程(只留骨架閘)。
- **分支策略定案(2026-08-28,使用者決策)** — 診斷出 remote 累積 200+ 條 `claude/vibrant-franklin-*` 之因:
  舊 `run.md` 收尾用動態偵測啟動分支 + routine 每 run 自動開隨機名工作分支 → 每 run 增生一條。
  改為**主排程釘 `claude/spine-main`、S4 釘 `claude/spine-s4-inpainting`**,開頭 checkout 固定分支、收尾 push 回同名。
  本 `spine-main` 分支經**一次性合流**:以最完整的研究線(weighted 生成器+評估器+skill 機制)為底,
  併入 S1 keyframe(擇優 zjze4k 版)、S4 交接、分支釘定,去除重複評估器。見 `log/2026-08-28-003.md`、`log/2026-08-28-004.md`。

## 真實資產(已收進 `assets/`)

- `assets/main_draw.json`(真實骨架:28 bones / 40 slots / 9 anims / 4 unweighted mesh)。
- `assets/main_draw.atlas`(region 矩形;sheet `main_draw.png` 2023×1896)。
- **`assets/Symbol_Ww.psd`**(symbol,180×180,18 圖層)、**`assets/robot_parts.psd`**(機器人拆件 big win,713×693,5 圖層)。
- **`assets/Award.json` + `assets/Award.atlas` + `assets/Award.png`(2040²)+ `assets/Award2.png`(1780×1376)**
  (機器人對應的生產 spine,77 bones/47 slots/12 anims,雙頁 atlas;貼圖被縮小 ~0.70 打包)。
- ⚠️ **`main_draw.png` 像素檔尚缺**(只在對話中顯示,未存成檔)。像素級工作(裁切貼圖、
  texture IoU、實機截圖)在拿到該 PNG 前 BLOCKED;但 **deform 幾何分析不需要 PNG**。

## 下一步動作 (next action)

**S3 已推廣到全部 4 個 mesh(里程碑,2026-06-26)**:整合 AC 跑 curtain_left/right + shadow/shadow2。
- **v1(散點 Delaunay)不通用**:靜態 IoU 高但 curtain_right(19 si)/shadow(64 si)真實 deform 自交。
- **v2(strip)通用**:4 mesh 全 deform 乾淨;`rows=10,cols=3`(30v)IoU 全過藝術家基準 → 設為 v2 預設。
- 關鍵副產:**IoU 由 rows 決定、cols 不影響覆蓋率**;評估器先以藝術家真值自一致性(4 mesh si=0)確認可信。
- 詳見 `knowledge/s3-four-mesh-generalization.md`。標準指令 `validate_against_real.py --gen v2` 對 4 mesh 全 overall_pass。

> ⚠️ **範圍變更(2026-08-28)**:S4(切圖+補圖)已交獨立排程(見上「⇢ S4 已交接」),
> 下列候選 **3(SkelToJson)、4(補圖閘)不再由本主排程做**;本排程專注 S1/S2骨架閘/S3/S5。

下一個 bounded chunk 候選:
0. **S1 分析器接續**:(a) ~~規格 → 實際素材~~ ✅;(b) ~~平圖流程~~ ✅ baseline(CPU 到頂);
   (c) ~~分鏡先驗庫~~ ✅ 2 類型;(d) ~~分鏡 → 動畫 keyframe~~ **✅ 完成(2026-08-27,candidate 0d,見上)**;
   **續**:(e) 關節 pivot 推斷(件中心→相鄰件關節),供 S5;(f) keyframe 補 hit/open/reveal 主秀 beat 模板。
1. ~~PSD件→S3 mesh→對照 Award 真實 mesh~~ **✅ 已完成**。3 件靜態覆蓋率全 PASS。
2. **~~S3 weighted mesh + 內部取樣密度 + BBW 權重~~ ✅ 全部完成(2026-08-27,weighted-forge READY)**。
   - ✅ **前置閘已完成(2026-08-27)**:`weighted_deform_eval.py` + `validate_weighted_deform.py`,
     可量化任一 weighted mesh 在真實 bone 動畫下的自交/翻面/塌陷,且對藝術家真值 + 負對照雙向驗證可信。
   - ✅ **權重生成完成(2026-08-27)**:`generate_weighted_mesh.py`(heat-diffusion/BBW 近似 + 內部取樣密度)
     對不透明件 body/hand 4 AC 全 PASS(si=0、平滑度≈藝術家、body nv==98)。軟件(光暈)未追平為已知限制。
   - ✅ **端到端完成(2026-08-27,weighted-forge 達 L3 → READY)**:`build_spine.py --weighted`
     產 weighted mesh(輪廓→PCA 軸骨→heat 權重→全域骨 index)+ `validate_weighted_build.py`(4 AC:
     可載入/setup 重建/輪廓 IoU/合成骨變形)。robot_parts OVERALL PASS(身體 IoU 0.937 變形 si=0、
     光暈 effect additive 容忍)。依 `build_meta.json` 的 effect/structural 語意分類。
   - **下一步(仍在本排程)**:weighted-forge 併入 `spine-asset-forge` skill(C 類回報拍板);次要:軟件非均勻拓樸追平光暈、rig pivot(S5)。
3. ~~切圖→Spine JSON 組裝(SkelToJson)~~ **⇢ 屬 S4 範圍,已交獨立排程**(且 build_spine 已可端到端產可載入 Spine)。
4. **S2 骨架閘**(補齊 S2 樞紐;純 CPU)。⚠️ **S2 補圖閘已隨 S4 交接**,本排程不做。
5. **S5 骨架半自動**:關節 pivot 推斷 —— **接觸縫子問題 ✅(2026-08-29)+ 接 build_spine 骨樹 ✅(2026-08-30,見上里程碑)**。
   **續(達 L3 → 脫離 HOLD)**:(a) ~~pivot→bone 父子樹寫入 `build_spine`~~ **✅ 完成(--rig,L2 GREEN)**;
   (b) **多 rig 真值(唯一硬缺口,資源類)**:實查 Award **只有機器人一件可拆肢體 rig**(`1_OMG`/`2_SUP`/`3_MEG`
   為單圖+特效,無接觸縫)→ 需**使用者提供**第二個含多肢體接觸縫 + 藝術家 pivot 的分層/rig 檔;
   (c) ~~肢體父子樹自動推斷(原取自先驗 note)~~ **✅ 完成(2026-08-31,`infer_tree`,L2 GREEN,見上里程碑)**;
   (d) ~~`--rig`×`--weighted` 併用~~ **✅ 完成(2026-08-31 session 002,`rig_weighted_combo` L2 GREEN,見上里程碑)**;
   (d') ~~多層 weighted 肢體鏈(2+ 跳遞迴接觸縫)~~ **✅ 完成(2026-08-31 session 003,合成鏈 fixture 端到端 5AC PASS,
   `rig_weighted_chain` L2 GREEN,見上里程碑)** —— 證併用機制**深度無關**;藝術家真值仍屬使用者資源。
   人形 RTMPose/MediaPipe、非人形光流分群為後續。
6. **S1 反推分析器(影片輸入)**:需一支 benchmark 影片(repo 無影片資產,屬使用者提供)。
7. ~~spine_inspector 實機 round-trip~~:**⛔ CDN(jsDelivr)被網路政策擋(403);需使用者改政策或提供離線 spine-webgl。**

> **主排程近況**:S1(分析器+build+keyframe 0d+**mesh deform 生成 0e**+**主秀 beat 模板 0f/0g/0h**+**件繞關節 pivot 轉 0i**)、S3(mesh 生成+weighted 生成+變形評估,weighted-forge READY)、
> S2(切圖閘)皆已達里程碑;**S5 rig pivot 接觸縫(08-29)→ 接 build_spine 骨樹(08-30,--rig)→ 肢體樹自動推斷(08-31 s1)
> → `--rig`×`--weighted` 併用(08-31 s2)→ 多跳 weighted 肢體鏈端到端(08-31 s3)已全部完成**;S4 已交獨立排程。
> ⚠️ **S5 達 L3 的唯一硬缺口 = 多 rig 真值,但 Award 只有機器人一件可拆肢體 rig → 屬使用者資源(C/資源類待辦)**。
> **S5 的可自主子問題已收斂到位**(pivot 縫 + 樹推斷 + rig 組裝 + weighted 併用 + 多跳鏈,合成 fixture 覆蓋深度通用)。
> 建議下一個 bounded chunk(擇一,皆可自主):
> **(A) ~~S1 keyframe 補主秀 beat 模板~~ ✅ 完成(2026-09-01 session 002,candidate 0f,`storyboard_beat_templates` L2,見上里程碑)** ——
>   `beat_templates.py`(hit/reveal,anticipation+settle)+ `validate_beat_templates.py` 6AC + 負對照;
> **(B) ~~mesh deform timeline 生成~~ ✅ 完成(2026-09-01,candidate 0e,`spine-anim-forge` L2,見上里程碑)** ——
>   `gen_deform.py` 真實律動場轉移 + `validate_deform_gen.py` 7AC + `build --animate --deform` 端到端;續充實可做「律動場庫擴充」(需更多真實 deform 樣本,資源類);
> **(C) weighted-forge / rig 併入 `spine-asset-forge` skill**(需 **C 類使用者拍板** sync;打包政策見 `skills/README.md`);
> **(D) rig 真值資源**(**C/資源類**,阻塞 S5→L3):請使用者提供**第二個含多肢體接觸縫 + 藝術家 pivot** 的分層/rig 檔。
> **建議下一個(擇一,皆純自主):**
> **(E) ~~主秀 beat 接進 genre 先驗庫~~ ✅ 完成(2026-09-04,`main_show_priors_integration` L2,見上里程碑)** ——
>   slot_bigwin 補 burst/hit beat、slot_reveal 既有 open/hit;`validate_priors_beats.py` 5 AC + 覆蓋率仍 1.0;
> **(F) ~~更多主秀節拍~~**:**✅ combo + anticipate_hold(2026-09-04,candidate 0g)+ ✅ cascade 跨件錯開波
>   (2026-09-04 session 002,candidate 0h,`cross_part_cascade` L2,見上里程碑)** —— cascade 是**跨件時序**簽章,
>   與 0g 的單件時序簽章互補,已逼出 build_animations 的 per-part phase threading(`_PHASE_AWARE`)。
>   **續**(擇一,皆自主):cascade **reveal 波變體**(每件 start collapsed 依序現身,首非 identity;需處理多件 collapse
>   疊加對 argmax 的擾動)、或用**空間位置**決定波方向(左→右/中心外擴,件序相位改由 bd.x/徑向決定);
> **(G) ~~S1 (e) 關節 pivot 推斷接 keyframe~~ ✅ 完成(2026-09-05,candidate 0i,`pivot_rotate_keyframe` L2,見上里程碑)** ——
>   `pivot_rotation.py`(Δ=(R(θ)−I)(O−P) + 非線性 densify)+ `build_spine --pivot-rotate` + `validate_pivot_rotation.py`
>   7AC(AC2 繞件中心=內建負對照)。**續**(擇一,皆自主):
>   (G-1) `--rig` × `--pivot-rotate` 語意去重(rig 已把 bone 搬到關節,pivot-rotate 應自動略過該件,現以 `not rig` 全域關掉;
>    可細到 per-bone:effect 件在 rig 下掛 root/body 仍可受惠 pivot-rotate);
>   (G-2) pivot-rotate 套到 **hit/combo/cascade** 等主秀 beat 的 limb rotate(現各 beat 都會被 apply_pivots 掃到,
>    可加 AC 驗主秀節拍下 limb 也繞關節);**(G-3) ~~scale-about-pivot~~ ✅ 完成(2026-09-05 session 002,
>    `scale_pivot_keyframe` L2,見上里程碑)** —— 一條公式 `Δ=(M−I)(O−P)`、M=R·S 統一旋轉+縮放,`build_spine
>    --scale-pivot`,`validate_scale_pivot.py` 7AC(AC5 相似性=scale 版等距、AC6 rotate+scale 併證組合)。**續**(擇一,皆自主):
>    (G-1) 上述 `--rig`×`--pivot-rotate`/`--scale-pivot` per-bone 語意去重;(G-2) 主秀 beat 下 limb 繞關節的 AC;
>    (G-4) **shear-about-pivot / 非均勻 scale 的 AC**(Δ 公式已通用,只差非均勻 scale 的相似性→仿射保形驗證)。
> **(H) ~~combo/charge 接進 genre 先驗庫~~ ✅ 完成(2026-09-06,candidate H,`combo_charge_priors_integration` L2,見上里程碑)** ——
>   如 (E) 對 hit/reveal 所做,把 0g 的 combo/charge 併入 `genre_priors.slot_bigwin`,`build_spine --animate` 直出;
>   `validate_priors_combo_charge.py` 5 AC(覆蓋率仍 1.0、兩簽章互斥),副產 charge-vs-reveal squash-floor 鑑別子。
> **(I) ~~cascade 接進 genre 先驗庫~~ ✅ 完成(2026-09-06 session 002,candidate I,`cascade_priors_integration` L2,見上里程碑)** ——
>   如 (E)/(H),把 0h 的 cascade 跨件波併入 `genre_priors.slot_bigwin`,`build_spine --animate` 直出跨件波;
>   `validate_priors_cascade.py` 5 AC(I3 crux 件序相位 threading 端到端存活、覆蓋率仍 1.0),副產「跨件簽章需散佈+遞增兩條件並立」鑑別點(Loop 散佈 0.5 但無序→非波)。
> **(J) ~~tier 變體幅度差異化~~ ✅ 完成(2026-09-07,candidate J,`tier_variant_amplitude` L2,見上里程碑)** ——
>   `tier_variants.py`(增益只放大 identity 上方 overshoot、下方樓地板不動 → 介面/簽章對所有檔位保形)+
>   `build_spine --tier-variants` + `validate_tier_variants.py` 5AC(J3 幅度 Super<Mega<Omg<Legend 嚴格遞增、
>   J5 平增益守衛證閘可信)。**續**(擇一,皆自主):
>   **(J-2) ~~連擊數隨檔位遞增~~ ✅ 完成(2026-09-07 session 002,candidate J-2,`tier_variant_combo_count` L2,見上里程碑)** ——
>    `gen_combo(nhits=)` 通用生成遞增 nhits 峰(nhits=3 逐位元同 0g)、`tier_combo_hits` 重生成再套幅度增益(與 J 幅度軸正交)、
>    `validate_tier_combo_count.py` 5AC(K2 峰數 [3,4,5,6] 嚴格遞增、K4 正交、K5 平連擊數守衛);**續**:
>    (J-3) cascade 波速/散佈/件數隨檔位;(J-2') 其他 count-aware 節拍(如 charge 的蓄力段數/cascade 件數隨檔位)。
> **(G-4) ~~shear / 非均勻 scale 仿射保形 AC~~ ✅ 完成(2026-09-08,candidate G-4,`shear_pivot_affine` L2,見上里程碑)** ——
>   `transform_matrix_full`(真實 Spine local 含 shear)+ `pivot_delta_affine`/`pivot_channels_affine`/
>   `apply_pivots(include_shear=)` + `validate_shear_pivot.py` 7AC(AC4 crux=anisotropy 證相似性壞掉、AC6 det==cosφ 證真 Spine shear)。
>   **續**(擇一,皆自主):(G-4') 讓某主秀節拍(如斜拉 squash)實際產出 `shear` 通道 + build 帶 `include_shear=True`
>   端到端(現管路已通但 gen_animations 尚未產 shear,honest boundary);或 (G-1)/(G-2) 見下。
> **(G-4') ~~生成器產 shear 通道端到端~~ ✅ 完成(2026-09-08 session 002,candidate G-4',`shear_channel_generation` L2,見上里程碑)** ——
>   `beat_templates.gen_wobble`(斜拉 jelly wobble,阻尼 shearX 擺動,**第一個產 shear 的生成器**)+ `genre_priors.slot_bigwin`
>   加 wobble beat 直出 + `build_spine --shear-pivot`(include_shear=True)+ `validate_shear_gen.py` 5AC
>   (W1 crux shear 產出峰 16°、W2 阻尼振盪簽章、W4 端到端 pivot 殘差 <0.02px vs 負對照 8–24px、W5 天真單調 shear 簽章 FALSE)。
>   **續**(擇一,皆自主):(G-4'') wobble 接 tier 幅度差異化(shear 峰隨檔位遞增,比照 (J));或產 shearY / 斜拉 squash(shear+coupled scale)。
> **(G-4'') ~~wobble 接 tier 幅度差異化(shear 峰隨檔位遞增)~~ ✅ 完成(2026-09-10 session 001,candidate G-4'',`wobble_tier_amplitude` L2,見上里程碑)** ——
>   把 wobble 併入 `MAIN_SHOW_CATS` + `amplify_bone_tl` 放大 shear(`v'=g*v`)→ shearX 峰 Super16°<Mega21.6°<Omg27.2°<Legend33.6° 嚴格遞增、阻尼簽章每檔位保形;
>   J 閘 J3 改 channel-aware(SA.sample 不含 shear → `_shear_amp` 直讀)。`validate_wobble_tier.py` 5AC(T2 crux 峰遞增、T3 阻尼保形、T5 平增益守衛+通道隔離)。
>   **續**(擇一,皆自主):(G-4''') wobble 接 count-aware(晃動段數隨檔位,gen 時決定,比照 J-2);或產 shearY / 斜拉 squash(shear+coupled scale 雙通道耦合)。
> **(G-4''') ~~wobble count-aware(晃動段數隨檔位)~~ ✅ 完成(2026-09-11,candidate G-4''',`wobble_count_generation` L2,見上里程碑)** ——
>   `gen_wobble(nosc=)`+`_wobble_env(A,nosc)`(nosc==4 逐位元同 G-4' golden)、`TIER_WOBBLE_CYCLES`(Super4→Legend7)、`_build_beat(count=None)` 泛化 + `build_animations(tier_wobble_cycles=)`
>   依 cat 路由段數(combo/wobble 段數階梯獨立)、`validate_wobble_count.py` 5AC(U2 段數 [4,5,6,7] 嚴格遞增、U3 阻尼簽章+峰幅皆保、U4 正交、U5 平段數守衛+段數不外洩)。
>   **關鍵:結構軸×幅度軸雙軸檔位差異化可推廣**(count-aware 概念在 combo=scale 峰數、wobble=shear 段數兩通道皆成立)。
> **(G-4'''') ~~產 shearY / 斜拉 squash(shear+coupled scale 雙通道耦合)~~ ✅ 完成(2026-09-12,candidate G-4'''',`squash_shear_scale_coupling` L2,見上里程碑)** ——
>   `gen_squash`(shearX 阻尼擺 + 體積守恆非均勻 scale squash)第一個同時產 shear+非均勻 scale;`--shear-pivot`
>   端到端一般仿射 pivot 不動;`validate_squash_gen.py` 6AC(SQ3 體積守恆耦合、SQ5 一般仿射殘差 <0.02px、SQ6 兩條件獨立守衛)。
> **(G-4''''') ~~squash 接 tier 檔位差異化(耦合 amplify)~~ ✅ 完成(2026-09-21,candidate G-4''''',`squash_tier_coupled_amplify` L2,見上里程碑)** ——
>   `_amp_scale_coupled`(放大拉長軸 overshoot、壓縮軸=倒數 → scaleX·scaleY≡1 由建構保證)+ squash 併入 `MAIN_SHOW_CATS`
>   + `COUPLED_SCALE_CATS` 路由;`validate_squash_tier.py` 6AC(ST2 crux 每檔位守恆+非均勻/拉長遞增、ST5 crux 逐軸破守恆 0.10–0.15 vs 耦合 ≤1e-4)。
>   **第一個帶跨通道守恆約束的檔位軸 + 第一個 shear+非均勻 scale 雙通道同時檔位差異化**。
> **(G-4'''''-c) ~~squash count-aware(擠壓段數隨檔位)~~ ✅ 完成(2026-09-21 run 002,candidate G-4'''''-c,`squash_tier_count_aware` L2,見上里程碑)** ——
>   `TIER_SQUASH_CYCLES`(Super4→Legend7)+ squash∈`COUNT_AWARE_CATS` + `build_animations(tier_squash_cycles=)` 依 cat 路由 +
>   `build_spine --tier-variants` 帶入 `squash_cycles_for`;`validate_squash_count.py` 5AC(SC2 crux 段數 [4,5,6,7] 嚴格遞增 **且**每檔位每內部
>   極值 |scaleX·scaleY−1|≤2e-4 max 9.7e-05、SC4 正交含「段數單獨作用亦不破守恆」)。**結構(段數)軸已在 combo/wobble/squash 三通道成立;
>   帶跨通道守恆約束的類別 count-aware 要多驗一層守恆**。
> **(G-4'''''') ~~產 shearY(雙軸 shear)~~ ✅ 完成(2026-09-23,candidate G-4'''''',`twist_dual_axis_shear` L2,見上里程碑)** ——
>   `gen_twist`(斜扭果凍扭轉,反相雙軸阻尼 shear,**產線第一個驅動 shearY**)+ `genre_priors.slot_bigwin` 加 twist beat 直出
>   + `build_spine --shear-pivot` 端到端;`validate_twist_gen.py` 6AC(TW1 crux shearX 峰 16°·shearY 峰 11.2°≠0、TW3 crux 反相耦合
>   每內部極值 shearX·shearY<0、TW5 shearY≠0 驅動下 pivot 殘差 <0.015px vs 負對照 ≈24px、TW6 同相=旋轉偽裝守衛)。
>   `twist` 併入 `SHEAR_CATS`(shear-isolation 閘認定)。**一般仿射 M 的 4 自由度生成端至此全數被真實 beat 驅動過**。
> **(G-4''''''-tier) ~~twist 接 tier 幅度~~ ✅ 完成(2026-09-23 run 002,candidate G-4''''''-tier,`twist_tier_amplitude` L2,見上里程碑)** ——
>   twist 併入 `MAIN_SHOW_CATS`,兩軸同一 g 同比放大 → 兩軸峰隨檔位遞增且 φ 比值不變(反相雙軸 scale-invariant);`validate_twist_tier.py` 6AC PASS。
> **(G-4''''''-count) ~~twist 接 count-aware(扭轉段數 nosc 隨檔位遞增)~~ ✅ 完成(2026-09-24 run 001,candidate G-4''''''-count,`twist_tier_count_aware` L2,見上里程碑)** ——
>   `TIER_TWIST_CYCLES`(Super4→Legend7)+ twist∈`COUNT_AWARE_CATS` + `build_animations(tier_twist_cycles=)` 依 cat 路由;段數重生成後兩軸仍 `shearY=−φ·shearX`(φ 由建構保證)→ count × tier 幅度 × φ 保形三效正交;`validate_twist_count.py` 5AC PASS。**結構(段數)軸已在 combo/wobble/squash/twist 四通道成立**。
> **(G-4''''''-vol) ~~volume-conserving twist~~ ✅ 完成(2026-09-27 run 001,candidate G-4''''''-vol,`twist_volume_conserving` L2,見上里程碑)** ——
>   等向補償 scale `s=1/√cos(shearX−shearY)` → 全域 `det≡1`(擰而不變面積);shear+scale+rotate 三通道同時 = 塞滿一般仿射四自由度**且守恆**;
>   crux twist 補償**等向**(vs squash 非均勻)不同源;`gen_twist(vol_conserve=)`/`build_spine --twist-volume`;`validate_twist_volume.py` 6AC PASS。
>   **一般仿射四自由度 + 體積守恆全數在生成端成立**。
> **(G-4''''''-vol-tier) ~~volume-conserving twist 接檔位差異化~~ ✅ 完成(2026-09-29 run 001,candidate G-4''''''-vol-tier,`twist_volume_tier` L2,見上里程碑)** ——
>   tier 放大把兩軸 shear 同比拉大(Δ'=(shearX−shearY)·g)→ 補償變 `s'=1/√cos(g·Δ)` 對 g 非線性;`amplify_bone_tl(twist_vol=True)` 先放大 shear 再**依放大後 shear 重算**等向補償(`_recompute_twist_scale_iso`)→ det≡1 於任一檔位保持。crux:squash 耦合是倒數 `sy'=1/sx'`(與 shear 無關),twist 是 cos 反推重算(值來自 shear)—— 不同源;逐軸線性追不上非線性 cos(VTT3 負對照 Legend 0.11–0.31 vs 重算 ≤8.5e-5)。`validate_twist_volume_tier.py` 6AC PASS。**一般仿射四自由度 + 體積守恆已在生成端 base 與 tier 全檔位成立;twist 系列生成端能力至此全數接齊**。
> **(J-3) ~~cascade 波掃次數隨檔位(cascade 的 count-aware:第一個跨件時序通道的段數軸)~~ ✅ 完成(2026-09-29 run 002,candidate J-3,`cascade_tier_ripple_count` L2,見上里程碑)** ——
>   `TIER_CASCADE_RIPPLES`(Super1→Legend4)+ `gen_cascade(nrip=)`(整段均分 nrip 個壓縮 sweep 窗,nrip==1 逐位元同基礎)+
>   cascade 併入 `_count_maps`(留 `_PHASE_AWARE`,非 COUNT_AWARE_CATS)+ `_build_beat` phase-aware 分支吃 count;
>   `validate_cascade_count.py` 5AC PASS(X2 crux 波掃次數 [1,2,3,4] 遞增;X3 crux **每道 sweep 仍保跨件排序**——跨件 count 比單件 count 多驗這一層)。
>   **結構(段數)軸已在 combo/wobble/squash/twist 四單件通道 + cascade 跨件通道 成立**。
> **(J-4) ~~cascade 波速/散佈隨檔位~~ ✅ 完成(2026-09-30 run 001,candidate J-4,`cascade_tier_span` L2,見上里程碑)** ——
>   `TIER_CASCADE_SPAN`(Super0.54→Legend0.66)+ `gen_cascade(span=)` + `build_animations(tier_cascade_span=)` 重生成;
>   `validate_cascade_span.py` 5AC PASS(Y2 crux 隔離 nrip=1 散佈 [0.54..0.66] 遞增;Y5b crux 值增益 amplify 加不出散佈→證 span 需重生成)。
>   **揭示:「幅度」未必用幅度機制——時間位置的幅度(span)需重生成,不同於值幅度(post-hoc g)。**
> **(J-5) ~~cascade 波方向由空間位置決定~~ ✅ 完成(2026-10-01 run 002,candidate J-5,`cascade_dir_spatial` L2,見上里程碑)** ——
>   件序相位改由**空間排序鍵**(lr=bd.x 升/rl 降/co=徑向升/oc 降)給 rank;波形(SPAN/nrip/深度)不動,只重排哪件何時 pop。
>   `_cascade_phase_of` + `build_animations(cascade_dir=)` + `build_spine --cascade-dir`;`None`/`po` 逐位元同件序(零回歸)。
>   `validate_cascade_dir.py` 5AC PASS(Z2 crux 峰序依空間鍵遞增;Z5b crux lr 峰序==x 排序≠件序;Z4 三軸正交,量深度用 HIRES 消混疊)。
>   **跨件時序通道至此三條正交軸:結構(nrip)× 幅度(span)× 方向(dir);揭示波方向本是作者排版順序的隱含假設**。
> **(J-6) ~~cascade 波方向一般化為任意角投影~~ ✅ 完成(2026-10-02 run 001,candidate J-6,`cascade_dir_vector` L2,見上里程碑)** ——
>   把 J-5 的方向軸由 4 向離散補成連續:`cascade_dir` 吃**角度(度)或向量 (ux,uy)**,相位依件中心投影 `x·ux+y·uy` 排序;
>   lr/rl == θ=0°/180° 投影特例(逐位元相容),co/oc radial 保留。`_normalize_cascade_dir` + `build_spine --cascade-dir 90|"1,1"`;
>   `validate_cascade_dir_vector.py` 5AC PASS(V2 crux 投影序遞增;V5a crux 垂直90°[3,0,4,1,2]・對角45°[3,0,1,2,4] ∉ 全部 J-5 序)。
>   **honest:J-6 不是新正交軸,是方向軸由離散補成連續(取值擴充);跨件時序通道仍三條正交軸**。
> **(J-7) ~~cascade 方向取幾何自動來源~~ ✅ 完成(2026-10-02 run 002,candidate J-7,`cascade_dir_geo` L2,見上里程碑)** ——
>   sentinel `cascade_dir="geo"`:方向向量由件質心→最遠件導出(`derive_cascade_dir`),把方向軸取值來源由手感常數下推成幾何導出。
> **(G-4'''''-charge) ~~charge 蓄力階段數 count-aware~~ ✅ 完成(2026-10-03 run 001,candidate G-4'''''-charge,`charge_tier_count_aware` L2,見上里程碑)** ——
>   `gen_anticipate_hold(ncharge=)`(ncharge==1 逐位元同手調單發)+ charge∈`COUNT_AWARE_CATS` + `TIER_CHARGE_CYCLES`(Super1→Legend4)依 cat 路由重生成;
>   `validate_charge_count.py` 5AC PASS(CC2 crux 階數 [1,2,3,4] 嚴格遞增;CC5b **crux combo 判別子** combo 每階 hold 佔比 <0.60 → 證「每階持續 hold」是與 combo count 的鑑別子)。
>   **count-aware(段數軸)至此補齊全部單件主秀 beat:combo/wobble/squash/twist/charge 五通道 + cascade 跨件通道**。
> **(L-2) ~~序列組合 shear 通道覆蓋~~ ✅ 完成(2026-10-04 run 002,candidate L-2,`sequence_composition_shear` L2,見上里程碑)** ——
>   補 L 的 honest boundary:把 shear 納入 `spine_anim.sample()`(加性 shearX/shearY)+ `validate_sequence_compose_shear.py`
>   以含 shear 序列 In→wobble→squash→twist→Loop→Out 把接點無縫/回切還原/簽章在 shear 兩軸釘回歸閘;LS5 crux 盲點負對照
>   (只 shear 不連續接點 shear-aware diff=12.0 判非無縫、non-shear diff=0.0 擴充前誤判無縫→證補掉真實盲點)。
> **(L-3) ~~序列內 Loop 重播 N 次 + loopability 不變量~~ ✅ 完成(2026-10-05 run 001,candidate L-3,`sequence_loop_repeat` L2,見上里程碑)** ——
>   `compose_sequence` 的 order 本就支援重複鍵(`In→Loop×N→Out`),但 L 每 beat 只出現一次,從未驗過「同一 clip 重複 N 次」路徑。
>   新增 `gen_animations.is_loopable`(首幀==尾幀→可安全重播,含 shear,純判斷)+ `validate_sequence_loop.py` 5AC PASS。
>   **關鍵:compose 的時間去重把值不符接點抹成陡坡 → composed 恆 C0 → loopability 只能在 clip 端點層判(self-seam/is_loopable)**。
> **建議下一個 bounded chunk(擇一,皆純自主):**
> **(L-4) 把序列組合閘擴成「跨 beat 混場(crossfade / mix)」接點閘**(L-3 的 Loop 重播是 C0 拼接;crossfade 是**時間重疊 + 權重混合**,
>   compose 的純平移+去重做不到,需真正的 mix 機制;屬序列組合的下一個組合層軸,仍整合閘精神);或 **(L-3') loop 的 C1 速度連續閘**
>   (L-3 只驗 C0,loop 重啟的「速度頓挫」= 尾速度≠首速度;可量兩端有限差速度向量並驗連續,為 loop 手感客觀化);
> **(J-8) 擴充 geo `source`(PCA 主軸配確定性定號 / 主秀爆點方向),或讓 genre 先驗庫建議「用 geo 還是手感常數」**;
> **(G-4'''''-charge-amp) charge 的蓄力深度(floor)或 hold 長度隨檔位(另一條 charge 軸,與階數正交)**;或 **charge 以空間/幾何決定首階方向(比照 cascade J-5)**;
> **(G-1) `--rig`×`--pivot-rotate`/`--scale-pivot`/`--shear-pivot` per-bone 語意去重**。
> ✅ **(ENV) pre-existing RED 已修**(2026-10-01 run 001,candidate ENV-fix):`validate_analyzer_award.py` ④ 由嚴格相等改**召回**(`award⊆proposed`)+ 主秀 beat 誠實列 `beats_proposal_only` + `--selftest` 負對照。**check_readiness 現 0 RED / 52 GREEN**。見上里程碑。
> S5→L3 仍待 **(D) 多 rig 真值**(C/資源類,使用者提供)。

## 環境前置(已驗證可用)

- 排程容器為臨時,CPU 套件需每次重裝。**已確認可裝**:numpy 2.4.6 / opencv-python-headless 4.13.0 /
  triangle / scipy 1.17.1(見 `requirements.txt`)。
- 每次排程執行前先 `pip install -r requirements.txt`。

## 未解問題 / 阻塞 (open questions / blockers)

- ✅ **[已修 2026-10-01 run 001] pre-existing RED**:`tools/analyzer/validate_analyzer_award.py` 的 `4_storyboard_structure`
  原 `beats_match`(嚴格相等)因累積先驗提出 8 個主秀 beat vs Award `[In,Loop,Out]` 而永遠 False → RED。**已修**:改**召回**
  判準(`award ⊆ proposed`),主秀 beat 誠實列為 `beats_proposal_only`(同 validate_priors 的 prior_beats_unused 處理),
  並固化 `--selftest` 負對照證閘仍有鑑別力。`check_readiness.py` 現 **0 RED / 48 GREEN**(2 個 analyzer gen 閘 RED→GREEN)。
  見上里程碑 candidate ENV-fix + `knowledge/s1-analyzer-storyboard-recall-gate.md`。**提醒仍成立**:`check_readiness.py` 不呼叫
  `sys.exit` 故總是 exit 0,判 RED 須看各閘 `閘:GREEN/RED`,不能用 exit code。
- ❓ 排程頻率未定(使用者尚未決定)。
- ✅ `main_draw.png`(2023×1896,含 alpha)已收進 `assets/`;texture/IoU 已解鎖。atlas 切圖工具見 `tools/mesh_gen/atlas_crop.py`。
- ❓ 切圖/補圖(S4)最大槓桿是「能否要到分層 PSD」— 屬使用者層級決策。
- ℹ️ spine_inspector 實機 round-trip 需瀏覽器自動化(headless),尚未設置。

## 進度摘要 (progress log)

- 2026-10-05 run 002:**S1 自接點 C1(速度)連續 / C1-loopability(里程碑,candidate L-4)** — 關掉 L-3 誠實列出的
  honest boundary(`is_loopable` 只驗 C0,明記不保證 C1 速度連續)。延續 L/L-2/L-3/G-2 整合/組合閘選題,**不加參數軸**。
  全 additive:新增 `gen_animations.loop_seam_velocity_gap`(自接點 C1 不連續量 `max|v_end−v_start|`,單側有限差分,純量測)
  + `is_c1_loopable`(C0 ∧ C1,嚴格更強)+ `validate_sequence_loop_c1.py`。5AC PASS(真實 robot 骨架):C1a present+C0
  複驗+非空驗、C1b crux metric 良定義(gap 對 h bit-stable=端點切線非 artifact;須 clip 端點層量,跨 composed 接點被 L-3
  時間去重抹平恆 C0)、C1c crux Loop gap 0.188<1 is_c1_loopable=True・分解 剛體 limb rotate 精確 C1(~1e-12)唯一殘差=光暈
  呼吸(scaleY 0.024/alpha 0.188)、**C1d crux C1 獨立於 C0**:{Loop,hit,combo,charge,cascade} 全 is_loopable=True(C0
  不能鑑別)但 C1 gap Loop 0.188 vs 主秀 ≥64(ratio 340×)→ 證 is_loopable 單獨會誤把單發 beat 當『可安全重播』,C1 是
  鑑別子;is_c1_loopable 對主秀全 False、C1e 負對照+空驗守衛(a crux 三角脈衝 C0-loopable 但注入 kick gap 2.0>1 →
  is_c1_loopable=False 抓出 is_loopable 看不到的頓挫;b 空驗守衛 靜止 clip gap=0 trivially C1 但端點速度 0 無運動→須配非靜止;
  c In 非 C0-loopable→C0 先否決)。回歸:check_readiness 0 RED / 57 GREEN(新增 cap `sequence_loop_c1` L2 併入
  `spine-anim-forge` 仍 HOLD;既有 56 閘逐一 GREEN 證兩新純量測函式零回歸)。關鍵發現:①is_loopable(C0)會誤把單發主秀
  beat 當可安全重播(首尾皆 identity→C0 全 True,但自接點速度突變 64~167 deg/s 符號翻轉→平鋪頓挫),C1 是鑑別子(真簽章
  常需兩獨立條件並立);②同一支 Loop 在不同通道有不同階連續性(剛體 limb rotate 精確 C1、光暈 breathing 只 C0);
  ③C1 metric 良定義須證對 h 不敏感(bit-stable=真切線)且須在 clip 端點層量。honest:Loop 是否該完美 C1 屬美術(A 類,
  光暈 0.19 kick 為已知邊界);vel_tol=1.0 量級選擇;無改任何生成/產線值;單一真值資產。見 `knowledge/s1-sequence-loop-c1.md`。
- 2026-10-05 run 001:**S1 序列內 Loop 重播 N 次 + loopability 不變量(里程碑,candidate L-3)** — 延續 L/L-2/G-2
  整合/組合閘選題,**不加任何參數軸**。`compose_sequence` 的 `order` 本就可重複同一 beat 名(`In→Loop×N→Out`),這正是真實大獎
  序列形態(進場→Loop 重播待機→收尾),但 L 每 beat 只出現一次,**從未有閘**驗過「同一支 clip 重複 N 次」路徑。全 additive:
  新增 `gen_animations.is_loopable`(判「首幀==尾幀(含 shear)→ 可安全重播」,純判斷不改值)+ `validate_sequence_loop.py`
  以 `In→Loop×3→Out` 從先驗庫→真實 robot 骨架→build_animations 把重複鍵 offset 累加/自接點無縫/N 份逐幀還原/非靜止嚴格週期
  釘回歸閘。5AC PASS:LP1 present+loopable+offset([0.6,2.6,4.6]・總時長 7.0)、LP2 crux 自接點無縫(Loop→Loop self-seam 0.0)、
  LP3 periodicity(N 份去 offset 逐幀還原孤立 Loop 0.0 且彼此逐幀相同)、LP4 non-static(內部運動 5.0)+嚴格週期
  (`sample(t)==sample(t+Loop_dur)` 0.0)、**LP5 負對照**(a crux In is_loopable=False・自接點 40・且 tiled-In composed 仍看似
  C0→證須 clip 端點判;b Out 自接點 25;c crux 空驗守衛 靜止 clip loopable 且自接點 0 但 LP4 非靜止=0→證須非靜止+嚴格週期)。
  **踩雷:初版想從 composed 時間軸量 wrap C0 跳變(sample(bt−ε) vs sample(bt+ε))對合格 Loop 量到 3e-3 誤判 —— 那是真實速度
  的量測 artifact;更發現 compose 的時間去重把值不符接點抹成陡坡而非真跳變 → composed 恆 C0 → loopability 只能在 clip 端點層判。**
  check_readiness 全綠 0 RED / 56 GREEN(新 cap `sequence_loop_repeat`)。**關鍵:①compose 去重讓 composed 恆 C0,loop 判準必須
  在 clip 端點層(is_loopable);②首尾 identity→loopable 只是 C0,有意義 loop 需非靜止+嚴格週期兩條件並立;③重複鍵的 offset
  累加/逐幀還原/彼此相同三者並驗**。honest:N 為 PROPOSAL(A 類);只驗 C0 不驗 C1;無改任何生成/產線值;anim-forge 仍 HOLD。
  見 `knowledge/s1-sequence-loop-repeat.md`。
- 2026-10-04 run 002:**S1 序列組合 shear 通道覆蓋(里程碑,candidate L-2)** — 補 candidate L 誠實列出的 honest
  boundary:L 的序列組合閘用 `spine_anim.sample()` 做接點/回切比對,但 `sample()` **原本只取 rotate/translate/scale/
  alpha,不取 shear** → L 正向序列刻意只用無 shear 的 hit/combo/charge/cascade 繞過盲點。**不加任何生成能力**,只
  (1) 把 shear 納入 `sample()`(加性:per-bone 新增 shearX/shearY 預設 0,既有索引既有鍵呼叫端逐位元不變);(2) 以
  含 shear 序列 `In→wobble→squash→twist→Loop→Out` 把 compose 的接點無縫/回切還原/簽章在 shear 通道釘回歸閘。
  `validate_sequence_compose_shear.py` 5AC PASS:LS1 present+shear 真被驅動(峰 15.27°)、LS2 crux 接點無縫含 shear
  (0.0<1e-3)、LS3 faithful concat 含 shear(回切逐幀還原 0.0<1e-4)、LS4 in-context shear 阻尼振盪+twist 反相簽章、
  **LS5 crux 盲點負對照**(只 shear 不連續接點:shear-aware diff=12.0 判非無縫、non-shear diff=0.0 擴充前誤判無縫→
  證補掉真實盲點)。**踩雷:稠密取樣序列不能直接套關鍵幀版 `_extrema_mags_decreasing`→新增 `_signed_extrema` 先抽
  局部極值**。check_readiness 0 RED(新 cap `sequence_composition_shear`)。**關鍵:①取樣器覆蓋通道數決定閘能看見哪些
  不連續,補一條通道=補所有下游閘的鑑別力;②證「擴充補掉真盲點」須同一接點跑擴充前後兩種 diff 對照**。honest:
  驗證器覆蓋修正非新生成能力;anim-forge 仍 HOLD。見 `knowledge/s1-sequence-compose-shear.md`。
- 2026-10-04:**S1 大獎序列組合:把各 beat clip 串接成單一可播放序列(里程碑,candidate L)** — 承 G-2 選題精神,
  刻意選**整合/組合閘**而非再加參數軸。`build_animations` 產的是各自獨立 clip(首尾 setup identity),**從未有閘**驗過
  真串接成單一 timeline 時「接點無縫 / 回切逐幀還原 / 簽章在序列脈絡中仍成立」。全 additive:`gen_animations.compose_sequence`
  (純時間平移 + 接點去重)把跨 beat 串接顯式做出(`In→hit→combo→charge→cascade→Loop→Out`),直指 north star「產出大獎動畫」。
  `validate_sequence_compose.py` 5AC PASS:L1 well-formed+present、L2 crux 接點無縫(殘差 0.0<1e-3)、L3 faithful concat
  (回切逐幀還原 0.00<1e-4)、L4 in-context 簽章(combo/cascade/charge 在序列中仍成立且==孤立 clip)、L5 負對照
  (a crux burst collapse-起手插中段→接點 30.0 判非無縫;b Out 插中段;c composability 發現:主秀 beat 可自由排序)。
  **踩雷:接點去重丟後者首幀會連帶丟 outgoing 緩動 curve(緩動掛起點幀)→ L3 殘差 7.09;改丟前者尾幀 → 0.00 還原。**
  check_readiness 0 RED / 54 GREEN(新 cap `sequence_composition`)。**關鍵:①各 beat 首尾 identity ≠ 串起來無縫可播放有 AC;
  ②去重無損性取決於保留帶正確 outgoing curve 的幀;③identity-介面構成可自由排序 beat 集合,進出場 collapse 端是唯一位置約束。**
  honest:排序 PROPOSAL、shear 通道未覆蓋、單一真值資產;anim-forge 仍 HOLD。見 `knowledge/s1-sequence-composition.md`。
- 2026-10-03:**S1 charge 蓄力充能階段數隨檔位遞增:count-aware 補齊全部單件主秀 beat(里程碑,candidate G-4'''''-charge)** —
  補最後一個尚未接 count-aware 的單件主秀通道 charge。`gen_anticipate_hold(ncharge=)`(ncharge==1 逐位元同手調單發 golden)、
  `TIER_CHARGE_CYCLES`(Super1→Legend4)、charge∈`COUNT_AWARE_CATS`、`build_animations(tier_charge_cycles=)` 依 cat 路由重生成再疊幅度增益。
  **crux(與 combo count 的鑑別)**:combo 與 charge count 外形相同(N 遞增 scale 峰),計數簽章須多驗一層「每階 hold 佔比 ≥0.60」
  (combo 每階 0.31–0.34 → FAIL)。`validate_charge_count.py` 5AC PASS;check_readiness 0 RED / 52 GREEN(新 cap `charge_tier_count_aware`)。
  **count-aware 至此補齊 combo/wobble/squash/twist/charge 五單件通道 + cascade 跨件通道**。見 `knowledge/s1-charge-tier-count.md`。
- 2026-09-21:**S1 squash 接檔位差異化:體積守恆耦合 amplify(里程碑,candidate G-4''''')** — 補 G-4''''
  的 honest boundary(squash 未接 tier 幅度,逐軸 `_amp_scale` 破守恆)。`_amp_scale_coupled`(拉長軸 overshoot
  放大、壓縮軸=倒數)使 `scaleX·scaleY≡1` 由建構保證在任一檔位保持,擠壓非均勻度與同源 shear 峰皆隨檔位嚴格遞增
  → 第一個帶跨通道守恆約束的檔位軸、第一個 shear+非均勻 scale 雙通道同時檔位差異化。squash 併入 `MAIN_SHOW_CATS`
  + `COUPLED_SCALE_CATS` 路由。`validate_squash_tier.py` 6AC 全 PASS(ST2 crux 每檔位守恆+遞增、ST5 crux 逐軸破守恆
  0.10–0.15 vs 耦合 ≤1e-4 >500×);18 回歸閘全綠(K5c 排除 SHEAR_CATS 修 combo impact 指標對 squash 的誤判);
  `build_spine --tier-variants --shear-pivot` 直出 squash__{tier} pivot 殘差 <0.06px、validate_build round-trip
  overall_pass。cap `squash_tier_coupled_amplify` L2;anim-forge 仍 HOLD。honest boundary:squash count-aware
  (nosc 已備參數未接)、shearY≡0。見 `knowledge/s1-squash-tier-coupled-amplify.md`。
- 2026-09-12:**S1 生成器產耦合 shear + 非均勻 scale(體積守恆擠壓)端到端(里程碑,candidate G-4'''')** —
  補 G-4/G-4' 留到現在的 honest boundary(shearY≡0、斜拉 squash 為後續)。`gen_squash` 是第一個同時產
  shear+非均勻 scale(sx≠sy)的生成器:shearX 阻尼擺動 + 每極值施體積守恆 squash(scaleX=1+q_i、
  scaleY=1/(1+q_i),q_i=Q·rⁱ)⇒ scaleX·scaleY≡1 且 scaleX≠scaleY,首尾 identity。**純 shear 只是相似特例;
  shear+非均勻 scale 才是真正一般仿射** —— G-4 的 Δ=(M−I)(O−P) 第一次被生成器產的非均勻 scale+shear 同時驅動。
  `genre_priors` 加 squash beat 直出;`build_spine --shear-pivot` 端到端一般仿射 pivot 補償(殘差 0.005–0.018px
  vs 負對照 9–33px)。`validate_squash_gen.py` **6 AC 全 PASS**(SQ3 體積守恆耦合 crux、SQ5 一般仿射 pivot 不動、
  SQ6 兩條件獨立守衛+耦合隔離+加性)。新增 `tier_variants.SHEAR_CATS`;shear-isolation 閘(shear_gen W5b/
  wobble_tier T4)改以此認定。**16 閘全綠 + round-trip validate_build overall_pass**。cap
  `squash_shear_scale_coupling` L2;anim-forge 仍 HOLD。honest boundary:squash 未接 tier(需耦合 amplify)、
  shearY≡0、count-aware nosc 未接。見 `knowledge/s1-squash-shear-scale-coupling.md`、圖 `s1_squash_coupling.png`。
- 2026-09-08 session 002:**S1 生成器產出 shear 通道端到端:斜拉 wobble beat(里程碑,candidate G-4')** —
  補 G-4 的 honest boundary(公式/閘就緒但**沒有 beat 產 shear 通道**,AC7 只用合成 shear)。讓 `gen_wobble`
  (斜拉 jelly wobble,純 shearX **阻尼擺動** 0→A→−rA→+r²A→−r³A→0,首尾 identity)**實際產 shear**(第一個),
  經 `genre_priors.slot_bigwin` 加 wobble beat **直出**;`build_spine --shear-pivot`(include_shear=True)端到端補償。
  **又一「公式/模板就緒 ≠ 生成器接上」實例**。全 additive(gen_animations 註冊 wobble、build summary 回報
  pivot_centers/joints)。`validate_shear_gen.py`(先驗庫→真實 robot 骨架→build_animations)**5 AC 全 PASS**:
  W1 present+shear 產出(crux 峰 16°、5 bone 全帶)、W2 阻尼振盪(繞 0 變號 4 + 極值 [16,8,4,2] 遞減)、
  W3 identity 介面、**W4 端到端 pivot 殘差 0.004–0.013px vs 負對照 8–24px(arm 50–164px)**、W5 負對照
  (天真單調 shear 簽章 FALSE・僅 wobble 帶 shear・移除 wobble 其餘 beat 逐位元不變)。**關鍵:阻尼簽章需
  「振盪+遞減」兩條件並立**(天真單調 shear 有值但無變號→W5a 證閘可信);shear 隔離讓補償對象明確、零回歸。
  honest:斜拉 wobble 為 PROPOSAL、shearY≡0、tier 變體未接。回歸 priors/tier/beat/pivot 系列 + round-trip
  (--shear-pivot,premult MAE 0.031、setup 不變)全綠。cap `shear_channel_generation` L2;anim-forge 仍 HOLD。
  見 `knowledge/s1-shear-channel-generation.md`。
- 2026-09-08:**S1 件繞關節 pivot 一般仿射:非均勻 scale + shear(里程碑,candidate G-4)** — 補建議 (G-4)。把
  0i(繞 pivot 轉,M=R)/ G-3(均勻縮放,M=R·sI=相似)推廣到**非均勻 scale + shear**(M 是一般仿射、非相似),
  **同一條 Δ=(M−I)(O−P)** 仍讓 pivot 精確不動、`world(x)−P=M(x−P)` 精確(仿射保形)。矩陣改真實 Spine local
  `transform_matrix_full`(含 shear,shx=shy=0 逐位元退化回 G-3);真 Spine shear 以 `det(pure shearX φ)=cosφ`
  鎖定(天真 unit-shear det≡1)。全 additive(`pivot_delta_affine`/`pivot_channels_affine`/
  `apply_pivots(include_shear=)`,0i/G-3 byte-for-byte)。`validate_shear_pivot.py`(真實 Award 左手+肩 pivot)
  **7 AC 全 PASS**:AC1 非均勻 scale 不動點 0.0001px、AC2 shear 25° 0.012px、AC3 仿射保形 4e-4px、**AC4 crux
  相似性壞掉**=anisotropy 均勻 0 / 非均勻 0.40 / shear 0.43、AC6 det==cosφ、AC7 端到端 include_shear=True
  0.05px vs 負對照 93px。**關鍵:相似→仿射,判準必換**(等距-類比 `|w−P|=s|x−P|` 失效→改仿射保形 + anisotropy
  鑑別)。honest boundary:公式/閘就緒但 gen_animations 尚未產 shear 通道(管路已通,AC7)。回歸 0i/G-3/
  round-trip(--scale-pivot)/tier/priors/beat 系列全綠。cap `shear_pivot_affine` L2;anim-forge 仍 HOLD。
  見 `knowledge/s1-shear-pivot-affine.md`。
- 2026-09-07 session 002:**S1 combo 連擊「數」隨檔位遞增(里程碑,candidate J-2)** — 續 (J):(J) 檔位變體只差
  **幅度**,combo 各檔位仍同樣三連擊。本次補上 combo 的 impact 峰**數**=`nhits` 隨檔位嚴格遞增(Super 3→Legend 6)。
  **幅度增益加不出連擊數**(峰「數」是關鍵幀拓樸,必須 gen 時決定,事後 amplify 只放大既有峰)→ 走 `tier_combo_hits`
  對 combo 檔位變體以該檔位 nhits **重生成**再套幅度增益,與 (J) 幅度軸**正交可疊**(峰數 [3,4,5,6] × overshoot
  [0.347,0.469,0.591,0.730] 皆遞增)。`gen_combo(nhits=3)` 逐位元同 0g(向後相容)、`nhits≠3` 通用生成;
  `build_animations(tier_combo_hits=None)` 預設逐位元同 (J)(加性 opt-in)。`validate_tier_combo_count.py`(先驗庫→
  真實 build_spine robot 骨架→build_animations)**5 AC 全 PASS**(K1 backward-compat・K2 crux 峰數 [3,4,5,6] 遞增・
  K3 每檔位仍 combo 簽章/settle/**非 charge**/幅度單調・K4 正交・K5 平連擊數守衛+count 不外洩)。**踩雷:連擊變多恐誤入
  charge 長蓄力簽章** → 擊間微回設 0.985(>0.97)使 hold-frac 反隨 nhits 下降(0.30→0.12)→ combo↔charge 互斥保持。
  回歸全綠(含 J 幅度-only 閘不變、round-trip --tier-variants build)。cap `tier_variant_combo_count` L2;anim-forge 仍 HOLD。
  見 `knowledge/s1-tier-variant-combo-count.md`。
- 2026-09-07:**S1 檔位(tier)幅度差異化(里程碑,candidate J)** — 把 `genre_priors.slot_bigwin` 宣告已久卻
  **從未被生成器使用**的 `tiers=[Super,Mega,Omg,Legend]` 接上產線:主秀 beat 依檔位產出幅度差異化變體
  `{beat}__{tier}`(檔位愈高愈爆)—— **又一「宣告就緒 ≠ 生成器接上」**。`tier_variants.py` 增益規則對介面契約與
  結構簽章皆保形(scale 只放大 identity **上方** overshoot、下方 squash/collapse 樓地板不動、rotate/translate
  對 0 對稱放大、alpha 不動;base=Super g=1.0 逐位元同無檔位輸出)。`build_animations(...,tier_gains=)`(附加)+
  `build_spine --tier-variants`。整合閘 `validate_tier_variants.py`(先驗庫→真實 build_spine robot 骨架→
  build_animations)**5 AC 全 PASS**(J1 present+routing・J2 每檔位介面契約・J3 crux 幅度 Super<Mega<Omg<Legend
  嚴格遞增・J4 每檔位結構簽章保持・J5 負對照+平增益守衛)。**關鍵:增益只放大 identity 上方 overshoot、不動下方
  樓地板與時間軸 → 端點/簽章對所有檔位保形**(蓄力深度/藏匿是結構語意非大獎強度,誠實檔位無關;天真均勻縮放會把
  reveal collapsed 0.02 在 g>1 推成負值翻面)。回歸全綠(含 --tier-variants round-trip)。cap `tier_variant_amplitude`
  L2;anim-forge 仍 HOLD。見 `knowledge/s1-tier-variant-amplitude.md`。
- 2026-09-06 session 002:**S1 cascade 接進 genre 先驗庫(里程碑,candidate I)** — 續 (E)/(H),把 0h 的 cascade
  (跨件錯開波)併入 `genre_priors.slot_bigwin`(additive),`build_spine --animate` 直出跨件波。cascade 比 (E)/(H)
  多驗一層(跨件時序簽章→件序相位 threading 須端到端存活)。`validate_priors_cascade.py`(先驗→真實 build_spine
  骨架→build_animations)5 AC 全 PASS。關鍵發現:跨件簽章需「散佈≥門檻 **且** 依件序嚴格遞增」兩條件並立 ——
  Loop 散佈 0.5 但無序→正確判非波(0h 只在手搭 fixture 驗過,此在真實產線再現)。cap `cascade_priors_integration`
  L2;anim-forge 仍 HOLD。見 `knowledge/s1-cascade-priors-integration.md`。
- 2026-09-06:**S1 combo/charge 接進 genre 先驗庫(里程碑,candidate H)** — 續 (E),把 0g 的 combo(連擊)/
  charge(蓄力充能)節拍併入 `genre_priors.slot_bigwin`(additive),`build_spine --animate --genre slot_bigwin`
  直出 combo/charge(接 H 前產線從未觸發 0g 模板 —— 「模板就緒 ≠ 生成器接上」再現)。beat key 經 `beat_category`
  路由到 `gen_combo`/`gen_anticipate_hold`;Award 真值僅 In/Loop/Out → combo/charge 列 prior_beats_unused、覆蓋率仍 1.0。
  整合閘 `validate_priors_combo_charge.py`(從先驗庫經 build_storyboard→build_animations)**5 AC 全 PASS**(H1 路由+真峰
  1.347≥1.12 / H2 首尾 identity / H3 combo 遞增峰 [1.207,1.28,1.347]・charge holdfrac 0.456,兩簽章互斥 / H4 覆蓋率 1.0 /
  H5 負對照)。**關鍵:閘找出真實漏洞** —— H5 抓到 reveal 被誤判為 charge(峰前皆長 <0.97),加 squash-floor(峰前最低
  >0.5:charge squash ~0.85 vs reveal collapse ~0.02,windup 是壓縮不是消失)強化 `has_charge_signature`;(E) 閘負對照
  加 `ALL_MAIN_SHOW_CATS`(combo/charge/cascade 共享 anticipation+settle 簽章)。回歸:validate_priors/priors_beats/
  more_beats/beat_templates/cascade/anim(+selftest)/round-trip/pivot-rotate/scale-pivot 全綠。cap
  `combo_charge_priors_integration` L2;anim-forge 仍 HOLD。見 `knowledge/s1-combo-charge-priors-integration.md`。
- 2026-09-05(session 002):**S1 件繞關節 pivot 縮放(里程碑,candidate 0i 延伸 G-3)** — 把 0i「繞 pivot 轉」
  推廣到「繞 pivot 縮放」。In/Out/pulse 的 `scale` 非 rig 下繞件中心脹縮(手臂該從肩伸長)。**一條公式統一**:
  `Δ=(M−I)(O−P)`,M=R·S(0i 是 S=I 特例)。純均勻 scale 約 pivot 為相似變換 `|w−P|=s|x−P|`(取代 0i 剛性判準)。
  `pivot_rotation.py` 延伸(`pivot_delta_full`/`pivot_channels_srt`/`apply_pivots(include_scale=)`,0i 路徑不變)+
  `build_spine --scale-pivot`。`validate_scale_pivot.py` **7 AC 全 PASS**(AC1 0.0001px / AC2 負對照 70.5px=0.6×117 /
  AC5 相似 0.0001px / AC6 rotate+scale 併 0.037px 證 M=R·S / AC7 端到端 pulse)。回歸 0i/validate_anim(+selftest)/
  round-trip 全綠。發現:0i 與 G-3 是同一仿射補償的兩分量、相似≠等距、非線性 scale 亦須 densify。
  cap `scale_pivot_keyframe` L2;anim-forge 仍 HOLD。見 `knowledge/s1-scale-pivot-keyframe.md`。
- 2026-09-05:**S1 件繞關節 pivot 轉 keyframe(里程碑,candidate 0i)** — 補建議 (G):把 S5 接觸縫 pivot 接進
  S1 keyframe。第一個把 **S5 rig 幾何 → S1 keyframe** 接起來的能力。非 rig 下 bone 落件中心 O,原 rotate 讓件繞 O 轉
  (對肢體不物理);`pivot_rotation.py` 加補償 translate Δ(θ)=(R(θ)−I)(O−P) → 淨效果繞 pivot P 轉,**不動骨架結構**
  (與 --rig 搬骨互補)。`build_spine --animate --pivot-rotate` 復用 rig_layout 樹+接觸縫。踩雷:**Δ 對 θ 非線性 →
  rotate 加密重取樣(dt=1/60)**才不幀間漏。`validate_pivot_rotation.py` 對真實 Award 左手+推得肩 pivot **7AC 全 PASS**
  (AC1 不動點 0.01px / AC2 負對照繞件中心 48.8px / AC3 件最遠點 94px / AC4 θ=0 Δ=0 identity / AC5 剛性 0.01px /
  AC6 端到端經 build_animations 無縫+pivot 不動+內建負對照 9.75px / AC7 bezier 緩動)。回歸 validate_anim(+selftest)、
  round-trip 對 --pivot-rotate build 全 PASS(setup 不變)。發現:「幾何就緒 ≠ 生成器接上」再現;非線性補償必須 densify。
  cap `pivot_rotate_keyframe` L2 併入 spine-anim-forge(仍 HOLD)。見 `knowledge/s1-pivot-rotation-keyframe.md`。
- 2026-09-04(session 002):**S1 cascade 跨件錯開波(里程碑,candidate 0h)** — 補 (F 續) cascade。第一個**跨件時序**
  主秀節拍:0f/0g 皆單件內時序,cascade 每件依件序相位錯開成波,簽章在「各件峰時刻排序+散佈」。`gen_cascade`(pop 波,
  首尾 identity)+ `gen_animations` 架構變更(`_PHASE_AWARE`,build_animations 配 `phase=pi/(nvalid-1)` —— 生成器**第一個
  per-part 參數**)+ `validate_cascade.py` **6 AC + 7 條負對照全 PASS**(峰時刻依件序嚴格遞增散佈 0.542;負對照 combo 同時序
  spread≈0、打亂/反序非遞增、單件非 combo 簽章=與 0g 正交)。關鍵:簽章要端到端量;cascade 逼出 build_animations 的 phase
  threading(「模板就緒≠生成器接上」新形式)。回歸 0f/0g/(E)/anim(+selftest)全 PASS。cap `cross_part_cascade` L2;anim-forge 仍 HOLD。
  見 `knowledge/s1-cascade-beat.md`。
- 2026-09-04:**S1 擴充主秀 beat 庫(里程碑,candidate 0g)** — 補建議 (F) 更多主秀節拍。加 `gen_combo`(連擊,
  遞增 impact 峰數 ≥3)+ `gen_anticipate_hold`(蓄力充能,峰前長蓄力佔比 ≥0.35),各有**互不相同、可量化**的
  結構簽章,wire 進 `gen_animations`(combo/charge 類別)。`validate_more_beats.py` **6 AC + 9 條負對照全 PASS**
  (兩簽章互斥、單發 hit/對稱脈衝皆非 combo/charge、等峰 combo 非遞增)。關鍵:combo 鑑別子是「遞增」非只「多峰」、
  charge 用「時間佔比」非「深度」(解耦峰值/取樣);impact 門檻 1.10 為乾淨切點。回歸 0f/0d/0e/(E) 全 PASS。
  新增 cap `beat_library_expansion` L2;anim-forge 仍 HOLD。見 `knowledge/s1-more-beats.md`。
- 2026-09-04:**S1 (E) 主秀 beat 接進 genre 先驗庫(里程碑)** — 把 0f hit/reveal 併入 `genre_priors`,`build_spine
  --animate` 直出主秀。診斷 slot_bigwin 完全沒觸發 0f(只 In/Loop/Out)→ additive 補 burst(reveal)+hit beat;
  slot_reveal 因命名含 open/hit 已自動受惠。coverage 單調非遞減仍 1.0(Award 無 hit/burst token→列 unused,誠實 PROPOSAL)。
  整合閘 `validate_priors_beats.py`(從先驗庫經 build_storyboard→build_animations,補 0f 只驗合成模板缺口)5 AC 全 PASS
  (主秀真峰≥1.12/介面契約/結構簽章/覆蓋率保留/負對照 character_idle 0 clip)。回歸 validate_priors/anim/beat_templates/deform 全 PASS。
  發現:模板就緒 ≠ 產線會用它(需先驗庫有對應 beat 才觸發)。cap `main_show_priors_integration` L2;anim-forge 仍 HOLD。
  見 `knowledge/s1-main-show-priors-integration.md`。
- 2026-09-01(session 002):**S1 big-win 主秀 beat 模板(里程碑,candidate 0f)** — 補 0d 主秀節拍只有對稱脈衝的缺口,
  加 anticipation(反向預備)+ settle(阻尼回擺)兩動畫原理。`beat_templates.py`(gen_hit 首尾 identity、gen_reveal 首 collapsed
  尾 identity)wire 進 gen_animations(hit/reveal 新類別)+ `validate_beat_templates.py` 6AC 全 PASS(對真實 robot 5 拆件端到端)+
  負對照(對稱脈衝 gen_pulse 判為非主秀)。關鍵:`(scale-1)` 符號變化數分辨主秀 hit(≥3)vs 天真脈衝(0 負偏移)。真值=結構
  簽章非美感。回歸 0d/0e/Symbol_Ww 全 PASS。新增 cap `storyboard_beat_templates` L2;anim-forge 仍 HOLD。見 `knowledge/s1-beat-templates.md`。
- 2026-08-31(session 003):**S5 (d') 多跳 weighted 肢體鏈端到端驗收(里程碑)** — 補 combo 唯一 honest-boundary
  缺口(「weighted mesh 當鏈中段肢體」在 robot_parts 無樣本)。合成鏈 fixture `make_limb_chain_psd.py`
  (body→arm→forearm→hand,arm/forearm 皆 weighted mesh)+ `validate_rig_weighted_chain.py` 5AC 全 PASS:
  鏈深 4 非星形 / setup 0.00px / **遞迴帶動**(轉 b_body→forearm 隔一跳隨動 80px、轉 b_arm→forearm 動 body 不動、
  weighted-only 全脫鉤 0px 雙軌負對照)/ region 葉件隨鏈 / 逐幀 si=0。結論:併用機制**深度無關**,非新演算法是覆蓋率。
  新增 cap `rig_weighted_chain` L2;區塊仍 HOLD(多 rig 真值缺口不變)。見 `knowledge/s5-rig-weighted-chain.md`。
- 2026-08-31(session 002):**S5 (d) `--rig`×`--weighted` 併用(里程碑)** — 移除兩旗標互斥;weighted mesh
  控制骨改掛該件關節骨 `b_{nm}`(座標轉相對局部),件同時可關節articulate + 局部 weighted 變形。純座標問題:
  setup 下父鏈純平移 → bind 偏移不變 → setup 逐頂點 **0.00px** 不位移。`validate_rig_weighted_build.py` 對
  robot_parts 4 AC 全 PASS(結構/setup 不動/自articulate 72·53px + 鏈帶動 73.9px vs weighted-only **脫鉤 0px**/
  關節旋轉逐幀 si=0)。內建負對照=weighted-only 位移=0(鑑別力)。回歸:validate_rig_build(rig-only)、
  validate_weighted_build(weighted-only)皆仍 PASS。新增 cap `rig_weighted_combo` L2;區塊仍 HOLD(多 rig 真值缺口)。
  見 `knowledge/s5-rig-weighted-combo.md`。
- 2026-08-31:**S5 肢體父子樹自動推斷(里程碑)** — 補上 rig pipeline 最後一個先驗環節:`infer_tree.py`
  由拆件相鄰幾何自動推父子樹(area-primary root + 接觸距離 Dijkstra 樹,支援多跳鏈),取代 `rig_layout` 星形先驗。
  `validate_tree.py` 對 Award 真值樹 AC1–4 + 3 負對照全 PASS,合成鏈驗多跳通用;接進後 `validate_rig_build` 4AC 回歸 PASS。
  發現 root 須 area-primary(純鏈中間件 degree 最高卻非 root;重疊 composite 下 degree 飽和)。新增 cap `limb_tree_infer` L2 GREEN;
  `spine-rig-pivot` 仍 HOLD(L3 缺口=多 rig 真值,屬使用者資源)。見 `knowledge/s5-limb-tree-inference.md`。
- 2026-08-30:**S5 pivot→bone 父子樹寫入 build_spine(里程碑)** — `build_spine --rig` 產帶真正關節鏈的可載入
  Spine(結構子件掛 body、關節落接觸縫、attachment delta 位移保 setup pose);`validate_rig_build.py` 4 AC 全 PASS
  (setup 不位移 0.00px、pivot 往返 0.04px、關節語意 rig vs 非rig 縫撕裂 2.1–3.2×↓)。`pivot_end2end` L0→L2 GREEN。
  發現 **Award 僅機器人一件可拆肢體 rig**(OMG/SUP/MEG 為單圖+特效)→ 多 rig 真值屬使用者資源,區塊維持 HOLD(防固化)。
- 2026-08-28:**跨分支成果乾淨合流 + 分支釘定(使用者決策 B)** — 發現 200+ 條 `claude/*` 是平行且重複的研究線
  (routine 每 run 從同 default clone、重做同一 chunk、push 到隨機新分支,從不合流)。以最完整線 `3r9ey4`
  (weighted 生成+評估+skill 機制)為底,擇優併入 S1 keyframe(zjze4k 版,5 選 1)、S4 交接、分支釘定,去重評估器。
  合流後單一 tree 全綠(keyframe 4AC+負對照 PASS、check_readiness 3 區塊 READY)。定為 canonical `claude/spine-main`。
  見 `log/2026-08-28-004.md`。**使用者待辦**:把 repo default 改 `claude/spine-main`、更新主 Routine Prompt、清舊分支。
- 2026-08-28:**S4 交獨立排程 + 分支策略定案** — S4(切圖+補圖)拆給 `claude/spine-s4-inpainting` 排程;
  主排程釘 `claude/spine-main`(見 `log/2026-08-28-002/003.md`)。
- 2026-08-27:**S1 keyframe(candidate 0d)+ S3 weighted 生成器/端到端 + skill 化機制**(多平行 run,已於 08-28 合流)。
- 2026-06-24：建立自驅研究框架骨架(RULES/PLAN/STATE/knowledge/log/prompts)。
- 2026-06-24：匯入「Spine mesh system analysis」完整交接;PLAN/RULES/STATE 依實際研究內容填妥,狀態轉 `ACTIVE`。
- 2026-06-24：**S3 第一輪** — 探測並安裝 CPU 套件;完成 mesh 生成器 + 評估器 + 合成測試;6 條 AC 全過(IoU 0.99)。
- 2026-06-24:收到真實 `main_draw.json` + `.atlas`(存入 `assets/`);解析確認 4 mesh + 9 anim deform;
  下一課題定為 deform-aware 評估器(純 CPU,不需 PNG)。
- 2026-06-24:**deform 評估器課題完成** — Python 重現 Spine deform;真實 4mesh×9anim benchmark 全乾淨
  (_checker_validated);負對照可抓自交/翻面;生成 mesh 耐變形 ≈ 藝術家手做(撐過 315px)。
- 2026-06-24:**真實資產驗證(里程碑)** — 收到 main_draw.png;atlas_crop 切真實貼圖;生成 mesh 靜態 IoU 0.98 過
  但耐變形失敗 → 發現「靜態≠變形穩健」,藝術家直條拓樸更耐變形。下一步定為 S3 v2 deform-aware 生成器。
- 2026-06-24:**S3 驗證 + 自我更正** — 真實位移場轉移評估器(自一致性驗證);推翻先前『耐變形失敗』
  (合成壓力 miscalibration);更正後 v1 對 curtain_left 整合 AC 通過(IoU 0.98、真實變形乾淨)。
- 2026-06-24:**排程就緒(B)** — 建 SessionStart hook(.claude/,自動裝 CPU 套件+PYTHONPATH,已驗證)、
  硬化 prompts/run.md、寫 SCHEDULE.md turnkey 指南。剩使用者在 web 建每日 trigger。
- 2026-06-26:**S3 推廣到全部 4 mesh(里程碑)** — v1 不通用(curtain_right/shadow 真實 deform 自交);
  v2 strip 通用(4 mesh 全乾淨)。發現 IoU 由 rows 決定、cols 不影響;v2 預設 rows 8→10,4 mesh 全 overall_pass。
  評估器先以藝術家真值自一致性(4 mesh si=0)確認可信再下判定。開 PR #1(zealous→hopeful default,a 方案)。
- 2026-06-26:**S2 切圖閘完成** — `evaluate_slicing.py` 端到端重組驗證;main_draw 45/45 region MAE=0/0孤兒/0重疊;
  雙向負對照確認鑑別力(rotate 對稱 region 不可區分為已知局限)。發現 spine_inspector round-trip 被 CDN 政策擋(blocker)。
- 2026-06-26:**S4 PSD 契約 pipeline 打通(使用者拍板)** — psd-tools 可裝;`make_test_psd.py`(合成 fixture)+
  `psd_slice.py`(PSD→各部位件+manifest+自驗閘);4 層 PSD 重組 MAE=0.01/0孤兒,漏層負對照抓到。
  寫 `knowledge/s4-psd-contract.md`(給美術的交檔規範)。待真實 PSD 驗收。
- 2026-06-26:**分支策略定案** — 排程 trigger 改**直接指向開發分支 `claude/zealous-noether-y2ecwu`**,
  不再走 PR/merge(零摩擦)。更新 `prompts/run.md`(分支說明 + 移除過時快照,改以 STATE 為準)、`SCHEDULE.md`。
  PR #1 已 merge;PR #2 關閉(改用分支直讀)。
- 2026-08-19:**S1 端到端「目標圖→可載入 Spine 素材」(里程碑)** — `build_spine.py`+`validate_build.py`;
  robot/Symbol_Ww round-trip 重建 == 原圖 全 PASS。規格→素材打通。下一步定為分鏡→動畫 keyframe。
- 2026-08-19:**S1 擴充:平圖流程 + 分鏡先驗庫(使用者指定)** — (A) 平圖純 CPU 拆件 baseline + 真值召回閘
  (同材質角色 0/5、0/18 語意召回,僅不相連塊可靠 → 佐證 PSD-first);(B) 先驗庫 slot_bigwin/slot_reveal
  對 Award/main_draw 覆蓋率 1.0。修 2 評估器 bug(decomposability 反向、動畫名子字串誤判)。
- 2026-08-19:**S1 目標圖反推分析器(里程碑,使用者新增研究項目)** — 分層 PSD → 五段規格
  (運動構件/周邊特效/動作分鏡/拆圖策略/補圖項目);`tools/analyzer/` + 對 Award 真值 5 項校驗全 PASS
  (件召回 1.0)。誠實界定補圖需求為輸入契約相依(分層 PSD 0 破洞)、#3 分鏡為類型先驗提案。
- 2026-08-19:**S3 端到端對真實美術 mesh 驗收(里程碑)** — `compare_robot_mesh.py`:Award 機器人
  3 mesh 件靜態覆蓋率全 PASS(頂點更省 37~48 vs 78~98)。校正 STATE 舊假設:**mesh uvs 是 region-local**
  (非 atlas 分數,4 組合實測 vflip=False)。新增軟邊 blob `boundary-dense-v1` 模式(光暈 0.92→0.98)+
  通用 `prune_orphans`(修 filter 造孤兒)。4 curtain/shadow strip 迴歸全 PASS。誠實限制:weighted 骨骼
  變形平滑度未驗 → 下一步定為 S3 weighted+BBW。見 `knowledge/s3-robot-mesh-vs-award.md`。
- 2026-06-26:**S4 真實驗收(里程碑)** — 使用者提供 2 份生產 PSD + 機器人對應 spine(Award)。
  psd_slice 對兩檔切圖無損 PASS;機器人 5 圖層 ⇄ Award slot `機器人拆件/<圖層名>` 逐件吻合(+2px)。
  抓修閘第三次 miscalibration(composite 透明區白底 → 改 premultiplied 比對 + 套圖層 opacity)。
  收 Award.json/atlas + 2 PSD 進 assets;校準契約。
- 2026-06-26:**texture 級驗證 + atlas_crop 修正(里程碑)** — 收到 Award.png/Award2.png(雙頁,~0.70 縮小)。
  PSD 切件 ↔ atlas 切件 alpha-IoU 0.92~0.99 → 確認同素材,PSD↔spine↔atlas 閉環。
  **用 PSD 外部真值揪出 atlas_crop derotate 方向 bug(CCW→CW),被 round-trip 自洽掩蓋**;
  升級 atlas_crop 多頁 + 修方向 + 修 evaluate_slicing.repack;main_draw 4 mesh + slicing 重驗全過(rotate=false 不受影響)。
