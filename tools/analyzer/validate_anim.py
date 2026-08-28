#!/usr/bin/env python3
"""candidate 0d 自我驗收閘 — 量化 storyboard→animation keyframe 是否達標(純 CPU,不靠肉眼)。

對 gen_animations.py 產出的 animations,用 spine_anim.py 取樣後逐條 AC 判定:

  AC1 well-formed  : 每支動畫 timeline 時間嚴格遞增、值皆有限、JSON round-trip。
  AC2 loop seamless: Loop 每通道 value(0) == value(duration)(呼吸無縫)。
  AC3 amplitude/相位: body scale 微呼吸(小幅非零)、head 點頭(小角度)、
                       limb 左右**反相**(某 t 兩手角度異號)、特效 alpha 脈動。
  AC4 beat chaining : In 尾 == setup identity == Loop 首/尾 == Out 首;In 有 overshoot(scale>1);
                       Out 收斂(scale/alpha→~0)。
  AC5 evaluator credibility: 對蓄意破壞的動畫(打斷 Loop 無縫 / In 不歸位)必須 FAIL(負對照)。

用法:
  python3 validate_anim.py <skeleton.json>            # 驗真實產出
  python3 validate_anim.py <skeleton.json> --selftest # 額外跑 AC5 負對照
"""
import argparse, copy, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
import spine_anim as SA
from gen_animations import beat_category

IDENT = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
EPS_SEAM = 1e-6     # 無縫容差
EPS_IDENT = 1e-6    # identity 容差
COLLAPSE = 0.05     # Out/In 端點「收合」判定(scale/alpha ≤)


def _bones_at(anim, t):
    return SA.sample(anim, t)["bones"]


def _slots_at(anim, t):
    return SA.sample(anim, t)["slots"]


def check_ac1(anims):
    """well-formed + JSON round-trip。"""
    detail = {}
    ok = True
    for name, a in anims.items():
        fin = SA.all_finite(a)
        try:
            rt = json.loads(json.dumps(a)) == a
        except Exception:
            rt = False
        detail[name] = {"finite_monotonic": fin, "roundtrip": rt}
        ok = ok and fin and rt
    return ok, detail


def _find_cat(anims, cat):
    """回傳第一支類別==cat 的 (name, anim);無則 (None, None)。"""
    for name, a in anims.items():
        if beat_category(name) == cat:
            return name, a
    return None, None


def check_ac2(anims):
    """loop 類別無縫:每 bone 每通道 value(0)==value(dur);slot alpha 同。"""
    lname, a = _find_cat(anims, "loop")
    if not a:
        return False, {"error": "no loop-category anim"}
    dur = SA.duration(a)
    b0, bE = _bones_at(a, 0.0), _bones_at(a, dur)
    s0, sE = _slots_at(a, 0.0), _slots_at(a, dur)
    max_err = 0.0
    for bone in b0:
        for k in ("rotate", "x", "y", "scaleX", "scaleY"):
            max_err = max(max_err, abs(b0[bone][k] - bE[bone][k]))
    for slot in s0:
        max_err = max(max_err, abs(s0[slot]["alpha"] - sE[slot]["alpha"]))
    ok = max_err <= EPS_SEAM
    return ok, {"loop_anim": lname, "duration": dur, "max_endpoint_err": max_err, "tol": EPS_SEAM}


def _channel_range(anim, bone, key, n=48):
    dur = SA.duration(anim)
    vals = []
    for i in range(n + 1):
        t = dur * i / n
        d = _bones_at(anim, t)[bone]
        vals.append(d[key])
    return min(vals), max(vals)


def check_ac3(anims, storyboard):
    """幅度/相位與 role 相符。"""
    lname, a = _find_cat(anims, "loop")
    if not a:
        return False, {"error": "no loop-category anim"}
    # role → 件名(取 loop 類別那個 beat 的 parts)
    loop_beat = next((b for b in storyboard["beats"] if b["beat"] == lname), None)
    if loop_beat is None:
        return False, {"error": "loop beat not in storyboard"}
    parts = {p["part"]: p["role"] for p in loop_beat["parts"]}
    detail = {}
    ok = True

    def bname(part):
        return "b_" + part.replace("/", "_").replace("\\", "_").replace(" ", "_")

    # body 呼吸(scale 幅度 0.5%~8%)
    bodies = [p for p, r in parts.items() if r == "body"]
    for p in bodies:
        lo, hi = _channel_range(a, bname(p), "scaleX")
        amp = (hi - lo) / 2.0
        good = 0.005 <= amp <= 0.08
        detail[f"body:{p}:scale_amp"] = {"amp": round(amp, 4), "pass": good}
        ok = ok and good
    # head 點頭(rotate 幅度 0.5°~8°)
    for p in [p for p, r in parts.items() if r == "head"]:
        lo, hi = _channel_range(a, bname(p), "rotate")
        amp = (hi - lo) / 2.0
        good = 0.5 <= amp <= 8.0
        detail[f"head:{p}:rot_amp_deg"] = {"amp": round(amp, 3), "pass": good}
        ok = ok and good
    # limb 反相:找兩件 limb,在某 t 角度異號
    limbs = [p for p, r in parts.items() if r == "limb"]
    if len(limbs) >= 2:
        dur = SA.duration(a)
        antiphase = False
        for i in range(1, 48):
            t = dur * i / 48
            r0 = _bones_at(a, t)[bname(limbs[0])]["rotate"]
            r1 = _bones_at(a, t)[bname(limbs[1])]["rotate"]
            if r0 * r1 < -1e-3:          # 異號 → 反相
                antiphase = True
                break
        detail["limb:antiphase"] = {"limbs": limbs[:2], "pass": antiphase}
        ok = ok and antiphase
    # 特效 alpha 脈動(range ≥ 5%)
    for p in [p for p, r in parts.items() if r == "特效"]:
        sname = p.replace("/", "_").replace("\\", "_").replace(" ", "_")
        dur = SA.duration(a)
        avals = [_slots_at(a, dur * i / 48)[sname]["alpha"] for i in range(49)] if sname in _slots_at(a, 0.0) else [1.0]
        rng = max(avals) - min(avals)
        good = rng >= 0.05
        detail[f"fx:{p}:alpha_range"] = {"range": round(rng, 4), "pass": good}
        ok = ok and good
    return ok, detail


