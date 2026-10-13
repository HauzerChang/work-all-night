#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_lib.pivot_about_joint — spine-ai-editor 2.0 的**繞關節 pivot 變換**入口(MERGE_PLAN Phase B3)。

把 repo 的確定性「繞任意點變換」模組(`tools/analyzer/pivot_rotation.py`)包成**一條 skill 層級的
公開 API** `pivot_about_joint()`,讓「件繞關節 pivot 轉/縮放/仿射,而**非**繞件中心」成為結構軸的
一個**零骨架改動**手段——與 `references/structural_expansion.md` 的「移 bone(SOP A–D)」互補。

== 為什麼存在(結構軸的 keyframe 級互補解)==
  `gen_animations` 產出的 `rotate` 讓 bone 繞**自身原點**轉。非 `--rig` 組裝時 bone 原點落在**件中心 O**,
  故 limb/head 的 rotate 會讓件繞**件中心**轉——對肢體不物理(手臂該繞肩、頭該繞頸)。
    - 「移 bone 到關節」= 結構改動(structural_expansion SOP A/B),改骨架、Cocos 需完整重 import。
    - 「繞 pivot 補償」= **本入口**,bone 留件中心,額外加一條補償 `translate`,使淨效果=件繞關節 pivot P 轉,
      **完全不動骨架結構**(可純 patch、可 diff、可回滾;介面 θ=0→Δ=0 保持無縫)。
  數學(確定性、無 ML):Δ = (M − I)(O − P),M = bone local 2×2(R·scale·shear)。
  不動點性質 world(ℓ_P)=(O+Δ)+M·(P−O)=P 對**任意 M** 成立。詳見 `pivot_rotation.py` docstring。

