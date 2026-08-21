"""weighted_deform — Spine 3.8 weighted-mesh deform evaluator (pure CPU).

補上 S3 唯一未驗維度:**weighted mesh 骨骼變形平滑度**。

之前的 deform_eval 只處理 unweighted mesh(deform timeline 直接位移頂點)。
真實美術 mesh(Award 機器人件)全為 weighted:頂點綁在多根骨、bind 為相對骨座標,
變形由「骨的世界變換」驅動。要量化「我方 BBW 生成 mesh」的變形平滑度,必須先能:

  1. 由 skeleton bones(setup local transform)+ 姿勢覆寫 → 每骨世界變換(FK,normal 模式)
  2. 由 weighted vertices(nb, boneIdx,bindX,bindY,weight ...)→ 變形後世界頂點
  3. 量化平滑度:三角翻面 / 自交 / 面積畸變 / 邊長拉伸離散度

本模組是「評估器先行」— 先對藝術家真值(Award 這幾件 weighted mesh)驗證自一致
(設定姿勢乾淨、合理骨轉下不翻面/不自交),確認評估器可信,才拿來評判生成 mesh。

Spine 3.8 normal-mode local matrix(已核 CLAUDE.md 雷點):
  la = cos(rot+shearX)*scaleX ; lc = sin(rot+shearX)*scaleX
  lb = cos(rot+90+shearY)*scaleY ; ld = sin(rot+90+shearY)*scaleY
  world = parentWorld ∘ local
"""
import json
import math
import numpy as np

from deform_eval import signed_area, _seg_cross, tri_edges  # reuse geometry primitives


# ---------- bone forward kinematics (normal transform mode) ----------
class Bone:
    __slots__ = ("name", "parent", "x", "y", "rot", "sx", "sy", "shx", "shy",
                 "a", "b", "c", "d", "wx", "wy")

    def __init__(self, data):
        self.name = data["name"]
        self.parent = data.get("parent")
        self.x = data.get("x", 0.0)
        self.y = data.get("y", 0.0)
        self.rot = data.get("rotation", 0.0)
        self.sx = data.get("scaleX", 1.0)
        self.sy = data.get("scaleY", 1.0)
        self.shx = data.get("shearX", 0.0)
        self.shy = data.get("shearY", 0.0)


def build_bones(skeleton):
    bones = [Bone(b) for b in skeleton["bones"]]
    idx = {b.name: i for i, b in enumerate(bones)}
    return bones, idx


def update_world(bones, idx, pose=None):
    """Compute world matrices for all bones. pose: {bone_name: {'rotate':deg,'x':dx,'y':dy,
    'scaleX':mul,'scaleY':mul}} additive/multiplicative override on local transform."""
    pose = pose or {}
    for b in bones:
        p = pose.get(b.name, {})
        rot = b.rot + p.get("rotate", 0.0)
        x = b.x + p.get("x", 0.0)
        y = b.y + p.get("y", 0.0)
        sx = b.sx * p.get("scaleX", 1.0)
        sy = b.sy * p.get("scaleY", 1.0)
        rr = math.radians(rot + b.shx)
        ry = math.radians(rot + 90.0 + b.shy)
        la = math.cos(rr) * sx
        lc = math.sin(rr) * sx
        lb = math.cos(ry) * sy
        ld = math.sin(ry) * sy
        if b.parent is None:
            b.a, b.b, b.c, b.d = la, lc, lb, ld
            b.wx, b.wy = x, y
        else:
            pb = bones[idx[b.parent]]
            b.a = pb.a * la + pb.c * lc
            b.c = pb.a * lb + pb.c * ld
            b.b = pb.b * la + pb.d * lc
            b.d = pb.b * lb + pb.d * ld
            b.wx = pb.a * x + pb.c * y + pb.wx
            b.wy = pb.b * x + pb.d * y + pb.wy
    return bones


