"""S5 肢體父子樹自動推斷器(確定性、純 CPU)。

問題(S5 (c),補上 rig 目前唯一「取自先驗」的環節):
  給定已拆好的各結構部位幾何(世界多邊形),**自動推斷運動學父子樹**
  (誰是根 / 誰是誰的子件)。此前 `build_spine --rig` 的 `rig_layout` 直接**假設星形**
  (每個結構件都是 body 的直接子件),父子關係與 root 皆取自分析器 note 先驗。
  本器改由**部位相鄰幾何**推得,使 `--rig` 完全自決,且支援多跳肢體鏈(手→前臂→上臂→軀幹)。

界定(誠實):
  - 本器推的是**拓樸**(root + parent 邊),輸入取「結構件集合」為已知
    (effect vs structural 的語意分類是另一子問題;見檔尾 diagnose_include_effect)。
  - 軸向/手感微調仍屬美術(RULES A 類)。

演算法(deterministic adjacency):
  1. 各件多邊形**加密**(沿邊補點)→ 準確的件間最近距離。
  2. 件間接觸距離 d(a,b):加密點雲最近距離;若一件的點落在另一件內(重疊)→ d=0。
  3. **root(軀幹)** = 接觸度(在 τ 內相鄰的件數)最高者;平手取面積最大件。
     — 真實骨架軀幹是掛最多肢體的 hub;單鏈退化時面積 tiebreak 取最大件(軀幹)。
  4. **父邊** = 以「接觸距離為權重」的完全圖,自 root 跑 Dijkstra 最短路徑樹;
     每件 parent = 其到 root 最短接觸路徑上的前驅。
     — 星形:各件經 body 直達(權重小)→ 全掛 body;
       鏈形:遠端件經中間件轉(touching=小權重)→ recover 鏈,不強制星形。

真相來源:對 Award 機器人以 `infer_pivots.load_award_robot` 抽真值,truth 樹 = `ROBOT_TREE`。
"""
import sys, os, math
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from infer_pivots import _poly_points  # noqa: E402


# ---------------- 幾何:加密、點在多邊形內、接觸距離 ----------------
def densify(poly, step=2.0):
    """沿多邊形每條邊補點,使相鄰點間距 <= step。回傳 Mx2。"""
    P = _poly_points(poly)
    n = len(P)
    if n < 2:
        return P
    out = []
    for i in range(n):
        a = P[i]; b = P[(i + 1) % n]
        seg = b - a
        L = float(np.hypot(*seg))
        k = max(1, int(math.ceil(L / step)))
        for t in range(k):
            out.append(a + seg * (t / k))
    return np.asarray(out, dtype=np.float64)


def _point_in_poly(pts, poly):
    """numpy ray-casting:回傳 pts 各點是否在 poly(Nx2 閉多邊形)內。pts: Mx2 → bool[M]。"""
    P = _poly_points(poly)
    x = pts[:, 0]; y = pts[:, 1]
    inside = np.zeros(len(pts), dtype=bool)
    n = len(P)
    j = n - 1
    for i in range(n):
        xi, yi = P[i]; xj, yj = P[j]
        cond = ((yi > y) != (yj > y)) & (
            x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi)
        inside ^= cond
        j = i
    return inside


def contact_distance(polyA, polyB, step=2.0):
    """兩件接觸距離:加密邊界最近距離;若任一件點落入對方內(重疊)→ 0。"""
    A = densify(polyA, step); B = densify(polyB, step)
    if _point_in_poly(A, polyB).any() or _point_in_poly(B, polyA).any():
        return 0.0
    try:
        from scipy.spatial import cKDTree
        d = cKDTree(B).query(A, k=1)[0].min()
    except Exception:
        d = np.min(np.linalg.norm(A[:, None, :] - B[None, :, :], axis=2))
    return float(d)


def _part_scale(parts):
    """尺度基準:各件包圍盒對角線的最大值(軀幹尺度代理)。"""
    best = 1.0
    for p in parts.values():
        P = _poly_points(p)
        d = float(np.hypot(np.ptp(P[:, 0]), np.ptp(P[:, 1])))
        best = max(best, d)
    return best


