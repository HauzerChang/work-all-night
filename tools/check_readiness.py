#!/usr/bin/env python3
"""skill 化完成度機制 —— 機器可驗的成熟度閘(防止固化半成品)。

哲學延續 RULES「每能力必配評估器」:每個『能力』的成熟度宣告(L0–L4)必須由它的
validator 實跑 PASS 佐證;script 會實跑各 validator 確認 GREEN/RED,再據**skill 化門檻**
判定每個『skill 區塊』能不能打包。

成熟度階梯(maturity ladder):
  L0 概念    —— 只有想法/計畫,無可跑程式。
  L1 原型    —— 工具能跑,但只在合成/自造資料上驗(無真值)。
  L2 真值驗收 —— 對真實生產資產 + 真值通過,且評估器本身經正/負對照確認可信。
  L3 端到端  —— 串成 pipeline,對多個真實標的穩定通過,有一鍵驗證指令。
  L4 skill化 —— 已打包為 skill(SKILL.md/觸發詞/references/回歸測試)。

skill 化門檻(READY_TO_SKILL):
  區塊內**所有核心能力 ≥ L2 且其 validator GREEN**,且**至少一條端到端能力達 L3**。
  只要有任一核心能力 < L2(尤其『生成器』還停在 L0/L1),即 HOLD ——
  **評估器就緒 ≠ 生成能力就緒**(這是防固化半成品的關鍵規則)。

用法:
  python3 tools/check_readiness.py            # 實跑所有 validator(含慢的 weighted,~90s)
  python3 tools/check_readiness.py --quick    # 跳過標 heavy 的 validator(僅讀宣告)
  python3 tools/check_readiness.py --json      # 機讀輸出
"""
import subprocess, sys, os, json, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = dict(os.environ, PYTHONPATH="tools/mesh_gen:tools/analyzer")

# 每個能力:key, 中文名, 宣告成熟度, validator 指令(None=無自動閘), heavy?, 角色(gen/eval/pipeline)
# validator 指令以 shell 執行於 repo 根;exit 0 = GREEN。
CAP = lambda key, name, lvl, cmd, role, heavy=False, note="": dict(
    key=key, name=name, level=lvl, cmd=cmd, role=role, heavy=heavy, note=note)

