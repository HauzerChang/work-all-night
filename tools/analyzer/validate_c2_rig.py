#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C2 閘 — `gen_lib.rig` weighted mesh 生成 + rig 自動推斷(spine-ai-editor 2.0 Phase C2)。

B2/B3/B4 抽了 repo 的**動畫生成**、C1 抽了 **mesh 生成 + 變形自交閘**;C2 把 repo 的 **S5 rig 自動化**
(`infer_tree` 肢體父子樹 + `infer_pivots` 接觸縫關節 pivot)與 **weighted mesh 生成**
(`generate_weighted_mesh` heat-diffusion / BBW 近似)抽成 skill 入口
`skills/spine-ai-editor/assets/gen_lib/rig.py`,成為**結構軸的 rig 分支**:
v1.3.0 只能修既有動畫手感、C1 能生成耐變形 mesh;C2 讓 2.0 能**自動推出骨架階層 + 關節 pivot +
生成接進關節鏈的 weighted mesh**,組成可被關節 articulate 的完整 rig。

**驗的是什麼(為何這個 chunk 有價值)**:
  「件只能整塊剛體位移、沒有骨架階層、關節 pivot 放錯」是 structural 限制;C2 證經**公開 API**:
   · rig 推斷對 **Award 機器人藝術家真值**:自動推得 root==身體 + 父子樹==ROBOT_TREE(拓樸精確)、
     關節 pivot 落接觸縫(中位誤差 < 子件質心 baseline、max err/rig < 0.10 draft 級)。
   · weighted mesh 生成對 **Award 真值**:partition of unity、≤4 骨/頂點、setup 乾淨、真實動畫骨骼
     變形 si=0 / flip=0(過 weighted_deform_eval 同一道閘,已對藝術家真值重現)、頂點預算 ≤1.4× 藝術家。
   · 端到端對**合成多跳肢體鏈 fixture**(body→arm→forearm→hand,arm/forearm 皆 weighted mesh 當鏈中段):
     經 `build_rigged_skeleton --rig --weighted` → 骨鏈拓樸(非星形、深 ≥3)、控制骨接進關節鏈、
     setup 不位移、**轉關節遞迴帶動後代**(多跳:轉 body 帶動隔一跳的 forearm)、變形逐幀 si=0 / flip=0。
   · 閘**非恆真**(負對照):(a) weighted-only 版轉關節**全脫鉤**(件不動)(b) 把 effect 件當結構推**汙染樹**
     (c) pivot 隨機 / 互換指派 err/rig >> 0.10 → 證推斷有鑑別力、須結構輸入。

**AC(全部客觀、可機讀;經 rig.py 公開 API)**:
  C2-1 infer-truth       : `infer_rig_tree`(Award 結構件)→ root==身體 且 tree==ROBOT_TREE;
                           `infer_joint_pivots` 中位誤差 < 子件質心 baseline 且 max err/rig_scale < 0.10。
  C2-2 weighted-gen-truth: `generate_weighted_part` + `weighted_part_quality`(Award 身體+左手)→
                           partition_ok、≤4 骨/頂點、setup_clean、worst_si==0 且 worst_flip==0、
                           checker_validated、nv ≤ 1.4× 藝術家。
  C2-3 chain-structure   : `build_rigged_skeleton`(合成鏈,rig×weighted)→ 骨鏈非星形、深 ≥3、
                           每 weighted mesh 件控制骨 parent==該件關節骨 b_{nm}、骨 index 合法。
  C2-4 recursive-drive   : (headline) setup 不位移(rig==weighted-only <0.05px)+ 轉每個關節 → **後代**件
                           位移 > 門檻、**祖先/旁支** ≈ 0 + 多跳(轉 body 帶動隔一跳 forearm)+ 關節旋轉逐幀
                           結構件 si==0 / flip==0。
  C2-5 gate-non-vacuous  : (a) weighted-only 版轉關節全脫鉤(位移 ≈ 0)(b) effect 件當結構 → 樹被汙染
                           (c) pivot 隨機 / 互換負對照 med err/rig >> 0.10 → 閘有牙。

用法:
  python3 validate_c2_rig.py            # 跑 C2-1..C2-5,印精簡 pass/fail + 指標
  python3 validate_c2_rig.py --json     # 完整 JSON 報告

