#!/usr/bin/env python3
"""motion spec(軌跡編輯結果)的資料模型與 keyframe 組裝。

spec 由 `spine_trajectory_editor.html` 匯出,描述「目標骨骼的**自身位移**該長什麼樣」:
世界座標的關鍵值 + 三個旋鈕(延後 lag 幀、幅度 scale、各軸幅度)。
本模組負責把它變成 Spine 3.8 timeline keys:

  1. 套旋鈕:frame += lag;value' = mean + (value − mean) × scale(以震盪中心縮放,靜止偏移不變)
  2. 迴圈邊界:延後後跨過總長的那一段,用 de Casteljau 在邊界切兩段,
     t=0 與 t=總長 放同一個內插值,曲線參數各自正規化 → **總長不變、loop 無縫**
  3. 世界位移 → 目標骨骼父體空間的 local translate(用該時刻父體世界矩陣的反矩陣)

de Casteljau 切分的作法沿用 spine-motion-skill `scripts/retime.py`。
"""
SCHEMA = "spine-motion-spec/1"
LINEAR = None


# ---------- bezier 切分 ----------
def _bez_pt(t, p0, p1, p2, p3):
    return tuple((1 - t) ** 3 * a + 3 * (1 - t) ** 2 * t * b + 3 * (1 - t) * t * t * c + t ** 3 * d
                 for a, b, c, d in zip(p0, p1, p2, p3))


def split_curve(cx1, cy1, cx2, cy2, u0):
    """把正規化 cubic bezier 在 x=u0 切成兩段 → (left, right, w0);left/right 為 Spine 緊湊 curve dict。"""
    p0, p1, p2, p3 = (0, 0), (cx1, cy1), (cx2, cy2), (1, 1)
    lo, hi = 0.0, 1.0
    for _ in range(60):
        t = (lo + hi) / 2
        if _bez_pt(t, p0, p1, p2, p3)[0] < u0:
            lo = t
        else:
            hi = t
    t = (lo + hi) / 2
    q1 = tuple(a + (b - a) * t for a, b in zip(p0, p1))
    q2 = tuple(a + (b - a) * t for a, b in zip(p1, p2))
    q3 = tuple(a + (b - a) * t for a, b in zip(p2, p3))
    r1 = tuple(a + (b - a) * t for a, b in zip(q1, q2))
    r2 = tuple(a + (b - a) * t for a, b in zip(q2, q3))
    mx, my = tuple(a + (b - a) * t for a, b in zip(r1, r2))
    if mx <= 1e-9 or my <= 1e-9 or (1 - mx) <= 1e-9 or (1 - my) <= 1e-9:
        return (None, None, my)          # 退化 → 兩段都用線性
    L = dict(curve=q1[0] / mx, c2=q1[1] / my, c3=r1[0] / mx, c4=r1[1] / my)
    R = dict(curve=(r2[0] - mx) / (1 - mx), c2=(r2[1] - my) / (1 - my),
             c3=(q3[0] - mx) / (1 - mx), c4=(q3[1] - my) / (1 - my))
    return (L, R, my)


def curve_value_at(curve, u):
    """給段內時間佔比 u,回傳值佔比 w(linear / stepped / 緊湊 bezier)。"""
    if curve is None:
        return u
    if curve == "stepped":
        return 0.0
    cx1, cy1 = curve.get("curve", 0.0), curve.get("c2", 0.0)
    cx2, cy2 = curve.get("c3", 1.0), curve.get("c4", 1.0)
    lo, hi = 0.0, 1.0
    for _ in range(40):
        t = (lo + hi) / 2
        x = 3 * (1 - t) ** 2 * t * cx1 + 3 * (1 - t) * t * t * cx2 + t ** 3
        if x < u:
            lo = t
        else:
            hi = t
    t = (lo + hi) / 2
    return 3 * (1 - t) ** 2 * t * cy1 + 3 * (1 - t) * t * t * cy2 + t ** 3


def norm_curve(c):
    """spec 的 curve 欄位 → (dict|'stepped'|None)。"""
    if c in (None, "linear", ""):
        return None
    if c == "stepped":
        return "stepped"
    if isinstance(c, dict):
        return {"curve": float(c.get("curve", 0.0)), "c2": float(c.get("c2", 0.0)),
                "c3": float(c.get("c3", 1.0)), "c4": float(c.get("c4", 1.0))}
    if isinstance(c, (list, tuple)) and len(c) == 4:
        return {"curve": float(c[0]), "c2": float(c[1]), "c3": float(c[2]), "c4": float(c[3])}
    raise ValueError(f"無法解析的 curve: {c!r}")


# ---------- 旋鈕 ----------
def strip_loop_duplicate(keys, nf, fields, tol=1e-6):
    """loop timeline 慣例:frame=總長 的那個 key 是 frame=0 的循環複製。
    延後(lag)前要先拿掉它,否則兩者取模後撞在同一幀,dedup 會保留錯的曲線。"""
    if len(keys) < 2:
        return list(keys)
    first, last = keys[0], keys[-1]
    if abs(float(first["frame"])) < tol and abs(float(last["frame"]) - nf) < tol \
            and all(abs(float(first.get(f, 0.0)) - float(last.get(f, 0.0))) < 1e-4 for f in fields):
        return list(keys[:-1])
    return list(keys)


