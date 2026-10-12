#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
curve_tools.py — Spine 3.8 timeline 曲線工具庫（v1.1 新增）
=============================================================
來源：實戰 session「idle loop 去僵硬」全套技法的可重用版本。
所有函式操作 Spine 3.8 JSON 的 frame list（dict 陣列），就地修改並回傳。

診斷→修復對照表：
  症狀「節拍器感/三角波」   → to_ease()          linear 轉 ease-in-out
  症狀「紙板感/全身同步」   → phase_shift()      環形相位平移（follower 滯後）
  症狀「走走停停/每key煞車」→ catmull_smooth()   穿透式切線（只在極值減速）
  症狀「末梢甩不開」        → amp_gain()         繞均值振幅增益
  症狀「末節完全沒動」      → derive_tip()       從父骨衍生 follow-through
  節奏調整                  → time_scale_anim()  全 timeline 等比縮放
  驗收                      → stiffness_metric() / loop_closure_report()

curve 格式（3.8 緊湊 bezier，散裝鍵not array）：
  {"curve": cx1, "c2": cy1, "c3": cx2, "c4": cy2}
  預設 c2=0, c3=1, c4=1；"curve":"stepped" 為階梯；無 curve 鍵 = linear。
  穿透式切線會產生 c2/c4 落在 [0,1] 之外 —— 這是刻意的，Spine runtime 支援
  （僅 cx 必須在 [0,1]），validator 對此只該 warn 不該 error。
