#!/usr/bin/env python3
"""S1/S2 — 動畫生成閘:量化驗證 gen_animation 產出的 In/Loop/Out 是否「會動且動得對」。

不靠肉眼、不需瀏覽器(CDN 被政策擋)。用 gen_animation 的取樣器(單一真相)在時間軸上
取樣每根 bone 的變換 / 每個 slot 的 alpha,計算可機讀指標,逐條 AC 判 PASS/FAIL。

AC(可機讀):
 A1 well-formed   :每支動畫每條 timeline time 嚴格遞增、值有限、curve 格式合法。
 A2 loop-seamless :Loop 每根 bone 於 t=0 與 t=LOOP_DUR 變換一致(無縫)+ slot alpha 首尾一致。
 A3 loop-has-motion:Loop 至少有 bone 的 rotate/scale peak-to-peak 超過門檻(不是靜態)。
 A4 loop-breathing:Loop 幅度落在「微呼吸」真實區間(body scale ppk、limb rotate ppk 校準自 Award)。
 A5 phase-offset  :兩 limb 的 Loop 擺盪反相(取樣序列相關係數 < 0(錯開,避免紙板感)。
 A6 in→loop-cont  :In 結束姿勢 == Loop 起始姿勢(In 收斂到 setup → 接 Loop 連續)。
 A7 in-dramatic   :In 的運動幅度 > Loop(入場比待機大),且 body scale 由小放大(彈入)。
 A8 out-exits     :Out 結束時 body scale≈0 且 特效 slot alpha≈0(退場收斂)。

評估器可信度:附**負對照**(--selfcheck)—— 故意造壞動畫(無縫破壞 / 零運動 / 同相 limb /
In 不收斂),確認對應 AC 由 PASS 翻 FAIL,證明閘有鑑別力。
交叉真值:--award 對 Award *_Loop 實測幅度區間做 sanity。
"""
import argparse, json, math, os, sys, copy
sys.path.insert(0, os.path.dirname(__file__))
from gen_animation import (sample_bone, sample_slot_alpha, build_animations,
                           LOOP_DUR, IN_DUR, OUT_DUR)

EPS = 1e-4
# A4 幅度區間(校準自 Award *_Loop:scale ppk∈[0.05,3.75]、rotate ppk∈[0.44,22.4]°)
BODY_SCALE_PPK = (0.02, 0.30)
LIMB_ROT_PPK = (1.0, 15.0)


def _samples(anim, bone, dur, n=24):
    return [sample_bone(anim, bone, dur * i / n) for i in range(n + 1)]


def _ppk(seq, idx):
    vals = [s[idx] for s in seq]
    return max(vals) - min(vals)


def _bones_in(anim):
    return list(anim.get("bones", {}).keys())


def _roles(spec):
    role = {}
    fx = {e["name"]: e["is_effect"] for e in spec["2_effects"]}
    for beat in spec["3_motion_storyboard"]["beats"]:
        for p in beat["parts"]:
            role[p["part"]] = p["role"]
    def safe(n): return n.replace("/", "_").replace("\\", "_").replace(" ", "_")
    out = []
    for p in spec["1_movable_parts"]:
        nm = p["name"]
        out.append(dict(name=nm, slot=safe(nm), bone="b_" + safe(nm),
                        role=role.get(nm, "body"), is_fx=fx.get(nm, False)))
    return out


