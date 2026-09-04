#!/usr/bin/env python3
"""candidate 0g 自我驗收閘 — 擴充主秀 beat 庫(combo / anticipate_hold)結構簽章量化(純 CPU)。

續 0f(`validate_beat_templates.py`):再加兩個 big-win 主秀節拍,各有**互不相同**的客觀結構簽章,
並用負對照證明鑑別力(閘可信)。真值來源同 0f:主秀 beat 無唯一正確運動(先驗手感),故驗**簽章非美感**。

  M1 well-formed  : combo/charge 每支 finite、時間嚴格遞增、JSON round-trip。
  M2 chainable IF : 兩者首尾皆 setup identity(可插 Loop 循環間)。
  M3 impact peak  : 兩者皆有真峰 scale overshoot ≥ 門檻。
  M4 signature    : combo = **遞增 impact 峰數 ≥3**(≥IMPACT_PROM 局部極大且嚴格遞增);
                    charge = **峰前長蓄力**(峰前持續 <0.97 的時間佔比 ≥0.35)。
  M5 shared beat  : 兩者仍具 0f 通用簽章 —— anticipation(峰前 <1)+ settle((scale-1) 變號 ≥3)。
  M6 neg-control  : 單發 hit 僅 1 impact 峰(FAIL combo 簽章)、蓄力佔比 <0.35(FAIL charge 簽章);
                    對稱脈衝(gen_pulse)兩簽章皆 FAIL;等峰 combo(非遞增)FAIL 遞增判定;正對照真簽章成立。

用法:
  python3 validate_more_beats.py            # 跑 M1–M6
  python3 validate_more_beats.py --json     # 完整 JSON
  python3 validate_more_beats.py --figure   # 另存 knowledge/figures/s1_more_beats.png
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
HOLD_LEVEL = 0.97       # 蓄力判定:scale 低於此視為「充能中」
HOLD_FRAC_THR = 0.35    # charge 簽章:峰前蓄力時間佔比門檻


# ---------------- fixture(用真實拆件 role 端到端) ----------------
def build_fixture():
    from analyze_target import analyze
    sb = analyze("assets/robot_parts.psd", "slot_bigwin")["3_motion_storyboard"]
    loop = next(b for b in sb["beats"] if b["beat"] == "Loop")
    parts = [{"part": p["part"], "role": p["role"], "action": "主秀"} for p in loop["parts"]]
    storyboard = {"beats": [{"beat": "combo", "desc": "連擊主秀", "parts": parts},
                            {"beat": "charge", "desc": "蓄力充能主秀", "parts": parts}]}
    bones = [{"name": "root"}]
    for i, p in enumerate(parts):
        bones.append({"name": "b_" + G.safe(p["part"]), "x": 100.0 + 30 * i, "y": 80.0})
    skel = {"skeleton": {"width": 713, "height": 693}, "bones": bones}
    return skel, storyboard, {p["part"]: p["role"] for p in parts}


# ---------------- 度量 ----------------
def series(anim, bone, key="scaleX", n=N):
    dur = SA.duration(anim)
    return [SA.sample(anim, dur * i / n)["bones"][bone][key] for i in range(n + 1)]


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


def impact_peaks(vals, prom=BT.IMPACT_PROM):
    """回傳時間序的局部極大值(僅 ≥prom),用嚴格上升→非上升偵測(過濾取樣抖動)。"""
    peaks = []
    for i in range(1, len(vals) - 1):
        if vals[i] >= prom and vals[i - 1] < vals[i] >= vals[i + 1]:
            peaks.append(vals[i])
    return peaks


def pre_peak_hold_frac(vals, level=HOLD_LEVEL):
    """峰前(到全域最大值索引前)scale 低於 level 的樣本數 / 全長 → 蓄力時間佔比。"""
    pk = max(range(len(vals)), key=lambda i: vals[i])
    if pk == 0:
        return 0.0
    low = sum(1 for v in vals[:pk] if v < level)
    return low / len(vals)


def is_ident(bd, tol=TOL_IDENT):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def bones_at(anim, t):
    return SA.sample(anim, t)["bones"]


def slots_at(anim, t):
    return SA.sample(anim, t)["slots"]


# ---------------- 簽章判定器(供 M4/M6 復用) ----------------
def is_escalating(peaks):
    return len(peaks) >= 3 and all(peaks[i] < peaks[i + 1] for i in range(len(peaks) - 1))


def has_combo_signature(anim):
    """每 bone:遞增 impact 峰 ≥3。"""
    bones = anim.get("bones", {})
    if not bones:
        return False
    for b in bones:
        if not is_escalating(impact_peaks(series(anim, b))):
            return False
    return True


def has_charge_signature(anim):
    """每 bone:峰前長蓄力佔比 ≥門檻,且有真峰。"""
    bones = anim.get("bones", {})
    if not bones:
        return False
    for b in bones:
        v = series(anim, b)
        if max(v) < 1.12:
            return False
        if pre_peak_hold_frac(v) < HOLD_FRAC_THR:
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
def check_m1(anims):
    ok, detail = True, {}
    for name in ("combo", "charge"):
        a = anims[name]
        fin = SA.all_finite(a)
        try:
            rt = json.loads(json.dumps(a)) == a
        except Exception:
            rt = False
        detail[name] = {"finite_monotonic": fin, "roundtrip": rt}
        ok = ok and fin and rt
    return ok, detail


def check_m2(anims):
    detail, ok = {}, True
    for name in ("combo", "charge"):
        a = anims[name]
        d = SA.duration(a)
        b0, bE = bones_at(a, 0.0), bones_at(a, d)
        s0, sE = slots_at(a, 0.0), slots_at(a, d)
        start_id = all(is_ident(v) for v in b0.values()) and all(abs(s["alpha"] - 1) <= 1e-6 for s in s0.values())
        end_id = all(is_ident(v) for v in bE.values()) and all(abs(s["alpha"] - 1) <= 1e-6 for s in sE.values())
        detail[name] = {"start_identity": start_id, "end_identity": end_id}
        ok = ok and start_id and end_id
    return ok, detail


def check_m3(anims):
    detail, ok = {}, True
    for name in ("combo", "charge"):
        a = anims[name]
        peaks = [max(series(a, b)) for b in a.get("bones", {})]
        pk = max(peaks) if peaks else 0.0
        good = pk >= 1.12
        detail[name] = {"peak_scale": round(pk, 3), "pass": good}
        ok = ok and good
    return ok, detail


def check_m4(anims):
    detail = {}
    combo = anims["combo"]
    combo_sig = has_combo_signature(combo)
    npk = {b: len(impact_peaks(series(combo, b))) for b in combo.get("bones", {})}
    detail["combo"] = {"signature": combo_sig, "impact_peaks_per_bone": npk}
    charge = anims["charge"]
    charge_sig = has_charge_signature(charge)
    frac = {b: round(pre_peak_hold_frac(series(charge, b)), 3) for b in charge.get("bones", {})}
    detail["charge"] = {"signature": charge_sig, "pre_peak_hold_frac": frac, "thr": HOLD_FRAC_THR}
    return combo_sig and charge_sig, detail


def check_m5(anims):
    detail, ok = {}, True
    for name in ("combo", "charge"):
        a = anims[name]
        anti = has_anticipation(a)
        settle = has_settle(a)
        detail[name] = {"anticipation": anti, "settle": settle}
        ok = ok and anti and settle
    return ok, detail


def check_m6(skel, storyboard):
    """負對照:證明兩簽章互斥且能與單發 hit / 對稱脈衝 / 等峰 combo 分離。"""
    out = {}
    # 真 combo / charge(正對照)
    good = G.build_animations(skel, storyboard)
    out["real_combo_has_combo_sig"] = has_combo_signature(good["combo"]) is True
    out["real_charge_has_charge_sig"] = has_charge_signature(good["charge"]) is True

    # 單發 hit:僅 1 impact 峰 → 非 combo;蓄力佔比小 → 非 charge
    hb, _ = BT.gen_hit("body")
    hit_anim = {"bones": {"b_hit": hb}}
    out["single_hit_not_combo"] = has_combo_signature(hit_anim) is False
    out["single_hit_not_charge"] = has_charge_signature(hit_anim) is False

    # 對稱脈衝:兩簽章皆不成立
    pb, _ = G.gen_pulse("body", 1.0, (0.0, 0.0))
    pulse_anim = {"bones": {"b_pulse": pb}}
    out["pulse_not_combo"] = has_combo_signature(pulse_anim) is False
    out["pulse_not_charge"] = has_charge_signature(pulse_anim) is False

    # 等峰 combo(峰不遞增)→ FAIL 遞增判定(把三峰壓成相同值)
    bad = copy.deepcopy(good)
    for b, ch in bad["combo"]["bones"].items():
        for f in ch["scale"]:
            if f["x"] > 1.05:            # 三個 impact 峰壓平成同值
                f["x"] = f["y"] = 1.15
    out["equal_peak_combo_not_escalating"] = has_combo_signature(bad["combo"]) is False

    # combo 與 charge 簽章互斥(combo 非長蓄力、charge 非多峰)
    out["combo_not_charge_sig"] = has_charge_signature(good["combo"]) is False
    out["charge_not_combo_sig"] = has_combo_signature(good["charge"]) is False
    return all(out.values()), out


def run_all(figure=False):
    skel, storyboard, roles = build_fixture()
    anims = G.build_animations(skel, storyboard)
    res = {}
    res["M1_wellformed"] = check_m1(anims)
    res["M2_chainable_interface"] = check_m2(anims)
    res["M3_impact_peak"] = check_m3(anims)
    res["M4_distinct_signature"] = check_m4(anims)
    res["M5_shared_beat_quality"] = check_m5(anims)
    res["M6_negative_control"] = check_m6(skel, storyboard)
    overall = all(v[0] for v in res.values())
    report = {"overall_pass": overall, "parts": len(roles),
              "beats": {k: {"bones": len(anims[k].get("bones", {})),
                            "slots": len(anims[k].get("slots", {}))} for k in ("combo", "charge")},
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

    def bone_for(role):
        for p, r in roles.items():
            if r == role:
                return "b_" + G.safe(p)
        return "b_" + G.safe(next(iter(roles)))

    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, name, title in ((axes[0], "combo", "combo: 3 遞增 impact 峰"),
                            (axes[1], "charge", "anticipate_hold: 長蓄力→釋放")):
        a = anims[name]
        d = SA.duration(a)
        ts = [d * i / N for i in range(N + 1)]
        bb = bone_for("body")
        ax.plot(ts, series(a, bb), label=f"{name} scale")
        ax.axhline(1.0, color="k", lw=0.5, ls="--")
        ax.axhline(BT.IMPACT_PROM, color="tab:red", lw=0.5, ls=":", label=f"impact≥{BT.IMPACT_PROM}")
        if name == "charge":
            ax.axhline(HOLD_LEVEL, color="tab:green", lw=0.5, ls=":", label=f"hold<{HOLD_LEVEL}")
        ax.set_title(title)
        ax.set_xlabel("t (s)")
        ax.legend(fontsize=8)
    fig.tight_layout()
    os.makedirs("knowledge/figures", exist_ok=True)
    fig.savefig("knowledge/figures/s1_more_beats.png", dpi=90)
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
