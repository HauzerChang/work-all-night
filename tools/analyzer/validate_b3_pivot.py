#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B3 閘 — `gen_lib.pivot_rig` 繞關節 pivot 變換入口 → 7AC 移植 + v1.3.0 `validator_v1` 雙真值
(spine-ai-editor 2.0 Phase B3)。

承 B2(`validate_b2_genlib.py`,生成庫入口):B3 把 repo 的 `pivot_rotation.py`(確定性「繞任意點
變換」補償)抽成**結構軸 skill 入口** `skills/spine-ai-editor/assets/gen_lib/pivot_rig.py`
(`apply_joint_pivots`),讓「件繞件中心動 → 件繞關節 pivot 動」成為一條可重用、可機讀的流程。

本閘證明:**透過 skill 入口**(非直呼 repo 內部函式)套用的 pivot 補償,
  (1) repo 既有 7 AC(不動點 / 負對照 / 件真的轉 / identity 介面 / 剛性等距 / 端到端 / curve 容忍)
      全部仍成立;
  (2) 補償後的 skeleton 仍過 **validator_v1 雙真值**(editor 可匯入 0 error + loop 閉合 0 問題)——
      對應 MERGE_PLAN §1 的 **G2**(遊戲能播 **且** 編輯器能匯入);
  (3) 入口 **G1 wired**(apply_g1=False 注入末鍵 curve → validator_v1 抓到 editor-crash)+
      負對照(繞件中心 vs 繞 pivot)證閘**非恆真**。

真值來源 = 真實 Award 機器人拆件世界幾何 + `infer_pivots` 推得的接觸縫肩 pivot(左手繞肩)。

**AC(全部客觀、可機讀;括號為移植的 repo AC)**:
  B3-1 entrypoint+fixed-point : 經 `pivot_rig.apply_joint_pivots`(公開 API),左手繞肩 pivot →
                                補償版 pivot 附著點世界座標殘差 < TOL_FIX(移植 AC1)。
  B3-2 negative-control       : **不補償**(繞件中心 O)→ pivot 位移 ≥ MIN_NEG 且 >> 補償版(移植 AC2)→ 閘非恆真。
  B3-3 moves+rigid            : 件最遠點確有位移 ≥ MIN_MOVE(移植 AC3)且所有件點到 P 距離逐幀不變
                                (剛性/等距,移植 AC5)→ 真繞 P 旋轉、沒凍住件。
  B3-4 identity+curve         : θ=0 幀 Δ=0(移植 AC4,loop 端點/無縫)且 bezier 緩動下殘差仍 < TOL_FIX(移植 AC7)。
  B3-5 end2end+double-truth   : 經入口在**可載入** skeleton(Loop limb rotate)上套補償 →
                                (a) 有限 + loop 端點無縫(移植 AC6 a,b);(b) 生成 loop pivot 殘差 < TOL_FIX(AC6 c);
                                (c) 內建負對照未套用版 pivot 會動(AC6 d);
                                (d) **validator_v1 0 error(editor 可匯入)+ loop 閉合 0 問題**(G2 雙真值);
                                (e) G1 wired:apply_g1=False 注入末鍵 curve → validator_v1 抓到 editor-crash。

用法:
  python3 validate_b3_pivot.py          # 跑 B3-1..B3-5,印精簡 pass/fail
  python3 validate_b3_pivot.py --json   # 完整 JSON 報告

