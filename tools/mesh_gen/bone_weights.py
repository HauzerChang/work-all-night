#!/usr/bin/env python3
"""S3 — weighted mesh 骨綁權重生成器(heat-diffusion / Pinocchio 式,純 CPU)。

補上 STATE 候選 2 的缺口:此前 S3 只驗「靜態覆蓋率 IoU」與 unweighted deform 拓樸,
**weighted mesh 的骨骼變形平滑度(權重品質)從未驗**。本模組提供:

  1. Spine 骨架 FK:由 bones 的 local (x,y,rotation,scale) 前向運動學算出各骨 world 矩陣。
  2. weighted-mesh rest 還原:由 `[nBones, boneIdx, bindX, bindY, weight, ...]` + 骨 world
     還原每頂點在骨架空間的 rest 世界座標(供權重演算法用)。
  3. **heat-diffusion 權重**:在三角網格上解 (L + M·diag(1/d²)) W = M·diag(1/d²) P,
     其中 L 為 cotangent Laplacian、M 為 lumped Voronoi 面積、d 為頂點到最近骨段距離、
     P 為最近骨 indicator。此式**尺度不變**(L 無量綱、M~面積、1/d²~面積⁻¹ → 兩項同量綱),
     故 α=1 無需對真值調參。數學保證 **partition of unity**(∑_b w_b = 1,見 validate)。

參考:Baran & Popović 2007 "Automatic Rigging"(Pinocchio 熱擴散權重)。
真值:`assets/Award.json` 機器人 3 mesh 件的美術權重 + 骨架結構(見 validate_bone_weights.py)。
"""
import json
import math
import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla


# ---------------- Spine FK ----------------
def local_mat(b):
    """單骨 local 3x3 仿射矩陣(transformMode=normal, shear=0)。"""
    rot = math.radians(b.get("rotation", 0.0))
    sx = b.get("scaleX", 1.0)
    sy = b.get("scaleY", 1.0)
    x = b.get("x", 0.0)
    y = b.get("y", 0.0)
    la = math.cos(rot) * sx
    lb = -math.sin(rot) * sy
    lc = math.sin(rot) * sx
    ld = math.cos(rot) * sy
    return np.array([[la, lb, x], [lc, ld, y], [0, 0, 1]], float)


def fk_world(skeleton):
    """回傳 {bone_index: 3x3 world matrix}。"""
    bones = skeleton["bones"]
    byname = {b["name"]: i for i, b in enumerate(bones)}
    world = {}

    def get(i):
        if i in world:
            return world[i]
        b = bones[i]
        m = local_mat(b)
        p = b.get("parent")
        world[i] = (get(byname[p]) @ m) if p else m
        return world[i]

    for i in range(len(bones)):
        get(i)
    return world


def bone_segments(skeleton, ids, world=None):
    """回傳 {bone_id: (origin(2,), tip(2,))} — world 座標。零長骨 tip=origin(視為點)。"""
    if world is None:
        world = fk_world(skeleton)
    bones = skeleton["bones"]
    segs = {}
    for i in ids:
        W = world[i]
        o = np.array([W[0, 2], W[1, 2]], float)
        L = bones[i].get("length", 0.0)
        # local +x 方向的骨尖
        tip = np.array([W[0, 0] * L + W[0, 2], W[1, 0] * L + W[1, 2]], float)
        segs[i] = (o, tip)
    return segs


# ---------------- weighted mesh 解析 / 還原 ----------------
def parse_weighted(att):
    """回傳 (bindings, bone_ids):bindings[i] = [(boneIdx, bindX, bindY, weight), ...]。"""
    verts = att["vertices"]
    bindings = []
    bone_ids = set()
    i = 0
    while i < len(verts):
        n = int(verts[i]); i += 1
        row = []
        for _ in range(n):
            bi = int(verts[i]); bx = verts[i + 1]; by = verts[i + 2]; w = verts[i + 3]
            row.append((bi, bx, by, w))
            bone_ids.add(bi)
            i += 4
        bindings.append(row)
    return bindings, sorted(bone_ids)


