#!/usr/bin/env python3
"""animations.loop 自我品質閘(候選 0d 的評估器)。

誠實原則:**驗的是 skeleton.json 裡真實存在的 keyframe**,不是產生器的意圖。
  → 重現 Spine 3.8 的 keyframe 取樣(dense-linear 內插),密集抽樣後量測各角色運動指標,
    逐條 AC 判 pass/fail。並附**負對照**(靜態/同相位)證明閘有鑑別力。

量測指標(對 build_loop 的角色原語):
  body  : translate.y 位移範圍(呼吸幅度)在合理區間、且 loop 無縫
  head  : rotate 角度範圍在合理區間、無縫
  limb  : rotate 角度範圍在合理區間、無縫、**各肢體相位有錯開(peak 時間分散)**
  effect: slot.color alpha 範圍在 [0,1] 內且有脈動、無縫
"""
import argparse, json, math, os, sys


def _interp(kfs, key, t, default):
    """線性內插 scalar timeline(Spine 無 curve 鍵=linear;第0幀可省 time)。"""
    pts = []
    for kf in kfs:
        tt = kf.get("time", 0.0)
        pts.append((tt, kf.get(key, default)))
    pts.sort(key=lambda p: p[0])
    if t <= pts[0][0]:
        return pts[0][1]
    if t >= pts[-1][0]:
        return pts[-1][1]
    for i in range(1, len(pts)):
        if t <= pts[i][0]:
            (t0, v0), (t1, v1) = pts[i - 1], pts[i]
            if t1 == t0:
                return v1
            f = (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * f
    return pts[-1][1]


def _hex_alpha(kf):
    c = kf.get("color", "ffffffff")
    return int(c[6:8], 16) / 255.0


def _interp_alpha(kfs, t):
    pts = [(kf.get("time", 0.0), _hex_alpha(kf)) for kf in kfs]
    pts.sort(key=lambda p: p[0])
    if t <= pts[0][0]:
        return pts[0][1]
    if t >= pts[-1][0]:
        return pts[-1][1]
    for i in range(1, len(pts)):
        if t <= pts[i][0]:
            (t0, v0), (t1, v1) = pts[i - 1], pts[i]
            f = 0 if t1 == t0 else (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * f
    return pts[-1][1]


def _duration(anim):
    d = 0.0
    for sect in ("bones", "slots"):
        for _, tls in anim.get(sect, {}).items():
            for _, kfs in tls.items():
                for kf in kfs:
                    d = max(d, kf.get("time", 0.0))
    return d or 1.0


def _range_and_peak(kfs, key, default, period, N=200):
    lo = hi = None; peak_t = 0.0
    for i in range(N + 1):
        t = period * i / N
        v = _interp(kfs, key, t, default)
        if lo is None or v < lo: lo = v
        if hi is None or v > hi:
            hi = v; peak_t = t
    return lo, hi, peak_t


def _seam(kfs, key, default, period):
    a = _interp(kfs, key, 0.0, default)
    b = _interp(kfs, key, period, default)
    return abs(a - b)


def _seam_alpha(kfs, period):
    return abs(_interp_alpha(kfs, 0.0) - _interp_alpha(kfs, period))


def evaluate(anim, ac=None):
    ac = ac or {}
    period = _duration(anim)
    checks = []
    bones = anim.get("bones", {})
    slots = anim.get("slots", {})

    body_ty = ac.get("body_ty", [2.0, 30.0])
    head_r = ac.get("head_deg", [1.0, 12.0])
    limb_r = ac.get("limb_deg", [1.0, 12.0])
    seam_tol = ac.get("seam_tol", 1e-6)
    phase_min = ac.get("phase_min", 0.1)     # 肢體 peak 時間最大差 / period

    limb_peaks = []
    for bone, tls in bones.items():
        if "translate" in tls and "scale" in tls:   # body
            lo, hi, _ = _range_and_peak(tls["translate"], "y", 0.0, period)
            rng = hi - lo
            checks.append(("body.ty_range", bone, round(rng, 3),
                           body_ty[0] <= rng <= body_ty[1]))
            checks.append(("body.seam", bone, round(_seam(tls["translate"], "y", 0.0, period), 6),
                           _seam(tls["translate"], "y", 0.0, period) <= seam_tol))
        elif "rotate" in tls:
            lo, hi, pk = _range_and_peak(tls["rotate"], "angle", 0.0, period)
            rng = hi - lo
            # 判 head vs limb:用範圍分類粗略,實務上由呼叫者帶 role;此處都檢查範圍+無縫
            checks.append(("rotate.range", bone, round(rng, 3),
                           limb_r[0] <= rng <= max(limb_r[1], head_r[1])))
            checks.append(("rotate.seam", bone, round(_seam(tls["rotate"], "angle", 0.0, period), 6),
                           _seam(tls["rotate"], "angle", 0.0, period) <= seam_tol))
            limb_peaks.append((bone, pk))

    # 相位錯開:所有 rotate bone 的 peak 時間需分散(至少一對差 > phase_min*period)
    phase_ok = True
    spread = 0.0
    if len(limb_peaks) >= 2:
        pts = sorted(p for _, p in limb_peaks)
        spread = max(pts) - min(pts)
        phase_ok = spread > phase_min * period
        checks.append(("limb.phase_spread", "*", round(spread / period, 3), phase_ok))

    for slot, tls in slots.items():
        if "color" in tls:
            vals = [_interp_alpha(tls["color"], period * i / 200) for i in range(201)]
            lo, hi = min(vals), max(vals)
            checks.append(("effect.alpha_in01", slot, [round(lo, 3), round(hi, 3)],
                           0.0 <= lo <= hi <= 1.0))
            checks.append(("effect.alpha_pulse", slot, round(hi - lo, 3), (hi - lo) > 0.02))
            sm = _seam_alpha(tls["color"], period)
            checks.append(("effect.seam", slot, round(sm, 6), sm <= seam_tol))

    passed = all(c[3] for c in checks)
    return {"period": period, "n_checks": len(checks),
            "passed": passed, "phase_spread_frac": round(spread / period, 3) if limb_peaks else None,
            "checks": checks}


# ---------- 負對照(證明閘有鑑別力) ----------
def _static_anim():
    """全零/靜態:body 無位移、limb 無旋轉 → 應 FAIL body/rotate range。"""
    return {"bones": {"b_body": {"translate": [{"y": 0}, {"time": 2, "y": 0}],
                                 "scale": [{"x": 1, "y": 1}, {"time": 2, "x": 1, "y": 1}]},
                      "b_l": {"rotate": [{"angle": 0}, {"time": 2, "angle": 0}]},
                      "b_r": {"rotate": [{"angle": 0}, {"time": 2, "angle": 0}]}}}


def _inphase_anim():
    """有動但肢體同相位(peak 同時)→ 應 FAIL phase_spread。"""
    kf = [{"angle": 0}, {"time": 0.5, "angle": 4}, {"time": 1.0, "angle": 0},
          {"time": 1.5, "angle": -4}, {"time": 2.0, "angle": 0}]
    return {"bones": {"b_l": {"rotate": [dict(k) for k in kf]},
                      "b_r": {"rotate": [dict(k) for k in kf]}}}


def negative_controls():
    out = {}
    s = evaluate(_static_anim())
    # 靜態:期望整體 FAIL(range 條目 fail)
    out["static_fails"] = (not s["passed"])
    ip = evaluate(_inphase_anim())
    # 同相位:phase_spread 條目應 fail
    phase_checks = [c for c in ip["checks"] if c[0] == "limb.phase_spread"]
    out["inphase_phase_fails"] = bool(phase_checks) and (not phase_checks[0][3])
    out["discriminating"] = out["static_fails"] and out["inphase_phase_fails"]
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton", help="含 animations.loop 的 skeleton.json")
    ap.add_argument("--anim", default="loop")
    ap.add_argument("--neg", action="store_true", help="附跑負對照")
    a = ap.parse_args()
    sk = json.load(open(a.skeleton, encoding="utf-8"))
    anim = sk.get("animations", {}).get(a.anim)
    if anim is None:
        print(json.dumps({"error": f"no animation '{a.anim}'"}, ensure_ascii=False)); sys.exit(1)
    res = evaluate(anim)
    if a.neg:
        res["negative_controls"] = negative_controls()
    print(json.dumps(res, ensure_ascii=False, indent=2))
    sys.exit(0 if res["passed"] else 2)


if __name__ == "__main__":
    main()
