#!/usr/bin/env python3
"""candidate (J-7) 自我驗收閘 — cascade 跨件波方向**由件幾何自動導出**(純 CPU)。

方向軸的三次精煉(**同一條軸**,逐步移除人手指定):
  J-5:相位來源由件序換成**空間**(4 個具名方向 lr/rl/co/oc)。
  J-6:把方向**值連續化**(任意角 / 向量)—— 但「用哪個方向」仍是 per-genre **手感常數**
       (`tier_variants.TIER_CASCADE_DIR`,如 slot_bigwin→"co")。
  J-7(本閘):把方向的**取值來源**下推一層 —— `cascade_dir="geo"` 時方向**向量由件幾何導出**
       (質心 → 距質心最遠件的單位向量),隨資產自適應,不再寫死。

**honest distinction(本閘核心,勿誇大)**:J-7 **不是**新正交軸。導出的方向向量導出後**仍走 J-6 的投影排序**
(同機制:既有相位的重新指派)。J-7 只是把 J-6 那條方向軸的**取值從「人手給」換成「幾何導出」**(provenance);
跨件時序通道仍是三條正交軸(結構 nrip × 幅度 span × 方向 dir)。其價值 = 方向不再是手感常數,隨件位置自適應。

  W1 present + backward-compat : `"geo"` 產每個 cascade beat 且 finite/有 bone;非 cascade 主秀 beat 逐位元同 base;
                                `None`/`"po"` 仍逐位元同件序(geo 為全新 sentinel,純加性)。
  W2 derived projection order  : (crux)每個 cascade beat 在 geo 下各件峰時刻依**閘獨立導出**的方向向量投影鍵
                                嚴格遞增(最遠件投影最大 → 最後 pop)。
  W3 still a cascade + iface   : geo 仍一道有序跨件波(沿投影序散佈 ≥ 門檻)+首尾 setup identity + 特效 slot alpha=1。
  W4 orthogonality            : geo 下仍保 (a) dir⟂深度(峰 overshoot 同 base,HIRES 量)、(b) dir⟂nrip
                                (帶 ripples 各件 pop 次數==nrip)、(c) dir⟂span(帶 span 跨件散佈==span)。
  W5 neg-control(data-derived): (a) **crux discriminator**:同一 `cascade_dir="geo"` 套在**兩個不同幾何**
                                 (真實 robot vs 把「頭」移遠成最遠件的變體)→ **導出向量不同**且**波序不同**,
                                 各自**吻合自身幾何**的質心→最遠件投影序 → 證方向**由資料導出、非常數**;
                                (b) 導出向量/波序 == 閘**獨立重算**的質心→最遠件投影序,且最遠件(左手)最後 pop;
                                (c) geo 波序 ≠ 手感常數 "co"(現 `cascade_dir_for(slot_bigwin)`)、≠ oc、≠ 件序 po、≠ lr/rl
                                 → J-7 與所有 J-5 具名 + 現行手感預設皆不同;
                                (d) 輸入守衛:未知 geo source、空件、退化幾何(件重合→零方向)→ ValueError。

閘從**先驗庫**經 `analyze_target` → **真實 build_spine robot 骨架** → `build_animations(..., cascade_dir="geo")`
端到端量,與 (J-5)/(J-6) 閘同一 fixture;**geo 向量由閘自行獨立重算**(不碰生成器私有導出函式)以保持獨立驗證。

用法:
  python3 validate_cascade_dir_geo.py            # 摘要
  python3 validate_cascade_dir_geo.py --json     # 完整 JSON
"""
import argparse, copy, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
import validate_cascade_dir as VD           # 復用 J-5 閘的 fixture / 量測 helper
from validate_cascade import is_strictly_increasing, cascade_spread

TIERS = VD.TIERS
SPREAD_FLOOR = VD.SPREAD_FLOOR
TOL = VD.TOL
N = VD.N

