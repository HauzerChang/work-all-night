#!/usr/bin/env python3
"""Spine 3.8 骨骼世界變換 + weighted-mesh 蒙皮(skinning)。

補上 deform_eval.py 沒涵蓋的維度:**weighted mesh 靠骨骼變形**(非 deform timeline)。
Award 機器人 3 個 mesh 件(光暈/左手/身體)皆 weighted、無 deform timeline,
它們的「藝術家意圖變形」= 對綁定骨施加 pose → 用美術權重蒙皮。這支模組重現該過程,
讓我們能把「任一 pose 下的變形結果」當量化真值,評估生成 mesh 的變形品質。

Spine 3.8 Bone.updateWorldTransform(TransformMode.normal,無 shear/skeleton scale):
  rot  = rotation(deg);  rotY = rotation + 90
  la = cos(rot)*sx      lb = cos(rotY)*sy
  lc = sin(rot)*sx      ld = sin(rotY)*sy      (local 2x2)
  world = parent.world ∘ (translate(x,y) ∘ local)
  worldX = pa*x + pb*y + p.worldX ;  worldY = pc*x + pd*y + p.worldY
  a = pa*la+pb*lc ; b = pa*lb+pb*ld ; c = pc*la+pd*lc ; d = pc*lb+pd*ld
root: a=1,b=0,c=0,d=1,worldX=x,worldY=y。

weighted vertex world:  P = Σ_bones w * (bone.a*bx + bone.b*by + bone.worldX,
                                         bone.c*bx + bone.d*by + bone.worldY)
其中 (bx,by)=bind(該骨 local 座標)、w=權重(每頂點 Σw=1)。

座標系:Spine 為 y-up。本模組全程 y-up(不翻)。
"""
import json, math
import numpy as np


def load_skeleton(path):
    sk = json.load(open(path))
    bones = sk["bones"]
    name2idx = {b["name"]: i for i, b in enumerate(bones)}
    return sk, bones, name2idx


def rest_pose(bones):
    """回傳每骨的 rest 參數 dict(補預設)。"""
    out = []
    for b in bones:
        out.append({
            "name": b["name"],
            "parent": b.get("parent"),
            "x": b.get("x", 0.0), "y": b.get("y", 0.0),
            "rotation": b.get("rotation", 0.0),
            "scaleX": b.get("scaleX", 1.0), "scaleY": b.get("scaleY", 1.0),
        })
    return out


def compute_world(bones, name2idx, overrides=None):
    """計算所有骨的世界變換。overrides: {bone_name: {'rotation': +delta 或絕對值? }}。
    這裡採**疊加**語意:overrides[name] 的 key 會『加到 rest 值上』(delta),
    以便 pose = rest + Δrotation。回傳 list of dict(a,b,c,d,worldX,worldY)。"""
    overrides = overrides or {}
    rest = rest_pose(bones)
    world = [None] * len(bones)

    def solve(i):
        if world[i] is not None:
            return world[i]
        r = rest[i]
        ov = overrides.get(r["name"], {})
        rot = r["rotation"] + ov.get("rotation", 0.0)
        sx = r["scaleX"] * ov.get("scaleX", 1.0)
        sy = r["scaleY"] * ov.get("scaleY", 1.0)
        x = r["x"] + ov.get("x", 0.0)
        y = r["y"] + ov.get("y", 0.0)
        rr = math.radians(rot); ry = math.radians(rot + 90.0)
        la = math.cos(rr) * sx; lb = math.cos(ry) * sy
        lc = math.sin(rr) * sx; ld = math.sin(ry) * sy
        p = r["parent"]
        if p is None:
            w = {"a": la, "b": lb, "c": lc, "d": ld, "worldX": x, "worldY": y}
        else:
            pw = solve(name2idx[p])
            pa, pb, pc, pd = pw["a"], pw["b"], pw["c"], pw["d"]
            worldX = pa * x + pb * y + pw["worldX"]
            worldY = pc * x + pd * y + pw["worldY"]
            w = {"a": pa * la + pb * lc, "b": pa * lb + pb * ld,
                 "c": pc * la + pd * lc, "d": pc * lb + pd * ld,
                 "worldX": worldX, "worldY": worldY}
        world[i] = w
        return w

    for i in range(len(bones)):
        solve(i)
    return world


def parse_weighted(att):
    """解析 weighted mesh 的 vertices → 每頂點 [(boneIdx,bx,by,w), ...]。
    回傳 (per_vertex_bindings, nv)。若為 unweighted 則 per_vertex_bindings=None。"""
    verts = att["vertices"]; uvs = att["uvs"]
    if len(verts) == len(uvs):
        return None, len(uvs) // 2
    bind = []
    i = 0
    while i < len(verts):
        bc = int(verts[i]); i += 1
        entry = []
        for _ in range(bc):
            bi = int(verts[i]); bx = verts[i + 1]; by = verts[i + 2]; w = verts[i + 3]
            entry.append((bi, bx, by, w)); i += 4
        bind.append(entry)
    return bind, len(bind)


def skin_vertices(world, bind):
    """用世界變換 + 綁定,算出每頂點世界座標 (nv,2)。"""
    out = np.zeros((len(bind), 2), np.float64)
    for vi, entry in enumerate(bind):
        px = py = 0.0
        for (bi, bx, by, w) in entry:
            b = world[bi]
            px += w * (b["a"] * bx + b["b"] * by + b["worldX"])
            py += w * (b["c"] * bx + b["d"] * by + b["worldY"])
        out[vi] = (px, py)
    return out


def get_attachment(sk, slot, name=None):
    skin = sk["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    name = name or slot
    return atts[slot][name]


def setup_world_vertices(sk, bones, name2idx, slot, name=None):
    """weighted mesh 在 setup pose 的世界座標(無 override)。"""
    att = get_attachment(sk, slot, name)
    bind, nv = parse_weighted(att)
    world = compute_world(bones, name2idx)
    if bind is None:
        # unweighted:vertices 已是 local,需 slot bone 變換;此模組聚焦 weighted。
        raise ValueError("unweighted mesh not supported here")
    return skin_vertices(world, bind), att


def deform_world_vertices(sk, bones, name2idx, slot, overrides, name=None):
    """對綁定骨施加 overrides(delta)後的世界座標。"""
    att = get_attachment(sk, slot, name)
    bind, nv = parse_weighted(att)
    world = compute_world(bones, name2idx, overrides)
    return skin_vertices(world, bind), att


def mesh_bones(att):
    """回傳此 weighted mesh 綁定到的骨 index 集合(排序)。"""
    bind, _ = parse_weighted(att)
    if bind is None:
        return []
    s = set()
    for entry in bind:
        for (bi, *_r) in entry:
            s.add(bi)
    return sorted(s)


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    sk, bones, n2i = load_skeleton(path)
    for slot in ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]:
        sv, att = setup_world_vertices(sk, bones, n2i, slot)
        mb = mesh_bones(att)
        print(slot, "nv", len(sv), "bones", [bones[i]["name"] for i in mb],
              "bbox", np.round(sv.min(0), 1).tolist(), np.round(sv.max(0), 1).tolist())
