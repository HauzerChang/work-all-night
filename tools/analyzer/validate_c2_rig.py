#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""MERGE_PLAN Phase C2 閘 —— **weighted mesh 生成 + rig 自動推斷**(經公開 skill API)。

承 C1(unweighted mesh 生成 + 變形自交閘)。C2 的 skill 入口 `gen_lib/rig.py` 把 repo 三個
確定性、純 CPU 生成/推斷器包成一條流程:weighted mesh 生成(heat-diffusion/BBW 近似)、
關節 pivot 推斷(父子接觸縫)、肢體父子樹推斷(接觸距離 Dijkstra)。本閘**經公開 API**
驗這三者,移植 repo 既有 5AC(`validate_weighted_gen` / `validate_pivots` / `validate_tree`),
並加真值校準(Award 藝術家 mesh/rig)+ 負對照(閘非恆真)。

AC(全經 `gen_lib.rig` 公開入口,真值 = Award 藝術家 rig + 合成鏈/星形 fixture):
  C2-1 weighted 生成 + schema + 預算
       公開 API 對 Award 不透明結構件(身體/左手)產 Spine **weighted** mesh:
       schema 合法(weighted 格式、每頂點 partition of unity 權重和=1、≤4 骨、hull∈(0,nv])+
       頂點 ≤ 1.4× 藝術家;軟性加成件(光暈)schema 亦合法。
  C2-2 weighted 真實變形 si=0(headline)+ 真值校準
       生成 weighted mesh 放回**真實動畫** skinning 變形 → setup 乾淨 + 逐幀 si=0/flip=0 +
       平滑度不劣於藝術家+裕度;真值校準:藝術家同件 mesh 經同一 checker 亦 si=0
       (checker_validated)→ 生成過閘與真值一致(非閘太鬆、非假性過)。
  C2-3 pivot 推斷準度 + 勝 baseline + 輸入保真依賴
       infer_joint_pivots 對 Award rig → max err/rig < TAU(0.10,draft 級);中位誤差勝
       「子件質心」天真 baseline;用粗略 rect 代理(--no-alpha)max err/rig 爆掉(> TAU)
       → 佐證 pivot 品質取決於件輪廓保真(PSD-first 論點在 rig 階段再現)。
  C2-4 tree 推斷真值 + 門檻穩定 + 多跳通用
       infer_limb_tree 對 Award → root==身體 且 拓樸樹 == 真值 ROBOT_TREE;root+tree 在一段
       τ_frac band 內不變;合成鏈 torso→upper→lower recover 成鏈(非星形)、合成星形 recover 成星形
       → 證 Dijkstra 接觸樹泛化多跳。
  C2-5 閘非恆真(三能力各一負對照)
       (a) pivot:隨機 pivot 與 關節互換 中位 err/rig 皆 >> TAU;
       (b) tree:隨機父指派命中率 ≈ 0 + 天真把 effect 件(光暈)當結構 → 汙染樹(須角色輸入);
       (c) weighted mesh:生成 mesh 對調兩非相鄰 hull 頂點造 tangle → 真實變形閘 setup si>0 抓到。

