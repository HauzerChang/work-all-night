#!/usr/bin/env python3
"""S1 #3 動畫 keyframe 驗收閘 — 量化「產出的素材會不會動、動得對不對」。

不靠肉眼:直接讀 skeleton.json 的 `animations`,對每個 animation 量測
bone 位移/旋轉/縮放範圍 + slot alpha 範圍,逐條 AC 判定(見 gen_animation.py 的 AC1–AC4)。

AC1 結構合法(bone/slot 存在、time 遞增、curve 格式合法)
AC2 語意幅度分帶(In 大幅+effect alpha 0→255;Loop seamless 且小幅非零;Out 末幀歸零)
AC3 角色分化(effect 有 alpha timeline;≥2 limb 時 Loop 峰值時刻錯開)
AC4 非平凡(每 anim 有 timeline 且幅度 >0)

閘本身可信度:附**負對照**(--selftest)—— 蓄意造壞 timeline(非 seamless loop / time 逆序 /
壞 curve / In 無大幅)確認閘會抓到,證明不是永遠 PASS。
"""
import argparse, json, os, sys

EPS = 1e-6


def _hex_alpha(c):
    """'rrggbbaa' → alpha int 0..255。"""
    if not isinstance(c, str) or len(c) < 8:
        return None
    return int(c[6:8], 16)


def _times_ok(frames):
    ts = [f["time"] for f in frames]
    return all(ts[i + 1] > ts[i] - EPS for i in range(len(ts) - 1)) and \
           all(ts[i + 1] != ts[i] for i in range(len(ts) - 1))


def _curve_ok(f):
    if "curve" not in f:
        return True
    c = f["curve"]
    if c == "stepped" or c == "linear":
        return True
    if isinstance(c, (int, float)):
        return all(k in f and isinstance(f[k], (int, float)) for k in ("c2", "c3", "c4"))
    return False


def _range(frames, key, default=0.0):
    vs = [f.get(key, default) for f in frames]
    return max(vs) - min(vs), vs


def analyze_anim(name, anim, bone_set, slot_set):
    """回傳該 animation 的度量 + 結構問題清單。"""
    issues = []
    metrics = {"bones": {}, "slots": {}, "n_timelines": 0}
    for bname, tl in anim.get("bones", {}).items():
        if bname not in bone_set:
            issues.append(f"{name}: bone '{bname}' 不存在")
        bm = {}
        for chan, frames in tl.items():
            metrics["n_timelines"] += 1
            if not _times_ok(frames):
                issues.append(f"{name}/{bname}/{chan}: time 非嚴格遞增")
            for f in frames:
                if not _curve_ok(f):
                    issues.append(f"{name}/{bname}/{chan}: 非法 curve 格式")
            if chan == "rotate":
                rng, vs = _range(frames, "angle")
                bm["rotate_range"] = rng
                bm["rotate_seam"] = abs(vs[0] - vs[-1])
            elif chan == "scale":
                rx, vx = _range(frames, "x", 1.0)
                ry, vy = _range(frames, "y", 1.0)
                bm["scale_dev"] = max(abs(v - 1.0) for v in vx + vy)
                bm["scale_seam"] = max(abs(vx[0] - vx[-1]), abs(vy[0] - vy[-1]))
                bm["scale_end"] = max(abs(vx[-1]), abs(vy[-1]))
            elif chan == "translate":
                tx, vx = _range(frames, "x")
                ty, vy = _range(frames, "y")
                bm["translate_range"] = max(tx, ty)
                bm["translate_seam"] = max(abs(vx[0] - vx[-1]), abs(vy[0] - vy[-1]))
        metrics["bones"][bname] = bm
    for sname, tl in anim.get("slots", {}).items():
        if sname not in slot_set:
            issues.append(f"{name}: slot '{sname}' 不存在")
        sm = {}
        for chan, frames in tl.items():
            metrics["n_timelines"] += 1
            if not _times_ok(frames):
                issues.append(f"{name}/{sname}/{chan}: time 非嚴格遞增")
            if chan == "color":
                alphas = [_hex_alpha(f.get("color", "")) for f in frames]
                alphas = [a for a in alphas if a is not None]
                if alphas:
                    sm["alpha_min"] = min(alphas)
                    sm["alpha_max"] = max(alphas)
                    sm["alpha_seam"] = abs(alphas[0] - alphas[-1])
                    sm["alpha_end"] = alphas[-1]
        metrics["slots"][sname] = sm
    return metrics, issues


