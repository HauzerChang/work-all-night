#!/usr/bin/env python3
"""分鏡 → 動畫 keyframe(S1 候選 0d)。

把 analyze_target 的 `3_motion_storyboard`(role-based beats:In / Loop / Out)確定性地
轉成 Spine 3.8 `animations`(bone TRS timeline + slot color/alpha),讓 build_spine 產出的
素材「會動」。純 CPU、無隨機、可自我量化驗收。

角色→運動模板(role motion templates):
  特效  : 緩轉一圈(seamless spin)+ scale 脈動 + alpha 脈動
  body : 呼吸(scale ±小 + 垂直 bob)
  head : 微點頭(rotate 小)+ 隨身體 bob
  limb : 末梢擺盪(rotate sine,左右相位錯開)
  其他  : 視為 body 呼吸(通用)

三個 beat:
  In  (入場爆發,~0.5s):由小 overshoot 彈入 + alpha 淡入 + limb 甩入 + 特效 spin-in
  Loop(待機呼吸,~2.0s,seamless):首尾 keyframe 相等,可無縫循環
  Out (退場,~0.35s):scale→0 + alpha→0

座標約定(對齊 build_spine):每件一根 bone,位於件中心、無旋轉、scale=1、parent=root。
  → translate 為相對 setup 的位移(root 空間);rotate 為角度;scale 為絕對倍率。
  ⚠️ 誠實界定:bone 原點在件中心(非關節 pivot),故 limb 旋轉是繞中心而非肩點
     (關節 pivot 推斷屬 S5,未做)。對待機呼吸/微擺盪視覺可接受。
"""
import json

# ---- 緩動曲線(Spine 3.8 緊湊 bezier 散鍵)----
EASE_INOUT = {"curve": 0.25, "c2": 0.0, "c3": 0.75, "c4": 1.0}  # 平滑進出
EASE_OUT = {"curve": 0.0, "c2": 0.0, "c3": 0.5, "c4": 1.0}      # 快起緩收(彈入尾段)


def _k(time, curve=None, **vals):
    """組一個 keyframe;time==0 時省略 time 鍵(對齊真實 3.8 匯出慣例)。"""
    d = {}
    if time != 0:
        d["time"] = round(time, 4)
    for kk, vv in vals.items():
        d[kk] = round(vv, 4) if isinstance(vv, float) else vv
    if curve:
        d.update(curve)
    return d


def _hex_alpha(a):
    """0..1 alpha → 'ffffffAA'(RGB 全白,只調 alpha)。"""
    a = max(0, min(255, int(round(a * 255))))
    return "ffffff{:02x}".format(a)


def _sine_rotate(dur, amp, phase, n=4, curve=EASE_INOUT):
    """seamless 正弦擺盪 rotate timeline;首尾相等可循環。phase 0..1。"""
    import math
    keys = []
    for i in range(n + 1):
        t = dur * i / n
        ang = amp * math.sin(2 * math.pi * (i / n + phase))
        keys.append(_k(t, curve=(curve if i < n else None), angle=ang))
    return keys


# ---------------- Loop(待機呼吸,seamless)----------------
def _loop_bone(role, dur, phase):
    tl = {}
    if role == "特效":
        # 緩轉一圈(0→360 seamless,等速線性即可無縫)+ 輕微 scale 脈動
        tl["rotate"] = [_k(0, angle=0.0), _k(dur, angle=360.0)]
        tl["scale"] = [_k(0, curve=EASE_INOUT, x=1.0, y=1.0),
                       _k(dur / 2, curve=EASE_INOUT, x=1.03, y=1.03),
                       _k(dur, x=1.0, y=1.0)]
    elif role == "body":
        # 呼吸:縱向撐大 + 上浮
        tl["scale"] = [_k(0, curve=EASE_INOUT, x=1.0, y=1.0),
                       _k(dur / 2, curve=EASE_INOUT, x=1.008, y=1.025),
                       _k(dur, x=1.0, y=1.0)]
        tl["translate"] = [_k(0, curve=EASE_INOUT, x=0.0, y=0.0),
                           _k(dur / 2, curve=EASE_INOUT, x=0.0, y=4.0),
                           _k(dur, x=0.0, y=0.0)]
    elif role == "head":
        # 微點頭 + 隨身體上浮
        tl["rotate"] = [_k(0, curve=EASE_INOUT, angle=0.0),
                        _k(dur / 2, curve=EASE_INOUT, angle=-2.0),
                        _k(dur, angle=0.0)]
        tl["translate"] = [_k(0, curve=EASE_INOUT, x=0.0, y=0.0),
                           _k(dur / 2, curve=EASE_INOUT, x=0.0, y=3.0),
                           _k(dur, x=0.0, y=0.0)]
    elif role == "limb":
        # 末梢擺盪(相位錯開)
        tl["rotate"] = _sine_rotate(dur, amp=3.0, phase=phase)
    else:
        tl["scale"] = [_k(0, curve=EASE_INOUT, x=1.0, y=1.0),
                       _k(dur / 2, curve=EASE_INOUT, x=1.012, y=1.012),
                       _k(dur, x=1.0, y=1.0)]
    return tl


