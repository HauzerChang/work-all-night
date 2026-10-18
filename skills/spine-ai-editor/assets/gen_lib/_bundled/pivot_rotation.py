#!/usr/bin/env python3
"""candidate 0i(S1 e)— 關節 pivot 接進 keyframe 生成:讓件**繞關節 pivot 轉**而非件中心。

背景(把 S5 的接觸縫 pivot 餵進 S1 keyframe 生成器):
  `gen_animations` 產出的 `rotate` timeline 是「bone 繞自身原點旋轉」。非 `--rig` 組裝時,
  bone 原點落在**件中心 O**,故 limb/head 的 `rotate` 會讓件繞**件中心**轉 —— 對肢體不物理
  (手臂該繞肩、頭該繞頸)。`--rig` 的解法是把 bone 搬到關節(結構性改骨架);本模組提供**互補的
  keyframe 級解法**:bone 留在件中心,額外加一條補償 `translate`,使淨效果=件**繞關節 pivot P** 轉,
  **完全不動骨架結構**。

數學(剛體「繞任意點旋轉」分解,確定性、無 ML):
  設 bone setup 原點在 O(parent 座標)、旋轉角 θ。要讓貼在該 bone 的幾何繞 pivot P(同 parent 座標)
  旋轉 θ,只需在原 `rotate θ` 外加平移
      Δ(θ) = (R(θ) − I)(O − P)
  其中 R(θ) 為 2D 旋轉矩陣。驗證:pivot 的附著局部點 ℓ_P = P−O,套用後世界座標
      (O + Δ) + R(θ)·ℓ_P = O + (R−I)(O−P) + R(P−O) = O + (P−O) = P   ∀θ  → P 為**不動點**。
  θ=0 時 Δ=0 → **setup / loop 端點 / In-Out 介面全保持 identity**(candidate 0d 無縫性不被破壞)。

實作要點:
  - Δ(θ) 對 θ **非線性**。若只在原 rotate keyframe 放 Δ,兩幀之間 translate 線性內插 ≠ 真值,
    P 在**幀間**會有殘差。故把 rotate 通道**加密重取樣**成均勻密網格(dt 秒),rotate/translate 同格線性,
    幀間殘差 ~ (1/8)|O−P|·(dθ_rad)² → dt=1/30 下 << 0.1px(validate 實測)。
  - 已存在的 translate(如 In 的徑向歸位)會被**疊加**(先在密網格上重取樣再加 Δ),兩種位移語意共存。

用法:`apply_pivots(anim, bone_origin, pivot_of, dt)` 就地把有 pivot + rotate 的 bone 轉成繞 pivot 版。

── candidate 0i 延伸(G-3):件繞關節 pivot **縮放**(scale-about-pivot)──
  0i 只補償 `rotate`(讓件繞 pivot 轉)。但 In/Out/pulse 等節拍會給件 `scale`(In 由 0.02→1 長大、
  Out 收 →0、pulse 峰 1.08)—— 非 rig 下 bone 落**件中心 O**,故件會繞**件中心**縮放(手臂該從肩伸長,
  不是從自身中心脹縮)。把「繞任意點旋轉」的推導**推廣到含 scale 的仿射**:
      設 bone 世界(parent 座標)變換 = translate T + M·local,其中 **M = R(θ)·diag(sx,sy)**(Spine TRS 序)。
      要讓 pivot 的附著局部點 ℓ_P = P−O 世界座標固定在 P(對任意 θ, s):
          T = P − O − M·(P−O)  ⟹  **Δ = (M − I)(O − P)**。
  θ=0 且 sx=sy=1 時 M=I → Δ=0(identity 介面/無縫保持);純旋轉(S=I)時 Δ=(R−I)(O−P) 退化回 0i。
  純均勻 scale s 約 pivot 為**相似變換**:∀x |world(x)−P| = s·|x−P|(scale-about-pivot 的等距類比,
  取代 0i 的「剛性等距」)。Δ 對 θ、s 皆非線性 → 同樣需密網格重取樣(dt)才不幀間漏。
  `apply_pivots(..., include_scale=True)` 啟用此模式:凡有 pivot 且有 rotate 或 scale 的 bone 皆按 M=R·S 補償。
"""
import math
import spine_anim  # 同目錄:_interp 用來在密網格上重取樣既有通道


