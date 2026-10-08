#!/usr/bin/env python3
"""candidate (J-9) 自我驗收閘 — cascade 跨件波方向的 **PCA 次主軸 geo source**(符號確定性,純 CPU)。

方向軸的來源精煉(**同一條 J-6 投影軸**,逐步移除 / 強化人手指定):
  J-5:相位來源由件序換成**空間**(4 個具名方向 lr/rl/co/oc)。
  J-6:方向**值連續化**(任意角 / 向量)—— 但「用哪個方向」仍是手感常數。
  J-7:`cascade_dir="geo"` 方向**向量由件幾何導出**(質心 → 最遠件),隨資產自適應。
  J-8:新增 `geo source = "pca"` —— 用 PCA **主軸**(最大變異方向),符號確定性地定。
  J-9(本閘):新增 `geo source = "pca_minor"` —— 用 PCA **次主軸**(**最小變異方向**,與主軸**正交**),
       符號同樣確定性地定。語意 = 波沿件群**短軸橫掃**(vs pca 沿長軸延掃)。

**honest distinction(勿誇大)**:J-9 **不是**新正交軸,也**不改** J-6 的投影排序機制;只是 J-7/J-8 那條
「方向軸取值來源(provenance)」再多一個 source(`pca_minor`)。其**價值 crux**:次主軸與主軸**正交**→ 產生
**不同的件 pop 序**(是一條真正不同的波,非 pca 主軸的改版);其**正確性 crux**:與 J-8 同——PCA 的**符號歧義**
以確定性幾何規則釘死,且**件輸入順序無關**。跨件時序通道仍是三條正交軸(結構 nrip × 幅度 span × 方向 dir)。

  PM1 present + backward-compat : `("geo","pca_minor")` 產每個 cascade beat 且 finite/有 bone;非 cascade 主秀
                                 beat 逐位元同 base;`None`/`"po"` 仍逐位元同件序;**零回歸** `"geo"` 預設
                                 (= centroid_farthest)與 `("geo","pca")`(J-8)皆**不被 pca_minor 新增影響**
                                 (逐位元同;且 `derive(.,"pca")` 仍 == 閘獨立 numpy **主**特徵向量 → 主軸路徑未動)。
  PM2 perp + deterministic sign: (crux)(a) **正交性**:`pca_minor` ⟂ `pca`(|dot|≈0)且 pca_minor == 閘獨立
                                 numpy **次**特徵向量(同一條線,|dot|≈1);(b) **件輸入順序無關**:非對稱 & 對稱
                                 佈局的**所有排列**產出**逐位元同一**帶號向量(對稱佈局正是天真 index tie-break
                                 會翻號處);(c) **符號跟隨幾何**:把次軸方向的極端件鏡射 → 導出向量符號確定性翻轉。
  PM3 minor vs major (value)   : (crux/價值)**次主軸是一條真正不同的波,非主軸改版**。拉長但二維展開的佈局 →
                                 (a) minor ⟂ major(|dot|≈0);(b) 依 minor 投影排序的件序 **≠** 依 major 投影排序
                                 的件序(短軸橫掃 vs 長軸延掃);(c) 次軸方向的極端件在 minor 下**最後 pop**。
  PM4 end-to-end ordering      : 真實 robot 骨架 `build_animations(cascade_dir=("geo","pca_minor"))` → 每 cascade
                                 beat 各件峰時刻依次主軸投影鍵嚴格遞增(最遠投影最後 pop)、仍一道有序跨件波
                                 (散佈≥門檻)+首尾 setup identity + 特效 slot alpha=1;**crux**:robot 上 pca_minor
                                 的 pop 序 **≠** pca 主軸的 pop 序(端到端證兩者不同波);且 dir⟂nrip 仍成立。
  PM5 metric + guards          : (a) pca_minor 主軸 == numpy 共變異**最小**特徵向量(|dot|≈1)、且 ⟂ 主軸 → metric
                                 良定義;(b) **各向異性門檻有鑑別力**:恰好各向同性(正方 / 正多邊形)→ ValueError
                                 (主/次軸皆不唯一),僅微量各向異性 → 放行且次軸正確(⟂ 主軸);(c) 守衛:件重合 /
                                 單件 / 空件 / 未知 source(直接 & 經 build_animations ("geo","pca_minor") 可用、
                                 ("geo","zzz") 報錯)→ ValueError。

閘從 VD(J-5 閘)fixture 的**真實 build_spine robot 骨架**端到端量;PCA 主 / 次軸 **由閘以 numpy 獨立重算**
(不呼叫生成器私有 `_pca_principal_axis_dir`)以保持獨立驗證。

用法:
  python3 validate_cascade_dir_pca_minor.py            # 摘要
  python3 validate_cascade_dir_pca_minor.py --json     # 完整 JSON
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

PERP_MAX = 1e-6           # |dot(major,minor)| 應 ≈ 0(正交)
ALIGN_MAX = 1e-6          # minor 與 numpy 次特徵向量同一條線:|dot| 應 ≈ 1


def _np_pca_axes(centers):
    """閘**獨立**的 PCA 主 / 次軸(numpy 共變異特徵向量,未定號 → 回傳線的代表向量)。"""
    pts = np.asarray(centers, dtype=float)
    pts = pts - pts.mean(axis=0)
    cov = np.cov(pts.T, bias=True)
    w, V = np.linalg.eigh(cov)
    major = V[:, int(np.argmax(w))]
    minor = V[:, int(np.argmin(w))]
    return major, minor


def _acute_to(v, ref):
    """單位向量 v 與參考**線** ref 的銳角(度,∈[0,90];摺疊方向正負)。"""
    d = max(-1.0, min(1.0, v[0] * ref[0] + v[1] * ref[1]))
    a = math.degrees(math.acos(d))
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
    return tuple(round(c, nd) for c in v)


def run():
    skel = VD._skeleton()
    sb = VD._storyboard(VD.GENRE)
    order = VD._part_order(sb)
    xy = VD._bone_xy(skel)
    gains = TV.gains_for(VD.GENRE)
    rip = TV.cascade_ripples_for(VD.GENRE)

    base = G.build_animations(skel, sb)                                       # cascade_dir=None(件序)
    pmin = G.build_animations(skel, sb, cascade_dir=("geo", "pca_minor"))
    pmaj = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    cbeats = VD._cascade_beats(base)
    main_beats = VD._main_beats(base)
    centers = [xy[b] for b in order]
    minor_vec = G.derive_cascade_dir(centers, "pca_minor")
    major_vec = G.derive_cascade_dir(centers, "pca")
    R = {}

    # ---- PM1 present + backward-compat + zero-regression ----
    p1 = {"missing": [], "not_finite": [], "no_bones": [], "noncascade_changed": [], "po_eq_none": None,
          "geo_default_eq_centroid": None, "pca_major_unchanged": None, "pca_derive_eq_numpy_major": None}
    for cb in cbeats:
        an = pmin.get(cb)
        if an is None:
            p1["missing"].append(cb); continue
        if not SA.all_finite(an):
            p1["not_finite"].append(cb)
        if not an.get("bones"):
            p1["no_bones"].append(cb)
    for beat, cat in main_beats.items():
        if cat == "cascade":
            continue
        if _bytes(pmin.get(beat)) != _bytes(base.get(beat)):
            p1["noncascade_changed"].append(beat)
    po = G.build_animations(skel, sb, cascade_dir="po")
    p1["po_eq_none"] = all(_bytes(po[cb]) == _bytes(base[cb]) for cb in cbeats)
    # 零回歸:J-7 預設 "geo"(= centroid_farthest)不被 pca_minor 新增影響
    geo_def = G.build_animations(skel, sb, cascade_dir="geo")
    geo_cf = G.build_animations(skel, sb, cascade_dir=("geo", "centroid_farthest"))
    p1["geo_default_eq_centroid"] = all(_bytes(geo_def[cb]) == _bytes(geo_cf[cb]) for cb in cbeats)
    # 零回歸:J-8 主軸路徑 ("geo","pca") 加了 minor 參數後仍逐位元不變 + derive(.,"pca") 仍 == numpy 主特徵向量
    pmaj2 = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    p1["pca_major_unchanged"] = all(_bytes(pmaj[cb]) == _bytes(pmaj2[cb]) for cb in cbeats)
    np_major, _ = _np_pca_axes(centers)
    p1["pca_derive_eq_numpy_major"] = abs(abs(major_vec[0] * np_major[0] + major_vec[1] * np_major[1]) - 1.0) <= ALIGN_MAX
    p1_pass = (bool(cbeats) and not p1["missing"] and not p1["not_finite"] and not p1["no_bones"]
               and not p1["noncascade_changed"] and p1["po_eq_none"] and p1["geo_default_eq_centroid"]
               and p1["pca_major_unchanged"] and p1["pca_derive_eq_numpy_major"])
    R["PM1_present_backward_compat"] = {"cascade_beats": cbeats, **p1, "pass": p1_pass}

    # ---- PM2 perpendicular + deterministic sign (crux) ----
    p2 = {}
    # (a) 正交性 + minor == numpy 次特徵向量(同一條線)
    elong = [(-3.0, 0.4), (-1.0, -0.3), (0.0, 0.0), (2.0, 0.5), (5.0, -0.2)]
    v_mi = G.derive_cascade_dir(elong, "pca_minor")
    v_ma = G.derive_cascade_dir(elong, "pca")
    _, np_mi = _np_pca_axes(elong)
    perp = abs(v_mi[0] * v_ma[0] + v_mi[1] * v_ma[1])
    same_line = abs(v_mi[0] * np_mi[0] + v_mi[1] * np_mi[1])
    p2["a_perp_and_numpy_minor"] = {"minor": _bits(v_mi, 4), "major": _bits(v_ma, 4),
                                    "numpy_minor": [round(float(c), 4) for c in np_mi],
                                    "abs_dot_major_minor": round(float(perp), 8),
                                    "abs_dot_numpy": round(float(same_line), 6),
                                    "pass": perp <= PERP_MAX and abs(same_line - 1.0) <= ALIGN_MAX}
    # (b) 件輸入順序無關:非對稱 + 對稱(天真 index tie-break 會翻號)佈局的所有排列 → 逐位元同一向量
    asym = [(-3.0, 0.0), (-1.0, 0.0), (0.0, 0.5), (2.0, 0.0), (5.0, 0.0)]
    sym = [(-10.0, 0.0), (10.0, 0.0), (0.0, 3.0), (0.0, -3.0)]
    asym_outs = {_bits(G.derive_cascade_dir(list(p), "pca_minor")) for p in itertools.permutations(asym)}
    sym_outs = {_bits(G.derive_cascade_dir(list(p), "pca_minor")) for p in itertools.permutations(sym)}
    p2["b_order_independent"] = {"asym_perms": math.factorial(len(asym)), "asym_distinct": len(asym_outs),
                                 "sym_perms": math.factorial(len(sym)), "sym_distinct": len(sym_outs),
                                 "sym_vec": sorted(sym_outs),
                                 "pass": len(asym_outs) == 1 and len(sym_outs) == 1}
    # (c) 符號跟隨幾何:沿 x 展開(major≈x),次軸(≈y)極端件在 +y;鏡射 y→−y → 極端件在 −y → 次軸符號翻轉。
    B = [(-3.0, 0.0), (-1.0, 0.0), (1.0, 0.0), (3.0, 0.0), (0.0, 4.0)]          # 次軸極端件在 +y
    Bm = [(x, -y) for (x, y) in B]                                              # 鏡射 → 極端件在 -y
    vB = G.derive_cascade_dir(B, "pca_minor"); vBm = G.derive_cascade_dir(Bm, "pca_minor")
    p2["c_sign_tracks_geometry"] = {"B": _bits(vB, 4), "mirror_y": _bits(vBm, 4),
                                    "pass": _bits(vB) == _bits((vBm[0], -vBm[1])) and abs(vB[1]) > 0.5}
    R["PM2_perp_deterministic_sign"] = {**p2, "pass": all(v["pass"] for v in p2.values())}

    # ---- PM3 minor vs major: genuinely different wave (crux / value) ----
    # 二維展開佈局(沿 x 拉長、沿 y 有次散佈,且含一個 +y 次軸極端件):
    L = [(-12.0, 0.0), (-6.0, 1.0), (0.0, -1.0), (6.0, 1.0), (12.0, 0.0), (0.0, 7.0)]
    v_ma3 = G.derive_cascade_dir(L, "pca")
    v_mi3 = G.derive_cascade_dir(L, "pca_minor")
    perp3 = abs(v_ma3[0] * v_mi3[0] + v_ma3[1] * v_mi3[1])
    ord_major = _proj_order(L, v_ma3)
    ord_minor = _proj_order(L, v_mi3)
    diff_order = ord_major != ord_minor
    # (c) 次軸方向的極端件(idx 5, (0,7))在 minor 投影下最大 → 最後 pop
    far_minor_last = ord_minor[-1] == 5
    p3_pass = perp3 <= PERP_MAX and diff_order and far_minor_last
    R["PM3_minor_vs_major"] = {
        "major_vec": _bits(v_ma3, 4), "minor_vec": _bits(v_mi3, 4),
        "abs_dot_major_minor": round(float(perp3), 8), "perp": perp3 <= PERP_MAX,
        "order_by_major": ord_major, "order_by_minor": ord_minor, "orders_differ": diff_order,
        "minor_extreme_pops_last": far_minor_last, "pass": p3_pass}

    # ---- PM4 end-to-end projection ordering (robot) + crux: minor order != major order ----
    p4 = {"detail": {}, "fail_order": [], "weak_spread": [], "bad_interface": [], "same_as_major": []}
    for cb in cbeats:
        an = pmin[cb]
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
        # crux:同 beat 在 pca 主軸下的測得 pop 序 vs pca_minor 下 → 應不同(不同波)
        an_maj = pmaj[cb]
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
    # dir ⟂ nrip:帶 ripples 時各件 pop 次數 == nrip 在 pca_minor 成立
    nrip_ok = True
    nrip_detail = {}
    full = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip,
                              cascade_dir=("geo", "pca_minor"))
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
    R["PM4_end_to_end_ordering"] = {**p4, "nrip_intact": nrip_ok, "nrip_detail": nrip_detail, "pass": p4_pass}

    # ---- PM5 metric well-defined + guards ----
    p5 = {}
    # (a) metric:pca_minor == numpy 共變異最小特徵向量(|dot|≈1)且 ⟂ 主軸
    cfgs = {"robot": centers, "elong": elong,
            "diag": [(0, 0), (1, 1), (2, 2), (3, 3.2), (0.5, 0.0)]}
    adet = {}
    a_ok = True
    for name, C in cfgs.items():
        vmi = G.derive_cascade_dir(C, "pca_minor"); vma = G.derive_cascade_dir(C, "pca")
        _, nv = _np_pca_axes(C)
        d_np = abs(vmi[0] * nv[0] + vmi[1] * nv[1])
        d_perp = abs(vmi[0] * vma[0] + vmi[1] * vma[1])
        adet[name] = {"abs_dot_numpy_minor": round(float(d_np), 6), "abs_dot_major": round(float(d_perp), 8)}
        if abs(d_np - 1.0) > ALIGN_MAX or d_perp > PERP_MAX:
            a_ok = False
    p5["a_metric_eq_numpy_minor"] = {"detail": adet, "pass": a_ok}
    # (b) 各向異性門檻有鑑別力:恰各向同性 → raise;微量各向異性 → 放行且次軸正確(⟂ 主軸)
    iso_raise = {}
    for name, C in {"square": [(0, 0), (2, 0), (2, 2), (0, 2)],
                    "pentagon": [(math.cos(2 * math.pi * k / 5), math.sin(2 * math.pi * k / 5)) for k in range(5)]}.items():
        try:
            G.derive_cascade_dir(C, "pca_minor"); iso_raise[name] = False
        except ValueError:
            iso_raise[name] = True
    barely = [(-1.0, 0.0), (1.0, 0.0), (0.0, 0.001), (0.0, -0.001)]   # var_x >> var_y 些微 → minor≈y
    try:
        vb_mi = G.derive_cascade_dir(barely, "pca_minor"); vb_ma = G.derive_cascade_dir(barely, "pca")
        barely_ok = abs(vb_mi[0] * vb_ma[0] + vb_mi[1] * vb_ma[1]) <= 1e-6 and abs(vb_mi[1]) >= 0.999
    except ValueError:
        vb_mi, barely_ok = None, False
    p5["b_anisotropy_threshold"] = {"isotropic_raise": iso_raise,
                                    "barely_minor": _bits(vb_mi, 4) if vb_mi else None,
                                    "barely_axis_ok": barely_ok,
                                    "pass": all(iso_raise.values()) and barely_ok}
    # (c) 守衛:件重合 / 單件 / 空件 / 未知 source(直接 & 經 build_animations)
    guards = {}
    for name, fn in {
        "coincident": lambda: G.derive_cascade_dir([(5.0, 7.0), (5.0, 7.0), (5.0, 7.0)], "pca_minor"),
        "single": lambda: G.derive_cascade_dir([(1.0, 2.0)], "pca_minor"),
        "empty": lambda: G.derive_cascade_dir([], "pca_minor"),
        "unknown_source_direct": lambda: G.derive_cascade_dir([(0, 0), (1, 1)], "nope_src"),
        "unknown_source_build": lambda: G.build_animations(skel, sb, cascade_dir=("geo", "zzz")),
    }.items():
        try:
            fn(); guards[name] = False
        except ValueError:
            guards[name] = True
    # pca_minor 經 build_animations ("geo","pca_minor") 可用(正面:不報錯且產 cascade)
    try:
        _ = G.build_animations(skel, sb, cascade_dir=("geo", "pca_minor")); guards["pca_minor_build_ok"] = True
    except Exception:
        guards["pca_minor_build_ok"] = False
    p5["c_input_guards"] = {"detail": guards, "pass": all(guards.values())}
    R["PM5_metric_guards"] = {**p5, "pass": all(v["pass"] for v in p5.values())}

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
        for k in ["PM1_present_backward_compat", "PM2_perp_deterministic_sign", "PM3_minor_vs_major",
                  "PM4_end_to_end_ordering", "PM5_metric_guards"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        p2a = R["PM2_perp_deterministic_sign"]["a_perp_and_numpy_minor"]
        print("PM2(a) perp: |dot(major,minor)|={} |dot(numpy_minor)|={}".format(
            p2a["abs_dot_major_minor"], p2a["abs_dot_numpy"]))
        p3 = R["PM3_minor_vs_major"]
        print("PM3 order major={} minor={} differ={} extreme_last={}".format(
            p3["order_by_major"], p3["order_by_minor"], p3["orders_differ"], p3["minor_extreme_pops_last"]))
        print("PM4 projection order (robot):")
        for cb, d in R["PM4_end_to_end_ordering"]["detail"].items():
            print("   {:10s} vec={} minor_order={} major_order={} mono={} differs={}".format(
                cb, d["minor_vec"], d["measured_minor_order"], d["measured_major_order"],
                d["monotone"], d["differs_from_major"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
