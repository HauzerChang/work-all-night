#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C2 閘 — `gen_lib.rig` weighted mesh 生成 + rig 自動推斷(spine-ai-editor 2.0 Phase C2)。

B2/B3/B4 把 repo 的**動畫生成**抽成 skill 入口;C1 把 repo 的 **mesh 生成 + 變形自交閘**抽成入口;
C2 把 repo 的 **weighted mesh 生成器**(`generate_weighted_mesh`,heat-diffusion/BBW 近似權重)
與 **rig 自動化**(`infer_tree` 肢體樹 + `infer_pivots` 接觸縫關節 pivot)抽成 skill 入口
`skills/spine-ai-editor/assets/gen_lib/rig.py`,成為**結構軸的 rig 分支**:
v1.3.0 只能**檢查**既有 rig/weighted mesh 且**假設星形**,C2 讓 2.0 能**自動推斷**拓樸 + 關節 pivot
(支援多跳肢體鏈)並**生成**骨綁 weighted mesh,使件「會彎折、隨骨鏈遞迴帶動」。

**驗的是什麼(為何這個 chunk 有價值)**:
  「件只能整塊剛體位移、無法彎折」+「rig 只能手動/假設星形」是 structural 限制;C2 證經公開 API:
   · 對 **mesh 件**(Award 身體)生成 weighted mesh → heat-diffusion 權重**天然 partition of unity**
     (每頂點權重和=1,worst|Σw-1|≈2e-16)、至多 4 骨 → 真實動畫變形 **si=0 / flip=0**(與藝術家真值一致)。
   · 對**件世界多邊形集合**自動推 **運動學樹**(合成多跳肢體鏈 recover 成鏈、**非星形**;Award robot
     recover 星形真值)+ **接觸縫關節 pivot**(對藝術家 rig 真值 err/rig < 0.1,顯著贏過質心 baseline)。
   · **端到端**(headline):合成肢體鏈 → `build_spine --rig --weighted` → 轉任一關節,**後代 weighted
     件遞迴帶動、祖先/旁支不動**(多跳),weighted-only 版全脫鉤(負對照),逐幀 si=0。
   · 閘**非恆真**:質心/隨機 pivot baseline 爆閘(err/rig >> 0.1);打亂權重綁定在放大動作下 si>0。

**AC(全部客觀、可機讀)**:
  C2-1 entrypoint+weighted-schema : `rig.{infer_limb_tree,infer_joint_pivots,generate_weighted_part_mesh,
                                    weighted_mesh_is_schema_valid,pv_to_spine_vertices,gate_limb_chain}` 皆可呼叫;
                                    `generate_weighted_part_mesh(Award,身體)`→ weighted mesh schema 合法
                                    (每頂點 1..4 骨、partition of unity worst|Σw-1|<1e-4)、nv≥artist、setup clean;
                                    `pv_to_spine_vertices` 攤平長度自洽(Σ(1+4·骨數))。
  C2-2 rig-inference-truth        : (a) 合成多跳肢體鏈 `infer_limb_tree` → root=body、tree recover **鏈**
                                    (forearm 父=arm 非 body → **非星形**);(b) Award robot `infer_limb_tree`
                                    root=身體、tree==ROBOT_TREE(星形真值);`infer_joint_pivots` max err/rig<0.1
                                    且中位顯著贏過質心 baseline。
  C2-3 end-to-end-chain (headline): `rig.gate_limb_chain()` overall PASS:ac1 鏈結構(非星形、控制骨掛關節骨、
                                    鏈深≥3)+ ac2 setup 不位移 + ac3 遞迴帶動(多跳、weighted-only 脫鉤)+ ac3r region 葉件隨鏈。
  C2-4 weighted-deform-clean+calib: (a) 生成 Award 身體 weighted mesh 真實動畫變形 worst si/flip/degen=0、
                                    checker_validated=True;(b) **真值校準**:藝術家 weighted mesh(身體+左手)
                                    於真實動畫亦乾淨(checker_validated=True)→ 閘不冤枉好 mesh;(c) 鏈 weighted 件變形乾淨(= ac4)。
  C2-5 gate-non-vacuous           : (a) **pivot 鑑別力**:質心 baseline 與隨機指派 pivot 中位 err/rig >> 0.1
                                    (接觸縫 < 0.1);(b) **weighted 鑑別力**:身體放大 4× 動作下藝術家 si=0、打亂
                                    權重 si>0,且左手打亂權重直接被抓;(c) **weighted-only 脫鉤**:鏈 rig=False
                                    時 weighted 件不隨關節動(負對照,含於 ac3)。

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

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILL_ASSETS = os.path.join(_REPO, "skills", "spine-ai-editor", "assets")
sys.path.insert(0, os.path.join(_SKILL_ASSETS, "gen_lib"))
sys.path.insert(0, os.path.join(_REPO, "tools", "mesh_gen"))
sys.path.insert(0, os.path.join(_REPO, "tools", "rig"))

