#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D1 閘 — 統一品質閘 `validator_v2`（spine-ai-editor 2.0 Phase D1）。

B1 把兩套閘的**接縫**機械化（repo cascade beat → validator_v1）；C1/C2 把 mesh/rig 生成 + 其
變形閘搬進 skill。**D1 把這些閘紀律合成單一一條指令** `assets/validator_v2.py`：對一支 2.0
生成的大獎動畫，一鍵輸出**全五維度** pass/fail + 量化指標
（runtime 可載入 / editor 可匯入 / loop 閉合 / stiffness / deform si(C1)），
不必分別跑 validator_v1 與 C1 兩套、也不必人工開 Spine editor。

**驗的是什麼（為何這個 chunk 有價值）**：
  2.0 的輸出合約是「遊戲能播 **且** 編輯器能匯入 **且** mesh 在極端變形下不撕裂」。此前這要跑
  validator_v1（前兩者 + loop + stiffness）**加** C1 deform 閘（後者）兩套、各自解讀。D1 證：
   · 把一支生成大獎動畫（含一個 C1 生成 mesh）丟給**一條指令** → 五維度一次全出。
   · 統一閘的維度 2/3/4 與**真正的** validator_v1（subprocess，使用者端實際用的 CLI）**逐項一致**
     （errors / loop problems / stiffness 不漂移）——「合成單一 ≠ 退化」。
   · 維度 5 在真實 `main_draw` 上對 4 個美術 mesh 走**真實 deform 位移場**路徑、si=0（真值校準），
     並對一個 **C1 生成 mesh** 套真實位移場仍 si=0（生成 mesh 在統一閘內受同一變形紀律把關）。
   · **每個維度各有牙**：注入末鍵 curve / 破壞 loop / 弄亂 mesh hull / 破壞 bone 引用 →
     由**同一條指令**分別抓到對應維度 FAIL（閘非恆真）。

**AC（全部客觀、可機讀）**：
  D1-1 one-command-all-dim : validate_v2 對「2.0 生成大獎動畫 + 嵌入 C1 生成 mesh」→ 五維度**全present**，
                             runtime/editor/loop/deform_si 皆 PASS、stiffness 有限、overall_pass=True；
                             deform_si 確實 gated ≥1 件（非空跑）。
  D1-2 agreement-no-drift  : 同一 skeleton，validate_v2 的 errors 集合 == 真正 validator_v1（subprocess）
                             errors 集合；loop problems 集合一致；stiffness[beat] 數值一致。
  D1-3 real-deform-truth   : validate_v2 對真實 `main_draw.json` → deform_si 維度對 4 個美術 mesh
                             has_real_deform=True 且 clean（si=0）→ 真實 deform 紀律在統一閘內且與真值一致。
  D1-4 generated-in-gate   : 一個 **C1 生成 strip mesh** 經 validator_v2 所**實際接線**的 deform 引擎
                             （`V2._mesh_module().deform_si_gate`，與維度 5 同一函式）套真實 deform 位移場
                             （源自原 artist mesh 的 uvs 轉移）→ has_real_deform=True 且 clean（si=0）。
                             證「統一閘裡的 C1 紀律是**真正的 C1 閘**，非退化副本」；且附帶驗證把生成幾何
                             塞回 artist 的 mesh-specific deform timeline（頂點佈局不一致）會被 validate_v2
                             抓到 si>0（inconsistent skeleton 不放水）。
  D1-5 per-dim-non-vacuous : 對 D1-1 的 skeleton 分別做 4 個破壞，**同一條** validate_v2 指令各抓到對應維度：
                             (a) 末鍵 curve → editor_importable FAIL；(b) 破壞 loop → loop_closure FAIL；
                             (c) mesh hull tangle → deform_si FAIL；(d) 破壞 bone 引用 → runtime_loadable FAIL。

用法：
  python3 validate_d1_validator.py            # 跑 D1-1..D1-5，印精簡 pass/fail + 指標
  python3 validate_d1_validator.py --json     # 完整 JSON 報告

