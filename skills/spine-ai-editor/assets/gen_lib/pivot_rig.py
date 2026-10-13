# -*- coding: utf-8 -*-
"""gen_lib.pivot_rig — spine-ai-editor 2.0 的**繞關節 pivot 變換**入口(MERGE_PLAN Phase B3)。

這支把 repo 的 `tools/analyzer/pivot_rotation.py`(確定性「繞任意點變換」keyframe 補償)包成
**一條 skill 層級的結構軸流程**:給一份已生成的 Spine skeleton(bones 帶 setup 原點 x,y)+
一組「bone → 關節 pivot」對映 → 就地把這些 bone 的動畫由「繞**件中心 O**(bone 原點)動」
改成「繞**關節 pivot P** 動」,**完全不動骨架結構**(不加 bone、不 reparent)。

== 為什麼存在(B3 相對結構擴充 patch 的增量)==
  `references/structural_expansion.md` 的 SOP A/B 是**結構面**解法(加 bone / reparent 把 bone
  搬到關節)。本入口提供**互補的 keyframe 面**解法:bone 留在件中心,額外疊一條補償 `translate`,
  使淨效果 = 件繞關節 pivot 動。手臂該繞肩轉、頭該繞頸轉,但 `gen_animations` 產的 `rotate`/`scale`
  是「繞 bone 自身原點(非 rig 下 = 件中心)」→ 對肢體不物理。本入口把 S5 的接觸縫 pivot 接進 S1/B2
  生成的動畫,一次補好,不碰美術骨架。

== 數學(確定性、無 ML,見 pivot_rotation.py docstring)==
  設 bone setup 原點 O(parent 座標)、該幀 local 2×2 仿射 M(=R·scale·shear,Spine TRS 序)。
  要讓 pivot P 的附著局部點 ℓ_P=P−O 世界座標固定在 P:疊平移 **Δ = (M − I)(O − P)**。
  驗:world(ℓ_P)=(O+Δ)+M·(P−O)=P ∀M。θ=0 且 scale=1、shear=0 時 M=I → Δ=0 → setup/loop 端點/
  In-Out 介面全保持 identity(無縫不被破壞)。Δ 對角度/scale/shear 非線性 → 把通道加密重取樣
  成密網格(dt),rotate/scale/shear/translate 同格線性 → 幀間殘差極小。

== 三種補償模式(對外契約)==
  - "rotate"(預設,candidate 0i):只補償有 `rotate` 的 bone → 件**繞 pivot 旋轉**(scale 不補)。
  - "srt"(G-3):M=R·diag(sx,sy),補償有 `rotate`/`scale` 的 bone → 件**繞 pivot 旋轉+縮放**。
  - "affine"(G-4):M=真實 Spine local(含 shear),補償 `rotate`/`scale`/`shear` → 件繞 pivot 一般仿射。

== G 護欄(見 MERGE_PLAN §1)==
  - **G1 末鍵 curve 必拔**:輸出前一律 `curve_tools.strip_last_frame_curves()`(地雷 #12)。
    補償本身產的 rotate/translate 密網格**無 curve 鍵**(逐幀線性)→ 天生 editor 乾淨;G1 仍 wired
    以保持入口契約一致並攔住任何既有通道的末鍵 curve。
  - **G3 不覆蓋美術原檔**:就地改傳入 dict 的指定 animations(呼叫端自行決定是否複製/另存 A/B)。

== 過渡期相依(B3 → E1)==
  同 B2:目前透過 `_wire_repo_tools()` import repo 的 `tools/analyzer`(`pivot_rotation`/`spine_anim`)
  與本 `assets/`(`curve_tools`)。E1 self-contained bundle 後移除此 shim。

用法(程式化):
  from gen_lib.pivot_rig import apply_joint_pivots, bone_origins, pivot_delta
  # skel: 已生成的大獎 skeleton(bones 帶 x,y);pivots: {bone: (Px,Py)} parent 座標關節 pivot
  conv = apply_joint_pivots(skel, {"b_左手": (shoulder_x, shoulder_y)}, mode="rotate")
  # conv == {"Loop": ["b_左手"], ...}(每支 anim 被補償的 bone 名)

CLI:
  python3 pivot_rig.py --self-test     # 內建合成肢體鏈自檢(不寫檔)
"""
from __future__ import annotations
import argparse
import json
import math
import os
import sys


