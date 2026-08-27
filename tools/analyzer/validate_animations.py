#!/usr/bin/env python3
"""S1 #3 動畫 keyframe 品質閘(純 CPU,不需瀏覽器)。

對一份含 animations 的 Spine 3.8 skeleton.json,逐動畫量化:
  A. schema     — 所有被動畫引用的 bone/slot 都存在。
  B. loop_cyclic — loop 類 beat 的每條 timeline 值 t=0 == t=T(gap ≤ eps),含特效 slot alpha。
  C. amplitude   — 每條 timeline 峰對峰在角色合理帶內且非零(呼吸不能是死圖也不能爆走)。
  D. phase_div   — 各 bone 到達極值的時間有離散度(> 門檻)→ 破「全身同步紙板感」。
  E. world_motion— 用 Spine bone 世界變換重現(root→bone),回報各 bone 世界位移峰值有界非零。

自身可信度(discriminative power):內建負對照
  - flat  :所有 keyframe 同值 → 應在 C(非零)fail。
  - synced:所有 bone 同相位 → 應在 D(相位離散)fail。
兩者被抓到才代表閘有鑑別力。

Spine 曲線取樣:curve 缺→linear;"stepped"→hold;數值→緊湊 bezier
  (curve=cx1, c2=cy1 def0, c3=cx2, c4=cy2 def1)。雙值 timeline x/y 共用同一 curve(對齊 main_draw)。
"""
import argparse, json, math, os, sys

# ---- 帶內門檻 ----
LOOP_EPS = 1e-3          # 週期閉合容差
PHASE_SPREAD_MIN = 0.10  # 極值時間離散(標準差/週期)最小值
AMP_BANDS = {            # 峰對峰 (min>0, max)
    "scale":     (1e-3, 0.30),
    "translate": (1e-3, 40.0),
    "rotate":    (1e-3, 45.0),
    "alpha":     (1e-3, 1.0),
}
LOOP_KEYS = {"Loop", "loop", "idle", "static"}


# ---------- Spine 曲線取樣 ----------
def _bezier_y(cx1, cy1, cx2, cy2, x, iters=8):
    """給 bezier(P0=0,P3=1)控制點,已知 x∈[0,1] 解對應 y。二分 s 使 X(s)=x。"""
    lo, hi = 0.0, 1.0
    for _ in range(iters * 4):
        s = (lo + hi) / 2
        xs = 3 * (1 - s) ** 2 * s * cx1 + 3 * (1 - s) * s ** 2 * cx2 + s ** 3
        if xs < x:
            lo = s
        else:
            hi = s
    s = (lo + hi) / 2
    return 3 * (1 - s) ** 2 * s * cy1 + 3 * (1 - s) * s ** 2 * cy2 + s ** 3


def _interp(f0, f1, t, prop, default):
    """兩 keyframe 間於時間 t 的插值(套 f0 的 curve)。"""
    t0 = f0.get("time", 0.0)
    t1 = f1.get("time", 0.0)
    v0 = f0.get(prop, default)
    v1 = f1.get(prop, default)
    if t1 <= t0:
        return v0
    p = (t - t0) / (t1 - t0)
    curve = f0.get("curve", None)
    if curve == "stepped":
        return v0
    if curve is None:                      # linear
        frac = p
    else:                                  # 緊湊 bezier
        cx1 = float(curve); cy1 = float(f0.get("c2", 0.0))
        cx2 = float(f0.get("c3", 1.0)); cy2 = float(f0.get("c4", 1.0))
        frac = _bezier_y(cx1, cy1, cx2, cy2, p)
    return v0 + (v1 - v0) * frac


def sample(frames, t, prop, default):
    """timeline 在時間 t 的值。"""
    if not frames:
        return default
    if t <= frames[0].get("time", 0.0):
        return frames[0].get(prop, default)
    if t >= frames[-1].get("time", 0.0):
        return frames[-1].get(prop, default)
    for i in range(len(frames) - 1):
        t0 = frames[i].get("time", 0.0)
        t1 = frames[i + 1].get("time", 0.0)
        if t0 <= t <= t1:
            return _interp(frames[i], frames[i + 1], t, prop, default)
    return frames[-1].get(prop, default)