def apply_knobs(keys, fields, lag=0.0, scale=1.0, per_axis=None, nf=None):
    """套用延後與幅度縮放。回傳新 key list(frame 可能 ≥ 總長,之後由 wrap 處理)。
    給 nf 時會先拿掉 loop 尾端的重複 key(見 strip_loop_duplicate)。"""
    per_axis = per_axis or {}
    if nf and lag:
        keys = strip_loop_duplicate(keys, nf, fields)
    means = {}
    for f in fields:
        vals = [float(k.get(f, 0.0)) for k in keys]
        means[f] = (max(vals) + min(vals)) / 2 if vals else 0.0   # 震盪中心
    out = []
    for k in keys:
        nk = {"frame": float(k["frame"]) + lag, "curve": norm_curve(k.get("curve"))}
        for f in fields:
            s = scale * float(per_axis.get(f, 1.0))
            v = float(k.get(f, 0.0))
            nk[f] = means[f] + (v - means[f]) * s
        out.append(nk)
    return out


# ---------- 迴圈邊界 ----------
def wrap_cycle(keys, nf, fields, loop=True):
    """把(可能因延後而跨過總長的)關鍵值整理成 [0, nf] 內、首尾同值的 timeline。

    keys: [{frame, <fields>, curve}](frame 單位=幀)。回傳同格式,含 frame=0 與 frame=nf 兩端。
    - 有 key 正好落在 0 → 直接補一個 frame=nf 的循環複製(不需切曲線)。
    - 沒有 → 跨邊界那一段用 de Casteljau 在 x=nf 切兩段,兩端放同一個內插值,
      曲線參數各自正規化。**總長不變、loop 無縫**(spine-motion-skill 第 5 步)。
    loop=False 時只夾取排序,不做邊界處理。
    """
    ks = sorted(({**k, "frame": float(k["frame"])} for k in keys), key=lambda k: k["frame"])
    if not ks:
        return []
    if not loop:
        return [k for k in ks if -1e-9 <= k["frame"] <= nf + 1e-9]

    ks = strip_loop_duplicate(ks, nf, fields)
    ks = sorted(({**k, "frame": float(k["frame"]) % nf} for k in ks), key=lambda k: k["frame"])
    dedup = {}
    for k in ks:
        dedup.setdefault(round(k["frame"], 6), k)     # 同幀保留先出現的(較可能帶正確曲線)
    ks = [dedup[f] for f in sorted(dedup)]

    if abs(ks[0]["frame"]) < 1e-9:                    # 已有 frame=0 的 key → 補尾
        return ks + [{**ks[0], "frame": float(nf), "curve": None}]

    last, first = ks[-1], ks[0]
    fl, ff = last["frame"], first["frame"]
    seg = (ff + nf) - fl
    if seg <= 1e-9:
        return ks + [{**ks[0], "frame": float(nf), "curve": None}]
    u0 = (nf - fl) / seg
    c = last.get("curve")
    if isinstance(c, dict):
        L, R, w0 = split_curve(*_curve_params(c), u0)
    else:                                             # linear / stepped 切開後仍是自己
        L = R = c
        w0 = curve_value_at(c, u0)
    boundary = {f: float(last.get(f, 0.0)) + (float(first.get(f, 0.0)) - float(last.get(f, 0.0))) * w0
                for f in fields}
    mid = [dict(k) for k in ks]
    mid[-1] = {**mid[-1], "curve": L}
    head = {**boundary, "frame": 0.0, "curve": R}
    tail = {**boundary, "frame": float(nf), "curve": None}
    return [head] + mid + [tail]


def _curve_params(c):
    if isinstance(c, dict):
        return (c.get("curve", 0.0), c.get("c2", 0.0), c.get("c3", 1.0), c.get("c4", 1.0))
    return (0.0, 0.0, 1.0, 1.0)


# ---------- 組成 Spine timeline ----------
def to_spine_keys(keys, fps, fields, defaults=None, ndigits=4):
    """[{frame, <fields>, curve}] → Spine 3.8 timeline(第一幀省略 time,最後一幀不帶 curve)。"""
    defaults = defaults or {}
    out = []
    for i, k in enumerate(keys):
        t = round(float(k["frame"]) / fps, 5)
        e = {}
        if t > 0:
            e["time"] = t
        for f in fields:
            v = round(float(k.get(f, defaults.get(f, 0.0))), ndigits)
            if v != defaults.get(f, 0.0) or True:      # 明確寫出,避免與 setup 缺省混淆
                e[f] = v
        c = k.get("curve")
        if i < len(keys) - 1 and c is not None:
            if c == "stepped":
                e["curve"] = "stepped"
            else:
                e["curve"] = round(float(c.get("curve", 0.0)), 5)
                e["c2"] = round(float(c.get("c2", 0.0)), 5)
                e["c3"] = round(float(c.get("c3", 1.0)), 5)
                e["c4"] = round(float(c.get("c4", 1.0)), 5)
        out.append(e)
    return out


def sample_keys(keys, fields, frame, nf, loop=True):
    """在已 wrap 好的 key 列上取樣(給預測/驗證用),frame 單位=幀。"""
    if not keys:
        return {f: 0.0 for f in fields}
    ks = sorted(keys, key=lambda k: float(k["frame"]))
    fr = frame % nf if loop else max(0.0, min(frame, nf))
    if fr <= ks[0]["frame"]:
        return {f: float(ks[0].get(f, 0.0)) for f in fields}
    if fr >= ks[-1]["frame"]:
        return {f: float(ks[-1].get(f, 0.0)) for f in fields}
    for i in range(len(ks) - 1):
        a, b = ks[i], ks[i + 1]
        if a["frame"] <= fr <= b["frame"]:
            span = b["frame"] - a["frame"]
            u = 0.0 if span <= 0 else (fr - a["frame"]) / span
            w = curve_value_at(a.get("curve"), u)
            return {f: float(a.get(f, 0.0)) + (float(b.get(f, 0.0)) - float(a.get(f, 0.0))) * w for f in fields}
    return {f: float(ks[-1].get(f, 0.0)) for f in fields}
