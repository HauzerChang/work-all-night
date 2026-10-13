#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 的**繞關節 pivot 變換**入口(MERGE_PLAN Phase B3)。

這支把 repo 的確定性 pivot 補償引擎(`tools/analyzer/pivot_rotation.py`)包成一條
**skill 層級的結構軸流程**:給一支(或整份)動畫 + 每個 bone 對應的關節 pivot →
就地把「bone 繞自身原點(= 件中心 O)旋轉/縮放/切變」轉成「件**繞關節 pivot P** 做同樣變換」,
**完全不動骨架結構**(不加 bone、不 reparent)。

== 為什麼它屬「結構軸」(對應 references/structural_expansion.md)==
  structural_expansion.md 的 SOP A/B 用**加 bone / reparent**(動骨架結構)讓某件能繞關節轉;
  本入口提供**互補的 keyframe 級解法**:bone 留在件中心,額外補一條 `translate`,使淨效果 =
  件繞 pivot 轉。數學(剛體/仿射「繞任意點變換」分解,確定性、無 ML):
      Δ = (M − I)(O − P),   M = bone local 2×2(R·shear·S;純旋轉時 M=R(θ))
  不動點:world(ℓ_P) = (O+Δ) + M·(P−O) = P 對任意 M 成立;θ=0 且 S=I、shear=0 → M=I → Δ=0
  → **setup / loop 端點 / In-Out 介面全保持 identity**(B2 生成波的無縫性不被破壞)。
  詳見 `references/structural_expansion.md` 新增的「SOP E:繞關節 pivot 的 keyframe 級變換」。

== G 護欄(見 MERGE_PLAN §1)==
  - **G1 末鍵 curve 必拔**:輸出前一律呼叫 `curve_tools.strip_last_frame_curves()`。pivot 補償後的
    rotate/translate/scale/shear 皆為**密網格線性鍵**(無 curve)→ 通常拔 0 條,但仍 wire 進流程
    (若上游 anim 本帶末鍵 curve,此步會拔)。
  - **G3 不覆蓋美術原檔**:本入口**就地改傳入的 anim dict**,呼叫端自行決定存新動畫名(Xxx_v2)。

== 過渡期相依(B3 → E1)==
  本檔 import repo 的 `tools/analyzer`(`pivot_rotation` / `spine_anim`)與 `assets/curve_tools`,
  做法同 `make_beat.py`(MERGE_PLAN 明列過渡期);E1 self-contained bundle 後移除 shim。

用法(程式化):
  from gen_lib.pivot_about import apply_pivot_about
  # 整份 skeleton(bone_origin 自 bones setup x/y 自動推得):
  report = apply_pivot_about(skel, pivot_of={"b_arm_L": (350.0, 520.0)}, include_scale=True)
  # 單支 anim(需顯式給 bone_origin):
  conv = apply_pivot_about(anim, pivot_of={"b_hand": P}, bone_origin={"b_hand": O})

  from gen_lib.pivot_about import generate_bigwin_about_pivots
  skel, aname, report = generate_bigwin_about_pivots(DEMO_PARTS, pivot_of={...}, beat="cascade")
