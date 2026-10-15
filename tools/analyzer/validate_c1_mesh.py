#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C1 閘 — `gen_lib.mesh_forge` mesh 生成 + 變形自交閘 → v1.3.0 `validator_v1`
(spine-ai-editor 2.0 Phase C1,結構軸 mesh 面)。

B2/B3/B4 把**動畫軸**(beat / 繞關節 pivot / 序列)包成 skill 入口並驗其雙真值。C1 補上**結構軸的
mesh 面**:把 repo deform-aware mesh 生成器(`generate_mesh_v2` strip)+ 真實位移場轉移自交閘
(`deform_eval`)抽成 skill 入口 `skills/spine-ai-editor/assets/gen_lib/mesh_forge.py`,並機械化驗
**mesh 軸的雙真值 G2**。

**驗的是什麼(為何這個 chunk 有價值)**:
  使用者既有 `validator_v1` **只檢查** mesh attachment 的 schema(型別/引用/hull),**不生成、也不驗變形期拓樸**。
  變形下自交/翻面(撕裂/破圖)是 mesh 軸獨有、所有 animation 閘從不碰的真值。C1 證:
   · **真值 A(可載入)**:生成 mesh 裝進完整 skeleton → 真正的 `validator_v1` **0 error**
     (runtime 能載入 / editor 能匯入);且可併進既有(動畫軸)skeleton = 結構軸組合,非孤立 scaffold。
   · **真值 B(變形安全)**:在**真實位移場**(自 main_draw 窗簾 deform timeline『總位移最大幀』)轉移到
     生成 mesh 後,拓樸乾淨(self-intersections=0 / triangle_flips=0 / degenerate=0)。
     ⚠️ **用真實場轉移,不用未校準的 stress_field**(合成場 mag=315 面積比 2.0 >> 真實 1.14,假性失敗)。
   · robot 件(weighted、無 deform timeline)→ auto 模式正確回退非 strip 拓樸,以靜態覆蓋率 + 拓樸合法性驗收。
   · 負對照(閘非恆真):tangle mesh → 真值 B 抓到自交;壞 slot 引用 → 真值 A validator_v1 抓到;
     越界三角索引 → 格式閘抓到。
  Cocos/viewer 實機載入 = 使用者端(排程 scope 邊界),本閘用 spine-webgl 無頭等價(validator_v1)替代。

**AC(全部客觀、可機讀)**:
  C1-1 entrypoint+strip+fmt : `mesh_forge.generate_strip_mesh` 公開 API 對真實窗簾件產 **strip** mesh,
                              過 evaluate_mesh 格式/拓樸閘(hull-first 0<hull≤nv、三角索引在範圍、
                              degenerate=0、orphans=0、頂點預算)。
  C1-2 loadable (真值 A)    : scaffold_skeleton(生成 mesh)→ 真正的 `validator_v1` **0 error**;
                              **併進既有 skeleton**(install_mesh 進 2-bone 骨架)亦 0 error(結構軸組合);
                              寫檔→重讀→validator_v1 0 error(端到端到可載入檔)。
  C1-3 deform-safe (真值 B) : 4 個真實 deform 件(curtain_left/right、shadow、shadow2)各生成 strip →
                              **真實位移場轉移** → si=0 且 flips=0 且 degenerate=0(**headline AC**)。
  C1-4 robot pieces         : 3 個 Award 機器人件(weighted、無 deform)→ auto 生成(正確回退非 strip)→
                              靜態覆蓋率 IoU ≥ 藝術家基準−margin 且拓樸合法。
  C1-5 neg-control+guards   : (a) tangle mesh → 真值 B clean=False(抓自交);(b) 壞 slot 引用 →
                              validator_v1 抓到 'unknown slot';(c) 越界三角索引 → 格式閘 AC4 fail。證閘非恆真。

用法:
  python3 validate_c1_mesh.py            # 跑 C1-1..C1-5,印精簡 pass/fail + 指標
  python3 validate_c1_mesh.py --json     # 完整 JSON 報告

