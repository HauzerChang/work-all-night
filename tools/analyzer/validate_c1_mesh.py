#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C1 閘 — `gen_lib.mesh` mesh 生成 + 變形自交閘(spine-ai-editor 2.0 Phase C1)。

B2/B3/B4 把 repo 的**動畫生成**(beat / 繞關節 pivot / 序列)抽成 skill 入口;C1 把 repo 的
**mesh 生成引擎**(`generate_mesh_v2` strip/delaunay/boundary-dense)+ **變形自交評估器**
(`deform_eval` 真實位移場轉移)抽成 skill 入口 `skills/spine-ai-editor/assets/gen_lib/mesh.py`,
成為**結構軸的 mesh 分支**:v1.3.0 只能**檢查**既有 mesh,C1 讓 2.0 能**生成**耐變形 mesh 並自驗。

**驗的是什麼(為何這個 chunk 有價值)**:
  「件沒有 mesh(只能整塊剛體位移、無法彎折/飄動)」是 structural 限制的一種;C1 證經公開 API:
   · 對**窗簾件**(main_draw,高瘦 row-convex)生成 **strip mesh** → 套**真實動畫 deform 位移場**
     (總位移最大幀,真值校準,**非** stress_field)→ **self-intersections = 0 / flips = 0**
     (= AC「真實 deform si=0」,遊戲拉扯下不撕裂)。
   · 對**機器人件**(Award,weighted 無 deform timeline)生成合法 mesh(auto 選 delaunay/boundary-dense)
     → 靜態拓樸乾淨 + IoU 達藝術家基準(真實位移場不適用 weighted → 退回 setup 靜態拓樸檢查)。
   · 閘**真值校準**:repo `benchmark_real` 證真實 4 美術 mesh × 9 動畫逐幀 si/flips/degen 全 0
     → 生成 mesh 過閘是**與真值一致**,非假性通過。
   · 閘**非恆真**:把生成 mesh 的兩個非相鄰 hull 頂點對調造 tangle → si 閘**抓到**(si>0)。

**AC(全部客觀、可機讀)**:
  C1-1 entrypoint+schema : `mesh.generate_part_mesh` / `deform_si_gate` / `generate_and_gate_part`
                           經**公開 API** 對窗簾件產 **strip** mesh(schema 合法、unweighted
                           len(vertices)==len(uvs)、hull∈(0,nv])、對機器人件產合法 mesh。
  C1-2 real-deform si=0  : **curtain_left 與 curtain_right** 生成 strip mesh,套**真實 deform 位移場**
                           → has_real_deform=True、frame 非 None、**self_intersections==0 且
                           triangle_flips==0 且 degenerate==0**(clean)、area_ratio 有限(~1.14)。
  C1-3 iou>=baseline     : 2 窗簾 + 3 機器人件,生成 mesh 覆蓋率 IoU ≥ 藝術家基準 − 0.03。
  C1-4 gate-calibration  : (a) repo `benchmark_real(main_draw)` 真實 4 mesh × 9 動畫逐幀
                           worst si/flips/degen 全 0(_checker_validated=True)→ 閘與真值一致(非假性過);
                           (b) 機器人件(weighted 無 deform)→ has_real_deform=False → 退回靜態拓樸檢查。
  C1-5 gate-non-vacuous  : 生成 mesh 對調兩非相鄰 hull 頂點造 tangle → (a) 窗簾經**真實 deform 閘**
                           si>0(clean=False) (b) 機器人經**靜態拓樸閘** si>0 → 證閘有牙。

用法:
  python3 validate_c1_mesh.py            # 跑 C1-1..C1-5,印精簡 pass/fail + 指標
  python3 validate_c1_mesh.py --json     # 完整 JSON 報告

