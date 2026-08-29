"""S5 (b) — 把「推斷出的關節 pivot」接成 Spine 骨骼父子鏈。

問題:`build_spine.py` 目前把每個件的骨 **各自綁 root**、擺在件的影像中心。
      這樣「轉某肢」= 繞該件自己的中心自轉 → 頭會原地打轉、脫離身體。
      真正的 rig 需要:子件骨 **座落在關節 pivot**、並 **parent 到父件骨**;
      如此「轉子件骨」= 繞關節旋轉(頭繞脖子、手繞肩膀),才是對的關節行為。

本模組(確定性、純 CPU,無瀏覽器)提供:
  build_bone_chain(parts_world, tree, pivots)
      → (bones, part_bone, part_local):Spine 3.8 bones 陣列(x,y 為相對父骨的局部座標)、
        件→骨名對映、件→局部多邊形(setup 下 = 世界點 − 該骨原點)。
      setup 全骨 rotation=0 scale=1,故局部合成回世界 == 原世界(round-trip 天然成立)。
  part_world(part, pose)
      → 給定姿勢(pose[bone]=rotation 角度,或完整 (x,y,rot,sx,sy) 覆寫),
        回傳該件變形後的世界點雲(透過骨鏈合成)。

座標/語意與 weighted_deform_eval 一致(重用其骨世界變換,確保與真實 Spine 3.8 對齊)。
"""
import sys, os
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
import weighted_deform_eval as wde  # noqa: E402


def _roots(parts, tree):
    """回傳「結構根件」:不在 tree 當 child,或其 parent 不在 parts 者。"""
    return [p for p in parts if (p not in tree) or (tree.get(p) not in parts)]


def build_bone_chain(parts_world, tree, pivots, root_name="root"):
    """parts_world: {part: Nx2 世界多邊形};tree: {child_part: parent_part};
       pivots: {child_part: (x,y) 世界關節位置}(root 件無 pivot)。

    回傳 (bones, part_bone, part_local):
      bones      —— Spine 3.8 bones 陣列(含 root);child 骨 x,y 為 **相對父骨局部座標**。
      part_bone  —— {part: bone_name}。
      part_local —— {part: Nx2 局部多邊形}(= 世界點 − 該件骨的世界原點;setup rotation=0)。
    """
    # 骨的世界原點:根件 = 其質心;子件 = 其關節 pivot。
    bone_world_origin = {}
    for p in _roots(parts_world, tree):
        bone_world_origin[p] = np.asarray(parts_world[p]).reshape(-1, 2).mean(0)
    for c in tree:
        if c in parts_world and tree.get(c) in parts_world:
            if c not in pivots:
                raise ValueError(f"child part {c} 缺 pivot")
            bone_world_origin[c] = np.asarray(pivots[c], dtype=np.float64)

    part_bone = {p: f"b_{_safe(p)}" for p in parts_world}

    # 依「父先於子」拓樸排序輸出 bones(Spine 要求 parent 在前)。
    bones = [{"name": root_name}]
    emitted = set()

    def parent_bone_of(p):
        par_part = tree.get(p)
        if par_part in parts_world:
            return part_bone[par_part], bone_world_origin[par_part]
        return root_name, np.zeros(2)  # 掛 spine root(原點)

    def emit(p):
        if p in emitted:
            return
        par_part = tree.get(p)
        if par_part in parts_world and par_part not in emitted:
            emit(par_part)                       # 先出父件
        pb_name, pb_world = parent_bone_of(p)
        loc = bone_world_origin[p] - pb_world    # setup 下父骨 rotation=0 → 局部=世界差
        bones.append({"name": part_bone[p], "parent": pb_name,
                      "x": round(float(loc[0]), 3), "y": round(float(loc[1]), 3)})
        emitted.add(p)

    for p in parts_world:
        emit(p)

    part_local = {p: np.asarray(parts_world[p]).reshape(-1, 2) - bone_world_origin[p]
                  for p in parts_world}
    return bones, part_bone, part_local


def _safe(name):
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


def _byorder(bones):
    byname = {b["name"]: b for b in bones}
    order = [b["name"] for b in bones]
    return byname, order


def part_world(part, bones, part_bone, part_local, pose=None):
    """回傳該件在 pose 下的世界點雲。
    pose: {bone_name: rot_deg}(只轉),或 {bone_name: (x,y,rot,sx,sy)}(完整覆寫)。"""
    byname, order = _byorder(bones)
    local_pose = {}
    for bn, v in (pose or {}).items():
        if np.isscalar(v):
            b = byname[bn]
            local_pose[bn] = (b.get("x", 0.0), b.get("y", 0.0), float(v),
                              b.get("scaleX", 1.0), b.get("scaleY", 1.0))
        else:
            local_pose[bn] = tuple(v)
    world = wde.bone_world_transforms(bones, byname, order, local_pose)
    w = world[part_bone[part]]
    loc = part_local[part]
    return np.array([wde.transform_point(w, px, py) for px, py in loc])


def fixed_point_of_rotation(before, after):
    """給同一件旋轉前/後的世界點雲(剛體旋轉),解出旋轉不動點(關節)。
    剛體:after = R(before - f) + f  →  對每點成立 → 最小平方解 f。"""
    B = np.asarray(before, float); A = np.asarray(after, float)
    cB, cA = B.mean(0), A.mean(0)
    Bc, Ac = B - cB, A - cA
    Hs = Bc.T @ Ac
    U, _, Vt = np.linalg.svd(Hs)
    R = (Vt.T @ U.T)
    if np.linalg.det(R) < 0:               # 反射修正
        Vt[-1] *= -1; R = Vt.T @ U.T
    # after = R(before) + t,t = cA - R cB;不動點 f: f = R f + t → (I-R) f = t
    t = cA - R @ cB
    return np.linalg.solve(np.eye(2) - R, t)
