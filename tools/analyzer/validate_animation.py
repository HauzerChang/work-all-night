#!/usr/bin/env python3
"""動畫 keyframe 自我品質閘(storyboard→animation 的評估器)。

對 animate_spine.py 產出的 Spine animations 做**幾何量化**驗收(純 CPU,不靠肉眼)。
判準以真實生產動畫校準(main_draw / Award);評估器可信度由「真值自一致 + 負對照」雙向確認:
  * 真值錨:main_draw_loop / main_idle 的 bone timeline 首末差 == 0(嚴格無縫)。
  * 負對照:蓄意破壞(非無縫 Loop / 超幅 / 同相位)必須被判 FAIL。

AC(逐條 pass/fail + 量化差距):
  A1 結構      :每 timeline 參照的 bone/slot 存在於 skeleton;數值有限(無 NaN/Inf)。
  A2 Loop 無縫 :每 channel 首 keyframe 值 == 末 keyframe 值(eps 1e-4)。
  A3 有動作    :Loop 對出現的每種 role 都產生非零振幅(body/head/limb/effect)。
  A4 幅度有界  :Loop rotate range ≤15° / scale range ≤0.15 / translate range ≤35px / alpha∈[0,1]。
  A5 相位錯開  :≥2 limb 時,rotate 軌跡峰值時間需分散(spread ≥0.05·T)或兩兩相關<0.99。
  A6 轉場連續  :In.末 ≈ Loop.首 且 Out.首 ≈ Loop.首(eps);In/Out 本身非無縫(是真轉場)。
"""
import argparse, json, math, os, sys

EPS = 1e-4
BAND = {"rotate": 15.0, "scale": 0.15, "translate": 35.0}
PHASE_SPREAD = 0.05


# ── keyframe 取值 / 取樣 ──────────────────────────────────────────
def _val(kf, prop):
    if prop == "angle":
        return kf.get("angle", 0.0)
    if prop in ("x", "y"):
        # scale 預設 1、translate 預設 0 — 由呼叫端指定 default
        return kf.get(prop)
    return None


def _channel_vals(frames, prop, default):
    return [(k.get("time", 0.0), k.get(prop, default)) for k in frames]


def _alpha_of(colorhex):
    return int(colorhex[6:8], 16) / 255.0 if len(colorhex) >= 8 else 1.0


