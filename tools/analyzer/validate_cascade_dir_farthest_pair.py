#!/usr/bin/env python3
"""candidate (J-10) 自我驗收閘 — cascade 跨件波方向的 **farthest_pair geo source**(件群直徑軸,純 CPU)。

方向軸的來源精煉(**同一條 J-6 投影軸**,逐步移除 / 替換「用哪個方向」的手感指定):
  J-5:相位來源由件序換成**空間**(4 個具名方向 lr/rl/co/oc)。
  J-6:方向**值連續化**(任意角 / 向量)—— 但「用哪個方向」仍是手感常數。
  J-7:`cascade_dir="geo"` 方向**向量由件幾何導出**(質心 → 最遠件),隨資產自適應。
  J-8:新增 `geo source = "pca"` —— 用 PCA **主軸**(最大變異方向),符號確定性地定。
  J-9:新增 `geo source = "pca_minor"` —— 用 PCA **次主軸**(最小變異方向,與主軸正交)。
  J-10(本閘):新增 `geo source = "farthest_pair"` —— 件中心的**直徑軸**(互距最遠的兩件連線方向)。

**honest distinction(勿誇大)**:J-10 **不是**新正交軸,也**不改** J-6 的投影排序機制;只是 J-7/J-8/J-9 那條
「方向軸取值來源(provenance)」再多一個 source(`farthest_pair`)。其**價值 crux**:farthest_pair 的**資訊基礎與
既有三者皆不同** —— 只依**兩個互距最遠的極端件**,**與件質心無關**(≠ centroid_farthest 依質心→最遠件)、
**與內部件 / 全域二階矩無關**(≠ pca/pca_minor);故**移動內部件時方向不變**(直徑只由 2 極端件決定)。其
**正確性 crux**:件對無序 → 直徑只給一條線(± 歧義同 PCA),以**同一套**確定性規則(`_orient_axis`:沿軸投影
極端件 + 座標字典序 tie-break)定號,且**件輸入順序無關**。跨件時序通道仍三條正交軸(結構 nrip × 幅度 span × 方向 dir)。

  FP1 present + backward-compat : `("geo","farthest_pair")` 產每個 cascade beat 且 finite/有 bone;非 cascade 主秀
                                 beat 逐位元同 base;`None`/`"po"` 仍逐位元同件序;**零回歸** `"geo"` 預設
                                 (= centroid_farthest)與 `("geo","pca")`/`("geo","pca_minor")` 皆**不被新增影響**
                                 (逐位元同;且 `derive(.,"pca_minor")` 仍 == 閘獨立 numpy **次**特徵向量 → PCA 路徑未動)。
  FP2 diameter + sign (crux)   : (a) **直徑正確**:`farthest_pair` 軸 == 閘**獨立 brute-force** 互距最遠件對方向
                                 (|dot|≈1,同一條線);(b) **件輸入順序無關**:非對稱 & 對稱(正方,兩對角線並列最遠
                                 → 需 tie-break)佈局的**所有排列**產出**逐位元同一**帶號向量;(c) **符號跟隨幾何**:
                                 把傾斜直徑沿 y 鏡射 → 導出向量 y 分量符號確定性翻轉。
  FP3 different source (crux)   : (crux/價值)**farthest_pair 是一條資訊基礎不同的 source,只依 2 極端件**。單一佈局
                                 (水平直徑 + 一個遠離質心的 +y 件 + 內部件)→ (a) farthest_pair ⟂ centroid_farthest
                                 (|dot|≈0,不同線);(b) **移動非極端的內部件** → farthest_pair **逐位元不變**,而
                                 centroid_farthest(質心移動)**與** pca(二階矩改變)**兩者皆改變** → 證 farthest_pair
                                 的資訊基礎(2 極端件)與 cf(質心單點)、pca(全域散佈)皆不同。
  FP4 end-to-end ordering      : 真實 robot 骨架 `build_animations(cascade_dir=("geo","farthest_pair"))` → 每 cascade
                                 beat 各件峰時刻依直徑投影鍵嚴格遞增(最遠投影最後 pop)、仍一道有序跨件波
                                 (散佈≥門檻)+首尾 setup identity + 特效 slot alpha=1;**crux**:robot 上 farthest_pair
                                 的 pop 序 **≠** pca 主軸的 pop 序(端到端證兩者不同波);且 dir⟂nrip 仍成立。
  FP5 metric + guards          : (a) farthest_pair == 閘獨立 brute-force 直徑(|dot|≈1)3 佈局 → metric 良定義;
                                 (b) **行為差異 crux**:恰各向同性(正方 / 正五邊形)→ farthest_pair **成功**
                                 (確定性選一條對角線,件序無關,因直徑無各向同性退化)而 **pca ValueError**(主軸不唯一)
                                 → 兩 source 在對稱佈局行為不同;(c) 守衛:件重合 / **單件(需 ≥2)** / 空件 / 未知 source
                                 (直接 & 經 build_animations ("geo","farthest_pair") 可用、("geo","zzz") 報錯)→ ValueError。

閘從 VD(J-5 閘)fixture 的**真實 build_spine robot 骨架**端到端量;直徑件對 **由閘以 O(n²) brute-force 獨立重算**
(不呼叫生成器私有 `_farthest_pair_axis_dir`)以保持獨立驗證。

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

ALIGN_MAX = 1e-6          # farthest_pair 與 brute-force 直徑同一條線:|dot| 應 ≈ 1
PERP_MAX = 1e-6           # farthest_pair ⟂ centroid_farthest(本閘 FP3 構造佈局):|dot| 應 ≈ 0
LINE_EPS = 1e-4           # 判「線改變了」:|dot| < 1 − LINE_EPS 視為方向改變


def _bf_diameter_dir(centers):
    """閘**獨立**的直徑方向:O(n²) brute-force 互距最遠件對,回傳**未定號**線的代表單位向量。"""
    n = len(centers)
    best_d2, bi, bj = -1.0, 0, 1
    for i in range(n):
        for j in range(i + 1, n):
            d2 = (centers[i][0] - centers[j][0]) ** 2 + (centers[i][1] - centers[j][1]) ** 2
            if d2 > best_d2:
                best_d2, bi, bj = d2, i, j
    dx, dy = centers[bj][0] - centers[bi][0], centers[bj][1] - centers[bi][1]
    L = math.hypot(dx, dy)
    return (dx / L, dy / L)


def _np_pca_axes(centers):
    """閘**獨立**的 PCA 主 / 次軸(numpy 共變異特徵向量,未定號 → 回傳線的代表向量)。"""
    pts = np.asarray(centers, dtype=float)
    pts = pts - pts.mean(axis=0)
    cov = np.cov(pts.T, bias=True)
    w, V = np.linalg.eigh(cov)
    return V[:, int(np.argmax(w))], V[:, int(np.argmin(w))]


def _absdot(a, b):
    return abs(a[0] * b[0] + a[1] * b[1])


def _proj_key(xy, bone, vec):
    x, y = xy[bone]
    return x * vec[0] + y * vec[1]


def _proj_order(centers, vec):
    return sorted(range(len(centers)),
                  key=lambda i: (centers[i][0] * vec[0] + centers[i][1] * vec[1], i))


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

    base = G.build_animations(skel, sb)                                          # cascade_dir=None(件序)
    fp = G.build_animations(skel, sb, cascade_dir=("geo", "farthest_pair"))
    pmaj = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    cbeats = VD._cascade_beats(base)
    main_beats = VD._main_beats(base)
    centers = [xy[b] for b in order]
    fp_vec = G.derive_cascade_dir(centers, "farthest_pair")
    major_vec = G.derive_cascade_dir(centers, "pca")
    R = {}

    # ---- FP1 present + backward-compat + zero-regression ----
    p1 = {"missing": [], "not_finite": [], "no_bones": [], "noncascade_changed": [], "po_eq_none": None,
          "geo_default_eq_centroid": None, "pca_unchanged": None, "pca_minor_unchanged": None,
          "pca_minor_derive_eq_numpy": None}
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
    # 零回歸:J-7 預設 "geo"(= centroid_farthest)不被 farthest_pair 新增影響
    geo_def = G.build_animations(skel, sb, cascade_dir="geo")
    geo_cf = G.build_animations(skel, sb, cascade_dir=("geo", "centroid_farthest"))
    p1["geo_default_eq_centroid"] = all(_bytes(geo_def[cb]) == _bytes(geo_cf[cb]) for cb in cbeats)
    # 零回歸:J-8 主軸 / J-9 次主軸路徑逐位元不變 + derive(.,"pca_minor") 仍 == numpy 次特徵向量
    pmaj2 = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    pmin2 = G.build_animations(skel, sb, cascade_dir=("geo", "pca_minor"))
    pmin_base = G.build_animations(skel, sb, cascade_dir=("geo", "pca_minor"))
    p1["pca_unchanged"] = all(_bytes(pmaj[cb]) == _bytes(pmaj2[cb]) for cb in cbeats)
    p1["pca_minor_unchanged"] = all(_bytes(pmin2[cb]) == _bytes(pmin_base[cb]) for cb in cbeats)
    _, np_minor = _np_pca_axes(centers)
    minor_vec = G.derive_cascade_dir(centers, "pca_minor")
    p1["pca_minor_derive_eq_numpy"] = abs(_absdot(minor_vec, np_minor) - 1.0) <= ALIGN_MAX
    p1_pass = (bool(cbeats) and not p1["missing"] and not p1["not_finite"] and not p1["no_bones"]
               and not p1["noncascade_changed"] and p1["po_eq_none"] and p1["geo_default_eq_centroid"]
               and p1["pca_unchanged"] and p1["pca_minor_unchanged"] and p1["pca_minor_derive_eq_numpy"])
    R["FP1_present_backward_compat"] = {"cascade_beats": cbeats, **p1, "pass": p1_pass}

    # ---- FP2 diameter correctness + deterministic sign (crux) ----
    p2 = {}
    # (a) 直徑正確:farthest_pair == 閘獨立 brute-force 直徑(同一條線)
    diam = [(-5.0, 0.0), (5.0, 0.0), (0.0, 4.0), (1.0, -1.0)]
    v_fp = G.derive_cascade_dir(diam, "farthest_pair")
    v_bf = _bf_diameter_dir(diam)
    same_line = _absdot(v_fp, v_bf)
    p2["a_eq_brute_force"] = {"fp": _bits(v_fp, 4), "brute_force": _bits(v_bf, 4),
                              "abs_dot": round(float(same_line), 8),
                              "pass": abs(same_line - 1.0) <= ALIGN_MAX}
    # (b) 件輸入順序無關:非對稱 + 對稱(正方,兩對角線並列最遠 → tie-break)佈局所有排列 → 逐位元同一向量
    asym = [(-3.0, 0.0), (-1.0, 0.3), (0.0, 0.0), (2.0, -0.2), (5.0, 0.1)]
    sq = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
    asym_outs = {_bits(G.derive_cascade_dir(list(p), "farthest_pair")) for p in itertools.permutations(asym)}
    sq_outs = {_bits(G.derive_cascade_dir(list(p), "farthest_pair")) for p in itertools.permutations(sq)}
    p2["b_order_independent"] = {"asym_perms": math.factorial(len(asym)), "asym_distinct": len(asym_outs),
                                 "sq_perms": math.factorial(len(sq)), "sq_distinct": len(sq_outs),
                                 "sq_vec": sorted(sq_outs),
                                 "pass": len(asym_outs) == 1 and len(sq_outs) == 1}
    # (c) 符號跟隨幾何:傾斜唯一直徑(-4,-3)-(4,3),沿 y 鏡射 → y 分量符號確定性翻轉。
    B = [(-4.0, -3.0), (4.0, 3.0), (0.0, 0.0), (1.0, -1.0)]
    Bm = [(x, -y) for (x, y) in B]
    vB = G.derive_cascade_dir(B, "farthest_pair"); vBm = G.derive_cascade_dir(Bm, "farthest_pair")
    p2["c_sign_tracks_geometry"] = {"B": _bits(vB, 4), "mirror_y": _bits(vBm, 4),
                                    "pass": _bits(vB) == _bits((vBm[0], -vBm[1])) and abs(vB[1]) > 0.3}
    R["FP2_diameter_sign"] = {**p2, "pass": all(v["pass"] for v in p2.values())}

    # ---- FP3 different source: only depends on 2 extreme parts (crux / value) ----
    # 水平唯一直徑 (-10,0)-(11,0);遠離質心的 +y 件 (0,16) → centroid_farthest 轉向 y;加 2 個內部件。
    L0 = [(-10.0, 0.0), (11.0, 0.0), (0.0, 16.0), (1.0, 1.0), (-2.0, -1.5)]
    fp0 = G.derive_cascade_dir(L0, "farthest_pair")
    cf0 = G.derive_cascade_dir(L0, "centroid_farthest")
    pc0 = G.derive_cascade_dir(L0, "pca")
    perp_cf = _absdot(fp0, cf0)                               # farthest_pair ⟂ centroid_farthest
    # 移動兩個**非極端內部件**(idx 3,4)——不動 4 個端點件(idx 0,1,2 不變,直徑/極端件不變)
    Lm = list(L0); Lm[3] = (4.0, 3.0); Lm[4] = (-3.0, 2.0)
    fp1 = G.derive_cascade_dir(Lm, "farthest_pair")
    cf1 = G.derive_cascade_dir(Lm, "centroid_farthest")
    pc1 = G.derive_cascade_dir(Lm, "pca")
    fp_invariant = _bits(fp0) == _bits(fp1)                   # farthest_pair 逐位元不變
    cf_changed = _absdot(cf0, cf1) < 1.0 - LINE_EPS           # centroid_farthest 方向改變(質心移動)
    pc_changed = _absdot(pc0, pc1) < 1.0 - LINE_EPS           # pca 方向改變(二階矩改變)
    p3_pass = (perp_cf <= PERP_MAX and fp_invariant and cf_changed and pc_changed)
    R["FP3_different_source"] = {
        "fp0": _bits(fp0, 4), "cf0": _bits(cf0, 4), "pc0": _bits(pc0, 4),
        "abs_dot_fp_cf": round(float(perp_cf), 8), "perp_fp_cf": perp_cf <= PERP_MAX,
        "fp1": _bits(fp1, 4), "cf1": _bits(cf1, 4), "pc1": _bits(pc1, 4),
        "fp_interior_invariant": fp_invariant,
        "cf_abs_dot_after_move": round(float(_absdot(cf0, cf1)), 6), "cf_changed": cf_changed,
        "pc_abs_dot_after_move": round(float(_absdot(pc0, pc1)), 6), "pc_changed": pc_changed,
        "pass": p3_pass}

    # ---- FP4 end-to-end projection ordering (robot) + crux: fp order != pca order ----
    p4 = {"detail": {}, "fail_order": [], "weak_spread": [], "bad_interface": [], "same_as_pca": []}
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
        # crux:同 beat 在 pca 主軸下的測得 pop 序 vs farthest_pair 下 → 應不同(不同波)
        an_maj = pmaj[cb]
        bones_maj = [b for b in order if b in an_maj.get("bones", {})]
        meas_maj = sorted(bones_maj, key=lambda b: VD.peak_time(an_maj, b))
        differs = [order.index(b) for b in meas] != [order.index(b) for b in meas_maj]
        p4["detail"][cb] = {"fp_vec": _bits(fp_vec, 4), "proj_order": [order.index(b) for b in proj_sorted],
                            "peak_times": [round(x, 3) for x in pts], "monotone": mono,
                            "farthest_pops_last": far_last, "spread": round(sp, 3), "iface": iface,
                            "measured_fp_order": [order.index(b) for b in meas],
                            "measured_pca_order": [order.index(b) for b in meas_maj],
                            "differs_from_pca": differs}
        if not (mono and far_last):
            p4["fail_order"].append(cb)
        if sp < SPREAD_FLOOR:
            p4["weak_spread"].append(cb)
        if not iface:
            p4["bad_interface"].append(cb)
        if not differs:
            p4["same_as_pca"].append(cb)
    # dir ⟂ nrip:帶 ripples 時各件 pop 次數 == nrip 在 farthest_pair 成立
    nrip_ok = True
    nrip_detail = {}
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
               and not p4["bad_interface"] and not p4["same_as_pca"] and nrip_ok)
    R["FP4_end_to_end_ordering"] = {**p4, "nrip_intact": nrip_ok, "nrip_detail": nrip_detail, "pass": p4_pass}

    # ---- FP5 metric well-defined + guards ----
    p5 = {}
    # (a) metric:farthest_pair == 閘獨立 brute-force 直徑(同一條線)3 佈局
    cfgs = {"robot": centers, "tri": [(-5.0, 0.0), (5.0, 0.0), (0.0, 4.0)],
            "diag": [(0.0, 0.0), (1.0, 1.0), (2.0, 2.0), (3.0, 3.2), (0.5, 0.0)]}
    adet = {}
    a_ok = True
    for name, C in cfgs.items():
        v = G.derive_cascade_dir(C, "farthest_pair")
        bf = _bf_diameter_dir(C)
        d = _absdot(v, bf)
        adet[name] = {"abs_dot_bf": round(float(d), 8)}
        if abs(d - 1.0) > ALIGN_MAX:
            a_ok = False
    p5["a_metric_eq_brute_force"] = {"detail": adet, "pass": a_ok}
    # (b) 行為差異 crux:恰各向同性(正方 / 正五邊形)→ farthest_pair 成功、pca ValueError
    iso = {}
    iso_ok = True
    for name, C in {"square": [(0, 0), (2, 0), (2, 2), (0, 2)],
                    "pentagon": [(math.cos(2 * math.pi * k / 5), math.sin(2 * math.pi * k / 5)) for k in range(5)]}.items():
        try:
            vfp = G.derive_cascade_dir(C, "farthest_pair"); fp_ok = True
        except ValueError:
            vfp, fp_ok = None, False
        try:
            G.derive_cascade_dir(C, "pca"); pca_raise = False
        except ValueError:
            pca_raise = True
        iso[name] = {"farthest_pair": _bits(vfp, 4) if vfp else None, "fp_ok": fp_ok, "pca_raises": pca_raise}
        if not (fp_ok and pca_raise):
            iso_ok = False
    p5["b_isotropy_behavior_differs"] = {"detail": iso, "pass": iso_ok}
    # (c) 守衛:件重合 / 單件(需 ≥2)/ 空件 / 未知 source(直接 & 經 build_animations)
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
        _ = G.build_animations(skel, sb, cascade_dir=("geo", "farthest_pair")); guards["farthest_pair_build_ok"] = True
    except Exception:
        guards["farthest_pair_build_ok"] = False
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
        for k in ["FP1_present_backward_compat", "FP2_diameter_sign", "FP3_different_source",
                  "FP4_end_to_end_ordering", "FP5_metric_guards"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        p2a = R["FP2_diameter_sign"]["a_eq_brute_force"]
        print("FP2(a) fp={} brute_force={} |dot|={}".format(p2a["fp"], p2a["brute_force"], p2a["abs_dot"]))
        p3 = R["FP3_different_source"]
        print("FP3 fp0={} cf0={} |dot(fp,cf)|={} fp_interior_invariant={} cf_changed={} pc_changed={}".format(
            p3["fp0"], p3["cf0"], p3["abs_dot_fp_cf"], p3["fp_interior_invariant"],
            p3["cf_changed"], p3["pc_changed"]))
        print("FP4 projection order (robot):")
        for cb, d in R["FP4_end_to_end_ordering"]["detail"].items():
            print("   {:10s} vec={} fp_order={} pca_order={} mono={} differs={}".format(
                cb, d["fp_vec"], d["measured_fp_order"], d["measured_pca_order"],
                d["monotone"], d["differs_from_pca"]))
        p5b = R["FP5_metric_guards"]["b_isotropy_behavior_differs"]["detail"]
        print("FP5(b) isotropy: " + "  ".join(
            "{}:fp_ok={}/pca_raises={}".format(n, v["fp_ok"], v["pca_raises"]) for n, v in p5b.items()))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
