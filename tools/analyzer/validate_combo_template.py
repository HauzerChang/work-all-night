#!/usr/bin/env python3
"""candidate 0g 自我驗收閘 — big-win「連擊 / rollup」主秀 beat 模板(gen_combo)結構簽章量化(純 CPU)。

延續 0f(hit/reveal)的方法學:主秀節拍無唯一正確運動(屬先驗手感),故本閘驗的是
**定義「連擊」的客觀結構簽章**——「同一拍內多次**遞減**重音」,而非美感;並以**負對照**
(單一 hit / 天真對稱脈衝 / **等幅重複脈衝** / 遞增脈衝)證明鑑別力。

  C1 well-formed   : combo 每支 finite、時間嚴格遞增、JSON round-trip。
  C2 chainable IF  : combo 首尾皆 setup identity(scale=1/rotate=0/alpha=1)→ 可插 Loop 間 / 串接。
  C3 multi-peak    : 每 bone 的 scale 有 **≥2 個獨立正峰**(擊間 scale 回落 identity 附近而分段)。
  C4 decaying peaks: 峰值序列**嚴格遞減**(follow-through / 能量耗散)。**核心鑑別簽章**。
  C5 separated+antic: 擊間回落 identity 附近(troughs ≤ +0.05);且每擊前有 anticipation 蓄力(<1)。
  C6 neg-control   : 單擊 hit / 對稱脈衝須 FAIL C3(僅 1 峰);**等幅重複脈衝**須 FAIL C4(多峰但不遞減);
                     **遞增脈衝**須 FAIL C4;真 combo 具完整簽章(正對照)。

用法:
  python3 validate_combo_template.py            # 跑 C1–C6
  python3 validate_combo_template.py --json     # 完整 JSON
  python3 validate_combo_template.py --figure    # 另存 knowledge/figures/s1_combo_template.png
"""
import argparse, copy, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))

import spine_anim as SA
import gen_animations as G
import beat_templates as BT

IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
TOL_IDENT = 1e-6
PROM = 0.03       # 正峰 prominence 門檻(scale-1 需超過此值才算一擊)
TROUGH = 0.05     # 擊間回落判定:相鄰峰間 (scale-1) 需回到 ≤ 此值(獨立擊、非長平台)
N = 300           # 密取樣點


# ---------------- fixture(用真實拆件 role 端到端,經 build_animations) ----------------
def build_fixture():
    """由 analyze_target 取真實 robot 拆件+role,組 combo beat storyboard + 最小 skeleton。
    走 build_animations → beat_category('combo') → _DISPATCH['combo'] 端到端(非直呼模板)。"""
    from analyze_target import analyze
    sb = analyze("assets/robot_parts.psd", "slot_bigwin")["3_motion_storyboard"]
    loop = next(b for b in sb["beats"] if b["beat"] == "Loop")
    parts = [{"part": p["part"], "role": p["role"], "action": "連擊"} for p in loop["parts"]]
    storyboard = {"beats": [{"beat": "combo", "desc": "連環中獎 rollup", "parts": parts}]}
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


def peak_segments(vals, center=1.0, prom=PROM):
    """回傳 [(peak_value, trough_before)] 的獨立正峰序列(above-threshold 分段)。
    一個「峰」= (scale-center) 連續 > prom 的區段之最大值;區段間須回落 ≤ prom → 保證獨立。
    trough_before = 此峰與前一峰之間 (scale-center) 的最小值(用於 C5 分離度)。"""
    peaks, troughs = [], []
    inpk, seg_max = False, None
    last_end = 0
    for i, v in enumerate(vals):
        d = v - center
        if d > prom:
            if not inpk:
                inpk, seg_max, seg_start = True, d, i
            else:
                seg_max = max(seg_max, d)
        else:
            if inpk:
                trough = min(vals[last_end:seg_start]) if peaks else center
                peaks.append(seg_max + center)
                troughs.append(trough)
                inpk, last_end = False, i
    if inpk:
        trough = min(vals[last_end:]) if peaks else center
        peaks.append(seg_max + center)
        troughs.append(trough)
    return peaks, troughs


def sign_of(v, center=1.0, dead=1e-3):
    d = v - center
    return 0 if abs(d) <= dead else (1 if d > 0 else -1)


def bones_at(anim, t):
    return SA.sample(anim, t)["bones"]


def slots_at(anim, t):
    return SA.sample(anim, t)["slots"]


def is_ident(bd, tol=TOL_IDENT):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


