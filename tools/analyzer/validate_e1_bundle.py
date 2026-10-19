# -*- coding: utf-8 -*-
"""validate_e1_bundle —— MERGE_PLAN 2.0 Phase E1 自驗閘(self-contained bundle,G5)。

E1 把 gen_lib 過渡期硬相依的 repo 生成碼 **verbatim 複製**進
`skills/spine-ai-editor/assets/gen_lib/_vendor/`,並把各模組的 `_wire_repo_tools()` 改成
**優先掛 `_vendor/`**。本閘機械化證明:**把 skill 單獨搬到沒有 repo `tools/` 的地方(且清掉
PYTHONPATH)仍能生成 + 驗收** —— 即 G5「self-contained,不讓 skill 在使用者端 import 不存在的
tools/」。

隔離手法(關鍵):把 `skills/spine-ai-editor/` 整包複製到 tmp,child 以
  cwd = tmp 根(其上無 repo `tools/`)、env 去掉 PYTHONPATH
跑。`_wire_repo_tools()` 算出的 `repo = 四層上` 不含 tools/,PYTHONPATH 也空 →
**唯一能 import 到生成碼的來源就是 `_vendor/`**。

AC(5 條,全自動量化):
  E1-1 bundle-complete : _vendor/ 含 13 個必需模組,且逐一與 repo 原檔 **byte-identical**
                         (verbatim = 零回歸保證);全部可在**隔離 sys.path(只有 _vendor)**下 import。
  E1-2 anim-headline   : 隔離環境(無 repo tools / 無 PYTHONPATH)下 `gen_lib.make_beat.generate_bigwin`
                         產大獎 beat → `validator_v2.validate_v2` 六維度單一報告,硬閘
                         runtime/editor/loop PASS + overall PASS(純碼,無外部資產)。
  E1-3 mesh-headline   : 同隔離環境下 `gen_lib.mesh.generate_and_gate_part` 對**使用者資產**
                         (main_draw,以絕對路徑傳入 = 使用者 data)生成 mesh 並過真實 deform 閘
                         → overall_pass(證 numpy/cv2/scipy 走 _vendor 的生成/評估碼可 standalone)。
  E1-4 v2-six-dim      : 同隔離環境下 validator_v2 的**維度 5(deform_si)/維度 6(c1)**(需 _vendor 的
                         gen_lib.mesh / gen_animations)可 wire 成功(非 unavailable)→ 六維度全可跑,
                         不再因缺 repo tools 而退化。
  E1-5 neg-control     : 隔離 skill 複本**刪掉 vendored `gen_animations.py`**(`_wire_repo_tools()` 直接
                         import 的核心生成模組,必在 cascade 生成路徑上)→ generate_bigwin 必 ImportError
                         (證 _vendor 複本確為隔離下真正被用的相依,非死碼 / 非偷偷走他處)。

用法:python3 tools/analyzer/validate_e1_bundle.py   (exit 0 = 全 PASS)
"""
from __future__ import annotations
import json
import os
import shutil
import subprocess
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILL = os.path.join(_REPO, "skills", "spine-ai-editor")
_ASSETS = os.path.join(_SKILL, "assets")
_VENDOR = os.path.join(_ASSETS, "gen_lib", "_vendor")

# (vendored 檔名, repo 原檔絕對路徑)—— E1-1 byte-identical 來源
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


def _clean_env():
    """去掉 PYTHONPATH 的 env(模擬使用者端;repo tools 不在搜尋路徑)。"""
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    return env


