#!/usr/bin/env python3
"""candidate 0h 自我驗收閘 — cascade(跨件錯開 reveal)的**跨件時序**簽章量化(純 CPU)。

續 0f/0g:前述主秀 beat(hit/reveal/combo/charge)簽章都在**單一件**的時間包絡上;cascade 是第一個
**跨件(cross-part)**簽章 —— 件依空間序**錯開** onset 逐一 reveal(掃出),而非同時炸開。因此驗證重點
從「單件包絡形狀」轉為「件與件之間的相對時序」,與 0g 的單件時序簽章互補。真值來源同前:主秀運動無
唯一正解(先驗手感),故驗**客觀結構簽章非美感**,並用負對照證明鑑別力(閘可信)。

  C1 well-formed : cascade 每支 finite、時間嚴格遞增、JSON round-trip。
  C2 interface   : reveal 家族介面 —— 首幀所有件 collapsed(scale≈0.02 / alpha≈0)、尾幀所有件 identity
                   (scale=1 / alpha=1 / rotate=0)→ 可接於 Loop 之前。
  C3 per-part    : 每件皆達真 burst 峰 scale ≥ 1.12(件真的 pop)。
  C4 signature   : **跨件簽章** = ①stagger spread(件 scale 峰時間跨度 /T)≥ 門檻 ②monotone sweep
                   (峰時間沿空間序 bone x **嚴格遞增**)。二者兼備才算 cascade。
  C5 neg-control : ①同時 reveal(非錯開)→ 峰時間幾乎相同 → spread≈0 且非遞增 → 非 cascade;
                   ②打亂 onset(逆空間序)→ spread 大但峰時間**遞減** → monotone sweep FAIL → 非 cascade
                     (證「單調掃向」是必要條件,非只看跨度);③單發 hit → identity 起(非 collapsed)
                     且無件間錯開 → 非 cascade;④正對照:真 cascade 具簽章。
  C6 regression  : 接上 cascade 特判後,reveal beat 經 build_animations 仍為合法 reveal(件皆 collapse→identity),
                   證新分支未破壞既有 dispatch。

用法:
  python3 validate_cascade.py            # 跑 C1–C6
  python3 validate_cascade.py --json     # 完整 JSON
  python3 validate_cascade.py --figure   # 另存 knowledge/figures/s1_cascade.png
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import beat_templates as BT

IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL_IDENT = 1e-6
N = 240
STAGGER_THR = 0.25      # cascade 簽章:件峰時間跨度 /T 門檻(同時 reveal → ~0)
COLLAPSE_SCALE = 0.05   # collapsed 判定:scale 低於此視為藏
PEAK_THR = 1.12


# ---------------- fixture(用真實拆件 role 端到端;bone x 遞增 → 空間序明確) ----------------
def build_fixture():
    from analyze_target import analyze
    sb = analyze("assets/robot_parts.psd", "slot_bigwin")["3_motion_storyboard"]
    loop = next(b for b in sb["beats"] if b["beat"] == "Loop")
    parts = [{"part": p["part"], "role": p["role"], "action": "主秀"} for p in loop["parts"]]
    storyboard = {"beats": [
        {"beat": "cascade", "desc": "跨件錯開 reveal", "parts": parts},
        {"beat": "reveal", "desc": "同時 reveal(負對照)", "parts": parts},
        {"beat": "hit", "desc": "單發 hit(負對照)", "parts": parts},
    ]}
    bones = [{"name": "root"}]
    for i, p in enumerate(parts):
        bones.append({"name": "b_" + G.safe(p["part"]), "x": 100.0 + 45 * i, "y": 80.0})
    skel = {"skeleton": {"width": 713, "height": 693}, "bones": bones}
    bone_x = {b["name"]: b.get("x", 0.0) for b in bones if b["name"] != "root"}
    entries = _entries(skel, parts)
    return skel, storyboard, {p["part"]: p["role"] for p in parts}, bone_x, entries


def _entries(skel, parts):
    """重建 gen_animations._cascade_beat 的件表(供自訂 onset 的負對照用)。"""
    bone_of = {b["name"].removeprefix("b_"): b for b in skel["bones"] if b["name"] != "root"}
    cx, cy = skel["skeleton"]["width"] / 2.0, skel["skeleton"]["height"] / 2.0
    out, limb_seen = [], 0
    for pe in parts:
        sname = G.safe(pe["part"]); role = pe["role"]
        bd = bone_of.get(sname)
        if bd is None:
            continue
        side = 1.0
        if role == "limb":
            side = 1.0 if limb_seen % 2 == 0 else -1.0
            limb_seen += 1
        dx, dy = bd.get("x", cx) - cx, bd.get("y", cy) - cy
        nrm = math.hypot(dx, dy) or 1.0
        out.append({"bname": "b_" + sname, "sname": sname, "role": role,
                    "side": side, "radial": (dx / nrm, dy / nrm), "x": bd.get("x", 0.0)})
    return out


def build_cascade_custom(entries, rank_of):
    """用給定的 rank_of(pos,n)→onset-rank 建 cascade(供打亂 onset 的負對照)。"""
    T = G.DUR.get("cascade", 1.4)
    W = 0.45 * T
    order = sorted(range(len(entries)), key=lambda i: (entries[i]["x"], entries[i]["sname"]))
    n = len(order)
    bones, slots = {}, {}
    for pos, idx in enumerate(order):
        rank = rank_of(pos, n)
        onset = (rank / max(n - 1, 1)) * 0.5 * T if n > 1 else 0.0
        e = entries[idx]
        b, s = BT.gen_cascade_part(e["role"], e["side"], e["radial"], onset, W, T)
        bones[e["bname"]] = b
        slots[e["sname"]] = s
    return {"bones": bones, "slots": slots}


# ---------------- 度量 ----------------
def series(anim, bone, key="scaleX", n=N):
    dur = SA.duration(anim)
    return [SA.sample(anim, dur * i / n)["bones"][bone][key] for i in range(n + 1)]


def peak_time(anim, bone):
    v = series(anim, bone)
    d = SA.duration(anim)
    i = max(range(len(v)), key=lambda k: v[k])
    return d * i / n_of(v)


def n_of(v):
    return len(v) - 1


def stagger_metrics(anim, bone_x):
    """回傳 (spread, monotone, peak_times_in_x_order)。spread=峰時間跨度/dur;monotone=沿 x 序嚴格遞增。"""
    bones = list(anim.get("bones", {}))
    d = SA.duration(anim) or 1.0
    if len(bones) < 2:
        return 0.0, False, []
    order = sorted(bones, key=lambda b: (bone_x[b], b))
    pts = [peak_time(anim, b) for b in order]
    spread = (max(pts) - min(pts)) / d
    mono = all(pts[i] < pts[i + 1] for i in range(len(pts) - 1))
    return spread, mono, pts


def has_cascade_signature(anim, bone_x, thr=STAGGER_THR):
    spread, mono, _ = stagger_metrics(anim, bone_x)
    return spread >= thr and mono


def is_ident(bd, tol=TOL_IDENT):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


# ---------------- AC ----------------
def check_c1(anims):
    a = anims["cascade"]
    fin = SA.all_finite(a)
    try:
        rt = json.loads(json.dumps(a)) == a
    except Exception:
        rt = False
    return fin and rt, {"finite_monotonic": fin, "roundtrip": rt}


def check_c2(anims):
    a = anims["cascade"]
    d = SA.duration(a)
    b0 = SA.sample(a, 0.0)
    bT = SA.sample(a, d)
    start_collapsed = all(v["scaleX"] <= COLLAPSE_SCALE for v in b0["bones"].values()) and \
        all(s["alpha"] <= 1e-6 for s in b0["slots"].values())
    end_identity = all(is_ident(v) for v in bT["bones"].values()) and \
        all(abs(s["alpha"] - 1) <= 1e-6 for s in bT["slots"].values())
    return start_collapsed and end_identity, {"start_collapsed": start_collapsed, "end_identity": end_identity}


def check_c3(anims):
    a = anims["cascade"]
    peaks = {b: round(max(series(a, b)), 3) for b in a.get("bones", {})}
    ok = all(p >= PEAK_THR for p in peaks.values())
    return ok, {"peak_per_bone": peaks, "thr": PEAK_THR}


def check_c4(anims, bone_x):
    a = anims["cascade"]
    spread, mono, pts = stagger_metrics(a, bone_x)
    ok = spread >= STAGGER_THR and mono
    return ok, {"spread": round(spread, 3), "thr": STAGGER_THR, "monotone_sweep": mono,
                "peak_times_x_order": [round(t, 3) for t in pts]}


def check_c5(anims, bone_x, entries):
    out, detail = {}, {}
    # 正對照:真 cascade 具簽章
    out["real_cascade_is_cascade"] = has_cascade_signature(anims["cascade"], bone_x) is True
    # ① 同時 reveal → spread≈0、非遞增 → 非 cascade
    rspread, rmono, _ = stagger_metrics(anims["reveal"], bone_x)
    out["simultaneous_reveal_not_cascade"] = has_cascade_signature(anims["reveal"], bone_x) is False
    detail["reveal_spread"] = round(rspread, 3)
    detail["reveal_monotone"] = rmono
    # ② 打亂 onset(逆空間序)→ spread 大但峰時間遞減 → monotone FAIL → 非 cascade
    perm = build_cascade_custom(entries, rank_of=lambda pos, n: n - 1 - pos)
    pspread, pmono, _ = stagger_metrics(perm, bone_x)
    out["permuted_onset_not_cascade"] = has_cascade_signature(perm, bone_x) is False
    out["permuted_has_spread_but_not_monotone"] = (pspread >= STAGGER_THR and not pmono)
    detail["permuted_spread"] = round(pspread, 3)
    detail["permuted_monotone"] = pmono
    # ③ 單發 hit → identity 起(非 collapsed)+ 無錯開 → 非 cascade
    hspread, hmono, _ = stagger_metrics(anims["hit"], bone_x)
    out["single_hit_not_cascade"] = has_cascade_signature(anims["hit"], bone_x) is False
    detail["hit_spread"] = round(hspread, 3)
    return all(out.values()), {"checks": out, "metrics": detail}


def check_c6(anims):
    """回歸:reveal beat 經 build_animations 仍為合法 reveal(件皆 collapse→identity)。"""
    a = anims["reveal"]
    d = SA.duration(a)
    b0, bT = SA.sample(a, 0.0), SA.sample(a, d)
    start_collapsed = all(v["scaleX"] <= COLLAPSE_SCALE for v in b0["bones"].values())
    end_identity = all(is_ident(v) for v in bT["bones"].values())
    has_peak = all(max(series(a, b)) >= PEAK_THR for b in a.get("bones", {}))
    ok = start_collapsed and end_identity and has_peak
    return ok, {"reveal_start_collapsed": start_collapsed, "reveal_end_identity": end_identity,
                "reveal_has_peak": has_peak}


def run_all(figure=False):
    skel, storyboard, roles, bone_x, entries = build_fixture()
    anims = G.build_animations(skel, storyboard)
    res = {}
    res["C1_wellformed"] = check_c1(anims)
    res["C2_reveal_interface"] = check_c2(anims)
    res["C3_per_part_peak"] = check_c3(anims)
    res["C4_cascade_signature"] = check_c4(anims, bone_x)
    res["C5_negative_control"] = check_c5(anims, bone_x, entries)
    res["C6_regression_reveal"] = check_c6(anims)
    overall = all(v[0] for v in res.values())
    report = {"overall_pass": overall, "parts": len(roles),
              "cascade": {"bones": len(anims["cascade"].get("bones", {})),
                          "slots": len(anims["cascade"].get("slots", {})),
                          "duration": round(SA.duration(anims["cascade"]), 3)},
              "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()}}
    if figure:
        _make_figure(anims, bone_x)
    return report


def _make_figure(anims, bone_x):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, name, title in ((axes[0], "cascade", "cascade:件峰時間沿空間序遞增(錯開)"),
                            (axes[1], "reveal", "reveal:件峰時間相同(同時)")):
        a = anims[name]
        d = SA.duration(a)
        ts = [d * i / N for i in range(N + 1)]
        for b in sorted(a["bones"], key=lambda b: bone_x[b]):
            ax.plot(ts, series(a, b), label=b)
        ax.axhline(1.0, color="k", lw=0.5, ls="--")
        ax.set_title(title)
        ax.set_xlabel("t (s)")
        ax.set_ylabel("scale")
        ax.legend(fontsize=7)
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
        print(json.dumps({"overall_pass": report["overall_pass"], "cascade": report["cascade"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
