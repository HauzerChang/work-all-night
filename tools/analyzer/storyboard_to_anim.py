#!/usr/bin/env python3
"""P1(物理主線基底)— 分鏡 beat → Spine 動畫 keyframe 生成器(v1:待機呼吸 Loop)。

目標:讓 `build_spine` 的產物「會動」。把分鏡先驗(`genre_priors`)的 **idle/loop** beat
(角色:body 微呼吸 / head 微擺 / limb 末梢微盪)轉成 Spine 3.8 `animations` timeline。

v1 只做**待機呼吸 Loop**(最基礎、可無縫循環、純 CPU、可量化自驗)。
物理層(follow-through 相位延遲、overshoot、材質反應)留給 **P2 物理注入**在此基底上疊加。

校準自真實 `main_draw.main_idle2`:身體呼吸 = **scaleY 為主的脈動**(sy≈0.88~1.22,±~15%,週期~1s),
sx 幾乎不變(非體積守恆,與 `p1-motion-physics-analyzer` 結論一致)→ 生成器採 scaleY 主導。

無縫循環:keyframe t=0 == t=period(neutral),峰值在 period/2;兩段皆 bezier **ease-in-out**
(neutral↔peak 端點速度 0 → 呼吸在極端「停頓」感,且 motion_physics 量得高 inertia_index)。

自驗(AC,不靠肉眼):
  1. loop-close:_sample(0) == _sample(period)(bezier-aware)。
  2. 幅度有界且非零(呼吸該小:sy_amp、rot 在合理範圍)。
  3. 物理簽名:motion_physics 對本動畫 inertia_index > 0。
  4. round-trip:輸出 JSON 可重新 parse、動畫時長正確。
"""
import json, sys, copy
import numpy as np

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from motion_physics import _sample, ease_profile, _anim_duration  # noqa: E402

# bezier ease-in-out(慢起步 + 慢收尾;端點速度≈0)。緊湊格式:curve=cx1,c2=cy1,c3=cx2,c4=cy2。
EASE_IN_OUT = {"curve": 0.25, "c2": 0.0, "c3": 0.75, "c4": 1.0}


def _seg(frames):
    """把 [(time, {chan-vals})...] 的每個非末端 keyframe 標上 ease-in-out 曲線。"""
    for f in frames[:-1]:
        f.update(EASE_IN_OUT)
    return frames


def auto_roles(skel, body=None):
    """啟發式把 bones 分成 body / head / limbs。可用 body 參數覆蓋。
    body = 指定或「非 root、後代最多」的骨(軀幹);limbs = 葉骨(無子、深度≥2);
    head = body 的子骨中名含 head/face/eye 者。"""
    bones = skel["bones"]
    name = [b["name"] for b in bones]
    parent = {b["name"]: b.get("parent") for b in bones}
    children = {n: [] for n in name}
    for n in name:
        if parent[n]:
            children[parent[n]].append(n)

    def descendants(n):
        out = 0
        for c in children[n]:
            out += 1 + descendants(c)
        return out

    def depth(n):
        d = 0
        while parent.get(n):
            n = parent[n]; d += 1
        return d

    # body 選取:①名稱關鍵字(軀幹)②後代最多的非 root 骨(階層 rig)③退回第一個非 root。
    # (build_spine 產出為**扁平 rig**:各件皆 root 直屬 → 後代數全 0,必須靠名稱關鍵字選對軀幹。)
    BODY_KW = ("身體", "body", "torso", "chest", "胸", "main", "軀")
    if body is None:
        nonroot = [n for n in name if parent[n] is not None]
        body = next((n for n in nonroot
                     if any(k in n.lower() or k in n for k in BODY_KW)), None)
        if body is None:
            cand = [(descendants(n), n) for n in nonroot]
            body = max(cand)[1] if cand else name[0]
    head = next((c for c in children.get(body, [])
                 if any(k in c.lower() for k in ("head", "face", "eye"))), None)
    limbs = [n for n in name if not children[n] and depth(n) >= 2 and n != head][:4]
    return {"body": body, "head": head, "limbs": limbs}