def _is_ident(bd, tol=EPS_IDENT):
    return all(abs(bd[k] - IDENT[k]) <= tol for k in IDENT)


def check_ac4(anims):
    """beat chaining + In overshoot + Out collapse。"""
    detail = {}
    ok = True
    _, In = _find_cat(anims, "intro")
    _, Loop = _find_cat(anims, "loop")
    _, Out = _find_cat(anims, "outro")
    # In 尾 == identity(每 bone)
    if In:
        dIn = SA.duration(In)
        endb = _bones_at(In, dIn)
        ends = _slots_at(In, dIn)
        in_end_ident = all(_is_ident(v) for v in endb.values()) and all(abs(s["alpha"] - 1.0) <= 1e-6 for s in ends.values())
        # In 起始收合(scale 小 或 alpha 0)
        startb = _bones_at(In, 0.0); starts = _slots_at(In, 0.0)
        in_start_collapsed = all(startb[b]["scaleX"] <= COLLAPSE for b in startb) or all(s["alpha"] <= COLLAPSE for s in starts.values())
        # overshoot:某 t scale>1.02
        overshoot = False
        for i in range(1, 40):
            t = dIn * i / 40
            if any(_bones_at(In, t)[b]["scaleX"] > 1.02 for b in endb):
                overshoot = True; break
        detail["In"] = {"end_identity": in_end_ident, "start_collapsed": in_start_collapsed, "overshoot": overshoot}
        ok = ok and in_end_ident and in_start_collapsed and overshoot
    # Loop 首 == identity(與 In 尾接得上)
    if Loop:
        loop_start_ident = all(_is_ident(v, 1e-4) for v in _bones_at(Loop, 0.0).values())
        detail["Loop_start_identity"] = loop_start_ident
        ok = ok and loop_start_ident
    # Out 首 == identity;尾收合
    if Out:
        dOut = SA.duration(Out)
        out_start_ident = all(_is_ident(v) for v in _bones_at(Out, 0.0).values())
        endb = _bones_at(Out, dOut); ends = _slots_at(Out, dOut)
        out_end_collapsed = all(endb[b]["scaleX"] <= COLLAPSE for b in endb) and all(s["alpha"] <= COLLAPSE for s in ends.values())
        detail["Out"] = {"start_identity": out_start_ident, "end_collapsed": out_end_collapsed}
        ok = ok and out_start_ident and out_end_collapsed
    return ok, detail


def run_all(skeleton, storyboard):
    anims = skeleton["animations"]
    res = {}
    res["AC1_wellformed"] = check_ac1(anims)
    res["AC2_loop_seamless"] = check_ac2(anims)
    res["AC3_amplitude_phase"] = check_ac3(anims, storyboard)
    res["AC4_beat_chaining"] = check_ac4(anims)
    return res


def selftest_negative(skeleton, storyboard):
    """AC5:蓄意破壞 → 對應 AC 必須 FAIL。"""
    out = {}
    # (a) 打斷 loop 無縫:平移最後一個 loop scale 幀
    bad = copy.deepcopy(skeleton)
    lname, loop = _find_cat(bad["animations"], "loop")
    for bone, ch in (loop or {}).get("bones", {}).items():
        if "scale" in ch:
            ch["scale"][-1]["x"] += 0.05    # 尾端與首端不等
            break
    ok, _ = check_ac2(bad["animations"])
    out["broken_loop_seam_detected"] = (ok is False)
    # (b) intro 不歸位:把 intro 尾 scale 設成非 1
    bad2 = copy.deepcopy(skeleton)
    iname, In = _find_cat(bad2["animations"], "intro")
    for bone, ch in (In or {}).get("bones", {}).items():
        if "scale" in ch:
            ch["scale"][-1]["x"] = 1.5; ch["scale"][-1]["y"] = 1.5
            break
    ok2, _ = check_ac4(bad2["animations"])
    out["broken_in_return_detected"] = (ok2 is False)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton_json")
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    from analyze_target import analyze
    sk = json.load(open(a.skeleton_json, encoding="utf-8"))
    sb = analyze(a.psd, a.genre)["3_motion_storyboard"]
    res = run_all(sk, sb)
    overall = all(v[0] for v in res.values())
    report = {"overall_pass": overall,
              "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()}}
    if a.selftest:
        neg = selftest_negative(sk, sb)
        report["AC5_negative_control"] = {"pass": all(neg.values()), "detail": neg}
        report["overall_pass"] = overall and all(neg.values())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
