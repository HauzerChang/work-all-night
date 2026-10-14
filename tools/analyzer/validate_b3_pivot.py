#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B3 閘 — `gen_lib` 繞關節 pivot 變換入口 → 幾何不動點真值 + v1.3.0 `validator_v1`
(spine-ai-editor 2.0 Phase B3)。

B1/B2 把「大獎節拍生成」接進 v1.3.0 編輯器真值閘。B3 把 repo 的**繞關節 pivot 變換引擎**
(`pivot_rotation.py`)抽成一條**可重用的 skill 結構軸入口**
`skills/spine-ai-editor/assets/gen_lib/pivot_about_joint.py`
(`apply_pivot_about_joint` / `apply_pivot_about_joint_anim`),讓 limb 繞**關節 pivot** 轉/縮/剪
而非件中心,且**不動骨架結構**。本閘證明:

  (甲) **經 skill 入口**(非臨時腳本)套用後,件確實繞關節 pivot(殘差 < 門檻),對照繞件中心的負對照;
  (乙) 套用後的輸出仍過**雙真值閘**(G2):editor 可匯入(validator_v1 0 error)+ loop 閉合。

真值來源 = 真實 Award 機器人拆件世界幾何 + `infer_pivots` 推得的接觸縫 pivot(左手繞肩),
與 repo 既有 `validate_pivot_rotation.py` 同一真值;本閘把那套 7AC **移植**並**改走 skill 入口**,
另加 B 階段固有的**編輯器雙真值閘**(repo 原 7AC 沒有的維度)。