# ---------- weighted mesh decode + world vertices ----------
def decode_weighted(attachment):
    """Return (n_vert, per-vertex list of (boneIdx, bindX, bindY, weight), uvs, triangles, hull)."""
    verts = attachment["vertices"]
    uvs = attachment["uvs"]
    flat = attachment["triangles"]
    tris = [tuple(flat[i:i + 3]) for i in range(0, len(flat), 3)]
    n = len(uvs) // 2
    weighted = len(verts) != len(uvs)
    per = []
    if weighted:
        i = 0
        while i < len(verts):
            nb = int(verts[i]); i += 1
            entry = []
            for _ in range(nb):
                bi = int(verts[i]); bx = verts[i + 1]; by = verts[i + 2]; w = verts[i + 3]
                i += 4
                entry.append((bi, bx, by, w))
            per.append(entry)
    else:
        # unweighted: treat as bound to a single implicit bone (root) — not used here
        per = None
    return n, per, uvs, tris, weighted


def world_vertices(bones, per):
    """Deformed world vertices from weighted binding + current bone world matrices."""
    out = np.zeros((len(per), 2))
    for vi, entry in enumerate(per):
        px = py = 0.0
        for bi, bx, by, w in entry:
            b = bones[bi]
            px += (b.a * bx + b.c * by + b.wx) * w
            py += (b.b * bx + b.d * by + b.wy) * w
        out[vi] = (px, py)
    return out


# ---------- smoothness metrics ----------
def setup_signs(verts, tris):
    return [signed_area(verts, t) > 0 for t in tris]


def edge_stretch(verts0, verts1, edges):
    """Per-edge length ratio (deformed/setup); returns (max, cv=std/mean) as smoothness signature.
    Low CV = deformation spread smoothly across edges; high CV = localized kink/pinch."""
    r = []
    for a, b in edges:
        l0 = np.hypot(*(verts0[a] - verts0[b]))
        l1 = np.hypot(*(verts1[a] - verts1[b]))
        if l0 > 1e-6:
            r.append(l1 / l0)
    r = np.array(r)
    return float(r.max()), float(r.std() / r.mean()) if len(r) else 0.0


def check_pose(verts, tris, signs0, area0, edges, verts0):
    flips = degen = 0
    for i, t in enumerate(tris):
        a = signed_area(verts, t)
        if abs(a) < 1e-6:
            degen += 1
        elif (a > 0) != signs0[i]:
            flips += 1
    xs = 0
    for i in range(len(edges)):
        e1 = edges[i]
        for j in range(i + 1, len(edges)):
            e2 = edges[j]
            if e1[0] in e2 or e1[1] in e2:
                continue
            if _seg_cross(verts[e1[0]], verts[e1[1]], verts[e2[0]], verts[e2[1]]):
                xs += 1
    area = sum(abs(signed_area(verts, t)) for t in tris)
    mxs, cv = edge_stretch(verts0, verts, edges)
    return {
        "self_intersections": xs, "triangle_flips": flips, "degenerate": degen,
        "area_ratio": round(area / area0, 3) if area0 else 0.0,
        "max_edge_stretch": round(mxs, 3), "stretch_cv": round(cv, 4),
        "clean": xs == 0 and flips == 0 and degen == 0,
    }


# ---------- attachment lookup ----------
def find_attachment(skeleton, slot_name):
    skins = skeleton["skins"]
    items = skins.items() if isinstance(skins, dict) else \
        ((s.get("name"), s.get("attachments", {})) for s in skins)
    for _, att in items:
        if slot_name in att:
            for an, a in att[slot_name].items():
                if a.get("type") == "mesh":
                    return an, a
    return None, None


def load_case(path, slot_name):
    sk = json.load(open(path))
    bones, idx = build_bones(sk)
    an, att = find_attachment(sk, slot_name)
    if att is None:
        raise ValueError(f"no mesh attachment on slot {slot_name}")
    n, per, uvs, tris, weighted = decode_weighted(att)
    return sk, bones, idx, an, per, np.array(uvs).reshape(-1, 2), tris, weighted


def driver_bones(per):
    """Bone indices this mesh is actually weighted to (sorted by total weight, desc)."""
    tot = {}
    for entry in per:
        for bi, _, _, w in entry:
            tot[bi] = tot.get(bi, 0.0) + w
    return sorted(tot, key=lambda k: -tot[k])
