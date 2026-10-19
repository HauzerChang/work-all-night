# -*- coding: utf-8 -*-
"""validate_e3_delivery —— MERGE_PLAN 2.0 Phase E3 自驗閘(交付 `.skill` 檔可用性)。

E1 證「skill 目錄」self-contained;E3 進一步證**實際交付的 `.skill` 壓縮檔**——使用者真正
拿到、拖進 Cowork 或複製進 plugin 的那一包——解壓後在**沒有 repo tools/、清掉 PYTHONPATH**
的環境下仍能生成 + 六維度驗收。這比 E1(複製目錄)更貼近交付真相:測的是 zip 本身。

隔離手法(沿用 E1):把 `.skill` 解壓到 tmp 根(其上無 repo tools/),child 以
  cwd = tmp 根、env 去掉 PYTHONPATH 跑 → 唯一能 import 到生成碼的來源就是解壓出來的
  `assets/gen_lib/_vendor/`。

AC(5 條,全自動量化):
  E3-1 manifest    : `.skill` 是合法 zip;含整包 skill 樹(SKILL.md/INSTALL.md/MERGE_PLAN_2.0.md
                     /references/ 至少 5 份/assets/gen_lib 5 入口 + validator_v2 + _vendor 13 模組);
                     **不含** `__pycache__`/`*.pyc`;_vendor 13 模組逐一與 repo 原檔 byte-identical。
  E3-2 headline    : 解壓 `.skill` 到隔離根 → `gen_lib.make_beat.generate_bigwin`(cascade)→
                     `validator_v2.validate_v2` 六維度:硬閘 runtime/editor/loop PASS + overall PASS;
                     維度 5 deform_si / 維度 6 c1 皆成功 wire(非 unavailable)。
  E3-3 docs-shipped: 解壓出的 SKILL.md frontmatter version == 2.0.0(E2 文件隨交付出貨)+
                     INSTALL.md 路線 B/結構樹齊 + MERGE_PLAN_2.0.md 在包內。
  E3-4 neg-control : 解壓後刪掉 `assets/gen_lib/_vendor/gen_animations.py` → generate_bigwin 必
                     ImportError(證 zip 內 _vendor 確為交付包真正被用的相依,閘非恆真)。
  E3-5 determinism : 連打包兩次 → 兩個 `.skill` 位元組完全相同(reproducible,commit 無 churn)。

用法:python3 tools/analyzer/validate_e3_delivery.py   (exit 0 = 全 PASS)
"""
from __future__ import annotations
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILL = os.path.join(_REPO, "skills", "spine-ai-editor")
_DELIVERY = os.path.join(_REPO, "skills", "spine-ai-editor.skill")

_VENDOR_SPEC = [
    ("gen_animations.py",        "tools/analyzer/gen_animations.py"),
    ("spine_anim.py",            "tools/analyzer/spine_anim.py"),
    ("beat_templates.py",        "tools/analyzer/beat_templates.py"),
    ("tier_variants.py",         "tools/analyzer/tier_variants.py"),
    ("pivot_rotation.py",        "tools/analyzer/pivot_rotation.py"),
    ("generate_mesh_v2.py",      "tools/mesh_gen/generate_mesh_v2.py"),
    ("generate_mesh.py",         "tools/mesh_gen/generate_mesh.py"),
    ("deform_eval.py",           "tools/mesh_gen/deform_eval.py"),
    ("atlas_crop.py",            "tools/mesh_gen/atlas_crop.py"),
    ("generate_weighted_mesh.py","tools/mesh_gen/generate_weighted_mesh.py"),
    ("weighted_deform_eval.py",  "tools/mesh_gen/weighted_deform_eval.py"),
    ("infer_pivots.py",          "tools/rig/infer_pivots.py"),
    ("infer_tree.py",            "tools/rig/infer_tree.py"),
]
_GENLIB_ENTRIES = ["make_beat.py", "sequence.py", "pivot_axis.py", "mesh.py", "rig.py"]
_MIN_REFERENCES = 5