# ---------- AC 檢查 ----------
def a1_wellformed(anims):
    errs = []
    for an, ad in anims.items():
        for sect in ("bones", "slots"):
            for owner, tls in ad.get(sect, {}).items():
                for tk, frames in tls.items():
                    last = -1e9
                    for f in frames:
                        t = f.get("time", 0.0)
                        if t < last - 1e-9:
                            errs.append(f"{an}/{owner}/{tk}: time 非遞增 {t}<{last}")
                        last = t
                        for k, v in f.items():
                            if k in ("time", "angle", "x", "y", "c2", "c3", "c4") and not math.isfinite(v):
                                errs.append(f"{an}/{owner}/{tk}: 非有限值 {k}={v}")
                        c = f.get("curve", None)
                        if c is not None and c != "stepped" and c != "linear" and not isinstance(c, (int, float)):
                            errs.append(f"{an}/{owner}/{tk}: 非法 curve {c!r}")
                        if tk == "color" and (len(f.get("color", "")) != 8):
                            errs.append(f"{an}/{owner}/color: 非 8-hex {f.get('color')!r}")
    return len(errs) == 0, errs


def a2_loop_seamless(anims):
    loop = anims["Loop"]
    errs = []
    for bone in _bones_in(loop):
        a = sample_bone(loop, bone, 0.0)
        b = sample_bone(loop, bone, LOOP_DUR)
        for i, nm in enumerate(("tx", "ty", "rot", "sx", "sy")):
            if abs(a[i] - b[i]) > (1e-3 if nm == "rot" else 1e-4):
                errs.append(f"bone {bone} {nm}: {a[i]:.5f} vs {b[i]:.5f}")
    for slot in loop.get("slots", {}):
        a = sample_slot_alpha(loop, slot, 0.0)
        b = sample_slot_alpha(loop, slot, LOOP_DUR)
        if abs(a - b) > 1e-3:
            errs.append(f"slot {slot} alpha: {a:.4f} vs {b:.4f}")
    return len(errs) == 0, errs


def a3_loop_motion(anims):
    loop = anims["Loop"]
    mx = 0.0
    for bone in _bones_in(loop):
        seq = _samples(loop, bone, LOOP_DUR)
        mx = max(mx, _ppk(seq, 2), _ppk(seq, 3) * 100)  # rot(deg) 與 scale(*100→同量綱)
    return mx > 0.5, {"max_motion_metric": round(mx, 3)}


def a4_breathing(anims, roles):
    loop = anims["Loop"]
    info = {}
    ok = True
    for r in roles:
        if r["is_fx"]:
            continue
        seq = _samples(loop, r["bone"], LOOP_DUR)
        if r["role"] == "body":
            ppk = _ppk(seq, 3)
            info[r["name"]] = {"scale_ppk": round(ppk, 4)}
            if not (BODY_SCALE_PPK[0] <= ppk <= BODY_SCALE_PPK[1]):
                ok = False
        elif r["role"] == "limb":
            ppk = _ppk(seq, 2)
            info[r["name"]] = {"rot_ppk_deg": round(ppk, 3)}
            if not (LIMB_ROT_PPK[0] <= ppk <= LIMB_ROT_PPK[1]):
                ok = False
    return ok, info


def _corr(a, b):
    n = len(a)
    ma = sum(a) / n
    mb = sum(b) / n
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    da = math.sqrt(sum((x - ma) ** 2 for x in a))
    db = math.sqrt(sum((y - mb) ** 2 for y in b))
    if da < 1e-9 or db < 1e-9:
        return 0.0
    return num / (da * db)


def a5_phase(anims, roles):
    loop = anims["Loop"]
    limbs = [r for r in roles if r["role"] == "limb"]
    if len(limbs) < 2:
        return True, {"note": "limb<2,跳過"}
    n = 24
    seqs = []
    for r in limbs:
        seqs.append([sample_bone(loop, r["bone"], LOOP_DUR * i / n)[2] for i in range(n + 1)])
    c = _corr(seqs[0], seqs[1])
    return c < 0.0, {"limbs": [limbs[0]["name"], limbs[1]["name"]], "rot_corr": round(c, 3)}


