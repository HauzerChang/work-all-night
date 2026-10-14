#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B3 閘 — 繞關節 pivot 變換併進**結構軸 skill 入口**(spine-ai-editor 2.0 Phase B3)。

B1/B2 把 repo 的大獎節拍生成包成 `gen_lib` 入口並過 v1.3.0 `validator_v1`(雙真值)。
B3 把 repo 的 `pivot_rotation`(`Δ=(M−I)(O−P)`,件繞關節 pivot 而非件中心)併成 `gen_lib`
的**公開結構軸入口** `apply_pivot_rotation`,並把 repo 既有的 7 條 pivot AC **移植**到「經 skill 入口」
的版本,外加 **G2 雙真值**(套 pivot 後 validator_v1 仍乾淨=editor 匯入不破)。

**驗的是什麼(為何這個 chunk 有價值)**:
  `references/structural_expansion.md` 原本只有「加 bone / reparent」的結構擴充。但「手臂該繞肩、
  頭該繞頸」常不必動骨架——`pivot_rotation` 給了 keyframe 級互補解。B3 把它固化成對外契約
  `apply_pivot_rotation(skel, pivots)`,並機械化證明:① pivot 真的成不動點;② 不補償(繞件中心)
  會明顯位移(閘非恆真);③ 套用後仍過 editor 真值閘(無縫 identity 不破、loop 閉合、0 error)。

**AC(全部客觀、可機讀;真值=真實 Award 機器人左手 + infer_pivots 推得肩 pivot)**:
  B3-1 entrypoint+fixed-point : `gen_lib.apply_pivot_rotation`(**公開 API**)對含 limb rotate 的動畫
                                → 肩 pivot P 的附著點世界座標固定(密網格幀間最大殘差 < TOL_FIX)。
  B3-2 neg-ctrl(繞件中心)    : **不補償**(繞件中心 O)時同一 P 明顯位移(>> B3-1 且 ≥ MIN_NEG)→ 閘非恆真。
  B3-3 part-moves             : 離 P 最遠的件點確有位移(≥ MIN_MOVE)→ 沒把件凍住。
  B3-4 identity-interface     : θ=0 幀 Δ=0(< EPS)→ setup/loop 端點/In-Out 介面保持 identity。
  B3-5 rigidity(等距)        : 純旋轉 pivot 下所有件點到 P 距離逐幀不變(絕對偏差 < TOL_RIGID)。
  B3-6 end2end+G2             : 經 `generate_bigwin` 產大獎 beat → `apply_pivot_rotation`(含 scale)→
                                (a) 有限+時間嚴格遞增;(b) loop 端點相等(無縫);(c) 生成 beat 上 pivot 不動;
                                (d) 內建負對照(未套用會動);(e) **validator_v1 0 error + loop 閉合**(editor 可匯入)。
  B3-7 curve-tolerance        : rotate 帶緊湊 bezier 緩動時 B3-1 仍成立(加密重取樣正確處理 curve)。

用法:
  python3 validate_b3_pivot.py          # 跑 B3-1..B3-7,印精簡 pass/fail
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

import spine_anim                      # noqa: E402
import pivot_rotation as pr            # noqa: E402  (只為 transform_matrix_full 幾何量測,非生成)
import validate_pivot_rotation as vpr  # noqa: E402  複用真值載入 / 幾何量測 helper
import make_beat as MB                 # noqa: E402  B3 skill 入口(gen_lib)

_VALIDATOR_V1 = os.path.join(_SKILL_ASSETS, "validator_v1.py")

TOL_FIX = 0.5      # px,pivot 不動點幀間最大殘差上限
TOL_RIGID = 0.5    # px,到 P 距離絕對偏差上限(等距)
MIN_NEG = 10.0     # px,負對照(繞件中心)位移下限
MIN_MOVE = 8.0     # px,件最遠點位移下限
EPS = 1e-6
NEG_RATIO = 20.0   # neg/fix 位移比下限


# ----------------------------------------------------------------- 世界變換量測(一般仿射)
def _world_affine(local, O, chans, t):
    """bone(root 子、setup 中性)在時間 t 對局部點 local 的世界座標。
    chans 為 anim["bones"][bone] dict(可含 rotate/scale/shear/translate,皆缺席→中性)。
    M = pr.transform_matrix_full(θ,sx,sy,shx,shy);world = (O + translate) + M·local。"""
    ang = spine_anim._interp(chans["rotate"], t, ["angle"])["angle"] if chans.get("rotate") else 0.0
    if chans.get("scale"):
        d = spine_anim._interp(chans["scale"], t, ["x", "y"]); sx, sy = d["x"], d["y"]
    else:
        sx, sy = 1.0, 1.0
    if chans.get("shear"):
        d = spine_anim._interp(chans["shear"], t, ["x", "y"]); shx, shy = d["x"], d["y"]
    else:
        shx, shy = 0.0, 0.0
    if chans.get("translate"):
        d = spine_anim._interp(chans["translate"], t, ["x", "y"]); tx, ty = d["x"], d["y"]
    else:
        tx, ty = 0.0, 0.0
    a, b, c, dd = pr.transform_matrix_full(ang, sx, sy, shx, shy)
    O = np.asarray(O, float); loc = np.asarray(local, float)
    wx = (O[0] + tx) + a * loc[0] + b * loc[1]
    wy = (O[1] + ty) + c * loc[0] + dd * loc[1]
    return np.array([wx, wy])


