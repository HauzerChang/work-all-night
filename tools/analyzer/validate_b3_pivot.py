#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B3 閘 — `gen_lib` 繞關節 pivot 變換入口(spine-ai-editor 2.0 Phase B3)。

B3 把 repo 的 pivot 補償引擎(`tools/analyzer/pivot_rotation.py`,Δ=(M−I)(O−P))包成
**skill 層級的結構軸入口** `skills/spine-ai-editor/assets/gen_lib/pivot_about.py`
(`apply_pivot_about` / `generate_bigwin_about_pivots`),併進 references/structural_expansion.md
的「繞關節 pivot 的 keyframe 級變換」SOP(SOP A/B 動骨架 vs 本法不動骨架的互補解)。

本閘 = **移植 repo 既有 7AC**(`validate_pivot_rotation.py`)**改經公開入口跑**,
**另加 B1/B2 的 G2 雙真值紀律**:證明 pivot 補償後(密網格 rotate/scale/translate 鍵)的輸出
仍過使用者既有 skill 的**編輯器真值閘** `validator_v1`(0 error + loop 閉合 0)——
即件繞 pivot 變換後「遊戲能播 **且** 編輯器能匯入」。repo 原閘只做純 Python 模擬,**未**驗 editor/loop。

真值幾何 = 真實 Award 機器人左手拆件世界輪廓 + `infer_pivots` 推得的接觸縫肩 pivot。

AC(全部客觀、可機讀;括號為對應 repo validate_pivot_rotation.py 的 AC):
  B3-1 fixed-point     (AC1): 經入口補償後,pivot 附著點世界座標 == P(幀間最大殘差 < TOL_FIX)。
  B3-2 neg-control     (AC2): **不補償**(繞件中心 O)時 pivot 明顯位移(>> B3-1 且 ≥ MIN_NEG)→ 閘非恆真。
  B3-3 part-moves      (AC3): 離 P 最遠的件點確有位移(≥ MIN_MOVE)→ 沒把件凍住。
  B3-4 identity-iface  (AC4): θ=0 幀 Δ=0(< EPS)→ setup/loop 端點/In-Out 介面保持 identity。
  B3-5 rigid-isometry  (AC5): 所有件點到 P 的距離逐幀不變(絕對偏差 < TOL_RIGID)→ 真繞 P 旋轉。
  B3-6 curve-tolerance (AC7): rotate 帶緊湊 bezier 緩動時 B3-1 仍成立(加密重取樣正確處理 curve)。
  B3-7 end2end+G2      (AC6+): 經 **B2 gen_lib `generate_bigwin`** 產 cascade beat(效果骨帶 rotate+scale)
                       → 經 **B3 入口** `apply_pivot_about(include_scale=True)` 繞合成關節 pivot →
                       (a) 通道有限、時間嚴格遞增;(b) loop 端點相等(無縫保持);
                       (c) 生成 loop 上 pivot 不動(< TOL_FIX);(d) 內建負對照(未補償)pivot 會動;
                       (e) **G2 編輯器真值**:pivot 補償後整份 skeleton 過 `validator_v1`
                           **0 error + loop 閉合 0**(密 rotate/scale/translate 鍵仍 editor 可匯入 + loop 閉合)。

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

import spine_anim                     # noqa: E402
import infer_pivots as ip            # noqa: E402  真值 pivot 推斷
import make_beat as MB               # noqa: E402  B2 gen_lib 入口
import pivot_about as PA             # noqa: E402  B3 gen_lib 入口(受測主體)

_VALIDATOR_V1 = os.path.join(_SKILL_ASSETS, "validator_v1.py")

TOL_FIX = 0.5       # px,pivot 不動點幀間最大殘差上限
TOL_RIGID = 0.5     # px,到 P 距離絕對偏差上限
MIN_NEG = 10.0      # px,負對照(繞件中心)pivot 位移下限
MIN_MOVE = 8.0      # px,件最遠點位移下限
EPS = 1e-6
NEG_RATIO = 20.0    # 負對照/補償 位移比下限


# ------------------------------------------------------------- 純 Python 世界變換模擬
def _R(deg):
    r = math.radians(deg); c, s = math.cos(r), math.sin(r)
    return np.array([[c, -s], [s, c]])


def _world_rot(local, O, rot_frames, tr_frames, t):
    """bone(root 子、setup 旋轉0、scale1)加 rotate/translate 對局部點 local 的世界座標(純旋轉模式)。"""
    ang = spine_anim._interp(rot_frames, t, ["angle"])["angle"]
    xy = spine_anim._interp(tr_frames, t, ["x", "y"]) if tr_frames else {"x": 0.0, "y": 0.0}
    O = np.asarray(O, float)
    return (O + np.array([xy["x"], xy["y"]])) + _R(ang) @ np.asarray(local, float)


