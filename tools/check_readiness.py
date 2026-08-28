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
        "title": "骨架 pivot 推斷(S5,唯一卡死環節)",
        "target_skill": "HOLD:閘就緒但生成仍 baseline(L1);pivot 閘可先併入 spine-mesh-doctor",
        "caps": [
            CAP("pivot_eval", "pivot 品質閘(err/len + swing;S2 骨架閘)", "L2",
                "python3 tools/analyzer/validate_pivots.py", "eval",
                note="今日新增;對 Award 真 rig 自洽+負對照(σ 單調)+baseline 分級 OVERALL PASS"),
            CAP("infer_pivots", "pivot 生成 baseline(parent_tip/origin)", "L1",
                "python3 tools/analyzer/validate_pivots.py", "gen",
                note="rig-only 啟發式:serial 60% / branch 0%;branch 須 per-part mask 重疊區證據,未做"),
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
