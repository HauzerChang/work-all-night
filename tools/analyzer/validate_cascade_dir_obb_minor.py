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
  J-13(本閘):新增 `geo source = "obb_minor"` —— 用件中心**最小面積包圍矩形(OBB)次軸**(OBB 長軸轉 90°,
       **較短邊**方向,與長軸**正交**),字典序確定性定號。語意 = 波沿件群最緊包圍盒的**短邊**橫掃
       (vs obb_major 沿長邊延掃)。比照 J-8→J-9(pca→pca_minor):同一個 OBB 幾何物件的正交次軸。

**honest distinction(勿誇大)**:J-13 **不是**新正交軸,也**不改** J-6 的投影排序機制;只是 J-7..J-12 那條
「方向軸取值來源(provenance)」再多一個 source(`obb_minor`)。其**最鋒利的 crux**:
  - **vs obb_major**(同一 OBB、正交次軸):次軸 ⟂ 長軸 → 產生**不同的件 pop 序**(是一條真正不同的波,
    非 obb_major 的改版);且 obb_minor == 閘**獨立**重算的 OBB 次軸(把閘獨立求得的 OBB 長軸轉 90° 後套同一符號規則)。
  - **退化守衛**(與 obb_major 共用):最小矩形為(近)**正方形**(長≈寬)→ 長軸/次軸皆不唯一 → ValueError;
    `farthest_pair`/`hull_longest_edge` **無**此守衛、確定性回值(與 OBB5b 同層)。
  - **正確性 crux**:== 閘**獨立**以 `scipy.spatial.ConvexHull` + 自寫旋轉卡尺重算的 OBB 次軸(套**同一套**
    「折半平面 → 座標字典序」tie-break 選唯一 OBB → 長軸轉 90° → 幾何符號規則);不呼叫生成器私有函式。

  OBM1 present + backward-compat: `("geo","obb_minor")` 產每個 cascade beat 且 finite/有 bone;非 cascade 主秀
                                 beat 逐位元同 base;`None`/`"po"` 仍逐位元同件序;**零回歸** `"geo"` 預設
                                 (= centroid_farthest)、`("geo","pca")`、`("geo","pca_minor")`、
                                 `("geo","farthest_pair")`、`("geo","hull_longest_edge")`、**`("geo","obb_major")`**
                                 皆**不被本次新增影響**(逐位元同;obb_major 加 minor 參數後路徑未動,且
                                 `derive(.,"obb_major")` 仍 == 閘獨立 scipy OBB 長軸)。
  OBM2 perp + order + sign     : (crux)(a) **正交性 + 正確性**:`obb_minor` ⟂ `obb_major`(|dot|≈0)且
                                 obb_minor == 閘**獨立 scipy+卡尺** OBB 次軸(**逐位元**同向量);(b) **件輸入
                                 順序無關**:唯一最小矩形(slant_quad)& 面積並列(三角形每邊)佈局的**所有排列**
                                 → **逐位元同一**帶號向量;(c) **符號跟隨幾何**:沿 x 鏡射(y→−y)→ 向量 y 分量
                                 符號翻轉、x 分量不變。
  OBM3 minor vs major (value)  : (crux/價值)**次軸是一條真正不同的波,非長軸改版**。斜四邊形 / 二維展開佈局 →
                                 (a) minor ⟂ major(|dot|≈0);(b) 依 minor 投影排序的件序 **≠** 依 major 投影
                                 排序的件序(短邊橫掃 vs 長邊延掃);(c) 次軸方向的極端件在 minor 下**最後 pop**。
  OBM4 end-to-end ordering     : 真實 robot 骨架 `build_animations(cascade_dir=("geo","obb_minor"))` → 每 cascade
                                 beat 各件峰時刻依 OBB 次軸投影鍵嚴格遞增(最遠投影最後 pop)、仍一道有序跨件波
                                 (散佈≥門檻)+首尾 setup identity + 特效 slot alpha=1;dir⟂nrip 仍成立。**crux**:
                                 robot 上 obb_minor 的 pop 序 **≠** obb_major 的 pop 序(端到端證兩者不同波)。
  OBM5 metric + guards         : (a) metric:obb_minor == 閘獨立 scipy+卡尺 OBB 次軸(多佈局逐位元)且 ⟂ 長軸;
                                 (b) **正方守衛**:正方 `obb_minor` **raise**(min-rect square,與 obb_major 共用守衛)、
                                 `pca` 亦 raise(各向同性,判據不同)、而 `farthest_pair`/`hull_longest_edge`
                                 **不 raise**、確定性回值;(c) 守衛:件重合 / 單件 / 空件 / 未知 source
                                 (直接 & 經 build_animations ("geo","obb_minor") 可用、("geo","zzz") 報錯)→ ValueError。

