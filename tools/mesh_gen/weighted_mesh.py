"""weighted_mesh — Spine weighted-mesh 骨綁權重能力 (S3 candidate 2)

補上 S3 唯一未驗維度:weighted mesh 的「骨骼變形平滑度」。

提供:
- FK:由 Spine 3.8 bones 陣列算 setup-pose 世界變換(origin + 2x2)。
- 解析 weighted vertices → 每頂點 [(boneIdx,bx,by,w),...]。
- reconstruct_setup:由藝術家權重重建每頂點 setup 世界座標(骨空間)。
- harmonic_weights:餘切 Laplacian 的**有界調和權重**(bounded harmonic weights),
  這是 BBW 在純 CPU 上可解的主幹形式 —— 由最大值原理自動保證
  (1) 每權重 ∈ [0,1]、(2) 各骨權重和 ≡ 1(partition of unity)、(3) 內部平滑(調和)。
- deform:給定每骨的 pose 增量(旋轉/平移),用某組權重把 setup 頂點變形。

⚠️ 座標系:mesh 重建座標與 bone origin 皆在同一 Award 骨架空間 → 不需 frame 轉換。

信心:中高。有界調和權重是 BBW 的可證有界/單位分解的子集(缺 biharmonic 的
額外平滑與 bound 不等式約束,但在三角網格上足以量化「變形平滑度」對照)。
"""
import math
import numpy as np


# ---------- FK：bone setup-pose 世界變換 ----------
def compute_bone_world(bones):
    """回傳 dict: name -> {a,b,c,d, wx,wy}  (世界 2x2 + 世界原點)。

    Spine local (shear=0):
      la= cos(rot)*sx ; lb= -sin(rot)*sy ; lc= sin(rot)*sx ; ld= cos(rot)*sy
    world = parentWorld ∘ local ; root = identity。
    """
    byname = {b["name"]: b for b in bones}
    world = {}

    def solve(name):
        if name in world:
            return world[name]
        b = byname[name]
        x = b.get("x", 0.0) or 0.0
        y = b.get("y", 0.0) or 0.0
        rot = (b.get("rotation", 0.0) or 0.0) * math.pi / 180.0
        sx = b.get("scaleX", 1.0)
        sx = 1.0 if sx is None else sx
        sy = b.get("scaleY", 1.0)
        sy = 1.0 if sy is None else sy
        cr, sr = math.cos(rot), math.sin(rot)
        la, lb, lc, ld = cr * sx, -sr * sy, sr * sx, cr * sy
        parent = b.get("parent")
        if parent is None:
            w = dict(a=la, b=lb, c=lc, d=ld, wx=x, wy=y)
        else:
            p = solve(parent)
            pa, pb, pc, pd = p["a"], p["b"], p["c"], p["d"]
            w = dict(
                a=pa * la + pb * lc,
                b=pa * lb + pb * ld,
                c=pc * la + pd * lc,
                d=pc * lb + pd * ld,
                wx=pa * x + pb * y + p["wx"],
                wy=pc * x + pd * y + p["wy"],
            )
        world[name] = w
        return w

    for b in bones:
        solve(b["name"])
    return world


def apply_xform(w, px, py):
    """把 (px,py) 用世界變換 w 轉到世界座標。"""
    return (w["a"] * px + w["b"] * py + w["wx"],
            w["c"] * px + w["d"] * py + w["wy"])


# ---------- 解析 weighted vertices ----------
def parse_weighted(vertices):
    """Spine weighted vertices → list[ list[(boneIdx,bx,by,w)] ]。"""
    out = []
    i = 0
    v = vertices
    while i < len(v):
        n = int(v[i]); i += 1
        vs = []
        for _ in range(n):
            bi = int(v[i]); bx = v[i + 1]; by = v[i + 2]; w = v[i + 3]; i += 4
            vs.append((bi, bx, by, w))
        out.append(vs)
    return out


def reconstruct_setup(parsed, bones):
    """由藝術家權重重建每頂點 setup 世界座標 (N,2)。"""
    world = compute_bone_world(bones)
    bname = [b["name"] for b in bones]
    pts = np.zeros((len(parsed), 2))
    for k, vs in enumerate(parsed):
        px = py = 0.0
        for (bi, bx, by, wgt) in vs:
            w = world[bname[bi]]
            wx, wy = apply_xform(w, bx, by)
            px += wgt * wx
            py += wgt * wy
        pts[k] = (px, py)
    return pts


# ---------- 餘切 Laplacian ----------
def cotangent_laplacian(V, F):
    """回傳稠密 (N,N) 餘切權重 Laplacian L (L = D - W, 對稱)。"""
    n = len(V)
    W = np.zeros((n, n))
    for tri in F:
        i, j, k = int(tri[0]), int(tri[1]), int(tri[2])
        vi, vj, vk = V[i], V[j], V[k]
        # 對邊 (j,k) 的角在 i,依此類推
        for (a, b, c) in ((i, j, k), (j, k, i), (k, i, j)):
            va, vb, vc = V[a], V[b], V[c]
            u = vb - va
            w = vc - va
            cross = u[0] * w[1] - u[1] * w[0]
            dot = u[0] * w[0] + u[1] * w[1]
            if abs(cross) < 1e-12:
                cot = 0.0
            else:
                cot = dot / abs(cross)
            # 角在 a → 貢獻到對邊 (b,c)
            W[b, c] += 0.5 * cot
            W[c, b] += 0.5 * cot
    W = np.maximum(W, 0.0)  # 鈍角三角截負(保正定 / 保最大值原理)
    D = np.diag(W.sum(axis=1))
    return D - W


