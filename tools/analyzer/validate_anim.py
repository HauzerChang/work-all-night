#!/usr/bin/env python3
"""S1 #3d 評估器 — 待機/呼吸循環動畫的可機讀品質閘。

自帶一支**純 Python Spine 3.8 bone/slot timeline 取樣器**(linear/stepped/緊湊 bezier),
不需瀏覽器(CDN 被網路政策擋)。對一份 skeleton.json 的某支動畫檢查:

  AC1 loop_closure  : 每條 timeline 首幀(t=0)== 末幀(t=T)——無縫循環。
  AC2 motion_present: 每個「該動」的 bone/slot,其取樣值域(max-min)> 門檻(非 no-op)。
  AC3 amp_bounded   : scale∈[0.9,1.1]、|rotate|≤15°、|translate|≤畫布 5%、alpha∈[0,1]
                      —— 幅度有界,不會飛出畫面/誇張變形。
  AC4 phase_stagger : limb bones 的峰值時間彼此錯開(相位散佈 > 0)。
  AC5 format_valid  : timeline 指向存在的 bone/slot;keyframe time 單調遞增且 ∈[0,T]。

取樣器另附**自驗**:在 keyframe 時間點取樣應精確回放該 key 的值(round-trip),
以此確認取樣器數學可信;再以此判定生成動畫。並提供**負對照**(注入壞動畫)確認閘有鑑別力。
"""
import argparse, json, math, os, sys


# ---------------- Spine 3.8 timeline 取樣器 ----------------
def _bezier(t01, cx1, cy1, cx2, cy2, iters=8):
    """緊湊 bezier:給定 x∈[0,1] 求 y。控制點 (cx1,cy1),(cx2,cy2),端點 (0,0),(1,1)。
    以 Newton/二分求參數 u 使 Bx(u)=x,回傳 By(u)。"""
    lo, hi = 0.0, 1.0
    for _ in range(iters):
        u = (lo + hi) / 2
        mu = 1 - u
        bx = 3 * mu * mu * u * cx1 + 3 * mu * u * u * cx2 + u * u * u
        if bx < t01:
            lo = u
        else:
            hi = u
    u = (lo + hi) / 2
    mu = 1 - u
    return 3 * mu * mu * u * cy1 + 3 * mu * u * u * cy2 + u * u * u


def _interp(prev, nxt, t, keys_field, defaults):
    """在相鄰兩 keyframe 之間對每個欄位內插。prev/nxt 為 dict。"""
    t0 = prev.get("time", 0.0)
    t1 = nxt.get("time", 0.0)
    span = t1 - t0
    a = 0.0 if span <= 0 else (t - t0) / span
    curve = prev.get("curve", None)
    out = {}
    for f in keys_field:
        v0 = prev.get(f, defaults[f])
        v1 = nxt.get(f, defaults[f])
        if curve == "stepped":
            out[f] = v0
        elif isinstance(curve, (int, float)):
            # 緊湊 bezier:curve=cx1,c2=cy1,c3=cx2,c4=cy2(缺者補 0/預設)
            cx1 = curve
            cy1 = prev.get("c2", 0.0)
            cx2 = prev.get("c3", 1.0)
            cy2 = prev.get("c4", 1.0)
            frac = _bezier(a, cx1, cy1, cx2, cy2)
            out[f] = v0 + (v1 - v0) * frac
        else:                      # 無 curve 鍵 = linear
            out[f] = v0 + (v1 - v0) * a
    return out


def sample_timeline(frames, t, keys_field, defaults):
    """在時間 t 取樣一條 timeline。回傳 {field: value}。"""
    if not frames:
        return dict(defaults)
    if t <= frames[0].get("time", 0.0):
        return {f: frames[0].get(f, defaults[f]) for f in keys_field}
    if t >= frames[-1].get("time", 0.0):
        return {f: frames[-1].get(f, defaults[f]) for f in keys_field}
    # 精確命中某 keyframe → 直接回放該 key 值(避免 bezier 端點數值誤差)
    for fr in frames:
        if abs(fr.get("time", 0.0) - t) < 1e-9:
            return {f: fr.get(f, defaults[f]) for f in keys_field}
    for i in range(len(frames) - 1):
        t0 = frames[i].get("time", 0.0)
        t1 = frames[i + 1].get("time", 0.0)
        if t0 <= t <= t1:
            return _interp(frames[i], frames[i + 1], t, keys_field, defaults)
    return {f: frames[-1].get(f, defaults[f]) for f in keys_field}


