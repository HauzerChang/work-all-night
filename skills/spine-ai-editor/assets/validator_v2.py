#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Spine 3.8 Validator — v2（統一品質閘 / spine-ai-editor 2.0 Phase D1）

把本 research repo 半年累積的**閘紀律**（mesh 變形自交閘 C1 / 真值校準）＋ v1.3.0 的
`validator_v1`（runtime 可載入 schema / editor 可匯入末鍵 curve / loop 閉合 / stiffness）
**合成單一一條指令**——對一支 2.0 生成的大獎動畫（skeleton JSON），一鍵輸出**全維度**
pass/fail + 量化指標，不必分別跑 v1 與 C1 兩套閘、也不必人工開 Spine editor。

**五個維度（= MERGE_PLAN G2 雙真值 + C 階段 mesh 紀律合流）：**
  1. runtime_loadable  : validator_v0 schema / 引用完整性（= spine-webgl 可載入的 CPU 代理）。
  2. editor_importable : v1 的末鍵 curve 檢查（地雷 #12 AIOOBE）＋ cx 超界升級（= editor 可匯入）。
  3. loop_closure      : v1 的 loop 閉合（首尾值一致、首鍵在 0、末鍵在時長處）。
  4. stiffness         : v1 的 --metric（key 處速度不連續量，越低越順）——量化，非 pass/fail 硬閘。
  5. deform_si (C1)    : 對 skin 內每個 **mesh** attachment 跑 `gen_lib.mesh.deform_si_gate`
                         （有真實 deform timeline → 真實位移場轉移 si/flips/degen；無 → 退回靜態拓樸）。
                         weighted mesh（len(vertices)!=len(uvs)）的逐骨 skinning 變形屬 C2
                         `weighted_deform_eval` 的範疇，本統一閘只對其做 schema 檢查、不列 si 硬閘。

**單一真相來源（無漂移）**：維度 1–4 直接 in-process 呼叫 `validator_v1.run_checks()`
（與 CLI `validator_v1.py` 同一函式），維度 5 直接呼叫 `gen_lib.mesh.deform_si_gate`。
validator_v2 不重寫任一套閘的判準，只是把兩者的結果**合流**成一份結構化報告。

用法：
  python3 validator_v2.py Main.json [Main.atlas] [--loop-anims A,B] [--json]
  python3 validator_v2.py Main.json --no-stiffness-gate   # stiffness 僅報告不參與 overall（預設即如此）

程式化：
  from validator_v2 import validate_v2
  report = validate_v2("Main.json", "Main.atlas", loop_anims=["cascade"])
  report["overall_pass"]; report["dimensions"]["deform_si"]["meshes"]

退出碼 0 = overall_pass；非 0 = 有 gating 維度 FAIL。
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _HERE)                           # validator_v0 / validator_v1 / curve_tools
sys.path.insert(0, os.path.join(_HERE, "gen_lib"))  # 讓 `import mesh` 可直接命中 gen_lib.mesh

import validator_v1 as V1                            # noqa: E402  維度 1–4 單一真相來源


def _mesh_module():
    """延遲載入 gen_lib.mesh（它在函式內才 import repo tools，top-level 匯入安全）。

    優先以套件路徑 `gen_lib.mesh` 匯入（self-contained 友善）；退回 `import mesh`。
    """
    try:
        from gen_lib import mesh as M  # type: ignore
        return M
    except Exception:
        import mesh as M  # type: ignore  # noqa
        return M


# ------------------------------------------------------------------ mesh 收集 / 分類
def _iter_mesh_attachments(data):
    """走訪所有 skin，yield (slot, attachment_key, attachment_dict)，只挑 type=='mesh'。

    linkedmesh 共用母 mesh 的幾何，無自帶 vertices/uvs → 跳過（由母 mesh 代表受檢）。
    """
    skins = data.get("skins", {})
    skin_map = {s["name"]: s["attachments"] for s in skins} if isinstance(skins, list) else skins
    for _skin_name, skin_atts in skin_map.items():
        for slot_name, atts in skin_atts.items():
            for att_key, att in atts.items():
                if not isinstance(att, dict):
                    continue
                if att.get("type") == "mesh":
                    yield slot_name, att_key, att


