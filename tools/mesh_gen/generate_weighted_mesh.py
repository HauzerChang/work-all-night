#!/usr/bin/env python3
"""S3 候選 2 —— weighted mesh 生成器:內部取樣密度控制 + heat-diffusion 骨綁權重(BBW 近似)。

補上 STATE 候選 2 的最後一塊:先前 boundary-dense 幾乎只有邊界點,無法服務骨骼變形平滑度;
藝術家用密集內部頂點 + 平滑權重。本工具:
  1. 由輪廓多邊形(S4 切圖產物;此處用藝術家 hull 當真值輸入)三角化,以 max-area 控制**內部取樣密度**。
  2. 以 **heat-diffusion 權重**(Baran & Popović 2007「bone heat」;BBW 的實用近似,純 CPU 稀疏解):
       (L + H) W = H P
     L=cotangent Laplacian(半正定慣例)、H=diag(1/d_i²) 為到最近骨的熱貢獻、P=最近骨 one-hot。
     此式**天然滿足 partition of unity**(每頂點權重和=1),且權重在網格上平滑擴散。
  3. 剪成每頂點至多 k 骨(Spine 上限 4)、重正規化。
  4. 輸出 Spine weighted vertices 格式(bind = 頂點在各骨 setup 局部座標,經逆變換算得)。

驗收:用 `weighted_deform_eval.eval_pv` 過同一道閘(不透明件真實動畫 si=0),並比對藝術家平滑度指標。
真值:Award.json 的機器人件骨架 + hull 輪廓。
"""
import numpy as np
import triangle as tr
from scipy.sparse import lil_matrix, csr_matrix
from scipy.sparse.linalg import spsolve

import weighted_deform_eval as W


# ---------- 三角化(內部取樣密度控制) ----------
def triangulate_polygon(poly, max_area, min_angle=28, boundary_steiner=True):
    """poly: Nx2 邊界(有序)。max_area 越小內部點越密。回傳 (V Nx2, F Mx3)。
    boundary_steiner=False(加 'Y'):禁止在邊界插點 → 前 N 個頂點 == 原邊界(順序不變),
    供 Spine 'hull 必排最前' 的需求(build_spine 用)。"""
    n = len(poly)
    segs = [[i, (i + 1) % n] for i in range(n)]
    d = {"vertices": np.asarray(poly, dtype=np.float64), "segments": np.asarray(segs, dtype=np.int32)}
    opts = f"pq{min_angle}a{max_area:.3f}" + ("" if boundary_steiner else "Y")
    t = tr.triangulate(d, opts)
    return np.asarray(t["vertices"], dtype=np.float64), np.asarray(t["triangles"], dtype=np.int32)


# ---------- cotangent Laplacian(半正定:L_ii=Σcot, L_ij=-cot) ----------
def cotangent_laplacian(V, F):
    n = len(V)
    L = lil_matrix((n, n))
    for tri in F:
        i, j, k = tri
        vi, vj, vk = V[i], V[j], V[k]
        # 每角的 cot 貢獻到對邊
        for (a, b, c) in ((i, j, k), (j, k, i), (k, i, j)):
            # 角在頂點 a,對邊 (b,c)
            u = V[b] - V[a]; w = V[c] - V[a]
            cross = abs(u[0] * w[1] - u[1] * w[0])
            if cross < 1e-12:
                cot = 0.0
            else:
                cot = float(np.dot(u, w)) / cross
            hw = 0.5 * cot
            L[b, c] -= hw; L[c, b] -= hw
            L[b, b] += hw; L[c, c] += hw
    return csr_matrix(L)


# ---------- heat-diffusion 權重 ----------
def _point_seg_dist(p, a, b):
    ab = b - a; t = np.dot(p - a, ab) / (np.dot(ab, ab) + 1e-12)
    t = max(0.0, min(1.0, t))
    return float(np.hypot(*(p - (a + t * ab))))


def heat_weights(V, F, bone_segs):
    """bone_segs: list of (a2, b2) 世界座標線段(每骨一段)。回傳 W (n, m) partition of unity。"""
    n = len(V); m = len(bone_segs)
    d = np.zeros((n, m))
    for i, p in enumerate(V):
        for j, (a, b) in enumerate(bone_segs):
            d[i, j] = _point_seg_dist(p, np.asarray(a), np.asarray(b))
    nearest = d.argmin(1)
    dmin = d[np.arange(n), nearest]
    # H = c/d²;c 用平均邊長平方尺度化以穩定條件數(Pinocchio 慣例的實用版)
    scale = np.median([np.hypot(*(V[t[0]] - V[t[1]])) for t in F]) ** 2
    Hdiag = scale / np.maximum(dmin, 1e-3) ** 2
    L = cotangent_laplacian(V, F)
    H = csr_matrix((Hdiag, (range(n), range(n))), shape=(n, n))
    A = (L + H).tocsc()
    Wgt = np.zeros((n, m))
    for j in range(m):
        p = np.zeros(n); p[nearest == j] = 1.0
        Wgt[:, j] = spsolve(A, H.dot(p))
    Wgt = np.clip(Wgt, 0, None)
    Wgt /= Wgt.sum(1, keepdims=True) + 1e-12
    return Wgt


