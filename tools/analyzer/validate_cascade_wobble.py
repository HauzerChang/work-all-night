#!/usr/bin/env python3
"""candidate (J-15c) 自我驗收閘 — cascade **晃動波變體**(wobble wave,純 CPU)。

至 (J-15) 為止,cascade 的**單件運動基元**有兩種:**pop**(scale 脈衝,J-5..J-14)與 **reveal**(scale+alpha
入場,J-15)。兩者都走 **scale 通道**(pop 另有 limb/特效 的 rotate/color)。本閘驗 (J-15c) 的**晃動波**:把
同一條跨件時序波的單件運動基元換成 **`gen_wobble` 的純 shearX 阻尼振盪** —— 每件 shearX 自 identity(0)起,
依 phase **依序晃起**(爆出一串遞減交替的 shearX 極值:A→−rA→+r²A→−r³A),再回穩到 0。

**為何有價值(不是又一個 geo 方向 source)**:J-5..J-14 十個候選全在「波方向/散佈/段數」軸(哪件何時),
J-15 reveal 是第一個動「單件運動基元」(每件做什麼)。J-15c 是**第三個**單件運動基元,且是**第一個把
`shear` 通道錯開成跨件波**的 cascade —— 前面所有 cascade(pop/reveal)皆 scale/rotate/color 通道,shear 從未
進過跨件波。這證實 J-15 的「跨件時序軸 × 單件運動基元軸」兩正交軸**可組任意通道的運動基元**(scale→shear)。

**crux(跨件晃起序可量)**:每件 shearX 的**首個極值**(幅度 A,阻尼下最大)唯一落在其晃起中心
c=CASCADE_LEAD+phase*SPAN → per-bone `argmax(|shearX|)` 可靠量得跨件晃起序(後續極值阻尼遞減,不搶首極值)。
與 pop/reveal 的乾淨鑑別:① 單件運動基元走 **shear 通道**(無 scale 脈衝);② **首尾皆 shearX=0**(兩端 identity
→ 兩端可接 Loop,同 pop;reveal 首端 collapsed 不可接)。

閘從**先驗庫**經 `analyze_target`(build_storyboard)→ **真實 build_spine robot 骨架** →
`build_animations(..., cascade_wobble=...)` 端到端量,與 (J-5..J-15) cascade 閘同一 fixture。

  W1 present + backward-compat : wobble build 產每個 cascade beat 且 finite/有 bone;`cascade_wobble=False` 逐位元
                                同預設(pop,零回歸);wobble=True 下**非 cascade 主秀 beat 逐位元不變**(wobble 只作用 cascade)。
  W2 wobble ordering (crux)   : wobble 下各件**晃起時刻**(argmax |shearX|)依 **phase(件序)**嚴格遞增 = 一道有序
                                晃動波;沿 cascade_dir 的 phase 序散佈 ≥ 門檻(仍是一道跨件波)。
  W3 shear primitive (crux)   : 每件 cascade 運動基元走 **shear 通道**(有 `shear` timeline、shearX **阻尼振盪**:
                                繞 0 變號 ≥3 且相繼極值 |值| 嚴格遞減)且**無 scale 脈衝**(scaleX 全程 identity);
                                **首尾 shearX==0**(兩端 identity → 兩端可接 Loop)。
  W4 wobble vs pop/reveal      : (a) **crux** 同一 beat,pop 走 scale(scaleX 有脈衝、shearX≡0)、wobble 走 shear
                                (shearX 有擺動、scaleX≡identity)→ 乾淨分離;(b) **neg-control** pop **不**滿足 wobble 的
                                「shearX 阻尼振盪」(證閘非恆真)、wobble **不**滿足 reveal 的「首幀 collapsed(scaleX≈0.02)」;
                                (c) **vs reveal** wobble 首幀 shearX==0 且 scaleX==identity(非 collapsed)、reveal 首幀
                                scaleX≈0.02 → 三種單件運動基元彼此乾淨分離。
  W5 metric + dir + guards    : (a) 晃起排序在 N 與 HIRES 取樣下一致(metric 良定義);(b) **dir discriminator**
                                wobble + cascade_dir="lr" 下晃起序== x 排序 ≠ 件序(wobble 沿用 dir threading);
                                (c) **guards** wobble×nrip>1 → ValueError(一次性單道波)、wobble×span 過大
                                (CASCADE_LEAD+span+0.24≥1)→ ValueError、wobble×reveal 同開 → ValueError(互斥);
                                (d) **端到端** build_spine --animate --cascade-wobble 產可載入 spine(cascade anim
                                finite + 含 shear + 首尾 shearX=0)。

用法:
  python3 validate_cascade_wobble.py           # 摘要
  python3 validate_cascade_wobble.py --json     # 完整 JSON
"""
import argparse, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import beat_templates as BT
from analyze_target import analyze
import tier_variants as TV
from validate_cascade import series, sign_changes, is_strictly_increasing, cascade_spread

