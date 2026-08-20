#!/usr/bin/env python3
"""S3 weighted-mesh 能力:骨架權重(biharmonic / BBW-relaxation)+ 加權變形。

補上 `compare_robot_mesh.py` 留下的唯一未驗維度:**weighted mesh 的骨骼變形平滑度**。
`compare_robot_mesh` 只驗靜態覆蓋率(IoU)+ 拓樸,對「靠骨骼+權重變形」的件無法量化變形品質。
本模組提供純 CPU、確定性的權重求解 + Spine 加權蒙皮,讓 weighted mesh 可被程式化生成並自我驗收。

方法(全部 CPU / scipy 稀疏解,無 ML):
  - **FK**:由 Spine 3.8 bones(x/y/rotation/scale/parent)算 setup-pose 世界矩陣;`pose_bones` 施加旋轉增量。
  - **加權蒙皮**:Spine weighted mesh 格式 `[nb, boneIdx,bindX,bindY,w, ...]`,
    世界頂點 = Σ_b w · (BoneWorld_b · [bindX,bindY])。用來重現美術權重的「真值變形」。
  - **cotangent Laplacian + biharmonic 權重**:每骨在其 handle 頂點 w=1、其餘 handle w=0,
    解 biharmonic(Q=Lᵀ M⁻¹ L)的 Dirichlet 問題,再 clamp≥0 + 正規化成 partition-of-unity。
    這是 Bounded Biharmonic Weights 的鬆弛版(去掉 0≤w≤1 硬約束改用 clamp),平滑且確定。
  - **綁定**:由 setup 世界頂點反算各骨 bind 座標(inverse boneWorld · V0),產出可寫回 Spine 的 weighted vertices。

驗收見 `validate_bbw.py`(對 Award 3 個真實美術 weighted mesh 的權重當真值)。
"""
import math
import copy
import numpy as np
from scipy.sparse import lil_matrix, csr_matrix, diags
from scipy.sparse.linalg import spsolve


# ---------- forward kinematics ----------
def _local(b):
    x = b.get("x", 0.0); y = b.get("y", 0.0)
    r = math.radians(b.get("rotation", 0.0))
    sx = b.get("scaleX", 1.0); sy = b.get("scaleY", 1.0)
    c, s = math.cos(r), math.sin(r)
    return np.array([[c * sx, -s * sy, x],
                     [s * sx,  c * sy, y],
                     [0, 0, 1]], float)


def fk(bones):
    """回傳 {bone_index: 3x3 世界矩陣}(setup pose;忽略 inherit 旗標,對本資產已足夠)。"""
    name2i = {b["name"]: i for i, b in enumerate(bones)}
    W = {}

    def comp(i):
        b = bones[i]; L = _local(b); p = b.get("parent")
        if p is None:
            W[i] = L
        else:
            pi = name2i[p]
            if pi not in W:
                comp(pi)
            W[i] = W[pi] @ L
        return W[i]

    for i in range(len(bones)):
        comp(i)
    return W


def pose_bones(bones, deltas):
    """複製 bones 並對 {bone_index: 旋轉增量(度)} 施加旋轉,回傳新 bones list。"""
    bp = copy.deepcopy(bones)
    for i, dr in deltas.items():
        bp[i]["rotation"] = bones[i].get("rotation", 0.0) + dr
    return bp


# ---------- Spine weighted mesh ----------
def parse_weighted(att):
    """Spine weighted `vertices` → per-vertex [(boneIdx,bindX,bindY,w), ...]。"""
    v = att["vertices"]; i = 0; perv = []
    while i < len(v):
        nb = int(v[i]); i += 1; e = []
        for _ in range(nb):
            e.append((int(v[i]), v[i + 1], v[i + 2], v[i + 3])); i += 4
        perv.append(e)
    return perv


def skin_world(perv, W):
    """加權蒙皮:回傳世界頂點 (n,2)。W = fk(bones)。"""
    out = np.empty((len(perv), 2))
    for vi, e in enumerate(perv):
        p = np.zeros(2)
        for (bi, bx, by, w) in e:
            M = W[bi]
            p += w * np.array([M[0, 0] * bx + M[0, 1] * by + M[0, 2],
                               M[1, 0] * bx + M[1, 1] * by + M[1, 2]])
        out[vi] = p
    return out


