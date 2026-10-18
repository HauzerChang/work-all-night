# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 的**繞關節 pivot 變換**入口(MERGE_PLAN Phase B3,結構軸)。

== 這支解決什麼(為何是「結構軸」)==
  `references/structural_expansion.md` 教的是**動骨架**(加 bone / reparent / transform mode)讓件繞關節轉。
  但那是結構性改動(改 bones 陣列)。本模組提供**互補的 keyframe 級解法**:**不動骨架結構**,
  只在既有動畫上額外疊一條補償 `translate`,使貼在某 bone 的件淨效果 = 繞**關節 pivot P**(而非件中心 O)轉/縮/剪。

  非 rig 組裝時 bone 原點落件中心 O,故 `gen_animations` 產出的 limb `rotate` 會讓手臂繞**自身中心**轉
  —— 對肢體不物理(手臂該繞肩、頭該繞頸)。數學(剛體/仿射「繞任意點變換」分解,確定性、無 ML):
      設 bone 世界(parent 座標)線性部 M(=R·shear·diag(sx,sy),真實 Spine 3.8 local)。
      要讓 pivot 的附著局部點 ℓ_P=P−O 世界座標固定在 P ⟹ 加平移 **Δ = (M − I)(O − P)**。
  θ=0、s=1、shear=0 時 M=I → Δ=0 → **setup / loop 端點 / In-Out 介面全保持 identity**(無縫不被破壞)。

== G 護欄(見 MERGE_PLAN §1)==
  - **G1 末鍵 curve 必拔**:補償會把 rotate 通道**加密重取樣**成均勻密網格(Δ 對 θ 非線性,只在原鍵放 Δ
    會有幀間殘差)。重取樣輸出為**純線性鍵(無 curve)** → 本就 editor-safe;收尾仍再過一次
    `strip_last_frame_curves()` 保險(與 make_beat 入口同一條 G1 契約)。
  - **G3 不覆蓋美術原檔**:本流程只在**傳入的動畫**上疊加補償,不碰其他動畫 / bones / slots。

== self-contained(E1,2026-10-18)==
  同 make_beat:透過其 `_wire_repo_tools()` 掛 **bundled** 生成引擎(`gen_lib/_bundled` 的
  `pivot_rotation` / `spine_anim`)。E1 後不再相依本 research repo 的 `tools/`。

用法(程式化):
  from gen_lib.pivot_axis import apply_joint_pivots, bone_origins_from_skel
  skel, aname = generate_idle(IDLE_DEMO_PARTS)             # 來源:limb 走 rotate 的 idle
  pivots = {"b_arm_L": (shoulder_x, shoulder_y), ...}      # 關節 pivot(parent 座標)
  converted = apply_joint_pivots(skel, aname, pivots)      # 就地把 limb 轉成繞肩旋轉;回傳被轉 bone 名
"""
from __future__ import annotations

# 取用 make_beat 的過渡期路徑 shim(package 或 path-added 兩種 import 皆可)。
try:
    from . import make_beat as _mb
except ImportError:  # 當 gen_lib 目錄被直接加進 sys.path 時
    import make_beat as _mb


def _wire():
    """掛上 bundled 生成引擎,回傳 (pivot_rotation_module, curve_tools_module)。E1 後走 self-contained。"""
    _, ct = _mb._wire_repo_tools()      # 把 gen_lib/_bundled、assets 掛上 sys.path
    import pivot_rotation as pr          # noqa: E402  bundled(含 spine_anim 同目錄相依)
    return pr, ct


def bone_origins_from_skel(skel):
    """從 skeleton 的 bones 取每根(非 root)bone 的 setup 原點 (x,y)(parent 座標)。
    回傳 {bone_name: (Ox, Oy)}。非 rig 組裝下這即件中心 O(補償的起點)。"""
    out = {}
    for b in skel.get("bones", []):
        name = b.get("name")
        if name and name != "root":
            out[name] = (float(b.get("x", 0.0)), float(b.get("y", 0.0)))
    return out


def apply_joint_pivots(skel, anim_name, pivot_of, bone_origin=None,
                       dt=1.0 / 60.0, include_scale=False, include_shear=False,
                       apply_g1=True):
    """就地把 `skel["animations"][anim_name]` 內「有 pivot」的 bone 轉成**繞關節 pivot** 版。

    skel         : 完整 Spine skeleton dict(含 "bones" 與 "animations")。
    anim_name    : 要處理的動畫名(只動這一支,G3 不碰其他)。
    pivot_of     : {bone_name: (Px,Py)} 關節 pivot(parent 座標,與 bone_origin 同系)。
    bone_origin  : {bone_name: (Ox,Oy)};None → 自 skel bones 取(`bone_origins_from_skel`)。
    include_scale: True → 按 M=R·diag(sx,sy) 補償(件**繞 pivot 旋轉+縮放**;手臂從肩伸長)。
    include_shear: True → 按真實 Spine local M=R·shear·S 補償(件繞 pivot 做**一般仿射**;隱含 include_scale)。
    apply_g1     : True(預設)→ 補償後再過一次 strip_last_frame_curves(保險)。

    回傳被轉換的 bone 名 list。pivot 與件原點重合(<0.5px)的 bone 自動跳過(避免多餘 translate)。
    """
    pr, ct = _wire()
    anims = skel.get("animations", {})
    if anim_name not in anims:
        raise KeyError("skel 無動畫 {!r}(現有:{})".format(anim_name, list(anims)))
    if bone_origin is None:
        bone_origin = bone_origins_from_skel(skel)
    anim = anims[anim_name]
    converted = pr.apply_pivots(anim, bone_origin, pivot_of, dt=dt,
                                include_scale=include_scale, include_shear=include_shear)
    if apply_g1:
        ct.strip_last_frame_curves(anim)
    return converted
