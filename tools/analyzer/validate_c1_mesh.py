#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C1 閘 — `gen_lib.mesh_gen` deform-aware mesh 生成 + 真實位移場自交閘
(spine-ai-editor 2.0 Phase C1)。

B2/B3/B4 把 repo 的**動畫**生成抽成 skill 入口;C1 補上**mesh 生成**這個結構軸:
`generate_mesh_v2`(strip/delaunay/boundary 確定性拓樸)+ `deform_eval`(**真實位移場轉移**自交閘)
抽成 `skills/spine-ai-editor/assets/gen_lib/mesh_gen.py`。v1.3.0 **只檢查既有 mesh、不生成**;C1 讓 2.0
能從一張件圖**自動產出可變形 mesh** 並以真實最壞變形證明它不撕裂(self_intersections=0)。

**驗的是什麼(為何這個 chunk 有價值)**:
  「評估器就緒 ≠ 生成器就緒」在 mesh 層的落點:repo `deform_eval` 早證**真實 main_draw 4 mesh** 全乾淨
  (藝術家 mesh),但那不代表**生成器**自動產的 mesh 也耐變形。本閘證:**生成器自動產**的 mesh,吃該件
  **真實 deform 最壞幀**位移場轉移後,**self_intersections=0 / flips=0 / degenerate=0**,且覆蓋率不低於藝術家
  baseline。並以**負對照**(打亂位移場空間平滑 / 放大幅度)證自交閘**非恆真**(抓得到壞 mesh)。

**AC(全部客觀、可機讀)**:
  C1-1 entrypoint+schema : `mesh_gen.generate_mesh` / `generate_and_gate` / `deform_gate` /
                           `real_deform_field` 皆**公開 API**;對真實 curtain_left region 產出 mesh →
                           `_mode=="strip"`(高瘦 row-convex 選 strip)+ Spine mesh schema 合法
                           (len(vertices)==len(uvs)==2·nv、triangles 為 3 倍數且索引 < nv、hull∈[1,nv]、全有限)。
  C1-2 real-deform-si0   : main_draw **4 mesh**(curtain_left/right/shadow/shadow2)皆經入口
                           `generate_and_gate` 自動生成 → 各件**自身真實 deform 最壞幀**位移場轉移後
                           **self_intersections==0 且 triangle_flips==0 且 degenerate==0**(deform si=0 核心 AC)。
  C1-3 robot+auto-select : Award robot 件(身體/左手)經 auto 生成 → schema 合法 + **setup pose 乾淨**
                           (生成拓樸本身合法);且**強制 strip 於緊湊件(身體)setup 不乾淨** →
                           證 auto 的拓樸選擇是**載重的**(strip 非萬用,窗簾才適用)—— 非恆真。
  C1-4 iou-not-degraded  : curtain_left/right 生成 mesh 對真實 alpha 的 IoU **≥ 藝術家 baseline**
                           (生成忠實,不是只拓樸乾淨卻漏覆蓋)。
  C1-5 gate-non-vacuous  : 真實場 baseline 乾淨(si=0);**打亂位移場空間平滑**(逐頂點 permute)→ 至少
                           一 mesh 非乾淨(si>0 或 flips>0);**放大幅度 ×6** → 非乾淨。證自交閘抓得到壞變形。

用法:
  python3 validate_c1_mesh.py            # 跑 C1-1..C1-5,印精簡 pass/fail + 指標
  python3 validate_c1_mesh.py --json     # 完整 JSON 報告

退出碼 0 = 全 AC PASS;非 0 = 有 AC FAIL。
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILL_ASSETS = os.path.join(_REPO, "skills", "spine-ai-editor", "assets")
sys.path.insert(0, os.path.join(_SKILL_ASSETS, "gen_lib"))
sys.path.insert(0, os.path.join(_REPO, "tools", "mesh_gen"))

import mesh_gen as M              # noqa: E402  C1 skill 入口(gen_lib)

