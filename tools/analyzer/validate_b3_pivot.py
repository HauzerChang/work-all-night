#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B3 閘 — `gen_lib` 繞關節 pivot 變換入口 → 幾何不動點 + v1.3.0 `validator_v1`(spine-ai-editor 2.0 Phase B3)。

repo 的 `validate_pivot_rotation.py` 已對**底層** `pivot_rotation` 的繞 pivot 數學證了 7 AC(真實 Award 肩
pivot 不動點殘差 < 0.5px、負對照、剛性、identity 介面、端到端)。B3 把那條能力**包成一條 skill 公開 API**
`skills/spine-ai-editor/assets/gen_lib/pivot_about_joint.py :: pivot_about_joint()`,並補上 repo 閘**沒驗**的
一層:**經此入口補償後的動畫,仍能過 v1.3.0 `validator_v1` 的 editor 匯入雙真值閘**(地雷 #12 末鍵 curve +
loop 閉合)。這正是把 pivot 能力「併進結構軸」的真正風險面——補償會**新增一條 dense translate 通道**,
要證它不破壞「遊戲能播 **且** 編輯器能匯入」(MERGE_PLAN G2)。

**驗的是什麼(為何這個 chunk 有價值)**:
  「件繞關節 pivot 轉」原本有兩條路:移 bone(結構改動,Cocos 須重 import)/ keyframe 補償(零結構改動)。
  B3 把後者固化成 skill 公開 API,並機械化證明它(a)幾何正確(經入口後 pivot 不動點殘差 < 門檻)、
  (b)負對照(繞件中心)會明顯漂、(c)identity/loop 介面保持無縫、(d)**過 editor 匯入雙真值閘**。
  Cocos 實機 round-trip/視覺確認 = 使用者端(排程 scope 邊界),本閘用 spine-webgl 無頭等價(validator_v1)替代。

**AC(全部客觀、可機讀)**:
  B3-1 entrypoint          : `gen_lib.pivot_about_joint`(**公開 API**,非直呼 repo 底層)把 demo limb Loop
                             就地轉成繞 pivot 版 → converts 該 limb bone;輸出通道有限、時間嚴格遞增、
                             已加密(dense keys >> 原鍵數)。
  B3-2 pivot-fixed(核心)  : **真實 Award 左手繞肩 pivot**——經入口補償後,pivot 的附著點世界座標逐幀 == P
                             (最大殘差 < TOL_FIX)。移植 repo AC1 到 skill API 路徑。
  B3-3 neg-control         : (a)**不補償**(繞件中心 O)時 pivot 明顯位移(>> B3-2 且 ≥ MIN_NEG,比值 ≥ NEG_RATIO);
                             (b)補償版件最遠點仍確有位移(≥ MIN_MOVE)→ 沒把件凍住。證閘非恆真。
  B3-4 identity/loop       : θ=0 幀補償 Δ=0(< EPS);Loop 首尾 rotate/translate 端點相等 → 繞 pivot 補償**保持
                             無縫 Loop 介面**(B1/B2 的 loop 閉合性質不被 pivot 補償破壞)。
  B3-5 editor double-truth : 完整 skeleton(root+limb+slot)的 limb Loop 經入口補償 → `validator_v1`
                             **0 error**(editor 可匯入,含末鍵 curve 檢查)+ loop 閉合 0 問題;
                             **負對照**:補償後注入末鍵 curve → validator_v1 **抓到** editor-crash;
                             入口 G1 wired(apply_g1=True → 無末鍵 curve)。證補償不破壞 G2 雙真值。

用法:
  python3 validate_b3_pivot.py          # 跑 B3-1..B3-5,印精簡 pass/fail + 關鍵量化
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

import spine_anim                       # noqa: E402  repo tools/analyzer
import pivot_about_joint as PJ          # noqa: E402  B3 skill 入口(gen_lib)

_VALIDATOR_V1 = os.path.join(_SKILL_ASSETS, "validator_v1.py")

TOL_FIX = 0.5       # px,pivot 不動點幀間最大殘差上限
MIN_NEG = 10.0      # px,負對照(繞件中心)pivot 位移下限
MIN_MOVE = 8.0      # px,件最遠點位移下限(證有轉)
NEG_RATIO = 20.0    # AC3/AC2 位移比下限
EPS = 1e-6


# ----------------------------------------------------------------- 世界變換模擬(純 Python)
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


def _swing(peak=24.0):
    return [{"time": 0.0, "angle": 0.0}, {"time": 0.25, "angle": peak}, {"time": 0.5, "angle": 0.0}]


