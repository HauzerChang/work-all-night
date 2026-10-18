# -*- coding: utf-8 -*-
"""validate_e1_selfcontained — MERGE_PLAN Phase E1 閘(spine-ai-editor 2.0,2026-10-18)。

E1 的 chunk 目標:把生成/評估引擎 bundle 進 `skills/spine-ai-editor/assets/gen_lib/_bundled/`
(repo `tools/` 的逐位元複本),讓 skill **self-contained**——使用者端只裝 skill、沒有本
research repo 的 `tools/` 目錄,也能跑完整的確定性大獎生成 + 變形/rig/序列閘(滿足 MERGE_PLAN G5)。

== 為何這樣驗(AC 設計理念)==
  * **逐位元複本 → 零回歸(by construction)**:bundle 與 repo 來源 byte-identical,in-repo 既有
    B/C/D 閘行為不變(E1-5 實測)。
  * **完整性 → external 隔離測試**:把整個 `assets/` 複製到 **repo 外**、`PYTHONPATH` 只給複製出的
    assets、cwd 設在中性空目錄(無 repo 在 import path)→ 跑 gen_lib 五模組公開 API + validator_v2;
    **再掃 `sys.modules`:任何 __file__ 落在 repo 內的載入 = self-contained 洩漏**(E1-2)。
  * **閘非恆真**:移掉 `_bundled/` → external 生成必須 ImportError 失敗(E1-3),證明生成確實靠 bundle,
    不是某個環境 fallback 在撐。

== 5 AC ==
  E1-1 bundle 完整 + 逐位元:13 個預期模組齊備、與 repo 來源 byte-identical、無未登錄的額外 .py。
  E1-2 (headline) external self-contained:repo 外跑 gen_lib(beat×4 / idle+pivot / mesh / rig / sequence)
       + validator_v2,全成功 + **零 repo import 洩漏** + validator_v2 維度 5/6 非 unavailable。
  E1-3 negative control:external 複本移掉 `_bundled/` → 生成 ImportError 失敗(非恆真)。
  E1-4 validator_v2 external 6 維度:在 external 複本對生成 beat 跑 validate_v2,硬閘維度 pass、
       deform_si/c1 可用(非 unavailable)、overall 有結論。
  E1-5 in-repo 零回歸:既有 B2/B3/B4/C1/C2/D1 六閘 in-repo 仍全 PASS(wire 改寫無行為漂移)。
"""
from __future__ import annotations
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

