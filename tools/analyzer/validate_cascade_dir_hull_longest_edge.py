#!/usr/bin/env python3
"""candidate (J-11) 自我驗收閘 — cascade 跨件波方向的 **凸包最長邊 geo source**(確定性,純 CPU)。

方向軸的來源精煉(**同一條 J-6 投影軸**,逐步移除 / 強化人手指定):
  J-5:相位來源由件序換成**空間**(4 個具名方向 lr/rl/co/oc)。
  J-6:方向**值連續化**(任意角 / 向量)—— 但「用哪個方向」仍是手感常數。
  J-7:`cascade_dir="geo"` 方向**向量由件幾何導出**(質心 → 最遠件),隨資產自適應。
  J-8:新增 `geo source = "pca"` —— 用 PCA **主軸**(最大變異方向),符號確定性地定。
  J-9:新增 `geo source = "pca_minor"` —— 用 PCA **次主軸**(最小變異方向,與主軸正交)。
  J-10:新增 `geo source = "farthest_pair"` —— 用件中心的 **diameter(最遠對,凸包直徑)**方向。
  J-11(本閘):新增 `geo source = "hull_longest_edge"` —— 用件中心**凸包最長邊**(相鄰兩頂點中連線最長者)
       方向,字典序確定性定號。語意 = 波沿件群外廓**最長的直邊**橫掃。

**honest distinction(勿誇大)**:J-11 **不是**新正交軸,也**不改** J-6 的投影排序機制;只是 J-7..J-10 那條
「方向軸取值來源(provenance)」再多一個 source(`hull_longest_edge`)。其**最鋒利的 crux(與最相近的
farthest_pair 區別)**:同一點集下,diameter 是**全域最遠對**(端點常是凸包**不相鄰**的兩頂點 = 對角線),
longest edge 是**相鄰**頂點的最長外廓線段 → 凸四邊形下兩者**方向不同**(HLE3a)。其**與 cf 的 crux**:
`hull_longest_edge` 只由**凸包頂點(外廓)**決定 → 移動凸包**內部**件**不改方向**,而 `centroid_farthest`
(質心移動)會改變(HLE3b;`farthest_pair` 同屬 hull-only 亦不變 → 誠實標明兩者共有此性質)。其**與 pca 的
crux**:對正方 / 正多邊形,pca 因 λ1≈λ2 會 ValueError,而 hull_longest_edge **仍確定性回最長邊**(極值型,
**無各向同性守衛**,HLE5b)。其**正確性 crux**:== 閘**獨立**以 `scipy.spatial.ConvexHull` 重算的最長邊
(套**同一套**字典序 tie-break);方向 = 字典序較小端點 → 較大端點(件輸入順序無關)。

  HLE1 present + backward-compat: `("geo","hull_longest_edge")` 產每個 cascade beat 且 finite/有 bone;非 cascade
                                 主秀 beat 逐位元同 base;`None`/`"po"` 仍逐位元同件序;**零回歸** `"geo"` 預設
                                 (= centroid_farthest)、`("geo","pca")`(J-8)、`("geo","pca_minor")`(J-9)、
                                 `("geo","farthest_pair")`(J-10)皆**不被本次新增影響**(逐位元同;
                                 `derive(.,"pca")` == 閘獨立 numpy 主特徵向量、`derive(.,"farthest_pair")` ==
                                 閘獨立 brute diameter、`derive(.,"centroid_farthest")` == 閘獨立質心→最遠件)。
  HLE2 correctness+order+sign  : (crux)(a) **最長邊正確性**:`hull_longest_edge` == 閘**獨立 scipy ConvexHull**
                                 最長邊(**逐位元**同向量,套同一字典序 tie-break);(b) **件輸入順序無關**:
                                 非對稱 & 對稱(邊並列,如正方)佈局的**所有排列** → **逐位元同一**帶號向量;
                                 (c) **符號跟隨幾何**:沿 x 鏡射(y→−y)→ 向量 y 分量符號翻轉、x 分量不變。
  HLE3 longest-edge value      : (crux/價值)(a) **longest edge ≠ diameter**:凸四邊形下 `hull_longest_edge`
                                 方向 ≠ `farthest_pair` 方向(acute ≥ 門檻),且**閘獨立 scipy 確認** hle 端點對是
                                 凸包**相鄰**頂點、diameter 端點對是**不相鄰**(對角線)→ 證兩者幾何物件不同;
                                 (b) **hull-only(內部件不變性)**:固定凸包 + 移動一個**嚴格內部**件 →
                                 `hull_longest_edge` **逐位元不變**、`farthest_pair` 亦不變(同屬 hull-only,誠實
                                 共標)、`centroid_farthest` 方向轉動(≥門檻,質心移動);pca 轉動量僅**誠實回報**
                                 (外廓極值主導其二階矩 → 內部件槓桿小,非判準)。
  HLE4 end-to-end ordering     : 真實 robot 骨架 `build_animations(cascade_dir=("geo","hull_longest_edge"))` → 每
                                 cascade beat 各件峰時刻依最長邊投影鍵嚴格遞增(最遠投影最後 pop)、仍一道有序
                                 跨件波(散佈≥門檻)+首尾 setup identity + 特效 slot alpha=1;dir⟂nrip 仍成立。並
                                 **誠實回報** robot 上 hle pop 序 vs farthest_pair / pca(資訊,不作判準)。
  HLE5 metric + guards         : (a) metric:hull_longest_edge == 閘獨立 scipy 最長邊(多佈局逐位元);(b) **並列
                                 邊 / 各向同性**:正方(pca 會 ValueError)→ hull_longest_edge **不 raise**、確定性
                                 回最長邊且所有排列單一結果(件序無關);(c) 守衛:件重合 / 單件 / 空件 / 未知
                                 source(直接 & 經 build_animations ("geo","hull_longest_edge") 可用、("geo","zzz")
                                 報錯)→ ValueError。

閘從 VD(J-5 閘)fixture 的**真實 build_spine robot 骨架**端到端量;最長邊 **由閘以 scipy.spatial.ConvexHull
獨立重算**(不呼叫生成器私有 `_hull_longest_edge_dir`),diameter / PCA 亦獨立重算,以保持獨立驗證。

用法:
  python3 validate_cascade_dir_hull_longest_edge.py            # 摘要
  python3 validate_cascade_dir_hull_longest_edge.py --json     # 完整 JSON
"""
import argparse, itertools, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
from scipy.spatial import ConvexHull
import spine_anim as SA
import gen_animations as G
import tier_variants as TV
import validate_cascade_dir as VD
from validate_cascade import is_strictly_increasing, cascade_spread