BLOCKS = [
    {
        "id": "spine-mesh-doctor",
        "title": "mesh 品質 / 變形評估閘套件",
        "target_skill": "新 skill《spine-mesh-doctor》(補 spine-ai-editor 只可視化、無量化 pass/fail 的空白)",
        "caps": [
            CAP("evaluate_mesh", "靜態輪廓 IoU 閘", "L2",
                "python3 tools/mesh_gen/validate_against_real.py --gen v2", "eval"),
            CAP("deform_eval", "unweighted 變形閘(真實位移場)", "L2",
                "python3 tools/mesh_gen/validate_against_real.py --gen v2", "eval"),
            CAP("weighted_deform_eval", "weighted 骨綁變形閘", "L2",
                "python3 tools/mesh_gen/validate_weighted_deform.py", "eval", heavy=True,
                note="今日新增;3 robot 真值 + 負對照"),
            CAP("validate_against_real", "整合 AC(端到端 4 mesh)", "L3",
                "python3 tools/mesh_gen/validate_against_real.py --gen v2", "pipeline"),
        ],
    },
    {
        "id": "spine-asset-forge",
        "title": "目標圖/PSD → 可載入 Spine 素材(靜態)",
        "target_skill": "新 skill《spine-asset-forge》(補 spine-ai-editor 明說『mesh 交給 editor』的空白)",
        "caps": [
            CAP("analyze_target", "反推分析:分層 PSD → 五段規格", "L2",
                "python3 tools/analyzer/validate_analyzer_award.py", "gen"),
            CAP("psd_slice", "PSD → 各部位件 + manifest", "L2",
                "python3 tools/mesh_gen/evaluate_slicing.py", "gen"),
            CAP("generate_mesh_v2", "件 → mesh 拓樸(strip)", "L2",
                "python3 tools/mesh_gen/validate_against_real.py --gen v2", "gen"),
            CAP("build_spine", "SkelToJson 組裝(端到端 round-trip)", "L3",
                "python3 tools/analyzer/build_spine.py assets/robot_parts.psd >/dev/null && "
                "python3 tools/analyzer/validate_build.py assets/robot_parts.psd specs/robot_parts_spine",
                "pipeline", note="限制:只驗靜態幾何/貼圖,不含 animation/weighted/pivot"),
        ],
    },
    {
        "id": "spine-slicing",
        "title": "切圖 / atlas 無損重組閘",
        "target_skill": "併入 forge 為子模組(或獨立輕量 skill)",
        "caps": [
            CAP("psd_slice", "PSD 切件保真", "L2",
                "python3 tools/mesh_gen/evaluate_slicing.py", "gen"),
            CAP("evaluate_slicing", "atlas 重組保真閘(45/45)", "L2",
                "python3 tools/mesh_gen/evaluate_slicing.py", "eval"),
            CAP("atlas_crop", "多頁 atlas 切圖(CW derotate)", "L2", None, "gen",
                note="方向 bug 已修;由 evaluate_slicing 間接覆蓋"),
        ],
    },
    {
        "id": "spine-target-analysis",
        "title": "反推分析 / 需求規格(上游)",
        "target_skill": "HOLD:折入 forge 前端,或併 spine-ai-editor 的可行性評估",
        "caps": [
            CAP("analyze_target", "分層 PSD → 規格(件/特效/分鏡/拆圖/補圖)", "L2",
                "python3 tools/analyzer/validate_analyzer_award.py", "gen"),
            CAP("genre_priors", "分鏡先驗庫(2 類型已驗/2 未驗)", "L2",
                "python3 tools/analyzer/validate_priors.py", "gen",
                note="覆蓋率 1.0 但僅 2 類型有真值"),
            CAP("segment_flat", "平圖(未分層)自動拆件", "L1",
                "python3 tools/analyzer/validate_flat_recall.py", "gen",
                note="誠實負結果:同材質語意召回 0,CPU 到頂需 GPU;非能力,是契約依據"),
            CAP("video_input", "影片 → 規格", "L0", None, "gen",
                note="repo 無影片資產,未開始"),
        ],
    },
    {
        "id": "spine-weighted-forge",
        "title": "weighted mesh 生成 + BBW 權重(候選 2 主體)",
        "target_skill": "READY:達門檻,可併入 spine-asset-forge(weighted 素材產線)",
        "caps": [
            CAP("weighted_deform_eval", "變形品質閘(前置)", "L2",
                "python3 tools/mesh_gen/validate_weighted_deform.py", "eval", heavy=True),
            CAP("bbw_weights", "heat-diffusion(BBW 近似)權重生成", "L2",
                "python3 tools/mesh_gen/validate_weighted_gen.py", "gen", heavy=True,
                note="不透明件(身體/左手)過閘 + 平滑度≈藝術家;軟性件(光暈極端 reveal)未追平,屬已知限制"),
            CAP("interior_sampling", "內部取樣密度控制(triangle max-area)", "L2",
                "python3 tools/mesh_gen/validate_weighted_gen.py", "gen", heavy=True,
                note="body 調到 nv=98 == 藝術家"),
            CAP("weighted_end2end", "build_spine --weighted 端到端產可載入 spine", "L3",
                "python3 tools/analyzer/build_spine.py assets/robot_parts.psd --out specs/robot_weighted_spine --weighted >/dev/null && "
                "python3 tools/analyzer/validate_weighted_build.py specs/robot_weighted_spine",
                "pipeline", heavy=True,
                note="round-trip + 輪廓 IoU + 合成變形閘;結構件 si=0、特效件 additive 容忍"),
        ],
    },
    {
        "id": "spine-rig-pivot",
        "title": "S5 rig pivot 推斷(關節=父子件接觸縫)",
        "target_skill": "HOLD:接 build_spine 骨樹已完成(L2);達 L3 尚缺『多 rig 真值』(Award 僅 1 個可拆肢體 rig,屬資源類),補齊後併入 forge 或開新 skill",
        "caps": [
            CAP("pivot_gate", "pivot 推斷閘(真值+負對照)", "L2",
                "python3 tools/rig/validate_pivots.py", "eval",
                note="Award 機器人 rig 3 關節藝術家真值 + 隨機/互換/rect 三負對照,皆有鑑別力"),
            CAP("contact_seam_infer", "接觸縫 pivot 推斷器", "L2",
                "python3 tools/rig/validate_pivots.py", "gen",
                note="3 關節 err 2–5% 軀幹尺度、勝質心 baseline;僅驗『關節在接觸縫』子問題,軸向精修屬美術(A類)"),
            CAP("limb_tree_infer", "肢體父子樹自動推斷(root+parent 邊)", "L2",
                "python3 tools/rig/validate_tree.py", "gen",
                note="area-primary root + 接觸距離 Dijkstra 樹;對 Award 機器人真值樹 AC1-4 + 3 負對照全 PASS,合成鏈驗多跳通用;"
                     "取代 rig_layout 的星形先驗(rig 拓樸現完全自決)。honest boundary:effect/structural 角色分類仍為輸入(NC3)"),
            CAP("pivot_end2end", "pivot→bone 父子樹寫入 build_spine(--rig)", "L2",
                "python3 tools/analyzer/validate_rig_build.py", "pipeline",
                note="build_spine --rig 端到端產關節鏈(父子樹改由 infer_tree 幾何推斷,非星形先驗)+ validate_rig_build 4AC(結構/setup不位移/pivot往返/關節語意 vs 非rig對照)PASS;"
                     "仍 L2 非 L3:僅單一 robot rig 驗過(Award 僅此件可拆肢體;OMG/SUP/MEG 為單圖+特效,無接觸縫)→ 多 rig 真值屬使用者資源"),
            CAP("rig_weighted_combo", "--rig × --weighted 併用(weighted 控制骨接進關節鏈)", "L2",
                "python3 tools/analyzer/validate_rig_weighted_build.py", "pipeline",
                note="移除 --rig/--weighted 互斥;weighted mesh 控制骨改掛該件關節骨 b_{nm}(座標轉局部)→ 4AC PASS "
                     "(結構/ setup 逐頂點 0.00px / 自articulate+鏈帶動 vs weighted-only 脫鉤(0px)/ 關節旋轉逐幀 si=0)。"
                     "仍 L2:同 pivot_end2end,僅單一 robot rig 驗過(多 rig 真值屬使用者資源)"),
            CAP("rig_weighted_chain", "多跳 weighted 肢體鏈(weighted mesh 當鏈中段)", "L2",
                "python3 tools/analyzer/validate_rig_weighted_chain.py", "pipeline",
                note="補 robot_parts 無『weighted mesh 當鏈中段肢體』樣本的缺口:合成鏈 fixture "
                     "(make_limb_chain_psd:body→arm→forearm→hand,arm/forearm 皆 weighted mesh)。5AC PASS:"
                     "鏈深 4≥3 非星形 / setup 0.00px / 遞迴帶動(轉 b_body→forearm 隔一跳仍隨動 80px、"
                     "轉 b_arm→forearm 動 body 不動、weighted-only 全脫鉤 0px)/ region 葉件隨鏈 / 逐幀 si=0。"
                     "演算法早已支援(接觸縫遞迴+控制骨掛關節骨),本閘證端到端成立。honest boundary:合成 fixture 非藝術家真值"),
        ],
    },
    {
        "id": "spine-anim-forge",
        "title": "分鏡 → 會動 Spine timeline(bone/slot + mesh deform)",
        "target_skill": "HOLD:讓 build --animate 素材『會動』;運動基元為手感先驗(非學自真值),達 L3 前不打包",
        "caps": [
            CAP("storyboard_keyframe", "分鏡→bone TRS + slot alpha timeline(0d)", "L2",
                "python3 tools/analyzer/build_spine.py assets/robot_parts.psd --out specs/_anim_chk_spine --animate >/dev/null && "
                "python3 tools/analyzer/validate_anim.py specs/_anim_chk_spine/skeleton.json",
                "gen", note="4AC(有限/loop無縫/pose不擾動/beat串接)+ --selftest 負對照全偵測;"
                            "role→運動基元為先驗手感提案(非學自真值),緩動美感留使用者(A類)"),
            CAP("mesh_deform_gen", "分鏡→mesh deform timeline(真實律動場轉移,0e)", "L2",
                "python3 tools/analyzer/validate_deform_gen.py", "pipeline",
                note="補 0d 只動 bone/slot 的缺口:軟件/特效 mesh 本身 deform。運動=真實 main_draw 窗簾/陰影 "
                     "deform 場(deform_eval.real_deform_field)UV 轉移到目標 mesh;beat 包絡首尾回 setup(無縫)。"
                     "7AC PASS(結構/逐幀乾淨/loop無縫/setup介面/幅度≤真實裕度/負對照 scramble×3 全破+連貫×4不破/"
                     "build_spine --animate --deform 端到端生成 mesh 逐幀乾淨)。gate=deform_eval(真實位移場,已驗可信)。"
                     "honest boundary:件role→律動場來源為先驗映射(預設軟布料模板);單一真值資產"),
            CAP("storyboard_beat_templates", "big-win 主秀 beat 模板 hit/reveal(anticipation+settle,0f)", "L2",
                "python3 tools/analyzer/validate_beat_templates.py",
                "gen", note="補 0d 只有對稱脈衝的缺口:hit=反向預備→命中→阻尼回擺、reveal=藏→蓄勢→炸開→回穩,"
                            "皆 setup identity/collapse 介面可與 In/Loop/Out 串接。6AC(well-formed/可串接介面/真峰/"
                            "anticipation/settle 阻尼回擺/負對照)全 PASS;負對照證閘能分辨主秀 hit 與天真對稱脈衝(gen_pulse "
                            "無反向預備+無阻尼回擺→非主秀)、不歸位、無峰。真值=結構簽章(非美感,美感留使用者 A類)"),
            CAP("main_show_priors_integration", "主秀 beat 接進 genre 先驗庫(E,build --animate 直出主秀)", "L2",
                "python3 tools/analyzer/validate_priors_beats.py", "pipeline",
                note="把 0f 的 hit/reveal 併入 genre_priors:slot_bigwin 加 burst(reveal)+hit beat、slot_reveal 既有 "
                     "open→reveal/hit→hit。與 validate_beat_templates 差別=本閘從**先驗庫**經 analyze_target.build_storyboard "
                     "→ build_animations,證主秀節拍真的從先驗流到最終 animations(--animate 直出),非只驗合成模板。"
                     "5AC PASS(P1 主秀 clip 真峰≥1.12/P2 介面契約 reveal collapse→identity・hit identity 首尾/"
                     "P3 結構簽章 hit_signature+reveal collapse-hold+峰後穿越≥2/P4 已驗先驗覆蓋率仍 1.0 未擾動/"
                     "P5 負對照 character_idle 產 0 主秀 clip・非主秀 beat 不具簽章)。honest:主秀運動仍先驗手感、burst/hit "
                     "於 Award 真值無命名故 validate_priors 列 prior_beats_unused(誠實 PROPOSAL);單一真值資產"),
            CAP("beat_library_expansion", "擴充主秀 beat 庫:combo(多峰遞增)+ anticipate_hold(長蓄力,0g)", "L2",
                "python3 tools/analyzer/validate_more_beats.py", "gen",
                note="續 0f 再加兩個大獎節拍,各有**互不相同**的客觀結構簽章:combo=遞增 impact 峰數≥3(單發 hit 僅 1 峰)、"
                     "anticipate_hold=峰前長蓄力時間佔比≥0.35(hit 蓄力僅短暫 dip)。皆保 setup identity 介面(可插 Loop 間)。"
                     "6AC PASS(well-formed/可串接介面/真峰/兩簽章各成立/共用 anticipation+settle/負對照)+9 條負對照全過:"
                     "兩簽章互斥、單發 hit 與對稱脈衝皆非 combo/charge、等峰 combo 非遞增。真值=結構簽章(美感留使用者 A類)"),
            CAP("cross_part_cascade", "cascade 跨件錯開波(跨件時序簽章,0h)", "L2",
                "python3 tools/analyzer/validate_cascade.py", "gen",
                note="補 0f/0g 全是**單件內**時序簽章的缺口:cascade=每件依件序相位錯開觸發成一道波,簽章在**件之間**"
                     "(各件峰時刻依件序嚴格遞增 + 散佈 ≥0.30),必須端到端經 build_animations 量測(證 per-part phase "
                     "threading 有接上)。pop 波形首尾 identity 可插 Loop 間。6AC PASS(well-formed/可串接介面/真峰/跨件簽章/"
                     "共用 anticipation+settle/負對照)+ 7 條負對照:combo(同時序)spread≈0 非波、打亂/反序件序非遞增、"
                     "cascade 單件非 combo 簽章(證與 0g 正交)、單件無 spread 非波。真值=結構簽章(美感留使用者 A類)"),
            CAP("pivot_rotate_keyframe", "件繞關節 pivot 轉(keyframe 級,把 S5 接觸縫 pivot 接進 keyframe,0i)", "L2",
                "python3 tools/analyzer/validate_pivot_rotation.py", "pipeline",
                note="把 S5 的接觸縫 pivot 餵進 S1 keyframe 生成器:件繞**關節 pivot** 轉而非件中心。非 rig 下 bone 落件中心 O,"
                     "原 rotate 讓件繞 O 轉(對肢體不物理);本能力在 rotate 外加補償 translate Δ(θ)=(R(θ)−I)(O−P),淨效果=繞 pivot P 轉,"
                     "**完全不動骨架結構**(與 --rig 搬骨的結構性解法互補)。Δ 對 θ 非線性 → rotate 通道加密重取樣(dt=1/60)使幀間殘差<<0.1px。"
                     "build_spine --animate --pivot-rotate 復用 rig_layout 的樹+接觸縫推斷取 pivot。7AC PASS(對真實 Award 左手世界幾何+推得肩 pivot):"
                     "AC1 pivot 不動點殘差 0.01px、AC2 負對照繞件中心位移 48.8px(>>AC1)、AC3 件最遠點轉 94px、AC4 θ=0 幀 Δ=0(identity 保持)、"
                     "AC5 剛性等距 0.01px、AC6 端到端經 build_animations 產 loop→apply_pivots 後仍有限/無縫/pivot 不動(內建負對照未套用會動 9.75px)、"
                     "AC7 bezier 緩動仍成立。回歸:validate_anim(+selftest)、round-trip build 對 --pivot-rotate build 全 PASS(setup pose 不變)。"
                     "真值=幾何不動點(客觀);繞 pivot 是否貼手感的美術微調留使用者(A類)。honest boundary:單一 rig 真值、與 anim-forge 同 HOLD"),
            CAP("scale_pivot_keyframe", "件繞關節 pivot 縮放(0i 延伸 G-3,把旋轉+縮放統一成 M=R·S 補償)", "L2",
                "python3 tools/analyzer/validate_scale_pivot.py", "pipeline",
                note="把 0i「繞關節 pivot 轉」推廣到「繞關節 pivot 縮放」:In/Out/pulse 給件的 scale 非 rig 下繞件中心脹縮(手臂該從肩伸長)。"
                     "一條公式統一——Δ=(M−I)(O−P),M=R(θ)·diag(sx,sy)(Spine TRS);0i 是 S=I 特例、θ=0,s=1 時 Δ=0(identity 保持)。"
                     "純均勻 scale 約 pivot 是相似變換 ∀x |world(x)−P|=s·|x−P|(取代 0i 剛性 AC 的判準)。pivot_rotation.py 延伸"
                     "(pivot_delta_full/pivot_channels_srt/apply_pivots(include_scale=),include_scale=False 預設=0i 路徑逐位元不變)+ "
                     "build_spine --scale-pivot(含 --pivot-rotate 語意)。踩雷同 0i:Δ 對 θ、s 皆非線性 → rotate 與 scale 都密網格重取樣。"
                     "7AC PASS(對真實 Award 左手+推得肩 pivot |O−P|=117px):AC1 不動點 0.0001px、AC2 負對照繞件中心 70.46px(=0.6×117)、"
                     "AC3 件最遠點相對變化 0.600、AC4 s=1 端點 Δ=0、AC5 相似 |w−P|=s|x−P| 偏差 0.0001px、AC6 rotate 24°+scale 1.6 併 0.037px"
                     "(證 M=R·S 組合)、AC7 端到端經 build_animations pulse(limb scale+rotate 無 translate)pivot 不動 0.014px vs 負對照 22.14px。"
                     "回歸:0i validate_pivot_rotation(逐 AC PASS,路徑不變)、validate_anim(+selftest)、round-trip 對 --scale-pivot build 全綠。"
                     "honest boundary:pivot 真值仍 S5 接觸縫草案、單一 rig、只非 rig 下套用;縮放幅度手感留使用者(A類)。與 anim-forge 同 HOLD"),
            CAP("combo_charge_priors_integration", "combo/charge 接進 genre 先驗庫(H,build --animate 直出連擊/蓄力)", "L2",
                "python3 tools/analyzer/validate_priors_combo_charge.py", "pipeline",
                note="續 (E) 對 hit/reveal 所做,把 0g 的 combo(連擊)/charge(蓄力充能)節拍併入 genre_priors:slot_bigwin 加 "
                     "combo+charge beat(beat key 經 beat_category 路由到 gen_combo/gen_anticipate_hold)。與 validate_more_beats(0g)"
                     "差別=本閘從**先驗庫**經 analyze_target.build_storyboard → build_animations,證 combo/charge 真的從先驗流到最終 "
                     "animations(--animate 直出),非只驗合成模板(「模板就緒 ≠ 生成器接上」在 combo/charge 上補上)。5AC PASS"
                     "(H1 present+routing 路由到 combo/charge 類別且真峰≥1.12/H2 介面契約首尾 identity 可插 Loop 間/H3 結構簽章 "
                     "combo=遞增 impact 峰≥3・charge=峰前長蓄力≥0.35 且兩簽章互斥/H4 已驗先驗覆蓋率仍 1.0 未擾動(combo/charge 為 "
                     "prior_beats_unused)/H5 負對照 character_idle 產 0 combo/charge clip・非 combo/charge beat 不具其簽章)。"
                     "副產:H5 逼出 charge vs reveal 鑑別子——兩者峰前皆長時間 <0.97,加 squash-floor(峰前最低 >0.5,charge 是壓縮"
                     "蓄力 ~0.85 非 reveal 塌陷 ~0.02)才分得開(強化 has_charge_signature,0g 閘回歸仍 PASS)。honest:主秀運動仍先驗手感、"
                     "combo/charge 於 Award 真值無命名故 validate_priors 列 prior_beats_unused(誠實 PROPOSAL);單一真值資產。與 anim-forge 同 HOLD"),
            CAP("cascade_priors_integration", "cascade 接進 genre 先驗庫(I,build --animate 直出跨件錯開波)", "L2",
                "python3 tools/analyzer/validate_priors_cascade.py", "pipeline",
                note="續 (E)/(H),把 0h 的 cascade(跨件錯開波)併入 genre_priors:slot_bigwin 加 cascade beat(beat key 經 "
                     "beat_category 路由到 gen_cascade)。cascade 比 (E)/(H) 多驗一層——它是**跨件**時序簽章(同 beat 套每件但依件序相位錯開"
                     "成波),故本閘證的不只 beat 有流到 animations,還證 _PHASE_AWARE 的件序相位 threading 端到端存活(單件曲線看不出)。"
                     "從**先驗庫**經 analyze_target.build_storyboard → **真實 build_spine 骨架** → build_animations，對真實 robot 5 拆件 "
                     "5AC PASS(I1 present+routing 路由到 cascade 類別且每件真峰≥1.12/I2 每件首尾 identity+特效 slot alpha=1 可插 Loop 間/"
                     "I3 crux 跨件簽章 各件峰時刻依真實件序 [0.158,0.296,0.429,0.567,0.70] 嚴格遞增・散佈 0.542≥0.30・非 combo 簽章/"
                     "I4 已驗先驗覆蓋率仍 1.0(cascade 為 prior_beats_unused)/I5 負對照 character_idle 產 0 cascade clip・非 cascade beat 不成波)。"
                     "副產:I5 逼出「跨件簽章需散佈+遞增兩條件並立」——Loop 散佈 0.5 甚至 > 門檻但無序→正確判非波(此鑑別力 0h 只在手搭 "
                     "fixture 驗過,本次在真實產線再現)。honest:主秀運動仍先驗手感、cascade 於 Award 真值無命名列 prior_beats_unused(誠實 "
                     "PROPOSAL);單一真值資產。與 anim-forge 同 HOLD"),
            CAP("tier_variant_amplitude", "檔位幅度差異化(J,build --animate --tier-variants 直出各檔位主秀變體)", "L2",
                "python3 tools/analyzer/validate_tier_variants.py", "pipeline",
                note="genre_priors.slot_bigwin 宣告 tiers=[Super,Mega,Omg,Legend] 已久但生成器從未用它(所有檔位共用同組主秀幅度)"
                     "——又一「宣告就緒 ≠ 生成器接上」缺口。把檔位轉成**主秀幅度增益** g(檔位愈高愈爆),端到端接進 build_animations,"
                     "每主秀 beat 依檔位產出 {beat}__{tier} 變體。tier_variants.py 幅度增益規則(對介面契約與結構簽章皆保形):"
                     "scale 只放大 identity **上方** overshoot(v'=1+g(v−1) 僅當 v≥1;下方 squash/collapse 樓地板不動)、rotate/translate 對 0 "
                     "對稱放大(v'=g·v)、color/alpha 不動;base=Super g=1.0 → 逐位元同無檔位輸出(向後相容)。build_spine --tier-variants。"
                     "從**先驗庫**經 build_storyboard → **真實 build_spine robot 骨架** → build_animations 對真實 robot 5 拆件 5AC PASS"
                     "(J1 present+routing 每主秀 beat×每檔位皆產變體且名經 beat_category 仍路由回原類別/J2 每檔位介面契約 hit/combo/charge/cascade "
                     "首尾 identity・burst 尾 identity 首 collapsed 樓地板/J3 crux scale overshoot 幅度 Super<Mega<Omg<Legend 嚴格遞增(端到端量)/"
                     "J4 每檔位結構簽章保持 combo≥3 遞增峰・charge 長蓄力・hit anticipation+settle・cascade 跨件峰時刻遞增散佈/J5 負對照 "
                     "In/Loop/Out 不產變體・無 tier 的 slot_reveal gains_for 回 None 不產變體且 base 相同・平增益守衛全 1.0→J3 單調性 FALSE 證閘可信)。"
                     "關鍵:幅度增益只放大 identity 上方 overshoot、不動下方樓地板與時間軸 → 端點/簽章對所有檔位保形(檔位簽章=更爆的 overshoot;"
                     "蓄力深度/藏匿是結構語意非大獎強度,誠實地檔位無關)。回歸:validate_priors/priors_beats/more_beats/beat_templates/cascade/"
                     "priors_combo_charge/priors_cascade/anim(+selftest)/pivot_rotation/scale_pivot/deform_gen/round-trip(含 --tier-variants build)全綠。"
                     "honest:主秀運動仍先驗手感、增益階梯數值為 PROPOSAL(結構簽章非美感);單一真值資產。與 anim-forge 同 HOLD"),
            CAP("tier_variant_combo_count", "檔位連擊數遞增(J-2,combo 峰數 Super3→Legend6 隨檔位遞增)", "L2",
                "python3 tools/analyzer/validate_tier_combo_count.py", "pipeline",
                note="candidate (J) 讓檔位變體只差**幅度**(愈爆),combo 各檔位仍同樣三連擊 —— 有『多爆』沒『連幾下』。"
                     "本 cap 補上:combo 的 impact 峰**數**=nhits 隨檔位嚴格遞增(Super3/Mega4/Omg5/Legend6)。連擊數是**結構**"
                     "(gen 時決定峰數,事後 amplify 加不出)→ 走 tier_combo_hits 對 combo 檔位變體以該檔位 nhits **重生成**再套幅度增益;"
                     "gen_combo(nhits=) 通用生成遞增 nhits 峰(nhits=3 逐位元同 0g 手調三連擊,向後相容)。與 (J) 幅度軸**正交可疊**"
                     "(nhits 決定連幾下、gain 決定多爆)。build_spine --tier-variants 直出(combo_hits_for slot_bigwin)。"
                     "從先驗庫→真實 build_spine robot 骨架→build_animations,validate_tier_combo_count.py 5AC PASS"
                     "(K1 present+backward-compat 每檔位產變體 finite/有 bone・base combo 恆 3 峰不變・tier_combo_hits=None 逐位元同 (J) 幅度-only 輸出/"
                     "K2 crux combo 峰數 [3,4,5,6]==宣告且 Super<Mega<Omg<Legend 嚴格遞增・每檔位內部峰值仍遞增/K3 每檔位首尾 identity・"
                     "仍 has_combo_signature・仍 settle・**仍非 charge**(連擊增多不誤入長蓄力)・幅度仍單調(與 J 疊加不衝突)/"
                     "K4 正交 counts+平增益→峰數仍遞增(結構獨立於幅度)・gains+無 counts→峰數恆 3 幅度遞增/K5 負對照 平連擊數全 3→峰數單調 FALSE"
                     "證閘可信・無宣告 count 的 slot_reveal→combo_hits_for None 不亂加・count 只作用 combo 不外洩 hit/charge/cascade/burst)。"
                     "回歸:validate_tier_variants(J,幅度-only 不變)/more_beats/priors_combo_charge/cascade/round-trip(含 --tier-variants build)全綠。"
                     "honest:連擊數階梯(3–6)為 PROPOSAL(結構簽章非美感);單一真值資產。與 anim-forge 同 HOLD"),
            CAP("shear_channel_generation", "生成器產出 shear 通道端到端(G-4',斜拉 wobble beat + --shear-pivot)", "L2",
                "python3 tools/analyzer/validate_shear_gen.py", "pipeline",
                note="G-4 補齊了『件繞關節 pivot 一般仿射(含 shear)』的**公式+閘**,但 honest boundary:當時**沒有任何 beat 產出 shear**"
                     "(產線只用 rotate/scale,G-4 的 AC7 用合成 shear 驗管路)。本 cap 補上那最後一段:gen_wobble(斜拉 jelly wobble)"
                     "**實際產出 shear 通道**(阻尼 shearX 擺動,首尾 identity),經 genre_priors.slot_bigwin 新增 wobble beat 直出;"
                     "build_spine --shear-pivot 帶 include_shear=True 端到端補償 → 件繞關節 pivot 做一般仿射而 pivot 精確不動。"
                     "從先驗庫→真實 build_spine robot 骨架→build_animations,validate_shear_gen.py 5AC PASS"
                     "(W1 present+shear 產出 crux=峰值 16°/W2 阻尼振盪簽章 繞0變號≥3+相繼極值嚴格遞減/W3 identity 介面可插 Loop/"
                     "W4 端到端 --shear-pivot pivot 殘差 <0.02px vs 負對照 8–24px(arm 50–164px)/W5 負對照 天真單調 shear 簽章 FALSE・"
                     "shear 隔離 僅 wobble 帶 shear・移除 wobble 其餘 beat 逐位元不變)。回歸:全 priors/tier/beat/pivot 系列 + round-trip"
                     "(--shear-pivot build overall_pass premult MAE 0.031 setup 不變)全綠。"
                     "honest:斜拉 wobble 為 PROPOSAL(阻尼振盪結構簽章非美感);shearY≡0、tier 變體未接;單一真值資產。與 anim-forge 同 HOLD"),
            CAP("wobble_tier_amplitude", "wobble shear 峰隨檔位遞增(G-4'',shear 通道接檔位差異化)", "L2",
                "python3 tools/analyzer/validate_wobble_tier.py", "pipeline",
                note="G-4' 讓 gen_wobble 產出 shear 通道,但當時 honest boundary:wobble ∉ MAIN_SHOW_CATS → **檔位機制(J)未放大 shear**"
                     "(J 的幅度增益只作用 scale/rotate/translate)。本 cap 補上:把 wobble 併入 MAIN_SHOW_CATS 並讓 amplify_bone_tl 一併"
                     "放大 shear(對 0 對稱 → v'=g*v,同 rotate/translate)→ wobble 的 shearX 峰隨檔位嚴格遞增(Super16°→Legend33.6°),"
                     "同時阻尼振盪簽章(振盪+遞減)在**每個檔位**保持(g*v 同比放大 → 符號序列與遞減比不變)。與 (J) 幅度軸同一機制、"
                     "對 shear 通道的自然推廣 —— 又一『檔位機制就緒 ≠ 每個新通道接上』實例(同 E/H/I/J/G-4')。"
                     "從先驗庫→真實 build_spine robot 骨架→build_animations(tier_gains),validate_wobble_tier.py 5AC PASS"
                     "(T1 present+backward-compat 每檔位產 wobble__tier finite/有 bone/帶 shear・base 逐位元不變/"
                     "T2 crux shear 峰 [16,21.6,27.2,33.6] Super<Mega<Omg<Legend 嚴格遞增且 Super==base/"
                     "T3 每檔位仍首尾 0+繞 0 變號≥3+相繼極值遞減(阻尼簽章保形)/T4 shear 隔離 只 wobble 及其變體帶 shear/"
                     "T5 負對照 平增益全 1.0→遞增 FALSE 且各檔位==base・通道隔離單元測 scale-only 不生 shear·shear-only 不生 scale)。"
                     "回歸:validate_tier_variants(J,J3 改 channel-aware 仍全綠)/tier_combo_count/shear_gen/全 priors/beat/pivot 系列全綠。"
                     "honest:shear 峰階梯沿用 (J) 幅度增益(PROPOSAL);shearY≡0;wobble 未接 count-aware(shearY/斜拉 squash 為後續);單一真值資產。與 anim-forge 同 HOLD"),
            CAP("wobble_tier_segment_count", "wobble 晃動段數隨檔位遞增(G-4''',阻尼擺動極值數 Super4→Legend7)", "L2",
                "python3 tools/analyzer/validate_wobble_count.py", "pipeline",
                note="G-4'' 讓 wobble 的 shear **峰值(幅度)**隨檔位遞增,但當時 honest boundary:所有檔位仍**同樣四擺**"
                     "(有『多斜』沒『晃幾下』)。本 cap 補上:wobble 的阻尼擺動**極值數** nseg 隨檔位嚴格遞增(Super4→Mega5→"
                     "Omg6→Legend7)。**關鍵:段數是結構、amplify 加不出來**——事後同比放大只能放大既有極值、無法多長一擺;"
                     "故不走 amplify,而對 wobble 檔位變體以該檔位 nseg **重生成**整個 beat(gen_wobble(nseg=),nseg=4 逐位元同 G-4' 手調"
                     "golden 四擺,向後相容),**再**疊 (G-4'') shear 幅度增益 → 與幅度軸**正交可疊**(端到端:段數 [4,5,6,7] × "
                     "shear 峰 [16,21.6,27.2,33.6] 皆遞增)。**又一『幅度機制就緒 ≠ 結構數接上』實例(同 J-2 之於 combo)**。"
                     "COUNT_AWARE_CATS 併入 wobble;build_animations 加 tier_wobble_segs(None→生成器自身預設,加性 opt-in);"
                     "build_spine --tier-variants 自動帶 seg。validate_wobble_count.py 5AC PASS"
                     "(V1 present+backward-compat 每檔位產 wobble__tier finite/有 bone/帶 shear・base 恆 nseg=4 逐位元不變・"
                     "tier_wobble_segs=None 逐位元同 (G-4'') 幅度-only/V2 crux 段數 [4,5,6,7]==宣告且嚴格遞增·每檔位仍阻尼/"
                     "V3 每檔位首尾 0+變號≥3+極值遞減·且 shear 峰仍隨檔位遞增(與 G-4'' 疊加不衝突)/V4 正交 segs+平增益→段數仍遞增·"
                     "gains+無 segs→段數恆 4 幅度遞增/V5 負對照 平段數全 4→遞增 FALSE·slot_reveal 無宣告→不產變體·seg 只作用 wobble 不外洩到 combo)。"
                     "回歸:validate_wobble_tier(G-4'')/tier_combo_count(J-2)/shear_gen/tier_variants/全 pivot/priors/beat 系列全綠、round-trip build overall_pass。"
                     "honest:斜拉 wobble 形狀為 PROPOSAL(結構簽章客觀、手感留使用者);shearY≡0;段數上界 7(T=0.8s 時間可容);單一真值資產。與 anim-forge 同 HOLD"),
        ],
    },
]