def _dense_ts(frames, n=400):
    t0, t1 = frames[0]["time"], frames[-1]["time"]
    return [t0 + (t1 - t0) * i / n for i in range(n + 1)]


# ----------------------------------------------------------------- 真實左手:經 skill 入口量測
def _real_limb_skel(O, rot_frames, bone="b_左手", part="左手"):
    """組一份最小 skeleton:單一 limb bone(setup 原點 O)+ 一支 rotate swing 動畫。
    供 skill 入口 `apply_pivot_rotation` 消費(件繞肩 pivot)。"""
    return {
        "skeleton": {"hash": "b3", "spine": "3.8.75", "width": 700, "height": 700, "images": "./"},
        "bones": [{"name": "root"},
                  {"name": bone, "parent": "root", "x": float(O[0]), "y": float(O[1])}],
        "slots": [{"name": part, "bone": bone, "attachment": part}],
        "skins": {"default": {part: {part: {"width": 32, "height": 32}}}},
        "animations": {"swing": {"bones": {bone: {"rotate": [dict(f) for f in rot_frames]}}}},
    }


def _real_metrics(pts, O, P, rot_frames, bone="b_左手", part="左手"):
    """經 skill 入口 `apply_pivot_rotation` 套 pivot,回傳 B3-1..B3-5/B3-7 量測。"""
    skel = _real_limb_skel(O, rot_frames, bone=bone, part=part)
    # 件名(slot)鍵 → 證入口鍵解析能映射件名到 bone
    MB.apply_pivot_rotation(skel, {part: (float(P[0]), float(P[1]))})
    chans = skel["animations"]["swing"]["bones"][bone]
    ell_P = np.asarray(P, float) - np.asarray(O, float)
    ts = _dense_ts(chans["rotate"])
    # B3-1 補償版 pivot 殘差
    fix = max(float(np.linalg.norm(_world_affine(ell_P, O, chans, t) - P)) for t in ts)
    # B3-2 負對照:繞件中心(只有原 rotate、無 translate)
    raw = {"rotate": rot_frames}
    neg = max(float(np.linalg.norm(_world_affine(ell_P, O, raw, t) - P)) for t in ts)
    # B3-3 件最遠點位移(補償版,相對 setup)
    far_i = int(np.argmax(np.linalg.norm(pts - P, axis=1)))
    far_local = pts[far_i] - O
    far_setup = pts[far_i]
    move = max(float(np.linalg.norm(_world_affine(far_local, O, chans, t) - far_setup)) for t in ts)
    # B3-5 剛性(等距):所有件點到 P 距離逐幀絕對偏差
    d0 = np.linalg.norm(pts - P, axis=1)
    worst_abs = 0.0
    for t in ts[::7]:
        for k in range(len(pts)):
            w = _world_affine(pts[k] - O, O, chans, t)
            worst_abs = max(worst_abs, abs(float(np.linalg.norm(w - P)) - d0[k]))
    # B3-4 identity:θ=0 幀 Δ
    tr = chans["translate"]
    d_t0 = math.hypot(tr[0]["x"], tr[0]["y"]); d_tN = math.hypot(tr[-1]["x"], tr[-1]["y"])
    return dict(fix=fix, neg=neg, move=move, rigid=worst_abs, d0=d_t0, dN=d_tN,
                nkeys=len(chans["rotate"]))


# ----------------------------------------------------------------- validator_v1(G2)
def _run_validator_v1(skel, loop_anim):
    data = copy.deepcopy(skel)
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


