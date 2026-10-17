#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D1 統一品質閘 — 證 `assets/validator_v2.py` 把全維度收斂成單一報告且非恆真(spine-ai-editor 2.0 Phase D1)。

MERGE_PLAN_2.0 Phase D：B/C 階段各自把生成器 + 它的專屬閘搬進 skill(gen_lib.make_beat / sequence /
mesh / rig，各配 validate_b*/c*)。D1 把這些分散的驗收面**合成單一 `validator_v2`**——對一支 2.0 生成的
大獎動畫，**一條指令輸出全維度 pass/fail + 量化指標**(runtime 可載入 / editor 可匯入 / loop 閉合 /
stiffness / deform si / C1)。

**驗的是什麼(為何這個 chunk 有價值)**：
  2.0 併完 B/C 後，驗收一支生成動畫要記住 validator_v0(schema)、validator_v1(editor+loop+stiffness)、
  gen_lib.mesh.deform_si_gate(mesh 變形)、gen_animations.is_c1_loopable(C1) 各自怎麼跑、怎麼解讀。
  D1 把它們編排成**一張報告**，並把 validator_v1 合併的「runtime 載不進來(schema/cx)」與「editor 匯入
  crash(末鍵 curve 地雷 #12)」**兩語意乾淨切開** = G2「遊戲能播 **且** 編輯器能匯入」的機讀落點。
  validator_v2 **不新寫檢查邏輯**，只編排既有(各自已有負對照)的閘——故本 gate 重點在證明
  **編排正確 + 各維度仍非恆真(真會因不乾淨而 FAIL)**。

**AC(全部客觀、可機讀)**：
  D1-1 unified-report   : 對 **gen_lib 公開 API 生成**的大獎 beat，一次 `validate_v2()` 回傳含 6 維度的
                          單一報告；硬閘(runtime/editor/loop)PASS、stiffness 有限、deform_si=na(region beat)、
                          c1 回報(一次性 beat 預期非 C1)、overall PASS。
  D1-2 runtime|editor   : **語意切分非恆真**——(a)注入末鍵 curve → editor_importable **FAIL** 但
                          runtime_loadable **仍 PASS**(乾淨切分);(b)G1 strip 後 editor 回 PASS;
                          (c)注入 cx>1(非末鍵)→ runtime_loadable **FAIL**(bezier runtime 解錯)。
  D1-3 loop-closure     : 生成 beat loop_closure PASS;破壞首尾 identity → loop_closure **FAIL**(開環被抓)。
  D1-4 deform-si        : 對 **main_draw(4 真實美術 mesh + deform)** deform_si **PASS**(真值校準:藝術家
                          mesh 套真實位移場 si=0);**負對照** 把某 mesh hull 兩頂點對調造 tangle → deform_si **FAIL**;
                          region beat → deform_si **na**(無 mesh)。
  D1-5 c1+overall       : idle Loop `is_c1_loopable`=True → `--require-c1 Idle_Loop` c1 升硬閘 **PASS** + overall PASS;
                          一次性大獎 beat 預設 c1=info(不害 overall)、但 `--require-c1` 指到它 → c1 **FAIL** + overall FAIL;
                          **overall 非恆真**:缺頂層 key 的壞 skeleton → runtime_loadable FAIL → overall FAIL。

用法：
  python3 validate_d1_validator_v2.py           # 跑 D1-1..D1-5,印精簡 pass/fail
  python3 validate_d1_validator_v2.py --json     # 完整 JSON 報告

退出碼 0 = 全 AC PASS;非 0 = 有 AC FAIL。
"""
from __future__ import annotations
import argparse
import copy
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILL_ASSETS = os.path.join(_REPO, "skills", "spine-ai-editor", "assets")
for _p in (_HERE, os.path.join(_REPO, "tools", "mesh_gen"), _SKILL_ASSETS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import validator_v2 as V2                               # noqa: E402
from gen_lib.make_beat import generate_bigwin, DEMO_PARTS           # noqa: E402
from gen_lib.sequence import compose_idle_loop, IDLE_DEMO_PARTS     # noqa: E402

_MAIN_DRAW = os.path.join(_REPO, "assets", "main_draw.json")
_MAIN_ATLAS = os.path.join(_REPO, "assets", "main_draw.atlas")


# ----------------------------------------------------------------- helpers
def _write_tmp(skel, name="skeleton.json"):
    d = tempfile.mkdtemp(prefix="d1v2_")
    p = os.path.join(d, name)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(skel, f, ensure_ascii=False, indent=1)
    return p


def _v2(skel_or_path, **kw):
    """validate_v2 on a dict(寫暫存)或 path。"""
    path = skel_or_path if isinstance(skel_or_path, str) else _write_tmp(skel_or_path)
    return V2.validate_v2(path, **kw)


def _inject_last_frame_curve(skel):
    """把某 bone timeline 的**末鍵**塞 curve(模擬未拔末鍵 → 地雷 #12 editor crash,runtime OK)。"""
    for anim in skel["animations"].values():
        for tls in anim.get("bones", {}).values():
            for frames in tls.values():
                if isinstance(frames, list) and len(frames) >= 2 and isinstance(frames[-1], dict):
                    frames[-1].update(curve=0.25, c2=0.0, c3=0.75, c4=1.0)
                    return skel
    raise RuntimeError("找不到可注入末鍵 curve 的 bone timeline")


def _inject_cx_out_of_range(skel):
    """把某 bone timeline **非末鍵**的 curve(cx)設成 >1(bezier runtime 解錯 → runtime_loadable)。"""
    for anim in skel["animations"].values():
        for tls in anim.get("bones", {}).values():
            for frames in tls.values():
                if isinstance(frames, list) and len(frames) >= 3 and isinstance(frames[0], dict):
                    frames[0].update(curve=1.8, c2=0.0, c3=0.9, c4=1.0)   # cx=curve=1.8 超界
                    return skel
    raise RuntimeError("找不到可注入 cx 超界的 bone timeline")


def _break_loop_closure(skel):
    """把某 bone scale 末鍵值改掉(首尾不再一致 → 開環)。"""
    for anim in skel["animations"].values():
        for tls in anim.get("bones", {}).values():
            if "scale" in tls and isinstance(tls["scale"], list) and len(tls["scale"]) >= 2:
                tls["scale"][-1]["x"] = tls["scale"][-1].get("x", 1.0) + 0.5
                return skel
    raise RuntimeError("找不到可破壞的 scale timeline")


def _tangle_a_mesh(md):
    """把 main_draw 某個 unweighted mesh 的 hull 兩非相鄰頂點座標對調 → 造拓樸 tangle。
    回傳 (mutated_skeleton, slot, name)。"""
    skins = md["skins"]
    skins = skins if isinstance(skins, dict) else {s["name"]: s["attachments"] for s in skins}
    for _skin, atts in skins.items():
        for slot, slot_atts in atts.items():
            for key, att in slot_atts.items():
                if att.get("type") != "mesh":
                    continue
                v, u = att.get("vertices", []), att.get("uvs", [])
                if len(v) != len(u):        # 只處理 unweighted(vertices 可直接 reshape)
                    continue
                h = att.get("hull", 0)
                if h < 4:
                    continue
                i, j = 0, h // 2            # 兩非相鄰 hull 頂點
                # 交換第 i / j 個頂點的 (x,y)
                att["vertices"][2*i], att["vertices"][2*j] = att["vertices"][2*j], att["vertices"][2*i]
                att["vertices"][2*i+1], att["vertices"][2*j+1] = att["vertices"][2*j+1], att["vertices"][2*i+1]
                return md, slot, att.get("name", key)
    raise RuntimeError("main_draw 找不到可 tangle 的 unweighted mesh")


# ----------------------------------------------------------------- AC
def run_all():
    res = {}

    # ---- 生成素材(全經 gen_lib 公開 API)----
    big, big_anim = generate_bigwin(DEMO_PARTS, beat="cascade")     # 一次性大獎 beat(region 占位)
    idle, idle_anim = compose_idle_loop(IDLE_DEMO_PARTS, repeats=2)  # loopable idle

    # ---- D1-1 unified-report ----
    rep = _v2(big)
    dims = rep["dimensions"]
    d11 = (set(dims) == {"runtime_loadable", "editor_importable", "loop_closure",
                         "stiffness", "deform_si", "c1_continuity"}
           and dims["runtime_loadable"]["status"] == "pass"
           and dims["editor_importable"]["status"] == "pass"
           and dims["loop_closure"]["status"] == "pass"
           and dims["stiffness"]["status"] == "info"
           and isinstance(dims["stiffness"]["metric"].get(big_anim), (int, float))
           and dims["deform_si"]["status"] == "na"
           and dims["c1_continuity"]["status"] == "info"
           and rep["overall_pass"] is True)
    res["D1-1_unified_report"] = (d11, {
        "dimensions": sorted(dims),
        "runtime": dims["runtime_loadable"]["status"],
        "editor": dims["editor_importable"]["status"],
        "loop": dims["loop_closure"]["status"],
        "stiffness": dims["stiffness"]["metric"],
        "deform_si": dims["deform_si"]["status"],
        "c1": dims["c1_continuity"]["status"],
        "overall": rep["overall_pass"],
    })

    # ---- D1-2 runtime | editor 語意切分非恆真 ----
    neg_curve = _v2(_inject_last_frame_curve(copy.deepcopy(big)))
    editor_caught = (neg_curve["dimensions"]["editor_importable"]["status"] == "fail")
    runtime_still_ok = (neg_curve["dimensions"]["runtime_loadable"]["status"] == "pass")
    # G1 strip 後 editor 回 PASS
    fixed = copy.deepcopy(big)
    _inject_last_frame_curve(fixed)
    import curve_tools as ct
    for a in fixed["animations"].values():
        ct.strip_last_frame_curves(a)
    editor_fixed = (_v2(fixed)["dimensions"]["editor_importable"]["status"] == "pass")
    # cx 超界 → runtime FAIL
    neg_cx = _v2(_inject_cx_out_of_range(copy.deepcopy(big)))
    cx_caught = (neg_cx["dimensions"]["runtime_loadable"]["status"] == "fail")
    d12 = editor_caught and runtime_still_ok and editor_fixed and cx_caught
    res["D1-2_runtime_vs_editor_split"] = (d12, {
        "lastframe_curve: editor_fail": editor_caught,
        "lastframe_curve: runtime_still_pass": runtime_still_ok,
        "after_G1_strip: editor_pass": editor_fixed,
        "cx_out_of_range: runtime_fail": cx_caught,
    })

    # ---- D1-3 loop-closure 非恆真 ----
    base_loop_ok = (dims["loop_closure"]["status"] == "pass")
    neg_loop = _v2(_break_loop_closure(copy.deepcopy(big)))
    loop_caught = (neg_loop["dimensions"]["loop_closure"]["status"] == "fail"
                   and any("open loop" in p for p in neg_loop["dimensions"]["loop_closure"]["problems"]))
    d13 = base_loop_ok and loop_caught
    res["D1-3_loop_closure"] = (d13, {
        "generated_beat_loop_pass": base_loop_ok,
        "broken_loop_caught": loop_caught,
        "sample_problems": neg_loop["dimensions"]["loop_closure"]["problems"][:2],
    })

    # ---- D1-4 deform-si(真值校準 + 負對照 + na)----
    md_rep = _v2(_MAIN_DRAW, atlas_path=_MAIN_ATLAS)
    md_deform = md_rep["dimensions"]["deform_si"]
    real_pass = (md_deform["status"] == "pass" and md_deform.get("mesh_count") == 4
                 and all(m["clean"] for m in md_deform["meshes"]))
    # 負對照:tangle 一個 mesh
    md = json.loads(open(_MAIN_DRAW, encoding="utf-8").read())
    md, tslot, tname = _tangle_a_mesh(md)
    tangled = _v2(md)["dimensions"]["deform_si"]
    tangle_caught = (tangled["status"] == "fail"
                     and any((not m["clean"]) for m in tangled["meshes"]))
    # region beat → na
    na_ok = (dims["deform_si"]["status"] == "na")
    d14 = real_pass and tangle_caught and na_ok
    res["D1-4_deform_si"] = (d14, {
        "main_draw_4mesh_clean": real_pass,
        "mesh_count": md_deform.get("mesh_count"),
        "tangle_caught": tangle_caught,
        "tangled_mesh": "{}/{}".format(tslot, tname),
        "worst_si_after_tangle": max((m.get("self_intersections") or 0)
                                     for m in tangled["meshes"]),
        "region_beat_na": na_ok,
    })

    # ---- D1-5 c1 + overall 組合非恆真 ----
    idle_req = _v2(idle, require_c1=[idle_anim])
    idle_c1_pass = (idle_req["dimensions"]["c1_continuity"]["status"] == "pass"
                    and idle_req["overall_pass"] is True)
    # 一次性 beat:預設 c1=info 不害 overall;require-c1 指到它 → fail + overall fail
    big_default_info = (dims["c1_continuity"]["status"] == "info" and rep["overall_pass"] is True)
    big_req = _v2(big, require_c1=[big_anim])
    big_req_fail = (big_req["dimensions"]["c1_continuity"]["status"] == "fail"
                    and big_req["overall_pass"] is False)
    # overall 非恆真:壞 skeleton
    broken = {"skeleton": {"spine": "3.8.75"}, "bones": [], "slots": [],
              "animations": {}}   # 缺 skins 等頂層 key
    broken_rep = _v2(broken)
    broken_caught = (broken_rep["dimensions"]["runtime_loadable"]["status"] == "fail"
                     and broken_rep["overall_pass"] is False)
    d15 = idle_c1_pass and big_default_info and big_req_fail and broken_caught
    res["D1-5_c1_and_overall"] = (d15, {
        "idle_require_c1_pass_and_overall": idle_c1_pass,
        "idle_c1_loopable": idle_req["dimensions"]["c1_continuity"]["per_anim"].get(idle_anim, {}),
        "bigwin_default_c1_info_overall_pass": big_default_info,
        "bigwin_require_c1_fails_and_overall_fail": big_req_fail,
        "broken_skeleton_overall_fail": broken_caught,
    })

    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "D1 validator_v2: 全維度合成單一品質閘(runtime/editor/loop/stiffness/deform_si/C1)",
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
        print(json.dumps({"overall_pass": report["overall_pass"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