# bundle 模組 → repo 來源(E1-1 逐位元校驗的真值對照)。
_MANIFEST = {
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


def _sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


# --------------------------------------------------------------------- external driver(字串)
# 在 repo 外、PYTHONPATH 只有複製出的 assets 下執行。退出碼 0=全過;非 0=失敗。
# 用純 python3(非 -I):-I 會忽略 PYTHONPATH;此處 cwd 設中性空目錄 + env 乾淨 → 無 repo 在 path。
_EXT_DRIVER = r'''
import os, sys, json, tempfile
import numpy as np, cv2

REPO = os.environ.get("E1_REPO_REAL", "")
out = {"steps": {}, "leaks": [], "beats": {}, "ok": True}

def _fail(tag, e):
    out["steps"][tag] = "ERR: %s: %s" % (type(e).__name__, e)
    out["ok"] = False

# ---- 載入 skill(只從 PYTHONPATH 的 external assets)----
try:
    import gen_lib  # noqa
    from gen_lib.make_beat import generate_bigwin, generate_idle, DEMO_PARTS, IDLE_DEMO_PARTS
    from gen_lib.pivot_axis import apply_joint_pivots, bone_origins_from_skel
    from gen_lib import mesh as M, rig as R, sequence as SEQ
    import validator_v2 as V2
    out["steps"]["import"] = "ok"
except Exception as e:
    _fail("import", e)
    print("E1_RESULT_JSON=" + json.dumps(out)); sys.exit(3)

tmp = tempfile.mkdtemp()

# ---- beat ×4 → validator_v2(G2 雙真值 + 維度 5/6 可用)----
try:
    for b in ("cascade", "pop", "wobble", "twist"):
        sk, an = generate_bigwin(DEMO_PARTS, beat=b)
        p = os.path.join(tmp, "beat_%s.json" % b)
        json.dump(sk, open(p, "w"))
        rep = V2.validate_v2(p)
        d = rep["dimensions"]
        out["beats"][b] = {k: d[k]["status"] for k in
                           ("runtime_loadable", "editor_importable", "loop_closure",
                            "deform_si", "c1_continuity")}
        out["beats"][b]["overall"] = rep["overall_pass"]
        assert d["runtime_loadable"]["status"] == "pass", "runtime not pass: " + b
        assert d["editor_importable"]["status"] == "pass", "editor not pass: " + b
        # 維度 5/6 必須 **可用**(非 unavailable)→ validator_v2 的 bundle wire 成功
        assert d["deform_si"]["status"] != "unavailable", "deform_si unavailable: " + b
        assert d["c1_continuity"]["status"] != "unavailable", "c1 unavailable: " + b
        assert rep["overall_pass"] is True, "overall not pass: " + b
    out["steps"]["beats_validate_v2"] = "ok"
except Exception as e:
    _fail("beats_validate_v2", e)

# ---- idle + 繞關節 pivot(B3 軸)----
try:
    sk, an = generate_idle(IDLE_DEMO_PARTS)
    origins = bone_origins_from_skel(sk)
    pivots = {}
    for bn in sk["bones"]:
        if bn["name"].startswith("b_arm"):
            ox, oy = origins.get(bn["name"], (0.0, 0.0))
            pivots[bn["name"]] = (ox, oy - 40.0)
    assert pivots, "no limb bone found"
    turned = apply_joint_pivots(sk, an, pivots)
    assert turned, "no bone turned"
    out["steps"]["idle_pivot"] = "ok (turned=%s)" % sorted(turned)
except Exception as e:
    _fail("idle_pivot", e)

# ---- mesh 生成(合成 mask,無 repo 資料)----
try:
    img = np.zeros((220, 90, 4), np.uint8)
    cv2.ellipse(img, (45, 110), (32, 100), 0, 0, 360, (255, 255, 255, 255), -1)
    pp = os.path.join(tmp, "part.png"); cv2.imwrite(pp, img)
    m = M.generate_part_mesh(pp)
    ok, probs = M.mesh_is_schema_valid(m)
    assert ok, "mesh schema: %s" % probs
    out["steps"]["mesh_generate"] = "ok (nv=%d hull=%d)" % (len(m["uvs"]) // 2, m["hull"])
except Exception as e:
    _fail("mesh_generate", e)

# ---- rig 推斷(合成 chain,無 repo 資料)----
try:
    parts = R.make_chain_parts()
    rig = R.rig_from_parts(parts)
    assert rig["root"] == "torso", "root=%s" % rig["root"]
    assert set(rig["tree"].keys()) == {"upper", "lower"}, "tree=%s" % rig["tree"]
    out["steps"]["rig_infer"] = "ok (root=%s)" % rig["root"]
except Exception as e:
    _fail("rig_infer", e)

# ---- sequence compose/crossfade + write → validate_v2 ----
try:
    order = ["cascade", "pop"]
    SEQ.compose_bigwin_sequence(DEMO_PARTS, order=order)
    SEQ.crossfade_bigwin_sequence(DEMO_PARTS, order=order)
    sp = os.path.join(tmp, "seq.json")
    SEQ.write_sequence(DEMO_PARTS, sp, mode="compose", order=order)
    rep = V2.validate_v2(sp)
    assert rep["dimensions"]["editor_importable"]["status"] == "pass", "seq editor"
    out["steps"]["sequence"] = "ok"
except Exception as e:
    _fail("sequence", e)

# ---- SELF-CONTAINMENT:掃 sys.modules,任何 __file__ 落在 repo = 洩漏 ----
if REPO:
    rp = os.path.realpath(REPO) + os.sep
    for name, mod in list(sys.modules.items()):
        f = getattr(mod, "__file__", None)
        if not f:
            continue
        if os.path.realpath(f).startswith(rp):
            out["leaks"].append([name, os.path.realpath(f)])
    if out["leaks"]:
        out["ok"] = False

print("E1_RESULT_JSON=" + json.dumps(out))
sys.exit(0 if out["ok"] else 3)
'''

# negative-control driver:移掉 bundle 後,生成必須失敗。
_NEG_DRIVER = r'''
import json, sys
try:
    from gen_lib.make_beat import generate_bigwin, DEMO_PARTS
    generate_bigwin(DEMO_PARTS, beat="cascade")
    print("NEG_RESULT=unexpected_success")
    sys.exit(0)
except Exception as e:
    print("NEG_RESULT=expected_failure: %s: %s" % (type(e).__name__, e))
    sys.exit(7)
'''


def _run_external(assets_copy, driver, with_bundle=True):
    """在 repo 外跑 driver;PYTHONPATH 只給 assets_copy、cwd 中性空目錄、env 乾淨。
    回傳 (returncode, stdout, stderr)。"""
    neutral = tempfile.mkdtemp(prefix="e1_cwd_")
    drv = os.path.join(neutral, "driver.py")
    with open(drv, "w", encoding="utf-8") as f:
        f.write(driver)
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "PYTHONPATH": assets_copy,                  # 只有複製出的 assets
        "E1_REPO_REAL": os.path.realpath(_REPO),    # 給 driver 判洩漏
        "HOME": os.environ.get("HOME", neutral),
    }
    # 保留 pip/site 安裝的 numpy/cv2 路徑(若在非標準位置)
    for k in ("VIRTUAL_ENV", "PYTHONHOME"):
        if k in os.environ:
            env[k] = os.environ[k]
    p = subprocess.run([sys.executable, drv], cwd=neutral, env=env,
                       capture_output=True, text=True, timeout=900)
    return p.returncode, p.stdout, p.stderr