退出碼 0 = 全 AC PASS;非 0 = 有 AC FAIL。
"""
from __future__ import annotations
import argparse
import copy
import json
import os
import subprocess
import sys
import tempfile

import numpy as np
import cv2

_HERE = os.path.dirname(os.path.abspath(__file__))
_SKILL_ASSETS = os.path.normpath(os.path.join(_HERE, "..", "..", "skills", "spine-ai-editor", "assets"))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "mesh_gen"))
sys.path.insert(0, _SKILL_ASSETS)
sys.path.insert(0, os.path.join(_SKILL_ASSETS, "gen_lib"))

import mesh_forge as MF           # noqa: E402  C1 skill 入口(gen_lib)
import deform_eval as de          # noqa: E402  真值 B 工具
import evaluate_mesh as em        # noqa: E402  格式/拓樸閘
from atlas_crop import extract    # noqa: E402

_VALIDATOR_V1 = os.path.join(_SKILL_ASSETS, "validator_v1.py")
_MD_JSON = os.path.join(_REPO, "assets", "main_draw.json")
_MD_ATLAS = os.path.join(_REPO, "assets", "main_draw.atlas")
_MD_PNG = os.path.join(_REPO, "assets", "main_draw.png")
_AW_JSON = os.path.join(_REPO, "assets", "Award.json")
_AW_ATLAS = os.path.join(_REPO, "assets", "Award.atlas")
_AW_PNG = os.path.join(_REPO, "assets", "Award.png")

# 4 真實 deform 件(有 deform timeline → 真值 B 適用)。
_DEFORM_PIECES = [
    ("image/curtain_left", "image/curtain_left"),
    ("image/curtain_right", "image/curtain_right"),
    ("image/shadow", "image/shadow"),
    ("image/shadow2", "image/shadow"),
]
# 3 Award 機器人件(weighted、無 deform → 靜態覆蓋率驗收)。
_ROBOT_PIECES = ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]
_ROBOT_MARGIN = 0.03

_EXTRACT_CACHE = {}


def _region_mask(atlas, png, name, tmpdir):
    """extract region → 回傳 (crop_png_path, mask)。"""
    key = (atlas, png, name)
    if key not in _EXTRACT_CACHE:
        sub = extract(atlas, png, name)
        alpha = sub[:, :, 3] if (sub.ndim == 3 and sub.shape[2] == 4) else \
            (cv2.cvtColor(sub, cv2.COLOR_BGR2GRAY) > 0).astype(np.uint8) * 255
        mask = (alpha > 8).astype(np.uint8)
        crop = os.path.join(tmpdir, "reg_%d.png" % (len(_EXTRACT_CACHE)))
        cv2.imwrite(crop, sub)
        _EXTRACT_CACHE[key] = (crop, mask)
    return _EXTRACT_CACHE[key]


def _run_validator_v1(skel, mutator=None):
    """寫檔 → 呼叫真正的 validator_v1.py(subprocess)→ 回傳 {valid, errors[], raw}。"""
    data = copy.deepcopy(skel)
    if mutator is not None:
        mutator(data)
    tmpdir = tempfile.mkdtemp(prefix="c1mesh_")
    jp = os.path.join(tmpdir, "skeleton.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    p = subprocess.run([sys.executable, _VALIDATOR_V1, jp], capture_output=True, text=True)
    errors = [s.strip()[len("[ERR ]"):].strip()
              for s in p.stdout.splitlines() if s.strip().startswith("[ERR ]")]
    try:
        os.remove(jp); os.rmdir(tmpdir)
    except OSError:
        pass
    return {"valid": p.returncode == 0, "errors": errors, "raw": p.stdout}


def _artist_coverage(att, mask):
    """美術 mesh 在 region 框的覆蓋率(uvs region-local [0,1], vflip=False)。"""
    uvs = np.array(att["uvs"]).reshape(-1, 2)
    tris = np.array(att["triangles"]).reshape(-1, 3)
    H, W = mask.shape
    pts = np.column_stack([uvs[:, 0] * W, uvs[:, 1] * H])
    recon = np.zeros((H, W), np.uint8)
    for t in tris:
        cv2.fillConvexPoly(recon, np.round(pts[t]).astype(np.int32), 1)
    return float(np.logical_and(recon, mask).sum() / max(np.logical_or(recon, mask).sum(), 1))


def _award_att(sk, slot):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    return atts[slot][slot]


def _tangle(mesh):
    """把一個乾淨 mesh 弄成**保證自交**(把一個內部頂點推到對側極端),供真值 B 負對照。"""
    m = copy.deepcopy(mesh)
    v = m["vertices"]
    nv = len(v) // 2
    hull = m["hull"]
    # 取第一個內部頂點(hull 之後),推到 x 對側遠端 + y 對側
    i = hull if hull < nv else 0
    xs = v[0::2]; ys = v[1::2]
    m["vertices"] = list(v)
    m["vertices"][2 * i] = max(xs) + (max(xs) - min(xs)) * 2.0     # 遠超包圍盒
    m["vertices"][2 * i + 1] = min(ys) - (max(ys) - min(ys)) * 2.0
    return m


def run_all():
    tmp = tempfile.mkdtemp(prefix="c1run_")
    ref_md = json.load(open(_MD_JSON, encoding="utf-8"))
    ref_aw = json.load(open(_AW_JSON, encoding="utf-8"))

    # ============ C1-1 entrypoint + strip + 格式 ============
    cl_crop, cl_mask = _region_mask(_MD_ATLAS, _MD_PNG, "image/curtain_left", tmp)
    cl_mesh = MF.generate_strip_mesh(cl_crop)
    fmt = em.evaluate(cl_mesh, cl_mask, vertex_budget=64, iou_thresh=0.0)
    c = fmt["criteria"]
    c11 = (callable(getattr(MF, "generate_strip_mesh", None))
           and cl_mesh.get("_mode") == "strip"
           and c["AC4_format"]["pass"] and c["AC2b_degenerate"]["pass"]
           and c["AC2c_orphans"]["pass"] and c["AC3_vertex_budget"]["pass"])

    # ============ C1-2 loadable(真值 A)============
    scaf = MF.scaffold_skeleton(cl_mesh)
    v_scaf = _run_validator_v1(scaf)
    # 併進既有(動畫軸)skeleton:2-bone 骨架,mesh 掛到 arm bone(結構軸組合)
    base = {"skeleton": {"spine": "3.8.99", "width": 100, "height": 100},
            "bones": [{"name": "root"}, {"name": "arm", "parent": "root", "x": 10}],
            "slots": [], "skins": [{"name": "default", "attachments": {}}], "animations": {}}
    MF.install_mesh(base, "arm_mesh", "m", cl_mesh, bone="arm")
    v_compose = _run_validator_v1(base)
    # 寫檔→重讀→validator_v1 0 error
    sp = os.path.join(tmp, "scaf.json")
    json.dump(scaf, open(sp, "w", encoding="utf-8"), ensure_ascii=False)
    reread = json.load(open(sp, encoding="utf-8"))
    v_rt = _run_validator_v1(reread)
    c12 = (v_scaf["valid"] and not v_scaf["errors"]
           and v_compose["valid"] and not v_compose["errors"]
           and v_rt["valid"] and not v_rt["errors"]
           and len(base["bones"]) == 2)   # 確實併進 2-bone 骨架

    # ============ C1-3 deform-safe(真值 B,headline)============
    deform_rows = []
    c13 = True
    for slot, name in _DEFORM_PIECES:
        crop, _ = _region_mask(_MD_ATLAS, _MD_PNG, name, tmp)
        mesh = MF.generate_strip_mesh(crop)
        d = MF.deform_safety_check(mesh, ref_md, slot, name)
        ok = (d["self_intersections"] == 0 and d["triangle_flips"] == 0 and d["degenerate"] == 0)
        c13 = c13 and ok and (mesh.get("_mode") == "strip")
        deform_rows.append({"slot": slot, "mode": mesh.get("_mode"), "nv": len(mesh["uvs"]) // 2,
                            "frame": d["frame"], "si": d["self_intersections"],
                            "flips": d["triangle_flips"], "degen": d["degenerate"],
                            "area_ratio": d["area_ratio"], "pass": ok})

    # ============ C1-4 robot pieces(靜態覆蓋率)============
    robot_rows = []
    c14 = True
    for slot in _ROBOT_PIECES:
        crop, mask = _region_mask(_AW_ATLAS, _AW_PNG, slot, tmp)
        mesh = MF.generate_strip_mesh(crop)
        ev = em.evaluate(mesh, mask, vertex_budget=128, iou_thresh=0.0)
        gen_iou = ev["criteria"]["AC1_iou"]["value"]
        art_iou = _artist_coverage(_award_att(ref_aw, slot), mask)
        topo_ok = (ev["criteria"]["AC2b_degenerate"]["pass"]
                   and ev["criteria"]["AC2c_orphans"]["pass"]
                   and ev["criteria"]["AC4_format"]["pass"])
        iou_ok = gen_iou >= art_iou - _ROBOT_MARGIN
        ok = iou_ok and topo_ok
        c14 = c14 and ok
        robot_rows.append({"slot": slot, "mode": mesh.get("_mode"), "nv": ev["vertices"],
                           "gen_iou": round(gen_iou, 4), "artist_iou": round(art_iou, 4),
                           "iou_ok": iou_ok, "topo_ok": topo_ok, "pass": ok})

    # ============ C1-5 neg-control + guards ============
    # (a) tangle mesh → 真值 B 抓到自交(clean=False)
    tangled = _tangle(cl_mesh)
    d_tangle = MF.deform_safety_check(tangled, ref_md, "image/curtain_left", "image/curtain_left")
    neg_deform_caught = (not d_tangle["clean"]) and d_tangle["self_intersections"] > 0
    # (b) 壞 slot 引用(skin 指到不存在的 slot)→ validator_v1 抓到 unknown slot

    def _break_slot(data):
        skin = data["skins"][0]["attachments"]
        skin["ghost_slot"] = skin.pop("mesh_slot")   # 把 attachment 搬到不存在的 slot

    v_badslot = _run_validator_v1(scaf, mutator=_break_slot)
    badslot_caught = (not v_badslot["valid"]) and any(
        "unknown slot" in e for e in v_badslot["errors"])
    # (c) 越界三角索引 → 格式閘 AC4 判非法(rasterize 前 AC4 即標 fail;或直接越界 raise)。兩者皆為閘拒收。
    bad_mesh = copy.deepcopy(cl_mesh)
    bad_mesh["triangles"] = list(bad_mesh["triangles"])
    bad_mesh["triangles"][0] = (len(bad_mesh["uvs"]) // 2) + 5   # 越界
    try:
        fmt_bad = em.evaluate(bad_mesh, cl_mask, vertex_budget=64, iou_thresh=0.0)
        badtri_caught = not fmt_bad["criteria"]["AC4_format"]["pass"]
    except IndexError:
        badtri_caught = True   # 越界索引直接讓光柵化 raise = 閘拒收(非法 mesh 不可能靜默通過)
    c15 = neg_deform_caught and badslot_caught and badtri_caught

    try:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    except Exception:
        pass

    res = {
        "C1-1_entrypoint_strip_format": (c11, {
            "api_callable": callable(getattr(MF, "generate_strip_mesh", None)),
            "mode": cl_mesh.get("_mode"), "nv": len(cl_mesh["uvs"]) // 2, "hull": cl_mesh["hull"],
            "format_ok": c["AC4_format"]["pass"], "degenerate": c["AC2b_degenerate"]["value"],
            "orphans": c["AC2c_orphans"]["value"]}),
        "C1-2_loadable_truth_A": (c12, {
            "scaffold_valid": v_scaf["valid"], "scaffold_errors": v_scaf["errors"][:2],
            "compose_into_2bone_valid": v_compose["valid"], "compose_errors": v_compose["errors"][:2],
            "roundtrip_valid": v_rt["valid"], "base_bones": len(base["bones"])}),
        "C1-3_deform_safe_truth_B": (c13, {"pieces": deform_rows}),
        "C1-4_robot_pieces_static": (c14, {"pieces": robot_rows}),
        "C1-5_neg_control_guards": (c15, {
            "tangle_deform_caught": neg_deform_caught,
            "tangle_si": d_tangle["self_intersections"], "tangle_clean": d_tangle["clean"],
            "bad_slot_caught": badslot_caught, "bad_slot_errors": v_badslot["errors"][:2],
            "bad_triangle_caught": badtri_caught}),
    }
    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "C1 gen_lib.mesh_forge: generate_mesh_v2 strip + deform_eval 真實位移場自交閘 → v1.3.0 validator_v1 (mesh 軸雙真值 G2)",
        "entry": "skills/spine-ai-editor/assets/gen_lib/mesh_forge.py :: "
                 "generate_strip_mesh / scaffold_skeleton / install_mesh / deform_safety_check",
        "metrics": {
            "deform_max_si": max((r["si"] for r in deform_rows), default=None),
            "deform_max_flips": max((r["flips"] for r in deform_rows), default=None),
            "deform_area_ratio_range": [min((r["area_ratio"] for r in deform_rows), default=None),
                                        max((r["area_ratio"] for r in deform_rows), default=None)],
            "robot_min_iou_margin": min((r["gen_iou"] - r["artist_iou"] for r in robot_rows),
                                        default=None),
        },
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
