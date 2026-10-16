#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 的**確定性 weighted mesh 生成 + rig 自動推斷**入口(MERGE_PLAN Phase C2)。

這支把 repo 半年累積的 **S3 weighted mesh 生成器**(`generate_weighted_mesh`,heat-diffusion/BBW
近似權重)與 **S5 rig 自動化**(`infer_tree` 肢體父子樹 + `infer_pivots` 接觸縫關節 pivot)
包成**一條 skill 層級的流程**:給一組「已拆件的世界多邊形」→ **自動推斷運動學樹 + 關節 pivot**,
並對 mesh 件 **生成骨綁 weighted mesh**(每頂點權重和=1、至多 4 骨),使件能隨骨骼平滑變形。

== 為什麼存在(C2 的增量;結構軸的 rig 分支)==
  B3 的 `pivot_axis.py` 是「不動骨架、動 keyframe 繞關節 pivot」;C1 的 `mesh.py` 是「生成耐變形
  unweighted mesh」。C2 補上**骨綁**那一面:
    · v1.3.0 的 skill **只能檢查既有 rig / weighted mesh**,**不能生成**;也**假設星形** rig
      (每結構件直掛 body)。
    · C2 讓 2.0 能(a)**自動推斷**拓樸(誰是根 / 誰的子件,支援多跳肢體鏈 手→前臂→上臂→軀幹)
      與**關節 pivot**(肩/頸/肘在子件↔父件的接觸縫);(b)對 mesh 件**生成 weighted mesh**
      (heat-diffusion 權重天然滿足 partition of unity、平滑擴散),使件「會彎折、會跟骨鏈遞迴帶動」,
      而非只能整塊剛體位移。
  併入後 2.0 就同時具備「生成骨綁網格 + 自動 rig」(本檔)與「把關 rig/weighted 品質」(變形 si 閘)兩面。

== 核心能力(對外契約)==
  1. `infer_limb_tree(parts)`          件世界多邊形集合 → (root, tree{child:parent}, info);接觸距離
                                        Dijkstra 樹,recover 鏈/星形(不強制星形)。
  2. `infer_joint_pivots(parts, tree)`  每子骨關節 pivot = 子件最靠近父件的接觸縫質心(tree=None 時自動先推)。
  3. `generate_weighted_part_mesh(skeleton, slot, ...)`  mesh 件 → 骨綁 weighted mesh(pv + Spine 攤平
                                        vertices + 真實動畫變形自評);權重 partition of unity、至多 topk 骨。
  4. `weighted_mesh_is_schema_valid(pv, nbones)`  Spine weighted 格式機讀檢查(每頂點 1..4 骨、權重和=1、index 合法)。
  5. `pv_to_spine_vertices(pv)`         pv(每頂點 entries)→ Spine 3.8 攤平 weighted vertices 陣列。
  6. `load_robot_rig_truth(award)`      自 Award 機器人 rig 抽真值(parts/pivots/tree/fidelity)供校準。
  7. `gate_limb_chain()`                端到端自驗:合成多跳肢體鏈 → `build_spine --rig --weighted` → 遞迴帶動
                                        (後代動/祖先旁支不動、weighted-only 脫鉤負對照、多跳)+ 變形 si=0。

== weighted mesh 的真相來源(誠實界定)==
  · heat-diffusion 權重(Baran & Popović「bone heat」;BBW 的純 CPU 稀疏解)**天然 partition of unity**,
    在網格上平滑擴散 → 剪成每頂點至多 4 骨(Spine 上限)、重正規化。
  · 變形自評用 `weighted_deform_eval.eval_pv`(真實動畫逐幀 skinning → si/flip/degen),對 Award 真值
    4 mesh×真實動畫重現 si=0(`checker_validated`),與 unweighted `deform_eval` 的 `_checker_validated`
    方法論一致。⚠️ **軟性加成件**(光暈)容許重疊(additive 混合下可見無害),不列硬性 si=0(見
    `knowledge/s3-weighted-deform-evaluator.md`)。
  · rig 推斷只推**拓樸 + 接觸縫關節**(可客觀);**軸向/手感微調**(pivot 沿肢體軸精確落點、該偏離縫幾
    像素)仍屬美術(RULES A 類),留給使用者。「結構 vs 特效」角色分類為輸入(光暈汙染樹的診斷見
    `infer_tree.diagnose_include_effect`)。