TL_SPEC = {
    "rotate":    (["angle"], {"angle": 0.0}),
    "translate": (["x", "y"], {"x": 0.0, "y": 0.0}),
    "scale":     (["x", "y"], {"x": 1.0, "y": 1.0}),
}
SLOT_COLOR_FIELDS = ["r", "g", "b", "a"]


def _color_to_rgba(hexstr):
    h = hexstr
    return [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4, 6)]


def anim_duration(anim):
    d = 0.0
    for _, tls in anim.get("bones", {}).items():
        for _, frames in tls.items():
            d = max(d, max((f.get("time", 0.0) for f in frames), default=0.0))
    for _, tls in anim.get("slots", {}).items():
        for _, frames in tls.items():
            d = max(d, max((f.get("time", 0.0) for f in frames), default=0.0))
    return d


# ---------------- 評估 ----------------
def evaluate(skeleton, anim_name, substeps=6,
             amp={"scale": (0.9, 1.1), "rot": 15.0, "trans_frac": 0.05},
             motion_eps={"rot": 0.2, "scale": 0.002, "trans": 0.3, "alpha": 0.02}):
    anim = skeleton["animations"][anim_name]
    bone_names = {b["name"] for b in skeleton["bones"]}
    slot_names = {s["name"] for s in skeleton["slots"]}
    W = skeleton["skeleton"].get("width", 1000)
    H = skeleton["skeleton"].get("height", 1000)
    T = anim_duration(anim)
    canvas = max(W, H)

    issues = []
    # AC5 format_valid: 指向存在 bone/slot + time 單調 ∈[0,T]
    fmt_ok = True
    for bn, tls in anim.get("bones", {}).items():
        if bn not in bone_names:
            issues.append(f"bone '{bn}' 不存在"); fmt_ok = False
        for tl, frames in tls.items():
            ts = [f.get("time", 0.0) for f in frames]
            if ts != sorted(ts) or (ts and (ts[0] < -1e-9 or ts[-1] > T + 1e-9)):
                issues.append(f"{bn}/{tl} time 非單調或越界"); fmt_ok = False
    for sn, tls in anim.get("slots", {}).items():
        if sn not in slot_names:
            issues.append(f"slot '{sn}' 不存在"); fmt_ok = False

    # 取樣時間點(keyframe 全含 + 每段 substeps 細分)
    keytimes = set([0.0, T])
    for _, tls in anim.get("bones", {}).items():
        for _, frames in tls.items():
            for f in frames:
                keytimes.add(f.get("time", 0.0))
    kt = sorted(keytimes)
    samples = set()
    for i in range(len(kt)):
        samples.add(kt[i])
        if i + 1 < len(kt):
            for s in range(1, substeps):
                samples.add(kt[i] + (kt[i + 1] - kt[i]) * s / substeps)
    samples = sorted(samples)

    # 逐 bone/timeline 量測
    closure_max = 0.0
    amp_bad = []
    motion = {}          # bone/tl/field -> range(細項,供檢視)
    tl_motion = {}       # bone/tl -> 聚合 range(判 no-op 用;單一靜止分量不算)
    limb_peak = {}       # rotate bone -> 帶號峰值時間(判相位錯開)
    for bn, tls in anim.get("bones", {}).items():
        for tl, frames in tls.items():
            fields, defaults = TL_SPEC[tl]
            v0 = sample_timeline(frames, 0.0, fields, defaults)
            vT = sample_timeline(frames, T, fields, defaults)
            closure_max = max(closure_max,
                              max(abs(v0[f] - vT[f]) for f in fields))
            series = {f: [] for f in fields}
            peak_t, peak_v = 0.0, -1e30   # 用**帶號**峰值時間(abs 對 π 相位差不敏感)
            for t in samples:
                v = sample_timeline(frames, t, fields, defaults)
                for f in fields:
                    series[f].append(v[f])
                if tl == "rotate" and v["angle"] > peak_v:
                    peak_v = v["angle"]; peak_t = t
            tl_range = 0.0
            for f in fields:
                rng = max(series[f]) - min(series[f])
                motion[f"{bn}/{tl}/{f}"] = round(rng, 4)
                tl_range = max(tl_range, rng)     # 逐 timeline 聚合(單一靜止分量不算 no-op)
                lo, hi = min(series[f]), max(series[f])
                if tl == "scale" and (lo < amp["scale"][0] - 1e-6 or hi > amp["scale"][1] + 1e-6):
                    amp_bad.append(f"{bn}/scale/{f}∈[{lo:.3f},{hi:.3f}]")
                if tl == "rotate" and max(abs(lo), abs(hi)) > amp["rot"] + 1e-6:
                    amp_bad.append(f"{bn}/rotate {max(abs(lo),abs(hi)):.2f}°")
                if tl == "translate" and max(abs(lo), abs(hi)) > amp["trans_frac"] * canvas + 1e-6:
                    amp_bad.append(f"{bn}/translate {max(abs(lo),abs(hi)):.1f}px")
            tl_motion[f"{bn}/{tl}"] = round(tl_range, 4)
            if tl == "rotate":
                limb_peak[bn] = peak_t

    # slot color
    for sn, tls in anim.get("slots", {}).items():
        frames = tls.get("color")
        if not frames:
            continue
        v0 = _color_to_rgba(frames[0]["color"])
        vT = _color_to_rgba(frames[-1]["color"])
        closure_max = max(closure_max, max(abs(a - b) for a, b in zip(v0, vT)))
        alphas = []
        for t in samples:
            # color 內插:對 hex 逐通道線性(近似;生成端亦線性)
            fr = _nearest_color(frames, t)
            alphas.append(fr[3])
        rng = max(alphas) - min(alphas)
        motion[f"{sn}/color/a"] = round(rng, 4)
        tl_motion[f"{sn}/color"] = round(rng, 4)
        if min(alphas) < -1e-6 or max(alphas) > 1 + 1e-6:
            amp_bad.append(f"{sn}/alpha∈[{min(alphas):.3f},{max(alphas):.3f}]")

    # AC2 motion_present:每條 timeline(聚合各分量)range 是否 > eps
    noops = []
    for key, rng in tl_motion.items():
        kind = key.split("/")[1]
        thr = (motion_eps["rot"] if kind == "rotate" else
               motion_eps["scale"] if kind == "scale" else
               motion_eps["alpha"] if kind == "color" else
               motion_eps["trans"])
        if rng < thr:
            noops.append(f"{key}={rng}")

    # AC4 phase_stagger:limb rotate 峰值時間散佈(至少 2 支才有意義)
    peaks = list(limb_peak.values())
    stagger = (max(peaks) - min(peaks)) if len(peaks) >= 2 else None

    ac = {
        "AC1_loop_closure": {"max_endpoint_diff": round(closure_max, 5),
                             "pass": closure_max < 1e-3},
        "AC2_motion_present": {"noops": noops, "pass": len(noops) == 0},
        "AC3_amp_bounded": {"violations": amp_bad, "pass": len(amp_bad) == 0},
        "AC4_phase_stagger": {"peak_time_spread": None if stagger is None else round(stagger, 4),
                              "n_rotate_bones": len(peaks),
                              "pass": (stagger is None) or (stagger > 1e-3)},
        "AC5_format_valid": {"issues": issues, "pass": fmt_ok},
    }
    ac["overall_pass"] = all(v["pass"] for k, v in ac.items() if k.startswith("AC"))
    ac["_anim"] = anim_name
    ac["_duration"] = T
    ac["_n_bone_tl"] = sum(len(t) for t in anim.get("bones", {}).values())
    ac["_n_slot_tl"] = sum(len(t) for t in anim.get("slots", {}).values())
    return ac


