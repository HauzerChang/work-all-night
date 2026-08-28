#!/usr/bin/env python3
"""Spine 3.8 animation timeline **sampler**（純 Python,無瀏覽器/無 spine-webgl)。

用途:把 gen_animations.py 產出的 `animations` timeline 在任意時間 t 取樣,回傳每根 bone
的動畫通道值(rotate 角度 / translate 位移 / scale 倍率)與每個 slot 的 color alpha。
這是 candidate 0d(分鏡→動畫 keyframe)的**自我驗證基石** — 用它量化運動幅度、
Loop 無縫性、In/Out 邊界,不靠肉眼、不需 CDN。

支援 3.8 keyframe 曲線:
  - 預設 linear(無 "curve" 鍵)
  - "curve":"stepped"
  - 緊湊 bezier 散鍵 {"curve":cx1,"c2":cy1,"c3":cx2,"c4":cy2}(CLAUDE.md 雷點 #7)

座標/單位約定與 Spine runtime 一致:
  rotate = 相對 setup 的角度增量(度);translate = 相對 setup local 的位移(px);
  scale  = 乘在 setup scale 上的倍率(setup=1);color = 8-hex RGBA,取 alpha=最後兩碼/255。
扁平骨架(全部 parent=root、root 為單位變換)下,這些 local 通道值即為有意義的物理量。
"""
import math


# ---------- 緊湊 bezier 求值(Spine BezierCurve) ----------
def _bezier_y(cx1, cy1, cx2, cy2, p):
    """給時間佔比 p∈[0,1](此幀→下一幀),解三次 Bezier 得值佔比 y∈[0,1]。
    控制點為相對 (0,0)→(1,1) 的正規化座標。以 Newton + bisection 解 x(t)=p。"""
    if p <= 0:
        return 0.0
    if p >= 1:
        return 1.0

    def bez(t, c1, c2):
        mt = 1 - t
        return 3 * mt * mt * t * c1 + 3 * mt * t * t * c2 + t * t * t

    lo, hi, t = 0.0, 1.0, p
    for _ in range(30):
        x = bez(t, cx1, cx2)
        if abs(x - p) < 1e-7:
            break
        if x < p:
            lo = t
        else:
            hi = t
        t = 0.5 * (lo + hi)
    return bez(t, cy1, cy2)


def _interp(frames, t, keys):
    """在 keyframe 陣列 frames 上取樣 t;keys=要內插的欄位名(如 ["angle"] 或 ["x","y"])。
    回傳 dict{key:value}。frames 每筆:{"time":.., key:.., "curve":..(可選)}。"""
    n = len(frames)
    if n == 0:
        return {k: 0.0 for k in keys}
    if t <= frames[0]["time"]:
        return {k: float(frames[0].get(k, 0.0)) for k in keys}
    if t >= frames[-1]["time"]:
        return {k: float(frames[-1].get(k, 0.0)) for k in keys}
    # 找區間 [i, i+1]
    i = 0
    while i + 1 < n and frames[i + 1]["time"] <= t:
        i += 1
    f0, f1 = frames[i], frames[i + 1]
    t0, t1 = f0["time"], f1["time"]
    span = t1 - t0
    p = 0.0 if span <= 0 else (t - t0) / span
    curve = f0.get("curve", None)
    if curve == "stepped":
        alpha = 0.0
    elif isinstance(curve, (int, float)):
        # 緊湊 bezier: curve=cx1, c2=cy1, c3=cx2, c4=cy2
        alpha = _bezier_y(f0["curve"], f0["c2"], f0["c3"], f0["c4"], p)
    else:
        alpha = p  # linear
    out = {}
    for k in keys:
        v0 = float(f0.get(k, 0.0))
        v1 = float(f1.get(k, 0.0))
        out[k] = v0 + (v1 - v0) * alpha
    return out


def _alpha_of(hexstr):
    """8-hex RGBA → alpha 0..1(最後兩碼)。"""
    hs = hexstr.strip()
    if len(hs) >= 8:
        return int(hs[6:8], 16) / 255.0
    return 1.0


def sample(anim, time, bones=None, slots=None):
    """在時間 time 取樣一支 animation。
    回傳 {"bones":{bone:{rotate,x,y,scaleX,scaleY}}, "slots":{slot:{alpha}}}。
    未在該 timeline 出現的通道 → setup 預設(rotate/x/y=0, scale=1, alpha=1)。"""
    res_b, res_s = {}, {}
    bts = anim.get("bones", {})
    for bone, chans in bts.items():
        d = {"rotate": 0.0, "x": 0.0, "y": 0.0, "scaleX": 1.0, "scaleY": 1.0}
        if "rotate" in chans:
            d["rotate"] = _interp(chans["rotate"], time, ["angle"])["angle"]
        if "translate" in chans:
            xy = _interp(chans["translate"], time, ["x", "y"])
            d["x"], d["y"] = xy["x"], xy["y"]
        if "scale" in chans:
            sc = _interp(chans["scale"], time, ["x", "y"])
            d["scaleX"], d["scaleY"] = sc["x"], sc["y"]
        res_b[bone] = d
    sts = anim.get("slots", {})
    for slot, chans in sts.items():
        a = 1.0
        if "color" in chans:
            fr = chans["color"]
            # color 幀值在 "color" 欄(8-hex);以 alpha 佔比線性內插
            n = len(fr)
            if n:
                if time <= fr[0]["time"]:
                    a = _alpha_of(fr[0]["color"])
                elif time >= fr[-1]["time"]:
                    a = _alpha_of(fr[-1]["color"])
                else:
                    i = 0
                    while i + 1 < n and fr[i + 1]["time"] <= time:
                        i += 1
                    t0, t1 = fr[i]["time"], fr[i + 1]["time"]
                    span = t1 - t0
                    p = 0.0 if span <= 0 else (time - t0) / span
                    cv = fr[i].get("curve", None)
                    if cv == "stepped":
                        p = 0.0
                    elif isinstance(cv, (int, float)):
                        p = _bezier_y(fr[i]["curve"], fr[i]["c2"], fr[i]["c3"], fr[i]["c4"], p)
                    a0, a1 = _alpha_of(fr[i]["color"]), _alpha_of(fr[i + 1]["color"])
                    a = a0 + (a1 - a0) * p
        res_s[slot] = {"alpha": a}
    return {"bones": res_b, "slots": res_s}


def duration(anim):
    """animation 最長 timeline 時間。"""
    d = 0.0
    for chans in anim.get("bones", {}).values():
        for tl in chans.values():
            if tl:
                d = max(d, tl[-1]["time"])
    for chans in anim.get("slots", {}).values():
        for tl in chans.values():
            if tl:
                d = max(d, tl[-1]["time"])
    return d


def all_finite(anim):
    """所有 keyframe 時間與數值是否皆有限(AC1)。"""
    def ok(v):
        return isinstance(v, (int, float)) and math.isfinite(v)
    for chans in anim.get("bones", {}).values():
        for key, tl in chans.items():
            last_t = -1e18
            for f in tl:
                if not ok(f.get("time", 0)):
                    return False
                if f["time"] <= last_t:      # 時間須嚴格遞增
                    return False
                last_t = f["time"]
                for k, v in f.items():
                    if k in ("time",):
                        continue
                    if k in ("curve", "c2", "c3", "c4"):
                        if k == "curve" and v == "stepped":
                            continue
                        if not ok(v):
                            return False
                    elif not ok(v):
                        return False
    return True