退出碼 0 = 全 AC PASS;非 0 = 有 AC FAIL。
"""
from __future__ import annotations
import argparse
import json
import os
import sys
import tempfile
import shutil

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILL_ASSETS = os.path.join(_REPO, "skills", "spine-ai-editor", "assets")
sys.path.insert(0, os.path.join(_SKILL_ASSETS, "gen_lib"))
sys.path.insert(0, os.path.join(_REPO, "tools", "mesh_gen"))
sys.path.insert(0, os.path.join(_REPO, "tools", "rig"))
sys.path.insert(0, _HERE)

import rig as R                      # noqa: E402  C2 skill 入口(gen_lib)
import weighted_deform_eval as W     # noqa: E402  真值校準(bone world transform / skinning)
# 評估輔助(真相來源,與 chain/combo 閘同一套):載入、取 weighted slot、skinning、旋轉 pose
from validate_rig_weighted_build import (  # noqa: E402
    _load, _weighted_slots, _skin_setup, _pose_rotate, EPS_POSE, THETA,
)
from validate_rig_weighted_chain import _parent_map, _ancestors_or_self  # noqa: E402
from infer_pivots import ROBOT_TREE  # noqa: E402

BODY = "機器人拆件/身體"
HALO = "機器人拆件/光暈"
LEFT_HAND = "機器人拆件/左手"
ARTIC_MIN = 5.0     # 「該動」的最小平均位移(px)
INERT_MAX = 1e-4    # 「不該動」的位移上界(px)
TAU = 0.10          # pivot 準度門檻(rig_scale 分數)
NV_MULT = 1.4       # weighted mesh 頂點預算上限(× 藝術家)
# weighted 生成品質 AC 的件(max_area 同 repo validate_weighted_gen)
WGEN_PARTS = {BODY: 1500.0, LEFT_HAND: 1400.0}


def _rig_scale(parts, tree):
    """正規化基準 = 父件(軀幹)bounding box 對角線平均(與 validate_pivots 一致)。"""
    parents = {tree[c] for c in tree if tree[c] in parts}
    diags = [float(np.hypot(*(parts[p].max(0) - parts[p].min(0)))) for p in parents]
    return float(np.mean(diags)) if diags else 1.0


# ---------------------------------------------------------------- C2-1 inference truth
def _ac_infer_truth():
    parts, truth, tree_truth, fid = R.award_robot_truth()
    struct = {k: v for k, v in parts.items() if k != HALO}
    root, tree, info = R.infer_rig_tree(struct)
    tree_ok = (root == BODY) and (tree == ROBOT_TREE)

    piv = R.infer_joint_pivots(struct, tree_truth)
    base = R.centroid_pivot_baseline(struct, tree_truth)
    scale = _rig_scale(struct, tree_truth)
    err = {c: float(np.linalg.norm(piv[c] - truth[c])) for c in tree_truth}
    berr = {c: float(np.linalg.norm(base[c] - truth[c])) for c in tree_truth}
    med_err = float(np.median(list(err.values())))
    med_base = float(np.median(list(berr.values())))
    max_rel = max(e / scale for e in err.values())
    piv_ok = (med_err < med_base) and (max_rel < TAU)

    ok = tree_ok and piv_ok
    detail = {
        "inferred_root": root.split("/")[-1], "root_ok": root == BODY,
        "tree_ok": tree == ROBOT_TREE,
        "inferred_tree": {c.split("/")[-1]: p.split("/")[-1] for c, p in tree.items()},
        "pivot_med_err_px": round(med_err, 2), "baseline_med_err_px": round(med_base, 2),
        "beats_baseline": med_err < med_base,
        "pivot_max_err_over_rig": round(max_rel, 3), "tau": TAU,
        "rig_scale_px": round(scale, 1),
    }
    return ok, detail, (parts, truth, tree_truth, struct, piv, scale)


# ---------------------------------------------------------------- C2-2 weighted gen truth
def _ac_weighted_gen():
    rows = {}
    ok = True
    for slot, ma in WGEN_PARTS.items():
        gen = R.generate_weighted_part(R._p("assets/Award.json"), slot, max_area=ma)
        q = R.weighted_part_quality(gen)
        budget_ok = q["nv"] <= q["artist_nv"] * NV_MULT
        part_ok = (q["partition_ok"] and q["max_bones_per_vertex"] <= 4
                   and q["setup_clean"] and q["worst_si"] == 0 and q["worst_flip"] == 0
                   and q["checker_validated"] and budget_ok)
        ok = ok and part_ok
        rows[slot.split("/")[-1]] = {
            "partition_ok": q["partition_ok"], "max_bones": q["max_bones_per_vertex"],
            "setup_clean": q["setup_clean"], "worst_si": q["worst_si"],
            "worst_flip": q["worst_flip"], "checker_validated": q["checker_validated"],
            "nv": q["nv"], "artist_nv": q["artist_nv"], "budget_ok": budget_ok, "pass": part_ok}
    return ok, rows


# ---------------------------------------------------------------- 合成鏈共用:build + 載入 + 驅動量
def _build_chain(tmp):
    psd = R.make_synthetic_limb_chain(os.path.join(tmp, "limb_chain.psd"))
    rw = R.build_rigged_skeleton(psd, os.path.join(tmp, "rw"), rig=True, weighted=True)
    wo = R.build_rigged_skeleton(psd, os.path.join(tmp, "wo"), rig=False, weighted=True)
    return rw, wo


def _chain_eval(rw_dir, wo_dir):
    """載入 rig×weighted 與 weighted-only,算 AC1 結構 / AC2 setup / AC3 遞迴帶動(含多跳)/ AC4 變形。
    回傳 dict(供 C2-3/C2-4/C2-5a 分享,一次 build 一次算)。"""
    skR, bonesR, bynameR, orderR, bidxR, world0R, metaR = _load(rw_dir)
    skW, bonesW, bynameW, orderW, bidxW, world0W, metaW = _load(wo_dir)
    pmapR = _parent_map(bonesR)
    wslotsR = dict(_weighted_slots(skR))
    wslotsW = dict(_weighted_slots(skW))
    wnames = sorted(wslotsR.keys())
    body = next((nm for nm, m in metaR.items() if m.get("role") == "body"), None)

    # ---- AC1 結構:鏈深 >=3、非星形、控制骨 parent == 關節骨、index 合法 ----
    joint_bones = [f"b_{nm}" for nm in metaR if f"b_{nm}" in bynameR]
    max_depth = max((len(_ancestors_or_self(jb, pmapR)) - 1 for jb in joint_bones), default=0)
    non_star = any(pmapR.get(f"b_{nm}") not in ("root", f"b_{body}", None)
                   for nm in metaR if f"b_{nm}" in bynameR)
    ctrl_ok = True
    ctrl_detail = {}
    for nm in wnames:
        v = wslotsR[nm]["vertices"]; i = 0; used = set()
        while i < len(v):
            bc = int(v[i]); i += 1
            for _ in range(bc):
                used.add(int(v[i])); i += 4
        valid_idx = all(0 <= k < len(bonesR) for k in used)
        parents = {bonesR[k].get("parent") for k in used}
        under_joint = parents == {f"b_{nm}"}
        ctrl_ok = ctrl_ok and valid_idx and under_joint
        ctrl_detail[nm] = {"parents": sorted(parents), "joint": f"b_{nm}",
                           "under_joint": under_joint, "idx_valid": valid_idx}
    ac1 = (body is not None) and (max_depth >= 3) and non_star and ctrl_ok and len(wnames) > 0

    # ---- AC2 setup 不位移 ----
    max_pose_dev = 0.0
    for nm in wnames:
        svR, _, _ = _skin_setup(wslotsR[nm], world0R, bidxR)
        svW, _, _ = _skin_setup(wslotsW[nm], world0W, bidxW)
        if svR.shape == svW.shape:
            max_pose_dev = max(max_pose_dev, float(np.max(np.linalg.norm(svR - svW, axis=1))))
        else:
            max_pose_dev = float("inf")
    ac2 = max_pose_dev < EPS_POSE

    # ---- AC3 遞迴帶動(後代動/祖先旁支不動;weighted-only 全脫鉤;多跳)----
    setupR = {nm: _skin_setup(wslotsR[nm], world0R, bidxR) for nm in wnames}
    setupW = {nm: _skin_setup(wslotsW[nm], world0W, bidxW) for nm in wnames}
    drivers = [f"b_{nm}" for nm in metaR if f"b_{nm}" in bynameR]
    ac3 = True
    wo_decoupled = True       # C2-5a:weighted-only 版一律不動
    drive_detail = {}
    multi_hop_ok = False
    for jb in drivers:
        wR = W.bone_world_transforms(bonesR, bynameR, orderR,
                                     _pose_rotate(bonesR, bynameR, orderR, jb, THETA))
        wW = W.bone_world_transforms(bonesW, bynameW, orderW,
                                     _pose_rotate(bonesW, bynameW, orderW, jb, THETA))
        rows = {}
        for nm in wnames:
            svR0, pvR, _ = setupR[nm]
            rd = float(np.mean(np.linalg.norm(W.skin_vertices(pvR, wR, bidxR) - svR0, axis=1)))
            svW0, pvW, _ = setupW[nm]
            fd = float(np.mean(np.linalg.norm(W.skin_vertices(pvW, wW, bidxW) - svW0, axis=1)))
            is_desc = jb in _ancestors_or_self(f"b_{nm}", pmapR)
            exp_ok = ((rd > ARTIC_MIN) if is_desc else (rd < INERT_MAX))
            ac3 = ac3 and exp_ok and (fd < INERT_MAX)
            wo_decoupled = wo_decoupled and (fd < INERT_MAX)
            rows[nm] = {"is_desc": is_desc, "rig": round(rd, 3), "wo": round(fd, 6), "ok": exp_ok}
        # 多跳:轉 rig 根 b_body → 離 body ≥2 跳的 weighted 件隨動(且 wo 脫鉤)
        if jb == f"b_{body}":
            body_depth = len(_ancestors_or_self(f"b_{body}", pmapR)) - 1
            for nm in wnames:
                hop = (len(_ancestors_or_self(f"b_{nm}", pmapR)) - 1) - body_depth
                if hop >= 2 and rows[nm]["is_desc"]:
                    multi_hop_ok = multi_hop_ok or (rows[nm]["rig"] > ARTIC_MIN and rows[nm]["wo"] < INERT_MAX)
        drive_detail[jb] = rows
    ac3 = ac3 and multi_hop_ok

    # ---- AC4 變形乾淨(關節旋轉逐幀 si/flip)----
    ac4 = True
    deform = {}
    for nm in wnames:
        jb = f"b_{nm}"
        pv, tris, hull, uvs, wt = W.parse_weighted(wslotsR[nm])
        sv0 = W.skin_vertices(pv, world0R, bidxR)
        signs = [W.signed_area(sv0, t) > 0 for t in tris]
        area0 = sum(abs(W.signed_area(sv0, t)) for t in tris)
        worst_si = worst_flip = 0
        for th in (-THETA, -THETA / 2, THETA / 2, THETA):
            for drive in (jb, f"b_{body}"):
                w = W.bone_world_transforms(bonesR, bynameR, orderR,
                                            _pose_rotate(bonesR, bynameR, orderR, drive, th))
                r = W.eval_pose_wm(W.skin_vertices(pv, w, bidxR), tris, signs, area0)
                worst_si = max(worst_si, r["self_intersections"])
                worst_flip = max(worst_flip, r["triangle_flips"])
        kind = metaR.get(nm, {}).get("kind", "structural")
        ok = True if kind == "effect" else (worst_si == 0 and worst_flip == 0)
        deform[nm] = {"kind": kind, "si": worst_si, "flip": worst_flip, "ok": ok}
        ac4 = ac4 and ok

    return {
        "body": body, "wnames": wnames, "chain_depth": max_depth, "non_star": non_star,
        "ctrl_ok": ctrl_ok, "ctrl_detail": ctrl_detail,
        "ac1": ac1, "ac2": ac2, "max_pose_dev": max_pose_dev,
        "ac3": ac3, "multi_hop": multi_hop_ok, "drive_detail": drive_detail,
        "wo_decoupled": wo_decoupled, "ac4": ac4, "deform": deform,
    }


# ---------------------------------------------------------------- C2-5b/c 負對照(非合成鏈)
def _ac_neg_controls(infer_bundle, chain):
    parts, truth, tree_truth, struct, piv, scale = infer_bundle
    # (b) effect 件當結構 → 汙染樹
    _, _, corrupted = R.diagnose_effect_contamination(parts, {HALO})
    # (c) pivot 隨機 / 互換負對照(med err/rig >> TAU)
    rng = np.random.default_rng(20260829)
    allp = np.vstack([struct[c] for c in tree_truth])
    lo, hi = allp.min(0), allp.max(0)
    rand = {c: lo + rng.random(2) * (hi - lo) for c in tree_truth}
    rand_med_rel = float(np.median([np.linalg.norm(rand[c] - truth[c]) / scale for c in tree_truth]))
    keys = list(tree_truth.keys())
    rot = {keys[i]: piv[keys[(i + 1) % len(keys)]] for i in range(len(keys))}
    swap_med_rel = float(np.median([np.linalg.norm(rot[c] - truth[c]) / scale for c in tree_truth]))
    neg_ok = (chain["wo_decoupled"] and corrupted
              and rand_med_rel > TAU and swap_med_rel > TAU)
    detail = {
        "weighted_only_decoupled": chain["wo_decoupled"],
        "effect_contaminates_tree": corrupted,
        "pivot_random_med_over_rig": round(rand_med_rel, 3),
        "pivot_swap_med_over_rig": round(swap_med_rel, 3), "tau": TAU,
    }
    return neg_ok, detail


# ---------------------------------------------------------------- 主流程
def run_all():
    api_ok = all(callable(getattr(R, fn, None)) for fn in (
        "infer_rig_tree", "infer_joint_pivots", "generate_weighted_part",
        "weighted_part_quality", "build_rigged_skeleton", "make_synthetic_limb_chain",
        "award_robot_truth"))

    # C2-1 inference truth(+ bundle 給負對照)
    infer_ok, infer_detail, infer_bundle = _ac_infer_truth()
    c21 = api_ok and infer_ok

    # C2-2 weighted gen truth
    c22, wgen_detail = _ac_weighted_gen()

    # 合成鏈:一次 build,算 AC1..AC4(+ wo 脫鉤)
    tmp = tempfile.mkdtemp(prefix="c2rig_")
    try:
        rw_dir, wo_dir = _build_chain(tmp)
        ch = _chain_eval(rw_dir, wo_dir)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    c23 = ch["ac1"]
    c24 = ch["ac2"] and ch["ac3"] and ch["ac4"]
    c25, neg_detail = _ac_neg_controls(infer_bundle, ch)

    res = {
        "C2-1_infer_truth": (c21, dict(api_callable=api_ok, **infer_detail)),
        "C2-2_weighted_gen_truth": (c22, {"parts": wgen_detail}),
        "C2-3_chain_structure": (c23, {
            "body": (ch["body"] or "").split("/")[-1], "weighted_parts": ch["wnames"],
            "chain_depth": ch["chain_depth"], "non_star": ch["non_star"],
            "control_bones": ch["ctrl_detail"]}),
        "C2-4_recursive_drive": (c24, {
            "setup_max_dev_px": round(ch["max_pose_dev"], 4), "setup_ok": ch["ac2"],
            "recursive_drive_ok": ch["ac3"], "multi_hop_ok": ch["multi_hop"],
            "deform_clean_ok": ch["ac4"], "deform": ch["deform"],
            "drive": {jb: {nm.split("_")[-1]: f"{r['rig']}({'D' if r['is_desc'] else '.'})/wo={r['wo']}"
                           for nm, r in rows.items()} for jb, rows in ch["drive_detail"].items()}}),
        "C2-5_gate_non_vacuous": (c25, neg_detail),
    }
    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "C2 gen_lib.rig: weighted mesh 生成 + rig 自動推斷(結構軸的 rig 分支)",
        "entry": "skills/spine-ai-editor/assets/gen_lib/rig.py :: "
                 "infer_rig_tree / infer_joint_pivots / generate_weighted_part / "
                 "build_rigged_skeleton / make_synthetic_limb_chain / award_robot_truth",
        "metrics": {
            "award_tree_ok": infer_detail["tree_ok"],
            "award_pivot_med_err": infer_detail["pivot_med_err_px"],
            "award_pivot_baseline_err": infer_detail["baseline_med_err_px"],
            "chain_depth": ch["chain_depth"],
            "chain_setup_max_dev": round(ch["max_pose_dev"], 4),
            "chain_multi_hop": ch["multi_hop"],
            "neg_wo_decoupled": neg_detail["weighted_only_decoupled"],
            "neg_pivot_swap_med_over_rig": neg_detail["pivot_swap_med_over_rig"],
        },
        "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="完整 JSON 報告")
    a = ap.parse_args()
    report = run_all()
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2, default=float))
    else:
        print(json.dumps({"overall_pass": report["overall_pass"], "metrics": report["metrics"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2, default=float))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