# --------------------------------------------------------------------- 過渡期路徑 shim
def _wire_repo_tools():
    """把 repo 的 tools/analyzer(pivot_rotation / spine_anim)與本 assets/(curve_tools)掛上 sys.path。
    回傳 (pivot_rotation_module, curve_tools_module)。E1 self-contained bundle 後改指 bundled 目錄。"""
    here = os.path.dirname(os.path.abspath(__file__))              # .../assets/gen_lib
    assets = os.path.dirname(here)                                 # .../assets
    repo = os.path.normpath(os.path.join(here, "..", "..", "..", ".."))
    cand = [os.path.join(repo, "tools", "analyzer"), assets]
    for p in cand:
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        import pivot_rotation as pr
        import curve_tools as ct
    except ImportError as e:
        raise ImportError(
            "pivot_rig 過渡期需要 repo 的 tools/analyzer(pivot_rotation/spine_anim)與 "
            "assets/curve_tools。在 repo 環境下跑;E1 self-contained bundle 後此相依會移除。"
            "原始錯誤:{}".format(e))
    return pr, ct


# --------------------------------------------------------------------- 公開 helper
def bone_origins(skel):
    """從 skeleton 的 bones 讀 setup 原點 {bone_name: (x,y)}(parent 座標;缺省為 0,0)。

    非 rig 組裝下 bone 原點即落件中心 O,正是「繞件中心動」的來源,也是補償公式的 O。
    """
    return {b["name"]: (float(b.get("x", 0.0)), float(b.get("y", 0.0)))
            for b in skel.get("bones", [])}


def pivot_delta(deg, O, P):
    """純旋轉補償 Δ(θ)=(R(θ)−I)(O−P)。見 pivot_rotation.pivot_delta。"""
    pr, _ = _wire_repo_tools()
    return pr.pivot_delta(deg, O, P)


# --------------------------------------------------------------------- 主入口
_MODES = ("rotate", "srt", "affine")


def apply_joint_pivots(skel, pivot_of, dt=1.0 / 60.0, mode="rotate",
                       anims=None, apply_g1=True):
    """就地把 skel 內指定 animations 的「有 pivot」bone 轉成繞關節 pivot 變換,回傳每支 anim 被轉的 bone。

    skel       : 完整 Spine skeleton dict(需有 "bones"(帶 setup x,y)與 "animations")。
    pivot_of   : {bone_name: (Px,Py)}  該 bone 對應件的關節 pivot(parent 座標,同 bone_origins 座標系)。
    dt         : 密網格步距(秒);1/60 下幀間殘差 << 0.1px(見 pivot_rotation)。
    mode       : _MODES 之一——"rotate"(0i,只補 rotate)/"srt"(G-3,+scale)/"affine"(G-4,+shear)。
    anims      : 要處理的 animation 名 list;None(預設)= 全部 animations。
    apply_g1   : True(預設)→ 每支處理後拔末鍵 curve(G1/地雷 #12)。設 False 僅供負對照/除錯。

    回傳 {anim_name: [converted bone names]}。pivot 與件原點重合(<0.5px)的 bone 自動略過(無需補償)。
    """
    if mode not in _MODES:
        raise ValueError("mode 須為 {} 之一,收到 {!r}".format(_MODES, mode))
    pr, ct = _wire_repo_tools()
    include_scale = mode in ("srt", "affine")
    include_shear = mode == "affine"
    origins = bone_origins(skel)
    target = list(skel.get("animations", {}).keys()) if anims is None else list(anims)
    out = {}
    for name in target:
        if name not in skel.get("animations", {}):
            raise KeyError("animation {!r} 不存在".format(name))
        anim = skel["animations"][name]
        conv = pr.apply_pivots(anim, origins, pivot_of, dt=dt,
                               include_scale=include_scale, include_shear=include_shear)
        out[name] = conv
        if apply_g1:
            ct.strip_last_frame_curves(anim)
    return out