LADDER = {"L0": 0, "L1": 1, "L2": 2, "L3": 3, "L4": 4}


_CACHE = {}  # 同一 validator 指令只實跑一次(多能力共用一支閘時避免重跑)


def run_validator(cmd, timeout=200):
    if not cmd:
        return None, 0.0
    if cmd in _CACHE:
        return _CACHE[cmd], 0.0
    t0 = time.time()
    try:
        r = subprocess.run(cmd, shell=True, cwd=ROOT, env=ENV,
                           capture_output=True, timeout=timeout)
        green = (r.returncode == 0)
    except subprocess.TimeoutExpired:
        green = False
    _CACHE[cmd] = green
    return green, time.time() - t0


def assess(quick=False):
    report = []
    for blk in BLOCKS:
        caps_out = []
        core_ok = True
        has_l3_green = False
        for c in blk["caps"]:
            if quick and c["heavy"]:
                green = None  # 未跑
            else:
                green, dt = run_validator(c["cmd"])
            lvl = LADDER[c["level"]]
            # 門檻邏輯:核心能力(gen/pipeline)須 ≥L2 且(若有閘)GREEN
            is_core = c["role"] in ("gen", "pipeline")
            gate_ok = (green is not False)  # None(無閘/未跑)不算 fail
            if is_core and (lvl < 2 or green is False):
                core_ok = False
            if lvl >= 3 and green is not False:
                has_l3_green = True
            caps_out.append({**{k: c[k] for k in ("key", "name", "level", "role", "note")},
                             "validator_green": green})
        ready = core_ok and has_l3_green
        report.append({
            "id": blk["id"], "title": blk["title"], "target_skill": blk["target_skill"],
            "block_maturity": max((c["level"] for c in blk["caps"]), key=lambda l: LADDER[l]),
            "READY_TO_SKILL": ready,
            "verdict": "READY ✅" if ready else "HOLD ⛔",
            "caps": caps_out,
        })
    return report


