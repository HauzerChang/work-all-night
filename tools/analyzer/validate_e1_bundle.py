#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""E1 self-contained bundle 閘 — 證 spine-ai-editor 2.0 的生成/驗收碼**不再硬相依 repo `tools/`**
(MERGE_PLAN_2.0 Phase E / E1,滿足護欄 G5)。

**驗的是什麼(為何這個 chunk 有價值)**:
  B/C/D 把生成器(gen_lib.make_beat/sequence/mesh/rig)+ 統一閘(validator_v2)搬進 skill,但過渡期
  各模組的 `_wire_repo_tools()` 仍 import repo 的 `tools/analyzer`/`tools/mesh_gen`/`tools/rig`——
  **純使用者端(只拿到 skill 資料夾、沒有本 research repo)會 import 不到而爆**。E1 把這些生成碼的
  **trimmed copy(18 模組的 import 閉包)** bundle 進 `assets/gen_lib/_bundled/`,各 `_wire_repo_tools()`
  **優先用 bundle**、repo `tools/` 僅為 repo 環境 fallback。本閘證明:
    ① bundle 是 repo 原檔的**逐 byte 複製 + 閉包完整**(無漂移、無漏相依);
    ② 把 skill 的 `assets/` **複製到 repo 外、清掉 repo 於 sys.path** 後(= 模擬使用者端),
       gen_lib 生成 API 與 validator_v2 全六維度**仍可跑**,且相依**解析自 `_bundled/`**(非 repo);
    ③ **負對照**:把 `_bundled/` 刪掉 → 同樣的呼叫**失敗**(生成 ImportError、validator 維度 5/6 退 unavailable)
       → 證 bundle 是**承重**的(閘非恆真),self-containment 不是假性通過;
    ④ **零回歸**:rewire 後 repo 內既有閘(validate_b2_genlib)仍 PASS。

**AC(全部客觀、可機讀)**:
  E1-1 faithful_trimmed_copy : `_bundled/BUNDLE_MANIFEST.json` 列的每個模組,sha256 == 其 repo 原檔;
                               且對 `_bundled/` 重算 import 閉包 → 所有「本地(repo-tool)import」都落在 bundle 內
                               (閉包完整,無漏;且只搬了閉包 = trimmed)。
  E1-2 generation_self_contained(headline):
                               把 `assets/` 複製到 repo 外、subprocess 清 env(無 repo 於 sys.path)→
                               generate_bigwin / generate_idle / compose / crossfade / pivot 全跑成,
                               且 gen_animations / generate_mesh_v2 / generate_weighted_mesh 皆解析自 `_bundled/`,
                               sys.path 不含 repo `tools/`。
  E1-3 validator_self_contained:
                               同隔離環境 → validate_v2 對生成 beat 回 deform_si=na / c1=info / overall PASS
                               (維度 5/6 **wired**,非 unavailable);對 main_draw(4 真實 mesh)deform_si=**pass**;
                               mesh.deform_si_gate / rig.infer_limb_tree 直呼亦成(mesh_gen+rig 來自 bundle)。
  E1-4 negative_control      : 同隔離環境但**刪掉 `_bundled/`** → generate_bigwin / mesh / rig 皆 ImportError
                               (錯誤指名缺的模組/_bundled);validate_v2 維度 5/6 退 `unavailable` 但維度 1-4
                               仍 PASS(graceful,不整支 crash)→ 證 bundle 承重 + 閘非恆真。
  E1-5 zero_regression       : repo 環境下既有閘 `validate_b2_genlib.py` 仍 exit 0(rewire 未破壞 repo 側)。

用法:
  python3 validate_e1_bundle.py            # 跑 E1-1..E1-5,印精簡 pass/fail
  python3 validate_e1_bundle.py --json      # 完整 JSON 報告

退出碼 0 = 全 AC PASS;非 0 = 有 AC FAIL。
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILL_ASSETS = os.path.join(_REPO, "skills", "spine-ai-editor", "assets")
_BUNDLED = os.path.join(_SKILL_ASSETS, "gen_lib", "_bundled")
_MANIFEST = os.path.join(_BUNDLED, "BUNDLE_MANIFEST.json")
_MAIN_DRAW = os.path.join(_REPO, "assets", "main_draw.json")
_MAIN_ATLAS = os.path.join(_REPO, "assets", "main_draw.atlas")

_TOOL_DIRS = [os.path.join(_REPO, "tools", "analyzer"),
              os.path.join(_REPO, "tools", "mesh_gen"),
              os.path.join(_REPO, "tools", "rig")]


# ----------------------------------------------------------------- helpers
def _sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def _local_imports(path, modnames):
    """回傳 path 這支檔 import 的、且屬於 modnames(repo-tool 平面名)的模組集合。"""
    tree = ast.parse(open(path, encoding="utf-8").read())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:
                names.add(node.module.split(".")[0])
    return {n for n in names if n in modnames}


