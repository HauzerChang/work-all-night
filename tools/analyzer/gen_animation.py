#!/usr/bin/env python3
"""S1 續:分鏡 (#3 storyboard) → Spine 3.8 `animations` timeline。

輸入:build_spine 產出的 skeleton(bones/slots/skin,animations 為空)+ analyze_target 的
#3 分鏡規格(beats: In/Loop/Out,每件 role: 特效/body/head/limb + action 文字)。
輸出:填好 `animations` 的 skeleton(可回寫 skeleton.json),讓素材「會動」。

設計原則(純 CPU、確定性,不學美術決定;幅度校準自真實 Award 生產檔):
  - **角色決定運動**(反推框架):body 呼吸縮放、head 微點頭、limb 末梢擺盪(相位錯開)、
    特效 脈動+alpha。與 CLAUDE.md「運動決定一切」一致。
  - **Loop 無縫**:每條 timeline 首尾同值(t=0 == t=LOOP_DUR),In 收斂到 setup(== Loop 起點)
    → In→Loop 連續;Out 收斂到 scale≈0 / alpha≈0。
  - **幅度校準**(見 log 2026-08-19):Award *_Loop 實測 scale ppk 最小 0.05、rotate ppk 最小 0.44°、
    中位 6.3°。故 body 呼吸 scale amp=0.05(== 大標)、limb rotate amp≈3°、head≈2°,皆落在真實區間。
  - **相位錯開**:limb 之間用 sin(2πt) / sin(2πt+π) 交錯取樣(避免全身同步的紙板感)。

Spine 3.8 格式雷點(見 CLAUDE.md #7):
  timeline frame 省略 time == time 0;scale 缺省 (1,1)、rotate 缺省 0、translate 缺省 (0,0)。
  curve:省略=linear、"stepped"、或緊湊 bezier {curve:cx1,c2:cy1,c3:cx2,c4:cy2}。
  slot color 為 "rrggbbaa" hex;此處只調 alpha(白色乘算)。

此模組同時導出 sample_bone / sample_slot_alpha 供 validate_animation.py 量化自驗(單一真相)。
"""
import argparse, json, math, os

LOOP_DUR = 1.0
IN_DUR = 0.5
OUT_DUR = 0.4

# 幅度參數(校準自真實 Award *_Loop)
BREATH_SCALE = 0.05     # body 呼吸縮放 amp(peak 1.05,ppk 0.05 == 大標)
LIMB_SWING = 3.0        # limb 末梢擺盪 amp(deg;ppk 6 ≈ Loop rotate 中位)
HEAD_NOD = 2.0          # head 微點頭 amp(deg)
GLOW_PULSE = 0.04       # 特效脈動縮放 amp
GLOW_ALPHA_LO = 0xB0    # 特效 alpha 脈動下限(白 200/255 ≈ 0.78)


def _sine_frames(amp, phase, dur, keyfn, n=4):
    """在 [0,dur] 均勻取 n+1 點造 amp*sin(2πt/dur + phase);首尾同值(無縫)。
    keyfn(value)->dict 生成 frame 的值鍵。回傳 frames list(含 time)。"""
    frames = []
    for i in range(n + 1):
        t = dur * i / n
        v = amp * math.sin(2 * math.pi * (i / n) + phase)
        f = keyfn(round(v, 4))
        if i > 0:
            f = {"time": round(t, 4), **f}
        frames.append(f)
    return frames


def _rot(a):
    return {"angle": a}


def _scale(s):
    return {"x": round(1 + s, 4), "y": round(1 + s, 4)}


def _breath_frames(amp, dur):
    """上行呼吸(只放大再回位,不縮小):setup(1.0) → 1+amp(mid) → setup。
    與 Award 大標 Loop 實測形狀一致(`[{}, {t:.5, 1.05}, {t:1}]`),首尾=setup 保證無縫且接 In。"""
    return [{"x": 1.0, "y": 1.0},
            {"time": round(dur / 2, 4), "x": round(1 + amp, 4), "y": round(1 + amp, 4)},
            {"time": round(dur, 4), "x": 1.0, "y": 1.0}]


def alpha_hex(a01):
    v = max(0, min(255, int(round(a01 * 255))))
    return "ffffff%02x" % v


