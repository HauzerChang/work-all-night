#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 的**weighted mesh 生成 + rig 自動推斷**入口(MERGE_PLAN Phase C2)。

承 C1(`mesh.py`,unweighted strip/delaunay mesh 生成 + 變形自交閘)。C1 的 mesh 是**靠逐頂點
deform 變形**的網格(窗簾/旗幟);C2 補上另一半——**靠骨骼 skinning 變形**的 weighted mesh,
以及把一堆拆件自動綁成可動 rig 所需的兩個上游推斷器(關節 pivot / 肢體父子樹)。

這支把 repo 半年累積的三個**確定性、純 CPU** 生成/推斷器包成一條 skill 層級入口:
  1. S3 候選2 `generate_weighted_mesh` —— 三角化(內部取樣密度)+ heat-diffusion 骨綁權重(BBW 近似)。
  2. S5 `infer_pivots`              —— 父子接觸縫 → 關節 pivot 草案(確定性)。
  3. S5 `infer_tree`               —— 件間接觸距離 Dijkstra → 肢體父子樹(root + parent 邊)。

== 為什麼存在(C2 的增量;結構軸的 rig 分支)==
  v1.3.0 的 skill 能**檢查/驅動既有骨架**,但不能:①從件影像**生成能被骨骼平滑變形的 weighted mesh**
  (藝術家手工綁權重);②把一堆**沒有父子關係的拆件自動推成可動 rig**(誰是根、誰掛誰、關節放哪)。
  C1 解「件沒有 mesh」;C2 解「件有 mesh 但沒綁骨 / 一堆件沒組成骨架」——結構軸補完整。

== 核心能力(對外契約)==
  weighted mesh:
    generate_weighted_part_mesh(skeleton, slot, ...)  件(藝術家 hull 真值)→ Spine weighted mesh。
    weighted_schema_valid(att)                        Spine weighted 格式檢查(partition of unity / ≤4 骨)。
    weighted_deform_gate(gen, ...)                    真實動畫 skinning 變形下 si=0/flip=0 + 平滑度(vs 藝術家)。
    generate_and_gate_weighted(skeleton, slot, ...)   生成 → schema + 真實變形閘 + 頂點預算,一條龍。
  rig 自動推斷:
    infer_limb_tree(parts, ...)                       件世界多邊形 → (root, {child:parent}, info)。
    infer_joint_pivots(parts, tree, ...)              父子樹 → {child: 關節 pivot xy}。
    rig_from_parts(parts, effect_names, ...)          件 → 樹 + pivots,一條龍(排除 effect 件)。

== 真相來源與誠實邊界 ==
  * weighted 變形閘用 `weighted_deform_eval.eval_pv`(對 Award 真值重現的 Spine 3.8 skinning),
    **不用** 未校準合成場;對不透明結構件過「真實動畫 si=0」硬閘,軟性加成件(光暈)只記錄。
  * pivot 推斷只做「關節落在父子接觸縫」這個**可客觀化**子問題;沿肢體軸的精修與手感屬美術(RULES A 類)。
  * tree 推斷推的是**拓樸**(root + parent 邊);effect vs structural 語意分類須作為輸入(見負對照)。
  * weighted mesh 的 uvs 由 setup 世界座標 bbox 正規化(schema 級);**像素精準 atlas UV = build_spine/使用者端**。

== 過渡期相依(C2 → E1)==
  本檔 import repo 的 `tools/mesh_gen`(generate_weighted_mesh / weighted_deform_eval)與
  `tools/rig`(infer_pivots / infer_tree),與 B2/B3/B4/C1 一致;**E1** bundle 後移除此 shim。
  依賴:numpy / scipy / triangle(三角化)—— 皆在 SessionStart hook 的 requirements.txt。

用法(CLI):
  python3 rig.py --self-test                      # 對 repo 真實 Award rig + 合成鏈/星形自檢
  python3 rig.py --weighted assets/Award.json "機器人拆件/身體"   # 生成單件 weighted mesh

程式化:
  from gen_lib.rig import (generate_and_gate_weighted, infer_limb_tree,
                           infer_joint_pivots, rig_from_parts, load_award_robot_parts)