退出碼 0 = 全 AC PASS;非 0 = 有 AC FAIL。
"""
from __future__ import annotations
import argparse
import copy
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILL_ASSETS = os.path.join(_REPO, "skills", "spine-ai-editor", "assets")
sys.path.insert(0, os.path.join(_SKILL_ASSETS, "gen_lib"))
sys.path.insert(0, os.path.join(_REPO, "tools", "mesh_gen"))

import mesh as M              # noqa: E402  C1 skill 入口(gen_lib)
import deform_eval as DE      # noqa: E402  真值校準(benchmark_real)


def _p(rel):
    return os.path.join(_REPO, rel)


_CURTAINS = [
    ("assets/main_draw.json", "assets/main_draw.atlas", "assets/main_draw.png",
     "image/curtain_left", "image/curtain_left"),
    ("assets/main_draw.json", "assets/main_draw.atlas", "assets/main_draw.png",
     "image/curtain_right", "image/curtain_right"),
]
_ROBOTS = [
    ("assets/Award.json", "assets/Award.atlas", "assets/Award.png", "機器人拆件/光暈", "機器人拆件/光暈"),
    ("assets/Award.json", "assets/Award.atlas", "assets/Award.png", "機器人拆件/左手", "機器人拆件/左手"),
    ("assets/Award.json", "assets/Award.atlas", "assets/Award.png", "機器人拆件/身體", "機器人拆件/身體"),
]


def _gen_mesh(spec):
    """(skeleton, atlas, png, slot, name) → (mesh, mask, skeleton_path)。經 skill 公開 API。"""
    skj, atl, png, slot, name = spec
    mask, crop = M._crop_region(_p(atl), _p(png), name)
    mesh = M.generate_part_mesh(crop)       # 公開 API
    return mesh, mask, _p(skj)


def _swap_two_hull_verts(mesh):
    """把生成 mesh 兩個非相鄰 hull 頂點位置對調 → 製造 tangle(負對照)。"""
    bad = copy.deepcopy(mesh)
    h = bad["hull"]
    v = bad["vertices"]
    i, j = 1, h // 2                          # 非相鄰(間隔 ≥ h/2-1)
    v[2 * i], v[2 * i + 1], v[2 * j], v[2 * j + 1] = v[2 * j], v[2 * j + 1], v[2 * i], v[2 * i + 1]
    return bad


def run_all():
    # ---- C1-1 entrypoint + schema ----
    api_ok = all(callable(getattr(M, fn, None))
                 for fn in ("generate_part_mesh", "deform_si_gate", "generate_and_gate_part"))
    cl_mesh, cl_mask, cl_sk = _gen_mesh(_CURTAINS[0])
    rb_mesh, rb_mask, rb_sk = _gen_mesh(_ROBOTS[2])          # 身體
    cl_schema_ok, cl_schema_probs = M.mesh_is_schema_valid(cl_mesh)
    rb_schema_ok, rb_schema_probs = M.mesh_is_schema_valid(rb_mesh)
    cl_strip = (cl_mesh.get("_mode") == "strip")
    cl_unweighted = (len(cl_mesh["vertices"]) == len(cl_mesh["uvs"]))
    c11 = (api_ok and cl_schema_ok and rb_schema_ok and cl_strip and cl_unweighted)

    # ---- C1-2 real-deform si=0(headline)----
    curtain_gates = []
    for spec in _CURTAINS:
        m, _, skp = _gen_mesh(spec)
        g = M.deform_si_gate(m, skp, spec[3], spec[4])
        curtain_gates.append((spec[3], g))
    c12 = all(g["has_real_deform"] and g["frame"] is not None
              and g["self_intersections"] == 0 and g["triangle_flips"] == 0
              and g["degenerate"] == 0 and g["clean"]
              and g["area_ratio"] == g["area_ratio"]        # not NaN
              for _, g in curtain_gates)

    # ---- C1-3 iou >= artist baseline - margin ----
    iou_reports = []
    for grp, specs in (("curtain", _CURTAINS), ("robot", _ROBOTS)):
        for spec in specs:
            rep = M.generate_and_gate_part(_p(spec[0]), _p(spec[1]), _p(spec[2]),
                                           spec[3], spec[4], iou_margin=0.03)
            iou_reports.append((grp, spec[3], rep["iou"]))
    c13 = all(r["pass"] for _, _, r in iou_reports)

    # ---- C1-4 gate calibration(真值一致 + weighted 退回靜態)----
    bench = DE.benchmark_real(_p("assets/main_draw.json"))
    worst = bench["_worst_across_all"]
    checker_validated = bench["_checker_validated"]
    robot_gate = M.deform_si_gate(rb_mesh, rb_sk, _ROBOTS[2][3], _ROBOTS[2][4])
    c14 = (checker_validated
           and worst["self_intersections"] == 0 and worst["triangle_flips"] == 0
           and worst["degenerate"] == 0
           and (robot_gate["has_real_deform"] is False))

    # ---- C1-5 gate non-vacuous(tangle 被抓)----
    bad_curtain = _swap_two_hull_verts(cl_mesh)
    bad_c_gate = M.deform_si_gate(bad_curtain, cl_sk, _CURTAINS[0][3], _CURTAINS[0][4])
    bad_robot = _swap_two_hull_verts(rb_mesh)
    bad_r_gate = M.deform_si_gate(bad_robot, rb_sk, _ROBOTS[2][3], _ROBOTS[2][4])
    c15 = (bad_c_gate["has_real_deform"] and bad_c_gate["self_intersections"] > 0
           and (not bad_c_gate["clean"])
           and (bad_r_gate["has_real_deform"] is False)
           and bad_r_gate["self_intersections"] > 0 and (not bad_r_gate["clean"]))

    res = {
        "C1-1_entrypoint_schema": (c11, {
            "api_callable": api_ok, "curtain_schema_ok": cl_schema_ok,
            "curtain_mode": cl_mesh.get("_mode"), "curtain_unweighted": cl_unweighted,
            "curtain_nv": len(cl_mesh["uvs"]) // 2, "curtain_hull": cl_mesh["hull"],
            "robot_schema_ok": rb_schema_ok, "robot_mode": rb_mesh.get("_mode"),
            "curtain_schema_problems": cl_schema_probs, "robot_schema_problems": rb_schema_probs}),
        "C1-2_real_deform_si0": (c12, {
            "curtains": [{"slot": s, "frame": g["frame"], "si": g["self_intersections"],
                          "flips": g["triangle_flips"], "degen": g["degenerate"],
                          "area_ratio": round(float(g["area_ratio"]), 3), "clean": g["clean"]}
                         for s, g in curtain_gates]}),
        "C1-3_iou_baseline": (c13, {
            "parts": [{"grp": grp, "slot": s, "iou": r["value"],
                       "baseline": r["artist_baseline"], "pass": r["pass"]}
                      for grp, s, r in iou_reports]}),
        "C1-4_gate_calibration": (c14, {
            "benchmark_checker_validated": checker_validated, "benchmark_worst": worst,
            "robot_has_real_deform": robot_gate["has_real_deform"],
            "robot_static_clean": robot_gate["clean"]}),
        "C1-5_gate_non_vacuous": (c15, {
            "curtain_tangle_si": bad_c_gate["self_intersections"],
            "curtain_tangle_flips": bad_c_gate["triangle_flips"],
            "curtain_tangle_clean": bad_c_gate["clean"],
            "robot_tangle_si": bad_r_gate["self_intersections"],
            "robot_tangle_clean": bad_r_gate["clean"]}),
    }
    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "C1 gen_lib.mesh: 件 → strip/auto mesh 生成 + 真實 deform 自交閘(結構軸的 mesh 分支)",
        "entry": "skills/spine-ai-editor/assets/gen_lib/mesh.py :: "
                 "generate_part_mesh / deform_si_gate / generate_and_gate_part",
        "metrics": {
            "curtain_si": {s: g["self_intersections"] for s, g in curtain_gates},
            "curtain_area_ratio": {s: round(float(g["area_ratio"]), 3) for s, g in curtain_gates},
            "iou": {s: r["value"] for _, s, r in iou_reports},
            "neg_curtain_tangle_si": bad_c_gate["self_intersections"],
            "neg_robot_tangle_si": bad_r_gate["self_intersections"],
        },
        "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="完整 JSON 報告")
    a = ap.parse_args()
    report = run_all()
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=float))
    else:
        print(json.dumps({"overall_pass": report["overall_pass"], "metrics": report["metrics"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2, default=float))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