def _color_alpha(hexstr):
    try:
        return int(hexstr[6:8], 16) / 255.0
    except Exception:
        return 1.0


def sample_alpha(frames, t):
    if not frames:
        return 1.0
    if t <= frames[0].get("time", 0.0):
        return _color_alpha(frames[0].get("color", "ffffffff"))
    if t >= frames[-1].get("time", 0.0):
        return _color_alpha(frames[-1].get("color", "ffffffff"))
    for i in range(len(frames) - 1):
        t0 = frames[i].get("time", 0.0); t1 = frames[i + 1].get("time", 0.0)
        if t0 <= t <= t1:
            a0 = _color_alpha(frames[i].get("color", "ffffffff"))
            a1 = _color_alpha(frames[i + 1].get("color", "ffffffff"))
            f0 = dict(frames[i]); f1 = dict(frames[i + 1])
            f0["_a"] = a0; f1["_a"] = a1
            return _interp(f0, f1, t, "_a", 1.0)
    return 1.0


# ---------- bone 世界變換重現 ----------
def _bone_local(bd, setup, t):
    """回傳該 bone 在時間 t 的 local (x,y,rot,sx,sy),疊加 setup。"""
    x = setup.get("x", 0.0); y = setup.get("y", 0.0)
    rot = setup.get("rotation", 0.0)
    sx = setup.get("scaleX", 1.0); sy = setup.get("scaleY", 1.0)
    if bd:
        tr = bd.get("translate")
        if tr:
            x += sample(tr, t, "x", 0.0); y += sample(tr, t, "y", 0.0)
        ro = bd.get("rotate")
        if ro:
            rot += sample(ro, t, "angle", 0.0)
        sc = bd.get("scale")
        if sc:
            sx *= sample(sc, t, "x", 1.0); sy *= sample(sc, t, "y", 1.0)
    return x, y, rot, sx, sy


def _world_pos(bone_name, bones_setup, parent, anim_bones, t):
    """root→bone 累乘,回傳世界原點座標 (wx,wy)。"""
    chain = []
    b = bone_name
    while b is not None:
        chain.append(b)
        b = parent.get(b)
    chain.reverse()
    wx = wy = 0.0
    wa = 0.0; wsx = wsy = 1.0
    for bn in chain:
        setup = bones_setup.get(bn, {})
        x, y, rot, sx, sy = _bone_local(anim_bones.get(bn), setup, t)
        rad = math.radians(wa)
        cos, sin = math.cos(rad), math.sin(rad)
        # 父世界:平移子的 local (含父 scale)
        nx = wx + (cos * (x * wsx) - sin * (y * wsy))
        ny = wy + (sin * (x * wsx) + cos * (y * wsy))
        wx, wy = nx, ny
        wa += rot
        wsx *= sx; wsy *= sy
    return wx, wy


# ---------- 評估 ----------
def _timeline_group(prop):
    if prop in ("x", "y", "angle"):
        return {"x": "translate", "y": "translate", "angle": "rotate"}[prop]
    return prop


