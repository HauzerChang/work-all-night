#!/usr/bin/env python3
"""candidate (J-6) 自我驗收閘 — cascade 跨件波方向**一般化為任意角投影**(純 CPU)。

(J-5) 把 cascade 波的**相位來源**從件序換成空間,給了 4 個**具名**方向:基數軸 lr/rl(左→右 / 右→左)+
radial co/oc(中心外擴 / 外向內)。本閘驗 (J-6):把這條**方向軸由離散(4 向)補成連續** —— 方向可給
**角度(度)或向量 (ux,uy)**,相位依件中心在該單位向量上的**投影** `x·ux + y·uy` 排序。

**honest distinction(本閘核心,勿誇大)**:J-6 **不是**第四條正交軸。J-5 已把「方向 / 相位來源」立為第三軸
(結構 nrip × 幅度 span × 方向)。J-6 只是把這**同一條方向軸**的取值從「4 個具名」擴成「連續角 + 任意向量」;
機制仍是 J-5 的「既有相位的重新指派(排列)」,只是**排序鍵**從 {基數軸 ±x, radial} 擴成 {任意投影角, radial}。
其價值 = 對角 / 垂直 / 任意角的波,J-5 的 4 向無法表達。

  V1 present + backward-compat : 每個新方向(90°/270°/45°/135°/向量)皆產每個 cascade beat 且 finite/有 bone;
                                **投影族含 J-5 具名方向**:角度 0°/180° 與向量 (1,0)/(-1,0) **逐位元同** "lr"/"rl";
                                `None`/`"po"` 仍逐位元同件序;非 cascade 主秀 beat 不受任一方向影響。
  V2 projection ordering(crux): 每個新方向下,各件峰時刻依**該方向投影鍵** `x·ux+y·sy` 嚴格遞增
                                (任意角的波序 = 投影序)。
  V3 still a cascade + iface   : 每個新方向仍一道有序跨件波(沿投影序散佈 ≥ 門檻)+首尾 setup identity + 特效 slot alpha=1。
  V4 orthogonality            : 新方向(角 / 向量)下仍保 (a) dir⟂深度(峰 overshoot 跨方向相同,HIRES 量)、
                                (b) dir⟂nrip(帶 ripples 各件 pop 次數==nrip)、(c) dir⟂span(帶 span 跨件散佈==span)。
  V5 neg-control              : (a) **crux discriminator**:垂直(90°)與對角(45°)的**實測峰序** ∉ 全部 J-5 方向
                                 {po, lr, rl, co, oc} 的件序集合 → 證任意角投影是**真‧新方向**,非換名的具名方向;
                                (b) **連續性 / 端點**:0°==lr 件序、180°==rl 件序、90° 兩者皆非(lr/rl 為投影族端點,內部為新);
                                (c) **投影 ≠ radial**:crux 方向的峰序亦 ≠ co/oc(含在 (a));
                                (d) 輸入守衛:零向量 / 長度≠2 向量 / bool / 未知字串 → ValueError。

閘從**先驗庫**經 `analyze_target`→ **真實 build_spine robot 骨架** → `build_animations(..., cascade_dir=...)` 端到端量,
與 (J-5) 閘同一 fixture(robot 件序 [光暈,右手,頭,身體,左手],x/y 非單調 → 垂直 / 對角序與件序、x 序、徑向序皆異)。

用法:
  python3 validate_cascade_dir_vector.py            # 摘要
  python3 validate_cascade_dir_vector.py --json     # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
import validate_cascade_dir as VD           # 復用 J-5 閘的 fixture / 量測 helper
from validate_cascade import is_strictly_increasing, cascade_spread

TIERS = VD.TIERS
J5_DIRS = ["lr", "rl", "co", "oc"]          # J-5 具名(用於 V5 鑑別集合)
# J-6 測試方向:角度(度)+ 向量(涵蓋垂直 / 對角 / 任意向量)。每個在此 fixture 上皆 ∉ J-5 件序集合。
TEST_DIRS = [90.0, 270.0, 45.0, 135.0, (1.0, 1.0), (0.0, -1.0)]
CRUX_DIRS = [90.0, 45.0]                     # V5(a) 鑑別用:垂直 + 對角
SPREAD_FLOOR = VD.SPREAD_FLOOR
TOL = VD.TOL
N = VD.N


def _dir_label(d):
    return "ang{:g}".format(d) if isinstance(d, (int, float)) else "vec{:g},{:g}".format(d[0], d[1])


def _proj_vec(d):
    """測試方向 → 正規化投影單位向量 (ux,uy)(閘自己算,不碰生成器私有函式,保持獨立驗證)。"""
    if isinstance(d, (int, float)):
        th = math.radians(float(d))
        return (math.cos(th), math.sin(th))
    n = math.hypot(d[0], d[1])
    return (d[0] / n, d[1] / n)


def _proj_key(bone, xy, vec):
    x, y = xy[bone]
    return x * vec[0] + y * vec[1]


def _bytes(obj):
    return json.dumps(obj, sort_keys=True)


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
    by_dir = {_dir_label(d): G.build_animations(skel, sb, cascade_dir=d) for d in TEST_DIRS}
    cbeats = VD._cascade_beats(base)
    main_beats = VD._main_beats(base)
    R = {}

    # ---- V1 present + backward-compat ----
    v1 = {"missing": [], "not_finite": [], "no_bones": [], "noncascade_changed": [],
          "proj_contains_named": {}, "po_eq_none": None}
    for d in TEST_DIRS:
        lab = _dir_label(d)
        for cb in cbeats:
            an = by_dir[lab].get(cb)
            if an is None:
                v1["missing"].append("{}:{}".format(lab, cb)); continue
            if not SA.all_finite(an):
                v1["not_finite"].append("{}:{}".format(lab, cb))
            if not an.get("bones"):
                v1["no_bones"].append("{}:{}".format(lab, cb))
        # 非 cascade 主秀 beat 不受方向影響(逐位元同 base)
        for beat, cat in main_beats.items():
            if cat == "cascade":
                continue
            if _bytes(by_dir[lab].get(beat)) != _bytes(base.get(beat)):
                v1["noncascade_changed"].append("{}:{}".format(lab, beat))
    # 投影族含 J-5 具名:0°/180° == lr/rl、向量 (1,0)/(-1,0) == lr/rl(逐位元)
    named = {"lr": G.build_animations(skel, sb, cascade_dir="lr"),
             "rl": G.build_animations(skel, sb, cascade_dir="rl")}
    equiv = {"ang0==lr": (0.0, "lr"), "ang180==rl": (180.0, "rl"),
             "vec1,0==lr": ((1.0, 0.0), "lr"), "vec-1,0==rl": ((-1.0, 0.0), "rl")}
    for key, (d, nm) in equiv.items():
        an_d = G.build_animations(skel, sb, cascade_dir=d)
        ok = all(_bytes(an_d[cb]) == _bytes(named[nm][cb]) for cb in cbeats)
        v1["proj_contains_named"][key] = ok
    # None/po 逐位元(繼承 J-5,再確認一次)
    po = G.build_animations(skel, sb, cascade_dir="po")
    v1["po_eq_none"] = all(_bytes(po[cb]) == _bytes(base[cb]) for cb in cbeats)
    v1_pass = (bool(cbeats) and not v1["missing"] and not v1["not_finite"] and not v1["no_bones"]
               and not v1["noncascade_changed"] and all(v1["proj_contains_named"].values())
               and v1["po_eq_none"])
    R["V1_present_backward_compat"] = {"test_dirs": [_dir_label(d) for d in TEST_DIRS],
                                       "cascade_beats": cbeats, **v1, "pass": v1_pass}

    # ---- V2 projection ordering (crux) ----
    v2 = {"detail": {}, "fail": []}
    for d in TEST_DIRS:
        lab = _dir_label(d); vec = _proj_vec(d)
        for cb in cbeats:
            an = by_dir[lab][cb]
            bones = [b for b in order if b in an.get("bones", {})]
            proj_sorted = sorted(bones, key=lambda b: (_proj_key(b, xy, vec), order.index(b)))
            pts = [VD.peak_time(an, b) for b in proj_sorted]
            mono = is_strictly_increasing(pts)
            v2["detail"]["{}:{}".format(lab, cb)] = {
                "proj_sorted": proj_sorted,
                "peak_times_in_proj_order": [round(x, 3) for x in pts],
                "monotone_in_projection": mono}
            if not mono:
                v2["fail"].append("{}:{}".format(lab, cb))
    R["V2_projection_ordering"] = {**v2, "pass": bool(cbeats) and not v2["fail"]}

    # ---- V3 still a cascade + interface ----
    v3 = {"weak_spread": [], "bad_interface": [], "detail": {}}
    for d in TEST_DIRS:
        lab = _dir_label(d); vec = _proj_vec(d)
        for cb in cbeats:
            an = by_dir[lab][cb]
            bones = [b for b in order if b in an.get("bones", {})]
            proj_sorted = sorted(bones, key=lambda b: (_proj_key(b, xy, vec), order.index(b)))
            pts = [VD.peak_time(an, b) for b in proj_sorted]
            sp = cascade_spread(pts)
            v3["detail"]["{}:{}".format(lab, cb)] = {"spread": round(sp, 3)}
            if sp < SPREAD_FLOOR:
                v3["weak_spread"].append("{}:{}".format(lab, cb))
            dur = SA.duration(an)
            b0 = SA.sample(an, 0.0)["bones"]; bE = SA.sample(an, dur)["bones"]
            s0 = SA.sample(an, 0.0)["slots"]; sE = SA.sample(an, dur)["slots"]
            iface = (all(VD._is_ident(v) for v in b0.values()) and all(VD._is_ident(v) for v in bE.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in s0.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in sE.values()))
            if not iface:
                v3["bad_interface"].append("{}:{}".format(lab, cb))
    R["V3_signature_interface"] = {"weak_spread": v3["weak_spread"], "bad_interface": v3["bad_interface"],
                                   "detail": v3["detail"],
                                   "pass": not v3["weak_spread"] and not v3["bad_interface"]}

    # ---- V4 orthogonality (新方向仍保三軸正交) ----
    # (a) dir ⟂ 深度:同件峰 overshoot 在 base + 所有新方向下相同(HIRES 量,消相位時移混疊)
    depth_const = True
    depth_detail = {}
    for cb in cbeats:
        bones = [b for b in order if b in base[cb].get("bones", {})]
        for b in bones:
            dvals = [round(VD.scale_overshoot_of(by_dir[_dir_label(d)][cb], b), 6) for d in TEST_DIRS]
            dvals.append(round(VD.scale_overshoot_of(base[cb], b), 6))
            depth_detail["{}:{}".format(cb, b)] = dvals
            if max(dvals) - min(dvals) > VD.DEPTH_TOL:
                depth_const = False
    # (b) dir ⟂ nrip:帶 ripples 時各件 pop 次數==nrip 在新方向成立
    nrip_ok = True
    nrip_detail = {}
    for d in TEST_DIRS:
        lab = _dir_label(d)
        full = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip, cascade_dir=d)
        for cb in cbeats:
            for t in TIERS:
                an = full["{}__{}".format(cb, t)]
                cnts = [VD.peak_times_count(an, b) for b in an.get("bones", {})]
                ok = bool(cnts) and all(c == rip[t] for c in cnts)
                nrip_detail["{}:{}__{}".format(lab, cb, t)] = {"nrip": rip[t], "counts": cnts, "ok": ok}
                if not ok:
                    nrip_ok = False
    # (c) dir ⟂ span:帶 span 時各檔位跨件散佈 == span,跨新方向恆相同(相位集合只被排列 → min/max 不變)
    span_const = True
    span_detail = {}
    spread_by_dir = {}
    for d in TEST_DIRS:
        lab = _dir_label(d)
        sp_run = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_span=span, cascade_dir=d)
        for cb in cbeats:
            for t in TIERS:
                an = sp_run["{}__{}".format(cb, t)]
                bones = [b for b in order if b in an.get("bones", {})]
                pts = [VD.peak_time(an, b) for b in bones]
                spread_by_dir.setdefault("{}__{}".format(cb, t), {})[lab] = round(cascade_spread(pts), 4)
    for key, dmap in spread_by_dir.items():
        vals = list(dmap.values())
        span_detail[key] = dmap
        if max(vals) - min(vals) > 2.0 / N:
            span_const = False
    R["V4_orthogonality"] = {"a_depth_const_over_dir": depth_const, "a_detail": depth_detail,
                             "b_nrip_intact_all_dirs": nrip_ok, "b_detail": nrip_detail,
                             "c_span_spread_const_over_dir": span_const, "c_detail": span_detail,
                             "pass": depth_const and nrip_ok and span_const}

    # ---- V5 negative controls ----
    v5 = {}
    # J-5 全部方向的**件序集合**(用 bone 的 part-order index 元組表示一個「波序」)
    def _idx_tuple(bones_in_order):
        return tuple(order.index(b) for b in bones_in_order)
    j5_orderings = {}          # per cascade beat: set of J-5 orderings {po, lr, rl, co, oc}
    for cb in cbeats:
        bones = [b for b in order if b in base[cb].get("bones", {})]
        s = {_idx_tuple(bones)}                                    # po(件序)
        for d in J5_DIRS:
            sorted_b = sorted(bones, key=lambda b: (VD._spatial_key(b, xy, cx, cy, d), order.index(b)))
            s.add(_idx_tuple(sorted_b))
        j5_orderings[cb] = s
    # (a) crux discriminator:垂直 / 對角 的**實測峰序** ∉ J-5 件序集合
    cda = {"detail": {}, "fail": []}
    for d in CRUX_DIRS:
        lab = _dir_label(d)
        for cb in cbeats:
            an = by_dir[lab][cb]
            bones = [b for b in order if b in an.get("bones", {})]
            measured = sorted(bones, key=lambda b: VD.peak_time(an, b))   # 依實測峰時刻
            mt = _idx_tuple(measured)
            novel = mt not in j5_orderings[cb]
            cda["detail"]["{}:{}".format(lab, cb)] = {
                "measured_peak_order_idx": list(mt),
                "j5_orderings_idx": [list(t) for t in sorted(j5_orderings[cb])],
                "novel_vs_all_j5": novel}
            if not novel:
                cda["fail"].append("{}:{}".format(lab, cb))
    v5["a_crux_novel_vs_all_j5"] = {"detail": cda["detail"], "pass": bool(cbeats) and not cda["fail"]}
    # (b) 連續性 / 端點:0°==lr、180°==rl、90° 兩者皆非(方向序層級)
    cont = {"detail": {}, "fail": []}
    ang0 = G.build_animations(skel, sb, cascade_dir=0.0)
    ang180 = G.build_animations(skel, sb, cascade_dir=180.0)
    ang90 = G.build_animations(skel, sb, cascade_dir=90.0)
    lr = named["lr"]; rl = named["rl"]
    for cb in cbeats:
        bones = [b for b in order if b in base[cb].get("bones", {})]
        def peakord(an):   # an = 單一 beat 動畫
            return _idx_tuple(sorted(bones, key=lambda b: VD.peak_time(an, b)))
        o0, o180, o90 = peakord(ang0[cb]), peakord(ang180[cb]), peakord(ang90[cb])
        olr, orl = peakord(lr[cb]), peakord(rl[cb])
        ok = (o0 == olr) and (o180 == orl) and (o90 != olr) and (o90 != orl)
        cont["detail"][cb] = {"ang0": list(o0), "lr": list(olr), "ang180": list(o180), "rl": list(orl),
                              "ang90": list(o90), "ang0_eq_lr": o0 == olr, "ang180_eq_rl": o180 == orl,
                              "ang90_differs_both": (o90 != olr and o90 != orl)}
        if not ok:
            cont["fail"].append(cb)
    v5["b_continuum_endpoints"] = {"detail": cont["detail"], "pass": bool(cbeats) and not cont["fail"]}
    # (c) 投影 ≠ radial:crux 方向峰序 ≠ co 與 oc(各別檢,補強 (a))
    radial = {"detail": {}, "fail": []}
    for cb in cbeats:
        bones = [b for b in order if b in base[cb].get("bones", {})]
        co_ord = _idx_tuple(sorted(bones, key=lambda b: (VD._spatial_key(b, xy, cx, cy, "co"), order.index(b))))
        oc_ord = _idx_tuple(sorted(bones, key=lambda b: (VD._spatial_key(b, xy, cx, cy, "oc"), order.index(b))))
        for d in CRUX_DIRS:
            lab = _dir_label(d); an = by_dir[lab][cb]
            mt = _idx_tuple(sorted(bones, key=lambda b: VD.peak_time(an, b)))
            ok = (mt != co_ord) and (mt != oc_ord)
            radial["detail"]["{}:{}".format(lab, cb)] = {"measured": list(mt), "co": list(co_ord),
                                                         "oc": list(oc_ord), "differs_from_radial": ok}
            if not ok:
                radial["fail"].append("{}:{}".format(lab, cb))
    v5["c_projection_ne_radial"] = {"detail": radial["detail"], "pass": bool(cbeats) and not radial["fail"]}
    # (d) 輸入守衛:零向量 / 長度≠2 / bool / 未知字串 → ValueError
    guards = {}
    for key, bad in [("zero_vector", (0.0, 0.0)), ("len3_vector", (1.0, 2.0, 3.0)),
                     ("bool", True), ("unknown_str", "zzz")]:
        raised = False
        try:
            G.build_animations(skel, sb, cascade_dir=bad)
        except ValueError:
            raised = True
        guards[key] = raised
    v5["d_input_guards"] = {"detail": guards, "pass": all(guards.values())}
    R["V5_neg_control"] = {**v5, "pass": all(v["pass"] for v in v5.values())}

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
        for k in ["V1_present_backward_compat", "V2_projection_ordering", "V3_signature_interface",
                  "V4_orthogonality", "V5_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V1 projection contains named (0/180/vec == lr/rl):",
              R["V1_present_backward_compat"]["proj_contains_named"])
        print("V2 peak times in projection order (per dir):")
        for key, d in R["V2_projection_ordering"]["detail"].items():
            print("  {:18s} {} mono={}".format(key, d["peak_times_in_proj_order"], d["monotone_in_projection"]))
        print("V5(a) crux novel vs all J-5 orderings:")
        for key, d in R["V5_neg_control"]["a_crux_novel_vs_all_j5"]["detail"].items():
            print("  {:14s} measured={} novel={}".format(key, d["measured_peak_order_idx"], d["novel_vs_all_j5"]))
        print("V5(b) continuum endpoints (0==lr, 180==rl, 90 differs):")
        for cb, d in R["V5_neg_control"]["b_continuum_endpoints"]["detail"].items():
            print("  {:10s} 0==lr {} / 180==rl {} / 90!=both {}".format(
                cb, d["ang0_eq_lr"], d["ang180_eq_rl"], d["ang90_differs_both"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