import rig as R                          # noqa: E402  C2 skill 入口(gen_lib)
import weighted_deform_eval as W         # noqa: E402  真值校準 + 負對照
import make_limb_chain_psd as MK         # noqa: E402  合成肢體鏈 fixture(件 rects)
import infer_pivots as IP                # noqa: E402  ROBOT_TREE 真值


def _p(rel):
    return os.path.join(_REPO, rel)


_AWARD = _p("assets/Award.json")
_ROBOT_BODY = "機器人拆件/身體"
_ROBOT_HAND = "機器人拆件/左手"


def _chain_parts():
    """合成肢體鏈 fixture 的件世界多邊形(由 PSD 件 rects 直接取,image 座標即 adjacency 世界)。"""
    parts = {}
    for (name, l, t, w, h, _rgb) in MK.PARTS:
        parts[name] = np.array([[l, t], [l + w, t], [l + w, t + h], [l, t + h]], dtype=float)
    return parts


def _pivot_errs(parts, truth, tree, pivots, scale):
    return {c: float(np.linalg.norm(pivots[c] - truth[c])) / scale for c in tree if c in pivots}


def run_all():
    # ================= C2-1 entrypoint + weighted schema =================
    api_fns = ("infer_limb_tree", "infer_joint_pivots", "generate_weighted_part_mesh",
               "weighted_mesh_is_schema_valid", "pv_to_spine_vertices", "load_robot_rig_truth",
               "gate_limb_chain")
    api_ok = all(callable(getattr(R, fn, None)) for fn in api_fns)
    wm = R.generate_weighted_part_mesh(_AWARD, _ROBOT_BODY)          # 公開 API
    schema_ok = wm["schema"]["pass"]
    pou_ok = wm["worst_weight_sum_dev"] < 1e-4                        # partition of unity
    topk_ok = wm["max_bones_per_vertex"] <= 4
    nv_ok = wm["nv"] >= wm["artist_nv"]
    setup_ok = wm["deform"]["setup_clean"]
    # pv_to_spine_vertices 長度自洽:Σ(1 + 4·骨數)
    spine_v = R.pv_to_spine_vertices(wm["pv"])
    exp_len = sum(1 + 4 * len(en) for en in wm["pv"])
    sv_ok = (len(spine_v) == exp_len)
    c21 = api_ok and schema_ok and pou_ok and topk_ok and nv_ok and setup_ok and sv_ok

    # ================= C2-2 rig 自動推斷(對真值)=================
    # (a) 合成多跳肢體鏈 → recover 鏈(非星形)
    cparts = _chain_parts()
    croot, ctree, cinfo = R.infer_limb_tree(cparts)
    chain_root_ok = (croot == "char/body")
    # 非星形:forearm 的父是 arm(非 body),hand 的父是 forearm
    non_star = (ctree.get("char/forearm") == "char/arm"
                and ctree.get("char/hand") == "char/forearm"
                and ctree.get("char/arm") == "char/body")
    c22a = chain_root_ok and non_star
    # (b) Award robot → 星形真值 + 接觸縫 pivot err/rig<0.1 且贏質心 baseline
    parts, truth, tree, fid = R.load_robot_rig_truth()
    struct = {k: v for k, v in parts.items() if "光暈" not in k}
    rroot, rtree, rinfo = R.infer_limb_tree(struct)
    scale = rinfo["scale"]
    robot_tree_ok = (rroot == _ROBOT_BODY
                     and {c: p for c, p in rtree.items()} == dict(IP.ROBOT_TREE))
    seam = R.infer_joint_pivots(struct, tree)
    base = R.centroid_pivot_baseline(struct, tree)
    seam_errs = _pivot_errs(struct, truth, tree, seam, scale)
    base_errs = _pivot_errs(struct, truth, tree, base, scale)
    seam_max = max(seam_errs.values())
    seam_med = float(np.median(list(seam_errs.values())))
    base_med = float(np.median(list(base_errs.values())))
    c22b = robot_tree_ok and (seam_max < 0.1) and (seam_med < base_med)
    c22 = c22a and c22b

    # ================= C2-3 端到端合成肢體鏈(headline)=================
    chain = R.gate_limb_chain()
    c23 = bool(chain["overall"] and chain["ac1"] and chain["ac2"] and chain["ac3"]
               and chain["ac3r"] and chain["chain_depth"] >= 3 and chain["multi_hop"])

    # ================= C2-4 weighted deform clean + 真值校準 =================
    gen_worst = wm["deform"]["worst"]
    gen_clean = (gen_worst["self_intersections"] == 0 and gen_worst["triangle_flips"] == 0
                 and gen_worst["degenerate"] == 0 and wm["deform"]["checker_validated"])
    # 真值校準:藝術家 weighted mesh 於真實動畫亦乾淨(閘不誤報)
    art_body = W.evaluate_weighted_mesh(_AWARD, _ROBOT_BODY)
    art_hand = W.evaluate_weighted_mesh(_AWARD, _ROBOT_HAND)
    art_clean = (art_body["checker_validated"] and art_hand["checker_validated"])
    chain_deform_ok = bool(chain["ac4"])
    c24 = gen_clean and art_clean and chain_deform_ok

    # ================= C2-5 gate non-vacuous(負對照)=================
    # (a) pivot 鑑別力:隨機 pivot(全 rig bbox)+ 關節互換(輪轉指派)兩者中位 err/rig >> 0.1
    #     (接觸縫 < 0.1);鏡像 repo validate_pivots AC3(質心 baseline 只作 C2-2 的「贏過」對照)。
    rng = np.random.default_rng(0)
    allp = np.vstack([struct[c] for c in tree])
    lo, hi = allp.min(0), allp.max(0)
    rand = {c: lo + rng.random(2) * (hi - lo) for c in tree}
    rand_errs = [float(np.linalg.norm(rand[c] - truth[c])) / scale for c in tree]
    keys = list(tree.keys())
    swap = {keys[i]: seam[keys[(i + 1) % len(keys)]] for i in range(len(keys))}
    swap_errs = [float(np.linalg.norm(swap[c] - truth[c])) / scale for c in tree]
    rand_med = float(np.median(rand_errs))
    swap_med = float(np.median(swap_errs))
    pivot_disc = (rand_med > 0.1) and (swap_med > 0.1) and (seam_med < 0.1)
    # (b) weighted 鑑別力:身體放大 4× 藝術家 si=0 vs 打亂權重 si>0 + 左手打亂直接被抓
    amp = 4.0
    art_amp = W.evaluate_weighted_mesh(_AWARD, _ROBOT_BODY, amplify=amp)
    bad_amp = W.evaluate_weighted_mesh(_AWARD, _ROBOT_BODY, mutate=W.mutate_scramble_weights, amplify=amp)
    body_disc = (art_amp["worst"]["self_intersections"] == 0
                 and bad_amp["worst"]["self_intersections"] > 0)
    hand_bad = W.evaluate_weighted_mesh(_AWARD, _ROBOT_HAND, mutate=W.mutate_scramble_weights)
    hand_disc = not (hand_bad["worst"]["self_intersections"] == 0
                     and hand_bad["worst"]["triangle_flips"] == 0)
    weighted_disc = body_disc and hand_disc
    # (c) weighted-only 脫鉤:鏈 ac3 內已含(rig=False 時 weighted 件不隨關節動)→ ac3 PASS 即證
    decouple_ok = bool(chain["ac3"])
    c25 = pivot_disc and weighted_disc and decouple_ok

    res = {
        "C2-1_entrypoint_weighted_schema": (c21, {
            "api_callable": api_ok, "schema_ok": schema_ok,
            "worst_weight_sum_dev": wm["worst_weight_sum_dev"],
            "max_bones_per_vertex": wm["max_bones_per_vertex"],
            "nv": wm["nv"], "artist_nv": wm["artist_nv"], "setup_clean": setup_ok,
            "spine_vertices_len": len(spine_v), "spine_vertices_len_ok": sv_ok,
            "schema_problems": wm["schema"]["problems"]}),
        "C2-2_rig_inference_truth": (c22, {
            "chain_root": croot, "chain_tree": ctree, "chain_non_star": non_star,
            "robot_root": rroot, "robot_tree_ok": robot_tree_ok,
            "seam_err_over_rig": {c: round(v, 4) for c, v in seam_errs.items()},
            "seam_max": round(seam_max, 4), "seam_median": round(seam_med, 4),
            "centroid_baseline_median": round(base_med, 4), "rig_scale": round(scale, 1)}),
        "C2-3_end_to_end_chain": (c23, {
            "overall": chain["overall"], "ac1_structure": chain["ac1"],
            "ac2_setup": chain["ac2"], "ac3_articulation": chain["ac3"],
            "ac3r_region_leaf": chain["ac3r"], "ac4_deform": chain["ac4"],
            "chain_depth": chain["chain_depth"], "multi_hop": chain["multi_hop"],
            "weighted_parts": chain["weighted"]}),
        "C2-4_weighted_deform_clean_calib": (c24, {
            "generated_body_worst": gen_worst, "generated_checker_validated": wm["deform"]["checker_validated"],
            "artist_body_validated": art_body["checker_validated"],
            "artist_hand_validated": art_hand["checker_validated"],
            "chain_deform_clean": chain_deform_ok}),
        "C2-5_gate_non_vacuous": (c25, {
            "pivot_random_median": round(rand_med, 4),
            "pivot_swap_median": round(swap_med, 4),
            "pivot_centroid_baseline_median": round(base_med, 4),
            "pivot_seam_median": round(seam_med, 4), "pivot_disc": pivot_disc,
            "body_amp4_artist_si": art_amp["worst"]["self_intersections"],
            "body_amp4_scrambled_si": bad_amp["worst"]["self_intersections"],
            "hand_scramble_worst": hand_bad["worst"], "weighted_disc": weighted_disc,
            "weighted_only_decoupled": decouple_ok}),
    }
    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "C2 gen_lib.rig: weighted mesh 生成(BBW/heat)+ rig 自動推斷(樹+接觸縫 pivot)"
                 "+ 端到端多跳肢體鏈(結構軸的 rig 分支)",
        "entry": "skills/spine-ai-editor/assets/gen_lib/rig.py :: "
                 "infer_limb_tree / infer_joint_pivots / generate_weighted_part_mesh / gate_limb_chain",
        "metrics": {
            "weighted_body_nv": wm["nv"], "weighted_worst_wsum_dev": wm["worst_weight_sum_dev"],
            "weighted_max_bones": wm["max_bones_per_vertex"],
            "pivot_seam_median_over_rig": round(seam_med, 4),
            "pivot_centroid_median_over_rig": round(base_med, 4),
            "chain_depth": chain["chain_depth"], "chain_multi_hop": chain["multi_hop"],
            "neg_body_amp4_scrambled_si": bad_amp["worst"]["self_intersections"],
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
