#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E1 self-contained bundle 閘 — 證 spine-ai-editor 2.0 的生成碼**不再相依 repo `tools/`**
(MERGE_PLAN_2.0 Phase E1，護欄 G5)。

**驗的是什麼(為何這個 chunk 有價值)**：
  B/C/D 把 repo 的生成引擎 + 評估器紀律搬進 `skills/spine-ai-editor/assets/gen_lib`，但各
  `_wire_repo_tools()` 在**過渡期**仍 `sys.path` 掛 repo 的 `tools/analyzer`、`tools/mesh_gen`、`tools/rig`。
  部署到使用者端時 skill 只帶 `skills/spine-ai-editor/`，**沒有** repo 的 `tools/` → 那些 import 會炸。
  E1 把需要的 13 個 repo 模組以 **verbatim copy** bundle 進 `gen_lib/_bundled/`，並把 4 個
  `_wire_repo_tools()`(make_beat / mesh / rig / validator_v2)改指向 `_bundled/`。本閘證明:
  **(頭條)把 `assets/` 整份複製到 repo 樹之外、sys.path 不含任何 repo `tools/`，生成 + 雙真值驗收 pipeline 仍能跑**。

**AC(全部客觀、可機讀)**：
  E1-1 bundle-complete : `_bundled/` 含全部 13 個必要模組;4 個 `_wire_repo_tools()` 原始碼**不再出現**
                         repo `tools/` 路徑(("tools","analyzer")/("tools","mesh_gen")/("tools","rig"))且引用 `_bundled`。
  E1-2 isolated-pipeline(headline): 把 `assets/` 複製到 **/tmp(repo 樹外)**,subprocess `python3 -I`
                         cwd=該目錄、sys.path 僅含複製出的 assets(剝除所有 repo 路徑)→
                         `write_bigwin` 產大獎 beat → `validator_v1` **0 error** → `validator_v2` **overall PASS**。
  E1-3 isolated-mesh-rig: 同一隔離環境下 `gen_lib.mesh` / `gen_lib.rig` 的 `_wire_repo_tools()` 皆成功,
                         回傳模組 `__file__` **落在 `_bundled/`**(非 repo tools/);rig `infer_limb_tree`
                         對合成鏈 recover 成鏈、對合成星形 recover 成星形(純 CPU、無真實資產)。
  E1-4 byte-identical  : `_bundled/` 每檔與其 repo 原檔**逐 byte 相同**(不產生第二份真值;守住 re-sync 不漂移)。
  E1-5 teeth           : (a)負對照——把隔離副本的某個必要 bundled 模組移走 → 隔離 import **失敗**
                         (證隔離測試確實隔離、且 bundle 集**最小完整**,非被環境同名模組偷渡);
                         (b)wired 模組 provenance——隔離環境下 make_beat 取到的 `gen_animations.__file__`
                         落在 `_bundled/`(證 rewire 確實生效,非仍偷用 repo)。

用法：
  python3 validate_e1_bundle.py            # 跑 E1-1..E1-5,印精簡 pass/fail
  python3 validate_e1_bundle.py --json      # 完整 JSON 報告