"""
from __future__ import annotations
import argparse
import json
import os
import sys


# --------------------------------------------------------------------- 過渡期路徑 shim
def _wire_repo_tools():
    """把 repo 的 tools/mesh_gen + tools/rig 掛上 sys.path,回傳生成/推斷模組。
    E1 self-contained bundle 後本函式改為指向 bundled 目錄即可。

    回傳 (generate_weighted_mesh_module G, weighted_deform_eval_module W,
          infer_pivots_module ip, infer_tree_module it)。"""
    here = os.path.dirname(os.path.abspath(__file__))              # .../assets/gen_lib
    repo = os.path.normpath(os.path.join(here, "..", "..", "..", ".."))
    for p in (os.path.join(repo, "tools", "mesh_gen"),
              os.path.join(repo, "tools", "rig")):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        import generate_weighted_mesh as G
        import weighted_deform_eval as W
        import infer_pivots as ip
        import infer_tree as it
    except ImportError as e:
        raise ImportError(
            "gen_lib.rig 過渡期需要 repo 的 tools/mesh_gen(generate_weighted_mesh / "
            "weighted_deform_eval)與 tools/rig(infer_pivots / infer_tree)。在 repo 環境下跑;"
            "E1 self-contained bundle 後此相依會移除。原始錯誤:{}".format(e))
    return G, W, ip, it


def _repo_root():
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, "..", "..", "..", ".."))


# --------------------------------------------------------------------- demo 件(repo 真實/合成資產)
# 自檢用:Award 機器人不透明結構件(過真實變形 si=0 硬閘)+ 軟性加成件(光暈,只記錄)。
AWARD = "assets/Award.json"
WEIGHTED_DEMO_PARTS = [
    {"skeleton": AWARD, "slot": "機器人拆件/身體", "max_area": 1500, "kind": "opaque"},
    {"skeleton": AWARD, "slot": "機器人拆件/左手", "max_area": 1400, "kind": "opaque"},
    {"skeleton": AWARD, "slot": "機器人拆件/光暈", "max_area": 1500, "kind": "soft"},
]


# ===================================================================== 1. weighted mesh 生成
def generate_weighted_part_mesh(skeleton, slot, max_area=400.0, topk=4):
    """件(以藝術家 hull 輪廓為真值輸入)→ Spine 3.8 **weighted** mesh attachment dict。

    流程(= repo generate_weighted_mesh.generate_for_slot):輪廓三角化(內部密度由 max_area 控制)
    → heat-diffusion 骨綁權重(BBW 近似,天然 partition of unity)→ 剪成每頂點 ≤ topk 骨(Spine 上限 4)
    → 逆變換算 bind 座標 → 組 Spine weighted vertices。

    回傳 dict:
      att            : Spine weighted mesh attachment(type/vertices/uvs/triangles/hull/width/height/_weighted)。
                       weighted 格式 → len(vertices) != len(uvs)([骨數, boneIdx,bindX,bindY,weight, ...] 變長)。
      pv/tris/...    : 生成中間物(供變形閘 eval_pv 直接用,與 repo 一致)。
      artist         : 藝術家同件資訊(nv/hull,作頂點預算與基準)。
    """
    import numpy as np
    G, W, _, _ = _wire_repo_tools()
    g = G.generate_for_slot(_abs_asset(skeleton), slot, max_area=max_area, topk=topk)

    # 由 pv(weighted bind)重建 setup 世界座標 → bbox 正規化成 uvs(schema 級;真 atlas UV = 使用者端)。
    world0 = W.bone_world_transforms(g["bones"], g["byname"], g["order"], {})
    V = np.asarray(W.skin_vertices(g["pv"], world0, g["bidx_to_name"]), dtype=np.float64)
    mn, mx = V.min(0), V.max(0)
    span = np.maximum(mx - mn, 1e-9)
    uvs = ((V - mn) / span).reshape(-1).tolist()

    # 攤平 weighted vertices:每頂點 [boneCount, (boneIdx, bindX, bindY, weight)*]。
    verts = []
    for entries in g["pv"]:
        verts.append(len(entries))
        for (bidx, bx, by, w) in entries:
            verts.extend([int(bidx), float(bx), float(by), float(w)])

    hull = int(g["artist"]["hull"])        # 三角化保留輸入 hull 邊界於最前 → hull 數 = 藝術家 hull 數
    tris = np.asarray(g["tris"], dtype=np.int32).reshape(-1).tolist()
    att = {
        "type": "mesh", "vertices": verts, "uvs": uvs, "triangles": tris,
        "hull": hull, "width": float(span[0]), "height": float(span[1]), "_weighted": True,
    }
    g["att"] = att
    return g


def weighted_schema_valid(att):
    """Spine **weighted** mesh attachment 的最小 schema 檢查(可機讀)。回傳 (ok, problems[])。

    檢查:type=mesh、weighted 格式(len(vertices)!=len(uvs))、每頂點 boneCount∈[1,4]、
    每頂點權重和≈1(partition of unity)、bone index 合法、hull∈(0,nv]、triangles 合法。"""
    probs = []
    if att.get("type") != "mesh":
        probs.append("type != mesh")
    v, u = att.get("vertices", []), att.get("uvs", [])
    nv = len(u) // 2
    if len(v) == len(u):
        probs.append("期待 weighted(len(vertices)!=len(uvs));本件看似 unweighted")
    # 解析 weighted vertices
    i = 0
    parsed = 0
    while i < len(v):
        bc = int(v[i]); i += 1
        if not (1 <= bc <= 4):
            probs.append("頂點 {} boneCount={} 不在 [1,4]".format(parsed, bc))
        if i + 4 * bc > len(v):
            probs.append("weighted vertices 長度不足(頂點 {})".format(parsed)); break
        wsum = 0.0
        for _ in range(bc):
            bidx = int(v[i]); w = float(v[i + 3]); i += 4
            if bidx < 0:
                probs.append("頂點 {} bone index {} < 0".format(parsed, bidx))
            wsum += w
        if abs(wsum - 1.0) > 1e-4:
            probs.append("頂點 {} 權重和 {:.5f} != 1(partition of unity)".format(parsed, wsum))
        parsed += 1
    if parsed != nv:
        probs.append("解析頂點數 {} != uvs/2 {}".format(parsed, nv))
    if nv < 3:
        probs.append("頂點數 < 3")
    h = att.get("hull", 0)
    if not (0 < h <= nv):
        probs.append("hull={} 不在 (0, nv={}]".format(h, nv))
    tris = att.get("triangles", [])
    if len(tris) == 0 or len(tris) % 3 != 0:
        probs.append("triangles 長度非 3 的倍數或空")
    if tris and (min(tris) < 0 or max(tris) >= nv):
        probs.append("triangle 索引越界 [0,{})".format(nv))
    return (len(probs) == 0, probs)


def weighted_deform_gate(gen, anims=None, amplify=1.0, mutate=None):
    """把生成 weighted mesh 放回**真實動畫**做 Spine 3.8 skinning 變形,量化幾何品質 + 平滑度。

    回傳 dict:
      setup_clean       : setup pose 下幾何乾淨(si=0 / degen=0)。
      self_intersections / triangle_flips : 真實動畫逐幀 worst。
      smoothness        : {edge_cv_increase_max, area_ratio_std, ...}(對照藝術家手感)。
      nv / checker_validated / clean。
    ⚠️ 用 eval_pv(對 Award 真值重現的 skinning),**不用** 未校準合成場;mutate 供負對照。
    """
    _, W, _, _ = _wire_repo_tools()
    pv = gen["pv"]
    if mutate is not None:
        pv = mutate(pv, gen["bidx_to_name"])
    r = W.eval_pv(gen["sk"], gen["bones"], gen["byname"], gen["order"], gen["bidx_to_name"],
                  pv, gen["tris"], gen["mesh_bone_names"], anims=anims, amplify=amplify)
    clean = bool(r["setup"]["clean"]
                 and r["worst"]["self_intersections"] == 0
                 and r["worst"]["triangle_flips"] == 0)
    return {
        "setup_clean": bool(r["setup"]["clean"]),
        "self_intersections": r["worst"]["self_intersections"],
        "triangle_flips": r["worst"]["triangle_flips"],
        "worst": r["worst"],
        "smoothness": r["smoothness"],
        "nv": r["nv"],
        "checker_validated": bool(r["checker_validated"]),
        "clean": clean,
    }


def artist_weighted_gate(skeleton, slot, anims=None):
    """同件藝術家 weighted mesh 過同一道閘(作真值校準:生成過閘應與藝術家一致,非假性過)。"""
    _, W, _, _ = _wire_repo_tools()
    return W.evaluate_weighted_mesh(_abs_asset(skeleton), slot, anims=anims)


def generate_and_gate_weighted(skeleton, slot, max_area=1500.0, topk=4,
                               cv_margin=0.02, ar_std_margin=0.03, nv_mult=1.4, kind="opaque"):
    """件 → 生成 weighted mesh → schema + 真實變形閘 + 平滑度 + 頂點預算,一條龍自驗。

    回傳 dict:mesh(摘要)/ schema / deform_gate / smoothness / budget / overall_pass。
    overall_pass(opaque)= schema 合法 AND setup 乾淨 AND 真實變形 si=0/flip=0 AND
                          平滑度不劣於藝術家+裕度 AND 頂點 ≤ nv_mult×藝術家。
    軟性加成件(kind='soft')= 只驗 schema(si 不列硬閘,additive 視覺無害,藝術家自身即 si>0)。
    """
    gen = generate_weighted_part_mesh(skeleton, slot, max_area=max_area, topk=topk)
    schema_ok, schema_probs = weighted_schema_valid(gen["att"])
    gate = weighted_deform_gate(gen)
    art = artist_weighted_gate(skeleton, slot)

    nv = gate["nv"]
    budget_ok = nv <= art["nv"] * nv_mult
    sm_ok = (gate["smoothness"]["edge_cv_increase_max"]
             <= art["smoothness"]["edge_cv_increase_max"] + cv_margin
             and gate["smoothness"]["area_ratio_std"]
             <= art["smoothness"]["area_ratio_std"] + ar_std_margin)

    if kind == "opaque":
        overall = schema_ok and gate["clean"] and sm_ok and budget_ok
    else:  # soft:只看 schema
        overall = schema_ok
    return {
        "slot": slot, "kind": kind,
        "mesh": {"vertices": nv, "hull": gen["att"]["hull"], "triangles": len(gen["tris"])},
        "schema": {"pass": schema_ok, "problems": schema_probs},
        "deform_gate": {"setup_clean": gate["setup_clean"],
                        "self_intersections": gate["self_intersections"],
                        "triangle_flips": gate["triangle_flips"],
                        "clean": gate["clean"],
                        "checker_validated": gate["checker_validated"]},
        "smoothness": {"gen": gate["smoothness"], "artist": art["smoothness"], "pass": sm_ok},
        "budget": {"gen_nv": nv, "artist_nv": art["nv"], "mult": nv_mult, "pass": budget_ok},
        "artist_worst": art["worst"],
        "overall_pass": bool(overall),
    }


# ===================================================================== 2. rig 自動推斷
def infer_limb_tree(parts, tau_frac=0.06, step=2.0):
    """件世界多邊形 {name: Nx2} → (root_name, {child: parent}, info)。

    確定性接觸距離 Dijkstra:root = 面積最大件(軀幹);父邊 = 以接觸距離為權的最短路徑樹
    (星形→全掛 root;鏈形→recover 鏈,不強制星形)。info 含 degree/tau/scale/D。"""
    _, _, _, it = _wire_repo_tools()
    return it.infer_tree(parts, tau_frac=tau_frac, step=step)


def infer_joint_pivots(parts, tree, q=0.2):
    """父子樹 → {child: 關節 pivot xy}。pivot = child 最靠近 parent 的 q 分位點集合質心
    (= 父子接觸縫;shoulder/neck/hip 皆在此)。root 不推斷。沿軸精修/手感屬美術(A 類)。"""
    import numpy as np
    _, _, ip, _ = _wire_repo_tools()
    raw = ip.infer_pivots(parts, tree, q=q)
    return {c: np.asarray(j, dtype=np.float64) for c, j in raw.items()}


def centroid_pivot_baseline(parts, tree):
    """天真 baseline(用子件質心當 pivot);接觸縫法應顯著勝它。"""
    _, _, ip, _ = _wire_repo_tools()
    return ip.centroid_baseline(parts, tree)


def rig_from_parts(parts, effect_names=None, tau_frac=0.06, step=2.0, q=0.2):
    """一堆拆件世界多邊形 → 完整 rig 草案(排除 effect 件後推 樹 + pivots)。

    effect_names:特效件(如光暈)須由語意分類作輸入排除——否則大面積背光會汙染樹(見負對照)。
    回傳 dict:root / tree / pivots(child→xy)/ info / excluded。"""
    effect_names = set(effect_names or [])
    struct = {k: v for k, v in parts.items() if k not in effect_names}
    root, tree, info = infer_limb_tree(struct, tau_frac=tau_frac, step=step)
    pivots = infer_joint_pivots(struct, tree, q=q)
    return {"root": root, "tree": tree, "pivots": pivots, "info": info,
            "excluded": sorted(effect_names)}


# --------------------------------------------------------------------- loaders / 合成 fixture
def load_award_robot_parts(award_path=AWARD, use_alpha=True):
    """Award 機器人 rig 真值 loader(wraps infer_pivots.load_award_robot)。
    回傳 (parts_world, truth_pivots, tree, fidelity)。use_alpha → region 件用 atlas 真實輪廓。"""
    _, _, ip, _ = _wire_repo_tools()
    return ip.load_award_robot(_abs_asset(award_path), use_alpha=use_alpha)


def award_robot_tree():
    """Award 機器人結構真值樹(child_slot → parent_slot;光暈 effect 不列)。"""
    _, _, ip, _ = _wire_repo_tools()
    return dict(ip.ROBOT_TREE)


def _rect(cx, cy, w, h):
    import numpy as np
    return np.array([[cx - w / 2, cy - h / 2], [cx + w / 2, cy - h / 2],
                     [cx + w / 2, cy + h / 2], [cx - w / 2, cy + h / 2]], dtype=np.float64)


def make_chain_parts():
    """合成多跳肢體鏈 fixture(torso→upper→lower,只鄰接相鄰件)—— 驗 recover 成鏈(非星形)。"""
    return {"torso": _rect(0, 0, 180, 180), "upper": _rect(0, 150, 90, 90),
            "lower": _rect(0, 290, 90, 90)}


def make_star_parts():
    """合成星形 fixture(torso 中心,3 件各方向貼上)—— 驗 recover 成星形。"""
    return {"torso": _rect(0, 0, 120, 120), "a": _rect(0, 130, 80, 80),
            "b": _rect(130, 0, 80, 80), "c": _rect(-130, 0, 80, 80)}


# --------------------------------------------------------------------- 小工具
def _abs_asset(path):
    """相對 'assets/...' 路徑 → repo 根絕對路徑(讓程式化呼叫不綁 cwd)。"""
    if os.path.isabs(path) or os.path.exists(path):
        return path
    cand = os.path.join(_repo_root(), path)
    return cand if os.path.exists(cand) else path


# ===================================================================== 自檢
def _self_test():
    import numpy as np
    out = {"weighted": [], "pivots": {}, "tree": {}}

    # --- weighted mesh:Award 不透明件過真實變形閘;軟件只記錄 ---
    for p in WEIGHTED_DEMO_PARTS:
        rep = generate_and_gate_weighted(p["skeleton"], p["slot"],
                                         max_area=p["max_area"], kind=p["kind"])
        out["weighted"].append(rep)
    w_ok = all(r["overall_pass"] for r in out["weighted"] if r["kind"] == "opaque")

    # --- rig 自動推斷:Award 真值樹 + pivot 準度 ---
    parts, truth, tree, fid = load_award_robot_parts(use_alpha=True)
    struct = {k: v for k, v in parts.items() if k != "機器人拆件/光暈"}
    root, inf_tree, info = infer_limb_tree(struct)
    tree_ok = (inf_tree == award_robot_tree())
    piv = infer_joint_pivots(struct, tree)
    scale = float(np.mean([np.hypot(*(struct[tree[c]].max(0) - struct[tree[c]].min(0)))
                           for c in tree if tree[c] in struct]))
    max_rel = max(float(np.linalg.norm(piv[c] - truth[c])) / scale for c in tree if c in piv)
    piv_ok = max_rel < 0.10
    out["tree"] = {"root": root.split("/")[-1], "match_truth": tree_ok}
    out["pivots"] = {"max_err_rel": round(max_rel, 4), "pass": piv_ok}

    # --- 合成鏈/星形:多跳通用 ---
    rc, tc, _ = infer_limb_tree(make_chain_parts(), tau_frac=0.30)
    chain_ok = (rc == "torso" and tc.get("upper") == "torso" and tc.get("lower") == "upper")
    rs, ts, _ = infer_limb_tree(make_star_parts(), tau_frac=0.30)
    star_ok = (rs == "torso" and all(ts.get(k) == "torso" for k in ("a", "b", "c")))
    out["synthetic"] = {"chain_ok": chain_ok, "star_ok": star_ok}

    out["overall_pass"] = bool(w_ok and tree_ok and piv_ok and chain_ok and star_ok)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weighted", nargs=2, metavar=("SKELETON", "SLOT"),
                    help="生成單件 weighted mesh 並過閘")
    ap.add_argument("--max-area", type=float, default=1500.0)
    ap.add_argument("--self-test", action="store_true",
                    help="對 repo Award rig + 合成鏈/星形自檢")
    a = ap.parse_args()
    if a.self_test:
        rep = _self_test()
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        sys.exit(0 if rep["overall_pass"] else 1)
    if a.weighted:
        rep = generate_and_gate_weighted(a.weighted[0], a.weighted[1], max_area=a.max_area)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        sys.exit(0 if rep["overall_pass"] else 1)
    ap.error("需 --weighted SKELETON SLOT 或 --self-test")


if __name__ == "__main__":
    main()
