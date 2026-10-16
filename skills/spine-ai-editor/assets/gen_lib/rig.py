#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_lib.rig — spine-ai-editor 2.0 的**weighted mesh 生成 + rig 自動推斷**入口(MERGE_PLAN Phase C2)。

承 C1(`mesh.py`,結構軸的 mesh 分支:件影像 → 耐變形 unweighted mesh)。C2 把 repo 累積的
**S5 rig 自動化**(`infer_tree` 肢體父子樹推斷 + `infer_pivots` 接觸縫關節 pivot)與
**weighted mesh 生成**(`generate_weighted_mesh` heat-diffusion / BBW 近似)包成一條 skill 層級流程:
給一組**拆件世界多邊形**(S4 切圖 / S1 分析器產物)→ 自動推斷**運動學骨架**(root + 父子樹 + 關節 pivot)
→ 對需要骨綁變形的件生成 **weighted mesh**(控制骨接進關節鏈)→ 經 `build_spine --rig --weighted`
組成**可被關節 articulate 的完整 rig**,並自驗(setup 不位移 / 遞迴帶動 / 變形乾淨)。

== 為什麼存在(C2 的增量;結構軸的 rig 分支)==
  v1.3.0 的 skill 能**修動畫手感**(curve_tools)、C1 讓 2.0 能**生成耐變形 mesh**;但「件只能整塊剛體
  位移、沒有骨架階層、關節 pivot 放錯 → 肢體繞錯點轉」仍是 structural 限制。當目標需要**多跳肢體鏈**
  (手→前臂→上臂→軀幹,轉肩膀整條手臂跟著動)時,需要:①自動推出父子樹(誰掛誰);②關節 pivot 落在
  父子接觸縫(肩/肘/腕);③中段肢體用 weighted mesh(既是某件的子、又是另一件的父)。C2 把這三件事
  抽成 skill 入口並端到端自驗。

== 核心能力(對外契約)==
  [rig 推斷 — 由拆件幾何]
    1. infer_rig_tree(parts)         → (root, tree, info):面積優先 root + 接觸距離 Dijkstra 父子樹(支援多跳鏈)。
    2. infer_joint_pivots(parts,tree)→ {child: (x,y)}:每個子件關節 = 與**其父件**接觸縫質心。
    3. contact_seam_joint(P,C)       → (joint, seam):單一父子對的接觸縫 pivot(低階)。
    4. centroid_pivot_baseline / diagnose_effect_contamination:負對照(證推斷非恆真、須結構輸入)。
  [weighted mesh 生成 — heat-diffusion / BBW 近似]
    5. generate_weighted_part(skeleton,slot) → 對一張輪廓三角化 + 骨綁權重(partition of unity、≤4 骨/頂點)。
    6. weighted_part_quality(gen)    → {partition_ok, max_bones_per_vertex, worst_si/flip, setup_clean, ...}。
  [端到端 rig 組裝]
    7. make_synthetic_limb_chain(psd)→ 合成多跳肢體鏈 fixture(body→arm→forearm→hand)。
    8. build_rigged_skeleton(psd,out)→ build_spine --rig --weighted 組成可載入 rig(控制骨接進關節鏈)。
    9. award_robot_truth()           → 載入 Award 機器人真值(parts/pivots/tree/fidelity),供 rig 推斷校準。

== 真相來源(誠實邊界)==
  · rig 推斷校準 = **Award 機器人藝術家真值**(骨世界位置 = 真值 pivot;ROBOT_TREE = 真值樹)。
  · 「weighted mesh 當鏈中段肢體」在 Award 無真實樣本(其可拆肢體皆 region、星形單跳)→ 用**合成多跳鏈
    fixture** 補此缺口(端到端 si=0 / 遞迴帶動,見 `knowledge/s5-rig-weighted-combo.md` honest boundary)。
  · ⚠️ **真實多 rig 真值**(多角色、非人形運動分群)仍屬**使用者資源**(S5→L3 硬缺口);此入口只搬**可自主**
    的合成端到端 + 單一真值(Award)校準。pivot 沿肢體軸的精修 / 動起來的手感 = 美術微調(RULES A 類)。

== 過渡期相依(C2 → E1)==
  本檔 import repo 的 `tools/mesh_gen`(generate_weighted_mesh / weighted_deform_eval)、`tools/rig`
  (infer_pivots / infer_tree)、`tools/analyzer`(build_spine)。與 B2/B3/B4/C1 一致。**Phase E1** bundle
  後移除此 shim。依賴:numpy / opencv(cv2)/ scipy(spsolve, cKDTree)/ triangle / psd_tools —— 皆在
  SessionStart hook 的 requirements.txt。

