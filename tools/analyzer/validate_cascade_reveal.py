#!/usr/bin/env python3
"""candidate (J-15) 自我驗收閘 — cascade **入場波變體**(reveal wave,純 CPU)。

至 (J-14) 為止,cascade 一直是 **pop 波**:每件恆 identity、依序 **pop**(短暫放大再回 identity),首尾皆 identity。
本閘驗 (J-15) 的**入場波**:把同一條跨件時序波的**單件運動基元**由「pop 脈衝」換成「reveal 入場」——
每件**起始 collapsed**(scale≈0 + alpha 0,隱形),依 phase **依序 burst 現身**(collapsed → 蓄勢 → overshoot
burst → 阻尼回穩 identity),現身後**保持 identity 到結尾**。這是一條與 pop **語意不同**的跨件波:pop 是「一件接一件
閃一下」(全程可見),reveal 是「一件接一件**冒出來**」(入場/揭幕);**首幀非 identity**(所有件 collapsed)是兩者的
乾淨鑑別點。入場次序沿用 cascade_dir(J-5/J-6/J-7..)決定的 phase 序(哪件何時),故與方向/散佈軸正交。

**crux(處理『多件 collapse 疊加對 argmax 的擾動』)**:reveal 的量化風險在於——若單件只是「collapsed hold → 升到
identity 後平台」,則該件 scaleX 的最大值落在**尾端 identity 平台**(整段 =1.0 的平地),`argmax` 會被平台的**第一個**
取樣點搶走、量不到真正的現身時刻 → 多件在 τ=0 的 collapsed 平台 + 尾端 identity 平台使跨件現身序**不可靠**。本設計讓
每件 burst 時有**唯一 overshoot 峰**(peak>1,現身後只回到 1.0)→ `argmax(scaleX)` 唯一落在其 burst 時刻(高於尾端
identity 平台)→ 跨件現身序以 per-bone argmax 可靠量得。R4(c) 固化此鑑別(每件全域最大 > 1.0 且落在 τ<1)。

閘從**先驗庫**經 `analyze_target`(build_storyboard)→ **真實 build_spine robot 骨架** →
`build_animations(..., cascade_reveal=...)` 端到端量,與 (J-5..J-14) cascade 閘同一 fixture。

  R1 present + backward-compat : reveal build 產每個 cascade beat 且 finite/有 bone;`cascade_reveal=False` 逐位元
                                同預設(pop,零回歸);reveal=True 下**非 cascade 主秀 beat 逐位元不變**(reveal 只作用 cascade)。
  R2 reveal ordering (crux)   : reveal 下各件 **burst 時刻**(argmax scaleX)依 **phase(件序)**嚴格遞增 = 一道有序
                                入場波;且沿 cascade_dir 的 phase 序散佈 ≥ 門檻(仍是一道跨件波)。
  R3 entrance interface(crux) : **首幀所有件 collapsed**(scaleX≈0.02 且 alpha≈0,**非 identity**)且**尾幀所有件
                                identity**(scaleX≈1 且 alpha≈1 → 入場波後可接 Loop);每件現身後**停在 identity**
                                (不回 collapse)。
  R4 reveal vs pop + neg-ctrl : (a) **crux** 同一 beat,pop 首幀 scaleX==1(identity)、reveal 首幀 scaleX≈0.02
                                (collapsed);pop 首幀 alpha==1、reveal 首幀 alpha≈0 → 乾淨分離;(b) **neg-control**
                                pop **不**滿足 reveal 的「首幀 collapsed」(證閘非恆真)、reveal **不**滿足 pop 的
                                「首幀==尾幀==identity」;(c) **crux argmax 良定義** 每件全域 max(scaleX) > 1.0+MARGIN
                                (overshoot 高於尾端 identity 平台)且 burst 落在 τ<1(非尾端平台)→ argmax 不被平台搶走。
  R5 metric + dir + guards    : (a) burst 排序在 N 與 HIRES 取樣下一致(metric 良定義);(b) **dir discriminator**
                                reveal + cascade_dir="lr" 下 burst 序== x 排序 ≠ 件序(reveal 沿用 dir threading);
                                (c) **guards** reveal×nrip>1 → ValueError(一次性入場,nrip 須 1)、reveal×span 過大
                                (CASCADE_LEAD+span+0.24≥1)→ ValueError;(d) **端到端** build_spine --animate
                                --cascade-reveal 產可載入 spine(cascade anim finite + 首幀 collapsed)。

用法:
  python3 validate_cascade_reveal.py           # 摘要
  python3 validate_cascade_reveal.py --json     # 完整 JSON
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
COLLAPSE = BT.REVEAL_COLLAPSE        # 0.02:入場藏匿 scale
COLLAPSE_TOL = 5e-3                  # collapsed 判定容忍(round 到 4 位 → 0.02 精確)
OVERSHOOT_MARGIN = 0.05             # 全域 max 須高於 identity 平台至少此量(peak≥1.18 → 餘裕充足)
SPREAD_FLOOR = 0.30                 # 一道有序跨件波的最小散佈
N = 240
HIRES = 9600


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/cascade_reveal_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _is_ident(bd, tol=TOL):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def _part_bones(sb):
    return ["b_" + G.safe(p["part"]) for p in sb["beats"][0]["parts"]]


def _part_slots(sb):
    return [G.safe(p["part"]) for p in sb["beats"][0]["parts"]]


def _canvas_center(skel):
    return skel["skeleton"]["width"] / 2.0, skel["skeleton"]["height"] / 2.0


def _bone_xy(skel):
    return {b["name"]: (b.get("x", 0.0), b.get("y", 0.0)) for b in skel["bones"] if b["name"] != "root"}


def _cascade_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "cascade"]


def _main_beats(anims):
    return {nm: G.beat_category(nm) for nm in anims
            if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


def burst_time(anim, bone, n=HIRES):
    """件 scaleX 的 argmax 時刻(τ∈[0,1])= reveal overshoot(現身)時刻。HIRES → 近連續峰。"""
    v = series(anim, bone, "scaleX", n=n)
    return max(range(len(v)), key=lambda i: v[i]) / n


def global_max(anim, bone, n=HIRES):
    return max(series(anim, bone, "scaleX", n=n))


def first_last_scale(anim, bone):
    dur = SA.duration(anim)
    return (SA.sample(anim, 0.0)["bones"][bone]["scaleX"],
            SA.sample(anim, dur)["bones"][bone]["scaleX"])


def first_last_alpha(anim, slot):
    dur = SA.duration(anim)
    s0 = SA.sample(anim, 0.0)["slots"]; sE = SA.sample(anim, dur)["slots"]
    a0 = s0[slot]["alpha"] if slot in s0 else 1.0
    aE = sE[slot]["alpha"] if slot in sE else 1.0
    return a0, aE


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    bones_order = _part_bones(sb)
    slots_order = _part_slots(sb)
    bone2slot = {b: s for b, s in zip(bones_order, slots_order)}
    cx, cy = _canvas_center(skel)
    xy = _bone_xy(skel)
    gains = TV.gains_for(GENRE)
    rip = TV.cascade_ripples_for(GENRE)

    base = G.build_animations(skel, sb)                                  # pop(cascade_reveal=False)
    rev = G.build_animations(skel, sb, cascade_reveal=True)              # reveal
    cbeats = _cascade_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- R1 present + backward-compat ----
    r1 = {"missing": [], "not_finite": [], "no_bones": [], "false_ne_base": [], "noncascade_changed": []}
    for cb in cbeats:
        an = rev.get(cb)
        if an is None:
            r1["missing"].append(cb); continue
        if not SA.all_finite(an):
            r1["not_finite"].append(cb)
        if not an.get("bones"):
            r1["no_bones"].append(cb)
    # cascade_reveal=False 逐位元同預設(零回歸)
    rev_false = G.build_animations(skel, sb, cascade_reveal=False)
    for cb in cbeats:
        if json.dumps(rev_false[cb], sort_keys=True) != json.dumps(base[cb], sort_keys=True):
            r1["false_ne_base"].append(cb)
    # reveal=True 下非 cascade 主秀 beat 逐位元不變
    for beat, cat in main_beats.items():
        if cat == "cascade":
            continue
        if json.dumps(rev.get(beat), sort_keys=True) != json.dumps(base.get(beat), sort_keys=True):
            r1["noncascade_changed"].append(beat)
    R["R1_present_backward_compat"] = {"cascade_beats": cbeats, **r1,
                                       "pass": bool(cbeats) and not any(r1[k] for k in r1)}

    # ---- R2 reveal ordering (crux) ----
    r2 = {"detail": {}, "fail_mono": [], "weak_spread": []}
    for cb in cbeats:
        an = rev[cb]
        bones = [b for b in bones_order if b in an.get("bones", {})]
        bts = [burst_time(an, b) for b in bones]        # 件序(= default phase 序)
        mono = is_strictly_increasing(bts)
        sp = cascade_spread(bts)
        r2["detail"][cb] = {"bones": bones, "burst_times": [round(x, 3) for x in bts],
                            "monotone_in_partorder": mono, "spread": round(sp, 3)}
        if not mono:
            r2["fail_mono"].append(cb)
        if sp < SPREAD_FLOOR:
            r2["weak_spread"].append(cb)
    R["R2_reveal_ordering"] = {**r2, "pass": bool(cbeats) and not r2["fail_mono"] and not r2["weak_spread"]}

    # ---- R3 entrance interface (crux) ----
    r3 = {"bad_first": [], "bad_last": [], "recollapse": [], "detail": {}}
    for cb in cbeats:
        an = rev[cb]
        bones = [b for b in bones_order if b in an.get("bones", {})]
        for b in bones:
            s0, sE = first_last_scale(an, b)
            a0, aE = first_last_alpha(an, bone2slot[b])
            # 首幀 collapsed:scale≈COLLAPSE 且 alpha≈0(非 identity)
            if not (abs(s0 - COLLAPSE) <= COLLAPSE_TOL and a0 <= COLLAPSE_TOL):
                r3["bad_first"].append("{}:{}".format(cb, b))
            # 尾幀 identity:scale≈1 且 alpha≈1
            if not (abs(sE - 1.0) <= TOL and abs(aE - 1.0) <= TOL):
                r3["bad_last"].append("{}:{}".format(cb, b))
            # 現身後停在 identity:burst 之後(取 τ=burst+0.2 與尾端)皆 ≈1(不回 collapse)
            bt = burst_time(an, b)
            tau_after = min(1.0, bt + 0.2)
            s_after = SA.sample(an, SA.duration(an) * tau_after)["bones"][b]["scaleX"]
            if s_after < 0.9:          # 現身後不應掉回 collapsed
                r3["recollapse"].append("{}:{}".format(cb, b))
            r3["detail"]["{}:{}".format(cb, b)] = {"s0": round(s0, 4), "sE": round(sE, 4),
                                                   "a0": round(a0, 4), "aE": round(aE, 4),
                                                   "s_after_burst": round(s_after, 4)}
    R["R3_entrance_interface"] = {"bad_first": r3["bad_first"], "bad_last": r3["bad_last"],
                                  "recollapse": r3["recollapse"], "detail": r3["detail"],
                                  "pass": bool(cbeats) and not r3["bad_first"]
                                  and not r3["bad_last"] and not r3["recollapse"]}

    # ---- R4 reveal vs pop + negative control ----
    r4 = {"detail": {}}
    # (a) crux:同一 beat pop 首幀 identity vs reveal 首幀 collapsed(scale+alpha)
    clean_sep = True
    for cb in cbeats:
        bones = [b for b in bones_order if b in base[cb].get("bones", {})]
        for b in bones:
            pop0, _ = first_last_scale(base[cb], b)
            rev0, _ = first_last_scale(rev[cb], b)
            popa0, _ = first_last_alpha(base[cb], bone2slot[b])
            reva0, _ = first_last_alpha(rev[cb], bone2slot[b])
            sep = (abs(pop0 - 1.0) <= TOL and abs(rev0 - COLLAPSE) <= COLLAPSE_TOL
                   and abs(popa0 - 1.0) <= TOL and reva0 <= COLLAPSE_TOL)
            r4["detail"]["{}:{}".format(cb, b)] = {"pop_s0": round(pop0, 4), "rev_s0": round(rev0, 4),
                                                   "pop_a0": round(popa0, 4), "rev_a0": round(reva0, 4)}
            if not sep:
                clean_sep = False
    # (b) neg-control:pop 不滿足 reveal 首幀 collapsed(否則閘恆真);reveal 不滿足 pop 首==尾==identity
    pop_is_collapsed = False     # 期望 False(pop 首幀非 collapsed)
    rev_is_popiface = False      # 期望 False(reveal 首幀非 identity)
    for cb in cbeats:
        bones = [b for b in bones_order if b in base[cb].get("bones", {})]
        for b in bones:
            pop0, popE = first_last_scale(base[cb], b)
            rev0, revE = first_last_scale(rev[cb], b)
            if abs(pop0 - COLLAPSE) <= COLLAPSE_TOL:
                pop_is_collapsed = True
            if abs(rev0 - 1.0) <= TOL and abs(revE - 1.0) <= TOL:
                rev_is_popiface = True
    neg_ok = (not pop_is_collapsed) and (not rev_is_popiface)
    # (c) crux argmax 良定義:每件全域 max > 1.0+MARGIN 且 burst 落在 τ<1(非尾端平台)
    argmax_ok = True
    argmax_detail = {}
    for cb in cbeats:
        bones = [b for b in bones_order if b in rev[cb].get("bones", {})]
        for b in bones:
            gm = global_max(rev[cb], b)
            bt = burst_time(rev[cb], b)
            ok = (gm > 1.0 + OVERSHOOT_MARGIN) and (bt < 1.0 - 1e-6)
            argmax_detail["{}:{}".format(cb, b)] = {"global_max": round(gm, 4), "burst_tau": round(bt, 4), "ok": ok}
            if not ok:
                argmax_ok = False
    R["R4_reveal_vs_pop"] = {"a_clean_separation": clean_sep, "a_detail": r4["detail"],
                             "b_pop_not_collapsed": not pop_is_collapsed,
                             "b_reveal_not_popiface": not rev_is_popiface, "b_neg_ok": neg_ok,
                             "c_argmax_welldefined": argmax_ok, "c_detail": argmax_detail,
                             "pass": clean_sep and neg_ok and argmax_ok}

    # ---- R5 metric + dir + guards ----
    r5 = {}
    # (a) burst 排序在 N 與 HIRES 一致(metric 良定義)
    order_stable = True
    for cb in cbeats:
        an = rev[cb]
        bones = [b for b in bones_order if b in an.get("bones", {})]
        o_hi = sorted(bones, key=lambda b: burst_time(an, b, n=HIRES))
        o_lo = sorted(bones, key=lambda b: burst_time(an, b, n=N))
        if o_hi != o_lo:
            order_stable = False
    r5["a_metric_stable"] = {"pass": order_stable}
    # (b) dir discriminator:reveal + lr → burst 序 == x 排序 ≠ 件序
    rev_lr = G.build_animations(skel, sb, cascade_reveal=True, cascade_dir="lr")
    disc_ok = True
    bcd = {}
    for cb in cbeats:
        an = rev_lr[cb]
        bones = [b for b in bones_order if b in an.get("bones", {})]
        order_by_burst = sorted(bones, key=lambda b: burst_time(an, b))
        order_by_x = sorted(bones, key=lambda b: (xy[b][0], bones_order.index(b)))
        part_list_order = bones
        follows_x = (order_by_burst == order_by_x)
        differs = (order_by_x != part_list_order)
        bcd[cb] = {"order_by_burst": order_by_burst, "order_by_x": order_by_x,
                   "part_list_order": part_list_order, "burst_follows_x": follows_x,
                   "x_differs_from_partlist": differs}
        if not (follows_x and differs):
            disc_ok = False
    r5["b_dir_discriminator"] = {"detail": bcd, "pass": bool(cbeats) and disc_ok}
    # (c) guards:reveal×nrip>1 → ValueError;reveal×span 過大 → ValueError;生成器直呼守衛
    g_nrip = g_span = g_bt_nrip = g_bt_span = False
    try:
        G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip, cascade_reveal=True)
    except ValueError:
        g_nrip = True
    try:
        G.build_animations(skel, sb, tier_gains=gains,
                           tier_cascade_span={t: 0.70 for t in TIERS}, cascade_reveal=True)
    except ValueError:
        g_span = True
    try:
        BT.gen_cascade("body", 1.0, (0, 0), phase=0.0, nrip=2, reveal=True)
    except ValueError:
        g_bt_nrip = True
    try:
        BT.gen_cascade("body", 1.0, (0, 0), phase=1.0, span=0.70, reveal=True)
    except ValueError:
        g_bt_span = True
    r5["c_guards"] = {"build_nrip_rejected": g_nrip, "build_span_rejected": g_span,
                      "gen_nrip_rejected": g_bt_nrip, "gen_span_rejected": g_bt_span,
                      "pass": g_nrip and g_span and g_bt_nrip and g_bt_span}
    # (d) 端到端 build_spine --animate --cascade-reveal 可載入
    import build_spine
    out = "/tmp/cascade_reveal_e2e"
    build_spine.build(_psd(), out, genre=GENRE, animate=True, cascade_reveal=True)  # 寫 skeleton.json
    e2e_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    anims = e2e_skel.get("animations", {})
    e2e_cbeats = [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "cascade"]
    e2e_ok = bool(e2e_cbeats)
    e2e_detail = {}
    for cb in e2e_cbeats:
        an = anims[cb]
        fin = SA.all_finite(an)
        bones = [b for b in bones_order if b in an.get("bones", {})]
        first_collapsed = all(abs(SA.sample(an, 0.0)["bones"][b]["scaleX"] - COLLAPSE) <= COLLAPSE_TOL
                              for b in bones) if bones else False
        e2e_detail[cb] = {"finite": fin, "first_collapsed": first_collapsed, "nbones": len(bones)}
        if not (fin and first_collapsed):
            e2e_ok = False
    r5["d_end_to_end"] = {"cascade_beats": e2e_cbeats, "detail": e2e_detail, "pass": e2e_ok}
    R["R5_metric_dir_guards"] = {**r5, "pass": all(r5[k]["pass"] for k in r5)}

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
        for k in ["R1_present_backward_compat", "R2_reveal_ordering", "R3_entrance_interface",
                  "R4_reveal_vs_pop", "R5_metric_dir_guards"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("R2 reveal burst times (part order):")
        for cb, d in R["R2_reveal_ordering"]["detail"].items():
            print("  {:10s} {} mono={} spread={}".format(cb, d["burst_times"],
                                                         d["monotone_in_partorder"], d["spread"]))
        print("R4(c) argmax well-defined (global_max / burst_tau):")
        for key, d in list(R["R4_reveal_vs_pop"]["c_detail"].items())[:6]:
            print("  {:18s} max={} tau={} ok={}".format(key, d["global_max"], d["burst_tau"], d["ok"]))
        print("R5(b) lr discriminator:")
        for cb, d in R["R5_metric_dir_guards"]["b_dir_discriminator"]["detail"].items():
            print("  {:10s} burst==x {} / x!=partlist {}".format(cb, d["burst_follows_x"],
                                                                 d["x_differs_from_partlist"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
