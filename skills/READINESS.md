# skill 化完成度快照 (READINESS)

> 由 `python3 tools/check_readiness.py` 產出。真相以指令即時輸出為準;本檔為人讀快照,里程碑時更新。
> 產生於 2026-09-06 run session 003(S1 candidate (J):檔位主秀幅度差異化 —— `slot_bigwin` 宣告 tiers[Super,Mega,Omg,Legend] 卻一直只是 metadata(build_animations 對所有檔位產同幅度主秀);把檔位 gain 政策(`genre_priors.tier_gains`,單調遞增)乘在主秀 overshoot 上(`beat_templates._tier_peak`,對 identity 恆回 1.0),經 `build_animations(tiers=True)` 展開 `<Tier>_<beat>`(`build_spine --animate --tiers`),幅度隨檔位單調遞增而端點介面與 back-compat 不受影響。`spine-anim-forge` 新增 cap `tier_amplitude_differentiation` L2(pipeline)→ 區塊仍 HOLD;運動基元先驗、單一真值資產,防固化。`validate_priors_tiers.py` 5AC 全 PASS;關鍵=端點恆等不變式讓放大與介面正交(同 0i/G-3 手法),T5 用等 gain 證判準可被證偽。可 skill 化 2 區塊 spine-mesh-doctor/spine-weighted-forge 不變)。
> (前次:(I) cascade 接進先驗庫 / (H) combo/charge 接進先驗庫 / 0i 件繞關節 pivot 轉 / G-3 pivot 縮放 / 0h cascade 模板 / 0g combo+charge 模板 / 0f big-win beat 模板 / 0e mesh deform。)