退出碼 0 = 全 AC PASS;非 0 = 有 AC FAIL。
"""
from __future__ import annotations
import argparse
import filecmp
import json
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILL_ASSETS = os.path.join(_REPO, "skills", "spine-ai-editor", "assets")
_GEN_LIB = os.path.join(_SKILL_ASSETS, "gen_lib")
_BUNDLED = os.path.join(_GEN_LIB, "_bundled")

# bundled 檔 → repo 原檔(真值來源;E1-4 byte-compare 依此)
_PROVENANCE = {
    "gen_animations.py":       os.path.join(_REPO, "tools", "analyzer", "gen_animations.py"),
    "beat_templates.py":       os.path.join(_REPO, "tools", "analyzer", "beat_templates.py"),
    "tier_variants.py":        os.path.join(_REPO, "tools", "analyzer", "tier_variants.py"),
    "spine_anim.py":           os.path.join(_REPO, "tools", "analyzer", "spine_anim.py"),
    "pivot_rotation.py":       os.path.join(_REPO, "tools", "analyzer", "pivot_rotation.py"),
    "generate_mesh_v2.py":     os.path.join(_REPO, "tools", "mesh_gen", "generate_mesh_v2.py"),
    "generate_mesh.py":        os.path.join(_REPO, "tools", "mesh_gen", "generate_mesh.py"),
    "deform_eval.py":          os.path.join(_REPO, "tools", "mesh_gen", "deform_eval.py"),
    "atlas_crop.py":           os.path.join(_REPO, "tools", "mesh_gen", "atlas_crop.py"),
    "generate_weighted_mesh.py": os.path.join(_REPO, "tools", "mesh_gen", "generate_weighted_mesh.py"),
    "weighted_deform_eval.py": os.path.join(_REPO, "tools", "mesh_gen", "weighted_deform_eval.py"),
    "infer_pivots.py":         os.path.join(_REPO, "tools", "rig", "infer_pivots.py"),
    "infer_tree.py":           os.path.join(_REPO, "tools", "rig", "infer_tree.py"),
}

# 隔離子程序腳本:cwd 與 sys.path 皆在 repo 樹外,只掛複製出的 assets。
# argv[1]=複製出的 assets 絕對路徑;印出一行 JSON 結果。
_ISO_SCRIPT = r'''
import sys, os, json, tempfile
ASSETS = sys.argv[1]
GEN = os.path.join(ASSETS, "gen_lib")
BUNDLED = os.path.join(GEN, "_bundled")
# 只留非 repo 的系統路徑 + 複製出的 assets;嚴格剝除任何 work-all-night 殘留
clean = [p for p in sys.path if "work-all-night" not in p and ASSETS not in p]
sys.path = [GEN, ASSETS, BUNDLED] + clean
out = {"import_ok": False}
try:
    from gen_lib.make_beat import write_bigwin, DEMO_PARTS, _wire_repo_tools as mb_wire
    from gen_lib.mesh import _wire_repo_tools as mesh_wire
    from gen_lib.rig import (_wire_repo_tools as rig_wire,
                             make_chain_parts, make_star_parts, infer_limb_tree)
    from validator_v1 import validate_v1
    from validator_v2 import validate_v2
    out["import_ok"] = True

    # --- headline pipeline ---
    d = tempfile.mkdtemp()
    outp = os.path.join(d, "bw.json")
    outp, aname = write_bigwin(DEMO_PARTS, outp, beat="cascade")
    r1, _demo, metrics = validate_v1(outp, None, ["cascade"], want_metric=True)
    rep = validate_v2(outp, None, ["cascade"])
    out["v1_errors"] = len(r1.errors)
    out["v1_error_sample"] = list(r1.errors)[:3]
    out["v2_overall"] = bool(rep["overall_pass"])
    out["v2_dims"] = {k: v.get("status") for k, v in rep["dimensions"].items()}
    out["stiffness"] = {k: round(v, 2) for k, v in metrics.items()}

    # --- mesh/rig wire provenance (__file__ must be under _bundled) ---
    G, _ct = mb_wire()
    GM, _DE, _AC = mesh_wire()
    WG, _W, _ip, _it = rig_wire()
    def _under_bundled(mod):
        f = os.path.abspath(getattr(mod, "__file__", ""))
        return f.startswith(os.path.abspath(BUNDLED))
    out["genanim_under_bundled"] = _under_bundled(G)
    out["meshgen_under_bundled"] = _under_bundled(GM)
    out["wmesh_under_bundled"] = _under_bundled(WG)
    out["genanim_file"] = os.path.abspath(getattr(G, "__file__", ""))

    # --- rig inference (pure CPU, no real assets) ---
    cp = make_chain_parts(); croot, ctree, _ci = infer_limb_tree(cp)
    sp = make_star_parts(); sroot, stree, _si = infer_limb_tree(sp)
    out["chain_root"] = croot
    out["chain_is_chain"] = (croot == "torso" and ctree.get("lower") == "upper")
    out["star_is_star"] = (sroot == "torso" and all(v == "torso" for v in stree.values()))
except Exception as e:
    import traceback
    out["error"] = "{}: {}".format(type(e).__name__, e)
    out["trace"] = traceback.format_exc().splitlines()[-4:]
print("E1_RESULT " + json.dumps(out, ensure_ascii=False))
'''


def _run_isolated(assets_dir, drop_module=None):
    """把 assets_dir 複製到 repo 樹外的 /tmp,在隔離 subprocess 跑 _ISO_SCRIPT。
    drop_module!=None 時先移走該 bundled 模組(負對照)。回傳解析出的 dict(或含 error)。"""
    work = tempfile.mkdtemp(prefix="e1_iso_")      # /tmp/... 必在 repo 樹外
    dst = os.path.join(work, "assets")
    shutil.copytree(assets_dir, dst)
    if drop_module:
        victim = os.path.join(dst, "gen_lib", "_bundled", drop_module)
        if os.path.exists(victim):
            os.remove(victim)
    script = os.path.join(work, "iso_run.py")
    with open(script, "w", encoding="utf-8") as f:
        f.write(_ISO_SCRIPT)
    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}
    try:
        proc = subprocess.run([sys.executable, "-I", script, dst],
                              cwd=work, capture_output=True, text=True,
                              timeout=180, env=env)
    except subprocess.TimeoutExpired:
        return {"import_ok": False, "error": "timeout"}
    finally:
        pass
    line = None
    for ln in proc.stdout.splitlines():
        if ln.startswith("E1_RESULT "):
            line = ln[len("E1_RESULT "):]
    if line is None:
        return {"import_ok": False, "error": "no result line",
                "stdout_tail": proc.stdout.splitlines()[-5:],
                "stderr_tail": proc.stderr.splitlines()[-5:]}
    try:
        return json.loads(line)
    except Exception as e:                           # noqa: BLE001
        return {"import_ok": False, "error": "bad json: {}".format(e)}
    # (cleanup left to OS /tmp; subprocess output already captured)


def _wire_srcs():
    """回傳 {label: 原始碼字串} —— 4 個 _wire_repo_tools() 所在檔。"""
    out = {}
    for label, path in (
        ("make_beat", os.path.join(_GEN_LIB, "make_beat.py")),
        ("mesh", os.path.join(_GEN_LIB, "mesh.py")),
        ("rig", os.path.join(_GEN_LIB, "rig.py")),
        ("validator_v2", os.path.join(_SKILL_ASSETS, "validator_v2.py")),
    ):
        with open(path, encoding="utf-8") as f:
            out[label] = f.read()
    return out


def run_all():
    res = {}

    # ---- E1-1 bundle-complete + wire 不再指 repo tools/ ----
    missing = [m for m in _PROVENANCE if not os.path.exists(os.path.join(_BUNDLED, m))]
    # 檢查 4 個 wire 函式所在檔:不得再出現 repo tools 路徑 tuple,且需引用 _bundled
    repo_markers = ('"tools", "analyzer"', '"tools", "mesh_gen"', '"tools", "rig"')
    srcs = _wire_srcs()
    still_repo = {}
    for label, src in srcs.items():
        hits = [m for m in repo_markers if m in src]
        if hits:
            still_repo[label] = hits
    refs_bundled = {label: ("_bundled" in src) for label, src in srcs.items()}
    e1_1 = (not missing) and (not still_repo) and all(refs_bundled.values())
    res["E1-1_bundle_complete"] = (e1_1, {
        "bundled_count": len(_PROVENANCE) - len(missing),
        "missing": missing,
        "wire_still_reference_repo_tools": still_repo,
        "wire_reference_bundled": refs_bundled,
    })

    # ---- E1-2 isolated pipeline (headline) ----
    iso = _run_isolated(_SKILL_ASSETS)
    e1_2 = (iso.get("import_ok") and iso.get("v1_errors") == 0
            and iso.get("v2_overall") is True)
    res["E1-2_isolated_pipeline"] = (e1_2, {
        "import_ok": iso.get("import_ok"),
        "v1_errors": iso.get("v1_errors"),
        "v1_error_sample": iso.get("v1_error_sample"),
        "v2_overall": iso.get("v2_overall"),
        "v2_dims": iso.get("v2_dims"),
        "stiffness": iso.get("stiffness"),
        "error": iso.get("error"),
        "trace": iso.get("trace"),
    })

    # ---- E1-3 isolated mesh/rig (wire provenance + rig inference) ----
    e1_3 = (iso.get("import_ok")
            and iso.get("genanim_under_bundled") is True
            and iso.get("meshgen_under_bundled") is True
            and iso.get("wmesh_under_bundled") is True
            and iso.get("chain_is_chain") is True
            and iso.get("star_is_star") is True)
    res["E1-3_isolated_mesh_rig"] = (e1_3, {
        "genanim_under_bundled": iso.get("genanim_under_bundled"),
        "meshgen_under_bundled": iso.get("meshgen_under_bundled"),
        "wmesh_under_bundled": iso.get("wmesh_under_bundled"),
        "chain_is_chain": iso.get("chain_is_chain"),
        "star_is_star": iso.get("star_is_star"),
        "chain_root": iso.get("chain_root"),
    })

    # ---- E1-4 byte-identical to repo originals ----
    diffs = []
    for name, repo_src in _PROVENANCE.items():
        b = os.path.join(_BUNDLED, name)
        if not (os.path.exists(b) and os.path.exists(repo_src) and filecmp.cmp(b, repo_src, shallow=False)):
            diffs.append(name)
    e1_4 = not diffs
    res["E1-4_byte_identical"] = (e1_4, {
        "checked": len(_PROVENANCE), "diffs": diffs,
    })

    # ---- E1-5 teeth: (a) drop a module breaks the isolated pipeline; (b) wire provenance under _bundled ----
    # 移走 gen_animations.py 後,make_beat 仍能 import(wire 是 lazy),但一呼叫生成就會在
    # _wire_repo_tools() 丟出「需要 self-contained bundle」ImportError → pipeline 無法產出 v2_overall。
    # 這正是 E1 修掉的「import 不存在的 tools/」情境:證隔離測試有牙、bundle 集最小完整。
    neg = _run_isolated(_SKILL_ASSETS, drop_module="gen_animations.py")
    drop_breaks = (neg.get("v2_overall") is not True) and bool(neg.get("error"))
    provenance_ok = iso.get("genanim_under_bundled") is True
    e1_5 = drop_breaks and provenance_ok
    res["E1-5_teeth"] = (e1_5, {
        "drop_gen_animations_breaks_pipeline": drop_breaks,
        "neg_v2_overall": neg.get("v2_overall"),
        "neg_error": neg.get("error") or (neg.get("trace") or [None])[-1],
        "wired_genanim_file": iso.get("genanim_file"),
        "wired_genanim_under_bundled": provenance_ok,
    })

    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "E1 self-contained bundle:gen_lib 生成碼 bundle 進 _bundled/,移除對 repo tools/ 的硬相依(G5)",
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
