#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B1 橋接閘 — 把 repo 的確定性生成器輸出跑過 v1.3.0 `validator_v1`(spine-ai-editor 2.0 Phase B1)。

這是 `MERGE_PLAN_2.0.md` Phase B 的**前提 chunk**:先機械化證明「repo 生成的一支動畫」能無痛
通過使用者既有 skill 的編輯器真值閘(validator_v1),G1(末鍵 curve 必拔)、G2(雙真值驗收)兩條硬性
護欄可自動化,之後才談把更多生成器(B2→…)搬進 skill。

**驗的是什麼(為何這個 chunk 有價值)**:
  repo 的 69 閘只驗「runtime(spine-webgl)可載入」;v1.3.0 的 validator_v1 另驗
  「**Spine editor 可匯入**(末鍵 curve = 地雷 #12 AIOOBE crash)+ loop 閉合 + stiffness」。
  B1 證明:把 repo 最單純的 cascade big-win beat →(G1)strip_last_frame_curves →(G2)validator_v1,
  **0 error、loop 閉合無問題、stiffness 可量**。這把兩套品質閘的接縫**機械化**成一條可重跑的閘。

**AC(全部客觀、可機讀)**:
  B1-1 generate+schema : repo 生成器產出一支 cascade beat,組成 schema 合法的完整 Spine JSON
                         (validator_v1 底層 v0 schema 檢查 0 error)。
  B1-2 editor-import   : 過 G1(strip_last_frame_curves)後,validator_v1 **0 error**
                         (含末鍵 curve = 地雷 #12 檢查)→ 證遊戲能播 **且** 編輯器能匯入(G2)。
  B1-3 loop-closure    : validator_v1 對 cascade 的 loop 閉合檢查 **0 問題**(首尾 identity,pop 波可接 Loop)。
  B1-4 stiffness       : validator_v1 --metric 回報 cascade 的 stiffness(有限數值),併入輸出。
  B1-5 gate-non-vacuous: **負對照**——(a)注入末鍵 curve → validator_v1 **抓到** editor-crash error,
                         再 strip → 修好;(b)破壞首尾 identity(開環)→ validator_v1 loop 閉合 **抓到** 開環。
                         證此閘非恆真(真的會因為 repo 輸出不乾淨而 FAIL)。

用法:
  python3 validate_v2_bridge.py            # 跑 B1-1..B1-5,印精簡 pass/fail + stiffness
  python3 validate_v2_bridge.py --json     # 完整 JSON 報告(含 validator_v1 原始輸出摘要)
  python3 validate_v2_bridge.py --keep      # 保留產生的 skeleton.json(預設跑完刪 temp)

退出碼 0 = 全 AC PASS;非 0 = 有 AC FAIL。
"""
from __future__ import annotations
import argparse
import copy
import json
import os
import re
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_SKILL_ASSETS = os.path.normpath(os.path.join(_HERE, "..", "..", "skills", "spine-ai-editor", "assets"))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "mesh_gen"))
sys.path.insert(0, _SKILL_ASSETS)

import gen_animations as G          # noqa: E402  repo 生成庫
import curve_tools as ct            # noqa: E402  v1.3.0 的 G1 工具(strip_last_frame_curves)

_VALIDATOR_V1 = os.path.join(_SKILL_ASSETS, "validator_v1.py")


# ----------------------------------------------------------------- fixture / 生成
def build_cascade_skeleton():
    """用真實拆件(robot_parts.psd)件序生成**最單純**的 cascade big-win beat,
    組成 schema 合法的完整 Spine 3.8 skeleton JSON(bones + slots + default skin + animations)。

    回傳 (skeleton_dict, cascade_anim_name)。每個部位件給一個 region 占位 attachment,
    讓 anim 引用到的 bone/slot 全部存在(validator_v0 引用完整性過關)。
    """
    from analyze_target import analyze
    sb = analyze("assets/robot_parts.psd", "slot_bigwin")["3_motion_storyboard"]
    loop = next(b for b in sb["beats"] if b["beat"] == "Loop")
    parts = [{"part": p["part"], "role": p["role"], "action": "主秀"} for p in loop["parts"]]
    storyboard = {"beats": [{"beat": "cascade", "desc": "跨件錯開波主秀(B1 最單純)", "parts": parts}]}

    bones = [{"name": "root"}]
    slots = []
    skin = {}
    for i, p in enumerate(parts):
        bn = "b_" + G.safe(p["part"])
        sn = p["part"]                                   # anim 的 slot 名用原件名(見 probe)
        bones.append({"name": bn, "parent": "root", "x": 100.0 + 30 * i, "y": 80.0})
        slots.append({"name": sn, "bone": bn, "attachment": sn})
        skin[sn] = {sn: {"width": 32, "height": 32}}     # region 占位(type 省略=region)

    skeleton = {
        "skeleton": {"hash": "b1bridge", "spine": "3.8.75", "x": 0, "y": 0,
                     "width": 713, "height": 693, "images": "./"},
        "bones": bones,
        "slots": slots,
        "skins": {"default": skin},
        "animations": {},
    }
    # 僅帶 bones(同 validate_cascade.build_fixture);build_animations 會依 role 自動生 effect slot timeline
    gen_skel = {"skeleton": skeleton["skeleton"], "bones": bones}
    anims = G.build_animations(gen_skel, storyboard)
    skeleton["animations"] = anims
    return skeleton, "cascade"


# ----------------------------------------------------------------- 跑 validator_v1
def _run_validator_v1(skel, loop_anim, extra_json_mutator=None, keep_path=None):
    """把 skeleton 寫檔,呼叫真正的 v1.3.0 validator_v1.py(subprocess),解析其輸出。

    回傳 dict:{returncode, valid, errors[], loop_problems[], stiffness{anim:val}, raw}。
    extra_json_mutator:寫檔前對 dict 做破壞性改動(負對照用)。
    """
    data = copy.deepcopy(skel)
    if extra_json_mutator is not None:
        extra_json_mutator(data)
    tmpdir = tempfile.mkdtemp(prefix="v2bridge_")
    jp = keep_path or os.path.join(tmpdir, "skeleton.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    cmd = [sys.executable, _VALIDATOR_V1, jp, "--metric", "--loop-anims", loop_anim]
    p = subprocess.run(cmd, capture_output=True, text=True)
    out = p.stdout
    errors, loops, stiff = [], [], {}
    in_metric = False
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("[ERR ]"):
            errors.append(s[len("[ERR ]"):].strip())
        elif s.startswith("[warn] (v1 loop)"):
            loops.append(s[len("[warn] (v1 loop)"):].strip())
        elif "stiffness" in line and "---" in line:
            in_metric = True
        elif in_metric:
            m = re.match(r"^(\S+)\s+([-\d.]+)$", s)
            if m:
                try:
                    stiff[m.group(1)] = float(m.group(2))
                except ValueError:
                    pass
    if keep_path is None:
        try:
            os.remove(jp)
            os.rmdir(tmpdir)
        except OSError:
            pass
    return {"returncode": p.returncode, "valid": p.returncode == 0,
            "errors": errors, "loop_problems": loops, "stiffness": stiff, "raw": out}


# ----------------------------------------------------------------- 負對照 mutator
def _inject_last_frame_curve(data):
    """把 cascade 某條 bone timeline 的**最後一鍵**塞一個 curve(模擬未拔末鍵 → 地雷 #12)。"""
    anim = data["animations"]["cascade"]
    for tls in anim.get("bones", {}).values():
        for frames in tls.values():
            if isinstance(frames, list) and len(frames) >= 2 and isinstance(frames[-1], dict):
                frames[-1]["curve"] = 0.25
                frames[-1]["c2"] = 0.0
                frames[-1]["c3"] = 0.75
                frames[-1]["c4"] = 1.0
                return
    raise RuntimeError("找不到可注入末鍵 curve 的 bone timeline(負對照前提壞了)")


def _break_loop_closure(data):
    """把 cascade 某條 bone scale timeline 的末鍵值改掉(首尾不再一致 → 開環)。"""
    anim = data["animations"]["cascade"]
    for tls in anim.get("bones", {}).values():
        if "scale" in tls:
            frames = tls["scale"]
            if isinstance(frames, list) and len(frames) >= 2:
                frames[-1]["x"] = frames[-1].get("x", 1.0) + 0.5   # 末鍵偏離 setup identity
                return
    raise RuntimeError("找不到可破壞的 scale timeline(負對照前提壞了)")


# ----------------------------------------------------------------- AC
def run_all(keep=False):
    skel, cname = build_cascade_skeleton()

    # G1:拔末鍵 curve(機械化護欄);回報拔了幾條(單 beat 下 repo _bez 只 curve frames[:-1],預期 0)
    stripped = 0
    for a in skel["animations"].values():
        stripped += ct.strip_last_frame_curves(a)

    keep_path = os.path.join(_HERE, "..", "..", "specs", "b1_bridge_skeleton.json") if keep else None
    if keep_path:
        os.makedirs(os.path.dirname(keep_path), exist_ok=True)
    main_res = _run_validator_v1(skel, cname, keep_path=keep_path)

    # 負對照(a):注入末鍵 curve → validator_v1 應抓到 editor-crash error
    neg_curve = _run_validator_v1(skel, cname, extra_json_mutator=_inject_last_frame_curve)
    curve_caught = (not neg_curve["valid"]) and any(
        ("最後一鍵帶 curve" in e) or ("AIOOBE" in e) for e in neg_curve["errors"])
    # 證 G1 能修:注入後再 strip → 回到 0 error
    def _inject_then_strip(d):
        _inject_last_frame_curve(d)
        for a in d["animations"].values():
            ct.strip_last_frame_curves(a)
    neg_curve_fixed = _run_validator_v1(skel, cname, extra_json_mutator=_inject_then_strip)

    # 負對照(b):破壞首尾 identity → validator_v1 loop 閉合應抓到開環
    neg_loop = _run_validator_v1(skel, cname, extra_json_mutator=_break_loop_closure)
    loop_caught = any("open loop" in p for p in neg_loop["loop_problems"])

    # ---- AC 判定 ----
    nbones = len(skel["animations"][cname].get("bones", {}))
    nslots = len(skel["animations"][cname].get("slots", {}))
    res = {}
    res["B1-1_generate_schema"] = (
        nbones >= 2 and nslots >= 1 and not any("missing top-level" in e or "parse failed" in e
                                                for e in main_res["errors"]),
        {"anim_bones": nbones, "anim_slots": nslots,
         "schema_errors": [e for e in main_res["errors"]
                           if "missing" in e or "not found" in e or "unknown" in e]})
    res["B1-2_editor_import_zero_error"] = (
        main_res["valid"] and len(main_res["errors"]) == 0,
        {"validator_v1_valid": main_res["valid"], "errors": main_res["errors"],
         "last_frame_curves_stripped_by_G1": stripped})
    res["B1-3_loop_closure"] = (
        len(main_res["loop_problems"]) == 0,
        {"loop_problems": main_res["loop_problems"]})
    cst = main_res["stiffness"].get(cname)
    res["B1-4_stiffness_reported"] = (
        cst is not None and cst == cst and cst != float("inf"),
        {"stiffness": main_res["stiffness"]})
    res["B1-5_gate_non_vacuous"] = (
        curve_caught and neg_curve_fixed["valid"] and loop_caught,
        {"neg_last_frame_curve_caught": curve_caught,
         "neg_curve_then_strip_valid": neg_curve_fixed["valid"],
         "neg_open_loop_caught": loop_caught,
         "neg_curve_errors": neg_curve["errors"][:3],
         "neg_loop_problems": neg_loop["loop_problems"][:3]})

    overall = all(v[0] for v in res.values())
    report = {
        "overall_pass": overall,
        "chunk": "B1 bridge: repo cascade beat → v1.3.0 validator_v1 (G1+G2 mechanized)",
        "beat": {"name": cname, "bones": nbones, "slots": nslots,
                 "stiffness": cst, "G1_last_frame_curves_stripped": stripped},
        "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()},
    }
    if keep_path:
        report["kept_skeleton"] = os.path.normpath(keep_path)
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="完整 JSON 報告")
    ap.add_argument("--keep", action="store_true", help="保留產生的 skeleton.json 到 specs/")
    a = ap.parse_args()
    report = run_all(keep=a.keep)
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"overall_pass": report["overall_pass"], "beat": report["beat"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
