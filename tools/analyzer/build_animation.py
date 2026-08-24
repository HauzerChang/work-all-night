#!/usr/bin/env python3
"""分鏡 → 動畫 keyframe(storyboard → Spine 3.8 animations timeline)。

接續 build_spine.py:build_spine 產出 setup-pose 素材(animations 留空),本工具讀
`analyze_target` 的 #3 分鏡(beats: In/Loop/Out,每件帶 role)+ 已建好的 skeleton.json,
用「角色參數化」的確定性規則生成 bone(rotate/translate/scale)與 slot(color alpha)timeline,
寫回 skeleton.json 的 `animations`。純 CPU、無 ML,可被 validate_animation.py 量化驗收。

角色 → 動作規則(校準自真實 slot loop `main_draw_loop`:身體呼吸 ~6%、末梢擺盪 ~10°、循環 ~0.67s):
  body   : Loop 呼吸(scale ±bs, 微 translate y);In 彈入 overshoot;Out 縮出。
  limb   : Loop 末梢擺盪(rotate ±sw, 左右相位錯開);In 大幅甩入(rotate 大);Out 縮出。
  head   : Loop 微點頭(rotate 小 + ty 小);In 隨身體回正;Out 縮出。
  特效   : Loop 脈動/緩轉(scale pulse + rotate 小 + slot alpha 脈動);In 炸開(scale+rotate+alpha 0→1);Out 收斂淡出。

座標/格式(Spine 3.8):rotate={time,angle};translate/scale={time,x,y};slot color={time,color:"rrggbbaa"}。
省略時 rotate angle=0、translate x/y=0、scale x/y=1、alpha=ff。曲線用 ease-in-out 緊湊 bezier。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from analyze_target import analyze

# ease-in-out 緊湊 bezier(Spine 3.8 散鍵:curve=cx1,c2=cy1,c3=cx2,c4=cy2)
EASE = {"curve": 0.25, "c2": 0.0, "c3": 0.75, "c4": 1.0}


def safe(name):
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


def kf(time, curve=True, **vals):
    k = {}
    if time:                      # time=0 省略(對齊真實檔慣例)
        k["time"] = round(time, 4)
    for kk, vv in vals.items():
        k[kk] = round(vv, 4)
    if curve:
        k.update(EASE)
    return k


def role_of(part_entry):
    r = part_entry.get("role", "")
    if r in ("body", "head", "limb"):
        return r
    return "fx"                    # 特效 / 其他


def alpha_hex(a):
    return "ffffff" + format(max(0, min(255, int(round(a * 255)))), "02x")


def gen_loop(parts, dur=0.8, limb_idx=None):
    """待機循環:seamless(首尾同值),幅度細微。回傳 (bones_tl, slots_tl)。"""
    bt, st = {}, {}
    half = dur / 2.0
    q = dur / 4.0
    for i, p in enumerate(parts):
        role = role_of(p)
        bone = "b_" + safe(p["part"])
        slot = p["part"]
        if role == "body":
            bs, ty = 0.03, 4.0     # 呼吸 3% + 微上抬
            bt[bone] = {
                "scale": [kf(0, x=1, y=1), kf(half, x=1 + bs, y=1 - bs * 0.6), kf(dur, x=1, y=1, curve=False)],
                "translate": [kf(0, x=0, y=0), kf(half, x=0, y=ty), kf(dur, x=0, y=0, curve=False)],
            }
        elif role == "head":
            r, ty = 2.0, 2.0       # 微點頭
            bt[bone] = {
                "rotate": [kf(0, angle=0), kf(half, angle=-r), kf(dur, angle=0, curve=False)],
                "translate": [kf(0, x=0, y=0), kf(half, x=0, y=ty), kf(dur, x=0, y=0, curve=False)],
            }
        elif role == "limb":
            sw = 6.0               # 末梢擺盪 ±6°;左右相位相反
            sign = 1.0 if (limb_idx and limb_idx.get(bone, 0) % 2 == 0) else -1.0
            bt[bone] = {
                "rotate": [kf(0, angle=sign * sw), kf(half, angle=-sign * sw), kf(dur, angle=sign * sw, curve=False)],
            }
        else:                      # fx / 特效:脈動 + 緩轉 + alpha 脈動
            ps, rr = 0.05, 3.0
            bt[bone] = {
                "scale": [kf(0, x=1, y=1), kf(half, x=1 + ps, y=1 + ps), kf(dur, x=1, y=1, curve=False)],
                "rotate": [kf(0, angle=-rr), kf(half, angle=rr), kf(dur, angle=-rr, curve=False)],
            }
            st[slot] = {"color": [kf(0, curve=False) | {"color": alpha_hex(1.0)},
                                  {"time": round(half, 4), "color": alpha_hex(0.7), **EASE},
                                  {"time": round(dur, 4), "color": alpha_hex(1.0)}]}
    return bt, st


def gen_in(parts, dur=0.4, limb_idx=None):
    """入場爆發:縮放彈入 overshoot,肢體大幅甩入,特效炸開。收於 setup(neutral)。"""
    bt, st = {}, {}
    p1, p2 = dur * 0.6, dur
    for p in parts:
        role = role_of(p)
        bone = "b_" + safe(p["part"])
        slot = p["part"]
        if role == "body":
            bt[bone] = {"scale": [kf(0, x=0.2, y=0.2), kf(p1, x=1.1, y=1.08), kf(p2, x=1, y=1, curve=False)],
                        "translate": [kf(0, x=0, y=40), kf(p1, x=0, y=-6), kf(p2, x=0, y=0, curve=False)]}
        elif role == "head":
            bt[bone] = {"scale": [kf(0, x=0.4, y=0.4), kf(p1, x=1.05, y=1.05), kf(p2, x=1, y=1, curve=False)],
                        "rotate": [kf(0, angle=8), kf(p1, angle=-3), kf(p2, angle=0, curve=False)]}
        elif role == "limb":
            sign = 1.0 if (limb_idx and limb_idx.get(bone, 0) % 2 == 0) else -1.0
            bt[bone] = {"rotate": [kf(0, angle=sign * 45), kf(p1, angle=-sign * 6), kf(p2, angle=0, curve=False)],
                        "scale": [kf(0, x=0.3, y=0.3), kf(p1, x=1.05, y=1.05), kf(p2, x=1, y=1, curve=False)],
                        "translate": [kf(0, x=-sign * 30, y=0), kf(p2, x=0, y=0, curve=False)]}
        else:                      # fx 炸開
            bt[bone] = {"scale": [kf(0, x=0, y=0), kf(p1, x=1.3, y=1.3), kf(p2, x=1, y=1, curve=False)],
                        "rotate": [kf(0, angle=-30), kf(p2, angle=0, curve=False)]}
            st[slot] = {"color": [kf(0, curve=False) | {"color": alpha_hex(0.0)},
                                  {"time": round(p2, 4), "color": alpha_hex(1.0)}]}
    return bt, st


def gen_out(parts, dur=0.3):
    """退場:主體縮出/淡出,特效收斂。"""
    bt, st = {}, {}
    for p in parts:
        role = role_of(p)
        bone = "b_" + safe(p["part"])
        slot = p["part"]
        bt[bone] = {"scale": [kf(0, x=1, y=1), kf(dur, x=0.05, y=0.05, curve=False)]}
        st[slot] = {"color": [kf(0, curve=False) | {"color": alpha_hex(1.0)},
                              {"time": round(dur, 4), "color": alpha_hex(0.0)}]}
    return bt, st


def build_animations(spec, skeleton):
    bone_names = {b["name"] for b in skeleton["bones"]}
    sb = spec["3_motion_storyboard"]
    beats = {b["beat"]: b["parts"] for b in sb["beats"]}
    # 建 limb 索引(供左右相位錯開)
    def limb_index(parts):
        idx, c = {}, 0
        for p in parts:
            if role_of(p) == "limb":
                idx["b_" + safe(p["part"])] = c
                c += 1
        return idx

    anims = {}
    if "In" in beats:
        bt, st = gen_in(beats["In"], limb_idx=limb_index(beats["In"]))
        anims["In"] = _assemble(bt, st, bone_names)
    if "Loop" in beats:
        bt, st = gen_loop(beats["Loop"], limb_idx=limb_index(beats["Loop"]))
        anims["Loop"] = _assemble(bt, st, bone_names)
    if "Out" in beats:
        bt, st = gen_out(beats["Out"])
        anims["Out"] = _assemble(bt, st, bone_names)
    return anims


def _assemble(bt, st, bone_names):
    # 丟掉不存在的 bone(健壯性)
    bt = {b: tl for b, tl in bt.items() if b in bone_names}
    a = {}
    if bt:
        a["bones"] = bt
    if st:
        a["slots"] = st
    return a


def build(psd_path, spine_dir, genre="slot_bigwin"):
    spec = analyze(psd_path, genre)
    sk_path = os.path.join(spine_dir, "skeleton.json")
    skeleton = json.load(open(sk_path, encoding="utf-8"))
    anims = build_animations(spec, skeleton)
    skeleton["animations"] = anims
    json.dump(skeleton, open(sk_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"spine_dir": spine_dir, "animations": {k: {"bones": len(v.get("bones", {})),
            "slots": len(v.get("slots", {}))} for k, v in anims.items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd")
    ap.add_argument("spine_dir")
    ap.add_argument("--genre", default="slot_bigwin")
    a = ap.parse_args()
    s = build(a.psd, a.spine_dir, a.genre)
    print(json.dumps(s, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