```
==============================================================================
skill 化完成度矩陣(已實跑全部 validator)
==============================================================================

■ spine-mesh-doctor — mesh 品質 / 變形評估閘套件
  區塊成熟度 L3 → READY ✅
  目標:新 skill《spine-mesh-doctor》(補 spine-ai-editor 只可視化、無量化 pass/fail 的空白)
    [L2] 靜態輪廓 IoU 閘                             閘:GREEN (eval)
    [L2] unweighted 變形閘(真實位移場)                  閘:GREEN (eval)
    [L2] weighted 骨綁變形閘                         閘:GREEN (eval)  «今日新增;3 robot 真值 + 負對照»
    [L3] 整合 AC(端到端 4 mesh)                      閘:GREEN (pipeline)

■ spine-asset-forge — 目標圖/PSD → 可載入 Spine 素材(靜態)
  區塊成熟度 L3 → HOLD ⛔
  目標:新 skill《spine-asset-forge》(補 spine-ai-editor 明說『mesh 交給 editor』的空白)
    [L2] 反推分析:分層 PSD → 五段規格                     閘:RED   (gen)
    [L2] PSD → 各部位件 + manifest                  閘:GREEN (gen)
    [L2] 件 → mesh 拓樸(strip)                     閘:GREEN (gen)
    [L3] SkelToJson 組裝(端到端 round-trip)          閘:GREEN (pipeline)  «限制:只驗靜態幾何/貼圖,不含 animation/weighted/pivot»

■ spine-slicing — 切圖 / atlas 無損重組閘
  區塊成熟度 L2 → HOLD ⛔
  目標:併入 forge 為子模組(或獨立輕量 skill)
    [L2] PSD 切件保真                               閘:GREEN (gen)
    [L2] atlas 重組保真閘(45/45)                     閘:GREEN (eval)
    [L2] 多頁 atlas 切圖(CW derotate)               閘:—     (gen)  «方向 bug 已修;由 evaluate_slicing 間接覆蓋»

■ spine-target-analysis — 反推分析 / 需求規格(上游)
  區塊成熟度 L2 → HOLD ⛔
  目標:HOLD:折入 forge 前端,或併 spine-ai-editor 的可行性評估
    [L2] 分層 PSD → 規格(件/特效/分鏡/拆圖/補圖)             閘:RED   (gen)
    [L2] 分鏡先驗庫(2 類型已驗/2 未驗)                     閘:GREEN (gen)  «覆蓋率 1.0 但僅 2 類型有真值»
    [L1] 平圖(未分層)自動拆件                            閘:GREEN (gen)  «誠實負結果:同材質語意召回 0,CPU 到頂需 GPU;非能力,是契約依據»
    [L0] 影片 → 規格                                閘:—     (gen)  «repo 無影片資產,未開始»

■ spine-weighted-forge — weighted mesh 生成 + BBW 權重(候選 2 主體)
  區塊成熟度 L3 → READY ✅
  目標:READY:達門檻,可併入 spine-asset-forge(weighted 素材產線)
    [L2] 變形品質閘(前置)                              閘:GREEN (eval)
    [L2] heat-diffusion(BBW 近似)權重生成             閘:GREEN (gen)  «不透明件(身體/左手)過閘 + 平滑度≈藝術家;軟性件(光暈極端 reveal)未追平,屬已知限制»
    [L2] 內部取樣密度控制(triangle max-area)            閘:GREEN (gen)  «body 調到 nv=98 == 藝術家»
    [L3] build_spine --weighted 端到端產可載入 spine   閘:GREEN (pipeline)  «round-trip + 輪廓 IoU + 合成變形閘;結構件 si=0、特效件 additive 容忍»

■ spine-rig-pivot — S5 rig pivot 推斷(關節=父子件接觸縫)
  區塊成熟度 L2 → HOLD ⛔
  目標:HOLD:接 build_spine 骨樹已完成(L2);達 L3 尚缺『多 rig 真值』(Award 僅 1 個可拆肢體 rig,屬資源類),補齊後併入 forge 或開新 skill
    [L2] pivot 推斷閘(真值+負對照)                      閘:GREEN (eval)  «Award 機器人 rig 3 關節藝術家真值 + 隨機/互換/rect 三負對照,皆有鑑別力»
    [L2] 接觸縫 pivot 推斷器                          閘:GREEN (gen)  «3 關節 err 2–5% 軀幹尺度、勝質心 baseline;僅驗『關節在接觸縫』子問題,軸向精修屬美術(A類)»
    [L2] 肢體父子樹自動推斷(root+parent 邊)               閘:GREEN (gen)  «area-primary root + 接觸距離 Dijkstra 樹;對 Award 機器人真值樹 AC1-4 + 3 負對照全 PASS,合成鏈驗多跳通用;取代 rig_layout 的星形先驗(rig 拓樸現完全自決)。honest boundary:effect/structural 角色分類仍為輸入(NC3)»
    [L2] pivot→bone 父子樹寫入 build_spine(--rig)    閘:GREEN (pipeline)  «build_spine --rig 端到端產關節鏈(父子樹改由 infer_tree 幾何推斷,非星形先驗)+ validate_rig_build 4AC(結構/setup不位移/pivot往返/關節語意 vs 非rig對照)PASS;仍 L2 非 L3:僅單一 robot rig 驗過(Award 僅此件可拆肢體;OMG/SUP/MEG 為單圖+特效,無接觸縫)→ 多 rig 真值屬使用者資源»
    [L2] --rig × --weighted 併用(weighted 控制骨接進關節鏈) 閘:GREEN (pipeline)  «移除 --rig/--weighted 互斥;weighted mesh 控制骨改掛該件關節骨 b_{nm}(座標轉局部)→ 4AC PASS (結構/ setup 逐頂點 0.00px / 自articulate+鏈帶動 vs weighted-only 脫鉤(0px)/ 關節旋轉逐幀 si=0)。仍 L2:同 pivot_end2end,僅單一 robot rig 驗過(多 rig 真值屬使用者資源)»
    [L2] 多跳 weighted 肢體鏈(weighted mesh 當鏈中段)    閘:GREEN (pipeline)  «補 robot_parts 無『weighted mesh 當鏈中段肢體』樣本的缺口:合成鏈 fixture (make_limb_chain_psd:body→arm→forearm→hand,arm/forearm 皆 weighted mesh)。5AC PASS:鏈深 4≥3 非星形 / setup 0.00px / 遞迴帶動(轉 b_body→forearm 隔一跳仍隨動 80px、轉 b_arm→forearm 動 body 不動、weighted-only 全脫鉤 0px)/ region 葉件隨鏈 / 逐幀 si=0。演算法早已支援(接觸縫遞迴+控制骨掛關節骨),本閘證端到端成立。honest boundary:合成 fixture 非藝術家真值»

■ spine-anim-forge — 分鏡 → 會動 Spine timeline(bone/slot + mesh deform)
  區塊成熟度 L2 → HOLD ⛔
  目標:HOLD:讓 build --animate 素材『會動』;運動基元為手感先驗(非學自真值),達 L3 前不打包
    [L2] 分鏡→bone TRS + slot alpha timeline(0d)  閘:GREEN (gen)  «4AC(有限/loop無縫/pose不擾動/beat串接)+ --selftest 負對照全偵測;role→運動基元為先驗手感提案(非學自真值),緩動美感留使用者(A類)»
    [L2] 分鏡→mesh deform timeline(真實律動場轉移,0e)    閘:GREEN (pipeline)  «補 0d 只動 bone/slot 的缺口:軟件/特效 mesh 本身 deform。運動=真實 main_draw 窗簾/陰影 deform 場(deform_eval.real_deform_field)UV 轉移到目標 mesh;beat 包絡首尾回 setup(無縫)。7AC PASS(結構/逐幀乾淨/loop無縫/setup介面/幅度≤真實裕度/負對照 scramble×3 全破+連貫×4不破/build_spine --animate --deform 端到端生成 mesh 逐幀乾淨)。gate=deform_eval(真實位移場,已驗可信)。honest boundary:件role→律動場來源為先驗映射(預設軟布料模板);單一真值資產»
    [L2] big-win 主秀 beat 模板 hit/reveal(anticipation+settle,0f) 閘:GREEN (gen)  «補 0d 只有對稱脈衝的缺口:hit=反向預備→命中→阻尼回擺、reveal=藏→蓄勢→炸開→回穩,皆 setup identity/collapse 介面可與 In/Loop/Out 串接。6AC(well-formed/可串接介面/真峰/anticipation/settle 阻尼回擺/負對照)全 PASS;負對照證閘能分辨主秀 hit 與天真對稱脈衝(gen_pulse 無反向預備+無阻尼回擺→非主秀)、不歸位、無峰。真值=結構簽章(非美感,美感留使用者 A類)»
    [L2] 主秀 beat 接進 genre 先驗庫(E,build --animate 直出主秀) 閘:GREEN (pipeline)  «把 0f 的 hit/reveal 併入 genre_priors:slot_bigwin 加 burst(reveal)+hit beat、slot_reveal 既有 open→reveal/hit→hit。與 validate_beat_templates 差別=本閘從**先驗庫**經 analyze_target.build_storyboard → build_animations,證主秀節拍真的從先驗流到最終 animations(--animate 直出),非只驗合成模板。5AC PASS(P1 主秀 clip 真峰≥1.12/P2 介面契約 reveal collapse→identity・hit identity 首尾/P3 結構簽章 hit_signature+reveal collapse-hold+峰後穿越≥2/P4 已驗先驗覆蓋率仍 1.0 未擾動/P5 負對照 character_idle 產 0 主秀 clip・非主秀 beat 不具簽章)。honest:主秀運動仍先驗手感、burst/hit 於 Award 真值無命名故 validate_priors 列 prior_beats_unused(誠實 PROPOSAL);單一真值資產»
    [L2] 擴充主秀 beat 庫:combo(多峰遞增)+ anticipate_hold(長蓄力,0g) 閘:GREEN (gen)  «續 0f 再加兩個大獎節拍,各有**互不相同**的客觀結構簽章:combo=遞增 impact 峰數≥3(單發 hit 僅 1 峰)、anticipate_hold=峰前長蓄力時間佔比≥0.35(hit 蓄力僅短暫 dip)。皆保 setup identity 介面(可插 Loop 間)。6AC PASS(well-formed/可串接介面/真峰/兩簽章各成立/共用 anticipation+settle/負對照)+9 條負對照全過:兩簽章互斥、單發 hit 與對稱脈衝皆非 combo/charge、等峰 combo 非遞增。真值=結構簽章(美感留使用者 A類)»
    [L2] cascade 跨件錯開波(跨件時序簽章,0h)               閘:GREEN (gen)  «補 0f/0g 全是**單件內**時序簽章的缺口:cascade=每件依件序相位錯開觸發成一道波,簽章在**件之間**(各件峰時刻依件序嚴格遞增 + 散佈 ≥0.30),必須端到端經 build_animations 量測(證 per-part phase threading 有接上)。pop 波形首尾 identity 可插 Loop 間。6AC PASS(well-formed/可串接介面/真峰/跨件簽章/共用 anticipation+settle/負對照)+ 7 條負對照:combo(同時序)spread≈0 非波、打亂/反序件序非遞增、cascade 單件非 combo 簽章(證與 0g 正交)、單件無 spread 非波。真值=結構簽章(美感留使用者 A類)»
    [L2] 件繞關節 pivot 轉(keyframe 級,把 S5 接觸縫 pivot 接進 keyframe,0i) 閘:GREEN (pipeline)  «把 S5 的接觸縫 pivot 餵進 S1 keyframe 生成器:件繞**關節 pivot** 轉而非件中心。非 rig 下 bone 落件中心 O,原 rotate 讓件繞 O 轉(對肢體不物理);本能力在 rotate 外加補償 translate Δ(θ)=(R(θ)−I)(O−P),淨效果=繞 pivot P 轉,**完全不動骨架結構**(與 --rig 搬骨的結構性解法互補)。Δ 對 θ 非線性 → rotate 通道加密重取樣(dt=1/60)使幀間殘差<<0.1px。build_spine --animate --pivot-rotate 復用 rig_layout 的樹+接觸縫推斷取 pivot。7AC PASS(對真實 Award 左手世界幾何+推得肩 pivot):AC1 pivot 不動點殘差 0.01px、AC2 負對照繞件中心位移 48.8px(>>AC1)、AC3 件最遠點轉 94px、AC4 θ=0 幀 Δ=0(identity 保持)、AC5 剛性等距 0.01px、AC6 端到端經 build_animations 產 loop→apply_pivots 後仍有限/無縫/pivot 不動(內建負對照未套用會動 9.75px)、AC7 bezier 緩動仍成立。回歸:validate_anim(+selftest)、round-trip build 對 --pivot-rotate build 全 PASS(setup pose 不變)。真值=幾何不動點(客觀);繞 pivot 是否貼手感的美術微調留使用者(A類)。honest boundary:單一 rig 真值、與 anim-forge 同 HOLD»
    [L2] 件繞關節 pivot 縮放(0i 延伸 G-3,把旋轉+縮放統一成 M=R·S 補償) 閘:GREEN (pipeline)  «把 0i「繞關節 pivot 轉」推廣到「繞關節 pivot 縮放」:In/Out/pulse 給件的 scale 非 rig 下繞件中心脹縮(手臂該從肩伸長)。一條公式統一——Δ=(M−I)(O−P),M=R(θ)·diag(sx,sy)(Spine TRS);0i 是 S=I 特例、θ=0,s=1 時 Δ=0(identity 保持)。純均勻 scale 約 pivot 是相似變換 ∀x |world(x)−P|=s·|x−P|(取代 0i 剛性 AC 的判準)。pivot_rotation.py 延伸(pivot_delta_full/pivot_channels_srt/apply_pivots(include_scale=),include_scale=False 預設=0i 路徑逐位元不變)+ build_spine --scale-pivot(含 --pivot-rotate 語意)。踩雷同 0i:Δ 對 θ、s 皆非線性 → rotate 與 scale 都密網格重取樣。7AC PASS(對真實 Award 左手+推得肩 pivot |O−P|=117px):AC1 不動點 0.0001px、AC2 負對照繞件中心 70.46px(=0.6×117)、AC3 件最遠點相對變化 0.600、AC4 s=1 端點 Δ=0、AC5 相似 |w−P|=s|x−P| 偏差 0.0001px、AC6 rotate 24°+scale 1.6 併 0.037px(證 M=R·S 組合)、AC7 端到端經 build_animations pulse(limb scale+rotate 無 translate)pivot 不動 0.014px vs 負對照 22.14px。回歸:0i validate_pivot_rotation(逐 AC PASS,路徑不變)、validate_anim(+selftest)、round-trip 對 --scale-pivot build 全綠。honest boundary:pivot 真值仍 S5 接觸縫草案、單一 rig、只非 rig 下套用;縮放幅度手感留使用者(A類)。與 anim-forge 同 HOLD»
    [L2] combo/charge 接進 genre 先驗庫(H,build --animate 直出連擊/蓄力) 閘:GREEN (pipeline)  «續 (E) 對 hit/reveal 所做,把 0g 的 combo(連擊)/charge(蓄力充能)節拍併入 genre_priors:slot_bigwin 加 combo+charge beat(beat key 經 beat_category 路由到 gen_combo/gen_anticipate_hold)。與 validate_more_beats(0g)差別=本閘從**先驗庫**經 analyze_target.build_storyboard → build_animations,證 combo/charge 真的從先驗流到最終 animations(--animate 直出),非只驗合成模板(「模板就緒 ≠ 生成器接上」在 combo/charge 上補上)。5AC PASS(H1 present+routing 路由到 combo/charge 類別且真峰≥1.12/H2 介面契約首尾 identity 可插 Loop 間/H3 結構簽章 combo=遞增 impact 峰≥3・charge=峰前長蓄力≥0.35 且兩簽章互斥/H4 已驗先驗覆蓋率仍 1.0 未擾動(combo/charge 為 prior_beats_unused)/H5 負對照 character_idle 產 0 combo/charge clip・非 combo/charge beat 不具其簽章)。副產:H5 逼出 charge vs reveal 鑑別子——兩者峰前皆長時間 <0.97,加 squash-floor(峰前最低 >0.5,charge 是壓縮蓄力 ~0.85 非 reveal 塌陷 ~0.02)才分得開(強化 has_charge_signature,0g 閘回歸仍 PASS)。honest:主秀運動仍先驗手感、combo/charge 於 Award 真值無命名故 validate_priors 列 prior_beats_unused(誠實 PROPOSAL);單一真值資產。與 anim-forge 同 HOLD»
    [L2] cascade 接進 genre 先驗庫(I,build --animate 直出跨件錯開波) 閘:GREEN (pipeline)  «續 (E)/(H),把 0h 的 cascade(跨件錯開波)併入 genre_priors:slot_bigwin 加 cascade beat(beat key 經 beat_category 路由到 gen_cascade)。cascade 比 (E)/(H) 多驗一層——它是**跨件**時序簽章(同 beat 套每件但依件序相位錯開成波),故本閘證的不只 beat 有流到 animations,還證 _PHASE_AWARE 的件序相位 threading 端到端存活(單件曲線看不出)。從**先驗庫**經 analyze_target.build_storyboard → **真實 build_spine 骨架** → build_animations，對真實 robot 5 拆件 5AC PASS(I1 present+routing 路由到 cascade 類別且每件真峰≥1.12/I2 每件首尾 identity+特效 slot alpha=1 可插 Loop 間/I3 crux 跨件簽章 各件峰時刻依真實件序 [0.158,0.296,0.429,0.567,0.70] 嚴格遞增・散佈 0.542≥0.30・非 combo 簽章/I4 已驗先驗覆蓋率仍 1.0(cascade 為 prior_beats_unused)/I5 負對照 character_idle 產 0 cascade clip・非 cascade beat 不成波)。副產:I5 逼出「跨件簽章需散佈+遞增兩條件並立」——Loop 散佈 0.5 甚至 > 門檻但無序→正確判非波(此鑑別力 0h 只在手搭 fixture 驗過,本次在真實產線再現)。honest:主秀運動仍先驗手感、cascade 於 Award 真值無命名列 prior_beats_unused(誠實 PROPOSAL);單一真值資產。與 anim-forge 同 HOLD»
    [L2] 檔位主秀幅度差異化(J,build --animate --tiers 直出 Super…Legend 遞增) 閘:GREEN (pipeline)  «slot_bigwin 一直宣告 tiers[Super,Mega,Omg,Legend] 卻只是 metadata(build_animations 對所有檔位產同幅度主秀,『檔位』形同虛設)。本能力把檔位 gain 政策(genre_priors.tier_gains,單調遞增)乘在主秀 overshoot(peak−1)上(beat_templates._tier_peak),經 build_animations(tiers=True) 把主秀節拍展開成 <Tier>_<beat>(Super_hit…Legend_hit),幅度隨檔位單調遞增,而端點介面契約與 back-compat 完全不受影響(_tier_peak 對 identity 恆回 1.0)。又一『模板/metadata 就緒 ≠ 生成器接上』的補上。從**先驗庫**經 build_storyboard → **真實 build_spine 骨架** → build_animations(tiers=True) 對真實 robot 5 拆件 5AC PASS(T1 present+routing 4檔×5節拍=20 支 <Tier>_<beat> 路由正確+真峰≥1.12、框架節拍不展開、tiers=False 無檔位前綴/T2 interface 保留 每檔端點逐一==base 端點+base 尾端 setup identity/T3 crux 每節拍每 bone scale 峰值嚴格遞增 Super<Mega<Omg<Legend、Legend/Super overshoot 比=1.6≈gain 比/T4 back-compat Super_<beat> 逐位元==<beat>(tiers=False)+覆蓋率仍 1.0/T5 負對照 slot_reveal(無 tiers)不展開・等 gain 令嚴格遞增失敗(鑑別力)・框架節拍不展開)。關鍵:把新自由度掛在對介面點恆為零的變換上(同 0i/G-3『補償在 identity 時為 0』手法)→ 放大與介面正交。honest:gain STEP 是手感先驗(A類),閘只驗**單調遞增+介面不破**這客觀性質;單一真值資產。與 anim-forge 同 HOLD»

==============================================================================
可 skill 化(達門檻): spine-mesh-doctor, spine-weighted-forge
HOLD(防固化半成品): spine-asset-forge, spine-slicing, spine-target-analysis, spine-rig-pivot, spine-anim-forge
```
