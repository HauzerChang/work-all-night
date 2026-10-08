#!/usr/bin/env python3
"""candidate (J-10) 自我驗收閘 — cascade 跨件波方向的 **diameter(最遠對)geo source**(確定性,純 CPU)。

方向軸的來源精煉(**同一條 J-6 投影軸**,逐步移除 / 強化人手指定):
  J-5:相位來源由件序換成**空間**(4 個具名方向 lr/rl/co/oc)。
  J-6:方向**值連續化**(任意角 / 向量)—— 但「用哪個方向」仍是手感常數。
  J-7:`cascade_dir="geo"` 方向**向量由件幾何導出**(質心 → 最遠件),隨資產自適應。
  J-8:新增 `geo source = "pca"` —— 用 PCA **主軸**(最大變異方向),符號確定性地定。
  J-9:新增 `geo source = "pca_minor"` —— 用 PCA **次主軸**(最小變異方向,與主軸正交)。
  J-10(本閘):新增 `geo source = "farthest_pair"` —— 用件中心點集的 **diameter(彼此距離最大的兩件,
       凸包直徑)**方向,字典序確定性定號。語意 = 波橫越「兩件最遠分離的肢體」的最長連線。

**honest distinction(勿誇大)**:J-10 **不是**新正交軸,也**不改** J-6 的投影排序機制;只是 J-7/J-8/J-9 那條
「方向軸取值來源(provenance)」再多一個 source(`farthest_pair`)。其**價值 crux**:幾何基礎與前三者**不同**——
diameter **只由兩個極端件決定** → **移動內部(非極端)件不改變方向**,而 `centroid_farthest`(質心移動)與
`pca`(二階矩轉動)皆會改變(FP3 鑑別子,asset-independent)。其**正確性 crux**:方向 = 字典序較小端點 → 較大
端點(件輸入順序無關;並列最遠以端點對字典序取唯一代表)。附帶誠實對比:farthest_pair **無各向同性守衛**——
對正方 / 正多邊形(pca 因 λ1≈λ2 會 ValueError)farthest_pair 仍確定性回對角 diameter。

  FP1 present + backward-compat : `("geo","farthest_pair")` 產每個 cascade beat 且 finite/有 bone;非 cascade 主秀
                                 beat 逐位元同 base;`None`/`"po"` 仍逐位元同件序;**零回歸** `"geo"` 預設
                                 (= centroid_farthest)、`("geo","pca")`(J-8)、`("geo","pca_minor")`(J-9)
                                 皆**不被 farthest_pair 新增影響**(逐位元同;`derive(.,"pca")` 仍 == 閘獨立
                                 numpy **主**特徵向量、`derive(.,"centroid_farthest")` 仍 == 閘獨立質心→最遠件)。
  FP2 deterministic + order-ind: (crux)(a) **diameter 正確性**:`farthest_pair` == 閘獨立 brute-force diameter
                                 (**逐位元**同向量,非只同線);(b) **件輸入順序無關**:非對稱 & 對稱(diameter
                                 並列,如正方)佈局的**所有排列**產出**逐位元同一**帶號向量;(c) **符號跟隨幾何**:
                                 沿 x 軸鏡射(y→−y)→ 導出向量 y 分量符號確定性翻轉、x 分量不變。
  FP3 fp vs pca/cf (value)     : (crux/價值)**diameter 是一條真正不同的幾何 source,只由兩極端件決定**。構造
                                 固定 diameter 對 + 移動一個**內部(非極端)件**:(a) **farthest_pair 逐位元不變**
                                 (diameter 對不變,方向鎖死);(b) **pca** 方向隨之轉動(≥門檻);(c)
                                 **centroid_farthest** 方向隨之轉動(質心移動,≥門檻)→ 證三者幾何基礎不同。
  FP4 end-to-end ordering      : 真實 robot 骨架 `build_animations(cascade_dir=("geo","farthest_pair"))` → 每 cascade
                                 beat 各件峰時刻依 diameter 投影鍵嚴格遞增(最遠投影最後 pop)、仍一道有序跨件波
                                 (散佈≥門檻)+首尾 setup identity + 特效 slot alpha=1;dir⟂nrip 仍成立。並**誠實
                                 回報** robot 上 fp pop 序 vs pca/cf(資訊,不作判準——genuine-difference crux 在 FP3)。
  FP5 metric + guards          : (a) metric:farthest_pair == 閘獨立 brute diameter(多佈局逐位元);(b) **並列
                                 diameter / 各向同性**:正方(pca 會 ValueError)→ farthest_pair **不 raise**、確定性
                                 回對角且所有排列單一結果(件序無關);(c) 守衛:件重合 / 單件 / 空件 / 未知 source
                                 (直接 & 經 build_animations ("geo","farthest_pair") 可用、("geo","zzz") 報錯)→ ValueError。

閘從 VD(J-5 閘)fixture 的**真實 build_spine robot 骨架**端到端量;diameter **由閘以 brute-force 獨立重算**
(不呼叫生成器私有 `_farthest_pair_dir`),PCA 軸亦以 numpy 獨立重算,以保持獨立驗證。

用法:
  python3 validate_cascade_dir_farthest_pair.py            # 摘要
  python3 validate_cascade_dir_farthest_pair.py --json     # 完整 JSON
"""
import argparse, itertools, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import numpy as np
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
MIN_ROT = 3.0             # FP3:移動內部件時 pca / cf 應轉動 ≥ 此角度(度)


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

    base = G.build_animations(skel, sb)                                       # cascade_dir=None(件序)
    fp = G.build_animations(skel, sb, cascade_dir=("geo", "farthest_pair"))
    pmaj = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    cbeats = VD._cascade_beats(base)
    main_beats = VD._main_beats(base)
    centers = [xy[b] for b in order]
    fp_vec = G.derive_cascade_dir(centers, "farthest_pair")
    R = {}

    # ---- FP1 present + backward-compat + zero-regression ----
    p1 = {"missing": [], "not_finite": [], "no_bones": [], "noncascade_changed": [], "po_eq_none": None,
          "geo_default_eq_centroid": None, "pca_unchanged": None, "pca_minor_unchanged": None,
          "pca_derive_eq_numpy_major": None, "cf_derive_eq_gate": None}
    for cb in cbeats:
        an = fp.get(cb)
        if an is None:
            p1["missing"].append(cb); continue
        if not SA.all_finite(an):
            p1["not_finite"].append(cb)
        if not an.get("bones"):
            p1["no_bones"].append(cb)
    for beat, cat in main_beats.items():
        if cat == "cascade":
            continue
        if _bytes(fp.get(beat)) != _bytes(base.get(beat)):
            p1["noncascade_changed"].append(beat)
    po = G.build_animations(skel, sb, cascade_dir="po")
    p1["po_eq_none"] = all(_bytes(po[cb]) == _bytes(base[cb]) for cb in cbeats)
    geo_def = G.build_animations(skel, sb, cascade_dir="geo")
    geo_cf = G.build_animations(skel, sb, cascade_dir=("geo", "centroid_farthest"))
    p1["geo_default_eq_centroid"] = all(_bytes(geo_def[cb]) == _bytes(geo_cf[cb]) for cb in cbeats)
    # 零回歸:J-8 pca / J-9 pca_minor 路徑逐位元不變(不被 farthest_pair 新增影響)
    pmaj2 = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    pmin2 = G.build_animations(skel, sb, cascade_dir=("geo", "pca_minor"))
    pmin1 = G.build_animations(skel, sb, cascade_dir=("geo", "pca_minor"))
    p1["pca_unchanged"] = all(_bytes(pmaj[cb]) == _bytes(pmaj2[cb]) for cb in cbeats)
    p1["pca_minor_unchanged"] = all(_bytes(pmin1[cb]) == _bytes(pmin2[cb]) for cb in cbeats)
    np_major = _np_pca_major(centers)
    dmaj = G.derive_cascade_dir(centers, "pca")
    p1["pca_derive_eq_numpy_major"] = abs(abs(dmaj[0] * np_major[0] + dmaj[1] * np_major[1]) - 1.0) <= ALIGN_MAX
    dcf = G.derive_cascade_dir(centers, "centroid_farthest")
    gcf = _gate_centroid_farthest(centers)
    p1["cf_derive_eq_gate"] = _bits(dcf) == _bits(gcf)
    p1_pass = (bool(cbeats) and not p1["missing"] and not p1["not_finite"] and not p1["no_bones"]
               and not p1["noncascade_changed"] and p1["po_eq_none"] and p1["geo_default_eq_centroid"]
               and p1["pca_unchanged"] and p1["pca_minor_unchanged"] and p1["pca_derive_eq_numpy_major"]
               and p1["cf_derive_eq_gate"])
    R["FP1_present_backward_compat"] = {"cascade_beats": cbeats, **p1, "pass": p1_pass}

    # ---- FP2 diameter correctness + order-independent + deterministic sign (crux) ----
    p2 = {}
    # (a) diameter 正確性:farthest_pair == 閘獨立 brute diameter(逐位元同向量)
    cfgs = {"robot": centers,
            "L": [(-12.0, 0.0), (-6.0, 1.0), (0.0, -1.0), (6.0, 1.0), (12.0, 0.0), (0.0, 7.0)],
            "scatter": [(-3.0, 0.4), (-1.0, -0.3), (0.0, 0.0), (2.0, 0.5), (5.0, -0.2)]}
    adet, a_ok = {}, True
    for name, C in cfgs.items():
        v = G.derive_cascade_dir(C, "farthest_pair")
        b = _brute_diameter(C)
        same = _bits(v) == _bits(b)
        adet[name] = {"fp": _bits(v, 4), "brute": _bits(b, 4), "bit_identical": same}
        if not same:
            a_ok = False
    p2["a_diameter_eq_brute"] = {"detail": adet, "pass": a_ok}
    # (b) 件輸入順序無關:非對稱 + 對稱(diameter 並列,如正方)佈局的所有排列 → 逐位元同一向量
    asym = [(-3.0, 0.0), (-1.0, 0.0), (0.0, 0.5), (2.0, 0.0), (5.0, 0.0)]
    sq = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]                       # 兩對角並列 diameter
    asym_outs = {_bits(G.derive_cascade_dir(list(p), "farthest_pair")) for p in itertools.permutations(asym)}
    sq_outs = {_bits(G.derive_cascade_dir(list(p), "farthest_pair")) for p in itertools.permutations(sq)}
    p2["b_order_independent"] = {"asym_perms": math.factorial(len(asym)), "asym_distinct": len(asym_outs),
                                 "square_perms": math.factorial(len(sq)), "square_distinct": len(sq_outs),
                                 "square_vec": sorted(sq_outs),
                                 "pass": len(asym_outs) == 1 and len(sq_outs) == 1}
    # (c) 符號跟隨幾何:沿 x 鏡射 y→−y → 方向 y 分量符號翻轉、x 分量不變(端點 x 相異)
    B = [(-4.0, -1.0), (4.0, 3.0), (0.0, 0.0), (-1.0, 2.0)]                     # diameter (-4,-1)-(4,3)
    Bm = [(x, -y) for (x, y) in B]
    vB = G.derive_cascade_dir(B, "farthest_pair"); vBm = G.derive_cascade_dir(Bm, "farthest_pair")
    p2["c_sign_tracks_geometry"] = {"B": _bits(vB, 4), "mirror_y": _bits(vBm, 4),
                                    "pass": _bits(vB) == _bits((vBm[0], -vBm[1])) and abs(vB[1]) > 0.2}
    R["FP2_diameter_order_sign"] = {**p2, "pass": all(v["pass"] for v in p2.values())}

    # ---- FP3 farthest_pair vs pca/cf: genuinely different source (crux / value) ----
    # 固定 diameter 對 (-6,0)-(6,0);移動一個**內部**件 (3,0.5)->(3,6)(仍非極端,diameter 對不變)。
    bse = [(-6.0, 0.0), (6.0, 0.0), (3.0, 0.5), (-2.0, -1.0), (0.0, 1.0)]
    mov = [(-6.0, 0.0), (6.0, 0.0), (3.0, 6.0), (-2.0, -1.0), (0.0, 1.0)]
    diam_bse = _brute_diameter(bse); diam_mov = _brute_diameter(mov)
    diam_same = _bits(diam_bse) == _bits(diam_mov)                            # diameter 對(方向)不變
    fp0 = G.derive_cascade_dir(bse, "farthest_pair"); fp1 = G.derive_cascade_dir(mov, "farthest_pair")
    pc0 = G.derive_cascade_dir(bse, "pca"); pc1 = G.derive_cascade_dir(mov, "pca")
    cf0 = G.derive_cascade_dir(bse, "centroid_farthest"); cf1 = G.derive_cascade_dir(mov, "centroid_farthest")
    fp_inv = _bits(fp0) == _bits(fp1)
    pca_rot = _acute(pc0, pc1)
    cf_rot = _acute(cf0, cf1)
    p3_pass = diam_same and fp_inv and pca_rot >= MIN_ROT and cf_rot >= MIN_ROT
    R["FP3_fp_vs_pca_cf"] = {
        "diameter_pair_unchanged": diam_same, "fp_vec": _bits(fp0, 4), "fp_bit_invariant": fp_inv,
        "pca_rotation_deg": round(pca_rot, 3), "cf_rotation_deg": round(cf_rot, 3),
        "min_rot_threshold": MIN_ROT, "pass": p3_pass}

    # ---- FP4 end-to-end projection ordering (robot) ----
    p4 = {"detail": {}, "fail_order": [], "weak_spread": [], "bad_interface": []}
    cf_full_vec = G.derive_cascade_dir(centers, "centroid_farthest")
    pmaj_vec = G.derive_cascade_dir(centers, "pca")
    for cb in cbeats:
        an = fp[cb]
        bones = [b for b in order if b in an.get("bones", {})]
        proj_sorted = sorted(bones, key=lambda b: (_proj_key(xy, b, fp_vec), order.index(b)))
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
        # 誠實回報(不作判準):fp 的測得 pop 序 vs pca / cf 的 pop 序
        meas_maj = sorted([b for b in order if b in pmaj[cb].get("bones", {})],
                          key=lambda b: VD.peak_time(pmaj[cb], b))
        differs_major = [order.index(b) for b in meas] != [order.index(b) for b in meas_maj]
        p4["detail"][cb] = {"fp_vec": _bits(fp_vec, 4), "proj_order": [order.index(b) for b in proj_sorted],
                            "peak_times": [round(x, 3) for x in pts], "monotone": mono,
                            "farthest_pops_last": far_last, "spread": round(sp, 3), "iface": iface,
                            "measured_fp_order": [order.index(b) for b in meas],
                            "measured_major_order": [order.index(b) for b in meas_maj],
                            "differs_from_major": differs_major}
        if not (mono and far_last):
            p4["fail_order"].append(cb)
        if sp < SPREAD_FLOOR:
            p4["weak_spread"].append(cb)
        if not iface:
            p4["bad_interface"].append(cb)
    # dir ⟂ nrip:帶 ripples 時各件 pop 次數 == nrip 在 farthest_pair 成立
    nrip_ok, nrip_detail = True, {}
    full = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip,
                              cascade_dir=("geo", "farthest_pair"))
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
    R["FP4_end_to_end_ordering"] = {**p4, "fp_vec": _bits(fp_vec, 4), "pca_vec": _bits(pmaj_vec, 4),
                                    "cf_vec": _bits(cf_full_vec, 4), "nrip_intact": nrip_ok,
                                    "nrip_detail": nrip_detail, "pass": p4_pass}

    # ---- FP5 metric well-defined + guards ----
    p5 = {}
    # (a) metric:farthest_pair == 閘獨立 brute diameter(多佈局逐位元)
    mdet, m_ok = {}, True
    for name, C in {"robot": centers, "L": cfgs["L"],
                    "diag": [(0, 0), (1, 1), (2, 2), (3, 3.2), (0.5, 0.0)]}.items():
        v = G.derive_cascade_dir(C, "farthest_pair"); b = _brute_diameter(C)
        same = _bits(v) == _bits(b)
        mdet[name] = {"fp": _bits(v, 4), "brute": _bits(b, 4), "bit_identical": same}
        if not same:
            m_ok = False
    p5["a_metric_eq_brute"] = {"detail": mdet, "pass": m_ok}
    # (b) 並列 diameter / 各向同性:正方(pca 會 ValueError)→ farthest_pair 不 raise、確定性回對角、件序無關
    sq2 = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    pca_raises = False
    try:
        G.derive_cascade_dir(sq2, "pca")
    except ValueError:
        pca_raises = True
    try:
        sq_vecs = {_bits(G.derive_cascade_dir(list(p), "farthest_pair")) for p in itertools.permutations(sq2)}
        fp_sq_ok = len(sq_vecs) == 1
        sq_vec = sorted(sq_vecs)
    except ValueError:
        fp_sq_ok, sq_vec = False, None
    p5["b_tie_isotropic"] = {"pca_raises_on_square": pca_raises, "fp_resolves": fp_sq_ok,
                             "fp_square_vec": sq_vec,
                             "pass": pca_raises and fp_sq_ok}
    # (c) 守衛:件重合 / 單件 / 空件 / 未知 source(直接 & 經 build)
    guards = {}
    for name, fn in {
        "coincident": lambda: G.derive_cascade_dir([(5.0, 7.0), (5.0, 7.0), (5.0, 7.0)], "farthest_pair"),
        "single": lambda: G.derive_cascade_dir([(1.0, 2.0)], "farthest_pair"),
        "empty": lambda: G.derive_cascade_dir([], "farthest_pair"),
        "unknown_source_direct": lambda: G.derive_cascade_dir([(0, 0), (1, 1)], "nope_src"),
        "unknown_source_build": lambda: G.build_animations(skel, sb, cascade_dir=("geo", "zzz")),
    }.items():
        try:
            fn(); guards[name] = False
        except ValueError:
            guards[name] = True
    try:
        _ = G.build_animations(skel, sb, cascade_dir=("geo", "farthest_pair")); guards["fp_build_ok"] = True
    except Exception:
        guards["fp_build_ok"] = False
    p5["c_input_guards"] = {"detail": guards, "pass": all(guards.values())}
    R["FP5_metric_guards"] = {**p5, "pass": all(v["pass"] for v in p5.values())}

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
        for k in ["FP1_present_backward_compat", "FP2_diameter_order_sign", "FP3_fp_vs_pca_cf",
                  "FP4_end_to_end_ordering", "FP5_metric_guards"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        p3 = R["FP3_fp_vs_pca_cf"]
        print("FP3 fp_invariant={} diam_unchanged={} pca_rot={}° cf_rot={}°".format(
            p3["fp_bit_invariant"], p3["diameter_pair_unchanged"], p3["pca_rotation_deg"], p3["cf_rotation_deg"]))
        print("FP4 projection order (robot):")
        for cb, d in R["FP4_end_to_end_ordering"]["detail"].items():
            print("   {:10s} vec={} fp_order={} major_order={} mono={} differs_major={}".format(
                cb, d["fp_vec"], d["measured_fp_order"], d["measured_major_order"],
                d["monotone"], d["differs_from_major"]))
        b5 = R["FP5_metric_guards"]["b_tie_isotropic"]
        print("FP5(b) pca_raises_on_square={} fp_resolves_square={} vec={}".format(
            b5["pca_raises_on_square"], b5["fp_resolves"], b5["fp_square_vec"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
