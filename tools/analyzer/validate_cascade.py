#!/usr/bin/env python3
"""candidate 0h 自我驗收閘 — cascade(跨件錯開波)**跨件時序簽章**量化(純 CPU)。

續 0f/0g:hit/reveal/combo/charge 都是**單件內**的時間簽章(同 beat 套每件、每件時序相同)。
cascade 是**跨件**時間簽章 —— 每件依件序相位錯開觸發成一道波。故其簽章不在單件曲線裡,而在
「各件峰值時刻的排序與散佈」,必須**端到端經 build_animations**(才會把件序相位帶進各件)量測 ——
這同時證明 build_animations 的 phase threading 有接上。真值來源同 0f/0g:主秀無唯一正解(先驗手感),
驗**客觀結構簽章非美感**;並用負對照證鑑別力(閘可信)。

  C1 well-formed   : cascade 每件 finite、時間嚴格遞增、JSON round-trip。
  C2 chainable IF  : 每件(bone)首尾皆 setup identity、特效 slot alpha 首尾=1(pop 波可插 Loop 間)。
  C3 impact peak   : 每件 scale overshoot ≥ 門檻(真波,不是微擾)。
  C4 cascade sig   : **跨件** —— 各件峰時刻(argmax scaleX,正規化)依**件序嚴格遞增**,
                     且散佈(末件峰時 − 首件峰時)≥ 門檻(否則近同時觸發,不成波)。
  C5 shared beat   : 每件仍具 0f 通用單件簽章 —— anticipation(峰前 <1)+ settle((scale-1) 變號 ≥3)。
  C6 neg-control   : (a) combo(同 beat 套每件、時序相同)各件峰時刻 spread≈0 → FAIL cascade;
                     (b) 打亂件序 → 峰時刻非遞增 → FAIL;(c) 反序 → 遞減 → FAIL;
                     (d) 正對照:真 cascade 成立;(e) 跨維度:cascade 單件**非** combo 簽章
                     (單峰,非 ≥3 遞增)→ 證 cascade 與 0g 正交(不同維度);(f) 單件 cascade 無 spread → 非波。

用法:
  python3 validate_cascade.py            # 跑 C1–C6
  python3 validate_cascade.py --json     # 完整 JSON
  python3 validate_cascade.py --figure   # 另存 knowledge/figures/s1_cascade.png
"""
import argparse, copy, json, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import beat_templates as BT

IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL_IDENT = 1e-6
DEAD = 1e-3
N = 240
SPREAD_THR = 0.30        # cascade 簽章:各件峰時刻散佈(末−首)須 ≥ 此(佔整段比例)
IMPACT_MIN = 1.12        # 真峰門檻


# ---------------- fixture(用真實拆件 role,件序 = storyboard 件序) ----------------
def build_fixture(beat_name="cascade"):
    from analyze_target import analyze
    sb = analyze("assets/robot_parts.psd", "slot_bigwin")["3_motion_storyboard"]
    loop = next(b for b in sb["beats"] if b["beat"] == "Loop")
    parts = [{"part": p["part"], "role": p["role"], "action": "主秀"} for p in loop["parts"]]
    storyboard = {"beats": [{"beat": beat_name, "desc": "跨件錯開波主秀", "parts": parts}]}
    bones = [{"name": "root"}]
    for i, p in enumerate(parts):
        bones.append({"name": "b_" + G.safe(p["part"]), "x": 100.0 + 30 * i, "y": 80.0})
    skel = {"skeleton": {"width": 713, "height": 693}, "bones": bones}
    # 保留件序(build_animations 依有效件序配相位) → 期望的 bone 順序
    order = ["b_" + G.safe(p["part"]) for p in parts]
    return skel, storyboard, order, {p["part"]: p["role"] for p in parts}


# ---------------- 度量 ----------------
def series(anim, bone, key="scaleX", n=N):
    dur = SA.duration(anim)
    return [SA.sample(anim, dur * i / n)["bones"][bone][key] for i in range(n + 1)]


def peak_time(anim, bone, n=N):
    """該 bone scaleX 全域最大值的正規化時刻 τ∈[0,1]。"""
    v = series(anim, bone, n=n)
    return max(range(len(v)), key=lambda i: v[i]) / n


