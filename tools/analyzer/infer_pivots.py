#!/usr/bin/env python3
"""S5 —— bone pivot(關節樞紐)推斷 baseline(純 CPU,確定性)。

給 `pivot_eval.py`(骨架閘)一個「真的要被打分」的對象。目標問題:在**不知道真 pivot**
的前提下,只用「骨的連接拓樸 + 各骨的幾何(方向/長度)」推斷每個關節該放哪。

本檔提供兩個 rig-only baseline(都只吃 parent 骨的幾何、不偷看子骨真 pivot):

  1. parent_tip  —— 「關節端對端相接」假設:子骨 pivot = parent 骨的尖端
     (parent world 套用 (parent.length, 0))。這是 rigging 最常見的直覺:
     前臂的關節在上臂末端。**對序列骨鏈(serial)成立,對岔出骨(branch)必然失手**
     (岔出子不在 parent 軸尖端)。
  2. parent_origin —— 退化對照:子骨 pivot = parent 骨原點。故意很弱,用來確認
     閘能分出「好啟發式 vs 爛啟發式」。

parent 無 length 時 tip 退回 parent 原點(等同 parent_origin)。

## 誠實界定

這是**只靠骨鏈幾何**的 baseline;branch 關節要放對,需要「件的像素footprint / 相鄰件
重疊區」這類影像證據(見 STATE 下一步:overlap-centroid 需要 per-part mask)。本 baseline
的價值在於:量化「最簡確定性啟發式能到哪」,並用閘精準指出它在哪類關節失手 → 指引 S5 下一步。
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
from weighted_deform_eval import load_skeleton, bone_world_transforms, transform_point


def _world_and_meta(sk):
    bones = sk["bones"]
    byname = {b["name"]: b for b in bones}
    order = [b["name"] for b in bones]
    world = bone_world_transforms(bones, byname, order, {})
    return bones, byname, order, world


def infer_parent_tip(sk):
    """子骨 pivot = parent 骨尖端(parent 無 length → 退回 parent 原點)。"""
    _, byname, order, world = _world_and_meta(sk)
    out = {}
    for n in order:
        p = byname[n].get("parent")
        if not p:
            continue
        pw = world[p]
        pL = byname[p].get("length") or 0.0
        out[n] = transform_point(pw, pL, 0.0)  # (length,0) 在 parent 局部 = 尖端
    return out


def infer_parent_origin(sk):
    """退化對照:子骨 pivot = parent 骨原點。"""
    _, byname, order, world = _world_and_meta(sk)
    out = {}
    for n in order:
        p = byname[n].get("parent")
        if not p:
            continue
        pw = world[p]
        out[n] = (pw[4], pw[5])
    return out


BASELINES = {
    "parent_tip": infer_parent_tip,
    "parent_origin": infer_parent_origin,
}


if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    which = sys.argv[2] if len(sys.argv) > 2 else "parent_tip"
    sk, *_ = load_skeleton(path)
    pv = BASELINES[which](sk)
    print(f"# {which} predicted pivots for {path} ({len(pv)} bones)")
    for n in list(pv)[:12]:
        print(f"  {n:10s} -> ({pv[n][0]:.1f}, {pv[n][1]:.1f})")
