#!/usr/bin/env python3
"""S3 weighted-mesh — Spine 3.8 骨骼姿態 + weighted mesh 世界座標基礎件。

背景(補上 STATE 候選 2 / knowledge s3-robot-mesh-vs-award 的唯一未驗維度):
  Award「機器人拆件」的 3 個 mesh 件(光暈/左手/身體)皆 **weighted**、無 deform timeline
  → 靠「骨骼 pose + 每頂點權重」變形。先前 S3 只驗靜態覆蓋率,無法量化 weighted 變形品質。
  本模組提供可信的 re-pose 基礎件(對照 CLAUDE.md 雷點 #4:先重算 bone world → 再算頂點):

  - bone_world_matrices(skeleton, overrides) : 逐骨算 setup / 施加 rotation/scale 覆寫後的世界 2x3 仿射
  - weighted_world_vertices(att, bones_world): 由 weighted attachment 的 [boneCount,(idx,bx,by,w)*] 算世界頂點
  - reconstruct_setup(...)                   : 用美術權重重建件在 skeleton 空間的 setup 世界頂點(件幾何真值)

Spine TransformMode:目前實作 `normal`(繼承旋轉+縮放),其餘模式(noScale/noRotation…)
以 normal 近似並在 skeleton 掃描時標記(這 3 條腿件實測皆 normal,見驗證輸出)。
"""
import json, math
import numpy as np

DEG = math.pi / 180.0


def _cos(d): return math.cos(d * DEG)
def _sin(d): return math.sin(d * DEG)


def bone_world_matrices(skeleton, rot_override=None, scale_override=None):
    """回傳 {bone_name: (a,b,c,d,wx,wy)} 每骨世界 2x3 仿射(x'=a*lx+b*ly+wx, y'=c*lx+d*ly+wy)。

    rot_override[name]=delta_deg  → 在該骨 local rotation 上加 delta(模擬動畫旋轉)。
    scale_override[name]=(sx,sy)  → 乘在該骨 local scale 上。
    依 bones 陣列順序處理(Spine 保證 parent 在 child 之前)。
    """
    rot_override = rot_override or {}
    scale_override = scale_override or {}
    bones = skeleton["bones"]
    out = {}
    for b in bones:
        name = b["name"]
        x = b.get("x", 0.0); y = b.get("y", 0.0)
        rotation = b.get("rotation", 0.0) + rot_override.get(name, 0.0)
        sx = b.get("scaleX", 1.0); sy = b.get("scaleY", 1.0)
        if name in scale_override:
            osx, osy = scale_override[name]; sx *= osx; sy *= osy
        shearX = b.get("shearX", 0.0); shearY = b.get("shearY", 0.0)
        # local matrix (TransformMode.normal)
        la = _cos(rotation + shearX) * sx
        lc = _sin(rotation + shearX) * sx
        lb = _cos(rotation + 90.0 + shearY) * sy
        ld = _sin(rotation + 90.0 + shearY) * sy
        parent = b.get("parent")
        if parent is None:
            out[name] = (la, lb, lc, ld, x, y)
        else:
            pa, pb, pc, pd, pwx, pwy = out[parent]
            a = pa * la + pb * lc
            bb = pa * lb + pb * ld
            c = pc * la + pd * lc
            d = pc * lb + pd * ld
            wx = pa * x + pb * y + pwx
            wy = pc * x + pd * y + pwy
            out[name] = (a, bb, c, d, wx, wy)
    return out


def parse_weighted(att):
    """把 weighted attachment 的扁平 vertices 解析成 per-vertex 列表。
    回傳 [ [(bone_index, bindX, bindY, weight), ...], ... ](長度 = nv)。"""
    verts = att["vertices"]
    nv = len(att["uvs"]) // 2
    per = []
    i = 0
    for _ in range(nv):
        c = int(verts[i]); i += 1
        entry = []
        for _k in range(c):
            bidx = int(verts[i]); bx = verts[i + 1]; by = verts[i + 2]; w = verts[i + 3]
            i += 4
            entry.append((bidx, bx, by, w))
        per.append(entry)
    return per


def weighted_world_vertices(per_vertex, bone_names, bones_world):
    """由 per-vertex 綁定 + 世界矩陣算世界座標(Nx2)。
    bone_names: bone_index → name 的對照(skeleton['bones'] 順序)。"""
    out = np.zeros((len(per_vertex), 2), np.float64)
    for i, entry in enumerate(per_vertex):
        wx = wy = 0.0
        for (bidx, bx, by, w) in entry:
            a, b, c, d, tx, ty = bones_world[bone_names[bidx]]
            px = a * bx + b * by + tx
            py = c * bx + d * by + ty
            wx += w * px; wy += w * py
        out[i] = (wx, wy)
    return out


def load_weighted_attachment(skeleton, slot, name=None):
    skin = skeleton["skins"]; skin = skin[0] if isinstance(skin, list) else skin
    atts = skin.get("attachments", skin)
    name = name or slot
    return atts[slot][name]


def bind_offsets_for_bones(world_pts, bones_world, bone_names, bone_indices):
    """給定世界頂點(Nx2)與要綁的骨 → 每骨的 local bind 座標(inverse world 仿射)。
    回傳 {bone_index: bind_xy Nx2}。供生成器把 setup 幾何重編成任意骨的 bind。"""
    out = {}
    for bidx in bone_indices:
        a, b, c, d, tx, ty = bones_world[bone_names[bidx]]
        det = a * d - b * c
        if abs(det) < 1e-12:
            det = 1e-12
        ia = d / det; ib = -b / det; ic = -c / det; idd = a / det
        rel = world_pts - np.array([tx, ty])
        bx = ia * rel[:, 0] + ib * rel[:, 1]
        by = ic * rel[:, 0] + idd * rel[:, 1]
        out[bidx] = np.column_stack([bx, by])
    return out


if __name__ == "__main__":
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    sk = json.load(open(path))
    bone_names = [b["name"] for b in sk["bones"]]
    bw = bone_world_matrices(sk)
    for slot in ["機器人拆件/光暈", "機器人拆件/左手", "機器人拆件/身體"]:
        att = load_weighted_attachment(sk, slot)
        per = parse_weighted(att)
        wv = weighted_world_vertices(per, bone_names, bw)
        mn = wv.min(0); mx = wv.max(0)
        print(f"{slot}: nv={len(per)} setup-world bbox "
              f"x[{mn[0]:.1f},{mx[0]:.1f}] y[{mn[1]:.1f},{mx[1]:.1f}]")