def fmt(report):
    lines = []
    for b in report:
        lines.append(f"\n■ {b['id']} — {b['title']}")
        lines.append(f"  區塊成熟度 {b['block_maturity']} → {b['verdict']}")
        lines.append(f"  目標:{b['target_skill']}")
        for c in b["caps"]:
            g = {True: "GREEN", False: "RED", None: "—"}[c["validator_green"]]
            note = f"  «{c['note']}»" if c["note"] else ""
            lines.append(f"    [{c['level']}] {c['name']:38s} 閘:{g:5s} ({c['role']}){note}")
    return "\n".join(lines)


if __name__ == "__main__":
    quick = "--quick" in sys.argv
    rep = assess(quick=quick)
    if "--json" in sys.argv:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        print("=" * 78)
        print("skill 化完成度矩陣" + ("(--quick:略過 heavy 閘)" if quick else "(已實跑全部 validator)"))
        print("=" * 78)
        print(fmt(rep))
        ready = [b["id"] for b in rep if b["READY_TO_SKILL"]]
        hold = [b["id"] for b in rep if not b["READY_TO_SKILL"]]
        print("\n" + "=" * 78)
        print("可 skill 化(達門檻):", ", ".join(ready) or "無")
        print("HOLD(防固化半成品):", ", ".join(hold) or "無")