def flip_count(V0, V, tris):
    """相對 setup,三角形有向面積變號(翻面/自交)的數量 —— 變形平滑度的硬閘。"""
    def area(P):
        a = P[tris[:, 1]] - P[tris[:, 0]]
        b = P[tris[:, 2]] - P[tris[:, 0]]
        return a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
    return int(np.sum(np.sign(area(V0)) != np.sign(area(V))))


# ---------- biharmonic (BBW-relaxation) weights ----------
def cotangent_laplacian(V, tris):
    n = len(V); L = lil_matrix((n, n)); M = np.zeros(n)
    for t in tris:
        i, j, k = int(t[0]), int(t[1]), int(t[2])
        for (a, b, c) in [(i, j, k), (j, k, i), (k, i, j)]:
            u = V[b] - V[a]; w = V[c] - V[a]
            cr = abs(u[0] * w[1] - u[1] * w[0]); cr = cr if cr > 1e-9 else 1e-9
            cot = (u @ w) / cr
            L[b, c] -= 0.5 * cot; L[c, b] -= 0.5 * cot
            L[b, b] += 0.5 * cot; L[c, c] += 0.5 * cot
        ar = 0.5 * abs((V[j] - V[i])[0] * (V[k] - V[i])[1] -
                       (V[j] - V[i])[1] * (V[k] - V[i])[0])
        for v in (i, j, k):
            M[v] += ar / 3.0
    return csr_matrix(L), M


def _solve_dirichlet(Q, cons, vals):
    n = Q.shape[0]
    free = np.setdiff1d(np.arange(n), cons)
    wf = spsolve(csr_matrix(Q[free][:, free]), -(Q[free][:, cons] @ vals))
    w = np.zeros(n); w[cons] = vals; w[free] = wf
    return w


def compute_weights(V, tris, handle_xy, weight_eps=1e-4):
    """biharmonic 權重。handle_xy: {bone_index: (x,y)} setup 世界座標(handle 定錨點)。
    回傳 (Wmat[n_bone, n_vert] 已 clamp+正規化, bone_order, anchor_vertex_per_bone)。"""
    L, M = cotangent_laplacian(V, tris)
    Q = L.T @ diags(1.0 / np.maximum(M, 1e-8)) @ L
    bone_order = sorted(handle_xy.keys())
    anchor = {b: int(np.argmin(np.linalg.norm(V - np.asarray(handle_xy[b]), axis=1)))
              for b in bone_order}
    cons = np.array([anchor[b] for b in bone_order])
    Wmat = np.array([_solve_dirichlet(Q, cons,
                     np.array([1.0 if bb == b else 0.0 for bb in bone_order]))
                     for b in bone_order])
    Wmat = np.clip(Wmat, 0.0, None)
    Wmat /= np.maximum(Wmat.sum(0), 1e-8)
    return Wmat, bone_order, anchor


def bind_weights(V, Wmat, bone_order, W_setup, weight_eps=1e-4):
    """由 setup 世界頂點 V + 權重矩陣,反算各骨 bind 座標,產出 Spine per-vertex 加權格式。"""
    perv = []
    for vi in range(len(V)):
        e = []
        for bidx, b in enumerate(bone_order):
            w = Wmat[bidx, vi]
            if w < weight_eps:
                continue
            R = W_setup[b][:2, :2]; Ri = np.linalg.inv(R); ti = -Ri @ W_setup[b][:2, 2]
            bind = Ri @ V[vi] + ti
            e.append((b, float(bind[0]), float(bind[1]), float(w)))
        s = sum(x[3] for x in e) or 1.0
        perv.append([(bi, bx, by, ww / s) for (bi, bx, by, ww) in e])
    return perv


def to_spine_vertices(perv):
    """per-vertex [(bone,bindX,bindY,w),...] → Spine flat `vertices` array。"""
    out = []
    for e in perv:
        out.append(len(e))
        for (bi, bx, by, w) in e:
            out.extend([bi, bx, by, w])
    return out
