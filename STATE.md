# 進度狀態 (STATE) — 續跑核心

> 每次 session 結束前**必須**更新此檔。

## 專案狀態

`ACTIVE`  <!-- SETUP / ACTIVE / BLOCKED / DONE -->

## 目前階段

**專案三階段：第 2 階段(用工具鍛鍊四能力)。**
- 第 1 階段(可視化工具)已完成 → `spine_inspector.html`(含 `window.spineTool` API)。
- **S6 軌跡分析／曲線編輯工具鏈(里程碑,2026-09-09,使用者指定新項目)** — 使用者要求:做一個
  **軌跡調整工具(HTML)**,減少 spine-motion-skill 調次級動態時「產圖 → 提修正 → 再產圖」的來回。
  五項需求全部落地:①分析特定目標的運動軌跡 ②網頁圖表 ③圖表上可編輯曲線(位移量/時間/加刪點)
  ④輸出 `motion spec` 供 skill 辨識 ⑤(進階,實驗)從 viewer 直接編輯。
  產出:`spine_trajectory_editor.html`(**單檔零外部相依** —— CDN 被本環境政策擋 403,所以取樣、
  bezier、繪圖、互動全自己實作)+ `tools/motion/`(`spine_world.py` 世界座標取樣器 /
  `analyze_trajectory.py` 分析 CLI / `motion_spec.py` spec 數學 / `apply_motion_spec.py` 套回 CLI /
  `verify_motion.py` V1–V7+Q1–Q3 閘 / `validate_motion_tools.py` A1–A8 自我驗收 / `js_core_probe.js`
  parity 探針 / `bridge_harness.html` 橋接夾具 / `shot_editor.py` 無頭截圖);`spine_inspector.html`
  加 `getBoneTrajectory()` / `openTrajectoryEditor()` / `spine-motion/preview` 即時預覽橋接。
  **三個必記技術結論**:(1) `own = actual − rigid` 不夠 —— 要拆 `actual = rigid + rotOwn + transOwn`
  (Spine bone local 是 T·R·S,translate 造成的世界位移與 rotate 無關,故三者精確可加,殘差 <1e-13),
  **只有 `transOwn` 能無損寫回 translate 關鍵值**;第一版拿總量回寫,round-trip 後 X 幅度 0.071→0.142px
  (剛好兩倍,rotate 貢獻被重複計入)—— 只有 round-trip AC 抓得到。(2) 追蹤點**預設不能用骨骼原點**:
  rotate-only 配件(bell)原點在自轉下完全不動,自身位移會被誤讀成 0;改取該骨骼 slot 的 attachment 中心。
  (3) 迴圈邊界 de Casteljau 切分,且**延後前要先移除 loop 尾端的重複 key**(慣例上 frame=總長 的 key 是
  frame=0 的複製,取模後撞幀、去重會留下錯曲線);修好後「延後 L 幀 == 原曲線循環平移 L 幀」誤差 7e-13。
  **`validate_motion_tools.py` A1–A8 對兩個真實資產全 PASS**(`main_draw`/`face`/`main`、
  `Award`/`4_LEG5`/`4_LEG3`):A1 三分解 1.1e-13px、A2 無損 round-trip(local 關鍵值誤差 **0**)、
  A3 延後 5 幀 0.118px / 0.0001px、A4 幅度 ×1.15 比值 1.1500、A5 負對照 4/4(V2 多動骨骼、V4 原動畫被改、
  V5 skins 被動、V7 key 超長)、A6 JS↔Python parity(世界座標 0、spec 數學 8.9e-16)、
  **A7 無頭瀏覽器端到端:頁面預測 vs 實測世界軌跡 0.113px / 0.00014px**(這條成立,來回試錯才真省下)、
  A8 viewer 橋接契約 0.114px。**負對照逼出兩個真 bug**:V7「key 時間 ≤ 總長」原以**新**動畫總長為準 →
  新加的長 key 自己撐大總長、檢查恆真(這正是 skill 列為退件原因的「動畫被撐長、主體末尾凍結」),
  改以**原**總長為準;JS 曲線求值原本重用對齊 runtime 的 `bezierY`(1e-7 提早跳出)與 Python 純二分差 1e-6,
  parity 閘抓到後統一演算法 → 8.9e-16。順手修 `tools/analyzer/spine_anim._interp` 兩個真實檔相容性
  (第一個 key 省略 `time`、curve 省略 `c2/c3/c4` → 缺省 0/1/1),readiness 全區塊回歸不變。
  **honest boundary**:(a) 進階功能⑤「從 viewer 直接編輯」只驗到 **postMessage 契約**(A8) ——
  `spine_inspector.html` 依賴 spine-webgl CDN,本環境 403,畫面真的動起來要在**使用者端**確認;
  (b) 世界↔local **內插固有殘差** 0.12px(關鍵值換算精確,幀間 Spine 在 local 內插、編輯器在世界內插;
  父體有 scale 動畫時才顯著,Award 無縮放為 1e-4)—— 要更緊就加密關鍵幀;(c) 只動 translate(可選 rotate),
  mesh/權重/deform/attachment 不碰;(d) 目標 translate 只有 1 個 key = 靜態擺位,無曲線可調(分析器警告、
  旋鈕 AC 自動 skip);(e) transform 繼承只精確支援 normal/onlyTranslation。
  見 `knowledge/s6-trajectory-editing-tool.md`、`tools/motion/README.md`、
  `tools/motion/skill_snippet.md`(可貼進 spine-motion-skill 的章節)、圖 `knowledge/figures/s6-trajectory-editor.png`。
  ⚠ 本次工作在分支 `claude/spine-motion-trajectory-tool-5xq97r`(排程指定),非 `claude/spine-main`。
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