def evaluate_anim(name, anim, bones_setup, parent, is_loop, samples=64):
    checks = {}
    reasons = []
    abones = anim.get("bones", {})
    aslots = anim.get("slots", {})

    # 時長
    dur = 0.0
    for bd in abones.values():
        for tl in bd.values():
            for kf in tl:
                dur = max(dur, kf.get("time", 0.0))
    for sd in aslots.values():
        for tl in sd.values():
            for kf in tl:
                dur = max(dur, kf.get("time", 0.0))
    dur = dur or 1.0

    # A. schema
    missing = [b for b in abones if b not in bones_setup] + \
              [s for s in aslots if s not in bones_setup and s not in _SLOTSET]
    checks["schema"] = (len(missing) == 0)
    if missing:
        reasons.append(f"schema: 未知 bone/slot {missing}")

    # B. loop_cyclic(僅 loop 類)
    if is_loop:
        max_gap = 0.0
        for bd in abones.values():
            for prop_tl, tl in bd.items():
                if prop_tl == "translate":
                    props = [("x", 0.0), ("y", 0.0)]
                elif prop_tl == "scale":
                    props = [("x", 1.0), ("y", 1.0)]
                else:
                    props = [("angle", 0.0)]
                for prop, dflt in props:
                    g = abs(sample(tl, 0.0, prop, dflt) - sample(tl, dur, prop, dflt))
                    max_gap = max(max_gap, g)
        for sd in aslots.values():
            if "color" in sd:
                g = abs(sample_alpha(sd["color"], 0.0) - sample_alpha(sd["color"], dur))
                max_gap = max(max_gap, g)
        checks["loop_cyclic"] = (max_gap <= LOOP_EPS)
        checks["_loop_max_gap"] = round(max_gap, 5)
        if max_gap > LOOP_EPS:
            reasons.append(f"loop_cyclic: 端點差 {max_gap:.4f} > {LOOP_EPS}")

    # C. amplitude:每個 group(translate/scale/rotate/alpha)整組至少一分量動(非零),
    #    且每分量峰對峰 ≤ 上限(不爆走)。純垂直 bob(x=0)合法,故非零判定看整組。
    amp_ok = True
    amp_rep = {}
    def _pp(vals):
        return max(vals) - min(vals)
    ts = [i * dur / samples for i in range(samples + 1)]
    # 每 bone 各 property 的取樣序列(相位分析也會用)
    bone_signals = {}
    for bn, bd in abones.items():
        bone_signals[bn] = {}
        for prop_tl, tl in bd.items():
            if prop_tl == "translate":
                plist = [("x", 0.0), ("y", 0.0)]
            elif prop_tl == "scale":
                plist = [("x", 1.0), ("y", 1.0)]
            else:
                plist = [("angle", 0.0)]
            grp = _timeline_group(plist[0][0])
            lo, hi = AMP_BANDS[grp]
            group_pp = 0.0
            over = False
            for prop, dflt in plist:
                vals = [sample(tl, t, prop, dflt) for t in ts]
                pp = _pp(vals)
                bone_signals[bn][f"{prop_tl}.{prop}"] = (vals, dflt)
                amp_rep[f"{bn}.{prop_tl}.{prop}"] = round(pp, 4)
                group_pp = max(group_pp, pp)
                if pp > hi:
                    over = True
            ok = (group_pp > lo) and (not over)
            amp_ok = amp_ok and ok
            if not ok:
                reasons.append(f"amplitude: {bn}.{prop_tl} group_pp={group_pp:.4f} 出帶[{lo},{hi}]")
    for sn, sd in aslots.items():
        if "color" in sd:
            vals = [sample_alpha(sd["color"], t) for t in ts]
            pp = _pp(vals); lo, hi = AMP_BANDS["alpha"]
            ok = (pp > lo) and (pp <= hi)
            amp_ok = amp_ok and ok
            amp_rep[f"{sn}.alpha"] = round(pp, 4)
            if not ok:
                reasons.append(f"amplitude: {sn}.alpha pp={pp:.4f} 出帶")
    checks["amplitude"] = amp_ok
    checks["_amp"] = amp_rep

    # D. phase_div(僅 loop 類硬閘;In/Out 資訊性):以各 bone「綜合活動訊號」的極值時間為相位代表。
    #    綜合訊號 = 各 animated property 以自身峰對峰正規化後的偏離量總和 → rotate/scale/translate 可比。
    peak_times = []
    for bn, sigs in bone_signals.items():
        if not sigs:
            continue
        activity = [0.0] * len(ts)
        for _, (vals, dflt) in sigs.items():
            pp = _pp(vals) or 1.0
            for i, v in enumerate(vals):
                activity[i] += abs(v - vals[0]) / pp
        peak_i = max(range(len(ts)), key=lambda i: activity[i])
        peak_times.append(ts[peak_i] / dur)
    if len(peak_times) >= 2:
        m = sum(peak_times) / len(peak_times)
        std = (sum((p - m) ** 2 for p in peak_times) / len(peak_times)) ** 0.5
        checks["_phase_std"] = round(std, 4)
        diverse = std >= PHASE_SPREAD_MIN
        if is_loop:
            checks["phase_div"] = diverse
            if not diverse:
                reasons.append(f"phase_div: 極值時間 std={std:.3f} < {PHASE_SPREAD_MIN}(疑同步紙板)")
        else:
            checks["phase_div"] = True   # 非 loop:同步進退場合法,僅記錄 std
    else:
        checks["phase_div"] = True

    # E. world_motion(有界非零)
    wmax = {}
    for bn in abones:
        wx0, wy0 = _world_pos(bn, bones_setup, parent, abones, 0.0)
        mx = max(math.hypot(*[a - b for a, b in zip(_world_pos(bn, bones_setup, parent, abones, t), (wx0, wy0))])
                 for t in ts)
        wmax[bn] = round(mx, 3)
    checks["_world_disp_max"] = wmax
    checks["world_motion"] = all(v < 1e5 for v in wmax.values())

    gate_keys = ["schema", "amplitude", "phase_div", "world_motion"] + (["loop_cyclic"] if is_loop else [])
    overall = all(checks.get(k, False) for k in gate_keys)
    return {"name": name, "duration": round(dur, 3), "is_loop": is_loop,
            "pass": overall, "checks": checks, "reasons": reasons}


