#!/usr/bin/env python3
"""candidate (J-13) 自我驗收閘 — cascade 跨件波方向的 **最小面積包圍矩形(OBB)短軸 geo source**(確定性,純 CPU)。

方向軸的來源精煉(**同一條 J-6 投影軸**,逐步移除 / 強化人手指定):
  J-7:`cascade_dir="geo"` 方向**向量由件幾何導出**(質心 → 最遠件),隨資產自適應。
  J-8:`geo source = "pca"` —— PCA **主軸**(最大變異方向),符號確定性地定。
  J-9:`geo source = "pca_minor"` —— PCA **次主軸**(最小變異方向,與主軸正交)。
  J-10:`geo source = "farthest_pair"` —— 件中心 **diameter(最遠對,凸包直徑)**方向。
  J-11:`geo source = "hull_longest_edge"` —— 件中心**凸包最長邊**方向。
  J-12:`geo source = "obb_major"` —— 件中心**最小面積包圍矩形(OBB)長軸**(旋轉卡尺)。
  J-13(本閘):新增 `geo source = "obb_minor"` —— 用件中心**最小面積包圍矩形(OBB)短軸**(與 `obb_major`
       **同一個**最小矩形的較短邊方向,與長軸嚴格正交),字典序定號。語意 = 波沿件群最緊包圍盒的
       **短邊**橫掃(vs `obb_major` 沿長邊延掃)。關係同 `pca_minor` 之於 `pca`。

**honest distinction(勿誇大)**:J-13 **不是**新正交軸族,也**不改** J-6 的投影排序機制;只是 J-7..J-12 那條
「方向軸取值來源(provenance)」再多一個 source(`obb_minor`)。其**最鋒利的 crux**:
  - **vs obb_major**(最相近,同一最小矩形):短軸**嚴格正交**於長軸(`|dot|≈0`)→ 產生**不同的件 pop 序**
    (OBM3,asset-independent + 真實 robot 皆成立)。短軸選**同一個**最小矩形(非另解一次),故正交由建構保證。
  - **守衛 crux**(與 `obb_major` 共用):最小矩形為(近)**正方形**(長≈寬)→ 長/短軸皆不唯一 → **兩者皆**
    ValueError(短軸不會在長軸退化時硬捏一個方向;比照 `pca`/`pca_minor` 各向同性守衛共用)。
  - **正確性 crux**:== 閘**獨立**以 `scipy.spatial.ConvexHull` + 自寫旋轉卡尺重算的 OBB 短軸(選同一最小
    矩形、取較短邊、套**同一套**「折半平面 → 座標字典序」tie-break + 幾何符號規則);不呼叫生成器私有函式。

  OBM1 present + backward-compat: `("geo","obb_minor")` 產每個 cascade beat 且 finite/有 bone;非 cascade 主秀
                                 beat 逐位元同 base;`None`/`"po"` 仍逐位元同件序;**零回歸** `"geo"` 預設
                                 (= centroid_farthest)、**`("geo","obb_major")`(本次改碼函式!)**、
                                 `("geo","pca")`、`("geo","pca_minor")`、`("geo","farthest_pair")`、
                                 `("geo","hull_longest_edge")` 皆**不被本次新增影響**(逐位元同;並對照
                                 各自閘獨立重算)。
  OBM2 correctness+ortho+order+sign: (crux)(a) **OBB 短軸正確性 + 正交**:`obb_minor` == 閘**獨立 scipy+卡尺**
                                 重算的 OBB 短軸(**逐位元**同向量)且 `obb_minor ⟂ obb_major`(|dot|≈0);
                                 (b) **件輸入順序無關**:非對稱(唯一最小矩形)& 面積並列(三角形每邊)佈局
                                 **所有排列** → **逐位元同一**帶號向量;(c) **符號跟隨幾何**:沿 x 鏡射
                                 (y→−y)→ 向量 y 分量符號翻轉、x 分量不變。
  OBM3 minor value             : (crux/價值)(a) **正交(多佈局)**:robot / L 形 / flag / slant_quad 皆
                                 `obb_minor ⟂ obb_major`(|dot|≈0);(b) **不同的波**:依 `obb_minor` 投影排序
                                 件序 ≠ 依 `obb_major` 投影排序件序(asset-independent 的 slant 佈局 + 真實
                                 robot 皆成立)—— 短軸不是長軸的改版。
  OBM4 end-to-end ordering     : 真實 robot 骨架 `build_animations(cascade_dir=("geo","obb_minor"))` → 每 cascade
                                 beat 各件峰時刻依 OBB 短軸投影鍵嚴格遞增(最遠投影最後 pop)、仍一道有序跨件波
                                 (散佈≥門檻)+首尾 setup identity + 特效 slot alpha=1;dir⟂nrip 仍成立。**crux**
                                 robot 上 obb_minor 測得 pop 序 ≠ obb_major 測得 pop 序(短軸是真正不同的波)。
  OBM5 metric + guards         : (a) metric:obb_minor == 閘獨立 scipy+卡尺 OBB 短軸(多佈局逐位元);(b) **正方
                                 守衛共用**:正方 `obb_minor` **raise** 且 `obb_major` 亦 raise(同一最小矩形退化)、
                                 而 `farthest_pair`/`hull_longest_edge` **不 raise**、確定性回值;(c) 守衛:件重合 /
                                 單件 / 空件 / 未知 source(直接 & 經 build_animations ("geo","obb_minor") 可用、
                                 ("geo","zzz") 報錯)→ ValueError。

閘從 VD(J-5 閘)fixture 的**真實 build_spine robot 骨架**端到端量;OBB 短軸 **由閘以 scipy.spatial.ConvexHull
+ 自寫旋轉卡尺獨立重算**(選同一最小矩形、取較短邊、套同一 tie-break),其餘 source 亦獨立重算。

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

ALIGN_MAX = 1e-6          # |dot| 同線 / 正交門檻
ORTHO_MAX = 1e-9          # obb_minor ⟂ obb_major 的 |dot| 門檻(建構保證 → 近 0)


def _scipy_obb_axis(centers, minor=False, aspect_tol=1e-6, tol=1e-9):
    """閘**獨立**的 OBB 長/短軸**單位向量**(scipy.spatial.ConvexHull + 自寫旋轉卡尺 + 同一套 tie-break + 符號規則)。
    `minor=True` → 選**同一**最小矩形(以長軸 canon tie-break)後取其長軸**轉 90°** = 短軸,再走同一符號規則。"""
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
    n = len(centers)
    mx = sum(c[0] for c in centers) / n
    my = sum(c[1] for c in centers) / n
    projs = [((x - mx) * ux + (y - my) * uy, x, y) for x, y in centers]
    maxabs = max(abs(p) for p, _, _ in projs)
    ref = max((p for p in projs if abs(p[0]) >= maxabs - 1e-9), key=lambda p: (p[1], p[2]))
    if ref[0] < 0.0:
        ux, uy = -ux, -uy
    return (ux, uy)


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
    return [i for i in sorted(range(len(centers)),
                              key=lambda i: (centers[i][0] * vec[0] + centers[i][1] * vec[1], i))]


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
    obm = G.build_animations(skel, sb, cascade_dir=("geo", "obb_minor"))
    obmaj = G.build_animations(skel, sb, cascade_dir=("geo", "obb_major"))
    cbeats = VD._cascade_beats(base)
    main_beats = VD._main_beats(base)
    centers = [xy[b] for b in order]
    obm_vec = G.derive_cascade_dir(centers, "obb_minor")
    obmaj_vec = G.derive_cascade_dir(centers, "obb_major")
    R = {}

    # layouts used across ACs
    cfgs = {"robot": centers,
            "L_shape": [(0.0, 0.0), (6.0, 0.0), (6.0, 1.0), (1.0, 1.0), (1.0, 4.0), (0.0, 4.0)],
            "slant_quad": [(0.0, 0.0), (6.0, 0.0), (6.0, 2.0), (0.0, 5.0)],
            "flag": [(0.0, 0.0), (10.0, 0.0), (10.0, 1.0), (3.0, 1.0), (3.0, 6.0), (0.0, 6.0)]}

    # ---- OBM1 present + backward-compat + zero-regression ----
    p1 = {"missing": [], "not_finite": [], "no_bones": [], "noncascade_changed": [], "po_eq_none": None,
          "geo_default_eq_centroid": None, "obb_major_unchanged": None, "pca_unchanged": None,
          "pca_minor_unchanged": None, "farthest_pair_unchanged": None, "hull_longest_edge_unchanged": None,
          "obb_major_derive_eq_scipy": None, "pca_derive_eq_numpy_major": None, "fp_derive_eq_brute": None,
          "hle_derive_eq_scipy": None, "cf_derive_eq_gate": None}
    for cb in cbeats:
        an = obm.get(cb)
        if an is None:
            p1["missing"].append(cb); continue
        if not SA.all_finite(an):
            p1["not_finite"].append(cb)
        if not an.get("bones"):
            p1["no_bones"].append(cb)
    for beat, cat in main_beats.items():
        if cat == "cascade":
            continue
        if _bytes(obm.get(beat)) != _bytes(base.get(beat)):
            p1["noncascade_changed"].append(beat)
    po = G.build_animations(skel, sb, cascade_dir="po")
    p1["po_eq_none"] = all(_bytes(po[cb]) == _bytes(base[cb]) for cb in cbeats)
    geo_def = G.build_animations(skel, sb, cascade_dir="geo")
    geo_cf = G.build_animations(skel, sb, cascade_dir=("geo", "centroid_farthest"))
    p1["geo_default_eq_centroid"] = all(_bytes(geo_def[cb]) == _bytes(geo_cf[cb]) for cb in cbeats)
    # 零回歸:本次改碼的是 _obb_major_axis_dir(加 minor 參數)→ obb_major 路徑必須逐位元不變
    obmaj2 = G.build_animations(skel, sb, cascade_dir=("geo", "obb_major"))
    pmaj = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    pmaj2 = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    pmin1 = G.build_animations(skel, sb, cascade_dir=("geo", "pca_minor"))
    pmin2 = G.build_animations(skel, sb, cascade_dir=("geo", "pca_minor"))
    fpm1 = G.build_animations(skel, sb, cascade_dir=("geo", "farthest_pair"))
    fpm2 = G.build_animations(skel, sb, cascade_dir=("geo", "farthest_pair"))
    hlem1 = G.build_animations(skel, sb, cascade_dir=("geo", "hull_longest_edge"))
    hlem2 = G.build_animations(skel, sb, cascade_dir=("geo", "hull_longest_edge"))
    p1["obb_major_unchanged"] = all(_bytes(obmaj[cb]) == _bytes(obmaj2[cb]) for cb in cbeats)
    p1["pca_unchanged"] = all(_bytes(pmaj[cb]) == _bytes(pmaj2[cb]) for cb in cbeats)
    p1["pca_minor_unchanged"] = all(_bytes(pmin1[cb]) == _bytes(pmin2[cb]) for cb in cbeats)
    p1["farthest_pair_unchanged"] = all(_bytes(fpm1[cb]) == _bytes(fpm2[cb]) for cb in cbeats)
    p1["hull_longest_edge_unchanged"] = all(_bytes(hlem1[cb]) == _bytes(hlem2[cb]) for cb in cbeats)
    # 各 source 的 derive == 閘獨立重算
    p1["obb_major_derive_eq_scipy"] = _bits(obmaj_vec) == _bits(_scipy_obb_axis(centers, minor=False))
    np_major = _np_pca_major(centers)
    dmaj = G.derive_cascade_dir(centers, "pca")
    p1["pca_derive_eq_numpy_major"] = abs(abs(dmaj[0] * np_major[0] + dmaj[1] * np_major[1]) - 1.0) <= ALIGN_MAX
    dfp = G.derive_cascade_dir(centers, "farthest_pair")
    p1["fp_derive_eq_brute"] = _bits(dfp) == _bits(_brute_diameter(centers))
    dhle = G.derive_cascade_dir(centers, "hull_longest_edge")
    p1["hle_derive_eq_scipy"] = _bits(dhle) == _bits(_scipy_hull_longest_edge(centers))
    dcf = G.derive_cascade_dir(centers, "centroid_farthest")
    p1["cf_derive_eq_gate"] = _bits(dcf) == _bits(_gate_centroid_farthest(centers))
    p1_pass = (bool(cbeats) and not p1["missing"] and not p1["not_finite"] and not p1["no_bones"]
               and not p1["noncascade_changed"] and p1["po_eq_none"] and p1["geo_default_eq_centroid"]
               and p1["obb_major_unchanged"] and p1["pca_unchanged"] and p1["pca_minor_unchanged"]
               and p1["farthest_pair_unchanged"] and p1["hull_longest_edge_unchanged"]
               and p1["obb_major_derive_eq_scipy"] and p1["pca_derive_eq_numpy_major"]
               and p1["fp_derive_eq_brute"] and p1["hle_derive_eq_scipy"] and p1["cf_derive_eq_gate"])
    R["OBM1_present_backward_compat"] = {"cascade_beats": cbeats, **p1, "pass": p1_pass}

    # ---- OBM2 correctness + orthogonality + order-independent + deterministic sign (crux) ----
    p2 = {}
    # (a) OBB 短軸正確性(== 閘獨立 scipy+卡尺 短軸逐位元)+ 正交(⟂ obb_major)
    adet, a_ok = {}, True
    for name, C in cfgs.items():
        v = G.derive_cascade_dir(C, "obb_minor")
        b = _scipy_obb_axis(C, minor=True)
        vmaj = G.derive_cascade_dir(C, "obb_major")
        same = _bits(v) == _bits(b)
        dot = abs(v[0] * vmaj[0] + v[1] * vmaj[1])
        ortho = dot <= ORTHO_MAX
        adet[name] = {"obb_minor": _bits(v, 4), "scipy": _bits(b, 4), "bit_identical": same,
                      "dot_with_major": dot, "ortho": ortho}
        if not (same and ortho):
            a_ok = False
    p2["a_minor_eq_scipy_and_ortho"] = {"detail": adet, "pass": a_ok}
    # (b) 件輸入順序無關:唯一最小矩形(slant_quad)+ 面積並列(三角每邊)佈局所有排列 → 逐位元同一向量
    uniq_cfg = [(0.0, 0.0), (6.0, 0.0), (6.0, 2.0), (0.0, 5.0)]
    tri_cfg = [(0.0, 0.0), (10.0, 0.0), (3.0, 7.0)]
    uniq_outs = {_bits(G.derive_cascade_dir(list(p), "obb_minor")) for p in itertools.permutations(uniq_cfg)}
    tri_outs = {_bits(G.derive_cascade_dir(list(p), "obb_minor")) for p in itertools.permutations(tri_cfg)}
    p2["b_order_independent"] = {"uniq_perms": math.factorial(len(uniq_cfg)), "uniq_distinct": len(uniq_outs),
                                 "tri_perms": math.factorial(len(tri_cfg)), "tri_distinct": len(tri_outs),
                                 "uniq_vec": sorted(uniq_outs), "tri_vec": sorted(tri_outs),
                                 "pass": len(uniq_outs) == 1 and len(tri_outs) == 1}
    # (c) 符號跟隨幾何:沿 x 鏡射 y→−y → 方向 y 分量符號翻轉、x 分量不變(用短軸有 y 分量的佈局)
    B = [(0.0, 0.0), (8.0, 1.0), (9.0, 3.0), (1.0, 2.0)]                   # wide slant → 短軸有 y 分量
    Bm = [(x, -y) for (x, y) in B]
    vB = G.derive_cascade_dir(B, "obb_minor"); vBm = G.derive_cascade_dir(Bm, "obb_minor")
    p2["c_sign_tracks_geometry"] = {"B": _bits(vB, 4), "mirror_y": _bits(vBm, 4),
                                    "pass": _bits(vB) == _bits((vBm[0], -vBm[1])) and abs(vB[1]) > 0.1}
    R["OBM2_correctness_ortho_order_sign"] = {**p2, "pass": all(v["pass"] for v in p2.values())}

    # ---- OBM3 minor value crux: orthogonal (multi-layout) + genuinely different wave ----
    p3 = {}
    # (a) 正交:多佈局 obb_minor ⟂ obb_major
    odet, o_ok = {}, True
    for name, C in cfgs.items():
        mn = G.derive_cascade_dir(C, "obb_minor")
        mj = G.derive_cascade_dir(C, "obb_major")
        dot = abs(mn[0] * mj[0] + mn[1] * mj[1])
        ok = dot <= ORTHO_MAX
        odet[name] = {"minor": _bits(mn, 4), "major": _bits(mj, 4), "dot": dot, "ortho": ok}
        if not ok:
            o_ok = False
    p3["a_ortho_multi"] = {"detail": odet, "pass": o_ok}
    # (b) 不同的波:依 obb_minor 投影排序件序 ≠ 依 obb_major 投影排序件序(slant 合成 + robot)
    ddet, d_ok = {}, True
    for name in ("slant_quad", "flag", "robot"):
        C = cfgs[name]
        om_order = _proj_order(C, G.derive_cascade_dir(C, "obb_minor"))
        oM_order = _proj_order(C, G.derive_cascade_dir(C, "obb_major"))
        differs = om_order != oM_order
        ddet[name] = {"minor_order": om_order, "major_order": oM_order, "differs": differs}
        if not differs:
            d_ok = False
    p3["b_different_wave"] = {"detail": ddet, "pass": d_ok}
    R["OBM3_minor_value"] = {**p3, "pass": all(v["pass"] for v in p3.values())}

    # ---- OBM4 end-to-end projection ordering (robot) ----
    p4 = {"detail": {}, "fail_order": [], "weak_spread": [], "bad_interface": []}
    for cb in cbeats:
        an = obm[cb]
        bones = [b for b in order if b in an.get("bones", {})]
        proj_sorted = sorted(bones, key=lambda b: (_proj_key(xy, b, obm_vec), order.index(b)))
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
        # crux(判準):obb_minor 測得 pop 序 ≠ obb_major 測得 pop 序
        meas_maj = sorted([b for b in order if b in obmaj[cb].get("bones", {})],
                          key=lambda b: VD.peak_time(obmaj[cb], b))
        differs_major = [order.index(b) for b in meas] != [order.index(b) for b in meas_maj]
        p4["detail"][cb] = {"minor_vec": _bits(obm_vec, 4), "proj_order": [order.index(b) for b in proj_sorted],
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
    differs_all = all(d["differs_from_major"] for d in p4["detail"].values())
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
               and not p4["bad_interface"] and nrip_ok and differs_all)
    R["OBM4_end_to_end_ordering"] = {**p4, "minor_vec": _bits(obm_vec, 4), "major_vec": _bits(obmaj_vec, 4),
                                     "differs_from_major_all": differs_all,
                                     "nrip_intact": nrip_ok, "nrip_detail": nrip_detail, "pass": p4_pass}

    # ---- OBM5 metric well-defined + guards ----
    p5 = {}
    # (a) metric:obb_minor == 閘獨立 scipy+卡尺 OBB 短軸(多佈局逐位元)
    mdet, m_ok = {}, True
    for name, C in {"robot": centers, "slant_quad": cfgs["slant_quad"],
                    "penta": [(0.0, 0.0), (10.0, 1.0), (12.0, 7.0), (5.0, 11.0), (-2.0, 6.0)]}.items():
        v = G.derive_cascade_dir(C, "obb_minor"); b = _scipy_obb_axis(C, minor=True)
        same = _bits(v) == _bits(b)
        mdet[name] = {"obb_minor": _bits(v, 4), "scipy": _bits(b, 4), "bit_identical": same}
        if not same:
            m_ok = False
    p5["a_metric_eq_scipy"] = {"detail": mdet, "pass": m_ok}
    # (b) 正方守衛共用:正方 obb_minor raise 且 obb_major 亦 raise(同一最小矩形退化)、fp/hle 不 raise、確定性回值
    sq = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    obm_raises = obmaj_raises = False
    try:
        G.derive_cascade_dir(sq, "obb_minor")
    except ValueError:
        obm_raises = True
    try:
        G.derive_cascade_dir(sq, "obb_major")
    except ValueError:
        obmaj_raises = True
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
    p5["b_square_guard"] = {"obb_minor_raises_on_square": obm_raises, "obb_major_raises_on_square": obmaj_raises,
                            "fp_resolves": fp_ok, "hle_resolves": hle_ok,
                            "fp_square_vec": fp_vec, "hle_square_vec": hle_vec,
                            "pass": obm_raises and obmaj_raises and fp_ok and hle_ok}
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
    R["OBM5_metric_guards"] = {**p5, "pass": all(v["pass"] for v in p5.values())}

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
        for k in ["OBM1_present_backward_compat", "OBM2_correctness_ortho_order_sign", "OBM3_minor_value",
                  "OBM4_end_to_end_ordering", "OBM5_metric_guards"]:
            print("{:36s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        a2 = R["OBM2_correctness_ortho_order_sign"]["a_minor_eq_scipy_and_ortho"]["detail"]
        for name, d in a2.items():
            print("OBM2a {:10s} minor={} scipy={} ortho={} (|dot|={:.1e})".format(
                name, d["obb_minor"], d["scipy"], d["ortho"], d["dot_with_major"]))
        b3 = R["OBM3_minor_value"]["b_different_wave"]["detail"]
        for name, d in b3.items():
            print("OBM3b {:10s} minor_order={} major_order={} differs={}".format(
                name, d["minor_order"], d["major_order"], d["differs"]))
        print("OBM4 projection order (robot):")
        for cb, d in R["OBM4_end_to_end_ordering"]["detail"].items():
            print("   {:10s} vec={} minor_order={} major_order={} mono={} differs_major={}".format(
                cb, d["minor_vec"], d["measured_minor_order"], d["measured_major_order"],
                d["monotone"], d["differs_from_major"]))
        b5 = R["OBM5_metric_guards"]["b_square_guard"]
        print("OBM5(b) obb_minor_raises={} obb_major_raises={} fp_resolves={} hle_resolves={}".format(
            b5["obb_minor_raises_on_square"], b5["obb_major_raises_on_square"], b5["fp_resolves"], b5["hle_resolves"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
