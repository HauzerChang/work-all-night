#!/usr/bin/env python3
"""分鏡 → 動畫 keyframe(storyboard → Spine 3.8 animations timeline)。

接續 build_spine.py:build_spine 產出 setup-pose 素材但 `animations:{}`(不會動)。
本工具把 analyze_target 的 #3 動作分鏡(每件 role→action)確定性地轉成 Spine bone/slot
timeline,讓素材「會動」。純 CPU、可自驅、可用 validate_animation.py 幾何量化自驗。

設計原則(全部確定性,無 ML):
  * 動作幅度**以真實生產動畫校準**(main_draw / Award 的 Loop/idle;見 knowledge/s1-storyboard-to-animation.md)。
  * **Loop 嚴格無縫**:每個 channel 首 keyframe 值 == 末 keyframe 值(真值錨:main_draw_loop 首末差=0)。
  * **錨點 = neutral setup pose**:Loop 繞 setup 振盪(首末=neutral);In 由 off-pose→neutral;Out 由 neutral→off-pose。
    → 保證 In.末 == Loop.首 == Out.首(轉場連續)。
  * **末梢相位錯開**:多個 limb 用不同相位 φ,且以 (sin(θ+φ)-sin(φ)) 平移使首末仍=0(錨在 neutral)。

Spine 3.8 timeline 格式:
  bones: { b_x: { rotate:[{time,angle}], translate:[{time,x,y}], scale:[{time,x,y}] } }
  slots: { name: { color:[{time,color:"rrggbbaa"}] } }  (預設 channel 間線性內插)

座標/角色來源:role 由 analyze_target 分鏡取得(effect/head/body/limb),件→bone 名沿用
build_spine 慣例 b_<safe(part)>、slot 名 <safe(part)>。
"""
import argparse, json, math, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from analyze_target import analyze

# ── 校準常數(真實動畫觀測,取保守值,全落在 validate_animation 的真值 band 內)──
LOOP_DUR = 1.0
IN_DUR   = 0.5
OUT_DUR  = 0.4
N_LOOP   = 9      # Loop 每 channel 取樣點(含首末),線性表示連續函數

BREATHE_SY   = 0.03    # 身體呼吸 scale y 振幅(胸口起伏)
BREATHE_SX   = 0.015   # 反向 scale x(體積守恆感)
BREATHE_TY   = 4.0     # 身體微上浮 px
HEAD_ROT     = 3.0     # 頭微擺 deg
LIMB_ROT     = 5.0     # 末梢擺盪 deg
EFFECT_ROT   = 7.0     # 特效緩擺 deg(峰對峰=2×7=14°,落在真值 band ≤15° 內)
EFFECT_ALO   = 0.78    # 特效 alpha 脈動低點(高點=1.0)


def safe(name):
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


def _raised_cos(u):
    """u∈[0,1] → [0,1];u=0,1 時為 0,u=0.5 時為 1(無縫升降)。"""
    return 0.5 - 0.5 * math.cos(2 * math.pi * u)


def _phase_sine(u, phi):
    """平移正弦:sin(2π u + φ) - sin(φ);u=0,1 時皆為 0(錨 neutral、無縫、可相位錯開)。"""
    return math.sin(2 * math.pi * u + phi) - math.sin(phi)


def _hexa(alpha):
    a = max(0, min(255, round(alpha * 255)))
    return "ffffff%02x" % a


def _samples(fn, dur, n=N_LOOP):
    """在 [0,dur] 取 n 點,回傳 [(t, fn(u)), ...],u=t/dur。"""
    return [(round(dur * i / (n - 1), 4), fn(i / (n - 1))) for i in range(n)]


def _role_of(part_row):
    return "effect" if part_row["role"] == "特效" else part_row["role"]