def _world_srt(local, O, rot_frames, sc_frames, tr_frames, t):
    """含 scale 的世界變換:M = R(θ)·diag(sx,sy)(Spine TRS),world = O + T + M·local。"""
    ang = spine_anim._interp(rot_frames, t, ["angle"])["angle"] if rot_frames else 0.0
    sx, sy = (1.0, 1.0)
    if sc_frames:
        d = spine_anim._interp(sc_frames, t, ["x", "y"]); sx, sy = d["x"], d["y"]
    xy = spine_anim._interp(tr_frames, t, ["x", "y"]) if tr_frames else {"x": 0.0, "y": 0.0}
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    M = np.array([[c * sx, -s * sy], [s * sx, c * sy]])
    O = np.asarray(O, float)
    return (O + np.array([xy["x"], xy["y"]])) + M @ np.asarray(local, float)


def _dense_ts(frames, n=400):
    t0, t1 = frames[0]["time"], frames[-1]["time"]
    return [t0 + (t1 - t0) * i / n for i in range(n + 1)]


def _swing(bezier=False):
    """pure-rotation 擺動 timeline(首尾 identity,峰 24°)。bezier=True 加緊湊緩動鍵。"""
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
    O = pts.mean(axis=0)                 # 非 rig 下 bone 落件中心
    P = np.asarray(inf[slot], float)     # 接觸縫肩 pivot
    return pts, O, P, fid.get(slot, "?")


def _convert_via_entry(rot_frames, O, P):
    """**經公開入口 B3** `apply_pivot_about`(單支 anim 模式)把一條 rotate timeline 轉成繞 pivot 版。
    回傳 (rot_dense, tr_dense, report)。這是閘「驗的是入口」而非直呼 repo 底層的關鍵。"""
    anim = {"bones": {"b_hand": {"rotate": [dict(f) for f in rot_frames]}}}
    report = PA.apply_pivot_about(anim, pivot_of={"b_hand": (float(P[0]), float(P[1]))},
                                  bone_origin={"b_hand": (float(O[0]), float(O[1]))},
                                  include_scale=False)
    ch = anim["bones"]["b_hand"]
    return ch["rotate"], ch["translate"], report