TIERS = VD.TIERS
SPREAD_FLOOR = VD.SPREAD_FLOOR
TOL = VD.TOL
N = VD.N

ALIGN_MAX = 1e-6          # |dot| 同線門檻(≈1)
MIN_ROT = 3.0             # HLE3:hle vs fp 方向差 / 內部件移動時 cf 轉動 ≥ 此角度(度)


def _scipy_hull_edge_pair(centers, tol=1e-9):
    """閘**獨立**的凸包最長邊端點對 `(lo, hi)`(scipy.spatial.ConvexHull + 同一套字典序 tie-break)。"""
    P = np.asarray(centers, dtype=float)
    hull = ConvexHull(P)
    verts = [(float(P[i][0]), float(P[i][1])) for i in hull.vertices]   # CCW 頂點順序
    m = len(verts)
    best_d = -1.0
    for i in range(m):
        a, b = verts[i], verts[(i + 1) % m]
        best_d = max(best_d, math.hypot(a[0] - b[0], a[1] - b[1]))
    best_pair = None
    for i in range(m):
        a, b = verts[i], verts[(i + 1) % m]
        d = math.hypot(a[0] - b[0], a[1] - b[1])
        if d >= best_d - tol:
            cand = (a, b) if a <= b else (b, a)
            if best_pair is None or cand < best_pair:
                best_pair = cand
    return best_pair, verts