== 過渡期相依(C2 → E1)==
  本檔目前**import repo 的 `tools/mesh_gen` / `tools/rig` / `tools/analyzer`**(透過 `_wire_repo_tools()`
  路徑 shim),與 B2/B3/B4/C1 一致。**Phase E1** 會把生成碼 bundle 進 `assets/`(self-contained,滿足 G5)。
  依賴:numpy / scipy(spsolve/cKDTree)/ triangle(三角化)—— 皆在 SessionStart hook 的 requirements.txt。

用法(CLI):
  python3 rig.py --infer                 # 對 Award 機器人 rig 推樹 + pivot(對真值),印誤差
  python3 rig.py --weighted 機器人拆件/身體  # 對該 slot 生成 weighted mesh,印變形自評
  python3 rig.py --gate                   # 端到端合成肢體鏈 rig×weighted 自驗

程式化:
  from gen_lib.rig import infer_limb_tree, infer_joint_pivots, generate_weighted_part_mesh
  root, tree, info = infer_limb_tree(parts)                 # parts: {name: Nx2 世界多邊形}
  pivots = infer_joint_pivots(parts, tree)                  # {child: pivot_xy}
  w = generate_weighted_part_mesh("assets/Award.json", "機器人拆件/身體")
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

    回傳 dict(GW, WDE, IT, IP, BS, MK, CHAIN)。"""
    here = os.path.dirname(os.path.abspath(__file__))              # .../assets/gen_lib
    repo = os.path.normpath(os.path.join(here, "..", "..", "..", ".."))
    for p in (os.path.join(repo, "tools", "mesh_gen"),
              os.path.join(repo, "tools", "rig"),
              os.path.join(repo, "tools", "analyzer")):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        import generate_weighted_mesh as GW
        import weighted_deform_eval as WDE
        import infer_tree as IT
        import infer_pivots as IP
    except ImportError as e:
        raise ImportError(
            "gen_lib.rig 過渡期需要 repo 的 tools/mesh_gen + tools/rig"
            "(generate_weighted_mesh / weighted_deform_eval / infer_tree / infer_pivots)。"
            "在 repo 環境下跑;E1 self-contained bundle 後此相依會移除。原始錯誤:{}".format(e))
    mods = {"GW": GW, "WDE": WDE, "IT": IT, "IP": IP}
    # build_spine / make_limb_chain_psd / 端到端鏈閘:僅 gate_limb_chain 需要(延後 import,較重)
    return mods


def _wire_chain_tools():
    """端到端合成肢體鏈需要的 repo 工具(build_spine + fixture + 既有鏈閘)。"""
    _wire_repo_tools()
    import build_spine as BS                       # noqa: F401
    import make_limb_chain_psd as MK               # noqa: F401
    import validate_rig_weighted_chain as CHAIN    # noqa: F401
    return {"BS": BS, "MK": MK, "CHAIN": CHAIN}


def _repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "..", ".."))


# --------------------------------------------------------------------- 1. rig 拓樸推斷
def infer_limb_tree(parts, tau_frac=0.06, step=2.0):
    """件世界多邊形集合 → (root_name, tree{child:parent}, info)。

    parts: {name: Nx2 世界多邊形(有序)}。接觸距離(加密邊界最近距離,重疊=0)完全圖自 root
    跑 Dijkstra 最短路徑樹:星形→各件經 body 直達全掛 body;鏈形→遠端件經中間件轉,recover 鏈。
    root = 面積最大件(軀幹穩健幾何簽名;degree-hub 於純鏈退化)。tree 不含 root。
    """
    m = _wire_repo_tools()
    return m["IT"].infer_tree(parts, tau_frac=tau_frac, step=step)


def infer_joint_pivots(parts, tree=None, q=0.2):
    """每子骨關節 pivot = 子件最靠近父件的接觸縫(距離最小 q 分位點集合)質心。

    parts: {name: Nx2 世界多邊形}; tree: {child: parent}(None → 先 `infer_limb_tree` 自動推)。
    回傳 {child: np.array([x, y])}。root(無父)不推斷。
    僅推可客觀的接觸縫關節(肩/頸/肘);沿肢體軸精確落點與手感偏移屬美術(A 類),本器輸出草案。
    """
    m = _wire_repo_tools()
    if tree is None:
        _, tree, _ = m["IT"].infer_tree(parts)
    return m["IP"].infer_pivots(parts, tree, q=q)


def centroid_pivot_baseline(parts, tree):
    """天真 baseline:用子件質心當 pivot(接觸縫法須顯著贏過它;供負對照)。"""
    m = _wire_repo_tools()
    return m["IP"].centroid_baseline(parts, tree)


def load_robot_rig_truth(award_path=None, use_alpha=True):
    """自 Award 機器人 rig 抽真值:回傳 (parts_world, truth_pivots, tree, fidelity)。
    truth_pivots = 各件關節骨世界位置(藝術家 rig);tree = ROBOT_TREE(星形);
    fidelity[slot] ∈ {'mesh','alpha','rect'} = 該件幾何代理保真度。"""
    m = _wire_repo_tools()
    if award_path is None:
        award_path = os.path.join(_repo_root(), "assets", "Award.json")
    return m["IP"].load_award_robot(award_path, use_alpha=use_alpha)


# --------------------------------------------------------------------- 2. weighted mesh 生成
def pv_to_spine_vertices(pv):
    """pv(每頂點 entries=[(boneIdx, bindX, bindY, weight), ...])→ Spine 3.8 攤平 weighted vertices
    陣列:[boneCount, boneIdx, bindX, bindY, weight, ...](逐頂點串接)。"""
    out = []
    for entries in pv:
        out.append(len(entries))
        for (bi, bx, by, w) in entries:
            out += [int(bi), float(bx), float(by), float(w)]
    return out


def weighted_mesh_is_schema_valid(pv, nbones=None, topk=4, wsum_tol=1e-4):
    """Spine weighted mesh 的最小 schema 檢查(可機讀)。回傳 (ok, problems[])。

    檢查:每頂點 1..topk 骨(Spine 上限 4)、每頂點權重和≈1(partition of unity)、
    骨 index ≥ 0(且 < nbones 若給)。pv = 每頂點 entries 的 list。
    """
    probs = []
    if not pv:
        return (False, ["pv 空"])
    worst_sum = 0.0
    max_bones = 0
    for i, entries in enumerate(pv):
        nb = len(entries)
        max_bones = max(max_bones, nb)
        if nb < 1:
            probs.append("頂點 {} 無綁骨".format(i))
            continue
        if nb > topk:
            probs.append("頂點 {} 綁 {} 骨 > topk={}".format(i, nb, topk))
        s = sum(e[3] for e in entries)
        worst_sum = max(worst_sum, abs(s - 1.0))
        for (bi, bx, by, w) in entries:
            if bi < 0 or (nbones is not None and bi >= nbones):
                probs.append("頂點 {} 骨 index {} 越界".format(i, bi))
            if w < -1e-9:
                probs.append("頂點 {} 權重 {} < 0".format(i, w))
    if worst_sum > wsum_tol:
        probs.append("partition of unity 破壞:worst |Σw-1|={:.2e} > {:.0e}".format(worst_sum, wsum_tol))
    return (len(probs) == 0, probs)


def generate_weighted_part_mesh(skeleton, slot, max_area=400.0, topk=4, eval_deform=True):
    """mesh 件 → 骨綁 weighted mesh(heat-diffusion/BBW 近似權重),並(可選)真實動畫變形自評。

    skeleton: Award.json 路徑(真值輸入:藝術家 hull 輪廓 + 綁骨)。slot: mesh slot 名。
    回傳 dict:
      pv              : 每頂點 entries=[(boneIdx, bindX, bindY, weight)] (weighted_deform_eval 格式)。
      spine_vertices  : Spine 3.8 攤平 weighted vertices 陣列(pv_to_spine_vertices)。
      triangles       : Mx3。
      mesh_bone_names : 綁定骨名清單。
      nv / artist_nv  : 生成 / 藝術家頂點數。
      max_bones_per_vertex / worst_weight_sum_dev : partition of unity / topk 指標。
      schema          : (ok, problems)。
      deform          : eval_deform=True 時 {worst, setup_clean, smoothness, checker_validated};否則 None。
    """
    m = _wire_repo_tools()
    GW, WDE = m["GW"], m["WDE"]
    g = GW.generate_for_slot(skeleton, slot, max_area=max_area, topk=topk)
    pv, tris = g["pv"], g["tris"]
    spine_v = pv_to_spine_vertices(pv)
    schema = weighted_mesh_is_schema_valid(pv, nbones=len(g["bones"]), topk=topk)
    max_b = max(len(en) for en in pv)
    worst_sum = max(abs(sum(e[3] for e in en) - 1.0) for en in pv)
    out = {
        "slot": slot,
        "pv": pv,
        "spine_vertices": spine_v,
        "triangles": tris,
        "mesh_bone_names": g["mesh_bone_names"],
        "nv": len(pv),
        "artist_nv": g["artist"]["nv"],
        "max_bones_per_vertex": max_b,
        "worst_weight_sum_dev": worst_sum,
        "schema": {"pass": schema[0], "problems": schema[1]},
        "deform": None,
    }
    if eval_deform:
        r = WDE.eval_pv(g["sk"], g["bones"], g["byname"], g["order"], g["bidx_to_name"],
                        pv, tris, g["mesh_bone_names"])
        out["deform"] = {
            "worst": r["worst"],
            "setup_clean": bool(r["setup"]["clean"]),
            "smoothness": r["smoothness"],
            "checker_validated": bool(r["checker_validated"]),
        }
    return out


# --------------------------------------------------------------------- 3. 端到端合成肢體鏈自驗
def gate_limb_chain():
    """端到端自驗(= C2 headline):合成多跳肢體鏈 fixture(body→arm→forearm→hand,arm/forearm
    皆 weighted mesh)→ `build_spine --rig --weighted` → 遞迴帶動 + 變形乾淨。

    委派 repo 既有鏈閘 `validate_rig_weighted_chain.evaluate`(確定性組裝 + Spine 3.8 bone world
    transform,已對 Award 真值重現;純 CPU 無瀏覽器)。回傳其 dict:
      ac1(鏈結構:拓樸鏈非星形、控制骨掛關節骨、鏈深≥3)/ ac2(setup 不位移)/
      ac3(遞迴帶動:後代動、祖先旁支不動;weighted-only 全脫鉤負對照;多跳)/
      ac3r(region 葉件隨鏈)/ ac4(變形乾淨 si=0/flip=0)/ overall / chain_depth / multi_hop。
    """
    c = _wire_chain_tools()
    return c["CHAIN"].evaluate(verbose=False)


# --------------------------------------------------------------------- CLI
def _cli_infer():
    parts, truth, tree, fid = load_robot_rig_truth()
    struct = {k: v for k, v in parts.items() if "光暈" not in k}
    root, itree, info = infer_limb_tree(struct)
    import numpy as np
    print("推斷樹 root = {}  (真值 body)".format(root))
    for c, p in itree.items():
        print("  {:<18} -> {}".format(c, p))
    piv = infer_joint_pivots(struct, tree)
    scale = info["scale"]
    print("\n接觸縫關節 pivot(vs 藝術家真值,rig_scale={:.1f}px):".format(scale))
    for c in tree:
        j = piv[c]; t = truth[c]
        print("  {:<18} [{:<5}] infer=({:8.2f},{:8.2f}) err/rig={:.3f}".format(
            c, fid[c], j[0], j[1], float(np.linalg.norm(j - t)) / scale))


def _cli_weighted(slot):
    skel = os.path.join(_repo_root(), "assets", "Award.json")
    w = generate_weighted_part_mesh(skel, slot)
    print("weighted mesh {}: nv={} (artist {}) 綁骨={} 最多 {} 骨/頂點 worst|Σw-1|={:.1e}".format(
        slot, w["nv"], w["artist_nv"], w["mesh_bone_names"],
        w["max_bones_per_vertex"], w["worst_weight_sum_dev"]))
    print("  schema_ok={}  deform worst={} setup_clean={} validated={}".format(
        w["schema"]["pass"], w["deform"]["worst"], w["deform"]["setup_clean"],
        w["deform"]["checker_validated"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--infer", action="store_true", help="對 Award 機器人 rig 推樹+pivot(對真值)")
    ap.add_argument("--weighted", metavar="SLOT", help="對該 slot 生成 weighted mesh + 變形自評")
    ap.add_argument("--gate", action="store_true", help="端到端合成肢體鏈 rig×weighted 自驗")
    a = ap.parse_args()
    if a.infer:
        _cli_infer()
    if a.weighted:
        _cli_weighted(a.weighted)
    if a.gate:
        r = gate_limb_chain()
        print(json.dumps({k: r[k] for k in ("overall", "ac1", "ac2", "ac3", "ac3r", "ac4",
                                            "chain_depth", "multi_hop")},
                         ensure_ascii=False, indent=2))
        sys.exit(0 if r["overall"] else 1)
    if not (a.infer or a.weighted or a.gate):
        ap.error("需 --infer / --weighted SLOT / --gate 之一")


if __name__ == "__main__":
    main()
