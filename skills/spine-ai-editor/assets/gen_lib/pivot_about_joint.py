#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_lib — spine-ai-editor 2.0 的**繞關節 pivot 變換**入口(MERGE_PLAN Phase B3)。

這支把 repo 累積的確定性 **pivot 變換引擎**(`tools/analyzer/pivot_rotation.py`:
`Δ=(M−I)(O−P)`、rotate / scale / shear 皆可)包成一條 **skill 層級的結構軸入口**:
給一份 skeleton(或單支 animation)+ 每件的**關節 pivot P**(由 S5 接觸縫推得)→
就地把「件繞**件中心 O** 轉/縮/剪」改成「件繞**關節 pivot P**」,而**完全不動骨架結構**。

== 為什麼存在(B3 相對 B1/B2 的增量)==
  B1/B2 把「大獎節拍生成」接進了 v1.3.0 的編輯器真值閘(`validator_v1`)。但生成出來的
  limb `rotate`/`scale` 在**非 rig** 組裝下 bone 落在**件中心 O**,故手臂會繞「自己中心」轉,
  對肢體不物理(手臂該繞肩、頭該繞頸)。repo 的**結構性解法**(`build_spine --rig`)是把 bone
  搬到關節(動骨架);本模組提供**互補的 keyframe 級解法**——bone 留在件中心,額外加一條
  補償 `translate`,使淨效果=件繞關節 pivot P,**骨架結構一位元都不動**。

  它屬「**結構軸**」(與 `references/structural_expansion.md` 的加骨/reparent 並列):
  同樣是「讓視覺元件取得正確的可動軸」,只是用 keyframe 補償而非改骨樹。見該檔 SOP E。

== 數學(確定性、無 ML)==
  設 bone setup 原點在 O(parent 座標)、local 線性部 M=R(θ)·shear·diag(sx,sy)(真實 Spine TRS)。
  要讓貼在該 bone 的幾何繞 pivot P(同 parent 座標)變換,只需在原通道外加平移
      Δ = (M − I)(O − P)。
  不動點:(O+Δ)+M·(P−O) = O + (M−I)(O−P) + M(P−O) = O + (P−O) = P  ∀M  → P 為不動點。
  M=I(θ=0,s=1,shear=0)時 Δ=0 → **setup / loop 端點 / In-Out 介面全保持 identity**(無縫不被破壞)。
  Δ 對 θ/s 非線性 → 通道**加密重取樣**成均勻密網格(dt 秒)使幀間殘差 << 0.1px(repo 已驗)。