# W5(a) 第二幾何:把哪個件移到何處成為最遠件(→ 導出方向轉向),用於「方向隨幾何變」鑑別。
RELOCATE_PART = "b_頭"
RELOCATE_DY = 1200.0                          # 沿 +y 推遠 → 導出方向 ≈ +y(與 robot 的 ~13° 大幅不同)


def _derive(centers, source="centroid_farthest"):
    """閘**獨立**重算質心→最遠件單位向量(不呼叫 G.derive_cascade_dir,保持獨立驗證)。"""
    n = len(centers)
    mx = sum(c[0] for c in centers) / n
    my = sum(c[1] for c in centers) / n
    best_i, best_d2 = 0, -1.0
    for i, (x, y) in enumerate(centers):
        d2 = (x - mx) ** 2 + (y - my) ** 2
        if d2 > best_d2:
            best_d2, best_i = d2, i
    dx, dy = centers[best_i][0] - mx, centers[best_i][1] - my
    L = math.hypot(dx, dy)
    return (dx / L, dy / L), best_i


def _proj_key(xy, bone, vec):
    x, y = xy[bone]
    return x * vec[0] + y * vec[1]


def _bytes(obj):
    return json.dumps(obj, sort_keys=True)


def _relocate_skeleton(skel, xy):
    """回傳 (mutated_skel, mutated_xy):把 RELOCATE_PART 沿 +y 推遠成最遠件。"""
    B = copy.deepcopy(skel)
    for b in B["bones"]:
        if b["name"] == RELOCATE_PART and b["name"] in xy:
            b["x"] = xy[b["name"]][0]
            b["y"] = xy[b["name"]][1] + RELOCATE_DY
    xyB = {b["name"]: (b.get("x", 0.0), b.get("y", 0.0)) for b in B["bones"] if b["name"] != "root"}
    return B, xyB


