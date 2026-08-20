#!/usr/bin/env python3
"""S1 #3 分鏡 → Spine 3.8 動畫 keyframe(讓產出的素材「會動」)。

`build_spine.py` 產出的素材只有 setup pose(`"animations": {}`)。本工具把分析器的
**動作分鏡(3_motion_storyboard)** 的每個 beat(In/Loop/Out …)+ 每件的結構角色
(body/head/limb/effect)確定性地轉成 Spine 3.8 `animations` 的 bone/slot timeline,
產出「會動」的素材。純 CPU、可自驗、不靠 ML(動作幅度/相位是**由類型先驗參數化**的確定性映射,
非學來的美術決定)。

座標/命名約定必須與 build_spine 一致:bone=`b_<safe(件名)>`(件中心, parent=root)、
slot=`<safe(件名)>`。translate/scale/rotate 皆相對該 bone(setup 為件中心)。

## 動作語彙(beat × 角色 → timeline)
- **In(入場爆發)**:body 彈入+scale overshoot;limb 大幅甩入(rotate swing);
  effect 炸開(scale 峰值 + slot alpha 0→ff)。→ 大幅、單程、末幀落回 setup。
- **Loop(待機循環)**:body 呼吸(scale/translate ±小);head 微點頭(rotate ±小);
  limb 末梢擺盪(rotate ±小,**相位錯開**);effect 脈動(alpha/scale ±小)。
  → **首尾同值(seamless loop)**、小幅。
- **Out(退場)**:全體 scale→0 + slot alpha→0(縮出/淡出);effect 收斂更快。
  → 末幀歸零。

## 驗收目標(AC — 由 validate_animation.py 量化,不靠肉眼)
- AC1 結構合法:所有 timeline 參照的 bone/slot 都存在;每 timeline `time` 嚴格遞增;
  緊湊 bezier `curve` 僅為 缺省(linear)/ "stepped" / 4 個數值散鍵之一。
- AC2 語意幅度分帶:
  - In 至少一 bone 有大幅動作(scale overshoot ≥0.08 或 rotate range ≥20°);effect slot alpha 0→255。
  - Loop 每 timeline **首尾同值**(seamless);且幅度小(scale 偏離 1 ≤0.06、rotate range ≤12°)但 >0(非靜止)。
  - Out 末幀 scale≈0 或 slot alpha≈0(退場歸零)。
- AC3 角色分化:effect 件有 slot color(alpha)timeline;limb 件 Loop 相位錯開(≥2 limb 時峰值時刻不同)。
- AC4 非平凡:每個 animation 至少 1 條 timeline 且有非零運動幅度。
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "mesh_gen"))
from analyze_target import analyze


def safe(name):
    return name.replace("/", "_").replace("\\", "_").replace(" ", "_")


# 平滑緩動(Spine 3.8 緊湊 bezier 散鍵):ease-in-out 手把。端點值不受影響(驗證器查端點)。
EASE = dict(curve=0.25, c2=0.0, c3=0.75, c4=1.0)


def _kf(time, ease=False, **vals):
    f = {"time": round(time, 4)}
    f.update({k: (round(v, 4) if isinstance(v, float) else v) for k, v in vals.items()})
    if ease:
        f.update(EASE)
    return f


def _role_of(part):
    return "effect" if part["classification_is_effect"] else (part["struct_role"] or "limb")


def _parts_from_spec(spec):
    """把 spec 攤平成動畫需要的欄位:name/safe/role/effect/centroid/z + limb 序(相位用)。"""
    eff = {e["name"]: e for e in spec["2_effects"]}
    out = []
    for p in spec["1_movable_parts"]:
        e = eff.get(p["name"], {})
        out.append({
            "name": p["name"], "safe": safe(p["name"]),
            "bone": "b_" + safe(p["name"]), "slot": safe(p["name"]),
            "classification_is_effect": bool(e.get("is_effect")),
            "struct_role": e.get("struct_role"),
            "centroid": p["centroid"], "z": p["z"],
        })
    # limb 相位序(以 z 排序穩定)
    limbs = [q for q in out if _role_of(q) == "limb"]
    limbs.sort(key=lambda q: q["z"])
    for i, q in enumerate(limbs):
        q["limb_idx"] = i
    for q in out:
        q.setdefault("limb_idx", 0)
    return out


# ---- 各 beat 的 timeline 合成 ---------------------------------------------

def _anim_in(parts, W, H, dur=0.5):
    """入場爆發:大幅、單程、末幀落回 setup(0 位移 / scale 1 / alpha ff)。"""
    bones, slots = {}, {}
    peak = dur * 0.6
    for p in parts:
        role = _role_of(p)
        b = p["bone"]
        if role == "effect":
            # 炸開:scale 0 → 1.3 → 1.0;slot alpha 0 → ff
            bones[b] = {"scale": [_kf(0, x=0.0, y=0.0, ease=True),
                                   _kf(peak, x=1.3, y=1.3, ease=True),
                                   _kf(dur, x=1.0, y=1.0)]}
            slots[p["slot"]] = {"color": [_kf(0, color="ffffff00", ease=True),
                                          _kf(peak, color="ffffffff", ease=True),
                                          _kf(dur, color="ffffffff")]}
        elif role == "limb":
            # 大幅甩入:rotate -40 → +12 → 0(相位錯開起手)。
            # 中幀時刻須嚴格落在 (0, dur):相位位移用「剩餘空間的比例」分配,永不觸及 dur。
            n = max(1, sum(1 for q in parts if _role_of(q) == "limb"))
            frac = p["limb_idx"] / n                       # [0,1)
            mid = peak + frac * (dur - peak) * 0.6         # ∈ [peak, dur) 之內
            sign = -1 if p["limb_idx"] % 2 == 0 else 1
            bones[b] = {"rotate": [_kf(0, angle=sign * -40.0, ease=True),
                                   _kf(mid, angle=sign * 12.0, ease=True),
                                   _kf(dur, angle=0.0)]}
        elif role == "head":
            bones[b] = {"rotate": [_kf(0, angle=-8.0, ease=True),
                                   _kf(peak, angle=4.0, ease=True),
                                   _kf(dur, angle=0.0)],
                        "translate": [_kf(0, x=0.0, y=-0.10 * H, ease=True),
                                      _kf(dur, x=0.0, y=0.0)]}
        else:  # body
            # 彈入 + overshoot 縮放:scale 0.2 → 1.12 → 1.0;由下方彈入
            bones[b] = {"scale": [_kf(0, x=0.2, y=0.2, ease=True),
                                  _kf(peak, x=1.12, y=1.12, ease=True),
                                  _kf(dur, x=1.0, y=1.0)],
                        "translate": [_kf(0, x=0.0, y=-0.14 * H, ease=True),
                                      _kf(dur, x=0.0, y=0.0)]}
    return {"bones": bones, "slots": slots}


def _anim_loop(parts, W, H, dur=1.2):
    """待機循環:小幅、seamless(首尾同值)。half=dur/2 為峰值。"""
    bones, slots = {}, {}
    half = dur / 2.0
    for p in parts:
        role = _role_of(p)
        b = p["bone"]
        if role == "effect":
            # 脈動:alpha ff → cc → ff;scale ±0.03
            bones[b] = {"scale": [_kf(0, x=1.0, y=1.0, ease=True),
                                  _kf(half, x=1.03, y=1.03, ease=True),
                                  _kf(dur, x=1.0, y=1.0)]}
            slots[p["slot"]] = {"color": [_kf(0, color="ffffffff", ease=True),
                                          _kf(half, color="ffffffcc", ease=True),
                                          _kf(dur, color="ffffffff")]}
        elif role == "limb":
            # 末梢擺盪 ±4°,相位錯開:swing(t)=A·sin(2π t/dur + φ_i),φ_i=2π·idx/n。
            # 以每 1/4 週期取樣(0,¼,½,¾,dur)→ 保證非零幅度、峰值時刻依相位錯開;
            # sin 週期性使 t=dur 值==t=0 值 → seamless(末幀顯式對齊避免浮點漂移)。
            import math
            n = max(1, sum(1 for q in parts if _role_of(q) == "limb"))
            A = 4.0
            phi = 2 * math.pi * (p["limb_idx"] / n)
            fr = []
            for k in range(5):
                t = dur * k / 4.0
                ang = A * math.sin(2 * math.pi * (t / dur) + phi)
                fr.append(_kf(t, angle=(0.0 if k == 4 else ang), ease=(k < 4)))
            fr[4]["angle"] = fr[0]["angle"]     # 顯式首尾同值
            bones[b] = {"rotate": fr}
        elif role == "head":
            bones[b] = {"rotate": [_kf(0, angle=0.0, ease=True),
                                   _kf(half, angle=2.0, ease=True),
                                   _kf(dur, angle=0.0)]}
        else:  # body 呼吸
            bones[b] = {"scale": [_kf(0, x=1.0, y=1.0, ease=True),
                                  _kf(half, x=1.015, y=1.025, ease=True),
                                  _kf(dur, x=1.0, y=1.0)],
                        "translate": [_kf(0, x=0.0, y=0.0, ease=True),
                                      _kf(half, x=0.0, y=0.012 * H, ease=True),
                                      _kf(dur, x=0.0, y=0.0)]}
    return {"bones": bones, "slots": slots}


def _anim_out(parts, W, H, dur=0.4):
    """退場:scale → 0 + slot alpha → 0;effect 收斂更快。"""
    bones, slots = {}, {}
    for p in parts:
        role = _role_of(p)
        b = p["bone"]
        end = dur * (0.7 if role == "effect" else 1.0)
        bones[b] = {"scale": [_kf(0, x=1.0, y=1.0, ease=True),
                              _kf(end, x=0.0, y=0.0)]}
        slots[p["slot"]] = {"color": [_kf(0, color="ffffffff", ease=True),
                                      _kf(end, color="ffffff00")]}
    return {"bones": bones, "slots": slots}


BEAT_SYNTH = {"In": _anim_in, "Loop": _anim_loop, "Out": _anim_out,
              # slot_reveal 類型的 beat 對映到三大骨幹
              "comeout": _anim_in, "open": _anim_in, "idle": _anim_loop,
              "loop": _anim_loop, "static": _anim_loop, "hit": _anim_in,
              "close": _anim_out, "land": _anim_in, "win": _anim_in, "accent": _anim_loop}


def synth_animations(spec, W, H, bone_names=None, slot_names=None):
    """spec + 畫布尺寸 → animations dict。若給 bone/slot 集合則過濾(只保留素材存在者)。"""
    parts = _parts_from_spec(spec)
    beats = [b["beat"] for b in spec["3_motion_storyboard"]["beats"]]
    anims = {}
    seen = {}
    for beat in beats:
        synth = BEAT_SYNTH.get(beat)
        if synth is None:
            continue
        a = synth(parts, W, H)
        # 過濾不存在的 bone/slot(素材可能只做部分件)
        if bone_names is not None:
            a["bones"] = {k: v for k, v in a["bones"].items() if k in bone_names}
        if slot_names is not None:
            a["slots"] = {k: v for k, v in a["slots"].items() if k in slot_names}
        if not a["bones"] and not a["slots"]:
            continue
        # 同一 synth 函式可能對映多 beat(如 idle/loop 都 → loop)→ 用實際 beat 名當 animation 名,去重
        name = beat
        seen[name] = seen.get(name, 0) + 1
        if seen[name] > 1:
            name = f"{beat}{seen[name]}"
        anims[name] = a
    return anims


def apply_to_build(out_dir, psd_path, genre="slot_bigwin"):
    """讀取 build_spine 產出的 skeleton.json,合成動畫寫回。"""
    sk_path = os.path.join(out_dir, "skeleton.json")
    sk = json.load(open(sk_path, encoding="utf-8"))
    W = sk["skeleton"]["width"]; H = sk["skeleton"]["height"]
    bone_names = {b["name"] for b in sk["bones"]}
    slot_names = {s["name"] for s in sk["slots"]}
    spec = analyze(psd_path, genre)
    anims = synth_animations(spec, W, H, bone_names, slot_names)
    sk["animations"] = anims
    json.dump(sk, open(sk_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return {"out": out_dir, "animations": list(anims.keys()),
            "n_timelines": sum(len(a["bones"]) + len(a["slots"]) for a in anims.values())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("psd", help="來源分層 PSD(重跑分析器取 storyboard/roles)")
    ap.add_argument("--out", required=True, help="build_spine 產出目錄(含 skeleton.json)")
    ap.add_argument("--genre", default="slot_bigwin")
    a = ap.parse_args()
    print(json.dumps(apply_to_build(a.out, a.psd, a.genre), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