== G 護欄(見 MERGE_PLAN §1)==
  - **G1 末鍵 curve 必拔**:補償通道以密網格線性重取樣產生(無 curve 鍵),故輸出一律過
    `curve_tools.strip_last_frame_curves()` 通常拔 0 條;仍保留這一關使入口與 B1/B2 的 G 護欄一致,
    避免 existing_translate 來源若帶末鍵 curve 時漏掉(地雷 #12,runtime 不炸、editor 炸)。
  - **G3 不覆蓋美術原檔**:本入口**就地改動傳入的 anim dict**(與 repo `apply_pivots` 同契約);
    要安全存 A/B,呼叫端先 deepcopy 再傳入,或把補償結果寫成新動畫名(`Xxx_pivot`)。

== 過渡期相依(B3 → E1)==
  同 make_beat:目前透過 `_wire_repo_tools()` import repo 的 `tools/analyzer`(pivot_rotation / spine_anim)
  與 `assets/curve_tools`。**Phase E1** 會 self-contained bundle 進 `assets/`,屆時移除此 shim。

用法(程式化):
  from gen_lib.pivot_about_joint import pivot_about_joint
  # anim 內「有 pivot」的 bone(有 rotate,mode="scale"/"affine" 時另含 scale/shear)會被就地轉成繞 pivot 版
  converted = pivot_about_joint(anim, bone_origin={"b_左手": O}, pivot_of={"b_左手": P}, mode="rotate")

用法(CLI 自檢,不寫檔):
  python3 pivot_about_joint.py --self-test
"""
from __future__ import annotations
import argparse
import json
import math
import os
import sys


# --------------------------------------------------------------------- 過渡期路徑 shim
def _wire_repo_tools():
    """掛上 repo 的 tools/analyzer(pivot_rotation / spine_anim)與 assets/(curve_tools)。
    E1 self-contained bundle 後改指向 bundled 目錄即可。回傳 (pivot_rotation, curve_tools)。"""
    here = os.path.dirname(os.path.abspath(__file__))              # .../assets/gen_lib
    assets = os.path.dirname(here)                                 # .../assets
    repo = os.path.normpath(os.path.join(here, "..", "..", "..", ".."))
    for p in (os.path.join(repo, "tools", "analyzer"),
              os.path.join(repo, "tools", "rig"),
              os.path.join(repo, "tools", "mesh_gen"),
              assets):
        if p not in sys.path:
            sys.path.insert(0, p)
    try:
        import pivot_rotation as pr
        import curve_tools as ct
    except ImportError as e:
        raise ImportError(
            "pivot_about_joint 過渡期需要 repo 的 tools/analyzer(pivot_rotation)與 assets/curve_tools。"
            "在 repo 環境下跑;E1 self-contained bundle 後此相依會移除。原始錯誤:{}".format(e))
    return pr, ct


# 支援的補償模式(skill 入口對外契約),對映 repo apply_pivots 的旗標:
#   "rotate" = candidate 0i(只補償有 rotate 的 bone,件繞 pivot 旋轉;scale 不動)
#   "scale"  = 延伸 G-3(M=R·S,件繞 pivot 旋轉+縮放)
#   "affine" = 延伸 G-4(真實 Spine local M=R·shear·S,含 shear/非均勻 scale)
SUPPORTED_MODES = ("rotate", "scale", "affine")


def pivot_about_joint(anim, bone_origin, pivot_of, mode="rotate",
                      dt=1.0 / 60.0, apply_g1=True):
    """讓 `anim` 內「有 pivot」的 bone 繞關節 pivot P 做變換(而非繞件中心 O),**不動骨架結構**。

    anim        : 單支 animation dict {"bones":{bone:{rotate,translate,scale,shear}}, ...}。**就地改動**。
    bone_origin : {bone_name: (Ox,Oy)}  bone setup 原點(parent 座標;非 rig 下 = 件中心 O)。
    pivot_of    : {bone_name: (Px,Py)}  該件的關節 pivot(同 parent 座標;如 infer_pivots 的接觸縫)。
    mode        : SUPPORTED_MODES 之一(見上)。
    dt          : 密網格重取樣步距(秒);Δ 對 θ/s 非線性,需加密才不幀間漏 pivot(repo 既有分析)。
    apply_g1    : True(預設)→ 轉換後拔末鍵 curve(G1,地雷 #12)。

    回傳被轉換的 bone 名 list(subset of anim.bones ∩ pivot_of ∩ bone_origin;pivot≈O 的 bone 跳過)。
    """
    if mode not in SUPPORTED_MODES:
        raise ValueError("mode 須為 {} 之一,收到 {!r}".format(SUPPORTED_MODES, mode))
    pr, ct = _wire_repo_tools()
    include_scale = mode in ("scale", "affine")
    include_shear = mode == "affine"
    converted = pr.apply_pivots(anim, bone_origin, pivot_of, dt=dt,
                                include_scale=include_scale, include_shear=include_shear)
    if apply_g1:
        ct.strip_last_frame_curves(anim)
    return converted


# --------------------------------------------------------------------- demo(無需真實資產)
# 合成「肩—手臂」幾何:bone 落件中心 O,肩關節 pivot P 在上方 ~150px(近 Award 左手臂長量級)。
# 供 standalone 自檢與示範(不依賴 Award.json / PSD)。
DEMO_BONE = "b_arm_L"
DEMO_O = (250.0, 300.0)          # 件中心(bone setup 原點)
DEMO_P = (330.0, 440.0)          # 肩關節 pivot(上外側),|O-P| ≈ 161px


def demo_limb_loop(peak_deg=24.0):
    """造一支最小 Loop:limb bone 繞擺 0→peak→0(首尾 identity,可接 Loop)。回傳 anim dict。"""
    return {
        "bones": {DEMO_BONE: {"rotate": [
            {"time": 0.0, "angle": 0.0},
            {"time": 0.25, "angle": peak_deg},
            {"time": 0.5, "angle": 0.0},
        ]}},
        "slots": {},
    }


def _self_test():
    """生成 demo Loop → 繞 pivot 補償 → 以純 Python 模擬世界變換,量 pivot 不動點殘差 + 負對照。"""
    pr, _ = _wire_repo_tools()
    import spine_anim  # repo tools/analyzer

    def world_of(local, O, rot_frames, tr_frames, t):
        ang = spine_anim._interp(rot_frames, t, ["angle"])["angle"]
        xy = (spine_anim._interp(tr_frames, t, ["x", "y"]) if tr_frames else {"x": 0.0, "y": 0.0})
        r = math.radians(ang)
        c, s = math.cos(r), math.sin(r)
        wx = O[0] + xy["x"] + c * local[0] - s * local[1]
        wy = O[1] + xy["y"] + s * local[0] + c * local[1]
        return wx, wy

    O, P = DEMO_O, DEMO_P
    ell = (P[0] - O[0], P[1] - O[1])
    anim = demo_limb_loop()
    raw_rot = [dict(f) for f in anim["bones"][DEMO_BONE]["rotate"]]  # 負對照用(未補償)
    converted = pivot_about_joint(anim, {DEMO_BONE: O}, {DEMO_BONE: P}, mode="rotate")
    rot_d = anim["bones"][DEMO_BONE]["rotate"]
    tr_d = anim["bones"][DEMO_BONE]["translate"]
    ts = [0.5 * i / 200 for i in range(201)]
    fix = max(math.hypot(*(lambda w: (w[0] - P[0], w[1] - P[1]))(
        world_of(ell, O, rot_d, tr_d, t))) for t in ts)
    neg = max(math.hypot(*(lambda w: (w[0] - P[0], w[1] - P[1]))(
        world_of(ell, O, raw_rot, None, t))) for t in ts)
    d0 = math.hypot(tr_d[0]["x"], tr_d[0]["y"])
    ok = (fix < 0.5) and (neg > 10.0) and (d0 < 1e-6) and bool(converted)
    print("  converted={}  dense_keys={}".format(converted, len(rot_d)))
    print("  pivot 不動點殘差(補償)= {:.4f}px  (< 0.5)".format(fix))
    print("  負對照(繞件中心)位移  = {:.2f}px  (>> 補償)".format(neg))
    print("  identity Δ@t0          = {:.2e}px  (< 1e-6)".format(d0))
    return ok


def main():
    ap = argparse.ArgumentParser(description="gen_lib 繞關節 pivot 變換入口(B3)")
    ap.add_argument("--mode", default="rotate", choices=SUPPORTED_MODES)
    ap.add_argument("--self-test", action="store_true", help="跑內建合成肩/臂自檢,不寫檔")
    ap.add_argument("--out", help="把 demo Loop 補償後寫成 anim JSON(除錯用)")
    a = ap.parse_args()
    if a.self_test:
        ok = _self_test()
        print("SELF-TEST:", "PASS" if ok else "FAIL")
        sys.exit(0 if ok else 1)
    anim = demo_limb_loop()
    conv = pivot_about_joint(anim, {DEMO_BONE: DEMO_O}, {DEMO_BONE: DEMO_P}, mode=a.mode)
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(anim, f, ensure_ascii=False, indent=1)
    print(json.dumps({"converted": conv, "mode": a.mode,
                      "out": a.out or None}, ensure_ascii=False))


if __name__ == "__main__":
    main()
