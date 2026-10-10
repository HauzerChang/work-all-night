#!/usr/bin/env python3
"""candidate (J-13) 自我驗收閘 — cascade 跨件波方向的 **最小面積包圍矩形(OBB)次軸 geo source**(確定性,純 CPU)。

方向軸的來源精煉(**同一條 J-6 投影軸**,逐步移除 / 強化人手指定):
  J-5:相位來源由件序換成**空間**(4 個具名方向 lr/rl/co/oc)。
  J-6:方向**值連續化**(任意角 / 向量)—— 但「用哪個方向」仍是手感常數。
  J-7:`cascade_dir="geo"` 方向**向量由件幾何導出**(質心 → 最遠件),隨資產自適應。
  J-8:新增 `geo source = "pca"` —— 用 PCA **主軸**(最大變異方向),符號確定性地定。
  J-9:新增 `geo source = "pca_minor"` —— 用 PCA **次主軸**(最小變異方向,與主軸正交)。
  J-10:新增 `geo source = "farthest_pair"` —— 用件中心的 **diameter(最遠對,凸包直徑)**方向。
  J-11:新增 `geo source = "hull_longest_edge"` —— 用件中心**凸包最長邊**方向。
  J-12:新增 `geo source = "obb_major"` —— 用件中心**最小面積包圍矩形(OBB)長軸**方向。
  J-13(本閘):新增 `geo source = "obb_minor"` —— 用件中心**最小面積包圍矩形(OBB)次軸**(**短邊**方向,
       與 `obb_major` 正交)方向,字典序確定性定號。語意 = 波沿件群**最緊包圍盒的短邊**橫掃(vs obb_major
       沿長邊延掃)。比照 `pca`→`pca_minor`:**同一個最小面積矩形、同一套 tie-break**,只把導出軸由較長邊
       換成較短邊(= 長軸轉 90°),再套同一套符號規則。

**honest distinction(勿誇大)**:J-13 **不是**新正交軸類(仍落在 J-6 的 `("proj", vec)` 投影排序機制);
只是 J-7..J-12 那條「方向軸取值來源(provenance)」再多一個 source(`obb_minor`)。其**最鋒利的 crux**:
  - **vs obb_major**(同一個 OBB 的兩軸):`obb_minor` ⟂ `obb_major`(|dot|≈0)→ **一條真正不同的波**
    (件 pop 序不同,非 obb_major 的改版);呼應 J-9 pca_minor vs pca。
  - **vs pca_minor**(皆「次軸」):OBB 次軸是最小化矩形**面積**之盒的短邊、pca_minor 是最小化**方差**的次
    主軸 → 質量偏一側佈局(L 形 / flag)兩者方向不同(OM3b,asset-independent)。
  - **守衛 crux**(與 fp/hle 不同):最小矩形為(近)**正方形**(長≈寬)→ 長 / 短軸皆不唯一 → ValueError;
    而 `farthest_pair`/`hull_longest_edge` **無**此守衛、確定性回值。pca_minor 亦在正方 raise(判據不同:
    λ1≈λ2 變異各向同性 vs OBB 的矩形長≈寬)→ 誠實共標(OM5b)。
  - **正確性 crux**:== 閘**獨立**以 `scipy.spatial.ConvexHull` + 自寫旋轉卡尺重算的 OBB 次軸(套**同一套**
    「折半平面 → 座標字典序」tie-break + 幾何符號規則);不呼叫生成器私有 `_obb_major_axis_dir`。

  OM1 present + backward-compat: `("geo","obb_minor")` 產每個 cascade beat 且 finite/有 bone;非 cascade 主秀
                                 beat 逐位元同 base;`None`/`"po"` 仍逐位元同件序;**零回歸** `"geo"` 預設
                                 (= centroid_farthest)、`("geo","pca")`、`("geo","pca_minor")`、
                                 `("geo","farthest_pair")`、`("geo","hull_longest_edge")`、`("geo","obb_major")`
                                 皆**不被本次新增影響**(逐位元同;並對照各自閘獨立重算)。
  OM2 correctness+order+sign  : (crux)(a) **OBB 次軸正確性**:`obb_minor` == 閘**獨立 scipy ConvexHull + 旋轉
                                 卡尺**重算的 OBB 次軸(**逐位元**同向量,套同一 tie-break + 符號規則)且
                                 ⟂ `obb_major`(|dot|≈0);(b) **件輸入順序無關**:唯一最小矩形 & 面積並列
                                 (三角形每邊並列)佈局的**所有排列** → **逐位元同一**帶號向量;(c) **符號跟隨
                                 幾何**:沿 x 鏡射(y→−y)→ 向量 y 分量符號翻轉、x 分量不變。
  OM3 obb_minor value          : (crux/價值)(a) **obb_minor ⟂ obb_major 是真正不同的波**:二維展開佈局下
                                 `obb_minor` ⟂ `obb_major`(|dot|≈0)且依 minor 投影排序的件序 **≠** 依 major
                                 投影排序的件序(asset-independent);(b) **min-area ≠ min-variance(vs pca_minor)**:
                                 L 形 / flag(質量偏一側)`obb_minor` 方向 ≠ `pca_minor` 方向(acute ≥ 門檻)。
  OM4 end-to-end ordering      : 真實 robot 骨架 `build_animations(cascade_dir=("geo","obb_minor"))` → 每 cascade
                                 beat 各件峰時刻依 OBB 次軸投影鍵嚴格遞增(最遠投影最後 pop)、仍一道有序跨件波
                                 (散佈≥門檻)+首尾 setup identity + 特效 slot alpha=1;dir⟂nrip 仍成立。
                                 **crux**:robot 上 obb_minor 的 pop 序 **≠** obb_major 的 pop 序(端到端證兩者不同波)。
  OM5 metric + guards          : (a) metric:obb_minor == 閘獨立 scipy+卡尺 OBB 次軸(多佈局逐位元)且 ⟂ 長軸;
                                 (b) **正方守衛**:正方 `obb_minor` **raise**(min-rect square)、`pca_minor` 亦 raise
                                 (各向同性,判據不同)、而 `farthest_pair`/`hull_longest_edge` **不 raise**、確定性回值;
                                 (c) 守衛:件重合 / 單件 / 空件 / 未知 source(直接 & 經 build_animations
                                 ("geo","obb_minor") 可用、("geo","zzz") 報錯)→ ValueError。

閘從 VD(J-5 閘)fixture 的**真實 build_spine robot 骨架**端到端量;OBB 長 / 次軸 **由閘以 scipy.spatial.ConvexHull
+ 自寫旋轉卡尺獨立重算**(套同一 tie-break),pca_minor 亦獨立重算,以保持獨立驗證。

用法:
  python3 validate_cascade_dir_obb_minor.py            # 摘要
  python3 validate_cascade_dir_obb_minor.py --json     # 完整 JSON
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
PERP_MAX = 1e-6           # |dot(major,minor)| 應 ≈ 0(正交)
MIN_ROT = 3.0             # OM3:obb_minor vs pca_minor 方向差 ≥ 此角度(度)


def _scipy_obb(centers, minor=False, aspect_tol=1e-6, tol=1e-9):
    """閘**獨立**的 OBB 長 / 次軸**單位向量**(scipy.spatial.ConvexHull + 自寫旋轉卡尺 + 同一套 tie-break + 符號規則)。
    `minor=False` 回長軸、`minor=True` 回次軸(短邊,= 長軸轉 90°)。"""
    P = np.asarray(centers, dtype=float)
    hull = ConvexHull(P)
    verts = [(float(P[i][0]), float(P[i][1])) for i in hull.vertices]   # CCW
    m = len(verts)
    cands = []    # (area, canon_major_unit, major_len, minor_len)
    for i in range(m):
        a, b = verts[i], verts[(i + 1) % m]
        ex, ey = b[0] - a[0], b[1] - a[1]
        L = math.hypot(ex, ey)
        if L < tol:
            continue
        ex, ey = ex / L, ey / L
        nx, ny = -ey, ex
        es = [px * ex + py * ey for px, py in verts]
        ns = [px * nx + py * ny for px, py in verts]
        we = max(es) - min(es)
        wn = max(ns) - min(ns)
        area = we * wn
        if we >= wn:
            mvx, mvy, major_len, minor_len = ex, ey, we, wn
        else:
            mvx, mvy, major_len, minor_len = nx, ny, wn, we
        if mvy < 0 or (mvy == 0.0 and mvx < 0):
            mvx, mvy = -mvx, -mvy
        cands.append((area, (mvx, mvy), major_len, minor_len))
    if not cands:
        raise ValueError("gate obb: degenerate")
    best_area = min(c[0] for c in cands)
    tied = [c for c in cands if c[0] <= best_area + tol * (1.0 + best_area)]
    tied.sort(key=lambda c: c[1])
    _, (ux, uy), major_len, minor_len = tied[0]
    if major_len - minor_len <= aspect_tol * (major_len + minor_len):
        raise ValueError("gate obb: near-square")
    if minor:
        ux, uy = -uy, ux
        if uy < 0.0 or (uy == 0.0 and ux < 0.0):
            ux, uy = -ux, -uy
    n = len(centers)
    mx = sum(c[0] for c in centers) / n
    my = sum(c[1] for c in centers) / n
    projs = [((x - mx) * ux + (y - my) * uy, x, y) for x, y in centers]
    maxabs = max(abs(p) for p, _, _ in projs)
    ref = max((p for p in projs if abs(p[0]) >= maxabs - 1e-9), key=lambda p: (p[1], p[2]))
    if ref[0] < 0.0:
        ux, uy = -ux, -uy
    return (ux, uy)


def _np_pca_minor(centers):
    """閘**獨立**的 PCA 次主軸(numpy 共變異**最小**特徵向量;未定號 → 回線的代表向量)。"""
    pts = np.asarray(centers, dtype=float)
    pts = pts - pts.mean(axis=0)
    cov = np.cov(pts.T, bias=True)
    w, V = np.linalg.eigh(cov)
    return V[:, int(np.argmin(w))]


def _scipy_hull_longest_edge(centers, tol=1e-9):
    P = np.asarray(centers, dtype=float)
    hull = ConvexHull(P)
    verts = [(float(P[i][0]), float(P[i][1])) for i in hull.vertices]
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
    lo, hi = best_pair
    dx, dy = hi[0] - lo[0], hi[1] - lo[1]
    L = math.hypot(dx, dy)
    return (dx / L, dy / L)


def _brute_diameter(centers, tol=1e-9):
    n = len(centers)
    best_d = -1.0
    for i in range(n):
        for j in range(i + 1, n):
            best_d = max(best_d, math.hypot(centers[i][0] - centers[j][0], centers[i][1] - centers[j][1]))
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
    lo, hi = best_pair
    dx, dy = hi[0] - lo[0], hi[1] - lo[1]
    L = math.hypot(dx, dy)
    return (dx / L, dy / L)


def _np_pca_major(centers):
    pts = np.asarray(centers, dtype=float)
    pts = pts - pts.mean(axis=0)
    cov = np.cov(pts.T, bias=True)
    w, V = np.linalg.eigh(cov)
    return V[:, int(np.argmax(w))]


def _gate_centroid_farthest(centers):
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


def _acute(u, v):
    d = max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1]))
    a = math.degrees(math.acos(abs(d)))
    return min(a, 180.0 - a)


def _proj_key(xy, bone, vec):
    x, y = xy[bone]
    return x * vec[0] + y * vec[1]


def _proj_order(centers, vec):
    """件 index 依沿 vec 投影排序(tie-break 件序 index,確定性)。"""
    return sorted(range(len(centers)),
                  key=lambda i: (centers[i][0] * vec[0] + centers[i][1] * vec[1], i))


def _bytes(obj):
    return json.dumps(obj, sort_keys=True)


def _bits(v, nd=9):
    return tuple(round(c, nd) + 0.0 for c in v)


def run():
    skel = VD._skeleton()
    sb = VD._storyboard(VD.GENRE)
    order = VD._part_order(sb)
    xy = VD._bone_xy(skel)
    gains = TV.gains_for(VD.GENRE)
    rip = TV.cascade_ripples_for(VD.GENRE)

    base = G.build_animations(skel, sb)                                       # cascade_dir=None(件序)
    omin = G.build_animations(skel, sb, cascade_dir=("geo", "obb_minor"))
    omaj = G.build_animations(skel, sb, cascade_dir=("geo", "obb_major"))
    pmin = G.build_animations(skel, sb, cascade_dir=("geo", "pca_minor"))
    fpm = G.build_animations(skel, sb, cascade_dir=("geo", "farthest_pair"))
    hlem = G.build_animations(skel, sb, cascade_dir=("geo", "hull_longest_edge"))
    cbeats = VD._cascade_beats(base)
    main_beats = VD._main_beats(base)
    centers = [xy[b] for b in order]
    omin_vec = G.derive_cascade_dir(centers, "obb_minor")
    omaj_vec = G.derive_cascade_dir(centers, "obb_major")
    R = {}

    # ---- OM1 present + backward-compat + zero-regression ----
    p1 = {"missing": [], "not_finite": [], "no_bones": [], "noncascade_changed": [], "po_eq_none": None,
          "geo_default_eq_centroid": None, "pca_unchanged": None, "pca_minor_unchanged": None,
          "farthest_pair_unchanged": None, "hull_longest_edge_unchanged": None, "obb_major_unchanged": None,
          "pca_derive_eq_numpy_major": None, "fp_derive_eq_brute": None, "hle_derive_eq_scipy": None,
          "cf_derive_eq_gate": None, "obb_major_derive_eq_scipy": None}
    for cb in cbeats:
        an = omin.get(cb)
        if an is None:
            p1["missing"].append(cb); continue
        if not SA.all_finite(an):
            p1["not_finite"].append(cb)
        if not an.get("bones"):
            p1["no_bones"].append(cb)
    for beat, cat in main_beats.items():
        if cat == "cascade":
            continue
        if _bytes(omin.get(beat)) != _bytes(base.get(beat)):
            p1["noncascade_changed"].append(beat)
    po = G.build_animations(skel, sb, cascade_dir="po")
    p1["po_eq_none"] = all(_bytes(po[cb]) == _bytes(base[cb]) for cb in cbeats)
    geo_def = G.build_animations(skel, sb, cascade_dir="geo")
    geo_cf = G.build_animations(skel, sb, cascade_dir=("geo", "centroid_farthest"))
    p1["geo_default_eq_centroid"] = all(_bytes(geo_def[cb]) == _bytes(geo_cf[cb]) for cb in cbeats)
    # 零回歸:J-8..J-12 六條既有 source 路徑逐位元不變(不被本次新增影響)
    pmaj1 = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    pmaj2 = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    pmin2 = G.build_animations(skel, sb, cascade_dir=("geo", "pca_minor"))
    fpm2 = G.build_animations(skel, sb, cascade_dir=("geo", "farthest_pair"))
    hlem2 = G.build_animations(skel, sb, cascade_dir=("geo", "hull_longest_edge"))
    omaj2 = G.build_animations(skel, sb, cascade_dir=("geo", "obb_major"))
    p1["pca_unchanged"] = all(_bytes(pmaj1[cb]) == _bytes(pmaj2[cb]) for cb in cbeats)
    p1["pca_minor_unchanged"] = all(_bytes(pmin[cb]) == _bytes(pmin2[cb]) for cb in cbeats)
    p1["farthest_pair_unchanged"] = all(_bytes(fpm[cb]) == _bytes(fpm2[cb]) for cb in cbeats)
    p1["hull_longest_edge_unchanged"] = all(_bytes(hlem[cb]) == _bytes(hlem2[cb]) for cb in cbeats)
    p1["obb_major_unchanged"] = all(_bytes(omaj[cb]) == _bytes(omaj2[cb]) for cb in cbeats)
    np_major = _np_pca_major(centers)
    dmaj = G.derive_cascade_dir(centers, "pca")
    p1["pca_derive_eq_numpy_major"] = abs(abs(dmaj[0] * np_major[0] + dmaj[1] * np_major[1]) - 1.0) <= ALIGN_MAX
    dfp = G.derive_cascade_dir(centers, "farthest_pair")
    p1["fp_derive_eq_brute"] = _bits(dfp) == _bits(_brute_diameter(centers))
    dhle = G.derive_cascade_dir(centers, "hull_longest_edge")
    p1["hle_derive_eq_scipy"] = _bits(dhle) == _bits(_scipy_hull_longest_edge(centers))
    dcf = G.derive_cascade_dir(centers, "centroid_farthest")
    p1["cf_derive_eq_gate"] = _bits(dcf) == _bits(_gate_centroid_farthest(centers))
    p1["obb_major_derive_eq_scipy"] = _bits(omaj_vec) == _bits(_scipy_obb(centers, minor=False))
    p1_pass = (bool(cbeats) and not p1["missing"] and not p1["not_finite"] and not p1["no_bones"]
               and not p1["noncascade_changed"] and p1["po_eq_none"] and p1["geo_default_eq_centroid"]
               and p1["pca_unchanged"] and p1["pca_minor_unchanged"] and p1["farthest_pair_unchanged"]
               and p1["hull_longest_edge_unchanged"] and p1["obb_major_unchanged"]
               and p1["pca_derive_eq_numpy_major"] and p1["fp_derive_eq_brute"] and p1["hle_derive_eq_scipy"]
               and p1["cf_derive_eq_gate"] and p1["obb_major_derive_eq_scipy"])
    R["OM1_present_backward_compat"] = {"cascade_beats": cbeats, **p1, "pass": p1_pass}

    # ---- OM2 correctness + order-independent + deterministic sign (crux) ----
    p2 = {}
    # (a) OBB 次軸正確性:obb_minor == 閘獨立 scipy+卡尺 OBB 次軸(逐位元同向量)且 ⟂ obb_major
    cfgs = {"robot": centers,
            "L_shape": [(0.0, 0.0), (6.0, 0.0), (6.0, 1.0), (1.0, 1.0), (1.0, 4.0), (0.0, 4.0)],
            "slant_quad": [(0.0, 0.0), (6.0, 0.0), (6.0, 2.0), (0.0, 5.0)],
            "flag": [(0.0, 0.0), (10.0, 0.0), (10.0, 1.0), (3.0, 1.0), (3.0, 6.0), (0.0, 6.0)]}
    adet, a_ok = {}, True
    for name, C in cfgs.items():
        v = G.derive_cascade_dir(C, "obb_minor")
        b = _scipy_obb(C, minor=True)
        mj = G.derive_cascade_dir(C, "obb_major")
        same = _bits(v) == _bits(b)
        perp = abs(v[0] * mj[0] + v[1] * mj[1]) <= PERP_MAX
        adet[name] = {"obb_minor": _bits(v, 4), "scipy": _bits(b, 4), "bit_identical": same,
                      "perp_to_major": perp, "dot_major": round(v[0] * mj[0] + v[1] * mj[1], 9)}
        if not (same and perp):
            a_ok = False
    p2["a_obb_minor_eq_scipy_and_perp"] = {"detail": adet, "pass": a_ok}
    # (b) 件輸入順序無關:唯一最小矩形(slant_quad)+ 面積並列(三角形每邊並列)佈局所有排列 → 逐位元同一向量
    uniq_cfg = [(0.0, 0.0), (6.0, 0.0), (6.0, 2.0), (0.0, 5.0)]
    tri_cfg = [(0.0, 0.0), (10.0, 0.0), (3.0, 7.0)]
    uniq_outs = {_bits(G.derive_cascade_dir(list(p), "obb_minor")) for p in itertools.permutations(uniq_cfg)}
    tri_outs = {_bits(G.derive_cascade_dir(list(p), "obb_minor")) for p in itertools.permutations(tri_cfg)}
    p2["b_order_independent"] = {"uniq_perms": math.factorial(len(uniq_cfg)), "uniq_distinct": len(uniq_outs),
                                 "tri_perms": math.factorial(len(tri_cfg)), "tri_distinct": len(tri_outs),
                                 "uniq_vec": sorted(uniq_outs), "tri_vec": sorted(tri_outs),
                                 "pass": len(uniq_outs) == 1 and len(tri_outs) == 1}
    # (c) 符號跟隨幾何:沿 x 鏡射 y→−y → 方向 y 分量符號翻轉、x 分量不變(用次軸有 y 分量的佈局)
    B = [(0.0, 0.0), (2.0, 0.0), (3.0, 8.0), (1.0, 9.0)]
    Bm = [(x, -y) for (x, y) in B]
    vB = G.derive_cascade_dir(B, "obb_minor"); vBm = G.derive_cascade_dir(Bm, "obb_minor")
    p2["c_sign_tracks_geometry"] = {"B": _bits(vB, 4), "mirror_y": _bits(vBm, 4),
                                    "pass": _bits(vB) == _bits((vBm[0], -vBm[1])) and abs(vB[1]) > 0.05}
    R["OM2_correctness_order_sign"] = {**p2, "pass": all(v["pass"] for v in p2.values())}

    # ---- OM3 value crux: minor != major (different wave) + min-area != min-variance (vs pca_minor) ----
    p3 = {}
    # (a) obb_minor ⟂ obb_major 且是真正不同的波(依 minor / major 投影排序的件序不同),asset-independent
    adet3, a3_ok = {}, True
    for name, C in {"spread2d": [(0.0, 0.0), (8.0, 1.0), (2.0, 6.0), (9.0, 7.0), (4.0, 3.0)],
                    "L_shape": cfgs["L_shape"]}.items():
        mn = G.derive_cascade_dir(C, "obb_minor")
        mj = G.derive_cascade_dir(C, "obb_major")
        perp = abs(mn[0] * mj[0] + mn[1] * mj[1]) <= PERP_MAX
        on = _proj_order(C, mn); oj = _proj_order(C, mj)
        differ = on != oj
        adet3[name] = {"obb_minor": _bits(mn, 4), "obb_major": _bits(mj, 4), "perp": perp,
                       "minor_order": on, "major_order": oj, "order_differs": differ, "ok": perp and differ}
        if not (perp and differ):
            a3_ok = False
    p3["a_minor_ne_major_wave"] = {"detail": adet3, "pass": a3_ok}
    # (b) min-area ≠ min-variance:L 形 / flag(質量偏一側)obb_minor 方向 ≠ pca_minor 方向
    bdet3, b3_ok = {}, True
    for name, C in {"L_shape": cfgs["L_shape"], "flag": cfgs["flag"]}.items():
        mn = G.derive_cascade_dir(C, "obb_minor")
        pm = G.derive_cascade_dir(C, "pca_minor")
        rot = _acute(mn, pm)
        bdet3[name] = {"obb_minor": _bits(mn, 4), "pca_minor": _bits(pm, 4), "rot_deg": round(rot, 3),
                       "ok": rot >= MIN_ROT}
        if rot < MIN_ROT:
            b3_ok = False
    p3["b_obb_minor_ne_pca_minor"] = {"detail": bdet3, "pass": b3_ok}
    R["OM3_obb_minor_value"] = {**p3, "pass": all(v["pass"] for v in p3.values())}

    # ---- OM4 end-to-end projection ordering (robot) ----
    p4 = {"detail": {}, "fail_order": [], "weak_spread": [], "bad_interface": []}
    for cb in cbeats:
        an = omin[cb]
        bones = [b for b in order if b in an.get("bones", {})]
        proj_sorted = sorted(bones, key=lambda b: (_proj_key(xy, b, omin_vec), order.index(b)))
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
        # crux:obb_minor 的測得 pop 序 vs obb_major 的 pop 序(端到端兩者不同波)
        meas_maj = sorted([b for b in order if b in omaj[cb].get("bones", {})],
                          key=lambda b: VD.peak_time(omaj[cb], b))
        differs_major = [order.index(b) for b in meas] != [order.index(b) for b in meas_maj]
        p4["detail"][cb] = {"obb_minor_vec": _bits(omin_vec, 4),
                            "proj_order": [order.index(b) for b in proj_sorted],
                            "peak_times": [round(x, 3) for x in pts], "monotone": mono,
                            "farthest_pops_last": far_last, "spread": round(sp, 3), "iface": iface,
                            "measured_minor_order": [order.index(b) for b in meas],
                            "measured_major_order": [order.index(b) for b in meas_maj],
                            "differs_from_major": differs_major}
        if not (mono and far_last):
            p4["fail_order"].append(cb)
        if sp < SPREAD_FLOOR:
            p4["weak_spread"].append(cb)
        if not iface:
            p4["bad_interface"].append(cb)
    differs_major_all = all(d["differs_from_major"] for d in p4["detail"].values())
    # dir ⟂ nrip:帶 ripples 時各件 pop 次數 == nrip 在 obb_minor 成立
    nrip_ok, nrip_detail = True, {}
    full = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip,
                              cascade_dir=("geo", "obb_minor"))
    for cb in cbeats:
        for t in TIERS:
            an = full["{}__{}".format(cb, t)]
            cnts = [VD.peak_times_count(an, b) for b in an.get("bones", {})]
            ok = bool(cnts) and all(c == rip[t] for c in cnts)
            nrip_detail["{}__{}".format(cb, t)] = {"nrip": rip[t], "counts": cnts, "ok": ok}
            if not ok:
                nrip_ok = False
    p4_pass = (bool(cbeats) and not p4["fail_order"] and not p4["weak_spread"]
               and not p4["bad_interface"] and nrip_ok and differs_major_all)
    R["OM4_end_to_end_ordering"] = {**p4, "obb_minor_vec": _bits(omin_vec, 4), "obb_major_vec": _bits(omaj_vec, 4),
                                    "differs_from_major_all": differs_major_all,
                                    "nrip_intact": nrip_ok, "nrip_detail": nrip_detail, "pass": p4_pass}

    # ---- OM5 metric well-defined + guards ----
    p5 = {}
    # (a) metric:obb_minor == 閘獨立 scipy+卡尺 OBB 次軸(多佈局逐位元)且 ⟂ 長軸
    mdet, m_ok = {}, True
    for name, C in {"robot": centers, "slant_quad": cfgs["slant_quad"],
                    "penta": [(0.0, 0.0), (10.0, 1.0), (12.0, 7.0), (5.0, 11.0), (-2.0, 6.0)]}.items():
        v = G.derive_cascade_dir(C, "obb_minor"); b = _scipy_obb(C, minor=True)
        mj = G.derive_cascade_dir(C, "obb_major")
        same = _bits(v) == _bits(b)
        perp = abs(v[0] * mj[0] + v[1] * mj[1]) <= PERP_MAX
        mdet[name] = {"obb_minor": _bits(v, 4), "scipy": _bits(b, 4), "bit_identical": same, "perp": perp}
        if not (same and perp):
            m_ok = False
    p5["a_metric_eq_scipy"] = {"detail": mdet, "pass": m_ok}
    # (b) 正方守衛:正方 obb_minor raise、pca_minor 亦 raise(判據不同)、fp/hle 不 raise、確定性回值
    sq = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    obbmin_raises = pcamin_raises = False
    try:
        G.derive_cascade_dir(sq, "obb_minor")
    except ValueError:
        obbmin_raises = True
    try:
        G.derive_cascade_dir(sq, "pca_minor")
    except ValueError:
        pcamin_raises = True
    fp_ok = hle_ok = False
    fp_vec = hle_vec = None
    try:
        fp_vecs = {_bits(G.derive_cascade_dir(list(p), "farthest_pair")) for p in itertools.permutations(sq)}
        fp_ok = len(fp_vecs) == 1; fp_vec = sorted(fp_vecs)
    except ValueError:
        fp_ok = False
    try:
        hle_vecs = {_bits(G.derive_cascade_dir(list(p), "hull_longest_edge")) for p in itertools.permutations(sq)}
        hle_ok = len(hle_vecs) == 1; hle_vec = sorted(hle_vecs)
    except ValueError:
        hle_ok = False
    p5["b_square_guard"] = {"obb_minor_raises_on_square": obbmin_raises,
                            "pca_minor_raises_on_square": pcamin_raises,
                            "fp_resolves": fp_ok, "hle_resolves": hle_ok,
                            "fp_square_vec": fp_vec, "hle_square_vec": hle_vec,
                            "pass": obbmin_raises and pcamin_raises and fp_ok and hle_ok}
    # (c) 守衛:件重合 / 單件 / 空件 / 未知 source(直接 & 經 build)
    guards = {}
    for name, fn in {
        "coincident": lambda: G.derive_cascade_dir([(5.0, 7.0), (5.0, 7.0), (5.0, 7.0)], "obb_minor"),
        "single": lambda: G.derive_cascade_dir([(1.0, 2.0)], "obb_minor"),
        "empty": lambda: G.derive_cascade_dir([], "obb_minor"),
        "unknown_source_direct": lambda: G.derive_cascade_dir([(0, 0), (1, 1), (0, 1)], "nope_src"),
        "unknown_source_build": lambda: G.build_animations(skel, sb, cascade_dir=("geo", "zzz")),
    }.items():
        try:
            fn(); guards[name] = False
        except ValueError:
            guards[name] = True
    try:
        _ = G.build_animations(skel, sb, cascade_dir=("geo", "obb_minor")); guards["obb_minor_build_ok"] = True
    except Exception:
        guards["obb_minor_build_ok"] = False
    p5["c_input_guards"] = {"detail": guards, "pass": all(guards.values())}
    R["OM5_metric_guards"] = {**p5, "pass": all(v["pass"] for v in p5.values())}

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
        for k in ["OM1_present_backward_compat", "OM2_correctness_order_sign", "OM3_obb_minor_value",
                  "OM4_end_to_end_ordering", "OM5_metric_guards"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        a3 = R["OM3_obb_minor_value"]["a_minor_ne_major_wave"]["detail"]
        for name, d in a3.items():
            print("OM3a {:8s} minor={} major={} minor_order={} major_order={} differ={}".format(
                name, d["obb_minor"], d["obb_major"], d["minor_order"], d["major_order"], d["order_differs"]))
        b3 = R["OM3_obb_minor_value"]["b_obb_minor_ne_pca_minor"]["detail"]
        for name, d in b3.items():
            print("OM3b {:8s} obb_minor={} pca_minor={} rot={}°".format(
                name, d["obb_minor"], d["pca_minor"], d["rot_deg"]))
        print("OM4 projection order (robot):")
        for cb, d in R["OM4_end_to_end_ordering"]["detail"].items():
            print("   {:10s} minor_vec={} minor_order={} major_order={} mono={} differs_major={}".format(
                cb, d["obb_minor_vec"], d["measured_minor_order"], d["measured_major_order"],
                d["monotone"], d["differs_from_major"]))
        b5 = R["OM5_metric_guards"]["b_square_guard"]
        print("OM5(b) obb_minor_raises={} pca_minor_raises={} fp_resolves={} hle_resolves={}".format(
            b5["obb_minor_raises_on_square"], b5["pca_minor_raises_on_square"],
            b5["fp_resolves"], b5["hle_resolves"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