def _repo_tool_modmap():
    """repo 三個 tool 目錄的平面模組名 → 檔路徑。"""
    m = {}
    for d in _TOOL_DIRS:
        if not os.path.isdir(d):
            continue
        for fn in os.listdir(d):
            if fn.endswith(".py"):
                m.setdefault(fn[:-3], os.path.join(d, fn))
    return m


# ----------------------------------------------------------------- E1-1 faithful + complete closure
def ac_faithful_trimmed_copy():
    detail = {}
    if not os.path.isfile(_MANIFEST):
        return False, {"error": "BUNDLE_MANIFEST.json 不存在", "path": _MANIFEST}
    manifest = json.loads(open(_MANIFEST, encoding="utf-8").read())
    modmap = _repo_tool_modmap()

    # (a) 逐 byte 複製:bundle 檔 sha256 == repo 原檔,且 manifest.sha256 一致。
    mism = []
    bundled_names = set()
    for fname, info in sorted(manifest.items()):
        bname = fname[:-3]
        bundled_names.add(bname)
        bpath = os.path.join(_BUNDLED, fname)
        rpath = os.path.join(_REPO, info["from"])
        if not os.path.isfile(bpath):
            mism.append({"mod": fname, "why": "bundle 檔不存在"}); continue
        if not os.path.isfile(rpath):
            mism.append({"mod": fname, "why": "repo 原檔不存在: " + info["from"]}); continue
        bs, rs = _sha256(bpath), _sha256(rpath)
        if not (bs == rs == info["sha256"]):
            mism.append({"mod": fname, "bundle": bs[:12], "repo": rs[:12],
                         "manifest": info["sha256"][:12]})
    faithful = not mism

    # (b) 閉包完整:對 bundle 內每支檔重算「本地(repo-tool)import」,全部須已在 bundle。
    missing_dep = []
    for fname in sorted(manifest):
        bpath = os.path.join(_BUNDLED, fname)
        if not os.path.isfile(bpath):
            continue
        for dep in _local_imports(bpath, set(modmap)):
            if dep not in bundled_names:
                missing_dep.append({"in": fname, "needs": dep + " (未進 bundle)"})
    closure_complete = not missing_dep

    # (c) trimmed:bundle 模組數 << repo tool 模組數(只搬閉包)。
    trimmed = len(bundled_names) < len(modmap)

    detail.update({
        "bundled_count": len(bundled_names),
        "repo_tool_count": len(modmap),
        "sha256_mismatches": mism,
        "closure_missing_deps": missing_dep,
        "faithful": faithful, "closure_complete": closure_complete, "trimmed": trimmed,
    })
    return (faithful and closure_complete and trimmed), detail


