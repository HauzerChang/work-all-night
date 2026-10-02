#!/usr/bin/env python3
"""candidate (J-6) 自我驗收閘 — cascade 跨件波方向推廣成**任意投影方向**(純 CPU)。

(J-5) 讓 cascade 波的**相位來源**由 4 個離散空間鍵(lr/rl/co/oc)決定;本閘驗 (J-6):把方向推廣成**任意投影向量**——
cascade_dir 可為數值**角度**(度)或 2-**向量** (ux,uy),件依其中心對畫布中心的位移在該單位向量上的**投影**
`k=(x−cx)·ux+(y−cy)·uy` 升序給 rank(投影最小者先 pop,波朝該方向掃)。相位值仍 `rank/(nvalid−1)∈[0,1]`,
**波形(SPAN/nrip/深度)分毫不動** → 只重排「哪件何時 pop」(與 J-5 同機制:相位的重新指派/排列)。

**crux(J-6 的 honest distinction,本閘核心鑑別點)**:投影是**線性**方向,lr=(1,0)=0°、rl=(−1,0)=180° 為其特例
(投影加常數位移 −cx 不改排序 → 逐位元同 J-5 的 "lr"/"rl")。但**對角**方向(如 (1,1))是 4 個離散鍵**產不出**的新方向。
robot fixture 件序 `[光暈,右手,頭,身體,左手]`、x=[359,320.5,361,393.5,557.5]、y=[341.5,435,443.5,227.5,408.5]、
畫布中心 (356.5,346.5)。對角 (1,1) 的投影 (x−cx)+(y−cy) = [−2.5,52.5,101.5,−82,263] → **身體**(y 最低 → 投影最負)
**最先** pop —— 這既非 "lr"(x 最小的**右手**先)也非件序(**光暈**先)。V5(a) 固化此鑑別:對角峰序==投影序 且 ≠lr序 且 ≠件序。

閘從**先驗庫**經 `analyze_target`(build_storyboard)→ **真實 build_spine robot 骨架** →
`build_animations(..., cascade_dir=角度/向量)` 端到端量,與 (J-5) 閘同一 fixture。

  V1 present + backward-compat : 每投影方向皆產每個 cascade beat 且 finite/有 bone;向量 (1,0) 逐位元同字串 "lr"、
                                (−1,0) 同 "rl"、角度 0 同 "lr"、角度 180 同 "rl";非 cascade 主秀 beat 不受方向影響。
  V2 projection monotone(crux): 每投影方向下,各件峰時刻依**該方向投影鍵**嚴格遞增 = 峰時刻由投影位置單調決定
                                (含對角 (1,1)/(1,−1) 與角度 0/45/90/135)。
  V3 still a cascade + iface   : 每投影方向仍是一道有序跨件波(散佈 ≥ 門檻);每件首尾 setup identity + 特效 slot
                                alpha 首尾=1(可插 Loop 間)。
  V4 orthogonality            : (a) 投影方向 ⟂ 深度:同一件 scale 峰 overshoot 在所有投影方向下相同(HIRES 消混疊);
                                (b) ⟂ nrip:帶 tier_cascade_ripples 時各件 pop 次數==nrip 於所有投影方向成立;
                                (c) ⟂ span:帶 tier_cascade_span 時各檔位跨件散佈(max−min)在所有投影方向下相同==span。
  V5 neg-control              : (a) **crux discriminator**:對角 (1,1) 各件峰序==投影序 **且 ≠lr 序 且 ≠件序**
                                   (身體最先 pop:4 離散鍵產不出的新方向);
                                (b) **角度≡向量 等價 + 正規化不變**:角度 45 逐位元同向量 (1,1);向量 (3,3) 同 (1,1)
                                   (正規化);角度 0 同向量 (1,0) 同字串 "lr";
                                (c) 輸入守衛:零向量 (0,0)→ValueError、長度≠2 向量→ValueError、未知字串→ValueError。

用法:
  python3 validate_cascade_dir_vec.py            # 摘要
  python3 validate_cascade_dir_vec.py --json     # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import tier_variants as TV
from validate_cascade import series, is_strictly_increasing, cascade_spread
# 重用 J-5 閘的 fixture/量測工具(同一 robot 真值管路,DRY)。
from validate_cascade_dir import (
    _skeleton, _storyboard, _part_order, _canvas_center, _bone_xy,
    peak_time, scale_overshoot_of, peak_times_count, _cascade_beats, _main_beats,
    _is_ident, GENRE, TIERS, SPREAD_FLOOR, TOL, N, DEPTH_TOL)

# J-6 測試方向:角度(度)與向量;對角為 crux(4 離散鍵產不出)。
ANGLES = [0.0, 45.0, 90.0, 135.0]
VECS = [(1.0, 1.0), (1.0, -1.0)]
DIRS = [("ang", a) for a in ANGLES] + [("vec", v) for v in VECS]


def _dkey(tag, d):
    return "{}:{}".format(tag, d)


def _unit(direction):
    """把測試方向(角度 float 或 2-向量)獨立解析成單位向量(閘自算,不依賴實作)。"""
    if isinstance(direction, (tuple, list)):
        ux, uy = float(direction[0]), float(direction[1])
        n = math.hypot(ux, uy)
        return (ux / n, uy / n)
    th = math.radians(float(direction))
    return (math.cos(th), math.sin(th))


def _proj_key(bone, xy, cx, cy, u):
    x, y = xy[bone]
    return (x - cx) * u[0] + (y - cy) * u[1]


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    order = _part_order(sb)
    cx, cy = _canvas_center(skel)
    xy = _bone_xy(skel)
    gains = TV.gains_for(GENRE)
    rip = TV.cascade_ripples_for(GENRE)
    span = TV.cascade_span_for(GENRE)

    base = G.build_animations(skel, sb)                               # cascade_dir=None(件序)
    by_dir = {_dkey(tag, d): G.build_animations(skel, sb, cascade_dir=d) for tag, d in DIRS}
    units = {_dkey(tag, d): _unit(d) for tag, d in DIRS}
    cbeats = _cascade_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- V1 present + backward-compat ----
    v1 = {"missing": [], "not_finite": [], "no_bones": [], "backcompat_fail": [], "noncascade_changed": []}
    for key in by_dir:
        for cb in cbeats:
            an = by_dir[key].get(cb)
            if an is None:
                v1["missing"].append(_dkey(key, cb)); continue
            if not SA.all_finite(an):
                v1["not_finite"].append(_dkey(key, cb))
            if not an.get("bones"):
                v1["no_bones"].append(_dkey(key, cb))
    # 向量/角度 → 對應字串特例 逐位元相同(投影家族涵蓋 lr/rl)
    equiv = [((1.0, 0.0), "lr"), ((-1.0, 0.0), "rl"), (0.0, "lr"), (180.0, "rl")]
    bc_detail = {}
    for direction, s in equiv:
        a_vec = G.build_animations(skel, sb, cascade_dir=direction)
        a_str = G.build_animations(skel, sb, cascade_dir=s)
        same = all(json.dumps(a_vec[cb], sort_keys=True) == json.dumps(a_str[cb], sort_keys=True) for cb in cbeats)
        bc_detail["{}=={}".format(direction, s)] = same
        if not same:
            v1["backcompat_fail"].append("{}=={}".format(direction, s))
    # 非 cascade 主秀 beat 不受投影方向影響
    for key in by_dir:
        for beat, cat in main_beats.items():
            if cat == "cascade":
                continue
            if json.dumps(by_dir[key].get(beat), sort_keys=True) != json.dumps(base.get(beat), sort_keys=True):
                v1["noncascade_changed"].append(_dkey(key, beat))
    R["V1_present_backward_compat"] = {"cascade_beats": cbeats, "dirs": list(by_dir.keys()),
                                       "backcompat_detail": bc_detail, **v1,
                                       "pass": bool(cbeats) and not any(v1[k] for k in v1)}

    # ---- V2 projection monotone (crux) ----
    v2 = {"detail": {}, "fail": []}
    for (tag, d) in DIRS:
        key = _dkey(tag, d)
        u = units[key]
        for cb in cbeats:
            an = by_dir[key][cb]
            bones = [b for b in order if b in an.get("bones", {})]
            proj_sorted = sorted(bones, key=lambda b: (_proj_key(b, xy, cx, cy, u), order.index(b)))
            pts = [peak_time(an, b) for b in proj_sorted]
            mono = is_strictly_increasing(pts)
            v2["detail"][_dkey(key, cb)] = {"proj_sorted": proj_sorted,
                                            "peak_times_in_proj_order": [round(x, 3) for x in pts],
                                            "monotone_in_proj": mono}
            if not mono:
                v2["fail"].append(_dkey(key, cb))
    R["V2_projection_monotone"] = {**v2, "pass": bool(cbeats) and not v2["fail"]}

    # ---- V3 still a cascade + interface ----
    v3 = {"weak_spread": [], "bad_interface": [], "detail": {}}
    for (tag, d) in DIRS:
        key = _dkey(tag, d)
        u = units[key]
        for cb in cbeats:
            an = by_dir[key][cb]
            bones = [b for b in order if b in an.get("bones", {})]
            proj_sorted = sorted(bones, key=lambda b: (_proj_key(b, xy, cx, cy, u), order.index(b)))
            pts = [peak_time(an, b) for b in proj_sorted]
            sp = cascade_spread(pts)
            v3["detail"][_dkey(key, cb)] = {"spread": round(sp, 3)}
            if sp < SPREAD_FLOOR:
                v3["weak_spread"].append(_dkey(key, cb))
            dur = SA.duration(an)
            b0 = SA.sample(an, 0.0)["bones"]; bE = SA.sample(an, dur)["bones"]
            s0 = SA.sample(an, 0.0)["slots"]; sE = SA.sample(an, dur)["slots"]
            iface = (all(_is_ident(v) for v in b0.values()) and all(_is_ident(v) for v in bE.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in s0.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in sE.values()))
            if not iface:
                v3["bad_interface"].append(_dkey(key, cb))
    R["V3_signature_interface"] = {"weak_spread": v3["weak_spread"], "bad_interface": v3["bad_interface"],
                                   "detail": v3["detail"],
                                   "pass": not v3["weak_spread"] and not v3["bad_interface"]}

    # ---- V4 orthogonality (depth / nrip / span across projection dirs) ----
    # (a) dir ⟂ 深度
    depth_const = True
    depth_detail = {}
    for cb in cbeats:
        bones = [b for b in order if b in base[cb].get("bones", {})]
        for b in bones:
            dvals = [round(scale_overshoot_of(by_dir[_dkey(tag, d)][cb], b), 6) for (tag, d) in DIRS]
            dvals.append(round(scale_overshoot_of(base[cb], b), 6))
            depth_detail[_dkey(cb, b)] = dvals
            if max(dvals) - min(dvals) > DEPTH_TOL:
                depth_const = False
    # (b) dir ⟂ nrip
    nrip_ok = True
    nrip_detail = {}
    for (tag, d) in DIRS:
        key = _dkey(tag, d)
        full = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip, cascade_dir=d)
        for cb in cbeats:
            for t in TIERS:
                an = full["{}__{}".format(cb, t)]
                cnts = [peak_times_count(an, b) for b in an.get("bones", {})]
                ok = bool(cnts) and all(c == rip[t] for c in cnts)
                nrip_detail["{}:{}__{}".format(key, cb, t)] = {"nrip": rip[t], "counts": cnts, "ok": ok}
                if not ok:
                    nrip_ok = False
    # (c) dir ⟂ span
    span_const = True
    span_detail = {}
    spread_by_dir = {}
    for (tag, d) in DIRS:
        key = _dkey(tag, d)
        sp_run = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_span=span, cascade_dir=d)
        for cb in cbeats:
            for t in TIERS:
                an = sp_run["{}__{}".format(cb, t)]
                bones = [b for b in order if b in an.get("bones", {})]
                pts = [peak_time(an, b) for b in bones]
                spread_by_dir.setdefault("{}__{}".format(cb, t), {})[key] = round(cascade_spread(pts), 4)
    for k, dmap in spread_by_dir.items():
        vals = list(dmap.values())
        span_detail[k] = dmap
        if max(vals) - min(vals) > 2.0 / N:
            span_const = False
    R["V4_orthogonality"] = {"a_depth_const_over_dir": depth_const, "a_detail": depth_detail,
                             "b_nrip_intact_all_dirs": nrip_ok, "b_detail": nrip_detail,
                             "c_span_spread_const_over_dir": span_const, "c_detail": span_detail,
                             "pass": depth_const and nrip_ok and span_const}

    # ---- V5 negative controls ----
    v5 = {}
    # (a) crux discriminator:對角 (1,1) 峰序==投影序 且 ≠lr序 且 ≠件序
    diag = (1.0, 1.0)
    u = _unit(diag)
    lr_anim = G.build_animations(skel, sb, cascade_dir="lr")
    diag_anim = G.build_animations(skel, sb, cascade_dir=diag)
    acd = {}
    disc_ok = True
    for cb in cbeats:
        bones = [b for b in order if b in diag_anim[cb].get("bones", {})]
        diag_pts = {b: peak_time(diag_anim[cb], b) for b in bones}
        lr_pts = {b: peak_time(lr_anim[cb], b) for b in bones}
        order_by_diag_peak = sorted(bones, key=lambda b: diag_pts[b])
        order_by_proj = sorted(bones, key=lambda b: (_proj_key(b, xy, cx, cy, u), order.index(b)))
        order_by_lr_peak = sorted(bones, key=lambda b: lr_pts[b])
        part_list_order = bones                              # 件序(storyboard 列表順序)
        follows_proj = (order_by_diag_peak == order_by_proj)
        differs_from_lr = (order_by_proj != order_by_lr_peak)
        differs_from_partlist = (order_by_proj != part_list_order)
        acd[cb] = {"order_by_diag_peak": order_by_diag_peak, "order_by_proj": order_by_proj,
                   "order_by_lr_peak": order_by_lr_peak, "part_list_order": part_list_order,
                   "peak_follows_proj": follows_proj, "proj_differs_from_lr": differs_from_lr,
                   "proj_differs_from_partlist": differs_from_partlist}
        if not (follows_proj and differs_from_lr and differs_from_partlist):
            disc_ok = False
    v5["a_diag_is_new_direction"] = {"detail": acd, "pass": bool(cbeats) and disc_ok}
    # (b) 角度≡向量 等價 + 正規化不變 + 角度0==向量(1,0)==字串lr
    eq_pairs = [(45.0, (1.0, 1.0)), ((3.0, 3.0), (1.0, 1.0)), (0.0, (1.0, 0.0))]
    eq_detail = {}
    eq_ok = True
    for lhs, rhs in eq_pairs:
        al = G.build_animations(skel, sb, cascade_dir=lhs)
        ar = G.build_animations(skel, sb, cascade_dir=rhs)
        same = all(json.dumps(al[cb], sort_keys=True) == json.dumps(ar[cb], sort_keys=True) for cb in cbeats)
        eq_detail["{}=={}".format(lhs, rhs)] = same
        if not same:
            eq_ok = False
    # 角度 0 亦應同字串 "lr"
    a0 = G.build_animations(skel, sb, cascade_dir=0.0)
    alr = G.build_animations(skel, sb, cascade_dir="lr")
    a0_eq_lr = all(json.dumps(a0[cb], sort_keys=True) == json.dumps(alr[cb], sort_keys=True) for cb in cbeats)
    eq_detail["0.0==lr(str)"] = a0_eq_lr
    v5["b_angle_vector_equivalence"] = {"detail": eq_detail, "pass": bool(cbeats) and eq_ok and a0_eq_lr}
    # (c) 輸入守衛:零向量 / 長度≠2 / 未知字串 → ValueError
    guards = {}
    for label, bad in [("zero_vec", (0.0, 0.0)), ("len3_vec", (1.0, 2.0, 3.0)), ("unknown_str", "zzz")]:
        raised = False
        try:
            G.build_animations(skel, sb, cascade_dir=bad)
        except ValueError:
            raised = True
        guards[label] = raised
    v5["c_input_guards"] = {"detail": guards, "pass": all(guards.values())}
    R["V5_neg_control"] = {**v5, "pass": all(v5[k]["pass"] for k in v5)}

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
        for k in ["V1_present_backward_compat", "V2_projection_monotone", "V3_signature_interface",
                  "V4_orthogonality", "V5_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("V2 cascade peak times in projection order (per dir):")
        for key, d in R["V2_projection_monotone"]["detail"].items():
            print("  {:16s} {} mono={}".format(key, d["peak_times_in_proj_order"], d["monotone_in_proj"]))
        print("V5(a) diagonal (1,1) is a new direction:")
        for cb, d in R["V5_neg_control"]["a_diag_is_new_direction"]["detail"].items():
            print("  {:10s} peak==proj {} / proj!=lr {} / proj!=partlist {}  proj_order={}".format(
                cb, d["peak_follows_proj"], d["proj_differs_from_lr"],
                d["proj_differs_from_partlist"], d["order_by_proj"]))
        print("V5(b) angle==vector equivalence:", R["V5_neg_control"]["b_angle_vector_equivalence"]["detail"])
        print("V5(c) input guards:", R["V5_neg_control"]["c_input_guards"]["detail"])
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