退出碼 0 = 全 AC PASS；非 0 = 有 AC FAIL。
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
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILL_ASSETS = os.path.join(_REPO, "skills", "spine-ai-editor", "assets")
sys.path.insert(0, _HERE)                                     # validate_v2_bridge
sys.path.insert(0, os.path.join(_REPO, "tools", "mesh_gen"))  # mesh_gen deps
sys.path.insert(0, _SKILL_ASSETS)                             # validator_v2 / validator_v1 / curve_tools
sys.path.insert(0, os.path.join(_SKILL_ASSETS, "gen_lib"))   # mesh

import validator_v2 as V2            # noqa: E402  受測的統一閘
import mesh as M                     # noqa: E402  C1 skill 入口（gen_lib.mesh）
from validate_v2_bridge import build_cascade_skeleton  # noqa: E402  複用 B1 的 2.0 生成大獎 fixture

_VALIDATOR_V1 = os.path.join(_SKILL_ASSETS, "validator_v1.py")


def _p(rel):
    return os.path.join(_REPO, rel)


# ------------------------------------------------------------------ fixtures
def _gen_robot_mesh():
    """經 C1 公開 API 產一個乾淨的機器人件 mesh（身體，boundary-dense/auto）。"""
    _, crop = M._crop_region(_p("assets/Award.atlas"), _p("assets/Award.png"), "機器人拆件/身體")
    return M.generate_part_mesh(crop)


def _bigwin_with_mesh():
    """2.0 生成的大獎動畫（cascade beat）+ 在 default skin 嵌入一個 C1 生成 mesh。

    回傳 (skeleton_dict, cascade_anim_name, mesh_slot, mesh_name)。
    嵌入的 mesh 不被任何 timeline 引用（無 deform）→ deform_si 走靜態拓樸檢查（仍 gated）。
    """
    skel, cname = build_cascade_skeleton()
    gmesh = _gen_robot_mesh()
    slot = skel["slots"][0]["name"]            # 掛到既有第一個 slot（避免新增 bone/slot 複雜度）
    mesh_name = "c1_gen_body"
    skel["skins"]["default"][slot][mesh_name] = gmesh
    return skel, cname, slot, mesh_name


