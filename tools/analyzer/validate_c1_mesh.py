#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C1 閘 — `gen_lib.mesh_forge` mesh 生成 + 變形自交閘(spine-ai-editor 2.0 Phase C1)。

v1.3.0 只**檢查**既有 mesh、不生成、也沒有「會不會在真實動畫拉扯下撕裂」的機讀閘。C1 把 repo 的
**確定性 strip mesh 生成**(`generate_mesh_v2`)+ **真實位移場轉移閘**(`deform_eval.transfer_deform_check`)
抽成 skill 入口 `skills/spine-ai-editor/assets/gen_lib/mesh_forge.py`,並機械化驗:
**對 robot / curtain 件生成 strip mesh,施加真實(main_draw 窗簾)deform 位移場後 self-intersection = 0**
(MERGE_PLAN Phase C1 的 AC)。

**驗的是什麼(為何這個 chunk 有價值)**:
  「生成器就緒 ≠ 評估器就緒」的互補面:B 階段把**動畫生成**接上 v1.3.0 雙真值;C1 把 **mesh 生成**接上
  **變形幾何閘**——證生成的網格不只「靜態輪廓吻合」,還「在真實 deform 幅度下不撕裂/不翻面」。
   · 真實 curtain(兩片,9 支動畫全有 deform)經 forge strip → 自身真實位移場 → **si=0 且 IoU≥藝術家基準**
     (乾淨 **且** 非空殼)。
   · 位移場以 UV 表達 → **可轉移到任一拓樸**:同一真實窗簾場轉移到 robot 件 / 合成肢體的生成 mesh → si=0。
   · auto 模式對 blob-aspect 的真實 robot 件**不硬塞 strip**(回退 Delaunay),是正確路由(honest)。
   · 閘**校準**:`benchmark_real` 對 4 片真實藝術家 mesh × 9 動畫 worst si/flips/degen = 0(閘與真值一致)。
   · 負對照(閘非恆真):對生成 mesh 做拓樸破壞(換 hull 頂點造交叉 / 折疊造翻面 / 塌陷造退化)→ 閘**抓到**。

**honest 核心洞見(本 run 實測)**:放大合成場破不破,**取決於件幾何**——細長的合成肢體把真實窗簾場 **×8**
  放大(面積比 ~42)仍 si=0,而較寬的窗簾 ×8(面積比 ~6.6)就撕裂。故閘的「牙」**不能**用「放大合成場」
  當可靠示範子(細長件會假性過關,呼應 `deform_eval` 警告「別拿未校準 stress_field 當閘」),必須用
  **拓樸破壞**(換 hull/折疊/塌陷)+ **真實場轉移** 來驗。triangle_flips 須相對**原 mesh** winding 量
  (以破壞後 mesh 自身為基準 flip 恆 0),與產線閘 `transfer_deform_check`(未變形為基準檢變形後)同語義。

