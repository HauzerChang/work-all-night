#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 的**weighted mesh 生成 + rig 自動推斷**入口(MERGE_PLAN Phase C2)。

C1 的 `mesh.py` 把 repo 的 **unweighted** mesh 生成(strip/delaunay)+ 真實 deform 自交閘抽成 skill 入口;
C2 的 `rig.py` 補上結構軸的另外兩塊,讓 2.0 能從「一堆拆好的件」**自動長出可動的骨架**:

  1. **weighted mesh 生成**(`generate_weighted_mesh`:內部取樣密度 + heat-diffusion/BBW 骨綁權重)——
     C1 的 strip mesh 是 unweighted(靠逐頂點 deform 動);C2 產**weighted** mesh(靠骨骼 skinning 動),
     權重天然 partition-of-unity、網格上平滑擴散,是「件綁骨後平滑彎折」的前提。
  2. **rig 自動推斷**(`infer_tree` 肢體父子樹 + `infer_pivots` 關節 pivot)——從各件世界多邊形
     **推斷運動學拓樸**(誰是根、誰掛誰)與**每根關節 pivot 落點**(父子接觸縫質心),
     使 `--rig` 完全自決,不再硬編星形假設,且支援多跳肢體鏈(手→前臂→上臂→軀幹)。

== 為什麼存在(C2 的增量;結構軸的 rig 分支)==
  v1.3.0 的 skill **只能在既有骨架上疊動畫**;要「新增 bone、把件綁上去、擺 pivot」得人工開 editor。
  C2 讓 2.0 能從**件幾何**自動推斷 rig 骨架拓樸 + pivot,並產出能平滑變形的 weighted mesh ——
  當「結構性無法做到」是因為件根本沒綁骨 / 綁錯父子 / pivot 擺錯關節時,本入口把這條上游補起來。

== 核心能力(對外契約)==
  rig 自動推斷:
    `infer_limb_tree(parts)`     各件世界多邊形 → (root, tree{child:parent}, info);接觸距離 Dijkstra 樹,
                                 recover 鏈(非強制星形)。
    `infer_joint_pivots(parts, tree)`  → {child: joint_xy};關節 = 子件最靠父件的 q 分位點質心(接觸縫)。
    `infer_rig(parts)`           一條龍 → {root, tree, pivots, info};rig_is_schema_valid 可機讀自檢。
  weighted mesh 生成:
    `generate_weighted_part_mesh(skeleton, slot, max_area, topk)`  mesh slot → heat-diffusion weighted mesh
                                 (回傳 eval 所需的 gen bundle)。
    `eval_generated_weighted(gen)`  生成 mesh 跑 setup 自一致 + 真實動畫 deform(worst si/flip/degen + 平滑度)。
    `weighted_deform_gate(skeleton, slot, mutate, amplify)`  既有藝術家 weighted mesh 過同一道閘(真值校準/負對照)。

== 真相來源(可自主驗收的範圍)==
  · **合成肢體鏈 fixture**(確定性矩形 body→arm→forearm→hand,只有相鄰件接觸)→ 驗 rig 拓樸推斷
    端到端 recover 成**鏈**(非星形);純幾何、無需真值。
  · **Award 機器人**(repo 既有真值:藝術家親手放的 bone pivot + 乾淨 weighted mesh)→ 校準 pivot 準度
    與 weighted mesh deform 閘。
  ⚠️ **honest boundary**:真實**多樣** rig 真值(各種人形/非人形骨架)仍屬使用者資源(S5→L3 硬缺口);
     本入口只搬「單一 Award 真值 + 合成鏈」可自主的部分。pivot 沿肢體軸的精修、動起來的手感 = 美術微調
     (RULES A 類),不在此入口的客觀閘內。

== 過渡期相依(C2 → E1)==
  本檔**import repo 的 `tools/mesh_gen` + `tools/rig`**(透過 `_wire_repo_tools()` 路徑 shim),與 B2/B3/B4/C1 一致。
  **Phase E1** 會把生成碼 bundle 進 `assets/`(self-contained,滿足 G5),屆時移除此 shim。
  依賴:numpy / scipy(稀疏解 + cKDTree)/ triangle(三角化)/ opencv(選用,region alpha 輪廓)——
  皆在 SessionStart hook 的 requirements.txt。