def _load_real_shoulder():
    """真實 Award 左手件世界輪廓 + infer_pivots 推得肩 pivot。
    成功回 ("OK", pts Nx2, O 件中心, P pivot, fid);資產/依賴缺失回 ("ERR", 原因字串)。"""
    try:
        import infer_pivots as ip
        cwd = os.getcwd()
        repo = os.path.normpath(os.path.join(_HERE, "..", ".."))
        os.chdir(repo)                               # load_award_robot 用相對路徑 assets/Award.json
        try:
            parts, truth, tree, fid = ip.load_award_robot(use_alpha=True)
            inf = ip.infer_pivots(parts, tree)
        finally:
            os.chdir(cwd)
        slot = "機器人拆件/左手"
        pts = np.asarray(parts[slot], float)
        O = pts.mean(axis=0)
        P = np.asarray(inf[slot], float)
        return ("OK", pts, O, P, fid.get(slot, "?"))
    except Exception as e:                            # noqa: BLE001
        return ("ERR", str(e))


# ----------------------------------------------------------------- validator_v1(editor 雙真值)
def _run_validator_v1(skel, loop_anim, mutator=None):
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


def _full_skel_with_limb_loop():
    """最小完整 skeleton:root + limb bone(落件中心 O)+ 一個 slot/attachment。
    limb 有 Loop rotate(首尾 identity)→ 經入口繞 pivot 補償後丟 validator_v1。回傳 (skel, O, P, anim_name)。"""
    O, P = PJ.DEMO_O, PJ.DEMO_P
    bn = PJ.DEMO_BONE
    skel = {
        "skeleton": {"hash": "b3pivot", "spine": "3.8.75", "x": 0, "y": 0,
                     "width": 700, "height": 700, "images": "./"},
        "bones": [{"name": "root"},
                  {"name": bn, "parent": "root", "x": O[0], "y": O[1]}],
        "slots": [{"name": "arm_L", "bone": bn, "attachment": "arm_L"}],
        "skins": {"default": {"arm_L": {"arm_L": {"width": 32, "height": 32}}}},
        "animations": {},
    }
    anim = {"bones": {bn: {"rotate": _swing()}}, "slots": {}}
    skel["animations"]["Loop_pivot"] = anim
    return skel, O, P, "Loop_pivot"


def _inject_last_frame_curve(data, aname):
    anim = data["animations"][aname]
    for tls in anim.get("bones", {}).values():
        for frames in tls.values():
            if isinstance(frames, list) and len(frames) >= 2 and isinstance(frames[-1], dict):
                frames[-1].update({"curve": 0.25, "c2": 0.0, "c3": 0.75, "c4": 1.0})
                return
    raise RuntimeError("找不到可注入末鍵 curve 的 bone timeline(負對照前提壞了)")