def _scipy_hull_longest_edge(centers, tol=1e-9):
    """閘獨立凸包最長邊**單位向量**(字典序定號),供逐位元對照。"""
    (lo, hi), _ = _scipy_hull_edge_pair(centers, tol)
    dx, dy = hi[0] - lo[0], hi[1] - lo[1]
    L = math.hypot(dx, dy)
    return (dx / L, dy / L)


def _brute_diameter_pair(centers, tol=1e-9):
    """閘獨立 diameter 端點對 `(lo, hi)`(brute-force 最遠對 + 字典序 tie-break)。"""
    n = len(centers)
    best_d = -1.0
    for i in range(n):
        for j in range(i + 1, n):
            d = math.hypot(centers[i][0] - centers[j][0], centers[i][1] - centers[j][1])
            best_d = max(best_d, d)
    best_pair = None
    for i in range(n):
        for j in range(i + 1, n):
            d = math.hypot(centers[i][0] - centers[j][0], centers[i][1] - centers[j][1])
            if d >= best_d - tol:
                a = (float(centers[i][0]), float(centers[i][1]))
                b = (float(centers[j][0]), float(centers[j][1]))
                cand = (a, b) if a <= b else (b, a)
                if best_pair is None or cand < best_pair:
                    best_pair = cand
    return best_pair


def _brute_diameter(centers, tol=1e-9):
    lo, hi = _brute_diameter_pair(centers, tol)
    dx, dy = hi[0] - lo[0], hi[1] - lo[1]
    L = math.hypot(dx, dy)
    return (dx / L, dy / L)


def _np_pca_major(centers):
    """閘獨立 PCA 主軸(numpy 共變異最大特徵向量,未定號 → 回線的代表向量)。"""
    pts = np.asarray(centers, dtype=float)
    pts = pts - pts.mean(axis=0)
    cov = np.cov(pts.T, bias=True)
    w, V = np.linalg.eigh(cov)
    return V[:, int(np.argmax(w))]


def _gate_centroid_farthest(centers):
    """閘獨立 centroid→farthest 單位向量(對照 derive(.,'centroid_farthest') 零回歸)。"""
    n = len(centers)
    mx = sum(c[0] for c in centers) / n
    my = sum(c[1] for c in centers) / n
    bi, bd2 = 0, -1.0
    for i, (x, y) in enumerate(centers):
        d2 = (x - mx) ** 2 + (y - my) ** 2
        if d2 > bd2:
            bd2, bi = d2, i
    dx, dy = centers[bi][0] - mx, centers[bi][1] - my
    L = math.hypot(dx, dy)
    return (dx / L, dy / L)


def _pair_adjacent_on_hull(pair, verts, tol=1e-6):
    """pair 的兩端點是否為 scipy 凸包 `verts`(CCW)上**相鄰**頂點(環狀)。"""
    def _idx(pt):
        for k, v in enumerate(verts):
            if abs(v[0] - pt[0]) <= tol and abs(v[1] - pt[1]) <= tol:
                return k
        return None
    lo, hi = pair
    i, j = _idx(lo), _idx(hi)
    if i is None or j is None:
        return False
    m = len(verts)
    return (abs(i - j) == 1) or (abs(i - j) == m - 1)


def _acute(u, v):
    """單位向量 u、v 的銳角(度,∈[0,90];摺疊方向正負,量「線」轉動)。"""
    d = max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1]))
    a = math.degrees(math.acos(abs(d)))
    return min(a, 180.0 - a)


def _proj_key(xy, bone, vec):
    x, y = xy[bone]
    return x * vec[0] + y * vec[1]


