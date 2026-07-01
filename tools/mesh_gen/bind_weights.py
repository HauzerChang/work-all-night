#!/usr/bin/env python3
"""S5(可自動)— mesh 權重綁定:把 rig 骨架的 unweighted mesh 轉成 Spine weighted mesh。

技術判斷(誠實):真正的 **BBW**(Bounded Biharmonic Weights)是給「單一連續 mesh 橫跨多根骨」
做平滑混合。本資產是**各件獨立 mesh、各掛自己的骨**(左手 mesh 全屬左手骨),關節活動由骨架階層
負責 → 正確且穩健的綁定是 **rigid(每頂點權重 1 給自己件的骨)**。故:

  mode=rigid(預設,對 part-based rig 正確):每頂點 → 自身件骨,weight 1。
  mode=blend(選用,給連續 mesh):inverse-distance² 到「自身+相鄰(父/子)骨」正規化 → 平滑接縫。
    ⚠️ 這是 inverse-distance 近似,非完整 FEM BBW;對獨立件會讓件跨骨牽連,通常不需要。

rig_draft 之後 mesh 頂點已在**骨-local**(相對 bone 原點=pivot);weighted bind 座標即「頂點在該骨
setup 局部座標」= 頂點世界 − 該骨世界原點(setup 無旋轉)。

Spine weighted 格式:vertices = [boneCount,(boneIdx,bindX,bindY,weight)*count, ...]。
自驗:① evaluate_skeleton AC3(權重和=1、bone 索引合法)② 變形測試(轉某骨→該件繞 pivot 轉、
其他件不動、θ=0 版面保真)。
"""
import argparse, json, os, sys, math
import numpy as np
sys.path.insert(0, os.path.dirname(__file__))
from evaluate_skeleton import evaluate_skeleton


def bone_index(skel):
    return {b["name"]: i for i, b in enumerate(skel["bones"])}


def bone_world_origins(skel, extra_rot=None):
    """回傳 {bone: (2x2 R, tx, ty)} 世界仿射(setup 平移鏈;extra_rot 加某骨旋轉(度))。"""
    extra_rot = extra_rot or {}
    bm = {b["name"]: b for b in skel["bones"]}
    cache = {}

    def world(name):
        if name in cache:
            return cache[name]
        b = bm[name]
        rot = math.radians(b.get("rotation", 0.0) + extra_rot.get(name, 0.0))
        c, s = math.cos(rot), math.sin(rot)
        Rl = np.array([[c, -s], [s, c]])
        t = np.array([b.get("x", 0.0), b.get("y", 0.0)])
        p = b.get("parent")
        if p is None:
            R, T = Rl, t
        else:
            Rp, Tp = world(p)
            R = Rp @ Rl
            T = Rp @ t + Tp
        cache[name] = (R, T)
        return cache[name]

    for b in skel["bones"]:
        world(b["name"])
    return cache


def to_weighted(skel, mode="rigid", k=3):
    bidx = bone_index(skel)
    worlds = bone_world_origins(skel)                      # setup 世界原點(平移)
    origin = {n: worlds[n][1] for n in bidx}               # translation part
    slot_bone = {s["name"]: s["bone"] for s in skel["slots"]}
    skin = skel["skins"][0]["attachments"]

    # 相鄰骨(自身+父+子),供 blend
    children = {}
    for b in skel["bones"]:
        p = b.get("parent")
        if p:
            children.setdefault(p, []).append(b["name"])

    converted = 0
    for slot, names in skin.items():
        for name, a in names.items():
            if a.get("type") != "mesh":
                continue
            if len(a["vertices"]) != len(a["uvs"]):
                continue                                   # 已 weighted,略過
            own = slot_bone[slot]
            v = a["vertices"]
            nv = len(v) // 2
            own_o = origin[own]
            new = []
            for i in range(nv):
                lx, ly = v[2 * i], v[2 * i + 1]            # 骨-local(相對 own 原點)
                wx, wy = own_o[0] + lx, own_o[1] + ly      # 世界
                if mode == "rigid":
                    new += [1, bidx[own], round(lx, 3), round(ly, 3), 1.0]
                else:
                    cand = set([own])
                    pb = next((bb.get("parent") for bb in skel["bones"] if bb["name"] == own), None)
                    if pb and pb != "root":
                        cand.add(pb)
                    for ch in children.get(own, []):
                        cand.add(ch)
                    cand = list(cand)
                    ws = []
                    for b in cand:
                        d2 = (wx - origin[b][0]) ** 2 + (wy - origin[b][1]) ** 2
                        ws.append(1.0 / (d2 + 1.0))
                    order = np.argsort(ws)[::-1][:k]
                    tot = sum(ws[j] for j in order)
                    new.append(len(order))
                    for j in order:
                        b = cand[j]; bx, by = wx - origin[b][0], wy - origin[b][1]
                        new += [bidx[b], round(bx, 3), round(by, 3), round(ws[j] / tot, 5)]
            a["vertices"] = new
            converted += 1
    return converted