def _part_area(poly):
    """多邊形面積(shoelace,絕對值)。"""
    P = _poly_points(poly)
    x = P[:, 0]; y = P[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


# ---------------- 拓樸推斷 ----------------
def contact_matrix(parts, step=2.0):
    names = list(parts.keys())
    n = len(names)
    D = np.zeros((n, n), dtype=np.float64)
    for i in range(n):
        for j in range(i + 1, n):
            d = contact_distance(parts[names[i]], parts[names[j]], step=step)
            D[i, j] = D[j, i] = d
    return names, D


def infer_root(parts, D=None, names=None, tau_frac=0.06):
    """root(軀幹)= **面積最大件**(軀幹是最大質量的 trunk);平手取接觸度最高。

    為何 area-primary 而非 degree-hub:degree-hub 只對星形對(軀幹掛多肢=hub);
    純肢體鏈中『中間件』degree 最高卻非 root(root 在鏈端)——真實軀幹的穩健幾何簽名是最大面積。
    degree 仍計算並回傳,作為 tiebreak 與診斷(重疊 composite 下常飽和,見 knowledge)。"""
    if D is None:
        names, D = contact_matrix(parts)
    scale = _part_scale(parts)
    tau = tau_frac * scale
    deg = (D <= tau).sum(axis=1) - 1  # 減自身(對角 0)
    areas = np.array([_part_area(parts[nm]) for nm in names])
    order = sorted(range(len(names)), key=lambda i: (-areas[i], -deg[i]))
    return names[order[0]], {names[i]: int(deg[i]) for i in range(len(names))}, tau


def _dijkstra_tree(names, D, root_idx):
    """完全圖(權重=接觸距離)自 root 跑 Dijkstra;回傳 parent 索引陣列(root=-1)。"""
    n = len(names)
    dist = np.full(n, np.inf); dist[root_idx] = 0.0
    parent = np.full(n, -1, dtype=int)
    visited = np.zeros(n, dtype=bool)
    for _ in range(n):
        u = -1; best = np.inf
        for i in range(n):
            if not visited[i] and dist[i] < best:
                best = dist[i]; u = i
        if u < 0:
            break
        visited[u] = True
        for v in range(n):
            if v == u or visited[v]:
                continue
            nd = dist[u] + D[u, v]
            if nd < dist[v]:
                dist[v] = nd; parent[v] = u
    return parent


def infer_tree(parts, tau_frac=0.06, step=2.0):
    """回傳 (root_name, tree{child:parent}, info)。tree 不含 root。"""
    names, D = contact_matrix(parts, step=step)
    root, deg, tau = infer_root(parts, D, names, tau_frac=tau_frac)
    ridx = names.index(root)
    par = _dijkstra_tree(names, D, ridx)
    tree = {names[i]: names[par[i]] for i in range(len(names)) if par[i] >= 0}
    info = dict(names=names, D=D, degree=deg, tau=tau, scale=_part_scale(parts))
    return root, tree, info


# ---------------- 對照/診斷 ----------------
def diagnose_include_effect(parts_with_effect, effect_names, tau_frac=0.06):
    """把 effect 件(如光暈:大面積、與多件重疊的背光)也當結構件推 → 展示會如何汙染樹,
    論證『結構 vs 特效角色分類』須作為輸入(honest boundary)。"""
    root, tree, info = infer_tree(parts_with_effect, tau_frac=tau_frac)
    corrupted = (root in effect_names) or any(
        p in effect_names or c in effect_names for c, p in tree.items())
    return root, tree, corrupted


if __name__ == "__main__":
    from infer_pivots import load_award_robot, ROBOT_TREE
    parts, truth, tree_truth, fid = load_award_robot()
    struct = {k: v for k, v in parts.items() if k != "機器人拆件/光暈"}
    root, tree, info = infer_tree(struct)
    print(f"scale={info['scale']:.1f}px  tau={info['tau']:.1f}px  degrees={info['degree']}")
    print(f"inferred root = {root}")
    print("inferred tree:")
    for c, p in tree.items():
        print(f"  {c:<18} -> {p}")
    print("truth tree:", {c: p for c, p in ROBOT_TREE.items()})