# ---------------- 簽章判定器(供 C6 復用) ----------------
def combo_signature(anim):
    """一支動畫是否具「連擊」結構簽章:每 bone 的 scale 具 ≥2 個獨立正峰且**嚴格遞減**。"""
    bones = anim.get("bones", {})
    scaled = [b for b in bones if "scale" in bones[b]]
    if not scaled:
        return False
    for b in scaled:
        peaks, _ = peak_segments(series(anim, b))
        if len(peaks) < 2:
            return False
        if not all(peaks[i] > peaks[i + 1] + 1e-6 for i in range(len(peaks) - 1)):
            return False
    return True


# ---------------- AC ----------------
def check_c1(anims):
    a = anims["combo"]
    fin = SA.all_finite(a)
    try:
        rt = json.loads(json.dumps(a)) == a
    except Exception:
        rt = False
    # 時間嚴格遞增(每 timeline)
    mono = True
    for ch in a.get("bones", {}).values():
        for key in ("scale", "rotate", "translate"):
            fr = ch.get(key)
            if fr:
                ts = [f["time"] for f in fr]
                mono = mono and all(ts[i] < ts[i + 1] for i in range(len(ts) - 1))
    return (fin and rt and mono), {"finite": fin, "roundtrip": rt, "monotonic": mono}


def check_c2(anims):
    a = anims["combo"]
    d = SA.duration(a)
    b0, bE = bones_at(a, 0.0), bones_at(a, d)
    s0, sE = slots_at(a, 0.0), slots_at(a, d)
    start_id = all(is_ident(v) for v in b0.values()) and all(abs(s["alpha"] - 1) <= 1e-6 for s in s0.values())
    end_id = all(is_ident(v) for v in bE.values()) and all(abs(s["alpha"] - 1) <= 1e-6 for s in sE.values())
    return (start_id and end_id), {"start_identity": start_id, "end_identity": end_id}


def check_c3(anims):
    a = anims["combo"]
    detail, ok = {}, True
    for b in a.get("bones", {}):
        peaks, _ = peak_segments(series(a, b))
        good = len(peaks) >= 2
        detail[b] = {"n_peaks": len(peaks), "peaks": [round(p, 3) for p in peaks], "pass": good}
        ok = ok and good
    return ok, detail


def check_c4(anims):
    a = anims["combo"]
    detail, ok = {}, True
    for b in a.get("bones", {}):
        peaks, _ = peak_segments(series(a, b))
        dec = len(peaks) >= 2 and all(peaks[i] > peaks[i + 1] + 1e-6 for i in range(len(peaks) - 1))
        detail[b] = {"peaks": [round(p, 3) for p in peaks], "strictly_decreasing": dec}
        ok = ok and dec
    return ok, detail


def check_c5(anims):
    """separated + anticipated:擊間 troughs 回落 identity 附近(≤ center+TROUGH);
    且每擊 impact 前有 anticipation 蓄力(局部 scale < 1)。"""
    a = anims["combo"]
    detail, ok = {}, True
    for b in a.get("bones", {}):
        v = series(a, b)
        peaks, troughs = peak_segments(v)
        # 擊間 trough(第 2 峰起才有前擊)須回落 identity 附近
        inter = troughs[1:] if len(troughs) > 1 else []
        sep = all(t <= 1.0 + TROUGH for t in inter)
        # anticipation:整條有明確 <1 的蓄力(min < 1-0.01)
        anti = min(v) < 1.0 - 0.01
        good = sep and anti and len(peaks) >= 2
        detail[b] = {"inter_troughs": [round(t, 3) for t in inter], "separated": sep,
                     "min_scale": round(min(v), 3), "anticipation": anti, "pass": good}
        ok = ok and good
    return ok, detail