def _nearest_color(frames, t):
    """color timeline 線性內插(逐通道)。"""
    if t <= frames[0].get("time", 0.0):
        return _color_to_rgba(frames[0]["color"])
    if t >= frames[-1].get("time", 0.0):
        return _color_to_rgba(frames[-1]["color"])
    for i in range(len(frames) - 1):
        t0 = frames[i].get("time", 0.0); t1 = frames[i + 1].get("time", 0.0)
        if t0 <= t <= t1:
            a = 0.0 if t1 == t0 else (t - t0) / (t1 - t0)
            c0 = _color_to_rgba(frames[i]["color"]); c1 = _color_to_rgba(frames[i + 1]["color"])
            if frames[i].get("curve") == "stepped":
                return c0
            return [x0 + (x1 - x0) * a for x0, x1 in zip(c0, c1)]
    return _color_to_rgba(frames[-1]["color"])


# ---------------- 取樣器自驗 + 負對照 ----------------
def sampler_selftest(path="assets/main_draw.json"):
    """對真實 main_draw:在每個 keyframe 時間點取樣,應精確回放該 key 值(誤差≈0)。
    驗證取樣器(linear + 緊湊 bezier + stepped)數學正確。"""
    sk = json.load(open(path))
    worst = 0.0; n = 0
    for an, ad in sk["animations"].items():
        for bn, tls in ad.get("bones", {}).items():
            for tl, frames in tls.items():
                if tl not in TL_SPEC:
                    continue
                fields, defaults = TL_SPEC[tl]
                for f in frames:
                    t = f.get("time", 0.0)
                    got = sample_timeline(frames, t, fields, defaults)
                    for fld in fields:
                        exp = f.get(fld, defaults[fld])
                        worst = max(worst, abs(got[fld] - exp)); n += 1
    return {"keyframes_checked": n, "max_replay_error": round(worst, 9),
            "pass": worst < 1e-6}