PSD = "assets/robot_parts.psd"
GENRE = "slot_bigwin"
TIERS = ["Super", "Mega", "Omg", "Legend"]
TOL = 1e-4
SHEAR_DEAD = 0.5           # shearX 變號判定死區(度;首極值≥10° → 餘裕充足)
SPREAD_FLOOR = 0.30        # 一道有序跨件波的最小散佈
COLLAPSE = BT.REVEAL_COLLAPSE   # 0.02:reveal 入場藏匿 scale(W4c 對照)
COLLAPSE_TOL = 5e-3
N = 240
HIRES = 9600


def _psd():
    return PSD if os.path.exists(PSD) else os.path.join("..", "..", "assets", "robot_parts.psd")


def _skeleton():
    import build_spine
    out = "/tmp/cascade_wobble_skel"
    build_spine.build(_psd(), out, genre=GENRE, animate=False)
    return json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))


def _storyboard(genre):
    return analyze(_psd(), genre)["3_motion_storyboard"]


def _part_bones(sb):
    return ["b_" + G.safe(p["part"]) for p in sb["beats"][0]["parts"]]


def _canvas_center(skel):
    return skel["skeleton"]["width"] / 2.0, skel["skeleton"]["height"] / 2.0


def _bone_xy(skel):
    return {b["name"]: (b.get("x", 0.0), b.get("y", 0.0)) for b in skel["bones"] if b["name"] != "root"}


def _cascade_beats(anims):
    return [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "cascade"]


def _main_beats(anims):
    return {nm: G.beat_category(nm) for nm in anims
            if "__" not in nm and G.beat_category(nm) in TV.MAIN_SHOW_CATS}


def onset_time(anim, bone, n=HIRES):
    """件 shearX 的 argmax(|shearX|) 時刻(τ∈[0,1])= wobble 晃起時刻。HIRES → 近連續峰。"""
    v = series(anim, bone, "shearX", n=n)
    return max(range(len(v)), key=lambda i: abs(v[i])) / n


def shear_extrema(anim, bone):
    """直接自 bone 的 shear timeline 取非零極值(度)序列(gate-independent,不經取樣)。"""
    sh = anim.get("bones", {}).get(bone, {}).get("shear", [])
    return [kf["x"] for kf in sh if abs(kf["x"]) > SHEAR_DEAD]


def first_last_shear(anim, bone):
    dur = SA.duration(anim)
    return (SA.sample(anim, 0.0)["bones"][bone]["shearX"],
            SA.sample(anim, dur)["bones"][bone]["shearX"])


def first_last_scale(anim, bone):
    dur = SA.duration(anim)
    return (SA.sample(anim, 0.0)["bones"][bone]["scaleX"],
            SA.sample(anim, dur)["bones"][bone]["scaleX"])


def scale_identity_throughout(anim, bone, n=N):
    return all(abs(x - 1.0) <= TOL for x in series(anim, bone, "scaleX", n=n))


def is_damped_osc(extrema):
    """阻尼振盪簽章:≥4 極值、符號交替(變號 ≥3)、相繼極值 |值| 嚴格遞減。"""
    if len(extrema) < 4:
        return False
    # 符號交替
    signs = [1 if e > 0 else -1 for e in extrema]
    alt = all(signs[i] != signs[i + 1] for i in range(len(signs) - 1))
    # |值| 嚴格遞減
    mags = [abs(e) for e in extrema]
    dec = all(mags[i] > mags[i + 1] + 1e-9 for i in range(len(mags) - 1))
    return alt and dec