# ----------------------------------------------------------------- B3-6 端到端(gen_lib beat)
def _end2end_genlib():
    """generate_bigwin 產 cascade beat(scale pop)→ apply_pivot_rotation(含 scale)→
    對一件(肢體)設肩 pivot,驗 pivot 不動 + 負對照 + validator_v1 乾淨。"""
    part = "arm_L"
    bone = "b_" + MB.generate_bigwin.__globals__["_wire_repo_tools"]()[0].safe(part)
    skel, aname = MB.generate_bigwin(MB.DEMO_PARTS, beat="cascade")
    bo = MB._bone_origin_from_skel(skel)
    O = np.asarray(bo[bone], float)
    P = O + np.array([0.0, 150.0])            # 肩位(合成):件原點上方 150px
    # 未套用版(負對照)快照該件通道
    raw_chans = copy.deepcopy(skel["animations"][aname]["bones"].get(bone, {}))
    skel2 = copy.deepcopy(skel)
    MB.apply_pivot_rotation(skel2, {part: (float(P[0]), float(P[1]))}, include_scale=True)
    chans = skel2["animations"][aname]["bones"][bone]
    ell = P - O
    ts = _dense_ts(chans.get("scale") or chans.get("rotate") or chans["translate"])
    # (a) finite + 時間嚴格遞增
    finite = spine_anim.all_finite(skel2["animations"][aname])
    # (b) loop 無縫:轉換 bone 各通道端點相等
    seamless = True
    for ch in ("rotate", "scale", "shear", "translate"):
        fr = chans.get(ch)
        if not fr:
            continue
        keys = [k for k in fr[0].keys() if k != "time"]
        for k in keys:
            seamless &= abs(fr[0][k] - fr[-1][k]) < 1e-4
    # (c) pivot 不動(含 scale 的 scale-about-pivot)
    fix_e = max(float(np.linalg.norm(_world_affine(ell, O, chans, t) - P)) for t in ts)
    # (d) 負對照:未套用(繞件中心 scale)→ pivot 位移
    neg_e = max(float(np.linalg.norm(_world_affine(ell, O, raw_chans, t) - P)) for t in ts) \
        if raw_chans else 0.0
    # (e) G2 雙真值:套 pivot 後 validator_v1 仍乾淨
    v1 = _run_validator_v1(skel2, aname)
    return dict(bone=bone, finite=bool(finite), seamless=bool(seamless), fix=fix_e, neg=neg_e,
                v1_valid=v1["valid"], v1_errors=v1["errors"], v1_loops=v1["loop_problems"])


# ----------------------------------------------------------------- 主流程
def run_all():
    pts, O, P, fid = vpr._load_real()
    armlen = float(np.linalg.norm(np.asarray(O) - np.asarray(P)))

    m = _real_metrics(pts, O, P, vpr._swing(bezier=False))
    b31 = bool(m["fix"] < TOL_FIX and callable(getattr(MB, "apply_pivot_rotation", None)))
    b32 = bool((m["neg"] >= MIN_NEG) and (m["neg"] > m["fix"] * NEG_RATIO))
    b33 = bool(m["move"] >= MIN_MOVE)
    b34 = bool(m["d0"] < EPS and m["dN"] < EPS)
    b35 = bool(m["rigid"] < TOL_RIGID)

    mb = _real_metrics(pts, O, P, vpr._swing(bezier=True))
    b37 = bool(mb["fix"] < TOL_FIX)

    e = _end2end_genlib()
    b36 = bool(e["finite"] and e["seamless"] and e["fix"] < TOL_FIX
               and e["neg"] > e["fix"] * NEG_RATIO and e["neg"] >= 1.0
               and e["v1_valid"] and len(e["v1_errors"]) == 0 and len(e["v1_loops"]) == 0)

    res = {
        "B3-1_entrypoint_fixed_point": (b31, {
            "public_api_callable": callable(getattr(MB, "apply_pivot_rotation", None)),
            "fix_residual_px": round(m["fix"], 4), "dense_keys": m["nkeys"]}),
        "B3-2_negctrl_part_center": (b32, {
            "neg_px": round(m["neg"], 2), "fix_px": round(m["fix"], 4),
            "ratio": round(m["neg"] / max(m["fix"], 1e-9), 1)}),
        "B3-3_part_moves": (b33, {"far_move_px": round(m["move"], 2)}),
        "B3-4_identity_interface": (b34, {"delta_t0_px": m["d0"], "delta_tN_px": m["dN"]}),
        "B3-5_rigidity_isometry": (b35, {"worst_abs_dev_px": round(m["rigid"], 4)}),
        "B3-6_end2end_genlib_dual_truth": (b36, {
            "bone": e["bone"], "finite": e["finite"], "seamless": e["seamless"],
            "gen_pivot_fix_px": round(e["fix"], 4), "gen_negctrl_px": round(e["neg"], 2),
            "validator_v1_valid": e["v1_valid"], "v1_errors": e["v1_errors"][:2],
            "v1_loop_problems": e["v1_loops"][:2]}),
        "B3-7_curve_tolerance": (b37, {"fix_residual_px": round(mb["fix"], 4)}),
    }
    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "B3 pivot: pivot_rotation → gen_lib structural-axis entry (apply_pivot_rotation) + G2",
        "entry": "skills/spine-ai-editor/assets/gen_lib/make_beat.py :: apply_pivot_rotation",
        "truth": {"limb": fid, "O": [round(float(O[0]), 1), round(float(O[1]), 1)],
                  "P_shoulder": [round(float(P[0]), 1), round(float(P[1]), 1)],
                  "arm_len_px": round(armlen, 1)},
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
        print(json.dumps({"overall_pass": report["overall_pass"], "truth": report["truth"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