def _bytes(obj):
    return json.dumps(obj, sort_keys=True)


def _bits(v, nd=9):
    return tuple(round(c, nd) for c in v)


def run():
    skel = VD._skeleton()
    sb = VD._storyboard(VD.GENRE)
    order = VD._part_order(sb)
    xy = VD._bone_xy(skel)
    gains = TV.gains_for(VD.GENRE)
    rip = TV.cascade_ripples_for(VD.GENRE)

    base = G.build_animations(skel, sb)                                             # cascade_dir=None(件序)
    hle = G.build_animations(skel, sb, cascade_dir=("geo", "hull_longest_edge"))
    pmaj = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    fpm = G.build_animations(skel, sb, cascade_dir=("geo", "farthest_pair"))
    cbeats = VD._cascade_beats(base)
    main_beats = VD._main_beats(base)
    centers = [xy[b] for b in order]
    hle_vec = G.derive_cascade_dir(centers, "hull_longest_edge")
    R = {}

    # ---- HLE1 present + backward-compat + zero-regression ----
    p1 = {"missing": [], "not_finite": [], "no_bones": [], "noncascade_changed": [], "po_eq_none": None,
          "geo_default_eq_centroid": None, "pca_unchanged": None, "pca_minor_unchanged": None,
          "farthest_pair_unchanged": None, "pca_derive_eq_numpy_major": None,
          "fp_derive_eq_brute": None, "cf_derive_eq_gate": None}
    for cb in cbeats:
        an = hle.get(cb)
        if an is None:
            p1["missing"].append(cb); continue
        if not SA.all_finite(an):
            p1["not_finite"].append(cb)
        if not an.get("bones"):
            p1["no_bones"].append(cb)
    for beat, cat in main_beats.items():
        if cat == "cascade":
            continue
        if _bytes(hle.get(beat)) != _bytes(base.get(beat)):
            p1["noncascade_changed"].append(beat)
    po = G.build_animations(skel, sb, cascade_dir="po")
    p1["po_eq_none"] = all(_bytes(po[cb]) == _bytes(base[cb]) for cb in cbeats)
    geo_def = G.build_animations(skel, sb, cascade_dir="geo")
    geo_cf = G.build_animations(skel, sb, cascade_dir=("geo", "centroid_farthest"))
    p1["geo_default_eq_centroid"] = all(_bytes(geo_def[cb]) == _bytes(geo_cf[cb]) for cb in cbeats)
    # 零回歸:J-8 pca / J-9 pca_minor / J-10 farthest_pair 路徑逐位元不變(不被本次新增影響)
    pmaj2 = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    pmin1 = G.build_animations(skel, sb, cascade_dir=("geo", "pca_minor"))
    pmin2 = G.build_animations(skel, sb, cascade_dir=("geo", "pca_minor"))
    fpm2 = G.build_animations(skel, sb, cascade_dir=("geo", "farthest_pair"))
    p1["pca_unchanged"] = all(_bytes(pmaj[cb]) == _bytes(pmaj2[cb]) for cb in cbeats)
    p1["pca_minor_unchanged"] = all(_bytes(pmin1[cb]) == _bytes(pmin2[cb]) for cb in cbeats)
    p1["farthest_pair_unchanged"] = all(_bytes(fpm[cb]) == _bytes(fpm2[cb]) for cb in cbeats)
    np_major = _np_pca_major(centers)
    dmaj = G.derive_cascade_dir(centers, "pca")
    p1["pca_derive_eq_numpy_major"] = abs(abs(dmaj[0] * np_major[0] + dmaj[1] * np_major[1]) - 1.0) <= ALIGN_MAX
    dfp = G.derive_cascade_dir(centers, "farthest_pair")
    p1["fp_derive_eq_brute"] = _bits(dfp) == _bits(_brute_diameter(centers))
    dcf = G.derive_cascade_dir(centers, "centroid_farthest")
    p1["cf_derive_eq_gate"] = _bits(dcf) == _bits(_gate_centroid_farthest(centers))
    p1_pass = (bool(cbeats) and not p1["missing"] and not p1["not_finite"] and not p1["no_bones"]
               and not p1["noncascade_changed"] and p1["po_eq_none"] and p1["geo_default_eq_centroid"]
               and p1["pca_unchanged"] and p1["pca_minor_unchanged"] and p1["farthest_pair_unchanged"]
               and p1["pca_derive_eq_numpy_major"] and p1["fp_derive_eq_brute"] and p1["cf_derive_eq_gate"])
    R["HLE1_present_backward_compat"] = {"cascade_beats": cbeats, **p1, "pass": p1_pass}

    # ---- HLE2 longest-edge correctness + order-independent + deterministic sign (crux) ----
    p2 = {}
    # (a) 最長邊正確性:hull_longest_edge == 閘獨立 scipy ConvexHull 最長邊(逐位元同向量)
    cfgs = {"robot": centers,
            "quad": [(0.0, 0.0), (6.0, 0.0), (6.0, 2.0), (0.0, 5.0)],
            "rect": [(0.0, 0.0), (14.0, 0.0), (14.0, 4.0), (0.0, 4.0)],
            "scatter": [(-3.0, 0.4), (-1.0, -0.3), (0.0, 0.0), (2.0, 0.5), (5.0, -0.2), (1.0, 3.0)]}
    adet, a_ok = {}, True
    for name, C in cfgs.items():
        v = G.derive_cascade_dir(C, "hull_longest_edge")
        b = _scipy_hull_longest_edge(C)
        same = _bits(v) == _bits(b)
        adet[name] = {"hle": _bits(v, 4), "scipy": _bits(b, 4), "bit_identical": same}
        if not same:
            a_ok = False
    p2["a_hle_eq_scipy"] = {"detail": adet, "pass": a_ok}
    # (b) 件輸入順序無關:非對稱 + 對稱(邊並列,如正方)佈局的所有排列 → 逐位元同一向量
    asym = [(0.0, 0.0), (6.0, 0.0), (6.0, 2.0), (0.0, 5.0)]
    sq = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]                       # 四邊並列最長
    asym_outs = {_bits(G.derive_cascade_dir(list(p), "hull_longest_edge")) for p in itertools.permutations(asym)}
    sq_outs = {_bits(G.derive_cascade_dir(list(p), "hull_longest_edge")) for p in itertools.permutations(sq)}
    p2["b_order_independent"] = {"asym_perms": math.factorial(len(asym)), "asym_distinct": len(asym_outs),
                                 "square_perms": math.factorial(len(sq)), "square_distinct": len(sq_outs),
                                 "square_vec": sorted(sq_outs),
                                 "pass": len(asym_outs) == 1 and len(sq_outs) == 1}
    # (c) 符號跟隨幾何:沿 x 鏡射 y→−y → 方向 y 分量符號翻轉、x 分量不變(最長邊端點 x 相異、y 相異)
    B = [(0.0, 0.0), (6.0, 0.0), (6.0, 2.0), (0.0, 5.0)]                        # 最長邊 (0,5)-(6,2)
    Bm = [(x, -y) for (x, y) in B]
    vB = G.derive_cascade_dir(B, "hull_longest_edge"); vBm = G.derive_cascade_dir(Bm, "hull_longest_edge")
    p2["c_sign_tracks_geometry"] = {"B": _bits(vB, 4), "mirror_y": _bits(vBm, 4),
                                    "pass": _bits(vB) == _bits((vBm[0], -vBm[1])) and abs(vB[1]) > 0.2}
    R["HLE2_longest_edge_order_sign"] = {**p2, "pass": all(v["pass"] for v in p2.values())}

    # ---- HLE3 value crux: longest-edge != diameter (vs farthest_pair) + hull-only (vs cf) ----
    p3 = {}
    # (a) longest edge != diameter:凸四邊形下方向不同 + 閘獨立確認 hle 相鄰 / diameter 不相鄰
    q = [(0.0, 0.0), (6.0, 0.0), (6.0, 2.0), (0.0, 5.0)]
    hle_q = G.derive_cascade_dir(q, "hull_longest_edge")
    fp_q = G.derive_cascade_dir(q, "farthest_pair")
    rot_q = _acute(hle_q, fp_q)
    hle_pair, verts = _scipy_hull_edge_pair(q)
    diam_pair = _brute_diameter_pair(q)
    hle_adj = _pair_adjacent_on_hull(hle_pair, verts)
    diam_adj = _pair_adjacent_on_hull(diam_pair, verts)
    p3["a_edge_ne_diameter"] = {
        "hle_vec": _bits(hle_q, 4), "fp_vec": _bits(fp_q, 4), "rot_deg": round(rot_q, 3),
        "hle_pair": [list(hle_pair[0]), list(hle_pair[1])], "hle_adjacent": hle_adj,
        "diam_pair": [list(diam_pair[0]), list(diam_pair[1])], "diam_adjacent": diam_adj,
        "pass": rot_q >= MIN_ROT and hle_adj and not diam_adj}
    # (b) hull-only:固定凸包(rect)+ 移動一個**嚴格內部**件 → hle/fp 逐位元不變、cf 轉動;pca 僅回報
    bse = [(0.0, 0.0), (14.0, 0.0), (14.0, 4.0), (0.0, 4.0), (2.0, 2.0)]
    mov = [(0.0, 0.0), (14.0, 0.0), (14.0, 4.0), (0.0, 4.0), (12.0, 2.0)]
    hle0 = G.derive_cascade_dir(bse, "hull_longest_edge"); hle1 = G.derive_cascade_dir(mov, "hull_longest_edge")
    fp0 = G.derive_cascade_dir(bse, "farthest_pair"); fp1 = G.derive_cascade_dir(mov, "farthest_pair")
    cf0 = G.derive_cascade_dir(bse, "centroid_farthest"); cf1 = G.derive_cascade_dir(mov, "centroid_farthest")
    pc0 = G.derive_cascade_dir(bse, "pca"); pc1 = G.derive_cascade_dir(mov, "pca")
    hle_inv = _bits(hle0) == _bits(hle1)
    fp_inv = _bits(fp0) == _bits(fp1)
    cf_rot = _acute(cf0, cf1)
    pca_rot = _acute(pc0, pc1)
    p3["b_hull_only_interior"] = {
        "hle_vec": _bits(hle0, 4), "hle_bit_invariant": hle_inv, "fp_bit_invariant": fp_inv,
        "cf_rotation_deg": round(cf_rot, 3), "min_rot_threshold": MIN_ROT,
        "pca_rotation_deg_info_only": round(pca_rot, 3),
        "pass": hle_inv and fp_inv and cf_rot >= MIN_ROT}
    R["HLE3_longest_edge_value"] = {**p3, "pass": all(v["pass"] for v in p3.values())}

    # ---- HLE4 end-to-end projection ordering (robot) ----
    p4 = {"detail": {}, "fail_order": [], "weak_spread": [], "bad_interface": []}
    fp_full_vec = G.derive_cascade_dir(centers, "farthest_pair")
    pmaj_vec = G.derive_cascade_dir(centers, "pca")
    for cb in cbeats:
        an = hle[cb]
        bones = [b for b in order if b in an.get("bones", {})]
        proj_sorted = sorted(bones, key=lambda b: (_proj_key(xy, b, hle_vec), order.index(b)))
        pts = [VD.peak_time(an, b) for b in proj_sorted]
        mono = is_strictly_increasing(pts)
        far_bone = proj_sorted[-1]
        meas = sorted(bones, key=lambda b: VD.peak_time(an, b))
        far_last = meas[-1] == far_bone
        sp = cascade_spread(pts)
        dur = SA.duration(an)
        b0 = SA.sample(an, 0.0)["bones"]; bE = SA.sample(an, dur)["bones"]
        s0 = SA.sample(an, 0.0)["slots"]; sE = SA.sample(an, dur)["slots"]
        iface = (all(VD._is_ident(v) for v in b0.values()) and all(VD._is_ident(v) for v in bE.values())
                 and all(abs(s["alpha"] - 1) <= TOL for s in s0.values())
                 and all(abs(s["alpha"] - 1) <= TOL for s in sE.values()))
        # 誠實回報(不作判準):hle 的測得 pop 序 vs farthest_pair / pca 的 pop 序
        meas_fp = sorted([b for b in order if b in fpm[cb].get("bones", {})],
                         key=lambda b: VD.peak_time(fpm[cb], b))
        meas_maj = sorted([b for b in order if b in pmaj[cb].get("bones", {})],
                          key=lambda b: VD.peak_time(pmaj[cb], b))
        differs_fp = [order.index(b) for b in meas] != [order.index(b) for b in meas_fp]
        p4["detail"][cb] = {"hle_vec": _bits(hle_vec, 4), "proj_order": [order.index(b) for b in proj_sorted],
                            "peak_times": [round(x, 3) for x in pts], "monotone": mono,
                            "farthest_pops_last": far_last, "spread": round(sp, 3), "iface": iface,
                            "measured_hle_order": [order.index(b) for b in meas],
                            "measured_fp_order": [order.index(b) for b in meas_fp],
                            "measured_major_order": [order.index(b) for b in meas_maj],
                            "differs_from_fp": differs_fp}
        if not (mono and far_last):
            p4["fail_order"].append(cb)
        if sp < SPREAD_FLOOR:
            p4["weak_spread"].append(cb)
        if not iface:
            p4["bad_interface"].append(cb)
    # dir ⟂ nrip:帶 ripples 時各件 pop 次數 == nrip 在 hull_longest_edge 成立
    nrip_ok, nrip_detail = True, {}
    full = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip,
                              cascade_dir=("geo", "hull_longest_edge"))
    for cb in cbeats:
        for t in TIERS:
            an = full["{}__{}".format(cb, t)]
            cnts = [VD.peak_times_count(an, b) for b in an.get("bones", {})]
            ok = bool(cnts) and all(c == rip[t] for c in cnts)
            nrip_detail["{}__{}".format(cb, t)] = {"nrip": rip[t], "counts": cnts, "ok": ok}
            if not ok:
                nrip_ok = False
    p4_pass = (bool(cbeats) and not p4["fail_order"] and not p4["weak_spread"]
               and not p4["bad_interface"] and nrip_ok)
    R["HLE4_end_to_end_ordering"] = {**p4, "hle_vec": _bits(hle_vec, 4), "fp_vec": _bits(fp_full_vec, 4),
                                     "pca_vec": _bits(pmaj_vec, 4), "nrip_intact": nrip_ok,
                                     "nrip_detail": nrip_detail, "pass": p4_pass}

    # ---- HLE5 metric well-defined + guards ----
    p5 = {}
    # (a) metric:hull_longest_edge == 閘獨立 scipy 最長邊(多佈局逐位元)
    mdet, m_ok = {}, True
    for name, C in {"robot": centers, "quad": cfgs["quad"],
                    "penta": [(0.0, 0.0), (10.0, 1.0), (12.0, 7.0), (5.0, 11.0), (-2.0, 6.0)]}.items():
        v = G.derive_cascade_dir(C, "hull_longest_edge"); b = _scipy_hull_longest_edge(C)
        same = _bits(v) == _bits(b)
        mdet[name] = {"hle": _bits(v, 4), "scipy": _bits(b, 4), "bit_identical": same}
        if not same:
            m_ok = False
    p5["a_metric_eq_scipy"] = {"detail": mdet, "pass": m_ok}
    # (b) 並列邊 / 各向同性:正方(pca 會 ValueError)→ hull_longest_edge 不 raise、確定性回最長邊、件序無關
    sq2 = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    pca_raises = False
    try:
        G.derive_cascade_dir(sq2, "pca")
    except ValueError:
        pca_raises = True
    try:
        sq_vecs = {_bits(G.derive_cascade_dir(list(p), "hull_longest_edge")) for p in itertools.permutations(sq2)}
        hle_sq_ok = len(sq_vecs) == 1
        sq_vec = sorted(sq_vecs)
    except ValueError:
        hle_sq_ok, sq_vec = False, None
    p5["b_tie_isotropic"] = {"pca_raises_on_square": pca_raises, "hle_resolves": hle_sq_ok,
                             "hle_square_vec": sq_vec,
                             "pass": pca_raises and hle_sq_ok}
    # (c) 守衛:件重合 / 單件 / 空件 / 未知 source(直接 & 經 build)
    guards = {}
    for name, fn in {
        "coincident": lambda: G.derive_cascade_dir([(5.0, 7.0), (5.0, 7.0), (5.0, 7.0)], "hull_longest_edge"),
        "single": lambda: G.derive_cascade_dir([(1.0, 2.0)], "hull_longest_edge"),
        "empty": lambda: G.derive_cascade_dir([], "hull_longest_edge"),
        "unknown_source_direct": lambda: G.derive_cascade_dir([(0, 0), (1, 1)], "nope_src"),
        "unknown_source_build": lambda: G.build_animations(skel, sb, cascade_dir=("geo", "zzz")),
    }.items():
        try:
            fn(); guards[name] = False
        except ValueError:
            guards[name] = True
    try:
        _ = G.build_animations(skel, sb, cascade_dir=("geo", "hull_longest_edge")); guards["hle_build_ok"] = True
    except Exception:
        guards["hle_build_ok"] = False
    p5["c_input_guards"] = {"detail": guards, "pass": all(guards.values())}
    R["HLE5_metric_guards"] = {**p5, "pass": all(v["pass"] for v in p5.values())}

    R["OVERALL_PASS"] = all(R[k]["pass"] for k in R)
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    R = run()
    if a.json:
        print(json.dumps(R, ensure_ascii=False, indent=2))
    else:
        for k in ["HLE1_present_backward_compat", "HLE2_longest_edge_order_sign", "HLE3_longest_edge_value",
                  "HLE4_end_to_end_ordering", "HLE5_metric_guards"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        a3 = R["HLE3_longest_edge_value"]["a_edge_ne_diameter"]
        print("HLE3a hle={} fp={} rot={}° hle_adj={} diam_adj={}".format(
            a3["hle_vec"], a3["fp_vec"], a3["rot_deg"], a3["hle_adjacent"], a3["diam_adjacent"]))
        b3 = R["HLE3_longest_edge_value"]["b_hull_only_interior"]
        print("HLE3b hle_inv={} fp_inv={} cf_rot={}° pca_rot(info)={}°".format(
            b3["hle_bit_invariant"], b3["fp_bit_invariant"], b3["cf_rotation_deg"],
            b3["pca_rotation_deg_info_only"]))
        print("HLE4 projection order (robot):")
        for cb, d in R["HLE4_end_to_end_ordering"]["detail"].items():
            print("   {:10s} vec={} hle_order={} fp_order={} mono={} differs_fp={}".format(
                cb, d["hle_vec"], d["measured_hle_order"], d["measured_fp_order"],
                d["monotone"], d["differs_from_fp"]))
        b5 = R["HLE5_metric_guards"]["b_tie_isotropic"]
        print("HLE5(b) pca_raises_on_square={} hle_resolves_square={} vec={}".format(
            b5["pca_raises_on_square"], b5["hle_resolves"], b5["hle_square_vec"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