def sign_changes(vals, center=1.0, dead=DEAD):
    prev, sc = 0, 0
    for x in vals:
        d = x - center
        s = 0 if abs(d) <= dead else (1 if d > 0 else -1)
        if s != 0 and s != prev:
            if prev != 0:
                sc += 1
            prev = s
    return sc


def impact_peaks(vals, prom=BT.IMPACT_PROM):
    peaks = []
    for i in range(1, len(vals) - 1):
        if vals[i] >= prom and vals[i - 1] < vals[i] >= vals[i + 1]:
            peaks.append(vals[i])
    return peaks


def is_ident(bd, tol=TOL_IDENT):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def bones_at(anim, t):
    return SA.sample(anim, t)["bones"]


def slots_at(anim, t):
    return SA.sample(anim, t)["slots"]


# ---------------- 簽章判定器 ----------------
def peak_times_in_order(anim, order):
    """依 order 回傳各件峰時刻 τ(僅取 anim 內存在的 bone)。"""
    bones = anim.get("bones", {})
    return [peak_time(anim, b) for b in order if b in bones]


def cascade_spread(pts):
    return (max(pts) - min(pts)) if len(pts) >= 2 else 0.0


def is_strictly_increasing(pts, eps=1e-6):
    return len(pts) >= 2 and all(pts[i] + eps < pts[i + 1] for i in range(len(pts) - 1))


def has_cascade_signature(anim, order, thr=SPREAD_THR):
    """跨件:峰時刻依件序嚴格遞增 且 散佈 ≥ thr。"""
    pts = peak_times_in_order(anim, order)
    return is_strictly_increasing(pts) and cascade_spread(pts) >= thr


def has_combo_signature(anim):
    """0g combo 簽章:每 bone 遞增 impact 峰 ≥3(用於跨維度負對照)。"""
    bones = anim.get("bones", {})
    if not bones:
        return False
    for b in bones:
        pk = impact_peaks(series(anim, b))
        if not (len(pk) >= 3 and all(pk[i] < pk[i + 1] for i in range(len(pk) - 1))):
            return False
    return True


def has_anticipation(anim):
    for b in anim.get("bones", {}):
        v = series(anim, b)
        pk = max(range(len(v)), key=lambda i: v[i])
        if not (pk > 0 and min(v[:pk]) < 1.0 - 0.01):
            return False
    return True


def has_settle(anim):
    for b in anim.get("bones", {}):
        if sign_changes(series(anim, b)) < 3:
            return False
    return True


# ---------------- AC ----------------
def check_c1(anim):
    fin = SA.all_finite(anim)
    try:
        rt = json.loads(json.dumps(anim)) == anim
    except Exception:
        rt = False
    return fin and rt, {"finite_monotonic": fin, "roundtrip": rt}


def check_c2(anim):
    d = SA.duration(anim)
    b0, bE = bones_at(anim, 0.0), bones_at(anim, d)
    s0, sE = slots_at(anim, 0.0), slots_at(anim, d)
    start_id = all(is_ident(v) for v in b0.values()) and all(abs(s["alpha"] - 1) <= 1e-6 for s in s0.values())
    end_id = all(is_ident(v) for v in bE.values()) and all(abs(s["alpha"] - 1) <= 1e-6 for s in sE.values())
    return start_id and end_id, {"start_identity": start_id, "end_identity": end_id}


def check_c3(anim):
    pk = {b: round(max(series(anim, b)), 3) for b in anim.get("bones", {})}
    ok = all(v >= IMPACT_MIN for v in pk.values()) and len(pk) > 0
    return ok, {"peak_scale_per_bone": pk, "min_required": IMPACT_MIN}


def check_c4(anim, order):
    pts = peak_times_in_order(anim, order)
    inc = is_strictly_increasing(pts)
    spread = cascade_spread(pts)
    ok = inc and spread >= SPREAD_THR
    return ok, {"peak_times_in_part_order": [round(p, 3) for p in pts],
                "strictly_increasing": inc, "spread": round(spread, 3), "spread_thr": SPREAD_THR}


def check_c5(anim):
    anti = has_anticipation(anim)
    settle = has_settle(anim)
    return anti and settle, {"anticipation": anti, "settle": settle}