def recover_rest_world(bindings, world):
    """由骨 world + bind 座標還原每頂點 rest 世界座標 (N,2)。"""
    pts = np.zeros((len(bindings), 2))
    for vi, row in enumerate(bindings):
        wx = wy = 0.0
        for (bi, bx, by, w) in row:
            W = world[bi]
            wx += w * (W[0, 0] * bx + W[0, 1] * by + W[0, 2])
            wy += w * (W[1, 0] * bx + W[1, 1] * by + W[1, 2])
        pts[vi] = (wx, wy)
    return pts


def artist_weight_matrix(bindings, bone_ids):
    """把美術權重攤成 (N, B) 矩陣(欄序 = bone_ids)。"""
    col = {b: k for k, b in enumerate(bone_ids)}
    W = np.zeros((len(bindings), len(bone_ids)))
    for vi, row in enumerate(bindings):
        for (bi, _, _, w) in row:
            W[vi, col[bi]] += w
    return W


# ---------------- 幾何:cotangent Laplacian + 質量 ----------------
def cotangent_laplacian(verts, tris):
    """cotangent Laplacian L(N,N,正半定)+ lumped Voronoi 質量 M 對角(N,)。"""
    n = len(verts)
    L = sp.lil_matrix((n, n))
    mass = np.zeros(n)
    for t in tris:
        i, j, k = int(t[0]), int(t[1]), int(t[2])
        vi, vj, vk = verts[i], verts[j], verts[k]
        # 每角 cotangent
        for (a, b, c) in ((i, j, k), (j, k, i), (k, i, j)):
            # 角在 a,對邊 (b,c)
            u = verts[b] - verts[a]
            v = verts[c] - verts[a]
            cross = abs(u[0] * v[1] - u[1] * v[0])
            dot = u[0] * v[0] + u[1] * v[1]
            cot = dot / cross if cross > 1e-12 else 0.0
            L[b, c] -= 0.5 * cot
            L[c, b] -= 0.5 * cot
            L[b, b] += 0.5 * cot
            L[c, c] += 0.5 * cot
        # 三角面積 → lumped mass (barycentric 1/3)
        area = 0.5 * abs((vj[0] - vi[0]) * (vk[1] - vi[1]) - (vk[0] - vi[0]) * (vj[1] - vi[1]))
        for idx in (i, j, k):
            mass[idx] += area / 3.0
    return sp.csr_matrix(L), mass


def point_seg_dist(p, a, b):
    ab = b - a
    L2 = ab[0] ** 2 + ab[1] ** 2
    if L2 < 1e-12:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ab[0] + (p[1] - a[1]) * ab[1]) / L2))
    proj = a + t * ab
    return math.hypot(p[0] - proj[0], p[1] - proj[1])


# ---------------- heat-diffusion 權重 ----------------
def heat_weights(verts, tris, segs, bone_ids, max_bones=4):
    """回傳 (N, B) 權重矩陣(欄序 = bone_ids),partition of unity(∑列=1)。

    A = L + M·diag(1/d²);  A W = M·diag(1/d²) P
      d_i = 頂點 i 到最近骨段距離;P_i = 最近骨 one-hot。
    尺度不變、α=1(不對真值調參)。
    max_bones:每頂點只保留權重最大的前 K 骨(Spine 慣例 ≤4)再重正規化,
    避免熱擴散長尾讓每頂點都掛到全部骨(稀疏化 → 貼近 runtime 實務)。
    """
    n = len(verts)
    B = len(bone_ids)
    L, mass = cotangent_laplacian(verts, tris)
    # 每頂點到各骨段距離
    D = np.zeros((n, B))
    for k, bid in enumerate(bone_ids):
        a, b = segs[bid]
        for i in range(n):
            D[i, k] = point_seg_dist(verts[i], a, b)
    nearest = D.argmin(axis=1)
    dmin = D[np.arange(n), nearest]
    dmin = np.maximum(dmin, 1e-3 * (verts.max() - verts.min() + 1.0))  # 防除零
    h = mass / (dmin ** 2)                       # 對角熱項
    P = np.zeros((n, B))
    P[np.arange(n), nearest] = 1.0
    A = (L + sp.diags(h)).tocsc()
    rhs = (h[:, None] * P)
    Wc = spla.spsolve(A, rhs)
    if Wc.ndim == 1:
        Wc = Wc.reshape(-1, 1)
    Wc = np.clip(Wc, 0.0, None)                  # 數值上偶有微負 → 夾 0
    if max_bones and B > max_bones:              # 稀疏化:每列只留前 K 骨
        for i in range(n):
            order = np.argsort(Wc[i])[::-1]
            Wc[i, order[max_bones:]] = 0.0
    Wc = Wc / np.maximum(Wc.sum(axis=1, keepdims=True), 1e-12)  # 重正規化 PoU
    return Wc, {"D": D, "nearest": nearest, "L": L}


