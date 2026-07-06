#!/usr/bin/env python3
"""S3 evaluator-driven 自動收斂生成器 —— 用評估器回饋自動選 hull 取樣密度。

發現(2026-07-06,對 Award 3 個真實 mesh 件驗):**固定 epsilon 不通用** —— 覆蓋率 IoU
由 hull 邊界取樣密度決定,而「達到藝術家 IoU 所需的密度是形狀相依的」。光暈需 eps≈0.002、
身體/左手 eps≈0.004 即可。單一預設值必然對某些件過疏(cover 不足)或過密(超頂點預算)。

解法(RULES 的「評估器即自主收斂閘」):給定 target_iou(藝術家基準)與 vertex budget,
從粗到細掃 epsilon,回傳**第一個** IoU≥target 的 mesh(最精簡即停);全程受 budget 上限約束。
附 orphan-pruning:過濾三角後移除未被使用的頂點並重編索引 → 保證 AC-topo(0 孤兒)。

這把 generate_mesh(v1)+ evaluate_mesh 串成自我收斂迴圈,不改動 v1 本體(既有 4-mesh 驗證不受影響)。
"""
import argparse, json, os, sys
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
import generate_mesh as g1
from evaluate_mesh import evaluate, load_mask

# 粗→細:先試最精簡,不夠再加密
EPS_LADDER = [0.008, 0.006, 0.004, 0.003, 0.002, 0.0015, 0.001]


def prune_orphans(mesh):
    """移除未被任何三角使用的頂點,重編 triangles/hull(hull 頂點永遠被使用,故 hull 計數不變)。"""
    nv = len(mesh["uvs"]) // 2
    tris = np.array(mesh["triangles"], dtype=np.int32).reshape(-1, 3) if mesh["triangles"] else np.zeros((0, 3), int)
    used = sorted(set(int(i) for i in tris.flatten())) if tris.size else []
    if len(used) == nv:
        return mesh
    remap = {old: new for new, old in enumerate(used)}
    verts, uvs = mesh["vertices"], mesh["uvs"]
    new_verts, new_uvs = [], []
    for old in used:
        new_verts += [verts[2 * old], verts[2 * old + 1]]
        new_uvs += [uvs[2 * old], uvs[2 * old + 1]]
    # orphan 只可能是 interior(hull 一定連到相鄰 hull 三角);hull 頂點 index < hull 且都被用到 → 保序
    new_tris = [remap[int(i)] for t in tris for i in t]
    hull = sum(1 for old in used if old < mesh["hull"])
    out = dict(mesh)
    out.update({"vertices": new_verts, "uvs": new_uvs, "triangles": new_tris, "hull": hull})
    return out


def generate_auto(path, target_iou=0.95, budget=64, min_dist=10, max_interior=40, verbose=False):
    """掃 epsilon 找到達 target_iou 的最精簡 mesh(受 budget 約束);回傳 (mesh, trace)。"""
    mask = load_mask(path)
    best = None            # 最佳「已達標且在預算內」
    best_over = None       # 後備:達標但超預算中最精簡的
    trace = []
    for eps in EPS_LADDER:
        mesh, _ = g1.generate(path, max_interior=max_interior, epsilon_frac=eps, min_dist=min_dist)
        mesh = prune_orphans(mesh)
        ev = evaluate(mesh, mask, vertex_budget=budget, iou_thresh=target_iou)
        nv, iou = ev["vertices"], ev["criteria"]["AC1_iou"]["value"]
        trace.append({"eps": eps, "v": nv, "iou": round(iou, 4)})
        if verbose:
            print(f"  eps={eps} v={nv} iou={iou:.4f}")
        if iou >= target_iou:
            if nv <= budget:
                mesh["_tune"] = {"eps": eps, "target_iou": target_iou, "budget": budget}
                return mesh, trace          # 最粗即達標且在預算 → 停(最精簡)
            if best_over is None:
                best_over = mesh; best_over["_tune"] = {"eps": eps, "over_budget": True}
    # 沒有「達標且在預算內」→ 回傳達標但超預算的最精簡者,或最後一個(盡力覆蓋)
    if best_over is not None:
        return best_over, trace
    mesh["_tune"] = {"eps": EPS_LADDER[-1], "target_not_met": True}
    return mesh, trace


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--target-iou", type=float, default=0.95)
    ap.add_argument("--budget", type=int, default=64)
    ap.add_argument("--min-dist", type=float, default=10)
    a = ap.parse_args()
    mesh, trace = generate_auto(a.image, a.target_iou, a.budget, a.min_dist, verbose=True)
    out = a.out or (a.image.rsplit(".", 1)[0] + "_mesh_auto.json")
    json.dump(mesh, open(out, "w"), ensure_ascii=False)
    nv = len(mesh["uvs"]) // 2
    print(f"{out}: v={nv} hull={mesh['hull']} tri={len(mesh['triangles'])//3} tune={mesh.get('_tune')}")


if __name__ == "__main__":
    main()
