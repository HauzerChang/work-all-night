#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""validate_e1_bundle —— spine-ai-editor 2.0 Phase E1「self-contained bundle」自檢閘(5 AC)。

E1 把 `gen_lib` 與 `validator_v2` 公開 API 需要的 repo `tools/` 生成/評估模組,byte-identical
copy 進 `skills/spine-ai-editor/assets/genpack/`,並把各 `_wire_repo_tools()` 改為**優先用 bundle**、
repo `tools/` 僅作開發 fallback。滿足 MERGE_PLAN_2.0 的 **G5｜self-contained**。

決定性自檢方法(**不靠肉眼**):
  把 `skills/spine-ai-editor/assets/` 複製到一個**沒有 sibling `tools/`** 的暫存目錄,
  在那裡用 `python3 -I` 子程序 import 公開 API 並生成/驗收 —— 這正是交付 `.skill`(只帶 assets/)
  的真實佈局。bundle 不足以獨立運作,子程序就會 ImportError。

AC:
  E1-1  bundle 完整且與 repo 來源逐位元一致(MANIFEST.json drift guard;13 模組)。
  E1-2  (headline)隔離環境(無 repo tools/)下,五條生成軸全 import+生成成功,
        且解析到的模組檔**位於隔離 genpack**(非 repo)。
  E1-3  隔離環境下 validator_v2.validate_v2 對生成的大獎 beat → overall PASS,
        且維度 5/6(deform_si/c1)**非 unavailable**(= 由 bundle 成功 wire,非 import 失敗)。
  E1-4  隔離環境下生成的大獎 beat 過 G2 雙真值(validator_v1 editor-import 0 error,含末鍵 curve 檢查)。
  E1-5  (閘非恆真)隔離環境把 genpack 移走 → 同一公開 API import **FAIL**(證測試真的靠 bundle,
        非洩漏的 repo 路徑);且確認隔離目錄確實無 repo tools/。
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, "..", ".."))
ASSETS = os.path.join(REPO, "skills", "spine-ai-editor", "assets")
GENPACK = os.path.join(ASSETS, "genpack")