def dirichlet_energy(W, L):
    """權重場平滑度:∑_b w_b^T L w_b(越小越平滑)。"""
    e = 0.0
    for b in range(W.shape[1]):
        w = W[:, b]
        e += float(w @ (L @ w))
    return e


# ---------------- 骨骼變形(linear blend skinning)----------------
def fk_world_posed(skeleton, deltas):
    """deltas = {bone_index: extra_rotation_deg}。回傳套上額外旋轉後的 {idx: 3x3 world}。
    改動會經 FK 傳遞給子骨(旋轉某骨 → 其所有後代跟著轉)。"""
    bones = skeleton["bones"]
    byname = {b["name"]: i for i, b in enumerate(bones)}
    world = {}

    def get(i):
        if i in world:
            return world[i]
        b = dict(bones[i])
        if i in deltas:
            b["rotation"] = b.get("rotation", 0.0) + deltas[i]
        m = local_mat(b)
        p = bones[i].get("parent")
        world[i] = (get(byname[p]) @ m) if p else m
        return world[i]

    for i in range(len(bones)):
        get(i)
    return world


def bind_local(rest_world, world_rest, bone_ids):
    """回傳 bind[i] = {bone_id: (bx,by)}:rest 世界座標在各骨 rest local 空間的座標
    (= inv(WorldRest_b) · restWorld_i)。供任意權重集做 skinning。"""
    inv = {b: np.linalg.inv(world_rest[b]) for b in bone_ids}
    out = []
    for i in range(len(rest_world)):
        row = {}
        p = np.array([rest_world[i, 0], rest_world[i, 1], 1.0])
        for b in bone_ids:
            q = inv[b] @ p
            row[b] = (q[0], q[1])
        out.append(row)
    return out


def skin_deform(bind, W, bone_ids, world_posed):
    """linear blend skinning:deformed_i = ∑_b w[i,b] · (WorldPosed_b · bind[i][b])。"""
    n = len(bind)
    out = np.zeros((n, 2))
    for i in range(n):
        x = y = 0.0
        for k, b in enumerate(bone_ids):
            w = W[i, k]
            if w == 0.0:
                continue
            bx, by = bind[i][b]
            Wp = world_posed[b]
            x += w * (Wp[0, 0] * bx + Wp[0, 1] * by + Wp[0, 2])
            y += w * (Wp[1, 0] * bx + Wp[1, 1] * by + Wp[1, 2])
        out[i] = (x, y)
    return out


def emit_weighted_vertices(bindings_geom, W, bone_ids, prune=1e-3):
    """把 (N,B) 權重 + bind 座標寫回 Spine `[nBones, boneIdx, bx, by, w, ...]` 格式。
    bindings_geom[i] = {bone_id: (bindX, bindY)} 提供各骨下的 bind 座標。"""
    out = []
    for i in range(W.shape[0]):
        row = [(bone_ids[k], W[i, k]) for k in range(len(bone_ids)) if W[i, k] > prune]
        s = sum(w for _, w in row) or 1.0
        row = [(b, w / s) for b, w in row]
        out.append(len(row))
        for (bid, w) in row:
            bx, by = bindings_geom[i][bid]
            out.extend([bid, bx, by, w])
    return out