"""
from __future__ import annotations
import copy

FPS = 30.0
EASE = {'curve': 0.25, 'c3': 0.75}          # ease-in-out
PROP_FIELDS = {'rotate': [('angle', 0.0)],
               'translate': [('x', 0.0), ('y', 0.0)],
               'shear': [('x', 0.0), ('y', 0.0)],
               'scale': [('x', 1.0), ('y', 1.0)]}

# ---------------------------------------------------------------- 取值

def bez_y(cx1, cy1, cx2, cy2, x):
    """cubic bezier((0,0),(cx1,cy1),(cx2,cy2),(1,1))：給 x 求 y（二分求參數）。"""
    lo, hi = 0.0, 1.0
    for _ in range(40):
        m = (lo + hi) / 2
        u = 1 - m
        bx = 3*u*u*m*cx1 + 3*u*m*m*cx2 + m**3
        if bx < x: lo = m
        else: hi = m
    s = (lo + hi) / 2
    u = 1 - s
    return 3*u*u*s*cy1 + 3*u*s*s*cy2 + s**3


def seg_percent(frame, x):
    """frame 的 outgoing 插值百分比。"""
    c = frame.get('curve')
    if c is None: return x
    if c == 'stepped': return 0.0
    return bez_y(float(c), float(frame.get('c2', 0)),
                 float(frame.get('c3', 1)), float(frame.get('c4', 1)), x)


def wrap_angle(a):
    while a > 180: a -= 360
    while a < -180: a += 360
    return a


def eval_timeline(frames, prop, t, dur):
    """在任意時間 t（環形）取 timeline 值 -> {field: value}。"""
    fields = PROP_FIELDS[prop]
    t = t % dur if dur > 0 else 0.0
    ts = [f.get('time', 0.0) for f in frames]
    if t <= ts[0]:  return {k: frames[0].get(k, d) for k, d in fields}
    if t >= ts[-1]: return {k: frames[-1].get(k, d) for k, d in fields}
    for i in range(len(frames) - 1):
        if ts[i] <= t <= ts[i+1]:
            x = 0.0 if ts[i+1] == ts[i] else (t - ts[i]) / (ts[i+1] - ts[i])
            p = seg_percent(frames[i], x)
            out = {}
            for k, dflt in fields:
                v0 = frames[i].get(k, dflt); v1 = frames[i+1].get(k, dflt)
                dv = v1 - v0
                if prop == 'rotate': dv = wrap_angle(dv)
                out[k] = v0 + dv * p
            return out
    return {k: frames[-1].get(k, d) for k, d in fields}

# ---------------------------------------------------------------- 修復

def to_ease(frames):
    """linear key -> ease-in-out；既有 bezier / stepped 保留。
    適用：擺動型（極值折返）timeline。若是連續掃過型改用 catmull_smooth。"""
    for f in frames[:-1]:
        if 'curve' not in f:
            f.update(EASE)
    return frames


def phase_shift(frames, prop, lag, dur):
    """環形時間平移：follower 延後 lag 秒到達同樣姿勢。閉環自動閉合。
    lag 建議值（30fps）：頭 2f、耳根/髮根 3f、末梢 5~7f、臂→手→指 1/3/5f。"""
    if lag <= 0 or len(frames) < 2 or dur <= 0:
        return frames
    core = frames[:-1]
    moved = []
    for f in core:
        nf = dict(f)
        nf['time'] = round((f.get('time', 0.0) + lag) % dur, 4)
        moved.append(nf)
    moved.sort(key=lambda f: f['time'])
    bv = eval_timeline(frames, prop, (0.0 - lag) % dur, dur)
    first = dict(EASE); first['time'] = 0.0
    first.update({k: round(v, 3) for k, v in bv.items()})
    # 最後一鍵「不可」帶 curve：Spine editor 匯入會 AIOOBE crash（地雷 #12）
    last = {'time': round(dur, 4)}
    last.update({k: round(v, 3) for k, v in bv.items()})
    out = [first] + [f for f in moved if 1e-4 < f['time'] < dur - 1e-4] + [last]
    dedup = [out[0]]
    for f in out[1:]:
        if f['time'] - dedup[-1]['time'] < (1.0 / FPS) * 0.5:
            continue
        dedup.append(f)
    if dedup[-1]['time'] < dur - 1e-4:
        dedup.append(last)
    return dedup


def catmull_smooth(frames, key='angle', dflt=0.0, dur=1.0,
                   cy_clamp=(-0.5, 1.5)):
    """穿透式切線：Catmull-Rom 過每個 key 的切線 -> Spine bezier。
    ease-in-out 在每個 key 速度歸零（走走停停）；本函式讓運動連續流過
    中間 key，只在真正極值自然減速。適用：空中連續揮動的手、掃視的頭。
    cy 會超出 [0,1]（過衝），屬刻意設計。"""
    n = len(frames)
    if n < 3: return frames
    ts = [f.get('time', 0.0) for f in frames]
    vs = [f.get(key, dflt) for f in frames]
    closed = abs(vs[0] - vs[-1]) < 0.05
    m = [0.0] * n
    for i in range(n):
        if i == 0:
            tp, vp = (ts[-2] - dur, vs[-2]) if closed else (ts[0], vs[0])
            tn, vn = ts[1], vs[1]
        elif i == n - 1:
            tp, vp = ts[-2], vs[-2]
            tn, vn = (ts[1] + dur, vs[1]) if closed else (ts[-1], vs[-1])
        else:
            tp, vp, tn, vn = ts[i-1], vs[i-1], ts[i+1], vs[i+1]
        if tn > tp: m[i] = (vn - vp) / (tn - tp)
    if closed:
        m[-1] = m[0]
    for i in range(n - 1):
        dt = ts[i+1] - ts[i]; dv = vs[i+1] - vs[i]
        f = frames[i]
        for k in ('curve', 'c2', 'c3', 'c4'):
            f.pop(k, None)
        if dt <= 0: continue
        if abs(dv) < 0.05:                      # 近水平段維持 ease，防除零過衝
            f.update(EASE); continue
        cy1 = (m[i] * dt / 3.0) / dv
        cy2 = 1.0 - (m[i+1] * dt / 3.0) / dv
        f['curve'] = round(1/3, 4)
        f['c2'] = round(max(cy_clamp[0], min(cy_clamp[1], cy1)), 4)
        f['c3'] = round(2/3, 4)
        f['c4'] = round(max(cy_clamp[0], min(cy_clamp[1], cy2)), 4)
    for k in ('curve', 'c2', 'c3', 'c4'):      # 末鍵不帶 curve（地雷 #12）
        frames[-1].pop(k, None)
    return frames


def strip_last_frame_curves(anim):
    """拔掉整支動畫所有 timeline 最後一鍵上的 curve 欄位。
    語義零影響（末鍵後沒有下一段），但不拔的話 Spine editor 匯入直接
    AIOOBE crash：curves 陣列大小 (key數-1)*19，末鍵 curve 寫進 index
    (key數-1)*19 越界。Cocos/spine runtime 讀檔會跳過末鍵 curve，所以
    遊戲正常、編輯器炸 —— 兩邊行為不一致，回美術前必跑。
    任何 patch 腳本 json.dump 前呼叫一次最保險。"""
    n = 0
    for sec in ('bones', 'slots'):
        for tls in anim.get(sec, {}).values():
            for fr in tls.values():
                if isinstance(fr, list) and fr and isinstance(fr[-1], dict):
                    for k in ('curve', 'c2', 'c3', 'c4'):
                        if fr[-1].pop(k, None) is not None:
                            n += 1
    return n


def amp_gain(frames, prop, g):
    """繞均值放大振幅（中心姿勢不變）。末梢 follow-through 建議 1.10~1.15。"""
    for k, dflt in PROP_FIELDS[prop]:
        vals = [f.get(k, dflt) for f in frames]
        mean = sum(vals) / len(vals)
        for f in frames:
            f[k] = round(mean + (f.get(k, dflt) - mean) * g, 3)
    return frames


def derive_tip(parent_frames, dur, gain=0.7, lag_frames=5, fps=FPS):
    """從父骨 rotate timeline 衍生末節 follow-through（繞 setup 0 擺動）。
    用於 idle 裡完全沒 key 的指尖/髮尾等。回傳新的 frame list。"""
    vals = [f.get('angle', 0.0) for f in parent_frames]
    mean = sum(vals) / len(vals)
    lag = lag_frames / fps
    moved = sorted(
        ({'time': (f.get('time', 0.0) + lag) % dur,
          'angle': (f.get('angle', 0.0) - mean) * gain} for f in parent_frames[:-1]),
        key=lambda f: f['time'])
    edge = (moved[0]['angle'] + moved[-1]['angle']) / 2
    out = [dict(EASE, time=0.0, angle=round(edge, 3))]
    for f in moved:
        if (1.0/fps)*0.5 < f['time'] < dur - (1.0/fps)*0.5:
            out.append(dict(EASE, time=round(f['time'], 4), angle=round(f['angle'], 3)))
    out.append({'time': round(dur, 4), 'angle': round(edge, 3)})   # 末鍵不帶 curve（地雷 #12）
    return out


def time_scale_anim(anim, s):
    """整支動畫等比變速（回傳深拷貝）。呼吸型 idle 建議 1.6~2.0s / loop。"""
    a = copy.deepcopy(anim)
    def walk(o):
        if isinstance(o, list):
            for x in o: walk(x)
        elif isinstance(o, dict):
            if 'time' in o and isinstance(o['time'], (int, float)):
                o['time'] = round(o['time'] * s, 4)
            for v in o.values(): walk(v)
    walk(a)
    return a

# ---------------------------------------------------------------- 驗收

def stiffness_metric(anim, dur, fps=FPS):
    """key 處速度不連續量的平均（deg|px / s）。linear 三角波高、平滑後低。
    修復前後各跑一次，量化改善幅度。"""
    tot, n = 0.0, 0
    for bn, tls in anim.get('bones', {}).items():
        for prop, frames in tls.items():
            if prop not in PROP_FIELDS or len(frames) < 3:
                continue
            eps = 1.0 / fps / 4
            for f in frames[1:-1]:
                t = f.get('time', 0.0)
                a = eval_timeline(frames, prop, t - eps, dur)
                b = eval_timeline(frames, prop, t + eps, dur)
                c = eval_timeline(frames, prop, t, dur)
                for k, _ in PROP_FIELDS[prop]:
                    tot += abs((b[k]-c[k])/eps - (c[k]-a[k])/eps)
                    n += 1
    return tot / max(n, 1)


def loop_closure_report(anim, dur, tol=0.01):
    """檢查每條 timeline 首尾值閉合 + key 時間單調 + 首鍵在 0 / 末鍵在 dur。
    回傳問題清單（空 = 通過）。"""
    bad = []
    for bn, tls in anim.get('bones', {}).items():
        for prop, fr in tls.items():
            if prop not in PROP_FIELDS or len(fr) < 2:
                continue
            ts = [f.get('time', 0.0) for f in fr]
            if ts != sorted(ts):
                bad.append(f'{bn}.{prop}: key times not sorted')
            if abs(ts[0]) > 1e-4:
                bad.append(f'{bn}.{prop}: first key at {ts[0]}, not 0')
            if abs(ts[-1] - dur) > 1e-3:
                bad.append(f'{bn}.{prop}: last key at {ts[-1]}, dur is {dur}')
            for k, dflt in PROP_FIELDS[prop]:
                v0, v1 = fr[0].get(k, dflt), fr[-1].get(k, dflt)
                if abs(v0 - v1) > tol:
                    bad.append(f'{bn}.{prop}.{k}: open loop {v0} != {v1}')
    return bad


def anim_duration(anim):
    """掃全 timeline 取最大 time 當時長。"""
    dur = 0.0
    def walk(o):
        nonlocal dur
        if isinstance(o, list):
            for x in o: walk(x)
        elif isinstance(o, dict):
            t = o.get('time')
            if isinstance(t, (int, float)) and t > dur: dur = t
            for v in o.values(): walk(v)
    walk(anim)
    return dur