def _run_validator_v1_subprocess(skel, loop_anim):
    """把 skeleton 寫檔，呼叫**真正的** validator_v1.py CLI，解析 errors/loop/stiffness（= 使用者端實際閘）。"""
    tmpdir = tempfile.mkdtemp(prefix="d1_v1_")
    jp = os.path.join(tmpdir, "skeleton.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(skel, f, ensure_ascii=False, indent=1)
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
    return {"errors": errors, "loops": loops, "stiffness": stiff}


# ------------------------------------------------------------------ 破壞 mutators（D1-5）
def _inject_last_frame_curve(data, cname):
    anim = data["animations"][cname]
    for tls in anim.get("bones", {}).values():
        for frames in tls.values():
            if isinstance(frames, list) and len(frames) >= 2 and isinstance(frames[-1], dict):
                frames[-1].update({"curve": 0.25, "c2": 0.0, "c3": 0.75, "c4": 1.0})
                return
    raise RuntimeError("找不到可注入末鍵 curve 的 bone timeline")


def _break_loop(data, cname):
    anim = data["animations"][cname]
    for tls in anim.get("bones", {}).values():
        if "scale" in tls and isinstance(tls["scale"], list) and len(tls["scale"]) >= 2:
            tls["scale"][-1]["x"] = tls["scale"][-1].get("x", 1.0) + 0.5
            return
    raise RuntimeError("找不到可破壞的 scale timeline")


def _tangle_mesh(data, slot, name):
    """把嵌入 mesh 的兩個非相鄰 hull 頂點對調 → tangle（負對照）。"""
    att = data["skins"]["default"][slot][name]
    h, v = att["hull"], att["vertices"]
    i, j = 1, h // 2
    v[2*i], v[2*i+1], v[2*j], v[2*j+1] = v[2*j], v[2*j+1], v[2*i], v[2*i+1]


def _break_bone_ref(data, cname):
    """把 cascade 某條 bone timeline 的 key 改成不存在的 bone 名 → v0 runtime 引用錯誤。"""
    anim = data["animations"][cname]
    bones = anim.get("bones", {})
    k = next(iter(bones))
    bones["__nonexistent_bone__"] = bones.pop(k)


# ------------------------------------------------------------------ AC
def run_all():
    skel, cname, mslot, mname = _bigwin_with_mesh()

    # ---- D1-1 one-command all-dimension ----
    rep = V2.validate_v2(skel, loop_anims=[cname])
    dims = rep["dimensions"]
    dd = dims["deform_si"]
    gated_mesh = next((m for m in dd["meshes"] if m["name"] == mname), None)
    d11 = (set(dims) == {"runtime_loadable", "editor_importable", "loop_closure",
                         "stiffness", "deform_si"}
           and dims["runtime_loadable"]["pass"] and dims["editor_importable"]["pass"]
           and dims["loop_closure"]["pass"] and dd["pass"]
           and dims["stiffness"]["all_finite"] and rep["overall_pass"]
           and dd["n_gated"] >= 1 and gated_mesh is not None and gated_mesh["gated"]
           and gated_mesh["clean"])

    # ---- D1-2 agreement with real validator_v1（subprocess，無漂移）----
    v1 = _run_validator_v1_subprocess(skel, cname)
    v2_errors = set(dims["runtime_loadable"]["errors"]) | set(dims["editor_importable"]["errors"])
    v2_loops = set(dims["loop_closure"]["problems"])
    v2_stiff = dims["stiffness"]["per_anim"].get(cname)
    v1_stiff = v1["stiffness"].get(cname)
    stiff_match = (v2_stiff is not None and v1_stiff is not None
                   and abs(v2_stiff - v1_stiff) < 1e-6)
    d12 = (v2_errors == set(v1["errors"]) and v2_loops == set(v1["loops"]) and stiff_match)

    # ---- D1-3 real main_draw：deform_si 真實路徑 + 真值 ----
    real = V2.validate_v2(_p("assets/main_draw.json"), _p("assets/main_draw.atlas"),
                          loop_anims=["main_draw_close"])
    real_meshes = real["dimensions"]["deform_si"]["meshes"]
    real_gated = [m for m in real_meshes if m.get("gated")]
    d13 = (len(real_gated) == 4
           and all(m["has_real_deform"] and m["clean"]
                   and m["self_intersections"] == 0 for m in real_gated))

    # ---- D1-4 C1 生成 mesh 經 validator_v2 的 deform 引擎套真實場 si=0 ----
    _, crop = M._crop_region(_p("assets/main_draw.atlas"), _p("assets/main_draw.png"),
                             "image/curtain_left")
    gen_curtain = M.generate_part_mesh(crop)   # C1 strip（公開 API）
    v2_mesh_engine = V2._mesh_module()         # validator_v2 維度 5 實際接線的同一引擎
    # 正確構法：deform 場源自**原 artist mesh 的 uvs**（原 skeleton），再轉移到生成 mesh（uvs 配對）。
    gi = v2_mesh_engine.deform_si_gate(gen_curtain, _p("assets/main_draw.json"),
                                       "image/curtain_left", "image/curtain_left")
    # 附帶：把生成幾何塞回 artist 的 mesh-specific deform timeline（頂點佈局不一致）→ validate_v2 應抓到 si>0。
    md = json.loads(open(_p("assets/main_draw.json"), encoding="utf-8").read())
    skins = md["skins"]
    skin_map = {s["name"]: s["attachments"] for s in skins} if isinstance(skins, list) else skins
    orig = skin_map["default"]["image/curtain_left"]["image/curtain_left"]
    swapped = dict(gen_curtain)
    if "name" in orig:
        swapped["name"] = orig["name"]
    skin_map["default"]["image/curtain_left"]["image/curtain_left"] = swapped
    repm = V2.validate_v2(md, loop_anims=["main_draw_close"])
    gm = next((m for m in repm["dimensions"]["deform_si"]["meshes"]
               if m["name"] == "image/curtain_left"), None)
    inconsistent_caught = (gm is not None and gm["gated"] and not gm["clean"]
                           and gm["self_intersections"] > 0)
    d14 = (gi["has_real_deform"] and gi["frame"] is not None and gi["clean"]
           and gi["self_intersections"] == 0 and gi["triangle_flips"] == 0
           and inconsistent_caught)

    # ---- D1-5 per-dimension non-vacuous（同一條指令各抓到）----
    def _mut(fn):
        d = copy.deepcopy(skel)
        fn(d)
        return V2.validate_v2(d, loop_anims=[cname])

    r_curve = _mut(lambda d: _inject_last_frame_curve(d, cname))
    r_loop = _mut(lambda d: _break_loop(d, cname))
    r_tangle = _mut(lambda d: _tangle_mesh(d, mslot, mname))
    r_bone = _mut(lambda d: _break_bone_ref(d, cname))

    neg = {
        "editor_caught": (not r_curve["dimensions"]["editor_importable"]["pass"]) and
                         (not r_curve["overall_pass"]),
        "loop_caught": (not r_loop["dimensions"]["loop_closure"]["pass"]) and
                       (not r_loop["overall_pass"]),
        "deform_caught": (not r_tangle["dimensions"]["deform_si"]["pass"]) and
                         (not r_tangle["overall_pass"]),
        "runtime_caught": (not r_bone["dimensions"]["runtime_loadable"]["pass"]) and
                          (not r_bone["overall_pass"]),
    }
    d15 = all(neg.values())

    res = {
        "D1-1_one_command_all_dim": (d11, {
            "dimensions_present": sorted(dims),
            "overall_pass": rep["overall_pass"],
            "runtime": dims["runtime_loadable"]["pass"],
            "editor": dims["editor_importable"]["pass"],
            "loop": dims["loop_closure"]["pass"],
            "stiffness_finite": dims["stiffness"]["all_finite"],
            "stiffness": dims["stiffness"]["per_anim"],
            "deform_si_pass": dd["pass"], "n_gated": dd["n_gated"],
            "embedded_mesh": {"slot": mslot, "name": mname,
                              "clean": gated_mesh and gated_mesh["clean"],
                              "has_real_deform": gated_mesh and gated_mesh["has_real_deform"],
                              "si": gated_mesh and gated_mesh["self_intersections"]}}),
        "D1-2_agreement_no_drift": (d12, {
            "errors_match": v2_errors == set(v1["errors"]),
            "loops_match": v2_loops == set(v1["loops"]),
            "stiffness_match": stiff_match,
            "v2_stiffness": v2_stiff, "v1_stiffness": v1_stiff,
            "n_v1_errors": len(v1["errors"]), "n_v2_errors": len(v2_errors)}),
        "D1-3_real_deform_truth": (d13, {
            "n_gated_mesh": len(real_gated),
            "meshes": [{"name": m["name"], "has_real_deform": m["has_real_deform"],
                        "si": m["self_intersections"], "frame": m["frame"],
                        "clean": m["clean"]} for m in real_gated]}),
        "D1-4_generated_in_gate": (d14, {
            "gen_mesh_mode": gen_curtain.get("_mode"),
            "correct_transfer": {"has_real_deform": gi["has_real_deform"], "frame": gi["frame"],
                                 "si": gi["self_intersections"], "flips": gi["triangle_flips"],
                                 "area_ratio": (round(float(gi["area_ratio"]), 3)
                                                if gi["area_ratio"] == gi["area_ratio"] else None),
                                 "clean": gi["clean"]},
            "inconsistent_skeleton_caught": inconsistent_caught,
            "inconsistent_si": gm and gm.get("self_intersections")}),
        "D1-5_per_dim_non_vacuous": (d15, neg),
    }
    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "D1 validator_v2: 統一品質閘（runtime/editor/loop/stiffness/deform_si 一鍵全維度）",
        "entry": "skills/spine-ai-editor/assets/validator_v2.py :: validate_v2 / CLI",
        "metrics": {
            "bigwin_overall_pass": rep["overall_pass"],
            "bigwin_stiffness": dims["stiffness"]["per_anim"].get(cname),
            "deform_si_gated_in_bigwin": dd["n_gated"],
            "real_main_draw_gated_mesh": len(real_gated),
            "v1_v2_errors_match": v2_errors == set(v1["errors"]),
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