def _is_weighted(att):
    """unweighted mesh：len(vertices)==len(uvs)；否則為 weighted（攤平變長格式）。"""
    v, u = att.get("vertices", []), att.get("uvs", [])
    return len(v) != len(u)


# ------------------------------------------------------------------ 五維度主閘
def validate_v2(skeleton, atlas_path=None, loop_anims=None, want_stiffness=True,
                stiffness_gate=False):
    """對一支 skeleton（JSON 路徑 或 dict）跑全部五個維度，回傳結構化報告。

    stiffness_gate=False（預設）：stiffness 僅量化報告、不參與 overall_pass
      （手感為美術主觀項，RULES A 類；硬閘只用客觀維度 1/2/3/5）。
    """
    # dict → 寫 temp json，讓 validator_v1 / deform_si_gate 都能吃路徑或 dict。
    tmp_path = None
    if isinstance(skeleton, (str, Path)):
        json_path = Path(skeleton)
        data = json.loads(json_path.read_text(encoding="utf-8"))
        skel_for_deform = str(json_path)
    else:
        data = skeleton
        fd, tmp_path = tempfile.mkstemp(prefix="validator_v2_", suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        json_path = Path(tmp_path)
        skel_for_deform = data

    try:
        # ---- 維度 1–4：validator_v1.run_checks（單一真相來源）----
        r, _demoted, metrics = V1.run_checks(json_path, atlas_path,
                                             loop_anims=loop_anims, want_metric=want_stiffness)
        errors = list(r.errors)
        # 分類：末鍵 curve / cx 超界 = editor 匯入；其餘 = runtime 載入（schema / 引用完整性）
        editor_errors = [e for e in errors
                         if ("最後一鍵帶 curve" in e) or ("AIOOBE" in e) or ("bezier cx" in e)]
        runtime_errors = [e for e in errors if e not in editor_errors]
        loop_problems = [w[len("(v1 loop)"):].strip() if w.startswith("(v1 loop)") else w
                         for w in r.warnings if w.startswith("(v1 loop)")]

        d_runtime = {"pass": len(runtime_errors) == 0, "errors": runtime_errors}
        d_editor = {"pass": len(editor_errors) == 0, "errors": editor_errors}
        d_loop = {"pass": len(loop_problems) == 0, "problems": loop_problems,
                  "scope": loop_anims}
        finite = all(v == v and v != float("inf") for v in metrics.values())
        d_stiff = {"reported": want_stiffness, "all_finite": finite,
                   "per_anim": {k: round(float(v), 2) for k, v in metrics.items()},
                   "gating": stiffness_gate}

        # ---- 維度 5：deform_si（C1 紀律）----
        M = _mesh_module()
        mesh_reports, deform_ok = [], True
        for slot, att_key, att in _iter_mesh_attachments(data):
            name = att.get("name", att_key)
            if _is_weighted(att):
                # weighted skinning 變形 → C2 範疇；此統一閘只驗 schema、不列 si 硬閘。
                mesh_reports.append({
                    "slot": slot, "name": name, "weighted": True,
                    "note": "weighted mesh：逐骨 skinning 變形由 C2 weighted_deform_eval 把關，"
                            "本統一閘不列 si 硬閘（honest boundary）",
                    "gated": False})
                continue
            schema_ok, schema_probs = M.mesh_is_schema_valid(att)
            try:
                g = M.deform_si_gate(att, skel_for_deform, slot, name)
            except Exception as ex:  # noqa — 閘本身出錯視為該件 FAIL（可追溯）
                mesh_reports.append({"slot": slot, "name": name, "weighted": False,
                                     "gated": True, "schema_ok": schema_ok,
                                     "error": f"deform_si_gate 例外: {ex}", "clean": False})
                deform_ok = False
                continue
            clean = bool(g["clean"]) and schema_ok
            mesh_reports.append({
                "slot": slot, "name": name, "weighted": False, "gated": True,
                "schema_ok": schema_ok, "schema_problems": schema_probs,
                "has_real_deform": g["has_real_deform"], "frame": g["frame"],
                "self_intersections": g["self_intersections"],
                "triangle_flips": g["triangle_flips"], "degenerate": g["degenerate"],
                "area_ratio": (round(float(g["area_ratio"]), 3)
                               if g["area_ratio"] == g["area_ratio"] else None),
                "clean": clean})
            if not clean:
                deform_ok = False
        gated_meshes = [m for m in mesh_reports if m.get("gated")]
        d_deform = {"pass": deform_ok, "n_mesh": len(mesh_reports),
                    "n_gated": len(gated_meshes), "meshes": mesh_reports}

        # ---- overall：客觀硬閘維度（stiffness 預設不參與）----
        gating = [d_runtime["pass"], d_editor["pass"], d_loop["pass"], d_deform["pass"]]
        if stiffness_gate:
            gating.append(finite)
        overall = all(gating)

        return {
            "overall_pass": overall,
            "validator": "validator_v2 (統一品質閘 D1)",
            "source": str(skeleton) if isinstance(skeleton, (str, Path)) else "<in-memory dict>",
            "n_animations": len(data.get("animations", {})),
            "dimensions": {
                "runtime_loadable": d_runtime,
                "editor_importable": d_editor,
                "loop_closure": d_loop,
                "stiffness": d_stiff,
                "deform_si": d_deform,
            },
        }
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _print_summary(report):
    dims = report["dimensions"]
    print(f"=== validator_v2 on {report['source']} ===")
    print(f"  animations: {report['n_animations']}")
    def _mark(ok):
        return "PASS" if ok else "FAIL"
    print(f"  [1] runtime_loadable  : {_mark(dims['runtime_loadable']['pass'])}"
          f"  ({len(dims['runtime_loadable']['errors'])} errors)")
    for e in dims["runtime_loadable"]["errors"][:4]:
        print(f"        - {e}")
    print(f"  [2] editor_importable : {_mark(dims['editor_importable']['pass'])}"
          f"  ({len(dims['editor_importable']['errors'])} errors)")
    for e in dims["editor_importable"]["errors"][:4]:
        print(f"        - {e}")
    print(f"  [3] loop_closure      : {_mark(dims['loop_closure']['pass'])}"
          f"  ({len(dims['loop_closure']['problems'])} problems)")
    for p in dims["loop_closure"]["problems"][:4]:
        print(f"        - {p}")
    st = dims["stiffness"]
    gated = " (gating)" if st["gating"] else " (report-only)"
    print(f"  [4] stiffness         : finite={st['all_finite']}{gated}")
    for k, v in sorted(st["per_anim"].items(), key=lambda x: -x[1])[:6]:
        print(f"        {k:28s} {v:8.2f}")
    dd = dims["deform_si"]
    print(f"  [5] deform_si (C1)    : {_mark(dd['pass'])}"
          f"  ({dd['n_gated']}/{dd['n_mesh']} mesh gated)")
    for m in dd["meshes"][:8]:
        if m.get("weighted"):
            print(f"        - {m['slot']}/{m['name']}: weighted (schema-only, out of D1 scope)")
        else:
            print(f"        - {m['slot']}/{m['name']}: clean={m.get('clean')} "
                  f"si={m.get('self_intersections')} flips={m.get('triangle_flips')} "
                  f"real_deform={m.get('has_real_deform')} frame={m.get('frame')}")
    print()
    print(f"RESULT: {'ALL PASS' if report['overall_pass'] else 'FAIL'}")


def main(argv=None):
    ap = argparse.ArgumentParser(description="spine-ai-editor 2.0 統一品質閘 validator_v2")
    ap.add_argument("json", help="skeleton JSON 路徑")
    ap.add_argument("atlas", nargs="?", default=None, help="atlas 路徑（選配）")
    ap.add_argument("--loop-anims", default=None,
                    help="逗號分隔，只對這些動畫做 loop 閉合檢查（不給=全部）")
    ap.add_argument("--no-stiffness", action="store_true", help="不計算 stiffness")
    ap.add_argument("--stiffness-gate", action="store_true",
                    help="把 stiffness 有限性納入 overall（預設僅報告）")
    ap.add_argument("--json", dest="as_json", action="store_true", help="輸出完整 JSON 報告")
    a = ap.parse_args(argv)
    loop_anims = a.loop_anims.split(",") if a.loop_anims else None
    report = validate_v2(a.json, a.atlas, loop_anims=loop_anims,
                         want_stiffness=not a.no_stiffness, stiffness_gate=a.stiffness_gate)
    if a.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=float))
    else:
        _print_summary(report)
    return 0 if report["overall_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