def a6_in_loop_cont(anims):
    inn, loop = anims["In"], anims["Loop"]
    bones = set(_bones_in(inn)) | set(_bones_in(loop))
    errs = []
    for bone in bones:
        a = sample_bone(inn, bone, IN_DUR)
        b = sample_bone(loop, bone, 0.0)
        for i, nm in enumerate(("tx", "ty", "rot", "sx", "sy")):
            if abs(a[i] - b[i]) > (1e-2 if nm in ("tx", "ty") else (1e-2 if nm == "rot" else 1e-3)):
                errs.append(f"bone {bone} {nm}: In端 {a[i]:.4f} vs Loop起 {b[i]:.4f}")
    # slot alpha 亦須連續
    for slot in set(inn.get("slots", {})) | set(loop.get("slots", {})):
        a = sample_slot_alpha(inn, slot, IN_DUR)
        b = sample_slot_alpha(loop, slot, 0.0)
        if abs(a - b) > 1e-2:
            errs.append(f"slot {slot} alpha: In端 {a:.4f} vs Loop起 {b:.4f}")
    return len(errs) == 0, errs


def a7_in_dramatic(anims, roles):
    inn, loop = anims["In"], anims["Loop"]
    info = {}
    ok = True
    body = [r for r in roles if r["role"] == "body"]
    for r in body:
        si = _samples(inn, r["bone"], IN_DUR)
        sl = _samples(loop, r["bone"], LOOP_DUR)
        ppk_in = _ppk(si, 3)
        ppk_loop = _ppk(sl, 3)
        smin = min(s[3] for s in si)
        info[r["name"]] = {"in_scale_ppk": round(ppk_in, 3), "loop_scale_ppk": round(ppk_loop, 3),
                           "in_scale_min": round(smin, 3)}
        if not (ppk_in > ppk_loop and smin < 0.5):   # In 幅度更大 + 由小放大(彈入)
            ok = False
    return ok, info


def a8_out_exits(anims, roles):
    out = anims["Out"]
    info = {}
    ok = True
    for r in roles:
        s = sample_bone(out, r["bone"], OUT_DUR)
        sc = max(s[3], s[4])
        if r["role"] == "body" or True:
            info.setdefault("scale_end", {})[r["name"]] = round(sc, 4)
            if sc > 0.05:
                ok = False
        if r["is_fx"]:
            a = sample_slot_alpha(out, r["slot"], OUT_DUR)
            info["fx_alpha_end"] = round(a, 4)
            if a > 0.05:
                ok = False
    return ok, info


def run(anims, spec):
    roles = _roles(spec)
    results = {}
    results["A1_wellformed"] = a1_wellformed(anims)
    results["A2_loop_seamless"] = a2_loop_seamless(anims)
    results["A3_loop_motion"] = a3_loop_motion(anims)
    results["A4_breathing"] = a4_breathing(anims, roles)
    results["A5_phase_offset"] = a5_phase(anims, roles)
    results["A6_in_loop_cont"] = a6_in_loop_cont(anims)
    results["A7_in_dramatic"] = a7_in_dramatic(anims, roles)
    results["A8_out_exits"] = a8_out_exits(anims, roles)
    overall = all(v[0] for v in results.values())
    return overall, results


def award_amplitude_truth(path="assets/Award.json"):
    d = json.load(open(path, encoding="utf-8"))
    sca, rot = [], []
    for an, ad in d["animations"].items():
        if not an.endswith("_Loop"):
            continue
        for bn, bt in ad.get("bones", {}).items():
            if "scale" in bt and len(bt["scale"]) > 1:
                xs = [f.get("x", 1.0) for f in bt["scale"]]
                sca.append(max(xs) - min(xs))
            if "rotate" in bt and len(bt["rotate"]) > 1:
                a = [f.get("angle", 0.0) for f in bt["rotate"]]
                rot.append(max(a) - min(a))
    return {"scale_ppk_range": [round(min(sca), 3), round(max(sca), 3)],
            "rotate_ppk_range_deg": [round(min(rot), 2), round(max(rot), 2)],
            "our_body_in_range": BODY_SCALE_PPK, "our_limb_in_range": LIMB_ROT_PPK}


