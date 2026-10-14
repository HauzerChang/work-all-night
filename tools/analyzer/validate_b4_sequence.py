#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B4 閘 — `gen_lib.sequence` 序列組合(compose / crossfade / loop)→ v1.3.0 `validator_v1`
(spine-ai-editor 2.0 Phase B4)。

B2(`validate_b2_genlib.py`)證「**單一** beat 經 skill 入口」能過 validator_v1;B1 的洞見明記
**G1 的真正風險在序列 compose/crossfade,不在單 beat**(`_bez` 只 curve `frames[:-1]`,單 beat 末鍵恆乾淨)。
B4 把 repo 的**跨 beat 序列組合**(`compose_sequence` / `crossfade_sequence` + C1 判準)抽成 skill 入口
`skills/spine-ai-editor/assets/gen_lib/sequence.py`,並在**序列層**機械化驗 G2 雙真值 + 相異 beat 接點 C1 +
loop 閉合 + stiffness,把 MERGE_PLAN 指名的「G1 真正戰場」關掉(以實測結論取代 B1 的假設)。

**驗的是什麼(為何這個 chunk 有價值)**:
  序列層是「X 就緒 ≠ 產線成立」在組合層的實例:各 beat 單獨過閘 ≠ 串成序列仍過閘。本閘證:
   · compose 與 crossfade 的**多 beat 序列**皆過 validator_v1(0 error,含末鍵 curve 地雷 #12 檢查)=
     遊戲能播 **且** 編輯器能匯入;並**實測**序列層末鍵 curve 數(G1 拔幾條)=**B1 假設的答案**。
   · 相異 beat 接點 C1:純接續 C0 無縫但 C1 不連續(離散節拍 kink 15~114);crossfade+smoothstep 把接點
     kink **消為 0**(閉式)→ 相異 beat 接點 C1 連續閘通過。
   · 首尾可接 Loop:Loop 重複序列首==尾 → validator_v1 loop 閉合 0 問題;Loop beat `is_c1_loopable`。
   · stiffness 不升:crossfade(接點平滑)stiffness **低於** compose(不升反降)。
   · 負對照(閘非恆真):手動注入接點末鍵 curve → validator_v1 抓到 editor-crash;破壞 Loop 閉合 → 抓到開環。
  Cocos/viewer 實機載入 = 使用者端(排程 scope 邊界),本閘用 spine-webgl 無頭等價(validator_v1)替代。

**AC(全部客觀、可機讀)**:
  B4-1 entrypoint+schema : `sequence.compose_bigwin_sequence` / `crossfade_bigwin_sequence` 經**公開 API**
                           產出 schema 合法完整 Spine JSON(單一 composed animation;validator_v1 底層 v0
                           0 schema error;非臨時腳本)。
  B4-2 seq-editor-import : compose 與 crossfade 的**多 beat 序列**皆過 validator_v1 **0 error**(含末鍵 curve
                           地雷 #12 檢查)→ 序列層遊戲能播 **且** 編輯器能匯入;並報序列層末鍵 curve 數
                           (G1 拔幾條,**實測 = 0**:compose 去重丟乾淨末幀、crossfade 重取樣成純線性)。
  B4-3 distinct-seam-c1  : 純接續(compose 介面)`is_c1_continuous_sequence`==**False**(C0 全 0 無縫但每接點
                           C1 kink ≥10,非因 C0);crossfade+**smoothstep** `is_c1_crossfade_sequence`==**True**
                           (每接點閉式 kink 0);**linear** 斜坡==**False**(證 C1 斜坡才是鑑別子)。
  B4-4 loopable+stiffness: Loop beat `is_c1_loopable`==True;**Loop×repeats** 序列 validator_v1 loop 閉合
                           **0 問題**(首尾可接 Loop);crossfade 序列 stiffness ≤ compose 序列 stiffness
                           (接點平滑 → stiffness 不升)。
  B4-5 roundtrip+g1+neg  : `write_sequence` 寫檔→重讀→validator_v1 0 error(端到端到「可載入檔」);
                           入口 **G1 wired**:注入接點末鍵 curve → validator_v1 **抓到** editor-crash,
                           預設(apply_g1=True)→ 乾淨;破壞 Loop 閉合 → loop 閘**抓到**。證閘非恆真。

用法:
  python3 validate_b4_sequence.py            # 跑 B4-1..B4-5,印精簡 pass/fail + 指標
  python3 validate_b4_sequence.py --json     # 完整 JSON 報告

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

import gen_animations as G          # noqa: E402  序列函式(C1 判準)
import sequence as SEQ              # noqa: E402  B4 skill 入口(gen_lib)
from sequence import IDLE_DEMO_PARTS, STANDARD_BIGWIN_ORDER   # noqa: E402

_VALIDATOR_V1 = os.path.join(_SKILL_ASSETS, "validator_v1.py")
_PARTS = IDLE_DEMO_PARTS
_ORDER = list(STANDARD_BIGWIN_ORDER)
_XF = 0.15


# ----------------------------------------------------------------- 跑 validator_v1
def _run_validator_v1(skel, loop_anim=None, mutator=None):
    """寫檔 → 呼叫真正的 validator_v1.py(subprocess)→ 解析輸出。
    回傳 {valid, errors[], loop_problems[], stiffness{}, raw}。
    loop_anim=None → 不指定 --loop-anims(validator 對所有動畫做 loop 檢查);給名 → 只檢該支。
    mutator:寫檔前破壞性改動(負對照)。"""
    data = copy.deepcopy(skel)
    if mutator is not None:
        mutator(data)
    tmpdir = tempfile.mkdtemp(prefix="b4seq_")
    jp = os.path.join(tmpdir, "skeleton.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    cmd = [sys.executable, _VALIDATOR_V1, jp, "--metric"]
    if loop_anim is not None:
        cmd += ["--loop-anims", loop_anim]
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


def _count_lastkey_curves(anim):
    n = 0
    for sec in ("bones", "slots"):
        for chans in anim.get(sec, {}).values():
            for frames in chans.values():
                if isinstance(frames, list) and frames and isinstance(frames[-1], dict) \
                   and any(k in frames[-1] for k in ("curve", "c2", "c3", "c4")):
                    n += 1
    return n


def _count_any_curves(anim):
    n = 0
    for sec in ("bones", "slots"):
        for chans in anim.get(sec, {}).values():
            for frames in chans.values():
                for fr in frames:
                    if isinstance(fr, dict) and any(k in fr for k in ("curve", "c2", "c3", "c4")):
                        n += 1
    return n


def _inject_junction_last_frame_curve(data, aname):
    """把某 bone timeline 末鍵塞 curve(模擬序列接點 outgoing curve 被推到末鍵 → 地雷 #12)。"""
    anim = data["animations"][aname]
    for tls in anim.get("bones", {}).values():
        for frames in tls.values():
            if isinstance(frames, list) and len(frames) >= 2 and isinstance(frames[-1], dict):
                frames[-1].update({"curve": 0.25, "c2": 0.0, "c3": 0.75, "c4": 1.0})
                return
    raise RuntimeError("找不到可注入末鍵 curve 的 bone timeline(負對照前提壞了)")


def _break_loop_closure(data, aname):
    """把某 bone scale/rotate/shear timeline 末鍵值改掉(首尾不再一致 → 開環)。"""
    anim = data["animations"][aname]
    for tls in anim.get("bones", {}).values():
        for key in ("rotate", "scale", "shear"):
            if key in tls:
                frames = tls[key]
                if isinstance(frames, list) and len(frames) >= 2 and isinstance(frames[-1], dict):
                    first_key = next(iter(frames[-1].keys() - {"time"}), None) or "angle"
                    frames[-1][first_key] = frames[-1].get(first_key, 0.0) + 5.0
                    return
    raise RuntimeError("找不到可破壞的 timeline(負對照前提壞了)")


# ----------------------------------------------------------------- AC
def run_all():
    # ---- 建一次 beat library,compose / crossfade 共用(效率 + 同一真值)----
    skel_scaffold, anims = SEQ.build_beat_library(_PARTS, beats=list(dict.fromkeys(_ORDER)))

    comp_skel, comp_name = SEQ.compose_bigwin_sequence(_PARTS, order=_ORDER)
    xf_skel, xf_name = SEQ.crossfade_bigwin_sequence(_PARTS, order=_ORDER, xf=_XF)
    idle_skel, idle_name = SEQ.compose_idle_loop(_PARTS, repeats=2)

    # 大獎序列非 loopable(In→…→Out,一次性進出場)→ **不**傳 --loop-anims:validator_v1 的 metric 與
    # loop 檢查共用 loop_anims 過濾(見 validator_v1.py L71),傳不存在的名會連 metric 一起跳過。故大獎序列
    # 不過濾(取得 stiffness;其「首尾不閉合」的 loop 警告是 warning 非 error、且一次性序列本就不該閉合,不 gate)。
    v_comp = _run_validator_v1(comp_skel)
    v_xf = _run_validator_v1(xf_skel)
    v_idle = _run_validator_v1(idle_skel, loop_anim=idle_name)   # idle 序列 → 檢 loop 閉合

    comp_anim = comp_skel["animations"][comp_name]
    xf_anim = xf_skel["animations"][xf_name]

    # ---- B4-1 entrypoint + schema ----
    nb = len(comp_anim.get("bones", {}))
    schema_errs = [e for e in v_comp["errors"]
                   if any(k in e for k in ("missing", "not found", "unknown", "parse failed"))]
    b41 = (nb >= 2 and not schema_errs
           and callable(getattr(SEQ, "compose_bigwin_sequence", None))
           and callable(getattr(SEQ, "crossfade_bigwin_sequence", None))
           and len(comp_skel["animations"]) == 1 and len(xf_skel["animations"]) == 1)

    # ---- B4-2 sequence editor-import 0 error + 實測序列層末鍵 curve 數 ----
    comp_lastkey = _count_lastkey_curves(comp_anim)
    xf_lastkey = _count_lastkey_curves(xf_anim)
    comp_anycurve = _count_any_curves(comp_anim)      # compose 內部保有各 beat bezier(非末位)
    xf_anycurve = _count_any_curves(xf_anim)          # crossfade 純線性(0)
    b42 = (v_comp["valid"] and len(v_comp["errors"]) == 0
           and v_xf["valid"] and len(v_xf["errors"]) == 0
           and comp_lastkey == 0 and xf_lastkey == 0)

    # ---- B4-3 distinct-beat junction C1 ----
    concat_seams = G.sequence_seam_gaps(anims, _ORDER)
    concat_c0_max = max(s["c0_gap"] for s in concat_seams)
    concat_c1_min = min(s["c1_gap"] for s in concat_seams)
    concat_is_c1 = G.is_c1_continuous_sequence(anims, _ORDER)              # 應 False
    xf_is_c1_smooth = G.is_c1_crossfade_sequence(anims, _ORDER, _XF, "smoothstep")   # 應 True
    xf_is_c1_linear = G.is_c1_crossfade_sequence(anims, _ORDER, _XF, "linear")       # 應 False
    xf_kinks = G.crossfade_junction_kinks(anims, _ORDER, _XF, "smoothstep")
    xf_kink_max = max(k["max"] for k in xf_kinks)
    b43 = ((not concat_is_c1) and concat_c0_max <= 1e-6 and concat_c1_min >= 10.0
           and xf_is_c1_smooth and (not xf_is_c1_linear) and xf_kink_max <= 1e-6)

    # ---- B4-4 loopable endpoints + stiffness 不升 ----
    loop_beat_c1 = G.is_c1_loopable(anims["Loop"])
    idle_loop_problems = len(v_idle["loop_problems"])
    comp_stiff = v_comp["stiffness"].get(comp_name)
    xf_stiff = v_xf["stiffness"].get(xf_name)
    stiff_ok = (comp_stiff is not None and xf_stiff is not None
                and comp_stiff == comp_stiff and xf_stiff == xf_stiff          # not NaN
                and xf_stiff <= comp_stiff + 1e-9)
    b44 = (loop_beat_c1 and v_idle["valid"] and idle_loop_problems == 0 and stiff_ok)

    # ---- B4-5 roundtrip + G1 wired + 負對照 ----
    # (a) write_sequence 寫檔 → 重讀 → validator_v1 0 error(端到端到可載入檔)
    tf = tempfile.mkdtemp(prefix="b4rt_")
    out = os.path.join(tf, "seq_xf.json")
    SEQ.write_sequence(_PARTS, out, mode="crossfade", xf=_XF)
    reread = json.loads(open(out, encoding="utf-8").read())
    rt_name = next(iter(reread["animations"].keys()))
    rt = _run_validator_v1(reread, loop_anim=idle_name)
    roundtrip_ok = rt["valid"] and len(rt["errors"]) == 0
    try:
        os.remove(out); os.rmdir(tf)
    except OSError:
        pass

    # (b) G1 wired:注入接點末鍵 curve → validator_v1 抓到 editor-crash
    neg_curve = _run_validator_v1(comp_skel,
                                  mutator=lambda d: _inject_junction_last_frame_curve(d, comp_name))
    curve_caught = (not neg_curve["valid"]) and any(
        ("最後一鍵帶 curve" in e) or ("AIOOBE" in e) for e in neg_curve["errors"])
    # apply_g1=False 仍乾淨(此家族結構上 editor-safe,拔 0 條;證「拔 0」是實測非未跑)
    raw_skel, raw_name = SEQ.compose_bigwin_sequence(_PARTS, order=_ORDER, apply_g1=False)
    raw_lastkey = _count_lastkey_curves(raw_skel["animations"][raw_name])
    g1_clean_default = (comp_lastkey == 0 and raw_lastkey == 0)   # 入口 G1 wired(預設套)+ 結構本就乾淨

    # (c) 破壞 Loop 閉合 → loop 閘抓到開環
    neg_loop = _run_validator_v1(idle_skel, loop_anim=idle_name,
                                 mutator=lambda d: _break_loop_closure(d, idle_name))
    loop_caught = any("open loop" in p for p in neg_loop["loop_problems"])

    b45 = roundtrip_ok and curve_caught and g1_clean_default and loop_caught

    res = {
        "B4-1_entrypoint_schema": (b41, {
            "compose_api_callable": callable(getattr(SEQ, "compose_bigwin_sequence", None)),
            "crossfade_api_callable": callable(getattr(SEQ, "crossfade_bigwin_sequence", None)),
            "anim_bones": nb, "single_composed_anim": len(comp_skel["animations"]) == 1,
            "schema_errors": schema_errs}),
        "B4-2_sequence_editor_import": (b42, {
            "compose_valid": v_comp["valid"], "compose_errors": v_comp["errors"][:2],
            "crossfade_valid": v_xf["valid"], "crossfade_errors": v_xf["errors"][:2],
            "compose_lastkey_curves": comp_lastkey, "crossfade_lastkey_curves": xf_lastkey,
            "compose_internal_curves": comp_anycurve, "crossfade_internal_curves": xf_anycurve,
            "note": "G1 在序列層拔 0 條(compose 去重丟乾淨末幀、crossfade 重取樣純線性)"}),
        "B4-3_distinct_seam_c1": (b43, {
            "concat_c0_max": round(concat_c0_max, 6), "concat_c1_min": round(concat_c1_min, 3),
            "concat_is_c1_continuous": concat_is_c1,
            "crossfade_smoothstep_is_c1": xf_is_c1_smooth,
            "crossfade_linear_is_c1": xf_is_c1_linear,
            "crossfade_smoothstep_kink_max": round(xf_kink_max, 6),
            "concat_seams": [{"seam": s.get("seam") or s.get("i"),
                              "c1": round(s["c1_gap"], 2)} for s in concat_seams]}),
        "B4-4_loopable_stiffness": (b44, {
            "loop_beat_is_c1_loopable": loop_beat_c1,
            "idle_loop_problems": idle_loop_problems,
            "compose_stiffness": comp_stiff, "crossfade_stiffness": xf_stiff,
            "crossfade_not_higher": (xf_stiff <= comp_stiff + 1e-9)
                                    if (comp_stiff is not None and xf_stiff is not None) else None}),
        "B4-5_roundtrip_g1_non_vacuous": (b45, {
            "write_roundtrip_valid": roundtrip_ok, "roundtrip_anim": rt_name,
            "neg_junction_last_frame_curve_caught": curve_caught,
            "entry_default_g1_clean": g1_clean_default, "raw_apply_g1_false_lastkey": raw_lastkey,
            "neg_open_loop_caught": loop_caught,
            "neg_curve_errors": neg_curve["errors"][:2],
            "neg_loop_problems": neg_loop["loop_problems"][:2]}),
    }
    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "B4 gen_lib.sequence: multi-beat compose/crossfade/loop → v1.3.0 validator_v1 (G1 真正戰場)",
        "entry": "skills/spine-ai-editor/assets/gen_lib/sequence.py :: "
                 "compose_bigwin_sequence / crossfade_bigwin_sequence / compose_idle_loop / write_sequence",
        "order": _ORDER,
        "metrics": {"compose_stiffness": comp_stiff, "crossfade_stiffness": xf_stiff,
                    "compose_lastkey_curves": comp_lastkey, "crossfade_lastkey_curves": xf_lastkey,
                    "crossfade_smoothstep_kink_max": round(xf_kink_max, 6),
                    "concat_c1_min": round(concat_c1_min, 3)},
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
        print(json.dumps({"overall_pass": report["overall_pass"], "metrics": report["metrics"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