def prune_topk(Wgt, k=4):
    out = Wgt.copy()
    for i in range(len(out)):
        row = out[i]
        if (row > 0).sum() > k:
            keep = np.argsort(row)[-k:]
            mask = np.zeros_like(row, bool); mask[keep] = True
            row[~mask] = 0
        out[i] = row / (row.sum() + 1e-12)
    return out


# ---------- 組成 Spine weighted pv ----------
def to_spine_pv(V, Wgt, bone_indices, bone_world_setup):
    """V setup 世界座標;Wgt (n,m);bone_indices m 個 spine bone idx;
    bone_world_setup m 個 (a,b,c,d,x,y)。回傳 pv(weighted_deform_eval 格式)。"""
    pv = []
    for i, p in enumerate(V):
        entries = []
        for j, bidx in enumerate(bone_indices):
            w = float(Wgt[i, j])
            if w <= 1e-6:
                continue
            bx, by = W.inverse_transform_point(bone_world_setup[j], p[0], p[1])
            entries.append((bidx, bx, by, w))
        # 保險:至少綁一骨
        if not entries:
            j = int(Wgt[i].argmax()); bidx = bone_indices[j]
            bx, by = W.inverse_transform_point(bone_world_setup[j], p[0], p[1])
            entries.append((bidx, bx, by, 1.0))
        # 重正規化
        s = sum(e[3] for e in entries)
        entries = [(e[0], e[1], e[2], e[3] / s) for e in entries]
        pv.append(entries)
    return pv


# ---------- 端到端:對 Award 某 mesh 件生成並回傳評估所需 ----------
def generate_for_slot(path, slot, max_area=400.0, topk=4):
    sk, bones, byname, order = W.load_skeleton(path)
    atts = W.get_skin_attachments(sk)
    name = next(iter(atts[slot]))
    att = atts[slot][name]
    apv, atris, hull, uvs, wt = W.parse_weighted(att)
    bidx_to_name = {i: b["name"] for i, b in enumerate(bones)}
    world0 = W.bone_world_transforms(bones, byname, order, {})
    asv = W.skin_vertices(apv, world0, bidx_to_name)  # 藝術家 setup 世界座標
    boundary = asv[:hull]                              # hull = 輪廓多邊形(真值輸入)

    # 三角化(內部密度由 max_area 控制)
    V, F = triangulate_polygon(boundary, max_area=max_area)

    # 骨:用藝術家 mesh 綁的骨;每骨線段 = parent_origin → bone_origin(setup 世界)
    mesh_bidx = sorted({e[0] for en in apv for e in en})
    segs = []
    for bi in mesh_bidx:
        nm = bidx_to_name[bi]; par = byname[nm].get("parent")
        o = world0[nm]; bo = (o[4], o[5])
        po = (world0[par][4], world0[par][5]) if par and par in world0 else bo
        segs.append((po, bo))
    Wgt = prune_topk(heat_weights(V, F, segs), k=topk)
    bworld = [world0[bidx_to_name[bi]] for bi in mesh_bidx]
    pv = to_spine_pv(V, Wgt, mesh_bidx, bworld)
    mesh_bone_names = [bidx_to_name[bi] for bi in mesh_bidx]
    return dict(sk=sk, bones=bones, byname=byname, order=order, bidx_to_name=bidx_to_name,
                pv=pv, tris=F, mesh_bone_names=mesh_bone_names,
                artist=dict(pv=apv, tris=atris, hull=hull, nv=len(apv)))


if __name__ == "__main__":
    import sys, json
    path = sys.argv[1] if len(sys.argv) > 1 else "assets/Award.json"
    slot = sys.argv[2] if len(sys.argv) > 2 else "機器人拆件/身體"
    ma = float(sys.argv[3]) if len(sys.argv) > 3 else 400.0
    g = generate_for_slot(path, slot, max_area=ma)
    print(f"generated nv={len(g['pv'])} tris={len(g['tris'])} (artist nv={g['artist']['nv']})")
    r = W.eval_pv(g["sk"], g["bones"], g["byname"], g["order"], g["bidx_to_name"],
                  g["pv"], g["tris"], g["mesh_bone_names"])
    print(json.dumps({"worst": r["worst"], "setup_clean": r["setup"]["clean"],
                      "smoothness": r["smoothness"], "validated": r["checker_validated"]},
                     ensure_ascii=False, indent=2))