用法(CLI):
  python3 rig.py --self-test                 # 對合成鏈 + Award 機器人自檢
  python3 rig.py --infer-award               # 印 Award 機器人推斷 rig(tree + pivots)

程式化:
  from gen_lib.rig import infer_rig, generate_weighted_part_mesh, synthetic_limb_chain
  rig = infer_rig(synthetic_limb_chain())    # {root, tree, pivots, info}
  gen = generate_weighted_part_mesh("assets/Award.json", "機器人拆件/身體")
"""
from __future__ import annotations
import argparse
import json
import math
import os
import sys


# --------------------------------------------------------------------- 過渡期路徑 shim
def _wire_repo_tools():
    """把 repo 的 tools/mesh_gen + tools/rig 掛上 sys.path,回傳生成/推斷/評估模組。
    E1 self-contained bundle 後本函式改為指向 bundled 目錄即可。

    回傳 (generate_weighted_mesh, weighted_deform_eval, infer_pivots, infer_tree)。"""
    here = os.path.dirname(os.path.abspath(__file__))              # .../assets/gen_lib
    # repo 根:assets/gen_lib → assets → spine-ai-editor → skills → repo
    repo = os.path.normpath(os.path.join(here, "..", "..", "..", ".."))
    for p in (os.path.join(repo, "tools", "mesh_gen"),
              os.path.join(repo, "tools", "rig")):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        import generate_weighted_mesh as GW
        import weighted_deform_eval as W
        import infer_pivots as IP
        import infer_tree as IT
    except ImportError as e:
        raise ImportError(
            "gen_lib.rig 過渡期需要 repo 的 tools/mesh_gen + tools/rig"
            "(generate_weighted_mesh / weighted_deform_eval / infer_pivots / infer_tree)。"
            "在 repo 環境下跑;E1 self-contained bundle 後此相依會移除。原始錯誤:{}".format(e))
    return GW, W, IP, IT


def _repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "..", ".."))


# --------------------------------------------------------------------- 1. rig 自動推斷
def infer_limb_tree(parts, tau_frac=0.06, step=2.0):
    """各件世界多邊形 → (root_name, tree{child:parent}, info)。

    parts: {name: Nx2 世界多邊形(有序外廓)}。
    演算法(見 repo infer_tree):件間接觸距離(加密邊界最近距;重疊=0)構成完全圖,
      root = 面積最大件(軀幹),父邊 = 自 root 的接觸距離 Dijkstra 最短路徑樹 → recover 鏈(非強制星形)。
    tree 不含 root。info 含 D(接觸矩陣)/degree/tau/scale。
    """
    _, _, _, IT = _wire_repo_tools()
    return IT.infer_tree(parts, tau_frac=tau_frac, step=step)


def infer_joint_pivots(parts, tree, q=0.2):
    """各件世界多邊形 + 父子樹 → {child: joint_xy(np.array)}。

    關節 = child 點集中最靠近 parent 點雲的 q 分位點質心(父子**接觸縫**;肩/頸/hip 皆在此)。
    root(無父)不推斷。此為 draft 級草案;沿肢體軸的精修屬美術微調(RULES A 類)。
    """
    _, _, IP, _ = _wire_repo_tools()
    return IP.infer_pivots(parts, tree, q=q)


def infer_rig(parts, tau_frac=0.06, q=0.2):
    """一條龍:各件世界多邊形 → {root, tree, pivots, info}。

    = infer_limb_tree(拓樸)+ infer_joint_pivots(每關節 pivot)。rig 自動推斷的對外單一入口。
    """
    root, tree, info = infer_limb_tree(parts, tau_frac=tau_frac)
    pivots = infer_joint_pivots(parts, tree, q=q)
    return {"root": root, "tree": tree, "pivots": pivots, "info": info}


def rig_is_schema_valid(rig, parts):
    """推斷出的 rig 的最小 schema 檢查(可機讀)。回傳 (ok, problems[])。

    檢查:root 在 parts;tree 每條邊 child/parent 皆在 parts 且父≠子;無環(每件沿 parent 可達 root);
    每個非 root 件都有 parent;每個非 root 件都有 pivot。
    """
    probs = []
    root = rig.get("root")
    tree = rig.get("tree", {})
    pivots = rig.get("pivots", {})
    names = set(parts.keys())
    if root not in names:
        probs.append("root={} 不在 parts".format(root))
    for c, p in tree.items():
        if c not in names:
            probs.append("tree child {} 不在 parts".format(c))
        if p not in names:
            probs.append("tree parent {} 不在 parts".format(p))
        if c == p:
            probs.append("tree 自環 {}".format(c))
    # 每個非 root 件都要有 parent
    for nm in names:
        if nm != root and nm not in tree:
            probs.append("非 root 件 {} 無 parent".format(nm))
    # 無環:沿 parent 走必在 len(names) 步內到 root
    for c in tree:
        cur, seen, steps = c, set(), 0
        while cur != root and cur in tree and steps <= len(names):
            if cur in seen:
                probs.append("tree 成環於 {}".format(cur))
                break
            seen.add(cur)
            cur = tree[cur]
            steps += 1
        if cur != root and cur not in tree and cur != root:
            # 走到一個既非 root、又無 parent 的節點 → 斷鏈(除非它就是 root)
            if cur != root:
                probs.append("件 {} 的 parent 鏈未達 root".format(c))
    # 每個非 root 件都要有 pivot
    for nm in names:
        if nm != root and nm not in pivots:
            probs.append("非 root 件 {} 無 pivot".format(nm))
    return (len(probs) == 0, probs)


def centroid_pivot_baseline(parts, tree):
    """天真 baseline:用子件質心當 pivot(接觸縫法須顯著贏過它)。供負對照/比較。"""
    _, _, IP, _ = _wire_repo_tools()
    return IP.centroid_baseline(parts, tree)


# --------------------------------------------------------------------- 2. weighted mesh 生成
def generate_weighted_part_mesh(skeleton, slot, max_area=1500.0, topk=4):
    """對 skeleton 某 mesh slot,從其輪廓 hull 生成 **heat-diffusion weighted mesh**。

    skeleton: Spine json 路徑。slot: mesh attachment 的 slot 名。
    max_area: 三角化內部取樣密度上界(越小越密)。topk: 每頂點至多綁幾骨(Spine 上限 4)。
    回傳 gen bundle(dict),含:
      pv(weighted vertices,[[(bidx,bx,by,w),...], ...])/ tris / mesh_bone_names /
      sk,bones,byname,order,bidx_to_name(供 eval)/ artist(藝術家 mesh 的 pv/tris/hull/nv 作基準)。
    權重由 cotangent Laplacian + heat H 稀疏解得,天然 partition-of-unity(每頂點和=1)。
    """
    GW, _, _, _ = _wire_repo_tools()
    return GW.generate_for_slot(skeleton, slot, max_area=max_area, topk=topk)


def eval_generated_weighted(gen):
    """生成 weighted mesh → setup 自一致 + 真實動畫 deform(worst si/flip/degen + 平滑度)。

    回傳 eval dict:worst(真實動畫最壞幀)/ setup(重建 setup pose 乾淨度)/ smoothness
      (edge_cv_increase_max / area_ratio_std,量變形平滑度)/ nv / checker_validated。
    """
    _, W, _, _ = _wire_repo_tools()
    return W.eval_pv(gen["sk"], gen["bones"], gen["byname"], gen["order"],
                     gen["bidx_to_name"], gen["pv"], gen["tris"], gen["mesh_bone_names"])


def weighted_deform_gate(skeleton, slot, name=None, mutate=None, amplify=1.0):
    """既有(藝術家)weighted mesh 過真實動畫 deform 閘。真值校準 + 負對照用。

    mutate: 可選的綁定擾動(如 scramble weights)→ 負對照應使閘爆(si>0)。
    amplify: 動作幅度放大倍數(放大可分離「藝術家乾淨 vs 壞綁定」)。
    回傳 evaluate_weighted_mesh 的 dict(nv/tris/bones/setup/worst/anims)。
    """
    _, W, _, _ = _wire_repo_tools()
    return W.evaluate_weighted_mesh(skeleton, slot, name=name, mutate=mutate, amplify=amplify)


def mutate_scramble_weights():
    """回傳 repo 的「打亂權重」擾動函式(供 weighted_deform_gate 的 mutate= 做負對照)。"""
    _, W, _, _ = _wire_repo_tools()
    return W.mutate_scramble_weights


# --------------------------------------------------------------------- 3. 真值/合成 fixture
def load_award_robot_parts(award_path=None, use_alpha=True):
    """Award 機器人子 rig → (parts_world, truth_pivots, tree_truth, fidelity)。

    parts_world: {slot: Nx2 世界多邊形};truth_pivots: {slot: 藝術家 bone 世界位置}(= pivot 真值);
    tree_truth: ROBOT_TREE(結構肢體,光暈不列);fidelity: {slot: 'mesh'|'alpha'|'rect'}。
    use_alpha=True 時 region 件優先用 atlas alpha 真實輪廓(需 Award.png)。
    """
    _, _, IP, _ = _wire_repo_tools()
    if award_path is None:
        award_path = os.path.join(_repo_root(), "assets", "Award.json")
    return IP.load_award_robot(award_path, use_alpha=use_alpha)


def award_robot_struct_parts(award_path=None, use_alpha=True):
    """Award 機器人**結構件**(去掉光暈 effect)的世界多邊形 + 真值,供 rig 推斷校準。
    回傳 (struct_parts, truth_pivots, tree_truth)。"""
    parts, truth, tree, _fid = load_award_robot_parts(award_path, use_alpha=use_alpha)
    _, _, IP, _ = _wire_repo_tools()
    halo = "機器人拆件/光暈"
    struct = {k: v for k, v in parts.items() if k != halo}
    return struct, truth, tree


def _rect(cx, cy, w, h):
    import numpy as np
    return np.array([[cx - w / 2, cy - h / 2], [cx + w / 2, cy - h / 2],
                     [cx + w / 2, cy + h / 2], [cx - w / 2, cy + h / 2]], dtype=float)


def synthetic_limb_chain():
    """確定性合成肢體鏈 fixture(無需真值,純幾何驗 rig 拓樸推斷)。

    body(trunk,最大面積→root)→ upper → lower,只有**相鄰件**邊界貼近、隔一件遠 →
    infer_limb_tree 的接觸距離 Dijkstra 樹應 recover 成**鏈**(upper→body、lower→upper),非星形。
    回傳 {name: Nx2 多邊形}。幾何對映 repo validate_tree.py AC4(端到端等價)。
    """
    return {
        "torso": _rect(0, 0, 180, 180),
        "upper": _rect(0, 150, 90, 90),
        "lower": _rect(0, 290, 90, 90),
    }


def synthetic_star():
    """確定性合成星形 fixture:torso 中心 + 3 件各方向貼上 → 全掛 torso(證推斷非只會鏈)。"""
    return {
        "torso": _rect(0, 0, 120, 120),
        "a": _rect(0, 130, 80, 80),
        "b": _rect(130, 0, 80, 80),
        "c": _rect(-130, 0, 80, 80),
    }


# --------------------------------------------------------------------- 自檢
def _self_test():
    import numpy as np
    out = {}

    # --- rig 推斷:合成鏈(端到端 recover 鏈) ---
    chain = synthetic_limb_chain()
    rig_chain = infer_rig(chain, tau_frac=0.30)
    sch_ok, sch_probs = rig_is_schema_valid(rig_chain, chain)
    chain_is_chain = (rig_chain["root"] == "torso"
                      and rig_chain["tree"].get("upper") == "torso"
                      and rig_chain["tree"].get("lower") == "upper")
    out["synthetic_chain"] = {
        "root": rig_chain["root"], "tree": rig_chain["tree"],
        "schema_ok": sch_ok, "schema_problems": sch_probs,
        "recovered_chain_not_star": chain_is_chain,
        "pass": sch_ok and chain_is_chain,
    }

    # --- rig 推斷:合成星形 ---
    star = synthetic_star()
    rig_star = infer_rig(star, tau_frac=0.30)
    star_ok = (rig_star["root"] == "torso"
               and all(rig_star["tree"].get(k) == "torso" for k in ("a", "b", "c")))
    out["synthetic_star"] = {"root": rig_star["root"], "tree": rig_star["tree"], "pass": star_ok}

    # --- rig 推斷 + pivot 準度:Award 機器人真值 ---
    try:
        struct, truth, tree_truth = award_robot_struct_parts()
        rig_award = infer_rig(struct)
        tree_ok = (rig_award["tree"] == tree_truth)
        # pivot 準度(相對軀幹 diag 的分數)
        parents = {tree_truth[c] for c in tree_truth if tree_truth[c] in struct}
        diags = [float(np.hypot(*(struct[p].max(0) - struct[p].min(0)))) for p in parents]
        scale = float(np.mean(diags)) if diags else 1.0
        rel = {c: float(np.linalg.norm(rig_award["pivots"][c] - truth[c])) / scale
               for c in tree_truth if c in rig_award["pivots"]}
        award_pivot_ok = max(rel.values()) < 0.10
        out["award_rig"] = {"tree_ok": tree_ok, "max_pivot_rel": round(max(rel.values()), 4),
                            "pass": tree_ok and award_pivot_ok}
    except Exception as e:
        out["award_rig"] = {"pass": False, "error": str(e)}

    # --- weighted mesh 生成 + deform 閘:Award body ---
    try:
        gen = generate_weighted_part_mesh(os.path.join(_repo_root(), "assets", "Award.json"),
                                          "機器人拆件/身體", max_area=1500.0)
        ev = eval_generated_weighted(gen)
        gen_ok = (ev["setup"]["clean"]
                  and ev["worst"]["self_intersections"] == 0
                  and ev["worst"]["triangle_flips"] == 0)
        out["weighted_gen"] = {"nv": ev["nv"], "worst": ev["worst"],
                               "setup_clean": ev["setup"]["clean"], "pass": gen_ok}
    except Exception as e:
        out["weighted_gen"] = {"pass": False, "error": str(e)}

    allpass = all(v.get("pass") for v in out.values())
    return {"overall_pass": allpass, "parts": out}


def _print_award_rig():
    import numpy as np
    struct, truth, tree_truth = award_robot_struct_parts()
    rig = infer_rig(struct)
    print("inferred root =", rig["root"])
    print("inferred tree:")
    for c, p in rig["tree"].items():
        print("  {:<18} -> {}".format(c, p))
    print("truth tree    :", tree_truth)
    print("inferred pivots vs truth:")
    for c in tree_truth:
        if c in rig["pivots"]:
            j = rig["pivots"][c]; t = truth[c]
            print("  {:<18} infer=({:8.2f},{:8.2f}) truth=({:8.2f},{:8.2f}) err={:6.2f}px".format(
                c, j[0], j[1], t[0], t[1], float(np.linalg.norm(j - t))))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true", help="對合成鏈 + Award 機器人自檢")
    ap.add_argument("--infer-award", action="store_true", help="印 Award 機器人推斷 rig(tree + pivots)")
    a = ap.parse_args()
    if a.self_test:
        rep = _self_test()
        print(json.dumps(rep, ensure_ascii=False, indent=2, default=float))
        sys.exit(0 if rep["overall_pass"] else 1)
    if a.infer_award:
        _print_award_rig()
        sys.exit(0)
    ap.error("需 --self-test 或 --infer-award")


if __name__ == "__main__":
    main()
