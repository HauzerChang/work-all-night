#!/usr/bin/env python3
"""S3 weighted-mesh — 骨綁權重生成器(bone-heat / Baran-Popović,純 CPU)。

用途:對一張 mesh(頂點在 skeleton 空間 + 三角)與一組骨(線段),自動算出每頂點對每骨的
權重矩陣 W(N×B),供 weighted mesh 骨骼變形。這補上 knowledge/s3-robot-mesh-vs-award 的
唯一未驗維度(靜態覆蓋率 PASS ≠ bone-driven 變形平滑度)。

方法:bone-heat equilibrium(Blender 預設「Bone Heat」/ Pinocchio 自動綁骨用的同一式):
    (-L + H) W = H P
  L = cotangent Laplacian(L·1 = 0);H = diag(1/d_min(j)²)(最近骨的熱貢獻);
  P[j,i] = 1 若骨 i 是頂點 j 的最近骨,否則 0。
數學性質(可機讀驗):
  * partition of unity:∑_i W[:,i] = 1(因 L·1=0 且 ∑_i P[:,i]=1 → 常數 1 為解)。
  * bounded:0 ≤ W ≤ 1(最大值原理)。
  * smooth/local:cotangent Laplacian 使權重沿 mesh 平滑遞減 → 變形無撕裂。
選 bone-heat 而非解 biharmonic(真 BBW):純 CPU 單次稀疏線性解、無需 QP、
工業標準且性質相同(bounded/partition/local),對本資產已足夠;BBW 為後續可選升級。
"""
import numpy as np
from scipy.sparse import lil_matrix, csr_matrix, diags
from scipy.sparse.linalg import spsolve


def _cot(a, b, c):
    """三角 (a,b,c) 在頂點 a 的角的 cotangent(2D)。"""
    u = b - a; v = c - a
    cross = u[0] * v[1] - u[1] * v[0]
    dot = u[0] * v[0] + u[1] * v[1]
    if abs(cross) < 1e-12:
        cross = 1e-12 if cross >= 0 else -1e-12
    return dot / abs(cross)


def cotangent_laplacian(verts, tris):
    """回傳 N×N 稀疏 cotangent Laplacian L(L·1 = 0,負半定)。"""
    n = len(verts)
    C = lil_matrix((n, n))
    for t in tris:
        i, j, k = int(t[0]), int(t[1]), int(t[2])
        vi, vj, vk = verts[i], verts[j], verts[k]
        # 對邊 (j,k) 用頂點 i 的角;以此類推
        for (a, b, opp) in ((j, k, vi), (k, i, vj), (i, j, vk)):
            w = 0.5 * _cot(opp, verts[a], verts[b])
            C[a, b] += w; C[b, a] += w
    C = C.tocsr()
    d = np.asarray(C.sum(axis=1)).ravel()
    L = C - diags(d)
    return L


def _pt_seg_dist2(p, a, b):
    """點 p 到線段 ab 的距離平方(向量化:p 為 N×2)。"""
    ab = b - a
    denom = ab.dot(ab)
    if denom < 1e-12:
        d = p - a
        return (d * d).sum(1)
    t = ((p - a) @ ab) / denom
    t = np.clip(t, 0.0, 1.0)
    proj = a + t[:, None] * ab
    d = p - proj
    return (d * d).sum(1)


def bone_heat_weights(verts, tris, bone_segments, max_influences=None, prune_eps=1e-3):
    """回傳 W(N×B):頂點×骨 權重(partition-of-unity、bounded)。
    bone_segments: [(p0(2,), p1(2,)), ...] 各骨線段(skeleton 空間)。
    max_influences:每頂點保留最大權重的前 k 骨(其餘歸零後重正規化;None=不限)。
    """
    verts = np.asarray(verts, np.float64)
    n = len(verts); B = len(bone_segments)
    # 每骨到每頂點的距離平方
    d2 = np.zeros((n, B))
    for i, (p0, p1) in enumerate(bone_segments):
        d2[:, i] = _pt_seg_dist2(verts, np.asarray(p0, float), np.asarray(p1, float))
    nearest = d2.argmin(1)
    dmin2 = d2[np.arange(n), nearest]
    dmin2 = np.maximum(dmin2, 1e-6)
    h = 1.0 / dmin2                       # 熱貢獻
    P = np.zeros((n, B)); P[np.arange(n), nearest] = 1.0

    L = cotangent_laplacian(verts, tris)
    A = (-L + diags(h)).tocsr()
    # (-L + H) W = H P  → 逐骨解一次稀疏線性系統
    W = np.column_stack([spsolve(A, h * P[:, i]) for i in range(B)])
    W = np.clip(W, 0.0, None)
    if max_influences is not None and B > max_influences:
        for j in range(n):
            row = W[j]
            keep = np.argsort(row)[-max_influences:]
            mask = np.zeros(B, bool); mask[keep] = True
            row[~mask] = 0.0
    W[W < prune_eps] = 0.0
    s = W.sum(1, keepdims=True); s[s == 0] = 1.0
    W = W / s
    return W


def bone_segments_from_skeleton(skeleton, bone_names, bone_indices, bones_world):
    """由骨的世界矩陣建線段:origin → origin + length·x軸(無 length 用到子骨)。"""
    bones = skeleton["bones"]
    segs = []
    for bidx in bone_indices:
        name = bone_names[bidx]
        a, b, c, d, tx, ty = bones_world[name]
        length = bones[bidx].get("length", 0.0)
        if length <= 1e-6:
            length = 40.0
        # 骨 x 軸方向 = (a, c) 正規化
        dirx, diry = a, c
        nrm = (dirx ** 2 + diry ** 2) ** 0.5 or 1.0
        dirx /= nrm; diry /= nrm
        p0 = np.array([tx, ty])
        p1 = np.array([tx + dirx * length, ty + diry * length])
        segs.append((p0, p1))
    return segs