# ----------------------------------------------------------------- isolated-run machinery
_DRIVER = r'''# -*- coding: utf-8 -*-
# 在「repo 外的 assets/ 複本」裡跑,模擬純使用者端(無 research repo)。
import sys, os, json, tempfile
HERE = os.path.dirname(os.path.abspath(__file__))     # TEMP 根(repo 外)
ASSETS = os.path.join(HERE, "assets")
sys.path.insert(0, ASSETS)                            # 只掛 skill 的 assets;其餘靠 _bundled 自 wire

out = {}
# sys.path 不該出現 repo 的 tools/(模擬使用者端)
out["sys_path_has_repo_tools"] = any(
    (os.sep + os.path.join("tools", "analyzer")) in p
    or (os.sep + os.path.join("tools", "mesh_gen")) in p
    or (os.sep + os.path.join("tools", "rig")) in p
    for p in sys.path)

def _under_bundled(f):
    return ("_bundled" + os.sep) in os.path.abspath(f)

def step(name, fn):
    try:
        out[name] = {"ok": True, "val": fn()}
    except Exception as e:
        out[name] = {"ok": False, "err": "{}: {}".format(type(e).__name__, str(e)[:240])}

def _first_mesh(data):
    skins = data.get("skins", {})
    it = ((s.get("name"), s.get("attachments", {})) for s in skins) if isinstance(skins, list) \
        else skins.items()
    for _n, atts in it:
        for slot, sa in atts.items():
            for k, a in sa.items():
                if isinstance(a, dict) and a.get("type") == "mesh":
                    return slot, a.get("name", k), a
    return None

def gen():
    import gen_lib.make_beat as MB
    from gen_lib import compose_bigwin_sequence, crossfade_bigwin_sequence
    import gen_lib.pivot_axis as PV
    import gen_lib.mesh as MESH
    import gen_lib.rig as RIG
    sk, an = MB.generate_bigwin(MB.DEMO_PARTS, beat="cascade")
    idle, iname = MB.generate_idle(MB.IDLE_DEMO_PARTS)
    cseq = compose_bigwin_sequence(MB.DEMO_PARTS)
    xseq = crossfade_bigwin_sequence(MB.DEMO_PARTS)
    origins = PV.bone_origins_from_skel(idle)          # pivot 入口可呼叫
    G, ct = MB._wire_repo_tools()
    GM, DE, AC = MESH._wire_repo_tools()
    Gw, W, ip, it = RIG._wire_repo_tools()
    prov = {"gen_animations": _under_bundled(G.__file__),
            "generate_mesh_v2": _under_bundled(GM.__file__),
            "generate_weighted_mesh": _under_bundled(Gw.__file__)}
    return {"bigwin_bones": len(sk["bones"]), "bigwin_anim": an,
            "bigwin_schema_ok": bool(sk.get("bones") and sk.get("animations", {}).get(an)),
            "idle": iname, "compose_anims": list(cseq[0]["animations"].keys()) if isinstance(cseq, tuple) else None,
            "crossfade_ok": bool(xseq), "pivot_origins": len(origins),
            "provenance_all_bundled": all(prov.values()), "prov": prov}

def mesh_rig():
    import gen_lib.mesh as MESH, gen_lib.rig as RIG
    data = json.load(open(os.path.join(HERE, "main_draw.json"), encoding="utf-8"))
    slot, name, att = _first_mesh(data)
    g = MESH.deform_si_gate(att, data, slot, name)
    parts = RIG.make_chain_parts()
    root, tree, meta = RIG.infer_limb_tree(parts)
    return {"mesh_slot": slot, "mesh_clean": bool(g.get("clean")),
            "mesh_has_real_deform": bool(g.get("has_real_deform")),
            "rig_root": root}

def validator_full():
    from validator_v2 import validate_v2
    beat = validate_v2(os.path.join(HERE, "beat.json"))
    md = validate_v2(os.path.join(HERE, "main_draw.json"))
    return {"beat_overall": beat["overall_pass"],
            "beat_deform_si": beat["dimensions"]["deform_si"]["status"],
            "beat_c1": beat["dimensions"]["c1_continuity"]["status"],
            "beat_runtime": beat["dimensions"]["runtime_loadable"]["status"],
            "beat_editor": beat["dimensions"]["editor_importable"]["status"],
            "beat_loop": beat["dimensions"]["loop_closure"]["status"],
            "maindraw_deform_si": md["dimensions"]["deform_si"]["status"]}

step("gen", gen)
step("mesh_rig", mesh_rig)
step("validator_full", validator_full)       # validate_v2 自身不 raise(wiring 失敗 → unavailable)
print("@@RESULT@@" + json.dumps(out))
'''


def _setup_isolated(remove_bundle):
    """把 skill 的 assets/ 複製到 repo 外的 TEMP,附 beat.json + main_draw.{json,atlas} + driver.py。
    remove_bundle=True → 刪掉複本的 _bundled/(負對照)。回傳 TEMP 路徑。"""
    tmp = tempfile.mkdtemp(prefix="e1_iso_")
    shutil.copytree(_SKILL_ASSETS, os.path.join(tmp, "assets"),
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    if remove_bundle:
        shutil.rmtree(os.path.join(tmp, "assets", "gen_lib", "_bundled"))
    # beat.json:在 repo 內先生成一支 region-only 大獎 beat,複製進隔離環境(負對照也拿得到)。
    _ensure_beat_json(os.path.join(tmp, "beat.json"))
    shutil.copy2(_MAIN_DRAW, os.path.join(tmp, "main_draw.json"))
    if os.path.isfile(_MAIN_ATLAS):
        shutil.copy2(_MAIN_ATLAS, os.path.join(tmp, "main_draw.atlas"))
    with open(os.path.join(tmp, "driver.py"), "w", encoding="utf-8") as f:
        f.write(_DRIVER)
    return tmp


def _ensure_beat_json(dst):
    """用 repo 內的 gen_lib 生成一支大獎 beat 寫到 dst(供隔離環境的 validator 讀)。"""
    if _SKILL_ASSETS not in sys.path:
        sys.path.insert(0, _SKILL_ASSETS)
    from gen_lib.make_beat import generate_bigwin, DEMO_PARTS
    skel, _ = generate_bigwin(DEMO_PARTS, beat="cascade")
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(skel, f, ensure_ascii=False, indent=1)


def _run_isolated(remove_bundle):
    tmp = _setup_isolated(remove_bundle)
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)          # 不讓外部 PYTHONPATH 洩漏 repo
    try:
        proc = subprocess.run([sys.executable, os.path.join(tmp, "driver.py")],
                              cwd=tmp, env=env, capture_output=True, text=True, timeout=600)
    finally:
        pass
    parsed = None
    for line in proc.stdout.splitlines():
        if line.startswith("@@RESULT@@"):
            parsed = json.loads(line[len("@@RESULT@@"):])
    return {"returncode": proc.returncode, "result": parsed,
            "stderr_tail": proc.stderr.strip().splitlines()[-3:] if proc.stderr else [],
            "tmp": tmp}


