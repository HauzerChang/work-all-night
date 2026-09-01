#!/usr/bin/env python3
"""candidate 0f 自我驗收閘 — big-win 主秀 beat 模板(hit/reveal)結構簽章量化(純 CPU)。

對 `beat_templates.py`(經 `gen_animations.build_animations` 端到端產生)的 hit/reveal beat,
用 `spine_anim.py` 取樣後逐條 AC 判定。**真值來源**:主秀 beat 沒有唯一正確運動(屬先驗手感),
故本閘驗的是**定義主秀節拍的客觀結構簽章**(anticipation 反向預備 + settle 阻尼回擺),
而非美感;並以**負對照**(天真對稱脈衝 / 不歸位 / 無峰)證明鑑別力。

  B1 well-formed  : hit/reveal 每支 finite、時間嚴格遞增、JSON round-trip。
  B2 chainable IF : hit 首尾皆 setup identity;reveal 首 collapsed(scale~0/alpha 0)、尾 identity。
  B3 impact peak  : 每 beat 有真峰值 scale overshoot ≥ 門檻(遠大於 Loop 微幅)。
  B4 anticipation : hit 命中前反向蓄力(scale 下蹲 <1);reveal burst 前蓄勢 hold(值近平且低)。
  B5 settle       : 命中後阻尼回擺穿越 identity(hit (scale-1) 變號 ≥3;reveal 峰後穿越 ≥2)。
  B6 neg-control  : 天真對稱脈衝(gen_pulse)須 FAIL B4/B5;不歸位須 FAIL B2;無峰須 FAIL B3。

用法:
  python3 validate_beat_templates.py            # 跑 B1–B5(+ 內建 B6 負對照)
  python3 validate_beat_templates.py --json     # 完整 JSON
  python3 validate_beat_templates.py --figure    # 另存 knowledge/figures/s1_beat_templates.png
"""
import argparse, copy, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import beat_templates as BT

IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL_IDENT = 1e-6
COLLAPSE = 0.10   # reveal「藏」判定:scale ≤ 或 alpha ≤
DEAD = 1e-3       # (scale-1) 死區(過濾取樣浮點)
N = 240           # 密取樣點


# ---------------- fixture(用真實拆件 role 端到端) ----------------
def build_fixture():
    """由 analyze_target 取真實 robot 拆件+role,組主秀 beat storyboard + 最小 skeleton。"""
    from analyze_target import analyze
    sb = analyze("assets/robot_parts.psd", "slot_bigwin")["3_motion_storyboard"]
    # 取 Loop beat 的 parts(含每件 role)當 part 清單
    loop = next(b for b in sb["beats"] if b["beat"] == "Loop")
    parts = [{"part": p["part"], "role": p["role"],
              "action": "主秀"} for p in loop["parts"]]
    storyboard = {"beats": [{"beat": "hit", "desc": "主秀重擊", "parts": parts},
                            {"beat": "reveal", "desc": "大獎現身", "parts": parts}]}
    # 最小 skeleton:每 part 一根 bone(名 b_<safe>),位置任意(模板不依賴 radial)
    bones = [{"name": "root"}]
    for i, p in enumerate(parts):
        bones.append({"name": "b_" + G.safe(p["part"]), "x": 100.0 + 30 * i, "y": 80.0})
    skel = {"skeleton": {"width": 713, "height": 693}, "bones": bones}
    return skel, storyboard, {p["part"]: p["role"] for p in parts}


# ---------------- 度量 ----------------
def series(anim, bone, key="scaleX", n=N):
    dur = SA.duration(anim)
    return [SA.sample(anim, dur * i / n)["bones"][bone][key] for i in range(n + 1)]


def alpha_series(anim, slot, n=N):
    dur = SA.duration(anim)
    return [SA.sample(anim, dur * i / n)["slots"][slot]["alpha"] for i in range(n + 1)]


def sign_changes(vals, center=1.0, dead=DEAD):
    prev, sc = 0, 0
    for v in vals:
        d = v - center
        s = 0 if abs(d) <= dead else (1 if d > 0 else -1)
        if s != 0 and s != prev:
            if prev != 0:
                sc += 1
            prev = s
    return sc


def bones_at(anim, t):
    return SA.sample(anim, t)["bones"]


def slots_at(anim, t):
    return SA.sample(anim, t)["slots"]


def is_ident(bd, tol=TOL_IDENT):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


# ---------------- AC ----------------
def check_b1(anims):
    ok, detail = True, {}
    for name in ("hit", "reveal"):
        a = anims[name]
        fin = SA.all_finite(a)
        try:
            rt = json.loads(json.dumps(a)) == a
        except Exception:
            rt = False
        detail[name] = {"finite_monotonic": fin, "roundtrip": rt}
        ok = ok and fin and rt
    return ok, detail