# ---------- 產生 animations ----------
def build_animations(skeleton, spec):
    """回傳 {In,Loop,Out} animations dict。件→bone 映射沿用 build_spine:bone=b_<slot>,slot=<safe name>。"""
    # 由 #4 slicing_strategy 拿 slot_name / part→slot;由 #2 effects 拿 is_effect;role 從 storyboard。
    parts = spec["1_movable_parts"]
    effect_map = {e["name"]: e["is_effect"] for e in spec["2_effects"]}
    role_map = {}
    for beat in spec["3_motion_storyboard"]["beats"]:
        for p in beat["parts"]:
            role_map[p["part"]] = p["role"]
    # slot 名沿用 build_spine safe()(只換 / \ 空白);bone = "b_"+slot
    def safe(n):
        return n.replace("/", "_").replace("\\", "_").replace(" ", "_")
    entries = []
    limb_idx = 0
    for p in parts:
        name = p["name"]
        slot = safe(name)
        bone = "b_" + slot
        is_fx = effect_map.get(name, False)
        role = role_map.get(name, "body")
        phase = 0.0
        if role == "limb":
            phase = math.pi * (limb_idx % 2)   # limb 交錯相位(0, π, 0, π…)
            limb_idx += 1
        entries.append(dict(name=name, slot=slot, bone=bone, is_fx=is_fx, role=role, phase=phase))

    anim_in = {"bones": {}, "slots": {}}
    anim_loop = {"bones": {}, "slots": {}}
    anim_out = {"bones": {}, "slots": {}}

    for e in entries:
        bone, slot, role, is_fx, phase = e["bone"], e["slot"], e["role"], e["is_fx"], e["phase"]

        # ---- Loop(待機微呼吸,無縫)----
        lb = {}
        if is_fx:
            lb["scale"] = _breath_frames(GLOW_PULSE, LOOP_DUR)   # 上行脈動,首尾=setup
            # alpha 脈動:1.0 -> lo -> 1.0(無縫)
            lo = GLOW_ALPHA_LO / 255.0
            mid = (1.0 + lo) / 2
            amp = (1.0 - lo) / 2
            frames = []
            for i in range(5):
                t = LOOP_DUR * i / 4
                a = mid + amp * math.cos(2 * math.pi * (i / 4))
                f = {"color": alpha_hex(round(a, 4))}
                if i > 0:
                    f = {"time": round(t, 4), **f}
                frames.append(f)
            anim_loop["slots"][slot] = {"color": frames}
        elif role == "body":
            lb["scale"] = _breath_frames(BREATH_SCALE, LOOP_DUR)   # 上行呼吸,首尾=setup
        elif role == "head":
            lb["rotate"] = _sine_frames(HEAD_NOD, 0.0, LOOP_DUR, _rot)
        elif role == "limb":
            lb["rotate"] = _sine_frames(LIMB_SWING, phase, LOOP_DUR, _rot)
        if lb:
            anim_loop["bones"][bone] = lb

        # ---- In(入場,收斂到 setup == Loop 起點)----
        ib = {}
        if is_fx:
            # 炸開:scale 0.5->1.15->1.0,alpha 0->255
            ib["scale"] = [{"x": 0.5, "y": 0.5},
                           {"time": round(IN_DUR * 0.6, 4), "x": 1.15, "y": 1.15},
                           {"time": IN_DUR, "x": 1.0, "y": 1.0}]
            ib["rotate"] = [{"angle": -30.0}, {"time": IN_DUR, "angle": 0.0}]
            anim_in["slots"][slot] = {"color": [{"color": alpha_hex(0.0)},
                                                {"time": round(IN_DUR * 0.5, 4), "color": alpha_hex(1.0)}]}
        elif role == "body":
            # 彈入 + overshoot:0.2 -> 1.08 -> 1.0
            ib["scale"] = [{"x": 0.2, "y": 0.2},
                           {"time": round(IN_DUR * 0.6, 4), "x": 1.08, "y": 1.08},
                           {"time": IN_DUR, "x": 1.0, "y": 1.0}]
            ib["translate"] = [{"x": 0.0, "y": -40.0}, {"time": IN_DUR, "x": 0.0, "y": 0.0}]
        elif role == "head":
            ib["rotate"] = [{"angle": -15.0}, {"time": IN_DUR, "angle": 0.0}]
        elif role == "limb":
            swing = -40.0 if phase == 0.0 else 40.0   # 左右手甩入方向相反
            ib["rotate"] = [{"angle": swing}, {"time": IN_DUR, "angle": 0.0}]
            ib["translate"] = [{"x": -swing * 0.6, "y": 0.0}, {"time": IN_DUR, "x": 0.0, "y": 0.0}]
        if ib:
            anim_in["bones"][bone] = ib

        # ---- Out(退場,收斂到 scale≈0 / alpha≈0)----
        ob = {"scale": [{"x": 1.0, "y": 1.0}, {"time": OUT_DUR, "x": 0.01, "y": 0.01}]}
        anim_out["bones"][bone] = ob
        if is_fx:
            anim_out["slots"][slot] = {"color": [{"color": alpha_hex(1.0)},
                                                 {"time": OUT_DUR, "color": alpha_hex(0.0)}]}

    return {"In": anim_in, "Loop": anim_loop, "Out": anim_out}


def add_animations(skeleton, spec, prefix=""):
    anims = build_animations(skeleton, spec)
    out = {}
    for k, v in anims.items():
        out[(prefix + k) if prefix else k] = v
    skeleton["animations"] = out
    return skeleton