def check_c6(skel, order):
    out = {}
    # 正對照:真 cascade
    casc = G.build_animations(skel, {"beats": [{"beat": "cascade", "parts": _parts_from(skel, order)}]})["cascade"]
    out["real_cascade_has_signature"] = has_cascade_signature(casc, order) is True

    # (a) combo:同 beat 套每件、時序相同 → 各件峰時刻近同時(spread≈0)→ 非 cascade
    combo = G.build_animations(skel, {"beats": [{"beat": "combo", "parts": _parts_from(skel, order)}]})["combo"]
    combo_pts = peak_times_in_order(combo, order)
    out["combo_spread_near_zero"] = cascade_spread(combo_pts) < SPREAD_THR
    out["combo_not_cascade"] = has_cascade_signature(combo, order) is False

    # (b) 打亂件序 → 峰時刻非遞增
    shuffled = [order[i] for i in _shuffle_idx(len(order))]
    out["shuffled_order_not_cascade"] = has_cascade_signature(casc, shuffled) is False

    # (c) 反序 → 遞減
    out["reversed_order_not_cascade"] = has_cascade_signature(casc, list(reversed(order))) is False

    # (e) 跨維度正交:cascade 單件是**單峰**,非 combo(≥3 遞增)簽章
    out["cascade_not_combo_signature"] = has_combo_signature(casc) is False

    # (f) 單件 cascade → 無 spread → 非波
    one = {"skeleton": skel["skeleton"], "bones": [skel["bones"][0], skel["bones"][1]]}
    one_order = [order[0]]
    solo = G.build_animations(one, {"beats": [{"beat": "cascade", "parts": _parts_from(one, one_order)}]})["cascade"]
    out["single_part_not_cascade"] = has_cascade_signature(solo, one_order) is False
    return all(out.values()), out


def _parts_from(skel, order):
    """由 bone 名還原 storyboard parts(role 由 fixture roles 帶,這裡用 role 佔位即可影響幅度不影響簽章判定)。"""
    roles = _ROLES
    return [{"part": b.removeprefix("b_"), "role": roles.get(b, "body"), "action": "主秀"}
            for b in order]


def _shuffle_idx(n):
    # 確定性「打亂」:非恆等、非反序的固定置換(頭尾對調中段旋轉),保證峰時刻不再單調。
    idx = list(range(n))
    if n >= 3:
        idx[0], idx[1] = idx[1], idx[0]
        idx[-1], idx[-2] = idx[-2], idx[-1]
    return idx


_ROLES = {}


def run_all(figure=False):
    global _ROLES
    skel, storyboard, order, roles = build_fixture()
    _ROLES = {"b_" + G.safe(p): r for p, r in roles.items()}
    anims = G.build_animations(skel, storyboard)
    anim = anims["cascade"]
    res = {}
    res["C1_wellformed"] = check_c1(anim)
    res["C2_chainable_interface"] = check_c2(anim)
    res["C3_impact_peak"] = check_c3(anim)
    res["C4_cross_part_cascade_signature"] = check_c4(anim, order)
    res["C5_shared_beat_quality"] = check_c5(anim)
    res["C6_negative_control"] = check_c6(skel, order)
    overall = all(v[0] for v in res.values())
    report = {"overall_pass": overall, "parts": len(order),
              "beat": {"bones": len(anim.get("bones", {})), "slots": len(anim.get("slots", {})),
                       "duration": round(SA.duration(anim), 3)},
              "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()}}
    if figure:
        _make_figure(anim, order, roles)
    return report


def _make_figure(anim, order, roles):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    d = SA.duration(anim)
    ts = [d * i / N for i in range(N + 1)]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for b in order:
        if b in anim.get("bones", {}):
            ax.plot(ts, series(anim, b), label=b)
            pt = peak_time(anim, b) * d
            ax.axvline(pt, color="gray", lw=0.4, ls=":")
    ax.axhline(1.0, color="k", lw=0.5, ls="--")
    ax.axhline(BT.IMPACT_PROM, color="tab:red", lw=0.5, ls=":", label=f"impact≥{BT.IMPACT_PROM}")
    ax.set_title("cascade: 各件峰時刻依件序錯開(跨件時序簽章)")
    ax.set_xlabel("t (s)")
    ax.set_ylabel("scale")
    ax.legend(fontsize=7, ncol=2)
    fig.tight_layout()
    os.makedirs("knowledge/figures", exist_ok=True)
    fig.savefig("knowledge/figures/s1_cascade.png", dpi=90)
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
        print(json.dumps({"overall_pass": report["overall_pass"], "beat": report["beat"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