**AC(全部客觀、可機讀)**:
  C1-1 entrypoint+strip  : `mesh_forge.generate_strip_mesh` 經**公開 API** 對真實 curtain_left 產 strip mesh——
                           mode=="strip"、**unweighted**(vertices.len==uvs.len)、hull 頂點排最前、三角索引合法且
                           winding 一致(setup 全同號、0 退化)、頂點數在預算內(≈rows×cols)。非臨時腳本。
  C1-2 curtain-real-si0  : 真實 **curtain_left + curtain_right** 各經 forge strip → 轉移**自身**真實 deform 場 →
                           `self_intersections==0 且 triangle_flips==0 且 degenerate==0`(clean),且
                           **IoU ≥ 藝術家 mesh 基準**(證乾淨非空殼)。← **headline AC**。
  C1-3 robot+transfer-si0: (a) 真實 **robot 身體**件經 forge auto → **回退 Delaunay**(blob-aspect,不硬塞 strip)→
                           轉移真實窗簾場 → si=0;(b) 合成**肢體**(tall row-convex)經 forge → **strip** →
                           轉移同一真實窗簾場 → si=0。證 forge+閘在**不同件形狀 × 真實位移場**下一致過。
  C1-4 checker-validated : `deform_eval.benchmark_real(main_draw)` 對 4 片真實藝術家 mesh × 9 動畫 worst
                           si/flips/degen **全 0**(`_checker_validated`==True)→ 閘的 checker 與藝術家真值一致
                           (閘有校準、非武斷寬鬆)。
  C1-5 non-vacuous(neg) : 對 C1-2 的乾淨 strip mesh 做三種拓樸破壞,閘由**對應通道各自抓到**:
                           (a) 換 hull 頂點 → self_intersections>0;(b) 折疊(鏡射半邊,相對原 winding)→
                           triangle_flips>0;(c) 塌陷(兩頂點重合)→ degenerate>0。證閘非恆真。
                           (觀察:×8 放大場破不破取決於件幾何——細長肢體仍 clean、較寬窗簾已撕裂,故放大場
                           非可靠示範子;記錄於 detail。)

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
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILL_ASSETS = os.path.join(_REPO, "skills", "spine-ai-editor", "assets")
for _p in (os.path.join(_REPO, "tools", "mesh_gen"), _SKILL_ASSETS,
           os.path.join(_SKILL_ASSETS, "gen_lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import cv2                              # noqa: E402
import deform_eval as de               # noqa: E402  真實位移場轉移 + benchmark_real(校準)
import mesh_forge as MF                # noqa: E402  C1 skill 入口(gen_lib)

_SKEL = os.path.join(_REPO, "assets", "main_draw.json")
_ATLAS = os.path.join(_REPO, "assets", "main_draw.atlas")
_PNG = os.path.join(_REPO, "assets", "main_draw.png")
_ROBOT_PSD = os.path.join(_REPO, "assets", "robot_parts.psd")
_ROWS, _COLS = 10, 3


# ----------------------------------------------------------------- fixtures
def _crop(name, out_png):
    """真實 main_draw region → 緊湊 PNG + alpha mask。"""
    return MF.crop_atlas_region(_ATLAS, _PNG, name, out_png)


def _robot_body_png(out_png):
    """真實 robot_parts.psd 的『身體』件 → 緊湊 RGBA PNG(blob-aspect,測 auto 回退)。"""
    from psd_tools import PSDImage
    psd = PSDImage.open(_ROBOT_PSD)
    body = [l for l in psd.descendants() if not l.is_group() and l.name == "身體"][0]
    im = body.topil().convert("RGBA")
    im.save(out_png)
    return out_png


def _synth_limb_png(out_png, H=260, W=90):
    """合成一條 tall、row-convex、略彎的肢體(代表 rig 後的機器人手臂/腿:strip 典型來源)。
    確定性(無隨機),每列單一 alpha 區段 → is_row_convex 成立 → forge 走 strip。"""
    mask = np.zeros((H, W), np.uint8)
    for y in range(20, H - 20):
        t = (y - 20) / (H - 40)
        half = int(34 * (1 - 0.45 * t))                 # 上粗下細
        cx = W // 2 + int(10 * np.sin(t * 2.2))         # 輕微彎曲
        mask[y, max(0, cx - half):min(W, cx + half)] = 255
    rgba = np.zeros((H, W, 4), np.uint8)
    rgba[..., :3] = 200
    rgba[..., 3] = mask
    cv2.imwrite(out_png, rgba)
    return out_png


# ----------------------------------------------------------------- mesh 結構檢查
def _strip_structure_ok(mesh):
    """unweighted + hull-first + 三角索引合法 + winding 一致 + 0 退化(setup)。"""
    nv = len(mesh["uvs"]) // 2
    unweighted = (len(mesh["vertices"]) == len(mesh["uvs"]) == 2 * nv)
    tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    idx_ok = bool(tris.min() >= 0 and tris.max() < nv)
    hull_ok = (0 < mesh["hull"] <= nv)
    v = np.array(mesh["vertices"], dtype=np.float64).reshape(-1, 2)
    signs = np.array([de.signed_area(v, t) for t in tris])
    degen = int((np.abs(signs) < 1e-6).sum())
    same_winding = bool((signs > 0).all() or (signs < 0).all())
    return {
        "unweighted": unweighted, "indices_valid": idx_ok, "hull_first": hull_ok,
        "degenerate_setup": degen, "consistent_winding": same_winding,
        "ok": unweighted and idx_ok and hull_ok and degen == 0 and same_winding,
    }


# ----------------------------------------------------------------- 拓樸破壞(負對照)
def _corrupt_swap_hull(mesh):
    """換兩個 hull 頂點座標 → 外周 self-crossing(figure-8)。"""
    bad = copy.deepcopy(mesh)
    v = bad["vertices"]
    i, j = 1, mesh["hull"] // 2
    v[2 * i], v[2 * i + 1], v[2 * j], v[2 * j + 1] = v[2 * j], v[2 * j + 1], v[2 * i], v[2 * i + 1]
    return bad


def _corrupt_fold(mesh):
    """把下半頂點繞中線鏡射(y 折疊)→ 大量三角翻面。"""
    bad = copy.deepcopy(mesh)
    v = np.array(bad["vertices"], dtype=np.float64).reshape(-1, 2)
    ymid = (v[:, 1].min() + v[:, 1].max()) / 2.0
    lo = v[:, 1] < ymid
    v[lo, 1] = 2 * ymid - v[lo, 1]
    bad["vertices"] = [round(float(x), 3) for x in v.reshape(-1)]
    return bad


def _corrupt_collapse(mesh):
    """把頂點 2 塌到頂點 1(兩頂點重合)→ 共用它們的三角退化(面積≈0)。"""
    bad = copy.deepcopy(mesh)
    v = bad["vertices"]
    v[4], v[5] = v[2], v[3]
    return bad


def _gate_corrupt(orig_mesh, corrupt_mesh):
    """把拓樸破壞當成『從原 mesh 的一次位移』:以**原 mesh** 的 winding/面積為基準,檢破壞後位置。
    這才能驗出 triangle_flips(相對原 setup 變號);否則用破壞 mesh 自身當基準,flip 恆 0。
    與產線閘 `transfer_deform_check`(以未變形 mesh 為基準檢變形後)同一語義。"""
    s = np.array(orig_mesh["vertices"], dtype=np.float64).reshape(-1, 2)
    t = np.array(orig_mesh["triangles"], dtype=np.int32).reshape(-1, 3)
    sd = np.array(corrupt_mesh["vertices"], dtype=np.float64).reshape(-1, 2)
    signs = [de.signed_area(s, x) > 0 for x in t]
    area = sum(abs(de.signed_area(s, x)) for x in t)
    return de.eval_pose(sd, t, signs, area)


# ----------------------------------------------------------------- AC
def run_all():
    tmp = tempfile.mkdtemp(prefix="c1mesh_")
    # ---- 真實窗簾位移場(可轉移)----
    uvs_cl, field_cl, frame_cl = MF.load_real_deform_field(_SKEL, "image/curtain_left", "image/curtain_left")
    uvs_cr, field_cr, frame_cr = MF.load_real_deform_field(_SKEL, "image/curtain_right", "image/curtain_right")

    # ---- C1-1 entrypoint + strip 結構 ----
    cl_png = _crop("image/curtain_left", os.path.join(tmp, "cl.png"))
    mesh_cl = MF.generate_strip_mesh(os.path.join(tmp, "cl.png"))
    struct = _strip_structure_ok(mesh_cl)
    nv_cl = len(mesh_cl["uvs"]) // 2
    budget_ok = nv_cl <= _ROWS * _COLS + 2
    c11 = (callable(getattr(MF, "generate_strip_mesh", None))
           and mesh_cl.get("_mode") == "strip" and struct["ok"] and budget_ok)

    # ---- C1-2 真實兩窗簾 strip → 自身真實場 → si=0 + IoU≥藝術家 ----
    def _artist_iou(slot, name, mask):
        sk = json.load(open(_SKEL, encoding="utf-8"))
        skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
        a = skin.get("attachments", skin)[slot][name]
        u = np.array(a["uvs"]).reshape(-1, 2); tr = np.array(a["triangles"]).reshape(-1, 3)
        H, W = mask.shape
        rp = np.column_stack([u[:, 0] * W, u[:, 1] * H])
        recon = np.zeros((H, W), np.uint8)
        for t in tr:
            cv2.fillConvexPoly(recon, np.round(rp[t]).astype(np.int32), 1)
        return float(np.logical_and(recon, mask).sum() / np.logical_or(recon, mask).sum())

    mask_cl = cl_png  # alpha mask returned by _crop
    iou_cl = MF.coverage_iou(mesh_cl, mask_cl)
    base_cl = _artist_iou("image/curtain_left", "image/curtain_left", mask_cl)
    gate_cl = MF.deform_safety_check(mesh_cl, uvs_cl, field_cl)

    mask_cr = _crop("image/curtain_right", os.path.join(tmp, "cr.png"))
    mesh_cr = MF.generate_strip_mesh(os.path.join(tmp, "cr.png"))
    iou_cr = MF.coverage_iou(mesh_cr, mask_cr)
    base_cr = _artist_iou("image/curtain_right", "image/curtain_right", mask_cr)
    gate_cr = MF.deform_safety_check(mesh_cr, uvs_cr, field_cr)

    c12 = (mesh_cl.get("_mode") == "strip" and gate_cl["clean"] and iou_cl >= base_cl
           and mesh_cr.get("_mode") == "strip" and gate_cr["clean"] and iou_cr >= base_cr)

    # ---- C1-3 robot(auto→delaunay)+ 合成肢體(strip),同一真實窗簾場 → si=0 ----
    rb_png = _robot_body_png(os.path.join(tmp, "robot_body.png"))
    mesh_rb = MF.generate_strip_mesh(rb_png)                     # auto → blob 回退 delaunay
    gate_rb = MF.deform_safety_check(mesh_rb, uvs_cl, field_cl)  # 轉移真實窗簾場
    robot_fallback = mesh_rb.get("_mode") != "strip"            # blob-aspect 不硬塞 strip(正確路由)

    lb_png = _synth_limb_png(os.path.join(tmp, "limb.png"))
    mesh_lb = MF.generate_strip_mesh(lb_png)                     # tall row-convex → strip
    gate_lb = MF.deform_safety_check(mesh_lb, uvs_cl, field_cl)  # 轉移同一真實窗簾場
    limb_strip = mesh_lb.get("_mode") == "strip"

    c13 = (robot_fallback and gate_rb["clean"] and limb_strip and gate_lb["clean"])

    # ---- C1-4 checker 校準(閘與藝術家真值一致)----
    bench = de.benchmark_real(_SKEL)
    worst = bench["_worst_across_all"]
    checker_ok = bench["_checker_validated"]
    n_real_meshes = len([k for k in bench if not k.startswith("_")])
    c14 = (checker_ok and worst["self_intersections"] == 0 and worst["triangle_flips"] == 0
           and worst["degenerate"] == 0 and n_real_meshes >= 4)

    # ---- C1-5 負對照(拓樸破壞有牙;× 放大場=geometry-dependent 觀察,非 pass 條件)----
    g_swap = _gate_corrupt(mesh_cl, _corrupt_swap_hull(mesh_cl))
    g_fold = _gate_corrupt(mesh_cl, _corrupt_fold(mesh_cl))
    g_coll = _gate_corrupt(mesh_cl, _corrupt_collapse(mesh_cl))
    swap_caught = g_swap["self_intersections"] > 0
    fold_caught = g_fold["triangle_flips"] > 0
    coll_caught = g_coll["degenerate"] > 0
    # 閘的牙 = 三種拓樸破壞各由對應通道抓到(非恆真)。
    c15 = swap_caught and fold_caught and coll_caught
    # 觀察(非 pass 條件):放大合成場破不破,**取決於件幾何**——細長肢體 ×8 真實場(ar 大)仍 clean,
    # 較寬的窗簾 ×8 已撕裂。故「放大場」不是可靠的閘-有牙示範子(呼應 deform_eval 警告:別拿未校準
    # 合成場當閘),牙須靠拓樸破壞 + 真實場轉移驗。
    x8_curtain = MF.deform_safety_check(mesh_cl, uvs_cl, field_cl * 8.0)
    x8_limb = MF.deform_safety_check(mesh_lb, uvs_cl, field_cl * 8.0)

    # cleanup
    import shutil
    shutil.rmtree(tmp, ignore_errors=True)

    res = {
        "C1-1_entrypoint_strip": (c11, {
            "api_callable": callable(getattr(MF, "generate_strip_mesh", None)),
            "mode": mesh_cl.get("_mode"), "nv": nv_cl, "hull": mesh_cl["hull"],
            "tris": len(mesh_cl["triangles"]) // 3, "vert_budget_ok": budget_ok,
            "structure": struct}),
        "C1-2_curtain_real_si0": (c12, {
            "curtain_left": {"mode": mesh_cl.get("_mode"), "nv": nv_cl,
                             "iou": round(iou_cl, 4), "artist_baseline": round(base_cl, 4),
                             "iou_ok": iou_cl >= base_cl, "deform_frame": frame_cl,
                             "area_ratio": gate_cl["area_ratio"],
                             "self_intersections": gate_cl["self_intersections"],
                             "triangle_flips": gate_cl["triangle_flips"],
                             "degenerate": gate_cl["degenerate"], "clean": gate_cl["clean"]},
            "curtain_right": {"mode": mesh_cr.get("_mode"), "nv": len(mesh_cr["uvs"]) // 2,
                              "iou": round(iou_cr, 4), "artist_baseline": round(base_cr, 4),
                              "iou_ok": iou_cr >= base_cr, "deform_frame": frame_cr,
                              "area_ratio": gate_cr["area_ratio"],
                              "self_intersections": gate_cr["self_intersections"],
                              "triangle_flips": gate_cr["triangle_flips"],
                              "degenerate": gate_cr["degenerate"], "clean": gate_cr["clean"]}}),
        "C1-3_robot_transfer_si0": (c13, {
            "robot_body": {"mode": mesh_rb.get("_mode"), "nv": len(mesh_rb["uvs"]) // 2,
                           "tris": len(mesh_rb["triangles"]) // 3,
                           "auto_fallback_not_strip": robot_fallback,
                           "area_ratio": gate_rb["area_ratio"],
                           "self_intersections": gate_rb["self_intersections"],
                           "triangle_flips": gate_rb["triangle_flips"], "clean": gate_rb["clean"]},
            "synth_limb": {"mode": mesh_lb.get("_mode"), "nv": len(mesh_lb["uvs"]) // 2,
                           "is_strip": limb_strip, "area_ratio": gate_lb["area_ratio"],
                           "self_intersections": gate_lb["self_intersections"],
                           "triangle_flips": gate_lb["triangle_flips"], "clean": gate_lb["clean"]},
            "note": "位移場 UV 可轉移到任一拓樸;robot blob→delaunay(正確路由)、limb tall→strip"}),
        "C1-4_checker_validated": (c14, {
            "checker_validated": checker_ok, "worst_across_all": worst,
            "n_real_meshes": n_real_meshes,
            "note": "benchmark_real 對 4 片真實藝術家 mesh × 9 動畫 worst si/flips/degen=0 → 閘與真值一致"}),
        "C1-5_non_vacuous_neg": (c15, {
            "swap_hull_self_intersections": g_swap["self_intersections"], "swap_caught": swap_caught,
            "fold_triangle_flips": g_fold["triangle_flips"], "fold_caught": fold_caught,
            "collapse_degenerate": g_coll["degenerate"], "collapse_caught": coll_caught,
            "x8_curtain_area_ratio": x8_curtain["area_ratio"], "x8_curtain_clean": x8_curtain["clean"],
            "x8_limb_area_ratio": x8_limb["area_ratio"], "x8_limb_clean": x8_limb["clean"],
            "note": "閘的牙=三種拓樸破壞各由對應通道抓到;×8 放大場破不破取決於件幾何"
                    "(細長肢體仍 clean、較寬窗簾已撕裂)→ 放大場非可靠示範子,牙靠拓樸破壞 + 真實場轉移"}),
    }
    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "C1 gen_lib.mesh_forge: strip mesh 生成 + 真實位移場轉移自交閘(robot/curtain → si=0)",
        "entry": "skills/spine-ai-editor/assets/gen_lib/mesh_forge.py :: "
                 "generate_strip_mesh / load_real_deform_field / deform_safety_check / forge_and_gate",
        "metrics": {
            "curtain_left": {"mode": mesh_cl.get("_mode"), "iou": round(iou_cl, 4),
                             "si": gate_cl["self_intersections"], "area_ratio": gate_cl["area_ratio"]},
            "curtain_right": {"mode": mesh_cr.get("_mode"), "iou": round(iou_cr, 4),
                              "si": gate_cr["self_intersections"], "area_ratio": gate_cr["area_ratio"]},
            "robot_body": {"mode": mesh_rb.get("_mode"), "si": gate_rb["self_intersections"]},
            "synth_limb": {"mode": mesh_lb.get("_mode"), "si": gate_lb["self_intersections"],
                           "area_ratio": gate_lb["area_ratio"]},
            "checker_worst": worst,
            "x8_curtain_clean": x8_curtain["clean"], "x8_limb_clean": x8_limb["clean"]},
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
