#!/usr/bin/env python3
"""candidate (J-5) 自我驗收閘 — cascade 跨件波的**方向由空間位置決定**(純 CPU)。

(J-3) 讓 cascade 的**波掃次數** nrip 隨檔位遞增(拓樸軸);(J-4) 讓一道 sweep 內的**散佈幅度** span 隨檔位遞增
(時間位置的幅度軸);(J) 讓**深度**隨檔位遞增(值幅度軸)。本閘驗 (J-5) 的**第四條正交軸——相位來源**:
跨件波的**方向**由件的**空間位置**決定,而非 storyboard parts 的**列表(作者排版)順序**。

至 (J-4) 為止,各件的相位恆為件序 `pi/(nvalid−1)`(第一件最先 pop、最後一件最後)—— 波的方向等於**作者把件寫進
storyboard 的順序**,是任意/排版決定的,沒有物理意義。(J-5) 把相位的**排序鍵**換成空間座標:
  "lr" 左→右(bd.x 升序,最左件最先 pop)、"rl" 右→左、"co" 中心外擴(距畫布中心升序,最內件最先)、"oc" 外向內。
相位值仍 `rank/(nvalid−1)∈[0,1]`,**波形(SPAN/nrip/深度)分毫不動** → 只重排「哪件何時 pop」。

**crux(J-5 的 honest distinction,本閘核心鑑別點)**:這**不是**新的幅度/段數軸,而是**同一道波的方向來源**從件序
換成幾何。要證「真的由空間決定」,必須證在 **部件列表順序 ≠ 空間順序** 的真實資產上,峰時刻的排序**跟著空間走、
不跟件序走**。robot fixture 恰好件序 `[光暈,右手,頭,身體,左手]`(x=359,320,361,394,558)**不是** x 排序
(x 最小的右手排在件序第 2),故 "lr" 下右手(件序 index 1)會比光暈(件序 index 0)**更早** pop —— 件序相位下不可能
發生。Z5(b) 固化此鑑別:lr 的峰序 == x 排序 ≠ 件序。

閘從**先驗庫**經 `analyze_target`(build_storyboard)→ **真實 build_spine robot 骨架** →
`build_animations(..., cascade_dir=...)` 端到端量,與 (J)/(J-2)/(J-3)/(J-4) 閘同一 fixture。

  Z1 present + backward-compat : 每方向皆產每個 cascade beat 且 finite/有 bone;`cascade_dir="po"`(顯式件序)逐位元
                                同 `cascade_dir=None`(預設件序);非 cascade 主秀 beat 不受方向影響(逐位元不變)。
  Z2 spatial ordering (crux)  : 每方向(lr/rl/co/oc)下,各件峰時刻依**該方向的空間排序鍵**嚴格遞增
                                (lr→x 升序、rl→x 降序、co→徑向升序、oc→徑向降序)= 峰時刻由空間位置單調決定。
  Z3 still a cascade + iface   : 每方向仍是**一道有序跨件波**(沿其空間排序的峰時刻散佈 ≥ 門檻);每件首尾 setup
                                identity + 特效 slot alpha 首尾=1(可插 Loop 間)。
  Z4 orthogonality            : (a) dir ⟂ 深度:同一件的 scale 峰 overshoot 在所有方向下**相同**(只重排時刻,不動值);
                                (b) dir ⟂ nrip:帶 tier_cascade_ripples 時,各件 pop 次數==nrip 在所有方向下皆成立;
                                (c) dir ⟂ span:帶 tier_cascade_span 時,各檔位跨件散佈(max−min)在所有方向下**相同**
                                   (相位集合 {0..1} 只被排列 → min/max 不變 → 散佈==span,與方向無關)。
  Z5 neg-control              : (a) `po`(顯式件序)逐位元==`None`(控制組重現件序);
                                (b) **crux discriminator**:lr 下各件峰時刻的排序(argsort over parts)== 件按 x 的排序
                                   **且 ≠ 件序**(identity);具體:x 最小的件(非件序第一件)最先 pop → 證相位來源是空間、非件序;
                                (c) 方向只作用 cascade:非 cascade 主秀 beat 在任一方向下逐位元同 None(不外洩);
                                (d) 未知方向字串 → build_animations 拋 ValueError(輸入守衛)。

用法:
  python3 validate_cascade_dir.py            # 摘要
  python3 validate_cascade_dir.py --json     # 完整 JSON
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import beat_templates as BT
from analyze_target import analyze
import tier_variants as TV
from validate_cascade import series, is_strictly_increasing, cascade_spread

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
DIRS = ["lr", "rl", "co", "oc"]
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
IMPACT = BT.IMPACT_PROM          # 1.10:pop 峰門檻
SPREAD_FLOOR = 0.30              # 有序跨件波的最小散佈
N = 240


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/cascade_dir_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _part_order(sb):
    return ["b_" + G.safe(p["part"]) for p in sb["beats"][0]["parts"]]


def _canvas_center(skel):
    return skel["skeleton"]["width"] / 2.0, skel["skeleton"]["height"] / 2.0


def _bone_xy(skel):
    return {b["name"]: (b.get("x", 0.0), b.get("y", 0.0)) for b in skel["bones"] if b["name"] != "root"}


def _spatial_key(bone, xy, cx, cy, d):
    x, y = xy[bone]
    if d == "lr":
        return x
    if d == "rl":
        return -x
    if d == "co":
        return math.hypot(x - cx, y - cy)
    return -math.hypot(x - cx, y - cy)   # oc


def peak_time(anim, bone, n=N):
    v = series(anim, bone, n=n)
    return max(range(len(v)), key=lambda i: v[i]) / n


HIRES = 9600                     # 高解析取樣:量「深度」不受相位時移造成的離散混疊影響
DEPTH_TOL = 1e-3                 # 深度跨方向一致容忍(HIRES 下殘差 ≈3e-4 << 此 → 證混疊 artifact,非真深度變化)


def scale_overshoot_of(anim, bone, n=HIRES):
    """件 scale 峰 overshoot。以 HIRES 取樣 → argmax 極近連續峰,消除「相位時移把峰中心挪到不同 τ、
    離散幀落在距連續峰不同偏移」造成的混疊(該混疊隨 n 二次收斂 → 非真深度變化,見 knowledge 文)。"""
    return max(series(anim, bone, n=n)) - 1.0


def peak_times_count(anim, bone, n=N):
    """該 bone scaleX 的 impact 峰(局部極大 ≥ IMPACT)個數(nrip 道各一 pop)。"""
    v = series(anim, bone, n=n)
    return sum(1 for i in range(1, len(v) - 1) if v[i] >= IMPACT and v[i - 1] < v[i] >= v[i + 1])


def _cascade_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "cascade"]


def _main_beats(anims):
    return {nm: G.beat_category(nm) for nm in anims
            if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


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
    by_dir = {d: G.build_animations(skel, sb, cascade_dir=d) for d in DIRS}
    po = G.build_animations(skel, sb, cascade_dir="po")               # 顯式件序(控制組)
    cbeats = _cascade_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- Z1 present + backward-compat ----
    z1 = {"missing": [], "not_finite": [], "no_bones": [], "po_ne_none": [], "noncascade_changed": []}
    for d in DIRS:
        for cb in cbeats:
            an = by_dir[d].get(cb)
            if an is None:
                z1["missing"].append("{}:{}".format(d, cb)); continue
            if not SA.all_finite(an):
                z1["not_finite"].append("{}:{}".format(d, cb))
            if not an.get("bones"):
                z1["no_bones"].append("{}:{}".format(d, cb))
    for cb in cbeats:
        if json.dumps(po[cb], sort_keys=True) != json.dumps(base[cb], sort_keys=True):
            z1["po_ne_none"].append(cb)
    # 非 cascade 主秀 beat 不受方向影響(逐位元同 None)
    for d in DIRS:
        for beat, cat in main_beats.items():
            if cat == "cascade":
                continue
            if json.dumps(by_dir[d].get(beat), sort_keys=True) != json.dumps(base.get(beat), sort_keys=True):
                z1["noncascade_changed"].append("{}:{}".format(d, beat))
    R["Z1_present_backward_compat"] = {"cascade_beats": cbeats, "dirs": DIRS, **z1,
                                       "pass": bool(cbeats) and not any(z1[k] for k in z1)}

    # ---- Z2 spatial ordering (crux) ----
    z2 = {"detail": {}, "fail": []}
    for d in DIRS:
        for cb in cbeats:
            an = by_dir[d][cb]
            bones = [b for b in order if b in an.get("bones", {})]
            # 依該方向的空間鍵排序 bones(tie-break 件序 index 保確定性)
            spatial_sorted = sorted(bones, key=lambda b: (_spatial_key(b, xy, cx, cy, d), order.index(b)))
            pts_spatial = [peak_time(an, b) for b in spatial_sorted]
            mono = is_strictly_increasing(pts_spatial)
            z2["detail"]["{}:{}".format(d, cb)] = {
                "spatial_sorted": spatial_sorted,
                "peak_times_in_spatial_order": [round(x, 3) for x in pts_spatial],
                "monotone_in_space": mono}
            if not mono:
                z2["fail"].append("{}:{}".format(d, cb))
    R["Z2_spatial_ordering"] = {**z2, "pass": bool(cbeats) and not z2["fail"]}

    # ---- Z3 still a cascade + interface ----
    z3 = {"weak_spread": [], "bad_interface": [], "detail": {}}
    for d in DIRS:
        for cb in cbeats:
            an = by_dir[d][cb]
            bones = [b for b in order if b in an.get("bones", {})]
            spatial_sorted = sorted(bones, key=lambda b: (_spatial_key(b, xy, cx, cy, d), order.index(b)))
            pts = [peak_time(an, b) for b in spatial_sorted]
            sp = cascade_spread(pts)
            z3["detail"]["{}:{}".format(d, cb)] = {"spread": round(sp, 3)}
            if sp < SPREAD_FLOOR:
                z3["weak_spread"].append("{}:{}".format(d, cb))
            dur = SA.duration(an)
            b0 = SA.sample(an, 0.0)["bones"]; bE = SA.sample(an, dur)["bones"]
            s0 = SA.sample(an, 0.0)["slots"]; sE = SA.sample(an, dur)["slots"]
            iface = (all(_is_ident(v) for v in b0.values()) and all(_is_ident(v) for v in bE.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in s0.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in sE.values()))
            if not iface:
                z3["bad_interface"].append("{}:{}".format(d, cb))
    R["Z3_signature_interface"] = {"weak_spread": z3["weak_spread"], "bad_interface": z3["bad_interface"],
                                   "detail": z3["detail"],
                                   "pass": not z3["weak_spread"] and not z3["bad_interface"]}

    # ---- Z4 orthogonality ----
    # (a) dir ⟂ 深度:同一件峰 overshoot 在所有方向下相同(只重排時刻)
    depth_const = True
    depth_detail = {}
    for cb in cbeats:
        bones = [b for b in order if b in base[cb].get("bones", {})]
        for b in bones:
            dvals = [round(scale_overshoot_of(by_dir[d][cb], b), 6) for d in DIRS]
            dvals.append(round(scale_overshoot_of(base[cb], b), 6))
            depth_detail["{}:{}".format(cb, b)] = dvals
            if max(dvals) - min(dvals) > DEPTH_TOL:
                depth_const = False
    # (b) dir ⟂ nrip:帶 ripples 時各件 pop 次數==nrip 在所有方向成立
    nrip_ok = True
    nrip_detail = {}
    for d in DIRS:
        full = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip, cascade_dir=d)
        for cb in cbeats:
            for t in TIERS:
                an = full["{}__{}".format(cb, t)]
                bones = an.get("bones", {})
                cnts = [peak_times_count(an, b) for b in bones]
                ok = bool(cnts) and all(c == rip[t] for c in cnts)
                nrip_detail["{}:{}__{}".format(d, cb, t)] = {"nrip": rip[t], "counts": cnts, "ok": ok}
                if not ok:
                    nrip_ok = False
    # (c) dir ⟂ span:帶 span 時各檔位跨件散佈在所有方向下相同(==span)
    span_const = True
    span_detail = {}
    spread_by_dir = {}
    for d in DIRS:
        sp_run = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_span=span, cascade_dir=d)
        for cb in cbeats:
            for t in TIERS:
                an = sp_run["{}__{}".format(cb, t)]
                bones = [b for b in order if b in an.get("bones", {})]
                pts = [peak_time(an, b) for b in bones]
                spread_by_dir.setdefault("{}__{}".format(cb, t), {})[d] = round(cascade_spread(pts), 4)
    for key, dmap in spread_by_dir.items():
        vals = list(dmap.values())
        span_detail[key] = dmap
        if max(vals) - min(vals) > 2.0 / N:
            span_const = False
    R["Z4_orthogonality"] = {"a_depth_const_over_dir": depth_const, "a_detail": depth_detail,
                             "b_nrip_intact_all_dirs": nrip_ok, "b_detail": nrip_detail,
                             "c_span_spread_const_over_dir": span_const, "c_detail": span_detail,
                             "pass": depth_const and nrip_ok and span_const}

    # ---- Z5 negative controls ----
    z5 = {}
    # (a) po == None 逐位元(控制組重現件序)
    po_eq = all(json.dumps(po[cb], sort_keys=True) == json.dumps(base[cb], sort_keys=True) for cb in cbeats)
    z5["a_po_equals_none"] = {"pass": bool(cbeats) and po_eq}
    # (b) crux discriminator:lr 峰序 == x 排序 且 ≠ 件序
    bcd = {}
    disc_ok = True
    for cb in cbeats:
        an = by_dir["lr"][cb]
        bones = [b for b in order if b in an.get("bones", {})]
        pts = {b: peak_time(an, b) for b in bones}
        order_by_peak = sorted(bones, key=lambda b: pts[b])                     # 實測:依峰時刻排序
        order_by_x = sorted(bones, key=lambda b: (xy[b][0], order.index(b)))    # 期望:依 x 排序
        part_list_order = bones                                                 # 件序(= storyboard 列表順序)
        follows_x = (order_by_peak == order_by_x)
        differs_from_partlist = (order_by_x != part_list_order)
        bcd[cb] = {"order_by_peak": order_by_peak, "order_by_x": order_by_x,
                   "part_list_order": part_list_order,
                   "peak_follows_x": follows_x, "x_order_differs_from_partlist": differs_from_partlist}
        if not (follows_x and differs_from_partlist):
            disc_ok = False
    z5["b_lr_follows_space_not_partlist"] = {"detail": bcd, "pass": bool(cbeats) and disc_ok}
    # (c) 方向只作用 cascade:非 cascade 主秀 beat 逐位元同 None
    leak = []
    for d in DIRS:
        for beat, cat in main_beats.items():
            if cat == "cascade":
                continue
            if json.dumps(by_dir[d].get(beat), sort_keys=True) != json.dumps(base.get(beat), sort_keys=True):
                leak.append("{}:{}".format(d, beat))
    z5["c_dir_isolated_to_cascade"] = {"leaked": leak, "pass": not leak}
    # (d) 未知方向 → ValueError(輸入守衛)
    raised = False
    try:
        G.build_animations(skel, sb, cascade_dir="zzz")
    except ValueError:
        raised = True
    z5["d_unknown_dir_rejected"] = {"raised_valueerror": raised, "pass": raised}
    R["Z5_neg_control"] = {**z5, "pass": all(v["pass"] for v in z5.values())}

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
        for k in ["Z1_present_backward_compat", "Z2_spatial_ordering", "Z3_signature_interface",
                  "Z4_orthogonality", "Z5_neg_control"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("Z2 cascade peak times in spatial order (per dir):")
        for key, d in R["Z2_spatial_ordering"]["detail"].items():
            print("  {:16s} {} mono={}".format(key, d["peak_times_in_spatial_order"], d["monotone_in_space"]))
        print("Z5(b) lr discriminator:")
        for cb, d in R["Z5_neg_control"]["b_lr_follows_space_not_partlist"]["detail"].items():
            print("  {:10s} peak_order==x_order {} / x_order!=partlist {}".format(
                cb, d["peak_follows_x"], d["x_order_differs_from_partlist"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
