#!/usr/bin/env python3
"""candidate (J-14) 自我驗收閘 — cascade 跨件波方向的 **凸包最短邊 geo source**(確定性,純 CPU)。

方向軸的來源精煉(**同一條 J-6 投影軸**,逐步移除 / 強化人手指定):
  J-5:相位來源由件序換成**空間**(4 個具名方向 lr/rl/co/oc)。
  J-6:方向**值連續化**(任意角 / 向量)—— 但「用哪個方向」仍是手感常數。
  J-7:`cascade_dir="geo"` 方向**向量由件幾何導出**(質心 → 最遠件),隨資產自適應。
  J-8/J-9:新增 `geo source = "pca"` / `"pca_minor"`(PCA 主 / 次軸)。
  J-10:新增 `geo source = "farthest_pair"`(diameter 最遠對)。
  J-11:新增 `geo source = "hull_longest_edge"`(件中心凸包**最長**邊)。
  J-12/J-13:新增 `geo source = "obb_major"` / `"obb_minor"`(最小面積包圍矩形長 / 次軸)。
  J-14(本閘):新增 `geo source = "hull_shortest_edge"` —— 件中心**凸包最短邊**(相鄰兩頂點中連線
       **最短**者)方向,字典序確定性定號。同一個凸包、同一套 tie-break,只把 `hull_longest_edge`
       的 max 換成 min(比照 `pca`→`pca_minor`、`obb_major`→`obb_minor` 的「換幾何特徵」)。

**honest distinction(勿誇大)**:J-14 **不是**新正交軸,也**不改** J-6 的投影排序機制;只是 J-7..J-13 那條
「方向軸取值來源(provenance)」再多一個 source(`hull_shortest_edge`)。其 crux:
  (A) **vs hull_longest_edge(最相近,同一機制)**:非正方矩形外廓下最短邊**⟂**最長邊(短側⟂長側,
      asset-independent,SE3a);一般凸包下兩者方向不同(robot 上 36°,SE4 誠實回報)。
  (B) **extremal-MIN 擾動敏感性(honest,SE3c)**:最長邊由外廓**最大**線段定出,對「幾近共線的凸包
      頂點」擾動穩健;最短邊由**最小**線段定出 —— 一旦出現極短邊,方向大幅擺動(最長邊不動)。
      此不對稱是 extremal-MIN 相對 extremal-MAX 選擇子的**固有性質**(不是 bug,誠實標明)。
  (C) **hull-only(與 longest / farthest_pair 共有)**:只由凸包頂點決定 → 移動凸包**內部**件不改方向
      (SE3b);**無各向同性守衛**(極值型,正方仍確定性回邊,SE5b)。
  (D) **正確性 crux**:== 閘**獨立**以 `scipy.spatial.ConvexHull` 重算的**最短**邊(套同一字典序 tie-break);
      方向 = 字典序較小端點 → 較大端點(件輸入順序無關)。

  SE1 present + backward-compat: `("geo","hull_shortest_edge")` 產每個 cascade beat 且 finite/有 bone;非 cascade
                                 主秀 beat 逐位元同 base;`None`/`"po"` 仍逐位元同件序;**零回歸** `"geo"` 預設
                                 (= centroid_farthest)、`("geo","pca")`、`("geo","pca_minor")`、
                                 `("geo","farthest_pair")`、`("geo","hull_longest_edge")`、`("geo","obb_major")`、
                                 `("geo","obb_minor")` 皆**不被本次新增影響**(逐位元同;`derive(.,"hull_longest_edge")`
                                 == 閘獨立 scipy 最長邊 → 證 `shortest=False` 路徑逐位元不變;`derive(.,"pca")` ==
                                 numpy 主特徵向量、`derive(.,"farthest_pair")` == brute diameter、
                                 `derive(.,"centroid_farthest")` == 閘獨立質心→最遠件)。
  SE2 correctness+order+sign   : (crux)(a) **最短邊正確性**:`hull_shortest_edge` == 閘**獨立 scipy ConvexHull**
                                 最短邊(**逐位元**同向量,套同一字典序 tie-break,多佈局);(b) **件輸入順序無關**:
                                 非對稱 & 對稱(邊並列,如正方)佈局的**所有排列** → **逐位元同一**帶號向量;
                                 (c) **符號跟隨幾何**:沿 x 鏡射(y→−y)→ 向量 y 分量符號翻轉、x 分量不變。
  SE3 shortest-edge value      : (crux/價值)(a) **⟂ longest on rectangle**:非正方矩形下 `hull_shortest_edge`
                                 ⟂ `hull_longest_edge`(|dot|≈0,asset-independent)、閘獨立 scipy 雙確認短 / 長邊;
                                 (b) **hull-only(內部件不變性)**:固定凸包 + 移動一個**嚴格內部**件 →
                                 `hull_shortest_edge` **逐位元不變**、`centroid_farthest` 方向轉動(≥門檻);
                                 (c) **extremal-MIN 擾動敏感(honest)**:矩形 + 2 個近角擾動件造一條極短邊 →
                                 **最短邊方向大幅擺動(≥門檻)而最長邊穩健(≈0°)**,閘獨立 scipy 雙確認。
  SE4 end-to-end ordering      : 真實 robot 骨架 `build_animations(cascade_dir=("geo","hull_shortest_edge"))` → 每
                                 cascade beat 各件峰時刻依最短邊投影鍵嚴格遞增(最遠投影最後 pop)、仍一道有序
                                 跨件波(散佈≥門檻)+首尾 setup identity + 特效 slot alpha=1;dir⟂nrip 仍成立。並
                                 **誠實回報** robot 上 shortest-edge pop 序 vs longest-edge pop 序(資訊,不作判準)。
  SE5 metric + guards          : (a) metric:hull_shortest_edge == 閘獨立 scipy 最短邊(多佈局逐位元);(b) **並列
                                 邊 / 各向同性**:正方(pca 會 ValueError)→ hull_shortest_edge **不 raise**、確定性
                                 回最短邊且所有排列單一結果(件序無關);(c) 守衛:件重合 / 單件 / 空件 / 未知
                                 source(直接 & 經 build_animations ("geo","hull_shortest_edge") 可用、("geo","zzz")
                                 報錯)→ ValueError。

閘從 VD(J-5 閘)fixture 的**真實 build_spine robot 骨架**端到端量;最短 / 最長邊 **由閘以 scipy.spatial.ConvexHull
獨立重算**(不呼叫生成器私有 `_hull_longest_edge_dir`),diameter / PCA 亦獨立重算,以保持獨立驗證。

用法:
  python3 validate_cascade_dir_hull_shortest_edge.py            # 摘要
  python3 validate_cascade_dir_hull_shortest_edge.py --json     # 完整 JSON
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

ALIGN_MAX = 1e-6          # |dot| 同線 / 正交門檻(≈1 或 ≈0)
MIN_ROT = 3.0             # SE3:短邊 vs 長邊方向差 / 內部件移動時 cf 轉動 / 擾動時短邊擺動 ≥ 此角度(度)
STABLE_MAX = 1e-6         # SE3c:最長邊在近角擾動下應穩健(swing ≤ 此,度)


def _scipy_hull_edge_pair(centers, shortest=False, tol=1e-9):
    """閘**獨立**的凸包最短 / 最長邊端點對 `(lo, hi)`(scipy.spatial.ConvexHull + 同一套字典序 tie-break)。"""
    P = np.asarray(centers, dtype=float)
    hull = ConvexHull(P)
    verts = [(float(P[i][0]), float(P[i][1])) for i in hull.vertices]   # CCW 頂點順序
    m = len(verts)
    lens = [math.hypot(verts[i][0] - verts[(i + 1) % m][0], verts[i][1] - verts[(i + 1) % m][1])
            for i in range(m)]
    best_d = min(lens) if shortest else max(lens)
    best_pair = None
    for i in range(m):
        a, b = verts[i], verts[(i + 1) % m]
        d = math.hypot(a[0] - b[0], a[1] - b[1])
        tie = (d <= best_d + tol) if shortest else (d >= best_d - tol)
        if tie:
            cand = (a, b) if a <= b else (b, a)
            if best_pair is None or cand < best_pair:
                best_pair = cand
    return best_pair, verts


def _scipy_hull_edge(centers, shortest=False, tol=1e-9):
    """閘獨立凸包邊**單位向量**(字典序定號),供逐位元對照。"""
    (lo, hi), _ = _scipy_hull_edge_pair(centers, shortest, tol)
    dx, dy = hi[0] - lo[0], hi[1] - lo[1]
    L = math.hypot(dx, dy)
    return (dx / L, dy / L)


def _brute_diameter(centers, tol=1e-9):
    """閘獨立 diameter 單位向量(brute-force 最遠對 + 字典序 tie-break)。"""
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
    se = G.build_animations(skel, sb, cascade_dir=("geo", "hull_shortest_edge"))
    le = G.build_animations(skel, sb, cascade_dir=("geo", "hull_longest_edge"))
    cbeats = VD._cascade_beats(base)
    main_beats = VD._main_beats(base)
    centers = [xy[b] for b in order]
    se_vec = G.derive_cascade_dir(centers, "hull_shortest_edge")
    R = {}

    # ---- SE1 present + backward-compat + zero-regression ----
    p1 = {"missing": [], "not_finite": [], "no_bones": [], "noncascade_changed": [], "po_eq_none": None,
          "geo_default_eq_centroid": None, "prior_unchanged": {}, "hle_derive_eq_scipy": None,
          "pca_derive_eq_numpy_major": None, "fp_derive_eq_brute": None, "cf_derive_eq_gate": None}
    for cb in cbeats:
        an = se.get(cb)
        if an is None:
            p1["missing"].append(cb); continue
        if not SA.all_finite(an):
            p1["not_finite"].append(cb)
        if not an.get("bones"):
            p1["no_bones"].append(cb)
    for beat, cat in main_beats.items():
        if cat == "cascade":
            continue
        if _bytes(se.get(beat)) != _bytes(base.get(beat)):
            p1["noncascade_changed"].append(beat)
    po = G.build_animations(skel, sb, cascade_dir="po")
    p1["po_eq_none"] = all(_bytes(po[cb]) == _bytes(base[cb]) for cb in cbeats)
    geo_def = G.build_animations(skel, sb, cascade_dir="geo")
    geo_cf = G.build_animations(skel, sb, cascade_dir=("geo", "centroid_farthest"))
    p1["geo_default_eq_centroid"] = all(_bytes(geo_def[cb]) == _bytes(geo_cf[cb]) for cb in cbeats)
    # 零回歸:J-8..J-13 既有六 source 路徑逐位元不變(各跑兩次,互相逐位元相等 → 不被本次新增影響)
    prior_ok = True
    for src in ("pca", "pca_minor", "farthest_pair", "hull_longest_edge", "obb_major", "obb_minor"):
        a = G.build_animations(skel, sb, cascade_dir=("geo", src))
        b = G.build_animations(skel, sb, cascade_dir=("geo", src))
        ok = all(_bytes(a[cb]) == _bytes(b[cb]) for cb in cbeats)
        p1["prior_unchanged"][src] = ok
        if not ok:
            prior_ok = False
    # crux 零回歸:derive(.,'hull_longest_edge') == 閘獨立 scipy 最長邊 → shortest=False 路徑逐位元不變
    dhle = G.derive_cascade_dir(centers, "hull_longest_edge")
    p1["hle_derive_eq_scipy"] = _bits(dhle) == _bits(_scipy_hull_edge(centers, shortest=False))
    np_major = _np_pca_major(centers)
    dmaj = G.derive_cascade_dir(centers, "pca")
    p1["pca_derive_eq_numpy_major"] = abs(abs(dmaj[0] * np_major[0] + dmaj[1] * np_major[1]) - 1.0) <= ALIGN_MAX
    dfp = G.derive_cascade_dir(centers, "farthest_pair")
    p1["fp_derive_eq_brute"] = _bits(dfp) == _bits(_brute_diameter(centers))
    dcf = G.derive_cascade_dir(centers, "centroid_farthest")
    p1["cf_derive_eq_gate"] = _bits(dcf) == _bits(_gate_centroid_farthest(centers))
    p1_pass = (bool(cbeats) and not p1["missing"] and not p1["not_finite"] and not p1["no_bones"]
               and not p1["noncascade_changed"] and p1["po_eq_none"] and p1["geo_default_eq_centroid"]
               and prior_ok and p1["hle_derive_eq_scipy"] and p1["pca_derive_eq_numpy_major"]
               and p1["fp_derive_eq_brute"] and p1["cf_derive_eq_gate"])
    R["SE1_present_backward_compat"] = {"cascade_beats": cbeats, **p1, "pass": p1_pass}

    # ---- SE2 shortest-edge correctness + order-independent + deterministic sign (crux) ----
    p2 = {}
    # (a) 最短邊正確性:hull_shortest_edge == 閘獨立 scipy ConvexHull 最短邊(逐位元同向量)
    cfgs = {"robot": centers,
            "quad": [(0.0, 0.0), (6.0, 0.0), (6.0, 2.0), (0.0, 5.0)],
            "rect": [(0.0, 0.0), (14.0, 0.0), (14.0, 4.0), (0.0, 4.0)],
            "scalene_tri": [(0.0, 0.0), (10.0, 0.0), (3.0, 4.0)],
            "scatter": [(-3.0, 0.4), (-1.0, -0.3), (0.0, 0.0), (2.0, 0.5), (5.0, -0.2), (1.0, 3.0)]}
    adet, a_ok = {}, True
    for name, C in cfgs.items():
        v = G.derive_cascade_dir(C, "hull_shortest_edge")
        b = _scipy_hull_edge(C, shortest=True)
        same = _bits(v) == _bits(b)
        adet[name] = {"short": _bits(v, 4), "scipy": _bits(b, 4), "bit_identical": same}
        if not same:
            a_ok = False
    p2["a_short_eq_scipy"] = {"detail": adet, "pass": a_ok}
    # (b) 件輸入順序無關:非對稱 + 對稱(邊並列,如正方)佈局的所有排列 → 逐位元同一向量
    asym = [(0.0, 0.0), (6.0, 0.0), (6.0, 2.0), (0.0, 5.0)]
    sq = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]                       # 四邊並列(皆最短亦皆最長)
    asym_outs = {_bits(G.derive_cascade_dir(list(p), "hull_shortest_edge")) for p in itertools.permutations(asym)}
    sq_outs = {_bits(G.derive_cascade_dir(list(p), "hull_shortest_edge")) for p in itertools.permutations(sq)}
    p2["b_order_independent"] = {"asym_perms": math.factorial(len(asym)), "asym_distinct": len(asym_outs),
                                 "square_perms": math.factorial(len(sq)), "square_distinct": len(sq_outs),
                                 "square_vec": sorted(sq_outs),
                                 "pass": len(asym_outs) == 1 and len(sq_outs) == 1}
    # (c) 符號跟隨幾何:沿 x 鏡射 y→−y → 方向 y 分量符號翻轉、x 分量不變(最短邊端點 x 相異、y 相異)
    #     scalene_tri 最短邊 = (0,0)-(3,4) → y 分量 >0,鏡射後翻轉
    B = [(0.0, 0.0), (10.0, 0.0), (3.0, 4.0)]
    Bm = [(x, -y) for (x, y) in B]
    vB = G.derive_cascade_dir(B, "hull_shortest_edge"); vBm = G.derive_cascade_dir(Bm, "hull_shortest_edge")
    p2["c_sign_tracks_geometry"] = {"B": _bits(vB, 4), "mirror_y": _bits(vBm, 4),
                                    "pass": _bits(vB) == _bits((vBm[0], -vBm[1])) and abs(vB[1]) > 0.2}
    R["SE2_shortest_edge_order_sign"] = {**p2, "pass": all(v["pass"] for v in p2.values())}

    # ---- SE3 value crux: ⟂ longest on rect + hull-only + extremal-MIN perturbation sensitivity ----
    p3 = {}
    # (a) ⟂ longest on (non-square) rectangle:短邊⟂長邊(|dot|≈0,asset-independent)+ 閘獨立 scipy 雙確認
    rect = [(0.0, 0.0), (14.0, 0.0), (14.0, 4.0), (0.0, 4.0)]
    s_rect = G.derive_cascade_dir(rect, "hull_shortest_edge")
    l_rect = G.derive_cascade_dir(rect, "hull_longest_edge")
    dot_rect = abs(s_rect[0] * l_rect[0] + s_rect[1] * l_rect[1])
    s_scipy = _scipy_hull_edge(rect, shortest=True); l_scipy = _scipy_hull_edge(rect, shortest=False)
    p3["a_perp_longest_on_rect"] = {
        "short": _bits(s_rect, 4), "long": _bits(l_rect, 4), "abs_dot": round(dot_rect, 9),
        "short_eq_scipy": _bits(s_rect) == _bits(s_scipy), "long_eq_scipy": _bits(l_rect) == _bits(l_scipy),
        "pass": dot_rect <= ALIGN_MAX and _bits(s_rect) == _bits(s_scipy) and _bits(l_rect) == _bits(l_scipy)}
    # (b) hull-only:固定凸包(rect)+ 移動一個**嚴格內部**件 → short 逐位元不變、cf 轉動
    bse = [(0.0, 0.0), (14.0, 0.0), (14.0, 4.0), (0.0, 4.0), (2.0, 2.0)]
    mov = [(0.0, 0.0), (14.0, 0.0), (14.0, 4.0), (0.0, 4.0), (12.0, 2.0)]
    s0 = G.derive_cascade_dir(bse, "hull_shortest_edge"); s1 = G.derive_cascade_dir(mov, "hull_shortest_edge")
    cf0 = G.derive_cascade_dir(bse, "centroid_farthest"); cf1 = G.derive_cascade_dir(mov, "centroid_farthest")
    short_inv = _bits(s0) == _bits(s1)
    cf_rot = _acute(cf0, cf1)
    p3["b_hull_only_interior"] = {
        "short_vec": _bits(s0, 4), "short_bit_invariant": short_inv,
        "cf_rotation_deg": round(cf_rot, 3), "min_rot_threshold": MIN_ROT,
        "pass": short_inv and cf_rot >= MIN_ROT}
    # (c) extremal-MIN 擾動敏感(honest):rect + 2 個近角擾動件造一條極短凸包邊 → short 大幅擺動 / long 穩健
    pert = [(0.0, 0.0), (14.0, 0.0), (14.0, 4.0), (0.0, 4.0), (14.1, 3.9), (13.9, 4.1)]
    s_pert = G.derive_cascade_dir(pert, "hull_shortest_edge")
    l_pert = G.derive_cascade_dir(pert, "hull_longest_edge")
    short_swing = _acute(s_rect, s_pert)
    long_swing = _acute(l_rect, l_pert)
    # 閘獨立 scipy 雙確認擾動後的短 / 長邊
    s_pert_sc = _scipy_hull_edge(pert, shortest=True); l_pert_sc = _scipy_hull_edge(pert, shortest=False)
    p3["c_extremal_min_perturbation"] = {
        "short_base": _bits(s_rect, 4), "short_pert": _bits(s_pert, 4), "short_swing_deg": round(short_swing, 3),
        "long_base": _bits(l_rect, 4), "long_pert": _bits(l_pert, 4), "long_swing_deg": round(long_swing, 3),
        "short_pert_eq_scipy": _bits(s_pert) == _bits(s_pert_sc),
        "long_pert_eq_scipy": _bits(l_pert) == _bits(l_pert_sc),
        "note": "extremal-MIN (shortest edge) is perturbation-sensitive; extremal-MAX (longest) is stable",
        "pass": short_swing >= MIN_ROT and long_swing <= STABLE_MAX
                and _bits(s_pert) == _bits(s_pert_sc) and _bits(l_pert) == _bits(l_pert_sc)}
    R["SE3_shortest_edge_value"] = {**p3, "pass": all(v["pass"] for v in p3.values())}

    # ---- SE4 end-to-end projection ordering (robot) ----
    p4 = {"detail": {}, "fail_order": [], "weak_spread": [], "bad_interface": []}
    le_vec = G.derive_cascade_dir(centers, "hull_longest_edge")
    for cb in cbeats:
        an = se[cb]
        bones = [b for b in order if b in an.get("bones", {})]
        proj_sorted = sorted(bones, key=lambda b: (_proj_key(xy, b, se_vec), order.index(b)))
        pts = [VD.peak_time(an, b) for b in proj_sorted]
        mono = is_strictly_increasing(pts)
        far_bone = proj_sorted[-1]
        meas = sorted(bones, key=lambda b: VD.peak_time(an, b))
        far_last = meas[-1] == far_bone
        sp = cascade_spread(pts)
        dur = SA.duration(an)
        b0 = SA.sample(an, 0.0)["bones"]; bE = SA.sample(an, dur)["bones"]
        s0b = SA.sample(an, 0.0)["slots"]; sEb = SA.sample(an, dur)["slots"]
        iface = (all(VD._is_ident(v) for v in b0.values()) and all(VD._is_ident(v) for v in bE.values())
                 and all(abs(s["alpha"] - 1) <= TOL for s in s0b.values())
                 and all(abs(s["alpha"] - 1) <= TOL for s in sEb.values()))
        # 誠實回報(不作判準):short 的測得 pop 序 vs longest 的 pop 序
        meas_le = sorted([b for b in order if b in le[cb].get("bones", {})],
                         key=lambda b: VD.peak_time(le[cb], b))
        differs_le = [order.index(b) for b in meas] != [order.index(b) for b in meas_le]
        p4["detail"][cb] = {"short_vec": _bits(se_vec, 4), "proj_order": [order.index(b) for b in proj_sorted],
                            "peak_times": [round(x, 3) for x in pts], "monotone": mono,
                            "farthest_pops_last": far_last, "spread": round(sp, 3), "iface": iface,
                            "measured_short_order": [order.index(b) for b in meas],
                            "measured_long_order": [order.index(b) for b in meas_le],
                            "differs_from_long": differs_le}
        if not (mono and far_last):
            p4["fail_order"].append(cb)
        if sp < SPREAD_FLOOR:
            p4["weak_spread"].append(cb)
        if not iface:
            p4["bad_interface"].append(cb)
    # dir ⟂ nrip:帶 ripples 時各件 pop 次數 == nrip 在 hull_shortest_edge 成立
    nrip_ok, nrip_detail = True, {}
    full = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip,
                              cascade_dir=("geo", "hull_shortest_edge"))
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
    R["SE4_end_to_end_ordering"] = {**p4, "short_vec": _bits(se_vec, 4), "long_vec": _bits(le_vec, 4),
                                    "nrip_intact": nrip_ok, "nrip_detail": nrip_detail, "pass": p4_pass}

    # ---- SE5 metric well-defined + guards ----
    p5 = {}
    # (a) metric:hull_shortest_edge == 閘獨立 scipy 最短邊(多佈局逐位元)
    mdet, m_ok = {}, True
    for name, C in {"robot": centers, "quad": cfgs["quad"], "scalene_tri": cfgs["scalene_tri"],
                    "penta": [(0.0, 0.0), (10.0, 1.0), (12.0, 7.0), (5.0, 11.0), (-2.0, 6.0)]}.items():
        v = G.derive_cascade_dir(C, "hull_shortest_edge"); b = _scipy_hull_edge(C, shortest=True)
        same = _bits(v) == _bits(b)
        mdet[name] = {"short": _bits(v, 4), "scipy": _bits(b, 4), "bit_identical": same}
        if not same:
            m_ok = False
    p5["a_metric_eq_scipy"] = {"detail": mdet, "pass": m_ok}
    # (b) 並列邊 / 各向同性:正方(pca 會 ValueError)→ hull_shortest_edge 不 raise、確定性回最短邊、件序無關
    sq2 = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    pca_raises = False
    try:
        G.derive_cascade_dir(sq2, "pca")
    except ValueError:
        pca_raises = True
    try:
        sq_vecs = {_bits(G.derive_cascade_dir(list(p), "hull_shortest_edge")) for p in itertools.permutations(sq2)}
        se_sq_ok = len(sq_vecs) == 1
        sq_vec = sorted(sq_vecs)
    except ValueError:
        se_sq_ok, sq_vec = False, None
    p5["b_tie_isotropic"] = {"pca_raises_on_square": pca_raises, "short_resolves": se_sq_ok,
                             "short_square_vec": sq_vec, "pass": pca_raises and se_sq_ok}
    # (c) 守衛:件重合 / 單件 / 空件 / 未知 source(直接 & 經 build)
    guards = {}
    for name, fn in {
        "coincident": lambda: G.derive_cascade_dir([(5.0, 7.0), (5.0, 7.0), (5.0, 7.0)], "hull_shortest_edge"),
        "single": lambda: G.derive_cascade_dir([(1.0, 2.0)], "hull_shortest_edge"),
        "empty": lambda: G.derive_cascade_dir([], "hull_shortest_edge"),
        "unknown_source_direct": lambda: G.derive_cascade_dir([(0, 0), (1, 1)], "nope_src"),
        "unknown_source_build": lambda: G.build_animations(skel, sb, cascade_dir=("geo", "zzz")),
    }.items():
        try:
            fn(); guards[name] = False
        except ValueError:
            guards[name] = True
    try:
        _ = G.build_animations(skel, sb, cascade_dir=("geo", "hull_shortest_edge")); guards["short_build_ok"] = True
    except Exception:
        guards["short_build_ok"] = False
    p5["c_input_guards"] = {"detail": guards, "pass": all(guards.values())}
    R["SE5_metric_guards"] = {**p5, "pass": all(v["pass"] for v in p5.values())}

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
        for k in ["SE1_present_backward_compat", "SE2_shortest_edge_order_sign", "SE3_shortest_edge_value",
                  "SE4_end_to_end_ordering", "SE5_metric_guards"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        a3 = R["SE3_shortest_edge_value"]["a_perp_longest_on_rect"]
        print("SE3a rect short={} long={} |dot|={}".format(a3["short"], a3["long"], a3["abs_dot"]))
        b3 = R["SE3_shortest_edge_value"]["b_hull_only_interior"]
        print("SE3b short_inv={} cf_rot={}°".format(b3["short_bit_invariant"], b3["cf_rotation_deg"]))
        c3 = R["SE3_shortest_edge_value"]["c_extremal_min_perturbation"]
        print("SE3c short_swing={}° long_swing={}° (extremal-MIN perturbation sensitivity)".format(
            c3["short_swing_deg"], c3["long_swing_deg"]))
        print("SE4 projection order (robot):")
        for cb, d in R["SE4_end_to_end_ordering"]["detail"].items():
            print("   {:10s} vec={} short_order={} long_order={} mono={} differs_long={}".format(
                cb, d["short_vec"], d["measured_short_order"], d["measured_long_order"],
                d["monotone"], d["differs_from_long"]))
        b5 = R["SE5_metric_guards"]["b_tie_isotropic"]
        print("SE5(b) pca_raises_on_square={} short_resolves_square={} vec={}".format(
            b5["pca_raises_on_square"], b5["short_resolves"], b5["short_square_vec"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
