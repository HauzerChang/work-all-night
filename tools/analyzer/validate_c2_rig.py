#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C2 閘 — `gen_lib.rig` weighted mesh 生成 + rig 自動推斷(spine-ai-editor 2.0 Phase C2)。

C1 把 repo 的 **unweighted** mesh 生成 + 真實 deform 自交閘抽成 skill 入口;C2 把 repo 的
**weighted mesh 生成**(`generate_weighted_mesh` heat-diffusion/BBW)+ **rig 自動推斷**
(`infer_tree` 肢體父子樹 + `infer_pivots` 關節 pivot)抽成 skill 入口
`skills/spine-ai-editor/assets/gen_lib/rig.py`,成為**結構軸的 rig 分支**:
v1.3.0 只能在既有骨架上疊動畫;C2 讓 2.0 能從**件幾何**自動長出 rig(拓樸 + pivot)並產可平滑彎折的 weighted mesh。

**驗的是什麼(為何這個 chunk 有價值)**:
  「件沒綁骨 / 綁錯父子 / pivot 擺錯關節 / 只能整塊剛體位移(無 weighted mesh 平滑彎折)」
  都是 structural 限制;C2 證經公開 API:
   · 對**合成肢體鏈 fixture**(body→arm→forearm→hand,只有相鄰件接觸)→ `infer_rig` **端到端 recover 成鏈**
     (非強制星形),合成星形亦正確 → 證接觸距離 Dijkstra 樹泛化到多跳。
   · 對 **Award 機器人**(repo 既有藝術家真值)→ 推斷樹 == 真值 ROBOT_TREE、pivot max err/rig < 0.10(draft 級)。
   · **weighted mesh 生成**:對 Award 不透明結構件(身體/左手)生成 heat-diffusion weighted mesh →
     setup 自一致乾淨 + 真實動畫 deform si=0/flip=0 + 頂點預算 ≤ 1.4× 藝術家。
   · 閘**真值校準**:藝術家既有 weighted mesh 在真實動畫全幀 si=0(閘不冤枉好 mesh)。
   · 閘**非恆真**:隨機父指派 ≈0 命中、拆件斷開→父邊改變、隨機/互換 pivot >> 門檻、打亂權重→si>0。

**AC(全部客觀、可機讀;透過 skill 公開 API)**:
  C2-1 entrypoint+schema : `rig.infer_limb_tree`/`infer_joint_pivots`/`infer_rig`/
                           `generate_weighted_part_mesh`/`weighted_deform_gate` 皆 callable;
                           `infer_rig` 對合成鏈產 **schema 合法** rig(root∈parts、無環、每非 root 件有 parent+pivot)。
  C2-2 tree-topology     : (headline)合成鏈 → root=torso 且 recover 成**鏈**(upper→torso、lower→upper,非星形)、
                           鏈深 ≥ 2 跳;合成星形 → 全掛 torso;Award 機器人 → 推斷樹 == 真值 ROBOT_TREE;
                           且 τ_frac band 內 root+tree 穩定(非 knife-edge)。
  C2-3 pivot-accuracy    : Award 機器人 → 每關節 pivot err/rig_scale < 0.10(TAU,draft 級);
                           中位誤差 < 用子件質心當 pivot 的 baseline 中位誤差(接觸縫顯著勝天真)。
  C2-4 weighted-gen      : (a) 生成 weighted mesh(身體/左手)→ setup clean + 真實動畫 si=0/flip=0/degen=0
                           + nv ≤ 1.4× 藝術家;(b) 真值校準:藝術家既有 weighted mesh 真實動畫全幀乾淨。
  C2-5 gates-non-vacuous : (a) tree:隨機父指派命中率 ≈ 0 + 左手平移遠離 → 父邊改變(幾何驅動,非硬編);
                           (b) pivot:隨機 pivot 與關節互換 median err/rig 皆 >> 0.10;
                           (c) weighted:打亂權重在放大動作下 si > 0(閘抓得到壞綁定)。

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

import rig as R                      # noqa: E402  C2 skill 入口(gen_lib);Award 真值經其 award_robot_struct_parts 取用

TAU = 0.10                           # pivot 準度門檻(rig_scale 分數)
NV_MULT = 1.4                        # weighted mesh 頂點預算倍數
OPAQUE = ["機器人拆件/身體", "機器人拆件/左手"]   # 不透明結構件:硬性 si=0


def _p(rel):
    return os.path.join(_REPO, rel)


def _rig_scale(parts, tree):
    """正規化基準 = 父件(軀幹)bounding box 對角線均值。"""
    parents = {tree[c] for c in tree if tree[c] in parts}
    diags = [float(np.hypot(*(parts[p].max(0) - parts[p].min(0)))) for p in parents]
    return float(np.mean(diags)) if diags else 1.0