**AC(全部客觀、可機讀)**:
  B3-1 entrypoint+schema : `apply_pivot_about_joint` 為公開 callable;對 B2 `generate_bigwin` 產的
                           cascade beat(include_scale)套用 → 轉換 ≥1 limb bone 且輸出 schema 合法
                           (validator_v1 底層 v0 0 schema error;非臨時腳本)。
  B3-2 pivot-fixed(crux): 真實 Award 左手 O + 推得肩 pivot P,經 skill 入口套 24° 擺動 →
                           (a) pivot 附著點殘差 < TOL_FIX(AC1);(b) 剛性等距 worst_abs < TOL_RIGID(AC5);
                           (c) 件最遠點位移 ≥ MIN_MOVE(AC3,沒把件凍住)。
  B3-3 negctrl+identity  : (a) **不補償**(繞件中心 O)pivot 位移 >> 補償版(比值 ≥ NEG_RATIO 且 ≥ MIN_NEG,
                           AC2 → 閘非恆真);(b) θ=0 幀 Δ=0(AC4 identity 介面保持)。
  B3-4 editor-import(G2) : 經 skill 入口套用後的生成 beat **仍過編輯器真值閘**——
                           (a) cascade(include_scale,M=R·S)validator_v1 **0 error** + loop 閉合 0;
                           (b) wobble(include_shear,一般仿射含 shear)validator_v1 **0 error**;
                           (c) bezier 緩動擺動 pivot 殘差仍 < TOL_FIX(AC7 加密重取樣正確處理 curve)。
  B3-5 end2end+non-vacuous: (a) 經真實 `build_animations` Loop → skill 入口 → finite/無縫/pivot 不動 +
                           內建負對照未套用會動(AC6);(b) 對套用後 beat **注入末鍵 curve** → validator_v1
                           **抓到** editor-crash(地雷 #12),預設 apply_g1=True 輸出乾淨 → 證編輯器閘在本軸非恆真。

用法:
  python3 validate_b3_pivot.py            # 跑 B3-1..B3-5,印精簡 pass/fail
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
_REPO = os.path.normpath(os.path.join(_HERE, "..", ".."))
_SKILL_ASSETS = os.path.join(_REPO, "skills", "spine-ai-editor", "assets")
for _p in (_HERE, os.path.join(_HERE, "..", "rig"), os.path.join(_HERE, "..", "mesh_gen"),
           _SKILL_ASSETS, os.path.join(_SKILL_ASSETS, "gen_lib")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import spine_anim                                   # noqa: E402
import infer_pivots as ip                           # noqa: E402
import make_beat as MB                              # noqa: E402  B2 生成入口
import pivot_about_joint as PAJ                     # noqa: E402  B3 skill 結構軸入口

_VALIDATOR_V1 = os.path.join(_SKILL_ASSETS, "validator_v1.py")

# --- 門檻(沿用 repo validate_pivot_rotation.py,同一真值同一尺度)---
TOL_FIX = 0.5      # px,pivot 不動點幀間最大殘差上限
TOL_RIGID = 0.5    # px,到 P 距離絕對偏差上限(等距)
MIN_NEG = 10.0     # px,負對照(繞件中心)pivot 位移下限
MIN_MOVE = 8.0     # px,件最遠點位移下限(證有轉)
EPS = 1e-6
NEG_RATIO = 20.0   # AC2/AC1 位移比下限


# ----------------------------------------------------------------- 幾何模擬(純 Python)
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


def _apply_entry_single(rot_frames, O, P):
    """**經 skill 入口** apply_pivot_about_joint_anim 把單 bone rotate 轉成繞 pivot 版。
    回傳套用後的 (rotate_dense, translate_dense)。"""
    bone = "b_test"
    anim = {"bones": {bone: {"rotate": [dict(f) for f in rot_frames]}}}
    conv = PAJ.apply_pivot_about_joint_anim(
        anim, {bone: tuple(O)}, {bone: tuple(P)}, apply_g1=True)
    assert conv == [bone], "skill 入口未轉換測試 bone(前提壞了):{}".format(conv)
    return anim["bones"][bone]["rotate"], anim["bones"][bone]["translate"]


def _pivot_metrics(pts, O, P, rot_frames):
    """經 skill 入口套用後的量測(補償版 + 繞件中心負對照)。"""
    rot_d, tr_d = _apply_entry_single(rot_frames, O, P)
    ell_P = P - O
    ts = _dense_ts(rot_frames)
    fix = max(np.linalg.norm(_world_of(ell_P, O, rot_d, tr_d, t) - P) for t in ts)
    neg = max(np.linalg.norm(_world_of(ell_P, O, rot_frames, None, t) - P) for t in ts)
    far_i = int(np.argmax(np.linalg.norm(pts - P, axis=1)))
    far_local = pts[far_i] - O
    far_setup = pts[far_i]
    move = max(np.linalg.norm(_world_of(far_local, O, rot_d, tr_d, t) - far_setup) for t in ts)
    d0 = np.linalg.norm(pts - P, axis=1)
    worst_abs = 0.0
    for t in ts[::7]:
        for k in range(len(pts)):
            w = _world_of(pts[k] - O, O, rot_d, tr_d, t)
            worst_abs = max(worst_abs, abs(np.linalg.norm(w - P) - d0[k]))
    d_t0 = math.hypot(tr_d[0]["x"], tr_d[0]["y"])
    d_tN = math.hypot(tr_d[-1]["x"], tr_d[-1]["y"])
    return dict(fix=fix, neg=neg, move=move, rigid=worst_abs, d0=d_t0, dN=d_tN, nkeys=len(rot_d))


# ----------------------------------------------------------------- validator_v1(編輯器真值閘)
def _run_validator_v1(skel, loop_anim, mutator=None):
    """寫檔 → 呼叫真正的 validator_v1.py(subprocess)→ 解析 {valid, errors[], loop_problems[]}。"""
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


def _inject_last_frame_curve(data, aname):
    """把某 bone timeline 末鍵塞 curve(模擬未拔末鍵 → 地雷 #12)。"""
    anim = data["animations"][aname]
    for tls in anim.get("bones", {}).values():
        for frames in tls.values():
            if isinstance(frames, list) and len(frames) >= 2 and isinstance(frames[-1], dict):
                frames[-1].update({"curve": 0.25, "c2": 0.0, "c3": 0.75, "c4": 1.0})
                return
    raise RuntimeError("找不到可注入末鍵 curve 的 bone timeline(負對照前提壞了)")


def _gen_beat_with_pivots(beat, include_scale=False, include_shear=False, apply_g1=True):
    """B2 生成 beat → 設每件 pivot 在 bone 原點下方 100px → 經 skill 入口套關節軸。
    回傳 (skel, anim_name, converted dict)。"""
    skel, aname = MB.generate_bigwin(MB.DEMO_PARTS, beat=beat)
    bo = PAJ._bone_origin_from_skel(skel)
    pivot_of = {b: (bo[b][0], bo[b][1] - 100.0) for b in bo}      # 件外 pivot(模擬關節)
    conv = PAJ.apply_pivot_about_joint(
        skel, pivot_of, include_scale=include_scale, include_shear=include_shear,
        apply_g1=apply_g1)
    return skel, aname, conv


def _last_frame_curve_count(skel):
    """統計整份 skeleton 所有 animation timeline 的末鍵帶 curve 數(應為 0)。"""
    bad = 0
    for anim in skel.get("animations", {}).values():
        for sec in ("bones", "slots"):
            for tls in anim.get(sec, {}).values():
                for fr in tls.values():
                    if isinstance(fr, list) and fr and isinstance(fr[-1], dict) \
                       and any(k in fr[-1] for k in ("curve", "c2", "c3", "c4")):
                        bad += 1
    return bad


# ----------------------------------------------------------------- 端到端(真實 build_animations)
def _synthetic_skeleton():
    return {
        "skeleton": {"width": 700, "height": 700},
        "bones": [
            {"name": "root"},
            {"name": "b_身體", "parent": "root", "x": 350, "y": 350},
            {"name": "b_左手", "parent": "root", "x": 250, "y": 300},
            {"name": "b_頭", "parent": "root", "x": 360, "y": 520},
        ],
        "slots": [], "skins": {"default": {}}, "animations": {},
    }


def _synthetic_storyboard():
    return {"beats": [{"beat": "Loop", "parts": [
        {"part": "身體", "role": "body"},
        {"part": "左手", "role": "limb"},
        {"part": "頭", "role": "head"},
    ]}]}


# ----------------------------------------------------------------- AC
def run_all():
    pts, O, P, fid = _load_real()
    armlen = float(np.linalg.norm(O - P))

    # ---- B3-2 / B3-3(linear swing,經 skill 入口)----
    m = _pivot_metrics(pts, O, P, _swing(bezier=False))
    b32 = (m["fix"] < TOL_FIX) and (m["rigid"] < TOL_RIGID) and (m["move"] >= MIN_MOVE)
    b33a = (m["neg"] >= MIN_NEG) and (m["neg"] > m["fix"] * NEG_RATIO)
    b33b = (m["d0"] < EPS) and (m["dN"] < EPS)
    b33 = b33a and b33b

    # ---- B3-1 entrypoint+schema(生成 beat + 經公開 API 套關節軸)----
    api_callable = callable(getattr(PAJ, "apply_pivot_about_joint", None))
    cas_skel, cas_name, cas_conv = _gen_beat_with_pivots("cascade", include_scale=True)
    v1_cas = _run_validator_v1(cas_skel, cas_name)
    schema_errs = [e for e in v1_cas["errors"]
                   if any(k in e for k in ("missing", "not found", "unknown", "parse failed"))]
    n_conv = len(cas_conv.get(cas_name, []))
    b31 = api_callable and (n_conv >= 1) and (not schema_errs)

    # ---- B3-4 editor-import 雙真值(G2)+ AC7 ----
    #  (a) cascade include_scale(M=R·S)過 validator_v1 0 error + loop 閉合 0
    b34a = v1_cas["valid"] and (len(v1_cas["errors"]) == 0) and (len(v1_cas["loop_problems"]) == 0)
    #  (b) wobble include_shear(一般仿射含 shear)過 validator_v1 0 error
    wob_skel, wob_name, wob_conv = _gen_beat_with_pivots("wobble", include_shear=True)
    v1_wob = _run_validator_v1(wob_skel, wob_name)
    b34b = v1_wob["valid"] and (len(v1_wob["errors"]) == 0) and (len(wob_conv.get(wob_name, [])) >= 1)
    #  (c) bezier 緩動 pivot 殘差仍 < TOL_FIX
    mb = _pivot_metrics(pts, O, P, _swing(bezier=True))
    b34c = mb["fix"] < TOL_FIX
    b34 = b34a and b34b and b34c

    # ---- B3-5 端到端 + 非恆真編輯器閘 ----
    #  (a) 真實 build_animations Loop → skill 入口
    from gen_animations import build_animations
    sk = _synthetic_skeleton()
    anims = build_animations(sk, _synthetic_storyboard())
    loop = anims["Loop"]
    bone_origin = {b["name"]: (b.get("x", 0.0), b.get("y", 0.0))
                   for b in sk["bones"] if b["name"] != "root"}
    pivots = {"b_左手": (350.0, 350.0), "b_頭": (355.0, 420.0)}
    loop_raw_rot = [dict(f) for f in loop["bones"]["b_左手"]["rotate"]]
    conv = PAJ.apply_pivot_about_joint_anim(loop, bone_origin, pivots, apply_g1=True)
    finite = spine_anim.all_finite(loop)
    seamless = True
    for b in conv:
        for ch in ("rotate", "translate"):
            fr = loop["bones"][b].get(ch)
            if not fr:
                continue
            if ch == "rotate":
                seamless &= abs(fr[0]["angle"] - fr[-1]["angle"]) < 1e-6
            else:
                seamless &= abs(fr[0]["x"] - fr[-1]["x"]) < 1e-6 and abs(fr[0]["y"] - fr[-1]["y"]) < 1e-6
    O_lh = np.array(bone_origin["b_左手"]); P_lh = np.array(pivots["b_左手"])
    rr = loop["bones"]["b_左手"]["rotate"]; tt = loop["bones"]["b_左手"]["translate"]
    ell = P_lh - O_lh
    ts = _dense_ts(rr)
    fix_e = max(np.linalg.norm(_world_of(ell, O_lh, rr, tt, t) - P_lh) for t in ts)
    neg_e = max(np.linalg.norm(_world_of(ell, O_lh, loop_raw_rot, None, t) - P_lh) for t in ts)
    b35a = finite and seamless and (fix_e < TOL_FIX) and (neg_e > fix_e * NEG_RATIO) and (neg_e >= 1.0)

    #  (b) 非恆真:套用後 beat 預設乾淨;注入末鍵 curve → validator_v1 抓到
    def_clean = _last_frame_curve_count(cas_skel) == 0
    neg_curve = _run_validator_v1(cas_skel, cas_name,
                                  mutator=lambda d: _inject_last_frame_curve(d, cas_name))
    curve_caught = (not neg_curve["valid"]) and any(
        ("最後一鍵帶 curve" in e) or ("AIOOBE" in e) for e in neg_curve["errors"])
    b35b = def_clean and curve_caught
    b35 = b35a and b35b

    res = {
        "B3-1_entrypoint_schema": (b31, {
            "public_api_callable": api_callable, "converted_bones": n_conv,
            "schema_errors": schema_errs}),
        "B3-2_pivot_fixed_point": (b32, {
            "fix_px": round(m["fix"], 4), "rigid_px": round(m["rigid"], 4),
            "far_move_px": round(m["move"], 2), "dense_keys": m["nkeys"]}),
        "B3-3_negctrl_identity": (b33, {
            "neg_center_px": round(m["neg"], 2), "ratio": round(m["neg"] / max(m["fix"], 1e-9), 1),
            "identity_d0": m["d0"], "identity_dN": m["dN"]}),
        "B3-4_editor_import_G2": (b34, {
            "cascade_scale_valid": b34a, "cascade_errors": v1_cas["errors"][:2],
            "cascade_loop_problems": v1_cas["loop_problems"][:2],
            "wobble_shear_valid": b34b, "wobble_errors": v1_wob["errors"][:2],
            "bezier_fix_px": round(mb["fix"], 4)}),
        "B3-5_end2end_non_vacuous": (b35, {
            "finite": finite, "seamless": seamless, "e2e_fix_px": round(fix_e, 4),
            "e2e_negctrl_px": round(neg_e, 2), "default_clean": def_clean,
            "neg_curve_caught": curve_caught, "neg_curve_errors": neg_curve["errors"][:2]}),
    }
    overall = all(v[0] for v in res.values())
    return {
        "overall_pass": overall,
        "chunk": "B3 pivot-about-joint: packaged skill structural axis (pivot_rotation) "
                 "→ real-truth fixed-point + v1.3.0 validator_v1 (editor double-truth)",
        "entry": "skills/spine-ai-editor/assets/gen_lib/pivot_about_joint.py "
                 ":: apply_pivot_about_joint / apply_pivot_about_joint_anim",
        "truth": {"part": fid, "verts": len(pts),
                  "O": [round(float(O[0]), 1), round(float(O[1]), 1)],
                  "P": [round(float(P[0]), 1), round(float(P[1]), 1)],
                  "armlen_px": round(armlen, 1)},
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
        print("=" * 70)
        print("B3 繞關節 pivot 變換(skill 入口)— 幾何真值 + 編輯器雙真值閘")
        print("=" * 70)
        t = report["truth"]
        print("真值:{} verts={} O={} 肩 pivot P={} |O-P|={}px".format(
            t["part"], t["verts"], t["O"], t["P"], t["armlen_px"]))
        for k, v in report["ac"].items():
            print("  {}  {}".format("PASS" if v["pass"] else "FAIL", k))
            print("        {}".format(json.dumps(v["detail"], ensure_ascii=False)))
        print("-" * 70)
        print("OVERALL:", "PASS ✅" if report["overall_pass"] else "FAIL ❌")
    sys.exit(0 if report["overall_pass"] else 1)


if __name__ == "__main__":
    main()