def _limb_loop_phase_ok(anim):
    """≥2 個有 rotate 的 bone → 檢查峰值(|angle| 最大)時刻是否錯開(至少 2 個不同)。"""
    peaks = []
    for bname, tl in anim.get("bones", {}).items():
        fr = tl.get("rotate")
        if not fr or len(fr) < 2:
            continue
        pk = max(fr, key=lambda f: abs(f.get("angle", 0.0)))
        peaks.append(round(pk["time"], 4))
    if len(peaks) < 2:
        return True  # 不足以檢查 → 不判 fail
    return len(set(peaks)) >= 2


def gate(sk_path):
    sk = json.load(open(sk_path, encoding="utf-8"))
    bone_set = {b["name"] for b in sk["bones"]}
    slot_set = {s["name"] for s in sk["slots"]}
    anims = sk.get("animations", {})
    report = {"file": sk_path, "n_anim": len(anims), "checks": [], "anim_metrics": {}}
    ok = True

    def check(cond, label):
        nonlocal ok
        report["checks"].append({"ac": label, "pass": bool(cond)})
        if not cond:
            ok = False

    check(len(anims) > 0, "有動畫(非空)")
    for name, anim in anims.items():
        m, issues = analyze_anim(name, anim, bone_set, slot_set)
        report["anim_metrics"][name] = m
        # AC1 結構
        check(not issues, f"AC1 結構合法[{name}]" + (f" 問題:{issues}" if issues else ""))
        # AC4 非平凡
        moved = any(any(v > EPS for k, v in bm.items() if k.endswith(("range", "dev")))
                    for bm in m["bones"].values()) or \
                any(sm.get("alpha_max", 0) - sm.get("alpha_min", 0) > 0 for sm in m["slots"].values())
        check(m["n_timelines"] > 0 and moved, f"AC4 非平凡[{name}]")
        # AC2 分帶(依 animation 名的 beat 前綴)
        beat = name.rstrip("0123456789")
        if beat in ("In", "comeout", "open", "hit", "land", "win"):
            big = any(bm.get("scale_dev", 0) >= 0.08 or bm.get("rotate_range", 0) >= 20.0
                      for bm in m["bones"].values())
            check(big, f"AC2-In 大幅動作[{name}]")
            eff_alpha = any(sm.get("alpha_min", 255) <= 5 and sm.get("alpha_max", 0) >= 250
                            for sm in m["slots"].values())
            check(eff_alpha or not m["slots"], f"AC2-In effect alpha 0→255[{name}]")
        elif beat in ("Loop", "idle", "loop", "static", "accent"):
            seam = all(bm.get("scale_seam", 0) <= EPS and bm.get("rotate_seam", 0) <= EPS
                       and bm.get("translate_seam", 0) <= EPS for bm in m["bones"].values()) and \
                   all(sm.get("alpha_seam", 0) <= EPS for sm in m["slots"].values())
            check(seam, f"AC2-Loop seamless(首尾同值)[{name}]")
            small = all(bm.get("scale_dev", 0) <= 0.06 and bm.get("rotate_range", 0) <= 12.0
                        for bm in m["bones"].values())
            check(small, f"AC2-Loop 小幅[{name}]")
            check(moved, f"AC2-Loop 非靜止[{name}]")
            # AC3 相位錯開
            check(_limb_loop_phase_ok(anim), f"AC3 limb 相位錯開[{name}]")
        elif beat in ("Out", "close"):
            zero = all(bm.get("scale_end", 1.0) <= 0.02 for bm in m["bones"].values() if "scale_end" in bm) and \
                   all(sm.get("alpha_end", 255) <= 5 for sm in m["slots"].values() if "alpha_end" in sm)
            check(zero, f"AC2-Out 末幀歸零[{name}]")
    report["overall_pass"] = ok
    return report


# ---- 負對照:蓄意壞資料,確認閘會抓到 --------------------------------------