# ----------------------------------------------------------------- AC
def run_all():
    pr_api_callable = callable(getattr(PJ, "pivot_about_joint", None))

    # ---- B3-1 entrypoint:公開 API 把 demo limb Loop 轉成繞 pivot 版 ----
    anim1 = PJ.demo_limb_loop()
    n_raw = len(anim1["bones"][PJ.DEMO_BONE]["rotate"])
    conv1 = PJ.pivot_about_joint(anim1, {PJ.DEMO_BONE: PJ.DEMO_O},
                                 {PJ.DEMO_BONE: PJ.DEMO_P}, mode="rotate")
    rot1 = anim1["bones"][PJ.DEMO_BONE].get("rotate", [])
    tr1 = anim1["bones"][PJ.DEMO_BONE].get("translate", [])
    times = [f["time"] for f in rot1]
    mono = all(b > a for a, b in zip(times, times[1:]))
    dense = len(rot1) > n_raw and len(tr1) == len(rot1)
    finite1 = spine_anim.all_finite(anim1)
    b31 = pr_api_callable and (PJ.DEMO_BONE in conv1) and mono and dense and finite1

    # ---- 真值幾何(真實 Award 肩 pivot;缺資產則合成)----
    real = _load_real_shoulder()
    if real[0] == "ERR":
        # 合成 fallback(肩在件中心上外側 ~160px)
        truth_src = "synthetic"
        pts = np.array([[250. + 40 * math.cos(a), 300. + 60 * math.sin(a)]
                        for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)])
        O = pts.mean(axis=0); P = np.array([330.0, 440.0]); fid = "synthetic-arm"
        real_err = real[1]
    else:
        truth_src = "real-Award"
        _, pts, O, P, fid = real
        real_err = None
    armlen = float(np.linalg.norm(O - P))

    # ---- B3-2 pivot-fixed(經入口補償,真值幾何)----
    ell_P = (P - O)
    anim2 = {"bones": {"b_lh": {"rotate": _swing()}}, "slots": {}}
    raw_rot2 = [dict(f) for f in anim2["bones"]["b_lh"]["rotate"]]
    PJ.pivot_about_joint(anim2, {"b_lh": tuple(O)}, {"b_lh": tuple(P)}, mode="rotate")
    rot2 = anim2["bones"]["b_lh"]["rotate"]
    tr2 = anim2["bones"]["b_lh"]["translate"]
    ts = _dense_ts(rot2)
    fix = max(float(np.linalg.norm(_world_of(ell_P, O, rot2, tr2, t) - P)) for t in ts)
    b32 = fix < TOL_FIX

    # ---- B3-3 neg-control(繞件中心漂 + 件最遠點有動)----
    neg = max(float(np.linalg.norm(_world_of(ell_P, O, raw_rot2, None, t) - P)) for t in ts)
    far_i = int(np.argmax(np.linalg.norm(pts - P, axis=1)))
    far_local = pts[far_i] - O
    move = max(float(np.linalg.norm(_world_of(far_local, O, rot2, tr2, t) - pts[far_i])) for t in ts)
    b33 = (neg >= MIN_NEG) and (neg > fix * NEG_RATIO) and (move >= MIN_MOVE)

    # ---- B3-4 identity / loop seamless ----
    d_t0 = math.hypot(tr2[0]["x"], tr2[0]["y"])
    d_tN = math.hypot(tr2[-1]["x"], tr2[-1]["y"])
    loop_rot_closed = abs(rot2[0]["angle"] - rot2[-1]["angle"]) < EPS
    loop_tr_closed = (abs(tr2[0]["x"] - tr2[-1]["x"]) < EPS and
                      abs(tr2[0]["y"] - tr2[-1]["y"]) < EPS)
    b34 = (d_t0 < EPS) and (d_tN < EPS) and loop_rot_closed and loop_tr_closed

    # ---- B3-5 editor double-truth(validator_v1 + 負對照)----
    skel, sO, sP, aname = _full_skel_with_limb_loop()
    PJ.pivot_about_joint(skel["animations"][aname], {PJ.DEMO_BONE: sO},
                         {PJ.DEMO_BONE: sP}, mode="rotate")
    v1 = _run_validator_v1(skel, aname)
    editor_ok = v1["valid"] and len(v1["errors"]) == 0
    loop_ok = len(v1["loop_problems"]) == 0
    # 入口 G1 wired:補償後預設無末鍵 curve
    def_clean = not any(
        isinstance(fr, list) and fr and isinstance(fr[-1], dict)
        and any(k in fr[-1] for k in ("curve", "c2", "c3", "c4"))
        for sec in ("bones", "slots")
        for tls in skel["animations"][aname].get(sec, {}).values()
        for fr in tls.values())
    # 負對照:補償後注入末鍵 curve → validator_v1 抓到 editor-crash
    neg_curve = _run_validator_v1(skel, aname,
                                  mutator=lambda d: _inject_last_frame_curve(d, aname))
    curve_caught = (not neg_curve["valid"]) and any(
        ("最後一鍵帶 curve" in e) or ("AIOOBE" in e) for e in neg_curve["errors"])
    b35 = editor_ok and loop_ok and def_clean and curve_caught

    res = {
        "B3-1_entrypoint": (b31, {
            "public_api_callable": pr_api_callable, "converted": conv1,
            "raw_keys": n_raw, "dense_keys": len(rot1),
            "time_monotonic": mono, "translate_matches_rotate": len(tr1) == len(rot1)}),
        "B3-2_pivot_fixed": (b32, {
            "truth": truth_src, "part": fid, "verts": int(len(pts)),
            "arm_len_px": round(armlen, 1),
            "pivot_residual_max_px": round(fix, 4), "tol": TOL_FIX}),
        "B3-3_neg_control": (b33, {
            "neg_about_center_px": round(neg, 2), "min_neg": MIN_NEG,
            "neg_over_fix_ratio": round(neg / max(fix, 1e-9), 1), "need_ratio": NEG_RATIO,
            "far_point_move_px": round(move, 2), "min_move": MIN_MOVE}),
        "B3-4_identity_loop_seamless": (b34, {
            "delta_t0_px": float(f"{d_t0:.2e}"), "delta_tN_px": float(f"{d_tN:.2e}"),
            "loop_rotate_closed": loop_rot_closed, "loop_translate_closed": loop_tr_closed}),
        "B3-5_editor_double_truth": (b35, {
            "validator_v1_valid": editor_ok, "validator_v1_errors": v1["errors"][:2],
            "loop_closure_ok": loop_ok, "entry_default_g1_clean": def_clean,
            "neg_last_frame_curve_caught": curve_caught,
            "neg_curve_errors": neg_curve["errors"][:2]}),
    }
    overall = all(v[0] for v in res.values())
    report = {
        "overall_pass": overall,
        "chunk": "B3 pivot_about_joint: packaged skill entry (繞關節 pivot 變換,零結構改動) "
                 "→ 幾何不動點 + v1.3.0 validator_v1 editor 雙真值",
        "entry": "skills/spine-ai-editor/assets/gen_lib/pivot_about_joint.py :: pivot_about_joint",
        "truth_source": truth_src,
        "ac": {k: {"pass": v[0], "detail": v[1]} for k, v in res.items()},
    }
    if real_err:
        report["real_truth_unavailable"] = real_err
    return report


def _py(o):
    """遞迴把 numpy 標量/bool 轉成原生 Python 型別,供 json.dumps。"""
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true", help="完整 JSON 報告")
    a = ap.parse_args()
    report = _py(run_all())
    if a.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(json.dumps({"overall_pass": report["overall_pass"],
                          "truth_source": report["truth_source"],
                          "ac": {k: v["pass"] for k, v in report["ac"].items()}},
                         ensure_ascii=False, indent=2))
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