# ----------------------------------------------------------------- E1-2 / E1-3 positive
def ac_positive(iso_pos):
    r = iso_pos.get("result") or {}
    gen = r.get("gen", {})
    gv = gen.get("val", {})
    gen_ok = (gen.get("ok") is True
              and gv.get("bigwin_schema_ok") is True
              and gv.get("provenance_all_bundled") is True
              and r.get("sys_path_has_repo_tools") is False
              and gv.get("idle") == "Loop"
              and bool(gv.get("crossfade_ok")))
    return gen_ok, {"gen_ok": gen.get("ok"), "schema_ok": gv.get("bigwin_schema_ok"),
                    "provenance": gv.get("prov"), "sys_path_has_repo_tools": r.get("sys_path_has_repo_tools"),
                    "idle": gv.get("idle"), "compose_anims": gv.get("compose_anims"),
                    "pivot_origins": gv.get("pivot_origins"),
                    "gen_err": gen.get("err")}


def ac_validator_positive(iso_pos):
    r = iso_pos.get("result") or {}
    mr = r.get("mesh_rig", {}); mv = mr.get("val", {})
    vf = r.get("validator_full", {}); vv = vf.get("val", {})
    mesh_rig_ok = (mr.get("ok") is True and mv.get("mesh_clean") is True
                   and mv.get("mesh_has_real_deform") is True and bool(mv.get("rig_root")))
    validator_ok = (vf.get("ok") is True
                    and vv.get("beat_deform_si") == "na"
                    and vv.get("beat_c1") == "info"
                    and vv.get("beat_overall") is True
                    and vv.get("maindraw_deform_si") == "pass")
    ok = mesh_rig_ok and validator_ok
    return ok, {"mesh_rig_ok": mesh_rig_ok, "mesh": mv, "mesh_err": mr.get("err"),
                "validator": vv, "validator_err": vf.get("err")}


# ----------------------------------------------------------------- E1-4 negative control
def ac_negative(iso_neg):
    r = iso_neg.get("result") or {}
    gen = r.get("gen", {})
    mr = r.get("mesh_rig", {})
    vf = r.get("validator_full", {}); vv = vf.get("val", {})
    # 生成 / mesh / rig 都該 ImportError
    gen_failed = gen.get("ok") is False and "Error" in (gen.get("err") or "")
    mesh_failed = mr.get("ok") is False
    # validate_v2 graceful:維度 5/6 unavailable、但 1-4 仍 pass、overall(硬閘 1-4)仍 True
    validator_degraded = (vf.get("ok") is True
                          and vv.get("beat_deform_si") == "unavailable"
                          and vv.get("beat_c1") == "unavailable"
                          and vv.get("beat_runtime") == "pass"
                          and vv.get("beat_editor") == "pass"
                          and vv.get("beat_overall") is True
                          and vv.get("maindraw_deform_si") == "unavailable")
    ok = gen_failed and mesh_failed and validator_degraded
    return ok, {"gen_failed": gen_failed, "gen_err": gen.get("err"),
                "mesh_failed": mesh_failed, "mesh_err": mr.get("err"),
                "validator_degraded": validator_degraded, "validator": vv}


# ----------------------------------------------------------------- E1-5 zero regression
def ac_zero_regression():
    gate = os.path.join(_HERE, "validate_b2_genlib.py")
    proc = subprocess.run([sys.executable, gate], cwd=_REPO,
                          capture_output=True, text=True, timeout=600)
    ok = proc.returncode == 0
    return ok, {"gate": "validate_b2_genlib.py", "returncode": proc.returncode,
                "stdout_tail": proc.stdout.strip().splitlines()[-2:] if proc.stdout else []}


# ----------------------------------------------------------------- orchestrate
def run_all():
    res = {}
    res["E1-1_faithful_trimmed_copy"] = ac_faithful_trimmed_copy()

    iso_pos = _run_isolated(remove_bundle=False)
    res["E1-2_generation_self_contained"] = ac_positive(iso_pos)
    res["E1-3_validator_self_contained"] = ac_validator_positive(iso_pos)

    iso_neg = _run_isolated(remove_bundle=True)
    res["E1-4_negative_control"] = ac_negative(iso_neg)

    res["E1-5_zero_regression"] = ac_zero_regression()

    # cleanup iso temp dirs
    for iso in (iso_pos, iso_neg):
        try:
            shutil.rmtree(iso["tmp"])
        except Exception:
            pass

    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "E1 self-contained bundle: 生成/驗收碼 bundle 進 assets/gen_lib/_bundled,移除 repo tools/ 硬相依(G5)",
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