def rot_matrix(deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return (c, -s, s, c)  # (m00, m01, m10, m11)


def transform_matrix(deg, sx, sy):
    """M = R(θ)·diag(sx,sy)(Spine TRS:先 scale 再 rotate)。回傳 (m00,m01,m10,m11)。"""
    m00, m01, m10, m11 = rot_matrix(deg)
    return (m00 * sx, m01 * sy, m10 * sx, m11 * sy)


def transform_matrix_full(deg, sx, sy, shx=0.0, shy=0.0):
    """候選 G-4:含 **shear** 的真實 Spine 3.8 bone local 2×2(TransformMode.Normal)。

    Spine `Bone.updateWorldTransform` 的 local basis(度數):
        a = cos(rot + shearX)·sx    b = cos(rot + 90 + shearY)·sy
        c = sin(rot + shearX)·sx    d = sin(rot + 90 + shearY)·sy
    回傳 (m00,m01,m10,m11)=(a,b,c,d)。**shx=shy=0 時逐位元退化回 `transform_matrix`**
    (cos(rot+90)=−sin rot、sin(rot+90)=cos rot),故對 0i/G-3 純 scale/rotate 路徑無回歸。
    此矩陣為**一般仿射**(非均勻 scale sx≠sy 或 shear≠0 → 非相似變換),但 Δ 公式仍成立。
    """
    rx = math.radians(deg + shx)
    ry = math.radians(deg + 90.0 + shy)
    a = math.cos(rx) * sx
    c = math.sin(rx) * sx
    b = math.cos(ry) * sy
    d = math.sin(ry) * sy
    return (a, b, c, d)


def pivot_delta_affine(m, O, P):
    """Δ = (M − I)(O − P),M=(m00,m01,m10,m11) 為**任意** 2×2 仿射線性部。回傳 (dx,dy)。

    不動點性質 world(ℓ_P)=(O+Δ)+M·(P−O)=P 對**任意 M** 皆成立(純代數,不需 M 是旋轉/相似);
    且對任意附著點 x:**world(x)−P = M·(x−P)** 精確成立(仿射保形)。G-4 據此驗非均勻 scale / shear。
    """
    m00, m01, m10, m11 = m
    ox, oy = O[0] - P[0], O[1] - P[1]      # O − P
    dx = (m00 - 1.0) * ox + m01 * oy
    dy = m10 * ox + (m11 - 1.0) * oy
    return dx, dy


def pivot_delta(deg, O, P):
    """Δ(θ) = (R(θ) − I)(O − P)。O,P = (x,y) parent 座標。回傳 (dx, dy)。"""
    m00, m01, m10, m11 = rot_matrix(deg)
    ox, oy = O[0] - P[0], O[1] - P[1]      # O − P
    dx = (m00 - 1.0) * ox + m01 * oy
    dy = m10 * ox + (m11 - 1.0) * oy
    return dx, dy


def pivot_delta_full(deg, sx, sy, O, P):
    """Δ = (M − I)(O − P),M = R(θ)·diag(sx,sy)。含 scale 的「繞 pivot 旋轉+縮放」補償。
    sx=sy=1 時退化回 `pivot_delta`(純旋轉);θ=0,sx=sy=1 時 Δ=0(identity)。"""
    m00, m01, m10, m11 = transform_matrix(deg, sx, sy)
    ox, oy = O[0] - P[0], O[1] - P[1]      # O − P
    dx = (m00 - 1.0) * ox + m01 * oy
    dy = m10 * ox + (m11 - 1.0) * oy
    return dx, dy


def _time_span(frames):
    return frames[0]["time"], frames[-1]["time"]


def _dense_grid(t0, t1, dt):
    """[t0,t1] 均勻密網格(含端點),步距 ~dt。"""
    span = t1 - t0
    if span <= 0:
        return [t0]
    n = max(1, int(math.ceil(span / dt)))
    return [t0 + span * i / n for i in range(n + 1)]


def _sample_angle(rotate_frames, t):
    return spine_anim._interp(rotate_frames, t, ["angle"])["angle"]


def _sample_xy(translate_frames, t):
    d = spine_anim._interp(translate_frames, t, ["x", "y"])
    return d["x"], d["y"]


def _sample_scale(scale_frames, t):
    d = spine_anim._interp(scale_frames, t, ["x", "y"])
    return d["x"], d["y"]


def pivot_channels(rotate_frames, O, P, dt=1.0 / 60.0, existing_translate=None):
    """把一條 rotate timeline 轉成「繞 pivot P」的 (rotate_dense, translate_dense)。

    - rotate_dense:原 rotate 在密網格上的線性重取樣(角度值不變,只是加密以配合 translate)。
    - translate_dense:每個密網格點的 Δ(θ) = (R(θ)−I)(O−P);若給 existing_translate 則疊加其重取樣值。
    兩條通道**同一組時間點、皆線性**(無 curve 鍵)→ 幀間內插一致,P 幀間殘差極小。
    """
    t0, t1 = _time_span(rotate_frames)
    grid = _dense_grid(t0, t1, dt)
    rot_out, tr_out = [], []
    for t in grid:
        ang = _sample_angle(rotate_frames, t)
        dx, dy = pivot_delta(ang, O, P)
        if existing_translate:
            ex, ey = _sample_xy(existing_translate, t)
            dx += ex
            dy += ey
        rot_out.append({"time": round(t, 5), "angle": round(ang, 4)})
        tr_out.append({"time": round(t, 5), "x": round(dx, 4), "y": round(dy, 4)})
    return rot_out, tr_out


def pivot_channels_srt(rotate_frames, scale_frames, O, P, dt=1.0 / 60.0,
                       existing_translate=None):
    """把一條 rotate/scale timeline(其一或兩者)轉成「繞 pivot P 旋轉+縮放」的
    (rotate_dense, scale_dense, translate_dense)。

    - 缺席的通道回 None(rotate_frames/scale_frames 為 None/空時)。
    - 密網格為 rotate、scale 時間跨度的聯集;每點 M=R(θ)·diag(sx,sy)、Δ=(M−I)(O−P)。
    - 三條通道同一組時間點、皆線性 → 幀間內插一致,pivot 幀間殘差極小。
    """
    spans = []
    if rotate_frames:
        spans.append(_time_span(rotate_frames))
    if scale_frames:
        spans.append(_time_span(scale_frames))
    t0 = min(s[0] for s in spans)
    t1 = max(s[1] for s in spans)
    grid = _dense_grid(t0, t1, dt)
    rot_out = [] if rotate_frames else None
    sc_out = [] if scale_frames else None
    tr_out = []
    for t in grid:
        ang = _sample_angle(rotate_frames, t) if rotate_frames else 0.0
        sx, sy = _sample_scale(scale_frames, t) if scale_frames else (1.0, 1.0)
        dx, dy = pivot_delta_full(ang, sx, sy, O, P)
        if existing_translate:
            ex, ey = _sample_xy(existing_translate, t)
            dx += ex
            dy += ey
        if rot_out is not None:
            rot_out.append({"time": round(t, 5), "angle": round(ang, 4)})
        if sc_out is not None:
            sc_out.append({"time": round(t, 5), "x": round(sx, 5), "y": round(sy, 5)})
        tr_out.append({"time": round(t, 5), "x": round(dx, 4), "y": round(dy, 4)})
    return rot_out, sc_out, tr_out


def _sample_shear(shear_frames, t):
    d = spine_anim._interp(shear_frames, t, ["x", "y"])
    return d["x"], d["y"]


def pivot_channels_affine(rotate_frames, scale_frames, shear_frames, O, P,
                          dt=1.0 / 60.0, existing_translate=None):
    """候選 G-4:把 rotate/scale/**shear**(任一或多者)轉成「繞 pivot P 的一般仿射變換」的
    (rotate_dense, scale_dense, shear_dense, translate_dense)。

    - 每點 M = `transform_matrix_full(θ,sx,sy,shx,shy)`(真實 Spine local,含 shear)、Δ=(M−I)(O−P)。
    - 缺席通道回 None;密網格為所有出席通道時間跨度的聯集;各通道同一組時間點、皆線性 → 幀間一致。
    - `shear_frames=None` 時 M 退化為 R·S(sx,sy),即 `pivot_channels_srt` 的等價結果(仿射→相似特例)。
    """
    spans = []
    for fr in (rotate_frames, scale_frames, shear_frames):
        if fr:
            spans.append(_time_span(fr))
    t0 = min(s[0] for s in spans)
    t1 = max(s[1] for s in spans)
    grid = _dense_grid(t0, t1, dt)
    rot_out = [] if rotate_frames else None
    sc_out = [] if scale_frames else None
    sh_out = [] if shear_frames else None
    tr_out = []
    for t in grid:
        ang = _sample_angle(rotate_frames, t) if rotate_frames else 0.0
        sx, sy = _sample_scale(scale_frames, t) if scale_frames else (1.0, 1.0)
        shx, shy = _sample_shear(shear_frames, t) if shear_frames else (0.0, 0.0)
        m = transform_matrix_full(ang, sx, sy, shx, shy)
        dx, dy = pivot_delta_affine(m, O, P)
        if existing_translate:
            ex, ey = _sample_xy(existing_translate, t)
            dx += ex
            dy += ey
        if rot_out is not None:
            rot_out.append({"time": round(t, 5), "angle": round(ang, 4)})
        if sc_out is not None:
            sc_out.append({"time": round(t, 5), "x": round(sx, 5), "y": round(sy, 5)})
        if sh_out is not None:
            sh_out.append({"time": round(t, 5), "x": round(shx, 4), "y": round(shy, 4)})
        tr_out.append({"time": round(t, 5), "x": round(dx, 4), "y": round(dy, 4)})
    return rot_out, sc_out, sh_out, tr_out


def apply_pivots(anim, bone_origin, pivot_of, dt=1.0 / 60.0, include_scale=False,
                 include_shear=False):
    """就地(回傳同一 dict)把 anim 內「有 pivot」的 bone 轉成繞 pivot 版。

    anim         : 單支 animation dict {"bones":{bone:{rotate,translate,scale}}, "slots":{...}}
    bone_origin  : {bone_name: (Ox,Oy)}  bone setup 原點(parent 座標)
    pivot_of     : {bone_name: (Px,Py)}  該 bone 對應件的關節 pivot(同 parent 座標)
    include_scale:
      - False(預設,candidate 0i):只補償有 `rotate` 的 bone,讓件**繞 pivot 旋轉**(scale 不動)。
      - True(延伸 G-3):按 M=R·S 補償有 `rotate` 或 `scale` 的 bone,讓件同時**繞 pivot 旋轉+縮放**。
    include_shear:
      - True(延伸 G-4):按真實 Spine local M=R·shear·S 補償有 `rotate`/`scale`/`shear` 的 bone,
        讓件繞 pivot 做**一般仿射**(含 shear/非均勻 scale)變換(隱含 include_scale)。
    回傳被轉換的 bone 名 list(供上層記錄)。
    """
    converted = []
    for bone, chans in anim.get("bones", {}).items():
        if bone not in pivot_of or bone not in bone_origin:
            continue
        has_rot = bool(chans.get("rotate"))
        has_sc = bool(chans.get("scale"))
        has_sh = bool(chans.get("shear"))
        if not (has_rot or ((include_scale or include_shear) and has_sc)
                or (include_shear and has_sh)):
            continue
        O = bone_origin[bone]
        P = pivot_of[bone]
        # pivot 與件原點重合(<0.5px)→ 繞件中心即繞 pivot,無需補償(避免多餘 translate)
        if math.hypot(O[0] - P[0], O[1] - P[1]) < 0.5:
            continue
        existing = chans.get("translate")
        if include_shear:
            rot_d, sc_d, sh_d, tr_d = pivot_channels_affine(
                chans.get("rotate"), chans.get("scale"), chans.get("shear"),
                O, P, dt=dt, existing_translate=existing)
            if rot_d is not None:
                chans["rotate"] = rot_d
            if sc_d is not None:
                chans["scale"] = sc_d
            if sh_d is not None:
                chans["shear"] = sh_d
            chans["translate"] = tr_d
        elif include_scale:
            rot_d, sc_d, tr_d = pivot_channels_srt(
                chans.get("rotate"), chans.get("scale"), O, P, dt=dt,
                existing_translate=existing)
            if rot_d is not None:
                chans["rotate"] = rot_d
            if sc_d is not None:
                chans["scale"] = sc_d
            chans["translate"] = tr_d
        else:
            rot_dense, tr_dense = pivot_channels(chans["rotate"], O, P, dt=dt,
                                                 existing_translate=existing)
            chans["rotate"] = rot_dense
            chans["translate"] = tr_dense
        converted.append(bone)
    return converted


if __name__ == "__main__":
    # 煙霧測試:5° 擺動繞 pivot,確認端點 Δ=0、峰值不動點殘差 ~0
    rot = [{"time": 0.0, "angle": 0.0}, {"time": 0.25, "angle": 12.0},
           {"time": 0.5, "angle": 0.0}]
    O, P = (300.0, 500.0), (310.0, 650.0)
    r, tr = pivot_channels(rot, O, P)
    print(f"grid pts={len(r)}  Δ@t0=({tr[0]['x']},{tr[0]['y']})  Δ@tN=({tr[-1]['x']},{tr[-1]['y']})")
