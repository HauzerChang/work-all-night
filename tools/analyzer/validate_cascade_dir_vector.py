#!/usr/bin/env python3
"""candidate (J-6) 自我驗收閘 — cascade 跨件波方向**推廣成任意直線方向向量投影**(純 CPU)。

(J-5) 把 cascade 波的**相位來源**從件序換成空間,但只有 **4 個離散名鍵**:lr/rl(軸向)+ co/oc(徑向)。
本閘驗 (J-6) 的推廣:相位排序鍵改由件中心沿**任意單位向量 `(ux,uy)` 的投影** `(x−cx)·ux+(y−cy)·uy` 決定
→ 波方向可沿**任一角度**(對角、垂直……)線性鋪開。波形(SPAN/nrip/深度)完全不動 → 只重排「哪件何時 pop」。

**crux(J-6 的 honest distinction,本閘核心鑑別點)**:投影族只推廣**直線/軸向**方向——
  ① lr≡(1,0)、rl≡(−1,0) 是投影族的**特例**(軸向投影)→ V1 證 `(1,0)` 逐位元==`"lr"`、`(−1,0)`==`"rl"`;
  ② **對角(45°)/ 垂直(90°)是 J-5 四名鍵到不了的新方向** → V3 證 45° 對角峰序與 lr/rl/co/oc **四者皆異** 且 ≠件序;
  ③ 但 **co/oc 是徑向(距中心的非線性距離),不是任何單一投影** → V3 證 co/oc 的峰序**不在**任一投影角度
     (密格掃 360°)能產生的排序集合裡 —— 徑向仍屬**另一族**,誠實標出投影族的邊界(非「涵蓋一切方向」)。

閘從**先驗庫**經 `analyze_target`(build_storyboard)→ **真實 build_spine robot 骨架** →
`build_animations(..., cascade_dir=(ux,uy))` 端到端量,與 (J)/(J-3)/(J-4)/(J-5) 閘同一 fixture 與量測機制
(直接複用 `validate_cascade_dir` 的證過的 helper,確保與 J-5 同源可信)。

  V1 present + axis special-case : 每向量方向皆產每個 cascade beat 且 finite/有 bone;`(1,0)` 逐位元==`"lr"`、
                                  `(−1,0)`==`"rl"`(**軸向名鍵是投影特例**);非 cascade 主秀 beat 不受影響。
  V2 projection ordering (crux)  : 每向量方向下,各件峰時刻依**沿該向量的投影**嚴格遞增(峰序由投影單調決定)。
  V3 diagonal new + radial bound : (a) 45° 對角峰序 ≠ lr/rl/co/oc **四者** 且 ≠件序(到得了 J-5 到不了的方向);
                                  (b) 密格掃 360° 投影排序集合:co/oc 徑向序 **不在**其中(徑向非投影,誠實邊界)、
                                     件序亦不在、而 45° 對角**在**其中且 ≠ 兩軸向序(真二維方向控制)。
  V4 still a cascade + iface     : 每向量方向仍是**一道有序跨件波**(沿投影序散佈 ≥ 門檻);每件首尾 setup
                                  identity + 特效 slot alpha 首尾=1(可插 Loop 間)。
  V5 orthogonality               : (a) dir ⟂ 深度:同件 scale 峰 overshoot 在所有向量方向下==base(HIRES 消混疊);
                                  (b) dir ⟂ span:帶 tier_cascade_span 時跨件散佈在所有向量方向下==span;
                                  (c) dir ⟂ nrip:帶 tier_cascade_ripples 時各件 pop 次數==nrip。
  V6 neg-control                 : (a) **crux 反向**:角度 θ 的峰序 == θ+180° 峰序的**逆序**(反方向把波倒過來);
                                  (b) 零向量 `(0,0)` → ValueError(輸入守衛);
                                  (c) `parse_cascade_dir` 對亂字串 / 殘缺向量 'v1' → ValueError;
                                  (d) 向量方向只作用 cascade:非 cascade 主秀 beat 逐位元同 base(不外洩)。

用法:
  python3 validate_cascade_dir_vector.py          # 摘要
  python3 validate_cascade_dir_vector.py --json    # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from analyze_target import analyze
from validate_cascade import series, is_strictly_increasing, cascade_spread
# 複用 J-5 閘證過的 helper(同源、同 fixture、同量測 → 新閘與 J-5 一致可信)
import validate_cascade_dir as VD

GENRE = "slot_bigwin"
TIERS = VD.TIERS
IDENT = VD.IDENT
TOL = VD.TOL
SPREAD_FLOOR = VD.SPREAD_FLOOR
N = VD.N
HIRES = VD.HIRES
DEPTH_TOL = VD.DEPTH_TOL

# 測試向量方向(未正規化亦可——投影排序對正縮放不變;gen 內部會正規化)。
# 取涵蓋軸向(0/180°,對 lr/rl 特例)、垂直(90°)、對角(45/135°)的代表集。
ANGLES = [0.0, 45.0, 90.0, 135.0, 180.0, 225.0, 270.0, 315.0]
AXIS_EQUIV = {(1.0, 0.0): "lr", (-1.0, 0.0): "rl"}   # 軸向名鍵 = 投影特例
DIAG = (1.0, 1.0)                                     # 45° 對角(J-5 四名鍵到不了)
NAMED = ["lr", "rl", "co", "oc"]


def _vec(deg):
    r = math.radians(deg)
    return (math.cos(r), math.sin(r))


def _proj_key(bone, xy, cx, cy, ux, uy):
    x, y = xy[bone]
    return (x - cx) * ux + (y - cy) * uy


def _peak_order(an, order):
    """件按實測峰時刻排序(tie-break 件序 index,確定性)。"""
    bones = [b for b in order if b in an.get("bones", {})]
    pt = {b: VD.peak_time(an, b) for b in bones}
    return tuple(sorted(bones, key=lambda b: (pt[b], order.index(b))))


def _proj_order(order, xy, cx, cy, ux, uy):
    return tuple(sorted(order, key=lambda b: (_proj_key(b, xy, cx, cy, ux, uy), order.index(b))))


def _radial_order(order, xy, cx, cy, sign):
    return tuple(sorted(order, key=lambda b: (sign * math.hypot(xy[b][0] - cx, xy[b][1] - cy), order.index(b))))


def run():
    skel = VD._skeleton()
    sb = VD._storyboard(GENRE)
    order = VD._part_order(sb)
    cx, cy = VD._canvas_center(skel)
    xy = VD._bone_xy(skel)
    gains = TV.gains_for(GENRE)
    rip = TV.cascade_ripples_for(GENRE)
    span = TV.cascade_span_for(GENRE)

    base = G.build_animations(skel, sb)                                   # cascade_dir=None(件序)
    vecs = [_vec(a) for a in ANGLES]
    by_vec = {a: G.build_animations(skel, sb, cascade_dir=v) for a, v in zip(ANGLES, vecs)}
    by_named = {d: G.build_animations(skel, sb, cascade_dir=d) for d in NAMED}
    cbeats = VD._cascade_beats(base)
    main_beats = VD._main_beats(base)
    R = {}

    # ---- V1 present + axis special-case ----
    v1 = {"missing": [], "not_finite": [], "no_bones": [], "axis_ne_named": [], "noncascade_changed": []}
    for a in ANGLES:
        for cb in cbeats:
            an = by_vec[a].get(cb)
            if an is None:
                v1["missing"].append("{}:{}".format(a, cb)); continue
            if not SA.all_finite(an):
                v1["not_finite"].append("{}:{}".format(a, cb))
            if not an.get("bones"):
                v1["no_bones"].append("{}:{}".format(a, cb))
    # 軸向向量 == 對應名鍵(逐位元)→ 證 lr/rl 是投影特例
    for vec, named in AXIS_EQUIV.items():
        av = G.build_animations(skel, sb, cascade_dir=vec)
        an = G.build_animations(skel, sb, cascade_dir=named)
        for cb in cbeats:
            if json.dumps(av[cb], sort_keys=True) != json.dumps(an[cb], sort_keys=True):
                v1["axis_ne_named"].append("{}!={}:{}".format(vec, named, cb))
    # 非 cascade 主秀 beat 不受向量方向影響
    for a in ANGLES:
        for beat, cat in main_beats.items():
            if cat == "cascade":
                continue
            if json.dumps(by_vec[a].get(beat), sort_keys=True) != json.dumps(base.get(beat), sort_keys=True):
                v1["noncascade_changed"].append("{}:{}".format(a, beat))
    R["V1_present_axis_special_case"] = {"angles": ANGLES, "axis_equiv": {str(k): v for k, v in AXIS_EQUIV.items()},
                                         **v1, "pass": bool(cbeats) and not any(v1[k] for k in v1)}

    # ---- V2 projection ordering (crux) ----
    v2 = {"detail": {}, "fail": []}
    for a, v in zip(ANGLES, vecs):
        ux, uy = v
        for cb in cbeats:
            an = by_vec[a][cb]
            bones = [b for b in order if b in an.get("bones", {})]
            proj_sorted = sorted(bones, key=lambda b: (_proj_key(b, xy, cx, cy, ux, uy), order.index(b)))
            pts = [VD.peak_time(an, b) for b in proj_sorted]
            mono = is_strictly_increasing(pts)
            v2["detail"]["{}:{}".format(a, cb)] = {
                "proj_sorted": proj_sorted,
                "peak_times_in_proj_order": [round(x, 3) for x in pts],
                "monotone_in_projection": mono}
            if not mono:
                v2["fail"].append("{}:{}".format(a, cb))
    R["V2_projection_ordering"] = {**v2, "pass": bool(cbeats) and not v2["fail"]}

    # ---- V3 diagonal new + radial boundary (crux) ----
    # (a) 45° 對角峰序 ≠ 四名鍵峰序 且 ≠件序
    diag = G.build_animations(skel, sb, cascade_dir=DIAG)
    a3 = {"detail": {}, "diag_collision": []}
    for cb in cbeats:
        diag_peak = _peak_order(diag[cb], order)
        named_peak = {d: _peak_order(by_named[d][cb], order) for d in NAMED}
        collide = [d for d in NAMED if named_peak[d] == diag_peak]
        same_as_partorder = (diag_peak == tuple(b for b in order if b in diag[cb].get("bones", {})))
        a3["detail"][cb] = {"diag_peak_order": list(diag_peak),
                            "named_peak_orders": {d: list(v) for d, v in named_peak.items()},
                            "collides_with": collide, "same_as_partorder": same_as_partorder}
        if collide or same_as_partorder:
            a3["diag_collision"].append(cb)
    # (b) 密格掃 360° 的投影排序集合;徑向 co/oc 與件序**不在**其中;對角**在**其中且 ≠ 兩軸向序
    proj_set = set(_proj_order(order, xy, cx, cy, *_vec(d)) for d in range(0, 360))
    co_ord = _radial_order(order, xy, cx, cy, 1)
    oc_ord = _radial_order(order, xy, cx, cy, -1)
    part_ord = tuple(order)
    diag_proj = _proj_order(order, xy, cx, cy, *DIAG)
    lr_proj = _proj_order(order, xy, cx, cy, 1.0, 0.0)
    rl_proj = _proj_order(order, xy, cx, cy, -1.0, 0.0)
    boundary = {
        "num_distinct_projection_orders": len(proj_set),
        "co_is_projection": co_ord in proj_set,         # 期望 False(徑向非投影)
        "oc_is_projection": oc_ord in proj_set,         # 期望 False
        "partorder_is_projection": part_ord in proj_set,  # 期望 False
        "diag_is_projection": diag_proj in proj_set,    # 期望 True
        "diag_differs_from_axes": diag_proj != lr_proj and diag_proj != rl_proj,  # 期望 True
    }
    boundary_pass = (not boundary["co_is_projection"] and not boundary["oc_is_projection"]
                     and not boundary["partorder_is_projection"] and boundary["diag_is_projection"]
                     and boundary["diag_differs_from_axes"])
    R["V3_diagonal_new_radial_boundary"] = {
        "diag_vector": DIAG, "detail": a3["detail"], "diag_collision": a3["diag_collision"],
        "radial_boundary": boundary,
        "pass": bool(cbeats) and not a3["diag_collision"] and boundary_pass}

    # ---- V4 still a cascade + interface ----
    v4 = {"weak_spread": [], "bad_interface": [], "detail": {}}
    for a, v in zip(ANGLES, vecs):
        ux, uy = v
        for cb in cbeats:
            an = by_vec[a][cb]
            bones = [b for b in order if b in an.get("bones", {})]
            proj_sorted = sorted(bones, key=lambda b: (_proj_key(b, xy, cx, cy, ux, uy), order.index(b)))
            pts = [VD.peak_time(an, b) for b in proj_sorted]
            sp = cascade_spread(pts)
            v4["detail"]["{}:{}".format(a, cb)] = {"spread": round(sp, 3)}
            if sp < SPREAD_FLOOR:
                v4["weak_spread"].append("{}:{}".format(a, cb))
            dur = SA.duration(an)
            b0 = SA.sample(an, 0.0)["bones"]; bE = SA.sample(an, dur)["bones"]
            s0 = SA.sample(an, 0.0)["slots"]; sE = SA.sample(an, dur)["slots"]
            iface = (all(VD._is_ident(vv) for vv in b0.values()) and all(VD._is_ident(vv) for vv in bE.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in s0.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in sE.values()))
            if not iface:
                v4["bad_interface"].append("{}:{}".format(a, cb))
    R["V4_signature_interface"] = {"weak_spread": v4["weak_spread"], "bad_interface": v4["bad_interface"],
                                   "detail": v4["detail"],
                                   "pass": not v4["weak_spread"] and not v4["bad_interface"]}

    # ---- V5 orthogonality ----
    # (a) dir ⟂ 深度:同件峰 overshoot 在所有向量方向下==base
    depth_const = True
    depth_detail = {}
    for cb in cbeats:
        bones = [b for b in order if b in base[cb].get("bones", {})]
        for b in bones:
            dvals = [round(VD.scale_overshoot_of(by_vec[a][cb], b), 6) for a in ANGLES]
            dvals.append(round(VD.scale_overshoot_of(base[cb], b), 6))
            depth_detail["{}:{}".format(cb, b)] = dvals
            if max(dvals) - min(dvals) > DEPTH_TOL:
                depth_const = False
    # (b) dir ⟂ span:帶 span 時各檔位跨件散佈在所有向量方向下==(== 名鍵一致)
    span_const = True
    span_detail = {}
    spread_by_dir = {}
    for a, v in zip(ANGLES, vecs):
        sp_run = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_span=span, cascade_dir=v)
        ux, uy = v
        for cb in cbeats:
            for t in TIERS:
                an = sp_run["{}__{}".format(cb, t)]
                bones = [b for b in order if b in an.get("bones", {})]
                pts = [VD.peak_time(an, b) for b in bones]
                spread_by_dir.setdefault("{}__{}".format(cb, t), {})[a] = round(cascade_spread(pts), 4)
    for key, dmap in spread_by_dir.items():
        vals = list(dmap.values())
        span_detail[key] = dmap
        if max(vals) - min(vals) > 2.0 / N:
            span_const = False
    # (c) dir ⟂ nrip:帶 ripples 時各件 pop 次數==nrip
    nrip_ok = True
    nrip_detail = {}
    for a, v in zip(ANGLES, vecs):
        full = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip, cascade_dir=v)
        for cb in cbeats:
            for t in TIERS:
                an = full["{}__{}".format(cb, t)]
                bones = an.get("bones", {})
                cnts = [VD.peak_times_count(an, b) for b in bones]
                ok = bool(cnts) and all(c == rip[t] for c in cnts)
                nrip_detail["{}:{}__{}".format(a, cb, t)] = {"nrip": rip[t], "counts": cnts, "ok": ok}
                if not ok:
                    nrip_ok = False
    R["V5_orthogonality"] = {"a_depth_const_over_dir": depth_const, "a_detail": depth_detail,
                             "b_span_spread_const_over_dir": span_const, "b_detail": span_detail,
                             "c_nrip_intact_all_dirs": nrip_ok, "c_detail": nrip_detail,
                             "pass": depth_const and span_const and nrip_ok}

    # ---- V6 neg-control ----
    v6 = {}
    # (a) crux 反向:θ 峰序 == (θ+180°) 峰序逆序
    rev = {"detail": {}, "fail": []}
    for base_deg in [0.0, 45.0, 90.0, 135.0]:
        fwd = G.build_animations(skel, sb, cascade_dir=_vec(base_deg))
        bwd = G.build_animations(skel, sb, cascade_dir=_vec(base_deg + 180.0))
        for cb in cbeats:
            of = _peak_order(fwd[cb], order)
            ob = _peak_order(bwd[cb], order)
            reversed_ok = (of == tuple(reversed(ob)))
            rev["detail"]["{}:{}".format(base_deg, cb)] = {
                "fwd": list(of), "bwd": list(ob), "is_reverse": reversed_ok}
            if not reversed_ok:
                rev["fail"].append("{}:{}".format(base_deg, cb))
    v6["a_opposite_reverses_wave"] = {"detail": rev["detail"], "pass": bool(cbeats) and not rev["fail"]}
    # (b) 零向量 → ValueError
    zraised = False
    try:
        G.build_animations(skel, sb, cascade_dir=(0.0, 0.0))
    except ValueError:
        zraised = True
    v6["b_zero_vector_rejected"] = {"raised_valueerror": zraised, "pass": zraised}
    # (c) parse_cascade_dir 守衛:亂字串 + 殘缺向量
    pc = {"bad_str": False, "bad_vec": False}
    try:
        G.parse_cascade_dir("zzz")
    except ValueError:
        pc["bad_str"] = True
    try:
        G.parse_cascade_dir("v1")
    except ValueError:
        pc["bad_vec"] = True
    # 同時證 parse 正常路徑:a0 ≡ lr(軸向角度特例)、v1,1 → (1,1)
    a0 = G.parse_cascade_dir("a0")
    parse_a0_is_lr = (isinstance(a0, tuple) and abs(a0[0] - 1.0) <= 1e-9 and abs(a0[1]) <= 1e-9)
    v6["c_parse_guard"] = {**pc, "parse_a0_is_axis": parse_a0_is_lr,
                           "pass": pc["bad_str"] and pc["bad_vec"] and parse_a0_is_lr}
    # (d) 向量方向只作用 cascade:非 cascade 主秀 beat 逐位元同 base
    leak = []
    for a in ANGLES:
        for beat, cat in main_beats.items():
            if cat == "cascade":
                continue
            if json.dumps(by_vec[a].get(beat), sort_keys=True) != json.dumps(base.get(beat), sort_keys=True):
                leak.append("{}:{}".format(a, beat))
    v6["d_dir_isolated_to_cascade"] = {"leaked": leak, "pass": not leak}
    R["V6_neg_control"] = {**v6, "pass": all(v["pass"] for v in v6.values())}

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
        for k in ["V1_present_axis_special_case", "V2_projection_ordering", "V3_diagonal_new_radial_boundary",
                  "V4_signature_interface", "V5_orthogonality", "V6_neg_control"]:
            print("{:34s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V2 peak times in projection order (per angle):")
        for key, d in R["V2_projection_ordering"]["detail"].items():
            print("  {:14s} {} mono={}".format(key, d["peak_times_in_proj_order"], d["monotone_in_projection"]))
        b = R["V3_diagonal_new_radial_boundary"]["radial_boundary"]
        print("V3 radial boundary: #proj_orders={} co_is_proj={} oc_is_proj={} diag_is_proj={} diag!=axes={}".format(
            b["num_distinct_projection_orders"], b["co_is_projection"], b["oc_is_projection"],
            b["diag_is_projection"], b["diag_differs_from_axes"]))
        for cb, d in R["V3_diagonal_new_radial_boundary"]["detail"].items():
            print("  {:10s} diag_peak={} collides={}".format(
                cb, [x.replace("b_", "") for x in d["diag_peak_order"]], d["collides_with"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