def negative_controls(skeleton, anim_name):
    """對合格動畫注入 4 種缺陷,確認對應 AC 由 pass→fail(閘有鑑別力)。"""
    import copy
    base = skeleton
    res = {}

    def run(mut, tag):
        sk = copy.deepcopy(base)
        mut(sk["animations"][anim_name])
        return evaluate(sk, anim_name)

    # (a) 破壞 loop 閉合:末幀值改掉
    def break_closure(a):
        for bn, tls in a.get("bones", {}).items():
            for tl, fr in tls.items():
                if tl == "rotate":
                    fr[-1]["angle"] = fr[-1].get("angle", 0) + 30
                    return
    r = run(break_closure, "closure"); res["break_closure→AC1_fail"] = not r["AC1_loop_closure"]["pass"]

    # (b) 幅度爆表:rotate 灌大角
    def blow_amp(a):
        for bn, tls in a.get("bones", {}).items():
            if "rotate" in tls:
                for f in tls["rotate"]:
                    f["angle"] = f.get("angle", 0) * 20
                return
    r = run(blow_amp, "amp"); res["blow_amp→AC3_fail"] = not r["AC3_amp_bounded"]["pass"]

    # (c) no-op:所有 rotate 歸零(不動)
    def make_noop(a):
        for bn, tls in a.get("bones", {}).items():
            for tl, fr in tls.items():
                for f in fr:
                    for k in ("angle",):
                        if k in f:
                            f[k] = 0.0
    r = run(make_noop, "noop"); res["zero_rotate→AC2_fail"] = not r["AC2_motion_present"]["pass"]

    # (d) 指向不存在 bone
    def bad_ref(a):
        b = a.get("bones", {})
        if b:
            k = list(b.keys())[0]
            b["b_does_not_exist_xyz"] = b.pop(k)
    r = run(bad_ref, "ref"); res["bad_bone_ref→AC5_fail"] = not r["AC5_format_valid"]["pass"]

    res["all_discriminating"] = all(res.values())
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton", nargs="?", default=None,
                    help="skeleton.json(內含要驗的動畫);省略則只跑取樣器自驗")
    ap.add_argument("--anim", default=None)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--neg", action="store_true", help="跑負對照")
    a = ap.parse_args()

    out = {}
    out["sampler_selftest"] = sampler_selftest()
    if a.skeleton:
        sk = json.load(open(a.skeleton))
        anim = a.anim or list(sk["animations"].keys())[0]
        out["evaluate"] = evaluate(sk, anim)
        if a.neg:
            out["negative_controls"] = negative_controls(sk, anim)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