def _sha(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


# --------------------------------------------------------------------- E1-1
def ac1_manifest_sync():
    man_path = os.path.join(GENPACK, "MANIFEST.json")
    assert os.path.isfile(man_path), "genpack/MANIFEST.json 不存在"
    man = json.load(open(man_path, encoding="utf-8"))
    files = man["files"]
    assert len(files) == 13, "預期 13 個 bundled 模組,實際 {}".format(len(files))
    problems = []
    for fn, rec in sorted(files.items()):
        bundled = os.path.join(GENPACK, fn)
        src = os.path.join(REPO, rec["repo_source"])
        if not os.path.isfile(bundled):
            problems.append("bundle 缺檔: {}".format(fn)); continue
        if not os.path.isfile(src):
            problems.append("repo 來源缺檔: {}".format(rec["repo_source"])); continue
        bh, sh, mh = _sha(bundled), _sha(src), rec["sha256"]
        if bh != mh:
            problems.append("{} bundle 與 manifest sha 不符".format(fn))
        if bh != sh:
            problems.append("{} 與 repo 來源漂移(忘了重 bundle?)".format(fn))
    assert not problems, "manifest/drift 問題: " + "; ".join(problems)
    return {"bundled_modules": len(files), "all_byte_identical_to_repo": True}


# --------------------------------------------------------------------- 隔離環境 driver
# 這段字串寫進隔離暫存目錄當子程序跑。只把隔離 assets 的 gen_lib / assets 掛上 sys.path,
# **絕不加 repo 路徑**。wire 函式算出的 repo fallback 指向隔離目錄的上層(無 tools/)→ 只有 bundle 可用。
_DRIVER = r'''
import sys, os, json, tempfile
ISO_ASSETS = sys.argv[1]            # .../iso/assets
OUT = sys.argv[2]
sys.path.insert(0, os.path.join(ISO_ASSETS, "gen_lib"))
sys.path.insert(0, ISO_ASSETS)
res = {"steps": {}, "ok": True}
def step(name, fn):
    try:
        res["steps"][name] = {"ok": True, **(fn() or {})}
    except Exception as e:
        import traceback
        res["steps"][name] = {"ok": False, "err": "{}: {}".format(type(e).__name__, e),
                              "tb": traceback.format_exc()[-800:]}
        res["ok"] = False

ISO_GENPACK = os.path.join(ISO_ASSETS, "genpack")
def _under_genpack(mod):
    return os.path.dirname(os.path.abspath(mod.__file__)) == ISO_GENPACK

# --- 軸 1: make_beat ---
def s_make_beat():
    import make_beat as MB
    G, ct = MB._wire_repo_tools()
    assert _under_genpack(G), "gen_animations 未解析到隔離 genpack: " + G.__file__
    skel, name = MB.generate_bigwin(MB.DEMO_PARTS, beat="cascade")
    idle, iname = MB.generate_idle(MB.IDLE_DEMO_PARTS)
    # 寫出大獎 beat 供 validator_v2 / validator_v1 用
    jp = os.path.join(tempfile.gettempdir(), "e1_bigwin.json")
    json.dump(skel, open(jp, "w"), ensure_ascii=False)
    return {"anim": name, "idle": iname, "json": jp, "gen_from": os.path.dirname(G.__file__)}
step("make_beat", s_make_beat)

# --- 軸 2: pivot_axis ---
def s_pivot():
    import make_beat as MB, pivot_axis as PA
    idle, iname = MB.generate_idle(MB.IDLE_DEMO_PARTS)
    origins = PA.bone_origins_from_skel(idle)
    # 給 limb bone 一個肩 pivot(parent 座標),繞肩旋轉
    limb = [b["name"] for b in idle["bones"] if b["name"].startswith("b_arm")]
    pivots = {bn: (origins[bn][0], origins[bn][1] + 40.0) for bn in limb}
    turned = PA.apply_joint_pivots(idle, iname, pivots)
    pr, _ = PA._wire()
    assert _under_genpack(pr), "pivot_rotation 未解析到隔離 genpack"
    return {"turned_bones": sorted(turned)}
step("pivot_axis", s_pivot)

# --- 軸 3: sequence ---
def s_seq():
    import make_beat as MB, sequence as SQ
    comp, cname = SQ.compose_bigwin_sequence(MB.DEMO_PARTS, order=["cascade", "wobble"])
    xf, xname = SQ.crossfade_bigwin_sequence(MB.DEMO_PARTS, order=["cascade", "wobble"])
    return {"compose_anim": cname, "crossfade_anim": xname,
            "compose_has_anim": cname in comp.get("animations", {}),
            "crossfade_has_anim": xname in xf.get("animations", {})}
step("sequence", s_seq)

# --- 軸 4: mesh ---
def s_mesh():
    import numpy as np, cv2
    import mesh as MESH
    GM, DE, AC = MESH._wire_repo_tools()
    assert _under_genpack(GM), "generate_mesh_v2 未解析到隔離 genpack"
    # 合成一張簡單遮罩 PNG(填滿橢圓),不需任何 repo 資產
    img = np.zeros((120, 80, 4), dtype=np.uint8)
    cv2.ellipse(img, (40, 60), (30, 50), 0, 0, 360, (255, 255, 255, 255), -1)
    mp = os.path.join(tempfile.gettempdir(), "e1_mask.png")
    cv2.imwrite(mp, img)
    m = MESH.generate_part_mesh(mp)
    assert MESH.mesh_is_schema_valid(m), "生成 mesh schema 不合法"
    nv = len(m["vertices"]) // 2
    return {"verts": nv, "hull": m.get("hull"), "mesh_from": os.path.dirname(GM.__file__)}
step("mesh", s_mesh)

# --- 軸 5: rig ---
def s_rig():
    import rig as RIG
    _g, _w, ip, it = RIG._wire_repo_tools()
    assert _under_genpack(it), "infer_tree 未解析到隔離 genpack"
    parts = RIG.make_chain_parts()
    out = RIG.rig_from_parts(parts)
    return {"root": out["root"], "tree": out["tree"], "n_pivots": len(out["pivots"])}
step("rig", s_rig)

# --- validator_v2 在隔離環境 ---
def s_v2():
    import validator_v2 as V2
    jp = res["steps"]["make_beat"].get("json")
    rep = V2.validate_v2(jp)
    d = rep["dimensions"]
    return {"overall": rep["overall_pass"],
            "runtime": d["runtime_loadable"]["status"],
            "editor": d["editor_importable"]["status"],
            "loop": d["loop_closure"]["status"],
            "deform_si": d["deform_si"]["status"],
            "c1": d["c1_continuity"]["status"]}
step("validator_v2", s_v2)

json.dump(res, open(OUT, "w"), ensure_ascii=False)
print("DRIVER_DONE")
'''


def _make_isolated_copy():
    """把 assets/ 複製到一個沒有 sibling tools/ 的暫存目錄。回傳 (tmpdir, iso_assets)。"""
    tmp = tempfile.mkdtemp(prefix="e1_iso_")
    iso_assets = os.path.join(tmp, "assets")
    shutil.copytree(ASSETS, iso_assets)
    return tmp, iso_assets


def _run_driver(iso_assets):
    tmp = os.path.dirname(iso_assets)
    drv = os.path.join(tmp, "driver.py")
    open(drv, "w").write(_DRIVER)
    out = os.path.join(tmp, "out.json")
    # -I:隔離 PYTHONPATH / user-site;確保只有 driver 自己插入的隔離路徑可用。
    p = subprocess.run([sys.executable, "-I", drv, iso_assets, out],
                       capture_output=True, text=True, timeout=300)
    data = json.load(open(out, encoding="utf-8")) if os.path.isfile(out) else None
    return p, data


def _assert_no_repo_tools(iso_assets):
    """隔離目錄的 wire 算出的 repo 根不得有 tools/(確認隔離確實成立)。"""
    # make_beat wire: repo = gen_lib/../../../.. ;驗那個 tools/ 不存在
    repo_guess = os.path.normpath(os.path.join(iso_assets, "..", "..", ".."))
    for sub in ("tools/analyzer", "tools/mesh_gen", "tools/rig"):
        assert not os.path.isdir(os.path.join(repo_guess, sub)), \
            "隔離不成立:{} 竟存在".format(sub)


# --------------------------------------------------------------------- E1-2/3/4
def ac234_isolated():
    tmp, iso = _make_isolated_copy()
    try:
        _assert_no_repo_tools(iso)
        p, data = _run_driver(iso)
        assert data is not None, "driver 無輸出。stderr tail:\n" + (p.stderr or "")[-1500:]
        assert "DRIVER_DONE" in p.stdout, "driver 未正常結束。stderr:\n" + (p.stderr or "")[-1500:]
        steps = data["steps"]
        # E1-2:五軸全成功 + 解析到隔離 genpack
        axes = ["make_beat", "pivot_axis", "sequence", "mesh", "rig"]
        failed = {k: steps[k].get("err") for k in axes if not steps[k]["ok"]}
        assert not failed, "E1-2 生成軸在隔離環境失敗: {}".format(json.dumps(failed, ensure_ascii=False))
        iso_genpack = os.path.join(iso, "genpack")
        assert steps["make_beat"]["gen_from"] == iso_genpack, \
            "gen_animations 非來自隔離 genpack: {}".format(steps["make_beat"]["gen_from"])
        assert steps["mesh"]["mesh_from"] == iso_genpack, "generate_mesh_v2 非來自隔離 genpack"
        # E1-3:validator_v2 overall PASS + 維度 5/6 非 unavailable
        v2 = steps["validator_v2"]
        assert v2["ok"], "E1-3 validator_v2 在隔離環境 crash: {}".format(v2.get("err"))
        assert v2["overall"] in (True, "pass", "PASS"), "E1-3 validator_v2 overall 非 PASS: {}".format(v2["overall"])
        assert v2["runtime"] in ("pass", True) and v2["editor"] in ("pass", True) and v2["loop"] in ("pass", True), \
            "E1-3 硬閘維度 1-3 未全 PASS: {}".format(v2)
        assert v2["deform_si"] != "unavailable", "E1-3 deform_si=unavailable → bundle 沒 wire 維度 5"
        assert v2["c1"] != "unavailable", "E1-3 c1=unavailable → bundle 沒 wire 維度 6"
        return {
            "axes_ok": axes,
            "rig_root": steps["rig"]["root"],
            "mesh_verts": steps["mesh"]["verts"],
            "v2_overall": v2["overall"],
            "v2_dims": {k: v2[k] for k in ("runtime", "editor", "loop", "deform_si", "c1")},
        }, iso
    finally:
        # 保留 iso 供 E1-5 用;由 ac5 清
        globals()["_LAST_ISO"] = (tmp, iso)
    # (unreachable)


def ac4_double_truth(iso_summary):
    """E1-4:隔離生成的大獎 beat 過 validator_v1 editor-import 0 error(G2)。
    用隔離 assets 的 validator_v1 跑(也在 bundle 交付範圍)。"""
    tmp, iso = globals()["_LAST_ISO"]
    jp = os.path.join(tempfile.gettempdir(), "e1_bigwin.json")
    assert os.path.isfile(jp), "E1-2 未產出 e1_bigwin.json"
    drv = os.path.join(tmp, "v1_driver.py")
    open(drv, "w").write(
        "import sys, os, json\n"
        "iso=sys.argv[1]\n"
        "sys.path.insert(0, iso)\n"
        "import validator_v1 as V1\n"
        "rep, demoted, metrics = V1.validate_v1(sys.argv[2])\n"
        "errs=list(rep.errors)\n"
        "json.dump({'errors': errs, 'valid': len(errs)==0}, open(sys.argv[3],'w'), ensure_ascii=False)\n"
        "print('V1_DONE')\n")
    out = os.path.join(tmp, "v1_out.json")
    p = subprocess.run([sys.executable, "-I", drv, iso, jp, out],
                       capture_output=True, text=True, timeout=180)
    assert "V1_DONE" in p.stdout, "validator_v1 driver 失敗:\n" + (p.stderr or "")[-1500:]
    r = json.load(open(out, encoding="utf-8"))
    errs = r["errors"]
    assert r["valid"] and not errs, "E1-4 validator_v1 editor-import 有 error(G2 失敗): {}".format(errs)
    return {"validator_v1_valid": True, "errors": errs}


def ac5_negative_control():
    """E1-5:把隔離 genpack 移走 → 公開 API import 應 FAIL。證測試真靠 bundle。"""
    tmp, iso = globals()["_LAST_ISO"]
    genpack = os.path.join(iso, "genpack")
    moved = genpack + ".DISABLED"
    shutil.move(genpack, moved)
    try:
        drv = os.path.join(tmp, "neg_driver.py")
        open(drv, "w").write(
            "import sys, os\n"
            "iso=sys.argv[1]\n"
            "sys.path.insert(0, os.path.join(iso,'gen_lib'))\n"
            "sys.path.insert(0, iso)\n"
            "import make_beat as MB\n"
            "MB.generate_bigwin(MB.DEMO_PARTS, beat='cascade')\n"
            "print('UNEXPECTED_OK')\n")
        p = subprocess.run([sys.executable, "-I", drv, iso],
                           capture_output=True, text=True, timeout=120)
        failed = ("UNEXPECTED_OK" not in p.stdout) and (p.returncode != 0)
        assert failed, "E1-5 移走 genpack 後竟仍成功 → 測試有洩漏路徑,非恆真失效"
        assert ("ImportError" in p.stderr or "ModuleNotFoundError" in p.stderr), \
            "E1-5 失敗但非 ImportError(預期找不到 gen_animations):\n" + (p.stderr or "")[-800:]
    finally:
        shutil.move(moved, genpack)
    return {"import_fails_without_bundle": True}


def main():
    results = {}
    ok = True

    def run(name, fn, *a):
        nonlocal ok
        try:
            results[name] = {"PASS": True, "detail": fn(*a)}
            print("  [PASS] {}".format(name))
        except Exception as e:  # noqa: BLE001
            ok = False
            results[name] = {"PASS": False, "error": "{}: {}".format(type(e).__name__, e)}
            print("  [FAIL] {}: {}".format(name, e))

    print("=== validate_e1_bundle (Phase E1 self-contained) ===")
    run("E1-1_manifest_sync", ac1_manifest_sync)
    # E1-2 與 E1-3 在同一隔離 run 內
    iso_summary = None
    try:
        detail, _iso = ac234_isolated()
        results["E1-2_isolated_axes"] = {"PASS": True, "detail": {"axes_ok": detail["axes_ok"],
                                         "rig_root": detail["rig_root"], "mesh_verts": detail["mesh_verts"]}}
        results["E1-3_isolated_validator_v2"] = {"PASS": True,
                                                 "detail": {"overall": detail["v2_overall"], "dims": detail["v2_dims"]}}
        print("  [PASS] E1-2_isolated_axes")
        print("  [PASS] E1-3_isolated_validator_v2")
        iso_summary = detail
    except Exception as e:  # noqa: BLE001
        ok = False
        results["E1-2_isolated_axes"] = {"PASS": False, "error": "{}: {}".format(type(e).__name__, e)}
        results["E1-3_isolated_validator_v2"] = {"PASS": False, "error": "see E1-2"}
        print("  [FAIL] E1-2/E1-3: {}".format(e))

    if iso_summary is not None:
        run("E1-4_double_truth_validator_v1", ac4_double_truth, iso_summary)
        run("E1-5_negative_control", ac5_negative_control)
    else:
        ok = False
        results["E1-4_double_truth_validator_v1"] = {"PASS": False, "error": "iso 未建立"}
        results["E1-5_negative_control"] = {"PASS": False, "error": "iso 未建立"}

    # 清隔離暫存
    try:
        if "_LAST_ISO" in globals():
            shutil.rmtree(globals()["_LAST_ISO"][0], ignore_errors=True)
    except Exception:
        pass

    print("\n=== RESULT: {} ===".format("ALL PASS" if ok else "SOME FAIL"))
    print(json.dumps(results, ensure_ascii=False, indent=2))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