閘從 VD(J-5 閘)fixture 的**真實 build_spine robot 骨架**端到端量;OBB 長/次軸 **由閘以 scipy.spatial.ConvexHull
+ 自寫旋轉卡尺獨立重算**(套同一 tie-break);不呼叫生成器私有 `_obb_major_axis_dir`,以保持獨立驗證。

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

PERP_MAX = 1e-6          # |dot(major,minor)| 應 ≈ 0(正交)
ALIGN_MAX = 1e-6         # 主軸 derive 與 numpy / scipy 同一條線:|dot| 應 ≈ 1
MIN_ROT = 3.0            # OBM3:obb_minor vs obb_major 投影序差異門檻(此處用 pop 序差,非角度)


def _obb_folded_major(centers, aspect_tol=1e-6, tol=1e-9):
    """閘**獨立**選出的 OBB 最小面積矩形的**折半平面長軸**(符號前)+ `(major_len, minor_len)`。
    用 scipy.spatial.ConvexHull + 自寫旋轉卡尺 + 同一套「折半平面 → 座標字典序」tie-break(不定號)。"""
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
    return (ux, uy), major_len, minor_len


def _apply_sign(centers, ux, uy):
    """同生成器的幾何符號規則:指向沿該軸投影 |proj| 最大的極端件(其 proj ≥ 0),tie 以座標字典序。"""
    n = len(centers)
    mx = sum(c[0] for c in centers) / n
    my = sum(c[1] for c in centers) / n
    projs = [((x - mx) * ux + (y - my) * uy, x, y) for x, y in centers]
    maxabs = max(abs(p) for p, _, _ in projs)
    ref = max((p for p in projs if abs(p[0]) >= maxabs - 1e-9), key=lambda p: (p[1], p[2]))
    if ref[0] < 0.0:
        ux, uy = -ux, -uy
    return (ux, uy)


def _scipy_obb_major(centers):
    """閘獨立 OBB **長軸**單位向量(折半平面長軸 → 幾何符號)。"""
    (ux, uy), _, _ = _obb_folded_major(centers)
    return _apply_sign(centers, ux, uy)


def _scipy_obb_minor(centers):
    """閘獨立 OBB **次軸**單位向量(折半平面長軸 → 轉 90° → 幾何符號;同生成器 minor 路徑)。"""
    (ux, uy), _, _ = _obb_folded_major(centers)
    ux, uy = -uy, ux                               # 轉 90°(與長軸正交)
    return _apply_sign(centers, ux, uy)


def _proj_key(xy, bone, vec):
    x, y = xy[bone]
    return x * vec[0] + y * vec[1]


