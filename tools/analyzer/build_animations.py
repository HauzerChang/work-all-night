#!/usr/bin/env python3
"""S1 #3 續:分鏡(storyboard)→ Spine 3.8 動畫 keyframe(讓 build_spine 的靜態素材「會動」)。

輸入:build_spine.py 產出的 spine 目錄(skeleton.json,animations 為空)+ 原 PSD + genre。
流程:
  1. 讀 skeleton.json 取 bones/slots;跑 analyze_target 取每件的 struct_role(body/head/limb/effect)。
  2. 依 genre 先驗的 beats(In/Loop/Out 或 static/idle/.../close),為每根件 bone 生成
     translate/scale/rotate timeline;特效件另生 slot color(alpha)timeline。
  3. 寫回 skeleton.json 的 "animations"。

設計原則(對應已知品質雷點):
  - **Loop 嚴格週期**:以正弦取樣(週期 = 動畫長度),t=0 與 t=T 的取樣值相等 → loop 不跳。
  - **有界且非零振幅**:各角色一組幅度上限(呼吸 scale ±0.03、rotate ±3°、translate ±3px)。
  - **相位錯開**:每件依索引給相位 φ_i = i/N,末梢/呼吸的極值時間錯開 → 破「全身同步紙板感」。
  - **平滑緩動**:段間用 Spine 3.8 緊湊 bezier {"curve":0.25,"c3":0.75}(對稱 ease-in-out)。
  - In/Out 為非週期(進退場):刻意 t=0≠t=T;仍套 overshoot/相位錯開。

Spine 3.8 bone timeline 格式(對齊 assets/main_draw.json):
  bones[bone] = {"translate":[{time,x,y,curve,c3}...], "rotate":[{time,angle,...}], "scale":[{time,x,y,...}]}
  keyframe 省略 time=0;translate/rotate 省略值=0;scale 省略值=1。
  緊湊 bezier:curve=cx1、c2=cy1(default 0 省)、c3=cx2、c4=cy2(default 1 省)。
"""
import argparse, json, math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
from analyze_target import analyze
from genre_priors import get as get_prior

# 對稱 ease-in-out 的緊湊 bezier(cx1=0.25, cy1=0, cx2=0.75, cy2=1)
EASE = {"curve": 0.25, "c3": 0.75}

# 各角色的呼吸(Loop)振幅預設
BREATH = {
    "body":   {"scale": 0.03, "ty": 3.0, "rot": 0.0},   # 主體:縮放呼吸 + 微上下
    "head":   {"scale": 0.0,  "ty": 2.0, "rot": 2.5},   # 頭:微點頭(旋轉)+ 微浮
    "limb":   {"scale": 0.0,  "ty": 0.0, "rot": 3.0},   # 末梢:擺盪(旋轉)
    "effect": {"scale": 0.04, "ty": 0.0, "rot": 0.0, "alpha": 0.35},  # 特效:脈動 + alpha
}


def _safe(name):
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


def _role_of(part_row):
    """storyboard 一列 → 標準角色 key。"""
    r = part_row["role"]
    if r == "特效":
        return "effect"
    return r if r in ("body", "head", "limb") else "limb"


def _sine_frames(period, amp, base, phase, n=4, prop_default=None):
    """繞一圈取樣正弦 → 週期 keyframe 值序列(k=0..n,末==首)。回傳 [(time,value)]。"""
    frames = []
    for k in range(n + 1):
        t = round(k * period / n, 4)
        v = base + amp * math.sin(2 * math.pi * (k / n + phase))
        frames.append((t, v))
    return frames


def _emit_bone_timeline(frames, prop, default, eps=1e-3):
    """把 [(time,value)] 轉成 Spine keyframe list;值等於 default 時省略;段間套 EASE。"""
    kfs = []
    for i, (t, v) in enumerate(frames):
        kf = {}
        if t > 0:
            kf["time"] = t
        if abs(v - default) > eps:
            kf[prop] = round(v, 3)
        # 除最後一格外都套緩動(最後一格無出段)
        if i < len(frames) - 1:
            kf.update(EASE)
        kfs.append(kf)
    return kfs


def _emit_xy_timeline(fx, fy, dx, dy, eps=1e-3):
    """translate/scale 這種雙值 timeline:x/y 共用一組 time + 一組 curve。"""
    kfs = []
    n = len(fx)
    for i in range(n):
        t, vx = fx[i]
        _, vy = fy[i]
        kf = {}
        if t > 0:
            kf["time"] = t
        if abs(vx - dx) > eps:
            kf["x"] = round(vx, 3)
        if abs(vy - dy) > eps:
            kf["y"] = round(vy, 3)
        if i < n - 1:
            kf.update(EASE)
        kfs.append(kf)
    return kfs


def _hex_alpha(a):
    v = max(0, min(255, int(round(a * 255))))
    return "ffffff%02x" % v