def build_loop(role_rows):
    """回傳 (bones_dict, slots_dict) — 無縫待機 Loop。role_rows: [{name,role}]。"""
    bones, slots = {}, {}
    limb_idx = 0
    limbs = [r for r in role_rows if _role_of(r) == "limb"]
    n_limb = max(1, len(limbs))
    for r in role_rows:
        role = _role_of(r)
        bn = "b_" + safe(r["name"])
        sn = safe(r["name"])
        if role == "body":
            sy = _samples(lambda u: round(1 + BREATHE_SY * _raised_cos(u), 4), LOOP_DUR)
            sx = _samples(lambda u: round(1 - BREATHE_SX * _raised_cos(u), 4), LOOP_DUR)
            ty = _samples(lambda u: round(BREATHE_TY * _raised_cos(u), 3), LOOP_DUR)
            bones[bn] = {
                "scale": [{"time": t, "x": vx, "y": vy} for (t, vx), (_, vy) in zip(sx, sy)],
                "translate": [{"time": t, "x": 0, "y": v} for t, v in ty],
            }
        elif role == "head":
            rot = _samples(lambda u: round(HEAD_ROT * _phase_sine(u, 0.0), 3), LOOP_DUR)
            bones[bn] = {"rotate": [{"time": t, "angle": v} for t, v in rot]}
        elif role == "limb":
            phi = 2 * math.pi * (limb_idx / n_limb)   # 相位錯開
            limb_idx += 1
            rot = _samples(lambda u, p=phi: round(LIMB_ROT * _phase_sine(u, p), 3), LOOP_DUR)
            bones[bn] = {"rotate": [{"time": t, "angle": v} for t, v in rot]}
        elif role == "effect":
            rot = _samples(lambda u: round(EFFECT_ROT * _phase_sine(u, 0.0), 3), LOOP_DUR)
            bones[bn] = {"rotate": [{"time": t, "angle": v} for t, v in rot]}
            al = _samples(lambda u: 1 - (1 - EFFECT_ALO) * _raised_cos(u), LOOP_DUR)
            slots[sn] = {"color": [{"time": t, "color": _hexa(v)} for t, v in al]}
    return bones, slots


def build_in(role_rows):
    """入場:off-pose → neutral(末幀=Loop 首=neutral,轉場連續);允許較大幅度(轉場非待機)。"""
    bones, slots = {}, {}
    for r in role_rows:
        role = _role_of(r)
        bn = "b_" + safe(r["name"])
        sn = safe(r["name"])
        if role == "body":
            bones[bn] = {"scale": [
                {"time": 0, "x": 0.55, "y": 0.55},
                {"time": round(IN_DUR * 0.7, 4), "x": 1.08, "y": 1.08},  # overshoot 彈入
                {"time": IN_DUR, "x": 1, "y": 1}]}
            slots[sn] = {"color": [{"time": 0, "color": _hexa(0)}, {"time": IN_DUR, "color": _hexa(1)}]}
        elif role == "effect":
            bones[bn] = {"rotate": [{"time": 0, "angle": -90}, {"time": IN_DUR, "angle": 0}],
                         "scale": [{"time": 0, "x": 0.2, "y": 0.2}, {"time": IN_DUR, "x": 1, "y": 1}]}
            slots[sn] = {"color": [{"time": 0, "color": _hexa(0)}, {"time": IN_DUR, "color": _hexa(1)}]}
        else:  # head / limb 甩入
            bones[bn] = {"rotate": [{"time": 0, "angle": 18 if role == "limb" else 8},
                                    {"time": IN_DUR, "angle": 0}]}
            slots[sn] = {"color": [{"time": 0, "color": _hexa(0)}, {"time": IN_DUR, "color": _hexa(1)}]}
    return bones, slots