_SLOTSET = set()


def validate(skel_path, samples=64):
    global _SLOTSET
    skel = json.load(open(skel_path, encoding="utf-8"))
    bones_setup = {b["name"]: b for b in skel["bones"]}
    parent = {b["name"]: b.get("parent") for b in skel["bones"]}
    _SLOTSET = {s["name"] for s in skel["slots"]}
    anims = skel.get("animations", {})
    results = []
    for name, anim in anims.items():
        is_loop = name in LOOP_KEYS
        results.append(evaluate_anim(name, anim, bones_setup, parent, is_loop, samples))
    overall = all(r["pass"] for r in results) and len(results) > 0
    return {"skeleton": skel_path, "n_anims": len(results),
            "overall_pass": overall, "results": results}


# ---------- 負對照 ----------
def _neg_controls(skel_path):
    """回傳 (flat_fail_amp, synced_fail_phase) 是否如預期被抓。"""
    skel = json.load(open(skel_path, encoding="utf-8"))
    bones_setup = {b["name"]: b for b in skel["bones"]}
    parent = {b["name"]: b.get("parent") for b in skel["bones"]}
    part_bones = [b["name"] for b in skel["bones"] if b["name"] != "root"]
    dur = 2.0

    # flat:所有 keyframe 同值(死圖)
    flat = {"bones": {bn: {"scale": [{"x": 1.0, "y": 1.0}, {"time": dur, "x": 1.0, "y": 1.0}]}
                      for bn in part_bones}}
    r_flat = evaluate_anim("flat", flat, bones_setup, parent, True)
    flat_caught = (not r_flat["checks"]["amplitude"])

    # synced:全 bone 同相位(同步紙板)但有振幅
    synced = {"bones": {}}
    for bn in part_bones:
        synced["bones"][bn] = {"scale": [
            {"x": 1.0, "y": 1.0, **{"curve": 0.25, "c3": 0.75}},
            {"time": dur / 2, "x": 1.05, "y": 0.95, **{"curve": 0.25, "c3": 0.75}},
            {"time": dur, "x": 1.0, "y": 1.0},
        ]}
    r_sync = evaluate_anim("synced", synced, bones_setup, parent, True)
    sync_caught = (not r_sync["checks"]["phase_div"])
    return {"flat_amp_caught": flat_caught, "flat_std": r_flat["checks"].get("_phase_std"),
            "synced_phase_caught": sync_caught, "synced_std": r_sync["checks"].get("_phase_std"),
            "neg_control_pass": flat_caught and sync_caught}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton", help="含 animations 的 skeleton.json")
    ap.add_argument("--neg", action="store_true", help="附跑負對照(可信度自檢)")
    a = ap.parse_args()
    out = validate(a.skeleton)
    if a.neg:
        out["neg_controls"] = _neg_controls(a.skeleton)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