def skin_world_vertices(skel, slot, name, extra_rot=None):
    """依 weighted 綁定 + 骨世界仿射,算該 mesh 的世界頂點(供變形測試)。"""
    worlds = bone_world_origins(skel, extra_rot)
    Ws = [worlds[b["name"]] for b in skel["bones"]]
    a = skel["skins"][0]["attachments"][slot][name]
    v = a["vertices"]; out = []
    i = 0
    while i < len(v):
        c = int(v[i]); i += 1
        px = py = 0.0
        for _ in range(c):
            bi = int(v[i]); bx = v[i + 1]; by = v[i + 2]; w = v[i + 3]; i += 4
            R, T = Ws[bi]
            p = R @ np.array([bx, by]) + T
            px += w * p[0]; py += w * p[1]
        out.append((px, py))
    return np.array(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("rig_skeleton", help="rig_draft 產出的 skeleton JSON(unweighted mesh)")
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--mode", choices=["rigid", "blend"], default="rigid")
    ap.add_argument("--test-bone", default=None, help="變形測試:要旋轉的骨名(預設取第一個 mesh 件骨)")
    a = ap.parse_args()

    skel = json.load(open(a.rig_skeleton))
    # 綁定前記錄各 mesh 世界頂點(rest)供保真比對
    rest = {}
    for slot, names in skel["skins"][0]["attachments"].items():
        for name, at in names.items():
            if at.get("type") == "mesh" and len(at["vertices"]) == len(at["uvs"]):
                o = bone_world_origins(skel)[[s["bone"] for s in skel["slots"] if s["name"] == slot][0]][1]
                vv = at["vertices"]
                rest[slot] = np.array([[o[0] + vv[2 * i], o[1] + vv[2 * i + 1]] for i in range(len(vv) // 2)])

    n = to_weighted(skel, a.mode)
    out = a.out or (a.rig_skeleton.rsplit(".", 1)[0] + "_weighted.json")
    json.dump(skel, open(out, "w"), ensure_ascii=False, indent=1)

    ev = evaluate_skeleton(skel)
    # 變形測試:test_slot 必須是「綁在 test_bone 上」的 mesh(否則測到不相干件)
    mesh_slots = [s for s in rest]
    slot_bone = {s["name"]: s["bone"] for s in skel["slots"]}
    if a.test_bone:
        test_bone = a.test_bone
        cand = [s for s in mesh_slots if slot_bone[s] == test_bone]
        if not cand:
            raise SystemExit(f"--test-bone {test_bone} 沒有對應的 mesh slot;mesh slots: {mesh_slots}")
        test_slot = cand[0]
    else:
        test_slot = mesh_slots[0]
        test_bone = slot_bone[test_slot]
    rest0 = skin_world_vertices(skel, test_slot, test_slot)                   # θ=0
    preserve = float(np.abs(rest0 - rest[test_slot]).max())
    rot = skin_world_vertices(skel, test_slot, test_slot, {test_bone: 90.0})  # 轉 90°
    # 該件應繞 pivot(=該骨世界原點)旋轉
    pivot = bone_world_origins(skel)[test_bone][1]
    exp = np.array([[pivot[0] - (p[1] - pivot[1]), pivot[1] + (p[0] - pivot[0])] for p in rest0])  # R90
    rot_err = float(np.abs(rot - exp).max())
    # 其他件不受影響
    other = [s for s in mesh_slots if s != test_slot]
    other_moved = 0.0
    for s in other:
        w0 = skin_world_vertices(skel, s, s)
        w1 = skin_world_vertices(skel, s, s, {test_bone: 90.0})
        other_moved = max(other_moved, float(np.abs(w0 - w1).max()))

    report = {
        "mode": a.mode, "meshes_bound": n,
        "AC_weights_valid": ev["criteria"]["AC3_rig_weights"]["pass"],
        "skeleton_summary": ev["summary"],
        "deform_test": {
            "test_bone": test_bone,
            "rest_preserved_px": round(preserve, 4),          # θ=0 應≈0
            "rotate_about_pivot_err_px": round(rot_err, 4),   # 應≈0(繞 pivot 轉)
            "other_parts_moved_px": round(other_moved, 4),    # 應=0(其他件不動)
        },
        "pass": (ev["criteria"]["AC3_rig_weights"]["pass"] and ev["summary"]["mesh_weighted"] == n
                 and preserve < 0.5 and rot_err < 0.5 and other_moved < 0.5),
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"\n寫出 {out}")
    raise SystemExit(0 if report["pass"] else 1)


if __name__ == "__main__":
    main()
