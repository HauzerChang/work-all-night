#!/usr/bin/env python3
"""candidate (J-8) 自我驗收閘 — cascade 跨件波方向的 **PCA 主軸 geo source**(符號確定性,純 CPU)。

方向軸的來源精煉(**同一條 J-6 投影軸**,逐步移除 / 強化人手指定):
  J-5:相位來源由件序換成**空間**(4 個具名方向 lr/rl/co/oc)。
  J-6:方向**值連續化**(任意角 / 向量)—— 但「用哪個方向」仍是手感常數。
  J-7:`cascade_dir="geo"` 方向**向量由件幾何導出**(質心 → 最遠件),隨資產自適應。
       **刻意避開 PCA**:因為 PCA 主軸只給一條**線**,方向正負(±v)皆合法特徵向量 → 符號歧義。
  J-8(本閘):新增 `geo source = "pca"` —— 用 PCA 主軸(**最大變異方向**,反映整體散佈),並以**幾何規則**
       **確定性地定號**,正面解掉 J-7 迴避的 ±歧義。較 `centroid_farthest` 穩健:方向取自整體散佈軸而非
       單一最遠件 → **波序跟隨件群的整體延展,不被單一離軸件主導**(見 PA3)。

**honest distinction(勿誇大)**:J-8 **不是**新正交軸,也**不改** J-6 的投影排序機制;只是 J-7 那條
「方向軸取值來源(provenance)」多一個 source(`pca`),其 crux 是把 PCA 的**符號歧義**以確定性幾何規則釘死。
跨件時序通道仍是三條正交軸(結構 nrip × 幅度 span × 方向 dir)。

  PA1 present + backward-compat : `("geo","pca")` 產每個 cascade beat 且 finite/有 bone;非 cascade 主秀 beat
                                 逐位元同 base;`None`/`"po"` 仍逐位元同件序;**零回歸** `"geo"` 預設
                                 (= centroid_farthest)不被 pca 新增影響(逐位元同 `("geo","centroid_farthest")`,
                                 且 `derive_cascade_dir(.,"centroid_farthest")` == 閘獨立質心→最遠件)。
  PA2 deterministic sign       : (crux)PCA ±歧義被確定性解掉 —— (a) 拉長件群 → 主軸 == 閘獨立 numpy 主特徵向量
                                 (同一條線,|dot|≈1);(b) **件輸入順序無關**:非對稱 & 對稱佈局的**所有排列**
                                 產出**逐位元同一**帶號向量(對稱佈局正是天真 index tie-break 會翻號處);
                                 (c) **符號跟隨幾何**:把佈局沿主軸鏡射 → 導出向量符號確定性翻轉。
  PA3 pca vs centroid_farthest : (crux/價值)**pca 看整體散佈,cf 只看單一最遠件**。(a) 最遠件**離主散佈軸**的
                                 佈局 → `pca` 沿**整體延展**(與 x 軸夾角小)、`cf` **朝單一最遠件**甩(夾角大),兩者
                                 **不同線**;(b) 移動一個**非最遠**內部件 → `cf` 方向**嚴格不變**(只依質心→最遠件)、
                                 `pca` 主軸**隨之改變** → 證兩者資訊基礎不同(全域二階矩 vs 單點)。
  PA4 end-to-end ordering      : 真實 robot 骨架 `build_animations(cascade_dir=("geo","pca"))` → 每 cascade beat
                                 各件峰時刻依**閘獨立重算**的 pca 投影鍵嚴格遞增(最遠投影最後 pop)、仍一道有序
                                 跨件波(散佈≥門檻)+首尾 setup identity + 特效 slot alpha=1;且 dir⟂nrip 仍成立。
  PA5 metric + guards          : (a) pca 主軸 == numpy 共變異主特徵向量(|dot|≈1)→ metric 良定義;(b) **各向異性
                                 門檻有鑑別力**:恰好各向同性(正方 / 正多邊形)→ ValueError,僅微量各向異性 →
                                 放行且軸正確;(c) 守衛:件重合 / 單件 / 空件 / 未知 source(直接 & 經
                                 build_animations ("geo","pca") 可用、("geo","zzz") 報錯)→ ValueError。

閘從 VD(J-5 閘)fixture 的**真實 build_spine robot 骨架**端到端量;PCA 主軸 / 投影序 **由閘以 numpy 獨立重算**
(不呼叫生成器私有 `_pca_principal_axis_dir`)以保持獨立驗證。

用法:
  python3 validate_cascade_dir_pca.py            # 摘要
  python3 validate_cascade_dir_pca.py --json     # 完整 JSON
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

# PA3 門檻:pca 與主散佈軸(x)夾角上界 / centroid_farthest 夾角下界(由探針量得 pca≈0°、cf≈90°)。
PCA_ALIGN_MAX = 15.0      # pca 應貼齊主散佈軸
CF_SWING_MIN = 40.0       # centroid_farthest 應被離群件甩離主軸


def _np_pca_axis(centers):
    """閘**獨立**的 PCA 主軸(numpy 共變異最大特徵值之特徵向量,未定號 → 回傳一條線的代表向量)。"""
    pts = np.asarray(centers, dtype=float)
    pts = pts - pts.mean(axis=0)
    cov = np.cov(pts.T, bias=True)
    w, V = np.linalg.eigh(cov)
    return V[:, int(np.argmax(w))]


def _acute_to_x(v):
    """單位向量與 x 軸**線**的銳角(度,∈[0,90];摺疊方向正負)。"""
    a = abs(math.degrees(math.atan2(v[1], v[0])))
    return min(a, 180.0 - a)


def _line_angle(v):
    return math.degrees(math.atan2(v[1], v[0])) % 180.0


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

    base = G.build_animations(skel, sb)                                   # cascade_dir=None(件序)
    pca = G.build_animations(skel, sb, cascade_dir=("geo", "pca"))
    cbeats = VD._cascade_beats(base)
    main_beats = VD._main_beats(base)
    centers = [xy[b] for b in order]
    pca_vec = G.derive_cascade_dir(centers, "pca")
    R = {}

    # ---- PA1 present + backward-compat ----
    p1 = {"missing": [], "not_finite": [], "no_bones": [], "noncascade_changed": [], "po_eq_none": None,
          "geo_default_eq_centroid": None, "cf_derive_eq_independent": None}
    for cb in cbeats:
        an = pca.get(cb)
        if an is None:
            p1["missing"].append(cb); continue
        if not SA.all_finite(an):
            p1["not_finite"].append(cb)
        if not an.get("bones"):
            p1["no_bones"].append(cb)
    for beat, cat in main_beats.items():
        if cat == "cascade":
            continue
        if _bytes(pca.get(beat)) != _bytes(base.get(beat)):
            p1["noncascade_changed"].append(beat)
    po = G.build_animations(skel, sb, cascade_dir="po")
    p1["po_eq_none"] = all(_bytes(po[cb]) == _bytes(base[cb]) for cb in cbeats)
    # 零回歸:J-7 預設 "geo" 不被 pca 新增影響(逐位元同 ("geo","centroid_farthest"))
    geo_def = G.build_animations(skel, sb, cascade_dir="geo")
    geo_cf = G.build_animations(skel, sb, cascade_dir=("geo", "centroid_farthest"))
    p1["geo_default_eq_centroid"] = all(_bytes(geo_def[cb]) == _bytes(geo_cf[cb]) for cb in cbeats)
    # centroid_farthest 導出不變:== 閘獨立質心→最遠件
    cf_vec = G.derive_cascade_dir(centers, "centroid_farthest")
    mx = sum(c[0] for c in centers) / len(centers); my = sum(c[1] for c in centers) / len(centers)
    fi = max(range(len(centers)), key=lambda i: (centers[i][0] - mx) ** 2 + (centers[i][1] - my) ** 2)
    dxx, dyy = centers[fi][0] - mx, centers[fi][1] - my
    Lc = math.hypot(dxx, dyy)
    p1["cf_derive_eq_independent"] = _bits(cf_vec) == _bits((dxx / Lc, dyy / Lc))
    p1_pass = (bool(cbeats) and not p1["missing"] and not p1["not_finite"] and not p1["no_bones"]
               and not p1["noncascade_changed"] and p1["po_eq_none"] and p1["geo_default_eq_centroid"]
               and p1["cf_derive_eq_independent"])
    R["PA1_present_backward_compat"] = {"cascade_beats": cbeats, **p1, "pass": p1_pass}

    # ---- PA2 deterministic sign (crux) ----
    p2 = {}
    # (a) 主軸 == 閘獨立 numpy 主特徵向量(同一條線)
    elong = [(-3.0, 0.0), (-1.0, 0.0), (0.0, 0.0), (2.0, 0.0), (5.0, 0.3)]
    v_el = G.derive_cascade_dir(elong, "pca")
    np_el = _np_pca_axis(elong)
    same_line = abs(v_el[0] * np_el[0] + v_el[1] * np_el[1])
    p2["a_axis_eq_numpy"] = {"pca": _bits(v_el, 4), "numpy": [round(float(c), 4) for c in np_el],
                             "abs_dot": round(float(same_line), 6), "pass": abs(same_line - 1.0) <= 1e-6}
    # (b) 件輸入順序無關:非對稱 + 對稱(天真 index tie-break 會翻號)佈局的所有排列 → 逐位元同一向量
    asym = [(-3.0, 0.0), (-1.0, 0.0), (0.0, 0.5), (2.0, 0.0), (5.0, 0.0)]
    sym = [(-10.0, 0.0), (10.0, 0.0), (0.0, 3.0), (0.0, -3.0)]
    asym_outs = {_bits(G.derive_cascade_dir(list(p), "pca")) for p in itertools.permutations(asym)}
    sym_outs = {_bits(G.derive_cascade_dir(list(p), "pca")) for p in itertools.permutations(sym)}
    p2["b_order_independent"] = {"asym_perms": math.factorial(len(asym)), "asym_distinct": len(asym_outs),
                                 "sym_perms": math.factorial(len(sym)), "sym_distinct": len(sym_outs),
                                 "sym_vec": sorted(sym_outs),
                                 "pass": len(asym_outs) == 1 and len(sym_outs) == 1}
    # (c) 符號跟隨幾何:沿主軸鏡射 → 符號確定性翻轉
    A = [(-2.0, 0.0), (0.0, 0.0), (2.0, 0.0), (9.0, 0.0)]           # 極端件在 +x
    Am = [(x * -1.0, y) for (x, y) in A]                            # 鏡射 → 極端件在 -x
    vA = G.derive_cascade_dir(A, "pca"); vAm = G.derive_cascade_dir(Am, "pca")
    p2["c_sign_tracks_geometry"] = {"A": _bits(vA, 4), "mirror": _bits(vAm, 4),
                                    "pass": _bits(vA) == _bits((-vAm[0], -vAm[1]))
                                    and abs(vA[0]) > 0.5}   # 翻號 + 非退化
    R["PA2_deterministic_sign"] = {**p2, "pass": all(v["pass"] for v in p2.values())}

    # ---- PA3 pca(整體散佈)vs centroid_farthest(單一最遠件)(crux / value) ----
    # 主散佈沿 x(6 件)+ 離軸最遠件(outlier 為質心最遠件):
    Rb = [(-15.0, 0.0), (-10.0, 0.0), (-5.0, 0.0), (5.0, 0.0), (10.0, 0.0), (15.0, 0.0), (0.0, 22.0)]

    def _far_idx(C):
        n = len(C); mx = sum(c[0] for c in C) / n; my = sum(c[1] for c in C) / n
        return max(range(n), key=lambda i: (C[i][0] - mx) ** 2 + (C[i][1] - my) ** 2)

    # (a) 最遠件離主散佈軸 → pca 貼主散佈軸(與 x 夾角小),cf 朝單一最遠件(夾角大),兩者不同線。
    far_is_outlier = _far_idx(Rb) == 6
    vpca = G.derive_cascade_dir(Rb, "pca"); vcf = G.derive_cascade_dir(Rb, "centroid_farthest")
    pca_al = _acute_to_x(vpca); cf_sw = _acute_to_x(vcf)
    diff_line = abs(vpca[0] * vcf[0] + vpca[1] * vcf[1])
    a_pass = far_is_outlier and pca_al <= PCA_ALIGN_MAX and cf_sw >= CF_SWING_MIN and diff_line < 0.9
    # (b) **cf 只看單一最遠件,pca 整合所有件**:移動一個**非最遠**內部件 → cf 方向不變(最遠件不變、
    #     質心 x 對稱不動 → 嚴格不變),pca 主軸隨之改變。證兩者資訊基礎不同(全域二階矩 vs 單點)。
    Rb2 = Rb[:2] + [(-5.0, 8.0)] + Rb[3:]            # idx2 (-5,0)->(-5,8);idx6 outlier 不變
    far_same = (_far_idx(Rb) == _far_idx(Rb2) == 6)
    p1v, p2v = G.derive_cascade_dir(Rb, "pca"), G.derive_cascade_dir(Rb2, "pca")
    c1v, c2v = G.derive_cascade_dir(Rb, "centroid_farthest"), G.derive_cascade_dir(Rb2, "centroid_farthest")

    def _line_shift(a, b):
        d = max(-1.0, min(1.0, a[0] * b[0] + a[1] * b[1]))
        return math.degrees(math.acos(abs(d)))

    pca_shift = _line_shift(p1v, p2v); cf_shift = _line_shift(c1v, c2v)
    b_pass = far_same and cf_shift <= 1e-6 and pca_shift >= 5.0
    p3_pass = a_pass and b_pass
    R["PA3_robust_vs_centroid_farthest"] = {
        "a_offaxis_farthest": {
            "farthest_is_offaxis_outlier": far_is_outlier,
            "pca_vec": _bits(vpca, 4), "cf_vec": _bits(vcf, 4),
            "pca_align_to_x_deg": round(pca_al, 3), "cf_swing_to_x_deg": round(cf_sw, 3),
            "abs_dot_pca_cf": round(diff_line, 4), "different_line": diff_line < 0.9, "pass": a_pass},
        "b_interior_move_cf_invariant_pca_responds": {
            "farthest_unchanged": far_same, "cf_line_shift_deg": round(cf_shift, 6),
            "pca_line_shift_deg": round(pca_shift, 3), "pass": b_pass},
        "pass": p3_pass}

    # ---- PA4 end-to-end projection ordering (robot) ----
    p4 = {"detail": {}, "fail_order": [], "weak_spread": [], "bad_interface": []}
    for cb in cbeats:
        an = pca[cb]
        bones = [b for b in order if b in an.get("bones", {})]
        proj_sorted = sorted(bones, key=lambda b: (_proj_key(xy, b, pca_vec), order.index(b)))
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
        p4["detail"][cb] = {"pca_vec": _bits(pca_vec, 4), "proj_order": [order.index(b) for b in proj_sorted],
                            "peak_times": [round(x, 3) for x in pts], "monotone": mono,
                            "farthest_pops_last": far_last, "spread": round(sp, 3), "iface": iface}
        if not (mono and far_last):
            p4["fail_order"].append(cb)
        if sp < SPREAD_FLOOR:
            p4["weak_spread"].append(cb)
        if not iface:
            p4["bad_interface"].append(cb)
    # dir ⟂ nrip:帶 ripples 時各件 pop 次數 == nrip 在 pca 成立
    nrip_ok = True
    nrip_detail = {}
    full = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip, cascade_dir=("geo", "pca"))
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
    R["PA4_end_to_end_ordering"] = {**p4, "nrip_intact": nrip_ok, "nrip_detail": nrip_detail, "pass": p4_pass}

    # ---- PA5 metric well-defined + guards ----
    p5 = {}
    # (a) metric:pca 主軸 == numpy 共變異主特徵向量(|dot|≈1)
    cfgs = {"robot": centers, "elong": elong, "diag": [(0, 0), (1, 1), (2, 2), (3, 3.2), (0.5, 0.0)]}
    adet = {}
    a_ok = True
    for name, C in cfgs.items():
        v = G.derive_cascade_dir(C, "pca"); nv = _np_pca_axis(C)
        d = abs(v[0] * nv[0] + v[1] * nv[1])
        adet[name] = {"abs_dot": round(float(d), 6)}
        if abs(d - 1.0) > 1e-6:
            a_ok = False
    p5["a_metric_eq_numpy"] = {"detail": adet, "pass": a_ok}
    # (b) 各向異性門檻有鑑別力:恰各向同性 → raise;微量各向異性 → 放行且軸正確
    iso_raise = {}
    for name, C in {"square": [(0, 0), (2, 0), (2, 2), (0, 2)],
                    "pentagon": [(math.cos(2 * math.pi * k / 5), math.sin(2 * math.pi * k / 5)) for k in range(5)]}.items():
        try:
            G.derive_cascade_dir(C, "pca"); iso_raise[name] = False
        except ValueError:
            iso_raise[name] = True
    barely = [(-1.0, 0.0), (1.0, 0.0), (0.0, 0.001), (0.0, -0.001)]   # var_x >> var_y 些微
    try:
        vb = G.derive_cascade_dir(barely, "pca"); barely_ok = _acute_to_x(vb) <= 1.0
    except ValueError:
        vb, barely_ok = None, False
    p5["b_anisotropy_threshold"] = {"isotropic_raise": iso_raise, "barely_vec": _bits(vb, 4) if vb else None,
                                    "barely_axis_ok": barely_ok,
                                    "pass": all(iso_raise.values()) and barely_ok}
    # (c) 守衛:件重合 / 單件 / 空件 / 未知 source(直接 & 經 build_animations)
    guards = {}
    for name, fn in {
        "coincident": lambda: G.derive_cascade_dir([(5.0, 7.0), (5.0, 7.0), (5.0, 7.0)], "pca"),
        "single": lambda: G.derive_cascade_dir([(1.0, 2.0)], "pca"),
        "empty": lambda: G.derive_cascade_dir([], "pca"),
        "unknown_source_direct": lambda: G.derive_cascade_dir([(0, 0), (1, 1)], "nope_src"),
        "unknown_source_build": lambda: G.build_animations(skel, sb, cascade_dir=("geo", "zzz")),
    }.items():
        try:
            fn(); guards[name] = False
        except ValueError:
            guards[name] = True
    # pca 經 build_animations ("geo","pca") 可用(正面:不報錯且產 cascade)
    try:
        _ = G.build_animations(skel, sb, cascade_dir=("geo", "pca")); guards["pca_build_ok"] = True
    except Exception:
        guards["pca_build_ok"] = False
    p5["c_input_guards"] = {"detail": guards, "pass": all(guards.values())}
    R["PA5_metric_guards"] = {**p5, "pass": all(v["pass"] for v in p5.values())}

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
        for k in ["PA1_present_backward_compat", "PA2_deterministic_sign", "PA3_robust_vs_centroid_farthest",
                  "PA4_end_to_end_ordering", "PA5_metric_guards"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        p3a = R["PA3_robust_vs_centroid_farthest"]["a_offaxis_farthest"]
        p3b = R["PA3_robust_vs_centroid_farthest"]["b_interior_move_cf_invariant_pca_responds"]
        print("PA3(a) off-axis farthest: pca_align={}° cf_swing={}° diff_line={}".format(
            p3a["pca_align_to_x_deg"], p3a["cf_swing_to_x_deg"], p3a["abs_dot_pca_cf"]))
        print("PA3(b) interior move: cf_shift={}° (invariant) pca_shift={}° (responds)".format(
            p3b["cf_line_shift_deg"], p3b["pca_line_shift_deg"]))
        print("PA4 projection order (robot):")
        for cb, d in R["PA4_end_to_end_ordering"]["detail"].items():
            print("   {:10s} vec={} order={} times={} mono={} far_last={}".format(
                cb, d["pca_vec"], d["proj_order"], d["peak_times"], d["monotone"], d["farthest_pops_last"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