== G 護欄(見 MERGE_PLAN §1)==
  - **G1 末鍵 curve 必拔**:本軸輸出的 rotate/translate/scale/shear 皆為**密網格線性鍵**(無 curve 鍵),
    理論上不產生末鍵 curve;為與 2.0 其餘輸出一致,`apply_pivot_about_joint(..., apply_g1=True)`
    仍對被改動的 animation 跑一次 `strip_last_frame_curves()`(預設開,地雷 #12 的統一保險)。
  - **G3 不覆蓋美術原檔**:本流程**就地改**傳入的 animation dict(呼叫端自行決定存 A/B);配合 B2
    `generate_bigwin` 從零生成時,等於在新生成的大獎動畫上套關節軸,不碰任何既有檔。

== 過渡期相依(B3 → E1)==
  本檔目前**import repo 的 `tools/analyzer`**(`pivot_rotation` / `spine_anim`)與 `assets/curve_tools`,
  透過 `_wire_repo_tools()` 路徑 shim。這是 MERGE_PLAN 明列的過渡期做法;**Phase E1** 會把生成/變換碼
  bundle 進 `assets/`(self-contained,滿足 G5),屆時移除此 shim。

用法(程式化):
  from gen_lib.pivot_about_joint import apply_pivot_about_joint, apply_pivot_about_joint_anim
  # 1) 整份 skeleton:bone_origin 由 skel['bones'] 的 (x,y) 推得,對所有 animations 套關節軸
  converted = apply_pivot_about_joint(skel, pivot_of={"b_arm_L": (Px, Py), ...})
  # 2) 單支 animation + 明確 bone_origin
  conv = apply_pivot_about_joint_anim(anim, bone_origin, pivot_of)

用法(CLI):
  python3 pivot_about_joint.py --self-test     # 煙霧測試:繞外部 pivot 的擺動,端點 Δ=0
"""
from __future__ import annotations
import argparse
import json
import math
import os
import sys


# --------------------------------------------------------------------- 過渡期路徑 shim
def _wire_repo_tools():
    """把 repo 的 tools/analyzer、tools/rig、tools/mesh_gen、以及本 assets/(curve_tools)掛上 sys.path。
    E1 self-contained bundle 後本函式改為指向 bundled 目錄即可。

    回傳 (pivot_rotation_module, spine_anim_module, curve_tools_module)。找不到時給清楚錯誤。
    """
    here = os.path.dirname(os.path.abspath(__file__))              # .../assets/gen_lib
    assets = os.path.dirname(here)                                 # .../assets
    repo = os.path.normpath(os.path.join(here, "..", "..", "..", ".."))
    cand = [
        os.path.join(repo, "tools", "analyzer"),
        os.path.join(repo, "tools", "rig"),
        os.path.join(repo, "tools", "mesh_gen"),
        assets,                                                     # curve_tools
    ]
    for p in cand:
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        import pivot_rotation as pr
        import spine_anim as sa
        import curve_tools as ct
    except ImportError as e:
        raise ImportError(
            "pivot_about_joint 過渡期需要 repo 的 tools/analyzer(pivot_rotation / spine_anim)"
            "與 assets/curve_tools。在 repo 環境下跑;E1 self-contained bundle 後此相依會移除。"
            "原始錯誤:{}".format(e))
    return pr, sa, ct


# --------------------------------------------------------------------- 核心入口
def _bone_origin_from_skel(skel):
    """從 skeleton 的 bones 清單推得每個 bone 的 setup 原點 (x,y)(parent 座標),root 除外。"""
    out = {}
    for b in skel.get("bones", []):
        if b.get("name") == "root":
            continue
        out[b["name"]] = (float(b.get("x", 0.0)), float(b.get("y", 0.0)))
    return out


def apply_pivot_about_joint_anim(anim, bone_origin, pivot_of, dt=1.0 / 60.0,
                                 include_scale=False, include_shear=False,
                                 apply_g1=True):
    """就地把單支 animation 內「有 pivot」的 bone 轉成**繞關節 pivot** 版。

    anim         : 單支 animation dict {"bones":{bone:{rotate,translate,scale,shear}}, "slots":{...}}
    bone_origin  : {bone_name: (Ox,Oy)}  bone setup 原點(parent 座標)
    pivot_of     : {bone_name: (Px,Py)}  該 bone 對應件的關節 pivot(同 parent 座標)
    include_scale: True → 連 scale 也繞 pivot(M=R·S);False(預設)=只繞 pivot 旋轉(0i)。
    include_shear: True → 一般仿射(含 shear,M=R·shear·S,隱含 include_scale)。
    apply_g1     : True(預設)→ 轉換後對本 anim 跑 strip_last_frame_curves(地雷 #12 統一保險)。

    回傳被轉換的 bone 名 list。
    """
    pr, _sa, ct = _wire_repo_tools()
    converted = pr.apply_pivots(anim, bone_origin, pivot_of, dt=dt,
                                include_scale=include_scale, include_shear=include_shear)
    if apply_g1:
        ct.strip_last_frame_curves(anim)
    return converted


def apply_pivot_about_joint(skel, pivot_of, dt=1.0 / 60.0, include_scale=False,
                            include_shear=False, anims=None, apply_g1=True,
                            bone_origin=None):
    """就地把一份 skeleton 的 animations 轉成**繞關節 pivot** 版(B3 skill 結構軸對外契約)。

    skel        : 完整 Spine skeleton dict(含 bones / animations)。
    pivot_of    : {bone_name: (Px,Py)} 關節 pivot(parent 座標)。
    bone_origin : 省略時由 `skel['bones']` 的 (x,y) 推得;可顯式覆寫。
    anims       : 要處理的 animation 名清單;None=全部。
    其餘參數同 `apply_pivot_about_joint_anim`。

    回傳 {anim_name: [converted bone names]}(只含真的有轉換的 anim)。
    """
    if bone_origin is None:
        bone_origin = _bone_origin_from_skel(skel)
    names = anims if anims is not None else list(skel.get("animations", {}).keys())
    result = {}
    for name in names:
        anim = skel["animations"][name]
        conv = apply_pivot_about_joint_anim(
            anim, bone_origin, pivot_of, dt=dt, include_scale=include_scale,
            include_shear=include_shear, apply_g1=apply_g1)
        if conv:
            result[name] = conv
    return result


# --------------------------------------------------------------------- 自檢(不寫檔)
def _self_test():
    """煙霧測試:一條繞**件外** pivot 的擺動 timeline,確認端點 Δ=0、密網格有產生。"""
    pr, _sa, _ct = _wire_repo_tools()
    anim = {"bones": {"b_arm": {"rotate": [
        {"time": 0.0, "angle": 0.0}, {"time": 0.25, "angle": 24.0}, {"time": 0.5, "angle": 0.0}]}}}
    bone_origin = {"b_arm": (300.0, 500.0)}
    pivot_of = {"b_arm": (310.0, 650.0)}            # 肩(件外)
    conv = apply_pivot_about_joint_anim(anim, bone_origin, pivot_of, apply_g1=True)
    tr = anim["bones"]["b_arm"]["translate"]
    d0 = math.hypot(tr[0]["x"], tr[0]["y"])
    dN = math.hypot(tr[-1]["x"], tr[-1]["y"])
    ok = (conv == ["b_arm"]) and (d0 < 1e-6) and (dN < 1e-6) and (len(tr) > 10)
    print("  converted={}  dense_keys={}  Δ@t0={:.2e}  Δ@tN={:.2e}  -> {}".format(
        conv, len(tr), d0, dN, "OK" if ok else "FAIL"))
    return ok


def main():
    ap = argparse.ArgumentParser(description="gen_lib 繞關節 pivot 變換入口(B3)")
    ap.add_argument("--self-test", action="store_true", help="跑內建煙霧測試,不寫檔")
    a = ap.parse_args()
    if a.self_test:
        ok = _self_test()
        print("SELF-TEST:", "PASS" if ok else "FAIL")
        sys.exit(0 if ok else 1)
    ap.error("需要 --self-test(程式化用請 import apply_pivot_about_joint)")


if __name__ == "__main__":
    main()
