#!/usr/bin/env python3
"""動畫 keyframe 自我品質閘(evaluator gate for storyboard→animation)。

驗收 build_animation.py 產出的 `animations`,純幾何量化(不需 Spine runtime;CDN 被政策擋)。
真相來源有二:
  (1) 校準真值:真實 slot loop `main_draw_loop`(身體呼吸幅度、末梢擺盪角度、循環時長)
      → 定義「合理待機」的量化帶。
  (2) 負對照(--selftest):對生成動畫刻意注入 4 種壞況(零運動/斷 loop 縫/scale=0 塌陷/缺件),
      斷言閘各自抓到 → 證明閘有鑑別力(非恆 PASS)。

檢查項:
  C1 完整性     每個 movable part 的 bone 在 In/Loop/Out 皆有 timeline。
  C2 Loop 無縫   Loop 每條 channel 首尾值相等(可循環)。
  C3 角色幅度    Loop 幅度落在校準帶(body 呼吸 1~10%、limb 擺盪 2~20°、head 微動);且非零(真的會動)。
  C4 相位錯開    兩肢 limb 在 t=0 rotate 反號(避免紙板同步)。
  C5 In 收斂     In 為大動作(某件 scale≤0.5 起 或 |rot|≥20° 或 scale≥1.05 overshoot)且末幀回 neutral。
  C6 Out 塌陷    Out 末幀 scale≈0 或 slot alpha≈0。
  C7 非退化      全部 keyframe scale>0(不塌陷/翻面)、無 NaN、值域合理(|rot|≤180、scale≤5)。
  C8 世界位移    FK 量化:Loop 位移細微、In 位移顯著(以件半徑折算 px),證幾何量化非空談。
"""
import argparse, json, math, os, sys, copy

CAL = {  # 校準自 main_draw_loop:身體 scale 變化 ~6%、hand rotate ~10°、循環 ~0.67s
    "loop_body_scale_var": (0.005, 0.12),   # 呼吸的 scale peak-to-peak
    "loop_limb_rot_pp": (2.0, 25.0),         # 末梢擺盪 peak-to-peak(°)
    "loop_head_max": 8.0,                    # 頭微動上限(°)
    "loop_dur": (0.3, 2.0),
}
EPS = 1e-6


def load(spine_dir):
    d = json.load(open(os.path.join(spine_dir, "skeleton.json"), encoding="utf-8"))
    return d


def ch_range(keys, field, default):
    vs = [k.get(field, default) for k in keys]
    return (min(vs), max(vs)) if vs else (default, default)


def anim_dur(anim):
    mt = 0.0
    for tl in anim.get("bones", {}).values():
        for keys in tl.values():
            for k in keys:
                mt = max(mt, k.get("time", 0.0))
    for tl in anim.get("slots", {}).values():
        for keys in tl.values():
            for k in keys:
                mt = max(mt, k.get("time", 0.0))
    return mt


def first_last_equal(keys, fields):
    if len(keys) < 2:
        return True
    a, b = keys[0], keys[-1]
    for f, dv in fields.items():
        if abs(a.get(f, dv) - b.get(f, dv)) > 1e-4:
            return False
    return True


def bone_role_map(spec):
    m = {}
    for beat in spec["3_motion_storyboard"]["beats"]:
        for p in beat["parts"]:
            r = p.get("role", "")
            m["b_" + p["part"].replace("/", "_").replace(" ", "_")] = (
                r if r in ("body", "head", "limb") else "fx")
    return m