def breathing_loop(skel, body=None, period=1.2, sy_amp=0.12, sx_amp=0.02,
                   head=None, head_rot=2.0, limbs=None, limb_rot=3.0, name="gen_idle_Loop"):
    """在 skel 上加一支待機呼吸 Loop。回傳 (新 skel, anim dict, roles)。"""
    sk = copy.deepcopy(skel)
    roles = auto_roles(sk, body)
    if body:
        roles["body"] = body
    if head is not None:
        roles["head"] = head or None
    if limbs is not None:
        roles["limbs"] = limbs
    half = round(period / 2, 4)
    bones = {}

    # body:scaleY 主導脈動(吸氣脹→吐氣回),sx 微反向(略),無縫
    bones[roles["body"]] = {
        "scale": _seg([
            {"time": 0.0, "x": 1.0, "y": 1.0},
            {"time": half, "x": 1.0 + sx_amp, "y": 1.0 + sy_amp},
            {"time": period, "x": 1.0, "y": 1.0},
        ])
    }
    # head:微擺(rotate 0→+amp→0)
    if roles.get("head"):
        bones[roles["head"]] = {"rotate": _seg([
            {"time": 0.0, "angle": 0.0},
            {"time": half, "angle": head_rot},
            {"time": period, "angle": 0.0},
        ])}
    # limbs:末梢微盪(rotate,左右交替方向讓畫面不同步)
    for i, lb in enumerate(roles.get("limbs", [])):
        s = 1.0 if i % 2 == 0 else -1.0
        bones[lb] = {"rotate": _seg([
            {"time": 0.0, "angle": 0.0},
            {"time": half, "angle": s * limb_rot},
            {"time": period, "angle": 0.0},
        ])}

    anim = {"bones": bones}
    sk.setdefault("animations", {})[name] = anim
    return sk, anim, roles


# ---------- 自驗 ----------
def verify(sk_with_anim, name, period, sy_amp, limit_rot=15.0):
    a = sk_with_anim["animations"][name]
    issues = []
    # 1) loop-close(bezier-aware,對每個 channel 每分量)
    max_gap = 0.0
    for bn, tl in a["bones"].items():
        for ch, frames in tl.items():
            keys = {"rotate": ("angle",), "translate": ("x", "y"),
                    "scale": ("x", "y")}.get(ch, ("x", "y"))
            dflt = (1.0, 1.0) if ch == "scale" else tuple(0.0 for _ in keys)
            v0 = _sample(frames, 0.0, keys, dflt)
            v1 = _sample(frames, period, keys, dflt)
            max_gap = max(max_gap, max(abs(a - b) for a, b in zip(v0, v1)))
    loop_closed = max_gap < 1e-6
    if not loop_closed:
        issues.append(f"loop not closed (max_gap={max_gap:.2e})")
    # 2) 幅度有界且非零
    dur = _anim_duration(a)
    N = 40
    moved = False
    over = False
    for bn, tl in a["bones"].items():
        for ch, frames in tl.items():
            keys = {"rotate": ("angle",), "translate": ("x", "y"),
                    "scale": ("x", "y")}.get(ch, ("x", "y"))
            dflt = (1.0, 1.0) if ch == "scale" else tuple(0.0 for _ in keys)
            arr = np.array([_sample(frames, t, keys, dflt)
                            for t in np.linspace(0, dur, N)])
            span = float((arr.max(0) - arr.min(0)).max())
            if span > 1e-4:
                moved = True
            if ch == "rotate" and span > limit_rot:
                over = True
    if not moved:
        issues.append("no motion generated")
    if over:
        issues.append("rotation amplitude exceeds sane breathing bound")
    # 3) 物理簽名
    inertia = ease_profile(sk_with_anim)["per_anim"].get(name, {}).get("inertia_index", 0.0)
    if inertia <= 0.0:
        issues.append(f"no inertia signature (inertia_index={inertia})")
    # 4) round-trip JSON
    try:
        rt = json.loads(json.dumps(sk_with_anim))
        rt_ok = name in rt["animations"] and abs(_anim_duration(rt["animations"][name]) - dur) < 1e-9
    except Exception as e:  # noqa: BLE001
        rt_ok = False; issues.append(f"round-trip failed: {e}")
    if not rt_ok and "round-trip failed" not in "".join(issues):
        issues.append("round-trip mismatch")
    return {
        "loop_closed": loop_closed, "loop_max_gap": round(max_gap, 9),
        "has_motion": moved, "rotation_in_bounds": not over,
        "duration": round(dur, 4), "inertia_index": inertia,
        "round_trip_ok": rt_ok,
        "passed": not issues, "issues": issues,
    }


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="storyboard beat → Spine 待機呼吸 Loop 生成器")
    ap.add_argument("skeleton", nargs="?", default="assets/main_draw.json")
    ap.add_argument("--body", default=None, help="指定軀幹骨(否則自動)")
    ap.add_argument("--period", type=float, default=1.2)
    ap.add_argument("--sy-amp", type=float, default=0.12)
    ap.add_argument("--save", default=None, help="把加了 Loop 的 skeleton 寫出到此路徑")
    a = ap.parse_args()
    src = json.load(open(a.skeleton))
    sk, anim, roles = breathing_loop(src, body=a.body, period=a.period, sy_amp=a.sy_amp)
    rep = verify(sk, "gen_idle_Loop", a.period, a.sy_amp)
    print("roles:", json.dumps(roles, ensure_ascii=False))
    print("verify:", json.dumps(rep, ensure_ascii=False, indent=2))
    if a.save and rep["passed"]:
        json.dump(sk, open(a.save, "w"), ensure_ascii=False)
        print("saved:", a.save)
    sys.exit(0 if rep["passed"] else 1)