def check_b2(anims):
    detail = {}
    hit = anims["hit"]
    dh = SA.duration(hit)
    hb0, hbE = bones_at(hit, 0.0), bones_at(hit, dh)
    hs0, hsE = slots_at(hit, 0.0), slots_at(hit, dh)
    hit_start_id = all(is_ident(v) for v in hb0.values()) and all(abs(s["alpha"] - 1) <= 1e-6 for s in hs0.values())
    hit_end_id = all(is_ident(v) for v in hbE.values()) and all(abs(s["alpha"] - 1) <= 1e-6 for s in hsE.values())
    detail["hit"] = {"start_identity": hit_start_id, "end_identity": hit_end_id}

    rev = anims["reveal"]
    dr = SA.duration(rev)
    rb0, rbE = bones_at(rev, 0.0), bones_at(rev, dr)
    rs0, rsE = slots_at(rev, 0.0), slots_at(rev, dr)
    rev_start_collapsed = (all(rb0[b]["scaleX"] <= COLLAPSE for b in rb0)
                           or (len(rs0) > 0 and all(s["alpha"] <= COLLAPSE for s in rs0.values())))
    rev_end_id = all(is_ident(v, 1e-4) for v in rbE.values()) and all(abs(s["alpha"] - 1) <= 1e-4 for s in rsE.values())
    detail["reveal"] = {"start_collapsed": rev_start_collapsed, "end_identity": rev_end_id}
    ok = hit_start_id and hit_end_id and rev_start_collapsed and rev_end_id
    return ok, detail


def check_b3(anims):
    detail, ok = {}, True
    for name, thr in (("hit", 1.12), ("reveal", 1.12)):
        a = anims[name]
        peaks = [max(series(a, b["name"] if isinstance(b, dict) else b)) for b in a.get("bones", {})]
        pk = max(peaks) if peaks else 0.0
        good = pk >= thr
        detail[name] = {"peak_scale": round(pk, 3), "thr": thr, "pass": good}
        ok = ok and good
    return ok, detail


def check_b4(anims):
    """anticipation。hit:命中(峰)前 scale 下蹲 <1。reveal:burst 前蓄勢 hold。"""
    detail = {}
    hit = anims["hit"]
    hit_ok = True
    for b in hit.get("bones", {}):
        v = series(hit, b)
        pk_idx = max(range(len(v)), key=lambda i: v[i])
        pre_min = min(v[:pk_idx]) if pk_idx > 0 else 1.0
        anti = pre_min < 1.0 - 0.01
        detail[f"hit:{b}:pre_impact_min"] = {"min": round(pre_min, 4), "pass": anti}
        hit_ok = hit_ok and anti

    rev = anims["reveal"]
    dr = SA.duration(rev)
    rev_ok = True
    for b in rev.get("bones", {}):
        v0 = SA.sample(rev, 0.0)["bones"][b]["scaleX"]
        v15 = SA.sample(rev, 0.15 * dr)["bones"][b]["scaleX"]
        hold = abs(v15 - v0) <= 0.02 and v0 <= COLLAPSE
        detail[f"reveal:{b}:pre_burst_hold"] = {"v0": round(v0, 4), "v15": round(v15, 4), "pass": hold}
        rev_ok = rev_ok and hold
    return hit_ok and rev_ok, detail


def check_b5(anims):
    """settle/follow-through。hit:(scale-1) 變號 ≥3(阻尼回擺);reveal:峰後穿越 identity ≥2。"""
    detail = {}
    hit = anims["hit"]
    hit_ok = True
    for b in hit.get("bones", {}):
        sc = sign_changes(series(hit, b))
        good = sc >= 3
        detail[f"hit:{b}:sign_changes"] = {"n": sc, "pass": good}
        hit_ok = hit_ok and good

    rev = anims["reveal"]
    rev_ok = True
    for b in rev.get("bones", {}):
        v = series(rev, b)
        pk_idx = max(range(len(v)), key=lambda i: v[i])
        post = v[pk_idx:]
        sc = sign_changes(post)
        good = sc >= 2  # 峰(>1)→下衝(<1)→上衝(>1) 至少 2 次穿越
        detail[f"reveal:{b}:post_peak_crossings"] = {"n": sc, "pass": good}
        rev_ok = rev_ok and good
    return hit_ok and rev_ok, detail


# ---------------- 判定器(供 B6 復用) ----------------
def _hit_signature(anim):
    """一支動畫是否具「主秀 hit」結構簽章:每 bone 反向預備 + 阻尼回擺 + 真峰。"""
    for b in anim.get("bones", {}):
        v = series(anim, b)
        pk_idx = max(range(len(v)), key=lambda i: v[i])
        if max(v) < 1.12:
            return False
        if not (pk_idx > 0 and min(v[:pk_idx]) < 1.0 - 0.01):
            return False
        if sign_changes(v) < 3:
            return False
    return True


