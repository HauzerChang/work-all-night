#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Spine 3.8 Validator — v2（統一品質閘；spine-ai-editor 2.0 Phase D1）

把 **repo 的閘紀律** 與 **v1.3.0 的 validator_v1** 合成**單一入口**：對一支 2.0 生成的大獎動畫，
一條指令同時輸出**全維度 pass/fail + 量化指標**。這是 MERGE_PLAN_2.0 Phase D 的落點——
B/C 階段各自把生成器 + 它的專屬閘搬進 skill，D1 把這些分散的驗收面收斂成一張**單一報告**，
讓「生成 → 驗收」只需跑一支 validator，而非記住 validator_v0 / validator_v1 / gen_lib.mesh.deform_si_gate /
gen_animations.is_c1_loopable 各自怎麼跑。

== 六個維度（對外契約）==
  1. runtime_loadable  —— runtime(spine-webgl)能不能載入：v0 schema/引用完整性 +
                          v1 的 cx 超界(bezier runtime 解錯)。**硬閘**。
  2. editor_importable —— Spine editor 能不能匯入：末鍵 curve(地雷 #12 AIOOBE,runtime 會忽略但
                          editor 匯入 crash)。**硬閘**。← 與 1 的乾淨切分 = G2「遊戲能播 且 編輯器能匯入」。
  3. loop_closure      —— 每條 timeline 首尾值閉合 + key 時間單調 + 首鍵在 0/末鍵在 dur。**硬閘**。
  4. stiffness         —— 每支動畫 key 處速度不連續量(越低越順)。**量化指標**(非硬閘;非有限才 fail)。
  5. deform_si         —— skeleton 內每個 **mesh** attachment 套真實 deform 位移場後
                          self-intersections/flips/degenerate=0(無 deform 的 weighted 件退回靜態拓樸檢查)。
                          **硬閘(有 mesh 時)**;無 mesh → n/a(大獎 beat 多為 region 占位 → 正常 n/a)。
  6. c1_continuity     —— 每支動畫自接點是否 C1-loopable(值且速度皆連續)+ loop_seam_velocity_gap。
                          **量化指標**(非硬閘;一次性大獎 beat 預期 C0 可接但非 C1,是刻畫非失敗);
                          `--require-c1 A,B` 可把指定動畫升為硬閘(idle Loop 類要求 C1 平滑)。

== overall_pass 怎麼算 ==
  = 所有**硬閘**維度 PASS：runtime_loadable AND editor_importable AND loop_closure
    AND (deform_si 若有 mesh) AND (c1_continuity 若有 --require-c1)。
  stiffness 與未要求的 c1 只回報量化值，不影響 overall（除非 stiffness 非有限）。

== 與既有閘的關係（不產生第二套真值）==
  - 維度 1/2/3/4 **直接呼叫 `validator_v1.validate_v1()`**(程式化入口,與 CLI 同一套檢查)，
    再依 error 字串前綴把「runtime」與「editor」兩語意切開——不重寫 schema/curve/loop 邏輯。
  - 維度 5 **直接呼叫 `gen_lib.mesh.deform_si_gate()`**(C1 的真實位移場閘,真值校準)。
  - 維度 6 **直接呼叫 `gen_animations.is_c1_loopable()`**(B4 的 C1 判準)。
  → validator_v2 是**編排層(orchestrator)**,不是新的檢查邏輯;各維度的真值來源仍是既有、已有負對照的閘。

== 過渡期相依（D1 → E1）==
  維度 1-4 **standalone**(只需 assets/ 的 validator_v0 / validator_v1 / curve_tools,無 repo tools)。
  維度 5(deform_si)需 repo tools/mesh_gen、維度 6(c1)需 repo tools/analyzer——與 gen_lib 一致的過渡期
  相依;**取不到時該維度標 `unavailable`(不讓整支 crash)**，standalone 的 1-4 仍可跑。E1 bundle 後補齊。

用法（CLI）:
  python3 validator_v2.py Main.json [Main.atlas]            # 全維度精簡報告
  python3 validator_v2.py Main.json --loop-anims Loop       # loop 閉合只查 Loop
  python3 validator_v2.py Main.json --require-c1 Loop        # 要求 Loop 動畫 C1-loopable(升硬閘)
  python3 validator_v2.py Main.json --json                  # 完整機讀報告

