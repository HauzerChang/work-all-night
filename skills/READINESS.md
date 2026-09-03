# skill 化完成度快照 (READINESS)

> 由 `python3 tools/check_readiness.py` 產出。真相以指令即時輸出為準;本檔為人讀快照,里程碑時更新。
> 產生於 2026-09-03 run 001(S1 candidate 0g 主秀 beat 併入 genre 先驗庫:先驗 beat 加顯式 cat + slot_bigwin Burst payoff,讓 `build_spine --animate` 端到端輸出主秀節拍。`spine-anim-forge` 新增 cap `mainshow_wiring` L2 → 區塊仍 HOLD;連帶把 `validate_analyzer_award ④` 分鏡結構由 exact-equal 放寬為 subset(重現 Award 全節拍 + 透明列額外模板節拍,鑑別力保留)。3 區塊仍 READY 不變)。
> (前次 run 0f:big-win 主秀 beat 模板;0e:mesh deform timeline 生成,新增區塊 `spine-anim-forge`。)

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
  區塊成熟度 L3 → READY ✅
  目標:新 skill《spine-asset-forge》(補 spine-ai-editor 明說『mesh 交給 editor』的空白)
    [L2] 反推分析:分層 PSD → 五段規格                     閘:GREEN (gen)
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
    [L2] 分層 PSD → 規格(件/特效/分鏡/拆圖/補圖)             閘:GREEN (gen)
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
    [L2] 主秀 beat 併入 genre 先驗庫(顯式 cat 分派 + slot_bigwin Burst payoff,0g) 閘:GREEN (pipeline)  «補 0f 只在手搭 storyboard 驗過的缺口:讓 build_spine --animate 走 genre 先驗庫時真的輸出主秀節拍。先驗 beat 加顯式 cat(取代脆弱 beat 名關鍵字:'burst'∈reveal 關鍵字);slot_bigwin 加 Burst(cat=hit,首尾 identity,接 In 後)payoff、slot_reveal open/hit 顯式標。6AC(bigwin payoff 端到端具 hit 簽章/reveal open+hit 主秀/cat 真驅分派勝關鍵字/串接介面/一般節拍不具主秀簽章+stripped 無主秀 的鑑別/回歸)全 PASS。honest boundary:Award 真值把 payoff 收在 In 一支內,Burst 為可復用模板提案(validate_priors 標 prior_beats_unused、覆蓋率不變)»

==============================================================================
可 skill 化(達門檻): spine-mesh-doctor, spine-asset-forge, spine-weighted-forge
HOLD(防固化半成品): spine-slicing, spine-target-analysis, spine-rig-pivot, spine-anim-forge
```