def run():
    skel = VD._skeleton()
    sb = VD._storyboard(VD.GENRE)
    order = VD._part_order(sb)
    cx, cy = VD._canvas_center(skel)
    xy = VD._bone_xy(skel)
    gains = TV.gains_for(VD.GENRE)
    rip = TV.cascade_ripples_for(VD.GENRE)
    span = TV.cascade_span_for(VD.GENRE)

    base = G.build_animations(skel, sb)                               # cascade_dir=None(件序)
    geo = G.build_animations(skel, sb, cascade_dir="geo")
    cbeats = VD._cascade_beats(base)
    main_beats = VD._main_beats(base)
    # 閘獨立導出(robot 幾何)的方向向量 + 最遠件 index(對齊 order)
    centers = [xy[b] for b in order]
    geo_vec, far_i = _derive(centers)
    R = {}

    # ---- W1 present + backward-compat ----
    w1 = {"missing": [], "not_finite": [], "no_bones": [], "noncascade_changed": [], "po_eq_none": None}
    for cb in cbeats:
        an = geo.get(cb)
        if an is None:
            w1["missing"].append(cb); continue
        if not SA.all_finite(an):
            w1["not_finite"].append(cb)
        if not an.get("bones"):
            w1["no_bones"].append(cb)
    for beat, cat in main_beats.items():
        if cat == "cascade":
            continue
        if _bytes(geo.get(beat)) != _bytes(base.get(beat)):
            w1["noncascade_changed"].append(beat)
    po = G.build_animations(skel, sb, cascade_dir="po")
    w1["po_eq_none"] = all(_bytes(po[cb]) == _bytes(base[cb]) for cb in cbeats)
    w1_pass = (bool(cbeats) and not w1["missing"] and not w1["not_finite"] and not w1["no_bones"]
               and not w1["noncascade_changed"] and w1["po_eq_none"])
    R["W1_present_backward_compat"] = {"cascade_beats": cbeats, **w1, "pass": w1_pass}

    # ---- W2 derived projection ordering (crux) ----
    w2 = {"detail": {}, "fail": []}
    for cb in cbeats:
        an = geo[cb]
        bones = [b for b in order if b in an.get("bones", {})]
        proj_sorted = sorted(bones, key=lambda b: (_proj_key(xy, b, geo_vec), order.index(b)))
        pts = [VD.peak_time(an, b) for b in proj_sorted]
        mono = is_strictly_increasing(pts)
        # 最遠件(投影最大)最後 pop
        far_bone = order[far_i]
        far_last = (far_bone in bones) and (proj_sorted[-1] == far_bone)
        w2["detail"][cb] = {"derived_vec": [round(c, 4) for c in geo_vec],
                            "proj_sorted": proj_sorted,
                            "peak_times_in_proj_order": [round(x, 3) for x in pts],
                            "monotone_in_projection": mono,
                            "farthest_pops_last": far_last, "farthest": far_bone}
        if not (mono and far_last):
            w2["fail"].append(cb)
    R["W2_derived_projection_ordering"] = {**w2, "pass": bool(cbeats) and not w2["fail"]}

    # ---- W3 still a cascade + interface ----
    w3 = {"weak_spread": [], "bad_interface": [], "detail": {}}
    for cb in cbeats:
        an = geo[cb]
        bones = [b for b in order if b in an.get("bones", {})]
        proj_sorted = sorted(bones, key=lambda b: (_proj_key(xy, b, geo_vec), order.index(b)))
        pts = [VD.peak_time(an, b) for b in proj_sorted]
        sp = cascade_spread(pts)
        w3["detail"][cb] = {"spread": round(sp, 3)}
        if sp < SPREAD_FLOOR:
            w3["weak_spread"].append(cb)
        dur = SA.duration(an)
        b0 = SA.sample(an, 0.0)["bones"]; bE = SA.sample(an, dur)["bones"]
        s0 = SA.sample(an, 0.0)["slots"]; sE = SA.sample(an, dur)["slots"]
        iface = (all(VD._is_ident(v) for v in b0.values()) and all(VD._is_ident(v) for v in bE.values())
                 and all(abs(s["alpha"] - 1) <= TOL for s in s0.values())
                 and all(abs(s["alpha"] - 1) <= TOL for s in sE.values()))
        if not iface:
            w3["bad_interface"].append(cb)
    R["W3_signature_interface"] = {"weak_spread": w3["weak_spread"], "bad_interface": w3["bad_interface"],
                                   "detail": w3["detail"],
                                   "pass": not w3["weak_spread"] and not w3["bad_interface"]}

    # ---- W4 orthogonality (geo 仍保三軸正交) ----
    # (a) dir ⟂ 深度:geo 各件峰 overshoot == base(po)(HIRES 量,消相位時移混疊)
    depth_const = True
    depth_detail = {}
    for cb in cbeats:
        bones = [b for b in order if b in base[cb].get("bones", {})]
        for b in bones:
            dg = round(VD.scale_overshoot_of(geo[cb], b), 6)
            db = round(VD.scale_overshoot_of(base[cb], b), 6)
            depth_detail["{}:{}".format(cb, b)] = [dg, db]
            if abs(dg - db) > VD.DEPTH_TOL:
                depth_const = False
    # (b) dir ⟂ nrip:帶 ripples 時各件 pop 次數==nrip 在 geo 成立
    nrip_ok = True
    nrip_detail = {}
    full = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip, cascade_dir="geo")
    for cb in cbeats:
        for t in TIERS:
            an = full["{}__{}".format(cb, t)]
            cnts = [VD.peak_times_count(an, b) for b in an.get("bones", {})]
            ok = bool(cnts) and all(c == rip[t] for c in cnts)
            nrip_detail["{}__{}".format(cb, t)] = {"nrip": rip[t], "counts": cnts, "ok": ok}
            if not ok:
                nrip_ok = False
    # (c) dir ⟂ span:帶 span 時各檔位跨件散佈 == 宣告 span(相位集合只被排列 → min/max 不變)
    span_ok = True
    span_detail = {}
    sp_run = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_span=span, cascade_dir="geo")
    for cb in cbeats:
        for t in TIERS:
            an = sp_run["{}__{}".format(cb, t)]
            bones = [b for b in order if b in an.get("bones", {})]
            proj_sorted = sorted(bones, key=lambda b: (_proj_key(xy, b, geo_vec), order.index(b)))
            pts = [VD.peak_time(an, b) for b in proj_sorted]
            sp = cascade_spread(pts)
            span_detail["{}__{}".format(cb, t)] = {"declared": round(span[t], 4), "spread": round(sp, 4)}
            if abs(sp - span[t]) > 2.0 / N:
                span_ok = False
    R["W4_orthogonality"] = {"a_depth_const_vs_base": depth_const, "a_detail": depth_detail,
                             "b_nrip_intact": nrip_ok, "b_detail": nrip_detail,
                             "c_span_spread_eq_declared": span_ok, "c_detail": span_detail,
                             "pass": depth_const and nrip_ok and span_ok}

    # ---- W5 negative controls (data-derived) ----
    w5 = {}

    def _idx_tuple(bones_in_order):
        return tuple(order.index(b) for b in bones_in_order)

    # (a) crux discriminator:同 cascade_dir="geo" 套兩個不同幾何 → 向量/波序不同,各吻合自身幾何
    skelB, xyB = _relocate_skeleton(skel, xy)
    geoB = G.build_animations(skelB, sb, cascade_dir="geo")
    centersB = [xyB[b] for b in order]
    vecB, farB_i = _derive(centersB)
    cda = {"detail": {}, "fail": []}
    for cb in cbeats:
        bones = [b for b in order if b in geo[cb].get("bones", {})]
        measA = sorted(bones, key=lambda b: VD.peak_time(geo[cb], b))           # robot 實測波序
        measB = sorted(bones, key=lambda b: VD.peak_time(geoB[cb], b))          # 變體實測波序
        indepA = sorted(bones, key=lambda b: (_proj_key(xy, b, geo_vec), order.index(b)))
        indepB = sorted(bones, key=lambda b: (_proj_key(xyB, b, vecB), order.index(b)))
        a_match = (measA == indepA)                    # robot 波序吻合自身幾何
        b_match = (measB == indepB)                    # 變體波序吻合自身幾何
        differs = (measA != measB)                     # 兩幾何波序不同 → 方向隨幾何變
        vec_diff = (_bytes([round(c, 6) for c in geo_vec]) != _bytes([round(c, 6) for c in vecB]))
        ok = a_match and b_match and differs and vec_diff
        cda["detail"][cb] = {
            "vecA": [round(c, 4) for c in geo_vec], "vecB": [round(c, 4) for c in vecB],
            "orderA_idx": list(_idx_tuple(measA)), "orderB_idx": list(_idx_tuple(measB)),
            "orderA_matches_geomA": a_match, "orderB_matches_geomB": b_match,
            "orders_differ": differs, "vectors_differ": vec_diff}
        if not ok:
            cda["fail"].append(cb)
    w5["a_crux_direction_tracks_geometry"] = {"detail": cda["detail"],
                                              "pass": bool(cbeats) and not cda["fail"]}

    # (b) derived == independent centroid→farthest(robot);最遠件(左手)最後 pop
    bdet = {"detail": {}, "fail": []}
    for cb in cbeats:
        bones = [b for b in order if b in geo[cb].get("bones", {})]
        meas = sorted(bones, key=lambda b: VD.peak_time(geo[cb], b))
        indep = sorted(bones, key=lambda b: (_proj_key(xy, b, geo_vec), order.index(b)))
        far_bone = order[far_i]
        ok = (meas == indep) and (far_bone in bones) and (meas[-1] == far_bone)
        bdet["detail"][cb] = {"measured": list(_idx_tuple(meas)), "independent": list(_idx_tuple(indep)),
                              "farthest": far_bone, "farthest_last": meas[-1] == far_bone}
        if not ok:
            bdet["fail"].append(cb)
    w5["b_derived_eq_independent"] = {"detail": bdet["detail"], "pass": bool(cbeats) and not bdet["fail"]}

    # (c) geo ≠ 手感常數 "co" / oc / 件序 po / lr / rl(J-7 與所有 J-5 具名 + 現行手感預設皆不同)
    handpick = TV.cascade_dir_for(VD.GENRE)            # 現行 slot_bigwin 手感預設 = "co"
    cdet = {"detail": {}, "fail": [], "handpick": handpick}
    other = {}
    for d in ["co", "oc", "lr", "rl"]:
        other[d] = G.build_animations(skel, sb, cascade_dir=d)
    for cb in cbeats:
        bones = [b for b in order if b in geo[cb].get("bones", {})]
        geo_ord = _idx_tuple(sorted(bones, key=lambda b: VD.peak_time(geo[cb], b)))
        po_ord = _idx_tuple(sorted(bones, key=lambda b: VD.peak_time(base[cb], b)))
        cmp = {"po": geo_ord != po_ord}
        for d in ["co", "oc", "lr", "rl"]:
            d_ord = _idx_tuple(sorted(bones, key=lambda b: VD.peak_time(other[d][cb], b)))
            cmp["ne_" + d] = geo_ord != d_ord
        ok = all(cmp.values())
        cdet["detail"][cb] = {"geo_order_idx": list(geo_ord), **cmp}
        if not ok:
            cdet["fail"].append(cb)
    w5["c_geo_ne_handpick_and_named"] = {"detail": cdet["detail"], "handpick": handpick,
                                         "pass": bool(cbeats) and not cdet["fail"]}

    # (d) 輸入守衛:未知 geo source / 空件 / 退化幾何 → ValueError
    guards = {}
    # 未知 source(經 build_animations 的 ("geo",src) 路徑)
    try:
        G.build_animations(skel, sb, cascade_dir=("geo", "zzz")); guards["unknown_source"] = False
    except ValueError:
        guards["unknown_source"] = True
    # derive 直接:空件
    try:
        G.derive_cascade_dir([]); guards["empty_centers"] = False
    except ValueError:
        guards["empty_centers"] = True
    # derive 直接:退化(所有件重合 → 零方向)
    try:
        G.derive_cascade_dir([(5.0, 7.0), (5.0, 7.0), (5.0, 7.0)]); guards["degenerate"] = False
    except ValueError:
        guards["degenerate"] = True
    # derive 直接:未知 source(J-8 起 "pca" 已為合法 source,改用仍未知的字串保持本守衛語意)
    try:
        G.derive_cascade_dir([(0.0, 0.0), (1.0, 1.0)], source="nonexistent_src_zzz")
        guards["derive_unknown_source"] = False
    except ValueError:
        guards["derive_unknown_source"] = True
    w5["d_input_guards"] = {"detail": guards, "pass": all(guards.values())}

    R["W5_neg_control"] = {**w5, "pass": all(v["pass"] for v in w5.values())}

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
        for k in ["W1_present_backward_compat", "W2_derived_projection_ordering", "W3_signature_interface",
                  "W4_orthogonality", "W5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("W2 derived vec + peak times in projection order:")
        for cb, d in R["W2_derived_projection_ordering"]["detail"].items():
            print("  {:10s} vec={} order={} times={} mono={} far_last={}".format(
                cb, d["derived_vec"], d["proj_sorted"], d["peak_times_in_proj_order"],
                d["monotone_in_projection"], d["farthest_pops_last"]))
        print("W5(a) direction tracks geometry (two geometries, same 'geo'):")
        for cb, d in R["W5_neg_control"]["a_crux_direction_tracks_geometry"]["detail"].items():
            print("  {:10s} vecA={} vecB={} orders_differ={} A_fits={} B_fits={}".format(
                cb, d["vecA"], d["vecB"], d["orders_differ"],
                d["orderA_matches_geomA"], d["orderB_matches_geomB"]))
        print("W5(c) geo != handpick({}) / co / oc / po / lr / rl:".format(
            R["W5_neg_control"]["c_geo_ne_handpick_and_named"]["handpick"]))
        for cb, d in R["W5_neg_control"]["c_geo_ne_handpick_and_named"]["detail"].items():
            print("  {:10s} {}".format(cb, {k: v for k, v in d.items() if k != "geo_order_idx"}))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