# --------------------------------------------------------------------- 自檢(不寫檔)
# 合成肢體鏈 demo:一支 limb bone 落件中心 O,關節 pivot P 在件外(肩)。
DEMO_ORIGIN = (250.0, 300.0)     # bone setup 原點(= 非 rig 下件中心 O)
DEMO_PIVOT = (350.0, 350.0)      # 關節 pivot P(肩,parent 座標)


def _demo_skeleton():
    """最小合成 skeleton:root + 一支 limb(b_左手,帶 setup 原點),外加一支繞該 bone 旋轉的 Loop。"""
    return {
        "skeleton": {"width": 700, "height": 700},
        "bones": [
            {"name": "root"},
            {"name": "b_左手", "parent": "root", "x": DEMO_ORIGIN[0], "y": DEMO_ORIGIN[1]},
        ],
        "slots": [], "skins": {"default": {}},
        "animations": {"Loop": {"bones": {"b_左手": {"rotate": [
            {"time": 0.0, "angle": 0.0},
            {"time": 0.25, "angle": 24.0},
            {"time": 0.5, "angle": 0.0},
        ]}}}},
    }


def _self_test():
    """合成肢體鏈:apply_joint_pivots(rotate) → 量 pivot 不動點殘差(補償版)vs 件中心(負對照)。"""
    pr, _ = _wire_repo_tools()
    import spine_anim                                     # noqa: E402  repo tools/analyzer
    skel = _demo_skeleton()
    raw_rot = [dict(f) for f in skel["animations"]["Loop"]["bones"]["b_左手"]["rotate"]]
    conv = apply_joint_pivots(skel, {"b_左手": DEMO_PIVOT}, mode="rotate")
    rr = skel["animations"]["Loop"]["bones"]["b_左手"]["rotate"]
    tt = skel["animations"]["Loop"]["bones"]["b_左手"]["translate"]
    O = DEMO_ORIGIN; P = DEMO_PIVOT
    ell = (P[0] - O[0], P[1] - O[1])

    def world(local, rot_f, tr_f, t):
        ang = spine_anim._interp(rot_f, t, ["angle"])["angle"]
        xy = spine_anim._interp(tr_f, t, ["x", "y"]) if tr_f else {"x": 0.0, "y": 0.0}
        r = math.radians(ang); c, s = math.cos(r), math.sin(r)
        wx = O[0] + xy["x"] + c * local[0] - s * local[1]
        wy = O[1] + xy["y"] + s * local[0] + c * local[1]
        return math.hypot(wx - P[0], wy - P[1])

    ts = [0.5 * i / 200 for i in range(201)]
    fix = max(world(ell, rr, tt, t) for t in ts)          # 補償版 pivot 殘差
    neg = max(world(ell, raw_rot, None, t) for t in ts)    # 繞件中心(負對照)位移
    seamless = (abs(rr[0]["angle"] - rr[-1]["angle"]) < 1e-6
                and abs(tt[0]["x"] - tt[-1]["x"]) < 1e-6
                and abs(tt[0]["y"] - tt[-1]["y"]) < 1e-6)
    ok = fix < 0.5 and neg >= 10.0 and seamless and conv["Loop"] == ["b_左手"]
    print("  converted = {}  dense_keys={}".format(conv, len(rr)))
    print("  pivot 殘差(補償版) = {:.4f}px (< 0.5)".format(fix))
    print("  件中心位移(負對照) = {:.2f}px (>> 補償版, ≥ 10)".format(neg))
    print("  loop 端點無縫 = {}".format(seamless))
    return ok


def main():
    ap = argparse.ArgumentParser(description="pivot_rig 繞關節 pivot 變換入口(B3)")
    ap.add_argument("--self-test", action="store_true", help="跑內建合成肢體鏈自檢,不寫檔")
    a = ap.parse_args()
    if a.self_test:
        ok = _self_test()
        print("SELF-TEST:", "PASS" if ok else "FAIL")
        sys.exit(0 if ok else 1)
    ap.error("需要 --self-test(程式化用途請 import apply_joint_pivots)")


if __name__ == "__main__":
    main()