def check_b6(skel, storyboard):
    """負對照:證明閘能分辨主秀 hit 與天真對稱脈衝 / 不歸位 / 無峰。"""
    out = {}
    # (a) 天真對稱脈衝:gen_pulse('body') 無 anticipation / 無 settle → _hit_signature False
    pb, _ = G.gen_pulse("body", 1.0, (0.0, 0.0))
    pulse_anim = {"bones": {"b_pulse": pb}}
    out["symmetric_pulse_not_main_show"] = (_hit_signature(pulse_anim) is False)

    # 產一份真 hit 供破壞
    good = G.build_animations(skel, storyboard)
    # (b) 不歸位:把 hit 尾 scale 設 1.5 → B2 end_identity FAIL
    bad2 = copy.deepcopy(good)
    for b, ch in bad2["hit"]["bones"].items():
        ch["scale"][-1]["x"] = 1.5
        ch["scale"][-1]["y"] = 1.5
    ok2, _ = check_b2(bad2)
    out["non_returning_hit_fails_B2"] = (ok2 is False)

    # (c) 無峰(flat identity):所有 scale=1 → B3 FAIL
    bad3 = copy.deepcopy(good)
    for b, ch in bad3["hit"]["bones"].items():
        for f in ch["scale"]:
            f["x"] = 1.0
            f["y"] = 1.0
    ok3, _ = check_b3(bad3)
    out["no_peak_fails_B3"] = (ok3 is False)

    # (d) 正對照:真 hit 具簽章
    out["real_hit_has_signature"] = (_hit_signature(good["hit"]) is True)
    return all(out.values()), out


def run_all(figure=False):
    skel, storyboard, roles = build_fixture()
    anims = G.build_animations(skel, storyboard)
    res = {}
    res["B1_wellformed"] = check_b1(anims)
    res["B2_chainable_interface"] = check_b2(anims)
    res["B3_impact_peak"] = check_b3(anims)
    res["B4_anticipation"] = check_b4(anims)
    res["B5_settle"] = check_b5(anims)
    res["B6_negative_control"] = check_b6(skel, storyboard)
    overall = all(v[0] for v in res.values())
    report = {"overall_pass": overall, "parts": len(roles),
              "beats": {k: {"bones": len(anims[k].get("bones", {})),
                            "slots": len(anims[k].get("slots", {}))} for k in ("hit", "reveal")},
              "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()}}
    if figure:
        _make_figure(anims, roles)
    return report


def _make_figure(anims, roles):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception as e:
        return
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    # 取一件 body、一件 limb、一件 特效(若有)
    def bone_for(role):
        for p, r in roles.items():
            if r == role:
                return "b_" + G.safe(p)
        return None
    hit = anims["hit"]; rev = anims["reveal"]
    dh = SA.duration(hit); dr = SA.duration(rev)
    ts_h = [dh * i / N for i in range(N + 1)]
    ts_r = [dr * i / N for i in range(N + 1)]
    ax = axes[0]
    bb = bone_for("body")
    ax.plot(ts_h, series(hit, bb), label="hit scale")
    ax.axhline(1.0, color="k", lw=0.5, ls="--")
    ax.set_title("hit: anticipation→impact→settle\n(body scale)")
    ax.set_xlabel("t (s)"); ax.legend()
    ax = axes[1]
    bl = bone_for("limb")
    if bl and "rotate" in hit["bones"][bl]:
        ax.plot(ts_h, series(hit, bl, "scaleX"), label="scaleX")
        rot = [SA.sample(hit, t)["bones"][bl]["rotate"] for t in ts_h]
        ax2 = ax.twinx(); ax2.plot(ts_h, rot, color="tab:orange", label="rotate")
        ax2.set_ylabel("rotate (deg)")
    ax.axhline(1.0, color="k", lw=0.5, ls="--")
    ax.set_title("hit: limb whip"); ax.set_xlabel("t (s)")
    ax = axes[2]
    ax.plot(ts_r, series(rev, bb), label="reveal scale")
    slot_name = None
    for p, r in roles.items():
        sn = G.safe(p)
        if sn in rev.get("slots", {}):
            slot_name = sn; break
    if slot_name:
        ax.plot(ts_r, alpha_series(rev, slot_name), label="alpha", color="tab:green")
    ax.axhline(1.0, color="k", lw=0.5, ls="--")
    ax.set_title("reveal: collapse→hold→burst→settle"); ax.set_xlabel("t (s)"); ax.legend()
    fig.tight_layout()
    os.makedirs("knowledge/figures", exist_ok=True)
    fig.savefig("knowledge/figures/s1_beat_templates.png", dpi=90)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--figure", action="store_true")
    a = ap.parse_args()
    report = run_all(figure=a.figure)
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"overall_pass": report["overall_pass"], "beats": report["beats"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
