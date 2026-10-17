#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D1 統一品質閘 — 驗 `assets/validator_v2.py`(spine-ai-editor 2.0 Phase D1)。

`MERGE_PLAN_2.0.md` Phase D：把 repo 的閘紀律 ＋ v1.3.0 `validator_v1` 合成**單一指令**
`validator_v2`，對一支 2.0 生成的大獎動畫一鍵輸出**全維度 pass/fail ＋ 量化指標**。
本檔是「閘的閘」：機械化證明 validator_v2 六維度(runtime / editor / loop / stiffness /
deform si / C1)**各自有牙、非恆真**，且對一支 2.0 生成大獎動畫全可檢維度 PASS(= G2 雙真值一鍵)。

**AC(全部客觀、可機讀)**：
  D1-1 unified-report   : validator_v2 對一支 **2.0 生成**(gen_lib 公開 API)大獎動畫一鍵輸出
                          六維度結構完整報告(每維 status/metrics/problems；核心四維有值)。
  D1-2 headline-G2      : 該 2.0 大獎動畫所有可檢維度 PASS —— runtime_loadable(0 error)＋
                          editor_importable(0 地雷#12)＋ loop_closure(首尾 identity)＋
                          stiffness 有限 → overall_pass=True。一條指令證「遊戲能播 **且** 編輯器能匯入 **且** 可循環」。
  D1-3 deform-truth     : validator_v2 對**真實資產 main_draw**(4 mesh×deform)→ deform_si 維度
                          **逐 mesh clean(si=0)**(藝術家真值本身過閘 = checker_validated，證維度非假性過)。
  D1-4 c1-discriminate  : idle Loop(generate_idle)→ c1_continuity **PASS**(C1-loopable)；
                          一次性大獎 beat 當 loop_anims → **FAIL**(非 C1-loopable)→ 維度能把真 Loop 與一次性 beat 分開。
  D1-5 gate-non-vacuous : 四維各一負對照 —— (a)注入末鍵 curve → editor_importable **FAIL** ＋ overall FAIL；
                          (b)破壞 scale 末鍵值 → loop_closure **FAIL**；(c)移除 root bone → runtime_loadable **FAIL**；
                          (d)mesh hull-tangle(main_draw 某 mesh 對調兩非相鄰 hull 頂點)→ deform_si **FAIL**。

用法：
  python3 validate_d1_validator_v2.py            # 跑 D1-1..D1-5，印精簡 pass/fail
  python3 validate_d1_validator_v2.py --json     # 完整 JSON 報告

退出碼 0 = 全 AC PASS；非 0 = 有 AC FAIL。
"""
from __future__ import annotations
import argparse
import copy
import json
import os
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_SKILL_ASSETS = os.path.normpath(os.path.join(_HERE, "..", "..", "skills", "spine-ai-editor", "assets"))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "mesh_gen"))
sys.path.insert(0, _SKILL_ASSETS)

import validator_v2 as VV                              # noqa: E402  受測統一閘
from gen_lib.make_beat import (generate_bigwin, generate_idle,   # noqa: E402  2.0 生成入口
                               DEMO_PARTS, IDLE_DEMO_PARTS)

_MAIN_DRAW = os.path.join(_REPO, "assets", "main_draw.json")
_MAIN_ATLAS = os.path.join(_REPO, "assets", "main_draw.atlas")


def _write_tmp(skel):
    d = tempfile.mkdtemp(prefix="d1_v2_")
    p = os.path.join(d, "skel.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(skel, f, ensure_ascii=False, indent=1)
    return p


# ----------------------------------------------------------------- 負對照 mutators
def _inject_last_frame_curve(skel):
    anim = next(iter(skel["animations"].values()))
    for tls in anim.get("bones", {}).values():
        for frames in tls.values():
            if isinstance(frames, list) and len(frames) >= 2 and isinstance(frames[-1], dict):
                frames[-1]["curve"] = 0.25
                frames[-1]["c2"] = 0.0
                frames[-1]["c3"] = 0.75
                frames[-1]["c4"] = 1.0
                return skel
    raise RuntimeError("找不到可注入末鍵 curve 的 bone timeline")


def _break_loop_closure(skel):
    anim = next(iter(skel["animations"].values()))
    for tls in anim.get("bones", {}).values():
        if "scale" in tls and isinstance(tls["scale"], list) and len(tls["scale"]) >= 2:
            tls["scale"][-1]["x"] = tls["scale"][-1].get("x", 1.0) + 0.5
            return skel
    raise RuntimeError("找不到可破壞的 scale timeline")


def _remove_root(skel):
    skel["bones"] = [b for b in skel["bones"] if b.get("name") != "root"]
    return skel


def _tangle_a_mesh(skel):
    """把 skeleton 某個 mesh attachment 的兩個非相鄰 hull 頂點對調 → 製造 tangle(deform_si 負對照)。"""
    skins = skel["skins"]
    skin = skins["default"] if isinstance(skins, dict) else skins[0]["attachments"]
    for _slot, atts in skin.items():
        for _k, att in atts.items():
            if isinstance(att, dict) and att.get("type") == "mesh" and att.get("hull"):
                h, v = att["hull"], att["vertices"]
                i, j = 1, h // 2
                v[2*i], v[2*i+1], v[2*j], v[2*j+1] = v[2*j], v[2*j+1], v[2*i], v[2*i+1]
                return skel
    raise RuntimeError("找不到帶 hull 的 mesh attachment")


# ----------------------------------------------------------------- AC
def run_all():
    res = {}

    # ---- 生成一支 2.0 大獎動畫(gen_lib 公開 API) ----
    big, big_anim = generate_bigwin(DEMO_PARTS, beat="cascade")
    big_path = _write_tmp(big)
    rep = VV.validate_v2(big_path)
    dims = rep["dimensions"]
    core = ("runtime_loadable", "editor_importable", "loop_closure", "stiffness")

    # ---- D1-1 unified report 結構完整 ----
    needed = core + ("deform_si", "c1_continuity")
    struct_ok = all(
        k in dims and all(f in dims[k] for f in ("status", "metrics", "problems"))
        for k in needed)
    core_have_val = (
        "errors" in dims["runtime_loadable"]["metrics"]
        and "problem_count" in dims["editor_importable"]["metrics"]
        and "problem_count" in dims["loop_closure"]["metrics"]
        and len(dims["stiffness"]["metrics"]["per_anim"]) >= 1)
    res["D1-1_unified_report"] = (
        struct_ok and core_have_val and callable(getattr(VV, "validate_v2", None)),
        {"dimensions_present": list(dims.keys()),
         "beat": big_anim, "stiffness": dims["stiffness"]["metrics"]["per_anim"]})

    # ---- D1-2 headline:2.0 大獎全可檢維 PASS(= G2 一鍵) ----
    res["D1-2_headline_G2"] = (
        rep["overall_pass"]
        and all(dims[k]["status"] == VV.PASS for k in core),
        {"overall_pass": rep["overall_pass"],
         "core": {k: dims[k]["status"] for k in core},
         "extended_na": {k: dims[k]["status"] for k in ("deform_si", "c1_continuity")}})

    # ---- D1-3 deform_si 真值校準(真實資產 main_draw 逐 mesh clean) ----
    md_ok = os.path.exists(_MAIN_DRAW)
    if md_ok:
        md_rep = VV.validate_v2(_MAIN_DRAW, _MAIN_ATLAS if os.path.exists(_MAIN_ATLAS) else None,
                                check_c1=False)
        dsi = md_rep["dimensions"]["deform_si"]
        meshes = dsi["metrics"].get("meshes", [])
        all_clean = (dsi["status"] == VV.PASS and len(meshes) >= 1
                     and all(m["clean"] and m["self_intersections"] == 0 for m in meshes))
    else:
        dsi, meshes, all_clean = {"status": "NO_ASSET"}, [], False
    res["D1-3_deform_truth"] = (
        md_ok and all_clean,
        {"status": dsi.get("status"), "meshes_checked": len(meshes),
         "per_mesh": [{"name": m["name"], "si": m["self_intersections"], "clean": m["clean"],
                       "frame": m["frame"]} for m in meshes]})

    # ---- D1-4 c1 鑑別:idle Loop C1-loopable PASS vs 一次性 beat FAIL ----
    idle, _ = generate_idle(IDLE_DEMO_PARTS)
    idle_path = _write_tmp(idle)
    idle_c1 = VV.validate_v2(idle_path, loop_anims=["Loop"])["dimensions"]["c1_continuity"]
    big_c1 = VV.validate_v2(big_path, loop_anims=[big_anim])["dimensions"]["c1_continuity"]
    res["D1-4_c1_discriminate"] = (
        idle_c1["status"] == VV.PASS and big_c1["status"] == VV.FAIL,
        {"idle_loop_c1": idle_c1["status"], "idle_detail": idle_c1["metrics"].get("anims"),
         "oneshot_beat_c1": big_c1["status"], "oneshot_detail": big_c1["metrics"].get("anims")})

    # ---- D1-5 四維各一負對照 ----
    # (a) 末鍵 curve → editor FAIL + overall FAIL
    rc = VV.validate_v2(_write_tmp(_inject_last_frame_curve(copy.deepcopy(big))))
    a_caught = (rc["dimensions"]["editor_importable"]["status"] == VV.FAIL
                and not rc["overall_pass"])
    # (b) 破壞 loop 閉合 → loop FAIL
    rb = VV.validate_v2(_write_tmp(_break_loop_closure(copy.deepcopy(big))))
    b_caught = rb["dimensions"]["loop_closure"]["status"] == VV.FAIL
    # (c) 移除 root → runtime FAIL
    rr = VV.validate_v2(_write_tmp(_remove_root(copy.deepcopy(big))))
    c_caught = rr["dimensions"]["runtime_loadable"]["status"] == VV.FAIL
    # (d) mesh hull-tangle(main_draw)→ deform_si FAIL
    if md_ok:
        md = json.loads(open(_MAIN_DRAW, encoding="utf-8").read())
        rd = VV.validate_v2(_write_tmp(_tangle_a_mesh(md)), check_c1=False)
        dsi_bad = rd["dimensions"]["deform_si"]
        d_caught = (dsi_bad["status"] == VV.FAIL
                    and any(m["self_intersections"] > 0 for m in dsi_bad["metrics"].get("meshes", [])))
        tangle_si = max((m["self_intersections"] for m in dsi_bad["metrics"].get("meshes", [])),
                        default=0)
    else:
        d_caught, tangle_si = False, None
    res["D1-5_gate_non_vacuous"] = (
        a_caught and b_caught and c_caught and d_caught,
        {"neg_lastframe_curve_editor_fail": a_caught,
         "neg_open_loop_loop_fail": b_caught,
         "neg_no_root_runtime_fail": c_caught,
         "neg_mesh_tangle_deform_fail": d_caught, "tangle_max_si": tangle_si})

    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "D1 unified validator_v2: runtime/editor/loop/stiffness/deform_si/C1 one command",
        "subject": {"beat": big_anim, "overall_pass_on_2.0_bigwin": rep["overall_pass"]},
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
        print(json.dumps({"overall_pass": report["overall_pass"], "subject": report["subject"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