用法(CLI):
  python3 rig.py --self-test                     # Award 真值 rig 推斷 + 合成鏈端到端自檢
  python3 rig.py --infer-award                   # 印 Award 機器人推得 root/tree/pivot vs 真值
  python3 rig.py --weighted-slot 機器人拆件/身體  # 對 Award 某件生成 weighted mesh 並印品質

程式化:
  from gen_lib.rig import (infer_rig_tree, infer_joint_pivots, generate_weighted_part,
                           build_rigged_skeleton, make_synthetic_limb_chain, award_robot_truth)
"""
from __future__ import annotations
import argparse
import json
import os
import sys


# --------------------------------------------------------------------- 過渡期路徑 shim
def _wire_repo_tools():
    """把 repo 的 tools/{mesh_gen,rig,analyzer} 掛上 sys.path,回傳所需模組。
    E1 self-contained bundle 後本函式改為指向 bundled 目錄即可。

    回傳 (gwm, wde, infer_pivots_mod, infer_tree_mod, build_spine_mod, make_chain_mod)。"""
    here = os.path.dirname(os.path.abspath(__file__))              # .../assets/gen_lib
    repo = os.path.normpath(os.path.join(here, "..", "..", "..", ".."))
    for p in (os.path.join(repo, "tools", "mesh_gen"),
              os.path.join(repo, "tools", "rig"),
              os.path.join(repo, "tools", "analyzer")):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        import generate_weighted_mesh as GWM
        import weighted_deform_eval as WDE
        import infer_pivots as IP
        import infer_tree as IT
        import build_spine as BS
        import make_limb_chain_psd as MK
    except ImportError as e:
        raise ImportError(
            "gen_lib.rig 過渡期需要 repo 的 tools/{mesh_gen,rig,analyzer}"
            "(generate_weighted_mesh / weighted_deform_eval / infer_pivots / infer_tree / "
            "build_spine / make_limb_chain_psd)。在 repo 環境下跑;E1 self-contained bundle 後"
            "此相依會移除。原始錯誤:{}".format(e))
    return GWM, WDE, IP, IT, BS, MK


def _repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "..", ".."))


def _p(rel):
    return os.path.join(_repo_root(), rel)


# --------------------------------------------------------------------- 1. rig 推斷(由拆件幾何)
def infer_rig_tree(parts, tau_frac=0.06, step=2.0):
    """parts: {name: Nx2 世界多邊形} → (root_name, tree{child:parent}, info)。

    root = **面積最大件**(軀幹);父邊 = 接觸距離為權重的 Dijkstra 最短路徑樹(星形直達 body、
    鏈形經中段轉),支援多跳肢體鏈。tree 不含 root。(wraps infer_tree.infer_tree)"""
    _, _, _, IT, _, _ = _wire_repo_tools()
    return IT.infer_tree(parts, tau_frac=tau_frac, step=step)


def infer_joint_pivots(parts, tree, q=0.2):
    """parts: {name: Nx2}; tree: {child:parent} → {child: joint_xy(np.array)}。
    每個子件關節 = child 最靠近**其父件**的 q 分位點集合質心(接觸縫)。root 不推斷。
    (wraps infer_pivots.infer_pivots)"""
    _, _, IP, _, _, _ = _wire_repo_tools()
    return IP.infer_pivots(parts, tree, q=q)


def contact_seam_joint(parent_poly, child_poly, q=0.2):
    """單一父子對的接觸縫 pivot(低階)→ (joint_xy, seam_pts)。(wraps infer_pivots.contact_seam_joint)"""
    _, _, IP, _, _, _ = _wire_repo_tools()
    return IP.contact_seam_joint(parent_poly, child_poly, q=q)


def centroid_pivot_baseline(parts, tree):
    """天真 baseline:用子件質心當 pivot。接觸縫法須顯著贏過它(負對照用)。"""
    _, _, IP, _, _, _ = _wire_repo_tools()
    return IP.centroid_baseline(parts, tree)


def diagnose_effect_contamination(parts_with_effect, effect_names, tau_frac=0.06):
    """把 effect 件(如光暈)也當結構件推 → 是否汙染樹(root/邊落在 effect 上)。
    回傳 (root, tree, corrupted)。corrupted=True 論證『結構 vs 特效角色分類須作為輸入』
    (honest boundary)。(wraps infer_tree.diagnose_include_effect)"""
    _, _, _, IT, _, _ = _wire_repo_tools()
    return IT.diagnose_include_effect(parts_with_effect, effect_names, tau_frac=tau_frac)


# --------------------------------------------------------------------- 2. weighted mesh 生成(BBW/heat)
def generate_weighted_part(skeleton_path, slot, max_area=1500.0, topk=4):
    """對 skeleton 中某件(以藝術家 hull 為輪廓真值)三角化 + heat-diffusion 骨綁權重,
    產出 Spine weighted mesh(partition of unity、每頂點 ≤4 骨)。回傳 generate_for_slot 的 dict
    (含 sk/bones/byname/order/bidx_to_name/pv/tris/mesh_bone_names/artist)。
    (wraps generate_weighted_mesh.generate_for_slot)"""
    GWM, _, _, _, _, _ = _wire_repo_tools()
    return GWM.generate_for_slot(skeleton_path, slot, max_area=max_area, topk=topk)


def weighted_part_quality(gen):
    """量化生成 weighted mesh 的品質(可機讀):
      partition_ok         : 每頂點權重和 ≈ 1(|sum-1| < 1e-5)。
      max_bones_per_vertex : 每頂點綁骨數上限(Spine ≤ 4)。
      setup_clean          : 生成 mesh 重建 setup pose 無自交 / 退化。
      worst_si / worst_flip: 真實動畫骨骼變形下最差自交 / 翻面(過 weighted_deform_eval 同一道閘)。
      checker_validated    : 該閘已對藝術家真值重現(真值校準)。
      smoothness / nv / artist_nv:平滑度指標與頂點預算。
    真相來源 = weighted_deform_eval.eval_pv(已對 Award 真值重現)。"""
    _, WDE, _, _, _, _ = _wire_repo_tools()
    pv = gen["pv"]
    partition_ok = True
    max_bones = 0
    for entries in pv:
        max_bones = max(max_bones, len(entries))
        s = sum(e[3] for e in entries)
        if abs(s - 1.0) > 1e-5:
            partition_ok = False
    r = WDE.eval_pv(gen["sk"], gen["bones"], gen["byname"], gen["order"], gen["bidx_to_name"],
                    gen["pv"], gen["tris"], gen["mesh_bone_names"])
    return {
        "partition_ok": bool(partition_ok),
        "max_bones_per_vertex": int(max_bones),
        "setup_clean": bool(r["setup"]["clean"]),
        "worst_si": int(r["worst"]["self_intersections"]),
        "worst_flip": int(r["worst"]["triangle_flips"]),
        "checker_validated": bool(r["checker_validated"]),
        "smoothness": r["smoothness"],
        "nv": int(r["nv"]),
        "artist_nv": int(gen["artist"]["nv"]),
    }


# --------------------------------------------------------------------- 3. 端到端 rig 組裝
def make_synthetic_limb_chain(out_psd):
    """造合成多跳肢體鏈 fixture:body → arm → forearm → hand(arm/forearm 夠大 → weighted mesh,
    各在鏈中段;hand 小 region 葉件;只有相鄰件重疊 → infer_tree recover 成鏈而非星形)。
    回傳 psd 路徑。(wraps make_limb_chain_psd.build)"""
    _, _, _, _, _, MK = _wire_repo_tools()
    return MK.build(out_psd)


def build_rigged_skeleton(psd_path, out_dir, genre="slot_bigwin", rig=True, weighted=True):
    """從拆件 PSD 組成 Spine 素材;rig=True 自動推斷骨架父子樹 + 關節 pivot,
    weighted=True 對 mesh 件生成 weighted mesh 並把控制骨接進關節鏈。回傳 out_dir。
    (wraps build_spine.build)"""
    _, _, _, _, BS, _ = _wire_repo_tools()
    BS.build(psd_path, out_dir, genre, rig=rig, weighted=weighted)
    return out_dir


def award_robot_truth(award_path=None, use_alpha=True):
    """載入 Award 機器人真值 → (parts_world, truth_pivots, tree, fidelity)。
    parts_world: {slot: Nx2 世界多邊形};truth_pivots: {slot: 藝術家 bone 世界位置};
    tree = ROBOT_TREE(真值父子樹)。rig 推斷閘用此校準。(wraps infer_pivots.load_award_robot)"""
    _, _, IP, _, _, _ = _wire_repo_tools()
    award_path = award_path or _p("assets/Award.json")
    return IP.load_award_robot(award_path, use_alpha=use_alpha)


# --------------------------------------------------------------------- 自檢
def _self_test():
    """Award 真值 rig 推斷(root/tree 精確、pivot 勝 baseline)+ 合成鏈端到端(root=body、鏈非星形)。
    回傳精簡自檢報告(非完整 5AC;完整閘見 tools/analyzer/validate_c2_rig.py)。"""
    import numpy as np
    import tempfile
    import shutil

    out = {}
    # (1) Award 真值 rig 推斷
    parts, truth, tree_truth, fid = award_robot_truth()
    halo = "機器人拆件/光暈"
    struct = {k: v for k, v in parts.items() if k != halo}
    root, tree, info = infer_rig_tree(struct)
    body = "機器人拆件/身體"
    tree_ok = (root == body) and (tree == tree_truth)
    piv = infer_joint_pivots(struct, tree_truth)
    base = centroid_pivot_baseline(struct, tree_truth)
    med_err = float(np.median([np.linalg.norm(piv[c] - truth[c]) for c in tree_truth]))
    med_base = float(np.median([np.linalg.norm(base[c] - truth[c]) for c in tree_truth]))
    out["award_infer"] = {"root_ok": root == body, "tree_ok": tree_ok,
                          "pivot_med_err": round(med_err, 2),
                          "baseline_med_err": round(med_base, 2),
                          "beats_baseline": med_err < med_base}

    # (2) 合成鏈端到端(只驗 build + root/鏈結構;完整帶動/變形見 validate_c2_rig)
    tmp = tempfile.mkdtemp(prefix="c2rig_selftest_")
    try:
        psd = make_synthetic_limb_chain(os.path.join(tmp, "limb_chain.psd"))
        out_dir = build_rigged_skeleton(psd, os.path.join(tmp, "rw"), rig=True, weighted=True)
        sk = json.load(open(os.path.join(out_dir, "skeleton.json"), encoding="utf-8"))
        bones = sk["bones"]
        pmap = {b["name"]: b.get("parent") for b in bones}
        # 鏈非星形:存在關節骨其 parent 是另一個關節骨(非 root / 非 body)
        joint_bones = [b["name"] for b in bones if b["name"].startswith("b_")]
        non_star = any(pmap.get(jb) not in ("root", "b_char_body", None) for jb in joint_bones)
        # 鏈深 >= 3 跳
        def _depth(nm):
            d, cur = 0, nm
            while pmap.get(cur) is not None:
                d += 1
                cur = pmap[cur]
            return d
        max_depth = max((_depth(jb) for jb in joint_bones), default=0)
        out["synth_chain"] = {"built": True, "non_star": non_star,
                              "max_chain_depth": max_depth, "chain_ok": non_star and max_depth >= 3}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    out["overall_pass"] = bool(out["award_infer"]["tree_ok"]
                               and out["award_infer"]["beats_baseline"]
                               and out["synth_chain"]["chain_ok"])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true",
                    help="Award 真值 rig 推斷 + 合成鏈端到端自檢")
    ap.add_argument("--infer-award", action="store_true",
                    help="印 Award 機器人推得 root/tree/pivot vs 真值")
    ap.add_argument("--weighted-slot", default=None,
                    help="對 Award 某件生成 weighted mesh 並印品質(如:機器人拆件/身體)")
    ap.add_argument("--max-area", type=float, default=1500.0)
    a = ap.parse_args()

    if a.self_test:
        rep = _self_test()
        print(json.dumps(rep, ensure_ascii=False, indent=2, default=float))
        sys.exit(0 if rep["overall_pass"] else 1)
    if a.infer_award:
        import numpy as np
        parts, truth, tree_truth, fid = award_robot_truth()
        struct = {k: v for k, v in parts.items() if k != "機器人拆件/光暈"}
        root, tree, info = infer_rig_tree(struct)
        piv = infer_joint_pivots(struct, tree_truth)
        print("inferred root =", root)
        for c, p in tree.items():
            print("  tree:", c, "->", p)
        for c in tree_truth:
            e = float(np.linalg.norm(piv[c] - truth[c]))
            print(f"  pivot {c}: infer={tuple(round(x,1) for x in piv[c])} "
                  f"truth={tuple(round(x,1) for x in truth[c])} err={e:.2f}px")
        sys.exit(0)
    if a.weighted_slot:
        gen = generate_weighted_part(_p("assets/Award.json"), a.weighted_slot, max_area=a.max_area)
        q = weighted_part_quality(gen)
        print(json.dumps(q, ensure_ascii=False, indent=2, default=float))
        sys.exit(0 if (q["partition_ok"] and q["setup_clean"]) else 1)
    ap.error("需 --self-test / --infer-award / --weighted-slot")


if __name__ == "__main__":
    main()