退出碼 0 = 全 AC PASS;非 0 = 有 AC FAIL。
"""
from __future__ import annotations
import argparse
import copy
import json
import math
import os
import re
import subprocess
import sys
import tempfile

import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
_SKILL_ASSETS = os.path.normpath(os.path.join(_HERE, "..", "..", "skills", "spine-ai-editor", "assets"))
sys.path.insert(0, _HERE)
sys.path.insert(0, os.path.join(_HERE, "..", "rig"))
sys.path.insert(0, os.path.join(_HERE, "..", "mesh_gen"))
sys.path.insert(0, _SKILL_ASSETS)
sys.path.insert(0, os.path.join(_SKILL_ASSETS, "gen_lib"))

import spine_anim                          # noqa: E402  repo 動畫 helper(世界座標量測用)
import infer_pivots as ip                  # noqa: E402  真值接觸縫 pivot 推斷
import pivot_rig as PR                     # noqa: E402  B3 結構軸 skill 入口(gen_lib)
from gen_animations import build_animations  # noqa: E402  端到端生成

_VALIDATOR_V1 = os.path.join(_SKILL_ASSETS, "validator_v1.py")

TOL_FIX = 0.5       # px,pivot 不動點幀間最大殘差上限
TOL_RIGID = 0.5     # px,到 P 距離絕對偏差上限(等距)
MIN_NEG = 10.0      # px,負對照(繞件中心)pivot 位移下限
MIN_MOVE = 8.0      # px,件最遠點位移下限
EPS = 1e-6
NEG_RATIO = 20.0    # AC2/AC1 位移比下限


# --------------------------------------------------------------------- 世界座標量測
def _R(deg):
    r = math.radians(deg); c, s = math.cos(r), math.sin(r)
    return np.array([[c, -s], [s, c]])


def _world_of(local, O, rot_frames, tr_frames, t):
    """bone(root 子、setup 旋轉0、scale1)加 rotate/translate 對局部點 local 的世界座標。"""
    ang = spine_anim._interp(rot_frames, t, ["angle"])["angle"]
    xy = spine_anim._interp(tr_frames, t, ["x", "y"]) if tr_frames else {"x": 0.0, "y": 0.0}
    O = np.asarray(O, float)
    return (O + np.array([xy["x"], xy["y"]])) + _R(ang) @ np.asarray(local, float)


def _dense_ts(rot_frames, n=400):
    t0, t1 = rot_frames[0]["time"], rot_frames[-1]["time"]
    return [t0 + (t1 - t0) * i / n for i in range(n + 1)]


def _swing(bezier=False):
    """pure-rotation 擺動 timeline(首尾 identity,峰 24°);bezier=True 加緊湊緩動鍵。"""
    fr = [{"time": 0.0, "angle": 0.0}, {"time": 0.25, "angle": 24.0}, {"time": 0.5, "angle": 0.0}]
    if bezier:
        for f in fr[:-1]:
            f.update({"curve": 0.25, "c2": 0.0, "c3": 0.25, "c4": 1.0})
    return fr


def _load_real():
    """真實 Award 左手件世界輪廓 + 推得肩 pivot。回傳 (pts Nx2, O 件中心, P pivot, fid)。"""
    parts, truth, tree, fid = ip.load_award_robot(use_alpha=True)
    inf = ip.infer_pivots(parts, tree)
    slot = "機器人拆件/左手"
    pts = np.asarray(parts[slot], float)
    O = pts.mean(axis=0)
    P = np.asarray(inf[slot], float)
    return pts, O, P, fid.get(slot, "?")


def _apply_via_entry(O, P, rot_frames):
    """**經 skill 入口** apply_joint_pivots 對單 limb 套補償,回傳補償後 (rotate, translate) 通道。

    把 O/rot_frames 包成最小 skeleton(bone 原點=O),pivot_of={bone:P},走公開 API → 讀回通道。
    """
    skel = {
        "skeleton": {"width": 700, "height": 700},
        "bones": [{"name": "root"},
                  {"name": "b_limb", "parent": "root", "x": float(O[0]), "y": float(O[1])}],
        "slots": [], "skins": {"default": {}},
        "animations": {"A": {"bones": {"b_limb": {"rotate": [dict(f) for f in rot_frames]}}}},
    }
    conv = PR.apply_joint_pivots(skel, {"b_limb": (float(P[0]), float(P[1]))}, mode="rotate")
    ch = skel["animations"]["A"]["bones"]["b_limb"]
    return ch["rotate"], ch["translate"], conv["A"]


# --------------------------------------------------------------------- validator_v1 雙真值
def _run_validator_v1(skel, loop_anim, mutator=None):
    """寫檔 → subprocess 呼叫真正的 validator_v1.py → 解析。回傳 {valid, errors, loop_problems, raw}。"""
    data = copy.deepcopy(skel)
    if mutator is not None:
        mutator(data)
    tmpdir = tempfile.mkdtemp(prefix="b3pivot_")
    jp = os.path.join(tmpdir, "skeleton.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    cmd = [sys.executable, _VALIDATOR_V1, jp, "--metric", "--loop-anims", loop_anim]
    p = subprocess.run(cmd, capture_output=True, text=True)
    errors, loops = [], []
    for line in p.stdout.splitlines():
        s = line.strip()
        if s.startswith("[ERR ]"):
            errors.append(s[len("[ERR ]"):].strip())
        elif s.startswith("[warn] (v1 loop)"):
            loops.append(s[len("[warn] (v1 loop)"):].strip())
    try:
        os.remove(jp); os.rmdir(tmpdir)
    except OSError:
        pass
    return {"valid": p.returncode == 0, "errors": errors, "loop_problems": loops, "raw": p.stdout}


def _loadable_limb_skeleton():
    """可載入 skeleton(bones 帶原點 + slots + default skin region 占位),Loop 給 limb 一條 rotate。

    用 repo build_animations 產 Loop(limb b_左手 得 rotate,body/head 另有通道),slot/attachment
    占位讓 validator_v1 能載入。回傳 (skel, 肩 pivot 字典)。
    """
    bones = [
        {"name": "root"},
        {"name": "b_身體", "parent": "root", "x": 350.0, "y": 350.0},
        {"name": "b_左手", "parent": "root", "x": 250.0, "y": 300.0},
        {"name": "b_頭", "parent": "root", "x": 360.0, "y": 520.0},
    ]
    slots = [{"name": s, "bone": b, "attachment": s} for s, b in
             (("身體", "b_身體"), ("左手", "b_左手"), ("頭", "b_頭"))]
    skin = {s: {s: {"width": 32, "height": 32}} for s in ("身體", "左手", "頭")}
    gen_skel = {"skeleton": {"hash": "b3pivot", "spine": "3.8.75", "x": 0, "y": 0,
                             "width": 700, "height": 700, "images": "./"},
                "bones": bones}
    story = {"beats": [{"beat": "Loop", "parts": [
        {"part": "身體", "role": "body"},
        {"part": "左手", "role": "limb"},
        {"part": "頭", "role": "head"}]}]}
    anims = build_animations(gen_skel, story)
    skel = {"skeleton": gen_skel["skeleton"], "bones": bones, "slots": slots,
            "skins": {"default": skin}, "animations": anims}
    pivots = {"b_左手": (350.0, 350.0), "b_頭": (355.0, 420.0)}   # 肩 / 頸(合成)
    return skel, pivots


def _inject_last_frame_curve(data, aname):
    """把某 bone timeline 末鍵塞 curve(模擬未拔末鍵 → 地雷 #12),供 G1 wired 負對照。"""
    anim = data["animations"][aname]
    for tls in anim.get("bones", {}).values():
        for frames in tls.values():
            if isinstance(frames, list) and len(frames) >= 2 and isinstance(frames[-1], dict):
                frames[-1].update({"curve": 0.25, "c2": 0.0, "c3": 0.75, "c4": 1.0})
                return
    raise RuntimeError("找不到可注入末鍵 curve 的 bone timeline(負對照前提壞了)")


# --------------------------------------------------------------------- AC
def run_all():
    pts, O, P, fid = _load_real()
    armlen = float(np.linalg.norm(O - P))

    # ---- B3-1 / B3-2 / B3-3 / B3-4:經入口對真實左手套補償 ----
    rot_d, tr_d, conv1 = _apply_via_entry(O, P, _swing(bezier=False))
    ell_P = P - O
    ts = _dense_ts(rot_d)
    fix = max(np.linalg.norm(_world_of(ell_P, O, rot_d, tr_d, t) - P) for t in ts)      # AC1
    neg = max(np.linalg.norm(_world_of(ell_P, O, _swing(False), None, t) - P) for t in ts)  # AC2
    far_i = int(np.argmax(np.linalg.norm(pts - P, axis=1)))
    far_local = pts[far_i] - O
    move = max(np.linalg.norm(_world_of(far_local, O, rot_d, tr_d, t) - pts[far_i]) for t in ts)  # AC3
    d0 = np.linalg.norm(pts - P, axis=1)                                                 # AC5 剛性
    worst_abs = 0.0
    for t in ts[::7]:
        for k in range(len(pts)):
            w = _world_of(pts[k] - O, O, rot_d, tr_d, t)
            worst_abs = max(worst_abs, abs(np.linalg.norm(w - P) - d0[k]))
    d_t0 = math.hypot(tr_d[0]["x"], tr_d[0]["y"])                                         # AC4
    d_tN = math.hypot(tr_d[-1]["x"], tr_d[-1]["y"])
    # AC7 bezier
    rot_b, tr_b, _ = _apply_via_entry(O, P, _swing(bezier=True))
    fix_b = max(np.linalg.norm(_world_of(ell_P, O, rot_b, tr_b, t) - P) for t in _dense_ts(rot_b))

    fix, neg, move, worst_abs, fix_b = map(float, (fix, neg, move, worst_abs, fix_b))
    b31 = fix < TOL_FIX and callable(getattr(PR, "apply_joint_pivots", None)) and conv1 == ["b_limb"]
    b32 = (neg >= MIN_NEG) and (neg > fix * NEG_RATIO)
    b33 = move >= MIN_MOVE and worst_abs < TOL_RIGID
    b34 = d_t0 < EPS and d_tN < EPS and fix_b < TOL_FIX

    # ---- B3-5 端到端 + 雙真值 ----
    skel, pivots = _loadable_limb_skeleton()
    loop_raw_rot = [dict(f) for f in skel["animations"]["Loop"]["bones"]["b_左手"]["rotate"]]
    conv5 = PR.apply_joint_pivots(skel, pivots, mode="rotate")         # 經入口,預設 apply_g1=True
    conv_bones = conv5.get("Loop", [])
    # (a) 有限 + loop 無縫
    finite = spine_anim.all_finite(skel["animations"]["Loop"])
    seamless = True
    for b in conv_bones:
        for ch in ("rotate", "translate"):
            fr = skel["animations"]["Loop"]["bones"][b].get(ch)
            if not fr:
                continue
            if ch == "rotate":
                seamless &= abs(fr[0]["angle"] - fr[-1]["angle"]) < 1e-6
            else:
                seamless &= abs(fr[0]["x"] - fr[-1]["x"]) < 1e-6 and abs(fr[0]["y"] - fr[-1]["y"]) < 1e-6
    # (b) 生成 loop pivot 殘差(左手)
    O_lh = np.array([250.0, 300.0]); P_lh = np.array(pivots["b_左手"])
    rr = skel["animations"]["Loop"]["bones"]["b_左手"]["rotate"]
    tt = skel["animations"]["Loop"]["bones"]["b_左手"]["translate"]
    ell = P_lh - O_lh
    fix_e = float(max(np.linalg.norm(_world_of(ell, O_lh, rr, tt, t) - P_lh) for t in _dense_ts(rr)))
    # (c) 內建負對照:未套用(繞件中心)pivot 位移
    neg_e = float(max(np.linalg.norm(_world_of(ell, O_lh, loop_raw_rot, None, t) - P_lh) for t in _dense_ts(rr)))
    # (d) validator_v1 雙真值(editor 可匯入 + loop 閉合)
    v1 = _run_validator_v1(skel, "Loop")
    editor_ok = v1["valid"] and len(v1["errors"]) == 0
    loop_ok = len(v1["loop_problems"]) == 0
    # (e) G1 wired:apply_g1=False 生成後注入末鍵 curve → validator_v1 抓到 editor-crash
    skel_raw, pivots_raw = _loadable_limb_skeleton()
    PR.apply_joint_pivots(skel_raw, pivots_raw, mode="rotate", apply_g1=False)
    neg_curve = _run_validator_v1(skel_raw, "Loop",
                                  mutator=lambda d: _inject_last_frame_curve(d, "Loop"))
    curve_caught = (not neg_curve["valid"]) and any(
        ("最後一鍵帶 curve" in e) or ("AIOOBE" in e) for e in neg_curve["errors"])

    b35 = (finite and seamless and (fix_e < TOL_FIX)
           and (neg_e > fix_e * NEG_RATIO) and (neg_e >= 1.0)
           and editor_ok and loop_ok and curve_caught)

    res = {
        "B3-1_entrypoint_fixed_point": (b31, {
            "public_api_callable": callable(getattr(PR, "apply_joint_pivots", None)),
            "converted": conv1, "pivot_residual_px": round(fix, 4),
            "O": [round(float(O[0]), 1), round(float(O[1]), 1)],
            "P": [round(float(P[0]), 1), round(float(P[1]), 1)], "armlen_px": round(armlen, 1),
            "fid": fid}),
        "B3-2_negative_control": (b32, {
            "neg_center_disp_px": round(neg, 2), "fix_px": round(fix, 4),
            "ratio": round(neg / max(fix, 1e-9), 1)}),
        "B3-3_moves_and_rigid": (b33, {
            "far_point_move_px": round(move, 2), "rigidity_abs_dev_px": round(worst_abs, 4)}),
        "B3-4_identity_and_curve": (b34, {
            "delta_t0_px": d_t0, "delta_tN_px": d_tN, "bezier_residual_px": round(fix_b, 4)}),
        "B3-5_end2end_double_truth": (b35, {
            "converted_bones": conv_bones, "finite": finite, "loop_seamless": seamless,
            "gen_loop_pivot_residual_px": round(fix_e, 4),
            "neg_unapplied_disp_px": round(neg_e, 2),
            "validator_v1_editor_importable": editor_ok, "validator_v1_errors": v1["errors"][:2],
            "validator_v1_loop_closed": loop_ok, "loop_problems": v1["loop_problems"][:2],
            "g1_wired_neg_curve_caught": curve_caught, "neg_curve_errors": neg_curve["errors"][:2]}),
    }
    res = {k: (bool(v[0]), v[1]) for k, v in res.items()}
    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "B3 pivot_rig: joint-pivot compensation skill entry → 7AC ported + validator_v1 double-truth",
        "entry": "skills/spine-ai-editor/assets/gen_lib/pivot_rig.py :: apply_joint_pivots",
        "truth": "real Award robot 左手 + infer_pivots 肩 pivot; |O-P|={:.1f}px".format(armlen),
        "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="完整 JSON 報告")
    a = ap.parse_args()
    report = run_all()
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"overall_pass": report["overall_pass"], "entry": report["entry"],
                          "truth": report["truth"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