真相來源:Spine 3.8 bone world transform / skinning(weighted_deform_eval,對 Award 真值重現)+
Award 藝術家親手放的 pivot/權重 + 合成 fixture。純 CPU、無瀏覽器。
一鍵:`python3 tools/analyzer/validate_c2_rig.py`(exit 0 = 全 PASS)。
"""
import sys, os, copy, argparse
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
# 公開 skill 入口(C2 驗的對象)
sys.path.insert(0, os.path.join(HERE, "..", "..", "skills", "spine-ai-editor", "assets"))
from gen_lib import rig  # noqa: E402
# 負對照用的 mutate(weight 擾動庫;hull-tangle 在本檔定義)
sys.path.insert(0, os.path.join(HERE, "..", "mesh_gen"))

TAU = 0.10           # pivot 準度門檻(rig_scale 分數)
NV_MULT = 1.4        # 頂點預算
CV_MARGIN = 0.02
AR_STD_MARGIN = 0.03
HALO = "機器人拆件/光暈"
SEED = 20261017

OPAQUE = [("機器人拆件/身體", 1500), ("機器人拆件/左手", 1400)]


def _rig_scale(parts, tree):
    """正規化基準 = 父件(軀幹)bounding box 對角線平均。"""
    parents = {tree[c] for c in tree if tree[c] in parts}
    diags = [float(np.hypot(*(parts[p].max(0) - parts[p].min(0)))) for p in parents]
    return float(np.mean(diags)) if diags else 1.0


def _hull_tangle(gen):
    """負對照 mutate:對調兩非相鄰 hull 頂點的 weighted bind → 邊界交叉(setup si>0)。"""
    hull = gen["att"]["hull"]

    def mut(pv, bidx):
        pv = copy.deepcopy(pv)
        i, j = 0, hull // 2
        pv[i], pv[j] = pv[j], pv[i]
        return pv
    return mut


def evaluate(verbose=True):
    import weighted_deform_eval as W  # noqa: E402

    def say(*a):
        if verbose:
            print(*a)

    # ================= C2-1 weighted 生成 + schema + 預算 =================
    weighted_reps = {}
    c21 = True
    for slot, ma in OPAQUE:
        rep = rig.generate_and_gate_weighted("assets/Award.json", slot, max_area=ma, kind="opaque")
        weighted_reps[slot] = rep
        c21 = c21 and rep["schema"]["pass"] and rep["budget"]["pass"]
    soft = rig.generate_and_gate_weighted("assets/Award.json", HALO, max_area=1500, kind="soft")
    c21 = c21 and soft["schema"]["pass"]

    say("C2-1 weighted 生成 + schema + 預算")
    for slot, ma in OPAQUE:
        r = weighted_reps[slot]
        say("     {:<6} nv={} (藝術家 {}, ≤{}×={}) schema={} budget={}".format(
            slot.split("/")[-1], r["budget"]["gen_nv"], r["budget"]["artist_nv"], NV_MULT,
            r["budget"]["pass"], r["schema"]["pass"], r["budget"]["pass"]))
    say("     光暈(soft) schema={} (si 不列硬閘)".format(soft["schema"]["pass"]))
    say("     -> {}".format("PASS" if c21 else "FAIL"))

    # ================= C2-2 weighted 真實變形 si=0 + 真值校準 =================
    c22 = True
    say("C2-2 weighted 真實變形 si=0(headline)+ 真值校準")
    for slot, ma in OPAQUE:
        r = weighted_reps[slot]
        art = rig.artist_weighted_gate("assets/Award.json", slot)
        gen_clean = r["deform_gate"]["clean"]
        checker_ok = r["deform_gate"]["checker_validated"]
        artist_clean = (art["worst"]["self_intersections"] == 0 and art["worst"]["triangle_flips"] == 0)
        sm_ok = r["smoothness"]["pass"]
        ok = gen_clean and checker_ok and artist_clean and sm_ok
        c22 = c22 and ok
        say("     {:<6} gen si={}/flip={} clean={} | checker_validated={} | 藝術家 si={} clean={} | smooth={} -> {}".format(
            slot.split("/")[-1], r["deform_gate"]["self_intersections"], r["deform_gate"]["triangle_flips"],
            gen_clean, checker_ok, art["worst"]["self_intersections"], artist_clean, sm_ok,
            "PASS" if ok else "FAIL"))
    say("     -> {}".format("PASS" if c22 else "FAIL"))

    # ================= C2-3 pivot 準度 + 勝 baseline + 保真依賴 =================
    parts_a, truth, tree, fid = rig.load_award_robot_parts(use_alpha=True)
    struct_a = {k: v for k, v in parts_a.items() if k != HALO}
    scale = _rig_scale(struct_a, tree)
    piv = rig.infer_joint_pivots(struct_a, tree)
    err = {c: float(np.linalg.norm(piv[c] - truth[c])) for c in tree if c in piv}
    rel = {c: err[c] / scale for c in err}
    max_rel = max(rel.values())
    base = rig.centroid_pivot_baseline(struct_a, tree)
    berr = {c: float(np.linalg.norm(np.asarray(base[c]) - truth[c])) for c in tree if c in base}
    med_err = float(np.median(list(err.values())))
    med_base = float(np.median(list(berr.values())))
    # rect 代理(--no-alpha)應爆
    parts_r, _, tree_r, fid_r = rig.load_award_robot_parts(use_alpha=False)
    struct_r = {k: v for k, v in parts_r.items() if k != HALO}
    scale_r = _rig_scale(struct_r, tree_r)
    piv_r = rig.infer_joint_pivots(struct_r, tree_r)
    rect_max_rel = max(float(np.linalg.norm(piv_r[c] - truth[c])) / scale_r
                       for c in tree_r if c in piv_r)
    c23 = (max_rel < TAU) and (med_err < med_base) and (rect_max_rel > TAU)
    say("C2-3 pivot 準度 + 勝 baseline + 輸入保真依賴")
    say("     max err/rig(alpha)={:.3f} (<{}) | 中位 {:.1f}px < baseline {:.1f}px | rect 代理 max/rig={:.3f} (>{} 爆) -> {}".format(
        max_rel, TAU, med_err, med_base, rect_max_rel, TAU, "PASS" if c23 else "FAIL"))

    # ================= C2-4 tree 真值 + 門檻穩定 + 多跳通用 =================
    truth_tree = rig.award_robot_tree()
    root, inf_tree, info = rig.infer_limb_tree(struct_a)
    award_ok = (root == "機器人拆件/身體") and (inf_tree == truth_tree)
    band = [0.008, 0.01, 0.02, 0.03, 0.05, 0.08, 0.12, 0.20]
    stable = True
    for tf in band:
        r2, t2, _ = rig.infer_limb_tree(struct_a, tau_frac=tf)
        if not (r2 == "機器人拆件/身體" and t2 == truth_tree):
            stable = False
    rc, tc, _ = rig.infer_limb_tree(rig.make_chain_parts(), tau_frac=0.30)
    chain_ok = (rc == "torso" and tc.get("upper") == "torso" and tc.get("lower") == "upper")
    rs, ts, _ = rig.infer_limb_tree(rig.make_star_parts(), tau_frac=0.30)
    star_ok = (rs == "torso" and all(ts.get(k) == "torso" for k in ("a", "b", "c")))
    c24 = award_ok and stable and chain_ok and star_ok
    say("C2-4 tree 真值 + 門檻穩定 + 多跳通用")
    say("     Award root={} tree==真值={} | τ_frac band 穩定={} | 合成鏈 recover 鏈={} | 合成星形={} -> {}".format(
        root.split("/")[-1], inf_tree == truth_tree, stable, chain_ok, star_ok,
        "PASS" if c24 else "FAIL"))

    # ================= C2-5 閘非恆真(三能力各一負對照)=================
    # (a) pivot:隨機 + 關節互換
    rng = np.random.default_rng(SEED)
    allp = np.vstack([struct_a[c] for c in tree])
    lo, hi = allp.min(0), allp.max(0)
    rand = {c: lo + rng.random(2) * (hi - lo) for c in tree}
    rand_med_rel = float(np.median([np.linalg.norm(rand[c] - truth[c]) / scale for c in tree]))
    keys = list(tree.keys())
    swap = {keys[i]: piv[keys[(i + 1) % len(keys)]] for i in range(len(keys))}
    swap_med_rel = float(np.median([np.linalg.norm(swap[c] - truth[c]) / scale for c in tree]))
    nc_pivot = (rand_med_rel > TAU) and (swap_med_rel > TAU)
    # (b) tree:隨機父指派命中率 ≈ 0 + 納 effect 汙染
    kids = list(truth_tree)
    cand = kids + ["機器人拆件/身體"]
    hits, N = 0, 20000
    for _ in range(N):
        rt = {c: cand[rng.integers(len(cand))] for c in kids}
        rt = {c: p for c, p in rt.items() if p != c}
        if rt == truth_tree:
            hits += 1
    rand_tree_hit = hits / N
    bad = rig.rig_from_parts(parts_a, effect_names=set())        # 不排除光暈 → 汙染
    corrupt = (bad["root"] == HALO) or any(c == HALO or p == HALO for c, p in bad["tree"].items())
    nc_tree = (rand_tree_hit < 0.05) and corrupt
    # (c) weighted mesh:hull-tangle → setup si>0
    nc_mesh = True
    tangle_detail = {}
    for slot, ma in OPAQUE:
        gen = rig.generate_weighted_part_mesh("assets/Award.json", slot, max_area=ma)
        tang = rig.weighted_deform_gate(gen, mutate=_hull_tangle(gen))
        caught = (not tang["clean"]) and (tang["self_intersections"] > 0)
        nc_mesh = nc_mesh and caught
        tangle_detail[slot] = (tang["self_intersections"], tang["setup_clean"])
    c25 = nc_pivot and nc_tree and nc_mesh
    say("C2-5 閘非恆真(三能力各一負對照)")
    say("     (a) pivot 隨機 med/rig={:.2f} 互換 med/rig={:.2f} (皆>{}) -> {}".format(
        rand_med_rel, swap_med_rel, TAU, "ok" if nc_pivot else "X"))
    say("     (b) tree 隨機命中={:.4f}(<0.05)+ 納 effect root={} 汙染={} -> {}".format(
        rand_tree_hit, bad["root"].split("/")[-1], corrupt, "ok" if nc_tree else "X"))
    say("     (c) weighted hull-tangle: " + ", ".join(
        "{} si={}".format(s.split("/")[-1], d[0]) for s, d in tangle_detail.items())
        + " -> {}".format("ok" if nc_mesh else "X"))
    say("     -> {}".format("PASS" if c25 else "FAIL"))

    overall = c21 and c22 and c23 and c24 and c25
    if verbose:
        print("\nOVERALL -> {}".format("PASS ✅" if overall else "FAIL ❌"))
    return dict(c21=c21, c22=c22, c23=c23, c24=c24, c25=c25, overall=overall,
                max_rel=max_rel, rect_max_rel=rect_max_rel,
                award_tree_ok=award_ok, rand_tree_hit=rand_tree_hit)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-q", "--quiet", action="store_true")
    a = ap.parse_args()
    print("=" * 74)
    print("C2 閘 —— weighted mesh 生成 + rig 自動推斷(經 gen_lib.rig 公開 API)")
    print("=" * 74)
    r = evaluate(verbose=not a.quiet)
    sys.exit(0 if r["overall"] else 1)


if __name__ == "__main__":
    main()