_ASSETS = os.path.join(_REPO, "assets")
_MD_JSON = os.path.join(_ASSETS, "main_draw.json")
_MD_ATLAS = os.path.join(_ASSETS, "main_draw.atlas")
_MD_PNG = os.path.join(_ASSETS, "main_draw.png")
_AW_JSON = os.path.join(_ASSETS, "Award.json")
_AW_ATLAS = os.path.join(_ASSETS, "Award.atlas")
_AW_PNG = os.path.join(_ASSETS, "Award.png")

_MD_MESHES = [
    ("image/curtain_left", "image/curtain_left"),
    ("image/curtain_right", "image/curtain_right"),
    ("image/shadow", "image/shadow"),
    ("image/shadow2", "image/shadow"),
]
_ROBOT_PARTS = ["機器人拆件/身體", "機器人拆件/左手"]


def run_all():
    tmp = tempfile.mkdtemp(prefix="c1val_")

    # ========================================================= C1-1 entrypoint + schema
    api_ok = all(callable(getattr(M, fn, None)) for fn in
                 ("generate_mesh", "generate_and_gate", "deform_gate",
                  "real_deform_field", "crop_region", "mesh_schema_ok"))
    crop_cl = M.crop_region(_MD_ATLAS, _MD_PNG, "image/curtain_left",
                            os.path.join(tmp, "cl.png"))
    mesh_cl = M.generate_mesh(crop_cl, mode="auto")
    schema_ok, schema = M.mesh_schema_ok(mesh_cl)
    is_strip = mesh_cl.get("_mode") == "strip"
    c11 = api_ok and schema_ok and is_strip

    # ========================================================= C1-2 real-deform si=0 (4 mesh)
    md_reports = {}
    c12 = True
    for slot, name in _MD_MESHES:
        rep = M.generate_and_gate(_MD_JSON, _MD_ATLAS, _MD_PNG, slot, name,
                                  out_dir=os.path.join(tmp, name.replace("/", "_")))
        d = rep["AC_real_deform"]
        good = (rep["schema_ok"] and d["self_intersections"] == 0
                and d["triangle_flips"] == 0 and d["degenerate"] == 0)
        c12 = c12 and good
        md_reports[name if name != "image/shadow" else slot] = {
            "mode": rep["mesh"]["mode"], "nv": rep["mesh"]["vertices"],
            "frame": d["frame"], "self_intersections": d["self_intersections"],
            "triangle_flips": d["triangle_flips"], "degenerate": d["degenerate"],
            "area_ratio": round(d["area_ratio"], 3), "clean": good}

    # ========================================================= C1-3 robot auto + strip-selection load-bearing
    robot_reports = {}
    robot_auto_ok = True
    for name in _ROBOT_PARTS:
        crop = M.crop_region(_AW_ATLAS, _AW_PNG, name,
                             os.path.join(tmp, "rb_" + name.replace("/", "_") + ".png"))
        mauto = M.generate_mesh(crop, mode="auto")
        a_schema, _ = M.mesh_schema_ok(mauto)
        a_setup = M.setup_clean(mauto)
        good = a_schema and a_setup["clean"]
        robot_auto_ok = robot_auto_ok and good
        robot_reports[name] = {"auto_mode": mauto.get("_mode"), "auto_nv": len(mauto["uvs"]) // 2,
                               "auto_schema_ok": a_schema, "auto_setup_clean": a_setup["clean"]}
    # 強制 strip 於緊湊件(身體)→ setup 不乾淨(證 auto 選擇是載重的、strip 非萬用)
    body_crop = M.crop_region(_AW_ATLAS, _AW_PNG, "機器人拆件/身體",
                              os.path.join(tmp, "body_strip.png"))
    body_strip = M.generate_mesh(body_crop, mode="strip")
    body_strip_setup = M.setup_clean(body_strip)
    strip_selection_load_bearing = (body_strip.get("_mode") == "strip"
                                    and not body_strip_setup["clean"])
    robot_reports["機器人拆件/身體"]["forced_strip_setup_clean"] = body_strip_setup["clean"]
    robot_reports["機器人拆件/身體"]["forced_strip_degenerate"] = body_strip_setup["degenerate"]
    c13 = robot_auto_ok and strip_selection_load_bearing

    # ========================================================= C1-4 IoU not degraded
    iou_reports = {}
    c14 = True
    for slot, name in _MD_MESHES[:2]:   # 兩窗簾(strip 核心件)
        rep = M.generate_and_gate(_MD_JSON, _MD_ATLAS, _MD_PNG, slot, name,
                                  out_dir=os.path.join(tmp, "iou_" + name.replace("/", "_")))
        ac = rep["AC_iou"]
        c14 = c14 and ac["pass"]
        iou_reports[name] = {"value": ac["value"], "artist_baseline": ac["artist_baseline"],
                             "pass": ac["pass"]}

    # ========================================================= C1-5 gate non-vacuous
    sk = json.load(open(_MD_JSON, encoding="utf-8"))
    uvs, field, frame = M.real_deform_field(sk, "image/curtain_left", "image/curtain_left")
    base = M.deform_gate(mesh_cl, uvs, field)
    base_clean = base["clean"]
    rng = np.random.default_rng(0)
    shuf = field[rng.permutation(len(field))]
    neg_shuf = M.deform_gate(mesh_cl, uvs, shuf)
    shuf_caught = not neg_shuf["clean"]
    neg_amp = M.deform_gate(mesh_cl, uvs, field * 6.0)
    amp_caught = not neg_amp["clean"]
    c15 = base_clean and shuf_caught and amp_caught

    # cleanup
    import shutil
    try:
        shutil.rmtree(tmp)
    except OSError:
        pass

    res = {
        "C1-1_entrypoint_schema": (c11, {
            "public_api_callable": api_ok, "schema_ok": schema_ok,
            "curtain_left_mode": mesh_cl.get("_mode"), "schema": schema}),
        "C1-2_real_deform_si0": (c12, {"meshes": md_reports,
            "note": "4 生成 mesh 吃各自真實 deform 最壞幀 → si=0/flips=0/degenerate=0"}),
        "C1-3_robot_auto_select": (c13, {"robot": robot_reports,
            "strip_selection_load_bearing": strip_selection_load_bearing,
            "note": "auto 為緊湊件選 boundary/delaunay(setup 乾淨);強制 strip 於身體 setup 不乾淨 → 選擇載重"}),
        "C1-4_iou_not_degraded": (c14, {"curtains": iou_reports,
            "note": "生成 mesh IoU ≥ 藝術家 baseline(忠實覆蓋)"}),
        "C1-5_gate_non_vacuous": (c15, {
            "baseline_clean": base_clean, "baseline_frame": frame,
            "real_field_max_mag": round(float(np.hypot(field[:, 0], field[:, 1]).max()), 2),
            "neg_shuffle_caught": shuf_caught,
            "neg_shuffle": {k: int(neg_shuf[k]) for k in ("self_intersections", "triangle_flips", "degenerate")},
            "neg_amplify6x_caught": amp_caught,
            "neg_amplify6x": {k: int(neg_amp[k]) for k in ("self_intersections", "triangle_flips", "degenerate")}}),
    }
    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "C1 gen_lib.mesh_gen: deform-aware mesh 生成 + 真實位移場自交閘(v1.3.0 只檢查不生成)",
        "entry": "skills/spine-ai-editor/assets/gen_lib/mesh_gen.py :: "
                 "generate_mesh / generate_and_gate / deform_gate / real_deform_field",
        "metrics": {
            "main_draw_meshes_si0": {k: v["self_intersections"] for k, v in md_reports.items()},
            "curtain_iou": {k: v["value"] for k, v in iou_reports.items()},
            "neg_shuffle_si": neg_shuf["self_intersections"],
            "neg_amplify6x_si": neg_amp["self_intersections"]},
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