程式化:
  from validator_v2 import validate_v2
  rep = validate_v2("Main.json", atlas_path=None, loop_anims=["Loop"])
  rep["overall_pass"]; rep["dimensions"]["deform_si"]["status"]

退出碼 0 = overall PASS;1 = 有硬閘 FAIL;2 = 用法錯。
"""
from __future__ import annotations
import argparse
import json
import math
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)

from validator_v0 import validate as validate_v0          # noqa: E402
from validator_v1 import validate_v1                      # noqa: E402


# --------------------------------------------------------------------- self-contained shim（維度 5/6，E1）
def _wire_repo_tools():
    """把 **bundled** 生成引擎(`gen_lib/_bundled`,repo tools 的逐位元複本)掛上 sys.path。
    回傳 (ok, err)。取不到時 ok=False，維度 5/6 標 unavailable（standalone 1-4 仍可跑）。
    E1(2026-10-18)後 skill **self-contained**,不再相依本 research repo 的 `tools/`。"""
    for p in (os.path.join(_HERE, "gen_lib", "_bundled"),            # 生成引擎逐位元複本
              os.path.join(_HERE, "gen_lib")):                       # gen_lib package
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        import gen_lib.mesh as _m           # noqa: F401  維度 5 deform_si
        import gen_animations as _g         # noqa: F401  維度 6 c1(bundled)
        return True, None
    except Exception as e:                   # noqa: BLE001
        return False, "{}: {}".format(type(e).__name__, e)


# --------------------------------------------------------------------- 維度 5 helper：找 mesh
def _iter_mesh_attachments(data):
    """掃 skeleton 的所有 skin，yield (slot_name, attachment_key, attachment_name, att_dict)
    僅限 type=='mesh' 的 attachment。相容 skins 為 list / dict 兩種 3.8 格式。"""
    skins = data.get("skins", {})
    if isinstance(skins, list):
        skin_iter = ((s.get("name"), s.get("attachments", {})) for s in skins)
    else:
        skin_iter = ((name, atts) for name, atts in skins.items())
    seen = set()
    for _skin_name, atts in skin_iter:
        for slot_name, slot_atts in atts.items():
            for att_key, att in slot_atts.items():
                if not isinstance(att, dict) or att.get("type") != "mesh":
                    continue
                att_name = att.get("name", att_key)
                sig = (slot_name, att_name)
                if sig in seen:          # 同件跨 skin 只驗一次
                    continue
                seen.add(sig)
                yield slot_name, att_key, att_name, att


# --------------------------------------------------------------------- 核心
def validate_v2(json_path, atlas_path=None, loop_anims=None, require_c1=None):
    """統一品質閘。回傳結構化報告 dict:
      {overall_pass, source, dimensions:{dim:{status, pass?, ...}}, hard_fail:[...]}。

    status ∈ {"pass","fail","na","info","unavailable"}。
      pass/fail  —— 硬閘(或被 --require-c1 升為硬閘)。
      na         —— 不適用(如無 mesh → deform_si)。不計入 overall。
      info       —— 純量化指標(stiffness / 未要求的 c1)。不計入 overall。
      unavailable—— 過渡期相依取不到。不計入 overall(但會在報告標示)。
    """
    json_path = Path(json_path)
    require_c1 = set(require_c1 or [])
    dims = {}

    # ---- 讀一次 data（維度 5/6 用）----
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception as e:                   # noqa: BLE001
        data = None
        parse_err = "{}: {}".format(type(e).__name__, e)
    else:
        parse_err = None

    # ---- 維度 1-4：呼叫 validator_v1 程式化入口（同一套真值）----
    r1, _demoted, metrics = validate_v1(json_path, atlas_path, loop_anims, want_metric=True)
    # error 依前綴切分語意：
    #   '(v1) ... cx 超出'            → runtime(bezier runtime 解錯)
    #   '(v1) ... 最後一鍵帶 curve'    → editor(地雷 #12,runtime OK)
    #   其餘(v0 schema/ref)           → runtime(載不進來)
    editor_errs, runtime_errs = [], []
    for e in r1.errors:
        if "最後一鍵帶 curve" in e or "AIOOBE" in e:
            editor_errs.append(e)
        else:
            runtime_errs.append(e)
    loop_probs = [w[len("(v1 loop)"):].strip() if w.startswith("(v1 loop)") else w
                  for w in r1.warnings if "(v1 loop)" in w]

    dims["runtime_loadable"] = {
        "status": "pass" if not runtime_errs else "fail",
        "pass": not runtime_errs,
        "errors": runtime_errs,
        "detail": "v0 schema/引用完整性 + v1 cx 超界(bezier runtime 解錯)",
    }
    dims["editor_importable"] = {
        "status": "pass" if not editor_errs else "fail",
        "pass": not editor_errs,
        "errors": editor_errs,
        "detail": "末鍵 curve(地雷 #12,editor 匯入 AIOOBE crash)",
    }
    dims["loop_closure"] = {
        "status": "pass" if not loop_probs else "fail",
        "pass": not loop_probs,
        "problems": loop_probs,
        "scope": sorted(loop_anims) if loop_anims else "all",
    }
    stiff_finite = all(isinstance(v, (int, float)) and math.isfinite(v) for v in metrics.values())
    dims["stiffness"] = {
        "status": "info" if stiff_finite else "fail",
        "pass": stiff_finite,               # 只有非有限才 fail
        "metric": {k: round(v, 2) for k, v in metrics.items()},
        "note": "量化指標(越低越順);非有限值才算硬閘 FAIL",
    }

    # ---- 維度 5/6：過渡期相依 ----
    wired, wire_err = _wire_repo_tools()

    # 維度 5：deform_si
    if data is None:
        dims["deform_si"] = {"status": "fail", "pass": False,
                             "error": "skeleton 解析失敗: {}".format(parse_err)}
    elif not wired:
        dims["deform_si"] = {"status": "unavailable", "reason": wire_err}
    else:
        import gen_lib.mesh as MESH
        meshes = list(_iter_mesh_attachments(data))
        if not meshes:
            dims["deform_si"] = {"status": "na", "reason": "skeleton 無 mesh attachment(region 占位 beat → 正常)"}
        else:
            results, all_clean = [], True
            for slot_name, _att_key, att_name, att in meshes:
                try:
                    gate = MESH.deform_si_gate(att, data, slot_name, att_name)
                except Exception as e:       # noqa: BLE001
                    gate = {"clean": False, "error": "{}: {}".format(type(e).__name__, e)}
                clean = bool(gate.get("clean"))
                all_clean = all_clean and clean
                results.append({
                    "slot": slot_name, "name": att_name,
                    "has_real_deform": gate.get("has_real_deform"),
                    "self_intersections": gate.get("self_intersections"),
                    "triangle_flips": gate.get("triangle_flips"),
                    "degenerate": gate.get("degenerate"),
                    "area_ratio": (round(gate["area_ratio"], 4)
                                   if isinstance(gate.get("area_ratio"), (int, float)) else None),
                    "clean": clean,
                    **({"error": gate["error"]} if gate.get("error") else {}),
                })
            dims["deform_si"] = {
                "status": "pass" if all_clean else "fail",
                "pass": all_clean,
                "mesh_count": len(meshes),
                "meshes": results,
            }

    # 維度 6：c1_continuity
    if data is None:
        dims["c1_continuity"] = {"status": "fail", "pass": False,
                                 "error": "skeleton 解析失敗"}
    elif not wired:
        dims["c1_continuity"] = {"status": "unavailable", "reason": wire_err}
    else:
        import gen_animations as G
        anims = data.get("animations", {})
        per = {}
        required_all_ok = True
        for aname, anim in anims.items():
            try:
                c1 = bool(G.is_c1_loopable(anim))
                c0 = bool(G.is_loopable(anim))
                gap = float(G.loop_seam_velocity_gap(anim))
            except Exception as e:           # noqa: BLE001
                per[aname] = {"error": "{}: {}".format(type(e).__name__, e)}
                if aname in require_c1:
                    required_all_ok = False
                continue
            per[aname] = {"c1_loopable": c1, "c0_loopable": c0,
                          "loop_seam_velocity_gap": round(gap, 4)}
            if aname in require_c1 and not c1:
                required_all_ok = False
        if require_c1:
            dims["c1_continuity"] = {
                "status": "pass" if required_all_ok else "fail",
                "pass": required_all_ok,
                "required": sorted(require_c1),
                "per_anim": per,
                "note": "--require-c1 指定動畫須 C1-loopable(升硬閘)",
            }
        else:
            dims["c1_continuity"] = {
                "status": "info",
                "per_anim": per,
                "note": "量化刻畫;一次性大獎 beat 預期 C0 可接但非 C1(刻畫非失敗)。"
                        "要求某動畫 C1 平滑請加 --require-c1",
            }

    # ---- overall：所有硬閘 PASS ----
    hard_fail = [name for name, d in dims.items()
                 if d.get("status") == "fail"]
    overall = len(hard_fail) == 0
    return {
        "overall_pass": overall,
        "source": json_path.name,
        "hard_fail": hard_fail,
        "dimensions": dims,
    }


# --------------------------------------------------------------------- CLI 輸出
_STATUS_TAG = {"pass": "PASS", "fail": "FAIL", "na": " n/a", "info": "info",
               "unavailable": "unav"}


def _print_report(rep):
    print("=== validator_v2 on {} ===".format(rep["source"]))
    dims = rep["dimensions"]
    order = ["runtime_loadable", "editor_importable", "loop_closure",
             "stiffness", "deform_si", "c1_continuity"]
    for name in order:
        d = dims[name]
        tag = _STATUS_TAG.get(d["status"], d["status"])
        line = "  [{}] {}".format(tag, name)
        if name == "stiffness" and d.get("metric"):
            top = sorted(d["metric"].items(), key=lambda x: -x[1])[:3]
            line += "  " + ", ".join("{}={}".format(k, v) for k, v in top)
        elif name == "deform_si" and d["status"] in ("pass", "fail"):
            line += "  ({} mesh)".format(d.get("mesh_count"))
        elif name == "deform_si" and d["status"] == "na":
            line += "  (無 mesh)"
        elif name == "c1_continuity" and d.get("per_anim"):
            c1s = [a for a, v in d["per_anim"].items() if v.get("c1_loopable")]
            line += "  C1-loopable: {}/{}".format(len(c1s), len(d["per_anim"]))
        elif d["status"] == "unavailable":
            line += "  ({})".format(d.get("reason", "")[:60])
        print(line)
        for e in d.get("errors", [])[:4]:
            print("        - {}".format(e))
        for p in d.get("problems", [])[:4]:
            print("        - {}".format(p))
        if name == "deform_si" and d["status"] == "fail":
            for m in d.get("meshes", []):
                if not m["clean"]:
                    print("        - {} si={} flips={} degen={}".format(
                        m["name"], m.get("self_intersections"),
                        m.get("triangle_flips"), m.get("degenerate")))
    print()
    if rep["overall_pass"]:
        print("RESULT: PASS  (all hard gates green)")
    else:
        print("RESULT: FAIL  (hard gates failed: {})".format(", ".join(rep["hard_fail"])))


def main(argv):
    ap = argparse.ArgumentParser(description="Spine 3.8 統一品質閘 validator_v2(D1)")
    ap.add_argument("json", help="skeleton JSON 路徑")
    ap.add_argument("atlas", nargs="?", default=None, help="(選)atlas 路徑,給了才做 atlas 交叉檢查")
    ap.add_argument("--loop-anims", default=None, help="loop 閉合只查這些(逗號分隔);預設全查")
    ap.add_argument("--require-c1", default=None, help="要求這些動畫 C1-loopable(逗號分隔,升硬閘)")
    ap.add_argument("--json", action="store_true", dest="as_json", help="完整機讀 JSON 報告")
    a = ap.parse_args(argv[1:])

    loop_anims = a.loop_anims.split(",") if a.loop_anims else None
    require_c1 = a.require_c1.split(",") if a.require_c1 else None
    rep = validate_v2(a.json, a.atlas, loop_anims, require_c1)
    if a.as_json:
        print(json.dumps(rep, ensure_ascii=False, indent=2))
    else:
        _print_report(rep)
    return 0 if rep["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