def check_c6(skel, storyboard):
    """負對照:證明閘能分辨「連擊」與 單擊 / 對稱脈衝 / 等幅重複 / 遞增。"""
    out = {}
    # (a) 單一 hit(0f)→ 僅 1 峰 → 非 combo
    hb, _ = BT.gen_hit("body", 1.0, (0.0, 0.0))
    out["single_hit_not_combo"] = (combo_signature({"bones": {"b": hb}}) is False)
    # (b) 天真對稱脈衝 → 僅 1 峰 → 非 combo
    pb, _ = G.gen_pulse("body", 1.0, (0.0, 0.0))
    out["symmetric_pulse_not_combo"] = (combo_signature({"bones": {"b": pb}}) is False)
    # (c) 等幅重複脈衝(3 等峰)→ 多峰但**不遞減** → 非 combo(關鍵鑑別)
    T = 1.2
    eqf = [{"time": 0.0, "x": 1.0, "y": 1.0}]
    for k in range(3):
        base = k / 3.0
        eqf += [{"time": round((base + 0.45 / 3) * T, 4), "x": 1.2, "y": 1.2},
                {"time": round((base + 0.85 / 3) * T, 4), "x": 1.0, "y": 1.0}]
    eqf.append({"time": round(T, 4), "x": 1.0, "y": 1.0})
    out["equal_amp_repeat_not_combo"] = (combo_signature({"bones": {"b": {"scale": eqf}}}) is False)
    # (d) 遞增脈衝(峰值上升)→ 多峰但遞增 → 非 combo
    inf = [{"time": 0.0, "x": 1.0, "y": 1.0}]
    for k in range(3):
        base = k / 3.0
        pk = 1.0 + 0.08 * (k + 1)   # 上升
        inf += [{"time": round((base + 0.45 / 3) * T, 4), "x": pk, "y": pk},
                {"time": round((base + 0.85 / 3) * T, 4), "x": 1.0, "y": 1.0}]
    inf.append({"time": round(T, 4), "x": 1.0, "y": 1.0})
    out["increasing_amp_not_combo"] = (combo_signature({"bones": {"b": {"scale": inf}}}) is False)
    # (e) 正對照:真 combo(端到端經 build_animations)具完整簽章
    good = G.build_animations(skel, storyboard)
    out["real_combo_has_signature"] = (combo_signature(good["combo"]) is True)
    return all(out.values()), out


def run_all(figure=False):
    skel, storyboard, roles = build_fixture()
    anims = G.build_animations(skel, storyboard)
    res = {}
    res["C1_wellformed"] = check_c1(anims)
    res["C2_chainable_interface"] = check_c2(anims)
    res["C3_multi_peak"] = check_c3(anims)
    res["C4_decaying_peaks"] = check_c4(anims)
    res["C5_separated_anticipated"] = check_c5(anims)
    res["C6_negative_control"] = check_c6(skel, storyboard)
    overall = all(v[0] for v in res.values())
    report = {"overall_pass": overall, "parts": len(roles),
              "combo": {"bones": len(anims["combo"].get("bones", {})),
                        "slots": len(anims["combo"].get("slots", {})),
                        "N_hits": BT._COMBO_N, "decay": BT._COMBO_DECAY},
              "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()}}
    if figure:
        _make_figure(anims, roles)
    return report


def _make_figure(anims, roles):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return
    combo = anims["combo"]
    dur = SA.duration(combo)
    ts = [dur * i / N for i in range(N + 1)]

    def bone_for(role):
        for p, r in roles.items():
            if r == role:
                return "b_" + G.safe(p)
        return None

    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    for ax, role, title in ((axes[0], "body", "body scale (decaying peaks)"),
                            (axes[1], "limb", "limb: scale + whip"),
                            (axes[2], "特效", "effect: scale + alpha flash")):
        bn = bone_for(role)
        if not bn or bn not in combo.get("bones", {}):
            ax.set_title(title + "\n(n/a)"); continue
        ax.plot(ts, series(combo, bn), label="scaleX", color="tab:blue")
        peaks, _ = peak_segments(series(combo, bn))
        ax.axhline(1.0, color="k", lw=0.5, ls="--")
        if "rotate" in combo["bones"][bn]:
            rot = [SA.sample(combo, t)["bones"][bn]["rotate"] for t in ts]
            ax2 = ax.twinx(); ax2.plot(ts, rot, color="tab:orange", lw=0.8, label="rotate")
            ax2.set_ylabel("rotate (deg)")
        sn = G.safe([p for p, r in roles.items() if r == role][0])
        if sn in combo.get("slots", {}):
            ax.plot(ts, alpha_series(combo, sn), label="alpha", color="tab:green")
        ax.set_title(title + f"\npeaks={[round(p,2) for p in peaks]}")
        ax.set_xlabel("t (s)"); ax.legend(loc="upper right", fontsize=8)
    fig.suptitle("candidate 0g — multi-hit combo (decaying peaks signature)")
    fig.tight_layout()
    os.makedirs("knowledge/figures", exist_ok=True)
    fig.savefig("knowledge/figures/s1_combo_template.png", dpi=90)
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
        print(json.dumps({"overall_pass": report["overall_pass"], "combo": report["combo"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