def _parse_json_line(stdout, prefix):
    for ln in stdout.splitlines():
        if ln.startswith(prefix):
            return json.loads(ln[len(prefix):])
    return None


def main():
    res = {}

    # ===== E1-1 bundle 完整 + 逐位元 =====
    try:
        present = {fn for fn in os.listdir(_BUNDLED) if fn.endswith(".py")}
        expected = set(_MANIFEST)
        missing = sorted(expected - present)
        extra = sorted(present - expected)                 # 未登錄的額外 .py
        identical = []
        mismatched = []
        for fn, src in _MANIFEST.items():
            dst = os.path.join(_BUNDLED, fn)
            if not os.path.exists(dst) or not os.path.exists(src):
                mismatched.append(fn + " (缺檔)")
                continue
            if _sha(dst) == _sha(src):
                identical.append(fn)
            else:
                mismatched.append(fn)
        e11 = (not missing) and (not extra) and (not mismatched) and len(identical) == len(_MANIFEST)
        res["E1-1_bundle_verbatim"] = {
            "pass": bool(e11), "n_identical": len(identical),
            "missing": missing, "extra_py": extra, "mismatched": mismatched,
        }
    except Exception as e:                              # noqa: BLE001
        res["E1-1_bundle_verbatim"] = {"pass": False, "error": "%s: %s" % (type(e).__name__, e)}

    # 準備 external 複本(E1-2/E1-4 共用;E1-3 另一份刪 bundle)
    tmp_root = tempfile.mkdtemp(prefix="e1_ext_")
    assets_copy = os.path.join(tmp_root, "assets")
    shutil.copytree(_SKILL_ASSETS, assets_copy)

    # ===== E1-2 external self-contained(headline)+ E1-4 validator_v2 =====
    try:
        rc, so, se = _run_external(assets_copy, _EXT_DRIVER)
        rep = _parse_json_line(so, "E1_RESULT_JSON=")
        if rep is None:
            res["E1-2_external_selfcontained"] = {
                "pass": False, "rc": rc, "stderr_tail": se[-800:]}
            res["E1-4_validator_v2_external"] = {"pass": False, "reason": "driver 無結果輸出"}
        else:
            steps_ok = all(v == "ok" or str(v).startswith("ok")
                           for v in rep["steps"].values())
            no_leaks = (len(rep["leaks"]) == 0)
            e12 = bool(rc == 0 and rep["ok"] and steps_ok and no_leaks)
            res["E1-2_external_selfcontained"] = {
                "pass": e12, "rc": rc, "steps": rep["steps"],
                "n_leaks": len(rep["leaks"]), "leaks": rep["leaks"][:8],
            }
            # E1-4:四 beat 的維度 5/6 皆非 unavailable + 硬閘 pass + overall
            beats = rep.get("beats", {})
            e14 = bool(beats) and all(
                b["runtime_loadable"] == "pass" and b["editor_importable"] == "pass"
                and b["deform_si"] != "unavailable" and b["c1_continuity"] != "unavailable"
                and b["overall"] is True
                for b in beats.values())
            res["E1-4_validator_v2_external"] = {"pass": bool(e14), "beats": beats}
    except Exception as e:                              # noqa: BLE001
        res["E1-2_external_selfcontained"] = {"pass": False, "error": "%s: %s" % (type(e).__name__, e)}
        res["E1-4_validator_v2_external"] = {"pass": False, "error": "see E1-2"}

    # ===== E1-3 negative control:移掉 bundle → 生成失敗 =====
    try:
        tmp_neg = tempfile.mkdtemp(prefix="e1_neg_")
        assets_neg = os.path.join(tmp_neg, "assets")
        shutil.copytree(_SKILL_ASSETS, assets_neg)
        shutil.rmtree(os.path.join(assets_neg, "gen_lib", "_bundled"))   # 拔掉 bundle
        rc, so, se = _run_external(assets_neg, _NEG_DRIVER)
        failed_as_expected = (rc != 0) and ("expected_failure" in so)
        res["E1-3_neg_control_no_bundle"] = {
            "pass": bool(failed_as_expected), "rc": rc,
            "signal": next((ln for ln in so.splitlines() if ln.startswith("NEG_RESULT=")), ""),
        }
    except Exception as e:                              # noqa: BLE001
        res["E1-3_neg_control_no_bundle"] = {"pass": False, "error": "%s: %s" % (type(e).__name__, e)}

    # ===== E1-5 in-repo 零回歸:既有 B/C/D 六閘仍全 PASS =====
    try:
        gates = ["validate_b2_genlib", "validate_b3_pivot", "validate_b4_sequence",
                 "validate_c1_mesh", "validate_c2_rig", "validate_d1_validator_v2"]
        gate_rc = {}
        for g in gates:
            gp = os.path.join(_HERE, g + ".py")
            r = subprocess.run([sys.executable, gp], cwd=_REPO,
                               capture_output=True, text=True, timeout=900)
            gate_rc[g] = r.returncode
        e15 = all(v == 0 for v in gate_rc.values())
        res["E1-5_in_repo_no_regression"] = {"pass": bool(e15), "gate_exit": gate_rc}
    except Exception as e:                              # noqa: BLE001
        res["E1-5_in_repo_no_regression"] = {"pass": False, "error": "%s: %s" % (type(e).__name__, e)}

    # ---- 匯總 ----
    all_pass = all(v.get("pass") for v in res.values())
    print(json.dumps({"E1_self_contained_gate": res, "ALL_PASS": all_pass},
                     ensure_ascii=False, indent=2))
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