# ---------- 取樣器(供 validator 量化;單一真相)----------
def _bezier_ease(cx1, cy1, cx2, cy2, x, iters=8):
    """Spine 緊湊 bezier:P0=(0,0),P3=(1,1),控制點 (cx1,cy1),(cx2,cy2)。給 x 求 y。"""
    t = x
    for _ in range(iters):
        mt = 1 - t
        bx = 3 * mt * mt * t * cx1 + 3 * mt * t * t * cx2 + t ** 3
        dbx = 3 * mt * mt * cx1 + 6 * mt * t * (cx2 - cx1) + 3 * t * t * (1 - cx2)
        if abs(dbx) < 1e-9:
            break
        t -= (bx - x) / dbx
        t = max(0.0, min(1.0, t))
    mt = 1 - t
    return 3 * mt * mt * t * cy1 + 3 * mt * t * t * cy2 + t ** 3


def _interp(f0, f1, key, default, time):
    v0 = f0.get(key, default)
    v1 = f1.get(key, default)
    t0 = f0.get("time", 0.0)
    t1 = f1.get("time", 0.0)
    if t1 <= t0:
        return v1
    a = (time - t0) / (t1 - t0)
    curve = f0.get("curve", None)
    if curve == "stepped":
        return v0
    if isinstance(curve, (int, float)):   # 緊湊 bezier
        a = _bezier_ease(curve, f0.get("c2", 0.0), f0.get("c3", 1.0), f0.get("c4", 1.0), a)
    # linear(省略)= a 不變
    return v0 + (v1 - v0) * a


def _sample_timeline(frames, keys, defaults, time):
    if not frames:
        return {k: defaults[k] for k in keys}
    if time <= frames[0].get("time", 0.0):
        return {k: frames[0].get(k, defaults[k]) for k in keys}
    if time >= frames[-1].get("time", 0.0):
        return {k: frames[-1].get(k, defaults[k]) for k in keys}
    for i in range(len(frames) - 1):
        t0 = frames[i].get("time", 0.0)
        t1 = frames[i + 1].get("time", 0.0)
        if t0 <= time <= t1:
            return {k: _interp(frames[i], frames[i + 1], k, defaults[k], time) for k in keys}
    return {k: frames[-1].get(k, defaults[k]) for k in keys}


def sample_bone(anim, bone, time):
    """回傳 (tx, ty, rot_deg, sx, sy)(相對該 bone setup;缺省 identity)。"""
    bt = anim.get("bones", {}).get(bone, {})
    tr = _sample_timeline(bt.get("translate", []), ("x", "y"), {"x": 0.0, "y": 0.0}, time)
    ro = _sample_timeline(bt.get("rotate", []), ("angle",), {"angle": 0.0}, time)
    sc = _sample_timeline(bt.get("scale", []), ("x", "y"), {"x": 1.0, "y": 1.0}, time)
    return (tr["x"], tr["y"], ro["angle"], sc["x"], sc["y"])


def sample_slot_alpha(anim, slot, time):
    """回傳 slot 白色乘算 alpha(0..1);無 color timeline → 1.0。"""
    st = anim.get("slots", {}).get(slot, {})
    frames = st.get("color", [])
    if not frames:
        return 1.0
    # 對 hex alpha 做線性內插(色恆白)
    def a_of(f):
        return int(f["color"][6:8], 16) / 255.0
    if time <= frames[0].get("time", 0.0):
        return a_of(frames[0])
    if time >= frames[-1].get("time", 0.0):
        return a_of(frames[-1])
    for i in range(len(frames) - 1):
        t0 = frames[i].get("time", 0.0)
        t1 = frames[i + 1].get("time", 0.0)
        if t0 <= time <= t1:
            a0, a1 = a_of(frames[i]), a_of(frames[i + 1])
            if t1 <= t0:
                return a1
            r = (time - t0) / (t1 - t0)
            curve = frames[i].get("curve", None)
            if curve == "stepped":
                return a0
            return a0 + (a1 - a0) * r
    return a_of(frames[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("skeleton_json", help="build_spine 產出的 skeleton.json")
    ap.add_argument("spec_json", help="analyze_target 產出的 spec(含 #3 storyboard)")
    ap.add_argument("--prefix", default="")
    ap.add_argument("--out", default=None, help="預設就地覆寫 skeleton_json")
    a = ap.parse_args()
    skel = json.load(open(a.skeleton_json, encoding="utf-8"))
    spec = json.load(open(a.spec_json, encoding="utf-8"))
    add_animations(skel, spec, a.prefix)
    out = a.out or a.skeleton_json
    json.dump(skel, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({"out": out, "animations": list(skel["animations"].keys()),
                      "bones_animated": {k: len(v.get("bones", {})) for k, v in skel["animations"].items()},
                      "slots_animated": {k: len(v.get("slots", {})) for k, v in skel["animations"].items()}},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