def _clean_env():
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def _run_child(code, cwd):
    p = subprocess.run([sys.executable, "-c", code], cwd=cwd, env=_clean_env(),
                       capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def _extract_delivery():
    """把 .skill 解壓到 tmp 根(其上無 repo tools/),回傳 (tmp_root, iso_assets)。

    布局:tmp_root/spine-ai-editor/assets/... → child 的 _wire 算 repo=tmp_root,不含 tools/。"""
    tmp_root = tempfile.mkdtemp(prefix="e3_iso_")
    dst = os.path.join(tmp_root, "spine-ai-editor")
    os.makedirs(dst)
    with zipfile.ZipFile(_DELIVERY, "r") as zf:
        zf.extractall(dst)
    assert not os.path.exists(os.path.join(tmp_root, "tools")), "隔離根不該有 tools/"
    return tmp_root, os.path.join(dst, "assets")


# --------------------------------------------------------------------- E3-1
def check_e3_1():
    if not os.path.isfile(_DELIVERY):
        return False, ["交付檔不存在:{}(先跑 tools/pack_skill.py)".format(_DELIVERY)]
    if not zipfile.is_zipfile(_DELIVERY):
        return False, [".skill 非合法 zip"]
    probs = []
    with zipfile.ZipFile(_DELIVERY, "r") as zf:
        bad = zf.testzip()
        if bad is not None:
            return False, ["zip CRC 損壞於:{}".format(bad)]
        names = set(zf.namelist())
        # 快取/編譯檔不得入包
        junk = [n for n in names if "__pycache__" in n or n.endswith((".pyc", ".pyo"))]
        if junk:
            probs.append("交付包含快取/編譯檔(不該):{}".format(junk[:5]))
        # 必備頂層文件
        for need in ("SKILL.md", "INSTALL.md", "MERGE_PLAN_2.0.md",
                     "assets/validator_v2.py", "assets/gen_lib/__init__.py"):
            if need not in names:
                probs.append("交付缺檔:{}".format(need))
        # gen_lib 5 入口
        for e in _GENLIB_ENTRIES:
            if "assets/gen_lib/" + e not in names:
                probs.append("交付缺 gen_lib 入口:{}".format(e))
        # references ≥ 5
        refs = [n for n in names if n.startswith("references/") and n.endswith(".md")]
        if len(refs) < _MIN_REFERENCES:
            probs.append("references/ 份數不足({} < {})".format(len(refs), _MIN_REFERENCES))
        # _vendor 13 模組齊 + byte-identical 對 repo 原檔
        for fn, rel in _VENDOR_SPEC:
            vn = "assets/gen_lib/_vendor/" + fn
            if vn not in names:
                probs.append("交付缺 vendored 模組:{}".format(fn)); continue
            zb = zf.read(vn)
            rp = os.path.join(_REPO, rel)
            if not os.path.isfile(rp):
                probs.append("repo 原檔不存在:{}".format(rel)); continue
            with open(rp, "rb") as f:
                rb = f.read()
            if zb != rb:
                probs.append("交付 vendored 非 byte-identical:{}".format(fn))
    if probs:
        return False, probs
    with zipfile.ZipFile(_DELIVERY, "r") as zf:
        n = len(zf.namelist())
    return True, ["合法 zip、{} 條目、13 vendored byte-identical、無 pycache、"
                  "頂層文件 + gen_lib 5 入口 + validator_v2 + references≥5 齊".format(n)]


# --------------------------------------------------------------------- E3-2
def check_e3_2():
    tmp_root, iso_assets = _extract_delivery()
    try:
        out_json = os.path.join(tmp_root, "bigwin.json")
        code = (
            "import sys, json\n"
            "sys.path.insert(0, {assets!r})\n"
            "from gen_lib.make_beat import generate_bigwin, DEMO_PARTS\n"
            "r = generate_bigwin(DEMO_PARTS, beat='cascade')\n"
            "skel, aname = r if isinstance(r, tuple) else (r, 'cascade')\n"
            "json.dump(skel, open({outj!r},'w'))\n"
            "from validator_v2 import validate_v2\n"
            "rep = validate_v2({outj!r}, loop_anims=[aname])\n"
            "print('V2REPORT::' + json.dumps(rep))\n"
        ).format(assets=iso_assets, outj=out_json)
        rc, out, err = _run_child(code, cwd=tmp_root)
        if rc != 0:
            return False, ["E3-2 解壓後生成/驗收 child 失敗 rc={}:{}".format(rc, (err or out)[-800:])]
        line = [l for l in out.splitlines() if l.startswith("V2REPORT::")]
        if not line:
            return False, ["E3-2 child 無 V2REPORT;stderr={}".format(err[-500:])]
        rep = json.loads(line[0][len("V2REPORT::"):])
        dims = rep.get("dimensions", {})
        probs = []
        for d in ("runtime_loadable", "editor_importable", "loop_closure"):
            if str(dims.get(d, {}).get("status", "")).lower() != "pass":
                probs.append("E3-2 硬閘 {} 非 PASS:{}".format(d, dims.get(d)))
        if not rep.get("overall_pass", False):
            probs.append("E3-2 overall_pass 非 True(hard_fail={})".format(rep.get("hard_fail")))
        for d in ("deform_si", "c1_continuity"):
            if str(dims.get(d, {}).get("status", "")).lower() == "unavailable":
                probs.append("E3-2 維度 {} = unavailable(交付包相依缺)".format(d))
        if probs:
            return False, probs
        return True, ["E3-2 解壓交付 .skill → generate_bigwin→validate_v2 六維度:"
                      "runtime/editor/loop PASS、overall_pass=True、"
                      "deform_si={}、c1={}(皆 wire)".format(
                          dims.get("deform_si", {}).get("status"),
                          dims.get("c1_continuity", {}).get("status"))]
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


# --------------------------------------------------------------------- E3-3
def check_e3_3():
    tmp_root, iso_assets = _extract_delivery()
    try:
        skill_root = os.path.dirname(iso_assets)
        probs = []
        # SKILL.md version 2.0.0(E2 以 blockquote `> **version: 2.0.0**` 宣告,非 YAML key)
        with open(os.path.join(skill_root, "SKILL.md"), encoding="utf-8") as f:
            sk = f.read()
        if "version: 2.0.0" not in sk:
            probs.append("E3-3 SKILL.md 無 `version: 2.0.0` 宣告")
        if not re.search(r"\*\*\s*2\.0\.0\s*\*\*", sk):
            probs.append("E3-3 SKILL.md 無 Changelog 2.0.0 條目")
        # INSTALL.md 路線 B + 結構樹
        with open(os.path.join(skill_root, "INSTALL.md"), encoding="utf-8") as f:
            inst = f.read()
        for kw in ("路線 B", ".skill", "gen_lib"):
            if kw not in inst:
                probs.append("E3-3 INSTALL.md 缺關鍵字:{}".format(kw))
        # MERGE_PLAN 在包內
        if not os.path.isfile(os.path.join(skill_root, "MERGE_PLAN_2.0.md")):
            probs.append("E3-3 交付包內無 MERGE_PLAN_2.0.md")
        if probs:
            return False, probs
        return True, ["E3-3 交付 SKILL.md version=2.0.0、INSTALL.md 路線B/結構樹齊、"
                      "MERGE_PLAN_2.0.md 在包內(E2 文件隨交付出貨)"]
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


# --------------------------------------------------------------------- E3-4 負對照
def check_e3_4():
    tmp_root, iso_assets = _extract_delivery()
    try:
        victim = os.path.join(iso_assets, "gen_lib", "_vendor", "gen_animations.py")
        if not os.path.isfile(victim):
            return False, ["E3-4 解壓後找不到要刪的 vendored gen_animations.py"]
        os.remove(victim)
        code = (
            "import sys\n"
            "sys.path.insert(0, {assets!r})\n"
            "from gen_lib.make_beat import generate_bigwin, DEMO_PARTS\n"
            "try:\n"
            "    generate_bigwin(DEMO_PARTS, beat='cascade')\n"
            "    print('UNEXPECTED_OK')\n"
            "except Exception as e:\n"
            "    print('EXPECTED_FAIL::' + type(e).__name__)\n"
        ).format(assets=iso_assets)
        rc, out, err = _run_child(code, cwd=tmp_root)
        combined = out + "\n" + err
        if "UNEXPECTED_OK" in out:
            return False, ["E3-4 刪掉交付包 vendored gen_animations.py 後仍成功 → _vendor 非真正相依"]
        if "EXPECTED_FAIL::" in out or "ModuleNotFoundError" in combined or "ImportError" in combined:
            return True, ["E3-4 刪掉交付包 vendored gen_animations.py → generate_bigwin 如預期失敗"
                          "(證 zip 內 _vendor 確為交付包真相依,閘非恆真)"]
        return False, ["E3-4 結果不明確 rc={}:{}".format(rc, combined[-500:])]
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


# --------------------------------------------------------------------- E3-5 determinism
def check_e3_5():
    sys.path.insert(0, os.path.join(_REPO, "tools"))
    try:
        import pack_skill
    except Exception as e:
        return False, ["E3-5 無法 import tools/pack_skill.py:{}".format(e)]
    d = tempfile.mkdtemp(prefix="e3_det_")
    try:
        a = os.path.join(d, "a.skill")
        b = os.path.join(d, "b.skill")
        pack_skill.pack(_SKILL, a)
        pack_skill.pack(_SKILL, b)
        ha = hashlib.sha256(open(a, "rb").read()).hexdigest()
        hb = hashlib.sha256(open(b, "rb").read()).hexdigest()
        # 已出貨的交付檔也應等於重打包(確保 commit 的那份就是 reproducible 產物)
        hs = hashlib.sha256(open(_DELIVERY, "rb").read()).hexdigest() if os.path.isfile(_DELIVERY) else None
        if ha != hb:
            return False, ["E3-5 連打包兩次位元不同(非 reproducible):{} != {}".format(ha[:12], hb[:12])]
        msg = "E3-5 連打包兩次位元相同(sha256 {}…,reproducible)".format(ha[:12])
        if hs is not None and hs != ha:
            msg += ";⚠️ 已 commit 的交付檔 sha 與重打包不一致(需用 pack_skill 重產)"
        return (hs is None or hs == ha), [msg]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def main():
    checks = [
        ("E3-1 manifest (合法 zip + 整包樹 + 13 vendored byte-identical + 無 pycache)", check_e3_1),
        ("E3-2 headline (解壓交付包隔離生成→validate_v2 六維度 PASS)",               check_e3_2),
        ("E3-3 docs-shipped (SKILL 2.0.0 + INSTALL + MERGE_PLAN 隨交付)",             check_e3_3),
        ("E3-4 neg-control (刪交付包 vendored 必炸)",                                 check_e3_4),
        ("E3-5 determinism (連打包兩次位元相同 + 等於已出貨)",                        check_e3_5),
    ]
    print("=" * 72)
    print("Phase E3 交付 .skill 可用性自驗閘")
    print("=" * 72)
    all_ok = True
    for name, fn in checks:
        ok, msgs = fn()
        print("[{}] {}".format("PASS" if ok else "FAIL", name))
        for m in msgs:
            print("      - {}".format(m))
        all_ok = all_ok and ok
    print("-" * 72)
    print("E3 OVERALL:", "PASS ✅" if all_ok else "FAIL ❌")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