# ---------- 有界調和權重 (bounded harmonic weights) ----------
def harmonic_weights(V, F, seeds):
    """解每個 handle 的調和權重。

    seeds: dict handle_id -> list[vertex index] (該 handle 的 w=1 約束點)。
    回傳 (N, H) 權重矩陣,H=len(seeds)。所有 seed 頂點固定,內部解 Laplace。
    最大值原理 → 每欄 ∈ [0,1];各欄約束互斥且覆蓋所有 seed → 逐列和 ≡ 1。
    """
    n = len(V)
    L = cotangent_laplacian(V, F)
    handles = list(seeds.keys())
    H = len(handles)
    # 所有被約束的頂點
    constrained = {}
    for hi, h in enumerate(handles):
        for vidx in seeds[h]:
            constrained[vidx] = hi
    fixed = sorted(constrained.keys())
    free = [i for i in range(n) if i not in constrained]
    Wmat = np.zeros((n, H))
    if not free:
        for vidx, hi in constrained.items():
            Wmat[vidx, hi] = 1.0
        return Wmat, handles
    Lff = L[np.ix_(free, free)]
    Lfc = L[np.ix_(free, fixed)]
    # 每 handle 的邊界值向量
    for hi in range(H):
        bc = np.array([1.0 if constrained[vidx] == hi else 0.0 for vidx in fixed])
        rhs = -Lfc @ bc
        try:
            wf = np.linalg.solve(Lff, rhs)
        except np.linalg.LinAlgError:
            wf = np.linalg.lstsq(Lff, rhs, rcond=None)[0]
        Wmat[free, hi] = wf
        Wmat[fixed, hi] = bc
    # 數值鉗制 + 正規化(理論上已是單位分解,鉗制殘差)
    Wmat = np.clip(Wmat, 0.0, 1.0)
    rs = Wmat.sum(axis=1, keepdims=True)
    rs[rs == 0] = 1.0
    Wmat = Wmat / rs
    return Wmat, handles


def artist_anchor_seeds(W_art, handles, thresh=0.9):
    """由藝術家權重取「純區」頂點作 Dirichlet 錨點:某骨 w>=thresh 的頂點。

    用於**方法驗證**:給定藝術家的硬指派區,harmonic 只解過渡帶 → 可證
    Dirichlet 能量 <= 藝術家(相同約束下 harmonic 為最小者)。
    每 handle 至少保底一個(該欄 argmax 頂點)。
    回傳 seeds dict handle -> [vertex idx]。
    """
    seeds = {}
    n = W_art.shape[0]
    for hi, h in enumerate(handles):
        col = W_art[:, hi]
        idxs = [i for i in range(n) if col[i] >= thresh and col[i] == W_art[i].max()]
        if not idxs:
            idxs = [int(np.argmax(col))]
        seeds[h] = idxs
    # 去重:一個頂點只歸最強的 handle(避免過約束衝突)
    owner = {}
    for hi, h in enumerate(handles):
        for i in seeds[h]:
            if i not in owner or W_art[i, hi] > W_art[i, owner[i]]:
                owner[i] = hi
    dedup = {h: [] for h in handles}
    for i, hi in owner.items():
        dedup[handles[hi]].append(i)
    for hi, h in enumerate(handles):
        if not dedup[h]:
            dedup[h] = [int(np.argmax(W_art[:, hi]))]
    return dedup


def assign_seeds(V, bone_origins):
    """每根 bone → 最近的 mesh 頂點作 seed(貪婪去重,確保各 handle 不共用頂點)。

    bone_origins: dict handle_id -> (x,y) (骨原點,骨架空間)。
    回傳 seeds dict handle_id -> [vertex idx]。
    """
    seeds = {}
    used = set()
    # 依到最近頂點的距離排序,近的先挑(避免遠 bone 搶走該近 bone 的唯一頂點)
    order = []
    for h, (ox, oy) in bone_origins.items():
        d = np.hypot(V[:, 0] - ox, V[:, 1] - oy)
        order.append((h, d))
    order.sort(key=lambda t: t[1].min())
    for h, d in order:
        idx = int(np.argmin([d[i] if i not in used else 1e18 for i in range(len(V))]))
        seeds[h] = [idx]
        used.add(idx)
    return seeds


# ---------- 變形 ----------
def bone_delta_xform(angle_deg, tx=0.0, ty=0.0, pivot=(0.0, 0.0)):
    """繞 pivot 旋轉 angle + 平移 的 2D 仿射。回傳 callable(pt)->pt。"""
    a = angle_deg * math.pi / 180.0
    ca, sa = math.cos(a), math.sin(a)
    px, py = pivot

    def f(p):
        x, y = p[0] - px, p[1] - py
        rx = ca * x - sa * y
        ry = sa * x + ca * y
        return (rx + px + tx, ry + py + ty)
    return f


def deform(V, Wmat, handles, bone_xforms):
    """linear blend skinning:每頂點 = Σ_h w_h * xform_h(v)。

    bone_xforms: dict handle_id -> callable(pt)->pt。
    """
    n = len(V)
    out = np.zeros((n, 2))
    for hi, h in enumerate(handles):
        f = bone_xforms[h]
        for i in range(n):
            dx, dy = f(V[i])
            out[i, 0] += Wmat[i, hi] * dx
            out[i, 1] += Wmat[i, hi] * dy
    return out


def dirichlet_energy(V, F, w):
    """權重向量 w 在網格上的 Dirichlet 能量(平滑度指標,越小越平滑)。"""
    edges = set()
    for tri in F:
        i, j, k = int(tri[0]), int(tri[1]), int(tri[2])
        for a, b in ((i, j), (j, k), (k, i)):
            edges.add((min(a, b), max(a, b)))
    e = 0.0
    for (a, b) in edges:
        e += (w[a] - w[b]) ** 2
    return e / max(1, len(edges))