def _loop_slot(role, dur):
    if role == "特效":
        return {"color": [_k(0, curve=EASE_INOUT, color=_hex_alpha(0.80)),
                          _k(dur / 2, curve=EASE_INOUT, color=_hex_alpha(1.0)),
                          _k(dur, color=_hex_alpha(0.80))]}
    return None


# ---------------- In(入場爆發)----------------
def _in_bone(role, dur):
    tl = {}
    if role == "特效":
        tl["rotate"] = [_k(0, curve=EASE_OUT, angle=-90.0), _k(dur, angle=0.0)]
        tl["scale"] = [_k(0, curve=EASE_OUT, x=0.3, y=0.3),
                       _k(dur * 0.7, curve=EASE_INOUT, x=1.2, y=1.2),
                       _k(dur, x=1.0, y=1.0)]
    elif role == "limb":
        tl["rotate"] = [_k(0, curve=EASE_OUT, angle=-40.0),
                        _k(dur * 0.75, curve=EASE_INOUT, angle=6.0),
                        _k(dur, angle=0.0)]
        tl["scale"] = [_k(0, curve=EASE_OUT, x=0.5, y=0.5),
                       _k(dur * 0.7, curve=EASE_INOUT, x=1.08, y=1.08),
                       _k(dur, x=1.0, y=1.0)]
    else:  # body / head / 其他:彈入 + overshoot
        tl["scale"] = [_k(0, curve=EASE_OUT, x=0.2, y=0.2),
                       _k(dur * 0.7, curve=EASE_INOUT, x=1.1, y=1.1),
                       _k(dur, x=1.0, y=1.0)]
        tl["translate"] = [_k(0, curve=EASE_OUT, x=0.0, y=-30.0),
                           _k(dur, x=0.0, y=0.0)]
    return tl


def _in_slot(role, dur):
    peak = 1.0
    return {"color": [_k(0, curve=EASE_OUT, color=_hex_alpha(0.0)),
                      _k(dur * 0.5, curve=EASE_INOUT, color=_hex_alpha(peak)),
                      _k(dur, color=_hex_alpha(1.0))]}


# ---------------- Out(退場)----------------
def _out_bone(role, dur):
    return {"scale": [_k(0, curve=EASE_INOUT, x=1.0, y=1.0), _k(dur, x=0.0, y=0.0)]}


def _out_slot(role, dur):
    return {"color": [_k(0, curve=EASE_INOUT, color=_hex_alpha(1.0)),
                      _k(dur, color=_hex_alpha(0.0))]}


DURATIONS = {"In": 0.5, "Loop": 2.0, "Out": 0.35}


def build_animations(spec, part_bone, part_slot):
    """spec: analyze_target 輸出;part_bone/part_slot: {原始件名: bone/slot 名}。
    回傳 Spine `animations` dict(In/Loop/Out)。"""
    sb = spec.get("3_motion_storyboard", {})
    # role per part(union across beats)
    role_of = {}
    for b in sb.get("beats", []):
        for p in b.get("parts", []):
            role_of[p["part"]] = p.get("role", "body")
    # 未在分鏡列出的件 → 用效果偵測補「特效」,否則 body
    eff_names = {e["name"] for e in spec.get("2_effects", []) if e.get("is_effect")}
    parts = [p["name"] for p in spec.get("1_movable_parts", [])]
    for nm in parts:
        if nm not in role_of:
            role_of[nm] = "特效" if nm in eff_names else "body"

    # limb 相位分派(左右錯開):依出現序 0, 0.5, 0.25, 0.75...
    limb_seq = [nm for nm in parts if role_of.get(nm) == "limb"]
    phase_of = {}
    for i, nm in enumerate(limb_seq):
        phase_of[nm] = 0.0 if i % 2 == 0 else 0.5

    beat_fns = {
        "In": (_in_bone, _in_slot),
        "Loop": (None, _loop_slot),   # Loop bone 需 phase → 特判
        "Out": (_out_bone, _out_slot),
    }
    anims = {}
    for beat in ["In", "Loop", "Out"]:
        dur = DURATIONS[beat]
        bones_tl, slots_tl = {}, {}
        for nm in parts:
            if nm not in part_bone:
                continue
            role = role_of.get(nm, "body")
            bname = part_bone[nm]
            sname = part_slot.get(nm)
            if beat == "Loop":
                btl = _loop_bone(role, dur, phase_of.get(nm, 0.0))
            else:
                btl = beat_fns[beat][0](role, dur)
            if btl:
                bones_tl[bname] = btl
            stl = beat_fns[beat][1](role, dur)
            if stl and sname:
                slots_tl[sname] = stl
        a = {}
        if bones_tl:
            a["bones"] = bones_tl
        if slots_tl:
            a["slots"] = slots_tl
        anims[beat] = a
    return anims


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("spec", help="analyze_target 輸出的 spec json")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    spec = json.load(open(a.spec, encoding="utf-8"))
    parts = [p["name"] for p in spec.get("1_movable_parts", [])]
    safe = lambda n: n.replace("/", "_").replace("\\", "_").replace(" ", "_")
    pb = {nm: "b_" + safe(nm) for nm in parts}
    ps = {nm: safe(nm) for nm in parts}
    anims = build_animations(spec, pb, ps)
    out = json.dumps(anims, ensure_ascii=False, indent=1)
    if a.out:
        open(a.out, "w", encoding="utf-8").write(out)
        print("wrote", a.out)
    else:
        print(out)