def build_loop(bone_roles, period=2.0):
    """呼吸循環:每件依角色 + 相位錯開產生週期 timeline。回傳 (bones_dict, slots_dict)。"""
    bones, slots = {}, {}
    N = max(1, len(bone_roles))
    for i, (bone, slot, role) in enumerate(bone_roles):
        phase = i / N                      # 相位錯開:各件極值時間不同
        b = BREATH[role]
        tl = {}
        # scale 呼吸(body/effect):x 反相 y → 微 squash/stretch,面積近守恆
        if b["scale"] > 0:
            fx = _sine_frames(period, -b["scale"], 1.0, phase)
            fy = _sine_frames(period, +b["scale"], 1.0, phase)
            tl["scale"] = _emit_xy_timeline(fx, fy, 1.0, 1.0)
        # translate y 微浮
        if b["ty"] > 0:
            fx = [(t, 0.0) for (t, _) in _sine_frames(period, 0, 0, phase)]
            fy = _sine_frames(period, b["ty"], 0.0, phase)
            tl["translate"] = _emit_xy_timeline(fx, fy, 0.0, 0.0)
        # rotate(head/limb)
        if b["rot"] > 0:
            fr = _sine_frames(period, b["rot"], 0.0, phase)
            tl["rotate"] = _emit_bone_timeline(fr, "angle", 0.0)
        if tl:
            bones[bone] = tl
        # 特效 alpha 脈動(slot color)
        if role == "effect" and b.get("alpha", 0) > 0:
            fa = _sine_frames(period, -b["alpha"], 1.0, phase)   # 由亮往暗脈動
            col = []
            for j, (t, a) in enumerate(fa):
                kf = {"color": _hex_alpha(a)}
                if t > 0:
                    kf["time"] = t
                if j < len(fa) - 1:
                    kf.update(EASE)
                col.append(kf)
            slots[slot] = {"color": col}
    return bones, slots


def build_in(bone_roles, dur=0.5):
    """入場:縮放彈入 + overshoot;末梢從偏角甩入;特效由 0 alpha 亮起。非週期。"""
    bones, slots = {}, {}
    N = max(1, len(bone_roles))
    for i, (bone, slot, role) in enumerate(bone_roles):
        ph = i / N
        t_mid = round(dur * (0.55 + 0.15 * ph), 4)   # overshoot 時間相位錯開
        tl = {}
        # scale 0.2 → 1.12(overshoot)→ 1.0
        tl["scale"] = [
            {"x": 0.2, "y": 0.2, **EASE},
            {"time": t_mid, "x": 1.12, "y": 1.12, **EASE},
            {"time": dur, "x": 1.0, "y": 1.0},
        ]
        if role == "limb":
            ang0 = -30 if i % 2 == 0 else 30
            tl["rotate"] = [
                {"angle": ang0, **EASE},
                {"time": t_mid, "angle": 4 if ang0 < 0 else -4, **EASE},
                {"time": dur, "angle": 0},
            ]
        bones[bone] = tl
        if role == "effect":
            slots[slot] = {"color": [
                {"color": _hex_alpha(0.0), **EASE},
                {"time": t_mid, "color": _hex_alpha(1.0), **EASE},
                {"time": dur, "color": _hex_alpha(1.0)},
            ]}
    return bones, slots


def build_out(bone_roles, dur=0.4):
    """退場:縮出 + 特效淡出。非週期。"""
    bones, slots = {}, {}
    for i, (bone, slot, role) in enumerate(bone_roles):
        bones[bone] = {"scale": [
            {"x": 1.0, "y": 1.0, **EASE},
            {"time": dur, "x": 0.05, "y": 0.05},
        ]}
        if role == "effect":
            slots[slot] = {"color": [
                {"color": _hex_alpha(1.0), **EASE},
                {"time": dur, "color": _hex_alpha(0.0)},
            ]}
    return bones, slots


# beat key → 生成器(loop 類 beat 用 build_loop;入/退場各自)
LOOP_KEYS = {"Loop", "loop", "idle", "static"}
IN_KEYS = {"In", "comeout", "land"}
OUT_KEYS = {"Out", "close"}


def build_animations(psd_path, spine_dir, genre="slot_bigwin", period=2.0):
    skel_path = os.path.join(spine_dir, "skeleton.json")
    skel = json.load(open(skel_path, encoding="utf-8"))
    bone_names = {b["name"] for b in skel["bones"]}
    slot_names = {s["name"] for s in skel["slots"]}

    spec = analyze(psd_path, genre)
    sb = spec["3_motion_storyboard"]
    # 用第一個 beat 的 parts 列表建 (bone, slot, role);過濾不存在的 bone
    first = sb["beats"][0]["parts"]
    bone_roles = []
    for row in first:
        slot = _safe(row["part"])
        bone = "b_" + slot
        if bone in bone_names and slot in slot_names:
            bone_roles.append((bone, slot, _role_of(row)))

    anims = {}
    for beat in sb["beats"]:
        key = beat["beat"]
        if key in LOOP_KEYS:
            bd, sd = build_loop(bone_roles, period)
        elif key in IN_KEYS:
            bd, sd = build_in(bone_roles)
        elif key in OUT_KEYS:
            bd, sd = build_out(bone_roles)
        else:
            continue
        a = {}
        if bd:
            a["bones"] = bd
        if sd:
            a["slots"] = sd
        anims[key] = a

    skel["animations"] = anims
    json.dump(skel, open(skel_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"out": skel_path, "genre": genre, "animations": list(anims.keys()),
            "loop_beats": [k for k in anims if k in LOOP_KEYS],
            "animated_bones": len(bone_roles), "period": period,
            "roles": {b: r for b, _, r in bone_roles}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd")
    ap.add_argument("spine_dir", help="build_spine.py 產出的目錄(含 skeleton.json)")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--period", type=float, default=2.0)
    a = ap.parse_args()
    s = build_animations(a.psd, a.spine_dir, a.genre, a.period)
    print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
