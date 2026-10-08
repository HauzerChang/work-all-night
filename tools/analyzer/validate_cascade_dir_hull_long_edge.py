#!/usr/bin/env python3
"""candidate (J-11) 自我驗收閘 — cascade 跨件波方向的 **凸包最長邊(hull_long_edge)geo source**(確定性,純 CPU)。

方向軸的來源精煉(**同一條 J-6 投影軸**,逐步移除 / 強化人手指定):
  J-5:相位來源由件序換成**空間**(4 個具名方向 lr/rl/co/oc)。
  J-6:方向**值連續化**(任意角 / 向量)—— 但「用哪個方向」仍是手感常數。
  J-7:`cascade_dir="geo"` 方向**向量由件幾何導出**(質心 → 最遠件),隨資產自適應。
  J-8:新增 `geo source = "pca"`      —— PCA **主軸**(最大變異方向),符號確定性地定。
  J-9:新增 `geo source = "pca_minor"` —— PCA **次主軸**(最小變異方向,與主軸正交)。
  J-10:新增 `geo source = "farthest_pair"` —— 件中心點集的 **diameter(最遠對 / 最長弦)**方向。
  J-11(本閘):新增 `geo source = "hull_long_edge"` —— 件中心**凸包最長邊**(相鄰頂點間最長邊界邊)方向,
       字典序確定性定號。語意 = 波沿件群輪廓的最長一段邊界掃。

**honest distinction(勿誇大)**:J-11 **不是**新正交軸,也**不改** J-6 的投影排序機制;只是 J-7..J-10 那條
「方向軸取值來源(provenance)」再多一個 source(`hull_long_edge`)。其**價值 crux**在**與 farthest_pair 的對比**:
兩者**同屬凸包邊界決定量**(只看 hull 頂點 → 移動嚴格內部件不改向,vs pca/cf 用全體點會改),**但取不同邊界特徵**
—— 最長**邊**(相鄰頂點)≠ 最長**弦**(diameter,兩端點一般不相鄰)→ **一般給出不同方向**(HE3:正方 diameter=
對角、hull_long_edge=邊)。其**正確性 crux**:derive 與**閘獨立 scipy ConvexHull 最長邊**逐位元相同;方向 =
字典序較小端點 → 較大端點(件輸入順序無關;並列最長邊以端點對字典序取唯一代表)。誠實邊界:**全共線**時凸包
退化成線段,其唯一邊 = diameter → hull_long_edge 與 farthest_pair 重合(HE5(b))。

  HE1 present + backward-compat : `("geo","hull_long_edge")` 產每個 cascade beat 且 finite/有 bone;非 cascade 主秀
                                 beat 逐位元同 base;`None`/`"po"` 仍逐位元同件序;**零回歸** `"geo"` 預設
                                 (= centroid_farthest)、`("geo","pca")`(J-8)、`("geo","pca_minor")`(J-9)、
                                 `("geo","farthest_pair")`(J-10)皆**不被 hull_long_edge 新增影響**(逐位元同;
                                 `derive(.,"pca")` 仍 == 閘獨立 numpy **主**特徵向量、`derive(.,"farthest_pair")` 仍
                                 == 閘獨立 brute diameter、`derive(.,"centroid_farthest")` 仍 == 閘獨立質心→最遠件)。
  HE2 correctness + order-ind  : (crux)(a) **最長邊正確性**:`hull_long_edge` == 閘獨立 **scipy ConvexHull 最長邊**
                                 (**逐位元**同向量,非只同線);(b) **件輸入順序無關**:非對稱 & 對稱(最長邊
                                 並列,如正方四邊)佈局的**所有排列**產出**逐位元同一**帶號向量;(c) **符號跟隨
                                 幾何**:沿 x 軸鏡射(y→−y)→ 導出向量 y 分量符號確定性翻轉、x 分量不變。
  HE3 he vs fp/pca/cf (value)  : (crux/價值)**最長邊是一條真正不同的幾何 source**。(a) **同一佈局** hull_long_edge
                                 與 farthest_pair / pca / centroid_farthest **方向皆相異**(acute ≥ 門檻;頭條 =
                                 **he≠fp** 最長邊≠最長弦);(b) **邊界決定性**:移動一個**嚴格內部(非 hull 頂點)件**
                                 → **hull_long_edge 與 farthest_pair 皆逐位元不變**(兩者同屬凸包邊界量),而
                                 **centroid_farthest 方向隨之轉動**(質心移動,≥門檻)→ 證 he 屬邊界決定量(vs
                                 cf 的全體點統計)。**誠實**:pca 對單一內部件移動**弱敏感**(邊界點主導方差)故
                                 僅回報 pca 轉角**不作判準**。
  HE4 end-to-end ordering      : 真實 robot 骨架 `build_animations(cascade_dir=("geo","hull_long_edge"))` → 每 cascade
                                 beat 各件峰時刻依最長邊投影鍵嚴格遞增(最遠投影最後 pop)、仍一道有序跨件波
                                 (散佈≥門檻)+首尾 setup identity + 特效 slot alpha=1;dir⟂nrip 仍成立。並**誠實
                                 回報** robot 上 he pop 序 vs pca/cf(資訊,不作判準——genuine-difference crux 在 HE3)。
  HE5 metric + guards          : (a) metric:hull_long_edge == 閘獨立 scipy 最長邊(多佈局逐位元);(b) **並列最長邊 /
                                 退化**:正方(pca 會 ValueError、fp 回對角)→ hull_long_edge **不 raise**、確定性回
                                 一條邊且所有排列單一結果;**全共線**→ hull_long_edge == farthest_pair(退化成 diameter,
                                 誠實邊界);(c) 守衛:件重合 / 單件 / 空件 / 未知 source(直接 & 經 build_animations
                                 ("geo","hull_long_edge") 可用、("geo","zzz") 報錯)→ ValueError。

閘從 VD(J-5 閘)fixture 的**真實 build_spine robot 骨架**端到端量;最長邊 **由閘以 scipy ConvexHull 獨立重算**
(不呼叫生成器私有 `_hull_long_edge_dir`),diameter 以 brute-force、PCA 以 numpy 獨立重算,以保持獨立驗證。

用法:
  python3 validate_cascade_dir_hull_long_edge.py            # 摘要
  python3 validate_cascade_dir_hull_long_edge.py --json     # 完整 JSON
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
MIN_ANGLE = 20.0          # HE3(a):同佈局 he 與 fp/pca/cf 方向相異至少(度)
MIN_ROT = 3.0             # HE3(b):移動內部件時 cf 應轉動 ≥ 此角度(度)


def _scipy_hull_long_edge(centers, tol=1e-9):
    """閘**獨立**的凸包最長邊單位向量(scipy ConvexHull + 字典序確定性定號;不呼叫生成器私有函式)。"""
    pts = np.array(sorted(set((float(x), float(y)) for x, y in centers)))
    h = ConvexHull(pts)
    v = list(h.vertices)                                  # CCW 2D 頂點 index
    m = len(v)
    verts = [(float(pts[i][0]), float(pts[i][1])) for i in v]
    edges = [(verts[k], verts[(k + 1) % m]) for k in range(m)]
    best_len = max(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in edges)
    best_pair = None
    for a, b in edges:
        if math.hypot(b[0] - a[0], b[1] - a[1]) >= best_len - tol:
            lo, hi = (a, b) if a <= b else (b, a)
            if best_pair is None or (lo, hi) < best_pair:
                best_pair = (lo, hi)
    lo, hi = best_pair
    dx, dy = hi[0] - lo[0], hi[1] - lo[1]
    L = math.hypot(dx, dy)
    return (dx / L, dy / L)


def _brute_diameter(centers, tol=1e-9):
    """閘**獨立**的 diameter 單位向量(brute-force 最遠對 + 字典序確定性定號)。"""
    n = len(centers)
    best_d = -1.0
    for i in range(n):
        for j in range(i + 1, n):
            d = math.hypot(centers[i][0] - centers[j][0], centers[i][1] - centers[j][1])
            if d > best_d:
                best_d = d
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
    """閘**獨立**的 PCA 主軸(numpy 共變異最大特徵向量,未定號 → 回線的代表向量)。"""
    pts = np.asarray(centers, dtype=float)
    pts = pts - pts.mean(axis=0)
    cov = np.cov(pts.T, bias=True)
    w, V = np.linalg.eigh(cov)
    return V[:, int(np.argmax(w))]


def _gate_centroid_farthest(centers):
    """閘**獨立**的 centroid→farthest 單位向量(對照 derive(.,'centroid_farthest') 零回歸)。"""
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

    base = G.build_animations(skel, sb)                                        # cascade_dir=None(件序)
    he = G.build_animations(skel, sb, cascade_dir=("geo", "hull_long_edge"))
    pmaj = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    cbeats = VD._cascade_beats(base)
    main_beats = VD._main_beats(base)
    centers = [xy[b] for b in order]
    he_vec = G.derive_cascade_dir(centers, "hull_long_edge")
    R = {}

    # ---- HE1 present + backward-compat + zero-regression ----
    p1 = {"missing": [], "not_finite": [], "no_bones": [], "noncascade_changed": [], "po_eq_none": None,
          "geo_default_eq_centroid": None, "pca_unchanged": None, "pca_minor_unchanged": None,
          "farthest_pair_unchanged": None, "pca_derive_eq_numpy_major": None,
          "fp_derive_eq_gate_brute": None, "cf_derive_eq_gate": None}
    for cb in cbeats:
        an = he.get(cb)
        if an is None:
            p1["missing"].append(cb); continue
        if not SA.all_finite(an):
            p1["not_finite"].append(cb)
        if not an.get("bones"):
            p1["no_bones"].append(cb)
    for beat, cat in main_beats.items():
        if cat == "cascade":
            continue
        if _bytes(he.get(beat)) != _bytes(base.get(beat)):
            p1["noncascade_changed"].append(beat)
    po = G.build_animations(skel, sb, cascade_dir="po")
    p1["po_eq_none"] = all(_bytes(po[cb]) == _bytes(base[cb]) for cb in cbeats)
    geo_def = G.build_animations(skel, sb, cascade_dir="geo")
    geo_cf = G.build_animations(skel, sb, cascade_dir=("geo", "centroid_farthest"))
    p1["geo_default_eq_centroid"] = all(_bytes(geo_def[cb]) == _bytes(geo_cf[cb]) for cb in cbeats)
    # 零回歸:J-8 pca / J-9 pca_minor / J-10 farthest_pair 路徑逐位元不變(不被 hull_long_edge 新增影響)
    pmaj2 = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    pmin1 = G.build_animations(skel, sb, cascade_dir=("geo", "pca_minor"))
    pmin2 = G.build_animations(skel, sb, cascade_dir=("geo", "pca_minor"))
    fp1 = G.build_animations(skel, sb, cascade_dir=("geo", "farthest_pair"))
    fp2 = G.build_animations(skel, sb, cascade_dir=("geo", "farthest_pair"))
    p1["pca_unchanged"] = all(_bytes(pmaj[cb]) == _bytes(pmaj2[cb]) for cb in cbeats)
    p1["pca_minor_unchanged"] = all(_bytes(pmin1[cb]) == _bytes(pmin2[cb]) for cb in cbeats)
    p1["farthest_pair_unchanged"] = all(_bytes(fp1[cb]) == _bytes(fp2[cb]) for cb in cbeats)
    np_major = _np_pca_major(centers)
    dmaj = G.derive_cascade_dir(centers, "pca")
    p1["pca_derive_eq_numpy_major"] = abs(abs(dmaj[0] * np_major[0] + dmaj[1] * np_major[1]) - 1.0) <= ALIGN_MAX
    dfp = G.derive_cascade_dir(centers, "farthest_pair")
    p1["fp_derive_eq_gate_brute"] = _bits(dfp) == _bits(_brute_diameter(centers))
    dcf = G.derive_cascade_dir(centers, "centroid_farthest")
    p1["cf_derive_eq_gate"] = _bits(dcf) == _bits(_gate_centroid_farthest(centers))
    p1_pass = (bool(cbeats) and not p1["missing"] and not p1["not_finite"] and not p1["no_bones"]
               and not p1["noncascade_changed"] and p1["po_eq_none"] and p1["geo_default_eq_centroid"]
               and p1["pca_unchanged"] and p1["pca_minor_unchanged"] and p1["farthest_pair_unchanged"]
               and p1["pca_derive_eq_numpy_major"] and p1["fp_derive_eq_gate_brute"] and p1["cf_derive_eq_gate"])
    R["HE1_present_backward_compat"] = {"cascade_beats": cbeats, **p1, "pass": p1_pass}

    # ---- HE2 longest-edge correctness + order-independent + deterministic sign (crux) ----
    p2 = {}
    # (a) 最長邊正確性:hull_long_edge == 閘獨立 scipy ConvexHull 最長邊(逐位元同向量)
    cfgs = {"robot": centers,
            "value": [(10.0, 3.0), (2.0, 9.0), (4.0, -3.0), (-6.0, -4.0), (-7.0, 6.0)],
            "pent": [(0.0, 0.0), (10.0, 0.0), (11.0, 4.0), (5.0, 8.0), (-1.0, 4.0)]}
    adet, a_ok = {}, True
    for name, C in cfgs.items():
        v = G.derive_cascade_dir(C, "hull_long_edge")
        b = _scipy_hull_long_edge(C)
        same = _bits(v) == _bits(b)
        adet[name] = {"he": _bits(v, 4), "scipy": _bits(b, 4), "bit_identical": same}
        if not same:
            a_ok = False
    p2["a_longedge_eq_scipy"] = {"detail": adet, "pass": a_ok}
    # (b) 件輸入順序無關:非對稱 + 對稱(正方四邊並列最長)佈局的所有排列 → 逐位元同一向量
    asym = [(10.0, 3.0), (2.0, 9.0), (4.0, -3.0), (-6.0, -4.0), (-7.0, 6.0)]
    sq = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]                       # 四邊並列最長
    asym_outs = {_bits(G.derive_cascade_dir(list(p), "hull_long_edge")) for p in itertools.permutations(asym)}
    sq_outs = {_bits(G.derive_cascade_dir(list(p), "hull_long_edge")) for p in itertools.permutations(sq)}
    p2["b_order_independent"] = {"asym_perms": math.factorial(len(asym)), "asym_distinct": len(asym_outs),
                                 "square_perms": math.factorial(len(sq)), "square_distinct": len(sq_outs),
                                 "square_vec": sorted(sq_outs),
                                 "pass": len(asym_outs) == 1 and len(sq_outs) == 1}
    # (c) 符號跟隨幾何:沿 x 鏡射 y→−y → 方向 y 分量符號翻轉、x 分量不變(最長邊端點 y 相異)
    Bv = [(10.0, 3.0), (2.0, 9.0), (4.0, -3.0), (-6.0, -4.0), (-7.0, 6.0)]
    Bm = [(x, -y) for (x, y) in Bv]
    vB = G.derive_cascade_dir(Bv, "hull_long_edge"); vBm = G.derive_cascade_dir(Bm, "hull_long_edge")
    p2["c_sign_tracks_geometry"] = {"B": _bits(vB, 4), "mirror_y": _bits(vBm, 4),
                                    "pass": _bits(vB) == _bits((vBm[0], -vBm[1])) and abs(vB[1]) > 0.2}
    R["HE2_longedge_order_sign"] = {**p2, "pass": all(v["pass"] for v in p2.values())}

    # ---- HE3 hull_long_edge vs farthest_pair/pca/cf: genuinely different source (crux / value) ----
    # (a) 同一佈局:he 與 fp / pca / cf 方向皆相異(頭條 = he≠fp:最長邊 ≠ 最長弦)。
    val = [(10.0, 3.0), (2.0, 9.0), (4.0, -3.0), (-6.0, -4.0), (-7.0, 6.0)]
    hev = G.derive_cascade_dir(val, "hull_long_edge")
    fpv = G.derive_cascade_dir(val, "farthest_pair")
    pcv = G.derive_cascade_dir(val, "pca")
    cfv = G.derive_cascade_dir(val, "centroid_farthest")
    a_fp, a_pca, a_cf = _acute(hev, fpv), _acute(hev, pcv), _acute(hev, cfv)
    a_ok3 = a_fp >= MIN_ANGLE and a_pca >= MIN_ANGLE and a_cf >= MIN_ANGLE
    # (b) 邊界決定性:移動嚴格內部件 → he & fp 逐位元不變;cf 轉動 ≥ 門檻(pca 僅回報不作判準)。
    bnd = [(-12.0, 0.0), (12.0, -1.0), (10.0, 10.0), (-10.0, 9.0)]
    bse = bnd + [(-5.0, 3.0)]
    mov = bnd + [(6.0, 5.0)]
    he0 = G.derive_cascade_dir(bse, "hull_long_edge"); he1 = G.derive_cascade_dir(mov, "hull_long_edge")
    fp0 = G.derive_cascade_dir(bse, "farthest_pair"); fp1v = G.derive_cascade_dir(mov, "farthest_pair")
    cf0 = G.derive_cascade_dir(bse, "centroid_farthest"); cf1 = G.derive_cascade_dir(mov, "centroid_farthest")
    pc0 = G.derive_cascade_dir(bse, "pca"); pc1 = G.derive_cascade_dir(mov, "pca")
    he_inv = _bits(he0) == _bits(he1)
    fp_inv = _bits(fp0) == _bits(fp1v)
    cf_rot = _acute(cf0, cf1)
    pca_rot = _acute(pc0, pc1)                                                  # 誠實回報,不作判準
    b_ok3 = he_inv and fp_inv and cf_rot >= MIN_ROT
    R["HE3_he_vs_fp_pca_cf"] = {
        "a_same_config_distinct": {"he": _bits(hev, 4), "fp": _bits(fpv, 4), "pca": _bits(pcv, 4),
                                   "cf": _bits(cfv, 4), "he_vs_fp_deg": round(a_fp, 2),
                                   "he_vs_pca_deg": round(a_pca, 2), "he_vs_cf_deg": round(a_cf, 2),
                                   "min_angle": MIN_ANGLE, "pass": a_ok3},
        "b_boundary_determinism": {"he_bit_invariant": he_inv, "fp_bit_invariant": fp_inv,
                                   "cf_rotation_deg": round(cf_rot, 3), "pca_rotation_deg_info": round(pca_rot, 3),
                                   "min_rot": MIN_ROT, "pass": b_ok3},
        "pass": a_ok3 and b_ok3}

    # ---- HE4 end-to-end projection ordering (robot) ----
    p4 = {"detail": {}, "fail_order": [], "weak_spread": [], "bad_interface": []}
    cf_full_vec = G.derive_cascade_dir(centers, "centroid_farthest")
    pmaj_vec = G.derive_cascade_dir(centers, "pca")
    for cb in cbeats:
        an = he[cb]
        bones = [b for b in order if b in an.get("bones", {})]
        proj_sorted = sorted(bones, key=lambda b: (_proj_key(xy, b, he_vec), order.index(b)))
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
        # 誠實回報(不作判準):he 的測得 pop 序 vs pca 的 pop 序
        meas_maj = sorted([b for b in order if b in pmaj[cb].get("bones", {})],
                          key=lambda b: VD.peak_time(pmaj[cb], b))
        differs_major = [order.index(b) for b in meas] != [order.index(b) for b in meas_maj]
        p4["detail"][cb] = {"he_vec": _bits(he_vec, 4), "proj_order": [order.index(b) for b in proj_sorted],
                            "peak_times": [round(x, 3) for x in pts], "monotone": mono,
                            "farthest_pops_last": far_last, "spread": round(sp, 3), "iface": iface,
                            "measured_he_order": [order.index(b) for b in meas],
                            "measured_major_order": [order.index(b) for b in meas_maj],
                            "differs_from_major": differs_major}
        if not (mono and far_last):
            p4["fail_order"].append(cb)
        if sp < SPREAD_FLOOR:
            p4["weak_spread"].append(cb)
        if not iface:
            p4["bad_interface"].append(cb)
    # dir ⟂ nrip:帶 ripples 時各件 pop 次數 == nrip 在 hull_long_edge 成立
    nrip_ok, nrip_detail = True, {}
    full = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip,
                              cascade_dir=("geo", "hull_long_edge"))
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
    R["HE4_end_to_end_ordering"] = {**p4, "he_vec": _bits(he_vec, 4), "pca_vec": _bits(pmaj_vec, 4),
                                    "cf_vec": _bits(cf_full_vec, 4), "nrip_intact": nrip_ok,
                                    "nrip_detail": nrip_detail, "pass": p4_pass}

    # ---- HE5 metric well-defined + guards ----
    p5 = {}
    # (a) metric:hull_long_edge == 閘獨立 scipy 最長邊(多佈局逐位元)
    mdet, m_ok = {}, True
    for name, C in {"robot": centers, "value": cfgs["value"],
                    "hex": [(0.0, 0.0), (6.0, -1.0), (9.0, 3.0), (6.0, 8.0), (1.0, 9.0), (-3.0, 4.0)]}.items():
        v = G.derive_cascade_dir(C, "hull_long_edge"); b = _scipy_hull_long_edge(C)
        same = _bits(v) == _bits(b)
        mdet[name] = {"he": _bits(v, 4), "scipy": _bits(b, 4), "bit_identical": same}
        if not same:
            m_ok = False
    p5["a_metric_eq_scipy"] = {"detail": mdet, "pass": m_ok}
    # (b) 並列最長邊 / 退化:正方(pca ValueError、fp 對角)→ he 不 raise、確定性回一條邊、件序無關;
    #     全共線 → he == farthest_pair(退化成 diameter,誠實邊界)。
    sq2 = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    pca_raises = False
    try:
        G.derive_cascade_dir(sq2, "pca")
    except ValueError:
        pca_raises = True
    sq_vecs = {_bits(G.derive_cascade_dir(list(p), "hull_long_edge")) for p in itertools.permutations(sq2)}
    he_sq_ok = len(sq_vecs) == 1
    sq_fp = _bits(G.derive_cascade_dir(sq2, "farthest_pair"))
    he_sq = sorted(sq_vecs)[0]
    he_ne_fp_sq = he_sq != sq_fp                                                # 正方:最長邊 ≠ 對角
    col = [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.0)]                      # 全共線
    he_col = _bits(G.derive_cascade_dir(col, "hull_long_edge"))
    fp_col = _bits(G.derive_cascade_dir(col, "farthest_pair"))
    col_eq_diam = he_col == fp_col
    p5["b_tie_degenerate"] = {"pca_raises_on_square": pca_raises, "he_resolves_square": he_sq_ok,
                              "he_square_vec": list(he_sq), "fp_square_vec": list(sq_fp),
                              "he_differs_fp_on_square": he_ne_fp_sq,
                              "collinear_he_eq_diameter": col_eq_diam,
                              "pass": pca_raises and he_sq_ok and he_ne_fp_sq and col_eq_diam}
    # (c) 守衛:件重合 / 單件 / 空件 / 未知 source(直接 & 經 build)
    guards = {}
    for name, fn in {
        "coincident": lambda: G.derive_cascade_dir([(5.0, 7.0), (5.0, 7.0), (5.0, 7.0)], "hull_long_edge"),
        "single": lambda: G.derive_cascade_dir([(1.0, 2.0)], "hull_long_edge"),
        "empty": lambda: G.derive_cascade_dir([], "hull_long_edge"),
        "unknown_source_direct": lambda: G.derive_cascade_dir([(0, 0), (1, 1)], "nope_src"),
        "unknown_source_build": lambda: G.build_animations(skel, sb, cascade_dir=("geo", "zzz")),
    }.items():
        try:
            fn(); guards[name] = False
        except ValueError:
            guards[name] = True
    try:
        _ = G.build_animations(skel, sb, cascade_dir=("geo", "hull_long_edge")); guards["he_build_ok"] = True
    except Exception:
        guards["he_build_ok"] = False
    p5["c_input_guards"] = {"detail": guards, "pass": all(guards.values())}
    R["HE5_metric_guards"] = {**p5, "pass": all(v["pass"] for v in p5.values())}

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
        for k in ["HE1_present_backward_compat", "HE2_longedge_order_sign", "HE3_he_vs_fp_pca_cf",
                  "HE4_end_to_end_ordering", "HE5_metric_guards"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        a3 = R["HE3_he_vs_fp_pca_cf"]["a_same_config_distinct"]
        b3 = R["HE3_he_vs_fp_pca_cf"]["b_boundary_determinism"]
        print("HE3(a) he={} he-vs-fp={}° he-vs-pca={}° he-vs-cf={}°".format(
            a3["he"], a3["he_vs_fp_deg"], a3["he_vs_pca_deg"], a3["he_vs_cf_deg"]))
        print("HE3(b) he_inv={} fp_inv={} cf_rot={}° (pca_rot_info={}°)".format(
            b3["he_bit_invariant"], b3["fp_bit_invariant"], b3["cf_rotation_deg"], b3["pca_rotation_deg_info"]))
        print("HE4 projection order (robot):")
        for cb, d in R["HE4_end_to_end_ordering"]["detail"].items():
            print("   {:10s} vec={} he_order={} major_order={} mono={} differs_major={}".format(
                cb, d["he_vec"], d["measured_he_order"], d["measured_major_order"],
                d["monotone"], d["differs_from_major"]))
        b5 = R["HE5_metric_guards"]["b_tie_degenerate"]
        print("HE5(b) pca_raises_sq={} he_resolves_sq={} he_ne_fp_sq={} collinear_he==diam={}".format(
            b5["pca_raises_on_square"], b5["he_resolves_square"], b5["he_differs_fp_on_square"],
            b5["collinear_he_eq_diameter"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