def _sample_linear(tv, t):
    """線性內插 [(time,val)] 在 t 的值(Spine 預設 channel 內插=線性)。"""
    if t <= tv[0][0]:
        return tv[0][1]
    if t >= tv[-1][0]:
        return tv[-1][1]
    for (t0, v0), (t1, v1) in zip(tv, tv[1:]):
        if t0 <= t <= t1:
            r = 0 if t1 == t0 else (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * r
    return tv[-1][1]


def _iter_channels(anim):
    """yield (kind, name, prop, [(time,val)], default) 給 bones(rotate/scale/translate)。"""
    for bn, tl in anim.get("bones", {}).items():
        if "rotate" in tl:
            yield ("rotate", bn, "angle", _channel_vals(tl["rotate"], "angle", 0.0), 0.0)
        if "scale" in tl:
            yield ("scale", bn, "x", _channel_vals(tl["scale"], "x", 1.0), 1.0)
            yield ("scale", bn, "y", _channel_vals(tl["scale"], "y", 1.0), 1.0)
        if "translate" in tl:
            yield ("translate", bn, "x", _channel_vals(tl["translate"], "x", 0.0), 0.0)
            yield ("translate", bn, "y", _channel_vals(tl["translate"], "y", 0.0), 0.0)


def _slot_alpha_channels(anim):
    for sn, tl in anim.get("slots", {}).items():
        if "color" in tl:
            yield sn, [(k.get("time", 0.0), _alpha_of(k.get("color", "ffffffff"))) for k in tl["color"]]


def _duration(anim):
    t = 0.0
    for _, _, _, tv, _ in _iter_channels(anim):
        t = max(t, tv[-1][0])
    for _, tv in _slot_alpha_channels(anim):
        t = max(t, tv[-1][0])
    return t


# ── 各 AC ────────────────────────────────────────────────────────
def check_structure(anims, bone_names, slot_names):
    bad = []
    for an, ad in anims.items():
        for bn in ad.get("bones", {}):
            if bn not in bone_names:
                bad.append(f"{an}:bone {bn} 不存在")
        for sn in ad.get("slots", {}):
            if sn not in slot_names:
                bad.append(f"{an}:slot {sn} 不存在")
        for _, name, prop, tv, _ in _iter_channels(ad):
            for _, v in tv:
                if not math.isfinite(v):
                    bad.append(f"{an}:{name}.{prop} 非有限值")
        for sn, tv in _slot_alpha_channels(ad):
            for _, v in tv:
                if not math.isfinite(v):
                    bad.append(f"{an}:{sn}.alpha 非有限值")
    return {"pass": not bad, "issues": bad[:10]}


def check_loop_seamless(loop):
    worst = 0.0; worst_ch = None
    for kind, name, prop, tv, _ in _iter_channels(loop):
        d = abs(tv[0][1] - tv[-1][1])
        if d > worst:
            worst, worst_ch = d, f"{name}.{prop}"
    for sn, tv in _slot_alpha_channels(loop):
        d = abs(tv[0][1] - tv[-1][1])
        if d > worst:
            worst, worst_ch = d, f"{sn}.alpha"
    return {"pass": worst <= EPS, "max_first_last_diff": round(worst, 6), "channel": worst_ch}


def check_motion_present(loop, role_by_bone, role_by_slot):
    seen = {}
    for kind, name, prop, tv, _ in _iter_channels(loop):
        role = role_by_bone.get(name)
        amp = max(v for _, v in tv) - min(v for _, v in tv)
        if amp > EPS:
            seen[role] = max(seen.get(role, 0), amp)
    for sn, tv in _slot_alpha_channels(loop):
        role = role_by_slot.get(sn)
        amp = max(v for _, v in tv) - min(v for _, v in tv)
        if amp > EPS:
            seen[role] = max(seen.get(role, 0), amp)
    expected = set(role_by_bone.values()) | set(role_by_slot.values())
    missing = [r for r in expected if r and seen.get(r, 0) <= EPS]
    return {"pass": not missing, "roles_with_motion": {k: round(v, 3) for k, v in seen.items() if k},
            "roles_missing_motion": missing}


def check_amplitude_bounded(loop):
    over = []; ranges = {}
    for kind, name, prop, tv, _ in _iter_channels(loop):
        amp = max(v for _, v in tv) - min(v for _, v in tv)
        ranges.setdefault(kind, 0.0)
        ranges[kind] = max(ranges[kind], amp)
        if amp > BAND[kind] + EPS:
            over.append(f"{name}.{prop} {kind}={amp:.3f}>{BAND[kind]}")
    for sn, tv in _slot_alpha_channels(loop):
        for _, v in tv:
            if v < -EPS or v > 1 + EPS:
                over.append(f"{sn}.alpha={v:.3f} 越界[0,1]")
    return {"pass": not over, "max_range_per_kind": {k: round(v, 3) for k, v in ranges.items()},
            "violations": over[:10]}


def check_phase_offset(loop, role_by_bone):
    dur = _duration(loop) or 1.0
    trajs = []
    for kind, name, prop, tv, _ in _iter_channels(loop):
        if kind == "rotate" and role_by_bone.get(name) == "limb":
            samp = [_sample_linear(tv, dur * i / 40) for i in range(41)]
            trajs.append((name, samp))
    if len(trajs) < 2:
        return {"pass": True, "note": "limb<2,不適用", "n_limb": len(trajs)}
    # 峰值時間分散
    peaks = [max(range(len(s)), key=lambda i: s[i]) / 40.0 for _, s in trajs]
    spread = max(peaks) - min(peaks)
    # 最大兩兩相關
    def corr(a, b):
        n = len(a); ma = sum(a) / n; mb = sum(b) / n
        va = sum((x - ma) ** 2 for x in a); vb = sum((x - mb) ** 2 for x in b)
        if va == 0 or vb == 0:
            return 1.0
        cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
        return cov / math.sqrt(va * vb)
    maxcorr = 0.0
    for i in range(len(trajs)):
        for j in range(i + 1, len(trajs)):
            maxcorr = max(maxcorr, abs(corr(trajs[i][1], trajs[j][1])))
    ok = spread >= PHASE_SPREAD or maxcorr < 0.99
    return {"pass": ok, "n_limb": len(trajs), "peak_time_spread": round(spread, 3),
            "max_pairwise_corr": round(maxcorr, 3)}


def _neutral_at(anim, t, bone_names_props):
    """回傳 {(bone,prop): value} 在時間 t(線性取樣)。bone_names_props 決定要取哪些 channel。"""
    out = {}
    # 以 (kind,name,prop) 為鍵:scale 與 translate 都用 x/y,不含 kind 會互相覆蓋。
    for kind, name, prop, tv, default in _iter_channels(anim):
        out[(kind, name, prop)] = _sample_linear(tv, t)
    for sn, tv in _slot_alpha_channels(anim):
        out[("slot", sn, "alpha")] = _sample_linear(tv, t)
    return out


LOOP_KEYS = {"loop"}
ENTER_KEYS = {"in", "comeout", "land", "static"}
EXIT_KEYS = {"out", "close"}


def _find_loop(anims):
    for k in anims:
        if k.lower() in LOOP_KEYS or k.lower() == "idle":
            return k
    return None


def check_transitions(anims):
    lk = _find_loop(anims)
    if not lk:
        return {"pass": True, "note": "無 loop 類 beat,略過"}
    loop = anims[lk]
    loop_first = _neutral_at(loop, 0.0, None)
    issues = []; checked = 0
    edges = [(k, "last") for k in anims if k.lower() in ENTER_KEYS]
    edges += [(k, "first") for k in anims if k.lower() in EXIT_KEYS]
    for beat, edge in edges:
        ad = anims[beat]
        dur = _duration(ad)
        t = dur if edge == "last" else 0.0
        vals = _neutral_at(ad, t, None)
        # 非無縫(是真轉場):該 beat 首末需不同
        v0 = _neutral_at(ad, 0.0, None); v1 = _neutral_at(ad, dur, None)
        seam = max((abs(v0.get(k, 0) - v1.get(k, 0)) for k in set(v0) | set(v1)), default=0)
        if seam <= EPS:
            issues.append(f"{beat} 首末相同(非真轉場)")
        # 邊界 ≈ Loop.首
        for k, v in vals.items():
            if k in loop_first:
                d = abs(v - loop_first[k])
                if d > 1e-2:   # 轉場連續容忍 0.01
                    issues.append(f"{beat}.{edge} {k} 與 Loop.首差 {d:.3f}")
                    checked += 1
    return {"pass": not issues, "issues": issues[:10]}


# ── 主驗證 ───────────────────────────────────────────────────────
def validate(skeleton_json, role_by_bone, role_by_slot):
    sk = json.load(open(skeleton_json)) if isinstance(skeleton_json, str) else skeleton_json
    anims = sk.get("animations", {})
    bone_names = {b["name"] for b in sk["bones"]}
    slot_names = {s["name"] for s in sk["slots"]}
    lk = _find_loop(anims)
    loop = anims.get(lk, {}) if lk else {}
    res = {
        "loop_beat": lk,
        "A1_structure": check_structure(anims, bone_names, slot_names),
        "A2_loop_seamless": check_loop_seamless(loop) if loop else {"pass": False, "note": "無 Loop"},
        "A3_motion_present": check_motion_present(loop, role_by_bone, role_by_slot) if loop else {"pass": False},
        "A4_amplitude_bounded": check_amplitude_bounded(loop) if loop else {"pass": False},
        "A5_phase_offset": check_phase_offset(loop, role_by_bone) if loop else {"pass": False},
        "A6_transitions": check_transitions(anims),
    }
    res["overall_pass"] = all(v.get("pass") for v in res.values()
                              if isinstance(v, dict) and "pass" in v)
    return res


def roles_from_spec(spec):
    """從 analyze 的 storyboard 取 role_by_bone / role_by_slot(件→bone/slot 名慣例)。"""
    def safe(n):
        return n.replace("/", "_").replace("\\", "_").replace(" ", "_")
    loop = next((b for b in spec["3_motion_storyboard"]["beats"] if b["beat"] == "Loop"), None)
    rb, rs = {}, {}
    if loop:
        for p in loop["parts"]:
            role = "effect" if p["role"] == "特效" else p["role"]
            rb["b_" + safe(p["part"])] = role
            rs[safe(p["part"])] = role
    return rb, rs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton", help="含 animations 的 skeleton.json")
    ap.add_argument("--psd", help="原 PSD(取 roles;不給則從 --genre 猜不出角色→A3 略過角色對照)")
    ap.add_argument("--genre", default="slot_bigwin")
    a = ap.parse_args()
    rb, rs = {}, {}
    if a.psd:
        sys.path.insert(0, os.path.dirname(__file__))
        from analyze_target import analyze
        rb, rs = roles_from_spec(analyze(a.psd, a.genre))
    res = validate(a.skeleton, rb, rs)
    print(json.dumps(res, ensure_ascii=False, indent=2))
    sys.exit(0 if res["overall_pass"] else 1)


if __name__ == "__main__":
    main()