def run():
    skel = _skeleton()
    sb = _storyboard(GENRE)
    bones_order = _part_bones(sb)
    cx, cy = _canvas_center(skel)
    xy = _bone_xy(skel)
    gains = TV.gains_for(GENRE)
    rip = TV.cascade_ripples_for(GENRE)

    base = G.build_animations(skel, sb)                              # pop(cascade_wobble=False)
    wob = G.build_animations(skel, sb, cascade_wobble=True)          # wobble
    rev = G.build_animations(skel, sb, cascade_reveal=True)          # reveal(W4c 對照)
    cbeats = _cascade_beats(base)
    main_beats = _main_beats(base)
    R = {}

    # ---- W1 present + backward-compat ----
    r1 = {"missing": [], "not_finite": [], "no_bones": [], "false_ne_base": [], "noncascade_changed": []}
    for cb in cbeats:
        an = wob.get(cb)
        if an is None:
            r1["missing"].append(cb); continue
        if not SA.all_finite(an):
            r1["not_finite"].append(cb)
        if not an.get("bones"):
            r1["no_bones"].append(cb)
    wob_false = G.build_animations(skel, sb, cascade_wobble=False)
    for cb in cbeats:
        if json.dumps(wob_false[cb], sort_keys=True) != json.dumps(base[cb], sort_keys=True):
            r1["false_ne_base"].append(cb)
    for beat, cat in main_beats.items():
        if cat == "cascade":
            continue
        if json.dumps(wob.get(beat), sort_keys=True) != json.dumps(base.get(beat), sort_keys=True):
            r1["noncascade_changed"].append(beat)
    R["W1_present_backward_compat"] = {"cascade_beats": cbeats, **r1,
                                       "pass": bool(cbeats) and not any(r1[k] for k in r1)}

    # ---- W2 wobble ordering (crux) ----
    r2 = {"detail": {}, "fail_mono": [], "weak_spread": []}
    for cb in cbeats:
        an = wob[cb]
        bones = [b for b in bones_order if b in an.get("bones", {})]
        ots = [onset_time(an, b) for b in bones]        # 件序(= default phase 序)
        mono = is_strictly_increasing(ots)
        sp = cascade_spread(ots)
        r2["detail"][cb] = {"bones": bones, "onset_times": [round(x, 3) for x in ots],
                            "monotone_in_partorder": mono, "spread": round(sp, 3)}
        if not mono:
            r2["fail_mono"].append(cb)
        if sp < SPREAD_FLOOR:
            r2["weak_spread"].append(cb)
    R["W2_wobble_ordering"] = {**r2, "pass": bool(cbeats) and not r2["fail_mono"] and not r2["weak_spread"]}

    # ---- W3 shear primitive (crux) ----
    r3 = {"no_shear": [], "not_damped": [], "scale_pulsed": [], "bad_ends": [], "detail": {}}
    for cb in cbeats:
        an = wob[cb]
        bones = [b for b in bones_order if b in an.get("bones", {})]
        for b in bones:
            ext = shear_extrema(an, b)
            has_shear = "shear" in an["bones"][b]
            sc = sign_changes(series(an, b, "shearX"), center=0.0, dead=SHEAR_DEAD)
            damped = is_damped_osc(ext) and sc >= 3
            scale_ident = scale_identity_throughout(an, b)
            s0, sE = first_last_shear(an, b)
            ends_ident = abs(s0) <= TOL and abs(sE) <= TOL
            key = "{}:{}".format(cb, b)
            r3["detail"][key] = {"extrema": [round(e, 3) for e in ext], "sign_changes": sc,
                                 "damped": damped, "scale_identity": scale_ident,
                                 "shear0": round(s0, 4), "shearE": round(sE, 4)}
            if not has_shear:
                r3["no_shear"].append(key)
            if not damped:
                r3["not_damped"].append(key)
            if not scale_ident:
                r3["scale_pulsed"].append(key)
            if not ends_ident:
                r3["bad_ends"].append(key)
    R["W3_shear_primitive"] = {k: r3[k] for k in r3}
    R["W3_shear_primitive"]["pass"] = (bool(cbeats) and not r3["no_shear"] and not r3["not_damped"]
                                       and not r3["scale_pulsed"] and not r3["bad_ends"])

    # ---- W4 wobble vs pop/reveal + neg-control ----
    r4 = {"detail": {}}
    # (a) crux:pop 走 scale(shearX≡0)vs wobble 走 shear(scaleX≡identity)
    clean_sep = True
    for cb in cbeats:
        bones = [b for b in bones_order if b in base[cb].get("bones", {})]
        for b in bones:
            pop_shear_flat = all(abs(x) <= TOL for x in series(base[cb], b, "shearX"))
            pop_scale_pulse = max(series(base[cb], b, "scaleX")) > 1.0 + 1e-3
            wob_shear_osc = max(abs(x) for x in series(wob[cb], b, "shearX")) > 1.0
            wob_scale_flat = scale_identity_throughout(wob[cb], b)
            sep = pop_shear_flat and pop_scale_pulse and wob_shear_osc and wob_scale_flat
            r4["detail"]["{}:{}".format(cb, b)] = {"pop_shear_flat": pop_shear_flat,
                                                   "pop_scale_pulse": pop_scale_pulse,
                                                   "wob_shear_osc": wob_shear_osc,
                                                   "wob_scale_flat": wob_scale_flat}
            if not sep:
                clean_sep = False
    # (b) neg-control:pop 不滿足 wobble shearX 阻尼振盪;wobble 不滿足 reveal 首幀 collapsed
    pop_is_wobble = False      # 期望 False(pop 無 shearX 振盪)
    wob_is_reveal = False      # 期望 False(wobble 首幀非 collapsed)
    for cb in cbeats:
        bones = [b for b in bones_order if b in base[cb].get("bones", {})]
        for b in bones:
            if sign_changes(series(base[cb], b, "shearX"), center=0.0, dead=SHEAR_DEAD) >= 3:
                pop_is_wobble = True
            w0, _ = first_last_scale(wob[cb], b)
            if abs(w0 - COLLAPSE) <= COLLAPSE_TOL:
                wob_is_reveal = True
    neg_ok = (not pop_is_wobble) and (not wob_is_reveal)
    # (c) vs reveal:wobble 首幀 scaleX==identity & shearX==0;reveal 首幀 scaleX≈collapse
    vs_reveal_ok = True
    vr_detail = {}
    for cb in cbeats:
        bones = [b for b in bones_order if b in wob[cb].get("bones", {})]
        for b in bones:
            w_s0, _ = first_last_scale(wob[cb], b)
            w_sh0, _ = first_last_shear(wob[cb], b)
            r_s0, _ = first_last_scale(rev[cb], b)
            ok = (abs(w_s0 - 1.0) <= TOL and abs(w_sh0) <= TOL and abs(r_s0 - COLLAPSE) <= COLLAPSE_TOL)
            vr_detail["{}:{}".format(cb, b)] = {"wob_scale0": round(w_s0, 4), "wob_shear0": round(w_sh0, 4),
                                                "rev_scale0": round(r_s0, 4), "ok": ok}
            if not ok:
                vs_reveal_ok = False
    R["W4_wobble_vs_pop_reveal"] = {"a_clean_separation": clean_sep, "a_detail": r4["detail"],
                                    "b_pop_not_wobble": not pop_is_wobble,
                                    "b_wob_not_reveal": not wob_is_reveal, "b_neg_ok": neg_ok,
                                    "c_vs_reveal": vs_reveal_ok, "c_detail": vr_detail,
                                    "pass": clean_sep and neg_ok and vs_reveal_ok}

    # ---- W5 metric + dir + guards + e2e ----
    r5 = {}
    # (a) 晃起排序在 N 與 HIRES 一致
    order_stable = True
    for cb in cbeats:
        an = wob[cb]
        bones = [b for b in bones_order if b in an.get("bones", {})]
        o_hi = sorted(bones, key=lambda b: onset_time(an, b, n=HIRES))
        o_lo = sorted(bones, key=lambda b: onset_time(an, b, n=N))
        if o_hi != o_lo:
            order_stable = False
    r5["a_metric_stable"] = {"pass": order_stable}
    # (b) dir discriminator:wobble + lr → 晃起序 == x 排序 ≠ 件序
    wob_lr = G.build_animations(skel, sb, cascade_wobble=True, cascade_dir="lr")
    disc_ok = True
    bcd = {}
    for cb in cbeats:
        an = wob_lr[cb]
        bones = [b for b in bones_order if b in an.get("bones", {})]
        order_by_onset = sorted(bones, key=lambda b: onset_time(an, b))
        order_by_x = sorted(bones, key=lambda b: (xy[b][0], bones_order.index(b)))
        part_list_order = bones
        follows_x = (order_by_onset == order_by_x)
        differs = (order_by_x != part_list_order)
        bcd[cb] = {"order_by_onset": order_by_onset, "order_by_x": order_by_x,
                   "part_list_order": part_list_order, "onset_follows_x": follows_x,
                   "x_differs_from_partlist": differs}
        if not (follows_x and differs):
            disc_ok = False
    r5["b_dir_discriminator"] = {"detail": bcd, "pass": bool(cbeats) and disc_ok}
    # (c) guards:wobble×nrip>1 / wobble×span 過大 / wobble×reveal → ValueError(build + gen 雙驗)
    g_nrip = g_span = g_excl = g_bt_nrip = g_bt_span = g_bt_excl = False
    try:
        G.build_animations(skel, sb, tier_gains=gains, tier_cascade_ripples=rip, cascade_wobble=True)
    except ValueError:
        g_nrip = True
    try:
        G.build_animations(skel, sb, tier_gains=gains,
                           tier_cascade_span={t: 0.70 for t in TIERS}, cascade_wobble=True)
    except ValueError:
        g_span = True
    try:
        G.build_animations(skel, sb, cascade_wobble=True, cascade_reveal=True)
    except ValueError:
        g_excl = True
    try:
        BT.gen_cascade("body", 1.0, (0, 0), phase=0.0, nrip=2, wobble=True)
    except ValueError:
        g_bt_nrip = True
    try:
        BT.gen_cascade("body", 1.0, (0, 0), phase=1.0, span=0.70, wobble=True)
    except ValueError:
        g_bt_span = True
    try:
        BT.gen_cascade("body", 1.0, (0, 0), phase=0.0, reveal=True, wobble=True)
    except ValueError:
        g_bt_excl = True
    r5["c_guards"] = {"build_nrip_rejected": g_nrip, "build_span_rejected": g_span,
                      "build_excl_rejected": g_excl, "gen_nrip_rejected": g_bt_nrip,
                      "gen_span_rejected": g_bt_span, "gen_excl_rejected": g_bt_excl,
                      "pass": g_nrip and g_span and g_excl and g_bt_nrip and g_bt_span and g_bt_excl}
    # (d) 端到端 build_spine --animate --cascade-wobble 可載入
    import build_spine
    out = "/tmp/cascade_wobble_e2e"
    build_spine.build(_psd(), out, genre=GENRE, animate=True, cascade_wobble=True)
    e2e_skel = json.load(open(os.path.join(out, "skeleton.json"), encoding="utf-8"))
    anims = e2e_skel.get("animations", {})
    e2e_cbeats = [nm for nm in anims if "__" not in nm and G.beat_category(nm) == "cascade"]
    e2e_ok = bool(e2e_cbeats)
    e2e_detail = {}
    for cb in e2e_cbeats:
        an = anims[cb]
        fin = SA.all_finite(an)
        bones = [b for b in bones_order if b in an.get("bones", {})]
        has_shear = all("shear" in an["bones"][b] for b in bones) if bones else False
        ends0 = all(abs(first_last_shear(an, b)[0]) <= TOL and abs(first_last_shear(an, b)[1]) <= TOL
                    for b in bones) if bones else False
        e2e_detail[cb] = {"finite": fin, "has_shear": has_shear, "ends_shear0": ends0, "nbones": len(bones)}
        if not (fin and has_shear and ends0):
            e2e_ok = False
    r5["d_end_to_end"] = {"cascade_beats": e2e_cbeats, "detail": e2e_detail, "pass": e2e_ok}
    R["W5_metric_dir_guards"] = {**r5, "pass": all(r5[k]["pass"] for k in r5)}

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
        for k in ["W1_present_backward_compat", "W2_wobble_ordering", "W3_shear_primitive",
                  "W4_wobble_vs_pop_reveal", "W5_metric_dir_guards"]:
            print("{:30s} {}".format(k, "PASS" if R[k]["pass"] else "FAIL"))
        print("W2 wobble onset times (part order):")
        for cb, d in R["W2_wobble_ordering"]["detail"].items():
            print("  {:10s} {} mono={} spread={}".format(cb, d["onset_times"],
                                                         d["monotone_in_partorder"], d["spread"]))
        print("W3 shear primitive (extrema / sign_changes / damped / scale-ident):")
        for key, d in list(R["W3_shear_primitive"]["detail"].items())[:6]:
            print("  {:18s} ext={} sc={} damped={} scale_id={}".format(
                key, d["extrema"], d["sign_changes"], d["damped"], d["scale_identity"]))
        print("W5(b) lr discriminator:")
        for cb, d in R["W5_metric_dir_guards"]["b_dir_discriminator"]["detail"].items():
            print("  {:10s} onset==x {} / x!=partlist {}".format(cb, d["onset_follows_x"],
                                                                 d["x_differs_from_partlist"]))
        print("OVERALL:", "PASS" if R["OVERALL_PASS"] else "FAIL")
    sys.exit(0 if R["OVERALL_PASS"] else 1)


if __name__ == "__main__":
    main()