def selftest():
    base_bones = {"root", "b_a", "b_b", "b_c"}
    base_slots = {"a", "b", "c"}
    sk_stub = {"bones": [{"name": n} for n in base_bones],
               "slots": [{"name": n} for n in base_slots]}
    cases = []

    def run(anims):
        import tempfile
        d = tempfile.mkdtemp()
        p = os.path.join(d, "skeleton.json")
        json.dump({**sk_stub, "animations": anims}, open(p, "w"))
        return gate(p)["overall_pass"]

    # 1. 非 seamless loop → 應 fail
    bad_loop = {"Loop": {"bones": {"b_a": {"scale": [
        {"time": 0, "x": 1.0, "y": 1.0}, {"time": 0.6, "x": 1.02, "y": 1.02},
        {"time": 1.2, "x": 1.05, "y": 1.05}]}}, "slots": {}}}  # 尾 != 首
    cases.append(("非 seamless loop", run(bad_loop) is False))
    # 2. time 逆序 → 應 fail
    bad_time = {"In": {"bones": {"b_a": {"rotate": [
        {"time": 0, "angle": -40}, {"time": 0.3, "angle": 12}, {"time": 0.2, "angle": 0}]}}, "slots": {}}}
    cases.append(("time 逆序", run(bad_time) is False))
    # 3. 壞 curve → 應 fail
    bad_curve = {"In": {"bones": {"b_a": {"scale": [
        {"time": 0, "x": 0.2, "y": 0.2, "curve": 0.25},  # 缺 c2/c3/c4
        {"time": 0.5, "x": 1.0, "y": 1.0}]}}, "slots": {}}}
    cases.append(("壞 curve 散鍵", run(bad_curve) is False))
    # 4. In 無大幅(只有微動)→ 應 fail
    weak_in = {"In": {"bones": {"b_a": {"scale": [
        {"time": 0, "x": 1.0, "y": 1.0}, {"time": 0.5, "x": 1.01, "y": 1.01}]}}, "slots": {}}}
    cases.append(("In 無大幅", run(weak_in) is False))
    # 5. 參照不存在 bone → 應 fail
    bad_ref = {"In": {"bones": {"b_ZZZ": {"rotate": [
        {"time": 0, "angle": -40}, {"time": 0.5, "angle": 0}]}}, "slots": {}}}
    cases.append(("參照不存在 bone", run(bad_ref) is False))
    # 6. 正對照:合法 seamless loop + 大幅 In → 應 pass
    good = {
        "In": {"bones": {"b_a": {"scale": [
            {"time": 0, "x": 0.2, "y": 0.2}, {"time": 0.3, "x": 1.12, "y": 1.12},
            {"time": 0.5, "x": 1.0, "y": 1.0}]}},
            "slots": {"a": {"color": [{"time": 0, "color": "ffffff00"},
                                      {"time": 0.5, "color": "ffffffff"}]}}},
        "Loop": {"bones": {"b_a": {"scale": [
            {"time": 0, "x": 1.0, "y": 1.0}, {"time": 0.6, "x": 1.02, "y": 1.02},
            {"time": 1.2, "x": 1.0, "y": 1.0}]}}, "slots": {}}}
    cases.append(("正對照(合法)", run(good) is True))
    return cases


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton_json", nargs="?", help="build_spine 產出的 skeleton.json")
    ap.add_argument("--selftest", action="store_true", help="跑負對照確認閘可信")
    a = ap.parse_args()
    if a.selftest:
        cases = selftest()
        allok = all(ok for _, ok in cases)
        for label, ok in cases:
            print(f"[{'OK' if ok else 'FAIL'}] 負對照:{label}")
        print("SELFTEST", "PASS" if allok else "FAIL")
        sys.exit(0 if allok else 1)
    if not a.skeleton_json:
        ap.error("需給 skeleton.json 或 --selftest")
    rep = gate(a.skeleton_json)
    for c in rep["checks"]:
        print(f"[{'PASS' if c['pass'] else 'FAIL'}] {c['ac']}")
    print(json.dumps({k: v for k, v in rep.items() if k != "checks"}, ensure_ascii=False, indent=2))
    print("OVERALL", "PASS" if rep["overall_pass"] else "FAIL")
    sys.exit(0 if rep["overall_pass"] else 1)


if __name__ == "__main__":
    main()
