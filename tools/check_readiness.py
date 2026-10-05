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
            CAP("pivot_main_show_integration", "主秀節拍下 limb 繞關節 pivot 旋轉+縮放(G-2,整合閘:真實產線主秀 beat × 真實推得關節)", "L2",
                "python3 tools/analyzer/validate_pivot_main_show.py", "pipeline",
                note="把兩條既有能力接起來驗:0i/G-3 的繞關節 pivot(--pivot-rotate/--scale-pivot)與 genre 先驗庫直出的主秀 beat。"
                     "0i(validate_pivot_rotation AC6)/G-3(validate_scale_pivot AC7)的端到端 AC 都只在**合成 skeleton+合成單一 beat**"
                     "(Loop/Win pulse)上驗機制;另一邊主秀 beat(hit/combo/charge/burst/cascade)早由 build_spine --animate 直出,且 "
                     "build_spine 的 apply_pivots 迴圈**逐一掃過所有 animations**(主秀 limb rotate/scale 其實已被轉成繞關節版)——但"
                     "**從未有 AC 驗過『真實產線產的主秀節拍下 limb 真的繞關節而非件中心動』**。本閘補上:從 genre 先驗庫→**真實 "
                     "build_spine --animate --scale-pivot robot 骨架**(apply_pivots 在 build 內實跑)→對**每個**旋轉/縮放主秀節拍"
                     "(cat∈MAIN_SHOW_CATS−SHEAR_CATS=hit/combo/charge/burst/cascade;shear 節拍 wobble/squash/twist 需 --shear-pivot,"
                     "其繞關節性質已由 validate_{twist,squash}_* 端到端 pivot 殘差 AC 覆蓋)×**每個**有關節 limb/head bone(右手/頭/左手)量測。"
                     "5AC PASS(15 組 pair=5 主秀節拍×3 有關節 limb):M1 present+routing(summary 具 pivot_centers/joints、每主秀節拍有補償 limb、"
                     "非關節件光暈/身體不在 joints、結構節拍 finite)、M2 crux 繞關節不動點 最差殘差 0.39px(<0.5)且件最遠點位移≥40.79px(真在動)、"
                     "M3 負對照繞件中心 逐 pair 比值≥147×(主判準:補償砍關節運動≥20×)且最大位移 161px(量級明顯)、M4 保設定姿勢(27 個靜止端點補償後 Δ=0;"
                     "**burst 首刻意塌陷登場非 setup → 不要求 identity,其關節仍由 M2 保證不動**)、M5 isolation+正確轉換集合(非關節件 comp/raw 逐位元同、"
                     "有差異 bone 集合==恰好有關節 limb 集合,無漏轉/多轉)。真值=關節幾何不動點(客觀,S5 接觸縫推得);限主秀運動手感為美術(A 類)。"
                     "honest boundary:單一 rig 真值、只非 rig 下套用、shear 節拍另由他閘覆蓋。與 anim-forge 同 HOLD"),
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
            CAP("wobble_count_generation", "wobble 振盪段數隨檔位遞增(G-4''',晃動段數 Super4→Legend7 隨檔位遞增)", "L2",
                "python3 tools/analyzer/validate_wobble_count.py", "pipeline",
                note="G-4'' 讓 wobble 的 shear 峰**幅度**隨檔位遞增,但各檔位仍**同樣 4 段**阻尼振盪(有『多斜』沒『晃幾下』)。"
                     "本 cap 補上振盪**段數** nosc 隨檔位嚴格遞增(Super4→Mega5→Omg6→Legend7)。**關鍵:幅度增益加不出段數** —— "
                     "段數是關鍵幀**拓樸**(繞 0 交替極值個數),須在 gen_wobble 生成當下決定,事後 amplify 只能放大既有極值、無法多長一段;"
                     "故對 wobble 檔位變體以該檔位 nosc **重生成**(gen_wobble(nosc=),nosc==4 逐位元同 G-4' golden),再疊 (G-4'') 幅度增益 → "
                     "與幅度軸**正交可疊**(段數 [4,5,6,7]×峰幅 [16,21.6,27.2,33.6]° 皆遞增)。此模式同 (J-2) 對 combo 連擊數,惟段數階梯"
                     "各類別獨立(combo→TIER_COMBO_HITS、wobble→TIER_WOBBLE_CYCLES,build_animations 依 cat 路由)—— 又一『檔位機制就緒 ≠ 每個軸接上』實例。"
                     "從先驗庫→真實 build_spine robot 骨架→build_animations(tier_gains,tier_wobble_cycles),validate_wobble_count.py 5AC PASS"
                     "(U1 present+backward-compat 每檔位產 wobble__tier finite/有 bone/帶 shear・base 恆 4 段逐位元不變・twc=None 逐位元同 (G-4'') 幅度-only/"
                     "U2 crux 段數 [4,5,6,7]==宣告 Super<Mega<Omg<Legend 嚴格遞增且 Super==base/U3 每檔位仍首尾 0+變號≥3+極值遞減(阻尼保形)且峰幅仍遞增/"
                     "U4 正交 段數+平增益→段數遞增·峰幅不遞增,增益+無段數→段數恆4·峰幅遞增/U5 負對照 平段數全4→單調 FALSE・slot_reveal wobble_cycles_for None 不亂加・段數只作用 wobble 不外洩)。"
                     "端到端 build_spine --animate --tier-variants --shear-pivot 直出 wobble__{Super4,Mega5,Omg6,Legend7} 段(pivot 補償後仍 [4,5,6,7]),validate_build round-trip overall_pass。"
                     "回歸:validate_wobble_tier(G-4'')/tier_combo_count/tier_variants/shear_gen/全 priors/beat/pivot 系列 16 閘全綠。"
                     "honest:段數階梯 PROPOSAL(手感留使用者 A 類);shearY≡0;斜拉 squash(shear+coupled scale)為後續;單一真值資產。與 anim-forge 同 HOLD"),
            CAP("squash_shear_scale_coupling", "生成器產耦合 shear + 非均勻 scale 體積守恆擠壓(G-4'''')", "L2",
                "python3 tools/analyzer/validate_squash_gen.py", "gen",
                note="補 G-4/G-4' 留到現在的 honest boundary(shearY≡0、斜拉 squash 為後續)。gen_squash 是**第一個同時產 shear 與非均勻 "
                     "scale(sx≠sy)** 的生成器:shearX 同 wobble 阻尼擺動,每個 shear 極值 i 施體積守恆 squash(scaleX=1+q_i 拉長、scaleY=1/(1+q_i) "
                     "壓扁,q_i=Q·rⁱ 與 shear 同源同阻尼)⇒ scaleX·scaleY≡1(面積守恆)且 scaleX≠scaleY(非均勻),首尾 identity。**關鍵:純 shear "
                     "(G-4' wobble)只是相似變換特例(等距+skew);shear+非均勻 scale 才是真正一般仿射** —— G-4 的通用 Δ=(M−I)(O−P) 第一次被生成器產的"
                     "非均勻 scale+shear 同時驅動(M 非相似,det=scaleX·scaleY·cos(shear))。genre_priors 加 squash beat 直出(additive、coverage 仍 1.0);"
                     "build_spine --shear-pivot(include_shear 隱含 include_scale)端到端把 rotate/scale/shear 三通道一起繞關節 pivot 補償。validate_squash_gen.py "
                     "6AC PASS(SQ1 present+dual-channel crux:shear 峰 16°+非均勻峰 0.30/SQ2 shear 阻尼振盪/SQ3 crux 體積守恆耦合:每極值幀 |scaleX·scaleY−1|≤5e-5+"
                     "非均勻 0.19–0.30+squash 幅度嚴格遞減/SQ4 identity 介面/SQ5 端到端一般仿射 pivot 殘差 0.005–0.018px vs 負對照 9–33px >1000×/"
                     "SQ6 負對照:等比 scale 守衛→非均勻 FALSE、非守恆守衛→體積 FALSE 而非均勻 TRUE 證兩條件獨立、耦合隔離、加性零回歸)。"
                     "新增 tier_variants.SHEAR_CATS={wobble,squash};shear-isolation 閘(shear_gen W5b/wobble_tier T4)改以此認定。16 閘全綠+round-trip validate_build overall_pass。"
                     "關鍵發現:真簽章常需兩獨立條件並立(體積守恆且非均勻;同 cascade 散佈且遞增、charge 長 hold 且 squash-floor)。"
                     "honest:squash 未接 tier(需耦合 amplify:_amp_scale 只放大 identity 上方會破壞守恆);shearY≡0;count-aware nosc 未接。與 anim-forge 同 HOLD"),
            CAP("squash_tier_coupled_amplify", "squash 接檔位差異化:體積守恆耦合 amplify(G-4''''')", "L2",
                "python3 tools/analyzer/validate_squash_tier.py", "pipeline",
                note="補 G-4'''' 明白列出的 honest boundary(squash 未接 tier 幅度:逐軸 _amp_scale 只放大 identity 上方 → 破壞體積守恆,需**耦合 amplify**)。"
                     "**關鍵:面積守恆 scaleX·scaleY≡1 是跨通道約束**,放大必須沿守恆流形走 —— 逐軸 _amp_scale 會脹 scaleX(>1)卻保留 scaleY(<1)樓地板 → 破守恆"
                     "(實測逐軸 Legend 增益下 |積−1| 達 0.10–0.15)。解法 _amp_scale_coupled:放大**拉長軸** overshoot(sx'=1+g·q)、壓縮軸設**倒數**(sy'=1/sx')"
                     " → scaleX·scaleY≡1 **由建構保證**在任一檔位保持,擠壓非均勻度隨檔位嚴格遞增;同源 shearX 峰亦隨檔位遞增(走既有 v'=g*v)⇒ "
                     "**第一個 shear + 非均勻 scale 兩通道同時檔位差異化**的節拍、**第一個帶跨通道守恆約束的檔位軸**。squash 併入 MAIN_SHOW_CATS;"
                     "新增 COUPLED_SCALE_CATS={squash},build_animations 依此路由耦合/逐軸 amplify(amplify_bone_tl(coupled=))。"
                     "從先驗庫→真實 build_spine robot 骨架→build_animations(tier_gains),validate_squash_tier.py 6AC PASS"
                     "(ST1 present+backward-compat 每檔位 dual-channel・base 逐位元不變・**Super g=1 逐位元==base squash**/"
                     "ST2 crux 每檔位每極值 |scaleX·scaleY−1|≤2e-4 + 非均勻 [0.298,0.394,0.486,0.588] 與拉長 [0.16,0.216,0.272,0.336] 皆嚴格遞增(Super==base)/"
                     "ST3 shear 峰 [16,21.6,27.2,33.6]° 遞增 + 每檔位阻尼簽章(繞0變號≥3+相繼極值遞減)保形/ST4 identity 介面(shear 首尾0・scale 首尾(1,1))/"
                     "ST5 crux 負對照 逐軸 amplify 破守恆 0.10–0.15 vs 耦合 ≤1e-4(>500× 鑑別餘裕)/ST6 平增益守衛+耦合 amplify 單元測+耦合隔離(wobble shear-only 不被波及)+加性零回歸)。"
                     "端到端 build_spine --animate --tier-variants --shear-pivot 直出 squash__{tier}(pivot 殘差 <0.06px 即使 Legend 最強一般仿射),validate_build round-trip overall_pass。"
                     "回歸踩雷:combo 專屬 _min_peaks(impact 門檻 1.10)對 squash head(base 峰恰 1.10)因耦合幅度增益推過門檻而誤判 count 外洩 → validate_tier_combo_count K5(c) 排除 SHEAR_CATS。18 閘全綠。"
                     "honest:squash count-aware(段數,gen_squash(nosc=) 已備參數未接);shearY≡0;幅度階梯 PROPOSAL(手感 A 類)。與 anim-forge 同 HOLD"),
            CAP("squash_tier_count_aware", "squash 擠壓段數隨檔位遞增(G-4'''''-c,段數×幅度×體積守恆三效正交)", "L2",
                "python3 tools/analyzer/validate_squash_count.py", "pipeline",
                note="補 G-4''''' 明白列出的 honest boundary(squash count-aware 段數未接:gen_squash(nosc=) 已備參數)。G-4''''' 讓 squash 的"
                     "shear 峰與擠壓**幅度**隨檔位遞增(愈高檔位擠愈深)而體積守恆保持,但各檔位仍**同樣 4 段**擠壓(有『擠多深』沒『擠幾下』)。"
                     "本 cap 補上擠壓**段數** nosc 隨檔位嚴格遞增(Super4→Mega5→Omg6→Legend7)。**關鍵:幅度增益加不出段數** —— 段數是關鍵幀**拓樸**"
                     "(繞 0 交替 shear 極值 = 耦合 squash 極值個數),須在 gen_squash 生成當下決定;故對 squash 檔位變體以該檔位 nosc **重生成**,再疊 (G-4''''') 的"
                     "**耦合**幅度增益 g。新增 TIER_SQUASH_CYCLES + squash∈COUNT_AWARE_CATS;build_animations 依 cat 路由 _count_maps。此模式同 (G-4'')wobble、(J-2)combo,"
                     "惟段數階梯各類別獨立。**squash 獨有 crux(與 wobble count 差異):squash∈COUPLED_SCALE_CATS → 段數重生成後仍走耦合 amplify,故段數×幅度×"
                     "體積守恆三效必須同時成立** —— 段數增多會多長出低幅擠壓極值(q_i=Q·rⁱ 隨 i 遞減),每個新極值仍由 _squash_env 建構 (1+q_i,1/(1+q_i)) → scaleX·scaleY≡1,"
                     "再經耦合 amplify 仍守恆。validate_squash_count.py 5AC PASS(SC1 present+backward-compat 每檔位 dual-channel・base 恆 4 段逐位元不變・tsc=None 逐位元同 (G-4''''') 幅度-only/"
                     "SC2 crux 段數 [4,5,6,7]==宣告嚴格遞增 Super==base **且**每檔位每內部極值 |scaleX·scaleY−1|≤2e-4(max 9.7e-05)/SC3 每檔位仍首尾 0+變號≥3+極值遞減(阻尼保形)"
                     "且峰 shear 與峰非均勻仍隨檔位遞增/SC4 正交 段數+平增益→段數遞增·非均勻不遞增·體積仍守恆,增益+無段數→段數恆4·非均勻遞增/SC5 負對照 平段數全4→單調 FALSE・"
                     "slot_reveal squash_cycles_for None 不亂加・段數只作用 squash 不外洩 wobble 仍4段)。端到端 build_spine --animate --tier-variants --shear-pivot 直出 "
                     "squash__{Super4,Mega5,Omg6,Legend7},validate_build round-trip overall_pass(premult MAE 0.031)。回歸:19 閘全綠(18 + 新 squash_count)。"
                     "honest:段數階梯 PROPOSAL(手感 A 類);shearY≡0;幅度階梯 PROPOSAL;單一真值資產。與 anim-forge 同 HOLD"),
            CAP("charge_tier_count_aware", "charge 蓄力階段數隨檔位遞增(G-4'''''-charge,階數×幅度兩效正交;count-aware 補齊全部單件主秀 beat)", "L2",
                "python3 tools/analyzer/validate_charge_count.py", "pipeline",
                note="把 count-aware(結構/段數軸)推到最後一個尚未接的單件主秀通道 charge(anticipate_hold,蓄力充能)。candidate (J) 已讓 charge 的 release 峰**幅度**"
                     "隨檔位遞增,但各檔位仍**同樣 1 階**單發蓄力(有『多爆』沒『蓄幾段』)。本 cap 補上充能-釋放**階段數** ncharge 隨檔位嚴格遞增(Super1→Mega2→Omg3→Legend4):"
                     "愈高檔位愈多階蓄力(每階一段長 hold + 遞增 release,末階=role peak)。**關鍵:幅度增益加不出蓄力階段** —— 階數是關鍵幀**拓樸**(dip→hold→release 窗數),"
                     "須在 gen_anticipate_hold 生成當下決定;故對 charge 檔位變體以該檔位 ncharge **重生成**,再疊 (J) 幅度增益 g(階數×幅度兩效正交可疊)。新增 TIER_CHARGE_CYCLES + "
                     "charge∈COUNT_AWARE_CATS(純 scale,非 SHEAR/COUPLED,走逐軸 amplify);build_animations 依 cat 路由 _count_maps。此模式同 combo/wobble/squash/twist,惟階數階梯各類別獨立。"
                     "**charge 獨有 crux(與 combo count 的差異 —— 計數簽章須多驗一層)**:combo 與 charge count **外形相同**(都是『N 個遞增 scale 峰』),光數 impact 峰無法鑑別;"
                     "差別在**峰間**:combo 峰間只有**短** dip(擊間微回 >HOLD_LEVEL),charge 每階 release 前有一段**持續**低 hold。故 charge count 簽章在『階數==ncharge』之外**多驗**"
                     "『每階 hold 佔比 ≥ 門檻』(每階皆真蓄力階),以此對 combo 做負對照(combo 每階 hold 佔比 <0.35 < 門檻 0.60 → FAIL)—— 呼應 (J-3)『真簽章常需兩獨立條件並立』。"
                     "validate_charge_count.py 5AC PASS(CC1 present+backward-compat 每檔位有 bone・base 恆 1 階逐位元不變・charge__Super 逐位元==base・tcc=None 逐位元同 (J) 幅度-only/"
                     "CC2 crux 階數 [1,2,3,4]==宣告嚴格遞增 Super==base/CC3 每檔位仍首尾 setup identity+具 charge 簽章(峰前長蓄力佔比≥0.35 非塌陷)+每階 hold 佔比≥0.60+階內 release 峰遞增,"
                     "且峰幅仍隨檔位遞增/CC4 正交 階數+平增益→階數遞增·峰幅不遞增,增益+無階數→階數恆1·峰幅遞增/CC5 負對照 平階數全1→單調 FALSE・**crux combo 判別子**(combo 每階 hold 佔比"
                     "0.31–0.34 < 0.60 → FAIL charge-count 簽章,且 combo 確有≥3 遞增峰 → 證『每階持續 hold』是鑑別子非『combo 沒峰』)・階數只作用 charge 非-charge 主秀變體逐位元同幅度-only・"
                     "slot_reveal charge_cycles_for None 不亂加)。**count-aware(段數軸)至此補齊全部單件主秀 beat:combo/wobble/squash/twist/charge 五通道 + cascade 跨件通道**。"
                     "honest:階數階梯 [1,2,3,4] 為 PROPOSAL(手感 A 類);單一真值資產。與 anim-forge 同 HOLD"),
            CAP("sequence_composition", "大獎序列組合:把各 beat clip 串接成單一可播放序列(L,整合/組合閘)", "L2",
                "python3 tools/analyzer/validate_sequence_compose.py", "pipeline",
                note="補的缺口(能力早在、AC 從缺,同 G-2 整合閘精神):build_animations 產出的是**各自獨立**的 beat clip(In/Loop/Out + 主秀 beat + {beat}__{tier}),"
                     "每支首尾皆 setup identity,**設計上**可在 runtime 依序播放成無縫大獎序列,但**從未有閘**驗過把它們真的串接成單一 timeline 時『接點無縫 / "
                     "各 beat 簽章在序列脈絡中仍成立 / 串接不扭曲任何值』。新增 gen_animations.compose_sequence(純時間平移 + 接點去重,additive)把跨 beat 串接**顯式做出來**"
                     "(In→hit→combo→charge→cascade→Loop→Out),直指 north star『產出可播放的大獎動畫』。選題理由:近期多是『單一 robot 加一軸』,本 run 刻意選**組合閘**抓回歸而非再加手感軸。"
                     "**踩雷(預算內自修):接點去重若丟『後者首幀』會連帶丟掉它的 outgoing 緩動 curve(Spine 緩動掛在起點幀)→ 後段首段內插用錯緩動,L3 回切殘差 7.09(非無損);"
                     "改丟『前者尾幀』(其 outgoing curve 屬 clip 之末無意義)、保留後者首幀 → 回切殘差 0.00 逐幀還原**。validate_sequence_compose.py 5AC PASS:"
                     "L1 well-formed+present(合法 Spine timeline 時間嚴格遞增・總時長==Σ段時長・segments 覆蓋序列・用到 bone 皆現身)/L2 crux 接點無縫(正向序列每內部接點"
                     "跨通道殘差 0.0 < 1e-3,皆 identity==identity)/L3 faithful concat(回切每段逐幀還原孤立 clip,殘差 0.00 < 1e-4 → 純平移無值扭曲)/L4 in-context 簽章"
                     "(從 composed 回切主秀段量測:combo 遞增 impact 峰≥3・cascade 跨件散佈≥0.30・charge 峰前長蓄力,且 == 孤立 clip 量值)/L5 負對照"
                     "(a crux burst collapse-起手插中段→其前接點殘差 30.0 >>1e-3 → 正確判非無縫,肇因接點確為 *->burst,證 L2 有鑑別力;b Out collapse-收尾插中段→其後接點殘差大→同;"
                     "c composability 發現:主秀 beat(皆 identity 介面)彼此對調→所有內部接點仍 0.0 無縫且各段簽章仍成立→證 identity-介面 beat 可自由排序,In 必首/Out 必尾/"
                     "burst 僅可起手為位置約束,由 a/b 界定)。**關鍵發現:①『各 beat 首尾 identity』≠『串起來真的無縫可播放』需 AC 驗(再現 X 就緒≠產線成立);"
                     "②接點去重的無損性取決於保留帶『正確 outgoing curve』的幀——緩動掛在起點幀,去重方向錯會悄悄換掉後段緩動;③identity-介面構成一個可自由排序的 beat 集合,"
                     "進出場(In/Out/burst 的 collapse 端)是唯一位置約束**。honest:beat 排序為 PROPOSAL(手感 A 類);shear beat(wobble/squash/twist)之 shear 通道不被 sample() 覆蓋,"
                     "正向序列採無 shear 的 hit/combo/charge/cascade;單一真值資產。與 anim-forge 同 HOLD"),
            CAP("sequence_composition_shear", "序列組合 shear 通道覆蓋:把 L 的接點/回切/簽章閘補到 shear 兩軸(L-2,整合/盲點閘)", "L2",
                "python3 tools/analyzer/validate_sequence_compose_shear.py", "pipeline",
                note="補 candidate L 誠實列出的 honest boundary:L 的序列組合閘用 spine_anim.sample() 做接點/回切比對,但 sample() **原本只取 "
                     "rotate/translate/scale/alpha,不取 shear** → L 的正向序列刻意只用無 shear 的 hit/combo/charge/cascade 繞過盲點。本 cap (1) 把 shear 納入 "
                     "sample()(加性:per-bone 新增 shearX/shearY,預設 0=setup identity,既有索引既有鍵的呼叫端逐位元不變);(2) 以**含 shear 的序列** "
                     "In→wobble→squash→twist→Loop→Out(三斜拉節拍全帶 shear)把 compose 的接點無縫/回切還原/in-context 簽章在 **shear 通道**釘回歸閘。"
                     "**選題理由(延續 L/G-2 整合閘精神,不加參數軸)**:L-2 不加任何生成能力,只關掉一個**已知驗證盲點** —— 讓序列組合閘對一般仿射四自由度(含兩條 shear 軸)"
                     "**全覆蓋**而非只覆蓋 5/7 通道。validate_sequence_compose_shear.py 5AC PASS:LS1 present+shear 真被驅動(composed 保有 shear timeline・sample() 現輸出 shearX/shearY・"
                     "≥1 shear 段回切後 |shearX| 峰≥5° 實測 15.27°)/LS2 crux 接點無縫含 shear(每內部接點 shear-aware 殘差 0.0<1e-3)/LS3 faithful concat 含 shear(回切逐幀還原 "
                     "含 shearX/shearY 殘差 0.0<1e-4 → 證 compose 時間平移+去重對 shear 通道亦無損)/LS4 in-context shear 簽章(回切 wobble/twist 段 shearX 阻尼振盪:繞0變號≥3+"
                     "極值遞減,且 twist 兩軸反相 shearX·shearY<0 在序列中仍成立,== 孤立 clip)/**LS5 crux 盲點負對照**:構造『5 非 shear 通道全無縫、只 shear 不連續』接點"
                     "(wobble 尾 shearX=0 → 合成 held clip 首 shearX=12°)→ (a) shear-aware diff=12.0 正確判非無縫+肇因指認;(b) **crux** 模擬擴充前盲點的 non-shear diff=0.0"
                     "(擴充前會誤判無縫)→ 證 shear 覆蓋補掉**真實**盲點;(c) 守衛 純 identity 合成接點 shear-aware diff 仍 0。**關鍵發現:①一個驗證器的『取樣器覆蓋通道數』決定"
                     "它能看見哪些不連續 —— sample() 漏 shear 使所有以它為基石的閘對 shear 盲,補通道=補所有下游閘的鑑別力;②負對照要證『擴充補掉真盲點』須在同一接點上同時跑"
                     "擴充前(non-shear)與擴充後(shear-aware)兩種 diff,證前者誤判無縫、後者正確判不連續(非只證後者會響);③稠密取樣序列套阻尼判準須先抽局部極值"
                     "(_signed_extrema),不能直接套關鍵幀版 _extrema_mags_decreasing**。honest:這是**驗證器覆蓋修正、非新生成能力**(無改任何 beat 生成/產線值,"
                     "compose 本就通道無關,本 cap 只補 sample()+閘);beat 排序仍 PROPOSAL(A 類);單一真值資產。與 anim-forge 同 HOLD"),
            CAP("sequence_loop_repeat", "序列內 Loop 重播 N 次 + loopability 不變量(L-3,整合/組合閘)", "L2",
                "python3 tools/analyzer/validate_sequence_loop.py", "pipeline",
                note="補 candidate L 的缺口(能力早在、AC 從缺,同 L/G-2 整合閘精神):compose_sequence(anims, order) 的 order **本就可重複同一 beat 名**"
                     "(如 In→Loop×N→Out)—— 這正是真實大獎序列的播放形態(進場後 Loop 重播 N 次待機、贏分滾動,再收尾),但 L 的正向序列每 beat **只出現一次**,"
                     "**從未有閘**驗過『同一支 clip 重複 N 次』路徑:重複鍵 offset 累加 / clip 接自己的**自接點**無縫(=loopability,L 只驗過**相異** beat 接點)/ "
                     "N 份重播逐幀還原同一 clip / 平鋪為**非靜止嚴格週期**。新增 gen_animations.is_loopable(把『首幀==尾幀 → 可安全重播』不變量顯式化,additive 純判斷)+ 閘。"
                     "選題理由:延續 L/L-2/G-2 刻意選整合/組合閘,不加參數軸;客觀新不變量=loopability+週期平鋪,L 涵蓋不到。"
                     "**關鍵發現(crux):compose_sequence 的時間去重會把『同時刻、不同值』的接點 collapse 成單幀 → 值不符的接點(非 loopable beat)被抹成陡坡而非真跳變,"
                     "composed 取樣恆 C0(Loop 與 tiled-In 的 wrap shrink 比皆 ≈0.1)→ loopability 只能在 clip 端點層(self-seam / is_loopable)判,不能從 composed 時間軸判。**"
                     "validate_sequence_loop.py 5AC PASS:LP1 present+loopable(Loop)+offset 累加([0.6,2.6,4.6]・總時長 7.0==In+3·Loop+Out)/LP2 crux 自接點無縫"
                     "(Loop→Loop self-seam 0.0<1e-3・compose 產物確為 C0)/LP3 periodicity(N 份去 offset 逐幀還原孤立 Loop 殘差 0.0 且彼此逐幀相同→重播不漂移)/"
                     "LP4 non-static(Loop 內部運動 5.0≥1.0,非靜止→無縫非空驗)+嚴格週期(平鋪區 sample(t)==sample(t+Loop_dur) 殘差 0.0)/"
                     "**LP5 負對照**:(a crux)In(collapsed→id)is_loopable=False・In→In 自接點 40>>・且 tiled-In 的 composed wrap 仍看似 C0(shrink 0.1)→證 loopability 須 clip 端點判;"
                     "(b)Out(id→collapsed)self-seam 25・非 loopable;(c crux 空驗守衛)合成靜止 clip is_loopable=True 且自接點 0(trivially 無縫)**但** LP4 非靜止=0→證"
                     "『光自接點無縫』不足以是有意義 loop(須同時非靜止+嚴格週期),LP4 有鑑別力。honest:重播次數 N 為 PROPOSAL(A 類);無改任何生成/產線值(is_loopable 純判斷);"
                     "單一真值資產。與 anim-forge 同 HOLD"),
            CAP("sequence_loop_c1", "自接點 C1(速度)連續 / C1-loopability(L-4,關掉 L-3 的 C0-only honest boundary)", "L2",
                "python3 tools/analyzer/validate_sequence_loop_c1.py", "pipeline",
                note="補 candidate (L-3) 誠實列出的 honest boundary:is_loopable 把『可安全重播』顯式化但**只驗 C0**(自接點值連續),"
                     "並明記『不保證 C1 速度連續(loop 重啟頓挫)』。本次關掉它:新增 gen_animations.loop_seam_velocity_gap(自接點 C1 速度不連續量,"
                     "單側有限差分 max|v_end−v_start|,additive 純函式)+ is_c1_loopable(C0 ∧ C1)+ 閘。選題:延續 L/L-2/L-3/G-2 刻意選整合/組合閘,不加參數軸。"
                     "**關鍵發現(crux):真實一次性主秀 beat(hit/combo/charge/cascade)首尾皆 setup identity → is_loopable(C0)一律 True —— L-3 的 loopability 判準會"
                     "誤把單發節拍當『可安全重播』;但它們自接點速度突變 64~167 deg/s(符號翻轉),平鋪會每份頓挫。唯 C1(自接點速度亦連續)能把真 idle-Loop"
                     "(gap≈0.19,僅光暈呼吸 scale/alpha 小殘差)與單發 beat(gap≥64)區分 → C1-loopability 嚴格更強、與 C0 獨立(真簽章常需兩獨立條件並立)。**"
                     "validate_sequence_loop_c1.py 5AC PASS:C1a present+C0 複驗+非空驗(Loop 端點速度≈15≥1)/C1b crux metric 良定義(gap 對 h∈{2e-3,1e-3,5e-4} bit-stable→"
                     "單側差分=端點切線非 artifact;且確認須在 clip 端點層量,跨 composed 接點因 L-3 時間去重被抹平恆 C0 量不到 kink)/C1c crux Loop gap 0.19<1 且 is_c1_loopable=True・"
                     "通道分解 剛體 limb rotate 精確 C1(gap~1e-12)唯一殘差=光暈呼吸(scaleY 0.024)/C1d crux C1 獨立於 C0:{Loop,hit,combo,charge,cascade} 全 is_loopable=True(C0 不能鑑別)"
                     "但 C1 gap Loop 0.19 vs 主秀 ≥64(ratio 340×)・is_c1_loopable 對主秀全 False→證 is_loopable 單獨會誤放單發 beat/C1e 負對照+空驗守衛:"
                     "(a crux)三角脈衝(C0-loopable 但注入速度 kink)gap 2.0>1 is_c1_loopable=False→抓出 is_loopable 看不到的頓挫;(b 空驗守衛)靜止 clip gap=0 trivially C1 且 is_c1_loopable=True"
                     "**但**端點速度 0<1 無運動→證 gap≤tol 必要不充分須配非靜止(呼應 LP4);(c)In 非 C0-loopable→is_c1_loopable False 由 C0 先否決。"
                     "honest:Loop 是否該被設計成完美 C1 屬美術手感(A 類,光暈呼吸殘差 kick 0.19 為已知邊界);vel_tol=1.0 為量級選擇;無改任何生成/產線值(兩新函式純量測);單一真值資產。與 anim-forge 同 HOLD"),
            CAP("sequence_crossfade", "跨 beat 混場(crossfade/overlap-mix)接點機制(M,compose 做不到的組合層軸)", "L2",
                "python3 tools/analyzer/validate_sequence_crossfade.py", "pipeline",
                note="補 candidate (L-4) 誠實列出的 honest boundary:compose_sequence(L)用**純時間平移+接點去重**串序列 → 任一時刻輸出**恰等於某一支 clip**,"
                     "**從不產生兩支 clip 的混合**;但真實大獎序列常需『前拍未收完、後拍已起』的**時間重疊交叉淡入淡出**(Spine runtime track mix),去重做不到"
                     "(值不等被抹成陡坡,見 L-3),**需真正 mix 機制**。新增 gen_animations.crossfade_pair(重疊窗內同步取樣兩 clip 做凸組合 out=(1-w)·A+w·B,"
                     "w 於窗內 0→1;smoothstep/linear 權重)+ crossfade_sequence(fold-left 折疊多拍),additive、窗外逐位元沿用原幀、僅窗內 dt 重取樣。"
                     "選題:延續 L/L-2/L-3/L-4 刻意選整合/組合閘,不加參數軸。**關鍵鑑別(crux M3):crossfade 窗內可達『兩拍當下都不在』的中間態(≈0.5A+0.5B),"
                     "compose 永遠做不到(任一時刻=某一支 clip 的值)—— 同一對 beat、同一絕對時間量 mix depth:crossfade 達 4.2≥1 而 compose=0 → 證本機制是 compose"
                     "做不到的新組合層軸而非換皮。第二 crux(M5a):窗→0 **連續退化**回 concat(sup-dist 線性於 W,sup/W 恆定 212.96→ W=0 時 0),證 concat=零窗 crossfade。**"
                     "validate_sequence_crossfade.py 5AC PASS(端到端 priors→build_spine robot→build_animations hit×combo):M1 present+structure(total=durA+durB−W・overlap=[durA−W,durA]・all_finite)/"
                     "M2 crux 端點精確+非空驗(窗首 cf==A(offsetB)・窗尾 cf==B(window) bone<1e-4・中點 cf==0.5A+0.5B 公式忠實・中點|A−B|≈8.3≥1 確在混)/"
                     "M3 crux 混場深度 compose 做不到(crossfade 4.2 vs compose 0)/M4 窗外逐位元忠實(A/B 內部 knot 殘差<1e-6 只動重疊窗)/"
                     "M5 負對照+守衛:(a crux)窗→0 線性退化 sup/W=[212.96×3] 恆定遞減(b)partition-of-unity 守衛 兩支相同靜止 hold 混場窗內恆 P 殘差 0(權重和=1,非相加)"
                     "(c)凸性守衛 窗內逐 knot 每通道 cf∈[min(A,B),max(A,B)] 越界 0。honest:重疊窗長 W/權重曲線(linear/smooth)屬美術手感(A 類);beat 排序仍 PROPOSAL;"
                     "單一真值資產。與 anim-forge 同 HOLD"),
            CAP("twist_dual_axis_shear", "生成器產反相雙軸 shear(G-4'''''',首度驅動 shearY)", "L2",
                "python3 tools/analyzer/validate_twist_gen.py", "pipeline",
                note="補 wobble(G-4')/squash(G-4'''')一路留到現在的最後一條 shear 通道 honest boundary(shearY≡0)。至今所有產 shear 的節拍"
                     "(wobble 純 shearX、squash shearX+耦合非均勻 scale)都令 shearY≡0,故 Spine local 一般仿射 M 的第二條 shear 軸(y 軸 skew)"
                     "從未被**生成器**驅動 —— 公式/閘早就吃 shy(G-4 transform_matrix_full(...,shy)/pivot_channels_affine/apply_pivots(include_shear=True)"
                     "以合成 shy 驗過管路),生成端這次才接上。gen_twist(斜扭果凍扭轉)= **反相雙軸阻尼 shear**(像擰毛巾:shearX 與 shearY 反相擺動);"
                     "shearX 同 wobble 阻尼擺(首尾 0),shearY 反號且幅度 ×TWIST_PHI(0.7,獨立通道)。關鍵幾何:兩基底夾角=90+shearY−shearX,反相時"
                     "偏離=(1+φ)|shearX| 被放大=真雙軸 shear;同相(shearX==shearY)夾角恆90°=旋轉偽裝(負對照)。build_spine --shear-pivot 端到端把"
                     "rotate/scale/shearX/**shearY** 一起繞關節 pivot 補償 → 件做用滿兩條 shear 軸的一般仿射變換而 pivot 精確不動(G-4 通用 Δ=(M−I)(O−P)"
                     "第一次被生成器產的 shearY 驅動)。validate_twist_gen.py 6AC PASS(TW1 present+dual-axis crux:shearX 峰 16°・shearY 峰 11.2°(≠0)/"
                     "TW2 兩軸各自阻尼振盪(繞0變號≥3+極值遞減)/TW3 crux 反相耦合 每內部極值 shearX·shearY<0 且夾角偏離≥8°(峰27.2°)/TW4 identity 介面 shear 首尾(0,0)/"
                     "TW5 端到端 shearY≠0 驅動下 pivot 殘差<0.015px vs 負對照(繞件中心)≈24px >1000×/TW6 負對照 同相→反相 FALSE・單軸 shearY≡0→雙軸 FALSE・"
                     "雙軸隔離 twist 獨佔 shearY・加性移除 twist 其餘逐位元不變)。twist 併入 SHEAR_CATS(shear-isolation 閘認定合法 shear 產出者)。"
                     "回歸:20 閘全綠(19 + 新 twist_gen)。honest:twist 未接 tier 幅度/count-aware(比照 wobble G-4''/G-4''');反相雙軸未接體積守恆耦合 scale"
                     "(det=cos(shearY−shearX)≠1,area 變化為已知,volume-conserving twist 為後續);單一真值資產。與 anim-forge 同 HOLD"),
            CAP("twist_tier_amplitude", "twist 反相雙軸 shear 峰隨檔位遞增(G-4''''''-tier,兩軸同比 φ 保形)", "L2",
                "python3 tools/analyzer/validate_twist_tier.py", "pipeline",
                note="補 (G-4'''''') 明列的 honest boundary:「twist 未接 tier 幅度(gen_twist(nosc=) 已備參數未接;比照 wobble G-4''/squash G-4''''')」。"
                     "twist(反相雙軸 shear)是主秀節拍,強度理應隨檔位遞增,幅度軸在**兩條** shear 軸。twist 純 shear(無 scale 通道,不在 COUPLED_SCALE_CATS),"
                     "併入 MAIN_SHOW_CATS 後 amplify_bone_tl 的 shear 迴圈以**同一 g** 同時放大 shearX 與 shearY(v'=g*v,對 0 對稱)⇒ 兩軸峰隨檔位嚴格遞增,"
                     "而 shearY/shearX ≡ −TWIST_PHI 逐檔**不變**(單一 g 對兩軸同比)、反相耦合與阻尼振盪簽章逐檔保形 = 反相雙軸幾何 scale-invariant。"
                     "crux(與 wobble tier 差異):wobble 一條 shear 軸;twist 兩條,檔位放大須**同比**才保住反相雙軸簽章(φ 比值不變)—— 獨立軸增益會使 φ 漂/翻反相。"
                     "從先驗庫→真實 build_spine robot 骨架→build_animations(tier_gains),validate_twist_tier.py 6AC PASS(TT1 present+backward-compat 每檔位 dual-channel・"
                     "base 逐位元不變/TT2 crux 兩軸峰 shearX[16,21.6,27.2,33.6]°・shearY[11.2,15.12,19.04,23.52]° 皆嚴格遞增 且 Super==base/TT3 crux φ 比值逐檔≈0.7 不變/"
                     "TT4 兩軸阻尼簽章逐檔保形(繞0變號≥3+極值遞減)/TT5 反相逐檔保形 且 夾角偏離峰[27.2,36.72,46.24,57.12]° 隨檔位遞增/"
                     "TT6 負對照 平增益→兩軸遞增 FALSE 且==base・單一-g 兩軸同比單元測(獨立軸增益負對照破 φ)・shear 隔離到 SHEAR_CATS)。"
                     "回歸:21 閘全綠(20 + 新 twist_tier)。honest:twist 未接 count-aware(扭轉段數隨檔位,gen_twist(nosc=) 已備參數未接);反相雙軸未接體積守恆耦合 scale"
                     "(volume-conserving twist 為後續);幅度/φ 為 PROPOSAL(手感 A 類);單一真值資產。與 anim-forge 同 HOLD"),
            CAP("twist_tier_count_aware", "twist 扭轉段數隨檔位遞增(G-4''''''-count,段數×幅度×φ 保形三效正交)", "L2",
                "python3 tools/analyzer/validate_twist_count.py", "pipeline",
                note="補 (G-4''''''-tier) 明列的 honest boundary:「twist 未接 count-aware(扭轉段數隨檔位,gen_twist(nosc=) 已備參數未接;比照 wobble G-4'''/squash G-4'''''-c)」。"
                     "(G-4''''''-tier) 讓 twist 兩軸 shear 峰幅度隨檔位遞增(同比 φ 不變),但各檔位仍**同樣 4 段**反相雙軸擺 —— 有『擰多狠』沒『擰幾下』。"
                     "本次補上扭轉**段數** nosc 隨檔位嚴格遞增(Super4→Mega5→Omg6→Legend7)。**幅度增益加不出段數**(段數=關鍵幀拓樸,繞0交替 shearX 極值個數,"
                     "須在 gen_twist 生成當下決定;事後 amplify 只能同比放大既有極值)→ 對 twist 檔位變體以該檔位 nosc **重生成**再疊單一-g 幅度增益。新增 TIER_TWIST_CYCLES + "
                     "twist∈COUNT_AWARE_CATS;build_animations 依 cat 路由 _count_maps。此模式同 (G-4'')wobble、(J-2)combo、(G-4'''''-c)squash,惟段數階梯各類別獨立。"
                     "**twist 獨有 crux(與 wobble count 差異):twist 有**兩條** shear 軸(反相雙軸)—— 段數重生成後兩軸各多長 nosc 個阻尼極值,每個新極值仍由 _twist_env 建構"
                     "shearY=−TWIST_PHI·shearX → φ 比值**由建構保證、與段數無關**;故段數×幅度×φ 保形三效正交可疊(每檔位不論扭幾段,φ 恆定、反相不變)。**"
                     "從先驗庫→真實 build_spine robot 骨架→build_animations(tier_gains,tier_twist_cycles),validate_twist_count.py 5AC PASS(TC1 present+backward-compat 每檔位 dual-axis・"
                     "base 恆4段逐位元不變・ttc=None 逐位元同幅度-only/TC2 crux 段數[4,5,6,7] 嚴格遞增 且每檔位每 bone φ 比值≈0.7 誤差 0.0/TC3 兩軸阻尼簽章逐檔保形+兩軸峰仍遞增+每內部極值反相/"
                     "TC4 正交 段數+平增益→段數遞增・兩軸峰不遞增・φ仍不變,增益+無段數→段數恆4・兩軸峰遞增/TC5 負對照 平段數全4→單調 FALSE・slot_reveal twist_cycles_for None 不亂加・段數只作用 twist 不外洩 wobble/squash 仍4段)。"
                     "端到端 build_spine --animate --tier-variants --shear-pivot 直出 twist__{Super,Mega,Omg,Legend}(兩軸峰隨檔位遞增 shearX16→33.6°、φ 逐檔=0.7000)。"
                     "**結構(段數)軸已在 combo/wobble/squash/twist 四通道成立;帶跨通道關係約束的類別 count-aware 要多驗一層約束(squash:體積守恆;twist:φ 比值)**。honest:volume-conserving twist(反相雙軸接體積守恆耦合 scale)為後續;"
                     "幅度/φ 為 PROPOSAL(手感 A 類);單一真值資產。與 anim-forge 同 HOLD"),
            CAP("twist_volume_conserving", "volume-conserving twist(G-4''''''-vol,反相雙軸 shear 接體積守恆等向 scale)", "L2",
                "python3 tools/analyzer/validate_twist_volume.py", "pipeline",
                note="補 twist 系列一路留到現在的最後一條 honest boundary:「反相雙軸未接體積守恆耦合 scale(det=cos(shearY−shearX)≠1 → 擰轉變面積,volume-conserving twist 為後續)」。"
                     "純 twist(shear-only)Spine local 行列式 det=cos(shearX−shearY)(兩基底夾角 90+shearY−shearX,反相被擰緊 → cos<1 → **擰轉使面積縮小**)。"
                     "本次補一條**等向**(uniform)補償 scale s=1/√cos(shearX−shearY) → 全域 det=(s·s)·cos(shearX−shearY)≡1(**擰而不變面積**):shear+scale+rotate 三通道同時作用、"
                     "塞滿一般仿射四自由度**且體積守恆**。crux:twist 補償為**等向**(scaleX==scaleY)——各向異性全由 shear 提供,scale 只做等向面積復原;與 squash(G-4'''')的**非均勻**"
                     "(scaleX≠scaleY)體積守恆機制**不同源**(squash 的 scale 本身即擠壓)。det 是 sx·sy 的約束,等向是最小(不引入額外各向異性)的守恆選擇。gen_twist(vol_conserve=) 掛 scale 通道(False 逐位元同 shear-only);"
                     "build_animations(twist_volume=)/build_spine --twist-volume 端到端,配 --shear-pivot 三通道一起繞關節 pivot 補償。validate_twist_volume.py 6AC PASS(TV1 present+shear&scale 雙通道 crux:"
                     "shearX 峰16°・shearY 峰11.2°・scale 等向/TV2 crux 體積守恆 每內部極值 |det−1|≤8.8e-5 vs 負對照 scale≡1 純 twist |det−1| 0.04–0.11 縮面積/TV3 雙軸反相阻尼簽章保形/TV4 identity 介面(shear 0,scale 1)/"
                     "TV5 端到端三通道 pivot 殘差 <0.016px vs 負對照 8–29px(含補償 scale)/TV6 負對照 無補償縮面積・等向 vs squash 非均勻隔離・twist_volume=False 逐位元同 shear-only+移除 twist 其餘不變)。"
                     "**一般仿射四自由度(rotate/非均勻 scale/shearX/shearY)+ 體積守恆全數在生成端成立;跨通道約束(twist:det≡1)由建構(等向補償)保證**。"
                     "honest:vol 僅作用 base twist(tier 變體 vol 隨檔位放大需重算補償 scale 維持 det≡1,比照 squash 耦合 amplify,為後續);幅度為 PROPOSAL(手感 A 類);單一真值資產。與 anim-forge 同 HOLD"),
            CAP("twist_volume_tier", "volume-conserving twist 接檔位差異化(G-4''''''-vol-tier,補償 scale 依放大後 shear 非線性重算)", "L2",
                "python3 tools/analyzer/validate_twist_volume_tier.py", "pipeline",
                note="補 (G-4''''''-vol) 明列的最後一條 honest boundary:「vol 僅作用 base twist;tier 變體仍 shear-only —— vol 隨檔位放大需**重算補償 scale** 維持 det≡1」。"
                     "tier 放大把兩軸 shear 同比拉大(shearX'=g·shearX、shearY'=g·shearY → 兩基底夾角偏離 Δ'=(shearX−shearY)·g)→ 真正的守恆補償變成 s'=1/√cos(g·Δ),對 g **非線性**。"
                     "amplify_bone_tl(twist_vol=True):先放大 shear、再**依放大後 shear 重算**每個 scale 極值等向 s(_recompute_twist_scale_iso)→ 全域 det≡1 於任一檔位保持,補償量隨檔位非線性遞增。"
                     "新增 VOL_TWIST_CATS={twist};build_animations(twist_volume=True,tier_gains=…) 對 twist 檔位變體路由 twist_vol 重算(段數 tier_twist_cycles 重生成的變體亦掛 vol → 段數×幅度×守恆三效正交)。"
                     "**crux(與 squash G-4''''' 耦合 amplify 對比):squash 耦合是 sy'=1/sx'(倒數、與 shear 無關);twist 補償是依放大後 shear 重算的等向 s(cos 反推、值來自 shear)—— 同為建構保證跨通道約束但不同源。**"
                     "從先驗庫→真實 build_spine robot 骨架→build_animations(tier_gains,tier_twist_cycles,twist_volume),validate_twist_volume_tier.py 6AC PASS(VTT1 present+backward-compat 每檔位 dual-channel 等向・"
                     "base 逐位元不變・Super(g=1)逐位元==base twist vol/VTT2 crux 每檔位每內部極值 |det−1|≤9.7e-5(TOL 2e-4)且峰補償 scale[1.0603,1.1169,1.2024,1.3572]・峰 shearX[16,21.6,27.2,33.6]° 皆嚴格遞增 Super==base/"
                     "VTT3 crux 負對照 逐軸線性 amplify Legend |det−1| 0.11–0.31 vs 重算 ≤8.5e-5(>1000× 鑑別)+ 重算單元測/VTT4 兩軸反相阻尼簽章+φ 比值≈0.7 逐檔不變+identity 介面 每檔位保形/"
                     "VTT5 端到端 build_spine --animate --tier-variants --twist-volume --shear-pivot 每檔位 twist__{tier} pivot 殘差 <0.33px(Legend 最強)vs 負對照 8–74px/VTT6 平增益守衛(隔離幅度軸→補償不遞增且==base vol)・非 twist 主秀變體不生 scale・移除 twist 其餘逐位元不變)。"
                     "回歸:24 閘全綠(23 + 新 twist_volume_tier)。**一般仿射四自由度 + 體積守恆已在生成端 base 與 tier 全檔位成立;跨通道約束(twist:det≡1)由建構(依放大後 shear 重算等向補償)保證於任一檔位**。"
                     "honest:幅度階梯為 PROPOSAL(手感 A 類);單一真值資產(防固化)。與 anim-forge 同 HOLD"),
            CAP("cascade_tier_ripple_count", "cascade 跨件波掃次數隨檔位遞增(J-3,第一個**跨件時序**通道的 count-aware)", "L2",
                "python3 tools/analyzer/validate_cascade_count.py", "pipeline",
                note="補 (J-3) 的 honest boundary:candidate (J) 讓 cascade 波峰**幅度**隨檔位放大,但各檔位仍是**同一道**跨件波 ——「掃得多猛」有了、「掃幾道」沒有。"
                     "本次補上波掃次數 nrip 隨檔位嚴格遞增(Super1→Mega2→Omg3→Legend4)。**與單件 count(combo/wobble/squash/twist)本質不同(crux)**:那些 count 是**單件內**極值數"
                     "(同一件連幾下,段數落在單件曲線);cascade 的 nrip 是**跨件波掃幾道**(段數落在**跨件時序**通道,cascade∈_PHASE_AWARE)——**第一個跨件的 count-aware 通道**。"
                     "整段 τ 均分 nrip 個窗,第 k 窗是一次壓縮版跨件 sweep(該件中心 c_k=(k+LEAD+p·SPAN)/nrip、包絡寬壓縮 1/nrip → 窗間隙 0.75/nrip>0 互不重疊、首尾仍 identity);"
                     "每件 pop nrip 次、整體掃 nrip 道有序波。**幅度 amplify 加不出第二道 sweep**(拓樸=gen 時決定的關鍵幀窗)→ 對 cascade 檔位變體以該檔位 nrip **重生成**再套單一-g 幅度增益(正交可疊)。"
                     "新增 TIER_CASCADE_RIPPLES + cascade_ripples_for;gen_cascade(nrip=)(nrip==1 逐位元同基礎單 sweep cascade);build_animations(tier_cascade_ripples=) 把 cascade 併入 _count_maps、"
                     "_build_beat 的 _PHASE_AWARE 分支吃 count=nrip;build_spine --tier-variants 透傳。"
                     "從先驗庫→真實 build_spine robot 骨架→build_animations(tier_gains,tier_cascade_ripples),validate_cascade_count.py 5AC PASS(X1 present+backward-compat 每檔位有 bone・"
                     "base 恆1道逐位元不變・Super 逐位元==base・tcr=None 逐位元同 (J) 幅度-only/X2 crux 波掃次數[1,2,3,4] 嚴格遞增 且每檔位所有件 pop 次數一致==nrip/"
                     "X3 crux **每一道 sweep 的各件峰時刻仍依件序嚴格遞增**且散佈≥0.6·SPAN/nrip(每道波皆有序跨件波非切碎)+每檔位首尾 setup identity+幅度峰仍遞增/"
                     "X4 正交 ripples+平增益→波掃次數遞增·峰幅不遞增,增益+無 ripples→波掃次數恆1·峰幅遞增/X5 負對照 平波掃次數全1→單調 FALSE・slot_reveal cascade_ripples_for None 不亂加·ripple 只作用 cascade 非-cascade 變體逐位元同幅度-only)。"
                     "**結構(段數)軸已在 combo/wobble/squash/twist **四個單件通道** + cascade **跨件通道** 成立;跨件 count 的簽章需多驗一層『每道 sweep 仍保跨件排序』(單件 count 無此層)**。"
                     "honest:波掃次數階梯(1–4)為 PROPOSAL(手感 A 類);單一真值資產(防固化)。與 anim-forge 同 HOLD"),
            CAP("cascade_tier_span", "cascade 跨件波散佈幅度隨檔位遞增(J-4,跨件時序通道的**幅度式**軸,與 nrip 結構軸正交)", "L2",
                "python3 tools/analyzer/validate_cascade_span.py", "pipeline",
                note="補 (J-3) 的另一條正交軸:(J-3) 讓 cascade **波掃次數** nrip 隨檔位遞增(掃幾道波=結構/拓樸軸),本次補上一道 sweep 內"
                     "**各件峰時刻的散佈幅度** span 隨檔位嚴格遞增(Super0.54→Mega0.58→Omg0.62→Legend0.66)——愈高檔位波掃**愈開**(跨件錯開愈戲劇)。"
                     "**crux(J-4 的 honest distinction)**:span 語意是「幅度」(愈大波掃愈開),照理應像 (J) 用 post-hoc 值增益 g 加大;**但不能** ——"
                     "跨件散佈活在關鍵幀的**時間位置**(峰中心 c_k=(LEAD+p·span)/nrip)**不在值**,值增益只放大 pop **深度**(scale 峰值),各件峰**時刻**不動 → 散佈不變。"
                     "故 span 雖語意屬幅度,機制上必須 gen 當下**重生成**(同 count 軸),是『**time-position 幅度** vs **value 幅度**』的分野。與 nrip **正交**(nrip 幾道波、span 一道多開,兩軸皆重生成、可同時帶入)、與 (J) 值增益**深度**軸正交(三效可疊)。"
                     "新增 TIER_CASCADE_SPAN + cascade_span_for;gen_cascade(span=)(None → CASCADE_SPAN=0.54 逐位元同基礎);build_animations(tier_cascade_span=) 對 cascade 變體以該檔位 span 重生成;"
                     "_build_beat 的 _PHASE_AWARE 分支吃 cascade_span;build_spine --tier-variants 透傳。上界 span<0.68(末件末幀 (LEAD+span+0.16)<1)。"
                     "從先驗庫→真實 build_spine robot 骨架→build_animations(tier_gains,tier_cascade_span),validate_cascade_span.py 5AC PASS(Y1 present+backward-compat 每檔位有 bone・base 逐位元不變・Super span-only 逐位元==base・tcs=None 逐位元同 (J) 幅度-only/"
                     "Y2 crux **隔離量測(nrip 固定=1)** 跨件散佈[0.54,0.58,0.62,0.66] 嚴格遞增且==宣告 span、每檔位仍依件序遞增(散佈變大不打亂波序)/Y3 每檔位仍具 cascade 簽章+首尾 setup identity 可插 Loop/"
                     "Y4 正交 (a) span+平增益→散佈遞增·深度不遞增 (b) 增益+無 span→散佈恆==base·深度遞增 (c) span⟂nrip pop 次數==nrip 不受 span 干擾·固定 nrip 下 span>base 者每道 sweep 更寬/"
                     "Y5 負對照 (a) 平 span→單調 FALSE (b) **crux honest-distinction** post-hoc 值增益 amplify(g=2.1)→深度 0.34→0.71 變大但散佈 0.5417==0.5417 **不變** 證 span 軸無法由幅度機制產生·非重生成不可 (c) slot_reveal cascade_span_for None 不亂加·span 只作用 cascade 非-cascade 變體逐位元同幅度-only)。"
                     "**跨件時序通道至此有兩條正交軸:結構(nrip,J-3)× 幅度(span,J-4);後者揭示『幅度』未必用幅度機制——時間位置的幅度需重生成**。"
                     "honest:散佈階梯(0.54–0.66)為 PROPOSAL(手感 A 類);單一真值資產(防固化)。與 anim-forge 同 HOLD"),
            CAP("cascade_dir_spatial", "cascade 跨件波方向由空間位置決定(J-5,第四條正交軸——相位來源:空間 vs 件序)", "L2",
                "python3 tools/analyzer/validate_cascade_dir.py", "pipeline",
                note="補 (J-4) 的 honest boundary:至 (J-4) 為止,cascade 各件相位恆為**件序** pi/(nvalid−1) ——波方向等於作者把件寫進 storyboard 的"
                     "**列表順序**,是任意/排版決定的,無物理意義。本次把相位的**排序鍵**換成**空間座標**:lr 左→右(bd.x 升序)/rl 右→左/"
                     "co 中心外擴(距畫布中心升序)/oc 外向內 —— 波方向變成幾何。相位值仍 rank/(nvalid−1)∈[0,1],**波形(SPAN/nrip/深度)分毫不動** → 只重排「哪件何時 pop」。"
                     "**crux(J-5 的 honest distinction)**:這不是新的幅度/段數軸,而是**同一道波的方向來源**從件序換成幾何;要證「真由空間決定」,必須在 **件序 ≠ 空間序** 的真實資產上證峰序**跟空間走不跟件序走**。"
                     "robot fixture 件序 [光暈,右手,頭,身體,左手](x=359,320,361,394,558)**非** x 排序(x 最小的右手排件序第 2)→ lr 下右手(件序 index 1)比光暈(件序 index 0)更早 pop,件序相位下不可能。"
                     "新增 _cascade_phase_of(依方向空間鍵給 rank,tie-break 件序 index)+ build_animations(cascade_dir=)/build_spine --cascade-dir{lr,rl,co,oc,auto};cascade_dir=None/\"po\" 逐位元同件序(向後相容)。tier_variants.cascade_dir_for 回 genre 建議(slot_bigwin→co,opt-in)。"
                     "從先驗庫→真實 build_spine robot 骨架→build_animations(cascade_dir),validate_cascade_dir.py 5AC PASS(Z1 present+backward-compat 每方向有 bone・po 逐位元==None・非 cascade beat 不受影響/"
                     "Z2 **crux spatial ordering** 每方向峰時刻依該方向空間鍵嚴格遞增(lr→x 升・rl→x 降・co→徑向升・oc→徑向降)/Z3 每方向仍一道有序跨件波(散佈≥0.30)+首尾 setup identity 可插 Loop/"
                     "Z4 正交 (a) dir⟂深度:同件峰 overshoot 跨方向相同(HIRES 取樣消混疊,殘差 3e-4<<1e-3)(b) dir⟂nrip:帶 ripples 各件 pop 次數==nrip (c) dir⟂span:帶 span 跨件散佈跨方向恆==span(相位集合只被排列→min/max 不變)/"
                     "Z5 負對照 (a) po 逐位元==None (b) **crux discriminator** lr 峰序==x 排序 且 ≠件序(x 最小件非件序第一件卻最先 pop)證相位來源是空間非件序 (c) 方向只作用 cascade 非-cascade 逐位元同 None (d) 未知方向字串→ValueError 輸入守衛)。"
                     "**跨件時序通道至此三條正交軸:結構(nrip,J-3)× 幅度(span,J-4)× 方向/相位來源(J-5);J-5 揭示波方向本是作者排版順序的隱含假設,改由幾何決定使波有物理意義**。"
                     "honest:方向選擇(co)為 PROPOSAL(手感 A 類);單一真值資產(防固化)。與 anim-forge 同 HOLD"),
            CAP("cascade_dir_vector", "cascade 波方向一般化為任意角投影(J-6,把 J-5 的方向軸由 4 向離散補成連續:角度/向量)", "L2",
                "python3 tools/analyzer/validate_cascade_dir_vector.py", "pipeline",
                note="承 (J-5):J-5 給方向軸 4 個**具名**取值(基數軸 lr/rl + radial co/oc)。J-6 把這**同一條方向軸由離散補成連續** —— "
                     "方向可給**角度(度)或向量 (ux,uy)**,相位依件中心在該單位向量上的**投影** x·ux+y·uy 排序。**honest distinction(勿誇大)**:"
                     "J-6 **不是**第四條正交軸(方向軸 J-5 已立);只是把其取值由「4 具名」擴成「連續角+任意向量」,機制仍是 J-5 的相位重新指派(排列),"
                     "只是**排序鍵**從 {基數軸 ±x, radial} 擴成 {任意投影角, radial}。價值=對角/垂直/任意角波,J-5 的 4 向表達不了。"
                     "lr==θ0°(k=x)/rl==θ180°(k=−x)→ 投影族的基數軸特例,逐位元相容;co/oc(radial,非線性)非投影,保留各自特例。"
                     "新增 _normalize_cascade_dir(方向規格→(kind,payload):po/proj/co/oc,角度→(cos,sin)、向量→正規化,零向量/長度≠2/bool/未知字串→ValueError)"
                     "+ _cascade_phase_of 改走統一排序鍵;build_spine --cascade-dir 吃角度/'ux,uy'(_parse_cascade_dir)。"
                     "從先驗庫→真實 build_spine robot 骨架→build_animations(cascade_dir=角度/向量),validate_cascade_dir_vector.py 5AC PASS"
                     "(V1 present+backward-compat 每新方向有 bone・**投影族含具名** 0°/180°/向量(±1,0) 逐位元==lr/rl・po==None・非 cascade 不受影響/"
                     "V2 **crux projection ordering** 每新方向峰時刻依投影鍵 x·ux+y·uy 嚴格遞增/V3 每新方向仍一道有序跨件波(散佈≥0.30)+首尾 setup identity/"
                     "V4 正交 (a)dir⟂深度(HIRES 量峰 overshoot 跨方向相同)(b)dir⟂nrip(c)dir⟂span(散佈==span)——新角/向量皆保/"
                     "V5 負對照 (a)**crux discriminator** 垂直90°峰序[3,0,4,1,2]・對角45°[3,0,1,2,4] ∉ 全部 J-5 件序集合{po,lr,rl,co,oc} 證任意角投影是真新方向非換名 "
                     "(b)連續性/端點 0°==lr・180°==rl・90° 兩者皆非(lr/rl 為投影族端點,內部為新)(c)投影≠radial:crux 峰序≠co/oc (d)輸入守衛零向量/長度≠2/bool/未知字串→ValueError)。"
                     "**方向軸至此連續化;honest:方向選擇仍 PROPOSAL(手感 A 類)、單一真值資產(防固化),與 anim-forge 同 HOLD**"),
            CAP("cascade_dir_geo", "cascade 波方向由件幾何自動導出(J-7,把 J-6 方向軸的取值來源由手感常數下推成幾何導出:質心→最遠件)", "L2",
                "python3 tools/analyzer/validate_cascade_dir_geo.py", "pipeline",
                note="承 (J-5)/(J-6):J-5 把方向立為相位來源(4 具名)、J-6 把其值連續化(角/向量),但「用哪個方向」仍是 per-genre **手感常數**"
                     "(tier_variants.TIER_CASCADE_DIR,如 slot_bigwin→co)。J-7 新增 sentinel cascade_dir=\"geo\":方向**向量由件幾何導出**"
                     "(質心→距質心最遠件的單位向量),隨資產自適應,不再寫死。**honest distinction(勿誇大)**:J-7 **不是**新正交軸,"
                     "導出後**仍走 J-6 的投影排序(同機制)**;只是把方向軸的**取值來源(provenance)從人手給換成幾何導出**(J-5 空間化→J-6 連續化→J-7 自動化,逐步移除人手指定)。"
                     "新增 derive_cascade_dir(centers,source)(centroid_farthest:確定性、無 PCA ±符號歧義)+ _normalize_cascade_dir/_cascade_phase_of 的 geo 解析(用當前 beat 有效件中心導出);build_spine --cascade-dir geo(或 geo:SOURCE)。"
                     "從先驗庫→真實 build_spine robot 骨架→build_animations(cascade_dir=\"geo\"),validate_cascade_dir_geo.py 5AC PASS"
                     "(W1 present+backward-compat geo 產每 cascade beat 有 bone・非 cascade 逐位元同 base・po==None/"
                     "W2 **crux derived projection ordering** 峰時刻依閘獨立導出的質心→最遠件投影鍵嚴格遞增(最遠件左手最後 pop)/W3 geo 仍一道有序跨件波(散佈≥0.30)+首尾 setup identity/"
                     "W4 正交 (a)dir⟂深度(geo 峰 overshoot==base,HIRES)(b)dir⟂nrip(c)dir⟂span(散佈==宣告 span)/"
                     "W5 負對照 (a)**crux data-derived discriminator** 同 cascade_dir=\"geo\" 套兩個不同幾何(robot vA≈13° vs 把頭移遠成最遠件 vB≈90°)→ 導出向量不同且波序不同,各自吻合自身幾何的質心→最遠件投影序 證方向由資料導出非常數 "
                     "(b)導出向量/波序==閘獨立重算(robot)且最遠件最後 pop (c)geo 波序≠手感常數 co(cascade_dir_for)/≠oc/≠件序 po/≠lr/≠rl (d)輸入守衛未知 source/空件/退化幾何→ValueError)。"
                     "**方向軸取值來源至此自動化;honest:source 選擇與最終手感微調仍 PROPOSAL(A 類)、單一真值資產(防固化),與 anim-forge 同 HOLD**"),
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