def evaluate(skeleton, spec):
    anims = skeleton.get("animations", {})
    roles = bone_role_map(spec)
    part_bones = set(roles.keys())
    R = {"checks": [], "pass": True}

    def chk(name, ok, detail=""):
        R["checks"].append({"check": name, "pass": bool(ok), "detail": detail})
        if not ok:
            R["pass"] = False

    # C1 完整性
    for beat in ("In", "Loop", "Out"):
        a = anims.get(beat, {})
        have = set(a.get("bones", {}).keys())
        missing = part_bones - have
        chk(f"C1_complete_{beat}", not missing,
            f"missing bones: {sorted(missing)}" if missing else f"{len(have)} bone timelines")

    loop = anims.get("Loop", {})
    # C2 Loop 無縫
    seam_ok, seam_bad = True, []
    for bn, tl in loop.get("bones", {}).items():
        if "rotate" in tl and not first_last_equal(tl["rotate"], {"angle": 0}):
            seam_ok = False; seam_bad.append(f"{bn}.rotate")
        if "translate" in tl and not first_last_equal(tl["translate"], {"x": 0, "y": 0}):
            seam_ok = False; seam_bad.append(f"{bn}.translate")
        if "scale" in tl and not first_last_equal(tl["scale"], {"x": 1, "y": 1}):
            seam_ok = False; seam_bad.append(f"{bn}.scale")
    for sn, tl in loop.get("slots", {}).items():
        if "color" in tl and tl["color"][0].get("color") != tl["color"][-1].get("color"):
            seam_ok = False; seam_bad.append(f"{sn}.color")
    chk("C2_loop_seamless", seam_ok, "broken: " + ",".join(seam_bad) if seam_bad else "首尾同值")

    # C3 角色幅度(Loop)+ 非零
    lo, hi = CAL["loop_body_scale_var"]
    rlo, rhi = CAL["loop_limb_rot_pp"]
    amp_ok, amp_detail = True, []
    for bn, tl in loop.get("bones", {}).items():
        role = roles.get(bn, "fx")
        if role == "body" and "scale" in tl:
            mn, mx = ch_range(tl["scale"], "x", 1.0)
            var = mx - mn
            good = lo <= var <= hi
            amp_ok &= good; amp_detail.append(f"{bn} body scaleVar={var:.3f}{'' if good else ' OUT'}")
        elif role == "limb" and "rotate" in tl:
            mn, mx = ch_range(tl["rotate"], "angle", 0.0)
            pp = mx - mn
            good = rlo <= pp <= rhi
            amp_ok &= good; amp_detail.append(f"{bn} limb rotPP={pp:.1f}{'' if good else ' OUT'}")
        elif role == "head":
            mx = 0.0
            if "rotate" in tl:
                a, b = ch_range(tl["rotate"], "angle", 0.0); mx = max(abs(a), abs(b))
            good = 0 < mx <= CAL["loop_head_max"] or ("translate" in tl)
            amp_ok &= good; amp_detail.append(f"{bn} head rotMax={mx:.1f}")
    chk("C3_loop_amplitude", amp_ok, "; ".join(amp_detail))

    # C4 相位錯開(兩肢 t=0 rotate 反號)
    limb_t0 = []
    for bn, tl in loop.get("bones", {}).items():
        if roles.get(bn) == "limb" and "rotate" in tl:
            limb_t0.append(tl["rotate"][0].get("angle", 0.0))
    phase_ok = (len(limb_t0) < 2) or (min(limb_t0) < 0 < max(limb_t0))
    chk("C4_limb_phase_offset", phase_ok, f"limb t0 angles={limb_t0}")

    # C5 In 收斂
    a_in = anims.get("In", {})
    dramatic, neutral_ok, ndet = False, True, []
    for bn, tl in a_in.get("bones", {}).items():
        if "scale" in tl:
            mn, mx = ch_range(tl["scale"], "x", 1.0)
            if mn <= 0.5 or mx >= 1.05:
                dramatic = True
            last = tl["scale"][-1]
            if abs(last.get("x", 1) - 1) > 0.06 or abs(last.get("y", 1) - 1) > 0.06:
                neutral_ok = False; ndet.append(f"{bn}.scale end≠1")
        if "rotate" in tl:
            mn, mx = ch_range(tl["rotate"], "angle", 0.0)
            if max(abs(mn), abs(mx)) >= 20:
                dramatic = True
            if abs(tl["rotate"][-1].get("angle", 0)) > 2:
                neutral_ok = False; ndet.append(f"{bn}.rotate end≠0")
    chk("C5_in_dramatic_and_settle", dramatic and neutral_ok,
        f"dramatic={dramatic} neutral={neutral_ok} " + ";".join(ndet))

    # C6 Out 塌陷
    a_out = anims.get("Out", {})
    collapse = False
    for bn, tl in a_out.get("bones", {}).items():
        if "scale" in tl and tl["scale"][-1].get("x", 1) <= 0.15:
            collapse = True
    for sn, tl in a_out.get("slots", {}).items():
        if "color" in tl and tl["color"][-1].get("color", "ffffffff")[6:] in ("00", "01", "02"):
            collapse = True
    chk("C6_out_collapse", collapse, "末幀 scale≈0 或 alpha≈0" if collapse else "未塌陷")

    # C7 非退化(全 anim)。注意:scale==0 在首/末 keyframe 是合法「不可見」邊界
    # (入場由 0 炸開、退場塌到 0);只把「中段塌陷 scale≤0」與「負 scale 翻面」判為退化。
    degen = []
    for an, a in anims.items():
        for bn, tl in a.get("bones", {}).items():
            for ch, keys in tl.items():
                n = len(keys)
                for i, k in enumerate(keys):
                    for f, v in k.items():
                        if isinstance(v, float) and math.isnan(v):
                            degen.append(f"{an}/{bn}/{ch} NaN")
                    if ch == "scale":
                        sx, sy = k.get("x", 1), k.get("y", 1)
                        if sx < 0 or sy < 0:
                            degen.append(f"{an}/{bn} scale<0(翻面)")
                        elif (sx <= 0 or sy <= 0) and 0 < i < n - 1:
                            degen.append(f"{an}/{bn} 中段 scale≤0(塌陷)")
                        if sx > 5 or sy > 5:
                            degen.append(f"{an}/{bn} scale>5")
                    if ch == "rotate" and abs(k.get("angle", 0)) > 180:
                        degen.append(f"{an}/{bn} |rot|>180")
    chk("C7_non_degenerate", not degen, "; ".join(degen[:6]) if degen else "無退化")

    # C8 世界位移(FK:件半徑折算 px)
    half = {}
    skin = skeleton["skins"]["default"]
    for sl in skeleton["slots"]:
        att = list(skin.get(sl["name"], {}).values())
        if att:
            a0 = att[0]
            half[sl["name"]] = (a0.get("width", 0) / 2.0, a0.get("height", 0) / 2.0)
    bone2slot = {}
    for sl in skeleton["slots"]:
        bone2slot[sl["bone"]] = sl["name"]

    def excursion(anim):
        """各 bone 在 anim keyframe 時間點,件角落相對 setup 的最大位移(px)。"""
        mx = 0.0
        for bn, tl in anim.get("bones", {}).items():
            hw, hh = half.get(bone2slot.get(bn, ""), (10, 10))
            corners = [(hw, hh), (-hw, hh), (hw, -hh), (-hw, -hh)]
            # 收集所有 keyframe 時間
            times = sorted({k.get("time", 0.0) for keys in tl.values() for k in keys})
            for t in times:
                ang = val_at(tl.get("rotate", []), t, "angle", 0.0)
                sx = val_at(tl.get("scale", []), t, "x", 1.0)
                sy = val_at(tl.get("scale", []), t, "y", 1.0)
                tx = val_at(tl.get("translate", []), t, "x", 0.0)
                ty = val_at(tl.get("translate", []), t, "y", 0.0)
                ca, sa = math.cos(math.radians(ang)), math.sin(math.radians(ang))
                for (px, py) in corners:
                    X = sx * px; Y = sy * py
                    wx = ca * X - sa * Y + tx
                    wy = sa * X + ca * Y + ty
                    d = math.hypot(wx - px, wy - py)
                    mx = max(mx, d)
        return mx

    loop_exc = excursion(loop)
    in_exc = excursion(a_in)
    move_ok = (0.5 < loop_exc < 60) and (in_exc > 30) and (in_exc > loop_exc)
    chk("C8_world_excursion", move_ok, f"loop={loop_exc:.1f}px in={in_exc:.1f}px")

    # duration sanity
    dl, dh = CAL["loop_dur"]
    ld = anim_dur(loop)
    chk("C9_loop_duration", dl <= ld <= dh, f"loop_dur={ld}s")

    return R