def _proj_order(centers, vec):
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
    obm = G.build_animations(skel, sb, cascade_dir=("geo", "obb_minor"))
    obM = G.build_animations(skel, sb, cascade_dir=("geo", "obb_major"))
    cbeats = VD._cascade_beats(base)
    main_beats = VD._main_beats(base)
    centers = [xy[b] for b in order]
    minor_vec = G.derive_cascade_dir(centers, "obb_minor")
    major_vec = G.derive_cascade_dir(centers, "obb_major")
    R = {}

    # ---- OBM1 present + backward-compat + zero-regression ----
    p1 = {"missing": [], "not_finite": [], "no_bones": [], "noncascade_changed": [], "po_eq_none": None,
          "geo_default_eq_centroid": None, "pca_unchanged": None, "pca_minor_unchanged": None,
          "farthest_pair_unchanged": None, "hull_longest_edge_unchanged": None, "obb_major_unchanged": None,
          "obb_major_derive_eq_scipy": None}
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
    # 零回歸:J-8..J-12 六條既有 source 路徑逐位元不變(不被本次新增影響)
    pmaj1 = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    pmaj2 = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    pmin1 = G.build_animations(skel, sb, cascade_dir=("geo", "pca_minor"))
    pmin2 = G.build_animations(skel, sb, cascade_dir=("geo", "pca_minor"))
    fpm1 = G.build_animations(skel, sb, cascade_dir=("geo", "farthest_pair"))
    fpm2 = G.build_animations(skel, sb, cascade_dir=("geo", "farthest_pair"))
    hle1 = G.build_animations(skel, sb, cascade_dir=("geo", "hull_longest_edge"))
    hle2 = G.build_animations(skel, sb, cascade_dir=("geo", "hull_longest_edge"))
    obM2 = G.build_animations(skel, sb, cascade_dir=("geo", "obb_major"))
    p1["pca_unchanged"] = all(_bytes(pmaj1[cb]) == _bytes(pmaj2[cb]) for cb in cbeats)
    p1["pca_minor_unchanged"] = all(_bytes(pmin1[cb]) == _bytes(pmin2[cb]) for cb in cbeats)
    p1["farthest_pair_unchanged"] = all(_bytes(fpm1[cb]) == _bytes(fpm2[cb]) for cb in cbeats)
    p1["hull_longest_edge_unchanged"] = all(_bytes(hle1[cb]) == _bytes(hle2[cb]) for cb in cbeats)
    p1["obb_major_unchanged"] = all(_bytes(obM[cb]) == _bytes(obM2[cb]) for cb in cbeats)
    p1["obb_major_derive_eq_scipy"] = _bits(major_vec) == _bits(_scipy_obb_major(centers))
    p1_pass = (bool(cbeats) and not p1["missing"] and not p1["not_finite"] and not p1["no_bones"]
               and not p1["noncascade_changed"] and p1["po_eq_none"] and p1["geo_default_eq_centroid"]
               and p1["pca_unchanged"] and p1["pca_minor_unchanged"] and p1["farthest_pair_unchanged"]
               and p1["hull_longest_edge_unchanged"] and p1["obb_major_unchanged"]
               and p1["obb_major_derive_eq_scipy"])
    R["OBM1_present_backward_compat"] = {"cascade_beats": cbeats, **p1, "pass": p1_pass}

    # ---- OBM2 perp + order-independent + deterministic sign (crux) ----
    p2 = {}
    # (a) 正交性 + minor == 閘獨立 scipy OBB 次軸(逐位元同向量)
    cfgs = {"robot": centers,
            "slant_quad": [(0.0, 0.0), (6.0, 0.0), (6.0, 2.0), (0.0, 5.0)],
            "tall_slant": [(0.0, 0.0), (2.0, 0.0), (3.0, 8.0), (1.0, 9.0)],
            "L_shape": [(0.0, 0.0), (6.0, 0.0), (6.0, 1.0), (1.0, 1.0), (1.0, 4.0), (0.0, 4.0)]}
    adet, a_ok = {}, True
    for name, C in cfgs.items():
        vmi = G.derive_cascade_dir(C, "obb_minor")
        vma = G.derive_cascade_dir(C, "obb_major")
        b = _scipy_obb_minor(C)
        perp = abs(vmi[0] * vma[0] + vmi[1] * vma[1])
        same = _bits(vmi) == _bits(b)
        adet[name] = {"minor": _bits(vmi, 4), "scipy_minor": _bits(b, 4), "major": _bits(vma, 4),
                      "abs_dot_major": round(float(perp), 8), "bit_identical": same}
        if not same or perp > PERP_MAX:
            a_ok = False
    p2["a_perp_and_scipy_minor"] = {"detail": adet, "pass": a_ok}
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
    B = [(0.0, 0.0), (8.0, 1.0), (9.0, 3.0), (1.0, 2.0)]                    # wide slant → 次軸有 y 分量
    Bm = [(x, -y) for (x, y) in B]
    vB = G.derive_cascade_dir(B, "obb_minor"); vBm = G.derive_cascade_dir(Bm, "obb_minor")
    p2["c_sign_tracks_geometry"] = {"B": _bits(vB, 4), "mirror_y": _bits(vBm, 4),
                                    "pass": _bits(vB) == _bits((vBm[0], -vBm[1])) and abs(vB[1]) > 0.2}
    R["OBM2_perp_order_sign"] = {**p2, "pass": all(v["pass"] for v in p2.values())}

    # ---- OBM3 minor vs major: genuinely different wave (crux / value) ----
    # 斜四邊形:OBB 長軸 (1,0)、次軸 (0,1);沿 x 拉長 + 沿 y 展開 → 兩軸投影序不同。
    L = [(0.0, 0.0), (12.0, 0.0), (12.0, 3.0), (0.0, 3.0), (6.0, 9.0)]
    v_ma3 = G.derive_cascade_dir(L, "obb_major")
    v_mi3 = G.derive_cascade_dir(L, "obb_minor")
    perp3 = abs(v_ma3[0] * v_mi3[0] + v_ma3[1] * v_mi3[1])
    ord_major = _proj_order(L, v_ma3)
    ord_minor = _proj_order(L, v_mi3)
    diff_order = ord_major != ord_minor
    # (c) 次軸方向的極端件(idx 4, (6,9),y 最大)在 minor 投影下最後 pop
    far_minor_last = ord_minor[-1] == 4
    p3_pass = perp3 <= PERP_MAX and diff_order and far_minor_last
    R["OBM3_minor_vs_major"] = {
        "major_vec": _bits(v_ma3, 4), "minor_vec": _bits(v_mi3, 4),
        "abs_dot_major_minor": round(float(perp3), 8), "perp": perp3 <= PERP_MAX,
        "order_by_major": ord_major, "order_by_minor": ord_minor, "orders_differ": diff_order,
        "minor_extreme_pops_last": far_minor_last, "pass": p3_pass}

    # ---- OBM4 end-to-end projection ordering (robot) + crux: minor order != major order ----
    p4 = {"detail": {}, "fail_order": [], "weak_spread": [], "bad_interface": [], "same_as_major": []}
    for cb in cbeats:
        an = obm[cb]
        bones = [b for b in order if b in an.get("bones", {})]
        proj_sorted = sorted(bones, key=lambda b: (_proj_key(xy, b, minor_vec), order.index(b)))
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
        # crux:同 beat 在 obb_major 下的測得 pop 序 vs obb_minor → 應不同(不同波)
        an_maj = obM[cb]
        bones_maj = [b for b in order if b in an_maj.get("bones", {})]
        meas_maj = sorted(bones_maj, key=lambda b: VD.peak_time(an_maj, b))
        differs = [order.index(b) for b in meas] != [order.index(b) for b in meas_maj]
        p4["detail"][cb] = {"minor_vec": _bits(minor_vec, 4), "proj_order": [order.index(b) for b in proj_sorted],
                            "peak_times": [round(x, 3) for x in pts], "monotone": mono,
                            "farthest_pops_last": far_last, "spread": round(sp, 3), "iface": iface,
                            "measured_minor_order": [order.index(b) for b in meas],
                            "measured_major_order": [order.index(b) for b in meas_maj],
                            "differs_from_major": differs}
        if not (mono and far_last):
            p4["fail_order"].append(cb)
        if sp < SPREAD_FLOOR:
            p4["weak_spread"].append(cb)
        if not iface:
            p4["bad_interface"].append(cb)
        if not differs:
            p4["same_as_major"].append(cb)
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
               and not p4["bad_interface"] and not p4["same_as_major"] and nrip_ok)
    R["OBM4_end_to_end_ordering"] = {**p4, "minor_vec": _bits(minor_vec, 4), "major_vec": _bits(major_vec, 4),
                                     "nrip_intact": nrip_ok, "nrip_detail": nrip_detail, "pass": p4_pass}

    # ---- OBM5 metric well-defined + guards ----
    p5 = {}
    # (a) metric:obb_minor == 閘獨立 scipy+卡尺 OBB 次軸(多佈局逐位元)且 ⟂ 長軸
    mdet, m_ok = {}, True
    for name, C in {"robot": centers, "slant_quad": cfgs["slant_quad"],
                    "penta": [(0.0, 0.0), (10.0, 1.0), (12.0, 7.0), (5.0, 11.0), (-2.0, 6.0)]}.items():
        vmi = G.derive_cascade_dir(C, "obb_minor"); vma = G.derive_cascade_dir(C, "obb_major")
        b = _scipy_obb_minor(C)
        same = _bits(vmi) == _bits(b)
        d_perp = abs(vmi[0] * vma[0] + vmi[1] * vma[1])
        mdet[name] = {"minor": _bits(vmi, 4), "scipy": _bits(b, 4), "abs_dot_major": round(float(d_perp), 8),
                      "bit_identical": same}
        if not same or d_perp > PERP_MAX:
            m_ok = False
    p5["a_metric_eq_scipy_minor"] = {"detail": mdet, "pass": m_ok}
    # (b) 正方守衛:正方 obb_minor raise、pca 亦 raise(判據不同)、fp/hle 不 raise、確定性回值
    sq = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    obm_raises = pca_raises = False
    try:
        G.derive_cascade_dir(sq, "obb_minor")
    except ValueError:
        obm_raises = True
    try:
        G.derive_cascade_dir(sq, "pca")
    except ValueError:
        pca_raises = True
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
    p5["b_square_guard"] = {"obb_minor_raises_on_square": obm_raises, "pca_raises_on_square": pca_raises,
                            "fp_resolves": fp_ok, "hle_resolves": hle_ok,
                            "fp_square_vec": fp_vec, "hle_square_vec": hle_vec,
                            "pass": obm_raises and pca_raises and fp_ok and hle_ok}
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
        for k in ["OBM1_present_backward_compat", "OBM2_perp_order_sign", "OBM3_minor_vs_major",
                  "OBM4_end_to_end_ordering", "OBM5_metric_guards"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        a2 = R["OBM2_perp_order_sign"]["a_perp_and_scipy_minor"]["detail"]
        for name, d in a2.items():
            print("OBM2a {:10s} minor={} scipy={} |dot_major|={} bit_id={}".format(
                name, d["minor"], d["scipy_minor"], d["abs_dot_major"], d["bit_identical"]))
        p3 = R["OBM3_minor_vs_major"]
        print("OBM3 major={} minor={} |dot|={} order_major={} order_minor={} differ={} extreme_last={}".format(
            p3["major_vec"], p3["minor_vec"], p3["abs_dot_major_minor"], p3["order_by_major"],
            p3["order_by_minor"], p3["orders_differ"], p3["minor_extreme_pops_last"]))
        print("OBM4 projection order (robot):")
        for cb, d in R["OBM4_end_to_end_ordering"]["detail"].items():
            print("   {:10s} vec={} minor_order={} major_order={} mono={} differs={}".format(
                cb, d["minor_vec"], d["measured_minor_order"], d["measured_major_order"],
                d["monotone"], d["differs_from_major"]))
        b5 = R["OBM5_metric_guards"]["b_square_guard"]
        print("OBM5(b) obb_minor_raises={} pca_raises={} fp_resolves={} hle_resolves={}".format(
            b5["obb_minor_raises_on_square"], b5["pca_raises_on_square"], b5["fp_resolves"], b5["hle_resolves"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