def run_all():
    award = _p("assets/Award.json")

    # ---- C2-1 entrypoint + schema ----
    api_ok = all(callable(getattr(R, fn, None)) for fn in
                 ("infer_limb_tree", "infer_joint_pivots", "infer_rig",
                  "generate_weighted_part_mesh", "weighted_deform_gate",
                  "eval_generated_weighted", "rig_is_schema_valid"))
    chain = R.synthetic_limb_chain()
    rig_chain = R.infer_rig(chain, tau_frac=0.30)
    schema_ok, schema_probs = R.rig_is_schema_valid(rig_chain, chain)
    c21 = api_ok and schema_ok

    # ---- C2-2 tree topology(headline)----
    chain_is_chain = (rig_chain["root"] == "torso"
                      and rig_chain["tree"].get("upper") == "torso"
                      and rig_chain["tree"].get("lower") == "upper")
    # 鏈深:lower 沿 parent 到 root 的跳數
    def _depth(nm, tree, root):
        d, cur = 0, nm
        while cur != root and cur in tree and d <= len(tree) + 1:
            cur = tree[cur]; d += 1
        return d
    chain_depth = _depth("lower", rig_chain["tree"], rig_chain["root"])
    star = R.synthetic_star()
    rig_star = R.infer_rig(star, tau_frac=0.30)
    star_ok = (rig_star["root"] == "torso"
               and all(rig_star["tree"].get(k) == "torso" for k in ("a", "b", "c")))
    # Award 真值樹
    struct, truth, tree_truth = R.award_robot_struct_parts()
    rig_award = R.infer_rig(struct)
    award_tree_ok = (rig_award["tree"] == tree_truth)
    # τ_frac band 穩定(非 knife-edge 調參):整段 band 內 root+tree 皆不變
    band = [0.008, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.20]
    band_stable = True
    body_root = rig_award["root"]
    for tf in band:
        r2, t2, _ = R.infer_limb_tree(struct, tau_frac=tf)
        if not (r2 == body_root and t2 == tree_truth):
            band_stable = False
    c22 = (chain_is_chain and chain_depth >= 2 and star_ok and award_tree_ok and band_stable)

    # ---- C2-3 pivot accuracy(truth-calibrated)----
    scale = _rig_scale(struct, tree_truth)
    piv = rig_award["pivots"]
    err = {c: float(np.linalg.norm(piv[c] - truth[c])) for c in tree_truth if c in piv}
    rel = {c: err[c] / scale for c in err}
    max_rel = max(rel.values())
    med_err = float(np.median(list(err.values())))
    base = R.centroid_pivot_baseline(struct, tree_truth)
    berr = {c: float(np.linalg.norm(base[c] - truth[c])) for c in tree_truth if c in base}
    med_base = float(np.median(list(berr.values())))
    c23 = (max_rel < TAU) and (med_err < med_base)

    # ---- C2-4 weighted mesh gen(truth + clean + budget)----
    gen_parts = {}
    gen_ok = True
    for slot in OPAQUE:
        gen = R.generate_weighted_part_mesh(award, slot, max_area=1500.0)
        ev = R.eval_generated_weighted(gen)
        art = R.weighted_deform_gate(award, slot)           # 藝術家既有 mesh(真值校準)
        setup_clean = bool(ev["setup"]["clean"])
        deform_clean = (ev["worst"]["self_intersections"] == 0
                        and ev["worst"]["triangle_flips"] == 0
                        and ev["worst"]["degenerate"] == 0)
        budget_ok = ev["nv"] <= art["nv"] * NV_MULT
        artist_clean = (art["worst"]["self_intersections"] == 0
                        and art["worst"]["triangle_flips"] == 0
                        and art["worst"]["degenerate"] == 0)
        ok = setup_clean and deform_clean and budget_ok and artist_clean
        gen_ok = gen_ok and ok
        gen_parts[slot] = {"gen_nv": ev["nv"], "artist_nv": art["nv"],
                           "gen_worst": ev["worst"], "artist_worst": art["worst"],
                           "setup_clean": setup_clean, "deform_clean": deform_clean,
                           "budget_ok": budget_ok, "artist_clean": artist_clean, "pass": ok}
    c24 = gen_ok

    # ---- C2-5 gates non-vacuous(negative controls)----
    # (a) tree: 隨機父指派命中率 ≈ 0
    rng = np.random.default_rng(0)
    children = list(tree_truth.keys())
    body = list(tree_truth.values())[0]          # 真值樹所有子件都掛 body(= rig 根)
    cand = children + [body]
    hits, N = 0, 20000
    for _ in range(N):
        rt = {c: cand[rng.integers(len(cand))] for c in children}
        rt = {c: p for c, p in rt.items() if p != c}
        if rt == tree_truth:
            hits += 1
    rand_tree_rate = hits / N
    nc_tree_rand = rand_tree_rate < 0.05
    # (a2) 左手平移遠離 1500px → 父邊改變
    lh = "機器人拆件/左手"
    struct2 = {k: (v + np.array([1500.0, 0.0]) if k == lh else v) for k, v in struct.items()}
    _, t3, _ = R.infer_limb_tree(struct2)
    nc_tree_disconnect = (t3.get(lh) != body)
    # (b) pivot: 隨機 + 互換 median err/rig 皆 >> TAU
    allp = np.vstack([struct[c] for c in tree_truth])
    lo, hi = allp.min(0), allp.max(0)
    rand_piv = {c: lo + rng.random(2) * (hi - lo) for c in tree_truth}
    rand_med = float(np.median([np.linalg.norm(rand_piv[c] - truth[c]) / scale for c in tree_truth]))
    keys = list(tree_truth.keys())
    swap = {keys[i]: piv[keys[(i + 1) % len(keys)]] for i in range(len(keys))}
    swap_med = float(np.median([np.linalg.norm(swap[c] - truth[c]) / scale for c in tree_truth]))
    nc_pivot = (rand_med > TAU) and (swap_med > TAU)
    # (c) weighted: 打亂權重 → 放大動作 si > 0
    scramble = R.mutate_scramble_weights()
    bad = R.weighted_deform_gate(award, "機器人拆件/身體", mutate=scramble, amplify=4.0)
    good = R.weighted_deform_gate(award, "機器人拆件/身體", amplify=4.0)
    nc_weighted = (bad["worst"]["self_intersections"] > 0
                   and good["worst"]["self_intersections"] == 0)
    c25 = nc_tree_rand and nc_tree_disconnect and nc_pivot and nc_weighted

    res = {
        "C2-1_entrypoint_schema": (c21, {
            "api_callable": api_ok, "chain_schema_ok": schema_ok,
            "chain_schema_problems": schema_probs,
            "chain_root": rig_chain["root"], "chain_tree": rig_chain["tree"]}),
        "C2-2_tree_topology": (c22, {
            "chain_recovered_chain_not_star": chain_is_chain, "chain_depth": chain_depth,
            "chain_tree": rig_chain["tree"], "star_ok": star_ok, "star_tree": rig_star["tree"],
            "award_tree": {c.split("/")[-1]: p.split("/")[-1] for c, p in rig_award["tree"].items()},
            "award_tree_truth_match": award_tree_ok,
            "tau_band_stable": band_stable}),
        "C2-3_pivot_accuracy": (c23, {
            "rig_scale_px": round(scale, 1), "TAU": TAU,
            "err_rel": {c.split("/")[-1]: round(rel[c], 4) for c in rel},
            "max_rel": round(max_rel, 4), "med_err_px": round(med_err, 2),
            "centroid_baseline_med_px": round(med_base, 2)}),
        "C2-4_weighted_gen": (c24, {
            slot.split("/")[-1]: v for slot, v in gen_parts.items()}),
        "C2-5_gates_non_vacuous": (c25, {
            "tree_rand_hit_rate": rand_tree_rate, "tree_rand_ok": nc_tree_rand,
            "tree_disconnect_parent": (t3.get(lh) or "(none)").split("/")[-1],
            "tree_disconnect_changed": nc_tree_disconnect,
            "pivot_rand_med_rel": round(rand_med, 3), "pivot_swap_med_rel": round(swap_med, 3),
            "pivot_ok": nc_pivot,
            "weighted_scramble_si": bad["worst"]["self_intersections"],
            "weighted_artist_si": good["worst"]["self_intersections"],
            "weighted_ok": nc_weighted}),
    }
    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "C2 gen_lib.rig: 件幾何 → rig 自動推斷(tree+pivot)+ weighted mesh 生成(結構軸的 rig 分支)",
        "entry": "skills/spine-ai-editor/assets/gen_lib/rig.py :: "
                 "infer_limb_tree / infer_joint_pivots / infer_rig / generate_weighted_part_mesh / weighted_deform_gate",
        "metrics": {
            "chain_tree": rig_chain["tree"], "chain_depth": chain_depth,
            "award_tree_match_truth": award_tree_ok,
            "pivot_max_rel": round(max_rel, 4), "pivot_med_err_px": round(med_err, 2),
            "weighted_gen_nv": {s.split("/")[-1]: v["gen_nv"] for s, v in gen_parts.items()},
            "neg_tree_rand_hit_rate": rand_tree_rate,
            "neg_pivot_rand_med_rel": round(rand_med, 3),
            "neg_weighted_scramble_si": bad["worst"]["self_intersections"],
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