# ------------------------------------------------------------- validator_v1(G2 editor 真值)
def _run_validator_v1(skel, loop_anim, mutator=None):
    """寫檔 → subprocess 呼叫真正的 validator_v1.py → 解析。回傳 {valid,errors,loop_problems,raw}。"""
    data = copy.deepcopy(skel)
    if mutator is not None:
        mutator(data)
    tmpdir = tempfile.mkdtemp(prefix="b3pivot_")
    jp = os.path.join(tmpdir, "skeleton.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    cmd = [sys.executable, _VALIDATOR_V1, jp, "--loop-anims", loop_anim]
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


# ------------------------------------------------------------- AC
def _py(o):
    """把 numpy 標量/容器遞迴轉成原生 Python 型別(供 json.dumps / 布林判斷)。"""
    if isinstance(o, dict):
        return {k: _py(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_py(v) for v in o]
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    return o


def run_all():
    pts, O, P, fid = _load_real()
    armlen = float(np.linalg.norm(O - P))

    # ---- B3-1..B3-5(linear swing,經入口)----
    rot_d, tr_d, rep_lin = _convert_via_entry(_swing(False), O, P)
    ell_P = P - O
    ts = _dense_ts(rot_d)
    fix = max(np.linalg.norm(_world_rot(ell_P, O, rot_d, tr_d, t) - P) for t in ts)
    neg = max(np.linalg.norm(_world_rot(ell_P, O, _swing(False), None, t) - P) for t in ts)
    far_i = int(np.argmax(np.linalg.norm(pts - P, axis=1)))
    far_local = pts[far_i] - O
    move = max(np.linalg.norm(_world_rot(far_local, O, rot_d, tr_d, t) - pts[far_i]) for t in ts)
    d0 = np.linalg.norm(pts - P, axis=1)
    rigid = 0.0
    for t in ts[::7]:
        for k in range(len(pts)):
            w = _world_rot(pts[k] - O, O, rot_d, tr_d, t)
            rigid = max(rigid, abs(np.linalg.norm(w - P) - d0[k]))
    d_t0 = math.hypot(tr_d[0]["x"], tr_d[0]["y"])
    d_tN = math.hypot(tr_d[-1]["x"], tr_d[-1]["y"])

    entry_used = (rep_lin.get("mode") == "anim" and rep_lin.get("converted") == ["b_hand"])
    b31 = (fix < TOL_FIX) and entry_used
    b32 = (neg >= MIN_NEG) and (neg > fix * NEG_RATIO)
    b33 = move >= MIN_MOVE
    b34 = d_t0 < EPS and d_tN < EPS
    b35 = rigid < TOL_RIGID

    # ---- B3-6(bezier ease,經入口)----
    rot_b, tr_b, _ = _convert_via_entry(_swing(True), O, P)
    tsb = _dense_ts(rot_b)
    fix_b = max(np.linalg.norm(_world_rot(ell_P, O, rot_b, tr_b, t) - P) for t in tsb)
    b36 = fix_b < TOL_FIX

    # ---- B3-7 end-to-end:B2 gen_lib 生成 → B3 入口繞 pivot(include_scale)→ G2 editor 真值 ----
    skel, aname = MB.generate_bigwin(MB.DEMO_PARTS, beat="cascade")
    # 效果骨 b_光暈 既有 rotate+scale(pop 脈衝);給它一個合成關節 pivot(件中心外一點)
    fx_bone = "b_光暈"
    O_fx = next((float(b.get("x", 0.0)), float(b.get("y", 0.0)))
                for b in skel["bones"] if b["name"] == fx_bone)
    O_fx = np.array(O_fx, float)
    P_fx = O_fx + np.array([0.0, 90.0])   # 關節在件上方 90px(合成,驗機制)
    # 負對照用:補償前先存一份原始 rotate/scale
    raw_fx = copy.deepcopy(skel["animations"][aname]["bones"][fx_bone])
    rep_e2e = PA.apply_pivot_about(skel, pivot_of={fx_bone: (float(P_fx[0]), float(P_fx[1]))},
                                   include_scale=True, anims=[aname])
    chfx = skel["animations"][aname]["bones"][fx_bone]
    conv_bones = rep_e2e["converted"].get(aname, [])

    # (a) finite + 時間嚴格遞增
    finite = spine_anim.all_finite(skel["animations"][aname])
    # (b) loop 端點相等(無縫)
    seamless = True
    for ch in ("rotate", "scale", "translate"):
        fr = chfx.get(ch)
        if not fr:
            continue
        keys = [k for k in fr[0].keys() if k != "time"]
        for kk in keys:
            seamless &= abs(fr[0].get(kk, 0.0) - fr[-1].get(kk, 0.0)) < 1e-5
    # (c) 生成 loop 上 pivot 不動(含 scale)
    ell_fx = P_fx - O_fx
    tse = _dense_ts(chfx["rotate"])
    fix_e = max(np.linalg.norm(
        _world_srt(ell_fx, O_fx, chfx.get("rotate"), chfx.get("scale"), chfx.get("translate"), t) - P_fx)
        for t in tse)
    # (d) 負對照:未補償(繞件中心,R·S about O)pivot 位移
    neg_e = max(np.linalg.norm(
        _world_srt(ell_fx, O_fx, raw_fx.get("rotate"), raw_fx.get("scale"), None, t) - P_fx)
        for t in tse)
    # (e) G2 editor 真值:pivot 補償後整份 skeleton 過 validator_v1(0 error + loop 閉合 0)
    v1 = _run_validator_v1(skel, aname)
    g2_ok = v1["valid"] and len(v1["errors"]) == 0 and len(v1["loop_problems"]) == 0

    b37 = (finite and seamless and (fix_e < TOL_FIX)
           and (neg_e > fix_e * NEG_RATIO) and (neg_e >= MIN_MOVE) and g2_ok
           and conv_bones == [fx_bone])

    res = {
        "B3-1_fixed_point": (b31, {"pivot_residual_px": round(fix, 4), "tol": TOL_FIX,
                                   "entry_mode": rep_lin.get("mode"), "converted": rep_lin.get("converted")}),
        "B3-2_neg_control": (b32, {"uncompensated_drift_px": round(neg, 2), "min": MIN_NEG,
                                   "ratio_vs_fixed": round(neg / max(fix, 1e-9), 1)}),
        "B3-3_part_moves": (b33, {"farthest_move_px": round(move, 2), "min": MIN_MOVE}),
        "B3-4_identity_interface": (b34, {"delta_t0_px": d_t0, "delta_tN_px": d_tN, "eps": EPS}),
        "B3-5_rigid_isometry": (b35, {"max_dist_to_P_dev_px": round(rigid, 4), "tol": TOL_RIGID}),
        "B3-6_curve_tolerance": (b36, {"bezier_pivot_residual_px": round(fix_b, 4), "tol": TOL_FIX}),
        "B3-7_end2end_g2": (b37, {
            "via": "gen_lib.generate_bigwin(cascade) -> pivot_about.apply_pivot_about(include_scale)",
            "effect_bone": fx_bone, "converted": conv_bones,
            "finite": finite, "loop_seamless": seamless,
            "gen_loop_pivot_residual_px": round(fix_e, 4),
            "neg_uncompensated_drift_px": round(neg_e, 2),
            "g2_validator_v1_valid": v1["valid"], "g2_errors": v1["errors"][:3],
            "g2_loop_problems": v1["loop_problems"][:3]}),
    }
    overall = bool(all(bool(v[0]) for v in res.values()))
    return _py({
        "overall_pass": overall,
        "chunk": "B3 繞關節 pivot 變換: pivot_about entry (Δ=(M−I)(O−P)) → repo 7AC 移植 + G2 editor 真值",
        "entry": "skills/spine-ai-editor/assets/gen_lib/pivot_about.py :: apply_pivot_about / generate_bigwin_about_pivots",
        "truth": {"part": f"機器人拆件/左手 [{fid}]", "verts": len(pts),
                  "O": [round(float(O[0]), 1), round(float(O[1]), 1)],
                  "P": [round(float(P[0]), 1), round(float(P[1]), 1)], "armlen_px": round(armlen, 1)},
        "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()},
    })


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
