#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B2 閘 — `gen_lib` 大獎節拍生成入口 → v1.3.0 `validator_v1`(spine-ai-editor 2.0 Phase B2)。

B1(`validate_v2_bridge.py`)證明了「repo 的**一支** cascade beat 臨時組 skeleton」能過 validator_v1。
B2 把那條流程抽成**可重用的 skill 入口** `skills/spine-ai-editor/assets/gen_lib/make_beat.py`
(`generate_bigwin` / `write_bigwin`),並涵蓋 4 種大獎單件運動基元 **cascade / pop / wobble / twist**。
本閘證明:**透過 skill 入口**(非臨時腳本)產出的每一種 beat,都能過 editor 真值閘,且寫檔可 round-trip。

**驗的是什麼(為何這個 chunk 有價值)**:
  B2 把「用 skill 生成 → 雙真值驗收」固化成一條**對外契約**——不再每次手搭 skeleton。
  AC 涵蓋 4 beat 類型 + 寫檔 round-trip + G1 機械化 + 負對照(閘非恆真)。
  Cocos/viewer 實機載入 = 使用者端(排程 scope 邊界),本閘用 spine-webgl 無頭等價(validator_v1)替代。

**AC(全部客觀、可機讀)**:
  B2-1 entrypoint+schema : `gen_lib.generate_bigwin(DEMO_PARTS,"cascade")` 經**公開 API** 產出 schema 合法
                           完整 Spine JSON(validator_v1 底層 v0 檢查 0 schema error;非臨時腳本)。
  B2-2 four-beat-import  : cascade / pop / wobble / twist **四種** 皆經同一入口生成 → validator_v1
                           **0 error**(含末鍵 curve 地雷 #12 檢查)→ 遊戲能播 **且** 編輯器能匯入。
  B2-3 loop-closure      : 四 beat(皆首尾 identity 的 pop/shear 波)loop 閉合 **0 問題**(可接 Loop)。
  B2-4 stiffness         : validator_v1 --metric 對每種 beat 回報有限 stiffness,併入輸出。
  B2-5 roundtrip+g1      : `write_bigwin` 寫檔 → 重讀 → validator_v1 **0 error**(證 skill 流程端到端到「可載入檔」);
                           且入口 **G1 wired**:apply_g1=False 時注入末鍵 curve → validator_v1 **抓到** editor-crash,
                           apply_g1=True(入口預設)→ 修好。另破壞首尾 identity(開環)→ loop 閉合 **抓到**。
                           證此閘非恆真,且 G1 確實是入口的一環。

用法:
  python3 validate_b2_genlib.py            # 跑 B2-1..B2-5,印精簡 pass/fail + 各 beat stiffness
  python3 validate_b2_genlib.py --json     # 完整 JSON 報告

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
sys.path.insert(0, os.path.join(_SKILL_ASSETS, "gen_lib"))

import make_beat as MB              # noqa: E402  B2 skill 入口(gen_lib)
import curve_tools as ct           # noqa: E402  G1 工具(負對照用)

_VALIDATOR_V1 = os.path.join(_SKILL_ASSETS, "validator_v1.py")
_BEATS = ("cascade", "pop", "wobble", "twist")


# ----------------------------------------------------------------- 跑 validator_v1
def _run_validator_v1(skel, loop_anim, mutator=None):
    """寫檔 → 呼叫真正的 validator_v1.py(subprocess)→ 解析輸出。
    回傳 {valid, errors[], loop_problems[], stiffness{}, raw}。mutator:寫檔前破壞性改動(負對照)。"""
    data = copy.deepcopy(skel)
    if mutator is not None:
        mutator(data)
    tmpdir = tempfile.mkdtemp(prefix="b2genlib_")
    jp = os.path.join(tmpdir, "skeleton.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    cmd = [sys.executable, _VALIDATOR_V1, jp, "--metric", "--loop-anims", loop_anim]
    p = subprocess.run(cmd, capture_output=True, text=True)
    errors, loops, stiff, in_metric = [], [], {}, False
    for line in p.stdout.splitlines():
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
    try:
        os.remove(jp); os.rmdir(tmpdir)
    except OSError:
        pass
    return {"valid": p.returncode == 0, "errors": errors,
            "loop_problems": loops, "stiffness": stiff, "raw": p.stdout}


def _inject_last_frame_curve(data, aname):
    """把某 bone timeline 末鍵塞 curve(模擬未拔末鍵 → 地雷 #12)。"""
    anim = data["animations"][aname]
    for tls in anim.get("bones", {}).values():
        for frames in tls.values():
            if isinstance(frames, list) and len(frames) >= 2 and isinstance(frames[-1], dict):
                frames[-1].update({"curve": 0.25, "c2": 0.0, "c3": 0.75, "c4": 1.0})
                return
    raise RuntimeError("找不到可注入末鍵 curve 的 bone timeline(負對照前提壞了)")


def _break_loop_closure(data, aname):
    """把某 bone scale 或 shear timeline 末鍵值改掉(首尾不再一致 → 開環)。"""
    anim = data["animations"][aname]
    for tls in anim.get("bones", {}).values():
        for key in ("scale", "shear"):
            if key in tls:
                frames = tls[key]
                if isinstance(frames, list) and len(frames) >= 2 and isinstance(frames[-1], dict):
                    first_key = next(iter(frames[-1].keys() - {"time"}), None) or "x"
                    frames[-1][first_key] = frames[-1].get(first_key, 1.0) + 0.5
                    return
    raise RuntimeError("找不到可破壞的 scale/shear timeline(負對照前提壞了)")


# ----------------------------------------------------------------- AC
def run_all():
    # ---- 透過公開 API 生成四種 beat(各過入口 G1)----
    gen = {}   # beat -> (skel, anim_name)
    for b in _BEATS:
        gen[b] = MB.generate_bigwin(MB.DEMO_PARTS, beat=b)

    v1 = {b: _run_validator_v1(skel, aname) for b, (skel, aname) in gen.items()}

    # ---- B2-1 entrypoint+schema(cascade,經公開 API)----
    cas_skel, cas_name = gen["cascade"]
    nb = len(cas_skel["animations"][cas_name].get("bones", {}))
    ns = len(cas_skel["animations"][cas_name].get("slots", {}))
    schema_errs = [e for e in v1["cascade"]["errors"]
                   if any(k in e for k in ("missing", "not found", "unknown", "parse failed"))]
    b21 = (nb >= 2 and ns >= 1 and not schema_errs
           and callable(getattr(MB, "generate_bigwin", None)))

    # ---- B2-2 four-beat editor-import 0 error ----
    per_beat_err = {b: v1[b]["errors"] for b in _BEATS}
    b22 = all(v1[b]["valid"] and len(v1[b]["errors"]) == 0 for b in _BEATS)

    # ---- B2-3 loop closure(四 beat)----
    per_beat_loop = {b: v1[b]["loop_problems"] for b in _BEATS}
    b23 = all(len(v1[b]["loop_problems"]) == 0 for b in _BEATS)

    # ---- B2-4 stiffness(四 beat 皆有限)----
    stiff = {}
    for b in _BEATS:
        _, aname = gen[b]
        stiff[b] = v1[b]["stiffness"].get(aname)
    b24 = all(s is not None and s == s and s != float("inf") for s in stiff.values())

    # ---- B2-5 roundtrip + G1 wired + 負對照 ----
    # (a) write_bigwin 寫檔 → 重讀 → validator_v1 0 error(端到端到「可載入檔」)
    tf = tempfile.mkdtemp(prefix="b2rt_")
    out = os.path.join(tf, "bigwin_cascade.json")
    MB.write_bigwin(MB.DEMO_PARTS, out, beat="cascade")
    reread = json.loads(open(out, encoding="utf-8").read())
    rt = _run_validator_v1(reread, "cascade")
    roundtrip_ok = rt["valid"] and len(rt["errors"]) == 0
    try:
        os.remove(out); os.rmdir(tf)
    except OSError:
        pass

    # (b) G1 wired:apply_g1=False 生成後注入末鍵 curve → validator_v1 抓到 editor-crash
    raw_skel, raw_name = MB.generate_bigwin(MB.DEMO_PARTS, beat="cascade", apply_g1=False)
    neg_curve = _run_validator_v1(raw_skel, raw_name,
                                  mutator=lambda d: _inject_last_frame_curve(d, raw_name))
    curve_caught = (not neg_curve["valid"]) and any(
        ("最後一鍵帶 curve" in e) or ("AIOOBE" in e) for e in neg_curve["errors"])
    # apply_g1=True(入口預設)→ 無末鍵 curve(入口 G1 這一步確實在跑)
    def_skel, def_name = MB.generate_bigwin(MB.DEMO_PARTS, beat="cascade")   # 預設 apply_g1=True
    def_clean = not any(
        isinstance(fr, list) and fr and isinstance(fr[-1], dict)
        and any(k in fr[-1] for k in ("curve", "c2", "c3", "c4"))
        for sec in ("bones", "slots")
        for tls in def_skel["animations"][def_name].get(sec, {}).values()
        for fr in tls.values())

    # (c) 破壞首尾 identity(開環)→ loop 閉合抓到
    neg_loop = _run_validator_v1(cas_skel, cas_name,
                                 mutator=lambda d: _break_loop_closure(d, cas_name))
    loop_caught = any("open loop" in p for p in neg_loop["loop_problems"])

    b25 = roundtrip_ok and curve_caught and def_clean and loop_caught

    res = {
        "B2-1_entrypoint_schema": (b21, {
            "public_api_callable": callable(getattr(MB, "generate_bigwin", None)),
            "anim_bones": nb, "anim_slots": ns, "schema_errors": schema_errs}),
        "B2-2_four_beat_import_zero_error": (b22, {
            "beats": list(_BEATS), "errors_per_beat": per_beat_err}),
        "B2-3_loop_closure": (b23, {"loop_problems_per_beat": per_beat_loop}),
        "B2-4_stiffness_reported": (b24, {"stiffness_per_beat": stiff}),
        "B2-5_roundtrip_g1_non_vacuous": (b25, {
            "write_roundtrip_valid": roundtrip_ok,
            "neg_last_frame_curve_caught": curve_caught,
            "entry_default_g1_clean": def_clean,
            "neg_open_loop_caught": loop_caught,
            "neg_curve_errors": neg_curve["errors"][:2],
            "neg_loop_problems": neg_loop["loop_problems"][:2]}),
    }
    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "B2 gen_lib: packaged skill entry (cascade/pop/wobble/twist) → v1.3.0 validator_v1",
        "entry": "skills/spine-ai-editor/assets/gen_lib/make_beat.py :: generate_bigwin / write_bigwin",
        "beats": {b: {"anim": gen[b][1], "stiffness": stiff[b]} for b in _BEATS},
        "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="完整 JSON 報告")
    a = ap.parse_args()
    report = run_all()
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"overall_pass": report["overall_pass"], "beats": report["beats"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