def val_at(keys, t, field, default):
    """在 keyframe 時間點取值(t 落在某 keyframe 上;非線內插,足夠量化極值)。"""
    if not keys:
        return default
    best = keys[0].get(field, default)
    for k in keys:
        if abs(k.get("time", 0.0) - t) < 1e-6:
            return k.get(field, default)
    # 落在區間:取最近較早
    prev = keys[0]
    for k in keys:
        if k.get("time", 0.0) <= t:
            prev = k
    return prev.get(field, default)


# ---------- 負對照:證明閘有鑑別力 ----------
def selftest(skeleton, spec):
    base = evaluate(skeleton, spec)
    assert base["pass"], "生成的動畫應先 PASS,實測 FAIL:" + json.dumps(
        [c for c in base["checks"] if not c["pass"]], ensure_ascii=False)
    results = [("baseline_generated", True, base["pass"])]

    def failed_checks(sk):
        r = evaluate(sk, spec)
        return not r["pass"], {c["check"] for c in r["checks"] if not c["pass"]}

    # (a) 零運動:Loop 所有值壓成 neutral
    sk = copy.deepcopy(skeleton)
    for bn, tl in sk["animations"]["Loop"]["bones"].items():
        for ch, keys in tl.items():
            for k in keys:
                if ch == "scale": k["x"] = k["y"] = 1.0
                if ch == "rotate": k["angle"] = 0.0
                if ch == "translate": k["x"] = k["y"] = 0.0
    caught, cks = failed_checks(sk)
    results.append(("zero_motion", caught, cks))

    # (b) 斷 loop 縫:改 Loop 某 bone 末幀
    sk = copy.deepcopy(skeleton)
    b = next(iter(sk["animations"]["Loop"]["bones"].values()))
    ch = "rotate" if "rotate" in b else "scale"
    if ch == "rotate": b["rotate"][-1]["angle"] = b["rotate"][0].get("angle", 0) + 30
    else: b["scale"][-1]["x"] = b["scale"][0].get("x", 1) + 0.3
    caught, cks = failed_checks(sk)
    results.append(("broken_loop_seam", caught, cks))

    # (c) scale=0 塌陷:In 某 bone 中間幀 scale=0
    sk = copy.deepcopy(skeleton)
    for bn, tl in sk["animations"]["In"]["bones"].items():
        if "scale" in tl:
            tl["scale"][1]["x"] = 0.0; break
    caught, cks = failed_checks(sk)
    results.append(("scale_zero_collapse", caught, cks))

    # (d) 缺件:移掉 Loop 一個 bone timeline
    sk = copy.deepcopy(skeleton)
    k0 = next(iter(sk["animations"]["Loop"]["bones"]))
    del sk["animations"]["Loop"]["bones"][k0]
    caught, cks = failed_checks(sk)
    results.append(("missing_bone", caught, cks))

    all_ok = all(r[1] for r in results)
    return all_ok, results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spine_dir")
    ap.add_argument("--psd", default="assets/robot_parts.psd")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--selftest", action="store_true", help="跑負對照(證明閘有鑑別力)")
    a = ap.parse_args()
    sys.path.insert(0, os.path.dirname(__file__))
    from analyze_target import analyze
    spec = analyze(a.psd, a.genre)
    skeleton = load(a.spine_dir)

    R = evaluate(skeleton, spec)
    for c in R["checks"]:
        print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['check']}: {c['detail']}")
    print(f"OVERALL: {'PASS' if R['pass'] else 'FAIL'}")

    if a.selftest:
        print("\n--- 負對照(selftest)---")
        ok, results = selftest(skeleton, spec)
        for name, caught, info in results:
            tag = "OK" if caught else "MISS"
            if name == "baseline_generated":
                print(f"  [{tag}] {name}: PASS={info}")
            else:
                print(f"  [{tag}] {name}: caught={caught} by {sorted(info)}")
        print(f"SELFTEST: {'PASS(閘有鑑別力)' if ok else 'FAIL(閘漏抓)'}")
        if not ok:
            sys.exit(2)

    sys.exit(0 if R["pass"] else 1)


if __name__ == "__main__":
    main()
