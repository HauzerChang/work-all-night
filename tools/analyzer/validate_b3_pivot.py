#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B3 閘 — `gen_lib` 繞關節 pivot 變換入口(結構軸)→ 幾何真值 + v1.3.0 `validator_v1`(雙真值)。

MERGE_PLAN_2.0 **Phase B3**(承 B1 橋接閘 / B2 生成庫入口):把 repo 的 `pivot_rotation.py`
(`Δ=(M−I)(O−P)`,繞任意點旋轉/縮放/剪切的確定性分解)併成 skill 層級入口
`skills/spine-ai-editor/assets/gen_lib/pivot_axis.py :: apply_joint_pivots`,補 `references/structural_expansion.md`
的 **SOP E(keyframe 級繞關節,不動骨架)**。

**驗的是什麼(為何這個 chunk 有價值)**:
  repo 既有 `validate_pivot_rotation.py` 已以 **7 AC** 對真實 Award 幾何證明「件繞關節 pivot 轉」正確;
  B3 把那條能力**抽成可重用的 skill 入口**(作用在 gen_lib 生成的動畫上,不只臨時腳本),
  並**新增 B1/B2 的雙真值紀律(G2)**:補償後的動畫不只幾何對,還要過 `validator_v1`——
  **editor 可匯入(密網格重取樣=純線性鍵,無末鍵 curve 地雷 #12)+ loop 閉合**。
  Cocos/viewer 實機載入 = 使用者端(排程 scope 邊界),本閘用 spine-webgl 無頭等價(validator_v1)替代。

**AC(全部客觀、可機讀;括號內為 repo 7 AC 的對映)**:
  B3-1 entry+double-truth : `apply_joint_pivots` 是可呼叫公開 API;作用在 **gen_lib idle beat**(limb 走 rotate →
                            繞肩旋轉)後,被轉 bone **恰為**給了 pivot 的 limb,且轉後 skel 過 `validator_v1`
                            **0 error**(含末鍵 curve 檢查 → 密網格重取樣 editor-safe)。(新增:G2 雙真值)
  B3-2 fixed-point        : 經入口對**真實 Award 左手→肩 pivot** 補償後,pivot 附著點世界座標 == P
                            (密網格最大殘差 < TOL_FIX)。(repo AC1)
  B3-3 negctrl+rigid+move : 不補償(繞件中心 O)時 pivot 明顯位移(≥ MIN_NEG 且 >> B3-2);件最遠點確有位移
                            (≥ MIN_MOVE,沒凍住);補償版所有件點到 P 距離逐幀不變(剛性 < TOL_RIGID)。
                            (repo AC2 / AC3 / AC5)
  B3-4 identity+loop      : θ=0 幀 Δ=0(< EPS)→ setup/loop 端點無縫;轉後 idle 動畫 rotate/translate 首尾相等
                            → `validator_v1` **loop 閉合 0 問題**。(repo AC4 + G1/loop 雙真值)
  B3-5 scale-pivot+curve+guard : (a) 對 **B2 大獎 pop beat** 的 scale bone 用 include_scale=True →
                            件**繞 pivot 縮放**(ℓ_P 世界固定在 P + 非 pivot 點確有位移)→ 接回 B2;
                            (b) rotate 帶緊湊 bezier 緩動時 B3-2 仍成立(密網格正確處理 curve,repo AC7);
                            (c) 守衛:pivot≈件原點(<0.5px)→ 該 bone 跳過不加多餘 translate、未知 bone 的 pivot 被忽略。

用法:
  python3 validate_b3_pivot.py            # 跑 B3-1..B3-5,印精簡 pass/fail + 關鍵量值
  python3 validate_b3_pivot.py --json     # 完整 JSON 報告

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

import spine_anim                    # noqa: E402  repo 取樣器
import infer_pivots as ip           # noqa: E402  S5 接觸縫 pivot(真值)
import make_beat as MB              # noqa: E402  B2/B3 生成入口(gen_lib)
import pivot_axis as PA             # noqa: E402  B3 繞關節 pivot 變換入口(gen_lib)

_VALIDATOR_V1 = os.path.join(_SKILL_ASSETS, "validator_v1.py")

TOL_FIX = 0.5       # px,pivot 不動點幀間最大殘差上限
TOL_RIGID = 0.5     # px,到 P 距離絕對偏差上限(等距 → 幀間殘差量級)
MIN_NEG = 8.0       # px,負對照(繞件中心)pivot 位移下限
MIN_MOVE = 8.0      # px,件最遠點位移下限(證有轉)
EPS = 1e-6
NEG_RATIO = 20.0    # 負對照/補償 位移比下限


# ----------------------------------------------------------------- 幾何模擬
def _R(deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return np.array([[c, -s], [s, c]])


def _M(deg, sx=1.0, sy=1.0):
    return _R(deg) @ np.diag([sx, sy])


def _world(local, O, rot_frames, tr_frames, t, scale_frames=None):
    """bone(root 子、setup 旋轉0)加 rotate(/scale)+ translate 對局部點 local 的世界座標。"""
    ang = spine_anim._interp(rot_frames, t, ["angle"])["angle"] if rot_frames else 0.0
    if scale_frames:
        sc = spine_anim._interp(scale_frames, t, ["x", "y"])
        sx, sy = sc["x"], sc["y"]
    else:
        sx, sy = 1.0, 1.0
    xy = spine_anim._interp(tr_frames, t, ["x", "y"]) if tr_frames else {"x": 0.0, "y": 0.0}
    O = np.asarray(O, float)
    return (O + np.array([xy["x"], xy["y"]])) + _M(ang, sx, sy) @ np.asarray(local, float)


def _dense_ts(frames, n=400):
    t0, t1 = frames[0]["time"], frames[-1]["time"]
    return [t0 + (t1 - t0) * i / n for i in range(n + 1)]


def _swing(bezier=False):
    """pure-rotation 擺動 timeline(首尾 identity,峰 24°);bezier=True 加緊湊緩動鍵。"""
    fr = [{"time": 0.0, "angle": 0.0}, {"time": 0.25, "angle": 24.0}, {"time": 0.5, "angle": 0.0}]
    if bezier:
        for f in fr[:-1]:
            f.update({"curve": 0.25, "c2": 0.0, "c3": 0.25, "c4": 1.0})
    return fr


def _load_real_lh():
    """真實 Award 左手件世界輪廓 + 推得肩 pivot。回傳 (pts Nx2, O 件中心, P 肩 pivot, fid)。"""
    parts, truth, tree, fid = ip.load_award_robot(use_alpha=True)
    inf = ip.infer_pivots(parts, tree)
    slot = "機器人拆件/左手"
    pts = np.asarray(parts[slot], float)
    O = pts.mean(axis=0)
    P = np.asarray(inf[slot], float)
    return pts, O, P, fid.get(slot, "?")


def _entry_convert_single(O, P, rot_frames, include_scale=False, scale_frames=None):
    """用**真正的 skill 入口** `apply_joint_pivots` 把單一 bone(落 O)的 rotate(/scale)轉成繞 P。
    回傳 (rot_dense, tr_dense, scale_dense_or_None)。"""
    bone = "b_lh"
    chans = {"rotate": [dict(f) for f in rot_frames]}
    if scale_frames:
        chans["scale"] = [dict(f) for f in scale_frames]
    skel = {
        "bones": [{"name": "root"}, {"name": bone, "parent": "root", "x": O[0], "y": O[1]}],
        "animations": {"T": {"bones": {bone: chans}}},
    }
    conv = PA.apply_joint_pivots(skel, "T", {bone: (float(P[0]), float(P[1]))},
                                 bone_origin={bone: (float(O[0]), float(O[1]))},
                                 include_scale=include_scale)
    out = skel["animations"]["T"]["bones"][bone]
    return out.get("rotate"), out.get("translate"), out.get("scale"), conv


# ----------------------------------------------------------------- validator_v1(雙真值)
def _run_validator_v1(skel, loop_anim):
    """寫檔 → subprocess 呼叫真正的 validator_v1.py → 解析 error / loop 問題。"""
    tmpdir = tempfile.mkdtemp(prefix="b3pivot_")
    jp = os.path.join(tmpdir, "skeleton.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(skel, f, ensure_ascii=False, indent=1)
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


# ----------------------------------------------------------------- AC
def run_all():
    # ===== 共用:gen_lib idle 來源(limb 走 rotate)=====
    idle_skel, idle_name = MB.generate_idle(MB.IDLE_DEMO_PARTS)
    origins = PA.bone_origins_from_skel(idle_skel)
    limb_bones = [b for b in ("b_arm_L", "b_arm_R") if b in idle_skel["animations"][idle_name]["bones"]]
    # 肩 pivot:每 limb bone 原點上方 120px(parent 座標)
    idle_pivots = {b: (origins[b][0], origins[b][1] + 120.0) for b in limb_bones}
    idle_conv = PA.apply_joint_pivots(idle_skel, idle_name, idle_pivots)

    # ---- B3-1 entry + double-truth(G2)----
    api_callable = callable(getattr(PA, "apply_joint_pivots", None))
    conv_is_limbs = sorted(idle_conv) == sorted(limb_bones) and len(limb_bones) >= 1
    v1 = _run_validator_v1(idle_skel, idle_name)
    b31 = api_callable and conv_is_limbs and v1["valid"] and len(v1["errors"]) == 0

    # ---- 真實 Award 幾何(經入口)----
    pts, O, P, fid = _load_real_lh()
    armlen = float(np.linalg.norm(O - P))
    rot_d, tr_d, _, rconv = _entry_convert_single(O, P, _swing(False))
    ell_P = P - O
    ts = _dense_ts(rot_d)

    # ---- B3-2 fixed-point(AC1)----
    fix = max(np.linalg.norm(_world(ell_P, O, rot_d, tr_d, t) - P) for t in ts)
    b32 = fix < TOL_FIX and rconv == ["b_lh"]

    # ---- B3-3 neg-control + rigid + moves(AC2/AC3/AC5)----
    raw_rot = _swing(False)   # 繞件中心 O、無補償
    neg = max(np.linalg.norm(_world(ell_P, O, raw_rot, None, t) - P) for t in ts)
    far_i = int(np.argmax(np.linalg.norm(pts - P, axis=1)))
    far_local = pts[far_i] - O
    far_setup = pts[far_i]
    move = max(np.linalg.norm(_world(far_local, O, rot_d, tr_d, t) - far_setup) for t in ts)
    d0 = np.linalg.norm(pts - P, axis=1)
    worst_abs = 0.0
    for t in ts[::7]:
        for k in range(len(pts)):
            w = _world(pts[k] - O, O, rot_d, tr_d, t)
            worst_abs = max(worst_abs, abs(np.linalg.norm(w - P) - d0[k]))
    b33 = (neg >= MIN_NEG and neg > fix * NEG_RATIO and move >= MIN_MOVE and worst_abs < TOL_RIGID)

    # ---- B3-4 identity interface + loop closure(AC4 + 雙真值)----
    d_t0 = math.hypot(tr_d[0]["x"], tr_d[0]["y"])
    d_tN = math.hypot(tr_d[-1]["x"], tr_d[-1]["y"])
    ident_real = d_t0 < EPS and d_tN < EPS
    # idle:轉後 limb rotate/translate 首尾相等
    seamless = True
    for b in idle_conv:
        for ch in ("rotate", "translate"):
            fr = idle_skel["animations"][idle_name]["bones"][b].get(ch)
            if not fr:
                continue
            if ch == "rotate":
                seamless &= abs(fr[0]["angle"] - fr[-1]["angle"]) < 1e-6
            else:
                seamless &= (abs(fr[0]["x"] - fr[-1]["x"]) < 1e-6
                             and abs(fr[0]["y"] - fr[-1]["y"]) < 1e-6)
    loop_clean = len(v1["loop_problems"]) == 0
    b34 = ident_real and seamless and loop_clean

    # ---- B3-5 scale-about-pivot(B2 pop)+ curve + guard ----
    # (a) B2 大獎 pop beat → 取一個有 scale 的 bone,include_scale=True 繞 pivot 縮放
    pop_skel, pop_name = MB.generate_bigwin(MB.DEMO_PARTS, beat="pop")
    pop_bones = pop_skel["animations"][pop_name]["bones"]
    sc_bone = next((b for b, ch in pop_bones.items() if ch.get("scale")), None)
    scale_pivot_ok = False
    sp_fix = sp_move = None
    if sc_bone is not None:
        Osp = np.array(PA.bone_origins_from_skel(pop_skel)[sc_bone], float)
        Psp = Osp + np.array([0.0, 100.0])         # 合成關節 pivot(原點上方)
        sc_frames = [dict(f) for f in pop_bones[sc_bone]["scale"]]
        rot_frames = [dict(f) for f in pop_bones[sc_bone].get("rotate", [])] or None
        r2, t2, s2, _ = _entry_convert_single(Osp, Psp, rot_frames or _swing(False),
                                               include_scale=True, scale_frames=sc_frames)
        # 若原無 rotate,_entry_convert_single 用 _swing 當佔位會污染 → 改走純 scale 路徑
        if rot_frames is None:
            # 重建:只給 scale(無 rotate),驗 scale-about-pivot
            bone = "b_sc"
            skel2 = {"bones": [{"name": "root"},
                               {"name": bone, "parent": "root", "x": Osp[0], "y": Osp[1]}],
                     "animations": {"T": {"bones": {bone: {"scale": sc_frames}}}}}
            PA.apply_joint_pivots(skel2, "T", {bone: (float(Psp[0]), float(Psp[1]))},
                                  bone_origin={bone: (float(Osp[0]), float(Osp[1]))},
                                  include_scale=True)
            ob = skel2["animations"]["T"]["bones"][bone]
            r2, t2, s2 = ob.get("rotate"), ob.get("translate"), ob.get("scale")
        ell = Psp - Osp
        tss = _dense_ts(t2)
        sp_fix = max(np.linalg.norm(_world(ell, Osp, r2, t2, t, scale_frames=s2) - Psp) for t in tss)
        far = np.array([Osp[0] + 40.0, Osp[1] + 40.0]) - Osp     # 非 pivot 局部點
        far_setup2 = Osp + far
        sp_move = max(np.linalg.norm(_world(far, Osp, r2, t2, t, scale_frames=s2) - far_setup2)
                      for t in tss)
        scale_pivot_ok = (sp_fix < TOL_FIX and sp_move >= 1.0)

    # (b) curve 容忍(bezier 緩動 rotate)
    rb, tb, _, _ = _entry_convert_single(O, P, _swing(True))
    tsb = _dense_ts(rb)
    fix_bez = max(np.linalg.norm(_world(ell_P, O, rb, tb, t) - P) for t in tsb)
    curve_ok = fix_bez < TOL_FIX

    # (c) 守衛:pivot≈件原點 → 該 bone 跳過(無 translate);未知 bone 的 pivot 被忽略
    guard_skel = {
        "bones": [{"name": "root"},
                  {"name": "b_a", "parent": "root", "x": 100.0, "y": 100.0},
                  {"name": "b_b", "parent": "root", "x": 200.0, "y": 100.0}],
        "animations": {"G": {"bones": {
            "b_a": {"rotate": _swing(False)},     # pivot≈原點 → 應跳過
            "b_b": {"rotate": _swing(False)}}}},   # 無 pivot 給 → 不轉
    }
    gconv = PA.apply_joint_pivots(
        guard_skel, "G",
        {"b_a": (100.2, 100.1),                   # 距原點 ~0.22px < 0.5 → 跳過
         "b_zzz_unknown": (0.0, 0.0)},            # skel 無此 bone → 忽略
        bone_origin={"b_a": (100.0, 100.0), "b_b": (200.0, 100.0)})
    guard_skip = (gconv == []
                  and "translate" not in guard_skel["animations"]["G"]["bones"]["b_a"]
                  and "translate" not in guard_skel["animations"]["G"]["bones"]["b_b"])

    b35 = scale_pivot_ok and curve_ok and guard_skip

    res = {
        "B3-1_entry_double_truth": (b31, {
            "public_api_callable": api_callable, "converted": idle_conv,
            "expected_limbs": limb_bones, "v1_valid": v1["valid"],
            "v1_errors": v1["errors"][:3]}),
        "B3-2_fixed_point_real_award": (b32, {
            "limb": fid, "arm_len_px": round(armlen, 1),
            "pivot_residual_max_px": round(fix, 4), "tol": TOL_FIX,
            "converted_via_entry": rconv}),
        "B3-3_negctrl_rigid_moves": (b33, {
            "negctrl_center_disp_px": round(neg, 2), "min_neg": MIN_NEG,
            "neg_over_fix_ratio": round(neg / max(fix, 1e-9), 1), "need_ratio": NEG_RATIO,
            "far_point_move_px": round(move, 2), "min_move": MIN_MOVE,
            "rigid_abs_dev_px": round(worst_abs, 4), "tol_rigid": TOL_RIGID}),
        "B3-4_identity_loop": (b34, {
            "identity_delta_t0_tN_px": [f"{d_t0:.2e}", f"{d_tN:.2e}"],
            "idle_seamless_endpoints": seamless,
            "v1_loop_problems": v1["loop_problems"][:3]}),
        "B3-5_scale_pivot_curve_guard": (b35, {
            "scale_about_pivot_bone": sc_bone,
            "scale_pivot_residual_px": None if sp_fix is None else round(sp_fix, 4),
            "scale_nonpivot_move_px": None if sp_move is None else round(sp_move, 3),
            "bezier_fixed_point_px": round(fix_bez, 4),
            "guard_skip_near_origin_and_unknown": guard_skip,
            "guard_converted": gconv}),
    }
    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "B3 pivot_axis: joint-pivot transform entry (Δ=(M−I)(O−P)) → geometry truth + v1.3.0 validator_v1",
        "entry": "skills/spine-ai-editor/assets/gen_lib/pivot_axis.py :: apply_joint_pivots / bone_origins_from_skel",
        "source": "gen_lib.generate_idle (limb rotate) + gen_lib.generate_bigwin pop (scale) + real Award 左手→肩 pivot",
        "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()},
    }


def _py(o):
    """把 numpy 標量轉成原生型別,供 json.dumps。"""
    if isinstance(o, dict):
        return {k: _py(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_py(x) for x in o]
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, np.integer):
        return int(o)
    if isinstance(o, np.floating):
        return float(o)
    return o


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="完整 JSON 報告")
    a = ap.parse_args()
    report = _py(run_all())
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"overall_pass": report["overall_pass"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()},
                          "detail": {k: v["detail"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