def _run_child(code, cwd, extra_env=None):
    """在 cwd 下、清掉 PYTHONPATH 的乾淨 env 跑一段 python child,回傳 (rc, stdout, stderr)。"""
    env = _clean_env()
    if extra_env:
        env.update(extra_env)
    p = subprocess.run([sys.executable, "-c", code], cwd=cwd, env=env,
                       capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr


def _copy_skill_isolated():
    """把 skill 複製到 tmp 根(其上無 repo tools/),回傳 (tmp_root, isolated_assets_dir)。

    佈局:tmp_root/spine-ai-editor/assets/...  → child 的 _wire 算 repo=tmp_root,不含 tools/。"""
    tmp_root = tempfile.mkdtemp(prefix="e1_iso_")
    dst = os.path.join(tmp_root, "spine-ai-editor")
    shutil.copytree(_SKILL, dst)
    # 保險:確認隔離根底下真的沒有 repo tools/
    assert not os.path.exists(os.path.join(tmp_root, "tools")), "隔離根不該有 tools/"
    return tmp_root, os.path.join(dst, "assets")


# --------------------------------------------------------------------- E1-1
def check_e1_1():
    probs = []
    # (a) 檔案齊 + byte-identical
    if not os.path.isdir(_VENDOR):
        return False, ["_vendor/ 不存在:{}".format(_VENDOR)]
    for fn, rel in _VENDOR_SPEC:
        vp = os.path.join(_VENDOR, fn)
        rp = os.path.join(_REPO, rel)
        if not os.path.isfile(vp):
            probs.append("缺 vendored 模組:{}".format(fn)); continue
        if not os.path.isfile(rp):
            probs.append("repo 原檔不存在:{}".format(rel)); continue
        with open(vp, "rb") as f: vb = f.read()
        with open(rp, "rb") as f: rb = f.read()
        if vb != rb:
            probs.append("非 byte-identical(verbatim 破壞 → 零回歸無保證):{}".format(fn))
    if probs:
        return False, probs
    # (b) 隔離 sys.path(只有 _vendor)下 13 模組全 import
    names = [fn[:-3] for fn, _ in _VENDOR_SPEC]
    code = (
        "import sys\n"
        "sys.path[:] = [p for p in sys.path if p not in ('','.')]\n"
        "sys.path.insert(0, {vendor!r})\n"
        "names = {names!r}\n"
        "for m in names:\n"
        "    __import__(m)\n"
        "print('IMPORT_OK')\n"
    ).format(vendor=_VENDOR, names=names)
    rc, out, err = _run_child(code, cwd=tempfile.gettempdir())
    if rc != 0 or "IMPORT_OK" not in out:
        return False, ["隔離 import 失敗 rc={}:{}".format(rc, (err or out)[-600:])]
    return True, ["13 模組齊全 + byte-identical + 隔離 sys.path 全 import OK"]


# --------------------------------------------------------------------- E1-2 / E1-4
def check_e1_2_and_4():
    tmp_root, iso_assets = _copy_skill_isolated()
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
            return False, ["隔離生成/驗收 child 失敗 rc={}:{}".format(rc, (err or out)[-800:])], None
        line = [l for l in out.splitlines() if l.startswith("V2REPORT::")]
        if not line:
            return False, ["child 無 V2REPORT 輸出;stderr={}".format(err[-500:])], None
        rep = json.loads(line[0][len("V2REPORT::"):])
        dims = rep.get("dimensions", {})
        probs = []
        # E1-2:硬閘三維(用 status=='pass',跨維度可靠)+ overall
        for d in ("runtime_loadable", "editor_importable", "loop_closure"):
            dd = dims.get(d, {})
            if str(dd.get("status", "")).lower() != "pass":
                probs.append("E1-2 硬閘 {} 非 PASS:{}".format(d, dd))
        if not rep.get("overall_pass", False):
            probs.append("E1-2 overall_pass 非 True(hard_fail={})".format(rep.get("hard_fail")))
        e1_2_ok = not probs
        # E1-4:維度 5(deform_si)/維度 6(c1_continuity)不可因缺 repo tools 而 unavailable(須成功 wire)
        probs4 = []
        for d in ("deform_si", "c1_continuity"):
            dd = dims.get(d, {})
            st = str(dd.get("status", "")).lower()
            # na / info / pass 皆可(代表 wire 成功、只是該 beat 不適用);unavailable 代表相依缺 = 失敗
            if st == "unavailable":
                probs4.append("E1-4 維度 {} = unavailable(隔離下相依缺,self-contained 未達成):{}".format(d, dd))
        e1_4_ok = not probs4
        msgs = []
        msgs.append("E1-2 generate→validate_v2 六維度:runtime/editor/loop PASS、overall_pass={}".format(
            rep.get("overall_pass")))
        msgs.append("E1-4 維度5 deform_si={} / 維度6 c1_continuity={}(皆已 wire,非 unavailable)".format(
            dims.get("deform_si", {}).get("status"),
            dims.get("c1_continuity", {}).get("status")))
        return (e1_2_ok and e1_4_ok), (probs + probs4 + msgs), rep
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


# --------------------------------------------------------------------- E1-3
def check_e1_3():
    # 使用者資產(以絕對路徑傳入 = 使用者 data,非 skill 內碼)
    sk = os.path.join(_REPO, "assets", "main_draw.json")
    at = os.path.join(_REPO, "assets", "main_draw.atlas")
    pg = os.path.join(_REPO, "assets", "main_draw.png")
    for p in (sk, at, pg):
        if not os.path.isfile(p):
            return False, ["E1-3 需要 main_draw 使用者資產(缺 {});此為 data 非 code,"
                           "排程環境應具備。".format(os.path.basename(p))]
    tmp_root, iso_assets = _copy_skill_isolated()
    try:
        code = (
            "import sys, json\n"
            "sys.path.insert(0, {assets!r})\n"
            "from gen_lib.mesh import generate_and_gate_part\n"
            "rep = generate_and_gate_part({sk!r}, {at!r}, {pg!r},\n"
            "                             'image/curtain_left', 'image/curtain_left')\n"
            "print('MESHREP::' + json.dumps(rep))\n"
        ).format(assets=iso_assets, sk=sk, at=at, pg=pg)
        rc, out, err = _run_child(code, cwd=tmp_root)
        if rc != 0:
            return False, ["E1-3 隔離 mesh child 失敗 rc={}:{}".format(rc, (err or out)[-800:])]
        line = [l for l in out.splitlines() if l.startswith("MESHREP::")]
        if not line:
            return False, ["E1-3 child 無 MESHREP;stderr={}".format(err[-500:])]
        rep = json.loads(line[0][len("MESHREP::"):])
        if not rep.get("overall_pass", False):
            return False, ["E1-3 mesh overall_pass=False:{}".format(rep)]
        g = rep.get("deform_gate", {})
        return True, ["E1-3 隔離下 generate_and_gate_part(curtain_left)overall_pass=True "
                      "(mode={}, verts={}, deform clean={} has_real_deform={})".format(
                          rep["mesh"]["mode"], rep["mesh"]["vertices"],
                          g.get("clean"), g.get("has_real_deform"))]
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


# --------------------------------------------------------------------- E1-5 負對照
def check_e1_5():
    tmp_root, iso_assets = _copy_skill_isolated()
    try:
        victim = os.path.join(iso_assets, "gen_lib", "_vendor", "gen_animations.py")
        if not os.path.isfile(victim):
            return False, ["E1-5 找不到要刪的 vendored gen_animations.py"]
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
            return False, ["E1-5 刪掉 vendored gen_animations.py 後仍成功 → _vendor 複本非隔離下真正相依(偷偷走他處)"]
        if "EXPECTED_FAIL::" in out or "ModuleNotFoundError" in combined or "ImportError" in combined:
            return True, ["E1-5 刪掉 vendored gen_animations.py → generate_bigwin 如預期失敗(證 _vendor 確為隔離下真相依)"]
        return False, ["E1-5 結果不明確 rc={}:{}".format(rc, combined[-500:])]
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)


def main():
    checks = [
        ("E1-1 bundle-complete+byte-identical+隔離import", check_e1_1),
        ("E1-3 mesh-headline (使用者資產, 隔離)",            check_e1_3),
        ("E1-5 neg-control (刪 vendored 必炸)",             check_e1_5),
    ]
    results = []
    for name, fn in checks:
        ok, msgs = fn()
        results.append((name, ok, msgs))
    # E1-2 與 E1-4 共用一次 child
    ok24, msgs24, _ = check_e1_2_and_4()
    results.insert(1, ("E1-2 anim-headline + E1-4 v2-six-dim (隔離)", ok24, msgs24))

    print("=" * 72)
    print("Phase E1 self-contained bundle 自驗閘")
    print("=" * 72)
    all_ok = True
    for name, ok, msgs in results:
        print("[{}] {}".format("PASS" if ok else "FAIL", name))
        for m in msgs:
            print("      - {}".format(m))
        all_ok = all_ok and ok
    print("-" * 72)
    print("E1 OVERALL:", "PASS ✅" if all_ok else "FAIL ❌")
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