# ---------- 負對照 ----------
def selfcheck(spec):
    """故意破壞 → 對應 AC 應翻 FAIL,證明閘有鑑別力。"""
    base = build_animations({}, spec)
    reports = []

    # (1) 破壞無縫:Loop 某 bone 尾值改掉
    b1 = copy.deepcopy(base)
    for bone, bt in b1["Loop"]["bones"].items():
        for tk in bt:
            bt[tk][-1] = {**bt[tk][-1], ("angle" if tk == "rotate" else "x"): 999.0}
            break
        break
    ok, _ = a2_loop_seamless(b1)
    reports.append(("破壞無縫→A2 應FAIL", not ok))

    # (2) 零運動:清空 Loop 所有 bone timeline
    b2 = copy.deepcopy(base)
    b2["Loop"]["bones"] = {}
    ok, _ = a3_loop_motion(b2)
    reports.append(("零運動→A3 應FAIL", not ok))

    # (3) limb 同相:把兩 limb rotate 設成完全相同
    b3 = copy.deepcopy(base)
    roles = _roles(spec)
    limbs = [r for r in roles if r["role"] == "limb"]
    if len(limbs) >= 2 and limbs[0]["bone"] in b3["Loop"]["bones"] and limbs[1]["bone"] in b3["Loop"]["bones"]:
        b3["Loop"]["bones"][limbs[1]["bone"]] = copy.deepcopy(b3["Loop"]["bones"][limbs[0]["bone"]])
        ok, _ = a5_phase(b3, roles)
        reports.append(("limb同相→A5 應FAIL", not ok))

    # (4) In 不收斂:In 尾值不等於 setup
    b4 = copy.deepcopy(base)
    for bone, bt in b4["In"]["bones"].items():
        if "scale" in bt:
            bt["scale"][-1] = {**bt["scale"][-1], "x": 0.5, "y": 0.5}
            break
    ok, _ = a6_in_loop_cont(b4)
    reports.append(("In不收斂→A6 應FAIL", not ok))

    # (5) Out 不退場:Out 尾值維持 scale 1
    b5 = copy.deepcopy(base)
    for bone, bt in b5["Out"]["bones"].items():
        bt["scale"][-1] = {**bt["scale"][-1], "x": 1.0, "y": 1.0}
    ok, _ = a8_out_exits(b5, roles)
    reports.append(("Out不退場→A8 應FAIL", not ok))

    return reports


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skeleton", default=None, help="含 animations 的 skeleton.json;省略則由 spec 現生")
    ap.add_argument("--spec", required=True, help="analyze_target spec json")
    ap.add_argument("--selfcheck", action="store_true", help="跑負對照確認鑑別力")
    ap.add_argument("--award", action="store_true", help="印 Award Loop 幅度真值 sanity")
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    if a.skeleton:
        skel = json.load(open(a.skeleton, encoding="utf-8"))
        anims = skel["animations"]
    else:
        anims = build_animations({}, spec)

    overall, results = run(anims, spec)
    print("=" * 60)
    print("動畫生成閘 —", "OVERALL PASS ✅" if overall else "OVERALL FAIL ❌")
    for k, (ok, detail) in results.items():
        print(f"  [{'PASS' if ok else 'FAIL'}] {k}: {json.dumps(detail, ensure_ascii=False)[:200]}")

    if a.award:
        print("\n-- Award *_Loop 幅度真值 sanity --")
        print(json.dumps(award_amplitude_truth(), ensure_ascii=False, indent=2))

    if a.selfcheck:
        print("\n-- 負對照(鑑別力)--")
        reps = selfcheck(spec)
        allok = all(x[1] for x in reps)
        for msg, ok in reps:
            print(f"  [{'OK' if ok else 'BROKEN-GATE'}] {msg}")
        print("  負對照結論:", "閘有鑑別力 ✅" if allok else "閘失效 ❌")
        overall = overall and allok

    sys.exit(0 if overall else 1)


if __name__ == "__main__":
    main()
