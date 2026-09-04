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
            CAP("priors_beats_wiring", "主秀 hit/reveal 接進已驗證 genre 先驗庫(0f→E)", "L2",
                "python3 tools/analyzer/validate_priors_beats.py",
                "pipeline", note="genre_priors beat 加 `cat` 明確宣告運動基元;slot_bigwin In=reveal 現身、"
                            "slot_reveal open=reveal/hit=hit → build_spine --animate 對真實 genre 直接輸出主秀簽章。"
                            "5AC(cat有效+覆蓋率仍1.0/In reveal簽章/open+hit簽章/尾identity可串接/剝cat退回intro的鑑別負對照)"
                            "全 PASS。cat 只改基元選擇不動關鍵字 → validate_priors 覆蓋率不受影響"),
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