"""
from __future__ import annotations
import os
import sys


# --------------------------------------------------------------------- 過渡期路徑 shim
def _wire_repo_tools():
    """掛上 repo 的 tools/analyzer(pivot_rotation / spine_anim)與 assets/(curve_tools)。
    回傳 (pivot_rotation_module, curve_tools_module)。E1 bundle 後改指向 bundled 目錄即可。"""
    here = os.path.dirname(os.path.abspath(__file__))              # .../assets/gen_lib
    assets = os.path.dirname(here)                                 # .../assets
    repo = os.path.normpath(os.path.join(here, "..", "..", "..", ".."))
    for p in (os.path.join(repo, "tools", "analyzer"), assets):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        import pivot_rotation as pr       # noqa: E402  (內部 import spine_anim)
        import curve_tools as ct          # noqa: E402
    except ImportError as e:
        raise ImportError(
            "pivot_about 過渡期需要 repo 的 tools/analyzer(pivot_rotation/spine_anim)與 "
            "assets/curve_tools。在 repo 環境下跑;E1 self-contained bundle 後此相依會移除。"
            "原始錯誤:{}".format(e))
    return pr, ct


def _bone_origins(skel):
    """從 skeleton 的 bones setup(parent 座標 x/y;預設 0,0)推得各 bone 原點 O。root 不含。"""
    origins = {}
    for b in skel.get("bones", []):
        if b.get("name") == "root":
            continue
        origins[b["name"]] = (float(b.get("x", 0.0)), float(b.get("y", 0.0)))
    return origins


def apply_pivot_about(target, pivot_of, bone_origin=None, dt=1.0 / 60.0,
                      include_scale=False, include_shear=False, anims=None,
                      apply_g1=True):
    """就地把「件繞件中心變換」轉成「件繞關節 pivot 變換」。回傳轉換報告。

    target       : 整份 skeleton dict(含 "animations")**或**單支 anim dict(含 "bones")。
    pivot_of     : {bone_name: (Px,Py)} 各 bone 對應件的關節 pivot(parent 座標)。
    bone_origin  : {bone_name: (Ox,Oy)} bone setup 原點。整份 skeleton 可省略(自 bones 推得);
                   單支 anim **必須**提供。
    dt           : 密網格步距(秒)。Δ 對 θ/s 非線性 → 加密重取樣使幀間殘差極小(dt=1/60 << 0.1px)。
    include_scale: True → 按 M=R·diag(sx,sy) 補償(件繞 pivot 旋轉+縮放;肢體從關節伸長)。
    include_shear: True → 按真實 Spine local M=R·shear·S 補償(一般仿射;隱含 include_scale)。
    anims        : 僅整份 skeleton 模式;限定只轉這些動畫名(None=全部)。
    apply_g1     : True(預設)→ 每支轉換後動畫過 G1(strip_last_frame_curves)。

    回傳:整份 skeleton → {"mode":"skeleton","converted":{anim_name:[bones...]},"g1":bool};
          單支 anim    → {"mode":"anim","converted":[bones...],"g1":bool}。
    """
    pr, ct = _wire_repo_tools()
    if not isinstance(pivot_of, dict) or not pivot_of:
        raise ValueError("pivot_of 須為非空 {bone:(x,y)} dict")

    # ---- 整份 skeleton 模式 ----
    if isinstance(target, dict) and "animations" in target:
        origins = dict(_bone_origins(target))
        if bone_origin:
            origins.update(bone_origin)
        names = list(target["animations"].keys()) if anims is None else list(anims)
        report = {}
        for an in names:
            anim = target["animations"][an]
            conv = pr.apply_pivots(anim, origins, pivot_of, dt=dt,
                                   include_scale=include_scale, include_shear=include_shear)
            if apply_g1 and conv:
                ct.strip_last_frame_curves(anim)
            report[an] = conv
        return {"mode": "skeleton", "converted": report, "g1": bool(apply_g1)}

    # ---- 單支 anim 模式 ----
    if bone_origin is None:
        raise ValueError("單支 anim 模式必須提供 bone_origin={bone:(Ox,Oy)}")
    conv = pr.apply_pivots(target, bone_origin, pivot_of, dt=dt,
                           include_scale=include_scale, include_shear=include_shear)
    if apply_g1 and conv:
        ct.strip_last_frame_curves(target)
    return {"mode": "anim", "converted": conv, "g1": bool(apply_g1)}


def generate_bigwin_about_pivots(parts, pivot_of, beat="cascade", bone_origin=None,
                                 dt=1.0 / 60.0, include_scale=False, include_shear=False,
                                 apply_g1=True, **gen_opts):
    """B2 生成 + B3 pivot 一步到位:generate_bigwin(parts,beat) → apply_pivot_about。
    回傳 (skeleton_dict, anim_name, pivot_report)。pivot_of 的 bone 名須對應 gen_lib 的 "b_"+safe(part)。"""
    from make_beat import generate_bigwin           # noqa: E402  同目錄 gen_lib 入口
    skel, aname = generate_bigwin(parts, beat=beat, apply_g1=apply_g1, **gen_opts)
    report = apply_pivot_about(skel, pivot_of, bone_origin=bone_origin, dt=dt,
                               include_scale=include_scale, include_shear=include_shear,
                               anims=[aname], apply_g1=apply_g1)
    return skel, aname, report
