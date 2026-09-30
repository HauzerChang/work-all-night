#!/usr/bin/env python3
"""candidate (J-5) 自我驗收閘 — cascade 波**方向**由空間位置決定(相位來源軸,純 CPU)。

至今 cascade 各件的相位(phase∈[0,1])一律由**件序**(storyboard `parts` 的位置)決定:`phase=pi/(n−1)`。
本閘驗 (J-5) 的新軸 —— **相位來源**改由**空間位置**排名決定波的**方向**:
  order  :件序(舊行為,預設,逐位元相容)。
  x      :件中心 bd.x 升序 → **左→右**波(x 小者先亮)。
  radial :件中心到畫布中心距離升序 → **中心外擴**波(近者先亮)。
相位仍以**排名** rank/(n−1) 均勻映到 [0,1] → span(J-4 散佈幅度)/nrip(J-3 波掃次數)/幅度(J 深度)語意不變。
這是繼結構(nrip)、幅度(span)之後,cascade 跨件時序通道的**第三條正交軸 = 方向(相位來源)**。

**crux(J-5 的 honest distinction,本閘核心鑑別點)**:相位來源只是**排名的重新指派**(permutation)——
改的是「哪一件在什麼時刻 pop」,不動「有幾道波 / 一道多開 / pop 多深」。故量測上有兩個強斷言:
  ① **真實 robot 骨架**上,cascade 件序 [光暈,右手,頭,身體,左手] 與 **x 序**不同(右手 x=320.5 < 光暈 x=359.0
     → x 模式下**右手與光暈 who-peaks-first 互換**),同一骨架、同一切,只換相位來源 → 波方向真的改變(P2/P5a)。
  ② 三種模式的**峰時刻多重集合完全相同**(只是指派給不同件)→ 證相位來源與 span/nrip/深度**正交**(P4)。
合成 3-排列 fixture(件序 / x 序 / 徑向序**兩兩皆異**)給出乾淨 crux:每種模式的峰時刻**只**在該模式自己的鍵
排序下嚴格遞增,在另兩鍵下**不**遞增(P2 正 + P5 負對照)。

閘從**先驗庫**經 `analyze_target`→**真實 build_spine robot 骨架**→`build_animations(..., cascade_phase=...)`
端到端量,與 (J)/(J-3)/(J-4) 閘同一真實 fixture;另加合成 3-排列 fixture 做乾淨鍵隔離。

  P1 present + backward-compat : `cascade_phase='order'`(預設)對 base 與**所有檔位變體**逐位元同無參數呼叫;
                                非-cascade 主秀 beat 在三種模式下逐位元不變(相位來源只作用 cascade,不外洩)。
  P2 spatial drives wave (crux): (真實骨架)x 模式峰時刻在 **bd.x 升序**下嚴格遞增、且與 order 模式相比右手/光暈
                                who-first **互換**;radial 模式峰時刻在**徑向升序**下嚴格遞增。
                                (合成 fixture)每種模式峰時刻在**該模式自己的鍵序**下嚴格遞增。
  P3 signature + interface     : 每種模式仍是**合法 cascade**(在自己的鍵序下跨件峰遞增 + 散佈 ≥ 門檻);
                                每件首尾 setup identity、特效 slot alpha 首尾=1(可插 Loop 間)。
  P4 orthogonality            : (a) 峰時刻**多重集合**在 order/x/radial 三模式下相同(相位來源=permutation,不動時刻集合);
                                (b) x 模式 + tier_cascade_span → 各檔位散佈(在 x 序量)== 宣告 span(span 軸不受相位來源干擾);
                                (c) x 模式 + tier_cascade_ripples → 每件 pop 次數==nrip(nrip 軸不受干擾);
                                (d) x 模式 + tier_gains → 峰**深度**隨檔位遞增(深度軸不受干擾)。
  P5 neg-control              : (a) 真實骨架 x 模式峰時刻在**件序**下**不**嚴格遞增(證非恆真、真的跟著 x);
                                (b) 合成 fixture 每模式在**另兩鍵**序下**不**遞增(鍵隔離);
                                (c) 退化:所有件同 x → x 模式平手以件序打破 → 逐位元==order 模式(穩定確定性);
                                (d) 非法 mode → ValueError(輸入守衛)。

用法:
  python3 validate_cascade_phase.py            # 摘要
  python3 validate_cascade_phase.py --json     # 完整 JSON
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
IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL = 1e-4
IMPACT = BT.IMPACT_PROM
SPREAD_FLOOR = 0.30
N = 240
MODES = ["order", "x", "radial"]


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/cascade_phase_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _cascade_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "cascade"]


def _main_beats(anims):
    return {nm: G.beat_category(nm) for nm in anims
            if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


def peak_time(anim, bone, n=N):
    v = series(anim, bone, n=n)
    return max(range(len(v)), key=lambda i: v[i]) / n


def peak_times(anim, bone, n=N):
    """該 bone scaleX 的所有 impact 局部極大(≥IMPACT)時刻 τ,升序(每道 sweep 一個 pop)。"""
    v = series(anim, bone, n=n)
    return [i / n for i in range(1, len(v) - 1) if v[i] >= IMPACT and v[i - 1] < v[i] >= v[i + 1]]


def scale_overshoot(anim):
    bones = anim.get("bones", {})
    return max((max(series(anim, b)) - 1.0 for b in bones), default=0.0)


def bones_in(anim, order):
    return [b for b in order if b in anim.get("bones", {})]


def peaks_by_keyorder(anim, key_order):
    """依 `key_order`(某鍵排序後的 bone 名列)回傳各件全域峰時刻 τ。"""
    return [peak_time(anim, b) for b in key_order if b in anim.get("bones", {})]


# ---------------- 真實 robot 骨架的鍵序 ----------------
def real_key_orders(skel, sb):
    """真實 cascade beat 的件 → 三種鍵序(order/x/radial)的 bone 名列。"""
    bone_of = {b["name"].removeprefix("b_"): b for b in skel["bones"] if b["name"] != "root"}
    cx = skel["skeleton"]["width"] / 2.0
    cy = skel["skeleton"]["height"] / 2.0
    cname = _cascade_beats(G.build_animations(skel, sb))[0]
    beat = next(b for b in sb["beats"] if b["beat"] == cname)
    valid = [pe for pe in beat["parts"] if bone_of.get(G.safe(pe["part"])) is not None]
    rows = []
    for pi, pe in enumerate(valid):
        bd = bone_of[G.safe(pe["part"])]
        rows.append({"bone": "b_" + G.safe(pe["part"]), "part": pe["part"], "idx": pi,
                     "x": bd["x"], "radial": math.hypot(bd["x"] - cx, bd["y"] - cy)})
    order_o = [r["bone"] for r in rows]
    order_x = [r["bone"] for r in sorted(rows, key=lambda r: (r["x"], r["idx"]))]
    order_r = [r["bone"] for r in sorted(rows, key=lambda r: (r["radial"], r["idx"]))]
    return cname, {"order": order_o, "x": order_x, "radial": order_r}, rows


# ---------------- 合成 3-排列 fixture(件序/x序/徑向序兩兩皆異) ----------------
def perm_fixture():
    """4 件,件中心經設計使 list / x / radial 三種排序**兩兩不同**,做乾淨鍵隔離 crux。

    canvas 400×400 → center (200,200)。件(list 序 A,B,C,D)座標:
      A(180,245.83) x=180 radial≈50 ; B(220,277.46) x=220 radial≈80 ;
      C(160,244.72) x=160 radial≈60 ; D(240,291.65) x=240 radial≈100
      list   : A,B,C,D              x: C,A,B,D (x 升序)         radial: A,C,B,D (徑向升序)
    三序兩兩皆異 → 每模式只在自己的鍵序遞增、另兩鍵序不遞增。"""
    roles = ["body", "head", "limb", "特效"]
    coords = [("A", 180.0, 245.83), ("B", 220.0, 277.46), ("C", 160.0, 244.72), ("D", 240.0, 291.65)]
    parts = [{"part": nm, "role": roles[i], "action": "主秀"} for i, (nm, _, _) in enumerate(coords)]
    storyboard = {"beats": [{"beat": "cascade", "desc": "合成跨件錯開波", "parts": parts}]}
    bones = [{"name": "root"}]
    for nm, x, y in coords:
        bones.append({"name": "b_" + G.safe(nm), "x": x, "y": y})
    skel = {"skeleton": {"width": 400, "height": 400}, "bones": bones}
    cx, cy = 200.0, 200.0
    rows = [{"bone": "b_" + G.safe(nm), "idx": i, "x": x, "radial": math.hypot(x - cx, y - cy)}
            for i, (nm, x, y) in enumerate(coords)]
    key_orders = {
        "order": [r["bone"] for r in rows],
        "x": [r["bone"] for r in sorted(rows, key=lambda r: (r["x"], r["idx"]))],
        "radial": [r["bone"] for r in sorted(rows, key=lambda r: (r["radial"], r["idx"]))],
    }
    return skel, storyboard, key_orders


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    gains = TV.gains_for(GENRE)
    rip = TV.cascade_ripples_for(GENRE)
    span = TV.cascade_span_for(GENRE)

    cname, rkeys, rrows = real_key_orders(skel, sb)
    anims = {m: G.build_animations(skel, sb, cascade_phase=m) for m in MODES}
    cbeats = _cascade_beats(anims["order"])
    main_beats = _main_beats(anims["order"])
    R = {}

    # ---------- P1 present + backward-compat ----------
    p1 = {"order_ne_default": [], "non_cascade_leaked": [], "variant_order_changed": []}
    default_run = G.build_animations(skel, sb)                                   # 無 cascade_phase 參數
    for cb in cbeats:
        if json.dumps(default_run[cb], sort_keys=True) != json.dumps(anims["order"][cb], sort_keys=True):
            p1["order_ne_default"].append(cb)
    # order 模式 + 檔位變體逐位元同無參數 + tier
    default_tier = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip, tier_cascade_span=span)
    order_tier = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip, tier_cascade_span=span,
                                    cascade_phase="order")
    for cb in cbeats:
        for t in TIERS:
            vk = "{}__{}".format(cb, t)
            if json.dumps(default_tier.get(vk), sort_keys=True) != json.dumps(order_tier.get(vk), sort_keys=True):
                p1["variant_order_changed"].append(vk)
    # 非-cascade 主秀 beat 在三種模式下逐位元不變(相位來源不外洩)
    for beat, cat in main_beats.items():
        if cat == "cascade":
            continue
        ref = json.dumps(anims["order"][beat], sort_keys=True)
        for m in ("x", "radial"):
            if json.dumps(anims[m][beat], sort_keys=True) != ref:
                p1["non_cascade_leaked"].append("{}:{}".format(beat, m))
    R["P1_present_backward_compat"] = {"cascade_beats": cbeats, **p1,
                                       "pass": bool(cbeats) and not any(p1[k] for k in p1)}

    # ---------- P2 spatial drives wave (crux) ----------
    p2 = {"real": {}, "perm": {}, "fail": []}
    # 真實骨架:x 在 x 序遞增 + who-first 互換 vs order;radial 在徑向序遞增
    for cb in cbeats:
        an_o = anims["order"][cb]
        an_x = anims["x"][cb]
        an_r = anims["radial"][cb]
        px_in_x = peaks_by_keyorder(an_x, rkeys["x"])
        pr_in_r = peaks_by_keyorder(an_r, rkeys["radial"])
        # who-peaks-first:order vs x 的第一件是否不同(右手 x 最小 → x 模式第一件應為右手,order 為光暈)
        first_order = min(bones_in(an_o, rkeys["order"]), key=lambda b: peak_time(an_o, b))
        first_x = min(bones_in(an_x, rkeys["x"]), key=lambda b: peak_time(an_x, b))
        swapped = first_order != first_x
        ok = is_strictly_increasing(px_in_x) and is_strictly_increasing(pr_in_r) and swapped
        p2["real"][cb] = {"x_peaks_in_xorder": [round(t, 3) for t in px_in_x],
                          "radial_peaks_in_radialorder": [round(t, 3) for t in pr_in_r],
                          "first_order": first_order, "first_x": first_x, "swapped": swapped,
                          "x_increasing": is_strictly_increasing(px_in_x),
                          "radial_increasing": is_strictly_increasing(pr_in_r)}
        if not ok:
            p2["fail"].append("real:" + cb)
    # 合成 fixture:每模式在自己的鍵序遞增
    ps, pstory, pkeys = perm_fixture()
    perm_anims = {m: G.build_animations(ps, pstory, cascade_phase=m)["cascade"] for m in MODES}
    for m in MODES:
        peaks_own = peaks_by_keyorder(perm_anims[m], pkeys[m])
        inc = is_strictly_increasing(peaks_own)
        p2["perm"][m] = {"peaks_in_own_key": [round(t, 3) for t in peaks_own], "increasing": inc}
        if not inc:
            p2["fail"].append("perm:" + m)
    R["P2_spatial_drives_wave"] = {**p2, "pass": bool(cbeats) and not p2["fail"]}

    # ---------- P3 signature + interface ----------
    p3 = {"bad_signature": [], "bad_interface": [], "detail": {}}
    for m in MODES:
        for cb in cbeats:
            an = anims[m][cb]
            pts = peaks_by_keyorder(an, rkeys[m])
            sig_ok = is_strictly_increasing(pts) and cascade_spread(pts) >= SPREAD_FLOOR
            if not sig_ok:
                p3["bad_signature"].append("{}:{}".format(cb, m))
            dur = SA.duration(an)
            b0 = SA.sample(an, 0.0)["bones"]; bE = SA.sample(an, dur)["bones"]
            s0 = SA.sample(an, 0.0)["slots"]; sE = SA.sample(an, dur)["slots"]
            iface = (all(_is_ident(v) for v in b0.values()) and all(_is_ident(v) for v in bE.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in s0.values())
                     and all(abs(s["alpha"] - 1) <= TOL for s in sE.values()))
            if not iface:
                p3["bad_interface"].append("{}:{}".format(cb, m))
            p3["detail"]["{}:{}".format(cb, m)] = {"spread": round(cascade_spread(pts), 3),
                                                   "increasing": is_strictly_increasing(pts)}
    R["P3_signature_interface"] = {**p3, "pass": not p3["bad_signature"] and not p3["bad_interface"]}

    # ---------- P4 orthogonality ----------
    p4 = {}
    # (a) 峰時刻多重集合三模式相同(相位來源=permutation)
    mset = {}
    multiset_same = True
    for cb in cbeats:
        sets = {}
        for m in MODES:
            an = anims[m][cb]
            sets[m] = sorted(round(peak_time(an, b), 4) for b in bones_in(an, rkeys["order"]))
        same = sets["order"] == sets["x"] == sets["radial"]
        mset[cb] = {"order": sets["order"], "x": sets["x"], "radial": sets["radial"], "same": same}
        multiset_same = multiset_same and same
    p4["a_peaktime_multiset_invariant"] = {"detail": mset, "pass": bool(cbeats) and multiset_same}
    # (b) x 模式 + span → 各檔位散佈(x 序量)== 宣告 span
    x_span = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_span=span, cascade_phase="x")
    span_ok = True
    span_detail = {}
    for cb in cbeats:
        spreads = []
        for t in TIERS:
            pts = peaks_by_keyorder(x_span["{}__{}".format(cb, t)], rkeys["x"])
            spreads.append(round(cascade_spread(pts), 4))
        matches = all(abs(spreads[i] - span[TIERS[i]]) <= 3.0 / N for i in range(len(TIERS)))
        mono = is_strictly_increasing(spreads)
        span_detail[cb] = {"spreads": spreads, "declared": [span[t] for t in TIERS],
                           "matches": matches, "monotone": mono}
        span_ok = span_ok and matches and mono
    p4["b_span_intact_under_x"] = {"detail": span_detail, "pass": bool(cbeats) and span_ok}
    # (c) x 模式 + nrip → 每件 pop 次數==nrip
    x_rip = G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip, cascade_phase="x")
    nrip_ok = True
    nrip_detail = {}
    for cb in cbeats:
        for t in TIERS:
            an = x_rip["{}__{}".format(cb, t)]
            cnts = [len(peak_times(an, b)) for b in an.get("bones", {})]
            good = bool(cnts) and min(cnts) == max(cnts) == rip[t]
            nrip_detail["{}__{}".format(cb, t)] = {"counts": [min(cnts) if cnts else 0, max(cnts) if cnts else 0],
                                                   "nrip": rip[t], "ok": good}
            nrip_ok = nrip_ok and good
    p4["c_nrip_intact_under_x"] = {"detail": nrip_detail, "pass": bool(cbeats) and nrip_ok}
    # (d) x 模式 + gains → 峰深度隨檔位遞增
    x_gain = G.build_animations(skel, sb, tier_gains=gains, cascade_phase="x")
    depth_ok = True
    depth_detail = {}
    for cb in cbeats:
        depths = [round(scale_overshoot(x_gain["{}__{}".format(cb, t)]), 4) for t in TIERS]
        good = is_strictly_increasing(depths)
        depth_detail[cb] = {"depths": depths, "increasing": good}
        depth_ok = depth_ok and good
    p4["d_depth_intact_under_x"] = {"detail": depth_detail, "pass": bool(cbeats) and depth_ok}
    R["P4_orthogonality"] = {**p4, "pass": all(v["pass"] for v in p4.values())}

    # ---------- P5 neg-control ----------
    p5 = {}
    # (a) 真實骨架 x 模式峰時刻在件序下 NOT 遞增(證真的跟著 x、非恆真)
    a_detail = {}
    a_ok = True
    for cb in cbeats:
        pts_listorder = peaks_by_keyorder(anims["x"][cb], rkeys["order"])
        not_inc = not is_strictly_increasing(pts_listorder)
        a_detail[cb] = {"x_peaks_in_listorder": [round(t, 3) for t in pts_listorder], "not_increasing": not_inc}
        a_ok = a_ok and not_inc
    p5["a_xmode_not_monotone_in_listorder"] = {"detail": a_detail, "pass": bool(cbeats) and a_ok}
    # (b) 合成 fixture:每模式在**另兩鍵**序下 NOT 遞增(鍵隔離)
    b_detail = {}
    b_ok = True
    for m in MODES:
        for k in MODES:
            if k == m:
                continue
            pts = peaks_by_keyorder(perm_anims[m], pkeys[k])
            not_inc = not is_strictly_increasing(pts)
            b_detail["{}_in_{}".format(m, k)] = {"peaks": [round(t, 3) for t in pts], "not_increasing": not_inc}
            b_ok = b_ok and not_inc
    p5["b_perm_key_isolation"] = {"detail": b_detail, "pass": b_ok}
    # (c) 退化:所有件同 x → x 模式逐位元==order 模式(平手以件序打破)
    deg_bones = [{"name": "root"}]
    deg_parts = []
    for i, role in enumerate(["body", "head", "limb", "特效"]):
        nm = "P{}".format(i)
        deg_parts.append({"part": nm, "role": role, "action": "主秀"})
        deg_bones.append({"name": "b_" + G.safe(nm), "x": 200.0, "y": 100.0 + 5 * i})  # 同 x,不同 y
    deg_skel = {"skeleton": {"width": 400, "height": 400}, "bones": deg_bones}
    deg_story = {"beats": [{"beat": "cascade", "desc": "退化同x", "parts": deg_parts}]}
    deg_o = G.build_animations(deg_skel, deg_story, cascade_phase="order")["cascade"]
    deg_x = G.build_animations(deg_skel, deg_story, cascade_phase="x")["cascade"]
    deg_same = json.dumps(deg_o, sort_keys=True) == json.dumps(deg_x, sort_keys=True)
    p5["c_degenerate_equal_x_falls_back"] = {"x_byte_eq_order": deg_same, "pass": deg_same}
    # (d) 非法 mode → ValueError
    try:
        G.build_animations(skel, sb, cascade_phase="bogus")
        raised = False
    except ValueError:
        raised = True
    except Exception:
        raised = False
    p5["d_invalid_mode_guard"] = {"valueerror_raised": raised, "pass": raised}
    R["P5_neg_control"] = {**p5, "pass": all(v["pass"] for v in p5.values())}

    R["OVERALL_PASS"] = all(R[k]["pass"] for k in R)
    R["_real_rows"] = [{"part": r["part"], "idx": r["idx"], "x": round(r["x"], 1),
                        "radial": round(r["radial"], 1)} for r in rrows]
    return R


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    R = run()
    if a.json:
        print(json.dumps(R, ensure_ascii=False, indent=2))
    else:
        for k in ["P1_present_backward_compat", "P2_spatial_drives_wave", "P3_signature_interface",
                  "P4_orthogonality", "P5_neg_control"]:
            print("{:32s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("real cascade parts (list idx / x / radial):")
        for r in R["_real_rows"]:
            print("  idx={idx} {part:8s} x={x} radial={radial}".format(**r))
        print("P2 real x-mode who-first swap:")
        for cb, d in R["P2_spatial_drives_wave"]["real"].items():
            print("  {:10s} order_first={} x_first={} swapped={}".format(cb, d["first_order"], d["first_x"], d["swapped"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