def build_out(role_rows):
    """退場:neutral(首幀=Loop 首)→ off-pose(縮出/淡出)。"""
    bones, slots = {}, {}
    for r in role_rows:
        role = _role_of(r)
        bn = "b_" + safe(r["name"])
        sn = safe(r["name"])
        if role == "body":
            bones[bn] = {"scale": [{"time": 0, "x": 1, "y": 1}, {"time": OUT_DUR, "x": 0.7, "y": 0.7}]}
        elif role == "effect":
            bones[bn] = {"scale": [{"time": 0, "x": 1, "y": 1}, {"time": OUT_DUR, "x": 0.3, "y": 0.3}]}
        slots[sn] = {"color": [{"time": 0, "color": _hexa(1)}, {"time": OUT_DUR, "color": _hexa(0)}]}
    return bones, slots


def build_accent(role_rows):
    """強調(open/hit/win):快速 pop 後回 neutral(首末=neutral,無縫);特效閃光。"""
    bones, slots = {}, {}
    dur = 0.4
    for r in role_rows:
        role = _role_of(r)
        bn = "b_" + safe(r["name"])
        sn = safe(r["name"])
        pop = 1.15 if role in ("body", "effect") else 1.08
        bones[bn] = {"scale": [
            {"time": 0, "x": 1, "y": 1},
            {"time": round(dur * 0.35, 4), "x": pop, "y": pop},
            {"time": dur, "x": 1, "y": 1}]}
        if role == "effect":
            slots[sn] = {"color": [
                {"time": 0, "color": _hexa(1)},
                {"time": round(dur * 0.35, 4), "color": _hexa(1)},
                {"time": dur, "color": _hexa(1)}]}
    return bones, slots


# beat key(各類型先驗)→ 語意類:enter / loop / exit / accent。
# 讓不同 genre 的分鏡都能對映到 4 個確定性動作原型,而非只認 In/Loop/Out。
BEAT_CLASS = {
    "in": "enter", "comeout": "enter", "land": "enter", "static": "enter",
    "loop": "loop", "idle": "loop",
    "out": "exit", "close": "exit",
    "open": "accent", "hit": "accent", "win": "accent", "accent": "accent",
}
CLASS_BUILDERS = {"enter": build_in, "loop": build_loop, "exit": build_out, "accent": build_accent}


def animate(skeleton_json, storyboard, out_json=None):
    """把 storyboard(analyze 的 #3)寫成 animations,回填 skeleton dict。"""
    sk = json.load(open(skeleton_json)) if isinstance(skeleton_json, str) else skeleton_json
    bone_names = {b["name"] for b in sk["bones"]}
    slot_names = {s["name"] for s in sk["slots"]}
    anims = {}
    for beat in storyboard["beats"]:
        key = beat["beat"]
        cls = BEAT_CLASS.get(key.lower())
        builder = CLASS_BUILDERS.get(cls)
        if not builder:
            continue
        rows = [{"name": p["part"], "role": p["role"]} for p in beat["parts"]]
        bones, slots = builder(rows)
        # 只保留 skeleton 內確實存在的 bone/slot
        bones = {k: v for k, v in bones.items() if k in bone_names}
        slots = {k: v for k, v in slots.items() if k in slot_names}
        anims[key] = {}
        if bones:
            anims[key]["bones"] = bones
        if slots:
            anims[key]["slots"] = slots
    sk["animations"] = anims
    if out_json:
        json.dump(sk, open(out_json, "w"), ensure_ascii=False, indent=1)
    return sk, anims


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd", help="原始分層 PSD(取 storyboard roles)")
    ap.add_argument("skeleton", help="build_spine 產出的 skeleton.json")
    ap.add_argument("--genre", default="slot_bigwin")
    ap.add_argument("--out", default=None, help="輸出 json(預設覆寫 skeleton)")
    a = ap.parse_args()
    spec = analyze(a.psd, a.genre)
    sb = spec["3_motion_storyboard"]
    out = a.out or a.skeleton
    _, anims = animate(a.skeleton, sb, out)
    summary = {"out": out, "genre": a.genre, "beats": list(anims.keys()),
               "channels": {k: {"bones": len(v.get("bones", {})), "slots": len(v.get("slots", {}))}
                            for k, v in anims.items()}}
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
