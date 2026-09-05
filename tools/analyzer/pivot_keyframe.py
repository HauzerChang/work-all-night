#!/usr/bin/env python3
"""candidate 0i — 關節 pivot 感知的 keyframe(S5 接觸縫 pivot → S1 動畫生成)。

問題:`gen_animations` 給結構子件(頭/手)加 `rotate` timeline 時,bone 位在**件中心** O,
      故件是**繞自己中心**旋轉(手臂原地打轉),而非繞**解剖關節** P(肩=與身體的接觸縫)。
      --rig 走「把 bone 搬到關節」的結構解;本檔提供**純 keyframe 補償**的另一條路:
      bone 仍留在件中心,靠**同步的 translate 補償**讓件繞任意 pivot P 旋轉。

數學(剛體繞 pivot):bone 的 rotate 讓件繞其原點 O 旋轉;要改繞 P,對每個 rotate 幀角度 θ
      加上補償位移 Δ(θ) = (R(θ) − I)(O − P)。
      證:件上與 P 重合的點局部座標 p = P − O。動畫後世界點
          world(p) = (O + translate) + R(θ)·(P − O)。
          令其 == P ⟺ translate = P − O − R(θ)(P−O) = (R(θ) − I)(O − P) = Δ(θ)。∎
      θ=0 ⟹ Δ=0 ⟹ **不擾動 setup identity**;loop 端點角度相等 ⟹ Δ 端點相等 ⟹ **無縫保留**。
      故本補償對既有介面契約(In 尾歸位、Loop 無縫、Out 首歸位)天然中性。

honest boundary:只有**有推得接觸縫 pivot 的結構子件**(頭/肢體)吃補償;rig 根(body,無父)
      與特效件(無關節語意)維持繞件中心 —— 與 S5 rig_layout 的 joint 判定一致。
      scale/徑向 translate 這類**非旋轉**運動仍會搬動 P(intro 縮放尤甚);pivot 不動點性質
      是對**旋轉分量**成立的,故驗收以「旋轉為主」的段落(loop 肢體純 rotate)量測。
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
import spine_anim as SA


def rotate_about_pivot_delta(O, P, theta_deg):
    """回傳把「繞 O 旋轉 θ」轉成「繞 P 旋轉 θ」所需的 bone translate 補償 Δ=(R(θ)−I)(O−P)。
    O,P 皆在 bone 的 parent-local 座標(扁平骨架下即世界座標,y 上)。"""
    th = math.radians(theta_deg)
    c, s = math.cos(th), math.sin(th)
    vx, vy = O[0] - P[0], O[1] - P[1]
    # R(θ)v − v
    dx = (c * vx - s * vy) - vx
    dy = (s * vx + c * vy) - vy
    return dx, dy


def _times_grid(rot_frames, tr_frames, subdiv):
    """rotate ∪ translate 幀時刻,並把每個相鄰區間細分 subdiv 段(讓 Δ 的非線性以線性內插逼近)。"""
    ts = sorted({round(f["time"], 6) for f in rot_frames} |
                {round(f["time"], 6) for f in (tr_frames or [])})
    if len(ts) < 2:
        return ts
    out = []
    for a, b in zip(ts[:-1], ts[1:]):
        for k in range(subdiv):
            out.append(a + (b - a) * k / subdiv)
    out.append(ts[-1])
    # 去重 + 排序(4 位小數對齊 spine_anim 產幀慣例)
    seen, uniq = set(), []
    for t in sorted(out):
        r = round(t, 4)
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return uniq


def compensate_bone(b, O, P, subdiv=8):
    """就地把單根 bone 的 timelines dict `b` 改成「繞 P 旋轉」。
    需要 b 有 "rotate";會**新建/合併** "translate"(既有 translate 之上疊加 Δ)。
    無 rotate ⟹ 原樣返回(不動點無意義)。回傳 b。"""
    rot = b.get("rotate")
    if not rot:
        return b
    tr = b.get("translate")  # 既有 translate(如 intro 徑向歸位),補償要疊加其上
    grid = _times_grid(rot, tr, subdiv)
    if len(grid) < 2:
        return b
    new_tr = []
    for t in grid:
        theta = SA._interp(rot, t, ["angle"])["angle"]
        base = SA._interp(tr, t, ["x", "y"]) if tr else {"x": 0.0, "y": 0.0}
        dx, dy = rotate_about_pivot_delta(O, P, theta)
        new_tr.append({"time": round(t, 4),
                       "x": round(base["x"] + dx, 4),
                       "y": round(base["y"] + dy, 4)})
    b["translate"] = new_tr
    return b


def compensate_animation(anim, origins, pivots, subdiv=8):
    """對一支 animation 的 bones 套 pivot 補償。
    origins/pivots: {bone_name: (x,y)}(bone_name 含 'b_' 前綴)。只補償同時在兩者出現的 bone。"""
    for bone, chans in anim.get("bones", {}).items():
        if bone in origins and bone in pivots:
            compensate_bone(chans, origins[bone], pivots[bone], subdiv=subdiv)
    return anim