**S6 續作候選(使用者若要繼續軌跡工具)**:
- (S6-a) **viewer 即時預覽在使用者端實測**(唯一未驗的一段:CDN 在本環境 403)。使用者端跑
  `python3 -m http.server` 開 `spine_inspector.html` → `spineTool.openTrajectoryEditor({bone:..., body:...})`
  → 編輯器按「送預覽到 viewer」→ 確認畫面即時更新;順便用 `spineTool.getBoneTrajectory()`(官方 runtime)
  與編輯器的純 JS 取樣器**交叉驗證**世界座標(目前只有 JS↔Python 兩邊互驗,都不是官方 runtime)。
- (S6-b) **rotate 通道進編輯器**(spec 已預留 `rotate.keys`,套用器已支援,但 UI 只編 translate)。
- (S6-c) **多目標同時編輯**(胸部 + 陰影 + 衣物的相位互補一起看)。
- (S6-d) 把 `tools/motion/skill_snippet.md` 併進使用者的 spine-motion-skill(C 類:需使用者拍板)。

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
> **建議下一個 bounded chunk(擇一,皆純自主):**
> **(G-1) `--rig`×`--pivot-rotate`/`--scale-pivot`/`--shear-pivot` per-bone 語意去重**;**(G-2) 主秀 beat 下 limb 繞關節 AC**;
> **(G-4'') wobble 接 tier 幅度差異化(shear 峰隨檔位遞增)**;**(J-3) cascade 波速/散佈/件數隨檔位**。S5→L3 仍待 **(D) 多 rig 真值**(C/資源類,使用者提供)。

## 環境前置(已驗證可用)

- 排程容器為臨時,CPU 套件需每次重裝。**已確認可裝**:numpy 2.4.6 / opencv-python-headless 4.13.0 /
  triangle / scipy 1.17.1(見 `requirements.txt`)。
- 每次排程執行前先 `pip install -r requirements.txt`。

## 未解問題 / 阻塞 (open questions / blockers)

- ❓ 排程頻率未定(使用者尚未決定)。
- ✅ `main_draw.png`(2023×1896,含 alpha)已收進 `assets/`;texture/IoU 已解鎖。atlas 切圖工具見 `tools/mesh_gen/atlas_crop.py`。
- ❓ 切圖/補圖(S4)最大槓桿是「能否要到分層 PSD」— 屬使用者層級決策。
- ℹ️ spine_inspector 實機 round-trip 需瀏覽器自動化(headless),尚未設置。

## 進度摘要 (progress log)

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
