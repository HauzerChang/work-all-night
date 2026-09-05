#!/usr/bin/env python3
"""candidate 0i(S1 (e)) — 關節 pivot 接 keyframe:讓件**繞關節轉而非繞件中心**。

問題:非 rig 的 build_spine 把每件 bone 放在**件中心**(parent=root),故 gen_animations 的
      limb `rotate` 是「繞件中心旋轉」——手臂會像唱盤一樣自轉,而非以肩關節為軸擺盪。
      S5 已能推斷關節 pivot(接觸縫,`infer_pivots`);本模組把 pivot 餵回 keyframe,
      用一個**補償平移**讓件(bone 仍在件中心)在視覺上繞關節 P 轉。

數學(扁平骨架:parent=root、root 單位變換、bone setup rotation=0、rotate 通道 scale=1):
  bone 原點 O(件中心世界座標),關節 pivot P(世界座標)。
  對某幀旋轉角 θ,補償平移
        Δ(θ) = (R(θ) − I)(O − P)
  則綁在該 bone 的任一點 v 的動畫世界座標
        v' = O + Δ(θ) + R(θ)(v − O)
  代入 v = P:
        P' = O + (R(θ)−I)(O−P) + R(θ)(P−O)
           = O + R(θ)(O−P) − (O−P) + R(θ)(P−O)
           = O − (O−P) = P                       ← P 為**不動點**(關節)。
  負對照:不補償(Δ=0)時 P' = O + R(θ)(P−O) = P + (I−R(θ))(O−P),
          位移量 = 2·sin(θ/2)·|O−P| ≠ 0 → 件繞中心轉會拖走關節。

R 約定(CCW 正,與 Spine runtime 一致 → 產出的 timeline 在真引擎也正確):
  R(θ) = [[c,−s],[s,c]],c=cos θ, s=sin θ。generator 與 validator 皆用本檔 `rot_apply`
  作為 R 的**單一真相來源**,故不動點性質與 CW/CCW 無關(只要一致)。

輸出格式:把原 `rotate` 通道與(可選)既有 `translate` 通道**共同密取樣**到同一均勻時間格
  (線性段),每個格點上 (rotate, translate) 皆自洽 → 格點上 P 精確不動;格點間殘差 O(step²),
  以 `samples` 控制到可忽略。首尾角度沿用原通道端點(多為 identity)→ 補償 Δ 在 θ=0 時為 0,
  故 setup/介面不被擾動、可無縫串接。
"""
import math, os, sys

sys.path.insert(0, os.path.dirname(__file__))
import spine_anim  # noqa: E402  (共用 keyframe 內插:含緊湊 bezier / stepped / linear)


def rot_apply(deg, vx, vy):
    """R(θ)·(vx,vy),θ 為度,CCW 正(Spine 一致)。generator/validator 的 R 單一真相來源。"""
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return c * vx - s * vy, s * vx + c * vy


def pivot_translate(theta_deg, oxp, oyp):
    """補償平移 Δ = (R(θ) − I)(O − P);(oxp,oyp)=(O−P)。回傳 (Δx, Δy)。"""
    rx, ry = rot_apply(theta_deg, oxp, oyp)
    return rx - oxp, ry - oyp


def articulate_about_pivot(rotate_frames, O, P, base_translate=None, samples=24):
    """把「繞 bone 原點 O 旋轉」的 rotate 通道,改成「繞關節 P 旋轉」。

    rotate_frames: [{"time","angle",...}] 既有 rotate 通道(任意 curve)。
    O=(ox,oy) bone 世界原點(件中心);P=(px,py) 關節 pivot 世界座標。
    base_translate: 既有 translate 通道(如 gen_in 的徑向歸位),補償量會**疊加**其上保留。
    samples: 共同時間格點數(格點上精確不動;越大格點間殘差越小)。

    回傳 (new_rotate_frames, new_translate_frames):密取樣、線性、共用時間。
    """
    if not rotate_frames:
        return rotate_frames, base_translate
    t0 = rotate_frames[0]["time"]
    tN = rotate_frames[-1]["time"]
    oxp = float(O[0]) - float(P[0])
    oyp = float(O[1]) - float(P[1])
    rout, tout = [], []
    n = max(1, int(samples))
    for i in range(n + 1):
        t = t0 + (tN - t0) * i / n
        th = spine_anim._interp(rotate_frames, t, ["angle"])["angle"]
        dxp, dyp = pivot_translate(th, oxp, oyp)
        bx = by = 0.0
        if base_translate:
            xy = spine_anim._interp(base_translate, t, ["x", "y"])
            bx, by = xy["x"], xy["y"]
        rout.append({"time": round(t, 4), "angle": round(th, 3)})
        tout.append({"time": round(t, 4), "x": round(bx + dxp, 3), "y": round(by + dyp, 3)})
    return rout, tout


def world_point(O, sampled_bone, v):
    """扁平骨架下,綁在 bone(原點 O)的點 v 在某取樣狀態下的世界座標。
    sampled_bone = spine_anim.sample()[bone] = {rotate,x,y,scaleX,scaleY}。
    world = (O + (dx,dy)) + R(rotate)·diag(sX,sY)·(v − O)。與 generator 用同一 rot_apply。"""
    ox, oy = float(O[0]), float(O[1])
    dx = sampled_bone.get("x", 0.0)
    dy = sampled_bone.get("y", 0.0)
    rot = sampled_bone.get("rotate", 0.0)
    sx = sampled_bone.get("scaleX", 1.0)
    sy = sampled_bone.get("scaleY", 1.0)
    lx = (float(v[0]) - ox) * sx
    ly = (float(v[1]) - oy) * sy
    rx, ry = rot_apply(rot, lx, ly)
    return (ox + dx + rx, oy + dy + ry)
